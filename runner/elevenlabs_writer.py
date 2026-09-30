#!/usr/bin/env python3
"""ElevenLabs writer: the original wiring, live.

Same inbox/outbox protocol as deck_writer, but every Jasmine line is
rendered fresh through her real ElevenLabs voice ('Jazz'), with delivery
shaped by the FULL beat packet — her side only, never his.

What actually leaves the machine per beat:
  - her voice line text, prefixed with short v3 brackets only:
    her voice tag ([Florida swamp valley]) + one anti-narrative objective
    ([teasing him playfully]) + one audio tag ([laughs]). Short on purpose:
    v3 performs short brackets as direction but reads long multi-clause
    brackets aloud.
  - HIS voice line text (v10 rework — every dialogue beat is an exchange),
    prefixed with short tags only: [Florida swamp valley] + one mood tag
    ([teasing her back playfully]). His pool is rewritten in-dialect;
    the old NLS dom interjections are retired.
  - voice_settings (stability / similarity / style / speed) derived from
    bird-side beat keys

The raw packet never leaves. Fiend's game-state keys are never read for
delivery; the library's 'fiend' voice is never selected (his real voice
is pinned by ID). ElevenLabs' TTS API has no freeform "context" field, so the
packet is translated locally into delivery params — that translation is
the context.

Key resolution: ELEVENLABS_API_KEY env first, then the authd surrogate
(this dev VM). If neither is available — or a render fails — the writer
falls back to the offline deck clip for the same line, so her voice never
drops out mid-session.

Usage: elevenlabs_writer.py <session-dir> [--model eleven_flash_v2_5]
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

RUNNER = Path(__file__).resolve().parent
sys.path.insert(0, str(RUNNER))
import deck_writer
from deck_writer import DeckWriter
from exchanges import pick_exchange, EXCHANGES

VOICE_LIB = RUNNER / "voice_library" / "voices.json"
DEFAULT_VOICE_ID = "MxEk11h8TFl0s7fhrCkF"  # 'Jazz' — Jasmine. Never the fiend voice.
API = "https://api.elevenlabs.io/v1/text-to-speech"
TTS_TIMEOUT_S = 20.0

# Bird-side beat keys allowed to shape delivery. fiend is never read here.
BIRD_KEYS = ("jasmine", "her", "finale", "phase", "beat")

# Her canonical voice direction (Andrew, 2026-09-24): Florida swamp valley
# is the timbre phrase. Not California valley girl, not polished mall-bright,
# not Martha dry, not generic girlfriend. Valley cadence dragged through
# humidity: bright nasal smile-voice, humid, husky, mouthy — sticky little
# throat catch, huffed clause endings, grin in the throat, tiny swampy
# gargle, feral mouth texture. Compressed consonants, humid drawl; endings
# stretch, huff, gargle slightly or smear when she's pleased with herself.
# Amused, smug, intimate, lived-in.
# Example of the target: "look't'rrrr. look't'r faceeeee. she's an auditorrrr."
#
# PIPELINE NOTE: v3 reads long multi-clause brackets ALOUD ("experimental,
# results vary"). So the injected tag stays SHORT — a few punchy words, no
# colons/commas/dashes. The full prompt lives in JASMINE_VOICE.md as the
# canonical reference; the wire only carries what v3 reliably performs.
VOICE_TAG = "[Florida swamp valley]"


# ── FIEND VOICE (v10 rework) ─────────────────────────────────────────
# Fiend speaks again — his real voice, invisible dialogue (no text anywhere).
# v10: the old NLS dom interjections are RETIRED. His pool is rewritten
# fresh in-dialect (Florida swamp valley): pretty softsad bratty boy,
# teasing her back, melting when she overwhelms him. Six moods in
# fiend_lines/; her category picks his mood (switchplay loop).
# Full voice direction: skills/elevenlabs/FIEND_VOICE.md
def _resolve_fiend_voice_id() -> str:
    return os.environ.get("FIEND_VOICE_ID", "").strip() or "pgrEFhHEIrYm4BF8476L"


import fiend_lines as _fiend_pool

# her category -> his mood. The switchplay loop: she brats, he brats back;
# she overwhelms, he melts; she taunts, he brat-tames; she pouts, he coaxes.
FIEND_RESPONSE_MAP = {
    "tease": "tease_back", "sweet": "tease_back", "giggle": "tease_back",
    "heated": "melt", "feral": "melt",
    "taunt": "brat_tamer",
    "pout": "coax",
    "aftercare": "aftercare_soft", "aftercare_smug": "aftercare_soft",
    "finale_announce_vaginal": "tease_back",
    "finale_announce_anal": "tease_back",
    "finale_vaginal": "melt", "finale_anal": "melt",
    "action": "tease_back", "toot": "tease_back",
    # v10.4: her wired registers + tender echo answer mapping
    "r1_mumble": "coax", "r2_scold": "brat_tamer",
    "r3_sleepy": "aftercare_soft", "r4_coverup": "tease_back",
    "r5_documentary": "tease_back", "r6_laugh": "tease_back",
    "r8_pen": "melt", "r10_deadpan": "tease_back",
    "tender_echo": "softsad",
}
FIEND_OPENER_CHANCE = 0.15  # he starts the exchange this time
FIEND_MOOD_TAGS = {
    "tease_back": "[teasing her back playfully]",
    "opener": "[poking at her to get her attention]",
    "melt": "[melting softly, overwhelmed]",
    "brat_tamer": "[grinning, playfully threatening]",
    "coax": "[coaxing her gently]",
    "aftercare_soft": "[quiet and tender]",
    "softsad": "[quiet and unguarded]",
    "escalation": "[flustered, losing it]",
    "daylife": "[warm, asking about her day]",
}
FIEND_VOICE_TAG = "[Florida swamp valley]"

FIEND_VOICE_SETTINGS = {"stability": 0.55, "similarity_boost": 0.80,
                        "style": 0.65, "speed": 1.0,
                        "use_speaker_boost": True}


def fiend_chance() -> float:
    """Kill-switch / dial. 1.0 = every dialogue beat is an exchange."""
    try:
        return min(1.0, max(0.0, float(os.environ.get("FIEND_CHANCE", "1.0") or 1.0)))
    except Exception:
        return 1.0


def fiend_softsad_chance() -> float:
    """R6 surfacing dial. Chance any fiend reply cracks into softsad
    (Ash Lynx showing) instead of the mapped mood. Rare on purpose."""
    try:
        return min(1.0, max(0.0, float(os.environ.get("FIEND_SOFTSAD_CHANCE", "0.07") or 0.07)))
    except Exception:
        return 0.07


def fiend_ledger_chance() -> float:
    """Ledger dial. Chance his reply ends in a bit finisher — sudden
    honest fluster (devotion) or the personified beast bit."""
    try:
        return min(1.0, max(0.0, float(os.environ.get("FIEND_LEDGER_CHANCE", "0.20") or 0.20)))
    except Exception:
        return 0.20


def escalation_chance() -> float:
    """The 😳 feedback loop dial. Chance a heated/feral beat becomes a
    paired escalation exchange (her escalation line + his escalation
    reply). ElevenLabs-only."""
    try:
        return min(1.0, max(0.0, float(os.environ.get("ESCALATION_CHANCE", "0.15") or 0.15)))
    except Exception:
        return 0.15


def escalation_crest_at() -> int:
    """Off-ramp threshold: how many loop beats before it can crest into
    the finale announce — and only at edging/climax (his state close/peak)."""
    try:
        return max(1, int(os.environ.get("ESCALATION_CREST_AT", "3") or 3))
    except Exception:
        return 3


def daylife_chance() -> float:
    """Daylife dial. Chance an early-night tease/opener becomes him asking
    about her day instead."""
    try:
        return min(1.0, max(0.0, float(os.environ.get("DAYLIFE_CHANCE", "0.25") or 0.25)))
    except Exception:
        return 0.25


def daylife_seq_max() -> int:
    """Daylife window: only in the first N beats of the night — he asks
    before the night takes over."""
    try:
        return max(1, int(os.environ.get("DAYLIFE_SEQ_MAX", "30") or 30))
    except Exception:
        return 30


# ── FIEND FALLBACK TTS (Piper, offline, credit-free) ──────────────────
# When ElevenLabs is unreachable or out of credits, Fiend must not go
# silent. Piper (local, free, no API, no network) renders his line with
# an offline masculine voice; output is converted to mp3 so the rest of
# the pipeline (fiend_<tag>.mp3 naming, mp3_dur_s, browser player) is
# untouched. Renders are cached by text hash so repeats cost nothing.
#
# Env: FIEND_TTS=auto (default: ElevenLabs first, Piper on ANY failure),
#      elevenlabs (force old behavior), piper (force fallback — testing
#      or saving credits). FIEND_PIPER_MODEL overrides the voice file.
FIEND_FALLBACK_DIR = RUNNER / "voice_fallback"
FIEND_FALLBACK_MODEL = os.environ.get("FIEND_PIPER_MODEL",
                                      "en_US-lessac-medium.onnx")
FIEND_FALLBACK_CACHE = FIEND_FALLBACK_DIR / "cache"
FIEND_FALLBACK_SPEED = 0.9  # slightly quick — rowdy gremlin cadence


def fiend_tts_mode() -> str:
    return (os.environ.get("FIEND_TTS") or "auto").strip().lower() or "auto"


def _render_fiend_piper(text: str) -> bytes:
    """Render one fiend line with the offline Piper voice. Returns mp3
    bytes. Raises RuntimeError if Piper/ffmpeg/the model is unavailable.

    NOTE: plain text only — Piper would read ElevenLabs direction tags
    ("[Florida swamp valley] ...") aloud, so they are NOT injected here."""
    import hashlib
    import shutil
    import subprocess
    import tempfile
    clean = " ".join(str(text or "").split())
    if not clean:
        raise RuntimeError("piper fallback: empty text")
    model_path = FIEND_FALLBACK_DIR / FIEND_FALLBACK_MODEL
    if not model_path.is_file():
        raise RuntimeError(f"piper fallback: model missing ({model_path})")
    piper_bin = shutil.which("piper")
    if not piper_bin:
        raise RuntimeError("piper fallback: 'piper' binary not on PATH")
    if not shutil.which("ffmpeg"):
        raise RuntimeError("piper fallback: ffmpeg not on PATH")
    key = hashlib.sha1(
        f"{FIEND_FALLBACK_MODEL}|{FIEND_FALLBACK_SPEED}|{clean}".encode("utf-8")
    ).hexdigest()
    FIEND_FALLBACK_CACHE.mkdir(parents=True, exist_ok=True)
    cached = FIEND_FALLBACK_CACHE / f"{key}.mp3"
    if cached.is_file() and cached.stat().st_size > 1000:
        return cached.read_bytes()
    with tempfile.TemporaryDirectory(prefix="fiend_piper_") as td:
        wav = Path(td) / "out.wav"
        mp3 = Path(td) / "out.mp3"
        p = subprocess.run(
            [piper_bin, "--model", str(model_path),
             "--output_file", str(wav),
             "--length-scale", str(FIEND_FALLBACK_SPEED)],
            input=clean.encode("utf-8"),
            capture_output=True, timeout=90)
        if p.returncode != 0 or not wav.is_file() or wav.stat().st_size < 1000:
            raise RuntimeError(
                "piper render failed: "
                + (p.stderr or b"")[-200:].decode("utf-8", "replace"))
        q = subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(wav),
             "-codec:a", "libmp3lame", "-b:a", "128k", "-ar", "44100",
             str(mp3)],
            capture_output=True, timeout=60)
        if q.returncode != 0 or not mp3.is_file() or mp3.stat().st_size < 1000:
            raise RuntimeError("piper fallback: ffmpeg mp3 conversion failed")
        data = mp3.read_bytes()
    cached.write_bytes(data)
    return data


# Offline voice decks (pre-rendered 2026-09-25, shipped in the zip): the
# writer checks these caches before ever calling the tts CLI, so the scene
# is fully voiced on machines without the tts binary (e.g. Andrew's PC).
VOICE_CACHE_DIR = RUNNER / "voice_cache"
FIEND_VOICE_CACHE = VOICE_CACHE_DIR / "fiend"
JASMINE_VOICE_CACHE = VOICE_CACHE_DIR / "jasmine"


def _ttscli_cache_key(voice_id: str, tts_text: str) -> str:
    import hashlib
    return hashlib.sha1(
        f"{voice_id}|{tts_text}".encode("utf-8")).hexdigest()


def jasmine_tts_text(text: str) -> str:
    # tts mangles heavy punctuation into long pauses (learned live) —
    # commas and periods only. Trailing commas choke the backend, so
    # strip them (2026-09-25: one escalation line failed 3/3 on "… ,").
    t = text.replace("—", ",").replace("...", ",").replace("~", "")
    t = t.replace(" ,", ",")
    return t.rstrip(", ").rstrip(",").strip()


def fiend_tts_text(text: str) -> str:
    clean = " ".join(str(text or "").split())
    t = clean.replace("—", ",").replace("...", ",").replace("~", "")
    t = t.replace(" ,", ",")
    return t.rstrip(", ").rstrip(",").strip()


# Andrew's pick 2026-09-25 after a 10-voice shootout: her offline voice.
# "Glossy Pendant" — mid, smoky. Beat marisol (creaky), aria, plush shawl.
JASMINE_TTSCLI_VOICE = "avocado_v2:qvd_03858"


# Andrew's pick 2026-09-30 (shootout winner, dethroned Quirky Domino
# after one day, supersedes the 2026-09-25 Mild Yarn stopgap): fiend's
# offline voice. "Sparkly Bracelet" (avocado_v2:qvd_03988) — the prettiest,
# slightly androgynous voice with smoky texture. The "pretty boy is literal"
# hypothesis won.
FIEND_TTSCLI_VOICE = "avocado_v2:qvd_03988"


# Launcher piper mode (BRATBOX_VOICE_MODE=piper): skip ElevenLabs
# entirely and voice everything through the tts CLI crowned voices
# (glossy pendant + Sparkling Bracelet above). No key, no network — on
# machines without the tts binary the pre-rendered cache/deck carries it.
_PIPER_MODE = (os.environ.get("BRATBOX_VOICE_MODE", "").strip().lower()
               == "piper")


def _render_fiend_ttscli(text: str) -> bytes:
    """Render one fiend line with the local tts CLI (Sparkling Bracelet voice).
    Returns mp3 bytes. Raises RuntimeError on failure."""
    import shutil
    import subprocess
    tts_text = fiend_tts_text(text)
    if not tts_text:
        raise RuntimeError("ttscli fallback: empty text")
    key = _ttscli_cache_key(FIEND_TTSCLI_VOICE, tts_text)
    FIEND_VOICE_CACHE.mkdir(parents=True, exist_ok=True)
    cached = FIEND_VOICE_CACHE / f"ttscli_{key}.mp3"
    if cached.is_file() and cached.stat().st_size > 1000:
        return cached.read_bytes()
    # cache missed — need the live tts binary from here on
    tts_bin = shutil.which("tts")
    if not tts_bin:
        raise RuntimeError("ttscli fallback: 'tts' binary not on PATH "
                           "and no cached clip")
    p = subprocess.run(
        [tts_bin, "speak", "--voice", FIEND_TTSCLI_VOICE,
         "--text", tts_text, "--output", str(cached)],
        capture_output=True, timeout=90)
    if (p.returncode != 0 or not cached.is_file()
            or cached.stat().st_size < 1000):
        raise RuntimeError(
            "ttscli fallback render failed: "
            + (p.stderr or b"")[-200:].decode("utf-8", "replace"))
    return cached.read_bytes()


def _render_fiend_elevenlabs(text: str, voice_id: str, mood: str = "tease_back",
                             model: str = "eleven_v3") -> bytes:
    """ElevenLabs leg of the fiend render. Clean dialogue text + short
    direction tags only ([Florida swamp valley] + one mood tag) — same
    short-tag convention as Jasmine's renders. Returns raw mp3 bytes
    or raises (no key, quota, network, short response)."""
    mode, key = resolve_key()
    if not mode:
        raise RuntimeError("no elevenlabs key for fiend render")
    tag = FIEND_MOOD_TAGS.get(mood, FIEND_MOOD_TAGS["tease_back"])
    script = f"{FIEND_VOICE_TAG} {tag} {text.strip()}"
    payload = {"text": script, "model_id": model,
               "voice_settings": dict(FIEND_VOICE_SETTINGS)}
    data = json.dumps(payload).encode("utf-8")
    url = f"{API}/{voice_id}?output_format=mp3_44100_128"
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "audio/mpeg")
    req.add_header("xi-api-key", key)
    with urllib.request.urlopen(req, timeout=TTS_TIMEOUT_S) as resp:
        audio = resp.read()
    if len(audio) < 1000:
        raise RuntimeError(f"elevenlabs returned {len(audio)} bytes for fiend")
    return audio


def render_fiend_line(text: str, voice_id: str, mood: str = "tease_back",
                      model: str = "eleven_v3") -> bytes:
    """Render one fiend line. Returns raw mp3 bytes or raises. Same
    signature as before — the call site is untouched.

    FIEND_TTS=auto (default): ElevenLabs first; ANY failure (no key,
    quota, network, short response) falls back to the offline tts CLI
    voice (Sparkling Bracelet), then Piper, transparently. =elevenlabs: force
    old behavior (raise on failure). =piper: force the Piper fallback
    (testing / saving credits). BRATBOX_VOICE_MODE=piper (launcher):
    skip ElevenLabs, straight to the tts CLI crowned voice."""
    tts_mode = fiend_tts_mode()
    if _PIPER_MODE:
        return _render_fiend_ttscli(text)
    if tts_mode == "piper":
        return _render_fiend_piper(text)
    try:
        return _render_fiend_elevenlabs(text, voice_id, mood, model)
    except Exception as e:
        if tts_mode == "elevenlabs":
            raise
        try:
            return _render_fiend_ttscli(text)
        except Exception as te:
            try:
                return _render_fiend_piper(text)
            except Exception as pe:
                raise RuntimeError(
                    f"fiend render failed (elevenlabs: {e}; "
                    f"ttscli (Sparkling Bracelet): {te}; piper fallback: {pe})"
                ) from e


def resolve_voice_id() -> str:
    try:
        lib = json.loads(VOICE_LIB.read_text(encoding="utf-8"))
        pinned = (lib.get("pinned") or {}).get("jasmine")
        if pinned:
            return pinned
    except Exception:
        pass
    return os.environ.get("JASMINE_VOICE_ID", "").strip() or DEFAULT_VOICE_ID


def resolve_key():
    """Return (mode, value). mode is 'env', 'surrogate', or None."""
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if key:
        return ("env", key)
    try:
        sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
        from dynamic_credentials import dynamic_credential_entry
        entry = dynamic_credential_entry("custom.elevenlabs", "access_token")
        surr = str(entry.get("surrogate") or "").strip()
        if surr.startswith("hsurr:"):
            return ("surrogate", surr)
    except Exception:
        pass
    return (None, None)


def delivery_for_beat(beat: dict, category: str):
    """Translate the FULL beat packet (bird-side keys only) into delivery.

    Returns (voice_settings, tag, direction). The tag is a v3 audio tag or
    "". The direction is a SHORT bracketed anti-narrative objective — a few
    punchy words, no internal punctuation (v3 reads long clauses aloud).
    It frames every line as live speech TO her partner, in the moment —
    never a story being narrated. Voice tag + direction + audio tag are
    prepended to the script text.
    """
    vs = {"stability": 0.40, "similarity_boost": 0.80, "style": 0.15,
          "speed": 1.05, "use_speaker_boost": True}
    tag = ""
    # default: live, to-him, not narrating
    direction = "[talking to her lover]"
    jas = beat.get("jasmine") or {}
    her = beat.get("her") or {}
    fin = beat.get("finale") or {}
    pleasure = float(her.get("pleasure") or 0.0)

    if fin.get("aftercare"):
        vs.update(stability=0.65, style=0.05, speed=0.92)
        tag = "[whisper]"
        direction = "[softly murmuring to him]"
    elif fin.get("active"):
        vs.update(stability=0.35, style=0.50, speed=1.05)
        tag = "[excited]"
        direction = "[overwhelmed in the moment]"
    elif beat.get("finale_crest"):
        # v10.4: the escalation loop cresting into the real thing.
        # Checked early: high pleasure would otherwise catch the heated
        # branch below.
        vs.update(stability=0.30, style=0.50, speed=1.10)
        tag = "[excited]"
        direction = "[overwhelmed and cresting]"
    elif category == "escalation":
        # the 😳 feedback loop: flushed-to-meltdown, losing it together
        vs.update(stability=0.30, style=0.50, speed=1.12)
        tag = "[excited]"
        direction = "[flustered and losing it]"
    elif category == "tender_echo":
        # v10.4: she noticed his softsad crack — soft, reaching back
        vs.update(stability=0.60, style=0.20, speed=0.95)
        tag = "[softly]"
        direction = "[softly noticing he's gone quiet]"
    elif category == "r1_mumble":
        vs.update(stability=0.55, style=0.25, speed=0.95)
        tag = "[mumbling]"
        direction = "[mumbling softly trailing off]"
    elif category == "r2_scold":
        vs.update(stability=0.50, style=0.35, speed=1.00)
        tag = ""
        direction = "[scolding him with affection]"
    elif category == "r3_sleepy":
        vs.update(stability=0.60, style=0.20, speed=0.88)
        tag = "[sleepy]"
        direction = "[half asleep barely forming words]"
    elif category == "r4_coverup":
        vs.update(stability=0.45, style=0.40, speed=1.10)
        tag = "[laughs]"
        direction = "[covering a real feeling with a joke]"
    elif category == "r5_documentary":
        vs.update(stability=0.55, style=0.30, speed=1.00)
        tag = ""
        direction = "[narrating him like a nature documentary]"
    elif category == "r6_laugh":
        vs.update(stability=0.45, style=0.45, speed=1.05)
        tag = "[laughing]"
        direction = "[laughing too hard to finish]"
    elif category == "r8_pen":
        vs.update(stability=0.60, style=0.25, speed=0.90)
        tag = "[softly]"
        direction = "[quiet swaying tracing his arm]"
    elif category == "r10_deadpan":
        vs.update(stability=0.60, style=0.15, speed=1.00)
        tag = ""
        direction = "[deadpan direct no theater]"
    elif category == "heated" or pleasure >= 0.75:
        vs.update(stability=0.30, style=0.45, speed=1.10)
        tag = "[excited]"
        direction = "[breathy and desperate for him]"
    elif category == "pout" or jas.get("pouting"):
        vs.update(stability=0.55, style=0.30, speed=0.95)
        tag = "[sighs]"
        direction = "[pouting at him]"
    elif category == "tease":
        vs.update(stability=0.50, style=0.35, speed=1.05)
        tag = "[laughs]"
        direction = "[teasing him playfully]"
    elif category == "toot" or jas.get("toot_pending"):
        vs.update(stability=0.55, style=0.40, speed=1.00)
        tag = "[laughs]"
        direction = "[giggly and unrepentant]"
    elif category == "sweet":
        vs.update(stability=0.60, style=0.20, speed=0.95)
        tag = ""
        direction = "[soft and fond for him]"
    elif category == "taunt":
        vs.update(stability=0.45, style=0.40, speed=1.05)
        tag = ""
        direction = "[smug and edging him]"
    elif category == "giggle":
        vs.update(stability=0.50, style=0.35, speed=1.08)
        tag = "[laughs]"
        direction = "[helplessly giggly]"
    return vs, tag, direction


def mp3_dur_s(path) -> float:
    """Spoken length of a rendered clip. ffprobe when present; else the
    size heuristic (ElevenLabs returns CBR 128kbps MP3, mp3_44100_128).
    Used to pace her lines by spoken length."""
    try:
        import subprocess
        r = subprocess.run(["ffprobe", "-v", "error",
                            "-show_entries", "format=duration",
                            "-of", "default=noprint_wrappers=1:nokey=1",
                            str(path)],
                           capture_output=True, text=True, timeout=10)
        d = float((r.stdout or "").strip())
        if d > 0:
            return d
    except Exception:
        pass
    try:
        return max(0.5, float(os.path.getsize(path)) * 8.0 / 128000.0)
    except Exception:
        return 0.0


def tts_render(text: str, voice_id: str, model: str, vs: dict, tag: str,
               direction: str = ""):
    mode, key = resolve_key()
    if not mode:
        raise RuntimeError("no elevenlabs key (env ELEVENLABS_API_KEY or authd)")
    # Voice tag + short objective + audio tag ride in front of the line so
    # v3 performs it as live speech to her partner — Florida swamp valley,
    # in the moment — never narration. All brackets stay short: v3 reads
    # long multi-clause directions aloud.
    prefix = " ".join(p for p in (VOICE_TAG, direction, tag) if p)
    body_text = f"{prefix} {text}".strip() if (prefix and "v3" in model) else text
    payload = {"text": body_text, "model_id": model, "voice_settings": vs}
    data = json.dumps(payload).encode("utf-8")
    url = f"{API}/{voice_id}?output_format=mp3_44100_128"
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "audio/mpeg")
    if mode == "surrogate":
        req.add_header("xi-api-key", key)  # hsurr:* swapped by authd on egress
    else:
        req.add_header("xi-api-key", key)
    try:
        with urllib.request.urlopen(req, timeout=TTS_TIMEOUT_S) as resp:
            audio = resp.read()
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = (e.read() or b"")[:200].decode("utf-8", "replace")
        except Exception:
            pass
        raise RuntimeError(f"elevenlabs HTTP {e.code}: {detail}")
    if len(audio) < 1000:
        raise RuntimeError(f"elevenlabs returned {len(audio)} bytes")
    return audio


class ElevenLabsWriter(DeckWriter):
    def __init__(self, session: Path, model: str = "eleven_flash_v2_5"):
        super().__init__(session)
        self.model = model
        self.voice_id = resolve_voice_id()
        mode, _ = resolve_key()
        self.key_mode = mode
        print(f"elevenlabs writer: voice={self.voice_id} model={model} "
              f"key={mode}", flush=True)

    def _render_jasmine_ttscli(self, text: str, tag: str, seq: int,
                               category: str):
        """Piper-mode voice for her lines: glossy pendant via the local tts
        CLI, with the pre-rendered voice cache (runner/voice_cache/jasmine)
        checked first so machines without the tts binary still speak.
        Returns (clip filename, dur_s). Raises when neither cache nor the
        tts binary can produce audio."""
        import shutil as _sh
        import subprocess
        self.clips.mkdir(parents=True, exist_ok=True)
        dest = self.clips / f"beat_{tag}.mp3"
        tts_text = jasmine_tts_text(text)
        if not tts_text:
            return None, 0.0
        jkey = _ttscli_cache_key(JASMINE_TTSCLI_VOICE, tts_text)
        JASMINE_VOICE_CACHE.mkdir(parents=True, exist_ok=True)
        jcached = JASMINE_VOICE_CACHE / f"ttscli_{jkey}.mp3"
        if jcached.is_file() and jcached.stat().st_size > 1000:
            _sh.copyfile(jcached, dest)
            dur = self._clip_dur_s(dest)
            print(f"voice-cache hit {seq} ({category}) dur={dur:.1f}s",
                  flush=True)
            return dest.name, dur
        tts_bin = _sh.which("tts")
        if not tts_bin:
            raise RuntimeError("tts binary not on PATH and no cached clip")
        subprocess.run(
            [tts_bin, "speak", "--voice", JASMINE_TTSCLI_VOICE,
             "--text", tts_text, "--output", str(dest)],
            timeout=60, check=True, capture_output=True)
        try:
            _sh.copyfile(dest, jcached)
        except Exception:
            pass
        dur = self._clip_dur_s(dest)
        print(f"tts render {seq} ({category}) dur={dur:.1f}s", flush=True)
        return dest.name, dur

    def render_line(self, lid: str, text: str, beat: dict, category: str):
        """Render one line; return (clip filename, dur_s).

        Primary path is ElevenLabs (her real voice). If the key is missing
        or the API fails, fall back to the offline deck clip for the same
        line id — there is always a voice, never silence.
        """
        seq = int(beat["seq"])
        tag = f"{seq:06d}"
        text = text.strip()
        if len(text) > 600:
            text = text[:597] + "..."
        vs, dtag, direction = delivery_for_beat(beat, category)
        # Circuit breaker: after 3 consecutive ElevenLabs failures
        # (e.g. quota exhausted 2026-09-25), stop burning attempts and
        # go straight to fallback for the rest of the session.
        _el_dead = getattr(self, "_el_dead", False)
        try:
            if _PIPER_MODE:
                # Launcher piper mode: no ElevenLabs at all — her lines
                # go through the tts CLI (glossy pendant), cache first,
                # deck after that.
                clip, dur = self._render_jasmine_ttscli(text, tag, seq,
                                                        category)
                if clip:
                    return clip, dur
                raise RuntimeError("piper mode: tts unavailable, "
                                   "falling back to deck")
            if _el_dead:
                raise RuntimeError("circuit breaker tripped")
            t0 = time.time()
            audio = tts_render(text, self.voice_id, self.model, vs, dtag,
                               direction)
            dest = self.clips / f"beat_{tag}.mp3"
            dest.write_bytes(audio)
            dt = time.time() - t0
            dur = mp3_dur_s(dest)
            self._el_fails = 0
            print(f"rendered {seq} ({category}) dir={direction} tag={dtag or '-'} "
                  f"{len(audio)}b dur={dur:.1f}s in {dt:.1f}s", flush=True)
            return dest.name, dur
        except Exception as e:
            if not _el_dead:
                _fails = getattr(self, "_el_fails", 0) + 1
                self._el_fails = _fails
                print(f"tts failed for {seq}: {e} — deck fallback", flush=True)
                if _fails >= 3:
                    self._el_dead = True
                    print("elevenlabs circuit breaker: TRIPPED", flush=True)
            else:
                print(f"tts skipped for {seq} (circuit breaker)", flush=True)
        # Deck fallback: same line, offline tts clip. Voice never drops.
        # Escalation lines have no pre-rendered deck clips (ElevenLabs-only
        # bit) — fall back to a random heated deck clip instead of silence.
        # Exchange lines (xchg_*) likewise have no pre-rendered clips —
        # fall back to a random clip from the same category.
        try:
            import random as _r2
            src = deck_writer.DECK_DIR / f"{lid}.mp3"
            if not src.exists() and lid.startswith("escalation_"):
                heated = sorted(deck_writer.DECK_DIR.glob("heated_*.mp3"))
                if heated:
                    src = _r2.choice(heated)
            if not src.exists() and lid.startswith("xchg_"):
                # Exchange lines have no pre-rendered deck clip — her line
                # renders via the local tts CLI (glossy pendant, Andrew's
                # pick 2026-09-25) so the words match the on-screen text,
                # voice cache first.
                try:
                    clip, dur = self._render_jasmine_ttscli(
                        text, tag, seq, category)
                    if clip:
                        return clip, dur
                    raise RuntimeError("tts render returned no clip")
                except Exception as e3:
                    print(f"tts fallback failed for {seq}: {e3}",
                          flush=True)
                    # last resort: random category clip (words won't match)
                    cat_clips = sorted(
                        deck_writer.DECK_DIR.glob(f"{category}_*.mp3"))
                    if cat_clips:
                        src = _r2.choice(cat_clips)
            if src.exists():
                import shutil
                self.clips.mkdir(parents=True, exist_ok=True)
                dest = self.clips / f"beat_{tag}.mp3"
                shutil.copyfile(src, dest)
                dur = self._clip_dur_s(dest)
                print(f"deck fallback {seq} ({category}) dur={dur:.1f}s",
                      flush=True)
                return dest.name, dur
        except Exception as e2:
            print(f"deck fallback failed for {seq}: {e2}", flush=True)
        return None, 0.0

    def _her_register_roll(self, cat: str, beat: dict) -> str:
        """v10.4: her 10 registers as routing. R7 vibing ~= heated deck and
        R9 feral ~= feral deck (already the writing), so they need no pool.
        The rest surface as small pools on compatible moods. R10 deadpan can
        cut into anything — funnier when hotter, so its chance scales with
        her heat. ElevenLabs-only; deck mode never calls this."""
        import random as _r
        her = beat.get("her") or {}
        try:
            pleasure = float(her.get("pleasure") or 0.0)
        except Exception:
            pleasure = 0.0
        if _r.random() < 0.03 + pleasure * 0.05:
            return "r10_deadpan"
        if cat in ("tease", "taunt"):
            r = _r.random()
            if r < 0.10:
                return "r5_documentary"
            if r < 0.18:
                return "r2_scold"
            if cat == "tease":
                r = _r.random()
                if r < 0.08:
                    return "r1_mumble"
                if r < 0.15:
                    return "r4_coverup"
                if r < 0.22:
                    return "r6_laugh"
        elif cat in ("sweet", "giggle"):
            r = _r.random()
            if r < 0.10:
                return "r1_mumble"
            if r < 0.18:
                return "r4_coverup"
            if cat == "giggle" and r < 0.25:
                return "r6_laugh"
        elif cat == "heated":
            if _r.random() < 0.10:
                return "r8_pen"
        if pleasure < 0.30 and _r.random() < 0.08:
            return "r3_sleepy"
        return cat

    def answer(self, beat: dict):
        seq = int(beat["seq"])
        tag = f"{seq:06d}"
        reply = {"seq": seq}
        kind = beat.get("beat")
        jas = beat.get("jasmine") or {}

        if kind == "dialogue":
            cat = self.mood_category(beat)
            # THE ESCALATION BIT (v10.3): the 😳 feedback loop. On heated/
            # feral beats there's a chance her line comes from the shared
            # escalation pool instead — and his reply is forced into the
            # paired fiend escalation pool, so it's a real two-sided bit.
            # cat stays heated/feral (sfx + wet pool still apply); her_cat
            # is what she actually says. ElevenLabs-only: the deck has no
            # pre-rendered escalation clips, and deck mode never picks it.
            #
            # v10.4 additions, in priority order:
            #  1. TENDER ECHO: his softsad crack sets a flag; her NEXT line
            #     is forced soft — she noticed. His reply to the echo is
            #     forced softsad again: a two-beat soft moment, no detours.
            #  2. OFF-RAMP: the loop tracks heat; at the crest threshold
            #     with his state at close/peak (edging or climax ONLY), her
            #     line crests into the finale announce and his reply drops
            #     to melt. The loop finally goes somewhere.
            #  3. HER REGISTERS: R7/R9 already ARE heated/feral; the rest
            #     surface as small pools on compatible moods (R10 can cut
            #     into anything, funnier when hotter).
            import random as _r
            her_cat = cat
            escalation_bit = False
            echo_active = False
            crest_active = False
            fin_active = bool((beat.get("finale") or {}).get("active"))
            ssq = getattr(self, "_softsad_seq", None)
            if ssq is not None:
                if 0 < seq - ssq <= 4 and not fin_active:
                    her_cat = "tender_echo"
                    echo_active = True
                # consumed or expired either way
                self._softsad_seq = None
            if echo_active:
                pass  # her line is the echo; his reply forced below
            elif cat in ("heated", "feral") and _r.random() < escalation_chance():
                fstate = str((beat.get("fiend") or {}).get("state") or "")
                eheat = getattr(self, "_escalation_heat", 0)
                if eheat >= escalation_crest_at() and fstate in ("close", "peak"):
                    route = str((beat.get("finale") or {}).get("route") or "vaginal")
                    if route not in ("vaginal", "anal"):
                        route = "vaginal"
                    her_cat = "finale_announce_" + route
                    beat["finale_crest"] = True
                    crest_active = True
                    self._escalation_heat = 0
                else:
                    her_cat = "escalation"
                    escalation_bit = True
            elif not fin_active:
                her_cat = self._her_register_roll(her_cat, beat)
            # escalation heat: rises on loop beats, cools otherwise
            if escalation_bit:
                self._escalation_heat = getattr(self, "_escalation_heat", 0) + 1
            else:
                self._escalation_heat = max(0, getattr(self, "_escalation_heat", 0) - 1)
            # EXCHANGE DOCTRINE (dialogue_direction.md): her line + his
            # reply are one authored conversation. Pick the exchange
            # first so his half is available below; legacy pools only
            # where no exchange exists for the category.
            xchg = None
            _xid, _xp = pick_exchange(her_cat, self._xchg_used)
            if _xp is not None:
                xchg = _xp
                lid, text = _xid, xchg["her"]
            else:
                lid, text = self.pick(her_cat)
            clip, dur = self.render_line(lid, text, beat, her_cat)
            if clip:
                reply["clip"] = clip
                reply["dur_s"] = round(dur, 2)
            reply["line"] = text
            jas = beat.get("jasmine") or {}
            if cat == "pout" and not jas.get("pouting"):
                import random as _r
                if _r.random() < 0.5:
                    reply["action"] = {"pout": True}
            sfx = self._maybe_sfx(her_cat, beat)
            if sfx:
                reply["sfx"] = sfx
            # FIEND EXCHANGE (v10 rework): every dialogue beat is a real
            # conversation — her line + his reply as a unit. His mood answers
            # her category (switchplay loop); ~15% of the time HE opens and
            # she answers. His clip lands right after hers in the manifest
            # (or before, when he opens — reply["fiend_first"]). His text
            # never enters "line" — invisible dialogue, voice only.
            try:
                import random as _rf
                ftext = None
                # EXCHANGE DOCTRINE: the pair is one conversation — his
                # half always plays, exactly as authored. No mood rolls,
                # no ledger appends; the exchange IS the unit.
                if xchg is not None:
                    fmood = xchg.get("him_mood") or "tease_back"
                    fiend_first = bool(xchg.get("fiend_first"))
                    ftext = xchg["him"]
                    # his softsad crack still arms her tender echo — the
                    # two-beat soft moment survives the doctrine.
                    if fmood == "softsad" and her_cat != "tender_echo":
                        self._softsad_seq = seq
                elif _rf.random() < fiend_chance():
                    if not hasattr(self, "_fiend_used"):
                        self._fiend_used = set()
                    fmood = FIEND_RESPONSE_MAP.get(cat, "tease_back")
                    fiend_first = False
                    if echo_active:
                        # v10.4 tender echo: she reached back soft — he
                        # answers soft. No detours; the moment is the point.
                        fmood = "softsad"
                    elif crest_active:
                        # v10.4 off-ramp: the loop crested — overwhelmed awe
                        fmood = "melt"
                    elif escalation_bit:
                        # paired bit: his reply comes from the escalation
                        # pool. No opener/softsad/ledger detours — the bit
                        # IS the detour. She starts, he loses it.
                        fmood = "escalation"
                    elif _rf.random() < FIEND_OPENER_CHANCE:
                        fmood = "opener"
                        fiend_first = True
                    elif _rf.random() < fiend_softsad_chance():
                        # R6: the bit cracks. Ash Lynx showing through the
                        # costume for one line, inside any exchange. Never
                        # as an opener — the softsad is a crack in the reply.
                        fmood = "softsad"
                    elif (fmood in ("tease_back", "opener")
                            and seq <= daylife_seq_max()
                            and _rf.random() < daylife_chance()):
                        # v10.4 daylife: early in the night he asks about
                        # HER day — art school, Priya, the dim square. He
                        # lives in her world, not just visits it.
                        fmood = "daylife"
                    ftext = _fiend_pool.pick(fmood, self._fiend_used)
                    # v10.4: his softsad crack arms the tender echo — her
                    # next line goes soft. Not when the line already IS the
                    # echo (no infinite soft loop).
                    if fmood == "softsad" and her_cat != "tender_echo":
                        self._softsad_seq = seq
                    # THE LEDGER (v10.2): semi-common bit finishers. His
                    # reply ends in sudden honest fluster (devotion) or the
                    # personified beast bit — appended to the SAME clip so
                    # the bit lands in one breath. Flavor follows his mood:
                    # playful moods get beast-or-devotion, sincere moods get
                    # devotion only. Never on softsad — don't puncture R6.
                    # fbase: the line before the ledger bit — the offline
                    # crowned-voice cache only holds base lines, so piper
                    # mode falls back to it when the combo isn't cached.
                    fbase = ftext
                    if (ftext and fmood not in ("softsad", "escalation", "daylife")
                            and not echo_active and not crest_active
                            and _rf.random() < fiend_ledger_chance()):
                        if fmood in ("tease_back", "brat_tamer", "opener"):
                            lmood = ("ledger_beast" if _rf.random() < 0.45
                                     else "ledger_devotion")
                        else:
                            lmood = "ledger_devotion"
                        ltext = _fiend_pool.pick(lmood, self._fiend_used)
                        if ltext:
                            ftext = ftext.rstrip() + " " + ltext
                if ftext:
                    fvid = _resolve_fiend_voice_id()
                    try:
                        if getattr(self, "_el_dead", False):
                            # Breaker tripped: ElevenLabs is dead, but he
                            # still speaks — straight to his offline voice,
                            # no wasted API attempts.
                            faudio = _render_fiend_ttscli(ftext)
                        else:
                            faudio = render_fiend_line(
                                ftext, fvid, fmood, self.model)
                    except Exception:
                        if ftext != fbase and (_PIPER_MODE or getattr(
                                self, "_el_dead", False)):
                            # Offline crowned voice: the ledger combo is
                            # composed at runtime so it won't be in the
                            # pre-rendered cache — fall back to the base
                            # line's clip rather than skipping his reply.
                            faudio = _render_fiend_ttscli(fbase)
                        else:
                            raise
                    fdest = self.clips / f"fiend_{tag}.mp3"
                    fdest.write_bytes(faudio)
                    fdur = mp3_dur_s(fdest)
                    reply["fiend_clip"] = fdest.name
                    reply["fiend_dur_s"] = round(fdur, 2)
                    reply["fiend_mood"] = fmood
                    if fiend_first:
                        reply["fiend_first"] = True
                    print(f"fiend {seq} [{fmood}]{' (opens)' if fiend_first else ''}: {ftext!r} dur={fdur:.1f}s", flush=True)
            except Exception as e:
                print(f"fiend exchange skipped for {seq}: {e}", flush=True)
        else:  # action beat
            action = self.agency_play(beat) or {}
            # her body tells the truth: forward tracked sweat/musk every action
            # beat so beads/wisps follow her actual heat (overlay defaults on).
            try:
                _sw = float(jas.get("sweat") or 0.0)
                _mu = float(jas.get("musk") or 0.0)
            except Exception:
                _sw, _mu = 0.0, 0.0
            if _sw > 0.5 or _mu > 0.5:
                action = {"body": {"sweat": round(_sw, 1), "musk": round(_mu, 1)},
                          **action}
            if action:
                reply["action"] = action
            import random as _r
            if _r.random() < 0.40:
                lid, text = self.pick("action")
                clip, dur = self.render_line(lid, text, beat, "action")
                if clip:
                    reply["clip"] = clip
                    reply["dur_s"] = round(dur, 2)
                reply["line"] = text
                sfx = self._maybe_sfx("action", beat)
                if sfx:
                    reply["sfx"] = sfx

        # v10.4.1: pace on the whole exchange, not just her line. The
        # browser plays her clip then his reply back-to-back (slight
        # step-over); pacing on her duration alone let the writer run
        # ahead and pile beats onto each other.
        _vd = float(reply.get("dur_s") or 0.0) + float(reply.get("fiend_dur_s") or 0.0)
        if _vd > 0:
            self._pace_emit(_vd)
        (self.outbox / f"reply_{tag}.json").write_text(json.dumps(reply))
        print(f"replied {seq} ({kind}) line={bool(reply.get('line'))} "
              f"clip={bool(reply.get('clip'))} action={reply.get('action')}",
              flush=True)


def main():
    if "--probe-key" in sys.argv:
        # launcher hook: print key mode (env|surrogate|none), no session needed
        mode, _ = resolve_key()
        print(mode or "none")
        sys.exit(0)
    if len(sys.argv) < 2:
        print("usage: elevenlabs_writer.py <session-dir> [--model ID]")
        sys.exit(1)
    model = "eleven_v3"
    if "--model" in sys.argv:
        model = sys.argv[sys.argv.index("--model") + 1]
    # test hook: WRITER_MAX_RUNTIME_S
    try:
        deck_writer.MAX_RUNTIME_S = float(
            os.environ.get("WRITER_MAX_RUNTIME_S", 45 * 60))
    except Exception:
        pass
    ElevenLabsWriter(Path(sys.argv[1]), model=model).run()


if __name__ == "__main__":
    main()
