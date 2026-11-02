# MALBOGUISTIC

> GitHub Linguist actualmente no reconoce Malbolge.
>
> Asi que tradujimos GitHub Linguist a Malbolge en su lugar. :p

**Este proyecto NO reclama que Linguist se ejecute en Malbolge.**

Este proyecto toma un snapshot fijado de [github-linguist/linguist](https://github.com/github-linguist/linguist)
y lo transporta mecanicamente, byte por byte, a traves de una cadena de herramientas de Malbolge,
verificando reconstruccion byte-identica con SHA-256.

```
github-linguist/linguist  (snapshot fijado, commit SOURCE_COMMIT.txt)
        ↓
Malbolge-Translator  (vendored bajo vendor/malbolge_translator/)
        ↓
Nivel 1: mirror/<path>.malrt1     (envoltura MALRT1, cada archivo de texto, codec-verificado)
Nivel 2: malbolge/<path>.mal      (programas REALES de Malbolge, ejecutados, verificados)
Nivel 3: vendor/cat/cat_compact.mal (UN solo programa; cada archivo entra por stdin y
          sale por stdout byte-exacto — no hay traduccion por archivo)
        ↓
traduccion reversa (decode + ejecucion)
        ↓
paridad SHA-256 contra los bytes originales
```

## Tres niveles, sin falsos

| Nivel | Alcance | Artifact | Reclamo |
|---|---|---|---|
| 1 — Codec mirror | **cada** archivo TEXT | `mirror/**/*.malrt1` | `CODEC_MIRROR_PARITY`: bytes fuente → MALRT1 → decode → SHA-256 identico |
| 2 — Malbolge real | archivos TEXT ≤ 1.024 B (frontera movida a d5 del port a Zig), bajo presupuesto de wall-clock | `malbolge/**/*.mal` | `FULL_EXECUTED_ROUNDTRIP`: fuente → Malbolge puro sintetizado → ejecucion canonica → decode → SHA-256 identico |
| 3 — Cat canónico | **todos** los archivos del catálogo: 4.258 TEXT **y** las 20 BINARY (4.278 en total; sólo los 3 `SYMLINK` no existen en el snapshot) | `vendor/cat/cat_compact.mal` (un solo programa) | `CONTRACT_LEVEL3_CANONICAL_CAT`: el archivo entra por stdin y el programa imprime sus bytes exactos — **no** incorpora el archivo al programa |

CODEC ROUNDTRIP ≠ FULL MALBOLGE E2E PARA ARCHIVOS ARBITRARiAMENTE GRANDES.
El costo de sintesis del nivel 2 **no es una ley por byte**. El "~0.7 s por byte
fuente" era de la maquina Windows de 2026-09-04 ⇒ `[HISTORICAL]`. Medido en Linux
(2026-11-01, profundidad 5, un proceso por archivo, `evidence/synthesis_linux_probe_20261101/`):
**~6 s fijos + ~0.16 s por byte**, o sea 5.7 s para 4 B y 21.2 s para 96 B. Ese numero es
de muro y **no dice nada de memoria**: la misma llamada, remedida con guarda
(`evidence/level2_cap_probe_20261101T215239ZZ/`), pide **>3 GB para un archivo de 96 B** y
**>5.5 GB para uno de 97 B**, y el control de 2 B ya se para en ~1.2-1.4 GB. Por eso el
generador Python no es via para extender el corpus en este host.
El port a Zig si lo es, y es el mismo trabajo: **1,11 ms por caracter de envoltura y 165 MB
de techo** (profundidad 5), 0,2 s para ese mismo CODEOWNERS de 96 B.
No pretendemos lo contrario: cada archivo no sintetizado se marca
`SKIPPED_TOO_LARGE` o `SKIPPED_BUDGET` en el manifest. Nada se oculta.

La sintesis del nivel 2 (generator Python) **no es byte-reproducible**: el mismo archivo,
tres corridas, produce programas distintos (todos con roundtrip PASS). Lo que estabiliza el
corpus **no** es `--resume` —su estado (`evidence/level2_state.json`) está en `.gitignore`,
así que es local a un host— sino la **adopción del manifest commiteado**: el build arrastra
los PASS que ya tienen su `.mal` en disco con el sha256 del manifest intacto, y no los
resintetiza. Medido 2026-11-01: `--level1-only` sobre el corpus entero reescribió un
`manifest/translation_manifest.json` **byte-idéntico** al que había (`54c4b704…`,
1.605 adoptados, 0 resintetizados, 1,2 s de muro); esa comparación es la fila
`REPRODUCIBLE_BUILD_COMMITTED_CORPUS_UNCHANGED`, escrita como medida, no como literal.
El nivel 1 (codec) si es determinista, y **el port a Zig
(`tools/zig_canonical/mbsearch.zig`) tambien lo es**: misma configuracion, misma huella
(medido 3 objetivos x 5 repeticiones → huella unica). Ojo: determinista no es
"reproduce el corpus commiteado" — contra los `.mal` del repo son 0/379 byte-identicos.
Lo que el port si cubre es el corpus entero: los 379 objetivos originales (cadenas de
envoltura de 72 a 244 caracteres) en 63 s de pared, 70,7M de evaluaciones, 379/379
canonicos bajo `mbc`, **más** los 1.226 que suben la frontera a 1.022 B
(`tools/extend_level2_zig.py`, 1.173.971.071 evaluaciones en 933 s).

El nivel 1 tiene su propio gate: `tools/level1_determinism.py` codifica **dos veces** cada
fuente TEXT y exige que los dos payloads coincidan entre si y con la envoltura commiteada
byte a byte. Medido 2026-11-01: **4.258/4.258 PASS en 0,44 s** (42,5M de caracteres de
envoltura), con `source_sha256` y `envelope_sha256` del manifest reproduciéndose también
4.258/4.258 — `evidence/level1_determinism_20261101T214729ZZ/`. Por eso el build puede
prometer `REPRODUCIBLE_BUILD_LEVEL1_BYTE_EXACT`; la sintesis de nivel 2 se marca
`REPRODUCIBLE_BUILD_LEVEL2_SYNTHESIS = NOT_CLAIMED` (no hay reclamación que sostener ahí).

Una envoltura `.malrt1` es texto ASCII (`MALRT1:<base64>:<sha256>`), **no** un
programa Malbolge. Solo los archivos bajo `malbolge/` son Malbolge ejecutable.

## Ejecucion actual (commit fijado: befd3af35e70150b76458085208435eef9286bb3)

| Metrica | Valor |
|---|---|
| Archivos fuente (incl. 3 symlinks registrados) | 4,281 |
| Archivos de texto mirror-eados (nivel 1) | 4,258 / 4,258 (paridad codec, 0 desajustes) |
| Archivos binarios saltados | 20 (sin programa propio; **sí** reproducidos byte a byte por el nivel 3) |
| **Programas reales de Malbolge sintetizados + ejecutados (nivel 2)** | **1.605 / 4.258 textos (379 ≤128 B por el generator + 1.226 hasta 1.022 B por el port a Zig), 0 fallos** |
| Bytes de texto originales | 31,647,823 |
| Bytes de texto cubiertos por nivel 2 | 662,412 |
| Bytes de envoltura mirror (`mirror/`) | 42,509,444 (×1.34) |
| Bytes de programa real de Malbolge (`malbolge/`) | 23,944,625 |
| Ratio de expansion (nivel 2) | min ×20.57 · mediana ×24.24 · max ×462.75 |
| **Nivel 3 — Cat canónico sobre el catálogo entero** | **4.258 / 4.258 archivos TEXT, 31,647,823 bytes, byte-exactos bajo ambos oráculos** |
| **Nivel 3 ampliado — también las 20 BINARY, y esas bytes clasificadas por linguist** | **4.278 / 4.278 archivos, 32,945,606 bytes**, 0 fallos · 4.235 con idioma al frente · **770 idiomas distintos** · Malbolge = `NIL` |

Detalles completos: `evidence/metrics.json`, `evidence/roundtrip.json`,
`evidence/VERDICTS.md` (tabla de claims) y su anexo de correcciones
`evidence/VERDICTS_CORRECTION_20261101.md`, y `manifest/translation_manifest.json`
(una entrada por archivo de texto; su SHA-256 es `evidence/manifest_sha256.txt`).

## Modernización del motor (2026-11-01)

Hasta esta sesión, la verificación del nivel 2 se apoyaba en el intérprete Python del
toolkit, que reejecutaba **los opcodes en memoria del generador**: nunca ejecutaba el
archivo `.mal` que este repo commitea. Se construyó encima una pila de verificación
propia, con un paquete de evidencia sellado por paso:

| qué | resultado medido | paquete |
|---|---|---|
| oráculos C vendorizados y fijados por SHA-256 | `mb_ref.c` (mismo byte que BolgeForge y PureEpoch) + `olmstead_original.c` (Olmstead 1998, dominio público) | `vendor/oracles/PROVENANCE.txt` |
| `tools/verify_corpus.py` — ejecutar **el archivo commiteado** | 1.605/1.605 · inventario 4.281/4.281 · 6,27 s (antes: 379/379 en 1,57 s) | `evidence/canonical_reverify_20261101T223703Z/` |
| `tools/engine_gate.py` — acuerdo semántico multi-motor, tier 2 con stdin real | `zig/bolg1` 382/383 (trunca a ~64 KiB) y toolkit Python 379/383 (0/4) ⇒ **DIVERGENTES**; los oráculos 383/383 | `evidence/engine_canonical_gate_20261101T080313ZZ/`, `…T082034ZZ/` |
| `tools/zig_canonical/mbc.zig` — motor canónico en Zig | **383/383** CANONICAL_AGREEMENT · 421.317.177 pasos/s frente a 412.592.903 del oráculo (ratio **1,02**) | `evidence/zig_canonical_engine_gate_20261101T154528ZZ/` |
| `tools/zig_canonical/mbsearch.zig` — port a Zig de la búsqueda del nivel 2 | corpus **379/379** canónico en **63 s** (70,7M de evaluaciones) · 12/12 y 30/30 byte-idéntico a la referencia con flujo RNG compartido | ver sección Zig |
| `CONTRACT_CAT_FED` — factibilidad: un solo `.mal` copiador con el archivo por stdin | **4.258/4.258** exactos bajo ambos oráculos, 31.647.823 bytes, 93,3 s | `evidence/corpus_cat_feasibility_20261101T074215Z/` |
| **nivel 3 adoptado**: `tools/verify_level3.py` sobre el Cat vendorizado y fijado por SHA-256 | **4.258/4.258** exactos bajo `mb_ref` y `olmstead`, 31.647.823 bytes, 82,1 s, 0 fallos | `evidence/level3_cat_sweep_20261101T223138Z/` |
| reparación del snapshot | 199 TEXT devueltos a los bytes de su propia envoltura + 3 BINARY desde upstream en `befd3af` (2 normalizados, 1 ausente) | `evidence/snapshot_eol_repair_20261101/` |
| `tools/level1_determinism.py` — determinismo del nivel 1 | **4.258/4.258** doble codificación idéntica y **byte-identica al `mirror/` commiteado** en 0,44 s | `evidence/level1_determinism_20261101T214729ZZ/` |
| sonda de tope del nivel 2 (Zig vs Python) | port: 1,11 ms/caracter y 165 MB (d5), frontera dura en la cinta (59.049 celdas ⇒ ~1.830 B a d5, ~3.900 B a d8); Python: **>3 GB a 96 B y >5,5 GB a 97 B** | `evidence/level2_cap_probe_20261101T215239ZZ/` |
| `tools/extend_level2_zig.py` — mover la frontera del nivel 2 de 128 B a 1.024 B con el port | **1.226 artefactos nuevos, 0 fallos**, 1.173.971.071 evaluaciones, 933 s; corpus resultante verificado 1.605/1.605 | `evidence/level2_zig_extend_20261101T221438Z/` |
| adopción del corpus commiteado en el build (nada de resintetizar sellado) | manifest reescrito **byte-idéntico** (`54c4b704…`): 1.605 adoptados, 0 resintetizados, 1,2 s | fila `REPRODUCIBLE_BUILD_COMMITTED_CORPUS_UNCHANGED` en `evidence/VERDICTS.md` |
| `tools/verify_linguist_pipeline.py` — el corpus devuelto por los `.mal`, clasificado por el linguist del snapshot | **1.605/1.605** de acuerdo con la clasificación del original · 441 idiomas · cadena de ejecución 10/10 eslabones verdes · **Malbolge no existe para linguist: 0/1.605** | `evidence/linguist_pipeline_sweep_20261102T043612Z/` |
| `tools/verify_linguist_pipeline.py --level 3 --include-non-text` — el catálogo **entero** por el Cat, clasificado por el mismo linguist | **4.278/4.278** byte-exactos (32.945.606 B), **incluidas las 20 BINARY** · **2.673 archivos sin `.mal` propio** alcanzados · 770 idiomas · Malbolge: NEGATIVE también para el Cat | `evidence/linguist_pipeline_level3_sweep_20261102T050208Z/` |

Nada de esto requiere `malbolge-generator`, salvo el tier diferencial del port.

Corrección de una cifra citada antes a boca de jarro: el margen del oráculo C sobre el
intérprete Python del toolkit es **~646×** (in-process, 584.664–652.484 pasos/s), no
~1.500×; el ~1.500× venía de una medida por subprocess que mezclaba el arranque del
intérprete y el empaquetado del programa.

## Reproducir

Requiere Python ≥ 3.10 para el nivel 1. El nivel 2 exige ademas `malbolge-generator`
(importable como `malbolge`, MIT, upstream `wallstop/malbolge-toolkit`), que **no esta
en PyPI**: se instala desde una copia local y el propio paquete pide Python ≥ 3.11.
Sin ese paquete el build reporta `SYNTHESIS_UNAVAILABLE` y produce solo nivel 1.
En este host: `python3` (los `py` de la GUIA son `[HISTORICAL]` de la maquina Windows).

```
python3 tools/build_malboguistic.py                # completo: nivel 1 + nivel 2 (default 1 h de budget)
python3 tools/build_malboguistic.py --level1-only  # solo codec mirror + adopcion, segundos
python3 tools/verify_corpus.py                     # re-verifica el nivel 2 SIN generator (oraculos C)
python3 tools/verify_level3.py                     # nivel 3: el catalogo entero por stdin contra el Cat
python3 tools/verify_linguist_pipeline.py           # nivel 2 ejecutado -> decodificado -> clasificado por linguist
python3 tools/verify_linguist_pipeline.py --level 3 --include-non-text  # catalogo entero por el Cat -> clasificado
python3 tools/level1_determinism.py --evidence evidence/level1_determinism_<UTC>/
python3 tools/extend_level2_zig.py --evidence evidence/level2_zig_extend_<UTC>/ \
    --cap-bytes 1024 --depth 5 --apply-manifest   # mueve la frontera del nivel 2
```

Opciones del build: `--e2e-max-bytes` (default 128), `--e2e-budget-seconds` (default 3600),
`--workers`, `--resume` (estado local al host, esta en `.gitignore`) y `--no-adopt`
(resintetiza y **sustituye bytes sellados**; por defecto apagado).

`tools/extend_level2_zig.py` no necesita `malbolge-generator`, pero si `zig` en el PATH:
compila el port desde `tools/zig_canonical/*.zig` con `zig build-exe -O ReleaseFast` y deja
las huellas del binario que ejecuto en el paquete. Escribe cada artefacto nuevo con
`lineage: "zig_port"` y `synthesizer_binary_sha256`, y lo verifica con los dos oraculos
antes de tocar el manifest. Sin `--apply-manifest` corre en scratch y no escribe el repo.

Exit code 0 ⇔ cero desajustes de codec Y cero ejecuciones fallidas.

## Re-verificación canónica (no requiere `malbolge-generator`)

El build histórico verificó el nivel 2 reejecutando **los opcodes en memoria del
generador** (`translator.py: execute(full_opcodes, ...)`). O sea: nunca se ejecutó el
archivo `.mal` que este repo commitea.

`tools/verify_corpus.py` ejecuta **el archivo commiteado** bajo dos interpretadores
independientes, fijados por SHA-256 en `vendor/oracles/` (procedencia y licencias en
`vendor/oracles/PROVENANCE.txt`):

| Motor | Linaje | EOF de `in` |
|---|---|---|
| `mb_ref.c` | referencia estricta (byte-idéntica en BolgeForge y Malbolge-PureEpoch) | 59048 = 3^10 − 1 |
| `olmstead_original.c` | Ben Olmstead 1998, dominio público | 59048 |

Nota: los `mb_ref.c` de BolgeForge y PureEpoch son el mismo byte, así que entre ellos
NO hay evidencia independiente; la independencia real es contra Olmstead 1998.

```
python3 tools/verify_corpus.py            # sellado automático en evidence/canonical_reverify_<UTC>/
python3 tools/verify_corpus.py --no-differential   # solo mb_ref (más rápido)
```

Comprueba 9 ligas por artefacto: sha del `.mal` vs manifest, sha de la envoltura vs
manifest, auto-consistencia de la envoltura, snapshot == bytes decodificados, HALT y
salida exacta en cada motor, y acuerdo entre motores. Exit 0 ⇔ todos limpios.

Ultima corrida (2026-11-01, Linux, corpus extendido): **1.605/1.605 en las 9 ligas +
inventario 4281/4281**, 6,27 s de pared → `evidence/canonical_reverify_20261101T223703Z/`.
Antes de la extension: 379/379 en 1,57 s → `evidence/canonical_reverify_20261101T071314Z/`.

## Nivel 3 — el catalogo entero por un solo programa (`CONTRACT_CAT_FED`)

El nivel 2 no puede cubrir los 4.258 textos: cada artifact tiene que caber en la cinta
canonica de 59.049 celdas, y con `depth 5` eso corta alrededor de 1.830 B de fuente. El
nivel 3 cambia el contrato en vez de forzar el tope: **un** programa,
`vendor/cat/cat_compact.mal` (7.596 celdas, sha256 `dd8f9b10…`, fijado en
`vendor/cat/PROVENANCE.txt`), recibe el archivo por stdin y tiene que imprimir sus bytes
exactos.

```
python3 tools/verify_level3.py                    # 4.258 archivos x 2 oraculos, ~82 s
python3 tools/verify_level3.py --sample 50        # smoke, nunca un reclamo sellado
```

Ultima corrida sellada (2026-11-01, Linux): **4.258/4.258 exactos** bajo `mb_ref` y
`olmstead`, 31.647.823 bytes, 82,1 s, 0 fallos → `evidence/level3_cat_sweep_20261101T223138Z/`.

Lo que el nivel 3 **no** es: no mete los bytes del archivo dentro del programa, así que no
hay traducción por archivo ni árbol `malbolge/` comparable. Es un contrato distinto, no un
nivel 2 mas grande, y no sustituye a las filas de nivel 2 del manifest. Scope de
`tools/verify_level3.py`: las 4.258 entradas `TEXT`. Las 20 `BINARY` **sí** están
reproducidas byte a byte, pero por la otra variante del mismo contrato —
`tools/verify_linguist_pipeline.py --level 3 --include-non-text`, 4.278/4.278 y 32.945.606
bytes (sección más abajo)—, no por ese script; y las 3 `SYMLINK` no existen en el snapshot
vendido, así que no tiene dónde ejecutarse.

Esto re-verifica **ejecución** y **integridad del snapshot**. La **síntesis** sigue
necesitando `malbolge-generator`, que no está en PyPI: se instala desde la copia local
del monorepo (`workspace/malbolge_toolkit`, `pip install <ese directorio>`). Sin él el
build reporta `SYNTHESIS_UNAVAILABLE` y no produce nivel 2 nuevo. Con él, el ciclo
fuente → `.mal` → oráculos canónicos → SHA-256 ya vuelve a cerrar en Linux
(`evidence/synthesis_linux_probe_20261101/`).

## El corpus devuelto por los `.mal`, clasificado por el linguist del propio snapshot

`tools/verify_linguist_pipeline.py` cierra el círculo sobre dos poblaciones, según la
bandera `--level`. Con `--level 2` (el default) toma la población `PASS` del manifest:
ejecuta cada archivo `.mal` commiteado bajo los dos oráculos fijados por SHA-256,
decodifica la envoltura MALRT1 con el codec del repo, y pasa los bytes a
**la copia de linguist que está dentro del snapshot** (`vendor/source_snapshot`,
versión 9.7.0), no a la gema publicada. Cada archivo se clasifica en seis variantes
(`source`, `source_repeat`, `from_mal`, `envelope`, `malprog`, `empty`), todas con el
**mismo path lógico** salvo `malprog`, de modo que la única variable sea el contenido.
Con `--level 3` el contrato cambia a `CONTRACT_CAT_FED` y la población también —ver
«Extensión» más abajo—: el archivo entra por stdin del Cat canónico y se clasifica lo que
sale por stdout.

Corrida sellada del nivel 2 (2026-11-02 UTC, Linux; 7,4 s de ejecución + 10,1 s de clasificación):

| afirmación | medido |
|---|---|
| LEVEL2_ARTIFACTS_EXECUTE_AND_REPRODUCE | **1.605/1.605**, cadena de 10 eslabones verde |
| LINGUIST_CLASSIFICATION_PRESERVED_THROUGH_MALBOLGE | **1.605/1.605** |
| flags de decisión (tipo, grupo, `generated?`, `documentation?`, `vendored?`) | **1.605/1.605** |
| idioma reconocido en la fuente original | 1.580/1.605, **441 idiomas distintos** |
| MALBOLGE_RECOGNIZED_BY_LINGUIST | **NEGATIVE: 0/1.605** |
| control negativo (0 bytes) | 1.605/1.605 devuelven `NIL` |
| control de determinismo (mismo blob, dos veces) | 1.605/1.605 idéntico |
| sensibilidad al contenido (envoltura sin decodificar) | 361/1.605 cambian (93 a `NIL`, 268 a otro idioma) |

Las tres lecturas obligadas:

- **La concordancia de clasificación está implicada por la paridad byte a byte**, no es
  evidencia independiente de fidelidad: mismo path y mismos bytes forzan el mismo
  veredicto. Su valor es que actúa de control del banco de pruebas — si el harness se
  rompe, ahí se ve. La evidencia de fidelidad sigue siendo `decoded_matches_snapshot`.
- **linguist 9.7.0 no conoce Malbolge**: cero coincidencias en su `languages.yml`. Ningún
  resultado de este barrido autoriza a decir que "linguist reconoce nuestros `.mal`".
- La envoltura sin decodificar pasa por el archivo original en **1.244 de 1.605** casos:
  un clasificador que mira la ruta por delante no nota que le llegan MALRT1. Es conducta
  de linguist, no un defecto del corpus, y hay que decirlo cuando se cite esta sección.

Requisitos del entorno: Ruby ≥ 3.2 con las gemas `charlock_holmes` y `mini_mime`
(`gem install --user-install charlock_holmes mini_mime`; el tool **no** instala gemas y
falla cerrado con el comando exacto). El runtime de linguist —lexer nativo
`linguist.so` y `samples_data.rb` generado— se construye en `--workdir` (por defecto
`/tmp/malboguidstic_linguist_rt`), **nunca dentro del repo**. `linguist.rb` se carga
quitando una sola línea, `require 'linguist/repository'`, única arrastradora de `rugged`
y usada sólo para clasificar repositorios Git; el worker aborta si el fichero no pierde
exactamente esa una línea.

```
python3 tools/verify_linguist_pipeline.py --limit 40 --evidence /tmp/smoke   # humo, no sella
python3 tools/verify_linguist_pipeline.py                                    # barrido completo
```

Cuatro corridas completas independientes del nivel 2: **0** diferencias en clasificaciones
y **0** en checks entre ellas; lo único que cambia son los `wall_ms` de los motores. En
nivel 3 las dos corridas dan las mismas 4.278 filas ignorando tiempos, pero la reemplazada
vivió fuera del repo (`/tmp/malpipe/pack_level3_render_045845Z`), así que ese control está
**documentado** en el anexo, no verificable desde el pack commiteado. La DB
del clasificador es byte-estable entre dos generaciones (`sha256` `e6922461…`, 5.871.252 B).

El pack **no puede contener rutas del host**: `jobs.jsonl` se tokeniza (`{SNAPSHOT}`,
`{STAGE}`, `{REPO}`, `{MIRROR}`, `{MALBOLGE}`, `{WORKDIR}`) y la copia absoluta queda en el
workdir; antes de escribir `SHA256SUMS.txt` un tripwire recorre el directorio y, si algún
archivo conserva el prefijo absoluto del repo o del home, se niega a sellar. Este repo es
público, así que la fuga de rutas es tan fallo como un `FAIL` en la cadena.

### Extensión: el catálogo entero por la ruta del Cat (`--level 3`)

El barrido anterior sólo llegaba a los 1.605 archivos que tienen `.mal` propio. Los otros
**2.673** (2.653 `SKIPPED_TOO_LARGE` + 20 `BINARY`) no tienen programa: la única ruta
Malbolge que los alcanza es el Cat universal con el archivo por stdin. El mismo tool, con
`--level 3`, cambia de contrato y de población —mismos oráculos fijados, mismo linguist del
snapshot, mismo tripwire de rutas— y añade dos variantes: `from_cat` (lo que devuelve el Cat,
en la misma ruta lógica) y `prefix64` (los primeros 64 bytes, misma ruta).

```
python3 tools/verify_linguist_pipeline.py --level 3 --include-non-text --rebuild-linguist
```

Medido en `evidence/linguist_pipeline_level3_sweep_20261102T050208Z/` (109,8 s de ejecución +
24,1 s de clasificación, 21.392 blobs, exit 0):

| afirmación | medido |
|---|---|
| cadena de 7 eslabones por archivo | **4.278/4.278**, 0 fallos (32.945.606 bytes) |
| `BINARY_ENTRIES_REPRODUCED_BYTE_EXACT` | **20/20** — el nivel 3 nunca había barrido binarios |
| `CATALOG_FILES_WITH_NO_OWN_PROGRAM_REACHED` | **2.673/2.673** |
| idioma reconocido en la fuente original | 4.235/4.278 · **770 idiomas distintos** (441 en el subconjunto de nivel 2) |
| `from_cat` coincide con `source` | 4.278/4.278, pero **sólo 4.235 con idioma al frente** |
| control `prefix64` (64 bytes, misma ruta) | 211/4.278 cambian: 182 a otro idioma, 29 a `NIL` |
| `cat_compact.mal` clasificado como idioma | **NEGATIVE — NIL** (pasa por el `Classifier` y devuelve nil) |
| controles negativo y de determinismo | 4.278/4.278 los dos |

Lecturas obligadas:

- **El `from_cat` 4.278/4.278 es más hueco que el del nivel 2**: 43 archivos no tienen idioma
  en ninguno de los dos lados, y en las 20 `BINARY` sólo 3 lo tienen, así que 20/20 de
  "coincidencia" binaria son 17 `NIL == NIL`. El pack lo separa en columnas
  (`coincide` / `coincide con idioma`) para que no se pueda citar la primera sin la segunda.
- **`prefix64` sí es independiente de la paridad byte a byte**: compara dos contenidos
  distintos en la misma ruta. Que sólo 211 de 4.278 cambien de veredicto al quedarse con 64
  bytes cuantifica cuánto depende linguist de la ruta y de los primeros caracteres.
- **Nuestra etiqueta `BINARY` no es la de linguist.** De los 20 archivos que el inventario
  marca como binarios (regla propia: NUL o no-UTF-8), linguist considera `binary? == true`
  en **14** (todos `bail_out` → `NIL`); en los otros **6** no: 3 reciben idioma
  (`Altium Designer` y `Oberon` por extensión, `Roff` por heurística) y 3 caen al
  `Classifier` y devuelven `NIL` — entre ellos los dos fixtures UTF-16, que tienen NULs
  porque la codificación lo pide.
- Las 3 entradas `SYMLINK` del inventario **no están en el snapshot vendido** (buscadas en
  disco y en `git ls-files`: no existen). Constan como `[ABSENT]`, no como acuerdo.

Tres controles cruzados, todos sin diferencias: las dos corridas de nivel 3 dan el mismo
`raw.jsonl` saliendo los tiempos; sobre las 1.605 archivos comunes con el pack de nivel 2,
0 inconsistencias entre las dos rutas (misma clasificación, los dos contratos verdes); y el
`exact` bajo `mb_ref` y `olmstead` de los 4.258 `TEXT` coincide con el barrido del Cat
sellado ayer por `tools/verify_level3.py`, que es otra herramienta y otro día.

## Motor canónico y búsqueda en Zig (`tools/zig_canonical/`)

Dos programas, misma máquina canónica Classic (59.049 celdas, `c`/`d` envolviendo en
59048, `in` en EOF = 59048, cola rellenada con `crazy`), construidos con Zig 0.16:

| programa | qué es | gate sellado |
|---|---|---|
| `mbc.zig` | intérprete canónico: `mbc <archivo.mal> <pasos>`; gateado contra los dos oráculos C, **aún no** sustituye a `mb_ref.c` dentro de `verify_corpus.py` | `evidence/zig_canonical_engine_gate_20261101T154528ZZ/` (383/383, iguala al oráculo en velocidad) |
| `mbsearch.zig` | port de la búsqueda del nivel 2 (`generate_for_string`) sobre `mbc`: misma bootstrap `i`+99`o`, mismos candidatos `op*`, misma poda, mismo cierre con `v` | `evidence/zig_search_port_gate_20261101T204042ZZ/` (determinismo + 12/12 byte-idéntico a la referencia), `…T204229ZZ` (corpus 379/379 canónico), `…T204332ZZ` (`depth 3`, 30/30) |

```
zig build-exe -O ReleaseFast -femit-bin=mbc      tools/zig_canonical/mbc.zig
zig build-exe -O ReleaseFast -femit-bin=mbsearch tools/zig_canonical/mbsearch.zig
./mbsearch --target-file mirror/samples/Text/foo.txt.malrt1 --out /tmp/p.mal --depth 5
./mbc /tmp/p.mal 5000000000                      # imprime el sobre exacto
python3 tools/mbsearch_gate.py --mode all --limit 12 --depth 5 --site-packages <site-packages>
```

Lo que el port **sí** reproduce: el texto del programa de la referencia, cuando ambos
lados consumen el mismo flujo aleatorio (SplitMix64 copiado en Python dentro de
`mbsearch_gate.py`). Lo que **no**: el sembrado MT19937 de `random.Random(42)`, que no
corresponde a ninguna inicialización estándar. Por eso el port **no regenera los `.mal`
commiteados** (0/379 byte-identicos) y tampoco lo hace la toolkit actual: la
procedencia del linaje generator es heterogénea (`search_depth` = `null` en 354 entradas,
`3` en 25). La canonicidad, en cambio, sí se reproduce: 379/379 en 63 s, y los 1.226
objetivos nuevos del `tools/extend_level2_zig.py` (hasta 1.022 B de fuente, `depth 5`,
`lineage: zig_port`) salen del mismo port con el binario actual
(`mbsearch.zig` fuente `b99e5e91…`, binario `e986891a…`; la diferencia con el binario que
selló el gate es solo el comentario de cabecera, y la equivalencia de comportamiento se
midio: 439/439 programas idénticos, `evidence/zig_search_port_gate_20261101T204229ZZ/SOURCE_CORRECTION.md`).
Resultado de la extension: 1.173.971.071 evaluaciones en 933 s, 0 fallos, y
**1.605/1.605** canónicos al re-verificar el árbol entero.

Coste medido del port (mismo host): **70,7M de evaluaciones de los 379 objetivos en 63 s
de pared**, ≥1,1M evaluaciones/s, es decir **78×-107×** sobre el camino Python. Eso
convierte la decisión del tope de búsqueda en una decisión de almacenamiento, no de CPU:
sobre los mismos 30 objetivos, `depth 3` = 151.766 caracteres (57,5×), `depth 5` =
65.940 (25,0×), `depth 8` = 34.017 (12,9×), a cambio de 1,44M / 3,30M / 18,44M de
evaluaciones (`evidence/zig_search_port_gate_20261101T204822ZZ/`, `…T204850ZZ`, `…T204916ZZ`).

A diferencia del generador Python, el port es determinista por construcción: misma
configuración, misma huella (medido 3 objetivos × 5 repeticiones → huella única).

## Reparación 2026-11-01: 202 archivos normalizados o ausentes

`vendor/source_snapshot/` tenía **199 de 4258** archivos de texto con CRLF convertido a
LF, commiteados antes de existir `.gitattributes` (`* -text`, añadido en `ad03146`, o
sea tarde: la normalización quedó horneada en el blob). Las envolturas `.malrt1` y el
upstream fijado (`befd3af`) coinciden entre sí; el eslabón roto era el snapshot. Se
restauraron los 199 desde los bytes de su propia envoltura (auto-consistente por
SHA-256), sin regenerar ningún programa.

Autoridades distintas por clase de archivo — aquí estaba la trampa:

- **TEXT**: la envoltura `mirror/*.malrt1` contiene los bytes y su sha.
- **BINARY**: no tiene envoltura. La autoridad es `manifest/source_inventory.json`.
  Ahí salieron **3 más**: 2 binarios normalizados (`samples/Oberon/beNull.ob2`,
  `samples/Altium Designer/Sample Schematic Sheet.SchDoc`) y 1 ausente
  (`test/fixtures/Binary/linguist.gem`). Restaurados de upstream en el commit fijado,
  exigiendo `sha(upstream) == sha(inventory)` antes de escribir.
- **SYMLINK**: 3 entradas con sha nulo, deliberadamente no materializadas. Exentas.

Después del arreglo: `4281/4281` del inventario casan con disco (0 desajustes, 0
faltantes), `4258/4258` snapshot == envoltura, `4258/4258` `source_sha256` del manifest
== disco, y los 5 nivel 2 afectados volvieron a pasar. `tools/verify_corpus.py` comprueba
ahora el inventario completo en cada corrida para que un binario mutado no vuelva a
quedar invisible. El defecto también habría roto `--resume` (compara el sha de la fuente).
Radio y hashes: `evidence/snapshot_eol_repair_20261101/`.

El hueco del `.gem` está cerrado: `test/fixtures/Binary/linguist.gem` (3.072 bytes, sha256
`55f5f0b5…` == la del inventario) entra en git con `git add -f` — decisión explícita de la
host el 2026-11-01. No se tocó `vendor/source_snapshot/.gitignore` (línea 1: `*.gem`), que
sigue siendo el archivo del tarball y sigue siendo parte de la byte-exactitud del snapshot:
el `add -f` es la excepción, no el cambio de regla. Consecuencia: un clon fresco trae los
4.278 archivos regulares del inventario y `tools/verify_corpus.py` ya no reporta el `.gem`
como faltante.

## Avisos

CORPUS GENERADO ≠ USO ORGANICO.

Este corpus NO debe presentarse como evidencia de adopcion real de Malbolge.
No digas "Malbolge ahora tiene N thousand archivos de uso real" por causa de este
repo. Eso seria falso.

El reclamo aqui es:

```
LINGUIST_TRANSLATED_TO_MALBOLGE = DEMONSTRATED (para los archivos listados PASS)
```

y enfaticamente NO:

```
LINGUIST_RUNS_ON_MALBOLGE = NOT_CLAIMED
```

Malbolge contiene a Linguist. Linguist sigue sin contener Malbolge. :p

## Layout

```
vendor/source_snapshot/      arbol fijado de linguist (sin .git) + su LICENSE
vendor/malbolge_translator/  paquete traductor vendored (MIT), ver vendor/TRANSLATOR_SOURCE.txt
vendor/oracles/              mb_ref.c + olmstead_original.c, fijados por SHA-256
                             (procedencia y licencias: vendor/oracles/PROVENANCE.txt)
vendor/cat/                  cat_compact.mal del nivel 3, fijado por SHA-256
                             (procedencia y licencia: vendor/cat/PROVENANCE.txt)
mirror/                      artifacts NIVEL 1: <path>.malrt1 (envolturas de codec)
malbolge/                    artifacts NIVEL 2: <path>.mal (programas reales ejecutados)
manifest/                    source_inventory.json, translation_manifest.json
evidence/                    roundtrip.json, metrics.json, VERDICTS.md, hashes
evidence/<tema>_<UTC>/       packs de evidencia sellados, uno por corrida (nunca se
                             reutiliza una ruta: el gate se niega si ya existe)
tools/build_malboguistic.py  el build reproducible de un comando (nivel 1 + nivel 2)
tools/verify_corpus.py       re-verificacion canónica del corpus + inventario completo
tools/verify_level3.py       nivel 3: catalogo completo por stdin contra el Cat canónico
tools/verify_linguist_pipeline.py  dos rutas sobre el mismo linguist del snapshot:
                             --level 2 (ejecutado -> decodificado -> clasificado) y
                             --level 3 --include-non-text (catalogo entero por el Cat);
                             worker Ruby en tools/gate_adapters/
tools/extend_level2_zig.py   mueve la frontera del nivel 2 con el port a Zig
tools/engine_gate.py         gate de semantica multi-engine (adapters bajo tools/gate_adapters/)
tools/mbsearch_gate.py       gate del port a Zig (corpus / determinismo / diferencial)
tools/level1_determinism.py  gate de determinismo del nivel 1 (doble codificacion vs envoltura commiteada)
tools/zig_canonical/         mbc.zig (interprete canonico) y mbsearch.zig (busqueda nivel 2)
SOURCE_REPO.txt / SOURCE_COMMIT.txt   procedencia del snapshot
```

## Licencia

Build tools de MALBOGUISTIC: MIT (ver LICENSE).
El snapshot de Linguist conserva su propia licencia MIT (`vendor/source_snapshot/LICENSE`).
El traductor vendored es MIT (`vendor/malbolge_translator/LICENSE`).
Los oracles vendorizados: `mb_ref.c` es MIT (BolgeForge), `olmstead_original.c` es
dominio publico (Ben Olmstead, 1998). Pines y procedencia en `vendor/oracles/PROVENANCE.txt`.
Ver THIRD_PARTY_NOTICES.md.
