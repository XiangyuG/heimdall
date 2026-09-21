# Branch-Merging Verification Benchmark

> **Note:** `in_execution_opt` is not implemented yet. Do not use
> `--test exec`. Always pass `--test source`; omitting `--test` also schedules
> the unavailable in-execution benchmark.

## Layout

```text
merge-branch/
├── README.md
├── compile_bpf.sh                 # Compiles one C/eBPF source into bytes/
├── run-benchmark.py               # Measures verification runtimes
├── cases/                         # Original C/eBPF source programs
│   └── *.bpf.c
├── source_level_opt/
│   ├── vanilla_remove_conditional.py
│   └── generated/                 # Generated source-optimized programs
│       └── *_MERGED.bpf.c
├── in_execution_opt/              # Not implemented yet
├── bytes/                         # Compiled benchmark objects
│   ├── NAME.o
│   └── NAME_MERGED.o
└── results/
    └── <case>_<test>_<timestamp>/
        ├── log.txt                # Verifier output
        ├── runtime.png            # Runtime comparison graph
        └── benchmark_results.json # Runtime data and verification status
```

## Compile an eBPF Program

```text
./compile_bpf.sh <path-to-bpf-source>
```

The script accepts one `.c` file and writes its `.o` file to `bytes/`.

```sh
./compile_bpf.sh cases/branch_10.bpf.c
./compile_bpf.sh source_level_opt/generated/branch_10_MERGED.bpf.c
```

This produces `bytes/branch_10.o` and `bytes/branch_10_MERGED.o`.

Set `BPF_CLANG=/path/to/clang` if the script cannot find a BPF-capable Clang.

## Run the Benchmark

```text
python run-benchmark.py \
  --case ORIGINAL.o \
  --test source \
  --entry ENTRY_SYMBOL
```

- `--case` is the original object filename under `bytes/`, not a path.
- `--test source` compares the original and source-optimized runtimes.
- `--entry` is the eBPF entry-point symbol to verify.

For `--case NAME.o`, both `bytes/NAME.o` and `bytes/NAME_MERGED.o` must exist.

Example:

```sh
/Users/dajohnyu/miniconda3/envs/c2rust/bin/python run-benchmark.py \
  --case branch_10.o \
  --test source \
  --entry blk_account_io_done
```

The graph compares `branch_10.o` versus itself with
`branch_10_MERGED.o` versus itself.

Results are written to:

```text
results/<case>_source_<timestamp>/
```
