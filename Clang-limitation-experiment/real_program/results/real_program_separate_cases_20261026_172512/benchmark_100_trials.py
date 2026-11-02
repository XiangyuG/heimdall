#!/usr/bin/env python3
"""Repeat the existing selected-entry self-equivalence benchmark 100 times per version."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import logging
import os
from pathlib import Path
import platform
import signal
import statistics
import sys
import time
import traceback

OUTPUT = Path(__file__).resolve().parent
ROOT = OUTPUT.parents[1]
REPO = ROOT.parents[1]
sys.dont_write_bytecode = True
sys.setrecursionlimit(20000)
os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/heimdall-clang-limitation-mpl")
sys.path.insert(0, str(ROOT / "source_level_opt" / "support"))
import benchmark_helpers as benchmark

CASE_IDS = {"tcprtt_alignment", "execsnoop_bound", "mdflush_alignment", "ken_execsnoop_alignment"}
VARIANTS = ("original_self", "optimized_self")
TRIALS = 100


def now():
    return datetime.now(timezone.utc).isoformat()


def checkpoint(state):
    temporary = OUTPUT / ".checkpoint.json"
    temporary.write_text(json.dumps(state, indent=2) + "\n")
    temporary.replace(OUTPUT / "checkpoint.json")
    with (OUTPUT / "raw_trials.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["case", "trial", "variant", "status", "seconds", "started_utc", "error"])
        writer.writeheader()
        for case in state["cases"]:
            for item in case["measurements"]:
                writer.writerow({"case": case["id"], **item})


def describe(values):
    if not values:
        return None
    quartiles = statistics.quantiles(values, n=4, method="inclusive") if len(values) > 1 else values * 3
    return {"n": len(values), "median": statistics.median(values), "mean": statistics.mean(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0,
            "min": min(values), "q25": quartiles[0], "q75": quartiles[2], "max": max(values)}


def summarize(state, intervals=False):
    rows = []
    for case in state["cases"]:
        row = {k: v for k, v in case.items() if k != "measurements"}
        row["raw_seconds"] = {variant: [m["seconds"] for m in case["measurements"]
                                        if m["variant"] == variant and m["status"] == "success"]
                              for variant in VARIANTS}
        row["distribution_seconds"] = {k: describe(v) for k, v in row["raw_seconds"].items()}
        row["attempts"] = {v: sum(m["variant"] == v for m in case["measurements"]) for v in VARIANTS}
        row["failures"] = [m for m in case["measurements"] if m["status"] != "success"]
        if all(row["raw_seconds"].values()):
            medians = {v: statistics.median(row["raw_seconds"][v]) for v in VARIANTS}
            row["median_seconds"] = medians
            row["speedup"] = medians["original_self"] / medians["optimized_self"]
            row["reduction_percent"] = 100 * (1 - 1 / row["speedup"])
        row["complete"] = all(row["attempts"][v] == TRIALS for v in VARIANTS)
        row["all_trials_successful"] = row["complete"] and not row["failures"]
        if intervals and row["all_trials_successful"]:
            row["reduction_ci95_percent"] = benchmark.bootstrap_reduction(
                row["raw_seconds"]["original_self"], row["raw_seconds"]["optimized_self"])
        rows.append(row)
    (OUTPUT / "results.json").write_text(json.dumps(rows, indent=2) + "\n")
    return rows


def plots(state):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    rows = summarize(state, intervals=True)
    valid = [r for r in rows if "median_seconds" in r]
    colors = ["#4472C4", "#2A9D8F"]
    labels = ["Original + Clang -O2", "Hand optimized + Clang -O2"]
    for row in valid:
        directory = OUTPUT / row["id"]
        values = [row["raw_seconds"][v] for v in VARIANTS]
        medians = [statistics.median(v) for v in values]
        deviations = [statistics.stdev(v) if len(v) > 1 else 0 for v in values]
        fig, ax = plt.subplots(figsize=(8, 5))
        bars = ax.bar([0, 1], medians, color=colors, width=.6,
                      yerr=deviations, capsize=5, error_kw={"elinewidth": 1.4})
        for i, sample in enumerate(values):
            # Deterministic horizontal jitter only; no timing value is changed or removed.
            jitter = [i + (((k * 37) % 101) / 100 - .5) * .34 for k in range(len(sample))]
            ax.scatter(jitter, sample, s=12, color="black", alpha=.3, zorder=3)
        label_gap = max(max(sample) for sample in values) * .035
        for i, (median, deviation, sample) in enumerate(zip(medians, deviations, values)):
            ax.text(i, max(max(sample), median + deviation) + label_gap,
                    f"{median:.4f} s\nSD {deviation:.4f} s", ha="center", va="bottom")
        ax.set_xticks([0, 1], [f"{label}\n{len(sample)}/100 successful" for label, sample in zip(labels, values)])
        ax.set_ylabel("Heimdall self-verification time (seconds)")
        qualifier = "Successful-run medians only; timeouts prevent a full comparison" if row["failures"] else f"Median reduction {row['reduction_percent']:.1f}%"
        ax.set_title(f"{row['id']}\n{qualifier}\nBars: median; whiskers: +/-1 sample SD (not a confidence interval)", fontsize=11)
        ax.set_ylim(0, max(max(max(v) for v in values), max(m + s for m, s in zip(medians, deviations))) * 1.22)
        ax.grid(axis="y", linestyle=":", alpha=.4); ax.set_axisbelow(True)
        fig.tight_layout(); fig.savefig(directory / "runtime.png", dpi=180); fig.savefig(directory / "runtime.svg"); plt.close(fig)
        fig, ax = plt.subplots(figsize=(8, 4.8))
        for sample, color, label in zip(values, colors, labels):
            ordered = sorted(sample)
            ax.step(ordered, np.arange(1, len(ordered) + 1) / len(ordered), where="post", label=f"{label}: {len(sample)}/100 successful", color=color)
        ax.set_xlabel("Heimdall self-verification time (seconds)"); ax.set_ylabel("Cumulative fraction of successful trials")
        ax.set_title(f"{row['id']} — all observed successful runtimes")
        ax.grid(linestyle=":", alpha=.4); ax.legend(); fig.tight_layout()
        fig.savefig(directory / "distribution.png", dpi=180); fig.savefig(directory / "distribution.svg"); plt.close(fig)
    if valid:
        for normalized, filename in [(False, "global-runtime"), (True, "global-relative-runtime")]:
            x = np.arange(len(valid)); before = [r["median_seconds"]["original_self"] for r in valid]
            after = [r["median_seconds"]["optimized_self"] for r in valid]
            before_sd = [r["distribution_seconds"]["original_self"]["stdev"] for r in valid]
            after_sd = [r["distribution_seconds"]["optimized_self"]["stdev"] for r in valid]
            if normalized:
                before_sd = [s / m for s, m in zip(before_sd, before)]
                after_sd = [s / m for s, m in zip(after_sd, before)]
                after = [b / a for a, b in zip(before, after)]; before = [1.] * len(valid)
            fig, ax = plt.subplots(figsize=(11, 6))
            a = ax.bar(x - .19, before, .38, color=colors[0], label=labels[0], yerr=before_sd, capsize=4, error_kw={"elinewidth": 1.3})
            b = ax.bar(x + .19, after, .38, color=colors[1], label=labels[1], yerr=after_sd, capsize=4, error_kw={"elinewidth": 1.3})
            ax.bar_label(a, labels=[f"{value:.4f}\nSD {sd:.4f}\nn={len(row['raw_seconds'][VARIANTS[0]])}/100" for value, sd, row in zip(before, before_sd, valid)], padding=4, fontsize=9)
            ax.bar_label(b, labels=[f"{value:.4f}\nSD {sd:.4f}\nn={len(row['raw_seconds'][VARIANTS[1]])}/100" for value, sd, row in zip(after, after_sd, valid)], padding=4, fontsize=9)
            for i, row in enumerate(valid):
                if row["failures"]:
                    a[i].set_hatch("//"); b[i].set_hatch("//")
            ax.set_xticks(x, [r["id"].replace("_", "\n", 1) + ("*" if r["requirement"] else "") for r in valid], rotation=10)
            ax.set_ylabel("Relative successful-run median (original = 1)" if normalized else "Successful-run median verification time (seconds)")
            ax.set_title("Four comparisons / eight bars — 100 attempts per version\nHatched bars exclude timeouts; n = successful runs (overall speedup not established)")
            units_note = "Normalized SD = runtime SD / original median." if normalized else "SD is measured in seconds."
            fig.text(.5, .035, f"Bars: median; whiskers: +/-1 sample SD (not a confidence interval). {units_note}", ha="center", fontsize=9)
            fig.text(.5, .01, "* Bound caching requires frozen configuration. Timeout values are not plotted or imputed.", ha="center", fontsize=9)
            ax.set_ylim(0, max([m + s for m, s in zip(before, before_sd)] + [m + s for m, s in zip(after, after_sd)]) * 1.28); ax.grid(axis="y", linestyle=":", alpha=.4); ax.set_axisbelow(True); ax.legend()
            fig.tight_layout(rect=[0, .07, 1, 1]); fig.savefig(OUTPUT / (filename + ".png"), dpi=180); fig.savefig(OUTPUT / (filename + ".svg")); plt.close(fig)
        fig, ax = plt.subplots(figsize=(11, 5.5))
        x = np.arange(len(valid))
        for offset, variant, color, label in zip([-.19, .19], VARIANTS, colors, labels):
            counts = [len(row["raw_seconds"][variant]) for row in valid]
            bars = ax.bar(x + offset, counts, .38, color=color, label=label)
            ax.bar_label(bars, labels=[f"{count}/100" for count in counts], padding=4)
        ax.set_xticks(x, [row["id"].replace("_", "\n", 1) for row in valid])
        ax.set_ylim(0, 123); ax.set_ylabel("Successful attempts out of 100")
        ax.set_title("Completion counts — configured 60-second alarm\nConfigured alarm is not assumed to be a strict wall-time cap")
        ax.legend(); ax.grid(axis="y", linestyle=":", alpha=.4); ax.set_axisbelow(True)
        fig.tight_layout(); fig.savefig(OUTPUT / "global-completions.png", dpi=180); fig.savefig(OUTPUT / "global-completions.svg"); plt.close(fig)
        fig, axes = plt.subplots(2, 2, figsize=(11, 8))
        for ax, row in zip(axes.flat, valid):
            values = [row["raw_seconds"][v] for v in VARIANTS]
            boxes = ax.boxplot(values, tick_labels=[f"{label}\nn={len(sample)}/100" for label, sample in zip(["Original", "Optimized"], values)], patch_artist=True, showfliers=True)
            for patch, color in zip(boxes["boxes"], colors): patch.set_facecolor(color); patch.set_alpha(.6)
            ax.set_title(row["id"]); ax.set_ylabel("Seconds"); ax.grid(axis="y", linestyle=":", alpha=.4)
        fig.suptitle("Runtime distributions — successful runs only, including outliers\nFailed/timeout attempts are excluded; see completion counts")
        fig.tight_layout(); fig.savefig(OUTPUT / "global-distributions.png", dpi=180); fig.savefig(OUTPUT / "global-distributions.svg"); plt.close(fig)
    lines = ["# Four real-program comparisons with 100 trials", "",
             "Timing uses the existing benchmark helper and verify_equivalence.run_verification() in the c2rust conda environment. Imports, compilation, garbage collection and log writes are outside the timed interval. Each case uses the same existing -O2 objects, selected entry, inputs, success-only helper model and configured 60-second alarm as the earlier experiment. Each version receives one warm-up, followed by100 timed attempts. Execution is serial and pair order alternates. No outliers are trimmed and failed attempts are not replaced.", "",
             "| Case | Successful original / optimized trials | Successful-run median seconds original to optimized | Successful-run time reduction | Paired bootstrap95% interval |",
             "|---|---:|---:|---:|---:|"]
    for row in rows:
        raw = row["raw_seconds"]; n = f"{len(raw['original_self'])}/100 and {len(raw['optimized_self'])}/100"
        if "median_seconds" in row:
            m = row["median_seconds"]; ci = row.get("reduction_ci95_percent")
            ci_text = f"{ci[0]:.2f}% to {ci[1]:.2f}%" if ci else "not computed"
            lines.append(f"| {row['id']} | {n} | {m['original_self']:.4f} to {m['optimized_self']:.4f} | {row['reduction_percent']:.2f}% | {ci_text} |")
        else:
            lines.append(f"| {row['id']} | {n} | unavailable | unavailable | unavailable |")
    lines += ["", "The intervals use10,000 paired bootstrap resamples of the median time ratio. They summarize this run and do not establish independence of trials or transferability to other system loads. JSON also records means, standard deviations, quartiles and ranges. Bar heights are successful-run medians; individual charts overlay every successful trial. ECDF and box plots retain outliers. Any failures/timeouts are listed in results.json and raw_trials.csv. No completion time is assigned to a failed attempt; successful-run reductions do not estimate the full sample when timeouts occur.", "",
              "The execsnoop bound rewrite requires configuration frozen during each invocation and excludes individual volatile-read traces from observations. Functional equivalence checks do not prove that external contract. These are selected-entry self-equivalence workloads, not program execution times or C-to-Rust verification. Saved five-trial results remain unchanged."]
    lines += ["", "Runtime bar graphs retain the median as their center and show whiskers spanning median +/- one sample standard deviation (n-1 denominator), with SD values printed above each bar. These whiskers describe observed spread, not confidence intervals or uncertainty of the median. Only successful runtimes contribute; timeouts are not imputed. In the normalized graph both each median and its SD are divided by that case's original successful-run median; normalized whiskers are not uncertainty intervals for a speedup ratio.", "", "## Process isolation and interpretation", "",
              "This new experiment uses a fresh Python process for each case. Cases run sequentially, with one persistent verifier process within each case. The earlier data, object files, timing helper, selected entries, timeout setting, warmups and alternating order are preserved. Only process isolation between cases differs from the previous experiment.", "",
              f"Started: {state['started_utc']}. Finished: {state.get('finished_utc', 'not finished')}. See process_runs.json for separate process start/end times and exit status."]
    for row in rows:
        counts = [len(row["raw_seconds"][v]) for v in VARIANTS]
        failures = row["failures"]
        over = [{"trial": m["trial"], "variant": m["variant"], "seconds": m["seconds"]}
                for case in state["cases"] if case["id"] == row["id"]
                for m in case["measurements"] if m["status"] == "success" and m["seconds"] > state["timeout_seconds"]]
        ci = row.get("reduction_ci95_percent")
        note = "Uncertainty interval includes zero; a clear improvement is not established." if ci and ci[0] <= 0 <= ci[1] else ""
        if failures:
            note += " Failures limit interpretation: successful-run reductions do not establish overall speedup."
        lines += ["", f"- {row['id']}: {counts[0]}/100 original and {counts[1]}/100 optimized attempts reported successful; {len(failures)} failed attempts. {note}"]
        if over:
            lines += [f"  Successful attempts exceeding the configured alarm: {json.dumps(over)}. Values are retained unchanged; the alarm is not a strict wall-time cap."]
        if row.get("preparation_error"):
            lines += ["  Preparation failed; see checkpoint.json and the case log. Timed trials were not fabricated or retried."]
    total = sum(len(case["measurements"]) for case in state["cases"])
    failures = sum(m["status"] != "success" for case in state["cases"] for m in case["measurements"])
    lines += ["", f"Recorded attempts: {total}/800; successful: {total - failures}; failed: {failures}. Raw failure statuses and error text are preserved. Wrapped TimeoutError exceptions may retain status 'failed'. No failed attempt was replaced, no outlier trimmed, and no timeout result imputed.", "",
              "The configured 60-second SIGALRM uses the existing helper and is not assumed to be a strict wall-time cap. Inspect raw timestamps for gaps and graphs for retained outliers; do not infer an uninterrupted stable environment merely from process isolation.", "",
              "Figures: global-runtime.png (eight absolute-time bars), global-relative-runtime.png (eight normalized bars), global-distributions.png (successful runtimes), global-completions.png (successful counts), per-case runtime.png and distribution.png; SVG copies included."]
    (OUTPUT / "REPORT.md").write_text("\n".join(lines).replace("by100", "by 100").replace("bootstrap95", "bootstrap 95").replace("use10,000", "use 10,000") + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--plots-only", action="store_true")
    parser.add_argument("--case", choices=sorted(CASE_IDS), help="Run exactly one case in this fresh Python process")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "real-programs.json").read_text())
    selected = [c for c in manifest["cases"] if c["id"] in CASE_IDS]
    assert len(selected) == 4
    state_file = OUTPUT / "checkpoint.json"
    if args.plots_only:
        plots(json.loads(state_file.read_text())); return 0
    if not args.case:
        parser.error("--case is required for timing; use --plots-only for analysis")
    if state_file.exists() and not args.resume:
        parser.error("checkpoint exists; use --resume to preserve recorded trials")
    import verify_equivalence as verifier
    logging.getLogger("angr").setLevel(logging.ERROR); logging.getLogger("cle").setLevel(logging.ERROR)
    signal.signal(signal.SIGALRM, benchmark.timeout_handler)
    if args.resume:
        state = json.loads(state_file.read_text())
    else:
        state = {"started_utc": now(), "trials_per_version": TRIALS, "timeout_seconds": manifest["timeout_seconds"],
                 "warmups_per_version": 1, "python": sys.executable, "python_version": sys.version,
                 "platform": platform.platform(), "compile_flags_provenance": manifest["flags"],
                 "timing": "run_verification only, excluding imports, gc and compilation", "cases": []}
        for case in selected:
            row = {k: case[k] for k in ["id", "program", "entry", "method", "requirement", "expected_instructions"]}
            row.update(measurements=[], preparation=[], objects={})
            for variant, suffix in zip(VARIANTS, ["", "_SOURCE_OPT"]):
                obj = ROOT / "bytes" / (case["id"] + suffix + ".o")
                row["objects"][variant] = {"path": str(obj), "sha256": hashlib.sha256(obj.read_bytes()).hexdigest()}
                assert case["entry"] in benchmark.entries(obj)
            counts = [sum(len(b) // 8 for b in benchmark.executable_code(Path(row["objects"][v]["path"])).values()) for v in VARIANTS]
            assert counts == case["expected_instructions"], (case["id"], counts)
            (OUTPUT / case["id"]).mkdir(exist_ok=True)
            state["cases"].append(row)
        checkpoint(state)
    print(f"Results: {OUTPUT}", flush=True)
    for case in state["cases"]:
        if case["id"] != args.case:
            continue
        objects = {v: Path(case["objects"][v]["path"]) for v in VARIANTS}
        for v, obj in objects.items():
            assert hashlib.sha256(obj.read_bytes()).hexdigest() == case["objects"][v]["sha256"], "binary changed"
        with (OUTPUT / case["id"] / "log.txt").open("a") as log:
            if not case["preparation"]:
                prep = [("equivalence", objects[VARIANTS[0]], objects[VARIANTS[1]]),
                        ("warmup_original", objects[VARIANTS[0]], objects[VARIANTS[0]]),
                        ("warmup_optimized", objects[VARIANTS[1]], objects[VARIANTS[1]])]
                try:
                    for label, left, right in prep:
                        seconds = benchmark.verify_pair(verifier, left, right, case["entry"], label, state["timeout_seconds"], log)
                        case["preparation"].append({"label": label, "status": "success", "seconds": seconds})
                except Exception as error:
                    case["preparation_error"] = traceback.format_exc(); checkpoint(state)
                    print(f"{case['id']}: preparation failed: {error}", flush=True); continue
                checkpoint(state)
            if case.get("preparation_error"):
                continue
            completed = {(m["trial"], m["variant"]) for m in case["measurements"]}
            for trial in range(1, TRIALS + 1):
                order = VARIANTS if trial % 2 else VARIANTS[::-1]
                for variant in order:
                    if (trial, variant) in completed:
                        continue
                    item = {"trial": trial, "variant": variant, "started_utc": now(), "status": "success", "seconds": None, "error": ""}
                    try:
                        item["seconds"] = benchmark.verify_pair(verifier, objects[variant], objects[variant], case["entry"],
                            f"trial_{trial}_{variant}", state["timeout_seconds"], log)
                    except Exception as error:
                        item["status"] = "timeout" if isinstance(error, TimeoutError) else "failed"
                        item["error"] = f"{type(error).__name__}: {error}"
                        print(f"{case['id']} trial{trial} {variant}: {item['error']}", flush=True)
                    case["measurements"].append(item); checkpoint(state)
                partial = summarize(state)
                row = next(r for r in partial if r["id"] == case["id"])
                m = row.get("median_seconds", {})
                print(json.dumps({"case": case["id"], "paired_trials": trial, "of": TRIALS,
                                  "median_seconds": m, "failures": len(row["failures"]), "utc": now()}), flush=True)
    if all(len(c["measurements"]) == 2 * TRIALS for c in state["cases"]):
        state["finished_utc"] = now()
    state["isolation"] = "One fresh Python process per case, sequential; persistent within each case"
    checkpoint(state)
    print(f"Case process finished: {args.case}", flush=True)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(REPO / "c2rust_translation"))
    raise SystemExit(main())
