"""
Unit tests for DnDEngineWrapper

Tests the integration between Roshar D&D system and dnd_engine.
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from components.dnd_engine_wrapper import DnDEngineWrapper, create_dnd_engine_wrapper
from components.game_engine import GameEngine
from components.character_manager import CharacterManager
from components.campaign_config import CampaignConfig
from components.policy import PolicyProfile


@pytest.fixture
def test_config():
    """Create minimal campaign config for testing."""
    from dataclasses import dataclass
    from typing import List, Dict

    @dataclass
    class TestNPC:
        name: str

    @dataclass
    class TestLocation:
        name: str

    @dataclass
    class TestCampaignConfig:
        name: str = "Test Campaign"
        theme: str = "Testing"
        story: str = "Test story"
        difficulty: str = "Medium"
        starting_location: str = "Test Location"
        key_npcs: List = None
        locations: List = None
        quests: List = None
        level_range: tuple = (1, 3)

        def __post_init__(self):
            if self.key_npcs is None:
                self.key_npcs = []
            if self.locations is None:
                self.locations = []
            if self.quests is None:
                self.quests = []

    return TestCampaignConfig()


@pytest.fixture
def character_manager():
    """Create CharacterManager with test character."""
    manager = CharacterManager()

    # Add test character (Aggi from integration tests)
    manager.add_character({
        "name": "Aggi",
        "level": 1,
        "character_class": "Lightweaver",
        "race": "Human",
        "background": "Entertainer",
        "radiant_order": "Lightweaver",
        "ability_scores": {
            "strength": 10,
            "dexterity": 16,
            "constitution": 12,
            "intelligence": 14,
            "wisdom": 13,
            "charisma": 17
        },
        "hit_points": {"current": 25, "maximum": 25, "temporary": 0},
        "armor_class": 13,
        "skills": {
            "persuasion": True,
            "deception": True,
            "insight": True
        },
        "expertise_skills": ["deception"],
        "conditions": [],
        "saving_throw_proficiencies": ["wisdom", "charisma"]
    })

    return manager


@pytest.fixture
def game_engine(test_config):
    """Create GameEngine with test config."""
    engine = GameEngine(
        policy_profile=PolicyProfile.HOUSE,
        campaign_config=test_config
    )
    return engine


@pytest.fixture
def wrapper(game_engine, character_manager):
    """Create DnDEngineWrapper."""
    # Add character to game engine as well
    for char_id, char_data in character_manager.characters.items():
        game_engine.character_manager = character_manager
        break

    return create_dnd_engine_wrapper(
        game_engine=game_engine,
        character_manager=character_manager
    )


def test_wrapper_initialization(wrapper):
    """Test that wrapper initializes and syncs characters."""
    assert len(wrapper.entities) == 1

    # Check that character was synced
    char_ids = list(wrapper.entities.keys())
    assert len(char_ids) > 0

    # Check entity has correct attributes
    entity = wrapper.entities[char_ids[0]]
    assert entity is not None
    assert entity.name == "Aggi"


def test_skill_check_execution(wrapper, character_manager):
    """Test skill check via dnd_engine."""
    # Get character ID
    char_id = list(character_manager.characters.keys())[0]

    result = wrapper.execute_skill_check(
        character_id=char_id,
        skill="persuasion",
        dc=15
    )

    assert "success" in result
    assert "roll" in result
    assert "natural_roll" in result
    assert result["dc"] == 15
    assert isinstance(result["success"], bool)
    assert isinstance(result["roll"], int)

    # Check roll is within valid range (1-20 + modifiers)
    assert 1 <= result["natural_roll"] <= 20


def test_attack_execution(wrapper, character_manager):
    """Test attack via dnd_engine."""
    # Add target enemy
    character_manager.add_character({
        "name": "Test Enemy",
        "level": 1,
        "character_class": "Barbarian",
        "race": "Orc",
        "background": "Soldier",
        "armor_class": 14,
        "hit_points": {"current": 20, "maximum": 20, "temporary": 0},
        "ability_scores": {
            "strength": 16,
            "dexterity": 10,
            "constitution": 14,
            "intelligence": 8,
            "wisdom": 10,
            "charisma": 8
        },
        "skills": {},
        "expertise_skills": [],
        "conditions": [],
        "saving_throw_proficiencies": ["strength", "constitution"]
    })

    # Re-sync to add new entity
    wrapper._sync_characters_to_entities()

    # Get character IDs
    char_ids = list(character_manager.characters.keys())
    attacker_id = char_ids[0]
    target_id = char_ids[1]

    result = wrapper.execute_attack(
        attacker_id=attacker_id,
        target_id=target_id,
        weapon="spear"
    )

    assert "hit" in result
    assert "damage" in result
    assert "attack_roll" in result
    assert "target_ac" in result
    assert isinstance(result["hit"], bool)

    # Check that damage is only applied on hit
    if result["hit"]:
        assert result["damage"] > 0
    else:
        assert result["damage"] == 0


def test_entity_sync_to_game_state(wrapper, character_manager):
    """Test that entity changes sync back to game state."""
    from dnd.core.events import DamageType

    # Get character ID
    char_id = list(character_manager.characters.keys())[0]

    # Get original HP
    original_hp = character_manager.characters[char_id].hit_points["current"]

    # Modify entity HP directly.
    # `take_damage` requires (damage, damage_type, source_entity_uuid) — calling it
    # with only the amount raised TypeError, so this test had been failing rather
    # than asserting anything about the sync it names.
    entity = wrapper.entities[char_id]
    entity.health.take_damage(5, DamageType.BLUDGEONING, entity.uuid)

    # Sync back
    wrapper._sync_entity_to_game_state(char_id)

    # Check that character manager was updated
    new_hp = character_manager.characters[char_id].hit_points["current"]
    assert new_hp == original_hp - 5


def test_invalid_character_id(wrapper):
    """Test error handling for invalid character ID."""
    result = wrapper.execute_skill_check(
        character_id="nonexistent",
        skill="athletics",
        dc=10
    )

    assert result["success"] == False
    assert "error" in result


def test_invalid_skill_name(wrapper, character_manager):
    """Test error handling for invalid skill name."""
    char_id = list(character_manager.characters.keys())[0]

    result = wrapper.execute_skill_check(
        character_id=char_id,
        skill="invalid_skill",
        dc=10
    )

    assert result["success"] == False
    assert "error" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
