# Jasmine SFX soundboard

Andrew's foley library for the Ogre Shader scene. Installed 2026-09-24.
All paths relative to `assets/audio/jasmine/`.

## Wired (live)

### Toots — hardcoded per flavor (Andrew's call)
The director sends `toot` with her agency flavor; the game pops the matching
take. Browser playback goes through the director → session `clips/` manifest
(the server has no speakers); local pygame plays the same files when the
game runs standalone.

| flavor (agency) | aka (Andrew) | takes | character |
|---|---|---|---|
| `power` | power | `toot/power/` ×3 | gross weighted bare — big, unapologetic |
| `submissive` | submission | `toot/submissive/` ×4 | deep sudden stomach — low, sudden release |
| `bashful` | humiliation | `toot/bashful/` ×3 | airy-but-cute — small embarrassed toot |

The bashful takes are the replacements Andrew made for the lost perfect cute
toot. Mourned, not replaced.

### Sloppy bed
`_pressure_sound("sloppy")` (the long wet bed for the second failure loop)
now plays the gooey melting slime takes (`squish/gooey/` ×4) instead of the
procedural pump.

## Installed, ready to wire

From `NEWSOUNDS_12_n0uf.zip` (70 wavs, `newsounds/`):

| dir | takes | obvious hook |
|---|---|---|
| `surge_greenpull/` | 4 | green surge pull SFX |
| `surge_redspank/` | 5 | red spank surge SFX |
| `climax_buildup/` | 4 | finale: buildup |
| `climax_release/` | 4 | finale: release |
| `aftercare_settling/` | 4 | Soft_Glow_Anchor aftercare bed |
| `wet_precise/` `wet_deep/` `wet_intimate/` | 6/8/8 | intimate wet foley pool |
| `elastic_finger/` `elastic_mouth/` `elastic_rhythm/` | 4/5/4 | body-play foley |
| `maw_seal/` | 4 | maw seal breaks |
| `slap_warm/` | 1 | warm bare-hand slap |
| `escalating_close/` | 4 | escalating close-mic |
| `sudden_forceful/` | 5 | sudden forceful wet |

`squish/stomach/` holds the deep sudden stomach mp3s (also the submissive
toot pool); `squish/closemic/` is empty — the close-mic gross take lives in
`toot/power/` (the old build-lane rejection was a different take).

## Notes
- Toot cooldowns are 18–30s; SFX files are small (25–73KB mp3s), so the
  per-event copy into the session clips dir is cheap.
- Browser plays SFX through the same queue as her voice lines; worst-case
  latency is the 1.5s clip poll.
- `ONRYO_PRESSURE_SFX=0` silences the local pygame path; the director path
  is unaffected (browser has its own sound toggle).
