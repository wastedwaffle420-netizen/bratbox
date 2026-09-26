#!/usr/bin/env python3
"""Bratbox receipt: write session receipts to the world store.

Called from the game at SESSION COMPLETE. Appends a receipt event and
updates state (needs, last_bratbox, mood, open threads).

Also provides pre-session briefing: load state + today's events +
yesterday's diary for the writer's context.
"""
import sys
from pathlib import Path

# World store lives in the jasmine-companion-build goal
WORLD = Path.home() / "workspace/goals/jasmine-companion-build/files/jasmine/world"
sys.path.insert(0, str(WORLD))

try:
    from store import (
        load_state, save_state, append_event,
        adjust_needs, today_events, yesterday_diary,
        open_thread, push_topic,
    )
    _HAS_WORLD = True
except Exception as e:
    print(f"[receipt] world store unavailable: {e}")
    _HAS_WORLD = False


def write_receipt(stats):
    """Write a session receipt from the game's stats dict."""
    if not _HAS_WORLD:
        return
    try:
        state = load_state()

        duration = float(stats.get("session_minutes", 0) or 0)
        accuracy = float(stats.get("accuracy", 0) or 0)
        max_combo = int(stats.get("max_combo", 0) or 0)

        # Derive the peak moment and mood from stats
        if accuracy >= 0.95:
            peak = f"flawless run, {max_combo} max combo — she took control"
            mood = "glowing, wrecked, smug"
        elif accuracy >= 0.85:
            peak = f"strong session, {max_combo} combo peak"
            mood = "pleased, warm, a little smug"
        elif accuracy >= 0.70:
            peak = "steady rhythm, she stayed with him"
            mood = "content, tired"
        else:
            peak = "rough session, but he stayed"
            mood = "tender, tired"

        end_state = "Soft_Glow_Anchor aftercare"

        receipt = append_event(
            "bratbox", "session_receipt",
            duration_min=round(duration, 1),
            peak=peak,
            end_state=end_state,
            mood=mood,
            accuracy=round(accuracy, 3),
            max_combo=max_combo,
            mood_delta={"horniness": -35, "energy": -20},
        )

        # Update state
        adjust_needs(state, {"horniness": -35, "energy": -20})
        state["mood"] = mood
        state["last_bratbox"] = receipt["ts"]
        state["attention_level"] = 10  # bratbox = maximum attention
        push_topic(state, "tonight's bratbox session", heat=9)

        save_state(state)
        print(f"[receipt] session logged: {duration:.1f}min, {mood}")
    except Exception as e:
        print(f"[receipt] failed: {e}")


def get_briefing():
    """Pre-session briefing: state + today's events + yesterday's diary."""
    if not _HAS_WORLD:
        return "world store unavailable"
    try:
        state = load_state()
        events = today_events()
        diary = yesterday_diary()

        lines = ["=== PRE-SESSION BRIEFING ===", ""]
        lines.append(f"mood: {state.get('mood', '?')}")
        lines.append(f"needs: {state.get('needs', {})}")
        lines.append("")

        topics = state.get("topics", [])
        if topics:
            lines.append("hot topics:")
            for t in sorted(topics, key=lambda x: -x.get("heat", 0))[:5]:
                lines.append(f"  - {t['text']} (heat {t['heat']})")
            lines.append("")

        threads = state.get("open_threads", [])
        if threads:
            lines.append("open threads:")
            for th in threads:
                lines.append(f"  - {th['text']}")
            lines.append("")

        inv = state.get("inventory", [])
        if inv:
            lines.append(f"closet: {', '.join(inv[-5:])}")
            lines.append("")

        if diary:
            lines.append("--- yesterday's diary ---")
            lines.append(diary[:1500])
            lines.append("")

        if events:
            lines.append(f"--- today's events ({len(events)}) ---")
            for e in events[-10:]:
                lines.append(f"  [{e.get('source')}] {e.get('event', e.get('type', ''))[:80]}")

        return "\n".join(lines)
    except Exception as e:
        return f"briefing failed: {e}"
