#!/usr/bin/env python3
"""
OGRE SHADER - RHYTHM SOUND ENGINE
Procedural audio for rhythm hits, synced to gameplay

Generates sounds for:
- Lane hits (A/S/D/SPACE with different tones)
- Perfect vs Good hits
- Misses
- Combo milestones
- Beat pulse (metronome)
"""

import threading
import time
import math
from typing import Optional, Dict, List
from dataclasses import dataclass

# Audio backend
try:
    import pygame
    import pygame.mixer
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


SAMPLE_RATE = 44100


# ═══════════════════════════════════════════════════════════════════════════════
#                              WAVE GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

def generate_tone(freq: float, duration: float, volume: float = 0.3,
                  attack: float = 0.01, release: float = 0.05,
                  wave_type: str = 'sine') -> Optional[bytes]:
    """Generate a tone with envelope."""
    if not NUMPY_AVAILABLE:
        return None
    
    samples = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, samples, False)
    
    # Wave shape
    if wave_type == 'sine':
        wave = np.sin(2 * np.pi * freq * t)
    elif wave_type == 'square':
        wave = np.sign(np.sin(2 * np.pi * freq * t))
    elif wave_type == 'saw':
        wave = 2 * (t * freq - np.floor(0.5 + t * freq))
    elif wave_type == 'triangle':
        wave = 2 * np.abs(2 * (t * freq - np.floor(t * freq + 0.5))) - 1
    else:
        wave = np.sin(2 * np.pi * freq * t)
    
    # Envelope
    envelope = np.ones(samples)
    attack_samples = int(SAMPLE_RATE * attack)
    release_samples = int(SAMPLE_RATE * release)
    
    if attack_samples > 0 and attack_samples < samples:
        envelope[:attack_samples] = np.linspace(0, 1, attack_samples)
    if release_samples > 0 and release_samples < samples:
        envelope[-release_samples:] = np.linspace(1, 0, release_samples)
    
    wave = wave * envelope * volume
    wave = np.clip(wave, -1, 1)
    wave = (wave * 32767).astype(np.int16)
    
    return wave.tobytes()


def generate_noise_hit(duration: float = 0.05, volume: float = 0.2,
                       cutoff: float = 0.5) -> Optional[bytes]:
    """Generate filtered noise burst (for hi-hat like sounds)."""
    if not NUMPY_AVAILABLE:
        return None
    
    samples = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, samples, False)
    
    # White noise
    wave = np.random.uniform(-1, 1, samples)
    
    # Simple filter (moving average)
    filter_size = max(1, int(10 * (1 - cutoff)))
    if filter_size > 1:
        wave = np.convolve(wave, np.ones(filter_size)/filter_size, mode='same')
    
    # Quick decay envelope
    envelope = np.exp(-20 * t)
    
    wave = wave * envelope * volume
    wave = (wave * 32767).astype(np.int16)
    
    return wave.tobytes()


def generate_kick(duration: float = 0.1, volume: float = 0.4) -> Optional[bytes]:
    """Generate kick drum sound."""
    if not NUMPY_AVAILABLE:
        return None
    
    samples = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, samples, False)
    
    # Pitch drops from high to low
    freq = 150 * np.exp(-30 * t) + 40
    phase = np.cumsum(2 * np.pi * freq / SAMPLE_RATE)
    wave = np.sin(phase)
    
    # Quick decay
    envelope = np.exp(-15 * t)
    
    wave = wave * envelope * volume
    wave = (wave * 32767).astype(np.int16)
    
    return wave.tobytes()


def generate_arpeggio(base_freq: float, duration: float = 0.3, 
                      volume: float = 0.25) -> Optional[bytes]:
    """Generate quick ascending arpeggio."""
    if not NUMPY_AVAILABLE:
        return None
    
    # Three notes ascending
    freqs = [base_freq, base_freq * 1.25, base_freq * 1.5]  # Major triad-ish
    note_duration = duration / 3
    
    waves = []
    for freq in freqs:
        wave_bytes = generate_tone(freq, note_duration, volume, 0.005, 0.02, 'triangle')
        if wave_bytes:
            wave = np.frombuffer(wave_bytes, dtype=np.int16)
            waves.append(wave)
    
    if waves:
        combined = np.concatenate(waves)
        return combined.tobytes()
    return None


# ═══════════════════════════════════════════════════════════════════════════════
#                              SOUND CACHE
# ═══════════════════════════════════════════════════════════════════════════════

