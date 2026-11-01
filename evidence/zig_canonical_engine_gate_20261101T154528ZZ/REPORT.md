# Motor canónico en Zig: `mbc` pasa el gate de dos tiers e iguala al oráculo en velocidad

Paquete: `evidence/zig_canonical_engine_gate_20261101T154528ZZ/`
Gate: 2026-11-01T15:45:28Z (31.4 s, 383 casos) · Throughput: 2026-11-01T15:52Z
Repo: Malbolguistic, HEAD `f6f980383d90aeac482bd064c3e44ddf60265f25` (fuente sin commitear)

## Pregunta

El gate anterior (`engine_canonical_gate_20261101T082034ZZ`) refutó a los dos motores
candidatos en el tier 2: `zig/bolge.exe` trunca la entrada a ~64 KiB y el intérprete
Python del toolkit no implementa el envoltorio Classic módulo 59.049. Antes de portar
la búsqueda hacía Zig había que responder dos cosas:

- **H1** — se puede escribir en Zig un motor que sea canónico en los 383 casos,
  incluidos los cuatro controles de stdin.
- **H2** — ese motor conserva el orden de magnitud del oráculo C (cientos de millones
  de pasos/s), o se queda cerca de la velocidad del Python.

Ambas quedan **demostradas** en este paquete. El motor es
`tools/zig_canonical/mbc.zig`.

## Construcción y procedencia

```
zig version                                    # 0.16.0
zig test    tools/zig_canonical/mbc.zig        # 5/5 pruebas unitarias
zig build-exe -O ReleaseFast -femit-bin=mbc tools/zig_canonical/mbc.zig
```

| objeto | sha256 |
|---|---|
| fuente `tools/zig_canonical/mbc.zig` | `1fead7d75f4905780db9bedfbdae614aa049e9d46dfa3fc2333f91409cca11f9` |
| binario construido (no se commitea) | `7e4479a8f47d6fef52bb1a071db2986a480601d0a98825c8c27298ead2c4aef8` |
| oráculo `vendor/oracles/mb_ref.c` | `a8ce19c2dc93e36f8c9c24a271c4187d68f922b9455262c7199a009763fe3ad3` |
| oráculo `vendor/oracles/olmstead_original.c` | `05abd38e78b266050c5a5e8cc5b36584daa5bbdeb404bfb351de7ea6fa26b510` |
| `cat_compact.mal` (BolgeForge, HEAD `7b4fbac`) | `dd8f9b106dd4b25cf190a2fa1cf7f1b03db08d2cb30d4144f8791d46a347079b` |

Las cinco pruebas unitarias fijan lo que el gate no puede fijar solo: la orientación
de la tabla crazy (`[dígito de y][dígito de x]`, no al revés — la trampa T24), que
`rot` y `crazy` no salgan del espacio de direcciones, que el decodificado del loader
sea inverso exacto del codificador que usó el corpus (`opcode_cell`), que las 94
celdas de la tabla contengan exactamente los ocho opcodes legales, y que el presupuesto
se analice como entero decimal estricto igual que el oráculo.

## Gate (comando)

```
BOLGE_EXE=<zig/bolge.exe> python3 tools/engine_gate.py \
  --engine zig_bolg1="python3 tools/gate_adapters/bolg1_runner.py {art} {steps}" \
  --engine toolkit_python="<python del toolkit> tools/gate_adapters/interpreter_runner.py {art} {steps}" \
  --engine zig_canonical="tools/zig_canonical/mbc {art} {steps}" \
  --control ../BolgeForge/artifacts/cat_compact.mal=<in_744.bin> \
  --control ../BolgeForge/artifacts/cat_compact.mal=<in_8k.bin> \
  --control ../BolgeForge/artifacts/cat_compact.mal=<in_64k.bin> \
  --control ../BolgeForge/artifacts/cat_compact.mal=<in_full.bin> \
  --out evidence/zig_canonical_engine_gate_20261101T154528ZZ
```

`in_*.bin` son prefijos de 744 / 8.192 / 65.536 / 719.637 bytes de
`vendor/source_snapshot/samples/Go/embedded.go`; sus SHA-256 están en `throughput.json`.

| motor | tier 1 | tier 2 | total | veredicto |
|---|---|---|---|---|
| oracle_mb_ref | 379/379 | 4/4 | 383/383 | CONTROL |
| oracle_olmstead | 379/379 | 4/4 | 383/383 | CONTROL |
| zig_bolg1 | 379/379 | 3/4 | 382/383 | DIVERGENT |
| toolkit_python | 379/379 | 0/4 | 379/383 | DIVERGENT |
| **zig_canonical** | **379/379** | **4/4** | **383/383** | **CANONICAL_AGREEMENT** |

Es el primer motor candidato que pasa el tier 2. El control completo (719.637 bytes
por stdin, 292.899.702 pasos) es exactamente donde `zig_bolg1` se corta: ejecuta
26.680.634 pasos — 314 más que sobre el prefijo de 64 KiB — y se detiene sin haber
consumido la entrada.

