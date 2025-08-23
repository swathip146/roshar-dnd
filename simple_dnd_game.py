#!/usr/bin/env python3
"""
Simple D&D Game - Week 1 Implementation
Absolute simplest D&D game possible using hwtgenielib
"""
import json
import time
import os
from typing import Dict, List, Any, Optional
from hwtgenielib.components.generators.chat import AppleGenAIChatGenerator
from hwtgenielib.dataclasses import ChatMessage

class SimpleDnDGame:
    """Absolute simplest D&D game possible"""
    
    def __init__(self):
        """Initialize the simple D&D game"""
        self.chat_generator = AppleGenAIChatGenerator(
            model="aws:anthropic.claude-sonnet-4-20250514-v1:0"
        )
        self.game_state = {
            "location": "Tavern",
            "story": "You enter a bustling tavern filled with adventurers, merchants, and locals. The air is thick with pipe smoke and the aroma of roasted meat. A fire crackles in the hearth, casting dancing shadows on weathered faces.",
            "history": [],
            "player_name": "Adventurer",
            "created_time": time.time()
        }
        
        print("🎲 Simple D&D Game initialized!")
        print("📍 Starting location:", self.game_state["location"])
    
    def play_turn(self, player_input: str) -> str:
        """Single turn of D&D"""
        
        if not player_input.strip():
            return "The world waits for your action..."
        
        # Build simple prompt for D&D DM
        prompt = f"""You are a D&D Dungeon Master running a game for {self.game_state['player_name']}.

Current situation: {self.game_state['story']}
Location: {self.game_state['location']}
Recent history: {self._format_recent_history()}

Player says: "{player_input}"

Respond as a DM would:
1. Describe what happens next based on the player's action
2. Set up the scene and atmosphere 
3. Give the player 2-3 clear choices for what to do next
4. Keep it engaging, brief, and appropriate for D&D

Response:"""

        try:
            # Generate with hwtgenielib
            messages = [ChatMessage.from_user(prompt)]
            response = self.chat_generator.run(messages=messages)
            
            if response and "replies" in response:
                dm_response = response["replies"][0].text
                
                # Update simple state
                self.game_state["history"].append({
                    "player": player_input,
                    "dm": dm_response,
                    "timestamp": time.time(),
                    "location": self.game_state["location"]
                })
                
                # Simple location detection
                self._update_location_from_response(dm_response)
                
                return dm_response
            
        except Exception as e:
            print(f"❌ Error generating response: {e}")
            return self._fallback_response(player_input)
        
        return "The tavern keeper looks confused and shrugs..."
    
    def _format_recent_history(self) -> str:
        """Format recent history for context"""
        if not self.game_state["history"]:
            return "This is the beginning of your adventure."
        
        recent = self.game_state["history"][-3:]  # Last 3 interactions
        formatted = []
        for entry in recent:
            formatted.append(f"Player: {entry['player']}")
            formatted.append(f"DM: {entry['dm'][:100]}...")
        
        return "\n".join(formatted)
    
    def _update_location_from_response(self, dm_response: str):
        """Simple location detection from DM response"""
        dm_lower = dm_response.lower()
        
        # Simple keyword detection for common locations
        location_keywords = {
            "forest": "Forest",
            "woods": "Forest", 
            "dungeon": "Dungeon",
            "cave": "Cave",
            "town": "Town",
            "city": "City",
            "road": "Road",
            "inn": "Inn",
            "tavern": "Tavern",
            "shop": "Shop",
            "temple": "Temple",
            "castle": "Castle"
        }
        
        for keyword, location in location_keywords.items():
            if keyword in dm_lower and location != self.game_state["location"]:
                print(f"📍 Location changed: {self.game_state['location']} → {location}")
                self.game_state["location"] = location
                break
    
    def _fallback_response(self, player_input: str) -> str:
        """Fallback response when AI fails"""
        fallbacks = [
            "The ancient magic in the air seems to muffle your action. Try something else.",
            "A strange mist clouds your vision momentarily. What do you do next?",
            "The tavern keeper looks at you expectantly. Perhaps try a different approach?",
            "Time seems to slow as you consider your options. What's your next move?"
        ]
        
        import random
        return random.choice(fallbacks)
    
    def save_game(self, filename: str = "simple_save.json"):
        """Simple JSON save"""
        try:
            # Ensure saves directory exists
            os.makedirs("saves", exist_ok=True)
            filepath = os.path.join("saves", filename)
            
            save_data = {
                **self.game_state,
                "save_time": time.time(),
                "save_version": "1.0"
            }
            
            with open(filepath, "w") as f:
                json.dump(save_data, f, indent=2)
            
            print(f"💾 Game saved to {filepath}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to save game: {e}")
            return False
    
    def load_game(self, filename: str = "simple_save.json") -> bool:
        """Simple JSON load"""
        try:
            filepath = os.path.join("saves", filename)
            
            if not os.path.exists(filepath):
                print(f"❌ Save file not found: {filepath}")
                return False
            
            with open(filepath, "r") as f:
                loaded_data = json.load(f)
            
            # Restore game state
            self.game_state.update(loaded_data)
            
            print(f"📁 Game loaded from {filepath}")
            print(f"📍 Current location: {self.game_state['location']}")
            print(f"📜 History entries: {len(self.game_state['history'])}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to load game: {e}")
            return False
    
    def list_saves(self) -> List[str]:
        """List available save files"""
        saves_dir = "saves"
        if not os.path.exists(saves_dir):
            return []
        
        save_files = []
        for file in os.listdir(saves_dir):
            if file.endswith(".json"):
                save_files.append(file)
        
        return sorted(save_files)
    
    def get_game_stats(self) -> Dict[str, Any]:
        """Get current game statistics"""
        return {
            "location": self.game_state["location"],
            "turns_played": len(self.game_state["history"]),
            "session_time": time.time() - self.game_state["created_time"],
            "player_name": self.game_state["player_name"]
        }
    
    def run_interactive(self):
        """Run the interactive game loop"""
        print("=" * 50)
        print("🎲 SIMPLE D&D GAME")
        print("=" * 50)
        print("Welcome to the simplest D&D game possible!")
        print("Type 'help' for commands, 'quit' to exit")
        print("Type 'save' to save, 'load' to load")
        print()
        
        # Initial scene
        print("🎭 SCENE:")
        print(self.game_state["story"])
        print()
        
        while True:
            try:
                # Get player input
                player_input = input(f"{self.game_state['player_name']}> ").strip()
                
                if not player_input:
                    continue
                
                # Handle special commands
                if player_input.lower() in ["quit", "exit", "q"]:
                    print("👋 Thanks for playing! Goodbye!")
                    break
                
                elif player_input.lower() == "help":
                    self._show_help()
                    continue
                
                elif player_input.lower() == "save":
                    self.save_game()
                    continue
                
                elif player_input.lower() == "load":
                    saves = self.list_saves()
                    if not saves:
                        print("❌ No save files found.")
                        continue
                    
                    print("\n📁 Available saves:")
                    for i, save in enumerate(saves, 1):
                        print(f"{i}. {save}")
                    
                    try:
                        choice = input("Enter number to load (or press Enter to cancel): ").strip()
                        if choice and choice.isdigit():
                            idx = int(choice) - 1
                            if 0 <= idx < len(saves):
                                self.load_game(saves[idx])
                    except (ValueError, KeyboardInterrupt):
                        print("Load cancelled.")
                    continue
                
                elif player_input.lower() == "stats":
                    stats = self.get_game_stats()
                    print(f"\n📊 Game Stats:")
                    print(f"Location: {stats['location']}")
                    print(f"Turns: {stats['turns_played']}")
                    print(f"Session time: {stats['session_time']:.1f}s")
                    continue
                
                # Process turn
                print("\n🎲 Processing...")
                dm_response = self.play_turn(player_input)
                print(f"\n🎭 DM:")
                print(dm_response)
                print()
                
            except KeyboardInterrupt:
                print("\n\n👋 Game interrupted. Goodbye!")
                break
            except Exception as e:
                print(f"❌ Unexpected error: {e}")
    
    def _show_help(self):
        """Show help information"""
        print("\n📖 HELP:")
        print("This is a simple D&D game powered by AI.")
        print()
        print("Commands:")
        print("  help     - Show this help")
        print("  save     - Save the game")
        print("  load     - Load a saved game")
        print("  stats    - Show game statistics")
        print("  quit     - Exit the game")
        print()
        print("Gameplay:")
        print("- Type what you want to do in natural language")
        print("- The AI DM will respond and give you choices")
        print("- Be creative! Try things like:")
        print("  'I look around the tavern'")
        print("  'I talk to the bartender'")
        print("  'I check my pockets for gold'")
        print("  'I listen for rumors'")
        print()


def main():
    """Main function to run the simple D&D game"""
    print("🚀 Initializing Simple D&D Game...")
    
    try:
        game = SimpleDnDGame()
        game.run_interactive()
        
    except Exception as e:
        print(f"❌ Failed to start game: {e}")
        print("Make sure hwtgenielib is properly installed and configured.")


if __name__ == "__main__":
    main()