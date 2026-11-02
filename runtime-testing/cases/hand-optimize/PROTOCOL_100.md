# 100-trial stability protocol

The permanent runner is `benchmark_100_trials.py`. It accepts **one required
case**, never a suite of cases. The five cases are dispatched to Luna one at
a time in this order: `tcpsynbl`, `funclatency`, `fsdist`, `biostacks`,
`biolatency`. The current case must exit and write its report before the next
case starts. A kernel file lock also rejects concurrent runs of this runner.

## Fixed experiment

- **100 paired rounds per case: 100 original and 100 optimized calls.**
- Odd rounds run original first; even rounds run optimized first. Each variant
  runs first exactly 50 times. Calls execute serially in fresh Python processes.
- One untimed warm-up for each variant; selected-entry original-to-optimized
  equivalence before timing and all remaining exported-entry proofs afterward.
- Reuse the existing five-trial benchmark's worker without changes. Time only
  the complete `run_verification` call; exclude imports, interpreter startup,
  compilation, reporting, and chart generation.
- Compile with the same `bpfel`, `-O2`, debug, architecture, and header flags.
  Keep all ten C sources, the verifier, input assumptions, observations, and
  default helper-failure mode (`off`) unchanged.
- Keep the existing **120-second process wall-time limit**. A timeout is a
  recorded failure, not an equivalent result, zero-time sample, or replacement
  opportunity. Do not change the limit, workload, inputs, flags, or method
  after inspecting results.
- Retain every completed sample, including outliers and slowdowns. Record
  every timeout, failed proof, worker failure, and interrupted attempted slot.
  No trimming, winsorizing, hidden retries, or substituted samples.

## Durability and resuming

An attempt marker is persisted before each verification process starts. The
per-call result, append-only `journal.jsonl`, and per-pair `progress.json`
checkpoint are flushed to disk. A resumed run uses completed results as-is.
An attempted slot with no result is recorded as interrupted and is **not
rerun**. That run consequently cannot be called a successful 100/100 result.

Compiler/dependency versions and hashes of sources, headers, runners, verifier,
and backend Python files are frozen in `protocol.json`. Resume is refused if
those fingerprints change. The lock spans compilation, timing, entry-point
proofs, and documentation. The Luna agent must also wait for the process to
exit and verify the report before declaring its case finished.

```sh
PYTHONDONTWRITEBYTECODE=1 ~/miniconda3/envs/c2rust/bin/python -B \
  runtime-testing/cases/hand-optimize/benchmark_100_trials.py \
  --case tcpsynbl --run-dir /absolute/path/to/new-run/tcpsynbl
```

For an interrupted controller, use the **same case and directory** and add
`--resume`. This continues the fixed schedule while retaining interrupted
slots as failures; it does not manufacture a new complete sample set.

## Reporting

Each case produces `REPORT.md`, `summary.json`, `stability.png`/`.svg`, build
commands/objects, and per-call proof logs and JSON. The report includes:

- Successful and failed counts, with failed round numbers.
- Median, mean, standard deviation, CV, min/max, p05/p95, IQR, and MAD.
- First/last-25 medians, ten-round block medians, and per-trial trend charts.
- Median runtime reduction and a paired-bootstrap 95% interval, using 10,000
  resamples of whole pairs with fixed seed 984.
- Original-to-optimized proof status for every exported entry point.

Statistics describe successful calls only, with their counts explicit. The
paired interval uses complete pairs only, also with its count explicit. Any
failed/interrupted/timeout call makes the case **incomplete**, even if most
calls finish. A confidence interval above zero supports a runtime reduction;
it does not establish that either timing series is stationary. CV, quantiles,
and trends must be examined separately when discussing stability.

These remain selected-entry self-equivalence timings, not eBPF execution or
C-to-Rust translation times. Earlier five-trial artifacts are preserved.

`latest-100-run.json` identifies the sequential session; its `session.json`
tracks case dispatch and documentation. Luna adds `AGENT_NOTES.md` per case
with an honest reading of variation, drift, failures, and the saved artifacts.

## Completed study

The [combined report](results-100/20261102T101430Z/SUMMARY_100.md) contains the
five completed results and links to Luna's per-case notes. To reproduce its
audit, summary, and figure from the saved observations without running any
verification calls:

```sh
PYTHONDONTWRITEBYTECODE=1 ~/miniconda3/envs/c2rust/bin/python -B \
  runtime-testing/cases/hand-optimize/summarize_100_trials.py \
  runtime-testing/cases/hand-optimize/results-100/20261102T101430Z
```

That reporter includes interpretations specific to this completed study.
For new benchmark trials, use `benchmark_100_trials.py` with a new run
directory, one case at a time.
