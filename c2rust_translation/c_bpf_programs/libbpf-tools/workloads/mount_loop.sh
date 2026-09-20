#!/bin/bash
# Workload for mountsnoop: repeatedly bind-mount a scratch source directory
# onto a scratch target directory and unmount it, so sys_enter_mount/umount
# keep firing. Both directories are private tmpfs-backed scratch paths under
# /tmp created by this script -- never touches any real filesystem or
# existing mount. Requires root (the evaluator already runs the runner via
# sudo -n; this script is expected to be invoked the same way).
set -u

SRC="/tmp/openevolve_mountsnoop_src"
DST="/tmp/openevolve_mountsnoop_dst"

mkdir -p "$SRC" "$DST"

cleanup() {
	mountpoint -q "$DST" && umount "$DST" 2>/dev/null
	rmdir "$SRC" "$DST" 2>/dev/null
}
trap cleanup EXIT

while true; do
	mount --bind "$SRC" "$DST" 2>/dev/null
	umount "$DST" 2>/dev/null
	sleep 0.05
done
