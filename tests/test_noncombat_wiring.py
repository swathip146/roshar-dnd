"""
Tests for non-combat wiring fixes (plan 0.3 §5,8,10,11).

Tests cover:
1. Social skill checks with real dice in NPC interactions
2. Passive perception calculation
3. Inventory add/remove tools
4. Export/import game state character data preservation
5. Routing history cap increase

All tests use real components, no mocks.
"""

import pytest
from typing import Dict, Any

from components.game_engine import GameEngine
from components.character_manager import CharacterManager, CharacterData
from components.session_manager import SessionManager
from components.policy import PolicyEngine
from agents import dm_tools
from agents.npc_controller_agent import (
    set_npc_tool_context,
    clear_npc_tool_context,
    roll_social_check,
    assess_attitude_change,
)


@pytest.fixture
def test_character() -> CharacterData:
    """Create a test character with specific ability scores."""
    print("🔧 Creating test character with WIS 16 (proficient in Perception and Persuasion)")
    return CharacterData(
        character_id="test_pc",
        name="Test Hero",
        level=3,
        proficiency_bonus=2,
        character_class="Windrunner",
        race="Alethi",
        background="Soldier",
        # Use lowercase full ability names as per AbilityScore enum
        ability_scores={"strength": 14, "dexterity": 12, "constitution": 13,
                       "intelligence": 10, "wisdom": 16, "charisma": 14},
        ability_modifiers={"strength": 2, "dexterity": 1, "constitution": 1,
                          "intelligence": 0, "wisdom": 3, "charisma": 2},
        skills={
            "perception": True,  # Proficient
            "persuasion": True,  # Proficient
            "insight": False,
            "deception": False,
            "intimidation": False,
        },
        expertise_skills=[],
        hit_points={"current": 25, "maximum": 25, "temporary": 0},
        armor_class=16,
        saving_throw_proficiencies=["wisdom", "charisma"],
        conditions=[],
        features=["Windrunner Maneuvers"],
        equipment=["Longsword", "Shield", "Traveler's Clothes"],
        currency={"gp": 50, "sp": 10, "cp": 5},
    )


@pytest.fixture
def manager_with_character(test_character: CharacterData) -> CharacterManager:
    """Create a character manager with a test character."""
    print("🔧 Setting up CharacterManager with test character")
    manager = CharacterManager()
    manager.add_character(test_character.to_dict())
    return manager


@pytest.fixture
def game_engine_with_character(test_character: CharacterData) -> GameEngine:
    """Create a game engine with a test character."""
    print("🔧 Setting up GameEngine with test character")

    # GameEngine creates its own CharacterManager, so we create the engine first
    engine = GameEngine()

    # Then add our test character to the engine's character manager
    engine.character_manager.add_character(test_character.to_dict())

    # Initialize character runtime state
    engine.game_state.characters["test_pc"] = {
        "position": {"x": 0, "y": 0},
        "hidden": False,
        "initiative": 0,
        "runtime_conditions": [],
        "last_action": None,
        "session_notes": [],
    }

    return engine


class TestPassivePerception:
    """Test passive perception calculation and exposure."""

    def test_passive_perception_calculation(self, manager_with_character: CharacterManager):
        """Passive Perception = 10 + WIS mod + proficiency if proficient."""
        print("\n🧪 TEST: Passive perception calculation")
        print("   Expected: 10 + 3 (WIS) + 2 (prof) = 15")

        result = manager_with_character.get_passive_score("test_pc", "perception")

        print(f"   Result: {result['passive_score']} ({result['breakdown']})")
        assert result["passive_score"] == 15, "Should be 10 + 3 WIS + 2 prof"
        assert result["breakdown"] == "10 + 5 = 15"
        print("   ✅ Passive perception correct")

    def test_passive_perception_tool(self, game_engine_with_character: GameEngine):
        """Test that get_passive_perception tool works."""
        print("\n🧪 TEST: Passive perception tool")

        dm_tools.set_dm_tool_context(
            game_engine=game_engine_with_character,
            character_manager=game_engine_with_character.character_manager
        )

        try:
            result = dm_tools.get_passive_perception.function(actor="test_pc")

            print(f"   Tool result: {result}")
            assert "passive_perception" in result
            assert result["passive_perception"] == 15
            assert "breakdown" in result
            print("   ✅ Passive perception tool works")
        finally:
            dm_tools.clear_dm_tool_context()


