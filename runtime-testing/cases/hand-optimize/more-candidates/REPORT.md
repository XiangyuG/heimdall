# Five more carry-log2 cases: measured results

Five complete C eBPF program pairs were compiled and run under the fixed protocol in [manifest.json](manifest.json). All five use **the same** carry-based `log2l`/`log2` rewrite previously used for `tcpsynbl`; these are five additional programs, not five new techniques. [Graph](runtime-comparison.png) · [SVG](runtime-comparison.svg) · [Summary](summary.json) · [Raw run](results/20261102T111111Z).

| Program | Timed entry | Conditional jumps, whole object | Cross proofs | Original median (s) | Optimized median (s) | Result |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `softirqs` | `softirq_exit` | 28 → 11 | 2/4 | 0.996 | 1.364 | **Cross proof failed** on both exit entries (`atomic_mismatch`); no valid speedup claim |
| `cpudist` | `sched_switch_tp` | 48 → 30 | 2/2 | 76.194 | 7.500 | **90.2% less verifier time** in five paired trials |
| `futexctn` | `futex_exit` | 28 → 19 | 2/2 | 5/5 timed out | 9.194* | Timing incomplete; no paired percentage |
| `hardiqs` | `irq_handler_exit` | 27 → 22 | 4/4 | 2.028 | 2.122 | **4.6% more verifier time** observed in five paired trials |
| `runqlat` | `handle_sched_switch` | 45 → 40 | 4/6 | 5/5 timed out | 20.059* | Two switch-entry cross proofs timed out; no paired percentage |

\* Median of five successful optimized-only trials, shown for context. All five original trials and the original warmup hit the **120-second subprocess limit** in each of these two cases. Because subprocess time includes startup, the timeout is not an exact `run_verification` duration. No zero-time values were inserted or used in medians.

The `softirqs` failure is reported exactly as the checker produced it: `atomic_mismatch`, with three atomic operations on the original's explored paths and none on the optimized's. The two entry-path proofs passed; both exit-path proofs failed. This result does not establish semantic inequivalence or equivalence. In `runqlat`, the four wakeup-entry proofs passed and both switch-entry proofs timed out, leaving equivalence unresolved on those paths. `futexctn` passed both cross proofs but its original self-equivalence calls did not finish under the limit.

The one complete, large improvement is `cpudist`. `hardiqs`'s 4.6% higher median is an observation from five trials, not a statistical claim about a stable slowdown. Across these cases, fewer conditional jumps do not predict shorter verification time. There were **14 passing cross-entry proofs out of 18**; two failed with `atomic_mismatch`, and two timed out. Every exported entry was attempted. All successful selected-entry self-equivalence trials used five alternating original/optimized calls, with one warmup per variant and a fresh process for each call. The timer enclosed only `run_verification`. The raw result records retain every timeout, proof logs for completed calls, compiler logs, objects, and trial records; timed-out subprocesses have timeout JSON records without completed proof logs. The [graph](runtime-comparison.png) marks incomplete cases and omits percentage claims for them.

Both versions were built with Clang `-target bpfel -O2 -g -D__TARGET_ARCH_x86` and `runtime-testing/include`. The original copies inline that bits header unchanged, and the optimized copies replace only its two log helpers with the earlier carry-based implementation. [Manifest](manifest.json) hashes the upstream sources, both generated full sources, the original bits header, and the exact helper replacement span. Its `carry_helper_sha256` is the hash of the UTF-8 substring from the inlined bits-header SPDX comment through the newline just before `#include "maps.bpf.h"` in `tcpsynbl.optimized.bpf.c`; it is not a hash of that entire file. This span clarification was added to the manifest after the run, without changing source, objects, protocol, or the environment snapshot stored with the raw run.

These are Heimdall model proofs and verifier runtimes. Linux kernel verifier acceptance and eBPF execution speed were not measured.
