# Reparación de EOL en `vendor/source_snapshot/` — 2026-11-01

## Hallazgo

`mirror/*.malrt1` codifica los bytes reales del snapshot fijado de linguist
(`befd3af35e70150b76458085208435eef9286bb3`). Al comparar cada envoltura contra el
archivo en `vendor/source_snapshot/`:

```
envelopes=4258 checked=4258 MISMATCH=199   (los 199: CRLF convertido a LF)
```

Causa: el snapshot se commiteó desde una máquina Windows **antes** de existir
`.gitattributes` (`* -text`, añadido en `ad03146`), así que Git normalizó CRLF→LF
dentro del blob. La normalización está horneada en el historial, no es un estado del
worktree.

## Consecuencia que tenía tapada el repo

- `--resume` compara `sha256_bytes(raw)` contra el sha registrado; con el snapshot
  corrupto habría abortado la síntesis de los 199 archivos con
  `source sha changed between inventory and synthesis`.
- 5 de los 199 eran artefactos nivel 2, por lo que `build_malboguistic.py` ya no
  podía reproducir el "379/379" que declara `evidence/VERDICTS.md`.

## Reparación

Método: para cada envoltura, decodificar su base64 y exigir
`sha256(decoded) == sha_envoltura` antes de escribir. Con esa guarda, sobreescribir
`vendor/source_snapshot/<path>` con `decoded`. Sin tocar ningún `.mal`, ningún
`.malrt1`, ni ningún manifest.

Radio: **199 archivos**, todos bajo `vendor/source_snapshot/`, todos trackeados, todos
`M` en `git diff --name-status` (0 altos, 0 añadidos, 0 sueltos).

| métrica | valor |
|---|---|
| archivos reescritos | 199 |
| bytes antes / después | 2,599,003 → 2,675,573 |
| bytes añadidos | 76,570 (pares CRLF restaurados; todos los deltas > 0) |
| envolturas no auto-consistentes | 0 (ninguna escritura fue rechazada) |

## Verificación posterior

| control | resultado |
|---|---|
| snapshot vs envoltura, los 4258 | `checked=4258 mismatch=0` |
| `manifest.source_sha256` vs disco | `4258/4258` coinciden (registro independiente, generado el 2026-09-04) |
| `manifest.mirror.envelope_sha256` vs disco | `4258/4258` coinciden |
| nivel 2 re-verificado con oráculo C | `artifacts=379 verified=379 failed=0` |
| muestreo directo a upstream (4 archivos) | sha idéntico al de la envoltura |

Upstream consultado en el commit fijado, vía `raw.githubusercontent.com`:

| archivo | upstream | envoltura | snapshot antes |
|---|---|---|---|
| `samples/JSON/pack.mcmeta` | 117 B CRLF `4ce0cd55e260` | `4ce0cd55e260` | 112 B LF |
| `samples/C++/render_adapter.cpp` | 45 B CRLF `212842a570e1` | `212842a570e1` | 39 B LF |
| `samples/Agda/NatCat.agda` | 1418 B CRLF `21369881ca09` | `21369881ca09` | 1379 B LF |
| `samples/Assembly/A8514.i` | 7782 B CRLF `dcaa1f773820` | `dcaa1f773820` | 7552 B LF |

## Reproducible con

```
python3 tools/verify_corpus.py        # cadena completa, incluye snapshot == envoltura
```

## No demostrado

- Que los otros 199-5 archivos nivel 1 necesiten algo más que este byte-fix: no se
  re-sintetizó ninguno, y no hacía falta.
- Que la normalización haya afectado a los 20 archivos binarios excluidos: no tienen
  envoltura, así que quedan `NOT_DEMONSTRATED` por ausencia de registro con el que
  comparar.
