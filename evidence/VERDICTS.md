# VERDICTS

Build at 2026-11-02T01:27:49Z UTC, source commit befd3af35e70150b76458085208435eef9286bb3.

| Claim | Verdict |
|---|---|
| TRANSLATOR_ROUNDTRIP | DEMONSTRATED |
| LINGUIST_SNAPSHOT_PINNED | DEMONSTRATED |
| TEXT_BINARY_CLASSIFICATION | DEMONSTRATED |
| TREE_PRESERVED | DEMONSTRATED |
| CODEC_MASS_MIRROR | DEMONSTRATED |
| MASS_TRANSLATION_REAL_MALBOLGE | DEMONSTRATED |
| BYTE_EXACT_ROUNDTRIP_LEVEL1 | DEMONSTRATED |
| BYTE_EXACT_ROUNDTRIP_LEVEL2 | DEMONSTRATED |
| ZERO_MISMATCH_LEVEL1 | DEMONSTRATED |
| ZERO_FAILED_EXECUTION_LEVEL2 | DEMONSTRATED |
| REPRODUCIBLE_BUILD_LEVEL1_BYTE_EXACT | DEMONSTRATED |
| REPRODUCIBLE_BUILD_LEVEL2_SYNTHESIS | NOT_CLAIMED: re-synthesizing a source yields a different program every run (evidence/synthesis_linux_probe_20261101/); the Zig port is deterministic but is a second lineage, not identical to the corpus (zig_search_port_gate_20261101T204229ZZ/) |
| REPRODUCIBLE_BUILD_COMMITTED_CORPUS_UNCHANGED | DEMONSTRATED: this run wrote manifest/translation_manifest.json byte-identical to the one it started from (sha256 54c4b70421eddaf13d0739c354651c5d1f64f6f2a40bdcb67466bad4b4c550d7) |
| CONTRACT_LEVEL2_SELF_CONTAINED | DEMONSTRATED: 1605 artifacts each hold their own file. 1605 carried over from the committed corpus (checked by sha256 on disk, not re-synthesized); 0 synthesized by this run. Canonical execution of the committed .mal FILES is tools/verify_corpus.py. |
| CONTRACT_LEVEL3_CANONICAL_CAT | DEMONSTRATED over 4258/4258 catalog TEXT files (31647823 bytes) under mb_ref, olmstead — sealed at level3_cat_sweep_20261101T223138Z |
| LICENSE_AUDIT | DEMONSTRATED |
| LINGUIST_EXECUTES_IN_MALBOLGE | NOT_CLAIMED |
| GENERATED_CORPUS_IS_ORGANIC_USAGE | NO |

Notes:
- Level 1 (codec mirror) covers ALL 4258 text files, byte-exact.
- Level 2 (real, executed Malbolge) PASS=1605 FAILED=0 SKIPPED_BUDGET=0 SKIPPED_TOO_LARGE=2653 (cap 128 B, eligible=379, budget 3600.0 s).
- MASS_TRANSLATION_REAL_MALBOLGE counts over the ELIGIBLE set: it is DEMONSTRATED only when every file <= the cap PASSes, so SKIPPED_BUDGET fails the row instead of hiding in it.
- Committed level-2 artifacts are carried over, never re-synthesized (adopted=1605). `--no-adopt` replaces sealed bytes with a fresh, non-reproducible synthesis. `evidence/level2_state.json` is gitignored, so `--resume` is host-local while adoption from the manifest works anywhere.
- Level 3 backs the corpus with ONE program plus the file on stdin (evidence/level3_cat_sweep_20261101T223138Z). It does not embed the file in the program, so it is a different contract from level 2, not a bigger level 2.
- Synthesis cost is NOT measured by this run. The historical '~0.7 s per source byte' was one Windows host [HISTORICAL]; the Linux measurement is ~6 s fixed + ~0.16 s per byte at depth 5, see evidence/synthesis_linux_probe_20261101/.
- Verification method matters for level 2: this build replays the generator's in-memory opcodes for what it synthesizes here and checks only sha256 for what it adopts. Executing the committed .mal FILES under the pinned canonical oracles is tools/verify_corpus.py. When quoting a 1605/1605, quote the pack that produced it.
- A `.malrt1` envelope is NOT a Malbolge program.
- LINGUIST_EXECUTES_IN_MALBOLGE is NOT_CLAIMED and WILL stay that way.
- This corpus is GENERATED, not organic Malbolge usage.
