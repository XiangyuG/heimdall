
/Users/dajohnyu/Documents/heimdall/heimdall/Clang-opt-experiment/manual-opt-2dBPkF/identical-branches/original-no-opt.o:	file format elf64-bpf

Disassembly of section fentry/blk_account_io_done:

0000000000000000 <blk_account_io_done>:
       0:	7b 1a e0 ff 00 00 00 00	*(u64 *)(r10 - 0x20) = r1
       1:	79 a2 e0 ff 00 00 00 00	r2 = *(u64 *)(r10 - 0x20)
       2:	79 21 00 00 00 00 00 00	r1 = *(u64 *)(r2 + 0x0)
       3:	7b 2a f8 ff 00 00 00 00	*(u64 *)(r10 - 0x8) = r2
       4:	7b 1a f0 ff 00 00 00 00	*(u64 *)(r10 - 0x10) = r1
       5:	79 a1 f0 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x10)
       6:	7b 1a e8 ff 00 00 00 00	*(u64 *)(r10 - 0x18) = r1
       7:	79 a1 f0 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x10)
       8:	57 01 00 00 01 00 00 00	r1 &= 0x1
       9:	15 01 05 00 00 00 00 00	if r1 == 0x0 goto +0x5 <blk_account_io_done+0x78>
      10:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x58>
      11:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      12:	07 01 00 00 03 00 00 00	r1 += 0x3
      13:	7b 1a e8 ff 00 00 00 00	*(u64 *)(r10 - 0x18) = r1
      14:	05 00 04 00 00 00 00 00	goto +0x4 <blk_account_io_done+0x98>
      15:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      16:	07 01 00 00 03 00 00 00	r1 += 0x3
      17:	7b 1a e8 ff 00 00 00 00	*(u64 *)(r10 - 0x18) = r1
      18:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x98>
      19:	79 a1 f0 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x10)
      20:	57 01 00 00 02 00 00 00	r1 &= 0x2
      21:	15 01 05 00 00 00 00 00	if r1 == 0x0 goto +0x5 <blk_account_io_done+0xd8>
      22:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0xb8>
      23:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      24:	07 01 00 00 03 00 00 00	r1 += 0x3
      25:	7b 1a e8 ff 00 00 00 00	*(u64 *)(r10 - 0x18) = r1
      26:	05 00 04 00 00 00 00 00	goto +0x4 <blk_account_io_done+0xf8>
      27:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      28:	07 01 00 00 03 00 00 00	r1 += 0x3
      29:	7b 1a e8 ff 00 00 00 00	*(u64 *)(r10 - 0x18) = r1
      30:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0xf8>
      31:	79 a1 f0 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x10)
      32:	57 01 00 00 04 00 00 00	r1 &= 0x4
      33:	15 01 05 00 00 00 00 00	if r1 == 0x0 goto +0x5 <blk_account_io_done+0x138>
      34:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x118>
      35:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      36:	07 01 00 00 03 00 00 00	r1 += 0x3
      37:	7b 1a e8 ff 00 00 00 00	*(u64 *)(r10 - 0x18) = r1
      38:	05 00 04 00 00 00 00 00	goto +0x4 <blk_account_io_done+0x158>
      39:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      40:	07 01 00 00 03 00 00 00	r1 += 0x3
      41:	7b 1a e8 ff 00 00 00 00	*(u64 *)(r10 - 0x18) = r1
      42:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x158>
      43:	79 a1 f0 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x10)
      44:	57 01 00 00 08 00 00 00	r1 &= 0x8
      45:	15 01 05 00 00 00 00 00	if r1 == 0x0 goto +0x5 <blk_account_io_done+0x198>
      46:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x178>
      47:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      48:	07 01 00 00 03 00 00 00	r1 += 0x3
      49:	7b 1a e8 ff 00 00 00 00	*(u64 *)(r10 - 0x18) = r1
      50:	05 00 04 00 00 00 00 00	goto +0x4 <blk_account_io_done+0x1b8>
      51:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      52:	07 01 00 00 03 00 00 00	r1 += 0x3
      53:	7b 1a e8 ff 00 00 00 00	*(u64 *)(r10 - 0x18) = r1
      54:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x1b8>
      55:	79 a1 f0 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x10)
      56:	57 01 00 00 10 00 00 00	r1 &= 0x10
      57:	15 01 05 00 00 00 00 00	if r1 == 0x0 goto +0x5 <blk_account_io_done+0x1f8>
      58:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x1d8>
      59:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      60:	07 01 00 00 03 00 00 00	r1 += 0x3
      61:	7b 1a e8 ff 00 00 00 00	*(u64 *)(r10 - 0x18) = r1
      62:	05 00 04 00 00 00 00 00	goto +0x4 <blk_account_io_done+0x218>
      63:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      64:	07 01 00 00 03 00 00 00	r1 += 0x3
      65:	7b 1a e8 ff 00 00 00 00	*(u64 *)(r10 - 0x18) = r1
      66:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x218>
      67:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      68:	bc 10 00 00 00 00 00 00	w0 = w1
      69:	95 00 00 00 00 00 00 00	exit
