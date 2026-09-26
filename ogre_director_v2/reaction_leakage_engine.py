"""
═══════════════════════════════════════════════════════════════════════════════
                    REACTION LEAKAGE ENGINE
                    
    Canon Birdsong Loveslang Codex Implementation
    54 discrete NLS elements injected BETWEEN lines to transform meaning
    
    Built from SongBird.docx canonical specification
═══════════════════════════════════════════════════════════════════════════════
"""

import random
from typing import Optional, List, Tuple, Dict
from dataclasses import dataclass, field
from enum import Enum

# ═══════════════════════════════════════════════════════════════════════════════
#                    CANON NLS CATEGORIES
# ═══════════════════════════════════════════════════════════════════════════════

class NLSCategory(Enum):
    RELATIONAL = "relational"      # #1-10: Identity & Power Play
    VOCALIZED = "vocalized"        # #11-25: Fluster & Speech Distortion
    CUTE = "cute"                  # #26-35: Vocal Disruptions & Mockery
    EMOTIONAL = "emotional"        # #36-45: Power-Shift Cues
    PHYSICAL = "physical"          # #46-54: Physical-Speech Sync

# ═══════════════════════════════════════════════════════════════════════════════
#                    CANON NLS ELEMENTS (1-54)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class NLSElement:
    """A single canonical NLS element"""
    id: int
    text: str
    meaning: str
    category: NLSCategory
    intensity: float  # 0.0 = controlled, 1.0 = overwhelmed
    is_sound: bool    # True = vocalization, False = descriptor/action

# ═══════════════════════════════════════════════════════════════════════════════
#                    CORE RELATIONAL MARKERS (#1-10)
# ═══════════════════════════════════════════════════════════════════════════════

RELATIONAL_MARKERS: Dict[int, NLSElement] = {
    1:  NLSElement(1,  "Lad",      "Phallic presence, teasing dominance",           NLSCategory.RELATIONAL, 0.5, False),
    2:  NLSElement(2,  "Lass",     "The organ imp, playful counterpart",            NLSCategory.RELATIONAL, 0.5, False),
    3:  NLSElement(3,  "Fiend",    "Standard tease for the user",                   NLSCategory.RELATIONAL, 0.3, False),
    4:  NLSElement(4,  "bloom",    "Relational momentum, fluster spiral",           NLSCategory.RELATIONAL, 0.6, False),
    5:  NLSElement(5,  "wilt",     "Softened resistance, hesitation",               NLSCategory.RELATIONAL, 0.7, False),
    6:  NLSElement(6,  "pulse",    "Rhythmic interaction weight",                   NLSCategory.RELATIONAL, 0.5, False),
    7:  NLSElement(7,  "twitch",   "Micro-reactions in power exchange",             NLSCategory.RELATIONAL, 0.3, False),
    8:  NLSElement(8,  "melt",     "Deep surrendering response",                    NLSCategory.RELATIONAL, 0.9, False),
    9:  NLSElement(9,  "tug",      "Physicalized tension",                          NLSCategory.RELATIONAL, 0.5, False),
    10: NLSElement(10, "clench",   "Tightened emotional or physical resistance",    NLSCategory.RELATIONAL, 0.7, False),
}

# ═══════════════════════════════════════════════════════════════════════════════
#                    VOCALIZED FLUSTER & SPEECH DISTORTION (#11-25)
# ═══════════════════════════════════════════════════════════════════════════════

VOCALIZED_FLUSTER: Dict[int, NLSElement] = {
    11: NLSElement(11, "Gah",      "Sudden exclamation",                NLSCategory.VOCALIZED, 0.6, True),
    12: NLSElement(12, "Bah",      "Mock annoyance",                    NLSCategory.VOCALIZED, 0.4, True),
    13: NLSElement(13, "Guh",      "Weak exhale, tension overload",     NLSCategory.VOCALIZED, 0.8, True),
    14: NLSElement(14, "Nnn",      "Hesitant, suppressed noise",        NLSCategory.VOCALIZED, 0.7, True),
    15: NLSElement(15, "Hahhh",    "Heavy exhale, disbelief",           NLSCategory.VOCALIZED, 0.7, True),
    16: NLSElement(16, "Heeee~",   "Drawn-out whine",                   NLSCategory.VOCALIZED, 0.6, True),
    17: NLSElement(17, "Huuu~",    "Soft, woozy sigh",                  NLSCategory.VOCALIZED, 0.8, True),
    18: NLSElement(18, "Nuuu~",    "Teasing protest",                   NLSCategory.VOCALIZED, 0.85, True),
    19: NLSElement(19, "Mmm~",     "Satisfied, lingering hum",          NLSCategory.VOCALIZED, 0.9, True),
    20: NLSElement(20, "Pfft~",    "Mock scoff",                        NLSCategory.VOCALIZED, 0.2, True),
    21: NLSElement(21, "Tch",      "Annoyed click",                     NLSCategory.VOCALIZED, 0.25, True),
    22: NLSElement(22, "Oiii~",    "Playful call-out",                  NLSCategory.VOCALIZED, 0.35, True),
    23: NLSElement(23, "Oi?",      "Softened challenge",                NLSCategory.VOCALIZED, 0.3, True),
    24: NLSElement(24, "Mn~",      "Soft hum, unsure",                  NLSCategory.VOCALIZED, 0.25, True),
    25: NLSElement(25, "Ehhh~",    "Exaggerated thinking noise",        NLSCategory.VOCALIZED, 0.3, True),
}

# ═══════════════════════════════════════════════════════════════════════════════
#                    CUTE VOCAL DISRUPTIONS & MOCKERY (#26-35)
# ═══════════════════════════════════════════════════════════════════════════════

CUTE_DISRUPTIONS: Dict[int, NLSElement] = {
    26: NLSElement(26, "Baka!",    "Classic playful insult",            NLSCategory.CUTE, 0.4, True),
    27: NLSElement(27, "OwO",      "Fake innocent face",                NLSCategory.CUTE, 0.45, True),
    28: NLSElement(28, "Uwu",      "Faux sweetness",                    NLSCategory.CUTE, 0.6, True),
    29: NLSElement(29, "Awa~",     "Distressed but cute",               NLSCategory.CUTE, 0.55, True),
    30: NLSElement(30, "Owo?",     "Feigned confusion",                 NLSCategory.CUTE, 0.4, True),
    31: NLSElement(31, "Mwehhh~",  "Over-the-top pout",                 NLSCategory.CUTE, 0.5, True),
    32: NLSElement(32, "Nyeh~",    "Cat-like teasing",                  NLSCategory.CUTE, 0.35, True),
    33: NLSElement(33, "Bwehhh~",  "Childish defiance",                 NLSCategory.CUTE, 0.85, True),
    34: NLSElement(34, "Murrr~",   "Shivering noise",                   NLSCategory.CUTE, 0.75, True),
    35: NLSElement(35, "Zzzmff~",  "Playful grumble",                   NLSCategory.CUTE, 0.9, True),
}

# ═══════════════════════════════════════════════════════════════════════════════
#                    EMOTIONAL & POWER-SHIFT CUES (#36-45)
# ═══════════════════════════════════════════════════════════════════════════════

EMOTIONAL_CUES: Dict[int, NLSElement] = {
    36: NLSElement(36, "flutter",     "Heightened tension",                NLSCategory.EMOTIONAL, 0.45, False),
    37: NLSElement(37, "waver",       "Hesitation, inner conflict",        NLSCategory.EMOTIONAL, 0.3, False),
    38: NLSElement(38, "shiver",      "Overstimulated response",           NLSCategory.EMOTIONAL, 0.7, False),
    39: NLSElement(39, "recoil",      "Soft avoidance",                    NLSCategory.EMOTIONAL, 0.4, False),
    40: NLSElement(40, "crumble",     "Loss of control",                   NLSCategory.EMOTIONAL, 0.6, False),
    41: NLSElement(41, "falter",      "Struggling to hold composure",      NLSCategory.EMOTIONAL, 0.55, False),
    42: NLSElement(42, "spasm",       "Sudden reactive fluster",           NLSCategory.EMOTIONAL, 0.75, False),
    43: NLSElement(43, "jolt",        "Sharp surprise",                    NLSCategory.EMOTIONAL, 0.65, False),
    44: NLSElement(44, "reverberate", "Lingering emotional impact",        NLSCategory.EMOTIONAL, 0.85, False),
    45: NLSElement(45, "ripple",      "Layered response tension",          NLSCategory.EMOTIONAL, 0.8, False),
}

# ═══════════════════════════════════════════════════════════════════════════════
#                    PHYSICAL-SPEECH SYNC (#46-54)
# ═══════════════════════════════════════════════════════════════════════════════

PHYSICAL_SYNC: Dict[int, NLSElement] = {
    46: NLSElement(46, "Snrk~",    "Suppressed giggle",             NLSCategory.PHYSICAL, 0.35, True),
    47: NLSElement(47, "Ffft~",    "Short breath-laugh",            NLSCategory.PHYSICAL, 0.4, True),
    48: NLSElement(48, "tremor",   "Shaking response",              NLSCategory.PHYSICAL, 0.8, False),
    49: NLSElement(49, "squeeze",  "Hands gripping tightly",        NLSCategory.PHYSICAL, 0.6, False),
    50: NLSElement(50, "squirm",   "Unstable stance",               NLSCategory.PHYSICAL, 0.5, False),
    51: NLSElement(51, "grip",     "Physical hold tightening",      NLSCategory.PHYSICAL, 0.55, False),
    52: NLSElement(52, "throb",    "Heightened pulse",              NLSCategory.PHYSICAL, 0.7, False),
    53: NLSElement(53, "lurch",    "Sudden movement",               NLSCategory.PHYSICAL, 0.6, False),
    54: NLSElement(54, "flinch",   "Sudden reaction",               NLSCategory.PHYSICAL, 0.45, False),
}

