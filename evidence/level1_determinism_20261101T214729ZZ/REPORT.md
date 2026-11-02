# Level-1 codec determinism (2026-11-01T21:47:29Z)

Scope: the 4258 TEXT entries that carry a `mirror/*.malrt1` artifact in
`manifest/translation_manifest.json`. Nothing else is in scope.

| medida | valor |
|---|---|
| entradas comprobadas | 4258 |
| PASS (doble codificacion identica Y coincide con la envoltura commiteada) | 4258 |
| FAIL | 0 |
| codificacion doble identica | 4258/4258 |
| coincide con mirror/ commiteado | 4258/4258 |
| envelope_sha256 del manifest coincide | 4258/4258 |
| source_sha256 del manifest coincide | 4258/4258 |
| caracteres de envoltura totales | 42,509,444 |
| muro | 0.44 s |
| python | 3.12.3 |

## Que prueba

`encode_roundtrip_bytes()` es una funcion pura sin RNG: codificar dos veces la
misma fuente da el mismo payload, y ese payload es byte a byte la envoltura que
esta commiteada. Por eso el nivel 1 se puede prometer como byte-reproducible.

## Que NO prueba

- Nada del nivel 2: la sintesis no es byte-reproducible (3 corridas, 3 programas
  distintos; `evidence/synthesis_linux_probe_20261101/`).
- No prueba que un clon fresco reconstruya el corpus entero sin `--resume`.
- No ejecuta Malbolge: solo el codec.
