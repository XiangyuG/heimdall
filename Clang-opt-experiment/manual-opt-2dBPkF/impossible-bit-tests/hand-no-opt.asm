
/Users/dajohnyu/Documents/heimdall/heimdall/Clang-opt-experiment/manual-opt-2dBPkF/impossible-bit-tests/hand-no-opt.o:	file format elf64-bpf

Disassembly of section fentry/blk_account_io_done:

0000000000000000 <blk_account_io_done>:
       0:	7b 1a f8 ff 00 00 00 00	*(u64 *)(r10 - 0x8) = r1
       1:	79 a1 f8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x8)
       2:	79 11 00 00 00 00 00 00	r1 = *(u64 *)(r1 + 0x0)
       3:	7b 1a f0 ff 00 00 00 00	*(u64 *)(r10 - 0x10) = r1
       4:	79 a1 f0 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x10)
       5:	7b 1a e8 ff 00 00 00 00	*(u64 *)(r10 - 0x18) = r1
       6:	79 a1 e8 ff 00 00 00 00	r1 = *(u64 *)(r10 - 0x18)
       7:	bc 10 00 00 00 00 00 00	w0 = w1
       8:	95 00 00 00 00 00 00 00	exit
