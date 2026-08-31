#!/usr/bin/env python3
"""Workload for tcp* tools (tcpconnect, tcpconnlat, tcplife, tcpstates,
tcpsynbl, tcptracer, solisten): a local TCP server plus a client that
connects/sends/closes in a tight loop, so tcp_v4_connect/tcp_rcv_state_process/
inet_sock_set_state/inet_listen etc. keep firing for as long as this process
runs. Runs until killed (the evaluator's _run_workload_benchmark kills the
whole process group once the runner's measurement window ends)."""
import socket
import threading
import time

HOST = "127.0.0.1"
PORT = 0  # let the OS pick a free port


def serve(server_sock):
    while True:
        try:
            conn, _ = server_sock.accept()
        except OSError:
            return
        try:
            conn.recv(64)
        except OSError:
            pass
        conn.close()


def main():
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((HOST, PORT))
    server_sock.listen(16)
    port = server_sock.getsockname()[1]

    server_thread = threading.Thread(target=serve, args=(server_sock,), daemon=True)
    server_thread.start()

    while True:
        try:
            with socket.create_connection((HOST, port), timeout=1) as client_sock:
                client_sock.sendall(b"ping")
        except OSError:
            pass
        time.sleep(0.01)


if __name__ == "__main__":
    main()
