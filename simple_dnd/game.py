#!/usr/bin/env python3
"""
Main game class for Week 2 structured D&D game
Enhanced version of simple_dnd_game.py with better organization
"""
import json
import time
import os
from typing import Dict, List, Any, Optional
from .scenario_generator import SimpleScenarioGenerator
from .dice import SimpleDice
from .config import GameConfig, DEFAULT_CONFIG

class StructuredDnDGame:
    """Structured D&D game with separated components"""
    
    def __init__(self, config: Optional[GameConfig] = None):
        """Initialize the structured game"""
        self.config = config or DEFAULT_CONFIG
        
        # Initialize components
        self.scenario_generator = SimpleScenarioGenerator(self.config)
        self.dice = SimpleDice(self.config)
        
        # Game state
        self.game_state = {
            "location": self.config.default_location,
            "story": self.config.default_story,
            "history": [],
            "player_name": self.config.default_player_name,
            "created_time": time.time(),
            "turn_count": 0
        }
        
        # Ensure saves directory exists
        os.makedirs(self.config.saves_directory, exist_ok=True)
        
        print("🎲 Structured D&D Game initialized!")
        print(f"📍 Starting location: {self.game_state['location']}")
    
    def play_turn(self, player_input: str) -> Dict[str, Any]:
        """Play a single turn and return structured result"""
        
        if not player_input.strip():
            return {"success": False, "message": "Please provide an action."}
        
        self.game_state["turn_count"] += 1
        
        # Check if player is asking for a dice roll
        if self._is_dice_command(player_input):
            return self._handle_dice_command(player_input)
        
        # Check if player is asking for scenario generation
        if self._is_scenario_command(player_input):
            return self._handle_scenario_command(player_input)
        
        # Default: generate scenario-based response
        return self._handle_general_action(player_input)
    
    def _is_dice_command(self, input_text: str) -> bool:
        """Check if input is a dice command"""
        dice_keywords = ["roll", "dice", "d20", "check", "skill check"]
        return any(keyword in input_text.lower() for keyword in dice_keywords)
    
    def _is_scenario_command(self, input_text: str) -> bool:
        """Check if input is asking for a new scenario"""
        scenario_keywords = ["new scenario", "generate", "what happens", "continue story"]
        return any(keyword in input_text.lower() for keyword in scenario_keywords)
    
    def _handle_dice_command(self, input_text: str) -> Dict[str, Any]:
        """Handle dice rolling commands"""
        try:
            # Simple skill check
            if "skill check" in input_text.lower() or "check" in input_text.lower():
                result = self.dice.skill_check()
                
                self._record_action(input_text, f"🎲 Skill Check: {result['message']}")
                
                return {
                    "success": True,
                    "type": "skill_check",
                    "message": result["message"],
                    "roll_data": result,
                    "turn": self.game_state["turn_count"]
                }
            
            # Simple d20 roll
            elif "d20" in input_text.lower() or "roll" in input_text.lower():
                roll = self.dice.roll_d20()
                message = f"🎲 Rolled d20: {roll}"
                
                self._record_action(input_text, message)
                
                return {
                    "success": True,
                    "type": "dice_roll",
                    "message": message,
                    "roll": roll,
                    "turn": self.game_state["turn_count"]
                }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Dice roll failed: {e}",
                "turn": self.game_state["turn_count"]
            }
    
    def _handle_scenario_command(self, input_text: str) -> Dict[str, Any]:
        """Handle scenario generation commands"""
        try:
            # Extract context from input or use current location
            context = self._extract_context_from_input(input_text)
            
            scenario = self.scenario_generator.generate_scenario(context)
            
            # Update game state
            self.game_state["location"] = context
            scenario_text = f"🎭 {scenario['scene']}\n\nChoices:\n"
            for i, choice in enumerate(scenario['choices'], 1):
                scenario_text += f"{i}. {choice}\n"
            
            self._record_action(input_text, scenario_text)
            
            return {
                "success": True,
                "type": "scenario",
                "message": scenario_text,
                "scenario_data": scenario,
                "turn": self.game_state["turn_count"]
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Scenario generation failed: {e}",
                "turn": self.game_state["turn_count"]
            }
    
    def _handle_general_action(self, input_text: str) -> Dict[str, Any]:
        """Handle general player actions"""
        try:
            # For general actions, generate a contextual response
            context = self.game_state["location"].lower()
            
            # Simple response based on common actions
            if "look" in input_text.lower() or "examine" in input_text.lower():
                scenario = self.scenario_generator.generate_scenario(context)
                response = f"🔍 Looking around: {scenario['scene']}"
                
            elif "talk" in input_text.lower() or "speak" in input_text.lower():
                response = "💬 You start a conversation. The person responds thoughtfully..."
                
            elif "move" in input_text.lower() or "go" in input_text.lower():
                new_context = self._extract_movement_target(input_text)
                if new_context:
                    self.game_state["location"] = new_context
                    scenario = self.scenario_generator.generate_scenario(new_context)
                    response = f"🚶 You travel to {new_context}. {scenario['scene']}"
                else:
                    response = "🚶 You move around, taking in your surroundings..."
                    
            else:
                # Generate contextual scenario for the action
                scenario = self.scenario_generator.generate_scenario(context)
                response = f"⚡ {scenario['scene']}\n\nWhat do you do next?"
            
            self._record_action(input_text, response)
            
            return {
                "success": True,
                "type": "general_action",
                "message": response,
                "turn": self.game_state["turn_count"]
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Action failed: {e}",
                "turn": self.game_state["turn_count"]
            }
    
    def _extract_context_from_input(self, input_text: str) -> str:
        """Extract location context from player input"""
        input_lower = input_text.lower()
        
        # Check for location keywords
        location_map = {
            "tavern": "tavern",
            "forest": "forest", 
            "woods": "forest",
            "dungeon": "dungeon",
            "cave": "cave",
            "town": "town",
            "city": "town",
            "road": "road"
        }
        
        for keyword, location in location_map.items():
            if keyword in input_lower:
                return location
        
        # Default to current location
        return self.game_state["location"].lower()
    
    def _extract_movement_target(self, input_text: str) -> Optional[str]:
        """Extract movement target from input"""
        input_lower = input_text.lower()
        
        movement_targets = ["forest", "tavern", "dungeon", "town", "cave", "road"]
        
        for target in movement_targets:
            if target in input_lower:
                return target.title()
        
        return None
    
    def _record_action(self, player_input: str, response: str):
        """Record action in game history"""
        self.game_state["history"].append({
            "player": player_input,
            "response": response,
            "timestamp": time.time(),
            "location": self.game_state["location"],
            "turn": self.game_state["turn_count"]
        })
        
        # Limit history length
        if len(self.game_state["history"]) > self.config.max_history_length:
            self.game_state["history"] = self.game_state["history"][-self.config.max_history_length:]
    
    def save_game(self, filename: Optional[str] = None) -> bool:
        """Save the game state"""
        try:
            if filename is None:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f"structured_save_{timestamp}.json"
            
            filepath = os.path.join(self.config.saves_directory, filename)
            
            save_data = {
                **self.game_state,
                "save_time": time.time(),
                "save_version": "2.0",
                "dice_stats": self.dice.get_roll_statistics()
            }
            
            with open(filepath, "w") as f:
                json.dump(save_data, f, indent=2)
            
            print(f"💾 Game saved to {filepath}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to save game: {e}")
            return False
    
    def load_game(self, filename: str) -> bool:
        """Load a game state"""
        try:
            filepath = os.path.join(self.config.saves_directory, filename)
            
            if not os.path.exists(filepath):
                print(f"❌ Save file not found: {filepath}")
                return False
            
            with open(filepath, "r") as f:
                loaded_data = json.load(f)
            
            # Restore game state (excluding save metadata)
            for key, value in loaded_data.items():
                if key not in ["save_time", "save_version", "dice_stats"]:
                    self.game_state[key] = value
            
            print(f"📁 Game loaded from {filepath}")
            print(f"📍 Current location: {self.game_state['location']}")
            print(f"📜 Turn count: {self.game_state['turn_count']}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to load game: {e}")
            return False
    
    def get_game_status(self) -> Dict[str, Any]:
        """Get current game status"""
        dice_stats = self.dice.get_roll_statistics()
        
        return {
            "location": self.game_state["location"],
            "turn_count": self.game_state["turn_count"],
            "history_length": len(self.game_state["history"]),
            "session_time": time.time() - self.game_state["created_time"],
            "player_name": self.game_state["player_name"],
            "dice_statistics": dice_stats
        }
    
    def run_interactive(self):
        """Run interactive game session"""
        print("=" * 60)
        print("🎲 STRUCTURED D&D GAME - Week 2")
        print("=" * 60)
        print("Enhanced with separated components!")
        print()
        print("Commands:")
        print("  - 'roll d20' or 'skill check' for dice")
        print("  - 'new scenario' for scenario generation") 
        print("  - Natural language for actions")
        print("  - 'save', 'load', 'status', 'help', 'quit'")
        print()
        
        # Show initial state
        print("🎭 INITIAL SCENE:")
        print(self.game_state["story"])
        print()
        
        while True:
            try:
                player_input = input(f"{self.game_state['player_name']}> ").strip()
                
                if not player_input:
                    continue
                
                # Handle meta commands
                if player_input.lower() in ["quit", "exit", "q"]:
                    print("👋 Thanks for playing!")
                    break
                
                elif player_input.lower() == "help":
                    self._show_help()
                    continue
                    
                elif player_input.lower() == "save":
                    self.save_game()
                    continue
                
                elif player_input.lower() == "load":
                    # Show available saves and let player choose
                    saves = [f for f in os.listdir(self.config.saves_directory) if f.endswith('.json')]
                    if not saves:
                        print("❌ No save files found.")
                        continue
                    
                    print("\n📁 Available saves:")
                    for i, save in enumerate(saves, 1):
                        print(f"{i}. {save}")
                    
                    try:
                        choice = input("Enter number to load (or Enter to cancel): ").strip()
                        if choice and choice.isdigit():
                            idx = int(choice) - 1
                            if 0 <= idx < len(saves):
                                self.load_game(saves[idx])
                    except (ValueError, KeyboardInterrupt):
                        print("Load cancelled.")
                    continue
                
                elif player_input.lower() == "status":
                    status = self.get_game_status()
                    print(f"\n📊 Game Status:")
                    for key, value in status.items():
                        print(f"  {key}: {value}")
                    continue
                
                # Process game turn
                print("\n🎲 Processing...")
                result = self.play_turn(player_input)
                
                if result["success"]:
                    print(f"\n{result['message']}")
                else:
                    print(f"\n❌ {result['message']}")
                
                print()
                
            except KeyboardInterrupt:
                print("\n\n👋 Game interrupted. Goodbye!")
                break
            except Exception as e:
                print(f"❌ Unexpected error: {e}")
    
    def _show_help(self):
        """Show help information"""
        print("\n📖 STRUCTURED D&D GAME HELP:")
        print()
        print("This version separates game logic into components:")
        print("- Scenario Generator: Creates scenes and choices")
        print("- Dice System: Handles all rolling with statistics") 
        print("- Config System: Manages game settings")
        print()
        print("Example commands:")
        print("  'I look around the tavern'")
        print("  'I want to go to the forest'")
        print("  'Roll a skill check'")
        print("  'Generate a new scenario'")
        print("  'I talk to the bartender'")
        print()