"""Tests for the transformation-witness DSL equivalence checker (equivalence.py).

Standalone, no pytest. Run:

    python3 test_equivalence.py

Mirrors test_lower.py's style: hand-built Env objects, no BTF / elftools
needed.
"""

from __future__ import annotations

import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # c2rust_translation, for witness_dsl

from witness_dsl import parse  # noqa: E402
from witness_dsl.equivalence import check_equivalent, check_files_equivalent, check_sources_equivalent  # noqa: E402
from witness_dsl.errors import Diagnostic, Pos  # noqa: E402
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


def mn_env():
    return Env(
        original=SideEnv({"m": MapInfo(4, 8), "n": MapInfo(4, 4)}),
        optimized=SideEnv({"m": MapInfo(4, 8), "n": MapInfo(4, 4)}),
    )


def plan_of(src, env=None):
    return lower(parse(src, "<test>"), env or Env(SideEnv(), SideEnv()))


# --------------------------------------------------------------------------
def test_identical_reordered():
    src_a = """
    assumption {
        original.ctx.x in [0, 100];
        ignore flag of h1;
        ignore flag of h2;
    }
    binding {
        original.m[k] = optimized.m[k];
        original.n[j] = optimized.n[j];
    }
    """
    src_b = """
    assumption {
        ignore flag of h2;
        original.ctx.x in [0, 100];
        ignore flag of h1;
    }
    binding {
        original.n[j] = optimized.n[j];
        original.m[k] = optimized.m[k];
    }
    """
    r = check_sources_equivalent(src_a, src_b, mn_env())
    check("reordered/equivalent", r.equivalent, r.render())
    check("reordered/no-diffs", not r.ranges_diff and not r.ranges_only_in_a and not r.ranges_only_in_b)


def test_alpha_renamed_key_var():
    src_a = "binding { original.m[k] = optimized.m[k]; }"
    src_b = "binding { original.m[j] = optimized.m[j]; }"
    r = check_sources_equivalent(src_a, src_b, mn_env())
    check("alpha/equivalent", r.equivalent, r.render())


def test_range_bounds_differ():
    src_a = "assumption { original.ctx.x in [0, 100]; }"
    src_b = "assumption { original.ctx.x in [0, 50]; }"
    r = check_sources_equivalent(src_a, src_b, mn_env())
    check("bounds-differ/not-equivalent", not r.equivalent)
    check("bounds-differ/diff", r.ranges_diff == [("original.ctx.x", "unsigned", (0, 100), (0, 50))], str(r.ranges_diff))


def test_range_split_same_net():
    src_a = "assumption { original.ctx.x in [10, 50]; }"
    src_b = "assumption { original.ctx.x in [0, 50]; original.ctx.x in [10, 100]; }"
    r = check_sources_equivalent(src_a, src_b, mn_env())
    check("split-same-net/equivalent", r.equivalent, r.render())


def test_range_split_different_net():
    src_a = "assumption { original.ctx.x in [0, 100]; }"
    src_b = "assumption { original.ctx.x in [0, 100]; original.ctx.x in [20, 80]; }"
    r = check_sources_equivalent(src_a, src_b, mn_env())
    check("split-diff-net/not-equivalent", not r.equivalent)
    check("split-diff-net/diff", r.ranges_diff == [("original.ctx.x", "unsigned", (0, 100), (20, 80))], str(r.ranges_diff))


def test_dead_range_both_sides_equal():
    src_a = "assumption { original.ctx.x in [10, 5]; }"
    src_b = "assumption { original.ctx.x in [20, 1]; }"
    r = check_sources_equivalent(src_a, src_b, mn_env())
    check("dead-both/equivalent", r.equivalent, r.render())
    check("dead-both/notes", len(r.notes) == 2, str(r.notes))


def test_dead_via_intersection_only():
    src_a = "assumption { original.ctx.x in [0, 100]; }"
    src_b = "assumption { original.ctx.x in [0, 10]; original.ctx.x in [20, 100]; }"
    r = check_sources_equivalent(src_a, src_b, mn_env())
    check("dead-intersection/not-equivalent", not r.equivalent)
    check("dead-intersection/diff",
          r.ranges_diff == [("original.ctx.x", "unsigned", (0, 100), "<empty>")], str(r.ranges_diff))
    check("dead-intersection/note-mentions-intersecting",
          any("intersecting" in n for n in r.notes), str(r.notes))


def test_signed_unsigned_same_path_kept_separate():
    src_a = "assumption { original.ctx.x in [-5, 10]; }"
    src_b = "assumption { original.ctx.x in [-5, 10]; original.ctx.x in [0, 1000]; }"
    r = check_sources_equivalent(src_a, src_b, mn_env())
    check("sign-split/not-equivalent", not r.equivalent)
    check("sign-split/only-in-b",
          r.ranges_only_in_b == [("original.ctx.x", "unsigned", (0, 1000))], str(r.ranges_only_in_b))
    check("sign-split/no-false-diff", r.ranges_diff == [], str(r.ranges_diff))


