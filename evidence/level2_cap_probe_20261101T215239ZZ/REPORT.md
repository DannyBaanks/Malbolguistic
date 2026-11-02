# Sonda de tope para el nivel 2 (2026-11-01)

## Preguntas que este pack responde

1. ¿Cuánto cuesta el nivel 2 **por encima** de los 128 B actuales, con los dos
   motores que existen: el generador Python (`vendor/malbolge_translator`, el que usó
   el build) y el port a Zig (`tools/zig_canonical/mbsearch.zig`)?
2. ¿Qué archivos son siquiera **alcanzables**: la cinta canónica son 3^10 = 59.049
   celdas, así que un programa más largo que la cinta nunca carga
   (`error.ProgramTooLong`)?
3. ¿Cuánto ocuparía cada tope en el repo?

No decide nada: entrega los números para que se decida con datos.

## Método

- `zig_cost.py` — para cada banda de tamaño toma mínimo/mediana/máximo de la banda,
  sintetiza con `mbsearch` en profundidad 5 y 8, mide pared y RSS pico desde `/proc`,
  y **re-ejecuta el programa con `mbc` exigiendo stdout byte a byte igual a la envoltura
  objetivo**. Los dos binarios se recompilan aquí desde el fuente commiteado con
  `zig build-exe -O ReleaseFast`; sus SHA-256 están en la primera línea de
  `raw_zig.jsonl` (`engine: build`).
- `py_cost.py` — la misma banda con la llamada exacta del build,
  `MalbolgeTranslator(max_search_depth=5).translate_and_verify_roundtrip()`, con guarda
  de memoria (`PY_GUARD_MB=5500`) y de muro (`PY_WALL_S=240`).
- `cap_table.py` — proyección por tope: fórmula exacta de la envoltura
  (`7 + 4*ceil(n/3) + 1 + 64`), constantes medidas (ms/caracter de envoltura y expansión
  por profundidad) y corte de cinta.

Host: Linux, python 3.12.3, zig 0.16.0, un proceso por archivo.

## Resultados

### Zig (`mbsearch`), medido, 60 síntesis

| profundidad | ms por caracter de envoltura (mediana) | expansión (mediana) | RSS pico observado | síntesis OK / intentos | verificación `mbc` byte-exacta |
|---|---|---|---|---|---|
| 5 | 1,114 | 23,64x | 165 MB | 22 / 30 | 22/22 |
| 8 | 6,995 | 11,46x | 1.874 MB | 30 / 30 | 30/30 |

Frontera de cinta medida en archivos reales del inventario:

| profundidad | última fuente que sí sintetiza | primera fuente que falla |
|---|---|---|
| 5 | 1.826 B | 1.863 B (`ProgramTooLong`) |
| 8 | 3.816 B (ninguna falla hasta ahí) | — |

Total del lote: 52 síntesis OK, 8 rechazos por cinta, **52/52 re-ejecutadas byte-exactas
bajo `mbc`**.

### Python (`vendor/malbolge_translator`), medido con guarda de 5.500 MB

| entrada | RSS pico | muro | resultado |
|---|---|---|---|
| control `hi` (2 B) | 1.206 MB | 5,3 s | PASS, programa de 2.002 caracteres |
| 97 B (**dentro del tope actual de 128 B**) | >5.500 MB | 17 s | matado por la guarda, curva aún subiendo (~350 MB/s) |
| 179 B | >5.500 MB | 17,5 s | idem |
| 224 B | >5.500 MB | 16 s | idem |
| 460 B | >5.500 MB | 17 s | idem |
| 838 B | >5.500 MB | 17,5 s | idem |

Dos medidas más, en `raw_py_extra.jsonl` (misma llamador, guarda bajada a 3.000 MB para
poder nombrar un archivo concreto con `@<ruta>`):

| entrada | RSS pico | muro | resultado |
|---|---|---|---|
| `.github/CODEOWNERS` (96 B) | >3.000 MB | 11,3 s | matado por la guarda |
| control `hi` (2 B), segunda toma | 1.408 MB | 5,5 s | PASS, **2.152** caracteres |

Ese archivo de 96 B es el mismo que el bench sellado sintetizó en **21,19 s**
(`synthesis_linux_probe_20261101/bench_depth5.log`) — el bench midió muro y no midió
memoria, así que su ley «~6 s + ~0,16 s/byte» era cierta pero **incompleta**: el coste
real incluye gigas por archivo. Y el control de 2 B salió dos veces en este pack con
programas de 2.002 y 2.152 caracteres: la no-reproducibilidad del nivel 2 vuelve a
aparecer sola.

