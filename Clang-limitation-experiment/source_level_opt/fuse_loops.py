"""Fuse same-index loops over restrict-qualified unsigned-int arrays."""
from ast_utils import Replacement, decl_id, for_parts, indexed_body, loop_node


def transform(source):
    replacements, skipped = [], []
    for function, body in source.functions():
        params = [n for n in function.get("inner", []) if n.get("kind") == "ParmVarDecl"]
        arrays = {n["id"] for n in params if source.type(n) == "unsigned int *restrict"}
        if not arrays:
            continue
        statements = body.get("inner", [])
        consumed = set()
        for index in range(len(statements) - 1):
            if index in consumed:
                continue
            first, second = statements[index:index + 2]
            left, right = loop_node(first), loop_node(second)
            if not left or not right:
                continue
            try:
                li, lb, lbody = for_parts(left)
                ri, rb, rbody = for_parts(right)
                if (li["name"] != ri["name"] or source.type(li) != "unsigned int"
                        or source.type(ri) != "unsigned int" or decl_id(lb) != decl_id(rb)
                        or not decl_id(lb) or source.decls[decl_id(lb)].get("kind") != "ParmVarDecl"
                        or source.type(lb) != "unsigned int"):
                    raise ValueError("iteration ranges must match a by-value unsigned bound")
                if not all(indexed_body(source, b, i["id"], arrays) for b, i in [(lbody, li), (rbody, ri)]):
                    raise ValueError("body is not pure same-index unsigned array updates")
                if lbody.get("kind") != "CompoundStmt" or rbody.get("kind") != "CompoundStmt":
                    raise ValueError("loop bodies must be braced")
                start, _ = source.bounds(lbody)
                header_start, _ = source.bounds(first)
                header = source.data[header_start:start].decode()
                # Both iterators have the same spelling, but separate AST identities.
                left_text = source.text(lbody)[1:-1].strip()
                right_text = source.text(rbody)[1:-1].strip()
                new = header + "{\n        " + left_text + "\n        " + right_text + "\n    }"
                begin, _ = source.bounds(first)
                _, end = source.bounds(second)
                replacements.append(Replacement(begin, end, new.encode()))
                consumed.add(index + 1)
            except (ValueError, KeyError) as error:
                skipped.append(f"{function['name']}: {error}")
    return replacements, skipped
