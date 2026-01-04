"""
Unit tests for CombatInitializer - Phase 2 of Combat Engine

Tests combat initialization including:
- Combat trigger detection
- Enemy parsing from scenarios
- Predefined NPC loading from registry
- NPC generation for undefined enemies
- Initiative rolling
- Combat state creation
"""

import pytest
import json
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, List, Any

from components.combat.combat_initializer import CombatInitializer, create_combat_initializer
from components.character_manager import CharacterManager
from components.combat.npc_stat_generator import NPCStatGenerator
from core.npc_stat_loader import NPCStatLoader
from config.logging_config import get_logger

logger = get_logger(__name__)


class TestCombatTriggerDetection:
    """Test suite for combat trigger detection"""

    @pytest.fixture
    def mock_components(self):
        """Create mock components for testing"""
        return {
            'game_engine': Mock(),
            'character_manager': Mock(),
            'dnd_engine_wrapper': Mock(),
            'npc_stat_generator': Mock(),
            'npc_registry': Mock(),
            'llm': Mock()
        }

    @pytest.fixture
    def combat_initializer(self, mock_components):
        """Create CombatInitializer with mock components"""
        return CombatInitializer(**mock_components)

    def test_should_trigger_combat_with_combat_choice(self, combat_initializer):
        """Test combat trigger detection when choice has combat_trigger=True"""
        scenario = {
            "scene": "Goblins attack!",
            "choices": [
                {"id": "c1", "title": "Talk to them", "combat_trigger": False},
                {"id": "c2", "title": "Attack **Combat**", "combat_trigger": True}
            ]
        }

        assert combat_initializer._should_trigger_combat(scenario) == True

    def test_should_trigger_combat_no_trigger(self, combat_initializer):
        """Test that combat doesn't trigger when no combat_trigger is True"""
        scenario = {
            "scene": "You see a merchant.",
            "choices": [
                {"id": "c1", "title": "Talk to merchant", "combat_trigger": False},
                {"id": "c2", "title": "Examine goods", "combat_trigger": False}
            ]
        }

        assert combat_initializer._should_trigger_combat(scenario) == False

    def test_should_trigger_combat_keyword_fallback(self, combat_initializer):
        """Test combat detection via keyword fallback when no explicit trigger"""
        scenario = {
            "scene": "Two hostile bandits attack with drawn weapons!",
            "gm_notes": "Combat encounter with 2 bandits",
            "choices": []
        }

        assert combat_initializer._should_trigger_combat(scenario) == True

    def test_should_trigger_combat_empty_scenario(self, combat_initializer):
        """Test handling of empty scenario"""
        scenario = {}

        assert combat_initializer._should_trigger_combat(scenario) == False


