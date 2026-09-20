"""Tests for the transformation-witness DSL semantic lowering (lower.py).

Standalone, no pytest. Run:

    python3 test_lower.py

`lower()` is exercised with hand-built Env objects (no BTF / elftools needed).
One test round-trips the emitted legacy JSON through witness_spec, and is
skipped if claripy is unavailable.
"""

from __future__ import annotations

import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # c2rust_translation, for witness_dsl + witness_spec

from witness_dsl import parse  # noqa: E402
from witness_dsl.lower import Env, MapInfo, SideEnv, WitnessPlan, lower  # noqa: E402

EXAMPLES = os.path.join(HERE, "examples")

_passed = 0
_failed = 0


def check(name, cond, detail=""):
    global _passed, _failed
    if cond:
        _passed += 1
    else:
        _failed += 1
        print(f"  FAIL: {name}" + (f"  ({detail})" if detail else ""))


def load(fname):
    with open(os.path.join(EXAMPLES, fname), encoding="utf-8") as fh:
        return parse(fh.read(), fname)


def lower_src(src, env=None):
    return lower(parse(src, "<test>"), env or Env(SideEnv(), SideEnv()))


# --------------------------------------------------------------------------
# reduce_queue: key narrowing 32 -> 16, value unchanged
# --------------------------------------------------------------------------
def test_reduce_queue():
    env = Env(
        original=SideEnv({"queue_packets": MapInfo(4, 8, "hash")}),
        optimized=SideEnv({"queue_packets": MapInfo(2, 8, "hash")}),
    )
    plan = lower(load("reduce_queue.wit"), env, name="reduce_queue")

    check("rq/no-errors", not plan.has_errors, str([d.render() for d in plan.diagnostics]))
    check("rq/range", [(r.path, r.lo, r.hi) for r in plan.ranges]
          == [("original.ctx.rx_queue_index", 0, 65535)], str(plan.ranges))
    check("rq/ignored-flag", plan.ignored_helper_flags == ["bpf_map_update_elem"])
    check("rq/ignore-warned",
          any("ignore flag of bpf_map_update_elem".replace("flag of ", "") in d.message
              or "bpf_map_update_elem" in d.message for d in plan.diagnostics
              if d.severity == "warning"))
    check("rq/one-corr", len(plan.map_correspondences) == 1, str(plan.map_correspondences))
    mc = plan.map_correspondences[0]
    check("rq/corr-shape",
          (mc.name, mc.key_var, mc.orig_key_bytes, mc.opt_key_bytes,
           mc.orig_val_bytes, mc.opt_val_bytes) == ("queue_packets", "k", 4, 2, 8, 8),
          str(mc))
    check("rq/key-narrows", mc.key_narrows and not mc.value_narrows)

    j = plan.to_legacy_json()["witness"]
    check("rq/json-name", j["name"] == "reduce_queue")
    corr = j["bindings"][0]["relation"]["map_correspondence"]
    check("rq/json-trunc-key", corr["optimized_key"] == {"truncate": {"value": "k", "width": 16}}, str(corr))
    check("rq/json-assume", corr["assume"]["unsigned_le"]["right"]["value"] == 65535, str(corr.get("assume")))
    check("rq/json-value-equal", corr["value_relation"] == {"equal": True}, str(corr["value_relation"]))
    aexpr = j["assumptions"][0]["expression"]["all_of"]
    check("rq/json-range-ops",
          set(list(aexpr[0])[0] for _ in [0]) == {"unsigned_ge"}
          and list(aexpr[1])[0] == "unsigned_le", str(aexpr))
    check("rq/json-range-vals",
          aexpr[0]["unsigned_ge"]["right"]["value"] == 0
          and aexpr[1]["unsigned_le"]["right"]["value"] == 65535, str(aexpr))
    # No `observation` block in the DSL: to_legacy_json() always emits [],
    # which witness_spec.build_observation_selection() reads as "compare
    # every output" -- see test_roundtrip_witness_spec below.
    check("rq/json-observations-empty", j["observations"] == [], str(j["observations"]))


# --------------------------------------------------------------------------
# empty program: no blocks at all -> empty plan, still compares everything
# --------------------------------------------------------------------------
def test_empty_program():
    plan = lower(parse("", "<empty>"), Env(SideEnv(), SideEnv()))
    check("empty/no-errors", not plan.has_errors)
    check("empty/all-empty", not plan.ranges and not plan.map_correspondences
          and not plan.ignored_helper_flags and not plan.unsupported)
    j = plan.to_legacy_json()["witness"]
    check("empty/json", j["bindings"] == [] and j["assumptions"] == []
          and j["observations"] == [], str(j))


