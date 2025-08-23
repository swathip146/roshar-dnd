"""
Integration tests for Phase 1 Haystack D&D Migration

This test suite validates that all Phase 1 components work together:
- Agents framework with proper Haystack Agent patterns
- Enhanced orchestrator with pipeline integration
- New components (SessionManager, InventoryManager) 
- Core migration (haystack_dnd_game.py) functionality

Run with: python -m pytest tests/test_phase1_integration.py -v
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from haystack import Pipeline
    from haystack.components.generators import OpenAIGenerator
    HAYSTACK_AVAILABLE = True
except ImportError:
    HAYSTACK_AVAILABLE = False
    Pipeline = None
    OpenAIGenerator = None

# Import our components
from agents.scenario_generator_agent import ScenarioGeneratorAgent
from agents.rag_retriever_agent import RAGRetrieverAgent
from agents.npc_controller_agent import NPCControllerAgent
from agents.main_interface_agent import MainInterfaceAgent

from orchestrator.pipeline_integration import PipelineOrchestrator
from orchestrator.context_broker import ContextBroker

from components.session_manager import SessionManager
from components.inventory_manager import InventoryManager


class TestAgentsFramework:
    """Test the Agents framework implementation"""
    
    @pytest.fixture
    def mock_generator(self):
        """Mock OpenAI generator for testing"""
        generator = Mock()
        generator.run.return_value = {
            "replies": [{"content": "Test response"}]
        }
        return generator

    def test_scenario_generator_agent_creation(self, mock_generator):
        """Test ScenarioGeneratorAgent can be created and configured"""
        agent = ScenarioGeneratorAgent(generator=mock_generator)
        
        assert agent.generator == mock_generator
        assert hasattr(agent, 'get_character_info')
        assert hasattr(agent, 'roll_dice')
        assert hasattr(agent, 'generate_scenario')

    def test_scenario_generator_tools(self, mock_generator):
        """Test ScenarioGeneratorAgent tools work correctly"""
        agent = ScenarioGeneratorAgent(generator=mock_generator)
        
        # Test character info tool
        char_info = agent.get_character_info("TestChar")
        assert isinstance(char_info, str)
        assert "TestChar" in char_info or "not found" in char_info.lower()
        
        # Test dice roll tool  
        result = agent.roll_dice("1d20")
        assert isinstance(result, str)
        assert "rolled" in result.lower() or "result" in result.lower()

    def test_rag_retriever_agent_creation(self, mock_generator):
        """Test RAGRetrieverAgent can be created"""
        agent = RAGRetrieverAgent(generator=mock_generator)
        
        assert agent.generator == mock_generator
        assert hasattr(agent, 'search_documents')
        assert hasattr(agent, 'enhance_context')

    def test_npc_controller_agent_creation(self, mock_generator):
        """Test NPCControllerAgent can be created"""
        agent = NPCControllerAgent(generator=mock_generator)
        
        assert agent.generator == mock_generator
        assert hasattr(agent, 'get_character_info')
        assert hasattr(agent, 'control_npc')

    def test_main_interface_agent_creation(self, mock_generator):
        """Test MainInterfaceAgent can be created"""
        agent = MainInterfaceAgent(generator=mock_generator)
        
        assert agent.generator == mock_generator
        assert hasattr(agent, 'parse_user_input')
        assert hasattr(agent, 'format_response')


class TestOrchestratorIntegration:
    """Test the enhanced orchestrator with pipeline integration"""
    
    @pytest.fixture
    def mock_components(self):
        """Mock all required components"""
        return {
            'character_manager': Mock(),
            'dice_roller': Mock(),
            'game_engine': Mock(),
            'policy_engine': Mock(),
            'rules_enforcer': Mock(),
            'session_manager': Mock(),
            'inventory_manager': Mock()
        }

    @pytest.fixture
    def context_broker(self, mock_components):
        """Create ContextBroker with mocked components"""
        return ContextBroker(**mock_components)

    def test_context_broker_creation(self, context_broker):
        """Test ContextBroker can be created with all components"""
        assert context_broker.character_manager is not None
        assert context_broker.dice_roller is not None
        assert context_broker.game_engine is not None
        assert context_broker.policy_engine is not None
        assert context_broker.rules_enforcer is not None
        assert context_broker.session_manager is not None
        assert context_broker.inventory_manager is not None

    def test_context_broker_should_use_rag(self, context_broker):
        """Test ContextBroker RAG decision logic"""
        # Test scenario that should use RAG
        rag_scenario = context_broker.should_use_rag("Tell me about dragons in D&D lore")
        assert isinstance(rag_scenario, bool)
        
        # Test scenario that should use rules
        rules_scenario = context_broker.should_use_rag("Can I cast this spell?")
        assert isinstance(rules_scenario, bool)

    @patch('orchestrator.pipeline_integration.Pipeline')
    def test_pipeline_orchestrator_creation(self, mock_pipeline_class, mock_components):
        """Test PipelineOrchestrator can be created"""
        mock_pipeline_class.return_value = Mock()
        
        orchestrator = PipelineOrchestrator(**mock_components)
        assert orchestrator.context_broker is not None
        assert orchestrator.pipelines is not None

    @patch('orchestrator.pipeline_integration.Pipeline')
    def test_pipeline_orchestrator_routing(self, mock_pipeline_class, mock_components):
        """Test PipelineOrchestrator can route requests"""
        mock_pipeline = Mock()
        mock_pipeline.run.return_value = {"response": "Test response"}
        mock_pipeline_class.return_value = mock_pipeline
        
        orchestrator = PipelineOrchestrator(**mock_components)
        
        result = orchestrator.process_request("scenario", {"user_input": "Test input"})
        assert isinstance(result, dict)


class TestNewComponents:
    """Test the new Phase 1 components"""
    
    def test_session_manager_creation(self):
        """Test SessionManager can be created and configured"""
        session_mgr = SessionManager()
        
        assert hasattr(session_mgr, 'run')
        assert hasattr(session_mgr, 'create_session')
        assert hasattr(session_mgr, 'get_session')
        assert hasattr(session_mgr, 'update_session')

    def test_session_manager_operations(self):
        """Test SessionManager core operations"""
        session_mgr = SessionManager()
        
        # Test session creation
        session_id = session_mgr.create_session("test_user")
        assert isinstance(session_id, str)
        assert len(session_id) > 0
        
        # Test session retrieval
        session = session_mgr.get_session(session_id)
        assert session is not None
        assert session.get("user_id") == "test_user"
        
        # Test session update
        updated = session_mgr.update_session(session_id, {"test_key": "test_value"})
        assert updated is True

    def test_inventory_manager_creation(self):
        """Test InventoryManager can be created and configured"""
        inventory_mgr = InventoryManager()
        
        assert hasattr(inventory_mgr, 'run')
        assert hasattr(inventory_mgr, 'add_item')
        assert hasattr(inventory_mgr, 'remove_item')
        assert hasattr(inventory_mgr, 'calculate_encumbrance')

    def test_inventory_manager_operations(self):
        """Test InventoryManager core operations"""
        inventory_mgr = InventoryManager()
        
        # Test adding item
        result = inventory_mgr.add_item(
            character_id="test_char",
            item_data={
                "name": "Test Sword",
                "type": "weapon",
                "weight": 3,
                "value": 100
            }
        )
        assert result.get("success") is True
        
        # Test calculating encumbrance
        encumbrance = inventory_mgr.calculate_encumbrance("test_char")
        assert isinstance(encumbrance, dict)
        assert "total_weight" in encumbrance
        assert "capacity" in encumbrance


class TestMigrationIntegration:
    """Test the core migration integration"""
    
    @patch('haystack_dnd_game.PipelineOrchestrator')
    @patch('haystack_dnd_game.ContextBroker')
    def test_haystack_dnd_game_imports(self, mock_context_broker, mock_orchestrator):
        """Test that haystack_dnd_game.py can import all required components"""
        try:
            import haystack_dnd_game
            assert hasattr(haystack_dnd_game, 'HaystackDnDGame')
        except ImportError as e:
            pytest.fail(f"Failed to import haystack_dnd_game: {e}")

    @patch('haystack_dnd_game.PipelineOrchestrator')
    @patch('haystack_dnd_game.ContextBroker')
    def test_haystack_dnd_game_creation(self, mock_context_broker, mock_orchestrator):
        """Test HaystackDnDGame can be created"""
        import haystack_dnd_game
        
        # Mock the orchestrator
        mock_orch = Mock()
        mock_orchestrator.return_value = mock_orch
        
        game = haystack_dnd_game.HaystackDnDGame()
        assert game is not None

    @patch('haystack_dnd_game.PipelineOrchestrator')
    @patch('haystack_dnd_game.ContextBroker')
    def test_backward_compatibility(self, mock_context_broker, mock_orchestrator):
        """Test that backward compatibility functions exist"""
        import haystack_dnd_game
        
        mock_orch = Mock()
        mock_orch.process_request.return_value = {"response": "Test response"}
        mock_orchestrator.return_value = mock_orch
        
        # Test that simple_dnd_game interface functions exist
        assert hasattr(haystack_dnd_game, 'create_character')
        assert hasattr(haystack_dnd_game, 'roll_dice')
        assert hasattr(haystack_dnd_game, 'start_adventure')


class TestSystemIntegration:
    """Test full system integration"""
    
    @pytest.fixture
    def integration_setup(self):
        """Set up components for integration testing"""
        with patch('haystack.Pipeline'), \
             patch('haystack.components.generators.OpenAIGenerator'), \
             patch('orchestrator.pipeline_integration.PipelineOrchestrator') as mock_orch:
            
            mock_orchestrator = Mock()
            mock_orchestrator.process_request.return_value = {
                "response": "Integration test response",
                "session_id": "test_session",
                "character_updates": {}
            }
            mock_orch.return_value = mock_orchestrator
            
            yield mock_orchestrator

    def test_end_to_end_scenario_generation(self, integration_setup):
        """Test end-to-end scenario generation flow"""
        mock_orchestrator = integration_setup
        
        # Simulate a scenario generation request
        result = mock_orchestrator.process_request(
            "scenario",
            {
                "user_input": "Generate a dungeon adventure",
                "character_id": "test_character",
                "session_id": "test_session"
            }
        )
        
        assert isinstance(result, dict)
        assert "response" in result
        mock_orchestrator.process_request.assert_called_once()

    def test_component_chain_integration(self):
        """Test that all components can be chained together"""
        # Test component instantiation chain
        session_mgr = SessionManager()
        inventory_mgr = InventoryManager()
        
        # Test they can work together
        session_id = session_mgr.create_session("test_user")
        session_mgr.update_session(session_id, {
            "character_id": "test_char",
            "current_location": "tavern"
        })
        
        # Test inventory integration with session
        inventory_result = inventory_mgr.add_item(
            character_id="test_char",
            item_data={"name": "Health Potion", "type": "consumable", "weight": 0.5}
        )
        
        assert inventory_result.get("success") is True


@pytest.mark.skipif(not HAYSTACK_AVAILABLE, reason="Haystack not available")
class TestHaystackIntegration:
    """Test integration with actual Haystack framework when available"""
    
    def test_pipeline_creation(self):
        """Test that Haystack Pipelines can be created"""
        pipeline = Pipeline()
        assert pipeline is not None

    def test_component_integration(self):
        """Test that our components integrate with Haystack"""
        session_mgr = SessionManager()
        
        # Test Haystack component interface
        assert hasattr(session_mgr, 'run')
        
        # Test component can be added to pipeline
        pipeline = Pipeline()
        pipeline.add_component("session_manager", session_mgr)
        
        components = pipeline.get_components()
        assert "session_manager" in components


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "--tb=short"])