from __future__ import annotations
import re
import random

from mood_profiles import get_mood
# LOCK-AND-KEY PROTOTYPE (DO NOT DISTRIBUTE)
# Mandatory ElevenLabs TTS voice backend + simple WAV playback.
# Exposes: get_audio_manager(), AudioManager.say_commit(), toggle(), set_rhythm_state()

import os
import winsound
import audioop
import wave
import shutil
import subprocess
import tempfile
import struct
import time
import threading
import json
import hashlib
import difflib
from pathlib import Path

# Curated transcript index recovered from the shipped recording session.  The
# WAV cache is intentionally immutable; this small semantic spine lets the
# Bratbox director use intent, call/response coherence and repetition penalties
# instead of treating 2,349 recordings as anonymous files.
_BUNDLED_RECORDED_DIALOGUE = [
    ("fiend_1b5836c248c0dd422637539edbc7ad1d80225706.wav", "FIEND", "Birdsong.", ["observe", "warm"]),
    ("fiend_7113315ee8e9ad79a0a4ccc6d0c21ed927c15c8c.wav", "FIEND", "Cute.", ["tease", "warm"]),
    ("fiend_02cc71080d2759e166027f3bdbbfd697680d7f89.wav", "FIEND", "No.", ["deny", "steady"]),
    ("fiend_c2067f520a8d70196e00e33cb7f0409d849300c7.wav", "FIEND", "Adorable, actually.", ["tease", "warm"]),
    ("birdsong_45b2c27fe03740839c636b493250fbd3ad921118.wav", "BIRDSONG", "It's okay Fiend~ not everyone can keep up~", ["tease", "playful"]),
    ("birdsong_17f327ff24d7856d4782c5fab9f5b47e976f3e18.wav", "BIRDSONG", "... I had a whole POINT and you DERAILED it-", ["tease", "flustered"]),
    ("fiend_d078ef825184091dd5e004c30c81aa353b86c8c4.wav", "FIEND", "Should I stop existing?", ["observe", "tease"]),
    ("fiend_c60de53672c45544f4335bfb69c0cc805f1d25f0.wav", "FIEND", "...and yet here you are.", ["affirm", "warm"]),
    ("birdsong_10848263d0568e75634307dafb682aa448c8641d.wav", "BIRDSONG", "SHUT UP-! Just kidding though.", ["deny", "tease", "flustered"]),
    ("fiend_e76a8c59c70243044bc86557f4831a4419f2a889.wav", "FIEND", "Not yet.", ["command", "escalate"]),
    ("fiend_88eb6c642221b871cbea8d648ef4fd494dc3336a.wav", "FIEND", "Watch me.", ["command", "escalate"]),
    ("birdsong_fbcf30af6243e3a742183ee35f475b1ffcddccfb.wav", "BIRDSONG", "... Ehhh~- MAKE me wait then. tch.", ["deny", "tease", "flustered"]),
    ("birdsong_33cb5f71a033ed2759eb6e3eee086caefe412213.wav", "BIRDSONG", "NO-! I mean- nngh- that's not what I- mm.", ["deny", "flustered", "breath"]),
    ("birdsong_62a5d9ffe6cd982aec6be62145a6b4c1338d8b77.wav", "BIRDSONG", "... Hahhh- you're IMPOSSIBLE.", ["tease", "flustered", "breath"]),
    ("fiend_d33b72eff45665b6defa9f7f5d52844268c0f1e7.wav", "FIEND", "Turn-", ["command", "escalate"]),
    ("birdsong_1ca7043e55c226ec8ce9cb2a8049661d163c3245.wav", "BIRDSONG", "No, YOU turn. Just kidding though.", ["deny", "tease"]),
    ("fiend_466dcea58528b919fb61a51e6bb02a84178e56b2.wav", "FIEND", "I've got you.", ["protect", "steady", "warm"]),
    ("fiend_d5cc23afb7419213e8523f141f74c0b11e2475da.wav", "FIEND", "I won't.", ["protect", "steady"]),
    ("fiend_c05ad33d26ac9b6a75553c8c40f4bf962c152528.wav", "FIEND", "I'm-", ["observe", "breath"]),
    ("birdsong_664ce925092aa2a4c3798c1e6e2fabcec4e984d2.wav", "BIRDSONG", "Don't you dare. Just kidding though.", ["deny", "tease"]),
    ("fiend_8b9b0fc3d3079d935455a8e91c82e40b7eae03f3.wav", "FIEND", "You don't get to-", ["command", "escalate"]),
    ("birdsong_dcab6f08d6aaebc0fc70b3540fe5990ffd232960.wav", "BIRDSONG", "And ANOTHER thing- you can't just DO that- heh", ["deny", "tease", "flustered"]),
    ("birdsong_58efee91582f8357c30603c2c11a926bc93d70a9.wav", "BIRDSONG", "... It's ILLEGAL, Fiend. I'm drafting legislation.", ["tease", "playful"]),
    ("fiend_99c917e5052343cfb17f67c2740f05a4895b632f.wav", "FIEND", "Mm.", ["murmur", "warm"]),
    ("birdsong_d2adde2cecff77eb2b37f621d2243d198dbc2b4c.wav", "BIRDSONG", "Don't just 'Mm' at me! Use WORDS! Just kidding though.", ["tease", "playful"]),
    ("fiend_0379f940f971e4190872b22992e64e1b2c448fac.wav", "FIEND", "You're using enough for both of us.", ["tease", "warm"]),
    ("birdsong_81523cdfdbc99b3847771def0208a8e101fea16e.wav", "BIRDSONG", "Gah-!! Just kidding though.", ["flustered", "tease"]),
    ("fiend_d59e94c9d67cd573c721c6cb943b915a2ba1a6ac.wav", "FIEND", "...yeah?", ["observe", "warm"]),
    ("fiend_eb782a8e133c683acfbefcbd87909450abfae8e6.wav", "FIEND", "...I see you.", ["observe", "protect", "warm"]),
    ("fiend_c7480121c8757ba2ce43179d2a75baf3fe446009.wav", "FIEND", "...together.", ["aftercare", "warm"]),
    ("fiend_51fcce9b3808b51e694f125fc6345db592678d45.wav", "FIEND", "With you.", ["aftercare", "protect", "warm"]),
    ("fiend_c8743fa46f8ef42f3606a37648dd3ffbd3d636c5.wav", "FIEND", "...always with you.", ["aftercare", "protect", "warm"]),
    ("fiend_7da89508a0ffa3b175709a5ad72c91e5d9aa7131.wav", "FIEND", "...my Birdsong.", ["aftercare", "warm"]),
    ("fiend_3e01a3c33ffc8c358bc4ff27d52635840dfd62f0.wav", "FIEND", "...hey.", ["observe", "warm"]),
]


# Optional: pygame mixer for overlapping voice playback
try:
    import pygame  # type: ignore
except Exception:
    pygame = None

from typing import Optional, Dict, Any, List, Tuple

# --- Noise 0–100 rubric (single dial) ---
# Default Noise=35 matches the shipped 'balanced' tuning (preserves prior tone).
def _noise_0_100() -> int:
    try:
        n = int(float(os.environ.get("LOCKKEY_NOISE", "35") or "35"))
    except Exception:
        n = 35
    return max(0, min(100, n))


def _noise_defaults() -> Dict[str, float]:
    """Derive default tuning from the Noise dial, only used when a specific env var is not set.

    These formulas are calibrated so Noise=35 reproduces existing defaults."""
    n = _noise_0_100()
    # Linear around 35; clamps keep sane bounds.
    murmur = max(0.04, min(0.24, 0.12 + (n - 35) * 0.0008))
    interrupt = max(0.02, min(0.20, 0.10 + (n - 35) * 0.0010))
    motif_rate = max(0.10, min(0.30, 0.22 + (35 - n) * 0.0015))
    beat_motif_rate = max(0.10, min(0.40, 0.28 + (35 - n) * 0.0012))
    motif_max = int(max(4, min(10, round(6 + (35 - n) * 0.03))))
    return {
        "murmur_rate": murmur,
        "interrupt_rate": interrupt,
        "motif_rate": motif_rate,
        "beat_motif_rate": beat_motif_rate,
        "motif_max": float(motif_max),
    }



# Stage directions are written in subtitles like *hair flip* or *head tilt*.
# They should remain visible but must NOT be read aloud.
_STAGE_DIR_RE = re.compile(r"\*([^*]{1,120})\*")


def _extract_stage_directions(text: str) -> List[str]:
    try:
        return [m.group(1).strip().lower() for m in _STAGE_DIR_RE.finditer(str(text or "")) if (m.group(1) or "").strip()]
    except Exception:
        return []


def _strip_stage_directions(text: str) -> str:
    """Remove *stage directions* but leave the rest of the sentence intact."""
    s = str(text or "")
    try:
        s = _STAGE_DIR_RE.sub("", s)
    except Exception:
        pass
    # collapse whitespace
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s




# Nonverbal-in-voice only: keep it tiny and semantically safe.
# Instead of playing separate overlapping "bark" audio (which can collide or truncate lines),
# we inject a short nonverbal token inline into the *same* TTS request.
_INLINE_NONVERBALS_DEFAULT = [
    "heh.", "mm.", "mhm.", "hmm.", "tch.", "ah.", "oh.", "hah."
]

def _is_safe_inline_nonverbal(nv: str) -> bool:
    s = str(nv or "").strip().lower()
    return bool(s) and len(s) <= 6 and all(ch.isalpha() or ch in ".'" for ch in s)

