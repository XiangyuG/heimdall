# Benchmarking libbpf-tools BPF programs

These BPF programs are checked for *semantic* equivalence symbolically (the
`verify_*.py` scripts never run them). To measure their **execution time** you
load and attach them for real and read the kernel's per-program accounting.

## What is measured

`ns/run` = `run_time_ns / run_cnt` from `struct bpf_prog_info` — the kernel's
own cumulative runtime and invocation count for each loaded BPF program. A
"runner" here is a small userspace program that:

1. loads a compiled `.o`, attaches its programs,
2. snapshots each program's `run_cnt` / `run_time_ns`,
3. sleeps N seconds while a **workload** drives the probed events,
4. snapshots again and prints the delta ratio.

## Requirements

- `clang`, `libbpf-dev` (>= 0.5), `libelf-dev`, zlib
- Linux >= 5.15 with BPF run statistics:
  `sudo sysctl -w kernel.bpf_stats_enabled=1`
- root, or passwordless `sudo` (loading BPF needs `CAP_BPF` / `CAP_SYS_ADMIN`)
- a workload generator for the probe class you are measuring
  (`fio` for block/fs tools; the scripts in `workloads/` for the rest)

## Build the runners

```sh
cd c2rust_translation/c_bpf_programs/libbpf-tools
make                # builds every *_runner (git-ignored)
```

The runners link against the system libbpf and do **not** need `vmlinux.h`
(that header, plus `bits.bpf.h` / `core_fixes.bpf.h` / `maps.bpf.h`, is only for
recompiling the `*.bpf.c` programs).

## Run one, manually

```sh
# 1. start a workload in the background
fio --name=w --filename=/tmp/bpfbench.data --size=1G --rw=randrw --bs=4k \
    --time_based --runtime=120 --numjobs=4 --group_reporting &

# 2. measure for 60 s
sudo ./filetop_runner filetop.o 60 256
```

```
program                          run_cnt        run_time_ns         ns/run
vfs_read_entry                     10342          11216402         1084.85
vfs_write_entry                     9871           7118930          721.07
```

Each runner prints its own usage. Argv shapes differ per tool; the shared
`generic_runner` takes the attach-target program names directly:

```sh
sudo ./generic_runner drsnoop.o 60 direct_reclaim_begin_btf direct_reclaim_end_btf
```

The exact argv and default workload for every wired tool are the source of
truth in `openevolve/examples/bpf_compile/evaluator.py` (`TOOLS`).

## Run via OpenEvolve

`openevolve/examples/bpf_compile/` drives the whole loop (compile candidate →
symbolic equivalence check → workload + runner → `ns/run`):

```sh
cd openevolve
BPF_TOOL=filetop python openevolve-run.py \
    examples/bpf_compile/initial_program.py examples/bpf_compile/evaluator.py \
    --config examples/bpf_compile/config.yaml
```

`HEIMDALL_ROOT` defaults to this repo root, so `LIBBPF_TOOLS_DIR` resolves to
this directory with no override. Useful env vars: `BPF_TOOL`, `BPF_RUNNER_SECONDS`,
`BPF_WORKLOAD_CMD` (override the default workload), `HEIMDALL_ROOT`, `BPF_RUNNER`.

## Tool status on a stock Ubuntu 22.04 / kernel 5.15 box

| status | tools |
|---|---|
| works with the default `fio` workload | `filetop` `cachestat` `biopattern` `biostacks` `bitesize` |
| works via `generic_runner` + a `workloads/` script | `drsnoop` `fsdist` `fsslower` `futexctn` `mdflush` `mountsnoop` `numamove` `offcputime` `oomkill` `runqslower` `slabratetop` `softirqs` `solisten` `statsnoop` `syncsnoop` `tcpconnect` `tcpconnlat` `tcplife` `tcpstates` `tcpsynbl` `tcptracer` |
| needs a non-`fio` workload | `wakeuptime` (scheduler activity) |
| broken here | `sigsnoop` (libbpf 0.5 rejects the `bpf_task_from_pid` weak extern), `tcprtt` (`tcprtt_op.bpf.c` has a pre-existing `BPF_CORE_READ` bug), `biotop` / `vfsstat` (runners print continuous samples, not an aggregate `ns/run`) |
