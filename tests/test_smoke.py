import pytest
import os
import sys

# Add the project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from modular_dm_assistant import ModularDMAssistant

def test_assistant_initialization():
    """Smoke test for basic initialization"""
    assistant = ModularDMAssistant(verbose=False)
    assert assistant is not None
    assert assistant.orchestrator is not None

def test_agent_registration():
    """Test that all agents are registered"""
    assistant = ModularDMAssistant(verbose=False)
    assistant.start()
    
    status = assistant.orchestrator.get_agent_status()
    expected_agents = [
        'haystack_pipeline', 'campaign_manager', 'game_engine',
        'character_manager', 'session_manager', 'inventory_manager', 
        'spell_manager', 'experience_manager', 'scenario_generator',
        'combat_engine', 'dice_system', 'npc_controller', 'rule_enforcement'
    ]
    
    for agent in expected_agents:
        assert agent in status
    
    assistant.stop()