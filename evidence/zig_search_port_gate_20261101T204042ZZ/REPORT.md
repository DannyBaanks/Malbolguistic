# Port a Zig del beam search nivel 2: idéntico a la referencia bajo flujo RNG compartido, y canónico en el corpus

Paquete: `evidence/zig_search_port_gate_20261101T204042ZZ/`
Gate: 2026-11-01T20:40:42Z · Repo Malbolguistic, HEAD `f6f980383d90aeac482bd064c3e44ddf60265f25`
Estado del código: `tools/zig_canonical/mbsearch.zig` y `tools/mbsearch_gate.py` **sin commitear** en el momento del gate.
Hermanos de este paquete: `…T204229ZZ` (corpus completo, 379 objetivos) y `…T204332ZZ` (diferencial con `--depth 3`, 30 objetivos).

## Pregunta

El nivel 2 del build (`tools/build_malboguistic.py`) sintetizaba programas con el motor
de búsqueda del toolkit Python (`malbolge.generator.ProgramGenerator.generate_for_string`),
a ~40 µs por evaluación. La pregunta del port no era "¿funciona en Zig?" sino
"¿es **el mismo sistema** en Zig?".

- **H1** — el port emite, para un mismo sobre, un programa que la semántica canónica
  acepta: impreso por `mbc`, devuelve exactamente los bytes del sobre.
- **H2** — el port reproduce el **texto** del programa de la referencia, no sólo un
  programa válido.
- **H3** — con semilla y configuración fijas, el port es determinista (una sola
  huella por objetivo y repeticiones).

H1 y H3 quedan **demostradas**. H2 queda demostrada **condicionalmente**: hace falta
fijar el generador aleatorio de ambos lados a un mismo flujo, porque la búsqueda de la
referencia alcanza su RNG en todo objetivo real (no existe configuración libre de RNG).

## Qué se porta y cuál es la única desviación

El port es `tools/zig_canonical/mbsearch.zig`: misma frontera (`i` + 99 `o`), mismos
candidatos (`op*`), mismo orden de expansión, misma decisión de aceptación/poda, mismo
cierre con `v`. Corre sobre la **máquina canónica** residente de `mbc.zig` (59.049
celdas, `c`/`d` con envoltura módulo 59.048, `in` en EOF = 59.048) y no sobre el motor
del toolkit (sin envoltura, memoria que crece).

La desviación deliberada es una sola: la referencia detiene un candidato cuando `c`
supera `len(tape) + len(suffix)`; aquí eso se emula con un umbral
`cp_peak + suffix.len` sobre la cinta canónica. Si la emulación divergiera (lecturas
más allá del programa propio), el contador `peak_gaps` lo contaría. Medido: 0 sobre
70,7M de evaluaciones del paquete hermano. El resto de las divergencias visibles
(`stalls`, `budget_exhausted`, `slash_executed`, `delta_overflows`) se cuentan igual:
todas en 0.

Se descartó el caché de estados de la referencia: midiendo 101.404 evaluaciones daba
`cache_hits = 0`, así que es neutral para el resultado. Y no se reprodujo el sembrado
MT19937 de CPython: `random.Random(42)` no corresponde ni a `init_by_array([42])` ni a
`init_genrand(42)` (mt[1] real `0xd473a4c0` frente a `0x15c4db9f`); el port usa
SplitMix64 documentado. Por eso el testeo de equivalencia **no** compara semillas
distintas: compara las dos búsquedas alimentadas con el mismo SplitMix64.

## Procedencia

```
zig version                                       # 0.16.0
python3 tools/mbsearch_gate.py --mode all --limit 12 --depth 5 --repeats 5 \
        --differential-limit 12 --site-packages <site-packages del toolkit>
```

| objeto | sha256 |
|---|---|
| fuente `tools/zig_canonical/mbsearch.zig` | `d7124002344b2f103c5df6bc1c43836249e3109543b1ca57402178edd721f398` |
| fuente `tools/zig_canonical/mbc.zig` | `1fead7d75f4905780db9bedfbdae614aa049e9d46dfa3fc2333f91409cca11f9` |
| binario `mbsearch` (no se commitea) | `d1914895e9e1c39699c3ee9865e7e42ead84c2bb53826844235c2ebe85400c9e` |
| binario `mbc` (no se commitea) | `7e4479a8f47d6fef52bb1a071db2986a480601d0a98825c8c27298ead2c4aef8` |
| driver `mbsearch_gate.py` (copia en este paquete) | `68e80ef8453893518f3bc9b8a9b41ce6b902cd82284acfc28e505feefa9a428d` |
| `manifest/translation_manifest.json` | `64b4a2a966947b50281b71a71ac016be0467e0d411aeb595c498a830c2372901` |

La copia del driver en este paquete se reconstruyó después del gate (el árbol tenía ya
la versión siguiente, que sólo cambia el significado de `--limit 0`) y se verificó por
hash: el sha256 reconstruido es idéntico al fijado en `summary.json`.

## Resultados (12 objetivos más pequeños, `--depth 5`, `choices=op*`, `seed=42`)

| tier | qué exige | resultado |
|---|---|---|
| corpus | `mbc` imprime el sobre byte a byte | 12/12 |
| corpus | verificación canónica dentro del port | 12/12 |
| corpus | contadores de divergencia (`peak_gaps`, `stalls`, `budget`, `/`, `delta_overflows`) | 0 en todos |
| corpus | evaluaciones totales | 1.268.583 |
| determinism | 3 objetivos × 5 repeticiones, huella única | 3/3 |
| differential | programa byte a byte igual que `generate_for_string` | **12/12** |
| differential | `evaluations` igual | **12/12** |
| differential | nº de `rng.choice` igual | **12/12** (p. ej. 234 = 234) |
| differential | tiempo Python / tiempo port | 44,33 s / 0,568 s → **78×** |

Ejemplos de la tabla `raw.jsonl`: `ext/linguist/linguist.h` (72 B de sobre → 1.855
caracteres, `port_sha256` = `ref_sha256`), `samples/D/function.d` (92 B → 2.307,
116.155 evaluaciones en ambos lados).

## Lo que este gate **no** demuestra

- **No reproduce los artefactos commiteados**: 0 de 12 programas coinciden con el
  `.mal` del corpus. Y tampoco la toolkit actual: el sondeo previo generó 3 objetivos y
  `mbc` los aceptó los 3 pero ninguno coincidió byte a byte. La causa es de
  procedencia, no del port: `search_depth` es `null` en 354 entradas del manifest y `3`
  en 25, y el sembrado MT19937 no es recreable. **NOT_DEMONSTRATED**: igualdad textual
  con los artefactos de `malbolge/`.
- Los umbrales de presupuesto por candidato (`--budget 65536`) no se agotaron nunca; no
  se ha probado el comportamiento del port por encima de los 244 B de sobre del corpus.
- Las razones de término `stall`/`budget` del port están instrumentadas pero no ejercidas
  por contenido real del corpus (0 casos).

## Criterio de aceptación usado

Puertas duras: (1) el programa emitido imprime el sobre exactamente bajo `mbc`;
(2) determinismo propio (N corridas, una huella). Puerta diferencial: igualdad textual
con la referencia compartiendo flujo RNG. Superposición con el corpus: medida, no puerta.
