"""
Surge accuracy + the Investiture-Point economy (plan 2.9).

These tests pin the book-accurate corrections made to the three hardcoded surge
classes (AUDIT_HARDCODED_SURGE_ACCURACY.md §4) and the new resource economy:

  * Lashing / Illumination — FREE cantrips (the old per-cast Stormlight-sphere
    cost was invented). Lashing also records the Adhesion escape DC.
  * ShardbladeAttack — a REAL attack roll vs AC (not armour-ignoring auto-hit),
    a level-scaled weapon die of a CHOSEN damage type (not fixed 2d6 necrotic),
    gated at the Third Ideal.
  * Soulcast — two tiers: a free cantrip (no combat effect) and a costed
    5th-level Art that requires the target's Constitution saving throw before it
    restrains (not an unconditional, unresisted effect).
  * ProgressionHealing (Regrowth) — 2 Investiture Points, spent through
    InvestiturePointLedger by the resolver; refunded when the action is refused.

Every test logs its progress so a failure reads as a story, not a stack trace.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "external" / "dnd_engine"))

pytestmark = [pytest.mark.combat]

from config.logging_config import get_logger
from components.character_manager import CharacterManager
from components.combat.combat_action_resolver import CombatActionResolver
from components.dnd_engine_wrapper import DnDEngineWrapper

logger = get_logger(__name__)


class _Engine:
    def __init__(self):
        self.game_state = type("S", (), {"characters": {}})()

    def update_combat_state(self, *a, **k):
        return None


def _sheet(char_id, **over):
    sheet = {
        "character_id": char_id, "name": char_id, "level": 5,
        "ability_scores": {"strength": 16, "dexterity": 14, "constitution": 14,
                           "intelligence": 12, "wisdom": 14, "charisma": 12},
        "hit_points": {"current": 40, "maximum": 40, "temporary": 0},
        "armor_class": 14, "character_class": "Fighter", "race": "Alethi",
        "background": "Soldier", "equipment": ["Spear"], "proficiency_bonus": 3,
    }
    sheet.update(over)
    return sheet


@pytest.fixture
def arena():
    """A Windrunner (with Shardblade), an Edgedancer (with IP), and a target."""
    mgr = CharacterManager()
    mgr.add_character(_sheet(
        "kal", radiant_order="Windrunner", surgebinding_level=3, ideal_level=3,
        stormlight_capacity=10, stormlight_current=8,
        has_shardblade=True, shardblade_summoned=True, shardblade_name="Syl"))
    mgr.add_character(_sheet(
        "lift", radiant_order="Edgedancer", surgebinding_level=3, ideal_level=3,
        stormlight_capacity=10, stormlight_current=8,
        investiture_points={"current": 6, "maximum": 6}))
    mgr.add_character(_sheet(
        "shal", radiant_order="Lightweaver", surgebinding_level=3, ideal_level=3,
        stormlight_capacity=10, stormlight_current=8))
    mgr.add_character(_sheet("foe", armor_class=13))

    wrapper = DnDEngineWrapper(game_engine=_Engine(), character_manager=mgr)
    state = {"combatant_states": {cid: {} for cid in mgr.characters}}
    resolver = CombatActionResolver(dnd_engine_wrapper=wrapper,
                                    character_manager=mgr, combat_state=state)
    return mgr, wrapper, resolver


def _hurt(wrapper, char_id, amount=20):
    from dnd.core.modifiers import DamageType
    e = wrapper.entities[char_id]
    e.health.take_damage(amount, DamageType.SLASHING, e.uuid)


# ---------------------------------------------------------------------------
# Lashing — a free cantrip with an Adhesion escape DC
# ---------------------------------------------------------------------------

class TestLashingIsAFreeCantrip:

    def test_lashing_costs_no_stormlight_and_records_escape_dc(self, arena):
        from components.combat.roshar_actions import Lashing, LashingEvent
        from components.combat.roshar_actions import _proficiency_bonus, _character_level

        mgr, wrapper, _ = arena
        kal = wrapper.entities["kal"]
        before = kal.stormlight_current
        logger.info(f"🧪 Lashing: kal starts with {before} Stormlight")

        event = Lashing(source_entity_uuid=kal.uuid,
                        target_entity_uuid=wrapper.entities["foe"].uuid).apply()
        assert isinstance(event, LashingEvent)
        assert not getattr(event, "canceled", True), "free cantrip was cancelled"
        assert kal.stormlight_current == before, "a cantrip must not spend Stormlight"

        level = _character_level(kal)
        bump = (level >= 5) + (level >= 11) + (level >= 17)
        expected = 8 + bump + _proficiency_bonus(kal)
        logger.info(f"🧪 Lashing: escape DC {event.escape_dc} (expected {expected})")
        assert event.escape_dc == expected, "Adhesion escape DC 8+prof scaling is wrong"

    def test_lashing_available_when_drained(self, arena):
        from components.combat.roshar_actions import Lashing
        mgr, wrapper, _ = arena
        assert wrapper.set_roshar_attr("kal", "stormlight_current", 0)
        event = Lashing(source_entity_uuid=wrapper.entities["kal"].uuid,
                        target_entity_uuid=wrapper.entities["foe"].uuid).apply()
        logger.info("🧪 Lashing at 0 Stormlight succeeded (free cantrip)")
        assert event is not None and not getattr(event, "canceled", False)


# ---------------------------------------------------------------------------
# ShardbladeAttack — a real attack roll vs AC
# ---------------------------------------------------------------------------

class TestShardbladeIsARealAttack:

    def test_nat_one_misses_and_deals_no_damage(self, arena, monkeypatch):
        from components.combat.roshar_actions import ShardbladeAttack
        mgr, wrapper, _ = arena
        foe = wrapper.entities["foe"]
        before = foe.health.damage_taken
        monkeypatch.setattr(random, "randint", lambda a, b: a)  # every roll = min => d20 of 1

        event = ShardbladeAttack(
            source_entity_uuid=wrapper.entities["kal"].uuid,
            target_entity_uuid=foe.uuid).apply()
        logger.info(f"🧪 Shardblade nat-1: hit={event.hit}, damage={event.soul_damage}")
        assert event.hit is False, "a natural 1 must miss (no armour-ignoring auto-hit)"
        assert event.soul_damage == 0
        assert foe.health.damage_taken == before, "a miss must deal no damage"

    def test_nat_twenty_hits_for_chosen_type_not_necrotic(self, arena, monkeypatch):
        from components.combat.roshar_actions import ShardbladeAttack
        mgr, wrapper, _ = arena
        foe = wrapper.entities["foe"]
        before = foe.health.damage_taken
        monkeypatch.setattr(random, "randint", lambda a, b: b)  # every roll = max => d20 of 20

        event = ShardbladeAttack(
            source_entity_uuid=wrapper.entities["kal"].uuid,
            target_entity_uuid=foe.uuid).apply()
        logger.info(f"🧪 Shardblade crit: hit={event.hit}, dmg={event.soul_damage} "
                    f"{event.damage_type}")
        assert event.hit is True
        assert event.soul_damage > 0 and foe.health.damage_taken > before
        assert event.damage_type == "slashing", "damage type must be the chosen weapon type"

    def test_third_ideal_gate(self, arena):
        from components.combat.roshar_actions import ShardbladeAttack
        mgr, wrapper, _ = arena
        # Drop the Windrunner below the Third Ideal: the blade is refused.
        assert wrapper.set_roshar_attr("kal", "ideal_level", 2)
        assert wrapper.set_roshar_attr("kal", "surgebinding_level", 2)
        event = ShardbladeAttack(
            source_entity_uuid=wrapper.entities["kal"].uuid,
            target_entity_uuid=wrapper.entities["foe"].uuid).apply()
        logger.info("🧪 Shardblade below Third Ideal was refused")
        assert event is None or getattr(event, "canceled", False)


# ---------------------------------------------------------------------------
# Soulcast — two tiers, the Art requires a saving throw
# ---------------------------------------------------------------------------

class TestSoulcastTwoTiers:

    def test_cantrip_tier_is_free_and_does_not_restrain(self, arena):
        from components.combat.roshar_actions import Soulcast
        mgr, wrapper, _ = arena
        foe = wrapper.entities["foe"]
        event = Soulcast(source_entity_uuid=wrapper.entities["shal"].uuid,
                         target_entity_uuid=foe.uuid).apply()  # art_level default 0
        logger.info(f"🧪 Soulcast cantrip: canceled={getattr(event,'canceled',None)}, "
                    f"restrained={getattr(event,'restrained',None)}")
        assert not getattr(event, "canceled", True)
        assert event.restrained is False, "the free cantrip must not restrain"
        assert "Restrained" not in getattr(foe, "active_conditions", {})

    def test_art_tier_restrains_only_on_a_failed_save(self, arena, monkeypatch):
        from components.combat.roshar_actions import Soulcast
        mgr, wrapper, _ = arena
        foe = wrapper.entities["foe"]

        # Force the target's d20 low => failed CON save => Restrained.
        monkeypatch.setattr(random, "randint", lambda a, b: a)
        event = Soulcast(source_entity_uuid=wrapper.entities["shal"].uuid,
                         target_entity_uuid=foe.uuid, art_level=5).apply()
        logger.info(f"🧪 Soulcast Art (failed save): saved={event.saved}, "
                    f"restrained={event.restrained}, dc={event.save_dc}")
        assert event.saved is False
        assert event.restrained is True

    def test_art_tier_does_nothing_on_a_successful_save(self, arena, monkeypatch):
        from components.combat.roshar_actions import Soulcast
        mgr, wrapper, _ = arena
        foe = wrapper.entities["foe"]

        # Force the target's d20 high => successful CON save => no effect.
        monkeypatch.setattr(random, "randint", lambda a, b: b)
        event = Soulcast(source_entity_uuid=wrapper.entities["shal"].uuid,
                         target_entity_uuid=foe.uuid, art_level=5).apply()
        logger.info(f"🧪 Soulcast Art (made save): saved={event.saved}, "
                    f"restrained={event.restrained}")
        assert event.saved is True
        assert event.restrained is False, "a successful save must not be restrained"


# ---------------------------------------------------------------------------
# ProgressionHealing (Regrowth) — the Investiture-Point economy
# ---------------------------------------------------------------------------

class TestProgressionEconomy:

    def test_regrowth_spends_two_investiture_points(self, arena):
        mgr, wrapper, resolver = arena
        _hurt(wrapper, "foe", 20)
        pool = mgr.characters["lift"].investiture_points
        before = pool["current"]
        result = resolver.resolve_action({
            "actor": "lift", "action_type": "progression_healing", "target": "foe"})
        logger.info(f"🧪 Regrowth: success={result['success']} ip_spent="
                    f"{result.get('ip_spent')} ({before}->{pool['current']})")
        assert result["success"] is True
        assert result.get("ip_spent") == 2
        assert pool["current"] == before - 2

    def test_refusal_refunds_no_investiture(self, arena):
        """A wrong-order caster is refused; if IP was taken it is refunded."""
        mgr, wrapper, resolver = arena
        # Give the Windrunner an IP pool, then have it try Progression (wrong order).
        mgr.characters["kal"].investiture_points = {"current": 6, "maximum": 6}
        _hurt(wrapper, "foe", 20)
        result = resolver.resolve_action({
            "actor": "kal", "action_type": "progression_healing", "target": "foe"})
        logger.info(f"🧪 Wrong-order Regrowth: success={result['success']} "
                    f"ip now {mgr.characters['kal'].investiture_points['current']}")
        assert result["success"] is False
        assert mgr.characters["kal"].investiture_points["current"] == 6, (
            "IP must be refunded when the art does not take effect")

    def test_empty_pool_refuses_without_spending_the_action(self, arena):
        mgr, wrapper, resolver = arena
        mgr.characters["lift"].investiture_points["current"] = 0
        result = resolver.resolve_action({
            "actor": "lift", "action_type": "progression_healing", "target": "foe"})
        logger.info(f"🧪 Empty pool: success={result['success']} "
                    f"refused={result.get('refused')}")
        assert result["success"] is False
        assert result.get("refused") is True


# ---------------------------------------------------------------------------
# The ledger refreshes on a long rest
# ---------------------------------------------------------------------------

class TestLedgerLongRest:

    def test_long_rest_restores_investiture_to_maximum(self, arena):
        from components.combat.investiture_ledger import InvestiturePointLedger
        from components.cosmere_rules import CosmereRules

        mgr, _, _ = arena
        ledger = InvestiturePointLedger(mgr, CosmereRules())
        mgr.characters["lift"].investiture_points["current"] = 1
        assert ledger.refresh_on_long_rest("lift") is True
        restored = mgr.characters["lift"].investiture_points["current"]
        logger.info(f"🧪 Long rest restored Investiture to {restored}")
        assert restored == mgr.characters["lift"].investiture_points["maximum"]
