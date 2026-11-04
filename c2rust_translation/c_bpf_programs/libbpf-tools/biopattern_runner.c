#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <errno.h>
#include <linux/bpf.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define PROGRAM_NAME "handle__block_rq_complete"

static int read_prog_stats(int fd, struct bpf_prog_info *info)
{
	__u32 info_len = sizeof(*info);

	memset(info, 0, sizeof(*info));
	return bpf_obj_get_info_by_fd(fd, info, &info_len);
}

static int compare_double(const void *a, const void *b)
{
	double x = *(const double *)a, y = *(const double *)b;

	return (x > y) - (x < y);
}

/* Summary of the per-second ns/run samples: the full-sample
 * median/min/max/mean/std, then mean/variance/std after dropping
 * floor(n * trim_pct / 100) samples from EACH end. */
static void print_sample_stats(double *v, int n, double trim_pct)
{
	int k, kept, i;
	double mean = 0, var = 0, tmean = 0, tvar = 0, median;

	if (!n) {
		printf("%-28s samples=0\n", PROGRAM_NAME);
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

	printf("%-28s samples=%d median=%.2f min=%.2f max=%.2f mean=%.2f "
	       "std=%.2f | trim=%g%% (%d each end, %d kept) "
	       "trimmed_mean=%.2f trimmed_var=%.2f trimmed_std=%.2f\n",
	       PROGRAM_NAME, n, median, v[0], v[n - 1], mean, sqrt(var),
	       trim_pct, k, kept, tmean, tvar, sqrt(tvar));
}

int main(int argc, char **argv)
{
	const char *object_path = argc > 1 ? argv[1] : "biopattern.o";
	int seconds = argc > 2 ? atoi(argv[2]) : 10;
	double trim_pct = argc > 3 ? atof(argv[3]) : 2.0;
	struct bpf_prog_info before = {}, prev, now, after = {};
	struct bpf_program *program;
	struct bpf_object *object = NULL;
	struct bpf_link *link = NULL;
	__u64 run_time_delta;
	__u64 run_count_delta;
	double *samples = NULL;
	int nsamples = 0;
	int program_fd;
	int error = 1;

	if (seconds <= 0) {
		fprintf(stderr, "duration must be a positive number of seconds\n");
		return 2;
	}
	if (trim_pct < 0 || trim_pct >= 50) {
		fprintf(stderr, "trim_pct must be in [0, 50)\n");
		return 2;
	}
	samples = calloc(seconds, sizeof(double));
	if (!samples) {
		fprintf(stderr, "out of memory\n");
		return 1;
	}

	libbpf_set_strict_mode(LIBBPF_STRICT_ALL);

	object = bpf_object__open_file(object_path, NULL);
	if (libbpf_get_error(object)) {
		fprintf(stderr, "failed to open %s: %s\n", object_path,
			strerror(errno));
		object = NULL;
		goto cleanup;
	}

	program = bpf_object__find_program_by_name(object, PROGRAM_NAME);
	if (!program) {
		fprintf(stderr, "program " PROGRAM_NAME " was not found\n");
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

	/* Sample the cumulative kernel stats once per second; each interval's
	 * delta run_time_ns / delta run_cnt is one ns/run sample. */
	prev = before;
	printf("\nper-second ns/run samples (second: program=ns/run(run_cnt) ...)\n");
	for (int t = 1; t <= seconds; t++) {
		__u64 dcnt, dtime;

		sleep(1);
		if (read_prog_stats(program_fd, &now)) {
			fprintf(stderr, "failed to read BPF statistics: %s\n",
				strerror(errno));
			goto cleanup;
		}
		dcnt = now.run_cnt - prev.run_cnt;
		dtime = now.run_time_ns - prev.run_time_ns;
		prev = now;
		if (dcnt) {
			double ns = (double)dtime / (double)dcnt;

			samples[nsamples++] = ns;
			printf("sample %3d:  %s=%.2f(%llu)\n", t, PROGRAM_NAME,
			       ns, (unsigned long long)dcnt);
		} else {
			printf("sample %3d:  %s=n/a(0)\n", t, PROGRAM_NAME);
		}
		fflush(stdout);
	}

	if (read_prog_stats(program_fd, &after)) {
		fprintf(stderr, "failed to read final BPF statistics: %s\n",
			strerror(errno));
		goto cleanup;
	}

	run_time_delta = after.run_time_ns - before.run_time_ns;
	run_count_delta = after.run_cnt - before.run_cnt;

	printf("\n%-28s %15s %18s %14s\n",
	       "program", "run_cnt", "run_time_ns", "ns/run");
	if (run_count_delta)
		printf("%-28s %15llu %18llu %14.2f\n", PROGRAM_NAME,
		       (unsigned long long)run_count_delta,
		       (unsigned long long)run_time_delta,
		       (double)run_time_delta / (double)run_count_delta);
	else
		printf("%-28s %15llu %18llu %14s\n", PROGRAM_NAME,
		       (unsigned long long)run_count_delta,
		       (unsigned long long)run_time_delta, "n/a");

	printf("\nper-second ns/run statistics\n");
	print_sample_stats(samples, nsamples, trim_pct);

	error = 0;

cleanup:
	bpf_link__destroy(link);
	bpf_object__close(object);
	free(samples);
	return error;
}
