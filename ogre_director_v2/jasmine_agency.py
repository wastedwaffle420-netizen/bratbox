#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
jasmine_agency.py — her agency kit, game side.

Registers director action handlers on the DirectorLink singleton so Jasmine's
writer can spend her meter on moves that play back at Andrew:

  action keys:
    "move":     "buck"|"wiggle"|"arch"|"grind"|"clench"|"melt"|"present"|"shy"
                (or {"name": <move>, "hold": <s>})
    "tempo":    0.7  or  {"scale": 0.5-1.5, "for_s": <game seconds, default 45>}
    "chart":    {"nudge_ms": ±120, "cluster": 0-3, "ghost": 0-2}
    "lightmap": {"dim": 0.4-1.2, "bloom": bool, "flicker": bool, "for_s": <s>}
    "body":     {"sweat": 0-100, "musk": 0-100}
    "toot":     "bashful"|"submissive"|"power" (or true)

Every handler uses the game's own mechanisms (surge pose override, lightmap
renderer, rhythm notes, tactile overlay) and is wrapped so failures never
break the frame loop. The game's own locks outrank these exactly the way they
outrank the built-in pose/flash handlers: we only set the same override
fields the game's own beats set.

Timed effects (tempo revert, dim restore, flicker) tick inside a wrapper
around link.poll(), which the game calls once per frame.
"""
from __future__ import annotations

import sys
import time as _real_time

try:
    from jasmine_director_link import get_link
except Exception:
    get_link = None


# ── helpers ──────────────────────────────────────────────────────────────

def _clamp(v, lo, hi, default=None):
    try:
        f = float(v)
    except Exception:
        return default
    return max(lo, min(hi, f))


def _game_clock():
    """The module-level slowed clock (has .speed). Runs as __main__."""
    try:
        m = sys.modules.get("__main__")
        t = getattr(m, "time", None)
        if t is not None and hasattr(t, "speed"):
            return t
    except Exception:
        pass
    return None


def _game_now():
    c = _game_clock()
    try:
        return float(c.time()) if c is not None else _real_time.time()
    except Exception:
        return _real_time.time()


def _renderer(engine):
    return getattr(engine, "lightmap_renderer", None)


def _rhythm(engine):
    try:
        return getattr(getattr(engine, "scene", None), "rhythm", None)
    except Exception:
        return None


def _overlay(engine):
    try:
        return getattr(_renderer(engine), "tactile_overlay", None)
    except Exception:
        return None


# timed effect state, keyed simply (one scene at a time)
_timed = {
    "tempo_revert_at": 0.0,
    "dim_restore_at": 0.0,
    "dim_restore_to": 1.0,
    "flicker_until": 0.0,
}


# ── move ─────────────────────────────────────────────────────────────────

_MOVE_POSES = {
    "wiggle": "coy_cheek",
    "arch": "downward",
    "grind": "squat",
    "present": "front_presence",
}
_MOVE_HOLDS = {
    "wiggle": 2.5, "arch": 3.0, "grind": 4.0, "present": 3.0,
}


def _pose_pulse(engine, pose, hold):
    """Same mechanism the game's own surge beats use."""
    try:
        engine._surge_pose_override = pose
        engine._surge_pose_t = max(float(getattr(engine, "_surge_pose_t", 0.0) or 0.0), hold)
        r = _renderer(engine)
        if r is not None:
            r.set_pose(pose)
    except Exception:
        pass


