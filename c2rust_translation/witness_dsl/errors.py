"""Diagnostics for the transformation-witness DSL syntax checker.

A single position type plus a `Diagnostic` container, and one exception,
`DslSyntaxError`, raised by the lexer and parser.  `Diagnostic.render()`
produces a `gcc`-style message with a source-line snippet and a caret.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Pos:
    """1-based line/column plus 0-based byte offset into the source."""

    line: int
    col: int
    offset: int

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.line}:{self.col}"


@dataclass
class Diagnostic:
    """A single error or warning, tied to a source position."""

    severity: str  # "error" | "warning"
    message: str
    pos: Pos
    filename: str = "<string>"
    # length of the offending token, for a multi-caret underline
    span: int = 1

    def render(self, source: str | None = None) -> str:
        head = f"{self.filename}:{self.pos.line}:{self.pos.col}: {self.severity}: {self.message}"
        if source is None:
            return head
        lines = source.splitlines()
        if not (1 <= self.pos.line <= len(lines)):
            return head
        src_line = lines[self.pos.line - 1]
        gutter = f"{self.pos.line} | "
        pad = " " * (len(gutter) - 2) + "| "
        caret = " " * (self.pos.col - 1) + "^" * max(1, self.span)
        return "\n".join([head, pad.rstrip(), gutter + src_line, pad + caret])


class DslSyntaxError(Exception):
    """Raised on the first lexical or grammatical error.

    Carries a fully-formed `Diagnostic` so callers can render it uniformly.
    """

    def __init__(self, diagnostic: Diagnostic):
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic
