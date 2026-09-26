#!/usr/bin/env python3
"""
OGRE SHADER: INTIMACY ENGINE
Continuous rhythm with reactive dialogue - the scene that was skipped

THE CONCEPT:
  • Notes fall continuously (not bursts)
  • Each hit triggers immediate dialogue response
  • Lane = action type (A=touch, S=hold, B=rhythm, SPACE=eye contact)
  • Pose changes with intensity
  • Tempo builds toward climax
  • Both voices active throughout

DIALOGUE SYSTEM:
  • Pool-based: each lane has reaction pools
  • Intensity tiers: building → peak → release
  • NLS anchors: hahhh—, mmhh, ghhh—, fieeeenddd~
  • Fiend: short, directive
  • Birdsong: reactive, building
  • Inner: body awareness
"""

import curses
import time
import math
import random
import cascade_engine
try:
    from wotw_glyphs import glyph_safe_char, glyph_safe_text
except Exception:
    def glyph_safe_text(text):
        return str(text)

    def glyph_safe_char(ch):
        value = str(ch)
        return value[0] if value else " "


def _cascade_pick(pool, speaker: str, intensity: float = 0.0, lane: str = "", quality: str = "") -> str:
    """Small helper for dialogue pools. Uses cascade scoring when available."""
    try:
        ctx = cascade_engine.CascadeContext(intensity=float(intensity), lane=str(lane), quality=str(quality))
        return cascade_engine.choose_from_pool(list(pool), speaker, ctx=ctx, sample=10)
    except Exception:
        import random as _r
        return _r.choice(list(pool))

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum

# ═══════════════════════════════════════════════════════════════════════════════
#                              LANE DIALOGUE POOLS
# ═══════════════════════════════════════════════════════════════════════════════

# Intensity tiers: 0-33 = BUILDING, 34-66 = PEAK, 67-100 = RELEASE

LANE_A_DIALOGUE = {  # Touch/caress
    "fiend": {
        "building": ["Here.", "Feel this.", "Soft.", "Like that.", "Mm."],
        "peak": ["More.", "Don't stop.", "Yes.", "There.", "Good."],
        "release": ["Hahhh—", "Yes.", "Perfect.", "Mine.", "Good girl."],
    },
    "bird": {
        "building": [
            "Mmhh— okay—",
            "That's— hahhh— new—",
            "Oy~ careful—",
            "Ghhh— your hands—",
            "Fieeeenddd~",
        ],
        "peak": [
            "Hahhh— more—",
            "Don't stop— mmhh—",
            "Right there— ghhh—",
            "Yessss~",
            "Again— please—",
        ],
        "release": [
            "Hahhh— HAHHH—",
            "I can't— mmhh— I can't—",
            "Fieeeenddd~ please—",
            "Ghhh— too much— not enough—",
            "THERE— yes— THERE—",
        ],
    },
    "inner": {
        "building": ["His hands know exactly where to go.", "Every touch is deliberate."],
        "peak": ["I'm melting. I'm actually melting.", "More. I need more."],
        "release": ["Everything is sensation. Nothing else exists.", "Just this. Just us."],
    },
}

LANE_S_DIALOGUE = {  # Hold/pull
    "fiend": {
        "building": ["Stay.", "Come here.", "Closer.", "Mine.", "Hold."],
        "peak": ["Don't move.", "Right there.", "Perfect.", "Steady.", "Good."],
        "release": ["Hahhh— stay.", "I've got you.", "Let go.", "I'm here.", "Fall."],
    },
    "bird": {
        "building": [
            "Mmhh— okay—",
            "I'm not— hahhh— going anywhere—",
            "Oy~ possessive much—",
            "Ghhh— hold tighter—",
            "Fieeeenddd~ I'm here—",
        ],
        "peak": [
            "Hahhh— don't let go—",
            "Stay— mmhh— stay—",
            "I've got you too— ghhh—",
            "Yessss~ like that—",
            "Hold me— please—",
        ],
        "release": [
            "Hahhh— I'm— I'm—",
            "Don't let me fall— mmhh—",
            "Fieeeenddd~ catch me—",
            "Ghhh— I'm shaking—",
            "Hold— HOLD—",
        ],
    },
    "inner": {
        "building": ["He's not letting go.", "I don't want him to."],
        "peak": ["Anchored. I'm anchored to him.", "This is safety. This is danger."],
        "release": ["Falling. Falling into him.", "He caught me. He always catches me."],
    },
}

LANE_B_DIALOGUE = {  # Rhythm/thrust
    "fiend": {
        "building": ["Move.", "Like this.", "Follow.", "Rhythm.", "There."],
        "peak": ["Faster.", "Harder.", "Don't stop.", "Yes.", "More."],
        "release": ["NOW.", "Let go.", "Come.", "With me.", "Yes."],
    },
    "bird": {
        "building": [
            "Mmhh— oh—",
            "Ghhh— that's—",
            "Oy~ hahhh—",
            "I feel— mmhh—",
            "Fieeeenddd~",
        ],
        "peak": [
            "Hahhh— MORE—",
            "Don't— ghhh— don't stop—",
            "Faster— mmhh— please—",
            "Yessss~ YESSSS~",
            "Right THERE—",
        ],
        "release": [
            "HAHHH— I'm— I'm gonna—",
            "Fieeeenddd~ I can't— I CAN'T—",
            "Ghhh— GHHH— oh god—",
            "YES— YES— YES—",
            "Mmhh— MMHH— MMMHHHH—",
        ],
    },
    "inner": {
        "building": ["The rhythm. I'm finding the rhythm.", "Body moving without permission."],
        "peak": ["Every nerve. Every single nerve.", "Building. Something's building."],
        "release": ["Everything. All at once. HERE.", "I'm— I'm— I'm—"],
    },
}

LANE_SPACE_DIALOGUE = {  # Eye contact/stillness
    "fiend": {
        "building": ["Look at me.", "Eyes here.", "See?", "I see you.", "There."],
        "peak": ["Don't look away.", "Stay with me.", "Right here.", "I've got you.", "Breathe."],
        "release": ["Beautiful.", "I see everything.", "You're perfect.", "Let me see.", "Show me."],
    },
    "bird": {
        "building": [
            "...mmhh...",
            "I see you too— hahhh—",
            "Oy~ don't look at me like—",
            "Ghhh— your eyes—",
            "Fieeeenddd~",
        ],
        "peak": [
            "Hahhh— I can't look away—",
            "You're— mmhh— seeing everything—",
            "Don't— ghhh— don't blink—",
            "Yessss~ right there—",
            "I'm here— I'm here—",
        ],
        "release": [
            "HAHHH— I'm—",
            "Fieeeenddd~ don't look away—",
            "See me— mmhh— SEE me—",
            "Ghhh— everything— you see—",
            "I'm— I'm yours—",
        ],
    },
    "inner": {
        "building": ["He's looking right through me.", "Nowhere to hide."],
        "peak": ["Connected. We're connected through the eyes.", "He sees everything."],
        "release": ["Witnessed. Completely witnessed.", "I'm seen. I'm known. I'm his."],
    },
}

LANE_DIALOGUES = {
    0: LANE_A_DIALOGUE,  # A
    1: LANE_S_DIALOGUE,  # S
    2: LANE_B_DIALOGUE,  # B
    3: LANE_SPACE_DIALOGUE,  # SPACE
}

# Miss dialogue
MISS_DIALOGUE = {
    "fiend": ["Wait.", "Patience.", "Not yet.", "Focus.", "..."],
    "bird": [
        "Hahhh— sorry—",
        "Mmhh— I lost it—",
        "Ghhh— wait—",
        "Oy~ my bad—",
        "Fieeeenddd~ I—",
    ],
    "inner": ["Lost the rhythm.", "Focus. Focus.", "Don't break the moment."],
}

# Pose progression based on intensity
# coy_cheek = crouch/butt (opener OR mid enticing)
# face = eye contact
# downward = the view (HOT)
# squat = main event (HOTTEST)
# laying_smile = post (aftermath only)
# angled_collapse = he pulls her (COMBO REWARD)

INTENSITY_POSES = {
    (0, 20):   "coy_cheek",    # Opener - mouth, enticing
    (20, 45):  "face",         # Connection builds
    (45, 70):  "coy_cheek",    # Returns - now it's enticing
    (70, 90):  "downward",     # The view - approaching peak
    (90, 101): "squat",        # Main event - climax
}

# ═══════════════════════════════════════════════════════════════════════════════
#                              UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def clamp(v, lo, hi): return lo if v < lo else hi if v > hi else v

def get_intensity_tier(intensity: float) -> str:
    if intensity < 34:
        return "building"
    elif intensity < 67:
        return "peak"
    return "release"

def get_pose_for_intensity(intensity: float) -> str:
    for (lo, hi), pose in INTENSITY_POSES.items():
        if lo <= intensity < hi:
            return pose
    return "angled_collapse"

# ═══════════════════════════════════════════════════════════════════════════════
#                              ENUMS
# ═══════════════════════════════════════════════════════════════════════════════

class Lane(Enum):
    A = 0
    S = 1
    B = 2
    SPACE = 3

LANE_KEYS = {
    ord('a'): Lane.A, ord('A'): Lane.A,
    ord('s'): Lane.S, ord('S'): Lane.S,
    ord('b'): Lane.B, ord('B'): Lane.B,
    ord(' '): Lane.SPACE
}

# ═══════════════════════════════════════════════════════════════════════════════
#                              NOTE & RHYTHM
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Note:
    lane: Lane
    spawn_time: float
    y_pos: float = 0.0
    hit: bool = False
    missed: bool = False
    # Decoys are 'noise' notes. A slight fall-speed variance makes them cognitively taxing
    # without being visually marked.
    fall_mult: float = 1.0
    decoy: bool = False  # noise note injected by 'performing'



# ═══════════════════════════════════════════════════════════════════════════════
#                        BIRDSONG KEYSTONE: ATTUNEMENT
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class MicroCue:
    """A micro-cue Birdsong emits: target intensity + tempo shaping + optional pause."""
    start_time: float
    duration: float
    target_intensity: float
    tolerance: float
    tempo_mult: float
    pause: bool
    label: str


