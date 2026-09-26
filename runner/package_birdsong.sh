#!/usr/bin/env bash
# Package the birdsong build: code zip + voice deck zips (each <95MB).
# Run after render_birdsong.py and render_birdsong_nls.py complete.
set -u
BB=~/workspace/bratbox
OUT=~/workspace/bratbox/dist
mkdir -p "$OUT"
VER="${1:-v11}"

# ---- code zip: game + runner, no decks, no runs/caches ----
CODE_STAGING=/tmp/bb_code_pkg
rm -rf "$CODE_STAGING"
mkdir -p "$CODE_STAGING/bratbox-birdsong"
cd "$BB"
# game: all python modules + assets (the game imports many sibling modules)
mkdir -p "$CODE_STAGING/bratbox-birdsong/scene/ogre_director_v2"
for f in scene/ogre_director_v2/*.py; do
  case "$f" in
    *jasmine_director_example*) continue;;
  esac
  cp "$f" "$CODE_STAGING/bratbox-birdsong/scene/ogre_director_v2/" 2>/dev/null
done
# lightmaps + configs live next to the game file
cp scene/ogre_director_v2/*.txt \
   "$CODE_STAGING/bratbox-birdsong/scene/ogre_director_v2/" 2>/dev/null
cp scene/ogre_director_v2/*.json \
   "$CODE_STAGING/bratbox-birdsong/scene/ogre_director_v2/" 2>/dev/null
cp -r scene/ogre_director_v2/assets \
      "$CODE_STAGING/bratbox-birdsong/scene/ogre_director_v2/" 2>/dev/null
[ -d scene/ogre_director_v2/wotw_bratbox ] && cp -r scene/ogre_director_v2/wotw_bratbox \
      "$CODE_STAGING/bratbox-birdsong/scene/ogre_director_v2/" 2>/dev/null
# runner (scripts only)
mkdir -p "$CODE_STAGING/bratbox-birdsong/scene/runner"
for f in scene/runner/*.py scene/runner/*.sh scene/runner/*.bat; do
  case "$f" in
    *render_*|*pre_render*|*package_birdsong*) continue;;
    # deck_writer.py, line_deck.py, exchanges.py, fiend_lines.py are all
    # runtime modules (imported by elevenlabs_writer/offline_writer).
    # Only render scripts are excluded above.
  esac
  cp "$f" "$CODE_STAGING/bratbox-birdsong/scene/runner/" 2>/dev/null
done
chmod +x "$CODE_STAGING/bratbox-birdsong/scene/runner/run_simple.sh"
cp "$BB/scene/runner/README_BIRDSONG.md" "$CODE_STAGING/bratbox-birdsong/README.md"
# empty voice_cache dirs so the tree is right after deck zips land
mkdir -p "$CODE_STAGING/bratbox-birdsong/scene/runner/voice_cache"/{jasmine,fiend}
find "$CODE_STAGING" -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null
cd "$CODE_STAGING"
zip -qr "$OUT/bratbox-birdsong-${VER}-code.zip" bratbox-birdsong
echo "code: $(du -h "$OUT/bratbox-birdsong-${VER}-code.zip" | cut -f1)"

# ---- deck zips: split voice_cache into <95MB chunks ----
cd "$BB/scene/runner/voice_cache"
i=1; cur=/tmp/bb_deck_$i; rm -rf /tmp/bb_deck_*
mkdir -p "$cur/bratbox-birdsong/scene/runner/voice_cache"/{jasmine,fiend}
for sub in jasmine fiend; do
  for f in "$sub"/*.mp3; do
    [ -f "$f" ] || continue
    sz=$(du -sb "$cur" | cut -f1)
    if [ "$sz" -gt 95000000 ]; then
      (cd /tmp/bb_deck_$i && zip -qr "$OUT/bratbox-birdsong-${VER}-deck$i.zip" bratbox-birdsong)
      echo "deck$i: $(du -h "$OUT/bratbox-birdsong-${VER}-deck$i.zip" | cut -f1)"
      i=$((i+1)); cur=/tmp/bb_deck_$i
      mkdir -p "$cur/bratbox-birdsong/scene/runner/voice_cache"/{jasmine,fiend}
    fi
    cp "$f" "$cur/bratbox-birdsong/scene/runner/voice_cache/$sub/"
  done
done
(cd /tmp/bb_deck_$i && zip -qr "$OUT/bratbox-birdsong-${VER}-deck$i.zip" bratbox-birdsong)
echo "deck$i: $(du -h "$OUT/bratbox-birdsong-${VER}-deck$i.zip" | cut -f1)"
echo "--- dist ---"; ls -lh "$OUT/"