def _h_move(engine, value, act):
    try:
        if isinstance(value, dict):
            name = str(value.get("name", "") or "").lower()
            hold = _clamp(value.get("hold"), 1.0, 8.0, None)
        else:
            name = str(value or "").lower()
            hold = None
        r = _renderer(engine)
        if name == "buck":
            # sudden surge toward him
            if r is not None:
                r.trigger_shake(0.45, 2.2)
                r.trigger_flash(2, 0.25)
        elif name == "wiggle":
            if r is not None:
                r.trigger_shake(0.8, 1.0)
                r.trigger_flash(2, 0.2)
            _pose_pulse(engine, _MOVE_POSES["wiggle"], hold or _MOVE_HOLDS["wiggle"])
        elif name == "arch":
            if r is not None:
                r.trigger_flash(2, 0.35)
            _pose_pulse(engine, _MOVE_POSES["arch"], hold or _MOVE_HOLDS["arch"])
        elif name == "grind":
            # slow roll; drags his notes off-beat a touch — he follows her
            _pose_pulse(engine, _MOVE_POSES["grind"], hold or _MOVE_HOLDS["grind"])
            if r is not None:
                r.set_dim(0.85)
            _timed["dim_restore_at"] = _game_now() + 5.0
            _timed["dim_restore_to"] = 1.0
            _h_chart(engine, {"nudge_ms": -45}, act)
        elif name == "clench":
            # sudden spike; hold through for the release bonus
            if r is not None:
                r.trigger_shake(0.4, 3.0)
                r.trigger_flash(2, 0.3)
                r.set_dim(0.7)
            _timed["dim_restore_at"] = _game_now() + 3.0
            _timed["dim_restore_to"] = 1.0
            _h_chart(engine, {"cluster": 2}, act)
        elif name == "melt":
            # she goes soft; chart thins in feel
            if r is not None:
                r.set_dim(0.9)
            _timed["dim_restore_at"] = _game_now() + 6.0
            _timed["dim_restore_to"] = 1.0
        elif name == "present":
            if r is not None:
                r.trigger_flash(2, 0.5)
                r.set_dim(1.0)
            _pose_pulse(engine, _MOVE_POSES["present"], hold or _MOVE_HOLDS["present"])
        elif name == "shy":
            # covers up; he coaxes her back
            if r is not None:
                r.set_dim(0.55)
            _timed["dim_restore_at"] = _game_now() + 6.0
            _timed["dim_restore_to"] = 1.0
        else:
            return
        try:
            engine._agency_last_move = name
            engine._agency_last_move_t = _game_now()
        except Exception:
            pass
    except Exception:
        pass


# ── tempo ────────────────────────────────────────────────────────────────

def _h_tempo(engine, value, act):
    try:
        clock = _game_clock()
        if clock is None:
            return
        if isinstance(value, dict):
            scale = _clamp(value.get("scale"), 0.5, 1.5, None)
            for_s = _clamp(value.get("for_s"), 5.0, 300.0, 45.0)
        else:
            scale = _clamp(value, 0.5, 1.5, None)
            for_s = 45.0
        if scale is None:
            return
        if not hasattr(clock, "_agency_base_speed"):
            try:
                clock._agency_base_speed = float(clock.speed)
            except Exception:
                return
        base = float(getattr(clock, "_agency_base_speed", 0.2) or 0.2)
        clock.speed = max(0.02, base * scale)
        _timed["tempo_revert_at"] = _game_now() + for_s
        try:
            engine._agency_tempo = scale
        except Exception:
            pass
    except Exception:
        pass


def _revert_tempo():
    try:
        clock = _game_clock()
        if clock is None:
            return
        base = getattr(clock, "_agency_base_speed", None)
        if base is not None:
            clock.speed = float(base)
    except Exception:
        pass


# ── chart ────────────────────────────────────────────────────────────────

def _actionable_notes(engine):
    out = []
    try:
        rhythm = _rhythm(engine)
        if rhythm is None:
            return out
        for n in list(getattr(rhythm, "notes", []) or []):
            if bool(getattr(n, "hit", False)) or bool(getattr(n, "missed", False)):
                continue
            if bool(getattr(n, "decoy", False)):
                continue
            out.append(n)
    except Exception:
        pass
    return out


