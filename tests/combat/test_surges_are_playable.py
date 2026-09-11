"""
The five Surges: implemented, wired to their event classes, and OFFERABLE.

THREE BUGS, EACH HIDING THE NEXT.

1. FIVE CUSTOM EVENT CLASSES WERE DEAD CODE. Each surge declares its own
   `ActionEvent` subclass (`LashingEvent`, `SoulcastEvent`, …) carrying
   surge-specific fields, and **not one was ever instantiated**.
   `BaseAction._create_declaration_event` hardcodes `ActionEvent.from_costs(...)`
   with the docstring "Override in subclasses if needed." Nobody overrode it.

   Invisible for four of the five, because they only READ their extra fields off
   `self`. `ProgressionHealing` WRITES one — `execution_event.healing_amount = ...`
   — and pydantic rejects unknown fields, so it raised
   `ValueError: "ActionEvent" object has no field "healing_amount"`.

2. Wiring the real event classes exposed two more, both previously unreachable:
     * `LashingEvent.stormlight_cost: int` had NO DEFAULT, and `from_costs` passes
       only source/target/costs/parent — so constructing it failed outright.
     * `ProgressionHealing`'s rolled-healing branch read
       `ability_scores.wisdom.score`. `Ability` exposes `.modifier`; there is no
       `.score`. Only the explicit-amount branch had ever run.

3. FOUR OF FIVE SURGES COULD NOT BE CHOSEN. Each declared one flavour parameter
   nothing supplied — `lashing_type`, `illusion_type`, `target_essence`,
   `healing_amount` — so `is_offerable()` correctly filtered them out and a
   Windrunner never saw "Lash" on their turn. Only `shardblade_attack` was
   offerable. Fixed with `param_defaults` in the registry, honoured by the
   resolver; the action classes already had sensible defaults, nothing passed them.

The filter itself is right and stays: its docstring records that 15 of 28 NPC
actions in one live encounter were wasted on actions refused for missing params.
The fix is to make the surges legitimately satisfiable, not to loosen the check.

Tests assert through `CombatActionResolver` — the path the game actually uses —
because every one of these bugs passed unit tests that constructed the action
directly with parameters supplied.
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
from components.combat.action_registry import (ACTION_REGISTRY, is_offerable,
                                               offerable_actions,
                                               param_defaults,
                                               required_caller_params)
from components.combat.combat_action_resolver import CombatActionResolver
from components.dnd_engine_wrapper import DnDEngineWrapper

# Order -> the surge that order can use, for the gate tests.
SURGE_BY_ORDER = {
    "Windrunner": "lashing",
    "Skybreaker": "lashing",
    "Edgedancer": "progression_healing",
    "Truthwatcher": "progression_healing",
    "Lightweaver": "illumination",
    "Elsecaller": "soulcast",
}

ALL_SURGES = ("lashing", "progression_healing", "illumination", "soulcast")


class _Engine:
    def __init__(self):
        self.game_state = type("S", (), {"characters": {}})()


def _sheet(char_id, order=None, **over):
    sheet = {
        "character_id": char_id, "name": char_id, "level": 5,
        "ability_scores": {"strength": 16, "dexterity": 14, "constitution": 14,
                           "intelligence": 10, "wisdom": 14, "charisma": 12},
        "hit_points": {"current": 40, "maximum": 40, "temporary": 0},
        "armor_class": 16, "character_class": "Fighter", "race": "Human",
        "background": "Soldier", "equipment": ["Spear"], "proficiency_bonus": 3,
    }
    if order:
        sheet.update({"radiant_order": order, "surgebinding_level": 3,
                      # Capacity matters: character_manager clamps
                      # stormlight_current to stormlight_capacity, so setting
                      # current without capacity silently yields 0.
                      "stormlight_capacity": 10, "stormlight_current": 10})
    sheet.update(over)
    return sheet


@pytest.fixture
def table():
    """One Radiant of every order that has a surge, plus a target and a commoner."""
    manager = CharacterManager()
    for order in sorted(set(SURGE_BY_ORDER)):
        manager.add_character(_sheet(order, order=order))
    manager.add_character(_sheet("Farmer"))
    manager.add_character(_sheet("Target"))

    wrapper = DnDEngineWrapper(game_engine=_Engine(), character_manager=manager)
    combat_state = {"combatant_states": {
        char_id: {"is_hostile": char_id == "Target"}
        for char_id in list(SURGE_BY_ORDER) + ["Farmer", "Target"]}}
    resolver = CombatActionResolver(dnd_engine_wrapper=wrapper,
                                    character_manager=manager,
                                    combat_state=combat_state)
    return resolver, wrapper


def _hurt(wrapper, char_id, amount=20):
    """Wound someone so healing has something to do."""
    from dnd.core.modifiers import DamageType

    entity = wrapper.entities[char_id]
    entity.health.take_damage(amount, DamageType.SLASHING, entity.uuid)


def _cast(resolver, actor, action_type, target="Target", **params):
    """Resolve a surge the way the GAME does — no flavour params unless asked."""
    return resolver.resolve_action({"actor": actor, "action_type": action_type,
                                    "target": target, **params})


# ---------------------------------------------------------------------------
# 1. Event classes are actually used
# ---------------------------------------------------------------------------

class TestSurgesUseTheirOwnEventClasses:
    """
    All five `*Event` subclasses were declared and never instantiated, because
    `BaseAction._create_declaration_event` hardcodes the base `ActionEvent`.
    """

    @pytest.mark.parametrize("action_name,event_name", [
        ("Lashing", "LashingEvent"),
        ("ShardbladeAttack", "ShardbladeAttackEvent"),
        ("ProgressionHealing", "ProgressionHealingEvent"),
        ("Illumination", "IlluminationEvent"),
        ("Soulcast", "SoulcastEvent"),
    ])
    def test_each_surge_declares_its_event_class(self, action_name, event_name):
        import components.combat.roshar_actions as roshar

        action_class = getattr(roshar, action_name)
        declared = action_class.model_fields["event_class"].default
        assert declared is getattr(roshar, event_name)

    def test_a_resolved_surge_produces_its_own_event_type(self, table):
        """The observable consequence: the event is the SUBCLASS, not ActionEvent."""
        from components.combat.roshar_actions import LashingEvent

        resolver, _ = table
        result = _cast(resolver, "Windrunner", "lashing")
        assert result["success"] is True
        assert isinstance(result.get("event"), LashingEvent)

    def test_every_event_class_is_constructible_from_costs(self):
        """
        `from_costs` passes only source/target/costs/parent, so any required field
        without a default makes construction fail. `LashingEvent.stormlight_cost`
        had none — latent while the class was dead code.
        """
        from uuid import uuid4

        import components.combat.roshar_actions as roshar

        for name in ("LashingEvent", "ShardbladeAttackEvent",
                     "ProgressionHealingEvent", "IlluminationEvent",
                     "SoulcastEvent"):
            event_class = getattr(roshar, name)
            event = event_class.from_costs([], uuid4(), uuid4(), None,
                                           use_register=False)
            assert event is not None, name


# ---------------------------------------------------------------------------
# 2. The two bugs the wiring exposed
# ---------------------------------------------------------------------------

class TestProgressionHealingBothBranches:
    """
    The explicit-amount branch was the only one anyone had exercised. The rolled
    branch read `ability_scores.wisdom.score`, which does not exist.
    """

    def test_explicit_amount_heals_exactly_that(self, table):
        resolver, wrapper = table
        _hurt(wrapper, "Target", 20)
        result = _cast(resolver, "Edgedancer", "progression_healing",
                       healing_amount=5)
        assert result["success"] is True
        assert "5" in str(result.get("description", ""))

    def test_omitting_the_amount_rolls_2d8_plus_wisdom(self, table):
        """
        Used to raise `AttributeError: 'Ability' object has no attribute 'score'`.
        WIS 14 (+2) means 2d8+2, so 4..18.
        """
        resolver, wrapper = table
        _hurt(wrapper, "Target", 30)
        result = _cast(resolver, "Edgedancer", "progression_healing")
        assert result["success"] is True

        healed = result.get("healing")
        if healed is None:
            import re
            match = re.search(r"(\d+)", str(result.get("description", "")))
            healed = int(match.group(1)) if match else None
        assert healed is not None, result
        assert 4 <= healed <= 18, f"2d8+2 out of range: {healed}"

    def test_healing_actually_restores_hit_points(self, table):
        """The point of a heal. Asserted on HP, not on the return message."""
        resolver, wrapper = table
        _hurt(wrapper, "Target", 20)
        before = wrapper.get_entity_current_hp(wrapper.entities["Target"]) \
            if hasattr(wrapper, "get_entity_current_hp") else None
        entity = wrapper.entities["Target"]
        con = entity.ability_scores.constitution.modifier
        before = entity.health.get_total_hit_points(con)

        _cast(resolver, "Edgedancer", "progression_healing", healing_amount=7)
        after = entity.health.get_total_hit_points(con)
        assert after > before, f"HP did not rise: {before} -> {after}"


# ---------------------------------------------------------------------------
# 3. Offerability — the bug that made four surges unplayable
# ---------------------------------------------------------------------------

class TestEverySurgeIsOfferable:
    """
    Only `shardblade_attack` was offerable. The other four each declared one
    flavour parameter nothing in the game supplied.
    """

    @pytest.mark.parametrize("surge", ALL_SURGES)
    def test_surge_needs_no_caller_supplied_parameter(self, surge):
        assert required_caller_params(surge) == [], (
            f"{surge} still needs a parameter nothing supplies")

    @pytest.mark.parametrize("surge", ALL_SURGES + ("shardblade_attack",))
    def test_surge_is_offerable(self, surge):
        assert is_offerable(surge) is True

    def test_all_five_surges_appear_in_the_offered_menu(self):
        offered = set(offerable_actions())
        missing = set(ALL_SURGES + ("shardblade_attack",)) - offered
        assert not missing, f"not offerable: {missing}"

    @pytest.mark.parametrize("surge", ALL_SURGES)
    def test_every_defaulted_param_is_a_real_param(self, surge):
        """
        A default for a param the action does not declare would be silently
        ignored — the kind of typo that makes a surge look fixed and stay broken.
        """
        declared = set(ACTION_REGISTRY[surge].get("params") or [])
        for name in param_defaults(surge):
            assert name in declared, f"{surge}: default for unknown param {name!r}"

    def test_move_is_still_not_offerable(self):
        """
        The filter must keep working. `move` genuinely needs `end_position`, which
        the tactical grid supplies through its own path, not the action menu.
        """
        assert is_offerable("move") is False

    def test_an_unknown_action_is_still_not_offerable(self):
        assert is_offerable("teleport_to_shadesmar") is False


class TestSurgesResolveThroughTheGamePath:
    """
    The check that matters: cast each surge with ONLY actor/action/target, exactly
    as the player menu and the NPC AI do. Every one of the three bugs above passed
    tests that constructed the action directly with parameters supplied.
    """

    @pytest.mark.parametrize("order,surge", sorted(SURGE_BY_ORDER.items()))
    def test_each_order_can_use_its_surge(self, table, order, surge):
        resolver, wrapper = table
        _hurt(wrapper, "Target", 20)
        result = _cast(resolver, order, surge)
        assert result["success"] is True, (
            f"{order} could not use {surge}: "
            f"{result.get('error') or result.get('description')}")

    def test_resolution_reports_no_missing_parameter(self, table):
        resolver, wrapper = table
        _hurt(wrapper, "Target", 20)
        for order, surge in sorted(SURGE_BY_ORDER.items()):
            result = _cast(resolver, order, surge)
            message = str(result.get("error") or "")
            assert "missing" not in message.lower(), f"{surge}: {message}"


class TestSurgeGatesStillEnforce:
    """
    Making the surges offerable must not make them free. These gates are the only
    thing stopping a commoner from Lashing.
    """

    def test_a_character_with_no_order_cannot_surge(self, table):
        resolver, _ = table
        result = _cast(resolver, "Farmer", "lashing")
        assert result["success"] is False

    def test_the_wrong_order_cannot_use_another_orders_surge(self, table):
        """A Windrunner has Adhesion and Gravitation — not Progression."""
        resolver, wrapper = table
        _hurt(wrapper, "Target", 20)
        result = _cast(resolver, "Windrunner", "progression_healing")
        assert result["success"] is False

    def test_no_stormlight_means_no_surge(self, table):
        """
        Drained of Stormlight, a Radiant cannot surge.

        Set through `set_roshar_attr`, not `entity.stormlight_current = 0`: the
        engine `Entity` is a pydantic model without `extra="allow"`, so direct
        assignment raises `"Entity" object has no field "stormlight_current"`. The
        wrapper mirrors these attributes into `__dict__` for reads and routes writes
        through this helper so CharacterData stays the authority.
        """
        resolver, wrapper = table
        assert wrapper.set_roshar_attr("Windrunner", "stormlight_current", 0)

        result = _cast(resolver, "Windrunner", "lashing")
        assert result["success"] is False
        assert "stormlight" in str(result.get("error", "")
                                   or result.get("description", "")).lower()

    def test_a_surge_costs_an_action(self, table):
        """
        The action economy still applies: a Radiant who Lashes cannot then attack
        in the same turn.
        """
        resolver, _ = table
        assert _cast(resolver, "Windrunner", "lashing")["success"] is True
        assert _cast(resolver, "Windrunner", "attack")["success"] is False
