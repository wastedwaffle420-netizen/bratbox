"""Bus-isolated authored audio for Ogre Shader and Idle/Rogue Fantasy."""
from __future__ import annotations

import os
import random
import time
from pathlib import Path

SOUNDSCAPE_PROFILES = ("full", "rhythm", "silent")

# One ownership table for every path touched by this subsystem.  Voice remains
# owned by voice_engine on 12-15; music remains on 0-1.
CHANNELS = {
    "anatomy_bed": 22,
    "intimacy_bed": 23,
    "bathroom": (24, 25, 26, 27),
    "musk": (28, 29),
    "ogress_asmr": (28, 29),
    "overflow": (30, 31),
}

_EVENTS = {
    "perfect_connection": ("newsounds_source/NEWSOUNDS/A_precise_soft_wet_c_*.wav", .34, .075, "punctuation"),
    "gentle_slick": ("newsounds_source/NEWSOUNDS/Close-mic_intimate_w_*.wav", .28, .10, "intimacy"),
    "deep_slick": ("newsounds_source/NEWSOUNDS/Close-mic,_deep,_wet_*.wav", .30, .12, "intimacy"),
    "auto_override": ("newsounds_source/NEWSOUNDS/Sudden_forceful_wet__*.wav", .38, .16, "punctuation"),
    "surge_purple": ("newsounds_source/NEWSOUNDS/Three_escalating_clo_*.wav", .40, .30, "punctuation"),
    "surge_red": ("newsounds_source/NEWSOUNDS/Surge—redspank_*.wav", .42, .28, "punctuation"),
    "surge_green": ("newsounds_source/NEWSOUNDS/Surge—greenpull_*.wav", .38, .28, "punctuation"),
    "spank": ("newsounds_source/NEWSOUNDS/One_warm_bare-hand_s_*.wav", .42, .22, "punctuation"),
    "climax_buildup": ("newsounds_source/NEWSOUNDS/Male_climax_buildup__*.wav", .42, .80, "punctuation"),
    "climax_release": ("newsounds_source/NEWSOUNDS/Male_climax_release__*.wav", .46, 1.0, "punctuation"),
    "maw_latch": ("newsounds_source/NEWSOUNDS/Elastic_Grotesque_ma_*.wav", .34, .35, "punctuation"),
    "maw_suckle": ("newsounds_source/NEWSOUNDS/Elastic_Grotesque_rh_*.wav", .31, .22, "anatomy"),
    "maw_final": ("newsounds_source/NEWSOUNDS/Elastic_Grotesque_fi_*.wav", .40, .60, "punctuation"),
    "maw_pop": ("newsounds_source/NEWSOUNDS/Maw_loses_seal_*.wav", .35, .45, "punctuation"),
    "settle": ("newsounds_source/NEWSOUNDS/Post-climax_settling_*.wav", .28, .65, "punctuation"),
    "urine_hana": ("bare/long_stream,_female__*.mp3", .25, .90, "bathroom"),
    "urine_male": ("bare/No_speech,_no_words,_*.mp3", .24, .90, "bathroom"),
    "bowl_hana": ("bare/3._Gooey_melting_sli_*.mp3", .16, .55, "bathroom"),
    "bowl_male": ("bare/4._Gross_weighted_ba_*.mp3", .18, .55, "bathroom"),
    "friction_hana": ("bare/3._Gooey_melting_sli_*.mp3", .16, 1.80, "bathroom"),
    # Deliberately no male friction/footstep-cadence take. Suckle carries this
    # portion until a genuinely non-repetitive contact bed is authored.
    "crackle_hana": ("bare/No_speech,_no_words,_*.mp3", .12, 2.40, "bathroom"),
    "crackle_male": ("bare/No_speech,_no_words,_*.mp3", .14, 2.10, "bathroom"),
    "strain_hana": ("bare/1._Deep_sudden_stoma_*.mp3", .14, 2.75, "bathroom"),
    "strain_male": ("bare/1._Deep_sudden_stoma_*.mp3", .16, 2.50, "bathroom"),
    "deposit_hana": ("bare/3._Gooey_melting_sli_*.mp3", .21, .85, "bathroom"),
    "deposit_male": ("bare/4._Gross_weighted_ba_*.mp3", .23, .85, "bathroom"),
    "ogress_stomach": ("bare/1._Deep_sudden_stoma_*.mp3", .13, 8.0, "ogress_asmr"),
    "ogress_burp": ("bare/1._Close-mic_gross_b_*.mp3", .11, 14.0, "ogress_asmr"),
    "ogress_domestic": ("bare/3._Gooey_melting_sli_*.mp3", .10, 7.0, "ogress_asmr"),
}

