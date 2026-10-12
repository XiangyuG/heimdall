"""Clang AST and byte-offset rewriting helpers for the narrow experiment passes."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent


def find_clang() -> str:
    requested = os.environ.get("BPF_CLANG")
    candidates = [requested] if requested else [
        "/opt/homebrew/opt/llvm/bin/clang", "/usr/local/opt/llvm/bin/clang",
        *[f"clang-{v}" for v in range(22, 13, -1)], "clang",
    ]
    for candidate in candidates:
        resolved = shutil.which(candidate) if candidate else None
        if resolved:
            result = subprocess.run([resolved, "--print-targets"], capture_output=True, text=True)
            if result.returncode == 0 and re.search(r"^\s+bpf", result.stdout, re.M):
                return resolved
    raise ValueError("No BPF-capable Clang found; set BPF_CLANG")


def clang_flags() -> list[str]:
    # Parsing, original compilation, and transformed compilation use these flags.
    return ["-target", "bpfel", "-O2", "-g", "-D__TARGET_ARCH_x86",
            "-I", str(REPO / "runtime-testing/include"),
            "-I", str(REPO / "c2rust_translation/c_bpf_programs/libbpf-tools")]


def walk(node):
    yield node
    for child in node.get("inner", []):
        yield from walk(child)


def unwrap(node):
    while node.get("kind") in {"ParenExpr", "ImplicitCastExpr", "ConstantExpr"}:
        children = node.get("inner", [])
        if len(children) != 1:
            break
        node = children[0]
    return node


def decl_id(node):
    node = unwrap(node)
    return node.get("referencedDecl", {}).get("id") if node.get("kind") == "DeclRefExpr" else None


def integer(node, value):
    node = unwrap(node)
    return node.get("kind") == "IntegerLiteral" and int(node["value"]) == value


def loop_node(node):
    # Loop annotations need separate analysis; the experiment uses ordinary loops.
    return node if node.get("kind") == "ForStmt" else None


def for_parts(node):
    parts = node.get("inner", [])
    if len(parts) != 5 or parts[1]:
        raise ValueError("unsupported for-loop header")
    init, _, cond, inc, body = parts
    variables = init.get("inner", [])
    if init.get("kind") != "DeclStmt" or len(variables) != 1:
        raise ValueError("loop must declare one iterator")
    iterator = variables[0]
    if len(iterator.get("inner", [])) != 1 or not integer(iterator["inner"][0], 0):
        raise ValueError("iterator must start at zero")
    cond, inc = unwrap(cond), unwrap(inc)
    if (cond.get("opcode") != "<" or decl_id(cond["inner"][0]) != iterator["id"]
            or inc.get("opcode") != "++" or decl_id(inc["inner"][0]) != iterator["id"]):
        raise ValueError("loop must increment by one and compare iterator < bound")
    return iterator, unwrap(cond["inner"][1]), body


@dataclass(frozen=True)
class Replacement:
    start: int
    end: int
    text: bytes


class Source:
    def __init__(self, path: Path):
        self.path = path.resolve()
        self.data = self.path.read_bytes()
        command = [find_clang(), *clang_flags(), "-Xclang", "-ast-dump=json",
                   "-fsyntax-only", str(self.path)]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            raise ValueError(result.stderr)
        self.ast = json.loads(result.stdout)
        self.decls = {n["id"]: n for n in walk(self.ast) if "id" in n and n.get("kind") in
                      {"VarDecl", "ParmVarDecl", "FunctionDecl", "TypedefDecl"}}
        self.typedefs = {n["name"]: n["type"]["qualType"] for n in walk(self.ast)
                         if n.get("kind") == "TypedefDecl" and "type" in n}

    def bounds(self, node):
        extent = node["range"]
        positions = [extent["begin"], extent["end"]]
        for p in positions:
            if "offset" not in p or "expansionLoc" in p or "spellingLoc" in p or "includedFrom" in p:
                raise ValueError("macro or non-file source range")
            if "file" in p and Path(p["file"]).resolve() != self.path:
                raise ValueError("included-file source range")
        return positions[0]["offset"], positions[1]["offset"] + positions[1]["tokLen"]

    def text(self, node):
        start, end = self.bounds(node)
        return self.data[start:end].decode()

    def type(self, node):
        result = node.get("type", {}).get("desugaredQualType", node.get("type", {}).get("qualType", ""))
        for _ in range(10):
            expanded = re.sub(r"\b[A-Za-z_]\w*\b", lambda m: self.typedefs.get(m[0], m[0]), result)
            if expanded == result:
                break
            result = expanded
        return result

    def functions(self):
        for node in self.ast.get("inner", []):
            location = node.get("loc", {})
            if ("includedFrom" in location or "expansionLoc" in location or "spellingLoc" in location
                    or ("file" in location and Path(location["file"]).resolve() != self.path)):
                continue
            body = next((n for n in node.get("inner", []) if n.get("kind") == "CompoundStmt"), None)
            if node.get("kind") == "FunctionDecl" and body:
                yield node, body

    def replacement(self, node, text):
        return Replacement(*self.bounds(node), text.encode())

    def apply(self, replacements):
        data = self.data
        previous = len(data)
        for r in sorted(replacements, key=lambda r: r.start, reverse=True):
            if not (0 <= r.start <= r.end <= previous):
                raise ValueError("overlapping or invalid replacements")
            data = data[:r.start] + r.text + data[r.end:]
            previous = r.start
        return data


def pure_indexed_expression(source, node, iterator_id, arrays):
    """Accept integer arithmetic over constants and array[iterator], nothing else."""
    node = unwrap(node)
    if node.get("kind") == "IntegerLiteral":
        return True
    if node.get("kind") == "ArraySubscriptExpr":
        base, index = node["inner"]
        ident = decl_id(base)
        if ident not in arrays or decl_id(index) != iterator_id:
            return False
        return source.type(node) in {"unsigned int", "const unsigned int"}
    if node.get("kind") == "BinaryOperator" and node.get("opcode") in {"+", "-", "*", "&", "|", "^"}:
        return all(pure_indexed_expression(source, x, iterator_id, arrays) for x in node["inner"])
    return False


def indexed_body(source, body, iterator_id, arrays):
    statements = body.get("inner", []) if body.get("kind") == "CompoundStmt" else [body]
    if not statements:
        return False
    for statement in statements:
        statement = unwrap(statement)
        if statement.get("kind") not in {"BinaryOperator", "CompoundAssignOperator"} or statement.get("opcode") not in {"=", "+=", "-=", "|=", "&=", "^="}:
            return False
        left, right = statement["inner"]
        if unwrap(left).get("kind") != "ArraySubscriptExpr":
            return False
        if not pure_indexed_expression(source, left, iterator_id, arrays) or not pure_indexed_expression(source, right, iterator_id, arrays):
            return False
    return True
