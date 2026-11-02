/* SPDX-License-Identifier: (LGPL-2.1 OR BSD-2-Clause) */
/* Copyright (c) 2021 Hengqi Chen */
#include "vmlinux.h"
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


#define MAX_ENTRIES	10240

const volatile pid_t target_pid = 0;
const volatile bool in_ms = false;

enum fs_file_op {
	F_READ,
	F_WRITE,
	F_OPEN,
	F_FSYNC,
	F_GETATTR,
	F_MAX_OP,
};

#define MAX_SLOTS	32

struct hist {
	__u32 slots[MAX_SLOTS];
};

struct {
	__uint(type, BPF_MAP_TYPE_HASH);
	__uint(max_entries, MAX_ENTRIES);
	__type(key, __u32);
	__type(value, __u64);
} starts SEC(".maps");

struct hist hists[F_MAX_OP] = {};

static int probe_entry()
{
	__u64 pid_tgid = bpf_get_current_pid_tgid();
	__u32 pid = pid_tgid >> 32;
	__u32 tid = (__u32)pid_tgid;
	__u64 ts;

	if (target_pid && target_pid != pid)
		return 0;

	ts = bpf_ktime_get_ns();
	bpf_map_update_elem(&starts, &tid, &ts, BPF_ANY);
	return 0;
}

static int probe_return(enum fs_file_op op)
{
	__u32 tid = (__u32)bpf_get_current_pid_tgid();
	__u64 ts = bpf_ktime_get_ns();
	__u64 *tsp, slot;
	__s64 delta;

	tsp = bpf_map_lookup_elem(&starts, &tid);
	if (!tsp)
		return 0;

	if (op >= F_MAX_OP)
		goto cleanup;

	delta = (__s64)(ts - *tsp);
	if (delta < 0)
		goto cleanup;

	if (in_ms)
		delta /= 1000000;
	else
		delta /= 1000;

	slot = log2l(delta);
	if (slot >= MAX_SLOTS)
		slot = MAX_SLOTS - 1;
	__sync_fetch_and_add(&hists[op].slots[slot], 1);

cleanup:
	bpf_map_delete_elem(&starts, &tid);
	return 0;
}

SEC("kprobe/dummy_file_read")
int BPF_KPROBE(file_read_entry)
{
	return probe_entry();
}

SEC("kretprobe/dummy_file_read")
int BPF_KRETPROBE(file_read_exit)
{
	return probe_return(F_READ);
}

SEC("kprobe/dummy_file_write")
int BPF_KPROBE(file_write_entry)
{
	return probe_entry();
}

SEC("kretprobe/dummy_file_write")
int BPF_KRETPROBE(file_write_exit)
{
	return probe_return(F_WRITE);
}

SEC("kprobe/dummy_file_open")
int BPF_KPROBE(file_open_entry)
{
	return probe_entry();
}

SEC("kretprobe/dummy_file_open")
int BPF_KRETPROBE(file_open_exit)
{
	return probe_return(F_OPEN);
}

SEC("kprobe/dummy_file_sync")
int BPF_KPROBE(file_sync_entry)
{
	return probe_entry();
}

SEC("kretprobe/dummy_file_sync")
int BPF_KRETPROBE(file_sync_exit)
{
	return probe_return(F_FSYNC);
}

SEC("kprobe/dummy_getattr")
int BPF_KPROBE(getattr_entry)
{
	return probe_entry();
}

SEC("kretprobe/dummy_getattr")
int BPF_KRETPROBE(getattr_exit)
{
	return probe_return(F_GETATTR);
}

SEC("fentry/dummy_file_read")
int BPF_PROG(file_read_fentry)
{
	return probe_entry();
}

SEC("fexit/dummy_file_read")
int BPF_PROG(file_read_fexit)
{
	return probe_return(F_READ);
}

SEC("fentry/dummy_file_write")
int BPF_PROG(file_write_fentry)
{
	return probe_entry();
}

SEC("fexit/dummy_file_write")
int BPF_PROG(file_write_fexit)
{
	return probe_return(F_WRITE);
}

SEC("fentry/dummy_file_open")
int BPF_PROG(file_open_fentry)
{
	return probe_entry();
}

SEC("fexit/dummy_file_open")
int BPF_PROG(file_open_fexit)
{
	return probe_return(F_OPEN);
}

SEC("fentry/dummy_file_sync")
int BPF_PROG(file_sync_fentry)
{
	return probe_entry();
}

SEC("fexit/dummy_file_sync")
int BPF_PROG(file_sync_fexit)
{
	return probe_return(F_FSYNC);
}

SEC("fentry/dummy_getattr")
int BPF_PROG(getattr_fentry)
{
	return probe_entry();
}

SEC("fexit/dummy_getattr")
int BPF_PROG(getattr_fexit)
{
	return probe_return(F_GETATTR);
}

char LICENSE[] SEC("license") = "Dual BSD/GPL";