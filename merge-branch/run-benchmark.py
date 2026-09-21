#!/usr/bin/env python3
"""Compare verification runtimes for branch-merging strategies."""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import TextIO


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent
BYTES_DIR = SCRIPT_DIR / "bytes"
RESULTS_DIR = SCRIPT_DIR / "results"
TRANSLATION_DIR = REPO_DIR / "c2rust_translation"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare self-equivalence verification runtimes."
    )
    parser.add_argument(
        "--case",
        required=True,
        help="name of the original .o file in bytes/ (paths are not accepted)",
    )
    parser.add_argument(
        "--test",
        choices=("source", "exec"),
        help=(
            "optimization to compare with the original; "
            "omit to compare both source and in-execution optimization"
        ),
    )
    parser.add_argument(
        "--entry",
        required=True,
        help="entry-point symbol to verify",
    )
    return parser.parse_args()


def resolve_original(case_argument: str) -> Path:
    """Resolve the original object name strictly within ``bytes/``."""

    if Path(case_argument).name != case_argument:
        raise ValueError("--case must be a file name from bytes/, not a path")
    if Path(case_argument).suffix != ".o":
        raise ValueError("--case must name an .o file")
    if Path(case_argument).stem.endswith("_MERGED"):
        raise ValueError("--case must name the original object, not a _MERGED.o file")

    object_path = BYTES_DIR / case_argument
    if not object_path.is_file():
        available = ", ".join(
            path.name
            for path in sorted(BYTES_DIR.glob("*.o"))
            if not path.stem.endswith("_MERGED")
        )
        raise FileNotFoundError(
            f"original object file {case_argument!r} was not found in {BYTES_DIR}; "
            f"available original cases: {available or '(none)'}"
        )
    return object_path


def resolve_source_optimized(original_path: Path) -> Path:
    """Return the source-optimized companion for an original object."""

    optimized_path = original_path.with_name(f"{original_path.stem}_MERGED.o")
    if not optimized_path.is_file():
        raise FileNotFoundError(
            "source-optimized object file "
            f"{optimized_path.name!r} was not found in {BYTES_DIR}"
        )
    return optimized_path


def build_schedule(
    original_path: Path, selected_test: str | None
) -> list[tuple[str, Path, bool]]:
    """Build the baseline-plus-selected-optimizations benchmark schedule."""

    scheduled = [("Original", original_path, False)]
    if selected_test in (None, "source"):
        source_path = resolve_source_optimized(original_path)
        scheduled.append(("Source optimization", source_path, False))
    if selected_test in (None, "exec"):
        scheduled.append(("In-exec optimization", original_path, True))
    return scheduled


def create_result_directory(case_name: str, test_name: str) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    result_dir = RESULTS_DIR / f"{case_name}_{test_name}_{timestamp}"
    result_dir.mkdir()
    return result_dir


def run_one_verification(
    *,
    label: str,
    object_path: Path,
    entry_symbol: str,
    online: bool,
    log_file: TextIO,
) -> dict:
    """Run one object against itself and return the full verifier runtime."""

    import verify_equivalence

    online_statistics: dict = {}
    restore_online = None
    result = None
    failure = None
    total_seconds = 0.0

    with contextlib.redirect_stdout(log_file), contextlib.redirect_stderr(log_file):
        print("=" * 72)
        print(f"benchmark: {label}")
        print(f"object: {object_path.resolve()}")
        print(f"entry: {entry_symbol}")
        print("=" * 72)

        try:
            if online:
                from in_execution_opt.online_merge import (
                    find_forward_conditional_join_offsets,
                    install_online_merging,
                )

                join_offsets = find_forward_conditional_join_offsets(
                    object_path, entry_symbol
                )
                online_statistics, restore_online = install_online_merging(
                    join_offsets
                )

            started = time.perf_counter()
            try:
                result = verify_equivalence.run_verification(
                    str(object_path.resolve()),
                    str(object_path.resolve()),
                    entry_symbol,
                    [],
                )
            finally:
                total_seconds = time.perf_counter() - started
        except Exception as error:  # Keep the complete failure in log.txt.
            failure = error
            traceback.print_exc()
        finally:
            if restore_online is not None:
                restore_online()

        if result is not None:
            print()
            print(f"equivalent: {result.equivalent}")
            print(f"result_type: {result.result_type}")
        print(f"total_seconds: {total_seconds:.6f}")
        print()

    benchmark = {
        "label": label,
        "object": str(object_path.resolve()),
        "equivalent": result.equivalent if result is not None else False,
        "result_type": result.result_type if result is not None else "error",
        "total_seconds": total_seconds,
        **online_statistics,
    }
    if failure is not None:
        benchmark["error"] = f"{type(failure).__name__}: {failure}"
    return benchmark


