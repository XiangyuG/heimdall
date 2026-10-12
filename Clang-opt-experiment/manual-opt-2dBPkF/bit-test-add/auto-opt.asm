
/Users/dajohnyu/Documents/heimdall/heimdall/Clang-opt-experiment/manual-opt-2dBPkF/bit-test-add/auto-opt.o:	file format elf64-bpf

Disassembly of section fentry/blk_account_io_done:

0000000000000000 <blk_account_io_done>:
       0:	79 11 00 00 00 00 00 00	r1 = *(u64 *)(r1 + 0x0)
       1:	bc 10 00 00 00 00 00 00	w0 = w1
       2:	54 00 00 00 01 00 00 00	w0 &= 0x1
       3:	0c 10 00 00 00 00 00 00	w0 += w1
       4:	bc 12 00 00 00 00 00 00	w2 = w1
       5:	54 02 00 00 02 00 00 00	w2 &= 0x2
       6:	0c 20 00 00 00 00 00 00	w0 += w2
       7:	bc 12 00 00 00 00 00 00	w2 = w1
       8:	54 02 00 00 04 00 00 00	w2 &= 0x4
       9:	0c 20 00 00 00 00 00 00	w0 += w2
      10:	bc 12 00 00 00 00 00 00	w2 = w1
      11:	54 02 00 00 08 00 00 00	w2 &= 0x8
      12:	0c 20 00 00 00 00 00 00	w0 += w2
      13:	54 01 00 00 10 00 00 00	w1 &= 0x10
      14:	0c 10 00 00 00 00 00 00	w0 += w1
      15:	95 00 00 00 00 00 00 00	exit
