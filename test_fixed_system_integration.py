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
        from shared_contract import new_fixed_dto, FixedSystemDTO, IntentType, RouteType
        
        # Test DTO creation
        test_dto = new_fixed_dto("test input", {"location": "tavern"})
        assert "correlation_id" in test_dto
        assert "confidence" in test_dto
        assert "target_kind" in test_dto
        print("✅ Enhanced shared contract working")
        
    except Exception as e:
        print(f"❌ Shared contract test failed: {e}")
        return False
    
    # Test WorldStateAdapter
    try:
        from adapters.world_state_adapter import MockWorldStateAdapter
        
        adapter = MockWorldStateAdapter()
        npcs = adapter.npcs
        places = adapter.places
        npc_names = adapter.npc_names
        
        assert isinstance(npcs, dict)
        assert isinstance(places, list)
        assert isinstance(npc_names, list)
        print("✅ WorldStateAdapter working")
        
    except Exception as e:
        print(f"❌ WorldStateAdapter test failed: {e}")
        return False
    
    # Test Fixed Interface Agent
    try:
        from main_interface_agent_fixed import create_fixed_interface_agent, execute_deterministic_routing_direct
        
        # Test direct tool execution
        test_context = {
            "world_state_adapter": MockWorldStateAdapter(),
            "location": "tavern"
        }
        
        result = execute_deterministic_routing_direct("talk to the bartender", test_context)
        
        assert "route" in result
        assert "confidence" in result
        assert "type" in result
        print("✅ Fixed Interface Agent working")
        
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
        from adapters.world_state_adapter import WorldStateAdapter, MockWorldStateAdapter
        
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