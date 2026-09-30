#!/usr/bin/env python3
"""Bratbox launcher — tkinter GUI.

First-run (and settings) UI for voice mode selection and API key entry.
Saves to %APPDATA%/bratbox/config.json (Windows) or ~/.config/bratbox/config.json.

Voice modes:
  voiceless  — no TTS, just the game. Zero setup.
  elevenlabs — live synthesis via ElevenLabs API. Needs API key.
  cache      — offline playback from previously synthesized lines.

The launcher writes the config then spawns the game. The game itself
reads the config (or Windows env vars as fallback).
"""
import json
import os
import sys
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path


def config_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", str(Path.home())))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    d = base / "bratbox"
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_path() -> Path:
    return config_dir() / "config.json"


DEFAULTS = {
    "voice_mode": "voiceless",
    "elevenlabs_api_key": "",
    "bird_voice_id": "",   # empty = use built-in default
    "fiend_voice_id": "",  # empty = use built-in default
    "input_offset_ms": 0,
    "bed_sounds": True,    # intimacy bed loop under everything
}


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    try:
        p = config_path()
        if p.exists():
            loaded = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                cfg.update({k: loaded[k] for k in DEFAULTS if k in loaded})
    except Exception:
        pass
    # Windows env var fallback for the API key
    if not cfg.get("elevenlabs_api_key"):
        cfg["elevenlabs_api_key"] = os.environ.get("ELEVENLABS_API_KEY", "")
    return cfg


def save_config(cfg: dict) -> None:
    p = config_path()
    # Only persist known keys
    out = {k: cfg.get(k, DEFAULTS[k]) for k in DEFAULTS}
    p.write_text(json.dumps(out, indent=2), encoding="utf-8")


