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
El costo de sintesis del nivel 2 en esta cadena de herramientas es aproximadamente **~0.7 s por byte fuente**
(medido en este host), asi que un `languages.yml` de 130 KB tomaria ~25 horas.
No pretendemos lo contrario: cada archivo no sintetizado se marca
`SKIPPED_TOO_LARGE` o `SKIPPED_BUDGET` en el manifest. Nada se oculta.

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
`evidence/VERDICTS.md` (tabla de claims), y `manifest/translation_manifest.json`
(una entrada por archivo de texto; su SHA-256 es `evidence/manifest_sha256.txt`).

## Reproducir

Requiere Python ≥ 3.10 y el paquete `malbolge-generator` (importable como
`malbolge`, MIT). En este equipo: `py` (bare `python` esta shimmed).

```
py tools/build_malboguistic.py                # completo: nivel 1 + nivel 2 (default 1 h de budget)
py tools/build_malboguistic.py --level1-only  # solo codec mirror, segundos
```

Opciones: `--e2e-max-bytes` (default 128), `--e2e-budget-seconds` (default 3600),
`--workers`, `--resume` (reusa resultados PASS previos para fuentes sin cambios).

Exit code 0 ⇔ cero desajustes de codec Y cero ejecuciones fallidas.

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
mirror/                      artifacts NIVEL 1: <path>.malrt1 (envolturas de codec)
malbolge/                    artifacts NIVEL 2: <path>.mal (programas reales ejecutados)
manifest/                    source_inventory.json, translation_manifest.json
evidence/                    roundtrip.json, metrics.json, VERDICTS.md, hashes
tools/build_malboguistic.py  el build reproducible de un comando
SOURCE_REPO.txt / SOURCE_COMMIT.txt   procedencia del snapshot
```

## Licencia

Build tools de MALBOGUISTIC: MIT (ver LICENSE).
El snapshot de Linguist conserva su propia licencia MIT (`vendor/source_snapshot/LICENSE`).
El traductor vendored es MIT (`vendor/malbolge_translator/LICENSE`).
Ver THIRD_PARTY_NOTICES.md.
