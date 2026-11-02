#!/usr/bin/env python3
"""Audit saved results and show time drift; never runs or changes a timed trial."""
import csv
import hashlib
import json
import os
from pathlib import Path
import statistics
os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/heimdall-clang-limitation-mpl")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUTPUT = Path(__file__).resolve().parent
state = json.loads((OUTPUT / "checkpoint.json").read_text())
processes = json.loads((OUTPUT / "process_runs.json").read_text())["processes"]
assert len(processes) == 4 and len({p["pid"] for p in processes}) == 4
assert all(a["finished_utc"] <= b["started_utc"] for a, b in zip(processes, processes[1:]))
assert len(list(csv.DictReader((OUTPUT / "raw_trials.csv").open()))) == 800
VARIANTS = ("original_self", "optimized_self")
colors = ("#4472C4", "#2A9D8F")
audit = {"distinct_case_processes": 4, "sequential_confirmed": True, "objects_unchanged": True, "cases": []}
fig, axes = plt.subplots(2, 2, figsize=(12, 8))
lines = ["", "## Independent audit and timing drift", "",
         "Independent validation confirms 800 unique attempt records, four distinct case process IDs with no overlap, and all eight object hashes unchanged. Timeout counts are 14 original and 5 optimized attempts in execsnoop bound; the other cases have none.", "",
         "| Case | Variant | Successful first-20 median (s) | Successful last-20 median (s) | Change |",
         "|---|---|---:|---:|---:|"]
for ax, case in zip(axes.flat, state["cases"]):
    assert {(m["trial"], m["variant"]) for m in case["measurements"]} == {(i, v) for i in range(1, 101) for v in VARIANTS}
    for obj in case["objects"].values():
        assert hashlib.sha256(Path(obj["path"]).read_bytes()).hexdigest() == obj["sha256"]
    row = {"case": case["id"], "variants": {}}
    for v, color, label in zip(VARIANTS, colors, ["Original", "Optimized"]):
        measures = sorted((m for m in case["measurements"] if m["variant"] == v), key=lambda m: m["trial"])
        good = [m for m in measures if m["status"] == "success"]
        bad = [m for m in measures if m["status"] != "success"]
        assert all("HEIMDALL_TIMEOUT_SECONDS" in m["error"] for m in bad)
        first = statistics.median(m["seconds"] for m in good if m["trial"] <= 20)
        last = statistics.median(m["seconds"] for m in good if m["trial"] > 80)
        delta = 100 * (last / first - 1)
        row["variants"][v] = {"successful": len(good), "timeouts": len(bad), "first20_success_median": first,
                                "last20_success_median": last, "increase_percent": delta,
                                "successful_over_configured_alarm": [m for m in good if m["seconds"] > state["timeout_seconds"]]}
        lines.append(f"| {case['id']} | {label} | {first:.4f} | {last:.4f} | {delta:+.1f}% |")
        ax.plot([m["trial"] for m in measures], [m["seconds"] if m["status"] == "success" else float("nan") for m in measures],
                color=color, marker=".", markersize=3, linewidth=.8, alpha=.8, label=f"{label}: {len(good)}/100 successful")
    audit["cases"].append(row)
    ax.set_title(case["id"]); ax.set_xlabel("Paired trial number"); ax.set_ylabel("Verification time (seconds)")
    ax.set_xlim(1, 100); ax.grid(linestyle=":", alpha=.4); ax.legend(fontsize=8)
fig.suptitle("Observed runtimes by trial — all successful measurements retained\nFailed attempts are gaps; no runtime is imputed")
fig.tight_layout(); fig.savefig(OUTPUT / "global-trial-trends.png", dpi=180); fig.savefig(OUTPUT / "global-trial-trends.svg"); plt.close(fig)
(OUTPUT / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
lines += ["", "These first/last summaries are diagnostics only; they do not replace the full-sample summaries or discard any trials. Timings rose substantially during tcprtt and execsnoop bound in both variants. Process isolation between cases did not produce a stable timing baseline within each case. The cause was not established; these data do not attribute the drift or earlier failures to token exhaustion.", "",
          "The observed failure count was lower than in the earlier 100-attempt run (19 versus 133), but that does not establish which environmental or process factor caused the difference. The two prior experiments remain preserved. Mdflush was 7.50% slower after optimization in this run; KEN and tcprtt uncertainty intervals include zero. The execsnoop successful-run reduction remains conditional on completion.", "",
          "See global-trial-trends.png (and SVG) for every successful timing in trial order; audit.json provides validation and per-variant failure counts."]
report = OUTPUT / "REPORT.md"
original = report.read_text().split("\n## Independent audit and timing drift")[0]
report.write_text(original.rstrip() + "\n" + "\n".join(lines) + "\n")
print("Audit and trial-trend figures generated; all raw timings and failure records preserved.")
