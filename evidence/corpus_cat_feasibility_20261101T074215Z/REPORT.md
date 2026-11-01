# ¿Puede el corpus completo de linguist existir como `.mal` real? Cat canónico vs conveyor

Fecha: 2026-11-01 (UTC). Pregunta de la host: *con BolgeForge y el nuevo Autobolge,
¿podemos hacer el corpus completo de linguistic en `.mal`?*

## Entorno y procedencia

| Elemento | Valor |
|---|---|
| Sistema | Linux 7.0.0-42-generic x86_64 GNU/Linux |
| gcc | 13.3.0 (Ubuntu 13.3.0-6ubuntu2~24.04.1) |
| Python | 3.12.3 |
| Oráculo estricto 1 | `vendor/oracles/mb_ref.c` SHA-256 `a8ce19c2dc93e36f8c9c24a271c4187d68f922b9455262c7199a009763fe3ad3` (BolgeForge `oracle/mb_ref.c`, HEAD `7b4fbacf2d7d58cdfadd83a48af17128c2c776f6`) |
| Oráculo independiente 2 | `vendor/oracles/olmstead_original.c` SHA-256 `05abd38e78b266050c5a5e8cc5b36584daa5bbdeb404bfb351de7ea6fa26b510` (mirror Olmstead 1998) |
| Programa evaluado | `BolgeForge/artifacts/cat_compact.mal`, 7,596 bytes, SHA-256 `dd8f9b106dd4b25cf190a2fa1cf7f1b03db08d2cb30d4144f8791d46a347079b` |
| Sintetizador evaluado | Autobolge `relational/synthesizer.py`, HEAD `dcfcd6fff0e40001ae686432d60a77434834e0b6` |
| Corpus | `vendor/source_snapshot` en el commit congelado `befd3af…`; 4,258 entradas `TEXT`, 31,647,823 bytes |

Los dos oráculos se recompilaron desde el `.c` pinneado (`gcc -O2 -std=c11`) antes de
cada ejecución; ningún resultado de este paquete depende de un binario heredado.

## Los dos contratos posibles (esto es el núcleo de la respuesta)

```text
CONTRACT_SELF_CONTAINED  un .mal por archivo; stdin vacío; stdout == envoltura del archivo
CONTRACT_CAT_FED         un solo .mal; el archivo entra por stdin; stdout == bytes del archivo
```

El nivel 2 actual de MALBOGUISTIC es `CONTRACT_SELF_CONTAINED` (los 379 artefactos se
verifican con stdin vacío contra su envoltura). `CONTRACT_CAT_FED` **no** incorpora los
bytes del archivo dentro del artefacto: el programa es un copiador universal.

## Comandos exactos (reproducibles desde este directorio)

```bash
B=$(mktemp -d)
gcc -O2 -std=c11 -o "$B/mb_ref" vendor/oracles/mb_ref.c
gcc -O2 -std=c11 -w -o "$B/olmstead" vendor/oracles/olmstead_original.c

MB_REF=$B/mb_ref OLMSTEAD=$B/olmstead \
  python3 evidence/<este-paquete>/cat_corpus_sweep.py \
    ../BolgeForge/artifacts/cat_compact.mal vendor/source_snapshot \
    manifest/source_inventory.json

AUTOBOLGE_ROOT=../Autobolge MB_REF=$B/mb_ref OLMSTEAD=$B/olmstead \
  python3 evidence/<este-paquete>/autobolge_gap_probe.py \
    vendor/source_snapshot manifest/source_inventory.json autobolge
```

`cat_corpus_sweep.py` sale 0 sólo si cada archivo medido es reproducido byte-exacto por
ambos motores. `autobolge_gap_probe.py` sale 0 si algún artefacto del conveyor es aceptado
por un loader canónico; en esta corrida su salida esperada es 1 (ninguno lo es).

## Resultados

### R1 — Cat canónico: el corpus completo, entero, byte-exacto, en 93 s

`summary.json`, `raw.jsonl` (4,258 registros):

| Medida | Valor |
|---|---|
| Archivos `TEXT` del catálogo | 4,258 |
| Archivos medidos | 4,258 |
| Bytes reproducidos | 31,647,823 (100 % del corpus texto) |
| `mb_ref` stdout idéntico | 4,258 / 4,258 |
| `olmstead` stdout idéntico | 4,258 / 4,258 |
| Fallos | 0 |
| Presupuesto de pasos `mb_ref` | 300,000,000 |
| Tiempo total | 93.3 s (≈ 340 kB/s por motor) |

El archivo más grande del corpus (`samples/Go/embedded.go`, 719,637 B) requiere levantar
el presupuesto: con 200 M pasos `mb_ref` aborta con `MAX_STEPS` tras 491,383 B; con 300 M
pasos halta y reproduce exacto. Consecuencia documentada: el presupuesto por defecto de
`mb_ref` (100 M) **no** cubre archivos grandes y el verificador debe escalarlo.

### R2 — Autobolge conveyor: techo estructural de 744 bytes de fuente

`autobolge_gap_analysis.json`, aritmética del layout `D_START=121`, `C_START=3315`
(hueco estéril de 3,194 celdas) aplicado a la envoltura real que el nivel 2 imprime
(`MALRT1:<base64>:<sha256>`), con coste por byte de salida 2 (`\n`) / 3 (imprimible) /
4 (`+`) celdas de datos:

| Medida | Valor |
|---|---|
| Envolturas con bytes no emisibles por la matriz de recetas | 0 / 4,258 |
| Archivos que caben en el hueco estéril | **1,277 / 4,258** (30.0 %) |
| Fuente máxima que cabe | 744 bytes |
| Bytes de fuente alcanzables | 372,815 (1.18 % del corpus) |
| Bytes de fuente inalcanzables | 31,275,008 |
| Nuevos respecto al tope actual de 128 B | 898 archivos |

