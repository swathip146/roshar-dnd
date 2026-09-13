"""
Tests for Cosmere economy mechanics: sapphire marks and polestones.

Item 1: Long-rest refill gated on Stormlight intake (HB:13133-13141, 12343-12382)
Item 2: Polestone cracking/draining mechanics (HB:13231-13241)
"""

import pytest
from typing import Dict, Any

from components.character_manager import CharacterManager, CharacterData
from components.cosmere_rules import CosmereRules
from components.combat.investiture_ledger import InvestiturePointLedger
from components.combat.polestone import (
    Polestone, resolve_polestone_outcome, apply_polestone_outcome,
    consume_polestone_for_art
)

from config.logging_config import get_logger

logger = get_logger(__name__)


# ========================================================================
# ITEM 1: Sapphire Marks and Long Rest Gating
# ========================================================================

def test_sapphire_marks_fields_initialized():
    """Test that sapphire mark fields are added to CharacterData."""
    logger.info("TEST: Sapphire marks fields initialized in CharacterData")

    char = CharacterData(
        character_id="test_radiant",
        name="Test Radiant",
        level=4,
        proficiency_bonus=2,
        ability_scores={"strength": 10, "dexterity": 10, "constitution": 10,
                       "intelligence": 14, "wisdom": 12, "charisma": 10},
        ability_modifiers={"strength": 0, "dexterity": 0, "constitution": 0,
                          "intelligence": 2, "wisdom": 1, "charisma": 0},
        skills={},
        expertise_skills=[],
        conditions=[],
        features=[],
        hit_points={"current": 30, "maximum": 30, "temporary": 0},
        armor_class=15,
        saving_throw_proficiencies=["intelligence", "wisdom"],
        character_class="Lightweaver",
        race="Human",
        background="Soldier",
        radiant_order="Lightweaver",
        ideal_level=2,
    )

    # Check fields exist with defaults
    assert hasattr(char, "sapphire_marks_total")
    assert hasattr(char, "sapphire_marks_dun")
    assert char.sapphire_marks_total == 0
    assert char.sapphire_marks_dun == 0

    logger.info("   ✓ Sapphire marks fields present and initialized to 0")


def test_add_sapphire_marks():
    """Test adding infused and dun sapphire marks."""
    logger.info("TEST: Adding sapphire marks to a character")

    manager = CharacterManager()
    char_data = {
        "character_id": "radiant1",
        "name": "Kaladin",
        "level": 5,
        "proficiency_bonus": 3,
        "ability_scores": {"strength": 16, "dexterity": 14, "constitution": 14,
                          "intelligence": 10, "wisdom": 12, "charisma": 8},
        "ability_modifiers": {"strength": 3, "dexterity": 2, "constitution": 2,
                             "intelligence": 0, "wisdom": 1, "charisma": -1},
        "skills": {},
        "expertise_skills": [],
        "conditions": [],
        "features": [],
        "hit_points": {"current": 40, "maximum": 40, "temporary": 0},
        "armor_class": 16,
        "saving_throw_proficiencies": ["strength", "constitution"],
        "character_class": "Windrunner",
        "race": "Human",
        "background": "Guard",
        "radiant_order": "Windrunner",
        "ideal_level": 3,
        "sapphire_marks_total": 0,  # Override auto-init for testing
        "sapphire_marks_dun": 0,
    }

    char_id = manager.add_character(char_data)
    character = manager.characters[char_id]

    # Add 100 infused marks
    result = manager.add_sapphire_marks(char_id, infused=100, dun=0)
    assert result["success"]
    assert result["total"] == 100
    assert result["infused"] == 100
    assert result["dun"] == 0

    logger.info(f"   ✓ Added 100 infused marks: {result}")

    # Add 50 dun marks
    result = manager.add_sapphire_marks(char_id, infused=0, dun=50)
    assert result["success"]
    assert result["total"] == 150
    assert result["infused"] == 100
    assert result["dun"] == 50

    logger.info(f"   ✓ Added 50 dun marks: {result}")


