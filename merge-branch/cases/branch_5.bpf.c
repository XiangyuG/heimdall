// SPDX-License-Identifier: GPL-2.0
#include "vmlinux.h"
#include "maps.bpf.h"
#include <bpf/bpf_tracing.h>

static __always_inline
int trace_done(struct request *rq)
{
	volatile __u64 benchmark_duration = (__u64)(unsigned long)rq;

	if (((unsigned long)rq & (1UL << 0)) != 0)
		benchmark_duration += 1;
	if (((unsigned long)rq & (1UL << 1)) != 0)
		benchmark_duration += 2;
	if (((unsigned long)rq & (1UL << 2)) != 0)
		benchmark_duration += 4;
	if (((unsigned long)rq & (1UL << 3)) != 0)
		benchmark_duration += 8;
	if (((unsigned long)rq & (1UL << 4)) != 0)
		benchmark_duration += 16;

	return (int)benchmark_duration;
}

SEC("fentry/blk_account_io_done")
int BPF_PROG(blk_account_io_done, struct request *rq)
{
	return trace_done(rq);
}

char LICENSE[] SEC("license") = "GPL";
