// SPDX-License-Identifier: GPL-2.0
/* Copyright (c) 2021 Google LLC. */
#include "vmlinux.h"
#include <bpf/bpf_core_read.h>
#include <bpf/bpf_helpers.h>
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


#define MAX_PIDS 102400
#define MAX_SLOTS 25

enum units {
	NSEC,
	USEC,
	MSEC,
};

const volatile pid_t targ_tgid = 0;
const volatile int units = 0;
const volatile bool filter_cg = false;

struct {
	__uint(type, BPF_MAP_TYPE_CGROUP_ARRAY);
	__type(key, u32);
	__type(value, u32);
	__uint(max_entries, 1);
} cgroup_map SEC(".maps");

/* key: pid.  value: start time */
struct {
	__uint(type, BPF_MAP_TYPE_HASH);
	__uint(max_entries, MAX_PIDS);
	__type(key, u32);
	__type(value, u64);
} starts SEC(".maps");

__u32 hist[MAX_SLOTS] = {};

static void entry(void)
{
	u64 id = bpf_get_current_pid_tgid();
	u32 tgid = id >> 32;
	u32 pid = id;
	u64 nsec;

	if (filter_cg && !bpf_current_task_under_cgroup(&cgroup_map, 0))
		return;

	if (targ_tgid && targ_tgid != tgid)
		return;
	nsec = bpf_ktime_get_ns();
	bpf_map_update_elem(&starts, &pid, &nsec, BPF_ANY);
}

SEC("fentry/dummy_fentry")
int BPF_PROG(dummy_fentry)
{
	entry();
	return 0;
}

SEC("kprobe/dummy_kprobe")
int BPF_KPROBE(dummy_kprobe)
{
	entry();
	return 0;
}

static void exit(void)
{
	u64 *start;
	u64 nsec = bpf_ktime_get_ns();
	u64 id = bpf_get_current_pid_tgid();
	u32 pid = id;
	u64 slot, delta;

	if (filter_cg && !bpf_current_task_under_cgroup(&cgroup_map, 0))
		return;

	start = bpf_map_lookup_elem(&starts, &pid);
	if (!start)
		return;

	delta = nsec - *start;

	switch (units) {
	case USEC:
		delta /= 1000;
		break;
	case MSEC:
		delta /= 1000000;
		break;
	}

	slot = log2l(delta);
	if (slot >= MAX_SLOTS)
		slot = MAX_SLOTS - 1;
	__sync_fetch_and_add(&hist[slot], 1);

	bpf_map_delete_elem(&starts, &pid);
}

SEC("fexit/dummy_fexit")
int BPF_PROG(dummy_fexit)
{
	exit();
	return 0;
}

SEC("kretprobe/dummy_kretprobe")
int BPF_KRETPROBE(dummy_kretprobe)
{
	exit();
	return 0;
}

char LICENSE[] SEC("license") = "GPL";