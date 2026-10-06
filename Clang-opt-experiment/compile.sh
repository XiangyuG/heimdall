#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 || ! "$1" =~ ^[a-zA-Z0-9][a-zA-Z0-9_-]*$ ]]; then
    echo "Usage: $0 <case-directory-name>" >&2
    exit 2
fi

script_dir=$(cd -P -- "$(dirname -- "$0")" && pwd)
repo_dir=$(cd -P -- "$script_dir/.." && pwd)
case_dir="$script_dir/$1"
source_path="$case_dir/program.bpf.c"

if [[ ! -f "$source_path" ]]; then
    echo "error: case source not found: $source_path" >&2
    exit 1
fi

find_clang() {
    local candidate resolved
    if [[ -n "${BPF_CLANG:-}" ]]; then
        if [[ "$BPF_CLANG" == */* ]]; then
            resolved="$BPF_CLANG"
        else
            resolved=$(command -v -- "$BPF_CLANG" 2>/dev/null || true)
        fi
        if [[ -n "$resolved" && -x "$resolved" ]] && \
            "$resolved" --print-targets 2>/dev/null | grep -Eq '^[[:space:]]+bpf'; then
            printf '%s\n' "$resolved"
            return 0
        fi
        echo "error: BPF_CLANG is not a BPF-capable Clang: $BPF_CLANG" >&2
        return 1
    fi
    for candidate in /opt/homebrew/opt/llvm/bin/clang \
        /usr/local/opt/llvm/bin/clang clang-22 clang-21 clang-20 clang-19 clang; do
        [[ -n "$candidate" ]] || continue
        if [[ "$candidate" == */* ]]; then
            resolved="$candidate"
        else
            resolved=$(command -v -- "$candidate" 2>/dev/null || true)
        fi
        if [[ -n "$resolved" && -x "$resolved" ]] && \
            "$resolved" --print-targets 2>/dev/null | grep -Eq '^[[:space:]]+bpf'; then
            printf '%s\n' "$resolved"
            return 0
        fi
    done
    echo "error: no BPF-capable Clang found; set BPF_CLANG to its path" >&2
    return 1
}

clang=$(find_clang)
echo "Clang: $clang"

for variant in default no-opt; do
    if [[ "$variant" == default ]]; then
        optimization=-O2
    else
        optimization=-O0
    fi
    temporary_output=$(mktemp "$case_dir/.${variant}.o.XXXXXX")
    trap 'rm -f -- "$temporary_output"' EXIT
    "$clang" -target bpf -D__TARGET_ARCH_x86 "$optimization" -g \
        -I "$repo_dir/runtime-testing/include" \
        -I "$repo_dir/c2rust_translation/c_bpf_programs/libbpf-tools" \
        -c "$source_path" -o "$temporary_output"
    mv -f -- "$temporary_output" "$case_dir/$variant.o"
    trap - EXIT
    echo "$optimization: $case_dir/$variant.o"
done
