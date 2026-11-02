#!/usr/bin/env python3
"""AST-discovered BPF source optimizations, selected by executable instruction slots.

No corpus recipes are used. Outputs are companions; the input is never overwritten.
"""
from __future__ import annotations
import argparse
import json
import re
import struct
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'support'))
from ast_utils import Source, Replacement, walk, unwrap, decl_id, find_clang, clang_flags, REPO

sys.dont_write_bytecode = True


@dataclass
class Candidate:
    kind: str
    reason: str
    edits: list[Replacement]


class Program(Source):
    def __init__(self, path, data, flags, clang):
        self.path = Path(path).resolve()
        self.data = data
        command = [clang, *flags, '-iquote', str(self.path.parent), '-x', 'c',
                   '-Xclang', '-ast-dump=json', '-fsyntax-only', '-']
        result = subprocess.run(command, input=data, capture_output=True)
        if result.returncode:
            raise ValueError(result.stderr.decode())
        self.ast = json.loads(result.stdout)
        self.decls = {n['id']: n for n in walk(self.ast) if n.get('kind') in
                      {'VarDecl', 'ParmVarDecl', 'FunctionDecl', 'TypedefDecl'}}
        self.typedefs = {n['name']: n['type']['qualType'] for n in walk(self.ast)
                         if n.get('kind') == 'TypedefDecl' and 'type' in n}

    def functions(self):
        # The function declaration itself can come from BPF_PROG; its body does not.
        for n in self.ast.get('inner', []):
            if n.get('kind') != 'FunctionDecl':
                continue
            body = next((c for c in n.get('inner', []) if c.get('kind') == 'CompoundStmt'), None)
            if body:
                try:
                    self.bounds(body)
                except (KeyError, ValueError):
                    continue
                yield n, body


def main_file(n):
    p = n.get('loc', {})
    return 'offset' in p and not any(k in p for k in ('includedFrom', 'spellingLoc', 'expansionLoc'))


def local_alignment(source, stack_addresses_unobserved=False):
    # alignof(object) and pointer-to-integer observation can observe changed stack layout.
    # Refuse the pass for such translation units rather than claiming C equivalence.
    nodes = list(walk(source.ast))
    if any(n.get('kind') == 'UnaryExprOrTypeTraitExpr' and n.get('name') in {'alignof', '__alignof'}
           for n in nodes):
        return []
    if not stack_addresses_unobserved and any(n.get('castKind') == 'PointerToIntegral' for n in nodes):
        return []
    # Source-defined callees are covered by the translation-unit observation
    # checks above. Unknown external functions/callbacks can inspect stack addresses.
    definitions = {n['id'] for n in nodes if n.get('kind') == 'FunctionDecl'
                   and any(c.get('kind') == 'CompoundStmt' for c in n.get('inner', []))}
    harmless_builtins = {'__builtin_memcpy', '__builtin_memset', '__builtin_memmove',
                         '__builtin_preserve_access_index', '__builtin_preserve_field_info',
                         '__builtin_btf_type_id', '__builtin_preserve_type_info',
                         '__builtin_preserve_enum_value', '__builtin_expect',
                         '__sync_fetch_and_add_4', '__sync_fetch_and_add_8',
                         '__builtin_bswap16', '__builtin_bswap32', '__builtin_bswap64'}
    for fn, body in source.functions():
        for n in walk(body):
            if n.get('kind') != 'CallExpr':
                continue
            callee = source.decls.get(decl_id(n['inner'][0]), {})
            if callee.get('id') in definitions or callee.get('name') in harmless_builtins:
                continue
            init = next(iter(callee.get('inner', [])), {})
            while init.get('kind') in {'ParenExpr', 'ImplicitCastExpr', 'CStyleCastExpr'} and len(init.get('inner', [])) == 1:
                init = init['inner'][0]
            if (callee.get('kind') != 'VarDecl' or callee.get('storageClass') != 'static'
                    or not re.search(r'\(\*\s*const\s*\)', source.type(callee))
                    or 'includedFrom' not in callee.get('loc', {})
                    or init.get('kind') != 'IntegerLiteral' or int(init.get('value', '0')) <= 0):
                return []
    candidates = []
    seen = set()
    for fn, body in source.functions():
        for stmt in walk(body):
            if stmt.get('kind') != 'DeclStmt':
                continue
            variables = [n for n in stmt.get('inner', []) if n.get('kind') == 'VarDecl']
            if len(variables) != 1:
                continue
            n = variables[0]
            typ = source.type(n)
            if (n.get('storageClass') in {'static', 'extern'} or '*' in typ
                    or not (typ.startswith(('struct ', 'union ')) or '[' in typ)
                    or any(c.get('kind') == 'AlignedAttr' for c in n.get('inner', []))):
                continue
            try:
                start, end = source.bounds(n)
                # A prefix attribute handles arrays, initializers, and named records alike.
                if start in seen or not main_file(n):
                    continue
                seen.add(start)
                candidates.append(Candidate('local_alignment',
                    f"{fn['name']}: strengthen automatic aggregate {n['name']} to 8-byte alignment",
                    [Replacement(start, start, b'__attribute__((aligned(8))) ')]))
            except (KeyError, ValueError):
                continue
    return candidates


