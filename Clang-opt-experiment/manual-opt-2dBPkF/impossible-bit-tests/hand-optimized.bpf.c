// SPDX-License-Identifier: GPL-2.0
#include "vmlinux.h"
#include <bpf/bpf_tracing.h>

SEC("fentry/blk_account_io_done")
int blk_account_io_done(struct request **ctx)
{
    struct request *rq = *ctx;
    __u64 bits = (__u64)(unsigned long)rq;
    return (int)bits;
}

char LICENSE[] SEC("license") = "GPL";
