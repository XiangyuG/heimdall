"""Private benchmark helpers for real-program experiments; timing logic preserved."""
import contextlib
import gc
import io
import json
import os
from pathlib import Path
import random
import re
import shutil
import signal
import statistics
import subprocess
import sys
import time
from ast_utils import find_clang

def select_python():
    candidates = [os.environ.get("HEIMDALL_VERIFY_PYTHON"), sys.executable,
                  str(Path.home() / "miniconda3/envs/c2rust/bin/python")]
    if os.environ.get("HEIMDALL_VERIFY_PYTHON"):
        candidates = candidates[:1]
    for candidate in candidates:
        python = shutil.which(candidate) if candidate else None
        if python:
            probe = subprocess.run([python, "-B", "-c", "import angr, z3, matplotlib, elftools"],
                                   capture_output=True)
            if probe.returncode == 0:
                return python
    raise ValueError("Heimdall dependencies unavailable; set HEIMDALL_VERIFY_PYTHON")

def executable_code(path):
    from elftools.elf.elffile import ELFFile
    with path.open("rb") as stream:
        elf = ELFFile(stream)
        return {s.name: s.data() for s in elf.iter_sections() if s["sh_flags"] & 4 and s.data_size}

def entries(path):
    from elftools.elf.elffile import ELFFile
    with path.open("rb") as stream:
        elf = ELFFile(stream)
        symbols = elf.get_section_by_name(".symtab")
        result = []
        for symbol in symbols.iter_symbols() if symbols else []:
            index = symbol["st_shndx"]
            if (symbol["st_info"]["type"] == "STT_FUNC" and symbol["st_info"]["bind"] == "STB_GLOBAL"
                    and isinstance(index, int) and index > 0
                    and elf.get_section(index).name != ".text"):
                result.append(symbol.name)
        return result

def timeout_handler(signum, frame):
    raise TimeoutError("verification exceeded HEIMDALL_TIMEOUT_SECONDS")

def verify_pair(verifier, left, right, entry, label, timeout, log, witness=None):
    gc.collect()
    buffer = io.StringIO()
    log.write(f"\n--- {label}: {left.name} vs {right.name} ---\n")
    log.flush()
    started = time.perf_counter()
    signal.alarm(timeout)
    try:
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            result = verifier.run_verification(str(left), str(right), entry, [], witness=witness)
        elapsed = time.perf_counter() - started
        # All benchmark loops have finite bounds under the recorded inputs. Any leftover execution
        # or errored path is a failed trial, even if a partial formula says UNSAT.
        output = buffer.getvalue()
        bad_stash = re.search(r"stash '(?:active|errored|unconstrained|deferred|stashed|cut)':\s*([1-9]\d*)", output)
        errored = re.search(r"errored=([1-9]\d*)", output)
        if not result.equivalent or bad_stash or errored:
            raise RuntimeError(f"incomplete/failed verification: {result.result_type}; {result.counter_example}")
        log.write(output)
        log.write(json.dumps({"label": label, "seconds": elapsed, "equivalent": result.equivalent,
                              "result_type": result.result_type}) + "\n")
        log.flush()
        return elapsed
    except BaseException:
        log.write(buffer.getvalue())
        raise
    finally:
        signal.alarm(0)

def bootstrap_reduction(original, optimized):
    rng = random.Random(984)
    samples = []
    for _ in range(10000):
        indices = [rng.randrange(len(original)) for _ in original]
        samples.append(100 * (1 - statistics.median(optimized[i] for i in indices)
                              / statistics.median(original[i] for i in indices)))
    samples.sort()
    return [samples[250], samples[9749]]

def chart(path, original_name, optimized_name, times, input_label=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    labels = [original_name, optimized_name]
    values = [statistics.median(times[k]) for k in ("original_self", "optimized_self")]
    fig, ax = plt.subplots(figsize=(8, 4.8))
    bars = ax.bar(["Original + Clang -O2", "Source optimized + Clang -O2"], values,
                  color=["#4472C4", "#2A9D8F"])
    for i, key in enumerate(("original_self", "optimized_self")):
        ax.scatter([i] * len(times[key]), times[key], s=16, color="black", alpha=0.35, zorder=3)
    ax.bar_label(bars, fmt="%.3f s", padding=5)
    ax.set_ylabel("Total Heimdall self-verification time (seconds)")
    reduction = 100 * (1 - values[1] / values[0])
    input_note = f"; {input_label}" if input_label else ""
    ax.set_title(f"{labels[0]}\nMedian of {len(times['original_self'])} trials{input_note}; reduction {reduction:.1f}%")
    ax.set_ylim(0, max(max(times[k]) for k in ("original_self", "optimized_self")) * 1.18)
    ax.grid(axis="y", linestyle=":", alpha=0.4)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
