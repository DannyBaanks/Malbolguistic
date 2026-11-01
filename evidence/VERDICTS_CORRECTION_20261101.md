# Corrección a `VERDICTS.md` — 2026-11-01 (anexa, no reescrita)

`evidence/VERDICTS.md` es **salida generada** por `tools/build_malboguistic.py` (línea
595 de esa herramienta): editarla a mano se borra en el siguiente build. Por eso esta
nota es anexa y el fichero original queda tal cual lo produjo el build del 2026-09-04.

Reclamos nuevos medidos en esta sesión, con su paquete sellado:

| Reclamo | Veredicto | Evidencia |
|---|---|---|
| `LEVEL2_COMMITTED_FILE_EXECUTES_CANONICALLY` | DEMONSTRATED — 379/379 HALT + stdout == envoltura bajo `mb_ref.c` **y** `olmstead_original.c`, ejecutando el `.mal` del repo | `canonical_reverify_20261101T071314Z/` |
| `SNAPSHOT_INTEGRITY_FULL_INVENTORY` | DEMONSTRATED — 4.281/4.281 del inventario casan con disco (0 desajustes, 0 faltantes), 3 symlinks exentos | `canonical_reverify_20261101T071314Z/`, `snapshot_eol_repair_20261101/` |
| `CANONICAL_ENGINE_ZIG_AGREES_WITH_ORACLES` | DEMONSTRATED — `mbc.zig` 383/383 contra ambos oráculos; 421.317.177 pasos/s vs 412.592.903 del oráculo (ratio 1,02) | `zig_canonical_engine_gate_20261101T154528ZZ/` |
| `ENGINE_SEMANTIC_AGREEMENT_TIER2` | **REFUTADO** para `zig_bolg1` (382/383, trunca a ~64 KiB) y para el intérprete Python del toolkit (379/383) con stdin real; los oráculos sí coinciden en los 383 | `engine_canonical_gate_20261101T080313ZZ/`, `…T082034ZZ/` + su `CORRECTION_20261101T1555Z.md` |
| `LEVEL2_SEARCH_PORT_FIDELITY_SHARED_RNG` | DEMONSTRATED — 12/12 byte-idéntico a `generate_for_string` a `depth 5` y 30/30 a `depth 3` cuando ambos lados consumen el mismo flujo aleatorio | `zig_search_port_gate_20261101T204042ZZ/`, `…T204332ZZ/` |
| `PORT_REGENERATES_COMMITTED_MAL` | **NOT_DEMONSTRATED** — 0/379 byte-idénticos; la procedencia del corpus es heterogénea (`search_depth` `null` en 354 entradas, `3` en 25) y el sembrado MT19937 de `random.Random(42)` no se reproduce | `zig_search_port_gate_20261101T204229ZZ/` |
| `LEVEL2_CANONICITY_WHOLE_COMMITTED_SET` | DEMONSTRATED — los 379 programas generados por el port imprimen su envoltura bajo `mbc` (70,7M de evaluaciones, 63 s) | `zig_search_port_gate_20261101T204229ZZ/` |
| `CONTRACT_CAT_FED_FEASIBLE` | DEMONSTRATED como **factibilidad**, no adoptado: un solo `.mal` copiador con el archivo por stdin reproduce 4.258/4.258 exactos (31.647.823 bytes) bajo ambos oráculos | `corpus_cat_feasibility_20261101T074215Z/` |

## Dos renglones del `VERDICTS.md` generado que no dicen lo que parecen decir

Ambos se dejan en el fichero generado porque corregirlos es cambio de herramienta, no de
evidencia; quedan abiertos como trabajo explícito:

1. **`REPRODUCIBLE_BUILD = DEMONSTRATED`** sale de `verdict(True)` — está escrito literal,
   no medido. Lo que sí está medido: el nivel 1 (codec) es determinista, y **la síntesis
   nivel 2 con el generador Python no es byte-reproducible** (el mismo archivo, tres
   corridas, da tres programas distintos: `synthesis_linux_probe_20261101/
   determinism_same_file_x3.jsonl`). El port a Zig, en cambio, es determinista por
   construcción (misma configuración ⇒ misma huella, 3 objetivos × 5 repeticiones).
2. **`MASS_TRANSLATION_REAL_MALBOLGE`** se evalúa como `len(l2_pass) > 0`: basta **un**
   archivo para el renglón "mass". Su contenido real es "379 archivos ≤128 B, 0 fallos",
   que es lo que reporta la fila de nivel 2 de la tabla de métricas.

## Nota de costo que el build imprime como vigente

La línea generada dice `synthesis ~0.7 s per source byte on this host`. Ese número es de
la máquina Windows del 2026-09-04 ⇒ `[HISTORICAL]`. Medido en Linux (2026-11-01,
`depth 5`, un proceso por archivo): **~6 s fijos + ~0.16 s por byte** (5,7 s para 4 B y
21,2 s para 96 B), sin medir por encima de 128 B de fuente. Para el port: **63 s de pared
para los 379 objetivos** (envolturas de 72 a 244 caracteres).

`LINGUIST_EXECUTES_IN_MALBOLGE = NOT_CLAIMED` y
`GENERATED_CORPUS_IS_ORGANIC_USAGE = NO` siguen vigentes sin cambio.
