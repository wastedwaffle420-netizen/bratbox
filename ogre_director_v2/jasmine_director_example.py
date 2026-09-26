#!/usr/bin/env python3
"""Minimal director. Run BEFORE or after the game (game retries every 2s):
    python3 jasmine_director_example.py [fifo_dir]
Game: JASMINE_DIRECTOR=1 JASMINE_SLOWMO=5 python3 ogre_shader_v5.py
Replace decide() with your model call; keep it under JASMINE_DIRECTOR_WAIT_MS (default 250)."""
import json, os, sys
d = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.environ.get("LOCKKEY_USER_DATA", "user_data"), "director")
os.makedirs(d, exist_ok=True)
for n in ("game_to_director.fifo", "director_to_game.fifo"):
    if not os.path.exists(os.path.join(d, n)): os.mkfifo(os.path.join(d, n), 0o600)

def decide(s):
    """s = state dict from the game. Return {"line":..., "action":...} or None (= let the pool line play)."""
    if s["beat"] != "dialogue": return None
    if s["her"]["composure"] < 0.3:
        return {"line": "...don't stop. Please.", "action": {"pose": "squat", "hold": 2.5}}
    return None

while True:
    with open(os.path.join(d, "game_to_director.fifo"), "r") as rx, open(os.path.join(d, "director_to_game.fifo"), "w") as tx:
        for raw in rx:
            try: s = json.loads(raw)
            except ValueError: continue
            print(s["seq"], s["beat"], s.get("candidate", {}).get("text", ""), flush=True)
            r = decide(s)
            if r: r["seq"] = s["seq"]; tx.write(json.dumps(r) + "\n"); tx.flush()
