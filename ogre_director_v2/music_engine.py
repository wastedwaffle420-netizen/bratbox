#!/usr/bin/env python3
"""
OGRE SHADER - MUSIC & RHYTHM SOUND ENGINE
"two animals. one room. forever."

TWO SYSTEMS:
1. BACKGROUND MUSIC - ambient tracks that shift with game state
2. RHYTHM SOUNDS - procedural hit/miss sounds synced to gameplay

This is the FOUNDATION - recruit an OST maker to replace procedural
sounds with proper samples and composed tracks.

RHYTHM SOUNDS:
  - Hit sounds (per lane: A, S, D, F)
  - Perfect hit (sparkle)
  - Miss sounds (thud)
  - Combo milestone chimes
  - Beat pulse (metronome-like)
"""

import os
import time
import threading
import math
import struct
import wave
import io
from pathlib import Path
from typing import Optional, Dict, Callable, List
from enum import Enum
from dataclasses import dataclass


def _fiendish_asset_root() -> Path:
    try:
        env_root = str(os.environ.get("FIENDISH_RELEASE_DIR", "") or "").strip()
        if env_root:
            return Path(env_root).expanduser().resolve()
    except Exception:
        pass
    return Path(__file__).resolve().parent

# Try numpy for better sound generation
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

SAMPLE_RATE = 44100

# ═══════════════════════════════════════════════════════════════════════════════
#                         PROCEDURAL SOUND GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

def generate_sine(freq: float, duration: float, volume: float = 0.3,
                  attack: float = 0.01, release: float = 0.05) -> bytes:
    """Generate a sine wave with envelope."""
    if not NUMPY_AVAILABLE:
        return b''
    
    samples = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, samples, False)
    wave = np.sin(2 * np.pi * freq * t)
    
    # Envelope
    envelope = np.ones(samples)
    attack_samples = min(int(SAMPLE_RATE * attack), samples // 2)
    release_samples = min(int(SAMPLE_RATE * release), samples // 2)
    
    if attack_samples > 0:
        envelope[:attack_samples] = np.linspace(0, 1, attack_samples)
    if release_samples > 0:
        envelope[-release_samples:] = np.linspace(1, 0, release_samples)
    
    wave = wave * envelope * volume
    wave = (wave * 32767).astype(np.int16)
    return wave.tobytes()


def generate_hit_sound(lane: int, quality: str = "good") -> bytes:
    """Generate a hit sound for a specific lane.

    Qualities:
      - good: clean tone
      - perfect: brighter sparkle
      - voice: warmer/formant-ish (for "voice" accents)
      - squish: thumpy/noisy (for slapstick barrage)
      - bleat: goatcore squeak/bleat accent
    """
    if not NUMPY_AVAILABLE:
        return b''

    # Different pitches per lane (pentatonic-ish)
    lane_freqs = {
        0: 440.0,   # A - A4
        1: 523.25,  # S - C5
        2: 587.33,  # D - D5
        3: 659.25,  # F - E5
    }

    base_freq = lane_freqs.get(lane, 440.0)

    if quality == "perfect":
        # Perfect: bright, sparkly
        duration = 0.12
        volume = 0.40

        samples = int(SAMPLE_RATE * duration)
        t = np.linspace(0, duration, samples, False)

        # Main tone + octave + fifth
        wave = (np.sin(2 * np.pi * base_freq * t) * 0.50 +
                np.sin(2 * np.pi * base_freq * 2 * t) * 0.30 +
                np.sin(2 * np.pi * base_freq * 1.5 * t) * 0.20)

        envelope = np.exp(-15 * t)
        wave = wave * envelope * volume

    elif quality == "voice":
        # Voice-tuned: warmer, formant-ish, slightly longer with gentle vibrato
        duration = 0.14
        volume = 0.38

        samples = int(SAMPLE_RATE * duration)
        t = np.linspace(0, duration, samples, False)

        vib = 1.0 + 0.015 * np.sin(2 * np.pi * 6.0 * t)   # gentle vibrato
        f = base_freq * 0.75 * vib

        wave = (np.sin(2 * np.pi * f * t) * 0.55 +
                np.sin(2 * np.pi * f * 2 * t) * 0.25 +
                np.sin(2 * np.pi * f * 3 * t) * 0.12)

        noise = (np.random.randn(samples) * 0.015)  # breath
        wave = (wave + noise)

        # Softer envelope
        env = (1 - np.exp(-t * 220)) * np.exp(-t * 10.0)
        wave = wave * env * volume

    elif quality == "squish":
        # Squishy: thumpy + soft noise, quick pitch-drop
        duration = 0.10
        volume = 0.42

        samples = int(SAMPLE_RATE * duration)
        t = np.linspace(0, duration, samples, False)

        drop = np.linspace(1.0, 0.6, samples)
        f = base_freq * 0.55 * drop

        tone = np.sin(2 * np.pi * f * t) * 0.35
        noise = np.random.randn(samples) * 0.12

        # Simple low-pass-ish smoothing
        k = 6
        noise_smooth = np.convolve(noise, np.ones(k)/k, mode='same')

        wave = tone + noise_smooth * 0.60

        env = (1 - np.exp(-t * 400)) * np.exp(-t * 22.0)
        wave = wave * env * volume
    elif quality == "bleat":
        # Bleat: cute-frantic goatcore accent (formant-ish with a squeaky tail)
        duration = 0.16
        volume = 0.40

        samples = int(SAMPLE_RATE * duration)
        t = np.linspace(0, duration, samples, False)

        # Pitch swoop + tiny end squeak
        swoop = np.linspace(1.15, 0.85, samples)
        squeak = 1.0 + 0.10 * np.exp(-((t - duration*0.78)/(duration*0.08))**2)
        f = base_freq * 0.55 * swoop * squeak

        # Formant-ish stack
        wave = (np.sin(2 * np.pi * f * t) * 0.48 +
                np.sin(2 * np.pi * f * 2.01 * t) * 0.22 +
                np.sin(2 * np.pi * f * 3.02 * t) * 0.10)

        breath = np.random.randn(samples) * 0.020
        wave = wave + breath

        # Envelope: quick rise, sustained, then cute drop
        env = (1 - np.exp(-t * 180)) * np.exp(-t * 7.5)
        wave = wave * env * volume



    else:
        # Good: clean, single tone
        duration = 0.08
        volume = 0.30

        samples = int(SAMPLE_RATE * duration)
        t = np.linspace(0, duration, samples, False)

        wave = np.sin(2 * np.pi * base_freq * t)
        envelope = np.exp(-20 * t)
        wave = wave * envelope * volume

    wave = (wave * 32767).astype(np.int16)
    return wave.tobytes()

def generate_miss_sound() -> bytes:
    """Generate a miss/error sound."""
    if not NUMPY_AVAILABLE:
        return b''
    
    duration = 0.15
    samples = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, samples, False)
    
    # Low thud + noise
    thud = np.sin(2 * np.pi * 80 * t) * np.exp(-15 * t)
    noise = np.random.uniform(-0.3, 0.3, samples) * np.exp(-20 * t)
    
    wave = (thud * 0.6 + noise * 0.4) * 0.25
    wave = (wave * 32767).astype(np.int16)
    return wave.tobytes()


def generate_beat_pulse(bpm: int, intensity: float = 0.5) -> bytes:
    """Generate a subtle beat pulse (metronome-like)."""
    if not NUMPY_AVAILABLE:
        return b''
    
    duration = 0.05
    samples = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, samples, False)
    
    # Subtle click
    freq = 800 + intensity * 400  # Higher pitch at higher intensity
    wave = np.sin(2 * np.pi * freq * t) * np.exp(-40 * t)
    
    volume = 0.1 + intensity * 0.1
    wave = wave * volume
    wave = (wave * 32767).astype(np.int16)
    return wave.tobytes()


