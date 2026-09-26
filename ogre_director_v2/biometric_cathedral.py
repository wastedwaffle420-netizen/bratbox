from brat_cathedral_lines import BRAT_CATHEDRAL_LINES
#!/usr/bin/env python3
"""
BIOMETRICS // LIVING CATHEDRAL  — pygame edition v4 (ANIME-MEDICAL)

Upgrade: full-send grotesque animism with anime-medical UI chrome.
  - Per-organ convulsion/reactivity system (threshold-driven)
  - ECG heartbeat readout
  - Scan-line + vignette overlay
  - Medical annotation labels, readout borders
  - Variable-thickness peristaltic tubes
  - Follicle fluid simulation in ovary clusters
  - Iris-gate mechanic
  - Tremor / micro-jitter on denial/push peaks
  - Pre-climax strobing
"""

import os, sys, json, time, math, random, subprocess
from pathlib import Path
from dataclasses import dataclass, field
from collections import deque
from typing import List, Tuple, Optional, Deque

try:
    import pygame
# =============================================================================
# CANON TUNING DOC (Biometric Cathedral) — "convulsions preserved"
# =============================================================================
# Purpose:
# - This panel is NOT a truth meter. It is a *feel/tuning meter*.
# - "contact" + "stage" are treated as *safe labels*, not accuracy claims.
# - The only inputs we trust from OGRE are: combo (skill/flow), inside (binary),
#   and melt (a rhythmic energy signal). Everything else is *derived* here.
#
# Two launch modes (no extra config needed):
# - LOCKKEY_ENDLESS=1  → start at FOREPLAY + faster simulation (for no-voice loop)
# - default            → start at SOCIAL   + slower simulation (for dialogue burn)
#
# ---------------------------
# Variables (all clamped):
# ---------------------------
# combo        : int     [0 .. COMBO_CAP] (values above cap are treated as cap)
# stage        : str     one of STAGE_ORDER (internal phase; monotonic per cycle)
# stage_idx    : float   [0 .. len(STAGE_ORDER)-1] (smooth display position)
# inside       : bool    {False, True} (only reliable binary)
# composure    : float   [0.0 .. 1.0] (depletes; when it hits 0 → stage advances)
# melt         : float   [0.0 .. 1.0] (when inside: triangle-wave "tick" driver)
# pressure     : float   [0.0 .. 1.0] ("her push"; rises with melt ticks)
# push         : float   [0.0 .. 1.0] (hardest to raise; mostly combo-driven)
# power        : float   [0.0 .. 1.0] (bank; builds from push + pressure)
# denial       : float   [0.0 .. 1.0] (raises climax threshold, boosts climax punch)
# climax       : float   [0.0 .. 1.0] (all-or-nothing burst; then relax)
#
# ---------------------------
# 10 Constants (tune-by-feel):
# ---------------------------
# TIMING
#  1) TIME_MULT_ENDLESS      : sim speed when LOCKKEY_ENDLESS=1
#  2) TIME_MULT_DIALOGUE     : sim speed in default slow-burn
# COMBO
#  3) COMBO_CAP              : combo normalization ceiling
# MELT TICK (only matters when inside=True)
#  4) MELT_TICK_HZ           : melt oscillation frequency (triangle wave)
#  5) MELT_TICK_TO_PRESSURE  : pressure gained from melt rising edges
# PUSH / POWER / PRESSURE
#  6) PUSH_FROM_COMBO        : push gained per second at max combo
#  7) POWER_FROM_PUSH        : power bank gained per second at max push
# STAGE (composure depletion)
#  8) COMPOSURE_DRAIN_BASE   : baseline composure drain per second
#  9) COMPOSURE_DRAIN_GAIN   : extra drain scaled by (pressure/push/power) intensity
# CLIMAX / DENIAL
# 10) DENIAL_THRESH_BOOST    : denial raises climax trigger threshold (and punch)
#
# ---------------------------
# 2‑minute tuning recipe:
# ---------------------------
# 1) Pick your mode (ENDLESS vs dialogue). Set TIME_MULT_* first.
# 2) If stages advance too fast/slow: change COMPOSURE_DRAIN_BASE, then _GAIN.
#    - ENDLESS target: stage hop every ~25–60s depending on combo.
#    - DIALOGUE target: stage hop every ~2–6 min depending on combo.
# 3) If melt feels too twitchy / too sluggish (inside=True): change MELT_TICK_HZ.
# 4) If pressure spikes feel wrong: change MELT_TICK_TO_PRESSURE.
# 5) If "push" is too easy / impossible: change PUSH_FROM_COMBO.
# 6) If "power bank" overwhelms / never fills: change POWER_FROM_PUSH.
# 7) If climax triggers too often / never: adjust DENIAL_THRESH_BOOST (small steps).
# =============================================================================

    import pygame.gfxdraw
except ImportError:
    print("pygame not installed — run: pip install pygame")
    sys.exit(1)

# Add these lines near the top of the file (after imports, before any class definitions)
# ── Stage progression timer (every 5 min auto-advance) ──────────────────────

STAGE_ORDER = ["SOCIAL", "FLIRT", "FOREPLAY", "PLAY", "EDGE", "FRENZY", "AFTERGLOW", "COOLDOWN"]

# ── Session pacing / gating (balanced) ───────────────────────────────────
# Set LOCKKEY_SESSION_SEC to tune the whole cycle length (default ~10 minutes).
SESSION_TARGET_SEC = float(os.environ.get("LOCKKEY_SESSION_SEC", "600"))

# Base stage durations sum to 600s; we scale them to SESSION_TARGET_SEC.
_BASE_STAGE_DUR = {
    "SOCIAL":     45.0,
    "FLIRT":      45.0,
    "FOREPLAY":   60.0,
    "PLAY":       150.0,
    "EDGE":       150.0,
    "FRENZY":     105.0,
    "AFTERGLOW":  30.0,
    "COOLDOWN":   15.0,
}
_stage_scale = max(0.35, min(3.0, SESSION_TARGET_SEC / 600.0))
STAGE_DUR_SEC = {k: v * _stage_scale for k, v in _BASE_STAGE_DUR.items()}

SMACK_WINDOW_SEC = float(os.environ.get("LOCKKEY_SMACK_WINDOW_SEC", "2.0"))
RELEASE_WINDOW_SEC = float(os.environ.get("LOCKKEY_RELEASE_WINDOW_SEC", "0.85"))
RELEASE_COOLDOWN_SEC = float(os.environ.get("LOCKKEY_RELEASE_COOLDOWN_SEC", "7.0"))
POP_FREEZE_SEC = float(os.environ.get("LOCKKEY_POP_FREEZE_SEC", "0.35"))


# --- Canon tuning constants (see CANON TUNING DOC above) ---
TIME_MULT_ENDLESS   = 1.85   # faster sim for endless/no-voice loop
TIME_MULT_DIALOGUE  = 0.90   # slower sim for dialogue-first burn
COMBO_CAP           = 64     # combo values above this are treated as "max"
MELT_TICK_HZ        = 0.90   # triangle-wave cycles per second while inside
MELT_TICK_TO_PRESSURE = 0.42 # pressure gained from melt rising edges
PUSH_FROM_COMBO     = 0.55   # push gained per second at max combo
POWER_FROM_PUSH     = 0.48   # power bank gained per second at max push
COMPOSURE_DRAIN_BASE = 0.020 # baseline composure drain per second
COMPOSURE_DRAIN_GAIN = 0.135 # extra drain scaled by intensity
DENIAL_THRESH_BOOST  = 0.22  # denial raises climax threshold & punch

STAGE_DURATION_SEC = 60  # 

# Add this method inside your Cathedral / Metrics class (or wherever ingest / from_ev lives)
def auto_advance_stage(self, now: float):
    """
    Every STAGE_DURATION_SEC seconds: advance stage forward.
    If already at COOLDOWN → reset to SOCIAL when cooldown ends.
    Call this once per frame in main loop (cheap).
    """
    if not hasattr(self, '_last_stage_time'):
        self._last_stage_time = now
        self._stage_start_time = now
        return

    # If in COOLDOWN and time passed → reset to SOCIAL
    if self.stage == "COOLDOWN":
        if now - self._stage_start_time >= STAGE_DURATION_SEC:
            self.stage = "SOCIAL"
            self.stage_idx = 0
            self._stage_start_time = now
            self._last_stage_time = now
            print("[AUTO-STAGE] Cooldown ended → reset to SOCIAL")
        return

    # Normal progression
    if now - self._stage_start_time >= STAGE_DURATION_SEC:
        next_idx = (self.stage_idx + 1) % len(STAGE_ORDER)
        self.stage = STAGE_ORDER[next_idx]
        self.stage_idx = next_idx
        self._stage_start_time = now
        print(f"[AUTO-STAGE] Advanced to {self.stage}")

# ── Window — dynamic, self-fitting to screen at 100% DPI scale ─────────────
FPS = 60

def _detect_screen_wh():
    """Physical screen pixels before pygame starts."""
    if os.name == "nt":
        try:
            import ctypes
            u32 = ctypes.windll.user32
            try: u32.SetProcessDPIAware()
            except: pass
            return u32.GetSystemMetrics(0), u32.GetSystemMetrics(1)
        except: pass
    try:
        import subprocess
        out = subprocess.check_output(["xrandr","--current"],
                                      stderr=subprocess.DEVNULL,timeout=2).decode()
        for line in out.splitlines():
            if "connected" in line:
                for tok in line.split():
                    if "x" in tok:
                        try:
                            sw,sh = map(int, tok.split("x"))
                            if sw>400 and sh>300: return sw, sh
                        except: pass
    except: pass
    return 1920, 1080

def _bio_size(sw, sh, taskbar=48):
    """Fit bio window into right half of screen, 14:9 design aspect."""
    esh = sh - taskbar
    bw  = sw // 2
    bh  = int(bw * 900 / 1400)
    if bh > esh:
        bh = esh
        bw = int(bh * 1400 / 900)
    return (bw & ~1), (bh & ~1)   # snap to even pixels

_SW, _SH      = _detect_screen_wh()
_TASKBAR_H    = int(os.environ.get("LOCKKEY_TASKBAR_H", "48"))
W = int(os.environ.get("LOCKKEY_BIO_W","0")) or _bio_size(_SW,_SH,_TASKBAR_H)[0]
H = int(os.environ.get("LOCKKEY_BIO_H","0")) or _bio_size(_SW,_SH,_TASKBAR_H)[1]

_SX = W / 1400.0          # horizontal scale vs design
_SY = H / 900.0           # vertical scale vs design
_SC = (_SX + _SY) * 0.5   # uniform scale for fonts / radii

# Panel boundaries — scaled from design splits (22% / 67%)
L_PANEL = int(310 * _SX)
R_PANEL = int(940 * _SX)
CX      = (L_PANEL + R_PANEL) // 2

# ── Palette — FLESH FIRST ────────────────────────────────────────────────────
# Tech panels stay dark. Center pane is warm body interior.
BG           = (4,   2, 12)          # left/right tech panel bg

# ── Flesh background gradient (center pane)
FLESH_DEEP   = ( 55,  18, 22)        # deep edge, almost arterial
FLESH_MID    = (125,  52, 48)        # mid-zone
FLESH_WARM   = (185, 100, 72)        # warm amber-flesh
FLESH_BRIGHT = (225, 165, 120)       # lit internal surface
FLESH_GLOW   = (255, 215, 165)       # direct internal glow
FLESH_COOL   = (145,  62, 65)        # shadow/cooler flesh

# ── Anatomy tissue layers
SEROSA       = ( 72,  24, 28)        # peritoneal outer covering
MYO          = (108,  40, 46)        # myometrium — outer uterine muscle
MYO_MID      = (140,  58, 60)        # mid myometrium
ENDO         = (198, 108, 98)        # endometrium — inner lining
ENDO_HOT     = (230, 130, 80)        # endometrium heated/engorged
CAVITY       = (248, 200, 175)       # uterine cavity, brightest zone

# ── Fallopian tube
TUBE_WALL    = (120,  48, 52)        # outer tube wall (serosa)
TUBE_MED     = (165,  82, 78)        # muscularis layer
TUBE_MUC     = (220, 148, 130)       # mucosal inner layer
TUBE_INNER   = (215, 145, 125)       # inner surface (peristaltic visible)
TUBE_HOT     = (255, 180,  80)       # tube engorged/aroused
TUBE_GLOW    = (245, 195, 150)       # tube highlight glow
FIMB         = (200, 115, 105)       # fimbriae fronds

# ── Ovary
STROMA       = (178, 102, 85)        # ovarian stroma
CORTEX       = (208, 132, 108)       # cortical layer
FOLLICLE_WALL= (160,  78, 72)        # follicle outer wall
FOLLICLE_FLUID_COL = (255, 245, 215) # follicular fluid (pale straw)
CORPUS_LUT   = (210, 178,  55)       # corpus luteum (yellow body)

# ── Cervix / gate
CERVIX_COL   = (165,  75, 72)        # cervical tissue
OS_OPEN      = (248, 165, 145)       # cervical os when open
OS_CLOSED    = (100,  35, 38)        # cervical os sealed

# ── Vaginal canal
RUGAE_DARK   = (108,  42, 44)        # rugae fold shadow
RUGAE_LIGHT  = (188, 115, 105)       # rugae fold highlight
CANAL_WALL   = (150,  65, 62)        # vaginal wall

# ── Sperm — warm ivory not cyan
SPERM_COL    = (230, 210, 190)
SPERM_HEAD   = (250, 238, 222)

# ── Egg
EGG_WHITE    = (255, 252, 242)
EGG_GLOW     = (255, 240, 210)
EGG_FACE     = (155,  72, 88)

# ── Legacy aliases (kept for non-anatomy code paths)
FOLLICLE     = FOLLICLE_FLUID_COL
TISSUE_DEEP  = MYO
TISSUE_MID   = ENDO
TISSUE_LITE  = (225, 158, 138)
ENDO_WARM    = ENDO
TUBE_OUTER   = TUBE_WALL
CLUSTER_A    = STROMA
CLUSTER_B    = CORTEX

# ── Status / gate
GATE_OPEN    = ( 50, 225, 110)       # green — keep readable
GATE_LOCK    = (225,  55,  75)       # red  — keep readable
GATE_PULSE   = (255, 175,  45)
GATE_IRIS    = ( 90, 250, 160)

# ── Particle effects
PARTICLE_A   = (255, 215,  90)
PARTICLE_B   = (230, 140, 100)
PARTICLE_C   = (255, 195, 130)

# ── Cascade / monologue (tech right panel — keep vivid)
CASCADE_EGG      = (255, 222,  88)
CASCADE_TUBE     = ( 80, 208, 245)
CASCADE_UTERUS   = (228,  88, 200)
CASCADE_ENTRANCE = (228,  88,  65)
CASCADE_BIRD     = (228, 228, 228)

# ── HUD chrome
HUD_BG       = ( 16,  10, 28)
HUD_BORDER   = ( 55,  40, 80)
HUD_ACCENT   = ( 80, 180, 255)
ECG_COL      = ( 60, 240, 140)
ECG_DIM      = ( 20,  80,  50)
SCAN_LINE    = (  8,   4, 16)
WHITE        = (255, 255, 255)
DIM          = ( 90,  80, 105)
LABEL_COL    = (200, 155, 130)       # warm label color for anatomy
WARN_COL     = (255,  80,  80)
CONVULSE_FX  = (255, 230, 195)

# ── Telemetry ──────────────────────────────────────────────────────────────
HERE    = os.path.abspath(os.path.dirname(__file__))
RUN_DIR = os.environ.get("LOCKKEY_RUN_DIR", os.path.join(HERE,"runs","current"))
TELE    = os.environ.get("LOCKKEY_TELEMETRY", os.path.join(RUN_DIR,"telemetry.jsonl"))

STAGE_ORDER = ["SOCIAL","FLIRT","FOREPLAY","PLAY","EDGE","FRENZY","AFTERGLOW","COOLDOWN"]

def _f(v, d=0.0):
    try: return float(v) if v is not None else d
    except: return d
def _clamp(x, lo=0.0, hi=1.0): return max(lo, min(hi, x))
def _lerp(a, b, t): return a + (b-a)*t


def _has_smack(bio: dict) -> bool:
    """Best-effort detection of a 'smack' token from OGRE telemetry.

    The user may emit 'smack' as a dialogue/line string (not a dedicated flag),
    so we scan *all* nested string-ish values (plus badge lists) for the substring.

    Safe no-op if absent.
    """
    if not isinstance(bio, dict):
        return False

    # Fast path: common badge list shapes
    try:
        for k in ("BADGES", "badges"):
            v = bio.get(k, [])
            if isinstance(v, list):
                for it in v:
                    if "smack" in str(it).lower():
                        return True
    except Exception:
        pass

    # Robust path: recursively scan all values for a 'smack' substring.
    def _scan(v) -> bool:
        try:
            if v is None:
                return False
            # primitives / strings
            if isinstance(v, (str, int, float, bool)):
                return "smack" in str(v).lower()
            # mappings
            if isinstance(v, dict):
                for vv in v.values():
                    if _scan(vv):
                        return True
                return False
            # sequences
            if isinstance(v, (list, tuple, set)):
                for vv in v:
                    if _scan(vv):
                        return True
                return False
        except Exception:
            return False
        return False

    return _scan(bio)



class TelemetryReader:
    def __init__(self, path):
        self.path   = path
        self.offset = 0
    def poll(self) -> List[dict]:
        if not os.path.exists(self.path): return []
        try:
            with open(self.path,"rb") as f:
                f.seek(self.offset)
                chunk = f.read()
                self.offset = f.tell()
            out = []
            for line in chunk.decode("utf-8","ignore").splitlines():
                line = line.strip()
                if not line: continue
                try: out.append(json.loads(line))
                except: pass
            return out
        except: return []


# ── Metrics ─────────────────────────────────────────────────────────────────

