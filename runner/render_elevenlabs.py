#!/usr/bin/env python3
"""Render a Jasmine line with her real ElevenLabs voice.

Usage:
    render_elevenlabs.py "<text>" <output.mp3> [--model eleven_flash_v2_5]

Env:
    ELEVENLABS_API_KEY  — her ElevenLabs API key (never logged, never stored here)
    JASMINE_VOICE_ID    — the voice id of the original Jasmine voice

Defaults are tuned for live beats: eleven_flash_v2_5 (~75ms first byte,
half the credit cost of v2) with expressive-but-stable voice settings.
Pass --model eleven_v3 for maximum expressiveness (slower, full credit cost).

Exit 0 on success (output is a real mp3 >1kB), non-zero on failure.
"""
import json
import os
import sys
import urllib.request

API = "https://api.elevenlabs.io/v1/text-to-speech"

# fast-but-savoring: she talks fast and melts her vowels. Slightly quick,
# expressive stability, strong similarity to the source voice.
DEFAULT_SETTINGS = {
    "stability": 0.40,
    "similarity_boost": 0.80,
    "style": 0.15,
    "use_speaker_boost": True,
    "speed": 1.05,
}


def main():
    if len(sys.argv) < 3:
        print("usage: render_elevenlabs.py \"<text>\" <output.mp3> [--model ID]",
              file=sys.stderr)
        sys.exit(2)
    text, out = sys.argv[1], sys.argv[2]
    model = "eleven_flash_v2_5"
    if "--model" in sys.argv:
        model = sys.argv[sys.argv.index("--model") + 1]

    key = os.environ.get("ELEVENLABS_API_KEY", "")
    voice_id = os.environ.get("JASMINE_VOICE_ID", "")
    if not key or not voice_id:
        print("ELEVENLABS_API_KEY and JASMINE_VOICE_ID must both be set",
              file=sys.stderr)
        sys.exit(2)

    body = json.dumps({
        "text": text,
        "model_id": model,
        "voice_settings": DEFAULT_SETTINGS,
    }).encode()
    req = urllib.request.Request(
        f"{API}/{voice_id}?output_format=mp3_44100_128",
        data=body,
        headers={"xi-api-key": key, "Content-Type": "application/json",
                 "Accept": "audio/mpeg"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            audio = resp.read()
    except Exception as e:
        # never print the key; the exception message shouldn't contain it,
        # but strip defensively anyway
        msg = str(e).replace(key, "[redacted]")
        print(f"elevenlabs tts failed: {msg}", file=sys.stderr)
        sys.exit(1)

    if len(audio) < 1000 or not audio.startswith(b"ID3") and not audio[:2] == b"\xff\xfb":
        # not obviously an mp3 — still write it for debugging, but fail
        print(f"elevenlabs returned {len(audio)} bytes, doesn't look like mp3",
              file=sys.stderr)
        sys.exit(1)
    with open(out, "wb") as f:
        f.write(audio)
    print(f"ok {out} ({len(audio)} bytes, model={model})")


if __name__ == "__main__":
    main()
