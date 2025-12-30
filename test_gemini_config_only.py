#!/usr/bin/env python3
"""
Minimal test for Gemini configuration without heavy dependencies
"""

import os
import sys

def test_minimal_gemini():
    print("🧪 Minimal Gemini Configuration Test")
    print("=" * 40)
    
    # Check API key
    if not os.getenv("GEMINI_API_KEY"):
        print("❌ GEMINI_API_KEY not set")
        return False
    
    try:
        # Test 1: Basic Google AI import
        print("1. Testing Google AI import...")
        import google.generativeai as genai
        print("✅ google-generativeai imported")
        
        # Test 2: Basic LLM config
        print("2. Testing LLM config import...")
        from config.llm_config import LLMProvider, GEMINI_AVAILABLE
        print(f"✅ LLM config imported, GEMINI_AVAILABLE: {GEMINI_AVAILABLE}")
        
        # Test 3: Gemini config creation (no heavy dependencies)
        print("3. Testing Gemini config creation...")
        from config.llm_config import create_gemini_config
        gemini_config = create_gemini_config()
        print("✅ Gemini config created")
        print(f"   main_interface model: {gemini_config.main_interface.model}")
        
        # Test 4: Basic Gemini API test (lightweight)
        print("4. Testing basic Gemini API...")
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content("Hello")
        print(f"✅ Basic Gemini API works: {response.text[:50]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_minimal_gemini()
    if success:
        print("\n🎉 Minimal Gemini config test passed!")
        print("The issue is likely with Haystack agent creation, not Gemini config.")
    else:
        print("\n❌ Basic Gemini setup has issues.")
    
    sys.exit(0 if success else 1)



