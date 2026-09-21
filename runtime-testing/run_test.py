#!/usr/bin/env python3
"""Compile and benchmark one Heimdall runtime-test suite."""

from __future__ import annotations

import argparse
import csv
import os
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

try:
    import matplotlib.pyplot as plt
except ModuleNotFoundError:
    plt = None


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent
CASES_DIR = SCRIPT_DIR / "cases"
OUTPUT_DIR = SCRIPT_DIR / "output"
VERIFY_SCRIPT = REPO_DIR / "c2rust_translation" / "verify_mixed_entries.py"
ENTRY_SYMBOL = "blk_account_io_done"


@dataclass(frozen=True)
class Suite:
    source_directory: str
    recursive: bool = False


SUITES = {
    "branch_expand": Suite("branch_expand"),
    "helper_expand": Suite("helper_expand"),
    "nest_expand": Suite("nest_expand"),
    "branch_helper_nest": Suite("branch_helper_nest"),
    "branch_helper_nest_basic": Suite("branch_helper_nest_basic"),
    "slot_operations": Suite("slot_operations", recursive=True),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compile every standalone eBPF program in one suite and measure "
            "Heimdall self-equivalence verification time."
        )
    )
    parser.add_argument(
        "--case",
        required=True,
        choices=tuple(SUITES),
        help="test suite to run",
    )
    return parser.parse_args()


def find_bpf_clang() -> str:
    candidates = (
        os.environ.get("BPF_CLANG"),
        "/opt/homebrew/opt/llvm/bin/clang",
        "/usr/local/opt/llvm/bin/clang",
        shutil.which("clang"),
    )
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise RuntimeError("no BPF-capable clang found; set BPF_CLANG")


def create_run_directory(case_name: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = OUTPUT_DIR / f"{case_name}_{timestamp}"
    run_dir = base
    suffix = 2
    while run_dir.exists():
        run_dir = Path(f"{base}_{suffix}")
        suffix += 1
    run_dir.mkdir()
    (run_dir / "build").mkdir()
    (run_dir / "logs").mkdir()
    return run_dir


def discover_sources(suite: Suite) -> list[Path]:
    suite_dir = CASES_DIR / suite.source_directory
    iterator = suite_dir.rglob("*.bpf.c") if suite.recursive else suite_dir.glob("*.bpf.c")
    sources = sorted(iterator)
    if not sources:
        raise RuntimeError(f"no test programs found in {suite_dir}")
    return sources


def case_label(source: Path, suite_dir: Path) -> str:
    relative = source.relative_to(suite_dir)
    return str(relative).removesuffix(".bpf.c")


def safe_name(label: str) -> str:
    return label.replace("/", "__").replace(" ", "_")


def command_text(command: list[str]) -> str:
    return "$ " + shlex.join(command)


def run_program(
    *,
    label: str,
    source: Path,
    run_dir: Path,
    clang: str,
    verify_python: str,
) -> dict:
    name = safe_name(label)
    object_path = run_dir / "build" / f"{name}.o"
    log_path = run_dir / "logs" / f"{name}.log"
    compile_command = [
        clang,
        "-O2",
        "-g",
        "-target",
        "bpf",
        "-D__TARGET_ARCH_x86",
        "-I",
        str(SCRIPT_DIR / "include"),
        "-c",
        str(source),
        "-o",
        str(object_path),
    ]

    compile_started = time.perf_counter()
    compiled = subprocess.run(
        compile_command,
        cwd=REPO_DIR,
        text=True,
        capture_output=True,
        check=False,
    )
    compile_seconds = time.perf_counter() - compile_started
    log_sections = [command_text(compile_command), compiled.stdout, compiled.stderr]

    if compiled.returncode != 0:
        log_path.write_text("\n".join(log_sections), encoding="utf-8")
        return {
            "case": label,
            "source": str(source.relative_to(SCRIPT_DIR)),
            "object": str(object_path.relative_to(run_dir)),
            "compile_seconds": compile_seconds,
            "verify_seconds": 0.0,
            "status": "compile_failed",
            "equivalent": False,
            "log": str(log_path.relative_to(run_dir)),
        }

    verify_command = [
        verify_python,
        str(VERIFY_SCRIPT),
        str(object_path),
        str(object_path),
        ENTRY_SYMBOL,
        ENTRY_SYMBOL,
    ]
    verify_started = time.perf_counter()
    verified = subprocess.run(
        verify_command,
        cwd=REPO_DIR / "c2rust_translation",
        text=True,
        capture_output=True,
        check=False,
    )
    verify_seconds = time.perf_counter() - verify_started
    equivalent = verified.returncode == 0 and "equivalent: True" in verified.stdout
    status = "equivalent" if equivalent else f"verify_exit_{verified.returncode}"
    log_sections.extend(
        ["", command_text(verify_command), verified.stdout, verified.stderr]
    )
    log_path.write_text("\n".join(log_sections), encoding="utf-8")

    return {
        "case": label,
        "source": str(source.relative_to(SCRIPT_DIR)),
        "object": str(object_path.relative_to(run_dir)),
        "compile_seconds": compile_seconds,
        "verify_seconds": verify_seconds,
        "status": status,
        "equivalent": equivalent,
        "log": str(log_path.relative_to(run_dir)),
    }


def write_results(results: list[dict], output_path: Path) -> None:
    fields = (
        "case",
        "source",
        "object",
        "compile_seconds",
        "verify_seconds",
        "status",
        "equivalent",
        "log",
    )
    with output_path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields, dialect="excel-tab")
        writer.writeheader()
        writer.writerows(results)