_CURATED = {
    "gentle_slick": (
        "Close-mic_intimate_w_#2-1785525404376.wav",
        "Close-mic_intimate_w_#3-1785525244749.wav",
    ),
    "deep_slick": (
        "Close-mic,_deep,_wet_#3-1785525379008.wav",
        "Close-mic,_deep,_wet_#1-1785525347862.wav",
        "Close-mic,_deep,_wet_#3-1785525355790.wav",
        "Close-mic,_deep,_wet_#2-1785525355788.wav",
    ),
    "maw_suckle": (
        "Elastic_Grotesque_rh_#3-1785525902920.wav",
        "Elastic_Grotesque_rh_#1-1785525902919.wav",
    ),
}

_files = {}
_sounds = {}
_last = {}
_lane_cursor = {"bathroom": 0, "musk": 0, "overflow": 0, "punctuation": 0}
_intimacy_channel = None
_suckle_channel = None
_intimacy_gain = 0.0
_suckle_gain = 0.0
_physical_audio_arc = 0.0
_session_token = ""
_MASTER_GAIN = .52
_ogress_next_at = 0.0


def profile() -> str:
    value = str(os.getenv("LOCKKEY_SOUNDSCAPE_PROFILE", os.getenv("LOCKKEY_IDLE_AUDIO_MODE", "rhythm")) or "rhythm").strip().lower()
    legacy = {"voices_rhythm": "rhythm", "rhythm_only": "rhythm"}
    value = legacy.get(value, value)
    return value if value in SOUNDSCAPE_PROFILES else "rhythm"


def mode() -> str:  # legacy callers
    return profile()


def rhythm_enabled() -> bool:
    return profile() in ("full", "rhythm")


def voices_enabled() -> bool:
    return str(os.getenv("LOCKKEY_VOICES_ENABLED", os.getenv("LOCKKEY_VOICE_ENABLED", "1")) or "1").lower() in ("1", "true", "yes", "on")


def foley_enabled() -> bool:
    return profile() == "full"


def musk_enabled() -> bool:
    return str(os.getenv("LOCKKEY_MUSK_ENABLED", os.getenv("ONRYO_TACTILE_MUSK", "1")) or "1").lower() in ("1", "true", "yes", "on")


def ogress_creature_asmr_enabled() -> bool:
    return str(os.getenv("LOCKKEY_OGRESS_CREATURE_ASMR", "0") or "0").lower() in ("1", "true", "yes", "on")


def _root() -> Path:
    return Path(__file__).resolve().parent / "assets" / "audio" / "idle_flagship"


def _ensure_mixer():
    import pygame
    if not pygame.mixer.get_init():
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
    if pygame.mixer.get_num_channels() < 32:
        pygame.mixer.set_num_channels(32)
    return pygame


def _choose_sound(event: str):
    try:
        pygame = _ensure_mixer()
        pattern = _EVENTS[event][0]
        candidates = _files.get(event)
        if candidates is None:
            curated = _CURATED.get(event, ())
            candidates = [_root() / "newsounds_source" / "NEWSOUNDS" / name for name in curated]
            candidates = [p for p in candidates if p.is_file()] or sorted(_root().glob(pattern))
            _files[event] = candidates
        if not candidates:
            return None
        previous = _last.get(event + ":file")
        pool = [p for p in candidates if str(p) != previous] or candidates
        path = random.choice(pool)
        sound = _sounds.get(str(path))
        if sound is None:
            sound = pygame.mixer.Sound(str(path))
            _sounds[str(path)] = sound
        _last[event + ":file"] = str(path)
        return sound
    except Exception:
        return None


def _owned_channel(family: str):
    pygame = _ensure_mixer()
    if family == "punctuation":
        # Explicit overflow only; never steal voice, rhythm, or continuous beds.
        owned = CHANNELS["overflow"]
    else:
        owned = CHANNELS.get(family, CHANNELS["overflow"])
    if isinstance(owned, int):
        return pygame.mixer.Channel(owned)
    cursor = _lane_cursor.get(family, 0)
    for offset in range(len(owned)):
        idx = owned[(cursor + offset) % len(owned)]
        channel = pygame.mixer.Channel(idx)
        if not channel.get_busy():
            _lane_cursor[family] = (cursor + offset + 1) % len(owned)
            return channel
    return None


def begin_session(token: str = "") -> None:
    global _physical_audio_arc, _session_token
    stop_intimacy(80)
    _physical_audio_arc = 0.0
    _session_token = str(token or time.perf_counter())


def note_surge(kind: str, quality: float = 1.0) -> float:
    """Advance runtime-only physical intensity for this Ogre Shader session."""
    global _physical_audio_arc
    gain = {"purple": .13, "red": .16, "green": .19}.get(str(kind or "").lower(), .08)
    _physical_audio_arc = max(0.0, min(1.0, _physical_audio_arc + gain * max(.25, min(1.25, float(quality or 1.0)))))
    return _physical_audio_arc


