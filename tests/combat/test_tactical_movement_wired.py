"""
Tactical movement, wired into combat.

`move` was in ACTION_REGISTRY needing an `end_position` that NOTHING supplied, so
every attempt was refused and combat ran on a fixed two-row line where everyone was
permanently adjacent. No flanking, no cover, no reach, no retreat.

These tests assert the WIRING, not just that the grid works in isolation — six
subsystems in this project were built, tested and never called.

Two bugs were introduced while wiring this, and both are pinned below:
  * terrain leaked across encounters via Tile's class-level registry, so a stale wall
    made a hero immune to attacks in the NEXT test file
  * NPCs could not close the distance, so a fight on a real map ran 334 rounds and
    returned `unknown`
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "external" / "dnd_engine"))

pytestmark = [pytest.mark.combat, pytest.mark.integration]

from components.combat.battle_map import parse_map
from components.combat.tactical_grid import TacticalGrid
from components.dnd_engine_wrapper import DnDEngineWrapper
from components.game_engine import GameEngine


def _sheet(char_id, **over):
    base = {
        "character_id": char_id, "name": char_id, "level": 2,
        "ability_scores": {"strength": 14, "dexterity": 12, "constitution": 12,
                           "intelligence": 10, "wisdom": 10, "charisma": 10},
        "hit_points": {"current": 16, "maximum": 16, "temporary": 0},
        "armor_class": 13, "character_class": "Radiant", "race": "Alethi",
        "background": "Soldier", "equipment": ["Spear"], "proficiency_bonus": 2,
    }
    base.update(over)
    return base


@pytest.fixture(autouse=True)
def _clean_terrain():
    """
    No test may inherit another's battlefield.

    This fixture exists because the leak actually happened: a 12x8 map left 96 tiles
    in Tile's class-level registry and the next file's combat ran inside it.
    """
    TacticalGrid._clear_tiles()
    yield
    TacticalGrid._clear_tiles()


class TestTerrainDoesNotLeak:
    """
    Tile keeps a CLASS-LEVEL registry, so terrain outlives the encounter that built
    it. Measured: a stale wall column blocked line of sight in a later test, the hero
    took no damage, and a death-save test failed with "assert 4 == 0". Same shape as
    Entity._entity_by_position, which cost a whole session.
    """

    def _grid(self):
        battle_map = parse_map({"rows": ["P....#....E",
                                        ".....#.....",
                                        "...........",
                                        ".....#....."]})
        return TacticalGrid(battle_map, None)

    def test_teardown_removes_every_tile(self):
        from dnd.core.base_tiles import Tile

        grid = self._grid()
        assert grid.build_terrain() == 44
        assert len(Tile._tile_by_position) == 44

        grid.teardown()
        assert len(Tile._tile_by_position) == 0, "terrain outlived the encounter"
        assert len(Tile._tile_registry) == 0

    def test_building_replaces_rather_than_overlays(self):
        """Two encounters in a row must not stack their walls."""
        from dnd.core.base_tiles import Tile

        self._grid().build_terrain()
        second = parse_map({"rows": ["P.......E", ".........",
                                     ".........", "........."]})
        TacticalGrid(second, None).build_terrain()
        assert len(Tile._tile_by_position) == 36, "the old map is still present"

    def test_combat_cleanup_tears_down(self):
        """Assert the CALL, not just that teardown exists."""
        import inspect

        from agents.combat_agent import CombatAgent

        source = inspect.getsource(CombatAgent._cleanup_combat)
        assert "teardown" in source, (
            "combat cleanup does not clear terrain, so the next encounter inherits "
            "this one's walls")


class TestCombatUsesTheGrid:
    def _initializer(self, location="The Shattered Plains", hostiles=2):
        from components.combat.combat_initializer import CombatInitializer
        from config.logging_config import get_logger

        class _Campaign:
            source_file = "data/current_campaign/shards_of_honor.json"

        engine = GameEngine()
        engine.add_character(_sheet("Aggi"))
        hostile_ids = []
        for i in range(hostiles):
            cid = f"scout_{i + 1}"
            engine.add_character(_sheet(cid, armor_class=12))
            hostile_ids.append(cid)
        engine.campaign_config = _Campaign()
        engine.set_location(location)

        wrapper = DnDEngineWrapper(game_engine=engine,
                                   character_manager=engine.character_manager)

        initializer = CombatInitializer.__new__(CombatInitializer)
        initializer.game_engine = engine
        initializer.character_manager = engine.character_manager
        initializer.dnd_wrapper = wrapper
        initializer.logger = get_logger("test")
        initializer._locations_cache = None
        initializer._encounters_cache = None
        return initializer, ["Aggi"], hostile_ids

    def test_the_authored_location_map_is_used(self):
        """
        The campaign authors a map per location; it must win over the template.
        """
        initializer, players, hostiles = self._initializer()
        grid = initializer._build_tactical_grid(players, hostiles)
        assert grid is not None, "no grid was built"
        assert grid.map.source == "authored", (
            f"used a {grid.map.source} map instead of the authored one")
        assert grid.map.name == "Broken Plateau"

    def test_combatants_do_not_start_adjacent(self):
        """
        The whole point. On the two-row line everyone was permanently in reach, so
        closing the distance was never a decision.
        """
        initializer, players, hostiles = self._initializer()
        grid = initializer._build_tactical_grid(players, hostiles)
        assert not grid.in_melee_reach("Aggi", hostiles[0])
        assert grid.distance_feet("Aggi", hostiles[0]) >= 25

    def test_an_unknown_location_still_gets_terrain(self):
        """A location with no authored map falls back to a template, not to nothing."""
        initializer, players, hostiles = self._initializer(location="Nowhere")
        grid = initializer._build_tactical_grid(players, hostiles)
        assert grid is not None
        assert grid.map.source == "generated"

    def test_everyone_is_placed(self):
        initializer, players, hostiles = self._initializer(hostiles=3)
        grid = initializer._build_tactical_grid(players, hostiles)
        positions = {grid.position_of(c) for c in players + hostiles}
        assert None not in positions, "someone was left off the grid"
        assert len(positions) == 4, f"combatants share a tile: {positions}"


class TestTheSessionManagerOffersMovement:
    def _session(self, gap=8):
        from components.combat.combat_action_resolver import CombatActionResolver
        from components.combat.combat_session_manager import CombatSessionManager

        engine = GameEngine()
        engine.add_character(_sheet("hero"))
        engine.add_character(_sheet("foe", armor_class=12))
        wrapper = DnDEngineWrapper(game_engine=engine,
                                   character_manager=engine.character_manager)

        rows = ["P" + "." * gap + "E"] + ["." * (gap + 2)] * 3
        grid = TacticalGrid(parse_map({"rows": rows}), wrapper)
        grid.build_terrain()
        grid.place_combatants(["hero"], ["foe"])

        state = {
            "round_number": 1, "current_turn_index": 0, "combat_log": [],
            "initiative_order": [{"char_id": "hero", "initiative": 20},
                                 {"char_id": "foe", "initiative": 10}],
            "active_combatants": ["hero", "foe"],
            "tactical_grid": grid,
            "combatant_states": {
                "hero": {"is_hostile": False, "hp_current": 16, "hp_max": 16,
                         "actions_remaining": 1, "bonus_actions_remaining": 1,
                         "reaction_available": True},
                "foe": {"is_hostile": True, "hp_current": 16, "hp_max": 16,
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
        return session, grid

    def test_movement_is_offered_when_out_of_reach(self):
        session, _ = self._session()
        options = session._movement_actions("hero")
        assert options, "no movement offered although the enemy is out of reach"
        assert any(o["intent"] == "close" for o in options)

    def test_movement_options_carry_a_destination(self):
        """`move` used to be offered with no end_position and always refused."""
        session, _ = self._session()
        for option in session._movement_actions("hero"):
            assert option.get("end_position") is not None
            assert option.get("cost_feet", 0) > 0

    def test_moving_closes_the_distance(self):
        session, grid = self._session()
        before = grid.distance_feet("hero", "foe")
        option = [o for o in session._movement_actions("hero")
                  if o["intent"] == "close"][0]
        result = session._execute_movement("hero", option)
        assert result["success"] is True
        assert grid.distance_feet("hero", "foe") < before

    def test_movement_does_not_consume_the_action(self):
        """
        5e: movement is a separate budget. Charging an action for a step would make
        repositioning strictly worse than standing still.
        """
        session, grid = self._session()
        entity = session.dnd_wrapper.entities["hero"]
        entity.action_economy.reset_all_costs()
        before = entity.action_economy.actions.normalized_score

        option = session._movement_actions("hero")[0]
        session._execute_movement("hero", option)
        assert entity.action_economy.actions.normalized_score == before

    def test_the_speed_budget_is_spent_and_bounded(self):
        session, _ = self._session()
        assert session._speed_remaining("hero") == 30
        option = session._movement_actions("hero")[0]
        session._execute_movement("hero", option)
        assert session._speed_remaining("hero") < 30

    def test_the_budget_resets_each_round(self):
        """Otherwise a character could only ever move once per fight."""
        session, _ = self._session()
        session._spend_movement("hero", 30)
        assert session._speed_remaining("hero") == 0
        session._begin_new_round()
        assert session._speed_remaining("hero") == 30

    def test_no_movement_is_offered_with_an_empty_budget(self):
        session, _ = self._session()
        session._spend_movement("hero", 30)
        assert session._movement_actions("hero") == []

    def test_no_grid_means_no_movement_and_no_crash(self):
        """Every tactical method must degrade quietly on the fallback line."""
        session, _ = self._session()
        session.combat_state["tactical_grid"] = None
        assert session._movement_actions("hero") == []
        assert session._execute_movement("hero", {"end_position": (1, 1)})[
            "success"] is False


class TestNpcsCloseTheDistance:
    """
    With a real map combatants no longer start adjacent, and an NPC that only attacks
    swings at nothing forever. Measured right after wiring the grid:
    `test_full_combat_session` ran **334 rounds and returned `unknown`**. After this
    fix it reports **victory in 9 rounds**.
    """

    def _session(self, gap=6):
        return TestTheSessionManagerOffersMovement()._session(gap=gap)

    def test_an_npc_moves_toward_its_enemy(self):
        session, grid = self._session()
        before = grid.distance_feet("foe", "hero")
        session._npc_close_distance("foe")
        assert grid.distance_feet("foe", "hero") < before

    def test_an_npc_already_in_reach_stands_still(self):
        """Walking away from a target you can already hit is strictly worse."""
        session, grid = self._session()
        grid.move_to("foe", (1, 0), speed_feet=40)
        position = grid.position_of("foe")
        session._npc_close_distance("foe")
        assert grid.position_of("foe") == position

    def test_closing_spends_the_movement_budget(self):
        session, _ = self._session()
        session._npc_close_distance("foe")
        assert session._speed_remaining("foe") < 30

    def test_closing_never_raises_without_a_grid(self):
        session, _ = self._session()
        session.combat_state["tactical_grid"] = None
        session._npc_close_distance("foe")     # must not raise

    def test_an_npc_advances_even_when_it_cannot_reach(self):
        """
        Across a wide field nothing adjacent is reachable in one turn. Without a
        partial advance the fight never progresses — that is the 334-round case.
        """
        session, grid = self._session(gap=14)
        before = grid.distance_feet("foe", "hero")
        session._npc_close_distance("foe")
        assert grid.distance_feet("foe", "hero") < before, (
            "the NPC stood still because it could not close all the way")
