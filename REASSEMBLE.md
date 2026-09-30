# Reassembly checklist

Everything ships in the repo. `assets/` holds the audio as zips
(git can't track the live folders — see .gitignore). Unzip at the
repo root, then run.

1. **Deck** — unzip all `assets/bratbox-deck-*.zip` at the repo root
   → `ogre_director_v2/assets/audio/jasmine/deck/`
   (her per-line voice deck, Glossy Pendant; split in 4 so every
   file stays small — they merge into the same folder)

2. **Bed sources** — unzip `assets/bratbox-bed-sources.zip` at the repo root
   → `ogre_director_v2/assets/audio/jasmine/newsounds/canon_bed/`
   (the 14 canon bed WAVs; the director renders a fresh seeded
   procedural bed from these every session — no ffmpeg needed)

3. **Fallback bed** — copy `assets/intimacy_bed.mp3` into
   `ogre_director_v2/assets/audio/jasmine/intimacy/`
   (create the folder; used only if the procedural render can't
   find the sources)

4. **Crowned voice cache** — unzip `assets/bratbox-voice-cache.zip`
   at the repo root → `runner/voice_cache/` (`jasmine/` + `fiend/`)
   (pre-rendered crowned voices — her Glossy Pendant, him Sparkling
   Bracelet. This is what makes piper mode genuinely offline:
   no `tts` binary needed)

5. **Run it** — `runner/run_simple.bat` for dev, or `build_exe.bat`
   for the frozen exe (installs numpy, bundles everything).

6. **Piper mode check** — pick "Piper TTS" in the launcher. If a line
   ever stays silent, look at `runner/runs/<latest>/writer_stdout.log`
   — nothing goes to DEVNULL anymore.
