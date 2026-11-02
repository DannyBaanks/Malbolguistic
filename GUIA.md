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
| `py tools/build_malboguistic.py --level1-only` | inventario + espejo codec + adopción del corpus commiteado (no resintetiza nada) | ~1 s medido (1,2 s) |
| `py tools/build_malboguistic.py --e2e-budget-seconds 300` | espejo + 5 min de Malbolge real | ~6 min |
| `py tools/build_malboguistic.py --resume` | continúa donde quedó reusando `evidence/level2_state.json` (estado **local al host**, está en `.gitignore`); lo que protege el corpus en cualquier clon es la adopción del manifest, que va activada por defecto | variable |
| `py tools/build_malboguistic.py --resume --serial --search-depth 3` | modo rescate, sin pool; así se terminaron los últimos archivos grandes | ~1-2 min/archivo |
| `py tools/build_malboguistic.py --e2e-max-bytes 256` | **NO VIABLE en este host**: sube el tope, pero el generador Python no cabe (medido: >5,5 GB ya a 97 B de fuente). Subir el tope del nivel 2 solo tiene sentido por el port a Zig | la guarda lo mata en ~17 s |
| `python3 tools/verify_corpus.py` | **re-verifica los 1.605 `.mal` ejecutando el archivo** bajo mb_ref + Olmstead 1998; no necesita `malbolge-generator` | ~6 s |
| `python3 tools/verify_level3.py` | nivel 3: pasa los 4.258 textos del catálogo por stdin al Cat canónico (`vendor/cat/cat_compact.mal`) bajo ambos oráculos; vende el pin del Cat y de los motores | ~82 s |
| `python3 tools/verify_linguist_pipeline.py` | barrido nivel 2 → oráculos → decode → **clasificación con el linguist del snapshot** (6 variantes por archivo, 9.630 blobs); construye el runtime Ruby en `/tmp`, nunca en el repo | 17,5 s (7,4 s ejecución + 10,1 s clasificación) en 1.605 archivos; +7,4 s si regenera la DB |
| `python3 tools/verify_linguist_pipeline.py --level 3 --include-non-text` | el mismo barrido sobre **el catálogo entero** (4.278 archivos, 21.392 blobs) por la ruta del Cat canónico: los bytes salen del `cat_compact.mal`, no del artefacto | 2 min 24 s (109,8 s ejecución + 24,1 s clasificación); sin `--include-non-text` el scope son los 4.258 `TEXT` y el tiempo no está medido aparte |
| `python3 tools/extend_level2_zig.py --evidence evidence/… --cap-bytes 1024 --depth 5 --apply-manifest` | sube la frontera del nivel 2 con el port a Zig: sintetiza, verifica con ambos oráculos y solo entonces escribe `malbolge/` + manifest. Sin `--apply-manifest` no toca el repo | ~15 min para 1.226 archivos |
| `python3 tools/mbsearch_gate.py --mode all --limit 12 --depth 5 --site-packages DIR` | gate del port a Zig (`tools/zig_canonical/mbsearch.zig`): canonicidad con `mbc`, determinismo e igualdad textual con la referencia | ~1 min |
| `python3 tools/mbsearch_gate.py --mode corpus --limit 0 --depth 5` | los 379 objetivos del manifest con el port en Zig (construye `mbsearch`+`mbc` él solo) | ~1 min |
| `python3 tools/level1_determinism.py --evidence evidence/level1_determinism_<UTC>` | gate de determinismo del nivel 1: codifica dos veces cada fuente TEXT y exige igualdad mutua **y** con el `mirror/*.malrt1` commiteado; se niega a escribir sobre una carpeta existente | ~0,5 s para 4.258 archivos |

Salida exitosa termina con `[done] manifest_sha256=...` y exit 0.

## Cómo leer la salida

