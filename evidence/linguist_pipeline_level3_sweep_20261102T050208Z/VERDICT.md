# Barrido del corpus nivel 3 por el pipeline linguist — 20261102T050208Z

Pasa cada archivo del catálogo por stdin del **Cat canónico** (`cat_compact.mal`, sha256 `dd8f9b106dd4b25cf190a2fa1cf7f1b03db08d2cb30d4144f8791d46a347079b`), ejecutado bajo mb_ref, olmstead_1998 (fuentes pinned por SHA-256), y clasifica lo que sale por stdout con **linguist 9.7.0**, la copia vendorada en `vendor/source_snapshot` (no la gema publicada).

Contrato: `CONTRACT_CAT_FED`. Budget de pasos mb_ref: 1200000000; timeout por proceso: 600.0 s (olmstead no tiene budget: depende del timeout).

El runtime de linguist se construyo en `/tmp/malboguidstic_linguist_rt` (fuera del repo): lexer nativo `linguist.so` + `samples_data.rb` generado (5871252 B, byte-estable entre dos corridas: True).

## Cadena de ejecucion (por artefacto)

| Eslabon | Conteo sobre 4278 |
|---|---|
| files_present | 4278 |
| snapshot_sha_matches_inventory | 4278 |
| cat_output_is_exact_bytes | 4278 |
| cat_output_sha_matches_inventory | 4278 |
| differential_engines_agree | 4278 |
| mb_ref_halt | 4278 |
| olmstead_1998_halt | 4278 |

## Afirmaciones

- CAT_FED_BYTES_REACH_LINGUIST = DEMONSTRATED (4278/4278) — el Cat reproduce el archivo byte a byte y esas bytes se clasifican
- LINGUIST_CLASSIFICATION_PRESERVED_THROUGH_MALBOLGE = DEMONSTRATED (4278/4278)
- LINGUIST_DECISION_FLAGS_PRESERVED (generated/docs/vendored/type/group) = DEMONSTRATED (4278/4278)
- CONTROL_SENSIBILIDAD_AL_CONTENIDO (sobre los primeros 64 bytes, misma ruta) = 211/4278 cambian de idioma (dominado por la ruta: la concordancia anterior no demuestra fidelidad de contenido por si sola)
- CONTROL_NEGATIVO (contenido vacio) = DEMONSTRATED (4278/4278 devuelven NIL)
- CONTROL_DETERMINISMO (mismo blob dos veces) = DEMONSTRATED (4278/4278)
- LINGUIST_CLASSIFIES_SOURCE (no NIL) = 4235/4278
- MALBOLGE_RECOGNIZED_BY_LINGUIST = NEGATIVE (cat_compact.mal, en su propia ruta, clasificado como: NIL)
- CATALOG_FILES_WITH_NO_OWN_PROGRAM_REACHED = DEMONSTRATED (2673/2673: sin el Cat no tienen ninguna ruta Malbolge)
- BINARY_ENTRIES_REPRODUCED_BYTE_EXACT = DEMONSTRATED (20/20) — nunca se habia medido: el nivel 3 solo barría TEXT

## Clasificacion por tipo de entrada

Un `from_cat coincide` entre dos `NIL` no dice nada: la columna siguiente pide que ambos lados tengan idioma.

| entrada | archivos | con idioma | `from_cat` coincide | coincide con idioma | `prefix64` coincide |
|---|---|---|---|---|---|
| BINARY | 20 | 3 | 20 | 3 | 20 |
| TEXT | 4258 | 4232 | 4258 | 4232 | 4047 |

## Alcance y limites

- Poblacion: entradas TEXT del inventario (nivel 3, catalogo completo) + las 20 BINARY. Bytes cubiertos: 32945606.
- Las 3 entradas `SYMLINK` del inventario NO estan en el snapshot vendido (3 ausentes: samples/Ant Build System/filenames/build.xml, samples/Markdown/symlink.md, test/fixtures/SVG/alg_schema.link.svg): constan como `[ABSENT]`, no como acuerdo.
- `prefix64` corta el archivo a 64 bytes dejando la ruta intacta: 211/4278 cambian de veredicto. Ese control SI es independiente de la paridad byte a byte, porque compara dos contenidos distintos en la misma ruta.
- El Cat no incorpora los bytes del archivo en el programa: no hay artefacto `.mal` por archivo en este nivel, asi que su cobertura no sustituye a la del nivel 2.
- `from_cat_equals_source` se clasifica en la MISMA ruta logica que `source` y con los MISMOS bytes, asi que su concordancia esta implicada por la paridad byte a byte: valida el banco de pruebas, no es evidencia independiente de fidelidad.
- `jobs.jsonl` viaja al pack con las rutas de host sustituidas por tokens (`{SNAPSHOT}`, `{STAGE}`, `{REPO}`…); la copia absoluta queda en el workdir. El pack se niega a sellarse si algún archivo conserva una ruta absoluta del host.
- No se midio el costo de sintesis; este tool no llama a `malbolge-generator`.
- NOT_DEMONSTRATED: que un clasificador externo a este repositorio (la gema publicada `github-linguist`) de el mismo resultado; aqui solo se usa la version del snapshot.
