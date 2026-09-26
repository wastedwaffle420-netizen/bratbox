"""RhythmDirector v0.1 (LOCKKEY) — Script-like Radio Play

This is a lightweight "radio play" scheduler that can run during the rhythm
segment (intimacy mode). It generates voice events on a rhythmic grid and routes
them to the offline-capable voice engine.

Design constraints:
  - Zero hard dependencies beyond the existing project modules.
  - Never crash the game loop: all exceptions are caught and the director can
    soft-disable itself.
  - Conservatively avoids ruining serious beats (uses mood + intensity guards).
  - Uses the voice engine's beat gate + fill-grid + beat motifs for musicality.

v0.1 additions:
  - Pseudo-conversation chaining (call/response) across main slots.
  - Rhythm-event steering: hit/perfect/miss/break influences intent selection per beat.
  - Safety clamps: on overwhelm or miss streaks, density collapses to grounded/soft roles.

Environment toggles (optional):
  - LOCKKEY_RHYTHM_DIRECTOR=1/0      enable/disable (default 1)
  - LOCKKEY_RADIO_PLAY_ONLY=1/0      suppress authored subtitles/lines (default 1)
  - LOCKKEY_RHYTHM_MAIN_SLOTS        CSV slots for main lines (default "0,4")
  - LOCKKEY_RHYTHM_LOG=1/0           append jsonl log (default 1)
"""

from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

def _fiendish_asset_root() -> Path:
    try:
        env_root = str(os.environ.get("FIENDISH_RELEASE_DIR", "") or "").strip()
        if env_root:
            return Path(env_root).expanduser().resolve()
    except Exception:
        pass
    return Path(__file__).resolve().parent

def _get_noise_0_100() -> int:
    """Single-dial 'Noise' control (0–100). Default is 35 (balanced shipping).

    This does NOT hard-lock routes/transcripts; it biases density/novelty/motif usage
    while the beat grid + arcs keep coherence."""
    try:
        n = int(float(os.environ.get("LOCKKEY_NOISE", "35") or "35"))
    except Exception:
        n = 35
    return max(0, min(100, n))


def _noise_density_multiplier() -> float:
    """Maps Noise->density multiplier with 1.0 at Noise=35 (preserves existing tone)."""
    n = _get_noise_0_100()
    # +/-0.5 across the full range; calibrated so 35 keeps current feel.
    return _clamp(1.0 + (n - 35) * 0.005, 0.70, 1.35)



