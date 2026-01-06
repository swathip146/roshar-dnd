"""
Test NPC Generation and dnd_engine Synchronization

Verifies that NPCs are correctly generated and synced to dnd_engine entities
with proper HP values.
"""

import pytest
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file BEFORE importing other modules
from dotenv import load_dotenv
env_path = project_root / '.env'
if env_path.exists():
    load_dotenv(env_path)
else:
    print(f"⚠️ Warning: .env file not found at {env_path}")

from components.combat.combat_initializer import CombatInitializer
from components.combat.npc_stat_generator import NPCStatGenerator
from components.character_manager import CharacterManager
from components.game_engine import GameEngine
from components.dnd_engine_wrapper import DnDEngineWrapper
from config.llm_config import LLMConfigManager, create_gemini_config
from config.logging_config import get_logger

logger = get_logger(__name__)


class TestNPCDndEngineSync:
    """Test suite for NPC generation and dnd_engine synchronization"""

    @pytest.fixture
    def game_components(self):
        """Create game components for testing"""
        logger.info("=" * 60)
        logger.info("🧪 TEST: Setting up game components")
        logger.info("=" * 60)

        # Create character manager
        char_manager = CharacterManager()

        # Create game engine (no character_manager parameter needed)
        game_engine = GameEngine()

        # Create dnd_engine wrapper
        dnd_wrapper = DnDEngineWrapper(game_engine, char_manager)

        logger.info("✅ Game components created")
        return {
            "char_manager": char_manager,
            "game_engine": game_engine,
            "dnd_wrapper": dnd_wrapper
        }

    @pytest.fixture
    def combat_initializer(self, game_components):
        """Create combat initializer with all dependencies"""
        logger.info("🔧 Creating combat initializer")

        char_manager = game_components["char_manager"]
        game_engine = game_components["game_engine"]
        dnd_wrapper = game_components["dnd_wrapper"]

        # Create LLM config manager
        config = create_gemini_config()
        llm_manager = LLMConfigManager(config)

        # Create NPC stat generator
        from components.combat.npc_stat_generator import NPC_STATS_RESPONSE_SCHEMA
        npc_generator_llm = llm_manager.create_generator(
            agent_name="npc_generator",
            response_schema=NPC_STATS_RESPONSE_SCHEMA
        )
        npc_stat_generator = NPCStatGenerator(
            llm=npc_generator_llm,
            document_store=None  # No RAG for this test
        )

        # Create NPC registry (empty for this test)
        from core.npc_stat_loader import NPCStatLoader
        npc_registry = NPCStatLoader(npc_directory="data/players/")

        # Create combat initializer
        combat_init_llm = llm_manager.create_generator(agent_name="combat_init")
        initializer = CombatInitializer(
            game_engine=game_engine,
            character_manager=char_manager,
            dnd_engine_wrapper=dnd_wrapper,
            npc_stat_generator=npc_stat_generator,
            npc_registry=npc_registry,
            llm=combat_init_llm
        )

        logger.info("✅ Combat initializer created")
        return initializer

    @pytest.fixture
    def player_character(self, game_components):
        """Create a test player character"""
        logger.info("👤 Creating test player character")

        char_manager = game_components["char_manager"]

        # Create player character data
        player_data = {
            "character_id": "test_player",  # Add character_id to the data
            "name": "Test Hero",
            "level": 1,
            "character_class": "Fighter",
            "race": "Human",
            "background": "Soldier",
            "ability_scores": {
                "strength": 16,
                "dexterity": 14,
                "constitution": 15,
                "intelligence": 10,
                "wisdom": 12,
                "charisma": 8
            },
            "hit_points": {
                "current": 12,
                "maximum": 12,
                "temporary": 0
            },
            "armor_class": 16,
            "proficiency_bonus": 2,
            "speed": 30,
            "skills": {
                "athletics": True,
                "intimidation": True
            },
            "saving_throw_proficiencies": ["strength", "constitution"],
            "expertise_skills": []
        }

        # add_character takes just the data dict and returns char_id
        char_id = char_manager.add_character(player_data)
        logger.info(f"✅ Created player: {player_data['name']} (HP: {player_data['hit_points']})")

        return char_id

    def test_npc_generation_basic(self, combat_initializer, player_character):
        """Test basic NPC generation without dnd_engine sync"""
        logger.info("")
        logger.info("=" * 60)
        logger.info("🧪 TEST 1: Basic NPC Generation")
        logger.info("=" * 60)

        # Create simple enemy description
        enemies = [{
            "name": "Goblin Warrior",
            "description": "A small, green-skinned humanoid with a crude sword",
            "count": 1,
            "estimated_cr": 0.25,
            "role": "combatant",
            "keywords": ["goblin", "warrior", "melee"],
            "is_predefined": False
        }]

        # Generate NPCs
        logger.info("📋 Generating NPCs...")
        generated_ids = combat_initializer._generate_undefined_npcs(enemies, [player_character])

        logger.info(f"✅ Generated {len(generated_ids)} NPCs")

        # Verify NPCs were created
        assert len(generated_ids) == 1, f"Expected 1 NPC, got {len(generated_ids)}"

        # Check NPC in character manager
        npc_id = generated_ids[0]
        npc = combat_initializer.character_manager.characters.get(npc_id)

        assert npc is not None, f"NPC {npc_id} not found in CharacterManager"

        logger.info(f"📊 NPC Stats in CharacterManager:")
        logger.info(f"   Name: {npc.name}")
        logger.info(f"   Level: {npc.level}")
        logger.info(f"   HP: {npc.hit_points}")
        logger.info(f"   AC: {npc.armor_class}")
        logger.info(f"   Ability Scores: {npc.ability_scores}")

        # Verify HP is not zero
        assert npc.hit_points.get("maximum", 0) > 0, "NPC max HP is 0!"
        assert npc.hit_points.get("current", 0) > 0, "NPC current HP is 0!"

        logger.info("✅ TEST 1 PASSED: NPC generated with valid HP")

    def test_npc_dnd_engine_sync(self, combat_initializer, player_character, game_components):
        """Test NPC synchronization to dnd_engine"""
        logger.info("")
        logger.info("=" * 60)
        logger.info("🧪 TEST 2: NPC dnd_engine Synchronization")
        logger.info("=" * 60)

        dnd_wrapper = game_components["dnd_wrapper"]
        char_manager = game_components["char_manager"]

        # Generate NPCs
        enemies = [{
            "name": "Orc Raider",
            "description": "A muscular, gray-skinned humanoid with a greataxe",
            "count": 2,
            "estimated_cr": 0.5,
            "role": "combatant",
            "keywords": ["orc", "raider", "melee"],
            "is_predefined": False
        }]

        logger.info("📋 Generating NPCs...")
        generated_ids = combat_initializer._generate_undefined_npcs(enemies, [player_character])

        logger.info(f"✅ Generated {len(generated_ids)} NPCs")

        # Sync to dnd_engine
        logger.info("🔄 Syncing to dnd_engine...")
        dnd_wrapper._sync_characters_to_entities()

        logger.info("✅ Sync complete")

        # Verify each NPC in dnd_engine
        for npc_id in generated_ids:
            logger.info("")
            logger.info(f"🔍 Checking NPC: {npc_id}")

            # Check CharacterManager
            npc = char_manager.characters.get(npc_id)
            assert npc is not None, f"NPC {npc_id} not in CharacterManager"

            char_hp = npc.hit_points
            logger.info(f"   CharacterManager HP: {char_hp}")

            # Check dnd_engine entity
            entity = dnd_wrapper.entities.get(npc_id)
            assert entity is not None, f"NPC {npc_id} not in dnd_engine!"

            # Get HP values from entity
            con_mod = entity.ability_scores.constitution.modifier
            entity_max_hp = entity.health.get_max_hit_dices_points(con_mod)
            entity_damage = entity.health.damage_taken
            entity_total_hp = entity.health.get_total_hit_points(con_mod)

            logger.info(f"   dnd_engine Entity:")
            logger.info(f"      Constitution modifier: {con_mod}")
            logger.info(f"      Max HP (from hit dice): {entity_max_hp}")
            logger.info(f"      Damage taken: {entity_damage}")
            logger.info(f"      Total HP (max - damage): {entity_total_hp}")

            # CRITICAL ASSERTIONS
            assert entity_max_hp > 0, f"Entity max HP is 0 for {npc_id}!"
            assert entity_total_hp > 0, f"Entity total HP is 0 for {npc_id}!"
            assert entity_total_hp <= entity_max_hp, f"Total HP exceeds max HP for {npc_id}!"

            # Check HP matches expectations
            expected_current = char_hp.get("current", 10)
            expected_max = char_hp.get("maximum", 10)

            # Total HP should be positive if current HP is positive
            if expected_current > 0:
                assert entity_total_hp > 0, \
                    f"Entity has 0 HP but CharacterManager shows {expected_current} HP!"

            logger.info(f"   ✅ {npc_id} properly synced to dnd_engine")

        logger.info("")
        logger.info("✅ TEST 2 PASSED: All NPCs correctly synced with positive HP")

    def test_combat_initialization_full(self, combat_initializer, player_character, game_components):
        """Test full combat initialization with player and NPCs"""
        logger.info("")
        logger.info("=" * 60)
        logger.info("🧪 TEST 3: Full Combat Initialization")
        logger.info("=" * 60)

        dnd_wrapper = game_components["dnd_wrapper"]

        # Create combat scenario
        scenario = {
            "scene": "You are ambushed by bandits on the road!",
            "choices": [],
            "gm_notes": "Combat encounter: 2 Bandit Thugs (CR 1/8 each)"
        }

        # Initialize combat
        logger.info("⚔️ Initializing combat...")
        combat_state = combat_initializer.initialize_combat(
            scenario=scenario,
            player_character_ids=[player_character]
        )

        logger.info("✅ Combat initialized")

        # Verify combat state
        assert combat_state is not None, "Combat state is None!"
        assert "active_combatants" in combat_state, "No active_combatants in combat state!"
        assert "initiative_order" in combat_state, "No initiative_order in combat state!"

        all_combatants = combat_state["active_combatants"]
        logger.info(f"📋 Active combatants: {all_combatants}")

        assert len(all_combatants) > 1, "No NPCs in combat!"

        # Check each combatant
        logger.info("")
        logger.info("🔍 Checking all combatants:")

        for combatant_id in all_combatants:
            logger.info(f"   {combatant_id}:")

            # Check combat state
            combatant_state = combat_state["combatant_states"][combatant_id]
            state_hp_current = combatant_state["hp_current"]
            state_hp_max = combatant_state["hp_max"]

            logger.info(f"      Combat State HP: {state_hp_current}/{state_hp_max}")

            # Check dnd_engine entity
            entity = dnd_wrapper.entities.get(combatant_id)
            assert entity is not None, f"No entity for {combatant_id}!"

            con_mod = entity.ability_scores.constitution.modifier
            entity_total_hp = entity.health.get_total_hit_points(con_mod)
            entity_max_hp = entity.health.get_max_hit_dices_points(con_mod)

            logger.info(f"      dnd_engine HP: {entity_total_hp}/{entity_max_hp}")

            # CRITICAL ASSERTIONS
            assert state_hp_current > 0, f"Combat state HP is 0 for {combatant_id}!"
            assert entity_total_hp > 0, f"Entity HP is 0 for {combatant_id}!"

            logger.info(f"      ✅ {combatant_id} has valid HP")

        logger.info("")
        logger.info("✅ TEST 3 PASSED: Full combat initialization successful")

    def test_npc_not_dead_at_start(self, combat_initializer, player_character, game_components):
        """Test that NPCs are not marked as dead at combat start"""
        logger.info("")
        logger.info("=" * 60)
        logger.info("🧪 TEST 4: NPCs Not Dead At Start")
        logger.info("=" * 60)

        dnd_wrapper = game_components["dnd_wrapper"]

        # Generate NPCs
        enemies = [{
            "name": "Skeleton Warrior",
            "description": "An animated skeleton wielding a rusty sword",
            "count": 3,
            "estimated_cr": 0.25,
            "role": "combatant",
            "keywords": ["skeleton", "undead", "melee"],
            "is_predefined": False
        }]

        generated_ids = combat_initializer._generate_undefined_npcs(enemies, [player_character])
        dnd_wrapper._sync_characters_to_entities()

        logger.info(f"📋 Generated {len(generated_ids)} NPCs")

        # Check if any are dead
        dead_count = 0
        alive_count = 0

        for npc_id in generated_ids:
            entity = dnd_wrapper.entities[npc_id]
            con_mod = entity.ability_scores.constitution.modifier
            total_hp = entity.health.get_total_hit_points(con_mod)

            is_dead = total_hp <= 0

            logger.info(f"   {npc_id}: HP={total_hp}, Dead={is_dead}")

            if is_dead:
                dead_count += 1
            else:
                alive_count += 1

        logger.info("")
        logger.info(f"📊 Summary: {alive_count} alive, {dead_count} dead")

        # CRITICAL ASSERTION
        assert dead_count == 0, f"{dead_count} NPCs are dead at combat start!"
        assert alive_count == len(generated_ids), "Not all NPCs are alive!"

        logger.info("✅ TEST 4 PASSED: All NPCs alive at combat start")


def run_tests():
    """Run all tests with detailed logging"""
    logger.info("=" * 60)
    logger.info("🧪 NPC DND_ENGINE SYNC TEST SUITE")
    logger.info("=" * 60)

    # Run pytest with verbose output
    pytest_args = [
        __file__,
        "-v",  # Verbose
        "-s",  # Show print statements
        "--tb=short",  # Short traceback
        "--log-cli-level=INFO"  # Show logs
    ]

    exit_code = pytest.main(pytest_args)

    logger.info("")
    logger.info("=" * 60)
    if exit_code == 0:
        logger.info("✅ ALL TESTS PASSED")
    else:
        logger.info("❌ SOME TESTS FAILED")
    logger.info("=" * 60)

    return exit_code


if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)
