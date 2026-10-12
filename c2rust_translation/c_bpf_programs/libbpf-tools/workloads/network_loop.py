#!/usr/bin/env python3
"""Workload for tcp* tools (tcpconnect, tcpconnlat, tcplife, tcpstates,
tcpsynbl, tcptracer, solisten): local TCP servers on 127.0.0.1 and ::1 plus a
client that connects/sends/closes to each in turn in a tight loop, so
tcp_v4_connect/tcp_v6_connect/tcp_rcv_state_process/inet_sock_set_state/
inet_listen etc. keep firing for as long as this process runs. Falls back to
IPv4 only if IPv6 loopback is unavailable. Runs until killed (the evaluator's
_run_workload_benchmark kills the whole process group once the runner's
measurement window ends)."""
import socket
import threading
import time

HOSTS = ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1"))
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


def start_server(family, host):
    """Listen on (host, any free port) and accept in a background thread;
    returns the (host, port) to connect to, or None if `family` is unusable."""
    try:
        server_sock = socket.socket(family, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((host, PORT))
        server_sock.listen(16)
    except OSError:
        return None
    port = server_sock.getsockname()[1]

    server_thread = threading.Thread(target=serve, args=(server_sock,), daemon=True)
    server_thread.start()
    return host, port


def main():
    targets = [t for t in (start_server(f, h) for f, h in HOSTS) if t]

    while True:
        for target in targets:
            try:
                with socket.create_connection(target, timeout=1) as client_sock:
                    client_sock.sendall(b"ping")
            except OSError:
                pass
        time.sleep(0.01)


if __name__ == "__main__":
    main()
