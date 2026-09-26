#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ogre.py — Birdsong Duel (Favor HUD + Role Presets + Deterministic Persona + Magnum Opus Lines)

New:
  • City favor threaded into HUD with floating +Favor pops and event hook.
  • Role presets (BPM/swing “vibe” + role dialogue pools).
  • npc_seed for consistent NPC tempo/persona; persona_script to force persona by phase.
  • Expanded “Magnum Opus” Jessica Birdsong lines (embarrassment stakes, reclaiming grace).
  • Retains: screen-shake on shove, phase hooks, personas, particles, typewriter dialogue.

Controls:
  A  = smack (hold = heavy)
  S  = soft/parry (parry during telegraph)
  B  = burst (double/long recognized)
  ENTER = mutual release (bigger favor if in Encore)
  SPACE = soft reset duel
  Q = quit
  d dialog toggle, ;/' pace -, +, k HUD minimal, [/] BPM, ,/. swing, v/V fine swing
  1..9 set intents; 0 reset. F/G/H/J micro-events.

Integration:
  run_duel(stdscr, opponent_role="samurai", on_event=None,
           npc_seed=None, persona_script=None, base_favor=0) -> outcome dict
"""

import curses, time, math, random
from dataclasses import dataclass, field
from collections import deque

# ========== UPGRADED FEATURES ==========
# Import stink particle system
try:
    from stink_particles import StinkParticle
    STINK_AVAILABLE = True
except ImportError:
    STINK_AVAILABLE = False
    print("Warning: stink_particles.py not found - stink effects disabled")

# ========== DIALOGUE SYSTEM ==========
DIALOGUE_LINES = {
    # Opening
    "opening": [
        "let's see if you last",
        "most break by the second verse",
        "try to keep tempo",
        "breathe. this will take a while",
    ],
    
    # Reactions to THRUST (W)
    "thrust_good": [
        "...ah",
        "mm—",
        "*breathes sharply*",
        "again",
    ],
    
    "thrust_bad": [
        "rushing already?",
        "tempo. find it.",
        "clumsy",
        "try listening first",
    ],
    
    # Reactions to SPANK (A)
    "spank_react": [
        "*gasps*",
        "again?",
        "...persistent",
        "mm",
    ],
    
    # Reactions to PULL (S)
    "pull_react": [
        "pulling now?",
        "*resists*",
        "careful",
        "...fine",
    ],
    
    # Reactions to CARESS (D)
    "caress_react": [
        "gentle now?",
        "*relaxes slightly*",
        "...better",
        "mm",
    ],
    
    # Conflicted (high pleasure + high resistance)
    "conflicted": [
        "stop making me—",
        "this isn't... fair",
        "damn your rhythm",
        "don't—",
    ],
    
    # Breaking (resistance dropping)
    "breaking": [
        "wait—",
        "no—",
        "*shudders*",
        "...you can't just—",
    ],
    
    # Climax
    "climax": [
        "...you win",
        "this round",
        "*trembles*",
        "...damn you",
    ],
}

# Dialogue queue class
class DialogueQueue:
    """Simple dialogue queue for timed lines"""
    def __init__(self):
        self.current = None
        self.timer = 0.0
        self.last_tag = None
    
    def say(self, tag: str):
        """Queue a line by tag"""
        if tag == self.last_tag:
            return  # Don't repeat same tag immediately
        
        lines = DIALOGUE_LINES.get(tag, [])
        if lines:
            self.current = random.choice(lines)
            self.timer = 2.5  # Display for 2.5 seconds
            self.last_tag = tag
    
    def update(self, dt: float):
        """Update timer"""
        if self.timer > 0:
            self.timer -= dt
            if self.timer <= 0:
                self.current = None
                self.last_tag = None
    
    def get(self) -> str:
        """Get current line"""
        return self.current if self.timer > 0 else ""

# ========================================


# -------- global util
def clamp(v, lo, hi): return lo if v < lo else hi if v > hi else v


def lerp(a, b, t): return a + (b - a) * max(0.0, min(1.0, t))


def ease_in(t): t = max(0, min(1, t)); return t * t


def ease_out(t): t = max(0, min(1, t)); return 1 - (1 - t) * (1 - t)


# >>> PATCH START: resource helpers & config
def toward(x, target, rate, dt):
    d = (target - x)
    if abs(d) < 1e-6: return x
    step = rate * dt
    if d > 0:
        return x + min(step, d)
    else:
        return x - min(step, -d)


class Costs:
    # Positive values = spend/drain; negative = refund/boost (for a few reactions)
    A_LIGHT = {"Energy": 6, "Pulse": 2}
    A_HEAVY = {"Energy": 14, "Pulse": 6, "Poise": 4}
    BURST = {"Energy": 8, "Poise": 4}
    PARRY = {"Energy": 3, "Poise": -3}  # parry “refunds” a little poise on success
    FEINT = {"Energy": 1}
    HEART = {"Pulse": -6, "Energy": -4}  # release/breath reset
# >>> PATCH END


def safe_addstr(scr, y, x, s):
    try:
        y = int(round(y))
        x = int(round(x))
        h, w = scr.getmaxyx()
        if y < 0 or y >= h: return
        if x < 0:
            cut = int(min(len(s), -x))
            s = s[cut:]
            x = 0
        if x >= w: return
        avail = int(max(0, w - x))
        if len(s) > avail: s = s[:avail]
        if s: scr.addstr(y, x, s)
    except Exception:
        pass


# -------- role presets: BPM/swing vibe & dialogue override seed
ROLE_PRESETS = {
    "samurai": {"bpm": 96, "swing": 0.08},
    "ninja": {"bpm": 110, "swing": 0.16},
    "merchant": {"bpm": 92, "swing": 0.10},
    "geisha": {"bpm": 100, "swing": 0.14},
    "monk": {"bpm": 84, "swing": 0.04},
    "bandit": {"bpm": 104, "swing": 0.12},
    "peasant": {"bpm": 90, "swing": 0.06},
}

ROLE_MODS = {
    "samurai": {"press": +2, "shove": +2, "tug": 0, "flick": -1, "step": 0, "persona_bias": {"Stoic Resister": +0.8}},
    "ninja": {"press": 0, "shove": -1, "tug": +1, "flick": +2, "step": +2,
              "persona_bias": {"Siren Trickster": +1.0, "Bratty Chaos": +0.5}},
    "merchant": {"press": +1, "shove": 0, "tug": +2, "flick": +1, "step": 0, "persona_bias": {"Pouting Brat": +0.6}},
    "geisha": {"press": +1, "shove": -1, "tug": +2, "flick": +1, "step": +1,
               "persona_bias": {"Collapse Romantic": +0.8}},
    "monk": {"press": -1, "shove": -2, "tug": 0, "flick": 0, "step": +2, "persona_bias": {"Stoic Resister": +1.0}},
    "bandit": {"press": +1, "shove": +2, "tug": +1, "flick": 0, "step": -1, "persona_bias": {"Bratty Chaos": +0.8}},
    "peasant": {"press": 0, "shove": -1, "tug": 0, "flick": 0, "step": 0, "persona_bias": {"Pouting Brat": +0.4}},
}


# -------- rhythm pattern tracker
class PatternDetector:
    def __init__(self):
        self.last_beats = deque(maxlen=16)
        self.last_phases = deque(maxlen=24)
        self.name = "straight"

    def note(self, beat_len: float, phase_t: float):
        self.last_beats.append((beat_len, phase_t))
        self.last_phases.append(phase_t)
        self._classify()

    def _classify(self):
        if not self.last_beats: return
        swings = [abs(0.5 - t) * 2.0 for (_, t) in self.last_beats]
        avg_off = sum(swings) / len(swings)
        phases = list(self.last_phases)
        early = sum(1 for p in phases if p < 0.33)
        middle = sum(1 for p in phases if 0.33 <= p < 0.66)
        late = sum(1 for p in phases if p >= 0.66)
        waltzish = (abs(early - middle) <= 2 and abs(middle - late) <= 2 and len(phases) >= 9)
        if early > late + 3 and early > middle + 2:
            pat = "clave32"
        elif late > early + 3 and late > middle + 2:
            pat = "clave23"
        elif waltzish:
            pat = "waltz"
        else:
            pat = "swing" if avg_off > 0.35 else "straight"
        self.name = pat


# -------- sprites
def ogre_helmet(): return "/^^^^^\\"


def ogre_brow():   return "</;:;:\\>"


def ogre_tail(crest_frames, crest_spike):
    spike = int(crest_spike) if crest_frames > 0 else 0
    base = "-" * int(4 + spike)
    return base + "==>"


OPP_HEAD_PREFIX = "   o'*'.,'*'o________ "

OGRE_FACES = {
    "calm": ["(o.o)", "(-.-)", "(·_·)", "( . .)", "(=_=)", "(＾_＾)"],
    "focus": ["(x.x)", "(¬.¬)", "(□.□)", "(>.<)", "(•̀_•́)"],
    "hype": ["(O.O)", "(^.^)", "(°o°)", "(•̀ᴗ•́)", "(ﾉ^_^)ﾉ"],
    "sync": ["(♥.♥)", "(^_^)", "(✧.✧)", "(•‿•)", "(｡♥‿♥｡)"],
    "shock": ["(x.o)", "(o_x)", "(⊙.⊙)", "(๑•́ _ •̀๑)", "(O_O;)"],
    "drool": ["(^q^)", "(ᵕ﹃ ᵕ)", "(º﹃º)", "(๑˃̵ᴗ˂̵)", "(｡´ڡ`｡)"],
    "smug": ["(ʘ‿ʘ)", "(￣ー￣)", "( ͡° ͜ʖ ͡°)", "(￣▽￣)"]
}
OPP_FACES = {
    "smug": ["( ͡°_͡°)", "(^‿^)", "(￣▽￣)", "(•̀‿•́)", "(˘◡˘)"],
    "brat": ["(¬//¬)", "(^//^)", "(>///<)", "(˵¯͒〰¯͒˵)", "(๑•﹏•)"],
    "alert": ["(o.O)", "(-_-)", "(•_•)", "(¬_¬)", "(º_º)"],
    "flow": ["(n_n)", "(^_^)", "(^.^)", "(˘◡˘)", "(づ｡◕‿‿◕｡)ã¥"],
    "surge": ["(O_O)", "(^O^)", "(⊙o⊙)", "(•O•)", "(ง •̀_•́)ง"],
    "wobble": ["(@_@)", "(x_X)", "(◎_◎)", "(~_~)", "(ಠ_ಠ)"],
    "heart": ["(♥.♥)", "(♡.♡)", "(Ë¶Ë˜ ³˘)♡", "(❣️_❣️)", "(｡♥‿♥｡)"],
    "freeze": ["(-_-)", "(= _=)", "(…_…)", "(._.)", "(￣^￣)"],
    "limp": ["(._.)", "(x_x)", "(;_;)", "(._.;)", "(；一_ä¸€)"],
}


# -------- feature vector & events
@dataclass
class FeatureVector:
    tempo_mean: float = 0.5
    tempo_var: float = 0.0
    sync_offset: float = 0.3
    burst_forward_bias: float = 0.5
    swing_level: float = 0.12
    feint_density: float = 0.0
    heartbeat_density: float = 0.0
    ghost_density: float = 0.0
    jitter_level: float = 0.0
    intent_pressure: float = 0.33
    intent_tease: float = 0.33
    intent_care: float = 0.33
    spotlight: float = 0.0
    humility: float = 0.0
    denial: float = 0.0
    lateral_bias: float = 0.5
    crest_armed: float = 0.0
    pattern: str = "straight"


class EventBus:
    def __init__(self, on_event=None):
        self.on_event = on_event
        self.last_burst_t = None
        self.tempos = deque(maxlen=32)
        self.offsets = deque(maxlen=32)
        self.feints = deque(maxlen=64)
        self.heartbeats = deque(maxlen=64)
        self.ghosts = deque(maxlen=64)
        self.jitter_decay = 0.0
        self.lateral_bias = 0.5
        self.crest_armed = 0.0
        self.intent_p = 0.33
        self.intent_t = 0.33
        self.intent_c = 0.33
        self.spotlight = 0.0
        self.humility = 0.0
        self.denial = 0.0
        self.early_hist = deque(maxlen=16)
        self.pattern = "straight"
        self.events_log = []

    def emit(self, t, typ, **payload):
        evt = {"t": t, "type": typ}
        evt.update(payload)
        self.events_log.append(evt)
        if self.on_event:
            try:
                self.on_event(evt)
            except Exception:
                pass

    def emit_burst(self, direction, phase):
        now = time.perf_counter()
        if self.last_burst_t is not None:
            dt = max(0.01, now - self.last_burst_t)
            self.tempos.append(dt)
        self.last_burst_t = now
        off = abs(0.5 - (phase % 1.0)) * 2.0
        self.offsets.append(off)
        self.emit(now, "burst", direction=direction, phase=phase)

    def emit_feint(self):
        self.feints.append(time.perf_counter())
        self.emit(time.perf_counter(), "feint")

    def emit_ghost(self):
        self.ghosts.append(time.perf_counter())
        self.emit(time.perf_counter(), "ghost")

    def emit_heartbeat(self):
        self.heartbeats.append(time.perf_counter())
        self.emit(time.perf_counter(), "heartbeat")

    def emit_jitter(self):
        self.jitter_decay = 1.0
        self.emit(time.perf_counter(), "jitter")

    def set_intent(self, p=None, t=None, c=None):
        if p is not None: self.intent_p = clamp(p, 0, 1)
        if t is not None: self.intent_t = clamp(t, 0, 1)
        if c is not None: self.intent_c = clamp(c, 0, 1)
        self.emit(time.perf_counter(), "intent", pressure=self.intent_p, tease=self.intent_t, care=self.intent_c)

    def note_early(self, happened: bool):
        self.early_hist.append(1 if happened else 0)

    def tick(self, dt, swing, pattern_name):
        if self.jitter_decay > 0: self.jitter_decay = max(0.0, self.jitter_decay - dt * 0.7)
        d = dt * 0.5
        self.spotlight = max(0.0, self.spotlight - d)
        self.humility = max(0.0, self.humility - d)
        self.denial = max(0.0, self.denial - d)
        self.pattern = pattern_name
        f = FeatureVector()
        if self.tempos:
            mean = sum(self.tempos) / len(self.tempos)
            var = sum((x - mean) ** 2 for x in self.tempos) / len(self.tempos)
            f.tempo_mean = mean
            f.tempo_var = var
        if self.offsets: f.sync_offset = sum(self.offsets) / len(self.offsets)
        f.burst_forward_bias = self.lateral_bias
        f.swing_level = swing
        now = time.perf_counter()

        def density(buf, horizon=4.0):
            return sum(1 for t in buf if now - t < horizon) / horizon

        f.feint_density = density(self.feints)
        f.heartbeat_density = density(self.heartbeats)
        f.ghost_density = density(self.ghosts)
        f.jitter_level = self.jitter_decay
        f.intent_pressure = self.intent_p
        f.intent_tease = self.intent_t
        f.intent_care = self.intent_c
        f.spotlight = self.spotlight
        f.humility = self.humility
        f.denial = self.denial
        f.lateral_bias = self.lateral_bias
        f.crest_armed = self.crest_armed
        f.pattern = self.pattern
        return f


# -------- personas
@dataclass
class Persona:
    name: str
    inertia: float
    dwell_beats: int
    w_groove: float
    w_syncop: float
    w_fakeout: float
    w_pressure: float
    w_congruence: float
    w_safety: float
    face_bias: dict
    stock: list


PERSONAS = [
    Persona("Bratty Chaos", 0.65, 4, +0.20, +0.55, +0.45, +0.35, -0.15, -0.20,
            {"calm": 0.6, "alert": 0.9, "flow": 0.4, "surge": 0.8, "wobble": 1.0},
            ["Pfft—keep up.", "Heh. Predictable?", "You wish.", "Cute try.", "I’m not flustered.", "Stop staring.",
             "Almost.", "Nope. (…maybe)"]),
    Persona("Pouting Brat", 0.70, 4, +0.45, +0.15, +0.20, +0.25, +0.15, +0.45,
            {"calm": 0.9, "alert": 0.5, "flow": 0.8, "surge": 0.6, "wobble": 0.4},
            ["H-hey… slower…", "Don’t let go.", "Fine—but softer.", "Mean. (…okay)", "Better.", "Breathe with me.",
             "Promise?"]),
    Persona("Siren Trickster", 0.60, 3, +0.35, +0.35, +0.55, +0.10, -0.10, -0.10,
            {"calm": 0.5, "alert": 0.9, "flow": 0.7, "surge": 0.9, "wobble": 0.6},
            ["Oh? You noticed?", "Keep chasing.", "Flip it.", "Nearly caught me.", "Pretend you didn’t.", "Gamble it.",
             "Again—slower."]),
    Persona("Stoic Resister", 0.80, 6, +0.25, -0.20, -0.10, -0.05, +0.50, +0.15,
            {"calm": 1.0, "alert": 0.6, "flow": 0.7, "surge": 0.3, "wobble": 0.2},
            ["…mm.", "Not impressed.", "Cleaner.", "Hold the line.", "Pace yourself.", "Keep center.",
             "Almost symmetric."]),
    Persona("Collapse Romantic", 0.85, 8, +0.55, -0.15, +0.10, +0.20, +0.40, +0.60,
            {"calm": 0.8, "alert": 0.4, "flow": 1.0, "surge": 0.7, "wobble": 0.3},
            ["…Okay. I trust you.", "Stay. Breathe.", "Perfect.", "Yes—like that.", "Shh—just feel.",
             "You’re doing fine.", "Right here."]),
]


@dataclass
class Signals:
    groove: float
    syncop: float
    fakeout: float
    pressure: float
    congruence: float
    safety: float
    pattern: str


@dataclass
class PersonaManager:
    current_idx: int = 0
    dwell_counter: int = 0
    lock_beats: int = 0
    persona_bias: dict = field(default_factory=dict)

    def current(self) -> Persona:
        return PERSONAS[self.current_idx]

    def lock(self, beats: int):
        self.lock_beats = max(self.lock_beats, beats)

    def score_persona(self, p: Persona, sig: Signals) -> float:
        swing_bonus = +0.12 if (sig.pattern in ("swing", "clave32", "clave23")) else 0.0
        base = (p.w_groove * sig.groove + p.w_syncop * sig.syncop + p.w_fakeout * sig.fakeout +
                p.w_pressure * sig.pressure + p.w_congruence * sig.congruence + p.w_safety * sig.safety + swing_bonus)
        return base + self.persona_bias.get(p.name, 0.0)

    def update(self, beat_pulse: bool, sig: Signals):
        if not beat_pulse: return
        if self.lock_beats > 0:
            self.lock_beats -= 1
            return
        scores = [self.score_persona(p, sig) for p in PERSONAS]
        scores[self.current_idx] += PERSONAS[self.current_idx].inertia * 0.25
        best_idx = max(range(len(PERSONAS)), key=lambda i: scores[i])
        if best_idx == self.current_idx:
            self.dwell_counter = 0
            return
        if scores[best_idx] - scores[self.current_idx] > 0.25:
            self.dwell_counter += 1
        else:
            self.dwell_counter = max(0, self.dwell_counter - 1)
        if self.dwell_counter >= PERSONAS[best_idx].dwell_beats:
            self.current_idx = best_idx
            self.dwell_counter = 0


# -------- particles
@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    glyph: str


class Particles:
    def __init__(self):
        self.ps = []

    def burst(self, x, y, kind="heart", n=14, speed=4.0, rng=random):
        glyphs = {"heart": ["♥", "♡", "❣"], "spark": ["*", "·", "."], "star": ["✶", "✦", "✧"], "sweat": ["'", "`", "·"],
                  "favor": ["+", "✚", "✙"]}
        G = glyphs.get(kind, ["*", "."])
        for _ in range(int(n)):
            ang = rng.random() * 2 * math.pi
            r = rng.random() * speed
            vx = math.cos(ang) * r
            vy = -abs(math.sin(ang)) * r * 0.7
            self.ps.append(Particle(x, y, vx, vy, life=0.6 + 0.8 * rng.random(), glyph=rng.choice(G)))

    def update(self, dt):
        g = 9.0
        alive = []
        for p in self.ps:
            p.life -= dt
            if p.life <= 0: continue
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.vy += g * dt * 0.2
            alive.append(p)
        self.ps = alive

    def render(self, scr, shake_x=0):
        for p in self.ps: safe_addstr(scr, p.y, p.x + shake_x, p.glyph)


# -------- typewriter dialogue with role banks & “Magnum Opus” lines
class TypeWriter:
    def __init__(self, cps=36.0):
        self.text = ""
        self.visible = 0
        self.t = 0.0
        self.cps = cps
        self.done = True

    def set(self, text):
        self.text = text
        self.visible = 0
        self.t = 0.0
        self.done = False

    def update(self, dt):
        if self.done: return
        self.t += dt * self.cps
        step = int(self.t) - self.visible
        if step > 0:
            self.visible += step
            if self.visible >= len(self.text):
                self.visible = len(self.text)
                self.done = True
        if self.visible < len(self.text) and self.visible > 0:
            ch = self.text[self.visible - 1]
            if ch in ",;": self.t -= 0.4
            if ch in ".!?": self.t -= 0.8

    def draw(self, scr, y, x, shake_x=0):
        if self.text and self.visible > 0: safe_addstr(scr, y, x + shake_x, self.text[:self.visible])


class Dialogue:
    def __init__(self, role="samurai", rng=random):
        self.enabled = True
        self.rate = 0.85
        self.tw_ogre = TypeWriter(cps=42.0)
        self.tw_opp = TypeWriter(cps=42.0)
        self.role = role
        self.rng = rng

        # Phase stingers – Jessica “Magnum Opus” (she lost at initiation; reclaiming grace w/ sly control)
        self.phase_lines = {
            "opening": [
                "Fine—count me late. Watch me arrive perfect.",
                "I know I lost the first step. I’ll make you slip on the second.",
                "Face me. I’ll blush on purpose, then make you earn it.",
                "We start how you like. We end how I decide.",
                "Breathe. Pretend I didn’t trip; I won’t."
            ],
            "mid": [
                "Tempo’s warmer now. See? I don’t have to try to win.",
                "Your pulse is telling on you. Shh—let it.",
                "I’ll borrow your balance; return it prettier.",
                "That flinch? Mine now.",
                "Stay neat. I like breaking tidy things."
            ],
            "crest": [
                "Don’t blink—I’m stealing your center in three… two…",
                "Hold still—I’m painting your gasp.",
                "We crest together; I pick the view.",
                "Smile for the transcript.",
                "There. That’s the look I wanted."
            ],
            "fatigue": [
                "Grace doesn’t tire. Only pride does.",
                "Small steps. I’ll make even those look shameless.",
                "Hush. I know where to touch the air.",
                "You can rest. I’ll keep our rhythm alive.",
                "We can lose pretty. Or win prettier."
            ],
            "encore": [
                "Encore? Then give me the last word.",
                "One more—let me sign your breath.",
                "Slow. Slower. Perfect.",
                "Now: the part you remember.",
                "Don’t move—I want the echo."
            ]
        }

        # Move tags (Ogre = player-side flavor; Opp = rival replies) – role-agnostic core
        self.ogre_lines = {
            "move_tug": ["Mine—come here.", "Closer.", "Forward.", "Stay with me."],
            "move_flick": ["Stop that.", "Cute twitch.", "I saw it.", "Behave."],
            "move_shove": ["Back you go.", "Space.", "Hold still.", "Reset."],
            "move_step": ["Catch me.", "Almost.", "Too slow.", "Missed."],
            "move_press": ["I’m here.", "Breathe with me.", "Stay close.", "Don’t flinch."],
            "parry": ["Nice catch.", "Clean parry.", "Sharp hands.", "Good ear."],
            "crest": ["Crest incoming.", "Ride it—now!", "Snap!", "Perfect."],
            "release": ["Reset the count.", "Back to one.", "Clean spill.", "We keep going."],
        }
        self.opp_lines = {
            "move_tug": ["Mine.", "Come here.", "Don’t blink.", "Closer~"],
            "move_flick": ["Tch—", "Ha!", "Try harder.", "Too neat."],
            "move_shove": ["Back!", "Oops—", "Personal space.", "Request denied."],
            "move_step": ["Missed me.", "Hm?", "Almost caught me.", "Late~"],
            "move_press": ["Fine—match me.", "Stay.", "Don’t run now.", "Bold."],
            "pain": ["Ow—hey!", "Rude.", "Mean.", "H-hey!"],
            "parry": ["Oh? You caught that.", "Okay—respect.", "Cheeky.", "Nice hands."],
            "release": ["…reset, then.", "Don’t get cocky.", "Still yours? Prove it.", "Again."]
        }

        # Role-specific overlays (additive flavor)
        self.role_bank = {
            "samurai": {
                "opening": ["Stand tall, then lean exactly where I want.", "Sword voice—keep it; I’ll tune it."],
                "crest": ["Fold your edge into mine.", "Cut clean—just the air."],
                "opp_press": ["Hold the line with me.", "Steel to rhythm, hm?"]
            },
            "ninja": {
                "opening": ["Hide, then cheat—see if I don’t catch it.", "Mask on. Now blush behind it."],
                "mid": ["Step wrong. I dare you.", "I can feel the wire tremble."],
                "opp_step": ["You thought you vanished.", "I hear your hush."]
            },
            "merchant": {
                "opening": ["Terms later. Pulse now.", "I’ll audit your breath."],
                "mid": ["Fair trade: your poise for my grin.", "Interest compounded—on your heartbeat."],
                "opp_tug": ["Collateral accepted."]
            }
        }

    def adapt_rate_for_phase(self, phase):
        self.rate = {"opening": 0.80, "mid": 0.90, "crest": 1.05, "fatigue": 0.78, "encore": 1.08}.get(phase, 0.85)
        self.tw_ogre.cps = 40.0 * self.rate
        self.tw_opp.cps = 40.0 * self.rate

    def _pick(self, arr):
        if not arr: return None
        return self.rng.choice(arr)

    def say_phase(self, phase, yx):
        if not self.enabled: return
        self.adapt_rate_for_phase(phase)
        base = self.phase_lines.get(phase, ["..."])
        overlay = self.role_bank.get(self.role, {}).get(phase, [])
        line = self._pick(base + overlay) or "..."
        y, x = yx
        self.tw_ogre.set("« " + line)
        self.tw_opp.set("")

    def say(self, side, tag, yx):
        if not self.enabled: return
        bank = self.ogre_lines if side == "ogre" else self.opp_lines
        line = self._pick(bank.get(tag, ["..."])) or "..."
        # role-tag overlays
        overlay_key = f"opp_{tag}" if side == "opp" else None
        if overlay_key:
            extra = self.role_bank.get(self.role, {}).get(overlay_key, [])
            if extra and self.rng.random() < 0.45:
                line = self._pick(extra + [line]) or line
        y, x = yx
        if side == "ogre":
            self.tw_ogre.set("« " + line)
            self.tw_opp.set("")
        else:
            self.tw_opp.set(" »" + line)
            self.tw_ogre.set("")

    def update(self, dt):
        self.tw_ogre.update(dt)
        self.tw_opp.update(dt)

    def render(self, scr, pos_ogre, pos_opp, shake_x=0):
        oy, ox = pos_ogre
        py, px = pos_opp
        self.tw_ogre.draw(scr, oy, ox, shake_x=shake_x)
        self.tw_opp.draw(scr, py, px, shake_x=shake_x)


# -------- AI move
@dataclass
class OppMove:
    kind: str
    t: float = 0.0
    tele: float = 0.18
    dur: float = 0.35
    done: bool = False
    hit: bool = False
    impact_at: float = 0.22
    pose: str = "base"


# -------- main duel
class Duel:
    CREST_FRAMES = 2
    CREST_SPIKE = 3
    BURST_TOTAL = 0.22
    SMACK_STEP_DUR = 0.18
    DOUBLETAP_B_MS = 0.25
    LONGPRESS_B_MS = 0.25
    LONGPRESS_A_MS = 0.28
    FAKEOUT_MS = 0.12

    def __init__(self, scr, opponent_role="samurai", on_event=None, npc_seed=None, persona_script=None, base_favor=0):
        self.scr = scr
        self.role = opponent_role
        self.on_event = on_event
        self.persona_script = persona_script or {}
        self.rng = random.Random(npc_seed) if npc_seed is not None else random

        h, w = scr.getmaxyx()
        self.h, self.w = h, w
        self.left, self.right = 2, w - 2
        self.base_y = h - 8

        # rhythm presets per role
        preset = ROLE_PRESETS.get(self.role, {"bpm": 92, "swing": 0.10})
        self.bpm = preset["bpm"]
        self.swing = preset["swing"]
        self.beat_idx = 0
        self.t_in = 0.0

        # phases
        self.clock = 0.0
        self.phase = "opening"
        self.phase_since = 0.0

        # pattern
        self.pattern = PatternDetector()

        # positions & motion
        self.ogre_x = 4.0
        self.max_adv = 6.0
        self.opp_cx = w * 0.56
        self.desired_gap = 4
        self.min_gap = 2
        self.k_spring = 9.0
        self.k_damp = 0.90
        self.gap_vx = 0.0

        # stats
        self.ogre = {"Pulse": self.rng.uniform(25, 45), "Energy": self.rng.uniform(55, 75),
                     "Poise": self.rng.uniform(35, 55)}
        self.opp = {"Pulse": self.rng.uniform(15, 35), "Energy": self.rng.uniform(52, 72),
                    "Nerve": self.rng.uniform(42, 65)}
        self.combo = 0.0
        self.combo_t = 0.0

        # >>> PATCH START: baselines, locks, flags
        # Homeostasis baselines the stats drift toward (per side)
        self.ogre_base = {"Pulse": 45.0, "Energy": 60.0, "Poise": 50.0}
        self.opp_base = {"Pulse": 30.0, "Energy": 60.0, "Nerve": 55.0}

        # Decay rates toward baseline (units/sec toward target)
        self.homeo_rate = {"Pulse": 6.0, "Energy": 8.0, "Poise": 7.0,
                           "opp_Pulse": 5.5, "opp_Energy": 7.5, "opp_Nerve": 6.0}

        # Fatigue: when Pulse>90, Energy drains extra and rhythm bonuses dampen
        self.fatigue_on = False

        # Locks: heavy smack lock if Energy low; parry effectiveness scales with Poise
        self.lock_heavy = False
        self.lock_rhythm = False
        self.lock_tooltip = ""  # quick HUD hint
        # >>> PATCH END

        # favor system
        self.favor = int(base_favor)
        self.favor_pops = []  # [(y, x, text, ttl)]

        # systems
        self.bus = EventBus(on_event=on_event)
        self.persona = PersonaManager()
        self.persona.persona_bias = ROLE_MODS.get(self.role, {}).get("persona_bias", {})
        # deterministic persona start
        if npc_seed is not None:
            self.persona.current_idx = self.rng.randrange(len(PERSONAS))

        self.dialogue = Dialogue(role=self.role, rng=self.rng)
        self.pfx = Particles()

        # action state
        self.rhythm_active = False
        self.rhythm_t = 0.0
        self.rhythm_dir = +1
        self.extra_dx = 0.0
        self.crest_frames = 0
        self.crest_armed = False
        self.smack_active = False
        self.smack_step = 0
        self.smack_t = 0.0
        self.smack_mode = "normal"
        self.smack_early = False
        self.pred_mem = deque(maxlen=8)
        self.bait_bias = 0.3
        self.swing_val = 0.0
        self.jiggle_t = 0.0
        self.jiggle_amp = 0.0
        self.recoil_t = 0.0
        self.opp_state = "normal"
        self.opp_state_t = 0.0
        self.hop_phase = 0.0

        # AI move
        self.move: OppMove | None = None
        self.move_cd = 0.0

        # UX
        self.toast_msg = ""
        self.toast_t = 0.0
        self.subtitle_only = False
        # HUD mode: 'classic' = old three bars (dynamic); 'advanced' = rich tech HUD; 'minimal' = almost nothing
        self.hud_mode = 'classic'


        # slomo/parry
        self.slowmo_t = 0.0
        self.slowmo_scale = 0.4
        self.parry_flash_t = 0.0

        # screen shake
        self.shake_t = 0.0
        self.shake_amp = 0.0
        self.shake_freq = 38.0

        # input times
        self.since_burst = 0.5
        self.last_b = 0.0
        self.last_a = 0.0
        self.b_down = None
        self.a_down = None

        # event mirror
        self.events = []
        
        # ========== UPGRADED FEATURES ==========
        # Dialogue queue (separate from existing dialogue system)
        self.dialogue_queue = DialogueQueue()
        
        # Stink particles
        self.stink_particles = [] if STINK_AVAILABLE else None
        self.stink_color_map = {}  # Will be set externally
        
        # Tether state
        self.tether_tension = 0.5  # 0.0 = slack, 1.0 = taut
        
        # Sync feedback
        self.sync_flash = 0.0
        self.sync_quality = 0.0
        # ========================================

        self._emit("phase", phase="opening")
        self.dialogue.say_phase("opening", (self.base_y - 6, 2))

    # ---- emit helper
    def _emit(self, typ, **payload):
        now = time.perf_counter()
        evt = {"t": now, "type": typ}
        evt.update(payload)
        self.events.append(evt)
        self.bus.emit(now, typ, **payload)
        # favor passthrough
        if typ == "favor_delta" and self.on_event:
            try:
                self.on_event(evt)
            except Exception:
                pass

    # ---- rhythm
    def beat_len(self, n):
        base = 60.0 / max(1, self.bpm)
        return base * (1.0 + self.swing) if n % 2 else base * (1.0 - self.swing)

    def update_rhythm(self, dt):
        L = self.beat_len(self.beat_idx)
        self.t_in += dt
        while self.t_in >= L:
            self.t_in -= L
            self.beat_idx = (self.beat_idx + 1) % 8
            self.update_persona_on_beat()
            self.try_schedule_move()

    def rhythm_quality(self):
        L = self.beat_len(self.beat_idx)
        t = (self.t_in / max(1e-3, L)) % 1.0
        return clamp(1.0 - abs(0.5 - t) * 2.0, 0.0, 1.0), t

    # ---- phases
    def update_phase(self, dt):
        self.clock += dt
        self.phase_since += dt
        if self.clock < 12.0:
            nextp = "opening"
        elif self.combo < 0.35 and self.clock < 24.0:
            nextp = "mid"
        elif self.combo >= 0.35 and self.clock < 36.0:
            nextp = "crest"
        elif self.clock < 48.0:
            nextp = "fatigue"
        else:
            nextp = "encore"
        if nextp != self.phase:
            self.phase = nextp
            self.phase_since = 0.0
            # persona_script override
            if isinstance(self.persona_script, dict):
                name = self.persona_script.get(self.phase)
                if name:
                    for i, p in enumerate(PERSONAS):
                        if p.name == name:
                            self.persona.current_idx = i
                            break
            # vibe drift
            if self.phase == "opening": self.bpm = int(clamp(self.bpm * 0.98, 70, 140))
            if self.phase == "mid":     self.bpm = int(clamp(self.bpm * 1.04, 70, 140))
            if self.phase == "crest":   self.bpm = int(clamp(self.bpm * 1.06, 70, 150))
            if self.phase == "fatigue": self.bpm = int(clamp(self.bpm * 0.95, 60, 150))
            if self.phase == "encore":  self.bpm = int(clamp(self.bpm * 1.05, 70, 155))
            self.dialogue.say_phase(self.phase, (self.base_y - 6, 2))
            self._emit("phase", phase=self.phase)

    # ---- inputs
    def press_burst(self, flavor="normal"):
        self.rhythm_active = True
        self.rhythm_t = 0.0
        self.rhythm_dir *= -1
        if self.rhythm_dir > 0:
            self.bpm = clamp(self.bpm * (1.07 if flavor == "double" else 1.05), 40, 180)
            self.swing = clamp(self.swing * (0.92 if flavor == "long" else 0.95), 0.0, 0.24)
        else:
            self.bpm = clamp(self.bpm * (0.93 if flavor == "long" else 0.95), 40, 180)
            self.swing = clamp(self.swing * 1.05 + 0.005, 0.0, 0.24)
        rq, phase = self.rhythm_quality()
        self.bus.emit_burst("forward" if self.rhythm_dir > 0 else "back", phase)
        self.pattern.note(self.beat_len(self.beat_idx), phase)
        self.since_burst = 0.0
        self.combo = min(1.0, self.combo + 0.18)
        self.combo_t = 0.0
        if self.smack_active and not self.smack_early:
            expected = (self.rng.random() < self.bait_bias)
            self.smack_early = True
            self.pred_mem.append(expected)
            rate = sum(1 for b in self.pred_mem if b) / max(1, len(self.pred_mem))
            self.bait_bias = clamp(0.25 + 0.5 * rate, 0.1, 0.9)
            self.bus.note_early(True)
            self.toast("[early]", 0.5)
            self.summon_particles_dual("spark", 0.6)
        # >>> PATCH START: costs on burst & rhythm lock
        if self.lock_rhythm:
            self.toast("rhythm dampened (fatigue)", 0.6)
        else:
            for k, c in Costs.BURST.items():
                self.ogre[k] = clamp(self.ogre.get(k, 0) + c, 0, 120 if k == "Pulse" else 100)
        # >>> PATCH END

    def press_smack(self, mode="normal"):
        self.smack_active = True
        self.smack_step = 0
        self.smack_t = 0.0
        self.smack_mode = mode
        self.smack_early = False
        self.jiggle_t = 0.6
        self.jiggle_amp = 1.1 if mode == "soft" else (1.6 if mode == "heavy" else 1.3)
        self.combo = min(1.0, self.combo + (0.12 if mode == "soft" else 0.18))
        self.combo_t = 0.0
        # contextual line: she reclaims dignity by guiding pressure
        self.last_dialogue = ("ogre", "move_press") if mode == "soft" else ("ogre", "crest")
        # >>> PATCH START: costs on smack
        if mode == "soft":
            for k, c in Costs.A_LIGHT.items():
                self.ogre[k] = clamp(self.ogre.get(k, 0) + c, 0, 120 if k == "Pulse" else 100)
        elif mode == "heavy":
            # heavy requires Energy >= 16 and no lock
            if self.ogre["Energy"] < 16 or self.lock_heavy:
                self.smack_mode = "normal"
                self.lock_tooltip = "HARD locked (Energy)"
                self.toast(self.lock_tooltip, 0.7)
                for k, c in Costs.A_LIGHT.items():
                    self.ogre[k] = clamp(self.ogre.get(k, 0) + c, 0, 120 if k == "Pulse" else 100)
            else:
                for k, c in Costs.A_HEAVY.items():
                    self.ogre[k] = clamp(self.ogre.get(k, 0) + c, 0, 120 if k == "Pulse" else 100)
        else:  # normal
            if self.ogre["Energy"] < 8:
                self.smack_mode = "soft"
            for k, c in Costs.A_LIGHT.items():
                self.ogre[k] = clamp(self.ogre.get(k, 0) + c, 0, 120 if k == "Pulse" else 100)
        # >>> PATCH END

    def trigger_release_both(self):
        self.summon_particles_dual("heart", 1.0)
        self.toast("[release]", 0.7)
        self.ogre["Pulse"] = clamp(self.ogre["Pulse"] + 4, 0, 120)
        self.opp["Pulse"] = clamp(self.opp["Pulse"] + 4, 0, 120)
        self.ogre["Energy"] = clamp(self.ogre["Energy"] + 3, 0, 100)
        self.opp["Energy"] = clamp(self.opp["Energy"] + 3, 0, 100)
        self.last_dialogue = ("opp", "release")
        self.persona.lock(4)
        self._emit("release", combo=self.combo)
        # favor hook: bigger in encore
        delta = 10 if self.phase == "encore" else 4
        self.add_favor(delta, reason="release")
        # >>> PATCH START: breath/reset relief
        for k, c in Costs.HEART.items():
            if k in self.ogre:
                self.ogre[k] = clamp(self.ogre[k] + c, 0, 120 if k == "Pulse" else 100)
            if k == "Pulse" and "Pulse" in self.opp:
                self.opp["Pulse"] = clamp(self.opp["Pulse"] + c * 0.7, 0, 120)
        # >>> PATCH END
        
        # UPGRADED: Big stink cloud on climax
        if STINK_AVAILABLE and self.stink_particles is not None:
            self.emit_stink_cloud(intensity=5)
        self.dialogue_queue.say("climax")
    
    # ========== UPGRADED ACTION METHODS ==========
    
    def press_thrust(self):
        """THRUST (W) - Forward, aggressive, high risk/reward"""
        q, _ = self.rhythm_quality()
        on_beat = q > 0.7
        
        if on_beat:
            # Good thrust - powerful
            self.ogre["Energy"] -= 12
            self.opp["Nerve"] = clamp(self.opp["Nerve"] - 10, 0, 100)
            self.add_favor(3, reason="thrust")
            self.dialogue_queue.say("thrust_good")
            self.sync_flash = 1.0
            self.sync_quality = q
            self.tether_tension = min(1.0, self.tether_tension + 0.2)
        else:
            # Bad thrust - penalty + embarrassment stink!
            self.opp["Nerve"] = clamp(self.opp["Nerve"] + 5, 0, 100)
            self.dialogue_queue.say("thrust_bad")
            if STINK_AVAILABLE and self.stink_particles is not None:
                self.emit_stink_cloud(intensity=2)
            self.tether_tension = max(0.0, self.tether_tension - 0.1)
        
        # Visual feedback
        self.jiggle_t = 0.8
        self.jiggle_amp = 2.0 if on_beat else 1.0
    
    def press_spank(self):
        """SPANK (A) - Rhythmic, playful (renamed from smack)"""
        # Use existing smack logic
        self.press_smack(mode="normal")
        self.dialogue_queue.say("spank_react")
    
    def press_pull(self):
        """PULL (S) - Control, dominance"""
        self.ogre["Energy"] -= 8
        self.opp["Nerve"] = clamp(self.opp["Nerve"] - 8, 0, 100)
        self.add_favor(2, reason="pull")
        self.dialogue_queue.say("pull_react")
        
        # Visual: tether tightens
        self.tether_tension = min(1.0, self.tether_tension + 0.3)
        self.jiggle_t = 0.5
        self.jiggle_amp = 1.2
    
    def press_caress(self):
        """CARESS (D) - Gentle, responsive"""
        self.ogre["Energy"] -= 4
        self.opp["Nerve"] = clamp(self.opp["Nerve"] - 5, 0, 100)
        self.add_favor(1, reason="caress")
        self.dialogue_queue.say("caress_react")
        
        # Visual: soft motion
        self.jiggle_t = 0.4
        self.jiggle_amp = 0.8
        self.tether_tension = max(0.0, self.tether_tension - 0.1)
    
    # ========== STINK PARTICLE METHODS ==========
    
    def emit_stink_cloud(self, intensity: int = 1):
        """Emit stink cloud during duel as reaction"""
        if not STINK_AVAILABLE or self.stink_particles is None:
            return
        
        # Spawn point: above geisha
        spawn_x = self.opp_cx
        spawn_y = self.base_y - 3
        
        count = intensity * 5
        
        for _ in range(count):
            angle = random.uniform(-45, 45)
            speed = random.uniform(1.0, 2.0)
            
            particle = StinkParticle(
                x=spawn_x + random.uniform(-2, 2),
                y=spawn_y,
                vx=math.sin(math.radians(angle)) * speed,
                vy=-abs(math.cos(math.radians(angle))) * speed,
                life=random.uniform(0.5, 0.8),
                glyph=random.choice(['≈', '~', '°'])
            )
            
            self.stink_particles.append(particle)
    
    def update_stink_particles(self, dt):
        """Update stink particles"""
        if not STINK_AVAILABLE or self.stink_particles is None:
            return
        
        for p in self.stink_particles:
            p.update(dt, self.opp_cx)
        
        # Remove dead
        self.stink_particles = [p for p in self.stink_particles if p.life > 0]
    
    def render_stink_particles(self, shake_x):
        """Render stink particles"""
        if not STINK_AVAILABLE or self.stink_particles is None:
            return
        
        for p in self.stink_particles:
            color = self.stink_color_map.get(p.get_color_name(), 0)
            try:
                self.scr.addch(int(p.y), int(p.x) + shake_x, p.glyph, color)
            except:
                pass
    
    # ==========================================

    # ---- AI schedule
    def try_schedule_move(self):
        if self.move or self.move_cd > 0: return
        base_p = {"opening": 0.25, "mid": 0.40, "crest": 0.55, "fatigue": 0.30, "encore": 0.60}[self.phase]
        name = self.persona.current().name
        if name == "Bratty Chaos": base_p += 0.08
        if name == "Siren Trickster": base_p += 0.07
        if self.rng.random() > base_p: return

        pat = self.pattern.name
        choices = []

        def add(kind, w):
            choices.append((kind, w))

        if pat in ("swing", "waltz"):
            add("press", 3); add("tug", 3); add("step", 2); add("flick", 2); add("shove", 2)
        elif pat == "clave32":
            add("tug", 4); add("flick", 3); add("step", 2); add("shove", 2); add("press", 2)
        elif pat == "clave23":
            add("press", 4); add("shove", 3); add("step", 2); add("flick", 2); add("tug", 2)
        else:
            add("shove", 3); add("press", 3); add("step", 2); add("flick", 2); add("tug", 2)

        rmod = ROLE_MODS.get(self.role, {})
        choices = [(k, max(0, w + rmod.get(k, 0))) for (k, w) in choices]

        if self.phase == "fatigue":
            choices = [(k, w - 1 if k == "shove" else w) for (k, w) in choices]

        total = sum(max(1, w) for _, w in choices)
        r = self.rng.randint(1, total)
        acc = 0
        chosen = "press"
        for k, w in choices:
            acc += max(1, w)
            if r <= acc: chosen = k; break

        m = OppMove(kind=chosen)
        m.pose = "press" if chosen in ("press", "tug") else ("step" if chosen == "step" else "lean")
        if chosen == "flick": m.tele = 0.12; m.dur = 0.28; m.impact_at = 0.17
        if chosen == "shove": m.tele = 0.18; m.dur = 0.34; m.impact_at = 0.21
        if chosen == "tug":  m.tele = 0.18; m.dur = 0.33; m.impact_at = 0.19
        if chosen == "step": m.tele = 0.16; m.dur = 0.30; m.impact_at = 0.00
        if chosen == "press": m.tele = 0.14; m.dur = 0.36; m.impact_at = 0.22
        self.move = m

    # ---- motion
    def update_motion(self, dt):
        if self.slowmo_t > 0:
            dt *= self.slowmo_scale
            self.slowmo_t = max(0.0, self.slowmo_t - dt)
        if self.parry_flash_t > 0:
            self.parry_flash_t = max(0.0, self.parry_flash_t - dt)

        if self.shake_t > 0:
            self.shake_t = max(0.0, self.shake_t - dt * 1.5)
            if self.shake_t <= 0: self.shake_amp = 0.0

        self.combo_t += dt
        self.combo = max(0.0, self.combo - dt * 0.07)
        rq, phase = self.rhythm_quality()
        self.swing_val = math.sin(phase * math.tau) * (0.6 + 0.4 * math.sin(phase * math.tau) ** 2)

        push = 0.28
        if self.recoil_t > 0:
            push -= 1.6 * min(1.0, self.recoil_t)
            self.recoil_t = max(0.0, self.recoil_t - dt * 1.4)
        self.ogre_x = clamp(self.ogre_x + push * dt * 7.0, 2.0, 2.0 + self.max_adv)

        crest_now = False
        if self.rhythm_active:
            self.rhythm_t += dt
            u = clamp(self.rhythm_t / self.BURST_TOTAL, 0, 1)
            if u < 0.33:
                disp = -1.0 * ease_out(u / 0.33)
            elif u < 0.66:
                disp = +1.6 * ease_in((u - 0.33) / 0.33)
                if not self.crest_armed:
                    self.crest_armed = True
                    crest_now = True
            else:
                self.rhythm_active = False
                disp = 0.0
                self.crest_armed = False
            self.extra_dx = disp * self.rhythm_dir
        else:
            self.extra_dx = 0.0

        if crest_now:
            self.crest_frames = self.CREST_FRAMES
            self.toast("crest!", 0.25)
            self.bus.crest_armed = 1.0
            self.summon_particles(side="opp", kind="spark", power=0.7)
            self.last_dialogue = ("ogre", "crest")
            qual, _ = self.rhythm_quality()
            if qual > 0.92: self.slowmo_t = 0.28

        smack_disp = 0.0
        if self.smack_active:
            self.smack_t += dt
            step_len = self.SMACK_STEP_DUR * (1.2 if self.smack_mode == "soft" else 1.0)
            step = int(self.smack_t // step_len)
            if self.smack_early:
                step = max(step, 3)
                self.smack_active = False
                self.recoil_t = 0.24
            else:
                if step <= 4:
                    self.smack_step = step
                else:
                    self.smack_active = False
                    self.recoil_t = 0.28
            if self.smack_step in (0, 1, 2):
                smack_disp = -1.2 if self.smack_mode != "soft" else -0.9
            elif self.smack_step == 3:
                smack_disp = +2.0 if self.smack_mode != "soft" else +1.6
                self.summon_particles(side="opp", kind="star", power=0.8)
            elif self.smack_step == 4:
                smack_disp = -0.6

        self.extra_dx += smack_disp

        # Spring spacing
        freeze_factor = 0.0 if self.opp_state == "freeze" else 1.0
        limp_damp = 0.6 if self.opp_state == "limp" else 1.0
        ogre_right = self.ogre_x + self.ogre_body_width()
        opp_left = self.opp_cx - self.opp_width() / 2.0
        target_left = ogre_right + self.desired_gap
        err = target_left - opp_left
        acc = self.k_spring * err * freeze_factor
        self.gap_vx = (self.gap_vx + acc * dt) * (self.k_damp * limp_damp)
        self.opp_cx += self.gap_vx * dt

        if (self.opp_cx - self.opp_width() / 2.0) < (ogre_right + self.min_gap):
            self.opp_cx = ogre_right + self.min_gap + self.opp_width() / 2.0
            self.gap_vx = 0.0
        if self.opp_cx + self.opp_width() / 2.0 > self.right:
            self.opp_cx = self.right - self.opp_width() / 2.0
            self.gap_vx = 0.0

        if self.jiggle_t > 0:
            self.jiggle_t = max(0.0, self.jiggle_t - dt)
        else:
            self.jiggle_amp = 0.5 * abs(self.swing_val)

        if self.opp_state in ("join", "heart_hop"):
            bias = self.hop_bias()
            self.hop_phase += dt * (3.0 + bias + (0.5 if self.slowmo_t > 0 else 0.0))

        now = time.perf_counter()
        if hasattr(self, "b_down") and self.b_down and (now - self.b_down) >= self.LONGPRESS_B_MS:
            self.CREST_SPIKE = 4
            self.recoil_t = max(self.recoil_t, 0.12)
            self.b_down = None
        if hasattr(self, "a_down") and self.a_down and (now - self.a_down) >= self.LONGPRESS_A_MS:
            self.smack_mode = "heavy"
            self.jiggle_amp = max(self.jiggle_amp, 1.6)
            self.a_down = None

    # ---- stats & AI resolve
    # >>> PATCH START: governed meters
    def update_stats(self, dt):
        # 1) Rhythm signal
        rq, phase = self.rhythm_quality()
        groove = rq
        combo_boost = 0.12 * self.combo

        # 2) Decay toward baseline (homeostasis)
        self.ogre["Pulse"] = toward(self.ogre["Pulse"], self.ogre_base["Pulse"], self.homeo_rate["Pulse"], dt)
        self.ogre["Energy"] = toward(self.ogre["Energy"], self.ogre_base["Energy"], self.homeo_rate["Energy"], dt)
        self.ogre["Poise"] = toward(self.ogre["Poise"], self.ogre_base["Poise"], self.homeo_rate["Poise"], dt)

        self.opp["Pulse"] = toward(self.opp["Pulse"], self.opp_base["Pulse"], self.homeo_rate["opp_Pulse"], dt)
        self.opp["Energy"] = toward(self.opp["Energy"], self.opp_base["Energy"], self.homeo_rate["opp_Energy"], dt)
        self.opp["Nerve"] = toward(self.opp["Nerve"], self.opp_base["Nerve"], self.homeo_rate["opp_Nerve"], dt)

        # 3) Active contributions (positive & negative)
        # Mild drift from groove; now smaller and phase-aware
        self.ogre["Energy"] += (1.2 * groove + 0.35 * abs(self.swing_val) + 0.6 * combo_boost) * dt * 2.0
        self.ogre["Poise"] += (0.5 * groove + 0.15 * combo_boost) * dt * 2.2
        self.ogre["Pulse"] += (0.50 * groove + 0.12 * abs(self.rhythm_dir) + 0.10 * self.combo) * dt * 2.4

        self.opp["Energy"] += (1.0 * groove + 0.32 * abs(self.swing_val)) * dt * 1.8
        self.opp["Nerve"] += (0.40 * groove) * dt * 1.9
        self.opp["Pulse"] += (0.45 * groove + 0.18 * abs(self.swing_val)) * dt * 2.0

        # 4) Fatigue/overheat effects
        self.fatigue_on = (self.ogre["Pulse"] >= 90)
        self.lock_heavy = (self.ogre["Energy"] < 16)
        self.lock_rhythm = self.fatigue_on

        if self.fatigue_on:
            # extra Energy leak and rhythm dampening
            self.ogre["Energy"] = max(0.0, self.ogre["Energy"] - dt * 4.5)
            self.bpm = int(clamp(self.bpm * 0.998, 60, 155))
            self.swing = clamp(self.swing * 0.98, 0.0, 0.24)

        # Cap ranges
        for k, mx in [("Pulse", 120), ("Energy", 100), ("Poise", 100)]:
            self.ogre[k] = clamp(self.ogre[k], 0, mx)
        self.opp["Pulse"] = clamp(self.opp["Pulse"], 0, 120)
        self.opp["Energy"] = clamp(self.opp["Energy"], 0, 100)
        self.opp["Nerve"] = clamp(self.opp["Nerve"], 0, 100)

        # Keep your existing move/AI resolve, dialogue, particles, etc.
        self.update_move(dt)

        if self.crest_frames > 0: self.crest_frames -= 1
        feat = self.bus.tick(dt, self.swing, self.pattern.name)

        if self.opp_state != "normal":
            self.opp_state_t += dt
            if self.opp_state == "freeze" and self.opp_state_t > 1.2: self.opp_state = "normal"
            if self.opp_state == "limp" and self.opp_state_t > 1.6: self.opp_state = "normal"
            if self.opp_state == "join" and self.opp_state_t > 3.0:
                self.opp_state = "heart_hop"
                self.opp_state_t = 0.0

        if self.smack_step == 3 or self.smack_early:
            if getattr(self, "_resolved_once", False) is False:
                self._resolved_once = True
                self.resolve_gambit()
        else:
            self._resolved_once = False

        # Auto release synergy (slightly stricter with new economy)
        if self.ogre["Pulse"] > 94 and self.opp["Pulse"] > 90 and self.combo > 0.75 and abs(self.swing_val) < 0.18:
            self.summon_particles_dual("heart", 1.0)
            self.trigger_release_both()
            self.combo = max(0.0, self.combo - 0.35)

        self.dialogue.update(dt)
        self.pfx.update(dt)
        if self.toast_t > 0:
            self.toast_t -= dt
        else:
            self.toast_msg = ""

        alive = []
        for (y, x, text, ttl) in self.favor_pops:
            ttl -= dt
            if ttl > 0: alive.append((y - 0.8 * dt, x, text, ttl))
        self.favor_pops = alive
        
        # ========== UPGRADED SYSTEMS UPDATE ==========
        # Update dialogue queue
        self.dialogue_queue.update(dt)
        
        # Update stink particles
        self.update_stink_particles(dt)
        
        # Decay sync flash
        if self.sync_flash > 0:
            self.sync_flash -= dt * 3.0
        
        # Decay tether tension toward neutral
        target_tension = 0.5
        self.tether_tension += (target_tension - self.tether_tension) * dt * 0.5
        
        # Check for resistance breaking (trigger stink)
        if STINK_AVAILABLE and self.stink_particles is not None:
            if self.opp["Nerve"] < 20 and not getattr(self, '_stink_break_triggered', False):
                self.emit_stink_cloud(intensity=3)
                self.dialogue_queue.say("breaking")
                self._stink_break_triggered = True
            elif self.opp["Nerve"] > 40:
                self._stink_break_triggered = False
        # =============================================
    # >>> PATCH END

    # ---- persona on beat
    def update_persona_on_beat(self):
        rq, _ = self.rhythm_quality()
        pressure = clamp(0.35 * self.combo + 0.25 * abs(self.swing_val) + (0.2 if self.smack_active else 0.0), 0.0, 1.0)
        fakeout = 1.0 if (self.smack_early and self.smack_step >= 3) else 0.25
        safety = 1.0 if self.opp_state in ("join", "heart_hop") else 0.0
        sig = Signals(groove=rq, syncop=abs(self.swing_val), fakeout=fakeout, pressure=pressure,
                      congruence=self.congruence_score(), safety=safety, pattern=self.pattern.name)
        # persona_script “lock” on phase durations if list provided
        self.persona.update(True, sig)

    def hop_bias(self):
        name = self.persona.current().name
        if name == "Collapse Romantic": return 1.2
        if name == "Pouting Brat": return 0.9
        if name == "Siren Trickster" and self.pattern.name.startswith("clave"): return 1.1
        return 0.6

    # ---- AI resolve
    def update_move(self, dt):
        if self.move_cd > 0: self.move_cd = max(0.0, self.move_cd - dt)
        m = self.move
        if not m: return
        m.t += dt
        hit_moment = (m.t >= m.tele + m.impact_at) and (not m.hit)

        if hit_moment:
            m.hit = True
            if m.kind == "shove":
                self.recoil_t = max(self.recoil_t, 0.45)
                self.ogre_x = max(2.0, self.ogre_x - 1.2)
                self.combo = max(0.0, self.combo - 0.15)
                self.pfx.burst(int(self.ogre_x + 6), self.base_y - 2, "spark", 16, 4.5, rng=self.rng)
                self.last_dialogue = ("opp", "move_shove")
                self.shake_t = 0.25
                self.shake_amp = 2.0
                self._emit("ai_hit", move="shove")
            elif m.kind == "tug":
                self.desired_gap = max(2, self.desired_gap - 1)
                self.opp["Pulse"] = clamp(self.opp["Pulse"] + 6, 0, 120)
                self.last_dialogue = ("opp", "move_tug")
                self._emit("ai_hit", move="tug")
            elif m.kind == "flick":
                self.bus.emit_jitter()
                self.combo = max(0.0, self.combo - 0.10)
                self.pfx.burst(int(self.opp_cx), self.base_y - 3, "star", 10, 3.8, rng=self.rng)
                self.last_dialogue = ("opp", "move_flick")
                self._emit("ai_hit", move="flick")
            elif m.kind == "press":
                self.opp_cx = min(self.right - 6, self.opp_cx + 1.2)
                self.desired_gap = max(2, self.desired_gap - 0.5)
                self.opp["Nerve"] = clamp(self.opp["Nerve"] + 4, 0, 100)
                self.last_dialogue = ("opp", "move_press")
                self._emit("ai_hit", move="press")
            elif m.kind == "step":
                self._emit("ai_feint", move="step")

        if m.t >= (m.tele + m.dur):
            self.move = None
            self.move_cd = 0.6 if self.phase != "encore" else 0.35

    # ---- outcomes
    def congruence_score(self):
        return clamp(0.15 * abs(self.rhythm_dir) + 0.15 * (1.0 - abs(self.swing_val)) + 0.2 * (
            1.0 if self.crest_frames > 0 else 0.0), -1.0, 1.0)

    def resolve_gambit(self):
        cong = self.congruence_score()
        pat = self.pattern.name
        w_join = 0.25 + 0.55 * cong
        w_freeze = 0.35 + 0.25 * (1.0 - cong) + 0.10 * clamp(self.opp["Nerve"] / 100.0, 0, 1)
        w_limp = 0.40 + 0.35 * (1.0 - self.opp["Nerve"] / 100.0)
        if pat == "swing":     w_join += 0.08
        if pat == "waltz":     w_join += 0.06; w_freeze -= 0.04
        if pat == "clave32":   w_freeze += 0.10; w_limp += 0.05
        if pat == "clave23":   w_join += 0.08; w_limp -= 0.04
        name = self.persona.current().name
        if name == "Collapse Romantic": w_join += 0.25
        if name == "Stoic Resister":    w_freeze += 0.20
        if name == "Bratty Chaos":      w_limp += 0.15
        if name == "Siren Trickster":   w_freeze += 0.10; w_join += 0.10
        if name == "Pouting Brat":      w_join += 0.15
        tot = w_join + w_freeze + w_limp
        r = self.rng.random() * tot
        if r < w_join:
            self.enter_state("join")
            self.toast("[join]", 0.6)
            self.summon_particles_dual("heart", 1.0)
            self.last_dialogue = ("opp", "parry")
            self.persona.lock(4)
            self._emit("state", state="join")
            self.add_favor(2, reason="join")
        elif r < w_join + w_freeze:
            self.enter_state("freeze")
            self.toast("[freeze]", 0.6)
            self.summon_particles(side="opp", kind="sweat", power=0.6)
            self.last_dialogue = ("opp", "pain")
            self._emit("state", state="freeze")
        else:
            self.enter_state("limp")
            self.toast("[limp]", 0.6)
            self.summon_particles(side="opp", kind="star", power=0.8)
            self.last_dialogue = ("opp", "pain")
            self._emit("state", state="limp")

    def enter_state(self, st):
        self.opp_state = st
        self.opp_state_t = 0.0
        if st == "freeze": self.opp["Nerve"] = clamp(self.opp["Nerve"] + 3, 0, 100)
        if st == "limp":
            self.opp["Nerve"] = clamp(self.opp["Nerve"] - 10, 0, 100)
            self.opp["Energy"] = clamp(self.opp["Energy"] - 6, 0, 100)
        if st == "join":
            self.hop_phase = 0.0
            self.opp["Pulse"] = clamp(self.opp["Pulse"] + 8, 0, 120)

    # ---- favor helpers
    def add_favor(self, delta, reason=""):
        self.favor += int(delta)
        # float pop near top-right HUD
        msg = f"+Favor {delta}"
        self.favor_pops.append((1.0, float(self.w - 16), msg, 1.2))
        self.pfx.burst(self.w - 18, 1.0, "favor", n=10, speed=2.5, rng=self.rng)
        self._emit("favor_delta", delta=int(delta), reason=reason)

    # ---- particles
    def summon_particles(self, side="opp", kind="heart", power=1.0):
        y = self.base_y - 3 if side == "ogre" else self.base_y - 2
        x = int(round(self.ogre_x + self.extra_dx + 4)) if side == "ogre" else int(round(self.opp_cx))
        n = int(8 + 10 * power)
        sp = 3.0 + 3.0 * power
        self.pfx.burst(x, y, kind=kind, n=n, speed=sp, rng=self.rng)

    def summon_particles_dual(self, kind="heart", power=1.0):
        self.summon_particles("ogre", kind, power)
        self.summon_particles("opp", kind, power)

    # ---- faces & pose
    def ogre_face(self):
        O, P = self.ogre, self.opp
        dom = (O["Poise"] - P["Nerve"]) * 0.01
        hype = (O["Pulse"] / 100.0) - 0.25 * (1.0 - O["Energy"] / 100.0)
        score = dom + 0.6 * hype
        if self.parry_flash_t > 0: return OGRE_FACES["focus"][0]
        if self.crest_frames > 0 and hype > 0.4: return OGRE_FACES["drool"][0]
        if score > 0.9:  return OGRE_FACES["sync"][0]
        if score > 0.4:  return OGRE_FACES["focus"][0]
        if score < -0.6: return OGRE_FACES["shock"][0]
        if score < -0.2: return OGRE_FACES["calm"][0]
        return OGRE_FACES["hype"][0]

    def opp_head_line(self, pose):
        face = self.pick_opp_face(pose)
        return OPP_HEAD_PREFIX + face.replace("(", "").replace(")", "")

    def opp_body_line(self, pose):
        if pose == "press": return ".__/0(<,*>)0\\__.  ./**\\."
        if pose == "step":  return "._/  (<,*>)  \\_.  ./**\\."
        if self.crest_frames > 1:
            return "._/0(<  #*  >)0\\_.  ./**\\."
        elif self.crest_frames == 1:
            return "._/0(<#*>)0\\_.  ./**\\."
        return "._/0(<,*>)0\\_.  ./**\\."

    def opp_width(self):
        pose = self.move.pose if self.move else "base"
        return max(len(self.opp_head_line(pose)), len(self.opp_body_line(pose)))

    def pick_opp_face(self, pose="base"):
        if self.opp_state in ("join", "heart_hop"): return OPP_FACES["heart"][0]
        if self.opp_state == "freeze": return OPP_FACES["freeze"][0]
        if self.opp_state == "limp":   return OPP_FACES["limp"][0]
        bias = self.persona.current().face_bias
        base = {
            "smug": 0.4 + 0.2 * bias.get("calm", 0.0),
            "brat": 0.4 + 0.2 * bias.get("alert", 0.0),
            "alert": 0.3 + 0.2 * bias.get("alert", 0.0),
            "wobble": 0.25 + 0.2 * bias.get("wobble", 0.0),
            "surge": 0.25 + 0.2 * bias.get("surge", 0.0),
            "flow": 0.25 + 0.2 * bias.get("flow", 0.0),
        }
        if pose == "press": base["surge"] += 0.2
        if pose == "step":  base["smug"] += 0.2
        lane = max(base, key=lambda k: base[k])
        bank = {"smug": OPP_FACES["smug"], "brat": OPP_FACES["brat"], "alert": OPP_FACES["alert"],
                "wobble": OPP_FACES["wobble"], "surge": OPP_FACES["surge"], "flow": OPP_FACES["flow"]}
        arr = bank[lane]
        return arr[0]

    # ---- rendering
    def ogre_body_width(self):
        return max(len(ogre_helmet()), len(ogre_brow()),
                   len(self.ogre_face()), len(ogre_tail(self.crest_frames, self.CREST_SPIKE)))

    def toast(self, msg, ttl):
        self.toast_msg = msg
        self.toast_t = ttl

    def _shake_x(self):
        if self.shake_t <= 0 or self.shake_amp <= 0: return 0
        phase = time.perf_counter() * self.shake_freq
        return int(round(math.sin(phase) * self.shake_amp * self.shake_t))

    # >>> PATCH START: HUD locks & outer names
    def render_hud(self, shake_x):
        s = self.scr
        mode = self.hud_mode
        per = self.persona.current().name
        patt = self.pattern.name

        def bar(y, x, label, val, mx, post=""):
            r = clamp(val / mx, 0, 1)
            n = int(round(20 * r))
            safe_addstr(s, y, x + shake_x, f"{label:<7} [" + "#"*n + "-"*(20-n) + "]")
            if post:
                safe_addstr(s, y, x + 30 + shake_x, post)

        if mode == 'classic':
            # Simple: old three bars (dynamic)
            safe_addstr(s, 0, 2 + shake_x, "OGRE — Classic")
            bar(1, 2, "Pulse",  self.ogre["Pulse"],  120, "OVR" if self.fatigue_on else "")
            bar(2, 2, "Energy", self.ogre["Energy"], 100, "LOCK" if self.lock_heavy else "")
            bar(3, 2, "Poise",  self.ogre["Poise"],  100, "")
            # Opponent (thin)
            bar(1, 42, "P-Pulse",  self.opp["Pulse"],  120, "")
            bar(2, 42, "P-Energy", self.opp["Energy"], 100, "")
            bar(3, 42, "P-Nerve",  self.opp["Nerve"],  100, "")
            hint = "A smack (hold=heavy) • S parry/soft • B burst (dbl/long) • ENTER release • M HUD • SPACE reset • Q quit"
            safe_addstr(s, 4, 2 + shake_x, hint[:self.w - 4])
            if self.toast_msg: safe_addstr(s, 5, self.w - (len(self.toast_msg) + 3), self.toast_msg)

        elif mode == 'advanced':
            # Rich tech HUD we already built (role, phase, BPM, pattern, locks...)
            state_tags = []
            if self.lock_heavy:  state_tags.append("HARD:LOCK")
            if self.lock_rhythm: state_tags.append("RHYTHM:OVR")
            tag_txt = (" [" + ",".join(state_tags) + "]") if state_tags else ""
            safe_addstr(
                s, 0, 2 + shake_x,
                f"Magnum Opus — {per} — role:{self.role} state:{self.opp_state} phase:{self.phase} pattern:{patt}{tag_txt}  BPM:{int(self.bpm)} sw:{self.swing:.2f}  combo:{int(self.combo * 100)}%  Favor:{self.favor}"
            )
            bar(1, 2, "Pulse",  self.ogre["Pulse"],  120, "OVR" if self.fatigue_on else "")
            bar(2, 2, "Energy", self.ogre["Energy"], 100, "LOCK" if self.lock_heavy else "")
            bar(3, 2, "Poise",  self.ogre["Poise"],  100, "")
            bar(1, 42, "P-Pulse",  self.opp["Pulse"],  120, "")
            bar(2, 42, "P-Energy", self.opp["Energy"], 100, "")
            bar(3, 42, "P-Nerve",  self.opp["Nerve"],  100, "")
            hint = "W=THRUST  A=SPANK  S=PULL  D=CARESS  SPACE=RELEASE  M HUD  ;/' pace±  ,/. swing  [/]=BPM  q quit"
            safe_addstr(s, 4, 2 + shake_x, hint[:self.w - 4])
            if self.toast_msg: safe_addstr(s, 5, self.w - (len(self.toast_msg) + 3), self.toast_msg)

        else:  # minimal
            safe_addstr(s, 0, 2 + shake_x, f"{per} • {self.phase} • BPM {int(self.bpm)} • sw {self.swing:.2f} • Fv {self.favor}")
            bar(1, 2, "E", self.ogre["Energy"], 100, "")
            bar(1, 26, "P", self.ogre["Pulse"], 120, "")
            # Minimal hint
            safe_addstr(s, 2, 2 + shake_x, "M HUD • WASD play • SPACE release")



    def render(self):
        s = self.scr
        s.erase()
        shake_x = self._shake_x()
        self.render_hud(shake_x)

        # floating favor pops
        for (y, x, text, ttl) in self.favor_pops:
            alpha = clamp(ttl / 1.2, 0, 1)
            if int(alpha * 10) % 2 == 0:
                safe_addstr(s, y, int(x) + shake_x, text)

        y = self.base_y
        ox = int(round(self.ogre_x + self.extra_dx))

        # Ogre
        safe_addstr(s, y - 4, ox + shake_x, ogre_helmet())
        face = self.ogre_face()
        if self.parry_flash_t > 0 and int(self.parry_flash_t * 20) % 2 == 0:
            face = OGRE_FACES["focus"][0]
        safe_addstr(s, y - 3, ox + shake_x, face)
        safe_addstr(s, y - 2, ox + shake_x, ogre_brow())
        tail = ogre_tail(self.crest_frames, self.CREST_SPIKE)
        safe_addstr(s, y - 1, ox + shake_x, tail)
        tail_tip = ox + len(tail)
        if self.crest_frames > 0: safe_addstr(s, y - 2, tail_tip - 1 + shake_x, "^")
        dy = -1 if (self.crest_frames > 0 or self.smack_step == 3) else 0
        safe_addstr(s, y + 1 + dy, tail_tip - 1 + shake_x, "00")

        # Opponent
        pose = self.move.pose if self.move else "base"
        hop_rows = 0
        if self.opp_state in ("join", "heart_hop"):
            hop_rows = int(round(0.5 * (1.0 - math.cos((self.hop_phase) * math.tau))))
        head = self.opp_head_line(pose)
        body = self.opp_body_line(pose)
        sway = int(round((self.jiggle_amp if self.jiggle_t > 0 else 0.0) * (1 if (self.beat_idx % 2) == 0 else -1)))
        hx = int(round(self.opp_cx - len(head) / 2.0 + self.swing_val))
        bx = int(round(self.opp_cx - len(body) / 2.0 + self.swing_val * 0.5)) + sway
        if self.move and self.move.t < self.move.tele and int(self.move.t * 50) % 2 == 0:
            head = head.replace("_", "=").replace("o", "◦")
        safe_addstr(s, y - 2 - hop_rows, hx + shake_x, head)
        safe_addstr(s, y - 1 - hop_rows, bx + shake_x, body)

        # Stage baseline
        stage_len = max(8, min(self.w - 4, int(round(self.opp_cx + len(body) / 2.0)) - self.left))
        safe_addstr(s, y, self.left + shake_x, "_" * stage_len)
        if self.crest_frames > 0: safe_addstr(s, y, tail_tip - 1 + shake_x, "__")

        # Tether
        tip = ox + len(tail) - 1
        start = tip + 1
        end = bx - 1
        if end > start:
            span = end - start + 1
            k = int(2 + round(2 * (abs(self.swing_val) + (0.25 if self.rhythm_active else 0.0))))
            if self.crest_frames > 0: k = int(round(k * 1.4))
            k = min(k, span)
            left = start + (span - k) // 2
            glyph = "≈" if self.slowmo_t > 0 else "~"
            safe_addstr(s, y - 1 - hop_rows, left + shake_x, glyph * max(0, int(k)))

        # Metronome orbs
        base = ox
        tipx = ox + len(tail) - 1
        span = max(4, len(tail) - 2)
        count = min(6, max(3, span // 2))
        amp = 2 + (1 if self.rhythm_active else 0)
        glyphs = ["·", "o", "O", "@"]
        gidx_base = int(clamp(1.0 + 0.45 * abs(self.swing_val) + (0.25 if self.rhythm_active else 0.0) - 1.0, 0, 1) * 3)
        for i in range(count):
            t = i / max(1, count - 1)
            x_eq = int(round(lerp(base + 1, tipx - 1, t)))
            x = x_eq + int(round((1 if i % 2 == 0 else -1) * amp * self.swing_val))
            g = glyphs[gidx_base]
            safe_addstr(s, y - 1, x + shake_x, g)

        # Particles & Dialogue
        self.pfx.render(s, shake_x=shake_x)
        dx_ogre = (y - 6, max(2, ox + 12))
        dx_opp = (y - 3 - hop_rows, min(self.w - 2, hx + len(head) + 2))
        self.dialogue.render(s, dx_ogre, dx_opp, shake_x=shake_x)
        
        # ========== UPGRADED RENDERING ==========
        # Render stink particles
        self.render_stink_particles(shake_x)
        
        # Render upgraded dialogue (above geisha)
        dialogue_line = self.dialogue_queue.get()
        if dialogue_line:
            dialogue_x = int(self.opp_cx - len(dialogue_line) // 2)
            safe_addstr(s, y - 4 - hop_rows, dialogue_x + shake_x, dialogue_line)
        
        # Render sync feedback
        if self.sync_flash > 0:
            if self.sync_quality > 0.9:
                msg = "★ PERFECT ★"
            elif self.sync_quality > 0.7:
                msg = "✓ Good"
            else:
                msg = ""
            
            if msg:
                msg_x = int(self.opp_cx - len(msg) // 2)
                safe_addstr(s, y - 5 - hop_rows, msg_x + shake_x, msg)
        # ==========================================

        try:
            s.refresh()
        except curses.error:
            pass

    # ---- main step
    def step(self, dt):
        self.update_phase(dt)
        self.update_rhythm(dt)
        self.update_motion(dt)
        self.update_stats(dt)


# -------- input harness
def _get_wch(scr):
    try:
        return scr.get_wch()
    except curses.error:
        return None


def run_duel(stdscr, opponent_role="samurai", on_event=None, npc_seed=None, persona_script=None, base_favor=0):
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout( 16)  # ~60 FPS; prevents \"dead\" feel between keypresses
    v = Duel(stdscr, opponent_role=opponent_role, on_event=on_event,
             npc_seed=npc_seed, persona_script=persona_script, base_favor=base_favor)
    last = time.perf_counter()
    outcome = {"released": False, "combo_max": 0.0, "phase": None, "events": v.events, "favor": v.favor}
    
    # ========== HOLD DETECTION ==========
    # Track which keys are currently down to prevent hold spam
    keys_down = set()
    key_release_timer = {}  # Auto-release keys after timeout
    # ====================================
    
    while True:
        now = time.perf_counter()
        dt = now - last
        last = now
        k = _get_wch(stdscr)
        
        # ========== HOLD DETECTION ==========
        # Check if this is a new press or a hold
        if k is not None and isinstance(k, str):
            is_new_press = k not in keys_down
            
            if is_new_press:
                keys_down.add(k)
                key_release_timer[k] = now + 0.2  # Auto-release after 200ms
            else:
                # This is a HOLD - ignore it
                k = None
        
        # Auto-release keys that timed out
        keys_to_release = [key for key, release_time in key_release_timer.items() if now >= release_time]
        for key in keys_to_release:
            keys_down.discard(key)
            del key_release_timer[key]
        # ====================================
        
        if isinstance(k, str):
            # Cycle HUD modes
            if k in 'mM':
                v.hud_mode = {'classic':'advanced','advanced':'minimal','minimal':'classic'}[v.hud_mode]
                v.toast(f"HUD: {v.hud_mode}", 0.6)
            if k in 'qQ': break
            if k == ' ':  # soft reset, keep role/vibe
                role = v.role
                on = v.on_event
                seed = None if npc_seed is None else npc_seed
                ps = v.persona_script
                base = v.favor
                v = Duel(stdscr, opponent_role=role, on_event=on, npc_seed=seed, persona_script=ps, base_favor=base)
            if k == '\n':
                v.trigger_release_both()
                outcome["released"] = True
            if k in 'dD': v.dialogue.enabled = not v.dialogue.enabled
            if k == ';': v.dialogue.rate = max(0.35, v.dialogue.rate - 0.05)
            if k == "'": v.dialogue.rate = min(1.20, v.dialogue.rate + 0.05)
            if k in 'kK': v.subtitle_only = not v.subtitle_only
            if k == '[': v.bpm = max(40, v.bpm - 2)
            if k == ']': v.bpm = min(180, v.bpm + 2)
            if k == ',': v.swing = max(0.0, round(v.swing - 0.02, 2))
            if k == '.': v.swing = min(0.24, round(v.swing + 0.02, 2))
            if k == 'v': v.swing = clamp(round(v.swing + 0.01, 3), 0.0, 0.24)
            if k == 'V': v.swing = clamp(round(v.swing - 0.01, 3), 0.0, 0.24)
            if k in '123': v.bus.set_intent(p={'1': 0.2, '2': 0.5, '3': 0.85}[k])
            if k in '456': v.bus.set_intent(t={'4': 0.2, '5': 0.5, '6': 0.85}[k])
            if k in '789': v.bus.set_intent(c={'7': 0.2, '8': 0.5, '9': 0.85}[k])
            if k == '0': v.bus.set_intent(p=0.33, t=0.33, c=0.33)
            if k in 'Ff': v.bus.emit_feint(); v.toast("[feint]", 0.5)
            if k in 'Gg': v.bus.emit_ghost(); v.toast("[ghost]", 0.4)
            if k in 'Hh': v.bus.emit_heartbeat(); v.toast("[beat]", 0.3)
            if k in 'Jj': v.bus.emit_jitter(); v.toast("[jitter]", 0.3)
            # ========== UPGRADED CONTROLS (WASD + Space) ==========
            if k in 'Ww':
                # THRUST (W) - Forward, aggressive
                v.press_thrust()
            if k in 'Aa':
                # SPANK (A) - Rhythmic, playful
                v.press_spank()
            if k in 'Ss':
                # PULL (S) - Control, dominance  
                # Keep parry mechanic if move active
                if v.move and v.move.t < v.move.tele and v.move.kind in ("shove", "tug", "flick", "press"):
                    v.move.done = True
                    v.move = None
                    v.move_cd = 0.5
                    v.parry_flash_t = 0.25
                    v.toast("parry!", 0.5)
                    v.pfx.burst(int(v.ogre_x + 6), v.base_y - 3, "spark", 20, 5.2, rng=v.rng)
                    v.opp["Nerve"] = clamp(v.opp["Nerve"] - 6, 0, 100)
                    v.add_favor(1, reason="parry")
                    v._emit("parry", move="block")
                else:
                    v.press_pull()
            if k in 'Dd':
                # CARESS (D) - Gentle, responsive
                v.press_caress()
            if k == ' ':
                # RELEASE (Space) - Mutual climax
                v.trigger_release_both()
                outcome["released"] = True
            # =======================================================
            
            # Keep debug/dev controls
            if k == '\n':
                # Alternate release (keep for compatibility)
                v.trigger_release_both()
                outcome["released"] = True

        v.step(dt)
        outcome["combo_max"] = max(outcome["combo_max"], v.combo)
        outcome["phase"] = v.phase
        outcome["favor"] = v.favor
        v.render()
        time.sleep(0.016)
    outcome["events"] = v.events
    return outcome


def main():
    curses.wrapper(lambda stdscr: run_duel(stdscr, opponent_role="samurai", npc_seed=777, base_favor=0))


if __name__ == "__main__":
    main()