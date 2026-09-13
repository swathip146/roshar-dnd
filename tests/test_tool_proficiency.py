"""
Test tool proficiency gating for skill checks.

Tool proficiencies should mechanically matter: a character can't get proficiency
bonus on tool-gated checks (picking locks, disarming traps, etc.) without the
actual tool proficiency.
"""

import pytest
from components.character_manager import CharacterManager
from components.game_engine import GameEngine
from components.policy import PolicyEngine, PolicyProfile


@pytest.fixture
def game_engine():
    """Game engine with test characters."""
    print("\n🔧 [test_tool_proficiency] Setting up game engine")
    engine = GameEngine()

    # Rogue with thieves' tools proficiency
    rogue = {
        "character_id": "rogue",
        "name": "Sly Rogue",
        "level": 3,
        "proficiency_bonus": 2,
        "ability_scores": {"dexterity": 16, "intelligence": 12},
        "ability_modifiers": {"dexterity": 3, "intelligence": 1},
        "skills": {"sleight_of_hand": True},  # Proficient in sleight of hand
        "expertise_skills": [],
        "conditions": [],
        "features": [],
        "hit_points": {"current": 20, "maximum": 20, "temporary": 0},
        "armor_class": 15,
        "saving_throw_proficiencies": ["dexterity", "intelligence"],
        "character_class": "Rogue",
        "race": "Human",
        "background": "Criminal",
        "tool_proficiencies": ["thieves' tools", "disguise kit"],  # HAS tool proficiency
    }

    # Fighter without thieves' tools proficiency
    fighter = {
        "character_id": "fighter",
        "name": "Strong Fighter",
        "level": 3,
        "proficiency_bonus": 2,
        "ability_scores": {"dexterity": 14, "strength": 16},
        "ability_modifiers": {"dexterity": 2, "strength": 3},
        "skills": {"sleight_of_hand": True},  # Proficient in sleight of hand
        "expertise_skills": [],
        "conditions": [],
        "features": [],
        "hit_points": {"current": 30, "maximum": 30, "temporary": 0},
        "armor_class": 18,
        "saving_throw_proficiencies": ["strength", "constitution"],
        "character_class": "Fighter",
        "race": "Human",
        "background": "Soldier",
        "tool_proficiencies": [],  # NO tool proficiency
    }

    engine.add_character(rogue)
    engine.add_character(fighter)
    print("✅ [test_tool_proficiency] Characters and engine ready")
    return engine


class TestToolProficiencyHelper:
    """Test the has_tool_proficiency helper method."""

    def test_has_tool_proficiency_exact_match(self, game_engine):
        """Character with exact tool proficiency returns True."""
        print("🔍 [test_tool_proficiency] Testing exact match")
        assert game_engine.character_manager.has_tool_proficiency("rogue", "thieves' tools")
        print("✅ Rogue has thieves' tools")

    def test_has_tool_proficiency_case_insensitive(self, game_engine):
        """Tool proficiency check is case-insensitive."""
        print("🔍 [test_tool_proficiency] Testing case insensitivity")
        assert game_engine.character_manager.has_tool_proficiency("rogue", "THIEVES' TOOLS")
        assert game_engine.character_manager.has_tool_proficiency("rogue", "Thieves' Tools")
        print("✅ Case-insensitive matching works")

    def test_lacks_tool_proficiency(self, game_engine):
        """Character without tool proficiency returns False."""
        print("🔍 [test_tool_proficiency] Testing missing proficiency")
        assert not game_engine.character_manager.has_tool_proficiency("fighter", "thieves' tools")
        print("✅ Fighter lacks thieves' tools")

    def test_unknown_character(self, game_engine):
        """Unknown character returns False."""
        print("🔍 [test_tool_proficiency] Testing unknown character")
        assert not game_engine.character_manager.has_tool_proficiency("unknown", "thieves' tools")
        print("✅ Unknown character handled gracefully")


