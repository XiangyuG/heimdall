# `witness_dsl` design rationale

> A teaching document. Each section corresponds to one production in
> `GRAMMAR.bnf` or one design decision, shown as a valid/invalid contrast to
> explain what the rule means and why it was carved out this way. Every code
> snippet has actually been run through `syntax_check.py` — the error text
> shown is real output.

How to run it (from the `c2rust_translation/` directory):

```
python3 -m witness_dsl path/to/file.wit        # full report
python3 -m witness_dsl -q *.wit                # only print failures
python3 -m witness_dsl --strict file.wit       # warnings count as failures
```

Exit code `0` iff every file is syntactically valid.

---

## 0. One-sentence philosophy

This DSL's front end answers **exactly one question**:

> Does this file conform to `GRAMMAR.bnf`?

It does not resolve names, check kinds, or interpret meaning. Whether
`original.m` actually exists, whether `m[:]` is really applied to a map, or
whether `bpf_map_update_elem` really takes a `flags` argument — all of that
is left to the semantic layer (`lower.py`) further down the pipeline.

**Teaching point**: where the line between the syntax layer and the semantic
layer is drawn is the single most important decision in this DSL's design.
Every "deliberately permissive" marker in the sections below is an
instance of that line.

---

## 1. A program is two sections, fixed order, both optional and may be empty

```bnf
<program> ::= <opt-assumption-block> <opt-binding-block>

<opt-assumption-block> ::= <assumption-block> | ε
<opt-binding-block>    ::= <binding-block>    | ε
```

> Design decision (4): `assumption` and `binding` may both be omitted, and
> may both be empty blocks. There is **no** `observation` concept in this
> language — heimdall always compares every output (return value, every
> map, every `.data` global). A witness can only add premises; it can never
> narrow what gets compared.

Mechanism: a witness's core assertion is always "every output must still
match after the optimization", but the *scope* of that assertion isn't
something the witness author gets to pick — it's the checker's fixed
default behavior. All a witness can do is add a premise (`assumption`) or a
correspondence (`binding`) that lets an otherwise-"not equivalent" legal
optimization go through; without them, the check only gets stricter, never
unsound. **This is why the language has no syntax at all for saying "only
compare this, ignore that" — that's a deliberate design choice, not an
oversight.**

### 1.1 The smallest legal program — a completely empty file

```wit
// Writing no blocks at all is legal: no premises, no bindings, every
// output is still compared as usual.
```

```
=> OK
```

### 1.2 Both sections present but empty — legal

```wit
assumption {
}
binding {
}
```

```
=> OK
```

### 1.3 Blocks out of order — invalid

```wit
binding {
}
assumption {
}
```

```
error: keyword 'assumption' block is out of order or repeated; blocks must
appear as: assumption? binding? (each at most once)
  |
3 | assumption {
  | ^^^^^^^^^^
```

The order is baked into the production (not treated as a set), so "wrong
order" and "duplicate" are reported as the same error.

### 1.4 The same block appearing twice — invalid

```wit
binding {
    original.a = optimized.a;
}
binding {
    original.b = optimized.b;
}
```

```
error: keyword 'binding' block is out of order or repeated; blocks must
appear as: assumption? binding? (each at most once)
```

---

## 2. `;` is a statement terminator, always required

```bnf
<assumption-statement> ::= <range-assumption>  ";" | <ignore-assumption> ";"
<binding-statement>    ::= <original-expression> "=" <optimized-expression> ";"
```

> Design decision (9): `;` is a terminator and must always be written.

```wit
binding {
    original.x = optimized.x
}
```

```
error: expected ';', found '}'
  |
3 | }
  | ^
```

Mechanism: not treating "end of line" as an implicit statement boundary
means multi-line expressions and interleaved comments never change where a
statement ends. The cost is that every statement needs its own semicolon.

---

## 3. A `binding`'s `=` is fixed as `original.` = `optimized.`

```bnf
<binding-statement> ::= <original-expression> "=" <optimized-expression> ";"

<original-expression>  ::= "original"  "." <expression>
<optimized-expression> ::= "optimized" "." <expression>
```

The left side **must** be `original.`; the right side **must** be
`optimized.`.

```wit
binding {
    optimized.x = original.x;
}
```

```
error: the left-hand side of a binding statement must be an
'original.' expression, found 'optimized.'
```

Mechanism: a witness describes a **directional** transformation (original →
optimized). Baking the direction into the grammar means the semantic layer
never has to disambiguate "which side of this equation is the baseline".

---

## 4. An expression = a variable + a chain of accessors (deliberately permissive)

```bnf
<expression>    ::= <variable> <accessor-list>
<accessor-list> ::= ε | <accessor> <accessor-list>
<accessor>      ::= "[:]" | "[" <variable> "]" | "." <field-name>
```

> Design decision (6): an expression is "a variable plus a run of
> accessors", so nested access like `m[k].a.b` and `m[:].v` is naturally
> writable. The grammar is **deliberately permissive** here: `x[:][:]` and
> `scalar.f` also parse. Kind consistency is left to the semantic layer, not
> this checker.

