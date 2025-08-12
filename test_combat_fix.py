#!/usr/bin/env python3
"""
Quick test of the combat fixes for Issue #6
"""
import sys
import os
import asyncio

sys.path.insert(0, os.getcwd())
from modular_dm_assistant import ModularDMAssistant

async def test_combat_fix():
    """Test combat fixes"""
    print("Testing combat fixes...")
    
    assistant = ModularDMAssistant(collection_name="dnd_documents", verbose=False)
    assistant.start()
    await asyncio.sleep(1)
    
    # Test combat sequence
    print("1. Starting combat...")
    response = assistant.process_dm_input("start combat")
    combat_started = "COMBAT STARTED" in response
    print(f"   Combat started: {'✅' if combat_started else '❌'}")
    
    print("2. Checking combat status...")
    response = assistant.process_dm_input("combat status")
    has_combatants = "combatants" in response.lower() or len(response) > 50
    print(f"   Has combatants: {'✅' if has_combatants else '❌'}")
    
    print("3. Advancing turn...")
    response = assistant.process_dm_input("next turn")
    turn_advanced = "active" in response or "Current Turn" in response or "Now active" in response
    turn_failed = "Cannot advance turn" in response or "not active" in response
    print(f"   Turn advanced: {'✅' if turn_advanced else '❌'}")
    if not turn_advanced:
        print(f"   Full response: {response}")
    
    print("4. Ending combat...")
    response = assistant.process_dm_input("end combat")
    combat_ended = "COMBAT ENDED" in response
    print(f"   Combat ended: {'✅' if combat_ended else '❌'}")
    
    assistant.stop()
    
    all_passed = combat_started and has_combatants and turn_advanced and combat_ended
    print(f"\nOverall result: {'✅ All tests passed' if all_passed else '❌ Some tests failed'}")

if __name__ == "__main__":
    asyncio.run(test_combat_fix())