def aligned_maps(source):
    maps = {}
    record = None
    # BTF map variables follow their defining RecordDecl at translation-unit scope.
    for n in source.ast.get('inner', []):
        if n.get('kind') == 'RecordDecl' and main_file(n):
            record = n
        elif n.get('kind') == 'VarDecl' and main_file(n) and record:
            try:
                if source.bounds(n)[0] != source.bounds(record)[0]:
                    continue
            except (KeyError, ValueError):
                continue
            if not any(c.get('kind') == 'SectionAttr' and c.get('section_name') == '.maps'
                       for c in n.get('inner', [])):
                continue
            fields = {c.get('name'): c for c in record.get('inner', []) if c.get('kind') == 'FieldDecl'}
            t = fields.get('type', {}).get('type', {}).get('qualType', '')
            match = re.fullmatch(r'int \(\*\)\[(\d+)\]', t)
            # Linux hash/array, per-CPU hash/array and LRU hash variants have
            # 8-byte-aligned value bases. Explicitly exclude all other map kinds.
            if match and int(match[1]) in {1, 2, 5, 6, 9, 10}:
                maps[n['id']] = n['name']
    helper_ids = set()
    for n in source.ast.get('inner', []):
        if (n.get('kind') == 'VarDecl' and n.get('name') == 'bpf_map_lookup_elem'
                and 'includedFrom' in n.get('loc', {}) and n.get('storageClass') == 'static'
                and re.search(r'\(\*\s*const\s*\)', source.type(n))):
            init = next((x for x in n.get('inner', []) if x.get('kind') not in {'UnusedAttr', 'UsedAttr'}), {})
            while init.get('kind') in {'ParenExpr', 'ImplicitCastExpr', 'CStyleCastExpr'} and len(init.get('inner', [])) == 1:
                init = init['inner'][0]
            if init.get('kind') == 'IntegerLiteral' and init.get('value') == '1':
                helper_ids.add(n['id'])
    edits = []
    for fn, body in source.functions():
        for n in walk(body):
            if n.get('kind') != 'CallExpr' or len(n.get('inner', [])) != 3:
                continue
            callee, arg, _ = n['inner']
            arg = unwrap(arg)
            if (decl_id(callee) not in helper_ids or arg.get('opcode') != '&'
                    or decl_id(arg['inner'][0]) not in maps):
                continue
            try:
                a, b = source.bounds(n)
                # Do not nest an existing assumption on repeated invocation.
                if source.data[max(0, a-40):a].rstrip().endswith(b'__builtin_assume_aligned('):
                    continue
                edits += [Replacement(a, a, b'__builtin_assume_aligned('), Replacement(b, b, b', 8)')]
            except (ValueError, KeyError):
                continue
    return [Candidate('map_alignment', 'Expose Linux hash/array map value-base alignment (8 bytes)', edits)] if edits else []


