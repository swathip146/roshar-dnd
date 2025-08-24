"""
Debug script to test AppleGenAI configuration directly
"""

import os
from haystack.dataclasses import ChatMessage

def test_apple_genai_direct():
    """Test AppleGenAI generator directly"""
    print("🧪 Testing AppleGenAI Direct Configuration")
    
    try:
        from hwtgenielib.components.generators.chat import AppleGenAIChatGenerator
        print("✅ AppleGenAI import successful")
        
        # Test with minimal configuration
        print("\n1. Testing with minimal config...")
        try:
            generator = AppleGenAIChatGenerator(model="aws:anthropic.claude-sonnet-4-20250514-v1:0")
            print(f"✅ Generator created: {type(generator).__name__}")
            
            # Try to inspect the generator
            print(f"   Model: {generator.model if hasattr(generator, 'model') else 'Unknown'}")
            
        except Exception as e:
            print(f"❌ Minimal config failed: {e}")
            return False
        
        # Test with API key from environment
        print("\n2. Testing with environment API key...")
        api_key = os.getenv("APPLE_GENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        if api_key:
            try:
                generator_with_key = AppleGenAIChatGenerator(
                    model="aws:anthropic.claude-sonnet-4-20250514-v1:0",
                    api_key=api_key
                )
                print(f"✅ Generator with API key created: {type(generator_with_key).__name__}")
            except Exception as e:
                print(f"❌ Config with API key failed: {e}")
        else:
            print("⚠️  No API key found in environment (APPLE_GENAI_API_KEY or OPENAI_API_KEY)")
        
        # Test a simple run
        print("\n3. Testing generator run...")
        try:
            test_message = ChatMessage.from_user("Hello, can you respond with just 'Working!'?")
            response = generator.run(messages=[test_message])
            print(f"✅ Generator run successful: {type(response)}")
            print(f"   Response keys: {list(response.keys()) if isinstance(response, dict) else 'Not a dict'}")
            
            # Try to extract the actual response
            if isinstance(response, dict):
                if 'replies' in response:
                    replies = response['replies']
                    if replies:
                        print(f"   First reply: {replies[0].text[:100]}...")
                
        except Exception as e:
            print(f"❌ Generator run failed: {e}")
            print(f"   Error type: {type(e).__name__}")
            
            # Check if it's an API-related error
            if "400" in str(e) or "Unsupported model" in str(e):
                print("   This appears to be a model/API configuration issue")
                
                # Try with a different model name
                print("\n4. Testing with alternative model names...")
                alternative_models = [
                    "claude-3-sonnet-20240229",
                    "claude-sonnet-3.5",
                    "anthropic/claude-sonnet-4-20250514-v1:0",
                    "gpt-4o-mini"  # Fallback
                ]
                
                for alt_model in alternative_models:
                    try:
                        print(f"   Trying model: {alt_model}")
                        alt_generator = AppleGenAIChatGenerator(model=alt_model)
                        alt_response = alt_generator.run(messages=[test_message])
                        print(f"   ✅ Success with {alt_model}")
                        break
                    except Exception as alt_e:
                        print(f"   ❌ Failed with {alt_model}: {type(alt_e).__name__}")
            else:
                raise e
        
        return True
        
    except ImportError as e:
        print(f"❌ AppleGenAI import failed: {e}")
        return False


def test_configuration_inspection():
    """Inspect AppleGenAI configuration options"""
    print("\n🔍 Inspecting AppleGenAI Configuration")
    
    try:
        from hwtgenielib.components.generators.chat import AppleGenAIChatGenerator
        
        # Try to inspect the class
        print(f"Class: {AppleGenAIChatGenerator}")
        print(f"MRO: {AppleGenAIChatGenerator.__mro__}")
        
        # Check __init__ signature
        import inspect
        sig = inspect.signature(AppleGenAIChatGenerator.__init__)
        print(f"__init__ signature: {sig}")
        
        # Check for class attributes/methods
        attrs = [attr for attr in dir(AppleGenAIChatGenerator) if not attr.startswith('_')]
        print(f"Public attributes: {attrs[:10]}...")  # Show first 10
        
    except Exception as e:
        print(f"❌ Configuration inspection failed: {e}")


if __name__ == "__main__":
    print("🐛 AppleGenAI Debug Script")
    print("=" * 50)
    
    # Test direct configuration
    success = test_apple_genai_direct()
    
    # Inspect configuration options
    test_configuration_inspection()
    
    # Environment check
    print("\n🌍 Environment Check")
    env_vars = ["APPLE_GENAI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"]
    for var in env_vars:
        value = os.getenv(var)
        status = "✅ Set" if value else "❌ Not set"
        print(f"   {var}: {status}")
    
    print(f"\nOverall success: {'✅ PASS' if success else '❌ FAIL'}")