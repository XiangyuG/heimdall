#!/usr/bin/env python3
"""One case only: 100 paired rounds with durable, non-replacing checkpoints."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import random
import statistics
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
import benchmark as legacy


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(path)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprints():
    paths = [HERE / "benchmark.py", Path(__file__), HERE / "manifest.json"]
    paths += sorted((REPO / "c2rust_translation").glob("*.py"))
    paths += sorted((REPO / "angr_ebpf_backend").rglob("*.py"))
    paths += sorted((REPO / "runtime-testing/include").rglob("*.h"))
    return {str(p.relative_to(REPO)): sha(p) for p in paths}


def percentile(xs, percent):
    ordered = sorted(xs)
    index = (len(ordered) - 1) * percent / 100
    low, high = math.floor(index), math.ceil(index)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def describe(xs):
    if not xs:
        return {"n": 0}
    mean = statistics.mean(xs)
    median = statistics.median(xs)
    deviation = statistics.stdev(xs) if len(xs) > 1 else 0.0
    return {"n": len(xs), "median": median, "mean": mean,
            "stdev": deviation, "cv_percent": 100 * deviation / mean,
            "min": min(xs), "max": max(xs),
            "p05": percentile(xs, 5), "p25": percentile(xs, 25),
            "p75": percentile(xs, 75), "p95": percentile(xs, 95),
            "iqr": percentile(xs, 75) - percentile(xs, 25),
            "mad": statistics.median(abs(x - median) for x in xs),
            "first_25_median": statistics.median(xs[:25]),
            "last_25_median": statistics.median(xs[-25:])}


def paired_interval(pairs):
    if not pairs:
        return None
    rng = random.Random(984)
    values = []
    for _ in range(10000):
        sample = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        values.append(100 * (1 - statistics.median(p[1] for p in sample)
                             / statistics.median(p[0] for p in sample)))
    return [percentile(values, 2.5), percentile(values, 97.5)]


def protocol_for(spec, clang, manifest):
    return {"case": spec, "created_protocol_version": 1, "paired_rounds": 100,
            "timed_calls_per_variant": 100, "warmups_per_variant": 1,
            "order": "odd round original then optimized; even round optimized then original",
            "timeout_process_wall_seconds": 120,
            "timing": "unchanged benchmark.py worker: run_verification only; startup/imports excluded",
            "compiler": str(Path(clang).resolve()),
            "clang_version": subprocess.check_output([clang, "--version"], text=True),
            "compiler_flags": manifest["compiler_flags"],
            "python": sys.version, "python_executable": str(Path(sys.executable).resolve()),
            "dependencies": {n: importlib.metadata.version(n) for n in
                             ["angr", "claripy", "cle", "z3-solver", "pyelftools", "matplotlib"]},
            "source_sha256": {v: sha(HERE / spec[v]) for v in ["original", "optimized"]},
            "code_sha256": fingerprints(), "extra_input_assumptions": [],
            "helper_fail_mode": "off", "observations": "unchanged verifier defaults",
            "failure_policy": "retain every failure, timeout, and interruption; never replace an attempted slot",
            "statistics": "all successful samples untrimmed; failure counts explicit; paired bootstrap uses complete pairs only"}


class CaseRun:
    def __init__(self, directory, protocol):
        self.directory = directory
        self.protocol = protocol
        self.case = protocol["case"]
        self.calls = directory / "calls"
        self.calls.mkdir(exist_ok=True)

    def invoke(self, left, right, entry, label):
        result_path = self.calls / (label + ".json")
        attempt_path = self.calls / (label + ".attempt.json")
        if result_path.exists():
            return json.loads(result_path.read_text())
        if attempt_path.exists():
            result = {"passed": False, "seconds": None, "error": "interrupted_unfinished_attempt",
                      "entry": entry, "label": label, "recorded_utc": now()}
            atomic_json(result_path, result)
            self.journal(label, result)
            return result
        atomic_json(attempt_path, {"started_utc": now(), "label": label,
                                  "left": str(left), "right": str(right), "entry": entry})
        command = [sys.executable, "-B", str(HERE / "benchmark.py"), "--worker",
                   "--left", str(left), "--right", str(right), "--entry", entry,
                   "--result", str(result_path), "--log", str(self.calls / (label + ".log"))]
        started = time.perf_counter()
        try:
            process = subprocess.run(command, capture_output=True, text=True, timeout=120,
                                     env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
            (self.calls / (label + ".process.log")).write_text(process.stdout + process.stderr)
            if result_path.exists():
                result = json.loads(result_path.read_text())
                if process.returncode != 0:
                    result["passed"] = False
                    result["process_returncode"] = process.returncode
            else:
                result = {"passed": False, "seconds": None, "error": "worker_missing_result",
                          "process_returncode": process.returncode}
        except subprocess.TimeoutExpired as exc:
            result = {"passed": False, "seconds": None, "error": "timeout",
                      "timeout_process_wall_seconds": 120}
            content = (exc.stdout or b"") + (exc.stderr or b"")
            (self.calls / (label + ".process.log")).write_bytes(content)
        result.update(label=label, entry=entry, finished_utc=now(),
                      process_wall_seconds=time.perf_counter() - started)
        atomic_json(result_path, result)
        self.journal(label, result)
        print(self.case["id"], label, "PASS" if result["passed"] else "FAIL",
              result.get("seconds"), result.get("error", ""), flush=True)
        return result

    def journal(self, label, result):
        with (self.directory / "journal.jsonl").open("a") as stream:
            stream.write(json.dumps({"label": label, **result}) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def checkpoint(self, rounds, stage):
        failures = sum(not value["passed"] for row in rounds for value in row["results"].values())
        atomic_json(self.directory / "progress.json", {
            "case": self.case["id"], "stage": stage, "updated_utc": now(),
            "rounds_recorded": len(rounds), "planned_rounds": 100,
            "timed_failures": failures, "rounds": rounds})


def compile_objects(run, clang):
    directory = run.directory / "build"
    directory.mkdir(exist_ok=True)
    result = {}
    metadata = {}
    for variant in ["original", "optimized"]:
        target = directory / (variant + ".o")
        command = [clang, *run.protocol["compiler_flags"], "-I", str(REPO / "runtime-testing/include"),
                   "-c", str(HERE / run.case[variant]), "-o", str(target)]
        log_path = directory / (variant + ".compile.log")
        if not target.exists():
            process = subprocess.run(command, text=True, capture_output=True)
            log_path.write_text(json.dumps(command) + "\n" + process.stdout + process.stderr)
            if process.returncode:
                raise RuntimeError(variant + " compilation failed")
        metadata[variant] = legacy.object_info(target)
        result[variant] = target
    if metadata["original"]["entries"] != metadata["optimized"]["entries"]:
        raise RuntimeError("exported entry points changed")
    record_path = run.directory / "objects.json"
    if record_path.exists() and json.loads(record_path.read_text()) != metadata:
        raise RuntimeError("compiled objects differ from checkpoint")
    atomic_json(record_path, metadata)
    return result, metadata


def finish(run, rounds, proofs, error=None):
    timings = {v: [row["results"][v]["seconds"] for row in rounds
                   if row["results"][v].get("passed") and row["results"][v].get("seconds") is not None]
               for v in ["original", "optimized"]}
    failures = {v: [row["round"] for row in rounds if not row["results"][v]["passed"]]
                for v in timings}
    pairs = [(row["results"]["original"]["seconds"], row["results"]["optimized"]["seconds"])
             for row in rounds if all(row["results"][v]["passed"] for v in timings)]
    complete = (len(rounds) == 100 and all(len(xs) == 100 for xs in timings.values())
                and bool(proofs) and all(p["passed"] for p in proofs.values()) and error is None)
    stats = {v: describe(xs) for v, xs in timings.items()}
    reduction = (100 * (1 - stats["optimized"]["median"] / stats["original"]["median"])
                 if timings["original"] and timings["optimized"] else None)
    blocks = []
    for begin in range(0, len(rounds), 10):
        rows = rounds[begin:begin + 10]
        block = {"first_round": begin + 1, "last_round": begin + len(rows)}
        for v in timings:
            xs = [row["results"][v]["seconds"] for row in rows if row["results"][v]["passed"]]
            block[v] = statistics.median(xs) if xs else None
        blocks.append(block)
    summary = {"case": run.case["id"], "complete": complete, "error": error,
               "completed_utc": now(), "planned_pairs": 100, "recorded_pairs": len(rounds),
               "statistics": stats, "failed_rounds": failures, "complete_pairs": len(pairs),
               "median_time_reduction_percent": reduction,
               "paired_bootstrap_ci95_reduction_percent": paired_interval(pairs),
               "bootstrap_pairs_used": len(pairs), "block_medians": blocks,
               "proofs": proofs, "rounds": rounds}
    atomic_json(run.directory / "summary.json", summary)
    report(run, summary, timings)
    return complete


def report(run, summary, timings):
    lines = ["# " + run.case["id"] + ": 100-trial stability benchmark", "",
             "Status: **" + ("COMPLETE" if summary["complete"] else "INCOMPLETE / FAILED") + "**.", "",
             "100 planned paired rounds: 100 original and 100 optimized self-equivalence calls. "
             "Fresh worker per call; identical Clang -O2 inputs and defaults; 120-second process limit. "
             "One untimed warm-up per version. Every exported entry is checked original-to-optimized.", "",
             "No samples are trimmed or replaced. Failed/timeout/interrupted calls are listed separately; "
             "statistics below describe successful calls only. An incomplete run is not a successful 100-trial result.", "",
             "| Variant | Successful | Failed rounds | Median s | Mean s | SD s | CV % | p05–p95 s | Min–max s |",
             "| --- | ---: | --- | ---: | ---: | ---: | ---: | --- | --- |"]
    for v, s in summary["statistics"].items():
        if s["n"]:
            lines.append(f"| {v} | {s['n']}/100 | {summary['failed_rounds'][v]} | {s['median']:.6f} | "
                         f"{s['mean']:.6f} | {s['stdev']:.6f} | {s['cv_percent']:.2f} | "
                         f"{s['p05']:.6f}–{s['p95']:.6f} | {s['min']:.6f}–{s['max']:.6f} |")
        else:
            lines.append(f"| {v} | 0/100 | {summary['failed_rounds'][v]} | — | — | — | — | — | — |")
    if summary["median_time_reduction_percent"] is not None:
        ci = summary["paired_bootstrap_ci95_reduction_percent"]
        lines += ["", f"Median time reduction: **{summary['median_time_reduction_percent']:.2f}%**.",
                  f"Paired-bootstrap 95% interval: **{ci[0]:.2f}% to {ci[1]:.2f}%**, "
                  f"using {summary['bootstrap_pairs_used']} complete pairs (10,000 resamples; fixed seed 984)."]
    lines += ["", "## Proofs", ""]
    for name, proof in summary["proofs"].items():
        lines.append(f"- `{name}`: {'PASS' if proof['passed'] else 'FAIL'}.")
    if summary["error"]:
        lines += ["", "Error: `" + summary["error"] + "`."]
    lines += ["", "## Stability and drift", "",
              "Large CV/IQR or a change in the first/last-25 medians indicates timing variability. "
              "A positive speedup interval addresses the before/after difference, not stationarity of either process.", "",
              "| Variant | First-25 median s | Last-25 median s | IQR s | MAD s |", "| --- | ---: | ---: | ---: | ---: |"]
    for v, s in summary["statistics"].items():
        if s["n"]:
            lines.append(f"| {v} | {s['first_25_median']:.6f} | {s['last_25_median']:.6f} | {s['iqr']:.6f} | {s['mad']:.6f} |")
    lines += ["", "![Runtime and trial trends](stability.png)", "",
              "[Raw summary and per-round results](summary.json) · [Frozen protocol](protocol.json) · "
              "[Append-only call journal](journal.jsonl)", "",
              "Heimdall default helper-failure mode is off. No extra witness, input restriction, "
              "or observation restriction is used. These are selected-entry self-equivalence timings; "
              "they are not kernel execution or C-to-Rust translation times.", ""]
    (run.directory / "REPORT.md").write_text("\n".join(lines))
    if not any(timings.values()):
        return
    os.environ.setdefault("MPLCONFIGDIR", str(run.directory / "matplotlib-cache"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8))
    colors = ["#577590", "#43aa8b"]
    for i, v in enumerate(timings):
        xs = timings[v]
        if not xs:
            continue
        median = statistics.median(xs)
        axes[0].bar(i, median, color=colors[i], width=.65)
        axes[0].scatter([i] * len(xs), xs, s=9, color="black", alpha=.3, zorder=3)
        axes[0].annotate(f"{median:.3f} s", (i, max(xs)), xytext=(0, 6),
                         textcoords="offset points", ha="center")
        rows = [(row["round"], row["results"][v]["seconds"]) for row in summary["rounds"]
                if row["results"][v]["passed"]]
        axes[i + 1].plot([x for x, y in rows], [y for x, y in rows], ".-", color=colors[i], linewidth=.7)
        axes[i + 1].set(title=v + ": all successful trials", xlabel="Paired round", ylabel="Seconds")
        axes[i + 1].set_ylim(bottom=0)
    axes[0].set_xticks([0, 1], ["Original", "Optimized"])
    axes[0].set(title="Medians and every observation", ylabel="Self-equivalence seconds")
    axes[0].set_ylim(bottom=0)
    axes[0].margins(y=.15)
    for ax in axes:
        ax.grid(axis="y", alpha=.2)
        ax.set_axisbelow(True)
    fig.suptitle(run.case["id"] + ": 100 paired rounds; untrimmed samples", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, .93))
    fig.savefig(run.directory / "stability.png", dpi=160)
    fig.savefig(run.directory / "stability.svg")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True,
                        choices=[c["id"] for c in json.loads((HERE / "manifest.json").read_text())["cases"]])
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    # This OS lock spans compilation, all timing calls, proof checks, and documentation.
    with (HERE / ".benchmark-100.lock").open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("Another 100-trial case holds the lock; do not overlap cases.")
        lock.seek(0)
        lock.truncate()
        lock.write(json.dumps({"pid": os.getpid(), "case": args.case, "started_utc": now()}))
        lock.flush()
        manifest = json.loads((HERE / "manifest.json").read_text())
        spec = next(c for c in manifest["cases"] if c["id"] == args.case)
        clang = os.environ.get("BPF_CLANG", "/opt/homebrew/opt/llvm/bin/clang")
        protocol = protocol_for(spec, clang, manifest)
        directory = args.run_dir.resolve()
        if args.resume:
            recorded = json.loads((directory / "protocol.json").read_text())
            if protocol != recorded:
                raise SystemExit("Source, dependencies, compiler, or protocol changed; resume refused.")
        else:
            directory.mkdir(parents=True, exist_ok=False)
            atomic_json(directory / "protocol.json", protocol)
            atomic_json(directory / "started.json", {"started_utc": now(), "case": args.case})
        run = CaseRun(directory, protocol)
        rounds = []
        proofs = {}
        error = None
        try:
            objects, metadata = compile_objects(run, clang)
            entry = spec["timed_entry"]
            proof = run.invoke(objects["original"], objects["optimized"], entry, "equivalence_" + entry)
            proofs[entry] = proof
            if not proof["passed"]:
                raise RuntimeError("timed-entry equivalence failed")
            for v in ["original", "optimized"]:
                warmup = run.invoke(objects[v], objects[v], entry, "warmup_" + v)
                if not warmup["passed"]:
                    raise RuntimeError(v + " warm-up failed")
            for index in range(1, 101):
                order = ["original", "optimized"] if index % 2 else ["optimized", "original"]
                row = {"round": index, "order": order, "results": {}}
                for v in order:
                    row["results"][v] = run.invoke(objects[v], objects[v], entry, f"trial_{index:03d}_{v}")
                rounds.append(row)
                run.checkpoint(rounds, "timing")
            for other in metadata["original"]["entries"]:
                if other != entry:
                    proofs[other] = run.invoke(objects["original"], objects["optimized"], other,
                                              "equivalence_" + other)
            run.checkpoint(rounds, "documenting")
        except Exception as exc:
            error = repr(exc)
        complete = finish(run, rounds, proofs, error)
        run.checkpoint(rounds, "complete" if complete else "incomplete")
        print("DOCUMENTED", directory / "REPORT.md", "complete=", complete, flush=True)
        return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
