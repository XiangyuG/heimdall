# fsdist run notes

Command used from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/dajohnyu/miniconda3/envs/c2rust/bin/python -B /Users/dajohnyu/Documents/heimdall/heimdall/runtime-testing/cases/hand-optimize/benchmark_100_trials.py --case fsdist --run-dir /Users/dajohnyu/Documents/heimdall/heimdall/runtime-testing/cases/hand-optimize/results-100/20261102T101430Z/fsdist
```

Controller exit status: **0**. The run is complete: 100/100 original observations, 100/100 optimized observations, 100 complete pairs, and zero failed, timed-out, or interrupted calls. All 20 exported-entry equivalence proofs passed. No observations were removed or replaced.

| Variant | Median s | Mean s | SD s | CV | p05–p95 s | Min–max s | First 25 median s | Last 25 median s | Last vs first |
| --- | ---: | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: |
| Original | 22.200431 | 22.406493 | 2.176759 | 9.71% | 18.803161–26.297254 | 16.974913–29.774034 | 21.766957 | 21.993864 | +1.04% |
| Optimized | 2.190338 | 2.224352 | 0.302657 | 13.61% | 1.794546–2.802661 | 1.660408–3.724156 | 2.055008 | 2.168511 | +5.52% |

The optimized median is 90.13% lower than the original median. The paired-bootstrap 95% interval for median reduction is 90.01%–90.23%, based on all 100 complete pairs and the protocol's 10,000 resamples. This supports a strong repeatable before/after benefit for this selected-entry self-equivalence workload.

The full timing sequences are not stationary. The original series steps from roughly 17–20 seconds in the first ten rounds to mostly 22 seconds or higher from round 11 onward; it also has elevated clusters around rounds 35–40 and 71–74. The optimized series rises from roughly 1.7–1.9 seconds early to a later band near 2.1–2.4 seconds, with spikes around rounds 35–36 and 71–73. First-to-last-25 medians change by +1.04% original and +5.52% optimized, which hides these earlier level shifts. CV is 9.71% original and 13.61% optimized. The largest retained observations are 29.774 s original at round 56 and 3.724 s optimized at round 72. The late portions are comparatively steady, but stationarity across the full run is not supported by the chart and block medians.

Proofs passed: `file_read_exit`, `file_read_entry`, `file_write_entry`, `file_write_exit`, `file_open_entry`, `file_open_exit`, `file_sync_entry`, `file_sync_exit`, `getattr_entry`, `getattr_exit`, `file_read_fentry`, `file_read_fexit`, `file_write_fentry`, `file_write_fexit`, `file_open_fentry`, `file_open_fexit`, `file_sync_fentry`, `file_sync_fexit`, `getattr_fentry`, and `getattr_fexit`.

Artifacts: [REPORT.md](REPORT.md), [summary.json](summary.json), [protocol.json](protocol.json), [stability.png](stability.png), [call journal](journal.jsonl), [controller log](../fsdist.controller.log).
