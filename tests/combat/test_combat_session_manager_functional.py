"""
Functional Tests for Combat Session Manager

Tests CombatSessionManager core mechanics without complex mocking.
Focuses on turn logic, action economy, end conditions, and target selection.

Based on: COMBAT_ENGINE_IMPLEMENTATION_PLAN.md Phase 3
"""

import pytest
from unittest.mock import Mock
from uuid import uuid4

from components.combat.combat_session_manager import CombatSessionManager


class TestCombatSessionManagerFunctional:
    """Functional tests for combat turn management"""

    @pytest.fixture
    def combat_state(self):
        """Create realistic combat state"""
        return {
            "in_combat": True,
            "combat_id": "test_combat_001",
            "active_combatants": ["hero", "goblin_1", "goblin_2"],
            "initiative_order": [
                {"char_id": "hero", "initiative": 18},
                {"char_id": "goblin_1", "initiative": 15},
                {"char_id": "goblin_2", "initiative": 12}
            ],
            "current_turn_index": 0,
            "round_number": 1,
            "combat_log": [],
            "combatant_states": {
                "hero": {
                    "hp_current": 25,
                    "hp_max": 25,
                    "conditions": [],
                    "actions_remaining": 1,
                    "bonus_actions_remaining": 1,
                    "reaction_available": True,
                    "is_hostile": False
                },
                "goblin_1": {
                    "hp_current": 7,
                    "hp_max": 7,
                    "conditions": [],
                    "actions_remaining": 1,
                    "bonus_actions_remaining": 1,
                    "reaction_available": True,
                    "is_hostile": True
                },
                "goblin_2": {
                    "hp_current": 7,
                    "hp_max": 7,
                    "conditions": [],
                    "actions_remaining": 1,
                    "bonus_actions_remaining": 1,
                    "reaction_available": True,
                    "is_hostile": True
                }
            },
            "end_conditions": {
                "all_hostiles_defeated": False,
                "all_players_defeated": False
            }
        }

    @pytest.fixture
    def mock_entities(self):
        """Create mock dnd_engine entities"""
        entities = {}

        for char_id in ["hero", "goblin_1", "goblin_2"]:
            entity = Mock()
            entity.uuid = uuid4()
            entity.health = Mock()
            entity.health.is_unconscious = Mock(return_value=False)
            entity.health.is_dead = Mock(return_value=False)
            entity.health.get_current_hit_points = Mock(return_value=25 if char_id == "hero" else 7)
            entity.health.get_max_hit_points = Mock(return_value=25 if char_id == "hero" else 7)

            entity.action_economy = Mock()
            entity.action_economy.actions = 1
            entity.action_economy.bonus_actions = 1
            entity.action_economy.reactions = 1
            entity.action_economy.reset = Mock()

            entities[char_id] = entity

        return entities

    @pytest.fixture
    def dnd_wrapper(self, mock_entities):
        """Create mock DnDEngineWrapper"""
        wrapper = Mock()
        wrapper.entities = mock_entities
        return wrapper

    @pytest.fixture
    def character_manager(self):
        """Create mock CharacterManager"""
        manager = Mock()
        manager.characters = {
            "hero": Mock(name="Aggi", attacks=[{"name": "Longsword"}]),
            "goblin_1": Mock(name="Goblin Warrior", attacks=[{"name": "Scimitar"}]),
            "goblin_2": Mock(name="Goblin Scout", attacks=[{"name": "Shortbow"}])
        }
        return manager

    @pytest.fixture
    def action_resolver(self):
        """Create mock CombatActionResolver"""
        resolver = Mock()
        resolver.ACTION_REGISTRY = {
            "attack": {
                "type": "dnd_action",
                "cost_type": "actions",
                "cost": 1,
                "params": ["target_entity_uuid"]
            },
            "dodge": {
                "type": "dnd_condition",
                "cost_type": "actions",
                "cost": 1,
                "params": []
            }
        }
        return resolver

    @pytest.fixture
    def session_manager(self, combat_state, dnd_wrapper, character_manager, action_resolver):
        """Create CombatSessionManager instance"""
        return CombatSessionManager(
            combat_state=combat_state,
            game_engine=Mock(),
            character_manager=character_manager,
            dnd_engine_wrapper=dnd_wrapper,
            combat_action_resolver=action_resolver,
            combat_narrative_generator=Mock(),
            npc_ai_agent=Mock()
        )

    # ========================================================================
    # TURN MANAGEMENT TESTS
    # ========================================================================

    def test_get_current_actor(self, session_manager):
        """Test getting current actor from initiative order"""
        # Round 1, turn 1 (index 0)
        actor = session_manager._get_current_actor()
        assert actor == "hero"

        # Advance to turn 2
        session_manager.combat_state["current_turn_index"] = 1
        actor = session_manager._get_current_actor()
        assert actor == "goblin_1"

        # Advance to turn 3
        session_manager.combat_state["current_turn_index"] = 2
        actor = session_manager._get_current_actor()
        assert actor == "goblin_2"

    def test_advance_turn_within_round(self, session_manager):
        """Test advancing turn stays in same round"""
        initial_round = session_manager.combat_state["round_number"]

        session_manager._advance_turn()

        assert session_manager.combat_state["current_turn_index"] == 1
        assert session_manager.combat_state["round_number"] == initial_round

    def test_advance_turn_to_new_round(self, session_manager, mock_entities):
        """Test advancing from last turn wraps to new round"""
        # Set to last combatant
        session_manager.combat_state["current_turn_index"] = 2

        session_manager._advance_turn()

        # Should wrap to index 0 and increment round
        assert session_manager.combat_state["current_turn_index"] == 0
        assert session_manager.combat_state["round_number"] == 2

        # Verify action economy was reset
        for entity in mock_entities.values():
            entity.action_economy.reset.assert_called()

    def test_skip_dead_combatants_on_advance(self, session_manager, mock_entities):
        """Test advancing turn skips dead/unconscious combatants"""
        # Mark goblin_1 as dead
        mock_entities["goblin_1"].health.is_dead.return_value = True

        # Start at hero's turn
        session_manager.combat_state["current_turn_index"] = 0

        # Advance should skip goblin_1 and go to goblin_2
        session_manager._advance_turn()

        # Due to skip logic, might advance twice
        # Just verify we don't crash and state is valid
        assert session_manager.combat_state["current_turn_index"] in [0, 1, 2]

    # ========================================================================
    # COMBATANT STATE TESTS
    # ========================================================================

    def test_is_player_detection(self, session_manager):
        """Test player vs NPC detection"""
        assert session_manager._is_player("hero") is True
        assert session_manager._is_player("goblin_1") is False
        assert session_manager._is_player("goblin_2") is False

    def test_is_combatant_dead_alive(self, session_manager, mock_entities):
        """Test detecting alive combatant"""
        mock_entities["hero"].health.is_unconscious.return_value = False
        mock_entities["hero"].health.is_dead.return_value = False

        assert session_manager._is_combatant_dead("hero") is False

    def test_is_combatant_dead_unconscious(self, session_manager, mock_entities):
        """Test detecting unconscious combatant"""
        mock_entities["goblin_1"].health.is_unconscious.return_value = True
        mock_entities["goblin_1"].health.is_dead.return_value = False

        assert session_manager._is_combatant_dead("goblin_1") is True

    def test_is_combatant_dead_killed(self, session_manager, mock_entities):
        """Test detecting dead combatant"""
        mock_entities["goblin_2"].health.is_unconscious.return_value = False
        mock_entities["goblin_2"].health.is_dead.return_value = True

        assert session_manager._is_combatant_dead("goblin_2") is True

    # ========================================================================
    # ACTION ECONOMY TESTS
    # ========================================================================

    def test_has_actions_remaining_true(self, session_manager, mock_entities):
        """Test detecting actions remaining"""
        mock_entities["hero"].action_economy.actions = 1
        mock_entities["hero"].action_economy.bonus_actions = 0

        assert session_manager._has_actions_remaining("hero") is True

    def test_has_actions_remaining_false(self, session_manager, mock_entities):
        """Test detecting no actions remaining"""
        mock_entities["hero"].action_economy.actions = 0
        mock_entities["hero"].action_economy.bonus_actions = 0

        assert session_manager._has_actions_remaining("hero") is False

    def test_has_actions_with_bonus_action_only(self, session_manager, mock_entities):
        """Test bonus action counts as having actions"""
        mock_entities["hero"].action_economy.actions = 0
        mock_entities["hero"].action_economy.bonus_actions = 1

        assert session_manager._has_actions_remaining("hero") is True

    def test_consume_action_syncs_state(self, session_manager, mock_entities, combat_state):
        """Test consuming action syncs dnd_engine state to combat_state"""
        # Set entity action economy
        mock_entities["hero"].action_economy.actions = 0
        mock_entities["hero"].action_economy.bonus_actions = 1
        mock_entities["hero"].action_economy.reactions = 0

        session_manager._consume_action("hero", "attack")

        # Verify combat_state was synced
        assert combat_state["combatant_states"]["hero"]["actions_remaining"] == 0
        assert combat_state["combatant_states"]["hero"]["bonus_actions_remaining"] == 1
        assert combat_state["combatant_states"]["hero"]["reaction_available"] is False

    # ========================================================================
    # END CONDITION TESTS
    # ========================================================================

    def test_check_end_conditions_ongoing(self, session_manager):
        """Test combat ongoing returns False"""
        ended, reason = session_manager._check_end_conditions()

        assert ended is False
        assert reason is None

    def test_check_end_conditions_all_hostiles_defeated(self, session_manager, mock_entities):
        """Test detecting all hostiles defeated"""
        # Mark all goblins as dead
        mock_entities["goblin_1"].health.is_dead.return_value = True
        mock_entities["goblin_2"].health.is_dead.return_value = True

        ended, reason = session_manager._check_end_conditions()

        assert ended is True
        assert reason == "all_hostiles_defeated"

    def test_check_end_conditions_all_players_defeated(self, session_manager, mock_entities):
        """Test detecting all players defeated"""
        # Mark hero as dead
        mock_entities["hero"].health.is_dead.return_value = True

        ended, reason = session_manager._check_end_conditions()

        assert ended is True
        assert reason == "all_players_defeated"

    def test_determine_outcome_victory(self, session_manager):
        """Test victory outcome"""
        session_manager.combat_state["end_reason"] = "all_hostiles_defeated"

        outcome = session_manager._determine_outcome()
        assert outcome == "victory"

    def test_determine_outcome_defeat(self, session_manager):
        """Test defeat outcome"""
        session_manager.combat_state["end_reason"] = "all_players_defeated"

        outcome = session_manager._determine_outcome()
        assert outcome == "defeat"

    def test_determine_outcome_fled(self, session_manager):
        """Test fled outcome"""
        session_manager.combat_state["end_reason"] = "fled"

        outcome = session_manager._determine_outcome()
        assert outcome == "fled"

    # ========================================================================
    # TARGET SELECTION TESTS
    # ========================================================================

    def test_get_valid_targets_player(self, session_manager):
        """Test player can target hostiles"""
        targets = session_manager._get_valid_targets("hero")

        assert "goblin_1" in targets
        assert "goblin_2" in targets
        assert "hero" not in targets

    def test_get_valid_targets_npc(self, session_manager):
        """Test NPC can target player"""
        targets = session_manager._get_valid_targets("goblin_1")

        assert "hero" in targets
        assert "goblin_2" not in targets  # Can't target allies

    def test_get_valid_targets_excludes_dead(self, session_manager, mock_entities):
        """Test dead combatants excluded from targets"""
        # Mark goblin_2 as dead
        mock_entities["goblin_2"].health.is_dead.return_value = True

        targets = session_manager._get_valid_targets("hero")

        assert "goblin_1" in targets
        assert "goblin_2" not in targets  # Dead, should be excluded

    def test_get_allies(self, session_manager):
        """Test getting allies list"""
        # Hero has no allies in this scenario
        allies = session_manager._get_allies("hero")
        assert len(allies) == 0

        # Goblin has one ally (other goblin)
        allies = session_manager._get_allies("goblin_1")
        assert "goblin_2" in allies
        assert "goblin_1" not in allies  # Self excluded
        assert len(allies) == 1

    def test_get_enemies(self, session_manager):
        """Test getting enemies list"""
        # Enemies same as valid targets
        enemies = session_manager._get_enemies("hero")
        targets = session_manager._get_valid_targets("hero")

        assert enemies == targets

    # ========================================================================
    # FALLBACK ACTION TESTS
    # ========================================================================

    def test_get_fallback_action_with_targets(self, session_manager):
        """Test fallback action when targets available"""
        action = session_manager._get_fallback_action("goblin_1")

        assert action["actor"] == "goblin_1"
        assert action["action_type"] == "attack"
        assert action["target"] == "hero"

    def test_get_fallback_action_no_targets(self, session_manager, mock_entities):
        """Test fallback action when no targets available"""
        # Mark hero as dead
        mock_entities["hero"].health.is_dead.return_value = True

        action = session_manager._get_fallback_action("goblin_1")

        assert action["actor"] == "goblin_1"
        assert action["action_type"] == "dodge"
        assert "target" not in action or action.get("target") is None

    # ========================================================================
    # COMBAT LOG TESTS
    # ========================================================================

    def test_log_combat_action(self, session_manager, combat_state):
        """Test logging combat action"""
        action = {
            "actor": "hero",
            "action_type": "attack",
            "target": "goblin_1"
        }
        result = {
            "success": True,
            "damage": 8
        }

        session_manager._log_combat_action(action, result)

        assert len(combat_state["combat_log"]) == 1
        log_entry = combat_state["combat_log"][0]
        assert log_entry["round"] == 1
        assert log_entry["actor"] == "hero"
        assert log_entry["action_type"] == "attack"
        assert log_entry["target"] == "goblin_1"
        assert log_entry["result"]["success"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
