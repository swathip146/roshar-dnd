#!/usr/bin/env python3
"""
Test script to check what actual scenario text is being generated
"""
import sys
import os
import asyncio
import time

# Add current directory to path for imports
sys.path.insert(0, os.getcwd())

from modular_dm_assistant import ModularDMAssistant

async def test_scenario_generation():
    """Test actual scenario generation to see what format we get"""
    print("=" * 60)
    print("TESTING ACTUAL SCENARIO GENERATION")
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
        
        # Test scenario generation
        test_queries = [
            "Generate a simple encounter with bandits",
            "Create a dungeon exploration scenario",
            "The party enters a mysterious forest"
        ]
        
        for i, query in enumerate(test_queries, 1):
            print(f"\n{'='*60}")
            print(f"TEST {i}: {query}")
            print('='*60)
            
            # Generate scenario
            response = assistant.process_dm_input(query)
            print(f"Response length: {len(response)} chars")
            print("-" * 40)
            print("FULL RESPONSE:")
            print(response)
            print("-" * 40)
            
            # Check what options were extracted
            if assistant.last_scenario_options:
                print(f"✅ OPTIONS EXTRACTED ({len(assistant.last_scenario_options)}):")
                for j, option in enumerate(assistant.last_scenario_options, 1):
                    print(f"  {j}: {repr(option)}")
            else:
                print("❌ NO OPTIONS EXTRACTED")
                
                # Try to debug by looking at the actual scenario text
                if "🎭 SCENARIO" in response:
                    # Extract just the scenario part
                    lines = response.split('\n')
                    scenario_lines = []
                    in_scenario = False
                    for line in lines:
                        if "🎭 SCENARIO" in line:
                            in_scenario = True
                            continue
                        elif in_scenario and line.strip().startswith("📝 *DM:"):
                            break
                        elif in_scenario:
                            scenario_lines.append(line)
                    
                    scenario_text = '\n'.join(scenario_lines).strip()
                    print(f"\nExtracted scenario text ({len(scenario_text)} chars):")
                    print(repr(scenario_text))
                    
                    # Test our extraction on this text
                    from debug_option_extraction import extract_and_store_options_debug
                    print("\nRunning extraction debug on actual text:")
                    extract_and_store_options_debug(scenario_text)
            
            print("\n" + "="*60)
            
            # Small delay between tests
            await asyncio.sleep(1)
        
        # Stop the assistant
        assistant.stop()
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_scenario_generation())