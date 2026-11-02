#!/usr/bin/env python3
"""Compile, prove, and time the five full-program hand optimizations."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def worker(args):
    sys.path.insert(0, str(REPO / "c2rust_translation"))
    import verify_equivalence as verifier
    logging.getLogger("angr").setLevel(logging.ERROR)
    logging.getLogger("cle").setLevel(logging.ERROR)
    output = io.StringIO()
    result = {"left": args.left, "right": args.right, "entry": args.entry,
              "passed": False, "seconds": None}
    started = time.perf_counter()
    try:
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            proof = verifier.run_verification(args.left, args.right, args.entry, [])
        result.update(seconds=time.perf_counter() - started,
                      equivalent=bool(proof.equivalent), result_type=proof.result_type,
                      counter_example=str(proof.counter_example))
        # A partial formula is not a successful whole-program proof.
        incomplete = re.search(
            r"stash '(?:active|errored|unconstrained|deferred|stashed|cut)':\s*([1-9]\d*)"
            r"|errored=([1-9]\d*)", output.getvalue())
        result["complete"] = incomplete is None
        result["passed"] = bool(proof.equivalent) and incomplete is None
    except BaseException as exc:
        import traceback
        traceback.print_exc(file=output)
        result.update(seconds=time.perf_counter() - started, error=repr(exc))
    finally:
        Path(args.log).write_text(output.getvalue())
        save(Path(args.result), result)
    return 0 if result["passed"] else 1


def object_info(path):
    from elftools.elf.elffile import ELFFile
    with path.open("rb") as stream:
        elf = ELFFile(stream)
        sections = {s.name: s.data() for s in elf.iter_sections()
                    if s["sh_flags"] & 4 and s.data_size}
        symbols = elf.get_section_by_name(".symtab")
        entries = []
        for symbol in symbols.iter_symbols():
            index = symbol["st_shndx"]
            if (symbol["st_info"]["type"] == "STT_FUNC"
                    and symbol["st_info"]["bind"] == "STB_GLOBAL"
                    and isinstance(index, int) and index > 0
                    and elf.get_section(index).name != ".text"):
                entries.append(symbol.name)
    conditional = sum(1 for data in sections.values() for offset in range(0, len(data), 8)
                      if data[offset] & 7 in (5, 6)
                      and data[offset] & 0xf0 not in (0x00, 0x80, 0x90))
    return {"instruction_slots": sum(map(len, sections.values())) // 8,
            "conditional_jumps": conditional, "entries": entries,
            "executable_sha256": hashlib.sha256(b"".join(sections.values())).hexdigest()}


def invoke(run, case, left, right, entry, label, timeout):
    folder = run / case
    folder.mkdir(exist_ok=True)
    result_path = folder / f"{label}.json"
    log_path = folder / f"{label}.log"
    command = [sys.executable, "-B", str(Path(__file__).resolve()), "--worker",
               "--left", str(left), "--right", str(right), "--entry", entry,
               "--result", str(result_path), "--log", str(log_path)]
    try:
        process = subprocess.run(command, capture_output=True, text=True,
                                 timeout=timeout, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        if result_path.exists():
            result = json.loads(result_path.read_text())
        else:
            result = {"passed": False, "error": "worker did not produce a result",
                      "stdout": process.stdout, "stderr": process.stderr}
            save(result_path, result)
    except subprocess.TimeoutExpired:
        result = {"passed": False, "error": "timeout", "timeout_seconds": timeout,
                  "left": str(left), "right": str(right), "entry": entry}
        save(result_path, result)
    print(case, label, "PASS" if result["passed"] else "FAIL",
          result.get("seconds", result.get("error")), flush=True)
    return result


def plot(run, results):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    measured = [c for c in results if c.get("medians")]
    if not measured:
        return
    fig, axes = plt.subplots(1, len(measured), figsize=(3.5 * len(measured), 4.6), squeeze=False)
    for ax, case in zip(axes[0], measured):
        before, after = [case["medians"][name] for name in ("original", "optimized")]
        ax.bar([0, 1], [before, after], color=["#577590", "#43aa8b"], width=.62)
        for x, name in enumerate(("original", "optimized")):
            ys = case["trials"][name]
            ax.scatter([x] * len(ys), ys, color="#222222", s=18, zorder=3)
            ax.text(x, max(ys) * 1.025, f"{case['medians'][name]:.3f} s", ha="center", fontsize=10)
        ax.set_xticks([0, 1], ["Original", "Optimized"])
        ax.set_ylim(0, max(case["trials"]["original"] + case["trials"]["optimized"]) * 1.18)
        change = 100 * (1 - after / before)
        ax.set_title(f"{case['id']}\n{change:+.1f}% time reduction", fontsize=11)
        ax.set_ylabel("Heimdall self-equivalence time (seconds)")
        ax.grid(axis="y", alpha=.2)
        ax.set_axisbelow(True)
    fig.suptitle("Hand optimization: verification runtime before and after\n"
                 "Clang -O2; median of 5 alternating trials; dots are individual trials", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, .87))
    fig.savefig(run / "runtime-comparison.png", dpi=170)
    fig.savefig(run / "runtime-comparison.svg")
    plt.close(fig)


def main(args):
    manifest = json.loads((HERE / "manifest.json").read_text())
    run = HERE / "results" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run.mkdir(parents=True)
    (run / "build").mkdir()
    clang = os.environ.get("BPF_CLANG", "/opt/homebrew/opt/llvm/bin/clang")
    save(run / "environment.json", {
        "clang": subprocess.check_output([clang, "--version"], text=True),
        "python": sys.version, "manifest": manifest,
        "worker_isolation": "Fresh process per verification call; imports and startup excluded from timings."})
    results = []
    print("RESULTS", run, flush=True)
    for spec in manifest["cases"]:
        if args.case and spec["id"] != args.case:
            continue
        case = {**spec, "proofs": {}, "trials": {"original": [], "optimized": []}}
        results.append(case)
        objects = {}
        try:
            for variant in ("original", "optimized"):
                source = HERE / spec[variant]
                target = run / "build" / f"{spec['id']}.{variant}.o"
                command = [clang, *manifest["compiler_flags"], "-I", str(REPO / "runtime-testing/include"),
                           "-c", str(source), "-o", str(target)]
                compiled = subprocess.run(command, capture_output=True, text=True)
                (run / "build" / f"{spec['id']}.{variant}.compile.log").write_text(
                    json.dumps(command) + "\n" + compiled.stdout + compiled.stderr)
                if compiled.returncode:
                    raise RuntimeError(f"{variant} compilation failed")
                objects[variant] = target
                case[variant + "_object"] = object_info(target)
                case[variant + "_source_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
            entries = case["original_object"]["entries"]
            if entries != case["optimized_object"]["entries"]:
                raise RuntimeError("entry points changed")
            entry = spec["timed_entry"]
            if entry not in entries:
                raise RuntimeError(f"missing timed entry {entry}")
            left, right = objects["original"], objects["optimized"]
            # Exact original-to-optimized proof, with unchanged inputs and observations.
            cross = invoke(run, spec["id"], left, right, entry, "equivalence_" + entry, 120)
            case["proofs"][entry] = cross
            if not cross["passed"]:
                raise RuntimeError("selected-entry equivalence failed")
            for variant in ("original", "optimized"):
                obj = objects[variant]
                warmup = invoke(run, spec["id"], obj, obj, entry, "warmup_" + variant, 120)
                if not warmup["passed"]:
                    raise RuntimeError(f"{variant} warmup failed")
            for trial in range(5):
                order = ("original", "optimized") if trial % 2 == 0 else ("optimized", "original")
                for variant in order:
                    obj = objects[variant]
                    result = invoke(run, spec["id"], obj, obj, entry,
                                    f"trial_{trial + 1}_{variant}", 120)
                    if not result["passed"]:
                        raise RuntimeError(f"{variant} timed trial failed")
                    case["trials"][variant].append(result["seconds"])
            case["medians"] = {k: statistics.median(v) for k, v in case["trials"].items()}
            case["time_reduction_percent"] = 100 * (1 - case["medians"]["optimized"] / case["medians"]["original"])
            # Check every exported entry, including entry points outside the timed workload.
            for other in entries:
                if other == entry:
                    continue
                proof = invoke(run, spec["id"], left, right, other, "equivalence_" + other, 120)
                case["proofs"][other] = proof
            case["all_entries_equivalent"] = all(p["passed"] for p in case["proofs"].values())
            case["status"] = "complete" if case["all_entries_equivalent"] else "some_entry_proofs_failed"
        except Exception as exc:
            case["status"] = "failed"
            case["error"] = str(exc)
        save(run / "results.json", results)
        plot(run, results)
        print("CASE_RESULT", json.dumps(case), flush=True)
    save(HERE / "latest-run.json", {"directory": str(run.relative_to(HERE))})
    return 0 if results and all(c.get("status") == "complete" for c in results) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case")
    parser.add_argument("--worker", action="store_true")
    for name in ("left", "right", "entry", "result", "log"):
        parser.add_argument("--" + name)
    parsed = parser.parse_args()
    raise SystemExit(worker(parsed) if parsed.worker else main(parsed))