def _h_chart(engine, value, act):
    try:
        if not isinstance(value, dict):
            return
        notes = _actionable_notes(engine)
        nudge_ms = _clamp(value.get("nudge_ms"), -120.0, 120.0, 0.0) or 0.0
        if nudge_ms and notes:
            delta = nudge_ms / 1000.0
            for n in notes[:12]:
                try:
                    n.spawn_time = float(getattr(n, "spawn_time", 0.0)) + delta
                except Exception:
                    pass
        cluster = int(_clamp(value.get("cluster"), 0, 3, 0) or 0)
        ghost = int(_clamp(value.get("ghost"), 0, 2, 0) or 0)
        for _ in range(cluster + ghost):
            try:
                fn = getattr(engine, "_rhythm_force_note_spawn", None)
                if callable(fn):
                    fn("jasmine_mischief")
                else:
                    break
            except Exception:
                break
        if ghost:
            # flag the freshest notes as her ghost flirts; the writer watches
            # the combo delta to see if he caught them
            try:
                fresh = _actionable_notes(engine)[-ghost:]
                for n in fresh:
                    n.ghost = True
                engine._agency_ghost_pending = int(getattr(engine, "_agency_ghost_pending", 0) or 0) + ghost
            except Exception:
                pass
    except Exception:
        pass


# ── lightmap ─────────────────────────────────────────────────────────────

def _h_lightmap(engine, value, act):
    try:
        if not isinstance(value, dict):
            return
        r = _renderer(engine)
        if r is None:
            return
        dim = _clamp(value.get("dim"), 0.4, 1.2, None)
        for_s = _clamp(value.get("for_s"), 2.0, 120.0, 8.0)
        if dim is not None:
            r.set_dim(dim)
            _timed["dim_restore_at"] = _game_now() + for_s
            _timed["dim_restore_to"] = 1.0
        if value.get("bloom"):
            try:
                r.trigger_flash(2, 0.5)
            except Exception:
                pass
        if value.get("flicker"):
            _timed["flicker_until"] = _game_now() + _clamp(value.get("for_s"), 2.0, 20.0, 6.0)
    except Exception:
        pass


# ── body ─────────────────────────────────────────────────────────────────

def _h_body(engine, value, act):
    try:
        if not isinstance(value, dict):
            return
        ov = _overlay(engine)
        if ov is None:
            return
        sweat = _clamp(value.get("sweat"), 0.0, 100.0, None)
        musk = _clamp(value.get("musk"), 0.0, 100.0, None)
        pose = str(getattr(ov, "pose", "") or "")
        if sweat is not None and pose:
            try:
                heat = getattr(ov, "pose_heat", {})
                heat[pose] = max(float(heat.get(pose, 0.0) or 0.0), sweat / 100.0)
            except Exception:
                pass
        if musk is not None:
            try:
                ov.musk_enabled = True
                if musk > 40:
                    ov.musk_credit = max(float(getattr(ov, "musk_credit", 0.0) or 0.0),
                                        musk / 100.0 * 2.0)
            except Exception:
                pass
    except Exception:
        pass


def _h_toot(engine, value, act):
    """Force a pressure event soon, in her chosen flavor."""
    try:
        ov = _overlay(engine)
        if ov is None:
            return
        flavor = str(value or "").lower()
        if flavor not in ("bashful", "submissive", "power"):
            flavor = "bashful"
        try:
            ov.musk_enabled = True
            now = _game_now()
            # perf_counter-based clock; schedule the event ~2s out
            import time as _rt
            try:
                pc = _game_clock()
                now_pc = float(pc.perf_counter()) if pc is not None else _rt.perf_counter()
            except Exception:
                now_pc = _rt.perf_counter()
            pose = str(getattr(ov, "pose", "") or "")
            if pose:
                nd = getattr(ov, "toot_next_by_pose", None)
                if isinstance(nd, dict):
                    nd[pose] = now_pc + 2.0
            # make sure heat is high enough for it to actually fire
            heat = getattr(ov, "pose_heat", {})
            if pose and isinstance(heat, dict):
                heat[pose] = max(float(heat.get(pose, 0.0) or 0.0), 0.75)
            engine._agency_toot_flavor = flavor
            engine._agency_toot_t = now
            try:
                ov._agency_toot_flavor = flavor
            except Exception:
                pass
        except Exception:
            pass
    except Exception:
        pass


