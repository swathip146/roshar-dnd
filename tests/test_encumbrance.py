"""
Encumbrance system tests.

Verifies that:
1. Carried weight is computed from SRD item weights
2. Encumbrance tiers are calculated correctly
3. Speed penalties are applied in combat
4. Disadvantage is applied on STR/DEX/CON checks when heavily encumbered
5. Encumbrance status is visible via character state
"""

import pytest
from components.character_manager import CharacterManager
from components.game_engine import GameEngine
from components.policy import PolicyEngine
from components.combat.combat_session_manager import CombatSessionManager
from config.logging_config import get_logger

logger = get_logger(__name__)


@pytest.fixture
def character_manager():
    """Fresh character manager for each test."""
    return CharacterManager()


@pytest.fixture
def weak_character_id(character_manager):
    """Create a character with STR 10 (carrying capacity 150 lb)."""
    logger.info("🧪 Creating weak character (STR 10, capacity 150 lb)")
    char_id = character_manager.add_character({
        "character_id": "weak_test",
        "name": "Weak Test Character",
        "level": 1,
        "proficiency_bonus": 2,
        "ability_scores": {
            "strength": 10,
            "dexterity": 14,
            "constitution": 12,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10
        },
        "skills": {"athletics": True, "acrobatics": True},
        "equipment": []
    })
    logger.info(f"   ✓ Created character: {char_id}")
    return char_id


@pytest.fixture
def strong_character_id(character_manager):
    """Create a character with STR 20 (carrying capacity 300 lb)."""
    logger.info("🧪 Creating strong character (STR 20, capacity 300 lb)")
    char_id = character_manager.add_character({
        "character_id": "strong_test",
        "name": "Strong Test Character",
        "level": 1,
        "proficiency_bonus": 2,
        "ability_scores": {
            "strength": 20,
            "dexterity": 14,
            "constitution": 12,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10
        },
        "skills": {"athletics": True, "acrobatics": True},
        "equipment": []
    })
    logger.info(f"   ✓ Created character: {char_id}")
    return char_id


class TestCarriedWeight:
    """Test carried weight computation from SRD item weights."""

    def test_empty_inventory(self, character_manager, weak_character_id):
        """Empty inventory should have 0 weight."""
        logger.info("🧪 TEST: Empty inventory weight")
        weight = character_manager.get_carried_weight(weak_character_id)
        logger.info(f"   Carried weight: {weight} lb")
        assert weight == 0.0, "Empty inventory should weigh 0 lb"
        logger.info("   ✓ PASS: Empty inventory has 0 weight")

    def test_single_item(self, character_manager, weak_character_id):
        """Single item weight from SRD."""
        logger.info("🧪 TEST: Single item weight (Longsword)")
        character_manager.add_equipment(weak_character_id, "Longsword")
        weight = character_manager.get_carried_weight(weak_character_id)
        logger.info(f"   Carried weight: {weight} lb (SRD: Longsword = 3 lb)")
        assert weight == 3.0, "Longsword should weigh 3 lb (SRD)"
        logger.info("   ✓ PASS: Single item weight correct")

    def test_multiple_items(self, character_manager, weak_character_id):
        """Multiple items sum correctly."""
        logger.info("🧪 TEST: Multiple items weight sum")
        items = ["Longsword", "Shield", "Chain Mail"]  # 3 + 6 + 55 = 64 lb
        for item in items:
            character_manager.add_equipment(weak_character_id, item)

        weight = character_manager.get_carried_weight(weak_character_id)
        logger.info(f"   Items: {items}")
        logger.info(f"   Carried weight: {weight} lb (expected 64 lb)")
        assert weight == 64.0, "Longsword (3) + Shield (6) + Chain Mail (55) = 64 lb"
        logger.info("   ✓ PASS: Multiple items sum correctly")

    def test_unknown_item_treated_as_weightless(self, character_manager, weak_character_id):
        """Unknown items default to 0 weight."""
        logger.info("🧪 TEST: Unknown item weight")
        character_manager.add_equipment(weak_character_id, "Mysterious Artifact")
        weight = character_manager.get_carried_weight(weak_character_id)
        logger.info(f"   Carried weight: {weight} lb (unknown item → 0 lb)")
        assert weight == 0.0, "Unknown item should default to 0 weight"
        logger.info("   ✓ PASS: Unknown items are weightless")

    def test_remove_equipment_reduces_weight(self, character_manager, weak_character_id):
        """Removing equipment reduces carried weight."""
        logger.info("🧪 TEST: Removing equipment reduces weight")
        character_manager.add_equipment(weak_character_id, "Longsword")
        character_manager.add_equipment(weak_character_id, "Shield")

        initial_weight = character_manager.get_carried_weight(weak_character_id)
        logger.info(f"   Initial weight: {initial_weight} lb")

        character_manager.remove_equipment(weak_character_id, "Shield")
        final_weight = character_manager.get_carried_weight(weak_character_id)
        logger.info(f"   After removing Shield: {final_weight} lb")

        assert final_weight < initial_weight, "Weight should decrease after removing item"
        assert final_weight == 3.0, "Should only have Longsword (3 lb) remaining"
        logger.info("   ✓ PASS: Removing equipment reduces weight")


