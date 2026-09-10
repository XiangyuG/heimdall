"""Tests for the transformation-witness DSL syntax checker.

Standalone, no pytest dependency.  Run:

    python3 test_syntax.py

Covers: the lexer (keywords, numbers, comments, '[:]'), the parser
(every production, nested accessors, optional/empty blocks), the structural
rules enforced beyond the raw token stream (block order, operand sides,
non-empty observation), and the optional well-formedness warnings.  Also
round-trips every *.wit file under examples/.
"""

from __future__ import annotations

import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # so "witness_dsl" imports

from witness_dsl import ast_nodes as A  # noqa: E402
from witness_dsl.errors import DslSyntaxError  # noqa: E402
from witness_dsl.lexer import tokenize  # noqa: E402
from witness_dsl.parser import parse  # noqa: E402
from witness_dsl.syntax_check import check_source  # noqa: E402

EXAMPLES = os.path.join(HERE, "examples")

_passed = 0
_failed = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _passed, _failed
    if cond:
        _passed += 1
    else:
        _failed += 1
        print(f"  FAIL: {name}" + (f"  ({detail})" if detail else ""))


def expect_ok(name: str, src: str) -> A.Program | None:
    res = check_source(src, name)
    if not res.ok:
        check(name, False, res.errors[0].render(src) if res.errors else "?")
        return None
    check(name, True)
    return res.program


def expect_err(name: str, src: str, needle: str = "") -> None:
    res = check_source(src, name)
    if res.ok:
        check(name, False, "expected a syntax error, got none")
        return
    msg = res.errors[0].message
    check(name, needle.lower() in msg.lower(), f"message was: {msg!r}")


# --------------------------------------------------------------------------
# lexer
# --------------------------------------------------------------------------


def test_lexer():
    kinds = [t.kind for t in tokenize("assumption { original.x in [0,-3] ; }")]
    check(
        "lex/keywords+punct",
        kinds
        == [
            "ASSUMPTION",
            "LBRACE",
            "ORIGINAL",
            "DOT",
            "IDENT",
            "IN",
            "LBRACK",
            "INT",
            "COMMA",
            "MINUS",
            "INT",
            "RBRACK",
            "SEMI",
            "RBRACE",
            "EOF",
        ],
        str(kinds),
    )

    toks = tokenize("0 0x1F 42")
    check("lex/int-values", [t.value for t in toks[:3]] == [0, 31, 42], str([t.value for t in toks[:3]]))

    check("lex/mapall-one-token", tokenize("m[:]")[1].kind == "MAPALL")
    check("lex/bracket-plain", tokenize("m[k]")[1].kind == "LBRACK")

    line_c = tokenize("a // comment\n b")
    check("lex/line-comment", [t.text for t in line_c[:2]] == ["a", "b"])
    block_c = tokenize("a /* x\n y */ b")
    check("lex/block-comment", [t.text for t in block_c[:2]] == ["a", "b"])

    for bad, why in [
        ("01", "leading zero"),
        ("0x", "0x"),
        ("12ab", "malformed"),
        ("/* unterminated", "unterminated"),
        ("m[:x]", "close"),
        ("@", "unexpected"),
    ]:
        try:
            tokenize(bad)
            check(f"lex/reject {bad!r}", False, "no error raised")
        except DslSyntaxError as e:
            check(f"lex/reject {bad!r}", why.lower() in e.diagnostic.message.lower(), e.diagnostic.message)


# --------------------------------------------------------------------------
# parser -- valid
# --------------------------------------------------------------------------


