#!/usr/bin/env python3
"""
server.py — scene night server (single port).

- Forks the game on a real PTY (pty.fork), tees output to `typescript`.
- Serves the web UI, the TTS clip manifest (/api/clips), the clips
  themselves (/clips/<name>), and /api/status — all over ONE port via the
  `websockets` server's process_request hook.
- Bridges the PTY to browsers over WebSocket (/term?token=...).
- Token auth on /term and /api/* and /clips/* (the URL itself is the secret).

Run with the scene venv (has `websockets`):
    .venv/bin/python runner/server.py --session <dir> --port 18731 --token <tok>
"""
from __future__ import annotations

import argparse
import asyncio
import fcntl
import json
import mimetypes
import os
import pty
import signal
import struct
import sys
import termios
import threading
import time
from http import HTTPStatus
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import websockets
from websockets.http11 import Request, Response
from websockets.datastructures import Headers

started = time.time()
shutdown = False
TOKEN = ""
SESSION = Path(".")
STATIC = Path(".")


def log(*a):
    print(f"[server {time.strftime('%H:%M:%S')}]", *a, flush=True)


def _telemetry_path() -> Path:
    return SESSION / "input_telemetry.jsonl"


def _log_input(key: str = "", voice=None):
    """Append one input-telemetry event. Cheap: open/append/close.

    voice is None (keypress event), a float (legacy broadband energy), or a
    dict {"energy": 0..1, "vocal": 0..1} from the voice-sense squeak detector.
    Only numbers — audio never leaves the browser, nothing is transcribed.
    """
    try:
        ev: dict = {"t": time.time()}
        if voice is None:
            ev["key"] = key[:8]
        else:
            if isinstance(voice, dict):
                ev["voice"] = max(0.0, min(1.0, float(voice.get("energy", 0.0))))
                ev["vocal"] = max(0.0, min(1.0, float(voice.get("vocal", 0.0))))
            else:
                ev["voice"] = max(0.0, min(1.0, float(voice)))
        with open(_telemetry_path(), "a") as f:
            f.write(json.dumps(ev) + "\n")
    except Exception:
        pass


clients: set = set()
client_queues: set = set()
pty_master: int = -1
child_pid: int = -1
loop: asyncio.AbstractEventLoop | None = None
typescript_f = None


def game_alive() -> bool:
    if child_pid <= 0:
        return False
    try:
        pid, _ = os.waitpid(child_pid, os.WNOHANG)
        return pid == 0
    except ChildProcessError:
        return False
    except Exception:
        return True


def set_winsize(fd: int, cols: int, rows: int):
    try:
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
    except Exception:
        pass


def pty_reader():
    """Pump PTY output -> typescript + all WS clients."""
    while not shutdown:
        try:
            data = os.read(pty_master, 65536)
        except OSError:
            break
        if not data:
            break
        try:
            typescript_f.write(data)
            typescript_f.flush()
        except Exception:
            pass
        if loop is not None and client_queues:
            for q in list(client_queues):
                try:
                    loop.call_soon_threadsafe(q.put_nowait, data)
                except Exception:
                    pass


def _json_body(obj) -> bytes:
    return json.dumps(obj).encode()


def _resp(status: int, ctype: str, body: bytes) -> Response:
    return Response(status, HTTPStatus(status).phrase,
                    Headers([("Content-Type", ctype),
                             ("Content-Length", str(len(body)))]), body)


def _json_resp(obj, status: int = 200) -> Response:
    return _resp(status, "application/json", _json_body(obj))


