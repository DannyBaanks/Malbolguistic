# Gate de semántica multi-engine — ¿es canónico un motor candidato?

Paquete: `evidence/engine_canonical_gate_20261101T082034ZZ/`
UTC de ejecución: 2026-11-01T08:20:34Z (30.1 s de reloj para 383 casos)
Repo: Malbolguistic, HEAD `f6f980383d90aeac482bd064c3e44ddf60265f25` (sin commitear las herramientas de este paquete)

## Pregunta

Paso 1 del plan aprobado: antes de portar la búsqueda
a Zig, cualquier motor candidato tiene que **coincidir con los oráculos canónicos
en el corpus entero**, no en una muestra. Un motor que discrepa en un artefacto no es
canónico, sea lo que sea que reporte sobre los otros 378.

Hipótesis falsables:

- **H1** — `zig/bolge.exe` (semántica toolkit, entrada por volcado de celdas BOLG1) es
  canónico sobre el corpus.
- **H2** — el intérprete Python del toolkit (`malbolge.interpreter`) es canónico sobre el corpus.
- **H3** — la concordancia en nivel 1 (stdout == envoltura, stdin vacío) implica concordancia
  canónico en general.

H3 es la que importa, y por eso el gate tiene dos tiers: el tier 1 sola no refuta nada,
porque los 379 artefactos no leen stdin ni empujan `d` más allá del borde de memoria.

## Entorno

Ubuntu 24.04, x86_64, 12 núcleos, gcc 13.3.0, glibc 2.39, Python 3.12.3 (host) y un
entorno virtual aparte para el toolkit. Los oráculos se compilan desde fuente pinned en
cada ejecución y el gate **se niega a seguir** si el SHA-256 del fuente no coincide:

| oráculo | sha256 del fuente | rol |
|---|---|---|
| `vendor/oracles/mb_ref.c` | `a8ce19c2dc93e36f8c9c24a271c4187d68f922b9455262c7199a009763fe3ad3` | control |
| `vendor/oracles/olmstead_original.c` | `05abd38e78b266050c5a5e8cc5b36584daa5bbdeb404bfb351de7ea6fa26b510` | control |

Olmstead (1998, dominio público) no acepta argumento de presupuesto y su salida se
compara byte a byte. `mb_ref` es **independiente de Olmstead** pero NO es independiente
entre repos hermanos: el mismo `mb_ref.c` byte a byte vive en BolgeForge y PureEpoch, así
que "mb_ref de otro repo" nunca cuenta como segundo oráculo.

Artefacto de control tier 2: `cat_compact.mal` de BolgeForge, sha256
`dd8f9b106dd4b25cf190a2fa1cf7f1b03db08d2cb30d4144f8791d46a347079b`, presente en HEAD
`7b4fbacf2d7d58cdfadd83a48af17128c2c776f6`.

## Procedimiento

Herramienta: `tools/engine_gate.py` (dos tiers) con adaptadores en
`tools/gate_adapters/`. Comando reconstruible (los valores de entorno se pasan por nombre,
nunca se escriben rutas del workstation en el paquete):

```
BOLGE_EXE=<zig/bolge.exe> TOOLKIT_PY=<python con el paquete malbolge instalado> \
python3 tools/engine_gate.py \
  --engine zig_bolg1="python3 tools/gate_adapters/bolg1_runner.py {art} {steps}" \
  --engine toolkit_python="<python del venv> tools/gate_adapters/interpreter_runner.py {art} {steps}" \
  --control ../BolgeForge/artifacts/cat_compact.mal=<in_744.bin> \
  --control ../BolgeForge/artifacts/cat_compact.mal=<in_8k.bin> \
  --control ../BolgeForge/artifacts/cat_compact.mal=<in_64k.bin> \
  --control ../BolgeForge/artifacts/cat_compact.mal=<in_full.bin> \
  --out evidence/engine_canonical_gate_20261101T082034ZZ
```

- **Tier 1** — los 379 artefactos nivel 2 commiteados, stdin vacío, esperar: rc 0 y
  stdout idéntico byte a byte a la envoltura `MALRT1` del espejo correspondiente.
