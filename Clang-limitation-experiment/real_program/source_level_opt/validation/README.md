# Parser assessment

All builds use the manifest's existing Clang `-O2` flags and original include directories. These are fresh parser assessments; existing benchmark measurements were not edited. No timing trials were run. Discovery never receives the recipes or expected instruction counts.

- `conservative/`: flag-free compile-only assessment; no volatile caching or stack-address contract.
- `frozen_configuration/`: explicit frozen-configuration contract and one existing selected-entry equivalence check per comparison. That contract is needed only by the two bound-caching transformations; the report records that the option was supplied throughout the run.
- `stack_contract/`: explicit stack-address-unobserved contract for the DAE comparison, with one selected-entry equivalence check. This is an additional assumption, not a static alias proof.

| Comparison | Original slots | Recorded target | Conservative parser | With frozen configuration | Additional stack contract |
|---|---:|---:|---:|---:|---:|
| KEN execsnoop alignment | 44 | 43 | 43 | 43 | — |
| KEN sigsnoop alignment | 67 | 64 | 64 | 64 | — |
| DAE alignment | 2339 | 2279 | 2339 | 2339 | 2279 |
| biosnoop alignment | 551 | 545 | 545 | 545 | — |
| capable alignment | 175 | 171 | 171 | 171 | — |
| execsnoop alignment | 1807 | 1806 | 1806 | 1806 | — |
| mdflush alignment | 126 | 118 | 118 | 118 | — |
| tcprtt alignment | 490 | 486 | 486 | 486 | — |
| execsnoop bound | 1807 | 192 | 1807 | 192 | — |
| tcpconnect bound | 393 | 381 | 393 | 381 | — |

The conservative parser matches 7 of 10 recorded targets. Explicit frozen configuration enables 9 of 10. The additional explicit stack-address contract enables the remaining DAE result. DAE's conservative miss is retained: unrelated incoming-pointer casts and a null-pointer offset macro trigger the broad address-observation filter. The parser does not infer their independence from local aggregates.

Each `summary.json` records actual counts and proof outcomes. Each comparison folder retains its generated companion, discovery/selection report and, when requested, verifier log. The saved selected-entry proofs do not establish all-entry equivalence, kernel verifier acceptance, the external contracts or verification-time speedups. Structural AST filters are not a complete equivalence proof for arbitrary C.