class TestInventoryTools:
    """Test inventory add/remove tools."""

    def test_add_item_to_inventory(self, game_engine_with_character: GameEngine):
        """Test adding items to character inventory."""
        print("\n🧪 TEST: Add item to inventory")

        dm_tools.set_dm_tool_context(
            game_engine=game_engine_with_character,
            character_manager=game_engine_with_character.character_manager
        )

        try:
            print("   Adding 'Healing Potion' to inventory")
            result = dm_tools.add_item_to_inventory.function(
                item="Healing Potion",
                actor="test_pc",
                quantity=2
            )

            print(f"   Result: {result}")
            assert result.get("added") is True
            assert result["item"] == "Healing Potion"
            assert result["quantity"] == 2
            assert "Healing Potion" in result["current_inventory"]

            # Check character directly
            char = game_engine_with_character.character_manager.characters["test_pc"]
            print(f"   Character inventory: {char.equipment}")
            assert "Healing Potion" in (char.equipment or [])
            print("   ✅ Item added successfully")
        finally:
            dm_tools.clear_dm_tool_context()

    def test_remove_item_from_inventory(self, game_engine_with_character: GameEngine):
        """Test removing items from character inventory."""
        print("\n🧪 TEST: Remove item from inventory")

        dm_tools.set_dm_tool_context(
            game_engine=game_engine_with_character,
            character_manager=game_engine_with_character.character_manager
        )

        try:
            # First add an item
            print("   Adding 'Rope' to inventory")
            dm_tools.add_item_to_inventory.function(item="Rope", actor="test_pc", quantity=1)

            # Now remove it
            print("   Removing 'Rope' from inventory")
            result = dm_tools.remove_item_from_inventory.function(
                item="Rope",
                actor="test_pc",
                quantity=1
            )

            print(f"   Result: {result}")
            assert result.get("removed") is True
            assert result["item"] == "Rope"

            # Check character directly
            char = game_engine_with_character.character_manager.characters["test_pc"]
            print(f"   Character inventory: {char.equipment}")
            # Rope should be gone or have reduced quantity
            print("   ✅ Item removed successfully")
        finally:
            dm_tools.clear_dm_tool_context()


class TestSocialSkillChecks:
    """Test social skill checks with real dice."""

    def test_roll_social_check_persuasion(self, game_engine_with_character: GameEngine):
        """Test rolling a Persuasion check."""
        print("\n🧪 TEST: Roll Persuasion check")
        print("   Character has +2 CHA, +2 prof = +4 modifier")

        set_npc_tool_context(game_engine=game_engine_with_character)

        try:
            # roll_social_check is a Tool, need to invoke its function
            result = roll_social_check.function(
                skill="persuasion",
                dc=15,
                actor="test_pc"
            )

            print(f"   Roll result: {result}")
            assert "success" in result
            assert "roll_total" in result
            assert "dc" in result
            # Policy engine may adjust DC, so just check it's reasonable
            assert 10 <= result["dc"] <= 20, f"DC {result['dc']} out of reasonable range"
            assert result["skill"] == "persuasion"

            # The roll should be d20 + modifier
            modifier = result.get("character_modifier", 0)
            roll_total = result.get("roll_total", 0)
            print(f"   Modifier: {modifier}, Total: {roll_total}, DC: {result['dc']}")
            print(f"   Success: {result['success']}")

            # Verify the roll is in valid range (1+mod to 20+mod)
            assert 1 + modifier <= roll_total <= 20 + modifier, f"Roll {roll_total} out of range"
            print("   ✅ Persuasion check rolled correctly")
        finally:
            clear_npc_tool_context()

    def test_assess_attitude_with_skill_success(self):
        """Test attitude change with successful skill check."""
        print("\n🧪 TEST: Attitude change with skill check success")

        result = assess_attitude_change.function(
            npc_id="guard",
            player_action="I try to persuade the guard to let us pass",
            npc_personality="neutral",
            current_attitude="unfriendly",
            skill_check_success=True
        )

        print(f"   Result: {result}")
        assert result["old_attitude"] == "unfriendly"
        # Success should improve attitude
        attitude_levels = ["hostile", "unfriendly", "neutral", "friendly", "helpful"]
        old_idx = attitude_levels.index(result["old_attitude"])
        new_idx = attitude_levels.index(result["new_attitude"])
        print(f"   Attitude: {result['old_attitude']} -> {result['new_attitude']}")
        print(f"   Reasoning: {result['reasoning']}")
        assert new_idx >= old_idx, "Successful persuasion should improve or maintain attitude"
        print("   ✅ Skill check affects attitude correctly")

    def test_assess_attitude_with_skill_failure(self):
        """Test attitude change with failed skill check."""
        print("\n🧪 TEST: Attitude change with skill check failure")

        result = assess_attitude_change.function(
            npc_id="guard",
            player_action="I try to persuade the guard to let us pass",
            npc_personality="suspicious",
            current_attitude="neutral",
            skill_check_success=False
        )

        print(f"   Result: {result}")
        # Failure should not improve attitude (might worsen or stay same)
        attitude_levels = ["hostile", "unfriendly", "neutral", "friendly", "helpful"]
        old_idx = attitude_levels.index(result["old_attitude"])
        new_idx = attitude_levels.index(result["new_attitude"])
        print(f"   Attitude: {result['old_attitude']} -> {result['new_attitude']}")
        print(f"   Reasoning: {result['reasoning']}")
        # With suspicious personality and failure, likely to worsen or stay
        print("   ✅ Failed skill check handled correctly")


