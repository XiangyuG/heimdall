#!/usr/bin/env python3
"""Workload for solisten: repeatedly open a socket, bind it, and listen()
(then close it) in a tight loop, so inet_listen keeps firing for as long as
this process runs. network_loop.py's connect loop calls listen() exactly
once at startup and never again, which never exercises solisten's hooks
during the runner's measurement window -- this script re-triggers listen()
itself instead of just connecting to an already-listening socket.
Runs until killed (the evaluator's _run_workload_benchmark kills the whole
process group once the runner's measurement window ends)."""
import socket
import time

HOST = "127.0.0.1"


def main():
    while True:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((HOST, 0))  # let the OS pick a free port
            sock.listen(16)
        finally:
            sock.close()
        time.sleep(0.01)


if __name__ == "__main__":
    main()