class TestEnemyParsing:
    """Test suite for enemy parsing from scenarios"""

    @pytest.fixture
    def combat_initializer_with_llm(self):
        """Create CombatInitializer with mock LLM"""
        mock_llm = Mock()
        return CombatInitializer(
            game_engine=Mock(),
            character_manager=Mock(),
            dnd_engine_wrapper=Mock(),
            npc_stat_generator=Mock(),
            npc_registry=Mock(),
            llm=mock_llm
        ), mock_llm

    def test_parse_enemies_with_goblins(self, combat_initializer_with_llm):
        """Test parsing goblins from scenario"""
        combat_init, mock_llm = combat_initializer_with_llm

        # Mock LLM response
        mock_response = Mock()
        mock_response.content = json.dumps([
            {
                "name": "Goblin Warrior",
                "description": "small goblin with rusty scimitar",
                "count": 2,
                "estimated_cr": 0.25,
                "role": "combatant",
                "keywords": ["goblin", "warrior"],
                "is_predefined": False
            }
        ])
        mock_llm.run.return_value = {'replies': [mock_response]}

        scenario = {
            "scene": "Two goblins leap out from behind rocks!",
            "gm_notes": "2 goblin warriors (CR 1/4 each)"
        }

        enemies = combat_init._parse_enemies_from_scenario(scenario)

        assert len(enemies) == 1
        assert enemies[0]['name'] == "Goblin Warrior"
        assert enemies[0]['count'] == 2
        assert enemies[0]['estimated_cr'] == 0.25
        assert enemies[0]['is_predefined'] == False

    def test_parse_enemies_with_predefined_npc(self, combat_initializer_with_llm):
        """Test parsing scenario with predefined NPC (Herald)"""
        combat_init, mock_llm = combat_initializer_with_llm

        # Mock LLM response
        mock_response = Mock()
        mock_response.content = json.dumps([
            {
                "name": "Kalak",
                "description": "Herald of the Oathpact",
                "count": 1,
                "estimated_cr": 10.0,
                "role": "boss",
                "keywords": ["kalak", "herald"],
                "is_predefined": True
            }
        ])
        mock_llm.run.return_value = {'replies': [mock_response]}

        scenario = {
            "scene": "The Herald Kalak appears before you!",
            "gm_notes": "Kalak the Herald (predefined NPC)"
        }

        enemies = combat_init._parse_enemies_from_scenario(scenario)

        assert len(enemies) == 1
        assert enemies[0]['name'] == "Kalak"
        assert enemies[0]['is_predefined'] == True

    def test_parse_enemies_handles_markdown_code_blocks(self, combat_initializer_with_llm):
        """Test that parser handles markdown code blocks from LLM"""
        combat_init, mock_llm = combat_initializer_with_llm

        # Mock LLM response with markdown
        mock_response = Mock()
        mock_response.content = """```json
[
    {
        "name": "Skeleton",
        "description": "undead skeleton",
        "count": 3,
        "estimated_cr": 0.25,
        "role": "minion",
        "keywords": ["skeleton", "undead"],
        "is_predefined": false
    }
]
```"""
        mock_llm.run.return_value = {'replies': [mock_response]}

        scenario = {"scene": "Skeletons rise!", "gm_notes": "3 skeletons"}

        enemies = combat_init._parse_enemies_from_scenario(scenario)

        assert len(enemies) == 1
        assert enemies[0]['name'] == "Skeleton"

    def test_parse_enemies_handles_invalid_json(self, combat_initializer_with_llm):
        """Test graceful handling of invalid JSON from LLM"""
        combat_init, mock_llm = combat_initializer_with_llm

        # Mock LLM response with invalid JSON
        mock_response = Mock()
        mock_response.content = "This is not valid JSON!"
        mock_llm.run.return_value = {'replies': [mock_response]}

        scenario = {"scene": "Enemies appear", "gm_notes": ""}

        enemies = combat_init._parse_enemies_from_scenario(scenario)

        assert enemies == []  # Should return empty list on error


class TestPredefinedNPCLoading:
    """Test suite for loading predefined NPCs from registry"""

    @pytest.fixture
    def combat_init_with_registry(self):
        """Create CombatInitializer with mock NPC registry and CharacterManager"""
        mock_registry = Mock()
        mock_char_manager = Mock()

        combat_init = CombatInitializer(
            game_engine=Mock(),
            character_manager=mock_char_manager,
            dnd_engine_wrapper=Mock(),
            npc_stat_generator=Mock(),
            npc_registry=mock_registry,
            llm=Mock()
        )

        return combat_init, mock_registry, mock_char_manager

    def test_load_predefined_npc_kalak(self, combat_init_with_registry):
        """Test loading Kalak from NPC registry"""
        combat_init, mock_registry, mock_char_manager = combat_init_with_registry

        # Mock registry returns Kalak stats
        kalak_stats = {
            "name": "Kalak",
            "level": 20,
            "hit_points": {"current": 400, "maximum": 400, "temporary": 0},
            "armor_class": 22
        }
        mock_registry.get_npc_by_name.return_value = kalak_stats
        mock_char_manager.add_npc.return_value = "kalak_herald"

        enemies = [
            {
                "name": "Kalak",
                "is_predefined": True,
                "count": 1
            }
        ]

        predefined_ids = combat_init._load_predefined_npcs(enemies)

        assert len(predefined_ids) == 1
        assert predefined_ids[0] == "kalak_herald"
        assert enemies[0]['processed'] == True
        mock_registry.get_npc_by_name.assert_called_once_with("Kalak")
        mock_char_manager.add_npc.assert_called_once_with(kalak_stats)

    def test_load_predefined_npc_not_found(self, combat_init_with_registry):
        """Test fallback when predefined NPC not in registry"""
        combat_init, mock_registry, mock_char_manager = combat_init_with_registry

        # Mock registry returns None (NPC not found)
        mock_registry.get_npc_by_name.return_value = None

        enemies = [
            {
                "name": "Unknown Hero",
                "is_predefined": True,
                "count": 1
            }
        ]

        predefined_ids = combat_init._load_predefined_npcs(enemies)

        assert len(predefined_ids) == 0
        assert enemies[0]['is_predefined'] == False  # Fallback flag set

    def test_load_predefined_npc_no_registry(self):
        """Test handling when no NPC registry available"""
        combat_init = CombatInitializer(
            game_engine=Mock(),
            character_manager=Mock(),
            dnd_engine_wrapper=Mock(),
            npc_stat_generator=Mock(),
            npc_registry=None,  # No registry
            llm=Mock()
        )

        enemies = [{"name": "Kalak", "is_predefined": True}]

        predefined_ids = combat_init._load_predefined_npcs(enemies)

        assert predefined_ids == []