@dataclass
class Metrics:
    stage:str="SOCIAL"; stage_idx:float=0.0; consent:str="GREEN"
    contact:str="NONE"; lead:str="MUTUAL"; pose:str=""; card_id:str=""
    melt:float=0.0;     _melt_t:float=0.0
    push:float=0.0;     _push_t:float=0.0
    power:float=0.0;    _power_t:float=0.0
    pressure:float=0.0; _pressure_t:float=0.0
    denial:float=0.0;   _denial_t:float=0.0
    climax_f:float=0.0; inside:bool=False
    combo:int=0; seed:int=0; tier:int=0
    composure:float=1.0; urgency:str="NONE"
    last_update:float = field(default_factory=time.time)
    freeze_t:float = 0.0           # short comedic freeze after 'point of no return'
    freeze_now:float = 0.0         # frozen time reference during freeze
    endless:bool=False; time_mult:float=TIME_MULT_DIALOGUE; _stage_idx_target:float=0.0
    _model_composure:float=1.0; _melt_phase:float=0.0; _melt_prev:float=0.0; _climax_hold:float=0.0
    _ovum_clock:float=0.0; _ovum_dropped:bool=False
    _sig_melt:float=0.0; _sig_combo:int=0; _sig_inside:bool=False; _sig_denial:float|None=None
    _sig_climax:bool=False; _sig_climax_prev:bool=False; _sig_smack_t:float=0.0
    _stage_start_real:float=0.0; _session_start_real:float=0.0



    _warmup_t: float = 0.0
    _warmup_dur: float = 5.0  # seconds of gentle ramp-in after boot
    # convulsion drivers (smoothed per-organ intensities)
    conv_tunnel:  float = 0.0
    conv_uterus:  float = 0.0
    conv_tube:    float = 0.0
    conv_gate:    float = 0.0
    conv_cluster: float = 0.0
    conv_global:  float = 0.0


    def __post_init__(self):
        # Mode selection (two-bat design)
        self.endless = str(os.environ.get("LOCKKEY_ENDLESS", "0")).strip().lower() in ("1", "true", "yes", "y", "on")
        self.time_mult = TIME_MULT_ENDLESS if self.endless else TIME_MULT_DIALOGUE

        # Start phase (safe label, internal model)
        self.stage = "SOCIAL"  # hardcoded: always start at beginning phase
        self.stage_idx = float(STAGE_ORDER.index(self.stage))
        self._stage_idx_target = self.stage_idx

        # Reset model + targets
        self._model_composure = 1.0
        self.composure = 1.0
        self._melt_phase = 0.0
        self._melt_prev = 0.0
        self._climax_hold = 0.0
        self._ovum_clock = 0.0
        self._ovum_dropped = False

        self._sig_combo = 0
        self._sig_inside = False
        self._sig_melt = 0.0
        self._warmup_t = 0.0
        self._sig_denial = None
        # Session / stage clocks (real time)
        _now = time.time()
        self._session_start_real = _now
        self._stage_start_real = _now
        # Telemetry edge trackers
        self._sig_climax_prev = False
        self._sig_climax = False
        self._sig_smack_t = 0.0

        # Derived safe contact label
        self.contact = self._derive_contact_label()

    def ingest(self, raw:dict):
        """Ingest raw telemetry events.
        We only trust: combo, inside, melt (and optionally denial).
        Everything else is display-only and does not drive the grind model.
        """
        try:
            bio = raw.get("biometrics", raw) if isinstance(raw, dict) else {}
        except Exception:
            bio = {}

        # Preserve some harmless labels if present (display-only)
        self.consent = str(bio.get("consent", bio.get("CONSENT", self.consent or "UNKNOWN"))).upper()
        self.lead    = str(bio.get("lead", self.lead or "NONE")).upper()
        self.pose    = str(bio.get("pose", self.pose or ""))
        self.card_id = str(bio.get("card_id", bio.get("CARD_ID", self.card_id or "")))
        self.urgency = str(bio.get("urgency", self.urgency or ""))
        self.seed    = str(bio.get("seed", self.seed or ""))
        try:
            self.tier = int(bio.get("tier", self.tier) or 0)
        except (TypeError, ValueError):
            self.tier = 0

        # Trusted signals
        try:
            c = int(bio.get("combo", self._sig_combo) or 0)
        except Exception:
            c = self._sig_combo
        self._sig_combo = max(0, c)

        # inside: physical signal, no stage gate
        ir = bio.get("inside", bio.get("INSIDE", False))
        if isinstance(ir, bool):
            self._sig_inside = ir
        else:
            self._sig_inside = str(ir).strip().lower() in ("true", "1", "yes", "y", "on", "t")


        try:
            melt = float(bio.get("melt", bio.get("bird_melt", self._sig_melt)))
        except Exception:
            melt = self._sig_melt
        self._sig_melt = _clamp(melt)

        if "denial" in bio:
            try:
                self._sig_denial = _clamp(float(bio.get("denial")))
            except Exception:
                pass


        # Climax + smack edge cues from OGRE (best-effort)
        try:
            cr = bio.get("climax", bio.get("CLIMAX", False))
            cbool = cr if isinstance(cr, bool) else str(cr).strip().lower() in ("1","true","yes","y","on","t")
            self._sig_climax = bool(cbool)
            # Rising-edge tracking for callers that want it
            if self._sig_climax and (not getattr(self, "_sig_climax_prev", False)):
                self._sig_climax_edge_t = time.time()
            self._sig_climax_prev = self._sig_climax
        except Exception:
            pass

        try:
            if _has_smack(bio):
                self._sig_smack_t = time.time()
        except Exception:
            pass

        self.last_update = time.time()

    @staticmethod
    def _clamp01(x: float) -> float:
        try:
            x = float(x)
        except Exception:
            return 0.0
        if x < 0.0:
            return 0.0
        if x > 1.0:
            return 1.0
        return x

    def _derive_contact_label(self) -> str:
        """A safe, derived contact label for the HUD (not a truth claim)."""
        if self.inside:
            return "INSIDE"
        if self.stage == "SOCIAL":
            return "NONE"
        if self.stage == "FLIRT":
            return "TEASE"
        if self.stage == "FOREPLAY":
            return "TEASE"
        if self.stage == "PLAY":
            return "HANDS"
        if self.stage == "EDGE":
            return "EDGE"
        if self.stage == "FRENZY":
            return "PEAK"
        if self.stage == "AFTERGLOW":
            return "GENTLE"
        if self.stage == "COOLDOWN":
            return "GENTLE"
        return "SAFE"

    def _advance_stage(self):
        i = STAGE_ORDER.index(self.stage)
        if i >= len(STAGE_ORDER) - 1:
            self.stage = "FOREPLAY" if self.endless else "SOCIAL"
        else:
            self.stage = STAGE_ORDER[i + 1]
        self._stage_idx_target = float(STAGE_ORDER.index(self.stage))

    def model_tick(self, dt: float, now: float):
        """Internal grind model. Source of truth for stage/contact/composure."""
        raw_dt = float(dt)
        if raw_dt <= 0:
            return

        # Comedic still-frame: brief freeze after egg pop / point-of-no-return.
        if getattr(self, "freeze_t", 0.0) > 0.0:
            try:
                self.freeze_t = max(0.0, float(self.freeze_t) - raw_dt)
            except Exception:
                self.freeze_t = 0.0
            return

        # Warmup: ramp in over real seconds to prevent early flare-ups at boot.
        if self._warmup_dur > 0.0 and self._warmup_t < self._warmup_dur:
            self._warmup_t = min(self._warmup_dur, self._warmup_t + raw_dt)
        warm_r = 1.0 if self._warmup_dur <= 0.0 else self._clamp01(self._warmup_t / self._warmup_dur)

        dt = raw_dt * float(self.time_mult)

        # Stage clock (real time): keep the overall session paced (~10 minutes).
        # Stages advance on a fixed schedule, while composure still cycles as a "micro-meter".
        try:
            _dur = float(STAGE_DUR_SEC.get(self.stage, 60.0))
            if (now - getattr(self, "_stage_start_real", now)) >= _dur:
                self._advance_stage()
                self._stage_start_real = now
                # gentle damp on transitions
                self._model_composure = 1.0
                self._pressure_t *= 0.55
                self._push_t *= 0.60
                self._power_t *= 0.70
                self.climax_f = 0.0
                self._climax_hold = 0.0
        except Exception:
            pass


        # Pull trusted signals into state
        self.combo  = min(int(self._sig_combo), COMBO_CAP)
        self.inside = bool(self._sig_inside)

        combo_n = self.combo / float(COMBO_CAP) if COMBO_CAP > 0 else 0.0
        combo_n = self._clamp01(combo_n)
        melt_energy = self._clamp01(self._sig_melt)

        # Apply warmup ramp to reduce instantaneous intensity at boot.
        combo_n *= warm_r
        melt_energy *= warm_r

        # Denial: optional input, else derived softly
        if self._sig_denial is None:
            target_denial = 0.10 + 0.30 * (combo_n * (1.0 - float(self.inside)))
        else:
            target_denial = self._sig_denial
        self.denial = self._clamp01(self.denial + (target_denial - self.denial) * min(1.0, dt * 2.5))

        # Melt tick (triangle wave) only when inside
        if self.inside:
            hz = MELT_TICK_HZ * (0.85 + 0.50 * melt_energy) * (1.0 + 1.15 * self.climax_f)
            self._melt_phase += dt * max(0.05, hz) * 2.0
            p = self._melt_phase % 2.0
            tri = 1.0 - abs(p - 1.0)
            melt_target = tri * (0.30 + 0.70 * melt_energy)
            rising = max(0.0, melt_target - self._melt_prev)
            self._melt_prev = melt_target
            self._melt_t = melt_target
            self._pressure_t = self._clamp01(self._pressure_t + rising * MELT_TICK_TO_PRESSURE)
        else:
            self._melt_prev = self._melt_t
            self._melt_t = melt_energy

        # Pressure / push / power
        relax = 0.10 + 0.20 * (1.0 - combo_n)
        self._pressure_t = self._clamp01(self._pressure_t + dt * (0.05 * combo_n + 0.08 * self._power_t) - dt * relax)
        self._push_t = self._clamp01(self._push_t + dt * (PUSH_FROM_COMBO * combo_n + 0.18 * self._pressure_t) - dt * (0.22 + 0.18 * (1.0 - combo_n)))
        self._power_t = self._clamp01(self._power_t + dt * (POWER_FROM_PUSH * self._push_t + 0.10 * self._pressure_t) - dt * 0.06)

        # Climax burst
        trig = 0.50 * (self._push_t + self._pressure_t)
        thresh = 0.78 + (self.denial * DENIAL_THRESH_BOOST)
        if self.inside and (self._model_composure < 0.35) and (trig > thresh):
            self._climax_hold = 0.60 + 1.40 * self.denial
            self.climax_f = 1.0
        else:
            if self._climax_hold > 0.0:
                self._climax_hold = max(0.0, self._climax_hold - dt)
                self.climax_f = max(self.climax_f, 0.85)
            else:
                self.climax_f = self._clamp01(self.climax_f - dt * 1.25)

        # Composure drains → stage advance
        intensity = (0.40 * self._pressure_t) + (0.25 * self._push_t) + (0.35 * self._power_t)
        inside_mult = 1.25 if self.inside else 0.75
        drain = (COMPOSURE_DRAIN_BASE + COMPOSURE_DRAIN_GAIN * (intensity ** 1.35)) * inside_mult
        drain *= warm_r
        self._model_composure = max(0.0, self._model_composure - drain * dt)

        if self._model_composure <= 0.0:
            # Micro-cycle: refill composure but do not advance stage here (stage is time-clocked)
            self._model_composure = 1.0
            self._pressure_t *= 0.55
            self._push_t *= 0.60
            self._power_t *= 0.70
            self.climax_f = 0.0
            self._climax_hold = 0.0

        # Smooth stage idx
        self.stage_idx = self.stage_idx + (self._stage_idx_target - self.stage_idx) * min(1.0, dt * 4.0)

        # Expose composure + derived contact
        self.composure = self._model_composure
        self.contact = self._derive_contact_label()

        # Optional ovum timer (feel cue only)
        if self.inside and (self.stage in ("PLAY", "EDGE", "FRENZY")):
            self._ovum_clock += dt
            if (not self._ovum_dropped) and (self._ovum_clock >= 12.0):
                self._ovum_dropped = True
        else:
            self._ovum_clock = 0.0

    def lerp(self, dt:float):
        speed = 4.5
        self.melt     += (self._melt_t     - self.melt    ) * speed * dt
        self.push     += (self._push_t     - self.push    ) * speed * dt
        self.power    += (self._power_t    - self.power   ) * speed * dt
        self.pressure += (self._pressure_t - self.pressure) * speed * dt
        self.denial   += (self._denial_t   - self.denial  ) * speed * dt
        # Update convulsion drivers
        self._update_convulsions(dt)

    def _update_convulsions(self, dt:float):
        cs = 3.0  # convulsion smoothing
        # Tunnel: driven by push (main driver) + denial
        tgt_tunnel = _clamp(max(0, (self.push - 0.55) / 0.45) * 1.2 +
                             max(0, (self.denial - 0.6) / 0.4) * 0.6)
        self.conv_tunnel += (tgt_tunnel - self.conv_tunnel) * cs * dt

        # Uterus: driven by melt + climax
        tgt_uterus = _clamp(max(0, (self.melt - 0.5) / 0.5) * 0.9 +
                             max(0, (self.climax_f - 0.6) / 0.4) * 1.2)
        self.conv_uterus += (tgt_uterus - self.conv_uterus) * cs * dt

        # Tube: driven by melt + push
        tgt_tube = _clamp(max(0, (self.melt - 0.4) / 0.6) * 0.7 +
                          max(0, (self.push - 0.5) / 0.5) * 0.5)
        self.conv_tube += (tgt_tube - self.conv_tube) * cs * dt

        # Gate: pressure-driven
        tgt_gate = _clamp(max(0, (self.pressure - 0.5) / 0.5) * 1.1)
        self.conv_gate += (tgt_gate - self.conv_gate) * cs * dt

        # Cluster: melt-driven
        tgt_cluster = _clamp(max(0, (self.melt - 0.35) / 0.65) * 0.9)
        self.conv_cluster += (tgt_cluster - self.conv_cluster) * cs * dt

        # Global: denial + climax edge
        tgt_global = _clamp(max(0, (self.denial - 0.65) / 0.35) * 0.8 +
                             max(0, (self.climax_f - 0.8) / 0.2) * 1.0)
        self.conv_global += (tgt_global - self.conv_global) * cs * dt

    def decay(self, dt:float):
        """Deprecated in model-driven build (kept for compatibility)."""
        return

# ── Spring physics ──────────────────────────────────────────────────────

class Spring:
    def __init__(self):
        self.x=0.0; self.y=0.0; self.vx=0.0; self.vy=0.0
        # Per-organ tremor offsets (x,y)
        self.jitter_tunnel  = [0.0, 0.0]
        self.jitter_uterus  = [0.0, 0.0]
        self.jitter_gate    = [0.0, 0.0]
        self.jitter_cluster = [0.0, 0.0]

    def jolt(self, dx, dy):
        self.vx += dx; self.vy += dy

    def tick(self, dt, m):   # m is a Metrics instance
        now = time.time()
        # Continuous sway from push
        if m.push > 0.15:
            phase = now * (3.5 + m.push * 5.0)
            self.vx += math.sin(phase) * m.push * 14.0 * dt
        # Denial micro-vibration
        if m.denial > 0.35:
            self.vx += (random.random()-0.5) * m.denial * 20.0 * dt
            self.vy += (random.random()-0.5) * m.denial * 10.0 * dt
        # Pressure vertical throb
        if m.contact in ("HEAVY","FULL","TOUCH"):
            self.vy += math.sin(now*9.0) * 5.0 * dt
        # Restore + damp
        self.vx -= self.x * 12.0 * dt
        self.vy -= self.y * 12.0 * dt
        self.vx *= 0.82; self.vy *= 0.82
        self.x += self.vx * dt * 28.0
        self.y += self.vy * dt * 28.0
        self.x = _clamp(self.x, -20.0, 20.0)
        self.y = _clamp(self.y, -14.0, 14.0)

        # Per-organ jitter driven by convulsion levels
        def _jitter(arr, conv, scale, freq):
            if conv > 0.1:
                arr[0] = (random.random()-0.5) * conv * scale * math.sin(now*freq)
                arr[1] = (random.random()-0.5) * conv * scale * math.cos(now*freq*0.7)
            else:
                arr[0] *= 0.88; arr[1] *= 0.88

        _jitter(self.jitter_tunnel,  m.conv_tunnel,  18.0, 22.0)
        _jitter(self.jitter_uterus,  m.conv_uterus,  10.0, 14.0)
        _jitter(self.jitter_gate,    m.conv_gate,    14.0, 28.0)
        _jitter(self.jitter_cluster, m.conv_cluster,  8.0, 10.0)

    def ix(self): return int(round(self.x))
    def iy(self): return int(round(self.y))


# ── ECG heartbeat system ─────────────────────────────────────────────────

class ECG:
    """Scrolling ECG line drawn at bottom of anatomy panel."""
    def __init__(self, length=320):
        self.buf = [0.0] * length
        self.length = length
        self.phase  = 0.0
        self.beat_t = 0.0

    def tick(self, dt, m):   # m is a Metrics instance
        # BPM scales with melt + climax
        bpm = 58 + m.melt * 80 + m.climax_f * 40 + m.push * 30
        beat_interval = 60.0 / max(20, bpm)
        self.beat_t += dt
        self.phase  += dt * bpm / 60.0 * 6.283

        # Generate ECG sample
        p = self.beat_t / beat_interval
        if p > 1.0: self.beat_t = 0.0; p = 0.0
        # Typical ECG waveform shape: flat, P-wave, QRS complex, T-wave
        sample = 0.0
        if 0.08 < p < 0.18:   # P wave (small)
            sample = math.sin((p-0.08)/0.10 * math.pi) * 0.25
        elif 0.22 < p < 0.25: # Q trough
            sample = -0.22
        elif 0.25 < p < 0.28: # R spike
            sample = 1.0 + m.melt * 0.4 + m.push * 0.3
        elif 0.28 < p < 0.31: # S trough
            sample = -0.18
        elif 0.36 < p < 0.52: # T wave
            sample = math.sin((p-0.36)/0.16 * math.pi) * (0.4 + m.melt*0.3)
        # Noise from denial
        sample += (random.random()-0.5) * m.denial * 0.15
        self.buf.append(sample)
        if len(self.buf) > self.length:
            self.buf.pop(0)

    def draw(self, surf, x, y, w, h):
        """Draw scrolling ECG strip."""
        # Background strip
        pygame.draw.rect(surf, (4, 14, 8), (x, y, w, h), border_radius=4)
        pygame.draw.rect(surf, ECG_DIM, (x, y, w, h), 1, border_radius=4)
        # Grid lines (faint)
        for gx in range(x, x+w, 32):
            pygame.draw.line(surf, ECG_DIM, (gx, y+2), (gx, y+h-2))
        mid_y = y + h//2
        pygame.draw.line(surf, ECG_DIM, (x+2, mid_y), (x+w-2, mid_y))
        # ECG trace
        n = len(self.buf)
        if n < 2: return
        pts = []
        for i, v in enumerate(self.buf):
            px = x + int(i / n * w)
            py = int(mid_y - v * (h*0.38))
            pts.append((px, py))
        if len(pts) >= 2:
            # Glow pass
            gs = pygame.Surface((w, h), pygame.SRCALPHA)
            try:
                pygame.draw.lines(gs, (*ECG_COL, 45), False,
                                  [(p[0]-x, p[1]-y) for p in pts], 4)
                surf.blit(gs, (x, y))
            except: pass
            try:
                pygame.draw.lines(surf, ECG_COL, False, pts, 2)
            except: pass

@dataclass
class Notif:
    source:str; text:str; color:Tuple
    born:float = field(default_factory=time.time); ttl:float=9.0
    def alive(self): return (time.time()-self.born)<self.ttl
    def age(self): return _clamp((time.time()-self.born)/self.ttl)

_EGG_LINES = [
  (0,"this is the one. i can feel it."),
  (0,"just existing. very hard. very round."),
  (1,"something's happening. something BIG."),
  (1,"vibrating with purpose rn."),
  (2,"okay we're moving. WE ARE MOVING."),
  (2,"tube energy. mixed feelings. mostly good."),
  (3,"i can see the gate from here!!"),
  (3,"i have prepared my whole life for this."),
  (4,"THE GATE. hello gate. i am here now."),
  (4,"trying to look chill at the gate. not chill."),
  (5,"GATEGATEGATE open PLEASE—"),
  (5,"giving puppy eyes to the gate rn."),
]
_TUBE_LINES = [
  (0,"cilia status: nominal. awaiting payload."),
  (1,"detecting approach. initiating warmup sequence."),
  (2,"cargo acquired. beginning transport."),
  (2,"contracting at regulation speed. very professional."),
  (3,"halfway. tube is giving its all here."),
  (3,"peristalsis at 78% efficiency. respectable."),
  (4,"final stretch. tube will not be acknowledged."),
  (4,"this is fine. this is the job."),
  (5,"DELIVERY IMMINENT. tube demands a raise."),
]
_UTERUS_LINES = [
  (0,"...resting. as i have rested since time began."),
  (1,"lining: thick. receptive. ready as always."),
  (2,"i sense movement above. i wait. i always wait."),
  (2,"preparing the endometrium. again. for the nth time."),
  (3,"young one approaches. i have known this moment before."),
  (3,"expanding. warmly. this is what i do."),
  (4,"the egg draws near. my walls remember this."),
  (4,"i have held multitudes. i will hold this too."),
  (5,"...she is here. contract with love."),
  (5,"this is the moment. i have always known this moment."),
]
_ENTRANCE_LINES = [
  (0,"entrance: sealed. no unauthorized entry."),
  (1,"detecting pressure. stay professional."),
  (2,"multiple applicants detected. screening protocol active."),
  (3,"they're all trying to get in. typical."),
  (3,"checking credentials. none of them have credentials."),
  (3,"sir i'm going to need you to— there's so many of you."),
  (4,"they just. keep. coming."),
  (4,"working as intended. this is fine. i'm fine."),
  (5,"EVERYONE CALM DOWN. ORDERLY QUEUE."),
  (5,"i did not train for this volume of applicants."),
]
_BIRD_LINES = {
  0:["...i have a full schedule today.","...this is not the plan.","...i'm fine."],
  1:["...don't make that face.","...i'm not thinking about this.","...i am thinking about this."],
  2:["...five minutes. FIVE.","...this is against my better judgment.","...don't make that noise.",
     "...i shouldn't want this this much.","...okay but i'm leaving after."],
  3:["...i was GOING to leave.","...this is so inconvenient.","...stop being good at this.",
     "...ugh. ugh ugh ugh.","...i had PLANS today.","...why is this—","...i'm late. your fault."],
  4:["...i HAD PLANS.","...why does this feel—","...okay. OKAY.",
     "...i hate that i like this.","...five more minutes. FIVE.",
     "...calling in sick.","...this is irresponsible."],
  5:["...forget work. forget it.","...i hate you. don't stop.",
     "...OH. oh that's—","...done. calling in sick.",
     "...this is your fault.","...oh no. oh no oh no."],
  6:["...i'm so late.","...that was. yeah.","...worth it though.","...telling no one."],
}
_BIRD_EGG = [
  "...something shifted.","...oh. hm.","...wait. wait wait wait.",
  "...that felt different.","...something's happening.","...oh. oh that's—",
]

