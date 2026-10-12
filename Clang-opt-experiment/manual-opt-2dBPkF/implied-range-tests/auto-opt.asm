
/Users/dajohnyu/Documents/heimdall/heimdall/Clang-opt-experiment/manual-opt-2dBPkF/implied-range-tests/auto-opt.o:	file format elf64-bpf

Disassembly of section fentry/blk_account_io_done:

0000000000000000 <blk_account_io_done>:
       0:	79 11 00 00 00 00 00 00	r1 = *(u64 *)(r1 + 0x0)
       1:	bc 10 00 00 00 00 00 00	w0 = w1
       2:	04 00 00 00 0a 00 00 00	w0 += 0xa
       3:	c5 01 01 00 08 00 00 00	if r1 s< 0x8 goto +0x1 <blk_account_io_done+0x28>
       4:	bc 10 00 00 00 00 00 00	w0 = w1
       5:	95 00 00 00 00 00 00 00	exit
