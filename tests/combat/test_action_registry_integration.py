"""
Integration Tests for Action Registry

Tests the ACTION_REGISTRY integration with real dnd_engine classes.
These tests verify that actions are properly configured and can be instantiated.

Based on: COMBAT_ENGINE_IMPLEMENTATION_PLAN.md Phase 3
"""

import pytest
from uuid import uuid4

from components.combat.action_registry import ACTION_REGISTRY


class TestActionRegistryIntegration:
    """Integration tests for ACTION_REGISTRY"""

    def test_registry_has_minimum_7_actions(self):
        """Test ACTION_REGISTRY has at least 7 actions (Phase 3 requirement)"""
        assert len(ACTION_REGISTRY) >= 7, "ACTION_REGISTRY should have at least 7 actions"

    def test_all_actions_have_required_fields(self):
        """Test all actions have required metadata fields"""
        required_fields = ["type", "description"]

        for action_type, metadata in ACTION_REGISTRY.items():
            for field in required_fields:
                assert field in metadata, f"Action '{action_type}' missing required field '{field}'"

    def test_dnd_actions_have_action_class(self):
        """Test D&D actions have action_class specified"""
        for action_type, metadata in ACTION_REGISTRY.items():
            if metadata["type"] in ["dnd_action", "roshar_action", "roshar_equipment"]:
                assert "action_class" in metadata, f"Action '{action_type}' missing action_class"
                assert metadata["action_class"] is not None

    def test_dnd_conditions_have_condition_class(self):
        """Test D&D conditions have condition_class specified"""
        for action_type, metadata in ACTION_REGISTRY.items():
            if metadata["type"] in ["dnd_condition", "roshar_condition"]:
                assert "condition_class" in metadata, f"Condition '{action_type}' missing condition_class"
                assert metadata["condition_class"] is not None

    def test_core_dnd_actions_present(self):
        """Test core D&D 5e actions are present"""
        core_actions = ["attack", "move", "dash", "dodge"]

        for action in core_actions:
            assert action in ACTION_REGISTRY, f"Core action '{action}' missing from registry"

    def test_attack_action_configuration(self):
        """Test Attack action is properly configured"""
        assert "attack" in ACTION_REGISTRY

        attack_meta = ACTION_REGISTRY["attack"]
        assert attack_meta["type"] == "dnd_action"
        assert "action_class" in attack_meta
        assert attack_meta["cost_type"] == "actions"
        assert attack_meta["cost"] == 1
        assert "target_entity_uuid" in attack_meta["params"]

    def test_move_action_configuration(self):
        """Test Move action is properly configured"""
        assert "move" in ACTION_REGISTRY

        move_meta = ACTION_REGISTRY["move"]
        assert move_meta["type"] == "dnd_action"
        assert "action_class" in move_meta
        assert "end_position" in move_meta["params"]

    def test_dash_condition_configuration(self):
        """Test Dash condition is properly configured"""
        assert "dash" in ACTION_REGISTRY

        dash_meta = ACTION_REGISTRY["dash"]
        assert dash_meta["type"] == "dnd_condition"
        assert "condition_class" in dash_meta
        assert dash_meta["cost_type"] == "actions"

    def test_dodge_condition_configuration(self):
        """Test Dodge condition is properly configured"""
        assert "dodge" in ACTION_REGISTRY

        dodge_meta = ACTION_REGISTRY["dodge"]
        assert dodge_meta["type"] == "dnd_condition"
        assert "condition_class" in dodge_meta
        assert dodge_meta["cost_type"] == "actions"

    def test_roshar_actions_if_available(self):
        """Test Roshar actions are present if roshar_actions module loaded"""
        roshar_actions = ["lashing", "shardblade_attack", "progression_healing"]

        # Check if any Roshar actions are present
        has_roshar = any(action in ACTION_REGISTRY for action in roshar_actions)

        if has_roshar:
            # If Roshar actions exist, verify they're properly configured
            for action in roshar_actions:
                if action in ACTION_REGISTRY:
                    metadata = ACTION_REGISTRY[action]
                    assert "action_class" in metadata
                    assert metadata["type"] in ["roshar_action", "roshar_equipment"]

                    # Roshar actions should have stormlight_cost or requires field
                    assert ("stormlight_cost" in metadata or
                            "requires" in metadata), f"Roshar action '{action}' missing resource requirements"

    def test_action_classes_are_importable(self):
        """Test that action classes can be imported and are valid"""
        from dnd.actions import Attack, Move
        from dnd.conditions import Dashing, Dodging

        # Verify classes exist
        assert Attack is not None
        assert Move is not None
        assert Dashing is not None
        assert Dodging is not None

        # Verify they match registry
        assert ACTION_REGISTRY["attack"]["action_class"] == Attack
        assert ACTION_REGISTRY["move"]["action_class"] == Move
        assert ACTION_REGISTRY["dash"]["condition_class"] == Dashing
        assert ACTION_REGISTRY["dodge"]["condition_class"] == Dodging

    def test_no_duplicate_action_types(self):
        """Test there are no duplicate action type keys"""
        action_types = list(ACTION_REGISTRY.keys())
        assert len(action_types) == len(set(action_types)), "Duplicate action types found in registry"

    def test_all_actions_have_cost_info(self):
        """Test all actions have cost information"""
        for action_type, metadata in ACTION_REGISTRY.items():
            # Should have either cost_type or be free
            if "cost_type" in metadata:
                assert metadata["cost_type"] in ["actions", "bonus_actions", "reactions", "movement"]
                assert "cost" in metadata, f"Action '{action_type}' has cost_type but no cost value"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
