#!/usr/bin/env python3
"""
Test the critical fixes for Issues #3 and #4
"""
import sys
import os
import asyncio
import time

# Add current directory to path for imports
sys.path.insert(0, os.getcwd())

from modular_dm_assistant import ModularDMAssistant

async def test_critical_fixes():
    """Test the critical fixes for option extraction and player choice system"""
    print("=" * 60)
    print("TESTING CRITICAL FIXES - ISSUES #3 & #4")
    print("=" * 60)
    
    try:
        # Initialize assistant
        assistant = ModularDMAssistant(
            collection_name="test_dnd_documents",
            verbose=True,
            enable_caching=False  # Disable caching to get fresh results
        )
        
        # Start the assistant
        assistant.start()
        
        # Wait a moment for initialization
        await asyncio.sleep(2)
        
        print("\n" + "="*50)
        print("TEST 1: SCENARIO GENERATION WITH OPTIONS")
        print("="*50)
        
        # Test scenario generation
        response = assistant.process_dm_input("generate a bandit encounter")
        print("Response:")
        print(response)
        print(f"\nOptions extracted: {len(assistant.last_scenario_options) if assistant.last_scenario_options else 0}")
        if assistant.last_scenario_options:
            for i, opt in enumerate(assistant.last_scenario_options, 1):
                print(f"  {i}: {opt}")
        
        print("\n" + "="*50)
        print("TEST 2: FALLBACK SCENARIO (SIMULATED RAG FAILURE)")
        print("="*50)
        
        # Simulate a scenario that might cause RAG to fail
        # Clear options first to test fallback
        assistant.last_scenario_options = []
        response = assistant.process_dm_input("the party enters a mysterious forest")
        print("Response:")
        print(response)
        print(f"\nOptions extracted: {len(assistant.last_scenario_options) if assistant.last_scenario_options else 0}")
        if assistant.last_scenario_options:
            for i, opt in enumerate(assistant.last_scenario_options, 1):
                print(f"  {i}: {opt}")
        
        print("\n" + "="*50)
        print("TEST 3: PLAYER CHOICE SYSTEM")
        print("="*50)
        
        # Test option selection
        if assistant.last_scenario_options and len(assistant.last_scenario_options) >= 2:
            print("Testing option selection with available options...")
            response = assistant.process_dm_input("select option 2")
            print("Response:")
            print(response)
        else:
            print("Testing option selection without available options (should auto-generate)...")
            assistant.last_scenario_options = []  # Clear options
            response = assistant.process_dm_input("select option 1")
            print("Response:")
            print(response)
        
        print("\n" + "="*50)
        print("TEST 4: ENHANCED SCENARIO ROUTING")
        print("="*50)
        
        # Test improved scenario detection
        scenario_tests = [
            "create a tavern encounter",
            "the party encounters bandits",
            "dungeon exploration scenario",
            "mysterious ancient ruins"
        ]
        
        for test_query in scenario_tests:
            print(f"\nTesting: '{test_query}'")
            response = assistant.process_dm_input(test_query)
            is_scenario = "SCENARIO" in response
            has_options = len(assistant.last_scenario_options) > 0 if assistant.last_scenario_options else False
            print(f"  Scenario generated: {'✅' if is_scenario else '❌'}")
            print(f"  Options extracted: {'✅' if has_options else '❌'} ({len(assistant.last_scenario_options) if assistant.last_scenario_options else 0})")
        
        # Stop the assistant
        assistant.stop()
        
        print("\n" + "="*60)
        print("CRITICAL FIXES TEST COMPLETED")
        print("="*60)
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_critical_fixes())