
/Users/dajohnyu/Documents/heimdall/heimdall/Clang-opt-experiment/manual-opt-2dBPkF/identical-branches/auto-opt.o:	file format elf64-bpf

Disassembly of section fentry/blk_account_io_done:

0000000000000000 <blk_account_io_done>:
       0:	79 10 00 00 00 00 00 00	r0 = *(u64 *)(r1 + 0x0)
       1:	04 00 00 00 0f 00 00 00	w0 += 0xf
       2:	95 00 00 00 00 00 00 00	exit