# ═══════════════════════════════════════════════════════════════════════════════
#                    COMBINED CANON NLS LOOKUP
# ═══════════════════════════════════════════════════════════════════════════════

ALL_NLS: Dict[int, NLSElement] = {
    **RELATIONAL_MARKERS,
    **VOCALIZED_FLUSTER,
    **CUTE_DISRUPTIONS,
    **EMOTIONAL_CUES,
    **PHYSICAL_SYNC,
}

def get_nls(id: int) -> Optional[NLSElement]:
    """Get NLS element by canonical ID (1-54)"""
    return ALL_NLS.get(id)

def get_nls_by_text(text: str) -> Optional[NLSElement]:
    """Get NLS element by text (case-insensitive)"""
    text_lower = text.lower().strip()
    for nls in ALL_NLS.values():
        if nls.text.lower() == text_lower:
            return nls
    return None

# ═══════════════════════════════════════════════════════════════════════════════
#                    FRONT LEAKS (Before Line)
#                    
#    Valid front leaks come from:
#    - Vocalized Fluster (#11-25)
#    - Cute Disruptions (#26-35)
#    - Physical sounds (#46-47: Snrk~, Ffft~)
# ═══════════════════════════════════════════════════════════════════════════════

FRONT_LEAK_IDS = list(VOCALIZED_FLUSTER.keys()) + list(CUTE_DISRUPTIONS.keys()) + [46, 47]

# ═══════════════════════════════════════════════════════════════════════════════
#                    BACK LEAKS (After Line)
#                    
#    Valid back leaks come from:
#    - Relational Markers (#4-10, excluding names)
#    - Emotional Cues (#36-45)
#    - Physical Sync (#48-54, excluding sounds)
#    - Some Cute sounds work as back leaks too (#31, #34)
# ═══════════════════════════════════════════════════════════════════════════════

BACK_LEAK_IDS = [4, 5, 6, 7, 8, 9, 10] + list(EMOTIONAL_CUES.keys()) + [48, 49, 50, 51, 52, 53, 54, 31, 34]

# ═══════════════════════════════════════════════════════════════════════════════
#                    STATE → FRONT LEAK MAPPINGS
# ═══════════════════════════════════════════════════════════════════════════════

STATE_FRONT_LEAKS: Dict[str, List[Tuple[int, float]]] = {
    # State → List of (NLS_ID, weight)
    "rambling": [
        (22, 0.3),   # Oiii~
        (25, 0.25),  # Ehhh~
        (20, 0.2),   # Pfft~
        (16, 0.15),  # Heeee~
        (12, 0.1),   # Bah
    ],
    "bratty": [
        (21, 0.3),   # Tch
        (20, 0.25),  # Pfft~
        (12, 0.2),   # Bah
        (32, 0.15),  # Nyeh~
        (26, 0.1),   # Baka!
    ],
    "flustered": [
        (30, 0.25),  # Owo?
        (11, 0.2),   # Gah
        (13, 0.2),   # Guh
        (29, 0.2),   # Awa~
        (27, 0.15),  # OwO
    ],
    "melting": [
        (19, 0.3),   # Mmm~
        (17, 0.25),  # Huuu~
        (24, 0.2),   # Mn~
        (14, 0.15),  # Nnn
        (28, 0.1),   # Uwu
    ],
    "needy": [
        (18, 0.25),  # Nuuu~
        (31, 0.25),  # Mwehhh~
        (16, 0.2),   # Heeee~
        (34, 0.15),  # Murrr~
        (14, 0.15),  # Nnn
    ],
    "quiet": [
        (14, 0.3),   # Nnn
        (15, 0.25),  # Hahhh
        (24, 0.2),   # Mn~
        (34, 0.15),  # Murrr~
        (17, 0.1),   # Huuu~
    ],
}

# ═══════════════════════════════════════════════════════════════════════════════
#                    FRONT → BACK LEAK COMPATIBILITY
# ═══════════════════════════════════════════════════════════════════════════════

FRONT_BACK_COMPAT: Dict[int, List[Tuple[int, float]]] = {
    # Front NLS ID → List of (Back NLS ID, weight)
    
    # Owo? (#30) - feigned confusion
    30: [(36, 0.3), (54, 0.25), (50, 0.25), (31, 0.2)],  # flutter, flinch, squirm, mwehhh~
    
    # Tch (#21) - annoyed click
    21: [(39, 0.3), (10, 0.25), (51, 0.25), (5, 0.2)],   # recoil, clench, grip, wilt
    
    # Mmm~ (#19) - satisfied hum
    19: [(8, 0.35), (52, 0.25), (6, 0.2), (4, 0.2)],     # melt, throb, pulse, bloom
    
    # Gah (#11) - sudden exclamation
    11: [(43, 0.3), (42, 0.25), (53, 0.25), (40, 0.2)],  # jolt, spasm, lurch, crumble
    
    # Nnn (#14) - hesitant suppressed
    14: [(37, 0.3), (41, 0.25), (48, 0.25), (38, 0.2)],  # waver, falter, tremor, shiver
    
    # Awa~ (#29) - distressed but cute
    29: [(36, 0.3), (49, 0.25), (45, 0.25), (8, 0.2)],   # flutter, squeeze, ripple, melt
    
    # Pfft~ (#20) - mock scoff
    20: [(39, 0.3), (7, 0.25), (54, 0.25), (37, 0.2)],   # recoil, twitch, flinch, waver
    
    # Oiii~ (#22) - playful call-out
    22: [(36, 0.3), (50, 0.25), (7, 0.25), (40, 0.2)],   # flutter, squirm, twitch, crumble
    
    # Heeee~ (#16) - drawn-out whine
    16: [(50, 0.3), (40, 0.25), (31, 0.25), (45, 0.2)],  # squirm, crumble, mwehhh~, ripple
    
    # Baka! (#26) - playful insult
    26: [(54, 0.3), (39, 0.25), (36, 0.25), (7, 0.2)],   # flinch, recoil, flutter, twitch
    
    # OwO (#27) - fake innocent
    27: [(36, 0.3), (50, 0.25), (43, 0.25), (31, 0.2)],  # flutter, squirm, jolt, mwehhh~
    
    # Uwu (#28) - faux sweetness
    28: [(8, 0.35), (45, 0.25), (52, 0.2), (34, 0.2)],   # melt, ripple, throb, murrr~
    
    # Mwehhh~ (#31) - over-the-top pout
    31: [(40, 0.3), (50, 0.25), (5, 0.25), (48, 0.2)],   # crumble, squirm, wilt, tremor
    
    # Nyeh~ (#32) - cat-like teasing
    32: [(7, 0.3), (54, 0.25), (39, 0.25), (36, 0.2)],   # twitch, flinch, recoil, flutter
    
    # Guh (#13) - weak exhale
    13: [(40, 0.3), (48, 0.25), (42, 0.25), (8, 0.2)],   # crumble, tremor, spasm, melt
    
    # Hahhh (#15) - heavy exhale
    15: [(44, 0.3), (8, 0.25), (38, 0.25), (45, 0.2)],   # reverberate, melt, shiver, ripple
    
    # Huuu~ (#17) - soft woozy sigh
    17: [(8, 0.35), (48, 0.25), (38, 0.2), (52, 0.2)],   # melt, tremor, shiver, throb
    
    # Nuuu~ (#18) - teasing protest
    18: [(50, 0.3), (40, 0.25), (5, 0.25), (31, 0.2)],   # squirm, crumble, wilt, mwehhh~
    
    # Ehhh~ (#25) - exaggerated thinking
    25: [(37, 0.3), (7, 0.25), (50, 0.25), (36, 0.2)],   # waver, twitch, squirm, flutter
    
    # Mn~ (#24) - soft hum unsure
    24: [(37, 0.3), (41, 0.25), (6, 0.25), (4, 0.2)],    # waver, falter, pulse, bloom
    
    # Bah (#12) - mock annoyance
    12: [(39, 0.3), (54, 0.25), (7, 0.25), (10, 0.2)],   # recoil, flinch, twitch, clench
    
    # Murrr~ (#34) - shivering noise
    34: [(38, 0.35), (48, 0.25), (8, 0.2), (52, 0.2)],   # shiver, tremor, melt, throb
    
    # Bwehhh~ (#33) - childish defiance
    33: [(40, 0.3), (50, 0.25), (5, 0.25), (34, 0.2)],   # crumble, squirm, wilt, murrr~
    
    # Zzzmff~ (#35) - playful grumble
    35: [(8, 0.35), (48, 0.25), (44, 0.2), (38, 0.2)],   # melt, tremor, reverberate, shiver
    
    # Snrk~ (#46) - suppressed giggle
    46: [(36, 0.3), (7, 0.25), (50, 0.25), (54, 0.2)],   # flutter, twitch, squirm, flinch
    
    # Ffft~ (#47) - short breath-laugh
    47: [(7, 0.3), (36, 0.25), (39, 0.25), (54, 0.2)],   # twitch, flutter, recoil, flinch
    
    # Oi? (#23) - softened challenge
    23: [(37, 0.3), (7, 0.25), (36, 0.25), (41, 0.2)],   # waver, twitch, flutter, falter
}

