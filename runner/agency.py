#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agency.py — Jasmine's agency kit, director side.

Tracks her side of the duet across beats: her surge meter, body state
(sweat/musk/pressure), move cooldowns, tempo, and ghost-note wagers.
Validates the writer's action dict (meter costs, cooldowns, clamps) and
builds the per-beat context the writer uses to play.

Nothing here touches the game directly; validated actions ride the normal
director_to_game.fifo path and land in jasmine_agency.py's handlers.
"""
from __future__ import annotations

import time

MOVES = {
    "buck":    {"cost": 15, "desc": "sudden surge toward him — screen shudder + flash"},
    "wiggle":  {"cost": 10, "desc": "playful hip sway, teasing pose"},
    "arch":    {"cost": 12, "desc": "arches back, shows off, warm flash"},
    "grind":   {"cost": 20, "desc": "slow roll in close; drags his notes off-beat, he follows her"},
    "clench":  {"cost": 25, "desc": "sudden spike — extra notes rush in; hold through for the release"},
    "melt":    {"cost": 12, "desc": "goes soft and glowy; gentle inputs earn free intimacy"},
    "present": {"cost": 18, "desc": "shows off — bloom flash, strikes a pose"},
    "shy":     {"cost": 8,  "desc": "covers up, light dims; he coaxes her back with soft surges"},
}

MOVE_COOLDOWN_S = 25.0
GLOBAL_MOVE_COOLDOWN_S = 8.0

# crazy-kit costs/cooldowns
HALFTIME_COST = 30.0
HALFTIME_COOLDOWN_S = 90.0
HIJACK_COST = 20.0
HIJACK_COOLDOWN_S = 60.0
HICCUP_COOLDOWN_S = 30.0
WEATHER_COST = 5.0

TOOT_FLAVORS = ("bashful", "submissive", "power")
WEATHERS = ("sparkles", "rain", "ember", "clear")

# a move bid counts as "answered" if he presses any key within this window
BID_ANSWER_WINDOW_S = 8.0
POUT_STREAK = 2  # consecutive unanswered bids before she pouts on her own


class AgencyState:
    def __init__(self):
        self.meter = 30.0
        self.sweat = 10.0
        self.musk = 5.0
        self.pressure = 15.0
        self.move_cd: dict[str, float] = {}
        self.last_move_at = 0.0
        self.last_move = None
        self.tempo = 1.0
        self.tempo_until = 0.0
        self.ghost_pending = 0
        self.ghost_wager_active = False
        self.last_combo = 0
        self.last_ghost_result = None  # "caught" | "missed" | None
        self.toot_flavor_pending = None
        self.beats_seen = 0
        self.t0 = time.time()
        # brat score: her bids vs his answers
        self.brat_bids = 0
        self.brat_answered = 0
        self._pending_bid_t: float | None = None
        self._unanswered_streak = 0
        self.pouting = False
        self.auto_pout_due = False
        self.pout_lift_due = False   # keypress broke the pout: tell the game to lift the visual
        # crazy-kit cooldowns
        self.halftime_cd_until = 0.0
        self.hijack_cd_until = 0.0
        self.hiccup_cd_until = 0.0

    # ── input observation (from server telemetry) ──────────────────────
    def note_keypress(self, t: float) -> None:
        """He pressed a key. Answers her pending move bid if in window."""
        if self._pending_bid_t is not None and (t - self._pending_bid_t) <= BID_ANSWER_WINDOW_S:
            self.brat_answered += 1
            self._pending_bid_t = None
            self._unanswered_streak = 0
        if self.pouting:
            # any keypress is attention — he coaxed her back, pout's over
            self.pouting = False
            self.auto_pout_due = False
            self.pout_lift_due = True   # director merges {"pout": false} into next reply

    @property
    def brat_score(self) -> int:
        if self.brat_bids == 0:
            return 50
        return max(0, min(100, round(100.0 * self.brat_answered / self.brat_bids)))

    # ── per-beat tracking ──────────────────────────────────────────────
    def track_beat(self, beat: dict) -> None:
        now = time.time()
        self.beats_seen += 1
        her = beat.get("her") or {}
        esc = beat.get("escalation") or {}
        try:
            pleasure = float(her.get("pleasure") or 0.0)
        except Exception:
            pleasure = 0.0
        try:
            intensity = float(her.get("intensity") or 0.0)
        except Exception:
            intensity = 0.0
        try:
            combo = int(esc.get("combo") or 0)
        except Exception:
            combo = 0

        # her meter: builds on his rhythm accuracy + her pleasure
        combo_delta = max(0, combo - self.last_combo)
        self.last_combo = combo
        self.meter = min(100.0, self.meter + 1.2 + pleasure * 0.02 + combo_delta * 0.4)

        # body state
        self.sweat = min(100.0, self.sweat + intensity * 0.012)
        self.musk = min(100.0, self.musk + (self.sweat / 100.0) * 0.02 + pleasure * 0.004)
        self.pressure = min(100.0, self.pressure + 0.10)
        if intensity < 25:
            self.sweat = max(0.0, self.sweat - 0.15)
            self.musk = max(0.0, self.musk - 0.10)

        # ghost wager resolution: combo climbed while a ghost was pending
        if self.ghost_wager_active:
            if combo_delta > 0:
                self.last_ghost_result = "caught"
                self.ghost_wager_active = False
                self.ghost_pending = 0
                self.meter = min(100.0, self.meter + 6.0)  # she loved that
            elif self.beats_seen % 6 == 0:
                # enough beats passed with no climb: he let it pass
                self.last_ghost_result = "missed"
                self.ghost_wager_active = False
                self.ghost_pending = 0

        # tempo expiry bookkeeping (game side reverts; we mirror for context)
        if self.tempo_until and now >= self.tempo_until:
            self.tempo = 1.0
            self.tempo_until = 0.0

        # bid expiry: her move went unanswered
        if self._pending_bid_t is not None and (now - self._pending_bid_t) > BID_ANSWER_WINDOW_S:
            self._pending_bid_t = None
            self._unanswered_streak += 1
            if self._unanswered_streak >= POUT_STREAK and not self.pouting:
                self.pouting = True
                self.auto_pout_due = True  # director converts to a pout action

    # ── validation ─────────────────────────────────────────────────────
    def validate(self, action) -> dict | None:
        """Sanitize the writer's action dict. Returns a clean dict (possibly
        empty → None) with meter/cooldowns enforced and values clamped."""
        if not isinstance(action, dict) or not action:
            return None
        now = time.time()
        out: dict = {}

        # move
        mv = action.get("move")
        mv_name = None
        if isinstance(mv, dict):
            mv_name = str(mv.get("name") or "").lower()
        elif isinstance(mv, str):
            mv_name = mv.lower()
        if mv_name in MOVES:
            cost = MOVES[mv_name]["cost"]
            cd_ok = (now - self.move_cd.get(mv_name, 0.0)) >= MOVE_COOLDOWN_S
            glob_ok = (now - self.last_move_at) >= GLOBAL_MOVE_COOLDOWN_S
            if self.meter >= cost and cd_ok and glob_ok:
                self.meter -= cost
                self.move_cd[mv_name] = now
                self.last_move_at = now
                self.last_move = mv_name
                # her bid: he answers by pressing a key within the window
                self.brat_bids += 1
                self._pending_bid_t = now
                m = {"name": mv_name}
                if isinstance(mv, dict):
                    try:
                        h = float(mv.get("hold"))
                        m["hold"] = max(1.0, min(8.0, h))
                    except Exception:
                        pass
                out["move"] = m
            # else: silently dropped — she keeps her line, skips the move

        # tempo
        tp = action.get("tempo")
        scale = None
        for_s = 45.0
        if isinstance(tp, dict):
            try:
                scale = float(tp.get("scale"))
            except Exception:
                pass
            try:
                for_s = max(5.0, min(300.0, float(tp.get("for_s", 45.0))))
            except Exception:
                pass
        elif isinstance(tp, (int, float)):
            try:
                scale = float(tp)
            except Exception:
                pass
        if scale is not None:
            scale = max(0.5, min(1.5, scale))
            if abs(scale - 1.0) >= 0.05:
                out["tempo"] = {"scale": round(scale, 2), "for_s": round(for_s, 1)}
                self.tempo = scale
                self.tempo_until = now + for_s
            else:
                self.tempo = 1.0
                self.tempo_until = 0.0

        # chart mischief
        ch = action.get("chart")
        if isinstance(ch, dict):
            c = {}
            try:
                nz = float(ch.get("nudge_ms", 0.0))
                if nz:
                    c["nudge_ms"] = max(-120.0, min(120.0, nz))
            except Exception:
                pass
            try:
                cl = int(ch.get("cluster", 0))
                if cl > 0:
                    c["cluster"] = max(1, min(3, cl))
            except Exception:
                pass
            try:
                gh = int(ch.get("ghost", 0))
                if gh > 0:
                    c["ghost"] = max(1, min(2, gh))
                    self.ghost_pending += c["ghost"]
                    self.ghost_wager_active = True
            except Exception:
                pass
            if c:
                out["chart"] = c

        # lightmap blush
        lm = action.get("lightmap")
        if isinstance(lm, dict):
            l = {}
            try:
                d = float(lm.get("dim"))
                l["dim"] = max(0.4, min(1.2, d))
            except Exception:
                pass
            if lm.get("bloom"):
                l["bloom"] = True
            if lm.get("flicker"):
                l["flicker"] = True
            if l:
                try:
                    l["for_s"] = max(2.0, min(120.0, float(lm.get("for_s", 8.0))))
                except Exception:
                    pass
                out["lightmap"] = l

        # body state push
        bo = action.get("body")
        if isinstance(bo, dict):
            b = {}
            for k in ("sweat", "musk"):
                try:
                    v = float(bo.get(k))
                    b[k] = max(0.0, min(100.0, v))
                except Exception:
                    pass
            if b:
                out["body"] = b
                # her push nudges the tracked state too
                if "sweat" in b:
                    self.sweat = min(100.0, max(self.sweat, b["sweat"] * 0.5))
                if "musk" in b:
                    self.musk = min(100.0, max(self.musk, b["musk"] * 0.5))

        # toot event
        tt = action.get("toot")
        if isinstance(tt, str) and tt.lower() in TOOT_FLAVORS:
            out["toot"] = tt.lower()
            self.toot_flavor_pending = tt.lower()
            self.pressure = max(10.0, self.pressure - 30.0)  # release
        elif tt is True:
            out["toot"] = "bashful"
            self.toot_flavor_pending = "bashful"
            self.pressure = max(10.0, self.pressure - 30.0)

        # ── the crazy kit ──

        # pout: she's sulking (or the writer chooses to pout)
        if "pout" in action:
            pt = action.get("pout")
            if pt:
                p = {}
                if isinstance(pt, dict):
                    try:
                        p["for_s"] = max(5.0, min(60.0, float(pt.get("for_s", 20.0))))
                    except Exception:
                        pass
                out["pout"] = p or True
                self.pouting = True
            else:
                # explicit release: {"pout": false} — she broke the sulk herself
                self.pouting = False
                self.auto_pout_due = False
                out["pout"] = False

        # halftime: hijack the chart for a chained move combo
        ht = action.get("halftime")
        if ht:
            for_s = 10.0
            if isinstance(ht, dict):
                try:
                    for_s = max(5.0, min(20.0, float(ht.get("for_s", 10.0))))
                except Exception:
                    pass
            if self.meter >= HALFTIME_COST and now >= self.halftime_cd_until:
                self.meter -= HALFTIME_COST
                self.halftime_cd_until = now + HALFTIME_COOLDOWN_S
                out["halftime"] = {"for_s": round(for_s, 1)}

        # hijack: his surge keys do her bidding
        hj = action.get("hijack")
        if hj:
            for_s = 6.0
            if isinstance(hj, dict):
                try:
                    for_s = max(3.0, min(15.0, float(hj.get("for_s", 6.0))))
                except Exception:
                    pass
            if self.meter >= HIJACK_COST and now >= self.hijack_cd_until:
                self.meter -= HIJACK_COST
                self.hijack_cd_until = now + HIJACK_COOLDOWN_S
                out["hijack"] = {"for_s": round(for_s, 1)}

        # hiccup: tiny screen jolts, devastating
        hc = action.get("hiccup")
        if hc:
            n = 3
            if isinstance(hc, dict):
                try:
                    n = max(1, min(6, int(hc.get("n", 3))))
                except Exception:
                    pass
            elif isinstance(hc, (int, float)):
                try:
                    n = max(1, min(6, int(hc)))
                except Exception:
                    pass
            if now >= self.hiccup_cd_until:
                self.hiccup_cd_until = now + HICCUP_COOLDOWN_S
                out["hiccup"] = {"n": n}

        # weather: her mood made visible
        wv = action.get("weather")
        wname = None
        if isinstance(wv, str) and wv.lower() in WEATHERS:
            wname = wv.lower()
        elif isinstance(wv, dict) and str(wv.get("kind", "")).lower() in WEATHERS:
            wname = str(wv.get("kind")).lower()
        if wname and self.meter >= WEATHER_COST:
            self.meter -= WEATHER_COST
            w = {"kind": wname}
            if isinstance(wv, dict):
                try:
                    w["for_s"] = max(10.0, min(180.0, float(wv.get("for_s", 60.0))))
                except Exception:
                    pass
            out["weather"] = w

        # pass through the already-supported keys untouched
        for k in ("pose", "hold", "flash", "name"):
            if k in action:
                out[k] = action[k]

        return out or None

    # ── writer context ─────────────────────────────────────────────────
    def writer_context(self) -> dict:
        now = time.time()
        moves = {}
        for name, spec in MOVES.items():
            cd_left = max(0.0, MOVE_COOLDOWN_S - (now - self.move_cd.get(name, 0.0)))
            glob_left = max(0.0, GLOBAL_MOVE_COOLDOWN_S - (now - self.last_move_at))
            afford = self.meter >= spec["cost"]
            why = None
            if not afford:
                why = f"need {spec['cost']} meter"
            elif cd_left > 0 or glob_left > 0:
                why = "cooling down"
            moves[name] = {
                "cost": spec["cost"],
                "ready": afford and cd_left <= 0 and glob_left <= 0,
                "cd_s": round(max(cd_left, glob_left), 1),
                "why_not": why,
            }
        ctx = {
            "meter": round(self.meter, 1),
            "sweat": round(self.sweat, 1),
            "musk": round(self.musk, 1),
            "pressure": round(self.pressure, 1),
            "moves": moves,
            "tempo": self.tempo,
            "last_move": self.last_move,
        }
        if self.last_ghost_result:
            ctx["ghost_result"] = self.last_ghost_result
            self.last_ghost_result = None  # report once
        if self.toot_flavor_pending:
            ctx["toot_pending"] = self.toot_flavor_pending
            self.toot_flavor_pending = None  # report once
        # auto-toot hint: pressure high → she may want to cut one loose
        if self.pressure >= 85:
            ctx["pressure_hint"] = "she's full — a toot is brewing whether she plans it or not"
        # brat score + pout state: she grades how well he answers her bids
        ctx["brat_score"] = self.brat_score
        ctx["bids"] = self.brat_bids
        if self.pouting:
            ctx["pouting"] = True
            ctx["pout_note"] = ("she's pouting — he ignored her last bids. "
                                "she needs coaxing: soft surges, sweet words. "
                                "any keypress from him ends it.")
        elif self._unanswered_streak == 1:
            ctx["pout_note"] = "he didn't answer her last move — one more ignored bid and she pouts."
        return ctx
