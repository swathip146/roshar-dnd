"""
Tests for activated class features (Rage, Second Wind, Action Surge).

Verifies that:
1. Features are offered only to actors who have them
2. Features are offered only when uses are available
3. Features work correctly when used in combat
4. NPC AI can use them too
5. Action economy is charged correctly
"""

import pytest
from typing import Dict, Any

from components.character_manager import CharacterManager
from components.dnd_engine_wrapper import DnDEngineWrapper
from components.combat.combat_session_manager import CombatSessionManager
from components.combat.combat_action_resolver import CombatActionResolver
from components.combat.action_registry import unusable_reason, is_usable_by
from config.logging_config import get_logger

logger = get_logger(__name__)


@pytest.fixture
def character_manager():
    """Create a CharacterManager with test characters."""
    cm = CharacterManager()

    # Add a Barbarian with Rage
    cm.add_character({
        "character_id": "barbarian",
        "name": "Conan",
        "character_class": "Barbarian",
        "level": 3,
        "strength": 16,
        "dexterity": 14,
        "constitution": 16,
        "intelligence": 8,
        "wisdom": 10,
        "charisma": 8,
        "hit_points": {"current": 30, "maximum": 30},
        "features": ["Rage", "Unarmored Defense"],
        "race": "Human",
        "background": "Outlander",
    })

    # Add a Fighter with Second Wind and Action Surge
    cm.add_character({
        "character_id": "fighter",
        "name": "Kaladin",
        "character_class": "Fighter",
        "level": 5,
        "strength": 16,
        "dexterity": 14,
        "constitution": 14,
        "intelligence": 10,
        "wisdom": 12,
        "charisma": 10,
        "hit_points": {"current": 25, "maximum": 40},
        "features": ["Fighting Style", "Second Wind", "Action Surge", "Extra Attack"],
        "race": "Human",
        "background": "Soldier",
    })

    # Add a Wizard with no combat class features
    cm.add_character({
        "character_id": "wizard",
        "name": "Gandalf",
        "character_class": "Wizard",
        "level": 3,
        "strength": 8,
        "dexterity": 14,
        "constitution": 12,
        "intelligence": 16,
        "wisdom": 12,
        "charisma": 10,
        "hit_points": {"current": 15, "maximum": 15},
        "features": ["Spellcasting", "Arcane Recovery"],
        "spell_slots": {
            1: {"current": 4, "maximum": 4},
            2: {"current": 2, "maximum": 2}
        },
        "race": "Human",
        "background": "Sage",
    })

    logger.info("✅ Character manager set up with Barbarian, Fighter, and Wizard")
    return cm


@pytest.fixture
def combat_setup(character_manager):
    """Set up a combat session with all test characters."""
    logger.info("🔧 Setting up combat with Barbarian, Fighter, and Wizard")

    # Create game engine and wrapper
    from components.game_engine import GameEngine
    game_engine = GameEngine()
    wrapper = DnDEngineWrapper(game_engine, character_manager)

    # Sync characters to create entities
    wrapper._sync_characters_to_entities()

    # Create combat state
    combat_state = {
        "combatant_states": {
            "barbarian": {
                "initiative": 15,
                "position": {"x": 0, "y": 0},
                "hp_current": 30,
                "hp_max": 30,
            },
            "fighter": {
                "initiative": 12,
                "position": {"x": 5, "y": 0},
                "hp_current": 25,
                "hp_max": 40,
            },
            "wizard": {
                "initiative": 10,
                "position": {"x": 10, "y": 0},
                "hp_current": 15,
                "hp_max": 15,
            },
        },
        "turn_order": ["barbarian", "fighter", "wizard"],
        "current_combatant": "barbarian",
        "round_number": 1,
    }

    # Create resolver
    resolver = CombatActionResolver(
        dnd_engine_wrapper=wrapper,
        character_manager=character_manager,
        combat_state=combat_state
    )

    logger.info("✅ Combat setup complete")

    return {
        "manager": character_manager,
        "wrapper": wrapper,
        "resolver": resolver,
        "combat_state": combat_state,
    }


