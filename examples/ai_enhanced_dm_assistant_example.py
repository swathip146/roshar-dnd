#!/usr/bin/env python3
"""
Example: AI-Enhanced DM Assistant

This example demonstrates how to use the new AI-enhanced command handler
that translates natural language input into specific commands.

Flow: User Input -> AI Intent Parser -> Manual Command Handler

Usage:
    python examples/ai_enhanced_dm_assistant_example.py
"""

import sys
import os

# Add the parent directory to the path so we can import the DM assistant
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modular_dm_assistant_refactored import ModularDMAssistant
from input_parser import AICommandHandler

def main():
    """Main demonstration of AI-enhanced D&D assistant."""
    
    print("🤖 AI-Enhanced D&D Assistant Example")
    print("=====================================\n")
    
    # Initialize the DM assistant with AI command handler
    print("🚀 Initializing DM Assistant with AI command handler...")
    
    try:
        # Create AI command handler instance
        ai_handler = None  # Will be created by the assistant
        
        # Initialize the assistant with AI command handler
        dm_assistant = ModularDMAssistant(
            verbose=True,
            enable_caching=True,
            enable_async=True,
            command_handler=None  # Will default to manual, but we'll replace it
        )
        
        # Replace the default manual handler with AI handler after initialization
        ai_handler = AICommandHandler(dm_assistant)
        dm_assistant.command_handler = ai_handler
        
        # Start the assistant
        dm_assistant.start()
        
        print("\n✅ AI-Enhanced DM Assistant is ready!")
        print("💡 You can now use natural language commands!")
        
        # Example natural language commands to test
        example_commands = [
            "I want to roll a twenty sided die",
            "Show me what campaigns are available",
            "What players are in the game?",
            "I need some help with commands",
            "Can you start a combat encounter?",
            "Tell me the rules about being poisoned",
            "Create a mysterious forest encounter",
            "Let the party take a short rest",
        ]
        
        print("\n🎮 EXAMPLE NATURAL LANGUAGE COMMANDS:")
        print("=" * 50)
        
        for i, command in enumerate(example_commands, 1):
            print(f"\n💬 Example {i}: \"{command}\"")
            try:
                response = dm_assistant.command_handler.handle_command(command)
                print(f"🤖 Response: {response[:200]}{'...' if len(response) > 200 else ''}")
            except Exception as e:
                print(f"❌ Error: {e}")
        
        # Show AI statistics
        print("\n" + "=" * 50)
        print("📊 AI STATISTICS:")
        stats_response = ai_handler.handle_ai_specific_commands("ai stats")
        print(stats_response)
        
        # Interactive mode
        print("\n" + "=" * 50)
        print("🎮 INTERACTIVE MODE")
        print("Type natural language commands or 'quit' to exit")
        print("Try things like:")
        print("  - 'I want to roll 3 six sided dice'")
        print("  - 'Show me the party members'")
        print("  - 'Create an exciting tavern scene'")
        print("  - 'What are the rules for advantage?'")
        print("-" * 50)
        
        while True:
            try:
                user_input = input("\n🎭 DM> ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    break
                
                if not user_input:
                    continue
                
                # Process the command
                response = dm_assistant.command_handler.handle_command(user_input)
                print(f"\n{response}")
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
        
    except Exception as e:
        print(f"❌ Failed to initialize DM Assistant: {e}")
        return 1
    
    finally:
        # Clean shutdown
        print("\n🛑 Shutting down...")
        try:
            if 'dm_assistant' in locals():
                dm_assistant.stop()
            print("✅ Shutdown complete")
        except Exception as e:
            print(f"⚠️ Shutdown error: {e}")
    
    return 0

def compare_handlers():
    """Demonstrate the difference between manual and AI handlers."""
    
    print("\n🔄 COMPARISON: Manual vs AI Command Handlers")
    print("=" * 60)
    
    # Test commands
    test_cases = [
        {
            "natural": "I want to roll a twenty sided die",
            "manual": "roll 1d20",
            "description": "Dice rolling"
        },
        {
            "natural": "Show me what campaigns we have",
            "manual": "list campaigns",
            "description": "Campaign listing"
        },
        {
            "natural": "Can we start fighting?",
            "manual": "start combat",
            "description": "Combat initiation"
        },
        {
            "natural": "What are the rules about being charmed?",
            "manual": "rule charmed condition",
            "description": "Rule lookup"
        }
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n📝 Test Case {i}: {test['description']}")
        print(f"   Natural Language: \"{test['natural']}\"")
        print(f"   Manual Command:   \"{test['manual']}\"")
        print(f"   💡 AI Handler automatically translates natural -> manual!")

if __name__ == "__main__":
    try:
        # Run the comparison first
        compare_handlers()
        
        # Run the main example
        exit_code = main()
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)

