"""
Test Roshar Combat Integration - Combat Plan v4.0
Tests all new Stormlight, Shardblade, and Shardplate functionality in CharacterManager
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from components.character_manager import CharacterManager, CharacterData
from config.logging_config import get_logger

logger = get_logger(__name__)


def test_stormlight_tracking():
    """Test Stormlight sphere tracking and consumption"""
    logger.info("🧪 Testing Stormlight tracking...")

    manager = CharacterManager()

    # Create a Windrunner Radiant at level 5
    windrunner_data = {
        "character_id": "kaladin",
        "name": "Kaladin Stormblessed",
        "level": 5,
        "ability_scores": {"strength": 16, "dexterity": 14, "constitution": 15, "intelligence": 10, "wisdom": 14, "charisma": 12},
        "character_class": "Radiant",
        "race": "Human",
        "radiant_order": "Windrunner",
        "ideal_level": 3,  # Third Ideal - has Shardblade
        "stormlight_current": 5,
        "stormlight_capacity": 10  # Level 5 × 2
    }

    char_id = manager.add_character(windrunner_data)
    character = manager.characters[char_id]

    # Test 1: Verify auto-calculation of stormlight capacity
    assert character.stormlight_capacity == 10, f"Expected capacity 10, got {character.stormlight_capacity}"
    assert character.stormlight_current == 5, f"Expected current 5, got {character.stormlight_current}"
    logger.info(f"✅ Test 1 passed: Stormlight capacity = {character.stormlight_capacity}")

    # Test 2: Consume Stormlight for Lashing
    success = manager.consume_stormlight(char_id, 2)
    assert success, "Failed to consume Stormlight"
    assert character.stormlight_current == 3, f"Expected 3 remaining, got {character.stormlight_current}"
    logger.info(f"✅ Test 2 passed: Consumed 2 Stormlight, {character.stormlight_current} remaining")

    # Test 3: Try to consume more than available
    success = manager.consume_stormlight(char_id, 5)
    assert not success, "Should have failed to consume 5 Stormlight (only 3 available)"
    assert character.stormlight_current == 3, "Stormlight should not have changed"
    logger.info(f"✅ Test 3 passed: Correctly prevented over-consumption")

    # Test 4: Replenish Stormlight (capped at capacity)
    success = manager.replenish_stormlight(char_id, 10)
    assert success, "Failed to replenish Stormlight"
    assert character.stormlight_current == 10, f"Expected full capacity (10), got {character.stormlight_current}"
    logger.info(f"✅ Test 4 passed: Replenished to full capacity")

    # Test 5: Set new capacity
    success = manager.set_stormlight_capacity(char_id, 12)
    assert success, "Failed to set capacity"
    assert character.stormlight_capacity == 12, f"Expected capacity 12, got {character.stormlight_capacity}"
    assert character.stormlight_current == 10, "Current should remain capped at old capacity"
    logger.info(f"✅ Test 5 passed: Updated capacity to {character.stormlight_capacity}")

    logger.info("✅ All Stormlight tracking tests passed!\n")
    return manager, char_id


def test_passive_stormlight_healing():
    """Test passive Stormlight healing during short rest"""
    logger.info("🧪 Testing passive Stormlight healing...")

    manager = CharacterManager()

    # Create wounded Radiant with Stormlight
    radiant_data = {
        "character_id": "shallan",
        "name": "Shallan Davar",
        "level": 4,
        "ability_scores": {"strength": 10, "dexterity": 12, "constitution": 13, "intelligence": 16, "wisdom": 14, "charisma": 15},
        "character_class": "Radiant",
        "radiant_order": "Lightweaver",
        "ideal_level": 2,
        "stormlight_current": 5,
        "stormlight_capacity": 8,
        "hit_points": {"current": 15, "maximum": 30, "temporary": 0}
    }

    char_id = manager.add_character(radiant_data)
    character = manager.characters[char_id]

    # Test: Apply passive healing (1 HP per sphere)
    healing = manager.apply_passive_stormlight_healing(char_id, rest_type="short")
    assert healing == 5, f"Expected 5 HP healing, got {healing}"
    assert character.hit_points["current"] == 20, f"Expected HP 20, got {character.hit_points['current']}"
    logger.info(f"✅ Passive healing test passed: Healed {healing} HP with 5 spheres")

    # Test: Healing capped at max HP
    character.hit_points["current"] = 28
    healing = manager.apply_passive_stormlight_healing(char_id, rest_type="short")
    assert character.hit_points["current"] == 30, "HP should be capped at maximum"
    logger.info(f"✅ Healing cap test passed: HP capped at maximum")

    logger.info("✅ All passive healing tests passed!\n")


def test_shardblade_mechanics():
    """Test Shardblade summoning and dismissal"""
    logger.info("🧪 Testing Shardblade mechanics...")

    manager = CharacterManager()

    # Create Third Ideal Windrunner (has Shardblade)
    radiant_data = {
        "character_id": "dalinar",
        "name": "Dalinar Kholin",
        "level": 12,
        "ability_scores": {"strength": 18, "dexterity": 12, "constitution": 16, "intelligence": 14, "wisdom": 16, "charisma": 15},
        "character_class": "Radiant",
        "radiant_order": "Bondsmith",
        "ideal_level": 3,
        "stormlight_capacity": 24
    }

    char_id = manager.add_character(radiant_data)

    # Test 1: Grant Shardblade (Third Ideal unlocks living blade)
    success = manager.grant_shardblade(char_id, blade_type="living", blade_name="Oathbringer")
    assert success, "Failed to grant Shardblade"

    character = manager.characters[char_id]
    assert character.has_shardblade, "Character should have Shardblade"
    assert character.shardblade_type == "living", f"Expected living blade, got {character.shardblade_type}"
    assert character.shardblade_name == "Oathbringer", f"Expected 'Oathbringer', got {character.shardblade_name}"
    logger.info(f"✅ Test 1 passed: Granted {character.shardblade_type} Shardblade '{character.shardblade_name}'")

    # Test 2: Summon Shardblade (1 Bonus Action)
    success = manager.summon_shardblade(char_id)
    assert success, "Failed to summon Shardblade"
    assert character.shardblade_summoned, "Shardblade should be summoned"
    logger.info(f"✅ Test 2 passed: Shardblade summoned")

    # Test 3: Try to summon again (should fail - already summoned)
    success = manager.summon_shardblade(char_id)
    assert success == False, "Should not be able to summon already-summoned blade"
    logger.info(f"✅ Test 3 passed: Prevented double summoning")

    # Test 4: Dismiss Shardblade (free action)
    success = manager.dismiss_shardblade(char_id)
    assert success, "Failed to dismiss Shardblade"
    assert not character.shardblade_summoned, "Shardblade should be dismissed"
    logger.info(f"✅ Test 4 passed: Shardblade dismissed")

    logger.info("✅ All Shardblade tests passed!\n")


def test_shardplate_mechanics():
    """Test Shardplate HP tracking and damage"""
    logger.info("🧪 Testing Shardplate mechanics...")

    manager = CharacterManager()

    # Create Fourth Ideal Radiant (has Shardplate)
    radiant_data = {
        "character_id": "jasnah",
        "name": "Jasnah Kholin",
        "level": 15,
        "ability_scores": {"strength": 12, "dexterity": 14, "constitution": 14, "intelligence": 20, "wisdom": 16, "charisma": 16},
        "character_class": "Radiant",
        "radiant_order": "Elsecaller",
        "ideal_level": 4
    }

    char_id = manager.add_character(radiant_data)

    # Test 1: Grant Shardplate (Fourth Ideal unlocks living plate)
    success = manager.grant_shardplate(char_id, plate_type="living")
    assert success, "Failed to grant Shardplate"

    character = manager.characters[char_id]
    assert character.has_shardplate, "Character should have Shardplate"
    assert character.shardplate_hp_maximum == 75, f"Expected 75 HP (15×5), got {character.shardplate_hp_maximum}"
    assert character.shardplate_hp_current == 75, "Shardplate should start at full HP"
    logger.info(f"✅ Test 1 passed: Granted Shardplate with {character.shardplate_hp_maximum} HP")

    # Test 2: Apply damage to Shardplate
    result = manager.damage_shardplate(char_id, 20)
    assert not result["shattered"], "Shardplate should not be shattered yet"
    assert result["hp_current"] == 55, f"Expected 55 HP remaining, got {result['hp_current']}"
    assert character.shardplate_hp_current == 55, "Character HP should be updated"
    logger.info(f"✅ Test 2 passed: Shardplate damaged to {result['hp_current']} HP")

    # Test 3: Shatter Shardplate (reduce to 0 HP)
    result = manager.damage_shardplate(char_id, 60)
    assert result["shattered"], "Shardplate should be shattered"
    assert result["hp_current"] == 0, "Shardplate HP should be 0"
    logger.info(f"✅ Test 3 passed: Shardplate shattered")

    # Test 4: Repair Shardplate (partial)
    success = manager.repair_shardplate(char_id, amount=30)
    assert success, "Failed to repair Shardplate"
    assert character.shardplate_hp_current == 30, f"Expected 30 HP, got {character.shardplate_hp_current}"
    logger.info(f"✅ Test 4 passed: Partially repaired to {character.shardplate_hp_current} HP")

    # Test 5: Full repair
    success = manager.repair_shardplate(char_id, amount=None)  # None = full repair
    assert success, "Failed to fully repair Shardplate"
    assert character.shardplate_hp_current == 75, "Shardplate should be at full HP"
    logger.info(f"✅ Test 5 passed: Fully repaired to {character.shardplate_hp_current} HP")

    logger.info("✅ All Shardplate tests passed!\n")


def test_backward_compatibility():
    """Test auto-migration from investiture_points to stormlight"""
    logger.info("🧪 Testing backward compatibility (investiture_points migration)...")

    manager = CharacterManager()

    # Create character with old investiture_points format
    old_radiant_data = {
        "character_id": "renarin",
        "name": "Renarin Kholin",
        "level": 6,
        "ability_scores": {"strength": 10, "dexterity": 12, "constitution": 14, "intelligence": 16, "wisdom": 14, "charisma": 10},
        "character_class": "Radiant",
        "radiant_order": "Truthwatcher",
        "ideal_level": 2,
        "investiture_points": {"current": 8, "maximum": 12}  # Old format
        # NOTE: No stormlight_current or stormlight_capacity
    }

    char_id = manager.add_character(old_radiant_data)
    character = manager.characters[char_id]

    # Test: Verify auto-migration happened
    assert character.stormlight_current == 8, f"Expected migrated current 8, got {character.stormlight_current}"
    assert character.stormlight_capacity == 12, f"Expected migrated capacity 12, got {character.stormlight_capacity}"
    logger.info(f"✅ Backward compatibility test passed: Migrated investiture_points to stormlight")

    # Test: Verify capacity auto-calculation for Radiants without explicit values
    radiant_no_investiture = {
        "character_id": "teft",
        "name": "Teft",
        "level": 4,
        "ability_scores": {"strength": 14, "dexterity": 12, "constitution": 14, "intelligence": 10, "wisdom": 12, "charisma": 10},
        "character_class": "Radiant",
        "radiant_order": "Windrunner",
        "ideal_level": 2
        # NOTE: No stormlight or investiture_points at all
    }

    char_id2 = manager.add_character(radiant_no_investiture)
    character2 = manager.characters[char_id2]

    assert character2.stormlight_capacity == 8, f"Expected auto-calculated capacity 8 (4×2), got {character2.stormlight_capacity}"
    logger.info(f"✅ Auto-calculation test passed: Calculated stormlight_capacity = {character2.stormlight_capacity}")

    logger.info("✅ All backward compatibility tests passed!\n")


def test_surgebinding_level():
    """Test surgebinding_level derivation from ideal_level"""
    logger.info("🧪 Testing surgebinding_level derivation...")

    manager = CharacterManager()

    # Create Radiant with ideal_level but no explicit surgebinding_level
    radiant_data = {
        "character_id": "lift",
        "name": "Lift",
        "level": 5,
        "ability_scores": {"strength": 10, "dexterity": 18, "constitution": 14, "intelligence": 8, "wisdom": 12, "charisma": 14},
        "character_class": "Radiant",
        "radiant_order": "Edgedancer",
        "ideal_level": 2
        # NOTE: No surgebinding_level specified
    }

    char_id = manager.add_character(radiant_data)
    character = manager.characters[char_id]

    # Test: Verify auto-derivation from ideal_level
    assert character.surgebinding_level == 2, f"Expected surgebinding_level 2 (from ideal_level), got {character.surgebinding_level}"
    logger.info(f"✅ Surgebinding level derivation test passed: surgebinding_level = {character.surgebinding_level}")

    logger.info("✅ All surgebinding level tests passed!\n")


def run_all_tests():
    """Run comprehensive Roshar combat integration test suite"""
    logger.info("=" * 70)
    logger.info("🚀 STARTING ROSHAR COMBAT INTEGRATION TESTS (Combat Plan v4.0)")
    logger.info("=" * 70 + "\n")

    try:
        # Run all test categories
        test_stormlight_tracking()
        test_passive_stormlight_healing()
        test_shardblade_mechanics()
        test_shardplate_mechanics()
        test_backward_compatibility()
        test_surgebinding_level()

        logger.info("=" * 70)
        logger.info("✅ ALL ROSHAR COMBAT TESTS PASSED (6/6 test categories)")
        logger.info("=" * 70)
        logger.info("\n📊 Test Summary:")
        logger.info("   ✅ Stormlight tracking and consumption")
        logger.info("   ✅ Passive Stormlight healing (1 HP per sphere)")
        logger.info("   ✅ Shardblade summoning/dismissal")
        logger.info("   ✅ Shardplate HP tracking and repair")
        logger.info("   ✅ Backward compatibility (investiture_points migration)")
        logger.info("   ✅ Surgebinding level auto-derivation")
        logger.info("\n🎯 CharacterManager is ready for Combat Plan v4.0 Phase 3 implementation!")

        return True

    except AssertionError as e:
        logger.error(f"❌ TEST FAILED: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
