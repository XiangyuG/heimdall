#!/usr/bin/env python3
"""Compile exactly two named cases at -O2 and benchmark Heimdall verification."""
from __future__ import annotations

import argparse
import contextlib
from datetime import datetime
import gc
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import random
import re
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import time
import traceback

ROOT = Path(__file__).resolve().parent
VERIFIER_DIR = ROOT.parent / "c2rust_translation"
sys.setrecursionlimit(20000)
sys.path.insert(0, str(ROOT / "source_level_opt"))
from ast_utils import Source, clang_flags, find_clang
from optimize import PASSES


def select_python():
    candidates = [os.environ.get("HEIMDALL_VERIFY_PYTHON"), sys.executable,
                  str(Path.home() / "miniconda3/envs/c2rust/bin/python")]
    if os.environ.get("HEIMDALL_VERIFY_PYTHON"):
        candidates = candidates[:1]
    for candidate in candidates:
        python = shutil.which(candidate) if candidate else None
        if python:
            probe = subprocess.run([python, "-B", "-c", "import angr, z3, matplotlib, elftools"],
                                   capture_output=True)
            if probe.returncode == 0:
                return python
    raise ValueError("Heimdall dependencies unavailable; set HEIMDALL_VERIFY_PYTHON")


def exact_source(name, directory):
    if Path(name).name != name or not name.endswith(".bpf.c"):
        raise ValueError("arguments must be exact .bpf.c filenames, without directories")
    path = directory / name
    if not path.is_file():
        raise ValueError(f"source not found: {path}")
    return path


def executable_code(path):
    from elftools.elf.elffile import ELFFile
    with path.open("rb") as stream:
        elf = ELFFile(stream)
        return {s.name: s.data() for s in elf.iter_sections() if s["sh_flags"] & 4 and s.data_size}


def entries(path):
    from elftools.elf.elffile import ELFFile
    with path.open("rb") as stream:
        elf = ELFFile(stream)
        symbols = elf.get_section_by_name(".symtab")
        result = []
        for symbol in symbols.iter_symbols() if symbols else []:
            index = symbol["st_shndx"]
            if (symbol["st_info"]["type"] == "STT_FUNC" and symbol["st_info"]["bind"] == "STB_GLOBAL"
                    and isinstance(index, int) and index > 0
                    and elf.get_section(index).name != ".text"):
                result.append(symbol.name)
        return result


def compile_case(path, log):
    command = ["bash", str(ROOT / "compile_bpf.sh"), str(path)]
    completed = subprocess.run(command, capture_output=True, text=True)
    log.write(completed.stdout + completed.stderr)
    log.flush()
    if completed.returncode:
        raise RuntimeError(f"compilation failed: {path.name}")
    return ROOT / "bytes" / (path.name[:-6] + ".o")


def timeout_handler(signum, frame):
    raise TimeoutError("verification exceeded HEIMDALL_TIMEOUT_SECONDS")


def controlled_input_witness(original_name):
    """Use the experiment's controlled first context word, without source guards."""
    match = re.fullmatch(r"(fusion|bound)_(01|08|32)\.bpf\.c", original_name)
    if not match:
        return None
    family = match.group(1)
    from witness_spec import Assumption, WitnessSpec
    # For kprobe/test, r15 occupies bytes 0..7 in the little-endian context.
    # The source reads the first u32, i.e. its low 32 bits.
    expression = {"eq": {
        "left": {"truncate": {"value": "original.ctx.r15", "width": 32}},
        "right": {"value": 8, "type": "u32"},
    }}
    return WitnessSpec(
        version="0.1", name=f"{family}_controlled_input", bindings=[],
        assumptions=[Assumption(
            id=f"{family}_n_8", expression=expression,
            provenance={"kind": "experiment_input"},
            description="Controlled experiment input: ctx[0] = 8; other context bits remain symbolic.",
        )], observations=[], source_path="<benchmark controlled input>",
    )