def _elongate_ending(text: str, mood_name: Optional[str] = None, strength: int = 2) -> str:
    """Add a soft affectionate/drawled ending to the final word.

    Used ONLY to create cache text variants and to bias offline packs toward
    legible affection (the 'ending softening / drawl / affectionate spill').

    Safety:
    - Never doubles-up if the text already has explicit elongation markers.
    - Keeps punctuation.
    """
    s = str(text or "")
    if not s.strip():
        return s

    m = (mood_name or "").upper()

    # Clamp strength
    try:
        strength = int(strength)
    except Exception:
        strength = 2
    strength = max(0, min(strength, 6))

    # If already elongated (~~~ / ... / repeated letters), do nothing.
    if re.search(r"(~~+|\.\.\.+|([A-Za-z])\2{3,})", s):
        return s

    # Only apply in moods where it reads as affectionate / playful / soft.
    allow = (
        "SOFT" in m or "AFTERCARE" in m or "DUET" in m or "TEASE" in m or
        "GLINT" in m or "MELT" in m or "LOVE" in m or "DEVOTION" in m
    )
    if not allow:
        return s

    # Split trailing punctuation.
    punct = ""
    base = s
    mm = re.search(r"([\.!\?…]+)$", s)
    if mm:
        punct = mm.group(1)
        base = s[:-len(punct)]

    # Only target the final word.
    w = re.search(r"([A-Za-z']+)$", base)
    if not w:
        return s
    word = w.group(1)

    lower = word.lower()
    repl = word

    if re.search(r"(ing|ed)$", lower):
        repl = word + ("h" * max(1, strength // 2))
    elif re.search(r"[aeiouy]$", lower):
        repl = word + (word[-1] * strength)
    elif re.search(r"(r|l|h)$", lower):
        repl = word + (word[-1] * max(1, strength // 2))
    elif lower == "just":
        repl = "j" + ("u" * (strength + 1)) + "st"
    elif lower == "please":
        repl = "pl" + ("e" * (strength + 1)) + "ase"

    out = re.sub(r"\b" + re.escape(word) + r"$", repl, base)

    # Gentle question-mark spice in duet/tease.
    if punct == "?" and ("DUET" in m or "TEASE" in m or "DUET_PLUS" in m):
        return out + "…?"
    return out + (punct or "")

    m = (mood_name or "").upper()
    # Stronger elongation in cinematic/duet+/tired pout; lighter elsewhere.
    strength = 3
    if "CINEMATIC" in m or "DUET_PLUS" in m or "TIRED" in m:
        strength = 5
    elif "FRENZY" in m:
        strength = 2

    # Normalize trailing punctuation.
    punct = ""
    if s and s[-1] in "?!.":
        punct = s[-1]
        base = s[:-1].rstrip()
    else:
        base = s

    # Only elongate on specific end-words.
    low = base.lower()
    # Match whole-word endings
    for word, vowel in [
        ("okay", "y"),
        ("ok", "y"),
        ("yeah", "a"),
        ("yah", "a"),
        ("no", "o"),
        ("please", "e"),
    ]:
        if re.search(r"\b" + re.escape(word) + r"$", low):
            if word in ("okay", "ok"):
                repl = word + ("y" * strength)
            elif word in ("yeah", "yah"):
                repl = word[:-1] + ("a" * strength) + "h"
            elif word == "no":
                repl = "no" + ("o" * strength)
            elif word == "please":
                # "pleeease" style
                repl = "pl" + ("e" * (strength+1)) + "ase"
            else:
                repl = word
            base2 = re.sub(r"\b" + re.escape(word) + r"$", repl, base, flags=re.IGNORECASE)
            # Add a soft ellipsis when it's a question/tease-y mood.
            if punct == "?" and ("DUET" in m or "TEASE" in m or "DUET_PLUS" in m):
                return base2 + "…?"
            return base2 + (punct or "")
    return s
def _get_env_or_registry(name: str) -> str:
    """Return an env var or registry value, trimmed. Also strips surrounding quotes (setx often stores quotes)."""
    def _strip_outer_quotes(s: str) -> str:
        s = (s or "").strip()
        # strip up to 2 layers of matching outer quotes
        for _ in range(2):
            if len(s) >= 2 and ((s[0] == s[-1]) and s[0] in ("'", '"')):
                s = s[1:-1].strip()
        return s

    v = os.environ.get(name, "") or ""
    v = _strip_outer_quotes(str(v))
    if v:
        return v

    # Windows registry fallbacks (HKCU then HKLM), value name matches env var name.
    try:
        import subprocess

        roots = [
            r"HKCU\Environment",
            r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        ]
        for root in roots:
            try:
                p = subprocess.run(
                    ["reg", "query", root, "/v", name],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if p.returncode != 0:
                    continue
                out = p.stdout or ""
                # Expect line like: <name>    <type>    <value>
                for line in out.splitlines():
                    if line.strip().lower().startswith(name.lower() + " "):
                        parts = line.split(None, 2)
                        if len(parts) >= 3:
                            vv = _strip_outer_quotes(parts[2])
                            if vv:
                                return vv
            except OSError:
                continue
    except Exception:
        pass
    return ""

def _require_env(name: str) -> str:
    v = _get_env_or_registry(name)
    if not v:
        raise RuntimeError(f"LOCKKEY: Missing required environment variable: {name}")
    return v

def _key_fingerprint(k: str) -> str:
    k = (k or "")
    tail = k[-4:] if len(k) >= 4 else k
    return f"len={len(k)} tail=***{tail}"

def _want_debug() -> bool:
    return str(os.environ.get("LOCKKEY_DEBUG", "")).strip().lower() in ("1", "true", "yes", "on")


def _is_truthy_env(name: str, default: bool = False) -> bool:
    v = str(os.environ.get(name, ""))
    if v.strip() == "" and default:
        return True
    return v.strip().lower() in ("1", "true", "yes", "on")

def _as_int(v: str, default: int) -> int:
    try:
        return int(str(v).strip())
    except Exception:
        return default



def _parse_json_env(name: str) -> Optional[dict]:
    """Parse a JSON object from an env var (or registry), returning dict or None."""
    raw = _get_env_or_registry(name)
    if not raw:
        return None
    try:
        j = json.loads(str(raw))
        return j if isinstance(j, dict) else None
    except Exception:
        return None
def _shorten_for_tts(text: str, max_chars: int) -> str:
    """Keep ElevenLabs requests cheap by truncating very long lines.

    Credits generally scale with text length and model; truncation prevents one giant
    narrated paragraph from consuming the remaining quota.
    """
    s = str(text or "").strip()
    if max_chars <= 0 or len(s) <= max_chars:
        return s



def _is_bark_like(text: str) -> bool:
    """Strict heuristic: identify short interjections that are allowed to overlap.
    We keep this conservative so we don't accidentally treat meaningful sentences as barks.
    """
    s = str(text or "").strip()
    if not s:
        return False
    # Very short = bark.
    if len(s) <= 22:
        return True
    # Short and "interjection-y"
    if len(s) <= 36:
        # Avoid treating full sentences as barks.
        if any(p in s for p in (".", ";", ":")):
            return False
        # Allow question/exclaim + short
        if s.endswith(("!", "?", "~")):
            return True
        # Common quick barks
        core = re.sub(r"[^a-zA-Z\s]", "", s).strip().lower()
        if core in {"mm", "mhm", "mhmm", "oh", "ooh", "uh", "uhh", "hey", "hah", "ha", "yeah", "yep", "no", "nah", "okay", "ok", "good", "cute", "please", "more"}:
            return True
    return False

    # Prefer cutting at a natural boundary.
    cut = max_chars
    for sep in (". ", "! ", "? ", "; ", ": ", ", "):
        i = s.rfind(sep, 0, max_chars)
        if i >= max(40, int(max_chars * 0.35)):
            cut = i + len(sep) - 1
            break
    s = s[:cut].rstrip()
    return s + "…"



def _is_grounded_bit(text: str, stage_dirs: list[str]) -> bool:
    """Detect 'intentional bit' / narrator-aside delivery.

    We keep this conservative. It should only trigger when the line is clearly performative.
    """
    s = (text or "").strip().lower()
    if not s:
        return False
    sd = " ".join([str(x or "").lower() for x in (stage_dirs or [])])
    # Stage-direction triggers
    if any(k in sd for k in ("narrat", "announc", "theatr", "aside", "monolog", "presenter", "commentary")):
        return True
    # Textual triggers
    starters = (
        "and now", "in tonight", "ladies and gentlemen", "behold", "welcome to", "previously on",
        "and in this episode", "coming up next", "for your consideration"
    )
    if s.startswith(starters):
        return True
    # Explicit self-tag in text (rare)
    if s.startswith(("narrator:", "announcer:", "aside:")):
        return True
    return False


def _is_sharp_like(text: str) -> bool:
    """Detect lines that may land too sharp/mean for the 'warm tease equal' archetype.

    This is a soft safety net: if it flags, we can soften with a light 'just kidding though'.
    """
    s = (text or "").strip()
    if not s:
        return False
    lo = s.lower()
    # If it's already softened, don't touch it.
    if "just kidding" in lo or "kidding" in lo:
        return False
    # Hard insults (avoid false positives)
    sharp_words = ("idiot", "stupid", "dumb", "pathetic", "gross", "trash", "loser", "shut up", "hate you")
    if any(w in lo for w in sharp_words):
        return True
    # Very short negative snaps
    if len(s) <= 40 and (lo.startswith(("no.", "no,", "stop", "don't", "do not", "whatever", "ugh", "seriously"))):
        return True
    # Lots of exclamation + imperative can read harsh
    if s.count("!") >= 2 and len(s) <= 90:
        return True
    return False
def _validate_elevenlabs_key(api_key: str, label: str, timeout: int = 10) -> None:
    raise RuntimeError("Runtime voice generation was removed from the public build; shipped recordings only.")
    """Fail fast with a readable message if an API key is missing/invalid/restricted."""
    if not api_key or not str(api_key).strip():
        raise RuntimeError(f"LOCKKEY: {label} ElevenLabs API key is empty")
    # Cheap auth check: /v1/user (or models) with xi-api-key.
    url = "https://api.elevenlabs.io/v1/user"
    req = urllib.request.Request(url, method="GET")
    req.add_header("xi-api-key", str(api_key).strip())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            # Any 2xx means the key is valid; body not needed.
            _ = resp.read(1)
            return
    except urllib.error.HTTPError as e:
        # Try to surface ElevenLabs' own error code (invalid_api_key, etc.)
        body = ""
        try:
            body = (e.read() or b"")[:4000].decode("utf-8", "replace")
        except Exception:
            pass
        msg = f"LOCKKEY: {label} ElevenLabs auth check failed ({e.code}).\n"
        msg += "This usually means: (1) the key is wrong/expired, or (2) the key has endpoint scope restrictions that block TTS.\n"
        msg += f"Key fingerprint: {_key_fingerprint(str(api_key).strip())}\n"
        if body:
            msg += f"Server message: {body}\n"
        msg += "Fix: In ElevenLabs → Settings/Developers → API Keys, regenerate a key and ensure it has access to Text-to-Speech endpoints.\n"
        raise RuntimeError(msg)
    except Exception as e:
        # Network/SSL/etc. Don't hard-fail unless they try to use TTS.
        if _want_debug():
            print(f"LOCKKEY: {label} auth check skipped (network error): {e}")
        return

# Embedded API key (prototype-only). Do NOT share this build.
_EMBEDDED_ELEVENLABS_API_KEY = ""  # stripped for public release — use your own key  # deprecated; use env vars ELEVENLABS_API_KEY_BIRD / ELEVENLABS_API_KEY_FIEND

DEFAULT_VOICE_ID = "ucFRCmbiaIxZfREpqsFw"
DEFAULT_FIEND_VOICE_ID = ""  # set in config or env; empty means fallback to DEFAULT_VOICE_ID

# Offline cache signature defaults (used when LOCKKEY_OFFLINE=1 or API keys are missing).
# These should match the voice IDs used when generating the bundled voice_cache wavs.
OFFLINE_DEFAULT_BIRD_VOICE_ID = "HyHeP4mGo90GnjhEn3gB"
OFFLINE_DEFAULT_FIEND_VOICE_ID = "bJMiTn2Y4zcwbsweBZXw"
DEFAULT_MODEL_ID = "eleven_multilingual_v2"
DEFAULT_OUTPUT_FORMAT = "pcm_44100"  # max quality; 2026-09-25: was pcm_22050

def _pcm_sr(fmt: str) -> int:
    try:
        if fmt.startswith("pcm_"):
            return int(fmt.split("_", 1)[1])
    except Exception:
        pass
    return 22050

def _wrap_pcm16le_mono_to_wav(pcm: bytes, sample_rate: int) -> bytes:
    nch = 1
    bps = 16
    byte_rate = sample_rate * nch * bps // 8
    block_align = nch * bps // 8
    data_size = len(pcm)
    riff_size = 36 + data_size

    def p32(x: int) -> bytes:
        return struct.pack("<I", x)
    def p16(x: int) -> bytes:
        return struct.pack("<H", x)

    header = b"RIFF" + p32(riff_size) + b"WAVE"
    header += b"fmt " + p32(16)
    header += p16(1)
    header += p16(nch)
    header += p32(sample_rate)
    header += p32(byte_rate)
    header += p16(block_align)
    header += p16(bps)
    header += b"data" + p32(data_size)
    return header + pcm

def _apply_gain_inplace_wav(path: Path, gain_db: float = 16.0, peak_limit: float = 0.97) -> None:
    import wave  # local safety import
    # Reads 16-bit mono WAV and boosts it with limiter.
    if gain_db is None:
        return
    try:
        gain_db = float(gain_db)
    except Exception:
        return
    if abs(gain_db) < 0.01:
        return

    with wave.open(str(path), "rb") as wf:
        nch = wf.getnchannels()
        sw = wf.getsampwidth()
        fr = wf.getframerate()
        n = wf.getnframes()
        frames = wf.readframes(n)

    if sw != 2:
        return

    # If stereo, downmix (rare)
    if nch == 2:
        left = audioop.tomono(frames, 2, 1.0, 0.0)
        right = audioop.tomono(frames, 2, 0.0, 1.0)
        frames = audioop.add(left, right, 2)
        frames = audioop.mul(frames, 2, 0.5)
        nch = 1

    scale = 10.0 ** (gain_db / 20.0)
    boosted = audioop.mul(frames, 2, scale)

    peak = audioop.max(boosted, 2)
    limit = int(peak_limit * 32767)
    if peak > limit and peak > 0:
        boosted = audioop.mul(boosted, 2, limit / float(peak))

    # De-click: short fades to avoid pops/static between clips
    try:
        fade_ms = float(os.environ.get('LOCKKEY_VOICE_DECICK_MS', '10') or 10)
        fade_ms = max(0.0, min(40.0, fade_ms))
        fade_n = int((fr * fade_ms) / 1000.0)
        fade_n = max(0, min(fade_n, int(len(boosted) / 2 / 4)))  # cap to quarter length
        if fade_n >= 8:
            import array
            a = array.array('h')
            a.frombytes(boosted)
            # fade in
            for j in range(fade_n):
                a[j] = int(a[j] * (j / float(fade_n)))
            # fade out
            L = len(a)
            for j in range(fade_n):
                k = L - fade_n + j
                a[k] = int(a[k] * (1.0 - (j / float(fade_n))))
            boosted = a.tobytes()
    except Exception:
        pass

    # Write back
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(fr)
        out.writeframes(boosted)


def wav_duration_seconds(path: Path) -> float:
    try:
        import wave
        with contextlib.closing(wave.open(str(path), "rb")) as wf:
            n = wf.getnframes()
            fr = wf.getframerate()
            if fr <= 0:
                return 0.0
            return float(n) / float(fr)
    except Exception:
        return 0.0


def _should_voice_text(speaker: str, text: str) -> bool:
    """Filter out formatting and action/narration stage directions from voicing."""
    t = (text or "").strip()
    if not t:
        return False

    # No letters/numbers -> likely UI separators or pure punctuation
    if not re.search(r"[A-Za-z0-9]", t):
        return False

    # Common stage-direction wrappers
    if (t.startswith("(") and t.endswith(")")) or (t.startswith("[") and t.endswith("]")):
        return False
    if (t.startswith("*") and t.endswith("*")) or (t.startswith("~") and t.endswith("~")):
        return False

    # Explicit action prefix tags
    if re.match(r"^\s*(\*+|\[action\]|\(action\)|\(sfx\)|\[sfx\])\b", t, flags=re.I):
        return False

    # Avoid narrating actions: short third-person / second-person action lines
    if speaker.upper() in ("NARRATOR", "SYSTEM", "HUD"):
        # e.g., "You nod.", "She blushes.", "He laughs."
        if re.match(r"^(you|she|he|they|birdsong|fiend)\s+\w+(ed|s)\b", t, flags=re.I) and len(t) <= 90:
            return False

    return True


def _post_preset_sox_args(post_preset: str) -> list[str]:
    """
    Additional SoX effects for speaker-specific character.
    'fiend_bit' = Birdsong doing a playful deeper bro-ish bit (non-derogatory):
      - slightly lower pitch
      - more low-mid presence (500–1200Hz), less sharp edge
      - gentler tremolo
    """
    p = (post_preset or "default").lower()
    if p == "fiend_bit":
        return [
            "pitch", "-180",          # ~ -1.8 semitones (impression, not full male)
            "equalizer", "900", "1.0q", "3",   # +3 dB around 900Hz (presence)
            "equalizer", "3500", "1.0q", "-2", # tame edge
            "tremolo", "6", "0.35",   # softer tremolo
        ]
    return []

class AudioManager:
    def __init__(self):
        # non-optional voices (prototype)
        self.enabled = True
        self.backend = "elevenlabs"
        self.voice_id = DEFAULT_VOICE_ID  # legacy default
        self.bird_voice_id = DEFAULT_VOICE_ID
        self.fiend_voice_id = (DEFAULT_FIEND_VOICE_ID or DEFAULT_VOICE_ID)

        # Overlapping chaos mode: allow multiple voice barks to overlap (limited channel pool).
        # Uses pygame.mixer channels when available; falls back to winsound if not.
        self.voice_overlap_mode = _get_env_or_registry("LOCKKEY_VOICE_OVERLAP").strip() not in ("0","false","False","off","OFF","")
        self._use_pygame_voice = False
        self._voice_channels = []
        self._voice_rr = 0
        self._voice_primary_channel = None
        self._voice_bark_channels = []
        # Anti-stack / flow guards for voice (prevents repeat dialogue piling up)
        self._recent_spoken = {}  # speaker -> {text, t}
        self._cooldown_until_by_speaker = {}  # speaker -> timestamp
        self._no_barks_until = 0.0

        # Voice backend: winsound (default) or pygame (if installed) for overlap mixing.
        backend = (_get_env_or_registry("LOCKKEY_VOICE_BACKEND") or "").strip().lower()
        if backend in ("", "auto"):
            backend = "pygame" if (pygame is not None and self.voice_overlap_mode) else "winsound"
        if backend == "pygame" and pygame is not None and self.voice_overlap_mode:
            try:
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
                pygame.mixer.set_num_channels(16)
                # Reserve a small pool of channels for voice so barks can overlap.
                # 12 = primary full lines (never stolen)
                # 13 = murmur/underlay channel
                # 14 = interrupt/cut-in channel
                # 15 = short barks/spice channel
                self._voice_channels = [pygame.mixer.Channel(i) for i in range(12, 16)]
                self._voice_primary_channel = self._voice_channels[0] if self._voice_channels else None
                self._voice_murmur_channel = self._voice_channels[1] if len(self._voice_channels) > 1 else None
                self._voice_interrupt_channel = self._voice_channels[2] if len(self._voice_channels) > 2 else None
                self._voice_bark_channels = [self._voice_channels[3]] if len(self._voice_channels) > 3 else self._voice_channels[1:]
                self._use_pygame_voice = True
                self._use_pygame_voice = True
            except Exception:
                self._use_pygame_voice = False
        else:
            self._use_pygame_voice = False
        self.model_id = DEFAULT_MODEL_ID
        self.output_format = DEFAULT_OUTPUT_FORMAT
        self.voice_settings = None  # can be dict

        self.in_rhythm = False
        self.pause_active = False

        # LOCKKEY_MOOD_V1: closed-box mood name (set by the engine)
        self.scene_mood_name = "DUET_TEASE_LOOP"

        # Closed-box mannerisms (voice-only nonverbals). These are intentionally
        # not shown as text and never replace semantic content.
        self._line_count_by_speaker = {"FIEND": 0, "BIRDSONG": 0, "NARRATOR": 0, "SOUND": 0}
        self._last_nonverbal_at = {"FIEND": 0.0, "BIRDSONG": 0.0, "NARRATOR": 0.0}
        # Track whether a speaker is currently in an 'intentional bit' (grounded narration) lane.
        self._bit_state_by_speaker = {"FIEND": False, "BIRDSONG": False, "NARRATOR": False}

        self._rng = random.Random(1337)
        # Timing guardrails: reduce overlap permission without slowing overall exchange.
        self._primary_line_end_time = 0.0  # wall-clock time when current full line ends
        self._bark_preempt_window = 0.18    # allow barks only near end of a full line
        self._nonverbal_cooldown = 1.15     # seconds between voice-only mannerisms per speaker

        # Cache + bundled offline voice support:
        # - home cache is writable (runtime TTS caching)
        # - bundled cache ships with the game (read-only, offline playback)
        home = Path(os.path.expanduser("~"))
        self.home_cache_dir = home / ".ogre_shader_cache" / "voice"
        self.home_cache_dir.mkdir(parents=True, exist_ok=True)

        # Optional explicit cache dir override (useful for portable installs)
        override_dir = str(os.environ.get("LOCKKEY_VOICE_CACHE_DIR", "")).strip()
        self.override_cache_dir = Path(override_dir).expanduser().resolve() if override_dir else None
        if self.override_cache_dir:
            try:
                self.override_cache_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                self.override_cache_dir = None

        # Bundled cache lives next to this file: lovesong/voice_cache/*.wav
        # 2026-09-25: Bundled cache is DISABLED by default. The game is ElevenLabs-first;
        # we do not ship with 175MB of pre-recorded audio. The writable cache still
        # saves synthesized lines (write-through) to save API calls during play.
        # Set BRATBOX_BUNDLED_VOICE=1 to re-enable bundled cache lookup.
        try:
            if os.environ.get("BRATBOX_BUNDLED_VOICE", "").strip() == "1":
                self.bundled_cache_dir = (Path(__file__).resolve().parent / "voice_cache")
            else:
                self.bundled_cache_dir = None
        except Exception:
            self.bundled_cache_dir = None
        if self.bundled_cache_dir is None:
            try:
                self.bundled_cache_dir = Path.cwd() / "voice_cache" if os.environ.get("BRATBOX_BUNDLED_VOICE", "").strip() == "1" else None
            except Exception:
                self.bundled_cache_dir = None

        # Primary cache dir is where we *write* new wavs.
        self.cache_dir = self.override_cache_dir or self.home_cache_dir

        # Search order for reads (bundled first, then writable cache).
        self.cache_search_dirs = [d for d in [self.bundled_cache_dir, self.cache_dir] if d is not None]
        # Offline transcript + wildcard metadata (optional)
        # If voice_tags.jsonl/json exists in cache dirs, we can match text->audio by transcript similarity
        # and route unassigned/babble files as 'wildcards' for momentum.
        self.voice_tags: Dict[str, Dict[str, Any]] = {}
        self.voice_catalog: Dict[str, List[Path]] = {"birdsong": [], "fiend": [], "any": []}
        self._voice_tags_loaded: bool = False
        self._scan_voice_cache_loaded: bool = False
        try:
            self._load_voice_tags()
        except Exception:
            pass
        for _fn, _speaker, _transcript, _tags in _BUNDLED_RECORDED_DIALOGUE:
            try:
                if (_fn not in self.voice_tags
                        and any((Path(_dir) / _fn).exists() for _dir in self.cache_search_dirs)):
                    self.voice_tags[_fn] = {
                        "file": _fn,
                        "speaker": _speaker,
                        "transcript": _transcript,
                        "tags": list(_tags),
                        "source": "bundled_recorded_dialogue",
                    }
            except Exception:
                continue
        try:
            self._scan_voice_cache()
        except Exception:
            pass

        # Balanced dialogue director state (for vibe-first matching + wildcard pacing)
        self._recent_voice_files: List[str] = []
        self._recent_voice_ts: List[float] = []
        self._wildcard_last_ts: float = 0.0
        self._wildcard_recent_ts: List[float] = []
        # Session motif memory (recurring favorites per speaker+intent)
        self._motif_by_key: Dict[Tuple[str, str], List[str]] = {}
        self._motif_last_used: Dict[str, float] = {}

        # Beat-position motifs (recurring favorites tied to rhythmic slot + role)
        # Keyed by (speaker_key, intent, role, slot_in_bar) -> [filenames...]
        self._beat_motif_by_key: Dict[Tuple[str, str, str, int], List[str]] = {}
        self._beat_motif_last_used: Dict[str, float] = {}
        try:
            if "LOCKKEY_BEAT_MOTIF_RATE" in os.environ:
                self._beat_motif_rate = float(os.environ.get("LOCKKEY_BEAT_MOTIF_RATE", "0.28") or 0.28)
            else:
                self._beat_motif_rate = float(_noise_defaults().get("beat_motif_rate", 0.28))
        except Exception:
            self._beat_motif_rate = 0.28

        # Director safety / fragility controls
        self._director_disabled_until: float = 0.0
        self._director_soft_disabled_until: float = 0.0

        # Loudness normalization + music ducking (pygame backend only)
        self._wav_rms_cache: Dict[str, float] = {}
        self._target_voice_rms: float = float(os.environ.get("LOCKKEY_VOICE_TARGET_RMS", "1800") or 1800)
        self._music_duck_factor: float = float(os.environ.get("LOCKKEY_MUSIC_DUCK_FACTOR", "0.72") or 0.72)
        self._music_duck_release_ms: int = int(float(os.environ.get("LOCKKEY_MUSIC_DUCK_RELEASE_MS", "160") or 160))
        self._music_prev_volume: Optional[float] = None

        # Overlap / interrupt / motif tuning (Balanced defaults)
        # Overlap / interrupt / motif tuning (Balanced defaults; can be steered by LOCKKEY_NOISE)
        nd = _noise_defaults()
        self._murmur_rate = float(os.environ.get("LOCKKEY_MURMUR_RATE", str(nd.get("murmur_rate", 0.12))) or nd.get("murmur_rate", 0.12))
        self._interrupt_rate = float(os.environ.get("LOCKKEY_INTERRUPT_RATE", str(nd.get("interrupt_rate", 0.10))) or nd.get("interrupt_rate", 0.10))
        self._motif_rate = float(os.environ.get("LOCKKEY_MOTIF_RATE", str(nd.get("motif_rate", 0.22))) or nd.get("motif_rate", 0.22))
        self._motif_max = int(float(os.environ.get("LOCKKEY_MOTIF_MAX", str(nd.get("motif_max", 6))) or nd.get("motif_max", 6)))
        self._director_shutdown_s: float = float(os.environ.get("LOCKKEY_DIRECTOR_SHUTDOWN_S", "12") or 12)


        # Non-destructive mask windows: OST can open a pocket and request a sanctioned micro-texture.
        try:
            from procedural_ost import ost_register_mask_callback
            ost_register_mask_callback(lambda tag, intensity=0.0, track="": _on_ost_mask_window(self, tag=str(tag or "mask"), intensity=float(intensity or 0.0), track=str(track or "")))
        except Exception:
            pass





        # Session stats (debug + tuning). Written to cache_dir/voice_session_report.json on exit.
        self._session_stats: Dict[str, Any] = {
            "started_ts": time.time(),
            "offline": bool(getattr(self, "offline", False)),
            "lines_total": 0,
            "lines_voiced": 0,
            "offline_missing": 0,
            "best_effort_used": 0,
            "wildcards_used": 0,
            "motifs_used": 0,
            "underlays_used": 0,
            "interrupts_used": 0,
            "suffix_used": 0,
            "director_soft_shutdowns": 0,
        }
        try:
            import atexit
            atexit.register(self._write_session_report)
        except Exception:
            pass
        # Loudness vs music
        self.voice_gain_db = float(os.environ.get("LOCKKEY_VOICE_GAIN_DB", "8.0") or 8.0)
        self._last_error: Optional[str] = None

        # Quota safety: don't hard-crash the game if an account runs out.
        #   LOCKKEY_ON_QUOTA=mute  -> skip voicing for that account after quota_exceeded
        #   LOCKKEY_ON_QUOTA=crash -> preserve old behavior (raise)
        self.on_quota = str(os.environ.get("LOCKKEY_ON_QUOTA", "mute")).strip().lower()
        self.max_tts_chars_bird = _as_int(os.environ.get("LOCKKEY_TTS_MAX_CHARS_BIRD", "0"), 0)  # 0 = no truncation
        self.max_tts_chars_fiend = _as_int(os.environ.get("LOCKKEY_TTS_MAX_CHARS_FIEND", "0"), 0)  # 0 = no truncation
        
        # Full-fidelity long lines: chunk instead of truncate (per-request safety).
        self.tts_chunk_chars = _as_int(os.environ.get("LOCKKEY_TTS_CHUNK_CHARS", "950"), 950)
        self.tts_chunk_silence_ms = _as_int(os.environ.get("LOCKKEY_TTS_CHUNK_SILENCE_MS", "8"), 8)

        # ElevenLabs latency tuning (higher = lower latency). Range depends on ElevenLabs; typical 0-4.
        self.latency_bird = _as_int(os.environ.get("LOCKKEY_ELEVEN_LATENCY_BIRD", "2"), 2)
        self.latency_fiend = _as_int(os.environ.get("LOCKKEY_ELEVEN_LATENCY_FIEND", "3"), 3)

        # Per-speaker voice settings (JSON). If unset, defaults apply (Fiend gets more expressive settings).
        self.voice_settings_bird = _parse_json_env("LOCKKEY_ELEVEN_VOICE_SETTINGS_BIRD") or None
        self.voice_settings_fiend = _parse_json_env("LOCKKEY_ELEVEN_VOICE_SETTINGS_FIEND") or {
            "stability": 0.42,
            "similarity_boost": 0.82,
            "style": 0.55,
            "speed": 1.0,
            "use_speaker_boost": True,
        }

        # Fiend "mode" presets. You can override the whole map with:
        #   LOCKKEY_FIEND_VOICE_PRESETS='{"TM":{...},"PC":{...},"BF":{...},"SD":{...}}'
        # Or lock a single mode for all Fiend lines with:
        #   LOCKKEY_FIEND_MODE=TM   (or PC/BF/SD)
        default_presets = {
            # Teasing & musical: playful, sing-song, expressive
            "TM": {"stability": 0.34, "similarity_boost": 0.80, "style": 0.70, "use_speaker_boost": True},
            # Predatory calm: steady, low volatility, controlled menace
            "PC": {"stability": 0.62, "similarity_boost": 0.90, "style": 0.25, "use_speaker_boost": True},
            # Bratty fast-talk: chaotic, quick, high style
            "BF": {"stability": 0.26, "similarity_boost": 0.78, "style": 0.80, "use_speaker_boost": True},
            # Soft domination: smooth, confident, warm control
            "SD": {"stability": 0.50, "similarity_boost": 0.88, "style": 0.45, "use_speaker_boost": True},
        }
        self.fiend_voice_presets = _parse_json_env("LOCKKEY_FIEND_VOICE_PRESETS") or default_presets

        # Mode cycling: apply TM -> PC -> BF -> SD line-by-line unless locked/tagged.
        seq_raw = str(os.environ.get("LOCKKEY_FIEND_MODE_SEQUENCE", "TM,PC,BF,SD"))
        self.fiend_mode_sequence = [s.strip().upper() for s in seq_raw.split(",") if s.strip()]
        if not self.fiend_mode_sequence:
            self.fiend_mode_sequence = ["TM", "PC", "BF", "SD"]
        self.fiend_mode_lock = str(os.environ.get("LOCKKEY_FIEND_MODE", "")).strip().upper()
        self._fiend_mode_rr = 0

        self._quota_blocked = {"bird": False, "fiend": False}
        self._quota_warned = set()  # account tags that already printed a warning

        # Offline mode (2026-09-25: voice-mode aware):
        # - BRATBOX_VOICE_MODE=voiceless → no voices at all, skip TTS entirely
        # - BRATBOX_VOICE_MODE=cache → offline, play from cache only
        # - BRATBOX_VOICE_MODE=elevenlabs → online, needs API key
        # - LOCKKEY_OFFLINE=1 → fully disable any network TTS
        # - If API keys are missing, we automatically drop into offline-safe mode.
        _voice_mode = str(os.environ.get("BRATBOX_VOICE_MODE", "")).strip().lower()
        self.voice_mode = _voice_mode or "elevenlabs"  # default to elevenlabs for backward compat

        self.offline = False
        if _voice_mode == "voiceless":
            self.offline = True
            self.voiceless = True
        elif _voice_mode == "cache":
            self.offline = True
            self.voiceless = False
        else:
            self.voiceless = False

        if str(os.environ.get("LOCKKEY_OFFLINE", "")).strip() == "1":
            self.offline = True

        # API key: env var first (set by launcher), then embedded fallback
        key_bird = str(os.environ.get("ELEVENLABS_API_KEY", "") or "").strip()
        key_fiend = key_bird  # same key for both
        if not key_bird:
            try:
                key_bird = str(_EMBEDDED_ELEVENLABS_API_KEY or "").strip()
                key_fiend = key_bird
            except Exception:
                pass
        if not key_bird or not key_fiend:
            self.offline = True

        self._api_key_bird = key_bird
        self._api_key_fiend = key_fiend

        # Optional: fail-fast auth check so you don't crash mid-scene (only when online).
        if (not self.offline) and str(os.environ.get("LOCKKEY_VALIDATE_KEYS", "1")).strip() not in ("0", "false", "no", "off"):
            _validate_elevenlabs_key(self._api_key_bird, "BIRD")
            _validate_elevenlabs_key(self._api_key_fiend, "FIEND")

        if _want_debug():
            print("LOCKKEY: keycheck",
                  "bird", _key_fingerprint(self._api_key_bird),
                  "fiend", _key_fingerprint(self._api_key_fiend),
                  "offline", self.offline)

        # Voice IDs (per-account). For offline-only playback, we fall back to bundled-cache defaults.
        bird_default = OFFLINE_DEFAULT_BIRD_VOICE_ID if self.offline else DEFAULT_VOICE_ID
        fiend_default = OFFLINE_DEFAULT_FIEND_VOICE_ID if self.offline else (DEFAULT_FIEND_VOICE_ID or DEFAULT_VOICE_ID)

        self.bird_voice_id = (_get_env_or_registry("ELEVENLABS_VOICE_ID_BIRD") or bird_default).strip() or bird_default
        self.fiend_voice_id = (_get_env_or_registry("ELEVENLABS_VOICE_ID_FIEND") or fiend_default).strip() or fiend_default
        print(f"LOCKKEY: envcheck bird_voice_id={repr(getattr(self, 'bird_voice_id', None))} fiend_voice_id={repr(getattr(self, 'fiend_voice_id', None))} offline={self.offline}")

        # Beat gating (Director v1): align underlays/interrupts/suffix to musical beats.
        # Enabled by default; disable with LOCKKEY_BEAT_GATE=0
        try:
            self.beat_gate_enabled = str(os.environ.get("LOCKKEY_BEAT_GATE", "1") or "1").strip().lower() not in ("0","false","no","off")
            self.beat_gate_beats_per_bar = int(os.environ.get("LOCKKEY_BEAT_GATE_BPB", "4") or 4)
            self.beat_gate_offset_ms = int(os.environ.get("LOCKKEY_BEAT_GATE_OFFSET_MS", "0") or 0)
        except Exception:
            self.beat_gate_enabled = True
            self.beat_gate_beats_per_bar = 4
            self.beat_gate_offset_ms = 0
        self._beat_gate_phase = 0.0
        self._beat_gate_bpm = 120.0
        self._beat_gate_last_music_ms = None
        self._beat_gate_last_sync_t = 0.0
        self._beat_gate_last_beat_i = 0
        self._beat_gate_last_bar_i = 0

        # Fill grid (Director v1): constrain optional events to rhythmic slots (drum-pattern style).
        # Enabled by default; disable with LOCKKEY_FILL_GRID=0
        try:
            self.fill_grid_enabled = str(os.environ.get("LOCKKEY_FILL_GRID", "1") or "1").strip().lower() not in ("0","false","no","off")
        except Exception:
            self.fill_grid_enabled = True
        try:
            self.fill_grid_slots = int(os.environ.get("LOCKKEY_FILL_GRID_SLOTS", "8") or 8)
            if self.fill_grid_slots < 4:
                self.fill_grid_slots = 8
        except Exception:
            self.fill_grid_slots = 8

        # Default balanced patterns (length == fill_grid_slots). 1/x = allowed, 0/. = blocked.
        # prefix: downbeat only; interrupt: beats 1&3; underlay: beats 2&4; suffix: bar tail.
        def _pat(s: str) -> str:
            s = str(s or "").strip()
            if not s:
                return ""
            return re.sub(r"[^01xX\.]", "", s)

        slots = int(self.fill_grid_slots or 8)
        default_prefix    = ("1" + ("0" * (slots - 1))) if slots >= 1 else "1"
        default_interrupt = ("1" + ("0" * (max(0, (slots//2) - 1))) + "1" + ("0" * (max(0, slots - (slots//2) - 1)))) if slots >= 2 else "1"
        if slots == 8:
            default_underlay = "00100010"  # 2&4
        else:
            half = max(1, slots//2)
            q1 = max(0, half//2)
            q3 = min(slots-1, half + q1)
            arr = ["0"] * slots
            arr[q1] = "1"
            arr[q3] = "1"
            default_underlay = "".join(arr)
        default_suffix    = ("0" * (slots - 1) + "1") if slots >= 2 else "1"

        self.fill_grid_patterns: Dict[str, str] = {
            "prefix":    _pat(os.environ.get("LOCKKEY_FILL_GRID_PREFIX", ""))    or default_prefix,
            "interrupt": _pat(os.environ.get("LOCKKEY_FILL_GRID_INTERRUPT", "")) or default_interrupt,
            "underlay":  _pat(os.environ.get("LOCKKEY_FILL_GRID_UNDERLAY", ""))  or default_underlay,
            "suffix":    _pat(os.environ.get("LOCKKEY_FILL_GRID_SUFFIX", ""))    or default_suffix,
            "wildcard":  _pat(os.environ.get("LOCKKEY_FILL_GRID_WILDCARD", ""))  or default_underlay,
        }

    def write_voice_tag_request(self, bundle: str = "", tags: List[str] = None, mode: str = "blend", ttl_ms: int = 2500) -> bool:
        """Write a short-lived director tag request into the active cache dir.

        This is the fastest/most reliable way to steer clip selection per-line without touching other JSON.
        Returns True if a file was written.
        """
        try:
            req_name = (os.environ.get("LOCKKEY_DIRECTOR_TAG_REQUEST_FILE", "voice_tag_request.json") or "voice_tag_request.json").strip()
            out_dir = Path(getattr(self, "cache_dir", "") or "")
            if not str(out_dir):
                return False
            out_dir.mkdir(parents=True, exist_ok=True)

            obj = {
                "ts_ms": int(time.time() * 1000),
                "ttl_ms": int(ttl_ms) if ttl_ms is not None else 2500,
                "mode": (mode or "blend").strip().lower(),
                "nonce": f"{int(time.time()*1000)}_{random.randint(1000,9999)}",
            }
            if tags:
                obj["tags"] = [str(t).strip().lower() for t in (tags or []) if str(t).strip()]
            if bundle:
                obj["bundle"] = str(bundle).strip().upper()

            (out_dir / req_name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
            return True
        except Exception:
            return False


    def _api_key_for_speaker(self, sp: str) -> str:
        s = (sp or "NARRATOR").upper()
        if s == "FIEND":
            return self._api_key_fiend
        return self._api_key_bird

    def _voice_id_for_speaker(self, sp: str) -> str:
        s = (sp or "NARRATOR").upper()
        if s == "FIEND":
            return getattr(self, "fiend_voice_id", "")
        return getattr(self, "bird_voice_id", "") or DEFAULT_VOICE_ID

    def _map_tts_speaker(self, speaker: str) -> tuple[str, str]:
        """Return (tts_speaker, post_preset). post_preset can alter SoX chain."""
        sp = (speaker or "NARRATOR").upper()
        if sp == "FIEND":
            # FIEND uses its own ElevenLabs account + voice. (Separate key)
            return ("FIEND", "fiend_bit")
        return (sp, "default")


    def _extract_fiend_mode_tag(self, text: str) -> Tuple[Optional[str], str]:
        """Detect an explicit Fiend mode tag at the start of a line.
        Supported: {TM} {PC} {BF} {SD}  or [TM] etc. Returns (mode, cleaned_text).
        """
        s = str(text or "")
        m = re.match(r"^\s*[\{\[\(<]\s*(TM|PC|BF|SD)\s*[\}\]\)>]\s*", s, flags=re.IGNORECASE)
        if not m:
            return (None, s)
        mode = (m.group(1) or "").upper()
        cleaned = s[m.end():].lstrip()
        return (mode, cleaned)

    def _select_fiend_voice_settings_for_line(self, text: str) -> Tuple[Optional[dict], str, str]:
        """Return (voice_settings_override, cleaned_text, cache_extra) for a Fiend line."""
        tag_mode, cleaned = self._extract_fiend_mode_tag(text)

        # Global lock wins (unless an explicit tag is present).
        mode = (tag_mode or "").upper()
        if not mode:
            lock = (self.fiend_mode_lock or "").upper()
            if lock in self.fiend_voice_presets:
                mode = lock

        # Otherwise cycle through the sequence per line.
        if not mode:
            seq = self.fiend_mode_sequence or ["TM", "PC", "BF", "SD"]
            mode = seq[self._fiend_mode_rr % len(seq)]
            self._fiend_mode_rr += 1

        vs = self.fiend_voice_presets.get(mode) or self.voice_settings_fiend
        return (vs, cleaned, f"fiend_mode={mode}")


    def toggle(self) -> bool:
        # non-optional: always on
        self.enabled = True
        return True

    def set_rhythm_state(self, in_rhythm: bool, pause_active: bool = False) -> None:
        self.in_rhythm = bool(in_rhythm)
        self.pause_active = bool(pause_active)

    def set_scene_mood(self, mood_name: str) -> None:
        """Set the active closed-box mood profile (affects default voice tuning).

        This is intentionally not user-configurable via env vars: the game sets it.
        """
        try:
            self.scene_mood_name = str(mood_name or "").strip().upper() or "DUET_TEASE_LOOP"
        except Exception:
            self.scene_mood_name = "DUET_TEASE_LOOP"

    # ─────────────────────────────────────────────────────────────────────
    # Voice-only nonverbal mannerisms
    # ─────────────────────────────────────────────────────────────────────
    def _choose_nonverbal(self, speaker: str, mp, stage_dirs: List[str]) -> Optional[str]:
        """Pick a very short, semantically-safe nonverbal sound.

        This must never carry plot meaning — it's seasoning (laughs/hums/clicks).
        """
        sp = (speaker or "NARRATOR").upper()
        pool = None
        try:
            pool = getattr(mp, "nonverbal_pool", None) if mp is not None else None
        except Exception:
            pool = None

        # Keyword-triggered cues from stage directions.
        sjoin = " ".join(stage_dirs or [])
        if sjoin:
            if "hair" in sjoin:
                return self._rng.choice(["heh.", "hah.", "mm."])
            if "head tilt" in sjoin or "tilt" in sjoin:
                return self._rng.choice(["mm?", "hmm?", "mhm?"])
            if "tongue" in sjoin or "teeth" in sjoin or "crackle" in sjoin:
                return self._rng.choice(["tsk.", "tch.", "heh."])
            if "pout" in sjoin or "melt" in sjoin or "overwhelm" in sjoin:
                return self._rng.choice(["mhm...", "mm...", "hahhh..."])

        # Fallback: mood-defined pool, if any.
        if pool:
            try:
                return self._rng.choice(list(pool))
            except Exception:
                return None

        # Conservative defaults by speaker.
        if sp == "FIEND":
            return self._rng.choice(["mm.", "heh.", "hmm.", "hah."])
        if sp == "BIRDSONG":
            return self._rng.choice(["mm!", "huh?", "heh!", "tch—"])
        return None

    def _maybe_voice_nonverbal(self, tts_speaker: str, mp, stage_dirs: List[str]) -> Optional[str]:
        """Return a tiny nonverbal token to inject inline, or None.

        Closed-box aesthetic: no overlapping/interrupt barks that can truncate plot lines.
        We inject only very short, semantically-safe nonverbals into the same TTS request.
        """
        sp = (tts_speaker or "NARRATOR").upper()
        now = time.time()
        last = float(self._last_nonverbal_at.get(sp, 0.0) or 0.0)
        cd = float(getattr(self, "_nonverbal_cooldown", 1.15) or 1.15)
        if (now - last) < cd:
            return None

        every_n = 0
        try:
            every_n = int(getattr(mp, "nonverbal_every_n_lines", 0) or 0) if mp is not None else 0
        except Exception:
            every_n = 0

        triggered = bool(stage_dirs)
        if not triggered and every_n <= 0:
            return None

        if not triggered:
            n = int(self._line_count_by_speaker.get(sp, 0) or 0)
            if n <= 0 or (n % every_n) != 0:
                return None

        nv = self._choose_nonverbal(sp, mp, stage_dirs)
        if not nv:
            return None
        # Validate: keep it tiny.
        if not _is_safe_inline_nonverbal(nv):
            return None
        self._last_nonverbal_at[sp] = now
        return nv

    def _tts_elevenlabs_pcm(self, speaker: str, text: str, voice_settings_override: Optional[dict] = None) -> bytes:
        lat = str(self.latency_fiend if (speaker or "").upper() == "FIEND" else self.latency_bird)
        qs = {"output_format": self.output_format, "optimize_streaming_latency": lat}
        voice_id = self._voice_id_for_speaker(speaker)
        api_key = self._api_key_for_speaker(speaker)
        account_tag = "fiend" if (speaker or "").upper() == "FIEND" else "bird"
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?" + urllib.parse.urlencode(qs)
        payload = {"text": text, "model_id": self.model_id}
        vs = voice_settings_override if voice_settings_override is not None else (self.voice_settings_fiend if (speaker or "").upper() == "FIEND" else self.voice_settings_bird)
        if vs:
            payload["voice_settings"] = vs
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("xi-api-key", api_key)
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = (e.read() or b"")[:4000].decode("utf-8", "replace")
            except Exception:
                pass

            # Try to parse ElevenLabs structured error.
            status = None
            detail_msg = None
            try:
                j = json.loads(body) if body else {}
                detail = j.get("detail")
                if isinstance(detail, dict):
                    status = detail.get("status")
                    detail_msg = detail.get("message")
            except Exception:
                pass

            if status == "quota_exceeded":
                # Special-case so caller can downgrade gracefully instead of crashing.
                qmsg = detail_msg or body or "quota_exceeded"
                raise RuntimeError(
                    f"ELEVENLABS_QUOTA_EXCEEDED: {qmsg} (speaker={speaker} account={account_tag} voice_id={voice_id})"
                )

            msg = f"ElevenLabs request failed ({e.code}): {e} (speaker={speaker} account={account_tag} voice_id={voice_id})"
            if body:
                msg += f"\nServer message: {body}"
            if e.code in (400, 401):
                msg += "\nHint: 400/401 usually means the API key is wrong/empty, or the key is restricted to certain endpoints. Check ElevenLabs API key scopes."
            if e.code == 404:
                msg += "\nHint: Voice IDs are account-scoped. Make sure the voice_id exists in that specific ElevenLabs account."
            raise RuntimeError(msg)
        except Exception as e:
            msg = f"ElevenLabs request failed: {e} (speaker={speaker} account={account_tag} voice_id={voice_id})"
            raise RuntimeError(msg)

    def _tts_elevenlabs_pcm_chunked(self, speaker: str, text: str, voice_settings_override: Optional[dict] = None) -> bytes:
        """Synthesize long text in multiple ElevenLabs calls and stitch PCM together.

        ElevenLabs responses can fail on very long bodies depending on plan/model. Since the
        user wants full-fidelity (no truncation), we chunk long lines into smaller requests
        and concatenate the returned PCM with a tiny silence gap.
        """
        s = str(text or "").strip()
        if not s:
            return b""
        chunk_chars = int(getattr(self, "tts_chunk_chars", 950) or 950)
        # Keep a sane lower bound so we don't spam tiny requests.
        if chunk_chars < 120:
            chunk_chars = 120

        if len(s) <= chunk_chars:
            return self._tts_elevenlabs_pcm(speaker, s, voice_settings_override=voice_settings_override)

        # Simple chunking that prefers punctuation/word boundaries.
        chunks: List[str] = []
        i = 0
        n = len(s)
        while i < n:
            j = min(n, i + chunk_chars)
            piece = s[i:j]
            if j < n:
                # Backtrack for a nicer boundary near the end of the chunk.
                window = piece[-180:] if len(piece) > 180 else piece
                cut = None
                # Prefer sentence-ish punctuation.
                for ch in [". ", "! ", "? ", "; ", ": ", ", "]:
                    k = window.rfind(ch)
                    if k != -1 and k > 20:
                        cut = len(piece) - len(window) + k + len(ch)
                        break
                # Fall back to whitespace.
                if cut is None:
                    k = window.rfind(" ")
                    if k != -1 and k > 20:
                        cut = len(piece) - len(window) + k + 1
                if cut is not None and cut > 0:
                    piece = piece[:cut]
                    j = i + cut
            piece = piece.strip()
            if piece:
                chunks.append(piece)
            i = j

        sr = _pcm_sr(self.output_format)
        gap_ms = int(getattr(self, "tts_chunk_silence_ms", 40) or 40)
        if gap_ms < 0:
            gap_ms = 0
        gap_samples = int(sr * (gap_ms / 1000.0))
        gap = (b"\x00\x00" * gap_samples) if gap_samples > 0 else b""

        pcm_parts: List[bytes] = []
        for idx, c in enumerate(chunks):
            pcm_parts.append(self._tts_elevenlabs_pcm(speaker, c, voice_settings_override=voice_settings_override))
            if gap and idx != len(chunks) - 1:
                pcm_parts.append(gap)
        return b"".join(pcm_parts)

    def _cache_path(self, speaker: str, text: str, cache_extra: str = "", voice_settings: Optional[dict] = None, voice_id_override: Optional[str] = None, voice_id: Optional[str] = None) -> Path:
        h = hashlib.sha1()
        account_tag = "fiend" if (speaker or "").upper() == "FIEND" else "bird"
        # Prefer explicit override; else accept legacy voice_id kw; else fall back to speaker default.
        voice_id = str(voice_id_override) if (voice_id_override is not None) else (str(voice_id) if (voice_id is not None) else self._voice_id_for_speaker(speaker))
        vs_str = "" if not voice_settings else json.dumps(voice_settings, sort_keys=True, separators=(",", ":"))
        h.update((account_tag + "\n" + speaker + "\n" + text + "\n" + voice_id + "\n" + self.model_id + "\n" + self.output_format + "\n" + vs_str + "\n" + (cache_extra or "")).encode("utf-8"))
        return self.cache_dir / f"{speaker.lower()}_{h.hexdigest()}.wav"

    def _synthesize_to_wav(self, speaker: str, text: str, post_preset: str = "default", cache_extra: str = "", voice_settings_override: Optional[dict] = None) -> Path:
        """Return a WAV path for this line.

        Resolution order (2026-09-25: ElevenLabs-first):
          1) writable cache_dir (write-through cache of synthesized lines)
          2) online synthesis (ElevenLabs) -> writes into writable cache_dir (if not offline)
          3) bundled voice_cache ONLY if BRATBOX_BUNDLED_VOICE=1 (not shipped by default)
        """
        # Build candidate cache filenames.
        # Important: offline playback should be resilient to small key-drift:
        # - mood tags added/removed (cache_extra)
        # - voice_settings overrides added/removed
        # We therefore try a small set of variants, preferring the most stable key when offline.
        extras: List[str] = []
        settings: List[Optional[dict]] = []

        try:
            if cache_extra is None:
                cache_extra = ""
        except Exception:
            cache_extra = ""

        # Candidate dimensions
        if voice_settings_override is not None:
            settings = [voice_settings_override, None]
        else:
            settings = [None]

        if cache_extra:
            extras = [cache_extra, ""]
        else:
            extras = [""]

        # Prefer stable keys first when offline
        if getattr(self, "offline", False):
            # Try without mood/settings first
            settings = [None] + [s for s in settings if s is not None]
            extras = [""] + [e for e in extras if e]

        # Choose voice-id variants to improve offline cache hit-rate (voice-id drift safe).
        voice_ids: List[str] = []
        try:
            current_vid = self._voice_id_for_speaker(speaker)
        except Exception:
            current_vid = ""

        def _add_vid(v: str) -> None:
            vv = str(v or "").strip()
            if vv and vv not in voice_ids:
                voice_ids.append(vv)

        # Always try the currently-configured voice-id first.
        _add_vid(current_vid)

        # In offline mode, also try canonical/bundled IDs (and legacy defaults) so recorded caches
        # still resolve even if the user's env ids drift.
        if getattr(self, "offline", False):
            try:
                if (speaker or "").upper() == "FIEND":
                    _add_vid(OFFLINE_DEFAULT_FIEND_VOICE_ID)
                    _add_vid(DEFAULT_FIEND_VOICE_ID or "")
                else:
                    _add_vid(OFFLINE_DEFAULT_BIRD_VOICE_ID)
                    _add_vid(DEFAULT_VOICE_ID)
            except Exception:
                pass
        else:
            try:
                if (speaker or "").upper() == "FIEND":
                    _add_vid(DEFAULT_FIEND_VOICE_ID or "")
                else:
                    _add_vid(DEFAULT_VOICE_ID)
            except Exception:
                pass

        if not voice_ids:
            voice_ids = [current_vid] if current_vid else [""]

        # Generate candidate filenames (dedup, preserve order)
        filenames: List[str] = []
        seen: set[str] = set()
        for vid in voice_ids:
            for e in extras:
                for s in settings:
                    try:
                        p = self._cache_path(speaker, text, cache_extra=e, voice_settings=s, voice_id_override=vid)
                        fn = p.name
                        if fn not in seen:
                            seen.add(fn)
                            filenames.append(fn)
                    except Exception:
                        continue

        # Ensure we have at least one filename
        if not filenames:
            out = self._cache_path(speaker, text, cache_extra=cache_extra or "", voice_settings=voice_settings_override)
            filenames = [out.name]

        # 1) Look in bundled cache + writable cache (read-first).
        for d in getattr(self, "cache_search_dirs", []):
            for fn in filenames:
                try:
                    cand = Path(d) / fn
                    if cand.exists() and cand.stat().st_size > 2000:
                        return cand
                except Exception:
                    continue

        # 2) If offline, do not attempt network TTS.
        if getattr(self, "offline", False):
            tried = ", ".join(filenames[:6])
            raise RuntimeError(f"OFFLINE_VOICE_MISSING: {filenames[0]} | tried: {tried}")

        # Primary output path (used for synthesis + writing)
        out = self._cache_path(speaker, text, cache_extra=cache_extra, voice_settings=voice_settings_override)
        filename = out.name

        # 3) Online: synthesize, then write into writable cache.
        pcm = self._tts_elevenlabs_pcm_chunked(speaker, text, voice_settings_override=voice_settings_override)
        if not pcm or len(pcm) < 200:
            raise RuntimeError("ElevenLabs returned empty audio")
        sr = _pcm_sr(self.output_format)
        wav_bytes = _wrap_pcm16le_mono_to_wav(pcm, sr)
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(wav_bytes)
            # boost loudness
            _apply_gain_inplace_wav(out, gain_db=self.voice_gain_db)
        except Exception:
            # If we can't write, still return a temp file so playback can proceed.
            tmp = Path(tempfile.gettempdir()) / filename
            tmp.write_bytes(wav_bytes)
            _apply_gain_inplace_wav(tmp, gain_db=self.voice_gain_db)
            return tmp
        return out

    def _play_wav_blocking(self, wav: Path) -> None:
        # Hard-fail on playback issues
        try:
            winsound.PlaySound(str(wav), winsound.SND_FILENAME)
        except Exception as e:
            raise RuntimeError(f"voice playback failed: {e}")


    def _play_wav_async(self, wav: Path, interrupt: bool = False, is_bark: bool = False) -> None:
        """Play voice asynchronously.

        If pygame mixer is available, uses a small pool of channels to allow overlapping
        barks/lines ("overlapping chaos"). If the pool is full, steals a channel.

        winsound fallback is single-stream (no overlap).
        """
        wav_path = str(wav)
        if getattr(self, "_use_pygame_voice", False):
            try:
                snd = pygame.mixer.Sound(wav_path)
                fade_ms = int(os.environ.get('LOCKKEY_VOICE_FADE_MS', '12') or 12)
                fade_ms = max(0, min(1200, fade_ms))

                # Full lines: use the primary channel and NEVER steal/stop it.
                if not is_bark and getattr(self, "_voice_primary_channel", None) is not None:
                    ch = self._voice_primary_channel
                    # If a previous full line is still speaking, we wait (listen) so we don't cut meaning.
                    max_wait = float(os.environ.get("LOCKKEY_PRIMARY_WAIT_MAX_S", "20") or 20)
                    t0 = time.time()
                    while ch.get_busy() and (time.time() - t0) < max_wait:
                        time.sleep(0.02)
                    try:
                        ch.play(snd, fade_ms=fade_ms,)
                    except Exception:
                        pass
                try:
                    if bool(is_bark) and time.time() < float(getattr(self, '_no_barks_until', 0.0) or 0.0):
                        return
                except Exception:
                    pass

                    return

                # Barks: use bark channels, and if none are free we DROP the bark (no stealing).
                # Less interrupt permission: only allow barks very near the end of a full line.
                try:
                    if getattr(self, "_voice_primary_channel", None) is not None and self._voice_primary_channel.get_busy():
                        endt = float(getattr(self, "_primary_line_end_time", 0.0) or 0.0)
                        win = float(getattr(self, "_bark_preempt_window", 0.18) or 0.18)
                        if endt <= 0.0 or time.time() < (endt - win):
                            return
                except Exception:
                    pass
                bark_channels = getattr(self, "_voice_bark_channels", None) or self._voice_channels
                ch = None
                for c in bark_channels:
                    try:
                        if not c.get_busy():
                            ch = c
                            break
                    except Exception:
                        continue
                if ch is None:
                    # Too much overlap already — skip this bark rather than chopping a real line.
                    return
                ch.play(snd, fade_ms=fade_ms,)
                return
            except Exception:
                # fall through to winsound
                pass

        try:
            if interrupt and (not getattr(self, "voice_overlap_mode", False)):
                winsound.PlaySound(None, winsound.SND_ASYNC)
            winsound.PlaySound(wav_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception as e:
            raise RuntimeError(f"voice playback failed: {e}")


    def stop_voice(self) -> None:
        """Stop voice playback."""
        if getattr(self, "_use_pygame_voice", False):
            for c in self._voice_channels:
                try:
                    c.stop()
                except Exception:
                    pass
        try:
            winsound.PlaySound(None, winsound.SND_ASYNC)
        except Exception:
            pass

    def prepare_and_play(self, speaker: str, text: str, async_play: bool = True, interrupt: bool = False) -> float:
        """Synthesize (or load cached) wav, start playback, return duration seconds."""
        # WotW release contract: the recorded duet belongs exclusively to Idle.
        # Do not let ordinary Ogre Shader/Black Wind/Bratbox calls stack it.
        if (str(os.environ.get("LOCKKEY_IDLE_OGRE_MODE", "") or "").strip().lower() not in ("1", "true", "yes", "on")
                or str(os.environ.get("LOCKKEY_VOICES_ENABLED", "0") or "0").strip().lower() not in ("1", "true", "yes", "on")):
            return 0.0
        raw = str(text or "")
        stage_dirs = _extract_stage_directions(raw)
        # Keep stage directions visible in subtitles, but strip them from the spoken text.
        msg = _strip_stage_directions(raw).strip()
        if not _should_voice_text(str(speaker), msg):
            return 0.0
        self._stat_inc("lines_total", 1)
        tts_speaker, post_preset = self._map_tts_speaker(str(speaker))
        account_tag = "fiend" if (tts_speaker or "").upper() == "FIEND" else "bird"

        # Anti-stack: per-speaker cooldown + de-dup to prevent repeat dialogue piling up.
        try:
            now_t = time.time()
            sp_u = str(tts_speaker or 'NARRATOR').upper()
            cd_ms = int(os.environ.get('LOCKKEY_VOICE_COOLDOWN_MS', '220') or 220)
            cd_ms = max(0, min(3000, cd_ms))
            until = float(getattr(self, '_cooldown_until_by_speaker', {}).get(sp_u, 0.0) or 0.0)
            if cd_ms > 0 and now_t < until:
                return 0.0
            dedup_s = float(os.environ.get('LOCKKEY_VOICE_DEDUP_S', '2.25') or 2.25)
            last = getattr(self, '_recent_spoken', {}).get(sp_u, None)
            if last and str(last.get('text', '')) == str(msg) and (now_t - float(last.get('t', 0.0) or 0.0)) < dedup_s:
                return 0.0
            # record + arm cooldown
            self._recent_spoken[sp_u] = {'text': str(msg), 't': now_t}
            self._cooldown_until_by_speaker[sp_u] = now_t + (float(cd_ms) / 1000.0)
        except Exception:
            pass


        # Quantum Switchplay: smile-tone clarity.
        # If Birdsong enters an intentional grounded 'bit' lane (narration/aside),
        # prepend a tiny consistent tag ("ahem") once on entry.
        try:
            sp_u = str(tts_speaker or "NARRATOR").upper()
            if sp_u == "BIRDSONG":
                is_bit = _is_grounded_bit(msg, stage_dirs)
                was_bit = bool(self._bit_state_by_speaker.get(sp_u, False))
                if is_bit and not was_bit:
                    msg = ("Ahem. " + msg).strip()
                self._bit_state_by_speaker[sp_u] = bool(is_bit)
                # If a line lands too sharp, soften it organically (without forcing every line into performance).
                if (not is_bit) and _is_sharp_like(msg):
                    # Ensure a clean boundary, then add the softener.
                    if msg and msg[-1] not in ".!?":
                        msg = msg.rstrip() + "."
                    msg = (msg.rstrip() + " Just kidding though.").strip()
        except Exception:
            pass

        # If we already hit quota on this account this session, skip voicing for it.
        if self._quota_blocked.get(account_tag, False) and self.on_quota != "crash":
            return 0.0
        # Count real lines (used for mood-controlled nonverbals).
        try:
            self._line_count_by_speaker[str(tts_speaker or "NARRATOR").upper()] = int(self._line_count_by_speaker.get(str(tts_speaker or "NARRATOR").upper(), 0) or 0) + 1
        except Exception:
            pass

        # Fiend per-line mode: TM -> PC -> BF -> SD (or tag/lock).
        cache_extra = ""
        vs_override = None
        # Closed-box mood profile can override default voice settings for both speakers.
        try:
            mp = get_mood(getattr(self, 'scene_mood_name', 'DUET_TEASE_LOOP'))
        except Exception:
            mp = None

        if account_tag == "fiend":
            try:
                if mp is not None and bool(getattr(mp, 'fiend_microcycle', False)):
                    vs_override, msg, cache_extra = self._select_fiend_voice_settings_for_line(msg)
                else:
                    vs_override = getattr(mp, 'fiend_voice', None) if mp is not None else None
                    cache_extra = f"mood={getattr(self, 'scene_mood_name', 'DUET_TEASE_LOOP')}"
            except Exception:
                vs_override, msg, cache_extra = self._select_fiend_voice_settings_for_line(msg)
        else:
            try:
                if mp is not None and getattr(mp, 'bird_voice', None) is not None:
                    vs_override = getattr(mp, 'bird_voice', None)
                    cache_extra = f"mood={getattr(self, 'scene_mood_name', 'DUET_TEASE_LOOP')}"
            except Exception:
                pass


        
        # OFFLINE cache compatibility:
        # Recorded/bundled WAVs should not require the *exact* mood tag or voice_settings
        # that were used when the cache was generated. By default, offline mode prefers
        # stable lookup keys so more lines resolve.
        if getattr(self, "offline", False):
            try:
                inc_mood = (os.environ.get("LOCKKEY_OFFLINE_INCLUDE_MOOD_CACHE", "") or "").strip().lower() in ("1","true","yes","on")
                use_vs  = (os.environ.get("LOCKKEY_OFFLINE_USE_VOICE_SETTINGS", "") or "").strip().lower() in ("1","true","yes","on")
                if not inc_mood:
                    cache_extra = ""
                if not use_vs:
                    vs_override = None
            except Exception:
                cache_extra = ""
                vs_override = None

# Voice-only mannerisms (laughs/hums/clicks): mostly in voice, never in text.
        # Only for full lines, not for barks.
        try:
            if not _is_bark_like(msg):
                nv = self._maybe_voice_nonverbal(tts_speaker, mp, stage_dirs)
                if nv:
                    msg = (msg.rstrip() + " " + nv).strip()
        except Exception:
            pass

        # Reduce credit burn by truncating very long lines (configurable).
        max_chars = self.max_tts_chars_fiend if account_tag == "fiend" else self.max_tts_chars_bird
        spoken = _shorten_for_tts(msg, max_chars)

        # Micro-breath inside the spoken delivery (no added gap between lines).
        # This is a tiny leading pause that reads as an inhale/lean-in on many voices.
        try:
            if (tts_speaker or "").upper() in ("FIEND", "BIRDSONG") and spoken and spoken[:1].isalnum():
                if random.random() < 0.12:
                    spoken = "... " + spoken
        except Exception:
            pass


        try:
            wav = self._synthesize_to_wav(tts_speaker, spoken, post_preset=post_preset, cache_extra=cache_extra, voice_settings_override=vs_override)
        except RuntimeError as e:
            err = str(e)
            self._last_error = err
            if "ELEVENLABS_QUOTA_EXCEEDED" in err and self.on_quota != "crash":
                self._quota_blocked[account_tag] = True
                return 0.0
            # Offline robustness: no lines left behind.
            if "OFFLINE_VOICE_MISSING" in err:
                self._stat_inc("offline_missing", 1)
                try:
                    # Try to keep momentum: optionally interject a wildcard, then play best-effort line audio.
                    self._maybe_play_wildcard_interjection(tts_speaker or "NARRATOR", mood_name=getattr(self, "scene_mood_name", ""))
                    self._stat_inc("wildcards_used", 1)
                except Exception:
                    pass
                try:
                    alt = self._offline_resolve_best_effort(tts_speaker or "NARRATOR", spoken)
                    if alt is not None:
                        try:
                            mood_name = str(getattr(self, "scene_mood_name", "") or "")
                            intent = self._infer_intent(tts_speaker or "NARRATOR", spoken, mood_name=mood_name)
                            serious = self._is_serious_context(intent, mood_name=mood_name, text=spoken)
                        except Exception:
                            mood_name = str(getattr(self, "scene_mood_name", "") or "")
                            intent = "UNKNOWN"
                            serious = False
                        total = float(self._play_line_directed(alt, tts_speaker or "NARRATOR", spoken, intent=intent, serious=serious, mood_name=mood_name, allow_suffix=True) or 0.0)
                        self._stat_inc("best_effort_used", 1)
                        try:
                            self._note_used_clip(getattr(alt, 'name', str(alt)))
                        except Exception:
                            pass
                        try:
                            if not serious:
                                self._note_motif(tts_speaker or "NARRATOR", intent, getattr(alt, 'name', str(alt)))

                                self._stat_inc("motifs_used", 1)
                        except Exception:
                            pass
                        return float(total or 0.0)
                except Exception:
                    pass
                # Nothing available at all.
                return 0.0
            if self.on_quota == "crash":
                raise
            return 0.0
        dur = wav_duration_seconds(wav)
        # Track end time for the current full line so overlap permission can be conservative.
        try:
            if not _is_bark_like(msg):
                self._primary_line_end_time = time.time() + float(dur or 0.0)
        except Exception:
            pass
        # Balanced Director: play with optional underlay/interrupt + ducking, while obeying serious-beat guards.
        try:
            mood_name = str(getattr(self, "scene_mood_name", "") or "")
            intent = self._infer_intent(tts_speaker or "NARRATOR", spoken, mood_name=mood_name)
            serious = self._is_serious_context(intent, mood_name=mood_name, text=spoken)
        except Exception:
            mood_name = str(getattr(self, "scene_mood_name", "") or "")
            intent = "UNKNOWN"
            serious = False

        total = float(self._play_line_directed(wav, tts_speaker or "NARRATOR", spoken, intent=intent, serious=serious, mood_name=mood_name, allow_suffix=True) or 0.0)

        try:
            self._note_used_clip(getattr(wav, 'name', str(wav)))
        except Exception:
            pass
        try:
            # Remember strong moments as session motifs (recurring favorites).
            if not serious:
                self._note_motif(tts_speaker or "NARRATOR", intent, getattr(wav, 'name', str(wav)))

                self._stat_inc("motifs_used", 1)
        except Exception:
            pass
        try:
            if float(total or 0.0) > 0.0:
                self._stat_inc("lines_voiced", 1)
        except Exception:
            pass
        return float(total or 0.0)


    def _load_voice_tags(self) -> None:
        """Load optional voice tag metadata.

        Supported files (searched in cache dirs):
          - voice_tags.jsonl (one json per line)
          - voice_tags.json  (list[dict] or dict{filename:meta})
        Each entry can include: file, speaker, transcript, tags (list[str]), vibe (dict).
        """
        if getattr(self, "_voice_tags_loaded", False):
            return
        self._voice_tags_loaded = True
        tag_names = ["voice_tags.jsonl", "voice_tags.json"]
        dirs = []
        try:
            dirs = list(getattr(self, "cache_search_dirs", []))
        except Exception:
            dirs = []
        for d in dirs:
            for tn in tag_names:
                p = Path(d) / tn
                if not p.exists():
                    continue
                try:
                    if tn.endswith(".jsonl"):
                        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                            line = line.strip()
                            if not line:
                                continue
                            obj = json.loads(line)
                            fn = (obj.get("file") or obj.get("filename") or "").strip()
                            if fn:
                                self.voice_tags[fn] = obj
                    else:
                        obj = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
                        if isinstance(obj, dict):
                            # dict{filename:meta} OR dict with "items"
                            items = obj.get("items") if isinstance(obj.get("items"), list) else None
                            if items:
                                for it in items:
                                    fn = (it.get("file") or it.get("filename") or "").strip()
                                    if fn:
                                        self.voice_tags[fn] = it
                            else:
                                for fn, meta in obj.items():
                                    if isinstance(meta, dict):
                                        meta = dict(meta)
                                        meta.setdefault("file", fn)
                                        self.voice_tags[str(fn)] = meta
                        elif isinstance(obj, list):
                            for it in obj:
                                if isinstance(it, dict):
                                    fn = (it.get("file") or it.get("filename") or "").strip()
                                    if fn:
                                        self.voice_tags[fn] = it
                except Exception:
                    continue


        # Voice Brain transcript augmentation.  A small voice_tags file must not
        # hide the complete Whisper transcript catalog: merge both sources so
        # the clip-native director can use the full recorded vocabulary.
        try:
            self._load_voice_tags_from_transcripts()
        except Exception:
            pass

    def _load_voice_tags_from_transcripts(self) -> None:
        """Load transcripts_with_speakers.json (generated via Whisper) as voice tag metadata.

        Expected formats:
          - list[{file, speaker, text}]  (preferred)
          - dict with key "rows" or "items" containing such a list
        We also derive lightweight tags to make offline selection feel 'alive' and consistent.
        """
        # Locate transcript file (prefer alongside run.py / voice_engine.py)
        candidates = []
        try:
            here = Path(__file__).resolve().parent
            candidates.append(here / "transcripts_with_speakers.json")
            candidates.append(here / "transcripts.json")
        except Exception:
            pass
        # Also check cache dirs
        try:
            for d in list(getattr(self, "cache_search_dirs", [])):
                candidates.append(Path(d) / "transcripts_with_speakers.json")
                candidates.append(Path(d) / "transcripts.json")
        except Exception:
            pass

        p = None
        for c in candidates:
            try:
                if c and c.exists():
                    p = c
                    break
            except Exception:
                continue
        if p is None:
            return

        raw = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
        if isinstance(raw, dict):
            rows = raw.get("rows") or raw.get("items") or raw.get("data")
        else:
            rows = raw
        if not isinstance(rows, list):
            return

        def _norm(s: str) -> str:
            s = (s or "").strip()
            s = re.sub(r"\s+", " ", s)
            return s

        def _derive_tags(text: str, speaker: str) -> list:
            t = (text or "").lower()
            tags = []
            # Texture / delivery
            if any(x in t for x in ["mm", "mmm", "mhm", "hmm", "uh", "ah", "oh"]):
                tags.append("TEXTURE_MURMUR")
            if any(x in t for x in ["giggle", "hehe", "haha", "laugh"]):
                tags.append("TEXTURE_GIGGLE")
            if any(x in t for x in ["whisper", "hush", "quiet"]):
                tags.append("TEXTURE_HUSH")
            if any(x in t for x in ["pant", "breath", "breathy", "gulp"]):
                tags.append("TEXTURE_BREATHLESS")
            # Consent / steering
            if any(x in t for x in ["wait", "hold on", "slow", "easy", "careful"]):
                tags.append("CONSENT_AMBER")
            if any(x in t for x in ["stop", "no", "don't", "not that"]):
                tags.append("CONSENT_RED")
            if any(x in t for x in ["yes", "okay", "good", "please", "more"]):
                tags.append("CONSENT_GREENISH")
            # Coaching / reassurance
            if any(x in t for x in ["i got you", "you're safe", "safe", "breathe", "trust me", "it's okay", "good girl", "good boy"]):
                tags.append("COACH")
            # Brat / tease / challenge (soft)
            if any(x in t for x in ["baka", "brat", "tease", "tempt", "try me", "oh really"]):
                tags.append("TEASE")
            # Soft affection
            if any(x in t for x in ["sweet", "cute", "love", "mine", "yours", "darling"]):
                tags.append("AFFECTION")
            # Speaker tint
            if str(speaker).lower().startswith("bird"):
                tags.append("SPEAKER_BIRD")
            elif str(speaker).lower().startswith("fiend"):
                tags.append("SPEAKER_FIEND")
            return tags

        # Build filename->meta map
        for r in rows:
            if not isinstance(r, dict):
                continue
            fn = (r.get("file") or r.get("filename") or "").strip()
            if not fn:
                continue
            # Keep only basename so it matches voice cache filenames
            base = os.path.basename(fn).replace("\\", "/").split("/")[-1]
            sp = (r.get("speaker") or "").strip() or ("fiend" if "fiend" in base.lower() else "birdsong" if "bird" in base.lower() else "any")
            tr = _norm(r.get("text") or r.get("transcript") or "")
            if not tr:
                # still keep, but low priority
                tr = ""
            tags = _derive_tags(tr, sp)
            prior = self.voice_tags.get(base, {}) if isinstance(self.voice_tags, dict) else {}
            merged_tags = list(dict.fromkeys([str(x) for x in (prior.get("tags") or []) if x] + tags))
            self.voice_tags[base] = {
                **prior,
                "file": base,
                "speaker": prior.get("speaker") or sp,
                "transcript": prior.get("transcript") or prior.get("text") or tr,
                "tags": merged_tags,
                "source": "%s+%s" % (str(prior.get("source") or "tags"), str(p.name)),
            }

    def _load_director_tag_bundles(self) -> None:
        """Load optional tag bundles for explicit director requests.

        Searched in cache dirs:
          - director_tag_bundles.json  (dict{BUNDLE_NAME: [tags...]})
        """
        if getattr(self, "_tag_bundles_loaded", False):
            return
        self._tag_bundles_loaded = True
        self.tag_bundles = {}
        try:
            dirs = list(getattr(self, "cache_search_dirs", []))
        except Exception:
            dirs = []
        for d in dirs:
            p = Path(d) / "director_tag_bundles.json"
            if not p.exists():
                continue
            try:
                obj = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
                if isinstance(obj, dict):
                    norm = {}
                    for k, v in obj.items():
                        if isinstance(v, list):
                            norm[str(k).strip().upper()] = [str(x).strip().lower() for x in v if str(x).strip()]
                    self.tag_bundles.update(norm)
            except Exception:
                continue

    
    def _read_director_tag_request_obj(self) -> dict:
        """Read a director tag request object (env/file). Returns {"tags":[...], "mode":"blend|override", "bundle":str|None} or {}.

        File schema (voice_tag_request.json), searched in cache dirs:
          {"tags":[...], "mode":"blend|override", "ttl_ms":2500, "ts_ms":..., "nonce":"..."}
          {"bundle":"AFTERGLOW", "mode":"override", "ttl_ms":6000, "ts_ms":..., "nonce":"..."}
        """
        try:
            self._load_director_tag_bundles()
        except Exception:
            pass

        # env direct tags
        try:
            raw = os.environ.get("LOCKKEY_DIRECTOR_TAGS", "") or ""
            if raw.strip():
                tags = [t.strip().lower() for t in re.split(r"[;,]", raw) if t.strip()]
                mode = (os.environ.get("LOCKKEY_TAG_REQUEST_MODE", "blend") or "blend").strip().lower()
                return {"tags": tags, "mode": mode}
        except Exception:
            pass

        # env bundle
        try:
            b = (os.environ.get("LOCKKEY_DIRECTOR_TAG_BUNDLE", "") or "").strip().upper()
            if b:
                tags = list(self.tag_bundles.get(b, [])) if isinstance(getattr(self, "tag_bundles", None), dict) else []
                mode = (os.environ.get("LOCKKEY_TAG_REQUEST_MODE", "blend") or "blend").strip().lower()
                return {"tags": [t for t in tags if t], "mode": mode, "bundle": b}
        except Exception:
            pass

        # file-based request (content/nonce cached, supports ttl)
        try:
            req_name = (os.environ.get("LOCKKEY_DIRECTOR_TAG_REQUEST_FILE", "voice_tag_request.json") or "voice_tag_request.json").strip()
            dirs = []
            try:
                dirs = list(getattr(self, "cache_search_dirs", []))
            except Exception:
                dirs = []
            best_p = None
            for d in dirs:
                p = Path(d) / req_name
                if p.exists():
                    best_p = p
                    break
            if best_p is None:
                return {}

            raw_text = best_p.read_text(encoding="utf-8", errors="ignore")
            # content hash is safer than mtime (Windows granularity)
            h = hashlib.sha1(raw_text.encode("utf-8", errors="ignore")).hexdigest()
            cache = getattr(self, "_tag_request_cache", None)
            if isinstance(cache, dict) and cache.get("hash") == h:
                return dict(cache.get("obj", {}) or {})

            obj = json.loads(raw_text)
            if not isinstance(obj, dict):
                self._tag_request_cache = {"hash": h, "obj": {}}
                return {}

            # ttl gate
            try:
                ttl_ms = int(obj.get("ttl_ms")) if obj.get("ttl_ms") is not None else None
            except Exception:
                ttl_ms = None
            try:
                ts_ms = int(obj.get("ts_ms")) if obj.get("ts_ms") is not None else None
            except Exception:
                ts_ms = None
            if ttl_ms is not None and ts_ms is not None:
                now_ms = int(time.time() * 1000)
                if now_ms > (ts_ms + ttl_ms):
                    self._tag_request_cache = {"hash": h, "obj": {}}
                    return {}

            tags = []
            bundle = None
            if isinstance(obj.get("tags"), list):
                tags = [str(x).strip().lower() for x in obj.get("tags") if str(x).strip()]
            elif isinstance(obj.get("bundle"), str):
                bundle = obj.get("bundle").strip().upper()
                tags = list(self.tag_bundles.get(bundle, [])) if isinstance(getattr(self, "tag_bundles", None), dict) else []

            mode = (str(obj.get("mode") or "")).strip().lower() or (os.environ.get("LOCKKEY_TAG_REQUEST_MODE", "blend") or "blend").strip().lower()
            out = {"tags": [t for t in tags if t], "mode": mode}
            if bundle:
                out["bundle"] = bundle
            self._tag_request_cache = {"hash": h, "obj": out}
            return out
        except Exception:
            return {}

    def _read_director_tag_request(self) -> List[str]:
        obj = self._read_director_tag_request_obj()
        if not isinstance(obj, dict):
            return []
        tags = obj.get("tags") if isinstance(obj.get("tags"), list) else []
        return [str(t).strip().lower() for t in tags if str(t).strip()]


    def _scan_voice_cache(self) -> None:
        """Scan cache dirs for wavs; build per-speaker catalogs for wildcard fallback."""
        if getattr(self, "_scan_voice_cache_loaded", False):
            return
        self._scan_voice_cache_loaded = True
        dirs = []
        try:
            dirs = list(getattr(self, "cache_search_dirs", []))
        except Exception:
            dirs = []
        found_any: List[Path] = []
        for d in dirs:
            try:
                dd = Path(d)
                if not dd.exists():
                    continue
                for p in dd.glob("*.wav"):
                    try:
                        if p.stat().st_size < 2000:
                            continue
                        found_any.append(p)
                        low = p.name.lower()
                        if low.startswith("birdsong_") or low.startswith("bird_"):
                            self.voice_catalog["birdsong"].append(p)
                        elif low.startswith("fiend_"):
                            self.voice_catalog["fiend"].append(p)
                        else:
                            # unknown speaker; still usable as wildcard
                            pass
                    except Exception:
                        continue
            except Exception:
                continue
        self.voice_catalog["any"] = found_any

    def _norm_text(self, s: str) -> str:
        s = str(s or "").lower()
        s = _strip_stage_directions(s)
        s = re.sub(r"[^a-z0-9\s\'\-]", " ", s)
        s = re.sub(r"\s{2,}", " ", s).strip()
        return s

    def _best_transcript_match(self, speaker: str, target_text: str, min_score: float = 0.74) -> Optional[Path]:
        """Find best wav whose transcript best matches target_text, for this speaker."""
        try:
            speaker_key = "fiend" if (speaker or "").upper() == "FIEND" else "birdsong"
            cand = list(self.voice_catalog.get(speaker_key, []))
            if not cand:
                cand = list(self.voice_catalog.get("any", []))
            tgt = self._norm_text(target_text)
            if not tgt:
                return None
            best: Tuple[float, Optional[Path]] = (0.0, None)
            for p in cand:
                meta = self.voice_tags.get(p.name)
                tr = ""
                if isinstance(meta, dict):
                    tr = str(meta.get("transcript") or meta.get("text") or "").strip()
                if not tr:
                    continue
                score = difflib.SequenceMatcher(None, tgt, self._norm_text(tr)).ratio()
                if score > best[0]:
                    best = (score, p)
            if best[1] is not None and best[0] >= min_score:
                return best[1]
        except Exception:
            pass
        return None

    def _choose_wildcard(self, speaker: str, want_tags: Optional[List[str]] = None) -> Optional[Path]:
        """Choose a 'wildcard' wav (babble, tone, interjection). Uses tags if available."""
        speaker_key = "fiend" if (speaker or "").upper() == "FIEND" else "birdsong"
        pool = list(self.voice_catalog.get(speaker_key, [])) or list(self.voice_catalog.get("any", []))
        if not pool:
            return None
        want = [t.lower() for t in (want_tags or []) if t]
        tagged: List[Path] = []
        if want and self.voice_tags:
            for p in pool:
                meta = self.voice_tags.get(p.name) or {}
                tags = meta.get("tags") if isinstance(meta, dict) else None
                if isinstance(tags, list):
                    tags_low = [str(x).lower() for x in tags]
                    if any(w in tags_low for w in want):
                        tagged.append(p)
        # Default wildcard tags
        if not tagged and self.voice_tags:
            for p in pool:
                meta = self.voice_tags.get(p.name) or {}
                tags = meta.get("tags") if isinstance(meta, dict) else None
                if isinstance(tags, list):
                    tags_low = [str(x).lower() for x in tags]
                    if any(t in tags_low for t in ["wild", "wildcard", "babble", "unintelligible", "laugh", "giggle", "hm", "mm"]):
                        tagged.append(p)
        pool2 = tagged or pool
        try:
            return random.choice(pool2)
        except Exception:
            return pool2[0] if pool2 else None

    def _log_fallback(self, payload: Dict[str, Any]) -> None:
        try:
            if os.environ.get("LOCKKEY_VOICE_FALLBACK_LOG", "1").strip() in ("0", "false", "False"):
                return
            # log into writable cache_dir
            logp = Path(self.cache_dir) / "voice_fallback_log.jsonl"
            payload = dict(payload or {})
            payload.setdefault("ts", time.time())
            logp.parent.mkdir(parents=True, exist_ok=True)
            with open(logp, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception:
            pass


    def _stat_inc(self, key: str, n: int = 1) -> None:
        try:
            if not hasattr(self, "_session_stats") or not isinstance(self._session_stats, dict):
                return
            self._session_stats[key] = int(self._session_stats.get(key, 0) or 0) + int(n or 0)
        except Exception:
            pass

    def _write_session_report(self) -> None:
        """Write a small tuning report for this session (safe to delete)."""
        try:
            if not hasattr(self, "_session_stats") or not isinstance(self._session_stats, dict):
                return
            payload = dict(self._session_stats)
            payload["ended_ts"] = time.time()
            payload["runtime_s"] = float(payload["ended_ts"] - float(payload.get("started_ts", payload["ended_ts"])) or 0.0)
            payload["offline"] = bool(getattr(self, "offline", False))
            outp = Path(self.cache_dir) / "voice_session_report.json"
            outp.parent.mkdir(parents=True, exist_ok=True)
            outp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _infer_intent(self, speaker: str, text: str, mood_name: str = "") -> str:
        """Lightweight intent classifier (offline, deterministic)."""
        t = self._norm_text(text or "")
        m = (mood_name or "").upper()
        # Mood overrides intent when strong
        if any(k in m for k in ("AFTERCARE", "LOVE", "FALLEN")):
            return "AFTERCARE"
        if any(k in m for k in ("FRENZY", "EDGE", "OVERDRIVE", "CLIMAX")):
            return "ESCALATE"
        if any(k in m for k in ("GROUND", "STORY")):
            return "GROUND"
        # Text heuristics
        if any(w in t for w in ("breathe", "slow", "it's ok", "its ok", "you're safe", "youre safe", "i'm here", "im here")):
            return "GROUND"
        if any(w in t for w in ("good", "that's it", "thats it", "yes", "keep going", "more")):
            return "AFFIRM"
        if any(w in t for w in ("no", "stop", "wait", "hold")):
            return "DENY"
        if any(w in t for w in ("look", "listen", "come here", "kneel", "do it", "now")):
            return "COMMAND"
        if any(w in t for w in ("tease", "cute", "naughty", "mmm", "mm", "hehe", "haha")):
            return "TEASE"
        if "?" in (text or ""):
            return "OBSERVE"
        return "OBSERVE"

    def _is_serious_context(self, intent: str, mood_name: str = "", text: str = "") -> bool:
        """True if we should avoid comedic wildcards."""
        m = (mood_name or "").upper()
        if any(k in m for k in ("AFTERCARE", "LOVE", "FALLEN", "GROUND")):
            return True
        it = (intent or "").upper()
        if it in ("AFTERCARE", "GROUND"):
            return True
        t = self._norm_text(text or "")
        if any(w in t for w in ("sorry", "are you okay", "are u ok", "i'm sorry", "im sorry", "please", "hurt")):
            return True
        return False

    def _intent_want_tags(self, intent: str, mood_name: str = "") -> List[str]:
        """Map intent/mood to preferred tag palette."""
        it = (intent or "OBSERVE").upper()
        m = (mood_name or "").upper()
        if it in ("AFTERCARE", "GROUND"):
            return ["soft", "breath", "mm", "mhm", "sigh"]
        if it == "COMMAND":
            return ["sharp", "tch", "hm", "command"]
        if it == "TEASE":
            return ["giggle", "laugh", "mm", "tease"]
        # Fiend guardian-lover intents (RhythmDirector): playful devotion without chaos.
        if it == "PROTECT":
            return ["soft", "steady", "care", "protect", "warm", "gentle", "here", "withyou", "mm", "mhm", "yes"]
        if it == "PLAYFUL_SCOLD":
            return ["warm", "tease", "mm", "mhm", "hm", "silly", "rude", "laugh"]
        if it == "DEVOTED_DISBELIEF":
            return ["warm", "mm", "mhm", "laugh", "yes", "good", "breath", "believe"]
        if it == "ESCALATE" or any(k in m for k in ("FRENZY", "EDGE", "OVERDRIVE", "CLIMAX")):
            return ["breath", "laugh", "babble", "wild", "tch"]
        if it == "AFFIRM":
            return ["mm", "mhm", "yes", "good"]
        if it == "DENY":
            return ["no", "wait", "shh"]

        # Gesture / physicality intents (used by RhythmDirector micro-gestures)
        if it in ("PHYSICAL", "GESTURE"):
            return ["breath", "sigh", "mm", "mhm", "lip", "smack", "gulp", "sniff", "moan"]
        if it in ("GESTURE_BREATH", "BREATH"):
            return ["breath", "inhale", "exhale", "sigh", "pant", "mm"]
        if it in ("PUPIL", "GESTURE_PUPIL"):
            # Micro-physical cue: subtle intake / blink / tiny gasp / warm breath.
            return ["breath", "inhale", "blink", "mm", "mhm", "gasp", "smile"]

        if it in ("STEADY_BREATH","STEADY"):
            return ["steady","breath","inhale","exhale","mm","mhm","soft","gentle","care"]
        if it in ("BREATH_HITCH","HITCH"):
            return ["gasp","inhale","breath","hitch","mm","mhm","soft"]
        if it in ("LEANIN","LEAN"):
            return ["breath","whisper","close","mm","mhm","soft","smile"]
        if it in ("POUT",):
            return ["pout","hmph","sigh","mm","mhm","cute","need","breath"]
        if it in ("HAIRFLIP",):
            return ["diva","hmph","tease","laugh","mm","breath","cute"]
        if it in ("LOOKBACK","LOOK_BACK"):
            return ["baka","lookback","glance","hmph","mm","tease","breath"]
        if it in ("TRACE","TOUCH"):
            return ["touch","trace","soft","gentle","mm","mhm","breath","warm"]
        if it in ("GESTURE_MISS", "REACT_MISS"):
            return ["tch", "ugh", "sigh", "breath", "wait", "no"]
        if it in ("GESTURE_PERFECT", "REACT_PERFECT"):
            return ["laugh", "giggle", "yes", "good", "mm", "mhm", "breath"]
        return ["wild", "babble", "laugh"]

    def _recent_penalty(self, filename: str, window_s: float = 45.0) -> float:
        """Penalty in [0,1] if we recently used this clip."""
        try:
            now = time.time()
            for fn, ts in zip(reversed(self._recent_voice_files), reversed(self._recent_voice_ts)):
                if (now - float(ts)) > float(window_s):
                    break
                if fn == filename:
                    # strong penalty if within window
                    return 0.35
        except Exception:
            pass
        return 0.0

    def _note_used_clip(self, filename: str) -> None:
        try:
            now = time.time()
            self._recent_voice_files.append(str(filename))
            self._recent_voice_ts.append(float(now))
            # cap
            if len(self._recent_voice_files) > 80:
                self._recent_voice_files = self._recent_voice_files[-60:]
                self._recent_voice_ts = self._recent_voice_ts[-60:]
        except Exception:
            pass

    
    # -----------------------------
    # Dialogue Director (Balanced)
    # -----------------------------
    def _director_is_disabled(self) -> bool:
        try:
            now = time.time()
            if now < float(getattr(self, "_director_disabled_until", 0.0) or 0.0):
                return True
        except Exception:
            return False
        return False

    def _director_soft_disable(self, seconds: float = 8.0) -> None:
        try:
            self._director_disabled_until = max(float(getattr(self, "_director_disabled_until", 0.0) or 0.0), time.time() + float(seconds or 0.0))
        except Exception:
            pass


    # ─────────────────────────────────────────────────────────────────────
    # Beat gating (Director v1)
    # ─────────────────────────────────────────────────────────────────────
    def tick_music(self, dt: float, bpm: float, beats_per_bar: int = 4) -> None:
        """
        Update internal beat clock. Called from the main game loop.
        Attempts to sync to pygame.mixer.music.get_pos() when available.
        """
        try:
            self._beat_gate_bpm = max(30.0, float(bpm or self._beat_gate_bpm or 120.0))
        except Exception:
            self._beat_gate_bpm = 120.0
        try:
            self.beat_gate_beats_per_bar = max(2, int(beats_per_bar or getattr(self, "beat_gate_beats_per_bar", 4) or 4))
        except Exception:
            self.beat_gate_beats_per_bar = 4

        if not bool(getattr(self, "beat_gate_enabled", True)):
            return

        # Default integrate
        try:
            self._beat_gate_phase += float(dt or 0.0) * (float(self._beat_gate_bpm) / 60.0)
        except Exception:
            pass

        # Optional: hard sync to current music position
        try:
            if pygame is not None:
                ms = pygame.mixer.music.get_pos()
                if isinstance(ms, int) and ms >= 0:
                    ms = int(ms) + int(getattr(self, "beat_gate_offset_ms", 0) or 0)
                    # Only resync if monotonic or first sync
                    if (getattr(self, "_beat_gate_last_music_ms", None) is None) or (ms >= int(self._beat_gate_last_music_ms or 0)):
                        self._beat_gate_last_music_ms = ms
                        self._beat_gate_phase = (float(ms) / 60000.0) * float(self._beat_gate_bpm)
                        self._beat_gate_last_sync_t = time.time()
        except Exception:
            # no hard failure; keep integrated clock
            pass

        # Update beat/bar indices
        try:
            beat_i = int(float(getattr(self, "_beat_gate_phase", 0.0) or 0.0))
            if beat_i != int(getattr(self, "_beat_gate_last_beat_i", 0) or 0):
                self._beat_gate_last_beat_i = beat_i
                bpb = int(getattr(self, "beat_gate_beats_per_bar", 4) or 4)
                if bpb > 0 and (beat_i % bpb) == 0:
                    self._beat_gate_last_bar_i = int(getattr(self, "_beat_gate_last_bar_i", 0) or 0) + 1
        except Exception:
            pass

    def _beat_gate_snapshot(self) -> tuple[int, int, float, float]:
        """Return (beat_in_bar, bar_i, frac_in_beat, sec_per_beat)."""
        bpm = float(getattr(self, "_beat_gate_bpm", 120.0) or 120.0)
        sec_per_beat = 60.0 / max(30.0, bpm)
        phase = float(getattr(self, "_beat_gate_phase", 0.0) or 0.0)
        beat_i = int(phase)
        frac = phase - float(beat_i)
        bpb = int(getattr(self, "beat_gate_beats_per_bar", 4) or 4)
        beat_in_bar = beat_i % max(1, bpb)
        bar_i = int(getattr(self, "_beat_gate_last_bar_i", 0) or 0)
        return beat_in_bar, bar_i, float(frac), float(sec_per_beat)

    def _beat_gate_time_to_next_allowed(self, allow_beats: set[int], *, min_delay: float, max_delay: float) -> float | None:
        """
        Returns seconds until next allowed beat boundary within [min_delay, max_delay].
        If none found, returns None.
        """
        try:
            _, _, frac, spb = self._beat_gate_snapshot()
            bpb = int(getattr(self, "beat_gate_beats_per_bar", 4) or 4)
            # time to next beat boundary
            t_to_next = (1.0 - frac) * spb
            # search forward for up to 2 bars
            accum = t_to_next
            beat_i = int(float(getattr(self, "_beat_gate_phase", 0.0) or 0.0)) + 1
            for _ in range(max(4, bpb * 2)):
                beat_in_bar = beat_i % max(1, bpb)
                if beat_in_bar in allow_beats and accum >= float(min_delay) and accum <= float(max_delay):
                    return float(accum)
                accum += spb
                beat_i += 1
        except Exception:
            return None
        return None
    # ─────────────────────────────────────────────────────────────────────
    # Fill-grid helpers (slot-level rhythmic gating)
    # ─────────────────────────────────────────────────────────────────────
    def _grid_snapshot(self) -> tuple[int, int, float, float, int]:
        """Return (slot_in_bar, bar_i, frac_in_slot, sec_per_slot, slots_per_bar)."""
        try:
            bpm = float(getattr(self, "_beat_gate_bpm", 120.0) or 120.0)
            sec_per_beat = 60.0 / max(30.0, bpm)
            phase = float(getattr(self, "_beat_gate_phase", 0.0) or 0.0)
            beat_i = int(phase)
            frac_beat = phase - float(beat_i)
            bpb = int(getattr(self, "beat_gate_beats_per_bar", 4) or 4)
            slots = int(getattr(self, "fill_grid_slots", 8) or 8)
            if slots < 4:
                slots = 8
            pos_in_bar_beats = (float(beat_i % max(1, bpb)) + float(frac_beat))
            slots_per_beat = float(slots) / float(max(1, bpb))
            pos_in_bar_slots = pos_in_bar_beats * slots_per_beat
            slot_i = int(pos_in_bar_slots) % max(1, slots)
            frac_slot = pos_in_bar_slots - float(int(pos_in_bar_slots))
            bar_i = int(getattr(self, "_beat_gate_last_bar_i", 0) or 0)
            sec_per_slot = float(sec_per_beat) / max(1e-6, float(slots_per_beat))
            return int(slot_i), int(bar_i), float(frac_slot), float(sec_per_slot), int(slots)
        except Exception:
            return (0, int(getattr(self, "_beat_gate_last_bar_i", 0) or 0), 0.0, 0.5, int(getattr(self, "fill_grid_slots", 8) or 8))

    def _grid_pattern_for_role(self, role: str) -> str:
        r = str(role or "wildcard").strip().lower()
        if r in ("murmur","under"):
            r = "underlay"
        if r not in ("prefix","suffix","interrupt","underlay","wildcard"):
            r = "wildcard"
        pats = getattr(self, "fill_grid_patterns", {}) if isinstance(getattr(self, "fill_grid_patterns", None), dict) else {}
        pat = str(pats.get(r, "") or "")
        slots = int(getattr(self, "fill_grid_slots", 8) or 8)
        if len(pat) != slots:
            if len(pat) < slots:
                pat = (pat + ("0" * (slots - len(pat))))[:slots]
            else:
                pat = pat[:slots]
        return pat

    def _grid_allowed_slots(self, role: str) -> set[int]:
        pat = self._grid_pattern_for_role(role)
        allow = set()
        for i,ch in enumerate(pat):
            if ch in ("1","x","X"):
                allow.add(int(i))
        return allow

    def _grid_time_to_next_allowed(self, role: str, *, min_delay: float, max_delay: float) -> tuple[float|None, int|None]:
        """Return (seconds_until, slot_index) for the next allowed slot boundary within window."""
        try:
            allow = self._grid_allowed_slots(role)
            if not allow:
                return (None, None)
            slot_i, _, frac, sps, slots = self._grid_snapshot()
            t_to_next = (1.0 - float(frac)) * float(sps)
            accum = float(t_to_next)
            cur = int(slot_i)
            for step in range(max(8, int(slots)*2)):
                nxt = (cur + 1 + step) % max(1, int(slots))
                if nxt in allow and accum >= float(min_delay) and accum <= float(max_delay):
                    return (float(accum), int(nxt))
                accum += float(sps)
        except Exception:
            return (None, None)
        return (None, None)

    # ─────────────────────────────────────────────────────────────────────
    # Beat motifs (slot-tied motif memory)
    # ─────────────────────────────────────────────────────────────────────
    def _beat_motif_key(self, speaker: str, intent: str, role: str, slot: int) -> Tuple[str, str, str, int]:
        sk = "fiend" if (speaker or "").upper() == "FIEND" else "birdsong"
        it = str(intent or "UNKNOWN").upper()
        rl = str(role or "wildcard").lower()
        if rl in ("murmur","under"):
            rl = "underlay"
        return (sk, it, rl, int(slot))

    def _note_beat_motif(self, speaker: str, intent: str, role: str, slot: int, filename: str) -> None:
        try:
            k = self._beat_motif_key(speaker, intent, role, int(slot))
            fn = str(filename)
            arr = list(self._beat_motif_by_key.get(k, []))
            if fn in arr:
                arr.remove(fn)
            arr.append(fn)
            mx = int(getattr(self, "_motif_max", 6) or 6)
            if len(arr) > mx:
                arr = arr[-mx:]
            self._beat_motif_by_key[k] = arr
        except Exception:
            pass

    def _try_beat_motif(self, speaker: str, intent: str, role: str, slot: int, avoid_tags: Optional[List[str]] = None) -> Optional[Path]:
        """Prefer recurring favorite clips for the same beat-slot (with adjacent-slot forgiveness)."""
        try:
            rate = float(getattr(self, "_beat_motif_rate", 0.0) or 0.0)
            if rate <= 0.0 or random.random() >= rate:
                return None
            avoid = set([str(x).lower() for x in (avoid_tags or []) if x])
            now = time.time()
            slots_per_bar = int(getattr(self, "fill_grid_slots", 8) or 8)
            slot_candidates = [int(slot)]
            if slots_per_bar > 1:
                slot_candidates += [int((slot - 1) % slots_per_bar), int((slot + 1) % slots_per_bar)]
            for sl in slot_candidates:
                k = self._beat_motif_key(speaker, intent, role, int(sl))
                arr = list(self._beat_motif_by_key.get(k, []))
                if not arr:
                    continue
                for fn in reversed(arr):
                    last = float(self._beat_motif_last_used.get(fn, 0.0) or 0.0)
                    if (now - last) < 30.0:
                        continue
                    meta = self.voice_tags.get(fn, {}) if isinstance(getattr(self, "voice_tags", None), dict) else {}
                    tags = meta.get("tags") if isinstance(meta, dict) else None
                    tags = tags if isinstance(tags, list) else []
                    tl = [str(x).lower() for x in tags]
                    if avoid and any(t in avoid for t in tl):
                        continue
                    p = None
                    for base in [getattr(self, "cache_dir", None), getattr(self, "bundled_cache_dir", None)]:
                        if base is None:
                            continue
                        cand = Path(base) / fn
                        if cand.exists():
                            p = cand
                            break
                    if p is None:
                        continue
                    self._beat_motif_last_used[fn] = float(now)
                    return Path(p)
        except Exception:
            return None
        return None

    def _wav_rms(self, wav: Path) -> float:
        """Return RMS amplitude (16-bit scale) for wav, cached."""
        try:
            key = str(getattr(wav, "name", str(wav)))
            if key in self._wav_rms_cache:
                return float(self._wav_rms_cache[key] or 0.0)
            with wave.open(str(wav), 'rb') as wf:
                n = wf.getnframes()
                # read at most ~1.0s worth for speed
                fr = int(min(n, wf.getframerate()))
                data = wf.readframes(fr)
                # width in bytes
                w = wf.getsampwidth()
                rms = float(audioop.rms(data, w) or 0.0) if data else 0.0
            self._wav_rms_cache[key] = float(rms or 0.0)
            return float(rms or 0.0)
        except Exception:
            return 0.0

    def _voice_volume_for_wav(self, wav: Path, role: str = "main") -> float:
        """Compute a per-clip volume multiplier so voice sits in the mix."""
        try:
            base = 1.0
            rms = float(self._wav_rms(wav) or 0.0)
            tgt = float(getattr(self, "_target_voice_rms", 1800.0) or 1800.0)
            mult = 1.0
            if rms > 1.0 and tgt > 1.0:
                mult = tgt / rms
            # apply voice_gain_db as a gentle overall lift
            try:
                db = float(getattr(self, "voice_gain_db", 0.0) or 0.0)
                mult *= (10.0 ** (db / 20.0)) if db else 1.0
            except Exception:
                pass
            # role scaling
            r = (role or "main").lower()
            if r in ("murmur","under","underlay"):
                mult *= 0.28
            elif r in ("interrupt","cutin"):
                mult *= 0.45
            elif r in ("bark","spice"):
                mult *= 0.55
            # clamp (pygame Sound volume is 0..1)
            mult = max(0.15, min(1.0, float(base) * float(mult)))
            return float(mult)
        except Exception:
            return 1.0

    def _duck_music(self, enable: bool) -> None:
        """Lower pygame music volume while a voice line plays, then restore."""
        if pygame is None:
            return
        if not getattr(self, "_use_pygame_voice", False):
            return
        try:
            if enable:
                try:
                    prev = pygame.mixer.music.get_volume()
                    self._music_prev_volume = float(prev)
                except Exception:
                    self._music_prev_volume = None
                prevv = float(self._music_prev_volume if self._music_prev_volume is not None else 1.0)
                factor = float(getattr(self, "_music_duck_factor", 0.72) or 0.72)
                pygame.mixer.music.set_volume(max(0.0, min(1.0, prevv * factor)))
            else:
                if self._music_prev_volume is None:
                    return
                pygame.mixer.music.set_volume(max(0.0, min(1.0, float(self._music_prev_volume))))
        except Exception:
            return

    def _motif_key(self, speaker: str, intent: str) -> Tuple[str, str]:
        sk = "fiend" if (speaker or "").upper() == "FIEND" else "birdsong"
        it = str(intent or "UNKNOWN").upper()
        return (sk, it)

    def _note_motif(self, speaker: str, intent: str, filename: str) -> None:
        """Remember a clip as a session motif for this speaker+intent."""
        try:
            k = self._motif_key(speaker, intent)
            fn = str(filename)
            arr = list(self._motif_by_key.get(k, []))
            if fn in arr:
                arr.remove(fn)
            arr.append(fn)
            mx = int(getattr(self, "_motif_max", 6) or 6)
            if len(arr) > mx:
                arr = arr[-mx:]
            self._motif_by_key[k] = arr
        except Exception:
            pass

    def _try_motif(self, speaker: str, intent: str, avoid_tags: Optional[List[str]] = None) -> Optional[Path]:
        """Occasionally reuse a remembered motif clip (recurring favorite)."""
        try:
            rate = float(getattr(self, "_motif_rate", 0.0) or 0.0)
            if rate <= 0.0 or random.random() >= rate:
                return None
            k = self._motif_key(speaker, intent)
            arr = list(self._motif_by_key.get(k, []))
            if not arr:
                return None
            avoid = set([str(x).lower() for x in (avoid_tags or []) if x])
            # choose most recent that isn't too recent
            now = time.time()
            for fn in reversed(arr):
                last = float(self._motif_last_used.get(fn, 0.0) or 0.0)
                if (now - last) < 35.0:
                    continue
                # if tags exist, honor avoid
                meta = self.voice_tags.get(fn, {}) if isinstance(self.voice_tags, dict) else {}
                tags = meta.get("tags") if isinstance(meta, dict) else None
                tags = tags if isinstance(tags, list) else []
                tl = [str(x).lower() for x in tags]
                if avoid and any(t in avoid for t in tl):
                    continue
                # locate file in cache search dirs
                for d in getattr(self, "cache_search_dirs", []):
                    p = Path(d) / fn
                    if p.exists():
                        self._motif_last_used[fn] = now
                        return p
            return None
        except Exception:
            return None

    def _choose_underlay(self, speaker: str, intent: str, serious: bool, mood_name: str = "", target_slot: Optional[int] = None) -> Optional[Path]:
        """Pick a low-volume murmur/breath underlay (other speaker), only when safe."""
        if serious:
            return None
        # only allow underlays in non-serious escalation/tease/observe lanes
        it = str(intent or "").upper()
        if it not in ("TEASE","ESCALATE","OBSERVE","AFFIRM"):
            return None
        if random.random() >= float(getattr(self, "_murmur_rate", 0.0) or 0.0):
            return None
        other = "FIEND" if (speaker or "").upper() != "FIEND" else "BIRDSONG"
        want = ["murmur","under","underlay","breath","mm","mhm","soft"]
        avoid = ["laugh","giggle","wild","babble","tch"]
        # Beat motif preference: reuse recurring underlay on the same rhythmic slot when possible.
        if target_slot is not None:
            try:
                m = self._try_beat_motif(other, intent, "underlay", int(target_slot), avoid_tags=avoid)
                if m is not None:
                    return m
            except Exception:
                pass
        return self._choose_wildcard_role(other, role="murmur", want_tags=want, avoid_tags=avoid)

    def _choose_interrupt(self, speaker: str, intent: str, serious: bool, mood_name: str = "", target_slot: Optional[int] = None) -> Optional[Path]:
        """Pick a cut-in interrupt clip (other speaker), only in non-serious escalation."""
        if serious:
            return None
        it = str(intent or "").upper()
        if it not in ("ESCALATE","TEASE"):
            return None
        if random.random() >= float(getattr(self, "_interrupt_rate", 0.0) or 0.0):
            return None
        other = "FIEND" if (speaker or "").upper() != "FIEND" else "BIRDSONG"
        want = ["interrupt","cutin","wait","no","hey","shh"]
        avoid = ["aftercare","ground","soft"]
        # Beat motif preference: reuse recurring interrupt on the same rhythmic slot when possible.
        if target_slot is not None:
            try:
                m = self._try_beat_motif(other, intent, "interrupt", int(target_slot), avoid_tags=avoid)
                if m is not None:
                    return m
            except Exception:
                pass
        p = self._choose_wildcard_role(other, role="interrupt", want_tags=want, avoid_tags=avoid)
        if p is None:
            # fallback to a short prefix-type clip from the other speaker
            p = self._choose_wildcard_role(other, role="prefix", want_tags=["hey","wait","breath","mm"], avoid_tags=avoid)
        return p

    def _play_line_directed(self, wav: Path, speaker: str, spoken: str, intent: str, serious: bool, mood_name: str = "", allow_suffix: bool = True) -> float:
        """Play a full line with balanced director rules: ducking + optional underlay + optional cut-in."""
        # Question/flow guard: keep questions clean (no underlay/interrupt), and block barks briefly.
        try:
            if '?' in str(spoken or ''):
                serious = True
                d_q = float(wav_duration_seconds(wav) or 0.0)
                self._no_barks_until = max(float(getattr(self, '_no_barks_until', 0.0) or 0.0), time.time() + max(0.9, d_q * 0.85))
        except Exception:
            pass
        try:
            fade_ms = int(os.environ.get('LOCKKEY_VOICE_FADE_MS', '12') or 12)
            fade_ms = max(0, min(1200, fade_ms))
        except Exception:
            fade_ms = 12

        # If director is disabled (fragile shutdown) or serious, play cleanly.
        if self._director_is_disabled() or serious:
            d = float(wav_duration_seconds(wav) or 0.0)
            self._duck_music(True)
            self._play_wav_blocking(wav) if not getattr(self, "_use_pygame_voice", False) else self._play_wav_blocking_pygame(wav, role="main")
            self._duck_music(False)
            extra = 0.0
            if allow_suffix and (not serious):
                try:
                    extra = float(self._maybe_play_suffix_interjection(speaker, mood_name=mood_name, text=spoken) or 0.0)
                    if float(extra or 0.0) > 0.0:
                        self._stat_inc("suffix_used", 1)
                except Exception:
                    extra = 0.0
            return float((d or 0.0) + (extra or 0.0))

        # pygame backend: do true overlaps/interrupts
        if getattr(self, "_use_pygame_voice", False) and pygame is not None:
            try:
                primary = pygame.mixer.Sound(str(wav))
                vol = float(self._voice_volume_for_wav(wav, role="main") or 1.0)
                primary.set_volume(vol)

                ch_main = getattr(self, "_voice_primary_channel", None) or pygame.mixer.find_channel(True)
                ch_murmur = getattr(self, "_voice_murmur_channel", None)
                ch_intr = getattr(self, "_voice_interrupt_channel", None)
                if ch_intr is None:
                    # fallback to any bark channel
                    b = getattr(self, "_voice_bark_channels", []) or []
                    ch_intr = b[0] if b else None

                # Select optional underlay + interrupt (after computing target slots)
                under = None
                intr = None
                under_slot = None
                intr_slot = None

                # Duck music while main plays
                self._duck_music(True)

                # Start main
                try:
                    ch_main.play(primary, fade_ms=fade_ms)
                except Exception:
                    ch_main.play(primary, fade_ms=fade_ms)

                t0 = time.time()
                fired_under = False
                fired_intr = False
                # schedule times
                dur = float(wav_duration_seconds(wav) or 0.0)
                # schedule times (beat-gated)
                dur = float(wav_duration_seconds(wav) or 0.0)
                under_base = float(min(0.65, max(0.20, dur * 0.22)))
                intr_base  = float(min(0.85, max(0.22, dur * 0.28)))

                under_at = t0 + under_base
                intr_at  = t0 + intr_base

                # Beat gating: align extra events to musical beats without breaking seriousness rules.
                try:
                    if bool(getattr(self, "beat_gate_enabled", True)):
                        # Underlay: prefer offbeats (2&4 -> indices 1&3)
                        dt_u = self._beat_gate_time_to_next_allowed({1, 3}, min_delay=0.12, max_delay=min(0.75, max(0.25, dur * 0.55)))
                        if dt_u is not None:
                            under_at = t0 + float(dt_u)
                        # Interrupt: prefer downbeats (1&3 -> indices 0&2), only if it can happen early enough
                        dt_i = self._beat_gate_time_to_next_allowed({0, 2}, min_delay=0.16, max_delay=min(0.85, max(0.30, dur * 0.65)))
                        if dt_i is not None:
                            intr_at = t0 + float(dt_i)
                except Exception:
                    pass

                while ch_main.get_busy():
                    now = time.time()
                    if under is not None and (not fired_under) and ch_murmur is not None and now >= under_at:
                        try:
                            snd_u = pygame.mixer.Sound(str(under))
                            snd_u.set_volume(float(self._voice_volume_for_wav(under, role="murmur") or 0.25))
                            ch_murmur.play(snd_u, fade_ms=45)
                        except Exception:
                            pass
                        fired_under = True
                        self._stat_inc("underlays_used", 1)
                        try:
                            if under_slot is not None and under is not None:
                                other_sp = ("FIEND" if (speaker or "").upper() != "FIEND" else "BIRDSONG")
                                self._note_beat_motif(other_sp, intent, "underlay", int(under_slot), under.name)
                                self._stat_inc("motifs_used", 1)
                        except Exception:
                            pass
                    if intr is not None and (not fired_intr) and ch_intr is not None and now >= intr_at:
                        try:
                            snd_i = pygame.mixer.Sound(str(intr))
                            snd_i.set_volume(float(self._voice_volume_for_wav(intr, role="interrupt") or 0.35))
                            ch_intr.play(snd_i, fade_ms=20)
                        except Exception:
                            pass
                        fired_intr = True
                        self._stat_inc("interrupts_used", 1)
                        try:
                            if intr_slot is not None and intr is not None:
                                other_sp = ("FIEND" if (speaker or "").upper() != "FIEND" else "BIRDSONG")
                                self._note_beat_motif(other_sp, intent, "interrupt", int(intr_slot), intr.name)
                                self._stat_inc("motifs_used", 1)
                        except Exception:
                            pass
                    time.sleep(0.02)

                # stop underlay if still playing
                try:
                    if ch_murmur is not None and ch_murmur.get_busy():
                        ch_murmur.fadeout(80)
                except Exception:
                    pass
                try:
                    if ch_intr is not None and ch_intr.get_busy():
                        ch_intr.fadeout(60)
                except Exception:
                    pass

                self._duck_music(False)

                extra = 0.0
                if allow_suffix and (not serious):
                    try:
                        extra = float(self._maybe_play_suffix_interjection(speaker, mood_name=mood_name, text=spoken) or 0.0)
                        if float(extra or 0.0) > 0.0:
                            self._stat_inc("suffix_used", 1)
                    except Exception:
                        extra = 0.0
                return float((dur or 0.0) + (extra or 0.0))
            except Exception:
                # fragile: if anything goes wrong, shut director down temporarily
                self._director_soft_disable(float(getattr(self, "_director_shutdown_s", 12) or 12))
                self._stat_inc("director_soft_shutdowns", 1)
                try:
                    self._duck_music(False)
                except Exception:
                    pass
                d = float(wav_duration_seconds(wav) or 0.0)
                self._play_wav_blocking(wav)
                return float(d or 0.0)

        # winsound backend: no true overlap; keep it clean
        d = float(wav_duration_seconds(wav) or 0.0)
        self._play_wav_blocking(wav)
        extra = 0.0
        if allow_suffix and (not serious):
            try:
                extra = float(self._maybe_play_suffix_interjection(speaker, mood_name=mood_name, text=spoken) or 0.0)
                if float(extra or 0.0) > 0.0:
                    self._stat_inc("suffix_used", 1)
            except Exception:
                extra = 0.0
        return float((d or 0.0) + (extra or 0.0))

    def _play_wav_blocking_pygame(self, wav: Path, role: str = "main") -> None:
        """Blocking playback using pygame channel (enables ducking/levels)."""
        if pygame is None:
            self._play_wav_blocking(wav)
            return
        try:
            snd = pygame.mixer.Sound(str(wav))
            snd.set_volume(float(self._voice_volume_for_wav(wav, role=role) or 1.0))
            ch = getattr(self, "_voice_primary_channel", None) or pygame.mixer.find_channel(True)
            # Fade-in ms (0 = none). Keep defined even if env var missing.
            try:
                fade_ms = int(os.environ.get('LOCKKEY_VOICE_FADE_MS', '12') or 12)
            except Exception:
                fade_ms = 12
            fade_ms = max(0, min(250, int(fade_ms)))
            if fade_ms <= 0:
                ch.play(snd)
            else:
                ch.play(snd, fade_ms=fade_ms)
            while ch.get_busy():
                time.sleep(0.02)
        except Exception as e:
            raise RuntimeError(f"voice playback failed: {e}")

    def _choose_wildcard_role(self, speaker: str, role: str, want_tags: Optional[List[str]] = None, avoid_tags: Optional[List[str]] = None, max_duration_s: Optional[float] = None) -> Optional[Path]:
        """Choose a wildcard clip with role-aware tag preferences."""
        want = [t.lower() for t in (want_tags or []) if t]
        avoid = set([t.lower() for t in (avoid_tags or []) if t])
        # If we have tags, filter manually for avoid + role
        speaker_key = "fiend" if (speaker or "").upper() == "FIEND" else "birdsong"
        pool = list(self.voice_catalog.get(speaker_key, [])) or list(self.voice_catalog.get("any", []))
        if not pool:
            return None
        role = (role or "").lower()
        def role_ok(meta_tags: List[str]) -> bool:
            if not role:
                return True
            tags = [x.lower() for x in (meta_tags or [])]
            if role in tags:
                return True
            # heuristic roles
            if role == "prefix" and any(x in tags for x in ("breath","inhale","ahem","hey","soft")):
                return True
            if role == "suffix" and any(x in tags for x in ("sigh","giggle","laugh","mm","mhm")):
                return True
            return False

        candidates: List[Path] = []
        for p in pool:
            meta = self.voice_tags.get(p.name, {}) if isinstance(self.voice_tags, dict) else {}
            tags = meta.get("tags") if isinstance(meta, dict) else None
            tags = tags if isinstance(tags, list) else []
            tl = [str(x).lower() for x in tags]
            if avoid and any(t in avoid for t in tl):
                continue
            if not role_ok(tl):
                continue
            # Gesture/physicality should stay snappy: optionally filter by duration.
            if max_duration_s is not None:
                try:
                    if not hasattr(self, "_wav_dur_cache"):
                        self._wav_dur_cache = {}
                    dur = self._wav_dur_cache.get(p.name)
                    if dur is None:
                        dur = float(wav_duration_seconds(p) or 0.0)
                        self._wav_dur_cache[p.name] = float(dur)
                    if float(dur or 0.0) > float(max_duration_s):
                        continue
                except Exception:
                    pass
            if want and not any(t in tl for t in want):
                continue
            candidates.append(p)
        if not candidates:
            # fall back to existing chooser without avoid/role
            return self._choose_wildcard(speaker, want_tags=want_tags)
        return random.choice(candidates)


    # ─────────────────────────────────────────────────────────────────────
    # RhythmDirector support (radio-play voice events)
    # ─────────────────────────────────────────────────────────────────────
    def _choose_main_by_intent(
        self,
        speaker: str,
        intent: str,
        want_tags: Optional[List[str]] = None,
        avoid_tags: Optional[List[str]] = None,
        *,
        coh_hint_text: str = "",
        coh_anchor_words: Optional[List[str]] = None,
        coh_prob: Optional[float] = None,
        coh_weight: Optional[float] = None,
        transcript_prefer_p: Optional[float] = None,
    ) -> Optional[Path]:
        """Prefer transcript-bearing clips that match the current intent (vibes-first).

        This is used by RhythmDirector so it can run without authored text.
        """
        speaker_key = "fiend" if (speaker or "").upper() == "FIEND" else "birdsong"
        pool = list(self.voice_catalog.get(speaker_key, [])) or list(self.voice_catalog.get("any", []))
        if not pool:
            return None

        want = [str(x).lower() for x in (want_tags or []) if x]
        avoid = set([str(x).lower() for x in (avoid_tags or []) if x])

        def _tok(s: str) -> List[str]:
            s = (s or "").lower()
            out: List[str] = []
            cur = []
            for ch in s:
                if ch.isalpha():
                    cur.append(ch)
                else:
                    if cur:
                        w = "".join(cur)
                        cur = []
                        if len(w) >= 3:
                            out.append(w)
            if cur:
                w = "".join(cur)
                if len(w) >= 3:
                    out.append(w)
            # very small stoplist (keep it cheap; this is a tie-breaker)
            stop = {"the","and","but","for","you","your","with","that","this","was","are","have","not","just","like","what","can","cant","dont","did","him","her","she","he","they","them","yeah","okay","ok","huh","mmm"}
            return [w for w in out if w not in stop]

        hint_tokens = set(_tok(str(coh_hint_text or "")))
        anchor_tokens = set(_tok(" ".join([str(x) for x in (coh_anchor_words or []) if x])))
        # Soft 80/20 coherence: only used as an occasional tie-breaker.
        try:
            if coh_prob is None:
                coh_prob = float(os.environ.get("LOCKKEY_COHERENCE_PROB", "0.20") or 0.20)
        except Exception:
            coh_prob = 0.20
        try:
            if coh_weight is None:
                coh_weight = float(os.environ.get("LOCKKEY_COHERENCE_WEIGHT", "0.35") or 0.35)
        except Exception:
            coh_weight = 0.35
        try:
            if transcript_prefer_p is None:
                transcript_prefer_p = float(os.environ.get("LOCKKEY_MAIN_TRANSCRIPT_PREFER", "0.60") or 0.60)
        except Exception:
            transcript_prefer_p = 0.60

        # Prefer intelligible mains most of the time, but allow a little wildness.
        only_transcripts = False
        if hint_tokens or anchor_tokens:
            only_transcripts = (random.random() < float(transcript_prefer_p or 0.60))

        best_score = -1.0
        best: Optional[Path] = None
        best_any_score = -1.0
        best_any: Optional[Path] = None
        for p in pool:
            meta = self.voice_tags.get(p.name, {}) if isinstance(getattr(self, "voice_tags", None), dict) else {}
            tr = ""
            tags: List[str] = []
            if isinstance(meta, dict):
                tr = str(meta.get("transcript") or meta.get("text") or "").strip()
                tg = meta.get("tags")
                if isinstance(tg, list):
                    tags = [str(x).lower() for x in tg]

            # avoid disallowed tags
            if avoid and any(a in tags for a in avoid):
                continue

            # Prefer intelligible clips for "main" by requiring some transcript unless the catalog is sparse.
            has_tr = 1.0 if tr else 0.0
            if only_transcripts and not tr:
                continue

            overlap = 0.0
            if want and tags:
                overlap = float(len(set(want) & set(tags))) / float(max(1, len(set(want))))

            # Fiend smoothing: bias harder toward intelligible, "meant" mains.
            # Protector/guardian tweak: prefer transcript-bearing clips slightly more than tag overlap.
            if (speaker_key == "fiend") and ((os.environ.get("LOCKKEY_FIEND_SMOOTH","1") or "1").strip().lower() in ("1","true","yes","on")):
                score = (0.48 * overlap) + (0.50 * has_tr)
            else:
                score = (0.62 * overlap) + (0.28 * has_tr)
            score -= float(self._recent_penalty(p.name) or 0.0)

            # 80/20 coherence tie-breaker:
            # If we have any hint tokens (partner just said something intelligible),
            # add a small boost to candidates whose transcript shares content words.
            if (hint_tokens or anchor_tokens) and (random.random() < float(coh_prob or 0.20)):
                try:
                    cand_tokens = set(_tok(tr)) if tr else set()
                    resp_overlap = 0.0
                    if hint_tokens and cand_tokens:
                        resp_overlap = float(len(hint_tokens & cand_tokens)) / float(max(1, len(hint_tokens)))
                    anch_overlap = 0.0
                    if anchor_tokens and cand_tokens:
                        anch_overlap = float(len(anchor_tokens & cand_tokens)) / float(max(1, len(anchor_tokens)))
                    coh = (0.70 * resp_overlap) + (0.30 * anch_overlap)
                    score += float(coh_weight or 0.35) * float(coh)
                except Exception:
                    pass

            # Track best-any for fallback when transcript preference filtered too hard.
            if score > best_any_score:
                best_any_score = score
                best_any = p
            if score > best_score:
                best_score = score
                best = p

        # If transcript preference filtered everything out, fall back to best-any.
        if best is None and best_any is not None:
            best = best_any

        # If we still didn't find anything, fall back to any role-aware wildcard.
        if best is None:
            return self._choose_wildcard_role(speaker, role="any", want_tags=want_tags, avoid_tags=avoid_tags)
        return best


    def prepare_selected_recording(self, path, *, speaker: str = "", role: str = "main") -> Dict[str, Any]:
        """Decode one director-selected WAV without touching mixer channels.

        Idle Voice Brain calls this on its private worker so disk I/O, RMS
        normalization, and WAV decoding cannot stall rhythm rendering.
        """
        try:
            p = Path(path).resolve()
            allowed = {Path(x).resolve() for values in (getattr(self, "voice_catalog", {}) or {}).values() for x in (values or [])}
            if p not in allowed or not p.is_file():
                return {"clip": None, "duration": 0.0, "error": "unapproved clip"}
            meta = self.voice_tags.get(p.name, {}) if isinstance(getattr(self, "voice_tags", None), dict) else {}
            transcript = str(meta.get("transcript") or meta.get("text") or "").strip() or None
            tags = [str(x) for x in (meta.get("tags") or []) if x]
            duration_s = float(wav_duration_seconds(p) or 0.0)
            sound = None
            if pygame is not None:
                sound = pygame.mixer.Sound(str(p))
                sound.set_volume(float(self._voice_volume_for_wav(p, role=role) or 1.0))
            return {"clip": p.name, "path": p, "sound": sound, "transcript": transcript,
                    "tags": tags, "duration": duration_s, "speaker": speaker, "role": role}
        except Exception as exc:
            return {"clip": None, "duration": 0.0, "error": str(exc)}


    def play_prepared_recording(self, prepared: Dict[str, Any], *, async_play: bool = True) -> Dict[str, Any]:
        """Commit an already-decoded recording; this path performs no disk I/O."""
        if (str(os.environ.get("LOCKKEY_IDLE_OGRE_MODE", "") or "").strip().lower() not in ("1", "true", "yes", "on")
                or str(os.environ.get("LOCKKEY_VOICES_ENABLED", "0") or "0").strip().lower() not in ("1", "true", "yes", "on")):
            return {"clip": None, "transcript": None, "tags": [], "duration": 0.0}
        if not isinstance(prepared, dict) or not prepared.get("clip"):
            return {"clip": None, "transcript": None, "tags": [], "duration": 0.0}
        p = Path(prepared.get("path"))
        duration_s = float(prepared.get("duration", 0.0) or 0.0)
        try:
            if pygame is None:
                if async_play:
                    return {**prepared, "not_played": True}
                self._play_wav_blocking(p)
            else:
                ch = getattr(self, "_voice_primary_channel", None)
                if ch is None or ch.get_busy():
                    return {"clip": None, "transcript": None, "tags": [], "duration": 0.0, "busy": True}
                sound = prepared.get("sound")
                if sound is None:
                    return {"clip": None, "transcript": None, "tags": [], "duration": 0.0, "error": "clip was not decoded"}
                ch.play(sound, fade_ms=45)
            self._note_used_clip(p.name)
            self._primary_line_end_time = max(float(getattr(self, "_primary_line_end_time", 0.0) or 0.0), time.time() + duration_s)
            return {k: v for k, v in prepared.items() if k != "sound"}
        except Exception as exc:
            return {"clip": None, "transcript": None, "tags": [], "duration": 0.0, "error": str(exc)}


    def play_selected_recording(
        self,
        path,
        *,
        speaker: str = "",
        role: str = "main",
        async_play: bool = True,
    ) -> Dict[str, Any]:
        """Play a clip already selected by the clip-native Idle Voice Brain.

        Selection and playback are deliberately separate: this method never
        substitutes a different WAV, which keeps the heard conversation equal
        to the director's transcript/compatibility decision.
        """
        if (str(os.environ.get("LOCKKEY_IDLE_OGRE_MODE", "") or "").strip().lower() not in ("1", "true", "yes", "on")
                or str(os.environ.get("LOCKKEY_VOICES_ENABLED", "0") or "0").strip().lower() not in ("1", "true", "yes", "on")):
            return {"clip": None, "transcript": None, "tags": [], "duration": 0.0}
        prepared = self.prepare_selected_recording(path, speaker=speaker, role=role)
        return self.play_prepared_recording(prepared, async_play=async_play)


    def play_role_event(
        self,
        speaker: str,
        *,
        role: str = "main",
        intent: str = "OBSERVE",
        slot: Optional[int] = None,
        mood_name: str = "",
        serious: bool = False,
        async_play: bool = True,
        # Coherence hints (optional): used to make call/response feel like they're about the same thing
        # without locking into transcript-authored routes.
        coh_hint_text: str = "",
        coh_anchor_words: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Play a short role-coded clip without authored text (used by RhythmDirector).

        Returns a dict with clip metadata for logging.
        Never raises.
        """
        if (str(os.environ.get("LOCKKEY_IDLE_OGRE_MODE", "") or "").strip().lower() not in ("1", "true", "yes", "on")
                or str(os.environ.get("LOCKKEY_VOICES_ENABLED", "0") or "0").strip().lower() not in ("1", "true", "yes", "on")):
            return {"clip": None, "transcript": None, "tags": []}
        try:
            if self._director_is_disabled():
                return {"clip": None, "transcript": None, "tags": []}
        except Exception:
            return {"clip": None, "transcript": None, "tags": []}

        rl = str(role or "main").strip().lower()
        orig_role = rl
        gesture_mode = orig_role in ("gesture", "react", "reaction")
        if rl in ("under", "underlay"):
            rl = "murmur"
        if rl in ("line", "dialogue"):
            rl = "main"

        if gesture_mode:
            rl = "murmur"

        want = []
        avoid = []
        try:
            want = list(self._intent_want_tags(str(intent or "OBSERVE"), mood_name=str(mood_name or "")))
        except Exception:
            want = []
        if serious:
            avoid = ["laugh", "giggle", "babble", "wild", "tch", "scream", "shriek"]
        # Canonical Fiend smoothing: avoid performative/noisy tags even when not in "serious" mode.
        fiend_smooth_on = False
        try:
            fiend_smooth_on = ((os.environ.get("LOCKKEY_FIEND_SMOOTH","1") or "1").strip().lower() in ("1","true","yes","on")) and ("FIEND" in str(speaker or "").upper())
            if fiend_smooth_on:
                avoid = list(avoid or [])
                # Canonical Fiend smoothing: avoid chaotic textures. Keep "laugh" available so
                # guardian-lover can still express warm disbelief when safe.
                for t in ("babble","wild","giggle","shriek","scream","tch"):
                    if t not in avoid:
                        avoid.append(t)
        except Exception:
            fiend_smooth_on = False

        # Protector/guardian Fiend: bias toward "meant it" warmth even outside strict "serious" arcs.
        # Guardian style 2 = playful devotion (lover warmth + gentle disbelief), still not chaotic.
        try:
            if fiend_smooth_on:
                it = str(intent or "OBSERVE").upper()
                style = str(os.environ.get("LOCKKEY_FIEND_GUARDIAN_STYLE", "2") or "2").strip().lower()

                guardian_core = ["tender","care","protect","steady","warm","gentle","here","withyou"]
                lover_spice = ["silly","rude","believe","ofcourse","mm","mhm","yes","good","breath"]

                if style in ("2","playful","playful_devotion","lover","warm"):
                    # Intent-specific palettes that feel "meant" but affectionate.
                    if it in ("PLAYFUL_SCOLD","DEVOTED_DISBELIEF"):
                        want = list(dict.fromkeys(["warm","tease","mm","mhm","silly","rude","believe","breath"] + list(want or [])))
                    elif it in ("TEASE",):
                        want = list(dict.fromkeys(guardian_core + lover_spice + list(want or [])))
                    elif it in ("COMMAND","ESCALATE","FRENZY"):
                        # Reframe heat as protective devotion.
                        want = ["soft","steady","care","protect","warm","gentle","here","withyou","mm","mhm","yes","good","breath"]
                    else:
                        want = list(dict.fromkeys(guardian_core + list(want or [])))

                    # Avoid harsh / chaotic textures, but don't ban mild warmth.
                    avoid = list(avoid or [])
                    for t in ("sharp","command","babble","wild","tch","scream","shriek"):
                        if t not in avoid:
                            avoid.append(t)
                    # Keep giggle mostly out for Fiend to avoid "performing".
                    if "giggle" not in avoid:
                        avoid.append("giggle")
                else:
                    # Fallback guardian (older behavior): more grounded, less playful.
                    want = list(dict.fromkeys(guardian_core + list(want or [])))
                    avoid = list(avoid or [])
                    for t in ("sharp","command","tease","giggle","laugh","babble","wild","tch","scream","shriek"):
                        if t not in avoid:
                            avoid.append(t)
        except Exception:
            pass


        p: Optional[Path] = None
        try:
            if slot is not None and hasattr(self, "_try_beat_motif"):
                p = self._try_beat_motif(speaker, str(intent or "OBSERVE"), rl, int(slot), avoid_tags=avoid)
        except Exception:
            p = None

        if p is None:
            try:
                if rl == "main":
                    p = self._choose_main_by_intent(
                        speaker,
                        str(intent or "OBSERVE"),
                        want_tags=want,
                        avoid_tags=avoid,
                        coh_hint_text=str(coh_hint_text or ""),
                        coh_anchor_words=list(coh_anchor_words or []),
                    )
                else:
                    # For gesture events, keep clips short so they read as micro-gestures.
                    max_dur = None
                    try:
                        if gesture_mode:
                            max_dur = float(os.environ.get("LOCKKEY_GESTURE_MAX_DUR", "0.95") or 0.95)
                    except Exception:
                        max_dur = 0.95 if gesture_mode else None
                    p = self._choose_wildcard_role(speaker, role=rl, want_tags=want, avoid_tags=avoid, max_duration_s=max_dur)
            except Exception:
                p = None
        if p is None:
            return {"clip": None, "transcript": None, "tags": []}

        # metadata
        meta = self.voice_tags.get(p.name, {}) if isinstance(getattr(self, "voice_tags", None), dict) else {}
        transcript = None
        tags: List[str] = []
        try:
            if isinstance(meta, dict):
                transcript = str(meta.get("transcript") or meta.get("text") or "").strip() or None
                tg = meta.get("tags")
                if isinstance(tg, list):
                    tags = [str(x) for x in tg]
        except Exception:
            transcript = None
            tags = []

        duration_s = float(wav_duration_seconds(p) or 0.0)

        # play
        try:
            if pygame is None:
                # winsound fallback is blocking; avoid if requested async
                if async_play:
                    # best-effort: do nothing rather than freeze the loop
                    return {"clip": p.name, "transcript": transcript, "tags": tags, "duration": duration_s}
                self._play_wav_blocking(p)
            else:
                snd = pygame.mixer.Sound(str(p))
                snd.set_volume(float(self._voice_volume_for_wav(p, role=rl) or 1.0))

                ch = getattr(self, "_voice_primary_channel", None)
                if rl in ("murmur", "underlay"):
                    ch = getattr(self, "_voice_murmur_channel", None) or ch
                if ch is None:
                    ch = pygame.mixer.find_channel(True)

                # Interrupts can gently cut whatever is on the primary channel.
                try:
                    if rl == "interrupt" and ch is not None:
                        ch.fadeout(55)
                except Exception:
                    pass

                ch.play(snd, fade_ms=45)

            # bookkeeping
            try:
                self._note_used_clip(p.name)
            except Exception:
                pass
            try:
                if slot is not None and hasattr(self, "_note_beat_motif"):
                    self._note_beat_motif(speaker, str(intent or "OBSERVE"), rl, int(slot), p.name)
            except Exception:
                pass

        except Exception:
            # fragile: shut down briefly
            try:
                self._director_soft_disable(float(getattr(self, "_director_shutdown_s", 10) or 10))
            except Exception:
                pass

        return {"clip": p.name, "transcript": transcript, "tags": tags, "duration": duration_s}



    def _offline_resolve_best_effort(self, speaker: str, text: str) -> Optional[Path]:
        """Balanced: vibes priority, then text. Never leave a line silent if audio exists."""
        mood_name = str(getattr(self, "scene_mood_name", "") or "")
        intent = self._infer_intent(speaker, text, mood_name=mood_name)
        serious = self._is_serious_context(intent, mood_name=mood_name, text=text)
        want_tags = self._intent_want_tags(intent, mood_name=mood_name)
        req_obj = {}
        try:
            req_obj = self._read_director_tag_request_obj() or {}
        except Exception:
            req_obj = {}
        req_tags = req_obj.get("tags") if isinstance(req_obj.get("tags"), list) else []
        if req_tags:
            mode = (str(req_obj.get("mode") or "")).strip().lower() or (os.environ.get("LOCKKEY_TAG_REQUEST_MODE", "blend") or "blend").strip().lower()
            if mode == "override":
                want_tags = list(req_tags)
            else:
                want_tags = list(dict.fromkeys([*req_tags, *want_tags]))
        speaker_key = "fiend" if (speaker or "").upper() == "FIEND" else "birdsong"
        pool = list(self.voice_catalog.get(speaker_key, [])) or list(self.voice_catalog.get("any", []))
        if not pool:
            return None

        tgt = self._norm_text(text or "")
        strict = os.environ.get("LOCKKEY_OFFLINE_STRICT_TRANSCRIPT", "0") == "1"
        best_score = -1.0
        best_path: Optional[Path] = None

        # Avoid comedic tags during serious beats
        avoid = ["laugh","giggle","babble","wild","tch"] if serious else []
        # Motif memory: occasionally reuse a recurring favorite clip for this intent.
        try:
            m = self._try_motif(speaker, intent, avoid_tags=avoid)
            if m is not None:
                return m
        except Exception:
            pass


        for p in pool:
            meta = self.voice_tags.get(p.name, {}) if isinstance(self.voice_tags, dict) else {}
            tr = ""
            tags: List[str] = []
            if isinstance(meta, dict):
                tr = str(meta.get("transcript") or meta.get("text") or "").strip()
                tg = meta.get("tags")
                if isinstance(tg, list):
                    tags = [str(x).lower() for x in tg]
            # Skip disallowed tags in serious contexts
            if avoid and any(a in tags for a in avoid):
                continue

            # transcript similarity
            sim = 0.0
            if tgt and tr:
                sim = difflib.SequenceMatcher(None, tgt, self._norm_text(tr)).ratio()

            # tag overlap score
            overlap = 0.0
            if want_tags and tags:
                overlap = float(len(set([t.lower() for t in want_tags]) & set(tags))) / float(max(1, len(set([t.lower() for t in want_tags]))))

            # base score: vibes-first, then text
            # Director-requested tags (if any) can hard-steer selection.
            req_overlap = 0.0
            try:
                if req_tags and tags:
                    req_overlap = float(len(set([t.lower() for t in req_tags]) & set(tags))) / float(max(1, len(set([t.lower() for t in req_tags]))))
            except Exception:
                req_overlap = 0.0
            
            if req_tags:
                # Explicit tags dominate; intent palette + transcript help tie-break.
                score = (0.65 * req_overlap) + (0.20 * overlap) + (0.15 * sim)
            else:
                score = (0.55 * overlap) + (0.40 * sim)
            # variety penalty
            score -= self._recent_penalty(p.name)

            if score > best_score:
                best_score = score
                best_path = p

        # Thresholds:
        # - In serious contexts: require either decent transcript match or soft tag overlap
        # - Otherwise: any reasonable vibe match is fine
        min_ok = 0.22 if not serious else 0.30
        if best_path is not None and best_score >= min_ok:
            self._log_fallback({"kind":"best_effort","speaker":speaker,"intent":intent,"mood":mood_name,"score":round(float(best_score),3),"file":best_path.name})
            return best_path

        # If we didn't find a good transcript/tag match, use a role-aware wildcard
        role = "prefix" if serious else "any"
        p2 = self._choose_wildcard_role(speaker, role=role, want_tags=want_tags, avoid_tags=avoid)
        if p2 is not None:
            self._log_fallback({"kind":"wildcard_fill","speaker":speaker,"intent":intent,"mood":mood_name,"file":p2.name})
            return p2

        # Last resort: any audio
        if pool:
            p3 = random.choice(pool)
            self._log_fallback({"kind":"any","speaker":speaker,"intent":intent,"mood":mood_name,"file":p3.name})
            return p3
        return None


    def _maybe_play_wildcard_interjection(self, speaker: str, mood_name: str = "", text: str = "") -> None:
        """Balanced: optional prefix interjection that never ruins serious beats."""
        style = (os.environ.get("LOCKKEY_DIALOGUE_STYLE", "balanced") or "balanced").strip().lower()
        if style not in ("balanced", "cinematic", "comedy"):
            style = "balanced"
        # Defaults: balanced has low but nonzero spice
        default_rate = 0.10 if style == "balanced" else (0.18 if style == "comedy" else 0.04)
        try:
            rate = float((os.environ.get("LOCKKEY_WILDCARD_RATE", "") or "").strip() or str(default_rate))
        except Exception:
            rate = default_rate
        if rate <= 0:
            return

        intent = self._infer_intent(speaker, text, mood_name=mood_name)
        if self._is_serious_context(intent, mood_name=mood_name, text=text):
            return

        # Beat/fill gating: only interject on allowed rhythmic windows (keeps rhythm clean).
        slot_for_motif: Optional[int] = None
        try:
            if bool(getattr(self, "beat_gate_enabled", True)):
                if bool(getattr(self, "fill_grid_enabled", True)):
                    slot_i, _, frac_s, _, _ = self._grid_snapshot()
                    slot_for_motif = int(slot_i)
                    allow = self._grid_allowed_slots("prefix")
                    if (int(slot_i) not in allow) or (float(frac_s) > 0.30):
                        return
                else:
                    beat_in_bar, _, frac, _ = self._beat_gate_snapshot()
                    if not (int(beat_in_bar) == 0 and float(frac) <= 0.22):
                        return
        except Exception:
            pass

        # pacing guards
        try:
            cooldown = float(os.environ.get("LOCKKEY_WILDCARD_COOLDOWN_S", "1.0") or "1.0")
        except Exception:
            cooldown = 1.0
        now = time.time()
        if (now - float(getattr(self, "_wildcard_last_ts", 0.0) or 0.0)) < cooldown:
            return

        # max per minute guard
        try:
            max_per_min = int(float(os.environ.get("LOCKKEY_WILDCARD_MAX_PER_MIN", "6") or "6"))
        except Exception:
            max_per_min = 6
        try:
            recent = [t for t in getattr(self, "_wildcard_recent_ts", []) if (now - float(t)) <= 60.0]
            self._wildcard_recent_ts = recent
            if len(recent) >= max_per_min:
                return
        except Exception:
            pass

        try:
            if random.random() > rate:
                return
        except Exception:
            return

        want = self._intent_want_tags(intent, mood_name=mood_name)
        p: Optional[Path] = None
        if slot_for_motif is not None:
            try:
                p = self._try_beat_motif(speaker, intent, "prefix", int(slot_for_motif), avoid_tags=["scream","shriek"])
                if p is not None:
                    self._stat_inc("motifs_used", 1)
            except Exception:
                p = None
        if p is None:
            p = self._choose_wildcard_role(speaker, role="prefix", want_tags=want, avoid_tags=["scream","shriek"])
        if p is None:
            return
        self._log_fallback({"kind":"interjection_prefix","speaker":speaker,"intent":intent,"mood":mood_name,"file":p.name})
        self._wildcard_last_ts = float(now)
        try:
            self._wildcard_recent_ts.append(float(now))
        except Exception:
            pass
        self._play_wav_blocking(p)
        try:
            if slot_for_motif is not None and p is not None:
                self._note_beat_motif(speaker, intent, "prefix", int(slot_for_motif), p.name)
        except Exception:
            pass
        try:
            self._note_used_clip(getattr(p, 'name', str(p)))
        except Exception:
            pass

    def _maybe_play_suffix_interjection(self, speaker: str, mood_name: str = "", text: str = "") -> float:
        """Optional suffix after the main line; returns extra duration."""
        style = (os.environ.get("LOCKKEY_DIALOGUE_STYLE", "balanced") or "balanced").strip().lower()
        default_rate = 0.05 if style == "balanced" else (0.10 if style == "comedy" else 0.02)
        try:
            rate = float((os.environ.get("LOCKKEY_WILDCARD_SUFFIX_RATE", "") or "").strip() or str(default_rate))
        except Exception:
            rate = default_rate
        if rate <= 0:
            return 0.0

        intent = self._infer_intent(speaker, text, mood_name=mood_name)
        if self._is_serious_context(intent, mood_name=mood_name, text=text):
            return 0.0

        # Beat/fill gating: prefer suffix on allowed tail slots (keeps cadence musical).
        slot_for_motif: Optional[int] = None
        try:
            if bool(getattr(self, "beat_gate_enabled", True)):
                if bool(getattr(self, "fill_grid_enabled", True)):
                    slot_i, _, frac_s, _, _ = self._grid_snapshot()
                    slot_for_motif = int(slot_i)
                    allow = self._grid_allowed_slots("suffix")
                    if (int(slot_i) not in allow) or (float(frac_s) < 0.55):
                        return 0.0
                else:
                    beat_in_bar, _, frac, _ = self._beat_gate_snapshot()
                    bpb = int(getattr(self, "beat_gate_beats_per_bar", 4) or 4)
                    last_beat = max(0, bpb - 1)
                    if not (int(beat_in_bar) == int(last_beat) and float(frac) >= 0.40):
                        return 0.0
        except Exception:
            pass

        try:
            if random.random() > rate:
                return 0.0
        except Exception:
            return 0.0

        want = self._intent_want_tags(intent, mood_name=mood_name)
        p: Optional[Path] = None
        if slot_for_motif is not None:
            try:
                p = self._try_beat_motif(speaker, intent, "suffix", int(slot_for_motif))
                if p is not None:
                    self._stat_inc("motifs_used", 1)
            except Exception:
                p = None
        if p is None:
            p = self._choose_wildcard_role(speaker, role="suffix", want_tags=want)
        if p is None:
            return 0.0
        try:
            d = float(wav_duration_seconds(p) or 0.0)
        except Exception:
            d = 0.0
        self._log_fallback({"kind":"interjection_suffix","speaker":speaker,"intent":intent,"mood":mood_name,"file":p.name})
        self._play_wav_blocking(p)
        try:
            if slot_for_motif is not None and p is not None:
                self._note_beat_motif(speaker, intent, "suffix", int(slot_for_motif), p.name)
        except Exception:
            pass
        try:
            self._note_used_clip(getattr(p, 'name', str(p)))
        except Exception:
            pass
        return float(d or 0.0)

    def say_commit(self, speaker: str, text: str, intensity: float = 0.5, commit_token: str = "", force: bool = False) -> None:
        # Mandatory voice: if enabled false, still speak
        if text is None:
            return
        msg = str(text).strip()
        if not msg:
            return
        tts_speaker, post_preset = self._map_tts_speaker(str(speaker))
        account_tag = "fiend" if (tts_speaker or "").upper() == "FIEND" else "bird"
        if self._quota_blocked.get(account_tag, False) and self.on_quota != "crash":
            return
        # Fiend per-line mode: TM -> PC -> BF -> SD (or tag/lock).
        cache_extra = ""
        vs_override = None
        if account_tag == "fiend":
            vs_override, msg, cache_extra = self._select_fiend_voice_settings_for_line(msg)


        max_chars = self.max_tts_chars_fiend if account_tag == "fiend" else self.max_tts_chars_bird
        spoken = _shorten_for_tts(msg, max_chars)
        try:
            wav = self._synthesize_to_wav(tts_speaker or "NARRATOR", spoken, post_preset=post_preset, cache_extra=cache_extra, voice_settings_override=vs_override)
        except RuntimeError as e:
            err = str(e)
            self._last_error = err
            if "ELEVENLABS_QUOTA_EXCEEDED" in err and self.on_quota != "crash":
                self._quota_blocked[account_tag] = True
                return
            # Offline robustness: no lines left behind.
            if "OFFLINE_VOICE_MISSING" in err:
                try:
                    # Try to keep momentum: optionally interject a wildcard, then play best-effort line audio.
                    self._maybe_play_wildcard_interjection(tts_speaker or "NARRATOR", mood_name=getattr(self, "scene_mood_name", ""))
                except Exception:
                    pass
                try:
                    alt = self._offline_resolve_best_effort(tts_speaker or "NARRATOR", spoken)
                    if alt is not None:
                        self._play_wav_blocking(alt)
                        return
                except Exception:
                    pass
                # Nothing available at all.
                return
            if self.on_quota == "crash":
                raise
            return
        self._play_wav_blocking(wav)

# -----------------------------
# OST mask windows (non-destructive)
# -----------------------------
def _on_ost_mask_window(self, tag: str = "mask", intensity: float = 0.0, track: str = "") -> None:
    """Callback from procedural_ost when a mask window begins.

    Non-destructive: OST briefly ducks the bed and requests a sanctioned micro-texture.
    Must be fast + non-blocking.
    """
    try:
        now = time.time()

        # Don't step on questions/answer lane, and don't machine-gun textures.
        min_gap = float(os.environ.get("LOCKKEY_MASK_TEX_MIN_GAP_S", "7.5") or 7.5)
        if (now - float(getattr(self, "_mask_texture_last_at", 0.0) or 0.0)) < min_gap:
            return
        if now < float(getattr(self, "_question_lock_until", 0.0) or 0.0):
            return
        if now < float(getattr(self, "_answer_lane_until", 0.0) or 0.0):
            return
        if now < float(getattr(self, "_no_barks_until", 0.0) or 0.0):
            return

        # If the Fiend main lane is actively speaking, don't add a texture (keeps it clean).
        try:
            if getattr(self, "_use_pygame_voice", False) and pygame is not None:
                chmap = getattr(self, "_voice_primary_channel_by_speaker", {}) or {}
                ch_f = chmap.get("FIEND", None)
                if ch_f is not None and ch_f.get_busy():
                    return
        except Exception:
            pass

        # Arm cooldown and fire primary texture (daemon thread).
        self._mask_texture_last_at = now
        th = threading.Thread(
            target=_play_mask_texture_blocking,
            args=(self, str(tag or "mask"), float(intensity or 0.0), str(track or "")),
            daemon=True,
        )
        th.start()

        # Optional: schedule a short "aftershiver" micro-slot on an offbeat-ish delay.
        try:
            if str(os.environ.get("LOCKKEY_MASK_AFTERSHIVER_ENABLE", "1")).strip().lower() in ("1","true","yes","on"):
                # Delay chooses an offbeat pocket; slightly longer when intensity is lower.
                it = float(intensity or 0.0)
                if it >= 0.70:
                    dmin = float(os.environ.get("LOCKKEY_MASK_AFTERSHIVER_MIN_S", "0.28") or 0.28)
                    dmax = float(os.environ.get("LOCKKEY_MASK_AFTERSHIVER_MAX_S", "0.44") or 0.44)
                else:
                    dmin = float(os.environ.get("LOCKKEY_MASK_AFTERSHIVER_MIN_S_LOW", "0.42") or 0.42)
                    dmax = float(os.environ.get("LOCKKEY_MASK_AFTERSHIVER_MAX_S_LOW", "0.75") or 0.75)
                delay = max(0.12, random.uniform(dmin, dmax))

                base_tag = str(tag or "mask")
                timer = threading.Timer(delay, _on_ost_mask_aftershiver, args=(self, base_tag, float(intensity or 0.0), str(track or "")))
                timer.daemon = True
                timer.start()
        except Exception:
            pass

    except Exception:
        return


def _on_ost_mask_aftershiver(self, base_tag: str, intensity: float, track: str) -> None:
    """A second micro-slot shortly after a mask texture.

    Keeps the song intact while "coding" bratty/feral energy as a rhythmic breath/huff.
    """
    try:
        now = time.time()

        # Only if we're still near the mask event (prevents stray timers later).
        last = float(getattr(self, "_mask_texture_last_at", 0.0) or 0.0)
        if (now - last) > float(os.environ.get("LOCKKEY_MASK_AFTERSHIVER_ARM_S", "2.25") or 2.25):
            return

        # Don't step on question/answer lanes.
        if now < float(getattr(self, "_question_lock_until", 0.0) or 0.0):
            return
        if now < float(getattr(self, "_answer_lane_until", 0.0) or 0.0):
            return
        if now < float(getattr(self, "_no_barks_until", 0.0) or 0.0):
            return

        # Aftershiver has its own gap guard (smaller than primary mask).
        min_gap = float(os.environ.get("LOCKKEY_MASK_AFTERSHIVER_MIN_GAP_S", "3.0") or 3.0)
        if (now - float(getattr(self, "_mask_aftershiver_last_at", 0.0) or 0.0)) < min_gap:
            return
        self._mask_aftershiver_last_at = now

        # If Fiend main is speaking, skip.
        try:
            if getattr(self, "_use_pygame_voice", False) and pygame is not None:
                chmap = getattr(self, "_voice_primary_channel_by_speaker", {}) or {}
                ch_f = chmap.get("FIEND", None)
                if ch_f is not None and ch_f.get_busy():
                    return
        except Exception:
            pass

        t = (base_tag or "").lower()
        after_tag = "aftershiver"
        if "brat" in t or "better" in t:
            after_tag = "brat_aftershiver"

        th = threading.Thread(
            target=_play_mask_texture_blocking,
            args=(self, after_tag, float(intensity or 0.0), str(track or "")),
            daemon=True,
        )
        th.start()
    except Exception:
        return


def _play_mask_texture_blocking(self, tag: str, intensity: float, track: str) -> None:
    """Play a sanctioned micro-texture for a mask window.

    This is *non-destructive*: we do not edit the music file; we only add a short, beat-friendly texture
    that reads as character, and we keep it short + gated so it never stacks.
    """
    # Global on/off
    try:
        if str(os.environ.get("LOCKKEY_MASK_TEX_ENABLE", "1")).strip().lower() not in ("1","true","yes","on"):
            return
    except Exception:
        pass

    # Lock to prevent overlap between concurrent mask requests.
    try:
        lk = getattr(self, "_mask_texture_lock", None)
        if lk is not None:
            acquired = lk.acquire(blocking=False)
            if not acquired:
                return
    except Exception:
        lk = None

    try:
        speaker = "FIEND"
        # Prefer real recorded micro-clips if available (best vibe, zero TTS risk).
        # Prefer real recorded micro-clips if available (best vibe, zero TTS risk).
        t = (tag or "").lower()
        phase = "aftershiver" if "aftershiver" in t else "mask"
        tr = (track or "").lower().strip()
        it = float(intensity or 0.0)

        # Track-aware palette: "simple effectiveness" (Loverot goes crazy) without turning into random harshness.
        if tr == "overdrive":
            want = ["oy","tch","huff","smirk","laugh","breath","gasp"]
        elif tr == "frenzy":
            want = ["moan","gasp","breath","huff","laugh","smirk"]
        elif tr in ("release","aftercare","story","love_bunny"):
            want = ["breath","mm","hum","mhm","smirk","soft","gasp"]
        else:
            want = ["huff","oy","tch","breath","gasp","moan","smirk","laugh"]

        # Aftershiver is smaller + airier.
        if phase == "aftershiver":
            want = ["breath","huff","mm","mhm","gasp"] + want

        # Intensity shaping: more feral at peak, more tidy when lower.
        if it >= 0.80 and tr == "frenzy":
            want = ["moan","gasp","laugh","huff"] + want
        if it < 0.45:
            want = ["breath","mm","mhm"] + want

        avoid = ["long","monologue"]
        try:
            max_d = float(os.environ.get("LOCKKEY_MASK_TEX_MAX_DUR_S", "1.25") or 1.25)
        except Exception:
            max_d = 1.25
        try:
            clip = self._choose_wildcard_role(speaker, role="interrupt", want_tags=want, avoid_tags=avoid, max_duration_s=max_d)
        except Exception:
            clip = None

        if clip is not None:
            try:
                if getattr(self, "_use_pygame_voice", False) and pygame is not None:
                    snd = pygame.mixer.Sound(str(clip))
                    snd.set_volume(float(self._voice_volume_for_wav(clip, role="interrupt") or 0.35))
                    bc = getattr(self, "_voice_bark_channels", None) or []
                    ch = (bc[0] if bc else pygame.mixer.find_channel(True))
                    fade_ms = int(os.environ.get("LOCKKEY_VOICE_FADE_MS", "18") or 18)
                    fade_ms = max(0, min(1200, fade_ms))
                    ch.play(snd, fade_ms=fade_ms)
                    # Tiny tail soften to avoid stop-clicks on short clips.
                    while ch.get_busy():
                        time.sleep(0.01)
                    try:
                        ch.fadeout(int(os.environ.get("LOCKKEY_VOICE_STOP_FADE_MS", "65") or 65))
                    except Exception:
                        pass
                else:
                    self._play_wav_blocking(clip)
                return
            except Exception:
                pass

        # Fallback: ultra-short text bark. Keep it tiny, so it reads as a rhythmic "oy/hff" not dialogue.
        # Tag-specific shaping (non-destructive): we *code* brat/feral energy as a rhythmic micro-texture,
        # without ever trying to "fix" lyrics by speaking them.
        t = (tag or '').lower()
        phase = 'aftershiver' if 'aftershiver' in t else 'mask'
        tr = (track or '').lower().strip()
        it = float(intensity or 0.0)

        pool = None
        if ('brat' in t) or ('better' in t):
            if phase == 'aftershiver':
                pool = ['hff… yeah.', '…mm.', 'hah… mm.', 'tch… mm.']
            elif tr == 'frenzy':
                pool = ['mm— ah… hff.', 'oy— hah… hff!', 'mm… don\'t. hff.']
            else:  # overdrive/default
                pool = ['oy— you can\'t… hff!', 'tch— mm. hff.', 'oy. try me— hff!']
        else:
            # Generic mask pocket: tidy, beat-friendly.
            if phase == 'aftershiver':
                pool = ['…mhm.', 'mm.', 'hff…']
            else:
                pool = ['mm— hff.', 'tch… mm.', 'mm.']

        # Avoid exact repeats back-to-back.
        try:
            last = str(getattr(self, '_mask_msg_last', '') or '')
        except Exception:
            last = ''
        try:
            choices = [p for p in pool if p != last] if pool else []
            msg = random.choice(choices or pool or ['mm.'])
        except Exception:
            msg = (pool[0] if pool else 'mm.')
        self._mask_msg_last = msg
        # Build wav via the existing offline/TTS stack, but play it as a bark lane WITHOUT extra director chaos.
        try:
            tts_speaker, post_preset = self._map_tts_speaker(speaker)
            wav = self._synthesize_to_wav(tts_speaker or speaker, msg, post_preset=post_preset)
        except Exception:
            wav = None

        if wav is None:
            return

        try:
            if getattr(self, "_use_pygame_voice", False) and pygame is not None:
                snd = pygame.mixer.Sound(str(wav))
                snd.set_volume(float(self._voice_volume_for_wav(wav, role="interrupt") or 0.33))
                bc = getattr(self, "_voice_bark_channels", None) or []
                ch = (bc[0] if bc else pygame.mixer.find_channel(True))
                fade_ms = int(os.environ.get("LOCKKEY_VOICE_FADE_MS", "18") or 18)
                fade_ms = max(0, min(1200, fade_ms))
                ch.play(snd, fade_ms=fade_ms)
                while ch.get_busy():
                    time.sleep(0.01)
                try:
                    ch.fadeout(int(os.environ.get("LOCKKEY_VOICE_STOP_FADE_MS", "65") or 65))
                except Exception:
                    pass
            else:
                # winsound backend: just play cleanly
                self._play_wav_blocking(wav)
        except Exception:
            return
    finally:
        try:
            if lk is not None:
                lk.release()
        except Exception:
            pass

# Singleton
_AUDIO_SINGLETON: Optional[AudioManager] = None

def get_audio_manager() -> Optional[AudioManager]:
    global _AUDIO_SINGLETON
    if _AUDIO_SINGLETON is None:
        _AUDIO_SINGLETON = AudioManager()
    return _AUDIO_SINGLETON
