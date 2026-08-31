#!/usr/bin/env python3
"""Workload for futexctn: several threads contending on the same lock so
glibc's pthread_mutex (which CPython's threading.Lock delegates to) actually
goes through futex() wait/wake, keeping sys_enter_futex/sys_exit_futex
firing. Runs until killed."""
import threading

LOCK = threading.Lock()
COUNTERS = [0] * 8


def worker(index):
    while True:
        with LOCK:
            COUNTERS[index] += 1


def main():
    threads = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


if __name__ == "__main__":
    main()
