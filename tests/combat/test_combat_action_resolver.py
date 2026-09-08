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
        """
        REAL DnDEngineWrapper (plan 1.3).

        The old fixture mocked health.get_current_hit_points()/
        get_max_hit_points() -- neither of which exists -- and pointed
        char_001 and target_001 at the SAME entity object, so an "attack"
        had the actor hitting itself and nothing could be verified.
        """
        from components.character_manager import CharacterManager
        from components.dnd_engine_wrapper import DnDEngineWrapper

        mgr = CharacterManager()
        for char_id, name in (("char_001", "Test Character"),
                              ("target_001", "Test Target")):
            mgr.add_character({
                "character_id": char_id,
                "name": name,
                "level": 3,
                "ability_scores": {"strength": 16, "dexterity": 14,
                                   "constitution": 12, "intelligence": 10,
                                   "wisdom": 10, "charisma": 10},
                "hit_points": {"current": 25, "maximum": 25, "temporary": 0},
                "armor_class": 13,
                "character_class": "Fighter",
                "race": "Human",
                "background": "Soldier",
            })

        class _StubGameEngine:
            def __init__(self):
                self.game_state = type("S", (), {"characters": {}})()

        return DnDEngineWrapper(game_engine=_StubGameEngine(),
                                character_manager=mgr)

    @pytest.fixture
    def mock_character_manager(self, mock_dnd_wrapper):
        """The same CharacterManager the wrapper was built from."""
        return mock_dnd_wrapper.character_manager

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

    def test_resolve_attack_action(self, action_resolver, mock_dnd_wrapper):
        """
        Resolve a REAL attack through the resolver and assert observable state.

        The old version @patch'd Attack and asserted only that the mock was
        constructed and .apply() called -- it could not tell whether the attack
        was cancelled or dealt damage (and before plan 1.1 every attack WAS
        cancelled for want of line of sight).
        """
        target = mock_dnd_wrapper.entities["target_001"]
        start_hp = mock_dnd_wrapper.get_entity_current_hp(target)

        action = {"actor": "char_001", "action_type": "attack",
                  "target": "target_001"}

        hits = 0
        for _ in range(20):
            mock_dnd_wrapper.entities["char_001"].action_economy.reset_all_costs()
            result = action_resolver.resolve_action(action)
            assert result is not None
            assert "not in line of sight" not in str(result).lower()
            if result.get("success"):
                hits += 1

        end_hp = mock_dnd_wrapper.get_entity_current_hp(target)
        assert hits > 0, "20 resolved attacks all failed"
        assert end_hp < start_hp, (
            f"20 attacks dealt no damage (HP {start_hp} -> {end_hp})"
        )

    def test_sync_hp_to_combat_state(self, action_resolver, mock_dnd_wrapper, combat_state):
        """Test HP syncing from dnd_engine to combat_state"""
        entity = mock_dnd_wrapper.entities["char_001"]
        # Health exposes get_total_hit_points()/damage_taken, NOT
        # get_current_hit_points()/get_max_hit_points(). Apply real damage.
        entity.health.damage_taken = 10

        action_resolver._sync_hp_to_combat_state(entity.uuid)

        expected_current = mock_dnd_wrapper.get_entity_current_hp(entity)
        expected_max = mock_dnd_wrapper.get_entity_max_hp(entity)
        assert combat_state["combatant_states"]["char_001"]["hp_current"] == expected_current
        assert combat_state["combatant_states"]["char_001"]["hp_max"] == expected_max
        assert expected_current == expected_max - 10

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
        event.attack_outcome = AttackOutcome.CRIT
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

    def test_apply_condition(self, action_resolver):
        """
        Apply a REAL dnd_engine condition and assert on observable state.

        The old version patched
        'components.combat.combat_action_resolver.Dashing' -- a name that does
        not exist there (Dashing is imported in action_registry) -- so the patch
        raised AttributeError. It also only asserted "the mock was called",
        which proves nothing about whether the condition landed (plan §12).
        """
        metadata = ACTION_REGISTRY["dash"]
        action = {"actor": "char_001", "action_type": "dash"}

        result = action_resolver._apply_condition(action, metadata)

        assert result["success"] is True, result
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
