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

## Resolución de los dos renglones (append 2026-11-01, misma sesión)

`tools/build_malboguistic.py` ya no emite `REPRODUCIBLE_BUILD` a secas ni
`MASS_TRANSLATION_REAL_MALBOLGE` con `len(l2_pass) > 0`. Los renglones ahora son:

| clave | cómo se evalúa |
|---|---|
| `REPRODUCIBLE_BUILD_LEVEL1_BYTE_EXACT` | `LEVEL1_CODEC_MISMATCH == 0 and LEVEL1_CODEC_MIRRORED == FILES_TEXT`, medida en cada corrida |
| `REPRODUCIBLE_BUILD_LEVEL2_BYTE_EXACT` | literal `NOT_CLAIMED`, apuntando a `evidence/synthesis_linux_probe_20261101/` |
| `MASS_TRANSLATION_REAL_MALBOLGE` | `len(candidates) > 0 and len(l2_pass) == len(candidates) and len(l2_fail) == 0` sobre el **conjunto elegible**: si un archivo elegible se va por presupuesto, el renglón cae |

Aviso de cadena de evidencia: el `evidence/VERDICTS.md` commiteado es la tabla **generada el
2026-09-04** y sigue diciendo `REPRODUCIBLE_BUILD = DEMONSTRATED`. No se regeneró a mano
(es salida del build); queda corregida por este anexo, y el renglón viejo debe leerse como
`[HISTORICAL]`.

Además el nivel 1 dejó de ser una afirmación de prose: `tools/level1_determinism.py` mide
doble codificación + igualdad byte a byte contra la envoltura commiteada sobre las
**4.258/4.258** fuentes TEXT, en 0,44 s (`level1_determinism_20261101T214729ZZ/`, exit 0).
Ese es el respaldo empírico de `REPRODUCIBLE_BUILD_LEVEL1_BYTE_EXACT`; el nivel 2 sigue sin
respaldo de reproducibilidad, y así lo dice la clave.

`LINGUIST_EXECUTES_IN_MALBOLGE = NOT_CLAIMED` y
`GENERATED_CORPUS_IS_ORGANIC_USAGE = NO` siguen vigentes sin cambio.

## Tercer append (2026-11-01, misma sesión): la tabla generada ya es vigente y hay 3 claves nuevas

El apartado anterior se escribió contra la tabla **generada el 2026-09-04** (commiteada en
`9f46b0a`). `tools/build_malboguistic.py --level1-only` la regeneró el 2026-11-01, así que
dos cosas de ahí quedan obsoletas y se corrigen sin borrarlas:

1. El «Aviso de cadena» («`evidence/VERDICTS.md` sigue diciendo `REPRODUCIBLE_BUILD =
   DEMONSTRATED`») ya no aplica al archivo actual: esa clave **no existe** en la tabla de
   hoy. La tabla del 2026-09-04 sigue tal cual en el historial de git y ese renglón vale
   allí como `[HISTORICAL]`.
2. La clave `REPRODUCIBLE_BUILD_LEVEL2_BYTE_EXACT` se dividió en dos, porque mezclar
   «la síntesis es reproducible» con «el corpus commiteado no cambia» fue el error que se
   quiso corregir:

| clave (hoy) | cómo se evalúa | estado |
|---|---|---|
| `REPRODUCIBLE_BUILD_LEVEL1_BYTE_EXACT` | `LEVEL1_CODEC_MISMATCH == 0 and LEVEL1_CODEC_MIRRORED == FILES_TEXT` | DEMONSTRATED, medida en cada corrida |
| `REPRODUCIBLE_BUILD_LEVEL2_SYNTHESIS` | literal `NOT_CLAIMED`, con las dos puntas de evidencia (`synthesis_linux_probe_20261101/` y `zig_search_port_gate_20261101T204229ZZ/`) | NOT_CLAIMED |
| `REPRODUCIBLE_BUILD_COMMITTED_CORPUS_UNCHANGED` | comparación real: el manifest que la corrida escribe vs el que había en disco antes de escribirla | DEMONSTRATED — `54c4b704…` byte-idéntico, 1.605 adoptados, 0 resintetizados, 1,2 s |
| `MASS_TRANSLATION_REAL_MALBOLGE` | `len(candidates) > 0 and all(candidate PASS) and len(l2_fail) == 0` — la forma vieja (`len(l2_pass) == len(candidates)`) se rompió al haber PASS por encima del tope, así que se cambió por el predicado que dice lo que siempre quiso decir | DEMONSTRATED |

