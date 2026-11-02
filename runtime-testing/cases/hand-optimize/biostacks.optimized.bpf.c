// SPDX-License-Identifier: GPL-2.0
// Copyright (c) 2020 Wenbo Zhang
#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_core_read.h>
#include <bpf/bpf_tracing.h>
/* Inlined runtime-testing/include/bits.bpf.h for an independent case. */
/* SPDX-License-Identifier: (LGPL-2.1 OR BSD-2-Clause) */
#ifndef __BITS_BPF_H
#define __BITS_BPF_H

#define READ_ONCE(x) (*(volatile typeof(x) *)&(x))
#define WRITE_ONCE(x, val) ((*(volatile typeof(x) *)&(x)) = val)

/* Same floor(log2(v)) as the reference, including log2(0) == 0.
 * Carry bits replace comparisons; unsigned intermediates fit in 64 bits.
 * After each shift v fits in 32, 16, 8, 4, then 2 bits respectively. */
static __always_inline u64 log2l(u64 v)
{
    u64 shift = (((v >> 32) + 0xffffffffULL) >> 32) << 5;
    u64 r = shift;
    v >>= shift;
    shift = ((v + 0xffff0000ULL) >> 32) << 4;
    v >>= shift; r |= shift;
    shift = ((v + 0xffffff00ULL) >> 32) << 3;
    v >>= shift; r |= shift;
    shift = ((v + 0xfffffff0ULL) >> 32) << 2;
    v >>= shift; r |= shift;
    shift = ((v + 0xfffffffcULL) >> 32) << 1;
    v >>= shift; r |= shift;
    return r | (v >> 1);
}

static __always_inline u64 log2(u32 v)
{
    return log2l(v);
}

#endif /* __BITS_BPF_H */

#include "maps.bpf.h"
#include "core_fixes.bpf.h"

#define MAX_ENTRIES	10240

#define DISK_NAME_LEN	32
#define TASK_COMM_LEN	16
#define MAX_SLOTS	20
#define MAX_STACK	20

#define MINORBITS	20
#define MINORMASK	((1U << MINORBITS) - 1)

#define MKDEV(ma, mi)	(((ma) << MINORBITS) | (mi))

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

static __always_inline
int trace_start(void *ctx, struct request *rq, bool merge_bio)
{
	struct internal_rqinfo *i_rqinfop = NULL, i_rqinfo = {};
	struct gendisk *disk = get_disk(rq);
	u32 dev;

	dev = disk ? MKDEV(BPF_CORE_READ(disk, major),
			BPF_CORE_READ(disk, first_minor)) : 0;
	if (filter_dev && targ_dev != dev)
		return 0;

	if (merge_bio)
		i_rqinfop = bpf_map_lookup_elem(&rqinfos, &rq);
	if (!i_rqinfop)
		i_rqinfop = &i_rqinfo;

	i_rqinfop->start_ts = bpf_ktime_get_ns();
	i_rqinfop->rqinfo.pid = bpf_get_current_pid_tgid();
	i_rqinfop->rqinfo.kern_stack_size =
		bpf_get_stack(ctx, i_rqinfop->rqinfo.kern_stack,
			sizeof(i_rqinfop->rqinfo.kern_stack), 0);
	bpf_get_current_comm(&i_rqinfop->rqinfo.comm,
			sizeof(&i_rqinfop->rqinfo.comm));
	i_rqinfop->rqinfo.dev = dev;

	if (i_rqinfop == &i_rqinfo)
		bpf_map_update_elem(&rqinfos, &rq, i_rqinfop, 0);
	return 0;
}

static __always_inline
int trace_done(void *ctx, struct request *rq)
{
	u64 slot, ts = bpf_ktime_get_ns();
	struct internal_rqinfo *i_rqinfop;
	struct hist *histp;
	s64 delta;

	i_rqinfop = bpf_map_lookup_elem(&rqinfos, &rq);
	if (!i_rqinfop)
		return 0;
	delta = (s64)(ts - i_rqinfop->start_ts);
	if (delta < 0)
		goto cleanup;
	histp = bpf_map_lookup_or_try_init(&hists, &i_rqinfop->rqinfo, &zero);
	if (!histp)
		goto cleanup;
	if (targ_ms)
		delta /= 1000000U;
	else
		delta /= 1000U;
	slot = log2l(delta);
	if (slot >= MAX_SLOTS)
		slot = MAX_SLOTS - 1;
	__sync_fetch_and_add(&histp->slots[slot], 1);

cleanup:
	bpf_map_delete_elem(&rqinfos, &rq);
	return 0;
}

SEC("kprobe/blk_account_io_merge_bio")
int BPF_KPROBE(blk_account_io_merge_bio, struct request *rq)
{
	return trace_start(ctx, rq, true);
}

SEC("fentry/blk_account_io_start")
int BPF_PROG(blk_account_io_start, struct request *rq)
{
	return trace_start(ctx, rq, false);
}

SEC("fentry/blk_account_io_done")
int BPF_PROG(blk_account_io_done, struct request *rq)
{
	return trace_done(ctx, rq);
}

SEC("tp_btf/block_io_start")
int BPF_PROG(block_io_start, struct request *rq)
{
	return trace_start(ctx, rq, false);
}

SEC("tp_btf/block_io_done")
int BPF_PROG(block_io_done, struct request *rq)
{
	return trace_done(ctx, rq);
}

char LICENSE[] SEC("license") = "GPL";