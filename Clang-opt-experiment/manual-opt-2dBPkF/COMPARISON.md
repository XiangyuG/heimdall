# Manual source rewrite versus Clang optimization

This is a temporary comparison of the seven cases in `Clang-opt-experiment`.
Each case directory contains a copy of the original source, a hand rewritten
source, three BPF objects, their `llvm-objdump -d` listings, and the program
formulas exported during self verification.

- `original-no-opt.o`: original source compiled with Clang `-O0`
- `hand-no-opt.o`: hand rewritten source compiled with Clang `-O0`
- `auto-opt.o`: original source compiled with Clang `-O2`

All builds used Clang 22.1.8 with `-target bpf -D__TARGET_ARCH_x86 -g` and the
same include paths as `Clang-opt-experiment/compile.sh`. The executable sections
of `original-no-opt.o` and `auto-opt.o` match the existing `no-opt.o` and
`default.o`, respectively, for every case.

## Compiled program sections

Each cell gives `instructions / conditional jumps`.

| Case | Original `-O0` | Hand `-O0` | Auto `-O2` |
| --- | ---: | ---: | ---: |
| bit-test-add | 50 / 5 | 13 / 0 | 16 / 0 |
| chain-of-updates | 81 / 5 | 21 / 0 | 8 / 0 |
| identical-branches | 70 / 5 | 11 / 0 | 3 / 0 |
| implied-range-tests | 44 / 5 | 19 / 1 | 6 / 1 |
| impossible-bit-tests | 51 / 5 | 9 / 0 | 2 / 0 |
| overwritten-conditional-updates | 50 / 5 | 11 / 0 | 3 / 0 |
| repeated-condition | 52 / 5 | 14 / 0 | 7 / 1 |

The hand rewrite removes branches without relying on `-O2`. The hand object is
usually longer because `-O0` retains stack loads and stores. `bit-test-add` is
the exception: its hand mask expression compiles to 13 instructions versus 16
for Clang's `-O2` result. In `repeated-condition`, the hand expression has no
branch while Clang's `-O2` result still has one.

## Heimdall checks

Heimdall reports every original `-O0` versus hand `-O0` pair equivalent when
comparing the full 64-bit BPF return register. Auto `-O2` versus hand `-O0`
passes the same full-register check in four cases. It reports a mismatch in
`chain-of-updates`, `impossible-bit-tests`, and `repeated-condition` because
Clang's `-O2` object leaves different upper 32 bits of `R0`; the entry returns
`int`. A separate Z3 check of the exported program formulas found no lower
32-bit return mismatch in any of the seven cases.

One self-verification run per object took the following wall time in seconds.
These measurements include Python startup and Z3 text export; repeat runs for
stable performance estimates.

| Case | Original `-O0` | Hand `-O0` | Auto `-O2` |
| --- | ---: | ---: | ---: |
| bit-test-add | 2.256 | 0.453 | 0.471 |
| chain-of-updates | 2.311 | 0.472 | 0.437 |
| identical-branches | 2.678 | 0.446 | 0.429 |
| implied-range-tests | 1.111 | 0.575 | 0.519 |
| impossible-bit-tests | 0.690 | 0.443 | 0.430 |
| overwritten-conditional-updates | 2.093 | 0.447 | 0.432 |
| repeated-condition | 0.869 | 0.451 | 0.535 |