Lo que **no** cambió: `MASS_TRANSLATION_REAL_MALBOLGE` mide sobre el conjunto elegible del
build (`--e2e-max-bytes`, default 128 B, generator Python). Que hoy haya 1.605 artefactos
no es mérito de esa corrida: 1.226 vinieron de `tools/extend_level2_zig.py` y se
re-verifican con `tools/verify_corpus.py` (**1.605/1.605**,
`evidence/canonical_reverify_20261101T223703Z/`).

## El contrato del corpus, por escrito (append 2026-11-01)

`CONTRACT_CAT_FED` estaba en esta casa como «demonstrated como factibilidad, no adoptado».
Hoy está adoptado como **nivel 3**, con el artefacto vendorizado y fijado por SHA-256
(`vendor/cat/cat_compact.mal`, `dd8f9b10…`) y su propia corrida sellada por
`tools/verify_level3.py`: **4.258/4.258 byte-exactos** bajo `mb_ref` y `olmstead`,
31.647.823 bytes, 82,1 s — `evidence/level3_cat_sweep_20261101T223138Z/`. Los tres
contratos conviven y no son graduaciones del mismo:

| nivel | quién holds los bytes | cobertura |
|---|---|---|
| 1 | la envoltura `mirror/*.malrt1` (codec, no Malbolge) | 4.258/4.258 TEXT |
| 2 | el programa `.mal` (`CONTRACT_SELF_CONTAINED`) | 1.605/4.258, hasta 1.022 B de fuente |
| 3 | stdin + un solo `cat_compact.mal` (`CONTRACT_CAT_FED`) | 4.258/4.258 TEXT |

El tope del nivel 2 no es una elección de presupuesto: un artefacto cabe o no en la cinta
canónica de 59.049 celdas, y con `depth 5` eso corta ~1.830 B de fuente
(`evidence/level2_cap_probe_20261101T215239ZZ/`). El nivel 3 cubre el resto cambiando de
contrato, no forzando el tope.

Cerrado también el hueco del snapshot: `test/fixtures/Binary/linguist.gem` está en git
desde hoy con `git add -f` (decisión de la host, sha `55f5f0b5…` == la del inventario). El
`.gitignore` vendorizado no se tocó.

## El corpus devuelto por los `.mal`, clasificado por el linguist del snapshot (append 2026-11-02 UTC)

Aparece una verificación nueva y hay que enmarcarla antes de que alguien la cite mal.
`tools/verify_linguist_pipeline.py` (+ worker Ruby `tools/gate_adapters/linguist_classify.rb`
y generador `linguist_gen_samples.rb`) toma los 1.605 artefactos `PASS`, los ejecuta bajo los
dos oráculos fijados, decodifica la envoltura con el codec del repo y pasa los bytes al
**linguist vendorizado en el propio snapshot** (versión 9.7.0). Pack sellado:
`evidence/linguist_pipeline_sweep_20261102T043612Z/` (7,4 s de ejecución + 10,1 s de
clasificación, exit 0); cómo se llegó a ese pack y sólo a ese está en la nota de manejo de
evidencia más abajo.

