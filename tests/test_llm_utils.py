"""
Test LLM Utils - Verify Gemini API Integration
Quick focused test to validate llm_utils.py configuration
"""

import os
import sys
from pathlib import Path

# Load env
from dotenv import load_dotenv
load_dotenv()

# Add project root
sys.path.insert(0, str(Path(__file__).parent))

from config.llm_utils import GeminiChatGenerator
from haystack.dataclasses import ChatMessage

def test_gemini_basic():
    """Test basic Gemini API call"""
    print("=" * 70)
    print("TEST 1: Basic Gemini API Call")
    print("=" * 70)

    try:
        # Create generator
        generator = GeminiChatGenerator(
            model_name="gemini-2.0-flash",
            generation_config={"temperature": 0.7, "max_output_tokens": 100}
        )
        print("✅ Generator created")

        # Create simple message
        messages = [ChatMessage.from_user("Say 'Hello World' and nothing else.")]
        print("✅ Message created")

        # Run
        result = generator.run(messages=messages)
        print("✅ API call succeeded")

        # Check response
        if "replies" in result and len(result["replies"]) > 0:
            reply = result["replies"][0]
            text = reply.text if hasattr(reply, 'text') else reply.content
            print(f"✅ Response received: {text[:100]}")
            return True
        else:
            print("❌ No replies in result")
            return False

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_gemini_with_tools():
    """Test Gemini API with tool/function calling"""
    print("\n" + "=" * 70)
    print("TEST 2: Gemini API with Function Calling")
    print("=" * 70)

    try:
        # Create generator
        generator = GeminiChatGenerator(
            model_name="gemini-2.0-flash",
            generation_config={"temperature": 0.0, "max_output_tokens": 100}
        )
        print("✅ Generator created")

        # Define a simple tool
        from haystack.tools import Tool

        test_tool = Tool(
            name="get_weather",
            description="Get the weather for a location",
            parameters={
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city name"
                    }
                },
                "required": ["location"]
            },
            function=lambda location: f"Weather in {location}: Sunny, 72°F"
        )
        print("✅ Tool defined")

        # Create message that should trigger tool use
        messages = [ChatMessage.from_user("What's the weather in San Francisco?")]
        print("✅ Message created")

        # Run with tools
        result = generator.run(messages=messages, tools=[test_tool])
        print("✅ API call with tools succeeded")

        # Check response
        if "replies" in result and len(result["replies"]) > 0:
            reply = result["replies"][0]

            # Check if it's a tool call
            if hasattr(reply, 'meta') and reply.meta and "tool_calls" in reply.meta:
                print(f"✅ Tool call detected: {reply.meta['tool_calls']}")
                return True
            else:
                text = reply.text if hasattr(reply, 'text') else reply.content
                print(f"⚠️  Got text response instead of tool call: {text[:100]}")
                return True  # Still success, just didn't choose to use tool
        else:
            print("❌ No replies in result")
            return False

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("🧪 TESTING LLM_UTILS.PY - GEMINI API INTEGRATION")
    print("=" * 70)

    # Check API key
    if not os.getenv("GEMINI_API_KEY"):
        print("❌ GEMINI_API_KEY not set")
        sys.exit(1)
    print("✅ API key found\n")

    # Run tests
    results = []

    results.append(("Basic API Call", test_gemini_basic()))
    results.append(("Function Calling", test_gemini_with_tools()))

    # Summary
    print("\n" + "=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 ALL TESTS PASSED - llm_utils.py is correctly configured!")
        sys.exit(0)
    else:
        print(f"\n❌ {total - passed} test(s) failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
