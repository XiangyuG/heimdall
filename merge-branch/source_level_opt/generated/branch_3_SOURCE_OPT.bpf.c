// SPDX-License-Identifier: GPL-2.0
#include "vmlinux.h"
#include "maps.bpf.h"
#include <bpf/bpf_tracing.h>





static __always_inline
int trace_done(struct request *rq)
{
	volatile __u64 benchmark_duration = (__u64)(unsigned long)rq;

	__u64 __vanilla_benchmark_duration_1_value_0 = benchmark_duration;
	int __vanilla_benchmark_duration_1_condition_1 = !!(((unsigned long)rq & (1UL << 0)) != 0);
	__u64 __vanilla_benchmark_duration_1_value_1 = __vanilla_benchmark_duration_1_condition_1 ? ((__vanilla_benchmark_duration_1_value_0) + (1)) : __vanilla_benchmark_duration_1_value_0;
	int __vanilla_benchmark_duration_1_condition_2 = !!(((unsigned long)rq & (1UL << 1)) != 0);
	__u64 __vanilla_benchmark_duration_1_value_2 = __vanilla_benchmark_duration_1_condition_2 ? ((__vanilla_benchmark_duration_1_value_1) + (2)) : __vanilla_benchmark_duration_1_value_1;
	int __vanilla_benchmark_duration_1_condition_3 = !!(((unsigned long)rq & (1UL << 2)) != 0);
	__u64 __vanilla_benchmark_duration_1_value_3 = __vanilla_benchmark_duration_1_condition_3 ? ((__vanilla_benchmark_duration_1_value_2) + (4)) : __vanilla_benchmark_duration_1_value_2;
	benchmark_duration = __vanilla_benchmark_duration_1_value_3;

	return (int)benchmark_duration;
}

SEC("fentry/blk_account_io_done")
int BPF_PROG(blk_account_io_done, struct request *rq)
{
	return trace_done(rq);
}

char LICENSE[] SEC("license") = "GPL";
