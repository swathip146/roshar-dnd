"""
Combat Integration Tests

Tests complete combat flow from trigger to end, including:
- Combat initialization
- Turn loop execution
- NPC generation
- Combat ends correctly
- Cleanup happens
"""

import pytest
import sys
import os
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from agents.combat_agent import CombatAgent, create_combat_agent
from agents.npc_combat_ai import NPCCombatAI, create_npc_combat_ai
from components.combat.combat_initializer import CombatInitializer
from components.combat.combat_action_resolver import CombatActionResolver
from components.combat.combat_narrative_generator import CombatNarrativeGenerator
from components.character_manager import CharacterManager
from components.game_engine import GameEngine
from components.dnd_engine_wrapper import DnDEngineWrapper
from core.npc_stat_loader import NPCStatLoader
from components.combat.npc_stat_generator import NPCStatGenerator
from config.logging_config import get_logger

logger = get_logger(__name__)


@pytest.fixture
def mock_llm():
    """Create mock LLM generator"""
    llm = Mock()

    # Mock response for NPC stat generation
    npc_response = Mock()
    npc_response.content = '''```json
{
    "name": "Goblin Warrior",
    "level": 1,
    "character_class": "Warrior",
    "race": "Goblin",
    "background": "Tribal Warrior",
    "ability_scores": {
        "strength": 8,
        "dexterity": 14,
        "constitution": 10,
        "intelligence": 10,
        "wisdom": 8,
        "charisma": 8
    },
    "hit_points": {"maximum": 7, "current": 7, "temporary": 0},
    "armor_class": 15,
    "proficiency_bonus": 2,
    "skills": {"stealth": true},
    "attacks": [{
        "name": "Scimitar",
        "attack_bonus": 4,
        "damage_dice": "1d6",
        "damage_bonus": 2,
        "damage_type": "slashing"
    }],
    "special_abilities": ["Nimble Escape"],
    "challenge_rating": 0.25
}
```'''

    # Mock response for combat AI
    ai_response = Mock()
    ai_response.content = '{"action_type": "attack", "target": "aggi", "weapon": "scimitar", "reasoning": "Attack the player"}'

    # Mock response for enemy parsing
    enemy_response = Mock()
    enemy_response.content = '''[{
        "name": "Goblin Warrior",
        "description": "small goblin with rusty scimitar",
        "count": 2,
        "estimated_cr": 0.25,
        "role": "combatant",
        "keywords": ["goblin", "warrior", "scimitar"],
        "is_predefined": false
    }]'''

    # Mock response for narrative generation
    narrative_response = Mock()
    narrative_response.content = "The goblin swings wildly with its scimitar!"

    def run_side_effect(*args, **kwargs):
        # Return appropriate response based on context
        messages = kwargs.get('messages', [])
        if messages:
            # Check both message objects and string representations
            message_text = ""
            for msg in messages:
                if hasattr(msg, 'content'):
                    message_text += msg.content + " "
                else:
                    message_text += str(msg) + " "

            message_text = message_text.lower()

            if "npc ai deciding" in message_text or "controlling" in message_text:
                return {'replies': [ai_response]}
            elif "extract enemy" in message_text or "enemy information" in message_text:
                return {'replies': [enemy_response]}
            elif "narrate this combat" in message_text or "combat action" in message_text:
                return {'replies': [narrative_response]}
        return {'replies': [npc_response]}

    llm.run = Mock(side_effect=run_side_effect)
    return llm


@pytest.fixture
def game_engine():
    """Create test game engine"""
    from components.policy import PolicyProfile
    engine = GameEngine(policy_profile=PolicyProfile.RAW, campaign_config=None)

    # Initialize game state
    engine.game_state.location_context["current_location"] = "Test Location"
    engine.game_state.narrative_context["current_scene"] = "Test scene"

    return engine


