# funclatency run notes

Command used from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/dajohnyu/miniconda3/envs/c2rust/bin/python -B /Users/dajohnyu/Documents/heimdall/heimdall/runtime-testing/cases/hand-optimize/benchmark_100_trials.py --case funclatency --run-dir /Users/dajohnyu/Documents/heimdall/heimdall/runtime-testing/cases/hand-optimize/results-100/20261102T101430Z/funclatency
```

Controller exit status: **0**. The run is complete: 100/100 original observations, 100/100 optimized observations, 100 complete pairs, and zero failed, timed-out, or interrupted calls. All four exported-entry equivalence proofs passed. No observations were removed or replaced.

| Variant | Median s | Mean s | SD s | CV | p05–p95 s | Min–max s | First 25 median s | Last 25 median s | Last vs first |
| --- | ---: | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: |
| Original | 5.352412 | 5.666222 | 0.730837 | 12.90% | 5.046050–7.241064 | 4.920738–7.977148 | 6.585516 | 5.262266 | −20.09% |
| Optimized | 1.447933 | 1.533358 | 0.217376 | 14.18% | 1.355796–1.950678 | 1.319866–2.473108 | 1.616961 | 1.453285 | −10.12% |

The optimized median is 72.95% lower than the original median. The paired-bootstrap 95% interval for median reduction is 72.37%–73.63%, based on all 100 complete pairs and the protocol's 10,000 resamples. This supports a repeatable before/after benefit for this selected-entry self-equivalence workload.

Both series start substantially slower and settle lower after the early rounds. The first-25 to last-25 median changes are −20.09% original and −10.12% optimized; the ten-round block medians show the original moving from 7.204 s in rounds 1–10 to a band mostly around 5.1–5.6 s in later blocks, while optimized moves from 1.903 s to roughly 1.4–1.5 s. CVs are 12.90% and 14.18%. The chart also shows retained high observations, including original 7.977 s at round 26 and optimized 2.473 s at round 78. The early shift means absolute timing stationarity across all 100 rounds is not established, although the later portion is comparatively steady. The median reduction remains clear across the paired set.

Proofs passed: `dummy_kretprobe`, `dummy_fentry`, `dummy_kprobe`, and `dummy_fexit`.

Artifacts: [REPORT.md](REPORT.md), [summary.json](summary.json), [protocol.json](protocol.json), [stability.png](stability.png), [call journal](journal.jsonl), [controller log](../funclatency.controller.log).
