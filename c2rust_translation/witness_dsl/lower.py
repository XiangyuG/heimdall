"""Semantic lowering for the transformation-witness DSL.

`lower(program, env)` turns a syntactically-valid `witness_dsl` AST into a
`WitnessPlan` -- heimdall's resolved, program-aware form of a transformation
witness. It is the semantic pass that sits between the parser and the
equivalence checker.

Transition period: `WitnessPlan.to_legacy_json()` emits the
`{"witness": {bindings, assumptions, observations}}` document that
`witness_spec.py` already consumes, so `--witness foo.wit` works today with no
change to the symbolic engine. When heimdall learns to read `WitnessPlan`
directly, `to_legacy_json()` and the JSON reader are deleted and `lower()`
stays as-is.

`lower()` needs an `Env` because the DSL is deliberately not self-contained
(see GRAMMAR.bnf): `m[:]`/`m[k]` require `m` to be a map, and a key/value
narrowing can only be expressed once we know both sides' BTF widths.

Known limitations of this transition path (each emits a diagnostic, never a
hard failure, so experiments are not blocked):
  * `ignore flag of <helper>` has no JSON representation -- recorded, not applied.
  * `binding` is lowered only for the `original.M[k] = optimized.M[k]` shape.
  * scalar `binding`s are not applied (same gap as the JSON path).

There is no `observation` block in the DSL: heimdall always compares every
output (return value, every map, every .data global) -- `to_legacy_json()`
always emits an empty `observations` list, which
`witness_spec.build_observation_selection()` reads as "no restriction".
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import ast_nodes as A
from .errors import Diagnostic, Pos


# --------------------------------------------------------------------------- #
# Environment (filled by heimdall from the two program objects' BTF)
# --------------------------------------------------------------------------- #
@dataclass
class MapInfo:
    key_bytes: int
    value_bytes: int
    kind: str = "hash"  # "hash" | "array"


@dataclass
class SideEnv:
    maps: dict = field(default_factory=dict)  # map name -> MapInfo

    def is_map(self, name: str) -> bool:
        return name in self.maps


@dataclass
class Env:
    original: SideEnv
    optimized: SideEnv

    @classmethod
    def from_btf(cls, original_obj: str, optimized_obj: str) -> "Env":
        """Build an Env from two eBPF object files via btf_parser."""
        from btf_parser import parse_map_metadata_from_btf

        def side(path: str) -> SideEnv:
            out = SideEnv()
            for name, meta in (parse_map_metadata_from_btf(path) or {}).items():
                kind = "array" if "ARRAY" in str(meta.map_type_name).upper() else "hash"
                out.maps[name] = MapInfo(
                    key_bytes=int(meta.key_size or 0),
                    value_bytes=int(meta.value_size or 0),
                    kind=kind,
                )
            return out

        return cls(original=side(original_obj), optimized=side(optimized_obj))


# --------------------------------------------------------------------------- #
# WitnessPlan -- the resolved IR
# --------------------------------------------------------------------------- #
@dataclass
class RangeAssumption:
    path: str  # e.g. "original.ctx.rx_queue_index"
    lo: int
    hi: int


@dataclass
class MapCorrespondence:
    name: str  # optimized-side object name (what heimdall enumerates)
    original_name: str
    key_var: str
    orig_key_bytes: int
    opt_key_bytes: int
    orig_val_bytes: int
    opt_val_bytes: int
    kind: str = "hash"

    @property
    def key_narrows(self) -> bool:
        return 0 < self.opt_key_bytes < self.orig_key_bytes

    @property
    def value_narrows(self) -> bool:
        return 0 < self.opt_val_bytes < self.orig_val_bytes


@dataclass
class WitnessPlan:
    name: str = "witness_dsl"
    ranges: list = field(default_factory=list)  # RangeAssumption
    ignored_helper_flags: list = field(default_factory=list)  # helper names
    map_correspondences: list = field(default_factory=list)  # MapCorrespondence
    unsupported: list = field(default_factory=list)  # human-readable notes
    diagnostics: list = field(default_factory=list)  # Diagnostic

    @property
    def has_errors(self) -> bool:
        return any(d.severity == "error" for d in self.diagnostics)

    # ---- transition-period JSON emitter ---------------------------------- #
    def to_legacy_json(self) -> dict:
        assumptions = []
        for i, r in enumerate(self.ranges):
            signed = r.lo < 0
            ge = "signed_ge" if signed else "unsigned_ge"
            le = "signed_le" if signed else "unsigned_le"
            t = "s64" if signed else "u64"
            assumptions.append(
                {
                    "id": f"A{i + 1}",
                    "expression": {
                        "all_of": [
                            {ge: {"left": r.path, "right": {"value": r.lo, "type": t}}},
                            {le: {"left": r.path, "right": {"value": r.hi, "type": t}}},
                        ]
                    },
                    "provenance": {"kind": "witness_dsl"},
                    "description": f"{r.path} in [{r.lo}, {r.hi}]",
                }
            )

        bindings = []
        for mc in self.map_correspondences:
            ok_bits = mc.orig_key_bytes * 8
            nk_bits = mc.opt_key_bytes * 8
            ov_bits = mc.orig_val_bytes * 8
            nv_bits = mc.opt_val_bytes * 8
            corr: dict = {"original_key": mc.key_var}
            if mc.key_narrows:
                corr["optimized_key"] = {
                    "truncate": {"value": mc.key_var, "width": nk_bits}
                }
                corr["assume"] = {
                    "unsigned_le": {
                        "left": mc.key_var,
                        "right": {"value": (1 << nk_bits) - 1, "type": f"u{ok_bits or 64}"},
                    }
                }
            else:
                corr["optimized_key"] = mc.key_var
            if mc.value_narrows:
                corr["value_relation"] = {
                    "equal": {
                        "left": "optimized.value",
                        "right": {
                            "truncate": {"value": "original.value", "width": nv_bits}
                        },
                    }
                }
            else:
                corr["value_relation"] = {"equal": True}
            okt = f"u{ok_bits}" if ok_bits else "_"
            nkt = f"u{nk_bits}" if nk_bits else "_"
            ovt = f"u{ov_bits}" if ov_bits else "_"
            nvt = f"u{nv_bits}" if nv_bits else "_"
            bindings.append(
                {
                    "name": mc.name,
                    "original": {"object": mc.original_name, "type": f"map<{okt}, {ovt}>"},
                    "optimized": {
                        "object": mc.name,
                        "type": f"map<{nkt}, {nvt}>",
                        "map_kind": mc.kind,
                    },
                    "relation": {"map_correspondence": corr},
                }
            )

        return {
            "witness": {
                "version": "0.1",
                "name": self.name,
                "bindings": bindings,
                "assumptions": assumptions,
                # No `observation` block in the DSL -- always empty, which
                # witness_spec.build_observation_selection() reads as
                # "compare every output" (return + every map + every global).
                "observations": [],
            }
        }


# --------------------------------------------------------------------------- #
# lowering
# --------------------------------------------------------------------------- #
def _diag(plan: WitnessPlan, severity: str, message: str, pos: Pos) -> None:
    plan.diagnostics.append(Diagnostic(severity, message, pos, "<witness_dsl:lower>"))


def _map_index_key(expr: A.Expr):
    """If `expr` is exactly `<side>.<map>[<var>]`, return the key var; else None."""
    if len(expr.accessors) == 1 and isinstance(expr.accessors[0], A.Index):
        return expr.accessors[0].key
    return None


def lower(program: A.Program, env: Env, name: str = "witness_dsl") -> WitnessPlan:
    plan = WitnessPlan(name=name)

    # -- assumptions --------------------------------------------------------
    if program.assumption is not None:
        for st in program.assumption.statements:
            if isinstance(st, A.RangeAssumption):
                if st.lo > st.hi:
                    _diag(
                        plan,
                        "warning",
                        f"range [{st.lo}, {st.hi}] is empty (lo > hi); kept as written",
                        st.pos,
                    )
                plan.ranges.append(RangeAssumption(st.expr.text(), st.lo, st.hi))
            elif isinstance(st, A.IgnoreAssumption):
                plan.ignored_helper_flags.append(st.helper)
                _diag(
                    plan,
                    "warning",
                    f"'ignore flag of {st.helper}' has no JSON representation; the "
                    f"check will NOT abstract {st.helper}'s flags argument in this "
                    f"transition path",
                    st.pos,
                )

    # -- bindings ---------------------------------------------------------
    if program.binding is not None:
        for st in program.binding.statements:
            lhs, rhs = st.lhs, st.rhs
            lk, rk = _map_index_key(lhs), _map_index_key(rhs)
            if lk is None or rk is None:
                if not lhs.accessors and not rhs.accessors:
                    plan.unsupported.append(
                        f"scalar binding '{lhs.text()} = {rhs.text()}' is not applied "
                        f"(objects still compared strictly)"
                    )
                else:
                    plan.unsupported.append(
                        f"binding '{lhs.text()} = {rhs.text()}' is not the "
                        f"original.M[k] = optimized.M[k] shape; skipped"
                    )
                _diag(
                    plan,
                    "warning",
                    "binding not lowered (see notes); it will not relax the check",
                    st.pos,
                )
                continue
            if lk != rk:
                _diag(
                    plan,
                    "warning",
                    f"binding key mismatch ('{lk}' vs '{rk}'); using '{lk}'",
                    st.pos,
                )
            o_name, p_name = lhs.root, rhs.root
            o_info = env.original.maps.get(o_name)
            p_info = env.optimized.maps.get(p_name)
            if o_info is None:
                _diag(plan, "warning", f"'{o_name}' is not a map in the original program; binding skipped", lhs.pos)
                continue
            if p_info is None:
                _diag(plan, "warning", f"'{p_name}' is not a map in the optimized program; binding skipped", rhs.pos)
                continue
            plan.map_correspondences.append(
                MapCorrespondence(
                    name=p_name,
                    original_name=o_name,
                    key_var=lk,
                    orig_key_bytes=o_info.key_bytes,
                    opt_key_bytes=p_info.key_bytes,
                    orig_val_bytes=o_info.value_bytes,
                    opt_val_bytes=p_info.value_bytes,
                    kind=p_info.kind,
                )
            )

    return plan
