# Corpus completo en Zig: 379/379 programas canónicos, contadores de divergencia en 0, ~63 s de pared

Paquete: `evidence/zig_search_port_gate_20261101T204229ZZ/`
Gate: 2026-11-01T20:42:29Z–20:43:32Z (63 s de pared) · Malbolguistic HEAD `f6f980383d90aeac482bd064c3e44ddf60265f25`
Código `tools/zig_canonical/mbsearch.zig` y `tools/mbsearch_gate.py` sin commitear al correr.
Paquete principal del port: `evidence/zig_search_port_gate_20261101T204042ZZ/` (tiers de determinismo y diferencial).

## Pregunta

Si el port es realmente la misma búsqueda sobre la máquina canónica, entonces la única
desviación que introdujo —emular el alto `program_end` con un umbral sobre una cinta que
sí envuelve módulo 59.049— tiene que ser **invisible en todo el corpus**, no sólo en los
12 objetivos pequeños del gate principal.

- **H1** — para los 379 sobre-envoltorios que produjeron artefactos `.mal`, `mbsearch`
  emite un programa y `mbc` imprime con él exactamente los bytes del sobre.
- **H2** — ningún objetivo toca ninguna de las cinco rutas de divergencia.
- **H3** — el coste del nivel 2 deja de estar dominado por el intérprete Python.

Las tres quedan demostradas en este paquete.

## Comando y procedencia

```
zig version                                       # 0.16.0
python3 tools/mbsearch_gate.py --mode corpus --limit 0 --depth 5
```

`--limit 0` = todos los objetivos con artefacto `.mal` en `status: PASS` del manifest
(379). El driver fija los sha256 de las fuentes y de los binarios que construye; la
copia exacta del driver usada está en este paquete.

| objeto | sha256 |
|---|---|
| fuente `tools/zig_canonical/mbsearch.zig` | `d7124002344b2f103c5df6bc1c43836249e3109543b1ca57402178edd721f398` |
| fuente `tools/zig_canonical/mbc.zig` | `1fead7d75f4905780db9bedfbdae614aa049e9d46dfa3fc2333f91409cca11f9` |
| binario `mbsearch` | `d1914895e9e1c39699c3ee9865e7e42ead84c2bb53826844235c2ebe85400c9e` |
| binario `mbc` | `7e4479a8f47d6fef52bb1a071db2986a480601d0a98825c8c27298ead2c4aef8` |
| driver `mbsearch_gate.py` | `5398e49cd8a33ea4fabebb8c314af5811f2ad0edafc616fefedd0cfabed992e5` |
| `manifest/translation_manifest.json` | `64b4a2a966947b50281b71a71ac016be0467e0d411aeb595c498a830c2372901` |

## Resultados

| medida | valor |
|---|---|
| objetivos | 379 (sobre de 72 a 244 bytes) |
| `mbc` imprime el sobre exacto | **379/379** |
| verificación canónica dentro del port | **379/379** |
| evaluaciones totales | 70.727.782 |
| evaluaciones máximas en un objetivo | 336.266 |
| `rng.choice` totales | 178.411 |
| `peak_gaps` / `stalls` / `budget_exhausted` / `slash_executed` / `delta_overflows` | **0 / 0 / 0 / 0 / 0** |
| caracteres de programa (suma) | 1.387.386 (máximo 6.422) |
| caracteres de los `.mal` commiteados (suma, del manifest) | 1.421.372 (máximo 6.980) |
| longitud port vs commiteada | 224 más cortos, 155 más largos, razón global 0,976 |
| razón de expansión | mínima 19,34 · mediana 24,32 · máxima 30,53 |
| programas iguales byte a byte a los commiteados | 0/379 (ver abajo) |

Las comparaciones de longitud salen del campo `malbolge.chars` del propio manifest, así
que son recomprobables sin volver a ejecutar nada.

## Coste: lo que cambia para el nivel 2

63 s de pared para los 379 objetivos, **incluidos** los dos `zig build-exe` y las 379
ejecuciones de `mbc`. Eso acota por debajo 1,12M de evaluaciones/s en búsqueda+verificación,
frente a los ~40 µs por evaluación del camino Python medido antes (≈25k eval/s), un
orden de magnitud de diferencia. Implicación directa para la decisión de tope: el
cuello de botella del corpus completo deja de ser la CPU y pasa a ser almacenamiento
(~1,4 MB de programas para 379 objetivos a `depth 5`) y el coste del `mbc` por artefacto.

## Lo que este paquete no demuestra

- **0/379 coincidencias textuales con los `.mal` commiteados.** No es un fallo del port:
  la toolkit actual tampoco reproduce esos artefactos (sondeo previo: 3 objetivos, 3
  aceptados por `mbc`, 0 iguales). La procedencia del corpus es heterogénea
  (`search_depth` = `null` en 354 entradas y `3` en 25) y el sembrado MT19937 de
  CPython `Random(42)` no es recreable con las inicializaciones estándar. Por eso la
  igualdad textual se mide en el paquete principal con flujo RNG compartido, y aquí sólo
  se afirma canonicidad.
- No hay objetivos por encima de 244 bytes de sobre: el comportamiento del port más allá
  de ese tamaño no está medido aquí.
- Los términos de alto `stall`/`budget` nunca se activaron: 0 casos, así que esas ramas
  del port siguen sin evidencia de ejecución.
