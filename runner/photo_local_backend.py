#!/usr/bin/env python3
"""Photo-terminal maximalist DLC — local inference client.

This module is the worker's view of the local backend. It does NOT run the
model itself; it talks to runner/photo_infer_server.py over localhost and
auto-launches it on demand.

The inference server's internal stack (quantized FLUX.1-dev + Jasmine LoRA)
is an implementation detail of photo_infer_server.py. This client only
depends on its tiny HTTP protocol:

    GET  /health            -> {"ok": true}
    POST /generate          -> {"url": "http://127.0.0.1:8189/img/<f>.png"}
         body: {"prompt": str, "negative_prompt": str,
                "width": int, "height": int, "steps": int, "guidance": float}
         (blocks until the render finishes; long timeout is expected)
    GET  /img/<f>           -> the PNG bytes

Pack layout (created by install_photo_dlc.bat):
    photo_dlc/
        DLC_MANIFEST.json
        infer_server.log
        models/
            dit/            quantized transformer
            vae/
            text/           CLIP-L + T5
            lora/           jasmine-lora.safetensors  (his weights)
        out/                rendered photos (served over HTTP)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

INFER_PORT = int(os.environ.get("BRATBOX_PHOTO_INFER_PORT", "8189"))
BASE = f"http://127.0.0.1:{INFER_PORT}"
SERVER_SCRIPT = Path(__file__).resolve().parent / "photo_infer_server.py"

_proc: Optional[subprocess.Popen] = None


def pack_dir() -> Path:
    override = os.environ.get("BRATBOX_PHOTO_DLC_DIR")
    if override:
        return Path(override)
    # repo root = parent of runner/
    return Path(__file__).resolve().parent.parent / "photo_dlc"


def is_installed() -> bool:
    """True when the DLC pack + LoRA are on disk."""
    d = pack_dir()
    man = d / "DLC_MANIFEST.json"
    lora = d / "models" / "lora" / "jasmine-lora.safetensors"
    return man.exists() and lora.exists()


def _http(method: str, path: str, payload=None, timeout: int = 15):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        BASE + path, data=data, method=method,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ctype = r.headers.get("Content-Type", "")
            body = r.read()
            if "json" in ctype:
                return json.loads(body.decode())
            return body
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode()[:200]
        except Exception:
            detail = ""
        raise RuntimeError(f"infer server {e.code}: {detail}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"infer server unreachable: {e}")


def health() -> bool:
    try:
        j = _http("GET", "/health", timeout=5)
        return bool(isinstance(j, dict) and j.get("ok"))
    except Exception:
        return False


def ensure_server(wait_s: int = 900) -> bool:
    """Launch the inference server if needed; wait until healthy."""
    global _proc
    if health():
        return True
    if not is_installed():
        raise RuntimeError("photo DLC pack not installed "
                           "(run install_photo_dlc.bat)")
    if not SERVER_SCRIPT.exists():
        raise RuntimeError("photo_infer_server.py missing from runner/")
    logf = open(pack_dir() / "infer_server.log", "ab")
    _proc = subprocess.Popen(
        [sys.executable, str(SERVER_SCRIPT),
         "--pack-dir", str(pack_dir()), "--port", str(INFER_PORT)],
        stdout=logf, stderr=subprocess.STDOUT,
        creationflags=(subprocess.CREATE_NO_WINDOW
                       if sys.platform == "win32" else 0))
    # First launch loads ~7GB of weights; be patient.
    deadline = time.time() + wait_s
    while time.time() < deadline:
        if _proc.poll() is not None:
            raise RuntimeError(
                f"inference server exited (code {_proc.returncode}); "
                f"see {pack_dir() / 'infer_server.log'}")
        if health():
            return True
        time.sleep(5)
    raise RuntimeError("inference server did not become healthy in time; "
                       f"see {pack_dir() / 'infer_server.log'}")


def generate(prompt: str, negative_prompt: str = "",
             width: int = 768, height: int = 1024,
             num_steps: int = 20, guidance_scale: float = 3.5,
             **_kw) -> Optional[str]:
    """Render one photo locally. Returns an http:// URL or None."""
    ensure_server()
    j = _http("POST", "/generate", {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "width": int(width), "height": int(height),
        "steps": int(num_steps), "guidance": float(guidance_scale),
    }, timeout=1500)
    if isinstance(j, dict):
        return j.get("url")
    return None