class TestEncumbranceTiers:
    """Test encumbrance tier calculation (5e PHB 176)."""

    def test_unencumbered(self, character_manager, weak_character_id):
        """Character under STR × 5 is unencumbered."""
        logger.info("🧪 TEST: Unencumbered tier (STR 10: 0-50 lb)")
        # STR 10 = 150 capacity, normal up to 50 lb
        character_manager.add_equipment(weak_character_id, "Longsword")  # 3 lb

        enc = character_manager.get_encumbrance(weak_character_id)
        logger.info(f"   Weight: {enc['weight']} / {enc['capacity']} lb")
        logger.info(f"   Tier: {enc['encumbrance_level']}")
        logger.info(f"   Speed penalty: {enc['speed_penalty']} ft")
        logger.info(f"   Disadvantage: {enc['has_disadvantage']}")

        assert enc["encumbrance_level"] == "normal", "Should be unencumbered"
        assert enc["speed_penalty"] == 0, "No speed penalty when unencumbered"
        assert not enc["has_disadvantage"], "No disadvantage when unencumbered"
        logger.info("   ✓ PASS: Unencumbered tier correct")

    def test_encumbered(self, character_manager, weak_character_id):
        """Character between STR × 5 and STR × 10 is encumbered (-10 speed)."""
        logger.info("🧪 TEST: Encumbered tier (STR 10: 51-100 lb)")
        # STR 10: encumbered at 51-100 lb
        items = ["Chain Mail", "Shield"]  # 55 + 6 = 61 lb
        for item in items:
            character_manager.add_equipment(weak_character_id, item)

        enc = character_manager.get_encumbrance(weak_character_id)
        logger.info(f"   Weight: {enc['weight']} / {enc['capacity']} lb")
        logger.info(f"   Tier: {enc['encumbrance_level']}")
        logger.info(f"   Speed penalty: {enc['speed_penalty']} ft")
        logger.info(f"   Disadvantage: {enc['has_disadvantage']}")

        assert enc["encumbrance_level"] == "encumbered", "Should be encumbered"
        assert enc["speed_penalty"] == 10, "Encumbered: -10 ft speed"
        assert not enc["has_disadvantage"], "No disadvantage when encumbered (only heavy)"
        logger.info("   ✓ PASS: Encumbered tier correct")

    def test_heavily_encumbered(self, character_manager, weak_character_id):
        """Character between STR × 10 and STR × 15 is heavily encumbered (-20 speed, disadvantage)."""
        logger.info("🧪 TEST: Heavily encumbered tier (STR 10: 101-150 lb)")
        # STR 10: heavily encumbered at 101-150 lb
        # Load up: Chain Mail (55) + 2x Greatsword (6 each) + 11x Javelin (2 each) + Pike (18)
        # = 55 + 12 + 22 + 18 = 107 lb
        items = ["Chain Mail", "Greatsword", "Greatsword", "Pike"] + ["Javelin"] * 11
        for item in items:
            character_manager.add_equipment(weak_character_id, item)

        enc = character_manager.get_encumbrance(weak_character_id)
        logger.info(f"   Weight: {enc['weight']} / {enc['capacity']} lb")
        logger.info(f"   Tier: {enc['encumbrance_level']}")
        logger.info(f"   Speed penalty: {enc['speed_penalty']} ft")
        logger.info(f"   Disadvantage: {enc['has_disadvantage']}")

        assert enc["encumbrance_level"] == "heavily_encumbered", "Should be heavily encumbered"
        assert enc["speed_penalty"] == 20, "Heavily encumbered: -20 ft speed"
        assert enc["has_disadvantage"], "Heavily encumbered: disadvantage on STR/DEX/CON checks"
        logger.info("   ✓ PASS: Heavily encumbered tier correct")

    def test_over_capacity(self, character_manager, weak_character_id):
        """Character over STR × 15 is over capacity."""
        logger.info("🧪 TEST: Over capacity (STR 10: 151+ lb)")
        # STR 10: over capacity at 151+ lb
        # Load up: 3x Chain Mail (55 each) = 165 lb
        for _ in range(3):
            character_manager.add_equipment(weak_character_id, "Chain Mail")

        enc = character_manager.get_encumbrance(weak_character_id)
        logger.info(f"   Weight: {enc['weight']} / {enc['capacity']} lb")
        logger.info(f"   Tier: {enc['encumbrance_level']}")

        assert enc["encumbrance_level"] == "over_capacity", "Should be over capacity"
        assert "error" in enc, "Should have error message"
        logger.info("   ✓ PASS: Over capacity tier correct")