# --------------------------------------------------------------------------
# empty_blocks: signed range, empty binding block
# --------------------------------------------------------------------------
def test_empty_blocks():
    env = Env(SideEnv({"pkts": MapInfo(4, 8)}), SideEnv({"pkts": MapInfo(4, 8)}))
    plan = lower(load("empty_blocks.wit"), env)
    check("eb/no-errors", not plan.has_errors)
    check("eb/range", [(r.path, r.lo, r.hi) for r in plan.ranges]
          == [("optimized.cfg[key].rate", -1, 0x7fffffff)], str(plan.ranges))
    check("eb/no-corr", plan.map_correspondences == [])
    j = plan.to_legacy_json()["witness"]
    ops = [list(c)[0] for c in j["assumptions"][0]["expression"]["all_of"]]
    check("eb/json-signed-ops", ops == ["signed_ge", "signed_le"], str(ops))
    check("eb/json-signed-type",
          j["assumptions"][0]["expression"]["all_of"][0]["signed_ge"]["right"]["type"] == "s64")


# --------------------------------------------------------------------------
# unsupported binding shapes are warnings, not errors
# --------------------------------------------------------------------------
def test_unsupported_bindings():
    src = """
    binding {
        original.scalarx = optimized.scalarx;
        original.m[:].f = optimized.m[:].f;
    }
    """
    plan = lower_src(src)
    check("ub/no-errors", not plan.has_errors, str([d.render() for d in plan.diagnostics]))
    check("ub/no-corr", plan.map_correspondences == [])
    check("ub/scalar-note", any("scalar binding" in n for n in plan.unsupported), str(plan.unsupported))
    check("ub/shape-note", any("original.M[k]" in n for n in plan.unsupported), str(plan.unsupported))
    check("ub/warned", all(d.severity == "warning" for d in plan.diagnostics))


def test_unknown_map_binding():
    src = "binding { original.ghost[k] = optimized.ghost[k]; }"
    plan = lower_src(src, Env(SideEnv(), SideEnv()))
    check("um/no-errors", not plan.has_errors)
    check("um/no-corr", plan.map_correspondences == [])
    check("um/warned", any("not a map" in d.message for d in plan.diagnostics))


# --------------------------------------------------------------------------
# legacy-JSON round-trip through witness_spec (needs claripy)
# --------------------------------------------------------------------------
def test_roundtrip_witness_spec():
    try:
        import claripy  # noqa: F401
        from witness_spec import witness_spec_from_doc
    except Exception as e:  # noqa: BLE001
        print(f"  skip test_roundtrip_witness_spec ({e})")
        return
    env = Env(
        original=SideEnv({"queue_packets": MapInfo(4, 8)}),
        optimized=SideEnv({"queue_packets": MapInfo(2, 8)}),
    )
    plan = lower(load("reduce_queue.wit"), env, name="reduce_queue")
    spec = witness_spec_from_doc(plan.to_legacy_json(), source_path="reduce_queue.wit")
    check("rt/name", spec.name == "reduce_queue")
    check("rt/counts", (len(spec.bindings), len(spec.assumptions), len(spec.observations)) == (1, 1, 0),
          f"{len(spec.bindings)},{len(spec.assumptions)},{len(spec.observations)}")
    check("rt/binding-is-map", spec.bindings[0].is_map)
    check("rt/derived-map-specs", spec.derived_map_specs() == ["queue_packets:hash"],
          str(spec.derived_map_specs()))

    from witness_spec import build_binding_plan, build_observation_selection
    bp = build_binding_plan(spec)
    check("rt/binding-plan", bp is not None and "queue_packets" in bp.maps)
    # Empty observations -> build_observation_selection returns None, which
    # means "no restriction": compare the return value and every map/global.
    sel = build_observation_selection(spec)
    check("rt/obs-selection-none", sel is None, str(sel))


def main():
    for fn in (
        test_reduce_queue,
        test_empty_program,
        test_empty_blocks,
        test_unsupported_bindings,
        test_unknown_map_binding,
        test_roundtrip_witness_spec,
    ):
        print(f"# {fn.__name__}")
        try:
            fn()
        except Exception:  # noqa: BLE001
            global _failed
            _failed += 1
            traceback.print_exc()
    print(f"\n{_passed} passed, {_failed} failed")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
