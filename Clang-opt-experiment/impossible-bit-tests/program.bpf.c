// SPDX-License-Identifier: GPL-2.0
#include "vmlinux.h"
#include <bpf/bpf_tracing.h>

SEC("fentry/blk_account_io_done")
int blk_account_io_done(struct request **ctx)
{
    struct request *rq = *ctx;
    __u64 bits = (__u64)(unsigned long)rq;
    __u64 value = bits;
    if ((bits & 1UL) == 2UL)
        value += 1;
    if ((bits & 2UL) == 4UL)
        value += 2;
    if ((bits & 4UL) == 8UL)
        value += 4;
    if ((bits & 8UL) == 16UL)
        value += 8;
    if ((bits & 16UL) == 32UL)
        value += 16;
    return (int)value;
}

char LICENSE[] SEC("license") = "GPL";
