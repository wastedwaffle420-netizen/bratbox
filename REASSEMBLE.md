# Bratbox — clone and run

Everything ships in the tree. No downloads, no unzipping, no setup steps.

- `runner/run_simple.bat` — dev run (double-click it)
- `build_exe.bat` — frozen exe build

Audio is all in place:

- `ogre_director_v2/assets/audio/jasmine/deck/` — her per-line voice deck (Glossy Pendant)
- `ogre_director_v2/assets/audio/jasmine/newsounds/canon_bed/` — the 14 canon bed WAVs; the director renders a fresh seeded procedural bed from these every session (no ffmpeg needed)
- `ogre_director_v2/assets/audio/jasmine/intimacy/` — `intimacy_bed.mp3` fallback bed + `bj_arc.mp3`
- `runner/voice_cache/` — pre-rendered crowned voices: her Glossy Pendant, him Sparkling Bracelet. This is what makes piper mode genuinely offline.

Pick "Piper TTS" in the launcher. If a line ever stays silent, check `runner/runs/<latest>/writer_stdout.log` — nothing goes to DEVNULL anymore.
