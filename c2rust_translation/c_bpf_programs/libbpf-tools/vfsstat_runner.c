#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

enum stat_type {
	S_READ,
	S_WRITE,
	S_FSYNC,
	S_OPEN,
	S_CREATE,
	S_UNLINK,
	S_MKDIR,
	S_RMDIR,
	S_MAXSTAT,
};

static const char *const stat_names[S_MAXSTAT] = {
	"read", "write", "fsync", "open",
	"create", "unlink", "mkdir", "rmdir",
};

static const char *const function_names[S_MAXSTAT] = {
	"vfs_read", "vfs_write", "vfs_fsync", "vfs_open",
	"vfs_create", "vfs_unlink", "vfs_mkdir", "vfs_rmdir",
};

static bool selected_program(const char *name)
{
	return !strncmp(name, "kprobe_vfs_", 11);
}

static void print_program_id(struct bpf_program *program)
{
	struct bpf_prog_info info = {};
	__u32 info_len = sizeof(info);

	if (bpf_obj_get_info_by_fd(bpf_program__fd(program), &info,
				   &info_len) == 0)
		printf("  %-20s BPF program ID %u\n",
		       bpf_program__name(program), info.id);
}

int main(int argc, char **argv)
{
	const char *object_path = argc > 1 ? argv[1] : "/tmp/vfsstat.bpf.o";
	int seconds = argc > 2 ? atoi(argv[2]) : 10;
	struct bpf_link *links[S_MAXSTAT] = {};
	struct bpf_object *object;
	struct bpf_program *program;
	struct bpf_map *bss;
	__u64 stats[S_MAXSTAT] = {};
	__u32 key = 0;
	int bss_fd;
	int error = 1;
	int i;

	if (seconds <= 0) {
		fprintf(stderr, "duration must be greater than zero\n");
		return 1;
	}

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

	for (i = 0; i < S_MAXSTAT; i++) {
		char program_name[32];

		snprintf(program_name, sizeof(program_name), "kprobe_%s",
			 function_names[i]);
		program = bpf_object__find_program_by_name(object, program_name);
		if (!program) {
			fprintf(stderr, "program %s was not found\n", program_name);
			goto cleanup;
		}

		links[i] = bpf_program__attach_kprobe(
			program, false, function_names[i]);
		if (libbpf_get_error(links[i])) {
			links[i] = NULL;
			fprintf(stderr, "failed to attach %s\n", function_names[i]);
			goto cleanup;
		}
	}

	bss = bpf_object__find_map_by_name(object, ".bss");
	if (!bss) {
		fprintf(stderr, ".bss map was not found\n");
		goto cleanup;
	}
	bss_fd = bpf_map__fd(bss);

	printf("Attached eight VFS kprobes; collecting for %d seconds.\n",
	       seconds);
	bpf_object__for_each_program(program, object) {
		if (bpf_program__autoload(program))
			print_program_id(program);
	}
	fflush(stdout);

	sleep(seconds);

	if (bpf_map_lookup_elem(bss_fd, &key, stats)) {
		fprintf(stderr, "failed to read the .bss statistics map\n");
		goto cleanup;
	}

	printf("\n%-10s %15s %15s\n", "operation", "calls", "calls/second");
	for (i = 0; i < S_MAXSTAT; i++)
		printf("%-10s %15llu %15.2f\n",
		       stat_names[i],
		       (unsigned long long)stats[i],
		       (double)stats[i] / seconds);

	error = 0;
cleanup:
	for (i = 0; i < S_MAXSTAT; i++)
		bpf_link__destroy(links[i]);
	bpf_object__close(object);
	return error;
}