class TestNPCGeneration:
    """Test suite for NPC generation"""

    @pytest.fixture
    def combat_init_with_generator(self):
        """Create CombatInitializer with mock NPC generator"""
        mock_generator = Mock()
        mock_char_manager = Mock()

        combat_init = CombatInitializer(
            game_engine=Mock(),
            character_manager=mock_char_manager,
            dnd_engine_wrapper=Mock(),
            npc_stat_generator=mock_generator,
            npc_registry=Mock(),
            llm=Mock()
        )

        return combat_init, mock_generator, mock_char_manager

    def test_generate_single_npc(self, combat_init_with_generator):
        """Test generating a single NPC"""
        combat_init, mock_generator, mock_char_manager = combat_init_with_generator

        # Mock generator returns goblin stats
        goblin_stats = {
            "name": "Goblin",
            "level": 1,
            "hit_points": {"current": 7, "maximum": 7, "temporary": 0}
        }
        mock_generator.generate_npc_stats.return_value = goblin_stats
        mock_char_manager.add_npc.return_value = "goblin_001"
        mock_char_manager.characters.get.return_value = Mock(level=1)

        enemies = [
            {
                "name": "Goblin",
                "description": "small goblin",
                "count": 1,
                "estimated_cr": 0.25,
                "role": "combatant",
                "processed": False
            }
        ]

        generated_ids = combat_init._generate_undefined_npcs(enemies, ["aggi"])

        assert len(generated_ids) == 1
        assert generated_ids[0] == "goblin_001"
        mock_generator.generate_npc_stats.assert_called_once()

    def test_generate_multiple_npc_instances(self, combat_init_with_generator):
        """Test generating multiple instances of same NPC"""
        combat_init, mock_generator, mock_char_manager = combat_init_with_generator

        # Mock generator
        goblin_stats = {"name": "Goblin", "level": 1}
        mock_generator.generate_npc_stats.return_value = goblin_stats
        mock_char_manager.add_npc.side_effect = ["goblin_001", "goblin_002", "goblin_003"]
        mock_char_manager.characters.get.return_value = Mock(level=1)

        enemies = [
            {
                "name": "Goblin",
                "description": "small goblin",
                "count": 3,  # 3 goblins
                "estimated_cr": 0.25,
                "role": "combatant"
            }
        ]

        generated_ids = combat_init._generate_undefined_npcs(enemies, ["aggi"])

        assert len(generated_ids) == 3
        assert mock_char_manager.add_npc.call_count == 3

    def test_generate_npc_skips_processed(self, combat_init_with_generator):
        """Test that generation skips already processed enemies"""
        combat_init, mock_generator, mock_char_manager = combat_init_with_generator

        # Add mock character with level attribute for _get_party_level
        mock_char = Mock()
        mock_char.level = 1
        mock_char_manager.characters.get.return_value = mock_char

        enemies = [
            {
                "name": "Kalak",
                "processed": True  # Already loaded as predefined
            }
        ]

        generated_ids = combat_init._generate_undefined_npcs(enemies, ["aggi"])

        assert generated_ids == []
        mock_generator.generate_npc_stats.assert_not_called()