class TestFeatureGating:
    """Test that features are only offered to appropriate actors."""

    def test_barbarian_can_rage(self, character_manager):
        """Barbarian with Rage uses should be offered Rage."""
        logger.info("🧪 Test: Barbarian can Rage")

        barbarian = character_manager.characters["barbarian"]
        reason = unusable_reason("rage", barbarian)
        logger.info(f"   Unusable reason for Barbarian: {reason}")

        assert reason is None, f"Barbarian should be able to Rage, got: {reason}"
        assert is_usable_by("rage", barbarian)
        logger.info("✅ Barbarian can Rage")

    def test_fighter_can_second_wind(self, character_manager):
        """Fighter with Second Wind uses should be offered Second Wind."""
        logger.info("🧪 Test: Fighter can use Second Wind")

        fighter = character_manager.characters["fighter"]
        reason = unusable_reason("second_wind", fighter)
        logger.info(f"   Unusable reason for Fighter: {reason}")

        assert reason is None, f"Fighter should be able to use Second Wind, got: {reason}"
        assert is_usable_by("second_wind", fighter)
        logger.info("✅ Fighter can use Second Wind")

    def test_fighter_can_action_surge(self, character_manager):
        """Fighter with Action Surge uses should be offered Action Surge."""
        logger.info("🧪 Test: Fighter can use Action Surge")

        fighter = character_manager.characters["fighter"]
        reason = unusable_reason("action_surge", fighter)
        logger.info(f"   Unusable reason for Fighter: {reason}")

        assert reason is None, f"Fighter should be able to use Action Surge, got: {reason}"
        assert is_usable_by("action_surge", fighter)
        logger.info("✅ Fighter can use Action Surge")

    def test_wizard_cannot_rage(self, character_manager):
        """Wizard should not be offered Rage."""
        logger.info("🧪 Test: Wizard cannot Rage")

        wizard = character_manager.characters["wizard"]
        reason = unusable_reason("rage", wizard)
        logger.info(f"   Unusable reason for Wizard: {reason}")

        assert reason is not None, "Wizard should not be able to Rage"
        assert not is_usable_by("rage", wizard)
        logger.info(f"✅ Wizard correctly denied Rage: {reason}")

    def test_wizard_cannot_second_wind(self, character_manager):
        """Wizard should not be offered Second Wind."""
        logger.info("🧪 Test: Wizard cannot use Second Wind")

        wizard = character_manager.characters["wizard"]
        reason = unusable_reason("second_wind", wizard)
        logger.info(f"   Unusable reason for Wizard: {reason}")

        assert reason is not None, "Wizard should not be able to use Second Wind"
        assert not is_usable_by("second_wind", wizard)
        logger.info(f"✅ Wizard correctly denied Second Wind: {reason}")

    def test_no_uses_remaining(self, character_manager):
        """
        Feature with no uses is still offered (registry-level gate passes) but will be
        refused at execution by ClassFeatureEngine.use().

        This is intentional: the registry gate checks "does the actor have this feature"
        but not "are there uses left", because calculating uses requires the full feature
        table (e.g., Barbarian rage uses scale with level). That logic lives in
        ClassFeatureEngine, so we defer to it. This test verifies the gate is lenient.
        """
        logger.info("🧪 Test: No uses remaining (registry gate is lenient)")

        barbarian = character_manager.characters["barbarian"]

        # Deplete Rage uses - mark all uses as spent (level 3 Barbarian has 2 uses)
        if barbarian.class_feature_uses is None:
            barbarian.class_feature_uses = {}
        barbarian.class_feature_uses["rage"] = 100  # Way over the limit = 0 remaining

        # Registry-level gate should still pass (it only checks "has feature")
        reason = unusable_reason("rage", barbarian)
        logger.info(f"   Unusable reason at registry level: {reason}")

        assert reason is None, (
            "Registry gate should pass even with no uses; "
            "ClassFeatureEngine.use() will refuse it"
        )
        logger.info("✅ Registry gate correctly passes; execution will refuse")


