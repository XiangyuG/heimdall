#!/usr/bin/env python3
"""Workload for runqslower/softirqs/offcputime: spawn more busy worker
processes than there are CPUs, each alternating short bursts of computation
with a yield/sleep, to force involuntary context switches (runqueue
contention) and voluntary ones (sleep-then-wake). Runs until killed."""
import multiprocessing
import time


def worker():
    while True:
        # short CPU burst
        x = 0
        for _ in range(200_000):
            x += 1
        # yield so the scheduler has to pick a next task -- this is what
        # actually drives sched_switch/sched_wakeup and softirq activity
        time.sleep(0.001)


def main():
    n = max(4, (multiprocessing.cpu_count() or 2) * 2)
    procs = [multiprocessing.Process(target=worker, daemon=True) for _ in range(n)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()


if __name__ == "__main__":
    main()
