"""
Components for D&D Haystack Game Engine - Phase 1 Complete

This module provides all the core components for the D&D game engine,
including the newly implemented Session Manager and Inventory Manager
that complete the Haystack migration Phase 1.
"""

# Core game components
from .character_manager import CharacterManager
from .dice import DiceRoller
from .game_engine import GameEngine
from .policy import PolicyEngine
from .rules import RulesEnforcer

# Phase 1: New Haystack components
from .session_manager import SessionManager
from .inventory_manager import InventoryManager

__all__ = [
    # Core components
    'CharacterManager',
    'DiceRoller', 
    'GameEngine',
    'PolicyEngine',
    'RulesEnforcer',
    
    # Phase 1: New components
    'SessionManager',
    'InventoryManager'
]

# Version info for Phase 1 completion
__version__ = '1.0.0'
__phase__ = 'Phase 1: Complete Haystack Migration'