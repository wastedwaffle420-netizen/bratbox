# BRATBOX

The universal smallest unit of fun horny software.

A rhythm game in your terminal. ASCII visuals, real-time input, and a voice that talks to you while you play — fully offline from your own voice cache. No account, no API key, no network needed.

## Play it

**No install needed.** Download `bratbox.exe` from [Releases](../../releases), double-click, pick how she should sound:

- **Voiceless** — just the game. Still fun, zero setup.
- **Cache** — offline voices from your voice pack. Fully local, no network.
- **ElevenLabs key** (opt-in) — live voices via your own API key. Only if you want it; the game never needs it.

Or build it yourself: `build_exe.bat` on Windows (needs Python 3.10+).

## What's in the box

- `launcher.py` — tkinter launcher: voice mode picker, API key entry, config
- `ogre_director_v2/` — the game engine (curses rhythm game, lightmap shaders)
- `runner/` — director + voice writer processes
- `bratbox.spec` — PyInstaller build spec

## What's NOT in the box

No bundled voices. The repo is ~30MB of code and sound effects. Voices play from your own local cache (`%APPDATA%/bratbox/voice_cache/`) — fully offline.

Want to hear what the full experience sounds like? Grab the **demo voice pack** from [Releases](../../releases) — 2,000 pre-synthesized lines, proof of perfection.

The photo terminal (AI-generated visuals) is a separate optional add-on — not in this repo, not needed to play.

## The cache mechanic

Every line you hear gets saved locally. Play with the voice pack and she talks fully offline — the cache is keyed to voice IDs + text + settings, so it's yours.

## License

MIT — see [LICENSE](LICENSE).
