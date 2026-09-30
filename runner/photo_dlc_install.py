#!/usr/bin/env python3
"""Photo-terminal maximalist DLC installer (Windows).

Downloads the ~10.5GB local image-model pack from HuggingFace into
./photo_dlc/, verifies it, installs the Python inference deps (pinned torch
CUDA wheel + exact-match Nunchaku wheel), and writes a manifest. After this,
the photo terminal runs fully offline — no Replicate key, no network calls.

One-time human step: the black-forest-labs/FLUX.1-dev repo is gated.
Accept its license at https://huggingface.co/black-forest-labs/FLUX.1-dev
then pass --hf-token <read-token>.

Usage:
    python runner/photo_dlc_install.py [--pack-dir DIR] [--skip-deps]
                                       [--hf-token TOKEN] [--skip-smoke]

The Jasmine LoRA weights are NOT on HuggingFace (they're yours, on
Replicate). Either:
  - drop jasmine-lora.safetensors into photo_dlc/models/lora/ yourself, or
  - pass --replicate-key <key> once and the installer pulls it from your
    Replicate model (key is used once, never stored).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# THE PACK — measured 2026-09-29 via the HuggingFace API.
# Total ≈ 10.35 GB + Jasmine LoRA. (The "7GB" estimate was wrong — the
# quantized DiT alone is 6.77GB.)
#
# Layout mirrors a diffusers FLUX.1-dev folder so the pipeline loads fully
# offline after install. BFL files are GATED: one-time license accept at
# https://huggingface.co/black-forest-labs/FLUX.1-dev + a read token
# (--hf-token). Everything else downloads anonymously.
# ---------------------------------------------------------------------------
PACK = [
    # -- quantized DiT (Nunchaku INT4, 6.768 GB) --
    {"repo": "nunchaku-ai/nunchaku-flux.1-dev",
     "file": "svdq-int4_r32-flux.1-dev.safetensors",
     "dest": "models/dit/svdq-int4_r32-flux.1-dev.safetensors",
     "bytes": 6768000000, "gated": False},
    # -- quantized T5-XXL (Nunchaku AWQ INT4, 2.987 GB; mandatory — FP16 T5
    #    is 9.5GB and can't live in 16GB RAM next to everything else) --
    {"repo": "mit-han-lab/nunchaku-t5",
     "file": "awq-int4-flux.1-t5xxl.safetensors",
     "dest": "models/text/awq-int4-flux.1-t5xxl.safetensors",
     "bytes": 2987000000, "gated": False},
    # -- CLIP-L (0.246 GB) -> diffusers text_encoder slot --
    {"repo": "comfyanonymous/flux_text_encoders",
     "file": "clip_l.safetensors",
     "dest": "models/flux-dev/text_encoder/diffusion_pytorch_model.safetensors",
     "bytes": 246000000, "gated": False},
    # -- BFL gated pieces (tokenizers, scheduler, VAE) --
    {"repo": "black-forest-labs/FLUX.1-dev",
     "file": "vae/diffusion_pytorch_model.safetensors",
     "dest": "models/flux-dev/vae/diffusion_pytorch_model.safetensors",
     "bytes": 335000000, "gated": True},
    {"repo": "black-forest-labs/FLUX.1-dev",
     "file": "vae/config.json",
     "dest": "models/flux-dev/vae/config.json", "gated": True},
    {"repo": "black-forest-labs/FLUX.1-dev",
     "file": "model_index.json",
     "dest": "models/flux-dev/model_index.json", "gated": True},
    {"repo": "black-forest-labs/FLUX.1-dev",
     "file": "scheduler/scheduler_config.json",
     "dest": "models/flux-dev/scheduler/scheduler_config.json", "gated": True},
    {"repo": "black-forest-labs/FLUX.1-dev",
     "file": "text_encoder/config.json",
     "dest": "models/flux-dev/text_encoder/config.json", "gated": True},
    {"repo": "black-forest-labs/FLUX.1-dev",
     "file": "tokenizer/merges.txt",
     "dest": "models/flux-dev/tokenizer/merges.txt", "gated": True},
    {"repo": "black-forest-labs/FLUX.1-dev",
     "file": "tokenizer/special_tokens_map.json",
     "dest": "models/flux-dev/tokenizer/special_tokens_map.json", "gated": True},
    {"repo": "black-forest-labs/FLUX.1-dev",
     "file": "tokenizer/tokenizer_config.json",
     "dest": "models/flux-dev/tokenizer/tokenizer_config.json", "gated": True},
    {"repo": "black-forest-labs/FLUX.1-dev",
     "file": "tokenizer/vocab.json",
     "dest": "models/flux-dev/tokenizer/vocab.json", "gated": True},
    {"repo": "black-forest-labs/FLUX.1-dev",
     "file": "tokenizer_2/special_tokens_map.json",
     "dest": "models/flux-dev/tokenizer_2/special_tokens_map.json", "gated": True},
    {"repo": "black-forest-labs/FLUX.1-dev",
     "file": "tokenizer_2/spiece.model",
     "dest": "models/flux-dev/tokenizer_2/spiece.model", "gated": True},
    {"repo": "black-forest-labs/FLUX.1-dev",
     "file": "tokenizer_2/tokenizer.json",
     "dest": "models/flux-dev/tokenizer_2/tokenizer.json", "gated": True},
    {"repo": "black-forest-labs/FLUX.1-dev",
     "file": "tokenizer_2/tokenizer_config.json",
     "dest": "models/flux-dev/tokenizer_2/tokenizer_config.json", "gated": True},
]
PACK_VERSION = "dlc-1-nunchaku"

# Plain-pip deps. torch + nunchaku are handled separately (pinned CUDA wheel
# + exact-match GitHub wheel — never `pip install nunchaku`, the PyPI name
# is an unrelated package).
PIP_DEPS = [
    "diffusers>=0.32",
    "huggingface_hub>=0.26",
    "accelerate",
    "safetensors",
    "sentencepiece",
    "protobuf",
]
TORCH_VERSION = "2.8.0"          # CUDA 12.8 wheel; sm_75 (Turing) supported
TORCH_INDEX = "https://download.pytorch.org/whl/cu128"


def here() -> Path:
    # repo root = parent of runner/
    return Path(__file__).resolve().parent.parent


def run(cmd, **kw):
    print("+", " ".join(str(c) for c in cmd))
    return subprocess.run(cmd, check=True, **kw)


def pip_install(pkgs, index_url=None):
    if not pkgs:
        return
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade"]
    if index_url:
        cmd += ["--index-url", index_url]
    run(cmd + pkgs)


def install_torch_and_nunchaku():
    """Pinned torch CUDA wheel + the exact-match nunchaku Windows wheel.

    The wheel<->torch<->Python triple must match; resolve it from the
    GitHub releases API instead of hardcoding a version that rots.
    """
    import urllib.request
    tag = f"cp{sys.version_info.major}{sys.version_info.minor}"
    if tag not in ("cp310", "cp311", "cp312", "cp313"):
        sys.exit(f"need Python 3.10-3.13 for the nunchaku wheel (have {tag})")
    print(f"== torch {TORCH_VERSION} (CUDA) ==")
    pip_install([f"torch=={TORCH_VERSION}"], index_url=TORCH_INDEX)

    print("== resolving nunchaku wheel ==")
    req = urllib.request.Request(
        "https://api.github.com/repos/nunchaku-tech/nunchaku/releases/latest",
        headers={"User-Agent": "bratbox-dlc-installer/1.0",
                 "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        rel = json.loads(r.read().decode())
    want_torch = TORCH_VERSION.rsplit(".", 1)[0].replace(".", "")
    cand = None
    for a in rel.get("assets", []):
        name = a.get("name", "")
        if ("win_amd64" in name and tag in name
                and f"torch{want_torch}" in name.replace(".", "")):
            cand = a.get("browser_download_url")
            break
    if not cand:
        names = [a.get("name") for a in rel.get("assets", [])]
        sys.exit("no matching nunchaku wheel in latest release "
                 f"(need win_amd64/{tag}/torch{TORCH_VERSION}); saw:\n"
                 + "\n".join(f"  {n}" for n in names))
    print(f"wheel: {cand}")
    pip_install([cand])


def download_pack(pack_dir: Path, hf_token=None):
    from huggingface_hub import hf_hub_download
    gated_seen = False
    total = 0
    for e in PACK:
        if e.get("gated"):
            gated_seen = True
        dest = pack_dir / e["dest"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and dest.stat().st_size > 0:
            print(f"skip (exists): {e['dest']}")
            total += dest.stat().st_size
            continue
        print(f"--- {e['repo']}/{e['file']} ---")
        try:
            p = hf_hub_download(repo_id=e["repo"], filename=e["file"],
                                local_dir=str(dest.parent),
                                token=hf_token if e.get("gated") else None)
        except Exception as ex:
            if e.get("gated"):
                raise RuntimeError(
                    "gated file failed. One-time human step: accept the "
                    "FLUX.1-dev license at "
                    "https://huggingface.co/black-forest-labs/FLUX.1-dev "
                    "then re-run with --hf-token <read-token>.\n"
                    f"original error: {ex}")
            raise
        got = Path(p)
        if got.resolve() != dest.resolve():
            got.replace(dest)
        got_bytes = dest.stat().st_size
        total += got_bytes
        want = e.get("bytes") or 0
        if want and abs(got_bytes - want) > max(1024 * 1024, want * 0.02):
            print(f"WARNING: size mismatch for {e['file']}: "
                  f"got {got_bytes}, expected {want}")
        else:
            print(f"ok ({got_bytes / 1e9:.2f} GB)")
    print(f"total pack: {total / 1e9:.2f} GB")
    return total


def pull_lora_from_replicate(pack_dir: Path, key: str):
    import urllib.request
    lora_dir = pack_dir / "models" / "lora"
    lora_dir.mkdir(parents=True, exist_ok=True)
    # Resolve the model's latest version, then find a .safetensors weight file.
    # (Adjust MODEL to your Replicate username/model if it ever moves.)
    model = "andrewstaab/jasmine-lora"
    headers = {"Authorization": f"Token {key}"}

    def get(url):
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())

    m = get(f"https://api.replicate.com/v1/models/{model}")
    ver = (m.get("latest_version") or {}).get("id")
    if not ver:
        raise RuntimeError("could not resolve latest model version")
    # Files endpoint lists version artifacts.
    try:
        files = get(
            f"https://api.replicate.com/v1/models/{model}/versions/{ver}/files")
    except Exception:
        files = []
    cand = None
    items = files if isinstance(files, list) else files.get("results", [])
    for f in items:
        name = str(f.get("name") or f.get("filename") or "")
        if name.endswith(".safetensors"):
            cand = (name, f.get("url") or f.get("href"))
            break
    if not cand:
        raise RuntimeError("no .safetensors found on the Replicate model; "
                           "drop the file in manually")
    name, url = cand
    dest = lora_dir / "jasmine-lora.safetensors"
    print(f"downloading LoRA {name} ...")
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as fh:
        shutil.copyfileobj(r, fh)
    print(f"LoRA saved to {dest} ({dest.stat().st_size / 1e6:.1f} MB)")


def write_manifest(pack_dir: Path, total_bytes: int):
    man = {
        "pack_version": PACK_VERSION,
        "backend": "nunchaku-int4",
        "total_bytes": total_bytes,
        "files": [{"repo": e["repo"], "file": e["file"],
                   "dest": e["dest"]} for e in PACK],
        "lora_present": (pack_dir / "models" / "lora" /
                         "jasmine-lora.safetensors").exists(),
    }
    (pack_dir / "DLC_MANIFEST.json").write_text(json.dumps(man, indent=2))
    print("manifest written")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack-dir", default=None,
                    help="install location (default: <repo>/photo_dlc)")
    ap.add_argument("--skip-deps", action="store_true")
    ap.add_argument("--skip-smoke", action="store_true",
                    help="skip the one-image smoke render at the end")
    ap.add_argument("--hf-token", default=None,
                    help="HuggingFace read token (needed once: the BFL repo "
                         "is gated; accept its license first)")
    ap.add_argument("--replicate-key", default=None,
                    help="one-time use: pull the Jasmine LoRA from Replicate")
    args = ap.parse_args()

    if sys.version_info < (3, 10):
        sys.exit("need Python 3.10+")

    pack_dir = Path(args.pack_dir) if args.pack_dir else here() / "photo_dlc"
    pack_dir.mkdir(parents=True, exist_ok=True)
    print(f"pack dir: {pack_dir}")

    if not args.skip_deps:
        print("== installing inference deps ==")
        pip_install(["huggingface_hub", *PIP_DEPS])
        install_torch_and_nunchaku()

    print("== downloading model pack (~10.5GB, grab a coffee) ==")
    if any(e.get("gated") for e in PACK) and not args.hf_token:
        print("NOTE: some files are gated — accept the FLUX.1-dev license at")
        print("https://huggingface.co/black-forest-labs/FLUX.1-dev")
        print("then re-run with --hf-token <your-read-token> if it fails.")
    total = download_pack(pack_dir, hf_token=args.hf_token)

    lora = pack_dir / "models" / "lora" / "jasmine-lora.safetensors"
    if args.replicate_key and not lora.exists():
        print("== pulling Jasmine LoRA from Replicate (one-time) ==")
        try:
            pull_lora_from_replicate(pack_dir, args.replicate_key)
        except Exception as e:
            print(f"LoRA pull failed: {e}")
    if not lora.exists():
        print("!! LoRA missing: drop jasmine-lora.safetensors into")
        print(f"   {pack_dir / 'models' / 'lora'}")
        print("   (from your Replicate model: andrewstaab/jasmine-lora)")

    write_manifest(pack_dir, total)

    if not args.skip_smoke:
        print()
        print("== smoke test: rendering ONE test image ==")
        print("   (first load is slow — ~10GB of weights; this is normal)")
        try:
            run([sys.executable,
                 str(here() / "runner" / "photo_infer_server.py"),
                 "--pack-dir", str(pack_dir), "--smoke-test"])
            print("smoke test passed — cadence numbers are real now, "
                  "not estimates.")
        except Exception as e:
            print(f"smoke test failed: {e}")
            print("the pack is installed but unproven — check the log above.")

    print()
    print("DLC installed. Start the photo terminal from the web UI —")
    print("it will use the local backend automatically (no key needed).")
    print("Override any time with BRATBOX_PHOTO_BACKEND=replicate|local|auto.")


if __name__ == "__main__":
    main()
