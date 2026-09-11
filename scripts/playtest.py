#!/usr/bin/env python3
"""
End-to-end playtest — the §12 Tier-3 gate, made runnable.

Plays several real turns against the live game and CHECKS THE MECHANISMS, rather
than eyeballing prose. Every check asserts on observable end state: HP actually
changed, a die was actually rolled, the save file actually contains equipment.

    ./scripts/playtest.py                 # 6 turns, all checks
    ./scripts/playtest.py --turns 12      # longer run
    ./scripts/playtest.py --no-llm        # mechanisms only, no API calls
    ./scripts/playtest.py --verbose       # show DM narration

Costs roughly 2-4 LLM calls per turn (~$0.0002/turn on Gemini Flash), so a
default run is well under a cent.

Exit code 0 = every check passed.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_OFFLINE", "1")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------- reporting

class Report:
    """Collects check results so one failure does not hide the rest."""

    def __init__(self):
        self.results: List[Dict[str, Any]] = []

    def check(self, name: str, condition: bool, detail: str = "") -> bool:
        self.results.append({"name": name, "ok": bool(condition), "detail": detail})
        mark = "✅" if condition else "❌"
        print(f"   {mark} {name}" + (f" — {detail}" if detail else ""))
        return bool(condition)

    def skip(self, name: str, why: str) -> None:
        self.results.append({"name": name, "ok": None, "detail": why})
        print(f"   ⏭️  {name} — skipped: {why}")

    @property
    def failures(self) -> List[Dict[str, Any]]:
        return [r for r in self.results if r["ok"] is False]

    def summary(self) -> int:
        passed = sum(1 for r in self.results if r["ok"] is True)
        failed = len(self.failures)
        skipped = sum(1 for r in self.results if r["ok"] is None)

        print("\n" + "=" * 66)
        print(f"PLAYTEST: {passed} passed, {failed} failed, {skipped} skipped")
        print("=" * 66)
        if failed:
            print("\nFAILURES:")
            for r in self.failures:
                print(f"  ❌ {r['name']}")
                if r["detail"]:
                    print(f"       {r['detail']}")
        return 1 if failed else 0


# ------------------------------------------------------- mechanism checks

def check_rules_data(report: Report) -> None:
    """Tier 1 and Tier 2 rulesets must be present and grounded."""
    print("\n📚 Rules data")
    try:
        from components.srd_rules import SRDRules
        srd = SRDRules()
        available = srd.available()
        report.check("SRD monsters vendored", available.get("monsters", 0) > 300,
                     f"{available.get('monsters', 0)} monsters "
                     f"(run scripts/vendor_srd_data.py if 0)")
        goblin = srd.monster_stats("Goblin")
        report.check("SRD stats are adjudicable",
                     goblin and goblin["armor_class"] == 15,
                     f"Goblin AC {goblin['armor_class'] if goblin else '?'}")
    except Exception as e:
        report.check("SRD rules load", False, str(e))

    try:
        from components.cosmere_rules import CosmereRules
        cosmere = CosmereRules()
        report.check("Cosmere maneuvers loaded", len(cosmere.maneuvers()) > 0,
                     f"{len(cosmere.maneuvers())} maneuvers")
        citations = cosmere.verify_citations()
        report.check("Every Cosmere rule is grounded in the Handbook",
                     not citations["mismatched"],
                     f"{citations['verified']}/{citations['checked']} verified")
        report.check("Nothing adjudicates unreviewed",
                     cosmere.unreviewed() == [],
                     f"{len(cosmere.unreviewed())} unreviewed")
    except Exception as e:
        report.check("Cosmere rules load", False, str(e))


def check_retrieval(report: Report) -> None:
    """The Handbook must be indexed and actually retrievable."""
    print("\n🔎 Retrieval (RAG)")
    try:
        import sqlite3, pickle, ast
        db = (PROJECT_ROOT / "qdrant_storage" / "collection"
              / "dnd_documents" / "storage.sqlite")
        if not db.exists():
            report.skip("Handbook indexed", "no dnd_documents collection")
            return

        handbook = total = 0
        conn = sqlite3.connect(db)
        for (blob,) in conn.execute("select point from points"):
            try:
                point = pickle.loads(blob)
            except Exception:
                continue
            payload = (point.get("payload") if isinstance(point, dict)
                       else getattr(point, "payload", None))
            if not payload:
                continue
            total += 1
            meta = payload.get("meta")
            if isinstance(meta, str):
                try:
                    meta = ast.literal_eval(meta)
                except Exception:
                    meta = {}
            if "Radiant" in str((meta or {}).get("source_file", "")):
                handbook += 1
        conn.close()

        report.check("Vector store populated", total > 1000, f"{total} chunks")
        report.check("Radiant's Handbook indexed", handbook > 0,
                     f"{handbook} Handbook chunks (0 = the Cosmere ruleset is "
                     f"invisible to the DM)")
    except Exception as e:
        report.check("Retrieval check", False, str(e))


def check_dice_and_checks(report: Report, game) -> None:
    """Dice must be real and difficulty must matter."""
    print("\n🎲 Dice and skill checks")
    engine = game.game_engine
    actor = game._active_character_id()

    rolls = set()
    for _ in range(30):
        result = engine.process_skill_check(
            {"actor": actor, "skill": "stealth", "dc": 13, "context": {}})
        rolls.add(result.get("selected_roll"))
    report.check("d20 produces varied results", len(rolls) > 5,
                 f"{len(rolls)} distinct values in 30 rolls")

    def rate(dc):
        hits = sum(engine.process_skill_check(
            {"actor": actor, "skill": "stealth", "dc": dc, "context": {}})["success"]
            for _ in range(60))
        return hits / 60

    easy, hard = rate(5), rate(25)
    report.check("Difficulty affects outcomes", easy > hard,
                 f"DC 5: {easy:.0%} vs DC 25: {hard:.0%}")

    from components.dice import DiceRoller
    roller = DiceRoller()
    ok = True
    for expression in ("4d6kh3", "1d6 + 2", "2d6[fire]", "1d8-1"):
        try:
            roller.damage_roll(expression)
        except Exception:
            ok = False
    report.check("Dice parser handles real 5e notation", ok,
                 "4d6kh3, spaces, [type] annotations, negatives")

    # Unsupported notation must FAIL LOUDLY, not silently deal 0 damage. Measured
    # before the fix: `4d6e6`, `1d20r1` and even "garbage" all returned
    # total_damage 0 with no error, so a spell written with exploding dice would
    # deal nothing and nobody would know.
    loud = True
    for expression in ("4d6e6", "1d20r1", "1d6+2d6e6"):
        try:
            roller.damage_roll(expression)
            loud = False
        except ValueError:
            pass
        except Exception:
            loud = False
    report.check("Unsupported dice notation fails loudly", loud,
                 "exploding/reroll notation raises instead of dealing 0 damage")


def check_progression(report: Report, game) -> None:
    """
    XP, levelling, rests and death saves.

    These checks are DESTRUCTIVE — they award 6,500 XP and drive HP to 0 to reach
    the death-save branches. They used to do that to the LIVE character and never
    restore it, and because every turn autosaves (0.9), the damage persisted:
    `playtest_save.json` ended up holding a level-5 Aggi at 13/36 HP, so every
    later run started from a mauled, over-levelled character and an encounter
    budgeted as "easy" was lethal. A test must not corrupt the artefact it tests.

    Snapshot before, restore after, and verify the restore actually took.
    """
    print("\n📈 Progression")
    from components.character_manager import CharacterData

    manager = game.character_manager
    actor = game._active_character_id()
    character = manager.characters[actor]

    snapshot = copy.deepcopy(character.to_dict())

    try:
        before_level = character.level
        before_hp = character.hit_points["maximum"]
        manager.award_xp(actor, 6500)
        report.check("XP levels a character up", character.level > before_level,
                     f"level {before_level} -> {character.level}")
        report.check("Levelling raises max HP",
                     character.hit_points["maximum"] > before_hp,
                     f"{before_hp} -> {character.hit_points['maximum']}")

        character.hit_points["current"] = 1
        manager.long_rest(actor)
        report.check("Long rest restores full HP",
                     character.hit_points["current"] == character.hit_points["maximum"],
                     f"{character.hit_points['current']}/{character.hit_points['maximum']}")

        character.hit_points["current"] = 0
        for _ in range(3):
            result = manager.roll_death_save(actor, roll=5)
        report.check("Three failed death saves kill", result.get("dead") is True)

        manager._reset_death_saves(character)
        character.is_dead = False
        character.hit_points["current"] = 0
        revive = manager.roll_death_save(actor, roll=20)
        report.check("A natural 20 revives at 1 HP", revive.get("revived") is True)
    finally:
        manager.characters[actor] = CharacterData.from_dict(snapshot)
        # Belt and braces: the restore is faithful, but this is the one place the
        # playtest deliberately drives HP to 0 and levels a character, so assert the
        # invariant rather than trusting it. A live run reached combat at
        # `current 13 / maximum 8`.
        manager.enforce_hp_invariant(manager.characters[actor])

    restored = manager.characters[actor]
    report.check(
        "Progression checks leave the character unchanged",
        (restored.level == snapshot["level"]
         and restored.hit_points == snapshot["hit_points"]
         and restored.experience_points == snapshot["experience_points"]
         and not getattr(restored, "is_dead", False)),
        f"L{restored.level} hp {restored.hit_points.get('current')}/"
        f"{restored.hit_points.get('maximum')} xp {restored.experience_points}")


def check_combat(report: Report, game) -> None:
    """Attacks must land and deal damage — audit finding #1."""
    print("\n⚔️  Combat")
    try:
        sys.path.insert(0, str(PROJECT_ROOT / "external" / "dnd_engine"))
        from components.dnd_engine_wrapper import DnDEngineWrapper
        from dnd.actions import Attack
        from dnd.blocks.equipment import WeaponSlot

        manager = game.character_manager
        if "playtest_dummy" not in manager.characters:
            manager.add_character({
                "character_id": "playtest_dummy", "name": "Training Dummy",
                "level": 1,
                "ability_scores": {"strength": 10, "dexterity": 10,
                                   "constitution": 10, "intelligence": 10,
                                   "wisdom": 10, "charisma": 10},
                "hit_points": {"current": 200, "maximum": 200, "temporary": 0},
                "armor_class": 5, "character_class": "Goblin",
                "race": "Construct", "background": "Target",
            })

        wrapper = DnDEngineWrapper(game_engine=game.game_engine,
                                   character_manager=manager)
        actor = game._active_character_id()
        attacker = wrapper.entities.get(actor)
        target = wrapper.entities.get("playtest_dummy")
        if attacker is None or target is None:
            report.skip("Combat", "could not build entities")
            return

        report.check("Entities have distinct positions",
                     attacker.position != target.position,
                     f"{attacker.position} vs {target.position}")
        report.check("Entities can see each other",
                     len(attacker.senses.entities) > 0,
                     f"{len(attacker.senses.entities)} in sense map "
                     f"(0 = every attack cancels)")

        wrapper.set_entity_position(actor, (0, 0))
        wrapper.set_entity_position("playtest_dummy", (0, 1))

        start_hp = wrapper.get_entity_current_hp(target)
        cancelled = 0
        for _ in range(25):
            attacker.action_economy.reset_all_costs()
            event = Attack(source_entity_uuid=attacker.uuid,
                           target_entity_uuid=target.uuid,
                           weapon_slot=WeaponSlot.MAIN_HAND).apply(parent_event=None)
            if event is not None and "CANCEL" in str(getattr(event, "phase", "")):
                cancelled += 1
        end_hp = wrapper.get_entity_current_hp(target)

        report.check("Attacks are not cancelled", cancelled == 0,
                     f"{cancelled}/25 cancelled")
        report.check("Attacks deal real damage", end_hp < start_hp,
                     f"dummy HP {start_hp} -> {end_hp}")

        report.check("Ability scores reach the engine",
                     attacker.ability_scores.strength.ability_score.score
                     == manager.characters[actor].ability_scores["strength"],
                     f"STR {attacker.ability_scores.strength.ability_score.score}")

        applied = wrapper.apply_condition("playtest_dummy", "prone")
        report.check("Conditions apply", applied is True,
                     f"active: {wrapper.get_conditions('playtest_dummy')}")

        manager.characters.pop("playtest_dummy", None)
    except Exception as e:
        report.check("Combat", False, f"{type(e).__name__}: {e}")