- **Tier 2** — 4 controles negativos: el programa Cat canónico alimentado con prefijos
  de `vendor/source_snapshot/samples/Go/embedded.go` (744 B / 8 KiB / 64 KiB / 719.637 B
  completos; sha256 de los cuatro están en `throughput.json`). Esperar: rc 0 y
  stdout == bytes de entrada. Ejercitan `in`, crecimiento de `d` y EOF — lo único que
  distingue a un motor toolkit de un motor Classic.
- El gate escribe en un directorio nuevo fechado y **rechaza** una ruta ya existente.

## Resultados

### Tier 1 — concordancia total, y no es suficiente

| motor | halt | tier1 exact |
|---|---|---|
| oracle_mb_ref | 383/383 | 379/379 |
| oracle_olmstead | 383/383 | 379/379 |
| zig_bolg1 | 382/383 | **379/379** |
| toolkit_python | 379/383 | **379/379** |

H1 y H2 **sobreviven al tier 1**. Esto era predecible: un motor que implementa la
máquina Classic sobre casos que nunca tocan el borde de memoria ni `in` no tiene
ninguna oportunidad de mostrar la diferencia.

### Tier 2 — refutación

| motor | tier2 exact | fallo |
|---|---|---|
| oráculos | 4/4 | — |
| zig_bolg1 | 3/4 | control de 719.637 B: `rc=3`, `steps=26680634 term=0 reason=3` |
| toolkit_python | 0/4 | los cuatro: `rc=4`, `MemoryLimitExceededError: Memory limit exceeded.` |

**H1 y H2 quedan REFUTADAS; H3 también** (379/379 en tier 1 conviviendo con 1/4 y 4/4 de
fallos en tier 2). Veredicto del gate para ambos candidatos: `DIVERGENT`.

Diagnóstico del fallo de `zig_bolg1`, medido y no interpretado: en el control completo
executa **26.680.634 pasos**, es decir **314 pasos más** que los 26.680.320 que ejecuta
sobre el prefijo de 64 KiB. No es un presupuesto agotado ni un cuelgue: consumió ~64 KiB
de los 719.637 B y se quedó sin entrada. Coincide con el límite de lectura del envoltorio
BOLG1 medido aparte. Consecuencia práctica: hoy `zig/bolge.exe` **no puede** verificar el
corpus por stdin, que es el contrato que sí cubre los 4.258 ficheros.

Diagnóstico del toolkit Python, en su propio fuente (`malbolge/interpreter.py`,
`_ensure_capacity`): al pedirse una dirección ≥ `MAX_ADDRESS_SPACE` (59049) **lanza**
`MemoryLimitExceededError`. El oráculo hace otra cosa — envuelve:

```c
c = (c == 59048) ? 0 : c + 1;
d = (d == 59048) ? 0 : d + 1;
...
a = (in_ch == EOF) ? 59048 : (unsigned short)in_ch;   /* in en EOF = 3^10 - 1 */
```

O sea: al toolkit le falta el envoltorio Classic módulo 59.049. No es un bug de
configuración de presupuesto ni de `allow_memory_expansion`: es otra semántica de
memoria, y se manifiesta precisamente cuando un programa alimentado por stdin empuja `d`
al borde.

## Throughput (para la decisión del port)

Sonda: `throughput_probe.py`, salida `throughput.json`.

```
ORACLE_DIR=<dir con mb_ref compilado desde vendor/oracles/mb_ref.c> \
CAT_MAL=../BolgeForge/artifacts/cat_compact.mal BOLGE_EXE=<zig/bolge.exe> \
TOOLKIT_PY=<python del toolkit> MBG_VENV_SITEPACKETS=<site-packages del toolkit> \
python3 evidence/engine_canonical_gate_20261101T082034ZZ/throughput_probe.py
```

Primero la condición para poder hablar de pasos/segundo: `mb_ref` **no reporta pasos**.
Así que la tasa se deriva del conteo del motor de celdas, y eso solo vale si los tres
registros independientes coinciden. Comprobado sobre 8 artefactos nivel 2 elegidos por
paso determinista del manifest: `manifest_steps == zig_bolg1_steps == toolkit_python_steps`
en **8/8** (ver `counting_convention`, veredicto `SHARED`).

| motor | workload 64 KiB | tasa |
|---|---|---|
| oracle_mb_ref | 0.070 s | 381.147.428 pasos/s (**derivada**) |
| zig_bolg1 (subprocess con adaptador) | 0.097 s | 275.054.845 pasos/s |
| toolkit_python (in-process) | 0.011 s sobre 6.882 pasos | 625.106 pasos/s |

