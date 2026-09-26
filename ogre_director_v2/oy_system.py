"""Shared OY/SURGE loadout and read-scoring helpers."""

from __future__ import annotations

import random
from typing import Dict, Iterable, List, Tuple


DEFAULT_OY_LOADOUT = ["soften", "counter", "anchor"]  # bottom, middle, top

OY_CALLS: Dict[str, Dict[str, object]] = {
    "soften": {
        "mouth": "OYYYYYY",
        "name": "Warm Wag",
        "tool": "ground",
        "hint": "melts the line if she is hiding softness",
        "affinity": {"quiet": 1.0, "melting": 0.88, "needy": 0.65, "rambling": 0.45, "bratty": 0.25},
    },
    "counter": {
        "mouth": "OY OY OY",
        "name": "Tease Back",
        "tool": "tease",
        "hint": "answers the bait and steals the tempo back",
        "affinity": {"bratty": 1.0, "rambling": 0.78, "needy": 0.55, "melting": 0.35, "quiet": 0.25},
    },
    "anchor": {
        "mouth": "OY.",
        "name": "Hard Oy",
        "tool": "command",
        "hint": "catches Bird when she runs off with the sentence",
        "affinity": {"rambling": 0.92, "bratty": 0.72, "needy": 0.55, "melting": 0.40, "quiet": 0.30},
    },
    "focus": {
        "mouth": "OY!",
        "name": "Face Grab",
        "tool": "command",
        "hint": "pulls her eyes back to Fiend",
        "affinity": {"rambling": 0.86, "needy": 0.68, "bratty": 0.58, "quiet": 0.45, "melting": 0.35},
    },
    "yield": {
        "mouth": "OY...",
        "name": "Praise Bait",
        "tool": "observe",
        "hint": "lets her lead because Fiend wants to hear what she does with it",
        "affinity": {"quiet": 0.92, "melting": 0.88, "needy": 0.68, "rambling": 0.42, "bratty": 0.35},
    },
    "glint": {
        "mouth": "OYHUHYYYY",
        "name": "Danger Laugh",
        "tool": "escalate",
        "hint": "laughs inside the word when she makes this fun",
        "affinity": {"bratty": 0.96, "rambling": 0.76, "needy": 0.58, "melting": 0.32, "quiet": 0.25},
    },
}

OY_ORDER = list(OY_CALLS.keys())


def normalize_oy_loadout(raw: Iterable[str] | None) -> List[str]:
    result: List[str] = []
    for item in list(raw or []):
        key = str(item or "").strip().lower()
        if key in OY_CALLS and key not in result:
            result.append(key)
        if len(result) >= 3:
            break
    for key in DEFAULT_OY_LOADOUT:
        if key not in result:
            result.append(key)
        if len(result) >= 3:
            break
    return result[:3]


def oy_call_for_tier(loadout: Iterable[str], tier: int) -> Dict[str, object]:
    ids = normalize_oy_loadout(loadout)
    idx = max(0, min(2, int(tier or 1) - 1))
    call_id = ids[idx]
    data = dict(OY_CALLS[call_id])
    data["id"] = call_id
    return data


def score_oy_read(
    call_id: str,
    birdsong_state: str,
    *,
    power_dynamic: float = 0.0,
    sync_level: float = 0.0,
    recent_interrupt_count: int = 0,
) -> Tuple[str, float, bool]:
    call = OY_CALLS.get(str(call_id or "").strip().lower(), OY_CALLS["soften"])
    state = str(birdsong_state or "rambling").strip().lower()
    score = float(dict(call.get("affinity", {})).get(state, 0.50))
    if call_id in ("anchor", "focus", "glint") and power_dynamic < -0.25:
        score += 0.12
    if call_id in ("soften", "yield") and sync_level >= 80.0:
        score += 0.08
    if recent_interrupt_count >= 2:
        score -= 0.18
    score = max(0.0, min(1.0, score))
    if score >= 0.88:
        match = "perfect"
    elif score >= 0.68:
        match = "good"
    elif score >= 0.42:
        match = "awkward"
    else:
        match = "bad"
    glint = bool(match in ("perfect", "good") and (call_id == "glint" or score >= 0.90))
    return match, score, glint


OY_REACTIONS = {
    "soften": {
        "good": ["Shut up. That worked.", "...don't wag the sentence at me.", "I was not hiding softness. Mostly."],
        "awkward": ["You can't warm-wag every sentence.", "Mm. Cute, but I was still talking."],
        "bad": ["Nope. Too soft. My turn.", "That one slides right off me."],
    },
    "counter": {
        "good": ["I did not flinch.", "Tch. Tempo thief.", "Okay, that one landed."],
        "awkward": ["Cute answer. Still my sentence.", "You're late, but adorable."],
        "bad": ["Too easy. I keep the line.", "You answered the wrong part, Fiend."],
    },
    "anchor": {
        "good": ["...don't say it like that.", "Ghhh. Fine. Back on beat.", "Okay. I heard you."],
        "awkward": ["Hard voice, soft timing.", "You caught the edge, not the line."],
        "bad": ["No. You don't get the stop there.", "I run right through that."],
    },
    "focus": {
        "good": ["...I am looking.", "Eyes up. Fine.", "You caught me."],
        "awkward": ["I was already looking, dramatic boy.", "Cute. Slightly early."],
        "bad": ["Don't grab the sentence when I'm carrying it.", "Missed me."],
    },
    "yield": {
        "good": ["...oh. You want me to keep going.", "That was unfairly sweet.", "Okay. Listen then."],
        "awkward": ["Praise bait? Now?", "Mm. I can use that."],
        "bad": ["You gave me the whole sentence. Mine.", "Careful. I take that."],
    },
    "glint": {
        "good": ["...oh no. You made it fun.", "That laugh is dangerous.", "Careful. I liked that."],
        "awkward": ["Big laugh. Little timing problem.", "Almost scary. Mostly cute."],
        "bad": ["You laughed before the joke landed.", "Nope. I steal that grin."],
    },
}


def choose_oy_reaction(call_id: str, match: str) -> str:
    pools = OY_REACTIONS.get(call_id, OY_REACTIONS["soften"])
    if match == "perfect":
        match = "good"
    pool = pools.get(match) or pools.get("awkward") or ["..."]
    return random.choice(pool)

