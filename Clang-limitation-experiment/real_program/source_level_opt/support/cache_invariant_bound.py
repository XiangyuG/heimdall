"""Cache an ordinary loop-bound load after proving disjoint local call arguments.

Only static helpers whose bound is not modified and whose every use is a direct
call with distinct local array/scalar objects are accepted. Generic pointers,
function-pointer escapes, volatile loads, and unsupported bodies are skipped.
"""
from ast_utils import Replacement, decl_id, for_parts, indexed_body, loop_node, unwrap, walk


def local_calls_are_disjoint(source, function, write_index, bound_index):
    refs = [n for n in walk(source.ast) if n.get("kind") == "DeclRefExpr"
            and decl_id(n) == function["id"]]
    accepted_refs = set()
    calls = 0
    for caller, body in source.functions():
        locals_ = {n["id"] for n in walk(body) if n.get("kind") == "VarDecl"
                   and n.get("storageClass") not in {"static", "extern"}}
        for node in walk(body):
            if node.get("kind") != "CallExpr" or decl_id(node["inner"][0]) != function["id"]:
                continue
            args = node["inner"][1:]
            if len(args) != 3:
                return False
            array_id = decl_id(args[write_index])
            address = unwrap(args[bound_index])
            if address.get("kind") != "UnaryOperator" or address.get("opcode") != "&":
                return False
            scalar_id = decl_id(address["inner"][0])
            if array_id not in locals_ or scalar_id not in locals_ or array_id == scalar_id:
                return False
            array, scalar = source.decls[array_id], source.decls[scalar_id]
            if not source.type(array).startswith("unsigned int[") or source.type(scalar) != "int":
                return False
            calls += 1
            accepted_refs.update(n["id"] for n in walk(node["inner"][0]) if n.get("kind") == "DeclRefExpr")
    return calls > 0 and len(refs) == len(accepted_refs)


def transform(source):
    replacements, skipped = [], []
    for function, body in source.functions():
        params = [n for n in function.get("inner", []) if n.get("kind") == "ParmVarDecl"]
        statements = body.get("inner", [])
        if len(params) != 3 or len(statements) != 1:
            continue
        loop = loop_node(statements[0])
        if not loop:
            continue
        try:
            iterator, bound, loop_body = for_parts(loop)
            if bound.get("kind") != "UnaryOperator" or bound.get("opcode") != "*":
                continue
            if function.get("previousDecl"):
                raise ValueError("helper redeclarations need additional call-site analysis")
            if (function.get("storageClass") != "static" or source.type(params[0]) != "unsigned int *"
                    or source.type(params[1]) != "const unsigned int *"
                    or source.type(params[2]) != "const int *"
                    or source.type(iterator) != "int" or decl_id(bound["inner"][0]) != params[2]["id"]):
                raise ValueError("requires static unsigned-array helper and ordinary const int bound")
            arrays = {params[0]["id"], params[1]["id"]}
            if not indexed_body(source, loop_body, iterator["id"], arrays):
                raise ValueError("unsupported loop body")
            # The shared expression checker also permits stores to b; reject them.
            for node in walk(loop_body):
                if node.get("opcode") in {"=", "+=", "-=", "|=", "&=", "^="}:
                    left = unwrap(node["inner"][0])
                    if decl_id(left["inner"][0]) != params[0]["id"]:
                        raise ValueError("only the first array may be written")
            if not local_calls_are_disjoint(source, function, 0, 2):
                raise ValueError("cannot prove all calls use a distinct local array and bound")
            if "_heimdall_bound" in source.text(body):
                raise ValueError("generated identifier already exists")
            start, _ = source.bounds(body)
            replacements.append(Replacement(start + 1, start + 1,
                f"\n    const int _heimdall_bound = *{params[2]['name']};".encode()))
            replacements.append(source.replacement(bound, "_heimdall_bound"))
        except (ValueError, KeyError) as error:
            skipped.append(f"{function['name']}: {error}")
    return replacements, skipped
