"""Transformation-witness DSL: concrete syntax + syntax checker.

This package covers stages S0-S3 of the witness tooling plan: lexing,
parsing, and BNF-conformance / structural well-formedness checking.  It does
*not* do semantic analysis (name resolution, kind checking, lowering to a
proof obligation) -- that is a separate, later module that consumes the
`ast_nodes.Program` produced here.

Public surface:

    from witness_dsl import parse, check_source, check_file
    from witness_dsl.errors import DslSyntaxError

The authoritative grammar is GRAMMAR.bnf in this directory.
"""

from __future__ import annotations

from .errors import Diagnostic, DslSyntaxError, Pos
from .parser import parse
from .syntax_check import CheckResult, check_file, check_source

__all__ = [
    "parse",
    "check_source",
    "check_file",
    "CheckResult",
    "Diagnostic",
    "DslSyntaxError",
    "Pos",
]
