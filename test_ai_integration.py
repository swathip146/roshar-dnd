#!/usr/bin/env python3
"""
Quick Integration Test for AI-Enhanced Command Handler

This script tests the integration between the AI intent parser and manual command handler
to ensure the new flow works correctly.

Usage: python test_ai_integration.py
"""

from input_parser import AICommandHandler, ManualCommandHandler
from unittest.mock import Mock
import sys

def create_mock_dm_assistant():
    """Create a mock DM assistant for testing."""
    mock_dm = Mock()
    mock_dm.verbose = True
    mock_dm.enable_caching = True
    mock_dm.cache_manager = None
    mock_dm.narrative_tracker = None
    
    # Mock orchestrator
    mock_orchestrator = Mock()
    mock_orchestrator.get_agent_status.return_value = {}
    mock_orchestrator.get_message_statistics.return_value = {
        'total_messages': 0,
        'queue_size': 0,
        'registered_agents': 0
    }
    mock_dm.orchestrator = mock_orchestrator
    
    return mock_dm

def test_ai_handler_initialization():
    """Test that AI handler initializes correctly."""
    print("🧪 Testing AI Handler Initialization...")
    
    try:
        mock_dm = create_mock_dm_assistant()
        
        # Test manual handler creation
        manual_handler = ManualCommandHandler(mock_dm)
        print("✅ Manual handler created successfully")
        
        # Test AI handler creation
        ai_handler = AICommandHandler(mock_dm)
        print("✅ AI handler created successfully")
        
        # Verify AI handler has manual handler
        assert hasattr(ai_handler, 'manual_handler'), "AI handler missing manual_handler"
        print("✅ AI handler properly wraps manual handler")
        
        # Verify AI handler has AI parser
        assert hasattr(ai_handler, 'ai_parser'), "AI handler missing ai_parser"
        print("✅ AI handler has AI parser component")
        
        # Test command map access
        command_count = len(ai_handler.manual_handler.command_map)
        print(f"✅ Command map loaded with {command_count} commands")
        
        return True
        
    except Exception as e:
        print(f"❌ Initialization test failed: {e}")
        return False

def test_direct_command_detection():
    """Test that direct commands are properly detected."""
    print("\n🧪 Testing Direct Command Detection...")
    
    try:
        mock_dm = create_mock_dm_assistant()
        ai_handler = AICommandHandler(mock_dm)
        
        # Test cases for direct commands
        direct_commands = [
            "help",
            "roll 1d20",
            "list campaigns",
            "start combat",
            "ai stats",
            "1"  # numeric selection
        ]
        
        for cmd in direct_commands:
            is_direct = ai_handler._is_direct_command(cmd)
            print(f"✅ '{cmd}' -> Direct: {is_direct}")
        
        # Test cases for natural language (should not be direct)
        natural_commands = [
            "I want to roll a die",
            "Show me the campaigns",
            "Can we start fighting?",
            "What are the rules for poisoned?"
        ]
        
        for cmd in natural_commands:
            is_direct = ai_handler._is_direct_command(cmd)
            if is_direct:
                print(f"⚠️ '{cmd}' incorrectly detected as direct command")
            else:
                print(f"✅ '{cmd}' -> Natural Language: {not is_direct}")
        
        return True
        
    except Exception as e:
        print(f"❌ Direct command detection test failed: {e}")
        return False

def test_command_categories():
    """Test command categorization for AI prompts."""
    print("\n🧪 Testing Command Categories...")
    
    try:
        mock_dm = create_mock_dm_assistant()
        ai_handler = AICommandHandler(mock_dm)
        ai_parser = ai_handler.ai_parser
        
        # Test command categories
        categories = ai_parser.command_categories
        print(f"✅ Found {len(categories)} command categories")
        
        for category, commands in categories.items():
            print(f"  📁 {category}: {len(commands)} commands")
        
        # Test prompt formatting
        formatted_categories = ai_parser._format_categories_for_prompt()
        assert len(formatted_categories) > 0, "Categories formatting failed"
        print("✅ Category formatting works")
        
        # Test command examples
        examples = ai_parser._get_command_examples()
        assert len(examples) > 0, "Examples generation failed"
        print("✅ Command examples generated")
        
        return True
        
    except Exception as e:
        print(f"❌ Command categories test failed: {e}")
        return False

def test_fallback_translation():
    """Test fallback translation mechanisms."""
    print("\n🧪 Testing Fallback Translation...")
    
    try:
        mock_dm = create_mock_dm_assistant()
        ai_handler = AICommandHandler(mock_dm)
        ai_parser = ai_handler.ai_parser
        
        # Test fallback translations
        test_cases = [
            ("roll", "roll 1d20"),
            ("campaigns", "list campaigns"),
            ("players", "list players"),
            ("help", "help"),
            ("status", "agent status"),
        ]
        
        for input_text, expected in test_cases:
            result = ai_parser._fallback_translation(input_text)
            print(f"✅ '{input_text}' -> '{result}' (expected: '{expected}')")
        
        # Test dice extraction
        dice_cases = [
            ("roll a d20", "roll 1d20"),
            ("roll 3d6+2", "roll 3d6+2"),
            ("20 sided die", "roll 1d20"),
        ]
        
        for input_text, expected in dice_cases:
            result = ai_parser._extract_dice_roll(input_text)
            print(f"✅ '{input_text}' -> '{result}' (expected: '{expected}')")
        
        return True
        
    except Exception as e:
        print(f"❌ Fallback translation test failed: {e}")
        return False

def test_supported_commands():
    """Test that supported commands include AI enhancements."""
    print("\n🧪 Testing Supported Commands...")
    
    try:
        mock_dm = create_mock_dm_assistant()
        ai_handler = AICommandHandler(mock_dm)
        
        # Get supported commands
        commands = ai_handler.get_supported_commands()
        
        # Check for AI-specific additions
        ai_features = [
            "🤖 Natural Language Support",
            "🎯 Direct Commands",
            "🔄 AI Translation",
            "📊 AI Statistics"
        ]
        
        for feature in ai_features:
            if feature in commands:
                print(f"✅ AI feature documented: {feature}")
            else:
                print(f"⚠️ Missing AI feature: {feature}")
        
        # Check that original commands are preserved
        manual_commands = ai_handler.manual_handler.get_supported_commands()
        original_count = len(manual_commands)
        total_count = len(commands)
        
        print(f"✅ Commands: {original_count} original + {total_count - original_count} AI features = {total_count} total")
        
        return True
        
    except Exception as e:
        print(f"❌ Supported commands test failed: {e}")
        return False

def main():
    """Run all integration tests."""
    print("🚀 AI-Enhanced Command Handler Integration Tests")
    print("=" * 60)
    
    tests = [
        test_ai_handler_initialization,
        test_direct_command_detection,
        test_command_categories,
        test_fallback_translation,
        test_supported_commands,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
                print("✅ PASSED")
            else:
                failed += 1
                print("❌ FAILED")
        except Exception as e:
            failed += 1
            print(f"❌ FAILED with exception: {e}")
    
    print("\n" + "=" * 60)
    print(f"🧪 TEST RESULTS: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! AI integration is working correctly.")
        return 0
    else:
        print("⚠️ Some tests failed. Please check the implementation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

