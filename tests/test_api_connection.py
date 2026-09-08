"""
Diagnostic script to verify Gemini API access.

NOTE: This is a diagnostic SCRIPT, not a pytest module (despite the test_ name).
Everything must stay behind the __main__ guard — pytest imports every tests/*.py
during collection, and this file makes a live API call and calls sys.exit() at
import scope, which aborts the whole run with INTERNALERROR. (Plan item 0.8.)

Run directly:  python tests/test_api_connection.py
"""

import os
import sys


def main() -> int:
    from dotenv import load_dotenv

    load_dotenv()
    sys.path.insert(0, ".")

    print("=" * 70)
    print("TESTING GEMINI API CONNECTION")
    print("=" * 70)

    # Test 1: Check API key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY not found in environment")
        return 1
    print(f"✅ API key found: {api_key[:10]}...")

    # Test 2: Try to create client and call API
    try:
        import google.generativeai as genai

        print("\n✅ google-generativeai package imported")

        # Configure API
        genai.configure(api_key=api_key)
        print("✅ API configured")

        # Try a simple API call
        print("\n🔄 Attempting API call to Gemini...")
        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        response = model.generate_content("Say 'test successful'")

        print(f"✅ API call succeeded!")
        print(f"✅ Response: {response.text}")
        print("\n🎉 ALL TESTS PASSED - Gemini API is working correctly!")

    except Exception as e:
        print(f"\n❌ API call failed: {e}")
        print("\n" + "=" * 70)
        print("DIAGNOSIS:")
        print("=" * 70)

        error_str = str(e)

        if "403" in error_str or "Forbidden" in error_str or "ProxyError" in error_str:
            print("🔍 PROXY/FIREWALL BLOCKING ACCESS")
            print("")
            print("Your network is blocking access to:")
            print("  - generativelanguage.googleapis.com")
            print("")
            print("Solutions:")
            print("  1. Disable your proxy temporarily")
            print("  2. Configure proxy to allow Google AI API")
            print("  3. Contact your network administrator")
            print("")
            print("The CODE is correct. This is a NETWORK issue.")
        elif "401" in error_str or "Unauthorized" in error_str:
            print("🔍 API KEY INVALID")
            print("")
            print("Your Gemini API key is not valid.")
            print("Get a new one from: https://aistudio.google.com/apikey")
        else:
            print(f"🔍 UNKNOWN ERROR: {error_str}")

        import traceback
        print("\nFull traceback:")
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
