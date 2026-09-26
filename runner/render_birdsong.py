#!/usr/bin/env python3
"""Pre-render the FULL birdsong corpus (vendor_full, verbatim) to the offline
voice deck: BIRDSONG lines in glossy pendant, FIEND lines in mild yarn.

Same cache-key scheme as the exchange deck, so the TTS operator (offline
writer) looks clips up by line text with zero special-casing.

Run once here (where the tts CLI exists); the deck ships in the zip(s).
"""
import ast
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from elevenlabs_writer import (  # noqa: E402
    _ttscli_cache_key,
    jasmine_tts_text,
    fiend_tts_text,
    JASMINE_TTSCLI_VOICE,
    FIEND_TTSCLI_VOICE,
    JASMINE_VOICE_CACHE,
    FIEND_VOICE_CACHE,
)

VENDOR = (HERE / "../../ogre_full/ogre_full/wotw_bratbox/vendor_full"
          "/ogre_shader_v5.py").resolve()


def extract_corpus():
    src = VENDOR.read_text(encoding="utf-8")
    tree = ast.parse(src)
    seen = set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            try:
                v = ast.literal_eval(node.value)
            except Exception:
                continue

            def walk(x):
                if (isinstance(x, tuple) and len(x) == 2
                        and isinstance(x[0], str) and isinstance(x[1], str)):
                    if x[0] in ("BIRDSONG", "FIEND"):
                        seen.add((x[0], x[1].strip()))
                elif isinstance(x, (list, tuple)):
                    for i in x:
                        walk(i)
                elif isinstance(x, dict):
                    for k, i in x.items():
                        walk(i)
            walk(v)
    return sorted(seen)


def jobs():
    seen_tags = set()
    for speaker, raw in extract_corpus():
        if speaker == "BIRDSONG":
            voice, cache, clean = (JASMINE_TTSCLI_VOICE, JASMINE_VOICE_CACHE,
                                   jasmine_tts_text)
        else:
            voice, cache, clean = (FIEND_TTSCLI_VOICE, FIEND_VOICE_CACHE,
                                   fiend_tts_text)
        tts_text = clean(raw)
        if not tts_text:
            continue
        key = _ttscli_cache_key(voice, tts_text)
        dest = cache / f"ttscli_{key}.mp3"
        tag = (voice, key)
        if tag in seen_tags:
            continue
        seen_tags.add(tag)
        if dest.is_file() and dest.stat().st_size > 1000:
            continue
        yield voice, tts_text, dest


def render_one(job):
    voice, tts_text, dest = job
    dest.parent.mkdir(parents=True, exist_ok=True)
    p = subprocess.run(
        ["tts", "speak", "--voice", voice,
         "--text", tts_text, "--output", str(dest)],
        capture_output=True, timeout=180)
    ok = (p.returncode == 0 and dest.is_file()
          and dest.stat().st_size > 1000)
    if not ok:
        err = (p.stderr or b"").decode(errors="replace")[-200:]
        print(f"FAILED {dest.name}: {err}", flush=True)
    return ok


def main():
    work = list(jobs())
    print(f"{len(work)} birdsong clips to render", flush=True)
    if not work:
        return
    done = failed = 0
    with ThreadPoolExecutor(max_workers=4) as ex:
        for ok in ex.map(render_one, work):
            if ok:
                done += 1
            else:
                failed += 1
            if (done + failed) % 25 == 0:
                print(f"  {done + failed}/{len(work)}", flush=True)
    print(f"done: {done} rendered, {failed} failed", flush=True)


if __name__ == "__main__":
    main()
