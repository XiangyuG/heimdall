// SPDX-License-Identifier: GPL-2.0
// Copyright (c) 2020 Wenbo Zhang
#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>
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

#include "maps.bpf.h"

#define MAX_SLOTS	20

struct hist {
	__u32 slots[MAX_SLOTS];
};


const volatile bool targ_dist = false;
const volatile bool targ_ns = false;
const volatile int targ_cpu = -1;

struct {
	__uint(type, BPF_MAP_TYPE_PERCPU_ARRAY);
	__uint(max_entries, 1);
	__type(key, u32);
	__type(value, u64);
} start SEC(".maps");

__u64 counts[NR_SOFTIRQS] = {};
__u64 time[NR_SOFTIRQS] = {};
struct hist hists[NR_SOFTIRQS] = {};

static bool is_target_cpu() {
	if (targ_cpu < 0)
		return true;

	return bpf_get_smp_processor_id() == targ_cpu;
}

static int handle_entry(unsigned int vec_nr)
{
	if (!is_target_cpu())
		return 0;

	u64 ts = bpf_ktime_get_ns();
	u32 key = 0;

	bpf_map_update_elem(&start, &key, &ts, BPF_ANY);
	return 0;
}

static int handle_exit(unsigned int vec_nr)
{
	if (!is_target_cpu())
		return 0;

	u64 delta, *tsp;
	u32 key = 0;

	if (vec_nr >= NR_SOFTIRQS)
		return 0;
	tsp = bpf_map_lookup_elem(&start, &key);
	if (!tsp)
		return 0;
	delta = bpf_ktime_get_ns() - *tsp;
	if (!targ_ns)
		delta /= 1000U;

	if (!targ_dist) {
		__sync_fetch_and_add(&counts[vec_nr], 1);
		__sync_fetch_and_add(&time[vec_nr], delta);
	} else {
		struct hist *hist;
		u64 slot;

		hist = &hists[vec_nr];
		slot = log2l(delta);
		if (slot >= MAX_SLOTS)
			slot = MAX_SLOTS - 1;
		__sync_fetch_and_add(&hist->slots[slot], 1);
	}

	return 0;
}

SEC("tp_btf/softirq_entry")
int BPF_PROG(softirq_entry_btf, unsigned int vec_nr)
{
	return handle_entry(vec_nr);
}

SEC("tp_btf/softirq_exit")
int BPF_PROG(softirq_exit_btf, unsigned int vec_nr)
{
	return handle_exit(vec_nr);
}

SEC("raw_tp/softirq_entry")
int BPF_PROG(softirq_entry, unsigned int vec_nr)
{
	return handle_entry(vec_nr);
}

SEC("raw_tp/softirq_exit")
int BPF_PROG(softirq_exit, unsigned int vec_nr)
{
	return handle_exit(vec_nr);
}

char LICENSE[] SEC("license") = "GPL";