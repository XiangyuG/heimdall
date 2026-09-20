/*
 * Generic benchmark runner for any libbpf-tools BPF object whose programs
 * are attached with plain bpf_program__attach() (kprobe/kretprobe/
 * tracepoint/fentry/fexit/tp_btf/raw_tp -- no perf_event/uprobe/USDT setup).
 *
 * Unlike the per-tool *_runner.c files (cachestat_runner.c, filetop_runner.c,
 * ...), this doesn't read any tool-specific map contents. It only reads the
 * kernel's own per-program bpf_prog_info.run_cnt/run_time_ns counters before
 * and after a sleep -- which the kernel tracks for ANY loaded BPF program
 * regardless of what its body does internally -- so one binary covers every
 * tool in this attach-mechanism family instead of a bespoke runner each.
 *
 * A named program that fails to attach is logged and skipped rather than
 * aborting the whole run: several tools define a CO-RE fallback pair for the
 * same logic (e.g. a tp_btf/raw_tp pair gated on kernel BTF support), where
 * only one half is expected to actually attach on a given kernel.
 *
 * usage: generic_runner OBJ.o SECONDS PROG_NAME [PROG_NAME ...]
 */
#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <errno.h>
#include <linux/bpf.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define MAX_PROGRAMS 64

struct measured_program {
	const char *name;
	struct bpf_program *program;
	struct bpf_link *link;
	struct bpf_prog_info before;
	bool attached;
};

static struct measured_program measured[MAX_PROGRAMS];
static size_t n_measured;

static bool wanted_program(const char *name)
{
	size_t i;

	for (i = 0; i < n_measured; i++) {
		if (!strcmp(name, measured[i].name))
			return true;
	}
	return false;
}

static int read_prog_stats(struct bpf_program *program, struct bpf_prog_info *info)
{
	__u32 info_len = sizeof(*info);

	memset(info, 0, sizeof(*info));
	return bpf_obj_get_info_by_fd(bpf_program__fd(program), info, &info_len);
}

static void cleanup(void)
{
	size_t i;

	for (i = 0; i < n_measured; i++)
		bpf_link__destroy(measured[i].link);
}

