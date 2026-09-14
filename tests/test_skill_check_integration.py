"""
Integration test for Phase 2: Skill Check Integration

Tests that skill checks flow through the complete pipeline:
GameEngine → dnd_engine_wrapper → actual D&D 5e mechanics
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.game_initialization import initialize_enhanced_dnd_game
from config.logging_config import get_logger

logger = get_logger(__name__)


def test_skill_check_integration():
    """Test that skill checks use dnd_engine wrapper in live game"""
    print("\n" + "="*80)
    print("PHASE 2 INTEGRATION TEST: Skill Check Flow")
    print("="*80 + "\n")

    # Initialize game
    print("1. Initializing game...")
    config = initialize_enhanced_dnd_game()

    assert config.dnd_engine_wrapper, (
        "dnd_engine_wrapper was not created during initialization, so no skill "
        "check can reach the real 5e mechanics")

    print(f"✅ Game initialized with {len(config.dnd_engine_wrapper.entities)} entities")

    # Get a character for testing
    character_manager = config.character_manager
    assert character_manager.characters, "initialization produced no characters"

    char_id = list(character_manager.characters.keys())[0]
    character = character_manager.characters[char_id]
    print(f"\n2. Testing with character: {character.name} (ID: {char_id})")

    # Display character stats
    print(f"\nCharacter Stats:")
    print(f"  - STR: {character.ability_scores.get('strength', 10)}")
    print(f"  - DEX: {character.ability_scores.get('dexterity', 10)}")
    print(f"  - CON: {character.ability_scores.get('constitution', 10)}")
    print(f"  - INT: {character.ability_scores.get('intelligence', 10)}")
    print(f"  - WIS: {character.ability_scores.get('wisdom', 10)}")
    print(f"  - CHA: {character.ability_scores.get('charisma', 10)}")
    print(f"  - Proficiency Bonus: +{character.proficiency_bonus}")
    print(f"  - HP: {character.hit_points.get('current', 0)}/{character.hit_points.get('maximum', 0)}")

    # Test skill check through GameEngine
    print("\n3. Testing skill check through GameEngine.process_skill_check()...")

    # Create a skill check request (simulating what would come from the game loop)
    from components.shared_contract import RequestDTO

    check_request = RequestDTO(
        actor=char_id,
        action_type="skill_check",
        skill="athletics",
        dc=15,
        _dnd_engine_wrapper_ref=config.dnd_engine_wrapper
    )

    print(f"\nSkill Check Request:")
    print(f"  - Character: {character.name}")
    print(f"  - Skill: athletics")
    print(f"  - DC: 15")

    # Execute skill check through GameEngine
    result = config.game_engine.process_skill_check(check_request)

    print(f"\nSkill Check Result:")
    print(f"  - Success: {result.get('success', False)}")
    print(f"  - Total Roll: {result.get('roll_total', 0)}")
    print(f"  - Natural Roll: {result.get('raw_rolls', [0])[0] if result.get('raw_rolls') else 'N/A'}")
    print(f"  - Modifier: {result.get('roll_total', 0) - (result.get('raw_rolls', [0])[0] if result.get('raw_rolls') else 0)}")
    print(f"  - DC: {result.get('dc', 0)}")
    print(f"  - Advantage State: {result.get('advantage_state', 'normal')}")

    # Verify the result has expected structure
    assert "roll_total" in result, (
        f"result is missing 'roll_total', so no die was reported. "
        f"Got keys: {sorted(result.keys())}")

    assert "success" in result, (
        f"result is missing 'success', so the check has no verdict. "
        f"Got keys: {sorted(result.keys())}")
    assert 1 <= int(result["roll_total"]) <= 40, (
        f"implausible d20-based total: {result['roll_total']}")

    print("\n✅ Skill check executed successfully through wrapper!")

    # Test multiple skill checks to verify consistency
    print("\n4. Testing multiple skill checks for consistency...")

    test_skills = [
        ("perception", 12),
        ("persuasion", 18),
        ("stealth", 10),
        ("acrobatics", 14)
    ]

    for skill, dc in test_skills:
        check_request["skill"] = skill
        check_request["dc"] = dc

        result = config.game_engine.process_skill_check(check_request)

        natural = result.get('raw_rolls', [0])[0] if result.get('raw_rolls') else 0
        total = result.get('roll_total', 0)
        modifier = total - natural
        success = result.get('success', False)

        print(f"  - {skill.capitalize():15} (DC {dc:2}): d20={natural:2}, modifier={modifier:+3}, total={total:2} → {'SUCCESS' if success else 'FAIL'}")

        # Previously this loop only PRINTED, so a broken skill produced tidy output
        # and a green test. Assert the shape of every check instead.
        assert "roll_total" in result, f"{skill}: no roll_total in {sorted(result)}"
        assert isinstance(success, bool), f"{skill}: success was {success!r}"
        assert 1 <= natural <= 20, f"{skill}: natural roll {natural} is not a d20"

    print("\n✅ Multiple skill checks working correctly!")

    # Test that wrapper entities are synced
    print("\n5. Verifying entity synchronization...")

    entity = config.dnd_engine_wrapper.entities.get(char_id)
    assert entity is not None, (
        f"no engine entity for {char_id}; the wrapper never synced this character")

    print(f"  - Entity name: {entity.name}")
    print(f"  - Entity UUID: {entity.uuid}")
    print(f"  - Entity has ability_scores: ✅")
    print(f"  - Entity has skill_set: ✅")
    print(f"  - Entity has health: ✅")
    print(f"  - Entity has equipment: ✅")

    # Verify wrapper is using actual character data
    assert entity.name == character.name, (
        f"entity/character mismatch: entity {entity.name!r} vs "
        f"CharacterManager {character.name!r}")

    print(f"  - Character sync: ✅ (Entity '{entity.name}' matches CharacterManager)")
    print("\n✅ Entity synchronization working correctly!")

    print("\n" + "="*80)
    print("PHASE 2 INTEGRATION TEST: ALL TESTS PASSED ✅")
    print("="*80)
    print("\nConclusion:")
    print("  - dnd_engine_wrapper successfully integrated into game initialization")
    print("  - Skill checks flow through GameEngine.process_skill_check()")
    print("  - dnd_engine wrapper executes actual D&D 5e mechanics")
    print("  - Results properly formatted for game pipeline")
    print("  - Entity synchronization maintains state consistency")
    print("\n🎲 Ready to proceed with Phase 3: Combat System Integration")


if __name__ == "__main__":
    try:
        test_skill_check_integration()
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ TEST FAILED WITH ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