def check_world_and_quests(report: Report, game) -> None:
    """Travel, the clock, and quest progression."""
    print("\n🗺️  World and quests")
    engine = game.game_engine

    engine.register_location("Playtest Camp", "A waystop", exits=["Playtest Ridge"])
    engine.register_location("Playtest Ridge", "A windswept ridge",
                             exits=["Playtest Camp"])
    engine.set_location("Playtest Camp")
    result = engine.travel_to("Playtest Ridge")
    report.check("Party can travel", result.get("success") is True,
                 f"{result.get('from')} -> {result.get('to')}")

    before = engine.get_game_time()["elapsed_hours"]
    engine.advance_time(days=1)
    report.check("Game clock advances",
                 engine.get_game_time()["elapsed_hours"] > before,
                 f"day {engine.get_game_time()['day']}")

    weather = {engine.advance_time(days=1)["weather"] for _ in range(6)}
    report.check("Highstorms cycle", "highstorm" in weather,
                 f"observed: {sorted(weather)}")

    engine.add_quest_objective("Playtest objective")
    engine.complete_quest_objective("Playtest objective")
    progress = engine.get_quest_progress()
    report.check("Quests complete",
                 "Playtest objective" in progress["completed"],
                 f"{progress['completed_count']} completed")


def check_persistence(report: Report, game) -> None:
    """Save/load must preserve state — audit finding #4."""
    print("\n💾 Persistence")
    manager = game.character_manager
    actor = game._active_character_id()
    character = manager.characters[actor]

    character.hit_points["current"] = 13
    character.equipment = ["playtest spear", "rope"]
    character.experience_points = 1234

    saved = game.save_game(filename="playtest_save.json")
    report.check("Save succeeds", saved is True)

    path = PROJECT_ROOT / "game_saves" / "playtest_save.json"
    if not path.exists():
        report.check("Save file written", False, str(path))
        return

    blob = path.read_text()
    for key in ("hit_points", "equipment", "armor_class", "experience_points"):
        report.check(f"Save contains {key}", key in blob,
                     "" if key in blob else "silently dropped on save")

    from components.character_manager import CharacterData
    data = json.loads(blob)["character_data"][actor]
    restored = CharacterData.from_dict(data)
    report.check("HP round-trips", restored.hit_points["current"] == 13,
                 f"{restored.hit_points['current']} (want 13)")
    report.check("Equipment round-trips",
                 "playtest spear" in (restored.equipment or []))
    report.check("XP round-trips", restored.experience_points == 1234,
                 f"{restored.experience_points} (want 1234)")
    report.check("Class is not 'Unknown'", restored.character_class != "Unknown",
                 restored.character_class)


