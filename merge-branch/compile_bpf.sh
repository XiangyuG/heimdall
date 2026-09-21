#!/usr/bin/env bash

set -euo pipefail

usage() {
    echo "Usage: $(basename "$0") <path-to-bpf-source>" >&2
}

if [[ $# -ne 1 ]]; then
    usage
    exit 2
fi

if [[ ! -f "$1" ]]; then
    echo "error: BPF source file not found: $1" >&2
    exit 1
fi

script_dir=$(cd -P -- "$(dirname -- "$0")" && pwd)
repo_dir=$(cd -P -- "$script_dir/.." && pwd)
source_dir=$(cd -P -- "$(dirname -- "$1")" && pwd)
source_path="$source_dir/$(basename -- "$1")"

runtime_include_dir="$repo_dir/runtime-testing/include"
libbpf_tools_dir="$repo_dir/c2rust_translation/c_bpf_programs/libbpf-tools"
output_dir="$script_dir/bytes"

find_clang() {
    local candidate
    local resolved

    if [[ -n "${BPF_CLANG:-}" ]]; then
        candidate="$BPF_CLANG"
        if [[ "$candidate" == */* ]]; then
            resolved="$candidate"
        else
            resolved=$(command -v -- "$candidate" 2>/dev/null || true)
        fi

        if [[ -z "$resolved" || ! -x "$resolved" ]]; then
            echo "error: BPF_CLANG is not executable: $candidate" >&2
            return 1
        fi
        if ! "$resolved" --print-targets 2>/dev/null | grep -Eq '^[[:space:]]+bpf'; then
            echo "error: BPF_CLANG does not support the BPF target: $resolved" >&2
            return 1
        fi

        printf '%s\n' "$resolved"
        return
    fi

    for candidate in \
        /opt/homebrew/opt/llvm/bin/clang \
        /usr/local/opt/llvm/bin/clang \
        clang-20 clang-19 clang-18 clang-17 clang-16 clang-15 clang-14 clang
    do
        if [[ "$candidate" == */* ]]; then
            resolved="$candidate"
        else
            resolved=$(command -v -- "$candidate" 2>/dev/null || true)
        fi

        if [[ -n "$resolved" && -x "$resolved" ]] && \
            "$resolved" --print-targets 2>/dev/null | grep -Eq '^[[:space:]]+bpf'; then
            printf '%s\n' "$resolved"
            return
        fi
    done

    echo "error: no BPF-capable clang found; set BPF_CLANG to its path" >&2
    return 1
}

source_name=$(basename -- "$source_path")
if [[ "$source_name" == *.bpf.c ]]; then
    output_name="${source_name%.bpf.c}.o"
elif [[ "$source_name" == *.c ]]; then
    output_name="${source_name%.c}.o"
else
    echo "error: expected a C source path ending in .c: $source_path" >&2
    exit 1
fi

clang=$(find_clang)
mkdir -p -- "$output_dir"
output_path="$output_dir/$output_name"
temporary_output=$(mktemp "$output_dir/.${output_name}.XXXXXX")
trap 'rm -f -- "$temporary_output"' EXIT

"$clang" \
    -target bpf \
    -D__TARGET_ARCH_x86 \
    -O2 \
    -g \
    -I "$runtime_include_dir" \
    -I "$libbpf_tools_dir" \
    -c "$source_path" \
    -o "$temporary_output"

mv -f -- "$temporary_output" "$output_path"
trap - EXIT

printf '%s\n' "$output_path"
