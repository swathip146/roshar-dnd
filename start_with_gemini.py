#!/usr/bin/env python3
"""
Start the D&D game with Gemini configuration
"""

import os
from config.llm_config import create_gemini_config, LLMConfigManager, set_global_config_manager

def main():
    print("🎲 Starting D&D Game with Gemini")
    print("=" * 40)
    
    # Verify API key
    if not os.getenv("GEMINI_API_KEY"):
        print("❌ Error: GEMINI_API_KEY environment variable not set")
        print("Please set it with: export GEMINI_API_KEY=your_api_key_here")
        return
    
    print("✅ API Key found")
    
    # Create Gemini configuration
    print("📝 Creating Gemini configuration...")
    try:
        gemini_config = create_gemini_config(model="gemini-2.5-flash")
        manager = LLMConfigManager(gemini_config)
        set_global_config_manager(manager)
        print("✅ Gemini configuration set")
        
        # Show configuration summary
        config_summary = manager.get_config_summary()
        for agent, config in config_summary.items():
            if not isinstance(config, bool):
                print(f"   {agent}: {config}")
                
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return
    
    # Start the game
    print("\n🎮 Starting game...")
    try:
        from haystack_dnd_game import HaystackDnDGame
        from core.game_initialization import initialize_enhanced_dnd_game
        
        # Initialize game with enhanced setup system
        config = initialize_enhanced_dnd_game()
        
        # Create and run game with configuration
        game = HaystackDnDGame(config=config)
        game.run_interactive()
    except Exception as e:
        print(f"❌ Game startup error: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    main()