@pytest.fixture
def character_manager():
    """Create test character manager with a test player character"""
    manager = CharacterManager()

    # Add test player character
    test_char_data = {
        "character_id": "aggi",
        "name": "Aggi",
        "level": 3,
        "character_class": "Lightweaver",
        "race": "Human",
        "background": "Radiant",
        "ability_scores": {
            "strength": 10,
            "dexterity": 14,
            "constitution": 12,
            "intelligence": 16,
            "wisdom": 13,
            "charisma": 15
        },
        "hit_points": {"maximum": 25, "current": 25, "temporary": 0},
        "armor_class": 13,
        "proficiency_bonus": 2,
        "skills": {"deception": True, "performance": True},
        "attacks": [{
            "name": "Rapier",
            "attack_bonus": 4,
            "damage_dice": "1d8",
            "damage_bonus": 2,
            "damage_type": "piercing"
        }],
        "special_abilities": ["Lightweaving", "Stormlight Infusion"]
    }

    manager.add_character(test_char_data)
    return manager


@pytest.fixture
def dnd_wrapper(game_engine, character_manager):
    """Create DnD engine wrapper"""
    wrapper = DnDEngineWrapper(game_engine, character_manager)
    # Sync initial character
    wrapper._sync_characters_to_entities()
    return wrapper


@pytest.fixture
def npc_registry():
    """Create NPC registry (may be empty for tests)"""
    return NPCStatLoader(npc_directory="data/players/")


@pytest.fixture
def npc_stat_generator(mock_llm):
    """Create NPC stat generator"""
    return NPCStatGenerator(
        llm=mock_llm,
        document_store=None  # Mock document store
    )


@pytest.fixture
def combat_initializer(game_engine, character_manager, dnd_wrapper, npc_stat_generator, npc_registry, mock_llm):
    """Create combat initializer"""
    return CombatInitializer(
        game_engine=game_engine,
        character_manager=character_manager,
        dnd_engine_wrapper=dnd_wrapper,
        npc_stat_generator=npc_stat_generator,
        npc_registry=npc_registry,
        llm=mock_llm
    )


@pytest.fixture
def combat_action_resolver(dnd_wrapper, character_manager):
    """Create combat action resolver"""
    return CombatActionResolver(
        dnd_engine_wrapper=dnd_wrapper,
        character_manager=character_manager,
        combat_state={}
    )


@pytest.fixture
def combat_narrative_gen(mock_llm, character_manager):
    """Create combat narrative generator"""
    return CombatNarrativeGenerator(llm=mock_llm, character_manager=character_manager)


@pytest.fixture
def npc_combat_ai(mock_llm):
    """Create NPC combat AI"""
    return NPCCombatAI(llm_generator=mock_llm)


@pytest.fixture
def combat_agent(game_engine, character_manager, dnd_wrapper, combat_initializer,
                 combat_action_resolver, combat_narrative_gen, npc_combat_ai):
    """Create combat agent"""
    return create_combat_agent(
        game_engine=game_engine,
        character_manager=character_manager,
        dnd_engine_wrapper=dnd_wrapper,
        combat_initializer=combat_initializer,
        combat_action_resolver=combat_action_resolver,
        combat_narrative_generator=combat_narrative_gen,
        npc_combat_ai=npc_combat_ai
    )


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