class BirdsongAttunement:
    """Signal-Matching Rhythm layer (Birdsong-only).

    The player is rewarded for matching *timing + intensity* with restraint.
    "Performing empathy" (spamming inputs / pressing during pauses / empty hits)
    damages session trust (a volatile meter, separate from permanent trust).
    """

    def __init__(self, duration: float = 45.0, seed: int | None = None, mode: str = 'gentle'):
        self.duration = float(duration)
        self.time = 0.0
        self.trust = 60.0  # 0-100 volatile session trust
        self.score = 0.0   # 0-100 attunement score
        self._press_times: list[float] = []
        self._empty_presses = 0
        self._mode = mode

        # Noise/decoy pressure rises when the player 'performs' instead of listens.
        # Decays over time. 0.0 = clean, 1.0 = heavy noise.
        self._noise = 0.0
        self._last_rate = 0.0
        self._last_within = False
        self._last_err = 999.0

        # Deterministic-ish cue schedule per run.
        rng = random.Random(seed if seed is not None else random.randint(0, 10_000_000))
        base = {'gentle': 35.0, 'steady': 55.0, 'rough': 70.0}.get(mode, 45.0)

        cues: list[MicroCue] = []
        t = 0.0
        # 6–10 cues across the segment
        n = rng.randint(6, 10)
        for i in range(n):
            dur = rng.uniform(3.8, 6.5)
            pause = rng.random() < (0.18 if mode != 'rough' else 0.12)

            # Intensity targets drift, but stay sane
            drift = rng.uniform(-18, 18)
            target = max(10.0, min(90.0, base + drift + i * rng.uniform(-2, 2)))

            # Pause cues want softness + slower tempo
            if pause:
                label = rng.choice(['PAUSE', 'BREATHE', 'HOLD', 'LISTEN'])
                tempo_mult = rng.uniform(0.80, 0.92)
                tolerance = 10.0
            else:
                label = rng.choice(['MATCH', 'EASE', 'FOLLOW', 'SYNC'])
                tempo_mult = rng.uniform(0.92, 1.08)
                tolerance = 14.0

            cues.append(MicroCue(
                start_time=t,
                duration=dur,
                target_intensity=target,
                tolerance=tolerance,
                tempo_mult=tempo_mult,
                pause=pause,
                label=label,
            ))
            t += dur
            if t >= self.duration:
                break

        # Ensure schedule covers full duration
        if cues:
            last = cues[-1]
            if last.start_time + last.duration < self.duration:
                cues[-1] = MicroCue(
                    start_time=last.start_time,
                    duration=self.duration - last.start_time,
                    target_intensity=last.target_intensity,
                    tolerance=last.tolerance,
                    tempo_mult=last.tempo_mult,
                    pause=last.pause,
                    label=last.label,
                )
        self.cues = cues

    def _current_cue(self) -> MicroCue | None:
        for cue in self.cues:
            if cue.start_time <= self.time < cue.start_time + cue.duration:
                return cue
        return self.cues[-1] if self.cues else None

    @property
    def cue_label(self) -> str:
        cue = self._current_cue()
        return cue.label if cue else 'SYNC'

    @property
    def tempo_mult(self) -> float:
        cue = self._current_cue()
        return cue.tempo_mult if cue else 1.0

    @property
    def noise_level(self) -> float:
        """0..1 decoy/noise pressure driven by 'performing'."""
        return float(max(0.0, min(1.0, getattr(self, '_noise', 0.0))))

    @property
    def window_mult(self) -> float:
        """Live timing-window multiplier.

        During pause cues, *calm listening* widens timing windows (reward restraint).
        """
        cue = self._current_cue()
        if cue is None or not cue.pause:
            return 1.0
        rate = float(getattr(self, '_last_rate', 0.0))
        within = bool(getattr(self, '_last_within', False))
        # Calm + in-range = generous windows
        if within and rate <= 0.35:
            return 1.25
        # Some calm still helps
        if within and rate <= 0.80:
            return 1.12
        return 1.0

    @property
    def press_rate(self) -> float:
        """Rolling press rate (presses per second) over the last scoring window."""
        return float(getattr(self, '_last_rate', 0.0))

    @property
    def decoy_spawn_mult(self) -> float:
        """Multiplier applied to decoy spawn interval.

        Calm listening during pause cues *suppresses* decoys (interval grows),
        helping the player 'clean the channel' faster.
        """
        cue = self._current_cue()
        if cue is None or not cue.pause:
            return 1.0
        rate = float(getattr(self, '_last_rate', 0.0))
        within = bool(getattr(self, '_last_within', False))
        if within and rate <= 0.35:
            return 1.85
        if rate <= 0.80:
            return 1.35
        return 1.0


    @property
    def pause_active(self) -> bool:
        cue = self._current_cue()
        return bool(cue.pause) if cue else False

    @property
    def target_intensity(self) -> float:
        cue = self._current_cue()
        return float(cue.target_intensity) if cue else 50.0

    @property
    def tolerance(self) -> float:
        cue = self._current_cue()
        return float(cue.tolerance) if cue else 14.0

    def update(self, dt: float, intensity: float):
        """Continuous scoring based on staying near the target without spamming."""
        self.time = min(self.duration, self.time + max(0.0, float(dt)))

        cue = self._current_cue()
        if cue is None:
            return


        # Intensity error: reward closeness.
        err = abs(float(intensity) - cue.target_intensity)
        within = err <= cue.tolerance

        self._last_within = bool(within)
        self._last_err = float(err)

        # Rolling press rate (last 1.25s)
        window = 1.25
        self._press_times = [t for t in self._press_times if self.time - t <= window]
        rate = len(self._press_times) / window

        self._last_rate = float(rate)

        # Restraint expectations differ by cue type
        max_rate = 1.2 if cue.pause else 3.2
        over_rate = max(0.0, rate - max_rate)

        # Trust + score dynamics
        if within and over_rate <= 0.01:
            self.score = min(100.0, self.score + 0.45 * dt)
            self.trust = min(100.0, self.trust + (0.30 if not cue.pause else 0.20) * dt)
        else:
            # Mild drift penalty
            self.score = max(0.0, self.score - 0.25 * dt)
            # Over-rate is the "performing" signature
            if over_rate > 0.1:
                self.trust = max(0.0, self.trust - (0.90 * over_rate) * dt)
                # Increase noise when performing (spamming/overfitting)
                self._noise = min(1.0, float(getattr(self, '_noise', 0.0)) + (0.18 * over_rate) * dt)


        # Noise decay: the channel clears over time.
        # During pause cues, calm listening accelerates clearing.
        base_decay = 0.06 * dt
        cue_decay = 0.0
        if cue.pause:
            # Reward calm restraint: faster decay when within range and not pressing.
            rate = float(getattr(self, '_last_rate', 0.0))
            within = bool(getattr(self, '_last_within', False))
            if within and rate <= 0.35:
                cue_decay = 0.26 * dt
            elif rate <= 0.80:
                cue_decay = 0.14 * dt
            else:
                cue_decay = 0.06 * dt
        self._noise = max(0.0, float(getattr(self, '_noise', 0.0)) - (base_decay + cue_decay))

        # If cue is a pause, high intensity itself is noisy
        if cue.pause and float(intensity) > cue.target_intensity + cue.tolerance:
            self.trust = max(0.0, self.trust - 0.35 * dt)
            self._noise = min(1.0, float(getattr(self, '_noise', 0.0)) + 0.10 * dt)

    def register_press(self, *, quality: str, is_empty: bool, intensity: float):
        """Discrete event scoring—captures spamming/empty presses."""
        self._press_times.append(self.time)
        cue = self._current_cue()
        if cue is None:
            return


        # Empty presses are pure "performing"—they aren't listening.
        if is_empty:
            self._empty_presses += 1
            self.trust = max(0.0, self.trust - 2.2)
            self.score = max(0.0, self.score - 1.0)
            self._noise = min(1.0, float(getattr(self, '_noise', 0.0)) + 0.35)
            return

        # v8: no pause-cue press penalty. Rhythm never stops for lines,
        # so pressing is always legitimate play, never "anti-flow".

        # Reward precision if intensity is near the cue target.
        err = abs(float(intensity) - cue.target_intensity)
        if err <= cue.tolerance:
            bonus = 0.9 if quality == 'perfect' else 0.6 if quality == 'great' else 0.3
            self.trust = min(100.0, self.trust + bonus)
            self.score = min(100.0, self.score + bonus * 0.8)
        else:
            # Pressing hard when out of sync is "overfitting".
            self.trust = max(0.0, self.trust - 0.8)
            self.score = max(0.0, self.score - 0.4)

    def intensity_nudge(self, intensity: float) -> float:
        """Suggest a small intensity adjustment to steer toward the cue target."""
        cue = self._current_cue()
        if cue is None:
            return 0.0
        x = float(intensity)
        if cue.pause:
            # During pauses, encourage softness.
            if x > cue.target_intensity + cue.tolerance:
                return -1.5
            return -0.3
        # Non-pause: small guidance only.
        if x > cue.target_intensity + cue.tolerance:
            return -0.8
        if x < cue.target_intensity - cue.tolerance:
            return +0.4
        return 0.0

