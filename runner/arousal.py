#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
arousal.py — the hidden "fiend arousal" stat, director side.

Andrew asked for it straight: a private, single-player read on whether HE is
probably getting close IRL, inferred from his exact inputs — how long he
holds keys (key-repeat runs), press rate, rhythmicity of his tapping, which
keys, session build — plus optional mic energy (opt-in toggle in the web UI,
off by default).

This is behavioral, not mined from his writing. It never leaves the scene
runner. It exists so she can notice — and so finale mode can trigger.

Signals (all from input telemetry, $SESSION/input_telemetry.jsonl):
  - hold_runs: consecutive same-key repeats within 150ms = holding the key
    down. Longer cumulative hold-time per minute = deeper in it.
  - press_rate: presses/minute, EMA'd. Acceleration matters more than level.
  - rhythmicity: CV of inter-press intervals over the last 24 presses.
    Lower CV (steadier tapping) reads as entrainment.
  - surge_bias: fraction of presses that are surge-ish keys (space/enter).
  - voice: optional mic telemetry (opt-in toggle in the web UI, off by
    default). The browser sends two numbers only — broadband loudness and a
    vocalization score (tonal, above-the-noise-floor sounds: squeaks, gasps,
    moans). NO audio leaves the browser, NO transcription exists anywhere.
    She may react to the fact he made a sound — never to words, because she
    never receives any. His dialogue is his; not hers to hear.
  - session_build: slow integrator, + while active, decays when idle.

Peak honesty rule: `peak` requires MEANINGFUL input (a keypress, or real
sound above the noise floor) within the last 60s. Session time alone can
never peak — no getting off an empty chair.