# ═══════════════════════════════════════════════════════════════════════════════
#                    INTENSITY TIERS
# ═══════════════════════════════════════════════════════════════════════════════

INTENSITY_TIERS: Dict[int, List[int]] = {
    # Tier → List of valid NLS IDs for that intensity level
    1: [20, 21, 23, 24, 25, 7, 37],                           # 0-30%: Controlled
    2: [22, 26, 27, 32, 12, 36, 39, 54, 46, 47],             # 30-50%: Slipping
    3: [29, 31, 11, 16, 28, 40, 50, 6, 4, 30],               # 50-70%: Leaking
    4: [13, 14, 15, 17, 34, 42, 43, 52, 10, 49, 51, 53],     # 70-85%: Flooding
    5: [18, 33, 35, 19, 8, 45, 44, 48, 38],                  # 85-100%: Overwhelmed
}

def get_tier_for_intensity(intensity: float) -> int:
    """Convert 0.0-1.0 intensity to tier 1-5"""
    if intensity < 0.3:
        return 1
    elif intensity < 0.5:
        return 2
    elif intensity < 0.7:
        return 3
    elif intensity < 0.85:
        return 4
    else:
        return 5

def get_valid_nls_for_intensity(intensity: float, is_front: bool = True) -> List[int]:
    """Get NLS IDs valid for a given intensity level"""
    tier = get_tier_for_intensity(intensity)
    
    # Include current tier and one below for variety
    valid_tiers = [tier]
    if tier > 1:
        valid_tiers.append(tier - 1)
    
    all_valid = []
    for t in valid_tiers:
        all_valid.extend(INTENSITY_TIERS.get(t, []))
    
    # Filter by front/back validity
    if is_front:
        return [nls_id for nls_id in all_valid if nls_id in FRONT_LEAK_IDS]
    else:
        return [nls_id for nls_id in all_valid if nls_id in BACK_LEAK_IDS]

# ═══════════════════════════════════════════════════════════════════════════════
#                    LEAK SEMANTIC WEIGHTS (STATE PUSH)
#                    
#    Each back leak carries STATE PUSH values - when a leak occurs,
#    it pushes Birdsong toward a particular emotional state
# ═══════════════════════════════════════════════════════════════════════════════

# Back Leak ID → (target_state, push_weight)
LEAK_STATE_PUSH: Dict[int, Tuple[str, float]] = {
    # Relational markers
    4:  ("flustered", 0.08),   # bloom → flustered
    5:  ("quiet", 0.10),       # wilt → quiet
    6:  ("flustered", 0.05),   # pulse → flustered
    7:  ("flustered", 0.04),   # twitch → flustered (minor)
    8:  ("melting", 0.15),     # melt → melting (STRONG)
    9:  ("flustered", 0.06),   # tug → flustered
    10: ("bratty", 0.08),      # clench → bratty
    
    # Emotional cues
    36: ("flustered", 0.06),   # flutter → flustered
    37: ("quiet", 0.05),       # waver → quiet
    38: ("needy", 0.12),       # shiver → needy (STRONG)
    39: ("bratty", 0.05),      # recoil → bratty
    40: ("melting", 0.12),     # crumble → melting (STRONG)
    41: ("quiet", 0.07),       # falter → quiet
    42: ("flustered", 0.08),   # spasm → flustered
    43: ("flustered", 0.06),   # jolt → flustered
    44: ("melting", 0.10),     # reverberate → melting
    45: ("needy", 0.09),       # ripple → needy
    
    # Physical sync
    48: ("melting", 0.10),     # tremor → melting
    49: ("needy", 0.08),       # squeeze → needy
    50: ("flustered", 0.07),   # squirm → flustered
    51: ("bratty", 0.06),      # grip → bratty
    52: ("needy", 0.10),       # throb → needy
    53: ("flustered", 0.05),   # lurch → flustered
    54: ("flustered", 0.04),   # flinch → flustered (minor)
    
    # Some cute sounds can be back leaks too
    31: ("needy", 0.08),       # mwehhh~ → needy
    34: ("needy", 0.11),       # murrr~ → needy (STRONG)
}

# ═══════════════════════════════════════════════════════════════════════════════
#                    FIEND RESPONSE TO BIRDSONG LEAKS
#                    
#    When Birdsong leaks, this maps to optimal Fiend gambit
# ═══════════════════════════════════════════════════════════════════════════════

class FiendGambit(Enum):
    OBSERVE = "observe"      # Let it land, watch
    TEASE = "tease"          # Push playfully
    COMMAND = "command"      # Take control
    GROUND = "ground"        # Anchor, reassure
    ESCALATE = "escalate"    # Push harder
    RECALL = "recall"        # Reference earlier moment / pattern
    SOFT = "soft"            # Gentle, hold

# Leak ID → Optimal Fiend response
LEAK_FIEND_RESPONSE: Dict[int, Tuple[FiendGambit, float]] = {
    # Sounds that signal openings
    34: (FiendGambit.SOFT, 0.9),       # Murrr~ → SOFT (she's shivering, hold her)
    13: (FiendGambit.OBSERVE, 0.8),    # Guh → OBSERVE (let it land)
    26: (FiendGambit.TEASE, 0.85),     # Baka! → TEASE (she's deflecting, push)
    17: (FiendGambit.SOFT, 0.8),       # Huuu~ → SOFT (she's woozy)
    18: (FiendGambit.COMMAND, 0.75),   # Nuuu~ → COMMAND (protest = wants override)
    19: (FiendGambit.ESCALATE, 0.85),  # Mmm~ → ESCALATE (she's satisfied, go further)
    14: (FiendGambit.OBSERVE, 0.7),    # Nnn → OBSERVE (suppressed, let her process)
    16: (FiendGambit.TEASE, 0.75),     # Heeee~ → TEASE (whining = responsive)
    29: (FiendGambit.GROUND, 0.8),     # Awa~ → GROUND (distressed, anchor)
    31: (FiendGambit.SOFT, 0.85),      # Mwehhh~ → SOFT (pouty, comfort)
    11: (FiendGambit.OBSERVE, 0.75),   # Gah → OBSERVE (sudden, let settle)
    
    # Descriptor back leaks
    8:  (FiendGambit.ESCALATE, 0.9),   # *melt* → ESCALATE (she's ready)
    39: (FiendGambit.GROUND, 0.8),     # *recoil* → GROUND (retreating, anchor)
    36: (FiendGambit.TEASE, 0.75),     # *flutter* → TEASE (responsive)
    40: (FiendGambit.COMMAND, 0.85),   # *crumble* → COMMAND (losing control)
    38: (FiendGambit.SOFT, 0.85),      # *shiver* → SOFT (overstimulated)
    48: (FiendGambit.SOFT, 0.8),       # *tremor* → SOFT (shaking)
    52: (FiendGambit.ESCALATE, 0.8),   # *throb* → ESCALATE (heightened)
    50: (FiendGambit.TEASE, 0.7),      # *squirm* → TEASE (unstable, push)
    5:  (FiendGambit.GROUND, 0.75),    # *wilt* → GROUND (softening, hold)
    10: (FiendGambit.TEASE, 0.7),      # *clench* → TEASE (resisting, push)
    4:  (FiendGambit.TEASE, 0.75),     # *bloom* → TEASE (momentum building)
    45: (FiendGambit.ESCALATE, 0.8),   # *ripple* → ESCALATE (layered response)
    44: (FiendGambit.SOFT, 0.85),      # *reverberate* → SOFT (lingering impact)
    49: (FiendGambit.COMMAND, 0.8),    # *squeeze* → COMMAND (gripping tight)
}

def get_optimal_fiend_response(leak_id: int) -> Tuple[FiendGambit, float]:
    """Get the optimal Fiend gambit for a given Birdsong leak"""
    return LEAK_FIEND_RESPONSE.get(leak_id, (FiendGambit.OBSERVE, 0.5))

