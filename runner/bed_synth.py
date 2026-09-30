#!/usr/bin/env python3
"""
bed_synth.py — procedural intimacy bed generator.

Replaces the single looping bed_intimacy.mp3 with a small generative engine.
Each render is a warm, evolving ambience — not a looped clip, not noise.

Layers (all subtle, all lowpassed):
  1. Warm body — brown noise, lowpassed ~180Hz, breathing LFO (0.1-0.15Hz)
  2. Pulse — soft low thump at 58-72 BPM, like a heartbeat heard through skin
  3. Pad — detuned low sines (A2+E3+B2) with slow beating, very quiet
  4. Rustle — sparse fabric-like filtered noise bursts, random but gentle
  5. Swell — slow random-walk amplitude on the whole mix, so it breathes

Usage:
  python bed_synth.py --duration 25 --intensity 0.5 --seed 7 --out bed_warm.mp3
  intensity 0.0-1.0: 0.3=warming, 0.6=close, 0.85=peak

Design notes (Andrew's call):
  - Everything is rolled off hard above ~2kHz. No hiss, no clank.
  - The loop breathes; it never bangs. Pulse stays under the warmth.
  - Different seeds = different nights, same room.
"""
import argparse
import subprocess
import shutil
import sys
from pathlib import Path
import numpy as np

SR = 44100

def _brown_noise(n, rng):
    # leaky integrator brown-ish
    white = rng.standard_normal(n).astype(np.float64)
    brown = np.zeros(n, dtype=np.float64)
    last = 0.0
    for i in range(n):
        last = (last + 0.02 * white[i]) / 1.02
        brown[i] = last
    # normalize to -1..1
    brown *= 3.5
    # soft clip
    brown = np.tanh(brown * 0.8)
    return brown

def _one_pole_lowpass(x, alpha):
    y = np.zeros_like(x)
    last = 0.0
    for i in range(len(x)):
        last += alpha * (x[i] - last)
        y[i] = last
    return y

def _soft_thump(sr, freq=55.0, dur=0.35):
    n = int(sr * dur)
    t = np.arange(n) / sr
    env = np.exp(-t * 9.0)
    tone = np.sin(2 * np.pi * freq * t) * env
    # add a touch of 2nd harmonic for body
    tone += 0.3 * np.sin(2 * np.pi * freq * 2 * t) * np.exp(-t * 12.0)
    return tone * 0.6