def cache_bounds(source, frozen):
    # Reuse the existing disjoint-call-site proof for ordinary pointer bounds.
    import cache_invariant_bound
    ordinary_edits, _ = cache_invariant_bound.transform(source)
    candidates = ([Candidate('invariant_bound', 'Static helper with proven disjoint local array and scalar call arguments', ordinary_edits)]
                  if ordinary_edits else [])
    globals_ = {n['id']: n for n in source.ast.get('inner', [])
                if n.get('kind') == 'VarDecl' and main_file(n)}
    for fn, body in source.functions():
        for loop in walk(body):
            if loop.get('kind') != 'ForStmt' or len(loop.get('inner', [])) != 5:
                continue
            cond = loop['inner'][2]
            ids = set()
            for n in walk(cond):
                ident = decl_id(n)
                if ident in globals_:
                    typ = source.type(globals_[ident])
                    if (re.fullmatch(r'(?:const volatile|volatile const|const) (?:unsigned )?(?:int|long|short|long long)', typ)
                            and ('volatile' not in typ or frozen)):
                        ids.add(ident)
            for ident in sorted(ids, key=lambda i: globals_[i]['name']):
                var = globals_[ident]
                name = var['name']
                if '_heimdall_cached_' + name in source.data.decode():
                    continue
                try:
                    loop_start, loop_end = source.bounds(loop)
                    # Limit caching to the condition plus earlier direct guards in the
                    # same compound scope; no speculative loads across nested branches.
                    anchor = next((n for n in walk(body) if n.get('kind') == 'AttributedStmt'
                                   and any(c is loop for c in n.get('inner', []))), loop)
                    parent = next((n for n in walk(body) if n.get('kind') == 'CompoundStmt'
                                   and any(c is anchor for c in n.get('inner', []))), None)
                    if parent is None:
                        continue
                    stmts = parent.get('inner', [])
                    index = next(i for i,c in enumerate(stmts) if c is anchor)
                    refs = [n for n in walk(cond) if n.get('kind') == 'DeclRefExpr' and decl_id(n) == ident]
                    start = source.bounds(anchor)[0]
                    for previous in reversed(stmts[:index]):
                        if previous.get('kind') != 'IfStmt':
                            break
                        prev_refs = [n for n in walk(previous) if n.get('kind') == 'DeclRefExpr' and decl_id(n) == ident]
                        if not prev_refs:
                            break
                        refs += prev_refs
                        start = source.bounds(previous)[0]
                    # Keep unroll directives attached to the original for statement.
                    line = source.data.rfind(b'\n', 0, start) + 1
                    prefix = source.data[:line]
                    pragma = re.search(rb'(?m)^[ \t]*#pragma[^\n]*\n[ \t]*$', prefix)
                    if pragma:
                        start = pragma.start()
                    cached = '_heimdall_cached_' + name
                    edits = [source.replacement(n, cached) for n in refs]
                    typ = source.type(var).replace('volatile ', '')
                    edits.append(Replacement(start, start, f'{typ} {cached} = {name};\n\t'.encode()))
                    candidates.append(Candidate('frozen_bound' if 'volatile' in source.type(var) else 'invariant_bound',
                        f"{fn['name']}: cache {name}; " + ('requires loader-frozen configuration and excludes volatile-read traces' if 'volatile' in source.type(var) else 'immutable const global scalar'), edits))
                except (KeyError, ValueError, StopIteration):
                    continue
    return candidates


def executable_sections(obj):
    """Read ELF64 little-endian SHF_EXECINSTR sections, counting 8-byte BPF slots."""
    data = Path(obj).read_bytes()
    if data[:6] != b'\x7fELF\x02\x01':
        raise ValueError('expected ELF64 little-endian object')
    offset = struct.unpack_from('<Q', data, 40)[0]
    size, count = struct.unpack_from('<HH', data, 58)
    sections = []
    for i in range(count):
        _, _, flags, _, at, length = struct.unpack_from('<IIQQQQ', data, offset + i*size)
        if flags & 4 and length:
            sections.append(data[at:at+length])
    return sections


