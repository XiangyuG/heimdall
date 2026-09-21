// SPDX-License-Identifier: GPL-2.0
#include "vmlinux.h"
#include "maps.bpf.h"
#include <bpf/bpf_tracing.h>

static __always_inline
int trace_done(struct request *rq)
{
	unsigned long base = (unsigned long)rq;

	__u64 r0 = (__u64)base;

	int c0 = (base & (1UL << 0)) != 0;
	__u64 r1 = c0 ? r0 + 1 : r0;

	int c1 = (base & (1UL << 1)) != 0;
	__u64 r2 = c1 ? r1 + 2 : r1;

	int c2 = (base & (1UL << 2)) != 0;
	__u64 r3 = c2 ? r2 + 4 : r2;

	int c3 = (base & (1UL << 3)) != 0;
	__u64 r4 = c3 ? r3 + 8 : r3;

	int c4 = (base & (1UL << 4)) != 0;
	__u64 r5 = c4 ? r4 + 16 : r4;

	int c5 = (base & (1UL << 5)) != 0;
	__u64 r6 = c5 ? r5 + 32 : r5;

	int c6 = (base & (1UL << 6)) != 0;
	__u64 r7 = c6 ? r6 + 64 : r6;

	int c7 = (base & (1UL << 7)) != 0;
	__u64 r8 = c7 ? r7 + 128 : r7;

	int c8 = (base & (1UL << 8)) != 0;
	__u64 r9 = c8 ? r8 + 256 : r8;

	int c9 = (base & (1UL << 9)) != 0;
	__u64 r10 = c9 ? r9 + 512 : r9;

	/*
	 * Keep the final value in a 64-bit volatile object.  The baseline object
	 * returns the 64-bit load of benchmark_duration even though this helper is
	 * declared as returning int, so allowing Clang to narrow r10 to an ALU32
	 * value here would clear the upper 32 bits and change the object-level
	 * behavior checked by verify_equivalence.py.
	 */
	volatile __u64 result = r10;
	return (int)result;
}

SEC("fentry/blk_account_io_done")
int BPF_PROG(blk_account_io_done, struct request *rq)
{
	return trace_done(rq);
}

char LICENSE[] SEC("license") = "GPL";