def generate_combo_chime(combo: int) -> bytes:
    """Generate a combo milestone chime."""
    if not NUMPY_AVAILABLE:
        return b''
    
    duration = 0.3
    samples = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, samples, False)
    
    # Rising arpeggio based on combo level
    if combo >= 100:
        freqs = [523.25, 659.25, 783.99, 1046.5]  # C5, E5, G5, C6
    elif combo >= 50:
        freqs = [440.0, 554.37, 659.25]  # A4, C#5, E5
    elif combo >= 25:
        freqs = [392.0, 493.88]  # G4, B4
    else:
        freqs = [440.0]  # A4
    
    wave = np.zeros(samples)
    note_len = samples // len(freqs)
    
    for i, freq in enumerate(freqs):
        start = i * note_len
        end = min(start + note_len, samples)
        note_t = t[start:end] - t[start]
        note_wave = np.sin(2 * np.pi * freq * note_t) * np.exp(-8 * note_t)
        wave[start:end] += note_wave
    
    wave = wave * 0.35
    wave = (wave * 32767).astype(np.int16)
    return wave.tobytes()


# ═══════════════════════════════════════════════════════════════════════════════
#                              TRACK DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

class MusicTrack(Enum):
    SILENCE = "silence"
    MENU = "menu"
    STORY = "story"
    RELEASE = "release"
    OVERDRIVE = "overdrive"
    FRENZY = "frenzy"
    BREAKING = "breaking"
    TRANSCENDENCE = "transcendence"
    CLIMAX = "climax"
    AFTERCARE = "aftercare"
    LOVE_BUNNY = "love_bunny"
    EDGE = "edge"
    ACHIEVEMENT = "achievement"


