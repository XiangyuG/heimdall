# biostacks run notes

Command used from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/dajohnyu/miniconda3/envs/c2rust/bin/python -B /Users/dajohnyu/Documents/heimdall/heimdall/runtime-testing/cases/hand-optimize/benchmark_100_trials.py --case biostacks --run-dir /Users/dajohnyu/Documents/heimdall/heimdall/runtime-testing/cases/hand-optimize/results-100/20261102T101430Z/biostacks
```

Controller exit status: **0**. The run is complete: 100/100 original observations, 100/100 optimized observations, 100 complete pairs, and zero failed, timed-out, or interrupted calls. All five exported-entry equivalence proofs passed. No observations were removed or replaced.

| Variant | Median s | Mean s | SD s | CV | p05–p95 s | Min–max s | First 25 median s | Last 25 median s | Last vs first |
| --- | ---: | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: |
| Original | 58.260161 | 58.523599 | 2.986200 | 5.10% | 53.920804–63.510454 | 51.287588–66.145736 | 58.922160 | 59.771231 | +1.44% |
| Optimized | 3.263544 | 3.282625 | 0.150445 | 4.58% | 3.101266–3.512891 | 3.003125–4.054261 | 3.274563 | 3.214395 | −1.84% |

The optimized median is 94.40% lower than the original median. The paired-bootstrap 95% interval for median reduction is 94.32%–94.52%, based on all 100 complete pairs and the protocol's 10,000 resamples. This supports a clear repeatable before/after benefit for this selected-entry self-equivalence workload.

Absolute timings show moderate variation but no clear directional drift across the 100 paired rounds. The first-to-last-25 medians differ by +1.44% original and −1.84% optimized; ten-round medians remain broadly similar throughout. CV is 5.10% original and 4.58% optimized. The observations include retained high values: 66.146 s original at round 1 and 4.054 s optimized at round 20. The chart shows these points while the rest of both series stays in relatively narrow bands. This is consistent with comparatively stable timings over this run, while not proving that timing is stationary beyond the observed conditions.

Proofs passed: `blk_account_io_done`, `blk_account_io_merge_bio`, `blk_account_io_start`, `block_io_start`, and `block_io_done`.

Artifacts: [REPORT.md](REPORT.md), [summary.json](summary.json), [protocol.json](protocol.json), [stability.png](stability.png), [call journal](journal.jsonl), [controller log](../biostacks.controller.log).
