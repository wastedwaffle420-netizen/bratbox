#!/bin/bash
# run_scene.sh — launch a bratbox scene night.
# Usage: ./run_scene.sh [--tunnel localhost.run|cloudflared|none] [--wait-ms 30000] [--port 18731]
set -u
# resolve paths relative to this script, before cd'ing anywhere
RUNNER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
SCENE_DIR="$(cd "$RUNNER_DIR/.." && pwd)"
cd "$RUNNER_DIR"

# ── local-kit mode: full speed, story intact ─────────────────────────────────
# tweak these any night you want a different flavor
: "${JASMINE_SLOWMO:=1}"        # 5 = fifth-speed (was for reading); 1 = full speed
export JASMINE_SLOWMO
: "${JASMINE_VOICE_GAP_S:=0}"    # v9: zero dead air between lines — she steps
                                # over her own thoughts; overlap below paces it
export JASMINE_VOICE_GAP_S
: "${JASMINE_VOICE_OVERLAP:=0.92}"  # v9.1: rapid-fire, 5-10% overlap — the
                                # next line steps on the previous one's tail,
                                # never two full sentences at once
export JASMINE_VOICE_OVERLAP
: "${FIEND_VOICE_ID:=pgrEFhHEIrYm4BF8476L}"  # v9: fiend speaks again, his
                                # real voice, invisible dialogue (voice only)
export FIEND_VOICE_ID
: "${FIEND_TTS:=auto}"          # v10.6: fiend's voice engine — auto (default:
                                # ElevenLabs, local Piper synth on ANY failure),
                                # elevenlabs (force, raises on failure),
                                # piper (force offline — zero credit spend)
export FIEND_TTS
: "${FIEND_CHANCE:=1.0}"       # v10: every dialogue beat is an exchange
                                # (her line + his reply). 0 = her only.
export FIEND_CHANCE
: "${FIEND_SOFTSAD_CHANCE:=0.07}" # v10.1: R6 softsad surfacing — chance any
                                # fiend reply cracks into Ash Lynx mode.
export FIEND_SOFTSAD_CHANCE
: "${FIEND_LEDGER_CHANCE:=0.20}"  # v10.2: the ledger — chance his reply ends
                                # in a bit finisher (honest fluster / beast).
export FIEND_LEDGER_CHANCE
: "${ESCALATION_CHANCE:=0.15}"    # v10.3: the 😳 feedback loop — chance a
                                # heated/feral beat becomes a paired
                                # escalation exchange. ElevenLabs-only.
export ESCALATION_CHANCE
: "${ESCALATION_CREST_AT:=3}"     # v10.4: off-ramp — loop beats before it
                                # can crest into the finale announce, and
                                # only at edging/climax (his close/peak).
export ESCALATION_CREST_AT
: "${DAYLIFE_CHANCE:=0.25}"      # v10.4: daylife — chance an early-night
                                # tease/opener becomes him asking about her
                                # day. He lives in her world. Rude otherwise.
export DAYLIFE_CHANCE
: "${DAYLIFE_SEQ_MAX:=30}"       # v10.4: daylife window — first N beats.
export DAYLIFE_SEQ_MAX
: "${JASMINE_AUDIO_ONLY:=1}"    # audio-only build: her voice carries it, no
                                # dialogue text on screen (nothing to desync)
export JASMINE_AUDIO_ONLY
: "${BRATBOX_UNBROKEN:=1}"      # v10.5: unbroken rhythm — no intro, no choice
                                # modals, no interludes, no post-rhythm scenes,
                                # no milestones/bathroom/vignettes. Just the
                                # rhythm, with the dialogue on top. 0 = legacy
                                # full story flow.
export BRATBOX_UNBROKEN

: "${LOCKKEY_OGRE_EXPERIENCE_MODE:=elastic_grotesque}"
                                # v10.8: the full elastic-grotesque experience —
                                # suckler/shaft/tract visuals + elastic climax
                                # grammar. Was defaulting to "suggestive" (plain
                                # rhythm) because nothing set it.
export LOCKKEY_OGRE_EXPERIENCE_MODE

: "${LOCKKEY_NOTE_CLICKS:=1}"   # v10.8: browser-audible hit/miss ticks.
                                # 0 = silent.
