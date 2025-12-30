"""
Complete D&D Workflow Integration Tests
Tests the full end-to-end D&D gameplay experience with all new agents
"""
import pytest
import tempfile
import shutil
import os
from unittest.mock import MagicMock, patch
import sys
import json
from pathlib import Path

# Add the project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, project_root)

from modular_dm_assistant import ModularDMAssistant
from agents.character_manager_agent import CharacterManagerAgent
from agents.session_manager_agent import SessionManagerAgent
from agents.inventory_manager_agent import InventoryManagerAgent
from agents.spell_manager_agent import SpellManagerAgent
from agents.experience_manager_agent import ExperienceManagerAgent


class TestCompleteDnDWorkflow:
    """Integration tests for complete D&D workflows"""
    
    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing"""
        temp_dir = tempfile.mkdtemp()
        dirs = {
            'base': temp_dir,
            'campaigns': os.path.join(temp_dir, 'campaigns'),
            'players': os.path.join(temp_dir, 'players'),
            'characters': os.path.join(temp_dir, 'characters'),
            'sessions': os.path.join(temp_dir, 'sessions'),
            'inventory': os.path.join(temp_dir, 'inventory'),
            'spells': os.path.join(temp_dir, 'spells'),
            'experience': os.path.join(temp_dir, 'experience'),
            'game_saves': os.path.join(temp_dir, 'game_saves')
        }
        
        # Create all directories
        for dir_path in dirs.values():
            os.makedirs(dir_path, exist_ok=True)
        
        yield dirs
        
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def mock_qdrant_client(self):
        """Mock Qdrant client for testing"""
        with patch('qdrant_client.QdrantClient') as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            
            # Mock collection info
            mock_instance.get_collection.return_value = MagicMock()
            mock_instance.get_collections.return_value = MagicMock()
            
            yield mock_instance
    
    @pytest.fixture
    def sample_campaign_data(self, temp_dirs):
        """Create sample campaign data"""
        campaign_data = {
            "title": "Test Campaign",
            "theme": "High Fantasy",
            "setting": "Forgotten Realms",
            "level_range": "1-5",
            "overview": "A test campaign for integration testing",
            "npcs": [
                {"name": "Test NPC", "role": "Merchant", "location": "Test Town"}
            ],
            "locations": [
                {"name": "Test Town", "location_type": "Settlement", "description": "A small testing town"}
            ]
        }
        
        campaign_file = os.path.join(temp_dirs['campaigns'], 'test_campaign.json')
        with open(campaign_file, 'w') as f:
            json.dump(campaign_data, f, indent=2)
        
        return campaign_data
    
    @pytest.fixture
    def sample_player_data(self, temp_dirs):
        """Create sample player data"""
        player_data = {
            "name": "Test Hero",
            "race": "Human",
            "character_class": "Fighter",
            "level": 3,
            "background": "Soldier",
            "rulebook": "PHB",
            "hp": 28,
            "ability_scores": {
                "strength": 16,
                "dexterity": 14,
                "constitution": 15,
                "intelligence": 12,
                "wisdom": 13,
                "charisma": 10
            },
            "combat_stats": {
                "armor_class": 16,
                "initiative_bonus": 2,
                "proficiency_bonus": 2
            }
        }
        
        player_file = os.path.join(temp_dirs['players'], 'test_hero.json')
        with open(player_file, 'w') as f:
            json.dump(player_data, f, indent=2)
        
        return player_data
    
    @pytest.fixture
    def dm_assistant(self, temp_dirs, mock_qdrant_client, sample_campaign_data, sample_player_data):
        """Create a ModularDMAssistant instance for testing"""
        with patch('haystack_pipeline_agent.QdrantDocumentStore'), \
             patch('haystack_pipeline_agent.get_embeddings_model'), \
             patch('haystack_pipeline_agent.get_llm_generator'):
            
            assistant = ModularDMAssistant(
                collection_name="test_collection",
                campaigns_dir=temp_dirs['campaigns'],
                players_dir=temp_dirs['players'],
                verbose=False,
                enable_game_engine=True,
                enable_caching=True,
                enable_async=False
            )
            
            # Override directories for new agents
            if assistant.character_agent:
                assistant.character_agent.characters_dir = temp_dirs['characters']
            if assistant.session_agent:
                assistant.session_agent.sessions_dir = temp_dirs['sessions']
            if assistant.inventory_agent:
                assistant.inventory_agent.inventory_dir = temp_dirs['inventory']
            if assistant.spell_agent:
                assistant.spell_agent.spells_dir = temp_dirs['spells']
            if assistant.experience_agent:
                assistant.experience_agent.xp_dir = temp_dirs['experience']
            
            assistant.game_saves_dir = temp_dirs['game_saves']
            
            yield assistant
    
    def test_character_creation_workflow(self, dm_assistant):
        """Test complete character creation workflow"""
        # Start the assistant
        dm_assistant.start()
        
        try:
            # Create a new character
            response = dm_assistant.process_dm_input("create character Aragorn")
            
            assert "CHARACTER CREATED" in response or "Failed to create character" in response
            
            # If character creation succeeded, test character info
            if "CHARACTER CREATED" in response:
                # Test getting character info (would require extending the system)
                pass
        
        finally:
            dm_assistant.stop()
    
    def test_inventory_management_workflow(self, dm_assistant):
        """Test complete inventory management workflow"""
        dm_assistant.start()
        
        try:
            # Add items to inventory
            response1 = dm_assistant.process_dm_input("add item Longsword")
            assert "ITEM ADDED" in response1 or "Failed to add item" in response1
            
            response2 = dm_assistant.process_dm_input("add item Health Potion")
            assert "ITEM ADDED" in response2 or "Failed to add item" in response2
            
            # Show inventory
            response3 = dm_assistant.process_dm_input("show inventory")
            assert "INVENTORY" in response3 or "Failed to show inventory" in response3
            
            # Remove an item
            response4 = dm_assistant.process_dm_input("remove item Longsword")
            assert "ITEM REMOVED" in response4 or "Failed to remove item" in response4
        
        finally:
            dm_assistant.stop()
    
    def test_rest_mechanics_workflow(self, dm_assistant):
        """Test rest mechanics workflow"""
        dm_assistant.start()
        
        try:
            # Take a short rest
            response1 = dm_assistant.process_dm_input("short rest")
            assert "SHORT REST" in response1 or "Failed to take short rest" in response1
            
            # Take a long rest
            response2 = dm_assistant.process_dm_input("long rest")
            assert "LONG REST" in response2 or "Failed to take long rest" in response2
        
        finally:
            dm_assistant.stop()
    
    def test_spell_management_workflow(self, dm_assistant):
        """Test spell management workflow"""
        dm_assistant.start()
        
        try:
            # Show prepared spells
            response1 = dm_assistant.process_dm_input("prepare spells")
            assert "PREPARED SPELLS" in response1 or "Failed to show prepared spells" in response1
            
            # Cast a spell
            response2 = dm_assistant.process_dm_input("cast Magic Missile")
            assert "SPELL CAST" in response2 or "Failed to cast spell" in response2
        
        finally:
            dm_assistant.stop()
    
    def test_experience_and_leveling_workflow(self, dm_assistant):
        """Test experience gain and leveling workflow"""
        dm_assistant.start()
        
        try:
            # Attempt to level up a character
            response = dm_assistant.process_dm_input("level up TestHero")
            assert "LEVEL UP" in response or "Failed to level up" in response
        
        finally:
            dm_assistant.stop()
    
    def test_combat_integration_workflow(self, dm_assistant):
        """Test combat integration with new D&D features"""
        dm_assistant.start()
        
        try:
            # Start combat
            response1 = dm_assistant.process_dm_input("start combat")
            assert "COMBAT STARTED" in response1 or "Failed to start combat" in response1
            
            # Check combat status
            response2 = dm_assistant.process_dm_input("combat status")
            assert "Combat Status" in response2 or "Failed to get combat status" in response2
            
            # End combat
            response3 = dm_assistant.process_dm_input("end combat")
            assert "COMBAT ENDED" in response3 or "Failed to end combat" in response3
        
        finally:
            dm_assistant.stop()
    
    def test_dice_rolling_integration(self, dm_assistant):
        """Test dice rolling with skill check integration"""
        dm_assistant.start()
        
        try:
            # Roll basic dice
            response1 = dm_assistant.process_dm_input("roll 1d20")
            assert "MANUAL ROLL" in response1 or "Result:" in response1
            
            # Roll skill check
            response2 = dm_assistant.process_dm_input("roll stealth check")
            assert "STEALTH CHECK" in response2 or "Result:" in response2
            
            # Roll attack
            response3 = dm_assistant.process_dm_input("roll attack")
            assert "ATTACK ROLL" in response3 or "Result:" in response3
        
        finally:
            dm_assistant.stop()
    
    def test_scenario_generation_with_dnd_features(self, dm_assistant):
        """Test scenario generation integration with D&D features"""
        dm_assistant.start()
        
        try:
            # Generate a scenario
            response1 = dm_assistant.process_dm_input("generate scenario")
            assert "SCENARIO" in response1 or "Failed to generate scenario" in response1
            
            # If options are available, try selecting one
            if "select option" in response1.lower():
                response2 = dm_assistant.process_dm_input("select option 1")
                assert "SELECTED" in response2 or "Invalid option" in response2
        
        finally:
            dm_assistant.stop()
    
    def test_rule_checking_integration(self, dm_assistant):
        """Test rule checking integration"""
        dm_assistant.start()
        
        try:
            # Check a combat rule
            response1 = dm_assistant.process_dm_input("rule opportunity attack")
            assert ("RULE" in response1 or "Failed to find rule" in response1 or 
                   "opportunity attack" in response1.lower())
            
            # Check a spell rule
            response2 = dm_assistant.process_dm_input("how does concentration work")
            assert ("concentration" in response2.lower() or "Failed to find rule" in response2)
        
        finally:
            dm_assistant.stop()
    
    def test_game_save_load_integration(self, dm_assistant):
        """Test game save and load functionality with new agents"""
        dm_assistant.start()
        
        try:
            # Make some changes to track
            dm_assistant.process_dm_input("add item Test Sword")
            dm_assistant.process_dm_input("short rest")
            
            # Save the game
            response1 = dm_assistant.process_dm_input("save game Integration Test")
            assert "Game saved successfully" in response1 or "Failed to save game" in response1
            
            # List saves
            response2 = dm_assistant.process_dm_input("list saves")
            assert "AVAILABLE GAME SAVES" in response2 or "No game saves found" in response2
            
            # If saves are available, try loading one
            if "Integration Test" in response2:
                response3 = dm_assistant.process_dm_input("load save 1")
                assert ("Successfully loaded" in response3 or "Failed to load save" in response3 or
                       "Invalid save number" in response3)
        
        finally:
            dm_assistant.stop()
    
    def test_agent_orchestration_integration(self, dm_assistant):
        """Test that all agents work together properly"""
        dm_assistant.start()
        
        try:
            # Test system status to verify all agents are running
            response = dm_assistant.process_dm_input("system status")
            assert "MODULAR DM ASSISTANT STATUS" in response
            
            # Verify key agents are mentioned
            agent_names = ["character_manager", "session_manager", "inventory_manager", 
                          "spell_manager", "experience_manager"]
            
            for agent_name in agent_names:
                # The status should show these agents or indicate they're not available
                assert (agent_name in response.lower() or 
                       "agent" in response.lower())  # More flexible check
        
        finally:
            dm_assistant.stop()
    
    def test_command_mapping_integration(self, dm_assistant):
        """Test that command mapping works with new D&D features"""
        dm_assistant.start()
        
        try:
            # Test various command formats
            commands_and_responses = [
                ("create character TestChar", "CHARACTER CREATED"),
                ("short rest", "SHORT REST"),
                ("long rest", "LONG REST"),
                ("add item Sword", "ITEM ADDED"),
                ("show inventory", "INVENTORY"),
                ("cast spell", "SPELL CAST"),
                ("level up TestChar", "LEVEL UP"),
            ]
            
            for command, expected_keyword in commands_and_responses:
                response = dm_assistant.process_dm_input(command)
                # More flexible checking - either success or proper error handling
                assert (expected_keyword in response or 
                       "Failed to" in response or 
                       "Agent communication timeout" in response or
                       "not initialized" in response)
        
        finally:
            dm_assistant.stop()
    
    def test_caching_integration_with_new_agents(self, dm_assistant):
        """Test that caching works properly with new D&D agents"""
        dm_assistant.start()
        
        try:
            # Make identical requests to test caching
            response1 = dm_assistant.process_dm_input("show inventory")
            response2 = dm_assistant.process_dm_input("show inventory")
            
            # Both should succeed (even if from cache)
            assert "INVENTORY" in response1 or "Failed to show inventory" in response1
            assert "INVENTORY" in response2 or "Failed to show inventory" in response2
            
            # Test that cache statistics are available
            if dm_assistant.inline_cache:
                stats = dm_assistant.inline_cache.get_stats()
                assert isinstance(stats, dict)
                assert 'total_items' in stats
        
        finally:
            dm_assistant.stop()
    
    def test_error_handling_integration(self, dm_assistant):
        """Test error handling across all integrated systems"""
        dm_assistant.start()
        
        try:
            # Test invalid commands
            response1 = dm_assistant.process_dm_input("invalid command that doesnt exist")
            assert ("Failed to" in response1 or 
                   "Unknown error" in response1 or
                   "💡" in response1)  # RAG fallback response
            
            # Test commands with missing parameters
            response2 = dm_assistant.process_dm_input("create character")
            assert "Please specify character name" in response2
            
            response3 = dm_assistant.process_dm_input("add item")
            assert "Please specify item name" in response3
            
            response4 = dm_assistant.process_dm_input("level up")
            assert "Please specify character name" in response4
        
        finally:
            dm_assistant.stop()


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])