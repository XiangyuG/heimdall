"""`python3 -m witness_dsl <file.wit> ...` -- run the syntax checker."""

from __future__ import annotations

import sys

from .syntax_check import _main

if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