def process_request(connection, request: Request):
    """Plain-HTTP handling inside the websockets server. Return a Response,
    or None to fall through to the WebSocket handler."""
    parsed = urlparse(request.path)
    p = parsed.path
    q = parse_qs(parsed.query)
    needs_auth = p.startswith("/api/") or p.startswith("/clips/")
    if needs_auth and q.get("token", [""])[0] != TOKEN:
        return _json_resp({"error": "bad token"}, 403)

    if p == "/api/status":
        st = {"uptime_s": round(time.time() - started, 1),
              "game_alive": game_alive(),
              "clients": len(clients)}
        sp = SESSION / "director_stats.json"
        if sp.exists():
            try:
                st["director"] = json.loads(sp.read_text()).get("stats")
            except Exception:
                pass
        return _json_resp(st)

    if p == "/api/clips":
        try:
            since = int(q.get("since", ["-1"])[0])
        except ValueError:
            since = -1
        items = []
        mp = SESSION / "clips" / "manifest.jsonl"
        if mp.exists():
            for raw in mp.read_text().splitlines():
                try:
                    e = json.loads(raw)
                except Exception:
                    continue
                if isinstance(e, dict) and e.get("idx", -1) > since:
                    items.append(e)
        return _json_resp({"clips": items})

    # v10.8: gameplay SFX (note hits/misses, squishes). The game appends tiny
    # events to <session>/sfx.jsonl; the browser polls this at ~120ms and
    # plays them immediately — far too timing-sensitive for the 1.5s
    # manifest/voice pump.
    if p == "/api/sfx":
        try:
            since = int(q.get("since", ["-1"])[0])
        except ValueError:
            since = -1
        items = []
        sp = SESSION / "sfx.jsonl"
        if sp.exists():
            for raw in sp.read_text().splitlines():
                try:
                    e = json.loads(raw)
                except Exception:
                    continue
                if isinstance(e, dict) and e.get("idx", -1) > since:
                    items.append(e)
        return _json_resp({"sfx": items})

    if p == "/api/voice_energy":
        # Optional mic telemetry for the fiend-arousal model.
        # Only ever receives data when he toggles "voice sense" on in the UI.
        # The browser sends two numbers — loudness and a vocalization score
        # (squeak detector). No audio, no transcription, ever.
        try:
            body = json.loads(getattr(request, "body", None) or b"{}")
            v = {"energy": float(body.get("energy", 0.0)),
                 "vocal": float(body.get("vocal", 0.0))}
        except Exception:
            v = 0.0
        _log_input(voice=v)
        return _json_resp({"ok": True})

    if p.startswith("/clips/"):
        name = p[len("/clips/"):]
        if "/" in name or name.startswith(".") or ".." in name:
            return _resp(400, "text/plain", b"bad name")
        fp = SESSION / "clips" / name
        if not fp.exists():
            return _resp(404, "text/plain", b"not found")
        data = fp.read_bytes()
        ctype = mimetypes.guess_type(name)[0] or "audio/mpeg"
        return _resp(200, ctype, data)

    if p == "/term":
        return None  # websocket handler does its own token check

    # static files
    rel = "index.html" if p == "/" else p.lstrip("/")
    fp = STATIC / rel
    if ".." in rel or not fp.exists() or not fp.is_file():
        return _resp(404, "text/plain", b"not found")
    data = fp.read_bytes()
    ctype = mimetypes.guess_type(str(fp))[0] or "application/octet-stream"
    return _resp(200, ctype, data)


async def _ws_sender(ws, myq: asyncio.Queue):
    try:
        while True:
            data = await myq.get()
            await ws.send(data)
    except (asyncio.CancelledError, websockets.ConnectionClosed):
        pass


async def term_ws(connection):
    parsed = urlparse(connection.request.path)
    q = parse_qs(parsed.query)
    if parsed.path != "/term" or q.get("token", [""])[0] != TOKEN:
        await connection.close(code=4403, reason="bad token")
        return
    myq: asyncio.Queue = asyncio.Queue()
    client_queues.add(myq)
    clients.add(connection)
    log("client connected", connection.remote_address)
    sender = asyncio.ensure_future(_ws_sender(connection, myq))
    try:
        async for msg in connection:
            if isinstance(msg, bytes):
                try:
                    os.write(pty_master, msg)
                except OSError:
                    break
                # input telemetry for her agency (brat score, fiend arousal)
                try:
                    _log_input(msg.decode("utf-8", "replace"))
                except Exception:
                    pass
            else:
                try:
                    obj = json.loads(msg)
                except Exception:
                    continue
                if isinstance(obj, dict) and obj.get("type") == "resize":
                    try:
                        set_winsize(pty_master, int(obj.get("cols", 130)), int(obj.get("rows", 42)))
                        if child_pid > 0:
                            os.kill(child_pid, signal.SIGWINCH)
                    except Exception:
                        pass
    except websockets.ConnectionClosed:
        pass
    finally:
        sender.cancel()
        client_queues.discard(myq)
        clients.discard(connection)
        log("client disconnected")