# ── pout ─────────────────────────────────────────────────────────────────

def _h_pout(engine, value, act):
    """She's pouting: dims, crosses arms (coy_cheek), withholds herself."""
    if value is False:
        # explicit release — she broke the pout herself, lift it now
        try:
            _timed["pout_until"] = 0.0
            r = _renderer(engine)
            if r is not None:
                r.set_dim(1.0)
            engine._agency_pouting = False
        except Exception:
            pass
        return
    try:
        dur = 20.0
        if isinstance(value, dict):
            dur = _clamp(value.get("for_s"), 5.0, 60.0, 20.0)
        r = _renderer(engine)
        if r is not None:
            r.set_dim(0.5)
        _pose_pulse(engine, "coy_cheek", min(dur, 8.0))
        _timed["pout_until"] = _game_now() + dur
        _timed["dim_restore_at"] = _game_now() + dur
        _timed["dim_restore_to"] = 1.0
        try:
            engine._agency_pouting = True
        except Exception:
            pass
    except Exception:
        pass


# ── halftime ─────────────────────────────────────────────────────────────

def _h_halftime(engine, value, act):
    """She hijacks the chart: notes pause, she runs a chained move combo."""
    try:
        for_s = 10.0
        if isinstance(value, dict):
            for_s = _clamp(value.get("for_s"), 5.0, 20.0, 10.0)
        now = _game_now()
        engine._agency_halftime_until = now + for_s
        # chain three moves across the window
        moves = ["wiggle", "arch", "present"]
        try:
            engine._agency_halftime_moves = [(now + for_s * (i + 0.5) / 3.0, m)
                                             for i, m in enumerate(moves)]
        except Exception:
            pass
        r = _renderer(engine)
        if r is not None:
            try:
                r.trigger_flash(2, 0.6)
            except Exception:
                pass
    except Exception:
        pass


# ── hijack ───────────────────────────────────────────────────────────────

def _h_hijack(engine, value, act):
    """His surge keys do HER bidding for a few seconds. Stolen surges tease."""
    try:
        for_s = 6.0
        if isinstance(value, dict):
            for_s = _clamp(value.get("for_s"), 3.0, 15.0, 6.0)
        engine._agency_hijack_until = _game_now() + for_s
        if not getattr(engine, "_agency_surge_wrapped", False):
            try:
                orig = engine._trigger_rhythm_surge  # bound

                def _stolen_surge():
                    try:
                        if _game_now() < float(getattr(engine, "_agency_hijack_until", 0.0) or 0.0):
                            r = _renderer(engine)
                            if r is not None:
                                r.trigger_shake(0.3, 1.6)
                                try:
                                    r.trigger_flash(2, 0.2)
                                except Exception:
                                    pass
                            engine._agency_hijack_stolen = int(
                                getattr(engine, "_agency_hijack_stolen", 0) or 0) + 1
                            return False
                    except Exception:
                        pass
                    return orig()

                engine._trigger_rhythm_surge = _stolen_surge
                engine._agency_surge_wrapped = True
            except Exception:
                pass
    except Exception:
        pass


# ── hiccup ───────────────────────────────────────────────────────────────

def _h_hiccup(engine, value, act):
    """She gets the hiccups: tiny screen jolts, devastating."""
    try:
        n = 3
        if isinstance(value, dict):
            n = int(_clamp(value.get("n"), 1, 6, 3) or 3)
        elif isinstance(value, (int, float)):
            n = int(_clamp(value, 1, 6, 3) or 3)
        now = _game_now()
        try:
            engine._agency_hiccups = [now + 0.4 + i * 0.65 for i in range(n)]
        except Exception:
            pass
    except Exception:
        pass


