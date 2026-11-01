# Gate multi-engine — tier 1 (solo corpus, stdin vacío)

Paquete: `evidence/engine_canonical_gate_20261101T080313ZZ/`
UTC de ejecución: 2026-11-01T08:03:13Z (31,9 s de reloj para 379 artefactos)
Repo: Malbolguistic, base `f6f980383d90aeac482bd064c3e44ddf60265f25`

## Qué mide este paquete

Los 379 artefactos de nivel 2 commiteados se ejecutan bajo cuatro motores y se compara
el stdout byte a byte contra la envoltura `.malrt1` esperada:

| motor | rol | halt | envelope_exact |
|---|---|---|---|
| `vendor/oracles/mb_ref.c` (`a8ce19c2…`) | control | 379/379 | 379/379 |
| `vendor/oracles/olmstead_original.c` (`05abd38e…`) | control | 379/379 | 379/379 |
| `zig/bolg1` (BolgeForge, volcado BOLG1) | candidato | 379/379 | 379/379 |
| `malbolge.interpreter` (toolkit Python) | candidato | 379/379 | 379/379 |

Veredictos registrados en `summary.json`: `CANONICAL_AGREEMENT` para los dos candidatos
en este tier.

## Qué NO demuestra este paquete

**Nada de acuerdo semántico general.** Los 379 artefactos no leen stdin y ningún opcode
`/` se ejecuta, así que el tier 1 no ejercita ni el valor de `in` en EOF ni el
auto-wrap de `c`/`d` — que es exactamente donde los motores discrepan. La hipótesis
"coincidir en tier 1 ⇒ coincidir en general" se probó falsa en el paquete hermano
`../engine_canonical_gate_20261101T082034ZZ/`, que añade 4 controles con stdin real
(383 casos): ahí `zig_bolg1` queda **382/383** y `toolkit_python` **379/383**, es decir
`DIVERGENT`, mientras los dos oráculos siguen coincidiendo en los 383.

Por tanto el reclamo que sobrevive de este paquete es únicamente:

- LEVEL1_AGREEMENT_ALL_ENGINES = DEMONSTRATED (379/379, stdin vacío)
- SEMANTIC_CANONICITY = NO DEMOSTRADA POR ESTE TIER (ver `…T082034ZZ`)

## Limitación de procedencia (declarada, no ocultada)

Este paquete fue producido por una revisión anterior de `tools/engine_gate.py` anterior
a la división en tiers: su `summary.json` usa las claves `artifacts_under_test` y
`agree_both_oracles`, y la versión commiteada hoy usa `cases` y `agrees_with_oracles`.
El script exacto de esta corrida no quedó dentro del paquete, así que **el significado
del campo `agree_both_oracles` no es verificable contra el código del repo**; en
particular los renglones de control muestran `0`, y no puede afirmarse desde la
evidencia si eso fue "no aplicable a los oráculos" o un cálculo distinto. Los hechos
que importan están en `raw.jsonl` (`rc`, `stdout_bytes`, `envelope_exact` por motor),
que sí es interpretable sin el script. El paquete `…T082034ZZ` es el que sostiene las
conclusiones del plan.

## Cómo se selló esto

`SHA256SUMS.txt` de este directorio se generó al commitear, después de que el paquete
se quedara sin sumario (la corrida escribió `raw.jsonl` y `summary.json`; el informe y
el sumario se añadieron el mismo día). Los dos ficheros crudos no se modificaron.