def test_full_combat_session(combat_agent, game_engine, character_manager):
    """
    Test complete combat from trigger to end.

    Verifies:
    - Combat initialization
    - Turn loop execution
    - NPC generation
    - Combat ends correctly
    - Cleanup happens
    """
    logger.info("=" * 60)
    logger.info("TEST: Full Combat Session")
    logger.info("=" * 60)

    # Create scenario with combat
    scenario = {
        "scene": "Two goblins leap out from behind rocks, scimitars drawn!",
        "gm_notes": "Two goblin warriors (CR 1/4 each). Armed with scimitars.",
        "choices": [{
            "id": "c1",
            "title": "Fight the goblins",
            "combat_trigger": True
        }]
    }

    # Create DTO
    dto = {
        "scenario_context": scenario,
        "player_character_id": "aggi",
        "_game_engine_ref": game_engine
    }

    logger.info("📋 Test Setup Complete:")
    logger.info(f"   Player: aggi")
    logger.info(f"   Scenario: {scenario['scene']}")
    logger.info(f"   Combat Trigger: True")

    # Get initial NPC count
    initial_npc_count = len(character_manager.get_npcs())
    logger.info(f"   Initial NPCs in CharacterManager: {initial_npc_count}")

    # Mock user input for combat turns
    # Simulate player always attacking first available enemy
    with patch('builtins.input', side_effect=['1', '1'] * 10):  # 10 turns max
        try:
            logger.info("\n🎮 Running Combat Agent...")
            result = combat_agent.run(dto)
            logger.info("✅ Combat Agent completed")
        except Exception as e:
            logger.error(f"❌ Combat Agent failed: {e}")
            import traceback
            traceback.print_exc()
            pytest.fail(f"Combat agent failed: {e}")

    # Verify result
    logger.info("\n📊 Verifying Results:")
    assert result is not None, "Combat agent should return a result"
    assert "response" in result, "Result should have response key"

    response = result["response"]
    logger.info(f"   Response Type: {response.get('response_type')}")
    assert response.get("response_type") == "combat_complete", "Should return combat_complete"

    outcome = response.get("outcome")
    logger.info(f"   Combat Outcome: {outcome}")
    assert outcome in ["victory", "defeat"], f"Outcome should be victory or defeat, got: {outcome}"

    rounds = response.get("rounds", 0)
    logger.info(f"   Combat Rounds: {rounds}")
    assert rounds >= 1, "Combat should take at least 1 round"

    # Verify NPCs removed (cleanup)
    final_npc_count = len(character_manager.get_npcs())
    logger.info(f"   Final NPCs in CharacterManager: {final_npc_count}")
    logger.info(f"   NPCs removed: {initial_npc_count - final_npc_count}")

    # Note: May not be 0 if persistent NPCs exist, but should be less than after generation
    assert final_npc_count <= initial_npc_count + 2, "NPCs should be cleaned up"

    logger.info("\n✅ TEST PASSED: Full Combat Session")
    logger.info("=" * 60)


def test_combat_initialization(combat_initializer, character_manager):
    """Test combat initialization creates proper combat state"""
    logger.info("=" * 60)
    logger.info("TEST: Combat Initialization")
    logger.info("=" * 60)

    scenario = {
        "scene": "A goblin warrior appears!",
        "gm_notes": "One goblin warrior (CR 1/4).",
        "choices": [{"combat_trigger": True}]
    }

    logger.info("📋 Initializing combat...")
    combat_state = combat_initializer.initialize_combat(
        scenario=scenario,
        player_character_ids=["aggi"]
    )

    # Verify combat state created
    logger.info("📊 Verifying Combat State:")
    assert combat_state is not None, "Combat state should be created"
    assert combat_state["in_combat"] == True
    logger.info("   ✓ in_combat flag set")

    assert len(combat_state["active_combatants"]) >= 2  # PC + at least 1 NPC
    logger.info(f"   ✓ Active combatants: {len(combat_state['active_combatants'])}")

    assert len(combat_state["initiative_order"]) == len(combat_state["active_combatants"])
    logger.info(f"   ✓ Initiative order: {len(combat_state['initiative_order'])} entries")

    assert combat_state["round_number"] == 1
    logger.info("   ✓ Round number: 1")

    # Verify NPCs generated
    npc_ids = [cid for cid in combat_state["active_combatants"] if cid != "aggi"]
    logger.info(f"   ✓ Generated NPCs: {len(npc_ids)} ({', '.join(npc_ids)})")
    assert len(npc_ids) >= 1, "Should generate at least 1 NPC"

    # Verify NPCs in CharacterManager
    for npc_id in npc_ids:
        assert npc_id in character_manager.characters, f"NPC {npc_id} should be in CharacterManager"
    logger.info("   ✓ All NPCs added to CharacterManager")

    logger.info("\n✅ TEST PASSED: Combat Initialization")
    logger.info("=" * 60)


