#!/usr/bin/env python3
"""Analyze saved standalone data without rerunning or changing any trial."""
import csv, hashlib, json, os, statistics
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/heimdall-clang-limitation-mpl")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
OUT = Path(__file__).resolve().parent
state = json.loads((OUT / "checkpoint.json").read_text())
assert len(state["cases"]) == 1
case = state["cases"][0]
variants = ("original_self", "optimized_self")
assert case["id"] == "execsnoop_bound"
assert {(m["trial"], m["variant"]) for m in case["measurements"]} == {(i, v) for i in range(1, 101) for v in variants}
assert len(case["measurements"]) == len(list(csv.DictReader((OUT / "raw_trials.csv").open()))) == 200
for obj in case["objects"].values():
    assert hashlib.sha256(Path(obj["path"]).read_bytes()).hexdigest() == obj["sha256"]
audit = {"case": case["id"], "unique_attempts": 200, "object_hashes_unchanged": True, "variants": {}}
lines = ["", "## Standalone audit", "",
         "The standalone experiment recorded all 200 scheduled attempts with unchanged original and optimized object hashes. Six original and one optimized attempt timed out. No failures were retried and no successful observations were removed.", "",
         "| Version | Successful first-20 median (s) | Successful last-20 median (s) | Timeout trials |",
         "|---|---:|---:|---|"]
fig, ax = plt.subplots(figsize=(9, 5))
for variant, color, label in zip(variants, ["#4472C4", "#2A9D8F"], ["Original", "Optimized"]):
    measurements = sorted((m for m in case["measurements"] if m["variant"] == variant), key=lambda m: m["trial"])
    good = [m for m in measurements if m["status"] == "success"]
    bad = [m for m in measurements if m["status"] != "success"]
    assert all("HEIMDALL_TIMEOUT_SECONDS" in m["error"] for m in bad)
    first = statistics.median(m["seconds"] for m in good if m["trial"] <= 20)
    last = statistics.median(m["seconds"] for m in good if m["trial"] > 80)
    row = {"successful": len(good), "timeouts": len(bad), "timeout_trials": [m["trial"] for m in bad],
           "first20_success_median": first, "last20_success_median": last,
           "successful_over_configured_alarm": [m for m in good if m["seconds"] > state["timeout_seconds"]]}
    audit["variants"][variant] = row
    lines.append(f"| {label} | {first:.4f} | {last:.4f} | {row['timeout_trials']} |")
    ax.plot([m["trial"] for m in measurements], [m["seconds"] if m["status"] == "success" else float("nan") for m in measurements],
            color=color, marker=".", markersize=4, linewidth=1, label=f"{label}: {len(good)}/100 successful")
ax.set_title("execsnoop_bound — standalone run, observed runtimes by trial\nTimeout attempts appear as gaps; no runtime is imputed")
ax.set_xlabel("Paired trial number"); ax.set_ylabel("Heimdall self-verification time (seconds)")
ax.set_xlim(1, 100); ax.set_ylim(bottom=0); ax.grid(linestyle=":", alpha=.4); ax.legend()
fig.tight_layout(); fig.savefig(OUT / "trial-trend.png", dpi=180); fig.savefig(OUT / "trial-trend.svg"); plt.close(fig)
(OUT / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
local = ZoneInfo("America/Los_Angeles")
started = datetime.fromisoformat(state["started_utc"]).astimezone(local)
finished = datetime.fromisoformat(state["finished_utc"]).astimezone(local)
lines += ["", f"Local run interval: {started.isoformat()} to {finished.isoformat()} (America/Los_Angeles).", "",
          "Runtimes again increased substantially in both versions during the standalone run. The first timeout occurred on original trial 86; optimized trial 91 also timed out. Thus running only this case did not eliminate late-run slowdown. The data show timing drift and timeout-triggered formula-generation errors; they do not diagnose whether the drift originates in retained verifier state, resource pressure, thermal behavior, or another factor. They do not identify token exhaustion as the cause.", "",
          "All successful times were below 60 seconds in this run, but the unchanged SIGALRM helper is not assumed to enforce a strict wall-time cap in general. No timeout completion time was imputed. Successful-run median reduction is 14.37% (1.168x), conditional on the 94/99 completed attempts; no full-sample confidence interval is reported because attempts failed.", "",
          "The original-version and optimized-version mean times among completed attempts are 32.5699 s and 29.4564 s; sample standard deviations are 14.5478 s and 15.1295 s. These broad distributions and the trial trend limit interpretation of an aggregate speedup. First/last-20 summaries are diagnostics and do not replace full-sample summaries.", "",
          "Figures: execsnoop_bound/runtime.png (median bars plus all successful measurements), execsnoop_bound/distribution.png (ECDF), trial-trend.png (timings by trial), and global-completions.png (completion counts). SVG versions are included. Previous experiments remain unchanged."]
report = OUT / "REPORT.md"
original = report.read_text().split("\n## Standalone audit")[0]
report.write_text(original.rstrip() + "\n" + "\n".join(lines) + "\n")
print("Standalone audit and trial-trend figure completed; raw records unchanged.")