def test_ignored_flags_set_semantics():
    src_a = "assumption { ignore flag of h1; ignore flag of h1; ignore flag of h2; }"
    src_b = "assumption { ignore flag of h2; ignore flag of h1; }"
    r = check_sources_equivalent(src_a, src_b, mn_env())
    check("flags-same-set/equivalent", r.equivalent, r.render())

    src_c = "assumption { ignore flag of h1; }"
    r2 = check_sources_equivalent(src_a, src_c, mn_env())
    check("flags-diff-set/not-equivalent", not r2.equivalent)
    check("flags-diff-set/only-in-a", r2.ignored_flags_only_in_a == ["h2"], str(r2.ignored_flags_only_in_a))


def test_unsupported_binding_present_only_in_one_is_informational():
    src_a = "binding { original.m[k] = optimized.m[k]; }"
    src_b = "binding { original.m[k] = optimized.m[k]; original.scalarx = optimized.scalarx; }"
    r = check_sources_equivalent(src_a, src_b, mn_env())
    check("unsupported-only-b/equivalent", r.equivalent, r.render())
    check("unsupported-only-b/informational", r.unsupported_only_in_b != [], str(r.unsupported_only_in_b))
    check("unsupported-only-b/flagged", r.has_informational_differences())


def test_diagnostics_only_diff_unknown_map():
    src_a = "binding { original.m[k] = optimized.m[k]; }"
    src_b = "binding { original.m[k] = optimized.m[k]; original.ghost[k] = optimized.ghost[k]; }"
    r = check_sources_equivalent(src_a, src_b, mn_env())
    check("unknown-map/equivalent", r.equivalent, r.render())
    check("unknown-map/diag-only-b", r.diagnostics_only_in_b != [], str(r.diagnostics_only_in_b))


def test_hard_lowering_error_inconclusive():
    # `lower()` never actually produces a "severity=error" diagnostic today
    # (real syntax errors are raised as DslSyntaxError before a Program
    # exists) -- this exercises the forward-compat guard directly.
    plan_a = WitnessPlan(name="a")
    plan_a.diagnostics.append(Diagnostic("error", "synthetic hard error", Pos(1, 1, 0), "<test>"))
    plan_b = WitnessPlan(name="b")
    r = check_equivalent(plan_a, plan_b)
    check("hard-error/inconclusive", r.inconclusive)
    check("hard-error/reason-mentions-a", "A" in (r.reason or ""), str(r.reason))


def test_syntax_error_inconclusive():
    env = Env(SideEnv(), SideEnv())
    r = check_files_equivalent(
        os.path.join(EXAMPLES, "invalid_missing_semicolon.wit"),
        os.path.join(EXAMPLES, "empty_blocks.wit"),
        env,
    )
    check("syntax-error/inconclusive", r.inconclusive, r.reason)


def test_two_empty_witnesses_equivalent():
    env = Env(SideEnv(), SideEnv())
    r = check_sources_equivalent("", "assumption {} binding {}", env)
    check("empty-vs-empty/equivalent", r.equivalent, r.render())


def test_empty_vs_nonempty():
    env = Env(SideEnv(), SideEnv())
    r = check_sources_equivalent("", "assumption { original.ctx.x in [0, 10]; }", env)
    check("empty-vs-nonempty/not-equivalent", not r.equivalent)
    check("empty-vs-nonempty/only-in-b",
          r.ranges_only_in_b == [("original.ctx.x", "unsigned", (0, 10))], str(r.ranges_only_in_b))


def test_map_correspondence_byte_width_sensitivity():
    src = "binding { original.m[k] = optimized.m[k]; }"
    env_no_narrow = Env(SideEnv({"m": MapInfo(4, 8)}), SideEnv({"m": MapInfo(4, 8)}))
    env_narrow = Env(SideEnv({"m": MapInfo(4, 8)}), SideEnv({"m": MapInfo(2, 8)}))
    plan_a = plan_of(src, env_no_narrow)
    plan_b = plan_of(src, env_narrow)
    r = check_equivalent(plan_a, plan_b)
    check("env-sensitivity/not-equivalent", not r.equivalent)
    check("env-sensitivity/diff", r.map_corr_only_in_a != [] and r.map_corr_only_in_b != [], r.render())


def main():
    for fn in (
        test_identical_reordered,
        test_alpha_renamed_key_var,
        test_range_bounds_differ,
        test_range_split_same_net,
        test_range_split_different_net,
        test_dead_range_both_sides_equal,
        test_dead_via_intersection_only,
        test_signed_unsigned_same_path_kept_separate,
        test_ignored_flags_set_semantics,
        test_unsupported_binding_present_only_in_one_is_informational,
        test_diagnostics_only_diff_unknown_map,
        test_hard_lowering_error_inconclusive,
        test_syntax_error_inconclusive,
        test_two_empty_witnesses_equivalent,
        test_empty_vs_nonempty,
        test_map_correspondence_byte_width_sensitivity,
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