class IntimacyRhythm:
    """Continuous rhythm with building tempo"""

    def __init__(self):
        self.notes: List[Note] = []
        self.time = 0.0
        # GEN 34: intensity-mode capable rhythm params (safe defaults)
        self.base_bpm = 84.0  # tuned: starts engaging without rush
        self.bpm_range = 156.0  # tuned: 84 → 240 at max intensity
        self.bpm = self.base_bpm  # Start slow
        self.target_bpm = self.base_bpm + self.bpm_range  # For reference / debugging
        self.beat_duration = 60.0 / self.bpm
        self.fall_time_base = 3.0
        self.fall_time_range = 1.5  # 3.0 → 1.5 seconds
        self.fall_time = self.fall_time_base
        self.next_spawn = 0.5

        # Intensity (0-100)
        self.intensity = 0.0
        self.combo = 0
        self.max_combo = 0

        # Timing windows (seconds). These are multiplied by window_mult.
        self.window_mult = 1.0

        # Birdsong attunement live modifiers (set externally each frame)
        self.live_bpm_mult = 1.0
        self.live_window_mult = 1.0  # widens timing windows during calm pause cues
        self.spawn_suppressed = False

        # Noise/decoy pressure (0..1). When >0, we inject decoy notes.
        self.noise_level = 0.0
        self.next_decoy = 1.25

        # Decoy spawn shaping (Birdsong-only; safe defaults)
        self.decoy_spawn_mult = 1.0  # >1 = fewer decoys
        self._cognitive_load = 0.0   # smoothed 0..3-ish
        self._overwhelm = 0.0        # rises on errors/decoy hits; decays over time

        self.perfect_window_base = 0.10
        self.great_window_base = 0.18
        self.good_window_base = 0.28
        self.perfect_window = self.perfect_window_base
        self.great_window = self.great_window_base
        self.good_window = self.good_window_base

        # State
        self.complete = False
        self.duration = 90.0  # 90 second scene

    def apply_mode_modifiers(self, bpm_mult: float = 1.0, window_mult: float = 1.0):
        """GEN 34: Apply intensity mode modifiers.

        Safety: clamps keep timing windows beatable.
        """
        def clamp(x: float, lo: float, hi: float) -> float:
            return max(lo, min(hi, x))

        self.base_bpm = clamp(self.base_bpm * float(bpm_mult), 60.0, 220.0)
        self.bpm_range = clamp(self.bpm_range * float(bpm_mult), 80.0, 220.0)
        self.target_bpm = self.base_bpm + self.bpm_range

        self.window_mult = clamp(float(window_mult), 0.78, 1.25)

        self.perfect_window = self.perfect_window_base * self.window_mult
        self.great_window = self.great_window_base * self.window_mult
        # Good window is the true "playability gate".
        self.good_window = clamp(self.good_window_base * self.window_mult, 0.22, 0.40)

    def update(self, dt: float) -> List[Tuple[str, Lane]]:
        events = []
        self.time += dt

        # Gradually increase tempo with intensity
        progress = self.intensity / 100.0

        # Flow-tuned tempo shaping:
        # - Start at an engaging pace (not sleepy)
        # - Accelerate non-linearly so early intimacy is readable and late intimacy is thrilling
        # - Allow attunement to push tempo slightly when SYNC is high, and rein it in when noise is high
        effective_mult = max(0.80, min(1.50, float(getattr(self, 'live_bpm_mult', 1.0))))
        base = self.base_bpm * effective_mult
        rng = self.bpm_range * effective_mult

        # Non-linear ramp (slower early, faster late)
        ramp = pow(max(0.0, min(1.0, progress)), 1.10)

        self.bpm = base + (ramp * rng)

        # Absolute ceiling (kept high, but not unreadable)
        self.bpm = clamp(self.bpm, 55.0, 255.0)
        self.beat_duration = 60.0 / self.bpm
        self.fall_time = max(0.75, self.fall_time_base - progress * self.fall_time_range)

        # Live window shaping (pause cues can widen timing windows when calm)
        live_w = max(0.85, min(1.35, float(getattr(self, 'live_window_mult', 1.0))))
        eff = max(0.78, min(1.35, float(getattr(self, 'window_mult', 1.0)) * live_w))
        self.perfect_window = self.perfect_window_base * eff
        self.great_window = self.great_window_base * eff
        self.good_window = max(0.22, min(0.40, self.good_window_base * eff))

        # Spawn notes (can be suppressed by Birdsong attunement pause cues)
        if not getattr(self, "spawn_suppressed", False):
            if self.time >= self.next_spawn:
                self._spawn_note()
        else:
            # Push next spawn forward so we don't instantly dump notes when pause ends
            self.next_spawn = max(self.next_spawn, self.time + self.beat_duration * 0.85)

        # Inject decoy notes/noise when the player is 'performing' (Birdsong-only; set externally).
        # These are meant to tax attention (mental bandwidth) without becoming an infinite punishment loop:
        # if the channel is already overloaded, decoy spawning backs off ("gives up").
        nl = float(getattr(self, 'noise_level', 0.0))

        # Cognitive load estimation (smoothed): active notes + active decoys + high-noise haze.
        active_decoys = sum(1 for n in self.notes if getattr(n, 'decoy', False) and (not n.hit) and (not n.missed))
        active_notes = sum(1 for n in self.notes if (not n.hit) and (not n.missed))
        target_load = (active_decoys * 0.95) + (active_notes * 0.22) + (0.6 if nl > 0.65 else 0.0)
        k = min(1.0, dt * 2.0)
        self._cognitive_load = float(getattr(self, '_cognitive_load', 0.0)) + (target_load - float(getattr(self, '_cognitive_load', 0.0))) * k

        # Overwhelm decays; rises elsewhere on decoy hits/empty presses.
        self._overwhelm = max(0.0, float(getattr(self, '_overwhelm', 0.0)) - 0.30 * dt)

        # Adaptive cap: when load is high, stop stacking decoys.
        max_decoys_allowed = 1 if (self._cognitive_load > 1.85 or nl > 0.78) else 2
        allow_decoy = (active_decoys < max_decoys_allowed) and (self._overwhelm < 1.35)

        if nl > 0.05 and allow_decoy and self.time >= float(getattr(self, 'next_decoy', 0.0)):
            self._spawn_decoy_note(nl)
            # Signal decoy spawn to callers (e.g., ImpStage)
            try:
                events.append(('decoy_spawn', Lane.A))
            except Exception:
                pass
        elif nl > 0.05 and (not allow_decoy) and self.time >= float(getattr(self, 'next_decoy', 0.0)):
            # Channel is overloaded; decoy system backs off ("gives up") and we signal it once per interval.
            try:
                events.append(('noise_backoff', Lane.A))
            except Exception:
                pass
            # Push the next-decoy time forward so we don't re-trigger every frame.
            self.next_decoy = self.time + self.beat_duration * max(0.9, 1.2 * float(getattr(self, 'decoy_spawn_mult', 1.0)))

        # Update notes
        for note in self.notes:
            if not note.hit and not note.missed:
                denom = self.fall_time * max(0.70, float(getattr(note, 'fall_mult', 1.0)))
                note.y_pos = (self.time - note.spawn_time) / denom

                if note.y_pos > 1.0 + self.good_window / self.fall_time:
                    note.missed = True
                    # Decoys are just noise: missing them is neutral.
                    if getattr(note, 'decoy', False):
                        continue
                    # GRIP-AS-COMBO-HEALTH: combo only breaks on a slip (grip→0).
                    # Regular note expiry just drains intensity — grip handles the rest.
                    # self.combo = 0  ← removed
                    self.intensity = max(0, self.intensity - 2)
                    events.append(('miss', note.lane))

        # Clean up
        self.notes = [n for n in self.notes if n.y_pos < 1.5]

        # Check completion
        if self.intensity >= 100 or self.time >= self.duration:
            self.complete = True

        return events

    def _spawn_note(self):
        # Weight lanes based on intensity tier
        tier = get_intensity_tier(self.intensity)
        if tier == "building":
            weights = [0.35, 0.35, 0.15, 0.15]  # More A/S (touch/hold)
        elif tier == "peak":
            weights = [0.25, 0.25, 0.35, 0.15]  # More B (rhythm)
        else:
            weights = [0.20, 0.20, 0.40, 0.20]  # B dominant, SPACE for connection

        lane = random.choices(list(Lane), weights=weights)[0]
        self.notes.append(Note(lane=lane, spawn_time=self.time))

        # Next spawn based on tempo
        variance = random.uniform(0.8, 1.2)
        self.next_spawn = self.time + self.beat_duration * variance

    def _spawn_decoy_note(self, noise_level: float = 0.5):
        """Spawn a decoy (noise) note.

        Design goals:
          - Keep mental bandwidth high: decoys are plausible and require attention to discriminate.
          - Avoid endless punishment: if the channel is overloaded, decoy rate backs off.
        Missing a decoy is neutral; hitting it is punished upstream.
        """
        nl = max(0.0, min(1.0, float(noise_level)))

        lane = random.choice(list(Lane))
        note = Note(lane=lane, spawn_time=self.time, decoy=True)

        # Subtle fall-speed variance makes decoys feel "off" to an attentive player
        # (a learnable tell), without visually marking them.
        freq_peak = max(0.0, 1.0 - abs(nl - 0.5) * 1.8)  # peak around nl≈0.5
        var_amt = 0.08 + 0.18 * freq_peak
        note.fall_mult = max(0.78, min(1.22, 1.0 + random.uniform(-var_amt, var_amt)))

        self.notes.append(note)

        # Next decoy timing:
        # - rises with moderate noise (player is overfitting)
        # - but backs off when noise is extreme or cognitive load is high ("gives up")
        base_interval = 1.40 - 0.85 * freq_peak          # 1.40 → 0.55 beats
        interval_beats = max(0.55, base_interval)

        # External suppression multiplier (pause-cue calm listening).
        interval_beats *= max(1.0, float(getattr(self, 'decoy_spawn_mult', 1.0)))

        # Backoff with overload/overwhelm.
        load = float(getattr(self, '_cognitive_load', 0.0))
        ov = float(getattr(self, '_overwhelm', 0.0))
        interval_beats *= (1.0 + 0.55 * max(0.0, load - 1.4) + 0.75 * ov)

        # If noise is extreme, the system stops piling on.
        if nl > 0.85:
            interval_beats *= 1.6

        variance = random.uniform(0.80, 1.30)
        self.next_decoy = self.time + self.beat_duration * interval_beats * variance


    def hit_lane(self, lane: Lane) -> Tuple[str, Optional[Note]]:
        best_dist = float('inf')
        best_note = None
        # INPUT LATENCY FIX (2026-09-25): user-calibratable offset in seconds.
        # Positive = player tends to hit late (shifts the hit line later).
        # Set via BRATBOX_INPUT_OFFSET_MS env var (e.g. "25" for +25ms).
        try:
            _offset_ms = float(__import__("os").environ.get("BRATBOX_INPUT_OFFSET_MS", "0") or "0")
        except Exception:
            _offset_ms = 0.0
        _offset_y = (_offset_ms / 1000.0) / max(0.1, self.fall_time)

        for note in self.notes:
            if note.lane == lane and not note.hit and not note.missed:
                dist = abs(note.y_pos - 1.0 - _offset_y) * self.fall_time
                if dist < best_dist and dist < self.good_window:
                    best_dist = dist
                    best_note = note

        if best_note is None:
            return ('empty', None)

        best_note.hit = True

        # Decoy notes are noise: they should not reward intensity/combos.
        if getattr(best_note, 'decoy', False):
            # Small immediate combo disruption; intensity penalty handled by caller.
            self.combo = max(0, int(self.combo) - 1)
            # Decoy hits imply the player is overloaded / overfitting; increase overwhelm,
            # which reduces future decoy spam ("the system gives up" if it's too much).
            self._overwhelm = min(3.0, float(getattr(self, '_overwhelm', 0.0)) + 0.35)
            return ('decoy', best_note)

        self.combo += 1
        self.max_combo = max(self.max_combo, self.combo)

        # Intensity gain
        if best_dist <= self.perfect_window:
            self.intensity = min(100, self.intensity + 3)
            return ('perfect', best_note)
        elif best_dist <= self.great_window:
            self.intensity = min(100, self.intensity + 2)
            return ('great', best_note)

        self.intensity = min(100, self.intensity + 1)
        return ('good', best_note)

    def register_empty_press(self):
        """Tell the rhythm system an empty press happened (Birdsong keystone uses this).

        Used to model overwhelm / bandwidth pressure so decoy spawning can back off.
        """
        self._overwhelm = min(3.0, float(getattr(self, '_overwhelm', 0.0)) + 0.20)

# ═══════════════════════════════════════════════════════════════════════════════
#                              DIALOGUE SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

class IntimacyDialogue:
    """Reactive dialogue based on lane hits"""

    def __init__(self):
        self.fiend_line = ""
        self.bird_line = ""
        self.inner_line = ""

        self.fiend_timer = 0.0
        self.bird_timer = 0.0
        self.inner_timer = 0.0

        # Track recent lines to avoid repetition
        self.recent_bird: List[str] = []
        self.recent_fiend: List[str] = []

    def trigger_hit(self, lane: Lane, quality: str, intensity: float):
        """Trigger dialogue for a successful hit"""
        tier = get_intensity_tier(intensity)
        lane_data = LANE_DIALOGUES.get(lane.value, LANE_A_DIALOGUE)

        # Get fiend line
        fiend_pool = lane_data["fiend"][tier]
        ctx = cascade_engine.CascadeContext(intensity=float(intensity), lane=str(lane.value), quality=str(quality))
        self.fiend_line = self._pick_fresh(fiend_pool, self.recent_fiend, speaker="FIEND", ctx=ctx)
        self.fiend_timer = 1.5

        # Get bird line (longer display)
        bird_pool = lane_data["bird"][tier]
        self.bird_line = self._pick_fresh(bird_pool, self.recent_bird, speaker="BIRDSONG", ctx=ctx)
        self.bird_timer = 2.0

        # Inner monologue (less frequent)
        if random.random() < 0.3:
            inner_pool = lane_data["inner"][tier]
            self.inner_line = cascade_engine.choose_from_pool(inner_pool, "INNER", ctx=ctx, sample=8)
            self.inner_timer = 2.5

    def trigger_miss(self, lane: Lane, intensity: float):
        """Trigger dialogue for a miss"""
        ctx = cascade_engine.CascadeContext(intensity=float(intensity), lane=str(lane.value), quality="miss")
        self.fiend_line = cascade_engine.choose_from_pool(MISS_DIALOGUE["fiend"], "FIEND", ctx=ctx, sample=8)
        self.fiend_timer = 1.0

        self.bird_line = cascade_engine.choose_from_pool(MISS_DIALOGUE["bird"], "BIRDSONG", ctx=ctx, sample=8)
        self.bird_timer = 1.5

        if random.random() < 0.5:
            self.inner_line = cascade_engine.choose_from_pool(MISS_DIALOGUE["inner"], "INNER", ctx=ctx, sample=6)
            self.inner_timer = 2.0

    def _pick_fresh(self, pool: List[str], recent: List[str], speaker: str = "", ctx: 'cascade_engine.CascadeContext' = None) -> str:
        """Pick a line not recently used"""
        available = [l for l in pool if l not in recent]
        if not available:
            available = pool
            recent.clear()

        choice = cascade_engine.choose_from_pool(available, speaker or "UNKNOWN", ctx=ctx) if speaker else random.choice(available)
        recent.append(choice)
        if len(recent) > 3:
            recent.pop(0)
        return choice

    def update(self, dt: float):
        self.fiend_timer = max(0, self.fiend_timer - dt)
        self.bird_timer = max(0, self.bird_timer - dt)
        self.inner_timer = max(0, self.inner_timer - dt)


# ═══════════════════════════════════════════════════════════════════════════════
#                              ENCORE DIALOGUE
# ═══════════════════════════════════════════════════════════════════════════════

