#!/usr/bin/env python3
from __future__ import annotations
import os as _mawgut_music_env
_mawgut_music_env.environ["LOCKKEY_MUSIC_ENABLED"] = "0"  # clicks ON, OST OFF
import configparser
import curses
import json
import os
import subprocess
import sys
import threading
import time
try:
    from bratbox_audio_bootstrap import start_music
except Exception:
    start_music = lambda: False
import traceback
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
RUN_DIR = Path(os.environ.get('LOCKKEY_RUN_DIR', str(ROOT/'runs'/'current')))
TELEMETRY = Path(os.environ.get('LOCKKEY_TELEMETRY', str(RUN_DIR/'telemetry.jsonl')))
CONTRACT_JSON = RUN_DIR/'minecraft_session.json'
CONTRACT_PROPS = RUN_DIR/'minecraft_session.properties'
RESULT_JSON = RUN_DIR/'shader_result.json'
REQUEST_PROPS = RUN_DIR/'minecraft_request.properties'
RUN_DIR.mkdir(parents=True, exist_ok=True)

SESSION_ID = (sys.argv[1].strip() if len(sys.argv) > 1 and sys.argv[1].strip() else str(uuid.uuid4()))
STARTED = time.time()

def _request_attention_without_focus_steal() -> None:
    """Show/flash Shader without activating it, so Minecraft keeps simulating."""
    if os.name != 'nt':
        return
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        hwnd = kernel32.GetConsoleWindow()
        if not hwnd:
            return
        SW_SHOWNOACTIVATE = 4
        user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
        class FLASHWINFO(ctypes.Structure):
            _fields_ = [
                ('cbSize', wintypes.UINT),
                ('hwnd', wintypes.HWND),
                ('dwFlags', wintypes.DWORD),
                ('uCount', wintypes.UINT),
                ('dwTimeout', wintypes.DWORD),
            ]
        FLASHW_TRAY = 0x00000002
        FLASHW_TIMERNOFG = 0x0000000C
        info = FLASHWINFO(ctypes.sizeof(FLASHWINFO), hwnd, FLASHW_TRAY | FLASHW_TIMERNOFG, 0, 0)
        user32.FlashWindowEx(ctypes.byref(info))
    except Exception:
        pass

_request_attention_without_focus_steal()

# Canonical host defaults recovered from Golden Ledger, with current Shader's
# newer three-mode experience key taking precedence over the legacy presentation key.
os.environ.setdefault('LOCKKEY_RUN_DIR', str(RUN_DIR))
os.environ.setdefault('LOCKKEY_TELEMETRY', str(TELEMETRY))
os.environ.setdefault('LOCKKEY_TELEMETRY_HZ', '10')
os.environ.setdefault('LOCKKEY_FORCE_GENESIS', '1')
os.environ.setdefault('LOCKKEY_OGRE_EXPERIENCE_MODE', 'elastic_grotesque')
os.environ.setdefault('LOCKKEY_OGRE_URINE_EFFECT', 'degradation')  # legacy fallback only
os.environ.setdefault('LOCKKEY_URINATION_PRESENTATION', '1')
os.environ.setdefault('LOCKKEY_PG_ACCESSIBILITY', '0')
os.environ.setdefault('LOCKKEY_REDUCE_MOTION', '0')
os.environ.setdefault('LOCKKEY_NSCL_HARDLINK', '1')
os.environ.setdefault('LOCKKEY_NSCL_FLOW', '1')
# User requested silent external windows: preserve text/mechanics, disable voice/music buses.
os.environ['LOCKKEY_VOICES_ENABLED'] = '0'
os.environ['LOCKKEY_VOICE_ENABLED'] = '0'
os.environ['LOCKKEY_MUSIC_ENABLED'] = '0'
os.environ['LOCKKEY_SOUNDSCAPE_PROFILE'] = 'rhythm'
os.environ['LOCKKEY_IDLE_AUDIO_MODE'] = 'rhythm'
os.environ.setdefault('FIENDISH_RELEASE_DIR', str(ROOT/'wotw_bratbox'/'vendor_full'))


def _load_request() -> dict[str,str]:
    if not REQUEST_PROPS.exists():
        return {}
    cp = configparser.ConfigParser()
    try:
        # java.util.Properties has no section header; ConfigParser needs one.
        raw = REQUEST_PROPS.read_text(encoding='utf-8', errors='ignore')
        cp.read_string('[request]\n' + raw)
        return dict(cp['request'])
    except Exception:
        return {}