def verify_pair(verifier, left, right, entry, label, timeout, log, witness=None):
    gc.collect()
    buffer = io.StringIO()
    log.write(f"\n--- {label}: {left.name} vs {right.name} ---\n")
    log.flush()
    started = time.perf_counter()
    signal.alarm(timeout)
    try:
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            result = verifier.run_verification(str(left), str(right), entry, [], witness=witness)
        elapsed = time.perf_counter() - started
        # All benchmark loops have finite bounds under the recorded inputs. Any leftover execution
        # or errored path is a failed trial, even if a partial formula says UNSAT.
        output = buffer.getvalue()
        bad_stash = re.search(r"stash '(?:active|errored|unconstrained|deferred|stashed|cut)':\s*([1-9]\d*)", output)
        errored = re.search(r"errored=([1-9]\d*)", output)
        if not result.equivalent or bad_stash or errored:
            raise RuntimeError(f"incomplete/failed verification: {result.result_type}; {result.counter_example}")
        log.write(output)
        log.write(json.dumps({"label": label, "seconds": elapsed, "equivalent": result.equivalent,
                              "result_type": result.result_type}) + "\n")
        log.flush()
        return elapsed
    except BaseException:
        log.write(buffer.getvalue())
        raise
    finally:
        signal.alarm(0)


def bootstrap_reduction(original, optimized):
    rng = random.Random(984)
    samples = []
    for _ in range(10000):
        indices = [rng.randrange(len(original)) for _ in original]
        samples.append(100 * (1 - statistics.median(optimized[i] for i in indices)
                              / statistics.median(original[i] for i in indices)))
    samples.sort()
    return [samples[250], samples[9749]]


