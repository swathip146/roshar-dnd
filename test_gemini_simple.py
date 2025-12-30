#!/usr/bin/env python3
"""
Simple Gemini API test - no Haystack dependencies.
This script tests just the basic Gemini functionality to verify your API key works.

Usage:
1. Set your GEMINI_API_KEY environment variable
2. Run: python test_gemini_simple.py
"""

import os
import sys


def main():
    """Simple Gemini test"""
    print("🧪 Simple Gemini API Test")
    print("=" * 40)
    
    # Test 1: Check google-generativeai package
    print("1. Testing google-generativeai import...")
    try:
        import google.generativeai as genai
        print("✅ google-generativeai imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import google-generativeai: {e}")
        print("   Install with: pip install google-generativeai")
        return 1
    
    # Test 2: Check API key
    print("\n2. Checking API key...")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY environment variable not set")
        print("   Set it with: export GEMINI_API_KEY=your_api_key_here")
        return 1
    
    print(f"✅ API key found (starts with: {api_key[:10]}...)")
    
    # Test 3: Configure and test Gemini
    print("\n3. Testing Gemini API connection...")
    try:
        # Configure the API
        genai.configure(api_key=api_key)
        
        # Create model
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        # Test prompt
        prompt = "Hello! Please respond with exactly: 'Gemini API is working correctly!'"
        
        print(f"Sending prompt: {prompt}")
        response = model.generate_content(prompt)
        
        if response.text:
            print("✅ Gemini API response received!")
            print(f"Response: {response.text}")
            
            if "working correctly" in response.text.lower():
                print("✅ Response content looks correct!")
            else:
                print("⚠️  Response content differs from expected, but API is working")
            
            return 0
        else:
            print("❌ No response text received")
            return 1
            
    except Exception as e:
        print(f"❌ Gemini API test failed: {e}")
        print(f"   Error type: {type(e).__name__}")
        
        # Check for common error types
        if "api key" in str(e).lower():
            print("   This looks like an API key issue. Check your key is valid.")
        elif "quota" in str(e).lower() or "limit" in str(e).lower():
            print("   This looks like a quota/rate limit issue. Try again later.")
        elif "not found" in str(e).lower():
            print("   The model might not be available. Try 'gemini-1.5-flash' instead.")
        else:
            print("   Check your internet connection and API key validity.")
        
        return 1


if __name__ == "__main__":
    result = main()
    if result == 0:
        print("\n🎉 All tests passed! Your Gemini API key is working correctly.")
        print("   You can now use Gemini in the D&D system.")
    else:
        print("\n❌ Tests failed. Fix the issues above before using Gemini.")
    
    sys.exit(result)
