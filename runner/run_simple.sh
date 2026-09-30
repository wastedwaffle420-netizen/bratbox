#!/usr/bin/env bash
# bratbox birdsong build — terminal + offline voices, nothing else.
#
#   bash run_simple.sh
#
# What it does:
#   - rhythm-only, max difficulty, elastic-grotesque bed
#   - the game's own birdsong dialogue, verbatim (never rewritten)
#   - every line voiced locally: glossy pendant (her), Sparkling Bracelet (him)
#   - sweat / musk / urine on
#   - no browser, no tunnel, no ElevenLabs, no network at all
#
# The game runs in THIS terminal (foreground). Director + TTS operator run
# behind it. Ctrl-C shuts the night down.

set -u
RUNNER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCENE_DIR="$(dirname "$RUNNER_DIR")"
GAME_DIR="$SCENE_DIR/ogre_director_v2"
RUNS_DIR="$SCENE_DIR/runs"
mkdir -p "$RUNS_DIR"

if [ -x "$SCENE_DIR/.venv/bin/python" ]; then PY="$SCENE_DIR/.venv/bin/python"; else PY="python3"; fi

STAMP="$(date +%Y%m%d-%H%M%S)"
SESSION="$RUNS_DIR/$STAMP"
mkdir -p "$SESSION"/{fifo,inbox,outbox,clips}
mkfifo -m 600 "$SESSION/fifo/game_to_director.fifo" 2>/dev/null || true
mkfifo -m 600 "$SESSION/fifo/director_to_game.fifo" 2>/dev/null || true
echo "{\"started\": $(date +%s)}" > "$SESSION/session.json"
echo "$SESSION" > "$RUNS_DIR/current"

# ---- the birdsong build contract ----
export BRATBOX_UNBROKEN="${BRATBOX_UNBROKEN:-1}"          # rhythm only
export LOCKKEY_INTENSITY="${LOCKKEY_INTENSITY:-rough}"    # difficulty maxed
export LOCKKEY_OGRE_EXPERIENCE_MODE="${LOCKKEY_OGRE_EXPERIENCE_MODE:-elastic_grotesque}"
export ONRYO_TACTILE_SURFACE="${ONRYO_TACTILE_SURFACE:-1}"  # sweat on
export ONRYO_TACTILE_MUSK="${ONRYO_TACTILE_MUSK:-1}"        # musk on
export LOCKKEY_URINATION_PRESENTATION="${LOCKKEY_URINATION_PRESENTATION:-1}"  # urine on
export JASMINE_SLOWMO="${JASMINE_SLOWMO:-1}"              # full speed; voice carries it
export JASMINE_VOICE_GAP_S="${JASMINE_VOICE_GAP_S:-2.0}"  # 2s breath between lines
export JASMINE_AUDIO_ONLY=0                              # show text AND play voice

# squish foley staging (was server.py's job; operator plays sfx_*.mp3 locally)
GOOEY="$GAME_DIR/assets/audio/jasmine/squish/gooey"
if [ -d "$GOOEY" ]; then
  i=0
  for src in "$GOOEY"/*.mp3; do
    [ -f "$src" ] || break
    [ $i -ge 4 ] && break
    cp -n "$src" "$SESSION/clips/sfx_squish_$i.mp3" 2>/dev/null || true
    i=$((i+1))
  done
fi

echo "session: $SESSION"
echo "mode: rhythm-only / intensity=$LOCKKEY_INTENSITY / bed=$LOCKKEY_OGRE_EXPERIENCE_MODE"
echo "voice: glossy pendant (her) + Sparkling Bracelet (him), offline deck"

"$PY" "$RUNNER_DIR/director.py" --session "$SESSION" \
  > "$SESSION/director_stdout.log" 2>&1 &
DPID=$!
"$PY" "$RUNNER_DIR/offline_writer.py" "$SESSION" \
  > "$SESSION/writer_stdout.log" 2>&1 &
WPID=$!

cleanup() {
  echo; echo "shutting down the night…"
  kill "$DPID" "$WPID" 2>/dev/null
  sleep 1
  kill -9 "$DPID" "$WPID" 2>/dev/null
  echo "logs in $SESSION"
}
trap cleanup INT TERM

# the game takes this terminal
cd "$GAME_DIR"
export TERM="${TERM:-xterm-256color}"
export JASMINE_DIRECTOR=1
export JASMINE_DIRECTOR_WAIT_MS="${JASMINE_DIRECTOR_WAIT_MS:-900}"
export JASMINE_FIFO_DIR="$SESSION/fifo"
exec "$PY" ogre_shader_v5.py
