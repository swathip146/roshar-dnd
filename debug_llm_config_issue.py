#!/usr/bin/env python3
"""
Debug script to test the exact AppleGenAI configuration our LLM system is using
"""

from haystack.dataclasses import ChatMessage

def test_direct_vs_config_approach():
    """Compare direct AppleGenAI usage vs our config system approach"""
    
    print("🔍 DEBUGGING LLM CONFIG ISSUE")
    print("="*60)
    
    # Test 1: Direct approach (we know this works)
    print("\n1. Testing DIRECT approach (should work)...")
    try:
        from hwtgenielib.components.generators.chat import AppleGenAIChatGenerator
        
        direct_generator = AppleGenAIChatGenerator(model="aws:anthropic.claude-sonnet-4-20250514-v1:0")
        test_message = ChatMessage.from_user("Hello, respond with 'Direct works!'")
        direct_response = direct_generator.run(messages=[test_message])
        print(f"✅ Direct approach: SUCCESS")
        print(f"   Response: {direct_response['replies'][0].text[:50]}...")
        
    except Exception as e:
        print(f"❌ Direct approach failed: {e}")
        return
    
    # Test 2: With generation_kwargs (like our config system)
    print("\n2. Testing WITH generation_kwargs (like our system)...")
    try:
        generation_kwargs = {
            "temperature": 0.8,
            "max_tokens": 3000
        }
        
        config_generator = AppleGenAIChatGenerator(
            model="aws:anthropic.claude-sonnet-4-20250514-v1:0",
            generation_kwargs=generation_kwargs
        )
        
        test_message = ChatMessage.from_user("Hello, respond with 'Config works!'")
        config_response = config_generator.run(messages=[test_message])
        print(f"✅ Config approach: SUCCESS")
        print(f"   Response: {config_response['replies'][0].text[:50]}...")
        
    except Exception as e:
        print(f"❌ Config approach failed: {e}")
        print(f"   Error type: {type(e).__name__}")
        print(f"   Error details: {str(e)}")
        
        # Test with individual parameters
        print("\n3. Testing individual generation_kwargs parameters...")
        
        # Test with just temperature
        try:
            temp_only_generator = AppleGenAIChatGenerator(
                model="aws:anthropic.claude-sonnet-4-20250514-v1:0",
                generation_kwargs={"temperature": 0.8}
            )
            temp_response = temp_only_generator.run(messages=[test_message])
            print(f"✅ Temperature only: SUCCESS")
        except Exception as temp_e:
            print(f"❌ Temperature only failed: {temp_e}")
        
        # Test with just max_tokens
        try:
            tokens_only_generator = AppleGenAIChatGenerator(
                model="aws:anthropic.claude-sonnet-4-20250514-v1:0",
                generation_kwargs={"max_tokens": 3000}
            )
            tokens_response = tokens_only_generator.run(messages=[test_message])
            print(f"✅ Max tokens only: SUCCESS")
        except Exception as tokens_e:
            print(f"❌ Max tokens only failed: {tokens_e}")
        
        # Test with empty generation_kwargs
        try:
            empty_kwargs_generator = AppleGenAIChatGenerator(
                model="aws:anthropic.claude-sonnet-4-20250514-v1:0",
                generation_kwargs={}
            )
            empty_response = empty_kwargs_generator.run(messages=[test_message])
            print(f"✅ Empty generation_kwargs: SUCCESS")
        except Exception as empty_e:
            print(f"❌ Empty generation_kwargs failed: {empty_e}")


def test_our_actual_config_manager():
    """Test our actual LLMConfigManager to see what's happening"""
    
    print("\n4. Testing our ACTUAL LLMConfigManager...")
    
    try:
        from config.llm_config import LLMConfigManager, create_apple_genai_config
        
        # Create our config manager
        apple_config = create_apple_genai_config()
        manager = LLMConfigManager(apple_config)
        
        print(f"✅ Config manager created")
        print(f"   Config summary: {manager.get_config_summary()}")
        
        # Create a generator using our system
        scenario_generator = manager.create_generator("scenario_generator")
        print(f"✅ Generator created: {type(scenario_generator).__name__}")
        
        # Try to run it
        test_message = ChatMessage.from_user("Hello, respond with 'Manager works!'")
        manager_response = scenario_generator.run(messages=[test_message])
        print(f"✅ Manager approach: SUCCESS")
        print(f"   Response: {manager_response['replies'][0].text[:50]}...")
        
    except Exception as e:
        print(f"❌ Manager approach failed: {e}")
        print(f"   Error type: {type(e).__name__}")
        print(f"   Error details: {str(e)}")


if __name__ == "__main__":
    test_direct_vs_config_approach()
    test_our_actual_config_manager()
    
    print("\n" + "="*60)
    print("🏁 DEBUG COMPLETE")