"""Recursive-descent parser for the transformation-witness DSL.

The grammar (GRAMMAR.bnf) has no left recursion and needs at most two tokens
of lookahead, so one function per non-terminal is enough.

`parse(source)` returns a `Program` or raises `DslSyntaxError` on the first
lexical or grammatical error.  Structural rules that the BNF productions
encode but a bare token stream does not -- block order, the `original.` /
`optimized.` side of each `=` operand, a non-empty `observation` block -- are
enforced here and reported as syntax errors.
"""

from __future__ import annotations

from . import ast_nodes as A
from .errors import Diagnostic, DslSyntaxError, Pos
from .lexer import Token, tokenize

# Human-readable names for token kinds, for "expected X" messages.
_FRIENDLY = {
    "LBRACE": "'{'",
    "RBRACE": "'}'",
    "LBRACK": "'['",
    "RBRACK": "']'",
    "MAPALL": "'[:]'",
    "DOT": "'.'",
    "COMMA": "','",
    "SEMI": "';'",
    "EQ": "'='",
    "MINUS": "'-'",
    "IDENT": "an identifier",
    "INT": "an integer literal",
    "EOF": "end of input",
}


def _friendly(kind: str) -> str:
    if kind in _FRIENDLY:
        return _FRIENDLY[kind]
    if kind.isupper() and kind.isalpha():
        return f"keyword '{kind.lower()}'"
    return kind


