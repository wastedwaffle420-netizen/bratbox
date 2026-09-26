"""LOCKKEY mood profiles (closed-box tuning).

These profiles are meant to be *defaults*, not user-facing knobs.
They encode pacing + overlap + bark density + voice acting flavor so the
experience ships as a finished instrument.

Modes are selectable in-game (press 'm' to cycle).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, Optional
from pathlib import Path
import json



@dataclass(frozen=True)
class MoodProfile:
    # UI
    label: str

    # Subtitle-sync rendering
    subtitle_sync: bool = True
    subtitle_stack: int = 3

    # Duet pacing (audio-linked hold)
    listen_frac: float = 0.80         # how much of audio plays before advancing
    preempt_max_s: float = 0.18       # max overlap allowed (advance before audio end)
    min_wait_s: float = 0.12
    max_wait_s: float = 1.50

    # Crosstalk (barks)
    max_barks_per_bar: int = 1
    bark_cooldown_s: float = 0.42
    allow_barks: bool = True

    # Voice acting (ElevenLabs voice_settings overrides)
    fiend_voice: Optional[dict] = None
    bird_voice: Optional[dict] = None

    # Fiend micro-cycle (TM/PC/BF/SD) inside this mood
    fiend_microcycle: bool = False

    # Nonverbal mannerisms (very short barks). Keep conservative.
    nonverbal_pool: Optional[tuple[str, ...]] = None
    nonverbal_every_n_lines: int = 0


# NOTE: These are intentionally *not* exposed as environment variables.
# They are the shipped defaults.
MOODS: Dict[str, MoodProfile] = {
    # Default: the “cute performance duet”
    "DUET_TEASE_LOOP": MoodProfile(
        label="Duet — tease loop",
        listen_frac=0.82,
        preempt_max_s=0.16,
        min_wait_s=0.12,
        max_wait_s=1.35,
        max_barks_per_bar=1,
        bark_cooldown_s=0.46,
        allow_barks=True,
        fiend_microcycle=True,
        # Baseline Fiend is expressive but not chaotic; microcycle supplies the color.
        fiend_voice={"stability": 0.44, "similarity_boost": 0.86, "style": 0.50, "use_speaker_boost": True},
        bird_voice={"stability": 0.55, "similarity_boost": 0.88, "style": 0.30, "use_speaker_boost": True},
        # Mostly voice: small laughs/hums/clicks that sell "people-pleaser listening".
        nonverbal_pool=("heh.", "hah.", "mm.", "mhm.", "hmm?", "tch."),
        nonverbal_every_n_lines=4,
    ),

    # Same duet, but “finger tracing the arm” escalation: sass + head tilts + hotter timing.
    "DUET_PLUS": MoodProfile(
        label="Duet+ — tilt & sass",
        listen_frac=0.74,
        preempt_max_s=0.26,
        min_wait_s=0.10,
        max_wait_s=1.15,
        max_barks_per_bar=1,
        bark_cooldown_s=0.38,
        allow_barks=True,
        fiend_microcycle=False,
        fiend_voice={"stability": 0.32, "similarity_boost": 0.84, "style": 0.72, "use_speaker_boost": True},
        bird_voice={"stability": 0.46, "similarity_boost": 0.88, "style": 0.42, "use_speaker_boost": True},
        nonverbal_pool=("heh.", "hah!", "mm?", "mhm!", "tch—", "hmm."),
        nonverbal_every_n_lines=3,
    ),

    # More florid, airy, “cinematic” delivery. Less overlap; longer holds.
    "CINEMATIC": MoodProfile(
        label="Cinematic — flourish",
        listen_frac=0.92,
        preempt_max_s=0.08,
        min_wait_s=0.14,
        max_wait_s=1.80,
        max_barks_per_bar=0,
        bark_cooldown_s=0.60,
        allow_barks=False,
        fiend_voice={"stability": 0.58, "similarity_boost": 0.90, "style": 0.42, "use_speaker_boost": True},
        bird_voice={"stability": 0.64, "similarity_boost": 0.92, "style": 0.34, "use_speaker_boost": True},
        # subtle mannerisms, extremely sparse
        nonverbal_pool=("tch", "mm", "heh"),
        nonverbal_every_n_lines=7,
    ),

    # Overwhelm melt: slower, softer, fewer barks.
    "TIRED_POUT": MoodProfile(
        label="Tired pout — melt",
        listen_frac=0.90,
        preempt_max_s=0.10,
        min_wait_s=0.16,
        max_wait_s=2.00,
        max_barks_per_bar=0,
        bark_cooldown_s=0.70,
        allow_barks=False,
        fiend_voice={"stability": 0.70, "similarity_boost": 0.92, "style": 0.18, "use_speaker_boost": True},
        bird_voice={"stability": 0.72, "similarity_boost": 0.92, "style": 0.18, "use_speaker_boost": True},
        nonverbal_pool=("mm...", "mhm...", "hahhh...", "...mm."),
        nonverbal_every_n_lines=6,
    ),

    # Aloof but smiling — happy tongue-on-teeth crackle vibe. Keep it rare.
    "ALOOF_SMILE": MoodProfile(
        label="Aloof smile — crackle",
        listen_frac=0.84,
        preempt_max_s=0.14,
        min_wait_s=0.12,
        max_wait_s=1.45,
        max_barks_per_bar=1,
        bark_cooldown_s=0.55,
        allow_barks=True,
        fiend_voice={"stability": 0.56, "similarity_boost": 0.90, "style": 0.30, "use_speaker_boost": True},
        bird_voice={"stability": 0.60, "similarity_boost": 0.90, "style": 0.24, "use_speaker_boost": True},
        nonverbal_pool=("tch", "tsk", "heh"),
        nonverbal_every_n_lines=5,
    ),

    # Sub frenzy: quick, eager, but still protected semantics.
    "SUB_FRENZY": MoodProfile(
        label="Sub frenzy",
        listen_frac=0.64,
        preempt_max_s=0.30,
        min_wait_s=0.08,
        max_wait_s=1.05,
        max_barks_per_bar=2,
        bark_cooldown_s=0.30,
        allow_barks=True,
        fiend_voice={"stability": 0.28, "similarity_boost": 0.86, "style": 0.82, "use_speaker_boost": True},
        bird_voice={"stability": 0.40, "similarity_boost": 0.88, "style": 0.52, "use_speaker_boost": True},
        nonverbal_pool=("mm!", "hah!", "huh?", "mhm!"),
        nonverbal_every_n_lines=5,
    ),

    # Dom frenzy (softened): commanding, playful, “hot feminist” warmth.
    "DOM_FRENZY": MoodProfile(
        label="Dom frenzy — warm",
        listen_frac=0.70,
        preempt_max_s=0.22,
        min_wait_s=0.10,
        max_wait_s=1.10,
        max_barks_per_bar=2,
        bark_cooldown_s=0.32,
        allow_barks=True,
        fiend_voice={"stability": 0.46, "similarity_boost": 0.90, "style": 0.58, "use_speaker_boost": True},
        bird_voice={"stability": 0.44, "similarity_boost": 0.90, "style": 0.44, "use_speaker_boost": True},
        nonverbal_pool=("mm.", "heh.", "tch.", "mhm."),
        nonverbal_every_n_lines=4,
    ),
}

# Optional user overrides (non-destructive):
# Create 'mood_overrides.json' in this folder to tweak shipped mood profiles without editing code.
# Format:
# {
#   "DEFAULT": {"subtitle_stack": 4},
#   "DUET_TEASE_LOOP": {"max_barks_per_bar": 2, "bark_cooldown_s": 0.35}
# }
def _apply_mood_overrides() -> None:
    p = Path(__file__).with_name("mood_overrides.json")
    if not p.exists():
        return
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return
    if not isinstance(data, dict):
        return

    default_over = data.get("DEFAULT") if isinstance(data.get("DEFAULT"), dict) else {}

    for k, v in list(MOODS.items()):
        over = {}
        if isinstance(default_over, dict):
            over.update(default_over)
        vk = data.get(k)
        if isinstance(vk, dict):
            over.update(vk)
        if not over:
            continue
        # Only allow fields that actually exist on MoodProfile
        allowed = {f.name for f in MoodProfile.__dataclass_fields__.values()}  # type: ignore
        filtered = {kk: vv for kk, vv in over.items() if kk in allowed}
        if not filtered:
            continue
        try:
            MOODS[k] = replace(v, **filtered)
        except Exception:
            continue

# Apply once at import time.
_apply_mood_overrides()


MOOD_ORDER = [
    "DUET_TEASE_LOOP",
    "DUET_PLUS",
    "CINEMATIC",
    "TIRED_POUT",
    "ALOOF_SMILE",
    "SUB_FRENZY",
    "DOM_FRENZY",
]


def get_mood(name: str) -> MoodProfile:
    return MOODS.get(str(name or "").strip().upper(), MOODS["DUET_TEASE_LOOP"])

