#!/usr/bin/env python3
"""Headless plumbing test: stub writer + scripted keys via WS."""
import asyncio, json, os, sys, time
from pathlib import Path
import websockets

SESSION = Path(sys.argv[1])
TOKEN = (SESSION / "token").read_text().strip()
PORT = json.loads((SESSION / "session.json").read_text())["port"]

async def drive():
    uri = f"ws://127.0.0.1:{PORT}/term?token={TOKEN}"
    async with websockets.connect(uri, max_size=2**20) as ws:
        print("WS connected", flush=True)
        async def drain():
            try:
                async for _ in ws:
                    pass
            except Exception:
                pass
        asyncio.ensure_future(drain())
        keys = [" ", "\r", "1", "2", "3", " ", "\r", "1"]
        for i in range(40):
            k = keys[i % len(keys)]
            await ws.send(k.encode())
            print(f"sent key {k!r}", flush=True)
            await asyncio.sleep(6)
        print("drive done", flush=True)

asyncio.run(drive())
