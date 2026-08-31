#!/usr/bin/env python3
"""Workload for sigsnoop: fork a child that just sleeps, then repeatedly
send it signals via kill()/tkill()-triggering syscalls so
sys_enter_kill/tkill/tgkill keep firing. Runs until killed."""
import os
import signal
import time


def child_main():
    def _ignore(_signum, _frame):
        pass

    for s in (signal.SIGUSR1, signal.SIGUSR2, signal.SIGHUP):
        signal.signal(s, _ignore)
    while True:
        time.sleep(3600)


def main():
    pid = os.fork()
    if pid == 0:
        child_main()
        os._exit(0)

    try:
        while True:
            os.kill(pid, signal.SIGUSR1)
            time.sleep(0.02)
    finally:
        try:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
        except OSError:
            pass


if __name__ == "__main__":
    main()
