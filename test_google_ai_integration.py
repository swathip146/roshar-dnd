#!/usr/bin/env python3
"""
Test script to verify GoogleAIGeminiChatGenerator integration
"""

import os
import sys

def test_google_ai_integration():
    """Test if GoogleAIGeminiChatGenerator can be imported and used"""
    
    print("=== Testing Google AI Haystack Integration ===")
    
    # Test 1: Check if google_ai_haystack is available
    try:
        from google_ai_haystack import GoogleAIGeminiChatGenerator
        print("✅ GoogleAIGeminiChatGenerator import successful")
    except ImportError as e:
        print(f"❌ GoogleAIGeminiChatGenerator import failed: {e}")
        return False
    
    # Test 2: Check if API key is available
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY not set")
        return False
    print("✅ GEMINI_API_KEY is set")
    
    # Test 3: Try to create the generator
    try:
        generator = GoogleAIGeminiChatGenerator(
            model="gemini-2.5-flash",
            generation_config={"temperature": 0.5}
        )
        print("✅ GoogleAIGeminiChatGenerator created successfully")
    except Exception as e:
        print(f"❌ Failed to create GoogleAIGeminiChatGenerator: {e}")
        return False
    
    # Test 4: Check if it has the expected interface
    if hasattr(generator, 'run'):
        print("✅ Generator has 'run' method")
    else:
        print("❌ Generator missing 'run' method")
        return False
    
    print("🎉 All tests passed! GoogleAIGeminiChatGenerator is ready to use.")
    return True

def test_simple_generation():
    """Test simple text generation without tools"""
    
    print("\n=== Testing Simple Generation ===")
    
    try:
        from google_ai_haystack import GoogleAIGeminiChatGenerator
        
        generator = GoogleAIGeminiChatGenerator(
            model="gemini-2.5-flash",
            generation_config={"temperature": 0.5}
        )
        
        # Create a simple message
        class SimpleMessage:
            def __init__(self, content, role="user"):
                self.content = content
                self.role = role
        
        messages = [SimpleMessage("What is 2+2?")]
        
        # Test generation
        result = generator.run(messages=messages)
        print(f"✅ Generation successful: {result}")
        return True
        
    except Exception as e:
        print(f"❌ Generation test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_google_ai_integration()
    if success:
        test_simple_generation()
    else:
        print("❌ Basic integration test failed")
        sys.exit(1)

