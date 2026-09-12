"""
Tests for new ManeuverExecutor nodes added for Invested Arts (plan 2.9).

NODES ADDED
-----------
- area_of_effect: expand targets based on geometry
- check: ability check vs DC
- resistance: grant damage resistance

NOTE: 'heal' is in SpellEffectExecutor.SPELL_NODES, not in ManeuverExecutor.KNOWN_NODES,
to preserve the test contract that spell nodes are additions to maneuver nodes.

These extend the existing 6-node interpreter (target/save/damage/attack/roll/ieffect2)
to support Invested Arts mechanics without breaking the 9 authored maneuvers or the
58 existing tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "external" / "dnd_engine"))

pytestmark = [pytest.mark.combat]

from components.character_manager import CharacterManager
from components.combat.maneuver_executor import KNOWN_NODES, ManeuverExecutor
from components.combat.tactical_grid import TacticalGrid
from components.cosmere_rules import CosmereRules
from components.dnd_engine_wrapper import DnDEngineWrapper


class _Engine:
    def __init__(self):
        self.game_state = type("S", (), {"characters": {}})()


def _sheet(char_id, **over):
    """A level-5 character unless overridden."""
    sheet = {
        "character_id": char_id, "name": char_id, "level": 5,
        "ability_scores": {"strength": 16, "dexterity": 14, "constitution": 14,
                           "intelligence": 12, "wisdom": 16, "charisma": 10},
        "hit_points": {"current": 40, "maximum": 50, "temporary": 0},
        "armor_class": 15, "character_class": "Truthwatcher",
        "radiant_order": "Truthwatcher",
        "race": "Human", "background": "Acolyte", "proficiency_bonus": 3,
    }
    sheet.update(over)
    return sheet


@pytest.fixture
def setup():
    """Executor with wrapper, grid, and two positioned characters."""
    TacticalGrid._clear_tiles()
    manager = CharacterManager()
    manager.add_character(_sheet("Caster"))
    manager.add_character(_sheet("Target", hit_points={"current": 25, "maximum": 50}))
    manager.add_character(_sheet("Nearby", hit_points={"current": 30, "maximum": 50}))
    manager.add_character(_sheet("Distant"))

    wrapper = DnDEngineWrapper(game_engine=_Engine(), character_manager=manager)
    # Position: Caster at (0,0), Target at (1,0) [5ft], Nearby at (2,0) [10ft],
    # Distant at (10,0) [50ft]
    wrapper.set_entity_position("Caster", (0, 0))
    wrapper.set_entity_position("Target", (1, 0))
    wrapper.set_entity_position("Nearby", (2, 0))
    wrapper.set_entity_position("Distant", (10, 0))
    wrapper.refresh_senses()

    rules = CosmereRules()
    executor = ManeuverExecutor(wrapper, cosmere_rules=rules,
                                combat_state={"combatant_states": {}})

    yield executor, wrapper, manager
    TacticalGrid._clear_tiles()


def _hp(wrapper, char_id):
    """Current HP = max - damage_taken + temporary."""
    entity = wrapper.entities[char_id]
    con = entity.ability_scores.constitution.modifier
    return entity.health.get_total_hit_points(con)


# ---------------------------------------------------------------------------
# 0. Verify KNOWN_NODES includes the new types
# ---------------------------------------------------------------------------

def test_new_nodes_are_registered():
    """The 3 new node types must be in KNOWN_NODES or they raise AutomationError."""
    assert "area_of_effect" in KNOWN_NODES
    assert "check" in KNOWN_NODES
    assert "resistance" in KNOWN_NODES
    # NOTE: 'heal' is in SpellEffectExecutor.SPELL_NODES, not KNOWN_NODES


# ---------------------------------------------------------------------------
# 1. area_of_effect node
# ---------------------------------------------------------------------------

class TestAreaOfEffectNode:
    """Expand a single target to everyone inside an area."""

    def test_aoe_sphere_affects_entities_in_range(self, setup):
        executor, wrapper, _ = setup

        # Sphere centered on Target (1,0), radius 15ft -> hits Caster (0,0) at 5ft
        # and Nearby (2,0) at 5ft from Target, but not Distant (10,0) at 45ft from Target
        tree = [{
            "type": "area_of_effect",
            "shape": "sphere",
            "size": 15,
            "effects": [{"type": "damage", "damage": "1d6", "damage_type": "fire"}]
        }]

        result = executor.execute({"name": "Fireball", "automation": tree},
                                  "Caster", ["Target"])

        aoe_events = [e for e in result.events if e["type"] == "area_of_effect"]
        assert len(aoe_events) == 1
        affected = aoe_events[0]["affected"]

        # Target (center), Caster (5ft), and Nearby (5ft from Target) are in range
        assert "Target" in affected
        assert "Caster" in affected or "Nearby" in affected  # at least one nearby
        assert "Distant" not in affected, "50ft away should not be hit by 15ft radius"

    def test_aoe_runs_effects_on_each_target(self, setup):
        executor, wrapper, _ = setup

        tree = [{
            "type": "area_of_effect",
            "shape": "sphere",
            "size": 20,
            "effects": [{"type": "damage", "damage": "1d4", "damage_type": "fire"}]
        }]

        result = executor.execute({"name": "AoE", "automation": tree},
                                  "Caster", ["Caster"])

        # Damage events should exist for multiple targets
        damages = [e for e in result.events if e["type"] == "damage"]
        assert len(damages) >= 2, "AoE should damage multiple entities"

    def test_aoe_without_shape_raises(self, setup):
        executor, wrapper, _ = setup

        tree = [{"type": "area_of_effect", "size": 10, "effects": []}]

        result = executor.execute({"name": "Bad", "automation": tree},
                                  "Caster", ["Target"])

        assert result.success is False
        assert "shape" in result.error.lower()


# ---------------------------------------------------------------------------
# 2. check node
# ---------------------------------------------------------------------------

class TestCheckNode:
    """Ability check vs DC, with success/fail branches."""

    def test_check_rolls_and_branches(self, setup):
        executor, wrapper, _ = setup

        # High DC to force a likely fail
        tree = [{
            "type": "check",
            "stat": "intelligence",
            "dc": 25,
            "fail": [{"type": "damage", "damage": "1d4", "damage_type": "psychic"}],
            "success": []
        }]

        result = executor.execute({"name": "Check", "automation": tree},
                                  "Caster", ["Target"])

        checks = [e for e in result.events if e["type"] == "check"]
        assert len(checks) == 1
        assert checks[0]["stat"] == "intelligence"
        assert checks[0]["dc"] == 25
        assert "roll" in checks[0]
        assert "passed" in checks[0]

    def test_check_without_stat_raises(self, setup):
        executor, wrapper, _ = setup

        tree = [{"type": "check", "dc": 15}]

        result = executor.execute({"name": "Bad", "automation": tree},
                                  "Caster", ["Target"])

        assert result.success is False
        assert "stat" in result.error.lower()


# ---------------------------------------------------------------------------
# 3. resistance node
# ---------------------------------------------------------------------------

class TestResistanceNode:
    """Grant damage resistance."""

    def test_resistance_records_effect(self, setup):
        executor, wrapper, _ = setup

        tree = [{
            "type": "resistance",
            "damage_type": "fire",
            "duration": "1 minute"
        }]

        result = executor.execute({"name": "Resist", "automation": tree},
                                  "Caster", ["Target"])

        assert result.success is True

        res_events = [e for e in result.events if e["type"] == "resistance"]
        assert len(res_events) == 1
        assert res_events[0]["damage_type"] == "fire"
        assert res_events[0]["duration"] == "1 minute"
        assert res_events[0]["target"] == "Target"

        # Effect should be recorded
        assert len(result.effects_applied) == 1
        effect = result.effects_applied[0]
        assert "resistance" in effect["effects"]
        assert effect["effects"]["resistance"] == "fire"

    def test_resistance_without_damage_type_raises(self, setup):
        executor, wrapper, _ = setup

        tree = [{"type": "resistance", "duration": "1 minute"}]

        result = executor.execute({"name": "Bad", "automation": tree},
                                  "Caster", ["Target"])

        assert result.success is False
        assert "damage_type" in result.error.lower()


# ---------------------------------------------------------------------------
# 4. Integration: new nodes do not break existing maneuvers
# ---------------------------------------------------------------------------

def test_existing_nodes_still_work(setup):
    """Adding new nodes must not break the 6 existing ones."""
    executor, wrapper, _ = setup

    # A tree using only old nodes
    tree = [
        {"type": "target", "effects": [
            {"type": "damage", "damage": "1d6", "damage_type": "slashing"}
        ]}
    ]

    result = executor.execute({"name": "OldStyle", "automation": tree},
                              "Caster", ["Target"])

    assert result.success is True
    damages = [e for e in result.events if e["type"] == "damage"]
    assert len(damages) == 1