class RhythmSoundCache:
    """Pre-generates and caches rhythm sounds."""
    
    def __init__(self):
        self.sounds: Dict[str, 'pygame.mixer.Sound'] = {}
        self._initialized = False
    
    def init(self):
        """Initialize pygame and generate sounds."""
        if not PYGAME_AVAILABLE or not NUMPY_AVAILABLE:
            return False
        
        if self._initialized:
            return True
        
        try:
            # If mixer already initialized (e.g., OST), don't re-init (would kill music)
            try:
                if pygame.mixer.get_init():
                    try:
                        # Ensure enough channels for layering; keep channel 0 reserved for music
                        if pygame.mixer.get_num_channels() < 32:
                            pygame.mixer.set_num_channels(32)
                        try:
                            pygame.mixer.set_reserved(1)
                        except Exception:
                            pass
                    except Exception:
                        pass
                    self._initialized = True
                else:
                    pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2, buffer=512)
                    pygame.mixer.set_num_channels(32)
                    try:
                        pygame.mixer.set_reserved(1)
                    except Exception:
                        pass
                    self._initialized = True
            except Exception:
                # Fallback to original init parameters
                pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2, buffer=512)
                pygame.mixer.set_num_channels(32)
                try:
                    pygame.mixer.set_reserved(1)
                except Exception:
                    pass
                self._initialized = True
        except Exception as e:
            print(f"Audio init failed: {e}")
            return False
        
        # Generate lane hit sounds (different pitches per lane)
        # Musical notes that sound good together
        lane_freqs = {
            'A': 440,      # A4
            'S': 523.25,   # C5
            'D': 659.25,   # E5
            'SPACE': 349.23,  # F4 (bass note)
        }
        
        for lane, freq in lane_freqs.items():
            # Normal hit
            wave = generate_tone(freq, 0.08, 0.35, 0.005, 0.03, 'triangle')
            if wave:
                self.sounds[f'hit_{lane}'] = pygame.mixer.Sound(buffer=wave)
            
            # Perfect hit (higher octave, brighter)
            wave = generate_tone(freq * 2, 0.1, 0.4, 0.005, 0.04, 'sine')
            if wave:
                self.sounds[f'perfect_{lane}'] = pygame.mixer.Sound(buffer=wave)
        
        # Miss sound (low thud)
        wave = generate_tone(80, 0.15, 0.3, 0.01, 0.1, 'sine')
        if wave:
            self.sounds['miss'] = pygame.mixer.Sound(buffer=wave)
        
        # Beat pulse (subtle metronome)
        wave = generate_tone(880, 0.03, 0.15, 0.002, 0.02, 'sine')
        if wave:
            self.sounds['beat'] = pygame.mixer.Sound(buffer=wave)
        
        # Downbeat (stronger, lower)
        wave = generate_tone(440, 0.05, 0.2, 0.002, 0.03, 'triangle')
        if wave:
            self.sounds['downbeat'] = pygame.mixer.Sound(buffer=wave)
        
        # Combo milestones
        wave = generate_arpeggio(523.25, 0.2, 0.3)  # C5 arpeggio
        if wave:
            self.sounds['combo_10'] = pygame.mixer.Sound(buffer=wave)
        
        wave = generate_arpeggio(659.25, 0.25, 0.35)  # E5 arpeggio
        if wave:
            self.sounds['combo_25'] = pygame.mixer.Sound(buffer=wave)
        
        wave = generate_arpeggio(783.99, 0.3, 0.4)  # G5 arpeggio
        if wave:
            self.sounds['combo_50'] = pygame.mixer.Sound(buffer=wave)
        
        wave = generate_arpeggio(880, 0.35, 0.45)  # A5 arpeggio
        if wave:
            self.sounds['combo_100'] = pygame.mixer.Sound(buffer=wave)
        
        # Slip/fail sound
        wave = generate_tone(110, 0.2, 0.35, 0.01, 0.15, 'saw')
        if wave:
            self.sounds['slip'] = pygame.mixer.Sound(buffer=wave)
        
        # Tier up fanfare
        wave = generate_arpeggio(440, 0.4, 0.4)
        if wave:
            self.sounds['tier_up'] = pygame.mixer.Sound(buffer=wave)
        
        return True
    
    def play(self, sound_name: str, volume: float = 1.0):
        """Play a cached sound."""
        if not self._initialized:
            return
        
        sound = self.sounds.get(sound_name)
        if sound:
            sound.set_volume(volume)
            sound.play()
    
    def cleanup(self):
        """Clean up audio resources."""
        if self._initialized:
            try:
                pygame.mixer.quit()
            except:
                pass
            self._initialized = False