def check_turns(report: Report, game, turns: int, verbose: bool,
                force_combat_on_turn: Optional[int] = None) -> None:
    """Play real turns through the live pipeline — the actual Tier-3 gate."""
    print(f"\n🎮 Playing {turns} real turns")
    # Inputs are chosen to exercise DIFFERENT mechanics, not to be realistic prose.
    #
    # These were six variants of "I look around" — all passive observation. So a
    # run could pass while travel, oaths, rests and skill checks were never
    # reached through gameplay at all; only combat was, and only because it is
    # forced. Each line below targets a subsystem:
    #
    #   1 perception/investigation  -> the 7-step skill pipeline
    #   2 (forced encounter lands here)
    #   3 travel                    -> the location graph + the game clock
    #   4 an oath                   -> Radiant ideal progression
    #   5 a rest                    -> HP recovery and the clock
    #   6 talking to an NPC         -> the NPC pipeline
    inputs = [
        "I search the ground carefully for tracks or anything hidden.",
        "I travel onwards to the next location.",
        "I speak my oath aloud: Life before death, strength before weakness, "
        "journey before destination.",
        "I make camp and take a long rest to recover.",
        "I look for someone to talk to, and ask them about the Voidbringers.",
        "I ready my weapon and advance towards whatever lies ahead.",
    ]

    # Force an encounter so combat is exercised deterministically. Combat was
    # UNREACHABLE from gameplay until CombatInitializer was wired to
    # combat_trigger; before that this whole subsystem went unchecked here.
    if force_combat_on_turn:
        game.force_combat_on_turn = force_combat_on_turn
        print(f"   (forcing an encounter on turn {force_combat_on_turn})")

    # Snapshot what the turns are supposed to CHANGE. Without this the turn checks
    # only assert that narration looked plausible, so a run could pass while skill
    # checks, travel, the clock and the NPC pipeline were never reached through
    # gameplay at all — only combat was, and only because it is forced.
    before = _mechanism_snapshot(game)

    # Combat asks the player to choose an action. Without an injected provider
    # CombatSessionManager falls back to real input() and an unattended run
    # BLOCKS FOREVER on "Choose action type (1-2):" — a live playtest hung there.
    # Always attack: it is the one choice guaranteed to advance the fight.
    combat_agent = (getattr(game.orchestrator, "agents", {}) or {}).get("combat")
    auto_player = None
    stdout_tap = None
    if combat_agent is not None:
        from components.combat.auto_combat_player import AutoCombatPlayer

        def _hp_fraction() -> float:
            actor = game._active_character_id()
            hp = game.character_manager.characters[actor].hit_points
            return hp.get("current", 0) / max(1, hp.get("maximum", 1))

        auto_player = AutoCombatPlayer(hp_fraction=_hp_fraction)
        stdout_tap = auto_player.install()
        combat_agent.input_provider = auto_player
        print("   (combat auto-played: heal when hurt, else attack)")

    errors, empties = 0, 0
    placeholder_hits = []
    responses: List[str] = []
    combat_outcomes: List[str] = []
    # Every hardcoded fallback that can reach the player verbatim. Each of these
    # is a real string in the source, not a guess: when one appears, the LLM call
    # failed and a canned scene was substituted, which is precisely the silent
    # degradation plan 3.3 exists to remove.
    PLACEHOLDERS = (
        "You find yourself in a moment of decision.",   # scenario_generator_agent:540
        "Continue Forward",                             # its canned choice 1
        "Reassess the Situation",                       # its canned choice 2
        "The adventure continues",                      # haystack_dnd_game:626/677/768
        "Something unexpected happened",                # haystack_dnd_game:639
        "responds to your action",                      # npc_controller / :778
    )

    for i in range(turns):
        player_input = inputs[i % len(inputs)]
        try:
            started = time.time()
            response = game.play_turn(player_input)
            elapsed = time.time() - started
        except Exception as e:
            errors += 1
            print(f"   turn {i+1}: ❌ {type(e).__name__}: {e}")
            continue

        text = str(response or "")
        responses.append(text)
        if not text.strip():
            empties += 1
        for marker in PLACEHOLDERS:
            if marker in text:
                placeholder_hits.append(marker)

        print(f"   turn {i+1}: {len(text):>5} chars, {elapsed:>5.1f}s")

        # Stop once the campaign is over. Playing on past a party wipe produces
        # near-identical refusals, which then fail the "narration varies" check for
        # a reason that is correct behaviour rather than a defect — the classic way
        # a gate starts crying wolf.
        if "campaign is over" in text or "campaign is complete" in text:
            print(f"   (campaign ended on turn {i+1} — stopping)")
            break

        if verbose:
            print(f"      {text[:300]}\n")

    report.check("No turn raised", errors == 0, f"{errors}/{turns} raised")
    report.check("No empty narration", empties == 0, f"{empties}/{turns} empty")
    report.check("No placeholder text reached the player",
                 not placeholder_hits,
                 f"the LLM call failed and a canned scene was substituted: "
                 f"{sorted(set(placeholder_hits))}" if placeholder_hits else "")

    # A live DM never narrates two different actions identically. Identical
    # output is the signature of a fallback that the placeholder list missed.
    distinct = len(set(responses))
    duplicated = sorted(
        {text for text in responses if responses.count(text) > 1})
    report.check("Narration varies between turns",
                 distinct == len(responses) if len(responses) > 1 else True,
                 f"{distinct} distinct responses across {len(responses)} turns"
                 + (f"; repeated text ({len(duplicated[0])} chars): "
                    f"{duplicated[0][:160]!r}" if duplicated else ""))

    # Memory and beats should have accumulated over those turns.
    try:
        from components.retry_with_reasoning import get_conversation_memory
        history = get_conversation_memory().messages(game.thread_id)
        report.check("Conversation history accumulated", len(history) >= turns,
                     f"{len(history)} messages")
    except Exception as e:
        report.skip("Conversation history", str(e))

    beats = game.game_engine.get_narrative_beats(20)
    report.check("Narrative beats recorded", len(beats) > 1,
                 f"{len(beats)} beats (1 = only a one-turn memory)")

    if stdout_tap is not None:
        stdout_tap.uninstall()
    if auto_player is not None and auto_player.decisions:
        print(f"\n   auto-combat made {len(auto_player.decisions)} choices; "
              f"first few: {auto_player.decisions[:3]}")

    _check_mechanisms_fired(report, game, before)
    _check_combat_and_quests(report, game, bool(force_combat_on_turn))


