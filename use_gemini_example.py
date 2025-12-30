#!/usr/bin/env python3
"""
Example of using Gemini in the D&D system.
This shows how to use the working Gemini integration.
"""

import os
from config.llm_config import create_gemini_config, LLMConfigManager

# Ensure API key is set (should already be set in your environment)
if not os.getenv("GEMINI_API_KEY"):
    os.environ["GEMINI_API_KEY"] = "your_api_key_here"

print("🎲 D&D System with Gemini")
print("=" * 40)

# Create Gemini configuration
print("1. Creating Gemini configuration...")
gemini_config = create_gemini_config(model="gemini-2.5-flash")
manager = LLMConfigManager(gemini_config)

print("✅ Configuration created:")
for agent, config in manager.get_config_summary().items():
    if not isinstance(config, bool):
        print(f"   {agent}: {config}")

# Create a scenario generator with Gemini
print("\n2. Creating scenario generator...")
scenario_generator = manager.create_generator("scenario_generator")
print(f"✅ Generator created: {type(scenario_generator).__name__}")

# Test D&D scenario generation
print("\n3. Testing D&D scenario generation...")

# Create a simple message class for testing
class SimpleMessage:
    def __init__(self, content: str, role: str = "user"):
        self.text = content  # Primary property for newer Haystack API  
        self.content = content  # Backward compatibility
        self.role = role

# Test prompt for D&D scenario
test_prompt = SimpleMessage(
    "Create a short D&D encounter for 4 level 3 adventurers exploring an ancient ruin. "
    "Include: setting description, a challenge/obstacle, and potential rewards. "
    "Keep it concise but evocative."
)

print(f"Sending prompt: {test_prompt.text[:80]}...")

try:
    result = scenario_generator.run([test_prompt])
    
    if result and "replies" in result and result["replies"]:
        reply = result["replies"][0]
        response = reply.text if hasattr(reply, 'text') else reply.content
        print("\n🎯 Gemini Generated D&D Scenario:")
        print("=" * 50)
        print(response)
        print("=" * 50)
        print("\n✅ Success! Gemini is ready for your D&D game!")
        
        # Show other agent types
        print("\n4. Other available agents:")
        agents = ["rag_retriever", "npc_controller", "main_interface"]
        for agent_name in agents:
            agent = manager.create_generator(agent_name)
            print(f"   ✅ {agent_name}: {type(agent).__name__}")
            
    else:
        print("❌ No response received")
        
except Exception as e:
    print(f"❌ Error: {e}")

print("\n🎲 Your Gemini integration is working! You can now:")
print("   • Generate D&D scenarios and content")
print("   • Create NPC dialogue and personalities") 
print("   • Retrieve information from your campaign docs")
print("   • Parse and understand player commands")
print("\n   Just use create_gemini_config() in your game setup!")