def test_dun_sapphire_marks_success():
    """Test dunning sapphire marks when sufficient infused marks are available."""
    logger.info("TEST: Dunning sapphire marks (sufficient marks available)")

    manager = CharacterManager()
    char_data = {
        "character_id": "radiant2",
        "name": "Shallan",
        "level": 4,
        "proficiency_bonus": 2,
        "ability_scores": {"strength": 10, "dexterity": 12, "constitution": 12,
                          "intelligence": 16, "wisdom": 14, "charisma": 14},
        "ability_modifiers": {"strength": 0, "dexterity": 1, "constitution": 1,
                             "intelligence": 3, "wisdom": 2, "charisma": 2},
        "skills": {},
        "expertise_skills": [],
        "conditions": [],
        "features": [],
        "hit_points": {"current": 28, "maximum": 28, "temporary": 0},
        "armor_class": 14,
        "saving_throw_proficiencies": ["intelligence", "wisdom"],
        "character_class": "Lightweaver",
        "race": "Human",
        "background": "Artist",
        "radiant_order": "Lightweaver",
        "ideal_level": 2,
        "sapphire_marks_total": 0,  # Override auto-init for testing
        "sapphire_marks_dun": 0,
    }

    char_id = manager.add_character(char_data)

    # Give character 50 infused marks
    manager.add_sapphire_marks(char_id, infused=50, dun=0)

    # Dun 20 marks (level 4 needs 4 × 5 = 20)
    result = manager.dun_sapphire_marks(char_id, amount=20)
    assert result["success"]
    assert result["infused"] == 30
    assert result["dun"] == 20

    logger.info(f"   ✓ Dunned 20 marks: {result}")


def test_dun_sapphire_marks_insufficient():
    """Test dunning sapphire marks when insufficient marks available."""
    logger.info("TEST: Dunning sapphire marks (insufficient marks)")

    manager = CharacterManager()
    char_data = {
        "character_id": "radiant3",
        "name": "Dalinar",
        "level": 8,
        "proficiency_bonus": 3,
        "ability_scores": {"strength": 18, "dexterity": 10, "constitution": 16,
                          "intelligence": 12, "wisdom": 16, "charisma": 14},
        "ability_modifiers": {"strength": 4, "dexterity": 0, "constitution": 3,
                             "intelligence": 1, "wisdom": 3, "charisma": 2},
        "skills": {},
        "expertise_skills": [],
        "conditions": [],
        "features": [],
        "hit_points": {"current": 64, "maximum": 64, "temporary": 0},
        "armor_class": 18,
        "saving_throw_proficiencies": ["strength", "constitution"],
        "character_class": "Bondsmith",
        "race": "Human",
        "background": "Noble",
        "radiant_order": "Bondsmith",
        "ideal_level": 4,
        "sapphire_marks_total": 0,  # Override auto-init for testing
        "sapphire_marks_dun": 0,
    }

    char_id = manager.add_character(char_data)

    # Give character only 10 infused marks (needs 40 for level 8)
    manager.add_sapphire_marks(char_id, infused=10, dun=0)

    # Try to dun 40 marks
    result = manager.dun_sapphire_marks(char_id, amount=40)
    assert not result["success"]
    assert "Insufficient" in result["error"]
    assert result["infused"] == 10

    logger.info(f"   ✓ Cannot dun 40 marks when only 10 available: {result}")


