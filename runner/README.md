# bratbox-night — v10.10.4 (magnum opus offline build)

Jasmine's playable night: the ogre-shader rhythm game, her live agency
director, and the dialogue writer, packed to run on your own machine.

## Run it

```bash
cd scene/runner
bash run_scene.sh --writer elevenlabs   # her real ElevenLabs voice, live per line
bash run_scene.sh --writer deck         # offline: pre-rendered marisol deck, no API needed
bash run_scene.sh --tunnel none         # local only (default: localhost.run tunnel)
```

Online voice uses `eleven_flash_v2_5` by default (half the credits per
character). For the most expressive renders at ~2x cost:
`bash run_scene.sh --writer elevenlabs --model eleven_v3`.

`run_scene.sh` prints a PLAY link when ready. Needs Python 3 and one
package: `pip install websockets` (the browser server's only dependency;
everything else is stdlib). No API key or quota needed for voices — the
offline voice decks (below) cover every line.

## What's in this build

- **Exchange-doctrine dialogue** — every beat is a real conversation: her line
  + his reply authored as one unit (`exchanges.py`, 245 pairs across 10
  categories; direction in `dialogue_direction.md`). No camp one-liners.
- **v10.10.2 fixes** — the 17-second insta-complete in unbroken mode is dead;
  sessions play their full authored arc. The writer survives normal gaps
  between beats instead of exiting early.
- **v10.10.4 dialogue** — all 245 exchanges rewritten: her lines are theatrical
  mini-scenes (25-45 words) where she narrates, reacts, and directs the whole
  interaction, so they land with or without his voice; his replies are longer
  too, a real back-and-forth. No short quips, no one-liners. Offline voice
  decks re-rendered for the new lines (490 clips).
- **v10.10.3 fixes** — fiend's circuit-breaker silence is dead: when
  ElevenLabs is unreachable he goes straight to his offline voice instead
  of going silent. Offline voice decks ship in the zip (below), so both
  voices work with zero quota and no extra installs.
- **Voice fallbacks** — if ElevenLabs is unreachable or its quota is spent,
  her exchange lines render on the fly with the local `tts` glossy-pendant
  voice and his with the `tts` mild-yarn voice (Andrew's picks 2026-09-25 —
  she steps up, mid and smoky; he reads softboi, not fuckboy); a circuit
  breaker stops burning failed API calls. When the breaker is tripped he
  goes straight to his offline voice instead of going silent.
- **Offline voice decks** — `runner/voice_cache/` ships 490 pre-rendered
  clips (her 245 exchange lines in glossy pendant, his 245 in mild yarn),
  so the scene is fully voiced on machines without the `tts` binary and
  without any API quota. The writer checks the deck before calling `tts`.
- **Agency kit** — surge moves, tempo control, note mischief, body state,
  brat score, fiend-arousal 0–100 with the empty-chair rule at peak.

## Layout

- `scene/ogre_director_v2/` — the game (ogre_shader_v5.py)
- `scene/ogre_director/` — classic director assets
- `scene/runner/` — launcher, director, writers, server, tunnel helper

`runs/` sessions are created at runtime and are not shipped.