class TestInitiativeRolling:
    """Test suite for initiative rolling"""

    @pytest.fixture
    def combat_init_with_chars(self):
        """Create CombatInitializer with mock character manager"""
        mock_char_manager = Mock()

        # Create mock characters with DEX scores
        aggi = Mock()
        aggi.ability_scores = {"dexterity": 14}  # +2 mod

        goblin = Mock()
        goblin.ability_scores = {"dexterity": 12}  # +1 mod

        mock_char_manager.characters.get.side_effect = lambda cid: {
            "aggi": aggi,
            "goblin_001": goblin
        }.get(cid)

        combat_init = CombatInitializer(
            game_engine=Mock(),
            character_manager=mock_char_manager,
            dnd_engine_wrapper=None,  # No dnd_wrapper - use fallback
            npc_stat_generator=Mock(),
            npc_registry=Mock(),
            llm=Mock()
        )

        return combat_init

    def test_roll_initiative_fallback(self, combat_init_with_chars):
        """Test initiative rolling with fallback method"""
        combatant_ids = ["aggi", "goblin_001"]

        with patch('random.randint') as mock_random:
            # Mock d20 rolls
            mock_random.side_effect = [15, 12]  # aggi rolls 15, goblin rolls 12

            initiative_order = combat_init_with_chars._roll_initiative_fallback(combatant_ids)

        assert len(initiative_order) == 2
        # aggi: 15 + 2 (DEX) = 17
        # goblin: 12 + 1 (DEX) = 13
        assert initiative_order[0]['char_id'] == "aggi"
        assert initiative_order[0]['initiative'] == 17
        assert initiative_order[1]['char_id'] == "goblin_001"
        assert initiative_order[1]['initiative'] == 13

    def test_roll_initiative_sorted_descending(self, combat_init_with_chars):
        """Test that initiative is sorted high to low"""
        combatant_ids = ["char1", "char2", "char3"]

        with patch('random.randint', return_value=10):
            initiative_order = combat_init_with_chars._roll_initiative_fallback(combatant_ids)

        # Verify sorted descending
        for i in range(len(initiative_order) - 1):
            assert initiative_order[i]['initiative'] >= initiative_order[i+1]['initiative']


class TestCombatantStates:
    """Test suite for combatant state initialization"""

    @pytest.fixture
    def combat_init_with_chars(self):
        """Create CombatInitializer with character data"""
        mock_char_manager = Mock()

        # Player character
        aggi = Mock()
        aggi.hit_points = {"current": 25, "maximum": 25, "temporary": 0}

        # NPC
        goblin = Mock()
        goblin.hit_points = {"current": 7, "maximum": 7, "temporary": 0}

        mock_char_manager.characters.get.side_effect = lambda cid: {
            "aggi": aggi,
            "goblin_001": goblin
        }.get(cid)
        mock_char_manager.get_npcs.return_value = []

        combat_init = CombatInitializer(
            game_engine=Mock(),
            character_manager=mock_char_manager,
            dnd_engine_wrapper=Mock(),
            npc_stat_generator=Mock(),
            npc_registry=Mock(),
            llm=Mock()
        )

        return combat_init

    def test_initialize_combatant_states(self, combat_init_with_chars):
        """Test creating combatant states"""
        combatant_ids = ["aggi", "goblin_001"]

        states = combat_init_with_chars._initialize_combatant_states(combatant_ids)

        assert len(states) == 2

        # Check player state
        assert "aggi" in states
        assert states["aggi"]["hp_current"] == 25
        assert states["aggi"]["hp_max"] == 25
        assert states["aggi"]["actions_remaining"] == 1
        assert states["aggi"]["is_hostile"] == False  # Player not hostile

        # Check NPC state
        assert "goblin_001" in states
        assert states["goblin_001"]["hp_current"] == 7
        assert states["goblin_001"]["is_hostile"] == True  # NPC is hostile

    def test_initialize_combatant_states_handles_missing_char(self, combat_init_with_chars):
        """Test handling of missing character"""
        combatant_ids = ["aggi", "missing_char"]

        states = combat_init_with_chars._initialize_combatant_states(combatant_ids)

        # Should only have aggi, skip missing_char
        assert len(states) == 1
        assert "aggi" in states
        assert "missing_char" not in states