class Launcher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("bratbox")
        self.geometry("380x570")
        self.resizable(False, False)
        self.cfg = load_config()

        # Dark theme matching the game's vibe
        bg = "#0b0710"
        fg = "#e8c8e0"
        accent = "#ff9ecf"
        self.configure(bg=bg)

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg, font=("Consolas", 10))
        style.configure("TRadiobutton", background=bg, foreground=fg, font=("Consolas", 10))
        style.configure("TCheckbutton", background=bg, foreground=fg, font=("Consolas", 10))
        style.configure("TButton", font=("Consolas", 11, "bold"))
        style.configure("TEntry", fieldbackground="#1a1022", foreground=fg)

        main = ttk.Frame(self, padding=24)
        main.pack(fill="both", expand=True)

        title = ttk.Label(main, text="BRATBOX", font=("Consolas", 24, "bold"), foreground=accent)
        title.pack(pady=(0, 4))
        ttk.Label(main, text="how should she sound?", font=("Consolas", 11)).pack(pady=(0, 12))

        self.mode_var = tk.StringVar(value=self.cfg.get("voice_mode", "voiceless"))
        modes = [
            ("voiceless", "Voiceless — just the game.\nStill fun, zero setup."),
            ("elevenlabs", "My ElevenLabs key — live voices.\nBest quality, needs API key."),
            ("cache", "My cache — offline voices.\nFrom your previous sessions."),
            ("piper", "Piper TTS — offline crowned voices.\nGlossy pendant + Sparkling Bracelet. No key —\nneeds the crowned voice cache pack in runner/voice_cache."),
        ]
        for val, label in modes:
            rb = ttk.Radiobutton(main, text=label, variable=self.mode_var, value=val,
                                 command=self._on_mode_change)
            rb.pack(anchor="w", pady=4)

        # Bed loop toggle (ultimate-bratbox sensory layer). The intimacy
        # bed loops under everything once he's in intimate territory —
        # hot, but not everyone's thing, so it's a real switch.
        bed_frame = ttk.Frame(main)
        bed_frame.pack(fill="x", pady=(10, 0))
        self.bed_var = tk.BooleanVar(value=bool(self.cfg.get("bed_sounds", True)))
        bed_cb = ttk.Checkbutton(bed_frame, text="Bed loop",
                                 variable=self.bed_var)
        bed_cb.pack(anchor="w")
        ttk.Label(bed_frame, text="the intimacy bed under everything",
                  font=("Consolas", 8), foreground="#8d7499").pack(anchor="w")

        # API key section
        self.key_frame = ttk.Frame(main)
        self.key_frame.pack(fill="x", pady=(12, 0))
        ttk.Label(self.key_frame, text="ElevenLabs API key:").pack(anchor="w")
        key_row = ttk.Frame(self.key_frame)
        key_row.pack(fill="x", pady=4)
        self.key_var = tk.StringVar(value=self.cfg.get("elevenlabs_api_key", ""))
        self.key_entry = ttk.Entry(key_row, textvariable=self.key_var, show="•", width=28)
        self.key_entry.pack(side="left", fill="x", expand=True)
        self.show_key = tk.BooleanVar(value=False)
        ttk.Button(key_row, text="👁", width=3,
                   command=self._toggle_key).pack(side="left", padx=(4, 0))

        # Voice IDs (optional)
        ttk.Label(self.key_frame, text="Her voice ID (optional):").pack(anchor="w", pady=(8, 0))
        self.bird_var = tk.StringVar(value=self.cfg.get("bird_voice_id", ""))
        ttk.Entry(self.key_frame, textvariable=self.bird_var, width=32).pack(fill="x", pady=4)
        ttk.Label(self.key_frame, text="His voice ID (optional):").pack(anchor="w")
        self.fiend_var = tk.StringVar(value=self.cfg.get("fiend_voice_id", ""))
        ttk.Entry(self.key_frame, textvariable=self.fiend_var, width=32).pack(fill="x", pady=4)
        ttk.Label(self.key_frame, text="blank = the good defaults",
                  font=("Consolas", 8), foreground="#8d7499").pack(anchor="w")

        # Input calibration
        cal_frame = ttk.Frame(main)
        cal_frame.pack(fill="x", pady=(12, 0))
        ttk.Label(cal_frame, text="Input offset (ms):").pack(side="left")
        self.offset_var = tk.StringVar(value=str(self.cfg.get("input_offset_ms", 0)))
        ttk.Entry(cal_frame, textvariable=self.offset_var, width=8).pack(side="left", padx=(8, 0))
        ttk.Label(cal_frame, text="+ = you hit late",
                  font=("Consolas", 8), foreground="#8d7499").pack(side="left", padx=(8, 0))

        # Play button
        play = ttk.Button(main, text="▶  PLAY", command=self._play)
        play.pack(fill="x", pady=(20, 0))

        self._on_mode_change()

    def _toggle_key(self):
        self.show_key.set(not self.show_key.get())
        self.key_entry.configure(show="" if self.show_key.get() else "•")

    def _on_mode_change(self):
        mode = self.mode_var.get()
        # Only show key fields for elevenlabs mode
        if mode == "elevenlabs":
            self.key_frame.pack(fill="x", pady=(12, 0))
        else:
            self.key_frame.pack_forget()

    def _play(self):
        mode = self.mode_var.get()
        cfg = {
            "voice_mode": mode,
            "elevenlabs_api_key": self.key_var.get().strip(),
            "bird_voice_id": self.bird_var.get().strip(),
            "fiend_voice_id": self.fiend_var.get().strip(),
            "input_offset_ms": self._parse_offset(),
            "bed_sounds": bool(self.bed_var.get()),
        }
        if mode == "elevenlabs" and not cfg["elevenlabs_api_key"]:
            messagebox.showwarning("bratbox",
                "ElevenLabs mode needs an API key.\n\n"
                "Paste your key, or pick Voiceless to play without voices.")
            return
        if mode == "cache" and not self._cache_has_voices():
            messagebox.showwarning("bratbox",
                "Your cache is empty.\n\n"
                "Play with an ElevenLabs key first — every line you hear "
                "gets saved, and then you can go offline.")
            return
        save_config(cfg)
        self.destroy()
        launch_game(cfg)

    def _parse_offset(self) -> int:
        try:
            return int(self.offset_var.get().strip() or "0")
        except ValueError:
            return 0

    def _cache_has_voices(self) -> bool:
        d = config_dir() / "voice_cache"
        try:
            return d.exists() and any(d.glob("*.wav"))
        except Exception:
            return False


