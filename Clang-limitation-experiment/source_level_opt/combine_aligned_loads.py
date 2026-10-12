"""Replace two-byte assembly with a cast-based load from an actual u16 object.

The byte-pointer interface must explicitly promise that it points to a valid,
aligned unsigned-short object. Arbitrary aligned byte storage is not accepted.
"""
from ast_utils import decl_id, integer, unwrap, walk


def byte_at(source, node, pointer, offset):
    node = unwrap(node)
    if node.get("kind") == "CStyleCastExpr":
        if source.type(node) != "unsigned int":
            return False
        node = unwrap(node["inner"][0])
    if node.get("kind") != "ArraySubscriptExpr" or source.type(node) != "const unsigned char":
        return False
    base, index = node["inner"]
    return decl_id(base) == pointer and integer(index, offset)


def transform(source):
    replacements, skipped = [], []
    for function, body in source.functions():
        params = [n for n in function.get("inner", []) if n.get("kind") == "ParmVarDecl"]
        statements = body.get("inner", [])
        if len(params) != 1 or len(statements) != 1:
            continue
        returned = statements[0]
        if returned.get("kind") != "ReturnStmt":
            continue
        pointer = params[0]
        expr = unwrap(returned["inner"][0])
        if expr.get("opcode") != "|":
            continue
        try:
            if source.type(pointer) != "const unsigned char *":
                raise ValueError("requires an ordinary const byte-pointer interface")
            name = pointer["name"]
            contract = f"/* heimdall:aligned-u16-object {name} */"
            if contract not in source.text(body):
                raise ValueError("requires explicit documented aligned u16-object precondition")
            low, high = expr["inner"]
            high = unwrap(high)
            if (not byte_at(source, low, pointer["id"], 0) or high.get("opcode") != "<<"
                    or not byte_at(source, high["inner"][0], pointer["id"], 1)
                    or not integer(high["inner"][1], 8)):
                raise ValueError("requires p[0] | (p[1] << 8)")
            if any(n.get("kind") == "CStyleCastExpr" and source.type(n) != "unsigned int" for n in walk(expr)):
                raise ValueError("unsupported cast in byte assembly")
            # This experiment targets bpfel and the contract guarantees a typed object.
            word_type = "u16" if source.typedefs.get("u16") == "unsigned short" else "unsigned short"
            replacements.append(source.replacement(returned, f"return *(const {word_type} *){name}"))
        except (ValueError, KeyError) as error:
            skipped.append(f"{function['name']}: {error}")
    return replacements, skipped
