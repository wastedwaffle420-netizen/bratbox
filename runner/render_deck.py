#!/usr/bin/env python3
"""Render every line in line_deck.py with marisol into assets deck dir."""
import subprocess, sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

RUNNER = Path(__file__).resolve().parent
sys.path.insert(0, str(RUNNER))
from line_deck import DECK

DECK_DIR = RUNNER.parent / "ogre_director_v2" / "assets" / "audio" / "jasmine" / "deck"
DECK_DIR.mkdir(parents=True, exist_ok=True)

jobs = [(lid, text) for cat in DECK.values() for lid, text in cat]

def render(job):
    lid, text = job
    out = DECK_DIR / f"{lid}.mp3"
    if out.exists() and out.stat().st_size > 1000:
        return f"skip {lid}"
    try:
        subprocess.run(["/opt/hatch/bin/tts", "speak", "--voice", "avocado_v2:marisol",
                        "--text", text, "--output", str(out)],
                       timeout=120, check=True, capture_output=True)
        return f"ok {lid}"
    except Exception as e:
        return f"FAIL {lid}: {e}"

with ThreadPoolExecutor(max_workers=4) as ex:
    for r in ex.map(render, jobs):
        print(r, flush=True)
print("deck render done", flush=True)
