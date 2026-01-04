"""
Test Combat Action Resolver - Unified Action Resolution

Tests for CombatActionResolver which dispatches to both dnd_engine Actions
and Roshar-specific Actions.

Based on: COMBAT_ENGINE_IMPLEMENTATION_PLAN.md Phase 3
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from uuid import uuid4

from components.combat.combat_action_resolver import CombatActionResolver
from components.combat.action_registry import ACTION_REGISTRY


class TestCombatActionResolver:
    """Test suite for CombatActionResolver"""

    @pytest.fixture
    def mock_dnd_wrapper(self):
        """Mock DnDEngineWrapper"""
        wrapper = Mock()
        wrapper.entities = {}

        # Create mock entity
        entity = Mock()
        entity.uuid = uuid4()
        entity.health = Mock()
        entity.health.get_current_hit_points = Mock(return_value=25)
        entity.health.get_max_hit_points = Mock(return_value=25)

        wrapper.entities["char_001"] = entity
        wrapper.entities["target_001"] = entity

        return wrapper

    @pytest.fixture
    def mock_character_manager(self):
        """Mock CharacterManager"""
        manager = Mock()
        manager.characters = {
            "char_001": Mock(name="Test Character"),
            "target_001": Mock(name="Test Target")
        }
        return manager

    @pytest.fixture
    def combat_state(self):
        """Sample combat state"""
        return {
            "round_number": 1,
            "combat_log": [],
            "combatant_states": {
                "char_001": {
                    "hp_current": 25,
                    "hp_max": 25,
                    "is_hostile": False
                },
                "target_001": {
                    "hp_current": 10,
                    "hp_max": 10,
                    "is_hostile": True
                }
            },
            "active_combatants": ["char_001", "target_001"]
        }

    @pytest.fixture
    def action_resolver(self, mock_dnd_wrapper, mock_character_manager, combat_state):
        """Create CombatActionResolver instance"""
        return CombatActionResolver(
            dnd_engine_wrapper=mock_dnd_wrapper,
            character_manager=mock_character_manager,
            combat_state=combat_state
        )

    def test_initialization(self, action_resolver):
        """Test CombatActionResolver initializes correctly"""
        assert action_resolver.dnd_wrapper is not None
        assert action_resolver.character_manager is not None
        assert action_resolver.combat_state is not None
        assert action_resolver.ACTION_REGISTRY is not None
        assert len(action_resolver.ACTION_REGISTRY) >= 4  # At least 4 D&D actions

    def test_action_registry_exposed(self, action_resolver):
        """Test ACTION_REGISTRY is exposed for CombatSessionManager"""
        assert hasattr(action_resolver, 'ACTION_REGISTRY')
        assert action_resolver.ACTION_REGISTRY == ACTION_REGISTRY

    def test_resolve_action_unknown_type(self, action_resolver):
        """Test resolving unknown action type returns error"""
        action = {
            "actor": "char_001",
            "action_type": "unknown_action",
            "target": "target_001"
        }

        result = action_resolver.resolve_action(action)

        assert result["success"] is False
        assert "Unknown action" in result["error"]

    @patch('components.combat.combat_action_resolver.Attack')
    def test_resolve_attack_action(self, mock_attack_class, action_resolver):
        """Test resolving attack action"""
        # Setup mock attack
        mock_attack_instance = Mock()
        mock_event = Mock()
        mock_event.canceled = False
        mock_event.attack_outcome = Mock()
        mock_event.damage_rolls = [Mock(total=10)]

        mock_attack_instance.apply = Mock(return_value=mock_event)
        mock_attack_class.return_value = mock_attack_instance

        action = {
            "actor": "char_001",
            "action_type": "attack",
            "target": "target_001"
        }

        result = action_resolver.resolve_action(action)

        # Verify attack was created
        assert mock_attack_class.called
        assert mock_attack_instance.apply.called
        assert result["success"] is True

    def test_get_entity_uuid_valid(self, action_resolver, mock_dnd_wrapper):
        """Test getting entity UUID for valid character"""
        char_id = "char_001"
        uuid = action_resolver._get_entity_uuid(char_id)

        assert uuid == mock_dnd_wrapper.entities[char_id].uuid

    def test_get_entity_uuid_invalid(self, action_resolver):
        """Test getting entity UUID for invalid character raises error"""
        with pytest.raises(ValueError, match="Entity not found"):
            action_resolver._get_entity_uuid("invalid_char")

    def test_sync_hp_to_combat_state(self, action_resolver, mock_dnd_wrapper, combat_state):
        """Test HP syncing from dnd_engine to combat_state"""
        entity = mock_dnd_wrapper.entities["char_001"]
        entity.health.get_current_hit_points.return_value = 15
        entity.health.get_max_hit_points.return_value = 25

        action_resolver._sync_hp_to_combat_state(entity.uuid)

        # Verify HP was synced
        assert combat_state["combatant_states"]["char_001"]["hp_current"] == 15
        assert combat_state["combatant_states"]["char_001"]["hp_max"] == 25

    def test_format_attack_result_hit(self, action_resolver):
        """Test formatting attack hit result"""
        from dnd.core.events import AttackOutcome

        event = Mock()
        event.attack_outcome = AttackOutcome.HIT
        event.damage_rolls = [Mock(total=8), Mock(total=2)]
        event.status_message = "Hit!"

        result = action_resolver._format_attack_result(event)

        assert "Hit!" in result
        assert "10 damage" in result

    def test_format_attack_result_critical_hit(self, action_resolver):
        """Test formatting critical hit result"""
        from dnd.core.events import AttackOutcome

        event = Mock()
        event.attack_outcome = AttackOutcome.CRIT_HIT
        event.damage_rolls = [Mock(total=15)]
        event.status_message = "Critical!"

        result = action_resolver._format_attack_result(event)

        assert "Critical Hit!" in result
        assert "15 damage" in result

    def test_format_attack_result_miss(self, action_resolver):
        """Test formatting attack miss result"""
        from dnd.core.events import AttackOutcome

        event = Mock()
        event.attack_outcome = AttackOutcome.MISS
        event.status_message = "Miss"

        result = action_resolver._format_attack_result(event)

        assert "Miss!" in result

    @patch('components.combat.combat_action_resolver.Dashing')
    def test_apply_condition(self, mock_dashing_class, action_resolver):
        """Test applying D&D condition"""
        # Setup mock condition
        mock_condition_instance = Mock()
        mock_event = Mock()
        mock_event.canceled = False

        mock_condition_instance.apply = Mock(return_value=mock_event)
        mock_dashing_class.return_value = mock_condition_instance

        action = {
            "actor": "char_001",
            "action_type": "dash"
        }

        # Get metadata for dash action
        metadata = ACTION_REGISTRY["dash"]

        result = action_resolver._apply_condition(action, metadata)

        # Verify condition was applied
        assert mock_dashing_class.called
        assert mock_condition_instance.apply.called
        assert result["success"] is True
        assert result["condition"] == "Dashing"

    def test_execute_action_with_exception(self, action_resolver):
        """Test action execution with exception is handled gracefully"""
        action = {
            "actor": "invalid_char",
            "action_type": "attack",
            "target": "target_001"
        }

        result = action_resolver.resolve_action(action)

        # Should return error result
        assert result["success"] is False
        assert "error" in result


class TestActionRegistryIntegration:
    """Test ACTION_REGISTRY integration with CombatActionResolver"""

    def test_all_dnd_actions_have_required_fields(self):
        """Test all D&D actions have required metadata fields"""
        for action_type, metadata in ACTION_REGISTRY.items():
            if metadata["type"] == "dnd_action":
                assert "action_class" in metadata
                assert "description" in metadata
                assert "params" in metadata
                assert "cost_type" in metadata

    def test_all_roshar_actions_have_required_fields(self):
        """Test all Roshar actions have required metadata fields"""
        for action_type, metadata in ACTION_REGISTRY.items():
            if metadata["type"] == "roshar_action":
                assert "action_class" in metadata
                assert "description" in metadata
                assert "params" in metadata
                assert "cost_type" in metadata
                assert "stormlight_cost" in metadata

    def test_action_registry_minimal_set(self):
        """Test ACTION_REGISTRY has minimal 7 actions"""
        assert len(ACTION_REGISTRY) >= 7

        # Check for required D&D actions
        assert "attack" in ACTION_REGISTRY
        assert "move" in ACTION_REGISTRY
        assert "dash" in ACTION_REGISTRY
        assert "dodge" in ACTION_REGISTRY

    def test_roshar_actions_conditional_import(self):
        """Test Roshar actions are conditionally added"""
        # Check if Roshar actions exist
        roshar_actions = ["lashing", "shardblade_attack", "progression_healing"]

        for action_type in roshar_actions:
            if action_type in ACTION_REGISTRY:
                metadata = ACTION_REGISTRY[action_type]
                assert metadata["type"] in ["roshar_action", "roshar_equipment"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
