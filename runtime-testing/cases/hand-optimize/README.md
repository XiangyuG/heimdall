# Hand-optimized real eBPF programs

This directory contains five original/optimized pairs: **ten complete C
programs**, derived from `c2rust_translation/c_bpf_programs/libbpf-tools/`.
No exported entry points, maps, filters, or helper calls are removed.

[Measured results and source links](REPORT.md) ·
[Comparison graph](runtime-comparison.png) · [Raw summary](summary.json)

These top-level result files summarize the recorded run named in `REPORT.md`.
Re-running the benchmark creates a separate timestamped result directory.

For the separate 100-trial stability investigation, see
[the fixed sequential protocol](PROTOCOL_100.md) and
[`benchmark_100_trials.py`](benchmark_100_trials.py). It requires one case per
invocation, prevents overlapping runs, and preserves interrupted attempts.

The completed 100-trial study is documented in
[the combined stability report](results-100/20261102T101430Z/SUMMARY_100.md),
with [the comparison graph](results-100/20261102T101430Z/runtime-comparison-100.png)
and [the call/source audit](results-100/20261102T101430Z/audit.json).
Each case also has Luna's `AGENT_NOTES.md`, raw calls, and a full timing chart.

| Program | Timed entry |
| --- | --- |
| `tcpsynbl` | `tcp_v4_syn_recv_kprobe` |
| `funclatency` | `dummy_kretprobe` |
| `fsdist` | `file_read_exit` |
| `biostacks` | `blk_account_io_done` |
| `biolatency` | `block_rq_complete_btf` |

Each `<name>.original.bpf.c` has a corresponding
`<name>.optimized.bpf.c`. Both files are independent translation units and
can use the existing headers in `runtime-testing/include/`.

## Rewrite

All five programs compute logarithmic histogram buckets. The original
`log2l` splits into high/low words and performs comparison-dependent shifts.
Clang's eBPF output contains conditional jumps for those comparisons, which
cause Heimdall's symbolic execution to explore multiple paths.

The optimized helper performs the same binary search with unsigned carry bits
instead of comparisons. For example, after reducing `v` to 32 bits,
`(v + 0xffff0000ULL) >> 32` is one exactly when `v >= 65536`. This selects
the 16-bit shift using arithmetic. The same technique selects the 8-, 4-,
and 2-bit shifts. Every shift amount is in range, and the additions fit in
64 bits. Both implementations return zero for an input of zero.

The returned bucket, the existing maximum-bucket clamp, and all subsequent
map/global updates stay the same. This is a single additional optimization
pattern demonstrated on five distinct real programs. It does not use loop
fusion, alignment annotations, or cached configuration/bounds.

The original `bits.bpf.h` is inlined into each original source so its exact
implementation is preserved. The optimized copy replaces only its logarithm
helpers. `tcpsynbl` also omits an unused `bpf_endian.h` include in **both**
copies because that header is absent locally; this source uses no endian
macros. `manifest.json` records source provenance and baseline hashes.

## Reproduce

From the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 ~/miniconda3/envs/c2rust/bin/python -B \
  runtime-testing/cases/hand-optimize/benchmark.py
```

To run one pair, add `--case tcpsynbl` (or another name in the table).
Set `BPF_CLANG` to select another compiler. The default is the Homebrew LLVM
Clang used by the existing experiments.

The procedure is fixed in advance:

1. Compile both full programs with identical `-target bpfel -O2 -g
   -D__TARGET_ARCH_x86` flags and header paths.
2. Verify the original against the optimized object with Heimdall at the
   selected timed entry. No witness, restricted inputs, or reduced output
   observations are supplied.
3. Run one warm-up per variant, then **five alternating trials** of original
   self-equivalence and optimized self-equivalence. Each call runs in a fresh
   process. Only `run_verification` is timed; compilation, Python startup,
   module imports, and chart generation are excluded.
4. Verify original-to-optimized equivalence for **every remaining exported
   entry point**. Nonempty unfinished/error stashes invalidate a proof.
5. Save raw timings, proof results, compiler commands, compiled objects,
   full verification logs, and before/after bar graphs in a new `results/`
   directory. Failures, timeouts, and regressions are retained.

Each verification call has the same 120-second process limit. A timeout is
a failure, not a successful proof or a zero-duration sample. The runner uses
Heimdall's existing default helper-failure mode (`off`) for both variants.
The verifier and its input/observation semantics are not modified.

The chart shows medians and individual trials, with a separate zero-based
seconds axis for each program. These are **selected-entry self-equivalence
verification times**, not eBPF execution times or C-to-Rust translation
times. Whole-program equivalence results cover every exported entry under
Heimdall's model. Linux kernel verifier acceptance is a separate check and
is not tested here.

`latest-run.json` identifies the most recent run. Its `results.json` records
all measurements; `runtime-comparison.png` and `.svg` show the comparison.
