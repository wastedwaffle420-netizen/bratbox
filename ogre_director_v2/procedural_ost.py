#!/usr/bin/env python3
"""
OGRE SHADER - PROCEDURAL OST
"two animals. one room. forever."

Full procedural soundtrack - 12 tracks generated via numpy synthesis.
Inspired by: OMORI (melancholy), Katana Zero (pulse), Hollow Knight (atmosphere)

NO EXTERNAL FILES NEEDED - everything generated on startup (~3 seconds)

BEAT-REACTIVE: Music pulses with gameplay intensity!
"""

from __future__ import annotations  # Deferred type hint evaluation

import time
import threading
import os
import sys
from pathlib import Path


from typing import List, Tuple, Optional, Dict, Callable, TYPE_CHECKING
from dataclasses import dataclass


def _add_local_site_packages() -> None:
    root = Path(__file__).resolve().parent
    candidates = [
        root / ".venv" / "Lib" / "site-packages",
    ]
    for candidate in candidates:
        try:
            if candidate.exists():
                path = str(candidate)
                if path not in sys.path:
                    sys.path.insert(0, path)
        except Exception:
            continue

# Only import numpy types for type checking, not runtime
if TYPE_CHECKING:
    import numpy as np

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    np = None  # Type hint placeholder

try:
    import pygame
    import pygame.mixer
    PYGAME_AVAILABLE = True
except ImportError:
    _add_local_site_packages()
    try:
        import pygame
        import pygame.mixer
        PYGAME_AVAILABLE = True
    except ImportError:
        PYGAME_AVAILABLE = False


if not NUMPY_AVAILABLE:
    print("ERROR: numpy required for procedural OST")
    print("Install with: pip install numpy")
    
if not PYGAME_AVAILABLE:
    print("ERROR: pygame required for audio playback")
    print("Install with: pip install pygame")


SAMPLE_RATE = 44100

# ── LOCKKEY AUDIO CONFIG / HARD MUTE GUARD ─────────────────────────────
# Shared with audio_calibration.py. This makes every OST entry point obey the
# user-facing Music On/Off setting, even if gameplay calls ost_play()/ost_tier()
# repeatedly after mute.
def _audio_config_path() -> Path:
    return Path.home() / ".ogre_shader_audio.json"

def _load_audio_config_safely() -> dict:
    default = {"music_enabled": True, "music_volume": 1.0}
    try:
        p = _audio_config_path()
        if p.exists():
            import json
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                default.update(data)
    except Exception:
        pass
    return default

def _music_enabled_from_config() -> bool:
    # Environment override for portable builds/testing.
    v = os.getenv("LOCKKEY_MUSIC_ENABLED", "").strip().lower()
    if v in ("0", "false", "no", "off", "mute", "muted"):
        return False
    if v in ("1", "true", "yes", "on"):
        return True
    return bool(_load_audio_config_safely().get("music_enabled", True))

def _music_volume_from_config(default: float = 1.0) -> float:
    try:
        return max(0.0, min(1.0, float(_load_audio_config_safely().get("music_volume", default))))
    except Exception:
        return float(default)

def _hard_stop_music_channels():
    try:
        if not PYGAME_AVAILABLE or not pygame.mixer.get_init():
            return
        # FileOST beds live on 0/1; legacy procedural bed on 0. Stop both.
        for i in (0, 1):
            try:
                ch = pygame.mixer.Channel(i)
                ch.set_volume(0.0)
                ch.stop()
            except Exception:
                pass
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
#                              NOTE FREQUENCIES
# ═══════════════════════════════════════════════════════════════════════════════

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

def note_to_freq(note: str, octave: int) -> float:
    """Convert note name + octave to frequency. A4 = 440Hz."""
    # Handle flats
    note = note.upper().replace('DB', 'C#').replace('EB', 'D#').replace('GB', 'F#').replace('AB', 'G#').replace('BB', 'A#')
    try:
        note_idx = NOTE_NAMES.index(note)
    except ValueError:
        note_idx = 9  # Default to A
    semitones_from_a4 = (octave - 4) * 12 + (note_idx - 9)
    return 440.0 * (2 ** (semitones_from_a4 / 12))

# Pre-compute common notes
NOTES = {}
for oct in range(1, 8):
    for i, name in enumerate(NOTE_NAMES):
        semitones = (oct - 4) * 12 + (i - 9)
        NOTES[f"{name}{oct}"] = 440.0 * (2 ** (semitones / 12))

# Chord intervals
CHORD_INTERVALS = {
    'maj': [0, 4, 7],
    'min': [0, 3, 7],
    'dim': [0, 3, 6],
    'aug': [0, 4, 8],
    'maj7': [0, 4, 7, 11],
    'min7': [0, 3, 7, 10],
    'sus2': [0, 2, 7],
    'sus4': [0, 5, 7],
}

# Scale intervals
SCALE_INTERVALS = {
    'major': [0, 2, 4, 5, 7, 9, 11],
    'minor': [0, 2, 3, 5, 7, 8, 10],
    'harmonic_minor': [0, 2, 3, 5, 7, 8, 11],
    'pentatonic': [0, 2, 4, 7, 9],
    'blues': [0, 3, 5, 6, 7, 10],
}


def get_scale(root: str, octave: int, scale_type: str = 'minor') -> List[float]:
    """Get frequencies for a scale."""
    root_freq = NOTES.get(f"{root}{octave}", 440)
    intervals = SCALE_INTERVALS.get(scale_type, SCALE_INTERVALS['minor'])
    return [root_freq * (2 ** (i / 12)) for i in intervals]


def get_chord(root: str, octave: int, chord_type: str = 'min') -> List[float]:
    """Get frequencies for a chord."""
    root_freq = NOTES.get(f"{root}{octave}", 440)
    intervals = CHORD_INTERVALS.get(chord_type, CHORD_INTERVALS['min'])
    return [root_freq * (2 ** (i / 12)) for i in intervals]


# ═══════════════════════════════════════════════════════════════════════════════
#                              WAVE GENERATORS
# ═══════════════════════════════════════════════════════════════════════════════

def gen_sine(freq: float, dur: float, sr: int = SAMPLE_RATE) -> np.ndarray:
    t = np.linspace(0, dur, int(sr * dur), False)
    return np.sin(2 * np.pi * freq * t)

def gen_saw(freq: float, dur: float, sr: int = SAMPLE_RATE) -> np.ndarray:
    t = np.linspace(0, dur, int(sr * dur), False)
    return 2 * (t * freq - np.floor(0.5 + t * freq))

def gen_square(freq: float, dur: float, sr: int = SAMPLE_RATE) -> np.ndarray:
    t = np.linspace(0, dur, int(sr * dur), False)
    return np.sign(np.sin(2 * np.pi * freq * t))

def gen_triangle(freq: float, dur: float, sr: int = SAMPLE_RATE) -> np.ndarray:
    t = np.linspace(0, dur, int(sr * dur), False)
    return 2 * np.abs(2 * (t * freq - np.floor(t * freq + 0.5))) - 1

def gen_noise(dur: float, sr: int = SAMPLE_RATE) -> np.ndarray:
    return np.random.uniform(-1, 1, int(sr * dur))


# ═══════════════════════════════════════════════════════════════════════════════
#                              ENVELOPES
# ═══════════════════════════════════════════════════════════════════════════════

