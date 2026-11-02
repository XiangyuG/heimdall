// SPDX-License-Identifier: GPL-2.0
// Copyright (c) 2021 Yaqi Chen
#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_core_read.h>
#include <bpf/bpf_tracing.h>
/* Unused bpf_endian.h include omitted in both standalone build copies. */
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

#define MAX_SLOTS 32

struct hist {
	__u32 slots[MAX_SLOTS];
};

#define MAX_ENTRIES 65536

struct {
	__uint(type, BPF_MAP_TYPE_HASH);
	__uint(max_entries, MAX_ENTRIES);
	__type(key, u64);
	__type(value, struct hist);
} hists SEC(".maps");

static struct hist zero;

static int do_entry(struct sock *sk)
{
	u64 max_backlog, backlog, slot;
	struct hist *histp;

	max_backlog = BPF_CORE_READ(sk, sk_max_ack_backlog);
	backlog = BPF_CORE_READ(sk, sk_ack_backlog);
	histp = bpf_map_lookup_or_try_init(&hists, &max_backlog, &zero);
	if (!histp)
		return 0;

	slot = log2l(backlog);
	if (slot >= MAX_SLOTS)
		slot = MAX_SLOTS - 1;
	__sync_fetch_and_add(&histp->slots[slot], 1);
	return 0;
}


SEC("kprobe/tcp_v4_syn_recv_sock")
int BPF_KPROBE(tcp_v4_syn_recv_kprobe, struct sock *sk)
{
	return do_entry(sk);
}

SEC("kprobe/tcp_v6_syn_recv_sock")
int BPF_KPROBE(tcp_v6_syn_recv_kprobe, struct sock *sk)
{
	return do_entry(sk);
}

SEC("fentry/tcp_v4_syn_recv_sock")
int BPF_PROG(tcp_v4_syn_recv, struct sock *sk)
{
	return do_entry(sk);
}

SEC("fentry/tcp_v6_syn_recv_sock")
int BPF_PROG(tcp_v6_syn_recv, struct sock *sk)
{
	return do_entry(sk);
}

char LICENSE[] SEC("license") = "Dual BSD/GPL";