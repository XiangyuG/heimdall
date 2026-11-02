# execsnoop_bound only: 100 attempts per version

Timing uses the existing benchmark helper and verify_equivalence.run_verification() in the c2rust conda environment. Imports, compilation, garbage collection and log writes are outside the timed interval. Each case uses the same existing -O2 objects, selected entry, inputs, success-only helper model and configured 60-second alarm as the earlier experiment. Each version receives one warm-up, followed by 100 timed attempts. Execution is serial and pair order alternates. No outliers are trimmed and failed attempts are not replaced.

| Case | Successful original / optimized trials | Successful-run median seconds original to optimized | Successful-run time reduction | Paired bootstrap 95% interval |
|---|---:|---:|---:|---:|
| execsnoop_bound | 94/100 and 99/100 | 27.4777 to 23.5301 | 14.37% | not computed |

The intervals use 10,000 paired bootstrap resamples of the median time ratio. They summarize this run and do not establish independence of trials or transferability to other system loads. JSON also records means, standard deviations, quartiles and ranges. Bar heights are successful-run medians; individual charts overlay every successful trial. ECDF and box plots retain outliers. Any failures/timeouts are listed in results.json and raw_trials.csv. No completion time is assigned to a failed attempt; successful-run reductions do not estimate the full sample when timeouts occur.

The execsnoop bound rewrite requires configuration frozen during each invocation and excludes individual volatile-read traces from observations. Functional equivalence checks do not prove that external contract. These are selected-entry self-equivalence workloads, not program execution times or C-to-Rust verification. Saved five-trial results remain unchanged.

## Process isolation and interpretation

This experiment runs only execsnoop_bound in one fresh Python process, persistent within the case. The earlier data, object files, timing helper, selected entries, timeout setting, warmups and alternating order are preserved. The previous sequential experiment also used a fresh process for this case; this run isolates it as the entire experiment and does not claim to fix the source of timing drift.

Started: 2026-10-27T06:59:13.326663+00:00. Finished: 2026-10-27T08:55:08.231114+00:00. This run contains only execsnoop_bound, in one fresh Python process; no other benchmark case is launched.

- execsnoop_bound: 94/100 original and 99/100 optimized attempts reported successful; 7 failed attempts.  Failures limit interpretation: successful-run reductions do not establish overall speedup.

Recorded attempts: 200/200; successful: 193; failed: 7. Raw failure statuses and error text are preserved. Wrapped TimeoutError exceptions may retain status 'failed'. No failed attempt was replaced, no outlier trimmed, and no timeout result imputed.

The configured 60-second SIGALRM uses the existing helper and is not assumed to be a strict wall-time cap. Inspect raw timestamps for gaps and graphs for retained outliers; do not infer an uninterrupted stable environment merely from process isolation.

Figures: global-runtime.png (eight absolute-time bars), global-relative-runtime.png (eight normalized bars), global-distributions.png (successful runtimes), global-completions.png (successful counts), per-case runtime.png and distribution.png; SVG copies included.

## Standalone audit

The standalone experiment recorded all 200 scheduled attempts with unchanged original and optimized object hashes. Six original and one optimized attempt timed out. No failures were retried and no successful observations were removed.

| Version | Successful first-20 median (s) | Successful last-20 median (s) | Timeout trials |
|---|---:|---:|---|
| Original | 16.0032 | 53.9493 | [86, 87, 88, 89, 91, 92] |
| Optimized | 11.6798 | 49.1534 | [91] |

Local run interval: 2026-10-26T23:59:13.326663-07:00 to 2026-10-27T01:55:08.231114-07:00 (America/Los_Angeles).

Runtimes again increased substantially in both versions during the standalone run. The first timeout occurred on original trial 86; optimized trial 91 also timed out. Thus running only this case did not eliminate late-run slowdown. The data show timing drift and timeout-triggered formula-generation errors; they do not diagnose whether the drift originates in retained verifier state, resource pressure, thermal behavior, or another factor. They do not identify token exhaustion as the cause.

All successful times were below 60 seconds in this run, but the unchanged SIGALRM helper is not assumed to enforce a strict wall-time cap in general. No timeout completion time was imputed. Successful-run median reduction is 14.37% (1.168x), conditional on the 94/99 completed attempts; no full-sample confidence interval is reported because attempts failed.

The original-version and optimized-version mean times among completed attempts are 32.5699 s and 29.4564 s; sample standard deviations are 14.5478 s and 15.1295 s. These broad distributions and the trial trend limit interpretation of an aggregate speedup. First/last-20 summaries are diagnostics and do not replace full-sample summaries.

Figures: execsnoop_bound/runtime.png (median bars plus all successful measurements), execsnoop_bound/distribution.png (ECDF), trial-trend.png (timings by trial), and global-completions.png (completion counts). SVG versions are included. Previous experiments remain unchanged.
