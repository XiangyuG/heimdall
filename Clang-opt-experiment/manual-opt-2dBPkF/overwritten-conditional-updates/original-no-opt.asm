
/Users/dajohnyu/Documents/heimdall/heimdall/Clang-opt-experiment/manual-opt-2dBPkF/overwritten-conditional-updates/original-no-opt.o:	file format elf64-bpf

Disassembly of section fentry/blk_account_io_done:

0000000000000000 <blk_account_io_done>:
       0:	7b 1a d8 ff 00 00 00 00	*(u64 *)(r10 - 0x28) = r1
       1:	79 a2 d8 ff 00 00 00 00	r2 = *(u64 *)(r10 - 0x28)
       2:	79 21 00 00 00 00 00 00	r1 = *(u64 *)(r2 + 0x0)
       3:	7b 2a f8 ff 00 00 00 00	*(u64 *)(r10 - 0x8) = r2
       4:	7b 1a f0 ff 00 00 00 00	*(u64 *)(r10 - 0x10) = r1
       5:	79 a1 f0 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x10)
       6:	7b 1a e8 ff 00 00 00 00	*(u64 *)(r10 - 0x18) = r1
       7:	b7 01 00 00 00 00 00 00	r1 = 0x0
       8:	7b 1a e0 ff 00 00 00 00	*(u64 *)(r10 - 0x20) = r1
       9:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      10:	57 01 00 00 01 00 00 00	r1 &= 0x1
      11:	15 01 04 00 00 00 00 00	if r1 == 0x0 goto +0x4 <blk_account_io_done+0x80>
      12:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x68>
      13:	b7 01 00 00 01 00 00 00	r1 = 0x1
      14:	7b 1a e0 ff 00 00 00 00	*(u64 *)(r10 - 0x20) = r1
      15:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x80>
      16:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      17:	57 01 00 00 02 00 00 00	r1 &= 0x2
      18:	15 01 04 00 00 00 00 00	if r1 == 0x0 goto +0x4 <blk_account_io_done+0xb8>
      19:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0xa0>
      20:	b7 01 00 00 02 00 00 00	r1 = 0x2
      21:	7b 1a e0 ff 00 00 00 00	*(u64 *)(r10 - 0x20) = r1
      22:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0xb8>
      23:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      24:	57 01 00 00 04 00 00 00	r1 &= 0x4
      25:	15 01 04 00 00 00 00 00	if r1 == 0x0 goto +0x4 <blk_account_io_done+0xf0>
      26:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0xd8>
      27:	b7 01 00 00 03 00 00 00	r1 = 0x3
      28:	7b 1a e0 ff 00 00 00 00	*(u64 *)(r10 - 0x20) = r1
      29:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0xf0>
      30:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      31:	57 01 00 00 08 00 00 00	r1 &= 0x8
      32:	15 01 04 00 00 00 00 00	if r1 == 0x0 goto +0x4 <blk_account_io_done+0x128>
      33:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x110>
      34:	b7 01 00 00 04 00 00 00	r1 = 0x4
      35:	7b 1a e0 ff 00 00 00 00	*(u64 *)(r10 - 0x20) = r1
      36:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x128>
      37:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      38:	57 01 00 00 10 00 00 00	r1 &= 0x10
      39:	15 01 04 00 00 00 00 00	if r1 == 0x0 goto +0x4 <blk_account_io_done+0x160>
      40:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x148>
      41:	b7 01 00 00 05 00 00 00	r1 = 0x5
      42:	7b 1a e0 ff 00 00 00 00	*(u64 *)(r10 - 0x20) = r1
      43:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x160>
      44:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      45:	07 01 00 00 07 00 00 00	r1 += 0x7
      46:	7b 1a e0 ff 00 00 00 00	*(u64 *)(r10 - 0x20) = r1
      47:	79 a1 e0 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x20)
      48:	bc 10 00 00 00 00 00 00	w0 = w1
      49:	95 00 00 00 00 00 00 00	exit
