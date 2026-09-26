#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
                    UNIFIED DIALOGUE SYSTEM
                    
    WIRES TOGETHER:
    ├── infinite_dialogue_grammar.py (cascade rules, energy flow)
    ├── reaction_leakage_engine.py (NLS injection, state push)  
    ├── interjection_engine.py (semantic interjection profiles)
    └── All feeding into AuthoredDialogue for main game
    
    THE FULL PIPELINE:
    1. CascadeState tracks conversation energy/composure
    2. Leakage engine tracks Birdsong emotional state  
    3. Both inform dialogue selection
    4. Selected dialogue passes through leakage for NLS injection
    5. Leaks feed back to both cascade and emotional state
    
═══════════════════════════════════════════════════════════════════════════════
"""

import random
from typing import List, Tuple, Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


import os
import json
import time
from pathlib import Path
# ═══════════════════════════════════════════════════════════════════════════════
#                    IMPORTS FROM SUBSYSTEMS
# ═══════════════════════════════════════════════════════════════════════════════

# Try to import all subsystems
GRAMMAR_AVAILABLE = False
LEAKAGE_AVAILABLE = False
INTERJECTION_AVAILABLE = False

try:
    from infinite_dialogue_grammar import (
        CascadeState,
        cascade_response,
        get_response_parameters,
        generate_exchange,
        exchange_to_tuples,
        AssembledLine,
        BIRDSONG_CORES,
        FIEND_CORES,
        assemble_birdsong_line,
        assemble_fiend_line,
        SentenceCore,
    )
    GRAMMAR_AVAILABLE = True
except ImportError as e:
    print(f"Grammar not available: {e}")

try:
    from reaction_leakage_engine import (
        IntegratedLeakageEngine,
        ReactionLeakageEngine,
        FiendGambit,
        FiendTool,
        get_nls,
        ALL_NLS,
        LEAK_STATE_PUSH,
        LEAK_FIEND_RESPONSE,
    )
    LEAKAGE_AVAILABLE = True
except ImportError as e:
    print(f"Leakage not available: {e}")

# Persona / mode core (GEN 31–34). Optional.
try:
    from persona_system import SessionPersonaProfile, leakage_bias
    PERSONA_AVAILABLE = True
except Exception:
    SessionPersonaProfile = None  # type: ignore
    leakage_bias = None  # type: ignore
    PERSONA_AVAILABLE = False

try:
    from interjection_engine import (
        generate_exchange as ie_generate_exchange,
        exchange_to_tuples as ie_exchange_to_tuples,
    )
    INTERJECTION_AVAILABLE = True
except ImportError as e:
    pass  # Interjection engine is optional enhancement

# ═══════════════════════════════════════════════════════════════════════════════
#                    UNIFIED STATE TRACKER
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class UnifiedDialogueState:
    """
    Master state tracker that unifies all dialogue subsystems.
    
    Tracks:
    - Cascade state (energy, vulnerability, composure)
    - Emotional state (from leakage engine)
    - Momentum and transitions
    - Suggested responses
    """
    # From CascadeState
    energy: float = 0.5
    vulnerability: float = 0.5
    birdsong_composure: float = 1.0
    fiend_composure: float = 1.0
    turn_count: int = 0
    last_speaker: str = ""
    
    # From Leakage Engine
    emotional_state: str = "rambling"
    emotional_weights: Dict[str, float] = field(default_factory=lambda: {
        "rambling": 0.3,
        "bratty": 0.2,
        "flustered": 0.2,
        "melting": 0.1,
        "needy": 0.1,
        "quiet": 0.1,
    })
    leak_momentum: float = 0.0
    
    # Response suggestions
    suggested_fiend_tool: str = "observe"
    suggested_fiend_confidence: float = 0.5
    
    # Recent history for coherence
    recent_categories: List[str] = field(default_factory=list)
    recent_leaks: List[int] = field(default_factory=list)
    
    def to_cascade_state(self) -> 'CascadeState':
        """Convert to CascadeState for grammar system"""
        if GRAMMAR_AVAILABLE:
            return CascadeState(
                energy=self.energy,
                vulnerability=self.vulnerability,
                birdsong_composure=self.birdsong_composure,
                fiend_composure=self.fiend_composure,
                turn_count=self.turn_count,
                last_speaker=self.last_speaker,
            )
        return None
    
    def get_intensity(self) -> float:
        """Get intensity for leakage engine (0.0-1.0)"""
        # Combine energy and inverse composure
        return min(1.0, self.energy * 0.6 + (1.0 - self.birdsong_composure) * 0.4)
    
    def get_dominant_emotional_state(self) -> str:
        """Get current dominant emotional state"""
        return max(self.emotional_weights.items(), key=lambda x: x[1])[0]

# ═══════════════════════════════════════════════════════════════════════════════
#                    UNIFIED DIALOGUE ENGINE
# ═══════════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════════
#                    CASCADE INTELLIGENCE: MEMORY + THEMES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class MemorableMoment:
    """A compact, persistent memory shard used to bias future dialogue."""
    ts: float
    speaker: str
    text: str
    trigger: str = ""
    intensity: float = 0.0
    themes: List[str] = field(default_factory=list)

@dataclass
class PersistentCascadeMemory:
    """Lightweight persistent memory store (file-backed)."""
    version: int = 1
    moments: List[MemorableMoment] = field(default_factory=list)
    theme_counts: Dict[str, int] = field(default_factory=dict)
    recent_themes: List[str] = field(default_factory=list)
    recent_exchange_hashes: List[str] = field(default_factory=list)
    total_lines_seen: int = 0
    dirty: bool = False

    PATH = Path.home() / ".ogre_shader_cascade_memory.json"

    @classmethod
    def load(cls) -> "PersistentCascadeMemory":
        try:
            if cls.PATH.exists():
                with open(cls.PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                mem = cls()
                mem.version = int(data.get("version", 1))
                mem.theme_counts = dict(data.get("theme_counts", {}))
                mem.recent_themes = list(data.get("recent_themes", []))[-50:]
                mem.recent_exchange_hashes = list(data.get("recent_exchange_hashes", []))[-200:]
                mem.total_lines_seen = int(data.get("total_lines_seen", 0))
                moments = []
                for m in data.get("moments", [])[-200:]:
                    if isinstance(m, dict):
                        moments.append(MemorableMoment(
                            ts=float(m.get("ts", 0.0)),
                            speaker=str(m.get("speaker", "")),
                            text=str(m.get("text", "")),
                            trigger=str(m.get("trigger", "")),
                            intensity=float(m.get("intensity", 0.0)),
                            themes=list(m.get("themes", []) or []),
                        ))
                mem.moments = moments
                mem.dirty = False
                return mem
        except Exception:
            pass
        return cls()

    def save(self, force: bool = False):
        if not force and not self.dirty:
            return
        try:
            payload = {
                "version": self.version,
                "theme_counts": self.theme_counts,
                "recent_themes": self.recent_themes[-50:],
                "recent_exchange_hashes": self.recent_exchange_hashes[-200:],
                "total_lines_seen": self.total_lines_seen,
                "moments": [
                    {
                        "ts": m.ts, "speaker": m.speaker, "text": m.text,
                        "trigger": m.trigger, "intensity": m.intensity, "themes": m.themes
                    } for m in self.moments[-200:]
                ],
            }
            with open(self.PATH, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            self.dirty = False
        except Exception:
            pass

    def push_themes(self, themes: List[str]):
        if not themes:
            return
        for t in themes:
            self.theme_counts[t] = int(self.theme_counts.get(t, 0)) + 1
            self.recent_themes.append(t)
        self.recent_themes = self.recent_themes[-50:]
        self.dirty = True

    def remember(self, speaker: str, text: str, trigger: str, intensity: float, themes: List[str]):
        # Keep only compact moments (avoid bloat)
        self.moments.append(MemorableMoment(
            ts=time.time(),
            speaker=speaker,
            text=text[:220],
            trigger=trigger[:40],
            intensity=float(intensity),
            themes=themes[:6],
        ))
        self.moments = self.moments[-200:]
        self.dirty = True

    def recent_theme_bias(self) -> Dict[str, float]:
        """Return a normalized bias map from recent themes."""
        bias: Dict[str, float] = {}
        if not self.recent_themes:
            return bias
        window = self.recent_themes[-12:]
        for t in window:
            bias[t] = bias.get(t, 0.0) + 1.0
        total = sum(bias.values()) or 1.0
        for k in list(bias.keys()):
            bias[k] /= total
        return bias

    def record_exchange_hash(self, h: str):
        if not h:
            return
        self.recent_exchange_hashes.append(h)
        self.recent_exchange_hashes = self.recent_exchange_hashes[-200:]
        self.dirty = True

    def exchange_seen_recently(self, h: str) -> bool:
        return h in set(self.recent_exchange_hashes[-80:])

class UnifiedDialogueEngine:
    """
    The master dialogue engine that wires everything together.
    
    PIPELINE:
    1. Track state from all sources
    2. Generate or select dialogue based on unified state
    3. Process through leakage engine
    4. Update all state trackers with results
    5. Return dialogue with leaks and metadata
    """
    
    def __init__(self):
        self.state = UnifiedDialogueState()
        # Persistent Cascade Memory (themes + compact callbacks)
        self.memory_store = PersistentCascadeMemory.load()
        self._lines_since_save = 0
        self._last_trigger = ""
        
        # Theme keyword map (lightweight, heuristic)
        self._theme_keywords = {
            "comfort": ["okay", "safe", "breathe", "gentle", "soft", "easy", "slow"],
            "control": ["hold", "stay", "listen", "obey", "control", "mine"],
            "praise": ["good", "proud", "perfect", "yes", "that's it"],
            "tease": ["brat", "cute", "try", "oops", "hehe", "hush"],
            "vulnerability": ["please", "can't", "too much", "help", "sorry"],
            "playful": ["lol", "hah", "hehe", "~", "owo"],
            "intensity": ["hard", "faster", "more", "again", "need", "now"],
            "aftercare": ["rest", "water", "cuddle", "warm", "after", "care"],
        }
        


        # Authored line packs (high-ROI callback pool expansions)
        self._authored_lines = self._load_line_packs()
        self._pending_payoff = None  # type: Optional[Tuple[str, str]]
        self._pending_payoff_ttl = 0

        # Initialize leakage engine if available
        if LEAKAGE_AVAILABLE:
            self.leakage = IntegratedLeakageEngine()
        else:
            self.leakage = None
        
        # Track if we just generated or selected
        self.last_source = "authored"  # "authored", "generated", "grammar"

        # Persona label (for debugging / HUD)
        self.persona_label: Optional[str] = None


    # ════════════════════════════════════════════════════════════════════════
    #                    AUTHORED LINE PACKS (HIGH ROI)
    # ════════════════════════════════════════════════════════════════════════
    def _load_line_packs(self) -> Dict[str, Any]:
        """Load authored line packs from ./line_packs.

        Returns dict with:
          - banter: List[str]
          - followup: List[str]
          - aftercare: List[str]
          - business: List[str]   (STAGE: ... lines)
          - setup_payoff: List[Tuple[str,str]]
        """
        packs = {"banter": [], "followup": [], "aftercare": [], "business": [], "setup_payoff": []}
        try:
            base = Path(__file__).parent / "line_packs"
            if not base.exists():

                # Optional: personification pack expansions (extra authored flavor)
                try:
                    extra_map = {
                        "personification_banter.json": ("banter",),
                        "personification_business.json": ("business",),
                        "personification_aftercare.json": ("aftercare",),
                    }
                    for fname, keys in extra_map.items():
                        p = base / fname
                        if p.exists():
                            data = load_json(p)
                            lines = data.get("lines", []) if isinstance(data, dict) else []
                            for k in keys:
                                packs.setdefault(k, [])
                                packs[k].extend([ln for ln in lines if isinstance(ln, str) and ln.strip()])
                except Exception:
                    pass
                return packs

            def load_lines_json(fname: str) -> List[str]:
                p = base / fname
                if not p.exists():
                    return []
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict) and "lines" in data and isinstance(data["lines"], list):
                    return [str(x) for x in data["lines"] if str(x).strip()]
                # Fallback if someone drops a raw list
                if isinstance(data, list):
                    return [str(x) for x in data if str(x).strip()]
                return []

            packs["banter"] = load_lines_json("banter_sitcom.json")
            packs["followup"] = load_lines_json("followup_glue.json")


            # Misfire → Repair pack (extends followup glue without changing probabilities)
            try:
                repair_lines = load_lines_json("misfire_repair.json")
                if repair_lines:
                    packs.setdefault("followup", [])
                    packs["followup"].extend(repair_lines)
            except Exception:
                pass

            # Breath-smile micro-confirmations (extends followup glue without changing probabilities)
            try:
                micro_lines = load_lines_json("breath_smile_microconfirm.json")
                if micro_lines:
                    packs.setdefault("followup", [])
                    packs["followup"].extend(micro_lines)
            except Exception:
                pass

            # Wrong key / right lock pack (extends followup glue without changing probabilities)
            try:
                lock_lines = load_lines_json("wrong_key_right_lock.json")
                if lock_lines:
                    packs.setdefault("followup", [])
                    packs["followup"].extend(lock_lines)
            except Exception:
                pass



            # Thread choreography pack (extends followup glue without changing probabilities)
            try:
                thread_lines = load_lines_json("thread_choreography.json")
                if thread_lines:
                    packs.setdefault("followup", [])
                    packs["followup"].extend(thread_lines)
            except Exception:
                pass


            # Silence handling pack (silence becomes content; extends followup glue without changing probabilities)
            try:
                silence_lines = load_lines_json("silence_handling.json")
                if silence_lines:
                    packs.setdefault("followup", [])
                    packs["followup"].extend(silence_lines)
            except Exception:
                pass

            # Imp arbitration pack (Lad/Lass/Bloom/Bloomlet as 'four feral imps' logic; extends followup glue without changing probabilities)
            try:
                imp_lines = load_lines_json("imp_arbitration.json")
                if imp_lines:
                    packs.setdefault("followup", [])
                    packs["followup"].extend(imp_lines)
            except Exception:
                pass



            # Body facts, lovingly (non-vulgar realism; grounding + tenderness; extends followup glue without changing probabilities)
            try:
                body_lines = load_lines_json("body_facts_lovingly.json")
                if body_lines:
                    packs.setdefault("followup", [])
                    packs["followup"].extend(body_lines)
            except Exception:
                pass







            # Consent map protocol banter (extends followup glue without changing probabilities)
            try:
                consent_lines = load_lines_json("consent_map_protocol.json")
                if consent_lines:
                    packs.setdefault("followup", [])
                    packs["followup"].extend(consent_lines)
            except Exception:
                pass

            # Callback tiny talismans (continuity spice; extends followup glue without changing probabilities)
            try:
                tal_lines = load_lines_json("callback_tiny_talismans.json")
                if tal_lines:
                    packs.setdefault("followup", [])
                    packs["followup"].extend(tal_lines)
            except Exception:
                pass
            packs["aftercare"] = load_lines_json("aftercare_anchors.json")
            packs["business"] = load_lines_json("character_business.json")

            # Setup/Payoff pairs (parse the text file for robustness)
            sp_path = base / "setup_payoff_pairs.txt"
            if sp_path.exists():
                setups = []
                payoffs = []
                for raw in sp_path.read_text(encoding="utf-8").splitlines():
                    line = raw.strip()
                    if not line:
                        continue
                    if line.startswith("SETUP→"):
                        setups.append(line.replace("SETUP→", "", 1).strip())
                    elif line.startswith("PAYOFF→"):
                        payoffs.append(line.replace("PAYOFF→", "", 1).strip())
                # Pair them in order
                pairs = []
                n = min(len(setups), len(payoffs))
                for i in range(n):
                    pairs.append((setups[i], payoffs[i]))
                packs["setup_payoff"] = pairs
        except Exception:
            # Never crash the game due to optional content packs
            return packs

        return packs

    def _parse_speaker_line(self, raw: str) -> Tuple[str, str]:
        """Parse 'SPEAKER: text' into (speaker, text). Defaults to FIEND."""
        if not raw:
            return ("FIEND", "Mm.")
        s = raw.strip()
        # Stage directions
        if s.startswith("STAGE:"):
            txt = s.replace("STAGE:", "", 1).strip()
            return ("OWO", txt if txt else "...")
        if ":" in s:
            sp, txt = s.split(":", 1)
            sp = sp.strip().upper()
            txt = txt.strip()
            if sp in ("FIEND", "BIRDSONG", "OWO", "NARRATOR"):
                return (sp, txt if txt else "...")
        return ("FIEND", s)

    def _inject_authored_lines(
        self,
        raw_exchange: List[Tuple[str, str, Optional[Dict]]],
        exchange_type: str
    ) -> List[Tuple[str, str, Optional[Dict]]]:
        """Inject authored lines BEFORE leakage/cascade processing.

        This is intentionally lightweight: it adds flavor without derailing pacing.
        """
        if not isinstance(raw_exchange, list) or not raw_exchange:
            return raw_exchange

        # If packs failed to load, do nothing
        packs = getattr(self, "_authored_lines", None)
        if not packs:
            return raw_exchange

        # Helper: safe add line
        def as_triplet(sp: str, txt: str, meta: Optional[Dict] = None):
            return (sp, txt, meta or {"source": "authored"})

        out = list(raw_exchange)

        # ── Setup→Payoff threading ──
        # Occasionally start a setup; if pending, try to pay it off.
        try:
            # Payoff first if pending
            if self._pending_payoff and self._pending_payoff_ttl > 0:
                # Higher chance to pay off near the end of an exchange
                if random.random() < 0.45:
                    sp, txt = self._parse_speaker_line(self._pending_payoff[1])
                    out.insert(max(0, len(out) - 1), as_triplet(sp, txt, {"source":"authored","tag":"payoff"}))
                    self._pending_payoff = None
                    self._pending_payoff_ttl = 0
                else:
                    self._pending_payoff_ttl -= 1

            # Start a setup sometimes
            if not self._pending_payoff and packs.get("setup_payoff"):
                if random.random() < 0.18:
                    setup, payoff = random.choice(packs["setup_payoff"])
                    sp, txt = self._parse_speaker_line(setup)
                    out.insert(0, as_triplet(sp, txt, {"source":"authored","tag":"setup"}))
                    self._pending_payoff = (setup, payoff)
                    self._pending_payoff_ttl = 6
        except Exception:
            pass

        # ── Aftercare anchoring ──
        # If energy/composure suggests landing, sprinkle an anchor.
        try:
            if packs.get("aftercare") and (exchange_type in ("aftercare", "rest") or self.state.energy < 0.25):
                if random.random() < 0.35:
                    sp, txt = self._parse_speaker_line(random.choice(packs["aftercare"]))
                    out.append(as_triplet(sp, txt, {"source":"authored","tag":"aftercare"}))
        except Exception:
            pass

        # ── Banter / sitcom beats ──
        try:
            if packs.get("banter") and exchange_type in ("banter", "default", "play"):
                if random.random() < 0.30:
                    sp, txt = self._parse_speaker_line(random.choice(packs["banter"]))
                    out.insert(random.randrange(0, len(out)), as_triplet(sp, txt, {"source":"authored","tag":"banter"}))
        except Exception:
            pass

        # ── Followup glue ──
        try:
            if packs.get("followup") and len(out) >= 3:
                if random.random() < 0.25:
                    sp, txt = self._parse_speaker_line(random.choice(packs["followup"]))
                    out.insert(len(out), as_triplet(sp, txt, {"source":"authored","tag":"glue"}))
        except Exception:
            pass

        # ── Character business (slapstick micro) ──
        try:
            if packs.get("business") and random.random() < 0.18:
                sp, txt = self._parse_speaker_line(random.choice(packs["business"]))
                # Put it near the middle so it plays like a cutaway gag
                out.insert(len(out)//2, as_triplet(sp, txt, {"source":"authored","tag":"business"}))
        except Exception:
            pass

        return out

    def set_session_profile(self, profile: 'SessionPersonaProfile'):
        """Apply persona/mode biases into leakage state.

        Safe to call even if persona or leakage systems are unavailable.
        """
        if not profile:
            return

        self.persona_label = getattr(profile, "label", None)

        if not (self.leakage and PERSONA_AVAILABLE and leakage_bias):
            return

        try:
            state_bias, fiend_tool_bias, mom_mult, trans_mult = leakage_bias(profile)
            # Apply biases to escalation state (base weights + thresholds)
            if hasattr(self.leakage, "escalation") and hasattr(self.leakage.escalation, "apply_persona_bias"):
                self.leakage.escalation.apply_persona_bias(
                    state_bias=state_bias,
                    fiend_tool_bias=fiend_tool_bias,
                    momentum_threshold_mult=mom_mult,
                    state_transition_threshold_mult=trans_mult,
                )
        except Exception:
            # Never allow persona to crash dialogue pipeline
            return
    
    # ═══════════════════════════════════════════════════════════════════════════
    #                    CORE PIPELINE
    # ═══════════════════════════════════════════════════════════════════════════
    
    def process_exchange(
        self,
        exchange: List[Tuple[str, str]],
        intensity: Optional[float] = None
    ) -> List[Tuple[str, str, Optional[Dict]]]:
        """
        Process an exchange through the full pipeline.
        
        Args:
            exchange: List of (speaker, text) tuples
            intensity: Override intensity, or use calculated
            
        Returns:
            List of (speaker, text, metadata) tuples with leaks injected
        """
        if intensity is None:
            intensity = self.state.get_intensity()
        
        processed = []
        
        for speaker, text in exchange:
            result = self.process_line(speaker, text, intensity)
            processed.extend(result)
            
            # Intensity grows slightly with each line
            intensity = min(1.0, intensity + 0.02)
        
        return processed
    
    def process_line(
        self,
        speaker: str,
        text: str,
        intensity: Optional[float] = None
    ) -> List[Tuple[str, str, Optional[Dict]]]:
        """
        Process a single line through the full pipeline.
        
        Returns list because leaks may be injected before/after.
        """
        if intensity is None:
            intensity = self.state.get_intensity()
        
        # Update state pre-line
        self.state.turn_count += 1
        self.state.last_speaker = speaker
        
        result = []
        metadata = {
            "intensity": intensity,
            "emotional_state": self.state.get_dominant_emotional_state(),
            "composure": self.state.birdsong_composure if speaker == "BIRDSONG" else self.state.fiend_composure,
        }
        
        # Process through leakage if available and it's Birdsong
        if self.leakage and speaker == "BIRDSONG":
            leaked, feedback = self.leakage.process_line_with_feedback(
                speaker=speaker,
                line=text,
                intensity=intensity,
                force_leak=False
            )
            
            # Check if leaks occurred
            if len(leaked) > 1:
                for s, t in leaked:
                    if t == text:
                        # Core line
                        result.append((s, t, metadata))
                    else:
                        # Leak line
                        leak_meta = {"is_leak": True}
                        result.append((f"{s}_LEAK", t, leak_meta))
                        
                        # Track leak for state update
                        nls = self._get_nls_from_text(t)
                        if nls:
                            self.state.recent_leaks.append(nls.id)
                            if len(self.state.recent_leaks) > 5:
                                self.state.recent_leaks.pop(0)
            else:
                result.append((speaker, text, metadata))
            
            # Update emotional state from feedback
            if feedback:
                if feedback.get('new_dominant_state'):
                    self.state.emotional_state = feedback['new_dominant_state']
                self.state.leak_momentum = feedback.get('leak_momentum', 0.0)
                if 'current_state_weights' in feedback:
                    self.state.emotional_weights = feedback['current_state_weights']
                
                # Update Fiend suggestions
                tool, conf = feedback.get('fiend_recommendation', ("observe", 0.5))
                self.state.suggested_fiend_tool = tool
                self.state.suggested_fiend_confidence = conf
        else:
            result.append((speaker, text, metadata))
        
        # Update cascade state
        self._update_cascade_from_line(speaker, text, intensity)
        
        return result
    
    def _get_nls_from_text(self, text: str) -> Optional[Any]:
        """Get NLS element from leak text"""
        if not LEAKAGE_AVAILABLE:
            return None
        
        # Strip formatting
        clean = text.strip().strip('*').strip('〈').strip('〉')
        
        for nls in ALL_NLS.values():
            if nls.text.lower() == clean.lower():
                return nls
        return None
    
    def _update_cascade_from_line(self, speaker: str, text: str, intensity: float):
        """Update cascade state based on line content"""
        # Energy flows based on punctuation and content
        if "!" in text or text.isupper():
            self.state.energy = min(1.0, self.state.energy * 0.7 + intensity * 0.4)
        elif "..." in text or text.endswith("~"):
            self.state.energy = max(0.1, self.state.energy * 0.85)
        
        # Vulnerability increases with soft sounds
        soft_markers = ["hahhh", "nnn", "mmm", "huuu", "~"]
        if any(m in text.lower() for m in soft_markers):
            self.state.vulnerability = min(1.0, self.state.vulnerability + 0.05)
        
        # Composure changes based on content
        if speaker == "BIRDSONG":
            crumble_markers = ["shut up", "i hate you", "okay", "fine", "..."]
            challenge_markers = ["pfft", "tch", "as if", "whatever", "!"]
            
            if any(m in text.lower() for m in crumble_markers):
                self.state.birdsong_composure = max(0.0, self.state.birdsong_composure - 0.1)
            elif any(m in text.lower() for m in challenge_markers):
                self.state.birdsong_composure = min(1.0, self.state.birdsong_composure + 0.05)
    
    # ═══════════════════════════════════════════════════════════════════════════
    #                    GENERATION METHODS
    # ═══════════════════════════════════════════════════════════════════════════
    

# ────────────────────────────────────────────────────────────────────
# Cascade Intelligence helpers
# ────────────────────────────────────────────────────────────────────
def set_trigger_context(self, trigger: str):
    """Optional hint from gameplay (hit/miss/milestone/etc)."""
    self._last_trigger = trigger or ""

def _detect_themes(self, text: str) -> List[str]:
    """Heuristic theme detection. Cheap, fast, good-enough."""
    if not text:
        return []
    t = text.lower()
    themes: List[str] = []
    # Keyword themes
    for theme, kws in self._theme_keywords.items():
        for kw in kws:
            if kw in t:
                themes.append(theme)
                break
    # Soft signals
    if "?" in text:
        themes.append("uncertainty")
    if "..." in text or "…" in text:
        themes.append("hesitation")
    if "!" in text and "?" in text:
        themes.append("overwhelm")
    # Dedupe, keep stable order
    seen=set()
    out=[]
    for th in themes:
        if th not in seen:
            out.append(th); seen.add(th)
    return out[:6]

def _update_memory_from_line(self, speaker: str, core_text: str, intensity: float, processed: List[Tuple[str,str,Optional[Dict]]]) -> List[str]:
    """Update persistent memory + theme history from a processed line."""
    leak_text = ""
    try:
        # Include leaks in theme detection (small but important)
        if processed:
            leaks=[t for s,t,m in processed if m and m.get("is_leak")]
            leak_text = " ".join(leaks)
    except Exception:
        leak_text = ""
    themes = self._detect_themes((core_text or "") + " " + (leak_text or ""))
    self.memory_store.total_lines_seen += 1
    self.memory_store.push_themes(themes)

    # Decide whether to store a memorable moment
    trig = (self._last_trigger or "")
    memorable = False
    if intensity >= 0.88:
        memorable = True
    if trig in ("milestone", "unlock", "climax", "aftercare", "critical"):
        memorable = True
    # A small vulnerability hook
    if core_text and any(x in core_text.lower() for x in ["please", "can't", "sorry", "help"]):
        memorable = True

    if memorable and core_text:
        self.memory_store.remember(speaker=speaker, text=core_text, trigger=trig, intensity=float(intensity), themes=themes)

    self._lines_since_save += 1
    if self._lines_since_save >= 12:
        self.memory_store.save()
        self._lines_since_save = 0
    return themes

def get_recent_themes_str(self, max_tags: int = 3) -> str:
    if not self.memory_store.recent_themes:
        return ""
    # Prefer last distinct themes
    seen=set()
    out=[]
    for th in reversed(self.memory_store.recent_themes[-18:]):
        if th not in seen:
            out.append(th); seen.add(th)
        if len(out) >= max_tags:
            break
    out=list(reversed(out))
    return " • ".join(out)

def score_exchange(self, exchange: tuple, intensity: float = 0.5, trigger: str = "") -> float:
    """Score an authored exchange for contextual selection."""
    try:
        fiend, bird, inner = exchange
    except Exception:
        return 1.0
    blob = f"{fiend} {bird} {inner}"
    themes = self._detect_themes(blob)
    bias = self.memory_store.recent_theme_bias()

    score = 1.0
    # Theme coherence: overlap with recent themes
    for th in themes:
        if th in bias:
            score *= (1.0 + 0.9 * bias[th])

    # Intensity alignment: exchanges with explicit intensity words scale up at high intensity
    t = blob.lower()
    has_intense = any(k in t for k in ["hard", "faster", "more", "again", "need", "now"])
    has_after = any(k in t for k in ["rest", "water", "cuddle", "after"])
    if has_intense and intensity >= 0.65:
        score *= 1.2
    if has_after and intensity <= 0.45:
        score *= 1.15

    # Callback spark: if exchange shares a theme with any stored moment, small bump
    if self.memory_store.moments and themes:
        recent_m = self.memory_store.moments[-12:]
        moment_themes=set()
        for m in recent_m:
            for th in (m.themes or []):
                moment_themes.add(th)
        if any(th in moment_themes for th in themes):
            score *= 1.15

    # Novelty: downweight if we've seen it recently
    h = str(abs(hash(blob)))  # stable enough for session memory
    if self.memory_store.exchange_seen_recently(h):
        score *= 0.55

    # Trigger hint
    if trigger and trigger in (self._last_trigger or ""):
        score *= 1.05

    # Clamp and jitter
    score = max(0.05, min(5.0, score))
    score *= (0.92 + random.random() * 0.16)
    return score

def pick_exchange(self, exchanges: List[tuple], intensity: float = 0.5, trigger: str = "") -> tuple:
    """Pick an exchange using contextual scoring (weighted random)."""
    if not exchanges:
        return None
    weights=[]
    total=0.0
    for ex in exchanges:
        w=self.score_exchange(ex, intensity=float(intensity), trigger=trigger)
        weights.append(w); total += w
    r=random.random() * (total or 1.0)
    cum=0.0
    for ex,w in zip(exchanges, weights):
        cum += w
        if r <= cum:
            # record hash for novelty tracking
            try:
                blob = f"{ex[0]} {ex[1]} {ex[2]}"
                self.memory_store.record_exchange_hash(str(abs(hash(blob))))
            except Exception:
                pass
            return ex
    return exchanges[0]

    def generate_exchange(
        self,
        length: int = 6,
        exchange_type: str = "banter"
    ) -> List[Tuple[str, str, Optional[Dict]]]:
        """
        Generate a fresh exchange using the unified system.
        
        Uses grammar system if available, falls back to interjection engine.
        """
        raw_exchange = []
        
        if GRAMMAR_AVAILABLE:
            # Use the grammar system with our unified state
            cascade = self.state.to_cascade_state()
            
            # Generate using the full grammar
            assembled = generate_exchange(
                length=length,
                starting_energy=self.state.energy,
                birdsong_starts=(exchange_type != "fiend_leads")
            )
            raw_exchange = exchange_to_tuples(assembled)
            self.last_source = "grammar"
            
        elif INTERJECTION_AVAILABLE:
            # Fall back to interjection engine
            raw_exchange = ie_generate_exchange(exchange_type, length)
            self.last_source = "interjection"
        else:
            # Minimal fallback
            raw_exchange = [
                ("FIEND", "Mm."),
                ("BIRDSONG", "What?"),
            ]
            self.last_source = "fallback"
        
        # Optionally inject authored line packs before processing (so leaks apply)
        raw_exchange = self._inject_authored_lines(raw_exchange, exchange_type)

        # Process through the full pipeline (adds leaks)
        return self.process_exchange(raw_exchange)
    
    def generate_response(
        self,
        to_speaker: str = "BIRDSONG"
    ) -> List[Tuple[str, str, Optional[Dict]]]:
        """
        Generate a single response line appropriate to current state.
        """
        if not GRAMMAR_AVAILABLE:
            # Simple fallback
            if to_speaker == "BIRDSONG":
                return [("BIRDSONG", "Whatever.", None)]
            else:
                return [("FIEND", "Mm.", None)]
        
        # Get response parameters from unified state
        cascade = self.state.to_cascade_state()
        params = get_response_parameters(cascade, to_speaker)
        
        # Select category
        categories = list(params["category_weights"].keys())
        weights = list(params["category_weights"].values())
        
        # Avoid recent categories
        if self.state.recent_categories:
            for i, cat in enumerate(categories):
                if cat in self.state.recent_categories[-2:]:
                    weights[i] *= 0.5
        
        category = random.choices(categories, weights=weights)[0]
        self.state.recent_categories.append(category)
        if len(self.state.recent_categories) > 5:
            self.state.recent_categories.pop(0)
        
        # Get cores
        if to_speaker == "BIRDSONG":
            cores = BIRDSONG_CORES.get(category, BIRDSONG_CORES.get("ramble", []))
        else:
            cores = FIEND_CORES.get(category, FIEND_CORES.get("observe", []))
        
        if not cores:
            return [("BIRDSONG" if to_speaker == "BIRDSONG" else "FIEND", "...", None)]
        
        core = random.choice(cores)
        energy_target = params["energy_target"]
        
        # Assemble line
        if to_speaker == "BIRDSONG":
            # Choose interjections based on category and state
            # REDUCED FREQUENCY - interjections should be rare, not constant
            front_interj = None
            end_interj = None
            
            if random.random() < params.get("interjection_chance", 0.15):  # Was 0.7
                if category in ("caught", "crumble"):
                    front_interj = random.choice(["gah", "nngh", "hahhh", None, None])  # More Nones
                elif category == "challenge":
                    front_interj = random.choice(["tch", "oy", None, None])
                elif category == "ramble":
                    front_interj = random.choice(["oy", "oiii", None, None, None])
            
            line = assemble_birdsong_line(
                core,
                front_interj=front_interj,
                end_interj=end_interj,
                energy_target=energy_target
            )
        else:
            front_interj = None
            if random.random() < params.get("interjection_chance", 0.08):  # Was 0.4
                front_interj = random.choice(["sooo", "mm", None, None])
            
            line = assemble_fiend_line(
                core,
                front_interj=front_interj,
                energy_target=energy_target,
                caught=params.get("use_cute_sounds", False)
            )
        
        # Process through pipeline
        return self.process_line(line.speaker, line.text)
    
    # ═══════════════════════════════════════════════════════════════════════════
    #                    STATE QUERIES
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_suggested_fiend_tool(self) -> Tuple[str, float]:
        """Get the optimal Fiend tool based on accumulated state"""
        return (self.state.suggested_fiend_tool, self.state.suggested_fiend_confidence)
    
    def get_birdsong_state(self) -> str:
        """Get Birdsong's current emotional state"""
        return self.state.get_dominant_emotional_state()
    
    def get_composure(self, who: str = "BIRDSONG") -> float:
        """Get composure level (1.0 = composed, 0.0 = crumbling)"""
        if who.upper() == "BIRDSONG":
            return self.state.birdsong_composure
        return self.state.fiend_composure
    
    def get_energy(self) -> float:
        """Get current conversation energy"""
        return self.state.energy
    
    def get_momentum(self) -> float:
        """Get leak momentum"""
        return self.state.leak_momentum
    
    def should_transition(self) -> bool:
        """Check if momentum warrants a scene transition"""
        return self.state.leak_momentum > 0.3 or self.state.birdsong_composure < 0.3
    
    def get_state_summary(self) -> Dict:
        """Get full state summary"""
        return {
            "emotional_state": self.get_birdsong_state(),
            "emotional_weights": dict(self.state.emotional_weights),
            "composure": self.state.birdsong_composure,
            "energy": self.state.energy,
            "vulnerability": self.state.vulnerability,
            "momentum": self.state.leak_momentum,
            "turn_count": self.state.turn_count,
            "suggested_fiend_tool": self.state.suggested_fiend_tool,
            "suggested_fiend_confidence": self.state.suggested_fiend_confidence,
            "last_source": self.last_source,
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    #                    STATE MANIPULATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def set_intensity(self, intensity: float):
        """Directly set intensity"""
        self.state.energy = intensity
        if self.leakage:
            self.leakage.set_intensity("BIRDSONG", intensity)
    
    def push_toward_state(self, state: str, weight: float = 0.1):
        """Push emotional state toward target"""
        if state in self.state.emotional_weights:
            self.state.emotional_weights[state] = min(1.0, 
                self.state.emotional_weights[state] + weight)
            # Normalize
            total = sum(self.state.emotional_weights.values())
            for s in self.state.emotional_weights:
                self.state.emotional_weights[s] /= total
    
    def reset_for_new_scene(self):
        """Reset for a new scene (preserves emotional state)"""
        self.state.energy = 0.5
        self.state.birdsong_composure = 0.8
        self.state.fiend_composure = 1.0
        self.state.turn_count = 0
        self.state.recent_categories.clear()
        # Don't reset emotional weights - they persist
        try:
            if hasattr(self, 'memory_store') and self.memory_store:
                self.memory_store.save()
        except Exception:
            pass

# ═══════════════════════════════════════════════════════════════════════════════
#                    GAME INTEGRATION HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

# Global engine instance for easy access
_engine: Optional[UnifiedDialogueEngine] = None

def get_engine() -> UnifiedDialogueEngine:
    """Get or create the global dialogue engine"""
    global _engine
    if _engine is None:
        _engine = UnifiedDialogueEngine()
    return _engine

def process_authored_exchange(exchange: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """
    Process an authored exchange through the full pipeline.
    Returns simple tuple format for backward compatibility.
    """
    engine = get_engine()
    processed = engine.process_exchange(exchange)
    
    # Convert back to simple tuples
    result = []
    for speaker, text, meta in processed:
        # Strip _LEAK suffix for compatibility
        clean_speaker = speaker.replace("_LEAK", "")
        result.append((clean_speaker, text))
    
    return result

def generate_dynamic_exchange(length: int = 6, type: str = "banter") -> List[Tuple[str, str]]:
    """
    Generate a dynamic exchange using the full system.
    Returns simple tuple format.
    """
    engine = get_engine()
    processed = engine.generate_exchange(length=length, exchange_type=type)
    
    result = []
    for speaker, text, meta in processed:
        clean_speaker = speaker.replace("_LEAK", "")
        result.append((clean_speaker, text))
    
    return result

def get_current_state() -> Dict:
    """Get current dialogue state summary"""
    return get_engine().get_state_summary()

def get_suggested_tool() -> Tuple[str, float]:
    """Get suggested Fiend tool"""
    return get_engine().get_suggested_fiend_tool()

# ═══════════════════════════════════════════════════════════════════════════════
#                    DEMONSTRATION
# ═══════════════════════════════════════════════════════════════════════════════

def demo():
    """Demonstrate the unified dialogue system"""
    print("═" * 70)
    print("        UNIFIED DIALOGUE SYSTEM DEMONSTRATION")
    print("═" * 70)
    print()
    
    print(f"Subsystems available:")
    print(f"  Grammar:      {'✓' if GRAMMAR_AVAILABLE else '✗'}")
    print(f"  Leakage:      {'✓' if LEAKAGE_AVAILABLE else '✗'}")
    print(f"  Interjection: {'✓' if INTERJECTION_AVAILABLE else '✗'}")
    print()
    
    engine = UnifiedDialogueEngine()
    
    # Test 1: Process authored exchange
    print("─" * 70)
    print("TEST 1: Processing authored exchange with leakage")
    print("─" * 70)
    
    authored = [
        ("FIEND", "Your hands are shaking."),
        ("BIRDSONG", "It's cold in here!"),
        ("FIEND", "It's not."),
        ("BIRDSONG", "Shut up."),
    ]
    
    processed = engine.process_exchange(authored)
    
    for speaker, text, meta in processed:
        if "_LEAK" in speaker:
            print(f"  [{speaker.replace('_LEAK', '')}] 〈{text}〉  ← LEAK")
        else:
            print(f"  [{speaker}] \"{text}\"")
    
    print()
    print(f"State after: {engine.get_birdsong_state()}, composure: {engine.get_composure():.2f}")
    
    # Test 2: Generate exchange
    if GRAMMAR_AVAILABLE:
        print()
        print("─" * 70)
        print("TEST 2: Generating fresh exchange")
        print("─" * 70)
        
        generated = engine.generate_exchange(length=6)
        
        for speaker, text, meta in generated:
            if "_LEAK" in speaker:
                print(f"  [{speaker.replace('_LEAK', '')}] 〈{text}〉  ← LEAK")
            else:
                print(f"  [{speaker}] \"{text}\"")
        
        print()
        print(f"Generated using: {engine.last_source}")
    
    # Test 3: State evolution
    print()
    print("─" * 70)
    print("TEST 3: State evolution over multiple exchanges")
    print("─" * 70)
    
    # Reset engine
    engine = UnifiedDialogueEngine()
    
    exchanges = [
        [("BIRDSONG", "Whatever."), ("FIEND", "Mm.")],
        [("BIRDSONG", "Stop looking at me!"), ("FIEND", "Can't help it.")],
        [("BIRDSONG", "I hate you..."), ("FIEND", "No you don't.")],
        [("BIRDSONG", "...maybe"), ("FIEND", "There it is.")],
    ]
    
    for i, ex in enumerate(exchanges):
        engine.process_exchange(ex)
        state = engine.get_state_summary()
        print(f"  Exchange {i+1}: {state['emotional_state']} (composure: {state['composure']:.2f})")
        
        tool, conf = state['suggested_fiend_tool'], state['suggested_fiend_confidence']
        if conf > 0.3:
            print(f"              → Fiend should: {tool.upper()} ({conf:.2f})")
    
    print()
    print("Final state:")
    summary = engine.get_state_summary()
    for k, v in summary.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.2f}")
        elif isinstance(v, dict):
            print(f"  {k}:")
            for sk, sv in sorted(v.items(), key=lambda x: -x[1] if isinstance(x[1], float) else 0):
                if isinstance(sv, float):
                    print(f"    {sk}: {sv:.2f}")
        else:
            print(f"  {k}: {v}")

if __name__ == "__main__":
    demo()
