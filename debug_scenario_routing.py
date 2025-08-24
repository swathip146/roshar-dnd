#!/usr/bin/env python3
"""
Debug Script: Test Scenario Pipeline Routing Fix
Tests if "I talk to the bartender" now properly routes to scenario pipeline
"""

import sys
import os
import time
import traceback

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.main_interface_agent import normalize_incoming, determine_response_routing
from orchestrator.pipeline_integration import create_full_haystack_orchestrator
from orchestrator.simple_orchestrator import GameRequest

def test_interface_routing():
    """Test that bartender interaction routes to scenario pipeline"""
    
    print("🔍 Testing Interface Agent Routing Logic")
    print("=" * 50)
    
    # Test input that was previously failing
    player_input = "I talk to the bartender"
    game_context = {"location": "Tavern", "character": "player"}
    
    print(f"Player Input: '{player_input}'")
    print(f"Game Context: {game_context}")
    
    try:
        # Step 1: Parse player input
        print("\n1️⃣ Parsing player input...")
        parsed_input = normalize_incoming(player_input, game_context)
        print(f"   Primary Intent: {parsed_input.get('primary_intent')}")
        print(f"   Target: {parsed_input.get('target')}")
        print(f"   Confidence: {parsed_input.get('confidence'):.2f}")
        print(f"   Complexity: {parsed_input.get('complexity')}")
        
        # Step 2: Determine routing
        print("\n2️⃣ Determining routing strategy...")
        routing = determine_response_routing(parsed_input, game_context)
        print(f"   Routing Strategy: {routing.get('routing_strategy')}")
        print(f"   Components Needed: {routing.get('components_needed')}")
        print(f"   Pipeline Type: {routing.get('pipeline_type')}")
        
        # Validate expected routing
        expected_routing = "scenario_pipeline"
        actual_routing = routing.get('routing_strategy')
        
        if actual_routing == expected_routing:
            print(f"\n✅ SUCCESS: Routing correctly set to '{expected_routing}'")
            return True
        else:
            print(f"\n❌ FAILURE: Expected '{expected_routing}', got '{actual_routing}'")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR in routing test: {e}")
        print(f"Full traceback: {traceback.format_exc()}")
        return False

def test_full_pipeline():
    """Test full pipeline execution with the bartender scenario"""
    
    print("\n🚀 Testing Full Pipeline Execution")
    print("=" * 50)
    
    try:
        # Create orchestrator
        orchestrator = create_full_haystack_orchestrator()
        
        # Create gameplay turn request
        request = GameRequest(
            request_type="gameplay_turn",
            data={
                "player_input": "I talk to the bartender",
                "actor": "player", 
                "context": {
                    "location": "Tavern",
                    "character": "player"
                }
            }
        )
        
        print("📤 Sending request to orchestrator...")
        start_time = time.time()
        
        response = orchestrator.process_request(request)
        
        processing_time = time.time() - start_time
        print(f"⏱️  Processing completed in {processing_time:.2f}s")
        
        # Analyze response
        print(f"\n📥 Response Analysis:")
        print(f"   Success: {response.success}")
        print(f"   Data Keys: {list(response.data.keys()) if response.data else 'None'}")
        
        if response.success and response.data:
            # Look for scenario content
            scenario_data = response.data.get('scenario') or response.data.get('response', '')
            print(f"   Response Text: '{scenario_data[:100]}{'...' if len(str(scenario_data)) > 100 else ''}'")
            
            # Check if it contains the old generic fallback
            generic_fallback = "You I talk to the bartender. The world responds accordingly."
            if generic_fallback in str(scenario_data):
                print(f"\n❌ FAILURE: Still using generic fallback response")
                return False
            elif scenario_data and len(str(scenario_data)) > 50:
                print(f"\n✅ SUCCESS: Generated rich scenario content")
                return True
            else:
                print(f"\n⚠️  WARNING: Response seems too short or empty")
                return False
        else:
            print(f"\n❌ FAILURE: Request unsuccessful or no data")
            print(f"   Error: {response.data.get('error') if response.data else 'Unknown error'}")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR in full pipeline test: {e}")
        print(f"Full traceback: {traceback.format_exc()}")
        return False

def main():
    """Run all routing tests"""
    
    print("🪲 DEBUG: Scenario Pipeline Routing Fix")
    print("Testing fix for bartender interaction routing")
    print("=" * 60)
    
    tests_passed = 0
    total_tests = 2
    
    # Test 1: Interface routing logic
    if test_interface_routing():
        tests_passed += 1
    
    # Test 2: Full pipeline execution  
    if test_full_pipeline():
        tests_passed += 1
    
    # Final results
    print("\n" + "=" * 60)
    print(f"📊 TEST RESULTS: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("✅ All tests passed! Scenario pipeline routing is fixed.")
        return True
    else:
        print("❌ Some tests failed. Scenario pipeline still has issues.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)