def play(event: str, intensity: float = 1.0) -> bool:
    """Play one Build-24-style authored event on an explicitly owned lane."""
    if event not in _EVENTS:
        return False
    pattern, gain, cooldown, family = _EVENTS[event]
    if family in ("intimacy", "anatomy") and not foley_enabled():
        return False
    if family == "bathroom" and profile() == "silent":
        return False
    if family == "musk" and (not musk_enabled() or profile() == "silent"):
        return False
    if family == "ogress_asmr" and (not ogress_creature_asmr_enabled() or profile() == "silent"):
        return False
    if family == "punctuation" and profile() == "silent":
        return False
    now = time.perf_counter()
    if now - _last.get(event, -999.0) < cooldown:
        return False
    sound = _choose_sound(event)
    if sound is None:
        return False
    try:
        channel = _owned_channel(family)
        if channel is None:
            return False
        channel.set_volume(max(.02, min(.34, _MASTER_GAIN * gain * max(.20, float(intensity or 1.0)))))
        channel.play(sound)
        _last[event] = now
        return True
    except Exception:
        return False


def update_ogress_creature(*, inserted: bool, intensity: float, motion: float, climax: bool = False) -> bool:
    """Sparse opt-in chieftess texture; independent of every authored profile."""
    global _ogress_next_at
    if not ogress_creature_asmr_enabled() or profile() == "silent":
        return False
    now = time.perf_counter()
    if _ogress_next_at <= 0.0:
        _ogress_next_at = now + random.uniform(6.0, 12.0)
        return False
    if now < _ogress_next_at:
        return False
    heat = max(0.0, min(1.0, .65 * float(intensity or 0.0) + .35 * float(motion or 0.0)))
    roll = random.random()
    if climax and roll < .42:
        event = "ogress_burp"
    elif inserted and roll < .55 + .18 * heat:
        event = "ogress_domestic"
    elif roll < .86:
        event = "ogress_stomach"
    else:
        event = "ogress_burp"
    played = play(event, .55 + .35 * heat)
    _ogress_next_at = now + random.uniform(10.0, 22.0) * (1.0 - .18 * heat)
    return played


def update_intimacy(*, inserted: bool, inside: bool, motion: float, intensity: float,
                    misses: int = 0, surge: str = "", surge_active: bool = False,
                    suckle_tier: int = 0, depth: float = 0.0,
                    movement_paused: bool = False) -> bool:
    """Maintain soft contact/anatomy beds without note-by-note retriggering."""
    global _intimacy_channel, _suckle_channel, _intimacy_gain, _suckle_gain
    if not foley_enabled() or not inserted or not inside:
        stop_intimacy(180)
        return False
    try:
        pygame = _ensure_mixer()
        if _intimacy_channel is not None and _intimacy_channel.get_busy():
            _intimacy_channel.fadeout(180)
        surge_kind = str(surge or "").lower() if surge_active else ""
        energy = max(0.0, min(1.0, .34 * float(intensity or 0.0) + .24 * float(motion or 0.0)
                              + .16 * float(depth or 0.0) + .38 * _physical_audio_arc))
        # The experimental close-mic contact bed read as footsteps. Leave this
        # lane intentionally blank; Build-24 surge punctuation and the authored
        # suckle lane still carry physical escalation.
        _intimacy_gain = 0.0
        tier = max(0, min(3, int(suckle_tier or 0)))
        if tier > 0:
            if _suckle_channel is None:
                _suckle_channel = pygame.mixer.Channel(CHANNELS["anatomy_bed"])
            if not _suckle_channel.get_busy():
                sound = _choose_sound("maw_suckle")
                if sound is not None:
                    _suckle_channel.play(sound)
            target_suckle = (.025 if movement_paused else .045 + .025 * tier + .045 * _physical_audio_arc) * _MASTER_GAIN
            _suckle_gain += (target_suckle - _suckle_gain) * .06
            _suckle_channel.set_volume(max(.015, min(.105, _suckle_gain)))
        elif _suckle_channel is not None and _suckle_channel.get_busy():
            _suckle_channel.fadeout(180)
        return True
    except Exception:
        return False


def stop_intimacy(fade_ms: int = 180) -> None:
    global _intimacy_gain, _suckle_gain
    try:
        for channel in (_intimacy_channel, _suckle_channel):
            if channel is not None and channel.get_busy():
                channel.fadeout(max(0, int(fade_ms)))
    except Exception:
        pass
    _intimacy_gain = 0.0
    _suckle_gain = 0.0


def recover_performance(fade_ms: int = 90) -> None:
    """Clear only Idle-owned physical lanes after a recovered false terminal."""
    global _physical_audio_arc
    try:
        pygame=_ensure_mixer()
        for idx in CHANNELS["overflow"]:
            channel=pygame.mixer.Channel(idx)
            if channel.get_busy():
                channel.fadeout(max(0,int(fade_ms)))
    except Exception:
        pass
    stop_intimacy(fade_ms)
    _physical_audio_arc=0.0


def end_session(fade_ms: int = 220) -> None:
    global _physical_audio_arc, _session_token
    stop_intimacy(fade_ms)
    _physical_audio_arc = 0.0
    _session_token = ""
