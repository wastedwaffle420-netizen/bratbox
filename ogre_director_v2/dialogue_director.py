from __future__ import annotations
from dataclasses import dataclass, field
from typing import Deque, List, Optional, Tuple, Dict, Any
from collections import deque
import time
import os

from mood_profiles import get_mood

@dataclass
class QueuedUtterance:
    kind: str          # 'bark' | 'line'
    speaker: str       # BIRDSONG | FIEND | NARRATOR
    text: str
    meta: Dict[str, Any] = field(default_factory=dict)  # optional semantic metadata for voice selection
    ttl: float = 2.0    # suggested on-screen duration (seconds)
    created_t: float = 0.0
    interrupt: bool = False  # if True, should cut in over current voice

class DialogueDirector:
    """
    Rhythm-safe dialogue scheduler.

    V3 (crosstalk):
    - Tight chaining (very small inter-release gap).
    - "Barks" are allowed to interrupt (cut in), producing overlapping/interrupt-y banter feel.
    - Releases ONLY on safe windows: barlines and pause cue edges.
    - Never blocks the rhythm loop.
    """
    def __init__(self, beats_per_bar: int = 4):
        self.beats_per_bar = max(2, int(beats_per_bar))
        self._beat_phase = 0.0     # continuous beats
        self._last_beat_i = 0
        self._bar_index = 0

        self.pause_active = False
        self._last_pause_active = False

        self._q_barks: Deque[QueuedUtterance] = deque()
        self._q_lines: Deque[QueuedUtterance] = deque()

        # Governor
        self.min_gap_s = 0.0  # tighter conversational chaining      # tighter conversational chaining
        self._last_release_t = 0.0

        # Density estimation for ceiling BPM play
        self._hit_times: Deque[float] = deque(maxlen=64)
        self._density_hz = 0.0

        # Policies
        # Closed-box defaults come from the active mood.
        self._mood_name = "DUET_TEASE_LOOP"
        m = get_mood(self._mood_name)
        self.max_barks_per_bar = int(getattr(m, "max_barks_per_bar", 1) or 1)
        self._barks_this_bar = 0

        self._last_bark_t = 0.0

        self.bark_cooldown_s = float(getattr(m, "bark_cooldown_s", 0.38) or 0.38)
        self.allow_barks = bool(getattr(m, "allow_barks", True))

        # Back-compat overrides (only if explicitly set)
        try:
            if os.environ.get("LOCKKEY_MAX_BARKS_PER_BAR", "").strip():
                self.max_barks_per_bar = int(os.environ.get("LOCKKEY_MAX_BARKS_PER_BAR", "1") or 1)
            if os.environ.get("LOCKKEY_BARK_COOLDOWN_S", "").strip():
                self.bark_cooldown_s = float(os.environ.get("LOCKKEY_BARK_COOLDOWN_S", "0.38") or 0.38)
        except Exception:
            pass

    def set_mood(self, mood_name: str) -> None:
        """Apply a closed-box profile at runtime."""
        name = str(mood_name or "").strip().upper() or "DUET_TEASE_LOOP"
        self._mood_name = name
        m = get_mood(name)
        try:
            self.max_barks_per_bar = int(getattr(m, "max_barks_per_bar", 1) or 1)
            self.bark_cooldown_s = float(getattr(m, "bark_cooldown_s", 0.38) or 0.38)
            self.allow_barks = bool(getattr(m, "allow_barks", True))
        except Exception:
            pass
    def on_note_hit(self, *, real: bool, t: Optional[float] = None) -> None:
        if not real:
            return
        now = float(t if t is not None else time.time())
        self._hit_times.append(now)
        window = 1.25
        while self._hit_times and (now - self._hit_times[0]) > window:
            self._hit_times.popleft()
        self._density_hz = len(self._hit_times) / window

    def on_pause_cue(self, active: bool) -> None:
        self.pause_active = bool(active)

    def tick(self, dt: float, effective_bpm: float) -> Tuple[bool, bool, bool]:
        """
        Advance internal beat clock.
        Returns (barline_crossed, pause_edge, beat_crossed) where pause_edge means start/end changed this tick.
        """
        pause_edge = (self.pause_active != self._last_pause_active)
        self._last_pause_active = self.pause_active

        bpm = max(30.0, float(effective_bpm))
        self._beat_phase += float(dt) * (bpm / 60.0)
        beat_i = int(self._beat_phase)
        barline = False
        beat_crossed = False

        if beat_i != self._last_beat_i:
            beat_crossed = True
            self._last_beat_i = beat_i
            if (beat_i % self.beats_per_bar) == 0:
                barline = True
                self._bar_index += 1
                self._barks_this_bar = 0

        return barline, pause_edge, beat_crossed
        self._macro6_slot = 0
        self._macro6_last_ts = 0.0



    def suggest_voice_bundle(self, speaker: str, stage: str = "", lane: str = "") -> str:
        """6-part 'exchange macro' to bias voice texture without changing text.

        Returns a director bundle name (must exist in director_tag_bundles.json), or "".
        Resets after long gaps so the arc starts at 'gaze/hush' again.
        """
        try:
            s = (stage or "").strip().upper()
            if s in ("AFTERGLOW", "COOLDOWN"):
                return "SAFETY_SEAL"
            if s in ("EDGE", "FRENZY"):
                return "MUTUAL_MENACE"

            now = time.time()
            last = float(getattr(self, "_macro6_last_ts", 0.0) or 0.0)
            slot = int(getattr(self, "_macro6_slot", 0) or 0)
            if now - last > 8.0:
                slot = 0

            sp = (speaker or "").strip().upper()
            if slot == 0:
                bundle = "BIRD_SLOW_TRACE" if sp == "BIRD" else "FIEND_TAFFY_TIME"
            elif slot == 1:
                bundle = "MUTUAL_MENACE"
            elif slot == 2:
                bundle = "MUTUAL_MENACE" if sp == "FIEND" else "BIRD_SLOW_TRACE"
            elif slot == 3:
                bundle = "FIEND_TAFFY_TIME" if sp == "FIEND" else "MUTUAL_MENACE"
            elif slot == 4:
                bundle = "BIRD_SLOW_TRACE" if sp == "BIRD" else "FIEND_TAFFY_TIME"
            else:
                bundle = "SAFETY_SEAL"

            self._macro6_last_ts = now
            self._macro6_slot = (slot + 1) % 6
            return bundle
        except Exception:
            return ""

    def queue_bark(self, speaker: str, text: str, ttl: float = 1.0, meta: Optional[Dict[str, Any]] = None) -> None:
        self._q_barks.append(QueuedUtterance("bark", speaker, text, (meta or {}), float(ttl), time.time(), interrupt=True))

    def queue_line(self, speaker: str, text: str, ttl: float = 2.0, meta: Optional[Dict[str, Any]] = None) -> None:
        self._q_lines.append(QueuedUtterance("line", speaker, text, (meta or {}), float(ttl), time.time(), interrupt=False))

    def queue_event(self, event: Dict[str, Any], ttl: float = 2.0, interrupt: bool = False) -> None:
        """Queue a rich event payload: {speaker,text,meta}. Back-compat with text-only callers."""
        try:
            sp = str(event.get('speaker', '') or '')
            tx = str(event.get('text', '') or '')
            meta = event.get('meta', None)
        except Exception:
            sp, tx, meta = '', '', None
        if interrupt:
            self.queue_bark(sp, tx, ttl=float(ttl), meta=meta)
        else:
            self.queue_line(sp, tx, ttl=float(ttl), meta=meta)


    def _can_release_now(self) -> bool:
        return (time.time() - self._last_release_t) >= self.min_gap_s

    def try_release(self, *, barline: bool, pause_edge: bool, beat_crossed: bool = False) -> List[QueuedUtterance]:
        """
        Release policy (crosstalk V1):
        - On pause cue edges: allow up to 2 releases (line + bark).
        - On barline: allow up to 2 barks and one line if density is calm.
        """
        out: List[QueuedUtterance] = []
        if not self._can_release_now():
            return out

        def emit_one(q: Deque[QueuedUtterance]) -> None:
            if not q:
                return
            u = q[0]
            if u.kind == "bark":
                if not getattr(self, "allow_barks", True):
                    return
                now = time.time()
                if (now - self._last_bark_t) < self.bark_cooldown_s:
                    return
                self._last_bark_t = now
            out.append(q.popleft())

        # GRINDER MODE: dump everything instantly
        while self._q_barks:
            emit_one(self._q_barks)

        while self._q_lines:
            emit_one(self._q_lines)


        if out:
            self._last_release_t = time.time()
        return out