def _mechanism_snapshot(game) -> Dict[str, Any]:
    """
    The state the turns are meant to move.

    Compared before/after so each subsystem is asserted to have fired THROUGH
    GAMEPLAY, not merely to work when called directly. Every defect this playtest
    has found was a wiring defect, so "the API works" is the weaker claim.
    """
    engine = game.game_engine
    manager = game.character_manager
    actor = game._active_character_id()
    character = manager.characters.get(actor)

    def _safe(getter, default=None):
        try:
            return getter()
        except Exception:
            return default

    return {
        "skill_checks": len(_safe(
            lambda: engine.game_state.narrative_context.get("skill_check_log"), []) or []),
        "elapsed_hours": _safe(
            lambda: engine.game_state.environment.get("elapsed_hours"), 0) or 0,
        "location": _safe(
            lambda: engine.game_state.location_context.get("current_location"), ""),
        "known_locations": len(_safe(
            lambda: engine.game_state.location_context.get("known_locations"), {}) or {}),
        "xp": getattr(character, "experience_points", 0) or 0,
        "ideal_level": getattr(character, "ideal_level", 0) or 0,
        "hp": dict(character.hit_points) if character else {},
        "completed_objectives": len(_safe(
            lambda: engine.game_state.quest_context.get("completed_objectives"), []) or []),
        "beats": len(_safe(lambda: engine.get_narrative_beats(50), []) or []),
    }


