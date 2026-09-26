#!/usr/bin/env python3
"""Deck writer: offline Jasmine for local play.

Reads beats from the session inbox, answers dialogue beats with a fresh
marisol-voiced line picked by scene context (never repeating within a
session), and plays her agency kit on action beats (moves, tempo, toots,
weather, pouts) using only moves the director reports as ready.

No network, no API keys, no TTS service needed — every line was
pre-rendered into assets/audio/jasmine/deck/.
"""
import json
import os
import random
import shutil
import sys
import time
from pathlib import Path

RUNNER = Path(__file__).resolve().parent
sys.path.insert(0, str(RUNNER))
from line_deck import DECK
from exchanges import pick_exchange

DECK_DIR = RUNNER.parent / "ogre_director_v2" / "assets" / "audio" / "jasmine" / "deck"

MOVE_NAMES = ["buck", "wiggle", "arch", "grind", "clench", "melt", "present", "shy"]
TOOT_FLAVORS = ["bashful", "submissive", "power"]
WEATHERS = ["sparkles", "rain", "ember", "clear"]

MAX_RUNTIME_S = 45 * 60


class DeckWriter:
    def __init__(self, session: Path):
        self.session = session
        self.inbox = session / "inbox"
        self.outbox = session / "outbox"
        self.clips = session / "clips"
        self.used: set[str] = set()
        self.bags: dict[str, list] = {}
        self._xchg_used: set[str] = set()
        self.start = time.time()

    # ── line picking ──────────────────────────────────────────────
    def pick(self, cat: str):
        # EXCHANGE DOCTRINE (dialogue_direction.md): prefer a paired
        # exchange for this category; her half is the line. Falls back
        # to the legacy deck where no exchanges exist.
        xid, xchg = pick_exchange(cat, self._xchg_used)
        if xchg is not None:
            return xid, xchg["her"]
        bag = self.bags.get(cat)
        if not bag:
            ids = [lid for lid, _ in DECK[cat] if lid not in self.used]
            if not ids:  # exhausted: allow repeats, reshuffle
                ids = [lid for lid, _ in DECK[cat]]
            random.shuffle(ids)
            bag = self.bags[cat] = ids
        lid = bag.pop()
        self.used.add(lid)
        text = next(t for i, t in DECK[cat] if i == lid)
        return lid, text

    def mood_category(self, beat: dict) -> str:
        # BIRD-ONLY: her heat comes from her side of the packet (her body,
        # her agency meter/pressure). fiend's keys are never read here.
        fin = beat.get("finale") or {}
        jas = beat.get("jasmine") or {}
        her = beat.get("her") or {}
        if fin.get("aftercare"):
            return "aftercare_smug" if fin.get("route") == "anal" else "aftercare"
        if fin.get("active"):
            route = str(fin.get("route") or "vaginal").lower()
            if route not in ("vaginal", "anal"):
                route = "vaginal"
            if fin.get("just_started"):
                return f"finale_announce_{route}"
            return f"finale_{route}"
        if jas.get("pouting"):
            return "pout" if random.random() < 0.75 else "tease"
        if jas.get("toot_pending") or jas.get("pressure_hint"):
            if random.random() < 0.65:
                return "toot"
        pleasure = float(her.get("pleasure") or 0.0)
        try:
            meter = float(jas.get("meter") or 0.0) / 100.0
        except Exception:
            meter = 0.0
        try:
            pressure = float(jas.get("pressure") or 0.0) / 100.0
        except Exception:
            pressure = 0.0
        heat = max(pleasure, meter, pressure)  # her heat, 0..1
        if heat >= 0.80 or pleasure >= 0.75:
            return random.choice(["heated", "feral", "feral"])
        if heat >= 0.40:
            return random.choice(["heated", "tease", "tease", "taunt"])
        # low heat: she goes soft/sweet sometimes, giggly sometimes
        r = random.random()
        if heat < 0.25:
            if r < 0.20:
                return "sweet"
            if r < 0.30:
                return "giggle"
            return "tease"
        if r < 0.10:
            return "giggle"
        return "tease"

    # ── agency plays ──────────────────────────────────────────────
    def agency_play(self, beat: dict):
        """Occasionally issue a real agency action on action beats."""
        jas = beat.get("jasmine") or {}
        fin = beat.get("finale") or {}
        if fin.get("active"):
            return None  # finale is intimate guidance, not mischief
        moves = jas.get("moves") or {}
        ready = [m for m in MOVE_NAMES if (moves.get(m) or {}).get("ready")]
        # pressure high -> she cuts one loose for real (not just a toot-flavored line)
        if jas.get("pressure_hint") and random.random() < 0.5:
            return {"toot": random.choice(TOOT_FLAVORS)}
        r = random.random()
        if ready and r < 0.42:
            return {"move": random.choice(ready)}
        if r < 0.50:
            return {"tempo": {"scale": random.choice([0.7, 0.85, 1.2, 1.35]),
                              "for_s": 30}}
        if r < 0.55 and not jas.get("pouting"):
            return {"pout": True}
        if r < 0.60:
            return {"toot": random.choice(TOOT_FLAVORS)}
        if r < 0.65:
            return {"weather": random.choice(WEATHERS)}
        if r < 0.67 and float(jas.get("meter") or 0) >= 30:
            return {"halftime": {"for_s": 20}}
        return None

    # ── beat handling ────────────────────────────────────────────
    @staticmethod
    @staticmethod
    def _probe_dur_s(path) -> float:
        """True MP3 duration via ffprobe when available."""
        try:
            import subprocess
            r = subprocess.run(["ffprobe", "-v", "error",
                                "-show_entries", "format=duration",
                                "-of", "default=noprint_wrappers=1:nokey=1",
                                str(path)],
                               capture_output=True, text=True, timeout=10)
            d = float((r.stdout or "").strip())
            if d > 0:
                return d
        except Exception:
            pass
        return 0.0

    def _clip_dur_s(self, path) -> float:
        """Spoken length of a deck clip. ffprobe when present; else the size
        heuristic (deck clips are ~64kbps CBR MP3s)."""
        d = self._probe_dur_s(path)
        if d > 0:
            return d
        try:
            return max(0.5, float(os.path.getsize(path)) * 8.0 / 64000.0)
        except Exception:
            return 1.5

    def _pace_emit(self, dur_s: float) -> None:
        """Overlap cadence: the next voiced reply may start while the previous
        clip is still playing — she steps over her own thoughts. Holds only
        until JASMINE_VOICE_OVERLAP fraction of the previous clip has elapsed
        (default 0.92 — rapid-fire, 5-10% overlap, never impossible vocal
        tricks), plus JASMINE_VOICE_GAP_S (default 0). Zero dead air, never
        more than ~2 voices deep (browser caps polyphony). Action-only
        replies are never paced."""
        try:
            overlap = float(os.environ.get("JASMINE_VOICE_OVERLAP", "0.92") or 0.92)
        except Exception:
            overlap = 0.92
        overlap = min(0.99, max(0.0, overlap))
        try:
            gap = max(0.0, float(os.environ.get("JASMINE_VOICE_GAP_S", "0") or 0))
        except Exception:
            gap = 0.0
        now = time.monotonic()
        nxt = float(getattr(self, "_next_emit_t", 0.0) or 0.0)
        if now < nxt:
            time.sleep(nxt - now)
            now = nxt
        self._next_emit_t = now + max(0.3, float(dur_s or 0.0)) * overlap + gap

    # v9: dormant newsounds library, wired to her moments. Names map to
    # newsounds/<dir>/ in the scene's SFX library; the director copies the
    # take into the session clips + manifest (same pump as her voice).
    _SFX_FOR_MOMENT = {
        "finale_announce_vaginal": ("climax_buildup", 1.0),
        "finale_announce_anal": ("climax_buildup", 1.0),
        "finale_vaginal": ("climax_release", 0.7),
        "finale_anal": ("climax_release", 0.7),
        "aftercare": ("aftercare_settling", 0.55),
        "aftercare_smug": ("aftercare_settling", 0.55),
    }
    _SFX_WET_POOL = ("wet_precise", "wet_deep", "wet_intimate")
    _SFX_ELASTIC_POOL = ("elastic_rhythm", "elastic_mouth", "elastic_finger")

    def _maybe_sfx(self, category: str, beat: dict):
        """Pick a foley SFX for this beat, or None. Chance-gated so the bed
        breathes instead of clattering."""
        moment = self._SFX_FOR_MOMENT.get(category)
        if moment:
            name, chance = moment
            if random.random() < chance:
                return name
            return None
        if category in ("heated", "feral"):
            if random.random() < 0.22:
                return random.choice(self._SFX_WET_POOL)
        elif category == "taunt":
            if random.random() < 0.15:
                return "escalating_close"
        elif category == "action":
            jas = beat.get("jasmine") or {}
            try:
                pressure = float(jas.get("pressure") or 0.0) / 100.0
            except Exception:
                pressure = 0.0
            if pressure > 0.6 and random.random() < 0.20:
                return random.choice(self._SFX_ELASTIC_POOL)
        return None

    def answer(self, beat: dict):
        seq = int(beat["seq"])
        tag = f"{seq:06d}"
        reply = {"seq": seq}
        kind = beat.get("beat")
        jas = beat.get("jasmine") or {}

        if kind == "dialogue":
            cat = self.mood_category(beat)
            lid, text = self.pick(cat)
            src = DECK_DIR / f"{lid}.mp3"
            if src.exists():
                dest = self.clips / f"beat_{tag}.mp3"
                shutil.copyfile(src, dest)
                reply["clip"] = dest.name
                reply["dur_s"] = round(self._clip_dur_s(dest), 2)
            reply["line"] = text
            # she sometimes pouts for real on dialogue beats too
            jas = beat.get("jasmine") or {}
            if cat == "pout" and not jas.get("pouting") and random.random() < 0.5:
                reply["action"] = {"pout": True}
            sfx = self._maybe_sfx(cat, beat)
            if sfx:
                reply["sfx"] = sfx
        else:  # action beat
            action = self.agency_play(beat) or {}
            # her body tells the truth: forward tracked sweat/musk every action
            # beat so beads/wisps follow her actual heat (overlay defaults on).
            try:
                _sw = float(jas.get("sweat") or 0.0)
                _mu = float(jas.get("musk") or 0.0)
            except Exception:
                _sw, _mu = 0.0, 0.0
            if _sw > 0.5 or _mu > 0.5:
                action = {"body": {"sweat": round(_sw, 1), "musk": round(_mu, 1)},
                          **action}
            if action:
                reply["action"] = action
            if random.random() < 0.40:
                lid, text = self.pick("action")
                src = DECK_DIR / f"{lid}.mp3"
                if src.exists():
                    dest = self.clips / f"beat_{tag}.mp3"
                    shutil.copyfile(src, dest)
                    reply["clip"] = dest.name
                    reply["dur_s"] = round(self._clip_dur_s(dest), 2)
                reply["line"] = text
                sfx = self._maybe_sfx("action", beat)
                if sfx:
                    reply["sfx"] = sfx

        if reply.get("clip") and float(reply.get("dur_s") or 0.0) > 0:
            self._pace_emit(float(reply["dur_s"]))
        (self.outbox / f"reply_{tag}.json").write_text(json.dumps(reply))
        print(f"replied {seq} ({kind}) line={bool(reply.get('line'))} "
              f"action={reply.get('action')}", flush=True)

    def run(self):
        idle_since = time.time()
        while True:
            if time.time() - self.start > MAX_RUNTIME_S:
                print("deck writer: max runtime, exiting", flush=True)
                return
            beats = sorted(self.inbox.glob("beat_*.json"))
            if not beats:
                # director done? the stats file goes STALE when the
                # director stops (it writes every ~2s while alive), so
                # staleness — not mere existence — means session over.
                # give it a grace period, then exit.
                st = self.session / "director_stats.json"
                if st.exists():
                    try:
                        stale_s = time.time() - st.stat().st_mtime
                    except Exception:
                        stale_s = 0.0
                    if stale_s > 30 and time.time() - idle_since > 15:
                        print("deck writer: session over, exiting", flush=True)
                        return
                else:
                    idle_since = time.time()
                time.sleep(0.5)
                continue
            idle_since = time.time()
            for bf in beats:
                try:
                    beat = json.loads(bf.read_text(encoding="utf-8"))
                except Exception:
                    bf.unlink(missing_ok=True)
                    continue
                if not isinstance(beat, dict) or "seq" not in beat:
                    bf.unlink(missing_ok=True)
                    continue
                try:
                    self.answer(beat)
                except Exception as e:
                    print(f"answer failed: {e}", flush=True)
                finally:
                    bf.unlink(missing_ok=True)


def main():
    if len(sys.argv) < 2:
        print("usage: deck_writer.py <session-dir>")
        sys.exit(1)
    DeckWriter(Path(sys.argv[1])).run()


if __name__ == "__main__":
    main()