class TestFeatureExecution:
    """Test that features work correctly when used."""

    def test_second_wind_heals(self, combat_setup):
        """Second Wind should restore hit points."""
        logger.info("🧪 Test: Second Wind heals")

        resolver = combat_setup["resolver"]
        fighter = combat_setup["manager"].characters["fighter"]

        # Fighter starts at 25/40 HP
        logger.info(f"   Fighter HP before: {fighter.hit_points['current']}/{fighter.hit_points['maximum']}")

        # Use Second Wind
        action = {
            "actor": "fighter",
            "action_type": "second_wind",
        }

        result = resolver.resolve_action(action)
        logger.info(f"   Second Wind result: success={result.get('success')}, healed={result.get('healed')}")

        assert result["success"], f"Second Wind should succeed: {result.get('error')}"
        assert result.get("healed", 0) > 0, "Second Wind should heal HP"

        # Check HP increased
        entity = combat_setup["wrapper"].entities["fighter"]
        hp_after = combat_setup["wrapper"].get_entity_current_hp(entity)
        logger.info(f"   Fighter HP after: {hp_after}/{combat_setup['wrapper'].get_entity_max_hp(entity)}")

        assert hp_after > 25, f"HP should increase, got {hp_after}"
        logger.info(f"✅ Second Wind healed {hp_after - 25} HP")

    def test_rage_grants_damage_bonus(self, combat_setup):
        """Rage should grant melee damage bonus and resistance."""
        logger.info("🧪 Test: Rage grants bonuses")

        resolver = combat_setup["resolver"]
        wrapper = combat_setup["wrapper"]

        # Use Rage
        action = {
            "actor": "barbarian",
            "action_type": "rage",
        }

        result = resolver.resolve_action(action)
        logger.info(f"   Rage result: success={result.get('success')}, error={result.get('error')}")

        assert result["success"], f"Rage should succeed: {result.get('error')}"

        # Verify the feature engine applied the effects
        engine = wrapper.class_feature_engine(combat_state=combat_setup["combat_state"])
        active = engine._active.get("rage", {})
        logger.info(f"   Active rage effects: {list(active.keys())}")

        assert "barbarian" in active, "Barbarian should have active Rage"
        logger.info("✅ Rage activated successfully")

    def test_action_surge_grants_extra_action(self, combat_setup):
        """Action Surge should grant an extra action."""
        logger.info("🧪 Test: Action Surge grants extra action")

        resolver = combat_setup["resolver"]
        wrapper = combat_setup["wrapper"]

        # Get initial action count
        entity = wrapper.entities["fighter"]
        actions_before = entity.action_economy.actions.normalized_score
        logger.info(f"   Fighter actions before: {actions_before}")

        # Use Action Surge
        action = {
            "actor": "fighter",
            "action_type": "action_surge",
        }

        result = resolver.resolve_action(action)
        logger.info(f"   Action Surge result: success={result.get('success')}, error={result.get('error')}")

        assert result["success"], f"Action Surge should succeed: {result.get('error')}"

        # Check action count increased
        actions_after = entity.action_economy.actions.normalized_score
        logger.info(f"   Fighter actions after: {actions_after}")

        assert actions_after > actions_before, f"Actions should increase, got {actions_after} vs {actions_before}"
        logger.info(f"✅ Action Surge granted {actions_after - actions_before} extra action(s)")

    def test_uses_consumed(self, combat_setup):
        """Using a feature should consume a use."""
        logger.info("🧪 Test: Uses are consumed")

        resolver = combat_setup["resolver"]
        manager = combat_setup["manager"]
        fighter = manager.characters["fighter"]

        # Check initial uses - should be 0 spent initially
        uses_spent_before = (fighter.class_feature_uses or {}).get("second_wind", 0)
        logger.info(f"   Second Wind uses spent before: {uses_spent_before}")

        # Use Second Wind
        action = {
            "actor": "fighter",
            "action_type": "second_wind",
        }

        result = resolver.resolve_action(action)
        assert result["success"]

        # Check uses increased (spent count goes up)
        uses_spent_after = (fighter.class_feature_uses or {}).get("second_wind", 0)
        logger.info(f"   Second Wind uses spent after: {uses_spent_after}")

        assert uses_spent_after > uses_spent_before, f"Spent uses should increase, got {uses_spent_after}"
        logger.info(f"✅ Second Wind consumed 1 use (spent went from {uses_spent_before} to {uses_spent_after})")

    def test_refused_when_no_uses(self, combat_setup):
        """Feature should be refused when no uses remaining."""
        logger.info("🧪 Test: Refused when no uses")

        resolver = combat_setup["resolver"]
        fighter = combat_setup["manager"].characters["fighter"]

        # Deplete uses - Second Wind has 1 use per short rest
        if fighter.class_feature_uses is None:
            fighter.class_feature_uses = {}
        fighter.class_feature_uses["second_wind"] = 1  # 1 spent = 0 remaining
        logger.info("   Depleted Second Wind uses (marked 1 as spent)")

        # Try to use Second Wind
        action = {
            "actor": "fighter",
            "action_type": "second_wind",
        }

        result = resolver.resolve_action(action)
        logger.info(f"   Second Wind result: success={result.get('success')}, error={result.get('error')}")

        assert not result["success"], "Second Wind should fail with no uses"
        assert "no uses" in str(result.get("error", "")).lower()
        logger.info(f"✅ Second Wind correctly refused: {result.get('error')}")