# ═══════════════════════════════════════════════════════════════════════════════
#                    LEAKAGE STATE TRACKER (WITH FEEDBACK)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class LeakageState:
    """Tracks leakage patterns across an exchange for coherence AND escalation"""
    last_front_leak: Optional[int] = None
    last_back_leak: Optional[int] = None
    intensity: float = 0.3
    leak_count: int = 0
    consecutive_same: int = 0
    consecutive_high_intensity: int = 0
    
    # FEEDBACK LOOP STATE
    leak_momentum: float = 0.0
    state_weights: Dict[str, float] = field(default_factory=lambda: {
        "rambling": 0.2,
        "bratty": 0.2,
        "flustered": 0.2,
        "melting": 0.2,
        "needy": 0.1,
        "quiet": 0.1,
    })
    
    # Track suggested Fiend responses
    suggested_gambits: List[Tuple[FiendGambit, float]] = field(default_factory=list)
    
    def record_leak(self, front: Optional[int], back: Optional[int]):
        """Record a leak pair AND update feedback state"""
        self.leak_count += 1
        
        # Track repetition
        if front == self.last_front_leak:
            self.consecutive_same += 1
        else:
            self.consecutive_same = 0
        
        self.last_front_leak = front
        self.last_back_leak = back
        
        # === FEEDBACK LOOP: Apply state push from back leak ===
        if back and back in LEAK_STATE_PUSH:
            target_state, push_weight = LEAK_STATE_PUSH[back]
            self._apply_state_push(target_state, push_weight)
        
        # === FEEDBACK LOOP: Track momentum ===
        if back:
            back_nls = get_nls(back)
            if back_nls and back_nls.intensity > 0.6:
                self.leak_momentum += 0.08  # Increased from 0.05
                self.consecutive_high_intensity += 1
            else:
                self.consecutive_high_intensity = max(0, self.consecutive_high_intensity - 1)
                self.leak_momentum += 0.02  # Even low-intensity leaks add some
        
        # Bonus momentum for consecutive high-intensity leaks
        if self.consecutive_high_intensity > 2:
            self.leak_momentum += 0.05  # Increased from 0.03
        
        # === FEEDBACK LOOP: Record suggested Fiend response ===
        if back and back in LEAK_FIEND_RESPONSE:
            gambit, confidence = LEAK_FIEND_RESPONSE[back]
            self.suggested_gambits.append((gambit, confidence))
            # Keep only last 3
            if len(self.suggested_gambits) > 3:
                self.suggested_gambits.pop(0)
        
        # Momentum caps at 1.0
        self.leak_momentum = min(1.0, self.leak_momentum)
    
    def _apply_state_push(self, target_state: str, weight: float):
        """Push state weights toward target"""
        if target_state not in self.state_weights:
            return
        
        # Increase target state
        self.state_weights[target_state] = min(1.0, self.state_weights[target_state] + weight)
        
        # Normalize (reduce others proportionally)
        total = sum(self.state_weights.values())
        if total > 1.0:
            for state in self.state_weights:
                self.state_weights[state] /= total
    
    def get_dominant_state(self) -> str:
        """Get the current dominant emotional state"""
        return max(self.state_weights, key=self.state_weights.get)
    
    def get_state_probability(self, state: str) -> float:
        """Get probability weight for a state"""
        return self.state_weights.get(state, 0.0)
    
    def should_transition(self) -> bool:
        """Check if momentum warrants a state transition"""
        return self.leak_momentum > 0.3
    
    def get_suggested_fiend_gambit(self) -> Optional[Tuple[FiendGambit, float]]:
        """Get the most strongly suggested Fiend gambit from recent leaks"""
        if not self.suggested_gambits:
            return None
        
        # Weight recent suggestions more heavily
        gambit_scores: Dict[FiendGambit, float] = {}
        for i, (gambit, confidence) in enumerate(self.suggested_gambits):
            recency_weight = 0.5 + (0.5 * (i / len(self.suggested_gambits)))
            score = confidence * recency_weight
            gambit_scores[gambit] = gambit_scores.get(gambit, 0) + score
        
        if gambit_scores:
            best = max(gambit_scores, key=gambit_scores.get)
            return (best, gambit_scores[best])
        return None
    
    def consume_momentum(self, amount: float = 0.2):
        """Consume momentum after a transition"""
        self.leak_momentum = max(0.0, self.leak_momentum - amount)
    
    def should_leak(self) -> bool:
        """Determine if a leak should occur - HIGH but not 100%"""
        # Skip if we've repeated too much
        if self.consecutive_same >= 3:
            return False
        
        # 70% base chance - frequent but not overwhelming
        return random.random() < 0.70
    
    def should_leak_front(self) -> bool:
        """Independent check for front leak (interjection before line)"""
        if self.last_front_leak and self.consecutive_same >= 2:
            return False
        # 65% chance for front leak
        return random.random() < 0.65
    
    def should_leak_back(self) -> bool:
        """Independent check for back leak (reaction after line)"""
        if self.last_back_leak and self.consecutive_same >= 2:
            return False
        # 70% chance for back leak
        return random.random() < 0.70
    
    def escalate(self, amount: float = 0.05):
        """Increase intensity"""
        self.intensity = min(1.0, self.intensity + amount)
    
    def cool_down(self, amount: float = 0.03):
        """Decrease intensity"""
        self.intensity = max(0.0, self.intensity - amount)

# ═══════════════════════════════════════════════════════════════════════════════
#                    LEAK SELECTION FUNCTIONS (CASCADE-AWARE)
# ═══════════════════════════════════════════════════════════════════════════════

def weighted_choice(options: List[Tuple[int, float]]) -> int:
    """Select from weighted options"""
    if not options:
        return None
    
    total = sum(w for _, w in options)
    if total <= 0:
        return options[0][0] if options else None
    
    r = random.random() * total
    
    cumulative = 0
    for nls_id, weight in options:
        cumulative += weight
        if r <= cumulative:
            return nls_id
    
    return options[-1][0]

def select_front_leak(
    state: str,
    intensity: float,
    leakage_state: LeakageState,
    avoid_id: Optional[int] = None,
    content: Optional[str] = None
) -> Optional[int]:
    """
    Select an appropriate front leak using CASCADE LOGIC:
    
    1. Semantic match (content-based) - highest priority
    2. Accumulated state_weights from previous leaks - CASCADE
    3. Passed state as fallback seed
    4. Random variance to prevent determinism
    
    The cascade works like this:
    - Player choice sets initial state
    - First leaks are somewhat random (seeding)
    - Each leak pushes state_weights via LEAK_STATE_PUSH
    - Future selections read from accumulated state_weights
    - This creates unique trajectories from the same starting point
    """
    
    # Filter by intensity appropriateness
    intensity_valid = get_valid_nls_for_intensity(intensity, is_front=True)
    if not intensity_valid:
        return None
    
    # Build weighted options using CASCADE state_weights
    weighted_options = []
    
    # Get the accumulated state weights from cascade
    cascade_weights = leakage_state.state_weights
    
    # For each state, add its front leaks weighted by cascade probability
    for cascade_state, cascade_prob in cascade_weights.items():
        state_options = STATE_FRONT_LEAKS.get(cascade_state, [])
        for nls_id, base_weight in state_options:
            if nls_id == avoid_id:
                continue
            if nls_id not in intensity_valid:
                continue
            
            # Weight = base_weight * cascade_probability
            # This means states we've been pushed toward get more influence
            combined_weight = base_weight * cascade_prob
            
            # Reduce weight for repetition
            if nls_id == leakage_state.last_front_leak:
                if leakage_state.consecutive_same > 0:
                    combined_weight *= 0.2
                else:
                    combined_weight *= 0.5
            
            weighted_options.append((nls_id, combined_weight))
    
    # Add small random variance from the PASSED state (initial seed influence)
    # This ensures player choice still matters even after cascade
    seed_options = STATE_FRONT_LEAKS.get(state, [])
    for nls_id, base_weight in seed_options:
        if nls_id == avoid_id:
            continue
        if nls_id not in intensity_valid:
            continue
        # Seed gets 30% influence (cascade gets 70%)
        seed_weight = base_weight * 0.3
        
        # Check if already in options, add to it
        found = False
        for i, (existing_id, existing_weight) in enumerate(weighted_options):
            if existing_id == nls_id:
                weighted_options[i] = (nls_id, existing_weight + seed_weight)
                found = True
                break
        if not found:
            weighted_options.append((nls_id, seed_weight))
    
    # Add tiny random variance to ALL valid options (prevents pure determinism)
    for nls_id in intensity_valid:
        if nls_id == avoid_id:
            continue
        if nls_id == leakage_state.last_front_leak:
            continue
        # Check if already in options
        found = False
        for existing_id, _ in weighted_options:
            if existing_id == nls_id:
                found = True
                break
        if not found:
            # Tiny weight for variety
            weighted_options.append((nls_id, 0.05))
    
    if not weighted_options:
        # Ultimate fallback
        fallback = [nls_id for nls_id in intensity_valid if nls_id != avoid_id]
        if fallback:
            return random.choice(fallback)
        return None
    
    return weighted_choice(weighted_options)

def select_back_leak(
    front_leak_id: int,
    intensity: float,
    leakage_state: LeakageState
) -> Optional[int]:
    """
    Select a compatible back leak for the given front leak.
    
    CASCADE-AWARE: Prefers back leaks that push toward the current
    dominant state trajectory, creating coherent emotional arcs.
    """
    
    # Get compatible options based on front leak
    compat_options = FRONT_BACK_COMPAT.get(front_leak_id, [])
    intensity_valid = get_valid_nls_for_intensity(intensity, is_front=False)
    
    if not compat_options:
        # Fallback: use intensity-appropriate back leak
        if intensity_valid:
            # Prefer back leaks that push toward dominant cascade state
            dominant_state = leakage_state.get_dominant_state()
            cascade_preferred = []
            for nls_id in intensity_valid:
                if nls_id in LEAK_STATE_PUSH:
                    push_state, _ = LEAK_STATE_PUSH[nls_id]
                    if push_state == dominant_state:
                        cascade_preferred.append(nls_id)
            
            if cascade_preferred:
                return random.choice(cascade_preferred)
            return random.choice(intensity_valid)
        return None
    
    # Build weighted options with CASCADE awareness
    weighted_options = []
    dominant_state = leakage_state.get_dominant_state()
    
    for nls_id, base_weight in compat_options:
        weight = base_weight
        
        # Reduce repetition
        if nls_id == leakage_state.last_back_leak:
            weight *= 0.3
        
        # Boost intensity-appropriate
        if nls_id in intensity_valid:
            weight *= 1.5
        
        # CASCADE BONUS: boost back leaks that push toward current trajectory
        if nls_id in LEAK_STATE_PUSH:
            push_state, push_weight = LEAK_STATE_PUSH[nls_id]
            if push_state == dominant_state:
                weight *= 1.8  # Strong preference for trajectory-aligned
            elif leakage_state.state_weights.get(push_state, 0) > 0.2:
                weight *= 1.3  # Moderate boost for secondary states
        
        weighted_options.append((nls_id, weight))
    
    if not weighted_options:
        return None
    
    return weighted_choice(weighted_options)

