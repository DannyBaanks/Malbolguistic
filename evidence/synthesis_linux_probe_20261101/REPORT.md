# Sonda de síntesis en Linux — 2026-11-01

Reactiva el nivel 2 después de que el host Windows que lo produjo se perdiera
(2026-09-23). Corre la síntesis en Linux y la contrasta contra el corpus commiteado.

## Entorno

- Linux, 12 CPUs, Python 3.12.3, gcc (oráculos de `vendor/oracles/`).
- Traductor: copia vendored `vendor/malbolge_translator`, commit `16ca8828…`.
- Generador: `malbolge-generator 0.1.0`, instalado desde la copia local del monorepo
  `workspace/malbolge_toolkit` (git HEAD `6555c55691d6cb78f70b742336bd090ca3c174d6`),
  en un venv desechable. `max_search_depth=5`, `max_steps=5_000_000`.
- Vía `MalbolgeTranslator.translate_and_verify_roundtrip()`, igual que el build.

## 1. El paquete no existe en PyPI

`pip index versions malbolge-generator` → `No matching distribution found`. La
instrucción de `vendor/TRANSLATOR_SOURCE.txt` era inalcanzable; se corrigió con
anexo. Solo funciona `pip install <directorio local>`.

## 2. Costo real de síntesis: fijo-dominado, no lineal

`bench_depth5.log`, un proceso por archivo, timeout de 240 s:

| bytes fuente | segundos | s/byte | chars .mal | roundtrip |
|---|---|---|---|---|
| 4 | 5.71 | 1.43 | 2328 | PASS |
| 16 | 8.47 | 0.53 | 2775 | PASS |
| 32 | 8.67 | 0.27 | 3103 | PASS |
| 48 | 15.70 | 0.33 | 4097 | PASS |
| 64 | 15.36 | 0.24 | 3941 | PASS |
| 96 | 21.19 | 0.22 | 4778 | PASS |

Ajuste grueso: **~6 s fijos + ~0.16 s por byte** a profundidad 5. El "`~0.7 s` por
byte fuente" del README era una regla de dedo de la máquina Windows
(`[HISTORICAL]`), y como ley lineal sobrestima 4x a 96 B y subestima lo que costará
a 4 KB. 127 B quedó sin medir en esta corrida.

## 3. La síntesis NO es byte-reproducible

Mismo archivo (`samples/Text/foo.txt`, 4 B), misma profundidad, tres corridas
(`determinism_same_file_x3.jsonl`): **2068, 2146, 2334 caracteres**; las tres con
roundtrip PASS y las tres distintas entre sí y distintas del artefacto commiteado
(1851 chars, sha `ad787ee7…`). Las 6 entradas del benchmark tampoco reproducen ni un
solo `.mal` commiteado (`identical_to_committed: False` en 6/6).

Consecuencia de reclamo: `tools/build_malboguistic.py:564` fija
`"REPRODUCIBLE_BUILD": verdict(True)` — sin medirla, unconditional. Vale para el
nivel 1 (código determinista). Para el nivel 2 el estado honesto es
**semánticamente reproducible, no byte-reproducible**. Lo que estabiliza el corpus es
`--resume`, que reutiliza PASS previos en vez de resintetizar.

## 4. El ciclo sí cierra en Linux (el resultado útil)

Un `.mal` sintetizado aquí, ejecutado como archivo por los dos oráculos canónicos:

```
mb_ref      exit 0, 116 bytes, byte-exact vs mirror/samples/Markdown/minimal.md.malrt1
olmstead1998 exit 0, 116 bytes, byte-exact vs la misma envoltura
envoltura auto-consistente por SHA-256; payload decodificado = "_This_ is a **Markdown** readme."
```

Artefacto `sha256` en `fresh_synthesis.sha256`. Es decir: la cadena
fuente → Malbolge → ejecución canónica → decode → SHA-256 está operativa en este host
por primera vez desde la pérdida del disco Windows, y no depende del corpus histórico.

## 5. Trampa de la GUIA, reproducida en Linux

Reutilizar una instancia de `MalbolgeTranslator` para varios archivos en un mismo
proceso pasó de ~25 s esperados a >900 s sin terminar (run abortado). Un proceso por
archivo lo arregla. El aviso "traductor reutilizado degrada" era de Windows y sigue
vivo en Linux.

## 6. Techo de crecimiento (distribución medida del snapshot)

| tope por archivo | elegibles de 4258 | % |
|---|---|---|
| 128 B (hoy) | 379 | 8% |
| 256 B | 642 | 15% |
| 512 B | 1022 | 24% |
| 1024 B | 1605 | 37% |
| 2048 B | 2597 | 60% |
| 4096 B | 3160 | 74% |

Mediana del corpus: 1389 B; p90: 12263 B. Los ~10-90 min de la última columna son
**extrapolación** desde el modelo de la sección 2 divididido entre 12 CPUs: no se
midió síntesis >96 B, ni escalabilidad del pool, y la GUIA documenta estancamiento
con 7+ workers. `NOT_DEMONSTRATED` hasta medir.

## No demostrado

- Costo de síntesis para >128 B (y por tanto la viabilidad real de subir el tope).
- Que el generador local (con `shared_state_cache`, tocado 2026-09-05) sea el mismo
  comportamiento que generó el corpus 2026-09-04: los sha no casan, pero eso también
  lo explica el no-determinismo de la sección 3, así que queda abierto.
- Rendimiento con `--workers > 1` en este host.
