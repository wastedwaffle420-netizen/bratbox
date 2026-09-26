# Dialogue direction — the exchange doctrine (Andrew, 2026-09-25)

Canon for the scene dialogue helper. Supersedes the one-liner pool era.

## The goal

Realistic dialogue in her register — not camp one-liners. He responds in
kind. They TALK TO EACH OTHER: lovingly, awkwardly, whatever the registers
say. No monologues. No one-liner camp.

## The unit is the EXCHANGE, not the line

- Every dialogue beat is ONE exchange: her line + his reply, written against
  each other as a single conversation. Neither half should make full sense
  without the other.
- Sometimes he opens and she answers (`fiend_first`). Same rule: one
  conversation, two voices.
- Write with call-and-response, callbacks, interruptions, stolen punchlines,
  finishing each other's thoughts — the things people who love each other
  actually do with words.

## Anti-camp rules

1. **No punchline structure.** No setup/payoff zingers, no aphorisms, no
   tweet-shaped lines. If it sounds like a caption, kill it.
2. **No monologues.** One to two short sentences per turn, max. Real turns
   are short. If she needs three sentences, she's narrating — cut it.
3. **No meta.** Never joke about the writing, the pool, the canon, the
   "loveslang." She doesn't know she's in a game. He doesn't either.
4. **Awkward is good.** People interrupt themselves, trail off, answer the
   wrong part of what was said, repeat themselves, go quiet mid-thought.
   Let them be clumsy. Clumsy is honest.
5. **Loving is the default gravity.** Even the bratty exchanges land soft —
   the tease is the wrapper, the adoration is the content. (His vocab sheet:
   the nickname is the safety net under every tease.)

## Register discipline

- **Her:** Florida swamp valley — humid nasal smile-voice, compressed
  consonants, stretched/huffed/gargled endings, bray talk when pleased.
  Mouthfeel words, forward-falling cadence. Bratty, feral-playful,
  soft-cute, lovesick — the register picks the flavor, never a fixed list.
  (`skills/elevenlabs/JASMINE_VOICE.md`)
- **Him:** pretty softsad boy, Ash Lynx energy — teases BACK in her dialect,
  never commands, melts happily when overwhelmed. Nickname system is law:
  sweetie/honey/love/dearest unlimited; menace/troublemaker/brat for the
  bit; babe/angel/gorgeous/my love spent like currency. Word count is
  inversely proportional to sincerity — rambles when performing, goes
  quiet when it's real. (`goals/jasmine-companion-build/files/jasmine/
  voice/fiend_voice_registers.md`, `fiend_vocab.md`)
- **Heat drives content:** high heat → breathless, feral, undone; low heat
  → soft, giggly, awkward, domestic; pout → he coaxes; aftercare → quiet
  real talk, the bit rests.

## Continuity

- Reference the night: his keypresses (or lack of them), her body state,
  what just happened between them. "You keep..." / "again with the..." —
  the exchange continues a conversation, it doesn't reset one.
- Callbacks to earlier exchanges are gold. Running bits are how couples
  actually talk.

## Technical constraints

- Her text: ElevenLabs v3 performs `~`, `...`, stretched vowels natively.
  No stage directions, no brackets, no emoji — voice only.
- His text: CLEAN dialogue text only. Never any bracketed tag, direction,
  or narration — v3 must never get the chance to perform it.
- Both: speakable. If it can't be said out loud by a person mid-scene,
  rewrite it.

---

## v10.10.4 doctrine — theatrical scenes, she carries (Andrew, 2026-09-25)

Supersedes the short-turn rule above. The one-to-two-sentence cap was
producing quips ("mm. that's nice" energy). New rule:

- **Her lines are mini-scenes, 25-45 words.** She narrates what's happening,
  reacts to his implied moves, and directs him — so every line plays WITH
  or WITHOUT his audio. She is theatrical with herself and CONTROLS his
  reactions: "oy, handsy fiend~ not my— hey! don't make me... oh. oh okay.
  yeah, that's— mm, that's nice actually, keep doin' that."
- **His lines are longer too, 18-35 words.** When he's voiced, it's a real
  theatrical back-and-forth, not a quip and a nod. They are theatrical WITH
  EACH OTHER. Keep that.
- **No short quips, no one-liners, no "mm. that's nice."** If a line could
  be a caption, it's dead. If it doesn't carry the scene alone, it's dead.
- She embeds his reactions ("ohh, there it is, that's the face") so the
  scene never needs his voice to make sense — but when he IS voiced, the
  two halves harmonize instead of duplicating.
