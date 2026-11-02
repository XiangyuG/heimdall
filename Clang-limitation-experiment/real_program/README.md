# Real-program Clang limitation experiments

Run the commands below from this `real_program/` directory.

The real-program audit contains ten measured comparisons across nine programs. Two
comparisons use `libbpf-tools/execsnoop.bpf.c`, separately testing alignment
and bound caching. Unmeasured programs and the timed-out crab case are excluded.

```sh
~/miniconda3/envs/c2rust/bin/python -B run-real-programs.py
```

This command applies the exact source edits recorded in `real-programs.json`,
writes optimized sources to `source_level_opt/generated/`, and recompiles both
versions at `-O2`. It checks original-to-optimized equivalence for each recorded
entry, then measures five alternating self-equivalence trials after one warm-up
per version, with a 60-second timeout for each verification call. These are
selected-entry self-equivalence workloads, not C-to-Rust verification or program
execution times. Inputs and verifier semantics are unchanged.

The manifest records provenance, baseline hashes, source edits, entry points,
expected instruction counts, compiler flags, and conditional requirements.
Cases are complete programs; no entry points are removed. `cases/build_support/`
records header-inlining and support-definition differences from the original
source programs. Those build preparations apply identically to both variants
and are separate from the optimization patches saved with results.

Bound caching in `execsnoop_bound` and `tcpconnect_bound` requires loader-frozen
configuration during each invocation and excludes volatile-read traces from
observations. The functional verifier does not establish that external contract.
Map-value alignment annotations rely on the relevant hash maps' allocator
guarantees. Equivalence covers the selected entry under Heimdall's model; Linux
kernel verifier acceptance is not tested by this experiment.

Each `results/real_program_<timestamp>/` contains:

- `REPORT.md`: one combined table of measured outcomes.
- `results.json`: raw trials, medians, paired-bootstrap intervals, and failures.
- One directory per comparison with `runtime.png`, `optimization.patch`, and `log.txt`.
- `global-runtime.png` and `.svg`: all new comparisons, two bars per comparison.
- `global-relative-runtime.png` and `.svg`: the same data with each original set to one.
- `all-experiments-runtime.png` and `.svg`: new results plus the nine existing synthetic results.
- `all-experiments-relative-runtime.png` and `.svg`: normalized combined results.

The combined legacy plots retain the old measurements and their different
workloads; they do not pool trials or imply matching inputs across programs.
Their original logs are listed in `legacy-results.json`. Individual graphs
show every trial; aggregate bars show medians. Slowdowns are retained. Failures
and timeouts remain in logs and JSON but are excluded from tables and graphs.
Use `--case <id>` to reproduce a particular manifest entry.

## Layout

```text
real_program/
├── README.md
├── real-programs.json
├── run-real-programs.py
├── cases/
│   └── build_support/
├── bytes/
├── results/
│   └── real_program_20261019_125237/
├── reference_results/
│   └── legacy-results.json
└── source_level_opt/
    ├── optimize_program.py
    ├── validate_program_optimizer.py
    ├── test_optimize_program.py
    ├── GENERAL_OPTIMIZER.md
    ├── generated/
    ├── validation/
    └── support/
        ├── ast_utils.py
        ├── cache_invariant_bound.py
        └── benchmark_helpers.py
```

The three original experiment families remain in the parent directory. The
real-program tools use private helper copies and write only within this tree
(or temporary working directories). Runtime headers, original program headers,
and the verifier are repository dependencies outside the experiment directory.

`reference_results/legacy-results.json` preserves the nine earlier synthetic
measurements used by the combined 38-bar charts. Combined charts use this fixed
snapshot; they do not depend on importing the original runner or scanning its
results. Its `source_log` entries are relative to the parent experiment directory.

All existing saved sources, objects, charts, raw results, and proof logs were
preserved during the move. Historical logs and JSON reports retain their original
recorded paths as provenance; live tools resolve the new layout.

## Reusable optimizer

```sh
python3 -B source_level_opt/optimize_program.py cases/ken_execsnoop_alignment.bpf.c \
  --output /tmp/ken_execsnoop.optimized.bpf.c --report /tmp/ken_execsnoop.optimization.json
python3 -B -m unittest discover -s source_level_opt -p test_optimize_program.py -v
```

See [the optimizer documentation](source_level_opt/GENERAL_OPTIMIZER.md) and
[saved parser assessments](source_level_opt/validation/README.md). The parser
assessment tool accepts `--verify` for equivalence checks; this is separate from
the timing benchmark and requires Heimdall's conda dependencies.
