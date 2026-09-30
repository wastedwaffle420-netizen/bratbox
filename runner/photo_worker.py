#!/usr/bin/env python3
"""Photo terminal worker (ultimate-bratbox sensory layer).

The second window: once he pastes a valid Replicate API key in the web UI,
this daemon thread generates one candid Jasmine photo a minute, cycling the
prompt pool forever. Totally optional — the key lives in memory only, never
on disk, never in a log.

Cost: ~$0.04 a photo at the cheap defaults (~$2.40/hr). The photo window
shows a running count + estimate so it never surprises him.
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

import photo_prompts

try:
    import photo_local_backend as _localmod
except Exception:
    _localmod = None  # local DLC not shipped / not importable

API = "https://api.replicate.com"

# Backend selection: "replicate" (cloud, needs key) or "local" (DLC, no key).
# BRATBOX_PHOTO_BACKEND=auto (default): local when the DLC pack is installed,
# otherwise replicate.
_BACKEND_ENV = os.environ.get("BRATBOX_PHOTO_BACKEND", "auto").strip().lower()
_backend = "replicate"
_local_ready = False

_lock = threading.Lock()
_state = {
    "key_ok": False,
    "running": False,
    "paused": False,
    "count": 0,
    "errors": 0,
    "last_error": "",
    "latest": None,  # {"url","prompt","ts"}
    "started_ts": 0.0,
}
_thread: Optional[threading.Thread] = None
_stop_ev = threading.Event()
_token: Optional[str] = None


def _req(method: str, path: str, payload=None, timeout: int = 30):
    """Authenticated Replicate call. Raises on HTTP error."""
    tok = _token
    if not tok:
        raise RuntimeError("no replicate key")
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        API + path, data=data, method=method,
        headers={"Authorization": f"Token {tok}",
                 "Content-Type": "application/json",
                 "User-Agent": "bratbox-photo-terminal/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode()[:200]
        except Exception:
            detail = ""
        raise RuntimeError(f"replicate {e.code}: {detail}")


def validate_key(token: str) -> bool:
    """True if the key authenticates (hits /v1/account). No persistence."""
    global _token
    token = (token or "").strip()
    if not token:
        return False
    _token = token
    try:
        _req("GET", "/v1/account", timeout=15)
        return True
    except Exception:
        _token = None
        return False


def _model_input_fields() -> set:
    """Read the model's predict schema once; fall back to a sane guess."""
    try:
        m = _req("GET", f"/v1/models/{photo_prompts.MODEL}", timeout=20)
        ver = (m.get("latest_version") or {}).get("id")
        if not ver:
            raise RuntimeError("no latest_version")
        v = _req("GET", f"/v1/models/{photo_prompts.MODEL}/versions/{ver}",
                 timeout=20)
        schema = v.get("openapi_schema", {})
        props = (schema.get("components", {}).get("schemas", {})
                 .get("Input", {}).get("properties", {}))
        return set(props.keys())
    except Exception:
        return set()


def _build_input(prompt: str, fields: set) -> dict:
    want = {"prompt": prompt}
    want.update(photo_prompts.GEN_DEFAULTS)
    if "negative_prompt" in fields:
        want["negative_prompt"] = photo_prompts.NEGATIVE_PROMPT
    if "disable_safety_checker" in fields:
        # her LoRA renders tasteful work better without the hair-trigger
        want["disable_safety_checker"] = False
    if not fields:
        return want
    return {k: v for k, v in want.items() if k in fields or k == "prompt"}


def _resolve_backend() -> str:
    """Pick the backend. 'auto' -> local if the DLC pack is installed."""
    global _backend, _local_ready
    if _BACKEND_ENV == "local":
        _backend = "local"
    elif _BACKEND_ENV == "replicate":
        _backend = "replicate"
    else:  # auto
        if _localmod is not None:
            try:
                if _localmod.is_installed():
                    _backend = "local"
                else:
                    _backend = "replicate"
            except Exception:
                _backend = "replicate"
        else:
            _backend = "replicate"
    _local_ready = False
    return _backend


def _ready() -> bool:
    if _backend == "local":
        return _local_ready
    return bool(_token)


def _generate_local(prompt: str) -> Optional[str]:
    """Generate via the local DLC backend. Returns an image URL or None."""
    if _localmod is None:
        raise RuntimeError("local photo backend not available")
    return _localmod.generate(
        prompt,
        negative_prompt=photo_prompts.NEGATIVE_PROMPT,
        **photo_prompts.GEN_DEFAULTS,
    )


def _generate(prompt: str, fields: set) -> Optional[str]:
    """Create a prediction and wait for it. Returns the image URL or None."""
    if _backend == "local":
        return _generate_local(prompt)
    return _generate_replicate(prompt, fields)