def compile_code(data, path, flags, clang, output):
    cmd = [clang, *flags, '-iquote', str(Path(path).resolve().parent), '-x', 'c', '-c', '-o', str(output), '-']
    result = subprocess.run(cmd, input=data, capture_output=True)
    if result.returncode:
        raise ValueError(result.stderr.decode())
    code = executable_sections(output)
    return sum(len(s)//8 for s in code), code


def optimize(path, flags, clang, passes, frozen=False, stack_addresses_unobserved=False):
    data = Path(path).read_bytes()
    report = {'source': str(Path(path).resolve()), 'compiler': clang, 'objective': 'strictly decrease total executable BPF instruction slots; no timing trials',
              'flags': flags, 'frozen_configuration': frozen,
              'stack_addresses_unobserved': stack_addresses_unobserved, 'accepted': [], 'trials': []}
    with tempfile.TemporaryDirectory(prefix='heimdall-source-opt-') as tmp:
        obj = Path(tmp)/'trial.o'
        baseline, original_code = compile_code(data, path, flags, clang, obj)
        score = baseline
        for pass_name in passes:
            # Each accepted generation is reparsed; candidate offsets are never reused.
            while True:
                source = Program(path, data, flags, clang)
                candidates = {'local_alignment': lambda s: local_alignment(s, stack_addresses_unobserved),
                              'map_alignment': aligned_maps,
                              'invariant_bound': lambda s: cache_bounds(s, frozen)}[pass_name](source)
                if not candidates:
                    break
                proposals = candidates[:]
                if len(candidates) > 1:
                    proposals += [Candidate(pass_name, 'All independently discovered candidates in this pass',
                                             [e for c in candidates for e in c.edits])]
                best = None
                for c in proposals:
                    trial = {'pass': pass_name, 'reason': c.reason}
                    try:
                        updated = source.apply(c.edits)
                        count, _ = compile_code(updated, path, flags, clang, obj)
                        trial['slots'] = count
                        if count < score and (best is None or count < best[0]):
                            best = count, updated, c
                    except ValueError as error:
                        trial['error'] = str(error)
                    report['trials'].append(trial)
                if best is None:
                    break
                score, data, accepted = best
                report['accepted'].append({'pass': pass_name, 'reason': accepted.reason, 'slots': score,
                                           'edits': [{'start': e.start, 'end': e.end, 'text': e.text.decode()} for e in accepted.edits]})
        final_count, final_code = compile_code(data, path, flags, clang, obj)
        report.update(baseline_slots=baseline, optimized_slots=final_count,
                      executable_code_changed=final_code != original_code)
    return data, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--passes', nargs='+', choices=['local_alignment','map_alignment','invariant_bound'],
                        default=['local_alignment','map_alignment','invariant_bound'])
    parser.add_argument('--frozen-configuration', action='store_true',
                        help='Contract: configuration fixed during invocation; volatile read traces unobserved')
    parser.add_argument('--stack-addresses-unobserved', action='store_true',
                        help='Contract: automatic aggregate addresses and physical-address-derived values are unobserved')
    parser.add_argument('--clang', default=None)
    parser.add_argument('--flags-json', type=Path, help='JSON array of compile flags (must retain -O2)')
    parser.add_argument('--include', action='append', default=[], help='additional quoted-include directory')
    args = parser.parse_args()
    try:
        if args.output.resolve() == args.source.resolve() or args.report.resolve() in {args.source.resolve(), args.output.resolve()}:
            raise ValueError('source, companion, and report must be different files')
        flags = json.loads(args.flags_json.read_text()) if args.flags_json else [*clang_flags(), '-I', str(REPO / 'runtime-testing/include/bpf')]
        if '-O2' not in flags or any(f.startswith('-O') and f != '-O2' for f in flags):
            raise ValueError('the deterministic code-size search requires -O2')
        for directory in args.include:
            flags += ['-iquote', directory]
        data, report = optimize(args.source, flags, args.clang or find_clang(), args.passes, args.frozen_configuration, args.stack_addresses_unobserved)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(data)
        args.report.write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps({k: report[k] for k in ('baseline_slots', 'optimized_slots', 'executable_code_changed')}))
        return 0
    except (ValueError, OSError) as error:
        print(f'error: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
