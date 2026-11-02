// SPDX-License-Identifier: GPL-2.0
// Copyright (c) 2020 Wenbo Zhang
#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_core_read.h>
#include <bpf/bpf_tracing.h>
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


#include "core_fixes.bpf.h"

#define TASK_RUNNING	0
#define TASK_COMM_LEN	16
#define MAX_SLOTS	36

struct hist {
	__u32 slots[MAX_SLOTS];
	char comm[TASK_COMM_LEN];
};

const volatile bool filter_cg = false;
const volatile bool targ_per_process = false;
const volatile bool targ_per_thread = false;
const volatile bool targ_offcpu = false;
const volatile bool targ_ms = false;
const volatile pid_t targ_tgid = -1;

struct {
	__uint(type, BPF_MAP_TYPE_CGROUP_ARRAY);
	__type(key, u32);
	__type(value, u32);
	__uint(max_entries, 1);
} cgroup_map SEC(".maps");

struct {
	__uint(type, BPF_MAP_TYPE_HASH);
	__type(key, u32);
	__type(value, u64);
} start SEC(".maps");

static struct hist initial_hist;

struct {
	__uint(type, BPF_MAP_TYPE_HASH);
	__type(key, u32);
	__type(value, struct hist);
} hists SEC(".maps");

static __always_inline void store_start(u32 tgid, u32 pid, u64 ts)
{
	if (targ_tgid != -1 && targ_tgid != tgid)
		return;
	bpf_map_update_elem(&start, &pid, &ts, 0);
}

static __always_inline void update_hist(struct task_struct *task,
					u32 tgid, u32 pid, u64 ts)
{
	u64 delta, *tsp, slot;
	struct hist *histp;
	u32 id;

	if (targ_tgid != -1 && targ_tgid != tgid)
		return;

	tsp = bpf_map_lookup_elem(&start, &pid);
	if (!tsp || ts < *tsp)
		return;

	if (targ_per_process)
		id = tgid;
	else if (targ_per_thread)
		id = pid;
	else
		id = -1;
	histp = bpf_map_lookup_elem(&hists, &id);
	if (!histp) {
		bpf_map_update_elem(&hists, &id, &initial_hist, 0);
		histp = bpf_map_lookup_elem(&hists, &id);
		if (!histp)
			return;
		BPF_CORE_READ_STR_INTO(&histp->comm, task, comm);
	}
	delta = ts - *tsp;
	if (targ_ms)
		delta /= 1000000;
	else
		delta /= 1000;
	slot = log2l(delta);
	if (slot >= MAX_SLOTS)
		slot = MAX_SLOTS - 1;
	__sync_fetch_and_add(&histp->slots[slot], 1);
}

static int handle_switch(struct task_struct *prev, struct task_struct *next)
{
	u32 prev_tgid = BPF_CORE_READ(prev, tgid), prev_pid = BPF_CORE_READ(prev, pid);
	u32 tgid = BPF_CORE_READ(next, tgid), pid = BPF_CORE_READ(next, pid);
	u64 ts = bpf_ktime_get_ns();

	if (filter_cg && !bpf_current_task_under_cgroup(&cgroup_map, 0))
		return 0;

	if (targ_offcpu) {
		store_start(prev_tgid, prev_pid, ts);
		update_hist(next, tgid, pid, ts);
	} else {
		if (get_task_state(prev) == TASK_RUNNING)
			update_hist(prev, prev_tgid, prev_pid, ts);
		store_start(tgid, pid, ts);
	}
	return 0;
}

SEC("tp_btf/sched_switch")
int BPF_PROG(sched_switch_btf, bool preempt, struct task_struct *prev,
	     struct task_struct *next)
{
	return handle_switch(prev, next);
}

SEC("raw_tp/sched_switch")
int BPF_PROG(sched_switch_tp, bool preempt, struct task_struct *prev,
	     struct task_struct *next)
{
	return handle_switch(prev, next);
}

char LICENSE[] SEC("license") = "GPL";