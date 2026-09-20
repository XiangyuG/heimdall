// SPDX-License-Identifier: GPL-2.0
// Copyright (c) 2021 Wenbo Zhang

#include "vmlinux.h"

#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>

enum stat_idx {
	IDX_TOTAL = 0,
	IDX_MISSES = 1,
	IDX_MBD = 2,
	MAX_STATS = 3,
};

struct {
	__uint(type, BPF_MAP_TYPE_PERCPU_ARRAY);
	__uint(max_entries, MAX_STATS);
	__type(key, __u32);
	__type(value, __s64);
} stats SEC(".maps");

static __always_inline void inc_stat(__u32 idx, __s64 delta)
{
	__s64 *value;

	value = bpf_map_lookup_elem(&stats, &idx);
	if (!value)
		return;

	*value += delta;
}

SEC("fentry/add_to_page_cache_lru")
int BPF_PROG(fentry_add_to_page_cache_lru)
{
	inc_stat(IDX_MISSES, 1);
	return 0;
}

SEC("fentry/mark_page_accessed")
int BPF_PROG(fentry_mark_page_accessed)
{
	inc_stat(IDX_TOTAL, 1);
	return 0;
}

SEC("fentry/account_page_dirtied")
int BPF_PROG(fentry_account_page_dirtied)
{
	inc_stat(IDX_MISSES, -1);
	return 0;
}

SEC("fentry/mark_buffer_dirty")
int BPF_PROG(fentry_mark_buffer_dirty)
{
	inc_stat(IDX_TOTAL, -1);
	inc_stat(IDX_MBD, 1);
	return 0;
}

SEC("kprobe/add_to_page_cache_lru")
int BPF_KPROBE(kprobe_add_to_page_cache_lru)
{
	inc_stat(IDX_MISSES, 1);
	return 0;
}

SEC("kprobe/mark_page_accessed")
int BPF_KPROBE(kprobe_mark_page_accessed)
{
	inc_stat(IDX_TOTAL, 1);
	return 0;
}

SEC("kprobe/account_page_dirtied")
int BPF_KPROBE(kprobe_account_page_dirtied)
{
	inc_stat(IDX_MISSES, -1);
	return 0;
}

SEC("kprobe/folio_account_dirtied")
int BPF_KPROBE(kprobe_folio_account_dirtied)
{
	inc_stat(IDX_MISSES, -1);
	return 0;
}

SEC("kprobe/mark_buffer_dirty")
int BPF_KPROBE(kprobe_mark_buffer_dirty)
{
	inc_stat(IDX_TOTAL, -1);
	inc_stat(IDX_MBD, 1);
	return 0;
}

SEC("tracepoint/writeback/writeback_dirty_folio")
int tracepoint__writeback_dirty_folio(void *ctx)
{
	inc_stat(IDX_MISSES, -1);
	return 0;
}

SEC("tracepoint/writeback/writeback_dirty_page")
int tracepoint__writeback_dirty_page(void *ctx)
{
	inc_stat(IDX_MISSES, -1);
	return 0;
}

char LICENSE[] SEC("license") = "GPL";