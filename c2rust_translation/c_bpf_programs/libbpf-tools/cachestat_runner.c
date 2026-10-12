#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <errno.h>
#include <linux/bpf.h>
#include <math.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define ARRAY_SIZE(x) (sizeof(x) / sizeof((x)[0]))

struct measured_program {
	const char *name;
	struct bpf_program *program;
	struct bpf_link *link;
	struct bpf_prog_info before;
	struct bpf_prog_info prev;	/* stats at the start of the current 1s interval */
	double *samples;		/* per-second ns/run, intervals with run_cnt > 0 */
	int nsamples;
};

static struct measured_program measured[] = {
	{ .name = "fentry_add_to_page_cache_lru" },
	{ .name = "fentry_mark_page_accessed" },
	{ .name = "fentry_account_page_dirtied" },
	{ .name = "fentry_mark_buffer_dirty" },
};

static bool selected_program(const char *name)
{
	size_t i;

	for (i = 0; i < ARRAY_SIZE(measured); i++) {
		if (!strcmp(name, measured[i].name))
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

static int compare_double(const void *a, const void *b)
{
	double x = *(const double *)a, y = *(const double *)b;

	return (x > y) - (x < y);
}

/* Summary of one program's per-second ns/run samples: the full-sample
 * median/min/max/mean/std, then mean/variance/std after dropping
 * floor(n * trim_pct / 100) samples from EACH end. */
static void print_sample_stats(const struct measured_program *m,
			       double trim_pct)
{
	int n = m->nsamples, k, kept, i;
	double mean = 0, var = 0, tmean = 0, tvar = 0, median;
	double *v = m->samples;

	if (!n) {
		printf("%-38s samples=0\n", m->name);
		return;
	}
	qsort(v, n, sizeof(*v), compare_double);
	k = (int)(n * trim_pct / 100.0);
	if (n - 2 * k <= 0)
		k = 0;
	kept = n - 2 * k;

	for (i = 0; i < n; i++)
		mean += v[i];
	mean /= n;
	for (i = 0; i < n; i++)
		var += (v[i] - mean) * (v[i] - mean);
	var = n > 1 ? var / (n - 1) : 0;

	for (i = k; i < n - k; i++)
		tmean += v[i];
	tmean /= kept;
	for (i = k; i < n - k; i++)
		tvar += (v[i] - tmean) * (v[i] - tmean);
	tvar = kept > 1 ? tvar / (kept - 1) : 0;

	median = n % 2 ? v[n / 2] : (v[n / 2 - 1] + v[n / 2]) / 2;

	printf("%-38s samples=%d median=%.2f min=%.2f max=%.2f mean=%.2f "
	       "std=%.2f | trim=%g%% (%d each end, %d kept) "
	       "trimmed_mean=%.2f trimmed_var=%.2f trimmed_std=%.2f\n",
	       m->name, n, median, v[0], v[n - 1], mean, sqrt(var),
	       trim_pct, k, kept, tmean, tvar, sqrt(tvar));
}

static void cleanup_links(void)
{
	size_t i;

	for (i = 0; i < ARRAY_SIZE(measured); i++) {
		bpf_link__destroy(measured[i].link);
		measured[i].link = NULL;
		free(measured[i].samples);
		measured[i].samples = NULL;
	}
}

int main(int argc, char **argv)
{
	const char *object_path = argc > 1 ? argv[1] : "cachestat.o";
	int seconds = argc > 2 ? atoi(argv[2]) : 10;
	double trim_pct = argc > 3 ? atof(argv[3]) : 2.0;
	struct bpf_object *object = NULL;
	struct bpf_program *program;
	int error = 1;
	size_t i;

	if (seconds <= 0) {
		fprintf(stderr, "duration must be a positive number of seconds\n");
		return 2;
	}
	if (trim_pct < 0 || trim_pct >= 50) {
		fprintf(stderr, "trim_pct must be in [0, 50)\n");
		return 2;
	}
	for (i = 0; i < ARRAY_SIZE(measured); i++) {
		measured[i].samples = calloc(seconds, sizeof(double));
		if (!measured[i].samples) {
			fprintf(stderr, "out of memory\n");
			goto cleanup;
		}
	}

	libbpf_set_strict_mode(LIBBPF_STRICT_ALL);

	object = bpf_object__open_file(object_path, NULL);
	if (libbpf_get_error(object)) {
		fprintf(stderr, "failed to open %s: %s\n", object_path,
			strerror(errno));
		object = NULL;
		goto cleanup;
	}

	bpf_object__for_each_program(program, object)
		bpf_program__set_autoload(
			program, selected_program(bpf_program__name(program)));

	for (i = 0; i < ARRAY_SIZE(measured); i++) {
		measured[i].program =
			bpf_object__find_program_by_name(object, measured[i].name);
		if (!measured[i].program) {
			fprintf(stderr, "program %s was not found in %s\n",
				measured[i].name, object_path);
			goto cleanup;
		}
	}

	if (bpf_object__load(object)) {
		fprintf(stderr, "failed to load %s; check kernel support and "
			"run as root\n", object_path);
		goto cleanup;
	}

	for (i = 0; i < ARRAY_SIZE(measured); i++) {
		measured[i].link = bpf_program__attach(measured[i].program);
		if (libbpf_get_error(measured[i].link)) {
			int attach_error = libbpf_get_error(measured[i].link);

			measured[i].link = NULL;
			fprintf(stderr, "failed to attach %s: %s\n",
				measured[i].name, strerror(-attach_error));
			goto cleanup;
		}

		if (read_prog_stats(measured[i].program,
				    &measured[i].before)) {
			fprintf(stderr, "failed to read initial statistics for "
				"%s: %s\n", measured[i].name, strerror(errno));
			goto cleanup;
		}
	}

	printf("Loaded %s and attached four fentry programs for %d seconds.\n",
	       object_path, seconds);
	printf("BPF statistics require: sysctl kernel.bpf_stats_enabled=1\n");
	printf("Generate buffered file I/O during this interval.\n\n");
	for (i = 0; i < ARRAY_SIZE(measured); i++)
		printf("  %-38s program ID %u\n", measured[i].name,
		       measured[i].before.id);
	fflush(stdout);

	/* Sample the cumulative kernel stats once per second; each interval's
	 * delta run_time_ns / delta run_cnt is one ns/run sample. */
	for (i = 0; i < ARRAY_SIZE(measured); i++)
		measured[i].prev = measured[i].before;
	printf("\nper-second ns/run samples (second: program=ns/run(run_cnt) ...)\n");
	for (int t = 1; t <= seconds; t++) {
		sleep(1);
		printf("sample %3d:", t);
		for (i = 0; i < ARRAY_SIZE(measured); i++) {
			struct measured_program *m = &measured[i];
			struct bpf_prog_info now;
			__u64 dcnt, dtime;

			if (read_prog_stats(m->program, &now)) {
				fprintf(stderr, "failed to read statistics for "
					"%s: %s\n", m->name, strerror(errno));
				goto cleanup;
			}
			dcnt = now.run_cnt - m->prev.run_cnt;
			dtime = now.run_time_ns - m->prev.run_time_ns;
			m->prev = now;
			if (dcnt) {
				double ns = (double)dtime / (double)dcnt;

				m->samples[m->nsamples++] = ns;
				printf("  %s=%.2f(%llu)", m->name, ns,
				       (unsigned long long)dcnt);
			} else {
				printf("  %s=n/a(0)", m->name);
			}
		}
		printf("\n");
		fflush(stdout);
	}

	printf("\n%-38s %15s %18s %14s\n",
	       "program", "run_cnt", "run_time_ns", "ns/run");
	for (i = 0; i < ARRAY_SIZE(measured); i++) {
		struct bpf_prog_info after;
		__u64 run_count;
		__u64 run_time;

		if (read_prog_stats(measured[i].program, &after)) {
			fprintf(stderr, "failed to read final statistics for "
				"%s: %s\n", measured[i].name, strerror(errno));
			goto cleanup;
		}

		run_count = after.run_cnt - measured[i].before.run_cnt;
		run_time = after.run_time_ns -
			   measured[i].before.run_time_ns;

		if (run_count)
			printf("%-38s %15llu %18llu %14.2f\n",
			       measured[i].name,
			       (unsigned long long)run_count,
			       (unsigned long long)run_time,
			       (double)run_time / (double)run_count);
		else
			printf("%-38s %15llu %18llu %14s\n",
			       measured[i].name,
			       (unsigned long long)run_count,
			       (unsigned long long)run_time, "n/a");
	}

	printf("\nper-second ns/run statistics\n");
	for (i = 0; i < ARRAY_SIZE(measured); i++)
		print_sample_stats(&measured[i], trim_pct);

	error = 0;

cleanup:
	cleanup_links();
	bpf_object__close(object);
	return error;
}
