# Barrido del corpus nivel 2 por el pipeline linguist — 20261102T043612Z

Ejecuta los artefactos `.mal` commiteados bajo mb_ref, olmstead_1998 (pinned por SHA-256), decodifica la envoltura con el codec del repo y clasifica el resultado con **linguist 9.7.0**, la copia vendorada en `vendor/source_snapshot` (no la gema publicada).

El runtime de linguist se construyo en `/tmp/malboguidstic_linguist_rt` (fuera del repo): lexer nativo `linguist.so` + `samples_data.rb` generado (5871252 B, byte-estable entre dos corridas: True).

## Cadena de ejecucion (por artefacto)

| Eslabon | Conteo sobre 1605 |
|---|---|
| files_present | 1605 |
| artifact_sha_matches_manifest | 1605 |
| snapshot_sha_matches_manifest | 1605 |
| output_is_committed_envelope | 1605 |
| envelope_decodes_valid | 1605 |
| decoded_matches_snapshot | 1605 |
| decoded_sha_matches_manifest | 1605 |
| differential_engines_agree | 1605 |
| mb_ref_halt | 1605 |
| olmstead_1998_halt | 1605 |

## Afirmaciones

- LEVEL2_ARTIFACTS_EXECUTE_AND_REPRODUCE = DEMONSTRATED (1605/1605)
- LINGUIST_CLASSIFICATION_PRESERVED_THROUGH_MALBOLGE = DEMONSTRATED (1605/1605)
- LINGUIST_DECISION_FLAGS_PRESERVED (generated/docs/vendored/type/group) = DEMONSTRATED (1605/1605)
- CONTROL_SENSIBILIDAD_AL_CONTENIDO (sobre envoltura sin decodificar) = 361/1605 cambian de idioma (el pipeline SI mira el contenido)
- CONTROL_NEGATIVO (contenido vacio) = DEMONSTRATED (1605/1605 devuelven NIL)
- CONTROL_DETERMINISMO (mismo blob dos veces) = DEMONSTRATED (1605/1605)
- MALBOLGE_RECOGNIZED_BY_LINGUIST = NEGATIVE (los 1605 programas .mal clasificados como idioma: 0)
- LINGUIST_CLASSIFIES_SOURCE (no NIL) = 1580/1605

## Alcance y limites

- Poblacion: artefactos con `malbolge.status == PASS` en el manifest commiteado.
- Los 2653 archivos SKIPPED_TOO_LARGE no tienen programa propio y no entran en este barrido.
- `from_mal` se clasifica en la MISMA ruta logica que `source` y con los MISMOS bytes, asi que su concordancia esta implicada por la paridad byte a byte: valida el banco de pruebas, no es evidencia independiente de fidelidad.
- Clasificar la envoltura sin decodificar mide cuanto depende linguist de la ruta: 361/1605 de los archivos cambiaron de idioma.
- `jobs.jsonl` viaja al pack con las rutas de host sustituidas por tokens (`{SNAPSHOT}`, `{STAGE}`, `{REPO}`…); la copia absoluta queda en el workdir. El pack se niega a sellarse si algún archivo conserva una ruta absoluta del host.
- No se midio el costo de sintesis; este tool no llama a `malbolge-generator`.
- NOT_DEMONSTRATED: que un clasificador externo a este repositorio (la gema publicada `github-linguist`) de el mismo resultado; aqui solo se usa la version del snapshot.
