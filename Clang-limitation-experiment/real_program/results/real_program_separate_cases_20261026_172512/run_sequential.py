#!/usr/bin/env python3
"""Launch the four independent case processes serially; never replace failed attempts."""
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys

OUTPUT = Path(__file__).resolve().parent
WORKER = OUTPUT / "benchmark_100_trials.py"
CASES = ["ken_execsnoop_alignment", "mdflush_alignment", "tcprtt_alignment", "execsnoop_bound"]
def now(): return datetime.now(timezone.utc).isoformat()
def save(state):
    temporary = OUTPUT / ".process_runs.json"
    temporary.write_text(json.dumps(state, indent=2) + "\n")
    temporary.replace(OUTPUT / "process_runs.json")

def main():
    state = {"started_utc": now(), "controller_pid": __import__("os").getpid(), "sequential": True, "processes": []}
    if (OUTPUT / "process_runs.json").exists():
        raise SystemExit("Controller already has saved state; inspect it before any manual resume")
    save(state)
    for case_id in CASES:
        directory = OUTPUT / case_id
        directory.mkdir(exist_ok=True)
        command = [sys.executable, "-B", str(WORKER), "--case", case_id]
        if (OUTPUT / "checkpoint.json").exists(): command.append("--resume")
        record = {"case": case_id, "started_utc": now(), "command": command}
        state["processes"].append(record)
        with (directory / "process_stdout.log").open("a") as log:
            child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            record["pid"] = child.pid; save(state)
            print(json.dumps({"event": "case_started", **record}), flush=True)
            record["returncode"] = child.wait()
        record["finished_utc"] = now()
        checkpoint = json.loads((OUTPUT / "checkpoint.json").read_text()) if (OUTPUT / "checkpoint.json").exists() else {}
        row = next((c for c in checkpoint.get("cases", []) if c["id"] == case_id), {})
        record["attempts"] = len(row.get("measurements", []))
        record["preparation_error"] = row.get("preparation_error")
        save(state)
        print(json.dumps({"event": "case_finished", **record}), flush=True)
    state["finished_utc"] = now(); save(state)
    analysis = subprocess.run([sys.executable, "-B", str(WORKER), "--plots-only"])
    state["analysis_returncode"] = analysis.returncode; save(state)
    complete = all(p["returncode"] == 0 and p["attempts"] == 200 for p in state["processes"])
    print(json.dumps({"event": "finished", "all_800_attempts_recorded": complete, "analysis_returncode": analysis.returncode}), flush=True)
    return 0 if complete and analysis.returncode == 0 else 1
if __name__ == "__main__": raise SystemExit(main())