@dataclass
class TrackInfo:
    name: str
    bpm: int
    filename: str
    loop: bool = True
    crossfade_in: float = 1.0
    crossfade_out: float = 0.5


TRACK_INFO: Dict[MusicTrack, TrackInfo] = {
    MusicTrack.SILENCE: TrackInfo("Silence", 0, "", loop=False),
    MusicTrack.MENU: TrackInfo("Two Animals", 60, "01_menu.ogg", crossfade_in=2.0),
    MusicTrack.STORY: TrackInfo("Circulation Issue", 88, "02_story.ogg"),
    MusicTrack.RELEASE: TrackInfo("Hold Still", 100, "03_release.ogg"),
    MusicTrack.OVERDRIVE: TrackInfo("More", 115, "04_overdrive.ogg"),
    MusicTrack.FRENZY: TrackInfo("Too Fast", 130, "05_frenzy.ogg", crossfade_in=0.5),
    MusicTrack.BREAKING: TrackInfo("Hold", 150, "06_breaking.ogg", crossfade_in=0.3),
    MusicTrack.TRANSCENDENCE: TrackInfo("Not Yet", 175, "07_transcendence.ogg", crossfade_in=0.5),
    MusicTrack.CLIMAX: TrackInfo("Everything", 140, "08_climax.ogg", loop=False, crossfade_in=0.1),
    MusicTrack.AFTERCARE: TrackInfo("Birdsong", 55, "09_aftercare.ogg", crossfade_in=3.0),
    MusicTrack.LOVE_BUNNY: TrackInfo("Woof", 120, "10_love_bunny.ogg"),
    MusicTrack.EDGE: TrackInfo("Please", 130, "11_edge.ogg"),
    MusicTrack.ACHIEVEMENT: TrackInfo("Achievement", 120, "12_achievement.ogg", loop=False),
}

TIER_TRACKS = {
    0: MusicTrack.RELEASE,
    1: MusicTrack.OVERDRIVE,
    2: MusicTrack.FRENZY,
    3: MusicTrack.BREAKING,
    4: MusicTrack.TRANSCENDENCE,
}


# ═══════════════════════════════════════════════════════════════════════════════
#                              AUDIO BACKEND
# ═══════════════════════════════════════════════════════════════════════════════

class AudioBackend:
    """Base audio backend."""
    
    def __init__(self):
        self.volume = 0.7
        self.mix = 1.0  # additional global SFX mix multiplier
        self.current_track: Optional[str] = None
        self._initialized = False
    
    def load(self, filepath: str) -> bool:
        return False
    
    def play(self, loop: bool = True):
        pass
    
    def stop(self):
        pass
    
    def set_volume(self, volume: float):
        self.volume = max(0.0, min(1.0, volume))
    
    def fade_to(self, volume: float, duration: float):
        pass
    
    def is_playing(self) -> bool:
        return False
    
    def cleanup(self):
        pass


class SilentBackend(AudioBackend):
    """Silent backend - tracks state without audio."""
    
    def __init__(self):
        super().__init__()
        self._playing = False
        self._initialized = True
    
    def load(self, filepath: str) -> bool:
        self.current_track = filepath
        return True
    
    def play(self, loop: bool = True):
        self._playing = True
    
    def stop(self):
        self._playing = False
    
    def is_playing(self) -> bool:
        return self._playing


class PygameBackend(AudioBackend):
    """Pygame mixer backend."""
    
    def __init__(self):
        super().__init__()
        self._sound = None
        self._channel = None
        try:
            import pygame
            import pygame.mixer
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
            self._pygame = pygame
            self._initialized = True
        except:
            pass
    
    def load(self, filepath: str) -> bool:
        if not self._initialized or not os.path.exists(filepath):
            return False
        try:
            self._sound = self._pygame.mixer.Sound(filepath)
            self.current_track = filepath
            return True
        except:
            return False
    
    def play(self, loop: bool = True):
        if not self._initialized or not self._sound:
            return
        try:
            # BRATBOX_MUSIC_SINGLE_VOICE_V2: use the same reserved bed
            # channel as FileOST so separate music systems cannot layer.
            loops = -1 if loop else 0
            ch = self._pygame.mixer.Channel(0)
            ch.stop()
            self._channel = ch
            self._channel.play(self._sound, loops=loops)
            if self._channel:
                self._channel.set_volume(self.volume)
        except:
            pass
    
    def stop(self):
        try:
            # Stop bed channels used by the two OST systems; leave rhythm SFX
            # and voice channels alone.
            if self._initialized:
                self._pygame.mixer.Channel(0).stop()
                self._pygame.mixer.Channel(1).stop()
        except:
            pass
        if self._channel:
            try:
                self._channel.stop()
            except:
                pass
    
    def set_volume(self, volume: float):
        super().set_volume(volume)
        if self._channel:
            try:
                self._channel.set_volume(self.volume)
            except:
                pass
    
    def fade_to(self, volume: float, duration: float):
        def _fade():
            start_vol = self.volume
            target_vol = max(0.0, min(1.0, volume))
            steps = max(1, int(duration * 30))
            for i in range(steps):
                t = (i + 1) / steps
                new_vol = start_vol + (target_vol - start_vol) * t
                self.set_volume(new_vol)
                time.sleep(1/30)
        
        threading.Thread(target=_fade, daemon=True).start()
    
    def is_playing(self) -> bool:
        if self._channel:
            try:
                return self._channel.get_busy()
            except:
                pass
        return False
    
    def cleanup(self):
        if self._initialized:
            try:
                self._pygame.mixer.quit()
            except:
                pass


