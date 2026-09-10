"""
Death saves in combat — the mechanic that was implemented and never reached.

`CharacterManager.roll_death_save()` is RAW-correct (DC 10, three successes
stabilise, three failures kill, natural 20 revives at 1 HP, natural 1 counts as
two failures) and had **zero production callers**. Combat asked
`_is_combatant_dead()` — really "is at 0 HP" — and ended the encounter with
`all_players_defeated` the instant anyone dropped. So in play, dropping to 0 was
identical to dying: no dying state, no saves, no chance of revival.

Two docstrings in `combat_session_manager.py` asserted that "D&D 5e death save
mechanics are handled entirely by dnd_engine". They are not: grep the engine's
Health block and there is no death-save API at all. That false claim is why the
gap survived review.

There was also a coupling that made the mechanic unreachable even once wired:
`roll_death_save()` reads `character.hit_points["current"]` and returns
`{"skipped": "character is conscious"}` above 0 — and combat only ever wrote HP
to `combat_state` (the display), never back to `CharacterData` (the record).

These tests assert on the RECORD, not the display, and drive real encounters.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "external" / "dnd_engine"))

from components.character_manager import CharacterManager
from components.dnd_engine_wrapper import DnDEngineWrapper
from components.combat.combat_action_resolver import CombatActionResolver
from components.combat.combat_session_manager import CombatSessionManager

pytestmark = [pytest.mark.combat, pytest.mark.integration]


class _StubEngine:
    def __init__(self, character_manager):
        self.character_manager = character_manager
        self.game_state = type("S", (), {"characters": {}})()

    def update_combat_state(self, *a, **k):
        return None


class _StubNarrative:
    def generate_combat_status(self, state):
        return ""

    def generate_action_narrative(self, *a, **k):
        return ""

    def generate_combat_summary(self, *a, **k):
        return ""


class _AlwaysAttack:
    """NPC AI that always attacks the (only) player — no LLM."""

    def decide_action(self, context):
        return {"action_type": "attack", "target": "hero", "reasoning": "test"}


def _character(char_id, name, **over):
    base = {
        "character_id": char_id, "name": name, "level": 3,
        "ability_scores": {"strength": 14, "dexterity": 12, "constitution": 12,
                           "intelligence": 10, "wisdom": 10, "charisma": 10},
        "hit_points": {"current": 20, "maximum": 20, "temporary": 0},
        "armor_class": 13, "character_class": "Fighter", "race": "Human",
        "background": "Soldier", "equipment": ["Spear"], "proficiency_bonus": 2,
    }
    base.update(over)
    return base


def _session(hero_hp=20, hero_ac=13, hostiles=1, hostile_hp=30, rolls=None):
    """A real session manager over the real engine. No mocks on the mechanics."""
    manager = CharacterManager()
    manager.add_character(_character(
        "hero", "Hero", hit_points={"current": hero_hp, "maximum": hero_hp,
                                    "temporary": 0}, armor_class=hero_ac))
    hostile_ids = []
    for i in range(hostiles):
        cid = f"foe_{i + 1}"
        manager.add_character(_character(
            cid, f"Foe {i + 1}", level=5,
            ability_scores={"strength": 18, "dexterity": 14, "constitution": 14,
                            "intelligence": 10, "wisdom": 10, "charisma": 10},
            hit_points={"current": hostile_hp, "maximum": hostile_hp,
                        "temporary": 0},
            equipment=["Greatsword"], proficiency_bonus=3))
        hostile_ids.append(cid)

    engine = _StubEngine(manager)
    wrapper = DnDEngineWrapper(game_engine=engine, character_manager=manager)
    wrapper.set_entity_position("hero", (0, 0))
    for index, cid in enumerate(hostile_ids):
        wrapper.set_entity_position(cid, (index, 1))

    state = {
        "round_number": 1, "current_turn_index": 0, "combat_log": [],
        "initiative_order": ([{"char_id": c, "initiative": 20 - i}
                              for i, c in enumerate(hostile_ids)]
                             + [{"char_id": "hero", "initiative": 1}]),
        "active_combatants": hostile_ids + ["hero"],
        "combatant_states": {},
    }
    for cid in hostile_ids:
        state["combatant_states"][cid] = {
            "is_hostile": True, "hp_current": hostile_hp, "hp_max": hostile_hp,
            "actions_remaining": 1, "bonus_actions_remaining": 1,
            "reaction_available": True}
    state["combatant_states"]["hero"] = {
        "is_hostile": False, "hp_current": hero_hp, "hp_max": hero_hp,
        "actions_remaining": 1, "bonus_actions_remaining": 1,
        "reaction_available": True}

    resolver = CombatActionResolver(dnd_engine_wrapper=wrapper,
                                    character_manager=manager,
                                    combat_state=state)
    session = CombatSessionManager(
        combat_state=state, game_engine=engine, character_manager=manager,
        dnd_engine_wrapper=wrapper, combat_action_resolver=resolver,
        combat_narrative_generator=_StubNarrative(),
        npc_ai_agent=_AlwaysAttack(),
        input_provider=lambda prompt="": "1")

    if rolls is not None:
        # Deterministic death saves: feed a fixed sequence.
        sequence = list(rolls)
        original = manager.roll_death_save

        def scripted(char_id, roll=None):
            value = sequence.pop(0) if sequence else 10
            return original(char_id, roll=value)

        manager.roll_death_save = scripted

    return session, manager, wrapper, state


# ---------------------------------------------------------------- the record

class TestCombatWritesHPBackToTheRecord:
    """
    `combat_state` is the DISPLAY; `CharacterData` is the RECORD. Writing only
    the display meant a 7-round defeat left the character at full health, so the
    encounter restarted next turn and death saves could never fire.
    """

    def test_damage_reaches_character_data(self):
        session, manager, wrapper, state = _session(hero_hp=20)
        before = manager.characters["hero"].hit_points["current"]

        for _ in range(6):
            wrapper.entities["foe_1"].action_economy.reset_all_costs()
            session._execute_npc_turn("foe_1")

        after = manager.characters["hero"].hit_points["current"]
        assert after < before, (
            f"CharacterData still says {after}/20 after six greatsword hits; "
            "combat is only updating the display")

    def test_record_matches_the_engine(self):
        session, manager, wrapper, state = _session(hero_hp=20)
        for _ in range(4):
            wrapper.entities["foe_1"].action_economy.reset_all_costs()
            session._execute_npc_turn("foe_1")

        engine_hp = wrapper.get_entity_current_hp(wrapper.entities["hero"])
        record_hp = manager.characters["hero"].hit_points["current"]
        assert record_hp == max(0, engine_hp), (
            f"record {record_hp} != engine {engine_hp}")

    def test_record_never_goes_negative(self):
        """5e floors HP at 0; a negative on the sheet breaks death saves."""
        session, manager, wrapper, state = _session(hero_hp=6)
        for _ in range(10):
            wrapper.entities["foe_1"].action_economy.reset_all_costs()
            session._execute_npc_turn("foe_1")
        assert manager.characters["hero"].hit_points["current"] == 0


# ------------------------------------------------------------- dying, not dead

class TestZeroHPIsDyingNotDefeat:
    def test_encounter_does_not_end_at_zero_hp(self):
        """
        The core regression. At 0 HP the hero is dying and can still be revived,
        so the encounter must continue.
        """
        session, manager, wrapper, state = _session(hero_hp=4)
        wrapper.entities["foe_1"].action_economy.reset_all_costs()
        session._execute_npc_turn("foe_1")
        session._sync_hp_from_engine()

        hero = manager.characters["hero"]
        assert hero.hit_points["current"] == 0, "test needs the hero downed"
        assert not hero.is_dead
        assert session._is_combatant_dead("hero") is True, "at 0 HP"
        assert session._is_out_of_the_fight("hero") is False, (
            "a dying player is not out of the fight — a nat 20 or a heal can "
            "still bring them back")

        ended, reason = session._check_end_conditions()
        assert ended is False, f"encounter ended at 0 HP with reason {reason!r}"

    def test_a_dead_player_does_end_it(self):
        session, manager, wrapper, state = _session(hero_hp=4)
        manager.characters["hero"].hit_points["current"] = 0
        manager.characters["hero"].is_dead = True

        assert session._is_out_of_the_fight("hero") is True
        ended, reason = session._check_end_conditions()
        assert ended is True and reason == "all_players_defeated"

    def test_a_stable_player_ends_it(self):
        """Stable but unconscious cannot act, so the fight is over."""
        session, manager, wrapper, state = _session(hero_hp=4)
        manager.characters["hero"].hit_points["current"] = 0
        manager.characters["hero"].is_stable = True

        assert session._is_out_of_the_fight("hero") is True
        ended, _ = session._check_end_conditions()
        assert ended is True

    def test_a_hostile_at_zero_is_simply_dead(self):
        """Monsters do not make death saves."""
        from dnd.core.modifiers import DamageType

        session, manager, wrapper, state = _session(hostile_hp=4)
        foe = wrapper.entities["foe_1"]
        foe.health.take_damage(50, DamageType.SLASHING, foe.uuid)
        assert session._is_out_of_the_fight("foe_1") is True
        assert session._roll_death_save_for("foe_1") is None, (
            "a monster must not roll death saves")


# ---------------------------------------------------------------- the saves

class TestDeathSavesActuallyRun:
    def _down_the_hero(self, session, manager, wrapper):
        wrapper.entities["foe_1"].action_economy.reset_all_costs()
        while manager.characters["hero"].hit_points["current"] > 0:
            wrapper.entities["foe_1"].action_economy.reset_all_costs()
            session._execute_npc_turn("foe_1")
            session._sync_hp_from_engine()

    def test_three_failures_kill(self):
        session, manager, wrapper, state = _session(hero_hp=4, rolls=[5, 5, 5])
        self._down_the_hero(session, manager, wrapper)

        for _ in range(3):
            session._roll_death_save_for("hero")

        hero = manager.characters["hero"]
        assert hero.is_dead is True, (
            f"three failed saves did not kill: {hero.death_save_failures} failures")
        assert session._is_out_of_the_fight("hero") is True

    def test_three_successes_stabilise(self):
        session, manager, wrapper, state = _session(hero_hp=4, rolls=[12, 12, 12])
        self._down_the_hero(session, manager, wrapper)

        for _ in range(3):
            session._roll_death_save_for("hero")

        hero = manager.characters["hero"]
        assert hero.is_stable is True
        assert hero.is_dead is False

    def test_natural_twenty_revives_at_one_hp(self):
        session, manager, wrapper, state = _session(hero_hp=4, rolls=[20])
        self._down_the_hero(session, manager, wrapper)

        result = session._roll_death_save_for("hero")

        assert result["revived"] is True
        assert manager.characters["hero"].hit_points["current"] == 1

    def test_revival_also_heals_the_engine(self):
        """
        If only the sheet is revived, the engine still reports 0 and the loop
        skips the hero forever — revived on paper, still down in play.
        """
        session, manager, wrapper, state = _session(hero_hp=4, rolls=[20])
        self._down_the_hero(session, manager, wrapper)
        session._roll_death_save_for("hero")

        engine_hp = wrapper.get_entity_current_hp(wrapper.entities["hero"])
        assert engine_hp >= 1, (
            f"engine still reports {engine_hp} HP after a natural 20; the hero "
            "would be skipped as unconscious on their next turn")
        assert session._is_combatant_dead("hero") is False

    def test_a_natural_one_counts_twice(self):
        session, manager, wrapper, state = _session(hero_hp=4, rolls=[1])
        self._down_the_hero(session, manager, wrapper)

        result = session._roll_death_save_for("hero")
        assert result["failures"] == 2, f"natural 1 gave {result['failures']}"

    def test_saves_are_recorded_for_the_narrator(self):
        session, manager, wrapper, state = _session(hero_hp=4, rolls=[5])
        self._down_the_hero(session, manager, wrapper)
        session._roll_death_save_for("hero")

        saves = state.get("death_saves", [])
        assert len(saves) == 1
        assert saves[0]["actor"] == "hero" and "roll" in saves[0]

    def test_a_conscious_player_does_not_roll(self):
        session, manager, wrapper, state = _session(hero_hp=20)
        result = session._roll_death_save_for("hero")
        assert result is None or "skipped" in result

    def test_a_dead_player_stops_rolling(self):
        session, manager, wrapper, state = _session(hero_hp=4, rolls=[5, 5, 5])
        self._down_the_hero(session, manager, wrapper)
        for _ in range(3):
            session._roll_death_save_for("hero")

        before = len(state.get("death_saves", []))
        session._roll_death_save_for("hero")
        assert len(state.get("death_saves", [])) == before, (
            "kept rolling saves for a dead character")


# ------------------------------------------------------- the loop, end to end

class TestTheLoopRollsSavesForADownedPlayer:
    def test_a_downed_hero_gets_saves_from_the_loop(self):
        """
        The wiring test: run the real loop with a hero who cannot win, and assert
        the loop itself rolled death saves. Nothing called them before.
        """
        session, manager, wrapper, state = _session(
            hero_hp=5, hostiles=1, hostile_hp=60, rolls=[5, 5, 5])
        result = session.run_combat_loop()

        assert state.get("death_saves"), (
            "the loop ended without rolling a single death save")
        assert result["outcome"] == "defeat"
        assert manager.characters["hero"].is_dead is True

    def test_a_lucky_hero_survives_the_loop(self):
        """
        Three successes stabilise: the encounter still ends, but the hero is
        alive — an outcome that was impossible before, since 0 HP meant dead.
        """
        session, manager, wrapper, state = _session(
            hero_hp=5, hostiles=1, hostile_hp=60, rolls=[15, 15, 15])
        session.run_combat_loop()

        hero = manager.characters["hero"]
        assert hero.is_stable is True
        assert hero.is_dead is False, "stabilising must not kill the hero"

    def test_the_loop_still_terminates(self):
        """Death saves must not open a new way to spin forever."""
        session, manager, wrapper, state = _session(
            hero_hp=5, hostiles=2, hostile_hp=60, rolls=[5, 5, 5])
        result = session.run_combat_loop()

        assert result["outcome"] in {"defeat", "victory"}
        assert result.get("stall_breaks", 0) == 0, (
            f"{result.get('stall_breaks')} stall-breaks fired")
        assert result.get("iterations", 0) < 100


class TestARoundBoundaryAlwaysResetsTheEconomy:
    """
    A round that begins WITHOUT resetting the action economy is a permanent
    stalemate, and there are two paths that cross a round boundary: the normal
    advance, and the skip loop that steps over downed combatants.

    Only the first used to reset. So once anyone died and the skip loop started
    wrapping the round, nothing was reset again and every survivor's attack was
    refused for "no action available" forever. Measured before the fix:
    **496 rounds, 978 refusals, outcome `unknown`** — a live goblin and a 12 HP
    hero unable to touch each other. This was my own bug, introduced when death
    saves were wired.

    `test_full_combat_session` had been reporting it for a while and was written off
    as "test-harness wiring" in the plan's known-open list. It was a real defect.
    """

    def test_the_normal_advance_resets(self):
        session, manager, wrapper, state = _session(hostiles=1)
        for entity in wrapper.entities.values():
            entity.action_economy.consume("actions", 1, cost_name="test")

        for _ in range(len(state["initiative_order"])):
            session._advance_turn()

        for cid, entity in wrapper.entities.items():
            assert entity.action_economy.actions.normalized_score > 0, (
                f"{cid} has no action after a round boundary")

    def test_the_skip_path_also_resets(self):
        """
        The regression proper. The dead hostile is LAST in the initiative order, so
        skipping it is what crosses the round boundary — that is the path that used
        to bump `round_number` without resetting anything.
        """
        from dnd.core.modifiers import DamageType

        session, manager, wrapper, state = _session(hostiles=2, hostile_hp=4)

        # Hero first, then TWO dead hostiles. Advancing off the hero lands on a
        # dead combatant, so the SKIP LOOP — not the normal advance — is what
        # wraps the round. Getting this wrong is easy: with a single hostile the
        # index wraps on the normal path and the test proves nothing (my first
        # version made exactly that mistake and passed with the bug restored).
        state["initiative_order"] = [{"char_id": "hero", "initiative": 20},
                                     {"char_id": "foe_1", "initiative": 10},
                                     {"char_id": "foe_2", "initiative": 5}]
        state["current_turn_index"] = 0

        for cid in ("foe_1", "foe_2"):
            entity = wrapper.entities[cid]
            entity.health.take_damage(50, DamageType.SLASHING, entity.uuid)
        for entity in wrapper.entities.values():
            entity.action_economy.consume("actions", 1, cost_name="test")
        assert wrapper.entities["hero"].action_economy.actions.normalized_score == 0

        before = state["round_number"]
        session._advance_turn()

        assert state["round_number"] > before, "no round boundary was crossed"
        hero = wrapper.entities["hero"]
        assert hero.action_economy.actions.normalized_score > 0, (
            "the hero has no action after the skip loop wrapped the round — "
            "every attack is refused for the rest of the fight (measured: 496 "
            "rounds, 978 refusals, outcome `unknown`)")

    def test_a_stalemate_cannot_outlast_the_encounter(self):
        """
        Guard the SYMPTOM as well as the cause: whatever the mechanism, a fight
        between two live combatants must not run hundreds of rounds.
        """
        session, manager, wrapper, state = _session(hostiles=1, hostile_hp=30,
                                                    hero_hp=30)
        result = session.run_combat_loop()
        assert result["rounds"] < 60, (
            f"{result['rounds']} rounds — the fight is not progressing")
        assert result["outcome"] != "unknown", (
            "combat ended without reaching an end condition")

    def test_a_new_round_is_announced_from_either_path(self, capsys):
        session, manager, wrapper, state = _session(hostiles=1)
        session._begin_new_round()
        assert "ROUND" in capsys.readouterr().out

    def test_begin_new_round_survives_a_missing_state_entry(self):
        """A combatant in the order but not in combatant_states must not raise."""
        session, manager, wrapper, state = _session(hostiles=1)
        state["active_combatants"].append("ghost")
        session._begin_new_round()   # must not raise

    def test_an_encounter_with_a_death_still_resolves(self):
        """
        End to end: the fight must reach a real outcome even though a combatant
        dies mid-way and the skip loop engages.
        """
        session, manager, wrapper, state = _session(
            hostiles=2, hostile_hp=4, hero_hp=40)
        result = session.run_combat_loop()

        assert result["outcome"] in {"victory", "defeat"}, (
            f"outcome {result['outcome']!r} after a mid-fight death")
        assert result["rounds"] < 50, f"took {result['rounds']} rounds"
