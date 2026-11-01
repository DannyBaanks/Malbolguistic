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
        ↓
traduccion reversa (decode + ejecucion)
        ↓
paridad SHA-256 contra los bytes originales
```

## Dos niveles, sin falsos

| Nivel | Alcance | Artifact | Reclamo |
|---|---|---|---|
| 1 — Codec mirror | **cada** archivo TEXT | `mirror/**/*.malrt1` | `CODEC_MIRROR_PARITY`: bytes fuente → MALRT1 → decode → SHA-256 identico |
| 2 — Malbolge real | archivos TEXT ≤ N bytes, bajo presupuesto de wall-clock | `malbolge/**/*.mal` | `FULL_EXECUTED_ROUNDTRIP`: fuente → Malbolge puro sintetizado → ejecucion canonica → decode → SHA-256 identico |

CODEC ROUNDTRIP ≠ FULL MALBOLGE E2E PARA ARCHIVOS ARBITRARiAMENTE GRANDES.
El costo de sintesis del nivel 2 **no es una ley por byte**. El "~0.7 s por byte
fuente" era de la maquina Windows de 2026-09-04 ⇒ `[HISTORICAL]`. Medido en Linux
(2026-11-01, profundidad 5, un proceso por archivo, `evidence/synthesis_linux_probe_20261101/`):
**~6 s fijos + ~0.16 s por byte**, o sea 5.7 s para 4 B y 21.2 s para 96 B. Mas alla de
128 B de fuente no esta medido por ese camino.
No pretendemos lo contrario: cada archivo no sintetizado se marca
`SKIPPED_TOO_LARGE` o `SKIPPED_BUDGET` en el manifest. Nada se oculta.

La sintesis del nivel 2 (generator Python) **no es byte-reproducible**: el mismo archivo,
tres corridas, produce programas distintos (todos con roundtrip PASS). Lo que estabiliza el
corpus es `--resume`, que reutiliza los PASS previos. El nivel 1 (codec) si es determinista,
y **el port a Zig (`tools/zig_canonical/mbsearch.zig`) tambien lo es**: misma configuracion,
misma huella (medido 3 objetivos x 5 repeticiones → huella unica). Ojo: determinista no es
"reproduce el corpus commiteado" — contra los `.mal` del repo son 0/379 byte-identicos.
Lo que el port si cubre es el corpus entero: 379 objetivos (cadenas de envoltura de 72 a 244
caracteres) en 63 s de pared, 70,7M de evaluaciones, 379/379 canonicos bajo `mbc`.

Una envoltura `.malrt1` es texto ASCII (`MALRT1:<base64>:<sha256>`), **no** un
programa Malbolge. Solo los archivos bajo `malbolge/` son Malbolge ejecutable.

## Ejecucion actual (commit fijado: befd3af35e70150b76458085208435eef9286bb3)

| Metrica | Valor |
|---|---|
| Archivos fuente (incl. 3 symlinks registrados) | 4,281 |
| Archivos de texto mirror-eados (nivel 1) | 4,258 / 4,258 (paridad codec, 0 desajustes) |
| Archivos binarios saltados | 20 |
| **Programas reales de Malbolge sintetizados + ejecutados (nivel 2)** | **379 / 379 elegibles (≤128 B), 0 fallos** |
| Bytes de texto originales | 31,647,823 |
| Bytes de envoltura mirror (`mirror/`) | 42,509,444 (×1.34) |
| Bytes de programa real de Malbolge (`malbolge/`) | 1,421,372 desde 21,902 bytes fuente |
| Ratio de expansion (nivel 2) | min ×41.7 · mediana ×67.8 · max ×462.8 |

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
| `tools/verify_corpus.py` — ejecutar **el archivo commiteado** | 379/379 en 9 ligas · inventario 4.281/4.281 · 1,57 s | `evidence/canonical_reverify_20261101T071314Z/` |
| `tools/engine_gate.py` — acuerdo semántico multi-motor, tier 2 con stdin real | `zig/bolg1` 382/383 (trunca a ~64 KiB) y toolkit Python 379/383 (0/4) ⇒ **DIVERGENTES**; los oráculos 383/383 | `evidence/engine_canonical_gate_20261101T080313ZZ/`, `…T082034ZZ/` |
| `tools/zig_canonical/mbc.zig` — motor canónico en Zig | **383/383** CANONICAL_AGREEMENT · 421.317.177 pasos/s frente a 412.592.903 del oráculo (ratio **1,02**) | `evidence/zig_canonical_engine_gate_20261101T154528ZZ/` |
| `tools/zig_canonical/mbsearch.zig` — port a Zig de la búsqueda del nivel 2 | corpus **379/379** canónico en **63 s** (70,7M de evaluaciones) · 12/12 y 30/30 byte-idéntico a la referencia con flujo RNG compartido | ver sección Zig |
| `CONTRACT_CAT_FED` — un solo `.mal` copiador con el archivo por stdin | **4.258/4.258** exactos bajo ambos oráculos, 31.647.823 bytes, 93,3 s | `evidence/corpus_cat_feasibility_20261101T074215Z/` |
| reparación del snapshot | 199 TEXT devueltos a los bytes de su propia envoltura + 3 BINARY desde upstream en `befd3af` (2 normalizados, 1 ausente) | `evidence/snapshot_eol_repair_20261101/` |

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
python3 tools/build_malboguistic.py --level1-only  # solo codec mirror, segundos
python3 tools/verify_corpus.py                     # re-verifica el nivel 2 SIN generator (oraculos C)
```

