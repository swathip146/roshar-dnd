"""
Game Initialization System - Haystack-Enhanced D&D Game Setup
Handles collection setup, saved game selection, and campaign selection
Uses Haystack framework for advanced document retrieval and processing
"""

import json
import os
import re
import time
from typing import Dict, Any, List, Optional, Tuple
from config.logging_config import get_logger

# Initialize logger
logger = get_logger(__name__)
from pathlib import Path
from dataclasses import dataclass, field

from haystack import Pipeline
from haystack.components.embedders import SentenceTransformersTextEmbedder
from haystack_integrations.document_stores.qdrant import QdrantDocumentStore
from haystack_integrations.components.retrievers.qdrant import QdrantEmbeddingRetriever
from haystack.dataclasses import ChatMessage
from haystack.components.agents import Agent
from haystack.tools import tool


from components.policy import PolicyEngine, PolicyProfile
from components.character_manager import CharacterManager, CharacterData
from components.session_manager import create_session_manager, SessionManager, GameSession
from components.game_engine import GameEngine, GameState
from components.campaign_config import CampaignConfig, create_default_campaign_config

from config.llm_config import get_global_config_manager
from storage.simple_document_store import SimpleDocumentStore


@dataclass
class GameInitConfig:
    """Enhanced configuration with fallback status tracking"""
    # Core required fields with sensible defaults
    collection_name: str = "dnd_documents"
    game_mode: str = "new_campaign"
    player_name: str = "Adventurer"
    
    # Optional enhanced fields
    campaign_config: Optional[CampaignConfig] = None
    save_file: Optional[str] = None
    shared_document_store: Optional[Any] = None
    selected_character_data: Optional[Dict[str, Any]] = None
    
    # Component instances (properly typed with actual classes)
    game_engine: Optional[GameEngine] = None
    character_manager: Optional[CharacterManager] = None
    session_manager: Optional[SessionManager] = None
    policy_engine: Optional[PolicyEngine] = None
    


