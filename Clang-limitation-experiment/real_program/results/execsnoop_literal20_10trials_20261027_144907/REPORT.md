# execsnoop: original vs literal bound 20

Ten alternating timed trials per version after one warmup per version. Timing uses the existing benchmark_helpers.verify_pair and verify_equivalence.run_verification, excluding imports, compilation, garbage collection and log writes. Both new objects use identical Clang -O2 flags. The configured timeout remains 60 seconds; it is an alarm, not assumed to be a strict wall-time cap. No failed trial is replaced and no outlier is removed. This comparison is original versus literal 20, not cached max_args versus literal 20.

The only C source edit replaces `i < TOTAL_MAX_ARGS && i < max_args` with `i < 20`; the loop body and #pragma unroll are preserved. The source and ELF initializer for max_args are checked to equal 20. This is configuration specialization: equivalence requires max_args = 20, and does not cover loader overrides to other values. No extra verifier witness or input constraints are introduced. An equivalence check in this model does not prove that external loader contract.

| Version | Successful attempts | Median seconds | Sample SD seconds | BPF instruction slots (all executable sections) |
|---|---:|---:|---:|---:|
| Original | 10/10 | 23.42241233351524 | 1.1998405383407242 | 1807 |
| Literal bound 20 | 10/10 | 21.409692396002356 | 1.1597263696013203 | 612 |

Successful-run median reduction: 8.59% (negative means slower). Speedup ratio: 1.094x.
Paired bootstrap 95% interval for median reduction (10,000 resamples): [0.7860717158524544, 11.734355161803133]. Ten pairs are a small sample; this interval does not establish stationarity or independent timing observations.

Started 2026-10-27T21:49:44.088412+00:00; finished 2026-10-27T21:58:25.430501+00:00. Full compiler invocation, hashes, preparation results and raw errors are saved in checkpoint.json. Existing sources, binaries and prior results are unchanged.