def test_parser_valid():
    p = expect_ok(
        "parse/full",
        """
        assumption {
            original.ctx.rx_queue_index in [0, 65535];
            optimized.q in [-1, 0x10];
            ignore flag of bpf_map_update_elem;
        }
        binding {
            original.m[k] = optimized.m[k];
        }
        observation {
            original.return = optimized.return;
            original.m[:].value = optimized.m[:].value;
        }
        """,
    )
    if p:
        check("parse/full/assumption-count", len(p.assumption.statements) == 3)
        check("parse/full/binding-count", len(p.binding.statements) == 1)
        check("parse/full/observation-count", len(p.observation.statements) == 2)
        rng = p.assumption.statements[0]
        check("parse/full/range-bounds", (rng.lo, rng.hi) == (0, 65535))
        check("parse/full/neg-hex", (p.assumption.statements[1].lo, p.assumption.statements[1].hi) == (-1, 16))
        check("parse/full/ignore", p.assumption.statements[2].helper == "bpf_map_update_elem")
        obs2 = p.observation.statements[1]
        check("parse/full/nested-accessors", obs2.lhs.text() == "original.m[:].value", obs2.lhs.text())

    p = expect_ok("parse/minimal", "observation { original.return = optimized.return; }")
    if p:
        check("parse/minimal/no-assumption", p.assumption is None)
        check("parse/minimal/no-binding", p.binding is None)

    p = expect_ok(
        "parse/empty-blocks",
        "assumption { } binding { } observation { original.a = optimized.a; }",
    )
    if p:
        check("parse/empty-blocks/assumption-empty", p.assumption.statements == [])
        check("parse/empty-blocks/binding-empty", p.binding.statements == [])

    p = expect_ok(
        "parse/deep-chain",
        "observation { original.a[k].b.c = optimized.a[k].b.c; }",
    )
    if p:
        acc = p.observation.statements[0].lhs.accessors
        check("parse/deep-chain/len", len(acc) == 3)
        check(
            "parse/deep-chain/kinds",
            [type(x).__name__ for x in acc] == ["Index", "Field", "Field"],
            str([type(x).__name__ for x in acc]),
        )

    # deliberately permissive: kind-nonsense still parses (semantic layer's job)
    expect_ok("parse/permissive-double-mapall", "observation { original.m[:][:] = optimized.m[:][:]; }")


# --------------------------------------------------------------------------
# parser -- invalid
# --------------------------------------------------------------------------


def test_parser_invalid():
    expect_err("err/missing-semi", "observation { original.a = optimized.a }", "';'")
    expect_err(
        "err/block-order",
        "binding { original.a = optimized.a; } assumption { } observation { original.a = optimized.a; }",
        "out of order",
    )
    expect_err("err/no-observation", "assumption { ignore flag of h; }", "observation")
    expect_err(
        "err/empty-observation", "observation { }", "at least one"
    )
    expect_err(
        "err/lhs-not-original",
        "observation { optimized.a = original.a; }",
        "left-hand side",
    )
    expect_err(
        "err/rhs-not-optimized",
        "observation { original.a = original.a; }",
        "right-hand side",
    )
    expect_err("err/reserved-field", "observation { original.x.flag = optimized.x.flag; }", "field name")
    expect_err("err/bare-side", "observation { original = optimized; }", "'.'")
    expect_err("err/index-not-ident", "observation { original.m[0] = optimized.m[0]; }", "key variable")
    expect_err("err/range-missing-comma", "assumption { original.a in [0 5]; } observation { original.a = optimized.a; }", "','")
    expect_err("err/trailing-junk", "observation { original.a = optimized.a; } xyz", "end of input")
    expect_err("err/unclosed-block", "observation { original.a = optimized.a;", "'}'")


# --------------------------------------------------------------------------
# well-formedness warnings
# --------------------------------------------------------------------------


def test_warnings():
    res = check_source(
        "assumption { original.a in [10, 0]; } observation { original.a = optimized.a; }",
        "w1",
    )
    check("warn/empty-range/ok", res.ok)
    check("warn/empty-range/warned", any("lower bound exceeds" in w.message for w in res.warnings))

    res = check_source(
        "assumption { ignore flag of h; ignore flag of h; } observation { original.a = optimized.a; }",
        "w2",
    )
    check("warn/dup-ignore", any("duplicate 'ignore flag of h'" in w.message for w in res.warnings))

    res = check_source(
        "observation { original.a = optimized.a; original.a = optimized.a; }", "w3"
    )
    check("warn/dup-observation", any("duplicate observation" in w.message for w in res.warnings))

    res = check_source(
        "assumption { original.a in [10, 0]; } observation { original.a = optimized.a; }",
        "w4",
        extra=False,
    )
    check("warn/suppressed-with-extra-false", res.warnings == [])


# --------------------------------------------------------------------------
# examples/*.wit round-trip
# --------------------------------------------------------------------------


def test_examples():
    files = sorted(f for f in os.listdir(EXAMPLES) if f.endswith(".wit"))
    check("examples/present", len(files) >= 4, str(files))
    for f in files:
        with open(os.path.join(EXAMPLES, f), encoding="utf-8") as fh:
            src = fh.read()
        res = check_source(src, f)
        if f.startswith("invalid_"):
            check(f"examples/{f} rejected", not res.ok, res.errors[0].message if res.errors else "?")
        else:
            check(f"examples/{f} accepted", res.ok, res.errors[0].render(src) if res.errors else "?")


def main() -> int:
    for fn in (
        test_lexer,
        test_parser_valid,
        test_parser_invalid,
        test_warnings,
        test_examples,
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
