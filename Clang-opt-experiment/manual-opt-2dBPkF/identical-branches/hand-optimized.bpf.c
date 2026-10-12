// SPDX-License-Identifier: GPL-2.0
#include "vmlinux.h"
#include <bpf/bpf_tracing.h>

SEC("fentry/blk_account_io_done")
int BPF_PROG(blk_account_io_done, struct request *rq)
{
    __u64 bits = (__u64)(unsigned long)rq;
    return (int)(bits + 15UL);
}

char LICENSE[] SEC("license") = "GPL";