class TestCombatSpeedPenalty:
    """Test that encumbrance speed penalties apply in combat."""

    def test_unencumbered_has_full_speed(self, character_manager, weak_character_id):
        """Unencumbered character has full movement in combat."""
        logger.info("🧪 TEST: Unencumbered combat movement (30 ft)")

        # Create minimal combat state
        combat_state = {
            "active_combatants": [weak_character_id],
            "combatant_states": {
                weak_character_id: {"is_hostile": False}
            },
            "round_number": 1,
            "current_turn_index": 0
        }

        # Create combat manager (we'll use just _reset_movement)
        from components.combat.combat_session_manager import CombatSessionManager
        combat_mgr = CombatSessionManager(
            combat_state=combat_state,
            game_engine=None,  # Not needed for movement reset
            character_manager=character_manager,
            dnd_engine_wrapper=None,
            combat_action_resolver=None,
            combat_narrative_generator=None,
            npc_ai_agent=None
        )

        combat_mgr._reset_movement()
        remaining = combat_state["combatant_states"][weak_character_id]["movement_remaining"]

        logger.info(f"   Movement remaining: {remaining} ft (expected 30 ft)")
        assert remaining == 30, "Unencumbered should have full 30 ft movement"
        logger.info("   ✓ PASS: Unencumbered has full speed in combat")

    def test_encumbered_reduced_speed(self, character_manager, weak_character_id):
        """Encumbered character has -10 ft speed in combat."""
        logger.info("🧪 TEST: Encumbered combat movement (20 ft)")

        # Load character to encumbered tier
        items = ["Chain Mail", "Shield"]  # 61 lb (encumbered for STR 10)
        for item in items:
            character_manager.add_equipment(weak_character_id, item)

        combat_state = {
            "active_combatants": [weak_character_id],
            "combatant_states": {
                weak_character_id: {"is_hostile": False}
            },
            "round_number": 1,
            "current_turn_index": 0
        }

        from components.combat.combat_session_manager import CombatSessionManager
        combat_mgr = CombatSessionManager(
            combat_state=combat_state,
            game_engine=None,
            character_manager=character_manager,
            dnd_engine_wrapper=None,
            combat_action_resolver=None,
            combat_narrative_generator=None,
            npc_ai_agent=None
        )

        combat_mgr._reset_movement()
        remaining = combat_state["combatant_states"][weak_character_id]["movement_remaining"]

        logger.info(f"   Movement remaining: {remaining} ft (expected 20 ft = 30 - 10)")
        assert remaining == 20, "Encumbered should have 30 - 10 = 20 ft movement"
        logger.info("   ✓ PASS: Encumbered speed penalty applied in combat")

    def test_heavily_encumbered_severely_reduced_speed(self, character_manager, weak_character_id):
        """Heavily encumbered character has -20 ft speed in combat."""
        logger.info("🧪 TEST: Heavily encumbered combat movement (10 ft)")

        # Load character to heavily encumbered tier
        items = ["Chain Mail", "Greatsword", "Greatsword", "Pike"] + ["Javelin"] * 11  # 107 lb
        for item in items:
            character_manager.add_equipment(weak_character_id, item)

        combat_state = {
            "active_combatants": [weak_character_id],
            "combatant_states": {
                weak_character_id: {"is_hostile": False}
            },
            "round_number": 1,
            "current_turn_index": 0
        }

        from components.combat.combat_session_manager import CombatSessionManager
        combat_mgr = CombatSessionManager(
            combat_state=combat_state,
            game_engine=None,
            character_manager=character_manager,
            dnd_engine_wrapper=None,
            combat_action_resolver=None,
            combat_narrative_generator=None,
            npc_ai_agent=None
        )

        combat_mgr._reset_movement()
        remaining = combat_state["combatant_states"][weak_character_id]["movement_remaining"]

        logger.info(f"   Movement remaining: {remaining} ft (expected 10 ft = 30 - 20)")
        assert remaining == 10, "Heavily encumbered should have 30 - 20 = 10 ft movement"
        logger.info("   ✓ PASS: Heavily encumbered speed penalty applied in combat")


