
/Users/dajohnyu/Documents/heimdall/heimdall/Clang-opt-experiment/manual-opt-2dBPkF/chain-of-updates/auto-opt.o:	file format elf64-bpf

Disassembly of section fentry/blk_account_io_done:

0000000000000000 <blk_account_io_done>:
       0:	79 11 00 00 00 00 00 00	r1 = *(u64 *)(r1 + 0x0)
       1:	7b 1a f8 ff 00 00 00 00	*(u64 *)(r10 - 0x8) = r1
       2:	57 01 00 00 1f 00 00 00	r1 &= 0x1f
       3:	79 a2 f8 ff 00 00 00 00	r2 = *(u64 *)(r10 - 0x8)
       4:	0f 21 00 00 00 00 00 00	r1 += r2
       5:	7b 1a f8 ff 00 00 00 00	*(u64 *)(r10 - 0x8) = r1
       6:	79 a0 f8 ff 00 00 00 00	r0 = *(u64 *)(r10 - 0x8)
       7:	95 00 00 00 00 00 00 00	exit
