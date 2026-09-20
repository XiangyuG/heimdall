// SPDX-License-Identifier: GPL-2.0
// Copyright (c) 2020 Wenbo Zhang

#include "vmlinux.h"

#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>
#include <bpf/bpf_core_read.h>

#include "bits.bpf.h"
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
	__uint(type, BPF_MAP_TYPE_PERCPU_HASH);
	__uint(max_entries, 10240);
	__type(key, struct hist_key);
	__type(value, struct hist);
} hists SEC(".maps");

static struct hist zero = {};

static __always_inline bool comm_allowed(const char *comm)
{
	int i;

#pragma unroll
	for (i = 0; i < TASK_COMM_LEN; i++) {
		if (targ_comm[i] == '\0')
			return true;
		if (comm[i] != targ_comm[i])
			return false;
	}

	return true;
}

static __always_inline int trace_rq_issue(struct request *rq)
{
	struct hist_key hkey = {};
	struct hist *histp;
	struct gendisk *disk;
	__u32 dev = 0;
	__u32 data_len;
	__u64 slot;

	if (filter_dev) {
		disk = get_disk(rq);

		if (disk) {
			dev = MKDEV(
				BPF_CORE_READ(disk, major),
				BPF_CORE_READ(disk, first_minor));
		}

		if (targ_dev != dev)
			return 0;
	}

	bpf_get_current_comm(&hkey.comm, sizeof(hkey.comm));

	if (!comm_allowed(hkey.comm))
		return 0;

	histp = bpf_map_lookup_or_try_init(&hists, &hkey, &zero);
	if (!histp)
		return 0;

	data_len = BPF_CORE_READ(rq, __data_len);

	data_len /= 1024;

	if (data_len == 0)
		slot = 0;
	else
		slot = log2l(data_len);

	if (slot >= MAX_SLOTS)
		slot = MAX_SLOTS - 1;

	/*
	 * hists is PERCPU_HASH, so no atomic operation is needed.
	 */
	histp->slots[slot]++;

	return 0;
}

SEC("tp_btf/block_rq_issue")
int BPF_PROG(block_rq_issue)
{
	/*
	 * commit a54895fa changed block_rq_issue tracepoint args:
	 *
	 * before:
	 *   TP_PROTO(struct request_queue *q, struct request *rq)
	 *
	 * after:
	 *   TP_PROTO(struct request *rq)
	 */
	if (LINUX_KERNEL_VERSION >= KERNEL_VERSION(5, 10, 137))
		return trace_rq_issue((void *)ctx[0]);
	else
		return trace_rq_issue((void *)ctx[1]);
}

char LICENSE[] SEC("license") = "GPL";