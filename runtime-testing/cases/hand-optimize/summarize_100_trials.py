#!/usr/bin/env python3
"""Reproduce the saved 20261102T101430Z study, including its interpretation.

Never launches a verification call. For new experiments use benchmark_100_trials.py.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CASES = ["tcpsynbl", "funclatency", "fsdist", "biostacks", "biolatency"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize(directory):
    if directory.name != "20261102T101430Z":
        raise ValueError("This reporter includes interpretation specific to the 20261102T101430Z study.")
    summaries, protocols, intervals, rows = {}, {}, [], []
    proof_count = 0
    previous_notes_time = None
    for case in CASES:
        path = directory / case
        summary = json.loads((path / "summary.json").read_text())
        protocol = json.loads((path / "protocol.json").read_text())
        objects = json.loads((path / "objects.json").read_text())
        assert summary["complete"] and summary["error"] is None, case
        assert summary["recorded_pairs"] == summary["complete_pairs"] == 100, case
        assert not any(summary["failed_rounds"].values()), case
        assert len(summary["rounds"]) == 100, case
        assert set(summary["proofs"]) == set(objects["original"]["entries"]), case
        assert objects["original"]["entries"] == objects["optimized"]["entries"], case
        assert all(p["passed"] and p["complete"] for p in summary["proofs"].values()), case
        proof_count += len(summary["proofs"])
        for variant in ["original", "optimized"]:
            source = HERE / protocol["case"][variant]
            assert sha(source) == protocol["source_sha256"][variant], str(source)
            samples = [r["results"][variant]["seconds"] for r in summary["rounds"]]
            stats = summary["statistics"][variant]
            assert stats["n"] == len(samples) == 100, (case, variant)
            assert all(math.isfinite(x) and x > 0 for x in samples), case
            assert math.isclose(statistics.median(samples), stats["median"]), case
            assert math.isclose(statistics.mean(samples), stats["mean"]), case
            assert math.isclose(statistics.stdev(samples), stats["stdev"]), case
        if protocols:
            previous = next(iter(protocols.values()))
            for key in ["code_sha256", "compiler", "clang_version", "compiler_flags",
                        "dependencies", "python", "timeout_process_wall_seconds"]:
                assert protocol[key] == previous[key], (case, key)
        for relative, expected in protocol["code_sha256"].items():
            assert sha(REPO / relative) == expected, relative
        journal = [json.loads(line) for line in (path / "journal.jsonl").read_text().splitlines()]
        labels = [item["label"] for item in journal]
        assert len(labels) == len(set(labels)) == 202 + len(summary["proofs"]), case
        attempts = sorted((path / "calls").glob("*.attempt.json"))
        assert len(attempts) == len(journal), case
        local_intervals = []
        for attempt in attempts:
            marker = json.loads(attempt.read_text())
            result = json.loads((path / "calls" / (marker["label"] + ".json")).read_text())
            assert result["passed"] and result["complete"], (case, marker["label"])
            assert result == next(item for item in journal if item["label"] == marker["label"])
            start = datetime.fromisoformat(marker["started_utc"])
            end = datetime.fromisoformat(result["finished_utc"])
            assert start < end
            local_intervals.append((start, end, case, marker["label"]))
        for index, recorded in enumerate(summary["rounds"], 1):
            assert recorded["round"] == index
            expected = ["original", "optimized"] if index % 2 else ["optimized", "original"]
            assert recorded["order"] == expected, (case, index)
            actual = sorted(expected, key=lambda v: next(
                item[0] for item in local_intervals if item[3] == f"trial_{index:03d}_{v}"))
            assert actual == expected, (case, index)
        assert all((path / f).exists() for f in ["REPORT.md", "AGENT_NOTES.md", "stability.png", "stability.svg"])
        first_start = min(item[0].timestamp() for item in local_intervals)
        if previous_notes_time is not None:
            assert previous_notes_time <= first_start, (case, "started before previous notes")
        previous_notes_time = (path / "AGENT_NOTES.md").stat().st_mtime
        intervals.extend(local_intervals)
        summaries[case], protocols[case] = summary, protocol
        rows.append({"case": case, "timed_entry": protocol["case"]["timed_entry"],
                     **{k: v for k, v in summary.items() if k not in ["rounds", "proofs"]},
                     "proofs_passed": len(summary["proofs"]),
                     "report": case + "/REPORT.md", "notes": case + "/AGENT_NOTES.md"})
    intervals.sort()
    assert all(a[1] <= b[0] for a, b in zip(intervals, intervals[1:])), "Overlapping calls"
    audit = {"audited_utc": datetime.now(timezone.utc).isoformat(), "passed": True,
             "timed_calls": 1000, "untimed_warmups": 10, "equivalence_proofs": proof_count,
             "total_serial_calls": len(intervals), "unique_attempts_and_results": True,
             "alternating_order_confirmed": True, "no_overlapping_calls": True,
             "previous_case_notes_before_next_case_start": True,
             "all_frozen_source_and_code_hashes_match": True,
             "all_cases_share_compiler_dependencies_and_code": True}
    (directory / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    (directory / "summary-100.json").write_text(json.dumps({"audit": audit, "cases": rows}, indent=2) + "\n")

    os.environ.setdefault("MPLCONFIGDIR", str(directory / "matplotlib-cache"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    fig, (ax, benefit) = plt.subplots(1, 2, figsize=(13.5, 5.5), gridspec_kw={"width_ratios": [1.7, 1]})
    x, width = np.arange(len(CASES)), .36
    colors = {"original": "#516d91", "optimized": "#229e89"}
    for variant, offset in [("original", -width / 2), ("optimized", width / 2)]:
        stats = [summaries[c]["statistics"][variant] for c in CASES]
        medians = [s["median"] for s in stats]
        errors = [[s["median"] - s["p05"] for s in stats], [s["p95"] - s["median"] for s in stats]]
        bars = ax.bar(x + offset, medians, width, label=variant.capitalize(), color=colors[variant],
                      yerr=errors, capsize=3, error_kw={"linewidth": 1})
        for bar, s in zip(bars, stats):
            ax.text(bar.get_x() + bar.get_width()/2, s["p95"] + .8, f'{s["median"]:.2f}',
                    ha="center", va="bottom", fontsize=8)
    ax.set(xticks=x, xticklabels=CASES, ylabel="Heimdall self-equivalence time (seconds)",
           title="Runtime: median and 5th–95th percentiles", ylim=(0, 73))
    ax.legend(frameon=False)
    reductions = [summaries[c]["median_time_reduction_percent"] for c in CASES]
    cis = [summaries[c]["paired_bootstrap_ci95_reduction_percent"] for c in CASES]
    benefit.barh(x, reductions, color="#229e89", height=.55,
                 xerr=[[v-ci[0] for v, ci in zip(reductions, cis)],
                       [ci[1]-v for v, ci in zip(reductions, cis)]], capsize=4)
    for i, value in enumerate(reductions):
        benefit.text(value + 1.1, i, f"{value:.2f}%", va="center", fontsize=9)
    benefit.set(yticks=x, yticklabels=CASES, xlim=(0, 107), xlabel="Median time reduction (%)",
                title="Reduction and paired-bootstrap 95% interval")
    benefit.invert_yaxis()
    for panel in [ax, benefit]:
        panel.spines[["top", "right"]].set_visible(False)
        panel.grid(axis="y" if panel is ax else "x", alpha=.18)
        panel.set_axisbelow(True)
    fig.suptitle("100 trials per variant · cases and verification calls run sequentially", fontsize=13)
    fig.text(.5, .015, "All 1,000 timings retained; 0 failures. Percentile whiskers show timing spread, not confidence intervals.",
             ha="center", fontsize=9)
    fig.tight_layout(rect=(0, .05, 1, .94))
    for extension in ["png", "svg"]:
        fig.savefig(directory / ("runtime-comparison-100." + extension), dpi=180)
    plt.close(fig)

    lines = ["# Five-program 100-trial stability results", "",
             "All five cases completed sequentially, using one Luna agent and the frozen protocol. "
             "Each case has 100 original and 100 optimized observations: **1,000 successful timed calls, "
             "zero failures/timeouts/interrupted calls, and 39/39 exported-entry equivalence proofs passed**. "
             "All samples, including outliers, are retained.", "",
             "| Program | Original median s | Optimized median s | Reduction | Paired-bootstrap 95% interval | Proofs |",
             "| --- | ---: | ---: | ---: | --- | ---: |"]
    for c in CASES:
        s = summaries[c]; a, b = (s["statistics"][v] for v in ["original", "optimized"])
        low, high = s["paired_bootstrap_ci95_reduction_percent"]
        lines.append(f'| [{c}]({c}/AGENT_NOTES.md) | {a["median"]:.3f} | {b["median"]:.3f} | '
                     f'{s["median_time_reduction_percent"]:.2f}% | {low:.2f}–{high:.2f}% | {len(s["proofs"])}/{len(s["proofs"])} |')
    lines += ["", "![100-trial runtime comparison](runtime-comparison-100.png)", "",
              "## Stability", "",
              "The before/after reductions are repeatable in these observations, but absolute timing stability varies. "
              "`biostacks` has the lowest relative variation and little directional drift. The other four cases "
              "show slow clusters, level shifts, drift, or larger outliers. No formal stationarity test was prespecified; "
              "these assessments describe the saved series, quantiles, and ten-round block medians.", "",
              "| Program | Original CV | Optimized CV | First-to-last 25 median change, original / optimized |",
              "| --- | ---: | ---: | --- |"]
    for c in CASES:
        a, b = (summaries[c]["statistics"][v] for v in ["original", "optimized"])
        drift = [100 * (s["last_25_median"] / s["first_25_median"] - 1) for s in [a, b]]
        lines.append(f'| {c} | {a["cv_percent"]:.2f}% | {b["cv_percent"]:.2f}% | {drift[0]:+.2f}% / {drift[1]:+.2f}% |')
    lines += ["", "CV is sample standard deviation divided by mean; lower is less relative variation. "
              "First/last comparisons can hide changes in the middle, so inspect each case's full chart and notes.", "",
              "- **tcpsynbl:** late slowdown; optimized maximum 5.613 s in round 95; relatively high optimized CV.",
              "- **funclatency:** early calls are slower, followed by lower timing levels. Full-run stationarity is not established.",
              "- **fsdist:** level shift after the first ten rounds and several elevated clusters, despite similar first/last medians.",
              "- **biostacks:** comparatively narrow bands, little directional drift; retained maxima 66.146 s original and 4.054 s optimized.",
              "- **biolatency:** slow cluster around rounds 34–43 and higher last-25 medians; full-run stationarity is not established.", "",
              "The fixed 10,000-resample paired bootstrap (seed 984) resamples individual whole rounds. "
              "It describes this run's median reduction; serial dependence and drift can make these intervals optimistic. "
              "They do not establish stationarity or predict timing on another machine/day.", "",
              "## What was timed", "",
              "The unchanged worker times the complete `run_verification` call for a selected entry, original against "
              "itself and optimized against itself. This matches the prior five-trial comparison. Imports, process startup, "
              "compilation, and reporting are excluded. These are not eBPF execution times or timings of an original-to-optimized proof. "
              "Correctness is checked separately with original-to-optimized proofs for every exported entry under Heimdall's "
              "existing model and defaults. No added input assumptions or reduced observations were used.", "",
              "Each round runs in fresh processes, alternating original-first/optimized-first (50 rounds each). "
              "There is one untimed warm-up per variant and an unchanged 120-second process limit. "
              "Clang 22.1.8 compiles both versions with the same `bpfel -O2` flags. "
              "See [the protocol](../../PROTOCOL_100.md) and each case's `protocol.json` for frozen configuration and hashes.", "",
              "Luna reached its usage limit during `biolatency`, but the existing controller kept running. "
              "After the user requested continuation, the same agent reattached to it. No controller or trial was restarted, "
              "and no sample was lost or replaced. The slowdown cluster is retained without attributing it to a particular cause.", "",
              "## Saved artifacts and audit", "",
              "[Benchmark runner](../../benchmark_100_trials.py) · [Summary/plot generator](../../summarize_100_trials.py) · "
              "[Machine-readable summary](summary-100.json) · [Audit](audit.json) · [SVG figure](runtime-comparison-100.svg)", "",
              "The audit confirms 1,049 unique serial verification calls (1,000 timed + 10 warm-ups + 39 proofs), "
              "no overlapping calls, balanced alternating order, previous case notes written before the next case started, "
              "all ten source hashes unchanged, and identical frozen compiler/dependency/code fingerprints across cases. "
              "The source, verifier, backend, header, and runner hashes still match their pre-run records. "
              "Each case retains per-call attempt markers, JSON, logs, journal, statistics, and full timing charts. "
              "Earlier five-trial artifacts were not overwritten.", ""]
    (directory / "SUMMARY_100.md").write_text("\n".join(lines))
    print(json.dumps(audit, indent=2))
    print(directory / "SUMMARY_100.md")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    summarize(parser.parse_args().run_dir.resolve())
