// SPDX-License-Identifier: GPL-2.0
#include "vmlinux.h"
#include <bpf/bpf_tracing.h>

static __always_inline int trace_done(struct request *rq)
{
    volatile __u64 benchmark_duration = (__u64)(unsigned long)rq;
    __u64 value = benchmark_duration;
    value = ((unsigned long)rq & 1UL) ? value + 1 : value;
    value = ((unsigned long)rq & 2UL) ? value + 2 : value;
    value = ((unsigned long)rq & 4UL) ? value + 4 : value;
    value = ((unsigned long)rq & 8UL) ? value + 8 : value;
    value = ((unsigned long)rq & 16UL) ? value + 16 : value;
    benchmark_duration = value;
    return (int)benchmark_duration;
}

SEC("fentry/blk_account_io_done")
int BPF_PROG(blk_account_io_done, struct request *rq)
{
    return trace_done(rq);
}

char LICENSE[] SEC("license") = "GPL";
