#!/usr/bin/env bash
# Both original and source-optimized programs retain Clang automatic optimization.
set -euo pipefail
if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <path-to-source.bpf.c>" >&2
    exit 2
fi
script_dir=$(cd -P -- "$(dirname -- "$0")" && pwd)
python3 -B - "$script_dir" "$1" <<'PY'
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

root = Path(sys.argv[1])
sys.path.insert(0, str(root / "source_level_opt"))
from ast_utils import find_clang, clang_flags

temporary = None
try:
    source = Path(sys.argv[2]).resolve(strict=True)
    if not source.is_file() or not source.name.endswith(".bpf.c"):
        raise ValueError("expected a standalone .bpf.c file")
    output_dir = root / "bytes"
    output_dir.mkdir(exist_ok=True)
    output = output_dir / (source.name[:-6] + ".o")
    fd, temporary = tempfile.mkstemp(prefix="." + output.stem + ".", dir=output_dir)
    os.close(fd)
    command = [find_clang(), *clang_flags(), "-c", str(source), "-o", temporary]
    print("$ " + shlex.join(command), flush=True)
    subprocess.run(command, check=True)
    os.replace(temporary, output)
    temporary = None
    print(output)
except (OSError, ValueError, subprocess.CalledProcessError) as error:
    print(f"error: {error}", file=sys.stderr)
    sys.exit(1)
finally:
    if temporary is not None:
        Path(temporary).unlink(missing_ok=True)
PY
