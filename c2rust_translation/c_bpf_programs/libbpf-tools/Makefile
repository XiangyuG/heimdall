# Build the benchmark "runners" -- small userspace programs that load a
# compiled BPF object, attach its programs, run for N seconds while a workload
# drives the probed events, and print each program's ns/run
# (kernel run_time_ns / run_cnt).
#
#   make            # build every *_runner
#   make filetop_runner
#   make clean
#
# Requires: clang, libbpf-dev (>= 0.5), libelf-dev, zlib. The runners link
# against the system libbpf; they do NOT need vmlinux.h (that is only for
# recompiling the *.bpf.c programs).

CC      ?= clang
CFLAGS  ?= -O2 -Wall
LDLIBS  := -lbpf -lelf -lz

RUNNER_SRCS := $(wildcard *_runner.c)
RUNNERS     := $(RUNNER_SRCS:.c=)

.PHONY: all clean
all: $(RUNNERS)

%_runner: %_runner.c
	$(CC) $(CFLAGS) -o $@ $< $(LDLIBS)

clean:
	rm -f $(RUNNERS)