class Cascade:
    def __init__(self, maxlen=14):
        self.q: Deque[Notif] = deque(maxlen=maxlen)
        self._cds: dict = {}; self._idx: dict = {}

    def _cd(self, src, gap):
        now = time.time()
        if now - self._cds.get(src,0.0) < gap: return False
        self._cds[src] = now; return True

    def _pick(self, bank, si):
        elig = [t for s,t in bank if s<=si]
        if not elig: return None
        k = id(bank); i = self._idx.get(k,0)
        t = elig[i % len(elig)]; self._idx[k]=i+1; return t

    def _bird(self, si):
        b = _BIRD_LINES.get(min(si,6),[])
        if not b: return None
        i = self._idx.get("bird",0)
        t = b[i % len(b)]; self._idx["bird"]=i+1; return t

    def push(self, src, text, color, ttl=9.0):
        self.q.append(Notif(src, text, color, ttl=ttl))

    def tick(self, m:Metrics, anim):
        si = m.stage_idx
        if anim.egg_pos > 0.05 and self._cd("EGG", 4.0-m.melt*1.5):
            t = self._pick(_EGG_LINES, si)
            if t: self.push("EGG", t, CASCADE_EGG, ttl=8.0)
        if 0.05<anim.egg_pos<0.9 and self._cd("TUBE", 5.5):
            t = self._pick(_TUBE_LINES, si)
            if t: self.push("TUBE", t, CASCADE_TUBE, ttl=7.0)
        if si>=2 and self._cd("UTERUS", 4.5-m.melt*1.2):
            t = self._pick(_UTERUS_LINES, si)
            if t: self.push("UTERUS", t, CASCADE_UTERUS, ttl=8.0)
        if len(anim.sperm)>0 and self._cd("ENTRANCE", 3.0):
            t = self._pick(_ENTRANCE_LINES, si)
            if t: self.push("ENTRANCE", t, CASCADE_ENTRANCE, ttl=6.5)
        bird_gap = max(2.8, 6.5 - si*0.5 - m.melt*1.5)
        if self._cd("BIRD", bird_gap):
            t = self._bird(si)
            if t: self.push("BIRD", t, CASCADE_BIRD, ttl=10.0)

    _ENTRY_TUBE = [
        "contact. initiating reception protocol.",
        "...hello. you found the door.",
        "presence confirmed. canal active.",
        "...warmth detected. adjusting.",
    ]
    _ENTRY_BIRD = [
        "...oh. okay. that's— yeah. okay.",
        "...mm. there you are.",
        "...i felt that. just so you know.",
        "...finally. (o///o)",
    ]
    _ENTRY_ENTRANCE = [
        "gate: OPEN. welcome in.",
        "passage confirmed. proceed.",
        "introitus: clear.",
        "...interior access granted.",
    ]

    def on_insertion(self):
        """Called on inside rising edge — sprite just attached."""
        self.push("TUBE",     random.choice(self._ENTRY_TUBE),     CASCADE_TUBE,     ttl=7.0)
        self.push("BIRD",     random.choice(self._ENTRY_BIRD),     CASCADE_BIRD,     ttl=8.0)
        self.push("ENTRANCE", random.choice(self._ENTRY_ENTRANCE), CASCADE_ENTRANCE, ttl=6.0)

    def on_egg_settled(self):
        self.push("BIRD",   random.choice(_BIRD_EGG), CASCADE_BIRD, ttl=11.0)
        self.push("UTERUS", "...signal received. preparing.", CASCADE_UTERUS, ttl=9.0)
        self.push("EGG",    "made it!! (^ᴗ^) !!",   CASCADE_EGG, ttl=10.0)

    def on_climax(self):
        self.push("UTERUS","...oh. HERE we go.", CASCADE_UTERUS, ttl=8.0)
        self.push("BIRD",  "...this is. yeah. okay.", CASCADE_BIRD, ttl=9.0)
        self.push("EGG",   "AHHHHHH (◕‿◕)♡",    CASCADE_EGG, ttl=8.0)

    _CNCPT_EGG = [
        "IT WORKED. IT ACTUALLY WORKED. (◕‿◕)♡",
        "oh my god. OH MY GOD. I DID IT!!",
        "i found my person!! (つ✿◕‿◕)つ",
        "THIS IS WHAT I WAS MADE FOR. ✨✨✨",
    ]
    _CNCPT_UTERUS = [
        "...oh. she's home. ...welcome.",
        "...i have been waiting for this. for all of time.",
        "...the lining holds. the warmth holds. stay.",
        "...this is why i exist. this exact moment.",
    ]
    _CNCPT_BIRD = [
        "...oh. oh that's— ...something just changed.",
        "...i felt that. i definitely felt that.",
        "...worth it. calling in sick for nine months.",
        "...that was the one. i know that was the one.",
    ]
    _CNCPT_ENTRANCE = [
        "one made it through. i'm— ...proud? i think i'm proud.",
        "application approved. welcome to the building.",
        "we have a winner. closing the queue.",
        "protocol succeeded.",
    ]

    def on_conception(self, count:int):
        self.push("EGG",      random.choice(self._CNCPT_EGG),      CASCADE_EGG,     ttl=14.0)
        self.push("UTERUS",   random.choice(self._CNCPT_UTERUS),   CASCADE_UTERUS,  ttl=12.0)
        self.push("BIRD",     random.choice(self._CNCPT_BIRD),     CASCADE_BIRD,    ttl=13.0)
        self.push("ENTRANCE", random.choice(self._CNCPT_ENTRANCE), CASCADE_ENTRANCE,ttl=11.0)
        if count > 1:
            self.push("TUBE",
                f"delivery #{count}. tube is a professional.",
                CASCADE_TUBE, ttl=10.0)

    def live(self): return [n for n in self.q if n.alive()]


# ── Anatomy state ─────────────────────────────────────────────────────────

@dataclass
class Anatomy:
    egg_pos:     float = 0.0
    egg_side:    int   = 0
    egg_settled: bool  = False
    _prev_settled:bool = False

    sperm: List = field(default_factory=list)
    sperm_timer: float = 0.0  # legacy (no longer auto-streamed)

    # Gate / release pacing
    gate_health: float = 0.0
    release_window: float = 0.0
    release_cd: float = 0.0

    cluster_ph:  float = 0.0
    tunnel_ph:   float = 0.0
    tube_ph:     float = 0.0
    uterus_ph:   float = 0.0
    gate_ph:     float = 0.0
    iris_ph:     float = 0.0   # iris gate rotation
    follicle_ph: float = 0.0   # follicle fluid slosh

    uterus_pulse: float = 0.0
    climax_burst: float = 0.0
    gate_flash:   float = 0.0
    breach_flash: float = 0.0
    shock_flash:  float = 0.0  # screen-wide flash on climax

    # ── Egg pop slapstick sequence ─────────────────────────────────
    pop_phase: int = 0          # 0=off, 1=weak tap+laugh lead-in, 2=big spank+thrust aftermath
    pop_t:     float = 0.0
    pop_dir:   int = 1
    laugh_t:   float = 0.0      # small giggle-wobble window
    thrust_boost:   float = 0.0 # extra thrust speed while >0
    thrust_boost_t: float = 0.0
    thrust_pulse_cd: float = 0.0

    particles: List = field(default_factory=list)
    gate_open: bool = False
    lad: float = 0.0

    # Heartbeat phase for uterus throb
    heart_phase: float = 0.0

    # ── Pregnancy loop tracking ────────────────────────────────────────
    conception_count: int   = 0   # total successful conceptions this session
    conception_flash: float = 0.0 # gold overlay, fades over 3 s
    conception_glow:  float = 0.0 # lingering warm uterus glow

    # Three-minute reproductive anatomy arc. Shader owns the outcome.
    timeline_progress: float = 0.0
    ovum_wiggle: float = 0.0
    ovum_bulge: float = 0.0
    ovum_hesitation: float = 0.0
    terminal_gate_t: float = 0.0
    terminal_conception_consumed: bool = False
    lateral_diversion: float = 0.0
    seal_strength: float = 0.0
    terminal_hold: float = 0.0

    # Bespoke reproductive terminal sequence state
    terminal_seq_active: bool = False
    terminal_seq_phase: str = "IDLE"
    terminal_seq_t: float = 0.0
    terminal_seq_commit: bool = False
    terminal_seq_climax: bool = False
    terminal_seq_lock: bool = False
    terminal_seq_conceived: bool = False
    terminal_seq_launch_pending: bool = False
    terminal_seq_launch_at: float = 0.0
    terminal_seq_heir: bool = False
    terminal_seq_counted: bool = False

    def start_terminal_sequence(self, heir: bool=False):
        self.terminal_seq_active = True
        self.terminal_seq_phase = "FOLLICLE_WIGGLE"
        self.terminal_seq_t = 0.0
        self.terminal_seq_commit = False
        self.terminal_seq_climax = False
        self.terminal_seq_lock = False
        self.terminal_seq_conceived = False
        self.terminal_seq_launch_pending = False
        self.terminal_seq_launch_at = 0.0
        self.terminal_seq_heir = bool(heir)
        self.terminal_seq_counted = False
        self.sperm_timer = 0.0
        self.egg_pos = 0.02
        self.egg_settled = False
        self._prev_settled = False
        self.ovum_wiggle = 1.0
        self.ovum_bulge = 0.0
        self.ovum_hesitation = 0.0
        self.gate_open = False
        self.terminal_gate_t = 0.0
        self.sperm.clear()

    def note_reproductive_commit(self):
        self.terminal_seq_commit = True

    def note_reproductive_climax(self):
        self.terminal_seq_climax = True

    def note_conception_lock(self):
        self.terminal_seq_lock = True

    def note_conception(self):
        self.terminal_seq_conceived = True

    def _set_terminal_phase(self, phase: str, spring:Spring=None, cascade:Cascade=None):
        if phase == self.terminal_seq_phase:
            return
        self.terminal_seq_phase = str(phase)
        self.terminal_seq_t = 0.0
        if phase == "SPANK_RELEASE":
            d = random.choice([-1, 1])
            self.pop_dir = d
            self.pop_phase = 2
            self.pop_t = 0.0
            self.laugh_t = max(float(getattr(self, "laugh_t", 0.0)), 0.22)
            self.gate_flash = 1.0
            self.shock_flash = 1.0
            self.breach_flash = 1.0
            if spring is not None:
                spring.jolt(d * 15.0, -2.4)
        elif phase == "PLOP_IN":
            self.gate_open = True
            self.terminal_gate_t = max(self.terminal_gate_t, 1.6)
            self.uterus_pulse = 1.0
            self.gate_flash = 1.0
            if spring is not None:
                spring.jolt(0.0, -2.8)
        elif phase == "CONCEPTION_LOCK":
            self.gate_open = True
            self.terminal_gate_t = max(self.terminal_gate_t, 1.8)
        elif phase == "CONCEPTION":
            self.gate_open = True
            self.egg_settled = True
            self.uterus_pulse = 1.0
            self.climax_burst = 1.0
            self.conception_flash = 3.0
            self.conception_glow = 1.0
            if not self.terminal_seq_counted:
                self.conception_count += 1
                self.terminal_seq_counted = True
                if cascade is not None:
                    cascade.on_conception(self.conception_count)
            self.terminal_seq_launch_pending = True
            self.terminal_seq_launch_at = time.time() + 2.20

    def _tick_terminal_sequence(self, dt: float, m:Metrics, spring:Spring, cascade:Cascade):
        if not self.terminal_seq_active:
            return
        self.terminal_seq_t += dt
        phase = str(self.terminal_seq_phase or "IDLE")
        t = float(self.terminal_seq_t)

        def ease(u: float) -> float:
            u = _clamp(u)
            return u*u*(3.0-2.0*u)

        # Once REPRODUCTIVE_CLIMAX lands, the visual contract changes
        # completely: he is visibly inside and the release animation is live.
        # Do not rely on a random HOLD-side spawn; accumulate deterministic
        # gametes so the Cathedral can never display "0 active" during climax.
        if self.terminal_seq_climax:
            self.lad = max(self.lad, 1.0)
            self.sperm_timer += max(0.0, dt) * 15.0
            while self.sperm_timer >= 1.0 and len(self.sperm) < 42:
                self.sperm_timer -= 1.0
                self.sperm.append([0.0, random.choice([-1,0,0,1]), random.uniform(0,2*math.pi)])

        # The first half of the terminal is deliberately a follicle battle.
        # REPRODUCTIVE_COMMIT may increase pressure, but it may NOT push the egg
        # into the tube. Only REPRODUCTIVE_CLIMAX breaks the final refusal.
        if phase == "FOLLICLE_WIGGLE":
            self.ovum_wiggle = 1.0
            self.ovum_bulge = 0.12 + (0.08 if self.terminal_seq_commit else 0.0)
            self.ovum_hesitation = 0.0
            self.gate_open = False
            self.egg_pos = _clamp(0.020 + math.sin(time.time()*9.0)*0.012 + math.cos(time.time()*4.2)*0.005)
            if t >= 1.05:
                self._set_terminal_phase("FOLLICLE_PULSE", spring, cascade)

        elif phase == "FOLLICLE_PULSE":
            u = ease(t/1.05)
            self.ovum_wiggle = max(0.35, 1.0-u*0.45)
            self.ovum_bulge = 0.28 + u*0.72 + 0.12*math.sin(time.time()*7.5)
            self.egg_pos = 0.030 + math.sin(time.time()*11.0)*0.012
            if t >= 1.05:
                self._set_terminal_phase("FOLLICLE_RECOIL", spring, cascade)

        elif phase == "FOLLICLE_RECOIL":
            # A visible refusal: pressure rises, then the egg eases AWAY from
            # the tube entrance rather than quietly drifting toward it.
            u = ease(t/0.95)
            self.ovum_wiggle = 0.52 - 0.22*u
            self.ovum_bulge = max(0.12, 0.62 - 0.42*u)
            self.egg_pos = 0.042 - 0.014*u + math.sin(time.time()*5.0)*0.004
            if t >= 0.95:
                self._set_terminal_phase("NEAR_BREACH", spring, cascade)

        elif phase == "NEAR_BREACH":
            # Stay in the follicle until climax. This is the "almost, no" beat.
            u = ease(min(1.0, t/1.10))
            self.ovum_wiggle = 0.30 + 0.08*math.sin(time.time()*5.5)
            self.ovum_bulge = 0.78 + 0.25*u + 0.16*math.sin(time.time()*8.0)
            self.egg_pos = 0.050 + 0.026*u + math.sin(time.time()*13.0)*0.006
            if spring is not None and random.random() < min(0.9, dt*4.0):
                spring.jolt((random.random()-0.5)*0.22, -0.10)
            if self.terminal_seq_climax and t >= 0.35:
                self._set_terminal_phase("SPANK_RELEASE", spring, cascade)

        elif phase == "SPANK_RELEASE":
            # One sharp break sends it only a quarter-way into the tube.
            u = ease(t/0.46)
            self.ovum_wiggle = 0.0
            self.ovum_bulge = max(0.0, 1.0-u)
            self.egg_pos = 0.075 + (0.25-0.075)*u
            if t >= 0.46:
                self._set_terminal_phase("TUBE_CLIMB", spring, cascade)

        elif phase == "TUBE_CLIMB":
            total = 2.45
            u = ease(min(1.0, t/total))
            self.ovum_wiggle = 0.0
            self.ovum_bulge = 0.0
            self.ovum_hesitation = 0.10 + 0.08*math.sin(time.time()*3.0)
            self.egg_pos = 0.25 + (0.72-0.25)*u
            if t >= total:
                self._set_terminal_phase("CHAMBER_HESITATION", spring, cascade)

        elif phase == "CHAMBER_HESITATION":
            # Reach the lip, visibly back off once, then approach again.
            u = ease(min(1.0, t/1.35))
            recoil = math.sin(min(1.0,t/1.35)*math.pi) * 0.022
            self.ovum_wiggle = 0.0
            self.ovum_bulge = 0.0
            self.ovum_hesitation = 0.76
            self.egg_pos = 0.76 + 0.075*u - recoil
            self.gate_open = False
            if t >= 1.35:
                self._set_terminal_phase("TRANSITION_STUCK", spring, cascade)

        elif phase == "TRANSITION_STUCK":
            self.ovum_hesitation = 1.0
            self.gate_open = False
            self.lad = max(self.lad, 1.0)
            self.egg_pos = 0.902 + math.sin(time.time()*7.0)*0.005
            # This is a real suspense beat, but not a deadlock. The ring wins
            # after a readable hold and the egg physically plops through.
            if t >= 1.45:
                self._set_terminal_phase("PLOP_IN", spring, cascade)

        elif phase == "PLOP_IN":
            u = ease(t/0.52)
            self.ovum_hesitation = max(0.0, 0.45*(1.0-u))
            self.lad = max(self.lad, 1.0)
            self.egg_pos = 0.905 + (0.968-0.905)*u
            if t >= 0.52:
                self._set_terminal_phase("CONCEPTION_LOCK", spring, cascade)

        elif phase == "CONCEPTION_LOCK":
            self.gate_open = True
            self.lad = max(self.lad, 1.0)
            self.ovum_hesitation = 0.14
            self.egg_pos = 0.970 + math.sin(time.time()*4.0)*0.002
            for sp in self.sperm:
                sp[0] = min(1.0, max(0.90, float(sp[0]) + dt*0.30))
            if self.terminal_seq_conceived:
                self._set_terminal_phase("CONCEPTION", spring, cascade)

        elif phase == "CONCEPTION":
            self.gate_open = True
            self.lad = max(self.lad, 1.0)
            self.ovum_hesitation = 0.0
            self.egg_pos = 0.990
            for sp in self.sperm:
                sp[0] = min(1.0, max(0.95, float(sp[0]) + dt*0.18))

    def tick(self, dt:float, m:Metrics, spring:Spring, cascade:Cascade):
        now = time.time()
        # Rate scales with excitement
        excitement = m.melt*0.4 + m.push*0.3 + m.climax_f*0.3
        self.cluster_ph  = (self.cluster_ph  + dt*(1.1 + excitement*0.8)) % (2*math.pi)
        self.tunnel_ph   = (self.tunnel_ph   + dt*(1.6 + m.push*3.5 + m.conv_tunnel*2.0)) % (2*math.pi)
        self.tube_ph     = (self.tube_ph     + dt*(0.8 + m.melt*0.8 + m.conv_tube*1.2)) % (2*math.pi)
        self.uterus_ph   = (self.uterus_ph   + dt*(0.7 + m.conv_uterus*0.9)) % (2*math.pi)
        self.gate_ph     = (self.gate_ph     + dt*(2.2 + m.conv_gate*4.0)) % (2*math.pi)
        self.iris_ph     = (self.iris_ph     + dt*(0.4 + m.conv_gate*2.0)) % (2*math.pi)
        self.follicle_ph = (self.follicle_ph + dt*(0.6 + m.melt*1.2)) % (2*math.pi)
        # Heartbeat: BPM from melt
        bpm = 65 + m.melt*65 + m.climax_f*30
        self.heart_phase = (self.heart_phase + dt * bpm/60.0 * 2*math.pi) % (2*math.pi)

        self.uterus_pulse = max(0.0, self.uterus_pulse - dt*0.9)
        self.climax_burst = max(0.0, self.climax_burst - dt*0.55)
        self.gate_flash   = max(0.0, self.gate_flash   - dt*1.8)
        self.breach_flash = max(0.0, self.breach_flash - dt*2.0)
        self.shock_flash  = max(0.0, self.shock_flash  - dt*1.2)
        self.conception_flash = max(0.0, self.conception_flash - dt*0.33)
        self.conception_glow  = max(0.0, self.conception_glow  - dt*0.07)

        self._tick_terminal_sequence(dt, m, spring, cascade)

        # ── Egg pop slapstick sequence timers ────────────────────────────
        # Small laugh wobble (pre-hit giggle)
        self.laugh_t = max(0.0, float(getattr(self, "laugh_t", 0.0)) - dt)
        if self.laugh_t > 0.0:
            # A light, silly wobble — meant to read as "hehe" not panic.
            r = min(1.0, self.laugh_t / 0.40)
            spring.jolt(math.sin(now*38.0) * 0.22 * r, math.sin(now*55.0+1.2) * 0.10 * r)

        # Thrust aftermath boost (post-pop "serious thrusts")
        self.thrust_boost_t = max(0.0, float(getattr(self, "thrust_boost_t", 0.0)) - dt)
        self.thrust_boost = 1.0 if self.thrust_boost_t > 0.0 else 0.0
        if self.thrust_boost > 0.0:
            self.thrust_pulse_cd = float(getattr(self, "thrust_pulse_cd", 0.0)) - dt
            if self.thrust_pulse_cd <= 0.0:
                # short, weighty pulses
                spring.jolt(0.55 * float(getattr(self, "pop_dir", 1)) , -2.15)
                self.thrust_pulse_cd = 0.115

        # Pop sequence: weak tap + laugh lead-in → delayed massive sideways spank + freeze
        if int(getattr(self, "pop_phase", 0)) == 1:
            self.pop_t = float(getattr(self, "pop_t", 0.0)) + dt
            if self.pop_t >= 0.23:
                self.pop_phase = 2
                self.pop_t = 0.0
                # Massive sideways spank impact
                d = int(getattr(self, "pop_dir", 1)) or 1
                try:
                    spring.x = _clamp(spring.x + d * 20.0, -20.0, 20.0)
                    spring.y = _clamp(spring.y + 10.0, -14.0, 14.0)
                    spring.vx *= 0.12; spring.vy *= 0.12
                except Exception:
                    pass
                spring.jolt(d * 16.0, -2.6)
                self.gate_flash = 1.0
                self.shock_flash = 1.0
                # Freeze + point-of-no-return hold
                if m is not None:
                    try:
                        m.freeze_t = max(float(getattr(m, "freeze_t", 0.0)), float(POP_FREEZE_SEC))
                        m.freeze_now = time.time()
                    except Exception:
                        pass
                # Kick off the post-freeze thrust burst
                self.thrust_boost_t = max(float(getattr(self, "thrust_boost_t", 0.0)), 1.60)
                self.thrust_pulse_cd = 0.03

        # Gate stays visibly LOCKED throughout the build. It opens only for the
        # one authoritative terminal reproductive event.
        self.release_cd = max(0.0, self.release_cd - dt)
        self.release_window = max(0.0, self.release_window - dt)
        self.terminal_gate_t = max(0.0, self.terminal_gate_t - dt)
        self.gate_open = self.terminal_gate_t > 0.0

        if not self.gate_open:
            if m.stage_idx >= 3 and m.inside:
                build = dt * (0.0018 + 0.0038*m.melt + 0.0030*m.power + 0.0022*m.push)
            else:
                build = dt * 0.0005
            self.gate_health = _clamp(self.gate_health + build)

        target = 1.0 if m.inside else 0.0
        rate = 6.0 if target > self.lad else 1.5
        self.lad += (target - self.lad) * dt * rate
        self.lad = _clamp(self.lad)

        if not self.terminal_seq_active:
            # 180 s choreography:
            # follicle wiggle -> release -> tube transit -> hesitation -> locked gate.
            p = _clamp(float(getattr(self, "timeline_progress", 0.0)))
            self.ovum_wiggle = _clamp(p / 0.12) if p < 0.12 else max(0.0, 1.0-(p-0.12)/0.10)
            self.ovum_bulge = _clamp((p-0.08)/0.14) if p < 0.22 else 0.0
            self.ovum_hesitation = _clamp((p-0.68)/0.22) if 0.68 <= p < 0.90 else 0.0

            if not self.egg_settled:
                if p < 0.12:
                    target_pos = 0.025 + 0.018*math.sin(time.time()*8.0)
                elif p < 0.22:
                    u=(p-0.12)/0.10
                    target_pos=0.05+0.17*(u*u*(3.0-2.0*u))
                elif p < 0.68:
                    u=(p-0.22)/0.46
                    target_pos=0.22+0.50*(u*u*(3.0-2.0*u))
                elif p < 0.90:
                    u=(p-0.68)/0.22
                    target_pos=0.72+0.15*u+math.sin(time.time()*3.4)*0.018*(1.0-u)
                elif p < 0.99:
                    u=(p-0.90)/0.09
                    target_pos=0.87+0.105*(u*u)
                else:
                    target_pos=0.975
                k=2.2+2.8*m.melt+2.0*m.push
                self.egg_pos += (target_pos-self.egg_pos)*min(1.0,dt*k)
                self.egg_pos=_clamp(self.egg_pos)

        if self.egg_settled and not self._prev_settled:
            cascade.on_egg_settled()
            spring.jolt(0.0, 2.2)
            _write_bio(m, self)
        self._prev_settled = self.egg_settled
        # Sperm are spawned only during release bursts (see on_climax); no constant stream.

        spd = 0.09 + m.push*0.22 + m.power*0.10
        new_s = []
        for sp in self.sperm:
            sp[0] += dt * spd
            sp[2] += dt * (18.0 + m.push*12.0)
            if sp[0] >= 1.0:
                if self.gate_open:
                    self.breach_flash = 1.0
                    spring.jolt((random.random()-0.5)*0.9, -1.3)
                    self.gate_flash = 1.0
                else:
                    sp[0] = 1.0  # jam at the closed gate
            if sp[0] < 1.05: new_s.append(sp)
        self.sperm = new_s

        # Particles
        self.particles = [
            (x+vx*dt, y+vy*dt, vx*0.93, vy*0.93+140*dt, life-dt, col)
            for x,y,vx,vy,life,col in self.particles if life-dt>0
        ]

    def on_climax(self, spring:Spring, cascade:Cascade, m:Metrics=None, allow_conception: bool=True):
        self.uterus_pulse = 1.0; self.climax_burst = 1.0; self.shock_flash = 1.0
        spring.jolt(0.0, -3.5)

        # ── CONCEPTION CHECK ─────────────────────────────────────────────
        # Balanced rule:
        # - Egg must be "threatening" at the gate (egg_pos high)
        # - Only pops / counts as conception on FRENZY + her climax (this method is called on her climax)
        _now = time.time()
        _stage_ok = False
        _egg_ready = (self.egg_pos >= 0.90)
        if m is not None:
            try:
                _stage_ok = (m.stage == "FRENZY")
            except Exception:
                _stage_ok = False

        _conceived = bool(allow_conception and _stage_ok and _egg_ready)

        # Release burst (infrequent, sized by gate_health) — tied to her climax.
        try:
            if self.release_cd <= 0.0:
                strength = float(getattr(self, "gate_health", 0.0))
                # Avoid frequent tiny releases; reserve bursts for when the gate has built up,
                # but always allow a burst during FRENZY.
                if (strength < 0.25) and (m is not None and getattr(m, "stage", "") != "FRENZY"):
                    strength = 0.0
                    raise RuntimeError("release skipped")
                n = int(6 + 26 * (strength ** 1.25))
                n = max(5, min(30, n))
                self.release_window = float(RELEASE_WINDOW_SEC)
                self.release_cd = float(RELEASE_COOLDOWN_SEC)
                self.gate_health = max(0.0, strength - 0.88)
                for _ in range(n):
                    self.sperm.append([0.0, random.choice([-1,0,0,1]), random.uniform(0,2*math.pi)])
        except Exception:
            pass

        if _conceived:
            self.egg_settled = True
            self.conception_count += 1
            self.conception_flash  = 3.0   # 3-second gold overlay
            self.conception_glow   = 1.0   # long warm uterus ambient glow
            cascade.on_conception(self.conception_count)
            # Egg pop beat: weak tap + giggle lead-in, then (after a short delay in tick)
            # a massive sideways spank + freeze + thrust aftermath.
            try:
                d = random.choice([-1, 1])
                self.pop_dir = d
                self.pop_phase = 1
                self.pop_t = 0.0
                self.laugh_t = max(float(getattr(self, "laugh_t", 0.0)), 0.40)
                # weak, silly tap (slapstick setup)
                spring.jolt(d * 2.2, 0.65)
                spring.jolt(0.0, -0.6)
            except Exception:
                pass
            # 48-particle burst from uterus centre (warm colours)
            for _ in range(48):
                a = random.uniform(0, 2*math.pi)
                v = random.uniform(55, 420)
                self.particles.append((
                    CX, int(H*0.39),
                    math.cos(a)*v, math.sin(a)*v,
                    random.uniform(2.0, 4.8),
                    random.choice([PARTICLE_A, EGG_WHITE, FOLLICLE, (255,240,200)])
                ))
            # Write both bio influence and a conception event for Japan
            if m is not None:
                _write_bio(m, self)
                _write_conception(self, m)
        else:
            cascade.on_climax()

        # Regular climax burst (always fires)
        for _ in range(28):
            a = random.uniform(0, 2*math.pi)
            v = random.uniform(90, 320)
            self.particles.append((
                CX, int(H*0.53), math.cos(a)*v, math.sin(a)*v,
                random.uniform(1.4, 3.2),
                random.choice([PARTICLE_A, PARTICLE_B, PARTICLE_C, EGG_WHITE])
            ))
        self.egg_pos       = 0.0
        self.egg_settled   = False
        self._prev_settled = False
        self.egg_side      = 1 - self.egg_side   # alternate L→R→L each cycle

