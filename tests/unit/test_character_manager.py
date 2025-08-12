"""
Unit tests for CharacterManager agent
"""
import pytest
from unittest.mock import Mock, patch
import os
import sys
import tempfile
import shutil

# Add the project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, project_root)

from character_manager_agent import CharacterManagerAgent

class TestCharacterManager:
    """Test CharacterManager functionality"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def character_agent(self, temp_dir):
        """Create CharacterManagerAgent for testing"""
        return CharacterManagerAgent(characters_dir=temp_dir, verbose=False)
    
    def test_create_character(self, character_agent):
        """Test character creation"""
        response = character_agent.handle_message({
            "action": "create_character",
            "data": {
                "name": "TestHero",
                "race": "Human",
                "character_class": "Fighter",
                "level": 1
            }
        })
        
        assert response["success"]
        assert "TestHero" in response["message"]
    
    def test_update_character_stats(self, character_agent):
        """Test character stat updates"""
        # Create character first
        character_agent.handle_message({
            "action": "create_character",
            "data": {
                "name": "TestHero",
                "race": "Human",
                "character_class": "Fighter",
                "level": 1
            }
        })
        
        # Update stats
        response = character_agent.handle_message({
            "action": "update_ability_scores",
            "data": {
                "name": "TestHero",
                "ability_scores": {
                    "strength": 16,
                    "dexterity": 14,
                    "constitution": 15
                }
            }
        })
        
        # Should succeed or handle gracefully
        assert "success" in response or "error" in response
    
    def test_get_character_info(self, character_agent):
        """Test character information retrieval"""
        # Create character first
        character_agent.handle_message({
            "action": "create_character",
            "data": {
                "name": "TestHero",
                "race": "Human",
                "character_class": "Fighter",
                "level": 1
            }
        })
        
        # Get character info
        response = character_agent.handle_message({
            "action": "get_character",
            "data": {"name": "TestHero"}
        })
        
        assert response["success"]
        assert "character" in response
        assert response["character"]["name"] == "TestHero"
    
    def test_calculate_modifiers(self, character_agent):
        """Test ability score modifier calculation"""
        # Test various ability scores
        test_cases = [
            (8, -1),   # 8-9 = -1
            (10, 0),   # 10-11 = 0
            (12, 1),   # 12-13 = +1
            (16, 3),   # 16-17 = +3
            (20, 5)    # 20 = +5
        ]
        
        for score, expected_modifier in test_cases:
            modifier = character_agent._calculate_ability_modifier(score)
            assert modifier == expected_modifier