def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _parse_slot_csv(s: str) -> set[int]:
    out: set[int] = set()
    for part in (s or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.add(int(float(part)))
        except Exception:
            continue
    return out


@dataclass
class PerfSnapshot:
    intensity01: float
    combo: int
    max_combo: int
    hits: int
    misses: int
    overwhelm: float
    cognitive_load: float
    attune_trust: float

    # Derived per-beat event (computed in director)
    event: str = "NONE"  # NONE/HIT/PERFECT/MISS/BREAK
    hit_streak: int = 0
    miss_streak: int = 0
    perfect_streak: int = 0

    @property
    def combo01(self) -> float:
        return _clamp(float(self.combo) / float(max(1, self.max_combo)), 0.0, 1.0)

    @property
    def accuracy01(self) -> float:
        tot = int(self.hits) + int(self.misses)
        if tot <= 0:
            return 0.75
        return _clamp(float(self.hits) / float(tot), 0.0, 1.0)

    @property
    def calm01(self) -> float:
        # overwhelm rises on errors; treat it as "stress"
        return _clamp(1.0 - (float(self.overwhelm) / 1.6), 0.0, 1.0)

    @property
    def stressed(self) -> bool:
        # Conservative: either overwhelm is high or cognitive load spikes.
        return (float(self.overwhelm) >= 1.1) or (float(self.cognitive_load) >= 1.0)


class RhythmDirector:
    def __init__(self, *, log_path: Optional[Path] = None):
        self.enabled = (os.environ.get("LOCKKEY_RHYTHM_DIRECTOR", "1") or "1").strip().lower() in (
            "1", "true", "yes", "on"
        )

        self._main_slots = _parse_slot_csv(os.environ.get("LOCKKEY_RHYTHM_MAIN_SLOTS", "0,4")) or {0, 4}
        # Optional: probability of emitting a main line at a CALL/RESP slot (keeps rhythm-first feel).
        try:
            self._main_prob = _clamp(float(os.environ.get("LOCKKEY_RHYTHM_MAIN_PROB", "1.0") or "1.0"), 0.0, 1.0)
        except Exception:
            self._main_prob = 1.0

        self._last_slot: Optional[int] = None
        self._last_bar: Optional[int] = None
        self._main_toggle = 0
        self._next_allowed: Dict[str, float] = {}

        # Rhythm event tracking (for hit/miss/perfect steering)
        self._last_hits = 0
        self._last_misses = 0
        self._last_combo = 0
        self._last_surge_streak = 0
        self._hit_streak = 0
        self._miss_streak = 0
        self._perfect_streak = 0
        self._last_event = "NONE"

        # Script-like call/response chaining
        self._pending_response: Optional[Dict[str, Any]] = None
        self._last_caller: Optional[str] = None
        # Coherence: topic anchors (light semantic spine), plus last-heard transcripts.
        # Anchors persist 2–6 bars and act like a scent trail (not a script).
        self._anchors: Dict[str, int] = {}  # anchor->remaining bars
        self._last_transcript: Dict[str, str] = {"BIRDSONG": "", "FIEND": ""}
        self._last_main_intent: Dict[str, str] = {"BIRDSONG": "", "FIEND": ""}
        self._anchor_words: Dict[str, list[str]] = {
            "want_need": ["need","want","please","more","closer","again","mine","hungry","miss","touch"],
            "tease_deny": ["tease","silly","baka","rude","no","stop","cant","dont","maybe","hmph"],
            "protect_steady": ["got","you","here","safe","steady","breathe","okay","hold","care","gentle"],
            "praise_disbelief": ["good","wow","believe","really","seriously","amazing","proud","nice"],
            "push_backtrack": ["push","come","say","admit","again","back","wait","fine","ugh","whatever"],
        }
        self._bar_plan: Dict[int, str] = {}  # slot->"CALL"/"RESP" (rebuilt each bar)
        self._micro_plan: Dict[int, list[dict]] = {}  # slot->[{role,speaker,intent,p}]
        self._bar_ctx: Dict[str, Any] = {}  # caller/responder/intents/kind
        self._seen_bar = -1
        # Multi-bar arcs (2-4 bars): commit to a mini-scene across bars.
        # This makes call/response feel like a real conversation rather than per-bar resets.
        self._arc: Dict[str, Any] = {}  # kind,len,pos,caller,responder
        self._arc_active = False
        self._arc_start_bar = 0
        self._arc_len = 0
        self._arc_pos = 0

        # Faster line preference (default on): add extra main slots when the player is clean.
        self._fast_lines = (os.environ.get("LOCKKEY_RHYTHM_FAST_LINES", "1") or "1").strip().lower() in ("1","true","yes","on")


        # Spicy devotion loop (Bird: neediness/deniability performance; Fiend: warm guardian devotion).
        # Enabled when Noise is in the "spicy" band and the player is stable; never in serious/recover.
        self._spicy_enabled = (os.environ.get("LOCKKEY_SPICY_MODE", "1") or "1").strip().lower() in ("1","true","yes","on")
        self._spicy_phase = 0
        self._deniability = 100.0  # Bird plausible deniability (drops over time in spicy mode)
        self._neediness = 0.0      # Bird "pulling strings" lever (rises with bait; falls with care)
        self._spicy_cooldown_until_bar = -999


        # ── GLINT state (Fiend glow hover + rare sacred spikes)
        self._glint_enabled = (os.environ.get("LOCKKEY_GLINT", "1") or "1").strip().lower() in ("1","true","yes","on")
        self._glint_state = "off"     # "off" | "hover" | "spike"
        self._glint_spike_until_bar = -1
        self._glint_next_spike_bar = 0
        self._glint_bar_last_sub = -999
        self._glint_pending_react: Optional[dict] = None
        self._glint_last_by_family: Dict[str, int] = {}
        self._glint_assets_by_family: Dict[str, list[dict]] = {}
        self._glint_policy: Dict[str, Any] = {}
        try:
            self._load_glint_assets()
        except Exception:
            self._glint_assets_by_family = {}
            self._glint_policy = {}

        # Canonical Fiend smoothing (default ON): makes Fiend pick clearer, more "meant" lines.
        self._fiend_smooth = (os.environ.get("LOCKKEY_FIEND_SMOOTH", "1") or "1").strip().lower() in ("1","true","yes","on")

        # Cascade guard (default ON): limits per-slot/per-bar extras to prevent "bad cascading".
        self._cascade_guard = (os.environ.get("LOCKKEY_CASCADE_GUARD", "1") or "1").strip().lower() in ("1","true","yes","on")
        # Posture knobs (can be loaded from director_preset.json via run.py):
        #   LOCKKEY_FIEND_GUARDIAN_BIAS   0..100 (how strongly Fiend stays in guardian-lover mode)
        #   LOCKKEY_CASCADE_TIGHTNESS     0..100 (higher = cleaner, fewer stacked extras)
        #   LOCKKEY_ARC_BARS              int (override arc commitment length; 2..8 recommended)
        #   LOCKKEY_UNDERLAY_DENSITY      float (multiplier for underlay/murmur probability)
        self._guardian_bias = 80
        try:
            self._guardian_bias = max(0, min(100, int(float(os.environ.get('LOCKKEY_FIEND_GUARDIAN_BIAS', '80') or '80'))))
        except Exception:
            self._guardian_bias = 80
        self._cascade_tightness = 70
        try:
            self._cascade_tightness = max(0, min(100, int(float(os.environ.get('LOCKKEY_CASCADE_TIGHTNESS', '70') or '70'))))
        except Exception:
            self._cascade_tightness = 70
        self._arc_bars_override = None
        try:
            if os.environ.get('LOCKKEY_ARC_BARS') is not None:
                self._arc_bars_override = int(float(os.environ.get('LOCKKEY_ARC_BARS') or '0'))
        except Exception:
            self._arc_bars_override = None
        self._underlay_mult = 1.0
        try:
            self._underlay_mult = float(os.environ.get('LOCKKEY_UNDERLAY_DENSITY', '1.0') or '1.0')
        except Exception:
            self._underlay_mult = 1.0
        self._underlay_mult = _clamp(self._underlay_mult, 0.50, 2.00)
        self._bar_extra = {"murmur": 0, "interrupt": 0, "suffix": 0, "gesture": 0, "prefix": 0, "glint_sub": 0}
        self._bar_extra_bar = -1
        self._last_interrupt_bar = -999
        self._last_underlay_bar_by_sp = {}
        self._rhythm_voice_pending: Optional[Dict[str, Any]] = None
        self._rhythm_voice_active_until = 0.0
        self._rhythm_voice_cooldown_until = 0.0
        self._last_voice_combo_threshold = 0
        self._last_lightmap_pose_seen = ""
        self._pose_shift_until = 0.0
        self._lightmap_reward_until = 0.0
        try:
            self._rhythm_voice_global_cd = _clamp(float(os.environ.get("LOCKKEY_RHYTHM_VOICE_COOLDOWN_S", "4.5") or "4.5"), 3.5, 8.0)
        except Exception:
            self._rhythm_voice_global_cd = 4.5
        try:
            self._rhythm_voice_micro_cd = _clamp(float(os.environ.get("LOCKKEY_RHYTHM_VOICE_MICRO_COOLDOWN_S", "6.0") or "6.0"), 4.0, 10.0)
        except Exception:
            self._rhythm_voice_micro_cd = 6.0
        try:
            self._rhythm_voice_recent_gap = _clamp(float(os.environ.get("LOCKKEY_RHYTHM_VOICE_RECENT_GAP_S", "0.65") or "0.65"), 0.15, 2.0)
        except Exception:
            self._rhythm_voice_recent_gap = 0.65

        self._log_enabled = (os.environ.get("LOCKKEY_RHYTHM_LOG", "1") or "1").strip().lower() in (
            "1", "true", "yes", "on"
        )
        self._log_path = log_path
        self._log_fh = None

        # Soft-disable window after any internal error.
        self._disabled_until = 0.0

        # Additive progression knobs. Baseline behavior stays complete; these
        # only bias density, glint rarity, and reward responsiveness.
        self._progression_density_bonus: float = 0.0
        self._progression_frisson_tier: int = 0
        self._progression_algorithm_tier: str = "base"
        self._progression_reward_ids: set[str] = set()

        # Stage checkpoint bias (skill-check stages)
        self._checkpoint_kind: Optional[str] = None
        self._checkpoint_stage: int = 0
        self._checkpoint_until_bar: int = 0
        self._clarity_boost: float = 0.0
        self._density_scale: float = 1.0
        self._interrupt_scale: float = 1.0
        # Long-form song form stitches micro-scenes into 3-5 acts.
        self._song_enabled = (os.environ.get("LOCKKEY_SONG_FORM", "1") or "1").strip().lower() in ("1","true","yes","on")
        try:
            self._chorus_strength = _clamp(float(os.environ.get("LOCKKEY_CHORUS_STRENGTH", "0.75") or "0.75"), 0.0, 1.0)
        except Exception:
            self._chorus_strength = 0.75
        try:
            self._verse_variation = _clamp(float(os.environ.get("LOCKKEY_VERSE_VARIATION", "0.35") or "0.35"), 0.0, 1.0)
        except Exception:
            self._verse_variation = 0.35
        self._act_count: int = 0
        self._act_index: int = 0
        self._act_types: list[str] = []
        self._act_end_bars: list[int] = []
        self._act_type: str = ""
        self._chorus_signature: Dict[str, str] = {}  # {"call": "...", "resp": "..."}
        self._prev_bar_seen: int = -1

    # ──────────────────────────────────────────────────────────────────
    # Public
    # ──────────────────────────────────────────────────────────────────
    def _legacy_song_defaults_placeholder(self) -> None:
        # Stage checkpoint bias (skill-check stages)
        # Long-form "song form" (acts) — stitches micro-scenes into 3–5 acts.
        self._song_enabled = (os.environ.get("LOCKKEY_SONG_FORM", "1") or "1").strip().lower() in ("1","true","yes","on")
        try:
            self._chorus_strength = _clamp(float(os.environ.get("LOCKKEY_CHORUS_STRENGTH", "0.75") or "0.75"), 0.0, 1.0)
        except Exception:
            self._chorus_strength = 0.75
        try:
            self._verse_variation = _clamp(float(os.environ.get("LOCKKEY_VERSE_VARIATION", "0.35") or "0.35"), 0.0, 1.0)
        except Exception:
            self._verse_variation = 0.35
        self._act_count: int = 0
        self._act_index: int = 0
        self._act_types: list[str] = []
        self._act_end_bars: list[int] = []
        self._act_type: str = ""
        self._chorus_signature: Dict[str, str] = {}  # {"call": "...", "resp": "..."}
        self._prev_bar_seen: int = -1

    def apply_progression(self, rewards: dict) -> None:
        """Apply level/achievement reward bias without replacing the director."""
        if not isinstance(rewards, dict):
            return
        try:
            self._progression_density_bonus = _clamp(float(rewards.get("dialogue_density_bonus", 0.0) or 0.0), 0.0, 0.28)
        except Exception:
            self._progression_density_bonus = 0.0
        try:
            self._progression_frisson_tier = max(0, min(3, int(rewards.get("frisson_reward_tier", 0) or 0)))
        except Exception:
            self._progression_frisson_tier = 0
        self._progression_algorithm_tier = str(rewards.get("dialogue_algorithm_tier", "base") or "base")
        try:
            self._progression_reward_ids = set(str(x) for x in (rewards.get("achievement_reward_ids", []) or []))
        except Exception:
            self._progression_reward_ids = set()

        if self._progression_frisson_tier >= 1:
            self._glint_enabled = True
        if self._progression_algorithm_tier in ("glint", "high_resonance", "authored_blend"):
            self._fiend_smooth = True

    def tick(self, engine: Any, dt: float, bpm: float) -> None:
        """Tick from the main game loop. Non-blocking."""
        if not self.enabled:
            return
        try:
            if time.time() < float(self._disabled_until or 0.0):
                return
        except Exception:
            return

        try:
            am = getattr(engine, "audio_manager", None)
            if am is None:
                from voice_engine import get_audio_manager

                am = get_audio_manager()
                engine.audio_manager = am
            if am is None:
                return

            # We rely on voice_engine.tick_music being called elsewhere in the loop.
            slot_i, bar_i, frac_slot, sec_per_slot, slots = am._grid_snapshot()  # type: ignore[attr-defined]

            # Remember bar for checkpoint bias
            self._bar_i = int(bar_i)

            # Initialize last slot without firing.
            if self._last_slot is None:
                self._last_slot = int(slot_i)
                self._last_bar = int(bar_i)
                return

            # Only fire close to the boundary (prevents double-fires mid-slot).
            if int(slot_i) == int(self._last_slot):
                return
            if float(frac_slot) > 0.35:
                self._last_slot = int(slot_i)
                self._last_bar = int(bar_i)
                return

            self._last_slot = int(slot_i)
            self._last_bar = int(bar_i)

            perf = self._snapshot_perf(engine)
            perf = self._apply_rhythm_event(engine, perf)
            mood = str(getattr(engine, "_mood_name", "DUET_TEASE_LOOP") or "DUET_TEASE_LOOP")
            serious = self._is_serious_mood(mood, perf)

            # Pull allowed slots from voice_engine fill-grid (used for micro-scripts + gating).
            try:
                allowed_underlay = set(am._grid_allowed_slots("underlay"))  # type: ignore[attr-defined]
                allowed_interrupt = set(am._grid_allowed_slots("interrupt"))  # type: ignore[attr-defined]
                allowed_suffix = set(am._grid_allowed_slots("suffix"))  # type: ignore[attr-defined]
            except Exception:
                allowed_underlay = set(range(int(slots) or 8))
                allowed_interrupt = set(range(int(slots) or 8))
                allowed_suffix = {int(slots) - 1} if int(slots) > 0 else {0}

            # Rebuild bar plan + micro-script on bar transition.
            try:
                if int(bar_i) != int(getattr(self, "_seen_bar", -1)):
                    # Long-form song form: detect new run (bar reset) and plan acts.
                    try:
                        prev = int(getattr(self, "_prev_bar_seen", -1))
                    except Exception:
                        prev = -1
                    if int(bar_i) < int(prev) or prev < 0:
                        try:
                            self._song_reset(bar_i=int(bar_i))
                        except Exception:
                            pass
                    try:
                        self._song_update_act(engine=engine, bar_i=int(bar_i))
                    except Exception:
                        pass
                    self._prev_bar_seen = int(bar_i)
                    self._seen_bar = int(bar_i)
                    # Expire checkpoint bias
                    try:
                        if self._checkpoint_kind and int(bar_i) >= int(self._checkpoint_until_bar or 0):
                            self._checkpoint_kind = None
                            self._clarity_boost = 0.0
                            self._density_scale = 1.0
                            self._interrupt_scale = 1.0
                    except Exception:
                        pass
                    try:
                        self._glint_update_state(perf=perf, serious=serious, bar=int(bar_i))
                    except Exception:
                        pass

                    self._build_bar_plan(
                        slots=int(slots),
                        engine=engine,
                        perf=perf,
                        mood=mood,
                        serious=serious,
                        allowed_underlay=allowed_underlay,
                        allowed_interrupt=allowed_interrupt,
                        allowed_suffix=allowed_suffix,
                    )
            except Exception:
                pass

            # Decide intent from live state (still used for reactive roles inside bar).
            intent = self._intent_from_perf(perf, mood)

            # Schedule events on the fill-grid.
            self._on_slot(
                engine,
                am,
                slot=int(slot_i),
                bar=int(bar_i),
                slots=int(slots),
                intent=intent,
                mood=mood,
                perf=perf,
                serious=serious,
                allowed_underlay=allowed_underlay,
                allowed_interrupt=allowed_interrupt,
                allowed_suffix=allowed_suffix,
            )
        except Exception:
            # Never crash the game loop.
            try:
                self._disabled_until = time.time() + 6.0
            except Exception:
                pass

    def notify_checkpoint(self, kind: str, stage: int, *, bar_i: Optional[int] = None) -> None:
        """Receive explicit stage checkpoint from rhythm skill-check.
        kind: 'CLEAR' | 'HEAT' | 'STRUGGLE'
        stage: 1-based stage that was completed.
        """
        if not self.enabled:
            return
        try:
            kind_u = (kind or "").strip().upper()
            if kind_u not in ("CLEAR", "HEAT", "STRUGGLE"):
                kind_u = "CLEAR"
            self._checkpoint_kind = kind_u
            self._checkpoint_stage = int(stage or 0)
            if bar_i is None:
                bar_i = int(getattr(self, "_bar_i", 0) or 0)
            dur = 4 if kind_u in ("CLEAR", "HEAT") else 6
            self._checkpoint_until_bar = int(bar_i) + dur
            if kind_u == "STRUGGLE":
                self._clarity_boost = 0.0
                self._density_scale = 0.80
                self._interrupt_scale = 0.0
            elif kind_u == "HEAT":
                self._clarity_boost = 0.25
                self._density_scale = 1.00
                self._interrupt_scale = 0.85
            else:  # CLEAR
                self._clarity_boost = 0.35
                self._density_scale = 0.92
                self._interrupt_scale = 0.65
            self._log({"type": "checkpoint", "kind": kind_u, "stage": self._checkpoint_stage, "until_bar": self._checkpoint_until_bar})
        except Exception:
            return

    def close(self) -> None:
        try:
            if self._log_fh is not None:
                self._log_fh.close()
        except Exception:
            pass
        self._log_fh = None

    # ──────────────────────────────────────────────────────────────────
    # Internals
    # ──────────────────────────────────────────────────────────────────
    def _song_reset(self, *, bar_i: int = 0) -> None:
        """(Re)plan long-form acts for the current rhythm run."""
        if not self._song_enabled:
            self._act_count = 0
            self._act_index = 0
            self._act_types = []
            self._act_end_bars = []
            self._act_type = ""
            self._chorus_signature = {}
            return
        try:
            ac = int(float(os.environ.get("LOCKKEY_ACTS", "0") or "0"))
        except Exception:
            ac = 0
        if ac <= 0:
            ac = random.choice([3, 4, 4, 5])
        ac = max(3, min(5, int(ac)))

        try:
            bpa = int(float(os.environ.get("LOCKKEY_BARS_PER_ACT", "0") or "0"))
        except Exception:
            bpa = 0
        if bpa <= 0:
            n = _get_noise_0_100()
            lo, hi = (8, 12) if n < 55 else (10, 14)
            bpa = random.randint(lo, hi)
        bpa = max(6, min(20, int(bpa)))

        if ac == 3:
            types = ["SETUP", "CHORUS", "CODA"]
        elif ac == 4:
            types = ["SETUP", "VERSE", "CHORUS", "CODA"]
        else:
            types = ["SETUP", "VERSE", "CHORUS", "HEAT", "CODA"]

        ends: list[int] = []
        cur = int(bar_i)
        for _ in range(ac):
            jitter = random.randint(-2, 2)
            cur += max(5, int(bpa) + int(jitter))
            ends.append(int(cur))

        self._act_count = ac
        self._act_index = 0
        self._act_types = types[:ac]
        self._act_end_bars = ends
        self._act_type = str(self._act_types[0] if self._act_types else "")
        self._chorus_signature = {}
        try:
            self._arc_active = False
            self._arc_pos = 0
        except Exception:
            pass
        self._log({"type": "song_reset", "acts": self._act_types, "ends": self._act_end_bars})

    def _play_tier_bell(self, engine: Any) -> None:
        """Best-effort tier_bell stinger at act transitions (never crash)."""
        try:
            candidates = [getattr(engine, "ost", None), getattr(engine, "music", None), getattr(engine, "audio", None), engine]
            for obj in candidates:
                if obj is None:
                    continue
                for fn in ("play_sfx", "play_stinger", "play_one_shot", "play_sound", "play_track", "play"):
                    f = getattr(obj, fn, None)
                    if callable(f):
                        try:
                            f("tier_bell")
                            return
                        except Exception:
                            continue
        except Exception:
            return

    def _song_update_act(self, *, engine: Any, bar_i: int) -> None:
        """Advance act when we cross an act boundary."""
        if not self._song_enabled:
            return
        if not self._act_end_bars or not self._act_types:
            self._song_reset(bar_i=int(bar_i))
            return
        try:
            ai = int(self._act_index)
            if ai < 0:
                ai = 0
            while ai < len(self._act_end_bars) and int(bar_i) >= int(self._act_end_bars[ai]):
                ai += 1
                self._play_tier_bell(engine)
                try:
                    self._arc_active = False
                    self._arc_pos = 0
                    self._pending_response = None
                except Exception:
                    pass
                self._log({"type": "act_transition", "to": ai, "bar": int(bar_i)})
            self._act_index = min(ai, max(0, len(self._act_types) - 1))
            self._act_type = str(self._act_types[self._act_index] if self._act_types else "")
        except Exception:
            return

    def _apply_chorus_verse_bias(self, call_intent: str, resp_intent: str, *, perf: PerfSnapshot, serious: bool) -> tuple[str, str]:
        """Chorus/verse bias: reuse the same call/resp intents on the same beat positions."""
        if (not self._song_enabled) or serious or perf.stressed or perf.event in ("MISS", "BREAK"):
            return call_intent, resp_intent
        at = str(self._act_type or "").upper()
        if at == "CHORUS":
            if (not self._chorus_signature) and perf.accuracy01 >= 0.75 and perf.combo01 >= 0.10:
                self._chorus_signature = {"call": str(call_intent), "resp": str(resp_intent)}
                self._log({"type": "chorus_signature", "call": call_intent, "resp": resp_intent})
                return call_intent, resp_intent
            if self._chorus_signature and random.random() < float(self._chorus_strength):
                return str(self._chorus_signature.get("call") or call_intent), str(self._chorus_signature.get("resp") or resp_intent)
            return call_intent, resp_intent
        if at.startswith("VERSE"):
            if self._chorus_signature and random.random() < float(self._verse_variation):
                def _variant(x: str) -> str:
                    x = str(x or "").upper()
                    ladder = ["OBSERVE", "TEASE", "ESCALATE", "FRENZY"]
                    if x not in ladder:
                        return x
                    i = ladder.index(x)
                    j = max(0, min(len(ladder) - 1, i + random.choice([-1, 1])))
                    return ladder[j]
                return _variant(call_intent), _variant(resp_intent)
            return call_intent, resp_intent
        return call_intent, resp_intent

    def _snapshot_perf(self, engine: Any) -> PerfSnapshot:
        r = getattr(getattr(engine, "scene", None), "rhythm", None)
        v = getattr(engine, "vibe", None)

        intensity = float(getattr(r, "intensity", 0.0) or 0.0)
        # Prefer engine.vibe for hit/miss combo tracking (authoritative in ogre_shader_v5)
        combo = int(getattr(v, "combo", getattr(r, "combo", 0) or 0) or 0)
        max_combo = int(getattr(v, "max_combo", getattr(r, "max_combo", 0) or 0) or 0)
        hits = int(getattr(v, "hits", getattr(r, "hits", 0) or 0) or 0)
        misses = int(getattr(v, "misses", getattr(r, "misses", 0) or 0) or 0)

        overwhelm = float(getattr(r, "_overwhelm", 0.0) or 0.0)
        cog = float(getattr(r, "_cognitive_load", 0.0) or 0.0)
        attune = float(getattr(getattr(engine, "round_state", None), "attune_trust", 0.0) or 0.0)
        return PerfSnapshot(
            intensity01=_clamp(intensity / 100.0, 0.0, 1.0),
            combo=combo,
            max_combo=max_combo,
            hits=hits,
            misses=misses,
            overwhelm=overwhelm,
            cognitive_load=cog,
            attune_trust=attune,
        )

    def _apply_rhythm_event(self, engine: Any, perf: PerfSnapshot) -> PerfSnapshot:
        """Compute per-slot event + streaks from deltas.

        We do not rely on any single judgement field, because the rhythm loop varies.
        Instead we derive:
          - MISS: misses increased
          - HIT: hits increased or combo increased
          - BREAK: combo dropped (combo_break)
          - PERFECT: hit + surge_combo_streak increased (when available)
        """
        try:
            rs = getattr(engine, "round_state", None)
            surge_streak = int(getattr(rs, "surge_combo_streak", 0) or 0)
        except Exception:
            surge_streak = 0

        dh = int(perf.hits) - int(self._last_hits)
        dm = int(perf.misses) - int(self._last_misses)
        # combo can be noisy across modes; treat drop as break event.
        combo_drop = (int(self._last_combo) > 0) and (int(perf.combo) < int(self._last_combo))

        # Stage checkpoint bias: tighten on CLEAR/HEAT, protect/ground on STRUGGLE
        try:
            ck = getattr(self, "_checkpoint_kind", None)
            ck_hint = None
            if ck and int(getattr(self, "_bar_i", 0) or 0) <= int(getattr(self, "_checkpoint_until_bar", 0) or 0):
                if ck == "STRUGGLE":
                    ck_hint = "GROUND"
                elif ck == "CLEAR":
                    if perf.combo01 >= 0.55 and perf.accuracy01 >= 0.75:
                        ck_hint = "OBSERVE"
                    else:
                        ck_hint = "GROUND"
                elif ck == "HEAT":
                    if perf.combo01 >= 0.70:
                        ck_hint = "ESCALATE"
                    else:
                        ck_hint = "OBSERVE"
            if ck_hint:
                setattr(perf, "checkpoint_intent", ck_hint)
        except Exception:
            pass

        event = "NONE"
        if dm > 0:
            event = "MISS"
        elif combo_drop:
            event = "BREAK"
        elif dh > 0 or int(perf.combo) > int(self._last_combo):
            # Hit-like.
            event = "HIT"
            # PERFECT if the surge streak advanced on this tick.
            if surge_streak > int(self._last_surge_streak):
                event = "PERFECT"

        # Update streaks
        if event in ("HIT", "PERFECT"):
            self._hit_streak += 1
            self._miss_streak = 0
        elif event in ("MISS", "BREAK"):
            self._miss_streak += 1
            self._hit_streak = 0
        # perfect streak only for PERFECT; else decay on any non-perfect.
        if event == "PERFECT":
            self._perfect_streak += 1
        else:
            self._perfect_streak = 0
        if event == "BREAK":
            self._last_voice_combo_threshold = 0

        self._last_hits = int(perf.hits)
        self._last_misses = int(perf.misses)
        self._last_combo = int(perf.combo)
        self._last_surge_streak = int(surge_streak)
        self._last_event = event

        perf.event = event
        perf.hit_streak = int(self._hit_streak)
        perf.miss_streak = int(self._miss_streak)
        perf.perfect_streak = int(self._perfect_streak)
        return perf

    def _is_serious_mood(self, mood: str, perf: PerfSnapshot) -> bool:
        m = str(mood or "").upper()
        if "AFTERCARE" in m or "TIRED" in m:
            return True
        # When calm + very low intensity, treat it as "do not clown".
        if perf.intensity01 < 0.12 and perf.calm01 > 0.72:
            return True
        return False


    def _should_start_new_arc(self, perf: PerfSnapshot, serious: bool) -> bool:
        if not self._arc_active:
            return True
        # Break or repeated misses force a new stabilizing arc.
        if perf.miss_streak >= 2 or perf.event == "BREAK":
            return True
        # Serious contexts start a gentle recover arc.
        if serious and (self._arc.get("kind") not in ("RECOVER","STABILIZE")):
            return True
        # End-of-arc.
        if int(self._arc_pos) >= int(self._arc_len):
            return True
        return False

    def _choose_arc_kind(self, perf: PerfSnapshot, serious: bool) -> str:
        at = str(getattr(self, "_act_type", "") or "").upper()
        # Act bias: setup=groove, chorus=groove+signature, heat=hype/spicy, coda=recover.
        if at == "CODA" and (not serious) and (not perf.stressed) and perf.calm01 >= 0.35:
            if random.random() < 0.65:
                return "RECOVER"
        if at == "HEAT" and (not serious) and (not perf.stressed) and perf.accuracy01 >= 0.72 and perf.combo01 >= 0.15:
            if random.random() < 0.55:
                return "HYPE"
        if serious or perf.stressed or perf.calm01 < 0.3:
            return "RECOVER"
        if perf.event in ("MISS","BREAK") or perf.miss_streak > 0:
            return "STABILIZE"
        if perf.event == "PERFECT" and perf.perfect_streak >= 2 and perf.intensity01 > 0.35:
            return "HYPE"
        if perf.intensity01 >= 0.78 and perf.accuracy01 >= 0.75:
            return "HYPE"

        # Spicy devotion loop: when Noise is in the spicy band and player is stable, start a SPICY arc.
        try:
            n = _get_noise_0_100()
        except Exception:
            n = 35
        if self._spicy_enabled and (not serious) and (not perf.stressed) and perf.accuracy01 >= 0.75 and perf.combo01 >= 0.18 and perf.calm01 >= 0.35:
            # Prefer SPICY in the mid-high Noise band (roughly 55–78), with a soft cooldown to prevent overuse.
            if int(n) >= 55 and int(n) <= 78:
                try:
                    bar_i = int(getattr(self, "_seen_bar", 0) or 0)
                except Exception:
                    bar_i = 0
                if bar_i >= int(self._spicy_cooldown_until_bar):
                    # Small random gate so SPICY doesn't dominate every arc.
                    if random.random() < (0.28 + 0.20 * perf.intensity01):
                        return "SPICY"
        return "GROOVE"

    def _arc_length(self, kind: str, perf: PerfSnapshot) -> int:
        # Optional override for arc commitment length (bars).
        try:
            ob = getattr(self, "_arc_bars_override", None)
            if ob is not None:
                ob = int(ob)
                # Keep within sane bounds; serious/stabilize arcs should not balloon.
                ob = max(2, min(8, ob))
                if str(kind or "").upper() in ("STABILIZE", "RECOVER"):
                    ob = max(2, min(4, ob))
                return int(ob)
        except Exception:
            pass

        # 2..4 bars, biased by intensity and stability.
        if kind == "HYPE":
            return 3 if perf.intensity01 > 0.78 else 2
        if kind == "RECOVER":
            return 3
        if kind == "STABILIZE":
            return 2
        # GROOVE
        if perf.accuracy01 >= 0.85 and perf.intensity01 > 0.35:
            return 4
        return 3

    def _arc_stage_intents(self, kind: str, pos: int, base_intent: str, perf: PerfSnapshot) -> tuple[str,str,str]:
        """Return (call_intent, resp_intent, underlay_intent) for the arc stage."""
        p = int(pos)
        if kind == "RECOVER":
            seq = [("GROUND","AFTERCARE","AFTERCARE"),("AFTERCARE","AFTERCARE","AFTERCARE"),("GROUND","AFTERCARE","AFTERCARE"),("AFTERCARE","GROUND","AFTERCARE")]
            return seq[p % len(seq)]
        if kind == "STABILIZE":
            seq = [("COMMAND" if perf.intensity01>0.35 else "GROUND","GROUND","GROUND"),("GROUND","GROUND","GROUND"),("COMMAND","GROUND","GROUND")]
            return seq[p % len(seq)]

        if kind == "SPICY":
            # Spicy "devotional brat" loop stages (7-step). Uses existing intent vocabulary
            # so it remains fully offline and robust with current voice-tag pools.
            # Bird: needy bait -> playful scold/backtrack -> diva mask -> soft vulnerability -> mask reset
            # Fiend: warm guardian/professor devotion (protect/affirm), occasional smooth push.
            phase = int(p) % 7
            self._spicy_phase = phase
            seq = [
                # 0: Bird NEEDY_BAIT (comedic lever)
                ("ESCALATE", "PROTECT", "PHYSICAL"),
                # 1: Bird BACKTRACK_SCOLD ("naughty~")
                ("PLAYFUL_SCOLD", "AFFIRM", "PHYSICAL"),
                # 2: Fiend WHINE/PUSH (still warm)
                ("PROTECT", "TEASE", "PHYSICAL"),
                # 3: Bird DIVA_MASK (hair flip / distance performance)
                ("TEASE", "AFFIRM", "PHYSICAL"),
                # 4: Fiend genuinely smooth (meaning-first) -> Bird break-fluster masked as tease
                ("AFFIRM", "TEASE", "GESTURE_BREATH"),
                # 5: Bird soft vulnerability (brief sincerity before masking again)
                ("AFTERCARE", "PROTECT", "GESTURE_BREATH"),
                # 6: Reset to light tease (awk pretty ditz dancer)
                ("TEASE", "TEASE", "PHYSICAL"),
            ]
            return seq[phase]
        if kind == "HYPE":
            seq = [("TEASE","TEASE","TEASE"),("ESCALATE","ESCALATE","TEASE"),("FRENZY" if perf.intensity01>0.82 else "ESCALATE","FRENZY" if perf.intensity01>0.88 else "ESCALATE","TEASE"),("FRENZY","FRENZY","TEASE")]
            return seq[p % len(seq)]
        # GROOVE
        seq = [("OBSERVE","TEASE","PHYSICAL"),("TEASE","ESCALATE","TEASE"),("ESCALATE","TEASE","PHYSICAL"),("TEASE","ESCALATE","TEASE")]
        # if base intent already escalated, bias into it
        if str(base_intent).upper() in ("ESCALATE","FRENZY"):
            seq = [("TEASE","ESCALATE","PHYSICAL"),("ESCALATE","ESCALATE","TEASE"),("ESCALATE","TEASE","PHYSICAL"),("FRENZY" if perf.intensity01>0.82 else "ESCALATE","ESCALATE","TEASE")]
        return seq[p % len(seq)]

    def _intent_from_perf(self, perf: PerfSnapshot, mood: str) -> str:
        """Select an intent family for this beat.

        This is intentionally small-set so it can match tags broadly.
        We bias based on rhythm events so dialogue feels reactive.
        """
        m = str(mood or "").upper()
        i = float(perf.intensity01)

        try:
            ck_hint = str(getattr(perf, "checkpoint_intent", "") or "").upper()
            if ck_hint:
                return ck_hint
        except Exception:
            pass

        # Safety clamp: if stressed or missing, lean grounded/command.
        if perf.stressed or perf.miss_streak >= 2:
            if "AFTERCARE" in m or i < 0.25:
                return "AFTERCARE"
            return "GROUND"

        # Direct reaction beats
        if perf.event in ("MISS", "BREAK"):
            return "COMMAND" if i > 0.35 else "GROUND"
        if perf.event == "PERFECT" and perf.perfect_streak >= 2:
            return "FRENZY" if i > 0.72 else "ESCALATE"

        # Baseline ladder
        if i < 0.22:
            return "OBSERVE"
        if i < 0.48:
            return "TEASE"
        if i < 0.72:
            return "ESCALATE"
        return "FRENZY"

    def _cooldown_ok(self, key: str, now: float, seconds: float) -> bool:
        t = float(self._next_allowed.get(key, 0.0) or 0.0)
        if now < t:
            return False
        self._next_allowed[key] = now + float(seconds or 0.0)
        return True

    # ─────────────────────────────────────────────────────────────────────
    # Coherence: topic anchors + transition guards
    # ─────────────────────────────────────────────────────────────────────
    def note_lightmap_pose(self, pose: str, *, reward: bool = False, flow_sync_level: int = 0) -> None:
        """Signal pose/reward shifts so rhythm voice can react without polling renderer internals."""
        now = time.time()
        p = str(pose or "")
        if not p:
            return
        try:
            if p != str(getattr(self, "_last_lightmap_pose_seen", "") or ""):
                self._last_lightmap_pose_seen = p
                self._pose_shift_until = now + 1.8
        except Exception:
            pass
        try:
            if bool(reward) or int(flow_sync_level or 0) >= 2:
                self._lightmap_reward_until = now + 2.5
        except Exception:
            pass

    def _rhythm_voice_priority(self, *, role: str, kind: str, perf: PerfSnapshot, engine: Any) -> int:
        """Lower number means more important. Story/theatrical voice is outside this arbiter."""
        now = time.time()
        role_l = str(role or "main").lower()
        try:
            if now < float(getattr(engine, "_flow_special_until", 0.0) or 0.0) or now < float(getattr(engine, "_flow_afterglow_until", 0.0) or 0.0):
                return 2
        except Exception:
            pass
        if perf.event in ("MISS", "BREAK") or perf.miss_streak >= 2:
            return 2
        if now < float(getattr(self, "_lightmap_reward_until", 0.0) or 0.0):
            return 3
        if now < float(getattr(self, "_pose_shift_until", 0.0) or 0.0):
            return 3
        if str(getattr(self, "_glint_state", "off") or "off").lower() == "spike":
            return 4
        try:
            for threshold in (25, 50, 75, 100, 150, 200, 250, 500):
                if int(perf.combo) >= threshold > int(getattr(self, "_last_voice_combo_threshold", 0) or 0):
                    return 4
        except Exception:
            pass
        if perf.perfect_streak >= 4 or (perf.accuracy01 >= 0.88 and perf.combo >= 20):
            return 4
        if role_l == "interrupt":
            return 5
        if role_l in ("murmur", "underlay", "suffix", "gesture", "react", "reaction"):
            return 6
        return 5

    def _rhythm_voice_cooldown_for_priority(self, priority: int, role: str) -> float:
        role_l = str(role or "").lower()
        if priority <= 2:
            return 3.5
        if priority == 3:
            return 4.0
        if priority == 4:
            return max(4.5, float(getattr(self, "_rhythm_voice_global_cd", 4.5) or 4.5))
        if role_l in ("murmur", "underlay", "suffix", "gesture", "react", "reaction"):
            return float(getattr(self, "_rhythm_voice_micro_cd", 6.0) or 6.0)
        return float(getattr(self, "_rhythm_voice_global_cd", 4.5) or 4.5)

    def _audio_voice_busy(self, am: Any, now: float) -> bool:
        """True when theatrical/full/role voice is active or has just ended."""
        try:
            if now < float(getattr(self, "_rhythm_voice_active_until", 0.0) or 0.0):
                return True
        except Exception:
            pass
        try:
            if now < float(getattr(self, "_rhythm_voice_cooldown_until", 0.0) or 0.0):
                return True
        except Exception:
            pass
        try:
            primary_end = float(getattr(am, "_primary_line_end_time", 0.0) or 0.0)
            gap = float(getattr(self, "_rhythm_voice_recent_gap", 0.65) or 0.65)
            if primary_end > 0.0 and now < primary_end + gap:
                return True
        except Exception:
            pass
        for attr in ("_voice_primary_channel", "_voice_murmur_channel", "_voice_interrupt_channel"):
            try:
                ch = getattr(am, attr, None)
                if ch is not None and ch.get_busy():
                    return True
            except Exception:
                continue
        try:
            for ch in list(getattr(am, "_voice_bark_channels", []) or []):
                try:
                    if ch is not None and ch.get_busy():
                        return True
                except Exception:
                    continue
        except Exception:
            pass
        return False

    def _estimate_role_clip_duration(self, am: Any, ev: Any, role: str) -> float:
        role_l = str(role or "main").lower()
        default = 1.45 if role_l == "main" else (0.95 if role_l == "interrupt" else 0.75)
        try:
            clip = str((ev or {}).get("clip") or "")
            if clip:
                meta = getattr(am, "voice_tags", {}).get(clip, {}) if isinstance(getattr(am, "voice_tags", None), dict) else {}
                for key in ("duration", "duration_s", "dur_s", "seconds"):
                    if isinstance(meta, dict) and key in meta:
                        return _clamp(float(meta.get(key) or default), 0.25, 8.0)
        except Exception:
            pass
        return default

    def _queue_rhythm_voice(self, priority: int, payload: Dict[str, Any]) -> None:
        if priority > 4:
            return
        pending = getattr(self, "_rhythm_voice_pending", None)
        try:
            if pending is None or int(priority) < int(pending.get("priority", 99)):
                payload["priority"] = int(priority)
                payload["queued_at"] = time.time()
                self._rhythm_voice_pending = payload
        except Exception:
            self._rhythm_voice_pending = None

    def _try_play_rhythm_voice(
        self,
        engine: Any,
        am: Any,
        *,
        speaker: str,
        role: str,
        intent: str,
        slot: Optional[int],
        mood_name: str,
        serious: bool,
        priority: int,
        kind: str,
        coh_hint_text: str = "",
        coh_anchor_words: Optional[list[str]] = None,
        allow_queue: bool = True,
    ) -> Dict[str, Any]:
        """Central arbiter for all mid-rhythm role voice."""
        now = time.time()
        if priority > 6:
            return {"clip": None, "transcript": None, "tags": [], "arbiter": "dropped_low_priority"}
        if self._audio_voice_busy(am, now):
            if allow_queue:
                self._queue_rhythm_voice(priority, {
                    "speaker": speaker,
                    "role": role,
                    "intent": intent,
                    "slot": slot,
                    "mood_name": mood_name,
                    "serious": serious,
                    "kind": kind,
                    "coh_hint_text": coh_hint_text,
                    "coh_anchor_words": list(coh_anchor_words or []),
                })
            return {"clip": None, "transcript": None, "tags": [], "arbiter": "blocked_busy"}

        try:
            ev = am.play_role_event(
                speaker,
                role=role,
                intent=intent,
                slot=slot,
                mood_name=mood_name,
                serious=serious,
                async_play=True,
                coh_hint_text=coh_hint_text,
                coh_anchor_words=list(coh_anchor_words or []),
            )
        except Exception:
            ev = {"clip": None, "transcript": None, "tags": [], "arbiter": "play_failed"}

        if isinstance(ev, dict) and ev.get("clip"):
            dur = self._estimate_role_clip_duration(am, ev, role)
            self._rhythm_voice_active_until = now + dur
            self._rhythm_voice_cooldown_until = now + dur + self._rhythm_voice_cooldown_for_priority(priority, role)
            try:
                combo = int(getattr(getattr(engine, "vibe", None), "combo", 0) or 0)
                for threshold in (25, 50, 75, 100, 150, 200, 250, 500):
                    if combo >= threshold:
                        self._last_voice_combo_threshold = max(int(self._last_voice_combo_threshold), threshold)
            except Exception:
                pass
        return ev if isinstance(ev, dict) else {"clip": None, "transcript": None, "tags": []}

    def _flush_pending_rhythm_voice(self, engine: Any, am: Any, *, slot: int) -> None:
        pending = getattr(self, "_rhythm_voice_pending", None)
        if not pending:
            return
        try:
            if time.time() - float(pending.get("queued_at", 0.0) or 0.0) > 6.0:
                self._rhythm_voice_pending = None
                return
            if self._audio_voice_busy(am, time.time()):
                return
            payload = dict(pending)
            self._rhythm_voice_pending = None
            self._try_play_rhythm_voice(
                engine,
                am,
                speaker=str(payload.get("speaker") or "BIRDSONG"),
                role=str(payload.get("role") or "main"),
                intent=str(payload.get("intent") or "OBSERVE"),
                slot=int(slot),
                mood_name=str(payload.get("mood_name") or ""),
                serious=bool(payload.get("serious", False)),
                priority=int(payload.get("priority", 5) or 5),
                kind=str(payload.get("kind") or "queued"),
                coh_hint_text=str(payload.get("coh_hint_text") or ""),
                coh_anchor_words=list(payload.get("coh_anchor_words") or []),
                allow_queue=False,
            )
        except Exception:
            self._rhythm_voice_pending = None

    def _tick_anchors(self) -> None:
        """Decay topic anchors once per bar."""
        try:
            dead = []
            for k, v in list(self._anchors.items()):
                nv = int(v) - 1
                if nv <= 0:
                    dead.append(k)
                else:
                    self._anchors[k] = nv
            for k in dead:
                self._anchors.pop(k, None)
        except Exception:
            self._anchors = {}

    def _add_anchor(self, name: str, *, bars: Optional[int] = None) -> None:
        if not name:
            return
        try:
            if bars is None:
                bars = int(random.randint(2, 6))
            cur = int(self._anchors.get(name, 0) or 0)
            self._anchors[name] = max(cur, int(bars))
        except Exception:
            pass

    def _anchors_from_intents(self, call_intent: str, resp_intent: str, kind: str) -> None:
        """Update anchors from intent families. This is deliberately small + cheap."""
        ci = str(call_intent or "").upper()
        ri = str(resp_intent or "").upper()
        kd = str(kind or "").upper()

        # Stabilizers
        if ci in ("GROUND","AFTERCARE","PROTECT") or ri in ("GROUND","AFTERCARE","PROTECT"):
            self._add_anchor("protect_steady")

        # Tease / denial / disbelief
        if ci in ("TEASE","PLAYFUL_SCOLD","DEVOTED_DISBELIEF") or ri in ("TEASE","PLAYFUL_SCOLD","DEVOTED_DISBELIEF"):
            self._add_anchor("tease_deny")
        if ci in ("AFFIRM","DEVOTED_DISBELIEF") or ri in ("AFFIRM","DEVOTED_DISBELIEF"):
            self._add_anchor("praise_disbelief")

        # Want/need + push/backtrack ladder
        if ci in ("ESCALATE","FRENZY") or ri in ("ESCALATE","FRENZY"):
            self._add_anchor("want_need")
            self._add_anchor("push_backtrack")
        if ci in ("COMMAND",) or ri in ("COMMAND",):
            self._add_anchor("push_backtrack")

        # Spicy arcs reinforce the core anchor pair for several bars.
        if kd == "SPICY":
            self._add_anchor("want_need", bars=4)
            self._add_anchor("tease_deny", bars=4)
            self._add_anchor("protect_steady", bars=4)

    def _current_anchor_words(self) -> list[str]:
        """Return a small list of anchor words for the current bar."""
        try:
            # Prefer the longest-lived anchors (the ones that are "still in the air").
            top = sorted(self._anchors.items(), key=lambda kv: int(kv[1]), reverse=True)[:2]
            words: list[str] = []
            for name, _ttl in top:
                words.extend(list(self._anchor_words.get(str(name), []) or []))
            # keep it short; this is just a tie-breaker hint
            return words[:18]
        except Exception:
            return []

    def _guard_transition(self, prev: str, nxt: str, *, serious: bool) -> str:
        """Forbid the worst whiplash jumps (soft state machine)."""
        p = str(prev or "").upper()
        n = str(nxt or "").upper()
        if not n:
            return n
        # Serious beats: no clown spikes.
        if serious and n in ("FRENZY","ESCALATE"):
            return "GROUND"
        # Don't jump from soft recovery into feral spikes.
        if p in ("AFTERCARE","GROUND") and n == "FRENZY":
            return "ESCALATE"
        # Don't jump from soft-vulnerability into feral interrupt.
        if p == "AFTERCARE" and n in ("FRENZY",):
            return "ESCALATE"
        # Don't go from grounded -> wild babble unless noise is deliberately high.
        if p in ("GROUND","AFTERCARE") and n in ("WILD_BABBLE",):
            return "TEASE"
        return n

    def _build_bar_plan(
        self,
        *,
        slots: int,
        engine: Any,
        perf: PerfSnapshot,
        mood: str,
        serious: bool,
        allowed_underlay: set[int],
        allowed_interrupt: set[int],
        allowed_suffix: set[int],
    ) -> None:
        """Rebuild bar plan and a 3–6 beat micro-script.

        We keep the main CALL/RESP skeleton (user-facing 'conversation'), then add
        deterministic *optional* role events (UNDERLAY/INTERRUPT/SUFFIX) placed on
        allowed grid slots, so the performance feels scripted and musical.

        Micro-scripts are selected from live rhythm outcomes (perfect/miss streaks),
        intensity, and stress/serious guards.
        """
        self._bar_plan = {}
        self._micro_plan = {}
        self._bar_ctx = {}
        # This method is called once per bar; decay topic anchors here.
        self._tick_anchors()

        # Resolve main slots within range.
        try:
            ms = [int(s) for s in sorted(self._main_slots) if 0 <= int(s) < int(slots)]
        except Exception:
            ms = []

        # Fast-lines: if the player is clean, add extra main slots for quicker call/response.
        if self._fast_lines and int(slots) >= 8 and perf.accuracy01 >= 0.82 and perf.combo01 >= 0.25 and (not serious):
            for extra in (2, 6):
                if extra not in ms and 0 <= int(extra) < int(slots):
                    ms.append(int(extra))
            ms = sorted(set(ms))
        if ms:
            for i, s in enumerate(ms):
                self._bar_plan[int(s)] = ("CALL" if (i % 2 == 0) else "RESP")

        # Drop any pending response from prior bar (prevents stale replies).
        self._pending_response = None

        # ── Arc selection (multi-bar mini-scenes)
        base_intent = self._intent_from_perf(perf, mood)

        if self._should_start_new_arc(perf, serious):
            kind = self._choose_arc_kind(perf, serious)
            self._arc_len = int(self._arc_length(kind, perf))
            self._arc_pos = 0
            self._arc_start_bar = int(getattr(self, "_seen_bar", 0) or 0)
            self._arc_active = True

            # Pick a stable caller/responder for the arc.
            caller = self._leader_speaker(engine)
            try:
                if self._last_caller and caller == self._last_caller and random.random() < 0.55:
                    caller = self._other(caller)
            except Exception:
                pass
            responder = self._other(caller)

            self._arc = {"kind": kind, "caller": caller, "responder": responder}
        else:
            # Continue arc
            self._arc_pos = int(self._arc_pos) + 1
            kind = str(self._arc.get("kind") or "GROOVE")
            caller = str(self._arc.get("caller") or self._leader_speaker(engine))
            responder = str(self._arc.get("responder") or self._other(caller))


        # SPICY arc enforces role order (keeps the "devotional brat" loop readable):
        # Bird drives bait/scold/diva/vulnerability, Fiend drives whine/smooth devotion.
        if kind == "SPICY":
            try:
                phase = int(self._arc_pos) % 7
            except Exception:
                phase = 0
            caller = "FIEND" if phase in (2, 4) else "BIRDSONG"
            responder = self._other(caller)

        # Arc stage intents (call/resp + underlay baseline)
        call_intent, resp_intent, under_intent = self._arc_stage_intents(kind, int(self._arc_pos), base_intent, perf)

        # Per-beat rhythm events can transiently steer the next bar within the arc.
        if perf.event in ("MISS", "BREAK"):
            # Keep the arc, but force grounding for this bar.
            call_intent = "COMMAND" if perf.intensity01 > 0.35 else "GROUND"
            resp_intent = "GROUND"
            under_intent = "GESTURE_MISS"
        elif perf.event == "PERFECT" and perf.perfect_streak >= 2:
            # Spike with playful physicality.
            if kind == "RECOVER":
                call_intent = "GROUND"
                resp_intent = "AFTERCARE"
            under_intent = "GESTURE_PERFECT"

                # ── Song form bias (chorus/verse): reuse intent signature on the same beat positions.
        try:
            call_intent, resp_intent = self._apply_chorus_verse_bias(str(call_intent), str(resp_intent), perf=perf, serious=serious)
        except Exception:
            pass

# ── Micro-script kind (kept for probability tuning)
        # kind is one of: GROOVE/HYPE/STABILIZE/RECOVER


        # ── Intent map per kind (call/resp + reactions)
        # Arc stage already produced call_intent/resp_intent/under_intent.
        if kind == "RECOVER":
            interrupt_intent = None
            suffix_intent = "AFTERCARE"
            p_under, p_int, p_suf = 0.55, 0.0, 0.92
        elif kind == "STABILIZE":
            interrupt_intent = None
            suffix_intent = "GROUND"
            p_under, p_int, p_suf = 0.65, 0.0, 0.86
        elif kind == "HYPE":
            interrupt_intent = "TEASE"
            suffix_intent = "TEASE"
            p_under, p_int, p_suf = 0.90, 0.38, 0.78

        elif kind == "SPICY":
            # Spicy: meaning-first, devotional loop. Keep it clean: underlay high, interrupts controlled,
            # and a soft-vulnerability bar (phase 5) is protected from spikes.
            try:
                phase = int(self._arc_pos) % 7
            except Exception:
                phase = 0
            interrupt_intent = "TEASE"
            if phase == 5:
                interrupt_intent = None
            suffix_intent = "AFTERCARE" if phase in (4, 5) else (call_intent if perf.intensity01 >= 0.30 else "TEASE")
            try:
                need01 = float(getattr(self, "_neediness", 0.0) or 0.0) / 100.0
            except Exception:
                need01 = 0.0
            p_under = 0.80 + 0.12 * need01
            p_int = 0.18 + 0.10 * perf.combo01
            p_suf = 0.74 + 0.10 * min(1.0, perf.intensity01 + 0.3 * need01)
            try:
                den = float(getattr(self, "_deniability", 100.0) or 100.0)
                if den <= 40.0:
                    p_int *= 0.70
                if den <= 20.0:
                    interrupt_intent = None
                    p_int = 0.0
            except Exception:
                pass

        else:  # GROOVE
            interrupt_intent = "TEASE" if perf.combo01 > 0.22 else None
            suffix_intent = "AFTERCARE" if perf.intensity01 < 0.25 else call_intent
            p_under, p_int, p_suf = (0.70 + 0.18 * perf.intensity01), (0.12 + 0.20 * perf.combo01), (0.62 + 0.20 * perf.intensity01)
        # Density multiplier. If explicitly set, it wins; otherwise derive from the Noise dial.
        try:
            if "LOCKKEY_MICROSCRIPT_DENSITY" in os.environ:
                dens = float(os.environ.get("LOCKKEY_MICROSCRIPT_DENSITY", "1.0") or "1.0")
            else:
                dens = _noise_density_multiplier()
        except Exception:
            dens = 1.0
        # Apply checkpoint scaling (tighten/ground based on stage signal)
        try:
            dens = float(dens) * float(getattr(self, "_density_scale", 1.0) or 1.0)
        except Exception:
            pass
        try:
            dens = float(dens) * (1.0 + float(getattr(self, "_progression_density_bonus", 0.0) or 0.0))
        except Exception:
            pass
        try:
            p_int = float(p_int) * float(getattr(self, "_interrupt_scale", 1.0) or 1.0)
        except Exception:
            pass
        ck = getattr(self, "_checkpoint_kind", None)
        try:
            if ck and int(getattr(self, "_bar_i", 0) or 0) <= int(getattr(self, "_checkpoint_until_bar", 0) or 0):
                if ck == "CLEAR":
                    p_under *= 0.90
                    p_suf *= 0.95
                elif ck == "HEAT":
                    p_int *= 0.85
                elif ck == "STRUGGLE":
                    p_int = 0.0
                    p_under *= 0.90
                    p_suf *= 1.10
        except Exception:
            pass
        p_under = _clamp(p_under * dens, 0.0, 0.95)
        p_suf = _clamp(p_suf * dens, 0.0, 0.95)
        p_int = _clamp(p_int * dens, 0.0, 0.85)

        # Interrupt hard guards (balanced: never in serious/recovery).
        if serious or perf.stressed or perf.miss_streak > 0 or perf.intensity01 < 0.42:
            interrupt_intent = None
            p_int = 0.0

        # ── Slot placement helpers
        forbidden = set(ms)
        def pick_near(target: int, allowed: set[int]) -> Optional[int]:
            if not allowed:
                return None
            # try exact, then +/-1..3 (wrap)
            for d in (0, 1, -1, 2, -2, 3, -3):
                s = (int(target) + int(d)) % int(slots or 8)
                if s in allowed and s not in forbidden:
                    return s
            # fallback: any allowed not forbidden
            for s in sorted(allowed):
                if s not in forbidden:
                    return int(s)
            return None

        # Choose micro-script slots relative to main beats (or sensible defaults).
        call_slot = ms[0] if ms else 0
        resp_slot = ms[1] if len(ms) > 1 else ((call_slot + (slots // 2)) % max(1, slots))

        # Pre-roll + post-roll micro-gestures: tiny physical cues scheduled like percussion.
        # - pre-roll gesture lands 1 slot before each main line
        # - reaction gesture can land 1 slot after (especially after Fiend SMOOTH / PROTECT)
        pre_call = pick_near((call_slot - 1) % max(1, slots), allowed_underlay)
        pre_resp = pick_near((resp_slot - 1) % max(1, slots), allowed_underlay)
        post_call = pick_near((call_slot + 1) % max(1, slots), allowed_underlay)
        post_resp = pick_near((resp_slot + 1) % max(1, slots), allowed_underlay)

        def _pick_pre_gesture(spk: str, main_intent: str, *, is_caller: bool) -> str:
            it = str(main_intent or "").upper()
            sp = str(spk or "").upper()
            is_fiend = ("FIEND" in sp)
            # Serious/recovery: only allow breath/steady cues (no comedy physicality).
            if serious or kind in ("RECOVER","STABILIZE","AFTERCARE"):
                return "STEADY_BREATH" if is_fiend else "GESTURE_BREATH"
            # Bird diva mask / backtrack scold reads as cute physical punctuation.
            if (not is_fiend) and it in ("DIVA_MASK","BACKTRACK_SCOLD","PLAYFUL_SCOLD"):
                return "HAIRFLIP"
            # Bird neediness as bait: pout + tiny sigh.
            if (not is_fiend) and it in ("NEEDY_BAIT","ESCALATE","DENY"):
                return "POUT"
            # Fiend protect/ground: steady breath / lean-in.
            if is_fiend and it in ("PROTECT","GROUND"):
                return "STEADY_BREATH" if perf.calm01 < 0.55 else "LEANIN"
            # Fiend warm devotion: occasionally preface with subtle pupil dilation cue.
            try:
                if self._fiend_smooth and is_fiend:
                    if it in ("DEVOTED_DISBELIEF","PLAYFUL_SCOLD","AFFIRM") and perf.calm01 > 0.45 and random.random() < 0.55:
                        return "PUPIL"
            except Exception:
                pass
            # Default: performance-reactive micro cue.
            if perf.event in ("MISS","BREAK"):
                return "GESTURE_MISS"
            if perf.event == "PERFECT":
                return "GESTURE_PERFECT"
            return "PHYSICAL"

        def _pick_post_gesture(main_spk: str, main_intent: str, other_spk: str) -> Optional[str]:
            it = str(main_intent or "").upper()
            ms = str(main_spk or "").upper()
            os_ = str(other_spk or "").upper()
            main_is_fiend = ("FIEND" in ms)
            other_is_bird = ("BIRD" in os_) or ("BIRDSONG" in os_)
            if serious or kind in ("RECOVER","STABILIZE","AFTERCARE"):
                return None
            # Fiend smooth → Bird trace (soft vuln leak), very cute + obvious.
            if main_is_fiend and other_is_bird and it in ("SMOOTH","AFFIRM","DEVOTED_DISBELIEF","PLAYFUL_SCOLD"):
                return "TRACE" if perf.calm01 > 0.25 else "BREATH_HITCH"
            # Fiend protect → Bird steady reaction (breath hitch / lean-in).
            if main_is_fiend and other_is_bird and it in ("PROTECT","GROUND"):
                return "BREATH_HITCH" if perf.calm01 > 0.30 else "LEANIN"
            # Bird diva/neediness → lookback as punctuation.
            if (not main_is_fiend) and it in ("DIVA_MASK","NEEDY_BAIT","PLAYFUL_SCOLD"):
                return "LOOKBACK"
            return None

        if (not serious) and perf.calm01 > 0.18:
            if pre_call is not None:
                g_call = _pick_pre_gesture(str(caller), str(call_intent or ""), is_caller=True)
                self._micro_plan.setdefault(int(pre_call), []).append(
                    {"role": "gesture", "speaker": "CALLER", "intent": g_call, "p": float(0.72 if kind != "RECOVER" else 0.85)}
                )
            if pre_resp is not None:
                g_resp = _pick_pre_gesture(str(responder), str(resp_intent or ""), is_caller=False)
                self._micro_plan.setdefault(int(pre_resp), []).append(
                    {"role": "gesture", "speaker": "RESPONDER", "intent": g_resp, "p": float(0.64 if kind != "RECOVER" else 0.82)}
                )
            # Post-roll reactions: slot after the line (if available).
            g_after_call = _pick_post_gesture(str(caller), str(call_intent or ""), str(responder))
            if g_after_call and post_call is not None:
                self._micro_plan.setdefault(int(post_call), []).append(
                    {"role": "gesture", "speaker": "RESPONDER", "intent": g_after_call, "p": float(0.58)}
                )
            g_after_resp = _pick_post_gesture(str(responder), str(resp_intent or ""), str(caller))
            if g_after_resp and post_resp is not None:
                self._micro_plan.setdefault(int(post_resp), []).append(
                    {"role": "gesture", "speaker": "CALLER", "intent": g_after_resp, "p": float(0.56)}
                )

        # Underlay tends to sit between call and response (backbeat feel).

        under_slot = pick_near((call_slot + max(1, slots // 4)) % max(1, slots), allowed_underlay)
        # Interrupt tends to sit just after response (spike), or on downbeat midbar.
        int_slot = pick_near((resp_slot + 1) % max(1, slots), allowed_interrupt)
        # Suffix is tail.
        suf_slot = pick_near((max(0, slots - 1)), allowed_suffix)

        # ── Build micro-plan
        if under_slot is not None and p_under > 0.0 and (not serious):
            self._micro_plan.setdefault(int(under_slot), []).append(
                {"role": "murmur", "speaker": "OTHER", "intent": under_intent, "p": float(p_under)}
            )
        if int_slot is not None and interrupt_intent is not None and p_int > 0.0:
            self._micro_plan.setdefault(int(int_slot), []).append(
                {"role": "interrupt", "speaker": "OTHER", "intent": interrupt_intent, "p": float(p_int)}
            )
        if suf_slot is not None and p_suf > 0.0 and (not serious):
            self._micro_plan.setdefault(int(suf_slot), []).append(
                {"role": "suffix", "speaker": "OTHER", "intent": suffix_intent, "p": float(p_suf)}
            )


        # ── Spicy meters: deniability + neediness (Bird performance loop)
        if kind == "SPICY" and (not serious):
            try:
                phase = int(self._arc_pos) % 7
            except Exception:
                phase = 0
            try:
                if str(caller).upper() == "BIRDSONG":
                    ci = str(call_intent or "").upper()
                    if ci == "ESCALATE":
                        self._neediness += 10.0 + 10.0 * float(perf.intensity01 or 0.0)
                        self._deniability -= 4.0
                    elif ci == "PLAYFUL_SCOLD":
                        self._neediness += 3.5
                        self._deniability -= 8.0
                    elif ci == "AFTERCARE":
                        # brief sincerity: neediness vents, deniability drops (she showed the truth)
                        self._neediness -= 8.0
                        self._deniability -= 6.0
                    else:
                        self._neediness += 4.5
                        self._deniability -= 3.0
                else:
                    ci = str(call_intent or "").upper()
                    if ci in ("PROTECT", "AFFIRM"):
                        self._neediness -= 9.0
                        self._deniability -= 2.5
            except Exception:
                pass

            try:
                if perf.event in ("MISS", "BREAK") or int(perf.miss_streak or 0) > 0:
                    self._neediness += 6.0
                elif perf.event == "PERFECT" and int(perf.perfect_streak or 0) >= 2:
                    self._deniability -= 1.0
            except Exception:
                pass

            if phase == 6:
                self._deniability += 3.0

            self._neediness = _clamp(float(self._neediness), 0.0, 100.0)
            self._deniability = _clamp(float(self._deniability), 0.0, 100.0)

            if phase == 6:
                try:
                    bar_i = int(getattr(self, "_seen_bar", 0) or 0)
                except Exception:
                    bar_i = 0
                self._spicy_cooldown_until_bar = int(bar_i) + 2


        # Store bar context so CALL/RESP are consistent and can drive motif memory.
        # Transition guard: prevent the worst whiplash jumps.
        try:
            call_intent = self._guard_transition(self._last_main_intent.get(str(caller).upper(), ""), str(call_intent), serious=serious)
            resp_intent = self._guard_transition(self._last_main_intent.get(str(responder).upper(), ""), str(resp_intent), serious=serious)
        except Exception:
            pass

        # Anchor update: keep 1–2 topics “in the air” for 2–6 bars.
        try:
            self._anchors_from_intents(str(call_intent), str(resp_intent), str(kind))
        except Exception:
            pass

        self._bar_ctx = {
            "kind": kind,
            "caller": caller,
            "responder": responder,
            "call_intent": str(call_intent),
            "resp_intent": str(resp_intent),
            "anchor_words": self._current_anchor_words(),
        }


    

    # ── GLINT asset loading + selection (subtitle-only micro-circuit)
    def _load_glint_assets(self) -> None:
        """Load glint_assets_v1.json from line_packs. Safe defaults if missing."""
        here = _fiendish_asset_root()
        fp = here / "line_packs" / "glint_assets_v1.json"
        data = {}
        if fp.exists():
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        assets = list((data.get("glint_assets_v1") or [])) if isinstance(data, dict) else []
        policy = dict((data.get("glint_selection_policy_v1") or {})) if isinstance(data, dict) else {}
        by_family: Dict[str, list[dict]] = {}
        for a in assets:
            try:
                fam = str(a.get("family") or "").strip()
                if not fam:
                    continue
                by_family.setdefault(fam, []).append(a)
            except Exception:
                continue
        self._glint_assets_by_family = by_family
        self._glint_policy = policy

    def _glint_state_min_ok(self, item_min_state: str) -> bool:
        ms = str(item_min_state or "hover").strip().lower()
        st = str(getattr(self, "_glint_state", "off") or "off").strip().lower()
        if st == "spike":
            return ms in ("hover","spike","0","1","2","3","any")
        if st == "hover":
            return ms in ("hover","0","1","any")
        return False

    def _glint_allowed_tiers(self) -> list[int]:
        st = str(getattr(self, "_glint_state", "off") or "off").strip().lower()
        try:
            reward_tier = int(getattr(self, "_progression_frisson_tier", 0) or 0)
        except Exception:
            reward_tier = 0
        if st == "spike":
            return [0,1,2,3]
        if st == "hover":
            if reward_tier >= 2:
                return [0,1,2]
            return [0,1]
        return []

    def _glint_pick_tier(self) -> int:
        st = str(getattr(self, "_glint_state", "off") or "off").strip().lower()
        dist = {}
        try:
            dist = dict((self._glint_policy.get("tier_distribution_by_state") or {}).get(st) or {})
        except Exception:
            dist = {}
        # Default distributions (hover is subtle, spike has rare tier3)
        if not dist:
            dist = {"0": 0.80, "1": 0.20} if st == "hover" else {"0": 0.35, "1": 0.35, "2": 0.20, "3": 0.10}
        try:
            reward_tier = int(getattr(self, "_progression_frisson_tier", 0) or 0)
            if reward_tier >= 2 and st == "hover":
                dist = {"0": 0.58, "1": 0.32, "2": 0.10}
            elif reward_tier >= 1 and st == "spike":
                dist = {"0": 0.28, "1": 0.34, "2": 0.24, "3": 0.14}
        except Exception:
            pass
        r = random.random()
        acc = 0.0
        picked = 0
        for k, p in dist.items():
            try:
                acc += float(p)
            except Exception:
                continue
            if r <= acc:
                try:
                    picked = int(k)
                except Exception:
                    picked = 0
                break
        return int(max(0, min(3, picked)))

    def _glint_choose(self, family: str) -> Optional[dict]:
        fam = str(family or "").strip()
        pool = list(self._glint_assets_by_family.get(fam) or [])
        if not pool:
            return None
        allowed_tiers = set(self._glint_allowed_tiers())
        tier = self._glint_pick_tier()
        # Filter by state + allowed tiers
        cand = []
        for it in pool:
            try:
                if not self._glint_state_min_ok(str(it.get("glint_min_state") or "hover")):
                    continue
                t = int(it.get("rarity_tier") or 0)
                if t not in allowed_tiers:
                    continue
                cand.append(it)
            except Exception:
                continue
        if not cand:
            return None
        # Prefer desired tier but fall back gracefully
        same = [c for c in cand if int(c.get("rarity_tier") or 0) == int(tier)]
        pick_from = same if same else cand
        return random.choice(pick_from) if pick_from else None

    def _glint_cd_ok(self, item: dict, *, bar: int) -> bool:
        fam = str(item.get("family") or "").strip()
        cd = int(item.get("cooldown_bars") or 0)
        last = int(self._glint_last_by_family.get(fam, -999))
        return (int(bar) - int(last)) >= int(cd)

    def _glint_mark_used(self, item: dict, *, bar: int) -> None:
        fam = str(item.get("family") or "").strip()
        if fam:
            self._glint_last_by_family[fam] = int(bar)

    def _glint_update_state(self, *, perf: PerfSnapshot, serious: bool, bar: int) -> None:
        if not getattr(self, "_glint_enabled", False):
            self._glint_state = "off"
            return
        if serious or perf.stressed or perf.miss_streak > 0:
            self._glint_state = "off"
            return
        # Hover: clean play with a hint of heat/clarity
        hover = (perf.accuracy01 >= 0.85 and perf.combo01 >= 0.22 and perf.calm01 >= 0.20)
        try:
            ck = str(getattr(self, "_checkpoint_kind", "") or "").upper()
            if ck in ("CLEAR","HEAT"):
                hover = hover or (perf.accuracy01 >= 0.82 and perf.combo01 >= 0.18)
        except Exception:
            pass
        if not hover:
            self._glint_state = "off"
            return

        # Spike window: rare sacred spikes (8–16 bars) when deniability drops + quality-time is real
        if int(bar) <= int(getattr(self, "_glint_spike_until_bar", -1) or -1):
            self._glint_state = "spike"
            return

        can_spike = False
        try:
            den = float(getattr(self, "_deniability", 100.0) or 100.0)
            need = float(getattr(self, "_neediness", 0.0) or 0.0)
            can_spike = (den <= 45.0 and need >= 25.0) or (den <= 30.0) or (need >= 45.0)
        except Exception:
            can_spike = False
        try:
            ck = str(getattr(self, "_checkpoint_kind", "") or "").upper()
            if ck == "HEAT":
                can_spike = can_spike or (perf.perfect_streak >= 2)
        except Exception:
            pass

        if can_spike and int(bar) >= int(getattr(self, "_glint_next_spike_bar", 0) or 0) and perf.perfect_streak >= 2:
            self._glint_state = "spike"
            self._glint_spike_until_bar = int(bar) + 1  # 2-bar micro event
            self._glint_next_spike_bar = int(bar) + random.randint(8, 16)
        else:
            self._glint_state = "hover"

    def _glint_try_emit_subtitle(self, engine: Any, *, item: dict, bar: int) -> None:
        """Emit a subtitle-only stage-direction line via engine.dialogue_commit(force=True)."""
        sp = str(item.get("speaker") or "").strip() or "FIEND"
        tx = str(item.get("text") or "").strip()
        if not tx:
            return
        try:
            am = getattr(engine, "audio_manager", None)
            if am is not None and self._audio_voice_busy(am, time.time()):
                return
        except Exception:
            pass
        # Force true to bypass RADIO_PLAY_ONLY in intimacy mode
        try:
            dc = getattr(engine, "dialogue_commit", None)
            if callable(dc):
                dc(sp, tx, kind="line", ttl=1.8, force=True)
        except Exception:
            pass
        try:
            self._glint_bar_last_sub = int(bar)
        except Exception:
            pass

    def _other(self, speaker: str) -> str:
        sp = str(speaker or "BIRDSONG").upper()
        return "FIEND" if sp == "BIRDSONG" else "BIRDSONG"


    def _is_fiend(self, speaker: str) -> bool:
        return "FIEND" in str(speaker or "").upper()

    def _fiend_intent(self, intent: str, perf: PerfSnapshot) -> str:
        """Fiend smoothing: protector/guardian — *playful devotion* (style 2).

        Philosophy: Fiend is a warm guardian who *means it*, but can surface
        affectionate disbelief / playful scolding ("rude~", "I can't believe")
        when safe. This does NOT route-lock transcripts; it only steers intent
        labels so the voice engine can bias tags.

        The strength of this smoothing is controlled by:
          - LOCKKEY_FIEND_GUARDIAN_BIAS (0..100). 100 = always; 0 = only during stress.
        """
        it = str(intent or "OBSERVE").upper()

        # Physical/gesture intents should stay physical; keep them in that lane.
        if it in ("PHYSICAL", "GESTURE_BREATH", "GESTURE_MISS", "GESTURE_PERFECT", "PUPIL", "LOOKBACK", "TRACE", "HAIRFLIP", "POUT", "LEANIN", "BREATH_HITCH", "STEADY_BREATH"):
            return it

        stressed = bool(perf.miss_streak > 0 or perf.stressed)

        # Guardian bias: if not stressed, sometimes let raw intent through.
        try:
            gb = float(getattr(self, "_guardian_bias", 80) or 80) / 100.0
        except Exception:
            gb = 0.80
        gb = _clamp(gb, 0.0, 1.0)
        if (not stressed) and gb < 0.999:
            try:
                if random.random() > gb:
                    return it
            except Exception:
                pass

        # During stress, Fiend becomes an anchor.
        if stressed:
            if it in ("TEASE", "ESCALATE", "FRENZY"):
                return "PROTECT"
            if it == "COMMAND":
                return "GROUND"
            return "GROUND" if it in ("DENY",) else it

        # In clean/stable play, Fiend can be lovingly incredulous.
        if it == "TEASE":
            if perf.event == "PERFECT" and perf.combo01 > 0.35:
                return "DEVOTED_DISBELIEF"
            # Default safe teasing is playful scold, not performative banter.
            return "PLAYFUL_SCOLD" if perf.intensity01 < 0.80 else "AFFIRM"

        if it in ("ESCALATE", "FRENZY"):
            # Reframe intensity as protective devotion.
            return "PROTECT" if perf.calm01 > 0.35 else "GROUND"

        if it == "COMMAND":
            # Soften commands into guidance.
            return "PROTECT" if perf.intensity01 > 0.35 else "OBSERVE"

        return it
    def _leader_speaker(self, engine: Any) -> str:
        """Pick the speaker who 'leads' the next call beat."""
        try:
            rs = getattr(engine, "round_state", None)
            pd = float(getattr(rs, "power_dynamic", 0.0) or 0.0)
        except Exception:
            pd = 0.0
        if pd > 0.15:
            return "FIEND"
        if pd < -0.15:
            return "BIRDSONG"
        # contested: alternate
        return "BIRDSONG" if (self._main_toggle % 2 == 0) else "FIEND"

    def _response_intent(self, call_intent: str, perf: PerfSnapshot) -> str:
        """Derive a response intent that feels like a reply, not a reset."""
        ci = str(call_intent or "TEASE").upper()
        if perf.event in ("MISS", "BREAK"):
            return "COMMAND" if ci in ("ESCALATE", "FRENZY", "TEASE") else "GROUND"
        if perf.event == "PERFECT":
            if ci in ("COMMAND", "GROUND", "AFTERCARE"):
                return "TEASE"
            return "ESCALATE" if perf.intensity01 < 0.78 else "FRENZY"
        # neutral
        if ci == "AFTERCARE":
            return "AFTERCARE"
        if ci == "GROUND":
            return "GROUND"
        if ci == "COMMAND":
            return "TEASE"
        if ci == "FRENZY":
            return "ESCALATE"
        return ci

    def _on_slot(
        self,
        engine: Any,
        am: Any,
        *,
        slot: int,
        bar: int,
        slots: int,
        intent: str,
        mood: str,
        perf: PerfSnapshot,
        serious: bool,
        allowed_underlay: set[int],
        allowed_interrupt: set[int],
        allowed_suffix: set[int],
    ) -> None:
        now = time.time()
        try:
            self._flush_pending_rhythm_voice(engine, am, slot=int(slot))
        except Exception:
            pass
        # Reset per-bar counters (cascade guard)
        try:
            if int(bar) != int(self._bar_extra_bar):
                self._bar_extra = {"murmur": 0, "interrupt": 0, "suffix": 0, "gesture": 0, "prefix": 0, "glint_sub": 0}
                self._bar_extra_bar = int(bar)
        except Exception:
            pass

        extras_this_slot = 0
        max_extras_per_slot = 1
        try:
            if not self._cascade_guard:
                max_extras_per_slot = 99
            else:
                # Allow slightly denser texture at high noise, but keep slot clean by default.
                n = _get_noise_0_100()
                max_extras_per_slot = 2 if n >= 60 else 1
        except Exception:
            max_extras_per_slot = 1


        
        # ── GLINT subtitle-only micro-circuit (touch excuse → laugh-back → stillness)
        try:
            # Resolve per-bar cap: hover=1 subtitle micro; spike=2 (still clean).
            st = str(getattr(self, "_glint_state", "off") or "off").lower()
            glint_cap = 0
            if st == "hover":
                glint_cap = 1
            elif st == "spike":
                glint_cap = 2

            # Pending reaction closure (if we previously emitted a Bird touch).
            try:
                pr = getattr(self, "_glint_pending_react", None)
                if pr and int(pr.get("bar", -1)) == int(bar) and int(slot) >= int(pr.get("earliest_slot", 0)) and int(self._bar_extra.get("glint_sub", 0)) < int(glint_cap):
                    item = self._glint_choose("F_G_SILENT_REACT")
                    if item and self._glint_cd_ok(item, bar=bar):
                        self._glint_try_emit_subtitle(engine, item=item, bar=bar)
                        self._glint_mark_used(item, bar=bar)
                        self._bar_extra["glint_sub"] = int(self._bar_extra.get("glint_sub", 0)) + 1
                        extras_this_slot += 1
                    self._glint_pending_react = None
            except Exception:
                self._glint_pending_react = None

            if glint_cap > 0 and (not serious) and int(self._bar_extra.get("glint_sub", 0)) < int(glint_cap):
                kind = str(self._bar_ctx.get("kind") or "")
                if kind not in ("RECOVER","STABILIZE","AFTERCARE") and slot in allowed_underlay and slot not in set(self._bar_plan.keys()):
                    # Bias toward slots adjacent to main beats.
                    near_main = False
                    try:
                        for s in self._bar_plan.keys():
                            if int((slot - int(s)) % max(1, slots)) in (1, max(0, slots - 1)):
                                near_main = True
                                break
                    except Exception:
                        near_main = False

                    base_p = 0.085 if st == "hover" else 0.18
                    if near_main:
                        base_p *= 1.7
                    # Never spam: also require we didn't emit one just last bar (unless spike).
                    if st != "spike" and int(bar) - int(getattr(self, "_glint_bar_last_sub", -999) or -999) < 1:
                        base_p *= 0.0

                    if extras_this_slot < max_extras_per_slot and random.random() < float(base_p):
                        # Identify adjacency to a main beat for targeted families.
                        prev_slot = int((slot - 1) % max(1, slots))
                        next_slot = int((slot + 1) % max(1, slots))
                        fam = "F_G_DIEGETIC_GLANCE"
                        # Pre-FIEND main → glance
                        try:
                            if next_slot in self._bar_plan:
                                plan_next = str(self._bar_plan.get(next_slot) or "").upper()
                                spk_next = str(self._bar_ctx.get("caller") or "BIRDSONG") if plan_next == "CALL" else str(self._bar_ctx.get("responder") or "FIEND")
                                if self._is_fiend(spk_next):
                                    fam = "F_G_DIEGETIC_GLANCE"
                        except Exception:
                            pass
                        # Post-main → touch/micro response
                        try:
                            if prev_slot in self._bar_plan:
                                plan_prev = str(self._bar_plan.get(prev_slot) or "").upper()
                                spk_prev = str(self._bar_ctx.get("caller") or "BIRDSONG") if plan_prev == "CALL" else str(self._bar_ctx.get("responder") or "FIEND")
                                it_prev = str(self._bar_ctx.get("call_intent") or "") if plan_prev == "CALL" else str(self._bar_ctx.get("resp_intent") or "")
                                it_u = it_prev.upper()
                                if (not self._is_fiend(spk_prev)) and it_u in ("DIVA_MASK","BACKTRACK_SCOLD","PLAYFUL_SCOLD","NEEDY_BAIT","DENY","ESCALATE"):
                                    fam = "B_G_TOUCH"
                                elif self._is_fiend(spk_prev) and it_u in ("SMOOTH","AFFIRM","DEVOTED_DISBELIEF","PROTECT","GROUND","STEADY_AUTHORITY","CLAIM"):
                                    fam = "F_G_MICRO_RESP"
                        except Exception:
                            pass

                        item = self._glint_choose(fam)
                        if item and self._glint_cd_ok(item, bar=bar):
                            self._glint_try_emit_subtitle(engine, item=item, bar=bar)
                            self._glint_mark_used(item, bar=bar)
                            self._bar_extra["glint_sub"] = int(self._bar_extra.get("glint_sub", 0)) + 1
                            extras_this_slot += 1
                            # If we emitted Bird touch, set up a pending Fiend reaction to close the circuit.
                            try:
                                if fam == "B_G_TOUCH":
                                    self._glint_pending_react = {"bar": int(bar), "earliest_slot": int(slot) + 1}
                            except Exception:
                                pass
        except Exception:
            pass

# ── Script main beats (call/response)
        plan = str(self._bar_plan.get(int(slot), "") or "").upper()
        main_cd = 0.34 if self._fast_lines else 0.55
        # Probabilistic mains: let rhythm breathe; voice becomes an accent.
        try:
            main_prob = float(getattr(self, "_main_prob", 1.0) or 1.0)
        except Exception:
            main_prob = 1.0
        if plan and self._cooldown_ok("main", now, seconds=main_cd):
            # Roll once per slot; if we skip, clear pending response so we don't "half-chain".
            try:
                if main_prob < 1.0 and random.random() >= main_prob:
                    self._pending_response = None
                    return
            except Exception:
                pass
            if plan == "CALL":
                # Bar context chooses caller/responder + call intent (micro-script).
                caller = str(self._bar_ctx.get("caller") or self._leader_speaker(engine))
                responder = str(self._bar_ctx.get("responder") or self._other(caller))
                call_intent = str(self._bar_ctx.get("call_intent") or intent or "TEASE")
                if self._fiend_smooth and self._is_fiend(caller):
                    call_intent = self._fiend_intent(call_intent, perf)
                self._last_caller = caller
                ev = self._try_play_rhythm_voice(
                    engine,
                    am,
                    speaker=caller,
                    role="main",
                    intent=call_intent,
                    slot=slot,
                    mood_name=mood,
                    serious=serious,
                    priority=self._rhythm_voice_priority(role="main", kind="call", perf=perf, engine=engine),
                    kind="call",
                    coh_hint_text=str(self._last_transcript.get(str(responder).upper(), "") or ""),
                    coh_anchor_words=list(self._bar_ctx.get("anchor_words") or []),
                )
                self._log(engine, kind="call", speaker=caller, intent=call_intent, mood=mood, slot=slot, extra=ev)

                # Remember what was *actually* said (for responsive coherence).
                try:
                    tr = str((ev or {}).get("transcript") or "")
                    if tr:
                        self._last_transcript[str(caller).upper()] = tr
                    self._last_main_intent[str(caller).upper()] = str(call_intent)
                except Exception:
                    pass

                

                # queue response for the next RESP slot in this bar.
                self._pending_response = {
                    "responder": responder,
                    "call_intent": call_intent,
                    "resp_intent": str(self._bar_ctx.get("resp_intent") or ""),
                    "mood": mood,
                    "serious": bool(serious),
                    "call_transcript": str((ev or {}).get("transcript") or ""),
                }

            elif plan == "RESP" and self._pending_response is not None:
                pr = dict(self._pending_response)
                responder = str(pr.get("responder", "BIRDSONG") or "BIRDSONG")
                call_intent = str(pr.get("call_intent", intent) or intent)
                resp_intent = str(pr.get("resp_intent") or "").strip() or self._response_intent(call_intent, perf)
                if self._fiend_smooth and self._is_fiend(responder):
                    resp_intent = self._fiend_intent(resp_intent, perf)

                ev = self._try_play_rhythm_voice(
                    engine,
                    am,
                    speaker=responder,
                    role="main",
                    intent=resp_intent,
                    slot=slot,
                    mood_name=mood,
                    serious=serious,
                    priority=self._rhythm_voice_priority(role="main", kind="resp", perf=perf, engine=engine),
                    kind="resp",
                    coh_hint_text=str(pr.get("call_transcript") or ""),
                    coh_anchor_words=list(self._bar_ctx.get("anchor_words") or []),
                )
                self._log(engine, kind="resp", speaker=responder, intent=resp_intent, mood=mood, slot=slot, extra=ev)
                try:
                    tr = str((ev or {}).get("transcript") or "")
                    if tr:
                        self._last_transcript[str(responder).upper()] = tr
                    self._last_main_intent[str(responder).upper()] = str(resp_intent)
                except Exception:
                    pass
                self._pending_response = None

            elif plan == "RESP" and self._pending_response is None:
                # If we don't have a queued response (eg. late-start, bar skip),
                # treat this as a new call so the bar doesn't go silent.
                caller = str(self._bar_ctx.get("caller") or self._leader_speaker(engine))
                self._last_caller = caller
                call_intent = str(self._bar_ctx.get("call_intent") or intent or "TEASE")
                if self._fiend_smooth and self._is_fiend(caller):
                    call_intent = self._fiend_intent(call_intent, perf)
                ev = self._try_play_rhythm_voice(
                    engine,
                    am,
                    speaker=caller,
                    role="main",
                    intent=call_intent,
                    slot=slot,
                    mood_name=mood,
                    serious=serious,
                    priority=self._rhythm_voice_priority(role="main", kind="call_fallback", perf=perf, engine=engine),
                    kind="call_fallback",
                    coh_hint_text=str(self._last_transcript.get(str(self._other(caller)).upper(), "") or ""),
                    coh_anchor_words=list(self._bar_ctx.get("anchor_words") or []),
                )
                self._log(engine, kind="call_fallback", speaker=caller, intent=call_intent, mood=mood, slot=slot, extra=ev)
                try:
                    tr = str((ev or {}).get("transcript") or "")
                    if tr:
                        self._last_transcript[str(caller).upper()] = tr
                    self._last_main_intent[str(caller).upper()] = str(call_intent)
                except Exception:
                    pass


        # ── Micro-script events (script-like 3–6 beat mini-scenes)
        # These are deterministic placements for roles, constrained by fill-grid + safety rules.
        ran_roles: set[str] = set()
        try:
            evs = list(self._micro_plan.get(int(slot), []) or [])
        except Exception:
            evs = []
        for spec in evs:
            try:
                role = str(spec.get("role", "") or "")
                if not role:
                    continue
                # Role-level guardrails
                # Resolve intended intent early (for serious filtering)
                ev_intent = str(spec.get("intent") or intent or "TEASE")
                if serious and role in ("interrupt", "prefix", "wild"):
                    continue
                if serious and role in ("murmur", "suffix", "gesture"):
                    # In serious beats, allow only soft/grounding physicalities.
                    if str(ev_intent).upper() not in ("AFTERCARE", "GROUND", "GESTURE_BREATH", "PHYSICAL"):
                        continue
                p = float(spec.get("p", 1.0) or 1.0)
                if p < 1.0 and random.random() > _clamp(p, 0.0, 1.0):
                    continue

                # Cooldowns per role (prevents stacking if bar plan repeats)
                cd = 0.45 if role == "murmur" else (1.25 if role == "interrupt" else 0.85)
                if not self._cooldown_ok(f"micro_{role}", now, seconds=cd):
                    continue

                # Choose speaker for this role
                sp_spec = str(spec.get("speaker", "OTHER") or "OTHER").upper()
                caller = str(self._bar_ctx.get("caller") or self._last_caller or self._leader_speaker(engine))
                responder = str(self._bar_ctx.get("responder") or self._other(caller))
                if sp_spec == "CALLER":
                    speaker = caller
                elif sp_spec == "RESPONDER":
                    speaker = responder
                elif sp_spec == "OTHER":
                    speaker = self._other(caller)
                else:
                    speaker = sp_spec
                if self._fiend_smooth and self._is_fiend(speaker):
                    ev_intent = self._fiend_intent(ev_intent, perf)
                # Extra guards for interrupt
                if role == "interrupt" and (perf.stressed or perf.miss_streak > 0 or perf.intensity01 < 0.42):
                    continue

                ev = self._try_play_rhythm_voice(
                    engine,
                    am,
                    speaker=speaker,
                    role=role,
                    intent=ev_intent,
                    slot=slot,
                    mood_name=mood,
                    serious=False,
                    priority=self._rhythm_voice_priority(role=role, kind=f"micro_{role}", perf=perf, engine=engine),
                    kind=f"micro_{role}",
                    allow_queue=False,
                )
                ran_roles.add(role)
                self._log(engine, kind=f"micro_{role}", speaker=speaker, intent=ev_intent, mood=mood, slot=slot, extra=ev)
                try:
                    if isinstance(ev, dict) and ev.get("clip"):
                        extras_this_slot += 1
                        if self._cascade_guard:
                            self._bar_extra[str(role)] = int(self._bar_extra.get(str(role),0)) + 1
                except Exception:
                    pass
            except Exception:
                continue


        # Underlay murmurs: subtle texture, only on allowed grid slots.
        if ('murmur' not in ran_roles) and (slot in allowed_underlay) and perf.calm01 > 0.28 and (not serious) and (not perf.stressed):
            # Reduce density during recovery; boost slightly on long hit streaks.
            base = 0.07 + 0.14 * perf.intensity01
            if perf.hit_streak >= 6:
                base += 0.04
            if perf.event in ("MISS", "BREAK"):
                base *= 0.35
            rate = _clamp(base * float(getattr(self, '_underlay_mult', 1.0) or 1.0), 0.0, 0.45)
            # Cascade guard: avoid stacking too many extras in a single slot/bar.
            if self._cascade_guard:
                if extras_this_slot >= max_extras_per_slot:
                    return
                try:
                    n = _get_noise_0_100()
                    t = int(getattr(self, "_cascade_tightness", 70) or 70)
                    cap = 2 if n >= 60 else 1
                    if t >= 70:
                        cap = 1
                    elif t <= 30 and n >= 60:
                        cap = 3
                    if int(self._bar_extra.get("murmur",0)) >= int(cap):
                        return
                except Exception:
                    if int(self._bar_extra.get("murmur",0)) >= (2 if _get_noise_0_100() >= 60 else 1):
                        return
            if random.random() < rate and self._cooldown_ok("murmur", now, seconds=0.50):
                # Reaction intent: misses get grounding, perfects get a teasing lift.
                mur_int = "GROUND" if perf.event in ("MISS", "BREAK") else ("TEASE" if perf.event == "PERFECT" else intent)
                other = self._other(self._last_caller or self._leader_speaker(engine))
                if self._fiend_smooth and self._is_fiend(other):
                    mur_int = self._fiend_intent(mur_int, perf)
                ev = self._try_play_rhythm_voice(
                    engine,
                    am,
                    speaker=other,
                    role="murmur",
                    intent=mur_int,
                    slot=slot,
                    mood_name=mood,
                    serious=False,
                    priority=self._rhythm_voice_priority(role="murmur", kind="murmur", perf=perf, engine=engine),
                    kind="murmur",
                    allow_queue=False,
                )
                self._log(engine, kind="murmur", speaker=other, intent=mur_int, mood=mood, slot=slot, extra=ev)
                try:
                    if isinstance(ev, dict) and ev.get("clip"):
                        extras_this_slot += 1
                        if self._cascade_guard:
                            self._bar_extra["murmur"] = int(self._bar_extra.get("murmur",0)) + 1
                except Exception:
                    pass

        # Interrupts: ONLY in non-serious escalation, never during recovery.
        if (
            ('interrupt' not in ran_roles)
            and (slot in allowed_interrupt)
            and (not serious)
            and (not perf.stressed)
            and perf.miss_streak == 0
            and perf.intensity01 > 0.42
            and perf.combo01 > 0.25
            and str(intent).upper() in ("ESCALATE", "FRENZY")
        ):
            # Let perfect streaks encourage playful cut-ins.
            rate = 0.03 + 0.07 * perf.combo01 + (0.03 if perf.perfect_streak >= 2 else 0.0)
            if self._cascade_guard:
                if extras_this_slot >= max_extras_per_slot:
                    return
                # never more than one interrupt every 2 bars
                try:
                    if int(bar) - int(self._last_interrupt_bar) < 2:
                        return
                except Exception:
                    pass
            if random.random() < _clamp(rate, 0.0, 0.18) and self._cooldown_ok("interrupt", now, seconds=1.25):
                speaker = self._other(self._last_caller or self._leader_speaker(engine))
                int_intent = "TEASE" if perf.event == "PERFECT" else intent
                ev = self._try_play_rhythm_voice(
                    engine,
                    am,
                    speaker=speaker,
                    role="interrupt",
                    intent=int_intent,
                    slot=slot,
                    mood_name=mood,
                    serious=False,
                    priority=self._rhythm_voice_priority(role="interrupt", kind="interrupt", perf=perf, engine=engine),
                    kind="interrupt",
                    allow_queue=False,
                )
                self._log(engine, kind="interrupt", speaker=speaker, intent=int_intent, mood=mood, slot=slot, extra=ev)
                try:
                    if isinstance(ev, dict) and ev.get("clip"):
                        extras_this_slot += 1
                        if self._cascade_guard:
                            self._bar_extra["interrupt"] = int(self._bar_extra.get("interrupt",0)) + 1
                            self._last_interrupt_bar = int(bar)
                except Exception:
                    pass

        # Suffix tags: bar tail or configured suffix slot(s).
        if ('suffix' not in ran_roles) and (slot in allowed_suffix) and (not serious) and self._cooldown_ok("suffix", now, seconds=0.85):
            if self._cascade_guard:
                if extras_this_slot >= max_extras_per_slot:
                    return
                try:
                    n = _get_noise_0_100()
                    t = int(getattr(self, "_cascade_tightness", 70) or 70)
                    cap = 2 if n >= 60 else 1
                    if t >= 70:
                        cap = 1
                    elif t <= 30 and n >= 60:
                        cap = 3
                    if int(self._bar_extra.get("suffix",0)) >= int(cap):
                        return
                except Exception:
                    if int(self._bar_extra.get("suffix",0)) >= (2 if _get_noise_0_100() >= 60 else 1):
                        return
            if random.random() < (0.06 + 0.08 * perf.intensity01) and (not perf.stressed):
                speaker = self._other(self._last_caller or self._leader_speaker(engine))
                suf_int = "AFTERCARE" if perf.intensity01 < 0.25 else intent
                if self._fiend_smooth and self._is_fiend(speaker):
                    suf_int = self._fiend_intent(suf_int, perf)
                ev = self._try_play_rhythm_voice(
                    engine,
                    am,
                    speaker=speaker,
                    role="suffix",
                    intent=suf_int,
                    slot=slot,
                    mood_name=mood,
                    serious=False,
                    priority=self._rhythm_voice_priority(role="suffix", kind="suffix", perf=perf, engine=engine),
                    kind="suffix",
                    allow_queue=False,
                )
                self._log(engine, kind="suffix", speaker=speaker, intent=suf_int, mood=mood, slot=slot, extra=ev)
                try:
                    if isinstance(ev, dict) and ev.get("clip"):
                        extras_this_slot += 1
                        if self._cascade_guard:
                            self._bar_extra["suffix"] = int(self._bar_extra.get("suffix",0)) + 1
                except Exception:
                    pass

    def _log(self, engine: Any, *, kind: str, speaker: str, intent: str, mood: str, slot: int, extra: Any) -> None:
        if not self._log_enabled:
            return
        try:
            if self._log_path is None:
                # Default: per-session file beside saves (or cwd).
                base = Path(getattr(engine, "save_dir", ".") or ".")
                base.mkdir(parents=True, exist_ok=True)
                self._log_path = base / f"radio_play_{int(time.time())}.jsonl"
            if self._log_fh is None:
                self._log_fh = open(self._log_path, "a", encoding="utf-8")
            payload = {
                "t": round(time.time(), 3),
                "kind": str(kind),
                "speaker": str(speaker),
                "intent": str(intent),
                "mood": str(mood),
                "slot": int(slot),
            }
            if isinstance(extra, dict):
                payload.update({"clip": extra.get("clip"), "transcript": extra.get("transcript"), "tags": extra.get("tags")})
            self._log_fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
            self._log_fh.flush()
        except Exception:
            # logging must never break gameplay
            return