# Encore-specific dialogue pools - cockier, more playful, references round one
ENCORE_LANE_A = {  # Touch - now familiar
    "fiend": {
        "building": ["Again.", "Missed this.", "Can't stop.", "More.", "Mine."],
        "peak": ["Insatiable.", "Good girl.", "Don't pretend.", "You wanted this.", "There."],
        "release": ["AGAIN.", "Take it.", "All of it.", "Yes.", "Mine."],
    },
    "bird": {
        "building": [
            "Oy~ we JUST— mmhh— okay—",
            "Fieeeenddd~ I thought we were— hahhh—",
            "Round two already— ghhh—",
            "You're insatiable— mmhh—",
            "I literally JUST caught my breath—",
        ],
        "peak": [
            "Hahhh— I KNEW you weren't done—",
            "Ghhh— okay okay OKAY—",
            "Show me— mmhh— show me again—",
            "Fieeeenddd~ MORE—",
            "I can take it— yessss~",
        ],
        "release": [
            "HAHHH— again— AGAIN—",
            "Don't stop— ghhh— DON'T—",
            "Fieeeenddd~ I'm— I'm gonna— AGAIN—",
            "YES— mmhh— YES—",
            "Everything— hahhh— EVERYTHING—",
        ],
    },
    "inner": {
        "building": ["He wasn't done. Neither was I.", "Round two."],
        "peak": ["Even better the second time.", "He knows exactly where now."],
        "release": ["Again. Again. Again.", "I'll never recover from this."],
    },
}

ENCORE_LANE_S = {  # Hold - possessive
    "fiend": {
        "building": ["Not letting go.", "Stay.", "Mine.", "Again.", "Here."],
        "peak": ["You're not going anywhere.", "I've got you.", "Stay down.", "Good.", "There."],
        "release": ["MINE.", "Don't you dare.", "Stay.", "I've got you.", "Fall."],
    },
    "bird": {
        "building": [
            "Mmhh— possessive— hahhh—",
            "I wasn't LEAVING— ghhh—",
            "Oy~ clingy much— yessss~",
            "Hold tighter— mmhh—",
            "Fieeeenddd~ I'm here—",
        ],
        "peak": [
            "Hahhh— don't let go— ever—",
            "Ghhh— I'm not going ANYWHERE—",
            "Yours— mmhh— I'm yours—",
            "Hold me down— yessss~",
            "Fieeeenddd~ PLEASE—",
        ],
        "release": [
            "HAHHH— I'm— I'm yours—",
            "Never letting go— ghhh— NEVER—",
            "Fieeeenddd~ catch me— CATCH—",
            "Falling— mmhh— FALLING—",
            "HOLD— HOLD— HOLD—",
        ],
    },
    "inner": {
        "building": ["He's claiming me.", "I want to be claimed."],
        "peak": ["Owned. Completely owned.", "I asked for this."],
        "release": ["His. Entirely his.", "Best decision I ever made."],
    },
}

ENCORE_LANE_B = {  # Rhythm - harder
    "fiend": {
        "building": ["Harder.", "You can take more.", "Don't hold back.", "Move.", "Now."],
        "peak": ["HARDER.", "That's it.", "More.", "Don't stop.", "Yes."],
        "release": ["NOW.", "COME.", "With me.", "Let GO.", "YES."],
    },
    "bird": {
        "building": [
            "Ghhh— already— hahhh—",
            "Oy~ fieeeenddd~ PACE yourself— mmhh—",
            "I can— hahhh— I can take it—",
            "Harder— ghhh— I said HARDER—",
            "Don't hold back— mmhh—",
        ],
        "peak": [
            "HAHHH— YES— THERE—",
            "Ghhh— don't— DON'T slow down—",
            "More— mmhh— MORE—",
            "Fieeeenddd~ PLEASE—",
            "Right— THERE— yessss~",
        ],
        "release": [
            "HAHHH— I'M— AGAIN—",
            "Fieeeenddd~ I CAN'T— I CAN'T—",
            "GHHH— OH GOD— GHHH—",
            "YES— YES— YES— YES—",
            "MMHH— COMING— I'M—",
        ],
    },
    "inner": {
        "building": ["He's not holding back anymore.", "Good."],
        "peak": ["Everything. He's giving everything.", "So am I."],
        "release": ["Shattered. Rebuilt. Shattered again.", "Perfect."],
    },
}

ENCORE_LANE_SPACE = {  # Eyes - intimate callback
    "fiend": {
        "building": ["Remember this.", "See me.", "Right here.", "Don't look away.", "Good."],
        "peak": ["I see everything.", "You're beautiful.", "Stay with me.", "There.", "Mine."],
        "release": ["Perfect.", "I see you.", "Beautiful.", "Mine.", "Yes."],
    },
    "bird": {
        "building": [
            "Mmhh— I remember— hahhh—",
            "The way you look at me— ghhh—",
            "Oy~ stop LOOKING at me like— yessss~",
            "I see you too— mmhh—",
            "Fieeeenddd~ your EYES—",
        ],
        "peak": [
            "Hahhh— don't blink— please—",
            "Ghhh— you see everything— I know—",
            "Look at me— mmhh— LOOK—",
            "I'm here— yessss~ I'm here—",
            "Fieeeenddd~ don't look away—",
        ],
        "release": [
            "HAHHH— see me— SEE ME—",
            "Ghhh— I'm yours— you see—",
            "Fieeeenddd~ witness— WITNESS—",
            "Everything— mmhh— you see EVERYTHING—",
            "I'm— I'm— hahhh— YOURS—",
        ],
    },
    "inner": {
        "building": ["He remembers too.", "Every moment recorded."],
        "peak": ["Witnessed. Again.", "He sees all of me now."],
        "release": ["Seen. Known. Loved.", "This is real."],
    },
}

ENCORE_DIALOGUES = {
    0: ENCORE_LANE_A,
    1: ENCORE_LANE_S,
    2: ENCORE_LANE_B,
    3: ENCORE_LANE_SPACE,
}

ENCORE_MISS = {
    "fiend": ["Focus.", "Stay with me.", "Again.", "Don't fade.", "Here."],
    "bird": [
        "Hahhh— sorry— mmhh— tired—",
        "Ghhh— give me a SECOND—",
        "Oy~ I'm only HUMAN— hahhh—",
        "Fieeeenddd~ pace—",
        "Mmhh— I'll catch up—",
    ],
    "inner": ["Overwhelmed. Keep going.", "Don't break now.", "Almost there."],
}

# Combo reward dialogue (when angled_collapse triggers)
COMBO_REWARD_DIALOGUE = {
    "fiend": ["Come here.", "MINE.", "Now.", "There.", "Good girl."],
    "bird": [
        "HAHHH— fieeeenddd—",
        "Ghhh— when you PULL me like—",
        "Oy~ WARN me before you— mmhh—",
        "Yessss~ like THAT—",
        "Oh— OH— hahhh—",
    ],
}

class EncoreDialogue(IntimacyDialogue):
    """Spicier dialogue for round two"""

    def trigger_hit(self, lane: Lane, quality: str, intensity: float):
        """Trigger encore-specific dialogue"""
        tier = get_intensity_tier(intensity)
        lane_data = ENCORE_DIALOGUES.get(lane.value, ENCORE_LANE_A)

        fiend_pool = lane_data["fiend"][tier]
        self.fiend_line = self._pick_fresh(fiend_pool, self.recent_fiend)
        self.fiend_timer = 1.5

        bird_pool = lane_data["bird"][tier]
        self.bird_line = self._pick_fresh(bird_pool, self.recent_bird)
        self.bird_timer = 2.0

        if random.random() < 0.3:
            inner_pool = lane_data["inner"][tier]
            self.inner_line = random.choice(inner_pool)
            self.inner_timer = 2.5

    def trigger_miss(self, lane: Lane, intensity: float):
        """Trigger encore miss dialogue"""
        self.fiend_line = random.choice(ENCORE_MISS["fiend"])
        self.fiend_timer = 1.0

        self.bird_line = random.choice(ENCORE_MISS["bird"])
        self.bird_timer = 1.5

        if random.random() < 0.5:
            self.inner_line = random.choice(ENCORE_MISS["inner"])
            self.inner_timer = 2.0

    def trigger_combo_reward(self):
        """Trigger dialogue for the pull (angled_collapse)"""
        self.fiend_line = random.choice(COMBO_REWARD_DIALOGUE["fiend"])
        self.fiend_timer = 2.0

        self.bird_line = random.choice(COMBO_REWARD_DIALOGUE["bird"])
        self.bird_timer = 2.5


# ═══════════════════════════════════════════════════════════════════════════════
#                         FERAL MODE: DIRTY FLOWER (OUTHOUSE)
# ═══════════════════════════════════════════════════════════════════════════════

# She just used the outhouse. He knows. He's leaning INTO it.
# Humiliation → liberation. "Did I say you could bloom?"

FERAL_LANE_A = {  # Touch - acknowledging the smell, the reality
    "fiend": {
        "building": [
            "Smell that?",
            "Don't pretend.",
            "I know where you were.",
            "Dirty girl.",
            "Mm. Natural.",
        ],
        "peak": [
            "Did I say you could bloom?",
            "Every part of you.",
            "Even this.",
            "Especially this.",
            "Don't hide.",
        ],
        "release": [
            "Beautiful creature.",
            "All of it. Mine.",
            "Filthy flower.",
            "Let me see everything.",
            "There's nothing to hide.",
        ],
    },
    "bird": {
        "building": [
            "Oy~ fieeeenddd~ don't— hahhh— don't MENTION—",
            "I JUST— ghhh— I needed to— mmhh—",
            "This is SO unfair— you can't just—",
            "Fieeeenddd~ I'm MORTIFIED—",
            "Stop SMELLING me— hahhh—",
        ],
        "peak": [
            "You're— ghhh— you're not supposed to LIKE—",
            "Hahhh— this is— mmhh— this is WRONG—",
            "Fieeeenddd~ I'm disgusting right now—",
            "Why does that— ghhh— why does that WORK—",
            "Stop— mmhh— don't stop— STOP—",
        ],
        "release": [
            "Hahhh— you LIKE it— ghhh— you actually—",
            "Fieeeenddd~ I'm— mmhh— I'm not supposed to—",
            "Every part— hahhh— you want EVERY part—",
            "Ghhh— even this— yessss~ even THIS—",
            "I'm so— hahhh— I'm so GROSS and you're still—",
        ],
    },
    "inner": {
        "building": ["He knows. He KNOWS.", "I can't hide anything."],
        "peak": ["He's not disgusted. He's... interested.", "Oh no."],
        "release": ["All of me. He wants ALL of me.", "Even the parts I hide."],
    },
}

FERAL_LANE_S = {  # Hold - wanting the raw, unpolished version
    "fiend": {
        "building": [
            "Stay. Just like that.",
            "Don't clean up.",
            "Raw.",
            "This is you.",
            "Let me hold the real thing.",
        ],
        "peak": [
            "The version you hide.",
            "I want her.",
            "Unpolished.",
            "Messy.",
            "Human.",
        ],
        "release": [
            "Perfect creature.",
            "Stink and all.",
            "ESPECIALLY the stink.",
            "You thought I wanted the mask?",
            "I want the animal underneath.",
        ],
    },
    "bird": {
        "building": [
            "Fieeeenddd~ let me SHOWER first—",
            "Ghhh— I'm not— hahhh— presentable—",
            "This is— mmhh— this is humiliating—",
            "You're holding me like I DIDN'T just—",
            "Oy~ at least let me WASH—",
        ],
        "peak": [
            "Hahhh— you really don't care— ghhh—",
            "Fieeeenddd~ I smell like— mmhh—",
            "Why is this— ghhh— why does this feel—",
            "You're SNIFFING me— hahhh— on PURPOSE—",
            "Mmhh— this shouldn't— yessss~ this shouldn't—",
        ],
        "release": [
            "Hahhh— no one's ever— ghhh— WANTED this—",
            "Fieeeenddd~ you want the REAL— mmhh—",
            "All of it— hahhh— you want ALL of it—",
            "Ghhh— even when I'm— yessss~ especially when—",
            "I don't have to— hahhh— I don't have to HIDE—",
        ],
    },
    "inner": {
        "building": ["He's not letting me clean up first.", "On purpose."],
        "peak": ["He wants me like THIS?", "Unfiltered."],
        "release": ["Seen. Smelled. Known. Wanted.", "All of me."],
    },
}