int main(int argc, char **argv)
{
	const char *object_path;
	int seconds;
	struct bpf_object *object = NULL;
	struct bpf_program *program;
	int error = 1;
	size_t i;
	bool any_attached = false;

	if (argc < 4) {
		fprintf(stderr, "usage: %s OBJ.o SECONDS PROG_NAME [PROG_NAME ...]\n", argv[0]);
		return 2;
	}

	object_path = argv[1];
	seconds = atoi(argv[2]);
	if (seconds <= 0) {
		fprintf(stderr, "duration must be a positive number of seconds\n");
		return 2;
	}

	n_measured = (size_t)(argc - 3);
	if (n_measured > MAX_PROGRAMS) {
		fprintf(stderr, "too many programs (max %d)\n", MAX_PROGRAMS);
		return 2;
	}
	for (i = 0; i < n_measured; i++)
		measured[i].name = argv[3 + i];

	libbpf_set_strict_mode(LIBBPF_STRICT_ALL);

	object = bpf_object__open_file(object_path, NULL);
	if (libbpf_get_error(object)) {
		object = NULL;
		fprintf(stderr, "failed to open %s: %s\n", object_path, strerror(errno));
		goto out;
	}

	/* Only autoload the programs we were asked to measure -- everything
	 * else in the object (unrelated variants, etc.) stays unloaded. */
	bpf_object__for_each_program(program, object)
		bpf_program__set_autoload(program, wanted_program(bpf_program__name(program)));

	/* Several tools (offcputime, futexctn, klockstat, profile, ...) declare
	 * a BPF_MAP_TYPE_STACK_TRACE map with no value_size/max_entries in the
	 * source -- those are meant to be filled in by the loader at runtime
	 * (see how filetop_runner.c does the analogous bpf_map__set_max_entries
	 * for its own "entries" map), and creating the map with value_size 0
	 * fails with EINVAL. Fix up any such map generically here (127 frames
	 * is the kernel's own PERF_MAX_STACK_DEPTH default) rather than
	 * special-casing it per tool -- equivalence checking never reads this
	 * map's contents anyway (raw, environment-dependent stack IDs), so its
	 * exact sizing only matters for successfully loading the object. */
	{
		struct bpf_map *map;

		bpf_object__for_each_map(map, object) {
			if (bpf_map__type(map) != BPF_MAP_TYPE_STACK_TRACE)
				continue;
			if (bpf_map__value_size(map) == 0)
				bpf_map__set_value_size(map, 127 * sizeof(__u64));
			if (bpf_map__max_entries(map) == 0)
				bpf_map__set_max_entries(map, 10240);
		}
	}

	if (bpf_object__load(object)) {
		fprintf(stderr, "failed to load %s; check kernel support and run as root\n",
			object_path);
		goto out;
	}

	for (i = 0; i < n_measured; i++) {
		measured[i].program = bpf_object__find_program_by_name(object, measured[i].name);
		if (!measured[i].program) {
			fprintf(stderr, "warning: program %s was not found in %s, skipping\n",
				measured[i].name, object_path);
			continue;
		}

		measured[i].link = bpf_program__attach(measured[i].program);
		if (libbpf_get_error(measured[i].link)) {
			int attach_error = libbpf_get_error(measured[i].link);

			measured[i].link = NULL;
			fprintf(stderr, "warning: failed to attach %s: %s, skipping\n",
				measured[i].name, strerror(-attach_error));
			continue;
		}

		if (read_prog_stats(measured[i].program, &measured[i].before)) {
			fprintf(stderr, "warning: failed to read initial stats for %s: %s, skipping\n",
				measured[i].name, strerror(errno));
			bpf_link__destroy(measured[i].link);
			measured[i].link = NULL;
			continue;
		}

		measured[i].attached = true;
		any_attached = true;
	}

	if (!any_attached) {
		fprintf(stderr, "no requested program could be attached\n");
		goto out;
	}

	{
		size_t n_attached = 0;

		for (i = 0; i < n_measured; i++)
			if (measured[i].attached)
				n_attached++;
		printf("Attached %zu/%zu program(s) from %s for %d seconds.\n",
		       n_attached, n_measured, object_path, seconds);
	}
	for (i = 0; i < n_measured; i++)
		if (measured[i].attached)
			printf("  %-38s program ID %u\n", measured[i].name, measured[i].before.id);
	fflush(stdout);

	sleep(seconds);

	printf("\n%-38s %15s %18s %14s\n", "program", "run_cnt", "run_time_ns", "ns/run");
	for (i = 0; i < n_measured; i++) {
		struct bpf_prog_info after;
		__u64 run_count, run_time;

		if (!measured[i].attached) {
			printf("%-38s %15s %18s %14s\n", measured[i].name, "n/a", "n/a", "n/a");
			continue;
		}

		if (read_prog_stats(measured[i].program, &after)) {
			fprintf(stderr, "failed to read final stats for %s: %s\n",
				measured[i].name, strerror(errno));
			goto cleanup_and_out;
		}

		run_count = after.run_cnt - measured[i].before.run_cnt;
		run_time = after.run_time_ns - measured[i].before.run_time_ns;

		if (run_count)
			printf("%-38s %15llu %18llu %14.2f\n", measured[i].name,
			       (unsigned long long)run_count, (unsigned long long)run_time,
			       (double)run_time / (double)run_count);
		else
			printf("%-38s %15llu %18llu %14s\n", measured[i].name,
			       (unsigned long long)run_count, (unsigned long long)run_time, "n/a");
	}

	error = 0;

cleanup_and_out:
	cleanup();
out:
	bpf_object__close(object);
	return error;
}
