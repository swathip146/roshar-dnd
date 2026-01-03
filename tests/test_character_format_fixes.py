"""
Test character format fixes for Phase 1 preparation.

Tests:
1. aggi.json loads correctly with new format
2. CharacterManager.add_character handles both int and dict hit_points
3. CharacterManager.add_npc supports both "class" and "character_class"
4. NPC generation creates correct character_id format
"""

import json
import pytest
from pathlib import Path
from components.character_manager import CharacterManager


def test_aggi_json_format():
    """Test that aggi.json has correct format"""
    aggi_path = Path(__file__).parent.parent / "data" / "aggi.json"

    with open(aggi_path, 'r') as f:
        aggi_data = json.load(f)

    # Check required fields exist
    assert "character_id" in aggi_data, "Missing character_id field"
    assert "ability_scores" in aggi_data, "Missing ability_scores (not stats)"
    assert "character_class" in aggi_data, "character_class field exists"

    # Check hit_points is dict format
    assert isinstance(aggi_data["hit_points"], dict), "hit_points should be dict"
    assert "current" in aggi_data["hit_points"], "hit_points missing current"
    assert "maximum" in aggi_data["hit_points"], "hit_points missing maximum"
    assert "temporary" in aggi_data["hit_points"], "hit_points missing temporary"

    # Check skills is dict
    assert isinstance(aggi_data["skills"], dict), "skills should be dict"

    print("✅ aggi.json format is correct")


def test_character_manager_with_aggi():
    """Test that CharacterManager can load aggi.json"""
    manager = CharacterManager()

    aggi_path = Path(__file__).parent.parent / "data" / "aggi.json"
    with open(aggi_path, 'r') as f:
        aggi_data = json.load(f)

    # Add character
    char_id = manager.add_character(aggi_data)

    assert char_id == "aggi"
    assert "aggi" in manager.characters

    character = manager.characters["aggi"]
    assert character.name == "Aggi"
    assert character.character_class == "Radiant"
    assert character.hit_points["current"] == 8
    assert character.hit_points["maximum"] == 8
    assert character.hit_points["temporary"] == 0

    print("✅ aggi.json loads correctly into CharacterManager")


def test_character_manager_hp_normalization():
    """Test that add_character normalizes hit_points from int to dict"""
    manager = CharacterManager()

    # Test with simple int (old format)
    char_data_int = {
        "name": "Test Character",
        "level": 1,
        "ability_scores": {"strength": 10, "dexterity": 10, "constitution": 10,
                          "intelligence": 10, "wisdom": 10, "charisma": 10},
        "hit_points": 15,  # Simple int
        "character_class": "Fighter"
    }

    char_id = manager.add_character(char_data_int)
    character = manager.characters[char_id]

    # Should be converted to dict
    assert isinstance(character.hit_points, dict)
    assert character.hit_points["current"] == 15
    assert character.hit_points["maximum"] == 15
    assert character.hit_points["temporary"] == 0

    print("✅ HP normalization from int to dict works")


def test_add_npc_with_class_field():
    """Test that add_npc supports 'class' field (backward compatibility)"""
    manager = CharacterManager()

    npc_data_old_format = {
        "name": "Goblin",
        "level": 1,
        "class": "Warrior",  # Old field name
        "race": "Goblin",
        "background": "Tribal",
        "ability_scores": {"strength": 8, "dexterity": 14, "constitution": 10,
                          "intelligence": 10, "wisdom": 8, "charisma": 8},
        "hit_points": {"maximum": 7, "current": 7, "temporary": 0},
        "armor_class": 15,
        "attacks": [{"name": "Scimitar", "damage_dice": "1d6"}],
        "challenge_rating": 0.25
    }

    npc_id = manager.add_npc(npc_data_old_format)

    assert npc_id.startswith("goblin_")
    assert npc_id.endswith("_001")

    npc = manager.characters[npc_id]
    assert npc.character_class == "Warrior"  # Converted from "class" to "character_class"
    assert npc.attacks == [{"name": "Scimitar", "damage_dice": "1d6"}]
    assert npc.challenge_rating == 0.25

    print("✅ add_npc backward compatibility works")