# ═══════════════════════════════════════════════════════════════════════════════
#                         RHYTHM SOUND ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class RhythmSoundEngine:
    """
    Plays rhythm game sounds - hits, misses, beats.
    
    Uses pygame mixer channels for quick, overlapping sounds.
    Falls back to silent if pygame unavailable.
    """
    
    def __init__(self):
        self._initialized = False
        self._pygame = None
        self._sounds: Dict[str, any] = {}
        self._channels: List[any] = []
        self._channel_idx = 0
        self.enabled = True
        self.volume = 0.7
        self.mix = 1.0  # additional global SFX mix multiplier
        self._beat_volume = 0.3  # Beat pulse quieter than hits
        
        self._init_pygame()
        if self._initialized:
            self._generate_sounds()
    
    def _init_pygame(self):
        """Initialize pygame mixer with multiple channels."""
        try:
            import pygame
            import pygame.mixer
            
            # Check if already initialized by MusicEngine
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=1, buffer=256)
            
            # Reserve channels for rhythm sounds
            pygame.mixer.set_num_channels(32)
            self._channels = [pygame.mixer.Channel(i) for i in range(8, 32)]
            
            self._pygame = pygame
            self._initialized = True
        except:
            pass
    
    def _generate_sounds(self):
        """Pre-generate all rhythm sounds."""
        if not self._initialized or not NUMPY_AVAILABLE:
            return
        
        # Hit sounds for each lane
        for lane in range(4):
            for quality in ['good', 'perfect', 'voice', 'squish', 'bleat']:
                key = f'hit_{lane}_{quality}'
                wave_bytes = generate_hit_sound(lane, quality)
                if wave_bytes:
                    try:
                        self._sounds[key] = self._pygame.mixer.Sound(buffer=wave_bytes)
                    except:
                        pass
        
        # Miss sound
        wave_bytes = generate_miss_sound()
        if wave_bytes:
            try:
                self._sounds['miss'] = self._pygame.mixer.Sound(buffer=wave_bytes)
            except:
                pass
        
        # Combo chimes
        for combo in [10, 25, 50, 100]:
            wave_bytes = generate_combo_chime(combo)
            if wave_bytes:
                try:
                    self._sounds[f'combo_{combo}'] = self._pygame.mixer.Sound(buffer=wave_bytes)
                except:
                    pass
        
        # Beat pulses at different intensities
        for intensity in [0.2, 0.5, 0.8]:
            wave_bytes = generate_beat_pulse(100, intensity)
            if wave_bytes:
                try:
                    self._sounds[f'beat_{int(intensity*10)}'] = self._pygame.mixer.Sound(buffer=wave_bytes)
                except:
                    pass
    
    def _get_channel(self):
        """Get next available channel (round-robin)."""
        if not self._channels:
            return None
        channel = self._channels[self._channel_idx]
        self._channel_idx = (self._channel_idx + 1) % len(self._channels)
        return channel
        def set_mix(self, mix: float):
            """Set additional SFX mix multiplier (0..1+)."""
            try:
                mix_f = float(mix)
            except Exception:
                mix_f = 1.0
            self.mix = max(0.0, min(1.5, mix_f))

    
    def play_hit(self, lane: int, quality: str = "good"):
        """Play a hit sound for the given lane."""
        if not self.enabled or not self._initialized:
            return
        
        key = f'hit_{lane}_{quality}'
        sound = self._sounds.get(key)
        if sound:
            channel = self._get_channel()
            if channel:
                sound.set_volume(self.volume * self.mix)
                channel.play(sound)
    
    def play_miss(self):
        """Play a miss sound."""
        if not self.enabled or not self._initialized:
            return
        
        sound = self._sounds.get('miss')
        if sound:
            channel = self._get_channel()
            if channel:
                sound.set_volume(self.volume * self.mix * 0.7)
                channel.play(sound)
    
    def play_combo_chime(self, combo: int):
        """Play combo milestone chime."""
        if not self.enabled or not self._initialized:
            return
        
        # Find closest milestone
        for milestone in [100, 50, 25, 10]:
            if combo >= milestone:
                sound = self._sounds.get(f'combo_{milestone}')
                if sound:
                    channel = self._get_channel()
                    if channel:
                        sound.set_volume(self.volume * self.mix)
                        channel.play(sound)
                break
    
    def play_beat(self, intensity: float = 0.5):
        """Play a beat pulse."""
        if not self.enabled or not self._initialized:
            return
        
        # Map intensity to sound
        if intensity > 0.6:
            key = 'beat_8'
        elif intensity > 0.3:
            key = 'beat_5'
        else:
            key = 'beat_2'
        
        sound = self._sounds.get(key)
        if sound:
            channel = self._get_channel()
            if channel:
                sound.set_volume(self._beat_volume)
                channel.play(sound)
    
    def set_volume(self, volume: float):
        """Set rhythm sound volume."""
        self.volume = max(0.0, min(1.0, volume))
    
    def set_beat_volume(self, volume: float):
        """Set beat pulse volume separately."""
        self._beat_volume = max(0.0, min(1.0, volume))


