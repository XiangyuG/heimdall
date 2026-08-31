#!/usr/bin/env python3
"""Workload for syncsnoop: repeatedly call sync()/fsync()/fdatasync()/msync()/
sync_file_range()/syncfs() against a scratch file, so the sys_enter_sync,
sys_enter_fsync, sys_enter_fdatasync, sys_enter_msync,
sys_enter_sync_file_range, and sys_enter_syncfs tracepoints all keep firing.
The default fio workload never calls any of these -- fio's sync ioengine just
does buffered pread()/pwrite(), no explicit flush -- so syncsnoop's hooks
never fire under it. sync_file_range2/arm_sync_file_range are non-x86_64
syscall variants and are expected to stay at 0 here, same as an unreachable
CO-RE fallback branch elsewhere in this tool family.
Runs until killed (the evaluator's _run_workload_benchmark kills the whole
process group once the runner's measurement window ends)."""
import ctypes
import mmap
import os
import time

PATH = "/tmp/syncsnoop_workload.data"

_libc = ctypes.CDLL("libc.so.6", use_errno=True)
_libc.sync_file_range.argtypes = [
    ctypes.c_int,
    ctypes.c_int64,
    ctypes.c_int64,
    ctypes.c_uint,
]
SYNC_FILE_RANGE_WRITE = 2


def main():
    fd = os.open(PATH, os.O_CREAT | os.O_RDWR, 0o600)
    os.ftruncate(fd, 4096)
    mm = mmap.mmap(fd, 4096)

    i = 0
    try:
        while True:
            os.lseek(fd, 0, os.SEEK_SET)
            os.write(fd, b"x" * 64)
            os.fsync(fd)
            os.fdatasync(fd)
            mm[0:4] = b"test"
            mm.flush()  # msync
            _libc.sync_file_range(fd, 0, 4096, SYNC_FILE_RANGE_WRITE)
            _libc.syncfs(fd)
            if i % 10 == 0:
                os.sync()  # whole-filesystem sync -- throttled, it's heavier
            i += 1
            time.sleep(0.1)
    finally:
        mm.close()
        os.close(fd)


if __name__ == "__main__":
    main()
