
from __future__ import annotations
import os, random
from pathlib import Path

_music_started = False

def _root():
    return Path(__file__).resolve().parent

def init_audio():
    global _music_started
    try:
        import pygame
        if not pygame.get_init():
            pygame.init()
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        if pygame.mixer.get_num_channels() < 24:
            pygame.mixer.set_num_channels(24)
        return True
    except Exception as exc:
        try:
            (_root()/"runs/current/audio_error.log").parent.mkdir(parents=True, exist_ok=True)
            (_root()/"runs/current/audio_error.log").write_text(repr(exc), encoding="utf-8")
        except Exception:
            pass
        return False

def start_music():
    global _music_started
    if _music_started:
        return True
    if not init_audio():
        return False
    try:
        import pygame
        candidates = []
        for base in (_root()/"music", _root()/"ost_pack_magnum_opus"):
            if base.exists():
                candidates.extend(sorted(base.rglob("*.wav")))
                candidates.extend(sorted(base.rglob("*.ogg")))
        if not candidates:
            return False
        # Prefer the recovered Bratbox release/build/frenzy beds.
        pref = [p for p in candidates if p.name.lower() in ("release.wav","build.wav","frenzy.wav","loop.wav")]
        chosen = pref[0] if pref else candidates[0]
        pygame.mixer.music.load(str(chosen))
        pygame.mixer.music.set_volume(0.34)
        pygame.mixer.music.play(-1)
        _music_started = True
        return True
    except Exception as exc:
        try:
            (_root()/"runs/current/audio_error.log").write_text(repr(exc), encoding="utf-8")
        except Exception:
            pass
        return False
