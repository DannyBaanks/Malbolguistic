#!/bin/sh
# Reconstruye exactamente el runtime usado en esta corrida (fuera del repo).
# 1. gemas de usuario que este tool NO instala por su cuenta:
#    gem install --user-install charlock_holmes mini_mime
# 2. copia del linguist pinned + lexer nativo + DB de samples:
# desde la raiz del repo (sin rutas de host: el repositorio es publico):
SNAP='vendor/source_snapshot'
W="${TMPDIR:-/tmp}/malboguidstic_linguist_rt"
rm -rf "$W"; mkdir -p "$W"
cp -r "$SNAP/lib" "$SNAP/samples" "$SNAP/ext" "$W/"
cd "$W/ext/linguist" && ruby extconf.rb && make -j4
cp linguist.so "$W/lib/linguist/"
ruby -I"$W/lib" tools/gate_adapters/linguist_gen_samples.rb "$W/lib/linguist/samples_data.rb"
# 3. barrido:
python3 tools/verify_linguist_pipeline.py --workdir "$W" --level 3 --include-non-text
# Pins de esta corrida:
#   linguist.so      ccd681d9346a18228376aca76489e48fbfdc11536837fd515b0856cad18567d3
#   samples_data.rb  e6922461252aee2914cb1895ad8a8c63b47cc59f0b6d1048ade77f0d2532e0c7
#   linguist.rb      45923b0449f4c154e74e6c6ee69e94ece08de0fee45913e6897ad08efcc989d7
#   mb_ref.c         a8ce19c2dc93e36f8c9c24a271c4187d68f922b9455262c7199a009763fe3ad3
#   olmstead_1998.c  05abd38e78b266050c5a5e8cc5b36584daa5bbdeb404bfb351de7ea6fa26b510
#   cat_compact.mal  dd8f9b106dd4b25cf190a2fa1cf7f1b03db08d2cb30d4144f8791d46a347079b
