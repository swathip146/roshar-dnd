#!/usr/bin/env python3
"""
Test script to debug Issue #5: Condition Rules Format Problem
"""
import sys
import os
import asyncio
import time

# Add current directory to path for imports
sys.path.insert(0, os.getcwd())

from modular_dm_assistant import ModularDMAssistant

async def test_condition_rules():
    """Test condition rule lookup functionality"""
    print("=" * 60)
    print("TESTING ISSUE #5: CONDITION RULES FORMAT")
    print("=" * 60)
    
    try:
        # Initialize assistant
        assistant = ModularDMAssistant(
            collection_name="dnd_documents",
            verbose=True,
            enable_caching=False  # Disable caching to get fresh results
        )
        
        # Start the assistant
        assistant.start()
        
        # Wait a moment for initialization
        await asyncio.sleep(2)
        
        print("\n" + "="*50)
        print("TEST 1: CONDITION RULE QUERIES")
        print("="*50)
        
        # Test various condition rule queries
        condition_tests = [
            "what happens when poisoned",
            "rule poisoned",
            "check rule poisoned",
            "poisoned condition",
            "what happens when charmed",
            "rule charmed",
            "stunned condition",
            "what happens when paralyzed"
        ]
        
        for test_query in condition_tests:
            print(f"\n--- Testing: '{test_query}' ---")
            response = assistant.process_dm_input(test_query)
            print(f"Response length: {len(response)} chars")
            
            # Check if response contains expected format indicators
            has_rule_format = "RULE" in response.upper()
            has_condition_format = "CONDITION" in response.upper()
            has_effects = "effects" in response.lower() or "effect" in response.lower()
            
            print(f"  Contains 'RULE': {'✅' if has_rule_format else '❌'}")
            print(f"  Contains 'CONDITION': {'✅' if has_condition_format else '❌'}")
            print(f"  Contains effects info: {'✅' if has_effects else '❌'}")
            
            print("Response preview:")
            print(response[:300] + "..." if len(response) > 300 else response)
            print("-" * 40)
        
        print("\n" + "="*50)
        print("TEST 2: DIRECT CONDITION LOOKUP")
        print("="*50)
        
        # Test direct access to rule enforcement agent
        if assistant.rule_agent:
            print("Testing direct rule enforcement agent...")
            
            # Test condition lookup
            direct_response = assistant._send_message_and_wait("rule_enforcement", "get_condition_effects", {
                "condition_name": "poisoned"
            })
            
            print(f"Direct agent response: {direct_response}")
        else:
            print("❌ Rule enforcement agent not available")
        
        # Stop the assistant
        assistant.stop()
        
        print("\n" + "="*60)
        print("CONDITION RULES TEST COMPLETED")
        print("="*60)
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_condition_rules())