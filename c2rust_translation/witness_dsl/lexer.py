"""Tokenizer for the transformation-witness DSL.

`tokenize(source)` returns a list of `Token`, ending with a single `EOF`
token.  Raises `DslSyntaxError` on an illegal character, an unterminated
block comment, a malformed number, or a bad `[:]`.

See GRAMMAR.bnf, section "Lexical side conditions".
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import Diagnostic, DslSyntaxError, Pos

# Reserved words -- never identifiers (GRAMMAR.bnf L3).
KEYWORDS = frozenset(
    {
        "assumption",
        "binding",
        "observation",
        "in",
        "ignore",
        "flag",
        "of",
        "original",
        "optimized",
    }
)

# Punctuation token kinds.
_PUNCT = {
    "{": "LBRACE",
    "}": "RBRACE",
    "[": "LBRACK",  # only when not the "[:]" token
    "]": "RBRACK",
    ".": "DOT",
    ",": "COMMA",
    ";": "SEMI",
    "=": "EQ",
    "-": "MINUS",
}

# Kinds that also appear as keyword tokens use their upper-cased word as kind.


@dataclass
class Token:
    kind: str  # e.g. "IDENT", "INT", "LBRACE", "ASSUMPTION", "MAPALL", "EOF"
    text: str  # exact source slice
    pos: Pos
    value: int | None = None  # for INT tokens: the parsed integer

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"Token({self.kind!r}, {self.text!r}, {self.pos})"


def _is_ident_start(ch: str) -> bool:
    return ch.isascii() and ch.isalpha()


def _is_ident_part(ch: str) -> bool:
    return ch == "_" or (ch.isascii() and ch.isalnum())


class _Lexer:
    def __init__(self, source: str, filename: str):
        self.src = source
        self.filename = filename
        self.i = 0
        self.line = 1
        self.col = 1

    # -- low-level cursor -------------------------------------------------

    def _pos(self) -> Pos:
        return Pos(self.line, self.col, self.i)

    def _peek(self, ahead: int = 0) -> str:
        j = self.i + ahead
        return self.src[j] if j < len(self.src) else ""

    def _advance(self) -> str:
        ch = self.src[self.i]
        self.i += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def _die(self, message: str, pos: Pos, span: int = 1) -> "DslSyntaxError":
        return DslSyntaxError(
            Diagnostic("error", message, pos, self.filename, span)
        )

    # -- trivia --------------------------------------------------------------

    def _skip_trivia(self) -> None:
        while self.i < len(self.src):
            ch = self._peek()
            if ch in " \t\r\n":
                self._advance()
            elif ch == "/" and self._peek(1) == "/":
                while self.i < len(self.src) and self._peek() != "\n":
                    self._advance()
            elif ch == "/" and self._peek(1) == "*":
                start = self._pos()
                self._advance()
                self._advance()
                while True:
                    if self.i >= len(self.src):
                        raise self._die("unterminated block comment", start, 2)
                    if self._peek() == "*" and self._peek(1) == "/":
                        self._advance()
                        self._advance()
                        break
                    self._advance()
            else:
                return

    # -- token producers ---------------------------------------------------

    def _lex_ident(self) -> Token:
        start = self._pos()
        chars = [self._advance()]
        while self.i < len(self.src) and _is_ident_part(self._peek()):
            chars.append(self._advance())
        text = "".join(chars)
        kind = text.upper() if text in KEYWORDS else "IDENT"
        return Token(kind, text, start)

    def _lex_number(self) -> Token:
        start = self._pos()
        chars = [self._advance()]  # first digit (0-9)
        is_hex = False
        if chars[0] == "0" and self._peek() in ("x", "X"):
            is_hex = True
            chars.append(self._advance())  # 'x'
            if not _is_hex_digit(self._peek()):
                raise self._die(
                    "hexadecimal literal has no digits after '0x'", start, len(chars)
                )
            while self.i < len(self.src) and _is_hex_digit(self._peek()):
                chars.append(self._advance())
        else:
            while self.i < len(self.src) and self._peek().isascii() and self._peek().isdigit():
                chars.append(self._advance())
        text = "".join(chars)

        # A digit immediately followed by an identifier char is a malformed
        # token (e.g. "12abc", "0xGG"); report rather than silently splitting.
        if self.i < len(self.src) and _is_ident_part(self._peek()):
            bad = text
            while self.i < len(self.src) and _is_ident_part(self._peek()):
                bad += self._advance()
            raise self._die(f"malformed number literal {bad!r}", start, len(bad))

        if is_hex:
            value = int(text, 16)
        else:
            if len(text) > 1 and text[0] == "0":
                raise self._die(
                    "decimal literal may not have a leading zero", start, len(text)
                )
            value = int(text, 10)
        return Token("INT", text, start, value=value)

    def _lex_bracket(self) -> Token:
        # "[:]" is one token; a bare "[" is LBRACK.  No whitespace allowed
        # inside "[:]" (GRAMMAR.bnf L4).
        start = self._pos()
        self._advance()  # '['
        if self._peek() == ":":
            self._advance()  # ':'
            if self._peek() != "]":
                raise self._die("expected ']' to close '[:'", start, 2)
            self._advance()  # ']'
            return Token("MAPALL", "[:]", start)
        return Token("LBRACK", "[", start)

    # -- driver ----------------------------------------------------------

    def run(self) -> list[Token]:
        tokens: list[Token] = []
        while True:
            self._skip_trivia()
            if self.i >= len(self.src):
                tokens.append(Token("EOF", "", self._pos()))
                return tokens
            ch = self._peek()
            if _is_ident_start(ch):
                tokens.append(self._lex_ident())
            elif ch.isascii() and ch.isdigit():
                tokens.append(self._lex_number())
            elif ch == "[":
                tokens.append(self._lex_bracket())
            elif ch in _PUNCT:
                start = self._pos()
                self._advance()
                tokens.append(Token(_PUNCT[ch], ch, start))
            else:
                raise self._die(f"unexpected character {ch!r}", self._pos())


def _is_hex_digit(ch: str) -> bool:
    return len(ch) == 1 and ch.isascii() and (ch.isdigit() or ch.lower() in "abcdef")


def tokenize(source: str, filename: str = "<string>") -> list[Token]:
    return _Lexer(source, filename).run()