def chart(path, original_name, optimized_name, times, input_label=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    labels = [original_name, optimized_name]
    values = [statistics.median(times[k]) for k in ("original_self", "optimized_self")]
    fig, ax = plt.subplots(figsize=(8, 4.8))
    bars = ax.bar(["Original + Clang -O2", "Source optimized + Clang -O2"], values,
                  color=["#4472C4", "#2A9D8F"])
    for i, key in enumerate(("original_self", "optimized_self")):
        ax.scatter([i] * len(times[key]), times[key], s=16, color="black", alpha=0.35, zorder=3)
    ax.bar_label(bars, fmt="%.3f s", padding=5)
    ax.set_ylabel("Total Heimdall self-verification time (seconds)")
    reduction = 100 * (1 - values[1] / values[0])
    input_note = f"; {input_label}" if input_label else ""
    ax.set_title(f"{labels[0]}\nMedian of {len(times['original_self'])} trials{input_note}; reduction {reduction:.1f}%")
    ax.set_ylim(0, max(max(times[k]) for k in ("original_self", "optimized_self")) * 1.18)
    ax.grid(axis="y", linestyle=":", alpha=0.4)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", help="exact filename in cases/")
    parser.add_argument("optimized", help="exact filename in source_level_opt/generated/")
    args = parser.parse_args()
    try:
        original = exact_source(args.original, ROOT / "cases")
        optimized = exact_source(args.optimized, ROOT / "source_level_opt/generated")
        trials = int(os.environ.get("HEIMDALL_TRIALS", "7"))
        timeout = int(os.environ.get("HEIMDALL_TIMEOUT_SECONDS", "120"))
        if trials < 2 or timeout < 1:
            raise ValueError("HEIMDALL_TRIALS must be >=2 and timeout must be positive")
        # Keep caches outside the per-run directory: it contains only log and graph.
        os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "heimdall-clang-limitation-mpl"))
        os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
        python = select_python()
        if Path(python).resolve() != Path(sys.executable).resolve():
            os.execv(python, [python, "-B", str(Path(__file__).resolve()), *sys.argv[1:]])
        sys.path.insert(0, str(VERIFIER_DIR))
        import verify_equivalence as verifier
        witness = controlled_input_witness(original.name)
        logging.getLogger("angr").setLevel(logging.ERROR)
        logging.getLogger("cle").setLevel(logging.ERROR)
        signal.signal(signal.SIGALRM, timeout_handler)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        run_dir = ROOT / "results" / f"{original.name[:-6]}_vs_{optimized.name[:-6]}_{stamp}"
        run_dir.mkdir(parents=True)
        print(f"Results: {run_dir}", flush=True)
        with (run_dir / "log.txt").open("w") as log:
            try:
                clang = find_clang()
                log.write(subprocess.check_output([clang, "--version"], text=True))
                log.write(json.dumps({"flags": clang_flags(), "trials": trials, "warmups": 1,
                                      "timeout_seconds": timeout, "timing": "run_verification only; imports and compilation excluded",
                                      "input_assumptions": [] if witness is None else [
                                          {"id": a.id, "expression": a.expression, "description": a.description,
                                           "provenance": a.provenance} for a in witness.assumptions]}) + "\n")
                for label, source_path in [("original", original), ("optimized", optimized)]:
                    log.write(f"\n--- {label} source: {source_path} ---\n" + source_path.read_text())
                source = Source(original)
                log.write("\n--- Parser analysis (no source mutation) ---\n")
                for name, module in PASSES.items():
                    changes, skipped = module.transform(source)
                    log.write(json.dumps({"pass": name, "replacement_count": len(changes), "skipped": skipped}) + "\n")
                objects = [compile_case(original, log), compile_case(optimized, log)]
                code = [executable_code(p) for p in objects]
                if code[0] == code[1]:
                    raise RuntimeError("Clang -O2 already emits identical executable instructions for this pair; not a demonstrated limitation")
                for path, sections in zip(objects, code):
                    log.write(json.dumps({"object": str(path), "instructions": sum(len(b) // 8 for b in sections.values()),
                                          "code_sha256": hashlib.sha256(b"".join(sections[k] for k in sorted(sections))).hexdigest()}) + "\n")
                for label, source_path in [("original", original), ("optimized", optimized)]:
                    command = [clang, *clang_flags(), "-S", str(source_path), "-o", "-"]
                    log.write(f"\n--- {label} assembly (-O2) ---\n" + subprocess.check_output(command, text=True))
                entry_lists = [entries(p) for p in objects]
                if len(entry_lists[0]) != 1 or entry_lists[0] != entry_lists[1]:
                    raise ValueError("both cases must have the same single global entry symbol")
                entry = entry_lists[0][0]
                left, right = objects
                verify_pair(verifier, left, right, entry, "original_to_optimized_equivalence", timeout, log, witness)
                schedule = {"original_self": (left, left), "optimized_self": (right, right),
                            "original_fixed_reference": (left, right)}
                for label, pair in schedule.items():
                    verify_pair(verifier, *pair, entry, "warmup_" + label, timeout, log, witness)
                times = {k: [] for k in schedule}
                for trial in range(trials):
                    order = list(schedule)
                    if trial % 2:
                        order.reverse()
                    for label in order:
                        value = verify_pair(verifier, *schedule[label], entry, f"trial_{trial + 1}_{label}", timeout, log, witness)
                        times[label].append(value)
                    print(f"Trial {trial + 1}/{trials} complete", flush=True)
                medians = {k: statistics.median(v) for k, v in times.items()}
                summary = {"raw_seconds": times, "median_seconds": medians,
                           "self_reduction_percent": 100 * (1 - medians["optimized_self"] / medians["original_self"]),
                           "self_reduction_ci95_percent": bootstrap_reduction(times["original_self"], times["optimized_self"]),
                           "fixed_reference_reduction_percent": 100 * (1 - medians["optimized_self"] / medians["original_fixed_reference"]),
                           "fixed_reference_reduction_ci95_percent": bootstrap_reduction(times["original_fixed_reference"], times["optimized_self"])}
                log.write("\n--- SUMMARY ---\n" + json.dumps(summary, indent=2) + "\n")
                log.flush()
                chart(run_dir / "runtime.png", original.name, optimized.name, times,
                      input_label="n = ctx[0] = 8" if witness is not None else None)
                print(json.dumps(summary, indent=2))
                print(f"Graph: {run_dir / 'runtime.png'}")
            except BaseException:
                traceback.print_exc(file=log)
                raise
        return 0
    except (ValueError, RuntimeError, OSError, ImportError, subprocess.CalledProcessError, TimeoutError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
