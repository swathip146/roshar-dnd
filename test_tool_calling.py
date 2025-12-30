#!/usr/bin/env python
"""
Test script to verify Gemini tool calling works correctly
"""
import os

# Ensure GEMINI_API_KEY is set in your environment
if not os.getenv("GEMINI_API_KEY"):
    raise ValueError("GEMINI_API_KEY environment variable must be set")

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
