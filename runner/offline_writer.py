#!/usr/bin/env python3
"""TTS operator: voices the game's own birdsong dialogue. Nothing else.

The game authors every line (birdsong corpus, verbatim, NLS-injected).
This writer only gives those lines a voice:

  beat["candidate"] = {"speaker": "BIRDSONG"|"FIEND", "text": "..."}
    -> look up the pre-rendered clip
       (glossy pendant for her, mild yarn for him)
    -> play it on this machine, fire-and-forget (never blocks a beat)
    -> reply {"seq", "line": <verbatim>, "dur_s": <clip seconds>}

No line authoring, no network, no ElevenLabs, no tts binary needed —
every clip is pre-rendered into voice_cache/ and ships with the build.
Also plays toot/SFX clips the director drops into clips/sfx_*.mp3.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from elevenlabs_writer import (  # noqa: E402
    _ttscli_cache_key,
    jasmine_tts_text,
    fiend_tts_text,
    mp3_dur_s,
    JASMINE_TTSCLI_VOICE,
    FIEND_TTSCLI_VOICE,
    JASMINE_VOICE_CACHE,
    FIEND_VOICE_CACHE,
)

MAX_RUNTIME_S = 6 * 60 * 60


def _detect_player():
    override = os.environ.get("JASMINE_AUDIO_PLAYER", "").strip()
    if override:
        return override.split()
    if shutil.which("afplay"):
        return ["afplay"]
    for p in ("paplay", "aplay", "ffplay", "mpg123", "mpv"):
        if shutil.which(p):
            if p == "ffplay":
                return ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"]
            if p == "mpv":
                return ["mpv", "--no-video", "--really-quiet"]
            return [p]
    if os.name == "nt":
        # last resort: PowerShell via the default media pipeline
        return ["powershell", "-NoProfile", "-Command"]
    return []


class Operator:
    def __init__(self, session: Path):
        self.session = session
        self.inbox = session / "inbox"
        self.outbox = session / "outbox"
        self.clips = session / "clips"
        for d in (self.inbox, self.outbox, self.clips):
            d.mkdir(parents=True, exist_ok=True)
        self.start = time.time()
        self.player = _detect_player()
        self._played_sfx = set()
        # Voice pacing (2026-09-25): sequential, no overlap.
        # _next_voice_t = earliest time the next voice clip may start.
        self._next_voice_t = 0.0
        if self.player:
            print(f"tts operator: audio via {' '.join(self.player)}",
                  flush=True)
        else:
            print("tts operator: WARNING no audio player found "
                  "(set JASMINE_AUDIO_PLAYER)", flush=True)
        self.n_voiced = 0
        self.n_missing = 0

    def _clip_for(self, speaker: str, text: str):
        sp = (speaker or "").upper()
        if sp == "FIEND":
            voice, cache, clean = (FIEND_TTSCLI_VOICE, FIEND_VOICE_CACHE,
                                   fiend_tts_text)
        else:
            voice, cache, clean = (JASMINE_TTSCLI_VOICE, JASMINE_VOICE_CACHE,
                                   jasmine_tts_text)
        tts_text = clean(text)
        if not tts_text:
            return None
        key = _ttscli_cache_key(voice, tts_text)
        p = cache / f"ttscli_{key}.mp3"
        if p.is_file() and p.stat().st_size > 1000:
            return p
        return None

    def _play(self, clip: Path):
        if not self.player or not clip:
            return
        try:
            # SEQUENTIAL VOICE (2026-09-25): wait for the previous clip to
            # finish + gap before starting the next. No overlap, ever.
            try:
                gap = max(0.0, float(os.environ.get("JASMINE_VOICE_GAP_S", "0.6") or 0.6))
            except Exception:
                gap = 0.6
            now = time.monotonic()
            if now < self._next_voice_t:
                time.sleep(self._next_voice_t - now)
                now = self._next_voice_t
            # Get clip duration for pacing
            try:
                dur = max(0.3, float(mp3_dur_s(clip) or 0.0))
            except Exception:
                dur = 2.0
            if self.player[0] == "powershell":
                # Windows fallback: play via .NET (wav only) — convert
                # via nothing; just shell out to the default handler
                # quietly is not possible, so skip rather than pop UI.
                return
            subprocess.Popen(
                self.player + [str(clip)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL, start_new_session=True)
            # Next clip may start after this one finishes + gap
            self._next_voice_t = now + dur + gap
        except Exception as e:
            print(f"audio play failed: {e}", flush=True)

    def _pump_sfx(self):
        # toot/SFX clips the director drops in clips/sfx_*.mp3
        try:
            files = sorted(self.clips.glob("sfx_*.mp3"))
        except Exception:
            return
        for f in files:
            if f.name in self._played_sfx:
                continue
            self._played_sfx.add(f.name)
            # only fresh drops (avoid replaying an old session's tail)
            try:
                if time.time() - f.stat().st_mtime > 120:
                    continue
            except Exception:
                continue
            self._play(f)

    def answer(self, beat: dict):
        seq = int(beat["seq"])
        tag = f"{seq:06d}"
        cand = beat.get("candidate") or {}
        speaker = str(cand.get("speaker") or "")
        text = str(cand.get("text") or "")
        reply = {"seq": seq}
        clip = self._clip_for(speaker, text) if text.strip() else None
        if clip is not None:
            self._play(clip)
            dur = mp3_dur_s(clip) or float(cand.get("ttl") or 2.0)
            self.n_voiced += 1
        else:
            if text.strip():
                self.n_missing += 1
                if self.n_missing <= 10 or self.n_missing % 50 == 0:
                    print(f"no clip for [{speaker}] {text[:60]!r}",
                          flush=True)
            dur = float(cand.get("ttl") or 2.0)
        # verbatim: the game's line goes back untouched — we only voice it.
        if text.strip():
            reply["line"] = text.strip()
        reply["dur_s"] = round(max(0.5, dur), 2)
        (self.outbox / f"reply_{tag}.json").write_text(json.dumps(reply))
        if self.n_voiced and self.n_voiced % 100 == 0:
            print(f"voiced {self.n_voiced} lines "
                  f"({self.n_missing} missing)", flush=True)

    def run(self):
        idle_since = time.time()
        while True:
            if time.time() - self.start > MAX_RUNTIME_S:
                print("tts operator: max runtime, exiting", flush=True)
                return
            self._pump_sfx()
            beats = sorted(self.inbox.glob("beat_*.json"))
            if not beats:
                st = self.session / "director_stats.json"
                if st.exists():
                    try:
                        stale_s = time.time() - st.stat().st_mtime
                    except Exception:
                        stale_s = 0.0
                    if stale_s > 30 and time.time() - idle_since > 15:
                        print("tts operator: session over, exiting",
                              flush=True)
                        return
                else:
                    idle_since = time.time()
                time.sleep(0.3)
                continue
            idle_since = time.time()
            for bf in beats:
                try:
                    beat = json.loads(bf.read_text(encoding="utf-8"))
                except Exception:
                    bf.unlink(missing_ok=True)
                    continue
                if not isinstance(beat, dict) or "seq" not in beat:
                    bf.unlink(missing_ok=True)
                    continue
                try:
                    # dialogue beats carry a candidate; anything else
                    # (actions etc.) gets a bare ack so the game continues.
                    if beat.get("candidate"):
                        self.answer(beat)
                    else:
                        tag = f"{int(beat['seq']):06d}"
                        (self.outbox / f"reply_{tag}.json").write_text(
                            json.dumps({"seq": int(beat["seq"])}))
                except Exception as e:
                    print(f"answer failed: {e}", flush=True)
                finally:
                    bf.unlink(missing_ok=True)


def main():
    if len(sys.argv) < 2:
        print("usage: offline_writer.py <session-dir>")
        sys.exit(1)
    Operator(Path(sys.argv[1])).run()


if __name__ == "__main__":
    main()