FERAL_LANE_B = {  # Rhythm - making animal sounds, rutting
    "fiend": {
        "building": [
            "Bodies do things.",
            "You're not above it.",
            "Neither am I.",
            "Human.",
            "Real.",
        ],
        "peak": [
            "Grunt for me.",
            "Make noise.",
            "The ugly sounds.",
            "Don't hold back.",
            "Let it out.",
        ],
        "release": [
            "There she is.",
            "The animal.",
            "Beautiful beast.",
            "Rut.",
            "Bloom.",
        ],
    },
    "bird": {
        "building": [
            "Ghhh— you want me to be— hahhh— LOUD?",
            "Fieeeenddd~ I sound like— mmhh— a farm animal—",
            "This is— ghhh— this is so CRUDE—",
            "Oy~ I can't believe you're— hahhh—",
            "Mmhh— making me— ghhh— grunt like—",
        ],
        "peak": [
            "HAHHH— I sound— ghhh— I sound FERAL—",
            "Fieeeenddd~ I'm— mmhh— I'm an ANIMAL—",
            "Ghhh— GHHH— oh god the SOUNDS—",
            "This is— hahhh— this is OBSCENE—",
            "Oy~ I can't— mmhh— believe my own BODY—",
        ],
        "release": [
            "GHHH— GHHHHH— I'M— HAHHH—",
            "Fieeeenddd~ I'm RUTTING— mmhh— like a—",
            "Every sound— ghhh— EVERY sound— hahhh—",
            "BEAST— I'm a— yessss~ I'm YOUR beast—",
            "Bloom— hahhh— BLOOMING— ghhh— dirty flower—",
        ],
    },
    "inner": {
        "building": ["He wants the sounds I hide.", "The ugly ones."],
        "peak": ["I'm making noises I didn't know I could make.", "Animal."],
        "release": ["Rutting. Actually rutting.", "His dirty flower."],
    },
}

FERAL_LANE_SPACE = {  # Eyes - seeing the real her, no masks
    "fiend": {
        "building": [
            "Look at me.",
            "Don't be ashamed.",
            "I see you.",
            "The real you.",
            "Nothing hidden.",
        ],
        "peak": [
            "You thought I'd judge?",
            "I've been waiting for this.",
            "The mask off.",
            "Finally.",
            "There you are.",
        ],
        "release": [
            "Beautiful.",
            "Filthy and perfect.",
            "My creature.",
            "Bloom for me.",
            "Let me witness.",
        ],
    },
    "bird": {
        "building": [
            "Ghhh— don't LOOK at me— hahhh— not now—",
            "Fieeeenddd~ I'm— mmhh— I'm a MESS—",
            "You're seeing me at my— ghhh— WORST—",
            "Oy~ this is— hahhh— so VULNERABLE—",
            "Mmhh— you're WATCHING me— ghhh— like this—",
        ],
        "peak": [
            "Hahhh— you're not— ghhh— disgusted?",
            "Fieeeenddd~ you're looking at me like I'm— mmhh—",
            "How can you— ghhh— SEE this and still—",
            "Oy~ your EYES— hahhh— they're so—",
            "Mmhh— you actually— ghhh— you LIKE this—",
        ],
        "release": [
            "Hahhh— seen— ghhh— TRULY seen—",
            "Fieeeenddd~ all of it— mmhh— you see ALL—",
            "No hiding— hahhh— no masks— ghhh—",
            "BLOOM— yessss~ blooming for you— hahhh—",
            "Witness— mmhh— WITNESS me— ghhh—",
        ],
    },
    "inner": {
        "building": ["He's looking at me. The REAL me.", "Terrifying."],
        "peak": ["No disgust. Just... hunger.", "For THIS?"],
        "release": ["Witnessed at my lowest. Wanted anyway.", "Free."],
    },
}

FERAL_DIALOGUES = {
    0: FERAL_LANE_A,
    1: FERAL_LANE_S,
    2: FERAL_LANE_B,
    3: FERAL_LANE_SPACE,
}

FERAL_COMBO_REWARD = {
    "fiend": [
        "Come here, creature.",
        "My filthy flower.",
        "Let me smell you.",
        "All of it.",
        "Bloom.",
    ],
    "bird": [
        "FIEEEENDDD~ ghhh— when you PULL me like— hahhh—",
        "Oy~ you want me CLOSER— mmhh— even though I—",
        "Ghhh— you're INHALING— hahhh— oh god—",
        "Yessss~ take it— mmhh— take ALL of it—",
        "Hahhh— dirty flower— ghhh— BLOOMING—",
    ],
}

FERAL_MISS = {
    "fiend": ["Stay present.", "Don't retreat.", "I see you hiding.", "Come back.", "Stay messy."],
    "bird": [
        "Ghhh— I got self-conscious— hahhh—",
        "Fieeeenddd~ I remembered what I— mmhh—",
        "Oy~ the SMELL— I just— ghhh—",
        "Hahhh— sorry— I'm— mmhh— embarrassed—",
        "Let me just— ghhh— give me a second—",
    ],
    "inner": ["The shame crept back in.", "Focus. He wants this."],
}


class FeralDialogue(IntimacyDialogue):
    """Dirty flower mode - outhouse scene dialogue"""

    def trigger_hit(self, lane: Lane, quality: str, intensity: float):
        """Trigger feral-specific dialogue"""
        tier = get_intensity_tier(intensity)
        lane_data = FERAL_DIALOGUES.get(lane.value, FERAL_LANE_A)

        fiend_pool = lane_data["fiend"][tier]
        self.fiend_line = self._pick_fresh(fiend_pool, self.recent_fiend)
        self.fiend_timer = 1.8  # Slightly longer for reading

        bird_pool = lane_data["bird"][tier]
        self.bird_line = self._pick_fresh(bird_pool, self.recent_bird)
        self.bird_timer = 2.5  # Longer - lots of NLS texture

        # Inner more frequent in feral - the humiliation/liberation arc
        if random.random() < 0.4:
            inner_pool = lane_data["inner"][tier]
            self.inner_line = random.choice(inner_pool)
            self.inner_timer = 3.0

    def trigger_miss(self, lane: Lane, intensity: float):
        """Trigger feral miss - shame creeping back"""
        self.fiend_line = random.choice(FERAL_MISS["fiend"])
        self.fiend_timer = 1.2

        self.bird_line = random.choice(FERAL_MISS["bird"])
        self.bird_timer = 2.0

        if random.random() < 0.6:  # More inner on miss - shame
            self.inner_line = random.choice(FERAL_MISS["inner"])
            self.inner_timer = 2.5

    def trigger_combo_reward(self):
        """Trigger dialogue for the pull - dirty flower moment"""
        self.fiend_line = random.choice(FERAL_COMBO_REWARD["fiend"])
        self.fiend_timer = 2.5

        self.bird_line = random.choice(FERAL_COMBO_REWARD["bird"])
        self.bird_timer = 3.0

# ═══════════════════════════════════════════════════════════════════════════════
#                              PARTICLE SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    char: str
    life: float
    max_life: float
    color: int = 0

class ParticleSystem:
    HIT_CHARS = ['✦', '✧', '◆', '◇', '★', '☆', '·', '•', '°', '♥']
    MISS_CHARS = ['×', '✕', '─', '·']

    def __init__(self):
        self.particles: List[Particle] = []

    def spawn_hit(self, x: int, y: int, quality: str, intensity: float, color: int):
        count = {'perfect': 15, 'great': 10, 'good': 6}.get(quality, 6)
        speed = 6 + intensity / 20
        life = 0.6 + intensity / 200

        # More hearts at high intensity
        chars = self.HIT_CHARS
        if intensity > 70:
            chars = self.HIT_CHARS + ['♥', '♥', '♥']

        for _ in range(count):
            angle = random.uniform(0, math.pi * 2)
            spd = random.uniform(speed * 0.5, speed)
            self.particles.append(Particle(
                x=float(x), y=float(y),
                vx=math.cos(angle) * spd,
                vy=math.sin(angle) * spd * 0.5,
                char=random.choice(chars),
                life=random.uniform(life * 0.7, life),
                max_life=life,
                color=color
            ))

    def spawn_miss(self, x: int, y: int, color: int):
        for _ in range(4):
            self.particles.append(Particle(
                x=float(x) + random.uniform(-2, 2),
                y=float(y),
                vx=random.uniform(-1, 1),
                vy=random.uniform(2, 4),
                char=random.choice(self.MISS_CHARS),
                life=random.uniform(0.3, 0.5),
                max_life=0.5,
                color=color
            ))

    def update(self, dt: float):
        for p in self.particles:
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.vy += 12 * dt
            p.life -= dt
        self.particles = [p for p in self.particles if p.life > 0]

    def render(self, scr, h: int, w: int):
        for p in self.particles:
            px, py = int(p.x), int(p.y)
            if 0 <= py < h and 0 <= px < w - 1:
                alpha = p.life / p.max_life
                attr = p.color
                if alpha < 0.3:
                    attr |= curses.A_DIM
                elif alpha > 0.7:
                    attr |= curses.A_BOLD
                try:
                    scr.addch(py, px, glyph_safe_char(p.char), attr)
                except:
                    pass

# ═══════════════════════════════════════════════════════════════════════════════
#                              LIGHTMAP LOADER
# ═══════════════════════════════════════════════════════════════════════════════

POSE_FILES = {
    "coy_cheek": "coy_cheek",
    "face": "face",
    "downward": "downward",
    "squat": "squat",
    "laying_smile": "laying_smile",
    "angled_collapse": "angled_collapse_low_quality",
    "outhouse": "outhouse",
}

@dataclass
class DualLayerLightmap:
    figure: List[str]
    frame: List[str]
    width: int
    height: int

def load_lightmaps() -> Dict[str, DualLayerLightmap]:
    lightmaps = {}
    import os

    paths = [os.path.dirname(__file__), "."]

    for pose_key, pose_name in POSE_FILES.items():
        figure_file = f"{pose_name}_figure.txt"
        frame_file = f"{pose_name}_frame.txt"

        figure_lines = None
        frame_lines = None

        for path in paths:
            fig_path = os.path.join(path, figure_file)
            frame_path = os.path.join(path, frame_file)

            if os.path.exists(fig_path) and os.path.exists(frame_path):
                try:
                    with open(fig_path, 'r', encoding='utf-8') as f:
                        figure_lines = f.read().split('\n')
                    with open(frame_path, 'r', encoding='utf-8') as f:
                        frame_lines = f.read().split('\n')
                    break
                except:
                    pass

        if figure_lines:
            max_h = max(len(figure_lines), len(frame_lines) if frame_lines else 0)
            while len(figure_lines) < max_h:
                figure_lines.append('')
            while frame_lines and len(frame_lines) < max_h:
                frame_lines.append('')

            width = max(max(len(l) for l in figure_lines),
                       max(len(l) for l in frame_lines) if frame_lines else 0)

            lightmaps[pose_key] = DualLayerLightmap(
                figure=figure_lines,
                frame=frame_lines or [],
                width=width,
                height=max_h
            )

    return lightmaps

# ═══════════════════════════════════════════════════════════════════════════════
#                              MAIN INTIMACY SCENE
# ═══════════════════════════════════════════════════════════════════════════════

