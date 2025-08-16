#!/usr/bin/env python3
"""
Test script to verify the input parsing and timeout fixes
"""

import time
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modular_dm_assistant_refactored import ModularDMAssistant

def test_scenario_option_selection():
    """Test that '1.' gets properly recognized as 'select option 1'."""
    print("🧪 Testing scenario option selection parsing...")
    
    # Initialize the DM assistant
    dm = ModularDMAssistant(
        verbose=False,
        enable_caching=False
    )
    
    try:
        # Start the system
        dm.start()
        time.sleep(2)
        
        # First generate a scenario to populate options
        print("📝 Generating scenario to set up options...")
        response = dm.process_dm_input("generate encounter")
        
        if "OPTIONS:" not in response:
            print("❌ Failed to generate scenario with options")
            return False
        
        print("✅ Scenario generated with options")
        
        # Now test that "1." gets recognized as option selection
        print("🎯 Testing input '1.' for option selection...")
        response = dm.process_dm_input("1.")
        
        # Should NOT contain RAG-related error messages
        if "Failed to process query" in response and "haystack_pipeline" in response:
            print("❌ TEST FAILED: '1.' was treated as RAG query instead of option selection")  
            print(f"Response: {response}")
            return False
        elif "SELECTED:" in response and "Option 1" in response:
            print("✅ TEST PASSED: '1.' correctly recognized as option selection")
            return True
        elif "Invalid option number" in response:
            print("⚠️ Input recognized as option selection but option invalid (expected)")
            return True
        else:
            print("⚠️ TEST UNCLEAR: Unexpected response format")
            print(f"Response: {response}")
            return False
            
    except Exception as e:
        print(f"❌ TEST ERROR: {e}")
        return False
    finally:
        try:
            dm.stop()
        except:
            pass

def test_haystack_timeout():
    """Test that haystack pipeline queries don't timeout."""
    print("\n🧪 Testing haystack pipeline timeout fix...")
    
    dm = ModularDMAssistant(
        verbose=False,
        enable_caching=False
    )
    
    try:
        dm.start()
        time.sleep(2)
        
        # Test a query that would go to haystack pipeline
        print("🎯 Testing general D&D query...")
        start_time = time.time()
        response = dm.process_dm_input("What are the rules for advantage in combat?")
        end_time = time.time()
        
        duration = end_time - start_time
        print(f"⏱️ Query completed in {duration:.2f} seconds")
        
        if "Failed to process query" in response and "timeout" in response.lower():
            print("❌ TEST FAILED: Still getting timeout errors")
            return False
        elif "No response received" in response:
            print("❌ TEST FAILED: Still getting 'No response received' errors")  
            return False
        elif len(response) > 50:  # Got a substantial response
            print("✅ TEST PASSED: Haystack query processed successfully")
            return True
        else:
            print("⚠️ TEST UNCLEAR: Short response received")
            print(f"Response: {response}")
            return False
            
    except Exception as e:
        print(f"❌ TEST ERROR: {e}")
        return False
    finally:
        try:
            dm.stop()
        except:
            pass

if __name__ == "__main__":
    print("🔬 Running Input Parsing and Timeout Fix Tests\n")
    
    test1_result = test_scenario_option_selection()
    test2_result = test_haystack_timeout()
    
    if test1_result and test2_result:
        print("\n🎉 All tests passed! Both fixes should resolve the issues.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. The fix may need further adjustment.")
        sys.exit(1)