Score 0..100. States: cool <35, warming 35-60, close 60-85, peak >85.
peak_ready: peak sustained 15s + consent GREEN + tier>=1 + 10-min cooldown.
"""
from __future__ import annotations

import math
import time


class ArousalModel:
    def __init__(self):
        self.t0 = time.time()
        self.press_times: list[float] = []   # recent press timestamps
        self.hold_ms_total = 0.0             # cumulative hold time, decayed
        self._last_key = None
        self._last_t = 0.0
        self._run_start = 0.0               # start of current repeat run
        self._run_key = None
        self.rate_ema = 0.0                  # presses per minute
        self.voice_ema = 0.0
        self.voice_on = False
        self.vocal_ema = 0.0                 # vocalization intensity 0..1
        self.vocal_heat = 0.0                # squeak pulses, 0..20, decays
        self._vocal_prev = 0.0
        self.squeaks: list[float] = []       # recent squeak-pulse timestamps
        self.last_meaningful_t = 0.0         # last keypress or real sound
        self._last_update = time.time()
        self.slow = 0.0                      # session build 0..40
        self.score = 0.0
        self.state = "cool"
        self._peak_since = 0.0
        self._last_finale_at = 0.0
        self.last_input_t = 0.0
        self.quiet_s = 0.0

    # ── inputs ──────────────────────────────────────────────────────────

    def observe_key(self, t: float, key: str):
        self.last_input_t = t
        self.last_meaningful_t = t   # a keypress is always him, really here
        self.press_times.append(t)
        # keep 90s window
        cutoff = t - 90.0
        while self.press_times and self.press_times[0] < cutoff:
            self.press_times.pop(0)
        # repeat-run detection: same key within 150ms = holding
        if key == self._run_key and (t - self._last_t) < 0.15:
            pass  # continue run
        else:
            if self._run_key is not None and self._run_start:
                held = (self._last_t - self._run_start) * 1000.0
                if held > 120:
                    self.hold_ms_total += held
            self._run_key = key
            self._run_start = t
        self._last_key = key
        self._last_t = t
        # rate EMA (per-minute)
        inst = 60.0 / max(0.2, t - (self.press_times[-2] if len(self.press_times) > 1 else t - 1.0))
        a = 0.12
        self.rate_ema = (1 - a) * self.rate_ema + a * min(inst, 240.0)
        # slow build while active
        self.slow = min(40.0, self.slow + 0.35)

    def observe_voice(self, t: float, energy: float, vocal: float = 0.0):
        """Mic telemetry: energy = broadband loudness 0..1, vocal = tonal
        vocalization score 0..1 (squeaks/gasps above the noise floor)."""
        self.voice_on = True
        self.last_input_t = t
        e = max(0.0, min(1.0, energy))
        v = max(0.0, min(1.0, vocal))
        a = 0.25
        self.voice_ema = (1 - a) * self.voice_ema + a * e
        self.vocal_ema = (1 - 0.35) * self.vocal_ema + 0.35 * v
        # real sound counts as him being here
        if e > 0.18 or v > 0.35:
            self.last_meaningful_t = t
        # squeak pulse: rising edge over the vocal threshold
        if v >= 0.35 and self._vocal_prev < 0.35:
            self.vocal_heat = min(20.0, self.vocal_heat + 6.0)
            self.squeaks.append(t)
        self._vocal_prev = v

    def _rhythmicity(self) -> float:
        """0..1 — steadiness of his tapping over recent presses."""
        ts = self.press_times[-24:]
        if len(ts) < 6:
            return 0.0
        iv = [b - a for a, b in zip(ts, ts[1:]) if 0.05 < (b - a) < 5.0]
        if len(iv) < 5:
            return 0.0
        mean = sum(iv) / len(iv)
        var = sum((x - mean) ** 2 for x in iv) / len(iv)
        cv = math.sqrt(var) / max(0.05, mean)
        return max(0.0, min(1.0, 1.0 - cv / 1.2))

    # ── scoring ─────────────────────────────────────────────────────────

    def update(self, now: float | None = None) -> dict:
        now = now or time.time()
        dt = max(0.0, now - self._last_update)
        self._last_update = now
        idle = now - self.last_input_t if self.last_input_t else 999.0
        self.quiet_s = idle
        # decay holds and slow-build when idle
        if idle > 20.0:
            self.hold_ms_total *= 0.97
            self.slow = max(0.0, self.slow - 0.15)
            self.rate_ema *= 0.98
        # squeak heat decays on its own clock (~25s half-life)
        if dt > 0:
            self.vocal_heat *= 0.5 ** (dt / 25.0)
            if self.vocal_heat < 0.05:
                self.vocal_heat = 0.0
        # prune old squeak marks (keep 2 minutes)
        cutoff = now - 120.0
        while self.squeaks and self.squeaks[0] < cutoff:
            self.squeaks.pop(0)
        # close any dangling hold run
        if self._run_key is not None and idle > 0.5:
            held = (self._last_t - self._run_start) * 1000.0
            if held > 120:
                self.hold_ms_total += held
            self._run_key = None

        hold_score = min(30.0, self.hold_ms_total / 1000.0 * 2.0)   # ~15s held = 30
        rate_score = min(20.0, self.rate_ema / 120.0 * 20.0)        # 120/min = 20
        rhythm_score = self._rhythmicity() * 15.0
        voice_score = 0.0
        if self.voice_on:
            voice_score = min(25.0, self.voice_ema * 12.0
                              + self.vocal_ema * 12.0 + self.vocal_heat * 0.4)

        target = hold_score + rate_score + rhythm_score + voice_score + self.slow
        target = max(0.0, min(100.0, target))
        # ease toward target (rises fast, falls slow)
        if target > self.score:
            self.score += (target - self.score) * 0.25
        else:
            self.score += (target - self.score) * 0.06

        prev = self.state
        if self.score > 85:
            self.state = "peak"
        elif self.score > 60:
            self.state = "close"
        elif self.score > 35:
            self.state = "warming"
        else:
            self.state = "cool"

        # empty-chair rule: peak needs him actually here — a keypress or real
        # sound within the last 60s. Session time alone can never peak.
        if self.state == "peak" and (now - self.last_meaningful_t) > 60.0:
            self.state = "close"

        if self.state == "peak":
            if not self._peak_since:
                self._peak_since = now
        else:
            self._peak_since = 0.0
        return self.snapshot()

    def snapshot(self) -> dict:
        return {
            "arousal": round(self.score, 1),
            "state": self.state,
            "quiet_s": round(max(0.0, self.quiet_s), 1),
            "voice_on": self.voice_on,
            "vocal": round(self.vocal_ema, 2),
            "squeaks": len(self.squeaks),
        }

    def peak_ready(self, consent: str, tier: int, now: float | None = None) -> bool:
        now = now or time.time()
        if self.state != "peak":
            return False
        if not self._peak_since or (now - self._peak_since) < 15.0:
            return False
        if str(consent or "").upper() != "GREEN":
            return False
        if int(tier or 0) < 1:
            return False
        if now - self._last_finale_at < 600.0:
            return False
        return True

    def mark_finale(self, now: float | None = None):
        self._last_finale_at = now or time.time()
        self._peak_since = 0.0
