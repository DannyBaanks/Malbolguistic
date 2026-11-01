# GUIA — cómo operar MALBOGUISTIC

## El comando que buscas

```
py tools/build_malboguistic.py
```

Eso reconstruye todo: inventario → espejo codec (4.258 archivos) → síntesis
Malbolge real con presupuesto → manifests → métricas → VERDICTS.

## Regla de oro

**Un `.malrt1` NO es un programa Malbolge.** Es el sobre MALRT1 (ASCII) que
garantiza paridad de bytes por códec. Los programas Malbolge de verdad son
solo los de `malbolge/`, y cada uno PASÓ ejecución + decode + SHA-256.
Nunca presentes un `.malrt1` como "código Malbolge".

## Comandos

| Comando | Qué hace | Tiempo típico |
|---|---|---|
| `py tools/build_malboguistic.py --level1-only` | inventario + espejo codec | ~1 min |
| `py tools/build_malboguistic.py --e2e-budget-seconds 300` | espejo + 5 min de Malbolge real | ~6 min |
| `py tools/build_malboguistic.py --resume` | continúa donde quedó (reusa los PASS previos; verificado en producción) | variable |
| `py tools/build_malboguistic.py --resume --serial --search-depth 3` | modo rescate, sin pool; así se terminaron los últimos archivos grandes | ~1-2 min/archivo |
| `py tools/build_malboguistic.py --e2e-max-bytes 256` | NO PROBADO: sube el tope por archivo (teórico ~3 min por archivo de 256 B) | ojo |
| `python3 tools/verify_corpus.py` | **re-verifica los 379 `.mal` ejecutando el archivo** bajo mb_ref + Olmstead 1998; no necesita `malbolge-generator` | ~1.4 s |
| `python3 tools/mbsearch_gate.py --mode all --limit 12 --depth 5 --site-packages DIR` | gate del port a Zig (`tools/zig_canonical/mbsearch.zig`): canonicidad con `mbc`, determinismo e igualdad textual con la referencia | ~1 min |
| `python3 tools/mbsearch_gate.py --mode corpus --limit 0 --depth 5` | los 379 objetivos del manifest con el port en Zig (construye `mbsearch`+`mbc` él solo) | ~1 min |

Salida exitosa termina con `[done] manifest_sha256=...` y exit 0.

## Cómo leer la salida

| Estado | Significado | Qué hacer |
|---|---|---|
| `PASS` | sintetizado + ejecutado + decodificado + SHA idéntico | nada |
| `FAILED` | la síntesis/ejecución falló para ese archivo | míralo en `manifest/translation_manifest.json` → `malbolge.error`; el build da exit 1 |
| `SKIPPED_TOO_LARGE` | supera `--e2e-max-bytes` | normal: la síntesis cuesta ~0.7 s/BYTE fuente en esta máquina |
| `SKIPPED_BUDGET` | cabía pero se agotó el tiempo | relanza con más `--e2e-budget-seconds` y `--resume` |
| `mismatches=0` en `[level1]` | el espejo codec es 100% íntegro | nada |

## Trampas

- **En Linux escribe `python3`.** El guardián que mataba `python` con exit 2718 era
  de la máquina Windows anterior (perdida 2026-09-23); ahí había que usar `py`. En
  este host `python` y `python3` funcionan. Los comandos `py …` de esta guía son
  `[HISTORICAL]`.
- **`ORACLE_PIN_MISMATCH` es intencional.** `tools/verify_corpus.py` fija los dos
  motores por SHA-256. Si no casan, el verificador se niega a producir evidencia:
  alguien cambió un interpretador y hay que re-validar el pin y `PROVENANCE.txt`.
- **Un directorio de evidencia no se reusa.** `verify_corpus.py` se niega a escribir
  sobre `evidence/canonical_reverify_*` existente. Deja el viejo y corre con fecha nueva.
- **El 379/379 PASS histórico ejecutaba opcodes en memoria, no el archivo.** Por eso
  existe `verify_corpus.py`. Al citar el nivel 2, di qué método usaste.
- **`malbolge-generator` no está en el `python3` del sistema.** No está en PyPI
  (medido 2026-11-01), así que sólo existe si lo instalas desde una copia local del
  toolkit en un venv. Sin él el build de nivel 2 reporta `SYNTHESIS_UNAVAILABLE`;
  la re-verificación canónica no lo necesita.
