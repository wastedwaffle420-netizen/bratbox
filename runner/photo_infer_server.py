#!/usr/bin/env python3
"""Photo-terminal maximalist DLC — local inference server (localhost only).

Wraps a quantized FLUX.1-dev pipeline (Nunchaku INT4, Turing-tuned for the
RTX 2080 SUPER) + the Jasmine LoRA, behind a tiny HTTP protocol consumed by
runner/photo_local_backend.py:

    GET  /health    -> {"ok": true, "ready": true}
    POST /generate  -> {"url": "http://127.0.0.1:PORT/img/<f>.png"}
         body: {"prompt", "negative_prompt" (accepted, ignored — FLUX-dev
                has no negative input; the maturity gate lives in the
                positive prompt), "width", "height", "steps", "guidance"}
    GET  /img/<f>   -> PNG bytes

Launched automatically by photo_local_backend.ensure_server(); never exposed
past localhost. First launch loads ~10GB of weights — slow, normal, logged.

Usage:
    python runner/photo_infer_server.py --pack-dir photo_dlc --port 8189
    python runner/photo_infer_server.py --pack-dir photo_dlc --smoke-test
        (renders one test image and exits — run once before trusting cadence)
"""
from __future__ import annotations

import argparse
import functools
import json
import os
import random
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_pack_dir: Path = Path(".")
_port: int = 8189
_pipe = None
_pipe_lock = threading.Lock()
_gen_lock = threading.Lock()   # one render at a time; concurrent calls queue
_ready = False
_lora_ok = False


def _log(msg: str):
    print(f"[infer] {msg}", flush=True)


def load_pipeline(pack_dir: Path):
    """Build the Nunchaku INT4 FLUX pipeline (official Turing recipe)."""
    global _lora_ok
    import torch
    from diffusers import FluxPipeline
    from nunchaku import NunchakuFluxTransformer2dModel, NunchakuT5EncoderModel
    from nunchaku.lora.flux.compose import compose_lora

    models = pack_dir / "models"
    dit = models / "dit" / "svdq-int4_r32-flux.1-dev.safetensors"
    t5 = models / "text" / "awq-int4-flux.1-t5xxl.safetensors"
    lora = models / "lora" / "jasmine-lora.safetensors"
    flux_dev = models / "flux-dev"  # local diffusers-layout dir (assembled by installer)

    for p in (dit, t5, flux_dev / "model_index.json"):
        if not p.exists():
            raise RuntimeError(f"missing pack file: {p} — re-run install_photo_dlc.bat")

    _log("loading quantized DiT (fp16, Turing attention, CPU offload)…")
    transformer = NunchakuFluxTransformer2dModel.from_pretrained(
        str(dit), offload=True, torch_dtype=torch.float16)
    transformer.set_attention_impl("nunchaku-fp16")

    if lora.exists():
        _log("composing Jasmine LoRA…")
        try:
            transformer.update_lora_params(compose_lora([(str(lora), 1.0)]))
            _lora_ok = True
        except Exception as e:
            raise RuntimeError(
                "LoRA format not recognized by compose_lora. One-time fix:\n"
                f"  python -m nunchaku.lora.flux.convert --lora-format diffusers "
                f"--lora-path {lora}\n"
                f"then restart. Original error: {e}")
    else:
        _log("WARNING: jasmine-lora.safetensors not found — rendering WITHOUT her identity.")

    _log("loading quantized T5-XXL…")
    text_encoder_2 = NunchakuT5EncoderModel.from_pretrained(str(t5))

    _log("assembling FLUX pipeline (local diffusers dir, no network)…")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    pipe = FluxPipeline.from_pretrained(
        str(flux_dev),
        transformer=transformer,
        text_encoder_2=text_encoder_2,
        torch_dtype=torch.float16,
    )
    pipe.enable_sequential_cpu_offload()
    _log("pipeline ready")
    return pipe


def render(prompt: str, width: int, height: int,
           steps: int, guidance: float) -> Path:
    import torch
    outdir = _pack_dir / "out"
    outdir.mkdir(parents=True, exist_ok=True)
    seed = random.randint(0, 2**31 - 1)
    _log(f"render {width}x{height} steps={steps} guidance={guidance} seed={seed}")
    t0 = time.time()
    with _gen_lock:
        img = _pipe(
            prompt, height=height, width=width,
            num_inference_steps=steps, guidance_scale=guidance,
            generator=torch.Generator().manual_seed(seed),
            max_sequence_length=256,
        ).images[0]
    dt = time.time() - t0
    _log(f"done in {dt:.0f}s")
    name = f"jasmine_{int(time.time())}_{seed % 100000}.png"
    p = outdir / name
    img.save(p)
    return p


class Handler(BaseHTTPRequestHandler):
    server_version = "bratbox-photo-infer/1"

    def _send_json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/health":
            self._send_json({"ok": True, "ready": _ready, "lora": _lora_ok})
            return
        if parsed.path.startswith("/img/"):
            name = os.path.basename(urllib.parse.unquote(parsed.path))
            if not name.endswith(".png") or "/" in name or "\\" in name:
                self.send_error(400)
                return
            p = _pack_dir / "out" / name
            if not p.exists():
                self.send_error(404)
                return
            data = p.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_error(404)

    def do_POST(self):
        if urllib.parse.urlparse(self.path).path != "/generate":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode() or "{}")
        except Exception:
            self._send_json({"error": "bad json"}, 400)
            return
        prompt = str(body.get("prompt") or "")
        if not prompt:
            self._send_json({"error": "empty prompt"}, 400)
            return
        try:
            # FLUX.1-dev takes no negative prompt; the maturity gate is baked
            # into every positive prompt by the worker. Accepted and ignored.
            p = render(
                prompt,
                width=int(body.get("width") or 768),
                height=int(body.get("height") or 1024),
                steps=int(body.get("steps") or 22),
                guidance=float(body.get("guidance") or 3.5),
            )
        except Exception as e:
            _log(f"render failed: {e}")
            self._send_json({"error": str(e)[:300]}, 500)
            return
        self._send_json({"url": f"http://127.0.0.1:{_port}/img/{p.name}"})

    def log_message(self, *a):
        pass  # keep the log clean; we log renders ourselves


def main():
    global _pack_dir, _port, _pipe, _ready
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack-dir", required=True)
    ap.add_argument("--port", type=int, default=8189)
    ap.add_argument("--smoke-test", action="store_true",
                    help="render one test image and exit")
    args = ap.parse_args()
    _pack_dir = Path(args.pack_dir)
    _port = args.port

    _log("starting (this takes a while the first time — ~10GB of weights)…")
    _pipe = load_pipeline(_pack_dir)
    _ready = True

    if args.smoke_test:
        p = render(
            "JASMINE, a mature adult woman in her late twenties, candid "
            "laugh on a couch, warm lamp light, photorealistic",
            768, 1024, 22, 3.5)
        print(f"SMOKE TEST OK: {p}")
        return

    srv = ThreadingHTTPServer(("127.0.0.1", _port), Handler)
    _log(f"serving on 127.0.0.1:{_port}")
    srv.serve_forever()


if __name__ == "__main__":
    main()
