"""
Test NPC Stat Generator with both mock and real LLM calls.

Tests:
1. Mock LLM test for fast validation
2. Real LLM test to verify Gemini generates correct format
3. Stat validation and repair
4. Template loading
5. JSON parsing
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Note: Will need to implement these when Phase 1 starts
# from components.combat.npc_stat_generator import NPCStatGenerator
# from config.llm_config import get_llm


@pytest.fixture
def llm_mock():
    """Mock LLM for testing"""
    llm = Mock()
    response = Mock()
    response.content = """```json
{
    "name": "Goblin Warrior",
    "level": 1,
    "character_class": "Warrior",
    "race": "Goblin",
    "background": "Tribal Warrior",
    "ability_scores": {
        "strength": 8,
        "dexterity": 14,
        "constitution": 10,
        "intelligence": 10,
        "wisdom": 8,
        "charisma": 8
    },
    "hit_points": {"maximum": 7, "current": 7, "temporary": 0},
    "armor_class": 15,
    "proficiency_bonus": 2,
    "skills": {
        "stealth": true,
        "survival": true
    },
    "attacks": [
        {
            "name": "Scimitar",
            "attack_bonus": 4,
            "damage_dice": "1d6",
            "damage_bonus": 2,
            "damage_type": "slashing"
        }
    ],
    "special_abilities": ["Nimble Escape"],
    "challenge_rating": 0.25
}
```"""
    llm.generate.return_value = response
    return llm


@pytest.fixture
def npc_generator_mock(llm_mock):
    """Create NPCStatGenerator with mocked LLM"""
    # This will be implemented in Phase 1
    # return NPCStatGenerator(llm=llm_mock, document_store=None)
    pass


@pytest.fixture
def real_llm():
    """Get real LLM for integration testing"""
    # This will be implemented in Phase 1
    # return get_llm()
    pass


@pytest.mark.unit
def test_generate_goblin_stats_mock(llm_mock):
    """Test NPC generation with mock LLM (fast test)"""
    # Placeholder - will implement in Phase 1
    # npc_generator = NPCStatGenerator(llm=llm_mock, document_store=None)

    # npc = npc_generator.generate_npc_stats(
    #     npc_description="A small goblin warrior with a rusty scimitar",
    #     challenge_rating=0.25,
    #     role="combatant",
    #     context={"party_level": 1}
    # )

    # Verify format matches CharacterData structure
    # assert npc["name"] == "Goblin Warrior"
    # assert npc["level"] == 1
    # assert npc["character_class"] == "Warrior"  # Not "class"
    # assert npc["background"] == "Tribal Warrior"
    # assert npc["ability_scores"]["dexterity"] == 14
    # assert npc["hit_points"]["maximum"] == 7
    # assert npc["hit_points"]["temporary"] == 0  # Must have temporary
    # assert npc["armor_class"] == 15
    # assert isinstance(npc["skills"], dict)  # Must be dict, not list
    # assert len(npc["attacks"]) == 1
    # assert npc["attacks"][0]["name"] == "Scimitar"

    print("⏭️  Skipping - Phase 1 not implemented yet")


@pytest.mark.integration
@pytest.mark.llm
def test_generate_goblin_stats_real_llm():
    """
    Test NPC generation with REAL Gemini LLM call.

    This verifies that the actual LLM generates the correct JSON format
    that matches CharacterData structure.

    ⚠️  Requires GEMINI_API_KEY in .env
    ⚠️  Makes actual API call (costs ~$0.0001)
    """
    # Skip if no API key
    import os
    if not os.getenv("GEMINI_API_KEY"):
        print("⏭️  Skipping - GEMINI_API_KEY not set")
        return

    # Placeholder - will implement in Phase 1
    # from config.llm_config import get_llm
    # from components.combat.npc_stat_generator import NPCStatGenerator

    # llm = get_llm()
    # npc_generator = NPCStatGenerator(llm=llm, document_store=None)

    # print("\n🔄 Making REAL LLM call to Gemini...")

    # npc = npc_generator.generate_npc_stats(
    #     npc_description="A small goblin warrior with a rusty scimitar and leather armor",
    #     challenge_rating=0.25,
    #     role="combatant",
    #     context={"party_level": 1}
    # )

    # print(f"\n📊 Generated NPC: {npc['name']}")
    # print(f"   Stats: {json.dumps(npc, indent=2)}")

    # # CRITICAL VALIDATIONS - verify real LLM output matches expected format

    # # 1. Required top-level fields
    # assert "name" in npc, "Missing 'name' field"
    # assert "level" in npc, "Missing 'level' field"
    # assert "character_class" in npc, "Missing 'character_class' field (not 'class'!)"
    # assert "background" in npc, "Missing 'background' field"
    # assert "race" in npc, "Missing 'race' field"
    # assert "ability_scores" in npc, "Missing 'ability_scores' field"
    # assert "hit_points" in npc, "Missing 'hit_points' field"
    # assert "armor_class" in npc, "Missing 'armor_class' field"
    # assert "proficiency_bonus" in npc, "Missing 'proficiency_bonus' field"
    # assert "skills" in npc, "Missing 'skills' field"
    # assert "attacks" in npc, "Missing 'attacks' field"
    # assert "challenge_rating" in npc, "Missing 'challenge_rating' field"

    # # 2. Verify ability_scores structure (all 6 abilities)
    # assert isinstance(npc["ability_scores"], dict), "ability_scores must be dict"
    # required_abilities = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]
    # for ability in required_abilities:
    #     assert ability in npc["ability_scores"], f"Missing ability: {ability}"
    #     assert isinstance(npc["ability_scores"][ability], int), f"{ability} must be int"
    #     assert 1 <= npc["ability_scores"][ability] <= 30, f"{ability} out of range (1-30)"

    # # 3. Verify hit_points structure (CRITICAL - must have all 3 keys)
    # assert isinstance(npc["hit_points"], dict), "hit_points must be dict, not int"
    # assert "current" in npc["hit_points"], "hit_points missing 'current'"
    # assert "maximum" in npc["hit_points"], "hit_points missing 'maximum'"
    # assert "temporary" in npc["hit_points"], "hit_points missing 'temporary' (REQUIRED!)"
    # assert npc["hit_points"]["maximum"] > 0, "HP must be > 0"
    # assert npc["hit_points"]["current"] == npc["hit_points"]["maximum"], "Current HP should equal max at creation"

    # # 4. Verify skills structure (CRITICAL - must be dict, not list)
    # assert isinstance(npc["skills"], dict), "skills must be dict of {skill_name: bool}, not list"

    # # 5. Verify attacks structure
    # assert isinstance(npc["attacks"], list), "attacks must be list"
    # if len(npc["attacks"]) > 0:
    #     attack = npc["attacks"][0]
    #     assert "name" in attack, "Attack missing 'name'"
    #     assert "attack_bonus" in attack, "Attack missing 'attack_bonus'"
    #     assert "damage_dice" in attack, "Attack missing 'damage_dice'"
    #     assert "damage_bonus" in attack, "Attack missing 'damage_bonus'"
    #     assert "damage_type" in attack, "Attack missing 'damage_type'"

    # # 6. Verify special_abilities
    # assert isinstance(npc.get("special_abilities", []), list), "special_abilities must be list"

    # # 7. Verify types
    # assert isinstance(npc["name"], str)
    # assert isinstance(npc["level"], int)
    # assert isinstance(npc["character_class"], str)
    # assert isinstance(npc["background"], str)
    # assert isinstance(npc["armor_class"], int)
    # assert isinstance(npc["proficiency_bonus"], int)
    # assert isinstance(npc["challenge_rating"], (int, float))

    # print("\n✅ Real LLM generated CORRECT format!")
    # print(f"   All required fields present")
    # print(f"   hit_points has current/maximum/temporary")
    # print(f"   skills is dict (not list)")
    # print(f"   Uses 'character_class' (not 'class')")

    print("⏭️  Skipping - Phase 1 not implemented yet")


@pytest.mark.unit
def test_validate_and_repair_invalid_stats():
    """Test stat validation and repair"""
    # Placeholder - will implement in Phase 1
    # npc_generator = NPCStatGenerator(llm=Mock(), document_store=None)

    # invalid_npc = {
    #     "name": "Test NPC",
    #     "ability_scores": {
    #         "strength": 50,  # Invalid (too high)
    #         "dexterity": -5,  # Invalid (too low)
    #         "constitution": 10,
    #         "intelligence": 10,
    #         "wisdom": 10,
    #         "charisma": 10
    #     },
    #     "hit_points": {"maximum": -5, "current": -5},  # Invalid (negative)
    #     "armor_class": 0,  # Invalid (too low)
    #     "attacks": []  # Missing attacks
    # }

    # repaired = npc_generator.validate_and_repair(invalid_npc, target_cr=1)

    # # Verify repairs
    # assert repaired["ability_scores"]["strength"] == 30  # Clamped
    # assert repaired["ability_scores"]["dexterity"] == 1  # Clamped
    # assert repaired["hit_points"]["maximum"] > 0  # Fixed
    # assert repaired["armor_class"] >= 8  # Fixed
    # assert len(repaired["attacks"]) >= 1  # Added default

    print("⏭️  Skipping - Phase 1 not implemented yet")


@pytest.mark.unit
def test_load_template():
    """Test loading predefined NPC template"""
    # Placeholder - will implement in Phase 1
    # npc_generator = NPCStatGenerator(llm=Mock(), document_store=None)

    # # Mock templates
    # npc_generator.templates = {
    #     "goblin": {
    #         "name": "Goblin",
    #         "character_class": "Warrior",
    #         "armor_class": 15,
    #         "hit_points": {"maximum": 7, "current": 7, "temporary": 0}
    #     }
    # }

    # goblin = npc_generator.get_npc_from_template("goblin")

    # assert goblin is not None
    # assert goblin["name"] == "Goblin"
    # assert goblin["armor_class"] == 15

    print("⏭️  Skipping - Phase 1 not implemented yet")


@pytest.mark.unit
def test_template_not_found():
    """Test handling of missing template"""
    # Placeholder - will implement in Phase 1
    # npc_generator = NPCStatGenerator(llm=Mock(), document_store=None)
    # result = npc_generator.get_npc_from_template("dragon")
    # assert result is None

    print("⏭️  Skipping - Phase 1 not implemented yet")


@pytest.mark.unit
def test_parse_json_with_code_block():
    """Test parsing JSON from markdown code block"""
    # Placeholder - will implement in Phase 1
    # npc_generator = NPCStatGenerator(llm=Mock(), document_store=None)

    # response = """```json
    # {
    #     "name": "Test",
    #     "level": 1
    # }
    # ```"""

    # parsed = npc_generator._parse_json_response(response)
    # assert parsed["name"] == "Test"
    # assert parsed["level"] == 1

    print("⏭️  Skipping - Phase 1 not implemented yet")


@pytest.mark.unit
def test_parse_json_fallback():
    """Test fallback when JSON parsing fails"""
    # Placeholder - will implement in Phase 1
    # npc_generator = NPCStatGenerator(llm=Mock(), document_store=None)

    # response = "Invalid JSON {{{{"

    # parsed = npc_generator._parse_json_response(response)

    # # Should return fallback dict
    # assert parsed["name"] == "Unknown NPC"
    # assert parsed["level"] == 1
    # assert "ability_scores" in parsed

    print("⏭️  Skipping - Phase 1 not implemented yet")


if __name__ == "__main__":
    print("Running NPC Stat Generator tests...\n")
    print("⚠️  Note: Phase 1 not implemented yet - all tests are placeholders\n")

    # Run tests
    print("=" * 60)
    print("UNIT TESTS (Mock LLM)")
    print("=" * 60)

    llm_mock_fixture = Mock()
    response = Mock()
    response.content = """```json
{
    "name": "Goblin Warrior",
    "level": 1,
    "character_class": "Warrior",
    "race": "Goblin",
    "background": "Tribal Warrior",
    "ability_scores": {
        "strength": 8,
        "dexterity": 14,
        "constitution": 10,
        "intelligence": 10,
        "wisdom": 8,
        "charisma": 8
    },
    "hit_points": {"maximum": 7, "current": 7, "temporary": 0},
    "armor_class": 15,
    "proficiency_bonus": 2,
    "skills": {
        "stealth": true,
        "survival": true
    },
    "attacks": [
        {
            "name": "Scimitar",
            "attack_bonus": 4,
            "damage_dice": "1d6",
            "damage_bonus": 2,
            "damage_type": "slashing"
        }
    ],
    "special_abilities": ["Nimble Escape"],
    "challenge_rating": 0.25
}
```"""
    llm_mock_fixture.generate.return_value = response

    test_generate_goblin_stats_mock(llm_mock_fixture)
    test_validate_and_repair_invalid_stats()
    test_load_template()
    test_template_not_found()
    test_parse_json_with_code_block()
    test_parse_json_fallback()

    print("\n" + "=" * 60)
    print("INTEGRATION TEST (Real LLM)")
    print("=" * 60)
    print("⚠️  This test makes a REAL API call to Gemini")
    print("⚠️  Costs ~$0.0001 per run")
    print("⚠️  Requires GEMINI_API_KEY in .env\n")

    test_generate_goblin_stats_real_llm()

    print("\n✅ All NPC stat generator tests completed!")
    print("📝 These are placeholder tests - will be implemented in Phase 1")
