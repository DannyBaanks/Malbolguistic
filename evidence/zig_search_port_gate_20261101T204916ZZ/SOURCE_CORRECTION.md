# Correccion anadida tras sellar el paquete (pre-commit, 2026-11-01T20:55Z)

El comentario de cabecera de `tools/zig_canonical/mbsearch.zig` afirmaba que la
igualdad textual con `generate_for_string` solo era testeable con `--depth` por encima
de toda profundidad alcanzable, "la unica configuracion en la que la referencia nunca
alcanza su RNG". Eso es falso y se midio despues: no existe regimen libre de RNG. La
referencia llama a `rng.choice` en todo objetivo del corpus sea cual sea el tope (234
llamadas con `--depth 5` en `ext/linguist/linguist.h`; aun 8 con `--depth 12`), porque
a veces el byte objetivo no se alcanza imprimiendo y la salida es un cambio de estado
aleatorio. El parrafo corregido describe el metodo real: fijar el mismo flujo en ambos
lados, que es lo que `tools/mbsearch_gate.py` hace con `SharedStream`.

Es texto de comentario: no cambio ninguna linea de codigo.

| objeto | sha256 |
|---|---|
| fuente usada en el gate (la que fija `summary.json`) | `d7124002344b2f103c5df6bc1c43836249e3109543b1ca57402178edd721f398` |
| fuente en disco tras la correccion | `b99e5e9100746b8b96819cd1efe4f8a8e76d4fb55f81e7dbb28ee02d9f4a290b` |
| binario sellado por `summary.json` | `d1914895e9e1c39699c3ee9865e7e42ead84c2bb53826844235c2ebe85400c9e` |
| binario reconstruido tras la correccion | `e986891aff437a3631f23a4ceadb0a0f514aff26045b04b223fdbd2c4f29cc15` |

Los dos binarios difieren porque Zig emite informacion de linea en los mensajes de
panico y la cabecera gano lineas. La equivalencia de comportamiento se midio, no se
supuso: reejecutando la busqueda con el binario nuevo sobre los objetivos registrados en
los paquetes y comparando el sha256 de cada programa salieron **identicos 439/439**
(379/379 a `depth 5`, 30/30 a `depth 3`, 30/30 a `depth 8`), lo que cubre tambien los 12
objetivos de `…T204042ZZ` y los 30 de `…T204850ZZ`, subconjuntos de las barridas
anteriores. Ninguna cifra de `REPORT.md` cambia.
