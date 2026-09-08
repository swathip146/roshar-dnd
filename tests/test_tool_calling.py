#!/usr/bin/env python
"""
Diagnostic script to verify Gemini tool calling works correctly.

NOTE: a SCRIPT, not a pytest module. pytest imports every tests/*.py during
collection; this made a live LLM call at import scope and hung collection.
Keep all execution behind __main__. (Plan item 0.8.)

Run directly:  python tests/test_tool_calling.py
"""
import os

# Ensure GEMINI_API_KEY is set in your environment

from haystack.dataclasses import ChatMessage
from haystack.tools import Tool
from config.llm_utils import GeminiChatGenerator

def test_function(text: str) -> str:
    """A simple test function"""
    return f"You said: {text}"

# Create a tool
test_tool = Tool(
    name="test_function",
    description="A test function that echoes back what you say",
    parameters={
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The text to echo back"
            }
        },
        "required": ["text"]
    },
    function=test_function
)

# Create generator
generator = GeminiChatGenerator(
    model_name="gemini-2.0-flash",
    generation_config={"temperature": 0.0}
)

# Create messages
messages = [
    ChatMessage.from_system("You are a helpful assistant. When the user asks you to echo something, use the test_function tool."),
    ChatMessage.from_user("Please echo 'Hello World'")
]

# Run with tools
print("=" * 60)


def main() -> int:
    if not os.getenv("GEMINI_API_KEY"):
        print("GEMINI_API_KEY environment variable must be set")
        return 1
    print("Testing Gemini with tool calling...")
    print("=" * 60)

    result = generator.run(messages=messages, tools=[test_tool])

    print("\n" + "=" * 60)
    print("RESULT:")
    print("=" * 60)
    for reply in result["replies"]:
        print(f"Role: {reply.role}")
        print(f"Content: {reply.content if hasattr(reply, 'content') else reply.text}")
        print()
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