**Corrección a lo dicho oralmente antes:** cité ~1.500× de margen Python→nativo usando
208.047 pasos/s, medido por subprocess (arranque del intérprete + empaquetado de celdas
dentro del tiempo). La tasa in-process del mismo intérprete es 453.595–625.106 pasos/s.
El margen real contra `mb_ref` es **~610×**, no ~1.500×. No cambia la conclusión del plan
— el port sigue valiendo la pena — pero sí cambia la expectativa: el techo end-to-end del
port no lo fija el stepping, lo fija la maquinaria de búsqueda (instantáneas, copias de
memoria por candidato: 65 % del tiempo de síntesis medido, 26,4 µs por candidato por sólo
5,5 pasos de VM).

## Reclamos

| # | reclamo | estado |
|---|---|---|
| R1 | Los 379 artefactos nivel 2 commiteados producen su envoltura byte-exacta en mb_ref Y Olmstead | DEMONSTRATED |
| R2 | `zig/bolge.exe` coincide con ambos oráculos en los 379 | DEMONSTRATED (tier 1) |
| R3 | `zig/bolg1` es canónico en general | REFUTED (tier 2, 64 KiB de tope de entrada) |
| R4 | El intérprete toolkit coincide en los 379 | DEMONSTRATED (tier 1) |
| R5 | El intérprete toolkit implementa semántica Classic | REFUTED (sin envoltorio módulo 59.049; `MemoryLimitExceededError` en 4/4 controles) |
| R6 | Concordar en tier 1 implica concordancia canónica | REFUTED por diseño; el tier 2 existe para esto |
| R7 | Los tres motores cuentan pasos igual sobre el corpus | DEMONSTRATED en 8/8 muestreados; no probado para los 379 |
| R8 | `mb_ref` ≈ 381 M pasos/s | DERIVADO, condicionado a R7 |
| R9 | Margen Python→nativo | DEMONSTRATED ~610× in-process; corrige el ~1.500× dicho antes |

## NOT_DEMONSTRATED

- Que el tope de 64 KiB esté en `bolge.exe` o en el empaquetado BOLG1 del adaptador: la
  sonda no separa las dos capas.
- Que `reason=3` del protocolo BOLG1 signifique "sin entrada". Se reporta el número, no
  su interpretación.
- Que los 8 artefactos del chequeo de convención representen a los 379.
- Un motor Zig con envoltorio Classic: no existe todavía; es el entregable del paso 2.
- Que la brecha del toolkit sea arreglable por configuración: el fuente muestra que la
  rama de excepción está en el camino de crecimiento de cinta, no en un presupuesto.

## Consecuencia para el port a Zig (tarea #10)

La especificación del motor es `mb_ref.c` / Olmstead, **no** `malbolge/interpreter.py`.
El motor nuevo tiene que implementar: cinta fija de 59.049, `c`/`d` con envoltorio
módulo 59.049, `in` en EOF = 3^padwidth − 1, y el chequeo de celda no imprimible que
produce `NONPRINTABLE_PC` / `INVALID_ENCRYPTION` en vez de un NOP inventado. Aceptación:
pasar los 4 controles tier 2, no sólo los 379 del tier 1.

## Estado del directorio

`evidence/engine_canonical_gate_20261101T080313ZZ/` (`raw.jsonl`, `summary.json`) es una
primera ejecución del gate en versión tier 1 única, abortada por un error de escritura en
el resumen de veredictos. **Se conserva en disco, no se borra**: borrar requiere
aprobación explícita de Danny. No está sellada y no se usa como evidencia de nada; la
etapa canónica es este paquete.

## Sellado

`SHA256SUMS.txt` generado con `sha256sum` sobre todos los ficheros del paquete salvo el
propio sumario. Verificar con `sha256sum -c SHA256SUMS.txt` desde dentro del directorio.

Marcas de tiempo UTC de lo que hay dentro (no todo corrió en la misma ventana):
gate tier 1 + tier 2 `raw.jsonl` / `summary.json` a las 2026-11-01T08:20:34Z;
`throughput_probe.py` y su salida `throughput.json` a las 2026-11-01T15:32Z del mismo día.
