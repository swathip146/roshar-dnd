"""
Haystack-Integrated D&D Game - Migrated from simple_dnd_game.py
Uses full Haystack architecture with orchestrator and pipeline integration
Maintains backward compatibility while adding sophisticated D&D mechanics
"""

# Set tokenizers parallelism to avoid fork warnings - MUST be set before any imports
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import json
import time
import logging
from typing import Dict, Any, Optional
from pathlib import Path

from orchestrator.pipeline_integration import create_full_haystack_orchestrator, GameRequest
from game_initialization import initialize_enhanced_dnd_game, GameInitConfig
from components.session_manager import SessionManager, create_session_manager

# Basic logging setup
logging.basicConfig(level=logging.WARNING)


class HaystackDnDGame:
    """
    Haystack-integrated D&D Game - Full Architecture Implementation
    Migrated from simple_dnd_game.py with enhanced capabilities
    """
    
    def __init__(self, policy_profile: str = "house", config: GameInitConfig = None):
        """Initialize with full Haystack integration and session management"""
        
        print("🚀 Initializing Enhanced D&D Game...")
        
        # Track initialization timing
        init_start = time.time()
        
        # Use provided config or initialize interactively
        if config is None:
            config = initialize_enhanced_dnd_game()
        
        self.config = config
        
        print(f"🗄️ Using document collection: {config.collection_name}")
        
        # Initialize session manager for sophisticated state management
        self.session_manager = create_session_manager(save_directory="game_saves")
        
        try:
            # Core orchestrator with all Stage 3 components + Pipeline integration
            # Pass the shared document store to avoid resource conflicts
            self.orchestrator = create_full_haystack_orchestrator(
                collection_name=config.collection_name,
                shared_document_store=config.shared_document_store
            )
        except Exception as e:
            raise
        
        # Initialize game session based on configuration
        if config.game_mode == "load_saved":
            self._load_saved_game(config.save_file)
        else:
            self._initialize_new_campaign(config)
        
        # Initialize with a default character using the sophisticated character manager
        self._initialize_default_character()
        
        session_state = self.session_manager.get_session_state()
        if session_state.get("session_active"):
            game_state = session_state["game_state"]
            print("🎲 Haystack D&D Game initialized with full architecture!")
            print("📍 Starting location:", game_state.get("location", "Unknown"))
            print("🎯 Enhanced features: Orchestrator, Agents, Pipelines & Components")
            print(f"📚 Document collection: {config.collection_name} for RAG-enhanced gameplay")
            
            # Show campaign info if available
            if "campaign_info" in game_state:
                campaign_info = game_state["campaign_info"]
                print(f"🗺️ Campaign: {campaign_info.get('name', 'Unknown Campaign')}")
                if campaign_info.get("theme"):
                    print(f"🎭 Theme: {campaign_info['theme']}")
                if campaign_info.get("difficulty"):
                    print(f"⚔️ Difficulty: {campaign_info['difficulty']}")
    
    def _initialize_new_campaign(self, config: GameInitConfig):
        """Initialize new campaign session with comprehensive campaign data"""
        
        campaign_data = config.campaign_data or {}
        
        # Enhanced game state with rich campaign information
        initial_state = {
            # Core game state (backward compatibility)
            "location": campaign_data.get("starting_location", campaign_data.get("location", "Tavern")),
            "story": campaign_data.get("story", "You enter a bustling tavern filled with adventurers, merchants, and locals. The air is thick with pipe smoke and the aroma of roasted meat. A fire crackles in the hearth, casting dancing shadows on weathered faces."),
            "history": [],
            "created_time": time.time(),
            "enhanced_features": True,
            "document_collection": config.collection_name,
            
            # Comprehensive campaign information
            "campaign_info": {
                "name": campaign_data.get("name", "Unknown Campaign"),
                "description": campaign_data.get("description", ""),
                "source": campaign_data.get("source", "default"),
                "theme": campaign_data.get("theme", "Fantasy Adventure"),
                "setting": campaign_data.get("setting", "Fantasy World"),
                "level_range": campaign_data.get("level_range", "1-5"),
                "difficulty": campaign_data.get("difficulty", "Medium"),
                "recommended_party_size": campaign_data.get("recommended_party_size", "3-5 players"),
                "session_count": campaign_data.get("session_count", 10),
                "main_plot": campaign_data.get("main_plot", ""),
                "dm_notes": campaign_data.get("dm_notes", ""),
                "enhanced_features": campaign_data.get("enhanced_features", {})
            },
            
            # Story elements for enhanced gameplay
            "campaign_content": {
                "hooks": campaign_data.get("campaign_hooks", []),
                "npcs": campaign_data.get("key_npcs", []),
                "locations": campaign_data.get("locations", []),
                "encounters": campaign_data.get("encounters", []),
                "rewards": campaign_data.get("rewards", []),
                "treasure_types": campaign_data.get("treasure_types", [])
            },
            
            # Session tracking
            "session_stats": {
                "turns_played": 0,
                "locations_visited": [campaign_data.get("starting_location", "Tavern")],
                "npcs_encountered": [],
                "encounters_completed": [],
                "rewards_earned": []
            }
        }
        
        # Create session with enhanced initial state
        result = self.session_manager.create_new_session(
            player_name=config.player_name or "Adventurer",
            initial_state=initial_state
        )
        
        if result["success"]:
            print(f"✅ New campaign session created")
            print(f"🗺️ Campaign: {campaign_data.get('name', 'Unknown Campaign')}")
            print(f"👤 Player: {config.player_name or 'Adventurer'}")
            
        else:
            print(f"❌ Failed to create campaign session: {result['message']}")
    
    def _load_saved_game(self, save_file: str):
        """Load game session from saved game file using session manager"""
        
        if not save_file:
            # Fallback to default new campaign
            self._initialize_new_campaign(GameInitConfig(
                collection_name=self.config.collection_name,
                game_mode="new_campaign"
            ))
            return
        
        # Use session manager to load the game
        result = self.session_manager.load_session(save_file)
        
        if result["success"]:
            session_data = result["result"]
            game_state = session_data.get("game_state", {})
            
            print(f"📁 Loaded game session: {save_file}")
            print(f"👤 Player: {session_data.get('player_name', 'Unknown')}")
            print(f"📍 Location: {game_state.get('location', 'Unknown')}")
            print(f"📜 History entries: {len(game_state.get('history', []))}")
            
            # Show campaign info if available
            if "campaign_info" in game_state:
                campaign_info = game_state["campaign_info"]
                print(f"🗺️ Campaign: {campaign_info.get('name', 'Unknown Campaign')}")
                
            # Show session stats if available
            if "session_stats" in game_state:
                stats = game_state["session_stats"]
                print(f"🎲 Turns played: {stats.get('turns_played', 0)}")
                print(f"🏛️ Locations visited: {len(stats.get('locations_visited', []))}")
                
        else:
            print(f"❌ Failed to load game: {result['message']}")
            print("   Starting new campaign instead...")
            self._initialize_new_campaign(GameInitConfig(
                collection_name=self.config.collection_name,
                game_mode="new_campaign"
            ))
    
    def _initialize_default_character(self):
        """Initialize default character using GameEngine's character management"""
        
        session_state = self.session_manager.get_session_state()
        if not session_state.get("session_active"):
            print("⚠️ No active session for character initialization")
            return
            
        game_state = session_state["game_state"]
        player_name = session_state["player_name"]
        
        default_character = {
            "character_id": "player",
            "name": player_name,
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
        
        # Use orchestrator's GameEngine for authoritative character management
        char_id = self.orchestrator.game_engine.add_character(default_character)
        
        # Store character data in session (for compatibility)
        self.session_manager.update_character_data(default_character)
        
        print(f"✅ Character '{default_character['name']}' initialized with GameEngine (ID: {char_id})")
    
    def play_turn(self, player_input: str) -> str:
        """
        Single turn of D&D - Send request directly to orchestrator with full session state
        The orchestrator and main_interface_agent handle all routing and processing decisions
        """
        
        # Handle None or invalid input
        if not player_input or not isinstance(player_input, str) or not player_input.strip():
            return "The world waits for your action..."
        
        try:
            # Get current session state for context
            session_state = self.session_manager.get_session_state()
            if not session_state.get("session_active"):
                return "No active session to process."
            
            # Create comprehensive request with enhanced world state context for fixed system
            game_state = session_state.get("game_state", {})
            
            request = GameRequest(
                request_type="gameplay_turn",
                data={
                    "player_input": player_input,
                    "actor": "player"
                },
                context={
                    # Full session state for orchestrator and interface agent
                    "session_state": session_state,
                    "game_state": game_state,
                    "character_data": session_state.get("character_data", {}),
                    "player_name": session_state.get("player_name", "Player"),
                    
                    # Enhanced context for fixed system routing
                    "collection_name": self.config.collection_name,
                    "recent_history": self._format_recent_history(),
                    "session_duration": session_state.get("session_duration", 0),
                    
                    # World state context for fixed system integration
                    "world_state": {
                        "current_location": game_state.get("location", "Unknown"),
                        "npcs": game_state.get("npcs", {}),
                        "environment": game_state.get("environment", {}),
                        "campaign_info": game_state.get("campaign_info", {}),
                        "locations_visited": game_state.get("session_stats", {}).get("locations_visited", []),
                        "npcs_encountered": game_state.get("session_stats", {}).get("npcs_encountered", [])
                    },
                    
                    # Fixed system compatibility flags
                    "fixed_system_enabled": True,
                    "enhanced_routing": True
                }
            )
            
            # Send directly to orchestrator - let it handle all routing decisions
            response = self.orchestrator.process_request(request)
            
            if response.success:
                # Format and update game state with orchestrator response
                formatted_result = self._format_enhanced_response(response.data)
                self._update_game_state(player_input, formatted_result)
                
                return formatted_result.get("formatted_response", "The adventure continues...")
            else:
                error_msg = response.data.get("error", "Unknown error")
                print(f"⚠️ Processing failed: {error_msg}")
                return "The world seems momentarily confused by your action. Try something else..."
                
        except Exception as e:
            print(f"❌ Error processing turn: {e}")
            return "Something unexpected happened. The adventure continues nonetheless..."
    
    
    def _format_enhanced_response(self, response_data: Dict[str, Any]) -> Dict[str, str]:
        """Format enhanced response data for display with comprehensive fallback handling and fixed system integration"""
        
        formatted_response = ""
        
        # Debug: Log what we received for troubleshooting
        print(f"🔍 Debug: Response data keys: {list(response_data.keys()) if response_data else 'None'}")
        
        # Check if this came from fixed system
        routing_context = response_data.get("routing_context", {})
        fixed_system_used = response_data.get("fixed_system_used", False)
        
        if fixed_system_used:
            print(f"✅ Response generated using fixed routing system (route: {routing_context.get('route', 'unknown')})")
        
        # Handle scenario-style responses
        if response_data and "scene" in response_data:
            formatted_response = response_data["scene"]
            
            # Add choices
            choices = response_data.get("choices", [])
            if choices:
                formatted_response += "\n\n📋 Available actions:"
                for choice in choices:
                    title = choice.get("title", "Action")
                    description = choice.get("description", "")
                    formatted_response += f"\n• {title}: {description}"
            
            # Add routing info if available
            if routing_context:
                confidence = routing_context.get("confidence", 0)
                if confidence > 0:
                    print(f"🎯 Routing confidence: {confidence:.1%}")
                    
        # Handle skill check results
        elif response_data and "skill_check_result" in response_data:
            skill_result = response_data["skill_check_result"]
            success = skill_result.get("success", False)
            total = skill_result.get("roll_total", 0)
            dc = skill_result.get("dc", 0)
            
            result_emoji = "✅" if success else "❌"
            formatted_response = f"{result_emoji} Skill Check: {total} vs DC {dc} - {'Success!' if success else 'Failure!'}"
            
            if "roll_breakdown" in skill_result:
                formatted_response += f"\n🎲 {skill_result['roll_breakdown']}"
                
        # Handle NPC responses
        elif response_data and "npc_response" in response_data:
            npc_data = response_data["npc_response"]
            dialogue = npc_data.get("dialogue", "The NPC responds...")
            formatted_response = f"💬 {dialogue}"
            
            # Show NPC resolution if from fixed system
            if routing_context and routing_context.get("target"):
                resolved_npc = routing_context["target"]
                print(f"👥 NPC interaction with: {resolved_npc}")
                
        # Handle general responses
        elif response_data and "response" in response_data:
            formatted_response = response_data["response"]
            
        # Handle orchestrator error responses
        elif response_data and "error" in response_data:
            error_msg = response_data["error"]
            print(f"⚠️ Orchestrator error: {error_msg}")
            formatted_response = f"The world pauses as mysterious forces interfere... ({error_msg[:50]}...)"
            
        # Handle pipeline processing responses with fallback_scene
        elif response_data and "fallback_scene" in response_data:
            formatted_response = response_data["fallback_scene"]
            print(f"⚠️ Using fallback scene due to: {response_data.get('error', 'unknown error')}")
            
        # Handle empty or invalid response data
        elif not response_data or not isinstance(response_data, dict):
            print(f"⚠️ Invalid response data: {type(response_data)} - {response_data}")
            formatted_response = "The world seems uncertain how to respond to your action. Try something else..."
            
        # Fallback for unrecognized response format
        else:
            print(f"⚠️ Unrecognized response format with keys: {list(response_data.keys())}")
            # Try to extract any text content from the response
            if isinstance(response_data, dict):
                for key in ["scene", "message", "text", "content", "result"]:
                    if key in response_data and isinstance(response_data[key], str):
                        formatted_response = response_data[key]
                        break
            
            if not formatted_response:
                formatted_response = "The adventure continues in ways you never expected..."
        
        # Enhanced response metadata
        response_metadata = {
            "formatted_response": formatted_response,
            "raw_data": response_data,
            "fixed_system_used": fixed_system_used,
            "routing_confidence": routing_context.get("confidence", 0) if routing_context else 0,
            "processing_route": routing_context.get("route", "unknown") if routing_context else "legacy"
        }
        
        return response_metadata
    
    def _update_game_state(self, player_input: str, response_data: Dict[str, Any]):
        """Update game state using GameEngine's authoritative state management"""
        
        session_state = self.session_manager.get_session_state()
        if not session_state.get("session_active"):
            print("⚠️ No active session to update")
            return
            
        game_state = session_state["game_state"]
        current_location = game_state.get("location", "Unknown")
        
        # Create enhanced history entry for session manager compatibility
        history_entry = {
            "player": player_input,
            "dm": response_data.get("scene", response_data.get("formatted_response", "Response generated")),
            "timestamp": time.time(),
            "location": current_location
        }
        
        # Add enhanced data if available
        if "effects" in response_data:
            history_entry["effects"] = response_data["effects"]
        
        # Update history in session manager (for compatibility)
        if "history" not in game_state:
            game_state["history"] = []
        game_state["history"].append(history_entry)
        
        # Process effects through GameEngine's authoritative state management
        if "effects" in response_data:
            for effect in response_data["effects"]:
                if effect.get("type") == "location_change":
                    new_location = effect.get("value")
                    if new_location:
                        print(f"📍 Location changed: {current_location} → {new_location}")
                        game_state["location"] = new_location
                        # Update environment in orchestrator's GameEngine
                        self.orchestrator.game_engine.update_environment({"current_location": new_location})
                        
                elif effect.get("type") == "character_condition":
                    char_id = effect.get("character_id", "player")
                    condition = effect.get("condition")
                    active = effect.get("active", True)
                    if condition:
                        self.orchestrator.game_engine.set_character_condition(char_id, condition, active)
                        
                elif effect.get("type") == "campaign_flag":
                    flag_name = effect.get("flag_name")
                    value = effect.get("value")
                    if flag_name:
                        self.orchestrator.game_engine.set_campaign_flag(flag_name, value)
        
        # Simple location detection (compatible with original)
        if not response_data.get("effects"):
            new_location = self._detect_location_from_response(history_entry["dm"])
            if new_location and new_location != current_location:
                print(f"📍 Location changed: {current_location} → {new_location}")
                game_state["location"] = new_location
                # Update orchestrator's GameEngine environment
                self.orchestrator.game_engine.update_environment({"current_location": new_location})
        
        # Update session stats manually (for backward compatibility)
        if "session_stats" not in game_state:
            game_state["session_stats"] = {"turns_played": 0, "locations_visited": [], "npcs_encountered": [], "encounters_completed": []}
        
        game_state["session_stats"]["turns_played"] += 1
        
        # Track location visits
        current_loc = game_state.get("location", "Unknown")
        if current_loc not in game_state["session_stats"]["locations_visited"]:
            game_state["session_stats"]["locations_visited"].append(current_loc)
        
        # Update session state in session manager
        self.session_manager.update_session_state(game_state)
    
    def _format_recent_history(self) -> str:
        """Format recent history for context using session manager"""
        
        session_state = self.session_manager.get_session_state()
        if not session_state.get("session_active"):
            return "No active session."
            
        game_state = session_state["game_state"]
        history = game_state.get("history", [])
        
        if not history:
            return "This is the beginning of your adventure."
        
        recent = history[-3:]  # Last 3 interactions
        formatted = []
        
        for entry in recent:
            formatted.append(f"Player: {entry['player']}")
            dm_text = entry['dm']
            if len(dm_text) > 100:
                dm_text = dm_text[:100] + "..."
            formatted.append(f"DM: {dm_text}")
        
        return "\n".join(formatted)
    
    def _detect_location_from_response(self, dm_response: str) -> Optional[str]:
        """Simple location detection from DM response - returns new location if detected"""
        
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
            if keyword in dm_lower:
                return location
                
        return None
    
    def save_game(self, filename: str = "haystack_save.json") -> bool:
        """Comprehensive save using SessionManager, GameEngine, and Orchestrator state"""
        
        try:
            # Get orchestrator's GameEngine complete state export (authoritative game state)
            game_engine_state = self.orchestrator.game_engine.export_game_state()
            
            # Get orchestrator state for comprehensive saving
            orchestrator_state = {}
            try:
                orchestrator_state = self.orchestrator.get_pipeline_status()
                
                # Try to get additional session statistics from orchestrator
                session_request = GameRequest("game_statistics", {})
                session_response = self.orchestrator.process_request(session_request)
                
                if session_response.success:
                    orchestrator_state["session_statistics"] = session_response.data
                    
            except Exception as e:
                print(f"⚠️ Could not get orchestrator state: {e}")
            
            # Add game engine data to orchestrator state before saving
            enhanced_orchestrator_state = orchestrator_state.copy() if orchestrator_state else {}
            enhanced_orchestrator_state.update({
                "game_engine_state": game_engine_state,
                "game_engine_statistics": self.orchestrator.game_engine.get_game_statistics(),
                "policy_profile": game_engine_state.get("policy_profile", "house"),
                "save_version": "2.0_with_game_engine"
            })
            
            # Use SessionManager for comprehensive saving with GameEngine state
            result = self.session_manager.save_session(
                filename=filename,
                orchestrator_state=enhanced_orchestrator_state
            )
            
            if result["success"]:
                filepath = result["result"]["filepath"]
                print(f"💾 Comprehensive game saved to {filepath}")
                print("📊 Save includes: session data, GameEngine state, character data, orchestrator state, and metadata")
                print(f"🎯 GameEngine exported: {len(game_engine_state.get('character_data', {}))} characters, {len(game_engine_state.get('game_state', {}).get('campaign_flags', {}))} campaign flags")
                return True
            else:
                print(f"❌ Failed to save game: {result['message']}")
                return False
                
        except Exception as e:
            print(f"❌ Failed to save game: {e}")
            return False
  
    def get_game_stats(self) -> Dict[str, Any]:
        """Comprehensive game statistics using GameEngine and orchestrator"""
        
        session_state = self.session_manager.get_session_state()
        if not session_state.get("session_active"):
            return {"error": "No active session"}
            
        game_state = session_state["game_state"]
        
        # Get comprehensive statistics from orchestrator's GameEngine
        engine_stats = self.orchestrator.game_engine.get_game_statistics()
        
        # Combine with session data for complete picture
        combined_stats = {
            # Core game information
            "location": game_state.get("location", "Unknown"),
            "player_name": session_state.get("player_name", "Unknown"),
            "campaign_name": game_state.get("campaign_info", {}).get("name", "Unknown Campaign"),
            
            # GameEngine statistics (7-step pipeline data)
            "session_duration": engine_stats["session_duration"],
            "total_skill_checks": engine_stats["total_skill_checks"],
            "successful_checks": engine_stats["successful_checks"],
            "success_rate": engine_stats["success_rate"],
            "dice_statistics": engine_stats["dice_statistics"],
            "active_characters": engine_stats["active_characters"],
            "campaign_flags": engine_stats["campaign_flags"],
            "environment": engine_stats["environment"],
            
            # Session manager statistics
            "turns_played": len(game_state.get("history", [])),
            "locations_visited": len(game_state.get("session_stats", {}).get("locations_visited", [])),
            "npcs_encountered": len(game_state.get("session_stats", {}).get("npcs_encountered", [])),
            
            # System status
            "enhanced_mode": True,
            "game_engine_active": True,
            "session_manager_active": True
        }
        
        # Try to get orchestrator statistics as well
        try:
            stats_request = GameRequest("game_statistics", {})
            stats_response = self.orchestrator.process_request(stats_request)
            
            if stats_response.success:
                combined_stats["orchestrator_stats"] = stats_response.data
                combined_stats["pipeline_status"] = self.orchestrator.get_pipeline_status()
        except Exception as e:
            print(f"⚠️ Could not get orchestrator stats: {e}")
            
        return combined_stats
    
    def run_interactive(self):
        """
        Enhanced interactive game loop 
        Maintains original interface with enhanced capabilities
        """
        
        print("=" * 70)
        print("🎲 D&D GAME")
        print("=" * 70)
        print("🚀 Powered by: Orchestrator, Agents, Pipelines & Components")
        print("Type 'help' for commands, 'quit' to exit")
        print()
        
        # Initial scene (enhanced)
        session_state = self.session_manager.get_session_state()
        if session_state.get("session_active"):
            game_state = session_state["game_state"]
            print("🎭 SCENE:")
            print(game_state.get("story", "Welcome to your adventure!"))
        else:
            print("🎭 SCENE:")
            print("No active session available.")
        
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
                # Get player input using session manager
                session_state = self.session_manager.get_session_state()
                player_name = "Player"
                if session_state.get("session_active"):
                    player_name = session_state.get("player_name", "Player")
                
                player_input = input(f"{player_name}> ").strip()
                
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
                
                elif player_input.lower() == "stats":
                    stats = self.get_game_stats()
                    print(f"\n📊 Enhanced Game Stats:")
                    print(f"Location: {stats.get('location', 'Unknown')}")
                    print(f"Turns: {stats.get('turns_played', 0)}")
                    session_duration = stats.get('session_duration', 0)
                    print(f"Session time: {session_duration:.1f}s")
                    if stats.get("enhanced_mode"):
                        print(f"Enhanced Features: ✅ Active")
                        print(f"GameEngine: {'✅ Active' if stats.get('game_engine_active') else '❌ Inactive'}")
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
        print()
        print("📋 Commands:")
        print("  help     - Show this help")
        print("  save     - Save the game (enhanced format)")
        print("  stats    - Show detailed statistics")
        print("  quit     - Exit the game")
        print()
        print("💡 Note: To load a different game, exit and restart the application.")
        print()
        print("🎮 Enhanced Gameplay:")
        print("  • Try complex actions like 'search the ancient library for dragon lore'")
        print("  • Engage in detailed conversations: 'talk to the bartender about rumors'")
        print("  • Attempt skill-based actions: 'climb the castle wall stealthily'")
        print("  • Cast spells: 'cast fireball at the goblins'")
        print("  • The system will automatically determine appropriate skill checks!")
        print()


def main():
    """Main function to run the Haystack-integrated D&D game"""
    
    try:
        # Initialize game with enhanced setup system
        config = initialize_enhanced_dnd_game()
        
        # Create and run game with configuration
        game = HaystackDnDGame(config=config)
        game.run_interactive()
        
    except Exception as e:
        print(f"❌ Failed to start game: {e}")
        import traceback
        print(f"Full error: {traceback.format_exc()}")

if __name__ == "__main__":
    main()