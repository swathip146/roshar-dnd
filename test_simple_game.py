#!/usr/bin/env python3
"""
Test script for the simple D&D game
"""
from simple_dnd_game import SimpleDnDGame
import os

def test_basic_functionality():
    """Test basic game functionality"""
    print("🧪 Testing Simple D&D Game...")
    
    try:
        # Initialize game
        game = SimpleDnDGame()
        print(f"✅ Game initialized with location: {game.game_state['location']}")
        
        # Test game stats
        stats = game.get_game_stats()
        print(f"✅ Game stats: {stats}")
        
        # Test save/load functionality
        print("✅ Testing save functionality...")
        save_success = game.save_game("test_save.json")
        if save_success:
            print("✅ Save successful")
        
        # Test loading
        print("✅ Testing load functionality...")
        load_success = game.load_game("test_save.json")
        if load_success:
            print("✅ Load successful")
        
        # Test list saves
        saves = game.list_saves()
        print(f"✅ Found {len(saves)} save files: {saves}")
        
        # Clean up test save
        try:
            os.remove("saves/test_save.json")
            print("✅ Test cleanup completed")
        except:
            pass
        
        print("\n🎉 All basic functionality tests passed!")
        print("\n🎲 To run the game interactively:")
        print("python simple_dnd_game.py")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        print("Make sure hwtgenielib is properly configured")

if __name__ == "__main__":
    test_basic_functionality()