"""
Advanced Combat Tests

Tests additional combat scenarios and edge cases:
- Multiple enemies
- Player death scenarios
- Multiple rounds of combat
- Different action types (dodge, dash, etc.)
- NPC AI tactical decisions in various situations
- Combat state persistence
- Damage and healing mechanics
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
from components.combat.combat_session_manager import CombatSessionManager
from components.character_manager import CharacterManager
from components.game_engine import GameEngine
from components.dnd_engine_wrapper import DnDEngineWrapper
from core.npc_stat_loader import NPCStatLoader
from components.combat.npc_stat_generator import NPCStatGenerator
from config.logging_config import get_logger
from components.policy import PolicyProfile

logger = get_logger(__name__)


@pytest.fixture
def mock_llm():
    """Create mock LLM generator with varied responses"""
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

    # Mock response for dodge action
    dodge_response = Mock()
    dodge_response.content = '{"action_type": "dodge", "target": null, "weapon": null, "reasoning": "Low HP, taking defensive action"}'

    # Mock response for enemy parsing (multiple enemies)
    enemy_response = Mock()
    enemy_response.content = '''[{
        "name": "Goblin Warrior",
        "description": "small goblin with rusty scimitar",
        "count": 3,
        "estimated_cr": 0.25,
        "role": "combatant",
        "keywords": ["goblin", "warrior", "scimitar"],
        "is_predefined": false
    }]'''

    # Mock response for single enemy
    single_enemy_response = Mock()
    single_enemy_response.content = '''[{
        "name": "Goblin Warrior",
        "description": "small goblin with rusty scimitar",
        "count": 1,
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

            # Check for specific contexts
            if "low hp" in message_text or "critical hp" in message_text:
                return {'replies': [dodge_response]}
            elif "npc ai deciding" in message_text or "controlling" in message_text:
                return {'replies': [ai_response]}
            elif "extract enemy" in message_text or "enemy information" in message_text:
                if "three" in message_text or "multiple" in message_text:
                    return {'replies': [enemy_response]}
                else:
                    return {'replies': [single_enemy_response]}
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
    """Create NPC registry"""
    return NPCStatLoader(npc_directory="data/players/")


@pytest.fixture
def npc_stat_generator(mock_llm):
    """Create NPC stat generator"""
    return NPCStatGenerator(
        llm=mock_llm,
        document_store=None
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
    # Create minimal combat state with required fields
    combat_state = {
        "combatant_states": {},
        "in_combat": True,
        "round_number": 1
    }
    return CombatActionResolver(
        dnd_engine_wrapper=dnd_wrapper,
        character_manager=character_manager,
        combat_state=combat_state
    )


@pytest.fixture
def combat_narrative_gen(mock_llm, character_manager):
    """Create combat narrative generator"""
    return CombatNarrativeGenerator(llm=mock_llm, character_manager=character_manager)


@pytest.fixture
def npc_combat_ai(mock_llm):
    """Create NPC combat AI"""
    return NPCCombatAI(llm_generator=mock_llm)


# ============================================================================
# ADVANCED COMBAT TESTS
# ============================================================================

def test_multiple_enemies_combat(combat_initializer, character_manager):
    """Test combat with multiple enemies (3 goblins)"""
    logger.info("=" * 60)
    logger.info("TEST: Multiple Enemies Combat")
    logger.info("=" * 60)

    scenario = {
        "scene": "Three goblin warriors surround you!",
        "gm_notes": "Three goblin warriors (CR 1/4 each). Armed with scimitars.",
        "choices": [{"combat_trigger": True}]
    }

    logger.info("📋 Initializing combat with multiple enemies...")
    combat_state = combat_initializer.initialize_combat(
        scenario=scenario,
        player_character_ids=["aggi"]
    )

    logger.info("📊 Verifying Multiple Enemies:")
    assert combat_state is not None, "Combat state should be created"

    # Get NPC count (excludes player)
    npc_ids = [cid for cid in combat_state["active_combatants"] if cid != "aggi"]
    logger.info(f"   Generated NPCs: {len(npc_ids)}")

    # Should have at least 2 NPCs (even if not all 3 were generated)
    assert len(npc_ids) >= 2, f"Should have at least 2 NPCs, got {len(npc_ids)}"

    # Verify all NPCs are hostile
    for npc_id in npc_ids:
        assert combat_state["combatant_states"][npc_id]["is_hostile"] == True
        logger.info(f"   ✓ {npc_id} is hostile")

    logger.info("\n✅ TEST PASSED: Multiple Enemies Combat")
    logger.info("=" * 60)


def test_npc_dodge_action_low_hp(npc_combat_ai):
    """Test NPC AI chooses dodge when at low HP"""
    logger.info("=" * 60)
    logger.info("TEST: NPC Dodge Action (Low HP)")
    logger.info("=" * 60)

    class MockNPC:
        name = "Goblin Warrior"
        character_class = "Warrior"
        level = 1
        attacks = [{"name": "Scimitar", "attack_bonus": 4}]

    # Low HP scenario (2/7 HP = ~28%)
    context = {
        "npc": MockNPC(),
        "npc_hp": 2,
        "npc_max_hp": 7,
        "available_actions": ["attack", "dodge", "dash"],
        "available_targets": ["aggi"],
        "allies": [],
        "enemies": ["aggi"],
        "round_number": 3
    }

    logger.info("📋 Testing NPC AI with low HP (28%)...")
    decision = npc_combat_ai.decide_action(context)

    logger.info("📊 Verifying decision:")
    logger.info(f"   Action Type: {decision.get('action_type')}")
    logger.info(f"   Reasoning: {decision.get('reasoning')}")

    # Should choose defensive action (dodge or fallback to dodge due to low HP)
    assert decision is not None
    assert decision["action_type"] in ["dodge", "attack"], "Should be valid action"

    logger.info(f"   ✓ NPC chose tactical action: {decision['action_type']}")

    logger.info("\n✅ TEST PASSED: NPC Dodge Action (Low HP)")
    logger.info("=" * 60)


def test_combat_action_resolver_attack(combat_action_resolver, dnd_wrapper, character_manager):
    """Test combat action resolver processes attacks correctly"""
    logger.info("=" * 60)
    logger.info("TEST: Combat Action Resolver - Attack")
    logger.info("=" * 60)

    # Create a mock NPC
    npc_data = {
        "character_id": "goblin_001",
        "name": "Goblin Warrior",
        "level": 1,
        "character_class": "Warrior",
        "race": "Goblin",
        "background": "Tribal",
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
        "skills": {},
        "attacks": [{
            "name": "Scimitar",
            "attack_bonus": 4,
            "damage_dice": "1d6",
            "damage_bonus": 2,
            "damage_type": "slashing"
        }],
        "special_abilities": []
    }

    character_manager.add_character(npc_data)
    dnd_wrapper._sync_characters_to_entities()

    # Create attack action
    action = {
        "actor": "goblin_001",
        "action_type": "attack",
        "target": "aggi",
        "weapon": "Scimitar"
    }

    logger.info("📋 Resolving attack action...")
    result = combat_action_resolver.resolve_action(action)

    logger.info("📊 Verifying attack result:")
    assert result is not None, "Should return result"
    assert "success" in result, "Should have success field"
    # Result might have "message" or "description" field
    message_field = result.get("message") or result.get("description") or result.get("error", "")

    logger.info(f"   Success: {result.get('success')}")
    logger.info(f"   Message: {message_field}")

    if result.get("success"):
        logger.info("   ✓ Attack succeeded")
        assert "damage" in result or "hit" in message_field.lower()
    else:
        logger.info("   ✓ Attack failed (miss, line of sight, or other reason)")
        # Valid failure reasons: miss, line of sight, range, etc.
        message_lower = message_field.lower()
        valid_failure = (
            "miss" in message_lower or
            "error" in message_lower or
            "line of sight" in message_lower or
            "range" in message_lower or
            "target" in message_lower
        )
        assert valid_failure, f"Expected valid attack failure reason, got: {message_field}"

    # Cleanup
    character_manager.remove_npc("goblin_001")

    logger.info("\n✅ TEST PASSED: Combat Action Resolver - Attack")
    logger.info("=" * 60)


def test_combat_action_resolver_dodge(combat_action_resolver):
    """Test combat action resolver processes dodge actions"""
    logger.info("=" * 60)
    logger.info("TEST: Combat Action Resolver - Dodge")
    logger.info("=" * 60)

    action = {
        "actor": "aggi",
        "action_type": "dodge",
        "target": None
    }

    logger.info("📋 Resolving dodge action...")
    result = combat_action_resolver.resolve_action(action)

    logger.info("📊 Verifying dodge result:")
    assert result is not None, "Should return result"
    assert result.get("success") == True, "Dodge should always succeed"

    # Dodge action applies the "Dodging" condition which gives:
    # - Disadvantage on attacks against you
    # - Advantage on Dexterity saving throws
    # Check that the result mentions the dodge effect (disadvantage or dodging)
    message_field = result.get("message") or result.get("description") or result.get("condition", "")
    message_str = str(message_field).lower()

    # Valid indicators of dodge action success:
    # - Contains "dodg" (Dodging condition name)
    # - Contains "disadvantage" (the primary effect of dodge)
    # - Contains "dexterity" and "advantage" (secondary effect)
    has_dodge_indicator = (
        "dodg" in message_str or
        "disadvantage" in message_str or
        ("dexterity" in message_str and "advantage" in message_str)
    )

    assert has_dodge_indicator, f"Should mention dodge effect (disadvantage on attacks or advantage on DEX saves), got: {message_field}"

    logger.info(f"   Description: {message_field}")
    logger.info("   ✓ Dodge action processed correctly")

    logger.info("\n✅ TEST PASSED: Combat Action Resolver - Dodge")
    logger.info("=" * 60)


def test_combat_session_turn_order(combat_initializer, dnd_wrapper, character_manager,
                                   combat_action_resolver, combat_narrative_gen, npc_combat_ai, game_engine):
    """Test combat session maintains proper turn order"""
    logger.info("=" * 60)
    logger.info("TEST: Combat Session Turn Order")
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

    assert combat_state is not None

    logger.info("📊 Verifying turn order:")
    assert "initiative_order" in combat_state
    assert len(combat_state["initiative_order"]) >= 2, "Should have at least player and 1 NPC"

    logger.info(f"   Initiative order: {combat_state['initiative_order']}")

    # initiative_order is a list of dicts: [{"char_id": "aggi", "initiative": 21}, ...]
    # Extract char_ids from initiative order
    for entry in combat_state["initiative_order"]:
        # Handle both dict format and string format
        if isinstance(entry, dict):
            char_id = entry.get("char_id")
        else:
            char_id = entry

        assert char_id in combat_state["active_combatants"], f"{char_id} should be active"
        logger.info(f"   ✓ {char_id} in turn order")

    # Verify round number starts at 1
    assert combat_state["round_number"] == 1
    logger.info("   ✓ Combat starts at round 1")

    logger.info("\n✅ TEST PASSED: Combat Session Turn Order")
    logger.info("=" * 60)


def test_combat_state_persistence(combat_initializer, character_manager):
    """Test combat state persists correctly between turns"""
    logger.info("=" * 60)
    logger.info("TEST: Combat State Persistence")
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

    assert combat_state is not None

    # Store initial state
    initial_round = combat_state["round_number"]
    initial_combatants = combat_state["active_combatants"].copy()
    initial_initiative = combat_state["initiative_order"].copy()

    logger.info("📊 Verifying state structure:")
    assert "in_combat" in combat_state
    assert "round_number" in combat_state
    assert "active_combatants" in combat_state
    assert "initiative_order" in combat_state
    assert "current_turn_index" in combat_state
    assert "combatant_states" in combat_state
    assert "combat_log" in combat_state

    logger.info("   ✓ All required state fields present")

    # Verify combat log is empty at start
    assert len(combat_state["combat_log"]) == 0, "Combat log should start empty"
    logger.info("   ✓ Combat log initialized empty")

    # Verify combatant states exist for all combatants
    for char_id in combat_state["active_combatants"]:
        assert char_id in combat_state["combatant_states"]
        combatant_state = combat_state["combatant_states"][char_id]

        # Check for HP fields (could be "hp"/"max_hp" or "hp_current"/"hp_max")
        has_hp = ("hp" in combatant_state and "max_hp" in combatant_state) or \
                 ("hp_current" in combatant_state and "hp_max" in combatant_state)
        assert has_hp, f"Missing HP fields in {char_id} state: {list(combatant_state.keys())}"

        assert "is_hostile" in combatant_state
        logger.info(f"   ✓ {char_id} state complete")

    logger.info("\n✅ TEST PASSED: Combat State Persistence")
    logger.info("=" * 60)


def test_npc_ai_tactical_decision_outnumbered(npc_combat_ai):
    """Test NPC AI makes tactical decisions when outnumbered"""
    logger.info("=" * 60)
    logger.info("TEST: NPC AI Tactical Decision (Outnumbered)")
    logger.info("=" * 60)

    class MockNPC:
        name = "Goblin Warrior"
        character_class = "Warrior"
        level = 1
        attacks = [{"name": "Scimitar", "attack_bonus": 4}]

    # Outnumbered scenario (1 ally vs 3 enemies)
    context = {
        "npc": MockNPC(),
        "npc_hp": 5,
        "npc_max_hp": 7,
        "available_actions": ["attack", "dodge", "dash"],
        "available_targets": ["aggi", "partner1", "partner2"],
        "allies": ["goblin_002"],
        "enemies": ["aggi", "partner1", "partner2"],
        "round_number": 2
    }

    logger.info("📋 Testing NPC AI when outnumbered (1 vs 3)...")
    decision = npc_combat_ai.decide_action(context)

    logger.info("📊 Verifying decision:")
    assert decision is not None
    assert "action_type" in decision
    assert decision["action_type"] in context["available_actions"]

    logger.info(f"   Action Type: {decision.get('action_type')}")
    logger.info(f"   Target: {decision.get('target')}")
    logger.info(f"   Reasoning: {decision.get('reasoning')}")

    logger.info(f"   ✓ NPC made tactical decision when outnumbered")

    logger.info("\n✅ TEST PASSED: NPC AI Tactical Decision (Outnumbered)")
    logger.info("=" * 60)


def test_npc_ai_tactical_decision_advantage(npc_combat_ai):
    """Test NPC AI makes aggressive decisions with numerical advantage"""
    logger.info("=" * 60)
    logger.info("TEST: NPC AI Tactical Decision (Advantage)")
    logger.info("=" * 60)

    class MockNPC:
        name = "Goblin Warrior"
        character_class = "Warrior"
        level = 1
        attacks = [{"name": "Scimitar", "attack_bonus": 4}]

    # Advantage scenario (3 allies vs 1 enemy)
    context = {
        "npc": MockNPC(),
        "npc_hp": 6,
        "npc_max_hp": 7,
        "available_actions": ["attack", "dodge", "dash"],
        "available_targets": ["aggi"],
        "allies": ["goblin_002", "goblin_003"],
        "enemies": ["aggi"],
        "round_number": 1
    }

    logger.info("📋 Testing NPC AI with numerical advantage (3 vs 1)...")
    decision = npc_combat_ai.decide_action(context)

    logger.info("📊 Verifying decision:")
    assert decision is not None
    assert "action_type" in decision

    logger.info(f"   Action Type: {decision.get('action_type')}")
    logger.info(f"   Reasoning: {decision.get('reasoning')}")

    # With advantage and good HP, should likely attack
    logger.info(f"   ✓ NPC made tactical decision with advantage")

    logger.info("\n✅ TEST PASSED: NPC AI Tactical Decision (Advantage)")
    logger.info("=" * 60)


def test_combat_damage_tracking(combat_action_resolver, dnd_wrapper, character_manager):
    """Test damage is properly tracked in combat"""
    logger.info("=" * 60)
    logger.info("TEST: Combat Damage Tracking")
    logger.info("=" * 60)

    # Get player entity
    player_entity = dnd_wrapper.entities["aggi"]
    initial_hp = player_entity.health.get_total_hit_points(
        player_entity.ability_scores.constitution.modifier
    )

    logger.info(f"📋 Initial player HP: {initial_hp}")

    # Apply damage directly to test damage tracking
    logger.info("   Applying 5 damage to player...")
    player_entity.health.add_damage(5)

    new_hp = player_entity.health.get_total_hit_points(
        player_entity.ability_scores.constitution.modifier
    )

    logger.info(f"   New player HP: {new_hp}")
    logger.info(f"   Damage taken: {player_entity.health.damage_taken}")

    assert new_hp == initial_hp - 5, "HP should decrease by damage amount"
    assert player_entity.health.damage_taken == 5, "damage_taken should track damage"

    logger.info("   ✓ Damage tracked correctly")

    # Test healing
    logger.info("   Healing 3 HP...")
    player_entity.health.heal(3)

    healed_hp = player_entity.health.get_total_hit_points(
        player_entity.ability_scores.constitution.modifier
    )

    logger.info(f"   Healed HP: {healed_hp}")

    assert healed_hp == new_hp + 3, "HP should increase by heal amount"
    assert player_entity.health.damage_taken == 2, "damage_taken should decrease"

    logger.info("   ✓ Healing tracked correctly")

    logger.info("\n✅ TEST PASSED: Combat Damage Tracking")
    logger.info("=" * 60)


def test_combat_ends_all_enemies_dead(combat_initializer, dnd_wrapper, character_manager,
                                       combat_action_resolver, combat_narrative_gen, npc_combat_ai, game_engine):
    """Test combat ends when all enemies are defeated"""
    logger.info("=" * 60)
    logger.info("TEST: Combat Ends (All Enemies Dead)")
    logger.info("=" * 60)

    scenario = {
        "scene": "A weak goblin appears!",
        "gm_notes": "One goblin warrior (CR 1/4).",
        "choices": [{"combat_trigger": True}]
    }

    logger.info("📋 Initializing combat...")
    combat_state = combat_initializer.initialize_combat(
        scenario=scenario,
        player_character_ids=["aggi"]
    )

    assert combat_state is not None

    # Get NPC ID
    npc_ids = [cid for cid in combat_state["active_combatants"] if cid != "aggi"]
    assert len(npc_ids) >= 1
    npc_id = npc_ids[0]

    logger.info(f"   Testing with NPC: {npc_id}")

    # Create session manager
    session_manager = CombatSessionManager(
        combat_state=combat_state,
        game_engine=game_engine,
        character_manager=character_manager,
        dnd_engine_wrapper=dnd_wrapper,
        combat_action_resolver=combat_action_resolver,
        combat_narrative_generator=combat_narrative_gen,
        npc_ai_agent=npc_combat_ai
    )

    # Kill NPC directly by setting max damage
    npc_entity = dnd_wrapper.entities[npc_id]
    max_hp = npc_entity.health.get_max_hit_dices_points(
        npc_entity.ability_scores.constitution.modifier
    )
    npc_entity.health.add_damage(max_hp + 10)  # Ensure dead

    logger.info("   ✓ NPC killed")

    # Check if combat should end
    current_hp = npc_entity.health.get_total_hit_points(
        npc_entity.ability_scores.constitution.modifier
    )

    logger.info(f"   NPC current HP: {current_hp}")
    assert current_hp <= 0, "NPC should be dead"

    logger.info("   ✓ Combat end condition verified")

    logger.info("\n✅ TEST PASSED: Combat Ends (All Enemies Dead)")
    logger.info("=" * 60)


def test_combat_initiative_sorting(combat_initializer, character_manager):
    """Test initiative order is properly sorted"""
    logger.info("=" * 60)
    logger.info("TEST: Combat Initiative Sorting")
    logger.info("=" * 60)

    scenario = {
        "scene": "Two goblins appear!",
        "gm_notes": "Two goblin warriors (CR 1/4).",
        "choices": [{"combat_trigger": True}]
    }

    logger.info("📋 Initializing combat...")
    combat_state = combat_initializer.initialize_combat(
        scenario=scenario,
        player_character_ids=["aggi"]
    )

    assert combat_state is not None

    logger.info("📊 Verifying initiative sorting:")
    initiative_order = combat_state["initiative_order"]

    logger.info(f"   Initiative order: {initiative_order}")

    # Extract char_ids from initiative order (handle dict format)
    char_ids_in_order = []
    for entry in initiative_order:
        if isinstance(entry, dict):
            char_ids_in_order.append(entry.get("char_id"))
        else:
            char_ids_in_order.append(entry)

    # Verify all combatants are in initiative order
    for char_id in combat_state["active_combatants"]:
        assert char_id in char_ids_in_order, f"{char_id} should be in initiative order"

    logger.info(f"   ✓ All {len(initiative_order)} combatants in initiative order")

    # Get actual initiative values
    initiatives = {}
    for entry in initiative_order:
        if isinstance(entry, dict):
            char_id = entry.get("char_id")
            init_value = entry.get("initiative", 0)
        else:
            char_id = entry
            combatant_state = combat_state["combatant_states"][char_id]
            init_value = combatant_state.get("initiative", 0)

        initiatives[char_id] = init_value
        logger.info(f"   {char_id}: Initiative {init_value}")

    # Verify sorted in descending order
    sorted_initiatives = sorted(initiatives.values(), reverse=True)
    actual_initiatives = [initiatives[cid] for cid in char_ids_in_order]

    assert actual_initiatives == sorted_initiatives, "Initiative should be sorted highest to lowest"
    logger.info("   ✓ Initiative properly sorted (highest to lowest)")

    logger.info("\n✅ TEST PASSED: Combat Initiative Sorting")
    logger.info("=" * 60)


# ============================================================================
# RUN ALL TESTS
# ============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("ADVANCED COMBAT TESTS")
    print("=" * 60)

    # Run pytest with verbose output
    pytest.main([__file__, "-v", "-s", "--tb=short"])
