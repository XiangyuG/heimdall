# General source optimizer

`optimize_program.py` discovers candidates from Clang's JSON AST and generates a companion C source plus a JSON explanation. It never imports `real-programs.json` and has no program names, source hashes, stored offsets, or instruction-count targets. Offsets in reports come from the newly parsed source. The existing synthetic optimizer and experiment runners are unchanged.

```sh
python3 -B source_level_opt/optimize_program.py path/to/new.bpf.c \
  --output /tmp/new.opt.bpf.c --report /tmp/new.opt.json
```

Use `--include DIRECTORY` for additional quoted includes, `--clang PATH` to choose Clang, or `--flags-json FILE` for a JSON array of the original build flags. Parsing and every compilation use the same flags, including `-O2`. Default includes cover this repository's runtime and libbpf headers. Outputs must differ from the source and each other. `--passes local_alignment`, `--passes map_alignment`, and `--passes invariant_bound` select individual methods; the default tries all three in that order.

`--frozen-configuration` additionally enables caching of `const volatile` integer configuration. This flag asserts that the loader freezes configuration during each invocation and that volatile-read traces are excluded from observations. Without that contract, the volatile transformation is unavailable. Ordinary immutable globals and the existing narrow disjoint-local-call-site proof for pointer bounds do not require this option.

## Candidate discovery

Automatic alignment: inspect single-variable declaration statements inside function bodies, including bodies produced by BPF function macros. Consider automatic struct, union and array objects. Prefix their declarations with `__attribute__((aligned(8)))`. Reject pointers, static objects, multiple declarators, existing alignment attributes, included-file and macro declaration locations. This changes object alignment rather than record layout. To avoid observing changed stack addresses, conservatively disable the pass for translation units containing pointer-to-integer casts or alignment queries, and for calls to unknown external functions or callbacks. Source-defined functions, selected memory/CO-RE builtins and literal-ID BPF helper pointers are supported. This intentionally rejects some harmless programs.

Map alignment: associate a translation-unit BTF `.maps` variable with its defining record, read the `type` field's constant pointer-to-array extent, and whitelist Linux hash, array, per-CPU hash/array and LRU hash/per-CPU hash types (IDs 1, 2, 5, 6, 9 and 10). These map implementations provide 8-byte-aligned value bases. Identify the actual lookup helper through its declaration identity, header origin, static const function-pointer declaration and initializer cast of integer helper ID 1. Only direct calls whose first argument is exactly `&known_map` qualify. Wrap the call with `__builtin_assume_aligned(call, 8)`. Unsupported map types, shadowed functions, arithmetic on map references and header/macro call locations are skipped. This relies on Linux's allocation contract; parsing C alone cannot establish a custom runtime allocator's alignment.

Bound caching: for each `for` condition, resolve references to immutable scalar global integer declarations. Include volatile scalars only with the explicit frozen contract. Insert one correctly typed cached value immediately before the loop or its attached loop pragma; replace condition references. Also share the cached value with immediately preceding direct `if` guards that reference the same declaration. Retain later and body reads. The cached load executes in the loop's own compound scope. Separately, reuse the existing ordinary-pointer-bound proof: a static array helper with a restricted body, whose every call passes distinct automatic array and scalar objects. Unknown pointers and alias patterns fail that proof.

## Selection algorithm

Discovery applies structural filters and records explicit contracts. Compilation then selects useful candidates using a deterministic code-size objective, not runtime or verifier timing. Count all 8-byte slots in nonempty ELF sections marked `SHF_EXECINSTR`, including two-slot BPF instructions. For each pass, try each candidate and the whole set of independent candidates; accept the smallest result only if it strictly decreases the current total. Ties follow source discovery order. Reparse after every accepted generation. Stop that pass when nothing strictly improves. Every trial and accepted edit is recorded in the report, including compiler failures and unsuccessful size trials. This is a greedy search; it does not enumerate all subsets, revisit earlier passes or prove an optimal result.

