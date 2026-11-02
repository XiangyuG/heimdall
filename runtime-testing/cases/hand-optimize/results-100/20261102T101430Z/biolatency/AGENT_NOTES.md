# biolatency run notes

Command used from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/dajohnyu/miniconda3/envs/c2rust/bin/python -B /Users/dajohnyu/Documents/heimdall/heimdall/runtime-testing/cases/hand-optimize/benchmark_100_trials.py --case biolatency --run-dir /Users/dajohnyu/Documents/heimdall/heimdall/runtime-testing/cases/hand-optimize/results-100/20261102T101430Z/biolatency
```

Controller exit status: **0**. The run is complete: 100/100 original observations, 100/100 optimized observations, 100 complete pairs, and zero failed, timed-out, or interrupted calls. All six exported-entry equivalence proofs passed. No observations were removed or replaced.

| Variant | Median s | Mean s | SD s | CV | p05–p95 s | Min–max s | First 25 median s | Last 25 median s | Last vs first |
| --- | ---: | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: |
| Original | 38.453197 | 39.949930 | 4.292589 | 10.74% | 36.141334–48.731554 | 35.914915–58.679487 | 37.450586 | 40.887937 | +9.18% |
| Optimized | 3.213723 | 3.254158 | 0.218724 | 6.72% | 2.990725–3.666857 | 2.933897–4.153589 | 3.083644 | 3.324203 | +7.80% |

The optimized median is 91.64% lower than the original median. The paired-bootstrap 95% interval for median reduction is 91.48%–91.84%, based on all 100 complete pairs and the protocol's 10,000 resamples. This supports a repeatable before/after benefit for this selected-entry self-equivalence workload.

Absolute timings vary and show some drift. The last-25 medians are 9.18% higher for original and 7.80% higher for optimized than their first-25 medians. Much of the original variation comes from a slow cluster around rounds 34–43: the rounds 31–40 block median is 47.569 s, while most other block medians are roughly 36.6–41.6 s. The optimized series has a smaller elevated patch in the same region. The largest retained samples are 58.679 s original at round 43 and 4.154 s optimized at round 38. CV is 10.74% original and 6.72% optimized. The chart supports an episodic slowdown and later upward median shift, so absolute stationarity is not established, despite the clear paired performance reduction.

Proofs passed: `block_rq_complete_btf`, `block_rq_insert_btf`, `block_rq_issue_btf`, `block_rq_insert`, `block_rq_issue`, and `block_rq_complete`.

Artifacts: [REPORT.md](REPORT.md), [summary.json](summary.json), [protocol.json](protocol.json), [stability.png](stability.png), [call journal](journal.jsonl), [controller log](../biolatency.controller.log).
