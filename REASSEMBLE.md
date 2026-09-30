# Reassembly checklist

`git clone` gives you code, not audio. The audio lives in the
**reassembly-kit** release on GitHub. Download it, then:

1. **Deck** — unzip `bratbox-deck.zip` at the repo root
   → `ogre_director_v2/assets/audio/jasmine/deck/`
   (her per-line voice deck, Glossy Pendant)

2. **Bed sources** — unzip `bratbox-bed-sources.zip` at the repo root
   → `ogre_director_v2/assets/audio/jasmine/newsounds/canon_bed/`
   (the 14 canon bed WAVs; the director renders a fresh seeded
   procedural bed from these every session — no ffmpeg needed)

3. **Fallback bed** — copy `intimacy_bed.mp3` into
   `ogre_director_v2/assets/audio/jasmine/intimacy/`
   (create the folder yourself; git can't keep it — the mp3 is
   gitignored. Used only if the procedural render can't find sources)

4. **Crowned voice cache** — unzip `bratbox-voice-cache.zip` at the repo root
   → `runner/voice_cache/` (`jasmine/` + `fiend/` inside)
   (pre-rendered crowned voices — her Glossy Pendant, him Sparkling
   Bracelet. This is what makes piper mode genuinely offline:
   no `tts` binary needed)

5. **Run it** — `runner/run_simple.bat` for dev, or `build_exe.bat`
   for the frozen exe (installs numpy, bundles everything).

6. **Piper mode check** — pick "Piper TTS" in the launcher. If a line
   ever stays silent, look at `runner/runs/<latest>/writer_stdout.log`
   — nothing goes to DEVNULL anymore.