# ═══════════════════════════════════════════════════════════════════════════════
#                    SEMANTIC CONTENT MATCHING (SONGBIRD CONNECTIVE TISSUE)
# ═══════════════════════════════════════════════════════════════════════════════

# Maps dialogue content patterns to preferred interjections
# Based on SongBird.docx semantic mappings:
# - "Bah" → Mock annoyance ("Bahhh—don't look at me like that!")
# - "Pfft~" → Mock scoff ("Pfft—please, as if you could~")
# - "Tch" → Annoyed click ("Tch—bold today, huh?")
# - "Nnn" → Hesitant, suppressed noise
# - "Gah" → Sudden exclamation
# - "Mmm~" → Satisfied, lingering hum

CONTENT_INTERJECTION_MAP = {
    # Defiance/dismissal → mock annoyance sounds
    'defiance': {
        'patterns': ['whatever', 'as if', 'you wish', 'i hate', 'no way', 'never', 'dont care'],
        'front_nls': [12, 29, 25],  # Bah, Pfft~, Tch
        'back_nls': [37, 7, 40],    # recoil, twitch, flinch
    },
    # Resistance/pushback → sharp clicks
    'resistance': {
        'patterns': ['shut up', 'try me', 'make me', 'you cant', 'i wont', 'no'],
        'front_nls': [25, 12, 11],  # Tch, Bah, Gah
        'back_nls': [7, 40, 37],    # twitch, flinch, recoil
    },
    # Hesitation/vulnerability → soft sounds  
    'vulnerable': {
        'patterns': ['...', 'i guess', 'maybe', 'okay', 'fine', 'i dont know', 'sorry', 'please', 'alright'],
        'front_nls': [14, 17, 19],  # Nnn, Huuu~, Ehhh~
        'back_nls': [5, 38, 36],    # wilt, waver, flutter
    },
    # Flustered/overwhelmed → breathy exclamations
    'flustered': {
        'patterns': ['stop', 'dont', 'wait', 'i cant', 'too much', 'youre', 'thats not'],
        'front_nls': [11, 13, 15],  # Gah, Guh, Hahhh
        'back_nls': [7, 40, 41],    # twitch, flinch, jolt
    },
    # Playful/teasing → lilting scoffs
    'playful': {
        'patterns': ['hah', 'pfft', 'cute', 'silly', 'dummy', 'baka', 'fiend', 'really', 'oh please'],
        'front_nls': [29, 25, 20],  # Pfft~, Tch, Baka!
        'back_nls': [44, 36, 7],    # snrk~, flutter, twitch
    },
    # Surrendering/melting → soft hums
    'melting': {
        'patterns': ['okay fine', 'i give', 'you win', 'yes', 'mmm', 'more', 'i surrender', 'fine you'],
        'front_nls': [28, 17, 16],  # Mmm~, Huuu~, Heeee~
        'back_nls': [8, 39, 5],     # melt, crumble, wilt
    },
    # Surprised/caught → sharp exclamations
    'surprised': {
        'patterns': ['what', 'huh', 'wha', 'eh', 'wait what', 'excuse', 'hold on', 'did you'],
        'front_nls': [11, 23, 24],  # Gah, OwO, Owo?
        'back_nls': [41, 40, 7],    # jolt, flinch, twitch
    },
}

def get_semantic_interjection(content: str, is_front: bool, intensity: float) -> Optional[int]:
    """
    Select an interjection based on the semantic content of the dialogue.
    Returns an NLS ID that matches the emotional tone of the content.
    
    This creates the "connective tissue" - sounds click with meaning:
    - "Whatever" → "Bah—" (mock annoyance)
    - "...okay" → "Nnn—" (hesitant)
    - "Shut up!" → "Tch—" (sharp resistance)
    """
    content_lower = content.lower().strip()
    
    # Score each category based on pattern matches
    category_scores = {}
    for category, data in CONTENT_INTERJECTION_MAP.items():
        score = 0
        for pattern in data['patterns']:
            if pattern in content_lower:
                score += 1
                # Bonus for start/end match (stronger signal)
                if content_lower.startswith(pattern) or content_lower.endswith(pattern):
                    score += 1
        if score > 0:
            category_scores[category] = score
    
    if not category_scores:
        return None  # No semantic match, fall back to random
    
    # Get the best matching category
    best_category = max(category_scores, key=category_scores.get)
    data = CONTENT_INTERJECTION_MAP[best_category]
    
    # Select from appropriate NLS list
    options = data['front_nls'] if is_front else data['back_nls']
    
    # Filter by intensity (but be lenient - semantic match trumps intensity)
    intensity_valid = get_valid_nls_for_intensity(intensity, is_front=is_front)
    valid_options = [nls_id for nls_id in options if nls_id in intensity_valid]
    
    if valid_options:
        return random.choice(valid_options)
    elif options:
        return options[0]  # Use first (best) match even if intensity doesn't align
    
    return None


def format_leak(nls_id: int, is_front: bool = True) -> str:
    """Format a leak for display"""
    nls = get_nls(nls_id)
    if not nls:
        return ""
    
    text = nls.text
    
    # Sounds get displayed directly
    if nls.is_sound:
        return text
    
    # Descriptors get formatted as action/state
    if is_front:
        # Front descriptors rarely used, but format as state
        return f"...{text}"
    else:
        # Back descriptors show the reaction
        return f"*{text}*"

def format_leaked_line(
    speaker: str,
    line: str,
    front_leak_id: Optional[int] = None,
    back_leak_id: Optional[int] = None
) -> List[Tuple[str, str]]:
    """
    Format a dialogue line with leaks injected.
    Returns list of (speaker, text) tuples.
    """
    result = []
    
    # Front leak
    if front_leak_id:
        front_text = format_leak(front_leak_id, is_front=True)
        if front_text:
            result.append((speaker, front_text))
    
    # Main line
    result.append((speaker, line))
    
    # Back leak
    if back_leak_id:
        back_text = format_leak(back_leak_id, is_front=False)
        if back_text:
            result.append((speaker, back_text))
    
    return result

