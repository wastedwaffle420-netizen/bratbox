# BRATBOX

The universal smallest unit of fun horny software.

A rhythm game in your terminal. ASCII visuals, real-time input, and a voice that talks to you while you play — synthesized live through ElevenLabs, or played back from your own session cache.

## Play it

**No install needed.** Download `bratbox.exe` from [Releases](../../releases), double-click, pick how she should sound:

- **Voiceless** — just the game. Still fun, zero setup.
- **ElevenLabs key** — live voices, best quality. Paste your API key once, it's saved locally.
- **Cache** — offline voices from your previous sessions. Earn it by playing.

Or build it yourself: `build_exe.bat` on Windows (needs Python 3.10+).

## What's in the box

- `launcher.py` — tkinter launcher: voice mode picker, API key entry, config
- `ogre_director_v2/` — the game engine (curses rhythm game, lightmap shaders)
- `runner/` — director + voice writer processes
- `bratbox.spec` — PyInstaller build spec

## What's NOT in the box

No bundled voices. The repo is ~30MB of code and sound effects. Voices are either synthesized live via your ElevenLabs key or played from your own local cache (`%APPDATA%/bratbox/voice_cache/`).

Want to hear what the full experience sounds like? Grab the **demo voice pack** from [Releases](../../releases) — 2,000 pre-synthesized lines, proof of perfection.

## The cache mechanic

Every line you hear gets saved locally. Play enough with an API key and you build a personal voice library — then you can go offline and she still talks. The cache is keyed to your voice IDs + text + settings, so it's yours. You earn her voice by playing.

## License

MIT — see [LICENSE](LICENSE).
