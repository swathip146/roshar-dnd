"""
Test Combat Session Manager - Internal Combat Turn Loop

Tests for CombatSessionManager which handles the complete combat turn loop
including player input, NPC AI, action execution, and end conditions.

Based on: COMBAT_ENGINE_IMPLEMENTATION_PLAN.md Phase 3
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from uuid import uuid4

from components.combat.combat_session_manager import CombatSessionManager


class TestCombatSessionManager:
    """Test suite for CombatSessionManager"""

    @pytest.fixture
    def combat_state(self):
        """Sample combat state"""
        return {
            "in_combat": True,
            "combat_id": "test_combat_001",
            "active_combatants": ["player_001", "goblin_001", "goblin_002"],
            "initiative_order": [
                {"char_id": "player_001", "initiative": 18},
                {"char_id": "goblin_001", "initiative": 15},
                {"char_id": "goblin_002", "initiative": 12}
            ],
            "current_turn_index": 0,
            "round_number": 1,
            "combat_log": [],
            "combatant_states": {
                "player_001": {
                    "hp_current": 25,
                    "hp_max": 25,
                    "conditions": [],
                    "actions_remaining": 1,
                    "bonus_actions_remaining": 1,
                    "reaction_available": True,
                    "is_hostile": False
                },
                "goblin_001": {
                    "hp_current": 7,
                    "hp_max": 7,
                    "conditions": [],
                    "actions_remaining": 1,
                    "bonus_actions_remaining": 1,
                    "reaction_available": True,
                    "is_hostile": True
                },
                "goblin_002": {
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
    def mock_game_engine(self):
        """Mock GameEngine"""
        return Mock()

    @pytest.fixture
    def mock_character_manager(self):
        """Mock CharacterManager"""
        manager = Mock()
        manager.characters = {
            "player_001": Mock(name="Aggi", attacks=[{"name": "Longsword"}]),
            "goblin_001": Mock(name="Goblin Warrior", attacks=[{"name": "Scimitar"}]),
            "goblin_002": Mock(name="Goblin Warrior", attacks=[{"name": "Scimitar"}])
        }
        return manager

    @pytest.fixture
    def mock_dnd_wrapper(self):
        """Mock DnDEngineWrapper"""
        wrapper = Mock()
        wrapper.entities = {}

        # Create mock entities
        for char_id in ["player_001", "goblin_001", "goblin_002"]:
            entity = Mock()
            entity.uuid = uuid4()
            entity.health = Mock()
            entity.health.is_unconscious = Mock(return_value=False)
            entity.health.is_dead = Mock(return_value=False)
            entity.health.get_current_hit_points = Mock(return_value=25 if "player" in char_id else 7)
            entity.health.get_max_hit_points = Mock(return_value=25 if "player" in char_id else 7)
            entity.action_economy = Mock()
            entity.action_economy.actions = 1
            entity.action_economy.bonus_actions = 1
            entity.action_economy.reactions = 1
            entity.action_economy.can_afford = Mock(return_value=True)
            entity.action_economy.reset = Mock()

            wrapper.entities[char_id] = entity

        return wrapper

    @pytest.fixture
    def mock_action_resolver(self):
        """Mock CombatActionResolver"""
        resolver = Mock()
        resolver.ACTION_REGISTRY = {
            "attack": {
                "type": "dnd_action",
                "description": "Attack with weapon",
                "params": ["target_entity_uuid"],
                "cost_type": "actions",
                "cost": 1
            },
            "dodge": {
                "type": "dnd_condition",
                "description": "Dodge",
                "params": [],
                "cost_type": "actions",
                "cost": 1
            }
        }
        resolver.resolve_action = Mock(return_value={
            "success": True,
            "damage": 8,
            "description": "Hit! Dealt 8 damage."
        })
        return resolver

    @pytest.fixture
    def mock_narrative_gen(self):
        """Mock CombatNarrativeGenerator"""
        gen = Mock()
        gen.generate_combat_status = Mock(return_value="=== COMBAT STATUS ===\nRound: 1")
        gen.generate_action_narrative = Mock(return_value="The blade strikes true!\n💥 Hit! 8 damage dealt.")
        return gen

    @pytest.fixture
    def mock_npc_ai(self):
        """Mock NPCAIAgent"""
        ai = Mock()
        ai.decide_action = Mock(return_value={
            "action_type": "attack",
            "target": "player_001",
            "weapon": "scimitar",
            "reasoning": "Attack closest enemy"
        })
        return ai

    @pytest.fixture
    def session_manager(self, combat_state, mock_game_engine, mock_character_manager,
                        mock_dnd_wrapper, mock_action_resolver, mock_narrative_gen, mock_npc_ai):
        """Create CombatSessionManager instance"""
        return CombatSessionManager(
            combat_state=combat_state,
            game_engine=mock_game_engine,
            character_manager=mock_character_manager,
            dnd_engine_wrapper=mock_dnd_wrapper,
            combat_action_resolver=mock_action_resolver,
            combat_narrative_generator=mock_narrative_gen,
            npc_ai_agent=mock_npc_ai
        )

    def test_initialization(self, session_manager):
        """Test CombatSessionManager initializes correctly"""
        assert session_manager.combat_state is not None
        assert session_manager.game_engine is not None
        assert session_manager.character_manager is not None
        assert session_manager.dnd_wrapper is not None
        assert session_manager.action_resolver is not None
        assert session_manager.narrative_gen is not None
        assert session_manager.npc_ai is not None

    def test_get_current_actor(self, session_manager):
        """Test getting current actor from initiative order"""
        actor_id = session_manager._get_current_actor()
        assert actor_id == "player_001"

        session_manager.combat_state["current_turn_index"] = 1
        actor_id = session_manager._get_current_actor()
        assert actor_id == "goblin_001"

    def test_is_player(self, session_manager):
        """Test checking if character is a player"""
        assert session_manager._is_player("player_001") is True
        assert session_manager._is_player("goblin_001") is False

    def test_is_combatant_dead_alive(self, session_manager, mock_dnd_wrapper):
        """Test checking if combatant is dead/unconscious (alive)"""
        mock_dnd_wrapper.entities["player_001"].health.is_unconscious.return_value = False
        mock_dnd_wrapper.entities["player_001"].health.is_dead.return_value = False

        is_dead = session_manager._is_combatant_dead("player_001")
        assert is_dead is False

    def test_is_combatant_dead_unconscious(self, session_manager, mock_dnd_wrapper):
        """Test checking if combatant is unconscious"""
        mock_dnd_wrapper.entities["goblin_001"].health.is_unconscious.return_value = True
        mock_dnd_wrapper.entities["goblin_001"].health.is_dead.return_value = False

        is_dead = session_manager._is_combatant_dead("goblin_001")
        assert is_dead is True

    def test_is_combatant_dead_dead(self, session_manager, mock_dnd_wrapper):
        """Test checking if combatant is dead"""
        mock_dnd_wrapper.entities["goblin_002"].health.is_unconscious.return_value = False
        mock_dnd_wrapper.entities["goblin_002"].health.is_dead.return_value = True

        is_dead = session_manager._is_combatant_dead("goblin_002")
        assert is_dead is True

    def test_check_end_conditions_combat_ongoing(self, session_manager):
        """Test checking end conditions when combat is ongoing"""
        ended, reason = session_manager._check_end_conditions()

        assert ended is False
        assert reason is None

    def test_check_end_conditions_all_hostiles_defeated(self, session_manager, mock_dnd_wrapper):
        """Test checking end conditions when all hostiles defeated"""
        # Mark all goblins as dead
        mock_dnd_wrapper.entities["goblin_001"].health.is_dead.return_value = True
        mock_dnd_wrapper.entities["goblin_002"].health.is_dead.return_value = True

        ended, reason = session_manager._check_end_conditions()

        assert ended is True
        assert reason == "all_hostiles_defeated"

    def test_check_end_conditions_all_players_defeated(self, session_manager, mock_dnd_wrapper):
        """Test checking end conditions when all players defeated"""
        # Mark player as dead
        mock_dnd_wrapper.entities["player_001"].health.is_dead.return_value = True

        ended, reason = session_manager._check_end_conditions()

        assert ended is True
        assert reason == "all_players_defeated"

    def test_determine_outcome_victory(self, session_manager):
        """Test determining outcome as victory"""
        session_manager.combat_state["end_reason"] = "all_hostiles_defeated"

        outcome = session_manager._determine_outcome()
        assert outcome == "victory"

    def test_determine_outcome_defeat(self, session_manager):
        """Test determining outcome as defeat"""
        session_manager.combat_state["end_reason"] = "all_players_defeated"

        outcome = session_manager._determine_outcome()
        assert outcome == "defeat"

    def test_has_actions_remaining_true(self, session_manager, mock_dnd_wrapper):
        """Test checking if combatant has actions remaining (true)"""
        mock_dnd_wrapper.entities["player_001"].action_economy.actions = 1
        mock_dnd_wrapper.entities["player_001"].action_economy.bonus_actions = 0

        has_actions = session_manager._has_actions_remaining("player_001")
        assert has_actions is True

    def test_has_actions_remaining_false(self, session_manager, mock_dnd_wrapper):
        """Test checking if combatant has actions remaining (false)"""
        mock_dnd_wrapper.entities["player_001"].action_economy.actions = 0
        mock_dnd_wrapper.entities["player_001"].action_economy.bonus_actions = 0

        has_actions = session_manager._has_actions_remaining("player_001")
        assert has_actions is False

    def test_consume_action_syncs_to_combat_state(self, session_manager, mock_dnd_wrapper):
        """Test consuming action syncs dnd_engine state to combat_state"""
        mock_dnd_wrapper.entities["player_001"].action_economy.actions = 0
        mock_dnd_wrapper.entities["player_001"].action_economy.bonus_actions = 1
        mock_dnd_wrapper.entities["player_001"].action_economy.reactions = 0

        session_manager._consume_action("player_001", "attack")

        # Verify combat_state was synced
        assert session_manager.combat_state["combatant_states"]["player_001"]["actions_remaining"] == 0
        assert session_manager.combat_state["combatant_states"]["player_001"]["bonus_actions_remaining"] == 1
        assert session_manager.combat_state["combatant_states"]["player_001"]["reaction_available"] is False

    def test_advance_turn_within_round(self, session_manager):
        """Test advancing turn within same round"""
        initial_index = session_manager.combat_state["current_turn_index"]
        initial_round = session_manager.combat_state["round_number"]

        session_manager._advance_turn()

        assert session_manager.combat_state["current_turn_index"] == initial_index + 1
        assert session_manager.combat_state["round_number"] == initial_round

    def test_advance_turn_new_round(self, session_manager, mock_dnd_wrapper):
        """Test advancing turn to new round"""
        # Set to last combatant in initiative order
        session_manager.combat_state["current_turn_index"] = 2

        session_manager._advance_turn()

        # Should wrap to index 0 and increment round
        assert session_manager.combat_state["current_turn_index"] == 0
        assert session_manager.combat_state["round_number"] == 2

        # Verify action economy was reset for all combatants
        for char_id in session_manager.combat_state["active_combatants"]:
            mock_dnd_wrapper.entities[char_id].action_economy.reset.assert_called()

    def test_log_combat_action(self, session_manager):
        """Test logging combat action"""
        action = {
            "actor": "player_001",
            "action_type": "attack",
            "target": "goblin_001"
        }
        result = {
            "success": True,
            "damage": 8
        }

        session_manager._log_combat_action(action, result)

        assert len(session_manager.combat_state["combat_log"]) == 1
        log_entry = session_manager.combat_state["combat_log"][0]
        assert log_entry["round"] == 1
        assert log_entry["actor"] == "player_001"
        assert log_entry["action_type"] == "attack"
        assert log_entry["target"] == "goblin_001"
        assert log_entry["result"] == result

    def test_get_valid_targets(self, session_manager):
        """Test getting valid targets for character"""
        # Player should target hostiles
        targets = session_manager._get_valid_targets("player_001")
        assert "goblin_001" in targets
        assert "goblin_002" in targets
        assert "player_001" not in targets

        # Goblin should target player
        targets = session_manager._get_valid_targets("goblin_001")
        assert "player_001" in targets
        assert "goblin_002" not in targets

    def test_get_valid_targets_excludes_dead(self, session_manager, mock_dnd_wrapper):
        """Test getting valid targets excludes dead combatants"""
        # Mark goblin_002 as dead
        mock_dnd_wrapper.entities["goblin_002"].health.is_dead.return_value = True

        targets = session_manager._get_valid_targets("player_001")

        assert "goblin_001" in targets
        assert "goblin_002" not in targets

    def test_get_allies(self, session_manager):
        """Test getting allies"""
        # Player has no allies in this test
        allies = session_manager._get_allies("player_001")
        assert len(allies) == 0

        # Goblin has one ally (other goblin)
        allies = session_manager._get_allies("goblin_001")
        assert "goblin_002" in allies
        assert len(allies) == 1

    def test_get_enemies(self, session_manager):
        """Test getting enemies (same as valid targets)"""
        enemies = session_manager._get_enemies("player_001")
        targets = session_manager._get_valid_targets("player_001")

        assert enemies == targets

    def test_get_fallback_action_with_targets(self, session_manager):
        """Test getting fallback action when targets available"""
        action = session_manager._get_fallback_action("goblin_001")

        assert action["actor"] == "goblin_001"
        assert action["action_type"] == "attack"
        assert action["target"] == "player_001"

    def test_get_fallback_action_no_targets(self, session_manager, mock_dnd_wrapper):
        """Test getting fallback action when no targets available"""
        # Mark all enemies as dead
        mock_dnd_wrapper.entities["player_001"].health.is_dead.return_value = True

        action = session_manager._get_fallback_action("goblin_001")

        assert action["actor"] == "goblin_001"
        assert action["action_type"] == "dodge"

    def test_build_npc_context(self, session_manager, mock_dnd_wrapper):
        """Test building NPC AI context"""
        context = session_manager._build_npc_context("goblin_001")

        assert context["npc"] is not None
        assert context["npc_hp"] == 7
        assert context["npc_max_hp"] == 7
        assert "player_001" in context["available_targets"]
        assert "attack" in context["available_actions"]
        assert context["round_number"] == 1

    def test_execute_npc_turn(self, session_manager, mock_npc_ai, mock_action_resolver):
        """Test executing NPC turn"""
        with patch('builtins.print'):  # Suppress print output
            session_manager._execute_npc_turn("goblin_001")

        # Verify NPC AI was called
        mock_npc_ai.decide_action.assert_called_once()

        # Verify action was resolved
        mock_action_resolver.resolve_action.assert_called_once()

        # Verify combat log was updated
        assert len(session_manager.combat_state["combat_log"]) == 1

    def test_can_character_afford_action(self, session_manager, mock_action_resolver):
        """Test checking if character can afford action"""
        metadata = mock_action_resolver.ACTION_REGISTRY["attack"]

        can_afford = session_manager._can_character_afford_action("player_001", metadata)

        # Mock returns True
        assert can_afford is True

    def test_character_meets_requirements_no_requirements(self, session_manager, mock_character_manager):
        """Test character meets requirements when no requirements specified"""
        metadata = {"requires": None}
        character = mock_character_manager.characters["player_001"]

        meets_req = session_manager._character_meets_requirements(character, metadata)

        assert meets_req is True

    def test_validate_action_valid(self, session_manager):
        """Test validating valid action"""
        action = {
            "actor": "player_001",
            "action_type": "attack",
            "target": "goblin_001"
        }

        is_valid = session_manager._validate_action(action)

        assert is_valid is True

    def test_validate_action_invalid_target(self, session_manager):
        """Test validating action with invalid target"""
        action = {
            "actor": "player_001",
            "action_type": "attack",
            "target": "nonexistent_target"
        }

        # Attack is a dnd_action, so high-level validation passes
        # (dnd_engine will validate target during execution)
        is_valid = session_manager._validate_action(action)

        assert is_valid is True

    def test_validate_action_unknown_type(self, session_manager):
        """Test validating action with unknown type"""
        action = {
            "actor": "player_001",
            "action_type": "unknown_action"
        }

        is_valid = session_manager._validate_action(action)

        assert is_valid is False

    def test_parse_hierarchical_action(self, session_manager):
        """Test parsing hierarchical menu selection"""
        action_item = {
            "action_type": "attack",
            "display": "Attack Goblin",
            "params": {"target": "goblin_001"}
        }

        action = session_manager._parse_hierarchical_action("player_001", "standard_actions", action_item)

        assert action["actor"] == "player_001"
        assert action["action_type"] == "attack"
        assert action["target"] == "goblin_001"

    def test_categorize_action_standard(self, session_manager):
        """Test categorizing standard action"""
        metadata = {"type": "dnd_action"}

        category = session_manager._categorize_action("attack", metadata)

        assert category == "standard_actions"

    def test_categorize_action_utility(self, session_manager):
        """Test categorizing utility action"""
        metadata = {"type": "dnd_condition"}

        category = session_manager._categorize_action("dodge", metadata)

        assert category == "utility"

    def test_generate_action_options_with_targets(self, session_manager, mock_action_resolver):
        """Test generating action options with targeting"""
        metadata = mock_action_resolver.ACTION_REGISTRY["attack"]

        options = session_manager._generate_action_options("player_001", "attack", metadata)

        # Should have options for each valid target
        assert len(options) == 2  # Two goblins
        assert all("goblin" in opt["params"]["target"] for opt in options)

    def test_generate_action_options_no_targets(self, session_manager, mock_action_resolver):
        """Test generating action options without targeting"""
        metadata = mock_action_resolver.ACTION_REGISTRY["dodge"]

        options = session_manager._generate_action_options("player_001", "dodge", metadata)

        # Should have single option with no target
        assert len(options) == 1
        assert options[0]["action_type"] == "dodge"
        assert options[0]["params"] == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