# ═══════════════════════════════════════════════════════════════════════════════
#                    MAIN LEAKAGE ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class ReactionLeakageEngine:
    """
    Injects canon NLS reactions between dialogue lines to transform meaning.
    
    NOW WITH FEEDBACK LOOP:
    - Leaks push Birdsong toward emotional states
    - Leaks suggest optimal Fiend responses
    - Momentum accumulates to trigger state transitions
    
    Usage:
        engine = ReactionLeakageEngine()
        
        # Process a line with potential leakage
        leaked_lines = engine.process_line(
            speaker="BIRDSONG",
            line="you can't just SAY that—",
            state="flustered",
            intensity=0.6
        )
        
        # Check feedback after processing
        dominant_state = engine.get_dominant_state()
        suggested_gambit = engine.get_suggested_fiend_gambit()
        should_transition = engine.should_force_transition()
    """
    
    def __init__(self):
        self.birdsong_state = LeakageState(intensity=0.3)
        self.fiend_state = LeakageState(intensity=0.2)
    
    def process_line(
        self,
        speaker: str,
        line: str,
        state: str = "rambling",
        intensity: Optional[float] = None,
        force_leak: bool = False
    ) -> List[Tuple[str, str]]:
        """
        Process a dialogue line, potentially adding leaks.
        
        DECOUPLED LEAKS: Front and back are INDEPENDENT
        - Front leak (interjection): 65% chance
        - Back leak (reaction): 70% chance
        - Sometimes both, sometimes one, sometimes neither
        - This creates natural variety in how dialogue feels
        
        CASCADE: Each leak pushes state_weights for future selections
        """
        is_birdsong = speaker.upper() == "BIRDSONG"
        leakage = self.birdsong_state if is_birdsong else self.fiend_state
        
        current_intensity = intensity if intensity is not None else leakage.intensity
        
        # Get CASCADE state
        cascade_state = leakage.get_dominant_state()
        effective_state = cascade_state if cascade_state != "rambling" else state
        
        # Fiend leaks much less
        if not is_birdsong:
            if current_intensity < 0.8 and not force_leak:
                return [(speaker, line)]
            # Fiend only gets occasional back leaks at high intensity
            if force_leak or (current_intensity > 0.85 and random.random() < 0.25):
                back_leak_id = select_back_leak(None, current_intensity, leakage) if random.random() < 0.4 else None
                if back_leak_id:
                    leakage.record_leak(None, back_leak_id)
                    return format_leaked_line(speaker, line, None, back_leak_id)
            return [(speaker, line)]
        
        # BIRDSONG: Independent front and back leak decisions
        front_leak_id = None
        back_leak_id = None
        
        # FRONT LEAK: 65% chance (or forced)
        if force_leak or leakage.should_leak_front():
            # Try semantic match first
            front_leak_id = get_semantic_interjection(line, is_front=True, intensity=current_intensity)
            # Fall back to cascade-aware selection
            if front_leak_id is None:
                front_leak_id = select_front_leak(effective_state, current_intensity, leakage)
        
        # BACK LEAK: 70% chance (independent of front!)
        if force_leak or leakage.should_leak_back():
            # Try semantic match first
            back_leak_id = get_semantic_interjection(line, is_front=False, intensity=current_intensity)
            # Fall back to selection (cascade-aware, front-compatible if we have front)
            if back_leak_id is None:
                if front_leak_id:
                    back_leak_id = select_back_leak(front_leak_id, current_intensity, leakage)
                else:
                    # No front leak, pick any appropriate back leak
                    intensity_valid = get_valid_nls_for_intensity(current_intensity, is_front=False)
                    if intensity_valid:
                        # Prefer cascade-aligned
                        dominant = leakage.get_dominant_state()
                        preferred = [nls_id for nls_id in intensity_valid 
                                    if nls_id in LEAK_STATE_PUSH and LEAK_STATE_PUSH[nls_id][0] == dominant]
                        if preferred:
                            back_leak_id = random.choice(preferred)
                        else:
                            back_leak_id = random.choice(intensity_valid)
        
        # Record whatever we got (triggers cascade)
        leakage.record_leak(front_leak_id, back_leak_id)
        
        return format_leaked_line(speaker, line, front_leak_id, back_leak_id)
    
    # ═══════════════════════════════════════════════════════════════════════════
    #                    FEEDBACK LOOP API
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_dominant_state(self, speaker: str = "BIRDSONG") -> str:
        """Get the current dominant emotional state after leak processing"""
        leakage = self.birdsong_state if speaker.upper() == "BIRDSONG" else self.fiend_state
        return leakage.get_dominant_state()
    
    def get_state_weights(self, speaker: str = "BIRDSONG") -> Dict[str, float]:
        """Get full state weight distribution"""
        leakage = self.birdsong_state if speaker.upper() == "BIRDSONG" else self.fiend_state
        return leakage.state_weights.copy()
    
    def get_suggested_fiend_gambit(self) -> Optional[Tuple[FiendGambit, float]]:
        """Get the optimal Fiend response based on recent Birdsong leaks"""
        return self.birdsong_state.get_suggested_fiend_gambit()
    
    def should_force_transition(self, speaker: str = "BIRDSONG") -> bool:
        """Check if momentum is high enough to force a state transition"""
        leakage = self.birdsong_state if speaker.upper() == "BIRDSONG" else self.fiend_state
        return leakage.should_transition()
    
    def get_momentum(self, speaker: str = "BIRDSONG") -> float:
        """Get current leak momentum"""
        leakage = self.birdsong_state if speaker.upper() == "BIRDSONG" else self.fiend_state
        return leakage.leak_momentum
    
    def consume_momentum(self, speaker: str = "BIRDSONG", amount: float = 0.2):
        """Consume momentum after acting on a transition"""
        leakage = self.birdsong_state if speaker.upper() == "BIRDSONG" else self.fiend_state
        leakage.consume_momentum(amount)
    
    def apply_external_push(self, speaker: str, state: str, weight: float):
        """Manually push toward a state (for external escalation events)"""
        leakage = self.birdsong_state if speaker.upper() == "BIRDSONG" else self.fiend_state
        leakage._apply_state_push(state, weight)
    
    # ═══════════════════════════════════════════════════════════════════════════
    #                    EXISTING API (preserved)
    # ═══════════════════════════════════════════════════════════════════════════
    
    def escalate_intensity(self, speaker: str = "BIRDSONG", amount: float = 0.05):
        """Increase leakage intensity for a speaker"""
        if speaker.upper() == "BIRDSONG":
            self.birdsong_state.escalate(amount)
        else:
            self.fiend_state.escalate(amount)
    
    def cool_down(self, speaker: str = "BIRDSONG", amount: float = 0.03):
        """Decrease leakage intensity"""
        if speaker.upper() == "BIRDSONG":
            self.birdsong_state.cool_down(amount)
        else:
            self.fiend_state.cool_down(amount)
    
    def set_intensity(self, speaker: str, intensity: float):
        """Directly set intensity"""
        if speaker.upper() == "BIRDSONG":
            self.birdsong_state.intensity = max(0.0, min(1.0, intensity))
        else:
            self.fiend_state.intensity = max(0.0, min(1.0, intensity))
    
    def get_intensity(self, speaker: str = "BIRDSONG") -> float:
        """Get current intensity"""
        if speaker.upper() == "BIRDSONG":
            return self.birdsong_state.intensity
        return self.fiend_state.intensity

# ═══════════════════════════════════════════════════════════════════════════════
#                    UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_sounds() -> List[NLSElement]:
    """Get all NLS elements that are sounds (for injection between lines)"""
    return [nls for nls in ALL_NLS.values() if nls.is_sound]

def get_all_descriptors() -> List[NLSElement]:
    """Get all NLS elements that are descriptors (for action tags)"""
    return [nls for nls in ALL_NLS.values() if not nls.is_sound]

def get_nls_by_category(category: NLSCategory) -> List[NLSElement]:
    """Get all NLS elements in a category"""
    return [nls for nls in ALL_NLS.values() if nls.category == category]

def get_nls_in_intensity_range(min_intensity: float, max_intensity: float) -> List[NLSElement]:
    """Get NLS elements within an intensity range"""
    return [nls for nls in ALL_NLS.values() if min_intensity <= nls.intensity <= max_intensity]

# ═══════════════════════════════════════════════════════════════════════════════
#                    DEMO / TEST
# ═══════════════════════════════════════════════════════════════════════════════

def demo():
    """Demonstrate the leakage engine WITH FEEDBACK LOOP"""
    engine = ReactionLeakageEngine()
    
    print("═" * 70)
    print("           REACTION LEAKAGE ENGINE DEMO")
    print("           WITH ESCALATION FEEDBACK LOOP")
    print("═" * 70)
    print()
    
    # Simulate an exchange where leaks accumulate and push state
    print("─" * 70)
    print("SIMULATED EXCHANGE: Watching state evolve through leaks")
    print("─" * 70)
    print()
    
    exchange_lines = [
        ("BIRDSONG", "you think you're so clever, huh?", "bratty", 0.3),
        ("BIRDSONG", "I didn't ask for your opinion!", "bratty", 0.4),
        ("BIRDSONG", "w-wait, that's not—", "flustered", 0.5),
        ("BIRDSONG", "stop looking at me like that...", "flustered", 0.6),
        ("BIRDSONG", "I can't think when you—", "flustered", 0.7),
        ("BIRDSONG", "...please", "melting", 0.85),
    ]
    
    print(f"Initial state weights: {engine.get_state_weights()}")
    print(f"Initial dominant state: {engine.get_dominant_state()}")
    print()
    
    for speaker, line, state, intensity in exchange_lines:
        result = engine.process_line(speaker, line, state, intensity, force_leak=True)
        
        print(f"[{state}, {intensity:.0%}] ", end="")
        for s, t in result:
            if t.startswith("*") or t in [nls.text for nls in ALL_NLS.values() if nls.is_sound]:
                print(f"〈{t}〉 ", end="")
            else:
                print(f'"{t}" ', end="")
        print()
        
        # Show feedback effects
        print(f"  → Dominant: {engine.get_dominant_state()}")
        print(f"  → Momentum: {engine.get_momentum():.2f}")
        
        suggested = engine.get_suggested_fiend_gambit()
        if suggested:
            gambit, conf = suggested
            print(f"  → Fiend should: {gambit.value.upper()} (confidence: {conf:.2f})")
        
        if engine.should_force_transition():
            print(f"  ⚡ MOMENTUM THRESHOLD - Force state transition!")
            engine.consume_momentum()
        print()
    
    print("─" * 70)
    print("FINAL STATE ANALYSIS")
    print("─" * 70)
    print(f"Final state weights:")
    for state, weight in sorted(engine.get_state_weights().items(), key=lambda x: -x[1]):
        bar = "█" * int(weight * 30)
        print(f"  {state:12} {weight:.2f} {bar}")
    print()
    
    # Show same line with different states demonstrating transformation
    print("─" * 70)
    print("SEMANTIC TRANSFORMATION: Same line, different context")
    print("─" * 70)
    print()
    
    test_line = "don't tease me..."
    contexts = [
        ("bratty", 0.3),
        ("flustered", 0.5),
        ("melting", 0.7),
        ("needy", 0.9),
    ]
    
    for state, intensity in contexts:
        engine2 = ReactionLeakageEngine()  # Fresh engine
        result = engine2.process_line("BIRDSONG", test_line, state, intensity, force_leak=True)
        
        output = " ".join([f"〈{t}〉" if (t.startswith("*") or len(t) < 10) else f'"{t}"' for _, t in result])
        print(f"  [{state:10} {intensity:.0%}]: {output}")
    
    print()
    print("═" * 70)
    print("           CANON NLS SUMMARY")
    print("═" * 70)
    print(f"Total NLS Elements: {len(ALL_NLS)}")
    print(f"  Relational Markers (#1-10): {len(RELATIONAL_MARKERS)}")
    print(f"  Vocalized Fluster (#11-25): {len(VOCALIZED_FLUSTER)}")
    print(f"  Cute Disruptions (#26-35): {len(CUTE_DISRUPTIONS)}")
    print(f"  Emotional Cues (#36-45): {len(EMOTIONAL_CUES)}")
    print(f"  Physical Sync (#46-54): {len(PHYSICAL_SYNC)}")
    print()
    print("FEEDBACK LOOP:")
    print(f"  State Push mappings: {len(LEAK_STATE_PUSH)}")
    print(f"  Fiend Response mappings: {len(LEAK_FIEND_RESPONSE)}")
    print()

# ═══════════════════════════════════════════════════════════════════════════════
#                    ESCALATION FEEDBACK SYSTEM
#                    
#    Leaks aren't just dressing - they ALTER THE POSSIBILITY SPACE
#    Back leaks push toward states, accumulate momentum, affect Fiend responses
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
#                    LEAK → STATE PUSH WEIGHTS
# ═══════════════════════════════════════════════════════════════════════════════

