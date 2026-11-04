// SPDX-License-Identifier: GPL-2.0
// Copyright (c) 2020 Wenbo Zhang
/*
 * Aggressively optimized biostacks. Program names are unchanged so
 * biostacks_runner can load it as-is. Differences from biostacks.bpf.c:
 *
 *  - the kernel stack is interned in a STACK_TRACE map and the hist key
 *    carries a 4-byte stack_id instead of a 160-byte stack + size. The hist
 *    key drops from 192 to 28 bytes and the per-request rqinfos value from
 *    200 to 40 bytes, so every hash, key compare and value copy is cheaper.
 *    Userspace must resolve stack_id through the stack_traces map.
 *  - hists is a PERCPU_HASH: the completion path bumps a CPU-local counter
 *    with a plain add instead of a locked __sync_fetch_and_add. Userspace
 *    must sum the per-CPU slots.
 *  - fentry / tp_btf programs read rq -> disk -> major/first_minor with
 *    direct BTF loads instead of bpf_probe_read_kernel helper calls; only the
 *    kprobe (merge_bio) keeps BPF_CORE_READ.
 */
#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_core_read.h>
#include <bpf/bpf_tracing.h>
#include "bits.bpf.h"
#include "maps.bpf.h"
#include "core_fixes.bpf.h"

#define MAX_ENTRIES	10240
#define STACK_ENTRIES	16384

#define DISK_NAME_LEN	32
#define TASK_COMM_LEN	16
#define MAX_SLOTS	20
#define MAX_STACK	20

/* biostacks.bpf.c passes sizeof(pointer) to bpf_get_current_comm(); keep the
 * same 8-byte comm so hist keys match the original. */
#define COMM_COPY_LEN	sizeof(void *)

#define MINORBITS	20
#define MINORMASK	((1U << MINORBITS) - 1)

#define MKDEV(ma, mi)	(((ma) << MINORBITS) | (mi))

struct rqinfo {
	__u32 pid;
	__s32 stack_id;
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
	__uint(type, BPF_MAP_TYPE_STACK_TRACE);
	__uint(max_entries, STACK_ENTRIES);
	__uint(key_size, sizeof(__u32));
	__uint(value_size, MAX_STACK * sizeof(__u64));
} stack_traces SEC(".maps");

struct {
	__uint(type, BPF_MAP_TYPE_PERCPU_HASH);
	__uint(max_entries, MAX_ENTRIES);
	__type(key, struct rqinfo);
	__type(value, struct hist);
} hists SEC(".maps");

static struct hist zero;

/* kprobe context: rq is a raw kernel pointer, go through probe reads */
static __always_inline __u32 rq_dev_probe(struct request *rq)
{
	struct gendisk *disk = get_disk(rq);

	return disk ? MKDEV(BPF_CORE_READ(disk, major),
			    BPF_CORE_READ(disk, first_minor)) : 0;
}

/* fentry / tp_btf context: rq is a BTF pointer, plain loads are allowed */
static __always_inline __u32 rq_dev_btf(struct request *rq)
{
	struct request___x *r = (void *)rq;
	struct gendisk *disk;

	if (bpf_core_field_exists(r->rq_disk))
		disk = r->rq_disk;
	else
		disk = r->q->disk;
	return disk ? MKDEV(disk->major, disk->first_minor) : 0;
}

static __always_inline
int trace_start(void *ctx, struct request *rq, __u32 dev, bool merge_bio)
{
	struct internal_rqinfo *i_rqinfop = NULL, i_rqinfo = {};

	if (filter_dev && targ_dev != dev)
		return 0;

	if (merge_bio)
		i_rqinfop = bpf_map_lookup_elem(&rqinfos, &rq);
	if (!i_rqinfop)
		i_rqinfop = &i_rqinfo;

	i_rqinfop->start_ts = bpf_ktime_get_ns();
	i_rqinfop->rqinfo.pid = bpf_get_current_pid_tgid();
	i_rqinfop->rqinfo.stack_id =
		bpf_get_stackid(ctx, &stack_traces, BPF_F_FAST_STACK_CMP);
	bpf_get_current_comm(&i_rqinfop->rqinfo.comm, COMM_COPY_LEN);
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
	histp->slots[slot]++;

cleanup:
	bpf_map_delete_elem(&rqinfos, &rq);
	return 0;
}

SEC("kprobe/blk_account_io_merge_bio")
int BPF_KPROBE(blk_account_io_merge_bio, struct request *rq)
{
	return trace_start(ctx, rq, rq_dev_probe(rq), true);
}

SEC("fentry/blk_account_io_start")
int BPF_PROG(blk_account_io_start, struct request *rq)
{
	return trace_start(ctx, rq, rq_dev_btf(rq), false);
}

SEC("fentry/blk_account_io_done")
int BPF_PROG(blk_account_io_done, struct request *rq)
{
	return trace_done(ctx, rq);
}

SEC("tp_btf/block_io_start")
int BPF_PROG(block_io_start, struct request *rq)
{
	return trace_start(ctx, rq, rq_dev_btf(rq), false);
}

SEC("tp_btf/block_io_done")
int BPF_PROG(block_io_done, struct request *rq)
{
	return trace_done(ctx, rq);
}

char LICENSE[] SEC("license") = "GPL";