def _generate_replicate(prompt: str, fields: set) -> Optional[str]:
    pred = _req("POST", f"/v1/models/{photo_prompts.MODEL}/predictions",
                {"input": _build_input(prompt, fields)}, timeout=30)
    pid = pred.get("id")
    if not pid:
        raise RuntimeError("no prediction id")
    deadline = time.time() + 240
    status_url = f"/v1/predictions/{pid}"
    while time.time() < deadline and not _stop_ev.is_set():
        time.sleep(4)
        p = _req("GET", status_url, timeout=20)
        st = p.get("status")
        if st == "succeeded":
            out = p.get("output")
            if isinstance(out, list) and out:
                return out[0]
            return out if isinstance(out, str) else None
        if st in ("failed", "canceled"):
            raise RuntimeError(f"prediction {st}: {str(p.get('error'))[:160]}")
    raise RuntimeError("prediction timed out")


def _loop():
    prompts = photo_prompts.all_prompts()
    n = len(prompts)
    idx = 0
    fields: set = set()
    if _backend == "replicate":
        try:
            fields = _model_input_fields()
        except Exception as e:
            with _lock:
                _state["last_error"] = f"schema: {e}"
            fields = set()
    while not _stop_ev.is_set():
        cycle_start = time.time()
        with _lock:
            paused = _state["paused"]
        if not paused and _ready():
            prompt = prompts[idx % n]
            idx += 1
            try:
                url = _generate(prompt, fields)
                if url:
                    with _lock:
                        _state["latest"] = {"url": url, "prompt": prompt,
                                            "ts": round(time.time(), 3)}
                        _state["count"] += 1
                        _state["last_error"] = ""
            except Exception as e:
                with _lock:
                    _state["errors"] += 1
                    _state["last_error"] = str(e)[:200]
        # one photo a minute, measured from cycle start
        while time.time() - cycle_start < photo_prompts.INTERVAL_S:
            if _stop_ev.wait(2.0):
                break
    with _lock:
        _state["running"] = False


def _begin_loop():
    """(Re)start the worker thread. Caller holds no lock requirements."""
    global _thread
    _stop_ev.clear()
    _thread = threading.Thread(target=_loop, daemon=True,
                               name="photo-terminal")
    _thread.start()
    with _lock:
        _state["running"] = True
        _state["started_ts"] = time.time()


def start(token: str) -> bool:
    """Validate + start the worker (Replicate backend). True on valid key."""
    global _thread
    with _lock:
        if _state["running"]:
            _state["paused"] = False
            return _state["key_ok"]
    _resolve_backend()
    if _backend == "local":
        return start_local()
    if not validate_key(token):
        with _lock:
            _state["key_ok"] = False
        return False
    with _lock:
        _state["key_ok"] = True
        _state["paused"] = False
    _begin_loop()
    return True


def start_local() -> bool:
    """Start the worker on the local DLC backend. No key needed."""
    global _local_ready
    _resolve_backend()
    if _backend != "local":
        with _lock:
            _state["last_error"] = "local photo DLC not installed"
        return False
    if _localmod is None:
        with _lock:
            _state["last_error"] = "local photo backend module missing"
        return False
    try:
        if not _localmod.ensure_server():
            raise RuntimeError("local inference server did not come up")
    except Exception as e:
        with _lock:
            _state["last_error"] = f"local backend: {e}"[:200]
        return False
    with _lock:
        if _state["running"]:
            _state["paused"] = False
            return True
        _local_ready = True
        _state["key_ok"] = True  # local needs no key; keeps UI gating simple
        _state["paused"] = False
    _begin_loop()
    return True


def local_status() -> dict:
    """DLC pack presence + server health, for the UI overlay."""
    if _localmod is None:
        return {"installed": False, "server_up": False}
    try:
        return {"installed": bool(_localmod.is_installed()),
                "server_up": bool(_localmod.health()),
                "pack_dir": str(_localmod.pack_dir())}
    except Exception as e:
        return {"installed": False, "server_up": False, "error": str(e)[:160]}


def stop():
    _stop_ev.set()
    with _lock:
        _state["running"] = False
        _state["paused"] = True


def resume():
    with _lock:
        if _state["key_ok"] and not _state["running"]:
            _stop_ev.clear()
            t = threading.Thread(target=_loop, daemon=True,
                                 name="photo-terminal")
            globals()["_thread"] = t
            t.start()
            _state["running"] = True
        _state["paused"] = False


def status() -> dict:
    with _lock:
        s = dict(_state)
    if _backend == "local":
        s["est_cost_usd"] = 0.0  # local pixels are free
    else:
        s["est_cost_usd"] = round(
            s["count"] * photo_prompts.EST_COST_PER_PHOTO_USD, 2)
    s["pool_size"] = len(photo_prompts.PROMPT_CORES)
    s["backend"] = _backend
    s["local"] = local_status()
    s.pop("latest", None)
    return s


def latest() -> dict:
    with _lock:
        return {"latest": _state["latest"],
                "running": _state["running"],
                "paused": _state["paused"],
                "count": _state["count"]}
