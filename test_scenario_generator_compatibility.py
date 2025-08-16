#!/usr/bin/env python3
"""
Test ScenarioGeneratorAgent compatibility with agent framework
Verifies that the cleaned up implementation works without the backward compatibility class
"""
import sys
import os

# Add the current directory to the path so we can import the agents
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_scenario_generator_import():
    """Test that ScenarioGeneratorAgent can be imported without errors"""
    try:
        from agents.scenario_generator import ScenarioGeneratorAgent
        print("✅ ScenarioGeneratorAgent imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Failed to import ScenarioGeneratorAgent: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error importing ScenarioGeneratorAgent: {e}")
        return False

def test_scenario_generator_init():
    """Test that ScenarioGeneratorAgent can be initialized"""
    try:
        from agents.scenario_generator import ScenarioGeneratorAgent
        agent = ScenarioGeneratorAgent(verbose=True)
        print("✅ ScenarioGeneratorAgent initialized successfully")
        
        # Verify agent properties
        assert agent.agent_id == "scenario_generator"
        assert agent.agent_type == "ScenarioGenerator"
        print("✅ Agent properties are correct")
        
        # Verify handlers are registered
        expected_handlers = [
            "generate_scenario",
            "generate_with_context", 
            "apply_player_choice",
            "get_generator_status"
        ]
        
        for handler in expected_handlers:
            if handler not in agent.message_handlers:
                print(f"❌ Missing handler: {handler}")
                return False
        
        print(f"✅ All {len(expected_handlers)} handlers registered correctly")
        return True
        
    except Exception as e:
        print(f"❌ Failed to initialize ScenarioGeneratorAgent: {e}")
        return False

def test_backward_compatibility_removed():
    """Test that the old ScenarioGenerator class is no longer available"""
    try:
        from agents.scenario_generator import ScenarioGenerator
        print("❌ ScenarioGenerator class still exists - backward compatibility not fully removed")
        return False
    except ImportError:
        print("✅ ScenarioGenerator class successfully removed - no backward compatibility")
        return True
    except Exception as e:
        print(f"❌ Unexpected error testing backward compatibility removal: {e}")
        return False

def test_agent_framework_compatibility():
    """Test that the agent works with the agent framework"""
    try:
        from agent_framework import AgentOrchestrator
        from agents.scenario_generator import ScenarioGeneratorAgent
        
        # Create orchestrator
        orchestrator = AgentOrchestrator()
        
        # Create and register agent
        agent = ScenarioGeneratorAgent(verbose=False)
        orchestrator.register_agent(agent)
        
        # Verify registration
        status = orchestrator.get_agent_status()
        if "scenario_generator" not in status:
            print("❌ Agent not registered in orchestrator")
            return False
            
        agent_info = status["scenario_generator"]
        if agent_info["agent_type"] != "ScenarioGenerator":
            print("❌ Agent type mismatch")
            return False
            
        print("✅ Agent framework compatibility verified")
        return True
        
    except Exception as e:
        print(f"❌ Agent framework compatibility test failed: {e}")
        return False

def main():
    """Run all compatibility tests"""
    print("🧪 Testing ScenarioGeneratorAgent Compatibility")
    print("=" * 50)
    
    tests = [
        ("Import Test", test_scenario_generator_import),
        ("Initialization Test", test_scenario_generator_init),
        ("Backward Compatibility Removal Test", test_backward_compatibility_removed),
        ("Agent Framework Compatibility Test", test_agent_framework_compatibility)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}:")
        print("-" * 30)
        
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} PASSED")
            else:
                print(f"❌ {test_name} FAILED")
        except Exception as e:
            print(f"❌ {test_name} FAILED with exception: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 TEST RESULTS: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED - ScenarioGeneratorAgent is fully compatible!")
        return True
    else:
        print("⚠️ Some tests failed - please review the issues above")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)