# Branch-reduction experiment

Six complete libbpf-tools C programs compare one source-level branch rewrite each: `bashreadline`, `tcptracer`, `bitesize`, `cpufreq`, `biotop`, and `capable`. Each original and optimized pair is a separate full translation unit. The baseline source hash, exact rewrite, build preparation, compiler flags, fixed verification protocol, and selected entry are in [`manifest.json`](manifest.json).

[Results and interpretation](REPORT.md) · [Graph](runtime-comparison.png) · [Raw summary](summary.json)

Run from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 ~/miniconda3/envs/c2rust/bin/python -B runtime-testing/cases/hand-optimize/branch-reduction/benchmark.py
```

The runner creates a new timestamped results directory and records compiler commands, objects, source and executable hashes, per-call proof logs, five alternating selected-entry self-equivalence trials with one warmup per variant, and cross-equivalence checks for every exported entry. All calls have a 120-second process timeout. Failed proofs, incomplete stashes, timeouts, and failed trials remain visible in the recorded results and graph. The graph plots medians and individual successful trial times; failures are labeled, never plotted as zero. This measures Heimdall verification time, not eBPF execution time.

## Program pairs

| Program | Original | Optimized |
| --- | --- | --- |
| bashreadline | [source](bashreadline.original.bpf.c) | [source](bashreadline.optimized.bpf.c) |
| tcptracer | [source](tcptracer.original.bpf.c) | [source](tcptracer.optimized.bpf.c) |
| bitesize | [source](bitesize.original.bpf.c) | [source](bitesize.optimized.bpf.c) |
| cpufreq | [source](cpufreq.original.bpf.c) | [source](cpufreq.optimized.bpf.c) |
| biotop | [source](biotop.original.bpf.c) | [source](biotop.optimized.bpf.c) |
| capable | [source](capable.original.bpf.c) | [source](capable.optimized.bpf.c) |