| Estado | Significado | Qué hacer |
|---|---|---|
| `PASS` | sintetizado + ejecutado + decodificado + SHA idéntico | nada |
| `FAILED` | la síntesis/ejecución falló para ese archivo | míralo en `manifest/translation_manifest.json` → `malbolge.error`; el build da exit 1 |
| `SKIPPED_TOO_LARGE` | supera `--e2e-max-bytes` **y** no tiene artefacto adoptado del manifest | normal: en este host el generador Python pide **gigabytes por archivo** (medido: >3 GB a 96 B, >5,5 GB a 97 B). Un PASS por encima del tope es del port a Zig (`lineage: zig_port`), no del generator |
| `SKIPPED_BUDGET` | cabía pero se agotó el tiempo | relanza con más `--e2e-budget-seconds` y `--resume` |
| `mismatches=0` en `[level1]` | el espejo codec es 100% íntegro | nada |

## Trampas

- **En Linux escribe `python3`.** El guardián que mataba `python` con exit 2718 era
  de la máquina Windows anterior (perdida 2026-09-23); ahí había que usar `py`. En
  este host `python` y `python3` funcionan. Los comandos `py …` de esta guía son
  `[HISTORICAL]`.
- **`ORACLE_PIN_MISMATCH` / `CAT_PIN_MISMATCH` son intencionales.** `tools/verify_corpus.py`
  fija los dos motores y `tools/verify_level3.py` fija además el Cat
  (`vendor/cat/cat_compact.mal` = `dd8f9b10…`). Si no casan, el verificador se niega a
  producir evidencia: alguien cambió un interpretador o el programa, y hay que
  re-validar el pin y su `PROVENANCE.txt` antes de tocar nada.
- **Un directorio de evidencia no se reusa.** Los verificadores (`verify_corpus.py`,
  `verify_level3.py`, `verify_linguist_pipeline.py`) se
  niegan a escribir sobre `evidence/<tipo>_<UTC>` existente. Deja el viejo y corre con
  fecha nueva.
- **`verify_linguist_pipeline.py` se niega a sellar si huele a ruta del host.** Antes de
  escribir `SHA256SUMS.txt` recorre el pack buscando el prefijo absoluto del repo y del home
  (`jobs.jsonl` viaja tokenizado con `{SNAPSHOT}`/`{STAGE}`/`{REPO}`…). Salta
  «El pack NO se sella: hay rutas absolutas del host en la evidencia» ⇒ el repo es público,
  así que eso es un fallo igual que un `FAIL`: corrige la tokenización, no borres el archivo.
  Si salta por el código de la propia herramienta (que también se copia al pack), el tripwire
  va demasiado ancho: estrecha los patrones, no los amplíes.
- **El 379/379 PASS histórico ejecutaba opcodes en memoria, no el archivo.** Por eso
  existe `verify_corpus.py`. Al citar el nivel 2, di qué método usaste. Hoy el número
  del archivo ejecutado es **1.605/1.605** (`evidence/canonical_reverify_20261101T223703Z/`).
- **La concordancia de clasificación 1.605/1.605 NO es una prueba de fidelidad.** Es el
  control del banco de pruebas: `from_mal` se clasifica en la misma ruta lógica y con los
  mismos bytes que `source`, así que el acuerdo está *implicado* por la paridad byte a
  byte. Al citar el barrido de linguist, la evidencia de fidelidad es el eslabón
  `decoded_matches_snapshot`; la clasificación sólo dice que el harness no se rompió.
- **linguist no conoce Malbolge: 0/1.605 en nivel 2 y 0/4.278 en nivel 3.** `languages.yml`
  del snapshot (9.7.0) no tiene ninguna entrada Malbolge, así que ningún resultado de
  `tools/verify_linguist_pipeline.py` autoriza a decir que "linguist reconoce los `.mal`".
  En nivel 3 el veredicto se mide además sobre el propio `cat_compact.mal` (job `@cat_program`
  del pack): pasa por el `Classifier` y devuelve `NIL`. Dato aparte y más incómodo: la
  envoltura MALRT1 sin decodificar pasa por el archivo original en 1.244 de 1.605 casos,
  porque linguist decide por la ruta primero.
