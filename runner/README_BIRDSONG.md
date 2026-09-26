# bratbox — birdsong build

The simple one. Terminal game, offline voices, nothing else.

## What's in the zips

- `bratbox-birdsong-v11-code.zip` — the game + runner scripts
- `bratbox-birdsong-v11-deck1.zip`, `-deck2.zip`, … — her + his voice clips

Extract **all** of them into the same folder (the deck zips merge into
`bratbox-birdsong/scene/runner/voice_cache/`).

## Run it

```bash
cd bratbox-birdsong/scene/runner
bash run_simple.sh
```

The game takes your terminal. Ctrl-C ends the night.

Needs: `python3` (+ `pip install websockets` only if the director complains —
it shouldn't for this build). Audio plays through whatever's available:
afplay (mac), paplay/aplay/ffplay/mpg123 (linux). Override with
`JASMINE_AUDIO_PLAYER="your player"` if it picks wrong.

## The contract

- **Rhythm only** (`BRATBOX_UNBROKEN=1`), difficulty maxed (`LOCKKEY_INTENSITY=rough`)
- **Her words, verbatim** — the full birdsong corpus from the original
  vendor, exactly as written. The writer never authors a line; it only
  gives the game's lines a voice.
- **Voices** — glossy pendant (her), mild yarn (him), pre-rendered, offline.
- **Bed** — the original wotw idle/elastic grotesque renderer via the exact
  bridge, with sweat / musk / urine on.
- **Toots** — the old flavor takes (bashful/power/submissive), played locally.

## Tuning knobs (env)

| var | default | what |
|---|---|---|
| `LOCKKEY_INTENSITY` | `rough` | `gentle`/`steady`/`rough` |
| `LOCKKEY_OGRE_EXPERIENCE_MODE` | `elastic_grotesque` | bed style |
| `JASMINE_SLOWMO` | `1` | `5` for the old slow flavor |
| `JASMINE_VOICE_GAP_S` | `0` | dead air between lines |
| `JASMINE_AUDIO_PLAYER` | auto | audio player command |
| `ONRYO_TACTILE_SURFACE` | `1` | sweat; `0` disables |
| `ONRYO_TACTILE_MUSK` | `1` | musk; `0` disables |
| `LOCKKEY_URINATION_PRESENTATION` | `1` | urine; `0` disables |

Logs per night land in `scene/runs/<timestamp>/`.