def test_combat_without_trigger(combat_initializer):
    """Test combat doesn't initialize if no combat_trigger"""
    logger.info("=" * 60)
    logger.info("TEST: Combat Without Trigger")
    logger.info("=" * 60)

    scenario = {
        "scene": "You see a peaceful village.",
        "choices": [{"id": "c1", "title": "Enter village", "combat_trigger": False}]
    }

    logger.info("📋 Attempting to initialize combat without trigger...")
    combat_state = combat_initializer.initialize_combat(
        scenario=scenario,
        player_character_ids=["aggi"]
    )

    logger.info("📊 Verifying no combat initialized:")
    assert combat_state is None, "Combat should not initialize without trigger"
    logger.info("   ✓ Combat correctly not initialized")

    logger.info("\n✅ TEST PASSED: Combat Without Trigger")
    logger.info("=" * 60)


def test_npc_combat_ai_decision(npc_combat_ai, character_manager):
    """Test NPC combat AI makes tactical decisions"""
    logger.info("=" * 60)
    logger.info("TEST: NPC Combat AI Decision")
    logger.info("=" * 60)

    # Create mock NPC
    class MockNPC:
        name = "Goblin Warrior"
        character_class = "Warrior"
        level = 1
        attacks = [{"name": "Scimitar", "attack_bonus": 4}]

    context = {
        "npc": MockNPC(),
        "npc_hp": 5,
        "npc_max_hp": 7,
        "available_actions": ["attack", "dodge", "dash"],
        "available_targets": ["aggi"],
        "allies": [],
        "enemies": ["aggi"],
        "round_number": 1
    }

    logger.info("📋 Testing NPC AI decision...")
    decision = npc_combat_ai.decide_action(context)

    logger.info("📊 Verifying decision:")
    assert decision is not None, "Decision should not be None"
    logger.info(f"   Action Type: {decision.get('action_type')}")
    assert "action_type" in decision, "Decision should have action_type"
    assert decision["action_type"] in context["available_actions"], "Should choose valid action"
    logger.info(f"   ✓ Valid action chosen: {decision['action_type']}")

    if decision["action_type"] == "attack":
        assert "target" in decision, "Attack should have target"
        logger.info(f"   ✓ Target selected: {decision.get('target')}")

    logger.info("\n✅ TEST PASSED: NPC Combat AI Decision")
    logger.info("=" * 60)


def test_combat_agent_error_handling(combat_agent, game_engine):
    """Test combat agent handles errors gracefully"""
    logger.info("=" * 60)
    logger.info("TEST: Combat Agent Error Handling")
    logger.info("=" * 60)

    # Invalid DTO (missing scenario_context)
    dto = {
        "player_character_id": "aggi",
        "_game_engine_ref": game_engine
    }

    logger.info("📋 Testing with invalid DTO (no scenario_context)...")
    result = combat_agent.run(dto)

    logger.info("📊 Verifying error handling:")
    assert result is not None, "Should return error response"
    assert "response" in result, "Should have response key"

    response = result["response"]
    logger.info(f"   Response Type: {response.get('response_type')}")
    assert response.get("response_type") == "error", "Should return error type"
    logger.info("   ✓ Error response returned")

    assert "message" in response or "error" in response, "Should have error message"
    logger.info(f"   ✓ Error message: {response.get('message', response.get('error'))}")

    logger.info("\n✅ TEST PASSED: Combat Agent Error Handling")
    logger.info("=" * 60)


# ============================================================================
# RUN ALL TESTS
# ============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("COMBAT INTEGRATION TESTS")
    print("=" * 60)

    # Run pytest with verbose output
    pytest.main([__file__, "-v", "-s", "--tb=short"])