class _Parser:
    def __init__(self, tokens: list[Token], filename: str):
        self.toks = tokens
        self.filename = filename
        self.p = 0

    # -- token helpers -------------------------------------------------------

    @property
    def cur(self) -> Token:
        return self.toks[self.p]

    def _at(self, kind: str) -> bool:
        return self.cur.kind == kind

    def _die(self, message: str, tok: Token | None = None) -> DslSyntaxError:
        tok = tok or self.cur
        span = len(tok.text) if tok.text else 1
        return DslSyntaxError(
            Diagnostic("error", message, tok.pos, self.filename, span)
        )

    def _die_at(self, message: str, pos: Pos, span: int = 1) -> DslSyntaxError:
        return DslSyntaxError(
            Diagnostic("error", message, pos, self.filename, span)
        )

    def _advance(self) -> Token:
        tok = self.cur
        if tok.kind != "EOF":
            self.p += 1
        return tok

    def _expect(self, kind: str, what: str | None = None) -> Token:
        if not self._at(kind):
            want = what or _friendly(kind)
            raise self._die(f"expected {want}, found {self._describe(self.cur)}")
        return self._advance()

    @staticmethod
    def _describe(tok: Token) -> str:
        if tok.kind == "EOF":
            return "end of input"
        if tok.kind == "IDENT":
            return f"identifier {tok.text!r}"
        if tok.kind == "INT":
            return f"integer {tok.text!r}"
        if tok.kind.isupper() and tok.kind.isalpha() and tok.text.isalpha():
            return f"keyword '{tok.text}'"
        return repr(tok.text)

    # -- grammar: program -------------------------------------------------

    def parse_program(self) -> A.Program:
        assumption = None
        binding = None
        if self._at("ASSUMPTION"):
            assumption = self._parse_assumption_block()
        if self._at("BINDING"):
            binding = self._parse_binding_block()

        if not self._at("OBSERVATION"):
            # Targeted messages for the most likely mistakes.
            if self.cur.kind in ("ASSUMPTION", "BINDING"):
                raise self._die(
                    f"{self._describe(self.cur)} block is out of order or repeated; "
                    "blocks must appear as: assumption? binding? observation "
                    "(each at most once)"
                )
            raise self._die(
                f"expected the 'observation' block, found {self._describe(self.cur)}"
            )
        observation = self._parse_observation_block()

        if not self._at("EOF"):
            raise self._die(
                f"expected end of input after the observation block, "
                f"found {self._describe(self.cur)}"
            )
        return A.Program(observation=observation, assumption=assumption, binding=binding)

    # -- grammar: blocks -------------------------------------------------

    def _parse_assumption_block(self) -> A.AssumptionBlock:
        kw = self._expect("ASSUMPTION")
        self._expect("LBRACE")
        stmts: list = []
        while not self._at("RBRACE"):
            if self._at("EOF"):
                raise self._die("unclosed 'assumption' block: expected '}'")
            stmts.append(self._parse_assumption_statement())
        self._expect("RBRACE")
        return A.AssumptionBlock(statements=stmts, pos=kw.pos)

    def _parse_binding_block(self) -> A.BindingBlock:
        kw = self._expect("BINDING")
        self._expect("LBRACE")
        stmts: list = []
        while not self._at("RBRACE"):
            if self._at("EOF"):
                raise self._die("unclosed 'binding' block: expected '}'")
            stmts.append(self._parse_eq_statement("binding"))
        self._expect("RBRACE")
        return A.BindingBlock(statements=stmts, pos=kw.pos)

    def _parse_observation_block(self) -> A.ObservationBlock:
        kw = self._expect("OBSERVATION")
        self._expect("LBRACE")
        stmts: list = []
        while not self._at("RBRACE"):
            if self._at("EOF"):
                raise self._die("unclosed 'observation' block: expected '}'")
            stmts.append(self._parse_eq_statement("observation"))
        self._expect("RBRACE")
        if not stmts:
            raise self._die(
                "the 'observation' block must contain at least one statement",
                tok=kw,
            )
        return A.ObservationBlock(statements=stmts, pos=kw.pos)

    # -- grammar: statements ----------------------------------------------

    def _parse_assumption_statement(self):
        start = self.cur
        if self._at("IGNORE"):
            stmt = self._parse_ignore_assumption()
        else:
            stmt = self._parse_range_assumption()
        self._expect("SEMI")
        return stmt

    def _parse_ignore_assumption(self) -> A.IgnoreAssumption:
        kw = self._expect("IGNORE")
        self._expect("FLAG", "keyword 'flag'")
        self._expect("OF", "keyword 'of'")
        name = self._expect("IDENT", "a helper name")
        return A.IgnoreAssumption(helper=name.text, pos=kw.pos)

    def _parse_range_assumption(self) -> A.RangeAssumption:
        expr = self._parse_side_expression()
        self._expect("IN", "keyword 'in'")
        self._expect("LBRACK")
        lo = self._parse_number()
        self._expect("COMMA")
        hi = self._parse_number()
        self._expect("RBRACK")
        return A.RangeAssumption(expr=expr, lo=lo, hi=hi, pos=expr.pos)

    def _parse_eq_statement(self, block: str) -> A.EqStatement:
        lhs = self._parse_side_expression()
        if lhs.side != A.ORIGINAL:
            raise self._die_at(
                f"the left-hand side of a statement in the {block} block must be "
                f"an 'original.' expression, found '{lhs.side}.'",
                lhs.pos,
                len(lhs.side),
            )
        self._expect("EQ")
        rhs = self._parse_side_expression()
        if rhs.side != A.OPTIMIZED:
            raise self._die_at(
                f"the right-hand side of a statement in the {block} block must be "
                f"an 'optimized.' expression, found '{rhs.side}.'",
                rhs.pos,
                len(rhs.side),
            )
        self._expect("SEMI")
        return A.EqStatement(lhs=lhs, rhs=rhs, pos=lhs.pos)

    # -- grammar: expressions ------------------------------------------------

    def _parse_number(self) -> int:
        neg = False
        if self._at("MINUS"):
            self._advance()
            neg = True
        tok = self._expect("INT")
        return -tok.value if neg else tok.value

    def _parse_side_expression(self) -> A.Expr:
        if self._at("ORIGINAL"):
            side = A.ORIGINAL
        elif self._at("OPTIMIZED"):
            side = A.OPTIMIZED
        else:
            raise self._die(
                f"expected 'original.' or 'optimized.', found {self._describe(self.cur)}"
            )
        kw = self._advance()
        self._expect("DOT")
        root = self._expect("IDENT", "a variable name")
        accessors = self._parse_accessor_list()
        return A.Expr(side=side, root=root.text, accessors=accessors, pos=kw.pos)

    def _parse_accessor_list(self) -> list:
        out: list = []
        while True:
            if self._at("MAPALL"):
                out.append(A.MapAll(pos=self._advance().pos))
            elif self._at("LBRACK"):
                lb = self._advance()
                key = self._expect("IDENT", "a key variable")
                self._expect("RBRACK")
                out.append(A.Index(key=key.text, pos=lb.pos))
            elif self._at("DOT"):
                dot = self._advance()
                name = self._expect("IDENT", "a field name")
                out.append(A.Field(name=name.text, pos=dot.pos))
            else:
                return out


def parse(source: str, filename: str = "<string>") -> A.Program:
    """Tokenize and parse `source`; raise `DslSyntaxError` on the first error."""
    tokens = tokenize(source, filename)
    return _Parser(tokens, filename).parse_program()