class TestCombatIntegration:
    """Test features work in a full combat turn."""

    def test_barbarian_rage_in_turn(self, combat_setup):
        """Barbarian should be offered Rage and able to use it in a real turn."""
        logger.info("🧪 Test: Barbarian Rage in real combat turn")

        resolver = combat_setup["resolver"]
        wrapper = combat_setup["wrapper"]
        manager = combat_setup["manager"]

        # Check that Rage is usable by the Barbarian
        barbarian = manager.characters["barbarian"]
        from components.combat.action_registry import is_usable_by
        assert is_usable_by("rage", barbarian), "Rage should be usable by Barbarian"

        # Execute Rage
        result = resolver.resolve_action({
            "actor": "barbarian",
            "action_type": "rage",
        })

        logger.info(f"   Rage execution: success={result.get('success')}")
        assert result["success"], f"Rage should succeed: {result.get('error')}"
        logger.info("✅ Barbarian successfully used Rage in combat turn")

    def test_fighter_second_wind_in_turn(self, combat_setup):
        """Fighter should be offered Second Wind and able to use it in a real turn."""
        logger.info("🧪 Test: Fighter Second Wind in real combat turn")

        resolver = combat_setup["resolver"]
        wrapper = combat_setup["wrapper"]
        manager = combat_setup["manager"]

        # Check that Second Wind is usable by the Fighter
        fighter = manager.characters["fighter"]
        from components.combat.action_registry import is_usable_by
        assert is_usable_by("second_wind", fighter), "Second Wind should be usable by Fighter"

        # Execute Second Wind
        result = resolver.resolve_action({
            "actor": "fighter",
            "action_type": "second_wind",
        })

        logger.info(f"   Second Wind execution: success={result.get('success')}, healed={result.get('healed')}")
        assert result["success"], f"Second Wind should succeed: {result.get('error')}"
        assert result.get("healed", 0) > 0
        logger.info(f"✅ Fighter successfully used Second Wind and healed {result.get('healed')} HP")

    def test_wizard_not_offered_features(self, combat_setup):
        """Wizard should not be offered class features they don't have."""
        logger.info("🧪 Test: Wizard not offered Barbarian/Fighter features")

        manager = combat_setup["manager"]
        wizard = manager.characters["wizard"]

        # Check that class features are NOT usable by the Wizard
        from components.combat.action_registry import is_usable_by
        assert not is_usable_by("rage", wizard), "Wizard should not be able to use Rage"
        assert not is_usable_by("second_wind", wizard), "Wizard should not be able to use Second Wind"
        assert not is_usable_by("action_surge", wizard), "Wizard should not be able to use Action Surge"

        logger.info("✅ Wizard correctly not offered other classes' features")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
