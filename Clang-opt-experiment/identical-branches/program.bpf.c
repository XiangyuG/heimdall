// SPDX-License-Identifier: GPL-2.0
#include "vmlinux.h"
#include <bpf/bpf_tracing.h>

SEC("fentry/blk_account_io_done")
int BPF_PROG(blk_account_io_done, struct request *rq)
{
    __u64 value = (__u64)(unsigned long)rq;
    if (((unsigned long)rq & 1UL) != 0)
        value += 3;
    else
        value += 3;
    if (((unsigned long)rq & 2UL) != 0)
        value += 3;
    else
        value += 3;
    if (((unsigned long)rq & 4UL) != 0)
        value += 3;
    else
        value += 3;
    if (((unsigned long)rq & 8UL) != 0)
        value += 3;
    else
        value += 3;
    if (((unsigned long)rq & 16UL) != 0)
        value += 3;
    else
        value += 3;
    return (int)value;
}

char LICENSE[] SEC("license") = "GPL";
