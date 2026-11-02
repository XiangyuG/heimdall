// SPDX-License-Identifier: GPL-2.0
// Copyright (c) 2020 Wenbo Zhang
#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>
#include <bpf/bpf_core_read.h>
/* Inlined runtime-testing/include/bits.bpf.h, unchanged. */
/* SPDX-License-Identifier: (LGPL-2.1 OR BSD-2-Clause) */
#ifndef __BITS_BPF_H
#define __BITS_BPF_H

#define READ_ONCE(x) (*(volatile typeof(x) *)&(x))
#define WRITE_ONCE(x, val) ((*(volatile typeof(x) *)&(x)) = val)

static __always_inline u64 log2(u32 v)
{
	u32 shift, r;

	r = (v > 0xFFFF) << 4; v >>= r;
	shift = (v > 0xFF) << 3; v >>= shift; r |= shift;
	shift = (v > 0xF) << 2; v >>= shift; r |= shift;
	shift = (v > 0x3) << 1; v >>= shift; r |= shift;
	r |= (v >> 1);

	return r;
}

static __always_inline u64 log2l(u64 v)
{
	u32 hi = v >> 32;

	if (hi)
		return log2(hi) + 32;
	else
		return log2(v);
}

#endif /* __BITS_BPF_H */

#include "core_fixes.bpf.h"

#define TASK_COMM_LEN	16
#define DISK_NAME_LEN	32
#define MAX_SLOTS	20

#define MINORBITS	20
#define MINORMASK	((1U << MINORBITS) - 1)

#define MKDEV(ma, mi)	(((ma) << MINORBITS) | (mi))

struct hist_key {
	char comm[TASK_COMM_LEN];
};

struct hist {
	__u32 slots[MAX_SLOTS];
};

const volatile char targ_comm[TASK_COMM_LEN] = {};
const volatile bool filter_dev = false;
const volatile __u32 targ_dev = 0;

extern __u32 LINUX_KERNEL_VERSION __kconfig;

struct {
	__uint(type, BPF_MAP_TYPE_HASH);
	__uint(max_entries, 10240);
	__type(key, struct hist_key);
	__type(value, struct hist);
} hists SEC(".maps");

static struct hist initial_hist;

static __always_inline bool comm_allowed(const char *comm)
{
	int i;

	for (i = 0; i < TASK_COMM_LEN && targ_comm[i] != '\0'; i++) {
		if (comm[i] != targ_comm[i])
			return false;
	}
	return true;
}

static int trace_rq_issue(struct request *rq)
{
	struct hist_key hkey;
	struct hist *histp;
	u64 slot;

	if (filter_dev) {
		struct gendisk *disk = get_disk(rq);
		u32 dev;

		dev = disk ? MKDEV(BPF_CORE_READ(disk, major),
				BPF_CORE_READ(disk, first_minor)) : 0;
		if (targ_dev != dev)
			return 0;
	}
	bpf_get_current_comm(&hkey.comm, sizeof(hkey.comm));
	if (!comm_allowed(hkey.comm))
		return 0;

	histp = bpf_map_lookup_elem(&hists, &hkey);
	if (!histp) {
		bpf_map_update_elem(&hists, &hkey, &initial_hist, 0);
		histp = bpf_map_lookup_elem(&hists, &hkey);
		if (!histp)
			return 0;
	}
	slot = log2l(rq->__data_len / 1024);
	if (slot >= MAX_SLOTS)
		slot = MAX_SLOTS - 1;
	__sync_fetch_and_add(&histp->slots[slot], 1);

	return 0;
}

SEC("tp_btf/block_rq_issue")
int BPF_PROG(block_rq_issue)
{
	/**
	 * commit a54895fa (block: remove the request_queue to argument
	 * request based tracepoints) changed tracepoint argument list
	 * from TP_PROTO(struct request_queue *q, struct request *rq)
	 * to TP_PROTO(struct request *rq)
	 * see:
	 *     https://github.com/torvalds/linux/commit/a54895fa
	 */
	if (LINUX_KERNEL_VERSION >= KERNEL_VERSION(5, 10, 137))
		return trace_rq_issue((void *)ctx[0]);
	else
		return trace_rq_issue((void *)ctx[1]);
}

char LICENSE[] SEC("license") = "GPL";