### R3 — Los artefactos del conveyor no son canónicos

`autobolge_canonical_acceptance.json` y los tres `.mal` del paquete:

| Archivo sonda | chars envoltura | bytes programa | celdas ilegales | síntesis | `mb_ref` | `olmstead` |
|---|---:|---:|---:|---:|---|---|
| `ext/linguist/linguist.h` | 72 | 3,532 | 357 (10.1 %) | 0.11 ms | rc=1 `INVALID_OPCODE: cell 1` | rc=1 `invalid character in source file` |
| `samples/Hurl/capture-data.hurl` | 412 | 4,552 | 1,922 (42.2 %) | 0.30 ms | rc=1 `INVALID_OPCODE: cell 1` | rc=1 `invalid character in source file` |
| `samples/NMODL/fornetcon.mod` | 1,064 | 6,508 | 4,950 (76.0 %) | 0.86 ms | rc=1 `INVALID_OPCODE: cell 1` | rc=1 `invalid character in source file` |

Causa visible en el código: `synthesize_text` escribe valores de celda crudos en las
posiciones de datos y de arranque (`prog[1] = 93`, `prog[96] = 73`, `prog[76] = 120`, y
`data_bytes` en 33..126). El loader canónico exige que **toda** celda cargada esté en
`ji*p</vo`, así que el `.mal` renderizado es ilegales en bloque. El consumidor real del
conveyor es `zig/bolge.exe` a través de un volcado de celdas binario (`BOLG1` + enteros),
no un archivo de texto: la ruta `--out` es una proyección con pérdidas.

Autobolge lo declara por sí mismo: `experiments/indep_frontier_v1.py:172` — *"Anything
under the strict canonical loader (mb_ref): toolkit semantics only"* — y
`experiments/semantic_oracles.py:122` fija
`canonical_parity_zig_vs_mb_ref: "NOT_DEMONSTRATED: different semantics"`.

### R4 — Economía comparada

| Ruta | Coste medido | Cubre |
|---|---|---|
| Generador de haz actual (nivel 2 self-contained) | 42,621 s acumulados para los 379 artefactos del manifest; extrapolado al corpus texto ≈ 5.34 M s en un núcleo ≈ 61.9 días | 379 archivos (tope 128 B) |
| Conveyor Autobolge | 0.11–0.86 ms por programa | 0 archivos canónicos hoy; 1,277 si llegara a ser canónico |
| Cat canónico (`cat_compact.mal`) | 93.3 s para verificar los 4,258 | 4,258 archivos bajo `CONTRACT_CAT_FED` |

## Tabla de claims

| Claim | Estado |
|---|---|
| Un único programa Malbolge canónico reproduce byte-exacto los 4,258 archivos texto del corpus congelado, dado el archivo en stdin, verificado por dos motores independientes | **DEMONSTRATED** (`raw.jsonl`, `summary.json`, exit 0) |
| El hueco estéril de 3,194 celdas limita el conveyor a envolturas de ≤ ~1,064 bytes imprimibles (744 bytes de fuente) y por tanto a 1,277 de 4,258 archivos | **DEMONSTRATED** (aritmética verificada contra las recetas reales del sintetizador) |
| Los artefactos del conveyor Autobolge son aceptados por un loader canónico | **REFUTED** (3/3 rechazados por `mb_ref` y por Olmstead en la celda 1) |
| El corpus completo existe como un `.mal` **autocontenido** por archivo | **NOT_DEMONSTRATED** |
| El conveyor puede re-aimarse a un hueco mayor y seguir siendo canónico | **NOT_DEMONSTRATED** (no se intentó) |
| `MASS_TRANSLATION_REAL_MALBOLGE` sube de 379 por este paquete | **NO**: sigue 379; aquí no se añadió ningún artefacto de nivel 2 |

## Hallazgo colateral en repo hermano (sin acción en este paquete)

`BolgeForge` pinnear `80b9dca9af6427135da41ffe2131fad0b5c6ffc1b4b92c8d832d5ebe1911afb9`
como el Cat publicado en `docs/CLAIMS.md:26-27`,
`docs/evidence/2026-10-25-cat-k19-frontier/REPORT.md:179`, `tools/build_compact_cat.py:20`
y `tools/cat_k19.py:5`, pero el artefacto commiteado en HEAD `7b4fbac` es
`dd8f9b106dd4b25cf190a2fa1cf7f1b03db08d2cb30d4144f8791d46a347079b` (7,596 bytes ambos,
difieren en 4,658 posiciones; `80b9dca9…` es `out_k19_candidate.mal` dentro de su propio
paquete de evidencia). `python3 tools/build_compact_cat.py --check` responde
`PASS … byte-exact rebuild`, así que el **artefacto** es la salida determinista y el hash de
la documentación está obsoleto; `--check` reporta además 7,080 ops de preámbulo frente a
los 7,056 documentados. Consecuencia operativa: pinnear por reconstrucción determinista,
no por el hash del doc. No se modificó BolgeForge.

## Alcance y lo que NO se afirma

- Nada del corpus, manifiesto, nivel 1 ni nivel 2 fue creado, borrado o modificado aquí.
- La verificación Cat demuestra la **relación de eco** de `cat_compact.mal`, no que cada
  archivo de linguist "haya sido traducido a Malbolge". Presentar el resultado de R1 como
  4,258 programas propios sería falso.
- Los 3 probes del conveyor son una muestra (mínimo, mediana y máximo de los que caben);
  la aritmética de R2 es la que cubre los 4,258 archivos.
- `git status` de Malbolguistic muestra este paquete como novedad sin commitear; el
  commit queda pendiente de aprobación de la host.
