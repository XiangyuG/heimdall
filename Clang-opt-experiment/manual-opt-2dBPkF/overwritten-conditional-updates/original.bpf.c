// SPDX-License-Identifier: GPL-2.0
#include "vmlinux.h"
#include <bpf/bpf_tracing.h>

SEC("fentry/blk_account_io_done")
int BPF_PROG(blk_account_io_done, struct request *rq)
{
    __u64 bits = (__u64)(unsigned long)rq;
    __u64 value = 0;
    if (bits & 1UL)
        value = 1;
    if (bits & 2UL)
        value = 2;
    if (bits & 4UL)
        value = 3;
    if (bits & 8UL)
        value = 4;
    if (bits & 16UL)
        value = 5;
    value = bits + 7;
    return (int)value;
}

char LICENSE[] SEC("license") = "GPL";
