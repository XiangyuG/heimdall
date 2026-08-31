// SPDX-License-Identifier: GPL-2.0
// Copyright (c) 2020 Wenbo Zhang

#include "vmlinux.h"

#include <bpf/bpf_helpers.h>
#include <bpf/bpf_core_read.h>
#include <bpf/bpf_tracing.h>

#include "bits.bpf.h"
#include "maps.bpf.h"
#include "core_fixes.bpf.h"

#define MAX_ENTRIES        10240

#define DISK_NAME_LEN      32
#define TASK_COMM_LEN      16

#define MAX_SLOTS          20
#define MAX_STACK          20

#define STACK_STORAGE_SIZE 16384

#define MINORBITS          20
#define MINORMASK          ((1U << MINORBITS) - 1)

#define MKDEV(ma, mi)      (((ma) << MINORBITS) | (mi))

struct rqinfo_key {
	__u32 pid;
	__u32 dev;
	__s32 stack_id;
	char comm[TASK_COMM_LEN];
};

struct internal_rqinfo {
	__u64 start_ts;
	struct rqinfo_key key;
};

struct hist {
	__u32 slots[MAX_SLOTS];
};

const volatile bool targ_ms = false;
const volatile bool filter_dev = false;
const volatile __u32 targ_dev = -1;

/*
 * request -> start timestamp
 */
struct {
	__uint(type, BPF_MAP_TYPE_HASH);
	__uint(max_entries, MAX_ENTRIES);
	__type(key, struct request *);
	__type(value, struct internal_rqinfo);
} rqinfos SEC(".maps");

/*
 * stack storage
 */
struct {
	__uint(type, BPF_MAP_TYPE_STACK_TRACE);
	__uint(key_size, sizeof(__u32));
	__uint(value_size, MAX_STACK * sizeof(__u64));
	__uint(max_entries, STACK_STORAGE_SIZE);
} stack_traces SEC(".maps");

/*
 * histogram
 *
 * Use PERCPU_HASH to avoid atomic contention.
 */
struct {
	__uint(type, BPF_MAP_TYPE_PERCPU_HASH);
	__uint(max_entries, MAX_ENTRIES);
	__type(key, struct rqinfo_key);
	__type(value, struct hist);
} hists SEC(".maps");

static struct hist zero = {};

static __always_inline
int trace_start(void *ctx, struct request *rq, bool merge_bio)
{
	struct internal_rqinfo local = {};
	struct internal_rqinfo *info = NULL;

	struct gendisk *disk;
	__u32 dev = 0;

	disk = get_disk(rq);

	if (disk) {
		dev = MKDEV(
			BPF_CORE_READ(disk, major),
			BPF_CORE_READ(disk, first_minor));
	}

	if (filter_dev && targ_dev != dev)
		return 0;

	if (merge_bio)
		info = bpf_map_lookup_elem(&rqinfos, &rq);

	if (!info)
		info = &local;

	info->start_ts = bpf_ktime_get_ns();

	/*
	 * pid
	 */
	info->key.pid =
		(__u32)(bpf_get_current_pid_tgid() >> 32);

	info->key.dev = dev;

	bpf_get_current_comm(
		info->key.comm,
		sizeof(info->key.comm));

	/*
	 * save stack into stack_traces map
	 */
	info->key.stack_id =
		bpf_get_stackid(
			ctx,
			&stack_traces,
			BPF_F_FAST_STACK_CMP);

	if (info == &local) {
		bpf_map_update_elem(
			&rqinfos,
			&rq,
			info,
			BPF_ANY);
	}

	return 0;
}

static __always_inline
int trace_done(void *ctx, struct request *rq)
{
	struct internal_rqinfo *info;
	struct hist *histp;

	__u64 ts;
	__s64 delta;
	__u64 slot;

	ts = bpf_ktime_get_ns();

	info = bpf_map_lookup_elem(&rqinfos, &rq);

	if (!info)
		return 0;

	delta = (__s64)(ts - info->start_ts);

	if (delta < 0)
		goto cleanup;

	histp = bpf_map_lookup_or_try_init(
		&hists,
		&info->key,
		&zero);

	if (!histp)
		goto cleanup;

	if (targ_ms)
		delta /= 1000000ULL;
	else
		delta /= 1000ULL;

	if (delta == 0)
		slot = 0;
	else
		slot = log2l(delta);

	if (slot >= MAX_SLOTS)
		slot = MAX_SLOTS - 1;

	/*
	 * PERCPU_HASH:
	 * no atomic needed
	 */
	histp->slots[slot]++;

cleanup:
	bpf_map_delete_elem(&rqinfos, &rq);

	return 0;
}

/*
 * merge bio
 */
SEC("kprobe/blk_account_io_merge_bio")
int BPF_KPROBE(blk_account_io_merge_bio,
	       struct request *rq)
{
	return trace_start(ctx, rq, true);
}

/*
 * kernels supporting fentry
 */
SEC("fentry/blk_account_io_start")
int BPF_PROG(blk_account_io_start,
	     struct request *rq)
{
	return trace_start(ctx, rq, false);
}

SEC("fentry/blk_account_io_done")
int BPF_PROG(blk_account_io_done,
	     struct request *rq)
{
	return trace_done(ctx, rq);
}

/*
 * kernels supporting BTF tracepoints
 */
SEC("tp_btf/block_io_start")
int BPF_PROG(block_io_start,
	     struct request *rq)
{
	return trace_start(ctx, rq, false);
}

SEC("tp_btf/block_io_done")
int BPF_PROG(block_io_done,
	     struct request *rq)
{
	return trace_done(ctx, rq);
}

char LICENSE[] SEC("license") = "GPL";