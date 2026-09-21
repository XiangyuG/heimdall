# Heimdall runtime tests

This directory contains standalone eBPF programs used to measure Heimdall's
self-equivalence verification runtime. Each source under `cases/` is complete;
test cases do not include another local `.c` file or select behavior through a
compile-time benchmark flag.

## Running a suite

Run exactly one suite with `--case`:

```sh
python runtime-testing/run_test.py --case branch_expand
python runtime-testing/run_test.py --case helper_expand
python runtime-testing/run_test.py --case nest_expand
python runtime-testing/run_test.py --case branch_helper_nest
python runtime-testing/run_test.py --case branch_helper_nest_basic
python runtime-testing/run_test.py --case slot_operations
```

The same names are available as Make targets when invoked inside this
directory, for example `make branch_expand`.

`run_test.py` compiles every program in the selected suite, verifies each
object against itself, and creates a timestamped directory under `output/`.
Each run contains the compiled objects, per-program logs, `results.tsv`,
`summary.txt`, and a runtime chart when matplotlib is installed.

## Dependencies

- A Clang build with the BPF target. The runner checks `BPF_CLANG` first, then
  common Homebrew locations, then `clang` on `PATH`.
- The Python environment used by Heimdall. Set `HEIMDALL_VERIFY_PYTHON` when
  the runner should invoke a different interpreter for the verifier.
- The committed libbpf and project-specific headers in `include/`.

Generated output is ignored by Git and can be deleted at any time.