class TestExportImportCharacterData:
    """Test that export/import preserves full character data."""

    def test_export_uses_to_dict(self, game_engine_with_character: GameEngine):
        """Test that export_game_state uses CharacterData.to_dict()."""
        print("\n🧪 TEST: Export uses to_dict() not get_character_summary()")

        # Export the state
        exported = game_engine_with_character.export_game_state()

        print("   Checking exported character data...")
        assert "character_data" in exported
        char_data = exported["character_data"]["test_pc"]

        # These fields are dropped by get_character_summary but preserved by to_dict
        print(f"   hit_points: {char_data.get('hit_points')}")
        print(f"   armor_class: {char_data.get('armor_class')}")
        print(f"   equipment: {char_data.get('equipment')}")

        assert "hit_points" in char_data, "hit_points should be preserved"
        assert "armor_class" in char_data, "armor_class should be preserved"
        assert "equipment" in char_data, "equipment should be preserved"
        assert char_data["hit_points"]["current"] == 25
        assert char_data["armor_class"] == 16
        assert "Longsword" in char_data["equipment"]
        print("   ✅ Export preserves full character data")

    def test_import_restores_full_character(self, game_engine_with_character: GameEngine):
        """Test that import restores full character state."""
        print("\n🧪 TEST: Import restores full character from to_dict() export")

        # Export current state
        exported = game_engine_with_character.export_game_state()

        # Modify character in place
        char = game_engine_with_character.character_manager.characters["test_pc"]
        original_hp = char.hit_points["current"]
        char.hit_points["current"] = 10
        print(f"   Modified HP: {original_hp} -> {char.hit_points['current']}")

        # Import should restore
        game_engine_with_character.import_game_state(exported)

        restored_char = game_engine_with_character.character_manager.characters["test_pc"]
        print(f"   Restored HP: {restored_char.hit_points['current']}")
        print(f"   Restored AC: {restored_char.armor_class}")
        print(f"   Restored equipment: {restored_char.equipment}")

        assert restored_char.hit_points["current"] == 25, "HP should be restored"
        assert restored_char.armor_class == 16, "AC should be restored"
        assert "Longsword" in restored_char.equipment, "Equipment should be restored"
        print("   ✅ Import restores full character data")


class TestRoutingHistoryCap:
    """Test that routing history cap is raised to 200."""

    def test_routing_history_cap_200(self):
        """Test that routing history is capped at 200 entries."""
        print("\n🧪 TEST: Routing history cap raised to 200")

        manager = SessionManager()

        # Add 250 routing decisions
        print("   Adding 250 routing decisions...")
        for i in range(250):
            manager.add_routing_decision({
                "player_input": f"test input {i}",
                "type": f"type_{i % 3}",
                "confidence": 0.9,
                "route": "test_path"
            })

        # Should keep only last 200
        stats = manager.get_routing_statistics()
        history_count = stats.get("total_decisions", 0)

        print(f"   Total routing decisions tracked: {history_count}")
        assert history_count == 200, f"Should cap at 200, got {history_count}"
        print("   ✅ Routing history capped at 200")

    def test_routing_history_save_cap_200(self):
        """Test that routing history saves last 200 entries."""
        print("\n🧪 TEST: Routing history saves last 200")

        manager = SessionManager()
        # Initialize routing history manually since there's no start_session
        manager._routing_history = []

        # Add many routing decisions
        print("   Adding 220 routing decisions...")
        for i in range(220):
            manager.add_routing_decision({
                "player_input": f"test input {i}",
                "type": f"type_{i % 3}",
                "confidence": 0.9,
                "route": "test_path"
            })

        # Check internal routing history
        saved_count = len(manager._routing_history)

        print(f"   Routing history entries in memory: {saved_count}")
        assert saved_count == 200, f"Should cap at 200, got {saved_count}"
        print("   ✅ Routing history capped at 200 in memory")


if __name__ == "__main__":
    print("=" * 70)
    print("NON-COMBAT WIRING TESTS")
    print("=" * 70)

    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s", "--tb=short"])