class TestHeavyEncumbranceDisadvantage:
    """Test that heavily encumbered characters have disadvantage on STR/DEX/CON checks."""

    def test_athletics_disadvantage_when_heavily_encumbered(self, character_manager, weak_character_id):
        """Heavily encumbered character has disadvantage on Athletics (STR)."""
        logger.info("🧪 TEST: Heavily encumbered disadvantage on Athletics (STR)")

        # Load to heavily encumbered
        items = ["Chain Mail", "Greatsword", "Greatsword", "Pike"] + ["Javelin"] * 11  # 107 lb
        for item in items:
            character_manager.add_equipment(weak_character_id, item)

        # Create game engine (it creates its own internal character manager)
        from components.policy import PolicyProfile
        game_engine = GameEngine(PolicyProfile.RAW)
        # Copy character to game engine's character manager
        game_engine.character_manager.characters[weak_character_id] = character_manager.characters[weak_character_id]

        check_request = {
            "actor": weak_character_id,
            "skill": "athletics",
            "dc": 15,
            "context": {}
        }

        result = game_engine.process_skill_check(check_request)

        logger.info(f"   Advantage state: {result['advantage_state']}")
        logger.info(f"   Disadvantage sources: {result['disadvantage_sources']}")

        assert result["advantage_state"] == "disadvantage", "Should have disadvantage"
        assert any("encumbered" in str(src).lower() for src in result["disadvantage_sources"]), \
            "Disadvantage should be from encumbrance"
        logger.info("   ✓ PASS: Heavily encumbered causes disadvantage on Athletics (STR)")

    def test_acrobatics_disadvantage_when_heavily_encumbered(self, character_manager, weak_character_id):
        """Heavily encumbered character has disadvantage on Acrobatics (DEX)."""
        logger.info("🧪 TEST: Heavily encumbered disadvantage on Acrobatics (DEX)")

        # Load to heavily encumbered
        items = ["Chain Mail", "Greatsword", "Greatsword", "Pike"] + ["Javelin"] * 11
        for item in items:
            character_manager.add_equipment(weak_character_id, item)

        from components.policy import PolicyProfile
        game_engine = GameEngine(PolicyProfile.RAW)
        # Copy character to game engine's character manager
        game_engine.character_manager.characters[weak_character_id] = character_manager.characters[weak_character_id]

        check_request = {
            "actor": weak_character_id,
            "skill": "acrobatics",
            "dc": 15,
            "context": {}
        }

        result = game_engine.process_skill_check(check_request)

        logger.info(f"   Advantage state: {result['advantage_state']}")
        logger.info(f"   Disadvantage sources: {result['disadvantage_sources']}")

        assert result["advantage_state"] == "disadvantage", "Should have disadvantage"
        assert any("encumbered" in str(src).lower() for src in result["disadvantage_sources"]), \
            "Disadvantage should be from encumbrance"
        logger.info("   ✓ PASS: Heavily encumbered causes disadvantage on Acrobatics (DEX)")

    def test_no_disadvantage_on_wisdom_checks(self, character_manager, weak_character_id):
        """Heavily encumbered character has NO disadvantage on Wisdom checks."""
        logger.info("🧪 TEST: No encumbrance disadvantage on Perception (WIS)")

        # Load to heavily encumbered
        items = ["Chain Mail", "Greatsword", "Greatsword", "Pike"] + ["Javelin"] * 11
        for item in items:
            character_manager.add_equipment(weak_character_id, item)

        # Add perception proficiency
        character_manager.characters[weak_character_id].skills["perception"] = True

        from components.policy import PolicyProfile
        game_engine = GameEngine(PolicyProfile.RAW)
        # Copy character to game engine's character manager
        game_engine.character_manager.characters[weak_character_id] = character_manager.characters[weak_character_id]

        check_request = {
            "actor": weak_character_id,
            "skill": "perception",
            "dc": 15,
            "context": {}
        }

        result = game_engine.process_skill_check(check_request)

        logger.info(f"   Advantage state: {result['advantage_state']}")
        logger.info(f"   Disadvantage sources: {result['disadvantage_sources']}")

        # Should NOT have disadvantage from encumbrance (Perception uses WIS)
        assert not any("encumbered" in str(src).lower() for src in result["disadvantage_sources"]), \
            "Encumbrance should NOT affect Wisdom checks"
        logger.info("   ✓ PASS: Encumbrance does not affect non-physical checks")

    def test_no_disadvantage_when_lightly_loaded(self, character_manager, weak_character_id):
        """Lightly loaded character has NO disadvantage even on STR checks."""
        logger.info("🧪 TEST: No disadvantage when lightly loaded")

        # Add just a longsword (3 lb - well under 50 lb normal limit)
        character_manager.add_equipment(weak_character_id, "Longsword")

        from components.policy import PolicyProfile
        game_engine = GameEngine(PolicyProfile.RAW)
        # Copy character to game engine's character manager
        game_engine.character_manager.characters[weak_character_id] = character_manager.characters[weak_character_id]

        check_request = {
            "actor": weak_character_id,
            "skill": "athletics",
            "dc": 15,
            "context": {}
        }

        result = game_engine.process_skill_check(check_request)

        logger.info(f"   Advantage state: {result['advantage_state']}")
        logger.info(f"   Weight: 3 lb (normal limit: 50 lb)")

        assert result["advantage_state"] == "normal", "Should have normal rolls (no disadvantage)"
        logger.info("   ✓ PASS: Lightly loaded has no disadvantage")


