
from __future__ import annotations
from dataclasses import dataclass, asdict
import time

PHASES = (
    "KISS_CAPTURE",
    "SIDE_CATCH",
    "HIP_PRESS_STRUGGLE",
    "COMMIT",
    "PRAISE",
    "COOPERATIVE_RHYTHM",
    "EXPLORATION_LOOP",
    "HIP_PRAISE",
    "IMPACT_OVUM_RELEASE",
    "TIGHTEN",
    "ARM_PULL",
    "FULL_BODY_CONTACT",
    "PRESSURE_BUILD",
    "LOCKED_GATE_SCARE",
    "OVUM_DROP",
    "POSE_BLOCK",
    "SEAL_ESTABLISHED",
    "LATERAL_DIVERSION",
    "MOVEMENT_GAMBIT",
    "GATE_OPEN",
    "PROLONGED_TERMINAL_HOLD",
    "RELEASE",
)

@dataclass
class DirectorState:
    phase: str = "KISS_CAPTURE"
    phase_index: int = 0
    progress: float = 0.0
    phase_progress: float = 0.0
    intensity: float = 0.0
    roleplay_resistance: float = 1.0
    cooperative: bool = False
    impact_release_armed: bool = False
    ovum_released: bool = False
    gate_locked: bool = True
    pose_block: bool = False
    seal_established: bool = False
    lateral_diversion: float = 0.0
    movement_risk: float = 0.0
    terminal_armed: bool = False
    terminal_committed: bool = False
    prolonged_hold: bool = False
    safeword: bool = False
    updated_at: float = 0.0

    def snapshot(self):
        d = asdict(self)
        d["updated_at"] = time.time()
        return d

class BratTamingDirector:
    """Adult-consensual performance director.

    The director describes staging/pacing only. "Resistance" here is authored,
    consensual roleplay. PANDORA is an immediate hard stop.
    """

    def __init__(self):
        self.state = DirectorState(updated_at=time.time())
        self._last_motion = 0.0
        self._still_time = 0.0
        self._impact_seen = False

    def safeword(self):
        s = self.state
        s.safeword = True
        s.phase = "RELEASE"
        s.phase_index = PHASES.index("RELEASE")
        s.phase_progress = 1.0
        s.roleplay_resistance = 0.0
        s.cooperative = False
        s.gate_locked = True
        s.pose_block = False
        s.seal_established = False
        s.lateral_diversion = 0.0
        s.movement_risk = 0.0
        s.terminal_armed = False
        s.terminal_committed = False
        s.prolonged_hold = False
        s.updated_at = time.time()

    def note_impact(self):
        if self.state.safeword:
            return
        self._impact_seen = True
        self.state.ovum_released = True
        self.state.impact_release_armed = False

    def arm_terminal(self):
        if not self.state.safeword:
            self.state.terminal_armed = True

    def tick(self, elapsed_sec: float, motion: float, fully_engaged: bool, impact: bool=False):
        s = self.state
        if s.safeword:
            return s

        p = max(0.0, min(1.0, elapsed_sec / 180.0))
        s.progress = p
        motion = max(0.0, min(1.0, float(motion)))

        if impact:
            self.note_impact()

        # authored phase thresholds, with the latter half intentionally slower
        # and more suspenseful than the opening.
        thresholds = [
            0.03, 0.07, 0.12, 0.16, 0.19, 0.28, 0.38, 0.43, 0.48, 0.54, 0.60,
            0.67, 0.73, 0.79, 0.84, 0.88, 0.91, 0.94, 0.965, 0.985, 0.997, 1.0
        ]
        idx = 0
        while idx < len(thresholds)-1 and p > thresholds[idx]:
            idx += 1

        # Impact release is a named mechanic: before the release beat, stay
        # armed; once impact is observed, advance naturally.
        if p >= 0.43 and not s.ovum_released:
            s.impact_release_armed = True
            idx = min(idx, PHASES.index("IMPACT_OVUM_RELEASE"))

        # POSE_BLOCK requires an actual stop in motion.
        if p >= 0.84:
            if motion < 0.08:
                self._still_time += 0.1
            else:
                self._still_time = max(0.0, self._still_time - 0.22)

            if self._still_time >= 0.7:
                s.pose_block = True
                s.seal_established = True
            if s.seal_established:
                # stillness strengthens diversion; resumed movement creates risk.
                if motion < 0.08:
                    s.lateral_diversion = min(1.0, s.lateral_diversion + 0.08)
                    s.movement_risk = max(0.0, s.movement_risk - 0.05)
                else:
                    s.movement_risk = min(1.0, s.movement_risk + 0.20)

            if s.seal_established and s.movement_risk >= 0.65 and fully_engaged and s.terminal_armed:
                s.pose_block = False
                s.seal_established = False
                s.terminal_committed = True
                s.gate_locked = False
                idx = max(idx, PHASES.index("GATE_OPEN"))

        s.phase_index = min(idx, len(PHASES)-1)
        s.phase = PHASES[s.phase_index]
        prev_t = 0.0 if s.phase_index == 0 else thresholds[s.phase_index-1]
        next_t = thresholds[s.phase_index]
        s.phase_progress = 1.0 if next_t <= prev_t else max(0.0, min(1.0, (p-prev_t)/(next_t-prev_t)))
        s.intensity = min(1.0, 0.18 + 0.82*p)

        # "brat" resistance is front-loaded; after COMMIT it becomes cooperative.
        if s.phase_index >= PHASES.index("COMMIT"):
            s.cooperative = True
            s.roleplay_resistance = max(0.0, 1.0 - (p-0.16)/0.18)
        else:
            s.cooperative = False
            s.roleplay_resistance = 1.0 - 0.25*p

        if s.phase == "HIP_PRAISE":
            s.impact_release_armed = True
        if s.phase == "GATE_OPEN":
            s.gate_locked = False
        elif not s.terminal_committed:
            s.gate_locked = True

        if s.terminal_committed and p >= 0.985:
            s.prolonged_hold = True
            s.phase = "PROLONGED_TERMINAL_HOLD"
            s.phase_index = PHASES.index("PROLONGED_TERMINAL_HOLD")

        self._last_motion = motion
        s.updated_at = time.time()
        return s