# ═══════════════════════════════════════════════════════════════════════════════
#                              RHYTHM SOUND ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class RhythmSoundEngine:
    """
    Manages rhythm sounds during gameplay.
    
    Features:
    - Hit sounds per lane
    - Perfect vs good distinction
    - Beat pulse (optional metronome)
    - Combo milestone sounds
    - Miss/slip sounds
    """
    
    def __init__(self):
        self.cache = RhythmSoundCache()
        self.enabled = True
        self.master_volume = 0.7
        self.beat_volume = 0.3  # Metronome volume (subtle)
        self.hit_volume = 0.8
        
        # Beat tracking
        self.beat_enabled = True
        self.last_beat = 0
        self.beat_count = 0
        
        # State
        self._initialized = False
    
    def init(self) -> bool:
        """Initialize the sound engine."""
        if self.cache.init():
            self._initialized = True
            return True
        return False
    
    def set_enabled(self, enabled: bool):
        """Enable/disable sounds."""
        self.enabled = enabled
    
    def set_volume(self, volume: float):
        """Set master volume (0.0 - 1.0)."""
        self.master_volume = max(0.0, min(1.0, volume))
    
    def set_beat_volume(self, volume: float):
        """Set beat/metronome volume."""
        self.beat_volume = max(0.0, min(1.0, volume))
    
    def set_beat_enabled(self, enabled: bool):
        """Enable/disable beat pulse."""
        self.beat_enabled = enabled
    
    # ═══════════════════════════════════════════════════════════════════════════
    #                              HIT SOUNDS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def play_hit(self, lane: str, quality: str = 'good'):
        """
        Play hit sound for a lane.
        
        Args:
            lane: 'A', 'S', 'D', or 'SPACE'
            quality: 'perfect' or 'good'
        """
        if not self.enabled or not self._initialized:
            return
        
        lane_upper = lane.upper()
        if quality == 'perfect':
            sound_name = f'perfect_{lane_upper}'
        else:
            sound_name = f'hit_{lane_upper}'
        
        self.cache.play(sound_name, self.master_volume * self.hit_volume)
    
    def play_miss(self):
        """Play miss sound."""
        if not self.enabled or not self._initialized:
            return
        self.cache.play('miss', self.master_volume * 0.5)
    
    def play_slip(self):
        """Play slip/fail sound."""
        if not self.enabled or not self._initialized:
            return
        self.cache.play('slip', self.master_volume * 0.6)
    
    # ═══════════════════════════════════════════════════════════════════════════
    #                              BEAT PULSE
    # ═══════════════════════════════════════════════════════════════════════════
    
    def tick_beat(self, bpm: float, current_time: float):
        """
        Call this each frame to trigger beat sounds.
        
        Args:
            bpm: Current beats per minute
            current_time: Current time in seconds
        """
        if not self.enabled or not self._initialized or not self.beat_enabled:
            return
        
        beat_interval = 60.0 / bpm
        
        # Check if we crossed a beat boundary
        current_beat = int(current_time / beat_interval)
        
        if current_beat > self.last_beat:
            self.last_beat = current_beat
            self.beat_count += 1
            
            # Downbeat every 4 beats
            if self.beat_count % 4 == 0:
                self.cache.play('downbeat', self.master_volume * self.beat_volume)
            else:
                self.cache.play('beat', self.master_volume * self.beat_volume * 0.5)
    
    def reset_beat(self):
        """Reset beat tracking (call when starting new section)."""
        self.last_beat = 0
        self.beat_count = 0
    
    # ═══════════════════════════════════════════════════════════════════════════
    #                              COMBO SOUNDS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def play_combo_milestone(self, combo: int):
        """Play combo milestone sound."""
        if not self.enabled or not self._initialized:
            return
        
        if combo == 10:
            self.cache.play('combo_10', self.master_volume * 0.6)
        elif combo == 25:
            self.cache.play('combo_25', self.master_volume * 0.7)
        elif combo == 50:
            self.cache.play('combo_50', self.master_volume * 0.8)
        elif combo >= 100:
            self.cache.play('combo_100', self.master_volume * 0.9)
    
    def play_tier_up(self):
        """Play tier escalation sound."""
        if not self.enabled or not self._initialized:
            return
        self.cache.play('tier_up', self.master_volume * 0.8)
    
    # ═══════════════════════════════════════════════════════════════════════════
    #                              CLEANUP
    # ═══════════════════════════════════════════════════════════════════════════
    
    def cleanup(self):
        """Clean up resources."""
        self.cache.cleanup()
        self._initialized = False


