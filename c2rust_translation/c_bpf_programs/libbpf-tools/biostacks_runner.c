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

static bool selected_program(const char *name)
{
	return !strcmp(name, "blk_account_io_merge_bio") ||
	       !strcmp(name, "blk_account_io_start") ||
	       !strcmp(name, "blk_account_io_done");
}

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
	struct measured_program measured[] = {
		{ .name = "blk_account_io_merge_bio" },
		{ .name = "blk_account_io_start" },
		{ .name = "blk_account_io_done" },
	};
	const char *object_path;
	struct bpf_program *program;
	struct bpf_object *object = NULL;
	int seconds;
	int error = 1;
	size_t i;

	if (argc != 3) {
		fprintf(stderr, "usage: %s BIOSTACKS.o SECONDS\n", argv[0]);
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

	/*
	 * fentry and tp_btf are alternative start/done hook pairs. Loading both
	 * would update the same maps twice for each request.
	 */
	bpf_object__for_each_program(program, object)
		bpf_program__set_autoload(
			program, selected_program(bpf_program__name(program)));

	if (bpf_object__load(object)) {
		fprintf(stderr, "failed to load %s\n", object_path);
		goto out;
	}

	for (i = 0; i < sizeof(measured) / sizeof(measured[0]); i++) {
		if (attach_program(object, &measured[i]))
			goto out;
	}

	for (i = 0; i < sizeof(measured) / sizeof(measured[0]); i++) {
		if (read_stats(&measured[i], &measured[i].before)) {
			fprintf(stderr, "failed to read initial stats for %s\n",
				measured[i].name);
			goto out;
		}
	}

	printf("Attached %s for %d seconds using kprobe + fentry hooks.\n",
	       object_path, seconds);
	printf("Generate the same direct-I/O workload in another terminal.\n");
	printf("Example:\n"
	       "  fio --name=biostacks --filename=/tmp/biostacks.data "
	       "--size=1G --rw=randread --direct=1 --runtime=%d "
	       "--time_based --ioengine=libaio --iodepth=32 --bs=4k\n",
	       seconds > 5 ? seconds - 5 : seconds);
	fflush(stdout);

	sleep(seconds);

	for (i = 0; i < sizeof(measured) / sizeof(measured[0]); i++) {
		if (read_stats(&measured[i], &measured[i].after)) {
			fprintf(stderr, "failed to read final stats for %s\n",
				measured[i].name);
			goto out;
		}
	}

	printf("\nResults:\n");
	for (i = 0; i < sizeof(measured) / sizeof(measured[0]); i++)
		print_result(&measured[i]);

	error = 0;
out:
	for (i = 0; i < sizeof(measured) / sizeof(measured[0]); i++)
		bpf_link__destroy(measured[i].link);
	bpf_object__close(object);
	return error;
}
