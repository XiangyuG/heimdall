
/Users/dajohnyu/Documents/heimdall/heimdall/Clang-opt-experiment/manual-opt-2dBPkF/implied-range-tests/original-no-opt.o:	file format elf64-bpf

Disassembly of section fentry/blk_account_io_done:

0000000000000000 <blk_account_io_done>:
       0:	7b 1a d8 ff 00 00 00 00	*(u64 *)(r10 - 0x28) = r1
       1:	79 a2 d8 ff 00 00 00 00	r2 = *(u64 *)(r10 - 0x28)
       2:	79 21 00 00 00 00 00 00	r1 = *(u64 *)(r2 + 0x0)
       3:	7b 2a f8 ff 00 00 00 00	*(u64 *)(r10 - 0x8) = r2
       4:	7b 1a f0 ff 00 00 00 00	*(u64 *)(r10 - 0x10) = r1
       5:	79 a1 f0 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x10)
       6:	7b 1a e8 ff 00 00 00 00	*(u64 *)(r10 - 0x18) = r1
       7:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
       8:	7b 1a e0 ff 00 00 00 00	*(u64 *)(r10 - 0x20) = r1
       9:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      10:	65 01 1e 00 07 00 00 00	if r1 s> 0x7 goto +0x1e <blk_account_io_done+0x148>
      11:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x60>
      12:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      13:	65 01 05 00 0f 00 00 00	if r1 s> 0xf goto +0x5 <blk_account_io_done+0x98>
      14:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x78>
      15:	79 a1 e0 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x20)
      16:	07 01 00 00 01 00 00 00	r1 += 0x1
      17:	7b 1a e0 ff 00 00 00 00	*(u64 *)(r10 - 0x20) = r1
      18:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x98>
      19:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      20:	65 01 05 00 1f 00 00 00	if r1 s> 0x1f goto +0x5 <blk_account_io_done+0xd0>
      21:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0xb0>
      22:	79 a1 e0 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x20)
      23:	07 01 00 00 02 00 00 00	r1 += 0x2
      24:	7b 1a e0 ff 00 00 00 00	*(u64 *)(r10 - 0x20) = r1
      25:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0xd0>
      26:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      27:	65 01 05 00 3f 00 00 00	if r1 s> 0x3f goto +0x5 <blk_account_io_done+0x108>
      28:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0xe8>
      29:	79 a1 e0 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x20)
      30:	07 01 00 00 03 00 00 00	r1 += 0x3
      31:	7b 1a e0 ff 00 00 00 00	*(u64 *)(r10 - 0x20) = r1
      32:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x108>
      33:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      34:	65 01 05 00 7f 00 00 00	if r1 s> 0x7f goto +0x5 <blk_account_io_done+0x140>
      35:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x120>
      36:	79 a1 e0 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x20)
      37:	07 01 00 00 04 00 00 00	r1 += 0x4
      38:	7b 1a e0 ff 00 00 00 00	*(u64 *)(r10 - 0x20) = r1
      39:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x140>
      40:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x148>
      41:	79 a1 e0 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x20)
      42:	bc 10 00 00 00 00 00 00	w0 = w1
      43:	95 00 00 00 00 00 00 00	exit
