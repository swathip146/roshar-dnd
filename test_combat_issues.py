#!/usr/bin/env python3
"""
Test script to debug Issue #6: Combat Turn Management Problems
"""
import sys
import os
import asyncio
import time

# Add current directory to path for imports
sys.path.insert(0, os.getcwd())

from modular_dm_assistant import ModularDMAssistant

async def test_combat_issues():
    """Test combat turn management and state synchronization"""
    print("=" * 60)
    print("TESTING ISSUE #6: COMBAT TURN MANAGEMENT")
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
        print("TEST 1: COMBAT INITIALIZATION AND STATE")
        print("="*50)
        
        # Test combat start
        print("--- Starting Combat ---")
        response = assistant.process_dm_input("start combat")
        print(f"Start response: {response[:200]}...")
        
        # Check initial state
        print("\n--- Checking Combat Status Immediately ---")
        response = assistant.process_dm_input("combat status")
        print(f"Status response: {response[:200]}...")
        
        print("\n" + "="*50)
        print("TEST 2: TURN ADVANCEMENT WITHOUT DELAY")
        print("="*50)
        
        # Try turn advancement immediately (should fail)
        print("--- Advancing Turn Immediately ---")
        response = assistant.process_dm_input("next turn")
        print(f"Turn response: {response}")
        
        # Check if it failed with "Combat is not active" or similar
        if "not active" in response.lower() or "failed" in response.lower():
            print("❌ Turn advancement failed as expected (timing issue)")
        else:
            print("✅ Turn advancement worked immediately")
        
        print("\n" + "="*50)
        print("TEST 3: TURN ADVANCEMENT WITH DELAY")
        print("="*50)
        
        # Wait a moment then try again
        print("--- Waiting 2 seconds then advancing turn ---")
        await asyncio.sleep(2)
        response = assistant.process_dm_input("next turn")
        print(f"Turn response after delay: {response}")
        
        if "active" in response.lower() or "now active" in response.lower():
            print("✅ Turn advancement worked after delay")
        else:
            print("❌ Turn advancement still failed")
        
        print("\n" + "="*50)
        print("TEST 4: MULTIPLE RAPID COMMANDS")
        print("="*50)
        
        # Test rapid succession of commands
        commands = ["combat status", "next turn", "combat status", "next turn"]
        
        for i, cmd in enumerate(commands):
            print(f"--- Command {i+1}: {cmd} ---")
            response = assistant.process_dm_input(cmd)
            success = ("status" in response.lower() and "combat" in response.lower()) or ("active" in response.lower())
            print(f"Success: {'✅' if success else '❌'}")
            print(f"Response preview: {response[:150]}...")
            
            # Small delay between commands
            await asyncio.sleep(0.5)
        
        print("\n" + "="*50)
        print("TEST 5: COMBAT STATE VALIDATION")
        print("="*50)
        
        # Test direct combat engine status
        if assistant.combat_agent:
            print("--- Testing Direct Combat Agent Communication ---")
            direct_response = assistant._send_message_and_wait("combat_engine", "get_combat_status", {})
            print(f"Direct agent response: {direct_response}")
        else:
            print("❌ Combat agent not available")
        
        # End combat
        print("\n--- Ending Combat ---")
        response = assistant.process_dm_input("end combat")
        print(f"End response: {response[:200]}...")
        
        # Stop the assistant
        assistant.stop()
        
        print("\n" + "="*60)
        print("COMBAT ISSUES TEST COMPLETED")
        print("="*60)
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_combat_issues())