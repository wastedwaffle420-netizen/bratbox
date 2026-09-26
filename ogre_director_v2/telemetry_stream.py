#!/usr/bin/env python3
from __future__ import annotations
import json, os, threading, time
from pathlib import Path

class TelemetryStream:
    """Golden-Ledger-compatible append-only JSONL telemetry.

    Named events are flat rows with an ``event`` key. 10 Hz state rows are flat
    mappings with no event key. This is the format consumed by the recovered
    Golden Ledger host and by biometric_cathedral.py.
    """
    def __init__(self, path, hz=10.0):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.hz = max(0.5, float(hz))
        self._last_state_t = 0.0
        self._lock = threading.Lock()

    @classmethod
    def from_env(cls, default_hz=10.0):
        here = Path(__file__).resolve().parent
        run_dir = Path(os.environ.get('LOCKKEY_RUN_DIR', str(here/'runs'/'current')))
        path = Path(os.environ.get('LOCKKEY_TELEMETRY', str(run_dir/'telemetry.jsonl')))
        hz = float(os.environ.get('LOCKKEY_TELEMETRY_HZ', str(default_hz)))
        return cls(path, hz)

    def _write(self, obj):
        row = dict(obj or {})
        row.setdefault('t', time.time())
        payload = json.dumps(row, ensure_ascii=False, separators=(',',':')) + '\n'
        with self._lock:
            with self.path.open('a', encoding='utf-8') as f:
                f.write(payload)
                f.flush()

    def emit(self, obj):
        self._write(dict(obj or {}))

    def emit_event(self, typ, payload=None):
        row = dict(payload or {})
        row['event'] = str(typ)
        self._write(row)

    def emit_state(self, state):
        row = dict(state or {})
        row.pop('event', None)
        self._write(row)

    def emit_state_throttled(self, state, now=None):
        now = time.perf_counter() if now is None else float(now)
        if now - self._last_state_t < 1.0 / self.hz:
            return False
        self._last_state_t = now
        self.emit_state(state)
        return True
