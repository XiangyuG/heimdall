#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

struct info_t {
	__u32 pid;
	int rwflag;
	int major;
	int minor;
	char name[16];
};

struct val_t {
	__u64 bytes;
	__u64 us;
	__u32 io;
};

static bool selected_program(const char *name)
{
	return !strcmp(name, "blk_mq_start_request") ||
	       !strcmp(name, "blk_account_io_start") ||
	       !strcmp(name, "blk_account_io_done");
}

static struct bpf_link *attach_kprobe(struct bpf_object *obj,
				     const char *program_name)
{
	struct bpf_program *program;
	struct bpf_link *link;

	program = bpf_object__find_program_by_name(obj, program_name);
	if (!program) {
		fprintf(stderr, "program %s was not found\n", program_name);
		return NULL;
	}

	link = bpf_program__attach_kprobe(program, false, program_name);
	if (libbpf_get_error(link)) {
		fprintf(stderr, "failed to attach kprobe %s\n", program_name);
		return NULL;
	}

	return link;
}

static void print_program_id(struct bpf_object *object, const char *name)
{
	struct bpf_program *program;
	struct bpf_prog_info info = {};
	__u32 info_len = sizeof(info);

	program = bpf_object__find_program_by_name(object, name);
	if (program &&
	    bpf_obj_get_info_by_fd(bpf_program__fd(program), &info, &info_len) == 0)
		printf("  %-24s BPF program ID %u\n", name, info.id);
}

int main(int argc, char **argv)
{
	const char *object_path = argc > 1 ? argv[1] : "/tmp/biotop.bpf.o";
	int seconds = argc > 2 ? atoi(argv[2]) : 10;
	struct bpf_link *timing_link = NULL;
	struct bpf_link *start_link = NULL;
	struct bpf_link *done_link = NULL;
	struct bpf_object *object;
	struct bpf_program *program;
	struct bpf_map *counts;
	struct info_t key = {}, next_key;
	struct val_t value;
	bool first = true;
	int counts_fd;
	int error = 1;

	libbpf_set_strict_mode(LIBBPF_STRICT_ALL);

	object = bpf_object__open_file(object_path, NULL);
	if (libbpf_get_error(object)) {
		fprintf(stderr, "failed to open %s\n", object_path);
		return 1;
	}

	bpf_object__for_each_program(program, object)
		bpf_program__set_autoload(
			program, selected_program(bpf_program__name(program)));

	if (bpf_object__load(object)) {
		fprintf(stderr, "failed to load BPF object\n");
		goto cleanup;
	}

	timing_link = attach_kprobe(object, "blk_mq_start_request");
	if (!timing_link)
		goto cleanup;

	start_link = attach_kprobe(object, "blk_account_io_start");
	if (!start_link)
		goto cleanup;

	done_link = attach_kprobe(object, "blk_account_io_done");
	if (!done_link)
		goto cleanup;

	counts = bpf_object__find_map_by_name(object, "counts");
	if (!counts) {
		fprintf(stderr, "counts map was not found\n");
		goto cleanup;
	}
	counts_fd = bpf_map__fd(counts);

	printf("Attached three kprobes; PID %d; collecting for %d seconds...\n",
	       getpid(), seconds);
	print_program_id(object, "blk_mq_start_request");
	print_program_id(object, "blk_account_io_start");
	print_program_id(object, "blk_account_io_done");
	fflush(stdout);
	sleep(seconds);

	while (bpf_map_get_next_key(counts_fd, first ? NULL : &key,
				    &next_key) == 0) {
		if (bpf_map_lookup_elem(counts_fd, &next_key, &value) == 0) {
			printf("%-16.16s pid=%-7u dev=%d:%d op=%s "
			       "io=%llu bytes=%llu latency_us=%llu\n",
			       next_key.name, next_key.pid,
			       next_key.major, next_key.minor,
			       next_key.rwflag ? "write" : "read",
			       (unsigned long long)value.io,
			       (unsigned long long)value.bytes,
			       (unsigned long long)value.us);
		}
		key = next_key;
		first = false;
	}

	error = 0;
cleanup:
	bpf_link__destroy(done_link);
	bpf_link__destroy(start_link);
	bpf_link__destroy(timing_link);
	bpf_object__close(object);
	return error;
}