class TestGetSkillDataWithTool:
    """Test get_skill_data with required_tool parameter."""

    def test_skill_data_no_tool_required(self, game_engine):
        """Without required_tool, behavior is unchanged (backward compatibility)."""
        print("\n🔍 [test_tool_proficiency] Testing backward compatibility (no tool)")
        data = game_engine.character_manager.get_skill_data("rogue", "sleight_of_hand")

        # Should get proficiency bonus (skill proficient, no tool gate)
        assert data["is_proficient"]
        assert data["proficiency_bonus"] == 2
        assert data["modifier"] == 5  # 3 (dex) + 2 (prof)

        # Tool fields should not be present when no tool required
        assert "required_tool" not in data
        assert "has_required_tool" not in data
        assert "tool_proficiency_applied" not in data
        print("✅ Backward compatibility maintained")

    def test_skill_data_with_tool_proficient(self, game_engine):
        """With required_tool, proficient character gets bonus."""
        print("\n🔍 [test_tool_proficiency] Testing proficient character with tool")
        data = game_engine.character_manager.get_skill_data(
            "rogue", "sleight_of_hand", required_tool="thieves' tools"
        )

        # Should get proficiency bonus (has both skill and tool proficiency)
        assert data["is_proficient"]
        assert data["has_required_tool"]
        assert data["tool_proficiency_applied"]
        assert data["proficiency_bonus"] == 2
        assert data["modifier"] == 5  # 3 (dex) + 2 (prof)
        print("✅ Proficient character gets bonus")

    def test_skill_data_with_tool_not_proficient(self, game_engine):
        """With required_tool, non-proficient character loses bonus."""
        print("\n🔍 [test_tool_proficiency] Testing non-proficient character with tool gate")
        data = game_engine.character_manager.get_skill_data(
            "fighter", "sleight_of_hand", required_tool="thieves' tools"
        )

        # Should NOT get proficiency bonus (lacks tool proficiency)
        assert data["is_proficient"]  # Has skill proficiency...
        assert not data["has_required_tool"]  # ...but lacks tool proficiency
        assert not data["tool_proficiency_applied"]
        assert data["proficiency_bonus"] == 0  # No bonus applied
        assert data["modifier"] == 2  # 2 (dex) only, no proficiency bonus
        print("✅ Non-proficient character loses bonus")


class TestProcessSkillCheckWithTool:
    """Test process_skill_check with required_tool parameter."""

    def test_backward_compatibility_no_tool(self, game_engine):
        """Without required_tool, behavior is unchanged."""
        print("\n🎲 [test_tool_proficiency] Testing skill check backward compatibility")
        result = game_engine.process_skill_check({
            "actor": "rogue",
            "skill": "sleight_of_hand",
            "dc": 15,
            "context": {},
        })

        # Should succeed or fail based on roll, with proficiency applied
        assert "success" in result
        assert result["character_modifier"] == 5  # 3 (dex) + 2 (prof)

        # Tool fields should not be present
        assert "required_tool" not in result
        assert "has_required_tool" not in result
        assert "tool_proficiency_applied" not in result
        print(f"✅ Backward compatibility: modifier={result['character_modifier']}, success={result['success']}")

    def test_tool_gated_check_proficient(self, game_engine):
        """Rogue with thieves' tools gets proficiency bonus."""
        print("\n🎲 [test_tool_proficiency] Testing tool-gated check (proficient)")

        # Run multiple checks to verify bonus is consistently applied
        results = []
        for i in range(5):
            result = game_engine.process_skill_check({
                "actor": "rogue",
                "skill": "sleight_of_hand",
                "dc": 15,
                "context": {},
                "required_tool": "thieves' tools",
            })
            results.append(result)
            print(f"  Attempt {i+1}: roll={result['roll_total']}, modifier={result['character_modifier']}, success={result['success']}")

        # Verify tool proficiency was recognized and applied
        for result in results:
            assert result["required_tool"] == "thieves' tools"
            assert result["has_required_tool"]
            assert result["tool_proficiency_applied"]
            assert result["character_modifier"] == 5  # 3 (dex) + 2 (prof)

        print("✅ Rogue consistently gets proficiency bonus with thieves' tools")

    def test_tool_gated_check_not_proficient(self, game_engine):
        """Fighter without thieves' tools loses proficiency bonus."""
        print("\n🎲 [test_tool_proficiency] Testing tool-gated check (not proficient)")

        # Run multiple checks to verify penalty is consistently applied
        results = []
        for i in range(5):
            result = game_engine.process_skill_check({
                "actor": "fighter",
                "skill": "sleight_of_hand",
                "dc": 15,
                "context": {},
                "required_tool": "thieves' tools",
            })
            results.append(result)
            print(f"  Attempt {i+1}: roll={result['roll_total']}, modifier={result['character_modifier']}, success={result['success']}")

        # Verify tool proficiency was missing and penalty applied
        for result in results:
            assert result["required_tool"] == "thieves' tools"
            assert not result["has_required_tool"]
            assert not result["tool_proficiency_applied"]
            assert result["character_modifier"] == 2  # 2 (dex) only, no proficiency

        print("✅ Fighter consistently loses proficiency bonus without thieves' tools")

    def test_tool_proficiency_makes_difference(self, game_engine):
        """Verify tool proficiency makes a measurable difference in outcomes."""
        print("\n📊 [test_tool_proficiency] Measuring tool proficiency impact")

        # The rogue and fighter have different dex modifiers (3 vs 2) and
        # different proficiency bonuses when the tool gate applies:
        # - Rogue: +3 dex + 2 prof = +5 total (HAS thieves' tools)
        # - Fighter: +2 dex + 0 prof = +2 total (LACKS thieves' tools)
        #
        # The 3-point difference should be consistently visible.

        dc = 15
        num_trials = 20

        rogue_checks = [
            game_engine.process_skill_check({
                "actor": "rogue",
                "skill": "sleight_of_hand",
                "dc": dc,
                "required_tool": "thieves' tools",
            })
            for _ in range(num_trials)
        ]

        fighter_checks = [
            game_engine.process_skill_check({
                "actor": "fighter",
                "skill": "sleight_of_hand",
                "dc": dc,
                "required_tool": "thieves' tools",
            })
            for _ in range(num_trials)
        ]

        # Verify modifiers are consistently different
        for result in rogue_checks:
            assert result["character_modifier"] == 5

        for result in fighter_checks:
            assert result["character_modifier"] == 2

        # Count successes
        rogue_successes = sum(1 for r in rogue_checks if r["success"])
        fighter_successes = sum(1 for r in fighter_checks if r["success"])

        print(f"  Rogue (modifier +5): {rogue_successes}/{num_trials} successes")
        print(f"  Fighter (modifier +2): {fighter_successes}/{num_trials} successes")

        # The rogue should have equal or higher success rate due to +3 modifier advantage
        # (This is probabilistic, but over 20 trials the difference should be visible
        # unless we get extremely unlucky rolls)
        assert rogue_successes >= fighter_successes - 2, (
            f"Rogue should succeed at least as often as fighter (margin for variance). "
            f"Got rogue={rogue_successes}, fighter={fighter_successes}"
        )

        print("✅ Tool proficiency creates measurable advantage")