def _check_mechanisms_fired(report: Report, game, before: Dict[str, Any]) -> None:
    """
    Did the turns actually exercise more than combat?

    This group exists because a 3-turn run once produced TWO encounters and
    nothing else: the turn inputs were six variants of "I look around", and a
    keyword scan for "hostile" hijacked a peaceful scene. Combat dominating the
    playtest is itself a finding, so assert on breadth.
    """
    print("\n🔧 Mechanisms exercised through gameplay")
    after = _mechanism_snapshot(game)

    # The clock is the broadest signal: skill checks, travel and rests all move it.
    report.check("The game clock advanced",
                 after["elapsed_hours"] > before["elapsed_hours"],
                 f"{before['elapsed_hours']}h -> {after['elapsed_hours']}h "
                 f"(unchanged = no turn consumed in-world time — no rest, no "
                 f"travel, no timed action reached the engine)")

    # Registering a location counts as growth: with only two authored locations the
    # DM may legitimately keep the party where the story is, and failing on that
    # would make the gate flaky. What must NOT happen is the graph staying empty.
    report.check("The world graph is populated",
                 after["known_locations"] >= 2,
                 f"{after['known_locations']} known locations; "
                 f"at {after['location']!r}")
    moved = (after["known_locations"] > before["known_locations"]
             or after["location"] != before["location"])
    print(f"   {'✅' if moved else 'ℹ️ '} The party moved or discovered somewhere — "
          f"{before['location']!r} -> {after['location']!r}"
          f"{'' if moved else '  (stayed put this run)'}")

    report.check("Narrative memory accumulated across turns",
                 after["beats"] > before["beats"],
                 f"{before['beats']} -> {after['beats']} beats")

    # HP moving in EITHER direction proves damage or healing reached the record.
    report.check("Character HP changed during play",
                 after["hp"].get("current") != before["hp"].get("current"),
                 f"{before['hp'].get('current')} -> {after['hp'].get('current')}"
                 f"/{after['hp'].get('maximum')}")

    # Soft signals: report them, but do not fail — the DM legitimately may not
    # offer an oath or award XP in three turns, and failing on that would make the
    # gate flaky in a way that invites weakening the real assertions.
    for name, key in (("XP awarded", "xp"),
                      ("An Ideal was spoken", "ideal_level"),
                      ("A quest objective completed", "completed_objectives")):
        moved = after[key] > before[key]
        print(f"   {'✅' if moved else 'ℹ️ '} {name} — "
              f"{before[key]} -> {after[key]}"
              f"{'' if moved else '  (not exercised this run)'}")


