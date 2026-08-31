#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <errno.h>
#include <linux/bpf.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

struct measured_program {
	const char *name;
	struct bpf_program *program;
	struct bpf_link *link;
	struct bpf_prog_info before;
	struct bpf_prog_info after;
};

static int read_stats(struct measured_program *measured,
		      struct bpf_prog_info *info)
{
	__u32 info_len = sizeof(*info);

	memset(info, 0, sizeof(*info));
	return bpf_obj_get_info_by_fd(bpf_program__fd(measured->program),
				      info, &info_len);
}

static int attach_program(struct bpf_object *object,
			  struct measured_program *measured)
{
	measured->program = bpf_object__find_program_by_name(
		object, measured->name);
	if (!measured->program) {
		fprintf(stderr, "program %s was not found\n", measured->name);
		return -1;
	}

	measured->link = bpf_program__attach(measured->program);
	if (libbpf_get_error(measured->link)) {
		measured->link = NULL;
		fprintf(stderr, "failed to attach %s: %s\n",
			measured->name, strerror(errno));
		return -1;
	}

	return 0;
}

static void print_result(const struct measured_program *measured)
{
	__u64 count = measured->after.run_cnt - measured->before.run_cnt;
	__u64 time = measured->after.run_time_ns -
		     measured->before.run_time_ns;

	printf("\nResults:\n");
	printf("%s\n", measured->name);
	printf("  program ID:        %u\n", measured->after.id);
	printf("  run_cnt delta:     %llu\n", (unsigned long long)count);
	printf("  run_time_ns delta: %llu\n", (unsigned long long)time);
	if (count)
		printf("  average execution: %.2f ns/run\n",
		       (double)time / (double)count);
	else
		printf("  average execution: unavailable (no events)\n");
}

int main(int argc, char **argv)
{
	struct measured_program measured = {
		.name = "block_rq_issue",
	};
	const char *object_path;
	struct bpf_object *object = NULL;
	int seconds;
	int error = 1;

	if (argc != 3) {
		fprintf(stderr, "usage: %s BITESIZE.o SECONDS\n", argv[0]);
		return 2;
	}

	object_path = argv[1];
	seconds = atoi(argv[2]);
	if (seconds <= 0) {
		fprintf(stderr, "duration must be positive\n");
		return 2;
	}

	libbpf_set_strict_mode(LIBBPF_STRICT_ALL);
	object = bpf_object__open_file(object_path, NULL);
	if (libbpf_get_error(object)) {
		object = NULL;
		fprintf(stderr, "failed to open %s: %s\n",
			object_path, strerror(errno));
		goto out;
	}

	if (bpf_object__load(object)) {
		fprintf(stderr, "failed to load %s\n", object_path);
		goto out;
	}

	if (attach_program(object, &measured))
		goto out;

	if (read_stats(&measured, &measured.before)) {
		fprintf(stderr, "failed to read initial stats for %s\n",
			measured.name);
		goto out;
	}

	printf("Attached %s for %d seconds.\n", object_path, seconds);
	printf("Generate the same direct-I/O workload in another terminal.\n");
	fflush(stdout);

	sleep(seconds);

	if (read_stats(&measured, &measured.after)) {
		fprintf(stderr, "failed to read final stats for %s\n",
			measured.name);
		goto out;
	}

	print_result(&measured);
	error = 0;
out:
	bpf_link__destroy(measured.link);
	bpf_object__close(object);
	return error;
}
