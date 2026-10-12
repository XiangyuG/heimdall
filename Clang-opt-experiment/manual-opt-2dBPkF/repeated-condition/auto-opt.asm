
/Users/dajohnyu/Documents/heimdall/heimdall/Clang-opt-experiment/manual-opt-2dBPkF/repeated-condition/auto-opt.o:	file format elf64-bpf

Disassembly of section fentry/blk_account_io_done:

0000000000000000 <blk_account_io_done>:
       0:	79 10 00 00 00 00 00 00	r0 = *(u64 *)(r1 + 0x0)
       1:	bf 01 00 00 00 00 00 00	r1 = r0
       2:	57 01 00 00 01 00 00 00	r1 &= 0x1
       3:	15 01 02 00 00 00 00 00	if r1 == 0x0 goto +0x2 <blk_account_io_done+0x30>
       4:	0c 10 00 00 00 00 00 00	w0 += w1
       5:	04 00 00 00 0e 00 00 00	w0 += 0xe
       6:	95 00 00 00 00 00 00 00	exit
