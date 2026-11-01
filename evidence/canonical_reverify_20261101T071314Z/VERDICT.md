# Canonical re-verification 20261101T071314Z

Source commit befd3af35e70150b76458085208435eef9286bb3. Engines: mb_ref, olmstead_1998 (pinned sha256, built with gcc -O2).

Executed the committed .mal FILES, not the generator's in-memory opcodes.

| Link in the chain | Count of 379 |
|---|---|
| artifact_sha_matches_manifest | 379 |
| envelope_sha_matches_manifest | 379 |
| envelope_self_consistent | 379 |
| snapshot_matches_envelope | 379 |
| mb_ref_halt | 379 |
| olmstead_1998_halt | 379 |
| mb_ref_output_is_envelope | 379 |
| olmstead_1998_output_is_envelope | 379 |
| differential_engines_agree | 379 |

- LEVEL2_ARTIFACT_EXECUTES_CANONICALLY = DEMONSTRATED (379/379)
- LEVEL2_DIFFERENTIAL_ENGINE_AGREEMENT = DEMONSTRATED
- Snapshot / envelope / manifest byte-exactness = DEMONSTRATED
- Synthesis throughput is NOT measured by this tool; it still requires malbolge-generator.