class TestEncumbranceVisibility:
    """Test that encumbrance status is visible via character state."""

    def test_character_summary_includes_encumbrance(self, character_manager, weak_character_id):
        """get_character_summary includes encumbrance data."""
        logger.info("🧪 TEST: Character summary includes encumbrance")

        character_manager.add_equipment(weak_character_id, "Chain Mail")  # 55 lb
        summary = character_manager.get_character_summary(weak_character_id)

        logger.info(f"   Summary keys: {list(summary.keys())}")
        assert "encumbrance" in summary, "Summary should include encumbrance"

        enc = summary["encumbrance"]
        logger.info(f"   Encumbrance: {enc['encumbrance_level']}, {enc['weight']}/{enc['capacity']} lb")
        assert "encumbrance_level" in enc, "Encumbrance should have level"
        assert "weight" in enc, "Encumbrance should have weight"
        assert "capacity" in enc, "Encumbrance should have capacity"
        logger.info("   ✓ PASS: Character summary includes encumbrance")

    def test_dm_tools_get_character_state_includes_encumbrance(self, character_manager, weak_character_id):
        """DM tools get_character_state includes encumbrance."""
        logger.info("🧪 TEST: DM tools get_character_state includes encumbrance")

        # Set up DM tool context
        from agents.dm_tools import set_dm_tool_context, get_character_state, clear_dm_tool_context

        try:
            set_dm_tool_context(character_manager=character_manager)

            # Load character
            character_manager.add_equipment(weak_character_id, "Chain Mail")

            # Get state via DM tool (Haystack tool requires .invoke())
            state = get_character_state.invoke(actor=weak_character_id)

            logger.info(f"   State keys: {list(state.keys())}")
            assert "encumbrance" in state, "DM tool state should include encumbrance"

            enc = state["encumbrance"]
            logger.info(f"   Encumbrance: {enc['encumbrance_level']}, {enc['weight']}/{enc['capacity']} lb")
            logger.info("   ✓ PASS: DM tools include encumbrance in character state")
        finally:
            clear_dm_tool_context()