def test_long_rest_with_sufficient_marks():
    """Test long rest succeeds when character has enough sapphire marks."""
    logger.info("TEST: Long rest with sufficient sapphire marks")

    manager = CharacterManager()
    rules = CosmereRules()

    char_data = {
        "character_id": "radiant4",
        "name": "Jasnah",
        "level": 6,
        "proficiency_bonus": 3,
        "ability_scores": {"strength": 10, "dexterity": 12, "constitution": 14,
                          "intelligence": 18, "wisdom": 16, "charisma": 12},
        "ability_modifiers": {"strength": 0, "dexterity": 1, "constitution": 2,
                             "intelligence": 4, "wisdom": 3, "charisma": 1},
        "skills": {},
        "expertise_skills": [],
        "conditions": [],
        "features": [],
        "hit_points": {"current": 20, "maximum": 42, "temporary": 0},  # Damaged
        "armor_class": 15,
        "saving_throw_proficiencies": ["intelligence", "wisdom"],
        "character_class": "Elsecaller",
        "race": "Human",
        "background": "Scholar",
        "radiant_order": "Elsecaller",
        "ideal_level": 3,
        "stormlight_current": 5,
        "stormlight_capacity": 12,
        "sapphire_marks_total": 0,  # Override auto-init, will add manually
        "sapphire_marks_dun": 0,
    }

    char_id = manager.add_character(char_data)
    character = manager.characters[char_id]

    # Give character enough marks (level 6 needs 30 marks)
    required = rules.stormlight_for_long_rest(6)
    assert required == 30
    manager.add_sapphire_marks(char_id, infused=50, dun=0)

    logger.info(f"   Character HP before rest: {character.hit_points['current']}/{character.hit_points['maximum']}")
    logger.info(f"   Sapphire marks: 50 infused, 0 dun")
    logger.info(f"   Required for rest: {required}sm")

    # Take long rest
    result = manager.long_rest(char_id)

    # Should succeed
    assert "error" not in result
    assert character.hit_points["current"] == character.hit_points["maximum"]
    assert character.stormlight_current == character.stormlight_capacity

    # Marks should be dunned
    infused_after = character.sapphire_marks_total - character.sapphire_marks_dun
    assert character.sapphire_marks_dun == 30
    assert infused_after == 20

    logger.info(f"   ✓ Long rest succeeded: HP fully restored to {character.hit_points['maximum']}")
    logger.info(f"   ✓ Dunned {required}sm, {infused_after}sm infused remaining")


def test_long_rest_without_sufficient_marks():
    """Test long rest fails when character lacks sufficient sapphire marks."""
    logger.info("TEST: Long rest without sufficient sapphire marks")

    manager = CharacterManager()
    rules = CosmereRules()

    char_data = {
        "character_id": "radiant5",
        "name": "Renarin",
        "level": 5,
        "proficiency_bonus": 3,
        "ability_scores": {"strength": 12, "dexterity": 10, "constitution": 14,
                          "intelligence": 14, "wisdom": 16, "charisma": 10},
        "ability_modifiers": {"strength": 1, "dexterity": 0, "constitution": 2,
                             "intelligence": 2, "wisdom": 3, "charisma": 0},
        "skills": {},
        "expertise_skills": [],
        "conditions": [],
        "features": [],
        "hit_points": {"current": 15, "maximum": 35, "temporary": 0},  # Damaged
        "armor_class": 14,
        "saving_throw_proficiencies": ["intelligence", "wisdom"],
        "character_class": "Truthwatcher",
        "race": "Human",
        "background": "Noble",
        "radiant_order": "Truthwatcher",
        "ideal_level": 2,
        "stormlight_current": 3,
        "stormlight_capacity": 10,
        "sapphire_marks_total": 0,  # Override auto-init, will add manually
        "sapphire_marks_dun": 0,
    }

    char_id = manager.add_character(char_data)
    character = manager.characters[char_id]

    # Give character insufficient marks (level 5 needs 25, give only 10)
    required = rules.stormlight_for_long_rest(5)
    assert required == 25
    manager.add_sapphire_marks(char_id, infused=10, dun=0)

    hp_before = character.hit_points["current"]
    logger.info(f"   Character HP before rest: {hp_before}/{character.hit_points['maximum']}")
    logger.info(f"   Sapphire marks: 10 infused (need {required}sm)")

    # Try to take long rest
    result = manager.long_rest(char_id)

    # Should fail
    assert "error" in result
    assert result["error"] == "insufficient_stormlight"
    assert result["required_marks"] == 25
    assert result["infused_marks"] == 10

    # HP should NOT be restored
    assert character.hit_points["current"] == hp_before

    # Marks should NOT be dunned
    assert character.sapphire_marks_dun == 0

    logger.info(f"   ✓ Long rest failed: HP remains at {character.hit_points['current']}")
    logger.info(f"   ✓ No marks dunned (still have 10 infused)")