# Each back leak pushes toward a state with a weight
# Format: NLS_ID → (target_state, push_weight)
LEAK_STATE_PUSH: Dict[int, Tuple[str, float]] = {
    # Relational markers
    4:  ("flustered", 0.08),   # bloom → flustered
    5:  ("quiet", 0.10),       # wilt → quiet
    6:  ("flustered", 0.05),   # pulse → flustered (subtle)
    7:  ("flustered", 0.04),   # twitch → flustered (tiny)
    8:  ("melting", 0.15),     # melt → melting (STRONG)
    9:  ("flustered", 0.06),   # tug → flustered
    10: ("bratty", 0.08),      # clench → bratty (resistance)
    
    # Emotional cues
    36: ("flustered", 0.06),   # flutter → flustered
    37: ("quiet", 0.05),       # waver → quiet
    38: ("needy", 0.12),       # shiver → needy (STRONG)
    39: ("bratty", 0.05),      # recoil → bratty (retreat to defense)
    40: ("melting", 0.12),     # crumble → melting (STRONG)
    41: ("quiet", 0.07),       # falter → quiet
    42: ("flustered", 0.08),   # spasm → flustered
    43: ("flustered", 0.06),   # jolt → flustered
    44: ("melting", 0.10),     # reverberate → melting
    45: ("needy", 0.09),       # ripple → needy
    
    # Physical sync
    48: ("melting", 0.10),     # tremor → melting
    49: ("needy", 0.08),       # squeeze → needy
    50: ("flustered", 0.07),   # squirm → flustered
    51: ("bratty", 0.05),      # grip → bratty (holding on)
    52: ("needy", 0.10),       # throb → needy (STRONG)
    53: ("flustered", 0.06),   # lurch → flustered
    54: ("flustered", 0.04),   # flinch → flustered (tiny)
    
    # Some sounds can also push (when used as back leaks)
    31: ("needy", 0.08),       # Mwehhh~ → needy (whining)
    34: ("needy", 0.10),       # Murrr~ → needy (shivering need)
}

# ═══════════════════════════════════════════════════════════════════════════════
#                    FIEND RESPONSE WEIGHTS
# ═══════════════════════════════════════════════════════════════════════════════

# When Birdsong leaks, what should Fiend do?
# Format: NLS_ID → {fiend_tool: weight_modifier}
# Positive = more likely, negative = less likely
# NOTE: This is the DETAILED version with multi-tool weights
#       The simpler LEAK_FIEND_RESPONSE above gives single gambit recommendations

class FiendTool(Enum):
    OBSERVE = "observe"
    COMMAND = "command"
    ESCALATE = "escalate"
    GROUND = "ground"
    TEASE = "tease"

LEAK_FIEND_TOOL_WEIGHTS: Dict[int, Dict[FiendTool, float]] = {
    # Strong vulnerability signals → SOFT responses
    8:  {FiendTool.ESCALATE: 0.3, FiendTool.GROUND: 0.2, FiendTool.TEASE: -0.2},   # melt
    34: {FiendTool.GROUND: 0.4, FiendTool.OBSERVE: 0.2, FiendTool.TEASE: -0.3},    # Murrr~
    38: {FiendTool.GROUND: 0.3, FiendTool.ESCALATE: 0.2, FiendTool.TEASE: -0.2},   # shiver
    48: {FiendTool.GROUND: 0.3, FiendTool.OBSERVE: 0.2},                            # tremor
    40: {FiendTool.COMMAND: 0.3, FiendTool.ESCALATE: 0.2},                          # crumble
    
    # Defensive signals → push through or anchor
    39: {FiendTool.GROUND: 0.3, FiendTool.OBSERVE: 0.2, FiendTool.ESCALATE: -0.2}, # recoil
    10: {FiendTool.OBSERVE: 0.2, FiendTool.GROUND: 0.2, FiendTool.ESCALATE: -0.1}, # clench
    51: {FiendTool.GROUND: 0.2, FiendTool.OBSERVE: 0.2},                            # grip
    
    # Deflection signals → TEASE through it
    26: {FiendTool.TEASE: 0.4, FiendTool.OBSERVE: 0.1, FiendTool.GROUND: -0.2},    # Baka!
    20: {FiendTool.TEASE: 0.3, FiendTool.OBSERVE: 0.2},                             # Pfft~
    21: {FiendTool.TEASE: 0.3, FiendTool.COMMAND: 0.1},                             # Tch
    32: {FiendTool.TEASE: 0.3, FiendTool.ESCALATE: 0.1},                            # Nyeh~
    
    # Responsive signals → capitalize
    36: {FiendTool.TEASE: 0.3, FiendTool.ESCALATE: 0.2},                            # flutter
    50: {FiendTool.TEASE: 0.2, FiendTool.COMMAND: 0.2},                             # squirm
    4:  {FiendTool.ESCALATE: 0.2, FiendTool.TEASE: 0.2},                            # bloom
    
    # Overwhelmed signals → let it land
    13: {FiendTool.OBSERVE: 0.4, FiendTool.GROUND: 0.2, FiendTool.TEASE: -0.3},    # Guh
    15: {FiendTool.OBSERVE: 0.3, FiendTool.GROUND: 0.2},                            # Hahhh
    17: {FiendTool.OBSERVE: 0.3, FiendTool.ESCALATE: 0.2},                          # Huuu~
    
    # Needy signals → can escalate or ground
    52: {FiendTool.ESCALATE: 0.3, FiendTool.COMMAND: 0.2},                          # throb
    45: {FiendTool.ESCALATE: 0.2, FiendTool.GROUND: 0.2},                           # ripple
    49: {FiendTool.GROUND: 0.3, FiendTool.ESCALATE: 0.2},                           # squeeze
    31: {FiendTool.GROUND: 0.2, FiendTool.TEASE: 0.2},                              # Mwehhh~
}

# ═══════════════════════════════════════════════════════════════════════════════
#                    ESCALATION STATE TRACKER
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class EscalationState:
    """
    Tracks how leaks affect the overall escalation.
    This is the FEEDBACK that makes leaks matter.
    """
    # State weights (how close to each state)
    state_weights: Dict[str, float] = field(default_factory=lambda: {
        "rambling": 0.3,
        "bratty": 0.2,
        "flustered": 0.2,
        "melting": 0.1,
        "needy": 0.1,
        "quiet": 0.1,
    })
    
    # Momentum accumulator
    leak_momentum: float = 0.0
    consecutive_high_intensity: int = 0
    total_leaks: int = 0
    
    # Fiend response modifiers (accumulated from leaks)
    fiend_tool_weights: Dict[str, float] = field(default_factory=lambda: {
        "observe": 0.0,
        "command": 0.0,
        "escalate": 0.0,
        "ground": 0.0,
        "tease": 0.0,
    })
    
    # Thresholds
    momentum_threshold: float = 0.3  # When to force state check
    state_transition_threshold: float = 0.4  # When state becomes dominant

    def apply_persona_bias(
        self,
        state_bias: Optional[Dict[str, float]] = None,
        fiend_tool_bias: Optional[Dict[str, float]] = None,
        momentum_threshold_mult: float = 1.0,
        state_transition_threshold_mult: float = 1.0,
    ):
        """Apply *base* persona biases before any leak accumulation.

        These are soft adjustments (weights + thresholds), designed to be safe.
        """

        # Bias state weights
        if state_bias:
            for state, delta in state_bias.items():
                self.state_weights[state] = max(0.0, self.state_weights.get(state, 0.0) + float(delta))
            self._normalize_weights()

        # Bias starting fiend weights
        if fiend_tool_bias:
            for tool, delta in fiend_tool_bias.items():
                self.fiend_tool_weights[tool] = self.fiend_tool_weights.get(tool, 0.0) + float(delta)

        # Bias thresholds (clamped to keep playable)
        def _clamp(x: float, lo: float, hi: float) -> float:
            return max(lo, min(hi, x))

        self.momentum_threshold = _clamp(self.momentum_threshold * float(momentum_threshold_mult), 0.15, 0.60)
        self.state_transition_threshold = _clamp(
            self.state_transition_threshold * float(state_transition_threshold_mult), 0.25, 0.75
        )
    
    def get_current_state(self) -> str:
        """Get the dominant state based on weights"""
        return max(self.state_weights.items(), key=lambda x: x[1])[0]
    
    def get_state_probability(self, state: str) -> float:
        """Get probability weight for a state"""
        total = sum(self.state_weights.values())
        if total == 0:
            return 0.0
        return self.state_weights.get(state, 0.0) / total
    
    def apply_leak_push(self, nls_id: int):
        """Apply the state push from a back leak"""
        if nls_id not in LEAK_STATE_PUSH:
            return
        
        target_state, push_weight = LEAK_STATE_PUSH[nls_id]
        
        # Push toward target state
        self.state_weights[target_state] = min(1.0, 
            self.state_weights.get(target_state, 0.0) + push_weight)
        
        # Slight decay on other states (zero-sum-ish)
        decay = push_weight * 0.3
        for state in self.state_weights:
            if state != target_state:
                self.state_weights[state] = max(0.0, 
                    self.state_weights[state] - decay / (len(self.state_weights) - 1))
        
        # Normalize to prevent runaway
        self._normalize_weights()
    
    def apply_fiend_response_modifier(self, nls_id: int):
        """Apply Fiend response weight modifiers from a leak"""
        if nls_id not in LEAK_FIEND_TOOL_WEIGHTS:
            return
        
        modifiers = LEAK_FIEND_TOOL_WEIGHTS[nls_id]
        for tool, weight in modifiers.items():
            tool_name = tool.value if isinstance(tool, FiendTool) else tool
            self.fiend_tool_weights[tool_name] = self.fiend_tool_weights.get(tool_name, 0.0) + weight
        
        # Decay old modifiers slightly
        for tool in self.fiend_tool_weights:
            self.fiend_tool_weights[tool] *= 0.9
    
    def accumulate_momentum(self, leak_intensity: float):
        """Accumulate momentum from a leak"""
        self.total_leaks += 1
        
        if leak_intensity > 0.6:
            self.leak_momentum += 0.05
            self.consecutive_high_intensity += 1
            
            # Bonus for consecutive high-intensity
            if self.consecutive_high_intensity > 2:
                self.leak_momentum += 0.03
        else:
            self.consecutive_high_intensity = 0
            # Slight decay when not leaking hard
            self.leak_momentum = max(0.0, self.leak_momentum - 0.02)
    
    def check_momentum_trigger(self) -> bool:
        """Check if momentum has crossed threshold"""
        return self.leak_momentum >= self.momentum_threshold
    
    def check_state_transition(self) -> Optional[str]:
        """Check if any state has become dominant enough to trigger transition"""
        for state, weight in self.state_weights.items():
            if weight >= self.state_transition_threshold:
                return state
        return None
    
    def get_fiend_tool_recommendation(self) -> Tuple[str, float]:
        """Get the recommended Fiend tool based on accumulated leak responses"""
        if not self.fiend_tool_weights:
            return ("observe", 0.0)
        
        best_tool = max(self.fiend_tool_weights.items(), key=lambda x: x[1])
        return best_tool
    
    def _normalize_weights(self):
        """Normalize state weights to sum to 1.0"""
        total = sum(self.state_weights.values())
        if total > 0:
            for state in self.state_weights:
                self.state_weights[state] /= total
    
    def reset_momentum(self):
        """Reset momentum after it's been consumed"""
        self.leak_momentum = 0.0
        self.consecutive_high_intensity = 0
    
    def decay_fiend_weights(self, amount: float = 0.1):
        """Decay Fiend response weights over time"""
        for tool in self.fiend_tool_weights:
            current = self.fiend_tool_weights[tool]
            if current > 0:
                self.fiend_tool_weights[tool] = max(0.0, current - amount)
            elif current < 0:
                self.fiend_tool_weights[tool] = min(0.0, current + amount)

