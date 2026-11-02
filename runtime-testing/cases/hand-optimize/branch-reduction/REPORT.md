# Branch-reduction benchmark results

Six full C eBPF program pairs were compiled and checked under the fixed protocol in [`manifest.json`](manifest.json). The raw run is [`results/20261102T104828Z`](results/20261102T104828Z); its `results.json`, build logs and objects, individual proof logs, and trial records remain available. [Graph](runtime-comparison.png) · [SVG](runtime-comparison.svg) · [Raw summary](summary.json).

| Program | Timed entry | Original median (s) | Optimized median (s) | Time reduction | Conditional jumps (whole object) | Cross proofs passed |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| bashreadline | `printret` | 0.791 | 0.571 | +27.8% | 6 → 2 | 1/1 |
| tcptracer | `entry_trace_close` | 3.926 | 5.391 | -37.3% | 70 → 69 | 7/7 |
| bitesize | `block_rq_issue` | 1.350 | 1.431 | -5.9% | 15 → 14 | 1/1 |
| cpufreq | `do_sample` | 1.451 | 1.856 | -27.9% | 17 → 16 | 2/2 |
| biotop | `blk_account_io_done` | 3.989 | 2.997 | +24.9% | 36 → 33 | 7/7 |
| capable | `kprobe__cap_capable_exit` | 1.039 | 1.092 | -5.1% | 14 → 14 | 2/2 |

Positive time reduction means faster verification. Medians are five alternating selected-entry **self-equivalence** trials; each variant has one preceding warmup. The cross-equivalence proof time is a separate observation and is never mixed into medians. Each verification call uses a fresh subprocess with a 120-second limit, and timing encloses only `run_verification`. All exported entries were checked for original-to-optimized equivalence with unchanged inputs, observations, and helper-failure mode. All 20 cross-entry proofs passed without unfinished or errored stashes; no timeout or counterexample occurred in this run.

The result does not support a general claim that fewer conditional jumps speed Heimdall. `bashreadline` gained 27.8% and `biotop` gained 24.9%, while `tcptracer` slowed 37.3%, `cpufreq` slowed 27.9%, and `bitesize` slowed 5.9%. The `capable` original and optimized executable sections have identical SHA-256 hashes and 14 conditional jumps in each; its 5.1% median difference is run variation rather than an effect of the source rewrite. The whole-object jump counts include every exported entry, so a small change in that count does not isolate the timed entry's path cost. The five trials do not establish statistical stability.

The `tcptracer` source uses `bpf_ntohs`; the local `bpf_endian.h` was unavailable, so both variants replace its include with `__builtin_bswap16` for this little-endian BPF target. The `bitesize` sources inline the unchanged `runtime-testing/include/bits.bpf.h` in both variants. `capable` retains its kernel-version branch. Provenance and source hashes are in the manifest and run results. These are Heimdall model proofs and verifier runtimes; Linux kernel verifier acceptance and eBPF execution speed were not measured.