class TestFullCombatInitialization:
    """Integration tests for full combat initialization"""

    @pytest.fixture
    def full_combat_init(self):
        """Create fully configured CombatInitializer for integration tests"""
        # Create real CharacterManager
        char_manager = CharacterManager()

        # Add player character
        aggi_data = {
            "character_id": "aggi",
            "name": "Aggi",
            "race": "Human",
            "character_class": "Fighter",
            "level": 1,
            "ability_scores": {
                "strength": 16, "dexterity": 14, "constitution": 14,
                "intelligence": 10, "wisdom": 12, "charisma": 10
            },
            "hit_points": {"current": 12, "maximum": 12, "temporary": 0},
            "armor_class": 16,
            "proficiency_bonus": 2,
            "skills": {}
        }
        char_manager.add_character(aggi_data)

        # Mock other components
        mock_npc_generator = Mock()
        mock_npc_generator.generate_npc_stats.return_value = {
            "name": "Goblin",
            "level": 1,
            "character_class": "Warrior",
            "race": "Goblin",
            "ability_scores": {
                "strength": 8, "dexterity": 14, "constitution": 10,
                "intelligence": 10, "wisdom": 8, "charisma": 8
            },
            "hit_points": {"current": 7, "maximum": 7, "temporary": 0},
            "armor_class": 15,
            "proficiency_bonus": 2,
            "skills": {},
            "attacks": [],
            "special_abilities": [],
            "challenge_rating": 0.25
        }

        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = json.dumps([
            {
                "name": "Goblin Warrior",
                "description": "small goblin with scimitar",
                "count": 2,
                "estimated_cr": 0.25,
                "role": "combatant",
                "keywords": ["goblin"],
                "is_predefined": False
            }
        ])
        mock_llm.run.return_value = {'replies': [mock_response]}

        combat_init = CombatInitializer(
            game_engine=Mock(),
            character_manager=char_manager,
            dnd_engine_wrapper=None,  # Use fallback initiative
            npc_stat_generator=mock_npc_generator,
            npc_registry=None,
            llm=mock_llm
        )

        return combat_init

    def test_full_combat_initialization(self, full_combat_init):
        """Test complete combat initialization flow"""
        scenario = {
            "scene": "Two goblins attack!",
            "gm_notes": "2 goblin warriors",
            "choices": [
                {"id": "c1", "title": "Fight **Combat**", "combat_trigger": True}
            ]
        }

        with patch('random.randint', return_value=10):
            combat_state = full_combat_init.initialize_combat(scenario, ["aggi"])

        # Verify combat state created
        assert combat_state is not None
        assert combat_state["in_combat"] == True
        assert combat_state["round_number"] == 1

        # Verify combatants (1 player + 2 goblins)
        assert len(combat_state["active_combatants"]) == 3
        assert "aggi" in combat_state["active_combatants"]

        # Verify initiative order
        assert len(combat_state["initiative_order"]) == 3

        # Verify combatant states
        assert len(combat_state["combatant_states"]) == 3
        assert "aggi" in combat_state["combatant_states"]

    def test_combat_initialization_no_trigger(self, full_combat_init):
        """Test that combat doesn't initialize without trigger"""
        scenario = {
            "scene": "You see a peaceful village.",
            "choices": [
                {"id": "c1", "title": "Talk to villagers", "combat_trigger": False}
            ]
        }

        combat_state = full_combat_init.initialize_combat(scenario, ["aggi"])

        assert combat_state is None


class TestFactoryFunction:
    """Test the factory function"""

    def test_create_combat_initializer(self):
        """Test factory function creates CombatInitializer"""
        combat_init = create_combat_initializer(
            game_engine=Mock(),
            character_manager=Mock(),
            dnd_engine_wrapper=Mock(),
            npc_stat_generator=Mock(),
            npc_registry=Mock(),
            llm=Mock()
        )

        assert isinstance(combat_init, CombatInitializer)
        assert combat_init.game_engine is not None
        assert combat_init.character_manager is not None


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