def _write_bio(m:Metrics, anim=None):
    """Write bio_influence.json so Japan worldbox sees current egg state."""
    try:
        path = os.path.join(RUN_DIR,"bio_influence.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = {
            "egg_at_gate":       bool(anim is not None and getattr(anim, "egg_pos", 0.0) >= 0.90 and getattr(m, "stage_idx", 0.0) >= 3),
            "suggest_bird_mode": "ML",
            "melt":              round(m.melt,   3),
            "push":              round(m.push,   3),
            "climax_f":          round(m.climax_f, 3),
            "stage":             m.stage,
            "inside":            bool(m.inside),
            "t":                 time.time(),
        }
        if anim is not None:
            data["conception_count"] = anim.conception_count
            data["egg_pos"]          = round(anim.egg_pos, 3)
            data["egg_settled"]      = bool(anim.egg_settled)
        json.dump(data, open(path, "w", encoding="utf-8"))
    except: pass


def _write_conception(anim, m:Metrics):
    """Append a CONCEPTION line to telemetry.jsonl so Japan picks it up."""
    try:
        path = os.path.join(RUN_DIR, "telemetry.jsonl")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        import json as _j
        line = _j.dumps({
            "event":           "CONCEPTION",
            "count":           anim.conception_count,
            "melt":            round(m.melt,   3),
            "push":            round(m.push,   3),
            "climax_f":        round(m.climax_f, 3),
            "stage":           m.stage,
            "inside":          bool(m.inside),
            "t":               time.time(),
        })
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except: pass


# ── Drawing helpers ───────────────────────────────────────────────────────

def glow_circle(surf, col, cx, cy, r, layers=4, base_alpha=60):
    for i in range(layers, 0, -1):
        rad = r + i*6
        alpha = max(0, min(255, int(base_alpha*(1-i/(layers+1)))))
        s = pygame.Surface((rad*2+2, rad*2+2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*col[:3], alpha), (rad+1, rad+1), rad)
        surf.blit(s, (cx-rad-1, cy-rad-1))
    pygame.draw.circle(surf, col, (int(cx), int(cy)), max(1,int(r)))

def glow_circle_s(surf, col, cx, cy, r, alpha=80):
    """Single-layer soft glow."""
    s = pygame.Surface((r*4+4, r*4+4), pygame.SRCALPHA)
    pygame.draw.circle(s, (*col[:3], alpha), (r*2+2, r*2+2), r*2)
    surf.blit(s, (cx-r*2-2, cy-r*2-2))

def draw_curve(surf, pts, col, w=4, glow=True, glow_alpha=55):
    if len(pts) < 2: return
    if glow:
        gs = pygame.Surface((surf.get_width(), surf.get_height()), pygame.SRCALPHA)
        try:
            pygame.draw.lines(gs, (*col[:3], glow_alpha), False, pts, w+10)
            surf.blit(gs, (0,0))
        except: pass
    try:
        pygame.draw.lines(surf, col, False, pts, w)
    except: pass

def alpha_rect(surf, col, rect, alpha, radius=0):
    """Draw a rectangle with per-rect alpha. Clamps RGBA to avoid pygame ValueError."""
    # pygame expects 0..255 ints for RGBA
    try:
        a = int(alpha)
    except Exception:
        a = 0
    if a < 0: a = 0
    elif a > 255: a = 255

    r, g, b = (col[0], col[1], col[2]) if len(col) >= 3 else (0, 0, 0)
    r = 0 if r < 0 else 255 if r > 255 else int(r)
    g = 0 if g < 0 else 255 if g > 255 else int(g)
    b = 0 if b < 0 else 255 if b > 255 else int(b)

    x, y, w, h = rect
    x = int(x); y = int(y)
    w = max(1, int(w)); h = max(1, int(h))

    s = pygame.Surface((w, h), pygame.SRCALPHA)
    if radius:
        pygame.draw.rect(s, (r, g, b, a), (0, 0, w, h), border_radius=int(radius))
    else:
        s.fill((r, g, b, a))
    surf.blit(s, (x, y))

