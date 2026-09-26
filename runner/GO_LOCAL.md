# Jasmine's Scene Night — local kit

One command, one night. This runs the whole Bratbox scene on your own PC:
the game, the director, her offline writer, and the browser UI.

## What you get

- The full Ogre Shader V5 scene with Jasmine's agency kit: surge moves
  (buck, wiggle, arch, grind, clench, melt, present, shy), tempo control,
  note mischief, blush lighting, body state, toots in three flavors, pouts,
  halftime, hijacks, room weather, brat scoring.
- Her voice: 74 fresh marisol lines, pre-rendered — picked by live context
  (how heated things are, whether she's pouting, whether she just tooted,
  finale, aftercare). No repeats within a night. None of these are the old
  corpus takes.
- Real toot audio in your browser (power / submissive / bashful takes).
- The hidden arousal stat, the finale, and Soft_Glow_Anchor aftercare.
- Optional mic squeak detection (browser-local, numbers only, off by default).

**House mode: story married to rhythm.** Vignettes, interludes, and story
beats all play — story is never removed — and her dialogue lands *inside*
the rhythm: every beat she answers with a fresh line + voice while you keep
playing. The game runs at full speed (the old slow-mo was for reading; her
voice carries it now), and her tempo agency can push it faster or slower as
the night heats up — up to 1.5x when she's feeling spicy.

Want the old slow flavor some night? Run it with:
```
JASMINE_SLOWMO=5 bash run_scene.sh --no-tunnel --writer deck
```

The offline writer isn't me writing live — it's a deck of her lines played
smart. The full live-writer nights (me writing every line fresh, in the
moment) happen in hosted sessions.

## Her real voice (ElevenLabs writer)

`--writer elevenlabs` plays the same deck of lines, but every line is
rendered **live through her real ElevenLabs voice** ('Jazz'), with delivery
shaped per-beat by the full game packet — her state only, never yours.
Tease lines get a laugh in them, heated lines come out breathless and
excited, aftercare drops to a whisper. The packet itself never leaves your
machine; only her line + delivery settings go out.

Your PC needs your ElevenLabs API key in the environment (one time per
terminal):
```
export ELEVENLABS_API_KEY="your-key-here"
bash run_scene.sh --no-tunnel --writer elevenlabs
```
Without the key she still plays — lines show as subtitles, just unvoiced.
Each night costs roughly 5–10k ElevenLabs credits on the default
`eleven_v3` model (flash model is cheaper/faster but drops the delivery
nuance).

**Key notes for future-you:**
- The writer reads `ELEVENLABS_API_KEY` once at startup. If you rotate or
  re-export the key, you must Ctrl+C and relaunch the scene — re-exporting
  alone won't reach the already-running writer.
- If she's suddenly silent, check the writer log:
  `grep -m3 "tts failed" $(cat ~/bratbox-night/scene/runs/current)/writer_stdout.log`
  `HTTP 401 ... Invalid API key` means the exported key is dead or wrong —
  export the good one and restart.

## Setup (Windows + WSL2)

1. **Install WSL2** (one time). In an admin PowerShell:
   `wsl --install -d Ubuntu` — then reboot.
2. **Open Ubuntu**, install Python:
   `sudo apt update && sudo apt install -y python3 python3-pip`
3. **Unzip this kit** somewhere, e.g. `~/bratbox-night`, so you have
   `~/bratbox-night/scene/runner/run_scene.sh`.
4. **Install the one dependency:**
   `pip3 install websockets` (if pip complains, add `--break-system-packages`)
5. **Play:**
   ```
   cd ~/bratbox-night/scene/runner
   bash run_scene.sh --no-tunnel --writer deck
   ```
   It prints a `PLAY:` link — open it in Edge/Chrome on Windows.
   (WSL2 forwards localhost to Windows automatically.)

## Playing

- The scene opens in a terminal in your browser. Press the keys it shows.
- She reacts to how you play: rhythm, pressure, teasing, ignoring her bids.
- Safeword is `pandora`. Green means go.
- Ctrl+C in the Ubuntu terminal ends the night. Logs live in `scene/runs/`.

## Troubleshooting

- **Port busy?** The script auto-bumps to the next free port and prints it.
- **`python3: command not found`?** Step 2 didn't finish — reinstall python3.
- **No audio?** Clips play through the browser — check the tab isn't muted.
  The server machine needs no speakers.
- **She's quiet?** Give it ~30 seconds — the first beats take a moment to
  arrive, and the writer answers each one as it lands.

## v5 changes (2026-09-25)
- Rapid-fire pacing: Jasmine's lines are timed by actual spoken clip length
  (MP3 duration) + a short `JASMINE_VOICE_GAP_S` breath (default 0.4s) in
  run_scene.sh. Fiend turns take no time and no screen space.
- Interludes removed: the 35%-per-cycle mode interludes no longer trigger.
  Her dialogue now lives entirely in the rhythm (ambient exchanges + live
  writer). Interlude pools stay in the code, dormant.
- Sweat/musk/tactile overlay now defaults ON (was off unless ONRYO_LAB=1).
  `ONRYO_TACTILE_SURFACE=0` still disables it.
- Toots: writer now fires a real toot action when her pressure is high
  (~50%), plus the ambient ~5% base rate. Needs downward/squat pose + heat,
  as designed.
- Body state: the writer forwards her tracked sweat/musk on action beats so
  beads/wisps follow her actual heat.

## v6 changes (2026-09-25) — audio-only build
- AUDIO-ONLY: no dialogue text is drawn on screen at all. Her voice carries
  everything via the browser audio. This removes the visible desync problem
  entirely (nothing to be out of sync with). `JASMINE_AUDIO_ONLY=1` (default)
  in run_scene.sh; set to 0 for the old subtitle behavior.
- Choice prompts (NARRATOR option hints like [A]/[S]/[SPACE]) are the one text
  exception — they're game controls, not dialogue, and she voices the question.
- Audio pacing moved to the WRITER: each voiced reply is held until the
  previous clip's real spoken length + `JASMINE_VOICE_GAP_S` (0.4s) has passed,
  so her voice never overlaps itself in the browser. Action-only beats are
  never delayed.
- Clip durations are now measured properly (ffprobe when present, else the
  correct bitrate heuristic). Deck clips are ~64kbps, not 128 — old estimates
  were ~2x short, which would have caused voice overlap.
- Line pool: 716 lines (was 97) across all 12 categories, all with marisol
  deck clips rendered. The live ElevenLabs writer uses the same pool and
  renders her real voice per line.