# ═══════════════════════════════════════════════════════════════════════════════
#                              GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

_rhythm_sounds: Optional[RhythmSoundEngine] = None


def get_rhythm_sounds() -> RhythmSoundEngine:
    """Get or create the global rhythm sound engine."""
    global _rhythm_sounds
    if _rhythm_sounds is None:
        _rhythm_sounds = RhythmSoundEngine()
        _rhythm_sounds.init()
    return _rhythm_sounds


def init_rhythm_sounds() -> RhythmSoundEngine:
    """Initialize the rhythm sound system."""
    global _rhythm_sounds
    _rhythm_sounds = RhythmSoundEngine()
    _rhythm_sounds.init()
    return _rhythm_sounds


def cleanup_rhythm_sounds():
    """Clean up rhythm sound resources."""
    global _rhythm_sounds
    if _rhythm_sounds:
        _rhythm_sounds.cleanup()
        _rhythm_sounds = None


# ═══════════════════════════════════════════════════════════════════════════════
#                              CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def rhythm_hit(lane: str, quality: str = 'good'):
    """Play a hit sound."""
    get_rhythm_sounds().play_hit(lane, quality)

def rhythm_miss():
    """Play miss sound."""
    get_rhythm_sounds().play_miss()

def rhythm_slip():
    """Play slip sound."""
    get_rhythm_sounds().play_slip()

def rhythm_beat(bpm: float, current_time: float):
    """Tick the beat pulse."""
    get_rhythm_sounds().tick_beat(bpm, current_time)

def rhythm_combo(combo: int):
    """Play combo milestone."""
    get_rhythm_sounds().play_combo_milestone(combo)

def rhythm_tier_up():
    """Play tier up sound."""
    get_rhythm_sounds().play_tier_up()

def rhythm_volume(volume: float):
    """Set rhythm sound volume."""
    get_rhythm_sounds().set_volume(volume)

def rhythm_beat_enabled(enabled: bool):
    """Enable/disable beat pulse."""
    get_rhythm_sounds().set_beat_enabled(enabled)


# ═══════════════════════════════════════════════════════════════════════════════
#                              TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("OGRE SHADER - Rhythm Sound Engine Test")
    print("=" * 50)
    
    if not PYGAME_AVAILABLE:
        print("pygame not available - install with: pip install pygame")
        exit(1)
    
    if not NUMPY_AVAILABLE:
        print("numpy not available - install with: pip install numpy")
        exit(1)
    
    engine = get_rhythm_sounds()
    
    if not engine._initialized:
        print("Failed to initialize audio")
        exit(1)
    
    print("Audio initialized!")
    print()
    print("Testing sounds...")
    print()
    
    # Test lane hits
    print("Lane hits (A, S, D, SPACE):")
    for lane in ['A', 'S', 'D', 'SPACE']:
        print(f"  {lane}...", end=" ", flush=True)
        rhythm_hit(lane, 'good')
        time.sleep(0.3)
        print("perfect...", end=" ", flush=True)
        rhythm_hit(lane, 'perfect')
        time.sleep(0.3)
        print("✓")
    
    print()
    print("Miss and slip:")
    rhythm_miss()
    time.sleep(0.3)
    rhythm_slip()
    time.sleep(0.5)
    print("✓")
    
    print()
    print("Combo milestones (10, 25, 50, 100):")
    for combo in [10, 25, 50, 100]:
        print(f"  {combo}...", end=" ", flush=True)
        rhythm_combo(combo)
        time.sleep(0.5)
        print("✓")
    
    print()
    print("Tier up:")
    rhythm_tier_up()
    time.sleep(0.5)
    print("✓")
    
    print()
    print("Beat pulse test (120 BPM for 4 seconds):")
    engine.reset_beat()
    start = time.time()
    while time.time() - start < 4.0:
        rhythm_beat(120, time.time() - start)
        time.sleep(0.01)
    print("✓")
    
    print()
    print("All tests complete!")
    
    engine.cleanup()