# ── weather ──────────────────────────────────────────────────────────────

_WEATHER = {
    # name: (dim, flicker_hz_or_0, shake_every_s_or_0)
    "sparkles": (1.12, 9.0, 0.0),
    "rain": (0.55, 2.2, 1.4),
    "ember": (0.95, 0.8, 0.0),
    "clear": (1.0, 0.0, 0.0),
}


def _h_weather(engine, value, act):
    """Room weather: her mood made visible. sparkles/rain/ember/clear."""
    try:
        name = str(value or "").lower()
        if isinstance(value, dict):
            name = str(value.get("kind", "") or "").lower()
            for_s = _clamp(value.get("for_s"), 10.0, 180.0, 60.0)
        else:
            for_s = 60.0
        if name not in _WEATHER:
            return
        dim, hz, shake_every = _WEATHER[name]
        r = _renderer(engine)
        if r is not None and name != "clear":
            r.set_dim(dim)
        _timed["weather"] = name
        _timed["weather_hz"] = hz
        _timed["weather_shake_every"] = shake_every
        _timed["weather_until"] = _game_now() + for_s
        _timed["weather_next_shake"] = 0.0
        if name == "clear":
            _timed["dim_restore_at"] = _game_now() + 1.0
            _timed["dim_restore_to"] = 1.0
        try:
            engine._agency_weather = name
        except Exception:
            pass
    except Exception:
        pass


# ── finale ───────────────────────────────────────────────────────────────

# Two authored climax animations, one per route. Each step: (at_s, pose, dim).
# vaginal ("inside") = surrender: she lost control, front-facing collapse into
# softness, warm bright light. anal = control: she withholds inside as a power
# move, back-facing and composed, cooler light, no soft glow after.
_FINALE_CHOREO = {
    "vaginal": [
        (0.5, "squat", 1.12),
        (6.0, "angled_collapse", 1.16),
        (14.0, "laying_smile", 1.10),
        (24.0, "laying_smile", 1.08),
    ],
    "anal": [
        (0.5, "stand_backfacing", 0.92),
        (6.0, "coy_cheek", 0.86),
        (14.0, "coy_cheek", 0.90),
        (24.0, "stand_backfacing", 0.88),
    ],
}


def _h_finale(engine, value, act):
    """Finale mode: notes stop, route-specific climax animation plays."""
    try:
        start = True
        route = "vaginal"
        if isinstance(value, dict):
            if "start" in value:
                start = bool(value.get("start"))
            elif "stop" in value:
                start = not bool(value.get("stop"))
            route = str(value.get("route") or "vaginal").lower()
        if route not in ("vaginal", "anal"):
            route = "vaginal"
        now = _game_now()
        if start:
            engine._agency_finale = True
            engine._agency_finale_route = route
            engine._agency_finale_until = now + 300.0  # 5 min hard cap
            engine._agency_finale_choreo = [
                (now + at, pose, dim)
                for at, pose, dim in _FINALE_CHOREO[route]
            ]
            _timed["finale_flicker"] = True
        else:
            engine._agency_finale = False
            engine._agency_finale_choreo = []
            _timed["finale_flicker"] = False
            r = _renderer(engine)
            if r is not None:
                try:
                    # vaginal exits into the soft glow; anal stays flat —
                    # afterglow is vulnerability, and a brat who stayed in
                    # control doesn't do vulnerable.
                    r.set_dim(1.08 if getattr(engine, "_agency_finale_route", "") == "vaginal" else 1.0)
                except Exception:
                    pass
            engine._agency_finale_route = ""
    except Exception:
        pass


