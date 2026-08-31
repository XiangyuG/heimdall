#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <errno.h>
#include <linux/bpf.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static int read_stats(struct bpf_program *program, struct bpf_prog_info *info)
{
	__u32 len = sizeof(*info);

	memset(info, 0, sizeof(*info));
	return bpf_obj_get_info_by_fd(bpf_program__fd(program), info, &len);
}

int main(int argc, char **argv)
{
	const char *object_path = argc > 1 ? argv[1] : "tcprtt.o";
	const char *mode = argc > 2 ? argv[2] : "fentry";
	int seconds = argc > 3 ? atoi(argv[3]) : 60;
	int max_entries = argc > 4 ? atoi(argv[4]) : 256;
	const char *selected_name;
	struct bpf_object *object = NULL;
	struct bpf_program *program;
	struct bpf_program *selected = NULL;
	struct bpf_map *hists;
	struct bpf_link *link = NULL;
	struct bpf_prog_info before, after;
	__u64 run_count, run_time;
	int error = 1;

	if (!strcmp(mode, "fentry"))
		selected_name = "tcp_rcv";
	else if (!strcmp(mode, "kprobe"))
		selected_name = "tcp_rcv_kprobe";
	else {
		fprintf(stderr, "mode must be fentry or kprobe\n");
		return 2;
	}
	if (seconds <= 0 || max_entries <= 0) {
		fprintf(stderr, "duration and max_entries must be positive\n");
		return 2;
	}

	libbpf_set_strict_mode(LIBBPF_STRICT_ALL);
	object = bpf_object__open_file(object_path, NULL);
	if (libbpf_get_error(object)) {
		fprintf(stderr, "failed to open %s: %s\n", object_path,
			strerror(errno));
		return 1;
	}

	bpf_object__for_each_program(program, object) {
		bool chosen = !strcmp(bpf_program__name(program), selected_name);

		bpf_program__set_autoload(program, chosen);
		if (chosen)
			selected = program;
	}
	if (!selected) {
		fprintf(stderr, "program %s was not found in %s\n",
			selected_name, object_path);
		goto cleanup;
	}

	hists = bpf_object__find_map_by_name(object, "hists");
	if (!hists || bpf_map__set_max_entries(hists, max_entries)) {
		fprintf(stderr, "failed to configure hists map\n");
		goto cleanup;
	}
	if (bpf_object__load(object)) {
		fprintf(stderr, "failed to load %s in %s mode\n",
			object_path, mode);
		goto cleanup;
	}

	if (!strcmp(mode, "fentry"))
		link = bpf_program__attach_trace(selected);
	else
		link = bpf_program__attach_kprobe(selected, false,
					  "tcp_rcv_established");
	if (libbpf_get_error(link)) {
		int attach_error = libbpf_get_error(link);

		link = NULL;
		fprintf(stderr, "failed to attach %s: %s\n", selected_name,
			strerror(-attach_error));
		goto cleanup;
	}
	if (read_stats(selected, &before)) {
		fprintf(stderr, "failed to read initial BPF statistics: %s\n",
			strerror(errno));
		goto cleanup;
	}

	printf("Loaded %s program %s (%s), ID %u, for %d seconds.\n",
	       object_path, selected_name, mode, before.id, seconds);
	printf("Generate TCP traffic during this interval.\n");
	fflush(stdout);
	sleep(seconds);

	if (read_stats(selected, &after)) {
		fprintf(stderr, "failed to read final BPF statistics: %s\n",
			strerror(errno));
		goto cleanup;
	}
	run_count = after.run_cnt - before.run_cnt;
	run_time = after.run_time_ns - before.run_time_ns;
	printf("\n%-24s %15s %18s %14s\n",
	       "program", "run_cnt", "run_time_ns", "ns/run");
	if (run_count)
		printf("%-24s %15llu %18llu %14.2f\n", selected_name,
		       (unsigned long long)run_count,
		       (unsigned long long)run_time,
		       (double)run_time / (double)run_count);
	else
		printf("%-24s %15llu %18llu %14s\n", selected_name,
		       (unsigned long long)run_count,
		       (unsigned long long)run_time, "n/a");
	error = 0;

cleanup:
	bpf_link__destroy(link);
	bpf_object__close(object);
	return error;
}
