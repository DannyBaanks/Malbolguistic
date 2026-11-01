# Diferencial con `--depth 3`: 30/30 programas byte-identicos con la referencia en el régimen de RNG más caliente

Paquete: `evidence/zig_search_port_gate_20261101T204332ZZ/`
Gate: 2026-11-01T20:43:32Z · Malbolguistic HEAD `f6f980383d90aeac482bd064c3e44ddf60265f25`
Paquete principal: `evidence/zig_search_port_gate_20261101T204042ZZ/` (los tres tiers a `depth 5`).

## Pregunta

La igualdad textual del port con `generate_for_string` sólo puede exigirse fijando el
flujo aleatorio de ambos lados. Quedaba por ver si la igualdad sobrevive cuando el
generador aleatorio **no es un caso marginal**: a `--depth 3` la frontera se agota mucho
antes, la rama `rng.choice` se dispara con mucha más frecuencia y cada elección cambia
el estado desde el que se re-expande toda la búsqueda. Si el port difiriera en el orden
de la frontera, en la firma de estado o en la poda de programas muertos, `depth 3` es
donde se vería.

- **H1** — con el mismo flujo SplitMix64 a la derecha y a la izquierda, los 30 programas
  son byte-idénticos también a `depth 3`.
- **H2** — no sólo el texto: los conteos internos (`evaluations` y número de
  `rng.choice`) coinciden objetivo a objetivo.

Ambas demostradas.

## Comando y procedencia

```
zig version                                       # 0.16.0
python3 tools/mbsearch_gate.py --mode differential --limit 30 --depth 3 \
        --site-packages <site-packages del toolkit>
```

El tier importa `malbolge.generator` del toolkit y sustituye su `Random` por
`SharedStream`, copia en Python de `Rng` en `tools/zig_canonical/mbsearch.zig`
(SplitMix64 con `below(n)` por rechazo). Con el mismo flujo, cualquier diferencia que
quede es de búsqueda, no de PRNG.

| objeto | sha256 |
|---|---|
| fuente `tools/zig_canonical/mbsearch.zig` | `d7124002344b2f103c5df6bc1c43836249e3109543b1ca57402178edd721f398` |
| fuente `tools/zig_canonical/mbc.zig` | `1fead7d75f4905780db9bedfbdae614aa049e9d46dfa3fc2333f91409cca11f9` |
| binario `mbsearch` | `d1914895e9e1c39699c3ee9865e7e42ead84c2bb53826844235c2ebe85400c9e` |
| binario `mbc` | `7e4479a8f47d6fef52bb1a071db2986a480601d0a98825c8c27298ead2c4aef8` |
| driver `mbsearch_gate.py` | `5398e49cd8a33ea4fabebb8c314af5811f2ad0edafc616fefedd0cfabed992e5` |

## Resultados (30 objetivos más pequeños, sobre de 72 a 100 bytes)

| medida | valor |
|---|---|
| programas byte-idénticos a la referencia | **30/30** |
| `evaluations` iguales | **30/30** |
| nº de `rng.choice` iguales | **30/30** |
| `mbc` imprime el sobre del programa del port | **30/30** |
| `rng.choice` totales | 34.959 sobre 1.438.261 evaluaciones |
| caracteres de programa totales | 151.766 |
| tiempo Python / tiempo port | 72,09 s / 0,675 s → **107×** |

Caso representativo (`test/fixtures/Data/Modelines/iamphp.inc`, sobre de 100 B):
6.062 caracteres en ambos lados, 57.743 evaluaciones en ambos lados, **1.405
`rng.choice` en ambos lados**, `mbc` OK. Con esa densidad de decisiones aleatorias, una
firma de estado o un orden de frontera distintos habría dado programas distintos en
todos los objetivos.

## Alcance y lo que no se demuestra

- Fija el motor de búsqueda, **no** el sembrado de CPython: con `Random(42)` real los
  programas del port no coinciden con los de la referencia (medido: 0/3 en el sondeo
  previo y 0/379 en el paquete de corpus). Ver `NOT_DEMONSTRATED` en el paquete principal.
- Objetivos de 72 a 100 bytes y `choices=op*`; no hay controles con `choices` distintos
  ni con entradas por encima de 100 bytes en este paquete.
- Los 30 objetivos son los más pequeños del corpus por caracteres de artefacto; la
  selección es la del driver, no un muestreo aleatorio.
