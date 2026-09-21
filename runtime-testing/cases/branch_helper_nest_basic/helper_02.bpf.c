// SPDX-License-Identifier: GPL-2.0
// Copyright (c) 2020 Wenbo Zhang
#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>
#include "maps.bpf.h"






#define MAX_ENTRIES	10240
#define TASK_COMM_LEN	16
#define MAX_SLOTS	20
#define MAX_STACK	20


struct rqinfo {
	__u32 pid;
	int kern_stack_size;
	__u64 kern_stack[MAX_STACK];
	char comm[TASK_COMM_LEN];
	__u32 dev;
};

struct hist {
	__u32 slots[MAX_SLOTS];
};

struct internal_rqinfo {
	u64 start_ts;
	struct rqinfo rqinfo;
};

struct {
	__uint(type, BPF_MAP_TYPE_HASH);
	__uint(max_entries, MAX_ENTRIES);
	__type(key, struct rqinfo);
	__type(value, struct hist);
} hists SEC(".maps");

static struct hist zero;

int trace_done(void *ctx, struct request *rq)
{
	u64 duration = bpf_ktime_get_ns();
	struct internal_rqinfo *i_rqinfop;
	struct hist *histp;

	/* Volatile accesses preserve the requested benchmark structure at -O2. */
	volatile u64 benchmark_duration = duration;
	histp = bpf_map_lookup_or_try_init(&hists, &i_rqinfop->rqinfo, &zero);
	histp = bpf_map_lookup_or_try_init(&hists, &i_rqinfop->rqinfo, &zero);
	return benchmark_duration;
}

SEC("fentry/blk_account_io_done")
int BPF_PROG(blk_account_io_done, struct request *rq)
{
	return trace_done(ctx, rq);
}

char LICENSE[] SEC("license") = "GPL";
