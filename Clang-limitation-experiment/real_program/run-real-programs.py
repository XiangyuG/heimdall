#!/usr/bin/env python3
"""Reproduce the measured real-program optimizations without changing verifier inputs."""
from __future__ import annotations

import argparse
from datetime import datetime
import difflib
import hashlib
import importlib.util
import json
import logging
import os
from pathlib import Path
import signal
import statistics
import subprocess
import sys
import traceback

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SUPPORT = ROOT / "source_level_opt" / "support"
sys.path.insert(0, str(SUPPORT))
os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/heimdall-clang-limitation-mpl")
sys.dont_write_bytecode = True
sys.setrecursionlimit(20000)
spec = importlib.util.spec_from_file_location("benchmark", SUPPORT / "benchmark_helpers.py")
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


def generate(case):
    original = ROOT / "cases" / (case["id"] + ".bpf.c")
    text = original.read_text()
    if hashlib.sha256(text.encode()).hexdigest() != case["baseline_sha256"]:
        raise ValueError(f"baseline changed: {original}")
    optimized_text = text
    for edit in sorted(case["replacements"], key=lambda e: e["start"], reverse=True):
        start, end = edit["start"], edit["end"]
        if optimized_text[start:end] != edit["expected"]:
            raise ValueError("optimization recipe no longer matches source")
        optimized_text = optimized_text[:start] + edit["replacement"] + optimized_text[end:]
    directory = ROOT / "source_level_opt" / "generated"
    directory.mkdir(exist_ok=True)
    optimized = directory / (case["id"] + "_SOURCE_OPT.bpf.c")
    optimized.write_text(optimized_text)
    patch = "".join(difflib.unified_diff(text.splitlines(True), optimized_text.splitlines(True),
                                         fromfile=original.name, tofile=optimized.name))
    return original, optimized, patch


def case_label(case):
    name = Path(case["program"]).name.removesuffix(".bpf.c").removesuffix(".c")
    prefix = "KEN " if case["program"].startswith("KEN/") else ""
    method = "bound caching*" if case.get("requirement") else "alignment"
    return f"{prefix}{name}\n{method}"


def global_chart(rows, path, normalized=False):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    x = np.arange(len(rows))
    before = [r["median_seconds"]["original_self"] for r in rows]
    after = [r["median_seconds"]["optimized_self"] for r in rows]
    if normalized:
        after = [b / a for a, b in zip(before, after)]
        before = [1.0] * len(rows)
    fig, ax = plt.subplots(figsize=(max(13, len(rows) * 1.15), 7.2))
    a = ax.bar(x - .2, before, .4, label="Original + Clang -O2", color="#4472C4")
    b = ax.bar(x + .2, after, .4, label="Hand optimized + Clang -O2", color="#2A9D8F")
    ax.bar_label(a, labels=[f"{v:.3f}" for v in before], padding=3, fontsize=8, rotation=90)
    ax.bar_label(b, labels=[f"{v:.3f}" for v in after], padding=3, fontsize=8, rotation=90)
    ax.set_xticks(x, [r.get("label", r["id"]) for r in rows],
                  rotation=35, ha="right", fontsize=9)
    ax.set_ylabel("Relative verification time (original = 1)" if normalized
                  else "Median Heimdall self-verification time (seconds)")
    ax.set_title(f"{len(rows)} comparisons / {len(rows) * 2} bars — lower is better\n"
                 "Selected-entry self-equivalence; * requires frozen configuration")
    ax.set_ylim(0, max(before + after) * 1.25)
    ax.grid(axis="y", linestyle=":", alpha=.4)
    ax.set_axisbelow(True)
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    fig.savefig(path.with_suffix(".svg"))
    plt.close(fig)


