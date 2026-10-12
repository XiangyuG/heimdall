
/Users/dajohnyu/Documents/heimdall/heimdall/Clang-opt-experiment/manual-opt-2dBPkF/chain-of-updates/hand-no-opt.o:	file format elf64-bpf

Disassembly of section fentry/blk_account_io_done:

0000000000000000 <blk_account_io_done>:
       0:	7b 1a d0 ff 00 00 00 00	*(u64 *)(r10 - 0x30) = r1
       1:	79 a2 d0 ff 00 00 00 00	r2 = *(u64 *)(r10 - 0x30)
       2:	79 21 00 00 00 00 00 00	r1 = *(u64 *)(r2 + 0x0)
       3:	7b 2a e0 ff 00 00 00 00	*(u64 *)(r10 - 0x20) = r2
       4:	7b 1a d8 ff 00 00 00 00	*(u64 *)(r10 - 0x28) = r1
       5:	79 a1 d8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x28)
       6:	7b 1a f8 ff 00 00 00 00	*(u64 *)(r10 - 0x8) = r1
       7:	79 a1 f8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x8)
       8:	7b 1a f0 ff 00 00 00 00	*(u64 *)(r10 - 0x10) = r1
       9:	79 a1 f0 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x10)
      10:	7b 1a e8 ff 00 00 00 00	*(u64 *)(r10 - 0x18) = r1
      11:	79 a2 f8 ff 00 00 00 00	r2 = *(u64 *)(r10 - 0x8)
      12:	57 02 00 00 1f 00 00 00	r2 &= 0x1f
      13:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      14:	0f 21 00 00 00 00 00 00	r1 += r2
      15:	7b 1a e8 ff 00 00 00 00	*(u64 *)(r10 - 0x18) = r1
      16:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      17:	7b 1a f0 ff 00 00 00 00	*(u64 *)(r10 - 0x10) = r1
      18:	79 a1 f0 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x10)
      19:	bc 10 00 00 00 00 00 00	w0 = w1
      20:	95 00 00 00 00 00 00 00	exit