### 4.1 Nested access — legal

```wit
binding {
    original.m[k].a.b = optimized.m[k].a.b;
    original.m[:].v   = optimized.m[:].v;
}
```

```
=> OK
```

The three accessor kinds can be chained arbitrarily: `[:]` (every key of a
map), `[k]` (a variable used as a key), `.field` (a struct field).

### 4.2 Obviously "type-wrong" spellings — the syntax layer lets them through anyway

```wit
binding {
    original.x[:][:]  = optimized.x[:][:];
    original.scalar.f = optimized.scalar.f;
}
```

```
=> OK
```

`x[:][:]` (iterating a map twice) and `scalar.f` (taking a field of a
scalar) are both semantically wrong, but **the syntax layer doesn't care**.
They get rejected by the kind check in `lower.py` instead (recorded as
`unsupported`, a warning, never a hard failure).

**Teaching point**: a permissive grammar plus an independent semantic layer
is easier to maintain than "stuff every constraint into the grammar" — the
BNF stays small and stable, and type rules can evolve on their own.

---

## 5. `[:]` is a single indivisible token

> Lexical side condition L4: `[:]` is one token; no whitespace is allowed
> between `[`, `:`, and `]`.
> L6: maximal munch — the lexer consumes the longest valid token at each
> step.

```wit
binding {
    original.m[ : ].v = optimized.m[ : ].v;
}
```

```
error: unexpected character ':'
  |
2 |     original.m[ : ].v = optimized.m[ : ].v;
  |                 ^
```

Mechanism: `[` is only recognized as "iterate every key" when a `:`
immediately follows it. As soon as there's whitespace, `[` instead follows
the `[` `<variable>` `]` production, and `:` isn't a legal variable, hence
the "unexpected character" error. Making `[:]` an atomic token avoids
needing lookahead after `[` to decide which production to take.

---

## 6. Integers: may be negative, may be hex, decimals may not have a leading zero

```bnf
<number>          ::= <unsigned-number> | "-" <unsigned-number>
<unsigned-number> ::= <decimal> | <hex>
<decimal>         ::= "0" | <nonzero-digit> <digit-list>
<hex>             ::= "0x" <hex-digit> <hex-digit-list>
```

> Design decision (5): integers may carry a leading `-` and may be written
> in hexadecimal (`0x...`); decimal literals may not have a leading zero.
> Lexical side condition L5: `01`, `007` are lexical errors; `0x` with no
> following hex digit is also a lexical error.

### 6.1 Legal

```wit
assumption {
    original.x in [-1, 0x7fffffff];
    optimized.y in [0, 255];
}
```

```
=> OK
```

### 6.2 Leading zero — invalid

```wit
assumption {
    original.x in [0, 007];
}
```

```
error: decimal literal may not have a leading zero
  |
2 |     original.x in [0, 007];
  |                       ^^^
```

Mechanism: a leading zero means octal in many languages. Banning it
outright removes the "is `010` 8 or 10?" ambiguity and forces the author to
be explicit about intent.

### 6.3 `0x` with no hex digits after it — invalid

```wit
assumption {
    original.x in [0, 0x];
}
```

```
error: hexadecimal literal has no digits after '0x'
```

---

## 7. A `range` assumption may constrain either side

```bnf
<range-assumption> ::= <side-expression> "in" "[" <number> "," <number> "]"
<side-expression>  ::= <original-expression> | <optimized-expression>
```

> Design decision (7): a range assumption may point at either `original.` or
> `optimized.`.

```wit
assumption {
    optimized.cfg[key].rate in [-1, 0x7fffffff];
}
```

```
=> OK
```

Contrast with section 3: a `binding`'s `=` is fixed (left `original`, right
`optimized`), but `range` is not. Mechanism — a precondition might be "some
input to the original program lies within a range", or it might be "some
narrowed quantity in the optimized program lies within a range"; both are
meaningful, so `<side-expression>`'s either/or is kept here.

Note that a range's `<side-expression>` prefix is also mandatory:

```wit
assumption {
    x in [0, 10];
}
```

```
error: expected 'original.' or 'optimized.', found identifier 'x'
```

---

## 8. `ignore flag of <helper>` is a fixed idiom, not a general mechanism

```bnf
<ignore-assumption> ::= "ignore" "flag" "of" <helper-name>
```

> Design decision (8): `ignore` is fixed as `ignore flag of <helper-name>`,
> not generalized into anything broader.

### 8.1 Legal

```wit
assumption {
    ignore flag of bpf_map_update_elem;
}
```

```
=> OK
```

Semantics: abstract away a helper's `flags` argument, so Heimdall models
that helper for every possible flag value.

### 8.2 A different word — invalid

```wit
assumption {
    ignore flags of bpf_map_update_elem;
}
```

```
error: expected keyword 'flag', found identifier 'flags'
  |
2 |     ignore flags of bpf_map_update_elem;
  |            ^^^^^
```

