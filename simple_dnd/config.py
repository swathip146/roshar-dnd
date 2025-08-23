#!/usr/bin/env python3
"""
Basic configuration for the simple D&D game
"""
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class GameConfig:
    """Simple game configuration"""
    
    # AI Model settings
    model_name: str = "aws:anthropic.claude-sonnet-4-20250514-v1:0"
    
    # Game settings
    max_history_length: int = 10
    auto_save_interval: int = 5  # turns
    
    # Default game state
    default_location: str = "Tavern"
    default_story: str = "You enter a bustling tavern filled with adventurers, merchants, and locals. The air is thick with pipe smoke and the aroma of roasted meat. A fire crackles in the hearth, casting dancing shadows on weathered faces."
    default_player_name: str = "Adventurer"
    
    # File paths
    saves_directory: str = "saves"
    
    # Dice settings
    default_difficulty: int = 15
    
    # Scenario generation settings
    scenario_contexts: Dict[str, str] = None
    
    def __post_init__(self):
        """Initialize default values that need to be computed"""
        if self.scenario_contexts is None:
            self.scenario_contexts = {
                "tavern": "A cozy tavern with warm lighting and friendly patrons",
                "forest": "A dense forest with ancient trees and mysterious sounds",
                "dungeon": "A dark underground dungeon filled with dangers",
                "town": "A bustling town square with merchants and townsfolk",
                "road": "A winding road through the countryside",
                "cave": "A mysterious cave entrance beckoning adventurers"
            }
    
    def get_context_description(self, context: str) -> str:
        """Get description for a given context"""
        return self.scenario_contexts.get(context.lower(), f"An unknown location: {context}")

# Global default config instance
DEFAULT_CONFIG = GameConfig()