def test_long_rest_no_recovery_needed():
    """Test long rest when character doesn't need recovery (no marks spent)."""
    logger.info("TEST: Long rest when no recovery needed (HB:12352)")

    manager = CharacterManager()
    rules = CosmereRules()

    char_data = {
        "character_id": "radiant6",
        "name": "Lift",
        "level": 3,
        "proficiency_bonus": 2,
        "ability_scores": {"strength": 10, "dexterity": 18, "constitution": 14,
                          "intelligence": 8, "wisdom": 12, "charisma": 14},
        "ability_modifiers": {"strength": 0, "dexterity": 4, "constitution": 2,
                             "intelligence": -1, "wisdom": 1, "charisma": 2},
        "skills": {},
        "expertise_skills": [],
        "conditions": [],
        "features": [],
        "hit_points": {"current": 24, "maximum": 24, "temporary": 0},  # Full HP
        "armor_class": 16,
        "saving_throw_proficiencies": ["dexterity", "charisma"],
        "character_class": "Edgedancer",
        "race": "Human",
        "background": "Urchin",
        "radiant_order": "Edgedancer",
        "ideal_level": 2,
        "stormlight_current": 6,
        "stormlight_capacity": 6,  # Full Stormlight
    }

    char_id = manager.add_character(char_data)
    character = manager.characters[char_id]

    # Give character only 5 marks (less than needed for level 3 = 15)
    manager.add_sapphire_marks(char_id, infused=5, dun=0)

    logger.info(f"   Character at full HP and Stormlight, has only 5sm (needs 15sm normally)")

    # Take long rest (should succeed without spending marks)
    result = manager.long_rest(char_id)

    # Should succeed because no recovery was needed
    assert "error" not in result

    # No marks should be dunned (per HB:12352)
    assert character.sapphire_marks_dun == 0

    logger.info(f"   ✓ Long rest succeeded without dunning marks (no recovery needed)")


# ========================================================================
# ITEM 2: Polestone Cracking/Draining
# ========================================================================

def test_polestone_creation():
    """Test creating polestone objects."""
    logger.info("TEST: Creating polestone objects")

    polestone = Polestone(
        type="diamond",
        size="large",
        value_sm=100,
        infused=True,
        cracked=False
    )

    assert polestone.type == "diamond"
    assert polestone.size == "large"
    assert polestone.value_sm == 100
    assert polestone.infused is True
    assert polestone.cracked is False
    assert polestone.is_usable() is True

    logger.info(f"   ✓ Created usable {polestone.size} {polestone.type} ({polestone.value_sm}sm)")


def test_polestone_outcome_interrupted():
    """Test polestone remains untouched when art is interrupted."""
    logger.info("TEST: Polestone outcome when art interrupted (HB:13239)")

    outcome = resolve_polestone_outcome(interrupted=True, art_succeeded=False)
    assert outcome == "untouched"

    logger.info("   ✓ Art interrupted → polestone UNTOUCHED")


def test_polestone_outcome_success():
    """Test polestone is cracked when art succeeds."""
    logger.info("TEST: Polestone outcome when art succeeds")

    outcome = resolve_polestone_outcome(interrupted=False, art_succeeded=True)
    assert outcome == "crack"

    logger.info("   ✓ Art succeeded → polestone CRACKED")


def test_polestone_outcome_failure():
    """Test polestone is cracked even when art fails (HB:13239)."""
    logger.info("TEST: Polestone outcome when art fails (cost paid regardless)")

    outcome = resolve_polestone_outcome(interrupted=False, art_succeeded=False)
    assert outcome == "crack"

    logger.info("   ✓ Art failed → polestone still CRACKED (cost paid)")


