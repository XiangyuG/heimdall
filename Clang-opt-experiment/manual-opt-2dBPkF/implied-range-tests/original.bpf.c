// SPDX-License-Identifier: GPL-2.0
#include "vmlinux.h"
#include <bpf/bpf_tracing.h>

SEC("fentry/blk_account_io_done")
int BPF_PROG(blk_account_io_done, struct request *rq)
{
    long input = (long)(unsigned long)rq;
    long value = input;
    if (input < 8) {
        if (input < 16)
            value += 1;
        if (input < 32)
            value += 2;
        if (input < 64)
            value += 3;
        if (input < 128)
            value += 4;
    }
    return (int)value;
}

char LICENSE[] SEC("license") = "GPL";
