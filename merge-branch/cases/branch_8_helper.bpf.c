// SPDX-License-Identifier: GPL-2.0
#include "vmlinux.h"
#include "maps.bpf.h"
#include <bpf/bpf_tracing.h>

static __always_inline void
add_duration(volatile __u64 *duration, __u64 amount)
{
	*duration += amount;
}

static __always_inline
int trace_done(struct request *rq)
{
	volatile __u64 benchmark_duration = (__u64)(unsigned long)rq;

	(((unsigned long)rq & (1UL << 0)) != 0)
		? add_duration(&benchmark_duration, 1) : (void)0;
	(((unsigned long)rq & (1UL << 1)) != 0)
		? add_duration(&benchmark_duration, 2) : (void)0;
	(((unsigned long)rq & (1UL << 2)) != 0)
		? add_duration(&benchmark_duration, 4) : (void)0;
	(((unsigned long)rq & (1UL << 3)) != 0)
		? add_duration(&benchmark_duration, 8) : (void)0;
	(((unsigned long)rq & (1UL << 4)) != 0)
		? add_duration(&benchmark_duration, 16) : (void)0;
	(((unsigned long)rq & (1UL << 5)) != 0)
		? add_duration(&benchmark_duration, 32) : (void)0;
	(((unsigned long)rq & (1UL << 6)) != 0)
		? add_duration(&benchmark_duration, 64) : (void)0;
	(((unsigned long)rq & (1UL << 7)) != 0)
		? add_duration(&benchmark_duration, 128) : (void)0;

	return (int)benchmark_duration;
}

SEC("fentry/blk_account_io_done")
int BPF_PROG(blk_account_io_done, struct request *rq)
{
	return trace_done(rq);
}

char LICENSE[] SEC("license") = "GPL";