# ═══════════════════════════════════════════════════════════════════════════════
#                              MUSIC ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class MusicEngine:
    """
    Main music engine for OGRE SHADER.
    
    Usage:
        engine = MusicEngine()
        engine.set_game_state('menu')
        # ... during gameplay ...
        engine.set_tier(2)  # Frenzy
        # ... on climax ...
        engine.set_game_state('climax')
    """
    
    def __init__(self, music_dir: Optional[str] = None):
        self.music_dir = self._find_music_dir(music_dir)
        self.backend = self._init_backend()
        
        self.current_track: MusicTrack = MusicTrack.SILENCE
        self.enabled = True
        self.master_volume = 0.7
        self._muted = False
        self._pre_mute_volume = 0.7
        self.last_requested_track: str = ""
        self.last_expected_filename: str = ""
        self.last_resolved_path: str = ""
        self.last_file_exists: bool = False
        self.last_load_succeeded: bool = False
        self.last_playback_started: bool = False
        self.last_backend_name: str = type(self.backend).__name__
        self.last_error: str = ""
        self._watchdog_stop = False
        self._watchdog_thread = None
        self._start_watchdog()
        
        self._transitioning = False
        self.on_track_change: Optional[Callable[[MusicTrack], None]] = None
    
    def _find_music_dir(self, music_dir: Optional[str]) -> Optional[str]:
        if music_dir and os.path.isdir(music_dir):
            return music_dir
        
        root = _fiendish_asset_root()
        search_paths = [
            root / "music",
            root / "ost",
            Path(__file__).parent / "music",
            Path(__file__).parent / "ost",
            Path.home() / ".ogre_shader" / "music",
            Path("music"),
            Path("ost"),
        ]
        
        for path in search_paths:
            if path.exists() and path.is_dir():
                return str(path)
        
        return None
    
    def _init_backend(self) -> AudioBackend:
        backend = PygameBackend()
        if backend._initialized:
            return backend
        return SilentBackend()
    
    def _get_track_path(self, track: MusicTrack) -> Optional[str]:
        if not self.music_dir:
            return None
        
        info = TRACK_INFO.get(track)
        if not info or not info.filename:
            return None
        
        # Try original filename
        path = os.path.join(self.music_dir, info.filename)
        if os.path.exists(path):
            return path
        
        # Try alternative extensions
        base = os.path.splitext(info.filename)[0]
        for ext in ['.ogg', '.mp3', '.wav', '.flac']:
            alt_path = os.path.join(self.music_dir, base + ext)
            if os.path.exists(alt_path):
                return alt_path

        # Compatibility with canonical unnumbered Bratbox packs such as story.wav.
        alias_base = str(track.value or "").strip()
        if alias_base and alias_base != base:
            for ext in ['.ogg', '.mp3', '.wav', '.flac']:
                alt_path = os.path.join(self.music_dir, alias_base + ext)
                if os.path.exists(alt_path):
                    return alt_path
        
        return None
    
    def _fallback_track(self) -> MusicTrack:
        for candidate in (MusicTrack.RELEASE, MusicTrack.STORY, MusicTrack.AFTERCARE, MusicTrack.MENU):
            try:
                if candidate != self.current_track and self._get_track_path(candidate):
                    return candidate
            except Exception:
                pass
        return MusicTrack.MENU

    def _start_watchdog(self):
        try:
            if self._watchdog_thread is not None and self._watchdog_thread.is_alive():
                return
            self._watchdog_stop = False
            def _run():
                while not bool(getattr(self, "_watchdog_stop", False)):
                    try:
                        self.tick()
                    except Exception:
                        pass
                    time.sleep(0.35)
            self._watchdog_thread = threading.Thread(target=_run, name="BratboxMusicBedWatchdog", daemon=True)
            self._watchdog_thread.start()
        except Exception:
            pass

    def tick(self):
        """Keep a minimum music bed alive when one-shots/traps end or fail."""
        try:
            if not self.enabled or self._muted:
                return
            if self.current_track == MusicTrack.SILENCE:
                return
            if not self.backend.is_playing():
                fb = self._fallback_track()
                if fb != self.current_track or self.current_track == MusicTrack.SILENCE:
                    self._play_immediate(fb)
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════════════
    #                              PLAYBACK
    # ═══════════════════════════════════════════════════════════════════════════
    
    def play(self, track: MusicTrack, crossfade: bool = True):
        """Play a track."""
        if not self.enabled or self._muted:
            self.current_track = track
            return
        
        if track == self.current_track:
            return
        
        # Bratbox strict music bed: no crossfade layering.
        if (os.getenv("LOCKKEY_OST_STRICT_SINGLE", "1") or "1").strip().lower() not in ("0", "false", "no", "off"):
            self._play_immediate(track)
        elif crossfade and self.current_track != MusicTrack.SILENCE:
            self._crossfade_to(track)
        else:
            self._play_immediate(track)
    
    def _play_immediate(self, track: MusicTrack):
        self.backend.stop()
        info = TRACK_INFO.get(track)
        self.last_requested_track = str(track.value)
        self.last_expected_filename = str(info.filename if info else "")
        self.last_resolved_path = ""
        self.last_file_exists = False
        self.last_load_succeeded = False
        self.last_playback_started = False
        self.last_backend_name = type(self.backend).__name__
        self.last_error = ""
        
        if track == MusicTrack.SILENCE:
            self.current_track = track
            return
        
        path = self._get_track_path(track)
        self.last_resolved_path = str(path or "")
        self.last_file_exists = bool(path and os.path.exists(path))
        if path and self.backend.load(path):
            self.last_load_succeeded = True
            loop = info.loop if info else True
            self.backend.set_volume(self.master_volume)
            self.backend.play(loop=loop)
            self.last_playback_started = bool(
                self.backend.is_playing() and type(self.backend).__name__ != "SilentBackend"
            )
        else:
            if not path:
                self.last_error = f"missing track file for {track.value}"
            else:
                self.last_error = f"backend could not load {path}"
            # Minimum-bed fallback: never let a missing/failed trap clip into dead air.
            try:
                fb = self._fallback_track()
                fb_path = self._get_track_path(fb)
                if fb_path and self.backend.load(fb_path):
                    self.last_requested_track = f"{track.value} -> fallback:{fb.value}"
                    self.last_resolved_path = str(fb_path)
                    self.last_file_exists = True
                    self.last_load_succeeded = True
                    self.backend.set_volume(self.master_volume)
                    self.backend.play(loop=True)
                    self.last_playback_started = bool(self.backend.is_playing() and type(self.backend).__name__ != "SilentBackend")
                    track = fb
            except Exception as exc:
                self.last_error = f"{self.last_error}; fallback failed: {exc}"
        
        self.current_track = track if self.last_load_succeeded else MusicTrack.SILENCE
        
        if self.on_track_change:
            try:
                self.on_track_change(track)
            except:
                pass
    
    def _crossfade_to(self, track: MusicTrack):
        if self._transitioning:
            # If already transitioning, just switch
            self._play_immediate(track)
            return
        
        self._transitioning = True
        
        def _transition():
            try:
                old_info = TRACK_INFO.get(self.current_track)
                new_info = TRACK_INFO.get(track)
                
                fade_out = old_info.crossfade_out if old_info else 0.5
                fade_in = new_info.crossfade_in if new_info else 1.0
                
                # Fade out
                self.backend.fade_to(0.0, fade_out)
                time.sleep(fade_out)
                
                # Switch
                self._play_immediate(track)
                
                # Fade in
                self.backend.set_volume(0.0)
                self.backend.fade_to(self.master_volume, fade_in)
                time.sleep(fade_in)
            finally:
                self._transitioning = False
        
        threading.Thread(target=_transition, daemon=True).start()
    
    def stop(self):
        """Stop playback."""
        self.backend.stop()
        self.current_track = MusicTrack.SILENCE
    
    def set_volume(self, volume: float):
        """Set master volume (0.0 - 1.0)."""
        self.master_volume = max(0.0, min(1.0, volume))
        if not self._transitioning and not self._muted:
            self.backend.set_volume(self.master_volume)
    
    def mute(self):
        """Mute music."""
        if not self._muted:
            self._pre_mute_volume = self.backend.volume
            self.backend.set_volume(0.0)
            self._muted = True
    
    def unmute(self):
        """Unmute music."""
        if self._muted:
            self.backend.set_volume(self._pre_mute_volume)
            self._muted = False
    
    def toggle_mute(self) -> bool:
        """Toggle mute. Returns True if now muted."""
        if self._muted:
            self.unmute()
        else:
            self.mute()
        return self._muted
    
    # ═══════════════════════════════════════════════════════════════════════════
    #                              STATE-BASED CONTROL
    # ═══════════════════════════════════════════════════════════════════════════
    
    def set_game_state(self, state: str, **kwargs):
        """
        Set music based on game state.
        
        States: 'menu', 'story', 'play', 'climax', 'aftercare', 'pause', 'unpause'
        """
        if state == 'menu':
            self.play(MusicTrack.MENU)
        
        elif state == 'story':
            self.play(MusicTrack.STORY)
        
        elif state == 'play':
            tier = kwargs.get('tier', 0)
            mode = kwargs.get('mode', None)
            
            if mode == 'love_bunny':
                self.play(MusicTrack.LOVE_BUNNY)
            elif mode == 'edge':
                self.play(MusicTrack.EDGE)
            else:
                self.set_tier(tier)
        
        elif state == 'climax':
            self.play(MusicTrack.CLIMAX, crossfade=False)
        
        elif state == 'aftercare':
            self.play(MusicTrack.AFTERCARE)
        
        elif state == 'pause':
            self.backend.set_volume(self.master_volume * 0.3)
        
        elif state == 'unpause':
            if not self._muted:
                self.backend.set_volume(self.master_volume)
    
    def set_tier(self, tier: int):
        """Set music for gameplay tier (0-4)."""
        tier = max(0, min(4, tier))
        track = TIER_TRACKS.get(tier, MusicTrack.RELEASE)
        self.play(track)
    
    def play_achievement(self):
        """Play achievement sting (ducks current music)."""
        if self._muted:
            return
        
        def _sting():
            original_vol = self.backend.volume
            self.backend.fade_to(original_vol * 0.4, 0.2)
            time.sleep(1.5)
            self.backend.fade_to(original_vol, 0.5)
        
        threading.Thread(target=_sting, daemon=True).start()
    
    # ═══════════════════════════════════════════════════════════════════════════
    #                              STATUS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_status(self) -> dict:
        info = TRACK_INFO.get(self.current_track)
        return {
            'track': self.current_track.value,
            'track_name': info.name if info else 'Unknown',
            'bpm': info.bpm if info else 0,
            'playing': self.backend.is_playing(),
            'volume': self.backend.volume,
            'muted': self._muted,
            'enabled': self.enabled,
            'backend': type(self.backend).__name__,
            'has_files': self.music_dir is not None,
            'music_dir': self.music_dir,
            'requested_track': self.last_requested_track,
            'expected_filename': self.last_expected_filename,
            'resolved_path': self.last_resolved_path,
            'file_exists': self.last_file_exists,
            'load_succeeded': self.last_load_succeeded,
            'playback_started': self.last_playback_started,
            'backend_initialized': bool(getattr(self.backend, "_initialized", False)),
            'backend_silent': type(self.backend).__name__ == "SilentBackend",
            'last_error': self.last_error,
        }
    
    def get_track_name(self) -> str:
        info = TRACK_INFO.get(self.current_track)
        return info.name if info else ""
    
    def get_bpm(self) -> int:
        info = TRACK_INFO.get(self.current_track)
        return info.bpm if info else 0
    
    def cleanup(self):
        self._watchdog_stop = True
        self.stop()
        self.backend.cleanup()


