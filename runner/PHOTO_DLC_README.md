# Photo terminal — maximalist DLC spec

The minimalist bratbox build is fully local and offline: voice, dialogue,
intimacy audio, no keys, no network. This DLC adds the one thing minimalism
leaves out: the **photo terminal** — the ambient second window that renders
candid Jasmine photos from the 88-scene prompt pool.

## What it is

A local image-generation backend + a ~10.5GB model pack. The photo terminal's
UI, prompt pool, pause/resume, and cadence logic do not change at all — the
worker just renders pixels on your GPU instead of calling Replicate.

- **Minimalist base** (GitHub repo): everything except image generation.
- **Maximalist DLC** (this): photo terminal, local, free per photo.

## Contents

| Piece | File | Notes |
|---|---|---|
| Backend client | `runner/photo_local_backend.py` | health check, server auto-launch, `generate()` → image URL |
| Inference server | `runner/photo_infer_server.py` | localhost server: Nunchaku INT4 FLUX.1-dev (Turing-tuned) + Jasmine LoRA |
| Worker switch | `runner/photo_worker.py` | `BRATBOX_PHOTO_BACKEND=auto\|local\|replicate`; auto = local when the pack is installed |
| API | `runner/server.py` | `POST /api/photo/local` — starts the terminal, no key |
| UI | `runner/static/photo.html` | `?backend=local` — skips the key prompt, sets warm-up copy |
| Installer | `install_photo_dlc.bat` / `runner/photo_dlc_install.py` | downloads the pack from HuggingFace, installs deps, writes manifest, smoke-tests one render |

## The model pack (~10.5GB, HuggingFace)

GitHub release assets cap at 2GB per file, so the weights live on
HuggingFace, not in the repo. The installer pulls every file and verifies
sizes (see `PACK` in `photo_dlc_install.py`):

- Nunchaku INT4 quantized FLUX.1-dev transformer — 6.77GB
  (`nunchaku-ai/nunchaku-flux.1-dev`)
- Nunchaku AWQ INT4 T5-XXL — 2.99GB (`mit-han-lab/nunchaku-t5`).
  The quantized T5 is mandatory, not optional: FP16 T5 is 9.5GB and can't
  live in 16GB RAM next to everything else.
- CLIP-L — 0.25GB (`comfyanonymous/flux_text_encoders`)
- FLUX VAE + tokenizers + scheduler — 0.34GB
  (`black-forest-labs/FLUX.1-dev`, **gated**)
- Jasmine LoRA (`jasmine-lora.safetensors`) — **not on HF**. Drop it into
  `photo_dlc/models/lora/` yourself, or pass `--replicate-key` once and the
  installer pulls it from your Replicate model (key used once, never stored).

Total download: ~10.5GB. Disk needed: ~12GB free.

**Gated-repo step (one time):** accept the FLUX.1-dev license at
https://huggingface.co/black-forest-labs/FLUX.1-dev, then run the installer
with `--hf-token <your-read-token>`. Install-time only; generation stays
fully local.

## Install

1. Extract the bratbox build, run `build_exe.bat` once (minimalist base).
2. Accept the FLUX license (link above), make a HF read token.
3. Run `install_photo_dlc.bat` (or
   `python runner/photo_dlc_install.py --hf-token TOKEN`). Go make coffee.
   The installer pins torch 2.8 (CUDA) + the exact-match Nunchaku Windows
   wheel for your Python — never `pip install nunchaku` (unrelated package).
4. Drop in the LoRA if the installer didn't pull it.
5. The installer renders **one smoke-test image** at the end — that render
   is the real cadence number for your card, replacing the 60–120s estimate.
6. Open bratbox, hit the photo window toggle — it starts locally, no key.

## Behavior notes

- **Cadence relaxes.** Replicate did a strict photo-a-minute. Local on a
  2080 SUPER does a photo every few minutes (estimate 60–120s per 768×1024
  render at 22 steps; the smoke test measures the truth). The worker's loop
  already paces itself (it never stacks renders), and the window just shows
  the latest whenever it lands.
- **Cost goes to zero.** The running-cost readout reports `$0.00` on local.
- **Maturity gate unchanged.** Every prompt still opens with the HARD
  maturity block. Note: FLUX.1-dev takes no negative prompt — the maturity
  gate rides entirely in the positive prompt, which the worker already does.
- **Fully offline after install.** Nothing phones home. The doomsday-prep
  principle holds: your PC dies, you re-download the repo + the HF pack,
  you're back.

## Troubleshooting

- `local photo DLC not installed` → run the installer; check
  `photo_dlc/DLC_MANIFEST.json` exists.
- `local inference server did not come up` → the server log is at
  `photo_dlc/infer_server.log`. First launch compiles/loads weights and
  can take several minutes — that's normal, not a hang.
- Out-of-memory on 8GB → the installer picks the Turing-tuned INT4 stack
  for the 2080 SUPER; if you edited `PACK`, you picked wrong. Re-run stock.
- `LoRA format not recognized` → run the one-time converter the error
  message prints (`python -m nunchaku.lora.flux.convert ...`), then restart.
- Slow photos → fewer steps is the lever (`GEN_DEFAULTS["num_steps"]`
  in `photo_prompts.py`). Quality/cadence tradeoff is yours.
- 16GB RAM is the real bottleneck, not VRAM — close the heavy stuff on
  first launch while ~10GB of weights page in.

## For the refactor (main chat)

This DLC is additive: new files + a backend switch in `photo_worker.py`
(all existing signatures keep working). Nothing here fights the
ElevenLabs removal or the local-voice default. If Replicate gets cut
from the worker entirely later, delete `_generate_replicate` and the
`/api/photo/key` endpoint — the local path stands alone.
