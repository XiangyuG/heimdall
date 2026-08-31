// SPDX-License-Identifier: GPL-2.0
#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_core_read.h>
#include <bpf/bpf_tracing.h>
#include <bpf/bpf_endian.h>
#include "bits.bpf.h"
#include "maps.bpf.h"

#define MAX_SLOTS 27
#define IPV6_LEN 16
#define MAX_ENTRIES 10240
#define AF_INET 2
#define AF_INET6 10

struct hist {
	__u64 latency;
	__u64 cnt;
	__u32 slots[MAX_SLOTS];
};

struct hist_key {
	__u16 family;
	__u8 addr[IPV6_LEN];
};

const volatile bool targ_laddr_hist = false;
const volatile bool targ_raddr_hist = false;
const volatile bool targ_show_ext = false;
const volatile __u16 targ_sport = 0;
const volatile __u16 targ_dport = 0;
const volatile __u32 targ_saddr = 0;
const volatile __u32 targ_daddr = 0;
const volatile __u8 targ_saddr_v6[IPV6_LEN] = {};
const volatile __u8 targ_daddr_v6[IPV6_LEN] = {};
const volatile bool targ_ms = false;

struct {
	__uint(type, BPF_MAP_TYPE_HASH);
	__uint(max_entries, MAX_ENTRIES);
	__type(key, struct hist_key);
	__type(value, struct hist);
} hists SEC(".maps");

static struct hist zero = {};

static __always_inline bool ipv6_is_not_zero(const volatile __u8 addr[IPV6_LEN])
{
#pragma unroll
	for (int i = 0; i < IPV6_LEN; i++) {
		if (addr[i])
			return true;
	}
	return false;
}

static __always_inline bool ipv6_are_different(
	const volatile __u8 a[IPV6_LEN],
	const __u8 b[IPV6_LEN])
{
#pragma unroll
	for (int i = 0; i < IPV6_LEN; i++) {
		if (a[i] != b[i])
			return true;
	}
	return false;
}

static __always_inline int handle_tcp_rcv_established(struct sock *sk)
{
	const struct inet_sock *inet = (struct inet_sock *)sk;
	struct hist_key key = {};
	struct hist *histp;
	struct tcp_sock *ts;
	__u16 family, sport, dport;
	bool has_saddr_v6, has_daddr_v6;
	__u32 srtt;
	__u64 slot;

	if (!sk)
		return 0;

	sport = bpf_ntohs(BPF_CORE_READ(inet, inet_sport));
	dport = bpf_ntohs(BPF_CORE_READ(sk, __sk_common.skc_dport));

	if (targ_sport && targ_sport != sport)
		return 0;
	if (targ_dport && targ_dport != dport)
		return 0;

	has_saddr_v6 = ipv6_is_not_zero(targ_saddr_v6);
	has_daddr_v6 = ipv6_is_not_zero(targ_daddr_v6);

	family = BPF_CORE_READ(sk, __sk_common.skc_family);
	key.family = family;

	if (family == AF_INET) {
		if (has_saddr_v6 || has_daddr_v6)
			return 0;

		if (targ_saddr && targ_saddr != BPF_CORE_READ(inet, inet_saddr))
			return 0;
		if (targ_daddr && targ_daddr != BPF_CORE_READ(sk, __sk_common.skc_daddr))
			return 0;
	} else if (family == AF_INET6) {
		if (targ_saddr || targ_daddr)
			return 0;

		if (has_saddr_v6 &&
		    ipv6_are_different(targ_saddr_v6,
				       BPF_CORE_READ(inet, pinet6,
						     saddr.in6_u.u6_addr8)))
			return 0;

		if (has_daddr_v6 &&
		    ipv6_are_different(targ_daddr_v6,
				       BPF_CORE_READ(sk, __sk_common,
						     skc_v6_daddr.in6_u.u6_addr8)))
			return 0;
	} else {
		return 0;
	}

	if (targ_laddr_hist) {
		if (family == AF_INET6) {
			BPF_CORE_READ_INTO(key.addr, inet, pinet6,
					   saddr.in6_u.u6_addr8);
		} else {
			__u32 saddr = BPF_CORE_READ(inet, inet_saddr);
			__builtin_memcpy(key.addr, &saddr, sizeof(saddr));
		}
	} else if (targ_raddr_hist) {
		if (family == AF_INET6) {
			BPF_CORE_READ_INTO(key.addr, sk, __sk_common,
					   skc_v6_daddr.in6_u.u6_addr8);
		} else {
			__u32 daddr = BPF_CORE_READ(sk, __sk_common.skc_daddr);
			__builtin_memcpy(key.addr, &daddr, sizeof(daddr));
		}
	} else {
		key.family = 0;
	}

	histp = bpf_map_lookup_or_try_init(&hists, &key, &zero);
	if (!histp)
		return 0;

	ts = (struct tcp_sock *)sk;
	srtt = BPF_CORE_READ(ts, srtt_us) >> 3;

	if (targ_ms)
		srtt /= 1000U;

	slot = log2l(srtt);
	if (slot >= MAX_SLOTS)
		slot = MAX_SLOTS - 1;

	__sync_fetch_and_add(&histp->slots[slot], 1);

	if (targ_show_ext) {
		__sync_fetch_and_add(&histp->latency, srtt);
		__sync_fetch_and_add(&histp->cnt, 1);
	}

	return 0;
}

SEC("fentry/tcp_rcv_established")
int BPF_PROG(tcp_rcv, struct sock *sk)
{
	return handle_tcp_rcv_established(sk);
}

char LICENSE[] SEC("license") = "Dual BSD/GPL";