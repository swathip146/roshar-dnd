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
from typing import Dict, Any, Optional, List
from pathlib import Path

from orchestrator.pipeline_integration import create_full_haystack_orchestrator
from core.game_initialization import initialize_enhanced_dnd_game, GameInitConfig
from components.shared_contract import new_dto, RequestDTO
from config.logging_config import get_logger

# Initialize logger
logger = get_logger(__name__)


class HaystackDnDGame:
    """
    Haystack-integrated D&D Game - Full Architecture Implementation
    Migrated from simple_dnd_game.py with enhanced capabilities
    """
    
    def __init__(self, policy_profile: str = "house", config: GameInitConfig = None):
        """Initialize with full Haystack integration and session management"""

        logger.info("🚀 Initializing Enhanced D&D Game...")

        # Track initialization timing
        init_start = time.time()

        # Use provided config or initialize interactively
        if config is None:
            raise Exception(" Error no config...")

        self.config = config

        logger.info(f"🗄️ Using document collection: {config.collection_name}")
        
        # Use all initialized components from config (already comprehensive initialization done)
        self.session_manager = config.session_manager
        self.character_manager = config.character_manager
        self.game_engine = config.game_engine
        self.policy_engine = config.policy_engine
        
        try:
            # Enhanced orchestrator with all game components from fallback-enabled initialization
            # Pass all components to enable comprehensive context population
            self.orchestrator = create_full_haystack_orchestrator(
                collection_name=config.collection_name,
                shared_document_store=config.shared_document_store,
                game_engine=config.game_engine,
                character_manager=config.character_manager,
                session_manager=config.session_manager,
                policy_engine=config.policy_engine
            )
            logger.info(f"🎯 Orchestrator created with enhanced component integration")

        except Exception as e:
            logger.error(f"❌ Failed to create enhanced orchestrator: {e}")
            raise
        
        # BREAKING CHANGE: Get session metadata instead of state (SessionManager is persistence-only)
        session_metadata = self.session_manager.get_session_metadata()
        if session_metadata.get("session_active"):
            logger.info("🎲 Haystack D&D Game initialized with full architecture!")

            # Get starting location from GameEngine (authoritative source)
            if self.game_engine and hasattr(self.game_engine, 'game_state'):
                location_context = self.game_engine.game_state.location_context
                current_location = location_context.get("current_location", "Unknown")
                logger.info(f"📍 Starting location: {current_location}")
                
                # Show campaign info from CampaignConfig (authoritative source)
                if hasattr(self.game_engine, 'campaign_config') and self.game_engine.campaign_config:
                    campaign_config = self.game_engine.campaign_config
                    logger.info(f"🗺️ Campaign: {campaign_config.name}")
                    logger.info(f"🎭 Theme: {campaign_config.theme}")
                    logger.info(f"⚔️ Difficulty: {campaign_config.difficulty}")
            
            logger.info("🎯 Enhanced features: Orchestrator, Agents, Pipelines & Components")
            logger.info(f"📚 Document collection: {config.collection_name} for RAG-enhanced gameplay")

        # Debug: Print all instance states after initialization is complete
        logger.debug("Instance States After Initialization")
        logger.debug("=" * 60)
        
        # GameEngine state with enhanced debugging
        try:
            if self.game_engine:
                if hasattr(self.game_engine, 'export_game_state'):
                    game_engine_export = self.game_engine.export_game_state()
                    game_state = game_engine_export.get('game_state', {})
                    logger.info(f"🎮 GameEngine State: {type(self.game_engine).__name__}")
                    logger.debug(f"   - Characters: {len(game_state.get('characters', {}))}")
                    logger.debug(f"   - Campaign flags: {len(game_state.get('campaign_flags', {}))}")
                    logger.debug(f"   - Environment keys: {list(game_state.get('environment', {}).keys())}")
                    logger.debug(f"   - Campaign data keys: {list(game_state.get('campaign_data', {}).keys())} (SHOULD be empty - moved to CampaignConfig)")
                    
                    # Show CampaignConfig state separately (this is the NEW authority)
                    if hasattr(self.game_engine, 'campaign_config') and self.game_engine.campaign_config:
                        campaign_config = self.game_engine.campaign_config
                        logger.debug(f"   📋 CampaignConfig (Authority): {type(campaign_config).__name__}")
                        logger.debug(f"      - Name: {campaign_config.name}")
                        logger.debug(f"      - Theme: {campaign_config.theme}")
                        logger.debug(f"      - Difficulty: {campaign_config.difficulty}")
                        logger.debug(f"      - NPCs: {len(getattr(campaign_config, 'key_npcs', []))}")
                        logger.debug(f"      - Locations: {len(getattr(campaign_config, 'locations', []))}")
                        logger.debug(f"      - Starting Location: {campaign_config.starting_location}")
                        logger.debug(f"      - Story Length: {len(campaign_config.story)} chars")
                    else:
                        logger.debug(f"   ⚠️ No CampaignConfig attached to GameEngine")
                else:
                    logger.info(f"🎮 GameEngine: {type(self.game_engine).__name__} (fallback implementation)")
            else:
                logger.info(f"🎮 GameEngine: None")
        except Exception as e:
            logger.info(f"🎮 GameEngine: Error accessing state - {e}")
        
        # CharacterManager state
        try:
            if self.character_manager:
                if hasattr(self.character_manager, 'get_party_snapshot'):
                    party_snapshot = self.character_manager.get_party_snapshot()
                    logger.info(f"👥 CharacterManager State: {type(self.character_manager).__name__}")
                    logger.debug(f"   - Party size: {party_snapshot.get('party_size', 0)}")
                    logger.debug(f"   - Average level: {party_snapshot.get('avg_level', 'Unknown')}")
                    logger.debug(f"   - Party roles: {party_snapshot.get('party_roles', {})}")
                elif hasattr(self.character_manager, 'characters'):
                    logger.info(f"👥 CharacterManager: {type(self.character_manager).__name__} (fallback)")
                    logger.debug(f"   - Characters: {len(getattr(self.character_manager, 'characters', {}))}")
                else:
                    logger.info(f"👥 CharacterManager: {type(self.character_manager).__name__} (unknown implementation)")
            else:
                logger.info(f"👥 CharacterManager: None")
        except Exception as e:
            logger.info(f"👥 CharacterManager: Error accessing state - {e}")
        
        # SessionManager state - BREAKING CHANGE: Only metadata now
        try:
            if self.session_manager:
                session_metadata = self.session_manager.get_session_metadata()
                logger.info(f"📝 SessionManager State: {type(self.session_manager).__name__}")
                logger.debug(f"   - Session active: {session_metadata.get('session_active', False)}")
                logger.debug(f"   - Player name: {session_metadata.get('player_name', 'Unknown')}")
                logger.debug(f"   - Session duration: {session_metadata.get('session_duration', 0):.1f}s")
            else:
                logger.info(f"📝 SessionManager: None")
        except Exception as e:
            logger.info(f"📝 SessionManager: Error accessing metadata - {e}")
        
        # PolicyEngine state
        try:
            if self.policy_engine:
                logger.info(f"⚖️ PolicyEngine State: {type(self.policy_engine).__name__}")
                if hasattr(self.policy_engine, 'get_difficulty_policy'):
                    try:
                        # Try to get a sample policy
                        sample_context = {"party_size": 1, "avg_level": 1}
                        difficulty_policy = self.policy_engine.get_difficulty_policy(sample_context)
                        logger.debug(f"   - Difficulty target: {difficulty_policy.get('difficulty_target', 'medium')}")
                        dc_policy = difficulty_policy.get('dc_policy', {})
                        logger.debug(f"   - DC policies: {list(dc_policy.keys())}")
                    except Exception as policy_e:
                        logger.debug(f"   - Policy access error: {policy_e}")
                else:
                    logger.debug(f"   - Basic fallback implementation")
            else:
                logger.info(f"⚖️ PolicyEngine: None")
        except Exception as e:
            logger.info(f"⚖️ PolicyEngine: Error accessing state - {e}")
        
        logger.debug("=" * 60)
        logger.debug(f"End Instance States")

        # Add choice management fields (UI state only, not game state)
        self.current_scenario: Optional[Dict[str, Any]] = None
        self.current_choices: List[Dict[str, Any]] = []
        self.turn_counter: int = 0
        
        logger.info("🎯 Enhanced response system initialized with choice management")
        
        # Generate initial scenario
        # self._generate_initial_scenario()

    def _generate_initial_scenario(self):
        """Generate initial scenario following state hierarchy"""
        
        try:
            logger.info("🎬 Generating initial scenario...")
            
            initial_dto = self._create_initial_dto()
            response_dict = self.orchestrator.process_request(initial_dto)
            
            # Handle dict response from orchestrator
            if response_dict.get("success", False):
                response_data = response_dict.get("data", response_dict)
                formatted_result = self._handle_response(response_data)
                
                # COMPLIANCE: Use authoritative components for state updates
                self._update_state_via_authorities(
                    {"type": "initialization", "original_input": "GAME_START"},
                    response_data
                )
                
                self.initial_scenario = formatted_result
                logger.info("✅ Initial scenario generated")
            else:
                error_msg = response_dict.get("error", "Unknown error")
                logger.warning(f"Failed to generate initial scenario: {error_msg}")
                
        except Exception as e:
            logger.error(f"Error generating initial scenario: {e}")

    def _create_initial_dto(self) -> RequestDTO:
        """Create DTO for initial scenario"""
        
        from components.shared_contract import new_dto
        
        request_dto = new_dto(
            "Generate the opening scenario for this campaign. Set the scene, introduce the setting, and provide initial choices for the player to begin their adventure.",
            {}
        )
        
        request_dto["_game_engine_ref"] = self.game_engine
        request_dto["_policy_engine_ref"] = self.policy_engine
        request_dto["type"] = "scenario"
        
        return request_dto
     
    def _process_input(self, player_input: str) -> Dict[str, Any]:
        """Process player input - UI logic only, no state management"""
        
        input_stripped = player_input.strip()
        
        # Check if input is a number corresponding to a choice
        if input_stripped.isdigit() and self.current_choices:
            choice_num = int(input_stripped)
            if 1 <= choice_num <= len(self.current_choices):
                selected_choice = self.current_choices[choice_num - 1]
                # Convert choice to action text for pipeline
                action_text = selected_choice.get("title", "") + " " + selected_choice.get("description", "")
                return {
                    "type": "gameplay_turn",
                    "original_input": player_input,
                    "processed_input": action_text,
                    "selected_choice": selected_choice
                }
        
        # Regular text input
        return {
            "type": "gameplay_turn",
            "original_input": player_input,
            "processed_input": input_stripped
        }

    def _update_state_via_authorities(self, processed_input: Dict[str, Any], response_data: Dict[str, Any]):
        """Update state via authoritative components following hierarchy"""
        
        response_type = response_data.get("response_type", "unknown")
        
        # COMPLIANCE: GameEngine is authoritative for runtime state
        if response_type == "scenario":
            scenario = response_data.get("scenario", {})
            self.game_engine.process_scenario_state_updates(scenario, self.turn_counter)
        
        # COMPLIANCE: SessionManager only for persistence/analytics
        confidence = 0
        if response_type == "scenario":
            confidence = response_data.get("scenario", {}).get("confidence", 0)
        elif response_type == "rag_query":
            confidence = response_data.get("rag_result", {}).get("confidence", 0)
        
        self.session_manager.record_turn_analytics(processed_input, response_type, confidence, self.turn_counter)

    def play_turn(self, player_input: str) -> str:
        """Enhanced turn processing following state hierarchy"""
        
        if not player_input or not isinstance(player_input, str) or not player_input.strip():
            return "The world waits for your action..."
        
        self.turn_counter += 1
        
        try:
            # COMPLIANCE: Get session metadata for context (SessionManager is persistence-only)
            session_metadata = self.session_manager.get_session_metadata()
            if not session_metadata.get("session_active"):
                return "No active session to process."
            
            # Process input (UI logic only)
            processed_input = self._process_input(player_input)
            
            # Create DTO using existing pattern - use processed input
            input_text = processed_input.get("processed_input", player_input)
            logger.debug(f"input_text = '{input_text}'")
            request_dto = new_dto(input_text, {})  # Empty context - no state copying
            request_dto["type"] = processed_input.get("type", "gameplay_turn")
            request_dto["_game_engine_ref"] = self.game_engine
            request_dto["_policy_engine_ref"] = self.policy_engine
            
            logger.info(f"🎯 Processing turn {self.turn_counter} with enhanced response system")
            
            # Use existing orchestrator
            response_dict = self.orchestrator.process_request(request_dto)
            
            # Handle None response from failed orchestrator
            if response_dict is None:
                logger.error("Orchestrator returned None - pipeline failure")
                return "The magical forces seem disrupted. Please try again."
            
            # Handle dict response from orchestrator
            if response_dict.get("success", False):
                # Format response using new response handlers
                formatted_result = self._handle_response(response_dict)
                
                # Update UI state for choice management
                self._update_ui_state(response_dict)
                
                # COMPLIANCE: Delegate state updates to authoritative components
                self._update_state_via_authorities(processed_input, response_dict)
                
                return formatted_result.get("formatted_response", "The adventure continues...")
            else:
                error_msg = response_dict.get("error", "Unknown error")
                logger.warning(f"Processing failed: {error_msg}")
                return "The world seems momentarily confused by your action. Try something else..."
                
        except Exception as e:
            logger.error(f"Error processing turn: {e}")
            return "Something unexpected happened. The adventure continues nonetheless..."

    def _update_ui_state(self, response_data: Dict[str, Any]):
        """Update UI state for choice management - UI state only"""
        
        response_type = response_data.get("response_type", "unknown")
        
        if response_type == "scenario":
            scenario = response_data.get("scenario", {})
            choices = scenario.get("choices", [])
            
            # Update UI state only (not game state - that's handled by GameEngine)
            self.current_scenario = scenario
            self.current_choices = choices
            
            logger.info(f"🎯 Updated UI state: {len(choices)} choices available")
        else:
            # For non-scenario responses, preserve existing choices if they exist
            logger.info(f"🎯 Non-scenario response: preserving existing UI state")
    
    def _handle_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle GameResponseDTO - UI presentation only"""
        
        response_type = response_data.get("response_type", "unknown")
        
        if response_type == "scenario":
            return self._handle_scenario(response_data)
        elif response_type == "rag_query":
            return self._handle_rag(response_data)
        elif response_type == "npc_interaction":
            return self._handle_npc(response_data)
        else:
            return self._handle_unknown(response_data)

    def _handle_scenario(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle scenario responses - UI state only"""
        
        scenario = response_data.get("scenario", {})
        scene = scenario.get("scene", "The adventure continues...")
        choices = scenario.get("choices", [])
        
        # Update UI state only (not game state - that's handled by GameEngine)
        self.current_scenario = scenario
        self.current_choices = choices
        
        # Format response with numbered choices
        formatted_response = scene
        if choices:
            formatted_response += "\n\n📋 Choose your action:"
            for i, choice in enumerate(choices, 1):
                title = choice.get("title", f"Option {i}")
                description = choice.get("description", "")
                formatted_response += f"\n{i}. {title}"
                if description:
                    formatted_response += f" - {description}"
        
        return {
            "formatted_response": formatted_response,
            "response_type": "scenario",
            "scenario_data": scenario,
            "choices": choices,
            "raw_data": response_data
        }

    def _handle_rag(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle RAG responses - UI presentation only"""
        
        rag_result = response_data.get("rag_result", {})
        rag_context = rag_result.get("response", "")
        query = rag_result.get("original_query", "")
        confidence = rag_result.get("confidence", 0)
        
        if rag_context:
            formatted_response = f"📚 {rag_context}"
            if confidence > 0:
                formatted_response += f"\n\n💡 Information confidence: {confidence:.1%}"
        else:
            formatted_response = f"I searched for information about '{query}', but couldn't find specific details."
        
        # Maintain current scenario context (UI state)
        if self.current_scenario and self.current_choices:
            formatted_response += "\n\n" + self._format_choices()
        
        return {
            "formatted_response": formatted_response,
            "response_type": "rag_query",
            "rag_data": rag_result,
            "raw_data": response_data
        }

    def _handle_npc(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle NPC interaction responses"""
        
        npc_response = response_data.get("npc_response", {})
        dialogue = npc_response.get("dialogue", "The NPC responds...")
        
        formatted_response = f"💬 {dialogue}"
        
        # Maintain current scenario context (UI state)
        if self.current_scenario and self.current_choices:
            formatted_response += "\n\n" + self._format_choices()
        
        return {
            "formatted_response": formatted_response,
            "response_type": "npc_interaction",
            "npc_data": npc_response,
            "raw_data": response_data
        }

    def _handle_unknown(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle unknown or legacy response formats"""
        
        formatted_response = ""
        
        # Handle legacy response formats
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
        elif response_data and "response" in response_data:
            formatted_response = response_data["response"]
        else:
            formatted_response = "The adventure continues in unexpected ways..."
            logger.warning(f"Unrecognized response format with keys: {list(response_data.keys()) if response_data else 'None'}")
        
        return {
            "formatted_response": formatted_response,
            "response_type": "unknown",
            "raw_data": response_data
        }

    def _format_choices(self) -> str:
        """Format current choices for display - UI only"""
        if not self.current_choices:
            return ""
        
        choice_text = "📋 Available actions:"
        for i, choice in enumerate(self.current_choices, 1):
            title = choice.get("title", f"Option {i}")
            choice_text += f"\n{i}. {title}"
        return choice_text

    def save_game(self, filename: str = "haystack_save.json") -> bool:
        """Comprehensive save using authoritative sources - BREAKING CHANGE: Updated for clean architecture"""
        
        try:
            # BREAKING CHANGE: Get state from authoritative sources
            game_engine_state = self.game_engine.export_game_state()
            character_manager_state = {}
            
            # Get character data from CharacterManager (authority)
            if self.character_manager:
                character_manager_state = {
                    char_id: self.character_manager.get_character_summary(char_id)
                    for char_id in self.character_manager.characters.keys()
                }
            
            # Use SessionManager for persistence coordination (not state management)
            result = self.session_manager.save_session(
                filename=filename,
                game_engine_state=game_engine_state,
                character_manager_state=character_manager_state
            )
            
            if result["success"]:
                filepath = result["result"]["filepath"]
                logger.info(f"💾 Clean architecture game saved to {filepath}")
                logger.info("📊 Save includes: GameEngine state (authoritative), CharacterManager data (authoritative), session metadata")
                logger.info(f"🎯 Data saved: {len(character_manager_state)} characters, campaign from CampaignConfig")
                return True
            else:
                logger.error(f"Failed to save game: {result['message']}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to save game: {e}")
            return False
  
    def get_game_stats(self) -> Dict[str, Any]:
        """Comprehensive game statistics using authoritative sources - BREAKING CHANGE"""
        
        session_metadata = self.session_manager.get_session_metadata()
        if not session_metadata.get("session_active"):
            return {"error": "No active session"}
        
        # BREAKING CHANGE: Get statistics from authoritative sources
        engine_stats = self.game_engine.get_game_statistics()
        
        # Get current location from GameEngine (authoritative)
        current_location = "Unknown"
        campaign_name = "Unknown Campaign"
        if self.game_engine and hasattr(self.game_engine, 'game_state'):
            location_context = self.game_engine.game_state.location_context
            current_location = location_context.get("current_location", "Unknown")
            
            # Get campaign name from CampaignConfig (authoritative)
            if hasattr(self.game_engine, 'campaign_config') and self.game_engine.campaign_config:
                campaign_name = self.game_engine.campaign_config.name
        
        combined_stats = {
            # Core game information from authoritative sources
            "location": current_location,
            "player_name": session_metadata.get("player_name", "Unknown"),
            "campaign_name": campaign_name,
            
            # GameEngine statistics (7-step pipeline data)
            "session_duration": engine_stats["session_duration"],
            "total_skill_checks": engine_stats["total_skill_checks"],
            "successful_checks": engine_stats["successful_checks"],
            "success_rate": engine_stats["success_rate"],
            "dice_statistics": engine_stats["dice_statistics"],
            "active_characters": engine_stats["active_characters"],
            "campaign_flags": engine_stats["campaign_flags"],
            "environment": engine_stats["environment"],
            
            # Session metadata (persistence info only)
            "session_duration_metadata": session_metadata.get("session_duration", 0),
            
            # System status
            "enhanced_mode": True,
            "game_engine_active": True,
            "session_manager_active": True
        }
        
        # Try to get orchestrator statistics as well
        try:
            combined_stats["pipeline_status"] = self.orchestrator.get_pipeline_status()
        except Exception as e:
            logger.warning(f"Could not get orchestrator stats: {e}")
            
        return combined_stats
    
    def run_interactive(self):
        """Enhanced interactive game loop - UI presentation only"""
        
        logger.info("=" * 70)
        logger.info("🎲 D&D GAME")
        logger.info("=" * 70)
        logger.info("🚀 Powered by: Orchestrator, Agents, Pipelines & Components")
        logger.info("Type \'help\' for commands, \'quit\' to exit")
        # Empty line for console output
        
        # Display initial scenario if available
        if hasattr(self, 'initial_scenario') and self.initial_scenario:
            print("🎭 OPENING SCENE:")
            print(self.initial_scenario["formatted_response"])
        else:
            # COMPLIANCE: Use immutable CampaignConfig via GameEngine
            session_metadata = self.session_manager.get_session_metadata()
            if session_metadata.get("session_active"):
                curr_scene = self.game_engine.game_state.narrative_context.get("current_scene")
                opening_scene = self.game_engine.game_state.narrative_context.get("opening_scene")
                quest = self.game_engine.get_quest_context().get("active_quests")
                print("🎭 SCENE:")
                logger.info(f"Curr: {curr_scene}")
                logger.info(f"Opening Scene: {opening_scene}")
                print(f"Active quest: {quest}")
                
        
        # Empty line for console output
        
        # Main game loop with choice display
        while True:
            try:
                # COMPLIANCE: Use SessionManager for session metadata only
                session_metadata = self.session_manager.get_session_metadata()
                player_name = session_metadata.get("player_name", "Player") if session_metadata.get("session_active") else "Player"
                
                # Show current choices if available (UI state)
                if self.current_choices:
                    print(f"\n📋 Available actions (enter number 1-{len(self.current_choices)}):")
                    for i, choice in enumerate(self.current_choices, 1):
                        title = choice.get("title", f"Option {i}")
                        print(f"  {i}. {title}")
                    print("Or enter your own action/question...")
                
                player_input = input(f"\n{player_name}> ").strip()
                
                if not player_input:
                    continue
                
                # Handle system commands
                if player_input.lower() in ["quit", "exit", "q"]:
                    print("💾 Saving game before exit...")
                    self.save_game()  # Uses existing state hierarchy
                    print("👋 Thanks for playing! Goodbye!")
                    break
                elif player_input.lower() == "help":
                    self._show_enhanced_help()
                    continue
                elif player_input.lower() == "save":
                    self.save_game()  # Uses existing state hierarchy
                    continue
                elif player_input.lower() == "stats":
                    self._show_stats()
                    continue
                
                # Process game turn
                print("\n🎲 Processing...")
                dm_response = self.play_turn(player_input)
                print(f"\n🎭 DM:")
                print(dm_response)
                # Empty line for console output
                
            except KeyboardInterrupt:
                print("\n\n💾 Saving game before exit...")
                self.save_game()
                print("👋 Game interrupted. Goodbye!")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                print("The game continues...")

    def _show_stats(self):
        """Enhanced stats display - read-only access to authoritative sources"""
        
        # COMPLIANCE: Get stats from authoritative GameEngine
        stats = self.get_game_stats()  # Uses existing method that accesses GameEngine
        
        print(f"\n📊 Game Statistics:")
        print(f"Location: {stats.get('location', 'Unknown')}")
        print(f"Turn: {self.turn_counter}")
        print(f"Session time: {stats.get('session_duration', 0):.1f}s")
        
        # UI state only
        if self.current_scenario:
            print(f"Current scenario: {self.current_scenario.get('scenario_type', 'Unknown')}")
            print(f"Choices available: {len(self.current_choices)}")
        
        # COMPLIANCE: Get analytics from SessionManager (persistence layer)
        session_stats = self.session_manager.get_session_statistics()
        routing_stats = self.session_manager.get_routing_statistics()
        if routing_stats["total_decisions"] > 0:
            print(f"Average routing confidence: {routing_stats['average_confidence']:.1%}")
    
    def _show_enhanced_help(self):
        """Enhanced help information"""
        
        print("\n📖 ENHANCED D&D GAME HELP:")
        # Empty line for console output
        print("📋 Commands:")
        print("  help     - Show this help")
        print("  save     - Save the game (enhanced format)")
        print("  stats    - Show detailed statistics")
        print("  quit     - Exit the game")
        # Empty line for console output
        print("💡 Note: To load a different game, exit and restart the application.")
        # Empty line for console output
        print("🎮 Enhanced Gameplay:")
        print("  • Try complex actions like 'search the ancient library for dragon lore'")
        print("  • Engage in detailed conversations: 'talk to the bartender about rumors'")
        print("  • Attempt skill-based actions: 'climb the castle wall stealthily'")
        print("  • Cast spells: 'cast fireball at the goblins'")
        print("  • The system will automatically determine appropriate skill checks!")
        # Empty line for console output


def main():
    """Main function to run the Haystack-integrated D&D game"""
    
    try:
        # Initialize game with enhanced setup system
        config = initialize_enhanced_dnd_game()
        
        # Create and run game with configuration
        game = HaystackDnDGame(config=config)
        game.run_interactive()
        
    except Exception as e:
        logger.error(f"Failed to start game: {e}")
        import traceback
        print(f"Full error: {traceback.format_exc()}")

if __name__ == "__main__":
    main()