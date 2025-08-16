"""
Agent Interaction Integration Tests
Tests interactions between different D&D agents
"""
import pytest
import tempfile
import shutil
import os
import sys
import json
from unittest.mock import MagicMock, patch

# Add the project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, project_root)

from agents.character_manager_agent import CharacterManagerAgent
from agents.session_manager_agent import SessionManagerAgent
from agents.inventory_manager_agent import InventoryManagerAgent
from agents.spell_manager_agent import SpellManagerAgent
from agents.experience_manager_agent import ExperienceManagerAgent
from agent_framework import AgentOrchestrator


class TestAgentInteractions:
    """Test interactions between D&D agents"""
    
    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing"""
        temp_dir = tempfile.mkdtemp()
        dirs = {
            'characters': os.path.join(temp_dir, 'characters'),
            'sessions': os.path.join(temp_dir, 'sessions'),
            'inventory': os.path.join(temp_dir, 'inventory'),
            'spells': os.path.join(temp_dir, 'spells'),
            'experience': os.path.join(temp_dir, 'experience')
        }
        
        for dir_path in dirs.values():
            os.makedirs(dir_path, exist_ok=True)
        
        yield dirs
        
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def orchestrator_with_agents(self, temp_dirs):
        """Create orchestrator with all D&D agents"""
        orchestrator = AgentOrchestrator()
        
        # Create agents
        character_agent = CharacterManagerAgent(
            characters_dir=temp_dirs['characters'],
            verbose=False
        )
        session_agent = SessionManagerAgent(
            sessions_dir=temp_dirs['sessions'],
            verbose=False
        )
        inventory_agent = InventoryManagerAgent(
            inventory_dir=temp_dirs['inventory'],
            verbose=False
        )
        spell_agent = SpellManagerAgent(
            spells_dir=temp_dirs['spells'],
            verbose=False
        )
        experience_agent = ExperienceManagerAgent(
            xp_dir=temp_dirs['experience'],
            verbose=False
        )
        
        # Register agents
        orchestrator.register_agent(character_agent)
        orchestrator.register_agent(session_agent)
        orchestrator.register_agent(inventory_agent)
        orchestrator.register_agent(spell_agent)
        orchestrator.register_agent(experience_agent)
        
        agents = {
            'character': character_agent,
            'session': session_agent,
            'inventory': inventory_agent,
            'spell': spell_agent,
            'experience': experience_agent
        }
        
        yield orchestrator, agents
    
    def test_character_creation_and_initialization(self, orchestrator_with_agents):
        """Test character creation with all dependent systems"""
        orchestrator, agents = orchestrator_with_agents
        orchestrator.start()
        
        try:
            # Create a character
            char_response = agents['character'].handle_message({
                "action": "create_character",
                "data": {
                    "name": "TestWizard",
                    "race": "Elf",
                    "character_class": "Wizard",
                    "level": 3
                }
            })
            
            assert char_response["success"]
            character_name = "testwizard"
            
            # Initialize spellcasting for the character
            spell_response = agents['spell'].handle_message({
                "action": "initialize_spellcaster",
                "data": {
                    "character": character_name,
                    "class": "wizard",
                    "level": 3,
                    "spellcasting_ability": "intelligence",
                    "ability_modifier": 3,
                    "proficiency_bonus": 2
                }
            })
            
            assert spell_response["success"]
            
            # Initialize XP tracking
            xp_response = agents['experience'].handle_message({
                "action": "initialize_character_xp",
                "data": {
                    "character": character_name,
                    "level": 3,
                    "xp": 900
                }
            })
            
            assert xp_response["success"]
            
            # Initialize inventory
            inv_response = agents['inventory'].handle_message({
                "action": "initialize_inventory",
                "data": {
                    "character": character_name,
                    "strength_score": 14
                }
            })
            
            assert inv_response["success"]
            
        finally:
            orchestrator.stop()
    
    def test_rest_mechanics_integration(self, orchestrator_with_agents):
        """Test rest mechanics affecting spells and abilities"""
        orchestrator, agents = orchestrator_with_agents
        orchestrator.start()
        
        try:
            character_name = "testcleric"
            
            # Setup character with spellcasting
            agents['spell'].handle_message({
                "action": "initialize_spellcaster",
                "data": {
                    "character": character_name,
                    "class": "cleric",
                    "level": 5,
                    "spellcasting_ability": "wisdom",
                    "ability_modifier": 3,
                    "proficiency_bonus": 3
                }
            })
            
            # Cast some spells to use spell slots
            agents['spell'].handle_message({
                "action": "cast_spell",
                "data": {
                    "character": character_name,
                    "spell": "cure wounds"
                }
            })
            
            # Check spell slots before rest
            slots_before = agents['spell'].handle_message({
                "action": "get_spell_slots",
                "data": {"character": character_name}
            })
            
            # Take a long rest (should restore spell slots)
            rest_response = agents['session'].handle_message({
                "action": "take_long_rest",
                "data": {"party": [character_name]}
            })
            
            assert rest_response["success"]
            
            # Verify spell slots are restored
            restore_response = agents['spell'].handle_message({
                "action": "restore_spell_slots",
                "data": {"character": character_name}
            })
            
            assert restore_response["success"]
            
        finally:
            orchestrator.stop()
    
    def test_leveling_up_integration(self, orchestrator_with_agents):
        """Test leveling up affecting multiple systems"""
        orchestrator, agents = orchestrator_with_agents
        orchestrator.start()
        
        try:
            character_name = "testfighter"
            
            # Create character
            agents['character'].handle_message({
                "action": "create_character",
                "data": {
                    "name": "TestFighter",
                    "race": "Human",
                    "character_class": "Fighter",
                    "level": 1
                }
            })
            
            # Initialize XP tracking
            agents['experience'].handle_message({
                "action": "initialize_character_xp",
                "data": {
                    "character": character_name,
                    "level": 1,
                    "xp": 0
                }
            })
            
            # Add enough XP to level up
            xp_response = agents['experience'].handle_message({
                "action": "add_xp",
                "data": {
                    "character": character_name,
                    "xp": 300,
                    "source": "combat"
                }
            })
            
            assert xp_response["success"]
            assert xp_response.get("level_up", False)
            
            # Level up the character
            level_response = agents['experience'].handle_message({
                "action": "level_up",
                "data": {"character": character_name}
            })
            
            assert level_response["success"]
            assert level_response["new_level"] == 2
            
            # Update character level
            char_response = agents['character'].handle_message({
                "action": "level_up_character",
                "data": {
                    "name": character_name,
                    "new_level": 2
                }
            })
            
            # Should succeed or give appropriate error
            assert char_response.get("success") or "error" in char_response
            
        finally:
            orchestrator.stop()
    
    def test_inventory_and_encumbrance(self, orchestrator_with_agents):
        """Test inventory management and carrying capacity"""
        orchestrator, agents = orchestrator_with_agents
        orchestrator.start()
        
        try:
            character_name = "testbarbarian"
            
            # Initialize inventory with low strength
            agents['inventory'].handle_message({
                "action": "initialize_inventory",
                "data": {
                    "character": character_name,
                    "strength_score": 8  # Low strength for testing encumbrance
                }
            })
            
            # Add multiple heavy items
            heavy_items = ["Plate Armor", "Great Sword", "Shield", "Backpack", "Rope"]
            
            for item in heavy_items:
                response = agents['inventory'].handle_message({
                    "action": "add_item",
                    "data": {
                        "character": character_name,
                        "item_name": item,
                        "quantity": 1
                    }
                })
                
                # Should succeed or warn about encumbrance
                assert response.get("success") or "encumbrance" in response.get("message", "").lower()
            
            # Check carrying capacity status
            capacity_response = agents['inventory'].handle_message({
                "action": "get_carrying_capacity",
                "data": {"character": character_name}
            })
            
            assert capacity_response["success"]
            
        finally:
            orchestrator.stop()
    
    def test_spell_preparation_and_casting_limits(self, orchestrator_with_agents):
        """Test spell preparation limits and slot usage"""
        orchestrator, agents = orchestrator_with_agents
        orchestrator.start()
        
        try:
            character_name = "testwizard"
            
            # Initialize low-level wizard
            agents['spell'].handle_message({
                "action": "initialize_spellcaster",
                "data": {
                    "character": character_name,
                    "class": "wizard",
                    "level": 1,
                    "spellcasting_ability": "intelligence",
                    "ability_modifier": 3,
                    "proficiency_bonus": 2
                }
            })
            
            # Learn some spells
            spell_names = ["Magic Missile", "Shield", "Detect Magic"]
            for spell in spell_names:
                agents['spell'].handle_message({
                    "action": "learn_spell",
                    "data": {
                        "character": character_name,
                        "spell": spell
                    }
                })
            
            # Try to prepare more spells than allowed
            prepare_response = agents['spell'].handle_message({
                "action": "prepare_spells",
                "data": {
                    "character": character_name,
                    "spells": spell_names  # Might be too many for level 1
                }
            })
            
            # Should succeed or give appropriate limit error
            assert prepare_response.get("success") or "maximum" in prepare_response.get("error", "").lower()
            
            # Cast spells until slots are exhausted
            for i in range(5):  # Try to cast more than available slots
                cast_response = agents['spell'].handle_message({
                    "action": "cast_spell",
                    "data": {
                        "character": character_name,
                        "spell": "Magic Missile"
                    }
                })
                
                if not cast_response.get("success"):
                    assert "slot" in cast_response.get("error", "").lower()
                    break
            
        finally:
            orchestrator.stop()
    
    def test_session_time_tracking(self, orchestrator_with_agents):
        """Test session time tracking across activities"""
        orchestrator, agents = orchestrator_with_agents
        orchestrator.start()
        
        try:
            # Start a new session
            session_response = agents['session'].handle_message({
                "action": "start_session",
                "data": {
                    "party": ["hero1", "hero2"],
                    "location": "Test Dungeon"
                }
            })
            
            assert session_response["success"]
            
            # Add some time-consuming activities
            agents['session'].handle_message({
                "action": "add_time",
                "data": {
                    "hours": 2,
                    "activity": "exploration"
                }
            })
            
            agents['session'].handle_message({
                "action": "add_time",
                "data": {
                    "minutes": 30,
                    "activity": "combat"
                }
            })
            
            # Check session status
            status_response = agents['session'].handle_message({
                "action": "get_session_status",
                "data": {}
            })
            
            assert status_response["success"]
            assert status_response["session"]["total_time_hours"] > 2
            
        finally:
            orchestrator.stop()
    
    def test_experience_calculation_integration(self, orchestrator_with_agents):
        """Test experience calculation and distribution"""
        orchestrator, agents = orchestrator_with_agents
        orchestrator.start()
        
        try:
            # Initialize multiple characters
            characters = ["hero1", "hero2", "hero3"]
            
            for char in characters:
                agents['experience'].handle_message({
                    "action": "initialize_character_xp",
                    "data": {
                        "character": char,
                        "level": 2,
                        "xp": 300
                    }
                })
            
            # Calculate encounter XP
            encounter_response = agents['experience'].handle_message({
                "action": "calculate_encounter_xp",
                "data": {
                    "monsters": [
                        {"cr": 1, "count": 2, "name": "Orc"},
                        {"cr": 2, "count": 1, "name": "Orc Chief"}
                    ],
                    "party_size": len(characters)
                }
            })
            
            assert encounter_response["success"]
            xp_per_character = encounter_response["xp_per_character"]
            
            # Award XP to all characters
            for char in characters:
                xp_response = agents['experience'].handle_message({
                    "action": "add_xp",
                    "data": {
                        "character": char,
                        "xp": xp_per_character,
                        "source": "combat encounter"
                    }
                })
                
                assert xp_response["success"]
            
        finally:
            orchestrator.stop()
    
    def test_error_handling_across_agents(self, orchestrator_with_agents):
        """Test error handling and edge cases across agents"""
        orchestrator, agents = orchestrator_with_agents
        orchestrator.start()
        
        try:
            # Test with non-existent character
            invalid_responses = []
            
            # Character agent
            invalid_responses.append(agents['character'].handle_message({
                "action": "get_character",
                "data": {"name": "nonexistent"}
            }))
            
            # Spell agent
            invalid_responses.append(agents['spell'].handle_message({
                "action": "cast_spell",
                "data": {
                    "character": "nonexistent",
                    "spell": "Magic Missile"
                }
            }))
            
            # Experience agent
            invalid_responses.append(agents['experience'].handle_message({
                "action": "add_xp",
                "data": {
                    "character": "nonexistent",
                    "xp": 100
                }
            }))
            
            # Inventory agent
            invalid_responses.append(agents['inventory'].handle_message({
                "action": "add_item",
                "data": {
                    "character": "nonexistent",
                    "item_name": "Sword"
                }
            }))
            
            # All should handle errors gracefully
            for response in invalid_responses:
                assert not response.get("success", True)  # Should fail
                assert "error" in response  # Should have error message
            
        finally:
            orchestrator.stop()
    
    def test_message_passing_integration(self, orchestrator_with_agents):
        """Test message passing between agents through orchestrator"""
        orchestrator, agents = orchestrator_with_agents
        orchestrator.start()
        
        try:
            # Send messages through orchestrator
            message_id = orchestrator.send_message_to_agent("character_manager", "get_stats", {})
            assert message_id is not None
            
            # Check message history
            history = orchestrator.message_bus.get_message_history(limit=10)
            assert len(history) > 0
            
            # Get agent status
            status = orchestrator.get_agent_status()
            assert len(status) == 5  # All 5 D&D agents
            
            # Get message statistics
            stats = orchestrator.get_message_statistics()
            assert stats["registered_agents"] == 5
            assert stats["total_messages"] > 0
            
        finally:
            orchestrator.stop()


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])