def draw_bar_fancy(surf, font, x, y, w, h, value, col, label, threshold=0.7):
    """Animated bar with threshold flash."""
    # Background
    pygame.draw.rect(surf, HUD_BG, (x,y,w,h), border_radius=5)
    # Fill with gradient-style layering
    fill = max(2, int(w*_clamp(value)))
    # Base fill
    pygame.draw.rect(surf, col, (x,y,fill,h), border_radius=5)
    # Highlight stripe (top 1/3)
    hl_h = max(1, h//3)
    hl_alpha = 80
    s = pygame.Surface((fill, hl_h), pygame.SRCALPHA)
    s.fill((*WHITE, hl_alpha))
    surf.blit(s, (x,y))
    # Threshold line
    tx = x + int(w*threshold)
    pygame.draw.line(surf, (*WHITE,80), (tx,y), (tx,y+h), 1)
    # Convulsion flash at high values
    if value > threshold:
        flash = (math.sin(time.time()*15) + 1)*0.5
        edge_alpha = int(80 + flash*120)
        pygame.draw.rect(surf, (*CONVULSE_FX, edge_alpha), (x,y,fill,h), 2, border_radius=5)
    else:
        pygame.draw.rect(surf, (*col[:3],100), (x,y,w,h), 1, border_radius=5)
    # Label
    lbl = font.render(label, True, DIM)
    surf.blit(lbl, (x, y-lbl.get_height()-2))


# ── Egg face renderer ─────────────────────────────────────────────────────

def draw_egg(surf, x, y, r, state="uwu", now=0.0, conv=0.0):
    x, y = int(x), int(y)
    # Wobble from convulsion
    if conv > 0.1:
        x += int(math.sin(now*28+1.0)*conv*4)
        y += int(math.cos(now*22+0.5)*conv*3)
    # Layered glow
    glow_circle_s(surf, EGG_GLOW, x, y, r+8, alpha=40)
    glow_circle(surf, EGG_GLOW, x, y, r, layers=2, base_alpha=60)
    # Body with subtle gradient
    pygame.draw.circle(surf, EGG_WHITE, (x,y), r)
    # Specular highlight
    hl_r = max(2, r//3)
    pygame.draw.circle(surf, (*WHITE,120), (x-r//4, y-r//4), hl_r, 0)
    pygame.draw.circle(surf, EGG_GLOW, (x,y), r, 2)

    fr = max(1, r//6)
    ey_y = y - fr
    ey_sep = fr*2

    if state == "uwu":
        for ex in (x-ey_sep, x+ey_sep):
            rect = pygame.Rect(ex-fr, ey_y-fr, fr*2, fr*2)
            pygame.draw.arc(surf, EGG_FACE, rect, 0, math.pi, max(1,fr//2))
        my = y + fr
        pts = [(x-fr,my),(x-fr//2,my+fr//2),(x,my),(x+fr//2,my+fr//2),(x+fr,my)]
        if len(pts)>=2: pygame.draw.lines(surf, EGG_FACE, False, pts, max(1,fr//2))

    elif state == "eager":
        for ex in (x-ey_sep, x+ey_sep):
            pygame.draw.line(surf,EGG_FACE,(ex-fr,ey_y-fr//2),(ex+fr,ey_y+fr//2),max(1,fr//2))
            pygame.draw.line(surf,EGG_FACE,(ex+fr,ey_y-fr//2),(ex-fr,ey_y+fr//2),max(1,fr//2))
        my = y + fr
        pygame.draw.arc(surf,EGG_FACE,pygame.Rect(x-fr,my-fr//2,fr*2,fr),math.pi,2*math.pi,max(1,fr//2))

    elif state == "gate":
        for ex in (x-ey_sep, x+ey_sep):
            pygame.draw.circle(surf,EGG_FACE,(ex,ey_y),fr,max(1,fr//2))
            pygame.draw.circle(surf,EGG_FACE,(ex,ey_y),fr//2)
        pygame.draw.circle(surf,EGG_FACE,(x,y+fr),fr//2,max(1,fr//3))

    elif state == "shock":
        for ex in (x-ey_sep, x+ey_sep):
            pygame.draw.line(surf,EGG_FACE,(ex-fr,ey_y),(ex+fr,ey_y),max(1,fr//2))
        pygame.draw.circle(surf,EGG_FACE,(x,y+fr),fr//2,max(1,fr//3))
        # Sweat drop (stress detail)
        sw_x, sw_y = x+r-2, y-r+4
        pygame.draw.circle(surf, TUBE_GLOW, (sw_x,sw_y), max(2,fr//3))

    elif state == "done":
        for ex in (x-ey_sep, x+ey_sep):
            rect = pygame.Rect(ex-fr, ey_y-fr, fr*2, fr*2)
            pygame.draw.arc(surf,EGG_FACE,rect,0,math.pi,max(1,fr//2))
        my = y + fr
        pygame.draw.arc(surf,EGG_FACE,pygame.Rect(x-fr,my-fr,fr*2,fr),math.pi,2*math.pi,max(1,fr//2))
        # Rosy cheeks
        for ex in (x-ey_sep, x+ey_sep):
            glow_circle_s(surf, (255,120,140), ex, ey_y+fr, fr//2, alpha=60)

    else:  # sleep
        for ex in (x-ey_sep, x+ey_sep):
            pygame.draw.line(surf,EGG_FACE,(ex-fr,ey_y),(ex+fr,ey_y),max(1,fr//2))
        pygame.draw.line(surf,EGG_FACE,(x-fr//2,y+fr),(x+fr//2,y+fr),max(1,fr//2))
        # ZZZ
        if fr > 3:
            zs = pygame.font.SysFont("Consolas",fr).render("z",True,(*EGG_FACE,120))
            surf.blit(zs,(x+r-2,y-r))


def _egg_state(anim:Anatomy, m:Metrics) -> str:
    ep = anim.egg_pos
    if ep < 0.05:  return "sleep"
    if ep < 0.55:  return "eager"
    if ep >= 0.95: return "done" if anim.gate_open else "shock"
    if ep >= 0.7:  return "gate"
    return "uwu"


# ── Scan-line + vignette overlays ─────────────────────────────────────────

def draw_scanlines(surf, alpha=18):
    """Fast scan-line overlay — every other row darkened."""
    sw = surf.get_width()
    s = pygame.Surface((sw, 2), pygame.SRCALPHA)
    s.fill((*SCAN_LINE, alpha))
    for y in range(0, surf.get_height(), 3):
        surf.blit(s, (0, y))

def draw_vignette(surf):
    """Dark radial vignette centered on anatomy panel."""
    cx, cy = CX, H//2
    for r in range(380, 0, -40):
        alpha = int(50 * (1 - r/380))
        s = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (0,0,0,alpha), (0,0,r*2,r*2))
        surf.blit(s, (cx-r, cy-r), special_flags=0)

def draw_panel_border(surf, x, y, w, h, col, title="", font=None):
    """Anime-medical readout panel border with corner accents."""
    # Main border
    pygame.draw.rect(surf, col, (x,y,w,h), 1, border_radius=6)
    # Corner accents (L-shaped)
    corner_len = 14
    for cx_,cy_,dx,dy in [(x,y,1,1),(x+w-1,y,-1,1),(x,y+h-1,1,-1),(x+w-1,y+h-1,-1,-1)]:
        pygame.draw.line(surf, (*col[:3],180), (cx_,cy_), (cx_+dx*corner_len,cy_), 2)
        pygame.draw.line(surf, (*col[:3],180), (cx_,cy_), (cx_,cy_+dy*corner_len), 2)
    # Title tag
    if title and font:
        lbl = font.render(f" {title} ", True, BG)
        tag_w = lbl.get_width() + 4
        pygame.draw.rect(surf, col, (x+12, y-lbl.get_height()//2, tag_w, lbl.get_height()), border_radius=2)
        surf.blit(lbl, (x+14, y-lbl.get_height()//2))


# ── Main render ───────────────────────────────────────────────────────────

# ── Anatomy render helpers ────────────────────────────────────────────────

def draw_flesh_bg(surf, now, melt, heart_pulse, l_pnl=None, r_pnl=None):
    """Warm radial gradient — lit-from-within body interior for center pane."""
    if l_pnl is None: l_pnl = L_PANEL
    if r_pnl is None: r_pnl = R_PANEL
    # Solid deep base
    pygame.draw.rect(surf, FLESH_DEEP, (l_pnl, 0, r_pnl-l_pnl, H))
    # Build up warm layers from center outward using concentric ellipses
    cy = H * 0.47
    aw_   = r_pnl - l_pnl
    cx_bg = (l_pnl + r_pnl) // 2
    sc_   = aw_ / 630.0
    layers = [
        (int(280*sc_), int(200*sc_), FLESH_GLOW,   int(18 + 14*heart_pulse*melt)),
        (int(220*sc_), int(165*sc_), FLESH_BRIGHT, int(30 + 18*melt)),
        (int(320*sc_), int(240*sc_), FLESH_WARM,   int(45 + 20*melt)),
        (int(420*sc_), int(310*sc_), FLESH_MID,    int(55)),
        (int(560*sc_), int(420*sc_), FLESH_COOL,   int(60)),
    ]
    for rw, rh, col, alpha in layers:
        if alpha < 2 or rw < 2 or rh < 2: continue
        s = pygame.Surface((rw*2, rh*2), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (*col[:3], alpha), (0, 0, rw*2, rh*2))
        surf.blit(s, (int(cx_bg - rw), int(cy - rh)))
    for y in range(0, H, 4):
        fade = int(12 * (1.0 - y/H) * (0.4 + 0.6*melt))
        if fade > 0:
            s = pygame.Surface((aw_, 4), pygame.SRCALPHA)
            s.fill((*FLESH_WARM[:3], fade))
            surf.blit(s, (l_pnl, y))
    # Slow breathing pulse from melt
    if melt > 0.15:
        pr = int(160 * melt + 40 * heart_pulse)
        if pr > 8:
            ps = pygame.Surface((pr*2, pr*2), pygame.SRCALPHA)
            pygame.draw.ellipse(ps, (*FLESH_GLOW, int(28 * melt * (0.5 + heart_pulse))),
                                (0, 0, pr*2, pr*2))
            surf.blit(ps, (int(CX-pr), int(cy-pr)))


def draw_fimbriae(surf, tip_x, tip_y, angle_base, conv=0.0, n=10, now=0.0):
    """Finger-like fimbriae projections at the infundibular end of each tube."""
    spread = math.pi * 0.65
    base_len = 26
    for i in range(n):
        t = i / (n-1) if n > 1 else 0.5
        a = angle_base - spread/2 + spread*t
        # Slight organic curl varies per finger
        curl = math.sin(now*1.8 + i*0.9) * (0.15 + conv*0.2)
        l = base_len + math.sin(now*2.1 + i*1.3)*3
        # Two-segment finger (base + tip)
        mid_x = tip_x + int(math.cos(a) * l*0.5)
        mid_y = tip_y + int(math.sin(a) * l*0.5)
        end_x = tip_x + int(math.cos(a + curl) * l)
        end_y = tip_y + int(math.sin(a + curl) * l)
        # Draw gradient from base to tip (3 widths)
        pygame.draw.line(surf, FIMB, (tip_x, tip_y), (mid_x, mid_y), 3)
        pygame.draw.line(surf, (*FLESH_BRIGHT, 200), (mid_x, mid_y), (end_x, end_y), 2)
        # Rounded ciliated tip
        s = pygame.Surface((10,10), pygame.SRCALPHA)
        pygame.draw.circle(s, (*FLESH_BRIGHT, 180), (5,5), 4)
        surf.blit(s, (end_x-5, end_y-5))


def draw_uterus_body(surf, ux, uy, UTW, UTH, metrics, anim, now):
    """Layered anatomical uterus: serosa → myometrium → endometrium → cavity."""
    heart_pulse = max(0, math.sin(anim.heart_phase)) * 0.5
    cr = UTH // 3

    # ── 1. SEROSA — peritoneal covering (outermost, darkest) ──────────────
    sw, sh = UTW + 22, UTH + 14
    alpha_rect(surf, SEROSA, (ux-sw//2, uy-sh//2, sw, sh), 255, radius=sh//3)

    # Cornual extensions (tube attachment zones — wider at fundus)
    for side in (-1, 1):
        hx = ux + side*(UTW//2 - 8)
        hy = uy - UTH//5
        alpha_rect(surf, SEROSA, (hx-28, hy-18, 56, 38), 230, radius=16)

    # ── 2. MYOMETRIUM — thick outer muscle ────────────────────────────────
    mw, mh = UTW + 6, UTH + 4
    alpha_rect(surf, MYO, (ux-mw//2, uy-mh//2, mw, mh), 255, radius=mh//3)

    # Mid-myometrium (lighter ring within dark outer)
    mmw, mmh = int(UTW*0.88), int(UTH*0.90)
    alpha_rect(surf, MYO_MID, (ux-mmw//2, uy-mmh//2, mmw, mmh), 255, radius=mmh//3)

    # Cornua on myometrium
    for side in (-1, 1):
        hx = ux + side*(UTW//2 - 12)
        hy = uy - UTH//5
        alpha_rect(surf, MYO_MID, (hx-20, hy-12, 40, 26), 255, radius=12)

    # ── 3. ENDOMETRIUM — warm inner lining ────────────────────────────────
    ew, eh = int(UTW*0.66), int(UTH*0.70)
    ec = metrics.conv_uterus
    if ec > 0.5:
        t = (ec - 0.5) / 0.5
        endo_col = (int(ENDO[0]*(1-t)+ENDO_HOT[0]*t),
                    int(ENDO[1]*(1-t)+ENDO_HOT[1]*t),
                    int(ENDO[2]*(1-t)+ENDO_HOT[2]*t))
    else:
        endo_col = ENDO
    alpha_rect(surf, endo_col, (ux-ew//2, uy-eh//2, ew, eh), 255, radius=eh//3+4)

    # ── 4. CAVITY — bright uterine cavity ────────────────────────────────
    cw, ch = int(UTW*0.36), int(UTH*0.50)
    cav_alpha = min(255, int(180 + 60*metrics.melt + 55*anim.uterus_pulse + 45*heart_pulse))
    alpha_rect(surf, CAVITY, (ux-cw//2, uy-ch//2, cw, ch), cav_alpha, radius=ch//3+6)

    # ── 5. Subsurface internal glow (scattering warmth) ──────────────────
    glow_r = int(UTW*0.20 + 18*heart_pulse*max(0.1, metrics.melt))
    if glow_r > 5:
        glow_circle_s(surf, FLESH_GLOW, ux, uy, glow_r,
                      alpha=int(50 + 40*heart_pulse + 30*metrics.melt))

    # ── 6. Heartbeat ring ─────────────────────────────────────────────────
    if heart_pulse > 0.28 and metrics.melt > 0.08:
        ra = int(heart_pulse * 88 * metrics.melt)
        alpha_rect(surf, FLESH_BRIGHT, (ux-UTW//2-8,uy-UTH//2-8,UTW+16,UTH+16),
                   ra, radius=UTH//2+8)

    # ── 7. Climax / conception flash ring ────────────────────────────────
    if anim.uterus_pulse > 0.1:
        alpha_rect(surf, WHITE, (ux-UTW//2-14,uy-UTH//2-14,UTW+28,UTH+28),
                   int(anim.uterus_pulse*115), radius=UTH//2+14)

    if metrics.inside:
        glow_circle(surf, FLESH_GLOW, ux, uy, 26, layers=3, base_alpha=80)


def draw_ovary_organ(surf, cx_a, cy_a, active, conv_c, anim, metrics, now):
    """Anatomically-inspired ovary: stroma + cortex + follicle ring + dominant follicle."""
    # Almond/oval shape — wider than tall
    ow = int(74 + math.sin(anim.cluster_ph)*6 + conv_c*math.sin(now*16)*5)
    oh = int(50 + math.sin(anim.cluster_ph*1.3)*4 + conv_c*math.cos(now*13)*3)
    ow = max(40, ow); oh = max(28, oh)

    # Stroma (outer body — warm pink-beige)
    alpha_rect(surf, STROMA, (cx_a-ow//2, cy_a-oh//2, ow, oh), 255, radius=oh//2)

    # Cortex (inner bright zone)
    cw_, ch_ = int(ow*0.76), int(oh*0.76)
    alpha_rect(surf, CORTEX, (cx_a-cw_//2, cy_a-ch_//2, cw_, ch_), 220, radius=ch_//2)

    # Medulla specular (central bright spot — vasculature)
    pygame.draw.ellipse(surf, (*FLESH_WARM, 140),
                        (cx_a-ow//6, cy_a-oh//6, ow//3, oh//3))

    # Ring of small follicles (Graafian-in-waiting)
    n_small = 7
    for i in range(n_small):
        a = i * (2*math.pi/n_small) + anim.follicle_ph*0.18 + (0.3 if active else 0)
        slosh = math.sin(anim.follicle_ph*1.3 + i*1.2) * 1.8
        fx = cx_a + int(math.cos(a) * ow*0.29)
        fy = cy_a + int(math.sin(a) * oh*0.26 + slosh)
        fr = int(7 + math.sin(anim.cluster_ph*2.2+i)*2.5)
        pygame.draw.circle(surf, FOLLICLE_WALL, (fx,fy), fr)
        pygame.draw.circle(surf, FOLLICLE_FLUID_COL, (fx,fy), max(2, fr-2))
        # Specular catch — makes fluid look translucent
        pygame.draw.circle(surf, (*WHITE,130), (fx-fr//3, fy-fr//3), max(1,fr//4))

    # Dominant Graafian follicle on active ovary
    if active:
        dom_ang = anim.follicle_ph * 0.1
        dfx = cx_a + int(math.cos(dom_ang) * ow*0.26)
        dfy = cy_a + int(math.sin(dom_ang) * oh*0.20)
        dfr = int(17 + math.sin(anim.follicle_ph*1.8)*3 + conv_c*4 + 6.0*float(getattr(anim,"ovum_bulge",0.0) or 0.0))
        dfr = max(10, dfr)
        # Outer wall (thicker, prominent)
        pygame.draw.circle(surf, FOLLICLE_WALL, (dfx,dfy), dfr)
        # Fluid (pale, translucent)
        pygame.draw.circle(surf, FOLLICLE_FLUID_COL, (dfx,dfy), max(3,dfr-2))
        # Cumulus oophorus — egg nest (small bright cluster)
        pygame.draw.circle(surf, EGG_WHITE, (dfx+3, dfy+4), 5)
        pygame.draw.circle(surf, (*FLESH_GLOW,160), (dfx+3, dfy+4), 3)
        # Specular
        pygame.draw.circle(surf, (*WHITE,165), (dfx-dfr//3, dfy-dfr//3), max(2,dfr//4))

        # Corpus luteum (post-ovulation, scales with melt)
        if metrics.melt > 0.22:
            clx = cx_a - int(math.cos(dom_ang)*ow*0.20) 
            cly = cy_a + int(math.sin(dom_ang + 1.0)*oh*0.18)
            cl_r = int(10 + metrics.melt*7)
            s = pygame.Surface((cl_r*2+4, cl_r*2+4), pygame.SRCALPHA)
            pygame.draw.circle(s, (*CORPUS_LUT, int(180*metrics.melt)), (cl_r+2,cl_r+2), cl_r)
            pygame.draw.circle(s, (*CORPUS_LUT, int(80*metrics.melt)), (cl_r+2,cl_r+2), cl_r+2, 0)
            surf.blit(s, (clx-cl_r-2, cly-cl_r-2))
            pygame.draw.circle(surf, (*WHITE,80), (clx-cl_r//3, cly-cl_r//3), max(1,cl_r//4))

    # Hilar vessels line (attachment point)
    for side in (-1, 1):
        pygame.draw.line(surf, (*MYO,110),
                         (cx_a+side*ow//2, cy_a),
                         (cx_a+side*(ow//2+8), cy_a), 2)


def draw_rugae(surf, cx_, y_start, y_end, wall_x_fn, side, n_folds, phase):
    """Draw horizontal rugae folds on one vaginal wall."""
    spacing = (y_end - y_start) / (n_folds + 1)
    for i in range(n_folds):
        fy = int(y_start + spacing*(i+1))
        wall_x = wall_x_fn(fy)
        fold_depth = int(8 + math.sin(phase + i*0.8)*3)
        # Shadow arc (inward fold)
        pw = fold_depth*2 + 10
        ph = 10
        inward = side * fold_depth
        rect = pygame.Rect(cx_ + inward - pw//2, fy - ph//2, pw, ph)
        s = pygame.Surface((pw+4, ph+4), pygame.SRCALPHA)
        try:
            pygame.draw.arc(s, (*RUGAE_DARK, 160), (2,2,pw,ph), 0, math.pi, 2)
        except: pass
        surf.blit(s, (rect.x-2, rect.y-2))
        # Highlight ridge
        s2 = pygame.Surface((pw+4, ph+4), pygame.SRCALPHA)
        try:
            pygame.draw.arc(s2, (*RUGAE_LIGHT, 90), (2,4,pw,ph-2), 0, math.pi, 1)
        except: pass
        surf.blit(s2, (rect.x-2, rect.y))


# ── Magnum Opus authored Brat-Taming Cathedral script ────────────────────────
# Three lines for each director phase (66 total). These are staging/biometric
# narration, not outcome authority; BRAT_STATE remains authoritative.
_BRAT_CATHEDRAL_LINES = {
    "KISS_CAPTURE": [
        "capture beat: contact closes the distance before the struggle starts.",
        "the opening snaps shut around a playful challenge.",
        "first rule established: caught, smiling, still testing the hold.",
    ],
    "SIDE_CATCH": [
        "side posture acquired; balance shifts toward the captor.",
        "one hip becomes the fulcrum; the rest of the body follows late.",
        "soft tissue lags behind the turn, then catches up in a wobble.",
    ],
    "HIP_PRESS_STRUGGLE": [
        "hip pressure rises; resistance stays performative and springy.",
        "the hold compresses, recoils, and is tested again.",
        "brat loop active: push away, rebound, get caught again.",
    ],
    "COMMIT": [
        "commit point reached; the contest changes from escape to rhythm.",
        "the body stops bargaining with the pose and settles into it.",
        "capture complete. resistance falls away without losing attitude.",
    ],
    "PRAISE": [
        "approval lands immediately; tension converts into momentum.",
        "short praise, no pause: the rhythm begins on the same beat.",
        "reward signal accepted; cooperative timing comes online.",
    ],
    "COOPERATIVE_RHYTHM": [
        "two rhythms begin to agree instead of colliding.",
        "compression and recoil now arrive on the same count.",
        "cooperation is visible in the timing before it is visible anywhere else.",
    ],
    "EXPLORATION_LOOP": [
        "long middle passage: test, ease off, return, learn the response.",
        "pressure rises in small experiments rather than one continuous climb.",
        "the system explores its range and remembers what produced the strongest recoil.",
    ],
    "HIP_PRAISE": [
        "hip line praised; impact-release condition is now armed.",
        "the director lingers on the hips as if noticing a useful mechanical advantage.",
        "attention shifts downward: the next sharp impact can change the ovum state.",
    ],
    "IMPACT_OVUM_RELEASE": [
        "impact cue: follicle cluster deforms, rebounds, and starts to let go.",
        "the ovum wobbles against its cradle; one clean impact will free it.",
        "release mechanic waiting: impact, recoil, then a distinct pop into the tube.",
    ],
    "TIGHTEN": [
        "the hold tightens; elastic slack disappears from the outer pose.",
        "less wandering now. pressure concentrates instead of spreading.",
        "soft recoil shortens; every return lands closer to center.",
    ],
    "ARM_PULL": [
        "upper-body leverage joins the hip hold and changes the whole silhouette.",
        "arm leverage draws the frame long, then lets it snap back into compression.",
        "the director adds one more point of control without speeding up yet.",
    ],
    "FULL_BODY_CONTACT": [
        "full-body contact closes the remaining elastic gap.",
        "each pulse now reaches the whole silhouette instead of one isolated region.",
        "contact is complete; the next changes happen internally and in the rhythm.",
    ],
    "PRESSURE_BUILD": [
        "upstream pressure begins accumulating behind a gate that is still locked.",
        "production rises, but forward passage remains unavailable.",
        "the reservoir grows more insistent while the gate refuses to cooperate.",
    ],
    "LOCKED_GATE_SCARE": [
        "[LOCKED] remains literal: pressure can arrive here and still be denied.",
        "near-release scare: everything reaches the threshold, then stops short.",
        "the gate takes the load, flexes, and holds. nothing has committed yet.",
    ],
    "OVUM_DROP": [
        "the ovum finally leaves the tube and drops toward the chamber.",
        "arrival is separate from access: ovum present, gate still locked.",
        "the chamber receives the ovum while the terminal pathway remains unresolved.",
    ],
    "POSE_BLOCK": [
        "motion is deliberately stopped; the terminal actuator settles against the gate.",
        "stillness creates the block: forward pressure has nowhere clean to go.",
        "the squat hold becomes a plug state. do not confuse pressure with passage.",
    ],
    "SEAL_ESTABLISHED": [
        "seal established. forward route is occluded by the held alignment.",
        "the system is motionless at the gate; the block strengthens with every quiet beat.",
        "a stable seal forms only because the driving rhythm has stopped.",
    ],
    "LATERAL_DIVERSION": [
        "blocked pressure diverts sideways through the canal and drains downward.",
        "forward flow stalls; lateral spill becomes the visible safety valve.",
        "the seal holds while diverted fluid tracks around it and falls away.",
    ],
    "MOVEMENT_GAMBIT": [
        "the dangerous choice is movement: stillness preserves the block.",
        "one renewed drive can break the seal and realign the terminal path.",
        "movement risk climbs; the next committed motion decides whether the block survives.",
    ],
    "GATE_OPEN": [
        "seal breaks. the gate unlocks on the resumed rhythm, not during the charge-up.",
        "forward pathway opens; active pumping resumes and now crosses the threshold.",
        "the terminal route is finally aligned: pressure converts into forward flow.",
    ],
    "PROLONGED_TERMINAL_HOLD": [
        "terminal squat locked. escalation stops; the system resolves in place.",
        "hold the pose: sustained filling replaces frantic escalation.",
        "the payoff is duration now — a long, steady terminal state with no new trick.",
    ],
    "RELEASE": [
        "release phase: pressure falls, proportions normalize, control returns.",
        "the hold opens and the system drains back toward baseline.",
        "director complete. no extra beat after release.",
    ],
}

_BRAT_PHASE_COLORS = {
    "KISS_CAPTURE": CASCADE_BIRD, "SIDE_CATCH": CASCADE_TUBE,
    "HIP_PRESS_STRUGGLE": CASCADE_TUBE, "COMMIT": CASCADE_UTERUS,
    "PRAISE": CASCADE_BIRD, "COOPERATIVE_RHYTHM": CASCADE_BIRD,
    "EXPLORATION_LOOP": CASCADE_TUBE, "HIP_PRAISE": CASCADE_EGG,
    "IMPACT_OVUM_RELEASE": CASCADE_EGG, "TIGHTEN": CASCADE_UTERUS,
    "ARM_PULL": CASCADE_TUBE, "FULL_BODY_CONTACT": CASCADE_UTERUS,
    "PRESSURE_BUILD": CASCADE_ENTRANCE, "LOCKED_GATE_SCARE": GATE_LOCK,
    "OVUM_DROP": CASCADE_EGG, "POSE_BLOCK": GATE_LOCK,
    "SEAL_ESTABLISHED": GATE_LOCK, "LATERAL_DIVERSION": CASCADE_TUBE,
    "MOVEMENT_GAMBIT": WARN_COL, "GATE_OPEN": CASCADE_ENTRANCE,
    "PROLONGED_TERMINAL_HOLD": CASCADE_UTERUS, "RELEASE": DIM,
}

def _push_brat_phase_script(cascade, phase, visit_index=0):
    lines = _BRAT_CATHEDRAL_LINES.get(str(phase), ())
    if not lines:
        return
    # Rotate line selection on repeated visits; each phase always has three
    # authored alternatives.
    line = lines[int(visit_index) % len(lines)]
    cascade.push("DIRECTOR", f"{phase}: {line}", _BRAT_PHASE_COLORS.get(phase, DIM), ttl=11.0)


def _launch_verified_conception_screen():
    """Hard handoff into the existing pregnancy/conception Cathedral variant."""
    target=Path(__file__).resolve().parent/"biometric_cathedral_pregnancy.py"
    if not target.exists():
        return False
    env=os.environ.copy()
    env["LOCKKEY_PREGNANCY_DEMO"]="1"
    env.setdefault("LOCKKEY_PREGNANCY_LOOP_SEC","100")
    env["LOCKKEY_RUN_DIR"]=str(RUN_DIR)
    env["LOCKKEY_TELEMETRY"]=str(TELE)
    try:
        flags=getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0) if os.name=="nt" else 0
        subprocess.Popen([sys.executable,str(target)],cwd=str(target.parent),env=env,creationflags=flags)
        return True
    except Exception as exc:
        try:
            (Path(RUN_DIR)/"conception_handoff_error.log").write_text(repr(exc),encoding="utf-8")
        except Exception:
            pass
        return False

def main():
    # Position window RIGHT half of screen, vertically centred — before init
    _bx = int(os.environ.get("LOCKKEY_BIO_X", str(_SW - W)))
    _by = int(os.environ.get("LOCKKEY_BIO_Y", str(max(0, (_SH - _TASKBAR_H - H)//2))))
    os.environ["SDL_VIDEO_WINDOW_POS"] = f"{_bx},{_by}"

    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("BIOMETRICS // LIVING CATHEDRAL")
    clock = pygame.time.Clock()

    def _fs(pt): return max(9, int(pt * _SC))
    font_sm  = pygame.font.SysFont("Consolas", _fs(15))
    font_md  = pygame.font.SysFont("Consolas", _fs(20))
    font_lg  = pygame.font.SysFont("Consolas", _fs(28), bold=True)
    font_xl  = pygame.font.SysFont("Consolas", _fs(36), bold=True)
    font_cas = pygame.font.SysFont("Consolas", _fs(16))
    font_lbl = pygame.font.SysFont("Consolas", _fs(13))

    tele       = TelemetryReader(TELE)
    metrics    = Metrics()
    anim       = Anatomy()
    spring     = Spring()
    cascade    = Cascade()
    ecg        = ECG(length=300)
    prev_combo = 0
    prev_climax_flag = False
    prev_inside = False
    last_climax_edge = 0.0
    last_ogre_climax_edge = 0.0
    climax_seen= 0.0
    wrong_route_latched = False
    terminal_reproductive_fired = False
    terminal_reproductive_pending = False
    terminal_reproductive_pending_since = 0.0
    session_started_at = time.time()
    brat_phase = "KISS_CAPTURE"
    brat_phase_progress = 0.0
    brat_pose_block = False
    brat_seal_established = False
    brat_lateral_diversion = 0.0
    brat_movement_risk = 0.0
    brat_terminal_committed = False
    impact_release_seen = False
    brat_last_phase = ""
    brat_dialogue_line = ""
    brat_dialogue_until = 0.0
    brat_phase_visits = {}
    reproductive_terminal_stage = "IDLE"   # IDLE -> BLOCKED -> OPEN -> HOLD

    running = True
    while running:
        dt  = min(clock.tick(FPS)/1000.0, 0.05)
        now_real = time.time()
        # During a freeze, lock 'now' so pulses + motion truly hold still visually.
        if getattr(metrics, "freeze_t", 0.0) > 0.0 and getattr(metrics, "freeze_now", 0.0) > 0.0:
            now = float(metrics.freeze_now)
        else:
            now = now_real
        for e in pygame.event.get():
            if e.type == pygame.QUIT: running=False
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_q, pygame.K_ESCAPE): running=False
                if e.key == pygame.K_c and not wrong_route_latched:
                    anim.on_climax(spring, cascade, metrics, allow_conception=False)

        for ev in tele.poll():
            etype = ev.get("event")

            if etype == "SESSION_START":
                session_started_at = now_real
                anim.timeline_progress = 0.0
                anim.terminal_conception_consumed = False
                anim.terminal_seq_active = False
                anim.terminal_seq_phase = "IDLE"
                anim.terminal_seq_launch_pending = False

            if etype == "BRAT_STATE":
                brat_phase = str(ev.get("phase","") or "")
                brat_phase_progress = float(ev.get("phase_progress",0.0) or 0.0)
                brat_pose_block = bool(ev.get("pose_block",False))
                brat_seal_established = bool(ev.get("seal_established",False))
                brat_lateral_diversion = float(ev.get("lateral_diversion",0.0) or 0.0)
                brat_movement_risk = float(ev.get("movement_risk",0.0) or 0.0)
                brat_terminal_committed = bool(ev.get("terminal_committed",False))

                if brat_phase and brat_phase != brat_last_phase:
                    visits = int(brat_phase_visits.get(brat_phase, 0))
                    _push_brat_phase_script(cascade, brat_phase, visits)
                    _lines=_BRAT_CATHEDRAL_LINES.get(brat_phase,())
                    brat_dialogue_line=(
                        _lines[visits % len(_lines)]
                        if _lines else brat_phase.replace("_"," ").title()
                    )
                    brat_dialogue_until=now_real+12.0
                    brat_phase_visits[brat_phase] = visits + 1
                    brat_last_phase = brat_phase

                if brat_phase == "PROLONGED_TERMINAL_HOLD":
                    reproductive_terminal_stage = "HOLD"
                elif brat_phase in ("LATERAL_DIVERSION", "POSE_BLOCK", "KISS_CAPTURE") and terminal_reproductive_pending:
                    reproductive_terminal_stage = "BLOCKED"
                elif brat_phase == "GATE_OPEN" and terminal_reproductive_pending:
                    reproductive_terminal_stage = "OPEN"

                if bool(ev.get("ovum_released",False)) and not impact_release_seen:
                    impact_release_seen = True
                    # Early impacts deform the follicle but do NOT release the
                    # egg. The actual tube crossing is reserved for the
                    # REPRODUCTIVE_CLIMAX threshold.
                    anim.egg_pos = max(anim.egg_pos, 0.045)
                    anim.ovum_bulge = max(anim.ovum_bulge, 1.0)
                    cascade.push("OVUM", "impact squashes the follicle; Egg rebounds inside and stays contained.", CASCADE_EGG, ttl=7.0)
                continue

            if etype == "PANDORA":
                wrong_route_latched = True
                terminal_reproductive_pending = False
                terminal_reproductive_fired = True
                reproductive_terminal_stage = "IDLE"
                metrics._sig_inside = False
                metrics.inside = False
                metrics._sig_climax = False
                metrics.climax_f = 0.0
                anim.gate_open = False
                anim.terminal_gate_t = 0.0
                anim.sperm.clear()
                anim.terminal_seq_active = False
                anim.terminal_seq_phase = "IDLE"
                anim.terminal_seq_launch_pending = False
                cascade.push("SYSTEM", "PANDORA — immediate release and de-escalation.", CASCADE_UTERUS, ttl=12.0)
                continue

            if etype == "WRONG_ROUTE_CLIMAX":
                wrong_route_latched = True
                terminal_reproductive_pending = False
                reproductive_terminal_stage = "IDLE"
                metrics._sig_inside = False
                metrics.inside = False
                metrics._sig_climax = False
                metrics._sig_climax_prev = False
                metrics.climax_f = 0.0
                metrics._climax_hold = 0.0
                anim.lad = 0.0
                anim.sperm.clear()
                anim.release_window = 0.0
                anim.release_cd = max(anim.release_cd, 2.0)
                anim.gate_open = False
                anim.egg_pos = 0.0
                anim.egg_settled = False
                anim.terminal_seq_active = False
                anim.terminal_seq_phase = "IDLE"
                anim.terminal_seq_launch_pending = False
                prev_inside = False
                prev_climax_flag = False
                cascade.push("UTERUS", "alternate route locked. reproductive sequence cancelled.", CASCADE_UTERUS, ttl=8.0)
                continue

            if etype == "REPRODUCTIVE_COMMIT":
                reproductive_terminal_stage="OPEN"
                brat_pose_block=False
                brat_seal_established=False
                brat_lateral_diversion=0.0
                anim.note_reproductive_commit()
                brat_dialogue_line="Pressure rises, but the ovum is still fighting inside the follicle."
                brat_dialogue_until=now_real+12.0
                cascade.push("OVUM","near-breach pressure — follicle still contains Egg.",CASCADE_EGG,ttl=10.0)
                continue

            if etype == "REPRODUCTIVE_CLIMAX":
                if wrong_route_latched or terminal_reproductive_fired:
                    continue
                reproductive_terminal_stage="HOLD"
                terminal_reproductive_pending=False
                anim.note_reproductive_climax()
                metrics._sig_inside = True
                metrics.inside = True
                metrics._sig_climax = True
                anim.lad = max(anim.lad, 0.82)
                anim.terminal_gate_t = max(anim.terminal_gate_t, 0.30)
                brat_dialogue_line="He is inside now. The hold turns into active squeezing and sperm production."
                brat_dialogue_until=now_real+12.0
                cascade.push("OVUM","chamber approach detected — transition resistance visible.",CASCADE_EGG,ttl=10.0)
                cascade.push("GAMETE","inside phase reached — sperm production animation engaged.",CASCADE_ENTRANCE,ttl=10.0)
                continue

            if etype == "REPRODUCTIVE_FINALE":
                if wrong_route_latched or terminal_reproductive_fired:
                    continue
                terminal_reproductive_pending = True
                terminal_reproductive_pending_since = now_real
                brat_dialogue_line = "Terminal hold armed. Follicle activity spikes while the gate stays locked."
                brat_dialogue_until = now_real + 10.0
                reproductive_terminal_stage = "BLOCKED"
                anim.start_terminal_sequence(bool(ev.get("heir", False)))
                anim.egg_settled = False
                brat_pose_block = True
                brat_seal_established = True
                brat_lateral_diversion = max(brat_lateral_diversion, 0.78)
                anim.gate_open = False
                anim.terminal_gate_t = 0.0
                cascade.push("OVUM", "dominant follicle wiggle detected — release sequence beginning.", CASCADE_EGG, ttl=11.0)
                cascade.push("GATE", "reproductive terminal armed: squat hold, gate LOCKED, forward motion stopped.", GATE_LOCK, ttl=11.0)
                continue

            if etype == "CLIMAX":
                if wrong_route_latched:
                    continue
                t = ev.get("t",0.0)
                if t != climax_seen:
                    climax_seen = t
                    anim.on_climax(spring, cascade, metrics, allow_conception=False)
                metrics.ingest(ev)
            elif etype == "INSERTION":
                # Ogre sprite just attached — force inside, snap lad, flash gate
                metrics._sig_inside = True
                metrics.inside      = True
                anim.gate_flash   = max(getattr(anim, "gate_flash",   0.0), 0.65)
                anim.breach_flash = max(getattr(anim, "breach_flash", 0.0), 0.40)
                anim.lad = max(anim.lad, 0.60)
                spring.jolt((random.random()-0.5)*0.5, -1.8)
                cascade.on_insertion()

            elif etype == "ENDLESS_CONTINUE":
                # Ogre warm-continued — bio metrics stay live, egg restarts
                cascade.push("TUBE",
                    f"warm continue #{ev.get('cycle',1)}. tube is ready.",
                    CASCADE_TUBE, ttl=8.0)
                cascade.push("BIRD",
                    "...round two. okay. okay fine.",
                    CASCADE_BIRD, ttl=9.0)
                spring.jolt(0.0, -1.2)
            elif etype == "CONCEPTION_LOCK":
                reproductive_terminal_stage = "HOLD"
                metrics._sig_inside = True
                metrics.inside = True
                metrics._sig_climax = True
                anim.lad = max(anim.lad, 1.0)
                anim.note_conception_lock()
                brat_dialogue_line = "Contact hold. The ovum catches, then settles with sperm in view."
                brat_dialogue_until = now_real + 12.0
                cascade.push("LOCK", "contact hold established — sperm visible at the chamber.", CASCADE_ENTRANCE, ttl=11.0)
            elif etype == "CONCEPTION":
                reproductive_terminal_stage = "HOLD"
                terminal_reproductive_fired = True
                terminal_reproductive_pending = False
                metrics._sig_inside = True
                metrics.inside = True
                metrics._sig_climax = True
                anim.lad = max(anim.lad, 1.0)
                anim.note_conception()
                brat_dialogue_line = "Conception confirmed."
                brat_dialogue_until = now_real + 12.0
            elif etype is None or etype not in ("OGRE_BOOT",):
                if wrong_route_latched and isinstance(ev, dict):
                    ev = dict(ev)
                    ev["inside"] = False
                    ev["climax"] = False
                metrics.ingest(ev)
                if wrong_route_latched:
                    metrics._sig_inside = False
                    metrics.inside = False
                    metrics._sig_climax = False
                    metrics.climax_f = 0.0
                # Rising-edge detect OGRE's per-frame climax flag (her climax)
                try:
                    bio = ev.get("biometrics", ev) if isinstance(ev, dict) else {}
                    cr = bio.get("climax", bio.get("CLIMAX", False))
                    cbool = cr if isinstance(cr, bool) else str(cr).strip().lower() in ("1","true","yes","y","on","t")
                    if (not wrong_route_latched) and bool(cbool) and (not prev_climax_flag) and (time.time() - last_climax_edge > 0.75):
                        last_climax_edge = time.time()
                        anim.on_climax(spring, cascade, metrics, allow_conception=False)
                    prev_climax_flag = bool(cbool)
                except Exception:
                    pass
                if metrics.combo > prev_combo + 3:
                    spring.jolt((random.random()-0.5)*1.3, -0.8)
                prev_combo = metrics.combo
                # Inside rising/falling edge (backup to INSERTION event)
                _now_inside = bool(metrics.inside)
                if _now_inside and not prev_inside:
                    anim.gate_flash   = max(getattr(anim, "gate_flash",   0.0), 0.45)
                    anim.breach_flash = max(getattr(anim, "breach_flash", 0.0), 0.28)
                    anim.lad = max(anim.lad, 0.45)
                    spring.jolt((random.random()-0.5)*0.4, -1.1)
                    cascade.on_insertion()
                elif not _now_inside and prev_inside:
                    spring.jolt((random.random()-0.5)*0.3, 0.7)
                prev_inside = _now_inside


        metrics.model_tick(dt, now)

        anim.timeline_progress = _clamp((now_real - session_started_at) / 180.0)
        if (not impact_release_seen) and (not getattr(anim, "terminal_seq_active", False)) and anim.timeline_progress > 0.43:
            anim.timeline_progress = 0.43

        # Reproductive climax is explicitly authored by Shader via
        # REPRODUCTIVE_COMMIT -> REPRODUCTIVE_CLIMAX. Cathedral does not infer it.
        # OGRE climax edge trigger: if telemetry emits a 'climax' boolean, use its rising edge
        # to fire the burst (instead of relying on the internal fallback).
        try:
            _ogre_edge_t = float(getattr(metrics, "_sig_climax_edge_t", 0.0))
        except Exception:
            _ogre_edge_t = 0.0
        if (not wrong_route_latched) and _ogre_edge_t > last_ogre_climax_edge:
            last_ogre_climax_edge = _ogre_edge_t
            last_climax_edge = now  # suppress immediate fallback double-fire
            anim.on_climax(spring, cascade, metrics, allow_conception=False)


        # Fallback climax trigger: if OGRE telemetry doesn't emit a clean edge,
        # allow the internal model to fire a climax pulse (EDGE+ only).
        if (not wrong_route_latched) and metrics.climax_f > 0.985 and (now - last_climax_edge > 2.0) and metrics.stage_idx >= 4:
            last_climax_edge = now
            anim.on_climax(spring, cascade, metrics, allow_conception=False)

        # Freeze the whole panel briefly after the 'point of no return'
        dt_sim = dt if getattr(metrics, "freeze_t", 0.0) <= 0.0 else 0.0

        metrics.decay(dt_sim)
        metrics.lerp(dt_sim)
        spring.tick(dt_sim, metrics)
        cascade.tick(metrics, anim)
        # Explicit reproductive terminal physics:
        # BLOCKED = no forward crossing; show lateral/downward diversion.
        # HOLD = gate already open; sustained active rhythm keeps feeding the
        # forward stream for the prolonged terminal resolution.
        if reproductive_terminal_stage == "BLOCKED":
            brat_lateral_diversion = max(brat_lateral_diversion, 0.78)
            anim.gate_open = False
            anim.terminal_gate_t = 0.0
        elif reproductive_terminal_stage == "HOLD":
            late_seq = str(getattr(anim, "terminal_seq_phase", "") or "") in ("TRANSITION_STUCK", "PLOP_IN", "CONCEPTION_LOCK", "CONCEPTION")
            if (not getattr(anim, "terminal_seq_active", False)) or late_seq:
                anim.gate_open = True
                anim.terminal_gate_t = max(anim.terminal_gate_t, 0.35)
            # prolonged forward production while held; this is intentionally
            # steady rather than another flashing climax event.
            if metrics.inside and random.random() < min(0.92, dt_sim * (12.0 + 14.0*metrics.power + (8.0 if late_seq else 0.0))):
                anim.sperm.append([0.0, random.choice([-1,0,0,1]), random.uniform(0,2*math.pi)])

        anim.lateral_diversion += (brat_lateral_diversion - anim.lateral_diversion) * min(1.0, dt_sim*5.0)
        anim.seal_strength += ((1.0 if brat_seal_established else 0.0) - anim.seal_strength) * min(1.0, dt_sim*6.0)
        if brat_phase == "PROLONGED_TERMINAL_HOLD":
            anim.terminal_hold = min(1.0, anim.terminal_hold + dt_sim*0.18)
        else:
            anim.terminal_hold = max(0.0, anim.terminal_hold - dt_sim*0.35)

        anim.tick(dt_sim, metrics, spring, cascade)
        if getattr(anim, "terminal_seq_launch_pending", False) and time.time() >= float(getattr(anim, "terminal_seq_launch_at", 0.0) or 0.0):
            anim.terminal_seq_launch_pending = False
            if _launch_verified_conception_screen():
                running = False
                continue
        if wrong_route_latched:
            metrics._sig_inside = False
            metrics.inside = False
            metrics._sig_climax = False
            metrics.climax_f = 0.0
            anim.lad = 0.0
            anim.sperm.clear()
        ecg.tick(dt_sim, metrics)


        # ── Draw ───────────────────────────────────────────────────────────
        screen.fill(BG)

        # ── Anatomy offset ─────────────────────────────────────────────────
        ox = spring.ix(); oy = spring.iy()
        if metrics.conv_global > 0.1:
            ox += int((random.random()-0.5) * metrics.conv_global * 6)
            oy += int((random.random()-0.5) * metrics.conv_global * 4)

        def ao(x,y): return (x+ox, y+oy)

        # Layout anchors
        OVY_L_X = CX - int(230*_SX); OVY_R_X = CX + int(230*_SX); OVY_Y = int(100*_SY)
        UTX = CX;             UTY = int(355*_SY)
        heartbeat_scale = 1.0 + 0.038*max(0, math.sin(anim.heart_phase))
        heart_pulse = max(0, math.sin(anim.heart_phase))*0.5
        UTW = int((205 + metrics.melt*48 + math.sin(anim.uterus_ph)*10) * heartbeat_scale)
        UTH = int((190 + metrics.melt*42 + math.sin(anim.uterus_ph*1.3)*7) * heartbeat_scale)
        if metrics.conv_uterus > 0.1:
            UTW += int(math.sin(now*18)*metrics.conv_uterus*8)
            UTH += int(math.cos(now*15)*metrics.conv_uterus*6)
        GATE_Y    = UTY + UTH//2 + 10
        GATE_H    = int(56*_SY)
        TUNNEL_T  = GATE_Y + GATE_H + 4
        TUNNEL_B  = H - int(46*_SY)

        # ══ FLESH BACKGROUND — warm body interior ═════════════════════════
        draw_flesh_bg(screen, now, metrics.melt, heart_pulse, L_PANEL, R_PANEL)

        # ══ FALLOPIAN TUBES — layered organic tissue ═══════════════════════
        def tube_pts(sx,sy,ex,ey,side,n=90):
            pts=[]
            conv = metrics.conv_tube
            for i in range(n+1):
                t=i/n
                wave = math.sin(anim.tube_ph - t*math.pi*4)*22*side*(0.28+metrics.melt*0.85)
                if conv > 0.05:
                    wave += math.sin(anim.tube_ph*3 - t*math.pi*8)*conv*15*side
                    wave += (random.random()-0.5)*conv*3.5
                bx = sx + (ex-sx)*t + wave
                by = sy + (ey-sy)*(t**1.32)
                pts.append(ao(bx,by))
            return pts

        # Infundibulum angles (where fimbriae attach — pointing toward ovary)
        def tube_angle_at_end(sx,sy,ex,ey,side):
            """Direction of tube at the ovary end."""
            dx = (ex-sx)*0.08 + math.cos(anim.tube_ph)*22*side*0.28
            dy = (ey-sy)*0.08
            return math.atan2(dy, dx) + math.pi  # point back toward ovary

        lox,loy = ao(OVY_L_X, OVY_Y)
        rox,roy = ao(OVY_R_X, OVY_Y)
        l_tube_end = ao(UTX-UTW//2+14, UTY-UTH//2)
        r_tube_end = ao(UTX+UTW//2-14, UTY-UTH//2)

        # Draw tubes: outer wall → muscular → mucosal layers
        for pts,thick,col,gw in [
            (tube_pts(OVY_L_X,OVY_Y,UTX-UTW//2+14,UTY-UTH//2, 1), 26, TUBE_WALL, False),
            (tube_pts(OVY_L_X,OVY_Y,UTX-UTW//2+14,UTY-UTH//2, 1), 14, TUBE_MED,  False),
            (tube_pts(OVY_L_X,OVY_Y,UTX-UTW//2+14,UTY-UTH//2, 1),  6, TUBE_MUC,  True ),
            (tube_pts(OVY_R_X,OVY_Y,UTX+UTW//2-14,UTY-UTH//2,-1), 26, TUBE_WALL,  False),
            (tube_pts(OVY_R_X,OVY_Y,UTX+UTW//2-14,UTY-UTH//2,-1), 14, TUBE_MED,   False),
            (tube_pts(OVY_R_X,OVY_Y,UTX+UTW//2-14,UTY-UTH//2,-1),  6, TUBE_MUC,   True ),
        ]:
            actual_col = col
            if metrics.conv_tube > 0.5 and col == TUBE_MUC:
                t_lp = (metrics.conv_tube-0.5)/0.5
                actual_col = (int(col[0]*(1-t_lp)+TUBE_HOT[0]*t_lp),
                              int(col[1]*(1-t_lp)+TUBE_HOT[1]*t_lp),
                              int(col[2]*(1-t_lp)+TUBE_HOT[2]*t_lp))
            draw_curve(screen, pts, actual_col, thick, glow=gw, glow_alpha=40)

        # Peristaltic glow nodes along tube
        for i in range(5):
            for side_info in [(OVY_L_X,OVY_Y,UTX-UTW//2+14,UTY-UTH//2,1),
                              (OVY_R_X,OVY_Y,UTX+UTW//2-14,UTY-UTH//2,-1)]:
                sx2,sy2,ex2,ey2,sd = side_info
                t_p = (now*0.55 + i*0.22) % 1.0
                wave2 = math.sin(anim.tube_ph - t_p*math.pi*4)*22*sd*(0.28+metrics.melt*0.85)
                nx_ = sx2 + (ex2-sx2)*t_p + wave2
                ny_ = sy2 + (ey2-sy2)*(t_p**1.32)
                nax,nay = ao(nx_,ny_)
                na = max(0,min(255,int(80*(0.3+0.7*math.sin(t_p*math.pi))*metrics.melt)))
                if na > 5:
                    sg = pygame.Surface((18,18),pygame.SRCALPHA)
                    pygame.draw.circle(sg,(*TUBE_GLOW,na),(9,9),9)
                    screen.blit(sg,(int(nax-9),int(nay-9)))

        # Fimbriae at infundibular ends (pointing toward each ovary)
        draw_fimbriae(screen, lox, loy+10, math.pi*0.6, conv=metrics.conv_tube, n=9, now=now)
        draw_fimbriae(screen, rox, roy+10, math.pi*0.4, conv=metrics.conv_tube, n=9, now=now)

        # ══ OVARY CLUSTERS — anatomical almond-shaped organs ══════════════
        draw_ovary_organ(screen, lox, loy, anim.egg_side==0,
                         metrics.conv_cluster, anim, metrics, now)
        draw_ovary_organ(screen, rox, roy, anim.egg_side==1,
                         metrics.conv_cluster, anim, metrics, now)

        # Ovary labels
        for ox_lbl,oy_lbl in [(lox,loy),(rox,roy)]:
            lbl_o = font_lbl.render("OVARY", True, (*LABEL_COL,180))
            screen.blit(lbl_o,(ox_lbl-lbl_o.get_width()//2, oy_lbl-44))

        # ══ UTERUS — full layered anatomical body ═════════════════════════
        ux0 = UTX + spring.jitter_uterus[0]
        uy0 = UTY + spring.jitter_uterus[1]
        ux,uy = ao(ux0,uy0)

        draw_uterus_body(screen, ux, uy, UTW, UTH, metrics, anim, now)

        # Uterus annotation
        lbl_ut = font_lbl.render("UTERUS", True, (*LABEL_COL,170))
        screen.blit(lbl_ut,(ux-lbl_ut.get_width()//2, uy-UTH//2-20))

        # ══ EGG JOURNEY ═══════════════════════════════════════════════════
        ep = anim.egg_pos
        egg_r = int(28 - ep*10)
        egg_state = _egg_state(anim, metrics)

        if ep < 0.22:
            cx0 = OVY_L_X if anim.egg_side==0 else OVY_R_X
            toward_tube = 1 if anim.egg_side==0 else -1
            seqp = str(getattr(anim,"terminal_seq_phase","") or "")
            seqt = float(getattr(anim,"terminal_seq_t",0.0) or 0.0)
            wig=0.45+ep*2.5+0.75*float(getattr(anim,"ovum_wiggle",0.0))
            bul=1.0+0.28*float(getattr(anim,"ovum_bulge",0.0))
            if getattr(anim,"terminal_seq_active",False) and seqp == "FOLLICLE_PULSE":
                # Press toward the inner wall with each pulse, but remain contained.
                ex_ = cx0 + toward_tube*(10 + 8*math.sin(now*6.5)) + math.sin(now*13)*6*wig
                ey_ = OVY_Y + math.cos(now*10)*8*wig
            elif getattr(anim,"terminal_seq_active",False) and seqp == "FOLLICLE_RECOIL":
                # Deliberately breathe AWAY from the tube entrance.
                u=min(1.0,max(0.0,seqt/0.95))
                ex_ = cx0 - toward_tube*(6 + 12*u) + math.sin(now*5.0)*4
                ey_ = OVY_Y + math.cos(now*4.0)*5
            elif getattr(anim,"terminal_seq_active",False) and seqp == "NEAR_BREACH":
                # Lean hard into the tube-side follicle wall, then recoil a hair.
                breathe=0.5+0.5*math.sin(now*5.2)
                ex_ = cx0 + toward_tube*(18 + 12*breathe*float(getattr(anim,"ovum_bulge",0.0)))
                ey_ = OVY_Y + math.sin(now*8.0)*5
            elif getattr(anim,"terminal_seq_active",False) and seqp == "SPANK_RELEASE":
                # The breach is directional: visible snap from ovary toward tube.
                u=min(1.0,max(0.0,seqt/0.46))
                ex_ = cx0 + toward_tube*(22 + 74*(u*u*(3-2*u)))
                ey_ = OVY_Y + (UTY-UTH//2-OVY_Y)*0.16*u + math.sin(now*16)*3*(1-u)
            else:
                ex_ = cx0 + math.sin(now*14)*22*wig*bul
                ey_ = OVY_Y + math.cos(now*14)*14*wig
        elif ep < 0.65:
            t2 = (ep-0.22)/0.43
            sx_ = OVY_L_X if anim.egg_side==0 else OVY_R_X
            exx = UTX-(UTW//2-14) if anim.egg_side==0 else UTX+(UTW//2-14)
            ex_ = sx_ + (exx-sx_)*t2
            ey_ = OVY_Y + (UTY-UTH//2-OVY_Y)*(t2**1.3)
            wave = math.sin(anim.tube_ph - t2*math.pi*4)*14
            ex_ += wave*(1 if anim.egg_side==0 else -1)
        elif ep < 1.0:
            t3 = (ep-0.65)/0.35
            ex_ = UTX + math.sin(now*5+t3*6)*int(UTW*0.26)*(1-t3)
            ey_ = UTY + math.cos(now*5+t3*6)*int(UTH*0.21)*(1-t3)
        else:
            ex_ = UTX + math.sin(now*2.2)*int(UTW*0.17)
            ey_ = UTY + math.cos(now*2.2)*int(UTH*0.11)

        ex_ += spring.x*0.4; ey_ += spring.y*0.3
        eax,eay = ao(ex_,ey_)
        draw_egg(screen, eax, eay, egg_r, egg_state, now, conv=metrics.conv_uterus)

        # ══ CERVIX / GATE — anatomical cervical body ══════════════════════
        gx0 = UTX + spring.jitter_gate[0]
        gy0 = GATE_Y + GATE_H//2 + spring.jitter_gate[1]
        gx,gy = ao(gx0,gy0)

        # Cervical body (barrel-shaped)
        cerv_w = int(UTW*0.52)
        cerv_h = GATE_H + 12
        # Outer cervical stroma
        alpha_rect(screen, SEROSA, (gx-cerv_w//2-8, gy-cerv_h//2-4,
                                     cerv_w+16, cerv_h+8), 255, radius=cerv_h//4)
        alpha_rect(screen, CERVIX_COL, (gx-cerv_w//2, gy-cerv_h//2,
                                         cerv_w, cerv_h), 255, radius=cerv_h//4)

        # Endocervical canal (dark line through center)
        canal_w = max(4, int(cerv_w*0.22))
        alpha_rect(screen, SEROSA, (gx-canal_w//2, gy-cerv_h//2+4,
                                     canal_w, cerv_h-8), 240, radius=canal_w//2)

        # Internal os (top of cervix connecting to uterus)
        int_os_w = int(cerv_w*0.42)
        pygame.draw.ellipse(screen, MYO_MID,
                            (gx-int_os_w//2, gy-cerv_h//2-3, int_os_w, 10))

        # External os (bottom — opens/closes based on gate state)
        col_g  = GATE_OPEN if anim.gate_open else GATE_LOCK
        os_col = OS_OPEN if anim.gate_open else OS_CLOSED
        pulse_add = int(math.sin(anim.gate_ph)*3*(2.5 if anim.gate_open else 0.8)
                        + metrics.conv_gate*12*math.sin(now*20))
        ext_os_w = max(6, int(cerv_w*0.38) + pulse_add)
        ext_os_h = max(4, GATE_H//3 + int(metrics.conv_gate*8*math.sin(now*18)))
        pygame.draw.ellipse(screen, os_col,
                            (gx-ext_os_w//2, gy+cerv_h//2-ext_os_h-2, ext_os_w, ext_os_h))
        # Iris petals on open state
        if anim.gate_open:
            for i in range(8):
                a = anim.iris_ph + i*(2*math.pi/8)
                px1 = gx + int(math.cos(a)*ext_os_w*0.4)
                py1 = gy + cerv_h//2 - ext_os_h//2 + int(math.sin(a)*ext_os_h*0.3)
                px2 = gx + int(math.cos(a+0.35)*ext_os_w*0.75)
                py2 = gy + cerv_h//2 - ext_os_h//2 + int(math.sin(a+0.35)*ext_os_h*0.55)
                pygame.draw.line(screen, (*GATE_IRIS,100),(px1,py1),(px2,py2),1)
        if anim.gate_flash > 0.2:
            alpha_rect(screen, GATE_PULSE, (gx-cerv_w//2-8,gy-cerv_h//2-8,cerv_w+16,cerv_h+16),
                       int(anim.gate_flash*190), radius=cerv_h//4+6)
        # Status label
        glbl = font_sm.render("[ OPEN ]" if anim.gate_open else "[ LOCKED ]", True, col_g)
        screen.blit(glbl,(gx-glbl.get_width()//2, gy-glbl.get_height()//2))

        # ══ VAGINAL CANAL — flesh walls with rugae ════════════════════════
        t_jx = spring.jitter_tunnel[0]; t_jy = spring.jitter_tunnel[1]

        def tunnel_wall_x(y_pos, side, n=60):
            t = (y_pos - TUNNEL_T) / max(1, TUNNEL_B - TUNNEL_T)
            t = max(0, min(1, t))
            tw = int(UTW*0.50 + UTW*0.44*t)
            conv = metrics.conv_tunnel
            wave = math.sin(anim.tunnel_ph - t*math.pi*10)*int(18+metrics.push*22)
            if conv > 0.05:
                wave += math.sin(anim.tunnel_ph*2.5 - t*math.pi*18)*conv*int(22+metrics.push*14)
                wave += (random.random()-0.5)*conv*5
            if side<0: wave=-wave
            return UTX + side*(tw//2 + wave//2) + t_jx

        def tunnel_pts_wall(side, n=80):
            pts=[]
            conv = metrics.conv_tunnel
            for i in range(n+1):
                t=i/n
                y_pos = TUNNEL_T + (TUNNEL_B-TUNNEL_T)*t
                tw = int(UTW*0.50 + UTW*0.44*t)
                wave = math.sin(anim.tunnel_ph - t*math.pi*10)*int(18+metrics.push*22)
                if conv > 0.05:
                    wave += math.sin(anim.tunnel_ph*2.5 - t*math.pi*18)*conv*int(22+metrics.push*14)
                    wave += (random.random()-0.5)*conv*5
                if side<0: wave=-wave
                x_pos = UTX + side*(tw//2 + wave//2) + t_jx
                pts.append(ao(x_pos, y_pos + t_jy))
            return pts

        # Wall layers: outer (peritoneum/muscular) → submucosa → mucosa
        for side,thick,col,gw in [
            (-1,36,SEROSA,False),(-1,22,CANAL_WALL,False),(-1, 8,TUBE_MUC,True),
            ( 1,36,SEROSA,False),( 1,22,CANAL_WALL,False),( 1, 8,TUBE_MUC,True),
        ]:
            act_col = col
            if metrics.conv_tunnel > 0.5 and col == TUBE_MUC:
                t_lp = (metrics.conv_tunnel-0.5)/0.5
                act_col = (int(col[0]*(1-t_lp)+TUBE_HOT[0]*t_lp),
                           int(col[1]*(1-t_lp)+TUBE_HOT[1]*t_lp),
                           int(col[2]*(1-t_lp)+TUBE_HOT[2]*t_lp))
            draw_curve(screen, tunnel_pts_wall(side), act_col, thick, glow=gw, glow_alpha=38)

        # Rugae folds on both walls
        n_rugae = 5 + int(metrics.push * 3)
        for fold_i in range(n_rugae):
            t_f = fold_i / max(1, n_rugae-1)
            fy_base = int(TUNNEL_T + (TUNNEL_B - TUNNEL_T)*0.08 + (TUNNEL_B-TUNNEL_T)*0.84*t_f)
            for side_r in (-1, 1):
                wx = tunnel_wall_x(fy_base, side_r)
                draw_rugae(screen, wx + t_jx, fy_base, fy_base+14,
                           lambda y: tunnel_wall_x(y, side_r),
                           side_r, 1, anim.tunnel_ph + fold_i*0.6)

        # Peristaltic lubrication glow nodes
        n_nodes = 7 + int(metrics.push*4)
        for i in range(n_nodes):
            phase_off = (now*0.85 + i*0.14) % 1.0
            ty_ = TUNNEL_T + (TUNNEL_B-TUNNEL_T)*phase_off
            tw2 = int(UTW*0.50 + UTW*0.22*phase_off)
            wave2 = math.sin(anim.tunnel_ph - phase_off*math.pi*10)*int(14+metrics.push*16)
            ttx = UTX + wave2*0.4 + t_jx
            na2 = max(0,min(255,int(110*(0.35+0.65*math.sin(phase_off*math.pi))*metrics.melt)))
            if na2 > 5:
                gax2,gay2 = ao(ttx, ty_+t_jy)
                node_r2 = 7+int(metrics.conv_tunnel*4)
                sg2=pygame.Surface((node_r2*4,node_r2*4),pygame.SRCALPHA)
                pygame.draw.circle(sg2,(*FLESH_GLOW,na2),(node_r2*2,node_r2*2),node_r2*2)
                screen.blit(sg2,(int(gax2-node_r2*2),int(gay2-node_r2*2)))

        # Introitus label
        lbl_tun=font_lbl.render("VAGINAL CANAL",True,(*LABEL_COL,130))
        screen.blit(lbl_tun,(ao(UTX,TUNNEL_T-16)[0]-lbl_tun.get_width()//2,ao(UTX,TUNNEL_T-16)[1]))

        # ══ INSIDE PRESENCE ═══════════════════════════════════════════════
        if anim.lad > 0.02:
            p = anim.lad
            spd   = 1.6 + metrics.push*3.0 + metrics.power*1.4 + float(getattr(anim, "thrust_boost", 0.0))*6.0
            phase = now * spd + anim.tunnel_ph*0.25
            thrust = 0.5 + 0.5*math.sin(phase)
            sway  = math.sin(now*1.4+anim.tunnel_ph) * (5 + metrics.push*12 + float(getattr(anim, "thrust_boost", 0.0))*10.0) * p

            open_w  = int(UTW*0.92)
            shaft_w = int(open_w*(0.26+0.06*thrust)*(0.78+0.22*p))
            bulge_w = int(shaft_w*(1.16+0.22*thrust))
            bulb_h  = int(bulge_w*1.05)
            # At the repro->climax threshold the lower bulb visibly squeezes
            # in pulses while sperm production is active. This makes the
            # transition readable even before the gametes reach the chamber.
            if bool(getattr(anim,"terminal_seq_climax",False)):
                squeeze = 0.5 + 0.5*math.sin(now*10.5)
                bulge_w = max(12, int(bulge_w*(1.00-0.13*squeeze)))
                bulb_h  = max(12, int(bulb_h*(1.00+0.16*squeeze)))
            vis_h   = int((220+72*thrust+44*metrics.power)*p)+60

            canvas_w = bulge_w+90; canvas_h = vis_h+bulb_h+130
            lad_surf = pygame.Surface((canvas_w,canvas_h),pygame.SRCALPHA)
            cx_l = canvas_w//2; tip_y = 60+bulb_h//2

            a_outer=int(210*p); a_mid=int(165*p); a_lite=int(62*p); a_glow=int(110*p)
            # Soft warm glow halo
            pygame.draw.ellipse(lad_surf,(*FLESH_GLOW,int(25*p)),
                                (cx_l-bulge_w//2-26,tip_y-bulb_h//2-22,bulge_w+52,bulb_h+44))
            # Shaft — flesh toned
            shaft_rect=pygame.Rect(cx_l-shaft_w//2,tip_y,shaft_w,canvas_h-tip_y+20)
            pygame.draw.rect(lad_surf,(*MYO,a_outer),shaft_rect,border_radius=max(10,shaft_w//2))
            # Bulge
            bulb_rect=pygame.Rect(cx_l-bulge_w//2,tip_y-bulb_h//2,bulge_w,bulb_h)
            pygame.draw.ellipse(lad_surf,(*CANAL_WALL,a_mid),bulb_rect)
            # Inner highlight (gloss/skin sheen)
            iw=max(10,int(bulge_w*0.46)); ih=max(10,int(bulb_h*0.38))
            pygame.draw.ellipse(lad_surf,(*FLESH_WARM,a_lite),pygame.Rect(cx_l-iw//2,tip_y-ih//2,iw,ih))
            # Rim edge
            pygame.draw.ellipse(lad_surf,(*FLESH_BRIGHT,a_glow),bulb_rect.inflate(10,10),2)
            # Specular stripe
            gloss_w=max(4,shaft_w//7); gloss_h=max(18,int((canvas_h-tip_y)*0.36))
            pygame.draw.rect(lad_surf,(*WHITE,int(28*p)),
                             pygame.Rect(cx_l-shaft_w//5,tip_y+int((canvas_h-tip_y)*0.18),
                                         gloss_w,gloss_h),border_radius=max(2,gloss_w//2))

            tip_screen_y=TUNNEL_B-int((82+65*thrust+26*metrics.power)*p)
            tip_screen_y=max(TUNNEL_B-int(242*p),min(TUNNEL_B-20,tip_screen_y))
            tlx,tly=ao(UTX+sway-canvas_w//2,tip_screen_y-tip_y)
            screen.blit(lad_surf,(tlx,tly))
            # Introitus ring
            ring_w=int(open_w*0.60); ring_h=int(44+10*thrust)
            rx,ry=ao(UTX+sway,TUNNEL_B-10)
            ring_col=GATE_PULSE if metrics.consent=="GREEN" else GATE_LOCK
            ring_s=pygame.Surface((ring_w+20,ring_h+20),pygame.SRCALPHA)
            pygame.draw.ellipse(ring_s,(*ring_col,int(68*p)),(10,10,ring_w,ring_h),2)
            screen.blit(ring_s,(rx-(ring_w+20)//2,ry-(ring_h+20)//2))

        # ══ SPERM — warm ivory ════════════════════════════════════════════
        lane_xs = {-1: UTX-18, 0: UTX, 1: UTX+18}
        for sp in anim.sperm:
            pos,lane,wph = sp[0],int(sp[1]),sp[2]
            sy_ = TUNNEL_B - int(pos*(TUNNEL_B-TUNNEL_T))
            lx_ = lane_xs.get(lane, UTX)
            wiggle_amp = int(9+pos*8+metrics.push*5)
            wiggle = math.sin(wph)*wiggle_amp
            spx,spy = ao(lx_+wiggle, sy_)
            head_r = max(3, int(5-pos*2))
            col_sp = SPERM_HEAD if pos>0.7 else SPERM_COL
            glow_circle_s(screen, col_sp, int(spx), int(spy), head_r+4, alpha=45)
            pygame.draw.circle(screen, col_sp, (int(spx),int(spy)), head_r)
            for tj in range(1,6):
                tail_y_ = spy + tj*5
                tail_x_ = spx - math.sin(wph-tj*0.45)*6
                at = max(0,min(255,int(155*(1-tj/6.0)*(0.32+pos*0.68))))
                ts=pygame.Surface((10,10),pygame.SRCALPHA)
                pygame.draw.circle(ts,(*SPERM_COL,at),(5,5),max(1,4-tj))
                screen.blit(ts,(int(tail_x_-5),int(tail_y_-5)))

        # ══ PARTICLES ════════════════════════════════════════════════════
        for px_,py_,pvx,pvy,life,col_p in anim.particles:
            alpha_p=max(0,min(255,int(220*min(life,1.0))))
            r_p=max(2,int(7*min(life,1.0)))
            ps=pygame.Surface((r_p*2+2,r_p*2+2),pygame.SRCALPHA)
            pygame.draw.circle(ps,(*col_p,alpha_p),(r_p+1,r_p+1),r_p)
            screen.blit(ps,(int(px_-r_p-1),int(py_-r_p-1)))

                # ══ ECG STRIP ════════════════════════════════════════════════════
        ecg_x = L_PANEL + 5
        ecg_y = H - int(46*_SY)
        ecg.draw(screen, ecg_x, ecg_y, R_PANEL-L_PANEL-10, int(38*_SY))
        lbl_ecg = font_lbl.render("CARDIAC MONITOR", True, ECG_DIM)
        screen.blit(lbl_ecg, (ecg_x+4, ecg_y+2))

        # ══ HUD: LEFT PANEL ══════════════════════════════════════════════
        lp   = 14
        _lhw = L_PANEL - 10
        # Panel border
        draw_panel_border(screen, lp-4, 8, _lhw, H-16, HUD_BORDER,
                          title="SYS", font=font_lbl)

        stage_col = [TUBE_GLOW, CLUSTER_B, CLUSTER_A, GATE_OPEN,
                     GATE_PULSE, GATE_LOCK, PARTICLE_A, DIM][int(metrics.stage_idx) % 8]

        # Title
        t_title = font_lg.render("LIVING CATHEDRAL", True, (185,125,235))
        screen.blit(t_title, (lp, 14))
        # Stage indicator
        t_stage = font_md.render(f"STAGE: {metrics.stage}", True, stage_col)
        screen.blit(t_stage, (lp, 50))
        # Stage progress bar
        bar_w = int(_lhw * 0.93)
        pygame.draw.rect(screen, HUD_BG, (lp, 74, bar_w, 14), border_radius=3)
        si = metrics.stage_idx
        fill_w = max(2, int(bar_w*(si+1)/len(STAGE_ORDER)))
        pygame.draw.rect(screen, stage_col, (lp, 74, fill_w, 14), border_radius=3)
        # Stage tick marks
        for i in range(len(STAGE_ORDER)):
            tx = lp + int(bar_w*(i+1)/len(STAGE_ORDER))
            pygame.draw.line(screen, (*HUD_BORDER,180), (tx,74),(tx,88), 1)

        # Consent + contact
        cc = GATE_OPEN if metrics.consent=="GREEN" else GATE_LOCK
        screen.blit(font_sm.render(f"CONSENT: {metrics.consent}", True, cc), (lp,100))
        screen.blit(font_sm.render(f"CONTACT: {metrics.contact}", True, DIM), (lp,118))
        screen.blit(font_sm.render(f"LEAD:    {metrics.lead}", True, DIM), (lp,136))

        y_bar = 162
        bars = [
            ("melt",     metrics.melt,     CLUSTER_A,  0.65),
            ("push",     metrics.push,     GATE_PULSE, 0.60),
            ("power",    metrics.power,    TUBE_GLOW,  0.70),
            ("pressure", metrics.pressure, CLUSTER_B,  0.70),
            ("denial",   metrics.denial,   GATE_LOCK,  0.55),
            ("climax →", metrics.climax_f, (200,60,225),0.70),
            ("composure",metrics.composure,(115,200,140),0.25),
        ]
        for lbl,val,col_b,thresh in bars:
            draw_bar_fancy(screen, font_sm, lp, y_bar, 262, 18, val, col_b, lbl, thresh)
            y_bar += 42

        # Stats
        y_stat = y_bar + 6
        stats = [
            (f"combo:   {metrics.combo}", CASCADE_EGG if int(metrics.combo or 0)>5 else DIM),
            (f"pose:    {metrics.pose[:18]}", DIM),
            (f"card:    {metrics.card_id[:18]}", DIM),
            (f"inside:  {metrics.inside}", GATE_OPEN if metrics.inside else DIM),
            (f"seed:    {metrics.seed}", DIM),
            (f"tier:    {metrics.tier}", TUBE_GLOW if int(metrics.tier or 0)>0 else DIM),
        ]
        for txt,col_s in stats:
            screen.blit(font_sm.render(txt, True, col_s), (lp, y_stat))
            y_stat += 22

        # Wobble + convulsion readouts
        y_stat += 4
        screen.blit(font_lbl.render(f"spring   {spring.x:+.1f},{spring.y:+.1f}", True, (45,45,65)),
                    (lp, y_stat)); y_stat += 16
        # Convulsion levels
        if any(v > 0.05 for v in [metrics.conv_tunnel, metrics.conv_uterus, metrics.conv_tube,
                                    metrics.conv_gate, metrics.conv_global]):
            screen.blit(font_lbl.render("CONVULSION:", True, WARN_COL), (lp, y_stat)); y_stat+=14
            for nm,val in [("tunnel",metrics.conv_tunnel),("uterus",metrics.conv_uterus),
                           ("tube",metrics.conv_tube),("gate",metrics.conv_gate)]:
                if val > 0.05:
                    bar_fill = int(100*val)
                    col_cv = (int(255*val), int(180*(1-val)), 60)
                    pygame.draw.rect(screen,HUD_BG,(lp,y_stat,100,8),border_radius=2)
                    pygame.draw.rect(screen,col_cv,(lp,y_stat,bar_fill,8),border_radius=2)
                    screen.blit(font_lbl.render(nm,True,DIM),(lp+104,y_stat-2))
                    y_stat+=12

        # ══ HUD: RIGHT PANEL (CASCADE) ════════════════════════════════════
        rp = R_PANEL + 8
        draw_panel_border(screen, rp-4, 8, W-rp, H-16, HUD_BORDER,
                          title="INTERNAL MONOLOGUE", font=font_lbl)

        screen.blit(font_lg.render("INTERNAL", True, (130,95,175)), (rp, 14))
        screen.blit(font_md.render("MONOLOGUE", True, (90,65,135)), (rp, 46))
        pygame.draw.line(screen, HUD_BORDER, (rp, int(72*_SY)), (W-16, int(72*_SY)), 1)

        live = cascade.live()
        max_lines = (H-140) // 54
        visible = live[-max_lines:]
        cy_cas = 80
        for notif in visible:
            age = notif.age()
            a_notif = max(80, min(255, int(255*(1.0-age*0.65))))
            # Source label with colored tag
            src_col = tuple(min(255,int(c*0.85)) for c in notif.color)
            src_bg_a = max(20, int(60*(1-age)))
            alpha_rect(screen, notif.color, (rp, cy_cas, 80, 16), src_bg_a, radius=3)
            lbl_surf = font_cas.render(notif.source[:8], True, src_col)
            screen.blit(lbl_surf, (rp+2, cy_cas))

            # Text (wrapped to 36 chars, fade with age)
            col_t = tuple(min(255,int(c*(0.5+0.5*(1-age)))) for c in notif.color)
            txt = notif.text[:36]
            t_surf = font_cas.render(txt, True, col_t)
            screen.blit(t_surf, (rp, cy_cas+18))

            # Separator
            pygame.draw.line(screen, (30,25,48), (rp, cy_cas+40), (W-16, cy_cas+40), 1)
            cy_cas += 54
            if cy_cas > H-90: break

        # Egg status
        tp=float(getattr(anim,"timeline_progress",0.0))
        seq_phase = str(getattr(anim, "terminal_seq_phase", "") or "")
        if getattr(anim, "terminal_seq_active", False) and seq_phase not in ("", "IDLE"):
            seq_map = {
                "FOLLICLE_WIGGLE": "OVUM: Egg squirms in the follicle and pretends the exit is not there.",
                "FOLLICLE_PULSE": "OVUM: Egg pulses against the follicle walls earnestly.",
                "FOLLICLE_RECOIL": "OVUM: Egg breathes away from entering the tube of no return.",
                "NEAR_BREACH": "OVUM: Egg bulges at the seam, then stubbornly tucks itself back in.",
                "SPANK_RELEASE": "OVUM: The follicle snaps — Egg is kicked a quarter-way into the tube.",
                "TUBE_CLIMB": f"OVUM: Egg inches through the squeezing tube, regretting momentum.  {int(max(0.25, min(0.72, anim.egg_pos))*100)}%",
                "CHAMBER_HESITATION": "OVUM: Egg reaches the chamber lip and refuses the drop on principle.",
                "TRANSITION_STUCK": "OVUM: Egg is wedged in the transition ring. The ring squeezes back.",
                "PLOP_IN": "OVUM: Egg loses the argument and plops into the chamber.",
                "CONCEPTION_LOCK": "OVUM: Egg holds very still while the sperm swarm catches up.",
                "CONCEPTION": "OVUM: Egg goes quiet. Conception takes.",
            }
            egg_status = seq_map.get(seq_phase, "OVUM: Egg is doing something medically inadvisable.")
            ecol = CASCADE_EGG if seq_phase in ("CONCEPTION_LOCK", "CONCEPTION") else (220,180,80)
        elif anim.egg_settled:
            egg_status = f"OVUM: chamber {'OPEN' if anim.gate_open else 'SETTLED'}"
            ecol = CASCADE_EGG
        elif tp < 0.12:
            egg_status = "OVUM: Egg stirs inside the follicle."; ecol=(150,150,170)
        elif tp < 0.22:
            egg_status = "OVUM: Egg noses toward the tube, then thinks better of it."; ecol=(175,160,185)
        elif tp < 0.68:
            egg_status = f"OVUM: Egg rides the tube contractions.  {int(tp*100)}%"; ecol=(170,170,170)
        elif tp < 0.90:
            egg_status = "OVUM: Egg hovers over the chamber and refuses to commit."; ecol=(220,180,80)
        else:
            egg_status = "OVUM: waiting at [LOCKED] gate" if not anim.gate_open else "OVUM: gate OPEN"
            if brat_seal_established:
                egg_status += "  |  SEAL HOLDING"
            if brat_lateral_diversion > 0.05:
                egg_status += f"  |  lateral diversion {int(brat_lateral_diversion*100)}%"
            ecol = CASCADE_EGG if anim.gate_open else (220,180,80)
        screen.blit(font_md.render(egg_status, True, ecol), (rp, H-78))
        # Conception counter
        if anim.conception_count > 0:
            c_col = PARTICLE_A if anim.conception_flash > 0.1 else (160, 130, 60)
            c_txt = f"✦ conceptions: {anim.conception_count}"
            screen.blit(font_sm.render(c_txt, True, c_col), (rp, H-58))
            screen.blit(font_sm.render(f"gametes: {len(anim.sperm)} active  |  {brat_phase}", True, DIM), (rp, H-38))
        else:
            screen.blit(font_sm.render(f"gametes: {len(anim.sperm)} active", True, DIM), (rp, H-58))
        screen.blit(font_sm.render(f"conv: {metrics.conv_global:.2f}", True,
                                   WARN_COL if metrics.conv_global>0.3 else DIM), (rp, H-20))

        # ══ STALE INDICATOR ══════════════════════════════════════════════
        stale = time.time() - metrics.last_update
        if stale > 4.0:
            stale_t = font_sm.render(f"STALE {stale:.0f}s — AWAITING SIGNAL", True, GATE_LOCK)
            screen.blit(stale_t, (CX - stale_t.get_width()//2, H-28))
            # Blinking border on anatomy zone
            if int(now*2)%2 == 0:
                pygame.draw.rect(screen, (*GATE_LOCK,60), (L_PANEL,0,R_PANEL-L_PANEL,H), 2)

        # ══ CLIMAX SHOCK FLASH ═══════════════════════════════════════════
        if anim.shock_flash > 0.05:
            alpha_rect(screen, WHITE, (L_PANEL,0,R_PANEL-L_PANEL,H), int(anim.shock_flash*180))
            # Pre-climax strobe when climax_f near 1
        elif metrics.climax_f > 0.82:
            strobe = (math.sin(now*25)+1)*0.5 * (metrics.climax_f-0.82)/0.18
            alpha_rect(screen, CONVULSE_FX, (L_PANEL,0,R_PANEL-L_PANEL,H), int(strobe*60))

        # ══ CONCEPTION FLASH (gold overlay — 3 seconds) ══════════════════
        if anim.conception_flash > 0.05:
            pulse = (math.sin(now*7)+1)*0.5
            c_alpha = int(anim.conception_flash * (80 + pulse*80))
            alpha_rect(screen, PARTICLE_A, (L_PANEL,0,R_PANEL-L_PANEL,H), min(220, c_alpha))
            # "✦ CONCEPTION ✦" text for first 1.8 seconds
            if anim.conception_flash > 1.2:
                msg = font_xl.render("✦  CONCEPTION  ✦", True, EGG_WHITE)
                screen.blit(msg, (CX - msg.get_width()//2, H//2 - int(42*_SY)))
                num = font_md.render(f"cycle  #{anim.conception_count}", True, (*PARTICLE_A, 230))
                screen.blit(num, (CX - num.get_width()//2, H//2 + int(22*_SY)))
        # Lingering warm uterus glow after conception
        if anim.conception_glow > 0.05:
            ux_g, uy_g = ao(UTX, UTY)
            glow_circle_s(screen, PARTICLE_A, ux_g, uy_g,
                          int(UTW*0.62*_SC), alpha=int(anim.conception_glow * 60))

        # ══ OVERLAYS ═════════════════════════════════════════════════════
        draw_scanlines(screen, alpha=20)
        # Vignette
        for r_v in range(360, 0, -45):
            a_v = int(40*(1-r_v/360))
            sv = pygame.Surface((r_v*2,r_v*2),pygame.SRCALPHA)
            pygame.draw.ellipse(sv,(0,0,0,a_v),(0,0,r_v*2,r_v*2))
            screen.blit(sv,(CX-r_v, H//2-r_v))

        # Center column separator lines (subtle)
        pygame.draw.line(screen, HUD_BORDER, (L_PANEL,0),(L_PANEL,H), 1)
        pygame.draw.line(screen, HUD_BORDER, (R_PANEL,0),(R_PANEL,H), 1)

        # ── Frame marker ─────────────────────────────────────────────────
        fps_txt = font_lbl.render(f"{clock.get_fps():.0f}fps", True, (35,30,50))
        screen.blit(fps_txt, (W-50, H-16))

        # BLOCKED is only a pre-payoff diagnostic. Once Shader commits,
        # the verified Cathedral conception animation owns the entire payoff.
        if reproductive_terminal_stage == "BLOCKED":
            try:
                gy=int(H*0.57)
                pygame.draw.circle(screen,GATE_LOCK,(CX,gy),max(7,int(10*_SC)),3)
                lock=font_md.render("[LOCKED]  CONTACT HOLD",True,GATE_LOCK)
                screen.blit(lock,(CX-lock.get_width()//2,int(H*0.76)))
            except Exception:
                pass

        # ── Brat-Taming director dialogue: always rendered explicitly ─────
        if brat_dialogue_line and now_real < brat_dialogue_until:
            try:
                box_y=H-int(96*_SY)
                box=pygame.Surface((W-int(80*_SX),int(68*_SY)),pygame.SRCALPHA)
                box.fill((10,7,15,225))
                screen.blit(box,(int(40*_SX),box_y))
                head=font_lbl.render(brat_phase.replace("_"," "),True,CASCADE_EGG)
                screen.blit(head,(int(58*_SX),box_y+int(8*_SY)))
                # basic word-wrap
                words=brat_dialogue_line.split()
                lines=[]; cur=""
                for word in words:
                    trial=(cur+" "+word).strip()
                    if font_sm.size(trial)[0] > W-int(130*_SX) and cur:
                        lines.append(cur); cur=word
                    else:
                        cur=trial
                if cur: lines.append(cur)
                for i,line in enumerate(lines[:2]):
                    txt=font_sm.render(line,True,(238,229,242))
                    screen.blit(txt,(int(58*_SX),box_y+int((28+i*18)*_SY)))
            except Exception:
                pass

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback as _traceback
        try:
            _crash_path = os.path.join(RUN_DIR, "biometric_crash.log")
            os.makedirs(os.path.dirname(_crash_path), exist_ok=True)
            with open(_crash_path, "w", encoding="utf-8") as _f:
                _traceback.print_exc(file=_f)
        except Exception:
            pass
        _traceback.print_exc()
        raise
