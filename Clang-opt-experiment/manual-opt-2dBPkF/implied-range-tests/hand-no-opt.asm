
/Users/dajohnyu/Documents/heimdall/heimdall/Clang-opt-experiment/manual-opt-2dBPkF/implied-range-tests/hand-no-opt.o:	file format elf64-bpf

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
      10:	65 01 05 00 07 00 00 00	if r1 s> 0x7 goto +0x5 <blk_account_io_done+0x80>
      11:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x60>
      12:	79 a1 e0 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x20)
      13:	07 01 00 00 0a 00 00 00	r1 += 0xa
      14:	7b 1a e0 ff 00 00 00 00	*(u64 *)(r10 - 0x20) = r1
      15:	05 00 00 00 00 00 00 00	goto +0x0 <blk_account_io_done+0x80>
      16:	79 a1 e0 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x20)
      17:	bc 10 00 00 00 00 00 00	w0 = w1
      18:	95 00 00 00 00 00 00 00	exit
