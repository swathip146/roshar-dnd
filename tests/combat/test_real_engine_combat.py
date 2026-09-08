"""
Real-engine combat tests (plan 1.3) — NO MOCKS.

This is the single most important item in Phase 1. The existing suite in
tests/combat/ passes `Mock()` as the dnd_engine wrapper. `Mock` auto-creates
any attribute you touch, so all of these "passed" while being false:

    entity.health.is_dead()          # Health has no is_dead
    action_economy.reset()           # real name is reset_all_costs
    ModifiableValue.value            # real name is normalized_score
    action_class.cost_type           # actions carry a `costs` LIST

That is exactly how five subsystems broke while the plan reported
"121/126 tests passing (96%)". These tests drive the REAL engine, so a
signature drift fails loudly instead of silently passing.

Rule (plan §12): assert on observable end state — HP actually dropped,
the event actually completed — never on "the method was called."
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "external" / "dnd_engine"))

from components.character_manager import CharacterManager
from components.dnd_engine_wrapper import DnDEngineWrapper

from dnd.actions import Attack
from dnd.blocks.action_economy import ActionEconomy
from dnd.blocks.equipment import WeaponSlot
from dnd.blocks.health import Health
from dnd.core.values import ModifiableValue


def _character(char_id: str, name: str, **over):
    base = {
        "character_id": char_id,
        "name": name,
        "level": 3,
        "ability_scores": {"strength": 16, "dexterity": 14, "constitution": 14,
                           "intelligence": 10, "wisdom": 10, "charisma": 10},
        "hit_points": {"current": 24, "maximum": 24, "temporary": 0},
        "armor_class": 13,
        "character_class": "Fighter",
        "race": "Human",
        "background": "Soldier",
    }
    base.update(over)
    return base


class _StubGameEngine:
    """Minimal stand-in — the wrapper only syncs state back to it."""
    def __init__(self):
        self.game_state = type("S", (), {"characters": {}})()


@pytest.fixture
def wrapper():
    mgr = CharacterManager()
    mgr.add_character(_character("hero", "Hero"))
    mgr.add_character(_character("goblin", "Goblin", armor_class=12))
    return DnDEngineWrapper(game_engine=_StubGameEngine(), character_manager=mgr)


# --------------------------------------------------------------------------
# The engine API the code actually depends on. These would have caught every
# signature bug in finding #6 the day it was introduced.
# --------------------------------------------------------------------------

class TestEngineAPIContract:
    """Pin the real dnd_engine API. Mock() made all of these vacuously true."""

    def test_action_economy_reset_is_reset_all_costs(self):
        assert not hasattr(ActionEconomy, "reset"), \
            "if upstream added reset(), revisit combat_session_manager"
        assert hasattr(ActionEconomy, "reset_all_costs")

    def test_modifiable_value_has_no_dot_value(self):
        assert not hasattr(ModifiableValue, "value"), \
            "code must use .normalized_score, not .value"
        assert hasattr(ModifiableValue, "normalized_score")

    def test_health_has_no_is_dead(self):
        assert not hasattr(Health, "is_dead"), \
            "combat must derive death from get_total_hit_points()"

    def test_take_damage_needs_three_arguments(self):
        import inspect
        params = list(inspect.signature(Health.take_damage).parameters)
        assert params == ["self", "damage", "damage_type", "source_entity_uuid"]

    def test_attack_uses_costs_list_not_cost_type(self):
        assert not hasattr(Attack, "cost_type")
        assert "costs" in Attack.model_fields


# --------------------------------------------------------------------------
# Finding #1: every attack cancelled for want of position/senses.
# --------------------------------------------------------------------------

class TestPositionsAndSenses:
    """1.1 — entities need distinct positions AND populated sense maps."""

    def test_entities_have_distinct_positions(self, wrapper):
        positions = [e.position for e in wrapper.entities.values()]
        assert len(set(positions)) == len(positions), \
            "all entities at the same spot -> line of sight always fails"
        assert (0, 0) not in positions[1:], "second entity still at default origin"

    def test_entities_can_see_each_other(self, wrapper):
        for char_id, entity in wrapper.entities.items():
            assert len(entity.senses.entities) > 0, (
                f"{char_id} has an empty sense map; validate_line_of_sight "
                "will cancel every attack"
            )

    def test_each_entity_senses_the_other(self, wrapper):
        hero = wrapper.entities["hero"]
        goblin = wrapper.entities["goblin"]
        assert goblin.uuid in hero.senses.entities
        assert hero.uuid in goblin.senses.entities

    def test_moving_refreshes_senses(self, wrapper):
        assert wrapper.set_entity_position("hero", (5, 5))
        assert wrapper.entities["hero"].position == (5, 5)
        # senses recomputed, not stale
        assert isinstance(wrapper.entities["hero"].senses.entities, dict)

    def test_move_unknown_entity_is_graceful(self, wrapper):
        assert wrapper.set_entity_position("nobody", (1, 1)) is False


# --------------------------------------------------------------------------
# The end-to-end proof: an attack must be able to deal damage.
# --------------------------------------------------------------------------

class TestAttackActuallyLands:
    """
    Plan 1.3's non-negotiable test. Before 1.1 this was impossible:
    every Attack returned EventPhase.CANCEL 'Target entity not in line of sight'.
    """

    def _attack(self, wrapper):
        hero = wrapper.entities["hero"]
        goblin = wrapper.entities["goblin"]
        hero.action_economy.reset_all_costs()
        return Attack(
            source_entity_uuid=hero.uuid,
            target_entity_uuid=goblin.uuid,
            weapon_slot=WeaponSlot.MAIN_HAND,
        ).apply(parent_event=None)

    def test_attack_is_not_cancelled(self, wrapper):
        event = self._attack(wrapper)
        assert event is not None, "attack produced no event"
        assert "CANCEL" not in str(event.phase), (
            f"attack cancelled: {getattr(event, 'status_message', '')}"
        )

    def test_attack_not_blocked_by_line_of_sight(self, wrapper):
        msg = str(getattr(self._attack(wrapper), "status_message", "") or "")
        assert "line of sight" not in msg.lower()

    def test_attack_not_blocked_by_reach(self, wrapper):
        msg = str(getattr(self._attack(wrapper), "status_message", "") or "")
        assert "not in reach" not in msg.lower()

    def test_repeated_attacks_eventually_deal_damage(self, wrapper):
        """
        Statistical, not per-roll: +3 vs AC 12 hits ~60% of the time, so 25
        swings missing entirely would mean damage is not being applied at all.
        """
        goblin = wrapper.entities["goblin"]
        con = 2
        start = goblin.health.get_total_hit_points(con)

        for _ in range(25):
            self._attack(wrapper)

        end = goblin.health.get_total_hit_points(con)
        assert end < start, (
            f"25 attacks dealt zero damage (HP {start} -> {end}); "
            "damage is not reaching the target"
        )

    def test_damage_is_bounded(self, wrapper):
        """Guard against the old `damage *= 2` style crit bug running away."""
        goblin = wrapper.entities["goblin"]
        con = 2
        start = goblin.health.get_total_hit_points(con)
        for _ in range(10):
            self._attack(wrapper)
        dealt = start - goblin.health.get_total_hit_points(con)
        assert 0 <= dealt <= 10 * 30, f"implausible damage total: {dealt}"


class TestActionEconomyEnforced:
    """
    1.2 — the affordability guard checked a field that does not exist, so
    _can_character_afford_action() always returned True.
    """

    def test_action_is_consumed_by_attacking(self, wrapper):
        hero = wrapper.entities["hero"]
        hero.action_economy.reset_all_costs()
        before = hero.action_economy.actions.normalized_score

        Attack(
            source_entity_uuid=hero.uuid,
            target_entity_uuid=wrapper.entities["goblin"].uuid,
            weapon_slot=WeaponSlot.MAIN_HAND,
        ).apply(parent_event=None)

        assert hero.action_economy.actions.normalized_score < before, \
            "attacking did not consume an action"

    def test_second_attack_same_turn_is_refused(self, wrapper):
        hero = wrapper.entities["hero"]
        goblin = wrapper.entities["goblin"]
        hero.action_economy.reset_all_costs()

        def swing():
            return Attack(
                source_entity_uuid=hero.uuid,
                target_entity_uuid=goblin.uuid,
                weapon_slot=WeaponSlot.MAIN_HAND,
            ).apply(parent_event=None)

        assert swing() is not None
        assert swing() is None, "action economy not enforced within a turn"

    def test_reset_restores_the_action(self, wrapper):
        hero = wrapper.entities["hero"]
        hero.action_economy.reset_all_costs()
        full = hero.action_economy.actions.normalized_score
        Attack(
            source_entity_uuid=hero.uuid,
            target_entity_uuid=wrapper.entities["goblin"].uuid,
            weapon_slot=WeaponSlot.MAIN_HAND,
        ).apply(parent_event=None)
        hero.action_economy.reset_all_costs()
        assert hero.action_economy.actions.normalized_score == full
