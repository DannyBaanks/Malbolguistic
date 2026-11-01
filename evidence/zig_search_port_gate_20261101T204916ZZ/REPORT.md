# Barrido de tope de busqueda en el port: cuanto cuesta bajar la expansion (punto `depth 8`)

Paquete: `evidence/zig_search_port_gate_20261101T204916ZZ/`
Gate: modo corpus, `--depth 8`, 30 objetivos · Malbolguistic HEAD `f6f980383d90aeac482bd064c3e44ddf60265f25`
Fuentes sin commitear al correr. Paquetes hermanos del barrido: `evidence/zig_search_port_gate_20261101T204822ZZ` (`depth 3`), `evidence/zig_search_port_gate_20261101T204850ZZ` (`depth 5`), `evidence/zig_search_port_gate_20261101T204916ZZ` (`depth 8`)

## Pregunta

El tope de busqueda (`max_search_depth`) es la palanca que decide cuantos caracteres
ocupa el corpus `.mal`. Con el port en Zig el tiempo de busqueda deja de ser el cuello,
asi que la decision pasa a ser de almacenamiento: hace falta la curva
expansion/precio medida sobre el mismo conjunto de objetivos. Este paquete es uno de los
tres puntos de esa curva, todos sobre **los mismos 30 objetivos**
(2,640 bytes de sobre en total).

## Comando

```
zig version                                       # 0.16.0
python3 tools/mbsearch_gate.py --mode corpus --limit 30 --depth 8
```

| objeto | sha256 |
|---|---|
| fuente `tools/zig_canonical/mbsearch.zig` | `d7124002344b2f103c5df6bc1c43836249e3109543b1ca57402178edd721f398` |
| fuente `tools/zig_canonical/mbc.zig` | `1fead7d75f4905780db9bedfbdae614aa049e9d46dfa3fc2333f91409cca11f9` |
| binario `mbsearch` | `d1914895e9e1c39699c3ee9865e7e42ead84c2bb53826844235c2ebe85400c9e` |
| driver `mbsearch_gate.py` | `5398e49cd8a33ea4fabebb8c314af5811f2ad0edafc616fefedd0cfabed992e5` |

## Curva (los tres puntos, mismo conjunto de objetivos)

| `depth` | caracteres de programa | razon global | maximo | expansion min/med/max | evaluaciones | `mbc` OK |
|---|---|---|---|---|---|---|
| 3 | 151,766 | 57.49x | 6,062 | 48.1 / 58.54 / 68.79 | 1,438,261 | **30/30** |
| 5 | 65,940 | 24.98x | 2,809 | 20.36 / 25.53 / 30.53 | 3,303,280 | 30/30 |
| 8 | 34,017 | 12.89x | 1,303 | 10.63 / 13.06 / 16.47 | 18,436,941 | 30/30 |

Lectura: subir el tope de 5 a 8 recorta el conjunto a la mitad de caracteres
(65,940 -> 34,017, un 48 % menos)
a cambio de 5.6x evaluaciones
(3,303,280 -> 18,436,941). Con los >=1,1M de evaluaciones/s medidos en
`evidence/zig_search_port_gate_20261101T204229ZZ`, los 18,436,941 evaluaciones de
estos 30 objetivos caben en decenas de segundos. Extrapolar el barrido a los 379
objetivos es decision de la tarea de tope, no de este paquete.

## Que demuestra este punto

- Los 30 programas emitidos a `depth 8` son canonicos: `mbc` imprime el sobre exacto
  en 30/30 casos y la verificacion dentro del port no falla en ninguno.
- Los cinco contadores de divergencia (`peak_gaps`, `stalls`, `budget_exhausted`,
  `slash_executed`, `delta_overflows`) quedan en 0 tambien en este tope: la emulacion del
  alto `program_end` sigue siendo invisible fuera del `depth 5`.

## Que no demuestra

- No compara con la referencia Python: el tier corpus no ejecuta el toolkit. La fidelidad
  textual esta sellada en `depth 5` (12/12) y `depth 3` (30/30) en sus paquetes.
- 30 objetivos de 72 a 100 bytes; no hay dato de coste para objetivos grandes a `depth 8`.
- El barrido entrega la curva, no fija el tope optimo: el contrato del corpus sigue abierto.
