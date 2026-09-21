// SPDX-License-Identifier: GPL-2.0
#include "vmlinux.h"
#include "maps.bpf.h"
#include <bpf/bpf_tracing.h>




struct {
	__uint(type, BPF_MAP_TYPE_HASH);
	__uint(max_entries, 1024);
	__type(key, __u32);
	__type(value, __u64);
} bench_map SEC(".maps");

static __u64 zero;

static __always_inline
int trace_done(struct request *rq)
{
	volatile __u64 benchmark_duration = (__u64)(unsigned long)rq;


	__u32 key = (__u32)(unsigned long)rq;
	void *value;
	value = bpf_map_lookup_or_try_init(&bench_map, &key, &zero);
	benchmark_duration += value != 0;
	value = bpf_map_lookup_or_try_init(&bench_map, &key, &zero);
	benchmark_duration += value != 0;
	value = bpf_map_lookup_or_try_init(&bench_map, &key, &zero);
	benchmark_duration += value != 0;

	return (int)benchmark_duration;
}

SEC("fentry/blk_account_io_done")
int BPF_PROG(blk_account_io_done, struct request *rq)
{
	return trace_done(rq);
}

char LICENSE[] SEC("license") = "GPL";