export LOCKKEY_NOTE_CLICKS

TUNNEL=localhost.run   # localhost.run (default: free, no signup, proxy-proof)
                      # | cloudflared | none
WAIT_MS=30000
PORT=18731
WRITER=none
MODEL=eleven_flash_v2_5  # elevenlabs TTS model: flash (half credits) | eleven_v3 (most expressive, ~2x)
while [ $# -gt 0 ]; do
  case "$1" in
    --no-tunnel) TUNNEL=none; shift;;  # legacy alias
    --tunnel) TUNNEL="$2"; shift 2;;   # localhost.run | cloudflared | none
    --wait-ms) WAIT_MS="$2"; shift 2;;
    --port) PORT="$2"; shift 2;;
    --writer) WRITER="$2"; shift 2;;  # none | stub | deck | elevenlabs
    --model) MODEL="$2"; shift 2;;    # elevenlabs model override
    *) echo "unknown arg $1"; exit 1;;
  esac
done

RUNS_DIR="$SCENE_DIR/runs"
SESSION="$RUNS_DIR/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$SESSION"/{fifo,inbox,outbox,clips}
TOKEN="$(head -c 18 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c 24)"
GAME_DIR="$SCENE_DIR/ogre_director_v2"
VENV="$SCENE_DIR/.venv/bin/python"
# local kit: fall back to system python3 when the venv isn't shipped
if [ -x "$VENV" ]; then PY="$VENV"; else PY="python3"; fi

# find a free port
while (exec 3<>/dev/tcp/127.0.0.1/$PORT) 2>/dev/null; do PORT=$((PORT+1)); done

echo "session: $SESSION"
echo "$SESSION" > "$RUNS_DIR/current"
echo "$TOKEN" > "$SESSION/token" && chmod 600 "$SESSION/token"
echo "{\"started\": $(date +%s), \"port\": $PORT, \"wait_ms\": $WAIT_MS}" > "$SESSION/session.json"

"$PY" "$PWD/director.py" --session "$SESSION" --wait-ms "$WAIT_MS" \
  > "$SESSION/director_stdout.log" 2>&1 &
DPID=$!
"$PY" "$PWD/server.py" --session "$SESSION" --port "$PORT" --token "$TOKEN" \
  --game-dir "$GAME_DIR" --wait-ms "$WAIT_MS" \
  > "$SESSION/server_stdout.log" 2>&1 &
SPID=$!

# Voice path: elevenlabs needs a key — from the env (his PC) or the authd
# surrogate (this VM). Probe the same resolution the writer uses, so the
# launcher never downgrades a working setup to the deck.
if [ "$WRITER" = "elevenlabs" ]; then
  KEY_MODE="$("$PY" "$PWD/elevenlabs_writer.py" --probe-key 2>/dev/null || echo none)"
  if [ "$KEY_MODE" = "none" ]; then
    echo "!! no ElevenLabs key found (env or authd) — her real voice can't connect."
    echo "!! Falling back to the offline deck (marisol)."
    WRITER="deck"
  fi
fi
if [ "$WRITER" = "elevenlabs" ]; then
  echo "VOICE: Jazz — her real ElevenLabs voice, live per line (key detected)"
elif [ "$WRITER" = "deck" ]; then
  echo "VOICE: marisol — offline deck, 1590 lines, no key needed"
fi
echo "MODE: $LOCKKEY_OGRE_EXPERIENCE_MODE (suckler/shaft/tract visuals; override"
echo "      with LOCKKEY_OGRE_EXPERIENCE_MODE=suggestive|degradation)"
if [ "$LOCKKEY_NOTE_CLICKS" = "1" ]; then
  echo "SFX: note hit/miss ticks + squish/toot foley on (LOCKKEY_NOTE_CLICKS=0 to mute)"
fi

# offline writer (local kit): deck = voiced lines + agency plays, stub = plumbing test
# elevenlabs = deck lines rendered LIVE through her real ElevenLabs voice,
# delivery shaped per-beat (needs net + key: ELEVENLABS_API_KEY env or authd)
WPID=""
case "$WRITER" in
  deck) "$PY" "$PWD/deck_writer.py" "$SESSION" > "$SESSION/writer_stdout.log" 2>&1 & WPID=$!;;
  stub) "$PY" "$PWD/stub_writer.py" "$SESSION" > "$SESSION/writer_stdout.log" 2>&1 & WPID=$!;;
  elevenlabs) "$PY" "$PWD/elevenlabs_writer.py" "$SESSION" --model "$MODEL" > "$SESSION/writer_stdout.log" 2>&1 & WPID=$!;;