def summarize(rows, output):
    successful = [r for r in rows if r.get("status") == "success"]
    (output / "results.json").write_text(json.dumps(rows, indent=2) + "\n")
    lines = ["# Measured real-program optimizations", "",
             "Both variants use Clang -O2 and identical headers and inputs. Times are medians of five alternating trials after one warm-up per variant. Each selected entry first passes original-to-optimized equivalence. Timing measures self-equivalence, not C-to-Rust verification. Individual graphs show raw trials as points.", "",
             "| Program | Optimization | BPF slots before → after | Median seconds before → after | Speedup (original / optimized) |",
             "|---|---|---:|---:|---:|"]
    for r in successful:
        m = r["median_seconds"]
        lines.append(f"| `{r['program']}` | {r['method']} | {r['instructions'][0]} → {r['instructions'][1]} | "
                     f"{m['original_self']:.4f} → {m['optimized_self']:.4f} | {m['original_self']/m['optimized_self']:.3f}× |")
    lines += ["", "Conditional bound caching requires loader-frozen configuration during an invocation and excludes volatile-read traces from observations. The verifier's functional model does not establish that external contract.", "",
              "Map-pointer alignment annotations rely on the relevant hash-map allocator's eight-byte value alignment. Equivalence results cover the recorded entry and verifier model, not every entry or Linux kernel verifier acceptance.", "",
              "Timeouts and failed/unmeasured cases are excluded from the table and graphs; any such outcome remains recorded in results.json and its log. Small differences and speedups below 1× are retained. No benchmark inputs or verifier semantics are changed."]
    (output / "REPORT.md").write_text("\n".join(lines) + "\n")
    if successful:
        global_chart(successful, output / "global-runtime.png")
        global_chart(successful, output / "global-relative-runtime.png", normalized=True)
    # Include existing synthetic experiments without rerunning or pooling their trials.
    reference = ROOT / "reference_results" / "legacy-results.json"
    legacy = json.loads(reference.read_text()) if reference.is_file() else []
    if successful and legacy:
        (output / "legacy-results.json").write_text(json.dumps(legacy, indent=2) + "\n")
        global_chart(legacy + successful, output / "all-experiments-runtime.png")
        global_chart(legacy + successful, output / "all-experiments-relative-runtime.png", normalized=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", help="run only these case IDs")
    args = parser.parse_args()
    python = benchmark.select_python()
    if Path(python).resolve() != Path(sys.executable).resolve():
        os.execv(python, [python, "-B", __file__, *sys.argv[1:]])
    sys.path.insert(0, str(REPO / "c2rust_translation"))
    import verify_equivalence as verifier
    logging.getLogger("angr").setLevel(logging.ERROR)
    logging.getLogger("cle").setLevel(logging.ERROR)
    signal.signal(signal.SIGALRM, benchmark.timeout_handler)
    manifest = json.loads((ROOT / "real-programs.json").read_text())
    cases = manifest["cases"]
    if args.case:
        unknown = set(args.case) - {c["id"] for c in cases}
        if unknown:
            parser.error(f"unknown cases: {sorted(unknown)}")
        cases = [c for c in cases if c["id"] in args.case]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = ROOT / "results" / ("real_program_" + stamp)
    output.mkdir()
    print(f"Results: {output}", flush=True)
    clang = benchmark.find_clang()
    compiler = subprocess.check_output([clang, "--version"], text=True)
    # Manifest paths are relocated from the original audit checkout when needed.
    old_repo = manifest["flags"][manifest["flags"].index("-I") + 1].rsplit("/runtime-testing/include", 1)[0]
    flags = [f.replace(old_repo, str(REPO)) for f in manifest["flags"]]
    rows = []
    for case in cases:
        run_dir = output / case["id"]
        run_dir.mkdir()
        row = {k: v for k, v in case.items() if k != "replacements"}
        row["label"] = case_label(case)
        row["status"] = "failed"
        try:
            with (run_dir / "log.txt").open("w") as log:
                log.write(compiler + "\n" + json.dumps({"flags": flags, "entry": case["entry"],
                    "trials": manifest["trials"], "warmups": 1, "timeout_seconds": manifest["timeout_seconds"],
                    "input_assumptions": [], "requirement": case.get("requirement")}) + "\n")
                original, optimized, patch = generate(case)
                (run_dir / "optimization.patch").write_text(patch)
                objects = []
                for label, source in (("original", original), ("optimized", optimized)):
                    obj = ROOT / "bytes" / (source.name[:-6] + ".o")
                    obj.parent.mkdir(exist_ok=True)
                    command = [clang, *flags, "-iquote", str(REPO / case["original_directory"]),
                               "-x", "c", "-c", "-o", str(obj), "-"]
                    log.write(json.dumps({"command": command, "source": str(source)}) + "\n")
                    result = subprocess.run(command, input=source.read_bytes(), capture_output=True)
                    log.write(result.stderr.decode())
                    if result.returncode:
                        raise RuntimeError(f"compilation failed: {source.name}")
                    objects.append(obj)
                code = [benchmark.executable_code(p) for p in objects]
                row["instructions"] = [sum(len(b) // 8 for b in c.values()) for c in code]
                if row["instructions"] != case["expected_instructions"]:
                    raise RuntimeError(f"instruction counts changed: {row['instructions']}")
                if code[0] == code[1]:
                    raise RuntimeError("identical executable code")
                if any(case["entry"] not in benchmark.entries(obj) for obj in objects):
                    raise RuntimeError("selected entry missing")
                left, right = objects
                timeout = manifest["timeout_seconds"]
                benchmark.verify_pair(verifier, left, right, case["entry"], "equivalence", timeout, log)
                row["equivalence"] = "passed for selected entry"
                schedule = {"original_self": (left, left), "optimized_self": (right, right)}
                for label, pair in schedule.items():
                    benchmark.verify_pair(verifier, *pair, case["entry"], "warmup_" + label, timeout, log)
                times = {k: [] for k in schedule}
                for trial in range(manifest["trials"]):
                    order = list(schedule)
                    if trial % 2:
                        order.reverse()
                    for label in order:
                        times[label].append(benchmark.verify_pair(verifier, *schedule[label], case["entry"],
                                                f"trial_{trial + 1}_{label}", timeout, log))
                    print(f"{case['id']}: trial {trial + 1}/{manifest['trials']}", flush=True)
                row["raw_seconds"] = times
                row["median_seconds"] = {k: statistics.median(v) for k, v in times.items()}
                row["speedup"] = row["median_seconds"]["original_self"] / row["median_seconds"]["optimized_self"]
                row["reduction_percent"] = 100 * (1 - 1 / row["speedup"])
                row["reduction_ci95_percent"] = benchmark.bootstrap_reduction(times["original_self"], times["optimized_self"])
                row["status"] = "success"
                log.write("\n--- SUMMARY ---\n" + json.dumps(row, indent=2) + "\n")
                benchmark.chart(run_dir / "runtime.png", original.name, optimized.name, times,
                                input_label="frozen configuration required" if case.get("requirement") else None)
                print(f"{case['id']}: {row['speedup']:.3f}x", flush=True)
        except Exception as error:
            row["error"] = f"{type(error).__name__}: {error}"
            (run_dir / "error.txt").write_text(traceback.format_exc())
            print(f"{case['id']}: FAILED: {row['error']}", flush=True)
        rows.append(row)
        (output / "results.json").write_text(json.dumps(rows, indent=2) + "\n")
    summarize(rows, output)
    print(f"Report: {output / 'REPORT.md'}", flush=True)
    return 0 if all(r["status"] == "success" for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
