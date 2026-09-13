"""
Simple manual test for DnDEngineWrapper without pytest

Run with: python3 tests/test_wrapper_simple.py
"""

import sys
from pathlib import Path

# Patch typing for Python 3.9
try:
    from typing import Self
except ImportError:
    from typing_extensions import Self
    import typing
    typing.Self = Self

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from components.dnd_engine_wrapper import DnDEngineWrapper
from components.game_engine import GameEngine
from components.character_manager import CharacterManager
from components.policy import PolicyProfile


def test_basic_functionality():
    """Test basic wrapper functionality"""
    print("=== Testing DnDEngineWrapper ===\n")

    # Create CharacterManager with test character
    print("1. Creating CharacterManager...")
    character_manager = CharacterManager()

    character_manager.add_character({
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
    print("✓ Character created: Aggi\n")

    # Create GameEngine
    print("2. Creating GameEngine...")
    game_engine = GameEngine(policy_profile=PolicyProfile.HOUSE)
    game_engine.character_manager = character_manager
    print("✓ GameEngine created\n")

    # Create wrapper
    print("3. Creating DnDEngineWrapper...")
    try:
        wrapper = DnDEngineWrapper(
            game_engine=game_engine,
            character_manager=character_manager
        )
        print(f"✓ Wrapper created with {len(wrapper.entities)} entities\n")
    except Exception as e:
        print(f"✗ Failed to create wrapper: {e}\n")
        import traceback
        traceback.print_exc()
        return False

    # Test skill check
    print("4. Testing skill check...")
    char_id = list(character_manager.characters.keys())[0]
    try:
        result = wrapper.execute_skill_check(
            character_id=char_id,
            skill="persuasion",
            dc=15
        )
        print(f"   Result: {result}")
        print(f"   Roll: {result.get('roll', 'N/A')}")
        print(f"   Success: {result.get('success', False)}")
        print(f"   DC: {result.get('dc', 'N/A')}")
        print("✓ Skill check executed\n")
    except Exception as e:
        print(f"✗ Skill check failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False

    # Add enemy for attack test
    print("5. Adding enemy...")
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
    wrapper._sync_characters_to_entities()
    print(f"✓ Enemy added, total entities: {len(wrapper.entities)}\n")

    # Test attack
    print("6. Testing attack...")
    char_ids = list(character_manager.characters.keys())
    attacker_id = char_ids[0]
    target_id = char_ids[1]

    try:
        result = wrapper.execute_attack(
            attacker_id=attacker_id,
            target_id=target_id,
            weapon="unarmed"
        )
        print(f"   Result: {result}")
        print(f"   Hit: {result.get('hit', False)}")
        print(f"   Attack Roll: {result.get('attack_roll', 'N/A')}")
        print(f"   Target AC: {result.get('target_ac', 'N/A')}")
        print(f"   Damage: {result.get('damage', 0)}")
        print("✓ Attack executed\n")
    except Exception as e:
        print(f"✗ Attack failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False

    print("=== All tests passed! ===\n")
    return True


if __name__ == "__main__":
    success = test_basic_functionality()
    sys.exit(0 if success else 1)