def _spawn_pause_fields(rhythm):
    """Candidate spawn-timer fields; push them forward to pause spawning."""
    return ("spawn_timer", "note_spawn_timer", "next_spawn", "next_note_time",
            "_next_spawn_at", "spawn_cooldown", "spawn_delay")


def _pause_spawning(engine):
    try:
        rhythm = _rhythm(engine)
        if rhythm is None:
            return
        now = _game_now()
        for f in _spawn_pause_fields(rhythm):
            try:
                v = getattr(rhythm, f, None)
                if isinstance(v, (int, float)) and v < now + 4.0:
                    setattr(rhythm, f, now + 4.0)
            except Exception:
                pass
    except Exception:
        pass


# ── tick ─────────────────────────────────────────────────────────────────

def _tick(engine):
    now = _game_now()
    # tempo revert
    if _timed["tempo_revert_at"] and now >= _timed["tempo_revert_at"]:
        _timed["tempo_revert_at"] = 0.0
        _revert_tempo()
        try:
            engine._agency_tempo = 1.0
        except Exception:
            pass
    # dim restore
    if _timed["dim_restore_at"] and now >= _timed["dim_restore_at"]:
        _timed["dim_restore_at"] = 0.0
        try:
            r = _renderer(engine)
            if r is not None:
                r.set_dim(_timed["dim_restore_to"])
        except Exception:
            pass
    # flicker: blush shimmer while it lasts
    if _timed["flicker_until"] and now < _timed["flicker_until"]:
        try:
            r = _renderer(engine)
            if r is not None:
                import math
                # oscillate dim 0.85..1.05 at ~6Hz
                r.set_dim(0.95 + 0.1 * math.sin(now * 37.0))
        except Exception:
            pass
    elif _timed["flicker_until"] and now >= _timed["flicker_until"]:
        _timed["flicker_until"] = 0.0
        try:
            r = _renderer(engine)
            if r is not None and not _timed["dim_restore_at"]:
                r.set_dim(1.0)
        except Exception:
            pass
    # pout expiry
    if _timed.get("pout_until") and now >= _timed["pout_until"]:
        _timed["pout_until"] = 0.0
        try:
            engine._agency_pouting = False
        except Exception:
            pass
    # halftime: fire chained moves WITHOUT pausing spawning (story-in-rhythm v2).
    # Notes never stop, even during halftime show.
    try:
        ht_until = float(getattr(engine, "_agency_halftime_until", 0.0) or 0.0)
    except Exception:
        ht_until = 0.0
    if ht_until and now < ht_until:
        # STORY-IN-RHYTHM V2: _pause_spawning removed - notes continue during halftime.
        try:
            pending = list(getattr(engine, "_agency_halftime_moves", None) or [])
            rest = []
            for at, m in pending:
                if now >= at:
                    _h_move(engine, m, {})
                    r = _renderer(engine)
                    if r is not None:
                        try:
                            r.trigger_flash(2, 0.35)
                        except Exception:
                            pass
                else:
                    rest.append((at, m))
            engine._agency_halftime_moves = rest
        except Exception:
            pass
    elif ht_until and now >= ht_until:
        try:
            engine._agency_halftime_until = 0.0
        except Exception:
            pass
    # finale: NOTES NEVER STOP (story-in-rhythm v2). Route-specific climax
    # animation + light play during continuous rhythm. Choreography pose steps
    # fire without pausing note spawning.
    try:
        finale = bool(getattr(engine, "_agency_finale", False))
        fin_until = float(getattr(engine, "_agency_finale_until", 0.0) or 0.0)
    except Exception:
        finale, fin_until = False, 0.0
    if finale:
        if fin_until and now >= fin_until:
            try:
                engine._agency_finale = False
            except Exception:
                pass
            _timed["finale_flicker"] = False
        else:
            # STORY-IN-RHYTHM V2: _pause_spawning removed - notes continue during finale.
            # choreography: due pose steps fire once each
            try:
                steps = list(getattr(engine, "_agency_finale_choreo", None) or [])
                if steps:
                    rest = []
                    r = _renderer(engine)
                    for at, pose, dim in steps:
                        if now >= at:
                            _pose_pulse(engine, pose, 7.0)
                            if r is not None:
                                try:
                                    r.set_dim(dim)
                                except Exception:
                                    pass
                        else:
                            rest.append((at, pose, dim))
                    engine._agency_finale_choreo = rest
            except Exception:
                pass
    if _timed.get("finale_flicker"):
        try:
            r = _renderer(engine)
            if r is not None:
                import math
                route = str(getattr(engine, "_agency_finale_route", "") or "vaginal")
                if route == "anal":
                    # cooler, steadier: she's composed, in control
                    r.set_dim(0.88 + 0.03 * math.sin(now * 2.0))
                else:
                    # warm slow flicker: she lost control
                    r.set_dim(1.10 + 0.06 * math.sin(now * 4.0))
        except Exception:
            pass
    # hiccups: tiny jolts on schedule
    try:
        hic = list(getattr(engine, "_agency_hiccups", None) or [])
        if hic:
            rest = []
            r = _renderer(engine)
            for at in hic:
                if now >= at:
                    if r is not None:
                        try:
                            r.trigger_shake(0.18, 1.2)
                        except Exception:
                            pass
                else:
                    rest.append(at)
            engine._agency_hiccups = rest
    except Exception:
        pass
    # weather
    w_until = _timed.get("weather_until") or 0.0
    if w_until and now < w_until:
        try:
            import math
            r = _renderer(engine)
            hz = _timed.get("weather_hz") or 0.0
            if r is not None and hz:
                base = {"sparkles": 1.1, "rain": 0.55, "ember": 0.95}.get(
                    _timed.get("weather"), 1.0)
                r.set_dim(base + 0.05 * math.sin(now * hz * 6.2831))
            shake_every = _timed.get("weather_shake_every") or 0.0
            if shake_every and r is not None:
                nxt = _timed.get("weather_next_shake") or 0.0
                if now >= nxt:
                    try:
                        r.trigger_shake(0.25, 0.8)
                    except Exception:
                        pass
                    _timed["weather_next_shake"] = now + shake_every
        except Exception:
            pass
    elif w_until and now >= w_until:
        _timed["weather_until"] = 0.0
        _timed["weather"] = "clear"
        try:
            r = _renderer(engine)
            if r is not None:
                r.set_dim(1.0)
            engine._agency_weather = "clear"
        except Exception:
            pass


