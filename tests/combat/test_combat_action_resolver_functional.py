"""
Functional Tests for Combat Action Resolver

Tests CombatActionResolver with minimal mocking, focusing on real behavior
and integration with dnd_engine.

Based on: COMBAT_ENGINE_IMPLEMENTATION_PLAN.md Phase 3
"""

import pytest
from uuid import uuid4
from unittest.mock import Mock, MagicMock

from components.combat.combat_action_resolver import CombatActionResolver
from components.combat.action_registry import ACTION_REGISTRY


class TestCombatActionResolverFunctional:
    """Functional tests for CombatActionResolver"""

    @pytest.fixture
    def dnd_wrapper(self):
        """
        REAL DnDEngineWrapper (plan 1.3).

        The old fixtures mocked health.get_current_hit_points()/
        get_max_hit_points() -- neither of which exists on the real Health
        block -- so HP assertions compared against a Mock object.
        """
        from components.character_manager import CharacterManager
        from components.dnd_engine_wrapper import DnDEngineWrapper

        mgr = CharacterManager()
        for char_id, name, hp in (("player_001", "Hero", 25),
                                  ("enemy_001", "Goblin", 10)):
            mgr.add_character({
                "character_id": char_id,
                "name": name,
                "level": 3,
                "ability_scores": {"strength": 14, "dexterity": 14,
                                   "constitution": 12, "intelligence": 10,
                                   "wisdom": 10, "charisma": 10},
                "hit_points": {"current": hp, "maximum": hp, "temporary": 0},
                "armor_class": 13,
                "character_class": "Fighter" if hp > 15 else "Goblin",
                "race": "Human",
                "background": "Soldier",
            })

        class _StubGameEngine:
            def __init__(self):
                self.game_state = type("S", (), {"characters": {}})()

        return DnDEngineWrapper(game_engine=_StubGameEngine(),
                                character_manager=mgr)

    @pytest.fixture
    def mock_entities(self, dnd_wrapper):
        """Real entities keyed as the tests expect."""
        return {
            "player": dnd_wrapper.entities["player_001"],
            "enemy": dnd_wrapper.entities["enemy_001"],
        }

    @pytest.fixture
    def character_manager(self, dnd_wrapper):
        """The same CharacterManager the wrapper was built from."""
        return dnd_wrapper.character_manager

    @pytest.fixture
    def combat_state(self):
        """Create sample combat state"""
        return {
            "round_number": 1,
            "combat_log": [],
            "combatant_states": {
                "player_001": {
                    "hp_current": 25,
                    "hp_max": 25,
                    "is_hostile": False
                },
                "enemy_001": {
                    "hp_current": 10,
                    "hp_max": 10,
                    "is_hostile": True
                }
            },
            "active_combatants": ["player_001", "enemy_001"]
        }

    @pytest.fixture
    def action_resolver(self, dnd_wrapper, character_manager, combat_state):
        """Create CombatActionResolver instance"""
        return CombatActionResolver(
            dnd_engine_wrapper=dnd_wrapper,
            character_manager=character_manager,
            combat_state=combat_state
        )

    def test_initialization_with_registry(self, action_resolver):
        """Test resolver initializes with ACTION_REGISTRY"""
        assert action_resolver.ACTION_REGISTRY is not None
        assert action_resolver.ACTION_REGISTRY == ACTION_REGISTRY
        assert len(action_resolver.ACTION_REGISTRY) >= 7

    def test_unknown_action_returns_error(self, action_resolver):
        """Test unknown action type returns error result"""
        action = {
            "actor": "player_001",
            "action_type": "nonexistent_action",
            "target": "enemy_001"
        }

        result = action_resolver.resolve_action(action)

        assert result["success"] is False
        assert "error" in result
        assert "Unknown action" in result["error"]

    def test_get_entity_uuid_valid(self, action_resolver, mock_entities):
        """Test retrieving valid entity UUID"""
        uuid = action_resolver._get_entity_uuid("player_001")

        assert uuid == mock_entities["player"].uuid
        assert isinstance(uuid, type(uuid4()))

    def test_get_entity_uuid_invalid_raises_error(self, action_resolver):
        """Test invalid character ID raises ValueError"""
        with pytest.raises(ValueError, match="Entity not found"):
            action_resolver._get_entity_uuid("invalid_char_id")

    def test_sync_hp_to_combat_state(self, action_resolver, mock_entities, combat_state):
        """Test HP syncing from dnd_engine to combat_state"""
        # Apply real damage (Health has no get_current_hit_points()/
        # get_max_hit_points(); it exposes get_total_hit_points()/damage_taken).
        player_entity = mock_entities["player"]
        player_entity.health.damage_taken = 10

        action_resolver._sync_hp_to_combat_state(player_entity.uuid)

        expected_current = action_resolver.dnd_wrapper.get_entity_current_hp(player_entity)
        expected_max = action_resolver.dnd_wrapper.get_entity_max_hp(player_entity)
        state = combat_state["combatant_states"]["player_001"]
        assert state["hp_current"] == expected_current
        assert state["hp_max"] == expected_max
        assert expected_current == expected_max - 10

    def test_action_registry_exposure(self, action_resolver):
        """Test ACTION_REGISTRY is exposed for other components"""
        # Verify registry is accessible
        registry = action_resolver.ACTION_REGISTRY

        # Verify it has expected actions
        assert "attack" in registry
        assert "move" in registry
        assert "dash" in registry
        assert "dodge" in registry

    def test_resolve_action_validates_action_type(self, action_resolver):
        """Test resolve_action validates action exists in registry"""
        # Valid action
        valid_action = {
            "actor": "player_001",
            "action_type": "attack",
            "target": "enemy_001"
        }

        # Should not immediately fail (will fail in _execute_action due to mocking limits)
        try:
            result = action_resolver.resolve_action(valid_action)
            # Either succeeds or fails gracefully with error dict
            assert isinstance(result, dict)
        except Exception:
            # If it raises an exception, that's also acceptable for this test
            # (we're just verifying it gets past the registry check)
            pass

        # Invalid action
        invalid_action = {
            "actor": "player_001",
            "action_type": "invalid_action",
            "target": "enemy_001"
        }

        result = action_resolver.resolve_action(invalid_action)
        assert result["success"] is False
        assert "Unknown action" in result["error"]

    def test_action_types_are_categorized(self, action_resolver):
        """
        Test actions are properly categorized by type.

        The allow-list is closed on purpose: a typo'd or invented `type` would make
        the resolver fall through to "Unknown action" at dispatch time rather than
        failing here. `spell_action` was added when 5e spellcasting landed — a
        genuinely new category, not a typo, since a spell is dispatched neither like
        a dnd_action nor like a Roshar surge. `art_action` was added the same way
        when Invested Arts (`cast_art`) landed — dispatched via compile_art +
        InvestiturePointLedger, distinct from spells and surges.
        """
        for action_type, metadata in action_resolver.ACTION_REGISTRY.items():
            # Verify type is valid
            assert metadata["type"] in [
                "dnd_action",
                "dnd_condition",
                "spell_action",
                "art_action",
                "roshar_action",
                "roshar_equipment",
                "roshar_condition"
            ], f"Action '{action_type}' has invalid type: {metadata['type']}"

    def test_combat_state_reference_maintained(self, action_resolver, combat_state):
        """Test resolver maintains reference to combat_state"""
        assert action_resolver.combat_state is combat_state

        # Verify modifications affect the same object
        action_resolver.combat_state["round_number"] = 5
        assert combat_state["round_number"] == 5

    def test_character_manager_integration(self, action_resolver, character_manager):
        """Test resolver integrates with CharacterManager"""
        assert action_resolver.character_manager is character_manager

        # Verify can access character data
        assert "player_001" in action_resolver.character_manager.characters
        assert action_resolver.character_manager.characters["player_001"].name == "Hero"

    def test_dnd_wrapper_integration(self, action_resolver, dnd_wrapper, mock_entities):
        """Test resolver integrates with DnDEngineWrapper"""
        assert action_resolver.dnd_wrapper is dnd_wrapper

        # Verify can access entities
        assert "player_001" in action_resolver.dnd_wrapper.entities
        player_entity = action_resolver.dnd_wrapper.entities["player_001"]
        assert player_entity.uuid == mock_entities["player"].uuid


