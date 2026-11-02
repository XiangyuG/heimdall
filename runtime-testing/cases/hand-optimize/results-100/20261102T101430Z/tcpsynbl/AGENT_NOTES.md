# tcpsynbl run notes

Command used from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/dajohnyu/miniconda3/envs/c2rust/bin/python -B /Users/dajohnyu/Documents/heimdall/heimdall/runtime-testing/cases/hand-optimize/benchmark_100_trials.py --case tcpsynbl --run-dir /Users/dajohnyu/Documents/heimdall/heimdall/runtime-testing/cases/hand-optimize/results-100/20261102T101430Z/tcpsynbl
```

Controller exit status: **0**. The run is complete: 100/100 original observations, 100/100 optimized observations, 100 complete pairs, and zero failed, timed-out, or interrupted calls. All four exported-entry equivalence proofs passed. No observations were removed or replaced.

| Variant | Median s | Mean s | SD s | CV | p05–p95 s | Min–max s | First 25 median s | Last 25 median s | Last vs first |
| --- | ---: | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: |
| Original | 9.532666 | 9.867794 | 1.168757 | 11.84% | 8.676424–12.418151 | 8.397213–14.196546 | 9.441845 | 10.003088 | +5.94% |
| Optimized | 1.715769 | 1.809761 | 0.440659 | 24.35% | 1.567804–2.326323 | 1.529098–5.613332 | 1.709805 | 1.812972 | +6.03% |

The optimized median is 82.00% lower than the original median. The paired-bootstrap 95% interval for median reduction is 81.73%–82.21%, based on all 100 complete pairs and the protocol's 10,000 resamples. This is strong evidence of a repeatable before/after performance benefit for this selected-entry self-equivalence workload.

The timing series are not especially stable over the full run. Both last-25 medians are about 6% above their first-25 medians, and the last ten-round block rises to 12.086 s original / 2.236 s optimized from earlier block medians mostly around 8.7–10.1 s / 1.63–1.80 s. The optimized CV is 24.35%; its maximum, 5.613 s at round 95, is a retained outlier. Original also has a pronounced late rise, reaching 14.197 s at round 100. The chart shows this tail movement and the optimized round-95 spike. Thus the reduction is repeatable across paired observations, while absolute timing stationarity is not established and the later timing environment appears slower.

Proofs passed: `tcp_v4_syn_recv_kprobe`, `tcp_v6_syn_recv_kprobe`, `tcp_v4_syn_recv`, and `tcp_v6_syn_recv`.

Artifacts: [REPORT.md](REPORT.md), [summary.json](summary.json), [protocol.json](protocol.json), [stability.png](stability.png), [call journal](journal.jsonl), [controller log](../tcpsynbl.controller.log).