REQUEST = _load_request()

# MawGut keeps the tactile/surface renderer, but not WotW character identity.
# Give each session a stable, lightly-randomized physiology profile.
os.environ["ONRYO_TACTILE_SURFACE"] = "1"
os.environ["ONRYO_TACTILE_MUSK"] = "1"
os.environ["OGRE_DISABLE_SWEAT"] = "1"
os.environ["LOCKKEY_PARTICLE_DRIP_ENABLED"] = "0"
os.environ["LOCKKEY_URINATION_PRESENTATION"] = "1"

try:
    import hashlib as _hashlib
    _fairy_seed = str(
        REQUEST.get("player_uuid","")
        or REQUEST.get("session_id","")
        or REQUEST.get("seed","mawgut")
    )
    _digest = _hashlib.sha256(_fairy_seed.encode("utf-8","ignore")).digest()
    _sweat = 0.55 + (_digest[0] / 255.0) * 0.40
    _musk  = 0.35 + (_digest[1] / 255.0) * 0.50
    _urine = 0.25 + (_digest[2] / 255.0) * 0.45
    _surface_variant = ("dry","warm","humid","dewy")[_digest[3] % 4]

    os.environ["LOCKKEY_FAIRY_SURFACE_PROFILE"] = _surface_variant
    os.environ["LOCKKEY_FAIRY_SWEAT_INTENSITY"] = f"{_sweat:.3f}"
    os.environ["LOCKKEY_FAIRY_MUSK_INTENSITY"] = f"{_musk:.3f}"
    os.environ["LOCKKEY_FAIRY_URINE_INTENSITY"] = f"{_urine:.3f}"
    # Keep the existing effect renderer, but use a generalized presentation
    # rather than any WotW-character-specific authored wording.
    os.environ["LOCKKEY_OGRE_URINE_EFFECT"] = "suggestive"
except Exception:
    os.environ["LOCKKEY_FAIRY_SURFACE_PROFILE"] = "warm"
    os.environ["LOCKKEY_FAIRY_SWEAT_INTENSITY"] = "0.70"
    os.environ["LOCKKEY_FAIRY_MUSK_INTENSITY"] = "0.55"
    os.environ["LOCKKEY_FAIRY_URINE_INTENSITY"] = "0.40"
    os.environ["LOCKKEY_OGRE_URINE_EFFECT"] = "suggestive"

# MawGut presentation profile. "auto" uses the recovered WotW Idle performer:
# Ogre plays the authored chart while Minecraft/Cathedral remain observable.
_AUTO_PROFILE = str(REQUEST.get("auto_profile","false") or "false").strip().lower() in ("1","true","yes","on","auto")
os.environ["LOCKKEY_OST_FILES"] = "0"
os.environ["LOCKKEY_MUSIC_ENABLED"] = "0"
os.environ["LOCKKEY_NOTE_CLICKS"] = "1"
os.environ["LOCKKEY_SOUNDSCAPE"] = "rhythm"
os.environ["LOCKKEY_RHYTHM_SOUNDS"] = "1"
if _AUTO_PROFILE:
    os.environ["LOCKKEY_IDLE_OGRE_MODE"] = "1"
    os.environ["LOCKKEY_OGRE_AI_CONTROL"] = "perform"
    os.environ.setdefault("LOCKKEY_OGRE_AI_PLAYSTYLE", "coy_improviser")
    os.environ.setdefault("LOCKKEY_OGRE_AI_OUTCOME", "dramatic")
else:
    os.environ.pop("LOCKKEY_IDLE_OGRE_MODE", None)
    os.environ.setdefault("LOCKKEY_OGRE_AI_CONTROL", "manual")

