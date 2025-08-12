#!/usr/bin/env python3
"""
Quick test of the improved condition rule routing
"""
import sys
import os
import asyncio

sys.path.insert(0, os.getcwd())
from modular_dm_assistant import ModularDMAssistant

async def test_condition_fix():
    """Test improved condition routing"""
    print("Testing improved condition routing...")
    
    assistant = ModularDMAssistant(collection_name="dnd_documents", verbose=False)
    assistant.start()
    await asyncio.sleep(1)
    
    # Test queries that should now route consistently
    tests = [
        "what happens when poisoned",
        "poisoned condition", 
        "charmed condition",
        "what happens when stunned"
    ]
    
    for test in tests:
        response = assistant.process_dm_input(test)
        is_consistent = "CONDITION**" in response and len(response) < 300  # Short, direct format
        print(f"✅ {test}: {'Consistent' if is_consistent else 'Inconsistent'} format")
    
    assistant.stop()

if __name__ == "__main__":
    asyncio.run(test_condition_fix())