class TestEncumbranceDynamics:
    """Test that encumbrance updates dynamically as equipment changes."""

    def test_encumbrance_tier_changes_with_equipment(self, character_manager, weak_character_id):
        """Encumbrance tier updates as items are added/removed."""
        logger.info("🧪 TEST: Dynamic encumbrance tier updates")

        # Start unencumbered
        enc = character_manager.get_encumbrance(weak_character_id)
        logger.info(f"   Initial: {enc['encumbrance_level']} ({enc['weight']} lb)")
        assert enc["encumbrance_level"] == "normal", "Should start unencumbered"

        # Add equipment to reach encumbered tier
        character_manager.add_equipment(weak_character_id, "Chain Mail")  # 55 lb
        enc = character_manager.get_encumbrance(weak_character_id)
        logger.info(f"   After Chain Mail: {enc['encumbrance_level']} ({enc['weight']} lb)")
        assert enc["encumbrance_level"] == "encumbered", "Should be encumbered at 55 lb"

        # Add more to reach heavily encumbered
        for _ in range(11):
            character_manager.add_equipment(weak_character_id, "Javelin")  # +22 lb = 77 lb total
        character_manager.add_equipment(weak_character_id, "Pike")  # +18 = 95 lb
        character_manager.add_equipment(weak_character_id, "Greatsword")  # +6 = 101 lb

        enc = character_manager.get_encumbrance(weak_character_id)
        logger.info(f"   After more items: {enc['encumbrance_level']} ({enc['weight']} lb)")
        assert enc["encumbrance_level"] == "heavily_encumbered", "Should be heavily encumbered at 101 lb"

        # Remove items to return to encumbered
        character_manager.remove_equipment(weak_character_id, "Greatsword")
        character_manager.remove_equipment(weak_character_id, "Pike")
        for _ in range(11):
            character_manager.remove_equipment(weak_character_id, "Javelin")

        enc = character_manager.get_encumbrance(weak_character_id)
        logger.info(f"   After removing items: {enc['encumbrance_level']} ({enc['weight']} lb)")
        assert enc["encumbrance_level"] == "encumbered", "Should return to encumbered at 55 lb"

        logger.info("   ✓ PASS: Encumbrance tier updates dynamically")

    def test_strength_increase_changes_capacity(self, character_manager, weak_character_id):
        """Increasing STR increases carrying capacity and may change tier."""
        logger.info("🧪 TEST: STR increase changes capacity")

        # Load to heavily encumbered for STR 10
        items = ["Chain Mail", "Greatsword", "Greatsword", "Pike"] + ["Javelin"] * 11  # 107 lb
        for item in items:
            character_manager.add_equipment(weak_character_id, item)

        enc = character_manager.get_encumbrance(weak_character_id)
        logger.info(f"   STR 10: {enc['encumbrance_level']} ({enc['weight']}/{enc['capacity']} lb)")
        assert enc["encumbrance_level"] == "heavily_encumbered", "Should be heavily encumbered"

        # Increase STR to 20 (capacity now 300 lb instead of 150 lb)
        character = character_manager.characters[weak_character_id]
        character.ability_scores["strength"] = 20
        # Recalculate modifier inline (no recalculate_modifiers method)
        character.ability_modifiers["strength"] = (20 - 10) // 2

        enc = character_manager.get_encumbrance(weak_character_id)
        logger.info(f"   STR 20: {enc['encumbrance_level']} ({enc['weight']}/{enc['capacity']} lb)")
        # STR 20 = 300 capacity, normal 0-100, encumbered 101-200, heavily 201-300
        # 107 lb is in the encumbered range for STR 20, which is much better than heavily encumbered for STR 10
        assert enc["encumbrance_level"] == "encumbered", "107 lb should be encumbered (not heavily) for STR 20"
        assert enc["speed_penalty"] == 10, "Should have -10 ft penalty (not -20)"
        assert not enc["has_disadvantage"], "Should NOT have disadvantage (only heavy encumbrance gives disadvantage)"

        logger.info("   ✓ PASS: STR increase improves encumbrance tier (heavily → encumbered)")


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s"])