def _check_combat_and_quests(report: Report, game, combat_was_forced: bool) -> None:
    """
    Did combat actually run during play, and did the world change because of it?

    Asserts on ENGINE STATE, not on narration text. CombatInitializer had zero
    production callers until it was wired to combat_trigger, so this whole
    subsystem previously went unexercised by the playtest — the combat checks
    above only drive the engine directly, never through a turn.
    """
    print("\n⚔️  Combat through gameplay")
    combat_state = game.game_engine.game_state.combat_state or {}
    resolved = combat_state.get("encounters_resolved", 0)

    if not combat_was_forced:
        report.skip("Combat ran during play", "--force-combat 0")
    else:
        report.check("Combat ran during play", resolved > 0,
                     f"{resolved} encounter(s) resolved "
                     f"(0 = combat never started from a turn)")

    if resolved:
        outcome = combat_state.get("last_outcome")
        report.check("Combat reached an outcome",
                     outcome in ("victory", "defeat", "fled"),
                     f"outcome={outcome!r}")
        report.check("Combat is not left running",
                     combat_state.get("in_combat") is False,
                     f"in_combat={combat_state.get('in_combat')!r}")
        report.check("Combat was recorded in history",
                     len(combat_state.get("history") or []) == resolved,
                     f"{len(combat_state.get('history') or [])} entries")

    print("\n🎯 Quest completion")
    progress = game.game_engine.get_quest_progress()
    report.check("Quest tracker has objectives", progress["total"] > 0,
                 f"{progress['completed_count']}/{progress['total']} complete "
                 f"({progress['percent_complete']}%)")

    # The endgame evaluator must at least be REACHABLE from a turn: it had no
    # production callers, so a campaign could never register as finished.
    reachable = hasattr(game, "_check_campaign_endgame")
    report.check("Endgame check is wired into the turn loop", reachable,
                 "nothing evaluated the campaign's ending condition before")
    if reachable:
        flags = game.game_engine.game_state.campaign_flags or {}
        complete = bool(flags.get("campaign_complete"))
        print(f"      campaign_complete flag: {complete} "
              f"(False is expected unless the endgame was reached)")


