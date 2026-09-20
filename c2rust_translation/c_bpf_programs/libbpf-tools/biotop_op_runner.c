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

int main(int argc, char **argv)
{
	const char *obj_path = argc > 1 ? argv[1] : "/tmp/biotop_op.bpf.o";
	int seconds = argc > 2 ? atoi(argv[2]) : 10;
	struct bpf_link *start_link = NULL, *done_link = NULL;
	struct bpf_object *obj;
	struct bpf_program *prog;
	struct bpf_map *counts;
	struct info_t key = {}, next_key;
	struct val_t *values = NULL;
	bool first = true;
	int counts_fd, ncpu, err = 1;

	libbpf_set_strict_mode(LIBBPF_STRICT_ALL);

	obj = bpf_object__open_file(obj_path, NULL);
	if (libbpf_get_error(obj)) {
		fprintf(stderr, "failed to open %s\n", obj_path);
		return 1;
	}

	bpf_object__for_each_program(prog, obj) {
		const char *name = bpf_program__name(prog);
		bool selected = !strcmp(name, "blk_account_io_start") ||
				!strcmp(name, "blk_account_io_done");

		bpf_program__set_autoload(prog, selected);
	}

	if (bpf_object__load(obj)) {
		fprintf(stderr, "failed to load BPF object\n");
		goto out;
	}

	prog = bpf_object__find_program_by_name(obj, "blk_account_io_start");
	start_link = bpf_program__attach_kprobe(prog, false,
					       "blk_account_io_start");
	if (libbpf_get_error(start_link)) {
		start_link = NULL;
		fprintf(stderr, "failed to attach blk_account_io_start\n");
		goto out;
	}

	prog = bpf_object__find_program_by_name(obj, "blk_account_io_done");
	done_link = bpf_program__attach_kprobe(prog, false,
					      "blk_account_io_done");
	if (libbpf_get_error(done_link)) {
		done_link = NULL;
		fprintf(stderr, "failed to attach blk_account_io_done\n");
		goto out;
	}

	counts = bpf_object__find_map_by_name(obj, "counts");
	counts_fd = bpf_map__fd(counts);
	ncpu = libbpf_num_possible_cpus();
	values = calloc(ncpu, sizeof(*values));
	if (!values)
		goto out;

	printf("Attached kprobes; collecting for %d seconds...\n", seconds);
	sleep(seconds);

	while (bpf_map_get_next_key(counts_fd, first ? NULL : &key,
				    &next_key) == 0) {
		__u64 bytes = 0, us = 0, io = 0;
		int cpu;

		if (bpf_map_lookup_elem(counts_fd, &next_key, values) == 0) {
			for (cpu = 0; cpu < ncpu; cpu++) {
				bytes += values[cpu].bytes;
				us += values[cpu].us;
				io += values[cpu].io;
			}

			printf("%-16.16s pid=%-7u dev=%d:%d op=%s "
			       "io=%llu bytes=%llu latency_us=%llu\n",
			       next_key.name, next_key.pid,
			       next_key.major, next_key.minor,
			       next_key.rwflag ? "write" : "read",
			       (unsigned long long)io,
			       (unsigned long long)bytes,
			       (unsigned long long)us);
		}

		key = next_key;
		first = false;
	}

	err = 0;
out:
	free(values);
	bpf_link__destroy(done_link);
	bpf_link__destroy(start_link);
	bpf_object__close(obj);
	return err;
}