## Throughput

Sonda `throughput_probe.py`, salida `throughput.json`; 3 repeticiones por punto, mejor
valor. Primero la convención de conteo, sin la cual la tasa del oráculo no es
derivable: sobre 8 artefactos nivel 2 (paso determinista del manifest) los **cuatro**
registros coinciden —`manifest == zig_canonical == zig_bolg1 == toolkit_python`— en
**8/8**.

| workload (Cat por stdin) | mbc | mb_ref | tasa derivada mb_ref |
|---|---|---|---|
| 744 B | 0.0028 s | 0.0019 s | 163.290.000 pasos/s |
| 8.192 B | 0.0102 s | 0.0093 s | 359.310.430 |
| 65.536 B | 0.0657 s | 0.0678 s | 393.519.100 |
| 719.637 B | 0.6952 s (292.899.702 pasos) | 0.7099 s | 412.592.903 |

Mejor tasa medida: **mbc 421.317.177 pasos/s**, oráculo derivado 412.592.903 —
**ratio 1,02**, es decir el motor Zig está a la par del C en esta máquina. Intérprete
Python del toolkit in-process: 584.664–652.484 pasos/s, **~646× más lento**.

Corrección de una cifra citada antes a boca de jarro: hablé de ~1.500× de margen
usando 208.047 pasos/s medidos por subprocess (arranque del intérprete y empaquetado
de celdas incluidos dentro del tiempo). La tasa in-process del mismo intérprete es
~0,6 M pasos/s; el margen real es **~646×**. La conclusión del plan no cambia —el port
vale la pena— pero el techo end-to-end lo fija la maquinaria de búsqueda (65 % del
tiempo de síntesis: copias de instantáneas y recorridos de memoria por candidato,
26,4 µs por candidato por sólo 5,5 pasos de VM), no el stepping.

## Hallazgo abierto: los dos motores nativos cuentan distinto bajo stdin

Con salida **byte-idéntica** en los cuatro controles, `mbc` reporta **exactamente 275
pasos más** que `zig_bolg1` en los tres controles que éste alcanza (744 / 8.192 /
65.536 B; la diferencia es constante, no proporcional). En nivel 1, donde no hay
entrada, los conteos coinciden al paso. Es un desacuerdo sobre *cómo se cuenta* una
lectura de EOF, no sobre lo que la máquina produce; no afecta a la canonicidad de la
salida, pero sí a cualquier comparación de `steps` entre los dos motores para programas
alimentados por stdin, y queda sin diagnosticar en el fuente de `bolge.exe`.

## Reclamos

| # | reclamo | estado |
|---|---|---|
| R1 | `mbc` coincide byte a byte con ambos oráculos en los 379 artefactos commiteados | DEMONSTRATED |
| R2 | `mbc` coincide con ambos oráculos en los 4 controles de stdin (incluido 719.637 B) | DEMONSTRATED |
| R3 | `mbc` es canónico en general (todo programa Classic) | NO: demostrado sobre 383 casos; el espacio de estados es 3^59049 |
| R4 | `mbc` está a la par del oráculo C en velocidad | DEMONSTRATED, ratio 1,02 (mejor de 3 repeticiones, 4 workloads) |
| R5 | ~646× sobre el intérprete Python in-process | DEMONSTRATED en este hardware |
| R6 | Los cuatro motores cuentan pasos igual en nivel 2 sin stdin | DEMONSTRATED en 8/8 muestreados |
| R7 | Los dos motores nativos cuentan igual bajo stdin | REFUTADO por 275 pasos constantes en 3 controles |
| R8 | La tasa del oráculo C es derivable | VÁLIDA sólo condicionado a R6; mb_ref no reporta pasos |

## NOT_DEMONSTRATED

- Que `mbc` sea más rápido que el C en otros micros o con `-march=native` (no se probó).
- Carga interactiva: `mbc` bufferiza salida y entrada igual que el oráculo, pero no se
  probó un caso donde el programa escriba y espere en el mismo paso.
- Que el offset de 275 pasos esté en el contador de `bolge.exe` o en su manejo de EOF.
- El port de la búsqueda (`generate_for_string`) sobre este motor: es la siguiente etapa;
  su aceptación es reproducir byte-exactos los 379 artefactos commiteados, no sólo
  pasar el gate.

## Siguiente etapa

Usar `mbc` como único motor de verificación dentro del repo (sustituye la dependencia
de dos fuentes externas), y portar encima la búsqueda del toolkit con máquina residente
y restauración por delta, validado por los 379 artefactos. Nada de esto toca el corpus
commiteado.

## Nota de inventario

`tools/zig_canonical/mbc` es un artefacto de construcción: se saca del árbol tras esta
ejecución (su sha256 queda arriba) y es reconstruible con el comando de esta sección; al
repo sólo va la fuente `.zig`. El paquete de evidencia abortado por la versión anterior
del gate (`engine_canonical_gate_20261101T080313ZZ`) sigue en disco, sin borrar.
