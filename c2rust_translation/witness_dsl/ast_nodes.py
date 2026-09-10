"""AST for the transformation-witness DSL.

The parser produces a `Program`.  Every node keeps the source `Pos` of its
first token so the semantic layer (a separate module, later) can report
against the original text.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import Pos

ORIGINAL = "original"
OPTIMIZED = "optimized"


# -- expressions -------------------------------------------------------------


@dataclass
class MapAll:
    """The `[:]` accessor -- every entry of a map."""

    pos: Pos


@dataclass
class Index:
    """The `[k]` accessor -- one entry of a map, keyed by a variable."""

    key: str
    pos: Pos


@dataclass
class Field:
    """The `.name` accessor -- a struct field."""

    name: str
    pos: Pos


Accessor = "MapAll | Index | Field"


@dataclass
class Expr:
    """`<side>.<variable><accessor>*`, e.g. `original.m[k].count`."""

    side: str  # ORIGINAL | OPTIMIZED
    root: str  # the leading variable name
    accessors: list  # list[Accessor]
    pos: Pos

    def text(self) -> str:
        out = f"{self.side}.{self.root}"
        for a in self.accessors:
            if isinstance(a, MapAll):
                out += "[:]"
            elif isinstance(a, Index):
                out += f"[{a.key}]"
            elif isinstance(a, Field):
                out += f".{a.name}"
        return out


# -- statements ------------------------------------------------------------


@dataclass
class RangeAssumption:
    """`<side-expr> in [lo, hi] ;`"""

    expr: Expr
    lo: int
    hi: int
    pos: Pos


@dataclass
class IgnoreAssumption:
    """`ignore flag of <helper-name> ;`"""

    helper: str
    pos: Pos


@dataclass
class EqStatement:
    """`original.<expr> = optimized.<expr> ;` -- used in binding and observation."""

    lhs: Expr
    rhs: Expr
    pos: Pos


# -- blocks / program ---------------------------------------------------------


@dataclass
class AssumptionBlock:
    statements: list  # list[RangeAssumption | IgnoreAssumption]
    pos: Pos


@dataclass
class BindingBlock:
    statements: list  # list[EqStatement]
    pos: Pos


@dataclass
class ObservationBlock:
    statements: list  # list[EqStatement] -- non-empty
    pos: Pos


@dataclass
class Program:
    observation: ObservationBlock
    assumption: AssumptionBlock | None = None
    binding: BindingBlock | None = None
