# Five more carry-log2 branch-reduction cases

This experiment applies the **same** carry-based `log2l`/`log2` rewrite used in the earlier `tcpsynbl` case to five additional complete C eBPF programs: `softirqs`, `cpudist`, `futexctn`, `hardiqs`, and `runqlat`. It does not test five distinct optimization techniques. Each baseline inlines the unchanged `runtime-testing/include/bits.bpf.h`; each optimized copy replaces only those two functions. The program body, globals, maps, helpers, and exported entries are preserved. Source hashes, exact compiler flags, and the fixed protocol are in [manifest.json](manifest.json).

Run from the `heimdall` repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 ~/miniconda3/envs/c2rust/bin/python -B runtime-testing/cases/hand-optimize/more-candidates/benchmark.py
```

The runner builds both full objects, checks selected-entry original-to-optimized equivalence, runs one warmup per variant, then five alternating self-equivalence trials per variant in fresh processes. It checks every remaining exported entry afterward. Each verifier call has a 120-second timeout. The timer surrounds `run_verification`; compilation and process startup are excluded. Failed proofs, timeouts, incomplete symbolic states, and failed trials remain in the raw records. This measures Heimdall verification time, not BPF execution speed or Linux kernel verifier acceptance.

[Results](REPORT.md) · [Graph](runtime-comparison.png) · [Raw run](results/20261102T111111Z) · [Manifest](manifest.json)