Mechanism: there is currently exactly one "ignore" need. Rather than
designing a general "ignore Y of X" grammar, it's fixed to one sentence for
now — generalize it if and when a second need actually shows up. **A DSL
should grow on demand, not pre-build a framework it doesn't need yet.**

---

## 9. Reserved words cannot be used as identifiers

> Lexical side condition L3: the following words are **not** valid
> `<identifier>`s:
> `assumption  binding  in  ignore  flag  of  original  optimized`
> so no variable, field, or helper name may spell exactly one of them. Note
> that `observation` is **not** on this list — it isn't a word in this
> language at all, so it's free to use as a name.

### 9.1 Using `flag` as a field name — invalid

```wit
binding {
    original.ctx.flag = optimized.ctx.flag;
}
```

```
error: expected a field name, found keyword 'flag'
  |
2 |     original.ctx.flag = optimized.ctx.flag;
  |                  ^^^^
```

### 9.2 Merely "starting with" a reserved word — legal

```wit
binding {
    original.informant = optimized.informant;
    original.flagship  = optimized.flagship;
}
```

```
=> OK
```

`in` and `flag` are reserved as whole words; `informant` / `flagship` just
happen to share a prefix — maximal munch treats them as complete
identifiers.

### 9.3 `return` isn't reserved, but it can't stand bare either

```wit
binding {
    return = optimized.return;
}
```

```
error: expected 'original.' or 'optimized.', found identifier 'return'
```

`return` is outside the L3 list, so it's a **legal identifier** — but at the
syntax level it's just an ordinary variable name. The error here is because
the left side of the statement is missing its `original.` prefix (see
section 3), not because of anything special about `return`.

**Before vs. now**: when `observation` existed, `original.return` /
`optimized.return` was specially recognized by `lower.py` as "the program's
return value". Now that `observation` is gone entirely, `original.return`
inside a `binding` is just an ordinary name — since it has no `[k]`
accessor, `lower.py` files it under "scalar binding, not applied", exactly
like any other scalar name.

**Teaching point**: distinguish "this word is reserved" from "this position
needs something else" — the two errors are fixed in completely different
ways.

### Known limitation

If a real BPF struct ever has a field literally named `flag` or `of`, these
keywords would need to become **context-sensitive** (only a keyword in
specific positions). The current implementation doesn't do that.

---

## 10. Comments are equivalent to whitespace

> Lexical side condition L2:
> line comments `// ...` run to end of line; block comments `/* ... */` run
> to the next `*/` (not nestable). An unterminated block comment is a
> lexical error.

### 10.1 Comments in various positions — legal

```wit
// line comment
binding {
    /* block */ original.x = optimized.x; // trailing
}
```

```
=> OK
```

Comments can be inserted between tokens anywhere, because the lexer treats
them as whitespace.

### 10.2 Unterminated block comment — invalid

```wit
binding {
    original.x = optimized.x;
} /* oops
```

```
error: unterminated block comment
  |
3 | } /* oops
  |   ^^
```

Block comments don't nest (`/* /* */` ends at the first `*/`), so the lexer
doesn't need to maintain a nesting counter — simple to implement, predictable
to reason about.

---

## 11. Optional "well-formedness" warnings

These are not syntax errors — the file is still legal — but they're usually
typos. Printed by default; `--no-extra` skips them, `--strict` turns them
into failures.

### 11.1 An empty range `[lo > hi]`

```wit
assumption {
    original.x in [10, 0];
}
```

```
warning: empty range [10, 0]: lower bound exceeds upper bound
=> OK (1 warning)          # FAILED with --strict
```

### 11.2 A duplicate `ignore flag of X`

```wit
assumption {
    ignore flag of h;
    ignore flag of h;
}
```

```
warning: duplicate 'ignore flag of h'
```

### 11.3 The exact same binding statement repeated

```wit
binding {
    original.x = optimized.x;
    original.x = optimized.x;
}
```

```
warning: duplicate binding statement 'original.x = optimized.x'
```

Mechanism: the syntax layer is a strict pass/fail; well-formedness warnings
are a separate, **toggleable** layer on top of it. Keeping the two apart
lets tooling dial the strictness up or down depending on context (a quick
experiment vs. a CI gate).

---

## 12. What the syntax layer does **not** do (left to `lower.py`)

| Question | Who's responsible |
|---|---|
| Does `original.m` name a real variable/map in the original program? | Semantic layer |
| Is `m[:]` applied to a map and `.f` to a struct? (`x[:][:]`, `scalar.f` parse fine at this layer) | Semantic layer's kind check |
| Does `bpf_map_update_elem` really take a `flags` argument? | Semantic layer |
| Lowering the `assumption`/`binding` blocks into a stronger-premise equivalence proof obligation | Semantic layer (`lower.py`) |

One-sentence summary of this whole document: **the BNF is responsible for
shape, the semantic layer is responsible for meaning, and the line between
them runs between "decidable without looking at the actual program" and
"only decidable by looking at the program". And this language deliberately
has no way to narrow what gets compared — a witness only ever adds
premises, never subtracts outputs.**
