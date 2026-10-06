#!/usr/bin/env python3
"""Time Heimdall self-verification of the optimized and unoptimized BPF objects."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from time import perf_counter


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent
VERIFIER_DIR = REPO_DIR / "c2rust_translation"
VERIFIER = VERIFIER_DIR / "verify_mixed_entries.py"
ENTRY = "blk_account_io_done"


def verifier_python() -> str:
    candidates = [os.environ.get("HEIMDALL_PYTHON"), sys.executable,
                  str(Path.home() / "miniconda3/envs/c2rust/bin/python")]
    for candidate in candidates:
        if not candidate:
            continue
        resolved = shutil.which(candidate)
        if not resolved:
            continue
        try:
            check = subprocess.run([resolved, "-c", "import angr, matplotlib"],
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, check=False)
        except OSError:
            continue
        if check.returncode == 0:
            return resolved
    raise RuntimeError("No Python with angr and matplotlib found; set HEIMDALL_PYTHON")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", help="Case directory name, e.g. chain-of-updates")
    args = parser.parse_args()

    case_dir = SCRIPT_DIR / args.case
    if (not args.case or args.case in {".", ".."} or
            Path(args.case).name != args.case or not case_dir.is_dir() or
            not (case_dir / "program.bpf.c").is_file()):
        parser.error(f"unknown case directory: {args.case}")

    python = verifier_python()
    if Path(python).resolve() != Path(sys.executable).resolve():
        os.execvp(python, [python, str(Path(__file__).resolve()), *sys.argv[1:]])
    results = []
    for variant in ("default", "no-opt"):
        obj = case_dir / f"{variant}.o"
        if not obj.is_file():
            parser.error(f"missing {obj}; run ./compile.sh {args.case} first")

        command = [python, "-B", str(VERIFIER),
                   str(obj), str(obj), ENTRY, ENTRY,
                   "--z3-output", str(case_dir / f"{variant}-z3.txt")]
        print(f"Running {variant}.o against itself...", flush=True)
        started = perf_counter()
        completed = subprocess.run(command, cwd=VERIFIER_DIR,
                                   text=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, check=False)
        elapsed = perf_counter() - started
        results.append({"variant": variant, "seconds": elapsed,
                        "returncode": completed.returncode})
        print(f"  {elapsed:.3f} s; exit {completed.returncode}", flush=True)
        if completed.returncode != 0:
            print(completed.stdout, file=sys.stderr)

    if any(result["returncode"] != 0 for result in results):
        print("Verification failed; no chart was generated.",
              file=sys.stderr)
        return 1

    mpl_dir = Path(tempfile.gettempdir()) / f"clang-opt-mpl-{os.getuid()}"
    mpl_dir.mkdir(exist_ok=True)
    os.environ["MPLCONFIGDIR"] = str(mpl_dir)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6, 4))
    values = [result["seconds"] for result in results]
    bars = ax.bar(["default (-O2)", "no-opt (-O0)"], values,
                  color=["#2878B5", "#D98236"])
    ax.bar_label(bars, fmt="%.2f s", padding=3)
    ax.set_ylim(0, max(values) * 1.18 if max(values) else 1)
    ax.set_ylabel("Wall-clock verification time (seconds)")
    ax.set_title(f"Heimdall self-verification: {args.case}")
    fig.tight_layout()
    chart_path = case_dir / "verification-times.png"
    fig.savefig(chart_path, dpi=160)
    plt.close(fig)

    print(f"Chart: {chart_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
