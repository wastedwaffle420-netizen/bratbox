#!/usr/bin/env python3
"""Pre-render the offline voice decks: every exchange line for Jasmine
(glossy pendant) and Fiend (mild yarn) into voice_cache/, keyed exactly
the way elevenlabs_writer.py looks them up at runtime.

Run once here (where the tts CLI exists); the caches ship in the zip so
the scene is fully voiced on machines without the tts binary.
"""
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RUNNER = Path(__file__).resolve().parent
sys.path.insert(0, str(RUNNER))

from exchanges import EXCHANGES
from elevenlabs_writer import (
    JASMINE_TTSCLI_VOICE, FIEND_TTSCLI_VOICE,
    JASMINE_VOICE_CACHE, FIEND_VOICE_CACHE,
    jasmine_tts_text, fiend_tts_text, _ttscli_cache_key,
)


def jobs():
    seen = set()
    for _cat, pairs in EXCHANGES.items():
        for xp in pairs:
            for voice, cache, cleanfn, raw in (
                (JASMINE_TTSCLI_VOICE, JASMINE_VOICE_CACHE,
                 jasmine_tts_text, xp["her"]),
                (FIEND_TTSCLI_VOICE, FIEND_VOICE_CACHE,
                 fiend_tts_text, xp["him"]),
            ):
                tts_text = cleanfn(raw)
                if not tts_text:
                    continue
                key = _ttscli_cache_key(voice, tts_text)
                dest = cache / f"ttscli_{key}.mp3"
                tag = (voice, key)
                if tag in seen:
                    continue
                seen.add(tag)
                if dest.is_file() and dest.stat().st_size > 1000:
                    continue
                yield voice, tts_text, dest


def render_one(job):
    voice, tts_text, dest = job
    dest.parent.mkdir(parents=True, exist_ok=True)
    p = subprocess.run(
        ["tts", "speak", "--voice", voice,
         "--text", tts_text, "--output", str(dest)],
        capture_output=True, timeout=120)
    ok = (p.returncode == 0 and dest.is_file()
          and dest.stat().st_size > 1000)
    return dest.name, ok


def main():
    work = list(jobs())
    print(f"{len(work)} clips to render")
    if not work:
        return
    done = failed = 0
    with ThreadPoolExecutor(max_workers=4) as ex:
        for name, ok in ex.map(render_one, work):
            if ok:
                done += 1
            else:
                failed += 1
                print("FAILED:", name, flush=True)
            if (done + failed) % 25 == 0:
                print(f"  {done + failed}/{len(work)}", flush=True)
    print(f"done: {done} rendered, {failed} failed")


if __name__ == "__main__":
    main()
