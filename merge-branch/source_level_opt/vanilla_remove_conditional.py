#!/usr/bin/env python3
"""Conservatively replace simple C ``if`` updates with conditional values.

The accepted source forms are intentionally narrow::

    if (condition) x = expression;
    if (condition) x += expression;
    if (condition) x -= expression;
    if (condition) x |= expression;

The condition and right-hand side must be side-effect-free Clang AST
expressions, and ``x`` must be an unaliased local scalar.  Adjacent accepted
updates to the same variable are emitted as a typed SSA-style value chain.
Everything else is copied without modification.

This tool uses Clang's typed JSON AST for analysis and source offsets for
rewriting.  Consequently, comments, includes, macros, and formatting outside
the replaced ``if`` statements are preserved.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator


SCRIPT_DIR = Path(__file__).resolve().parent
MERGE_BRANCH_DIR = SCRIPT_DIR.parent
REPO_DIR = MERGE_BRANCH_DIR.parent
CASES_DIR = MERGE_BRANCH_DIR / "cases"
GENERATED_DIR = SCRIPT_DIR / "generated"
RUNTIME_INCLUDE_DIR = REPO_DIR / "runtime-testing" / "include"
LIBBPF_TOOLS_DIR = REPO_DIR / "c2rust_translation" / "c_bpf_programs" / "libbpf-tools"

SUPPORTED_ASSIGNMENTS = {"=", "+=", "-=", "|="}
SUPPORTED_BINARY_OPERATORS = {
    "+", "-", "*", "/", "%",
    "<<", ">>",
    "&", "|", "^",
    "<", "<=", ">", ">=", "==", "!=",
    "&&", "||",
}
SUPPORTED_UNARY_OPERATORS = {"+", "-", "!", "~"}
TRANSPARENT_EXPRESSION_NODES = {
    "ParenExpr",
    "ImplicitCastExpr",
    "CStyleCastExpr",
    "ConstantExpr",
}
LEAF_EXPRESSION_NODES = {
    "IntegerLiteral",
    "FloatingLiteral",
    "CharacterLiteral",
    "StringLiteral",
    "GNUNullExpr",
}
QUALIFIERS = re.compile(r"\b(?:const|volatile|restrict)\b\s*")
IDENTIFIER = re.compile(rb"[A-Za-z_][A-Za-z0-9_]*")


class TransformError(RuntimeError):
    """Raised when the input cannot be analyzed without risking corruption."""


@dataclass(frozen=True)
class Token:
    text: str
    start: int
    end: int


@dataclass
class Candidate:
    node: dict[str, Any]
    condition: dict[str, Any]
    rhs: dict[str, Any]
    target_id: str
    target_name: str
    target_type: str
    opcode: str
    start: int
    end: int


@dataclass(frozen=True)
class Replacement:
    start: int
    end: int
    text: bytes


@dataclass
class TransformReport:
    transformed: int = 0
    skipped: Counter[str] | None = None
    volatile_targets: set[str] | None = None

    def __post_init__(self) -> None:
        if self.skipped is None:
            self.skipped = Counter()
        if self.volatile_targets is None:
            self.volatile_targets = set()


def find_clang() -> str:
    candidates = (
        os.environ.get("BPF_CLANG"),
        "/opt/homebrew/opt/llvm/bin/clang",
        "/usr/local/opt/llvm/bin/clang",
        shutil.which("clang"),
    )
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    raise TransformError("no Clang executable found; set BPF_CLANG")


def lex_source(source: bytes) -> list[Token]:
    """Return significant C tokens while ignoring comments and directives."""

    tokens: list[Token] = []
    index = 0
    line_start = True
    size = len(source)

    while index < size:
        byte = source[index]

        if byte in b" \t\r":
            index += 1
            continue
        if byte == ord("\n"):
            line_start = True
            index += 1
            continue

        if line_start and byte == ord("#"):
            index += 1
            while index < size:
                if source[index] == ord("\n"):
                    backslashes = 0
                    cursor = index - 1
                    while cursor >= 0 and source[cursor] == ord("\\"):
                        backslashes += 1
                        cursor -= 1
                    index += 1
                    if backslashes % 2 == 0:
                        break
                else:
                    index += 1
            line_start = True
            continue

        line_start = False

        if source.startswith(b"//", index):
            newline = source.find(b"\n", index + 2)
            index = size if newline < 0 else newline
            continue
        if source.startswith(b"/*", index):
            close = source.find(b"*/", index + 2)
            if close < 0:
                raise TransformError("unterminated block comment")
            line_start = source.rfind(b"\n", index, close + 2) >= 0
            index = close + 2
            continue
        if byte in (ord('"'), ord("'")):
            quote = byte
            start = index
            index += 1
            while index < size:
                if source[index] == ord("\\"):
                    index += 2
                    continue
                if source[index] == quote:
                    index += 1
                    break
                index += 1
            else:
                raise TransformError("unterminated string or character literal")
            tokens.append(Token("literal", start, index))
            continue

        match = IDENTIFIER.match(source, index)
        if match:
            tokens.append(Token(match.group().decode("ascii"), index, match.end()))
            index = match.end()
            continue

        tokens.append(Token(chr(byte), index, index + 1))
        index += 1

    return tokens


def discover_function_names(source: bytes) -> list[str]:
    """Discover top-level function definitions without expanding headers."""

    tokens = lex_source(source)
    names: list[str] = []
    brace_depth = 0

    for index, token in enumerate(tokens):
        if token.text == "{":
            if brace_depth == 0 and index > 0 and tokens[index - 1].text == ")":
                close_index = index - 1
                depth = 1
                open_index = close_index - 1
                while open_index >= 0:
                    if tokens[open_index].text == ")":
                        depth += 1
                    elif tokens[open_index].text == "(":
                        depth -= 1
                        if depth == 0:
                            break
                    open_index -= 1

                if open_index > 0:
                    introducer = tokens[open_index - 1].text
                    if introducer.startswith("BPF_"):
                        for argument in tokens[open_index + 1:close_index]:
                            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", argument.text):
                                names.append(argument.text)
                                break
                    elif re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", introducer):
                        names.append(introducer)
            brace_depth += 1
        elif token.text == "}":
            brace_depth -= 1
            if brace_depth < 0:
                raise TransformError("unbalanced closing brace")

    if brace_depth != 0:
        raise TransformError("unbalanced braces")
    return list(dict.fromkeys(names))


def clang_base_command(clang: str, source_path: Path) -> list[str]:
    return [
        clang,
        "-target", "bpf",
        "-D__TARGET_ARCH_x86",
        "-Wno-unknown-attributes",
        "-I", str(source_path.parent),
        "-I", str(RUNTIME_INCLUDE_DIR),
        "-I", str(LIBBPF_TOOLS_DIR),
        "-fsyntax-only",
    ]


def check_source_with_clang(clang: str, source_path: Path) -> None:
    command = [*clang_base_command(clang, source_path), str(source_path)]
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        diagnostics = completed.stderr.strip() or completed.stdout.strip()
        raise TransformError(f"Clang could not parse {source_path}:\n{diagnostics}")


def decode_json_stream(data: str) -> Iterator[dict[str, Any]]:
    decoder = json.JSONDecoder()
    index = 0
    while index < len(data):
        while index < len(data) and data[index].isspace():
            index += 1
        if index >= len(data):
            return
        value, index = decoder.raw_decode(data, index)
        if isinstance(value, dict):
            yield value


def load_function_asts(clang: str, source_path: Path,
                       function_names: Iterable[str]) -> list[dict[str, Any]]:
    functions: list[dict[str, Any]] = []
    seen_ranges: set[tuple[int, int]] = set()

    for function_name in function_names:
        command = [
            *clang_base_command(clang, source_path),
            "-Xclang", "-ast-dump=json",
            "-Xclang", "-ast-dump-filter",
            "-Xclang", function_name,
            str(source_path),
        ]
        completed = subprocess.run(command, capture_output=True, text=True)
        if completed.returncode != 0:
            diagnostics = completed.stderr.strip() or completed.stdout.strip()
            raise TransformError(
                f"Clang AST generation failed for {function_name}:\n{diagnostics}"
            )

        for root in decode_json_stream(completed.stdout):
            for node in walk(root):
                if node.get("kind") != "FunctionDecl":
                    continue
                if node.get("name") != function_name:
                    continue
                if not any(child.get("kind") == "CompoundStmt"
                           for child in node.get("inner", [])):
                    continue
                span = node_span(node)
                if span is None or span in seen_ranges:
                    continue
                seen_ranges.add(span)
                functions.append(node)

    return functions


def walk(node: dict[str, Any]) -> Iterator[dict[str, Any]]:
    yield node
    for child in node.get("inner", []):
        if isinstance(child, dict):
            yield from walk(child)


def point_offset(point: dict[str, Any]) -> int | None:
    if "offset" in point:
        return int(point["offset"])
    for key in ("expansionLoc", "spellingLoc"):
        nested = point.get(key)
        if isinstance(nested, dict) and "offset" in nested:
            return int(nested["offset"])
    return None


def point_token_length(point: dict[str, Any]) -> int | None:
    if "tokLen" in point:
        return int(point["tokLen"])
    for key in ("expansionLoc", "spellingLoc"):
        nested = point.get(key)
        if isinstance(nested, dict) and "tokLen" in nested:
            return int(nested["tokLen"])
    return None


def node_span(node: dict[str, Any]) -> tuple[int, int] | None:
    node_range = node.get("range")
    if not isinstance(node_range, dict):
        return None
    begin = node_range.get("begin", {})
    end = node_range.get("end", {})
    start = point_offset(begin)
    finish = point_offset(end)
    token_length = point_token_length(end)
    if start is None or finish is None or token_length is None:
        return None
    return start, finish + token_length


def direct_node_span(node: dict[str, Any]) -> tuple[int, int] | None:
    """Return a range only when both endpoints are written in this source file."""

    node_range = node.get("range")
    if not isinstance(node_range, dict):
        return None
    begin = node_range.get("begin", {})
    end = node_range.get("end", {})
    if "offset" not in begin or "offset" not in end or "tokLen" not in end:
        return None
    return int(begin["offset"]), int(end["offset"]) + int(end["tokLen"])


def unwrap_parens(node: dict[str, Any]) -> dict[str, Any]:
    while node.get("kind") == "ParenExpr" and len(node.get("inner", [])) == 1:
        node = node["inner"][0]
    return node


def referenced_type(node: dict[str, Any]) -> str:
    referenced = node.get("referencedDecl", {})
    type_info = referenced.get("type", {})
    return str(type_info.get("desugaredQualType", type_info.get("qualType", "")))


def is_safe_expression(node: dict[str, Any], target_id: str) -> bool:
    kind = node.get("kind")

    if kind in LEAF_EXPRESSION_NODES:
        return True
    if kind == "DeclRefExpr":
        referenced = node.get("referencedDecl", {})
        referenced_id = referenced.get("id")
        referenced_kind = referenced.get("kind")
        if referenced_kind in {"EnumConstantDecl", "NonTypeTemplateParmDecl"}:
            return True
        if referenced_kind not in {"VarDecl", "ParmVarDecl"}:
            return False
        decl_type = referenced_type(node)
        if referenced_id != target_id and (
            "volatile" in decl_type or "_Atomic" in decl_type
        ):
            return False
        return True
    if kind in TRANSPARENT_EXPRESSION_NODES:
        children = node.get("inner", [])
        return bool(children) and all(is_safe_expression(child, target_id)
                                      for child in children)
    if kind == "UnaryOperator":
        if node.get("opcode") not in SUPPORTED_UNARY_OPERATORS:
            return False
        return all(is_safe_expression(child, target_id)
                   for child in node.get("inner", []))
    if kind == "BinaryOperator":
        if node.get("opcode") not in SUPPORTED_BINARY_OPERATORS:
            return False
        return all(is_safe_expression(child, target_id)
                   for child in node.get("inner", []))
    if kind == "ConditionalOperator":
        children = node.get("inner", [])
        return len(children) == 3 and all(
            is_safe_expression(child, target_id) for child in children
        )
    return False


def scalar_type_without_qualifiers(type_name: str) -> str | None:
    if not type_name or "_Atomic" in type_name:
        return None
    if any(marker in type_name for marker in ("*", "[", "struct ", "union ", "(")):
        return None
    result = QUALIFIERS.sub("", type_name).strip()
    return result or None


def target_is_address_taken(function: dict[str, Any], target_id: str) -> bool:
    for node in walk(function):
        if node.get("kind") != "UnaryOperator" or node.get("opcode") != "&":
            continue
        for descendant in walk(node):
            if descendant.get("kind") != "DeclRefExpr":
                continue
            if descendant.get("referencedDecl", {}).get("id") == target_id:
                return True
    return False


def extend_if_end(source: bytes, if_node: dict[str, Any], end: int) -> int | None:
    children = if_node.get("inner", [])
    if len(children) != 2:
        return None
    body = children[1]
    if body.get("kind") == "CompoundStmt":
        return end

    index = end
    while index < len(source):
        if source[index] in b" \t\r\n":
            index += 1
            continue
        if source.startswith(b"//", index):
            newline = source.find(b"\n", index + 2)
            index = len(source) if newline < 0 else newline + 1
            continue
        if source.startswith(b"/*", index):
            close = source.find(b"*/", index + 2)
            if close < 0:
                return None
            index = close + 2
            continue
        return index + 1 if source[index] == ord(";") else None
    return None


def analyze_if(source: bytes, function: dict[str, Any],
               local_declarations: dict[str, dict[str, Any]],
               if_node: dict[str, Any]) -> tuple[Candidate | None, str | None]:
    children = if_node.get("inner", [])
    if len(children) != 2:
        return None, "has else, initializer, or non-canonical condition"

    condition, body = children
    if body.get("kind") == "CompoundStmt":
        body_children = body.get("inner", [])
        if len(body_children) != 1:
            return None, "body does not contain exactly one statement"
        assignment = body_children[0]
    else:
        assignment = body

    kind = assignment.get("kind")
    opcode = assignment.get("opcode")
    if kind not in {"BinaryOperator", "CompoundAssignOperator"}:
        return None, "body is not a supported assignment"
    if opcode not in SUPPORTED_ASSIGNMENTS:
        return None, f"assignment operator {opcode!r} is unsupported"

    operands = assignment.get("inner", [])
    if len(operands) != 2:
        return None, "assignment does not have two operands"
    lhs = unwrap_parens(operands[0])
    rhs = operands[1]
    if lhs.get("kind") != "DeclRefExpr":
        return None, "left-hand side is not a plain variable"

    referenced = lhs.get("referencedDecl", {})
    target_id = referenced.get("id")
    target_name = referenced.get("name")
    if not target_id or not target_name or target_id not in local_declarations:
        return None, "target is not a local variable"

    target_decl = local_declarations[target_id]
    if not target_decl.get("inner"):
        return None, "target is not initialized at its declaration"
    type_info = target_decl.get("type", {})
    original_type = str(type_info.get("qualType", ""))
    target_type = scalar_type_without_qualifiers(original_type)
    if target_type is None:
        return None, "target is not a supported scalar type"
    if target_is_address_taken(function, target_id):
        return None, "target address is taken"
    if not is_safe_expression(condition, target_id):
        return None, "condition is not side-effect-free scalar arithmetic"
    if not is_safe_expression(rhs, target_id):
        return None, "right-hand side is not side-effect-free scalar arithmetic"

    if_span = direct_node_span(if_node)
    condition_span = direct_node_span(condition)
    rhs_span = direct_node_span(rhs)
    if if_span is None or condition_span is None or rhs_span is None:
        return None, "source range comes from a macro expansion"
    start, end = if_span
    end = extend_if_end(source, if_node, end)
    if end is None or not (0 <= start < end <= len(source)):
        return None, "could not determine the complete source range"

    return Candidate(
        node=if_node,
        condition=condition,
        rhs=rhs,
        target_id=target_id,
        target_name=target_name,
        target_type=target_type,
        opcode=opcode,
        start=start,
        end=end,
    ), None


def declaration_map(function: dict[str, Any]) -> dict[str, dict[str, Any]]:
    declarations: dict[str, dict[str, Any]] = {}
    body_seen = False
    for node in walk(function):
        if node.get("kind") == "CompoundStmt":
            body_seen = True
        elif body_seen and node.get("kind") == "VarDecl" and node.get("id"):
            declarations[node["id"]] = node
    return declarations


def render_expression(source: bytes, node: dict[str, Any],
                      target_id: str, replacement_name: str) -> bytes:
    span = direct_node_span(node)
    if span is None:
        raise TransformError("expression has no editable source range")
    start, end = span
    expression = source[start:end]
    edits: list[tuple[int, int]] = []

    for descendant in walk(node):
        if descendant.get("kind") != "DeclRefExpr":
            continue
        if descendant.get("referencedDecl", {}).get("id") != target_id:
            continue
        ref_span = direct_node_span(descendant)
        if ref_span is None:
            raise TransformError("target reference comes from a macro expansion")
        ref_start, ref_end = ref_span
        if not (start <= ref_start < ref_end <= end):
            raise TransformError("target reference lies outside its expression")
        edits.append((ref_start - start, ref_end - start))

    rendered = bytearray(expression)
    encoded_name = replacement_name.encode("ascii")
    for edit_start, edit_end in sorted(edits, reverse=True):
        rendered[edit_start:edit_end] = encoded_name
    return bytes(rendered)


def source_indentation(source: bytes, offset: int) -> bytes:
    line_start = source.rfind(b"\n", 0, offset) + 1
    prefix = source[line_start:offset]
    return prefix if not prefix.strip() else b""


def fresh_identifier(prefix: str, used: set[str]) -> str:
    candidate = prefix
    suffix = 0
    while candidate in used:
        suffix += 1
        candidate = f"{prefix}_{suffix}"
    used.add(candidate)
    return candidate


def emit_candidate_run(source: bytes, run: list[Candidate], run_number: int,
                       used_identifiers: set[str]) -> list[Replacement]:
    target = run[0].target_name
    target_type = run[0].target_type
    safe_target = re.sub(r"[^A-Za-z0-9_]", "_", target)
    stem = f"__vanilla_{safe_target}_{run_number}"
    previous = fresh_identifier(f"{stem}_value_0", used_identifiers)
    replacements: list[Replacement] = []

    for index, candidate in enumerate(run, start=1):
        indent = source_indentation(source, candidate.start)
        condition_name = fresh_identifier(f"{stem}_condition_{index}", used_identifiers)
        next_value = fresh_identifier(f"{stem}_value_{index}", used_identifiers)
        condition = render_expression(
            source, candidate.condition, candidate.target_id, previous
        )
        rhs = render_expression(source, candidate.rhs, candidate.target_id, previous)

        if candidate.opcode == "=":
            selected = b"(" + rhs + b")"
        else:
            operator = candidate.opcode[:-1].encode("ascii")
            selected = b"(" + previous.encode("ascii") + b") " + operator + b" (" + rhs + b")"

        # The original indentation precedes candidate.start and is therefore
        # retained by the source-range edit.  Add indentation only after the
        # first generated line.
        lines: list[bytes] = []
        if index == 1:
            lines.append(
                target_type.encode("utf-8") + b" " + previous.encode("ascii")
                + b" = " + target.encode("ascii") + b";"
            )
        lines.append(
            b"int " + condition_name.encode("ascii") + b" = !!(" + condition + b");"
        )
        lines.append(
            target_type.encode("utf-8") + b" " + next_value.encode("ascii")
            + b" = " + condition_name.encode("ascii") + b" ? (" + selected + b") : "
            + previous.encode("ascii") + b";"
        )
        if index == len(run):
            lines.append(
                target.encode("ascii") + b" = " + next_value.encode("ascii") + b";"
            )

        replacements.append(
            Replacement(candidate.start, candidate.end, (b"\n" + indent).join(lines))
        )
        previous = next_value

    return replacements


def collect_compound_groups(function: dict[str, Any], candidates: dict[str, Candidate]) -> list[list[Candidate]]:
    groups: list[list[Candidate]] = []

    def visit(node: dict[str, Any]) -> None:
        if node.get("kind") == "CompoundStmt":
            current: list[Candidate] = []
            for child in node.get("inner", []):
                candidate = candidates.get(child.get("id", ""))
                if candidate is not None:
                    if current and current[-1].target_id != candidate.target_id:
                        groups.append(current)
                        current = []
                    current.append(candidate)
                else:
                    if current:
                        groups.append(current)
                        current = []
                visit(child)
            if current:
                groups.append(current)
            return
        for child in node.get("inner", []):
            visit(child)

    visit(function)
    return groups


def apply_replacements(source: bytes, replacements: list[Replacement]) -> bytes:
    ordered = sorted(replacements, key=lambda replacement: replacement.start)
    for earlier, later in zip(ordered, ordered[1:]):
        if earlier.end > later.start:
            raise TransformError("internal error: overlapping source replacements")

    result = bytearray(source)
    for replacement in reversed(ordered):
        result[replacement.start:replacement.end] = replacement.text
    return bytes(result)


def transform_source(source_path: Path) -> tuple[bytes, TransformReport]:
    source = source_path.read_bytes()
    function_names = discover_function_names(source)
    if not function_names:
        raise TransformError(f"no function definitions found in {source_path}")

    clang = find_clang()
    check_source_with_clang(clang, source_path)
    functions = load_function_asts(clang, source_path, function_names)
    if not functions:
        raise TransformError("Clang did not return an editable function AST")

    report = TransformReport()
    replacements: list[Replacement] = []
    used_identifiers = {
        match.group().decode("ascii") for match in IDENTIFIER.finditer(source)
    }
    run_number = 0

    for function in functions:
        declarations = declaration_map(function)
        candidates: dict[str, Candidate] = {}

        for node in walk(function):
            if node.get("kind") != "IfStmt":
                continue
            candidate, reason = analyze_if(source, function, declarations, node)
            if candidate is None:
                report.skipped[reason or "unsupported"] += 1
                continue
            candidates[node.get("id", "")] = candidate

            target_decl = declarations[candidate.target_id]
            target_qual_type = str(target_decl.get("type", {}).get("qualType", ""))
            if "volatile" in target_qual_type:
                report.volatile_targets.add(candidate.target_name)

        for run in collect_compound_groups(function, candidates):
            run_number += 1
            replacements.extend(
                emit_candidate_run(source, run, run_number, used_identifiers)
            )
            report.transformed += len(run)

    return apply_replacements(source, replacements), report


def output_path_for(source_path: Path) -> Path:
    name = source_path.name
    if name.endswith(".bpf.c"):
        base = name[:-len(".bpf.c")]
    elif name.endswith(".c"):
        base = name[:-len(".c")]
    else:
        base = name
    return GENERATED_DIR / f"{base}_MERGED.bpf.c"


def write_generated(output_path: Path, contents: bytes) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb", dir=output_path.parent, prefix=f".{output_path.name}.", delete=False
    ) as temporary:
        temporary.write(contents)
        temporary_path = Path(temporary.name)
    try:
        temporary_path.chmod(0o644)
        os.replace(temporary_path, output_path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def resolve_input(argument: str) -> Path:
    requested = Path(argument).expanduser()
    candidates = [requested]
    if not requested.is_absolute():
        candidates.append(CASES_DIR / requested)
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise TransformError(f"input file not found: {argument}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Replace provably simple if-updates with typed conditional-value chains "
            "and write the result under source_level_opt/generated."
        )
    )
    parser.add_argument("program", help="C/eBPF source file to transform")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        source_path = resolve_input(args.program)
        output_path = output_path_for(source_path).resolve()
        if output_path == source_path:
            raise TransformError("refusing to overwrite the input source")
        transformed, report = transform_source(source_path)
        write_generated(output_path, transformed)
    except TransformError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(f"input:       {source_path}")
    print(f"output:      {output_path}")
    print(f"transformed: {report.transformed} if statement(s)")
    print(f"skipped:     {sum(report.skipped.values())} if statement(s)")
    for reason, count in sorted(report.skipped.items()):
        print(f"  {count}: {reason}")
    if report.volatile_targets:
        names = ", ".join(sorted(report.volatile_targets))
        print(
            "warning: transformed local volatile target(s): " + names + ". "
            "This preserves computed values for the eBPF output model, but not the "
            "ISO C volatile-access trace.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
