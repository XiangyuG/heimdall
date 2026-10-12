
/Users/dajohnyu/Documents/heimdall/heimdall/Clang-opt-experiment/manual-opt-2dBPkF/chain-of-updates/original-no-opt.o:	file format elf64-bpf

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
      11:	79 a1 f8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x8)
      12:	57 01 00 00 01 00 00 00	r1 &= 0x1
      13:	15 01 05 00 00 00 00 00	if r1 == 0x0 goto +0x5 <blk_account_io_done+0x98>
      14:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x78>
      15:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      16:	07 01 00 00 01 00 00 00	r1 += 0x1
      17:	7b 1a c8 ff 00 00 00 00	*(u64 *)(r10 - 0x38) = r1
      18:	05 00 03 00 00 00 00 00	goto +0x3 <blk_account_io_done+0xb0>
      19:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      20:	7b 1a c8 ff 00 00 00 00	*(u64 *)(r10 - 0x38) = r1
      21:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0xb0>
      22:	79 a1 c8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x38)
      23:	7b 1a e8 ff 00 00 00 00	*(u64 *)(r10 - 0x18) = r1
      24:	79 a1 f8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x8)
      25:	57 01 00 00 02 00 00 00	r1 &= 0x2
      26:	15 01 05 00 00 00 00 00	if r1 == 0x0 goto +0x5 <blk_account_io_done+0x100>
      27:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0xe0>
      28:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      29:	07 01 00 00 02 00 00 00	r1 += 0x2
      30:	7b 1a c0 ff 00 00 00 00	*(u64 *)(r10 - 0x40) = r1
      31:	05 00 03 00 00 00 00 00	goto +0x3 <blk_account_io_done+0x118>
      32:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      33:	7b 1a c0 ff 00 00 00 00	*(u64 *)(r10 - 0x40) = r1
      34:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x118>
      35:	79 a1 c0 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x40)
      36:	7b 1a e8 ff 00 00 00 00	*(u64 *)(r10 - 0x18) = r1
      37:	79 a1 f8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x8)
      38:	57 01 00 00 04 00 00 00	r1 &= 0x4
      39:	15 01 05 00 00 00 00 00	if r1 == 0x0 goto +0x5 <blk_account_io_done+0x168>
      40:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x148>
      41:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      42:	07 01 00 00 04 00 00 00	r1 += 0x4
      43:	7b 1a b8 ff 00 00 00 00	*(u64 *)(r10 - 0x48) = r1
      44:	05 00 03 00 00 00 00 00	goto +0x3 <blk_account_io_done+0x180>
      45:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      46:	7b 1a b8 ff 00 00 00 00	*(u64 *)(r10 - 0x48) = r1
      47:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x180>
      48:	79 a1 b8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x48)
      49:	7b 1a e8 ff 00 00 00 00	*(u64 *)(r10 - 0x18) = r1
      50:	79 a1 f8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x8)
      51:	57 01 00 00 08 00 00 00	r1 &= 0x8
      52:	15 01 05 00 00 00 00 00	if r1 == 0x0 goto +0x5 <blk_account_io_done+0x1d0>
      53:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x1b0>
      54:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      55:	07 01 00 00 08 00 00 00	r1 += 0x8
      56:	7b 1a b0 ff 00 00 00 00	*(u64 *)(r10 - 0x50) = r1
      57:	05 00 03 00 00 00 00 00	goto +0x3 <blk_account_io_done+0x1e8>
      58:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      59:	7b 1a b0 ff 00 00 00 00	*(u64 *)(r10 - 0x50) = r1
      60:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x1e8>
      61:	79 a1 b0 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x50)
      62:	7b 1a e8 ff 00 00 00 00	*(u64 *)(r10 - 0x18) = r1
      63:	79 a1 f8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x8)
      64:	57 01 00 00 10 00 00 00	r1 &= 0x10
      65:	15 01 05 00 00 00 00 00	if r1 == 0x0 goto +0x5 <blk_account_io_done+0x238>
      66:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x218>
      67:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      68:	07 01 00 00 10 00 00 00	r1 += 0x10
      69:	7b 1a a8 ff 00 00 00 00	*(u64 *)(r10 - 0x58) = r1
      70:	05 00 03 00 00 00 00 00	goto +0x3 <blk_account_io_done+0x250>
      71:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      72:	7b 1a a8 ff 00 00 00 00	*(u64 *)(r10 - 0x58) = r1
      73:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x250>
      74:	79 a1 a8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x58)
      75:	7b 1a e8 ff 00 00 00 00	*(u64 *)(r10 - 0x18) = r1
      76:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      77:	7b 1a f0 ff 00 00 00 00	*(u64 *)(r10 - 0x10) = r1
      78:	79 a1 f0 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x10)
      79:	bc 10 00 00 00 00 00 00	w0 = w1
      80:	95 00 00 00 00 00 00 00	exit
