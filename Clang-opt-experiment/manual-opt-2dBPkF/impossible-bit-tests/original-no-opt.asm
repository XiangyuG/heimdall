
/Users/dajohnyu/Documents/heimdall/heimdall/Clang-opt-experiment/manual-opt-2dBPkF/impossible-bit-tests/original-no-opt.o:	file format elf64-bpf

Disassembly of section fentry/blk_account_io_done:

0000000000000000 <blk_account_io_done>:
       0:	7b 1a f8 ff 00 00 00 00	*(u64 *)(r10 - 0x8) = r1
       1:	79 a1 f8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x8)
       2:	79 11 00 00 00 00 00 00	r1 = *(u64 *)(r1 + 0x0)
       3:	7b 1a f0 ff 00 00 00 00	*(u64 *)(r10 - 0x10) = r1
       4:	79 a1 f0 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x10)
       5:	7b 1a e8 ff 00 00 00 00	*(u64 *)(r10 - 0x18) = r1
       6:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
       7:	7b 1a e0 ff 00 00 00 00	*(u64 *)(r10 - 0x20) = r1
       8:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
       9:	57 01 00 00 01 00 00 00	r1 &= 0x1
      10:	55 01 05 00 02 00 00 00	if r1 != 0x2 goto +0x5 <blk_account_io_done+0x80>
      11:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x60>
      12:	79 a1 e0 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x20)
      13:	07 01 00 00 01 00 00 00	r1 += 0x1
      14:	7b 1a e0 ff 00 00 00 00	*(u64 *)(r10 - 0x20) = r1
      15:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x80>
      16:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      17:	57 01 00 00 02 00 00 00	r1 &= 0x2
      18:	55 01 05 00 04 00 00 00	if r1 != 0x4 goto +0x5 <blk_account_io_done+0xc0>
      19:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0xa0>
      20:	79 a1 e0 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x20)
      21:	07 01 00 00 02 00 00 00	r1 += 0x2
      22:	7b 1a e0 ff 00 00 00 00	*(u64 *)(r10 - 0x20) = r1
      23:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0xc0>
      24:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      25:	57 01 00 00 04 00 00 00	r1 &= 0x4
      26:	55 01 05 00 08 00 00 00	if r1 != 0x8 goto +0x5 <blk_account_io_done+0x100>
      27:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0xe0>
      28:	79 a1 e0 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x20)
      29:	07 01 00 00 04 00 00 00	r1 += 0x4
      30:	7b 1a e0 ff 00 00 00 00	*(u64 *)(r10 - 0x20) = r1
      31:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x100>
      32:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      33:	57 01 00 00 08 00 00 00	r1 &= 0x8
      34:	55 01 05 00 10 00 00 00	if r1 != 0x10 goto +0x5 <blk_account_io_done+0x140>
      35:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x120>
      36:	79 a1 e0 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x20)
      37:	07 01 00 00 08 00 00 00	r1 += 0x8
      38:	7b 1a e0 ff 00 00 00 00	*(u64 *)(r10 - 0x20) = r1
      39:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x140>
      40:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      41:	57 01 00 00 10 00 00 00	r1 &= 0x10
      42:	55 01 05 00 20 00 00 00	if r1 != 0x20 goto +0x5 <blk_account_io_done+0x180>
      43:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x160>
      44:	79 a1 e0 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x20)
      45:	07 01 00 00 10 00 00 00	r1 += 0x10
      46:	7b 1a e0 ff 00 00 00 00	*(u64 *)(r10 - 0x20) = r1
      47:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x180>
      48:	79 a1 e0 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x20)
      49:	bc 10 00 00 00 00 00 00	w0 = w1
      50:	95 00 00 00 00 00 00 00	exit