class ContractMirror:
    def __init__(self):
        self.stop_evt = threading.Event()
        self.lock = threading.Lock()
        # Contract writes happen from both the 10 Hz mirror thread and the
        # Shader completion path. Serialize filesystem I/O separately from
        # state mutation so Windows never sees two writers fighting over the
        # same temp/final file.
        self.io_lock = threading.Lock()
        self.offset = 0
        self.state: dict[str, Any] = {
            'schema': 'mawgut.golden_ledger.session.v1',
            'session_id': SESSION_ID,
            'route': REQUEST.get('route','gazelle_flower_birth'),
            'player_uuid': REQUEST.get('player_uuid',''),
            'active': True,
            'finished': False,
            'failed': False,
            'success': False,
            'phase': 'BOOT',
            'stage': 'SOCIAL',
            'elapsed_sec': 0.0,
            'heartbeat_unix_ms': int(time.time()*1000),
            'combo': 0,
            'tier': 0,
            'melt': 0.0,
            'push': 0.0,
            'pressure': 0.0,
            'power': 0.0,
            'denial': 0.0,
            'inside': False,
            'climax': False,
            'climax_events': 0,
            'conception_events': 0,
            'reproductive_finale': False,
            'ovum_forced': False,
            'ovum_stage': '',
            'ovum_progress': 0.0,
            'ovum_in_tube': False,
            'ovum_in_chamber': False,
            'sperm_visible': False,
            'conception_locked': False,
            'conception_phase': '',
            'terminal_heir': False,
            'terminal_heir_count': 0,
            'purple_cadence_qualified': False,
            'wrong_route_lock': False,
            'climax_suppressed': False,
            'biometric_instrument_visible': True,
            'brat_phase': 'KISS_CAPTURE',
            'brat_phase_progress': 0.0,
            'brat_pose_block': False,
            'brat_seal_established': False,
            'brat_lateral_diversion': 0.0,
            'brat_movement_risk': 0.0,
            'brat_terminal_committed': False,
            'pandora_stop': False,
            'last_event': '',
            'error': '',
        }

    def _atomic_text(self, path: Path, text: str):
        path.parent.mkdir(parents=True, exist_ok=True)
        # Unique temp file prevents mirror-thread / completion-thread collisions.
        tmp = path.with_name(
            path.name + f'.{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex}.tmp'
        )
        with self.io_lock:
            last_exc = None
            try:
                tmp.write_text(text, encoding='utf-8')
                # Windows can briefly deny replace while Minecraft/AV has the
                # destination open. Retry long enough to cross a Java poll.
                for attempt in range(24):
                    try:
                        os.replace(tmp, path)
                        return
                    except (PermissionError, OSError) as exc:
                        last_exc = exc
                        time.sleep(0.025 + min(0.075, attempt * 0.004))

                # Final fallback: overwrite in place. A reader may see one
                # partial poll, but MawGut caches the previous good state and
                # will recover on the next 100 ms poll.
                for attempt in range(24):
                    try:
                        with path.open('w', encoding='utf-8', newline='') as fh:
                            fh.write(text)
                            fh.flush()
                        try:
                            tmp.unlink(missing_ok=True)
                        except Exception:
                            pass
                        return
                    except (PermissionError, OSError) as exc:
                        last_exc = exc
                        time.sleep(0.025 + min(0.075, attempt * 0.004))
                if last_exc is not None:
                    raise last_exc
            finally:
                try:
                    tmp.unlink(missing_ok=True)
                except Exception:
                    pass

    def write(self):
        with self.lock:
            self.state['elapsed_sec'] = round(max(0.0, time.time()-STARTED), 3)
            self.state['heartbeat_unix_ms'] = int(time.time()*1000)
            snap = dict(self.state)
        self._atomic_text(CONTRACT_JSON, json.dumps(snap, indent=2, ensure_ascii=False))
        lines=[]
        for k,v in snap.items():
            if isinstance(v, bool): val='true' if v else 'false'
            elif isinstance(v, (dict,list,tuple)): val=json.dumps(v, ensure_ascii=False, separators=(',',':'))
            else: val=str(v).replace('\\','\\\\').replace('\n',' ')
            lines.append(f'{k}={val}')
        self._atomic_text(CONTRACT_PROPS, '\n'.join(lines)+'\n')

    def note_row(self, row: dict[str,Any]):
        if not isinstance(row, dict): return
        # Backwards compatibility for our pre-Golden bridge rows, while emitting
        # only the flat canonical format from this build.
        bio = row.get('biometrics', row)
        event = row.get('event') or (row.get('type') if row.get('kind') == 'event' else None)
        with self.lock:
            if event:
                ev = str(event)
                self.state['last_event'] = ev
                self.state['phase'] = ev
                if ev == 'SESSION_START':
                    self.state['phase'] = 'ACTIVE'
                elif ev == 'PANDORA':
                    self.state['pandora_stop'] = True
                    self.state['phase'] = 'RELEASE'
                    self.state['inside'] = False
                    self.state['climax'] = False
                    self.state['biometric_instrument_visible'] = False
                    self.state['climax_suppressed'] = True
                elif ev == 'BRAT_STATE':
                    self.state['brat_phase'] = str(row.get('phase',''))
                    self.state['brat_phase_progress'] = float(row.get('phase_progress',0.0) or 0.0)
                    self.state['brat_pose_block'] = bool(row.get('pose_block',False))
                    self.state['brat_seal_established'] = bool(row.get('seal_established',False))
                    self.state['brat_lateral_diversion'] = float(row.get('lateral_diversion',0.0) or 0.0)
                    self.state['brat_movement_risk'] = float(row.get('movement_risk',0.0) or 0.0)
                    self.state['brat_terminal_committed'] = bool(row.get('terminal_committed',False))
                elif ev == 'WRONG_ROUTE_CLIMAX':
                    self.state['wrong_route_lock'] = True
                    self.state['climax_suppressed'] = True
                    self.state['biometric_instrument_visible'] = False
                    self.state['inside'] = False
                    self.state['climax'] = False
                    self.state['phase'] = 'WRONG_ROUTE_LOCK'
                elif ev == 'REPRODUCTIVE_FINALE':
                    if not bool(self.state.get('wrong_route_lock', False)):
                        self.state['reproductive_finale'] = True
                        self.state['phase'] = 'REPRODUCTIVE_FINALE'
                        self.state['ovum_forced'] = bool(row.get('force_ovum', False))
                        self.state['terminal_heir'] = bool(row.get('heir', False))
                        self.state['terminal_heir_count'] = max(
                            int(row.get('heir_count', 0) or 0),
                            1 if bool(row.get('heir', False)) else 0,
                        )
                        self.state['purple_cadence_qualified'] = bool(row.get('purple_cadence_qualified', False))
                        if row.get('ovum_stage') is not None:
                            self.state['ovum_stage'] = str(row.get('ovum_stage', '') or '')
                        if row.get('ovum_progress') is not None:
                            self.state['ovum_progress'] = float(row.get('ovum_progress', 0.0) or 0.0)
                        self.state['ovum_in_tube'] = bool(row.get('ovum_in_tube', self.state.get('ovum_in_tube', False)))
                        self.state['ovum_in_chamber'] = bool(row.get('ovum_in_chamber', self.state.get('ovum_in_chamber', False)))
                        self.state['conception_phase'] = str(row.get('conception_phase', self.state.get('conception_phase', ''))) or self.state.get('conception_phase', '')
                        if bool(row.get('heir', False)):
                            self.state['conception_events'] = max(
                                1, int(self.state.get('conception_events', 0) or 0)
                            )
                elif ev == 'REPRODUCTIVE_COMMIT':
                    if not bool(self.state.get('wrong_route_lock', False)):
                        self.state['phase'] = 'REPRODUCTIVE_COMMIT'
                        self.state['ovum_stage'] = str(row.get('ovum_stage', 'TUBE_TRANSIT') or 'TUBE_TRANSIT')
                        self.state['ovum_progress'] = float(row.get('ovum_progress', 0.25) or 0.25)
                        self.state['ovum_in_tube'] = bool(row.get('ovum_in_tube', True))
                        self.state['ovum_in_chamber'] = bool(row.get('ovum_in_chamber', False))
                elif ev == 'REPRODUCTIVE_CLIMAX':
                    if not bool(self.state.get('wrong_route_lock', False)):
                        self.state['phase'] = 'REPRODUCTIVE_CLIMAX'
                        self.state['climax'] = True
                        self.state['sperm_visible'] = bool(row.get('sperm_visible', False))
                        if row.get('ovum_stage') is not None:
                            self.state['ovum_stage'] = str(row.get('ovum_stage', '') or '')
                        if row.get('ovum_progress') is not None:
                            self.state['ovum_progress'] = float(row.get('ovum_progress', 0.0) or 0.0)
                        self.state['ovum_in_tube'] = bool(row.get('ovum_in_tube', self.state.get('ovum_in_tube', False)))
                        self.state['ovum_in_chamber'] = bool(row.get('ovum_in_chamber', self.state.get('ovum_in_chamber', False)))
                elif ev == 'CONCEPTION_LOCK':
                    if not bool(self.state.get('wrong_route_lock', False)):
                        self.state['phase'] = 'CONCEPTION_LOCK'
                        self.state['conception_locked'] = True
                        self.state['sperm_visible'] = bool(row.get('sperm_visible', True))
                        self.state['ovum_stage'] = str(row.get('ovum_stage', 'CONTACT_HOLD') or 'CONTACT_HOLD')
                        self.state['ovum_progress'] = float(row.get('ovum_progress', 0.94) or 0.94)
                        self.state['ovum_in_tube'] = bool(row.get('ovum_in_tube', False))
                        self.state['ovum_in_chamber'] = bool(row.get('ovum_in_chamber', True))
                        self.state['conception_phase'] = str(row.get('conception_phase', 'CONTACT_HOLD') or 'CONTACT_HOLD')
                elif ev == 'CONCEPTION':
                    if not bool(self.state.get('wrong_route_lock', False)):
                        self.state['conception_events'] = int(self.state.get('conception_events',0))+1
                        self.state['phase'] = 'CONCEPTION'
                        self.state['conception_locked'] = False
                        self.state['sperm_visible'] = bool(row.get('sperm_visible', True))
                        self.state['ovum_stage'] = str(row.get('ovum_stage', 'CONCEPTION') or 'CONCEPTION')
                        self.state['ovum_progress'] = float(row.get('ovum_progress', 1.0) or 1.0)
                        self.state['ovum_in_tube'] = False
                        self.state['ovum_in_chamber'] = True
                        self.state['conception_phase'] = str(row.get('conception_phase', 'CONCEPTION') or 'CONCEPTION')
                elif ev == 'CLIMAX':
                    if not bool(self.state.get('wrong_route_lock', False)):
                        self.state['climax_events'] = int(self.state.get('climax_events',0))+1
                        self.state['climax'] = True
                elif ev in ('SESSION_END','SESSION_COMPLETE'):
                    self.state['phase'] = ev
            if isinstance(bio, dict) and not event:
                _wrong_locked = bool(self.state.get('wrong_route_lock', False))
                for key in ('stage','combo','tier','melt','push','pressure','power','denial','inside','climax'):
                    if key not in bio:
                        continue
                    if _wrong_locked and key in ('inside','climax'):
                        continue
                    self.state[key] = bio[key]
                if _wrong_locked:
                    self.state['inside'] = False
                    self.state['climax'] = False
                    self.state['biometric_instrument_visible'] = False
                if bio.get('stage') and not _wrong_locked:
                    self.state['phase'] = str(bio.get('stage'))

    def monitor(self):
        self.write()
        while not self.stop_evt.is_set():
            try:
                if TELEMETRY.exists():
                    with TELEMETRY.open('rb') as f:
                        f.seek(self.offset)
                        chunk=f.read()
                        self.offset=f.tell()
                    for line in chunk.decode('utf-8','ignore').splitlines():
                        try: self.note_row(json.loads(line))
                        except Exception: pass
                self.write()
            except Exception as exc:
                with self.lock:
                    self.state['bridge_warning']=repr(exc)
            self.stop_evt.wait(0.10)

    def finish(self, result: dict[str,Any] | None=None, error: str=''):
        result = dict(result or {})
        with self.lock:
            self.state['active'] = False
            self.state['finished'] = True
            self.state['failed'] = bool(error or result.get('_error') or result.get('terminal_failure'))
            self.state['success'] = not self.state['failed']
            self.state['phase'] = 'FAILED' if self.state['failed'] else 'SESSION_COMPLETE'
            self.state['error'] = str(error or result.get('_error','') or '')
            self.state['result_session_minutes'] = float(result.get('session_minutes',0.0) or 0.0)
            _duration = float(result.get('duration_seconds',0.0) or 0.0)
            if _duration <= 0.0:
                _duration = float(result.get('session_minutes',0.0) or 0.0) * 60.0
            self.state['result_duration_seconds'] = round(max(0.0, _duration), 3)
            self.state['result_cycles'] = int(result.get('cycles',0) or 0)
            self.state['result_accuracy'] = float(result.get('accuracy',0.0) or 0.0)
            self.state['result_max_combo'] = int(result.get('max_combo',0) or 0)
            self.state['result_total_climaxes'] = int(result.get('total_climaxes',0) or 0)
            self.state['result_climax_reached'] = bool(result.get('climax_reached',False))
            self.state['result_session_completed'] = bool(result.get('session_completed',False))
            self.state['result_highest_tier'] = int(result.get('highest_tier',0) or 0)

            _purple = dict(result.get('terminal_purple_cadence', {}) or {})
            _terminal_heir = bool(result.get('terminal_climax_heir', False))
            _terminal_heir_count = max(
                0,
                int(result.get('terminal_climax_heir_count', 0) or 0),
                int(_purple.get('heir_count', 0) or 0) if _terminal_heir else 0,
            )
            self.state['result_terminal_heir'] = _terminal_heir
            self.state['result_terminal_heir_count'] = _terminal_heir_count
            self.state['result_purple_cadence_qualified'] = bool(_purple.get('qualified', False))
            self.state['result_conceived'] = bool(
                _terminal_heir or _terminal_heir_count > 0
                or int(self.state.get('conception_events', 0) or 0) > 0
            )
            if self.state['result_conceived']:
                self.state['conception_events'] = max(
                    int(self.state.get('conception_events', 0) or 0),
                    max(1, _terminal_heir_count),
                )
        try:
            self._atomic_text(RESULT_JSON, json.dumps(result, indent=2, ensure_ascii=False, default=str))
        except Exception:
            pass
        self.write()
        self.stop_evt.set()