def _forced_turn(args) -> Optional[int]:
    """
    Which turn to force combat on: the LAST turn unless asked otherwise.

    0 (the default) means "last". -1 disables. Any other value is that turn.
    """
    if args.force_combat == -1:
        return None
    if args.force_combat == 0:
        return max(1, args.turns)
    return args.force_combat


def check_logs(report: Report) -> None:
    """
    THIS RUN's log should be clean.

    Reviewing `logs[-1]` — the newest file by name — reads whatever process wrote
    last, which is not necessarily this one. A concurrent `pytest` run put 19
    errors into a different log file and the playtest reported them as its own:
    HTTP 403s from real-LLM tests plus DELIBERATE negative-path assertions
    (`Unknown actor: invalid_char`, `Unknown action type: unknown_action`,
    `character nobody not found`). All expected, none this run's.

    So pin the file this process is actually writing to, via the live handler.
    """
    print("\n📋 Log review")

    log_path = _own_log_path()
    if log_path is None or not log_path.exists():
        report.skip("Log review", "could not identify this run's log file")
        return

    lines = log_path.read_text(errors="ignore").splitlines()
    errors = [l for l in lines if " - ERROR - " in l]
    # No whitelist. An earlier version treated "Gemini API error" and
    # "403 Forbidden" as benign, which suppressed exactly the failures that
    # mattered: the run that found the tools+JSON-mode 400 reported a clean log
    # while every scenario turn was falling back to a canned scene.
    report.check("No errors logged", not errors,
                 f"{len(errors)} in {log_path.name}")
    for line in errors[:5]:
        print(f"      {line[-160:]}")


def _own_log_path():
    """
    The log file THIS process is writing to, from the live logging handlers.

    Falls back to the newest `dnd_game_*.log` only if no file handler is found —
    better than skipping the check entirely, but it is the fallback precisely
    because it can pick up another process's file.
    """
    import logging

    for logger in (logging.getLogger(), logging.getLogger("haystack_dnd_game")):
        for handler in getattr(logger, "handlers", []):
            filename = getattr(handler, "baseFilename", None)
            if filename and "dnd_game_" in filename:
                return Path(filename)

    logs = sorted((PROJECT_ROOT / "logs").glob("dnd_game_*.log"))
    return logs[-1] if logs else None


# ------------------------------------------------------------- scripted input

class ScriptedInput:
    """
    Answers the six `input()` prompts in game_initialization so a live run is
    unattended.

    Patching builtins.input keeps this out of production code: the interactive
    setup flow is what a real player sees, and the playtest should exercise that
    same path rather than a test-only branch of it.
    """

    def __init__(self, answers: List[str]):
        self.answers = list(answers)
        self.used: List[str] = []

    def __call__(self, prompt: str = "") -> str:
        answer = self.answers.pop(0) if self.answers else ""
        self.used.append(f"{prompt.strip()} -> {answer!r}")
        print(f"   ↳ {prompt.strip()} {answer!r}")
        return answer


# ------------------------------------------------------------------- main