# ═══════════════════════════════════════════════════════════════════════════════
#                              GLOBAL INSTANCES
# ═══════════════════════════════════════════════════════════════════════════════

_music_engine: Optional[MusicEngine] = None
_rhythm_engine: Optional[RhythmSoundEngine] = None


def get_music_engine() -> MusicEngine:
    """Get or create the global music engine."""
    global _music_engine
    if _music_engine is None:
        _music_engine = MusicEngine()
    return _music_engine


def get_rhythm_engine() -> RhythmSoundEngine:
    """Get or create the global rhythm sound engine."""
    global _rhythm_engine
    if _rhythm_engine is None:
        _rhythm_engine = RhythmSoundEngine()
    return _rhythm_engine


def init_music(music_dir: Optional[str] = None) -> MusicEngine:
    """Initialize the music system."""
    global _music_engine, _rhythm_engine
    _music_engine = MusicEngine(music_dir)
    _rhythm_engine = RhythmSoundEngine()
    return _music_engine


def cleanup_music():
    """Clean up music resources."""
    global _music_engine, _rhythm_engine
    if _music_engine:
        _music_engine.cleanup()
        _music_engine = None
    _rhythm_engine = None


# ═══════════════════════════════════════════════════════════════════════════════
#                         MUSIC CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def music_menu():
    get_music_engine().play(MusicTrack.MENU)

