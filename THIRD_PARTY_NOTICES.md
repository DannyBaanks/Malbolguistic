# THIRD-PARTY NOTICES

## github-linguist/linguist

- Snapshot pinned at commit `befd3af35e70150b76458085208435eef9286bb3`
  (see SOURCE_REPO.txt / SOURCE_COMMIT.txt).
- License: **MIT** — full text preserved at `vendor/source_snapshot/LICENSE`.
- The snapshot directory `vendor/source_snapshot/` is an unmodified copy
  (tarball SHA-256 `01EF2366FAA3481608C5B3E9E83E613C12A4A1724947D87EC12B081B1A9A7677`),
  except that 3 symlinks could not be materialized on Windows and are recorded
  in `manifest/source_inventory.json` instead.
- Files under `mirror/` and `malbolge/` are mechanical, byte-exactly
  reversible transformations of those MIT-licensed sources; the MIT license
  of linguist applies to them as derivative encodings.

## Malbolge-Translator (`vendor/malbolge_translator/`)

- Vendored verbatim from the Malbolge-Translator repo
  (commit `16ca88287615588027a1b5b78ec606def02ef4ad`, see
  `vendor/TRANSLATOR_SOURCE.txt`).
- License: **MIT** — `vendor/malbolge_translator/LICENSE`.

## malbolge-generator (runtime dependency, NOT vendored)

- Importable as the `malbolge` package; provides the level-2 program generator
  (`generate_for_string`). The canonical interpreter used for verification is
  no longer taken from this package — see `vendor/oracles/` below.
- License: **MIT**, upstream `wallstop/malbolge-toolkit`
  (`https://github.com/wallstop/malbolge-toolkit`); package metadata pins
  version `0.1.0` and `requires-python >= 3.11`.
- **Not on PyPI.** Measured 2026-11-01: `pip install malbolge-generator` fails;
  the earlier wording in this file was wrong. It is installed from a local copy
  of the toolkit source (`pip install <toolkit-dir>`), which is why a host
  without it reports `SYNTHESIS_UNAVAILABLE` and builds level 1 only.
- Not copied into this repo. Level 2 remains reproducible without it only in the
  verification direction: `tools/verify_corpus.py` and `tools/zig_canonical/`
  re-run the committed `.mal` files without the generator; synthesizing *new*
  targets still needs it.

## Oráculos Malbolge (`vendor/oracles/`)

Vendored so that `tools/verify_corpus.py` does not depend on a host path or on a
sibling repo being present. Full provenance, CLI, exit codes and semantics:
`vendor/oracles/PROVENANCE.txt`.

### `vendor/oracles/mb_ref.c`

- SHA-256 `a8ce19c2dc93e36f8c9c24a271c4187d68f922b9455262c7199a009763fe3ad3`.
- Origin: sibling repo **BolgeForge**, `oracle/mb_ref.c` at commit `1dc5cb5`
  (repo HEAD `7b4fbacf2d7d58cdfadd83a48af17128c2c776f6`). The same byte appears
  at `Malbolge-PureEpoch/vendor/mb_ref.c` (verified), so those two are **not**
  independent evidence of each other.
- License: **MIT** (Copyright (c) 2026 ISyCo Contributors), per the BolgeForge
  `LICENSE`; the text itself lives in that repo, not in this one.

### `vendor/oracles/olmstead_original.c`

- SHA-256 `05abd38e78b266050c5a5e8cc5b36584daa5bbdeb404bfb351de7ea6fa26b510`.
- Origin: sibling repo **Malbolge-PureEpoch**, `vendor/olmstead_original.c` at
  commit `48ddc15` (repo HEAD `d09a42f8efac1287e6a0aa8bb70f62214a82f97d`).
- Authorship: **Ben Olmstead, 1998**, the original implementer of Malbolge; the
  file header places it in the public domain
  ("I hereby place it in the public domain. Have fun...").
- A different implementation lineage from `mb_ref.c` (separate loader and input
  handling), which is what makes agreement between the two meaningful.

## `tools/zig_canonical/` (this repo, no third-party code)

`mbc.zig` and `mbsearch.zig` are original to MALBOGUISTIC, written against the
published Classic semantics (59,049 cells, `in` EOF = 3^10 − 1, crazy
recurrence) with Zig 0.16's standard library only. No vendored Zig dependency.
They are not derived from `mb_ref.c`; the oracles above remain the independent
witnesses used to gate them.

## Nota sobre el snapshot (2026-11-01)

El punto "unmodified copy" de arriba se escribió antes de la reparación
registrada en `evidence/snapshot_eol_repair_20261101/`: 199 archivos de texto
tenían CRLF convertido a LF en el blob y 3 archivos binarios estaban
normalizados o ausentes. Esos 202 archivos se restauraron a los bytes
autoritativos (envoltura `.malrt1` para TEXT, `manifest/source_inventory.json`
+ upstream en `befd3af` para BINARY), y `tools/verify_corpus.py` comprueba ahora
el inventario completo en cada corrida. La tarball SHA-256 citada arriba no se
re-medió después de esa restauración; no se afirma aquí que siga vigente.
