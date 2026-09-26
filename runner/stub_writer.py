#!/usr/bin/env python3
"""Stub writer for plumbing test: replies STUB LINE <seq> to dialogue beats,
action-only acks to action beats. Renders TTS for the first dialogue beat."""
import json, subprocess, sys, time
from pathlib import Path

SESSION = Path(sys.argv[1])
INBOX, OUTBOX, CLIPS = SESSION/"inbox", SESSION/"outbox", SESSION/"clips"
tts_done = False
deadline = time.time() + 240
while time.time() < deadline:
    beats = sorted(INBOX.glob("beat_*.json"))
    if not beats:
        time.sleep(0.5); continue
    for bf in beats:
        try:
            beat = json.loads(bf.read_text())
        except Exception:
            bf.unlink(missing_ok=True); continue
        seq = beat["seq"]; tag = f"{seq:06d}"
        reply = {"seq": seq}
        if beat.get("beat") == "dialogue":
            reply["line"] = f"STUB LINE {seq}"
            if not tts_done:
                tts_done = True
                out = CLIPS / f"beat_{tag}.mp3"
                try:
                    subprocess.run(["tts","speak","--voice","avocado_v2:marisol",
                                    "--text", reply["line"], "--output", str(out)],
                                   timeout=90, check=True, capture_output=True)
                    reply["clip"] = out.name
                    print(f"tts rendered for {seq}", flush=True)
                except Exception as e:
                    print(f"tts failed: {e}", flush=True)
        else:
            reply["action"] = {"flash": True}
        (OUTBOX/f"reply_{tag}.json").write_text(json.dumps(reply))
        bf.unlink(missing_ok=True)
        print(f"replied {seq} ({beat.get('beat')})", flush=True)
print("stub done", flush=True)
