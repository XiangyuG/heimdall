# Clang limitation experiment

Compare Heimdall verification time before and after three source optimizations:
loop fusion (`fusion`), aligned 16-bit loads (`aligned_load`), and loop-bound
caching (`bound`). Each family has cases with 1, 8, and 32 repetitions.
Both variants compile with Clang **`-O2`**. Fusion and bound verification uses
controlled input `ctx[0] = 8`.

## Usage

Run from this directory using Heimdall’s Python environment and a BPF-capable Clang:

```sh
# Generate the optimized source.
python3 source_level_opt/optimize.py fusion_08.bpf.c

# Compile both sources and benchmark verification.
python3 run-benchmark.py fusion_08.bpf.c fusion_08_SOURCE_OPT.bpf.c
```

Replace `fusion_08` with any `fusion`, `aligned_load`, or `bound` case using
suffix `01`, `08`, or `32`. Originals are in `cases/`, generated sources in
`source_level_opt/generated/`, and compiled objects in `bytes/`.
Each successful run saves `log.txt` and `runtime.png` in a timestamped
`results/` directory.

The default is seven trials with one warm-up per mode. Optional environment
variables: `HEIMDALL_TRIALS`, `HEIMDALL_TIMEOUT_SECONDS` (default 120),
`BPF_CLANG`, and `HEIMDALL_VERIFY_PYTHON`.
