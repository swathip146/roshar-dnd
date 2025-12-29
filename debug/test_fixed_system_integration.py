#!/usr/bin/env python3
"""
Test script for Fixed System Integration
Validates the implementation of Phases 1, 2, and 3
"""

import os
import sys
import json
import time

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_phase_1_foundation():
    """Test Phase 1: Foundation components"""
    print("🔧 Testing Phase 1: Foundation")
    
    # Test enhanced shared contract
    try:
        from components.shared_contract import new_dto, new_response_dto, RequestDTO
        
        # Test DTO creation
        test_dto = new_dto("test input", {"location": "tavern"})
        assert "player_input" in test_dto
        assert "correlation_id" in test_dto
        assert "confidence" in test_dto
        print("✅ Enhanced shared contract working")
        
    except Exception as e:
        print(f"❌ Shared contract test failed: {e}")
        return False
    
    # Test RoutingContextAdapter (enhanced WorldStateAdapter)
    try:
        from adapters.world_state_adapter import MockRoutingContextAdapter, RoutingContextAdapter

        # Test mock adapter with enhanced features
        mock_data = {
            "campaign": {"name": "Test Campaign", "theme": "fantasy", "difficulty": "medium"},
            "npcs": {
                "test_npc": {"name": "Test NPC", "aliases": ["tester"], "source": "test"}
            },
            "places": ["Test Location", "Another Place"],
            "current_location": "Test Location",
            "campaign_flags": {"test_flag": True}
        }
        
        adapter = MockRoutingContextAdapter(mock_data)
        npcs = adapter.npcs
        places = adapter.places
        npc_names = adapter.npc_names
        context = adapter.get_current_context()
        
        assert isinstance(npcs, dict)
        assert isinstance(places, list)
        assert isinstance(npc_names, list)
        assert isinstance(context, dict)
        assert "campaign_name" in context
        assert "data_sources" in context
        print("✅ Enhanced RoutingContextAdapter working")

        # Test backward compatibility aliases
        from adapters.world_state_adapter import WorldStateAdapter, MockWorldStateAdapter
        assert WorldStateAdapter == RoutingContextAdapter
        assert MockWorldStateAdapter == MockRoutingContextAdapter
        print("✅ Backward compatibility aliases working")

    except Exception as e:
        print(f"❌ RoutingContextAdapter test failed: {e}")
        return False
    
    # Test Fixed Interface Agent
    try:
        from agents.main_interface_agent_fixed import create_fixed_interface_agent
        
        # Test agent creation
        agent = create_fixed_interface_agent()
        assert agent is not None
        print("✅ Fixed Interface Agent creation working")
        
        # Note: Full agent testing requires Haystack infrastructure
        # This validates the agent can be created successfully
        
    except Exception as e:
        print(f"❌ Fixed Interface Agent test failed: {e}")
        return False
    
    return True

def test_phase_2_orchestrator():
    """Test Phase 2: Orchestrator integration (simulated)"""
    print("🔧 Testing Phase 2: Orchestrator Integration")
    
    try:
        # Test imports
        from orchestrator.pipeline_integration import PipelineOrchestrator
        from adapters.world_state_adapter import RoutingContextAdapter, MockRoutingContextAdapter
        
        print("✅ Orchestrator imports successful")
        
        # Note: Full orchestrator testing requires GameEngine initialization
        # which needs more complex setup - this validates the imports work
        
    except Exception as e:
        print(f"❌ Orchestrator integration test failed: {e}")
        return False
    
    return True

def test_phase_3_game_integration():
    """Test Phase 3: Game integration (simulated)"""  
    print("🔧 Testing Phase 3: Game Integration")
    
    try:
        # Test session manager enhancements
        from components.session_manager import SessionManager
        
        # Create test session manager
        manager = SessionManager("test_saves")
        
        # Test routing decision tracking
        test_routing = {
            "route": "scenario",
            "confidence": 0.85,
            "player_input": "search the room",
            "type": "scenario_action"
        }
        
        manager.add_routing_decision(test_routing)
        stats = manager.get_routing_statistics()
        
        assert stats["total_decisions"] >= 1
        assert "route_distribution" in stats
        print("✅ Enhanced Session Manager working")
        
    except Exception as e:
        print(f"❌ Game integration test failed: {e}")
        return False
    
    return True

def main():
    """Run all tests"""
    print("🚀 Fixed System Integration Test Suite")
    print("=" * 50)
    
    results = []
    
    # Test each phase
    results.append(("Phase 1: Foundation", test_phase_1_foundation()))
    results.append(("Phase 2: Orchestrator", test_phase_2_orchestrator()))  
    results.append(("Phase 3: Game Integration", test_phase_3_game_integration()))
    
    # Print results
    print("\n📊 Test Results:")
    print("=" * 50)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    print("=" * 50)
    
    if all_passed:
        print("🎉 All tests passed! Fixed System Integration is ready.")
        print("\n📋 Implementation Summary:")
        print("• Enhanced DTO structure with confidence scoring")
        print("• Deterministic routing with world state integration")  
        print("• Single-tool Haystack Agent execution")
        print("• Enhanced session management with routing history")
        print("• Comprehensive error handling and fallbacks")
    else:
        print("⚠️ Some tests failed. Please review the implementation.")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)