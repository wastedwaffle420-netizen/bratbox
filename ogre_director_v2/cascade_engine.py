#!/usr/bin/env python3
"""Cascade Intelligence (refined)

Goal: the "tagged chaining masterpiece" feel without requiring you to hand-tag the entire corpus.

What this module provides:
- Emotional DNA tagging (auto + optional author overrides)
- Explicit theme taxonomy + multi-signal detectors (beyond keyword-only)
- Callback library with long-range payoffs (thread-aware)
- Manual/author tagging hooks (inline markup + external JSON overrides)
- A single public selector: choose_from_pool(pool, speaker, ctx)

Safety:
- Never blocks; always returns a line from the pool
- All scoring is clamped; selection always has a fallback
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
import json
import time
import hashlib
import random
import re

DEFAULT_MEMORY_PATH = Path.home() / ".ogre_shader_cascade_memory.json"
DEFAULT_AUTHOR_TAGS_PATHS = [
    Path(__file__).with_name("author_tags.json"),
    Path.home() / ".ogre_shader_author_tags.json",
]

# ---------------------------------------------------------------------------
# Callback library (seed callbacks for fresh saves)
# ---------------------------------------------------------------------------
DEFAULT_CALLBACK_LIBRARY_PATHS = [
    Path(__file__).with_name('callback_library.json'),
    Path.home() / '.ogre_shader_callback_library.json',
]

_CALLBACK_LIBRARY_CACHE = None  # type: ignore
_LIB_LAST_USED = {}  # line -> last_used timestamp


def _load_callback_library():
    # Expected JSON format:
    # {"themes": {"banter": ["..."], ...}}
    lib = {}
    for p in DEFAULT_CALLBACK_LIBRARY_PATHS:
        try:
            if not p.exists():
                continue
            raw = json.loads(p.read_text(encoding='utf-8'))
            themes = raw.get('themes', raw)
            if isinstance(themes, dict):
                for k, v in themes.items():
                    if isinstance(k, str) and isinstance(v, list):
                        lib.setdefault(k, [])
                        for s in v:
                            if isinstance(s, str) and s.strip():
                                lib[k].append(s.strip())
        except Exception:
            continue
    # de-dupe while preserving order
    for k in list(lib.keys()):
        seen = set()
        out = []
        for s in lib[k]:
            if s not in seen:
                seen.add(s)
                out.append(s)
        lib[k] = out
    return lib


def _get_callback_library():
    global _CALLBACK_LIBRARY_CACHE
    if _CALLBACK_LIBRARY_CACHE is None:
        _CALLBACK_LIBRARY_CACHE = _load_callback_library()
    return _CALLBACK_LIBRARY_CACHE


# ---------------------------------------------------------------------------
# Theme taxonomy (explicit, compact)
# ---------------------------------------------------------------------------

THEME_TAXONOMY: Dict[str, Dict[str, Any]] = {
    # tender / safety
    "aftercare": {"aliases": ["safety", "care", "soft", "breathe", "shh"], "weight": 1.0},
    "affection": {"aliases": ["love", "kiss", "sweet", "gentle"], "weight": 0.9},

    # power / control
    "control": {"aliases": ["hold", "wait", "not yet", "edge"], "weight": 1.0},
    "ownership": {"aliases": ["mine", "stay", "not letting go"], "weight": 0.9},
    "resistance": {"aliases": ["no", "stop", "don't", "not fair"], "weight": 0.8},
    "surrender": {"aliases": ["please", "more", "need you", "beg"], "weight": 0.9},

    # energy / pacing
    "hunger": {"aliases": ["again", "faster", "harder", "more!"], "weight": 1.0},
    "overwhelm": {"aliases": ["too much", "can't", "oh god", "i'm gonna"], "weight": 0.9},

    # tone
    "play": {"aliases": ["tease", "cute", "good?", "you like that"], "weight": 0.7},
    "validation": {"aliases": ["good girl", "perfect", "that's it", "so good"], "weight": 0.7},
    "mischief": {"aliases": ["baka", "nyeh", "oy"], "weight": 0.5},

    # meta / ritual (works well with your procedural-authority vibe)
    "ritual": {"aliases": ["remember", "promise", "next time", "as i said"], "weight": 0.8},
}

# Base tag patterns (fast keyword anchors)
_TAG_PATTERNS: List[Tuple[str, List[str]]] = [
    ("begging", [r"\bplease\b", r"\bpls\b", r"don't stop", r"\bmore\b", r"need you", r"beg\b"]),
    ("defiant", [r"\bno\b", r"\bstop\b", r"\bdon't\b", r"make me", r"not fair"]),
    ("tease", [r"\btease\b", r"\bmean\b", r"you like that", r"\bcute\b", r"mm+h+"]),
    ("praise", [r"good girl", r"that's it", r"perfect", r"so good", r"yes\b"]),
    ("possessive", [r"\bmine\b", r"stay", r"not letting go", r"you're not going anywhere"]),
    ("aftercare", [r"breathe", r"okay\?", r"gentle", r"shh", r"i've got you", r"safe"]),
    ("edge", [r"\bedge\b", r"don't you dare", r"\bhold\b", r"\bwait\b", r"not yet"]),
    ("frenzy", [r"again", r"faster", r"harder", r"insatiable", r"more\!"]),
    ("tender", [r"\blove\b", r"soft", r"careful", r"slow", r"kiss"]),
    ("comic", [r"baka", r"mwehh", r"nyeh", r"\boy\b"]),
    ("panic", [r"\bcan't\b", r"too much", r"i'm gonna", r"oh god", r"hahh+"]),
]

# Map core tags to canonical themes (taxonomy)
_TAG_TO_THEME: Dict[str, str] = {
    "begging": "surrender",
    "defiant": "resistance",
    "tease": "play",
    "praise": "validation",
    "possessive": "ownership",
    "aftercare": "aftercare",
    "edge": "control",
    "frenzy": "hunger",
    "tender": "affection",
    "comic": "mischief",
    "panic": "overwhelm",
}

# Setup/payoff markers (thread system)
_SETUP_MARKERS = [
    r"next time", r"later", r"after this", r"promise", r"don't forget", r"remember this",
    r"when we're done", r"i'll make you", r"i'm going to"
]
_PAYOFF_MARKERS = [
    r"as promised", r"told you", r"remember", r"like i said", r"there you go", r"you asked for it"
]

# ---------------------------------------------------------------------------
# Author tagging hooks
# ---------------------------------------------------------------------------

# Inline markup supported (anywhere in a line):
#   [[tag:begging,aftercare]] [[theme:aftercare,ritual]]
# Trailing markup supported:
#   {#begging,#aftercare theme=aftercare,ritual setup=ritual payoff=aftercare}
_INLINE_BLOCK_PAT = re.compile(r"\[\[(tag|theme|setup|payoff):([^\]]+)\]\]", re.I)
_TRAILING_BLOCK_PAT = re.compile(r"\{([^{}]{1,160})\}\s*$")

_author_overrides_cache: Optional[Dict[str, Dict[str, Any]]] = None

def _load_author_overrides() -> Dict[str, Dict[str, Any]]:
    global _author_overrides_cache
    if _author_overrides_cache is not None:
        return _author_overrides_cache
    merged: Dict[str, Dict[str, Any]] = {}
    for p in DEFAULT_AUTHOR_TAGS_PATHS:
        try:
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    for k, v in data.items():
                        if isinstance(k, str) and isinstance(v, dict):
                            merged[k] = v
        except Exception:
            pass
    _author_overrides_cache = merged
    return merged

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())

def _strip_author_markup(text: str) -> Tuple[str, Dict[str, Set[str]]]:
    """Return (clean_text, meta_sets)."""
    meta = {"tags": set(), "themes": set(), "setup": set(), "payoff": set()}
    raw = text or ""

    # Inline blocks
    def _inline_repl(m: re.Match) -> str:
        kind = (m.group(1) or "").lower().strip()
        val = (m.group(2) or "")
        parts = [p.strip() for p in re.split(r"[,;]", val) if p.strip()]
        if kind in meta:
            meta[kind].update({p.lower() for p in parts})
        return ""

    cleaned = _INLINE_BLOCK_PAT.sub(_inline_repl, raw)

    # Trailing brace block
    m = _TRAILING_BLOCK_PAT.search(cleaned)
    if m:
        body = m.group(1) or ""
        # tags: #tag1 #tag2
        for t in re.findall(r"#([a-zA-Z0-9_\-]+)", body):
            meta["tags"].add(t.lower())
        # key= lists
        for key in ("theme", "themes", "setup", "payoff", "tag", "tags"):
            km = re.search(rf"\b{key}\s*=\s*([^\s]+)", body, flags=re.I)
            if km:
                vals = [p.strip().lower() for p in re.split(r"[,;]", km.group(1)) if p.strip()]
                if key.startswith("theme"):
                    meta["themes"].update(vals)
                elif key.startswith("setup"):
                    meta["setup"].update(vals)
                elif key.startswith("payoff"):
                    meta["payoff"].update(vals)
                elif key.startswith("tag"):
                    meta["tags"].update(vals)
        cleaned = _TRAILING_BLOCK_PAT.sub("", cleaned).rstrip()

    return cleaned, meta

def line_hash(speaker: str, text: str) -> str:
    """Stable hash based on normalized *display* text + speaker."""
    clean, _ = _strip_author_markup(text)
    h = hashlib.sha1()
    h.update((speaker + "|" + _norm(clean)).encode("utf-8", errors="ignore"))
    return h.hexdigest()

# ---------------------------------------------------------------------------
# Detectors (beyond keyword-only)
# ---------------------------------------------------------------------------

def _punct_intensity(text: str) -> float:
    if not text:
        return 0.0
    ex = text.count("!")
    qm = text.count("?")
    dots = text.count("...")
    caps = sum(1 for c in text if c.isupper())
    letters = sum(1 for c in text if c.isalpha())
    cap_ratio = (caps / max(1, letters))
    # strong signals: exclamations and caps, weak: questions/dots
    score = 0.18 * min(6, ex) + 0.08 * min(6, qm) + 0.06 * min(4, dots) + 0.35 * min(0.6, cap_ratio)
    return max(0.0, min(1.0, score))

def _hesitation_score(text: str) -> float:
    t = text or ""
    return max(0.0, min(1.0, 0.30 * t.count("...") + 0.12 * t.count("—") + 0.10 * t.count("~")))

def _negation_score(text: str) -> float:
    t = _norm(text)
    return 1.0 if re.search(r"\b(no|don't|stop|can't|won't|never)\b", t) else 0.0

def _need_score(text: str) -> float:
    t = _norm(text)
    return 1.0 if re.search(r"\b(need|please|more|again)\b", t) else 0.0

def _care_score(text: str) -> float:
    t = _norm(text)
    return 1.0 if re.search(r"\b(breathe|safe|okay|gentle|shh)\b", t) else 0.0

def detect_setup(text: str) -> bool:
    t = _norm(text)
    return any(re.search(p, t) for p in _SETUP_MARKERS)

def detect_payoff(text: str) -> bool:
    t = _norm(text)
    return any(re.search(p, t) for p in _PAYOFF_MARKERS)

# ---------------------------------------------------------------------------
# Public tag/theme inference
# ---------------------------------------------------------------------------

def infer_tags(text: str, speaker: str = "", extra: Optional[Set[str]] = None) -> Set[str]:
    clean, tags, themes, meta = infer_meta(text, speaker=speaker, extra=extra)
    return tags

def infer_themes(tags: Set[str]) -> Set[str]:
    themes: Set[str] = set()
    for tg in tags:
        base = tg.split(":", 1)[-1]
        if base in _TAG_TO_THEME:
            themes.add(_TAG_TO_THEME[base])
    # Also allow explicit theme tags: theme:aftercare
    for tg in tags:
        if tg.startswith("theme:"):
            themes.add(tg.split(":", 1)[1])
    return themes

def infer_meta(text: str, speaker: str = "", extra: Optional[Set[str]] = None) -> Tuple[str, Set[str], Set[str], Dict[str, Any]]:
    """Return (clean_text, tags, themes, meta)."""
    raw = text or ""
    clean, inline_meta = _strip_author_markup(raw)
    t = _norm(clean)

    tags: Set[str] = set(extra or [])
    for tag, pats in _TAG_PATTERNS:
        for p in pats:
            if re.search(p, t):
                tags.add(tag)
                break

    # Add multi-signal tags
    pi = _punct_intensity(clean)
    if pi >= 0.55:
        tags.add("high_arousal")
    if _hesitation_score(clean) >= 0.35:
        tags.add("hesitate")
    if _negation_score(clean) > 0.0:
        tags.add("negation")
    if _need_score(clean) > 0.0:
        tags.add("need")
    if _care_score(clean) > 0.0:
        tags.add("care")

    if speaker:
        tags.add(f"speaker:{speaker.lower()}")
    if "!" in clean:
        tags.add("exclaim")
    if "..." in clean:
        tags.add("ellipsis")
    if "~" in clean:
        tags.add("sing")

    # Inline author meta
    for tg in inline_meta.get("tags", set()):
        tags.add(tg)

    # Themes from tags + taxonomy hints
    themes = infer_themes(tags)

    # Inline explicit theme overrides
    for th in inline_meta.get("themes", set()):
        themes.add(th)

    # External author overrides by hash
    lh = line_hash(speaker or "", clean)
    overrides = _load_author_overrides().get(lh)
    if overrides and isinstance(overrides, dict):
        for tg in overrides.get("tags", []) or []:
            if isinstance(tg, str):
                tags.add(tg.lower())
        for th in overrides.get("themes", []) or []:
            if isinstance(th, str):
                themes.add(th.lower())

    # Detect taxonomy themes directly from text (not only tags)
    theme_scores = detect_themes_scored(clean, tags=tags)
    # promote any theme with score >= 0.55 into active theme set
    for th, sc in theme_scores.items():
        if sc >= 0.55:
            themes.add(th)

    meta: Dict[str, Any] = {
        "inline": inline_meta,
        "hash": lh,
        "theme_scores": theme_scores,
        "setup": set(inline_meta.get("setup", set())),
        "payoff": set(inline_meta.get("payoff", set())),
    }
    # merge overrides setup/payoff if present
    if overrides and isinstance(overrides, dict):
        for th in overrides.get("setup", []) or []:
            if isinstance(th, str):
                meta["setup"].add(th.lower())
        for th in overrides.get("payoff", []) or []:
            if isinstance(th, str):
                meta["payoff"].add(th.lower())

    return clean, tags, themes, meta

def detect_themes_scored(text: str, tags: Optional[Set[str]] = None) -> Dict[str, float]:
    """Return theme->score using multiple signals."""
    tags = tags or set()
    t = _norm(text)

    scores: Dict[str, float] = {k: 0.0 for k in THEME_TAXONOMY.keys()}

    # Tag-derived boosts
    for tg in tags:
        base = tg.split(":", 1)[-1]
        th = _TAG_TO_THEME.get(base)
        if th:
            scores[th] = max(scores[th], 0.75)

    # Lexical alias matches (fast)
    for theme, info in THEME_TAXONOMY.items():
        aliases = info.get("aliases", [])
        for a in aliases:
            if a and a in t:
                scores[theme] = max(scores[theme], 0.60)

    # Signal-based boosts
    pi = _punct_intensity(text)
    neg = _negation_score(text)
    need = _need_score(text)
    care = _care_score(text)
    hes = _hesitation_score(text)

    if care > 0.0:
        scores["aftercare"] = max(scores["aftercare"], 0.80)
        scores["affection"] = max(scores["affection"], 0.55)
    if need > 0.0:
        scores["surrender"] = max(scores["surrender"], 0.70)
        scores["hunger"] = max(scores["hunger"], 0.55)
    if neg > 0.0:
        scores["resistance"] = max(scores["resistance"], 0.70)
    if pi >= 0.65:
        scores["hunger"] = max(scores["hunger"], 0.70)
        scores["overwhelm"] = max(scores["overwhelm"], 0.55)
    if hes >= 0.45:
        scores["ritual"] = max(scores["ritual"], 0.55)

    # Setup/payoff markers push ritual
    if detect_setup(text) or detect_payoff(text):
        scores["ritual"] = max(scores["ritual"], 0.75)

    return scores

# ---------------------------------------------------------------------------
# Memory + threads + callbacks
# ---------------------------------------------------------------------------

@dataclass
class Thread:
    theme: str
    created: float
    ttl: int = 40
    strength: float = 1.0
    kind: str = "thread"  # "setup" or "thread"

@dataclass
class CallbackEntry:
    h: str
    text: str
    theme: str
    created: float
    strength: float = 1.0
    last_used: float = 0.0

@dataclass
class CascadeMemory:
    path: Path = DEFAULT_MEMORY_PATH
    theme_weights: Dict[str, float] = field(default_factory=dict)
    recent_hashes: List[str] = field(default_factory=list)
    last_lines: List[Dict[str, Any]] = field(default_factory=list)
    open_threads: List[Thread] = field(default_factory=list)
    callbacks: Dict[str, List[CallbackEntry]] = field(default_factory=dict)
    version: int = 2
    dirty: bool = False

    def load(self) -> None:
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self.version = int(data.get("version", 1))
                self.theme_weights = dict(data.get("theme_weights", {}))
                self.recent_hashes = list(data.get("recent_hashes", []))[-250:]
                self.last_lines = list(data.get("last_lines", []))[-35:]

                # callbacks backward compat (strings)
                raw_cb = data.get("callbacks", {}) or {}
                cb: Dict[str, List[CallbackEntry]] = {}
                if isinstance(raw_cb, dict):
                    for theme, entries in raw_cb.items():
                        theme = str(theme)
                        cb_list: List[CallbackEntry] = []
                        if isinstance(entries, list):
                            for e in entries:
                                if isinstance(e, str):
                                    cb_list.append(CallbackEntry(
                                        h=line_hash("", e),
                                        text=e,
                                        theme=theme,
                                        created=time.time(),
                                        strength=0.6,
                                        last_used=0.0,
                                    ))
                                elif isinstance(e, dict):
                                    cb_list.append(CallbackEntry(
                                        h=str(e.get("h") or line_hash("", str(e.get("text", "")))),
                                        text=str(e.get("text", "")),
                                        theme=theme,
                                        created=float(e.get("created", time.time())),
                                        strength=float(e.get("strength", 1.0)),
                                        last_used=float(e.get("last_used", 0.0)),
                                    ))
                        cb[theme] = cb_list
                self.callbacks = cb

                self.open_threads = []
                for td in data.get("open_threads", []) or []:
                    try:
                        self.open_threads.append(Thread(**td))
                    except Exception:
                        pass
        except Exception:
            pass

    def save(self, force: bool = False) -> None:
        if not force and not self.dirty:
            return
        try:
            payload = {
                "version": self.version,
                "theme_weights": self.theme_weights,
                "recent_hashes": self.recent_hashes[-250:],
                "last_lines": self.last_lines[-35:],
                "open_threads": [t.__dict__ for t in self.open_threads[-60:]],
                "callbacks": {
                    th: [e.__dict__ for e in lst[-120:]]
                    for th, lst in self.callbacks.items()
                },
            }
            self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            self.dirty = False
        except Exception:
            pass

_memory_singleton: Optional[CascadeMemory] = None

def get_memory() -> CascadeMemory:
    global _memory_singleton
    if _memory_singleton is None:
        mem = CascadeMemory()
        mem.load()
        _memory_singleton = mem
    return _memory_singleton

# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _novelty_penalty(mem: CascadeMemory, h: str) -> float:
    # penalty if repeated recently
    if h in mem.recent_hashes[-30:]:
        return 0.85
    if h in mem.recent_hashes[-120:]:
        return 0.35
    return 0.0

def _theme_score(mem: CascadeMemory, theme_scores: Dict[str, float]) -> float:
    # dot product between candidate theme scores and stored weights (clamped)
    s = 0.0
    for th, sc in theme_scores.items():
        if sc <= 0.0:
            continue
        w = float(mem.theme_weights.get(th, 0.0))
        s += sc * w
    return max(0.0, min(2.5, s))

def _thread_score(mem: CascadeMemory, candidate_themes: Set[str], meta: Dict[str, Any]) -> float:
    now = time.time()
    score = 0.0

    payoff_set = set(meta.get("payoff", set()) or [])
    # If candidate explicitly pays off a thread theme, big reward.
    for th in payoff_set:
        for tr in mem.open_threads:
            if tr.theme == th:
                score += 1.25 * tr.strength

    for tr in mem.open_threads:
        age = now - tr.created
        if age > tr.ttl:
            continue
        if tr.theme in candidate_themes:
            # prefer closing threads that have been open longer
            closeness = min(1.0, age / max(1.0, tr.ttl))
            score += 0.45 * tr.strength * (0.4 + 0.6 * closeness)

    return max(0.0, min(2.0, score))

def _followup_score(mem: CascadeMemory, candidate_themes: Set[str]) -> float:
    if not mem.last_lines:
        return 0.0
    last = mem.last_lines[-1]
    last_themes = set(last.get("themes", []) or [])
    if not last_themes:
        return 0.0
    overlap = len(candidate_themes & last_themes)
    if overlap <= 0:
        return 0.0
    return min(1.0, 0.25 + 0.25 * overlap)

def _intensity_fit(ctx: "CascadeContext", theme_scores: Dict[str, float]) -> float:
    # Encourage aftercare/affection at low intensity; hunger/overwhelm/control at high.
    intensity = float(getattr(ctx, "intensity", 0.5) or 0.5)
    low = max(0.0, 1.0 - intensity)
    high = max(0.0, intensity)

    fit = 0.0
    fit += low * (0.70 * theme_scores.get("aftercare", 0.0) + 0.35 * theme_scores.get("affection", 0.0))
    fit += high * (0.55 * theme_scores.get("hunger", 0.0) + 0.45 * theme_scores.get("control", 0.0) + 0.35 * theme_scores.get("overwhelm", 0.0))
    return max(0.0, min(1.5, fit))

# ---------------------------------------------------------------------------
# Public selection
# ---------------------------------------------------------------------------

@dataclass
class CascadeContext:
    intensity: float = 0.5
    lane: str = ""
    quality: str = ""

def score_candidate(text: str, speaker: str, ctx: Optional[CascadeContext] = None) -> float:
    ctx = ctx or CascadeContext()
    mem = get_memory()

    clean, tags, themes, meta = infer_meta(text, speaker=speaker)
    h = meta.get("hash") or line_hash(speaker, clean)
    theme_scores = dict(meta.get("theme_scores", {}) or {})

    novelty = 1.0 - _novelty_penalty(mem, h)
    base = 0.35

    # Main components
    s_theme = _theme_score(mem, theme_scores)
    s_thread = _thread_score(mem, themes, meta)
    s_follow = _followup_score(mem, themes)
    s_fit = _intensity_fit(ctx, theme_scores)

    score = base + 0.55 * s_theme + 0.65 * s_thread + 0.35 * s_follow + 0.45 * s_fit
    score *= max(0.15, novelty)

    # Small lane/quality shaping
    if ctx.quality == "miss":
        score *= 0.85
    if ctx.lane and ctx.lane.lower() in ("aftercare", "release") and "aftercare" in themes:
        score *= 1.10

    return max(0.01, min(6.0, score))

def _update_memory_after_pick(mem: CascadeMemory, speaker: str, clean: str, themes: Set[str], meta: Dict[str, Any]) -> None:
    now = time.time()
    h = meta.get("hash") or line_hash(speaker, clean)

    mem.recent_hashes.append(h)
    mem.recent_hashes = mem.recent_hashes[-250:]

    # Theme weights: reinforce active themes, decay others gently
    decay = 0.985
    for k in list(mem.theme_weights.keys()):
        mem.theme_weights[k] = float(mem.theme_weights.get(k, 0.0)) * decay
        if mem.theme_weights[k] < 0.03:
            del mem.theme_weights[k]

    for th in themes:
        w = float(mem.theme_weights.get(th, 0.0))
        mem.theme_weights[th] = min(4.0, w + 0.22)

    # Add last line record
    mem.last_lines.append({
        "ts": now,
        "speaker": speaker,
        "text": clean,
        "themes": sorted(list(themes)),
        "hash": h,
    })
    mem.last_lines = mem.last_lines[-35:]

    # Threads: setup opens a thread
    setup_themes = set(meta.get("setup", set()) or [])
    if detect_setup(clean) or setup_themes:
        # pick a theme to track: explicit setup themes first, else strongest theme score
        chosen: Optional[str] = None
        if setup_themes:
            chosen = next(iter(setup_themes))
        else:
            theme_scores = dict(meta.get("theme_scores", {}) or {})
            if theme_scores:
                chosen = max(theme_scores.items(), key=lambda kv: kv[1])[0]
        if chosen:
            mem.open_threads.append(Thread(theme=chosen, created=now, ttl=45, strength=1.0, kind="setup"))

    # Aging threads
    mem.open_threads = [t for t in mem.open_threads if (now - t.created) <= t.ttl]
    mem.open_threads = mem.open_threads[-60:]

    # Callback harvesting: store lines that look like payoffs or are "memorable" (high arousal or ritual)
    memorable = ("high_arousal" in infer_tags(clean, speaker=speaker)) or detect_payoff(clean)
    if memorable:
        # choose a dominant theme for callback
        dominant = None
        if themes:
            dominant = next(iter(themes))
        else:
            theme_scores = dict(meta.get("theme_scores", {}) or {})
            if theme_scores:
                dominant = max(theme_scores.items(), key=lambda kv: kv[1])[0]
        if dominant:
            mem.callbacks.setdefault(dominant, [])
            # prevent duplicates
            if not any(e.h == h for e in mem.callbacks[dominant][-200:]):
                mem.callbacks[dominant].append(CallbackEntry(
                    h=h, text=clean, theme=dominant, created=now, strength=1.0, last_used=0.0
                ))
                mem.callbacks[dominant] = mem.callbacks[dominant][-200:]

    mem.dirty = True

def maybe_inject_callback(get_memory, ctx, min_gap=12.0):
    # Optionally inject a callback line based on dominant theme.
    # Now supports a small curated seed library so brand-new saves can still feel 'alive'.
    try:
        mem = get_memory()
    except Exception:
        return None

    import time, random
    now = time.time()

    # Quick spam guard: if we just spoke, don't immediately callback.
    if getattr(mem, 'last_lines', None):
        try:
            last_ts = mem.last_lines[-1][0]
            if (now - float(last_ts)) < 2.5:
                return None
        except Exception:
            pass

    lib = _get_callback_library()

    # Determine dominant theme.
    dominant = None
    try:
        if getattr(mem, 'theme_weights', None):
            dominant = max(mem.theme_weights.items(), key=lambda kv: kv[1])[0]
    except Exception:
        dominant = None

    if not dominant:
        # Fallback guess from context
        mode = (getattr(ctx, 'mode', '') or '').lower()
        if 'after' in mode or 'release' in mode:
            dominant = 'aftercare'
        elif getattr(ctx, 'intensity', 0.0) < 0.35:
            dominant = 'aftercare'
        elif getattr(ctx, 'intensity', 0.0) < 0.65:
            dominant = 'banter'
        else:
            dominant = 'ritual'

    mem_pool = []
    try:
        mem_pool = list(getattr(mem, 'callbacks', {}).get(dominant, []))
    except Exception:
        mem_pool = []

    lib_pool = []
    if isinstance(lib, dict):
        lib_pool = list(lib.get(dominant, []))

    if not mem_pool and not lib_pool:
        return None

    candidates = []

    # Prefer memory callbacks, but mix in library entries.
    for entry in mem_pool[-60:]:
        try:
            if (now - float(entry.last_used)) < 120:
                continue
            sc = float(entry.strength) + 0.25
            sc += 0.15 * random.random()
            candidates.append((sc, entry.text, ('mem', entry)))
        except Exception:
            continue

    for txt in lib_pool:
        try:
            last = _LIB_LAST_USED.get(txt, 0.0)
            if (now - float(last)) < 90:
                continue
        except Exception:
            pass
        sc = 0.70 + 0.20 * random.random()
        # Slight bias for aftercare at low intensity
        if dominant == 'aftercare' and getattr(ctx, 'intensity', 0.0) < 0.45:
            sc *= 1.10
        candidates.append((sc, txt, ('lib', txt)))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    top = candidates[:7]
    _, txt, meta = random.choice(top)

    # Record usage
    try:
        if meta[0] == 'mem':
            entry = meta[1]
            entry.last_used = now
            mem.dirty = True
            mem.save()
        else:
            _LIB_LAST_USED[txt] = now
    except Exception:
        pass

    return txt


def choose_from_pool(pool: List[str], speaker: str, ctx: Optional[CascadeContext] = None, sample: int = 10) -> str:
    """Pick a line from pool with cascade scoring, returning *clean display text*.

    Manual hooks:
    - inline markup (removed from display, used for tags/themes)
    - external overrides keyed by line_hash
    """
    if not pool:
        return ""

    ctx = ctx or CascadeContext()
    mem = get_memory()

    # Small chance to inject a callback if it fits
    inject = maybe_inject_callback(speaker, ctx=ctx)
    if inject:
        clean, _, themes, meta = infer_meta(inject, speaker=speaker)
        _update_memory_after_pick(mem, speaker, clean, themes, meta)
        mem.save()
        return clean

    # Sample candidates to keep CPU low
    if sample and len(pool) > sample:
        candidates_raw = random.sample(pool, k=min(sample, len(pool)))
    else:
        candidates_raw = list(pool)

    scored: List[Tuple[float, str, str, Set[str], Dict[str, Any]]] = []
    for raw in candidates_raw:
        try:
            clean, tags, themes, meta = infer_meta(raw, speaker=speaker)
            sc = score_candidate(raw, speaker=speaker, ctx=ctx)
            scored.append((sc, raw, clean, themes, meta))
        except Exception:
            # fallback: treat as low-scoring but valid
            cleaned, _ = _strip_author_markup(raw)
            scored.append((0.05, raw, cleaned, set(), {"hash": line_hash(speaker, cleaned), "theme_scores": {}}))

    scored.sort(key=lambda x: x[0], reverse=True)
    best = scored[0]

    # Soft-random among top few for variety
    topn = scored[:max(1, min(5, len(scored)))]
    weights = [max(0.05, min(4.0, s[0])) for s in topn]
    chosen = random.choices(topn, weights=weights, k=1)[0]

    _, raw, clean, themes, meta = chosen
    _update_memory_after_pick(mem, speaker, clean, themes, meta)
    mem.save()
    return clean

