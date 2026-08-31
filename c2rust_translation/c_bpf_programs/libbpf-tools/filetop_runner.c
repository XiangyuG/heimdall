#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <errno.h>
#include <linux/bpf.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define ARRAY_SIZE(x) (sizeof(x) / sizeof((x)[0]))

struct measured_program {
	const char *program_name;
	const char *kernel_function;
	struct bpf_program *program;
	struct bpf_link *link;
	struct bpf_prog_info before;
};

static struct measured_program measured[] = {
	{
		.program_name = "vfs_read_entry",
		.kernel_function = "vfs_read",
	},
	{
		.program_name = "vfs_write_entry",
		.kernel_function = "vfs_write",
	},
};

static bool selected_program(const char *name)
{
	size_t i;

	for (i = 0; i < ARRAY_SIZE(measured); i++) {
		if (!strcmp(name, measured[i].program_name))
			return true;
	}
	return false;
}

static int read_prog_stats(struct bpf_program *program,
			   struct bpf_prog_info *info)
{
	__u32 info_len = sizeof(*info);

	memset(info, 0, sizeof(*info));
	return bpf_obj_get_info_by_fd(bpf_program__fd(program), info,
				      &info_len);
}

int main(int argc, char **argv)
{
	const char *object_path = argc > 1 ? argv[1] : "filetop.o";
	int seconds = argc > 2 ? atoi(argv[2]) : 60;
	int max_entries = argc > 3 ? atoi(argv[3]) : 256;
	struct bpf_object *object = NULL;
	struct bpf_program *program;
	struct bpf_map *entries;
	int error = 1;
	size_t i;

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

	bpf_object__for_each_program(program, object)
		bpf_program__set_autoload(
			program, selected_program(bpf_program__name(program)));

	entries = bpf_object__find_map_by_name(object, "entries");
	if (!entries) {
		fprintf(stderr, "entries map was not found in %s\n", object_path);
		goto cleanup;
	}
	if (bpf_map__set_max_entries(entries, max_entries)) {
		fprintf(stderr, "failed to set entries capacity to %d\n",
			max_entries);
		goto cleanup;
	}

	for (i = 0; i < ARRAY_SIZE(measured); i++) {
		measured[i].program = bpf_object__find_program_by_name(
			object, measured[i].program_name);
		if (!measured[i].program) {
			fprintf(stderr, "program %s was not found in %s\n",
				measured[i].program_name, object_path);
			goto cleanup;
		}
	}

	if (bpf_object__load(object)) {
		fprintf(stderr, "failed to load %s; run as root and check the "
			"BPF verifier log\n", object_path);
		goto cleanup;
	}

	for (i = 0; i < ARRAY_SIZE(measured); i++) {
		measured[i].link = bpf_program__attach_kprobe(
			measured[i].program, false, measured[i].kernel_function);
		if (libbpf_get_error(measured[i].link)) {
			int attach_error = libbpf_get_error(measured[i].link);

			measured[i].link = NULL;
			fprintf(stderr, "failed to attach %s to %s: %s\n",
				measured[i].program_name,
				measured[i].kernel_function,
				strerror(-attach_error));
			goto cleanup;
		}

		if (read_prog_stats(measured[i].program,
				    &measured[i].before)) {
			fprintf(stderr, "failed to read initial statistics for "
				"%s: %s\n", measured[i].program_name,
				strerror(errno));
			goto cleanup;
		}
	}

	printf("Loaded %s with entries.max_entries=%d for %d seconds.\n",
	       object_path, max_entries, seconds);
	printf("Generate regular-file reads and writes during this interval.\n\n");
	for (i = 0; i < ARRAY_SIZE(measured); i++)
		printf("  %-24s -> %-12s program ID %u\n",
		       measured[i].program_name, measured[i].kernel_function,
		       measured[i].before.id);
	fflush(stdout);

	sleep(seconds);

	printf("\n%-24s %15s %18s %14s\n",
	       "program", "run_cnt", "run_time_ns", "ns/run");
	for (i = 0; i < ARRAY_SIZE(measured); i++) {
		struct bpf_prog_info after;
		__u64 run_count;
		__u64 run_time;

		if (read_prog_stats(measured[i].program, &after)) {
			fprintf(stderr, "failed to read final statistics for "
				"%s: %s\n", measured[i].program_name,
				strerror(errno));
			goto cleanup;
		}

		run_count = after.run_cnt - measured[i].before.run_cnt;
		run_time = after.run_time_ns -
			   measured[i].before.run_time_ns;

		if (run_count)
			printf("%-24s %15llu %18llu %14.2f\n",
			       measured[i].program_name,
			       (unsigned long long)run_count,
			       (unsigned long long)run_time,
			       (double)run_time / (double)run_count);
		else
			printf("%-24s %15llu %18llu %14s\n",
			       measured[i].program_name,
			       (unsigned long long)run_count,
			       (unsigned long long)run_time, "n/a");
	}

	error = 0;

cleanup:
	for (i = 0; i < ARRAY_SIZE(measured); i++)
		bpf_link__destroy(measured[i].link);
	bpf_object__close(object);
	return error;
}