def save_timing_graph(
    case_name: str,
    selected_test: str,
    benchmarks: list[dict],
    output_path: Path,
) -> None:
    """Save a bar graph comparing complete verification runtimes."""

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as error:
        raise RuntimeError(
            "matplotlib is required to generate the benchmark timing graph"
        ) from error

    labels = [benchmark["label"] for benchmark in benchmarks]
    seconds = [benchmark["total_seconds"] for benchmark in benchmarks]
    colors = [
        "#4472C4"
        if benchmark["equivalent"] and not benchmark.get("error")
        else "#C94C4C"
        for benchmark in benchmarks
    ]

    figure, axis = plt.subplots(figsize=(max(7, len(labels) * 2.2), 5))
    bars = axis.bar(labels, seconds, color=colors)
    axis.set_ylabel("Verification runtime (seconds)")
    axis.set_title(f"{case_name} — {selected_test} benchmark")
    axis.grid(axis="y", linestyle=":", alpha=0.5)
    for bar, elapsed in zip(bars, seconds):
        axis.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"{elapsed:.3f}s",
            ha="center",
            va="bottom",
        )
    figure.tight_layout()
    figure.savefig(output_path, dpi=160)
    plt.close(figure)


def main() -> int:
    args = parse_args()
    if not args.entry.strip():
        print("error: --entry must not be empty", file=sys.stderr)
        return 2

    try:
        original_path = resolve_original(args.case)
        scheduled = build_schedule(original_path, args.test)
    except (ValueError, FileNotFoundError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    selected_test = args.test or "all"
    result_dir = create_result_directory(original_path.name, selected_test)
    log_path = result_dir / "log.txt"
    graph_path = result_dir / "runtime.png"
    summary_path = result_dir / "benchmark_results.json"

    sys.path.insert(0, str(SCRIPT_DIR))
    sys.path.insert(0, str(TRANSLATION_DIR))

    print(f"Benchmarking {original_path.name} ({selected_test})", flush=True)
    print(f"Results directory: {result_dir}", flush=True)

    benchmarks = []
    with log_path.open("w", encoding="utf-8") as log_file:
        for label, object_path, online in scheduled:
            print(f"Running {label}...", flush=True)
            benchmark = run_one_verification(
                label=label,
                object_path=object_path,
                entry_symbol=args.entry,
                online=online,
                log_file=log_file,
            )
            benchmarks.append(benchmark)
            print(f"  {benchmark['total_seconds']:.3f}s", flush=True)

    summary = {
        "case": original_path.name,
        "test": selected_test,
        "entry": args.entry,
        "log": str(log_path.resolve()),
        "benchmarks": benchmarks,
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    try:
        save_timing_graph(original_path.name, selected_test, benchmarks, graph_path)
    except RuntimeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    print(f"Log:   {log_path}")
    print(f"Graph: {graph_path}")
    print(f"Data:  {summary_path}")

    failures = [
        benchmark
        for benchmark in benchmarks
        if benchmark.get("error")
        or not benchmark["equivalent"]
        or benchmark["result_type"] != "equivalent"
    ]
    if failures:
        labels = ", ".join(benchmark["label"] for benchmark in failures)
        print(f"error: verification failed for: {labels}; see {log_path}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
