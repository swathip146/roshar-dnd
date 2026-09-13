"""
Every playable Radiant order can SELECT and RESOLVE BOTH of its Surges.

THE GAP THIS CLOSES. Only four of the ten Surges had an offerable action
(`lashing`/`progression_healing`/`illumination`/`soulcast`, one bespoke Python
class each). Abrasion, Adhesion, Cohesion, Division, Tension and Transportation
had NO action at all, so Dustbringer, Willshaper and Stoneward could use nothing,
and Windrunner/Skybreaker/Edgedancer/Elsecaller could use only one of their two
Surges. The other nine trees were `needs_adjudication` and nothing invoked them.

THE FIX (surge-complete). A single data-driven `cast_surge` action reads the
`surges` bucket of surgebinding.json and runs each Surge's authored cantrip
`automation` tree through ManeuverExecutor — the same interpreter the reviewed
Windrunner Maneuvers use. Three new nodes make the cantrips resolvable:
`utility` (narrative effects — kindle a fire, recolor eyes, see into the
Cognitive Realm), `forced_move` (a Gravitation creature-Lash), and `choice`
("choose one of the following effects").

These tests assert through `CombatActionResolver` — the path the game uses — and
guard the citation/adjudication invariants the rules architecture depends on.
Progress is logged so a failure reads as a story, not a stack trace.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "external" / "dnd_engine"))

pytestmark = [pytest.mark.combat]

from config.logging_config import get_logger
from components.character_manager import CharacterManager
from components.combat.action_registry import (is_offerable, is_usable_by,
                                               required_caller_params,
                                               unusable_reason)
from components.combat.combat_action_resolver import CombatActionResolver
from components.combat.maneuver_executor import KNOWN_NODES, ManeuverExecutor
from components.cosmere_rules import CosmereRules
from components.dnd_engine_wrapper import DnDEngineWrapper

logger = get_logger(__name__)

# The nine playable orders and BOTH Surges each holds, straight from the
# Invested Arts / Radiant's Handbook (Bondsmith is absent from the source books).
SURGES_BY_ORDER = {
    "Windrunner": ("Adhesion", "Gravitation"),
    "Skybreaker": ("Gravitation", "Division"),
    "Edgedancer": ("Abrasion", "Progression"),
    "Truthwatcher": ("Progression", "Illumination"),
    "Lightweaver": ("Illumination", "Transformation"),
    "Elsecaller": ("Transformation", "Transportation"),
    "Dustbringer": ("Abrasion", "Division"),
    "Willshaper": ("Transportation", "Cohesion"),
    "Stoneward": ("Cohesion", "Tension"),
}

ALL_SURGE_NAMES = sorted({s for pair in SURGES_BY_ORDER.values() for s in pair})

# (order, surge) for every surge every playable order can use — the full matrix.
ORDER_SURGE_PAIRS = sorted(
    (order, surge) for order, pair in SURGES_BY_ORDER.items() for surge in pair)


class _Engine:
    def __init__(self):
        self.game_state = type("S", (), {"characters": {}})()

    def update_combat_state(self, *a, **k):
        return None


def _sheet(char_id, order=None, ac=14, **over):
    sheet = {
        "character_id": char_id, "name": char_id, "level": 5,
        "ability_scores": {"strength": 18, "dexterity": 16, "constitution": 14,
                           "intelligence": 12, "wisdom": 14, "charisma": 12},
        "hit_points": {"current": 60, "maximum": 60, "temporary": 0},
        "armor_class": ac, "character_class": "Fighter", "race": "Alethi",
        "background": "Soldier", "equipment": ["Spear"], "proficiency_bonus": 3,
    }
    if order:
        # Capacity matters: CharacterManager clamps stormlight_current to capacity.
        # IP funds any costed tier; surge cantrips are free and ignore the pool.
        sheet.update({"radiant_order": order, "surgebinding_level": 3,
                      "stormlight_capacity": 10, "stormlight_current": 10,
                      "investiture_points": {"current": 10, "maximum": 10}})
    sheet.update(over)
    return sheet


@pytest.fixture
def arena():
    """One Radiant of every playable order, a plain foe, and a non-Radiant."""
    manager = CharacterManager()
    for order in SURGES_BY_ORDER:
        manager.add_character(_sheet(order, order=order))
    manager.add_character(_sheet("foe", ac=1))   # AC 1 so a real attack lands
    manager.add_character(_sheet("commoner"))     # no radiant_order

    wrapper = DnDEngineWrapper(game_engine=_Engine(), character_manager=manager)
    # Position everyone next to the foe so a weapon-attack Surge has line/ reach.
    wrapper.set_entity_position("foe", (1, 0))
    col = 0
    for cid in list(SURGES_BY_ORDER) + ["commoner"]:
        wrapper.set_entity_position(cid, (0, col))
        col += 1
    wrapper.refresh_senses()

    state = {"combatant_states": {cid: {} for cid in manager.characters}}
    resolver = CombatActionResolver(dnd_engine_wrapper=wrapper,
                                    character_manager=manager, combat_state=state)
    return resolver, wrapper, manager


def _hurt(wrapper, char_id, amount=15):
    from dnd.core.modifiers import DamageType
    e = wrapper.entities[char_id]
    e.health.take_damage(amount, DamageType.SLASHING, e.uuid)


def _cast(resolver, wrapper, actor, surge_name=None, target="foe", **params):
    """Resolve a Surge the way the game does, from a fresh action economy."""
    wrapper.entities[actor].action_economy.reset_all_costs()
    action = {"actor": actor, "action_type": "cast_surge", "target": target}
    if surge_name is not None:
        action["surge_name"] = surge_name
    action.update(params)
    return resolver.resolve_action(action)


# ---------------------------------------------------------------------------
# 1. cast_surge is offerable, and only to Radiants who own a resolvable Surge
# ---------------------------------------------------------------------------

class TestCastSurgeIsOfferable:

    def test_cast_surge_needs_no_caller_supplied_parameter(self):
        assert required_caller_params("cast_surge") == [], (
            "cast_surge still needs a parameter nothing supplies")
        assert is_offerable("cast_surge") is True

    @pytest.mark.parametrize("order", sorted(SURGES_BY_ORDER))
    def test_every_playable_order_is_offered_cast_surge(self, arena, order):
        _, _, manager = arena
        char = manager.characters[order]
        assert is_usable_by("cast_surge", char) is True, (
            unusable_reason("cast_surge", char))

    def test_a_non_radiant_is_denied_cast_surge(self, arena):
        _, _, manager = arena
        commoner = manager.characters["commoner"]
        assert is_usable_by("cast_surge", commoner) is False
        assert "not a Radiant" in unusable_reason("cast_surge", commoner)


# ---------------------------------------------------------------------------
# 2. THE GOAL: every playable order resolves BOTH its Surges through the game path
# ---------------------------------------------------------------------------

class TestBothSurgesResolvePerOrder:

    def test_the_surge_matrix_matches_the_source(self, arena):
        """Guard against drift: the data must still pair orders to these Surges."""
        rules = CosmereRules()
        for order, expected in SURGES_BY_ORDER.items():
            got = tuple(rules.surges_for_order(order))
            logger.info("📜 %-12s surges %s", order, got)
            assert set(got) == set(expected), f"{order}: {got} != {expected}"

    @pytest.mark.parametrize("order,surge", ORDER_SURGE_PAIRS)
    def test_each_order_resolves_each_of_its_surges(self, arena, order, surge):
        resolver, wrapper, _ = arena
        _hurt(wrapper, "foe")
        result = _cast(resolver, wrapper, order, surge)
        logger.info("⚡ %-12s -> %-14s success=%s (%s)", order, surge,
                    result.get("success"),
                    result.get("error") or result.get("description"))
        assert result.get("success") is True, (
            f"{order} could not resolve {surge}: "
            f"{result.get('error') or result.get('description')}")
        # A resolved Surge is NOT a refusal: it carries a real, non-None result
        # object with no `canceled` flag (the invariant test_actions_are_filtered
        # keys off).
        event = result.get("event")
        assert event is not None
        assert getattr(event, "canceled", False) is False

    @pytest.mark.parametrize("order", sorted(SURGES_BY_ORDER))
    def test_auto_selection_picks_an_owned_surge(self, arena, order):
        """With no surge_name, cast_surge picks a Surge the order owns."""
        resolver, wrapper, _ = arena
        result = _cast(resolver, wrapper, order)  # surge_name omitted
        assert result.get("success") is True, result.get("error")
        assert result.get("surge_name") in SURGES_BY_ORDER[order]


# ---------------------------------------------------------------------------
# 3. The gates still hold
# ---------------------------------------------------------------------------

class TestSurgeGatesStillEnforce:

    def test_a_non_radiant_cannot_resolve_a_surge(self, arena):
        resolver, wrapper, _ = arena
        result = _cast(resolver, wrapper, "commoner", "Adhesion")
        assert result.get("success") is False

    def test_the_wrong_order_cannot_use_a_surge_it_does_not_own(self, arena):
        """A Windrunner has Adhesion and Gravitation — not Tension."""
        resolver, wrapper, _ = arena
        result = _cast(resolver, wrapper, "Windrunner", "Tension")
        logger.info("🚫 Windrunner tried Tension: %s", result.get("error"))
        assert result.get("success") is False
        assert result.get("refused") is True
        assert "does not have the Surge of Tension" in str(result.get("error", ""))

    def test_a_surge_costs_an_action(self, arena):
        """A Radiant who Surges cannot then attack in the same turn."""
        resolver, wrapper, _ = arena
        wrapper.entities["Stoneward"].action_economy.reset_all_costs()
        first = resolver.resolve_action({"actor": "Stoneward",
                                         "action_type": "cast_surge",
                                         "target": "foe", "surge_name": "Tension"})
        assert first.get("success") is True
        second = resolver.resolve_action({"actor": "Stoneward",
                                          "action_type": "attack", "target": "foe"})
        assert second.get("success") is False, "the Surge should have spent the action"


# ---------------------------------------------------------------------------
# 4. The mechanical branches actually do their mechanic
# ---------------------------------------------------------------------------

class TestMechanicalSurgeBranches:

    def test_gravitation_creature_lash_is_an_attack_that_forces_movement(self, arena):
        """The 11th-level creature-Lash: an attack roll, forced movement on a hit."""
        resolver, wrapper, _ = arena
        saw_forced_move = False
        for _ in range(10):
            result = _cast(resolver, wrapper, "Windrunner", "Gravitation",
                           surge_option="lash_creature")
            assert result.get("success") is True
            events = result["event"].events
            assert any(e["type"] == "attack" for e in events), events
            if any(e["type"] == "forced_move" for e in events):
                saw_forced_move = True
                break
        logger.info("💨 Gravitation creature-Lash forced movement on a hit: %s",
                    saw_forced_move)
        assert saw_forced_move, "a hitting creature-Lash must force movement"

    def test_tension_stiffen_clothing_grants_an_ac_buff(self, arena):
        resolver, wrapper, _ = arena
        result = _cast(resolver, wrapper, "Stoneward", "Tension",
                       surge_option="stiffen_clothing")
        effects = result["event"].effects_applied
        logger.info("🛡️  Tension stiffen_clothing effects: %s", effects)
        assert result.get("success") is True
        buff = next((e for e in effects if e["effects"].get("ac_bonus") == 2), None)
        assert buff is not None, "stiffen-clothing must grant +2 AC"
        assert buff["effects"].get("speed_reduction_ft") == 10

    def test_a_utility_surge_narrates_and_succeeds(self, arena):
        """A purely narrative cantrip resolves — it is not needs_adjudication."""
        resolver, wrapper, _ = arena
        result = _cast(resolver, wrapper, "Elsecaller", "Transportation")
        logger.info("✨ Transportation narration: %s", result["event"].narrations[:1])
        assert result.get("success") is True
        assert result["event"].narrations, "a utility Surge must record a narration"


# ---------------------------------------------------------------------------
# 5. The new executor nodes are registered and every authored tree executes
# ---------------------------------------------------------------------------

class TestAuthoredSurgeTreesExecute:

    def test_new_nodes_are_known(self):
        for node in ("utility", "forced_move", "choice"):
            assert node in KNOWN_NODES, f"{node} not registered in KNOWN_NODES"

    @pytest.mark.parametrize("surge", ALL_SURGE_NAMES)
    def test_every_surge_tree_executes_and_produces_an_event(self, arena, surge):
        resolver, wrapper, manager = arena
        rules = CosmereRules()
        entry = rules.get_surge(surge)
        assert entry is not None and entry.get("automation"), (
            f"{surge} has no automation tree")
        # Pick any order that owns this surge as the caster.
        caster = next(o for o, pair in SURGES_BY_ORDER.items() if surge in pair)
        executor = ManeuverExecutor(dnd_wrapper=wrapper, cosmere_rules=rules,
                                    combat_state={"combatant_states": {}})
        maneuver = {"name": f"Surge of {surge}", "automation": entry["automation"]}
        result = executor.execute(maneuver, caster, targets=["foe"])
        logger.info("🌀 %-14s -> success=%s events=%d", surge, result.success,
                    len(result.events))
        assert result.success is True, f"{surge} failed: {result.error}"
        assert result.events, f"{surge} executed but produced no observable event"

    @pytest.mark.parametrize("surge", ALL_SURGE_NAMES)
    def test_every_surge_tree_uses_only_known_nodes(self, surge):
        rules = CosmereRules()

        def walk(node):
            if isinstance(node, dict):
                if "type" in node:
                    assert node["type"] in KNOWN_NODES, (
                        f"{surge} uses unsupported node {node['type']!r}")
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        walk(rules.get_surge(surge)["automation"])


# ---------------------------------------------------------------------------
# 6. The rules-integrity invariants must survive the authoring pass
# ---------------------------------------------------------------------------

class TestAuthoringStaysGrounded:

    def test_no_unreviewed_entries_and_all_citations_verify(self):
        rules = CosmereRules()
        assert rules.unreviewed() == [], (
            f"unreviewed entries would silently not adjudicate: "
            f"{[u.get('name') for u in rules.unreviewed()]}")
        result = rules.verify_citations()
        logger.info("📖 citations checked=%d verified=%d mismatched=%d",
                    result["checked"], result["verified"], len(result["mismatched"]))
        assert not result["mismatched"], (
            f"citation(s) drifted: {result['mismatched'][:5]}")

    def test_all_ten_surges_have_an_automation_tree(self):
        rules = CosmereRules()
        for name, entry in (rules._data.get("surges") or {}).items():
            assert entry.get("automation"), f"{name} still has no automation tree"
            assert entry.get("automation_status") != "needs_adjudication", (
                f"{name} is still marked needs_adjudication")
