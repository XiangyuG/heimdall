# Four real-program comparisons with 100 trials

Timing uses the existing benchmark helper and verify_equivalence.run_verification() in the c2rust conda environment. Imports, compilation, garbage collection and log writes are outside the timed interval. Each case uses the same existing -O2 objects, selected entry, inputs, success-only helper model and 60-second timeout as the earlier experiment. Each version receives one warm-up, followed by 100 timed attempts. Execution is serial and pair order alternates. No outliers are trimmed and failed attempts are not replaced.

| Case | Successful original / optimized trials | Successful-run median seconds original to optimized | Successful-run time reduction | Paired bootstrap 95% interval |
|---|---:|---:|---:|---:|
| ken_execsnoop_alignment | 100/100 and 100/100 | 0.5121 to 0.4984 | 2.67% | -0.75% to 3.84% |
| mdflush_alignment | 100/100 and 100/100 | 1.0370 to 0.9190 | 11.37% | 9.41% to 13.24% |
| tcprtt_alignment | 96/100 and 98/100 | 27.1959 to 27.8187 | -2.29% | not computed |
| execsnoop_bound | 36/100 and 37/100 | 52.3408 to 45.4645 | 13.14% | not computed |

The intervals use 10,000 paired bootstrap resamples of the median time ratio. They summarize this run and do not establish independence of trials or transferability to other system loads. JSON also records means, standard deviations, quartiles and ranges. Bar heights are successful-run medians; individual charts overlay every successful trial. ECDF and box plots retain outliers. Any failures/timeouts are listed in results.json and raw_trials.csv. No completion time is assigned to a failed attempt; successful-run reductions do not estimate the full sample when timeouts occur.

The execsnoop bound rewrite requires configuration frozen during each invocation and excludes individual volatile-read traces from observations. Functional equivalence checks do not prove that external contract. These are selected-entry self-equivalence workloads, not program execution times or C-to-Rust verification. Saved five-trial results remain unchanged.

## Interpretation

- mdflush: the median reduction is 11.37%, with a paired bootstrap interval of 9.41% to 13.24% for this run.
- KEN execsnoop: the observed median reduction is 2.67%, but its interval (-0.75% to 3.84%) includes zero; the run does not establish a clear improvement.
- tcprtt: the successful-run median is 2.29% slower after optimization; 4 original and 2 optimized attempts timed out. This run does not reproduce the earlier speedup.
- execsnoop bound: 64 original and 63 optimized attempts timed out. Its 13.14% reduction is conditional on the 36/37 attempts reported successful by the helper and must not be claimed as an overall speedup. With more than half the attempts failing in each version, the full-sample median completion time cannot be estimated from the successful subset.

The run began at 2026-10-20T23:08:27.306033+00:00 and finished at 2026-10-22T11:26:54.123147+00:00. Timestamps contain substantial gaps between some attempts. Their cause was not diagnosed, and this multi-day run must not be treated as an uninterrupted controlled session. No strategy, timeout, inputs or object code was changed in response to these results.

All 800 attempt records and all eight unchanged object hashes were validated. There were 667 successful attempts and 133 timeouts. Some timeout exceptions were wrapped by the verifier as RuntimeError and retain the raw status 'failed'; their error text identifies the same timeout. No semantic inequivalence was reported for those attempts.

The configured 60-second SIGALRM did not enforce a strict wall-time cutoff. Five execsnoop bound attempts were reported successful by the existing helper after more than 60 measured seconds: optimized trials 40 (165.5741 s), 59 (88.4146 s), 65 (91.9299 s), and original trials 81 (105.4513 s), 90 (140.0363 s). They are retained unchanged in every summary and plot. The mechanism was not diagnosed; these observations further limit interpretation of this case and prevent treating this as uniformly right-censored data at exactly 60 seconds.

Figures: global-runtime.png (eight absolute-time bars), global-relative-runtime.png (eight normalized bars), global-distributions.png (all successful runtimes), global-completions.png (successful attempt counts), and per-case runtime.png/distribution.png. SVG copies are provided for report figures.