mirror = ContractMirror()




def _spawn_cathedral():
    target = ROOT/'biometric_cathedral.py'
    if not target.exists(): return None
    env = os.environ.copy()
    env['LOCKKEY_RUN_DIR'] = str(RUN_DIR)
    env['LOCKKEY_TELEMETRY'] = str(TELEMETRY)
    env['LOCKKEY_ENDLESS'] = '0'
    flags = getattr(subprocess, 'CREATE_NEW_CONSOLE', 0) if os.name == 'nt' else 0
    try:
        return subprocess.Popen([sys.executable, str(target)], cwd=str(ROOT), env=env, creationflags=flags)
    except Exception:
        return None


def _receipt(scr, result: dict[str,Any]):
    try:
        scr.erase(); h,w=scr.getmaxyx(); cx=max(1,w//2); y=2
        lines=[
            'GOLDEN LEDGER SESSION COMPLETE',
            '',
            f"Time: {float(result.get('session_minutes',0.0) or 0.0):.2f} min",
            f"Accuracy: {float(result.get('accuracy',0.0) or 0.0)*100:.1f}%",
            f"Max combo: {int(result.get('max_combo',0) or 0)}",
            f"Cycles: {int(result.get('cycles',0) or 0)}",
            f"Climaxes: {int(result.get('total_climaxes',0) or 0)}",
            '',
            'Minecraft has already received the completion receipt.',
        ]
        for line in lines:
            x=max(0,cx-len(line)//2); scr.addstr(y,x,line[:max(1,w-2)]); y+=1
        scr.refresh(); scr.timeout(2600); scr.getch()
    except Exception:
        pass


def run_shader():
    import ogre_shader_v5 as shader
    result: dict[str,Any] = {}
    def wrapped(scr):
        nonlocal result
        engine = shader.PlayableEngineV5(scr, flow_mode=False)
        # Match Golden Ledger's in-process host behavior: skip only the outer
        # grinder wrapper, not the actual Shader/intimacy mechanics.
        engine._grinder_skip = True
        engine.grin_factor = 0.001
        try:
            engine.session_cycle_cap = max(1, int(os.environ.get('MAWGUT_OGRE_CYCLE_CAP','1') or 1))
        except Exception:
            engine.session_cycle_cap = 1
        result = dict(engine.run() or {})
        mirror.finish(result)
        _receipt(scr, result)
    curses.wrapper(wrapped)
    return result


def main():
    for p in (TELEMETRY, CONTRACT_JSON, CONTRACT_PROPS, RESULT_JSON):
        try: p.unlink(missing_ok=True)
        except Exception: pass
    mirror.write()
    monitor = threading.Thread(target=mirror.monitor, name='GoldenLedgerTelemetryMirror', daemon=True)
    monitor.start()
    cathedral = _spawn_cathedral()
    try:
        run_shader()
    except (KeyboardInterrupt, SystemExit) as exc:
        if not mirror.state.get('finished'):
            mirror.finish({}, error=f'{type(exc).__name__}: session interrupted')
    except Exception:
        err = traceback.format_exc()
        mirror.finish({}, error=err)
        print(err)
        print('\nShader host failed. Minecraft received FAILED=true.')
        try: input('Press Enter to close...')
        except Exception: pass
    finally:
        mirror.stop_evt.set()
        monitor.join(timeout=1.0)
        mirror.write()
        if cathedral is not None:
            try:
                cathedral.terminate(); cathedral.wait(timeout=2.0)
            except Exception:
                try: cathedral.kill()
                except Exception: pass

if __name__ == '__main__':
    main()
