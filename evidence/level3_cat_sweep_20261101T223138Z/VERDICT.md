# Nivel 3 — corpus reproducido por Cat canónico (20261101T223138Z)

Un solo programa Malbolge Classic, `cat_compact.mal` (7596 bytes, sha256 `dd8f9b106dd4b25cf190a2fa1cf7f1b03db08d2cb30d4144f8791d46a347079b`), con cada archivo del catálogo por stdin.

Motor: mb_ref, olmstead (fuentes .c pinneadas, recompiladas con gcc -O2 antes de la corrida). Cinta canónica 59049 = 3^10; `in` en EOF = 59048.

| Medida | Valor |
|---|---|
| archivos en scope | 4258 |
| medidos | 4258 |
| bytes cubiertos | 31647823 |
| exacto bajo `mb_ref` | 4258 |
| exacto bajo `olmstead` | 4258 |
| acuerdo entre motores | 4258 |
| fallos | 0 |
| sha256 vs inventory | 0 |
| pared (s) | 82.11 |

- CONTRACT_CAT_FED_COVERS Catalog TEXT = DEMONSTRATED (4258/4258)
- Scope: entradas `TEXT` del catálogo. Las 20 `BINARY` y 3 `SYMLINK` de `manifest/source_inventory.json` NO entran en esta corrida.
- Este nivel NO sustituye al nivel 2: el Cat no incorpora los bytes del archivo en el programa, así que no hay artefacto por archivo aquí.
