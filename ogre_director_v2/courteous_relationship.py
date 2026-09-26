"""Runtime-only relationship authority for autonomous Courteous Ruin.

This model owns conversational/physical intent, never rendering or saves.  The
Ogre runtime reports recordings and performed surges; the model returns the
next desired physical answer and, when the exchange reaches release, the route
that the pair actually authored.  There are no protected sessions or outcome
quotas.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from collections import deque
import json
import os
from pathlib import Path
import random
import re
import time


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9']+", " ", str(value or "").lower())).strip()


@dataclass
class CourteousRelationship:
    fertility: float = 0.5
    courtesy_history: float = 0.35
    hana_teasing_confidence: float = 0.30
    fiend_birdsong_literacy: float = 0.25
    seed: int = 0
    arousal: float = 0.12
    reproductive_pull: float = 0.0
    thrust_pressure: float = 0.0
    safe_release_pressure: float = 0.0
    withdrawal_pull: float = 0.18
    trust: float = 0.42
    fiend_confidence: float = 0.25
    edge_control: float = 1.0
    voice_fascination: float = 0.12
    mutual_humiliation: float = 0.08
    animal_spiral: float = 0.0
    invitation_clarity: float = 0.0
    purple_confirmations: int = 0
    reopened_risks: int = 0
    tentative_purple_budget: int = 0
    bodily_weakness_pending: bool = False
    last_register: str = "baseline"
    pending_intent: str = "listen"
    desired_surge: str = "purple"
    last_surge: str = ""
    climax_ready: bool = False
    climax_kind: str = ""
    committed: bool = False
    exchanges: int = 0
    actions: int = 0
    commands_obeyed: int = 0
    corrected_overreaches: int = 0
    pleased_one_ups: int = 0
    birdsong_locks: int = 0
    recent: deque = field(default_factory=lambda: deque(maxlen=18))

    def __post_init__(self) -> None:
        self.fertility = max(0.0, min(1.0, float(self.fertility)))
        self.rng = random.Random(int(self.seed or time.time_ns()))
        raw_log=os.environ.get("WOTW_COURTEOUS_DIAGNOSTIC", "") or ""
        self.log_path = Path(raw_log) if raw_log else None

    def _log(self, event: str, **extra) -> None:
        if self.log_path is None:
            return
        row = {"ts": round(time.time(), 3), "event": event, **self.snapshot(), **extra}
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def observe_voice(self, speaker: str, transcript: str, register: str = "", prosody: str = "") -> None:
        speaker = str(speaker or "").upper()
        text = _norm(transcript)
        register = str(register or "baseline")
        self.exchanges += 1
        self.last_register = register
        self.recent.append(("voice", speaker, register, text[:100]))
        if speaker == "BIRDSONG":
            if register == "direct_command":
                if any(x in text for x in ("inside", "deliver", "don't pull", "do not pull", "stay in")):
                    self.pending_intent="repeat"
                    self.desired_surge="purple"
                    self.tentative_purple_budget=max(self.tentative_purple_budget,3)
                    self.reopened_risks+=1
                    self.invitation_clarity=min(1.0,self.invitation_clarity+0.32)
                    self.reproductive_pull=min(1.0,self.reproductive_pull+0.24)
                elif any(x in text for x in ("back out", "not yet", "wait", "slow")):
                    self.pending_intent = "withdraw"
                    self.withdrawal_pull = min(1.0, self.withdrawal_pull + 0.34)
                    self.reproductive_pull = max(0.0, self.reproductive_pull - 0.16)
                    self.thrust_pressure = max(0.0, self.thrust_pressure - 0.10)
                    self.tentative_purple_budget = 0
                    self.desired_surge = "green"
                    self.safe_release_pressure=min(1.0,self.safe_release_pressure+0.035)
                elif any(x in text for x in ("hold me tighter", "closer", "stay")):
                    self.pending_intent = "draw_close"
                    self.desired_surge = "green"
                elif any(x in text for x in ("harder", "right there")):
                    self.pending_intent = "bend"
                    self.desired_surge = "red"
                else:
                    self.pending_intent = "repeat"
                    self.desired_surge = self.desired_surge or self.last_surge or "purple"
                    if self.desired_surge == "purple":
                        self.tentative_purple_budget = max(self.tentative_purple_budget,1)
                self.trust = min(1.0, self.trust + 0.025)
                self.invitation_clarity = min(1.0,self.invitation_clarity+0.08)
                if self.bodily_weakness_pending:
                    # A crisp instruction after the embarrassment reclaims the
                    # exchange and makes his attention feel especially legible.
                    self.bodily_weakness_pending=False
                    self.trust=min(1.0,self.trust+0.045)
                    self.mutual_humiliation=min(1.0,self.mutual_humiliation+0.035)
            elif register == "coy_escalation":
                self.pending_intent = "test"
                self.hana_teasing_confidence = min(1.0, self.hana_teasing_confidence + 0.035)
                self.reproductive_pull = min(1.0, self.reproductive_pull + 0.055 + self.fertility * 0.025)
                purple_weight=0.34+0.46*self.animal_spiral+0.12*self.voice_fascination
                self.desired_surge = self.rng.choices(("purple", "red", "green"), (purple_weight,0.36,0.30))[0]
                if self.desired_surge=="purple":
                    self.tentative_purple_budget=1+(1 if self.animal_spiral>=0.52 else 0)
                    self.reopened_risks+=1
                self.invitation_clarity=max(0.08,self.invitation_clarity*0.86)
            elif register == "sentence_repair":
                self.pending_intent = "listen"
                self.fiend_confidence = max(0.05, self.fiend_confidence - 0.10)
                self.withdrawal_pull = min(1.0, self.withdrawal_pull + 0.12)
                self.thrust_pressure=max(0.0,self.thrust_pressure-0.045)
                self.tentative_purple_budget=0
            elif register == "birdsong_lock":
                # Eruption confirms pleasure in the action already underway; it
                # never invents permission in an otherwise empty context.
                self.birdsong_locks += 1
                self.fiend_birdsong_literacy = min(1.0, self.fiend_birdsong_literacy + 0.045)
                if self.last_surge:
                    self.pending_intent = "continue"
                    self.desired_surge = self.last_surge
                    self.reproductive_pull = min(1.0, self.reproductive_pull + 0.07 * self.fiend_birdsong_literacy)
                    if self.last_surge=="purple":
                        self.purple_confirmations+=1
                        # Confirmation licenses repeating the action once, not
                        # inventing a new or terminal permission.
                        self.tentative_purple_budget=max(self.tentative_purple_budget,1+(1 if self.animal_spiral>=0.62 else 0))
            elif register == "hana_evaluation":
                if any(x in text for x in ("no", "stop", "wait", "wrong", "careful")):
                    self.pending_intent = "withdraw"
                    self.corrected_overreaches += 1
                    self.withdrawal_pull = min(1.0, self.withdrawal_pull + 0.30)
                    self.fiend_confidence = max(0.05, self.fiend_confidence - 0.16)
                    self.thrust_pressure=max(0.0,self.thrust_pressure-0.13)
                    self.tentative_purple_budget=0
                    self.desired_surge="green"
                else:
                    self.trust = min(1.0, self.trust + 0.018)
        else:
            self.fiend_confidence = min(1.0, self.fiend_confidence + 0.012)
            self.voice_fascination=min(1.0,self.voice_fascination+0.010)
        self.voice_fascination=min(1.0,self.voice_fascination+(0.012 if register in ("birdsong_lock","coy_escalation") else 0.003))
        self.mutual_humiliation=min(1.0,self.mutual_humiliation+(0.008 if register in ("sentence_repair","birdsong_lock") else 0.002))
        self.animal_spiral=min(1.0,max(0.0,(self.arousal*0.40+self.voice_fascination*0.30+self.mutual_humiliation*0.30)-0.34))
        # Fertility changes the emotional weight of risk, not the route by fiat.
        self.arousal = min(1.0, self.arousal + 0.0015 + (0.0015 if register in ("coy_escalation", "birdsong_lock") else 0.0))
        self._evaluate_release()
        self._log("voice", speaker=speaker, transcript=transcript, register=register, prosody=prosody)

    def choose_surge(self, available_tier: int) -> str:
        if self.pending_intent == "withdraw":
            return ""
        desired = self.desired_surge or self.last_surge or "purple"
        if desired=="purple" and self.tentative_purple_budget<=0 and self.pending_intent not in ("continue","repeat"):
            # His own desire cannot authorize another thrust test.
            desired="red" if int(available_tier)>=2 else ""
        legal = {1: ("purple",), 2: ("purple", "red"), 3: ("purple", "red", "green")}.get(max(1, int(available_tier)), ("purple",))
        if desired not in legal:
            desired = legal[-1]
        return desired

    def observe_bodily_interruption(self) -> None:
        """Treat Hana's small loss of composure as dialogue, not a gag roll."""
        self.bodily_weakness_pending=True
        self.mutual_humiliation=min(1.0,self.mutual_humiliation+0.065)
        self.voice_fascination=min(1.0,self.voice_fascination+0.035)
        self.thrust_pressure=max(0.0,self.thrust_pressure-0.055)
        self.pending_intent="listen"
        self.desired_surge="green"
        self._log("bodily_interruption")

    def observe_surge(self, kind: str) -> None:
        kind = str(kind or "").lower()
        if kind not in ("purple", "red", "green"):
            return
        requested = self.desired_surge
        self.last_surge = kind
        self.actions += 1
        self.recent.append(("surge", kind, self.pending_intent, requested))
        if requested == kind:
            self.commands_obeyed += 1
            self.trust = min(1.0, self.trust + 0.035)
        elif self.pending_intent not in ("listen", "test", "continue"):
            self.fiend_confidence = max(0.05, self.fiend_confidence - 0.035)
        else:
            self.pleased_one_ups += 1
            self.fiend_confidence = min(1.0, self.fiend_confidence + 0.045)
        # Intensity accumulates through many coherent answers. This creates a
        # full performance without an elapsed-time gate or protected climax.
        arousal_gains = {"purple": 0.005, "red": 0.007, "green": 0.010}
        arousal_gain = arousal_gains[kind]
        self.arousal = min(1.0, self.arousal + arousal_gain)
        # Purple is the repeated thrust route. Red and green are fully intense
        # alternate postures that bleed thrust-count pressure without rewinding
        # the physical presentation or reducing pleasure.
        if kind == "purple":
            self.thrust_pressure = min(1.0, self.thrust_pressure + 0.052 * (0.72 + self.trust * 0.28) * (1.0+1.45*self.animal_spiral))
            self.edge_control=max(0.0,self.edge_control-(0.018+0.022*self.animal_spiral))
            self.tentative_purple_budget=max(0,self.tentative_purple_budget-1)
            self.safe_release_pressure=max(0.0,self.safe_release_pressure-0.028)
        elif kind == "red":
            self.thrust_pressure = max(0.0, self.thrust_pressure - 0.055)
            self.reproductive_pull = max(0.0, self.reproductive_pull - 0.018)
            self.edge_control=min(1.0,self.edge_control+0.030)
            self.safe_release_pressure=min(1.0,self.safe_release_pressure+0.042)
        else:
            self.thrust_pressure = max(0.0, self.thrust_pressure - 0.085)
            self.reproductive_pull = max(0.0, self.reproductive_pull - 0.028)
            self.edge_control=min(1.0,self.edge_control+0.045)
            self.safe_release_pressure=min(1.0,self.safe_release_pressure+0.062)
        self.withdrawal_pull = max(0.0, self.withdrawal_pull - 0.035)
        self.pending_intent = "evaluate"
        self._evaluate_release()
        self._log("surge", kind=kind, requested=requested)

    def _evaluate_release(self) -> None:
        if self.committed:
            return
        # Release is physiological and relational: enough accumulated arousal
        # plus a decisive shared direction. There is no elapsed-time gate.
        reproductive_direction = min(1.0, self.reproductive_pull * 0.58 + self.thrust_pressure * 0.72)
        decisive = max(reproductive_direction, self.withdrawal_pull)
        readiness = self.arousal * 0.80 + self.trust * 0.14 + decisive * 0.08
        if readiness < 0.92 or self.actions < 2:
            return
        reproductive = (
            self.thrust_pressure >= 0.62
            and self.purple_confirmations>=2
            and self.reopened_risks>=2
            and reproductive_direction > (self.withdrawal_pull + 0.10)
        )
        # A last legible withdrawal remains binding; otherwise their performed
        # trajectory determines the insertion route.
        if self.pending_intent == "withdraw":
            reproductive = False
        safe_release=(self.safe_release_pressure>=0.58 or
                      (self.pending_intent=="withdraw" and self.safe_release_pressure>=0.42))
        if not reproductive and not safe_release:
            return
        self.climax_kind = "vaginal" if reproductive else "anal"
        self.climax_ready = True
        self.committed = True
        self._log("commit", kind=self.climax_kind)

    def performance_composure(self) -> float:
        """Live vocal/animation composure, derived from the authored exchange.

        This is deliberately not elapsed time.  Red/green posture work can
        settle thrust danger while the pair remain highly aroused; repeated
        purple answers, reproductive pull, and the animal spiral make speech
        progressively less orderly.  The value is presentation authority only
        and never commits an outcome by itself.
        """
        disorder = (
            self.animal_spiral * 0.34
            + self.thrust_pressure * 0.28
            + self.reproductive_pull * 0.18
            + self.arousal * 0.14
            + (1.0 - self.edge_control) * 0.06
        )
        if self.pending_intent == "withdraw":
            disorder -= 0.12
        elif self.pending_intent in ("continue", "repeat") and self.last_surge == "purple":
            disorder += 0.08
        return max(0.0, min(1.0, 1.0 - disorder))

    def snapshot(self) -> dict:
        return {
            "fertility": round(self.fertility, 4), "arousal": round(self.arousal, 4),
            "courtesy_history": round(self.courtesy_history, 4),
            "hana_teasing_confidence": round(self.hana_teasing_confidence, 4),
            "fiend_birdsong_literacy": round(self.fiend_birdsong_literacy, 4),
            "reproductive_pull": round(self.reproductive_pull, 4),
            "thrust_pressure": round(self.thrust_pressure, 4),
            "safe_release_pressure":round(self.safe_release_pressure,4),
            "edge_control":round(self.edge_control,4),
            "voice_fascination":round(self.voice_fascination,4),
            "mutual_humiliation":round(self.mutual_humiliation,4),
            "animal_spiral":round(self.animal_spiral,4),
            "invitation_clarity":round(self.invitation_clarity,4),
            "purple_confirmations":self.purple_confirmations,
            "reopened_risks":self.reopened_risks,
            "withdrawal_pull": round(self.withdrawal_pull, 4), "trust": round(self.trust, 4),
            "fiend_confidence": round(self.fiend_confidence, 4), "intent": self.pending_intent,
            "performance_composure": round(self.performance_composure(), 4),
            "desired_surge": self.desired_surge, "last_surge": self.last_surge,
            "climax_ready": self.climax_ready, "climax_kind": self.climax_kind,
            "exchanges": self.exchanges, "actions": self.actions,
            "commands_obeyed": self.commands_obeyed,
            "corrected_overreaches": self.corrected_overreaches,
            "pleased_one_ups": self.pleased_one_ups,
            "birdsong_locks": self.birdsong_locks,
        }
