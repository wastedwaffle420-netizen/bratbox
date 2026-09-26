"""Release achievement registry for Way of the Wind.

Achievements are singular discoveries and cross-system consequences.  Ordinary
time, quantity, upgrade and battle counters remain progression, never trophies.
The save keeps only unlocked receipts and a small recent-event ring.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping

SCHEMA = 1


def _spec(aid: str, title: str, event: str, description: str, *,
          hidden: bool = True, requires: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    return {
        "id": aid, "title": title, "event": event, "description": description,
        "hidden": bool(hidden), "requires": dict(requires or {}),
    }


CATALOG: List[Dict[str, Any]] = [
    _spec("the_sound_was_enough", "The Sound Was Enough", "voice_brain_exchange",
          "One performed cue changes the adult duet's next answer without needing a menu.",
          requires={"adult_mutual_context": True, "connected_exchange": True}),
    _spec("quite_thoroughly_encouraged", "Quite Thoroughly Encouraged", "voice_brain_exchange",
          "Let coy permission become an accepted escalation between two attentive creatures.",
          requires={"coy_permission_heard": True, "accepted_escalation": True}),
    _spec("an_excellent_listener", "An Excellent Listener", "voice_brain_exchange",
          "Hear her ask for room, honor it, and remain present for what she asks next.",
          requires={"honored_back_down": True, "direct_permission_heard": True}),
    _spec("courtesy_eventually", "Courtesy, Eventually", "voice_brain_exchange",
          "Carry both restraint and invitation through one connected adult performance.",
          requires={"honored_back_down": True, "accepted_escalation": True}),
    _spec("birdsong_eruption", "Birdsong Eruption", "voice_brain_exchange",
          "Let articulated direction crack into a pleased animal answer without losing the thread.",
          requires={"birdsong_eruption": True, "answered_birdsong": True}),
    _spec("he_cannot_disobey_that_noise", "He Cannot Disobey That Noise", "voice_brain_exchange",
          "Make one impossible little sound and receive a connected answer.",
          requires={"birdsong_eruption": True, "connected_exchange": True}),
    _spec("no_again_there_you_go", "No. Again. There You Go.", "voice_brain_exchange",
          "Correct the pace, then deliberately reopen it in the same adult conversation.",
          requires={"honored_back_down": True, "direct_permission_heard": True, "accepted_escalation": True}),
    _spec("both_creatures_talking", "Both Creatures Talking", "voice_brain_exchange",
          "Hear a complete two-voice exchange instead of a row of unrelated recordings.",
          hidden=False, requires={"both_creatures_talking": True, "connected_exchange": True}),
    _spec("wrong_hole_is_all_he_gets", "Wrong Hole Is All He Gets", "black_wind_finale",
          "Hold the adult Black Wind finale perfectly from warning to receipt.",
          requires={"outcome": "wrong_hole_success", "misses": 0}),
    _spec("a_technical_victory", "A Technical Victory", "black_wind_finale",
          "Return from a flawless nonreproductive rescue to an adult spouse.",
          requires={"outcome": "wrong_hole_success", "adult_spouse_present": True}),
    _spec("spillage_is_a_legal_theory", "Spillage Is a Legal Theory", "black_wind_finale",
          "Begin in the wrong place and finish with an authored lineage redirect.",
          requires={"outcome": "intended_reproductive_redirect"}),
    _spec("three_minutes_of_bad_advice", "Three Minutes of Bad Advice", "black_wind_finale",
          "Let an uncertain Ogre performer reach the correct mistake.",
          requires={"outcome": "wrong_hole_success", "ai_outcome": "uncertain"}),
    _spec("he_was_trying_to_help", "He Was Trying to Help", "black_wind_finale",
          "Allow a reckless performer to correct the finale reproductively.",
          requires={"outcome": "intended_reproductive_redirect", "ai_outcome": "reckless"}),
    _spec("fill_complete", "Fill Complete", "black_wind_finale",
          "Let the complete authored redirect and its consequence finish.",
          requires={"outcome": "intended_reproductive_redirect", "visual_complete": True}),
    _spec("the_wrong_answer_perfectly_executed", "The Wrong Answer, Perfectly Executed",
          "black_wind_finale", "Finish the alternate route without one timing fault.",
          requires={"outcome": "wrong_hole_success", "accuracy": 1.0}),
    _spec("an_heir_to_a_misunderstanding", "An Heir to a Misunderstanding", "black_wind_finale",
          "Let an interrupted wrong-hole hold become canonical lineage.",
          requires={"outcome": "intended_reproductive_redirect", "lineage_produced": True}),
    _spec("we_will_call_that_a_rescue", "We’ll Call That a Rescue", "black_wind_finale",
          "Recover Hana with the household tree exactly as crowded as before.",
          requires={"outcome": "wrong_hole_success", "hana_recovered": True}),
    _spec("the_nursery_disagrees", "The Nursery Disagrees", "black_wind_finale",
          "Finish a declared loss and discover that the nursery has minutes.",
          requires={"outcome": "intended_reproductive_redirect", "story_birth": True}),
    _spec("his_intentions_were_good_truly", "His Intentions Were Good, Truly",
          "black_wind_finale", "Maintain the reproductive correction long enough to prove intent.",
          requires={"outcome": "intended_reproductive_redirect", "repro_confirmed": True}),

    _spec("assigned_quarters_assigned_doom", "Assigned Quarters, Assigned Doom", "person_aftermath",
          "Give a generated adult recruit a real room and an immediate canonical casualty.",
          requires={"generated_recruit": True, "room_assigned": True, "first_deployment_casualty": True}),
    _spec("the_barracks_knows_your_name", "The Barracks Knows Your Name", "terminal_reconciliation",
          "Find one changed soldier identically represented by War and People.",
          requires={"same_person": True, "state_equal": True}),
    _spec("one_person_two_clipboards", "One Person, Two Clipboards", "terminal_reconciliation",
          "Carry Sake, armor, Katana and mastery through both terminal doors.",
          requires={"all_training_equal": True}),
    _spec("one_cup_before_the_funeral", "One Cup Before the Funeral", "person_aftermath",
          "Let Sake training become the last polite entry before loss.",
          requires={"sake_last_event": True, "terminal_or_missing": True}),
    _spec("armor_has_one_joke", "Armor Has One Joke", "combat_aftermath",
          "Have armor prevent the ending and then become one itself.",
          requires={"armor_saved_owner": True, "armor_broke": True}),
    _spec("the_room_is_still_his", "The Room Is Still His", "people_room_opened",
          "Visit the room of someone missing but not declared dead.",
          requires={"occupant_missing": True, "occupant_dead": False, "room_present": True}),
    _spec("please_stop_recruiting_strangers", "Please Stop Recruiting Strangers", "person_recruited",
          "Generate a recruit who already belongs to someone else’s story.",
          requires={"generated": True, "existing_relationship": True}),
    _spec("the_volunteer_had_a_mother", "The Volunteer Had a Mother", "person_aftermath",
          "Let a new volunteer acquire family meaning before battle.",
          requires={"generated_recruit": True, "family_event_before_deployment": True}),
    _spec("returned_with_different_manners", "Returned With Different Manners", "person_recovered",
          "Recover a trained captive whose instruction survived but whose allegiance did not.",
          requires={"training_preserved": True, "allegiance_changed": True}),
    _spec("the_memorial_is_premature", "The Memorial Is Premature", "person_recovered",
          "Recover someone after absence became ceremony but before it became death.",
          requires={"was_memorialized_missing": True, "alive": True}),
    _spec("administrative_necromancy", "Administrative Necromancy", "people_audit",
          "Repair contradictory records and return one living name to the city.",
          requires={"contradiction_repaired": True, "living_person_restored": True}),
    _spec("nobody_was_expendable", "Nobody Was Expendable", "combat_aftermath",
          "Return from battle using only the real named people who left.",
          requires={"named_only": True, "generated_replacements": 0, "all_returned": True}),
    _spec("someone_had_to_get_the_room", "Someone Had to Get the Room", "person_recruited",
          "Turn a necessary generated soldier into a housed canonical person.",
          hidden=False, requires={"generated": True, "room_assigned": True}),

    _spec("a_family_matter_unfortunately", "A Family Matter, Unfortunately", "lineage_aftermath",
          "Make one consequence agree across People, lineage and the map.",
          requires={"people_synced": True, "lineage_synced": True, "world_synced": True}),
    _spec("the_child_inherited_the_footnote", "The Child Inherited the Footnote", "lineage_aftermath",
          "Pass a parental embarrassment into an otherwise respectable inheritance.",
          requires={"inherited_humiliation_trait": True}),
    _spec("father_unknown_everyone_else_certain", "Father Unknown, Everyone Else Certain",
          "lineage_aftermath", "Record social and biological parentage without making either disappear.",
          requires={"social_parent_differs": True}),
    _spec("nobody_wake_the_husband", "Nobody Wake the Husband", "idle_aftermath",
          "Resolve an autonomous adult household consequence before strategic time resumes.",
          requires={"adult_spouse_present": True, "cuckold_consequence": True, "no_year_advance": True}),
    _spec("idle_hands_busy_household", "Idle Hands, Busy Household", "idle_aftermath",
          "Return to one wrong-hole fill and one new nursing-room consequence.",
          requires={"wrong_hole_fill": True, "nursing_room_growth": True}),
    _spec("the_family_tree_bent_first", "The Family Tree Bent First", "lineage_aftermath",
          "Create a lawful relationship the ordinary family label cannot say gracefully.",
          requires={"relationship_label_fallback": True}),
    _spec("a_nursery_with_no_victory_music", "A Nursery With No Victory Music", "lineage_aftermath",
          "Receive a canonical birth from a route recorded as defeat.",
          requires={"birth": True, "route_success": False}),
    _spec("the_rescuer_needed_a_moment", "The Rescuer Needed a Moment", "person_recovered",
          "Recover an adult partner after captivity has already opened lineage.",
          requires={"partner": True, "lineage_opened_before_rescue": True}),
    _spec("the_room_was_prepared_in_advance", "The Room Was Prepared in Advance", "lineage_aftermath",
          "Let a named arrival discover that housing preceded biology.",
          requires={"birth": True, "room_preassigned": True}),
    _spec("inherited_bad_timing", "Inherited Bad Timing", "lineage_aftermath",
          "Make lineage canonical on a year boundary without stopping play.",
          requires={"birth": True, "year_boundary": True, "no_freeze": True}),

    _spec("a_small_gods_honest_mistake", "A Small God’s Honest Mistake", "animist_aftermath",
          "Accept sincere supernatural help with an undignified second clause.",
          requires={"benefit": True, "humiliation": True}),
    _spec("the_shrine_was_trying_to_help", "The Shrine Was Trying to Help", "animist_aftermath",
          "Receive a useful shrine answer whose presentation solves nothing socially.",
          requires={"shrine": True, "benefit": True, "humiliation": True}),
    _spec("please_chew_responsibly", "Please Chew Responsibly", "container_aftermath",
          "Return a named adult from a restrained appetite with identity intact.",
          requires={"vore_route": True, "survived": True, "identity_preserved": True}),
    _spec("the_meal_filed_a_complaint", "The Meal Filed a Complaint", "container_aftermath",
          "House a person whom digestion had prematurely classified as scenery.",
          requires={"vore_route": True, "survived": True, "room_assigned": True}),
    _spec("indigestion_has_a_name", "Indigestion Has a Name", "container_aftermath",
          "Track a captive inside one specific living container.",
          requires={"named_captive": True, "specific_gulk": True}),
    _spec("unfinished_lunch", "Unfinished Lunch", "person_recovered",
          "Intervene between swallowing and irreversible digestion.",
          requires={"rescued_from_gulk": True, "digestion_irreversible": False}),
    _spec("the_pot_kept_records", "The Pot Kept Records", "person_recovered",
          "Recover a pot- or sewer-held person with relationships intact.",
          requires={"pot_or_sewer": True, "identity_preserved": True}),
    _spec("the_container_became_a_witness", "The Container Became a Witness", "container_aftermath",
          "Carry one canonical identity through two different custody systems.",
          requires={"container_count": 2, "identity_preserved": True}),
    _spec("the_appetite_was_political", "The Appetite Was Political", "container_aftermath",
          "Let appetite alter control, diplomacy, ransom or succession.",
          requires={"political_consequence": True}),
]

BY_ID = {entry["id"]: entry for entry in CATALOG}


def _matches(payload: Mapping[str, Any], requirements: Mapping[str, Any]) -> bool:
    for key, expected in requirements.items():
        actual = payload.get(key)
        if isinstance(expected, float):
            try:
                if abs(float(actual) - expected) > 1e-9:
                    return False
            except Exception:
                return False
        elif actual != expected:
            return False
    return True


def normalize_state(raw: Any = None) -> Dict[str, Any]:
    data = dict(raw or {}) if isinstance(raw, dict) else {}
    unlocked = data.get("unlocked", {})
    recent = data.get("recent_events", [])
    witnesses = data.get("witnesses", {})
    return {
        "schema": SCHEMA,
        "unlocked": dict(unlocked) if isinstance(unlocked, dict) else {},
        "recent_events": list(recent)[-24:] if isinstance(recent, list) else [],
        # Only meaningful named identities receive witnesses. This is transition
        # evidence, not a second People database, and remains strictly bounded.
        "witnesses": dict(list(witnesses.items())[-256:]) if isinstance(witnesses, dict) else {},
    }


def record_event(raw_state: Any, event: str, payload: Mapping[str, Any] | None = None,
                 *, year: int = 0) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    state = normalize_state(raw_state)
    body = dict(payload or {})
    event = str(event or "").strip()
    unlocked = state["unlocked"]
    new: List[Dict[str, Any]] = []
    state["recent_events"].append({"event": event, "year": int(year or 0), "payload": body})
    state["recent_events"] = state["recent_events"][-24:]
    for spec in CATALOG:
        aid = spec["id"]
        if aid in unlocked or spec["event"] != event:
            continue
        if not _matches(body, spec.get("requires", {})):
            continue
        receipt = {
            "id": aid, "title": spec["title"], "year": int(year or 0),
            "event": event, "payload": body,
        }
        unlocked[aid] = receipt
        new.append(receipt)
    return state, new


def display_rows(raw_state: Any, *, reveal_locked: bool = False) -> Iterable[Dict[str, Any]]:
    state = normalize_state(raw_state)
    unlocked = state["unlocked"]
    for spec in CATALOG:
        done = spec["id"] in unlocked
        hidden = bool(spec.get("hidden", True))
        yield {
            **spec,
            "done": done,
            "title": spec["title"] if done or reveal_locked or not hidden else "???",
            "description": spec["description"] if done or reveal_locked or not hidden else "A peculiar condition remains unmet.",
        }