- **`--e2e-max-bytes` alto = horas.** El coste **no es lineal, es fijo-dominado**:
  medido en Linux a `depth 5` son **~6 s fijos + ~0,16 s por byte** (5,7 s para 4 B y
  21,2 s para 96 B; 128 B sin medir) — `evidence/synthesis_linux_probe_20261101/`. El
  "~90 s por archivo de 128 B" y el "~0,7 s por byte" viejos eran de la máquina Windows
  ⇒ `[HISTORICAL]`. Subir el tope multiplica objetivos, no segundos por byte.
- **`--workers` alto se estanca en esta máquina.** Medido: con 7 workers la
  contención dispara el watchdog (stalls de 900 s); con 3 workers va bien.
  Cada tarea usa un proceso fresco (`max_tasks_per_child=1`): un traductor
  reutilizado entre tareas degrada el rendimiento (medido: mismo archivo
  42 s solo vs >900 s en worker reutilizado).
- **Si el pool se sigue portando raro, usa `--serial`.** Fue el modo que cerró
  el corpus: 379/379 PASS con 0 fallos.
- **Si borras `evidence/level2_state.json`, pierdes el resume.** No lo borres
  salvo que quieras re-sintetizar todo.
- **Los 3 symlinks del tarball no existen en disco.** Están registrados en
  `manifest/source_inventory.json` con su destino. No los "arregles".
- **Exit 1 con `mismatches>0` es un fallo real**, no un aviso. Investiga antes
  de relanzar.
- **El mirror NO cubre binarios.** `mirror/*.malrt1` solo existe para texto. Para
  `BINARY` la autoridad es `manifest/source_inventory.json` (ahí están los sha reales);
  un binario con EOL normalizado es invisible para el mirror. `verify_corpus.py`
  revisa las 4281 entradas del inventario y sale 1 si alguna desalinea.
- **No resintetices sin `--resume`.** El generador no es byte-reproducible (mismo
  archivo, tres corridas, tres programas distintos). Sin `--resume` el build reemplaza
  los 379 `.mal` por otros igual de válidos pero distintos, y rompes los sha del
  manifest. Medido en `evidence/synthesis_linux_probe_20261101/`.
- **Hay DOS clones de este repo en el disco**: `Malbolguistic` y `MALBOGUISTIC` (el
  grande), con history compartido pero **worktrees divergentes y cambios sin commitear**
  (el grande trae `vendor/malbolge_translator/backend.py` y evidencia regenerada). El
  blob corrupto de EOL es común a ambos. Asegúrate en cuál estás antes de escribir.
- **El snapshot se trae su propio `.gitignore` y te esconde un archivo.**
  `vendor/source_snapshot/.gitignore` línea 1 es `*.gem` (viene del tarball de
  linguist), así que `test/fixtures/Binary/linguist.gem` **no está en git**: 4278
  archivos en disco vs 4277 trackeados. Un clon fresco no reproduce el snapshot
  completo y `verify_corpus.py` lo reportará como `missing`. Un `.gitignore` en la
  raíz NO lo arregla (el más profundo gana); se resuelve con `git add -f` sobre esa
  ruta. No edites el `.gitignore` vendorizado: rompería la byte-exactitud del snapshot.
- **`py tools/build_malboguistic.py` es `[HISTORICAL]`**: así se construyó el corpus,
  en Windows. En Linux usa `python3`.
- **El port en Zig no te devuelve los `.mal` commiteados.** Mismo sobre, programa
  distinto: 0/379 coincidencias byte a byte, y la toolkit actual tampoco las devuelve.
  El port sí reproduce el **texto** de la referencia cuando ambos lados comparten flujo
  aleatorio (`--mode differential`), y eso es lo que prueba que es la misma búsqueda. El
  `mbsearch` usa SplitMix64 porque el sembrado MT19937 de `random.Random(42)` no es
  recreable con las inicializaciones estándar.
- **`--mode differential` y `--mode all` exigen `--site-packages`** con el paquete
  `malbolge` instalable; sin eso el gate se niega (los modos `corpus` y `determinism`
  no necesitan Python, sólo Zig 0.16).
- **`mbsearch_gate.py` se niega a reusar un directorio de evidencia.** Si ves
  `REFUSING to reuse evidence path`, no borres el viejo: corre con fecha nueva.
  `--limit 0` significa "todos los objetivos del manifest".