def write_summary(
    *,
    case_name: str,
    results: list[dict],
    started_at: datetime,
    elapsed: float,
    output_path: Path,
) -> None:
    passed = sum(result["equivalent"] for result in results)
    failed = len(results) - passed
    lines = [
        f"case: {case_name}",
        f"started_at: {started_at.astimezone().isoformat()}",
        f"elapsed_seconds: {elapsed:.6f}",
        f"programs: {len(results)}",
        f"equivalent: {passed}",
        f"failed: {failed}",
        "",
    ]
    lines.extend(
        f"{result['case']}\t{result['status']}\t{result['verify_seconds']:.6f}s"
        for result in results
    )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def save_runtime_plot(case_name: str, results: list[dict], output_path: Path) -> bool:
    if plt is None:
        return False

    labels = [result["case"] for result in results]
    runtimes = [result["verify_seconds"] for result in results]
    colors = ["#31965a" if result["equivalent"] else "#c94c4c" for result in results]
    width = max(11, len(results) * 0.72)
    figure, axis = plt.subplots(figsize=(width, 6))
    bars = axis.bar(labels, runtimes, color=colors)
    axis.set_xlabel("Test program")
    axis.set_ylabel("Verification runtime (seconds)")
    axis.set_title(f"Heimdall runtime test: {case_name}")
    axis.tick_params(axis="x", rotation=40, labelsize=8)
    axis.grid(axis="y", linestyle=":", alpha=0.5)
    for bar, result in zip(bars, results):
        axis.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"{result['verify_seconds']:.2f}s",
            ha="center",
            va="bottom",
            fontsize=7,
        )
    figure.tight_layout()
    figure.savefig(output_path, dpi=160)
    plt.close(figure)
    return True


def main() -> int:
    args = parse_args()
    suite = SUITES[args.case]
    suite_dir = CASES_DIR / suite.source_directory
    started_at = datetime.now().astimezone()
    run_started = time.perf_counter()

    try:
        clang = find_bpf_clang()
        sources = discover_sources(suite)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not VERIFY_SCRIPT.is_file():
        print(f"error: verifier not found: {VERIFY_SCRIPT}", file=sys.stderr)
        return 2

    verify_python = os.environ.get("HEIMDALL_VERIFY_PYTHON", sys.executable)
    run_dir = create_run_directory(args.case)
    print(f"Output: {run_dir}")
    print(f"Programs: {len(sources)}")

    results = []
    for index, source in enumerate(sources, start=1):
        label = case_label(source, suite_dir)
        print(f"[{index}/{len(sources)}] {label}", flush=True)
        result = run_program(
            label=label,
            source=source,
            run_dir=run_dir,
            clang=clang,
            verify_python=verify_python,
        )
        results.append(result)
        write_results(results, run_dir / "results.tsv")
        print(
            f"    {result['status']} "
            f"(compile {result['compile_seconds']:.2f}s, "
            f"verify {result['verify_seconds']:.2f}s)",
            flush=True,
        )

    elapsed = time.perf_counter() - run_started
    write_summary(
        case_name=args.case,
        results=results,
        started_at=started_at,
        elapsed=elapsed,
        output_path=run_dir / "summary.txt",
    )
    plotted = save_runtime_plot(args.case, results, run_dir / "runtime.png")
    if not plotted:
        print("Warning: matplotlib is unavailable; runtime.png was not created.")

    failures = [result for result in results if not result["equivalent"]]
    print(f"Results: {run_dir / 'results.tsv'}")
    print(f"Summary: {run_dir / 'summary.txt'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
