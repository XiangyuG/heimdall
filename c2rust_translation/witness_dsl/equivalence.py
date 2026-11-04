"""Semantic equivalence checking for the transformation-witness DSL.

`check_equivalent(plan_a, plan_b)` answers: do two already-lowered
`WitnessPlan`s (see `lower.py`) impose the *same net constraints* on
heimdall's proof obligation, for one shared `Env` (i.e. the same
original/optimized program pair)? This is the next stage after `lower.py` in
the pipeline: parse -> lower -> equivalence.

What counts as "the same constraints" (proof-relevant, drives the verdict):
  * `ranges`      -- canonicalized per `(path, sign_tag)` and intersected;
                     see `_canon_ranges` for why grouping by signedness (not
                     just by path) is required.
  * `ignored_helper_flags` -- compared as a set. NOTE: `WitnessPlan.
                     to_legacy_json()` does not emit this field yet (see
                     `lower.py`'s docstring, "known limitations"), so today
                     two plans differing only here are reported
                     not-equivalent even though their *emitted JSON* would be
                     byte-identical. This is intentional: the field is a
                     first-class, fully-populated part of the resolved IR
                     (unlike `unsupported`, which is just a note for AST
                     shapes with no IR representation at all), and the JSON
                     gap is a known emitter-side TODO, not a decision that
                     `ignore flag of X` is semantically inert. Revisit this
                     module's tests the day `to_legacy_json()` starts
                     emitting it.
  * `map_correspondences` -- compared as a set, ignoring the bound key
                     variable name (`key_var`), which is scoped to a single
                     binding statement and never referenced anywhere else
                     (confirmed against `to_legacy_json()`), so two
                     witnesses that differ only by `[k]` vs `[j]` are
                     equivalent.

What is surfaced but never flips the verdict (informational only):
  * `unsupported`  -- statements `lower()` couldn't apply (e.g. scalar
                     bindings); by construction these don't affect
                     `to_legacy_json()`'s output, but a human comparing two
                     `.wit` texts should still be told about them.
  * `diagnostics`  -- e.g. "not a map, binding skipped" only records a
                     `Diagnostic`, not an `unsupported` entry, so diffing
                     `unsupported` alone would miss it.
  * dead-range notes -- see `_canon_ranges`.

Not built here (explicit non-goals): cross-`Env` comparison, and
subsumption/entailment ("does A imply B") -- only exact equivalence. Both
canonical forms already computed (per-`(path, sign_tag)` intervals, and sets
for the other two categories) would make entailment a straightforward
per-category containment/subset check later, with no solver needed there
either -- just not built now.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field

from .errors import DslSyntaxError
from .lower import Env, WitnessPlan, lower
from .parser import parse

# Sentinel for a range group that has become unsatisfiable (lo > hi after
# intersecting every statement in that group), distinct from any real
# (lo, hi) pair.
_EMPTY_RANGE = "<empty>"


def _sign_tag(lo: int) -> str:
    return "signed" if lo < 0 else "unsigned"


def _canon_ranges(plan: WitnessPlan):
    """Group `plan.ranges` by `(path, sign_tag)` and intersect within each group.

    `to_legacy_json()` classifies each `RangeAssumption` as signed or
    unsigned independently, from that *statement's own* `lo` (`lower.py`:
    `signed = r.lo < 0`) -- not from any path-wide property. Two range
    statements on the same path where one has `lo < 0` and another has
    `lo >= 0` become differently-typed predicates (`signed_ge/le` vs
    `unsigned_ge/le`) over the same value, so they must be tracked as
    separate dimensions, not merged into one interval.

    Multiple statements sharing a `(path, sign_tag)` are additional ANDed
    premises, so intersecting them (`lo = max(...), hi = min(...)`) is sound
    and exact -- no SMT solver needed. Intersection only ever narrows: it can
    drive a group to `_EMPTY_RANGE` (unsatisfiable), but a nonempty group can
    never widen back to "no constraint".

    Returns `(canon, notes)` where `canon` maps `(path, sign_tag)` to either
    `(lo, hi)` or `_EMPTY_RANGE`, and `notes` is a list of human-readable
    strings for any group that came out empty (including the case where no
    single statement was individually inverted -- an unsatisfiable
    conjunction that neither `lower()` nor `syntax_check.py`'s
    well-formedness pass would catch, since both look at one
    `RangeAssumption` at a time).
    """
    groups: dict = {}
    for r in plan.ranges:
        groups.setdefault((r.path, _sign_tag(r.lo)), []).append((r.lo, r.hi))

    canon: dict = {}
    notes: list = []
    for (path, sign_tag), bounds in groups.items():
        lo = max(b[0] for b in bounds)
        hi = min(b[1] for b in bounds)
        if lo > hi:
            canon[(path, sign_tag)] = _EMPTY_RANGE
            if any(b[0] > b[1] for b in bounds):
                reason = "an individual statement has inverted bounds"
            else:
                reason = f"intersecting {len(bounds)} non-empty statements"
            notes.append(f"{path} ({sign_tag}): range is empty ({reason})")
        else:
            canon[(path, sign_tag)] = (lo, hi)
    return canon, notes


def _canon_map_corr(plan: WitnessPlan) -> frozenset:
    """Set of correspondences, `key_var` excluded (see module docstring)."""
    return frozenset(
        (mc.original_name, mc.name, mc.kind, mc.orig_key_bytes, mc.opt_key_bytes,
         mc.orig_val_bytes, mc.opt_val_bytes)
        for mc in plan.map_correspondences
    )


def _canon_flags(plan: WitnessPlan) -> frozenset:
    return frozenset(plan.ignored_helper_flags)


def _canon_unsupported(plan: WitnessPlan) -> frozenset:
    return frozenset(plan.unsupported)


def _canon_diagnostics(plan: WitnessPlan) -> frozenset:
    # `pos` is deliberately excluded -- two files necessarily differ in
    # source position even when the underlying note is the same.
    return frozenset((d.severity, d.message) for d in plan.diagnostics)


@dataclass
class EquivalenceResult:
    """Verdict plus a per-category diff explaining it.

    `equivalent` is only meaningful when `inconclusive` is False -- it
    defaults to `False` so a caller who forgets to check `.inconclusive`
    first fails closed rather than treating an inconclusive run as a pass.
    """

    equivalent: bool = False
    inconclusive: bool = False
    reason: str | None = None  # set iff inconclusive

    ranges_only_in_a: list = field(default_factory=list)  # (path, sign_tag, bound)
    ranges_only_in_b: list = field(default_factory=list)
    ranges_diff: list = field(default_factory=list)  # (path, sign_tag, bound_a, bound_b)

    ignored_flags_only_in_a: list = field(default_factory=list)
    ignored_flags_only_in_b: list = field(default_factory=list)

    map_corr_only_in_a: list = field(default_factory=list)
    map_corr_only_in_b: list = field(default_factory=list)

    # informational only -- never affects `equivalent`
    unsupported_only_in_a: list = field(default_factory=list)
    unsupported_only_in_b: list = field(default_factory=list)
    diagnostics_only_in_a: list = field(default_factory=list)  # (severity, message)
    diagnostics_only_in_b: list = field(default_factory=list)
    notes: list = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.inconclusive:
            return "inconclusive"
        return "equivalent" if self.equivalent else "not_equivalent"

    def has_informational_differences(self) -> bool:
        return bool(
            self.unsupported_only_in_a
            or self.unsupported_only_in_b
            or self.diagnostics_only_in_a
            or self.diagnostics_only_in_b
        )

    def render(self) -> str:
        lines = [f"status: {self.status}"]
        if self.inconclusive:
            lines.append(f"reason: {self.reason}")
            return "\n".join(lines)

        def section(title, only_a, only_b, diff=None):
            if not only_a and not only_b and not diff:
                return
            lines.append(f"{title}:")
            for x in only_a:
                lines.append(f"  only in A: {x}")
            for x in only_b:
                lines.append(f"  only in B: {x}")
            for x in diff or []:
                lines.append(f"  differs: {x}")

        section("ranges", self.ranges_only_in_a, self.ranges_only_in_b, self.ranges_diff)
        section("ignored helper flags", self.ignored_flags_only_in_a, self.ignored_flags_only_in_b)
        section("map correspondences", self.map_corr_only_in_a, self.map_corr_only_in_b)

        if self.has_informational_differences():
            lines.append("informational differences (do not affect the verdict):")
            for x in self.unsupported_only_in_a:
                lines.append(f"  unsupported only in A: {x}")
            for x in self.unsupported_only_in_b:
                lines.append(f"  unsupported only in B: {x}")
            for x in self.diagnostics_only_in_a:
                lines.append(f"  diagnostic only in A: {x}")
            for x in self.diagnostics_only_in_b:
                lines.append(f"  diagnostic only in B: {x}")

        for n in self.notes:
            lines.append(f"note: {n}")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "equivalent": self.equivalent,
            "inconclusive": self.inconclusive,
            "reason": self.reason,
            "ranges_only_in_a": self.ranges_only_in_a,
            "ranges_only_in_b": self.ranges_only_in_b,
            "ranges_diff": self.ranges_diff,
            "ignored_flags_only_in_a": self.ignored_flags_only_in_a,
            "ignored_flags_only_in_b": self.ignored_flags_only_in_b,
            "map_corr_only_in_a": self.map_corr_only_in_a,
            "map_corr_only_in_b": self.map_corr_only_in_b,
            "unsupported_only_in_a": self.unsupported_only_in_a,
            "unsupported_only_in_b": self.unsupported_only_in_b,
            "diagnostics_only_in_a": self.diagnostics_only_in_a,
            "diagnostics_only_in_b": self.diagnostics_only_in_b,
            "notes": self.notes,
        }


def check_equivalent(plan_a: WitnessPlan, plan_b: WitnessPlan) -> EquivalenceResult:
    """Compare two already-lowered plans (same shared `Env`) for equivalence."""
    if plan_a.has_errors or plan_b.has_errors:
        which = [n for n, p in (("A", plan_a), ("B", plan_b)) if p.has_errors]
        return EquivalenceResult(
            inconclusive=True,
            reason=f"lowering reported hard error(s) in {', '.join(which)}; cannot compare",
        )

    result = EquivalenceResult()

    ranges_a, notes_a = _canon_ranges(plan_a)
    ranges_b, notes_b = _canon_ranges(plan_b)
    result.notes.extend(f"A: {n}" for n in notes_a)
    result.notes.extend(f"B: {n}" for n in notes_b)

    ranges_equal = True
    for key in sorted(set(ranges_a) | set(ranges_b)):
        path, sign_tag = key
        va, vb = ranges_a.get(key), ranges_b.get(key)
        if va is None:
            result.ranges_only_in_b.append((path, sign_tag, vb))
            ranges_equal = False
        elif vb is None:
            result.ranges_only_in_a.append((path, sign_tag, va))
            ranges_equal = False
        elif va != vb:
            result.ranges_diff.append((path, sign_tag, va, vb))
            ranges_equal = False

    flags_a, flags_b = _canon_flags(plan_a), _canon_flags(plan_b)
    result.ignored_flags_only_in_a = sorted(flags_a - flags_b)
    result.ignored_flags_only_in_b = sorted(flags_b - flags_a)

    mc_a, mc_b = _canon_map_corr(plan_a), _canon_map_corr(plan_b)
    result.map_corr_only_in_a = sorted(mc_a - mc_b)
    result.map_corr_only_in_b = sorted(mc_b - mc_a)

    unsupported_a, unsupported_b = _canon_unsupported(plan_a), _canon_unsupported(plan_b)
    result.unsupported_only_in_a = sorted(unsupported_a - unsupported_b)
    result.unsupported_only_in_b = sorted(unsupported_b - unsupported_a)

    diag_a, diag_b = _canon_diagnostics(plan_a), _canon_diagnostics(plan_b)
    result.diagnostics_only_in_a = sorted(diag_a - diag_b)
    result.diagnostics_only_in_b = sorted(diag_b - diag_a)

    result.equivalent = (
        ranges_equal
        and not result.ignored_flags_only_in_a
        and not result.ignored_flags_only_in_b
        and not result.map_corr_only_in_a
        and not result.map_corr_only_in_b
    )
    return result


def check_sources_equivalent(
    source_a: str,
    source_b: str,
    env: Env,
    filename_a: str = "<a>",
    filename_b: str = "<b>",
    name_a: str | None = None,
    name_b: str | None = None,
) -> EquivalenceResult:
    """Parse + lower + compare two `.wit` texts against one shared `Env`.

    Never raises: a syntax error in either source is reported as
    `inconclusive`, not `not_equivalent`.
    """
    try:
        program_a = parse(source_a, filename_a)
    except DslSyntaxError as e:
        return EquivalenceResult(
            inconclusive=True,
            reason=f"{filename_a} failed to parse: {e.diagnostic.render(source_a)}",
        )
    try:
        program_b = parse(source_b, filename_b)
    except DslSyntaxError as e:
        return EquivalenceResult(
            inconclusive=True,
            reason=f"{filename_b} failed to parse: {e.diagnostic.render(source_b)}",
        )

    plan_a = lower(program_a, env, name=name_a or filename_a)
    plan_b = lower(program_b, env, name=name_b or filename_b)
    return check_equivalent(plan_a, plan_b)


def check_files_equivalent(
    path_a: str,
    path_b: str,
    env: Env,
    name_a: str | None = None,
    name_b: str | None = None,
) -> EquivalenceResult:
    """Read + parse + lower + compare two `.wit` files against one shared `Env`."""
    try:
        with open(path_a, "r", encoding="utf-8") as fh:
            source_a = fh.read()
    except OSError as e:
        return EquivalenceResult(inconclusive=True, reason=f"cannot read {path_a}: {e}")
    try:
        with open(path_b, "r", encoding="utf-8") as fh:
            source_b = fh.read()
    except OSError as e:
        return EquivalenceResult(inconclusive=True, reason=f"cannot read {path_b}: {e}")

    return check_sources_equivalent(
        source_a,
        source_b,
        env,
        filename_a=path_a,
        filename_b=path_b,
        name_a=name_a or path_a,
        name_b=name_b or path_b,
    )


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
# A sibling of `syntax_check.py`'s CLI, not folded into `witness_dsl/
# __main__.py`: that module's contract is specifically "does this file
# conform to the grammar", and shouldn't silently grow a second, unrelated
# meaning.


def _main(argv: list) -> int:
    ap = argparse.ArgumentParser(
        prog="witness_dsl.equivalence",
        description="Check whether two transformation-witness DSL files impose the same net constraints.",
    )
    ap.add_argument("file_a")
    ap.add_argument("file_b")
    ap.add_argument("--original-obj", required=True, help="original program's compiled object (BTF source)")
    ap.add_argument("--optimized-obj", required=True, help="optimized program's compiled object (BTF source)")
    ap.add_argument("--json", action="store_true", help="print machine-readable JSON instead of text")
    ap.add_argument("-q", "--quiet", action="store_true", help="only print output when the run fails")
    ap.add_argument("--strict", action="store_true", help="informational differences also fail the run")
    args = ap.parse_args(argv)

    env = Env.from_btf(args.original_obj, args.optimized_obj)
    result = check_files_equivalent(args.file_a, args.file_b, env)

    if result.inconclusive:
        code = 3
    elif not result.equivalent:
        code = 1
    elif args.strict and result.has_informational_differences():
        code = 1
    else:
        code = 0

    if not (args.quiet and code == 0):
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(f"{args.file_a} vs {args.file_b}")
            print(result.render())

    return code


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
