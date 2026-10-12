// SPDX-License-Identifier: GPL-2.0
#include "vmlinux.h"
#include <bpf/bpf_tracing.h>

SEC("fentry/blk_account_io_done")
int BPF_PROG(blk_account_io_done, struct request *rq)
{
    long input = (long)(unsigned long)rq;
    long value = input;
    if (input < 8)
        value += 10;
    return (int)value;
}

char LICENSE[] SEC("license") = "GPL";
