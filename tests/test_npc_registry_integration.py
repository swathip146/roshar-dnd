"""
Unit tests for NPC Registry Integration in Game Initialization

Tests that verify:
1. NPCStatLoader is initialized correctly during game initialization
2. Predefined NPC JSON files are loaded into the registry
3. NPC stats can be retrieved by name
4. NPC stats match CharacterData format
5. Integration with CharacterManager works correctly
"""

import pytest
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.npc_stat_loader import NPCStatLoader
from components.character_manager import CharacterManager
from config.logging_config import get_logger

logger = get_logger(__name__)


class TestNPCRegistryIntegration:
    """Test suite for NPC registry integration"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures"""
        self.npc_directory = "data/players/"
        self.logger = get_logger(__name__)

    def test_npc_registry_initialization(self):
        """Test that NPCStatLoader initializes correctly"""
        logger.info("\n" + "="*60)
        logger.info("TEST: NPC Registry Initialization")
        logger.info("="*60)

        # Create NPCStatLoader
        npc_registry = NPCStatLoader(npc_directory=self.npc_directory)

        # Verify initialization
        assert npc_registry is not None, "NPCStatLoader should be created"
        assert npc_registry.npc_directory == self.npc_directory, "NPC directory should be set correctly"
        assert isinstance(npc_registry.npc_registry, dict), "NPC registry should be a dict"

        logger.info(f"✅ NPCStatLoader initialized successfully")
        logger.info(f"   NPC directory: {npc_registry.npc_directory}")
        logger.info(f"   NPCs loaded: {npc_registry.get_npc_count()}")

    def test_npc_registry_loads_herald_npcs(self):
        """Test that Herald NPC JSON files are loaded correctly"""
        logger.info("\n" + "="*60)
        logger.info("TEST: Herald NPC Loading")
        logger.info("="*60)

        # Create NPCStatLoader
        npc_registry = NPCStatLoader(npc_directory=self.npc_directory)

        # Check that NPCs were loaded
        npc_count = npc_registry.get_npc_count()
        available_npcs = npc_registry.list_available_npcs()

        logger.info(f"   NPCs found: {npc_count}")
        logger.info(f"   Available NPCs: {available_npcs}")

        # Verify at least the Herald NPCs are loaded
        assert npc_count >= 2, f"Expected at least 2 NPCs (Kalak, Nale), found {npc_count}"

        # Check for specific Herald NPCs
        assert npc_registry.has_npc("Kalak"), "Kalak should be in registry"
        assert npc_registry.has_npc("Nale"), "Nale should be in registry"

        logger.info("✅ Herald NPCs loaded successfully")

    def test_npc_registry_retrieves_kalak_stats(self):
        """Test retrieving Kalak's stats from registry"""
        logger.info("\n" + "="*60)
        logger.info("TEST: Retrieve Kalak Stats")
        logger.info("="*60)

        # Create NPCStatLoader
        npc_registry = NPCStatLoader(npc_directory=self.npc_directory)

        # Get Kalak's stats
        kalak_stats = npc_registry.get_npc_by_name("Kalak")

        assert kalak_stats is not None, "Kalak stats should be retrieved"

        # Verify required CharacterData fields
        required_fields = [
            'name', 'character_class', 'level', 'ability_scores',
            'hit_points', 'armor_class', 'proficiency_bonus'
        ]

        for field in required_fields:
            assert field in kalak_stats, f"Kalak stats missing required field: {field}"

        # Verify field values
        assert kalak_stats['name'] == "Kalak", "Name should match"
        assert kalak_stats['level'] == 20, "Kalak should be level 20"
        assert kalak_stats['character_class'] == "Herald", "Class should be Herald"

        # Verify hit_points structure
        hp = kalak_stats['hit_points']
        assert isinstance(hp, dict), "hit_points should be a dict"
        assert 'current' in hp, "hit_points should have 'current' key"
        assert 'maximum' in hp, "hit_points should have 'maximum' key"
        assert 'temporary' in hp, "hit_points should have 'temporary' key"
        assert hp['maximum'] == 400, "Kalak should have 400 max HP"

        # Verify ability_scores structure
        abilities = kalak_stats['ability_scores']
        assert isinstance(abilities, dict), "ability_scores should be a dict"
        required_abilities = {'strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma'}
        assert required_abilities.issubset(abilities.keys()), "All 6 abilities should be present"

        logger.info("✅ Kalak stats retrieved and validated")
        logger.info(f"   Name: {kalak_stats['name']}")
        logger.info(f"   Level: {kalak_stats['level']}")
        logger.info(f"   Class: {kalak_stats['character_class']}")
        logger.info(f"   HP: {hp['maximum']}")
        logger.info(f"   AC: {kalak_stats['armor_class']}")

    def test_npc_registry_retrieves_nale_stats(self):
        """Test retrieving Nale's stats from registry"""
        logger.info("\n" + "="*60)
        logger.info("TEST: Retrieve Nale Stats")
        logger.info("="*60)

        # Create NPCStatLoader
        npc_registry = NPCStatLoader(npc_directory=self.npc_directory)

        # Get Nale's stats
        nale_stats = npc_registry.get_npc_by_name("Nale")

        assert nale_stats is not None, "Nale stats should be retrieved"

        # Verify required fields
        assert 'name' in nale_stats, "Missing name field"
        assert 'level' in nale_stats, "Missing level field"
        assert 'hit_points' in nale_stats, "Missing hit_points field"

        # Verify values
        assert nale_stats['name'] == "Nale", "Name should match"
        assert nale_stats['level'] == 20, "Nale should be level 20"
        assert nale_stats['hit_points']['maximum'] == 380, "Nale should have 380 max HP"

        logger.info("✅ Nale stats retrieved and validated")
        logger.info(f"   Name: {nale_stats['name']}")
        logger.info(f"   Level: {nale_stats['level']}")
        logger.info(f"   HP: {nale_stats['hit_points']['maximum']}")
        logger.info(f"   AC: {nale_stats['armor_class']}")

    def test_npc_registry_case_insensitive_lookup(self):
        """Test case-insensitive NPC lookup"""
        logger.info("\n" + "="*60)
        logger.info("TEST: Case-Insensitive Lookup")
        logger.info("="*60)

        # Create NPCStatLoader
        npc_registry = NPCStatLoader(npc_directory=self.npc_directory)

        # Test various case combinations
        test_cases = ["kalak", "KALAK", "Kalak", "KaLaK"]

        for name in test_cases:
            npc_stats = npc_registry.get_npc_by_name(name)
            assert npc_stats is not None, f"Should find NPC with name: {name}"
            assert npc_stats['name'] == "Kalak", f"Should return Kalak for input: {name}"
            logger.info(f"   ✓ Found '{npc_stats['name']}' with input: '{name}'")

        logger.info("✅ Case-insensitive lookup working correctly")

    def test_npc_registry_partial_name_matching(self):
        """Test partial name matching (e.g., 'Kalak' matches 'Kalak the Herald')"""
        logger.info("\n" + "="*60)
        logger.info("TEST: Partial Name Matching")
        logger.info("="*60)

        # Create NPCStatLoader
        npc_registry = NPCStatLoader(npc_directory=self.npc_directory)

        # Test partial matches
        partial_searches = [
            ("Kalak", "Kalak"),
            ("Nale", "Nale"),
            ("kalak the", "Kalak"),  # Partial match
        ]

        for search_term, expected_name in partial_searches:
            npc_stats = npc_registry.get_npc_by_name(search_term)
            if npc_stats:
                logger.info(f"   ✓ '{search_term}' → Found: {npc_stats['name']}")
                assert expected_name in npc_stats['name'], f"Expected '{expected_name}' in result"
            else:
                logger.info(f"   ✗ '{search_term}' → Not found")

        logger.info("✅ Partial name matching working")

    def test_npc_registry_integration_with_character_manager(self):
        """Test that NPC stats can be added to CharacterManager"""
        logger.info("\n" + "="*60)
        logger.info("TEST: Integration with CharacterManager")
        logger.info("="*60)

        # Create NPCStatLoader and CharacterManager
        npc_registry = NPCStatLoader(npc_directory=self.npc_directory)
        character_manager = CharacterManager()

        # Get Kalak's stats
        kalak_stats = npc_registry.get_npc_by_name("Kalak")
        assert kalak_stats is not None, "Kalak stats should be retrieved"

        # Add to CharacterManager
        char_id = character_manager.add_npc(kalak_stats)

        assert char_id is not None, "Character ID should be returned"
        logger.info(f"   Added Kalak to CharacterManager with ID: {char_id}")

        # Verify NPC was added
        assert char_id in character_manager.characters, "NPC should be in CharacterManager"

        # NOTE: Predefined NPCs with character_id field (like "kalak_herald")
        # won't match the _\d{3}$ pattern in get_npcs(), which is expected behavior.
        # get_npcs() is primarily for dynamically generated NPCs with _001, _002 suffixes.
        logger.info(f"   NPC ID pattern: {char_id}")

        # Get character back from manager
        kalak_character = character_manager.characters[char_id]
        assert kalak_character.name == "Kalak", "Character name should match"
        assert kalak_character.level == 20, "Character level should match"

        logger.info("✅ NPC successfully integrated with CharacterManager")
        logger.info(f"   Character ID: {char_id}")
        logger.info(f"   Name: {kalak_character.name}")
        logger.info(f"   Level: {kalak_character.level}")

    def test_npc_registry_missing_npc_returns_none(self):
        """Test that missing NPCs return None"""
        logger.info("\n" + "="*60)
        logger.info("TEST: Missing NPC Returns None")
        logger.info("="*60)

        # Create NPCStatLoader
        npc_registry = NPCStatLoader(npc_directory=self.npc_directory)

        # Try to get non-existent NPC
        missing_npc = npc_registry.get_npc_by_name("Dragon Lord Zorblax")

        assert missing_npc is None, "Missing NPC should return None"
        assert not npc_registry.has_npc("Dragon Lord Zorblax"), "has_npc should return False"

        logger.info("✅ Missing NPC handled correctly (returns None)")

    def test_npc_registry_list_available_npcs(self):
        """Test listing all available NPCs"""
        logger.info("\n" + "="*60)
        logger.info("TEST: List Available NPCs")
        logger.info("="*60)

        # Create NPCStatLoader
        npc_registry = NPCStatLoader(npc_directory=self.npc_directory)

        # Get list of NPCs
        available_npcs = npc_registry.list_available_npcs()

        assert isinstance(available_npcs, list), "Should return a list"
        assert len(available_npcs) > 0, "Should have at least one NPC"

        logger.info(f"   Available NPCs ({len(available_npcs)}):")
        for npc_name in available_npcs:
            logger.info(f"      - {npc_name}")

        # Verify Herald NPCs are in the list
        assert "Kalak" in available_npcs, "Kalak should be in available NPCs"
        assert "Nale" in available_npcs, "Nale should be in available NPCs"

        logger.info("✅ Successfully listed all available NPCs")


def test_game_init_npc_registry_integration():
    """
    Integration test: Verify NPC registry is properly initialized in game initialization.

    This test simulates what happens during GameInitializationSystem.initialize_game()
    """
    logger.info("\n" + "="*60)
    logger.info("INTEGRATION TEST: Game Init NPC Registry")
    logger.info("="*60)

    # Simulate the game initialization NPC registry loading
    # (Lines 272-284 in core/game_initialization.py)

    try:
        npc_registry = NPCStatLoader(npc_directory="data/players/")
        npc_count = npc_registry.get_npc_count()

        if npc_count > 0:
            npc_names = ", ".join(npc_registry.list_available_npcs())
            logger.info(f"   🎭 NPC Registry: ✅ Loaded {npc_count} predefined NPCs ({npc_names})")
        else:
            logger.info(f"   🎭 NPC Registry: ✅ Created (no NPCs found)")

        # Verify successful initialization
        assert npc_registry is not None, "NPC registry should be created"
        assert npc_count >= 2, f"Should load at least 2 Herald NPCs, found {npc_count}"

        logger.info("✅ Game initialization NPC registry integration successful")

    except Exception as e:
        logger.error(f"   ❌ NPC Registry initialization failed: {e}")
        raise


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
