"""
texture_reward.py
MACRO6 reactive tag-request emitter.

- Called frequently from gameplay (safe; does nothing most frames)
- Tracks streak/cooldown, advances MACRO6 slots earnestly
- Writes voice_tag_request.json into the voice cache dir so voice_engine can read it

This file is intentionally tiny + self-contained.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

# ----------------------------
# Config (env overrides)
# ----------------------------
DEFAULT_COOLDOWN_S = float(os.environ.get("LOCKKEY_TEXTURE_REWARD_COOLDOWN_S", "6.0"))
FLOW_COOLDOWN_S = float(os.environ.get("LOCKKEY_TEXTURE_REWARD_FLOW_COOLDOWN_S", "3.0"))
STATE_FILENAME = os.environ.get("LOCKKEY_TEXTURE_REWARD_STATE_FILE", "texture_reward_state.json")
REQUEST_FILENAME = os.environ.get("LOCKKEY_DIRECTOR_TAG_REQUEST_FILE", "voice_tag_request.json")

# how many "quality hits" before we allow slot advance attempts
MIN_COMBO_FOR_REWARD = int(os.environ.get("LOCKKEY_TEXTURE_REWARD_MIN_COMBO", "4"))
COMBO_STEP = int(os.environ.get("LOCKKEY_TEXTURE_REWARD_COMBO_STEP", "5"))  # 4-6 feels good

# if we detect a fresh mistake, drop to AFTERGLOW for a moment
MISTAKE_GRACE_S = float(os.environ.get("LOCKKEY_TEXTURE_REWARD_MISTAKE_GRACE_S", "7.0"))

LANES = ("AFTERGLOW", "MENACE", "TAFFY", "TRACE")

def _now() -> float:
    return time.time()

def _safe_int(x: Any, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        return default

def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default

def _safe_bool(x: Any) -> bool:
    return bool(x)

@dataclass
class RewardState:
    last_emit_ts: float = 0.0
    lane: str = "AFTERGLOW"
    slot: int = 1
    streak: int = 0
    last_combo: int = 0
    last_slips: int = 0
    last_mishaps: int = 0
    mistake_grace_until: float = 0.0

_STATE: Dict[str, RewardState] = {}  # keyed by cache_dir

# ----------------------------
# Bundles (must match director_tag_bundles.json)
# ----------------------------
_MAIN_BUNDLE = {
    "AFTERGLOW": "AFTERGLOW_SAFETY_SEAL",
    "MENACE": "MUTUAL_MENACE",
    "TAFFY": "FIEND_TAFFY_TIME",
    "TRACE": "BIRD_SLOW_TRACE",
}

_SLOT_NAME = {
    1: "GAZE",
    2: "LAUGH",
    3: "DEEP_TEASE",
    4: "POUT_WORSHIP",
    5: "RECIPROCITY",
    6: "MATURE",
}

def _macro6_bundle(lane: str, slot: int) -> str:
    lane = lane if lane in LANES else "AFTERGLOW"
    slot = max(1, min(6, int(slot)))
    return f"MACRO6_{lane}_{slot}_{_SLOT_NAME.get(slot,'GAZE')}"

def _choose_lane(vibe: Any, nscl: Any, round_state: Any, st: RewardState) -> str:
    """
    Lane selection = 'what is the current flavor of intimacy play?'
    Conservative rules:
      - if consent/amber flags: AFTERGLOW
      - else prefer TRACE for quiet, MENACE for bratty/playful, TAFFY for deep flow
    """
    # 1) Safety / amber override
    try:
        consent = ""
        if nscl is not None and hasattr(nscl, "state") and isinstance(nscl.state, dict):
            consent = str(nscl.state.get("CONSENT", "")).upper()
        if consent in ("AMBER", "RED"):
            return "AFTERGLOW"
    except Exception:
        pass

    # 2) mistake grace = calm the system
    now = _now()
    if now < st.mistake_grace_until:
        return "AFTERGLOW"

    # 3) lane hints from NSCL
    try:
        lane = ""
        lead = ""
        if nscl is not None and hasattr(nscl, "state") and isinstance(nscl.state, dict):
            lane = str(nscl.state.get("LANE", "")).lower()
            lead = str(nscl.state.get("LEAD", "")).lower()
        # quiet/slow trace
        if "quiet" in lane or "hush" in lane:
            return "TRACE"
        # needy/aftercare
        if "needy" in lane or "after" in lane or "warm" in lane:
            return "AFTERGLOW"
        # bratty / playful
        if "brat" in lane or "tease" in lane or "play" in lane:
            return "MENACE"
        # lead hints
        if "fiend" in lead and _safe_bool(getattr(vibe, "in_flow", False)):
            return "TAFFY"
        if "bird" in lead and _safe_bool(getattr(vibe, "in_flow", False)):
            return "TRACE"
    except Exception:
        pass

    # 4) flow heuristics
    in_flow = _safe_bool(getattr(vibe, "in_flow", False))
    depth = _safe_float(getattr(vibe, "depth", 0.0))
    comp = _safe_float(getattr(round_state, "composure", 0.0))
    power = _safe_float(getattr(vibe, "power_dynamic", 0.0))
    if in_flow and depth >= 0.65:
        # deep flow: if comp is strong, allow TAFFY; else keep TRACE for clarity
        return "TAFFY" if comp >= 0.55 else "TRACE"
    if power >= 0.55:
        return "MENACE"
    if depth >= 0.45:
        return "TRACE"
    return "AFTERGLOW"

def _target_slot(vibe: Any, round_state: Any, lane: str) -> int:
    """
    Target slot based on earned rhythm consistency.
    Slots:
      1 gaze
      2 laugh
      3 deep tease
      4 pout/worship
      5 reciprocity
      6 mature/correction
    """
    combo = _safe_int(getattr(vibe, "combo", 0))
    depth = _safe_float(getattr(vibe, "depth", 0.0))
    comp = _safe_float(getattr(round_state, "composure", 0.0))

    # baseline from combo
    slot = 1 + max(0, (combo - MIN_COMBO_FOR_REWARD) // max(1, COMBO_STEP))
    # depth & composure can gently nudge up (never more than +1)
    if depth >= 0.80 and comp >= 0.70:
        slot += 1
    # safety lane shouldn't jump too far
    if lane == "AFTERGLOW":
        slot = min(slot, 4)
        # if composure dropping, force slot 6 sometimes (gentle correction)
        if comp < 0.35:
            slot = 6
    return max(1, min(6, int(slot)))

def _cooldown_s(vibe: Any) -> float:
    in_flow = _safe_bool(getattr(vibe, "in_flow", False))
    combo = _safe_int(getattr(vibe, "combo", 0))
    if in_flow and combo >= 8:
        return FLOW_COOLDOWN_S
    return DEFAULT_COOLDOWN_S

def _get_cache_dir(engine: Any) -> str:
    # Prefer live audio manager cache dir (matches voice_engine search path)
    try:
        from voice_engine import get_audio_manager
        am = get_audio_manager()
        if am is not None and getattr(am, "cache_dir", None):
            return str(am.cache_dir)
    except Exception:
        pass
    # Fallback: game root
    try:
        return os.getcwd()
    except Exception:
        return "."

def _state_path(cache_dir: str) -> str:
    return os.path.join(cache_dir, STATE_FILENAME)

def _request_path(cache_dir: str) -> str:
    return os.path.join(cache_dir, REQUEST_FILENAME)

def _load_state(cache_dir: str) -> RewardState:
    st = _STATE.get(cache_dir)
    if st is not None:
        return st
    st = RewardState()
    # best-effort restore from disk (optional)
    try:
        p = _state_path(cache_dir)
        if os.path.exists(p):
            data = json.loads(open(p, "r", encoding="utf-8").read())
            st.last_emit_ts = _safe_float(data.get("last_emit_ts", 0.0))
            st.lane = str(data.get("lane", "AFTERGLOW"))
            st.slot = _safe_int(data.get("slot", 1))
            st.streak = _safe_int(data.get("streak", 0))
            st.last_combo = _safe_int(data.get("last_combo", 0))
            st.last_slips = _safe_int(data.get("last_slips", 0))
            st.last_mishaps = _safe_int(data.get("last_mishaps", 0))
            st.mistake_grace_until = _safe_float(data.get("mistake_grace_until", 0.0))
    except Exception:
        pass
    _STATE[cache_dir] = st
    return st

def _save_state(cache_dir: str, st: RewardState) -> None:
    _STATE[cache_dir] = st
    try:
        os.makedirs(cache_dir, exist_ok=True)
        with open(_state_path(cache_dir), "w", encoding="utf-8") as f:
            json.dump({
                "last_emit_ts": st.last_emit_ts,
                "lane": st.lane,
                "slot": st.slot,
                "streak": st.streak,
                "last_combo": st.last_combo,
                "last_slips": st.last_slips,
                "last_mishaps": st.last_mishaps,
                "mistake_grace_until": st.mistake_grace_until,
            }, f, indent=2)
    except Exception:
        pass

def _write_request(cache_dir: str, bundle: str, reason: str = "") -> None:
    try:
        os.makedirs(cache_dir, exist_ok=True)
        payload = {
            "bundle": bundle,
            # voice_engine will also accept explicit tags, but bundle keeps it simple
            "reason": reason,
            "ts": _now(),
        }
        with open(_request_path(cache_dir), "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    except Exception:
        pass

def maybe_emit_texture_reward(engine: Any) -> None:
    """
    Call this from gameplay. It will sometimes emit a tag bundle request.
    """
    try:
        vibe = getattr(engine, "vibe", None)
        round_state = getattr(engine, "round_state", None)
        nscl = getattr(engine, "nscl", None)
        if vibe is None or round_state is None:
            return

        cache_dir = _get_cache_dir(engine)
        st = _load_state(cache_dir)

        now = _now()
        combo = _safe_int(getattr(vibe, "combo", 0))
        slips = _safe_int(getattr(round_state, "slips", 0))
        mishaps = _safe_int(getattr(round_state, "mishaps", 0))

        # Detect fresh mistakes (punish = NO; we just switch to afterglow briefly)
        if slips > st.last_slips or mishaps > st.last_mishaps:
            st.mistake_grace_until = max(st.mistake_grace_until, now + MISTAKE_GRACE_S)

        lane = _choose_lane(vibe, nscl, round_state, st)
        target = _target_slot(vibe, round_state, lane)

        # Earned advancement only: never jump more than +1 per emission,
        # and lane switch resets slot to 1 (with a tiny forgiveness to 2 in-flow).
        if lane != st.lane:
            st.slot = 1
            st.streak = 0
        else:
            # keep within 1-step increments
            if target > st.slot:
                st.slot += 1
            elif target < st.slot:
                # gentle decay
                st.slot = max(1, st.slot - 1)

        st.lane = lane

        # Emit gating
        cooldown = _cooldown_s(vibe)
        if (now - st.last_emit_ts) < cooldown:
            # update counters only
            st.last_combo = combo
            st.last_slips = slips
            st.last_mishaps = mishaps
            _save_state(cache_dir, st)
            return

        # only emit if combo is moving or a safety event happened
        combo_progress = combo - st.last_combo
        safety_forced = (now < st.mistake_grace_until) or (lane == "AFTERGLOW" and st.slot in (5,6))
        should_emit = (combo >= MIN_COMBO_FOR_REWARD and combo_progress >= 3) or safety_forced

        if not should_emit:
            st.last_combo = combo
            st.last_slips = slips
            st.last_mishaps = mishaps
            _save_state(cache_dir, st)
            return

        bundle = _macro6_bundle(lane, st.slot)
        reason = f"lane={lane} slot={st.slot} combo={combo} depth={getattr(vibe,'depth',0.0):.2f}"
        _write_request(cache_dir, bundle=bundle, reason=reason)

        st.last_emit_ts = now
        st.last_combo = combo
        st.last_slips = slips
        st.last_mishaps = mishaps
        _save_state(cache_dir, st)
    except Exception:
        return

