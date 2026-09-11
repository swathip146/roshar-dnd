"""
Maneuvers are reachable from a real combat turn — the wiring, not the interpreter.

`ManeuverExecutor` and `LashingDicePool` shipped with 58 passing tests and **ZERO
production callers**. All nine authored maneuvers executed perfectly in
tests/combat/test_maneuvers_are_data.py while no player could reach a single one.

That is the SEVENTH instance of the pattern catalogued in docs/REBUILD_PLAN_V5.md §14e
— a subsystem built, tested, and unreachable — and it was nearly reported as done. The
lesson recorded there is exact: **a passing unit test proves a component works, never
that the product reaches it.**

So this file deliberately tests almost nothing about maneuver MECHANICS (that is the
other file's job). It tests the seam: does a Windrunner taking a turn get offered
maneuvers, does choosing one run it, does it cost the action and the die, and does a
non-Radiant see nothing. Every assertion goes through `CombatSessionManager`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "external" / "dnd_engine"))

pytestmark = [pytest.mark.combat]

from components.combat.battle_map import parse_map
from components.combat.tactical_grid import TacticalGrid
from components.dnd_engine_wrapper import DnDEngineWrapper
from components.game_engine import GameEngine


def _sheet(char_id, order=None, **over):
    base = {
        "character_id": char_id, "name": char_id, "level": 5,
        "ability_scores": {"strength": 16, "dexterity": 14, "constitution": 12,
                           "intelligence": 10, "wisdom": 12, "charisma": 10},
        "hit_points": {"current": 40, "maximum": 40, "temporary": 0},
        "armor_class": 14, "character_class": "Radiant", "race": "Alethi",
        "background": "Soldier", "equipment": ["Spear"], "proficiency_bonus": 3,
    }
    if order:
        base.update({"radiant_order": order, "surgebinding_level": 3,
                     "stormlight_capacity": 10, "stormlight_current": 10})
    base.update(over)
    return base


@pytest.fixture(autouse=True)
def _clean_terrain():
    """No test may inherit another's battlefield — tiles are class-level state."""
    TacticalGrid._clear_tiles()
    yield
    TacticalGrid._clear_tiles()


def _session(hero_order="Windrunner"):
    """A real CombatSessionManager with a Windrunner, a foe, and a grid."""
    from components.combat.combat_action_resolver import CombatActionResolver
    from components.combat.combat_session_manager import CombatSessionManager

    engine = GameEngine()
    engine.add_character(_sheet("hero", order=hero_order))
    engine.add_character(_sheet("foe", armor_class=12))
    wrapper = DnDEngineWrapper(game_engine=engine,
                               character_manager=engine.character_manager)

    grid = TacticalGrid(parse_map({"rows": ["P..E", "....", "....", "...."]}),
                        wrapper)
    grid.build_terrain()
    grid.place_combatants(["hero"], ["foe"])

    state = {
        "round_number": 1, "current_turn_index": 0, "combat_log": [],
        "initiative_order": [{"char_id": "hero", "initiative": 20},
                             {"char_id": "foe", "initiative": 10}],
        "active_combatants": ["hero", "foe"],
        "tactical_grid": grid,
        "combatant_states": {
            "hero": {"is_hostile": False, "hp_current": 40, "hp_max": 40,
                     "actions_remaining": 1, "bonus_actions_remaining": 1,
                     "reaction_available": True},
            "foe": {"is_hostile": True, "hp_current": 40, "hp_max": 40,
                    "actions_remaining": 1, "bonus_actions_remaining": 1,
                    "reaction_available": True}},
    }
    resolver = CombatActionResolver(dnd_engine_wrapper=wrapper,
                                    character_manager=engine.character_manager,
                                    combat_state=state)
    session = CombatSessionManager(
        combat_state=state, game_engine=engine,
        character_manager=engine.character_manager,
        dnd_engine_wrapper=wrapper, combat_action_resolver=resolver,
        combat_narrative_generator=None, npc_ai_agent=None,
        input_provider=lambda prompt="": "1")
    return session, state