Lectura honesta: **no se midió un fallo del generador, se midió que no cabe**. Con esta
pareja (copias locales del translator y de `malbolge-generator`) y esta profundidad, un
archivo de 97 B —que sí tiene artefacto commiteado— pide más de 5,5 GB. El artefacto
commiteado se produjo en otro entorno (Windows, 2026-09-04), así que la comparación de
coste con el build histórico **no** es manzana-a-manzana; lo que sí es comparable es que
el port hace el mismo trabajo en 0,2-2,4 s con 165 MB.

### Proyección por tope (`summary.json`)

| tope | elegibles | % del TEXT | Zig d5: muro | Zig d5: almacén | d5 alcanzables | Zig d8: muro | Zig d8: almacén | d8 alcanzables |
|---|---|---|---|---|---|---|---|---|
| 128 B (actual) | 379 | 8,9 % | 64 s | 1,3 MB | 379 | 399 s | 0,7 MB | 379 |
| 256 B | 642 | 15,1 % | 159 s | 3,4 MB | 642 | 1.000 s | 1,6 MB | 642 |
| 512 B | 1.022 | 24,0 % | 403 s | 8,5 MB | 1.022 | 2.529 s | 4,1 MB | 1.022 |
| 1.024 B | 1.605 | 37,7 % | 1.115 s | 23,7 MB | 1.605 | 7.001 s | 11,5 MB | 1.605 |
| 1.792 B | 2.444 | 57,4 % | 2.887 s | 61,3 MB | 2.444 | 18.130 s | 29,7 MB | 2.444 |
| 2.048 B | 2.597 | 61,0 % | 3.335 s | 70,8 MB | **2.464** | 20.941 s | 34,3 MB | 2.597 |
| 4.096 B | 3.160 | 74,2 % | 5.806 s | 123,2 MB | **2.464** | 36.454 s | 59,7 MB | **3.110** |
| 8.192 B | 3.603 | 84,6 % | 9.621 s | 204,2 MB | **2.464** | 60.413 s | 99,0 MB | **3.110** |

`alcanzables` = archivos cuya longitud de programa proyectada cabe en los 59.049 caracteres
de la cinta. Por encima de eso no es "tarda más": **nunca carga**. Los 1.098 archivos de
más de 4.096 B quedan fuera del nivel 2 con las profundidades probadas.

Control de la proyección: la fila de 128 B dice 64 s, y el gate sellado del corpus entero
midió **63 s de pared para los 379 objetivos** (`zig_search_port_gate_20261101T204229ZZ/`).
La proyección lineal en caracteres de envoltura acierta en el caso que ya se conoce.

## Lo que este pack prueba

- Que extender el nivel 2 es factible **con el port a Zig** en costes de minutos, no de
  días, y con 165 MB de pico (profundidad 5).
- Que la frontera dura del nivel 2 es la cinta (59.049 celdas), no el presupuesto: a
  profundidad 5 se agota sobre ~1.830 B de fuente (2.464 archivos, 57,9 % del TEXT); a
  profundidad 8 sobre ~3.900 B (3.110 archivos, 73,0 %).
- Que cada síntesis nueva quedó byte-exacta bajo el motor canónico Zig (52/52).
- Que el generador Python no es vía para extender el corpus en este host.
- Comparación directa sobre **el mismo archivo**: `.github/CODEOWNERS` (96 B) — Python
  21,19 s de muro y >3,0 GB de RAM; Zig `mbsearch` **0,2 s**, con `mbc` byte-exacto. El RSS
  de los casos sub-segundo del port sale `0 MB` porque el muestreo es cada 0,2 s: hay que
  leerlo como "no resuelto por el muestreo", no como "<1 MB". El techo medido con resolución
  suficiente es 165 MB (profundidad 5, lote completo).

## Lo que NO prueba

- Que los programas del port sean los del corpus: contra los `.mal` commiteados son
  **0/379 byte-identicos** (`zig_search_port_gate_20261101T204229ZZ/`). Ampliar con el
  port crea un **segundo linaje** dentro de `malbolge/`, y eso hay que declararlo.
- Nada de reproducibilidad del nivel 2: la síntesis no es byte-reproducible
  (`synthesis_linux_probe_20261101/`).
- Que el generador Python falle: con 5,5 GB no alcanza; con más memoria disponible podría
  terminar. No se intentó porque tumbaría el host.
- Que la proyección lineal en caracteres de envoltura sea exacta: es la mediana medida
  sobre 60 síntesis; casos patológicos (muchos estados repetidos) se salen de la mediana.
