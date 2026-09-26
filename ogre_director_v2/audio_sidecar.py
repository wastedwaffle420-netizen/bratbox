
from __future__ import annotations
import json, math, os, random, struct, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUN_DIR = Path(os.environ.get("LOCKKEY_RUN_DIR", str(ROOT/"runs"/"current")))
TELEMETRY = Path(os.environ.get("LOCKKEY_TELEMETRY", str(RUN_DIR/"telemetry.jsonl")))
STOP = RUN_DIR/"audio_sidecar.stop"
STATUS = RUN_DIR/"audio_status.json"

def write_status(**kw):
    try:
        RUN_DIR.mkdir(parents=True, exist_ok=True)
        data={"t":time.time(), **kw}
        STATUS.write_text(json.dumps(data,indent=2),encoding="utf-8")
    except Exception:
        pass

def make_click(pygame, freq=900.0, dur=.045, gain=.45):
    sr=44100; n=max(64,int(sr*dur)); pcm=bytearray()
    for i in range(n):
        t=i/sr
        env=math.exp(-t*48.0)
        x=(math.sin(2*math.pi*freq*t)+0.22*math.sin(2*math.pi*freq*2.03*t))*env*gain
        v=int(max(-1,min(1,x))*32767)
        pcm += struct.pack("<hh",v,v)
    return pygame.mixer.Sound(buffer=bytes(pcm))

def main():
    try:
        import pygame
        pygame.mixer.pre_init(44100,-16,2,512)
        pygame.init()
        if not pygame.mixer.get_init():
            pygame.mixer.init(44100,-16,2,512)
        pygame.mixer.set_num_channels(max(16,pygame.mixer.get_num_channels()))
    except Exception as exc:
        write_status(ok=False,error=f"mixer init: {exc!r}")
        return 2

    tracks=[]
    for base in (ROOT/"music", ROOT/"ost_pack_magnum_opus"):
        if base.exists():
            tracks += sorted(base.rglob("*.wav")) + sorted(base.rglob("*.ogg"))
    if not tracks:
        write_status(ok=False,error="no music files found")
        return 3

    preferred=("build.wav","frenzy.wav","release.wav","climax.wav")
    chosen=next((p for name in preferred for p in tracks if p.name.lower()==name), tracks[0])
    try:
        pygame.mixer.music.load(str(chosen))
        pygame.mixer.music.set_volume(.42)
        pygame.mixer.music.play(-1)
    except Exception as exc:
        write_status(ok=False,error=f"music load: {exc!r}",track=str(chosen))
        return 4

    clicks={
        "A":make_click(pygame,720,.042,.48),
        "S":make_click(pygame,840,.042,.50),
        "D":make_click(pygame,960,.042,.52),
        "F":make_click(pygame,1080,.042,.54),
        "B":make_click(pygame,1000,.042,.52),
        "SPACE":make_click(pygame,1220,.050,.56),
    }
    click_channel=pygame.mixer.Channel(10)
    click_channel.set_volume(.48)

    write_status(ok=True,track=str(chosen),music_busy=bool(pygame.mixer.music.get_busy()))
    offset=0
    while not STOP.exists():
        try:
            if not pygame.mixer.music.get_busy():
                pygame.mixer.music.play(-1)
        except Exception:
            pass
        try:
            if TELEMETRY.exists():
                with TELEMETRY.open("r",encoding="utf-8",errors="ignore") as fh:
                    fh.seek(offset)
                    for line in fh:
                        try:
                            row=json.loads(line)
                        except Exception:
                            continue
                        if str(row.get("event",""))=="NOTE_HIT":
                            lane=str(row.get("lane","S") or "S").upper()
                            snd=clicks.get(lane,clicks["S"])
                            click_channel.play(snd)
                    offset=fh.tell()
        except Exception:
            pass
        time.sleep(.025)
    try:
        pygame.mixer.music.stop()
    except Exception:
        pass
    return 0

if __name__=="__main__":
    raise SystemExit(main())
