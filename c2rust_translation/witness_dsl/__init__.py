"""Transformation-witness DSL: concrete syntax + syntax checker + semantic pass.

This package covers lexing, parsing, BNF-conformance / structural
well-formedness checking (`syntax_check.py`), semantic lowering to a
resolved `WitnessPlan` (`lower.py`), and equivalence checking between two
lowered witnesses (`equivalence.py`).

Public surface:

    from witness_dsl import parse, check_source, check_file
    from witness_dsl import check_equivalent, check_sources_equivalent, check_files_equivalent
    from witness_dsl.errors import DslSyntaxError

The authoritative grammar is GRAMMAR.bnf in this directory.
"""

from __future__ import annotations

from .equivalence import (
    EquivalenceResult,
    check_equivalent,
    check_files_equivalent,
    check_sources_equivalent,
)
from .errors import Diagnostic, DslSyntaxError, Pos
from .parser import parse
from .syntax_check import CheckResult, check_file, check_source

__all__ = [
    "parse",
    "check_source",
    "check_file",
    "CheckResult",
    "check_equivalent",
    "check_sources_equivalent",
    "check_files_equivalent",
    "EquivalenceResult",
    "Diagnostic",
    "DslSyntaxError",
    "Pos",
]
