#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <errno.h>
#include <linux/bpf.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static int read_prog_stats(int fd, struct bpf_prog_info *info)
{
	__u32 info_len = sizeof(*info);

	memset(info, 0, sizeof(*info));
	return bpf_obj_get_info_by_fd(fd, info, &info_len);
}

int main(int argc, char **argv)
{
	const char *object_path = argc > 1 ? argv[1] : "biopattern.o";
	int seconds = argc > 2 ? atoi(argv[2]) : 10;
	struct bpf_prog_info before = {}, after = {};
	struct bpf_program *program;
	struct bpf_object *object = NULL;
	struct bpf_link *link = NULL;
	__u64 run_time_delta;
	__u64 run_count_delta;
	int program_fd;
	int error = 1;

	if (seconds <= 0) {
		fprintf(stderr, "duration must be a positive number of seconds\n");
		return 2;
	}

	libbpf_set_strict_mode(LIBBPF_STRICT_ALL);

	object = bpf_object__open_file(object_path, NULL);
	if (libbpf_get_error(object)) {
		fprintf(stderr, "failed to open %s: %s\n", object_path,
			strerror(errno));
		return 1;
	}

	program = bpf_object__find_program_by_name(
		object, "handle__block_rq_complete");
	if (!program) {
		fprintf(stderr, "program handle__block_rq_complete was not found\n");
		goto cleanup;
	}

	if (bpf_object__load(object)) {
		fprintf(stderr, "failed to load %s\n", object_path);
		goto cleanup;
	}

	link = bpf_program__attach_tracepoint(program, "block",
					      "block_rq_complete");
	if (libbpf_get_error(link)) {
		link = NULL;
		fprintf(stderr, "failed to attach block:block_rq_complete\n");
		goto cleanup;
	}

	program_fd = bpf_program__fd(program);
	if (read_prog_stats(program_fd, &before)) {
		fprintf(stderr, "failed to read initial BPF statistics: %s\n",
			strerror(errno));
		goto cleanup;
	}

	printf("Attached BPF program ID %u for %d seconds.\n",
	       before.id, seconds);
	printf("Generate block I/O now, for example:\n"
	       "  fio --name=biopattern --filename=/tmp/biopattern.data "
	       "--size=256M --rw=randread --direct=1 --runtime=%d "
	       "--time_based --ioengine=sync --bs=4k\n",
	       seconds);
	fflush(stdout);

	sleep(seconds);

	if (read_prog_stats(program_fd, &after)) {
		fprintf(stderr, "failed to read final BPF statistics: %s\n",
			strerror(errno));
		goto cleanup;
	}

	run_time_delta = after.run_time_ns - before.run_time_ns;
	run_count_delta = after.run_cnt - before.run_cnt;

	printf("\nrun_cnt delta:     %llu\n",
	       (unsigned long long)run_count_delta);
	printf("run_time_ns delta: %llu\n",
	       (unsigned long long)run_time_delta);
	if (run_count_delta) {
		printf("average execution: %.2f ns/run\n",
		       (double)run_time_delta / (double)run_count_delta);
	} else {
		printf("average execution: unavailable (no block completions)\n");
	}

	error = 0;

cleanup:
	bpf_link__destroy(link);
	bpf_object__close(object);
	return error;
}
