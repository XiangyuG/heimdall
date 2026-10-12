
/Users/dajohnyu/Documents/heimdall/heimdall/Clang-opt-experiment/manual-opt-2dBPkF/repeated-condition/original-no-opt.o:	file format elf64-bpf

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
      10:	57 01 00 00 01 00 00 00	r1 &= 0x1
      11:	15 01 05 00 00 00 00 00	if r1 == 0x0 goto +0x5 <blk_account_io_done+0x88>
      12:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x68>
      13:	79 a1 e0 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x20)
      14:	07 01 00 00 01 00 00 00	r1 += 0x1
      15:	7b 1a e0 ff 00 00 00 00	*(u64 *)(r10 - 0x20) = r1
      16:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x88>
      17:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      18:	57 01 00 00 01 00 00 00	r1 &= 0x1
      19:	15 01 05 00 00 00 00 00	if r1 == 0x0 goto +0x5 <blk_account_io_done+0xc8>
      20:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0xa8>
      21:	79 a1 e0 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x20)
      22:	07 01 00 00 02 00 00 00	r1 += 0x2
      23:	7b 1a e0 ff 00 00 00 00	*(u64 *)(r10 - 0x20) = r1
      24:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0xc8>
      25:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      26:	57 01 00 00 01 00 00 00	r1 &= 0x1
      27:	15 01 05 00 00 00 00 00	if r1 == 0x0 goto +0x5 <blk_account_io_done+0x108>
      28:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0xe8>
      29:	79 a1 e0 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x20)
      30:	07 01 00 00 03 00 00 00	r1 += 0x3
      31:	7b 1a e0 ff 00 00 00 00	*(u64 *)(r10 - 0x20) = r1
      32:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x108>
      33:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      34:	57 01 00 00 01 00 00 00	r1 &= 0x1
      35:	15 01 05 00 00 00 00 00	if r1 == 0x0 goto +0x5 <blk_account_io_done+0x148>
      36:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x128>
      37:	79 a1 e0 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x20)
      38:	07 01 00 00 04 00 00 00	r1 += 0x4
      39:	7b 1a e0 ff 00 00 00 00	*(u64 *)(r10 - 0x20) = r1
      40:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x148>
      41:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
      42:	57 01 00 00 01 00 00 00	r1 &= 0x1
      43:	15 01 05 00 00 00 00 00	if r1 == 0x0 goto +0x5 <blk_account_io_done+0x188>
      44:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x168>
      45:	79 a1 e0 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x20)
      46:	07 01 00 00 05 00 00 00	r1 += 0x5
      47:	7b 1a e0 ff 00 00 00 00	*(u64 *)(r10 - 0x20) = r1
      48:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x188>
      49:	79 a1 e0 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x20)
      50:	bc 10 00 00 00 00 00 00	w0 = w1
      51:	95 00 00 00 00 00 00 00	exit