def generate_bed(duration_s=25.0, intensity=0.5, seed=0):
    rng = np.random.default_rng(seed)
    n = int(SR * duration_s)
    t = np.arange(n) / SR

    intensity = float(np.clip(intensity, 0.0, 1.0))

    # ---- 1. Warm body: brown noise lowpassed, breathing ----
    brown = _brown_noise(n, rng)
    warm = _one_pole_lowpass(brown, alpha=0.04)  # ~180Hz-ish
    # breathing LFO — integer cycles so it loops cleanly
    breath_hz = 0.11 + 0.03 * intensity
    cycles = max(1, round(duration_s * breath_hz))
    breath_hz = cycles / duration_s
    breath = 0.75 + 0.25 * np.sin(2 * np.pi * breath_hz * t)
    warm = warm * breath * (0.55 + 0.25 * intensity)

    # ---- 2. Pulse: soft heartbeat under the warmth ----
    bpm = 58 + 14 * intensity
    beat_period = 60.0 / bpm
    thump = _soft_thump(SR)
    pulse = np.zeros(n)
    # integer beats for loopability
    n_beats = int(duration_s / beat_period)
    for b in range(n_beats):
        # slight humanization, but keep loop seam safe by not humanizing first/last beat
        jitter = (rng.standard_normal() * 0.02) if 0 < b < n_beats - 1 else 0.0
        idx = int((b * beat_period + jitter) * SR)
        if idx + len(thump) < n:
            # velocity varies gently
            vel = 0.5 + 0.5 * (0.6 + 0.4 * np.sin(2 * np.pi * b / max(1, n_beats)))
            pulse[idx:idx+len(thump)] += thump * vel
    pulse = _one_pole_lowpass(pulse, alpha=0.12)
    pulse *= 0.28 + 0.22 * intensity  # stays under the warmth

    # ---- 3. Pad: low detuned sines, very quiet ----
    # A2 110Hz, E3 164.81Hz, B2 123.47Hz — warm open fifth stack
    pad_freqs = [110.0, 123.47, 164.81]
    pad = np.zeros(n)
    for f in pad_freqs:
        # slow beating via slight detune
        detune = 1.0 + (rng.standard_normal() * 0.0008)
        ph = 2 * np.pi * f * detune * t + rng.uniform(0, 2*np.pi)
        # slow swell, integer cycles
        swell_cycles = max(1, round(duration_s * 0.05))
        swell = 0.6 + 0.4 * np.sin(2*np.pi*swell_cycles*t/duration_s + rng.uniform(0, 6.28))
        pad += np.sin(ph) * swell
    pad /= len(pad_freqs)
    pad *= 0.08 + 0.05 * intensity

    # ---- 4. Rustle: sparse fabric bursts ----
    rustle = np.zeros(n)
    # density scales with intensity, but stays sparse
    n_bursts = int(4 + 10 * intensity)
    for _ in range(n_bursts):
        start = rng.integers(0, n - SR//2)
        blen = rng.integers(int(SR*0.25), int(SR*0.7))
        if start + blen >= n:
            continue
        burst_noise = rng.standard_normal(blen)
        # bandpass-ish: lowpass fairly open, then subtract lowpassed version for air
        soft = _one_pole_lowpass(burst_noise, alpha=0.25)
        env = np.hanning(blen)
        # keep it VERY quiet
        rustle[start:start+blen] += soft * env * 0.12

    # ---- 5. Whole-mix slow swell (random walk, loop-safe) ----
    # random walk with pull to center, then lowpass hard
    walk = np.cumsum(rng.standard_normal(n) * 0.002)
    walk = _one_pole_lowpass(walk, alpha=0.002)
    walk = np.tanh(walk * 0.7)
    swell_mix = 0.85 + 0.15 * walk
    # normalize swell to 0.75..1.0 range
    swell_mix = 0.75 + 0.25 * (swell_mix - swell_mix.min()) / (swell_mix.max() - swell_mix.min() + 1e-6)

    mix = (warm + pulse + pad + rustle) * swell_mix

    # ---- master: gentle glue ----
    # soft clip, normalize to -18dBFS-ish headroom for bed-under-everything
    mix = np.tanh(mix * 1.1)
    peak = np.max(np.abs(mix)) + 1e-6
    target = 0.28  # quiet bed, sits under voices
    mix = mix * (target / peak)

    # fades to avoid clicks (not a full loop crossfade — demo clips)
    fade = int(SR * 0.15)
    fade_in = np.linspace(0, 1, fade)
    fade_out = np.linspace(1, 0, fade)
    mix[:fade] *= fade_in
    mix[-fade:] *= fade_out

    return (mix * 32767).astype(np.int16)

def write_mp3(pcm16, out_path):
    out_path = Path(out_path)
    tmp_wav = out_path.with_suffix(".tmp.wav")
    import wave
    with wave.open(str(tmp_wav), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm16.tobytes())
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        # no ffmpeg — leave wav
        tmp_wav.rename(out_path.with_suffix(".wav"))
        return str(out_path.with_suffix(".wav"))
    # quiet mp3, 128k, mono
    cmd = [ffmpeg, "-y", "-v", "error", "-i", str(tmp_wav),
           "-codec:a", "libmp3lame", "-b:a", "128k", "-ac", "1",
           str(out_path)]
    subprocess.run(cmd, check=True)
    tmp_wav.unlink(missing_ok=True)
    return str(out_path)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=float, default=25.0)
    ap.add_argument("--intensity", type=float, default=0.5)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=str, required=True)
    args = ap.parse_args()
    pcm = generate_bed(args.duration, args.intensity, args.seed)
    out = write_mp3(pcm, args.out)
    print(f"wrote {out} ({args.duration}s, intensity={args.intensity}, seed={args.seed})")

if __name__ == "__main__":
    main()