- **`--level 3` pide otro presupuesto que `--level 2`.** Si no pasas `--max-steps`, la
  herramienta arranca en **1.200.000.000** de pasos (nivel 2: 100.000.000) y eleva el timeout
  por proceso a **600 s**. Son techo de seguridad, no necesidad medida: el Cat tarda muchísimo
  más pasos que un artefacto autocontenido porque recorre la cinta por cada byte de stdin, y
  el pack no registra los pasos consumidos, así que no se puede bajar el techo "a ver si cabe"
  —si mb_ref se agota imprime `MAX_STEPS: N (HALT not reached)` y sale 2, y el pack sale con
  fallos. Margen real medido sobre los 4.278 archivos: **12,62 ms de media** y **1.383,8 ms**
  en el peor (`test/fixtures/Binary/octocat.ai`, 1.041.378 B), los dos motores llegan a `HALT`.
- **En nivel 3 la columna que se cita es `coincide con idioma`, no `from_cat`.** Da
  4.278/4.278, pero 43 archivos no tienen idioma en ninguno de los dos lados y en las 20
  `BINARY` sólo 3 lo tienen: 20/20 de "coincidencia" binaria son 17 `NIL == NIL`, que no
  dice nada. El control que sí es independiente de la paridad byte a byte es `prefix64`
  (64 bytes, misma ruta): 211/4.278 cambian de veredicto — 182 a otro idioma, 29 a `NIL`.
- **La etiqueta `BINARY` del inventario es regla nuestra, no veredicto de linguist.**
  `build_malboguistic.py` llama `BINARY` a "contiene NUL" o "no es UTF-8 válido". De los 20
  archivos así marcados, linguist confirma `binary? == true` en **14** (todos `bail_out`) y
  en los otros **6** no: 3 reciben idioma y 3 caen al `Classifier` y devuelven `NIL` — entre
  ellos los fixtures UTF-16, que llevan NULs porque la codificación los pide. No uses la
  columna `classification` como si la hubiera producido el clasificador.
- **El barrido de linguist necesita Ruby y cae cerrado si faltan gemas.** Pide
  `charlock_holmes` y `mini_mime` (`gem install --user-install charlock_holmes mini_mime`)
  y **no instala nada por su cuenta**. El runtime (`linguist.so` + `samples_data.rb`) se
  construye en `--workdir` (`/tmp/malboguidstic_linguist_rt` por defecto), nunca dentro del
  repo: el snapshot sigue byte-exacto, y `LINGUIST_PROVENANCE_MISMATCH` aborta si alguno de
  los 12 archivos críticos del clasificador driftan respecto a `manifest/source_inventory.json`.
- **`linguist.rb` se carga con UNA línea menos, a propósito.** El worker quita
  `require 'linguist/repository'` (única arrastradora de la gema nativa `rugged`, usada sólo
  para repositorios Git) y aborta si el archivo no pierde exactamente esa línea. Si algún
  día ves más de una línea caída, el worker está roto o alguien tocó el snapshot.
- **`malbolge-generator` no está en el `python3` del sistema.** No está en PyPI
  (medido 2026-11-01), así que sólo existe si lo instalas desde una copia local del
  toolkit en un venv. Sin él el build de nivel 2 reporta `SYNTHESIS_UNAVAILABLE`;
  la re-verificación canónica no lo necesita.
- **`--e2e-max-bytes` alto = GIGAS, no horas.** El muro del nivel 2 en este host es la
  memoria, y la ley de tiempo a solas engaña. Muro medido a `depth 5`: **~6 s fijos +
  ~0,16 s por byte** (5,7 s para 4 B, 21,2 s para 96 B; `evidence/synthesis_linux_probe_20261101/`).
  Memoria medida el mismo día sobre esas mismas llamadas: **>3 GB para 96 B, >5,5 GB para
  97 B, ~1,2-1,4 GB hasta para un control de 2 B**
  (`evidence/level2_cap_probe_20261101T215239ZZ/`). Conclusión práctica: no subas el tope
  esperando que "tarda más y ya"; el port a Zig hace el mismo trabajo en 1,11 ms por
  caracter de envoltura con 165 MB de techo. El "~90 s por archivo de 128 B" y el
  "~0,7 s por byte" viejos eran de la máquina Windows ⇒ `[HISTORICAL]`.