| clave medida | valor |
|---|---|
| cadena de ejecución (10 eslabones, por artifact) | **1.605/1.605**, 0 fallos |
| `LINGUIST_CLASSIFICATION_PRESERVED_THROUGH_MALBOLGE` | 1.605/1.605 |
| banderas de decisión (`type`/`group`/`generated?`/`documentation?`/`vendored?`) | 1.605/1.605 |
| `MALBOLGE_RECOGNIZED_BY_LINGUIST` | **NEGATIVE — 0/1.605** |
| fuente original clasificada (no `NIL`) | 1.580/1.605, 441 idiomas |
| control negativo (0 bytes ⇒ `NIL`) | 1.605/1.605 |
| control de determinismo (mismo blob dos veces) | 1.605/1.605 |
| sensibilidad al contenido (envoltura cruda en la misma ruta) | 361/1.605 cambian: 93 a `NIL`, 268 a otro idioma |

Cómo hay que leer la fila 2, que es la que se presta: **esa concordancia está implicada por
la paridad byte a byte** — mismo path lógico, mismos bytes, mismo veredicto por construcción.
No es evidencia independiente de que Malbolge «preserve» el archivo; es el control del banco
de pruebas. La evidencia de fidelidad sigue siendo `decoded_matches_snapshot` = 1.605/1.605,
que es lo que la cadena de arriba mide eslabón por eslabón.

El hallazgo realmente nuevo es el negativo: **linguist 9.7.0 no tiene Malbolge en su
`languages.yml`** (cero coincidencias buscadas en el fichero). Ninguna salida de este barrido
autoriza a afirmar que un clasificador externo reconozca nuestros programas `.mal` como
Malbolge, ni que el corpus sea «visible como Malbolge» para ninguna herramienta externa.

Y un tercero incómodo que conviene tener escrito: presentarle a linguist la envoltura MALRT1
sin decodificar produce el mismo idioma que el archivo original en **1.244 de 1.605** casos.
Quien clasifique por la ruta no nota que le están dando un sobre de códec. No es un defecto
del corpus; es una limitación del experimento de clasificación, y por eso el control de
sensibilidad va medido en el mismo pack.

Dos notas de método, para que el pack no se lea mejor de lo que es:

- **Determinismo entre corridas, medido.** Se corrió el barrido completo **cuatro veces**. Diferencia
  entre `raw.jsonl` y `linguist_raw.jsonl` de las cuatro, ignorando `wall_ms` y la marca de tiempo:
  **0** clasificaciones distintas y **0** checks distintos en los 1.605 archivos; sólo cambian los
  `wall_ms` de los motores. La `samples_data.rb` del clasificador es byte-estable entre dos
  generaciones (`e6922461…`, 5.871.252 B).
- **Manejo de evidencia, con la trazabilidad completa.** En `evidence/` queda **un solo pack** por
  este experimento (`…T043612Z`). Los tres anteriores no se borraron ni se reescribieron: se
  **movieron** fuera del repo (reversible con un `mv`) y siguen en `/tmp/malpipe/`; los dos
  primeros llegaron a sellarse (tienen su `SHA256SUMS.txt`), el tercero abortó antes de sellar.
  La razón de cada movimiento:
  - `…T042221Z` → `/tmp/malpipe/pack_intermedio_042221Z`: reutilizó el runtime ya construido, así
    que no midió el determinismo de la DB (`samples_data_deterministic` quedó en `None`). Se volvió
    a sellar con `--rebuild-linguist`.
  - `…T042315Z` → `/tmp/malpipe/pack_con_rutas_de_host_042315Z`: **fuga de rutas absolutas del host**
    (`BUILD_RECIPE.sh` ×2 y `jobs.jsonl` ×1.605). Este repo es público, así que eso es un fallo, no
    un detalle de formato. La fuga estaba sólo en los metadatos generados: las clasificaciones y los
    checks de ese pack son idénticos a los del sellado (ver el control de arriba).
  - `…T043532Z` → `/tmp/malpipe/pack_abortado_tripwire`: primer intento tras añadir el tripwire, que
    saltó por **falso positivo** (los patrones de búsqueda genéricos `/home/` y `/root/` casaban con
    el propio código de la herramienta, que se copia al pack). El tripwire se estrechó a los prefijos
    concretos del repo y del home; las rutas del workdir en `VERDICT.md` (`/tmp/…`) quedan a la vista
    porque no son rutas del usuario del host, y se citan aquí para que no se lean como ocultación.
  El tripwire ahora tokeniza `jobs.jsonl` (`{SNAPSHOT}`, `{STAGE}`, `{REPO}`, `{MIRROR}`,
  `{MALBOLGE}`, `{WORKDIR}`) y se niega a escribir `SHA256SUMS.txt` si algún archivo del pack
  conserva el prefijo absoluto del repo o del home.