def test_apply_polestone_outcome_crack():
    """Test applying crack outcome to a polestone."""
    logger.info("TEST: Applying CRACK outcome to polestone")

    polestone = Polestone(type="diamond", size="enormous", value_sm=500, infused=True)
    result = apply_polestone_outcome(polestone, "crack")

    assert result["outcome"] == "crack"
    assert polestone.cracked is True
    assert polestone.infused is False
    assert not polestone.is_usable()

    logger.info(f"   ✓ Polestone cracked: {result['message']}")


def test_apply_polestone_outcome_drain():
    """Test applying drain outcome to a polestone."""
    logger.info("TEST: Applying DRAIN outcome to polestone")

    polestone = Polestone(type="heliodor", size="large", value_sm=100, infused=True)
    result = apply_polestone_outcome(polestone, "drain")

    assert result["outcome"] == "drain"
    assert polestone.cracked is False
    assert polestone.infused is False
    assert not polestone.is_usable()  # Not usable until re-infused

    logger.info(f"   ✓ Polestone drained: {result['message']}")


def test_apply_polestone_outcome_untouched():
    """Test applying untouched outcome to a polestone."""
    logger.info("TEST: Applying UNTOUCHED outcome to polestone")

    polestone = Polestone(type="zircon", size="small", value_sm=10, infused=True)
    result = apply_polestone_outcome(polestone, "untouched")

    assert result["outcome"] == "untouched"
    assert polestone.cracked is False
    assert polestone.infused is True
    assert polestone.is_usable()

    logger.info(f"   ✓ Polestone untouched: {result['message']}")


def test_consume_polestone_for_art_success():
    """Test full polestone consumption cycle for successful art."""
    logger.info("TEST: Full polestone consumption for successful art")

    polestone = Polestone(type="diamond", size="large", value_sm=100, infused=True)
    result = consume_polestone_for_art(
        polestone=polestone,
        art_name="Soulcast",
        interrupted=False,
        art_succeeded=True
    )

    assert result["success"] is True
    assert result["outcome"] == "crack"
    assert polestone.cracked is True

    logger.info(f"   ✓ Soulcast succeeded, polestone cracked: {result['message']}")


def test_consume_polestone_for_art_failure():
    """Test polestone is consumed even when art fails."""
    logger.info("TEST: Polestone consumption when art fails (HB:13239)")

    polestone = Polestone(type="diamond", size="large", value_sm=100, infused=True)
    result = consume_polestone_for_art(
        polestone=polestone,
        art_name="Soulcast",
        interrupted=False,
        art_succeeded=False  # Art failed
    )

    assert result["success"] is True
    assert result["outcome"] == "crack"
    assert polestone.cracked is True

    logger.info(f"   ✓ Soulcast failed, but polestone STILL cracked: {result['message']}")


def test_consume_polestone_already_cracked():
    """Test consuming a polestone that's already cracked."""
    logger.info("TEST: Cannot consume already-cracked polestone")

    polestone = Polestone(type="diamond", size="large", value_sm=100, infused=False, cracked=True)
    result = consume_polestone_for_art(
        polestone=polestone,
        art_name="Soulcast",
        interrupted=False,
        art_succeeded=True
    )

    assert result["success"] is False
    assert "cracked and worthless" in result["error"]

    logger.info(f"   ✓ Cannot use cracked polestone: {result['error']}")


def test_consume_polestone_not_infused():
    """Test consuming a polestone that's not infused."""
    logger.info("TEST: Cannot consume dun (not infused) polestone")

    polestone = Polestone(type="diamond", size="large", value_sm=100, infused=False, cracked=False)
    result = consume_polestone_for_art(
        polestone=polestone,
        art_name="Soulcast",
        interrupted=False,
        art_succeeded=True
    )

    assert result["success"] is False
    assert "not infused" in result["error"]

    logger.info(f"   ✓ Cannot use dun polestone: {result['error']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