class IntimacyScene:
    """
    Continuous rhythm intimacy scene

    - Notes fall continuously
    - Hits trigger immediate dialogue
    - Intensity builds toward climax
    - Pose changes with intensity
    - Combo rewards trigger angled_collapse (he pulls her)
    """

    COMBO_REWARD_THRESHOLD = 10  # Combo needed to trigger pull
    COMBO_REWARD_DURATION = 2.5  # Seconds to hold the pull pose

    def __init__(self, scr, encore_mode: bool = False):
        self.scr = scr
        self.encore_mode = encore_mode

        # Systems
        self.rhythm = IntimacyRhythm()
        self.dialogue = IntimacyDialogue()
        self.particles = ParticleSystem()
        self.lightmaps = load_lightmaps()

        # Encore adjustments
        if encore_mode:
            self.rhythm.bpm = 80  # Start faster
            self.rhythm.intensity = 50  # Start warmed up
            self.rhythm.duration = 60.0  # Shorter
            self.COMBO_REWARD_THRESHOLD = 7  # Easier to trigger pulls
            self.dialogue = EncoreDialogue()  # Different dialogue

        # State
        self.play_time = 0.0
        self.current_pose = "squat" if encore_mode else "coy_cheek"
        self.base_pose = self.current_pose  # Pose from intensity
        self.result_text = ""
        self.result_timer = 0.0

        # Combo reward (angled_collapse flash)
        self.combo_reward_active = False
        self.combo_reward_timer = 0.0
        self.last_combo_rewarded = 0  # Track to avoid repeat triggers

        # Figure animation
        self.figure_ox = 0.0
        self.figure_oy = 0.0
        self.figure_vx = 0.0
        self.figure_vy = 0.0

        # Screen shake
        self.shake = 0.0

        # Colors
        self.colors = {}
        self._init_colors()

        curses.curs_set(0)
        scr.nodelay(True)

    def _init_colors(self):
        curses.start_color()

        # Windows compatibility - use_default_colors may not work
        try:
            curses.use_default_colors()
            bg = -1  # Transparent background
        except:
            bg = curses.COLOR_BLACK  # Fallback for Windows

        # Dedicated hit-feedback palette; no collisions with Shader low pairs.
        curses.init_pair(41, curses.COLOR_YELLOW, bg)
        curses.init_pair(42, curses.COLOR_WHITE, bg)
        curses.init_pair(43, curses.COLOR_CYAN, bg)
        curses.init_pair(44, curses.COLOR_GREEN, bg)
        curses.init_pair(45, curses.COLOR_RED, bg)
        curses.init_pair(46, curses.COLOR_CYAN, bg)

        self.colors = {
            'fiend': curses.color_pair(41),
            'bird': curses.color_pair(42),
            'inner': curses.color_pair(43),
            'perfect': curses.color_pair(44),
            'great': curses.color_pair(46),
            'good': curses.color_pair(42),
            'miss': curses.color_pair(45),
        }

    def run(self) -> dict:
        """Run scene, return results dict"""
        last_time = time.time()

        while not self.rhythm.complete:
            current_time = time.time()
            dt = min(current_time - last_time, 0.1)
            last_time = current_time

            if not self._handle_input():
                return {
                    "completed": False,
                    "intensity": self.rhythm.intensity,
                    "max_combo": self.rhythm.max_combo,
                    "quit": True
                }

            self._update(dt)
            self._render()

            time.sleep(0.016)

        return {
            "completed": True,
            "intensity": self.rhythm.intensity,
            "max_combo": self.rhythm.max_combo,
            "success": self.rhythm.intensity >= 80,
            "encore_unlocked": self.rhythm.intensity >= 85 and self.rhythm.max_combo >= 15
        }

    def _handle_input(self) -> bool:
        try:
            key = self.scr.getch()
        except:
            key = -1

        if key == -1:
            return True

        if key in (ord('q'), ord('Q'), 27):
            return False

        if key in LANE_KEYS:
            lane = LANE_KEYS[key]
            quality, note = self.rhythm.hit_lane(lane)

            if quality != 'empty':
                self.result_text = quality.upper()
                self.result_timer = 0.4

                # Trigger dialogue
                self.dialogue.trigger_hit(lane, quality, self.rhythm.intensity)

                # Animation
                self._trigger_animation(lane, quality)

                # Particles
                self._spawn_particles(lane, quality)

                # Check for combo reward (angled_collapse pull)
                self._check_combo_reward()

        return True

    def _check_combo_reward(self):
        """Trigger angled_collapse when combo threshold reached"""
        combo = self.rhythm.combo

        # Only trigger if we crossed a threshold (not already in reward)
        if combo >= self.COMBO_REWARD_THRESHOLD and not self.combo_reward_active:
            # Check if this is a new threshold crossing
            if combo // self.COMBO_REWARD_THRESHOLD > self.last_combo_rewarded // self.COMBO_REWARD_THRESHOLD:
                self.combo_reward_active = True
                self.combo_reward_timer = self.COMBO_REWARD_DURATION
                self.last_combo_rewarded = combo

                # Trigger special dialogue
                if hasattr(self.dialogue, 'trigger_combo_reward'):
                    self.dialogue.trigger_combo_reward()
                else:
                    # Fallback for base IntimacyDialogue
                    self.dialogue.fiend_line = random.choice(["Come here.", "MINE.", "Now."])
                    self.dialogue.fiend_timer = 2.0
                    self.dialogue.bird_line = random.choice(["HAHHH— fieeeenddd—", "Ghhh— when you PULL—", "Yessss~ like THAT—"])
                    self.dialogue.bird_timer = 2.5

                # Big animation
                self.figure_vx = random.choice([-3, 3])
                self.figure_vy = -2
                self.shake = 0.5

    def _trigger_animation(self, lane: Lane, quality: str):
        intensity_mult = 1 + self.rhythm.intensity / 100

        if quality == 'perfect':
            self.shake = 0.3 * intensity_mult
        elif quality == 'great':
            self.shake = 0.2 * intensity_mult

        if lane == Lane.A:
            self.figure_vy = -2 * intensity_mult
        elif lane == Lane.S:
            self.figure_vx = random.choice([-1, 1]) * 1.5 * intensity_mult
        elif lane == Lane.B:
            self.figure_vy = 1.5 * intensity_mult
            self.shake = max(self.shake, 0.2 * intensity_mult)

    def _spawn_particles(self, lane: Lane, quality: str):
        h, w = self.scr.getmaxyx()
        cx = w // 2

        lane_w = 6
        total_w = lane_w * 4
        left = cx - total_w // 2
        lane_x = left + lane.value * lane_w + 2

        hit_y = h - 6

        color = self.colors.get(quality, 0)
        self.particles.spawn_hit(lane_x, hit_y, quality, self.rhythm.intensity, color)

    def _update(self, dt: float):
        self.play_time += dt

        # Rhythm
        events = self.rhythm.update(dt)
        for event, lane in events:
            if event == 'miss':
                self.result_text = "MISS"
                self.result_timer = 0.3
                self.dialogue.trigger_miss(lane, self.rhythm.intensity)

                # Miss particles
                h, w = self.scr.getmaxyx()
                cx = w // 2
                lane_w = 6
                total_w = lane_w * 4
                left = cx - total_w // 2
                lane_x = left + lane.value * lane_w + 2
                self.particles.spawn_miss(lane_x, h - 6, self.colors['miss'])

                # Miss breaks combo reward
                if self.combo_reward_active:
                    self.combo_reward_active = False
                    self.combo_reward_timer = 0

        # Dialogue
        self.dialogue.update(dt)

        # Particles
        self.particles.update(dt)

        # Figure physics
        self.figure_ox += self.figure_vx * dt * 8
        self.figure_oy += self.figure_vy * dt * 8
        self.figure_vx *= 0.92
        self.figure_vy *= 0.92
        self.figure_ox *= 0.95
        self.figure_oy *= 0.95

        # Shake decay
        self.shake = max(0, self.shake - dt * 4)

        # Result timer
        self.result_timer = max(0, self.result_timer - dt)

        # Combo reward timer
        if self.combo_reward_active:
            self.combo_reward_timer -= dt
            if self.combo_reward_timer <= 0:
                self.combo_reward_active = False

        # Pose update
        if self.combo_reward_active:
            # Combo reward = angled_collapse (he pulls her)
            self.current_pose = "angled_collapse"
        elif self.encore_mode:
            # Encore cycles between squat and downward
            intensity = self.rhythm.intensity
            if intensity >= 80:
                self.current_pose = "squat"
            elif intensity >= 60:
                # Oscillate based on time
                cycle = int(self.play_time * 0.5) % 2
                self.current_pose = "squat" if cycle == 0 else "downward"
            else:
                self.current_pose = "downward" if intensity >= 40 else "squat"
        else:
            # Normal intensity-based progression
            self.current_pose = get_pose_for_intensity(self.rhythm.intensity)

        self.base_pose = self.current_pose

    def _render(self):
        self.scr.erase()
        h, w = self.scr.getmaxyx()
        cx = w // 2

        # Shake offset
        shake_x = int(random.uniform(-2, 2) * self.shake) if self.shake > 0 else 0
        shake_y = int(random.uniform(-1, 1) * self.shake) if self.shake > 0 else 0

        # Layout
        highway_h = 8
        dialogue_h = 6
        status_h = 2
        lightmap_h = h - highway_h - dialogue_h - status_h - 2

        lightmap_top = 1
        lightmap_bottom = lightmap_top + lightmap_h
        dialogue_top = lightmap_bottom + 1
        highway_top = h - highway_h - status_h
        status_y = h - 1

        # Render
        ox, oy = int(self.figure_ox) + shake_x, int(self.figure_oy) + shake_y
        self._render_lightmap(lightmap_top, lightmap_bottom, w, cx, ox, oy)
        self._render_dialogue(dialogue_top, w, cx)
        self._render_highway(highway_top, h - status_h - 1, w, cx)
        self._render_status(status_y, w, cx)
        self._render_intensity_bar(0, w, cx)

        # Particles
        self.particles.render(self.scr, h, w)

        self.scr.refresh()

    def _render_lightmap(self, top: int, bottom: int, w: int, cx: int, ox: int, oy: int):
        lightmap = self.lightmaps.get(self.current_pose)
        if not lightmap:
            return

        available_h = bottom - top

        if lightmap.height > available_h:
            step = lightmap.height / available_h
            frame_lines = [lightmap.frame[int(i * step)] for i in range(available_h)]
            figure_lines = [lightmap.figure[int(i * step)] for i in range(available_h)]
        else:
            frame_lines = lightmap.frame[:available_h]
            figure_lines = lightmap.figure[:available_h]

        start_y = top
        if len(frame_lines) < available_h:
            start_y = top + (available_h - len(frame_lines)) // 2

        # Frame (static)
        for i, line in enumerate(frame_lines):
            if not line:
                continue
            x = cx - lightmap.width // 2
            y = start_y + i
            if top <= y < bottom and x < w:
                self._safe_addstr(y, max(0, x), line[:w-1], curses.A_DIM)

        # Figure (animated)
        for i, line in enumerate(figure_lines):
            if not line or not line.strip():
                continue
            x = cx - lightmap.width // 2 + ox
            y = start_y + i + oy
            if top <= y < bottom:
                for j, char in enumerate(line):
                    if char != ' ':
                        px = x + j
                        if 0 <= px < w - 1:
                            try:
                                self.scr.addch(y, px, glyph_safe_char(char))
                            except:
                                pass

    def _render_dialogue(self, top: int, w: int, cx: int):
        y = top

        # Fiend (left)
        if self.dialogue.fiend_timer > 0:
            line = f'"{self.dialogue.fiend_line}"'
            x = cx - len(line) - 5
            self._safe_addstr(y, max(2, x), line, self.colors['fiend'] | curses.A_BOLD)

        # Birdsong (right)
        if self.dialogue.bird_timer > 0:
            line = f'"{self.dialogue.bird_line}"'
            x = cx + 5
            self._safe_addstr(y, min(x, w - len(line) - 2), line, self.colors['bird'])

        # Inner (centered below)
        if self.dialogue.inner_timer > 0:
            line = f'*{self.dialogue.inner_line}*'
            x = cx - len(line) // 2
            self._safe_addstr(y + 2, max(2, x), line, self.colors['inner'] | curses.A_DIM)

    def _render_highway(self, top: int, bottom: int, w: int, cx: int):
        lane_w = 6
        total_w = lane_w * 4
        left = cx - total_w // 2
        hit_y = bottom

        # Lane labels
        labels = "  A     S     B    ···"
        self._safe_addstr(hit_y, left, labels, curses.A_BOLD)

        # Hit line
        self._safe_addstr(hit_y - 1, left, "━" * total_w, curses.A_BOLD)

        # Notes
        fall_range = hit_y - 1 - top
        for note in self.rhythm.notes:
            if note.hit or note.missed:
                continue

            lx = left + note.lane.value * lane_w + 2
            ny = top + int(note.y_pos * fall_range)

            if top <= ny < hit_y - 1:
                if getattr(note, 'decoy', False):
                    char, attr = '×', curses.A_DIM | self.colors['miss']
                elif note.y_pos > 0.85:
                    char, attr = '◆', curses.A_BOLD | self.colors['perfect']
                elif note.y_pos > 0.65:
                    char, attr = '●', curses.A_BOLD
                else:
                    char, attr = '○', curses.A_DIM
                self._safe_addstr(ny, lx, char, attr)

        # Result
        if self.result_timer > 0:
            attr = curses.A_BOLD
            if 'PERFECT' in self.result_text:
                attr |= self.colors['perfect']
            elif 'GREAT' in self.result_text:
                attr |= self.colors['great']
            elif 'MISS' in self.result_text:
                attr |= self.colors['miss']
            self._safe_addstr(hit_y - 1, left + total_w + 2, self.result_text, attr)

    def _render_intensity_bar(self, y: int, w: int, cx: int):
        # Intensity bar at top
        bar_w = 40
        filled = int(self.rhythm.intensity / 100 * bar_w)

        # Color based on intensity
        if self.rhythm.intensity >= 80:
            attr = self.colors['perfect'] | curses.A_BOLD
        elif self.rhythm.intensity >= 50:
            attr = self.colors['great']
        else:
            attr = curses.A_DIM

        bar = "█" * filled + "░" * (bar_w - filled)
        tier = get_intensity_tier(self.rhythm.intensity)
        label = f" {tier.upper()} "

        self._safe_addstr(y, cx - bar_w // 2, bar, attr)
        self._safe_addstr(y, cx - len(label) // 2, label, curses.A_BOLD | curses.A_REVERSE)

    def _render_status(self, y: int, w: int, cx: int):
        # Time
        mins, secs = divmod(int(self.play_time), 60)
        time_str = f"{mins}:{secs:02d}"
        self._safe_addstr(y, 2, time_str, curses.A_DIM)

        # Combo
        if self.rhythm.combo >= 5:
            combo_str = f"{self.rhythm.combo}x"
            attr = curses.A_BOLD
            if self.rhythm.combo >= 20:
                attr |= self.colors['perfect']
            elif self.rhythm.combo >= 10:
                attr |= self.colors['great']
            self._safe_addstr(y, w - len(combo_str) - 2, combo_str, attr)

        # Controls
        controls = "[A] [S] [B] [SPACE]"
        self._safe_addstr(y, cx - len(controls) // 2, controls, curses.A_DIM)

    def _safe_addstr(self, y: int, x: int, text: str, attr: int = 0):
        text = glyph_safe_text(text)
        h, w = self.scr.getmaxyx()
        if 0 <= y < h and x < w:
            if x < 0:
                text = text[-x:]
                x = 0
            try:
                self.scr.addstr(y, x, text[:w - x - 1], attr)
            except:
                pass


# ═══════════════════════════════════════════════════════════════════════════════
#                              SCREENSAVER MODE
# ═══════════════════════════════════════════════════════════════════════════════

class ScreensaverScene(IntimacyScene):
    """
    Auto-play screensaver mode - no input required, LOOPS forever

    Modes:
    - gentle: Slow, tender, occasional soft misses
    - steady: Default pacing, perfect hits
    - rough:  Faster, aggressive, relentless
    - feral:  Outhouse mode - dirty flower dialogue + bathroom animations
    """

    MODE_SETTINGS = {
        "gentle": {
            "bpm_start": 50,
            "bpm_end": 70,
            "hit_variance": 0.12,
            "miss_chance": 0.08,
            "dialogue_hold": 1.5,
            "combo_threshold": 15,
            "pose_linger": 2.0,
        },
        "steady": {
            "bpm_start": 65,
            "bpm_end": 95,
            "hit_variance": 0.05,
            "miss_chance": 0.02,
            "dialogue_hold": 1.2,
            "combo_threshold": 10,
            "pose_linger": 1.0,
        },
        "rough": {
            "bpm_start": 85,
            "bpm_end": 130,
            "hit_variance": 0.03,
            "miss_chance": 0.0,
            "dialogue_hold": 1.0,
            "combo_threshold": 7,
            "pose_linger": 0.5,
        },
        "feral": {
            "bpm_start": 60,
            "bpm_end": 110,
            "hit_variance": 0.08,
            "miss_chance": 0.05,
            "dialogue_hold": 1.4,
            "combo_threshold": 8,
            "pose_linger": 1.2,
            "use_outhouse_pose": True,
        },
    }

    FERAL_POSES = {
        (0, 30):   "outhouse",
        (30, 50):  "coy_cheek",
        (50, 70):  "squat",
        (70, 85):  "downward",
        (85, 101): "squat",
    }

    # Outhouse animation events
    OUTHOUSE_EVENTS = {
        "shiver": {
            "duration": 0.8,
            "shake_x": 0.3,
            "shake_y": 0.1,
            "dialogue_bird": [
                "Ghhh— cold seat—",
                "Oy~ brrr—",
                "Hahhh— shivers—",
                "Mmhh— goosebumps—",
            ],
        },
        "plop": {
            "duration": 0.4,
            "jump_y": 1.5,
            "dialogue_bird": [
                "...oh.",
                "Ghhh—",
                "Hahhh— there it goes—",
                "Mmhh— relief—",
            ],
            "dialogue_inner": [
                "Plop.",
                "Finally.",
                "Oh thank god.",
            ],
        },
        "stream": {
            "duration": 2.0,
            "wiggle_x": 0.15,
            "dialogue_bird": [
                "Hahhh— okay— mmhh—",
                "Ghhh— needed this—",
                "Oy~ sweet relief—",
            ],
            "dialogue_inner": [
                "The relief is indescribable.",
                "Why did I wait so long.",
            ],
        },
        "strain": {
            "duration": 1.2,
            "shake_y": 0.2,
            "dialogue_bird": [
                "Ghhh— come ON—",
                "Hahhh— just— mmhh—",
                "Oy~ stubborn—",
                "Nnh— almost—",
            ],
            "dialogue_inner": [
                "Push.",
                "Come on body, cooperate.",
            ],
        },
        "sigh": {
            "duration": 1.5,
            "settle_y": -0.5,
            "dialogue_bird": [
                "Hahhh~~~",
                "...mmhh...",
                "...okay...",
                "...yessss~...",
            ],
            "dialogue_inner": [
                "Done. Finally done.",
                "Sweet, sweet relief.",
            ],
        },
        "wipe": {
            "duration": 0.6,
            "wiggle_x": 0.3,
            "dialogue_bird": [
                "Okay— mmhh— okay—",
                "Ghhh— almost done—",
                "Hahhh— cleanup—",
            ],
        },
    }

    def __init__(self, scr, mode: str = "steady"):
        self.mode = mode
        self.settings = self.MODE_SETTINGS.get(mode, self.MODE_SETTINGS["steady"])

        super().__init__(scr, encore_mode=False)

        if mode == "feral":
            self.dialogue = FeralDialogue()
            self.current_pose = "outhouse"  # Start on the toilet
        elif mode == "rough":
            self.dialogue = EncoreDialogue()

        self.rhythm.bpm = self.settings["bpm_start"]
        self.rhythm.duration = 120.0
        self.COMBO_REWARD_THRESHOLD = self.settings["combo_threshold"]

        self.auto_hit_queue: List[Tuple[float, Lane]] = []
        self.last_auto_hit = 0.0
        self.breath_phase = 0.0
        self.breath_speed = 0.3
        self.pose_linger_timer = 0.0
        self.lingering_pose = None

        # Outhouse animation state (feral mode)
        self.outhouse_event = None
        self.outhouse_event_timer = 0.0
        self.outhouse_event_data = {}
        self.next_outhouse_event = random.uniform(2.0, 5.0)  # First event comes sooner
        self.outhouse_sequence = ["shiver", "strain", "plop", "sigh", "stream", "wipe"]
        self.outhouse_seq_index = 0

        # Loop counter
        self.loop_count = 0

    def _reset_for_loop(self):
        """Reset state for next loop iteration"""
        self.rhythm = IntimacyRhythm()
        self.rhythm.bpm = self.settings["bpm_start"]
        self.rhythm.duration = 120.0
        self.play_time = 0.0
        self.loop_count += 1

        # Reset outhouse sequence
        self.outhouse_seq_index = 0
        self.next_outhouse_event = random.uniform(3.0, 8.0)

    def run(self) -> dict:
        """Run screensaver in LOOP - only exits on Q"""
        last_time = time.time()

        while True:  # Loop forever
            current_time = time.time()
            dt = min(current_time - last_time, 0.1)
            last_time = current_time

            try:
                key = self.scr.getch()
                if key in (ord('q'), ord('Q'), 27):
                    return {"quit": True, "mode": self.mode, "loops": self.loop_count}
            except:
                pass

            self._auto_play(dt)
            self._update(dt)
            self._update_screensaver(dt)

            # Outhouse events (feral mode)
            if self.mode == "feral":
                self._update_outhouse(dt)

            self._render()

            # Check for loop reset
            if self.rhythm.complete:
                self._reset_for_loop()

            time.sleep(0.016)

        return {
            "completed": True,
            "mode": self.mode,
            "intensity": self.rhythm.intensity,
            "max_combo": self.rhythm.max_combo,
            "loops": self.loop_count,
        }

    def _update_outhouse(self, dt: float):
        """Handle outhouse-specific animations"""
        # Currently in an event?
        if self.outhouse_event:
            self.outhouse_event_timer -= dt
            data = self.outhouse_event_data

            # Apply event-specific animations
            if "shake_x" in data:
                self.figure_vx += random.uniform(-data["shake_x"], data["shake_x"]) * 10 * dt
            if "shake_y" in data:
                self.figure_vy += random.uniform(-data["shake_y"], data["shake_y"]) * 10 * dt
            if "wiggle_x" in data:
                wiggle = math.sin(self.play_time * 15) * data["wiggle_x"]
                self.figure_ox += wiggle * dt * 5
            if "jump_y" in data and self.outhouse_event_timer > data["duration"] * 0.7:
                self.figure_vy = -data["jump_y"]
            if "settle_y" in data:
                self.figure_vy += data["settle_y"] * dt

            # Event complete
            if self.outhouse_event_timer <= 0:
                self.outhouse_event = None
                self.next_outhouse_event = random.uniform(4.0, 10.0)
        else:
            # Time for next event?
            self.next_outhouse_event -= dt
            if self.next_outhouse_event <= 0 and self.current_pose == "outhouse":
                self._trigger_outhouse_event()

    def _trigger_outhouse_event(self):
        """Trigger the next outhouse animation event"""
        # Get next event in sequence
        event_name = self.outhouse_sequence[self.outhouse_seq_index % len(self.outhouse_sequence)]
        self.outhouse_seq_index += 1

        event = self.OUTHOUSE_EVENTS.get(event_name)
        if not event:
            return

        self.outhouse_event = event_name
        self.outhouse_event_timer = event["duration"]
        self.outhouse_event_data = event

        # Trigger dialogue
        if "dialogue_bird" in event:
            self.dialogue.bird_line = _cascade_pick(event["dialogue_bird"], "BIRDSONG", intensity=getattr(self.rhythm,'intensity',0.0), quality='event')
            self.dialogue.bird_timer = event["duration"] + 0.5

        if "dialogue_inner" in event and random.random() < 0.6:
            self.dialogue.inner_line = _cascade_pick(event["dialogue_inner"], "INNER", intensity=getattr(self.rhythm,'intensity',0.0), quality='event')
            self.dialogue.inner_timer = event["duration"] + 1.0

        # Particles for plop
        if event_name == "plop":
            h, w = self.scr.getmaxyx()
            cx = w // 2
            # Spawn "splash" particles below figure
            for _ in range(8):
                self.particles.particles.append(Particle(
                    x=float(cx + random.randint(-5, 5)),
                    y=float(h // 2 + 10),
                    vx=random.uniform(-3, 3),
                    vy=random.uniform(-5, -2),
                    char=random.choice(['·', '°', '~', '○']),
                    life=random.uniform(0.4, 0.8),
                    max_life=0.8,
                    color=0
                ))

    def _auto_play(self, dt: float):
        """Auto-generate perfect (or near-perfect) hits"""
        for note in self.rhythm.notes:
            if note.hit or note.missed:
                continue

            if 0.92 <= note.y_pos <= 1.08:
                variance = random.uniform(-self.settings["hit_variance"],
                                         self.settings["hit_variance"])
                target_y = 1.0 + variance

                if abs(note.y_pos - target_y) < 0.05:
                    if random.random() < self.settings["miss_chance"]:
                        continue

                    quality, _ = self.rhythm.hit_lane(note.lane)

                    if quality != 'empty':
                        self.result_text = quality.upper()
                        self.result_timer = 0.4 * self.settings["dialogue_hold"]

                        self.dialogue.trigger_hit(note.lane, quality, self.rhythm.intensity)
                        self.dialogue.fiend_timer *= self.settings["dialogue_hold"]
                        self.dialogue.bird_timer *= self.settings["dialogue_hold"]
                        self.dialogue.inner_timer *= self.settings["dialogue_hold"]

                        self._trigger_animation(note.lane, quality)
                        self._spawn_particles(note.lane, quality)
                        self._check_combo_reward()

    def _update_screensaver(self, dt: float):
        """Extra screensaver-specific updates"""
        self.breath_phase += dt * self.breath_speed
        breath_offset = math.sin(self.breath_phase * math.pi * 2) * 0.3
        self.figure_oy += breath_offset * dt * 2

        progress = self.rhythm.intensity / 100
        target_bpm = self.settings["bpm_start"] + progress * (
            self.settings["bpm_end"] - self.settings["bpm_start"]
        )
        self.rhythm.bpm = int(target_bpm)
        self.rhythm.beat_duration = 60.0 / self.rhythm.bpm

        if self.pose_linger_timer > 0:
            self.pose_linger_timer -= dt
            if self.lingering_pose:
                self.current_pose = self.lingering_pose
        else:
            self.lingering_pose = None

    def _update(self, dt: float):
        """Override to use feral poses if needed"""
        super()._update(dt)

        if self.mode == "feral" and self.settings.get("use_outhouse_pose"):
            if not self.combo_reward_active and not self.lingering_pose:
                self.current_pose = self._get_feral_pose(self.rhythm.intensity)

        if not self.lingering_pose:
            if self.rhythm.intensity >= 85 and self.current_pose in ["squat", "downward"]:
                self.lingering_pose = self.current_pose
                self.pose_linger_timer = self.settings["pose_linger"]

    def _get_feral_pose(self, intensity: float) -> str:
        """Get pose for feral mode"""
        for (lo, hi), pose in self.FERAL_POSES.items():
            if lo <= intensity < hi:
                return pose
        return "squat"

    def _render_status(self, y: int, w: int, cx: int):
        """Override to show screensaver mode + loop count"""
        mins, secs = divmod(int(self.play_time), 60)
        time_str = f"{mins}:{secs:02d}"
        self._safe_addstr(y, 2, time_str, curses.A_DIM)

        # Mode + loop count
        if self.loop_count > 0:
            mode_str = f"~ {self.mode.upper()} (loop {self.loop_count + 1}) ~"
        else:
            mode_str = f"~ {self.mode.upper()} ~"
        self._safe_addstr(y, cx - len(mode_str) // 2, mode_str,
                         curses.A_BOLD | self.colors.get('inner', 0))

        # Outhouse event indicator (feral mode)
        if self.mode == "feral" and self.outhouse_event:
            event_str = f"[{self.outhouse_event.upper()}]"
            self._safe_addstr(y, w - len(event_str) - 12, event_str,
                             curses.A_DIM | self.colors.get('bird', 0))

        if self.rhythm.combo >= 5:
            combo_str = f"{self.rhythm.combo}x"
            attr = curses.A_BOLD
            if self.rhythm.combo >= 20:
                attr |= self.colors['perfect']
            elif self.rhythm.combo >= 10:
                attr |= self.colors['great']
            self._safe_addstr(y, w - len(combo_str) - 2, combo_str, attr)

    def _render_highway(self, top: int, bottom: int, w: int, cx: int):
        """Override to show mode indicator"""
        super()._render_highway(top, bottom, w, cx)

        hit_y = bottom
        lane_w = 6
        total_w = lane_w * 4
        left = cx - total_w // 2

        if self.mode == "feral":
            label = "   ~ DIRTY FLOWER ~   "
        else:
            label = "      [Q to exit]     "
        self._safe_addstr(hit_y, left, label, curses.A_DIM)

# ═══════════════════════════════════════════════════════════════════════════════
#                              ENCORE TRANSITION
# ═══════════════════════════════════════════════════════════════════════════════

ENCORE_INTRO_LINES = [
    ("BIRDSONG", "...fieeeenddd?"),
    ("FIEND", "Mm?"),
    ("BIRDSONG", "...again?"),
    ("FIEND", "Again."),
    ("BIRDSONG", "Oy~ I literally JUST— hahhh— okay. OKAY. Fine."),
    ("FIEND", "Good girl."),
]

ENCORE_OUTRO_LINES = [
    ("BIRDSONG", "...hahhh..."),
    ("BIRDSONG", "...okay NOW we're done."),
    ("FIEND", "...for now."),
    ("BIRDSONG", "Fieeeenddd~ I'm going to DIE."),
    ("FIEND", "Mm. But what a way to go."),
    ("BIRDSONG", "...yessss~... yeah. Hahhh. Yeah."),
]

def show_transition(scr, lines: List[tuple], title: str = ""):
    """Show dialogue transition between scenes"""
    h, w = scr.getmaxyx()
    cx = w // 2

    # Windows compatible colors
    try:
        curses.use_default_colors()
        bg = -1
    except:
        bg = curses.COLOR_BLACK

    curses.init_pair(1, curses.COLOR_YELLOW, bg)
    curses.init_pair(2, curses.COLOR_WHITE, bg)

    for speaker, text in lines:
        scr.erase()

        if title:
            scr.addstr(2, cx - len(title) // 2, title, curses.A_BOLD | curses.A_REVERSE)

        color = curses.color_pair(1) if speaker == "FIEND" else curses.color_pair(2)
        line = f'{speaker}: "{text}"'
        scr.addstr(h // 2, cx - len(line) // 2, line, color)

        scr.addstr(h - 2, cx - 10, "[SPACE to continue]", curses.A_DIM)
        scr.refresh()

        # Wait for space
        scr.nodelay(False)
        while True:
            key = scr.getch()
            if key in (ord(' '), ord('\n'), 10, 13):
                break
            if key in (ord('q'), ord('Q'), 27):
                return False
        scr.nodelay(True)

    return True

# ═══════════════════════════════════════════════════════════════════════════════
#                              ENTRY POINTS
# ═══════════════════════════════════════════════════════════════════════════════

def run_intimacy(scr, encore_mode: bool = False) -> dict:
    """Run the intimacy scene, return results dict"""
    scene = IntimacyScene(scr, encore_mode=encore_mode)
    return scene.run()

def run_full_intimacy(scr) -> dict:
    """Run intimacy with automatic encore if unlocked"""
    # Run main intimacy
    result = run_intimacy(scr, encore_mode=False)

    if result.get("quit"):
        return result

    # Check for encore unlock
    if result.get("encore_unlocked"):
        # Show transition
        if not show_transition(scr, ENCORE_INTRO_LINES, "✦ ENCORE UNLOCKED ✦"):
            return result

        # Run encore
        encore_result = run_intimacy(scr, encore_mode=True)

        # Show outro
        if encore_result.get("completed"):
            show_transition(scr, ENCORE_OUTRO_LINES, "")

        # Merge results
        result["encore_completed"] = encore_result.get("completed", False)
        result["encore_intensity"] = encore_result.get("intensity", 0)
        result["total_max_combo"] = max(result.get("max_combo", 0), encore_result.get("max_combo", 0))

    return result

def run_screensaver(scr, mode: str = "steady") -> dict:
    """Run screensaver mode"""
    scene = ScreensaverScene(scr, mode=mode)
    return scene.run()

def main(scr):
    """Standalone test with full encore support"""
    result = run_full_intimacy(scr)

    # Show result
    scr.clear()
    h, w = scr.getmaxyx()
    cx = w // 2

    # Windows compatible colors
    try:
        curses.use_default_colors()
        bg = -1
    except:
        bg = curses.COLOR_BLACK

    curses.init_pair(4, curses.COLOR_GREEN, bg)
    curses.init_pair(5, curses.COLOR_CYAN, bg)

    if result.get("encore_completed"):
        msg = "** ENCORE COMPLETE **"
        scr.addstr(h // 2 - 2, cx - len(msg) // 2, msg, curses.A_BOLD | curses.color_pair(5))
    elif result.get("success"):
        msg = "* COMPLETE *"
        scr.addstr(h // 2 - 2, cx - len(msg) // 2, msg, curses.A_BOLD | curses.color_pair(4))
    else:
        msg = "Scene ended"
        scr.addstr(h // 2 - 2, cx - len(msg) // 2, msg)

    # Stats
    stats = f"Intensity: {result.get('intensity', 0):.0f}%  |  Max Combo: {result.get('max_combo', 0)}"
    scr.addstr(h // 2, cx - len(stats) // 2, stats)

    if result.get("encore_unlocked") and not result.get("encore_completed"):
        unlock_msg = "(Encore was unlocked!)"
        scr.addstr(h // 2 + 1, cx - len(unlock_msg) // 2, unlock_msg, curses.color_pair(5))

    scr.addstr(h // 2 + 3, cx - 10, "Press any key...")
    scr.refresh()
    scr.nodelay(False)
    scr.getch()

def main_screensaver(scr, mode: str):
    """Screensaver main"""
    result = run_screensaver(scr, mode)

    scr.clear()
    h, w = scr.getmaxyx()
    cx = w // 2

    if result.get("completed"):
        msg = f"~ {mode.upper()} COMPLETE ~"
    else:
        msg = "Screensaver ended"

    scr.addstr(h // 2, cx - len(msg) // 2, msg, curses.A_BOLD)
    scr.addstr(h // 2 + 2, cx - 10, "Press any key...")
    scr.refresh()
    scr.nodelay(False)
    scr.getch()

def run():
    curses.wrapper(main)

def run_screensaver_mode(mode: str = "steady"):
    curses.wrapper(lambda scr: main_screensaver(scr, mode))

if __name__ == "__main__":
    run()
