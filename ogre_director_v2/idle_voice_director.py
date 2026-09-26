"""Clip-native Idle Voice Brain for Way of the Wind.

The older radio-play path generated prose and then independently searched for a
similar recording.  Distinct generated lines could consequently collapse onto
the same high-scoring WAV.  This director makes the shipped recordings the
canonical vocabulary: it classifies the transcript catalog, chooses compatible
call/response clips, protects peak phrases, and remembers semantic repetition.

This module owns no mixer channels and no game outcomes.  It only selects audio.
All state is process/session state and is intentionally never serialized.
"""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import random
import re
import time
from typing import Any, Deque, Dict, Iterable, List, Optional, Sequence, Set, Tuple


_STOP = {
    "a", "an", "and", "are", "but", "for", "he", "her", "him", "i", "in",
    "is", "it", "just", "me", "my", "of", "on", "or", "she", "so", "that",
    "the", "their", "them", "they", "this", "to", "was", "we", "what", "with",
    "you", "your", "yeah", "okay", "really",
}


def _norm(text: str) -> str:
    text = str(text or "").lower().replace("’", "'")
    text = re.sub(r"[^a-z0-9']+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokens(text: str) -> Set[str]:
    return {w for w in _norm(text).split() if len(w) > 2 and w not in _STOP}


def _stemmed_signature(text: str) -> str:
    """Cheap near-duplicate key suitable for noisy Whisper transcripts."""
    words = []
    for word in _norm(text).split():
        if word in _STOP:
            continue
        for suffix in ("ing", "edly", "edly", "ed", "ly", "s"):
            if len(word) > len(suffix) + 3 and word.endswith(suffix):
                word = word[:-len(suffix)]
                break
        words.append(word)
    return " ".join(words[:12])


def _contains(text: str, phrases: Iterable[str]) -> bool:
    t = " " + _norm(text) + " "
    return any((" " + _norm(p) + " ") in t for p in phrases)


def _near_duplicate(a: str, b: str) -> bool:
    aa, bb = set(str(a or "").split()), set(str(b or "").split())
    if not aa or not bb:
        return False
    overlap = len(aa & bb)
    union = len(aa | bb)
    return (overlap >= 3 and overlap / max(1, min(len(aa), len(bb))) >= 0.80) or (overlap / max(1, union) >= 0.72)


@dataclass(frozen=True)
class VoiceClip:
    path: Path
    speaker: str
    transcript: str
    normalized: str
    signature: str
    family: str
    role: str
    intensity_min: float
    intensity_max: float
    intelligibility: float
    peak_value: int
    duration: float
    tags: Tuple[str, ...] = ()
    response_families: Tuple[str, ...] = ()
    tier: str = "conversation"
    prosody: str = "neutral_spoken"
    duplicate_group: str = ""
    performed_intent: str = "neutral_statement"

    @property
    def clip_id(self) -> str:
        return self.path.name


@dataclass
class VoiceContext:
    progress: float = 0.0
    pressure: float = 0.0
    composure: float = 1.0
    paused: bool = False
    climax: bool = False

    @property
    def heat(self) -> float:
        # Pressure is a dramatic color, never a mechanical outcome selector.
        return max(0.0, min(1.0, self.progress * 0.82 + self.pressure * self.progress * 0.18))

    @property
    def disorder(self) -> float:
        return max(0.0, min(1.0, 1.0 - self.composure))


@dataclass
class VoiceSessionMemory:
    exact: Deque[str] = field(default_factory=lambda: deque(maxlen=42))
    # A three-to-five minute duet is long enough for a familiar sentence to
    # become conspicuous. Keep semantic signatures for almost the full event;
    # evolving motifs still recur through related, not identical, recordings.
    signatures: Deque[str] = field(default_factory=lambda: deque(maxlen=96))
    spoken_texts: Deque[str] = field(default_factory=lambda: deque(maxlen=96))
    families: Deque[str] = field(default_factory=lambda: deque(maxlen=18))
    motifs: Deque[str] = field(default_factory=lambda: deque(maxlen=24))
    peak_used: Set[str] = field(default_factory=set)
    pending_family: Optional[str] = None
    pending_setup: Optional[str] = None
    last_speaker: str = ""
    last_progress: float = 0.0
    exchanges: int = 0
    courtesy_state: str = "baseline"
    commands_obeyed: int = 0
    commands_one_upped: int = 0
    birdsong_locks: int = 0
    fiend_confidence: float = 0.20
    shared_recklessness: float = 0.0
    current_gambit: str = ""
    story_arc: str = ""
    story_beat: int = 0
    length_target: int = 6
    cascade_emotional: float = 0.0
    cascade_intensity: float = 0.0
    cascade_lines_since_interjection: int = 99
    fiend_arc_state: str = "pose"
    fiend_last_motif: str = ""
    fiend_motif_exchange: Dict[str, int] = field(default_factory=dict)
    semantic_turns: Deque[Dict[str, Any]] = field(default_factory=lambda: deque(maxlen=48))
    semantic_exchanges: Deque[Dict[str, Any]] = field(default_factory=lambda: deque(maxlen=24))
    pending_semantic: Optional[Dict[str, Any]] = None

    def reset_event(self) -> None:
        self.exact.clear()
        self.signatures.clear()
        self.spoken_texts.clear()
        self.families.clear()
        self.motifs.clear()
        self.peak_used.clear()
        self.pending_family = None
        self.pending_setup = None
        self.last_speaker = ""
        self.last_progress = 0.0
        self.exchanges = 0
        self.courtesy_state = "baseline"
        self.commands_obeyed = 0
        self.commands_one_upped = 0
        self.birdsong_locks = 0
        self.fiend_confidence = 0.20
        self.shared_recklessness = 0.0
        self.current_gambit = ""
        self.story_arc = ""
        self.story_beat = 0
        self.length_target = 6
        self.cascade_emotional = 0.0
        self.cascade_intensity = 0.0
        self.cascade_lines_since_interjection = 99
        self.fiend_arc_state = "pose"
        self.fiend_last_motif = ""
        self.fiend_motif_exchange.clear()
        self.semantic_turns.clear()
        self.semantic_exchanges.clear()
        self.pending_semantic = None


class IdleVoiceDirector:
    """Selects coherent recorded exchanges without importing Fiendish scenes."""

    RESPONSE_MAP: Dict[str, Tuple[str, ...]] = {
        "challenge": ("reassure", "tease", "answer", "devotion"),
        "question": ("answer", "reassure", "tease", "devotion"),
        "tease": ("tease", "challenge", "reaction", "answer"),
        "request": ("answer", "reassure", "devotion", "reaction"),
        "resistance": ("reassure", "answer", "tease"),
        "reassure": ("reaction", "devotion", "tease"),
        "devotion": ("reaction", "devotion", "tease"),
        "reaction": ("reassure", "tease", "answer"),
        "surrender": ("devotion", "reassure", "reaction", "peak"),
        "peak": ("reaction", "devotion", "peak"),
        "observation": ("answer", "tease", "reaction", "observation"),
        "answer": ("reaction", "tease", "question", "devotion"),
        "bathroom_need": ("reassure", "answer", "tease", "bathroom_attention"),
        "bathroom_attention": ("bathroom_command", "tease", "reaction", "devotion"),
        "bathroom_command": ("answer", "reassure", "reaction", "bathroom_attention"),
        "bathroom_callback": ("reaction", "tease", "devotion", "bathroom_attention"),
    }

    # Recorded-story grammar.  These are semantic beats, not newly generated
    # prose: every performed line still comes from the approved WAV catalog.
    # The plan supplies continuity across several exchanges while the ordinary
    # response map retains local conversational truth.
    STORY_ARCS: Dict[str, Tuple[Tuple[str, ...], ...]] = {
        "private_dare": (
            ("observation", "question"), ("tease", "challenge"),
            ("answer", "reassure"), ("request", "devotion"),
        ),
        "courteous_test": (
            ("request", "question"), ("answer", "reassure"),
            ("tease", "challenge"), ("devotion", "reaction"),
        ),
        "inside_outside": (
            ("tease", "question"), ("resistance", "request"),
            ("reassure", "answer"), ("surrender", "devotion"),
        ),
        "domestic_confession": (
            ("observation", "tease"), ("question", "request"),
            ("answer", "reassure"), ("devotion", "reaction"),
        ),
        "brink_and_return": (
            ("challenge", "request"), ("surrender", "resistance"),
            ("reassure", "answer"), ("devotion", "reaction"),
        ),
    }

    def __init__(self, manager: Any, *, rng: Optional[random.Random] = None, diagnostic: Optional[bool] = None):
        self.manager = manager
        self.rng = rng or random.Random()
        self.memory = VoiceSessionMemory()
        self._curated = self._load_curated_matrix()
        # Runtime-only exposure ledger. It survives event resets on this Ogre
        # process but is never written into a game save.
        self.exposure: Counter[str] = Counter()
        self.group_exposure: Counter[str] = Counter()
        self.family_exposure: Counter[str] = Counter()
        self.catalog: List[VoiceClip] = self._build_catalog()
        self.by_speaker: Dict[str, List[VoiceClip]] = {
            "BIRDSONG": [c for c in self.catalog if c.speaker == "BIRDSONG"],
            "FIEND": [c for c in self.catalog if c.speaker == "FIEND"],
        }
        self._queue: Deque[VoiceClip] = deque()
        self._story_targets: Tuple[str, ...] = ()
        self._event_serial = 0
        if diagnostic is None:
            diagnostic = str(os.environ.get("WOTW_VOICE_DIAGNOSTICS", "0")).lower() in ("1", "true", "yes", "on")
        self.diagnostic = bool(diagnostic)
        self.log_path = self._diagnostic_path()
        self.courteous_ruin = str(os.environ.get("LOCKKEY_COURTEOUS_RUIN", "0")).lower() in ("1", "true", "yes", "on")
        # The pot is not a second voice brain.  The enclosing Idle theater
        # supplies a tiny semantic receipt; this director merely lets the
        # existing recorded vocabulary remember it at the proper point.
        try:
            raw = json.loads(os.environ.get("LOCKKEY_POT_CONTINUITY", "{}") or "{}")
            self.pot_continuity = raw if isinstance(raw, dict) else {}
        except Exception:
            self.pot_continuity = {}
        self.pot_scheduled = str(os.environ.get("LOCKKEY_POT_SCHEDULED", "0")).lower() in ("1", "true", "yes", "on")
        self.pot_musk = str(os.environ.get("LOCKKEY_MUSK_ENABLED", "1")).lower() in ("1", "true", "yes", "on")
        self.pot_urine = str(os.environ.get("LOCKKEY_URINATION_PRESENTATION", "1")).lower() in ("1", "true", "yes", "on")

    @staticmethod
    def _courtesy_register(clip: VoiceClip) -> str:
        text = _norm(clip.transcript)
        combined = " ".join((text, _norm(clip.performed_intent), _norm(clip.prosody), " ".join(clip.tags)))
        if clip.speaker == "BIRDSONG":
            if clip.tier == "texture" or any(x in combined for x in ("babble", "bleat", "goat", "eruption", "incoherent")):
                return "birdsong_lock"
            if any(x in text for x in ("no i mean", "wait i", "i need you", "no i i just")):
                return "sentence_repair"
            if any(x in text for x in ("what if i wanted", "try harder", "make me wait", "if you want", "i could push", "actually mmm deliver")):
                return "coy_escalation"
            if any(x in text for x in ("again", "stay", "keep going", "harder", "right there", "good boy", "not yet", "closer", "hold me tighter", "back out", "give me more", "there you go")):
                return "direct_command"
            return "hana_evaluation"
        if clip.speaker == "FIEND":
            # Fiend's nonliteral noises are personality, not failed speech.
            # Keep their semantic distinctions so the cascade can remember
            # whether he was playful, flustered, animal, or carefully steady.
            if clip.tier == "texture" or any(x in combined for x in ("babble", "animal", "growl", "grunt", "incoherent")):
                return "fiend_animal"
            if any(x in combined for x in ("laugh", "playful", "tease", "silly", "anime", "bright")):
                return "fiend_playful"
            if any(x in text for x in ("breathe", "i've got you", "i am here", "easy", "slow")):
                return "fiend_steady"
            if clip.family in ("reaction", "surrender") or len(text.split()) <= 2:
                return "fiend_flustered"
            return "fiend_response"
        return "baseline"

    @staticmethod
    def _fiend_icarus_features(clip: VoiceClip) -> Tuple[str, str]:
        """Map existing Fiend recordings onto his preserved social rhythm.

        This does not quote or package the private reference songs.  It finds
        the same dramatic actions already present in Fiend's approved catalog:
        borrowed confidence, visible exposure, a sideways recovery, and the
        small sincere thing he cannot quite joke away.
        """
        if clip.speaker != "FIEND":
            return ("", "")
        text = _norm(clip.transcript)
        combined = " ".join((text, _norm(clip.performed_intent), _norm(clip.prosody)))
        if clip.tier == "texture" or any(x in combined for x in ("babble", "growl", "grunt", "incoherent")):
            beat = "animal"
        elif any(x in text for x in (
            "too much", "was it good", "handsome", "don't look at me",
            "would you prefer", "can i", "i don't know tell me", "i'm really not",
            "should i", "um hey", "um so",
        )):
            beat = "exposed"
        elif any(x in text for x in (
            "fair point", "dramatic", "noted", "thinking too loud", "i said nothing",
            "withholdee", "greedy", "double or nothing", "i narrate", "true things",
            "and yet", "or what", "please what",
        )):
            beat = "side_smile"
        elif any(x in text for x in (
            "favorite person", "beautiful", "big deal", "home now", "always with you",
            "with me always", "still here", "take responsibility", "i've got you",
            "stay with me", "all of you", "i wanted all of you",
        )):
            beat = "sincere"
        else:
            beat = "pose"

        motif = ""
        motif_terms = (
            ("word", ("word", "say it", "tell me")),
            ("home", ("home", "still here", "i'm back")),
            ("seeing", ("look", "see", "beautiful", "handsome")),
            ("keeping", ("stay", "with me", "got you", "all of you")),
            ("permission", ("asked", "command", "can i", "promise")),
            ("truth", ("true", "thinking", "said nothing", "responsibility")),
        )
        for name, needles in motif_terms:
            if any(needle in text for needle in needles):
                motif = name
                break
        return (beat, motif)

    @staticmethod
    def _fiend_private_lock_reject(clip: VoiceClip) -> bool:
        """Exclude transcript-corrupted or out-of-world Fiend recordings.

        The source audio is preserved untouched. These clips remain available
        to archival tools, but the authored Idle persona may not select lines
        whose ASR text reveals a recording session, a timer exercise, modern
        manipulation language, religious boilerplate, or obvious word salad.
        """
        if clip.speaker != "FIEND":
            return False
        text = _norm(clip.transcript)
        blocked = (
            "thanks for watching", "next video", "20 seconds", "twenty seconds",
            "clock starts now", "new game", "god is always", "stop existing",
            "being manipulated", "06 00", "kareem", "yoga center",
            "rest sock", "gizmos", "intrastaia", "chachamuner",
            "certain breasts die", "shallower chagr",
        )
        return any(x in text for x in blocked)

    @staticmethod
    def _fiend_arc_next(beat: str) -> str:
        return {
            "pose": "exposed",
            "exposed": "side_smile",
            "side_smile": "sincere",
            "sincere": "pose",
            "animal": "side_smile",
        }.get(beat, "pose")

    def observe_cascade(self, cascade_context: Dict[str, Any]) -> None:
        """Accept Cascade memory without importing its modal machinery."""
        try:
            trajectory = dict(cascade_context.get("trajectory") or {})
            self.memory.cascade_emotional = float(trajectory.get("emotional", 0.0) or 0.0)
            self.memory.cascade_intensity = float(trajectory.get("intensity", 0.0) or 0.0)
            self.memory.cascade_lines_since_interjection = int(cascade_context.get("lines_since_interjection", 99) or 0)
        except Exception:
            pass

    def _advance_courtesy_state(self, ctx: VoiceContext) -> None:
        if not self.courteous_ruin:
            return
        m = self.memory
        relationship=getattr(self,"relationship",None)
        spiral=float(getattr(relationship,"animal_spiral",0.0) or 0.0)
        disorder=max(ctx.disorder,float(getattr(relationship,"animal_spiral",0.0) or 0.0))
        if ctx.climax:
            m.courtesy_state = "final_brink"
        elif disorder>=0.68 or spiral>=0.52:
            # Late heat remains conversational. More exchanges become coy and
            # vocal, but Fiend still waits for an authored register.
            if m.exchanges%4==0:
                m.courtesy_state="coy_escalation"
            elif m.last_speaker=="BIRDSONG":
                m.courtesy_state="fiend_response"
            elif m.exchanges%3==0:
                m.courtesy_state="birdsong_lock"
            else:
                m.courtesy_state="direct_command"
        elif m.courtesy_state == "birdsong_lock":
            m.courtesy_state = "settle"
        elif m.exchanges % 5 == 4:
            m.courtesy_state = "coy_escalation"
        elif m.exchanges % 3 == 1:
            m.courtesy_state = "direct_command"
        elif m.last_speaker == "BIRDSONG":
            m.courtesy_state = "fiend_response"
        else:
            m.courtesy_state = "hana_evaluation"
        m.fiend_confidence = min(1.0, 0.20 + m.exchanges * 0.035)
        m.shared_recklessness = min(1.0, ctx.heat * (0.55 + m.fiend_confidence * 0.45))

    def _story_families(self, ctx: VoiceContext) -> Tuple[str, ...]:
        """Return the current multi-exchange story beat and advance safely."""
        m=self.memory
        if not m.story_arc or m.story_arc not in self.STORY_ARCS:
            if self.pot_continuity:
                m.story_arc="domestic_confession"
            elif ctx.disorder>=0.62:
                m.story_arc="brink_and_return"
            else:
                m.story_arc=self.rng.choice(("private_dare","courteous_test","inside_outside","domestic_confession"))
            m.story_beat=0
        beats=self.STORY_ARCS[m.story_arc]
        families=beats[m.story_beat % len(beats)]
        m.story_beat+=1
        if m.story_beat>=len(beats):
            # Let an arc land before choosing another; a high-risk scene may
            # naturally select the brink story on its next exchange.
            m.story_arc=""
            m.story_beat=0
        return families

    def _load_curated_matrix(self) -> Dict[str, Dict[str, Any]]:
        try:
            path = Path(__file__).resolve().parent / "voice_catalog_matrix.json"
            raw = json.loads(path.read_text(encoding="utf-8"))
            return {str(row.get("file")): row for row in (raw.get("clips") or []) if isinstance(row, dict) and row.get("file")}
        except Exception:
            return {}

    def _diagnostic_path(self) -> Path:
        base = getattr(self.manager, "cache_dir", None) or Path.cwd()
        return Path(base) / "idle_voice_brain_diagnostic.jsonl"

    def _duration(self, path: Path) -> float:
        try:
            from voice_engine import wav_duration_seconds
            return float(wav_duration_seconds(path) or 0.0)
        except Exception:
            return 0.0

    @staticmethod
    def _speaker(meta: Dict[str, Any], path: Path) -> str:
        raw = str(meta.get("speaker") or "").upper()
        name = path.name.upper()
        if "FIEND" in raw or "FIEND" in name:
            return "FIEND"
        if "BIRD" in raw or "BIRD" in name or "HANA" in raw:
            return "BIRDSONG"
        return ""

    @staticmethod
    def classify(transcript: str, tags: Sequence[str]) -> Tuple[str, str, float, float, float, int, Tuple[str, ...]]:
        t = _norm(transcript)
        tag_text = " ".join(str(x).lower() for x in tags)
        combined = t + " " + tag_text
        words = t.split()
        intelligibility = 0.25 if not t else min(1.0, 0.48 + len(words) * 0.055)
        if len(words) <= 2:
            intelligibility *= 0.72
        if re.search(r"(.)\1{3,}", t):
            intelligibility *= 0.82

        peak_terms = ("baka", "ba ah ka", "climax", "come", "coming", "can't take", "cannot take", "too much")
        surrender_terms = ("please", "more", "don't stop", "dont stop", "yes", "take me", "all yours")
        reassure_terms = ("safe", "got you", "breathe", "with you", "right here", "it's okay", "its okay")
        devotion_terms = ("love", "mine", "yours", "always", "need you", "want you")
        resist_terms = ("stop", "wait", "hold on", "not yet", "slow", "careful")
        challenge_terms = ("try me", "you won't", "you wont", "prove", "coward", "tease", "actually")
        question_terms = ("why", "what", "how", "really", "are you", "do you", "can you")
        answer_terms = ("i will", "i am", "because", "of course", "yes i", "no i")
        reaction_terms = ("oh", "ah", "mm", "mhm", "ngh", "hah", "fuck")
        bathroom_need_terms = ("bathroom", "have to go", "need to go", "now now", "can't hold", "cannot hold", "privy")
        bathroom_command_terms = ("clench", "let go", "take your time", "breathe", "again", "there you go")
        bathroom_attention_terms = ("watch", "looking", "staring", "don't look", "dont look", "help me", "hand me")

        peak = 0
        if _contains(combined, peak_terms):
            peak = 2 if _contains(combined, ("baka", "ba ah ka", "climax", "coming")) else 1

        if _contains(combined, bathroom_need_terms):
            family, role, lo, hi = "bathroom_need", "setup", 0.58, 1.0
        elif _contains(combined, bathroom_command_terms) and _contains(combined, ("clench", "let go", "take your time")):
            family, role, lo, hi = "bathroom_command", "setup", 0.18, 0.96
        elif _contains(combined, bathroom_attention_terms):
            family, role, lo, hi = "bathroom_attention", "either", 0.08, 0.95
        elif peak >= 2:
            family, role, lo, hi = "peak", "payoff", 0.78, 1.0
        elif _contains(combined, surrender_terms):
            family, role, lo, hi = "surrender", "payoff", 0.55, 1.0
        elif _contains(combined, reassure_terms):
            family, role, lo, hi = "reassure", "response", 0.05, 0.95
        elif _contains(combined, devotion_terms):
            family, role, lo, hi = "devotion", "response", 0.25, 1.0
        elif _contains(combined, resist_terms):
            family, role, lo, hi = "resistance", "setup", 0.05, 0.78
        elif _contains(combined, challenge_terms):
            family, role, lo, hi = "challenge", "setup", 0.12, 0.84
        elif "?" in transcript or _contains(combined, question_terms):
            family, role, lo, hi = "question", "setup", 0.05, 0.82
        elif _contains(combined, answer_terms):
            family, role, lo, hi = "answer", "response", 0.05, 0.95
        elif _contains(combined, reaction_terms) or len(words) <= 3:
            family, role, lo, hi = "reaction", "response", 0.12, 1.0
        elif "tease" in combined or "brat" in combined:
            family, role, lo, hi = "tease", "setup", 0.08, 0.9
        else:
            family, role, lo, hi = "observation", "either", 0.0, 0.88
        responses = IdleVoiceDirector.RESPONSE_MAP.get(family, ("reaction", "answer", "tease"))
        return family, role, lo, hi, intelligibility, peak, responses

    def _build_catalog(self) -> List[VoiceClip]:
        out: List[VoiceClip] = []
        seen: Set[str] = set()
        tags_by_name = getattr(self.manager, "voice_tags", {}) or {}
        paths: List[Path] = []
        for values in (getattr(self.manager, "voice_catalog", {}) or {}).values():
            for path in values or []:
                p = Path(path)
                if p.name not in seen:
                    seen.add(p.name)
                    paths.append(p)
        for path in paths:
            meta = tags_by_name.get(path.name, {}) if isinstance(tags_by_name, dict) else {}
            curated = self._curated.get(path.name, {})
            transcript = str(meta.get("transcript") or meta.get("text") or "").strip()
            speaker = self._speaker(meta, path)
            if not transcript or not speaker:
                continue
            tier = str(curated.get("tier") or "conversation")
            if tier == "questionable":
                continue
            tags = tuple(str(x) for x in (meta.get("tags") or []) if x)
            family, role, lo, hi, intel, peak, responses = self.classify(transcript, tags)
            prosody = str(curated.get("prosody") or "neutral_spoken")
            if prosody == "birdsong_hot_whine":
                family, role, lo, hi, peak = "peak", "payoff", 0.78, 1.0, 2
                responses = self.RESPONSE_MAP["peak"]
            elif prosody == "birdsong_bright_probe":
                family, role, lo, hi, peak = "challenge", "setup", 0.05, 0.78, 0
                responses = self.RESPONSE_MAP["challenge"]
            elif tier == "texture":
                # Opaque dialect and babble remain valid performed responses.
                # Never pretend their uncertain transcript is a full setup.
                family, role, peak = "reaction", "response", 0
                if prosody in ("breathy_extended", "short_reaction_bright"):
                    lo, hi = 0.34, 1.0
                else:
                    lo, hi = 0.0, 0.92
                responses = self.RESPONSE_MAP["reaction"]
            out.append(VoiceClip(
                path=path, speaker=speaker, transcript=transcript, normalized=_norm(transcript),
                signature=_stemmed_signature(transcript), family=family, role=role,
                intensity_min=lo, intensity_max=hi, intelligibility=intel,
                # WAV duration is intentionally lazy. Reading 2,349 headers at
                # first voice use caused a visible hitch; playback resolves the
                # duration for the single selected recording.
                peak_value=peak, duration=0.0, tags=tags,
                response_families=tuple(responses), tier=tier, prosody=prosody,
                duplicate_group=str(curated.get("duplicate_group") or (speaker + "|" + _stemmed_signature(transcript))),
                performed_intent=str(curated.get("performed_intent") or "neutral_statement"),
            ))
        return out

    def begin_event(self) -> None:
        self.memory.reset_event()
        self._queue.clear()
        self._event_serial += 1

    @staticmethod
    def _semantic_intent(clip: VoiceClip) -> str:
        """Translate a performed recording into a small authored vocabulary.

        Curated metadata and performance register are authoritative.  Text is
        used only to distinguish directions inside an already-authored command;
        it is never treated as a magic achievement keyword.
        """
        register = IdleVoiceDirector._courtesy_register(clip)
        text = _norm(clip.transcript)
        authored = _norm(clip.performed_intent)
        if clip.speaker == "BIRDSONG":
            if authored == "late yielding whine":
                return "pleased_eruption"
            if authored == "breathy escalation" and register not in ("direct_command", "sentence_repair"):
                return "coy_permission"
            if register == "direct_command":
                if _contains(text, ("back out", "not yet", "wait", "slow", "easy")):
                    return "request_back_down"
                if _contains(text, ("again", "keep going", "harder", "right there", "closer", "stay")):
                    return "invite_continue"
                return "direct_permission"
            if register == "coy_escalation":
                return "coy_permission"
            if register == "sentence_repair":
                return "uncertain_correction"
            if register == "birdsong_lock":
                return "pleased_eruption"
            if _contains(authored, ("warning", "consequence", "risk")):
                return "consequence_warning"
            return "evaluation"
        if register == "fiend_steady" or clip.family == "reassure":
            return "reassurance"
        if authored == "breathy escalation":
            return "accepted_invitation"
        if register == "fiend_animal":
            return "animal_answer"
        if register in ("fiend_playful", "fiend_flustered"):
            return "playful_one_up"
        if clip.family in ("answer", "devotion", "surrender"):
            return "accepted_invitation"
        return "attentive_answer"

    @staticmethod
    def _response_posture(prompt: str, answer: str) -> str:
        if prompt == "request_back_down" and answer in ("reassurance", "attentive_answer", "accepted_invitation"):
            return "honored_back_down"
        if prompt in ("invite_continue", "direct_permission", "coy_permission") and answer in (
            "accepted_invitation", "attentive_answer", "playful_one_up", "animal_answer"
        ):
            return "accepted_escalation"
        if prompt in ("uncertain_correction", "consequence_warning") and answer in (
            "reassurance", "attentive_answer"
        ):
            return "listened_carefully"
        if prompt == "pleased_eruption" and answer in ("animal_answer", "playful_one_up", "accepted_invitation"):
            return "answered_birdsong"
        return "connected_reply"

    def _record_semantic_turn(self, clip: VoiceClip) -> None:
        intent = self._semantic_intent(clip)
        turn = {
            "speaker": clip.speaker,
            "intent": intent,
            "clip_id": clip.clip_id,
            "family": clip.family,
            "performed_intent": clip.performed_intent,
        }
        self.memory.semantic_turns.append(turn)
        pending = self.memory.pending_semantic
        if pending and pending.get("speaker") != clip.speaker:
            exchange = {
                "speaker_intent": pending.get("intent", ""),
                "listener_response": intent,
                "response_posture": self._response_posture(str(pending.get("intent", "")), intent),
                "prompt_speaker": pending.get("speaker", ""),
                "answer_speaker": clip.speaker,
                "connected": True,
            }
            self.memory.semantic_exchanges.append(exchange)
        self.memory.pending_semantic = turn

    def semantic_snapshot(self) -> Dict[str, Any]:
        exchanges = list(self.memory.semantic_exchanges)
        turns = list(self.memory.semantic_turns)
        postures = {str(row.get("response_posture", "")) for row in exchanges}
        intents = [str(row.get("intent", "")) for row in turns]
        relationship = getattr(self, "relationship", None)
        rel = relationship.snapshot() if relationship is not None else {}
        return {
            "version": 1,
            "voices_heard": len(turns),
            "connected_exchanges": len(exchanges),
            "both_creatures_talking": {row.get("speaker") for row in turns} >= {"BIRDSONG", "FIEND"},
            "honored_back_down": "honored_back_down" in postures,
            "accepted_escalation": "accepted_escalation" in postures,
            "listened_carefully": "listened_carefully" in postures,
            "answered_birdsong": "answered_birdsong" in postures,
            "birdsong_eruption": "pleased_eruption" in intents,
            "coy_permission_heard": "coy_permission" in intents,
            "direct_permission_heard": "direct_permission" in intents or "invite_continue" in intents,
            "commands_obeyed": int(rel.get("commands_obeyed", 0) or 0),
            "pleased_one_ups": int(getattr(relationship, "pleased_one_ups", 0) or 0) if relationship else 0,
            "adult_mutual_context": True,
            "recent_exchanges": exchanges[-8:],
        }

    def end_event(self) -> None:
        self.begin_event()

    def _motif(self, clip: VoiceClip) -> str:
        tokens = sorted(_tokens(clip.transcript))
        return " ".join(tokens[:3]) or clip.family

    def _repeat_penalty(self, clip: VoiceClip) -> float:
        m = self.memory
        if clip.clip_id in m.exact:
            return 100.0
        if clip.normalized and clip.normalized in m.spoken_texts:
            return 100.0
        if clip.signature and clip.signature in m.signatures:
            return 80.0
        if clip.signature and any(_near_duplicate(clip.signature, old) for old in m.signatures):
            return 65.0
        penalty = 0.0
        recent_families = list(m.families)
        for distance, fam in enumerate(reversed(recent_families), 1):
            if fam == clip.family:
                penalty += max(0.4, 3.2 - distance * 0.35)
                break
        motif = self._motif(clip)
        if motif in m.motifs:
            penalty += 12.0
        if clip.peak_value and clip.clip_id in m.peak_used:
            penalty += 100.0
        return penalty

    def _score(self, clip: VoiceClip, ctx: VoiceContext, *, desired_speaker: str,
               desired_families: Sequence[str], first: bool) -> Tuple[float, Dict[str, float]]:
        heat = ctx.heat
        parts: Dict[str, float] = {}
        if clip.speaker != desired_speaker:
            return -999.0, {"speaker": -999.0}
        if self.courteous_ruin and self._fiend_private_lock_reject(clip):
            return -999.0, {"fiend_private_lock": -999.0}
        if heat + 0.12 < clip.intensity_min or heat - 0.16 > clip.intensity_max:
            parts["phase"] = -5.5
        else:
            parts["phase"] = 1.6 - abs(((clip.intensity_min + clip.intensity_max) / 2.0) - heat)
        parts["intelligibility"] = clip.intelligibility * 2.5
        parts["compatibility"] = 3.4 if clip.family in desired_families else 0.0
        if first and clip.role == "setup":
            parts["role"] = 1.2
        elif not first and clip.role in ("response", "payoff"):
            parts["role"] = 1.5
        else:
            parts["role"] = 0.0
        # Babble/opaque texture may answer a line, never lead an exchange as if
        # Whisper had recovered a reliable proposition.
        if clip.tier == "texture":
            parts["texture_gate"] = -100.0 if first else -0.65
        # Signature phrases are dramaturgical resources, not ordinary vocabulary.
        if clip.peak_value >= 2:
            eligible = ctx.climax or heat >= 0.86
            parts["peak_gate"] = (4.0 + ctx.pressure * 1.1) if eligible else -100.0
        elif clip.peak_value == 1:
            parts["peak_gate"] = 1.4 if heat >= 0.70 else -5.0
        parts["repeat"] = -self._repeat_penalty(clip)
        used = int(self.exposure.get(clip.clip_id, 0))
        group_used = int(self.group_exposure.get(clip.duplicate_group, 0)) if clip.duplicate_group else 0
        family_used = int(self.family_exposure.get(clip.family, 0))
        parts["discovery"] = 4.2 if used == 0 else -(2.1 * min(5, used))
        parts["variant_exposure"] = -(1.25 * min(5, group_used))
        parts["family_exposure"] = -(0.08 * min(20, family_used))
        parts["jitter"] = self.rng.uniform(0.0, 1.25)
        if self.courteous_ruin:
            register = self._courtesy_register(clip)
            wanted = self.memory.courtesy_state
            parts["courtesy"] = 5.0 if register == wanted else 0.0
            if clip.family in self._story_targets:
                # Story is a preference inside conversational grammar, never
                # permission to ignore the preceding recorded line.
                parts["story_beat"] = 2.8
            if register == "birdsong_lock":
                earned = wanted == "birdsong_lock" or ctx.climax or self.memory.commands_one_upped > self.memory.birdsong_locks
                parts["birdsong_gate"] = 4.5 if earned else -100.0
            # GLINT/Ghostheart's useful principle: coherent speech owns the
            # composed scene; fragments become truthful as composure breaks.
            # This prevents tiny lines such as "breathe" from crowding out
            # Fiend's real vocabulary at the beginning of every encounter.
            words=len(clip.normalized.split())
            disorder=ctx.disorder
            noisy=(clip.tier=="texture" or clip.family=="reaction" or words<=2)
            if noisy:
                parts["composure_register"] = -7.5*(1.0-disorder) + 5.0*disorder
            else:
                parts["composure_register"] = 2.8*(1.0-disorder)
            if clip.speaker=="FIEND":
                if words>=5:
                    parts["fiend_substance"] = 2.7*(1.0-disorder)+0.7
                elif words<=2:
                    parts["fiend_fragment_reserve"] = -5.0*(1.0-disorder)
                register = self._courtesy_register(clip)
                # Cascade turns Fiend's noises into an earned character beat:
                # composed runs prefer his articulate courtesy; rising motion
                # invites playful/animal cracks without making him random.
                cascade_heat=max(0.0,min(1.0,
                    0.5 + self.memory.cascade_emotional*0.35 + self.memory.cascade_intensity*2.0))
                if register in ("fiend_playful", "fiend_animal", "fiend_flustered"):
                    parts["fiend_personality"] = -2.2*(1.0-disorder) + 3.6*max(disorder,cascade_heat)
                elif register in ("fiend_response", "fiend_steady"):
                    parts["fiend_personality"] = 1.5*(1.0-max(disorder,cascade_heat))
                beat, motif = self._fiend_icarus_features(clip)
                wanted_beat = self.memory.fiend_arc_state
                # The arc is a preference, not a script. Local response
                # grammar remains authoritative, but Fiend now tends to build
                # a pose, leak, notice it, smile sideways, and leave one true
                # thing behind before trying the pose again.
                if beat == wanted_beat:
                    parts["fiend_authored_arc"] = 4.4
                elif beat == "animal" and disorder >= 0.54:
                    parts["fiend_authored_arc"] = 2.8
                elif beat == "sincere" and wanted_beat not in ("sincere", "side_smile"):
                    parts["fiend_authored_arc"] = -3.2
                else:
                    parts["fiend_authored_arc"] = 0.0
                if motif:
                    last_at = self.memory.fiend_motif_exchange.get(motif, -99)
                    distance = self.memory.exchanges - last_at
                    # A returning image changes meaning after the conversation
                    # has moved. Immediate repetition remains penalized by the
                    # ordinary duplicate guards above.
                    if 3 <= distance <= 12:
                        parts["fiend_lore_callback"] = 2.2
            # Vary actual sentence length instead of making every exchange a
            # pair of interchangeable barks. Long recorded thoughts are most
            # valuable while composed; the target shortens as language breaks.
            target=max(2,int(self.memory.length_target or 6))
            distance=abs(words-target)
            parts["length_shape"]=max(-2.0,2.4-distance*0.28)
            if words>=9 and disorder<0.48 and clip.tier=="conversation":
                parts["long_form"] = 2.2
        pot_family = clip.family.startswith("bathroom_")
        if pot_family:
            if self.pot_scheduled and ctx.progress >= 0.72:
                # Urgency belongs at the end only when the interlude will
                # really follow.  Never leak it into pot-off sessions.
                parts["pot_scheduled"] = 8.0 + ctx.progress * 3.0
            elif self.pot_continuity and ctx.progress <= 0.38:
                parts["pot_callback"] = 7.0 - ctx.progress * 5.0
            else:
                parts["pot_gate"] = -100.0
        elif self.pot_continuity and ctx.progress <= 0.30:
            # Ordinary affection remains eligible, but one true callback gets
            # first claim rather than allowing the receipt to dominate a run.
            parts["pot_ordinary_early"] = -1.2
        if not self.pot_musk and _contains(clip.transcript, ("toot", "fart", "gas", "stomach growl", "stomach is growling")):
            parts["musk_filter"] = -100.0
        if not self.pot_urine and _contains(clip.transcript, ("pee", "piss", "urine", "stream", "leak")):
            parts["urine_filter"] = -100.0
        return sum(parts.values()), parts

    def _choose(self, ctx: VoiceContext, *, speaker: str, desired: Sequence[str], first: bool,
                excluded: Sequence[VoiceClip] = ()) -> Optional[VoiceClip]:
        scored: List[Tuple[float, VoiceClip, Dict[str, float]]] = []
        excluded_ids = {c.clip_id for c in excluded}
        excluded_signatures = {c.signature for c in excluded if c.signature}
        for clip in self.by_speaker.get(speaker, []):
            if clip.clip_id in excluded_ids or (clip.signature and clip.signature in excluded_signatures):
                continue
            score, parts = self._score(clip, ctx, desired_speaker=speaker, desired_families=desired, first=first)
            scored.append((score, clip, parts))
        if not scored:
            return None
        compatible = [row for row in scored if row[1].family in desired and row[0] > -20.0]
        if compatible:
            scored = compatible
        texture_chance=0.03+0.52*ctx.disorder
        if not first and self.rng.random() < texture_chance:
            performed_texture = [row for row in scored if row[1].tier == "texture" and row[0] > -20.0]
            if performed_texture:
                scored = performed_texture
        scored.sort(key=lambda row: row[0], reverse=True)
        viable = [row for row in scored[:96] if row[0] > -20.0]
        if not viable:
            return None
        # Stratified quality sampling: strong lines remain common, while an
        # approved second tier can actually surface instead of losing forever
        # to the same eight winners.
        bands = (viable[:12], viable[12:40], viable[40:96])
        chances = (0.46, 0.34, 0.20)
        roll = self.rng.random(); acc = 0.0; band = bands[0]
        for candidate_band, chance in zip(bands, chances):
            acc += chance
            if roll <= acc and candidate_band:
                band = candidate_band
                break
        weights = [max(0.08, row[0] - band[-1][0] + 0.25) for row in band]
        selected = self.rng.choices(band, weights=weights, k=1)[0]
        self._log("select", ctx, selected[1], selected[2], alternatives=[x[1].clip_id for x in viable[:4]])
        return selected[1]

    def _seed_families(self, ctx: VoiceContext) -> Tuple[str, ...]:
        heat = ctx.heat
        if self.pot_scheduled and ctx.progress >= 0.78:
            return ("bathroom_need", "bathroom_attention", "tease", "reassure", "reaction")
        if self.pot_continuity and ctx.progress <= 0.30:
            return ("bathroom_callback", "bathroom_attention", "bathroom_command", "tease", "devotion", "reaction")
        if ctx.climax or heat >= 0.88:
            return ("surrender", "peak", "devotion", "reaction")
        if heat >= 0.64:
            return ("challenge", "tease", "request", "devotion", "surrender")
        if heat >= 0.32:
            return ("tease", "question", "challenge", "devotion", "observation")
        return ("observation", "tease", "question", "reassure")

    def build_exchange(self, ctx: VoiceContext, length: int = 2) -> List[VoiceClip]:
        # A new event is detected without requiring Ogre Shader architecture changes.
        if ctx.progress + 0.20 < self.memory.last_progress:
            self.begin_event()
        self.memory.last_progress = ctx.progress
        self._advance_courtesy_state(ctx)
        story_families=self._story_families(ctx) if self.courteous_ruin else ()
        self._story_targets=tuple(story_families)
        # A scene should breathe between compact reactions and complete
        # thoughts.  At low composure, articulate monologues become rarer.
        if ctx.disorder<0.34:
            self.memory.length_target=self.rng.choices((4,7,11,16),(0.18,0.34,0.34,0.14))[0]
        elif ctx.disorder<0.68:
            self.memory.length_target=self.rng.choices((3,6,10),(0.34,0.46,0.20))[0]
        else:
            self.memory.length_target=self.rng.choices((2,4,7),(0.52,0.36,0.12))[0]
        # Fiend is a conversational participant, not a permanent response
        # socket.  He may initiate when composed and may carry a three-beat
        # exchange; disorder gradually returns both voices to short answers.
        if self.memory.last_speaker=="BIRDSONG":
            speaker="FIEND"
        elif self.memory.last_speaker=="FIEND":
            fiend_initiates=self.rng.random() < (0.30*(1.0-ctx.disorder)+0.08)
            speaker="FIEND" if fiend_initiates else "BIRDSONG"
        else:
            speaker="FIEND" if self.rng.random()<0.34 else "BIRDSONG"
        response_families=tuple(self.RESPONSE_MAP.get(self.memory.pending_family or "", ()))
        desired_first=response_families or tuple(story_families)
        # The conversation remains responsive, while the dramatic arc gradually
        # expands which truthful responses may enter.  This prevents an early
        # question/reassurance loop from trapping the whole three-minute scene.
        if not desired_first or ctx.heat >= 0.34:
            desired_first = tuple(dict.fromkeys(desired_first + self._seed_families(ctx)))
        first = self._choose(ctx, speaker=speaker, desired=desired_first, first=True)
        if first is None:
            return []
        result = [first]
        next_speaker = "FIEND" if first.speaker == "BIRDSONG" else "BIRDSONG"
        desired = first.response_families
        for turn_index in range(max(0, int(length) - 1)):
            reply = self._choose(ctx, speaker=next_speaker, desired=desired, first=False, excluded=result)
            if reply is None:
                break
            result.append(reply)
            desired = reply.response_families
            # Rare same-speaker codas create genuine monologue-length
            # variation. They only occur while composed, after an articulate
            # line, and never twice in one exchange.
            coda=(turn_index==0 and ctx.disorder<0.42 and
                  len(reply.normalized.split())>=5 and self.rng.random()<0.18)
            next_speaker = reply.speaker if coda else ("FIEND" if reply.speaker == "BIRDSONG" else "BIRDSONG")
        self.memory.exchanges += 1
        return result

    def next_clip(self, ctx: VoiceContext) -> Optional[VoiceClip]:
        if ctx.paused:
            return None
        if not self._queue:
            # Composed exchanges sometimes have room for call / answer / coda.
            # At the brink, clipped alternation is the point rather than a
            # catalog failure.
            roll=self.rng.random()
            if roll < 0.10*(1.0-ctx.disorder):
                length=5
            elif roll < 0.34*(1.0-ctx.disorder):
                length=4
            elif roll < 0.62*(1.0-ctx.disorder):
                length=3
            else:
                length=2
            self._queue.extend(self.build_exchange(ctx, length=length))
        return self._queue.popleft() if self._queue else None

    def note_played(self, clip: VoiceClip) -> None:
        m = self.memory
        m.exact.append(clip.clip_id)
        if clip.normalized:
            m.spoken_texts.append(clip.normalized)
        if clip.signature:
            m.signatures.append(clip.signature)
        m.families.append(clip.family)
        m.motifs.append(self._motif(clip))
        if clip.peak_value:
            m.peak_used.add(clip.clip_id)
        self.exposure[clip.clip_id] += 1
        if clip.duplicate_group:
            self.group_exposure[clip.duplicate_group] += 1
        self.family_exposure[clip.family] += 1
        self._record_semantic_turn(clip)
        m.pending_family = clip.family
        m.pending_setup = clip.transcript if clip.role == "setup" else None
        m.last_speaker = clip.speaker
        if clip.speaker == "FIEND":
            beat, motif = self._fiend_icarus_features(clip)
            if beat:
                m.fiend_arc_state = self._fiend_arc_next(beat)
            if motif:
                m.fiend_last_motif = motif
                m.fiend_motif_exchange[motif] = m.exchanges
        if clip.family.startswith("bathroom_"):
            # One early callback is enough to establish memory.  Later speech
            # returns to the live encounter instead of recapping the privy.
            self.pot_continuity = {}
        relationship=getattr(self,"relationship",None)
        if relationship is not None:
            try:
                relationship.observe_voice(
                    clip.speaker,clip.transcript,
                    self._courtesy_register(clip),clip.prosody,
                )
            except Exception:
                pass
        if self.courteous_ruin:
            register = self._courtesy_register(clip)
            m.courtesy_state = register
            if register == "direct_command":
                m.current_gambit = clip.transcript
            elif register.startswith("fiend_") and m.current_gambit:
                if self.rng.random() < (0.12 + m.fiend_confidence * 0.24):
                    m.commands_one_upped += 1
                    m.courtesy_state = "birdsong_lock"
                else:
                    m.commands_obeyed += 1
                    m.courtesy_state = "hana_evaluation"
            elif register == "birdsong_lock":
                m.birdsong_locks += 1
                m.current_gambit = ""

    def pause_hold(self) -> None:
        """Preserve thread/memory while preventing queued physical-state chatter."""
        self._queue.clear()

    def _log(self, event: str, ctx: VoiceContext, clip: VoiceClip,
             score_parts: Dict[str, float], **extra: Any) -> None:
        if not self.diagnostic:
            return
        row = {
            "ts": round(time.time(), 3), "event": event, "event_serial": self._event_serial,
            "progress": round(ctx.progress, 4), "pressure": round(ctx.pressure, 4),
            "heat": round(ctx.heat, 4), "composure": round(ctx.composure, 4),
            "disorder": round(ctx.disorder, 4), "clip": clip.clip_id, "speaker": clip.speaker,
            "transcript": clip.transcript, "family": clip.family, "role": clip.role,
            "peak": clip.peak_value, "score": score_parts,
            "profile": "courteous_ruin" if self.courteous_ruin else "standard_idle",
            "courtesy_state": self.memory.courtesy_state,
        }
        row.update(extra)
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        except Exception:
            pass


def quality_report(director: IdleVoiceDirector, sessions: int = 100, seed: int = 1337) -> Dict[str, Any]:
    """Offline selection simulation used by tests and release verification."""
    rng = random.Random(seed)
    director.rng = rng
    exact_repeats = near_repeats = early_peak = duplicate_peak = incompatible = arc_transitions = 0
    total = 0
    unique: Set[str] = set()
    families: Counter[str] = Counter()
    for session in range(max(1, int(sessions))):
        director.begin_event()
        prior: Optional[VoiceClip] = None
        seen_peak: Set[str] = set()
        for step in range(24):
            progress = step / 23.0
            ctx = VoiceContext(progress=progress, pressure=(session % 11) / 10.0, climax=step >= 22)
            clip = director.next_clip(ctx)
            if clip is None:
                continue
            total += 1
            unique.add(clip.clip_id)
            families[clip.family] += 1
            if prior and clip.clip_id == prior.clip_id:
                exact_repeats += 1
            if prior and clip.signature and _near_duplicate(clip.signature, prior.signature):
                near_repeats += 1
            if clip.peak_value >= 2 and progress < 0.72:
                early_peak += 1
            if clip.peak_value and clip.clip_id in seen_peak:
                duplicate_peak += 1
            if prior and clip.family not in prior.response_families:
                if clip.family in director._seed_families(ctx):
                    arc_transitions += 1
                else:
                    incompatible += 1
            if clip.peak_value:
                seen_peak.add(clip.clip_id)
            director.note_played(clip)
            prior = clip
    return {
        "sessions": sessions, "total_lines": total, "unique_clips": len(unique),
        "unique_ratio": round(len(unique) / max(1, total), 4),
        "exact_adjacent_repeats": exact_repeats, "near_adjacent_repeats": near_repeats,
        "early_peak_leaks": early_peak, "duplicate_peak_uses": duplicate_peak,
        "incompatible_transitions": incompatible, "authored_arc_transitions": arc_transitions,
        "families": dict(families),
        "catalog_size": len(director.catalog),
    }
