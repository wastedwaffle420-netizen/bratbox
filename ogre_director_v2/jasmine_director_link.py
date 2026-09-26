#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
jasmine_director_link.py - optional external "director" for her beats.

Two named pipes (POSIX FIFOs), newline-delimited JSON, one object per line:

  game -> director   game_to_director.fifo
      {"v":1,"seq":7,"beat":"dialogue"|"action","t":<game clock>,"slowmo":0.2,
       "wait_ms":250,
       "phase":   {"mode","stage","pose","loc","contact","lead"},
       "his_input":{"key":"a","age_s":0.4},
       "her":     {"pleasure","momentum","depth","composure","denial","power","intensity"},
       "escalation":{"tier","consent","urgency","consequence","combo","climax","release_state"},
       "candidate":{"speaker":"BIRDSONG","text":"<pool line that plays on timeout>","ttl":2.0}}

  director -> game   director_to_game.fifo
      {"seq":7, "line":"...", "dur_s":4.2, "action":{"pose":"squat","hold":2.5,"flash":true}}
      "line" and "action" are both optional. "seq" echoes the state message;
      a reply without "seq" applies to the oldest waiting beat.
      "line" replaces the candidate pool line VERBATIM (no filtering, leak
      injection, rewriting or truncation). "dur_s" is the spoken length of the
      rendered clip in seconds when the line was voiced; the game paces her
      next line off it (line ends + a short gap), never off a fixed timer.
      "action" is an open dict: it is passed through untouched (stored on
      engine.jd_last_action / engine.jd_action_queue)
      and each top-level key is offered to a handler registered with
      register_action_handler(key, fn). Built-ins: "pose" (+"hold"), "flash".
      Unknown keys are kept, never rejected. A bare string action is offered as
      {"name": <str>} (and as {"pose": <str>} if it names a known pose).

Rules
  * Off unless JASMINE_DIRECTOR=1. Off (or no reader/no reply/any error) means
    the game behaves exactly as before: the existing pool line + scripted
    action play untouched.
  * Never blocks: every pipe op is O_NONBLOCK, and waiting for a reply is done
    by holding her line in a small queue that the frame loop polls. If no reply
    arrives within JASMINE_DIRECTOR_WAIT_MS (default 250, real time, not
    slow-mo scaled) the original line plays.
  * A director line is only *text*. It still goes through the same
    authored_dialogue.queue_line() path, so consent/gating/palette/escalation
    code sees it exactly like a pool line. Actions are limited to a whitelist
    (pose names from pose_config.json, and "flash") and use the game's existing
    surge-pose override, which the game's own locks still outrank.

Env
  JASMINE_DIRECTOR=1            enable
  JASMINE_DIRECTOR_WAIT_MS=250  reply budget per beat (real ms)
  JASMINE_FIFO_DIR=<dir>        default: <LOCKKEY_USER_DATA or ./user_data>/director
  JASMINE_VOICE_GAP_S=0.4       breath between her voiced lines (real seconds).
                                Inter-line pacing = spoken length + this gap only.