def env_adsr(length: int, attack: float, decay: float, sustain: float, release: float) -> np.ndarray:
    """ADSR envelope. Times in seconds, sustain is level 0-1."""
    env = np.ones(length)
    sr = SAMPLE_RATE
    
    a_samp = min(int(sr * attack), length // 4)
    d_samp = min(int(sr * decay), length // 4)
    r_samp = min(int(sr * release), length // 2)
    
    # Attack
    if a_samp > 0:
        env[:a_samp] = np.linspace(0, 1, a_samp)
    
    # Decay
    d_start = a_samp
    d_end = min(d_start + d_samp, length)
    if d_end > d_start:
        env[d_start:d_end] = np.linspace(1, sustain, d_end - d_start)
    
    # Sustain
    s_start = d_end
    s_end = max(0, length - r_samp)
    if s_end > s_start:
        env[s_start:s_end] = sustain
    
    # Release
    if r_samp > 0 and s_end < length:
        env[s_end:] = np.linspace(sustain, 0, length - s_end)
    
    return env

def env_exp_decay(length: int, rate: float = 5.0) -> np.ndarray:
    """Exponential decay."""
    t = np.linspace(0, length / SAMPLE_RATE, length)
    return np.exp(-rate * t)

def env_swell(length: int, peak_pos: float = 0.6) -> np.ndarray:
    """Swell up and down."""
    peak = int(length * peak_pos)
    env = np.zeros(length)
    env[:peak] = np.linspace(0, 1, peak)
    env[peak:] = np.linspace(1, 0, length - peak)
    return env


# ═══════════════════════════════════════════════════════════════════════════════
#                              INSTRUMENTS
# ═══════════════════════════════════════════════════════════════════════════════

def synth_violin(freq: float, dur: float, vol: float = 0.3) -> np.ndarray:
    """
    Rich violin-like tone with:
    - Warm fundamental + odd/even harmonics
    - Subtle chorus (detuned layers)
    - Expressive vibrato (delayed start)
    - Body resonance (sub-octave warmth)
    - Room reverb tail
    """
    samples = int(SAMPLE_RATE * dur)
    t = np.linspace(0, dur, samples, False)
    
    # ─── VIBRATO ───
    vib_rate = 5.2  # Slightly slower, more human
    vib_depth = 0.015  # Wider
    vib = 1 + vib_depth * np.sin(2 * np.pi * vib_rate * t)
    
    # Delayed vibrato (fades in over 0.2s)
    vib_envelope = np.clip(t / 0.2, 0, 1)
    vib = 1 + (vib - 1) * vib_envelope
    
    # ─── MAIN TONE (with chorus) ───
    # Three slightly detuned copies for warmth
    detune = [0.998, 1.0, 1.002]
    wave = np.zeros(samples)
    
    for d in detune:
        phase = np.cumsum(2 * np.pi * freq * d * vib / SAMPLE_RATE)
        
        # Harmonics - violin has strong odd harmonics but needs some evens for warmth
        tone = np.sin(phase) * 0.45           # Fundamental
        tone += np.sin(phase * 2) * 0.22      # 2nd harmonic (adds warmth)
        tone += np.sin(phase * 3) * 0.18      # 3rd (characteristic violin)
        tone += np.sin(phase * 4) * 0.10      # 4th 
        tone += np.sin(phase * 5) * 0.08      # 5th
        tone += np.sin(phase * 6) * 0.04      # 6th
        tone += np.sin(phase * 7) * 0.03      # 7th (adds edge)
        
        wave += tone / len(detune)
    
    # ─── BODY RESONANCE (sub-octave warmth) ───
    body_phase = np.cumsum(2 * np.pi * (freq / 2) * vib / SAMPLE_RATE)
    body = np.sin(body_phase) * 0.08
    wave += body
    
    # ─── BOW NOISE (very subtle) ───
    bow_noise = np.random.uniform(-1, 1, samples) * 0.015
    # Filter to high frequencies only
    bow_noise = np.convolve(bow_noise, np.ones(3)/3, mode='same')
    wave += bow_noise * np.clip(t / 0.1, 0, 1)  # Fade in
    
    # ─── ENVELOPE ───
    env = env_adsr(samples, 0.06, 0.12, 0.8, 0.2)
    wave = wave * env
    
    # ─── ROOM REVERB (simple delay-based) ───
    reverb_delay = int(SAMPLE_RATE * 0.03)  # 30ms
    reverb_amount = 0.15
    if len(wave) > reverb_delay:
        reverb = np.zeros_like(wave)
        reverb[reverb_delay:] = wave[:-reverb_delay] * reverb_amount
        reverb[reverb_delay*2:] += wave[:-reverb_delay*2] * reverb_amount * 0.5
        wave = wave + reverb
    
    return wave * vol



def synth_violin_duet(freq: float, dur: float, vol: float = 0.28) -> np.ndarray:
    """
    'Duet' inspired violin: warmer, smoother top-end, more lyrical sustain.
    Uses synth_violin base then applies gentle low-pass + softer bow-noise.
    """
    wave = synth_violin(freq, dur, vol)
    if len(wave) < 4:
        return wave
    # Gentle one-pole low-pass to reduce harshness
    alpha = 0.08
    y = np.zeros_like(wave)
    y[0] = wave[0]
    for i in range(1, len(wave)):
        y[i] = y[i-1] + alpha * (wave[i] - y[i-1])
    # Tiny bow-noise breath (subtle)
    t = np.linspace(0, dur, len(wave), False)
    noise = (np.random.randn(len(wave)) * 0.0025).astype(np.float32)
    env = np.clip(t / 0.06, 0, 1) * np.clip((dur - t) / 0.18, 0, 1)
    y = y + noise * env
    return y


def synth_violin_soft(freq: float, dur: float, vol: float = 0.25) -> np.ndarray:
    """Softer, breathier violin for pads and backgrounds."""
    samples = int(SAMPLE_RATE * dur)
    t = np.linspace(0, dur, samples, False)
    
    # Slower, gentler vibrato
    vib = 1 + 0.01 * np.sin(2 * np.pi * 4.5 * t) * np.clip(t / 0.3, 0, 1)
    
    # Simpler harmonic content
    phase = np.cumsum(2 * np.pi * freq * vib / SAMPLE_RATE)
    wave = np.sin(phase) * 0.5
    wave += np.sin(phase * 2) * 0.25
    wave += np.sin(phase * 3) * 0.15
    wave += np.sin(phase * 0.5) * 0.1  # Sub-octave
    
    # Very slow attack
    env = env_adsr(samples, 0.2, 0.15, 0.7, 0.3)
    
    return wave * env * vol


def synth_drone(freq: float, dur: float, vol: float = 0.12) -> np.ndarray:
    """
    Low, warm drone that sits underneath everything.
    Creates the "room" feel.
    """
    samples = int(SAMPLE_RATE * dur)
    t = np.linspace(0, dur, samples, False)
    
    # Very slow movement
    drift = 1 + 0.003 * np.sin(2 * np.pi * 0.1 * t)
    
    # Multiple detuned low tones
    wave = np.zeros(samples)
    for detune in [0.995, 1.0, 1.005]:
        phase = np.cumsum(2 * np.pi * freq * detune * drift / SAMPLE_RATE)
        wave += np.sin(phase) * 0.4
        wave += np.sin(phase * 2) * 0.2
    
    wave = wave / 3
    
    # Very slow envelope
    env = env_adsr(samples, 0.5, 0.3, 0.8, 0.5)
    
    return wave * env * vol


def synth_cello(freq: float, dur: float, vol: float = 0.3) -> np.ndarray:
    """
    Warm cello - lower, richer than violin.
    Provides body and low-mid warmth.
    """
    samples = int(SAMPLE_RATE * dur)
    t = np.linspace(0, dur, samples, False)
    
    # Slower, deeper vibrato than violin
    vib_rate = 4.8
    vib_depth = 0.012
    vib = 1 + vib_depth * np.sin(2 * np.pi * vib_rate * t)
    vib_envelope = np.clip(t / 0.25, 0, 1)
    vib = 1 + (vib - 1) * vib_envelope
    
    # Detuned layers for warmth
    wave = np.zeros(samples)
    for d in [0.997, 1.0, 1.003]:
        phase = np.cumsum(2 * np.pi * freq * d * vib / SAMPLE_RATE)
        
        # Cello has stronger low harmonics, warmer timbre
        tone = np.sin(phase) * 0.50           # Strong fundamental
        tone += np.sin(phase * 2) * 0.28      # Strong 2nd
        tone += np.sin(phase * 3) * 0.15      # 3rd
        tone += np.sin(phase * 4) * 0.08      # 4th
        tone += np.sin(phase * 5) * 0.04      # 5th
        
        wave += tone / 3
    
    # Extra warmth from sub-octave
    sub_phase = np.cumsum(2 * np.pi * (freq / 2) * vib / SAMPLE_RATE)
    wave += np.sin(sub_phase) * 0.12
    
    # Slower attack than violin
    env = env_adsr(samples, 0.1, 0.15, 0.8, 0.25)
    wave = wave * env
    
    # Subtle room
    reverb_delay = int(SAMPLE_RATE * 0.035)
    if len(wave) > reverb_delay * 2:
        wave[reverb_delay:] += wave[:-reverb_delay] * 0.12
        wave[reverb_delay*2:] += wave[:-reverb_delay*2] * 0.06
    
    return wave * vol


def synth_strings(freq: float, dur: float, vol: float = 0.2) -> np.ndarray:
    """
    String ensemble - lush, layered strings for warmth.
    Multiple "players" slightly detuned.
    """
    samples = int(SAMPLE_RATE * dur)
    t = np.linspace(0, dur, samples, False)
    
    wave = np.zeros(samples)
    
    # Simulate 4 "players" with different vibratos and tunings
    players = [
        (0.996, 5.0, 0.010),  # detune, vib_rate, vib_depth
        (0.999, 5.3, 0.012),
        (1.001, 4.9, 0.011),
        (1.004, 5.2, 0.013),
    ]
    
    for detune, vib_rate, vib_depth in players:
        # Each player has slightly different vibrato
        vib = 1 + vib_depth * np.sin(2 * np.pi * vib_rate * t + np.random.random() * 2 * np.pi)
        vib_env = np.clip(t / 0.3, 0, 1)
        vib = 1 + (vib - 1) * vib_env
        
        phase = np.cumsum(2 * np.pi * freq * detune * vib / SAMPLE_RATE)
        
        # Simple but warm harmonics
        tone = np.sin(phase) * 0.45
        tone += np.sin(phase * 2) * 0.25
        tone += np.sin(phase * 3) * 0.15
        tone += np.sin(phase * 4) * 0.08
        
        wave += tone / len(players)
    
    # Slow, smooth envelope
    env = env_adsr(samples, 0.25, 0.2, 0.75, 0.35)
    wave = wave * env
    
    # Gentle room ambience
    reverb_delay = int(SAMPLE_RATE * 0.04)
    if len(wave) > reverb_delay * 3:
        wave[reverb_delay:] += wave[:-reverb_delay] * 0.18
        wave[reverb_delay*2:] += wave[:-reverb_delay*2] * 0.1
        wave[reverb_delay*3:] += wave[:-reverb_delay*3] * 0.05
    
    return wave * vol


def synth_room_ambience(dur: float, vol: float = 0.03) -> np.ndarray:
    """
    Very subtle filtered noise that creates a sense of space.
    Like the room breathing.
    """
    samples = int(SAMPLE_RATE * dur)
    
    # Generate noise
    noise = np.random.uniform(-1, 1, samples)
    
    # Simple low-pass filter (moving average)
    kernel_size = 100
    kernel = np.ones(kernel_size) / kernel_size
    filtered = np.convolve(noise, kernel, mode='same')
    
    # Slow modulation (breathing)
    t = np.linspace(0, dur, samples, False)
    modulation = 0.5 + 0.5 * np.sin(2 * np.pi * 0.15 * t)
    
    # Slow fade in/out
    env = env_adsr(samples, 0.5, 0.2, 0.8, 0.5)
    
    return filtered * modulation * env * vol


# ═══════════════════════════════════════════════════════════════════════════════
#                         FALLEN ANGEL INSTRUMENTS
# ═══════════════════════════════════════════════════════════════════════════════

def synth_choir(freq: float, dur: float, vol: float = 0.25, vowel: str = 'ah') -> np.ndarray:
    """
    Ethereal choir pad - formant synthesis for vowel-like tone.
    Heavenly, floating, angelic.
    """
    samples = int(SAMPLE_RATE * dur)
    t = np.linspace(0, dur, samples, False)
    
    # Formant frequencies for different vowels (simplified)
    formants = {
        'ah': [730, 1090, 2440],   # Open "aah"
        'oh': [570, 840, 2410],    # Round "ooh"  
        'ee': [270, 2290, 3010],   # Bright "eee"
        'mm': [300, 900, 2200],    # Humming
    }
    f1, f2, f3 = formants.get(vowel, formants['ah'])
    
    # Slow vibrato (multiple voices slightly out of phase)
    wave = np.zeros(samples)
    
    # 6 "voices" for thickness
    for i in range(6):
        # Each voice slightly detuned and different vibrato
        detune = 0.995 + (i * 0.002)
        vib_rate = 4.5 + i * 0.3
        vib_depth = 0.008 + i * 0.001
        phase_offset = i * 0.5
        
        vib = 1 + vib_depth * np.sin(2 * np.pi * vib_rate * t + phase_offset)
        vib_env = np.clip(t / 0.4, 0, 1)  # Vibrato fades in
        vib = 1 + (vib - 1) * vib_env
        
        # Base tone
        phase = np.cumsum(2 * np.pi * freq * detune * vib / SAMPLE_RATE)
        tone = np.sin(phase) * 0.4
        
        # Add formants (resonances that create vowel character)
        for formant_freq in [f1, f2, f3]:
            # Formant as filtered harmonic emphasis
            harmonic = int(round(formant_freq / freq))
            if 1 <= harmonic <= 8:
                tone += np.sin(phase * harmonic) * (0.15 / harmonic)
        
        wave += tone / 6
    
    # Very slow attack, long release (ethereal)
    env = env_adsr(samples, 0.4, 0.2, 0.8, 0.5)
    wave = wave * env
    
    # Soft reverb tail
    reverb_delay = int(SAMPLE_RATE * 0.05)
    if len(wave) > reverb_delay * 3:
        wave[reverb_delay:] += wave[:-reverb_delay] * 0.2
        wave[reverb_delay*2:] += wave[:-reverb_delay*2] * 0.12
        wave[reverb_delay*3:] += wave[:-reverb_delay*3] * 0.06
    
    return wave * vol


def synth_bell(freq: float, dur: float, vol: float = 0.35) -> np.ndarray:
    """
    Cathedral bell - rich overtones, long decay.
    Sacred, resonant, haunting.
    """
    samples = int(SAMPLE_RATE * dur)
    t = np.linspace(0, dur, samples, False)
    
    wave = np.zeros(samples)
    
    # Bell has inharmonic partials (not integer multiples)
    # Classic bell ratios
    partials = [
        (1.0, 1.0),      # Fundamental
        (2.0, 0.6),      # Octave
        (2.4, 0.45),     # Minor third above octave (characteristic)
        (3.0, 0.35),     # Fifth above octave
        (4.0, 0.25),     # Two octaves
        (4.8, 0.18),     # 
        (6.0, 0.12),     # Three octaves
        (8.0, 0.08),     # Four octaves (shimmer)
    ]
    
    for ratio, amplitude in partials:
        partial_freq = freq * ratio
        # Each partial decays at different rate (higher = faster)
        decay_rate = 3 + ratio * 1.5
        env = np.exp(-decay_rate * t)
        wave += np.sin(2 * np.pi * partial_freq * t) * amplitude * env
    
    # Slight pitch drop at attack (bell physics)
    pitch_env = 1 + 0.02 * np.exp(-20 * t)
    
    # Attack click
    click_samples = int(SAMPLE_RATE * 0.003)
    if click_samples < len(wave):
        click = np.random.uniform(-1, 1, click_samples) * 0.3
        click *= np.exp(-50 * np.linspace(0, 0.003, click_samples))
        wave[:click_samples] += click
    
    # Long reverb tail (cathedral space)
    reverb_delay = int(SAMPLE_RATE * 0.08)
    if len(wave) > reverb_delay * 4:
        wave[reverb_delay:] += wave[:-reverb_delay] * 0.25
        wave[reverb_delay*2:] += wave[:-reverb_delay*2] * 0.15
        wave[reverb_delay*3:] += wave[:-reverb_delay*3] * 0.08
        wave[reverb_delay*4:] += wave[:-reverb_delay*4] * 0.04
    
    return wave * vol


def synth_bell_toll(freq: float, dur: float, vol: float = 0.4) -> np.ndarray:
    """
    Deep, dark bell toll - for fallen/ominous moments.
    Lower, with dissonant undertones.
    """
    samples = int(SAMPLE_RATE * dur)
    t = np.linspace(0, dur, samples, False)
    
    wave = np.zeros(samples)
    
    # Darker partials with some dissonance
    partials = [
        (1.0, 1.0),       # Deep fundamental
        (1.5, 0.3),       # Dissonant fifth (darker)
        (2.0, 0.5),       # Octave
        (2.83, 0.35),     # Minor sixth (haunting)
        (4.0, 0.2),       # 
        (5.33, 0.15),     # Tritone area (evil)
    ]
    
    for ratio, amplitude in partials:
        partial_freq = freq * ratio
        decay_rate = 2.5 + ratio * 0.8  # Slower decay = more doom
        env = np.exp(-decay_rate * t)
        wave += np.sin(2 * np.pi * partial_freq * t) * amplitude * env
    
    # Sub-bass rumble
    sub = np.sin(2 * np.pi * freq * 0.5 * t) * 0.2 * np.exp(-1.5 * t)
    wave += sub
    
    # Heavy attack thud
    thud_samples = int(SAMPLE_RATE * 0.02)
    if thud_samples < len(wave):
        thud = np.sin(2 * np.pi * 60 * np.linspace(0, 0.02, thud_samples))
        thud *= np.exp(-30 * np.linspace(0, 0.02, thud_samples))
        wave[:thud_samples] += thud * 0.4
    
    return wave * vol


def synth_glass_shatter(dur: float = 0.3, vol: float = 0.35) -> np.ndarray:
    """
    Glass/crystal shatter - sharp, bright, violent break.
    For combo drops, punishment moments.
    """
    samples = int(SAMPLE_RATE * dur)
    t = np.linspace(0, dur, samples, False)
    
    # High frequency noise burst
    noise = np.random.uniform(-1, 1, samples)
    
    # Multiple resonant frequencies (glass shards)
    wave = noise * 0.3
    for freq in [2200, 3500, 4800, 6200, 8000]:
        # Each "shard" rings briefly
        ring = np.sin(2 * np.pi * freq * t) * np.exp(-25 * t)
        wave += ring * 0.15
    
    # Sharp attack, quick decay with some tail
    env = np.exp(-12 * t)
    env[:int(SAMPLE_RATE * 0.005)] = np.linspace(0, 1, int(SAMPLE_RATE * 0.005))
    
    # Add some "tinkle" at the end (settling shards)
    tinkle_start = int(samples * 0.3)
    if tinkle_start < samples:
        tinkle_t = np.linspace(0, dur * 0.7, samples - tinkle_start)
        for freq in [4000, 5500, 7000]:
            tinkle = np.sin(2 * np.pi * freq * tinkle_t) * 0.05
            tinkle *= np.exp(-8 * tinkle_t)
            wave[tinkle_start:] += tinkle
    
    return wave * env * vol


def synth_sharp_cut(dur: float = 0.08, vol: float = 0.5) -> np.ndarray:
    """
    Digital glitch/cut - harsh, sudden, violent.
    Like reality tearing.
    """
    samples = int(SAMPLE_RATE * dur)
    t = np.linspace(0, dur, samples, False)
    
    # Start with harsh square wave burst
    freq = 150
    wave = np.sign(np.sin(2 * np.pi * freq * t)) * 0.4
    
    # Add some bitcrushed noise
    noise = np.random.uniform(-1, 1, samples)
    # Quantize (bitcrush effect)
    noise = np.round(noise * 4) / 4
    wave += noise * 0.3
    
    # Very sharp envelope - instant attack, quick cut
    env = np.ones(samples)
    cut_point = int(samples * 0.7)
    env[cut_point:] = np.linspace(1, 0, samples - cut_point) ** 0.5
    
    # Add a "glitch" - brief silence in middle
    glitch_start = int(samples * 0.3)
    glitch_end = int(samples * 0.35)
    if glitch_end < samples:
        wave[glitch_start:glitch_end] *= 0.1
    
    return wave * env * vol


def synth_angelic_rise(dur: float, vol: float = 0.3) -> np.ndarray:
    """
    Ascending choir swell - builds to heaven then cuts.
    For transcendent moments before the fall.
    """
    samples = int(SAMPLE_RATE * dur)
    t = np.linspace(0, dur, samples, False)
    
    wave = np.zeros(samples)
    
    # Rising pitch (starts at base, rises an octave)
    base_freq = NOTES.get('C4', 261.63)
    freq_env = base_freq * (1 + t / dur)  # Rises to 2x
    
    # Multiple choir voices
    for i in range(4):
        detune = 0.99 + i * 0.007
        vib = 1 + 0.01 * np.sin(2 * np.pi * (5 + i) * t)
        
        phase = np.cumsum(2 * np.pi * freq_env * detune * vib / SAMPLE_RATE)
        tone = np.sin(phase) * 0.3
        tone += np.sin(phase * 2) * 0.15
        tone += np.sin(phase * 3) * 0.08
        
        wave += tone / 4
    
    # Volume builds
    vol_env = t / dur  # Linear rise
    vol_env = vol_env ** 0.7  # Slight curve
    
    # Slight fade at very end (or sharp cut for drama)
    fade_samples = int(SAMPLE_RATE * 0.05)
    vol_env[-fade_samples:] *= np.linspace(1, 0.3, fade_samples)
    
    return wave * vol_env * vol


def synth_fallen_impact(dur: float = 0.5, vol: float = 0.45) -> np.ndarray:
    """
    The moment of falling - bell toll + glass + sub drop.
    Combo drop, punishment, failure.
    """
    samples = int(SAMPLE_RATE * dur)
    t = np.linspace(0, dur, samples, False)
    
    wave = np.zeros(samples)
    
    # Deep bell toll
    bell_freq = NOTES.get('E2', 82.41)
    for ratio, amp in [(1.0, 0.4), (2.0, 0.2), (2.83, 0.15)]:
        wave += np.sin(2 * np.pi * bell_freq * ratio * t) * amp * np.exp(-3 * t)
    
    # Sub bass drop
    sub_freq = 40
    sub = np.sin(2 * np.pi * sub_freq * t) * 0.35
    sub *= np.exp(-4 * t)
    wave += sub
    
    # Glass shatter overlay (delayed slightly)
    shatter_delay = int(SAMPLE_RATE * 0.05)
    shatter = synth_glass_shatter(dur - 0.05, 0.25)
    if shatter_delay + len(shatter) <= samples:
        wave[shatter_delay:shatter_delay + len(shatter)] += shatter
    
    # Impact thud
    thud_samples = min(int(SAMPLE_RATE * 0.03), samples)
    thud = np.sin(2 * np.pi * 50 * np.linspace(0, 0.03, thud_samples))
    thud *= np.exp(-40 * np.linspace(0, 0.03, thud_samples))
    wave[:thud_samples] += thud * 0.5
    
    return wave * vol


# ═══════════════════════════════════════════════════════════════════════════════
#                         FRISSON INSTRUMENTS - "CARA MIA" VOCALS
# ═══════════════════════════════════════════════════════════════════════════════

def synth_soprano(freq: float, dur: float, vol: float = 0.3, vowel: str = 'ooh') -> np.ndarray:
    """
    Operatic soprano - wordless "ooh/aah" singing.
    The Cara Mia Addio voice. Pure, soaring, emotional.
    
    This is the serene squeak at the crescendo.
    """
    samples = int(SAMPLE_RATE * dur)
    t = np.linspace(0, dur, samples, False)
    
    # Soprano formants (female operatic voice)
    formants = {
        'ooh': [325, 700, 2530],    # Round, warm "ooh" 
        'aah': [800, 1150, 2800],   # Open "aah"
        'eeh': [350, 2000, 2800],   # Bright "eeh"
        'mmm': [280, 900, 2200],    # Humming with lips closed
    }
    f1, f2, f3 = formants.get(vowel, formants['ooh'])
    
    # Expressive vibrato - starts subtle, blooms
    vib_rate = 5.8  # Operatic vibrato rate
    vib_depth_start = 0.008
    vib_depth_end = 0.025  # Blooms wider
    vib_depth = vib_depth_start + (vib_depth_end - vib_depth_start) * np.clip(t / (dur * 0.6), 0, 1)
    
    # Vibrato with slight irregularity (human feel)
    vib_phase = 2 * np.pi * vib_rate * t + 0.3 * np.sin(2 * np.pi * 0.5 * t)
    vib = 1 + vib_depth * np.sin(vib_phase)
    
    # Slight pitch rise at end (expressive)
    pitch_expr = 1 + 0.015 * np.clip((t - dur * 0.7) / (dur * 0.3), 0, 1)
    
    wave = np.zeros(samples)
    
    # Multiple "singers" slightly detuned for richness
    for i, detune in enumerate([0.997, 1.0, 1.003]):
        phase = np.cumsum(2 * np.pi * freq * detune * vib * pitch_expr / SAMPLE_RATE)
        
        # Base tone
        tone = np.sin(phase) * 0.5
        
        # Formant resonances (what makes it sound like a voice)
        for j, formant_freq in enumerate([f1, f2, f3]):
            # Find which harmonic is closest to this formant
            harmonic = max(1, round(formant_freq / freq))
            if harmonic <= 10:
                # Formant amplitude decreases for higher formants
                amp = 0.25 / (j + 1)
                tone += np.sin(phase * harmonic) * amp
        
        # Slight breathiness (adds humanity)
        breath = np.random.uniform(-1, 1, samples) * 0.02
        breath_env = np.clip(t / 0.1, 0, 1) * np.clip((dur - t) / 0.1, 0, 1)
        tone += breath * breath_env
        
        wave += tone / 3
    
    # Soprano envelope - soft attack, sustain, gentle release
    attack = int(SAMPLE_RATE * min(0.15, dur * 0.15))
    release = int(SAMPLE_RATE * min(0.3, dur * 0.25))
    
    env = np.ones(samples)
    if attack > 0:
        env[:attack] = np.linspace(0, 1, attack) ** 0.7  # Soft attack curve
    if release > 0 and release < samples:
        env[-release:] = np.linspace(1, 0, release) ** 0.5  # Gentle release
    
    wave = wave * env
    
    # Gentle reverb (cathedral space)
    reverb_delay = int(SAMPLE_RATE * 0.04)
    if len(wave) > reverb_delay * 3:
        wave[reverb_delay:] += wave[:-reverb_delay] * 0.18
        wave[reverb_delay*2:] += wave[:-reverb_delay*2] * 0.10
        wave[reverb_delay*3:] += wave[:-reverb_delay*3] * 0.05
    
    return wave * vol


def synth_soprano_swell(freq: float, dur: float, vol: float = 0.35) -> np.ndarray:
    """
    The FRISSON moment - soprano voice swelling from nothing to full.
    The "ooh" that triggers chills. Cara Mia energy.
    
    Builds from whisper to full voice, then fades.
    """
    samples = int(SAMPLE_RATE * dur)
    t = np.linspace(0, dur, samples, False)
    
    # The swell shape - builds to 70% of duration, then releases
    peak_point = 0.7
    
    # Build phase: gradual rise
    build_mask = t < dur * peak_point
    swell = np.zeros(samples)
    swell[build_mask] = (t[build_mask] / (dur * peak_point)) ** 1.5
    
    # Fall phase: gentle release (clip to avoid negative values in power)
    fall_mask = ~build_mask
    fall_progress = np.clip((t[fall_mask] - dur * peak_point) / (dur * (1 - peak_point)), 0, 1)
    swell[fall_mask] = 1 - fall_progress ** 0.7
    
    swell = np.clip(swell, 0, 1)
    
    # Vibrato intensifies with volume
    vib_rate = 5.5
    vib_depth = 0.008 + swell * 0.02  # Wider vibrato at peak
    vib = 1 + vib_depth * np.sin(2 * np.pi * vib_rate * t)
    
    # Slight pitch rise at peak (expressive)
    pitch_rise = 1 + 0.02 * swell * np.sin(np.pi * t / dur)  # Arch shape
    
    wave = np.zeros(samples)
    
    # "ooh" formants
    f1, f2, f3 = 325, 700, 2530
    
    # Build the voice
    for detune in [0.998, 1.0, 1.002]:
        phase = np.cumsum(2 * np.pi * freq * detune * vib * pitch_rise / SAMPLE_RATE)
        
        tone = np.sin(phase) * 0.45
        
        # Formants
        for j, formant_freq in enumerate([f1, f2, f3]):
            harmonic = max(1, round(formant_freq / freq))
            if harmonic <= 10:
                tone += np.sin(phase * harmonic) * (0.2 / (j + 1))
        
        wave += tone / 3
    
    # Apply the swell envelope
    wave = wave * swell
    
    # Reverb tail
    reverb_delay = int(SAMPLE_RATE * 0.05)
    if len(wave) > reverb_delay * 4:
        wave[reverb_delay:] += wave[:-reverb_delay] * 0.2
        wave[reverb_delay*2:] += wave[:-reverb_delay*2] * 0.12
        wave[reverb_delay*3:] += wave[:-reverb_delay*3] * 0.06
        wave[reverb_delay*4:] += wave[:-reverb_delay*4] * 0.03
    
    return wave * vol


def synth_frisson_moment(base_freq: float, dur: float, vol: float = 0.4) -> np.ndarray:
    """
    THE BLESSED MOMENT - everything aligns for frisson.
    
    Structure:
    1. Brief silence/breath
    2. Single soprano note emerging
    3. Harmony joins (fifth above)
    4. Swell to peak
    5. Gentle resolution
    
    This is the "OOH" that gives you chills.
    """
    samples = int(SAMPLE_RATE * dur)
    wave = np.zeros(samples)
    
    # Timing (in samples)
    breath_end = int(samples * 0.08)      # Brief breath
    voice1_start = breath_end
    voice2_start = int(samples * 0.25)    # Harmony enters
    peak = int(samples * 0.65)            # Emotional peak
    
    # Voice 1: Main soprano (root)
    voice1_dur = dur - (breath_end / SAMPLE_RATE)
    voice1 = synth_soprano_swell(base_freq, voice1_dur, vol * 0.8)
    if voice1_start + len(voice1) <= samples:
        wave[voice1_start:voice1_start + len(voice1)] += voice1
    
    # Voice 2: Harmony (perfect fifth above) - enters later, softer
    fifth_freq = base_freq * 1.5  # Perfect fifth
    voice2_dur = dur - (voice2_start / SAMPLE_RATE)
    voice2 = synth_soprano_swell(fifth_freq, voice2_dur, vol * 0.5)
    if voice2_start + len(voice2) <= samples:
        wave[voice2_start:voice2_start + len(voice2)] += voice2
    
    # Voice 3: Octave above at the peak (the transcendent moment)
    octave_freq = base_freq * 2
    octave_start = int(samples * 0.45)
    octave_dur = dur * 0.4
    octave_voice = synth_soprano(octave_freq, octave_dur, vol * 0.35, 'ooh')
    # Swell envelope for the octave
    octave_env = np.sin(np.linspace(0, np.pi, len(octave_voice))) ** 0.7
    octave_voice = octave_voice * octave_env
    if octave_start + len(octave_voice) <= samples:
        wave[octave_start:octave_start + len(octave_voice)] += octave_voice
    
    # Subtle bell at the very peak (transcendence marker)
    bell_start = peak
    bell = synth_bell(base_freq * 4, 0.5, vol * 0.15)  # High, quiet bell
    if bell_start + len(bell) <= samples:
        wave[bell_start:bell_start + len(bell)] += bell
    
    return wave


def synth_cara_mia(dur: float, vol: float = 0.35) -> np.ndarray:
    """
    Full "Cara Mia" style phrase - wordless operatic melody.
    
    A complete emotional arc:
    - Soft opening
    - Rising phrase  
    - THE MOMENT (the "ooh" that triggers frisson)
    - Gentle resolution
    """
    samples = int(SAMPLE_RATE * dur)
    wave = np.zeros(samples)
    
    # Key of A minor - emotional, yearning
    # Melody: A4 -> C5 -> E5 -> (swell) -> D5 -> A4
    melody = [
        # (freq, start_ratio, dur_ratio, vol_mult, is_swell)
        (NOTES['A4'], 0.0, 0.2, 0.6, False),      # Soft opening
        (NOTES['C5'], 0.15, 0.2, 0.7, False),     # Rising
        (NOTES['E5'], 0.30, 0.35, 1.0, True),     # THE MOMENT - swell
        (NOTES['D5'], 0.60, 0.2, 0.7, False),     # Coming down
        (NOTES['A4'], 0.75, 0.25, 0.5, False),    # Resolution
    ]
    
    for freq, start_ratio, dur_ratio, vol_mult, is_swell in melody:
        start_sample = int(samples * start_ratio)
        note_dur = dur * dur_ratio
        
        if is_swell:
            note = synth_soprano_swell(freq, note_dur, vol * vol_mult)
        else:
            note = synth_soprano(freq, note_dur, vol * vol_mult, 'ooh')
        
        end_sample = min(start_sample + len(note), samples)
        wave[start_sample:end_sample] += note[:end_sample - start_sample]
    
    # Subtle string bed underneath
    strings = synth_strings(NOTES['A3'], dur, vol * 0.15)
    if len(strings) <= samples:
        wave[:len(strings)] += strings
    
    return wave


# ═══════════════════════════════════════════════════════════════════════════════
#                    FRISSON INSTRUMENTS - THE BLESSED MOMENTS
#                    "everything dies, but (OOH)"
# ═══════════════════════════════════════════════════════════════════════════════

def synth_voice_ooh(freq: float, dur: float, vol: float = 0.35) -> np.ndarray:
    """
    Pure soprano "ooh" - Cara Mia Addio style.
    Serene, ethereal, spine-tingling.
    The blessed squeak at the crescendo.
    """
    samples = int(SAMPLE_RATE * dur)
    t = np.linspace(0, dur, samples, False)
    
    # Formants for "ooh" (closed, round vowel)
    # F1≈300, F2≈870, F3≈2240 (soprano)
    f1, f2, f3 = 320, 900, 2300
    
    # Expressive vibrato - wider, more human
    vib_rate = 5.8
    vib_depth = 0.018  # Wider than instruments
    # Vibrato grows over time (like a real singer)
    vib_envelope = np.clip(t / 0.3, 0, 1) ** 0.7
    vib = 1 + vib_depth * np.sin(2 * np.pi * vib_rate * t) * vib_envelope
    
    # Slight pitch drift (human imperfection)
    drift = 1 + 0.003 * np.sin(2 * np.pi * 0.4 * t)
    
    wave = np.zeros(samples)
    
    # Multiple "singers" slightly detuned (but fewer than choir - more intimate)
    for i, detune in enumerate([0.997, 1.0, 1.003]):
        phase = np.cumsum(2 * np.pi * freq * detune * vib * drift / SAMPLE_RATE)
        
        # Voice harmonics with formant shaping
        tone = np.sin(phase) * 0.5  # Fundamental
        
        # Add harmonics shaped by formants
        for h in range(2, 12):
            harmonic_freq = freq * h
            # Formant resonance (boost near formant frequencies)
            f1_boost = np.exp(-((harmonic_freq - f1) / 100) ** 2) * 0.4
            f2_boost = np.exp(-((harmonic_freq - f2) / 150) ** 2) * 0.25
            f3_boost = np.exp(-((harmonic_freq - f3) / 200) ** 2) * 0.15
            
            harmonic_vol = (0.3 / h) + f1_boost + f2_boost + f3_boost
            tone += np.sin(phase * h) * harmonic_vol
        
        wave += tone / 3
    
    # Breath component (very subtle)
    breath = np.random.uniform(-1, 1, samples) * 0.02
    breath_env = np.clip(t / 0.2, 0, 1) * np.clip((dur - t) / 0.3, 0, 1)
    wave += breath * breath_env
    
    # Soft attack, sustained, gentle release (singer's breath)
    attack = min(0.15, dur * 0.2)
    release = min(0.25, dur * 0.3)
    env = env_adsr(samples, attack, 0.1, 0.85, release)
    wave = wave * env
    
    # Cathedral reverb (blessed space)
    for delay_ms, amount in [(40, 0.2), (80, 0.12), (120, 0.07), (180, 0.04)]:
        delay = int(SAMPLE_RATE * delay_ms / 1000)
        if len(wave) > delay:
            wave[delay:] += wave[:-delay] * amount
    
    return wave * vol


def synth_voice_frantic(freq: float, dur: float, vol: float = 0.42) -> np.ndarray:
    """
    Frantic 'desperate cute' voice call:
    loud + breathy + sustained, with a tiny squeak near the end.
    Designed for the FALLING / 'fallen' state.
    """
    samples = int(SAMPLE_RATE * dur)
    t = np.linspace(0, dur, samples, False)

    # Slight pitch drift + vibrato (more emotional)
    vib_rate = 6.4
    vib_depth = 0.022
    vib_env = np.clip(t / 0.18, 0, 1) ** 0.6
    vib = 1 + vib_depth * np.sin(2 * np.pi * vib_rate * t) * vib_env

    # End squeak: pitch rises a bit in last 120ms
    squeak = np.ones(samples)
    tail = int(SAMPLE_RATE * 0.12)
    if tail > 8 and tail < samples:
        ramp = np.linspace(1.0, 1.18, tail)
        squeak[-tail:] = ramp

    f = freq * vib * squeak

    # Base harmonic stack (voice-like)
    wave = (
        0.55 * np.sin(2*np.pi*f*t) +
        0.25 * np.sin(2*np.pi*(2*f)*t) +
        0.12 * np.sin(2*np.pi*(3*f)*t) +
        0.06 * np.sin(2*np.pi*(4*f)*t)
    )

    # Breath noise (band-limited-ish)
    noise = np.random.randn(samples) * 0.10
    # crude highpass by subtracting lowpass
    hp = np.zeros(samples)
    alpha = 0.03
    hp[0] = noise[0]
    for i in range(1, samples):
        hp[i] = hp[i-1] + alpha*(noise[i] - hp[i-1])
    breath = (noise - hp) * 0.18

    wave = wave + breath

    # Formant-ish emphasis (very light)
    form1 = np.sin(2*np.pi*820*t) * 0.05
    form2 = np.sin(2*np.pi*1450*t) * 0.03
    wave = wave + form1 + form2

    # Envelope: quick attack, strong sustain, soft release
    env = np.ones(samples)
    a = max(1, int(SAMPLE_RATE * 0.03))
    r = max(1, int(SAMPLE_RATE * 0.22))
    env[:a] = np.linspace(0, 1, a)
    env[-r:] = np.linspace(1, 0, r)

    wave = wave * env

    # Soft saturation to keep it present without clipping
    wave = np.tanh(wave * 1.25)

    return (wave * vol).astype(np.float32)



def synth_goat_bleat(freq: float, dur: float, vol: float = 0.40) -> np.ndarray:
    """Goatcore bleat: formant-ish chirp with a tiny squeak tail."""
    n = int(SAMPLE_RATE * dur)
    t = np.linspace(0, dur, n, False)

    # Quick pitch swoop downward + end squeak bump
    swoop = np.linspace(1.18, 0.82, n)
    squeak = 1.0 + 0.12 * np.exp(-((t - dur*0.78)/(dur*0.09))**2)
    f = freq * 0.55 * swoop * squeak

    # Formant-ish partials
    wave = (np.sin(2*np.pi*f*t) * 0.55 +
            np.sin(2*np.pi*f*2.02*t) * 0.25 +
            np.sin(2*np.pi*f*3.01*t) * 0.12)

    # Breath
    wave = wave + (np.random.randn(n) * 0.02)

    # Envelope: fast rise, sustain-ish, then soften
    env = (1 - np.exp(-t * 160)) * np.exp(-t * 6.5)
    wave = wave * env * vol
    return wave

def synth_plip(freq: float, dur: float, vol: float = 0.28) -> np.ndarray:
    """Plip: bright tiny droplet blip."""
    n = int(SAMPLE_RATE * dur)
    t = np.linspace(0, dur, n, False)

    wave = (np.sin(2*np.pi*freq*t) * 0.65 +
            np.sin(2*np.pi*freq*2*t) * 0.18)

    env = np.exp(-t * 45.0)
    return wave * env * vol

def synth_squish_hit(dur: float, vol: float = 0.30) -> np.ndarray:
    """Squish: soft thumpy noise burst (onomatopoeia bed)."""
    n = int(SAMPLE_RATE * dur)
    t = np.linspace(0, dur, n, False)

    thump = np.sin(2*np.pi*80.0*t) * 0.35
    noise = np.random.randn(n) * 0.20

    # simple smoothing (low-pass-ish)
    k = 10
    smooth = np.convolve(noise, np.ones(k)/k, mode='same')

    wave = thump + smooth * 0.55
    env = (1 - np.exp(-t * 420)) * np.exp(-t * 18.0)
    return wave * env * vol

def synth_hoof(dur: float, vol: float = 0.26) -> np.ndarray:
    """Hoof/clop: woody click with a body."""
    n = int(SAMPLE_RATE * dur)
    t = np.linspace(0, dur, n, False)

    click = np.random.randn(n) * 0.25
    k = 6
    click = np.convolve(click, np.ones(k)/k, mode='same')

    body = np.sin(2*np.pi*140.0*t) * 0.25
    wave = click * 0.55 + body * 0.45
    env = np.exp(-t * 35.0)
    return wave * env * vol


def synth_voice_ahh(freq: float, dur: float, vol: float = 0.32) -> np.ndarray:
    """
    Open "ahh" voice - warmer, fuller than ooh.
    For building moments before the ooh.
    """
    samples = int(SAMPLE_RATE * dur)
    t = np.linspace(0, dur, samples, False)
    
    # Formants for "ahh" (open vowel)
    f1, f2, f3 = 750, 1100, 2500
    
    # Vibrato
    vib_rate = 5.5
    vib_depth = 0.015
    vib_envelope = np.clip(t / 0.25, 0, 1)
    vib = 1 + vib_depth * np.sin(2 * np.pi * vib_rate * t) * vib_envelope
    
    wave = np.zeros(samples)
    
    for detune in [0.998, 1.0, 1.002]:
        phase = np.cumsum(2 * np.pi * freq * detune * vib / SAMPLE_RATE)
        
        tone = np.sin(phase) * 0.45
        for h in range(2, 10):
            harmonic_freq = freq * h
            f1_boost = np.exp(-((harmonic_freq - f1) / 120) ** 2) * 0.35
            f2_boost = np.exp(-((harmonic_freq - f2) / 180) ** 2) * 0.2
            f3_boost = np.exp(-((harmonic_freq - f3) / 220) ** 2) * 0.1
            
            harmonic_vol = (0.25 / h) + f1_boost + f2_boost + f3_boost
            tone += np.sin(phase * h) * harmonic_vol
        
        wave += tone / 3
    
    env = env_adsr(samples, 0.12, 0.1, 0.8, 0.2)
    wave = wave * env
    
    # Reverb
    for delay_ms, amount in [(35, 0.18), (70, 0.1), (110, 0.05)]:
        delay = int(SAMPLE_RATE * delay_ms / 1000)
        if len(wave) > delay:
            wave[delay:] += wave[:-delay] * amount
    
    return wave * vol


def synth_frisson_ooh(base_freq: float, dur: float, vol: float = 0.4) -> np.ndarray:
    """
    THE BLESSED MOMENT - rising "ooh" that triggers frisson.
    Starts lower, rises to the target note, holds with vibrato.
    The spine-tingling crescendo squeak.
    """
    samples = int(SAMPLE_RATE * dur)
    t = np.linspace(0, dur, samples, False)
    
    # Pitch rises from a 4th below to target (portamento)
    start_freq = base_freq * 0.75  # Perfect 4th below
    rise_time = min(0.4, dur * 0.3)
    rise_samples = int(rise_time * SAMPLE_RATE)
    
    freq_env = np.ones(samples) * base_freq
    if rise_samples > 0:
        # Smooth rise (ease-out curve)
        rise_curve = np.linspace(0, 1, rise_samples) ** 0.6
        freq_env[:rise_samples] = start_freq + (base_freq - start_freq) * rise_curve
    
    # Vibrato kicks in after the rise
    vib_rate = 6.0
    vib_depth = 0.02
    vib_start = rise_samples
    vib = np.ones(samples)
    if vib_start < samples:
        vib_t = np.linspace(0, dur - rise_time, samples - vib_start)
        vib_envelope = np.clip(vib_t / 0.15, 0, 1)
        vib[vib_start:] = 1 + vib_depth * np.sin(2 * np.pi * vib_rate * vib_t) * vib_envelope
    
    # Formants for "ooh"
    f1, f2, f3 = 320, 900, 2300
    
    wave = np.zeros(samples)
    
    for detune in [0.996, 1.0, 1.004]:
        phase = np.cumsum(2 * np.pi * freq_env * detune * vib / SAMPLE_RATE)
        
        tone = np.sin(phase) * 0.5
        for h in range(2, 14):
            harmonic_freq = base_freq * h  # Use base for formant calc
            f1_boost = np.exp(-((harmonic_freq - f1) / 100) ** 2) * 0.4
            f2_boost = np.exp(-((harmonic_freq - f2) / 150) ** 2) * 0.25
            f3_boost = np.exp(-((harmonic_freq - f3) / 200) ** 2) * 0.15
            
            harmonic_vol = (0.3 / h) + f1_boost + f2_boost + f3_boost
            tone += np.sin(phase * h) * harmonic_vol
        
        wave += tone / 3
    
    # Volume swells WITH the pitch rise (crescendo)
    vol_env = np.ones(samples)
    if rise_samples > 0:
        vol_env[:rise_samples] = np.linspace(0.4, 1.0, rise_samples) ** 0.8
    
    # Overall envelope
    env = env_adsr(samples, 0.08, 0.1, 0.9, 0.3)
    wave = wave * env * vol_env
    
    # Rich reverb (cathedral blessing)
    for delay_ms, amount in [(50, 0.25), (100, 0.15), (160, 0.08), (240, 0.04)]:
        delay = int(SAMPLE_RATE * delay_ms / 1000)
        if len(wave) > delay:
            wave[delay:] += wave[:-delay] * amount
    
    return wave * vol


def synth_blessed_squeak(freq: float, dur: float = 0.8, vol: float = 0.3) -> np.ndarray:
    """
    Quick blessed squeak - shorter frisson hit.
    For combo milestones, special moments.
    """
    samples = int(SAMPLE_RATE * dur)
    t = np.linspace(0, dur, samples, False)
    
    # Quick rise
    rise_time = min(0.15, dur * 0.25)
    rise_samples = int(rise_time * SAMPLE_RATE)
    
    start_freq = freq * 0.85
    freq_env = np.ones(samples) * freq
    if rise_samples > 0:
        freq_env[:rise_samples] = start_freq + (freq - start_freq) * (np.linspace(0, 1, rise_samples) ** 0.5)
    
    # Vibrato after rise
    vib = np.ones(samples)
    if rise_samples < samples:
        vib_t = np.linspace(0, dur - rise_time, samples - rise_samples)
        vib[rise_samples:] = 1 + 0.02 * np.sin(2 * np.pi * 6.5 * vib_t)
    
    # Simple ooh formants
    wave = np.zeros(samples)
    phase = np.cumsum(2 * np.pi * freq_env * vib / SAMPLE_RATE)
    
    wave = np.sin(phase) * 0.5
    wave += np.sin(phase * 2) * 0.2
    wave += np.sin(phase * 3) * 0.1
    wave += np.sin(phase * 4) * 0.05
    
    # Quick swell envelope
    env = np.ones(samples)
    env[:rise_samples] = np.linspace(0.3, 1.0, rise_samples) ** 0.6
    env[-int(samples * 0.3):] *= np.linspace(1, 0, int(samples * 0.3)) ** 0.8
    
    wave = wave * env
    
    # Light reverb
    delay = int(SAMPLE_RATE * 0.04)
    if len(wave) > delay:
        wave[delay:] += wave[:-delay] * 0.2
    
    return wave * vol


def synth_pizz(freq: float, dur: float, vol: float = 0.4) -> np.ndarray:
    """Pizzicato: plucked string, quick decay."""
    actual_dur = min(dur, 0.25)
    samples = int(SAMPLE_RATE * actual_dur)
    
    wave = gen_triangle(freq, actual_dur) * 0.6
    wave += gen_sine(freq * 2, actual_dur) * 0.25
    wave += gen_noise(actual_dur) * 0.08
    
    env = env_exp_decay(samples, 15)
    wave = wave * env * vol
    
    # Pad to requested duration
    total_samples = int(SAMPLE_RATE * dur)
    if len(wave) < total_samples:
        wave = np.pad(wave, (0, total_samples - len(wave)))
    
    return wave

def synth_pad(freq: float, dur: float, vol: float = 0.2, chord_type: str = 'min') -> np.ndarray:
    """Pad: layered chord tones, slow attack."""
    samples = int(SAMPLE_RATE * dur)
    intervals = CHORD_INTERVALS.get(chord_type, [0, 3, 7])
    
    wave = np.zeros(samples)
    for interval in intervals:
        note_freq = freq * (2 ** (interval / 12))
        tone = gen_sine(note_freq, dur) * 0.4
        tone += gen_sine(note_freq * 0.998, dur) * 0.2  # Slight detune
        tone += gen_sine(note_freq * 1.002, dur) * 0.2
        wave += tone
    
    wave = wave / len(intervals)
    env = env_adsr(samples, 0.3, 0.2, 0.7, 0.4)
    
    return wave * env * vol

def synth_bass(freq: float, dur: float, vol: float = 0.35) -> np.ndarray:
    """Bass: sub sine + saw presence."""
    samples = int(SAMPLE_RATE * dur)
    
    wave = gen_sine(freq, dur) * 0.6
    wave += gen_saw(freq, dur) * 0.25
    wave += gen_sine(freq * 2, dur) * 0.15
    
    env = env_adsr(samples, 0.02, 0.1, 0.6, 0.1)
    
    return wave * env * vol

def synth_arp(freq: float, dur: float, vol: float = 0.25) -> np.ndarray:
    """Arpeggio note: bright, short."""
    samples = int(SAMPLE_RATE * dur)
    
    wave = gen_triangle(freq, dur) * 0.5
    wave += gen_sine(freq * 2, dur) * 0.3
    wave += gen_square(freq, dur) * 0.1
    
    env = env_adsr(samples, 0.01, 0.05, 0.4, 0.1)
    
    return wave * env * vol

def synth_musicbox(freq: float, dur: float, vol: float = 0.3) -> np.ndarray:
    """Music box: pure, bell-like."""
    samples = int(SAMPLE_RATE * dur)
    
    wave = gen_sine(freq, dur) * 0.5
    wave += gen_sine(freq * 2, dur) * 0.25
    wave += gen_sine(freq * 3, dur) * 0.15
    wave += gen_sine(freq * 4, dur) * 0.1
    
    env = env_exp_decay(samples, 3)
    
    return wave * env * vol

def synth_kick(vol: float = 0.5) -> np.ndarray:
    """Kick drum."""
    dur = 0.12
    samples = int(SAMPLE_RATE * dur)
    t = np.linspace(0, dur, samples, False)
    
    # Pitch drops
    freq = 150 * np.exp(-35 * t) + 40
    phase = np.cumsum(2 * np.pi * freq / SAMPLE_RATE)
    wave = np.sin(phase)
    
    # Click
    click_samples = int(SAMPLE_RATE * 0.008)
    click = gen_noise(0.008) * np.exp(-150 * np.linspace(0, 0.008, click_samples))
    wave[:click_samples] += click * 0.3
    
    env = np.exp(-18 * t)
    
    return wave * env * vol

def synth_snare(vol: float = 0.4) -> np.ndarray:
    """Snare drum."""
    dur = 0.12
    samples = int(SAMPLE_RATE * dur)
    t = np.linspace(0, dur, samples, False)
    
    tone = np.sin(2 * np.pi * 180 * t) * np.exp(-22 * t)
    noise = np.random.uniform(-1, 1, samples) * np.exp(-16 * t)
    
    return (tone * 0.35 + noise * 0.65) * vol

def synth_hat(closed: bool = True, vol: float = 0.2) -> np.ndarray:
    """Hi-hat."""
    dur = 0.04 if closed else 0.15
    samples = int(SAMPLE_RATE * dur)
    t = np.linspace(0, dur, samples, False)
    
    wave = np.random.uniform(-1, 1, samples)
    decay = 50 if closed else 12
    
    return wave * np.exp(-decay * t) * vol


# ═══════════════════════════════════════════════════════════════════════════════
#                              SEQUENCER
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Note:
    freq: float
    beat: float  # Start beat
    dur: float   # Duration in beats
    vol: float = 0.3
    inst: str = 'violin'  # All instruments including fallen angel


def render_track(notes: List[Note], bpm: float, total_beats: int) -> np.ndarray:
    """Render a list of notes to audio."""
    beat_dur = 60.0 / bpm
    total_samples = int(total_beats * beat_dur * SAMPLE_RATE)
    output = np.zeros(total_samples)
    
    for note in notes:
        start_sample = int(note.beat * beat_dur * SAMPLE_RATE)
        note_dur_sec = note.dur * beat_dur
        
        if start_sample >= total_samples:
            continue
        
        # Generate based on instrument
        if note.inst == 'violin':
            wave = synth_violin(note.freq, note_dur_sec, note.vol)
        elif note.inst == 'violin_soft':
            wave = synth_violin_soft(note.freq, note_dur_sec, note.vol)

        elif note.inst == 'violin_duet':
            wave = synth_violin_duet(note.freq, note_dur_sec, note.vol)
        elif note.inst == 'cello':
            wave = synth_cello(note.freq, note_dur_sec, note.vol)
        elif note.inst == 'strings':
            wave = synth_strings(note.freq, note_dur_sec, note.vol)
        elif note.inst == 'drone':
            wave = synth_drone(note.freq, note_dur_sec, note.vol)
        elif note.inst == 'pizz':
            wave = synth_pizz(note.freq, note_dur_sec, note.vol)
        elif note.inst == 'bass':
            wave = synth_bass(note.freq, note_dur_sec, note.vol)
        elif note.inst == 'arp':
            wave = synth_arp(note.freq, note_dur_sec, note.vol)
        elif note.inst == 'pad':
            wave = synth_pad(note.freq, note_dur_sec, note.vol)
        elif note.inst == 'musicbox':
            wave = synth_musicbox(note.freq, note_dur_sec, note.vol)
        # ─── FALLEN ANGEL INSTRUMENTS ───
        elif note.inst == 'choir':
            wave = synth_choir(note.freq, note_dur_sec, note.vol)
        elif note.inst == 'choir_oh':
            wave = synth_choir(note.freq, note_dur_sec, note.vol, 'oh')
        elif note.inst == 'bell':
            wave = synth_bell(note.freq, note_dur_sec, note.vol)
        elif note.inst == 'bell_toll':
            wave = synth_bell_toll(note.freq, note_dur_sec, note.vol)
        elif note.inst == 'glass':
            wave = synth_glass_shatter(note_dur_sec, note.vol)
        elif note.inst == 'cut':
            wave = synth_sharp_cut(note_dur_sec, note.vol)
        elif note.inst == 'fallen':
            wave = synth_fallen_impact(note_dur_sec, note.vol)
        elif note.inst == 'rise':
            wave = synth_angelic_rise(note_dur_sec, note.vol)
        # ─── CARA MIA FRISSON INSTRUMENTS ───
        elif note.inst == 'soprano':
            wave = synth_soprano(note.freq, note_dur_sec, note.vol)
        elif note.inst == 'soprano_aah':
            wave = synth_soprano(note.freq, note_dur_sec, note.vol, 'aah')
        elif note.inst == 'voice_frantic':
            wave = synth_voice_frantic(note.freq, note_dur_sec, note.vol)

        elif note.inst == 'plip':
            wave = synth_plip(note.freq, note_dur_sec, note.vol)
        elif note.inst == 'squish_hit':
            wave = synth_squish_hit(note_dur_sec, note.vol)
        elif note.inst == 'bleat':
            wave = synth_goat_bleat(note.freq, note_dur_sec, note.vol)
        elif note.inst == 'hoof':
            wave = synth_hoof(note_dur_sec, note.vol)
        elif note.inst == 'swell':
            wave = synth_soprano_swell(note.freq, note_dur_sec, note.vol)
        elif note.inst == 'frisson':
            wave = synth_frisson_moment(note.freq, note_dur_sec, note.vol)
        elif note.inst == 'cara_mia':
            wave = synth_cara_mia(note_dur_sec, note.vol)
        # ─── DRUMS ───
        elif note.inst == 'kick':
            wave = synth_kick(note.vol)
        elif note.inst == 'snare':
            wave = synth_snare(note.vol)
        elif note.inst == 'hat':
            wave = synth_hat(True, note.vol)
        elif note.inst == 'hat_open':
            wave = synth_hat(False, note.vol)
        else:
            wave = synth_violin(note.freq, note_dur_sec, note.vol)
        
        end_sample = min(start_sample + len(wave), total_samples)
        output[start_sample:end_sample] += wave[:end_sample - start_sample]
    
    return output


def normalize(wave: np.ndarray, peak: float = 0.95) -> np.ndarray:
    """Normalize to peak level. Default 95% to avoid clipping."""
    max_val = np.max(np.abs(wave))
    if max_val > 0:
        wave = wave * (peak / max_val)
    return wave


def fade_in(wave: np.ndarray, dur: float) -> np.ndarray:
    """Apply fade in."""
    samples = min(int(SAMPLE_RATE * dur), len(wave))
    wave[:samples] *= np.linspace(0, 1, samples)
    return wave


def fade_out(wave: np.ndarray, dur: float) -> np.ndarray:
    """Apply fade out."""
    samples = min(int(SAMPLE_RATE * dur), len(wave))
    wave[-samples:] *= np.linspace(1, 0, samples)
    return wave


def to_int16(wave: np.ndarray) -> np.ndarray:
    """Convert to int16."""
    return (np.clip(wave, -1, 1) * 32767).astype(np.int16)


# ═══════════════════════════════════════════════════════════════════════════════
#                              TRACK GENERATORS
# ═══════════════════════════════════════════════════════════════════════════════

def gen_menu() -> Tuple[np.ndarray, int]:
    """01. Menu - Two Animals (60 BPM) - lonely, intimate, warm."""
    bpm, beats = 60, 32
    scale = get_scale('A', 4, 'minor')
    
    notes = [
        # ─── WARM STRING BED (foundation) ───
        Note(NOTES['A2'], 0, 16, 0.10, 'strings'),
        Note(NOTES['A2'], 16, 16, 0.10, 'strings'),
        
        # ─── CELLO (warmth in the low-mids) ───
        Note(NOTES['A2'], 0, 8, 0.15, 'cello'),
        Note(NOTES['E3'], 8, 6, 0.12, 'cello'),
        Note(NOTES['A2'], 16, 8, 0.15, 'cello'),
        Note(NOTES['D3'], 26, 6, 0.12, 'cello'),
        
        # ─── VIOLIN MELODY (lonely, expressive) ───
        Note(scale[0], 0, 4, 0.32, 'violin'),
        Note(scale[4], 6, 3, 0.28, 'violin'),
        Note(scale[3], 12, 3, 0.28, 'violin'),
        Note(scale[2], 18, 4, 0.30, 'violin'),
        Note(scale[1], 24, 3, 0.26, 'violin'),
        Note(scale[0], 28, 4, 0.28, 'violin'),
        
        # ─── MUSIC BOX (sparse, ethereal) ───
        Note(scale[4] * 2, 10, 1, 0.15, 'musicbox'),
        Note(scale[2] * 2, 22, 1, 0.15, 'musicbox'),
        
        # ─── LOW DRONE (breathing room) ───
        Note(NOTES['A1'], 0, 32, 0.06, 'drone'),
    ]
    
    wave = render_track(notes, bpm, beats)
    wave = fade_in(wave, 1.5)
    wave = fade_out(wave, 2.5)
    return to_int16(normalize(wave, 0.85)), bpm


def gen_story() -> Tuple[np.ndarray, int]:
    """02. Story - Circulation Issue (88 BPM) - nervous pizzicato."""
    bpm, beats = 88, 32
    scale = get_scale('E', 4, 'minor')
    
    notes = []
    
    # Pizzicato pattern
    for beat in range(0, beats, 2):
        idx = (beat // 4) % len(scale)
        notes.append(Note(scale[idx], beat, 0.5, 0.35, 'pizz'))
        notes.append(Note(scale[(idx + 2) % 7], beat + 0.75, 0.5, 0.3, 'pizz'))
    
    # Tense violin
    notes.extend([
        Note(scale[4], 4, 3, 0.25, 'violin'),
        Note(scale[3], 10, 3, 0.25, 'violin'),
        Note(scale[2], 16, 3, 0.28, 'violin'),
        Note(scale[4], 22, 3, 0.25, 'violin'),
        Note(scale[1], 28, 3, 0.28, 'violin'),
    ])
    
    # Subtle bass
    for beat in range(0, beats, 4):
        notes.append(Note(NOTES['E2'], beat, 2, 0.2, 'bass'))
    
    wave = render_track(notes, bpm, beats)
    wave = fade_in(wave, 0.5)
    wave = fade_out(wave, 1.0)
    return to_int16(normalize(wave, 0.85)), bpm


def gen_release() -> Tuple[np.ndarray, int]:
    """03. Release - Hold Still (100 BPM) - warm, supportive, full."""
    bpm, beats = 100, 32
    scale = get_scale('C', 4, 'major')
    
    notes = [
        # ─── STRING BED (lush foundation) ───
        Note(NOTES['C3'], 0, 16, 0.12, 'strings'),
        Note(NOTES['G3'], 16, 16, 0.12, 'strings'),
        
        # ─── CELLO (rich low-mid warmth) ───
        Note(NOTES['C3'], 0, 8, 0.18, 'cello'),
        Note(NOTES['A2'], 8, 8, 0.16, 'cello'),
        Note(NOTES['F3'], 16, 8, 0.18, 'cello'),
        Note(NOTES['G3'], 24, 8, 0.16, 'cello'),
        
        # ─── VIOLIN MELODY (expressive lead) ───
        Note(scale[0], 0, 4, 0.30, 'violin'),
        Note(scale[2], 4, 2, 0.28, 'violin'),
        Note(scale[4], 8, 4, 0.32, 'violin'),
        Note(scale[3], 14, 2, 0.28, 'violin'),
        Note(scale[2], 16, 4, 0.30, 'violin'),
        Note(scale[0], 22, 2, 0.28, 'violin'),
        Note(scale[4], 24, 4, 0.32, 'violin'),
        Note(scale[2], 30, 2, 0.28, 'violin'),
        
        # ─── PAD (harmonic color) ───
        Note(NOTES['C3'], 0, 8, 0.08, 'pad'),
        Note(NOTES['A3'], 8, 8, 0.08, 'pad'),
        Note(NOTES['F3'], 16, 8, 0.08, 'pad'),
        Note(NOTES['G3'], 24, 8, 0.08, 'pad'),
        
        # ─── LOW DRONE ───
        Note(NOTES['C2'], 0, 32, 0.06, 'drone'),
    ]
    
    # Light bass
    for beat in range(0, beats, 4):
        root = ['C', 'A', 'F', 'G'][beat // 8 % 4]
        notes.append(Note(NOTES[f'{root}2'], beat, 2, 0.22, 'bass'))
    
    # Subtle pulse
    for beat in range(0, beats, 4):
        notes.append(Note(60, beat, 0.1, 0.12, 'kick'))
    
    wave = render_track(notes, bpm, beats)
    return to_int16(normalize(wave, 0.85)), bpm


def gen_overdrive() -> Tuple[np.ndarray, int]:
    """04. Overdrive - More (115 BPM) - arpeggios enter."""
    bpm, beats = 115, 32
    scale = get_scale('A', 4, 'minor')
    chord = get_chord('A', 4, 'min')
    
    notes = []
    
    # More active melody
    melody_pattern = [
        (0, 0, 2), (2, 2, 1), (4, 4, 2), (3, 7, 1),
        (2, 8, 2), (0, 10, 1), (4, 12, 2), (2, 15, 1),
    ]
    for idx, beat, dur in melody_pattern:
        notes.append(Note(scale[idx % 7], beat, dur, 0.33, 'violin'))
        notes.append(Note(scale[idx % 7], beat + 16, dur, 0.33, 'violin'))
    
    # Arpeggios
    for bar in range(0, beats, 4):
        for i, freq in enumerate(chord):
            notes.append(Note(freq, bar + i * 0.5, 0.4, 0.22, 'arp'))
            notes.append(Note(freq, bar + 2 + i * 0.5, 0.4, 0.22, 'arp'))
    
    # Bass
    for beat in range(0, beats, 2):
        notes.append(Note(NOTES['A2'], beat, 1.5, 0.28, 'bass'))
    
    # Light drums
    for beat in range(0, beats, 4):
        notes.append(Note(60, beat, 0.1, 0.22, 'kick'))
        notes.append(Note(60, beat + 2, 0.1, 0.18, 'kick'))
    for beat in range(0, beats, 2):
        notes.append(Note(8000, beat + 0.5, 0.05, 0.12, 'hat'))
    
    wave = render_track(notes, bpm, beats)
    return to_int16(normalize(wave, 0.85)), bpm


def gen_frenzy() -> Tuple[np.ndarray, int]:
    """05. Frenzy - Too Fast (130 BPM) - DRUMS ENTER."""
    bpm, beats = 130, 32
    scale = get_scale('D', 5, 'minor')
    chord = get_chord('D', 4, 'min')
    
    notes = []
    
    # Aggressive melody
    for bar in range(0, beats, 4):
        notes.extend([
            Note(scale[0], bar, 1, 0.4, 'violin'),
            Note(scale[2], bar + 1, 0.5, 0.38, 'violin'),
            Note(scale[4], bar + 1.5, 0.5, 0.4, 'violin'),
            Note(scale[3], bar + 2.5, 1, 0.38, 'violin'),
        ])
    
    # Driving arpeggios
    for bar in range(0, beats, 2):
        for i, freq in enumerate(chord):
            notes.append(Note(freq, bar + i * 0.25, 0.2, 0.25, 'arp'))
    
    # Heavy bass
    for beat in range(0, beats):
        vol = 0.35 if beat % 2 == 0 else 0.28
        notes.append(Note(NOTES['D2'], beat, 0.4, vol, 'bass'))
    
    # FULL DRUMS
    for beat in range(0, beats):
        if beat % 4 in [0, 2]:
            notes.append(Note(60, beat, 0.1, 0.45, 'kick'))
        if beat % 4 in [1, 3]:
            notes.append(Note(200, beat, 0.1, 0.38, 'snare'))
        notes.append(Note(8000, beat, 0.05, 0.18, 'hat'))
        notes.append(Note(8000, beat + 0.5, 0.05, 0.14, 'hat'))
    
    wave = render_track(notes, bpm, beats)
    return to_int16(normalize(wave, 0.9)), bpm


def gen_breaking() -> Tuple[np.ndarray, int]:
    """06. Breaking - Hold (150 BPM) - sparse, HEAVY."""
    bpm, beats = 150, 32
    scale = get_scale('E', 5, 'minor')
    
    notes = [
        # Long tense holds
        Note(scale[4], 0, 8, 0.45, 'violin'),
        Note(scale[0], 12, 6, 0.42, 'violin'),
        Note(scale[4], 20, 8, 0.45, 'violin'),
        Note(scale[3], 30, 2, 0.4, 'violin'),
    ]
    
    # Sub bass pulse
    for beat in range(0, beats, 4):
        notes.append(Note(NOTES['E1'], beat, 2, 0.4, 'bass'))
    
    # Sparse HEAVY drums
    for bar in range(0, beats // 4):
        notes.append(Note(60, bar * 4, 0.1, 0.55, 'kick'))
        if bar % 2 == 1:
            notes.append(Note(200, bar * 4 + 3, 0.1, 0.45, 'snare'))
    
    # Heartbeat undertone
    for beat in range(0, beats, 2):
        notes.append(Note(40, beat, 0.1, 0.15, 'kick'))
    
    wave = render_track(notes, bpm, beats)
    return to_int16(normalize(wave, 0.9)), bpm


def gen_transcendence() -> Tuple[np.ndarray, int]:
    """07. Transcendence - Not Yet (175 BPM) - ethereal, CARA MIA blessed squeaks."""
    bpm, beats = 175, 32
    scale = get_scale('A', 5, 'minor')
    
    notes = [
        # ─── ETHEREAL CHOIR BED (the angelic presence) ───
        Note(NOTES['A3'], 0, 16, 0.08, 'choir'),
        Note(NOTES['E4'], 0, 16, 0.06, 'choir'),
        Note(NOTES['A3'], 16, 16, 0.08, 'choir'),
        Note(NOTES['D4'], 16, 16, 0.06, 'choir'),
        
        # ─── SINGLE VIOLIN VOICE (highest register) ───
        Note(scale[4], 0, 10, 0.32, 'violin'),
        Note(scale[2], 16, 8, 0.30, 'violin'),
        Note(scale[0], 26, 6, 0.32, 'violin'),
        
        # ═══════════════════════════════════════════════════════════════
        #              CARA MIA BLESSED SQUEAKS
        #              "everything dies, but (OOH)"
        # ═══════════════════════════════════════════════════════════════
        
        # First blessed moment - soprano swell emerges from the texture
        Note(NOTES['E5'], 8, 4, 0.35, 'swell'),
        
        # THE MOMENT - full frisson (soprano + harmony + bell)
        Note(NOTES['A5'], 20, 5, 0.40, 'frisson'),
        
        # ─── HIGH BELLS (angelic chimes) ───
        Note(NOTES['E5'], 3, 2, 0.10, 'bell'),
        Note(NOTES['A5'], 14, 2, 0.12, 'bell'),
        Note(NOTES['E5'], 28, 3, 0.14, 'bell'),
        
        # ─── SUBTLE SHARP CUTS (reality cracks) ───
        Note(0, 7.5, 0.08, 0.12, 'cut'),
        Note(0, 19.5, 0.08, 0.15, 'cut'),
    ]
    
    # Heartbeat (faster now, softer under the voice)
    for beat in range(0, beats, 4):
        notes.append(Note(50, beat, 0.1, 0.15, 'kick'))
        notes.append(Note(50, beat + 1.5, 0.1, 0.12, 'kick'))
    
    wave = render_track(notes, bpm, beats)
    return to_int16(normalize(wave, 0.85)), bpm



def gen_climax() -> Tuple[np.ndarray, int]:
    """08. Climax - BEAUTIFUL + ANIMAL (138 BPM)

    Goal:
      - Beautiful, satisfying, "full track" feel (not a tiny loop)
      - Animal/onomatopoeia layer baked into the track (plip/squish/clop)
      - Goatcore accents (cute bleat chirps) without drowning the melody
    """
    bpm, beats = 138, 128  # ~55s before any loop
    scale = get_scale('C', 5, 'major')
    scale_low = get_scale('C', 4, 'major')

    root = scale_low[0]
    fifth = scale_low[4]
    fourth = scale_low[3]
    sixth = scale_low[5]

    notes: List[Note] = []

    def pad_prog(start_beat: float, length: int, vol: float = 0.20):
        # I–V–vi–IV (a bit more emotional than I–V–IV)
        prog = [(root, 0), (fifth, 4), (sixth, 8), (fourth, 12)]
        for base, off in prog:
            for b in range(0, length, 16):
                notes.append(Note(base, start_beat + b + off, 4, vol, 'pad'))
                notes.append(Note(base * 2, start_beat + b + off, 4, vol * 0.52, 'pad'))

    def drums(start_beat: float, length: int, intensity: float = 1.0):
        for b in range(int(start_beat), int(start_beat + length)):
            # kick 4/4
            notes.append(Note(50, b, 0.1, 0.12 * intensity, 'kick'))
            # snare 2/4
            if b % 4 in (1, 3):
                notes.append(Note(0, b + 0.0, 0.1, 0.10 * intensity, 'snare'))
            # hats
            notes.append(Note(0, b + 0.5, 0.05, 0.055 * intensity, 'hat'))

    def squish_bed(start_beat: float, length: int, vol: float = 0.10):
        # rhythmic squish at 8ths (onomatopoeia texture)
        t = start_beat
        end = start_beat + length
        while t < end:
            notes.append(Note(0, t, 0.08, vol, 'squish_hit'))
            t += 0.5

    def plip_sparkle(start_beat: float, length: int, vol: float = 0.10):
        # bright droplets on offbeats
        for b in range(int(start_beat), int(start_beat + length)):
            step = [0, 2, 4, 7][b % 4]
            freq = scale[min(step, len(scale)-1)]
            notes.append(Note(freq, b + 0.5, 0.12, vol, 'plip'))

    def hoof_slaps(start_beat: float, length: int, vol: float = 0.10):
        # occasional clops (slapstick body hits)
        for b in range(int(start_beat), int(start_beat + length), 2):
            if b % 8 in (2, 6):
                notes.append(Note(0, b + 0.25, 0.10, vol, 'hoof'))

    def melody(start_beat: float, motif: int, vol: float = 0.42):
        # 8-beat phrases; duet-ish contour
        if motif == 0:
            seq = [0, 2, 4, 5, 7, 5, 4, 2]
        elif motif == 1:
            seq = [5, 4, 2, 0, 2, 4, 5, 7]
        elif motif == 2:
            seq = [7, 5, 4, 2, 4, 5, 7, 9]
        else:
            seq = [9, 7, 5, 4, 2, 4, 5, 7]

        for i, step in enumerate(seq):
            notes.append(Note(scale[min(step, len(scale)-1)], start_beat + i, 1, vol, 'violin_duet'))

        notes.append(Note(scale[4], start_beat + 8, 2, vol * 0.78, 'violin_soft'))

    def response_bleat(at_beat: float, vol: float = 0.28):
        # Goatcore accent: short bleat chirp (satisfying but not dominant)
        freq = scale_low[0]
        notes.append(Note(freq, at_beat, 0.18, vol, 'bleat'))

    def choir_swells(start_beat: float, length: int, vol: float = 0.18):
        notes.append(Note(scale_low[0], start_beat + 4, 8, vol, 'choir'))
        notes.append(Note(scale_low[4], start_beat + 12, 8, vol, 'choir_oh'))
        notes.append(Note(scale_low[3], start_beat + 20, 8, vol, 'choir'))

    def arp_run(start_beat: float, length: int, vol: float = 0.14):
        arps = [0, 2, 4, 7, 9, 7, 4, 2]
        t = start_beat
        for i in range(int(length * 2)):
            step = arps[i % len(arps)]
            notes.append(Note(scale[min(step, len(scale)-1)], t, 0.5, vol, 'arp'))
            t += 0.5

    # SECTION A (0–32): beautiful lift (light animal texture)
    pad_prog(0, 32, vol=0.18)
    drums(0, 32, intensity=0.70)
    plip_sparkle(0, 32, vol=0.075)
    for b in (0, 8, 16, 24):
        melody(b, motif=0, vol=0.38)
    response_bleat(31.5, vol=0.20)

    # SECTION B (32–64): animal layer comes in (squish bed + hoof)
    pad_prog(32, 32, vol=0.20)
    drums(32, 32, intensity=0.95)
    squish_bed(32, 32, vol=0.10)
    hoof_slaps(32, 32, vol=0.09)
    for b in (32, 40, 48, 56):
        melody(b, motif=1, vol=0.41)
    response_bleat(63.5, vol=0.24)

    # SECTION C (64–96): choir swell + calmer drums (beauty dominates)
    pad_prog(64, 32, vol=0.22)
    drums(64, 32, intensity=0.55)
    plip_sparkle(64, 32, vol=0.08)
    choir_swells(64, 32, vol=0.18)
    for b in (64, 72, 80, 88):
        melody(b, motif=2, vol=0.44)
    response_bleat(95.5, vol=0.22)

    # SECTION D (96–128): final sprint (arp + full animal rhythm)
    pad_prog(96, 32, vol=0.20)
    drums(96, 32, intensity=1.10)
    squish_bed(96, 32, vol=0.11)
    hoof_slaps(96, 32, vol=0.10)
    arp_run(96, 32, vol=0.16)
    for b in (96, 104, 112, 120):
        melody(b, motif=3, vol=0.46)
    response_bleat(127.5, vol=0.26)

    wave = render_track(notes, bpm, beats)
    return to_int16(normalize(wave, 0.90)), bpm

def gen_aftercare() -> Tuple[np.ndarray, int]:
    """09. Aftercare - Birdsong (55 BPM) - tender, slowing, LUSH."""
    bpm, beats = 55, 32
    scale = get_scale('F', 4, 'major')
    
    notes = [
        # ─── LUSH STRING BED (warmest moment) ───
        Note(NOTES['F3'], 0, 16, 0.14, 'strings'),
        Note(NOTES['C4'], 16, 16, 0.14, 'strings'),
        
        # ─── WARM CELLO (heartfelt) ───
        Note(NOTES['F2'], 0, 12, 0.18, 'cello'),
        Note(NOTES['C3'], 12, 10, 0.16, 'cello'),
        Note(NOTES['A2'], 22, 10, 0.18, 'cello'),
        
        # ─── TENDER VIOLIN MELODY ───
        Note(scale[0], 0, 6, 0.28, 'violin'),
        Note(scale[2], 10, 4, 0.25, 'violin'),
        Note(scale[4], 18, 4, 0.27, 'violin'),
        Note(scale[2], 24, 6, 0.25, 'violin'),
        
        # ─── MUSIC BOX (bookend with menu) ───
        Note(scale[4] * 2, 14, 1, 0.12, 'musicbox'),
        Note(scale[2] * 2, 28, 1, 0.12, 'musicbox'),
        
        # ─── LOW DRONE (breathing room) ───
        Note(NOTES['F1'], 0, 32, 0.08, 'drone'),
        
        # ─── FADING HEARTBEAT ───
        Note(50, 0, 0.1, 0.08, 'kick'),
        Note(50, 12, 0.1, 0.06, 'kick'),
        Note(50, 24, 0.1, 0.04, 'kick'),
    ]
    
    wave = render_track(notes, bpm, beats)
    wave = fade_in(wave, 2.0)
    wave = fade_out(wave, 4.0)
    return to_int16(normalize(wave, 0.8)), bpm


def gen_love_bunny() -> Tuple[np.ndarray, int]:
    """10. Love Bunny - Woof (120 BPM) - bouncy, cute."""
    bpm, beats = 120, 32
    scale = get_scale('G', 4, 'major')
    scale_high = get_scale('G', 5, 'major')
    
    notes = []
    
    # Bouncy pizzicato
    for bar in range(0, beats, 4):
        notes.extend([
            Note(scale[0], bar, 0.5, 0.35, 'pizz'),
            Note(scale[2], bar + 0.75, 0.5, 0.33, 'pizz'),
            Note(scale[4], bar + 1.5, 0.5, 0.35, 'pizz'),
            Note(scale[2], bar + 2.25, 0.5, 0.33, 'pizz'),
            Note(scale_high[0], bar + 3, 0.75, 0.38, 'pizz'),
        ])
    
    # Music box (toy-like)
    for beat in range(0, beats, 4):
        notes.append(Note(scale_high[beat % 5] * 1.5, beat + 1, 0.5, 0.22, 'musicbox'))
    
    # Light drums
    for beat in range(0, beats, 2):
        notes.append(Note(60, beat, 0.1, 0.18, 'kick'))
        notes.append(Note(8000, beat + 0.5, 0.05, 0.12, 'hat'))
        notes.append(Note(8000, beat + 1.25, 0.05, 0.1, 'hat'))
    
    wave = render_track(notes, bpm, beats)
    return to_int16(normalize(wave, 0.85)), bpm


def gen_edge() -> Tuple[np.ndarray, int]:
    """11. Edge - Please (130 BPM) - ascending, NEVER resolves, full sound."""
    bpm, beats = 130, 32
    scale = get_scale('B', 4, 'minor')
    chord = get_chord('B', 4, 'min')
    
    notes = []
    
    # ─── CELLO (building intensity underneath) ───
    for bar in range(0, beats, 8):
        vol = 0.12 + (bar / beats) * 0.1  # Builds
        notes.append(Note(NOTES['B2'], bar, 8, vol, 'cello'))
    
    # ─── STRINGS (tension bed) ───
    notes.append(Note(NOTES['B3'], 0, 16, 0.08, 'strings'))
    notes.append(Note(NOTES['F#3'], 16, 16, 0.10, 'strings'))
    
    # ─── VIOLIN MELODY (ascending, NEVER resolves) ───
    for bar in range(0, beats, 4):
        base = bar // 4
        notes.extend([
            Note(scale[base % 5], bar, 1, 0.32, 'violin'),
            Note(scale[(base + 1) % 7], bar + 1, 1, 0.34, 'violin'),
            Note(scale[(base + 2) % 7], bar + 2, 1, 0.36, 'violin'),
            Note(scale[(base + 3) % 7], bar + 3, 1, 0.38, 'violin'),
        ])
    
    # ─── ARPEGGIOS (ascending pitch shift) ───
    for bar in range(0, beats, 2):
        for i, freq in enumerate(chord):
            vol = 0.18 + (bar / beats) * 0.08
            notes.append(Note(freq * (1 + bar / 64), bar + i * 0.5, 0.4, vol, 'arp'))
    
    # ─── BASS (building) ───
    for beat in range(0, beats, 2):
        vol = 0.18 + (beat / beats) * 0.12
        notes.append(Note(NOTES['B2'], beat, 1.5, vol, 'bass'))
    
    # ─── DRUMS (tension pulse) ───
    for beat in range(0, beats):
        vol = 0.22 + (beat / beats) * 0.15
        notes.append(Note(60, beat, 0.1, vol, 'kick'))
        notes.append(Note(8000, beat + 0.5, 0.05, 0.15, 'hat'))
    
    wave = render_track(notes, bpm, beats)
    wave = fade_in(wave, 0.3)
    # No fade out - tension maintained!
    return to_int16(normalize(wave, 0.85)), bpm


def gen_achievement() -> Tuple[np.ndarray, int]:
    """12. Achievement Sting - quick fanfare."""
    bpm, beats = 120, 4
    scale = get_scale('C', 5, 'major')
    
    notes = [
        Note(scale[0], 0, 0.5, 0.4, 'musicbox'),
        Note(scale[2], 0.5, 0.5, 0.42, 'musicbox'),
        Note(scale[4], 1, 0.5, 0.45, 'musicbox'),
        Note(scale[0] * 2, 1.5, 1.5, 0.5, 'musicbox'),
        Note(scale[4], 1.5, 1.5, 0.35, 'violin'),
    ]
    
    wave = render_track(notes, bpm, beats)
    wave = fade_out(wave, 0.3)
    return to_int16(normalize(wave, 0.9)), bpm


def gen_fallen() -> Tuple[np.ndarray, int]:
    """
    13. Fallen Angel (FALLING STATE) — longer, less frantic, more *frisson*.
    Flow → falling: violin crests + desperate cute voice calls.
    Inspiration unit: OMORI 'Duet' (violin tenderness + emotional lift).
    """
    bpm, beats = 68, 64

    notes: List[Note] = []

    # ─── Soft choir bed (kept low so violin + voice can lead) ───
    notes.extend([
        Note(NOTES['A3'], 0, 16, 0.13, 'choir'),
        Note(NOTES['E4'], 0, 16, 0.11, 'choir'),
        Note(NOTES['A4'], 4, 12, 0.09, 'choir_oh'),

        Note(NOTES['F3'], 16, 16, 0.13, 'choir'),
        Note(NOTES['C4'], 16, 16, 0.11, 'choir'),
        Note(NOTES['F4'], 20, 12, 0.09, 'choir_oh'),

        Note(NOTES['D3'], 32, 16, 0.14, 'choir'),
        Note(NOTES['A3'], 32, 16, 0.11, 'choir'),
        Note(NOTES['D4'], 36, 12, 0.09, 'choir_oh'),

        Note(NOTES['E3'], 48, 16, 0.14, 'choir'),
        Note(NOTES['B3'], 48, 16, 0.11, 'choir'),
        Note(NOTES['E4'], 52, 12, 0.10, 'choir_oh'),
    ])

    # ─── Violin crests (Duet-like: rising, lyrical, not frantic) ───
    # A small motif that crests, resolves, repeats with variation.
    crest = [
        ('E4', 0.0), ('F4', 0.8), ('A4', 1.6), ('C5', 2.4), ('B4', 3.2),
        ('A4', 4.0), ('F4', 4.8), ('E4', 5.6),
    ]
    crest_starts = [6, 14, 22, 30, 46, 54]
    for s in crest_starts:
        for name, off in crest:
            notes.append(Note(NOTES[name], s + off, 0.75, 0.26, 'violin_duet'))
        # gentle cello underpin
        notes.append(Note(NOTES['A3'], s, 6.0, 0.16, 'cello'))

    # ─── Desperate cute voice calls (loud+breathy+sustained+squeak) ───
    # "Fiiiiiee(squeak)nd!~" as rising call, then soften.
    voice_calls = [
        (34, 'A4'), (36, 'C5'), (38, 'E5'),
        (42, 'B4'), (44, 'D5')
    ]
    for b, n in voice_calls:
        notes.append(Note(NOTES[n], b, 1.4, 0.36, 'voice_frantic'))
        # tiny answer in violin so it feels like a duet/callback
        notes.append(Note(NOTES[n], b + 1.6, 0.8, 0.22, 'violin_duet'))

    # ─── Tender resolving line (keep the scene feeling longer, not shorter) ───
    resolve = [('C5', 0), ('B4', 1.2), ('A4', 2.4), ('F4', 3.6), ('E4', 4.8)]
    for name, off in resolve:
        notes.append(Note(NOTES[name], 58 + off, 1.1, 0.24, 'violin_duet'))
    notes.append(Note(NOTES['A3'], 58, 7.5, 0.15, 'cello'))

    wave = render_track(notes, bpm, beats)
    wave = normalize(wave, 0.94)
    wave = fade_in(wave, 0.35)
    wave = fade_out(wave, 0.6)
    return wave, bpm

def gen_combo_drop() -> Tuple[np.ndarray, int]:
    """
    Combo Drop Stinger - played when combo is broken.
    Bell toll + glass shatter = fallen.
    """
    bpm, beats = 120, 2
    
    notes = [
        # Deep toll
        Note(NOTES['E2'], 0, 2, 0.45, 'bell_toll'),
        # Glass shatter immediately after
        Note(0, 0.1, 0.3, 0.35, 'glass'),
        # Sharp cut for impact
        Note(0, 0, 0.1, 0.4, 'cut'),
        # Sub bass thud
        Note(40, 0, 0.3, 0.3, 'kick'),
    ]
    
    wave = render_track(notes, bpm, beats)
    return to_int16(normalize(wave, 0.9)), bpm


def gen_tier_bell() -> Tuple[np.ndarray, int]:
    """
    Tier transition bell - ascending bell tone.
    Marks progression through intensity tiers.
    """
    bpm, beats = 120, 2
    
    notes = [
        Note(NOTES['C4'], 0, 2, 0.35, 'bell'),
        Note(NOTES['E4'], 0.3, 1.5, 0.30, 'bell'),
        Note(NOTES['G4'], 0.6, 1.2, 0.28, 'bell'),
    ]
    
    wave = render_track(notes, bpm, beats)
    wave = fade_out(wave, 0.3)
    return to_int16(normalize(wave, 0.85)), bpm


def gen_frisson_sting() -> Tuple[np.ndarray, int]:
    """
    Quick frisson sting - blessed squeak for combo milestones.
    A short soprano "ooh" swell that triggers chills.
    Plays at 50+ combo, 100+ combo, etc.
    """
    bpm, beats = 120, 3
    
    # Quick soprano swell - the blessed moment
    notes = [
        # Main swell
        Note(NOTES['E5'], 0, 2, 0.40, 'swell'),
        # Soft harmony
        Note(NOTES['B5'], 0.3, 1.5, 0.25, 'soprano'),
        # Tiny bell
        Note(NOTES['E6'], 0.8, 1, 0.15, 'bell'),
    ]
    
    wave = render_track(notes, bpm, beats)
    wave = fade_out(wave, 0.5)
    return to_int16(normalize(wave, 0.9)), bpm


def gen_cara_mia_phrase() -> Tuple[np.ndarray, int]:
    """
    Full Cara Mia style phrase - for very special moments.
    Complete wordless operatic arc.
    """
    bpm = 80
    
    # Use the cara_mia instrument which generates the full phrase
    dur = 4.0  # 4 seconds
    wave = synth_cara_mia(dur, 0.45)
    
    # Ensure stereo
    if len(wave.shape) == 1:
        wave = np.column_stack([wave, wave])
    
    return to_int16(normalize(wave, 0.9)), bpm


# ═══════════════════════════════════════════════════════════════════════════════
#                              OST ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

GENERATORS = {
    'menu': gen_menu,
    'story': gen_story,
    'release': gen_release,
    'overdrive': gen_overdrive,
    'frenzy': gen_frenzy,
    'breaking': gen_breaking,
    'transcendence': gen_transcendence,
    'climax': gen_climax,
    'aftercare': gen_aftercare,
    'love_bunny': gen_love_bunny,
    'edge': gen_edge,
    'achievement': gen_achievement,
    'fallen': gen_fallen,
    'combo_drop': gen_combo_drop,
    'tier_bell': gen_tier_bell,
    'frisson': gen_frisson_sting,
    'cara_mia': gen_cara_mia_phrase,
}

TIER_TRACKS = {
    0: 'release',
    1: 'overdrive',
    2: 'frenzy',
    3: 'breaking',
    4: 'transcendence',
}


class ProceduralOST:
    """Complete procedural OST system."""
    
    def __init__(self):
        self.tracks: Dict[str, 'pygame.mixer.Sound'] = {}
        self.bpms: Dict[str, int] = {}
        self._channel = None
        self._current = None
        self.volume = 1.0
        self._volume = self.volume
        self._muted = False
        self._init = False
    
    def init(self) -> bool:
        """Initialize pygame mixer."""
        if not NUMPY_AVAILABLE or not PYGAME_AVAILABLE:
            print("Missing numpy or pygame!")
            return False
        try:
            # IMPORTANT: Initialize pygame first!
            pygame.init()
            
            if not pygame.mixer.get_init():
                # Use larger buffer for stability
                pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2, buffer=2048)
            # Ensure enough channels for layering (music + SFX)
            pygame.mixer.set_num_channels(32)
            # Reserve channel 0 for music so SFX won't starve music playback
            try:
                pygame.mixer.set_reserved(1)
            except Exception:
                pass
            # Dedicated music channel
            try:
                self._music_channel = pygame.mixer.Channel(0)
                self._channel = self._music_channel
            except Exception:
                self._music_channel = None

            # Ensure enough channels for layering (music + SFX)
            try:
                pygame.mixer.set_num_channels(32)
            except Exception:
                pass
            try:
                pygame.mixer.set_reserved(1)
            except Exception:
                pass
            try:
                self._music_channel = pygame.mixer.Channel(0)
                self._channel = self._music_channel
            except Exception:
                self._music_channel = None
            self._init = True
            return True
        except Exception as e:
            print(f"Audio init error: {e}")
            return False
    
    def generate_all(self, callback=None):
        """Generate all tracks."""
        if not self._init:
            if not self.init():
                print("Failed to initialize audio!")
                return
        
        total = len(GENERATORS)
        for i, (name, gen) in enumerate(GENERATORS.items()):
            if callback:
                callback(name, i + 1, total)
            try:
                wave, bpm = gen()
                # Ensure wave is proper format
                if len(wave) == 0:
                    print(f"  Warning: {name} generated empty wave!")
                    continue
                stereo = np.column_stack([wave, wave])
                self.tracks[name] = pygame.mixer.Sound(buffer=stereo.tobytes())
                self.bpms[name] = bpm
            except Exception as e:
                import traceback
                print(f"Error generating {name}: {e}")
                traceback.print_exc()
    

    def play(self, track: str, loop: bool = True, fade: int = 500):
        """Play a background track on the reserved music channel.

        Notes:
        - Uses channel 0 (reserved) so SFX cannot starve music.
        - Only updates current-track state if playback actually starts.
        """
        if not _music_enabled_from_config():
            self._muted = True
            self._playing = False
            self._current_track = None
            _hard_stop_music_channels()
            return
        try:
            self._muted = False
            self.set_volume(_music_volume_from_config(getattr(self, "_volume", 1.0)))
        except Exception:
            pass

        if not self._init:
            # Try late init so imports don't hard-fail
            if not self.init():
                print("OST not initialized!")
                return

        if track not in self.tracks:
            print(f"Track '{track}' not found!")
            return

        # Ensure mixer has enough channels and reserve channel 0 for music
        try:
            if pygame.mixer.get_num_channels() < 32:
                pygame.mixer.set_num_channels(32)
            try:
                pygame.mixer.set_reserved(1)  # reserve channel 0
            except Exception:
                pass
        except Exception:
            pass

        loops = -1 if loop else 0

        try:
            ch = pygame.mixer.Channel(0)
            snd = self.tracks[track]

            # Apply mute/volume consistently
            vol = 0.0 if getattr(self, "_muted", False) else float(getattr(self, "_volume", 1.0))
            try:
                ch.set_volume(vol)
            except Exception:
                pass

            # Fade out previous if different
            try:
                if getattr(self, "_current_track", None) and self._current_track != track:
                    try:
                        ch.fadeout(int(fade))
                    except Exception:
                        pass
            except Exception:
                pass

            # Start playback
            ch.play(snd, loops=loops, fade_ms=int(fade) if fade else 0)

            # Only commit state if actually busy after starting
            self._music_channel = ch
            self._current_track = track
            self._playing = True
        except Exception as e:
            print(f"OST play() failed: {e}")

    def stop(self, fade: int = 500):
        """Stop background music."""
        try:
            ch = getattr(self, "_music_channel", None)
            if ch is None:
                ch = pygame.mixer.Channel(0)
            if fade and int(fade) > 0:
                try:
                    ch.fadeout(int(fade))
                except Exception:
                    ch.stop()
            else:
                ch.stop()
        except Exception:
            pass
        self._playing = False
        self._current_track = None

    def play_tier(self, tier: int):
        """Play tier-associated track."""
        track = TIER_TRACKS.get(int(tier), "story")
        self.play(track, loop=True, fade=300)

    def set_volume(self, vol: float):
        """Set music volume (0.0 - 1.0)."""
        try:
            v = max(0.0, min(1.0, float(vol)))
        except Exception:
            v = 1.0
        self._volume = v
        self.volume = v  # keep legacy attribute in sync
        if getattr(self, "_muted", False):
            return
        try:
            ch = getattr(self, "_music_channel", None) or pygame.mixer.Channel(0)
            ch.set_volume(v)
        except Exception:
            pass

    def mute(self):
        self._muted = True
        try:
            ch = getattr(self, "_music_channel", None) or pygame.mixer.Channel(0)
            ch.set_volume(0.0)
        except Exception:
            pass

    def unmute(self):
        self._muted = False
        self.set_volume(getattr(self, "_volume", 1.0))

    def toggle_mute(self):
        if getattr(self, "_muted", False):
            self.unmute()
        else:
            self.mute()

    def get_bpm(self, track: str) -> int:
        return int(self.bpms.get(track, 120))

    # --- One-shot stingers / utility tracks (play on a free SFX channel) ---
    def _play_one_shot(self, track: str, volume: float = 1.0):
        if not _music_enabled_from_config():
            _hard_stop_music_channels()
            return
        if not self._init:
            return
        if track not in self.tracks:
            return
        try:
            ch = pygame.mixer.find_channel(True)
            snd = self.tracks[track]
            if getattr(self, "_muted", False):
                ch.set_volume(0.0)
            else:
                base = float(getattr(self, "_volume", 1.0))
                ch.set_volume(max(0.0, min(1.0, base * float(volume))))
            ch.play(snd, loops=0)
        except Exception:
            pass

    def play_achievement(self):
        self._play_one_shot("achievement", volume=1.0)

    def play_combo_drop(self):
        self._play_one_shot("combo_drop", volume=1.0)

    def play_tier_bell(self):
        self._play_one_shot("tier_bell", volume=1.0)

    def play_fallen(self):
        # Fallen is usually a full mood track; play it as background.
        self.play("fallen", loop=True, fade=300)

    def play_frisson(self):
        self._play_one_shot("frisson", volume=1.0)

    def play_cara_mia(self):
        self.play("cara_mia", loop=True, fade=300)

    # Hooks used by beat-reactive systems; safe no-ops if unused
    def pulse_beat(self, strength: float = 0.15):
        return

    def set_intensity(self, intensity: float):
        self._intensity = float(intensity)

    def swell(self, amount: float = 0.15):
        # tiny volume swell, capped
        v = float(getattr(self, "_volume", 1.0))
        self.set_volume(min(1.0, v + float(amount)))

    def cleanup(self):
        try:
            self.stop(fade=0)
        except Exception:
            pass


_ost: Optional[ProceduralOST] = None

def get_ost() -> ProceduralOST:
    global _ost
    if _ost is None:
        # This shouldn't happen if init_ost was called first
        _ost = ProceduralOST()
    return _ost


# ═══════════════════════════════════════════════════════════════════════════════
#                            FILE-BASED OST (DROP-IN)
# ═══════════════════════════════════════════════════════════════════════════════

class FileOST:
    """File-based OST loader using pygame.mixer.

    Goals:
      - Never stack looping beds (single-voiced bed on reserved channels)
      - Avoid bad loop seams by defaulting beds to *one-shot* playback + crossfade chaining
      - Keep stingers/SFX as true one-shots on free channels
      - Provide shim methods used by gameplay (pulse_beat, set_intensity, swell)

    Folders:
      - assets/audio/music/wotw/<mapped track>.(mp3|ogg|wav|flac)
      - music/<track>.(wav|ogg|mp3|flac)
    """

    BED_KEYS = [
        "story","release","overdrive","frenzy","breaking","transcendence",
        "climax","aftercare","love_bunny","edge",
        "ashen_bureaucracy","red_talismans","red_talisman_throne",
        "red_silk_oath","black_shrine_oath","black_sun_ledger",
    ]
    STINGER_KEYS = [
        "achievement","combo_drop","tier_bell","frisson","cara_mia"
    ]
    SPECIAL_KEYS = ["menu","fallen"]
    TRACK_OVERRIDES = {
        "menu": ("ashen_bureaucracy.mp3", 0.35),
        "story": ("ashen_bureaucracy.mp3", 0.35),
        "release": ("ashen_bureaucracy.mp3", 0.35),
        "overdrive": ("red_talisman_throne.mp3", 0.38),
        "frenzy": ("red_talismans.mp3", 0.38),
        "breaking": ("red_talismans.mp3", 0.38),
        "transcendence": ("red_talisman_throne.mp3", 0.38),
        "climax": ("red_talisman_throne.mp3", 0.38),
        "aftercare": ("ashen_bureaucracy.mp3", 0.35),
        "love_bunny": ("ashen_bureaucracy.mp3", 0.35),
        "edge": ("red_talismans.mp3", 0.38),
        "fallen": ("red_talismans.mp3", 0.38),
        "ashen_bureaucracy": ("ashen_bureaucracy.mp3", 0.35),
        "red_talismans": ("red_talismans.mp3", 0.38),
        "red_talisman_throne": ("red_talisman_throne.mp3", 0.38),
        "red_silk_oath": ("red_silk_oath.mp3", 0.30),
        "black_shrine_oath": ("black_shrine_oath.mp3", 0.28),
        "black_sun_ledger": ("black_sun_ledger.mp3", 0.32),
    }
    TRACK_FADE_MS = {
        "edge": 900,
        "frenzy": 900,
        "breaking": 900,
        "transcendence": 900,
        "climax": 1200,
        "fallen": 1400,
        "red_talismans": 900,
        "red_talisman_throne": 1100,
        "red_silk_oath": 1000,
        "black_shrine_oath": 1000,
        "black_sun_ledger": 1200,
    }
    SUPPORTED_EXTS = (".wav", ".ogg", ".mp3", ".flac")

    def __init__(self):
        self._volume = 1.0
        self._muted = False

        root = Path(__file__).resolve().parent
        self._music_dirs = [
            root / "assets" / "audio" / "music" / "wotw",
            root / "music",
        ]
        self._music_dir = self._music_dirs[0]
        self._tracks: Dict[str, "pygame.mixer.Sound"] = {}
        self._meta: Dict[str, Dict[str, float]] = {}  # dur/lead/trail/seam_rms/jump
        self._track_gain: Dict[str, float] = {}

        # Bed playback is single-voiced with true crossfade using two reserved channels.
        self._bed_ch_a = None
        self._bed_ch_b = None
        self._bed_active = 0  # 0 => A, 1 => B
        self._bed_track = None
        self._bed_started_at = 0.0
        self._bed_dur = 0.0
        self._bed_useful_dur = 0.0
        self._bed_loop_allowed: Dict[str, bool] = {}

        # Dynamic control
        self._intensity = 0.0  # 0..1
        self._last_switch_at = 0.0
        self._recent_beds: List[str] = []
        self._recent_window = int(os.getenv("LOCKKEY_OST_NOREPEAT", "4") or "4")

        # Timing knobs
        self._xfade_ms = int(os.getenv("LOCKKEY_OST_XFADE_MS", "650") or "650")
        self._guard_s = float(os.getenv("LOCKKEY_OST_SWITCH_GUARD_S", "0.35") or 0.35)
        self._menu_hold_s = float(os.getenv("LOCKKEY_OST_MENU_HOLD_S", "4.0") or 4.0)

        # Menu handling
        try:
            self._menu_atten_db = float(os.getenv("LOCKKEY_MENU_ATTEN_DB", "-4") or -4.0)
        except Exception:
            self._menu_atten_db = -4.0

    def _iter_track_candidates(self, key: str):
        seen = set()

        override = self.TRACK_OVERRIDES.get(key)
        if override:
            filename, gain = override
            candidate = self._music_dirs[0] / str(filename)
            seen.add(str(candidate).lower())
            yield candidate, float(gain)

        for music_dir in self._music_dirs:
            for ext in self.SUPPORTED_EXTS:
                candidate = music_dir / f"{key}{ext}"
                norm = str(candidate).lower()
                if norm in seen:
                    continue
                seen.add(norm)
                yield candidate, 1.0

    def _resolve_track_asset(self, key: str):
        for candidate, gain in self._iter_track_candidates(key):
            if candidate.exists():
                return candidate, gain
        return None, 1.0

    def _fade_ms_for(self, track: str) -> int:
        try:
            return max(int(self._xfade_ms), int(self.TRACK_FADE_MS.get(track, 0)))
        except Exception:
            return int(self._xfade_ms)

    def _sound_gain(self, track: str) -> float:
        gain = float(self._track_gain.get(track, 1.0))
        if track == "menu":
            gain *= 10.0 ** (self._menu_atten_db / 20.0)
        return max(0.0, min(1.0, gain))

    # -----------------------------
    # Init + loading
    # -----------------------------
    def init(self) -> bool:
        if not PYGAME_AVAILABLE:
            return False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=48000, size=-16, channels=2, buffer=512)
            # Ensure we have enough channels for: beds (0..1), sfx (2..11), voice (12..15)
            try:
                pygame.mixer.set_num_channels(max(16, pygame.mixer.get_num_channels() or 16))
            except Exception:
                pygame.mixer.set_num_channels(16)
        except Exception as e:
            print(f"  ✗ pygame.mixer.init failed: {e}")
            return False

        # Reserve bed channels
        try:
            self._bed_ch_a = pygame.mixer.Channel(0)
            self._bed_ch_b = pygame.mixer.Channel(1)
        except Exception:
            self._bed_ch_a = None
            self._bed_ch_b = None

        # The frozen distribution loads this file more than once under distinct
        # module names. Keep one process-wide decoded Sound per physical file so
        # aliases and subsequent module loads do not decode long MP3s repeatedly.
        sound_cache = getattr(pygame, "_wotw_file_ost_sound_cache", None)
        if not isinstance(sound_cache, dict):
            sound_cache = {}
            setattr(pygame, "_wotw_file_ost_sound_cache", sound_cache)

        # Load canonical tracks if present
        for key in [
            "menu","story","release","overdrive","frenzy","breaking","transcendence",
            "climax","aftercare","love_bunny","edge","achievement","fallen",
            "combo_drop","tier_bell","frisson","cara_mia",
            "ashen_bureaucracy","red_talismans","red_talisman_throne",
            "red_silk_oath","black_shrine_oath","black_sun_ledger",
        ]:
            fp, gain = self._resolve_track_asset(key)
            if fp is None:
                continue
            try:
                cache_key = str(fp.resolve()).casefold()
                sound = sound_cache.get(cache_key)
                if sound is None:
                    sound = pygame.mixer.Sound(str(fp))
                    sound_cache[cache_key] = sound
                self._tracks[key] = sound
                self._track_gain[key] = float(gain)
                if fp.suffix.lower() == ".wav":
                    self._meta[key] = self._analyze_wav(fp)
                else:
                    self._meta[key] = {
                        "dur_s": float(self._tracks[key].get_length() or 0.0),
                        "lead_s": 0.0,
                        "trail_s": 0.0,
                        "seam_rms": 1.0,
                        "jump": 1.0,
                    }
            except Exception as e:
                print(f"  ⚠ could not load {fp.name}: {e}")
                try:
                    cache_key = str(fp.resolve()).casefold()
                    sound = sound_cache.get(cache_key)
                    if sound is None:
                        sound = pygame.mixer.Sound(str(fp))
                        sound_cache[cache_key] = sound
                    self._tracks[key] = sound
                    self._meta[key] = self._analyze_wav(fp)
                except Exception as e:
                    print(f"  ⚠ could not load {fp.name}: {e}")

        if not self._tracks:
            print("  ✗ No music tracks found in assets/audio/music/wotw or music/. Falling back to procedural OST.")
            return False

        # Determine which tracks are safe to loop (menu usually is; most beds aren't)
        for k in self._tracks.keys():
            allow = False
            if k == "menu":
                allow = True
            else:
                md = self._meta.get(k, {})
                seam_rms = float(md.get("seam_rms", 1.0) or 1.0)
                lead = float(md.get("lead_s", 0.0) or 0.0)
                trail = float(md.get("trail_s", 0.0) or 0.0)
                # Only allow looping if seam is already extremely clean and no big silence pads.
                allow = (seam_rms < 0.04) and (lead < 0.15) and (trail < 0.25)
            self._bed_loop_allowed[k] = bool(allow)

        self._apply_volume()
        print(f"  ✓ File OST Ready: {len(self._tracks)} wavs")
        return True

    def generate_all(self, callback=None):
        return

    # -----------------------------
    # Meta analysis (no numpy)
    # -----------------------------
    def _analyze_wav(self, path: Path) -> Dict[str, float]:
        out = {"dur_s": 0.0, "lead_s": 0.0, "trail_s": 0.0, "seam_rms": 1.0, "jump": 1.0}
        try:
            import wave, audioop
            with wave.open(str(path), "rb") as wf:
                nch = wf.getnchannels()
                sw = wf.getsampwidth()
                fr = wf.getframerate()
                n = wf.getnframes()
                frames = wf.readframes(n)
            if fr and n:
                out["dur_s"] = float(n) / float(fr)
            if sw != 2 or not frames:
                return out

            # downmix to mono for analysis
            if nch == 2:
                left = audioop.tomono(frames, 2, 1.0, 0.0)
                right = audioop.tomono(frames, 2, 0.0, 1.0)
                frames_m = audioop.mul(audioop.add(left, right, 2), 2, 0.5)
            else:
                frames_m = frames

            # lead/trail silence estimate using RMS windows
            win = int(max(1, min(n, int(fr * 0.05))))  # 50ms
            win_bytes = win * 2
            thresh = 0.0015  # ~ -56dBFS
            def rms_at(off_frames: int) -> float:
                b0 = off_frames * 2
                b1 = min(len(frames_m), b0 + win_bytes)
                if b1 <= b0:
                    return 0.0
                return float(audioop.rms(frames_m[b0:b1], 2)) / 32768.0

            # leading silence
            lead = 0.0
            step = win
            i = 0
            while i < n and rms_at(i) < thresh:
                i += step
            lead = float(i) / float(fr)
            # trailing silence
            j = n - win
            while j > 0 and rms_at(j) < thresh:
                j -= step
            trail = float(max(0, n - j - win)) / float(fr)

            out["lead_s"] = max(0.0, min(out["dur_s"], lead))
            out["trail_s"] = max(0.0, min(out["dur_s"], trail))

            # seam metrics: RMS diff between first and last 100ms + endpoint jump
            seam_frames = int(max(1, min(n // 4, int(fr * 0.10))))
            seam_bytes = seam_frames * 2
            head = frames_m[:seam_bytes]
            tail = frames_m[-seam_bytes:] if len(frames_m) >= seam_bytes else frames_m

            # RMS of difference (approx): rms(head - tail)
            try:
                # audioop.add with factor -1 to subtract
                diff = audioop.add(head, audioop.mul(tail, 2, -1.0), 2)
                out["seam_rms"] = float(audioop.rms(diff, 2)) / 32768.0
            except Exception:
                out["seam_rms"] = 1.0

            try:
                # endpoint jump (first sample vs last sample)
                if len(frames_m) >= 4:
                    first = int.from_bytes(frames_m[0:2], "little", signed=True) / 32768.0
                    last = int.from_bytes(frames_m[-2:], "little", signed=True) / 32768.0
                    out["jump"] = abs(first - last)
            except Exception:
                out["jump"] = 1.0

        except Exception:
            return out
        return out

    # -----------------------------
    # Volume + channels
    # -----------------------------
    def _apply_volume(self):
        cfg_enabled = _music_enabled_from_config()
        if not cfg_enabled:
            self._muted = True
        base = 0.0 if self._muted or not cfg_enabled else float(self._volume)
        base = max(0.0, min(1.0, base))
        for k, s in self._tracks.items():
            try:
                s.set_volume(self._sound_gain(k))
            except Exception:
                pass
        # Also force active bed channels. Sound.set_volume alone does not always
        # mute sounds already playing on pygame channels.
        try:
            for ch in (self._bed_ch_a, self._bed_ch_b, getattr(self, "_current_channel", None)):
                if ch is not None:
                    ch.set_volume(base)
                    if base <= 0.0:
                        ch.stop()
        except Exception:
            pass

    def set_volume(self, vol: float):
        self._volume = max(0.0, min(1.0, float(vol)))
        self._apply_volume()

    def mute(self):
        self._muted = True
        _hard_stop_music_channels()
        self._apply_volume()

    def unmute(self):
        self._muted = not _music_enabled_from_config()
        if not self._muted:
            self._volume = _music_volume_from_config(self._volume)
        self._apply_volume()

    def stop(self):
        try:
            if self._bed_ch_a is not None:
                self._bed_ch_a.stop()
            if self._bed_ch_b is not None:
                self._bed_ch_b.stop()
            pygame.mixer.stop()
        except Exception:
            pass
        self._bed_track = None
        self._current_channel = None

    def _now(self) -> float:
        try:
            import time
            return float(time.time())
        except Exception:
            return 0.0

    def _bed_channels(self):
        return (self._bed_ch_a, self._bed_ch_b)

    def _active_bed_channel(self):
        a, b = self._bed_channels()
        return a if self._bed_active == 0 else b

    def _inactive_bed_channel(self):
        a, b = self._bed_channels()
        return b if self._bed_active == 0 else a

    def _flip_bed(self):
        self._bed_active = 1 - int(self._bed_active)

    def _find_sfx_channel(self):
        # Keep channels 0..1 reserved for beds; 12..15 are reserved by voice engine.
        try:
            for i in range(2, 12):
                ch = pygame.mixer.Channel(i)
                if not ch.get_busy():
                    return ch
            return pygame.mixer.find_channel(True)
        except Exception:
            return None

    # -----------------------------
    # Bed playback + smart chaining
    # -----------------------------
    def _bed_play(self, track: str, fade_ms: int = 0, loop: bool = False):
        if not _music_enabled_from_config():
            self._muted = True
            self._bed_track = None
            _hard_stop_music_channels()
            return
        else:
            self._muted = False
            self._volume = _music_volume_from_config(self._volume)
            self._apply_volume()
        s = self._tracks.get(track)
        if not s:
            return
        ch_on = self._active_bed_channel()
        ch_off = self._inactive_bed_channel()
        if ch_on is None or ch_off is None:
            # fallback
            try:
                loops = -1 if loop else 0
                self._current_channel = s.play(loops=loops)
            except Exception:
                pass
            return

        # Guard against thrash
        now = self._now()
        if (now - float(self._last_switch_at or 0.0)) < float(self._guard_s or 0.0):
            return

        # If already playing this bed, do nothing.
        if self._bed_track == track and ch_on.get_busy():
            return

        # Crossfade: fade out current bed, fade in new bed on the other channel.
        try:
            if ch_on.get_busy():
                ch_on.fadeout(int(fade_ms or 0))
        except Exception:
            pass

        try:
            ch_off.stop()
        except Exception:
            pass

        try:
            loops = -1 if loop else 0
            ch_off.play(s, loops=loops, fade_ms=int(fade_ms or 0))
        except TypeError:
            # older pygame without fade_ms kw? (rare)
            try:
                ch_off.play(s, loops=loops)
            except Exception:
                pass
        except Exception:
            pass

        self._flip_bed()
        self._bed_track = track
        self._bed_started_at = now
        md = self._meta.get(track, {})
        self._bed_dur = float(md.get("dur_s", 0.0) or 0.0)
        # Use "useful" duration to avoid long trailing silence (start next before the dead air)
        trail = float(md.get("trail_s", 0.0) or 0.0)
        self._bed_useful_dur = max(0.0, self._bed_dur - max(0.0, trail))
        self._last_switch_at = now

        # Recent history
        try:
            if track != "menu":
                self._recent_beds.append(track)
                self._recent_beds = self._recent_beds[-max(1, self._recent_window):]
        except Exception:
            pass

    def _choose_bed_pool(self) -> List[str]:
        # Use intensity to choose a phase-appropriate pool
        x = float(self._intensity or 0.0)
        calm = ["story", "release", "aftercare", "love_bunny"]
        drive = ["overdrive", "breaking", "transcendence"]
        peak  = ["frenzy", "edge"]
        recover = ["aftercare", "story", "release"]

        if x >= 0.78:
            pool = peak
        elif x >= 0.45:
            pool = drive + peak[:1]
        elif x >= 0.22:
            pool = calm + drive[:1]
        else:
            pool = calm

        # Recovery bias: after too many peaks, force recover
        try:
            recent = list(self._recent_beds)[-3:]
            peaks = sum(1 for r in recent if r in peak)
            if peaks >= 2:
                pool = recover
        except Exception:
            pass

        # Filter to existing tracks, exclude menu, exclude bad loopers from loop rotation
        out = []
        for t in pool:
            if t == "menu":
                continue
            if t in self._tracks:
                out.append(t)
        if not out:
            # fallback to any bed track present
            out = [t for t in self.BED_KEYS if t in self._tracks and t != "menu"]
        return out

    def _pick_next_bed(self) -> str:
        pool = self._choose_bed_pool()
        # No repeat window
        recent = set(self._recent_beds[-max(1, self._recent_window):])
        cand = [t for t in pool if t not in recent]
        if not cand:
            cand = pool[:]
        # Avoid immediate same-track
        if self._bed_track in cand and len(cand) > 1:
            cand = [t for t in cand if t != self._bed_track]
        try:
            import random
            return random.choice(cand) if cand else (pool[0] if pool else "release")
        except Exception:
            return cand[0] if cand else (pool[0] if pool else "release")

    def _tick(self):
        # Called frequently via pulse_beat / set_intensity / swell.
        # Chains beds before the end to avoid audible loop seams.
        if self._bed_track is None:
            return
        if self._bed_track == "menu":
            return
        ch = self._active_bed_channel()
        if ch is None:
            return
        now = self._now()
        # If bed isn't playing, start next immediately.
        if not ch.get_busy():
            nxt = self._pick_next_bed()
            self._bed_play(nxt, fade_ms=self._fade_ms_for(nxt), loop=False)
            return
        # If we know duration, crossfade near end.
        useful = float(self._bed_useful_dur or 0.0)
        if useful > 1.0:
            xfade_ms = self._fade_ms_for(self._bed_track)
            xfade_s = max(0.12, float(xfade_ms) / 1000.0)
            if (now - float(self._bed_started_at or 0.0)) >= max(0.0, useful - xfade_s - 0.05):
                nxt = self._pick_next_bed()
                self._bed_play(nxt, fade_ms=self._fade_ms_for(nxt), loop=False)

    # -----------------------------
    # Public surface
    # -----------------------------
    def play(self, track: str, loop: bool = True):
        if not _music_enabled_from_config():
            self._muted = True
            self._bed_track = None
            _hard_stop_music_channels()
            return
        track = str(track or "").strip()
        if not track:
            return
        # Menu: loop is allowed and expected.
        if track == "menu":
            self._bed_play("menu", fade_ms=self._fade_ms_for("menu"), loop=True)
            # Cap how long menu can survive into FLOW/endless
            self._last_switch_at = self._now()
            return

        # Fallen is a special "state" bed: treat as bed but avoid looping unless it's actually loop-safe.
        if track == "fallen":
            allow_loop = bool(self._bed_loop_allowed.get("fallen", False))
            self._bed_play("fallen", fade_ms=self._fade_ms_for("fallen"), loop=bool(loop and allow_loop))
            return

        # Stingers / one-shots
        if track in self.STINGER_KEYS or (not loop and track in self._tracks):
            s = self._tracks.get(track)
            if not s:
                return
            ch = self._find_sfx_channel()
            if ch is None:
                try:
                    s.set_volume(max(0.0, min(1.0, float(self._volume) * self._sound_gain(track))))
                    s.play()
                except Exception:
                    pass
                return
            try:
                ch.set_volume(max(0.0, min(1.0, float(self._volume))))
                ch.play(s)
            except Exception:
                try:
                    s.set_volume(max(0.0, min(1.0, float(self._volume) * self._sound_gain(track))))
                    s.play()
                except Exception:
                    pass
            return

        # Beds: default to non-looping unless it's explicitly loop-safe.
        allow_loop = bool(self._bed_loop_allowed.get(track, False))
        want_loop = bool(loop and allow_loop)
        self._bed_play(track, fade_ms=self._fade_ms_for(track), loop=want_loop)


    def play_tier(self, tier=0, *args, **kwargs):
        """Compatibility API: called by ogre_shader via ost_tier(t).

        We keep this musically minimal for file-OST: it gently nudges the bed selection rules,
        but does not hard-switch or add hype layers.
        """
        try:
            self._tier = int(tier or 0)
        except Exception:
            self._tier = 0
        # Optional: tiny biasing hook if your scheduler uses it
        return None
    def play_achievement(self): self.play("achievement", loop=False)
    def play_combo_drop(self): self.play("combo_drop", loop=False)
    def play_tier_bell(self): self.play("tier_bell", loop=False)
    def play_fallen(self): self.play("fallen", loop=True)
    def play_frisson(self): self.play("frisson", loop=False)
    def play_cara_mia(self): self.play("cara_mia", loop=False)

    def get_bpm(self) -> int:
        return int(os.getenv("LOCKKEY_BPM", "150").strip() or "150")

    # Procedural API shims

    def pulse_beat(self, strength=0.15, *args, **kwargs):
        """Compatibility API: called by ost_pulse(). For file-OST we keep it subtle."""
        try:
            self._last_pulse = self._now()
            self._pulse_strength = float(strength or 0.0)
        except Exception:
            pass
        return None
    def pulse(self, strength: float = 0.15):
        self._tick()
        return


    def set_intensity(self, intensity=0.0, *args, **kwargs):
        """Compatibility API: called by ost_intensity(). We store it for the scheduler."""
        try:
            self._intensity = max(0.0, min(1.0, float(intensity or 0.0)))
        except Exception:
            self._intensity = 0.0
        return None
    def swell(self, strength: float = 0.25):
        # Optional: tiny volume lift during swell moments (clamped)
        try:
            s = float(strength)
        except Exception:
            s = 0.0
        s = max(0.0, min(1.0, s))
        # very subtle: up to +6%
        try:
            base = float(self._volume)
            self.set_volume(max(0.0, min(1.0, base * (1.0 + 0.06 * s))))
        except Exception:
            pass
        self._tick()



def init_ost(callback=None):
    """Initialize OST.

    Preference order:
      1) File-based OST (assets/audio/music/wotw/* or music/*) when present or when LOCKKEY_OST_FILES=1
      2) Procedural OST fallback
    """
    global _ost

    want_files = os.getenv("LOCKKEY_OST_FILES", "0").strip().lower() in ("1","true","yes","on")
    root = Path(__file__).resolve().parent
    music_dirs = [
        root / "assets" / "audio" / "music" / "wotw",
        root / "music",
    ]
    has_files = any(
        music_dir.exists() and any(music_dir.glob(f"*{ext}") for ext in FileOST.SUPPORTED_EXTS)
        for music_dir in music_dirs
    )

    # Try file OST first when requested or when files are present
    if want_files or has_files:
        _ost = FileOST()
        if _ost.init():
            try:
                keys = sorted(getattr(_ost, "_tracks", {}).keys())
                print(f"  ✓ Tracks: {keys}")
            except Exception:
                pass
            return _ost

    # Fall back to procedural OST
    _ost = ProceduralOST()
    if _ost.init():
        _ost.generate_all(callback)
    else:
        print("  ✗ OST init() returned False!")
    return _ost

def ost_play(track: str, loop: bool = True):
    if not _music_enabled_from_config():
        _hard_stop_music_channels()
        try: get_ost().mute()
        except Exception: pass
        return
    get_ost().play(track, loop)

def ost_tier(tier: int):
    if not _music_enabled_from_config():
        _hard_stop_music_channels()
        try: get_ost().mute()
        except Exception: pass
        return
    get_ost().play_tier(tier)

def ost_stop():
    _hard_stop_music_channels()
    get_ost().stop()

def ost_volume(vol: float):
    if not _music_enabled_from_config():
        _hard_stop_music_channels()
        try: get_ost().mute()
        except Exception: pass
        return
    get_ost().set_volume(vol)

def ost_mute():
    get_ost().mute()

def ost_unmute():
    if not _music_enabled_from_config():
        _hard_stop_music_channels()
        return
    get_ost().unmute()

def ost_achievement():
    if not _music_enabled_from_config():
        _hard_stop_music_channels()
        return
    get_ost().play_achievement()

def ost_combo_drop():
    """Play combo drop sound - fallen angel moment."""
    if not _music_enabled_from_config():
        _hard_stop_music_channels()
        return
    get_ost().play_combo_drop()

def ost_tier_bell():
    """Play tier transition bell."""
    if not _music_enabled_from_config():
        _hard_stop_music_channels()
        return
    get_ost().play_tier_bell()

def ost_fallen():
    """Switch to fallen angel track."""
    if not _music_enabled_from_config():
        _hard_stop_music_channels()
        return
    get_ost().play_fallen()

def ost_frisson():
    """Play frisson sting - blessed squeak for combo milestones."""
    if not _music_enabled_from_config():
        _hard_stop_music_channels()
        return
    get_ost().play_frisson()

def ost_cara_mia():
    """Play full Cara Mia phrase - for very special moments."""
    if not _music_enabled_from_config():
        _hard_stop_music_channels()
        return
    get_ost().play_cara_mia()

def ost_bpm() -> int:
    return get_ost().get_bpm()

def ost_pulse(strength: float = 0.15):
    """Pulse music on beat hit - creates breathing feel."""
    if not _music_enabled_from_config():
        _hard_stop_music_channels()
        return
    get_ost().pulse_beat(strength)

def ost_intensity(intensity: float):
    """Set music intensity (0-1) based on gameplay."""
    if not _music_enabled_from_config():
        _hard_stop_music_channels()
        return
    get_ost().set_intensity(intensity)

def ost_swell(duration: float = 0.5):
    """Dramatic volume swell."""
    if not _music_enabled_from_config():
        _hard_stop_music_channels()
        return
    get_ost().swell(duration)


# ═══════════════════════════════════════════════════════════════════════════════
#                              TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("OGRE SHADER - PROCEDURAL OST")
    print("=" * 60)
    
    if not NUMPY_AVAILABLE:
        print("numpy required: pip install numpy")
        exit(1)
    if not PYGAME_AVAILABLE:
        print("pygame required: pip install pygame")
        exit(1)
    
    def progress(name, i, total):
        bar = "█" * i + "░" * (total - i)
        print(f"\r  [{bar}] {i}/{total} - {name:<15}", end="", flush=True)
    
    print("\nGenerating OST...")
    ost = init_ost(progress)
    print("\n")
    
    print("Commands: 0-4 (tiers), m/s/c/a/b/e (tracks), x (sting), +/-, space, q")
    
    ost.play('menu')
    print(f"Playing: menu ({ost.get_bpm()} BPM)")
    
    try:
        while True:
            cmd = input("> ").strip().lower()
            if cmd == 'q': break
            elif cmd in '01234':
                ost.play_tier(int(cmd))
                print(f"Tier {cmd}: {ost._current} ({ost.get_bpm()} BPM)")
            elif cmd == 'm': ost.play('menu'); print(f"menu ({ost.get_bpm()} BPM)")
            elif cmd == 's': ost.play('story'); print(f"story ({ost.get_bpm()} BPM)")
            elif cmd == 'c': ost.play('climax', False); print(f"climax ({ost.get_bpm()} BPM)")
            elif cmd == 'a': ost.play('aftercare'); print(f"aftercare ({ost.get_bpm()} BPM)")
            elif cmd == 'b': ost.play('love_bunny'); print(f"love_bunny ({ost.get_bpm()} BPM)")
            elif cmd == 'e': ost.play('edge'); print(f"edge ({ost.get_bpm()} BPM)")
            elif cmd == 'x': ost.play_achievement(); print("*achievement*")
            elif cmd == '+': ost.set_volume(min(1, ost.volume + 0.1)); print(f"Vol: {ost.volume:.0%}")
            elif cmd == '-': ost.set_volume(max(0, ost.volume - 0.1)); print(f"Vol: {ost.volume:.0%}")
            elif cmd in ('', ' '): print("Muted" if ost.toggle_mute() else "Unmuted")
    except KeyboardInterrupt:
        pass
    
    ost.cleanup()
    print("\nDone!")
