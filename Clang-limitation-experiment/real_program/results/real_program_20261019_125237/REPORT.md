# Measured corpus optimizations

Both variants use Clang -O2 and identical headers and inputs. Times are medians of five alternating trials after one warm-up per variant. Each selected entry first passes original-to-optimized equivalence. Timing measures self-equivalence, not C-to-Rust verification. Individual graphs show raw trials as points.

| Program | Optimization | BPF slots before → after | Median seconds before → after | Speedup (original / optimized) |
|---|---|---:|---:|---:|
| `KEN/dataset/libbpf/execsnoop.bpf.c` | Align local event buffer | 44 → 43 | 0.3465 → 0.3138 | 1.104× |
| `KEN/dataset/libbpf/sigsnoop.bpf.c` | Align local event buffer | 67 → 64 | 0.2542 → 0.2430 | 1.046× |
| `ebpf-se/dae/dae_kern.c` | Align local event buffer | 2339 → 2279 | 7.3299 → 7.2284 | 1.014× |
| `libbpf-tools/biosnoop.bpf.c` | Expose hash-map value alignment | 551 → 545 | 1.4841 → 1.5412 | 0.963× |
| `libbpf-tools/capable.bpf.c` | Align event and i_key | 175 → 171 | 0.7703 → 0.7324 | 1.052× |
| `libbpf-tools/execsnoop.bpf.c` | Expose hash-map value alignment | 1807 → 1806 | 16.9260 → 17.0155 | 0.995× |
| `libbpf-tools/mdflush.bpf.c` | Align local event buffer | 126 → 118 | 0.7549 → 0.6426 | 1.175× |
| `libbpf-tools/tcprtt.bpf.c` | Align local key | 490 → 486 | 27.0169 → 23.5133 | 1.149× |
| `libbpf-tools/execsnoop.bpf.c` | Cache max_args (conditional) | 1807 → 192 | 19.6543 → 15.5661 | 1.263× |
| `libbpf-tools/tcpconnect.bpf.c` | Cache filter_ports_len (conditional) | 393 → 381 | 1.3124 → 1.3262 | 0.990× |

Conditional bound caching requires loader-frozen configuration during an invocation and excludes volatile-read traces from observations. The verifier's functional model does not establish that external contract.

Map-pointer alignment annotations rely on the relevant hash-map allocator's eight-byte value alignment. Equivalence results cover the recorded entry and verifier model, not every entry or Linux kernel verifier acceptance.

Timeouts and failed/unmeasured cases are excluded from the table and graphs; any such outcome remains recorded in results.json and its log. Small differences and speedups below 1× are retained. No benchmark inputs or verifier semantics are changed.