def test_add_npc_with_character_class_field():
    """Test that add_npc supports 'character_class' field (new format)"""
    manager = CharacterManager()

    npc_data_new_format = {
        "name": "Bandit",
        "level": 1,
        "character_class": "Rogue",  # New field name
        "race": "Human",
        "background": "Criminal",
        "ability_scores": {"strength": 11, "dexterity": 12, "constitution": 12,
                          "intelligence": 10, "wisdom": 10, "charisma": 10},
        "hit_points": {"maximum": 11, "current": 11, "temporary": 0},
        "armor_class": 12,
        "skills": {"stealth": True, "deception": True},
        "attacks": [],
        "challenge_rating": 0.125
    }

    npc_id = manager.add_npc(npc_data_new_format)

    assert npc_id.startswith("bandit_")

    npc = manager.characters[npc_id]
    assert npc.character_class == "Rogue"
    assert npc.skills == {"stealth": True, "deception": True}
    assert npc.challenge_rating == 0.125

    print("✅ add_npc with character_class works")


def test_npc_unique_ids():
    """Test that add_npc generates unique IDs"""
    manager = CharacterManager()

    npc_data = {
        "name": "Goblin",
        "level": 1,
        "character_class": "Warrior",
        "ability_scores": {"strength": 8, "dexterity": 14, "constitution": 10,
                          "intelligence": 10, "wisdom": 8, "charisma": 8},
        "hit_points": {"maximum": 7, "current": 7, "temporary": 0},
        "armor_class": 15
    }

    # Add same NPC 3 times
    npc_id_1 = manager.add_npc(npc_data)
    npc_id_2 = manager.add_npc(npc_data)
    npc_id_3 = manager.add_npc(npc_data)

    print(f"Generated IDs: {npc_id_1}, {npc_id_2}, {npc_id_3}")

    # Verify they're all unique and follow the pattern
    assert npc_id_1.startswith("goblin_") and "_00" in npc_id_1, f"ID 1 malformed: {npc_id_1}"
    assert npc_id_2.startswith("goblin_") and "_00" in npc_id_2, f"ID 2 malformed: {npc_id_2}"
    assert npc_id_3.startswith("goblin_") and "_00" in npc_id_3, f"ID 3 malformed: {npc_id_3}"

    # Verify all are different
    assert len({npc_id_1, npc_id_2, npc_id_3}) == 3, "IDs are not unique"

    print("✅ NPC unique ID generation works")


def test_get_npcs():
    """Test that get_npcs returns only NPCs"""
    manager = CharacterManager()

    # Add a player character
    player_data = {
        "character_id": "aggi",
        "name": "Aggi",
        "level": 1,
        "ability_scores": {"strength": 8, "dexterity": 11, "constitution": 11,
                          "intelligence": 8, "wisdom": 6, "charisma": 13},
        "hit_points": {"current": 8, "maximum": 8, "temporary": 0},
        "character_class": "Radiant"
    }
    manager.add_character(player_data)

    # Add NPCs
    npc_data = {
        "name": "Goblin",
        "level": 1,
        "character_class": "Warrior",
        "ability_scores": {"strength": 8, "dexterity": 14, "constitution": 10,
                          "intelligence": 10, "wisdom": 8, "charisma": 8},
        "hit_points": {"maximum": 7, "current": 7, "temporary": 0},
        "armor_class": 15
    }
    manager.add_npc(npc_data)
    manager.add_npc(npc_data)

    npcs = manager.get_npcs()

    assert len(npcs) == 2
    assert "goblin_001" in npcs
    assert "goblin_002" in npcs
    assert "aggi" not in npcs

    print("✅ get_npcs filters correctly")


def test_remove_npc():
    """Test that remove_npc works"""
    manager = CharacterManager()

    npc_data = {
        "name": "Goblin",
        "level": 1,
        "character_class": "Warrior",
        "ability_scores": {"strength": 8, "dexterity": 14, "constitution": 10,
                          "intelligence": 10, "wisdom": 8, "charisma": 8},
        "hit_points": {"maximum": 7, "current": 7, "temporary": 0},
        "armor_class": 15
    }

    npc_id = manager.add_npc(npc_data)
    assert npc_id in manager.characters

    # Remove NPC
    removed = manager.remove_npc(npc_id)

    assert removed is True
    assert npc_id not in manager.characters

    # Try removing again (should return False)
    removed_again = manager.remove_npc(npc_id)
    assert removed_again is False

    print("✅ remove_npc works correctly")


if __name__ == "__main__":
    print("Running character format fix tests...\n")

    test_aggi_json_format()
    test_character_manager_with_aggi()
    test_character_manager_hp_normalization()
    test_add_npc_with_class_field()
    test_add_npc_with_character_class_field()
    test_npc_unique_ids()
    test_get_npcs()
    test_remove_npc()

    print("\n✅ All character format tests passed!")
