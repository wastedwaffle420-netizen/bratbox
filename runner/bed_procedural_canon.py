"""Procedural canon intimacy bed — seeded variations on the v7 canon (2026-09-30).

Based on Andrew's relabeled usable set (14 sounds, screenshots 2026-09-30):
  10 plop into suckle.wav
  11 pooping suction.wav
  12 really hot suction sex sounds, during orgasm.wav
  13 really wet sex sound, faint, gross and real. good..wav
  14 2nd organic sex + bed.wav
  15 bed sound with organic sex sound.wav
  16 slightly more primal sex sound.wav
  17 SQUELCH.wav
  18 plap,plap.wav
  19 poop or sex sounds.wav
  20 sack splitting bed sound + sex sound.wav
  22 Excited sucksucksuck BJ.wav
  23 deepthroat.wav
  24 near climax sucking.wav

Design (faithful to canon v7 structure in build_bed.py):
  1. KEYNOTE: 18 <-> 10 alternating ~1.0s, straight through (repetition is fine, ONLY on good sounds)
  2. bed base: 14 / 15 / 20 as sparse bed hits
  3. suction chatter: 11 / 13 / 16 / 19 / 17 in rotation, density by phase
  4. BJ texture: 24 / 22 / 23 under the peak (low, as texture)
  5. peak (29-36s): wet -> primal -> suction -> hot orgasm (12) -> SQUELCH once -> wet again
  6. SPERM PUMP (36.4s): 20 layered x3, each hit starting 0.38s after the last (pump, not wallop)
  7. settle: sparse 10 accents + keynote to end

Emotional brief (his): Fiend is ONLY in control — lovingly, animalistically,
earnestly humiliating. No glass, no washing machine. Keep it earful all the way through.

Seeded RNG => reproducible, reusable. Seed 11 = closest to canon v7.
No soundfile/scipy dependency — uses ffmpeg + numpy + wave only.
"""
import subprocess
import wave
import numpy as np
import os
import sys

SR = 44100
SDIR = "/home/hatch/workspace/sfx/rose/verified/NEWSOUNDS--VERIFIED"
DUR = 48.0

# number -> filename (from his screenshots)
USABLE = {
    10: "plop into suckle.wav",
    11: "pooping suction.wav",
    12: "really hot suction sex sounds, during orgasm.wav",
    13: "really wet sex sound, faint, gross and real. good..wav",
    14: "2nd organic sex + bed.wav",
    15: "bed sound with organic sex sound.wav",
    16: "slightly more primal sex sound.wav",
    17: "SQUELCH.wav",
    18: "plap,plap.wav",
    19: "poop or sex sounds.wav",
    20: "sack splitting bed sound + sex sound.wav",
    22: "Excited sucksucksuck BJ.wav",
    23: "deepthroat.wav",
    24: "near climax sucking.wav",
}

def load(num):
    name = USABLE[num]
    path = os.path.join(SDIR, name)
    if not os.path.exists(path):
        raise FileNotFoundError(f"missing {num}: {path}")
    # decode to mono 44100 float32 via ffmpeg
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
        capture_output=True,
    )
    if not proc.stdout:
        raise RuntimeError(f"ffmpeg failed on {path}: {proc.stderr.decode()[:200]}")
    data = np.frombuffer(proc.stdout, dtype=np.float32).astype(np.float64)
    peak = np.max(np.abs(data))
    if peak > 1e-6:
        data = data / peak
    return data

def place(track, snd, t, gain, rng):
    i = int(t * SR)
    j = min(len(track), i + len(snd))
    if 0 <= i < len(track) and j > i:
        g = gain * rng.uniform(0.9, 1.1)
        track[i:j] += snd[: j - i] * g

def phase(t):
    if t < 12:
        return 0
    if t < 28:
        return 1
    if t < 40:
        return 2
    return 3

def build(seed=11, dur=DUR):
    rng = np.random.default_rng(seed)
    print(f"loading 14 usable sounds (seed {seed})...", flush=True)
    s = {n: load(n) for n in USABLE}
    track = np.zeros(int(dur * SR), dtype=np.float64)

    # --- 1. KEYNOTE: 18 <-> 10 alternating, ~1.0s, straight through ---
    t = 1.0
    flip = False
    while t < dur - 1:
        ph = phase(t)
        period = {0: 1.05, 1: 1.0, 2: 0.9, 3: 1.05}[ph]
        place(track, s[10] if flip else s[18], t + rng.uniform(-0.05, 0.05), 0.52, rng)
        flip = not flip
        t += period * rng.uniform(0.97, 1.03)

    # --- 2. bed base: 14 / 15 / 20 sparse ---
    t = 2.0
    bed_pool = [s[14], s[15], s[20]]
    bi = seed % len(bed_pool)
    while t < dur - 4:
        place(track, bed_pool[bi % len(bed_pool)], t + rng.uniform(-0.4, 0.4), 0.30, rng)
        bi += 1
        t += rng.uniform(7.0, 11.0)

    # --- 3. suction chatter: 11 / 13 / 16 / 19 / 17 in rotation, density by phase ---
    t = 0.5
    pool = [s[11], s[13], s[16], s[19], s[17]]
    wi = seed % len(pool)
    while t < dur - 2:
        ph = phase(t)
        gap = {0: 4.5, 1: 2.6, 2: 1.4, 3: 4.0}[ph]
        # keep SQUELCH (17) sparse — it's the exclamation, not the chatter
        snd = pool[wi % len(pool)]
        gain = 0.28 if wi % len(pool) == 4 else 0.36
        place(track, snd, t + rng.uniform(-0.15, 0.15), gain, rng)
        wi += 1
        t += gap * rng.uniform(0.85, 1.15)

    # --- 4. BJ texture under the peak (low, as texture) ---
    place(track, s[24], 26.0 + rng.uniform(-0.3, 0.3), 0.22, rng)
    place(track, s[22], 27.2 + rng.uniform(-0.3, 0.3), 0.18, rng)
    place(track, s[23], 31.0 + rng.uniform(-0.3, 0.3), 0.20, rng)

    # --- 5. the peak: suction at its most diabolical ---
    place(track, s[13], 29.0, 0.55, rng)
    place(track, s[16], 30.5, 0.50, rng)
    place(track, s[11], 32.0, 0.55, rng)
    place(track, s[12], 33.0, 0.62, rng)   # the hot orgasm — the climax
    place(track, s[17], 34.8, 0.60, rng)   # the ONE squelch exclamation — no repeats
    place(track, s[13], 36.0, 0.40, rng)

    # --- 6. sperm pump: 20 layered x3, overlapping (pump, not wallop) ---
    t0 = 36.4
    for k, g in enumerate([0.50, 0.45, 0.40]):
        place(track, s[20], t0 + k * 0.38, g, rng)

    # --- 7. settle: sparse 10 accents breathing between keynote hits ---
    t = 41.0
    while t < dur - 1:
        place(track, s[10], t + rng.uniform(-0.3, 0.3), 0.30, rng)
        t += rng.uniform(3.5, 5.5)

    # normalize to 0.92 peak
    peak = np.max(np.abs(track))
    if peak > 1e-6:
        track = track / peak * 0.92
    return track

def write_wav(path, track):
    track = np.clip(track, -1.0, 1.0)
    pcm = (track * 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())

def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 11
    out = sys.argv[2] if len(sys.argv) > 2 else f"/tmp/canon_bed_seed{seed}.wav"
    track = build(seed=seed)
    write_wav(out, track)
    print(f"wrote {out} ({DUR}s, seed {seed})")

if __name__ == "__main__":
    main()
