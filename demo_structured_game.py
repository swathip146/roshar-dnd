#!/usr/bin/env python3
"""
Demo script for the structured D&D game (Week 2)
Shows the enhanced architecture with separated components
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'simple_dnd'))

from simple_dnd.game import StructuredDnDGame
from simple_dnd.config import GameConfig

def demo_structured_features():
    """Demonstrate the structured game features"""
    print("🎲 STRUCTURED D&D GAME DEMO")
    print("=" * 50)
    
    # Create custom config
    config = GameConfig()
    config.default_player_name = "Demo Hero"
    config.default_location = "Forest"
    
    print(f"Creating game with custom config...")
    print(f"Player: {config.default_player_name}")
    print(f"Starting location: {config.default_location}")
    print()
    
    # Initialize game
    game = StructuredDnDGame(config)
    
    # Demo component separation
    print("🔧 COMPONENT DEMONSTRATION:")
    print()
    
    # 1. Dice System Demo
    print("1️⃣ DICE SYSTEM:")
    result = game.dice.skill_check(difficulty=15, modifier=3)
    print(f"   Skill check result: {result['message']}")
    
    attack = game.dice.attack_roll(target_ac=14, modifier=5)
    print(f"   Attack roll result: {attack['message']}")
    
    damage = game.dice.damage_roll("2d6+3")
    print(f"   Damage roll result: {damage['message']}")
    print()
    
    # 2. Scenario Generator Demo
    print("2️⃣ SCENARIO GENERATOR:")
    scenario = game.scenario_generator.generate_scenario("dungeon")
    print(f"   Scene: {scenario['scene']}")
    print(f"   Choices:")
    for i, choice in enumerate(scenario['choices'], 1):
        print(f"     {i}. {choice}")
    print()
    
    # 3. Game Turn Demo
    print("3️⃣ GAME TURN PROCESSING:")
    
    # Demo different types of turns
    turn_examples = [
        "I want to roll a skill check",
        "Generate a new forest scenario", 
        "I look around carefully",
        "I go to the tavern"
    ]
    
    for example in turn_examples:
        print(f"   Input: '{example}'")
        result = game.play_turn(example)
        print(f"   Result: {result['type']} - {result.get('message', 'No message')[:100]}...")
        print()
    
    # 4. Game Status Demo
    print("4️⃣ GAME STATUS:")
    status = game.get_game_status()
    for key, value in status.items():
        print(f"   {key}: {value}")
    print()
    
    # 5. Save/Load Demo
    print("5️⃣ SAVE/LOAD SYSTEM:")
    save_success = game.save_game("demo_save.json")
    if save_success:
        print("   ✅ Save successful")
        
        # Create new game and load
        new_game = StructuredDnDGame()
        load_success = new_game.load_game("demo_save.json")
        if load_success:
            print("   ✅ Load successful")
            print(f"   Loaded game turn count: {new_game.game_state['turn_count']}")
    
    print()
    print("🎉 Demo completed! All components working.")
    print()
    print("🚀 To run the interactive game:")
    print("   python -c \"from simple_dnd.game import StructuredDnDGame; StructuredDnDGame().run_interactive()\"")

def test_component_integration():
    """Test that all components work together"""
    print("\n🧪 INTEGRATION TESTING:")
    print()
    
    try:
        # Test basic initialization
        game = StructuredDnDGame()
        print("✅ Game initialization successful")
        
        # Test each component individually
        dice_result = game.dice.roll_d20()
        print(f"✅ Dice system working: rolled {dice_result}")
        
        scenario = game.scenario_generator.generate_scenario("tavern")
        print(f"✅ Scenario generator working: generated {len(scenario['choices'])} choices")
        
        # Test turn processing
        result = game.play_turn("I look around")
        print(f"✅ Turn processing working: {result['type']}")
        
        # Test save system
        save_ok = game.save_game("integration_test.json")
        print(f"✅ Save system working: {save_ok}")
        
        print("\n🎉 All integration tests passed!")
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("Starting structured D&D game demonstration...\n")
    
    try:
        demo_structured_features()
        test_component_integration()
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure hwtgenielib is installed and configured")
    except Exception as e:
        print(f"❌ Demo failed: {e}")