esac

cleanup() {
  echo; echo "shutting down scene…"
  kill "$DPID" "$SPID" 2>/dev/null
  [ -n "${TPID:-}" ] && kill "$TPID" 2>/dev/null
  [ -n "$WPID" ] && kill "$WPID" 2>/dev/null
  sleep 1
  kill -9 "$DPID" "$SPID" ${TPID:-} 2>/dev/null
  [ -n "$WPID" ] && kill -9 "$WPID" 2>/dev/null
  python3 - "$SESSION" <<'EOF'
import json, sys, time
s = sys.argv[1] + "/session.json"
try:
    d = json.load(open(s)); d["ended"] = int(time.time()); json.dump(d, open(s, "w"), indent=1)
except Exception: pass
EOF
  echo "scene closed. logs in $SESSION"
}
trap cleanup INT TERM

# wait for the server
for i in $(seq 1 60); do
  (exec 3<>/dev/tcp/127.0.0.1/$PORT) 2>/dev/null && break
  sleep 1
done

TUNNEL_URL=""
TPID=""
if [ "$TUNNEL" != "none" ]; then
  case "$TUNNEL" in
    localhost.run)
      # free, no signup, works through the egress proxy (verified 2026-09-25).
      # the nokey user skips the key check (their FAQ); -tt (a shell, no -N)
      # is required or the server never prints the URL — parse
      # https://<id>.lhr.life out of the log. behind a proxy the bundled
      # helper CONNECTs out (needs HTTPS_PROXY); without one, plain ssh dials
      # direct — same command both ways. (array, not a string: the
      # ProxyCommand value contains spaces and must stay one ssh argument.)
      SSH_ARGS=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null
                -o ConnectTimeout=15 -o ServerAliveInterval=60)
      if [ -n "${HTTPS_PROXY:-}" ] && [ -x "$RUNNER_DIR/connect_proxy.py" ]; then
        SSH_ARGS+=(-o "ProxyCommand=$RUNNER_DIR/connect_proxy.py %h %p")
      fi
      ssh -tt "${SSH_ARGS[@]}" -R "80:localhost:$PORT" nokey@ssh.localhost.run \
        > "$SESSION/tunnel.log" 2>&1 &
      TPID=$!
      for i in $(seq 1 45); do
        TUNNEL_URL="$(grep -a -o 'https://[a-z0-9]*\.lhr\.life' "$SESSION/tunnel.log" 2>/dev/null | head -1)"
        [ -n "$TUNNEL_URL" ] && break
        sleep 1
      done
      ;;
    cloudflared)
      cloudflared tunnel --url "http://127.0.0.1:$PORT" --no-autoupdate \
        > "$SESSION/tunnel.log" 2>&1 &
      TPID=$!
      for i in $(seq 1 45); do
        TUNNEL_URL="$(grep -o 'https://[a-zA-Z0-9.-]*\.trycloudflare\.com' "$SESSION/tunnel.log" 2>/dev/null | head -1)"
        [ -n "$TUNNEL_URL" ] && break
        sleep 1
      done
      ;;
    *) echo "unknown --tunnel $TUNNEL (localhost.run | cloudflared | none)"; exit 1;;
  esac
  echo "$TUNNEL_URL" > "$SESSION/tunnel_url"
fi

echo "────────────────────────────────────────"
if [ -n "$TUNNEL_URL" ]; then
  echo "PLAY: ${TUNNEL_URL}/?token=${TOKEN}"
else
  echo "LOCAL (no tunnel): http://127.0.0.1:${PORT}/?token=${TOKEN}"
fi
echo "director pid $DPID · server pid $SPID · tunnel pid ${TPID:-none} · writer pid ${WPID:-none} ($WRITER)"
echo "inbox: $SESSION/inbox  (spawn the Jasmine writer against this session)"
echo "────────────────────────────────────────"
echo "READY"

wait "$SPID" 2>/dev/null
cleanup