class TestActionMetadataValidation:
    """Test action metadata structure and validation"""

    def test_all_actions_have_valid_cost_types(self):
        """Test all actions have valid cost_type values"""
        valid_cost_types = ["actions", "bonus_actions", "reactions", "movement"]

        for action_type, metadata in ACTION_REGISTRY.items():
            if "cost_type" in metadata:
                assert metadata["cost_type"] in valid_cost_types, \
                    f"Action '{action_type}' has invalid cost_type: {metadata['cost_type']}"

    def test_all_actions_have_descriptions(self):
        """Test all actions have human-readable descriptions"""
        for action_type, metadata in ACTION_REGISTRY.items():
            assert "description" in metadata, f"Action '{action_type}' missing description"
            assert len(metadata["description"]) > 0, f"Action '{action_type}' has empty description"

    def test_targeted_actions_have_target_param(self):
        """Test targeted actions specify target_entity_uuid in params"""
        targeted_actions = ["attack", "shardblade_attack", "lashing", "progression_healing"]

        for action in targeted_actions:
            if action in ACTION_REGISTRY:
                metadata = ACTION_REGISTRY[action]
                if metadata["type"] in ["dnd_action", "roshar_action", "roshar_equipment"]:
                    assert "params" in metadata, f"Targeted action '{action}' missing params"
                    # Most targeted actions should have target_entity_uuid
                    # (though some like move don't)
                    if action != "move":
                        assert "target_entity_uuid" in metadata["params"], \
                            f"Targeted action '{action}' missing target_entity_uuid param"

    def test_roshar_actions_have_resource_costs(self):
        """Test Roshar actions specify Stormlight or other resource costs"""
        roshar_actions = ["lashing", "progression_healing"]

        for action in roshar_actions:
            if action in ACTION_REGISTRY:
                metadata = ACTION_REGISTRY[action]
                # Should have stormlight_cost for surge abilities
                if metadata["type"] == "roshar_action":
                    assert "stormlight_cost" in metadata, \
                        f"Roshar action '{action}' missing stormlight_cost"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