"""
from __future__ import annotations

import errno
import json
import os
import time
from collections import deque
from pathlib import Path

_ON = ("1", "true", "yes", "on")
_MAX_PENDING = 4
_REOPEN_EVERY_S = 2.0


def _env_on(name: str) -> bool:
    return str(os.environ.get(name, "") or "").strip().lower() in _ON


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except (TypeError, ValueError):
        return default


def _fifo_dir() -> Path:
    d = os.environ.get("JASMINE_FIFO_DIR", "").strip()
    if d:
        return Path(d)
    base = os.environ.get("LOCKKEY_USER_DATA", "").strip() or str(Path(__file__).resolve().parent / "user_data")
    return Path(base) / "director"


def _known_poses() -> set:
    try:
        p = Path(__file__).resolve().parent / "pose_config.json"
        return set(json.loads(p.read_text(encoding="utf-8")).keys())
    except Exception:
        return {"angled_collapse_low_quality", "coy_cheek", "downward", "face", "front_presence",
                "laying_smile", "outhouse", "squat", "stand_backfacing", "strut"}


class DirectorLink:
    def __init__(self):
        # Windows has no mkfifo; use JSONL files instead of FIFOs.
        self._win32 = os.name == "nt" or not hasattr(os, "mkfifo")
        self.enabled = _env_on("JASMINE_DIRECTOR") and (hasattr(os, "mkfifo") or self._win32)
        try:
            self.wait_s = max(0.0, min(120000.0, float(os.environ.get("JASMINE_DIRECTOR_WAIT_MS", "250")))) / 1000.0
        except ValueError:
            self.wait_s = 0.25
        self.dir = _fifo_dir()
        if self._win32:
            self.out_path = self.dir / "game_to_director.jsonl"
            self.in_path = self.dir / "director_to_game.jsonl"
        else:
            self.out_path = self.dir / "game_to_director.fifo"
            self.in_path = self.dir / "director_to_game.fifo"
        self._out_fd = -1
        self._in_fd = -1
        self._win32_rx_off = 0  # file offset for tailing director_to_game.jsonl
        self._next_try = 0.0
        self._rx = b""
        self._seq = 0
        self._stash = []
        self._pending = deque()      # dicts: seq, deadline, utt, queue_fn
        # Spoken-length pacing (v5): voiced lines are APPLIED on a cadence of
        # (spoken length + voice_gap), never on a fixed timer. Replies may
        # arrive early (the writer renders ahead); they wait their turn here.
        self._apply_q = deque()      # dicts: apply_at, queue_fn, speaker, line, dur
        self._next_apply_t = 0.0     # monotonic; next line may not apply before this
        self._voice_gap_s = max(0.0, _env_float("JASMINE_VOICE_GAP_S", 0.4))
        # AUDIO-ONLY BUILD (2026-09-25): beats still flow to the writer and
        # clips still land in the manifest (voice on), but no line text is
        # ever applied to the screen. Nothing to desync with.
        self.audio_only = _env_on("JASMINE_AUDIO_ONLY")
        # Overflow: when _pending is full, BIRDSONG utterances wait here for a
        # slot instead of bypassing the writer unvoiced. Promoted in poll().
        self._waiting = deque()      # dicts: engine, utt, queue_fn, clock
        self._poses = _known_poses()
        self._last_action_pose = None
        self._handlers = {"pose": self._h_pose, "flash": self._h_flash}
        self.stats = {"sent": 0, "replied": 0, "timeouts": 0, "dropped": 0}

    # ── pipe plumbing (all non-blocking, all exceptions swallowed) ─────────
    def _ensure(self) -> None:
        now = time.monotonic()
        if self._win32:
            # Windows: JSONL files, no FIFOs. Just ensure the dir exists.
            try:
                self.dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            return
        if self._out_fd >= 0 and self._in_fd >= 0:
            return
        if now < self._next_try:
            return
        self._next_try = now + _REOPEN_EVERY_S
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            for p in (self.out_path, self.in_path):
                if not p.exists():
                    os.mkfifo(str(p), 0o600)
            if self._in_fd < 0:
                self._in_fd = os.open(str(self.in_path), os.O_RDONLY | os.O_NONBLOCK)
            if self._out_fd < 0:
                # ENXIO until a director opens the read end; we just retry later.
                self._out_fd = os.open(str(self.out_path), os.O_WRONLY | os.O_NONBLOCK)
        except OSError:
            pass
        except Exception:
            pass

    def _close_out(self) -> None:
        if self._out_fd >= 0:
            try:
                os.close(self._out_fd)
            except OSError:
                pass
        self._out_fd = -1

    def _send(self, obj: dict) -> bool:
        self._ensure()
        try:
            data = (json.dumps(obj, separators=(",", ":"), default=str) + "\n").encode("utf-8")
            if len(data) > 4000:          # keep writes atomic (< PIPE_BUF)
                return False
            if self._win32:
                # Windows: append to JSONL file
                with open(str(self.out_path), "ab") as f:
                    f.write(data)
                self.stats["sent"] += 1
                return True
        except Exception:
            self.stats["dropped"] += 1
            return False
        if self._out_fd < 0:
            return False
        try:
            os.write(self._out_fd, data)
            self.stats["sent"] += 1
            return True
        except BlockingIOError:
            self.stats["dropped"] += 1    # director is slow; drop, never wait
            return False
        except BrokenPipeError:
            self._close_out()             # director went away; reopen later
            return False
        except OSError as e:
            if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                self.stats["dropped"] += 1
            else:
                self._close_out()
            return False

    def _read_replies(self) -> list:
        out = []
        if self._win32:
            # Windows: tail director_to_game.jsonl from last offset
            try:
                with open(str(self.in_path), "rb") as f:
                    f.seek(self._win32_rx_off)
                    chunk = f.read(65536)
                    self._win32_rx_off = f.tell()
                self._rx += chunk
            except FileNotFoundError:
                return out
            except Exception:
                return out
            if len(self._rx) > 65536:
                self._rx = b""
            while b"\n" in self._rx:
                raw, self._rx = self._rx.split(b"\n", 1)
                try:
                    obj = json.loads(raw.decode("utf-8", "replace"))
                    if isinstance(obj, dict):
                        out.append(obj)
                except Exception:
                    continue
            return out
        if self._in_fd < 0:
            return out
        for _ in range(8):
            try:
                chunk = os.read(self._in_fd, 8192)
            except BlockingIOError:
                break
            except OSError:
                break
            if not chunk:                 # no writer connected right now
                break
            self._rx += chunk
        if len(self._rx) > 65536:
            self._rx = b""                # runaway garbage guard
        while b"\n" in self._rx:
            raw, self._rx = self._rx.split(b"\n", 1)
            try:
                obj = json.loads(raw.decode("utf-8", "replace"))
                if isinstance(obj, dict):
                    out.append(obj)
            except Exception:
                continue
        return out

    # ── state snapshot ─────────────────────────────────────────────────────
    def _snapshot(self, engine, beat: str, candidate: dict | None, clock) -> dict:
        g = lambda o, k, d=None: getattr(o, k, d) if o is not None else d
        rs = g(engine, "round_state")
        vibe = g(engine, "vibe")
        nscl = (g(getattr(engine, "nscl", None), "state", {}) or {})
        rhythm = g(g(engine, "scene"), "rhythm")

        def f(o, k, d=0.0):
            try:
                return float(g(o, k, d) or 0.0)
            except Exception:
                return d

        comp = f(rs, "composure", 1.0)
        key = g(engine, "_lk_last_lane_key")
        try:
            key_s = chr(int(key)) if isinstance(key, int) and 32 <= int(key) < 127 else (str(key) if key is not None else "")
        except Exception:
            key_s = ""
        try:
            key_age = max(0.0, float(clock.time()) - float(g(engine, "_lk_last_lane_key_ts", 0.0) or 0.0)) if key is not None else None
        except Exception:
            key_age = None

        snap = {
            "v": 1,
            "seq": 0,
            "beat": beat,
            "t": float(clock.time()),
            "slowmo": float(getattr(clock, "speed", 1.0) or 1.0),
            "wait_ms": int(self.wait_s * 1000),
            "phase": {
                "mode": str(g(engine, "current_mode", "") or ""),
                "stage": str(nscl.get("STAGE", "") or ""),
                "pose": str(nscl.get("POSE_ID", "") or g(g(engine, "lightmap_renderer"), "current_pose", "") or ""),
                "loc": str(nscl.get("LOC", "") or ""),
                "contact": str(nscl.get("CONTACT", "") or ""),
                "lead": str(nscl.get("LEAD", "") or ""),
            },
            "his_input": {"key": key_s, "age_s": key_age},
            "her": {
                "pleasure": f(rs, "her_pleasure"),
                "momentum": f(rs, "momentum"),
                "depth": f(rs, "depth"),
                "composure": comp,
                "denial": max(0.0, min(1.0, 1.0 - comp)),
                "power": f(rs, "power_dynamic"),
                "intensity": f(rhythm, "intensity"),
            },
            "escalation": {
                "tier": int(f(rs, "tier", 0)),
                "consent": str(nscl.get("CONSENT", "GREEN") or "GREEN"),
                "urgency": str(nscl.get("URGENCY", "") or ""),
                "consequence": str(nscl.get("CONSEQUENCE", "") or ""),
                "combo": int(f(vibe, "combo", 0)),
                "climax": bool(g(vibe, "climax_reached", False)),
                "release_state": bool(g(engine, "in_release_state", False)),
            },
        }
        if candidate is not None:
            snap["candidate"] = candidate
        # agency echo: what her kit actually did game-side (observability for
        # the director/writer — proves actions land, not just validate)
        try:
            snap["agency_state"] = {
                "last_move": str(g(engine, "_agency_last_move", "") or ""),
                "tempo": float(g(engine, "_agency_tempo", 1.0) or 1.0),
                "pouting": bool(g(engine, "_agency_pouting", False)),
                "hijack_stolen": int(g(engine, "_agency_hijack_stolen", 0) or 0),
                "weather": str(g(engine, "_agency_weather", "") or ""),
                "finale": bool(g(engine, "_agency_finale", False)),
                "toot_flavor": str(g(engine, "_agency_toot_flavor", "") or ""),
            }
        except Exception:
            pass
        return snap

    # ── engine glue ────────────────────────────────────────────────────────
    def route_line(self, engine, utt, queue_fn, clock) -> None:
        """Called where a released line would be queued. queue_fn(speaker, text, ttl)
        is the game's normal queue_line. Never blocks; every utterance gets
        exactly one queue_fn call, though it may be deferred (voiced replies
        are applied on the spoken-length cadence; overflow waits for a pending
        slot instead of bypassing the writer unvoiced)."""
        try:
            sp = str(getattr(utt, "speaker", "") or "")
            # 2026-09-25 (birdsong build): FIEND rides the writer too, so the
            # TTS operator voices him (mild yarn). Anything else bypasses.
            if (not self.enabled) or sp.upper() not in ("BIRDSONG", "FIEND"):
                queue_fn(utt.speaker, utt.text, float(utt.ttl), False)
                return
            if len(self._pending) >= _MAX_PENDING:
                # Writer is saturated rendering ahead: hold the line for a
                # slot rather than showing it unvoiced. poll() promotes these.
                self.stats["waiting"] = int(self.stats.get("waiting", 0)) + 1
                self._waiting.append({"engine": engine, "utt": utt,
                                      "queue_fn": queue_fn, "clock": clock})
                return
            # Only park a line if some frame loop is actually calling poll(); otherwise
            # (a scene/loop that never polls) it would be stranded, so use the bounded
            # synchronous offer instead. Either way exactly one queue_fn call happens.
            if (time.monotonic() - float(getattr(engine, "_jd_last_poll", 0.0) or 0.0)) > 0.5:
                _t = self.offer_sync(engine, sp, str(utt.text), float(utt.ttl), clock)
                # Audio-only: the beat above already went to the writer; the
                # voice flows via the manifest, so there is no text to show.
                if not self.audio_only:
                    if _t is not None:
                        queue_fn(utt.speaker, _t, float(utt.ttl), True)
                    else:
                        queue_fn(utt.speaker, utt.text, float(utt.ttl), False)
                return
            snap = self._snapshot(
                engine, "dialogue",
                {"speaker": sp, "text": str(utt.text), "ttl": float(utt.ttl)}, clock)
            self._seq += 1
            snap["seq"] = self._seq
            if not self._send(snap):
                queue_fn(utt.speaker, utt.text, float(utt.ttl), False)    # nobody listening: no delay at all
                return
            self._pending.append({"seq": self._seq, "deadline": time.monotonic() + self.wait_s,
                                  "utt": utt, "queue_fn": queue_fn})
        except Exception:
            queue_fn(utt.speaker, utt.text, float(utt.ttl), False)

    def action_beat(self, engine, pose: str, clock) -> None:
        """Informational + optional action reply on her pose changes."""
        try:
            if not self.enabled or pose == self._last_action_pose:
                return
            self._last_action_pose = pose
            snap = self._snapshot(engine, "action", None, clock)
            snap["phase"]["pose"] = str(pose or "")
            self._seq += 1
            snap["seq"] = self._seq
            self._send(snap)
        except Exception:
            pass

    def toot_beat(self, flavor: str) -> None:
        """A toot popped game-side. Tell the director so the browser can play
        the real take (the server has no speakers). No seq: the director
        handles kind=toot outside the dialogue-beat flow. Never blocks."""
        try:
            if not self.enabled:
                return
            flavor = str(flavor or "bashful").lower()
            if flavor not in ("bashful", "submissive", "power"):
                flavor = "bashful"
            self._send({"kind": "toot", "flavor": flavor, "t": time.time()})
        except Exception:
            pass

    def poll(self, engine) -> None:
        """Call once per frame. Applies replies, expires waits. Non-blocking.

        Voiced lines are applied on the spoken-length cadence: each line's
        on-screen time is its actual clip length, and the next line applies
        no earlier than (previous line ends + JASMINE_VOICE_GAP_S). Replies
        that arrive early (writer renders ahead) wait in _apply_q. This is
        real-time pacing, never slow-mo scaled.
        """
        if not self.enabled:
            return
        try:
            try:
                engine._jd_last_poll = time.monotonic()
            except Exception:
                pass
            self._ensure()
            replies = self._stash + self._read_replies()
            self._stash = []
            now = time.monotonic()
            for r in replies:
                seq = r.get("seq")
                target = None
                if isinstance(seq, int):
                    target = next((p for p in self._pending if p["seq"] == seq), None)
                elif self._pending:
                    target = self._pending[0]
                _ln = r.get("line")
                line = _ln if (isinstance(_ln, str) and _ln != "") else None   # verbatim
                if target is not None:
                    self._pending.remove(target)
                    utt = target["utt"]
                    self.stats["replied"] += 1
                    if self.audio_only:
                        pass  # voice is already flowing via the manifest
                    elif line is not None:
                        # Spoken-length pacing: schedule, don't apply now.
                        try:
                            dur = float(r.get("dur_s") or utt.ttl or 2.0)
                        except (TypeError, ValueError):
                            dur = float(getattr(utt, "ttl", 2.0) or 2.0)
                        dur = max(0.5, dur)
                        apply_at = max(now, self._next_apply_t)
                        self._next_apply_t = apply_at + dur + self._voice_gap_s
                        self._apply_q.append({
                            "apply_at": apply_at,
                            "queue_fn": target["queue_fn"],
                            "speaker": utt.speaker,
                            "line": line,
                            "dur": dur,
                        })
                    else:
                        target["queue_fn"](utt.speaker, utt.text, float(utt.ttl), False)
                elif isinstance(seq, int) and seq not in [p["seq"] for p in self._pending]:
                    pass                      # late reply after fallback, or an action-beat reply
                self._apply_action(engine, r.get("action"))
            # promote overflow utterances into freed pending slots (in order)
            while self._waiting and len(self._pending) < _MAX_PENDING:
                w = self._waiting.popleft()
                self.route_line(w["engine"], w["utt"], w["queue_fn"], w["clock"])
            # apply voiced lines whose turn has come (spoken-length cadence)
            while self._apply_q and self._apply_q[0]["apply_at"] <= now:
                a = self._apply_q.popleft()
                if not self.audio_only:
                    a["queue_fn"](a["speaker"], a["line"], a["dur"], True)
            # expire in order
            while self._pending and now >= self._pending[0]["deadline"]:
                p = self._pending.popleft()
                self.stats["timeouts"] += 1
                if not self.audio_only:
                    p["queue_fn"](p["utt"].speaker, p["utt"].text, float(p["utt"].ttl), False)
        except Exception:
            # Any failure: flush waiting lines with their original text.
            while self._pending:
                p = self._pending.popleft()
                if self.audio_only:
                    continue
                try:
                    p["queue_fn"](p["utt"].speaker, p["utt"].text, float(p["utt"].ttl), False)
                except Exception:
                    pass

    def register_action_handler(self, key: str, fn) -> None:
        """fn(engine, value, action_dict) is called for that top-level key of any action.
        Lets tempo/chart/lightmap/body-state handlers be added without touching the schema."""
        self._handlers[str(key)] = fn

    def _apply_action(self, engine, action) -> None:
        if action is None or action == "" or action == {}:
            return
        try:
            if isinstance(action, str):
                act = {"name": action}
                if action in self._poses:
                    act["pose"] = action
            elif isinstance(action, dict):
                act = action                  # passed through untouched
            else:
                act = {"value": action}
            engine.jd_last_action = act
            q = getattr(engine, "jd_action_queue", None)
            if q is None:
                q = engine.jd_action_queue = deque(maxlen=32)
            q.append(act)
            for k, v in act.items():
                h = self._handlers.get(k)
                if h is not None:
                    try:
                        h(engine, v, act)
                    except Exception:
                        pass
        except Exception:
            pass

    # built-in handlers (the game's own locks still outrank these)
    def _h_pose(self, engine, pose, act) -> None:
        if not (isinstance(pose, str) and pose in self._poses):
            return
        try:
            hold = max(0.5, min(8.0, float(act.get("hold", 2.5))))
        except Exception:
            hold = 2.5
        # Same mechanism the game's own surge/slip beats use.
        engine._surge_pose_override = pose
        engine._surge_pose_t = max(float(getattr(engine, "_surge_pose_t", 0.0) or 0.0), hold)

    def _h_flash(self, engine, on, act) -> None:
        if on:
            engine.lightmap_renderer.trigger_flash(2, 0.15)

    def offer_sync(self, engine, speaker: str, text: str, ttl: float, clock):
        """For the modal story renderer (_display_line), which draws synchronously and
        has no per-frame loop to park a line in. Returns the director's line (verbatim)
        or None. Zero delay when disabled / no director attached; otherwise waits at
        most JASMINE_DIRECTOR_WAIT_MS (real ms)."""
        try:
            # 2026-09-25 (birdsong build): FIEND rides the writer too.
            if not self.enabled or str(speaker).upper() not in ("BIRDSONG", "FIEND") or not isinstance(text, str):
                return None
            snap = self._snapshot(engine, "dialogue", {"speaker": str(speaker), "text": text, "ttl": float(ttl)}, clock)
            self._seq += 1
            snap["seq"] = self._seq
            snap["modal"] = True
            if not self._send(snap):
                return None
            deadline = time.monotonic() + self.wait_s
            while time.monotonic() < deadline:
                for r in self._read_replies():
                    seq = r.get("seq")
                    mine = (seq == self._seq) or seq is None
                    if not mine:
                        self._stash.append(r)     # belongs to a parked beat; poll() will take it
                        continue
                    self.stats["replied"] += 1
                    self._apply_action(engine, r.get("action"))
                    ln = r.get("line")
                    return ln if (isinstance(ln, str) and ln != "") else None
                time.sleep(0.002)
            self.stats["timeouts"] += 1
        except Exception:
            pass
        return None

    def close(self) -> None:
        # Flush anything still scheduled/waiting through its queue_fn so no
        # utterance is ever stranded silently. (Audio-only: nothing to show.)
        if self.audio_only:
            self._apply_q.clear()
            self._waiting.clear()
            return
        try:
            while self._apply_q:
                a = self._apply_q.popleft()
                try:
                    a["queue_fn"](a["speaker"], a["line"], a["dur"], True)
                except Exception:
                    pass
            while self._waiting:
                w = self._waiting.popleft()
                try:
                    w["queue_fn"](w["utt"].speaker, w["utt"].text,
                                  float(getattr(w["utt"], "ttl", 2.0) or 2.0), False)
                except Exception:
                    pass
        except Exception:
            pass
        for fd in (self._out_fd, self._in_fd):
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError:
                    pass
        self._out_fd = self._in_fd = -1


_LINK = None


def get_link() -> DirectorLink:
    global _LINK
    if _LINK is None:
        _LINK = DirectorLink()
    return _LINK
