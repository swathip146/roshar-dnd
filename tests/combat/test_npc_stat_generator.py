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

from components.combat.npc_stat_generator import NPCStatGenerator, NPCStats
from pydantic import ValidationError


@pytest.fixture
def llm_mock():
    """Mock LLM for testing"""
    llm = Mock()

    # Mock the run method to return proper structure
    mock_reply = Mock()
    mock_reply.content = """```json
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

    llm.run.return_value = {"replies": [mock_reply]}
    return llm


@pytest.fixture
def npc_generator_mock(llm_mock):
    """Create NPCStatGenerator with mocked LLM"""
    return NPCStatGenerator(llm=llm_mock, document_store=None)


@pytest.fixture
def real_llm():
    """Get real LLM for integration testing"""
    from config.llm_config import LLMConfigManager
    llm_config = LLMConfigManager()
    return llm_config.create_generator("npc_stat_generator")


@pytest.mark.unit
def test_generate_goblin_stats_mock(npc_generator_mock):
    """Test NPC generation with mock LLM (fast test)"""
    npc = npc_generator_mock.generate_npc_stats(
        npc_description="A small goblin warrior with a rusty scimitar",
        challenge_rating=0.25,
        role="combatant",
        context={"party_level": 1}
    )

    # Verify format matches CharacterData structure
    assert npc["name"] == "Goblin Warrior"
    assert npc["level"] == 1
    assert npc["character_class"] == "Warrior"  # Not "class"
    assert npc["background"] == "Tribal Warrior"
    assert npc["ability_scores"]["dexterity"] == 14
    assert npc["hit_points"]["maximum"] == 7
    assert npc["hit_points"]["temporary"] == 0  # Must have temporary
    assert npc["armor_class"] == 15
    assert isinstance(npc["skills"], dict)  # Must be dict, not list
    assert len(npc["attacks"]) == 1
    assert npc["attacks"][0]["name"] == "Scimitar"


@pytest.mark.integration
@pytest.mark.llm
def test_generate_goblin_stats_real_llm(real_llm):
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
        pytest.skip("GEMINI_API_KEY not set")

    npc_generator = NPCStatGenerator(llm=real_llm, document_store=None)

    print("\n🔄 Making REAL LLM call to Gemini...")

    npc = npc_generator.generate_npc_stats(
        npc_description="A small goblin warrior with a rusty scimitar and leather armor",
        challenge_rating=0.25,
        role="combatant",
        context={"party_level": 1}
    )

    print(f"\n📊 Generated NPC: {npc['name']}")
    print(f"   Stats: {json.dumps(npc, indent=2)}")

    # CRITICAL VALIDATIONS - verify real LLM output matches expected format

    # 1. Required top-level fields
    assert "name" in npc, "Missing 'name' field"
    assert "level" in npc, "Missing 'level' field"
    assert "character_class" in npc, "Missing 'character_class' field (not 'class'!)"
    assert "background" in npc, "Missing 'background' field"
    assert "race" in npc, "Missing 'race' field"
    assert "ability_scores" in npc, "Missing 'ability_scores' field"
    assert "hit_points" in npc, "Missing 'hit_points' field"
    assert "armor_class" in npc, "Missing 'armor_class' field"
    assert "proficiency_bonus" in npc, "Missing 'proficiency_bonus' field"
    assert "skills" in npc, "Missing 'skills' field"
    assert "attacks" in npc, "Missing 'attacks' field"
    assert "challenge_rating" in npc, "Missing 'challenge_rating' field"

    # 2. Verify ability_scores structure (all 6 abilities)
    assert isinstance(npc["ability_scores"], dict), "ability_scores must be dict"
    required_abilities = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]
    for ability in required_abilities:
        assert ability in npc["ability_scores"], f"Missing ability: {ability}"
        assert isinstance(npc["ability_scores"][ability], int), f"{ability} must be int"
        assert 1 <= npc["ability_scores"][ability] <= 30, f"{ability} out of range (1-30)"

    # 3. Verify hit_points structure (CRITICAL - must have all 3 keys)
    assert isinstance(npc["hit_points"], dict), "hit_points must be dict, not int"
    assert "current" in npc["hit_points"], "hit_points missing 'current'"
    assert "maximum" in npc["hit_points"], "hit_points missing 'maximum'"
    assert "temporary" in npc["hit_points"], "hit_points missing 'temporary' (REQUIRED!)"
    assert npc["hit_points"]["maximum"] > 0, "HP must be > 0"
    assert npc["hit_points"]["current"] == npc["hit_points"]["maximum"], "Current HP should equal max at creation"

    # 4. Verify skills structure (CRITICAL - must be dict, not list)
    assert isinstance(npc["skills"], dict), "skills must be dict of {skill_name: bool}, not list"

    # 5. Verify attacks structure
    assert isinstance(npc["attacks"], list), "attacks must be list"
    if len(npc["attacks"]) > 0:
        attack = npc["attacks"][0]
        assert "name" in attack, "Attack missing 'name'"
        assert "attack_bonus" in attack, "Attack missing 'attack_bonus'"
        assert "damage_dice" in attack, "Attack missing 'damage_dice'"
        assert "damage_bonus" in attack, "Attack missing 'damage_bonus'"
        assert "damage_type" in attack, "Attack missing 'damage_type'"

    # 6. Verify special_abilities
    assert isinstance(npc.get("special_abilities", []), list), "special_abilities must be list"

    # 7. Verify types
    assert isinstance(npc["name"], str)
    assert isinstance(npc["level"], int)
    assert isinstance(npc["character_class"], str)
    assert isinstance(npc["background"], str)
    assert isinstance(npc["armor_class"], int)
    assert isinstance(npc["proficiency_bonus"], int)
    assert isinstance(npc["challenge_rating"], (int, float))

    print("\n✅ Real LLM generated CORRECT format!")
    print(f"   All required fields present")
    print(f"   hit_points has current/maximum/temporary")
    print(f"   skills is dict (not list)")
    print(f"   Uses 'character_class' (not 'class')")


@pytest.mark.unit
def test_validate_and_repair_invalid_stats(npc_generator_mock):
    """Test stat validation and repair"""
    invalid_npc = {
        "name": "Test NPC",
        "ability_scores": {
            "strength": 50,  # Invalid (too high)
            "dexterity": -5,  # Invalid (too low)
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10
        },
        "hit_points": {"maximum": -5, "current": -5},  # Invalid (negative)
        "armor_class": 0,  # Invalid (too low)
        "attacks": []  # Missing attacks
    }

    repaired = npc_generator_mock.validate_and_repair(invalid_npc, target_cr=1)

    # Verify repairs
    assert repaired["ability_scores"]["strength"] == 30  # Clamped
    assert repaired["ability_scores"]["dexterity"] == 1  # Clamped
    assert repaired["hit_points"]["maximum"] > 0  # Fixed
    assert repaired["armor_class"] >= 5  # Fixed (10 + DEX mod, where DEX=1 gives mod=-5)
    assert len(repaired["attacks"]) >= 1  # Added default


@pytest.mark.unit
def test_load_template(npc_generator_mock):
    """Test loading predefined NPC template"""
    # Templates should be loaded from data/npc_templates.json
    goblin = npc_generator_mock.get_npc_from_template("goblin")

    assert goblin is not None
    assert goblin["name"] == "Goblin"
    assert goblin["character_class"] == "Warrior"
    assert goblin["armor_class"] == 15


@pytest.mark.unit
def test_template_not_found(npc_generator_mock):
    """Test handling of missing template"""
    result = npc_generator_mock.get_npc_from_template("dragon")
    assert result is None


@pytest.mark.unit
def test_parse_json_with_code_block(npc_generator_mock):
    """Test parsing JSON from markdown code block"""
    response = """```json
{
    "name": "Test",
    "level": 1
}
```"""

    parsed = npc_generator_mock._parse_json_response(response)
    assert parsed["name"] == "Test"
    assert parsed["level"] == 1


@pytest.mark.unit
def test_parse_json_fallback(npc_generator_mock):
    """Test fallback when JSON parsing fails"""
    response = "Invalid JSON {{{{"

    parsed = npc_generator_mock._parse_json_response(response)

    # Should return fallback dict
    assert parsed["name"] == "Unknown NPC"
    assert parsed["level"] == 1
    assert "ability_scores" in parsed


@pytest.mark.unit
def test_pydantic_validation():
    """Test Pydantic model validation"""
    # Valid NPC data
    valid_data = {
        "name": "Test NPC",
        "level": 1,
        "character_class": "Warrior",
        "race": "Human",
        "background": "Soldier",
        "ability_scores": {
            "strength": 10, "dexterity": 10, "constitution": 10,
            "intelligence": 10, "wisdom": 10, "charisma": 10
        },
        "hit_points": {"current": 10, "maximum": 10, "temporary": 0},
        "armor_class": 10,
        "proficiency_bonus": 2,
        "skills": {"athletics": True},
        "attacks": [{
            "name": "Sword",
            "attack_bonus": 2,
            "damage_dice": "1d6",
            "damage_bonus": 0,
            "damage_type": "slashing"
        }],
        "special_abilities": [],
        "challenge_rating": 0.5
    }

    # Should validate successfully
    npc = NPCStats(**valid_data)
    assert npc.name == "Test NPC"
    assert npc.character_class == "Warrior"


@pytest.mark.unit
def test_pydantic_validation_fails_missing_hp_keys():
    """Test Pydantic validation catches missing hit_points keys"""
    invalid_data = {
        "name": "Test NPC",
        "level": 1,
        "character_class": "Warrior",
        "race": "Human",
        "background": "Soldier",
        "ability_scores": {
            "strength": 10, "dexterity": 10, "constitution": 10,
            "intelligence": 10, "wisdom": 10, "charisma": 10
        },
        "hit_points": {"current": 10, "maximum": 10},  # Missing temporary!
        "armor_class": 10,
        "proficiency_bonus": 2,
        "skills": {},
        "attacks": [],
        "special_abilities": [],
        "challenge_rating": 0.5
    }

    # Should raise ValidationError
    with pytest.raises(ValidationError) as excinfo:
        NPCStats(**invalid_data)

    assert "temporary" in str(excinfo.value).lower()


if __name__ == "__main__":
    print("Running NPC Stat Generator tests...\n")

    # Run tests
    print("=" * 60)
    print("UNIT TESTS (Mock LLM)")
    print("=" * 60)

    pytest.main([__file__, "-v", "-m", "unit"])

    print("\n" + "=" * 60)
    print("INTEGRATION TEST (Real LLM)")
    print("=" * 60)
    print("⚠️  This test makes a REAL API call to Gemini")
    print("⚠️  Costs ~$0.0001 per run")
    print("⚠️  Requires GEMINI_API_KEY in .env\n")

    pytest.main([__file__, "-v", "-m", "llm"])