def music_story():
    get_music_engine().play(MusicTrack.STORY)

def music_tier(tier: int):
    eng = get_music_engine()
    eng.set_tier(tier)
    eng.tick()

def music_climax():
    eng = get_music_engine()
    eng.set_game_state('climax')
    eng.tick()

def music_aftercare():
    eng = get_music_engine()
    eng.set_game_state('aftercare')
    eng.tick()

def music_love_bunny():
    get_music_engine().play(MusicTrack.LOVE_BUNNY)

def music_edge():
    get_music_engine().play(MusicTrack.EDGE)

def music_stop():
    get_music_engine().stop()

def music_volume(vol: float):
    get_music_engine().set_volume(vol)

def music_toggle_mute() -> bool:
    return get_music_engine().toggle_mute()

def music_achievement():
    get_music_engine().play_achievement()


# ═══════════════════════════════════════════════════════════════════════════════
#                      RHYTHM SOUND CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════


def rhythm_set_mix(mix: float):
    """Set global rhythm SFX mix multiplier (affects hit/miss/beat)."""
    try:
        get_rhythm_engine().set_mix(mix)
    except Exception:
        pass

def rhythm_hit(lane: int, quality: str = "good"):
    """Play hit sound. lane: 0-3 (A,S,D,F), quality: 'good' or 'perfect'"""
    get_rhythm_engine().play_hit(lane, quality)

