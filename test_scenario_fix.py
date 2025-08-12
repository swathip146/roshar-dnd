#!/usr/bin/env python3
"""
Test script to verify the scenario generation fix
"""
import sys
import os

# Add the current directory to the path so we can import modules
sys.path.insert(0, os.getcwd())

from modular_dm_assistant import ModularDMAssistant

def test_scenario_generation():
    """Test the scenario generation functionality"""
    print("🧪 Testing scenario generation fix...")
    
    try:
        # Initialize the assistant with default settings
        assistant = ModularDMAssistant(
            collection_name="dnd_documents",
            verbose=True,
            enable_caching=False,  # Disable caching for testing
            enable_async=False     # Disable async for simpler testing
        )
        
        # Start the orchestrator
        assistant.start()
        
        print("✅ Assistant initialized successfully")
        
        # Test the scenario generation command
        print("\n🎭 Testing 'introduce scenario' command...")
        response = assistant.process_dm_input("introduce scenario")
        
        print(f"\n📝 Response:")
        print(response)
        
        # Check if the response contains scenario content instead of cached rule info
        if "Based on the D&D rules provided" in response:
            print("\n❌ ISSUE: Still returning cached rule information instead of generating scenario")
            return False
        elif "SCENARIO" in response or "scenario" in response.lower():
            print("\n✅ SUCCESS: Scenario generation working correctly")
            return True
        else:
            print(f"\n❓ UNCLEAR: Unexpected response format")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False
    finally:
        # Clean up
        try:
            assistant.stop()
            print("\n🛑 Assistant stopped")
        except:
            pass

if __name__ == "__main__":
    success = test_scenario_generation()
    sys.exit(0 if success else 1)