- **`--workers` alto se estanca en esta máquina.** Medido: con 7 workers la
  contención dispara el watchdog (stalls de 900 s); con 3 workers va bien.
  Cada tarea usa un proceso fresco (`max_tasks_per_child=1`): un traductor
  reutilizado entre tareas degrada el rendimiento (medido: mismo archivo
  42 s solo vs >900 s en worker reutilizado).
- **Si el pool se sigue portando raro, usa `--serial`.** Fue el modo que cerró
  el corpus: 379/379 PASS con 0 fallos.
- **`evidence/level2_state.json` solo sirve en el host que lo escribió** (está en
  `.gitignore`). Perderlo no pierde el corpus: el build adopta los PASS del manifest
  commiteado, que sí viaja en git.
- **Los 3 symlinks del tarball no existen en disco.** Están registrados en
  `manifest/source_inventory.json` con su destino. No los "arregles".
- **Exit 1 con `mismatches>0` es un fallo real**, no un aviso. Investiga antes
  de relanzar.
- **El mirror NO cubre binarios.** `mirror/*.malrt1` solo existe para texto. Para
  `BINARY` la autoridad es `manifest/source_inventory.json` (ahí están los sha reales);
  un binario con EOL normalizado es invisible para el mirror. `verify_corpus.py`
  revisa las 4281 entradas del inventario y sale 1 si alguna desalinea.
- **No resintetices bytes sellados.** El generador no es byte-reproducible (mismo
  archivo, tres corridas, tres programas distintos; `evidence/synthesis_linux_probe_20261101/`).
  El build ya no pica ese verbo: arrastra los PASS del manifest commiteado cuya
  huella sigue casando en disco (`[adopt] committed level-2 artifacts carried over: N`).
  `--no-adopt` es la única vía que sustituye artefactos sellados, y no hay razón
  operativa para usarla. Medido: `--level1-only` reescribió el manifest
  **byte-idéntico** (`54c4b704…`), 1.605 adoptados y 0 resintetizados en 1,2 s.
- **`malbolge/` es de dos linajes, y eso es deliberado.** 379 archivos los hizo el
  generador Python (≤128 B, sin clave `lineage` en el manifest) y 1.226 los hizo el port
  a Zig hasta 1.022 B (`"lineage": "zig_port"`, con `synthesizer_binary_sha256`). El port
  **no** reproduce los `.mal` del generator (0/379), así que una pasada nueva por el
  port no "arregla" los viejos: son árboles distintos con la misma semántica. Si algún
  día hay que separarlos, se separan por la clave `lineage`, no por tamaño de archivo.
- **Hay DOS clones de este repo en el disco**: `Malbolguistic` y `MALBOGUISTIC` (el
  grande), con history compartido pero **worktrees divergentes y cambios sin commitear**
  (el grande trae `vendor/malbolge_translator/backend.py` y evidencia regenerada). El
  blob corrupto de EOL es común a ambos. Asegúrate en cuál estás antes de escribir.
- **El snapshot se trae su propio `.gitignore` y te escondió un archivo.**
  `vendor/source_snapshot/.gitignore` línea 1 es `*.gem` (viene del tarball de
  linguist), así que `test/fixtures/Binary/linguist.gem` estuvo fuera de git: un clon
  fresco no reproducía el snapshot y `verify_corpus.py` lo reportaba como `missing`.
  Desde el 2026-11-01 está dentro con `git add -f` (decisión de la host). Un `.gitignore`
  en la raíz no lo arregla (el más profundo gana). **No edites el `.gitignore`
  vendorizado**: rompería la byte-exactitud del snapshot; la excepción se fuerza por
  ruta, no cambiando la regla.
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