def rhythm_miss():
    """Play miss sound."""
    get_rhythm_engine().play_miss()

def rhythm_combo(combo: int):
    """Play combo milestone chime (10, 25, 50, 100)."""
    get_rhythm_engine().play_combo_chime(combo)

def rhythm_beat(intensity: float = 0.5):
    """Play beat pulse. intensity: 0.0-1.0"""
    get_rhythm_engine().play_beat(intensity)

def rhythm_volume(vol: float):
    """Set rhythm sound volume."""
    get_rhythm_engine().set_volume(vol)

def rhythm_beat_volume(vol: float):
    """Set beat pulse volume (separate from hit sounds)."""
    get_rhythm_engine().set_beat_volume(vol)

def rhythm_enable(enabled: bool = True):
    """Enable or disable rhythm sounds."""
    get_rhythm_engine().enabled = enabled


# ═══════════════════════════════════════════════════════════════════════════════
#                              TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("OGRE SHADER - Music Engine")
    print("=" * 50)
    
    engine = get_music_engine()
    status = engine.get_status()
    
    print(f"Backend: {status['backend']}")
    print(f"Music dir: {engine.music_dir}")
    print(f"Has files: {status['has_files']}")
    print()
    print("Commands: 0-4 (tier), m (menu), c (climax), a (aftercare)")
    print("          e (edge), +/- (volume), space (mute), q (quit)")
    print()
    
    engine.set_game_state('menu')
    
    try:
        while True:
            cmd = input("> ").strip().lower()
            
            if cmd == 'q':
                break
            elif cmd in '01234':
                engine.set_game_state('play', tier=int(cmd))
                info = TRACK_INFO[TIER_TRACKS[int(cmd)]]
                print(f"Tier {cmd}: {info.name} ({info.bpm} BPM)")
            elif cmd == 'm':
                engine.set_game_state('menu')
                print("Menu: Two Animals (60 BPM)")
            elif cmd == 'c':
                engine.set_game_state('climax')
                print("Climax: Everything (140 BPM)")
            elif cmd == 'a':
                engine.set_game_state('aftercare')
                print("Aftercare: Birdsong (55 BPM)")
            elif cmd == 'e':
                engine.play(MusicTrack.EDGE)
                print("Edge: Please (130 BPM)")
            elif cmd == '+':
                engine.set_volume(min(1.0, engine.master_volume + 0.1))
                print(f"Volume: {engine.master_volume:.0%}")
            elif cmd == '-':
                engine.set_volume(max(0.0, engine.master_volume - 0.1))
                print(f"Volume: {engine.master_volume:.0%}")
            elif cmd == '' or cmd == ' ':
                muted = engine.toggle_mute()
                print("Muted" if muted else "Unmuted")
            elif cmd == 'x':
                engine.play_achievement()
                print("*achievement*")
    
    except KeyboardInterrupt:
        pass
    
    engine.cleanup()
    print("\nDone!")
