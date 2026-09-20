#!/usr/bin/env python3
"""Syntax checker for the transformation-witness DSL.

Answers one question: *does this file conform to GRAMMAR.bnf?*  It runs the
lexer and the parser and reports the first violation.  It does NOT resolve
names, check kinds, or interpret meaning -- that is the job of a later
semantic pass over the `Program` this module returns.

Library use:

    from witness_dsl.syntax_check import check_source, check_file
    res = check_file("witness.wit")
    if res.ok:
        program = res.program        # ast_nodes.Program, for the next pass

CLI use:

    python3 -m witness_dsl.syntax_check witness.wit [more.wit ...]
    python3 syntax_check.py witness.wit

Exit code: 0 if every file is syntactically valid, 1 otherwise.  `--strict`
also fails on warnings from the optional well-formedness checks.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field

if __package__ in (None, ""):  # run as a plain script
    import os

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from witness_dsl import ast_nodes as A
    from witness_dsl.errors import Diagnostic, DslSyntaxError
    from witness_dsl.parser import parse
else:
    from . import ast_nodes as A
    from .errors import Diagnostic, DslSyntaxError
    from .parser import parse


@dataclass
class CheckResult:
    ok: bool
    errors: list = field(default_factory=list)  # list[Diagnostic]
    warnings: list = field(default_factory=list)  # list[Diagnostic]
    program: A.Program | None = None


# --------------------------------------------------------------------------
# optional well-formedness checks (beyond the raw BNF)
# --------------------------------------------------------------------------
# These are static, syntax-adjacent sanity checks that the BNF cannot state.
# They are warnings by default; --strict promotes them to errors.


def _wellformedness_warnings(prog: A.Program, filename: str) -> list:
    warns: list = []

    if prog.assumption is not None:
        seen_ignore: dict = {}
        for st in prog.assumption.statements:
            if isinstance(st, A.RangeAssumption):
                if st.lo > st.hi:
                    warns.append(
                        Diagnostic(
                            "warning",
                            f"empty range [{st.lo}, {st.hi}]: lower bound exceeds upper bound",
                            st.pos,
                            filename,
                        )
                    )
            elif isinstance(st, A.IgnoreAssumption):
                if st.helper in seen_ignore:
                    warns.append(
                        Diagnostic(
                            "warning",
                            f"duplicate 'ignore flag of {st.helper}'",
                            st.pos,
                            filename,
                        )
                    )
                seen_ignore[st.helper] = True

    if prog.binding is not None:
        seen: dict = {}
        for st in prog.binding.statements:
            key = (st.lhs.text(), st.rhs.text())
            if key in seen:
                warns.append(
                    Diagnostic(
                        "warning",
                        f"duplicate binding statement '{key[0]} = {key[1]}'",
                        st.pos,
                        filename,
                    )
                )
            seen[key] = True

    return warns


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------


def check_source(
    source: str, filename: str = "<string>", extra: bool = True
) -> CheckResult:
    try:
        program = parse(source, filename)
    except DslSyntaxError as e:
        return CheckResult(ok=False, errors=[e.diagnostic])

    warnings = _wellformedness_warnings(program, filename) if extra else []
    return CheckResult(ok=True, errors=[], warnings=warnings, program=program)


def check_file(path: str, extra: bool = True) -> CheckResult:
    with open(path, "r", encoding="utf-8") as fh:
        return check_source(fh.read(), path, extra=extra)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _main(argv: list) -> int:
    ap = argparse.ArgumentParser(
        prog="witness_dsl.syntax_check",
        description="Check transformation-witness DSL files against GRAMMAR.bnf.",
    )
    ap.add_argument("files", nargs="+", help="witness DSL source files (*.wit)")
    ap.add_argument(
        "-q", "--quiet", action="store_true", help="only print failures"
    )
    ap.add_argument(
        "--no-extra",
        action="store_true",
        help="skip the optional well-formedness warnings",
    )
    ap.add_argument(
        "--strict",
        action="store_true",
        help="treat well-formedness warnings as failures",
    )
    args = ap.parse_args(argv)

    worst = 0
    for path in args.files:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                source = fh.read()
        except OSError as e:
            print(f"{path}: error: {e}", file=sys.stderr)
            worst = 1
            continue

        res = check_source(source, path, extra=not args.no_extra)

        for diag in res.errors:
            print(diag.render(source), file=sys.stderr)
        for diag in res.warnings:
            print(diag.render(source), file=sys.stderr)

        failed = (not res.ok) or (args.strict and res.warnings)
        if failed:
            worst = 1
            if not res.ok:
                print(f"{path}: FAILED (syntax error)", file=sys.stderr)
            else:
                print(f"{path}: FAILED (warnings, --strict)", file=sys.stderr)
        elif not args.quiet:
            suffix = f" ({len(res.warnings)} warning(s))" if res.warnings else ""
            print(f"{path}: OK{suffix}")

    return worst


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