```text
current = read(source)
score = executable_slots(compile(current, original_O2_flags))
for method in requested_methods:
    repeat:
        ast = parse(current, original_O2_flags)
        candidates = discover_with_preconditions(ast, method, explicit_contracts)
        proposals = each_candidate(candidates) + all_candidates_together(candidates)
        best = none
        for proposal in proposals:
            companion = apply_fresh_AST_edits(current, proposal)
            result = compile(companion, original_O2_flags)
            record(proposal, compiler_error_or_slot_count(result))
            if result.slots < score and result is better than best:
                best = result
        if best is none: break
        current, score = best.source, best.slots
        record_accepted(best)
write_companion_and_report(current)
```

The optimizer does not change benchmark inputs, verifier semantics, flags between variants, existing cases or measurement data. A smaller instruction count does not establish faster verification or Linux kernel acceptance. No timing trials are part of selection.

## Validation

The generic regression suite uses fresh names and miniature sources and checks discovery, multi-declarator rejection, address/alignment observations, unknown helper identity, supported/unsupported map types, frozen-configuration gating, shared zero guards and pragma placement:

```sh
python3 -B -m unittest discover -s source_level_opt -p test_optimize_program.py -v
```

Real-program validation is compile-only using the manifest's unchanged build flags and original include directories. Pass families follow each recorded comparison: alignment passes for the eight alignment rows, bound caching with the explicit frozen contract for the two conditional rows. This selects an optimization family, not a particular source location or expected result. All instruction targets are assessment data, never search inputs. No verification-time measurements are inferred from these counts.

The optional `--stack-addresses-unobserved` contract permits the local-alignment pass in translation units with pointer-to-integer casts. It asserts that automatic aggregate addresses and values derived from their physical addresses are not observable outputs. It does not prove which pointers are related to local buffers. The default retains the conservative cast rejection. Alignment queries still block the pass. Unknown external observers remain unsupported. Use this option only when the caller can establish the contract; it is independent of frozen configuration.

These AST checks are structural filters, not a complete C equivalence proof. For example, encoding pointer representations in emitted records can expose physical addresses without an explicit cast. New programs require independent equivalence validation and review of their address observations and runtime contracts.

Per-pass pseudocode:

```text
local_alignment(ast, stack_contract):
    reject translation unit if alignment-query AST nodes exist
    reject pointer-to-integer casts unless stack_contract is explicitly enabled
    reject unknown external calls and callbacks
    for each source function body, including BPF macro-generated bodies:
        for each single-variable declaration statement:
            if automatic aggregate, no existing alignment attribute,
               no pointer type, and fresh nonmacro main-source extent:
                propose inserting aligned(8) before declaration

map_alignment(ast):
    for each main-source BTF .maps variable and defining record:
        resolve numeric map type from type-field pointer-to-array extent
        retain only hash/array/per-CPU/LRU implementations with aligned value bases
    identify static const lookup-helper pointer initialized by cast(integer 1)
    for each direct main-source call to that exact helper declaration:
        if first argument is exactly address_of(retained_map):
            propose assume_aligned(call, 8)

cache_bound(ast, frozen_contract):
    include ordinary-pointer candidates from restricted disjoint-call-site proof
    for each for-loop condition:
        resolve references to scalar const integer globals
        exclude volatile globals unless frozen_contract is explicitly enabled
        for each qualifying global:
            find loop's own compound scope, preserving attached loop attributes
            include immediately preceding direct if-guards referencing same global
            insert a typed cached load before first included guard or loop pragma
            replace only those guards' and loop condition's references
```

The reusable assessment runner accepts the manifest as build context and comparison oracle; it does not pass recipes, case IDs, selected-entry names or expected counts into discovery:

```sh
# Flag-free conservative behavior, no timing or equivalence trials:
python3 -B source_level_opt/validate_program_optimizer.py --output /tmp/assessment
# Explicit frozen-configuration contract; one selected-entry proof per row:
python3 -B source_level_opt/validate_program_optimizer.py \
  --output /tmp/frozen-assessment --frozen-configuration --verify
# Explicit stack-address contract, assessed only on the DAE comparison:
python3 -B source_level_opt/validate_program_optimizer.py --case dae_alignment \
  --output /tmp/stack-assessment --stack-addresses-unobserved --verify
```

`--verify` requires the existing verifier's Python dependencies. It uses unchanged inputs and semantics, the recorded selected entry and existing timeout. It performs one equivalence check, with no warmups, repeated trials or timing charts. A passing proof covers that selected entry and verifier model; it cannot establish either external contract.