Opciones: `--e2e-max-bytes` (default 128), `--e2e-budget-seconds` (default 3600),
`--workers`, `--resume` (reusa resultados PASS previos para fuentes sin cambios).

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
salida exacta en cada motor, y acuerdo entre motores. Exit 0 ⇔ 379/379 limpios.

Ultima corrida (2026-11-01, Linux): **379/379 en las 9 ligas + inventario 4281/4281**,
1.57 s de pared → `evidence/canonical_reverify_20261101T071314Z/`.

Esto re-verifica **ejecución** y **integridad del snapshot**. La **síntesis** sigue
necesitando `malbolge-generator`, que no está en PyPI: se instala desde la copia local
del monorepo (`workspace/malbolge_toolkit`, `pip install <ese directorio>`). Sin él el
build reporta `SYNTHESIS_UNAVAILABLE` y no produce nivel 2 nuevo. Con él, el ciclo
fuente → `.mal` → oráculos canónicos → SHA-256 ya vuelve a cerrar en Linux
(`evidence/synthesis_linux_probe_20261101/`).

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
procedencia del corpus es heterogénea (`search_depth` = `null` en 354 entradas, `3` en
25). La canonicidad, en cambio, sí se reproduce: 379/379.

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

Un hueco que queda a la vista: `test/fixtures/Binary/linguist.gem` sigue **sin estar en
git**, porque el `.gitignore` que viene en el propio tarball de linguist
(`vendor/source_snapshot/.gitignore`, línea 1: `*.gem`) lo cubre. No se editó ese
`.gitignore` porque rompería la byte-exactitud del snapshot, y `git add -f` sobre esa
ruta es una decisión explícita que no se tomó. Consecuencia: este working tree tiene
4.278 archivos en disco (4.277 trackeados + el `.gem` ignorado) frente a 4.281 entradas
del inventario — las 3 de symlinks van exentas—, pero **un clon fresco sólo trae 4.277**
y `tools/verify_corpus.py` reporta el `.gem` como faltante (exit 1). Se resuelve recuperándolo de upstream en `befd3af` o
forzando el `add`, no silenciando el chequeo.

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
mirror/                      artifacts NIVEL 1: <path>.malrt1 (envolturas de codec)
malbolge/                    artifacts NIVEL 2: <path>.mal (programas reales ejecutados)
manifest/                    source_inventory.json, translation_manifest.json
evidence/                    roundtrip.json, metrics.json, VERDICTS.md, hashes
evidence/<tema>_<UTC>/       packs de evidencia sellados, uno por corrida (nunca se
                             reutiliza una ruta: el gate se niega si ya existe)
tools/build_malboguistic.py  el build reproducible de un comando (nivel 1 + nivel 2)
tools/verify_corpus.py       re-verificacion canónica del corpus + inventario completo
tools/engine_gate.py         gate de semantica multi-engine (adapters bajo tools/gate_adapters/)
tools/mbsearch_gate.py       gate del port a Zig (corpus / determinismo / diferencial)
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