def _install():
    if get_link is None:
        return False
    try:
        link = get_link()
    except Exception:
        return False
    try:
        link.register_action_handler("move", _h_move)
        link.register_action_handler("tempo", _h_tempo)
        link.register_action_handler("chart", _h_chart)
        link.register_action_handler("lightmap", _h_lightmap)
        link.register_action_handler("body", _h_body)
        link.register_action_handler("toot", _h_toot)
        link.register_action_handler("pout", _h_pout)
        link.register_action_handler("halftime", _h_halftime)
        link.register_action_handler("hijack", _h_hijack)
        link.register_action_handler("hiccup", _h_hiccup)
        link.register_action_handler("weather", _h_weather)
        link.register_action_handler("finale", _h_finale)
    except Exception:
        return False
    # tick timed effects inside the per-frame poll.
    # NOTE: link.poll is a BOUND method (poll(self, engine)). Capture it bound,
    # then install a plain closure taking (engine) — NOT __get__ rebinding,
    # which double-binds and TypeErrors every frame (previously swallowed by
    # the game's try/except, silently killing all agency actions game-side).
    try:
        orig_poll = link.poll  # bound

        def _ticking_poll(engine):
            try:
                _tick(engine)
            except Exception:
                pass
            return orig_poll(engine)

        link.poll = _ticking_poll
    except Exception:
        pass
    return True


_installed = _install()
