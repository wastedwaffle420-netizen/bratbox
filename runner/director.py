#!/usr/bin/env python3
"""
director.py — Jasmine director daemon.

Bridges the game (via FIFOs) and the Jasmine writer subagent (via a
file dropbox), with hard timing guarantees so the game NEVER blocks:

  game --(game_to_director.fifo)--> director --(inbox/beat_N.json)--> writer (Jasmine)
  game <--(director_to_game.fifo)-- director <--(outbox/reply_N.json)-- writer

Per beat, the writer gets (wait_ms - margin) seconds. On timeout the game
falls back to its pool line untouched. Late replies are dropped, never
applied out of order.

Session layout (all under --session):
  fifo/game_to_director.fifo, fifo/director_to_game.fifo
  inbox/beat_<seq>.json      written by director, consumed by writer
  outbox/reply_<seq>.json   written by writer, consumed by director
  clips/beat_<seq>.mp3      rendered by writer (tts)
  clips/manifest.jsonl      appended by director: {"idx","seq","clip","t"}
  director.log              JSONL event log
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path

running = True


def _on_sig(signum, frame):
    global running
    running = False


# Intimacy bed loop toggle (launcher checkbox -> BRATBOX_BED_LOOP).
# Off = the bed never starts, in any flow: the director is the single
# producer of bed events (clips/bed_intimacy.mp3 + manifest kind:"bed"),
# so gating here silences the browser, the offline operator, and the
# native writer paths all at once.
_BED_LOOP_ENABLED = (os.environ.get("BRATBOX_BED_LOOP", "1").strip().lower()
                     not in ("0", "false", "no", "off"))


signal.signal(signal.SIGINT, _on_sig)
signal.signal(signal.SIGTERM, _on_sig)

try:
    import agency as _agency_mod
except Exception:
    _agency_mod = None

try:
    import arousal as _arousal_mod
except Exception:
    _arousal_mod = None


def logj(logf, **kw):
    try:
        logf.write(json.dumps({"t": round(time.time(), 3), **kw}) + "\n")
        logf.flush()
    except Exception:
        pass


def prune_stale(d: Path, older_than_s: float, pattern: str, logf) -> int:
    now = time.time()
    n = 0
    for p in d.glob(pattern):
        try:
            if now - p.stat().st_mtime > older_than_s:
                p.unlink()
                n += 1
        except Exception:
            pass
    return n


# Hardcoded toot takes per flavor — mirrors the game's _TOOT_TAKES.
# The SFX library lives in the scene tree next to the game.
def _sfx_library() -> Path:
    return Path(__file__).resolve().parent.parent / "ogre_director_v2" / "assets" / "audio" / "jasmine"


_TOOT_SFX = {
    "cute": ("toot/cute", (
        "mature_toot.mp3",
    )),
    "power": ("toot/power", (
        "4._Gross_weighted_ba__2-1779910860583.mp3",
        "4._Gross_weighted_ba__4-1779910870476.mp3",
        "1._Close-mic_gross_b__3-1779910962356.mp3",
    )),
    "submissive": ("toot/submissive", (
        "1._Deep_sudden_stoma__1-1779906650241.mp3",
        "1._Deep_sudden_stoma__2-1779906658856.mp3",
        "1._Deep_sudden_stoma__3-1779906663368.mp3",
        "1._Deep_sudden_stoma__4-1779906667314.mp3",
    )),
    "bashful": ("toot/bashful", (
        "female_fart__airy_bu__1-1790283559792.mp3",
        "female_fart__airy_bu__3-1790283540979.mp3",
        "female_fart__airy_bu__3-1790283566222.mp3",
    )),
}

import random as _random


def _handle_toot(beat: dict, clips: Path, manifest, logf, idx: int) -> None:
    """Copy her flavor's toot take into the session clips and queue it in the
    manifest so the browser plays it. Same pump as her voice lines."""
    flavor = str(beat.get("flavor") or "cute").lower()
    sub, names = _TOOT_SFX.get(flavor, _TOOT_SFX["cute"])
    lib = _sfx_library()
    takes = [p for p in (lib / sub / n for n in names) if p.is_file()]
    if not takes:
        logj(logf, event="toot_sfx_missing", flavor=flavor)
        return
    src = _random.choice(takes)
    dest = clips / f"sfx_toot_{idx}.mp3"
    try:
        dest.write_bytes(src.read_bytes())
    except Exception as e:
        logj(logf, event="toot_sfx_copy_error", error=str(e)[:120])
        return
    manifest.write(json.dumps({"idx": idx, "kind": "sfx", "clip": dest.name,
                               "t": round(time.time(), 3)}) + "\n")
    manifest.flush()
    logj(logf, event="toot_sfx", flavor=flavor, clip=dest.name)


# v9: dormant newsounds library, wired. The writer names a moment ("sfx" in
# its reply); the director picks a random take from newsounds/<name>/ and
# queues it in the manifest like any other voice. Same pump, no new path.
def _handle_sfx(name: str, clips: Path, manifest, logf, idx: int) -> bool:
    """Copy a random newsounds take into the session clips and queue it.
    Returns True if a clip was queued."""
    sub = str(name or "").strip()
    if not sub or "/" in sub or sub.startswith("."):
        return False
    lib = _sfx_library() / "newsounds" / sub
    try:
        takes = [p for p in lib.iterdir() if p.is_file()]
    except Exception:
        takes = []
    if not takes:
        logj(logf, event="sfx_missing", name=sub)
        return False
    src = _random.choice(takes)
    ext = src.suffix.lower() or ".wav"
    dest = clips / f"sfx_{sub}_{idx}{ext}"
    try:
        dest.write_bytes(src.read_bytes())
    except Exception as e:
        logj(logf, event="sfx_copy_error", error=str(e)[:120])
        return False
    manifest.write(json.dumps({"idx": idx, "kind": "sfx", "clip": dest.name,
                               "t": round(time.time(), 3)}) + "\n")
    manifest.flush()
    logj(logf, event="sfx", name=sub, clip=dest.name)
    return True


# Intimacy layer (ultimate-bratbox sensory wiring).
# Explicit assets live user-local under assets/audio/jasmine/intimacy/
# (gitignored — never committed to the public repo). The bed loops under
# everything once he's in intimate territory; the BJ arc fires once at
# climax. Both degrade to silence when the files are absent.
def _intimacy_dir() -> Path:
    return _sfx_library() / "intimacy"


def _bed_start(clips: Path, manifest, logf, idx: int) -> bool:
    """Drop the intimacy bed into the session and announce the loop."""
    src = _intimacy_dir() / "intimacy_bed.mp3"
    if not src.is_file():
        logj(logf, event="intimacy_bed_missing")
        return False
    dest = clips / "bed_intimacy.mp3"
    try:
        if not dest.is_file():
            dest.write_bytes(src.read_bytes())
    except Exception as e:
        logj(logf, event="bed_copy_error", error=str(e)[:120])
        return False
    manifest.write(json.dumps({"idx": idx, "kind": "bed", "action": "start",
                               "clip": dest.name,
                               "t": round(time.time(), 3)}) + "\n")
    manifest.flush()
    logj(logf, event="bed_start", clip=dest.name)
    return True


def _bed_stop(clips: Path, manifest, logf, idx: int) -> None:
    """Announce the end of the bed loop and pull the file."""
    manifest.write(json.dumps({"idx": idx, "kind": "bed", "action": "stop",
                               "t": round(time.time(), 3)}) + "\n")
    manifest.flush()
    try:
        (clips / "bed_intimacy.mp3").unlink(missing_ok=True)
    except Exception:
        pass
    logj(logf, event="bed_stop")


def _handle_bjarc(clips: Path, manifest, logf, idx: int) -> bool:
    """Fire the BJ arc once, over the bed. The climax trigger."""
    src = _intimacy_dir() / "bj_arc.mp3"
    if not src.is_file():
        logj(logf, event="bjarc_missing")
        return False
    dest = clips / f"sfx_bjarc_{idx}.mp3"
    try:
        dest.write_bytes(src.read_bytes())
    except Exception as e:
        logj(logf, event="bjarc_copy_error", error=str(e)[:120])
        return False
    manifest.write(json.dumps({"idx": idx, "kind": "sfx", "clip": dest.name,
                               "t": round(time.time(), 3)}) + "\n")
    manifest.flush()
    logj(logf, event="bjarc", clip=dest.name)
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", required=True)
    ap.add_argument("--wait-ms", type=int, default=30000)
    args = ap.parse_args()

    sess = Path(args.session)
    fifo_d = sess / "fifo"
    inbox = sess / "inbox"
    outbox = sess / "outbox"
    clips = sess / "clips"
    for d in (fifo_d, inbox, outbox, clips):
        d.mkdir(parents=True, exist_ok=True)
    # never loop a crashed session's bed tail: fresh session, no bed
    try:
        (clips / "bed_intimacy.mp3").unlink(missing_ok=True)
    except Exception:
        pass

    WIN32 = os.name == "nt"
    if WIN32:
        # Windows: JSONL files instead of FIFOs (no mkfifo on Windows)
        rx_path = fifo_d / "game_to_director.jsonl"
        tx_path = fifo_d / "director_to_game.jsonl"
        rx_path.touch(exist_ok=True)
        tx_path.touch(exist_ok=True)
        rx_fd = None
        tx_fd = None
    else:
        for n in ("game_to_director.fifo", "director_to_game.fifo"):
            p = fifo_d / n
            if not p.exists():
                os.mkfifo(str(p), 0o600)

    logf = open(sess / "director.log", "a", buffering=1)
    manifest = open(clips / "manifest.jsonl", "a", buffering=1)
    manifest_idx = sum(1 for _ in open(clips / "manifest.jsonl")) if (clips / "manifest.jsonl").exists() else 0
    logj(logf, event="director_start",
         bed_loop="on" if _BED_LOOP_ENABLED else "off (BRATBOX_BED_LOOP=0)")

    # O_RDWR on both ends: open never blocks, read never sees EOF.
    # (Windows: JSONL files instead, see WIN32 above.)
    if not WIN32:
        rx_fd = os.open(str(fifo_d / "game_to_director.fifo"), os.O_RDWR | os.O_NONBLOCK)
        tx_fd = os.open(str(fifo_d / "director_to_game.fifo"), os.O_RDWR | os.O_NONBLOCK)
        rx = os.fdopen(rx_fd, "r", buffering=1)
        tx = os.fdopen(tx_fd, "w", buffering=1)
    else:
        rx = None
        tx = None

    margin = 2.0
    budget = max(3.0, args.wait_ms / 1000.0 - margin)
    stats = {"beats": 0, "replied": 0, "timeouts": 0, "dropped": 0}
    _last_stats_write = 0.0
    logj(logf, event="director_up", budget_s=round(budget, 1), wait_ms=args.wait_ms)

    ag = _agency_mod.AgencyState() if _agency_mod is not None else None
    if ag is not None:
        logj(logf, event="agency_up")

    ar = _arousal_mod.ArousalModel() if _arousal_mod is not None else None
    if ar is not None:
        logj(logf, event="arousal_up")

    # input-telemetry tail state (server.py appends key/voice events)
    tele_path = sess / "input_telemetry.jsonl"
    tele_off = 0

    def ingest_telemetry():
        """Feed new key/voice events into the arousal model + brat score."""
        nonlocal tele_off
        if ar is None or not tele_path.exists():
            return
        try:
            with open(tele_path, "rb") as f:
                f.seek(tele_off)
                data = f.read()
                tele_off = f.tell()
        except Exception:
            return
        for raw in data.split(b"\n"):
            if not raw.strip():
                continue
            try:
                ev = json.loads(raw.decode("utf-8", "replace"))
            except Exception:
                continue
            if not isinstance(ev, dict):
                continue
            t = float(ev.get("t") or time.time())
            # observe at ingest time: event clocks can skew (test feeds,
            # clock drift); ingest order + spacing is what matters
            now_ev = time.time()
            if "key" in ev:
                try:
                    ar.observe_key(min(t, now_ev), str(ev.get("key") or ""))
                except Exception:
                    pass
                if ag is not None:
                    try:
                        ag.note_keypress(now_ev)
                    except Exception:
                        pass
            elif "voice" in ev:
                try:
                    ar.observe_voice(now_ev, float(ev.get("voice") or 0.0),
                                     float(ev.get("vocal") or 0.0))
                except Exception:
                    pass

    # finale state machine
    finale_active = False
    finale_start_t = 0.0
    finale_route = "vaginal"
    # intimacy bed state machine (ultimate-bratbox sensory layer)
    bed_on = False
    bed_cool_since = 0.0
    bed_dead = False  # asset missing; don't retry this session
    best_combo = 0


    def _decide_finale_route(ag, snap, best_combo):
        """Her call, his play sways it. Returns "vaginal" or "anal".

        vaginal ("inside") = surrender variant: she's too horny for reason
        (pressure blown out) or he played so well he earned it.
        anal = control variant: she's still composed enough to withhold
        inside as a power move. Weighted whim, never a menu.
        """
        w_v, w_a = 1.0, 1.5  # she leans brat by default; it is her call
        try:
            pressure = float(getattr(ag, "pressure", 0) or 0)
        except Exception:
            pressure = 0.0
        if pressure >= 80:
            w_v += 3.0  # too horny for reason: composure broken
        elif pressure >= 60:
            w_v += 1.0
        try:
            combo = int(best_combo or 0)
        except Exception:
            combo = 0
        if combo >= 40:
            w_v += 2.0  # he earned it
        elif combo >= 20:
            w_v += 1.0
        try:
            brat = float(getattr(ag, "brat_score", 5) or 5)
        except Exception:
            brat = 5.0
        if brat >= 8:
            w_v += 1.0  # she grades him well
        return "vaginal" if _random.random() < w_v / (w_v + w_a) else "anal"

    rx_buf = b""
    win32_rx_off = 0  # file offset for tailing game_to_director.jsonl on Windows
    def _win32_read():
        """Tail game_to_director.jsonl on Windows."""
        nonlocal win32_rx_off
        try:
            with open(str(rx_path), "rb") as f:
                f.seek(win32_rx_off)
                chunk = f.read(65536)
                win32_rx_off = f.tell()
            return chunk
        except Exception:
            return b""
    def _win32_send(obj: dict):
        """Append a reply to director_to_game.jsonl on Windows."""
        try:
            with open(str(tx_path), "a", encoding="utf-8") as f:
                f.write(json.dumps(obj, separators=(",", ":"), default=str) + "\n")
        except Exception:
            pass
    while running:
        try:
            if WIN32:
                chunk = _win32_read()
            else:
                chunk = os.read(rx_fd, 65536)
        except BlockingIOError:
            time.sleep(0.02)
            continue
        except OSError:
            time.sleep(0.1)
            continue
        if not chunk:
            time.sleep(0.02)
            continue
        rx_buf += chunk
        while b"\n" in rx_buf:
            raw, rx_buf = rx_buf.split(b"\n", 1)
            try:
                beat = json.loads(raw.decode("utf-8", "replace"))
            except Exception:
                continue
            if not isinstance(beat, dict):
                continue
            # SFX beats carry no seq: a toot popped game-side. Play her real
            # take in the browser via the clips manifest (the server has no
            # speakers). Outside the dialogue flow; never blocks a beat.
            if beat.get("kind") == "toot":
                try:
                    _handle_toot(beat, clips, manifest, logf, manifest_idx)
                    manifest_idx += 1
                except Exception as e:
                    logj(logf, event="toot_sfx_error", error=str(e)[:120])
                continue
            if "seq" not in beat:
                continue
            seq = int(beat["seq"])
            stats["beats"] += 1
            tag = f"{seq:06d}"

            # Don't let a slow writer drown: prune ancient beats.
            prune_stale(inbox, older_than_s=budget * 1.5, pattern="beat_*.json", logf=logf)
            prune_stale(outbox, older_than_s=budget * 2.0, pattern="reply_*.json", logf=logf)

            beat["_director_arrived"] = round(time.time(), 3)
            beat["_director_budget_s"] = round(budget, 1)
            if ag is not None:
                try:
                    ag.track_beat(beat)
                    beat["jasmine"] = ag.writer_context()
                except Exception:
                    pass
            # fiend arousal: hidden stat from his input behavior
            try:
                ingest_telemetry()
            except Exception:
                pass
            if ar is not None:
                try:
                    snap = ar.update()
                    beat["fiend"] = snap
                    esc = beat.get("escalation") or {}
                    consent = str(esc.get("consent") or "")
                    try:
                        tier = int(esc.get("tier") or 0)
                    except Exception:
                        tier = 0
                    # his best combo this session sways her call at finale time
                    try:
                        _cb = int(esc.get("combo") or 0)
                    except Exception:
                        _cb = 0
                    if _cb > best_combo:
                        best_combo = _cb
                    # finale trigger: he's peaking and the scene allows it.
                    # the start action goes straight to the game (not via the
                    # writer) so it lands even if she misses the beat.
                    if (not finale_active and ar.peak_ready(consent, tier)
                            and not str(beat.get("safeword") or "").strip()):
                        finale_active = True
                        finale_start_t = time.time()
                        finale_route = _decide_finale_route(ag, snap, best_combo)
                        ar.mark_finale()
                        beat["finale"] = {"active": True, "just_started": True,
                                          "route": finale_route}
                        try:
                            _msg = {"seq": seq, "action": {"finale": {"start": True, "route": finale_route}}}
                            if WIN32:
                                _win32_send(_msg)
                            else:
                                tx.write(json.dumps(_msg, separators=(",", ":")) + "\n")
                                tx.flush()
                        except Exception as e:
                            logj(logf, event="finale_tx_fail", seq=seq, err=str(e))
                        logj(logf, event="finale_start", seq=seq,
                             arousal=snap.get("arousal"), route=finale_route)
                        # climax trigger: the BJ arc fires once, over the bed.
                        try:
                            if _handle_bjarc(clips, manifest, logf,
                                             manifest_idx):
                                manifest_idx += 1
                        except Exception as e:
                            logj(logf, event="bjarc_error",
                                 error=str(e)[:120])
                    elif finale_active:
                        beat["finale"] = {"active": True, "route": finale_route}
                        # exit: he's gone quiet (done), 5-min cap, or safeword
                        quiet = float(snap.get("quiet_s") or 0.0)
                        sw = str(beat.get("safeword") or "").strip()
                        reason = None
                        if sw:
                            reason = "safeword"
                        elif quiet > 60.0:
                            reason = "quiet"
                        elif (time.time() - finale_start_t) > 300.0:
                            reason = "cap"
                        if reason:
                            finale_active = False
                            beat["finale"] = {"active": False, "aftercare": True,
                                              "route": finale_route}
                            try:
                                _msg = {"seq": seq, "action": {"finale": {"stop": True}}}
                                if WIN32:
                                    _win32_send(_msg)
                                else:
                                    tx.write(json.dumps(_msg, separators=(",", ":")) + "\n")
                                    tx.flush()
                            except Exception:
                                pass
                            logj(logf, event="finale_end", seq=seq, reason=reason)
                    # intimacy bed: the default loop. Starts once he's in
                    # intimate territory (warming+), stops after 60s back
                    # at cool. Missing asset degrades to silence, logged once.
                    try:
                        st = str(snap.get("state") or "cool")
                        if st in ("warming", "close", "peak"):
                            bed_cool_since = 0.0
                            if not bed_on and not bed_dead and _BED_LOOP_ENABLED:
                                if _bed_start(clips, manifest, logf,
                                              manifest_idx):
                                    bed_on = True
                                    manifest_idx += 1
                                else:
                                    bed_dead = True
                        elif bed_on:
                            if not bed_cool_since:
                                bed_cool_since = time.time()
                            elif time.time() - bed_cool_since > 60.0:
                                _bed_stop(clips, manifest, logf, manifest_idx)
                                manifest_idx += 1
                                bed_on = False
                                bed_cool_since = 0.0
                    except Exception as e:
                        logj(logf, event="bed_error", error=str(e)[:120])
                except Exception:
                    pass
            try:
                (inbox / f"beat_{tag}.json").write_text(json.dumps(beat), encoding="utf-8")
            except Exception as e:
                logj(logf, event="inbox_write_fail", seq=seq, err=str(e))
                stats["dropped"] += 1
                continue

            logj(logf, event="beat", seq=seq, beat=beat.get("beat"),
                 mode=(beat.get("phase") or {}).get("mode"),
                 pose=(beat.get("phase") or {}).get("pose"),
                 candidate=(beat.get("candidate") or {}).get("text", "")[:80])

            reply_path = outbox / f"reply_{tag}.json"
            deadline = time.time() + budget
            reply = None
            last_ar = 0.0
            while running and time.time() < deadline:
                if reply_path.exists():
                    try:
                        reply = json.loads(reply_path.read_text(encoding="utf-8"))
                        reply_path.unlink()
                    except Exception:
                        reply = None
                        try:
                            reply_path.unlink()
                        except Exception:
                            pass
                    break
                # keep her read on him fresh while she writes
                if ar is not None and time.time() - last_ar > 2.0:
                    last_ar = time.time()
                    try:
                        ingest_telemetry()
                        ar.update()
                    except Exception:
                        pass
                time.sleep(0.1)

            try:
                (inbox / f"beat_{tag}.json").unlink()
            except Exception:
                pass

            if not running:
                break
            if not isinstance(reply, dict):
                stats["timeouts"] += 1
                logj(logf, event="timeout", seq=seq, stats=dict(stats))
                continue

            out = {"seq": seq}
            line = reply.get("line")
            if isinstance(line, str) and line.strip():
                line = line.strip()
                if len(line) > 600:
                    line = line[:597] + "..."
                out["line"] = line
            action = reply.get("action")
            if isinstance(action, dict) and action:
                if ag is not None:
                    try:
                        action = ag.validate(action)
                    except Exception:
                        pass
                if action:
                    out["action"] = action
            elif isinstance(action, str) and action.strip():
                out["action"] = {"name": action.strip()}

            # spoken length (seconds) of the rendered clip, when the writer
            # voiced the line. The game paces her next line off this, not a
            # fixed timer.
            try:
                _dur = float(reply.get("dur_s") or 0.0)
            except (TypeError, ValueError):
                _dur = 0.0
            if _dur > 0:
                out["dur_s"] = round(_dur, 2)

            # auto-pout: she sulks on her own when he keeps ignoring her bids
            if ag is not None and getattr(ag, "auto_pout_due", False):
                try:
                    ag.auto_pout_due = False
                    ag.pouting = True
                    oa = out.get("action") if isinstance(out.get("action"), dict) else {}
                    oa["pout"] = True
                    out["action"] = oa
                    logj(logf, event="auto_pout", seq=seq)
                except Exception:
                    pass

            # pout lift: a keypress broke the sulk — tell the game to drop the visual now
            if ag is not None and getattr(ag, "pout_lift_due", False):
                try:
                    ag.pout_lift_due = False
                    oa = out.get("action") if isinstance(out.get("action"), dict) else {}
                    if "pout" not in oa:   # don't clobber a fresh pout she chose this beat
                        oa["pout"] = False
                        out["action"] = oa
                    logj(logf, event="pout_lift", seq=seq)
                except Exception:
                    pass

            if len(out) == 1:
                stats["dropped"] += 1
                logj(logf, event="empty_reply", seq=seq, stats=dict(stats))
                continue

            try:
                if WIN32:
                    _win32_send(out)
                else:
                    tx.write(json.dumps(out, separators=(",", ":"), default=str) + "\n")
                    tx.flush()
                stats["replied"] += 1
            except Exception as e:
                stats["dropped"] += 1
                logj(logf, event="tx_fail", seq=seq, err=str(e), stats=dict(stats))
                continue

            # v10: the exchange. Her clip + his clip queue as a unit; order
            # depends on who opened (reply["fiend_first"]). The browser
            # overlaps them — stepping over each other's thoughts. His text
            # never enters the reply; invisible dialogue, voice only.
            _clips = []
            clip = reply.get("clip")
            if isinstance(clip, str) and clip:
                _clips.append((clip, None))
            fclip = reply.get("fiend_clip")
            if isinstance(fclip, str) and fclip:
                if reply.get("fiend_first"):
                    _clips.insert(0, (fclip, "fiend"))
                else:
                    _clips.append((fclip, "fiend"))
            for _clip, _speaker in _clips:
                clip_p = clips / Path(_clip).name
                if clip_p.exists():
                    _entry = {"idx": manifest_idx, "seq": seq,
                              "clip": clip_p.name, "t": round(time.time(), 3)}
                    if _speaker:
                        _entry["speaker"] = _speaker
                    manifest.write(json.dumps(_entry) + "\n")
                    manifest.flush()
                    manifest_idx += 1
                else:
                    logj(logf, event="clip_missing", seq=seq, clip=_clip,
                         speaker=_speaker or "jasmine")

            # v9: foley SFX the writer named for this beat (newsounds lib).
            sfx = reply.get("sfx")
            if isinstance(sfx, str) and sfx.strip():
                try:
                    if _handle_sfx(sfx, clips, manifest, logf, manifest_idx):
                        manifest_idx += 1
                except Exception as e:
                    logj(logf, event="sfx_error", error=str(e)[:120])

            # v10.8: the writer's toot pick. deck_writer.agency_play returns
            # {"toot": flavor}, which lands in reply["action"]["toot"].
            # Nothing consumed it before (the game registers no "toot"
            # action handler — only "pose" and "flash" exist), so
            # writer-driven toots were completely silent even though the
            # _handle_toot -> manifest -> browser chain works fine.
            _toot_action = reply.get("action")
            _toot_flavor = (_toot_action.get("toot")
                            if isinstance(_toot_action, dict) else None)
            if isinstance(_toot_flavor, str) and _toot_flavor.strip():
                try:
                    _handle_toot({"flavor": _toot_flavor}, clips, manifest,
                                 logf, manifest_idx)
                    manifest_idx += 1
                except Exception as e:
                    logj(logf, event="toot_error", error=str(e)[:120])

            logj(logf, event="replied", seq=seq,
                 has_line="line" in out, has_action="action" in out,
                 action=out.get("action"),
                 meter=round(ag.meter, 1) if ag is not None else None,
                 clip=clip if isinstance(clip, str) else None,
                 stats=dict(stats))

            # v10.10.2: keep the browser status bar honest — /api/status
            # reads this file, and it used to appear only at shutdown.
            try:
                _now = time.time()
                if _now - _last_stats_write > 2.0:
                    _last_stats_write = _now
                    (sess / "director_stats.json").write_text(
                        json.dumps({"stats": stats, "t": round(_now, 1)}))
            except Exception:
                pass

    logj(logf, event="director_down", stats=stats)
    try:
        (sess / "director_stats.json").write_text(json.dumps({"stats": stats, "ended": time.time()}, indent=1))
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
