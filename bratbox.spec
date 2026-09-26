# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for bratbox.exe

Builds a single-file executable with tkinter launcher GUI.
The launcher spawns game subprocesses from the same exe.

Build with: pyinstaller bratbox.spec
"""
import sys
from pathlib import Path

HERE = Path(SPECPATH)
BRATBOX = HERE

a = Analysis(
    [str(BRATBOX / "launcher.py")],
    pathex=[str(BRATBOX)],
    binaries=[],
    datas=[
        # Game code
        (str(BRATBOX / "scene" / "ogre_director_v2"), "ogre_director_v2"),
        (str(BRATBOX / "scene" / "runner"), "runner"),
        # Assets: lightmaps + sound bank (NOT the voice deck or cache)
        (str(BRATBOX / "scene" / "ogre_director_v2" / "assets" / "audio" / "jasmine" / "squish"), "ogre_director_v2/assets/audio/jasmine/squish"),
        (str(BRATBOX / "scene" / "ogre_director_v2" / "assets" / "audio" / "jasmine" / "toot"), "ogre_director_v2/assets/audio/jasmine/toot"),
        (str(BRATBOX / "scene" / "ogre_director_v2" / "assets" / "audio" / "jasmine" / "newsounds"), "ogre_director_v2/assets/audio/jasmine/newsounds"),
    ],
    hiddenimports=[
        "tkinter",
        "pygame",
        "curses",
        "websockets",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Don't bundle dev/test stuff
        "pytest", "unittest",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="bratbox",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Need console for the curses game
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # TODO: add icon
)