class GameInitializationSystem:
    """
    Haystack-enhanced initialization system for D&D game
    Manages collection setup, saved games, and campaign selection
    """
    
    def __init__(self):
        """Initialize the game setup system"""
        self.saves_dir = "game_saves"
        self.simple_doc_store = None
        self.embedder = None
        self.document_store = None
        
        # Ensure game_saves directory exists
        os.makedirs(self.saves_dir, exist_ok=True)
    
    def initialize_game(self) -> GameInitConfig:
        """
        Main initialization flow - creates components and updates them as data becomes available
        """
        logger.info("🎮 ENHANCED D&D GAME INITIALIZATION")
        logger.info("=" * 60)
        logger.info("Welcome to the Haystack-enhanced D&D experience\!")
        logger.info("This system uses AI-powered document retrieval and scenario generation.")
        print()
        
        # Create initial configuration with defaults
        config = GameInitConfig()
        
        # Step 1: Create components with basic defaults immediately
        logger.info(f"🔧 Creating game components with defaults...")
        
        # Create PolicyEngine with default HOUSE profile
        config.policy_engine = PolicyEngine(PolicyProfile.HOUSE)
        logger.info(f"   ⚖️ PolicyEngine: ✅ Created with HOUSE profile")
        
        # Create CharacterManager with defaults
        config.character_manager = CharacterManager()
        logger.info(f"   👥 CharacterManager: ✅ Created")
        
        # Create SessionManager with default save directory
        config.session_manager = create_session_manager(save_directory="game_saves")
        logger.info(f"   📝 SessionManager: ✅ Created")
        
        # Create GameEngine with default profile (CampaignConfig will be set later)
        config.game_engine = GameEngine(policy_profile=PolicyProfile.HOUSE)
        print(f"   🎮 GameEngine: ✅ Created")
        
        # Step 2: Get collection name and initialize document system
        collection_name = self._prompt_for_collection_name()
        config.collection_name = collection_name
        self._initialize_document_system(collection_name)
        config.shared_document_store = self.simple_doc_store
        
        # Step 3: Choose game mode and handle data accordingly
        game_mode = self._prompt_for_game_mode()
        config.game_mode = game_mode
        
        if game_mode == "load_saved":
            # Handle saved game loading and update components
            save_file = self._prompt_for_saved_game()
            if save_file:
                config.save_file = save_file
                
                # Load saved game data and update components
                try:
                    result = config.session_manager.load_session(config.save_file)
                    if result["success"]:
                        session_data = result["result"]
                        
                        # Update player name from save
                        config.player_name = session_data.get("session_metadata", {}).get("player_name", "Adventurer")
                        logger.info(f"   👤 Player name loaded: {config.player_name}")
                        
                        # Restore GameEngine state if available
                        if ("orchestrator_state" in session_data and
                            "game_engine_state" in session_data["orchestrator_state"]):
                            try:
                                game_engine_state = session_data["orchestrator_state"]["game_engine_state"]
                                config.game_engine.import_game_state(game_engine_state)
                                print(f"   🎮 GameEngine: State restored from save")
                            except Exception as e:
                                logger.warning(f"   ⚠️ GameEngine restore failed: {e}")
                        
                        # Restore character data if available
                        if "character_data" in session_data:
                            try:
                                character_data = session_data["character_data"]
                                if isinstance(character_data, dict):
                                    char_id = config.character_manager.add_character(character_data)
                                    config.game_engine.add_character(char_id)
                                elif isinstance(character_data, list):
                                    for char_data in character_data:
                                        char_id = config.character_manager.add_character(char_data)
                                        config.game_engine.add_character(char_id)
                                logger.info(f"   👥 CharacterManager: Characters restored from save")
                            except Exception as e:
                                logger.warning(f"   ⚠️ Character restore failed: {e}")
                        
                        logger.info(f"   ✅ Saved game loaded successfully")
                    else:
                        logger.error(f"   ❌ Save load failed: {result.get('message', 'Unknown error')}")
                        print(f"   🆕 Falling back to new campaign")
                        config.game_mode = "new_campaign"
                        game_mode = "new_campaign"
                except Exception as e:
                    logger.error(f"   ❌ Save load exception: {e}")
                    print(f"   🆕 Falling back to new campaign")
                    config.game_mode = "new_campaign"
                    game_mode = "new_campaign"
            else:
                logger.warning(f"   ⚠️ No save file selected, using new campaign")
                config.game_mode = "new_campaign"
                game_mode = "new_campaign"
        
        if game_mode == "new_campaign":
            # NEW: Create immutable CampaignConfig instead of dict
            config.campaign_config = self._create_campaign_config()
            
            # Update PolicyEngine based on campaign difficulty
            if config.campaign_config.difficulty == "High":
                config.policy_engine.change_profile(PolicyProfile.RAW)
            elif config.campaign_config.difficulty == "Easy":
                config.policy_engine.change_profile(PolicyProfile.EASY)
            logger.info(f"   ⚖️ PolicyEngine: Updated for {config.campaign_config.difficulty} difficulty")
            
            # Get selected character
            selected_character_data = self._prompt_for_character_selection()
            config.player_name = selected_character_data["name"]
            config.selected_character_data = selected_character_data
            
            # BREAKING CHANGE: Update GameEngine with CampaignConfig
            config.game_engine.campaign_config = config.campaign_config
            print(f"   🎮 GameEngine: Updated with CampaignConfig")
            
            # COMPLIANCE: Use GameEngine as authoritative source - initialize all state through proper methods
            # Set location through GameEngine (authoritative)
            config.game_engine.set_location(
                config.campaign_config.starting_location,
                "campaign_start",
                config.campaign_config.story
            )
            
            # Set campaign flags through GameEngine (authoritative)
            config.game_engine.set_campaign_flag("campaign_active", True)
            config.game_engine.set_campaign_flag("current_campaign", config.campaign_config.name)
            config.game_engine.set_campaign_flag("document_collection", config.collection_name)
            config.game_engine.set_campaign_flag("created_time", time.time())
            
            # Initialize narrative context through GameEngine (authoritative)
            config.game_engine.update_narrative_context({
                "campaign_started": True,
                "opening_scene": "campaign_introduction",
                "current_scene": config.campaign_config.story[:200] + "..." if len(config.campaign_config.story) > 200 else config.campaign_config.story
            })
            
            # Add initial story hooks from campaign
            if hasattr(config.campaign_config, 'story_hooks'):
                for hook in config.campaign_config.story_hooks:
                    config.game_engine.add_story_hook(hook, "high")
            
            # Initialize quest context dynamically from campaign data
            self._initialize_quest_context_from_campaign(config)
            
            # COMPLIANCE: SessionManager needs initial state but GameEngine remains authoritative
            # Provide minimal initial state for session metadata while GameEngine manages runtime state
            initial_session_state = {
                "session_type": "new_campaign",
                "campaign_name": config.campaign_config.name,
                "starting_location": config.game_engine.get_location_context().get("location_name", "unknown"),
                "created_time": time.time(),
                "document_collection": config.collection_name
            }
            
            result = config.session_manager.create_new_session(
                player_name=config.player_name,
                initial_state=initial_session_state
            )
            
            if result["success"]:
                logger.info(f"   📝 SessionManager: New session created")
            else:
                logger.warning(f"   ⚠️ SessionManager: Session creation failed: {result.get('message')}")
            
            # Use selected character data instead of creating default
            character_data = selected_character_data
            
            # BREAKING CHANGE: Use CharacterManager as authority (SessionManager is persistence-only)
            # CharacterManager.add_character returns the character_id
            char_id = config.character_manager.add_character(character_data)
            
            # Add to GameEngine for runtime state management (GameEngine will also add to its CharacterManager)
            config.game_engine.add_character(character_data)
            
            logger.info(f"   👤 Created selected character: {config.player_name}")
        
        # Finalize setup
        print(f"\n✅ Game initialization complete!")
        print(f"   Player: {config.player_name}")
        print(f"   Mode: {config.game_mode}")
        print(f"   Collection: {config.collection_name}")
        print(f"   All components initialized and ready")
        
        return config
    
    def _create_campaign_config(self) -> CampaignConfig:
        """Create CampaignConfig from campaign selection - replaces old dict-based approach"""
        
        # Get available campaigns from file system
        campaigns = self._discover_file_campaigns()
        
        if not campaigns:
            logger.warning(f"⚠️ No campaign files found in docs/current_campaign directory.")
            print("   Creating default campaign.")
            return create_default_campaign_config()
        
        print("\n🗺️ Campaign Selection")
        print("-" * 40)
        print("Available campaign files:")
        for i, campaign in enumerate(campaigns, 1):
            print(f"{i}. 📁 {campaign['name']}")
            if campaign.get("description"):
                print(f"   📖 {campaign['description'][:100]}...")
            print(f"   📍 Source: {campaign['file_path']}")
        
        print()
        
        while True:
            try:
                choice = input(f"Select campaign (1-{len(campaigns)}): ").strip()
                
                if choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(campaigns):
                        selected_campaign = campaigns[idx]
                        logger.info(f"✅ Selected: {selected_campaign['name']}")
                        return self._parse_campaign_to_config(selected_campaign)
                    else:
                        logger.error(f"❌ Invalid selection. Please choose 1-{len(campaigns)}")
                else:
                    logger.error(f"❌ Invalid input. Please enter a number.")
                    
            except (KeyboardInterrupt, EOFError):
                print("\n⚠️ Using default campaign")
                return create_default_campaign_config()
     
    def _create_default_character(self, player_name: str, campaign_config: CampaignConfig) -> Dict[str, Any]:
        """Create a simple default D&D character with fixed values"""
        
        # Fixed default values - Level 1 Human Fighter
        level = 1
        proficiency_bonus = 2
        
        # Standard array ability scores
        ability_scores = {
            "strength": 15, "dexterity": 14, "constitution": 13,
            "intelligence": 12, "wisdom": 10, "charisma": 8
        }
        
        # Calculate ability modifiers
        ability_modifiers = {
            ability: (score - 10) // 2
            for ability, score in ability_scores.items()
        }
        
        # Fixed HP for level 1 Fighter: d10 + CON mod
        max_hp = 10 + ability_modifiers["constitution"]
        
        return {
            "character_id": "player",
            "name": player_name,
            "level": level,
            "proficiency_bonus": proficiency_bonus,
            "ability_scores": ability_scores,
            "ability_modifiers": ability_modifiers,
            "skills": {
                "perception": True,
                "athletics": True
            },
            "expertise_skills": [],
            "conditions": [],
            "features": ["Fighting Style", "Second Wind"],
            "hit_points": {
                "current": max_hp,
                "maximum": max_hp,
                "temporary": 0
            },
            "armor_class": 16,  # Chain mail
            "saving_throw_proficiencies": ["strength", "constitution"],
            "character_class": "Fighter",
            "race": "Human",
            "background": "Folk Hero",
            "spell_slots": {}
        }
    

    def _prompt_for_collection_name(self) -> str:
        """Prompt for Qdrant document collection name"""
        
        print("\n🗄️ Document Collection Setup")
        print("-" * 40)
        print("The enhanced D&D game uses document collections for")
        print("RAG-enhanced world knowledge and lore retrieval.")
        print()
        
        try:
            while True:
                try:
                    collection_name = input("Enter collection name (default: 'dnd_documents'): ").strip()
                    
                    # Default to "dnd_documents" if empty
                    if not collection_name:
                        return "dnd_documents"
                    
                    # Validate collection name format
                    if self._validate_collection_name(collection_name):
                        return collection_name
                    else:
                        logger.error(f"❌ Invalid collection name. Use letters, numbers, and underscores only.")
                        continue
                        
                except (KeyboardInterrupt, EOFError):
                    print("\n⚠️ Using default collection name: dnd_documents")
                    return "dnd_documents"
                    
        except Exception as e:
            logger.warning(f"⚠️ Error during collection setup, using default: dnd_documents")
            return "dnd_documents"
    
    def _validate_collection_name(self, name: str) -> bool:
        """Validate Qdrant collection name format"""
        # Qdrant collection names should be alphanumeric with underscores
        return bool(re.match(r'^[a-zA-Z0-9_]+$', name)) and len(name) > 0 and len(name) <= 64
    
    def _initialize_document_system(self, collection_name: str):
        """Initialize document system for campaign discovery using existing SimpleDocumentStore"""
        
        print(f"\n🔍 Initializing document system for collection: {collection_name}")
        try:
            # Use existing SimpleDocumentStore instead of creating duplicate initialization
            self.simple_doc_store = SimpleDocumentStore(collection_name=collection_name)
            
            # Extract the components we need for campaign discovery
            self.embedder = self.simple_doc_store.embedder
            self.document_store = self.simple_doc_store.document_store
            
            logger.info(f"✅ Document system ready for campaign discovery")
            
        except Exception as e:
            logger.warning(f"⚠️ Document system initialization failed: {e}")
            print("   Campaign selection will use default campaign only")
            self.document_store = None
    
    def _prompt_for_game_mode(self) -> str:
        """Prompt user to choose between new campaign or load saved game"""
        
        print("\n🎯 Game Mode Selection")
        print("-" * 40)
        
        # Check for available saved games
        saved_games = self._list_saved_games()
        
        print("Choose how you want to start:")
        print("1. 🆕 Start new campaign")
        if saved_games:
            print("2. 💾 Load saved game")
        print()
        
        while True:
            try:
                if saved_games:
                    choice = input("Enter your choice (1 for new, 2 for saved): ").strip()
                    if choice == "1":
                        return "new_campaign"
                    elif choice == "2":
                        return "load_saved"
                    else:
                        logger.error(f"❌ Invalid choice. Please enter 1 or 2.")
                else:
                    choice = input("Enter your choice (1 for new campaign): ").strip()
                    if choice == "1" or not choice:
                        return "new_campaign"
                    else:
                        logger.error(f"❌ Invalid choice. Please enter 1.")
                        
            except (KeyboardInterrupt, EOFError):
                print("\n⚠️ Defaulting to new campaign")
                return "new_campaign"
    
    def _list_saved_games(self) -> List[Dict[str, Any]]:
        """List available SessionManager format saved games only"""
        
        saved_games = []
        
        if not os.path.exists(self.saves_dir):
            return saved_games
        
        for filename in os.listdir(self.saves_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(self.saves_dir, filename)
                try:
                    with open(filepath, 'r') as f:
                        save_data = json.load(f)
                    
                    # Only accept SessionManager format saves
                    if not self._is_session_manager_save(save_data):
                        logger.warning(f"⚠️ Skipping legacy save file: {filename}")
                        continue
                    
                    # Extract metadata from SessionManager format
                    session_metadata = save_data["session_metadata"]
                    game_state = save_data.get("game_state", {})
                    
                    save_info = {
                        "filename": filename,
                        "player_name": session_metadata.get("player_name", "Unknown"),
                        "session_id": session_metadata.get("session_id", ""),
                        "location": game_state.get("location", "Unknown"),
                        "turns": len(game_state.get("history", [])),
                        "created_time": session_metadata.get("created_time", 0),
                        "save_time": session_metadata.get("last_save_time", 0),
                        "save_version": session_metadata.get("save_version", "2.0_haystack"),
                        "enhanced": True  # All SessionManager saves are enhanced
                    }
                    
                    saved_games.append(save_info)
                    
                except Exception as e:
                    logger.warning(f"⚠️ Could not read save file {filename}: {e}")
        
        # Sort by save time (most recent first)
        saved_games.sort(key=lambda x: x["save_time"], reverse=True)
        return saved_games
    
    def _is_session_manager_save(self, save_data: Dict[str, Any]) -> bool:
        """Check if save file is in SessionManager format"""
        
        # Must have session_metadata with required fields
        if "session_metadata" not in save_data:
            return False
            
        metadata = save_data["session_metadata"]
        required_fields = ["session_id", "player_name", "save_version"]
        
        for field in required_fields:
            if field not in metadata:
                return False
        
        # Must have game_state
        if "game_state" not in save_data:
            return False
            
        return True
    
    def _prompt_for_saved_game(self) -> str:
        """Prompt user to select a saved game"""
        
        print("\n💾 Saved Game Selection")
        print("-" * 40)
        
        saved_games = self._list_saved_games()
        
        if not saved_games:
            logger.error(f"❌ No saved games found. Starting new campaign instead.")
            return None
        
        print("Available saved games (SessionManager format only):")
        for i, save_info in enumerate(saved_games, 1):
            enhanced_flag = "✨"  # All SessionManager saves are enhanced
            save_time = time.strftime("%Y-%m-%d %H:%M", time.localtime(save_info["save_time"]))
            print(f"{i}. {enhanced_flag} {save_info['player_name']} - {save_info['location']}")
            print(f"   📅 {save_time} | 🎲 {save_info['turns']} turns | 🆔 {save_info['session_id'][:8]}...")
        
        print()
        
        while True:
            try:
                choice = input(f"Select save file (1-{len(saved_games)}) or press Enter to cancel: ").strip()
                
                if not choice:
                    return None
                
                if choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(saved_games):
                        selected_save = saved_games[idx]
                        logger.info(f"✅ Selected: {selected_save['filename']}")
                        return selected_save["filename"]
                    else:
                        logger.error(f"❌ Invalid selection. Please choose 1-{len(saved_games)}")
                else:
                    logger.error(f"❌ Invalid input. Please enter a number.")
                    
            except (KeyboardInterrupt, EOFError):
                print("\n⚠️ Save selection cancelled")
                return None
    
    def _parse_campaign_to_config(self, campaign: Dict[str, Any]) -> CampaignConfig:
        """Parse campaign file data and create CampaignConfig - replaces old dict approach"""
        
        try:
            if campaign["source"] == "file":
                # Use file content for comprehensive parsing
                raw_content = campaign.get("content", "")
                filename = campaign.get("filename", "")
                
                # Parse campaign data based on format
                parsed_data = self._parse_structured_content(raw_content)
                
                # Create CampaignConfig using factory method
                campaign_config = CampaignConfig.create_from_parsed_data(
                    parsed_data,
                    source_file=filename
                )
                
                logger.info(f"✅ Created CampaignConfig from {filename}")
                print(f"   📊 {len(campaign_config.key_npcs)} NPCs, {len(campaign_config.locations)} locations")
                
                return campaign_config
                
        except Exception as e:
            logger.warning(f"⚠️ Could not create CampaignConfig: {e}")
            import traceback
            traceback.print_exc()
        
        # Fallback to default campaign
        return create_default_campaign_config()
    
    def _discover_file_campaigns(self) -> List[Dict[str, Any]]:
        """Discover campaign files from docs/current_campaign directory"""
        
        campaigns = []
        campaign_dir = "docs/current_campaign"
        
        if not os.path.exists(campaign_dir):
            logger.warning(f"⚠️ Campaign directory {campaign_dir} not found")
            return campaigns
        
        try:
            # List all files in the campaign directory
            for filename in os.listdir(campaign_dir):
                if filename.startswith('.'):  # Skip hidden files
                    continue
                    
                file_path = os.path.join(campaign_dir, filename)
                
                # Skip directories
                if os.path.isdir(file_path):
                    continue
                
                try:
                    # Read file content
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Extract campaign name and description
                    campaign_name = self._extract_campaign_name_from_file(filename, content)
                    description = self._extract_description_from_content(content)
                    
                    campaign_info = {
                        "name": campaign_name,
                        "source": "file",
                        "file_path": file_path,
                        "filename": filename,
                        "description": description,
                        "content": content
                    }
                    
                    campaigns.append(campaign_info)
                    
                except Exception as e:
                    logger.warning(f"⚠️ Could not read campaign file {filename}: {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"⚠️ Could not read campaign directory: {e}")
        
        # Sort campaigns by filename for consistent ordering
        campaigns.sort(key=lambda x: x["filename"])
        return campaigns
    
    def _extract_campaign_name_from_file(self, filename: str, content: str) -> str:
        """Extract campaign name from file content or filename"""
        
        # Try to extract from content first
        # Look for title patterns in structured content
        if "TITLE:" in content:
            for line in content.split('\n'):
                if line.strip().startswith("TITLE:"):
                    return line.split("TITLE:", 1)[1].strip()
        
        # Look for campaign name patterns
        if "CAMPAIGN:" in content:
            for line in content.split('\n'):
                if line.strip().startswith("CAMPAIGN:"):
                    return line.split("CAMPAIGN:", 1)[1].strip()
        
        # Try JSON format (for .json files)
        if filename.endswith('.json'):
            try:
                # Try to parse if it looks like JSON
                if content.strip().startswith('{'):
                    data = json.loads(content)
                    if 'title' in data:
                        return data['title']
                    elif 'name' in data:
                        return data['name']
            except:
                pass
        
        # Extract from filename as fallback
        name = filename.replace('.json', '').replace('.txt', '').replace('.md', '')
        name = name.replace('_', ' ').replace(':', ' - ')
        return name.title()
    
    def _extract_description_from_content(self, content: str) -> str:
        """Extract a brief description from campaign content"""
        
        # Try JSON format first
        if content.strip().startswith('{'):
            try:
                data = json.loads(content)
                if 'overview' in data:
                    return str(data['overview'])[:200]
                elif 'description' in data:
                    return str(data['description'])[:200]
            except:
                pass
        
        # Look for overview sections in structured text
        if "=== CAMPAIGN OVERVIEW ===" in content:
            lines = content.split('\n')
            in_overview = False
            overview_lines = []
            
            for line in lines:
                if line.strip() == "=== CAMPAIGN OVERVIEW ===":
                    in_overview = True
                    continue
                elif line.strip().startswith("=== ") and in_overview:
                    break
                elif in_overview and line.strip():
                    if not line.startswith("CHUNK_TYPE:") and not line.startswith("CAMPAIGN:"):
                        overview_lines.append(line.strip())
            
            if overview_lines:
                return " ".join(overview_lines)[:200]
        
        # Fallback - use first few lines of content
        lines = [line.strip() for line in content.split('\n')[:5] if line.strip()]
        if lines:
            return " ".join(lines)[:200]
        
        return "Campaign file"
    
    
    def _parse_structured_content(self, content: str) -> Dict[str, Any]:
        """Parse campaign content from various formats (JSON, structured text, etc.)"""
        
        parsed_data = {}
        
        try:
            # Try JSON parsing first
            if content.strip().startswith("{"):
                import json
                parsed_data = json.loads(content)
                return parsed_data
        except json.JSONDecodeError:
            pass
        
        # Enhanced parsing for structured text format (like the Shards of Honor vectordb.txt)
        lines = content.split('\n')
        current_section = None
        current_content = []
        
        for line in lines:
            line = line.strip()
            
            # Detect section headers (=== SECTION NAME ===)
            if line.startswith("=== ") and line.endswith(" ==="):
                # Save previous section
                if current_section and current_content:
                    parsed_data[current_section] = '\n'.join(current_content).strip()
                
                # Start new section - clean up section name
                section_name = line.replace("=== ", "").replace(" ===", "").lower()
                current_section = section_name
                current_content = []
                
            # Extract standalone metadata fields at file level
            elif line.startswith("TITLE:") or line.startswith("THEME:") or line.startswith("SETTING:") or \
                 line.startswith("DIFFICULTY:") or line.startswith("STARTING_LOCATION:") or \
                 line.startswith("LEVEL_RANGE:") or line.startswith("RECOMMENDED_PARTY_SIZE:"):
                key, value = line.split(":", 1)
                parsed_data[key.lower()] = value.strip()
                
            elif current_section and line:
                current_content.append(line)
        
        # Save final section
        if current_section and current_content:
            parsed_data[current_section] = '\n'.join(current_content).strip()
        
        # Debug: Print what we parsed for troubleshooting
        logger.info(f"🔍 Parsed {len(parsed_data)} sections from campaign content")
        section_names = list(parsed_data.keys())[:10]  # First 10 section names
        print(f"   📋 Sections found: {', '.join(section_names)}")
        
        return parsed_data
    
    
    def _initialize_quest_context_from_campaign(self, config: GameInitConfig):
        """Initialize quest context dynamically from campaign data using GameEngine methods"""
        
        if not config.campaign_config or not config.game_engine:
            print("   ⚠️ Quest initialization skipped: missing campaign or game engine")
            return
        
        campaign = config.campaign_config
        engine = config.game_engine
        
        print(f"   🎯 Initializing quest context from campaign: {campaign.name}")
        
        # 1. Set up main campaign quest if quests exist
        if campaign.quests:
            main_quest = campaign.quests[0]  # Use first quest as main
            engine.update_quest_context({
                "active_quests": [main_quest],
                "main_quest_name": main_quest
            })
            
            # Add first quest objective dynamically
            if len(campaign.quests) > 1:
                engine.add_quest_objective(f"Begin: {campaign.quests[1]}", main_quest)
            else:
                engine.add_quest_objective("Explore and discover your purpose", main_quest)
            
            print(f"     ✓ Main quest set: {main_quest}")
        
        # 2. Set time pressure based on campaign difficulty
        time_pressure = "moderate"  # Default
        if campaign.difficulty == "High":
            time_pressure = "urgent"
        elif campaign.difficulty == "Easy":
            time_pressure = "relaxed"
        
        # 3. Set consequences and rewards based on campaign difficulty
        consequences = []
        rewards = []
        
        # Determine consequences based on campaign context
        if "war" in campaign.theme.lower() or "crisis" in campaign.theme.lower():
            consequences = ["Regional instability", "Lives at stake"]
        elif "mystery" in campaign.theme.lower() or "investigation" in campaign.theme.lower():
            consequences = ["Truth remains hidden", "Corruption spreads"]
        else:
            consequences = ["Opportunity lost", "Local problems persist"]
        
        # Use campaign rewards if available, otherwise generate based on difficulty
        if campaign.rewards:
            rewards = campaign.rewards[:3]  # Use up to 3 campaign rewards
        else:
            if campaign.difficulty == "High":
                rewards = ["Legendary artifact", "Noble title", "Substantial gold"]
            elif campaign.difficulty == "Easy":
                rewards = ["Magic item", "Local recognition", "Modest reward"]
            else:
                rewards = ["Magical equipment", "Regional fame", "Fair compensation"]
        
        # 4. Add campaign hooks as quest constraints or opportunities
        quest_constraints = []
        if campaign.campaign_hooks:
            # Use first hook as a constraint or opportunity
            first_hook = campaign.campaign_hooks[0][:100]  # Limit length
            quest_constraints = [f"Opportunity: {first_hook}"]
        
        # 5. Update quest context with derived information (no quest_giver or theme)
        quest_context_updates = {
            "time_pressure": time_pressure,
            "consequences": consequences,
            "rewards": rewards,
            "quest_constraints": quest_constraints,
            "quest_source": "campaign_derived"
        }
        
        engine.update_quest_context(quest_context_updates)
        
        # 6. Add story hooks from campaign as potential quest leads
        if campaign.campaign_hooks:
            for hook in campaign.campaign_hooks[:2]:  # Add up to 2 hooks
                engine.add_story_hook(hook, "normal")
        
        print(f"     ✓ Time pressure: {time_pressure}")
        print(f"     ✓ Rewards configured: {len(rewards)} items")
        print(f"     ✓ Story hooks added: {len(campaign.campaign_hooks[:2])}")
    
    def _prompt_for_character_selection(self) -> Dict[str, Any]:
        """Prompt for character selection from predefined list"""
        
        print("\n👤 Character Selection")
        print("-" * 40)
        print("Choose your character:")
        print("1. 🌟 Aggi - Alethi Lightweaver (Folk Hero)")
        print("   Level 1 Radiant with strong sense of justice")
        print("2. 🌟 Kali - Azish Lightweaver (Hermit)")
        print("   Level 1 Radiant who follows their chosen path")
        print()
        
        # Predefined character data
        characters = {
            "1": {
                "name": "Aggi",
                "character_id": "Aggi",
                "race": "Alethi",
                "identity": "Alethi",
                "character_class": "Radiant",
                "radiant_order": "Lightweaver",
                "level": 1,
                "background": "Folk Hero",
                "rulebook": "Cosmere 5e (Roshar)",
                "ability_scores": {
                    "strength": 8,
                    "dexterity": 11,
                    "constitution": 11,
                    "intelligence": 8,
                    "wisdom": 6,
                    "charisma": 13
                },
                "hit_points": {"current": 8, "maximum": 8, "temporary": 0},
                "armor_class": 10,
                "proficiency_bonus": 2,
                "languages": ["Common", "Alethi"],
                "equipment": [],
                "personality": {
                    "traits": ["Stands up for the common people", "Strong sense of justice"],
                    "ideals": ["Justice and personal growth"],
                    "bonds": ["Connected to folk hero background and alethi heritage"],
                    "flaws": ["Sometimes too focused on goals to consider consequences"]
                },
                "backstory": "A Alethi Radiant who stands up for the common people and has a strong sense of justice.",
                "speed": 30,
                "investiture_points": {"current": 3, "maximum": 5},
                "spren": {"type": "Cryptic", "name": None, "status": "active"},
                "surges_known": ["Illumination", "Transformation"],
                "cantrips_known": [],
                "spells_known": [],
                "skills": {},
                "expertise_skills": [],
                "conditions": [],
                "features": ["Spellcasting", "Investiture Points", "Spren Bond"],
                "saving_throw_proficiencies": []
            },
            "2": {
                "name": "Kali",
                "character_id": "Kali",
                "race": "Azish",
                "identity": "Azish",
                "character_class": "Radiant",
                "radiant_order": "Lightweaver",
                "level": 1,
                "background": "Hermit",
                "rulebook": "Cosmere 5e (Roshar)",
                "ability_scores": {
                    "strength": 11,
                    "dexterity": 15,
                    "constitution": 16,
                    "intelligence": 13,
                    "wisdom": 12,
                    "charisma": 14
                },
                "hit_points": {"current": 11, "maximum": 11, "temporary": 0},
                "armor_class": 12,
                "proficiency_bonus": 2,
                "languages": ["Common", "Azish", "Common Script", "Common Glyphs"],
                "equipment": [
                    "Herbalism kit",
                    "Scroll case with spiritual writings",
                    "Winter blanket",
                    "Artisan's tools",
                    "Belt pouch",
                    "Common clothes"
                ],
                "personality": {
                    "traits": ["Follows their chosen path", "Pursues their goals"],
                    "ideals": ["Justice and personal growth"],
                    "bonds": ["Connected to hermit background and azish heritage"],
                    "flaws": ["Sometimes too focused on goals to consider consequences"]
                },
                "backstory": "An Azish Radiant who follows their chosen path and pursues their goals.",
                "speed": 30,
                "investiture_points": {"current": 4, "maximum": 6},
                "spren": {"type": "Cryptic", "name": None, "status": "active"},
                "surges_known": ["Illumination", "Transformation"],
                "cantrips_known": [],
                "spells_known": [],
                "skills": {},
                "expertise_skills": [],
                "conditions": [],
                "features": ["Spellcasting", "Investiture Points", "Spren Bond"],
                "saving_throw_proficiencies": [],
                "tool_proficiencies": ["Herbalism kit"]
            }
        }
        
        while True:
            try:
                choice = input("Select your character (1 or 2): ").strip()
                
                if choice in characters:
                    selected_character = characters[choice]
                    logger.info(f"✅ Selected: {selected_character['name']} ({selected_character['identity']} {selected_character['radiant_order']})")
                    return selected_character
                else:
                    logger.error(f"❌ Invalid choice. Please enter 1 or 2.")
                    
            except (KeyboardInterrupt, EOFError):
                print("\n⚠️ Defaulting to Aggi")
                return characters["1"]

# Convenience function for main game initialization
def initialize_enhanced_dnd_game() -> GameInitConfig:
    """
    Initialize enhanced D&D game with full Haystack integration
    Returns configuration for game startup
    """
    
    init_system = GameInitializationSystem()
    return init_system.initialize_game()


# Example usage and testing
if __name__ == "__main__":
    print("🧪 Testing Game Initialization System")
    
    try:
        config = initialize_enhanced_dnd_game()
        
        print("\n🎯 Initialization Results:")
        print(f"Collection: {config.collection_name}")
        print(f"Mode: {config.game_mode}")
        
        if config.game_mode == "new_campaign":
            campaign_name = config.campaign_config.name if config.campaign_config else "Unknown"
            print(f"Campaign: {campaign_name}")
            print(f"Player: {config.player_name}")
        elif config.game_mode == "load_saved":
            print(f"Save file: {config.save_file}")
            
    except Exception as e:
        logger.error(f"❌ Initialization test failed: {e}")