#!/usr/bin/env python3
"""Fiend's line pool — the rework (2026-09-24).

Seven moods, authored in-dialect (Florida swamp valley), brat-first:
tease_back / opener / melt / brat_tamer / coax / aftercare_soft / softsad.
One text file per mood in fiend_lines/; this module loads them and picks
with no-repeat tracking per category.

His response mapping (her category -> his mood) lives in
elevenlabs_writer.FIEND_RESPONSE_MAP. softsad (R6) is special: it never
answers a specific category — it surfaces rarely inside ANY exchange,
the bit cracking for one line.
"""
import random
from pathlib import Path

LINES_DIR = Path(__file__).resolve().parent / "fiend_lines"

CATEGORIES = ("tease_back", "opener", "melt", "brat_tamer", "coax",
              "aftercare_soft", "softsad", "ledger_devotion", "ledger_beast",
              "escalation", "daylife")


def _load() -> dict:
    pool = {}
    for cat in CATEGORIES:
        p = LINES_DIR / f"{cat}.txt"
        try:
            lines = [ln.strip() for ln in p.read_text(encoding="utf-8").split("\n")]
            lines = [ln for ln in lines if ln]
        except Exception:
            lines = []
        # de-dupe within category, keep order
        seen, uniq = set(), []
        for ln in lines:
            if ln not in seen:
                seen.add(ln)
                uniq.append(ln)
        pool[cat] = uniq
    return pool


FIEND_POOL = _load()


def pool_size() -> int:
    return sum(len(v) for v in FIEND_POOL.values())


def pick(category: str, used: set) -> str | None:
    """Pick an unused line from category; resets when exhausted."""
    lines = FIEND_POOL.get(category) or []
    if not lines:
        return None
    avail = [ln for ln in lines if ln not in used]
    if not avail:
        used.clear()
        avail = lines
    line = random.choice(avail)
    used.add(line)
    return line