class TestDMToolsIntegration:
    """Test roll_skill_check DM tool with required_tool parameter."""

    def test_dm_tool_backward_compatibility(self, game_engine):
        """DM tool without required_tool works as before."""
        print("\n🔧 [test_tool_proficiency] Testing DM tool backward compatibility")

        # Import here to avoid circular dependencies
        from agents.dm_tools import roll_skill_check, set_dm_tool_context

        # Set context for DM tool
        set_dm_tool_context(game_engine=game_engine)

        # Haystack @tool decorator returns a Tool object; use .invoke() to call it
        result = roll_skill_check.invoke(skill="sleight_of_hand", dc=15, actor="rogue")

        assert "success" in result
        assert result["character_modifier"] == 5  # 3 (dex) + 2 (prof)
        assert "required_tool" not in result

        print(f"✅ DM tool backward compatible: modifier={result['character_modifier']}")

    def test_dm_tool_with_required_tool(self, game_engine):
        """DM tool with required_tool passes it through correctly."""
        print("\n🔧 [test_tool_proficiency] Testing DM tool with required_tool")

        from agents.dm_tools import roll_skill_check, set_dm_tool_context

        set_dm_tool_context(game_engine=game_engine)

        # Rogue with tool proficiency (use .invoke() for Haystack Tool objects)
        rogue_result = roll_skill_check.invoke(
            skill="sleight_of_hand",
            dc=15,
            actor="rogue",
            required_tool="thieves' tools"
        )

        assert rogue_result["has_required_tool"]
        assert rogue_result["tool_proficiency_applied"]
        assert rogue_result["character_modifier"] == 5

        # Fighter without tool proficiency
        fighter_result = roll_skill_check.invoke(
            skill="sleight_of_hand",
            dc=15,
            actor="fighter",
            required_tool="thieves' tools"
        )

        assert not fighter_result["has_required_tool"]
        assert not fighter_result["tool_proficiency_applied"]
        assert fighter_result["character_modifier"] == 2

        print("✅ DM tool correctly passes through tool proficiency requirements")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("🔧 TOOL PROFICIENCY TEST SUITE")
    print("="*70)
    pytest.main([__file__, "-v", "-s", "--tb=short"])
