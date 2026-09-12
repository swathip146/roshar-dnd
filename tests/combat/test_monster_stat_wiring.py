"""
Test Monster Stat-Block Wiring

Verifies that damage resistances/vulnerabilities/immunities and monster senses
are correctly applied to dnd_engine entities.

Tests:
1. Damage resistance (2× damage → 0.5× after resistance)
2. Damage vulnerability (1× damage → 2× after vulnerability)
3. Damage immunity (any damage → 0 after immunity)
4. Darkvision sense wiring
5. HP sync invariant (total_hp <= max_hp always holds)
"""

import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from components.character_manager import CharacterManager, CharacterData
from components.game_engine import GameEngine
from components.dnd_engine_wrapper import DnDEngineWrapper, _parse_damage_type
from dnd.core.modifiers import DamageType, ResistanceStatus
from dnd.blocks.sensory import SensesType
from config.logging_config import get_logger

logger = get_logger(__name__)


class TestMonsterStatWiring:
    """Test suite for monster resistance/vulnerability/immunity and senses"""

    @pytest.fixture
    def game_components(self):
        """Create game components for testing"""
        logger.info("=" * 60)
        logger.info("🧪 TEST: Setting up game components")
        logger.info("=" * 60)

        char_manager = CharacterManager()
        game_engine = GameEngine()
        dnd_wrapper = DnDEngineWrapper(game_engine, char_manager)

        logger.info("✅ Game components created")
        return {
            "char_manager": char_manager,
            "game_engine": game_engine,
            "dnd_wrapper": dnd_wrapper
        }

    def test_damage_type_parsing(self):
        """Test damage type string parsing"""
        logger.info("")
        logger.info("=" * 60)
        logger.info("🧪 TEST: Damage Type Parsing")
        logger.info("=" * 60)

        # Test simple types
        assert _parse_damage_type("acid") == DamageType.ACID
        assert _parse_damage_type("POISON") == DamageType.POISON
        assert _parse_damage_type("Fire") == DamageType.FIRE
        assert _parse_damage_type(" slashing ") == DamageType.SLASHING

        # Test complex conditions (should return None)
        assert _parse_damage_type("bludgeoning from nonmagical weapons") is None
        assert _parse_damage_type("piercing, slashing") is None
        assert _parse_damage_type("bludgeoning, piercing, and slashing from nonmagical attacks") is None

        # Test invalid
        assert _parse_damage_type("") is None
        assert _parse_damage_type("foobar") is None

        logger.info("✅ TEST PASSED: Damage type parsing works correctly")

    def test_damage_immunity(self, game_components):
        """Test that damage immunity reduces damage to 0"""
        logger.info("")
        logger.info("=" * 60)
        logger.info("🧪 TEST: Damage Immunity")
        logger.info("=" * 60)

        char_manager = game_components["char_manager"]
        dnd_wrapper = game_components["dnd_wrapper"]

        # Create a character with poison immunity (like a zombie)
        zombie_data = {
            "character_id": "test_zombie",
            "name": "Test Zombie",
            "level": 3,
            "character_class": "Undead",
            "race": "Undead",
            "background": "Reanimated",
            "ability_scores": {
                "strength": 13,
                "dexterity": 6,
                "constitution": 16,
                "intelligence": 3,
                "wisdom": 6,
                "charisma": 5
            },
            "hit_points": {
                "current": 22,
                "maximum": 22,
                "temporary": 0
            },
            "armor_class": 8,
            "proficiency_bonus": 2,
            "speed": 20,
            "skills": {},
            "saving_throw_proficiencies": ["wisdom"],
            "expertise_skills": [],
            "damage_immunities": ["poison"],  # Zombie is immune to poison
            "damage_resistances": [],
            "damage_vulnerabilities": [],
            "senses": {}
        }

        char_id = char_manager.add_character(zombie_data)
        logger.info(f"✅ Created zombie: {zombie_data['name']} (immune to poison)")

        # Sync to dnd_engine
        dnd_wrapper._sync_characters_to_entities()
        entity = dnd_wrapper.entities[char_id]

        # Check immunity was applied
        resistance_status = entity.health.get_resistance(DamageType.POISON)
        logger.info(f"   Poison resistance status: {resistance_status}")
        assert resistance_status == ResistanceStatus.IMMUNITY, \
            f"Expected IMMUNITY, got {resistance_status}"

        # Apply poison damage
        initial_hp = entity.health.get_total_hit_points(entity.ability_scores.constitution.modifier)
        logger.info(f"   Initial HP: {initial_hp}")

        damage_dealt = entity.health.take_damage(
            damage=10,
            damage_type=DamageType.POISON,
            source_entity_uuid=entity.uuid
        )

        final_hp = entity.health.get_total_hit_points(entity.ability_scores.constitution.modifier)
        logger.info(f"   Applied 10 poison damage")
        logger.info(f"   Damage actually dealt: {damage_dealt}")
        logger.info(f"   Final HP: {final_hp}")

        # Immunity should reduce damage to 0
        assert damage_dealt == 0, \
            f"Expected 0 damage (immune), but {damage_dealt} damage was dealt"
        assert final_hp == initial_hp, \
            f"HP changed from {initial_hp} to {final_hp}, but should be unchanged (immune)"

        logger.info("✅ TEST PASSED: Poison immunity works correctly")

    def test_damage_resistance(self, game_components):
        """Test that damage resistance reduces damage by half"""
        logger.info("")
        logger.info("=" * 60)
        logger.info("🧪 TEST: Damage Resistance")
        logger.info("=" * 60)

        char_manager = game_components["char_manager"]
        dnd_wrapper = game_components["dnd_wrapper"]

        # Create a character with fire resistance (like a tiefling)
        tiefling_data = {
            "character_id": "test_tiefling",
            "name": "Test Tiefling",
            "level": 1,
            "character_class": "Fighter",
            "race": "Tiefling",
            "background": "Soldier",
            "ability_scores": {
                "strength": 16,
                "dexterity": 14,
                "constitution": 15,
                "intelligence": 10,
                "wisdom": 12,
                "charisma": 13
            },
            "hit_points": {
                "current": 12,
                "maximum": 12,
                "temporary": 0
            },
            "armor_class": 16,
            "proficiency_bonus": 2,
            "speed": 30,
            "skills": {},
            "saving_throw_proficiencies": ["strength", "constitution"],
            "expertise_skills": [],
            "damage_immunities": [],
            "damage_resistances": ["fire"],  # Tiefling resists fire
            "damage_vulnerabilities": [],
            "senses": {}
        }

        char_id = char_manager.add_character(tiefling_data)
        logger.info(f"✅ Created tiefling: {tiefling_data['name']} (resistant to fire)")

        # Sync to dnd_engine
        dnd_wrapper._sync_characters_to_entities()
        entity = dnd_wrapper.entities[char_id]

        # Check resistance was applied
        resistance_status = entity.health.get_resistance(DamageType.FIRE)
        logger.info(f"   Fire resistance status: {resistance_status}")
        assert resistance_status == ResistanceStatus.RESISTANCE, \
            f"Expected RESISTANCE, got {resistance_status}"

        # Apply fire damage
        initial_hp = entity.health.get_total_hit_points(entity.ability_scores.constitution.modifier)
        logger.info(f"   Initial HP: {initial_hp}")

        damage_dealt = entity.health.take_damage(
            damage=10,
            damage_type=DamageType.FIRE,
            source_entity_uuid=entity.uuid
        )

        final_hp = entity.health.get_total_hit_points(entity.ability_scores.constitution.modifier)
        logger.info(f"   Applied 10 fire damage")
        logger.info(f"   Damage actually dealt: {damage_dealt}")
        logger.info(f"   Final HP: {final_hp}")

        # Resistance should halve damage (10 → 5)
        assert damage_dealt == 5, \
            f"Expected 5 damage (half of 10), but {damage_dealt} damage was dealt"
        assert final_hp == initial_hp - 5, \
            f"HP should be {initial_hp - 5}, but is {final_hp}"

        logger.info("✅ TEST PASSED: Fire resistance works correctly")

    def test_damage_vulnerability(self, game_components):
        """Test that damage vulnerability doubles damage"""
        logger.info("")
        logger.info("=" * 60)
        logger.info("🧪 TEST: Damage Vulnerability")
        logger.info("=" * 60)

        char_manager = game_components["char_manager"]
        dnd_wrapper = game_components["dnd_wrapper"]

        # Create a character with bludgeoning vulnerability (like a skeleton)
        skeleton_data = {
            "character_id": "test_skeleton",
            "name": "Test Skeleton",
            "level": 1,
            "character_class": "Undead",
            "race": "Undead",
            "background": "Reanimated",
            "ability_scores": {
                "strength": 10,
                "dexterity": 14,
                "constitution": 15,
                "intelligence": 6,
                "wisdom": 8,
                "charisma": 5
            },
            "hit_points": {
                "current": 13,
                "maximum": 13,
                "temporary": 0
            },
            "armor_class": 13,
            "proficiency_bonus": 2,
            "speed": 30,
            "skills": {},
            "saving_throw_proficiencies": [],
            "expertise_skills": [],
            "damage_immunities": [],
            "damage_resistances": [],
            "damage_vulnerabilities": ["bludgeoning"],  # Skeleton vulnerable to bludgeoning
            "senses": {}
        }

        char_id = char_manager.add_character(skeleton_data)
        logger.info(f"✅ Created skeleton: {skeleton_data['name']} (vulnerable to bludgeoning)")

        # Sync to dnd_engine
        dnd_wrapper._sync_characters_to_entities()
        entity = dnd_wrapper.entities[char_id]

        # Check vulnerability was applied
        resistance_status = entity.health.get_resistance(DamageType.BLUDGEONING)
        logger.info(f"   Bludgeoning resistance status: {resistance_status}")
        assert resistance_status == ResistanceStatus.VULNERABILITY, \
            f"Expected VULNERABILITY, got {resistance_status}"

        # Apply bludgeoning damage
        initial_hp = entity.health.get_total_hit_points(entity.ability_scores.constitution.modifier)
        logger.info(f"   Initial HP: {initial_hp}")

        damage_dealt = entity.health.take_damage(
            damage=6,
            damage_type=DamageType.BLUDGEONING,
            source_entity_uuid=entity.uuid
        )

        final_hp = entity.health.get_total_hit_points(entity.ability_scores.constitution.modifier)
        logger.info(f"   Applied 6 bludgeoning damage")
        logger.info(f"   Damage actually dealt: {damage_dealt}")
        logger.info(f"   Final HP: {final_hp}")

        # Vulnerability should double damage (6 → 12)
        assert damage_dealt == 12, \
            f"Expected 12 damage (double 6), but {damage_dealt} damage was dealt"
        assert final_hp == initial_hp - 12, \
            f"HP should be {initial_hp - 12}, but is {final_hp}"

        logger.info("✅ TEST PASSED: Bludgeoning vulnerability works correctly")

    def test_darkvision_sense_wiring(self, game_components):
        """Test that darkvision sense is correctly wired to entity"""
        logger.info("")
        logger.info("=" * 60)
        logger.info("🧪 TEST: Darkvision Sense Wiring")
        logger.info("=" * 60)

        char_manager = game_components["char_manager"]
        dnd_wrapper = game_components["dnd_wrapper"]

        # Create a character with darkvision (like a dwarf)
        dwarf_data = {
            "character_id": "test_dwarf",
            "name": "Test Dwarf",
            "level": 1,
            "character_class": "Fighter",
            "race": "Dwarf",
            "background": "Soldier",
            "ability_scores": {
                "strength": 16,
                "dexterity": 12,
                "constitution": 16,
                "intelligence": 10,
                "wisdom": 13,
                "charisma": 8
            },
            "hit_points": {
                "current": 13,
                "maximum": 13,
                "temporary": 0
            },
            "armor_class": 16,
            "proficiency_bonus": 2,
            "speed": 25,
            "skills": {},
            "saving_throw_proficiencies": ["strength", "constitution"],
            "expertise_skills": [],
            "damage_immunities": [],
            "damage_resistances": [],
            "damage_vulnerabilities": [],
            "senses": {"darkvision": "60 ft."}  # Dwarf has darkvision
        }

        char_id = char_manager.add_character(dwarf_data)
        logger.info(f"✅ Created dwarf: {dwarf_data['name']} (darkvision 60 ft.)")

        # Sync to dnd_engine
        dnd_wrapper._sync_characters_to_entities()
        entity = dnd_wrapper.entities[char_id]

        # Check darkvision was applied
        has_darkvision = SensesType.DARKVISION in entity.senses.extra_senses
        logger.info(f"   Entity senses: {entity.senses.extra_senses}")
        logger.info(f"   Has darkvision: {has_darkvision}")

        assert has_darkvision, \
            f"Expected DARKVISION in entity senses, but got {entity.senses.extra_senses}"

        logger.info("✅ TEST PASSED: Darkvision sense wired correctly")

    def test_hp_sync_invariant(self, game_components):
        """Test that HP sync invariant (total_hp <= max_hp) always holds"""
        logger.info("")
        logger.info("=" * 60)
        logger.info("🧪 TEST: HP Sync Invariant")
        logger.info("=" * 60)

        char_manager = game_components["char_manager"]
        dnd_wrapper = game_components["dnd_wrapper"]

        # Create multiple characters with different HP configurations
        test_cases = [
            {
                "name": "Low HP Character",
                "level": 1,
                "constitution": 10,
                "max_hp": 8,
                "current_hp": 3
            },
            {
                "name": "High HP Character",
                "level": 5,
                "constitution": 16,
                "max_hp": 45,
                "current_hp": 30
            },
            {
                "name": "Full HP Character",
                "level": 3,
                "constitution": 14,
                "max_hp": 25,
                "current_hp": 25
            },
            {
                "name": "Odd HP Character",
                "level": 2,
                "constitution": 13,
                "max_hp": 15,
                "current_hp": 7
            }
        ]

        for i, test_case in enumerate(test_cases):
            char_data = {
                "character_id": f"test_hp_sync_{i}",
                "name": test_case["name"],
                "level": test_case["level"],
                "character_class": "Fighter",
                "race": "Human",
                "background": "Soldier",
                "ability_scores": {
                    "strength": 14,
                    "dexterity": 14,
                    "constitution": test_case["constitution"],
                    "intelligence": 10,
                    "wisdom": 12,
                    "charisma": 10
                },
                "hit_points": {
                    "current": test_case["current_hp"],
                    "maximum": test_case["max_hp"],
                    "temporary": 0
                },
                "armor_class": 16,
                "proficiency_bonus": 2,
                "speed": 30,
                "skills": {},
                "saving_throw_proficiencies": ["strength", "constitution"],
                "expertise_skills": []
            }

            char_id = char_manager.add_character(char_data)
            logger.info(f"   Testing: {test_case['name']} "
                       f"({test_case['current_hp']}/{test_case['max_hp']} HP)")

            # Sync to dnd_engine
            dnd_wrapper._sync_characters_to_entities()
            entity = dnd_wrapper.entities[char_id]

            # Check HP invariant
            con_mod = entity.ability_scores.constitution.modifier
            entity_max_hp = dnd_wrapper.get_entity_max_hp(entity)
            entity_total_hp = entity.health.get_total_hit_points(con_mod)

            logger.info(f"      Entity max HP: {entity_max_hp}")
            logger.info(f"      Entity total HP: {entity_total_hp}")
            logger.info(f"      Damage taken: {entity.health.damage_taken}")

            # CRITICAL ASSERTION
            assert entity_total_hp <= entity_max_hp, \
                f"HP INVARIANT VIOLATED: total_hp ({entity_total_hp}) > max_hp ({entity_max_hp})"
            assert entity_total_hp >= 0, \
                f"HP INVARIANT VIOLATED: total_hp ({entity_total_hp}) < 0"

            logger.info(f"      ✅ Invariant holds: {entity_total_hp} <= {entity_max_hp}")

        logger.info("")
        logger.info(f"✅ TEST PASSED: HP invariant holds for all {len(test_cases)} cases")


def run_tests():
    """Run all tests with detailed logging"""
    logger.info("=" * 60)
    logger.info("🧪 MONSTER STAT WIRING TEST SUITE")
    logger.info("=" * 60)

    # Run pytest with verbose output
    pytest_args = [
        __file__,
        "-v",  # Verbose
        "-s",  # Show print statements
        "--tb=short",  # Short traceback
        "--log-cli-level=INFO"  # Show logs
    ]

    exit_code = pytest.main(pytest_args)

    logger.info("")
    logger.info("=" * 60)
    if exit_code == 0:
        logger.info("✅ ALL TESTS PASSED")
    else:
        logger.info("❌ SOME TESTS FAILED")
    logger.info("=" * 60)

    return exit_code


if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)