async def amain(port: int):
    global loop
    loop = asyncio.get_running_loop()
    async with websockets.serve(term_ws, "127.0.0.1", port,
                                max_size=2 ** 20, ping_interval=20,
                                process_request=process_request):
        log(f"listening on 127.0.0.1:{port}")
        while not shutdown:
            await asyncio.sleep(0.5)


def main() -> int:
    global pty_master, child_pid, typescript_f, shutdown, TOKEN, SESSION, STATIC
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", required=True)
    ap.add_argument("--port", type=int, default=18731)
    ap.add_argument("--token", required=True)
    ap.add_argument("--game-dir", required=True)
    ap.add_argument("--cols", type=int, default=130)
    ap.add_argument("--rows", type=int, default=42)
    ap.add_argument("--wait-ms", type=int, default=30000)
    args = ap.parse_args()

    sess = Path(args.session)
    sess.mkdir(parents=True, exist_ok=True)
    TOKEN = args.token
    SESSION = sess
    STATIC = Path(__file__).resolve().parent / "static"

    # v10.8: stage the squish pool where the browser can fetch it. The game
    # names sfx_squish_<0-3>.mp3 in its sfx events; the /clips/ route serves
    # them like any other clip.
    try:
        _gooey = (Path(__file__).resolve().parent.parent / "ogre_director_v2"
                  / "assets" / "audio" / "jasmine" / "squish" / "gooey")
        _takes = sorted(_gooey.glob("*.mp3"))[:4]
        _clips = sess / "clips"
        _clips.mkdir(parents=True, exist_ok=True)
        for _i, _src in enumerate(_takes):
            _dst = _clips / f"sfx_squish_{_i}.mp3"
            if not _dst.exists():
                _dst.write_bytes(_src.read_bytes())
    except Exception as _e:
        log(f"squish staging failed: {_e}")

    env = dict(os.environ)
    env.update({
        "TERM": "xterm-256color",
        "JASMINE_DIRECTOR": "1",
        "JASMINE_SLOWMO": os.environ.get("JASMINE_SLOWMO", "1"),
        "JASMINE_DIRECTOR_WAIT_MS": str(args.wait_ms),
        "JASMINE_FIFO_DIR": str(sess / "fifo"),
        "JASMINE_VOICE_GAP_S": os.environ.get("JASMINE_VOICE_GAP_S", "0.4"),
        "JASMINE_AUDIO_ONLY": os.environ.get("JASMINE_AUDIO_ONLY", "1"),
    })

    typescript_f = open(sess / "typescript", "ab", buffering=0)

    child_pid, pty_master = pty.fork()
    if child_pid == 0:
        os.chdir(args.game_dir)
        os.execvpe("python3", ["python3", "ogre_shader_v5.py"], env)

    set_winsize(pty_master, args.cols, args.rows)
    log(f"game pid={child_pid} master={pty_master}")

    reader = threading.Thread(target=pty_reader, daemon=True)
    reader.start()

    try:
        asyncio.run(amain(args.port))
    except KeyboardInterrupt:
        pass
    finally:
        shutdown = True
        try:
            if child_pid > 0:
                os.kill(child_pid, signal.SIGTERM)
        except Exception:
            pass
        try:
            (sess / "server_down").write_text(str(time.time()))
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
