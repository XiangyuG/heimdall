# `witness_dsl` — transformation-witness DSL: syntax layer

A small, dependency-free front end for the textual transformation-witness
language. It answers exactly one question:

> **Does this file conform to `GRAMMAR.bnf`?**

It does **not** resolve names, check kinds, or interpret meaning. That is a
separate semantic pass (a later module) that consumes the AST this package
produces.

## What a witness looks like

```
// examples/reduce_queue.wit
assumption {
    original.ctx.rx_queue_index in [0, 65535];
    ignore flag of bpf_map_update_elem;
}

binding {
    original.queue_packets[k] = optimized.queue_packets[k];
}
```

- **`assumption`** *(optional, may be empty)* — preconditions. Either a range
  `<side>.<expr> in [lo, hi]` on the original **or** optimized side, or
  `ignore flag of <helper-name>` (abstract away a helper's `flags` argument so
  Heimdall models the helper for all flag values).
- **`binding`** *(optional, may be empty)* — assumed original↔optimized
  correspondences, always `original.<expr> = optimized.<expr>`.

There is no `observation` block. Heimdall always compares every output
(return value, every map, every `.data` global) — a witness only ever adds
premises (`assumption`/`binding`); it never narrows what gets compared.

Integers may be negative (`-1`) or hexadecimal (`0x7fffffff`); decimal
literals may not have a leading zero. `;` terminates every statement.
Comments are `// line` and `/* block */`.

The full grammar, including the lexical rules that a bare BNF cannot state,
is in **[`GRAMMAR.bnf`](GRAMMAR.bnf)**.

## Usage

CLI:

```
python3 -m witness_dsl path/to/witness.wit [more.wit ...]
# or, from this directory:
python3 syntax_check.py path/to/witness.wit
```

Flags: `-q/--quiet` (only print failures), `--no-extra` (skip the optional
well-formedness warnings), `--strict` (warnings fail the run). Exit code is
`0` iff every file is syntactically valid.

Library:

```python
from witness_dsl import check_file, parse

res = check_file("witness.wit")
if res.ok:
    program = res.program          # ast_nodes.Program -> feed the semantic pass
    for w in res.warnings:
        print(w.render())
else:
    print(res.errors[0].render())  # gcc-style message + caret

program = parse(source_text)       # raises DslSyntaxError on the first error
```

## Layout

| file | role |
|---|---|
| `GRAMMAR.bnf` | authoritative grammar + lexical side conditions |
| `TEACHING.md` | annotated walkthrough: each design decision as valid/invalid `.wit` pairs |
| `lexer.py` | `tokenize(src)` → `[Token]`; keywords, numbers, comments, `[:]` |
| `ast_nodes.py` | dataclass AST (`Program`, `Expr`, statements, …) |
| `parser.py` | recursive-descent `parse(src)` → `Program` |
| `syntax_check.py` | `check_source` / `check_file` API + CLI |
| `errors.py` | `Pos`, `Diagnostic` (caret rendering), `DslSyntaxError` |
| `examples/*.wit` | valid + `invalid_*` fixtures |
| `test_syntax.py` | standalone test suite — `python3 test_syntax.py` |

## What "syntax checking" covers here

1. **Lexing** — token classes, reserved words, number forms, comment
   handling, `[:]` as one token.
2. **Parsing** — every production in `GRAMMAR.bnf`, LL(2), recursive descent.
3. **Structural rules the productions encode** but a token stream does not:
   block order (`assumption? binding?`) and single occurrence, and the
   fixed `original. = optimized.` sides of each `=`.
4. **Optional well-formedness warnings** (`--no-extra` to skip, `--strict` to
   enforce): empty range `[lo > hi]`, duplicate `ignore flag of X`, duplicate
   identical binding statement.

## Deliberately **out of scope** (the semantic pass)

- Does `original.m` name a real variable/map in the original program?
- Is `m[:]` applied to a map and `.f` to a struct? (`x[:][:]`, `scalar.f`
  parse fine here — kind checking rejects them later.)
- Is `bpf_map_update_elem` a helper that actually takes a `flags` argument?
- Lowering the two blocks to a relational proof obligation.

## Known limitation

Reserved words (`assumption binding in ignore flag of original
optimized`) cannot be used as variable, field, or helper names. If a real BPF
struct ever has a field literally named one of these, the keywords would need
to become contextual.