NOT_DEMONSTRATED: que la gema publicada `github-linguist` dé los mismos veredictos (aquí sólo
se usa la versión del snapshot); la clasificación de las 20 entradas `BINARY` y los 3
`SYMLINK` del inventario; y cualquier cosa sobre los 2.653 `SKIPPED_TOO_LARGE`, que no tienen
programa propio. El path de `repository.rb`/`rugged` queda excluido del cargador (una línea,
con guarda que aborta si fuera otra cosa), así que la clasificación de repositorios Git enteros
no está verificada aquí.

## Extensión del barrido al catálogo entero por la ruta del Cat (append 2026-11-02 UTC)

`tools/verify_linguist_pipeline.py` gana `--level 3` (contrato `CONTRACT_CAT_FED`) y
`--include-non-text`, y con ellas dos variantes de clasificación nuevas: `prefix64` (los primeros
64 bytes, misma ruta) y el job `@cat_program` (clasificar el propio `cat_compact.mal`). El scope
deja de ser "los que tienen `.mal`" y pasa a ser **el catálogo completo**: 4.258 `TEXT` + 20
`BINARY`. Pack sellado: `evidence/linguist_pipeline_level3_sweep_20261102T050208Z/`
(9 archivos, exit 0, **109,81 s de ejecución + 24,12 s de clasificación**, 21.392 blobs).
Presupuesto: 1.200.000.000 pasos en mb_ref y 600 s por proceso; los oráculos y el Cat van fijados
por SHA-256 como siempre.

| clave medida | valor |
|---|---|
| cadena de 7 eslabones por archivo | **4.278/4.278**, 0 fallos (32.945.606 bytes) |
| `CAT_FED_BYTES_REACH_LINGUIST` | DEMONSTRATED (4.278/4.278) |
| `CATALOG_FILES_WITH_NO_OWN_PROGRAM_REACHED` | DEMONSTRATED (**2.673/2.673**: 2.653 `SKIPPED_TOO_LARGE` + 20 `BINARY`) |
| `BINARY_ENTRIES_REPRODUCED_BYTE_EXACT` | DEMONSTRATED (**20/20**) — el nivel 3 nunca había barrido binarios |
| `LINGUIST_CLASSIFIES_SOURCE` (no `NIL`) | 4.235/4.278 · **770 idiomas distintos** |
| `from_cat` coincide con `source` | 4.278/4.278, pero **sólo 4.235 con idioma al frente** |
| control `prefix64` | 211/4.278 cambian de veredicto: 182 a otro idioma, 29 a `NIL` |
| control negativo (blob vacío) y de determinismo | 4.278/4.278 en los dos |
| `MALBOLGE_RECOGNIZED_BY_LINGUIST` | **NEGATIVE** — `cat_compact.mal` pasa por el `Classifier` y devuelve `NIL` |
| tiempo de motor | media 12,62 ms; máximo 1.383,8 ms (`test/fixtures/Binary/octocat.ai`, 1.041.378 B) |
| `samples_data.rb` | regenerado y byte-estable entre corridas (`e6922461…`, 5.871.252 B), 8,89 s |

### Del `NOT_DEMONSTRATED` de arriba: qué queda cubierto y qué sigue en pie

Cubierto por este pack, con evidencia commiteada:

- la clasificación de las **20 entradas `BINARY`**, y
- "cualquier cosa sobre los 2.653 `SKIPPED_TOO_LARGE`": ahora tienen una ruta Malbolge medida
  (el Cat universal) y una clasificación medida. Lo que **no** tienen sigue siendo un programa
  `.mal` propio —el nivel 3 no crea artefactos—, así que su cobertura no sustituye a la del
  nivel 2 y la frase "cada archivo del catálogo tiene su programa" no autoriza a decirla.

Sigue en pie, sin cambios:

- que la gema publicada `github-linguist` dé los mismos veredictos (aquí sólo se usa la copia del
  snapshot, lingüist 9.7.0);
- los **3 `SYMLINK`**: no están en el snapshot vendido —buscados en disco y en `git ls-files`, no
  existen— y en el pack constan `[ABSENT]`, no como acuerdo;
- la clasificación de repositorios Git enteros (el path `repository.rb`/`rugged` sigue fuera);
- y el costo de síntesis: esta herramienta no llama a `malbolge-generator`.

### Tres controles cruzados, los tres sin diferencias

1. **Dos corridas del nivel 3** (`…T045845Z` y `…T050208Z`): las 4.278 filas de `raw.jsonl` son
   idénticas ignorando `wall_ms`, y `linguist_raw.jsonl` tiene 4.279 registros en ambas con
   **0** diferencias como conjunto.
2. **Contra el pack de nivel 2** sobre los 1.605 archivos comunes: **0** inconsistencias comparando
   `language/type/group/strategy` de la fuente y de lo devuelto por el programa. Dos contratos
   distintos (`CONTRACT_SELF_CONTAINED` y `CONTRACT_CAT_FED`) convergen en el mismo veredicto.
3. **Contra `evidence/level3_cat_sweep_20261101T223138Z/`** (otra herramienta, otro día, sin
   linguist en medio): el conjunto de `TEXT` exactos bajo ambos oráculos es el mismo —4.258 en
   los dos packs, diferencia simétrica **0**.

### Lecturas que no se pueden citar sueltas

- **El 4.278/4.278 de `from_cat` es más hueco que el del nivel 2**: 43 archivos no tienen idioma en
  ninguno de los dos lados y en las 20 `BINARY` sólo 3 lo tienen, así que 20/20 de "coincidencia"
  binaria son **17 `NIL == NIL`**. El pack publica las dos columnas (`coincide` / `coincide con
  idioma`) para que la primera no se cite sola.
- **`prefix64` sí es independiente de la paridad byte a byte**, porque compara dos contenidos
  distintos en la misma ruta; cuantifica cuánto del veredicto sostiene la ruta y los primeros
  caracteres.
- **La etiqueta `BINARY` del inventario es regla nuestra** (NUL o no-UTF-8: 16 por NUL, 4 por
  no-UTF-8), no veredicto de linguist, que confirma `binary? == true` en **14** —los 14 de
  `test/fixtures/Binary/`, todos por `bail_out`— y lo rechaza en los otros **6**: 3 reciben idioma
  (`Altium Designer` y `Oberon` por extensión, `Roff` por heurística) y 3 caen al `Classifier` y
  devuelven `NIL` (`iso8859-8-i` y los dos UTF-16, que llevan NULs porque la codificación los pide).

### Manejo de evidencia de este experimento

En `evidence/` queda **un solo pack** nivel 3 (`…T050208Z`). El intento anterior del mismo
experimento, `linguist_pipeline_level3_sweep_20261102T045845Z`, se **movió** fuera del repo —no se
borró, y es reversible con un `mv`— a `/tmp/malpipe/pack_level3_render_045845Z`. La razón es
cosmética y hay que decirla: la tabla por tipo de entrada del `VERDICT.md` no iba precedida de una
línea en blanco y GitHub no la renderizaba. Los datos de ambos packs son idénticos (control 1 de
arriba), y se re-selló para que la evidencia commiteada se vea como se lee. El tripwire de rutas
volvió a pasar: los 9 archivos del pack están sin prefijo absoluto del repo ni del home, y
`sha256sum -c` cuadra los 9.