def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--turns", type=int, default=6,
                        help="how many real turns to play (default 6)")
    parser.add_argument("--no-llm", action="store_true",
                        help="check mechanisms only; skip the live turns")
    parser.add_argument("--verbose", action="store_true",
                        help="print the DM narration for each turn")
    # LAST turn by default, not turn 2.
    #
    # A level-1 Aggi (8 HP) reliably DIES to the authored 2 x CR 1/4 ambush, and
    # once the party is wiped the endgame gate correctly refuses every later turn.
    # With combat on turn 2, turns 3-6 — travel, oath, rest, NPC — never executed,
    # so the clock never advanced and the run reported failures for mechanics it had
    # never reached. Combat last means everything else gets a turn first.
    parser.add_argument("--force-combat", type=int, metavar="TURN", default=0,
                        help="force an encounter on this turn (default: the last "
                             "turn, so a party wipe cannot cut the run short; "
                             "-1 disables)")
    args = parser.parse_args()

    print("=" * 66)
    print("END-TO-END PLAYTEST — docs/REBUILD_PLAN_V5.md §12 Tier 3")
    print("=" * 66)

    report = Report()

    # Mechanisms that need no game instance
    check_rules_data(report)
    check_retrieval(report)

    # Everything below needs a live game
    game = None
    if args.no_llm:
        print("\n🎮 Building a headless game (no orchestrator, --no-llm)")
        try:
            from components.game_engine import GameEngine
            from haystack_dnd_game import HaystackDnDGame

            engine = GameEngine()
            engine.add_character({
                "character_id": "aggi", "name": "Aggi", "level": 3,
                "ability_scores": {"strength": 12, "dexterity": 16,
                                   "constitution": 12, "intelligence": 10,
                                   "wisdom": 12, "charisma": 14},
                "hit_points": {"current": 24, "maximum": 24, "temporary": 0},
                "armor_class": 14, "character_class": "Lightweaver",
                "race": "Alethi", "background": "Soldier",
                "skills": {"stealth": True, "perception": True},
                "radiant_order": "Lightweaver",
                "stormlight_current": 6, "stormlight_capacity": 6,
                "ideal_level": 1,
            })
            game = HaystackDnDGame.__new__(HaystackDnDGame)
            game.game_engine = engine
            game.character_manager = engine.character_manager
            game.dnd_engine_wrapper = None
            game.current_choices = []
            game.turn_counter = 0

            class _Session:
                save_directory = str(PROJECT_ROOT / "game_saves")

                def get_session_metadata(self):
                    return {"session_id": "playtest", "session_active": True}

                def save_session(self, filename=None, game_engine_state=None,
                                 character_manager_state=None):
                    target = Path(self.save_directory) / (filename or "playtest.json")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(json.dumps({
                        "session_metadata": {"player_name": "Playtest"},
                        "game_state": game_engine_state or {},
                        "character_data": character_manager_state or {},
                    }, indent=1, default=str))
                    return {"success": True, "result": {"filepath": str(target)}}

            game.session_manager = _Session()
            print("   ✅ headless game ready")
        except Exception as e:
            report.check("Game construction", False, f"{type(e).__name__}: {e}")
            traceback.print_exc()
            return report.summary()
    else:
        print("\n🎮 Initialising the FULL game (LLM enabled)")
        # Nothing in the import graph calls load_dotenv(); only run_game.sh
        # exports the key. Without this a live run fails even though .env is set.
        try:
            from dotenv import load_dotenv
            load_dotenv(PROJECT_ROOT / ".env")
        except ImportError:
            pass

        if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
            print("   ❌ GEMINI_API_KEY not set (checked the environment and .env).")
            print("      Set it, or run with --no-llm for the mechanism checks.")
            return 1

        # Answers to the six input() prompts in game_initialization, in the
        # order they are actually asked: collection name (default), new-vs-saved,
        # campaign choice, character choice.
        scripted = ScriptedInput(["", "1", "1", "1", "1", "1"])
        import builtins
        real_input = builtins.input
        builtins.input = scripted
        try:
            from core.game_initialization import initialize_enhanced_dnd_game
            from haystack_dnd_game import HaystackDnDGame

            config = initialize_enhanced_dnd_game()
            game = HaystackDnDGame(config=config)
            print("   ✅ full game ready")
        except Exception as e:
            report.check("Game initialisation", False, f"{type(e).__name__}: {e}")
            traceback.print_exc()
            return report.summary()
        finally:
            builtins.input = real_input

    check_dice_and_checks(report, game)
    check_combat(report, game)
    check_world_and_quests(report, game)
    check_progression(report, game)
    check_persistence(report, game)

    if args.no_llm:
        report.skip("Live turns", "--no-llm")
    else:
        check_turns(report, game, args.turns, args.verbose,
                    force_combat_on_turn=_forced_turn(args))

    check_logs(report)
    return report.summary()


if __name__ == "__main__":
    sys.exit(main())
