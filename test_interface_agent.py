#!/usr/bin/env python3
"""
Test script to isolate interface agent creation issues.
"""

import os
import sys

def test_interface_agent_creation():
    """Test interface agent creation step by step"""
    print("🧪 Testing Interface Agent Creation")
    print("=" * 50)
    
    # Step 1: Test Gemini config creation
    try:
        print("1. Testing Gemini config creation...")
        from config.llm_config import create_gemini_config, LLMConfigManager, set_global_config_manager
        
        gemini_config = create_gemini_config()
        print("✅ Gemini config created successfully")
        print(f"   main_interface provider: {gemini_config.main_interface.provider}")
        print(f"   main_interface model: {gemini_config.main_interface.model}")
        
    except Exception as e:
        print(f"❌ Gemini config creation failed: {e}")
        return False
    
    # Step 2: Test LLM config manager creation
    try:
        print("\n2. Testing LLM config manager creation...")
        manager = LLMConfigManager(gemini_config)
        print("✅ LLM config manager created successfully")
        
    except Exception as e:
        print(f"❌ LLM config manager creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 3: Test setting global config manager
    try:
        print("\n3. Testing global config manager setup...")
        set_global_config_manager(manager)
        print("✅ Global config manager set successfully")
        
    except Exception as e:
        print(f"❌ Global config manager setup failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 4: Test generator creation for main_interface
    try:
        print("\n4. Testing main_interface generator creation...")
        interface_generator = manager.create_generator("main_interface")
        print(f"✅ Interface generator created: {type(interface_generator).__name__}")
        
    except Exception as e:
        print(f"❌ Interface generator creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 5: Test interface agent creation
    try:
        print("\n5. Testing interface agent creation...")
        from agents.main_interface_agent_fixed import create_fixed_interface_agent
        
        interface_agent = create_fixed_interface_agent()
        print(f"✅ Interface agent created: {type(interface_agent).__name__}")
        
    except Exception as e:
        print(f"❌ Interface agent creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 6: Test basic agent functionality
    try:
        print("\n6. Testing basic agent functionality...")
        from haystack.dataclasses import ChatMessage
        
        test_message = ChatMessage.from_user("test input")
        
        # Don't actually run the agent, just check if it has the right structure
        if hasattr(interface_agent, 'run'):
            print("✅ Agent has run method")
        else:
            print("❌ Agent missing run method")
        
        if hasattr(interface_agent, 'tools'):
            print(f"✅ Agent has {len(interface_agent.tools)} tools")
        else:
            print("❌ Agent missing tools")
            
    except Exception as e:
        print(f"❌ Basic agent functionality test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n🎉 All interface agent tests passed!")
    return True

if __name__ == "__main__":
    # Set API key if not already set
    if not os.getenv("GEMINI_API_KEY"):
        print("❌ GEMINI_API_KEY not set. Please set it first.")
        sys.exit(1)
    
    success = test_interface_agent_creation()
    sys.exit(0 if success else 1)



