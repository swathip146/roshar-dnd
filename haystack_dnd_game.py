"""
Haystack-Integrated D&D Game - Migrated from simple_dnd_game.py
Uses full Haystack architecture with orchestrator and pipeline integration
Maintains backward compatibility while adding sophisticated D&D mechanics
"""

import json
import time
import os
from typing import Dict, Any, Optional
from pathlib import Path

from orchestrator.pipeline_integration import create_full_haystack_orchestrator, GameRequest
from agents.scenario_generator_agent import create_fallback_scenario


class HaystackDnDGame:
    """
    Haystack-integrated D&D Game - Full Architecture Implementation
    Migrated from simple_dnd_game.py with enhanced capabilities
    """
    
    def __init__(self, policy_profile: str = "house"):
        """Initialize with full Haystack integration"""
        
        print("🚀 Initializing Haystack D&D Game...")
        
        # Core orchestrator with all Stage 3 components + Pipeline integration
        self.orchestrator = create_full_haystack_orchestrator()
        
        # Game state compatible with original simple_dnd_game.py
        self.game_state = {
            "location": "Tavern",
            "story": "You enter a bustling tavern filled with adventurers, merchants, and locals. The air is thick with pipe smoke and the aroma of roasted meat. A fire crackles in the hearth, casting dancing shadows on weathered faces.",
            "history": [],
            "player_name": "Adventurer", 
            "created_time": time.time(),
            "enhanced_features": True  # Flag to indicate Haystack features
        }
        
        # Initialize with a default character using the sophisticated character manager
        self._initialize_default_character()
        
        print("🎲 Haystack D&D Game initialized with full architecture!")
        print("📍 Starting location:", self.game_state["location"])
        print("🎯 Enhanced features: Orchestrator, Agents, Pipelines & Components")
    
    def _initialize_default_character(self):
        """Initialize default character using the character manager"""
        
        default_character = {
            "character_id": "player",
            "name": self.game_state["player_name"],
            "level": 1,
            "ability_scores": {
                "strength": 14,
                "dexterity": 12,
                "constitution": 13,
                "intelligence": 11,
                "wisdom": 15,
                "charisma": 10
            },
            "skills": {
                "perception": True,
                "investigation": True,
                "persuasion": True
            },
            "expertise_skills": [],
            "conditions": [],
            "features": []
        }
        
        # Add character through orchestrator
        char_request = GameRequest(
            request_type="character_add",
            data={"character_data": default_character}
        )
        
        try:
            response = self.orchestrator.process_request(char_request)
            if response.success:
                print(f"✅ Character '{default_character['name']}' initialized with sophisticated stats")
            else:
                print(f"⚠️ Character initialization had issues: {response.data}")
        except Exception as e:
            print(f"⚠️ Character manager not available: {e}")
    
    def play_turn(self, player_input: str) -> str:
        """
        Single turn of D&D - Enhanced with Haystack pipeline processing
        Maintains compatibility with original simple_dnd_game.py interface
        """
        
        if not player_input.strip():
            return "The world waits for your action..."
        
        try:
            # Enhanced processing with Haystack pipeline integration
            if self._should_use_enhanced_processing(player_input):
                return self._process_enhanced_turn(player_input)
            else:
                return self._process_simple_turn(player_input)
                
        except Exception as e:
            print(f"❌ Error processing turn: {e}")
            return self._fallback_response(player_input)
    
    def _should_use_enhanced_processing(self, player_input: str) -> bool:
        """Determine if input should use full Haystack pipeline processing"""
        
        # Triggers for enhanced processing
        enhanced_triggers = [
            "search", "investigate", "look for", "examine", "inspect",
            "talk to", "speak with", "ask", "tell", "persuade", "negotiate",
            "cast", "spell", "magic", "ability", "skill",
            "attack", "fight", "combat", "defend",
            "history", "lore", "legend", "knowledge", "research"
        ]
        
        input_lower = player_input.lower()
        return any(trigger in input_lower for trigger in enhanced_triggers)
    
    def _process_enhanced_turn(self, player_input: str) -> str:
        """Process turn using full Haystack pipeline integration"""
        
        # Create enhanced gameplay request
        request = GameRequest(
            request_type="gameplay_turn",
            data={
                "player_input": player_input,
                "actor": "player",
                "context": self._get_enhanced_context()
            }
        )
        
        try:
            # Process through Haystack pipeline orchestrator
            response = self.orchestrator.process_request(request)
            
            if response.success:
                result = self._format_enhanced_response(response.data)
                
                # Update game state with results
                self._update_game_state(player_input, result)
                
                return result.get("formatted_response", "The adventure continues...")
            else:
                error_msg = response.data.get("error", "Unknown error")
                print(f"⚠️ Enhanced processing failed: {error_msg}")
                return self._process_simple_turn(player_input)
                
        except Exception as e:
            print(f"⚠️ Pipeline error: {e}")
            return self._process_simple_turn(player_input)
    
    def _process_simple_turn(self, player_input: str) -> str:
        """Process turn using simple scenario generation (fallback/compatibility)"""
        
        # Create simple scenario request
        request = GameRequest(
            request_type="scenario_generation",
            data={
                "player_action": player_input,
                "game_context": {
                    "location": self.game_state["location"],
                    "difficulty": "medium",
                    "recent_history": self._format_recent_history()
                }
            }
        )
        
        try:
            response = self.orchestrator.process_request(request)
            
            if response.success and "scene" in response.data:
                scenario_data = response.data
                
                # Format response in original style
                dm_response = scenario_data.get("scene", "The scene unfolds...")
                
                # Add choices if available
                choices = scenario_data.get("choices", [])
                if choices:
                    dm_response += "\n\nYou could:"
                    for choice in choices[:3]:  # Limit to 3 choices
                        dm_response += f"\n• {choice.get('title', 'Take action')}: {choice.get('description', '')}"
                
                # Update game state
                self._update_game_state(player_input, scenario_data)
                
                return dm_response
            else:
                # Use fallback scenario generation
                fallback_scenario = create_fallback_scenario(player_input, {
                    "location": self.game_state["location"],
                    "difficulty": "medium"
                })
                
                dm_response = fallback_scenario.get("scene", "You consider your options...")
                self._update_game_state(player_input, fallback_scenario)
                
                return dm_response
                
        except Exception as e:
            print(f"⚠️ Scenario generation error: {e}")
            return self._fallback_response(player_input)
    
    def _get_enhanced_context(self) -> Dict[str, Any]:
        """Get enhanced context for Haystack processing"""
        
        return {
            "location": self.game_state["location"],
            "difficulty": "medium",
            "environment": {
                "lighting": "normal",
                "atmosphere": "tavern" if "tavern" in self.game_state["location"].lower() else "adventure"
            },
            "recent_history": self._format_recent_history(),
            "session_duration": time.time() - self.game_state["created_time"],
            "enhanced_mode": True,
            "average_party_level": 1  # Default for single player
        }
    
    def _format_enhanced_response(self, response_data: Dict[str, Any]) -> Dict[str, str]:
        """Format enhanced response data for display"""
        
        formatted_response = ""
        
        # Handle scenario-style responses
        if "scene" in response_data:
            formatted_response = response_data["scene"]
            
            # Add choices
            choices = response_data.get("choices", [])
            if choices:
                formatted_response += "\n\n📋 Available actions:"
                for choice in choices:
                    title = choice.get("title", "Action")
                    description = choice.get("description", "")
                    formatted_response += f"\n• {title}: {description}"
                    
        # Handle skill check results
        elif "skill_check_result" in response_data:
            skill_result = response_data["skill_check_result"]
            success = skill_result.get("success", False)
            total = skill_result.get("roll_total", 0)
            dc = skill_result.get("dc", 0)
            
            result_emoji = "✅" if success else "❌"
            formatted_response = f"{result_emoji} Skill Check: {total} vs DC {dc} - {'Success!' if success else 'Failure!'}"
            
            if "roll_breakdown" in skill_result:
                formatted_response += f"\n🎲 {skill_result['roll_breakdown']}"
                
        # Handle NPC responses
        elif "npc_response" in response_data:
            npc_data = response_data["npc_response"]
            dialogue = npc_data.get("dialogue", "The NPC responds...")
            formatted_response = f"💬 {dialogue}"
            
        # Handle general responses  
        elif "response" in response_data:
            formatted_response = response_data["response"]
            
        # Fallback
        else:
            formatted_response = "The adventure continues in ways you never expected..."
        
        return {
            "formatted_response": formatted_response,
            "raw_data": response_data
        }
    
    def _update_game_state(self, player_input: str, response_data: Dict[str, Any]):
        """Update game state with turn results (compatible with original)"""
        
        # Create history entry in original format
        history_entry = {
            "player": player_input,
            "dm": response_data.get("scene", response_data.get("formatted_response", "Response generated")),
            "timestamp": time.time(),
            "location": self.game_state["location"]
        }
        
        # Add enhanced data if available
        if "effects" in response_data:
            history_entry["effects"] = response_data["effects"]
        
        self.game_state["history"].append(history_entry)
        
        # Update location if effects indicate location change
        if "effects" in response_data:
            for effect in response_data["effects"]:
                if effect.get("type") == "location_change":
                    new_location = effect.get("value")
                    if new_location:
                        print(f"📍 Location changed: {self.game_state['location']} → {new_location}")
                        self.game_state["location"] = new_location
        
        # Simple location detection (compatible with original)
        if not response_data.get("effects"):
            self._update_location_from_response(history_entry["dm"])
    
    def _format_recent_history(self) -> str:
        """Format recent history for context (compatible with original)"""
        
        if not self.game_state["history"]:
            return "This is the beginning of your adventure."
        
        recent = self.game_state["history"][-3:]  # Last 3 interactions
        formatted = []
        
        for entry in recent:
            formatted.append(f"Player: {entry['player']}")
            dm_text = entry['dm']
            if len(dm_text) > 100:
                dm_text = dm_text[:100] + "..."
            formatted.append(f"DM: {dm_text}")
        
        return "\n".join(formatted)
    
    def _update_location_from_response(self, dm_response: str):
        """Simple location detection from DM response (original compatibility)"""
        
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
            "castle": "Castle",
            "library": "Library"
        }
        
        for keyword, location in location_keywords.items():
            if keyword in dm_lower and location != self.game_state["location"]:
                print(f"📍 Location changed: {self.game_state['location']} → {location}")
                self.game_state["location"] = location
                break
    
    def _fallback_response(self, player_input: str) -> str:
        """Fallback response when all systems fail (original compatibility)"""
        
        fallbacks = [
            "The ancient magic in the air seems to muffle your action. The world shifts around you as new possibilities emerge.",
            "A strange mist clouds your vision momentarily, but as it clears, the path forward becomes evident.",
            "Time seems to slow as you consider your options. The weight of adventure hangs in the air.",
            "The tavern keeper looks at you with knowing eyes, as if understanding the significance of your words."
        ]
        
        import random
        return random.choice(fallbacks)
    
    def save_game(self, filename: str = "haystack_save.json") -> bool:
        """Enhanced save with Haystack architecture data"""
        
        try:
            # Ensure saves directory exists
            os.makedirs("saves", exist_ok=True)
            filepath = os.path.join("saves", filename)
            
            # Get comprehensive game state from orchestrator
            orchestrator_status = self.orchestrator.get_pipeline_status()
            
            save_data = {
                # Original game state (backward compatibility)
                **self.game_state,
                "save_time": time.time(),
                "save_version": "2.0_haystack",
                
                # Enhanced Haystack data
                "orchestrator_status": orchestrator_status,
                "enhanced_features_active": True
            }
            
            # Try to get session data from orchestrator
            try:
                session_request = GameRequest("game_statistics", {})
                session_response = self.orchestrator.process_request(session_request)
                
                if session_response.success:
                    save_data["session_statistics"] = session_response.data
                    
            except Exception as e:
                print(f"⚠️ Could not save session statistics: {e}")
            
            with open(filepath, "w") as f:
                json.dump(save_data, f, indent=2)
            
            print(f"💾 Enhanced game saved to {filepath}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to save game: {e}")
            return False
    
    def load_game(self, filename: str = "haystack_save.json") -> bool:
        """Enhanced load with backward compatibility"""
        
        try:
            filepath = os.path.join("saves", filename)
            
            if not os.path.exists(filepath):
                print(f"❌ Save file not found: {filepath}")
                return False
            
            with open(filepath, "r") as f:
                loaded_data = json.load(f)
            
            # Restore game state (backward compatible)
            original_keys = ["location", "story", "history", "player_name", "created_time"]
            for key in original_keys:
                if key in loaded_data:
                    self.game_state[key] = loaded_data[key]
            
            # Check if this is an enhanced save
            if loaded_data.get("enhanced_features_active", False):
                print("📁 Loading enhanced Haystack save...")
                self.game_state["enhanced_features"] = True
                
                # Restore enhanced features if available
                if "session_statistics" in loaded_data:
                    print("📊 Session statistics restored")
            else:
                print("📁 Loading classic save file (enhanced features available)")
            
            print(f"📁 Game loaded from {filepath}")
            print(f"📍 Current location: {self.game_state['location']}")
            print(f"📜 History entries: {len(self.game_state['history'])}")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to load game: {e}")
            return False
    
    def list_saves(self) -> list:
        """List available save files (original compatibility)"""
        
        saves_dir = "saves"
        if not os.path.exists(saves_dir):
            return []
        
        save_files = []
        for file in os.listdir(saves_dir):
            if file.endswith(".json"):
                save_files.append(file)
        
        return sorted(save_files)
    
    def get_game_stats(self) -> Dict[str, Any]:
        """Enhanced game statistics using orchestrator"""
        
        try:
            # Get enhanced statistics from orchestrator
            stats_request = GameRequest("game_statistics", {})
            stats_response = self.orchestrator.process_request(stats_request)
            
            if stats_response.success:
                enhanced_stats = stats_response.data
                
                return {
                    # Original stats (compatibility)
                    "location": self.game_state["location"],
                    "turns_played": len(self.game_state["history"]),
                    "session_time": time.time() - self.game_state["created_time"],
                    "player_name": self.game_state["player_name"],
                    
                    # Enhanced stats
                    "enhanced_mode": True,
                    "orchestrator_stats": enhanced_stats,
                    "pipeline_status": self.orchestrator.get_pipeline_status()
                }
            else:
                # Fallback to original stats
                return self._get_original_stats()
                
        except Exception as e:
            print(f"⚠️ Could not get enhanced stats: {e}")
            return self._get_original_stats()
    
    def _get_original_stats(self) -> Dict[str, Any]:
        """Original statistics format (fallback)"""
        
        return {
            "location": self.game_state["location"],
            "turns_played": len(self.game_state["history"]),
            "session_time": time.time() - self.game_state["created_time"],
            "player_name": self.game_state["player_name"],
            "enhanced_mode": False
        }
    
    def run_interactive(self):
        """
        Enhanced interactive game loop 
        Maintains original interface with enhanced capabilities
        """
        
        print("=" * 70)
        print("🎲 HAYSTACK D&D GAME - Enhanced Architecture Edition")
        print("=" * 70)
        print("🚀 Powered by: Orchestrator, Agents, Pipelines & Components")
        print("📖 All original commands work, plus enhanced D&D mechanics!")
        print("Type 'help' for commands, 'quit' to exit")
        print()
        
        # Initial scene (enhanced)
        print("🎭 SCENE:")
        print(self.game_state["story"])
        
        # Show enhanced features available
        try:
            status = self.orchestrator.get_pipeline_status()
            if status.get("pipelines_enabled"):
                print("\n✨ Enhanced Features Active:")
                print("   • Intelligent scenario generation")
                print("   • Sophisticated skill checks with 7-step pipeline")
                print("   • Policy-driven rule mediation")
                print("   • Comprehensive decision logging")
                print("   • RAG-enhanced world knowledge")
        except:
            pass
        
        print()
        
        while True:
            try:
                # Get player input (same as original)
                player_input = input(f"{self.game_state['player_name']}> ").strip()
                
                if not player_input:
                    continue
                
                # Handle special commands (enhanced)
                if player_input.lower() in ["quit", "exit", "q"]:
                    print("👋 Thanks for playing the enhanced D&D experience! Goodbye!")
                    break
                
                elif player_input.lower() == "help":
                    self._show_enhanced_help()
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
                    print(f"\n📊 Enhanced Game Stats:")
                    print(f"Location: {stats['location']}")
                    print(f"Turns: {stats['turns_played']}")
                    print(f"Session time: {stats['session_time']:.1f}s")
                    if stats.get("enhanced_mode"):
                        print(f"Enhanced Features: ✅ Active")
                        if "orchestrator_stats" in stats:
                            orch_stats = stats["orchestrator_stats"]
                            if "game_statistics" in orch_stats:
                                game_stats = orch_stats["game_statistics"]
                                print(f"Skill Checks: {game_stats.get('total_skill_checks', 0)}")
                                print(f"Success Rate: {game_stats.get('success_rate', 0):.1%}")
                    continue
                
                # Process game turn (enhanced)
                print("\n🎲 Processing (Enhanced Pipeline)...")
                dm_response = self.play_turn(player_input)
                print(f"\n🎭 DM:")
                print(dm_response)
                print()
                
            except KeyboardInterrupt:
                print("\n\n👋 Enhanced game interrupted. Goodbye!")
                break
            except Exception as e:
                print(f"❌ Unexpected error: {e}")
                print("The enhanced architecture is handling this gracefully...")
    
    def _show_enhanced_help(self):
        """Enhanced help information"""
        
        print("\n📖 ENHANCED D&D GAME HELP:")
        print("This game combines the simplicity of the original with sophisticated D&D mechanics.")
        print()
        print("🎯 Enhanced Features:")
        print("  • Intelligent AI agents for creative responses")
        print("  • Sophisticated rule enforcement with D&D 5e mechanics")  
        print("  • Policy engine supporting RAW, House Rules, and Easy modes")
        print("  • Complete skill check system with dice rolling and modifiers")
        print("  • Multi-step saga workflows for complex interactions")
        print("  • Comprehensive decision logging and statistics")
        print("  • RAG-enhanced world knowledge and lore")
        print()
        print("📋 Commands:")
        print("  help     - Show this help")
        print("  save     - Save the game (enhanced format)")
        print("  load     - Load a saved game")
        print("  stats    - Show detailed statistics")
        print("  quit     - Exit the game")
        print()
        print("🎮 Enhanced Gameplay:")
        print("  • Try complex actions like 'search the ancient library for dragon lore'")
        print("  • Engage in detailed conversations: 'talk to the bartender about rumors'")
        print("  • Attempt skill-based actions: 'climb the castle wall stealthily'")
        print("  • Cast spells: 'cast fireball at the goblins'")
        print("  • The system will automatically determine appropriate skill checks!")
        print()
        print("🎲 Backward Compatibility:")
        print("  • All original simple_dnd_game.py commands still work")
        print("  • Save files from the original game can be loaded")
        print("  • Same interface, enhanced capabilities")
        print()


def main():
    """Main function to run the Haystack-integrated D&D game"""
    
    print("🚀 Initializing Enhanced D&D Game with Haystack Architecture...")
    
    try:
        game = HaystackDnDGame()
        game.run_interactive()
        
    except Exception as e:
        print(f"❌ Failed to start enhanced game: {e}")
        print("This may be due to missing dependencies or configuration issues.")
        print("Please ensure all Haystack components are properly installed.")
        
        # Fallback suggestion
        print("\n💡 Tip: You can still run the original simple_dnd_game.py for basic functionality.")


if __name__ == "__main__":
    main()