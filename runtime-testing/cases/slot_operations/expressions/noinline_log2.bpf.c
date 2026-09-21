// SPDX-License-Identifier: GPL-2.0
// Copyright (c) 2020 Wenbo Zhang
#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_core_read.h>
#include <bpf/bpf_tracing.h>
#include "bits.bpf.h"
#include "maps.bpf.h"
#include "core_fixes.bpf.h"





#define MAX_ENTRIES 10240

#define DISK_NAME_LEN 32
#define TASK_COMM_LEN 16
#define MAX_SLOTS 20
#define MAX_STACK 20

#define MINORBITS 20
#define MINORMASK ((1U << MINORBITS) - 1)

#define MKDEV(ma, mi) (((ma) << MINORBITS) | (mi))

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

const volatile bool targ_ms = false;
const volatile bool filter_dev = false;
const volatile __u32 targ_dev = -1;

struct internal_rqinfo {
	u64 start_ts;
	struct rqinfo rqinfo;
};

struct {
	__uint(type, BPF_MAP_TYPE_HASH);
	__uint(max_entries, MAX_ENTRIES);
	__type(key, struct request *);
	__type(value, struct internal_rqinfo);
} rqinfos SEC(".maps");

struct {
	__uint(type, BPF_MAP_TYPE_HASH);
	__uint(max_entries, MAX_ENTRIES);
	__type(key, struct rqinfo);
	__type(value, struct hist);
} hists SEC(".maps");

static struct hist zero;

static __noinline u64 calculate_slot(u64 duration)
{
	return log2l(duration);
}


static __always_inline
int trace_done(void *ctx, struct request *rq)
{
	u64 duration, slot, ts = bpf_ktime_get_ns();
	struct internal_rqinfo *i_rqinfop;
	struct hist *histp;
	s64 delta;

	i_rqinfop = bpf_map_lookup_elem(&rqinfos, &rq);
	if (!i_rqinfop)
		return 0;
	delta = (s64)(ts - i_rqinfop->start_ts);
	if (delta < 0)
		goto cleanup;
	duration = (u64)delta;

	histp = bpf_map_lookup_or_try_init(&hists, &i_rqinfop->rqinfo, &zero);
	if (!histp)
		goto cleanup;
	if (targ_ms)
		duration /= 1000000U;
	else
		duration /= 1000U;

	slot = calculate_slot(duration);

	__sync_fetch_and_add(&histp->slots[slot], 1);

cleanup:
	bpf_map_delete_elem(&rqinfos, &rq);
	return 0;
}

SEC("fentry/blk_account_io_done")
int BPF_PROG(blk_account_io_done, struct request *rq)
{
	return trace_done(ctx, rq);
}

char LICENSE[] SEC("license") = "GPL";