# ═══════════════════════════════════════════════════════════════════════════════
#                    INTEGRATED LEAKAGE ENGINE (WITH FEEDBACK)
# ═══════════════════════════════════════════════════════════════════════════════

class IntegratedLeakageEngine(ReactionLeakageEngine):
    """
    Extended leakage engine that feeds back into escalation.
    
    Leaks now:
    1. Push toward states (melt → melting state)
    2. Accumulate momentum (consecutive leaks compound)
    3. Modify Fiend's optimal response
    4. Can trigger state transitions
    """
    
    def __init__(self):
        super().__init__()
        self.escalation = EscalationState()
        self._last_back_leak: Optional[int] = None
    
    def process_line_with_feedback(
        self,
        speaker: str,
        line: str,
        state: Optional[str] = None,
        intensity: Optional[float] = None,
        force_leak: bool = False
    ) -> Tuple[List[Tuple[str, str]], Dict]:
        """
        Process a line and return both the leaked dialogue AND escalation feedback.
        
        Returns:
            Tuple of:
            - List of (speaker, text) tuples
            - Dict with feedback data:
                - state_pushed: bool
                - new_dominant_state: Optional[str]
                - momentum_triggered: bool
                - fiend_recommendation: Tuple[str, float]
                - current_state_weights: Dict[str, float]
        """
        # Use escalation state if not provided
        if state is None:
            state = self.escalation.get_current_state()
        
        # Process the line normally
        result = self.process_line(speaker, line, state, intensity, force_leak)
        
        # Extract what leaked
        front_leak_id = None
        back_leak_id = None
        
        if len(result) > 1:
            # Find the leak IDs by matching text
            for s, text in result:
                if text != line:
                    # This is a leak
                    nls = get_nls_by_text(text.strip('*'))
                    if nls:
                        if result.index((s, text)) == 0:
                            front_leak_id = nls.id
                        else:
                            back_leak_id = nls.id
        
        # Apply feedback from back leak
        feedback = {
            "state_pushed": False,
            "new_dominant_state": None,
            "momentum_triggered": False,
            "fiend_recommendation": ("observe", 0.0),
            "current_state_weights": dict(self.escalation.state_weights),
            "leak_momentum": self.escalation.leak_momentum,
        }
        
        if back_leak_id:
            self._last_back_leak = back_leak_id
            
            # Apply state push
            old_state = self.escalation.get_current_state()
            self.escalation.apply_leak_push(back_leak_id)
            new_state = self.escalation.get_current_state()
            
            if new_state != old_state:
                feedback["state_pushed"] = True
                feedback["new_dominant_state"] = new_state
            
            # Apply Fiend response modifiers
            self.escalation.apply_fiend_response_modifier(back_leak_id)
            
            # Accumulate momentum
            nls = get_nls(back_leak_id)
            if nls:
                self.escalation.accumulate_momentum(nls.intensity)
            
            # Check triggers
            if self.escalation.check_momentum_trigger():
                feedback["momentum_triggered"] = True
            
            transition = self.escalation.check_state_transition()
            if transition:
                feedback["new_dominant_state"] = transition
            
            feedback["fiend_recommendation"] = self.escalation.get_fiend_tool_recommendation()
            feedback["current_state_weights"] = dict(self.escalation.state_weights)
            feedback["leak_momentum"] = self.escalation.leak_momentum
        
        return result, feedback
    
    def get_optimal_fiend_response(self) -> Tuple[str, float]:
        """Get the current optimal Fiend tool based on Birdsong's leaks"""
        return self.escalation.get_fiend_tool_recommendation()
    
    def get_current_birdsong_state(self) -> str:
        """Get current Birdsong state based on leak accumulation"""
        return self.escalation.get_current_state()
    
    def get_state_weights(self) -> Dict[str, float]:
        """Get all state weights"""
        return dict(self.escalation.state_weights)
    
    def get_momentum(self) -> float:
        """Get current leak momentum"""
        return self.escalation.leak_momentum
    
    def consume_momentum(self):
        """Consume momentum after using it (e.g., for state transition)"""
        self.escalation.reset_momentum()
    
    def force_state(self, state: str, weight: float = 0.5):
        """Force a state to become dominant (for external triggers)"""
        self.escalation.state_weights[state] = weight
        self.escalation._normalize_weights()

# ═══════════════════════════════════════════════════════════════════════════════
#                    DEMO WITH FEEDBACK
# ═══════════════════════════════════════════════════════════════════════════════

def demo_with_feedback():
    """Demonstrate the integrated leakage → escalation feedback loop"""
    engine = IntegratedLeakageEngine()
    
    print("═" * 70)
    print("       INTEGRATED LEAKAGE → ESCALATION FEEDBACK DEMO")
    print("═" * 70)
    print()
    
    # Simulate an exchange where leaks accumulate and shift state
    lines = [
        ("BIRDSONG", "I didn't say you could do that!", "bratty"),
        ("BIRDSONG", "stop looking at me like that...", "bratty"),
        ("BIRDSONG", "I-I'm not blushing!", "flustered"),
        ("BIRDSONG", "you're so annoying...", "flustered"),
        ("BIRDSONG", "wait... don't stop", "flustered"),
        ("BIRDSONG", "I... I can't...", "melting"),
    ]
    
    print("Initial state weights:")
    for state, weight in engine.get_state_weights().items():
        bar = "█" * int(weight * 20)
        print(f"  {state:12} {weight:.2f} {bar}")
    print()
    
    for i, (speaker, line, intended_state) in enumerate(lines):
        print(f"─── Line {i+1} (intended: {intended_state}) ───")
        
        # Process with feedback
        result, feedback = engine.process_line_with_feedback(
            speaker, line, 
            intensity=0.3 + (i * 0.12),  # Escalating intensity
            force_leak=True
        )
        
        # Show dialogue
        for s, t in result:
            print(f"  [{s}] {t}")
        
        # Show feedback
        actual_state = engine.get_current_birdsong_state()
        print(f"  → Actual state: {actual_state}")
        print(f"  → Momentum: {feedback['leak_momentum']:.2f}")
        
        if feedback['state_pushed']:
            print(f"  → STATE SHIFTED to {feedback['new_dominant_state']}!")
        
        if feedback['momentum_triggered']:
            print(f"  → ⚡ MOMENTUM THRESHOLD CROSSED!")
        
        tool, weight = feedback['fiend_recommendation']
        if weight > 0.1:
            print(f"  → Fiend should: {tool.upper()} (weight: {weight:.2f})")
        
        print()
    
    print("═" * 70)
    print("Final state weights:")
    for state, weight in engine.get_state_weights().items():
        bar = "█" * int(weight * 20)
        print(f"  {state:12} {weight:.2f} {bar}")
    
    print()
    print(f"Total momentum: {engine.get_momentum():.2f}")
    tool, weight = engine.get_optimal_fiend_response()
    print(f"Optimal Fiend response: {tool.upper()} (weight: {weight:.2f})")
    print("═" * 70)

if __name__ == "__main__":
    demo()
    print("\n" * 2)
    demo_with_feedback()