class TestTheExecutorIsReachable:
    """
    The check whose absence let 58 passing tests coexist with an unplayable feature.
    """

    def test_the_session_builds_a_maneuver_executor(self):
        session, _ = _session()
        assert session._maneuvers() is not None

    def test_the_session_builds_a_lashing_dice_pool(self):
        """
        `lashing_dice` had zero references in components/, agents/ or core/, so there
        was nothing to spend even if a tree had run.
        """
        session, _ = _session()
        assert session._dice_pool().remaining("hero") > 0

    def test_both_are_cached_on_combat_state(self):
        """
        Cached so the SAME instance persists across a turn: the pool must not reset
        its dice, and the executor must not lose the effects it recorded.
        """
        session, state = _session()
        first = session._maneuvers()
        session._dice_pool().spend("hero")

        assert session._maneuvers() is first
        assert state["maneuver_executor"] is first
        assert session._dice_pool().remaining("hero") < session._dice_pool().get("hero").total


class TestManeuversAreOfferedOnATurn:
    def test_a_windrunner_is_offered_maneuvers(self):
        session, _ = _session()
        options = session._maneuver_actions("hero")
        assert options, "a Windrunner was offered no maneuvers"
        assert all(o["action_type"] == "maneuver" for o in options)

    def test_every_offered_maneuver_carries_what_execution_needs(self):
        """A menu entry without a `maneuver_id` cannot be dispatched."""
        session, _ = _session()
        for option in session._maneuver_actions("hero"):
            assert option.get("maneuver_id"), option
            assert option.get("name")

    def test_a_non_radiant_is_offered_nothing(self):
        session, _ = _session(hero_order=None)
        assert session._maneuver_actions("hero") == []

    def test_an_order_with_no_authored_maneuvers_is_offered_nothing(self):
        """
        All nine authored maneuvers are Windrunner-only. A Stoneward must not be
        offered them — and must not crash for having none.
        """
        session, _ = _session(hero_order="Stoneward")
        assert session._maneuver_actions("hero") == []

    def test_an_exhausted_pool_offers_nothing(self):
        """Never offer what cannot be paid for."""
        session, _ = _session()
        pool = session._dice_pool()
        while pool.remaining("hero"):
            pool.spend("hero")
        assert session._maneuver_actions("hero") == []

    def test_target_requirement_is_derived_from_the_tree(self):
        """
        A maneuver needs a target only if its automation has a `target` node. Full
        Lashing does; Alerted Lash (a self bonus) does not.
        """
        session, _ = _session()
        by_name = {o["name"]: o for o in session._maneuver_actions("hero")}
        assert by_name["Full Lashing"]["requires_target"] is True
        assert by_name["Alerted Lash"]["requires_target"] is False


class TestExecutingThroughTheSession:
    def test_executing_a_maneuver_reports_success(self):
        session, _ = _session()
        result = session._execute_maneuver("hero", "alerted_lash")
        assert result["success"] is True
        assert result["description"]

    def test_executing_spends_a_lashing_die(self):
        session, _ = _session()
        before = session._dice_pool().remaining("hero")
        session._execute_maneuver("hero", "alerted_lash")
        assert session._dice_pool().remaining("hero") == before - 1

    def test_a_targeted_maneuver_reaches_the_target(self):
        session, _ = _session()
        result = session._execute_maneuver("hero", "full_lashing", "foe")
        assert result["success"] is True
        # Either a save event or its consequences — both prove the target was used.
        assert any(e.get("target") == "foe" for e in result["events"]), result

    def test_an_unknown_maneuver_is_refused_not_raised(self):
        session, _ = _session()
        result = session._execute_maneuver("hero", "lash_the_moons")
        assert result["success"] is False
        assert "unknown maneuver" in result["error"]

    def test_a_full_action_maneuver_costs_the_action(self):
        """
        Maneuvers bypass the engine's action path, so the economy must be debited
        EXPLICITLY — otherwise a Windrunner could maneuver all round. `Full Lashing`
        is `action_type: "action"` in the authored data.
        """
        session, _ = _session()
        entity = session.dnd_wrapper.entities["hero"]
        assert entity.action_economy.can_afford("actions", 1)

        session._spend_maneuver_action("hero", {"maneuver_id": "full_lashing"})
        assert not entity.action_economy.can_afford("actions", 1)

    def test_a_triggered_maneuver_does_not_cost_a_separate_action(self):
        """
        `Distracting Attack` is `on_hit` — it rides along on an attack the actor is
        already making. Charging it an action would make a Windrunner strictly worse
        for having the option.
        """
        session, _ = _session()
        entity = session.dnd_wrapper.entities["hero"]

        session._spend_maneuver_action("hero", {"maneuver_id": "distracting_attack"})
        assert entity.action_economy.can_afford("actions", 1)
