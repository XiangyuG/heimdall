# Four real-program comparisons with 100 trials

Timing uses the existing benchmark helper and verify_equivalence.run_verification() in the c2rust conda environment. Imports, compilation, garbage collection and log writes are outside the timed interval. Each case uses the same existing -O2 objects, selected entry, inputs, success-only helper model and configured 60-second alarm as the earlier experiment. Each version receives one warm-up, followed by 100 timed attempts. Execution is serial and pair order alternates. No outliers are trimmed and failed attempts are not replaced.

| Case | Successful original / optimized trials | Successful-run median seconds original to optimized | Successful-run time reduction | Paired bootstrap 95% interval |
|---|---:|---:|---:|---:|
| ken_execsnoop_alignment | 100/100 and 100/100 | 0.3198 to 0.3182 | 0.52% | -0.25% to 1.00% |
| mdflush_alignment | 100/100 and 100/100 | 0.5330 to 0.5730 | -7.50% | -8.28% to -6.75% |
| tcprtt_alignment | 100/100 and 100/100 | 26.0341 to 25.0839 | 3.65% | -14.71% to 9.89% |
| execsnoop_bound | 86/100 and 95/100 | 38.8189 to 36.4074 | 6.21% | not computed |

The intervals use 10,000 paired bootstrap resamples of the median time ratio. They summarize this run and do not establish independence of trials or transferability to other system loads. JSON also records means, standard deviations, quartiles and ranges. Bar heights are successful-run medians; individual charts overlay every successful trial. ECDF and box plots retain outliers. Any failures/timeouts are listed in results.json and raw_trials.csv. No completion time is assigned to a failed attempt; successful-run reductions do not estimate the full sample when timeouts occur.

The execsnoop bound rewrite requires configuration frozen during each invocation and excludes individual volatile-read traces from observations. Functional equivalence checks do not prove that external contract. These are selected-entry self-equivalence workloads, not program execution times or C-to-Rust verification. Saved five-trial results remain unchanged.

Runtime bar graphs retain the median as their center and show whiskers spanning median +/- one sample standard deviation (n-1 denominator), with SD values printed above each bar. These whiskers describe observed spread, not confidence intervals or uncertainty of the median. Only successful runtimes contribute; timeouts are not imputed. In the normalized graph both each median and its SD are divided by that case's original successful-run median; normalized whiskers are not uncertainty intervals for a speedup ratio.

## Process isolation and interpretation

This new experiment uses a fresh Python process for each case. Cases run sequentially, with one persistent verifier process within each case. The earlier data, object files, timing helper, selected entries, timeout setting, warmups and alternating order are preserved. Only process isolation between cases differs from the previous experiment.

Started: 2026-10-27T00:26:06.693653+00:00. Finished: 2026-10-27T04:16:09.718316+00:00. See process_runs.json for separate process start/end times and exit status.

- ken_execsnoop_alignment: 100/100 original and 100/100 optimized attempts reported successful; 0 failed attempts. Uncertainty interval includes zero; a clear improvement is not established.

- mdflush_alignment: 100/100 original and 100/100 optimized attempts reported successful; 0 failed attempts. 

- tcprtt_alignment: 100/100 original and 100/100 optimized attempts reported successful; 0 failed attempts. Uncertainty interval includes zero; a clear improvement is not established.

- execsnoop_bound: 86/100 original and 95/100 optimized attempts reported successful; 19 failed attempts.  Failures limit interpretation: successful-run reductions do not establish overall speedup.

Recorded attempts: 800/800; successful: 781; failed: 19. Raw failure statuses and error text are preserved. Wrapped TimeoutError exceptions may retain status 'failed'. No failed attempt was replaced, no outlier trimmed, and no timeout result imputed.

The configured 60-second SIGALRM uses the existing helper and is not assumed to be a strict wall-time cap. Inspect raw timestamps for gaps and graphs for retained outliers; do not infer an uninterrupted stable environment merely from process isolation.

Figures: global-runtime.png (eight absolute-time bars), global-relative-runtime.png (eight normalized bars), global-distributions.png (successful runtimes), global-completions.png (successful counts), per-case runtime.png and distribution.png; SVG copies included.

## Independent audit and timing drift

Independent validation confirms 800 unique attempt records, four distinct case process IDs with no overlap, and all eight object hashes unchanged. Timeout counts are 14 original and 5 optimized attempts in execsnoop bound; the other cases have none.

| Case | Variant | Successful first-20 median (s) | Successful last-20 median (s) | Change |
|---|---|---:|---:|---:|
| ken_execsnoop_alignment | Original | 0.3024 | 0.3371 | +11.5% |
| ken_execsnoop_alignment | Optimized | 0.3001 | 0.3363 | +12.1% |
| mdflush_alignment | Original | 0.5012 | 0.5402 | +7.8% |
| mdflush_alignment | Optimized | 0.5414 | 0.5794 | +7.0% |
| tcprtt_alignment | Original | 20.7889 | 36.3819 | +75.0% |
| tcprtt_alignment | Optimized | 20.7198 | 36.4744 | +76.0% |
| execsnoop_bound | Original | 17.3942 | 51.3322 | +195.1% |
| execsnoop_bound | Optimized | 13.4866 | 48.9839 | +263.2% |

These first/last summaries are diagnostics only; they do not replace the full-sample summaries or discard any trials. Timings rose substantially during tcprtt and execsnoop bound in both variants. Process isolation between cases did not produce a stable timing baseline within each case. The cause was not established; these data do not attribute the drift or earlier failures to token exhaustion.

The observed failure count was lower than in the earlier 100-attempt run (19 versus 133), but that does not establish which environmental or process factor caused the difference. The two prior experiments remain preserved. Mdflush was 7.50% slower after optimization in this run; KEN and tcprtt uncertainty intervals include zero. The execsnoop successful-run reduction remains conditional on completion.

See global-trial-trends.png (and SVG) for every successful timing in trial order; audit.json provides validation and per-variant failure counts.
