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


def check_progression(report: Report, game) -> None:
    """XP, levelling, rests and death saves."""
    print("\n📈 Progression")
    manager = game.character_manager
    actor = game._active_character_id()
    character = manager.characters[actor]

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
    manager.long_rest(actor)


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


def check_turns(report: Report, game, turns: int, verbose: bool) -> None:
    """Play real turns through the live pipeline — the actual Tier-3 gate."""
    print(f"\n🎮 Playing {turns} real turns")
    inputs = [
        "I look around and take stock of my surroundings.",
        "I search the area for anything useful.",
        "I listen carefully for any sound of danger.",
        "I examine the ground for tracks.",
        "I call out to see if anyone answers.",
        "I ready myself and move on.",
    ]

    errors, empties = 0, 0
    placeholder_hits = []
    responses: List[str] = []
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
    report.check("Narration varies between turns",
                 distinct == len(responses) if len(responses) > 1 else True,
                 f"{distinct} distinct responses across {len(responses)} turns")

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


def check_logs(report: Report) -> None:
    """The run's own log should be clean."""
    print("\n📋 Log review")
    logs = sorted((PROJECT_ROOT / "logs").glob("dnd_game_*.log"))
    if not logs:
        report.skip("Log review", "no log file")
        return
    lines = logs[-1].read_text(errors="ignore").splitlines()
    errors = [l for l in lines if " - ERROR - " in l]
    # These are known-benign in a sandbox without network access.
    benign = ("ProxyError", "403 Forbidden", "Gemini API error")
    real = [l for l in errors if not any(b in l for b in benign)]
    report.check("No unexpected errors logged", not real,
                 f"{len(real)} unexpected ({len(errors)} total) in {logs[-1].name}")
    for line in real[:3]:
        print(f"      {line[-150:]}")


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
        check_turns(report, game, args.turns, args.verbose)

    check_logs(report)
    return report.summary()


if __name__ == "__main__":
    sys.exit(main())