def launch_game(cfg: dict):
    """Set env vars from config and spawn the game."""
    env = dict(os.environ)
    env["BRATBOX_VOICE_MODE"] = cfg["voice_mode"]
    if cfg["elevenlabs_api_key"]:
        env["ELEVENLABS_API_KEY"] = cfg["elevenlabs_api_key"]
    if cfg["bird_voice_id"]:
        env["ELEVENLABS_VOICE_ID_BIRD"] = cfg["bird_voice_id"]
    if cfg["fiend_voice_id"]:
        env["ELEVENLABS_VOICE_ID_FIEND"] = cfg["fiend_voice_id"]
    env["BRATBOX_INPUT_OFFSET_MS"] = str(cfg.get("input_offset_ms", 0))
    # Intimacy bed loop toggle (launcher checkbox). The director and the
    # offline operator both honor it; off = the bed never starts.
    env["BRATBOX_BED_LOOP"] = "1" if cfg.get("bed_sounds", True) else "0"
    # Point the voice cache at appdata so it's user-local, not bundled
    env["LOCKKEY_VOICE_CACHE_DIR"] = str(config_dir() / "voice_cache")

    # Find the game entry point (works both in dev and in PyInstaller bundle)
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent

    # The game is launched via the runner (same as run_elevenlabs.bat)
    runner = base / "runner"
    game_py = base / "ogre_director_v2" / "ogre_shader_v5.py"

    # For now, delegate to the .bat-equivalent Python startup
    # (PyInstaller build will inline this)
    import runpy
    # Set up session dir
    from datetime import datetime
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session = runner / "runs" / stamp
    session.mkdir(parents=True, exist_ok=True)
    env["BRATBOX_SESSION"] = str(session)
    env["JASMINE_FIFO_DIR"] = str(session / "fifo")
    env["BRATBOX_UNBROKEN"] = "1"
    env["BRATBOX_RHYTHM_ONLY"] = "1"
    env["LOCKKEY_INTENSITY"] = "rough"
    env["LOCKKEY_OGRE_EXPERIENCE_MODE"] = "elastic_grotesque"
    env["JASMINE_DIRECTOR"] = "1"

    # Spawn director + writer as subprocesses, game in foreground
    # In a frozen exe, we re-invoke ourselves with mode flags.
    # In dev, we use sys.executable (python) with the launcher's mode flags.
    exe = sys.executable
    base_args = []
    if getattr(sys, "frozen", False):
        # Frozen: exe handles --run-* flags directly
        pass
    else:
        # Dev: python launcher.py --run-*
        base_args = [str(Path(__file__).resolve())]

    def _spawn(mode: str, session: str, logname: str | None = None,
               extra_env: dict | None = None):
        # Subprocess chatter goes to a session log file, never DEVNULL —
        # a silent writer/director is undiagnosable (2026-09-30: piper
        # mode failed voiceless with zero trace because of DEVNULL).
        cmd = [exe] + base_args + [mode, session]
        penv = dict(env)
        if extra_env:
            penv.update(extra_env)
        if logname:
            logf = open(Path(session) / logname, "a", buffering=1)
            return subprocess.Popen(cmd, env=penv,
                stdout=logf, stderr=subprocess.STDOUT)
        return subprocess.Popen(cmd, env=penv,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    director = _spawn("--run-director", str(session), "director_stdout.log")
    writer = None
    # piper mode renders live via the local tts CLI (crowned voices) with
    # the pre-rendered deck as fallback — no ElevenLabs key involved.
    if cfg["voice_mode"] in ("elevenlabs", "cache", "piper"):
        extra = ({"LOCKKEY_OFFLINE": "1"}
                 if cfg["voice_mode"] == "cache" else None)
        writer = _spawn("--run-writer", str(session), "writer_stdout.log",
                        extra)
    try:
        # Game in the foreground (inherits our console)
        cmd = [exe] + base_args + ["--run-game"]
        subprocess.run(cmd, env=env)
    finally:
        for p in (director, writer):
            if p:
                try:
                    p.terminate()
                except Exception:
                    pass


def main():
    # Frozen exe subprocess modes (PyInstaller spawns these from the same exe)
    if "--run-director" in sys.argv:
        idx = sys.argv.index("--run-director")
        session = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else ""
        _run_director(session)
        return
    if "--run-writer" in sys.argv:
        idx = sys.argv.index("--run-writer")
        session = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else ""
        _run_writer(session)
        return
    if "--run-game" in sys.argv:
        _run_game()
        return
    # Skip launcher if --skip-launcher (for dev/testing)
    if "--skip-launcher" in sys.argv:
        cfg = load_config()
        launch_game(cfg)
        return
    app = Launcher()
    app.mainloop()


def _run_director(session: str):
    """Entry point for director subprocess (frozen or dev)."""
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent
    sys.path.insert(0, str(base / "runner"))
    sys.argv = ["director.py", "--session", session]
    import runpy
    runpy.run_path(str(base / "runner" / "director.py"), run_name="__main__")


def _run_writer(session: str):
    """Entry point for writer subprocess (frozen or dev)."""
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent
    sys.path.insert(0, str(base / "runner"))
    sys.argv = ["elevenlabs_writer.py", session]
    import runpy
    runpy.run_path(str(base / "runner" / "elevenlabs_writer.py"), run_name="__main__")


def _run_game():
    """Entry point for game subprocess (frozen or dev)."""
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent
    sys.path.insert(0, str(base / "ogre_director_v2"))
    import runpy
    runpy.run_path(str(base / "ogre_director_v2" / "ogre_shader_v5.py"), run_name="__main__")


if __name__ == "__main__":
    main()
