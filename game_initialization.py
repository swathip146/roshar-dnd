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
from pathlib import Path
from dataclasses import dataclass

from haystack import Pipeline
from haystack.components.embedders import SentenceTransformersTextEmbedder
from haystack_integrations.document_stores.qdrant import QdrantDocumentStore
from haystack_integrations.components.retrievers.qdrant import QdrantEmbeddingRetriever
from haystack.dataclasses import ChatMessage
from haystack.components.agents import Agent
from haystack.tools import tool

from config.llm_config import get_global_config_manager


@dataclass
class GameInitConfig:
    """Configuration for game initialization"""
    collection_name: str
    game_mode: str  # "new_campaign" or "load_saved"
    campaign_data: Optional[Dict[str, Any]] = None
    save_file: Optional[str] = None
    player_name: Optional[str] = None


class GameInitializationSystem:
    """
    Haystack-enhanced initialization system for D&D game
    Manages collection setup, saved games, and campaign selection
    """
    
    def __init__(self):
        """Initialize the game setup system"""
        self.saves_dir = "game_saves"
        self.embedder = None
        self.document_store = None
        
        # Ensure game_saves directory exists
        os.makedirs(self.saves_dir, exist_ok=True)
    
    def initialize_game(self) -> GameInitConfig:
        """
        Main initialization flow - returns complete game configuration
        """
        print("🎮 ENHANCED D&D GAME INITIALIZATION")
        print("=" * 60)
        print("Welcome to the Haystack-enhanced D&D experience!")
        print("This system uses AI-powered document retrieval and scenario generation.")
        print()
        
        # Step 1: Get collection name
        collection_name = self._prompt_for_collection_name()
        
        # Step 2: Initialize document system for campaign discovery
        self._initialize_document_system(collection_name)
        
        # Step 3: Choose game mode (new campaign or load saved)
        game_mode = self._prompt_for_game_mode()
        
        if game_mode == "load_saved":
            save_file = self._prompt_for_saved_game()
            return GameInitConfig(
                collection_name=collection_name,
                game_mode="load_saved",
                save_file=save_file
            )
        else:
            # New campaign flow
            campaign_data = self._prompt_for_campaign_selection()
            player_name = self._prompt_for_player_name()
            
            return GameInitConfig(
                collection_name=collection_name,
                game_mode="new_campaign",
                campaign_data=campaign_data,
                player_name=player_name
            )
    
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
                        print("❌ Invalid collection name. Use letters, numbers, and underscores only.")
                        continue
                        
                except (KeyboardInterrupt, EOFError):
                    print("\n⚠️ Using default collection name: dnd_documents")
                    return "dnd_documents"
                    
        except Exception as e:
            print(f"⚠️ Error during collection setup, using default: dnd_documents")
            return "dnd_documents"
    
    def _validate_collection_name(self, name: str) -> bool:
        """Validate Qdrant collection name format"""
        # Qdrant collection names should be alphanumeric with underscores
        return bool(re.match(r'^[a-zA-Z0-9_]+$', name)) and len(name) > 0 and len(name) <= 64
    
    def _initialize_document_system(self, collection_name: str):
        """Initialize document system for campaign discovery"""
        
        print(f"\n🔍 Initializing document system for collection: {collection_name}")
        try:
            # Initialize embedder
            self.embedder = SentenceTransformersTextEmbedder(
                model="sentence-transformers/all-MiniLM-L6-v2"
            )
            self.embedder.warm_up()
            
            # Initialize document store (temporary for campaign discovery)
            storage_path = f"temp_init_{collection_name}_{int(time.time())}"
            self.document_store = QdrantDocumentStore(
                path=storage_path,
                index=collection_name,
                embedding_dim=384,
                recreate_index=False  # Don't recreate if exists
            )
            
            print("✅ Document system ready for campaign discovery")
            
        except Exception as e:
            print(f"⚠️ Document system initialization failed: {e}")
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
                        print("❌ Invalid choice. Please enter 1 or 2.")
                else:
                    choice = input("Enter your choice (1 for new campaign): ").strip()
                    if choice == "1" or not choice:
                        return "new_campaign"
                    else:
                        print("❌ Invalid choice. Please enter 1.")
                        
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
                        print(f"⚠️ Skipping legacy save file: {filename}")
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
                    print(f"⚠️ Could not read save file {filename}: {e}")
        
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
            print("❌ No saved games found. Starting new campaign instead.")
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
                        print(f"✅ Selected: {selected_save['filename']}")
                        return selected_save["filename"]
                    else:
                        print(f"❌ Invalid selection. Please choose 1-{len(saved_games)}")
                else:
                    print("❌ Invalid input. Please enter a number.")
                    
            except (KeyboardInterrupt, EOFError):
                print("\n⚠️ Save selection cancelled")
                return None
    
    def _prompt_for_campaign_selection(self) -> Dict[str, Any]:
        """Prompt user to select available campaign using Haystack retrieval from Qdrant"""
        
        print("\n🗺️ Campaign Selection")
        print("-" * 40)
        
        # Get available campaigns from Qdrant collection only
        campaigns = []
        
        if self.document_store:
            qdrant_campaigns = self._discover_qdrant_campaigns()
            campaigns.extend(qdrant_campaigns)
        else:
            print("⚠️ Document store not available. Cannot retrieve campaigns from Qdrant.")
        
        if not campaigns:
            print("⚠️ No campaigns found in Qdrant collection. Using default campaign setup.")
            return self._create_default_campaign()
        
        print("Available campaigns from Qdrant collection:")
        for i, campaign in enumerate(campaigns, 1):
            print(f"{i}. 🗄️ {campaign['name']}")
            if campaign.get("description"):
                print(f"   📖 {campaign['description'][:100]}...")
            print(f"   📍 Source: Qdrant collection")
        
        print()
        
        while True:
            try:
                choice = input(f"Select campaign (1-{len(campaigns)}): ").strip()
                
                if choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(campaigns):
                        selected_campaign = campaigns[idx]
                        print(f"✅ Selected: {selected_campaign['name']}")
                        return self._load_campaign_data(selected_campaign)
                    else:
                        print(f"❌ Invalid selection. Please choose 1-{len(campaigns)}")
                else:
                    print("❌ Invalid input. Please enter a number.")
                    
            except (KeyboardInterrupt, EOFError):
                print("\n⚠️ Using default campaign")
                return self._create_default_campaign()
    
    
    def _discover_qdrant_campaigns(self) -> List[Dict[str, Any]]:
        """Discover campaigns from Qdrant collection with resources/current_campaign tags"""
        
        campaigns = []
        
        if not self.document_store:
            return campaigns
        
        try:
            # Use retriever to find documents with campaign tags
            retriever = QdrantEmbeddingRetriever(
                document_store=self.document_store,
                top_k=10  # Get up to 10 campaigns
            )
            
            # Create search query for campaign documents
            campaign_query = "campaign resources current_campaign"
            query_embedding = self.embedder.run(text=campaign_query)["embedding"]
            
            # Retrieve campaign documents
            retrieved_docs = retriever.run(
                query_embedding=query_embedding,
                filters={
                    "must": [
                        {"key": "type", "match": {"value": "campaign"}},
                        {"key": "source", "match": {"any": ["resources", "current_campaign"]}}
                    ]
                }
            )
            
            for doc in retrieved_docs.get("documents", []):
                campaign_info = {
                    "name": doc.meta.get("name", "Unknown Campaign"),
                    "source": "qdrant",
                    "document_id": doc.id,
                    "description": doc.content[:200] if doc.content else "",
                    "metadata": doc.meta
                }
                campaigns.append(campaign_info)
                
        except Exception as e:
            print(f"⚠️ Could not search Qdrant for campaigns: {e}")
        
        return campaigns
    
    
    def _load_campaign_data(self, campaign: Dict[str, Any]) -> Dict[str, Any]:
        """Load comprehensive campaign data from selected Qdrant campaign with enhanced field extraction"""
        
        try:
            if campaign["source"] == "qdrant":
                # Extract raw content for parsing
                raw_content = campaign.get("description", "")
                metadata = campaign.get("metadata", {})
                
                # Parse campaign data based on format
                parsed_data = self._parse_campaign_content(raw_content)
                
                # Build comprehensive campaign configuration
                campaign_config = {
                    "name": campaign.get("name", "Unknown Campaign"),
                    "description": self._extract_field(parsed_data, ["overview", "description"], raw_content[:300]),
                    "story": self._extract_story_content(parsed_data, raw_content),
                    "metadata": metadata,
                    "source": "qdrant_collection",
                    
                    # Game Configuration Fields
                    "level_range": self._extract_field(parsed_data, ["level_range", "LEVEL_RANGE"], "1-5"),
                    "starting_location": self._extract_starting_location(parsed_data),
                    "session_count": self._extract_session_count(parsed_data),
                    "theme": self._extract_field(parsed_data, ["theme", "THEME"], "Fantasy Adventure"),
                    "setting": self._extract_field(parsed_data, ["setting", "SETTING"], "Fantasy World"),
                    
                    # Character Creation Guidance
                    "difficulty": self._assess_campaign_difficulty(parsed_data),
                    "recommended_party_size": self._extract_party_size(parsed_data),
                    
                    # Story Elements
                    "main_plot": self._extract_field(parsed_data, ["main_plot", "MAIN PLOT"], ""),
                    "campaign_hooks": self._extract_hooks(parsed_data),
                    "key_npcs": self._extract_npcs(parsed_data),
                    "locations": self._extract_locations(parsed_data),
                    "encounters": self._extract_encounters(parsed_data),
                    
                    # Rewards and Progression
                    "rewards": self._extract_rewards(parsed_data),
                    "treasure_types": self._extract_treasure_types(parsed_data),
                    
                    # DM Information
                    "dm_notes": self._extract_field(parsed_data, ["dm_notes", "DM NOTES"], ""),
                    "generated_on": self._extract_field(parsed_data, ["generated_on", "GENERATED_ON"], ""),
                    
                    # Enhanced Game Features
                    "enhanced_features": {
                        "rag_enhanced": True,
                        "has_structured_content": len(parsed_data) > 3,
                        "content_complexity": self._assess_content_complexity(parsed_data),
                        "npc_count": len(self._extract_npcs(parsed_data)),
                        "location_count": len(self._extract_locations(parsed_data))
                    }
                }
                
                return campaign_config
                
        except Exception as e:
            print(f"⚠️ Could not load campaign data: {e}")
        
        return self._create_default_campaign()
    
    def _parse_campaign_content(self, content: str) -> Dict[str, Any]:
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
        
        # Parse structured text format (like the Shards of Honor campaign)
        lines = content.split('\n')
        current_section = None
        current_content = []
        
        for line in lines:
            line = line.strip()
            
            # Detect section headers
            if line.startswith("=== ") and line.endswith(" ==="):
                # Save previous section
                if current_section and current_content:
                    parsed_data[current_section] = '\n'.join(current_content).strip()
                
                # Start new section
                current_section = line.replace("=== ", "").replace(" ===", "").lower()
                current_content = []
                
            elif line.startswith("TITLE:") or line.startswith("THEME:") or line.startswith("SETTING:"):
                # Extract metadata fields
                key, value = line.split(":", 1)
                parsed_data[key.lower()] = value.strip()
                
            elif current_section and line:
                current_content.append(line)
        
        # Save final section
        if current_section and current_content:
            parsed_data[current_section] = '\n'.join(current_content).strip()
        
        return parsed_data
    
    def _extract_field(self, data: Dict[str, Any], field_names: List[str], default: str = "") -> str:
        """Extract field value from parsed data using multiple possible field names"""
        
        for field_name in field_names:
            if field_name in data and data[field_name]:
                return str(data[field_name])
        
        return default
    
    def _extract_story_content(self, data: Dict[str, Any], raw_content: str) -> str:
        """Extract the main story/opening content for game initialization"""
        
        # Try to find campaign overview or background
        story_sources = [
            "campaign overview", "overview", "campaign background", "background",
            "main_plot", "story", "description"
        ]
        
        for source in story_sources:
            if source in data and data[source]:
                content = data[source]
                # Clean up and format for game opening
                if len(content) > 500:
                    # Take first paragraph for opening
                    content = content.split('\n')[0]
                return content
        
        # Fallback to default tavern opening
        return "You enter a bustling tavern filled with adventurers, merchants, and locals. The air is thick with pipe smoke and the aroma of roasted meat. A fire crackles in the hearth, casting dancing shadows on weathered faces."
    
    def _extract_starting_location(self, data: Dict[str, Any]) -> str:
        """Extract or infer starting location from campaign data"""
        
        # Look for explicit starting location
        location_hints = ["starting_location", "start_location", "beginning"]
        for hint in location_hints:
            if hint in data:
                return data[hint]
        
        # Extract from locations list
        if "locations" in data:
            locations = data["locations"]
            if isinstance(locations, list) and locations:
                first_location = locations[0]
                if isinstance(first_location, dict):
                    return first_location.get("name", "Tavern")
                return str(first_location).split('\n')[0] if first_location else "Tavern"
        
        # Look in content for location mentions
        content_text = str(data.get("campaign overview", "")).lower()
        common_starting_locations = ["tavern", "village", "town", "city", "inn", "crossroads"]
        
        for location in common_starting_locations:
            if location in content_text:
                return location.title()
        
        return "Tavern"
    
    def _extract_session_count(self, data: Dict[str, Any]) -> int:
        """Extract estimated session count from campaign data"""
        
        # Look for explicit session count
        session_fields = ["session_count", "sessions", "duration"]
        for field in session_fields:
            if field in data:
                value = str(data[field])
                # Extract number from strings like "5 sessions" or "25-30 sessions"
                import re
                numbers = re.findall(r'\d+', value)
                if numbers:
                    return int(numbers[0])
        
        # Estimate based on level range
        level_range = self._extract_field(data, ["level_range", "LEVEL_RANGE"], "1-5")
        if "-" in level_range:
            try:
                start_level, end_level = level_range.split("-")
                level_span = int(end_level) - int(start_level)
                return max(5, level_span * 2)  # Rough estimate: 2 sessions per level
            except:
                pass
        
        return 10  # Default estimate
    
    def _assess_campaign_difficulty(self, data: Dict[str, Any]) -> str:
        """Assess campaign difficulty based on content analysis"""
        
        content_text = str(data).lower()
        
        # High difficulty indicators
        high_difficulty_terms = ["deadly", "very hard", "epic", "legendary", "ancient", "god", "desolation", "apocalypse"]
        medium_difficulty_terms = ["hard", "challenging", "dangerous", "adventure", "quest"]
        easy_difficulty_terms = ["easy", "beginner", "simple", "peaceful", "village"]
        
        high_count = sum(1 for term in high_difficulty_terms if term in content_text)
        medium_count = sum(1 for term in medium_difficulty_terms if term in content_text)
        easy_count = sum(1 for term in easy_difficulty_terms if term in content_text)
        
        if high_count >= 2:
            return "High"
        elif medium_count >= 3 or high_count >= 1:
            return "Medium"
        elif easy_count >= 2:
            return "Easy"
        else:
            return "Medium"  # Default
    
    def _extract_party_size(self, data: Dict[str, Any]) -> str:
        """Extract recommended party size"""
        
        content_text = str(data).lower()
        
        if "single player" in content_text or "solo" in content_text:
            return "1 player"
        elif "large group" in content_text or "6+" in content_text:
            return "5-6 players"
        else:
            return "3-5 players"  # Standard D&D party
    
    def _extract_npcs(self, data: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract key NPCs from campaign data"""
        
        npcs = []
        
        # Look for NPCs in various formats
        if "npcs" in data or "key_npcs" in data:
            npc_data = data.get("npcs", data.get("key_npcs", []))
            if isinstance(npc_data, list):
                for npc in npc_data:
                    if isinstance(npc, dict):
                        npcs.append({
                            "name": npc.get("name", "Unknown NPC"),
                            "role": npc.get("role", npc.get("NPC_ROLE", "Unknown")),
                            "description": npc.get("description", npc.get("DESCRIPTION", ""))
                        })
        
        # Extract from structured text format
        for key, value in data.items():
            if "npc:" in key.lower():
                npc_name = key.replace("npc: ", "").replace("NPC: ", "")
                npcs.append({
                    "name": npc_name,
                    "role": "Important NPC",
                    "description": str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
                })
        
        return npcs[:6]  # Limit to top 6 NPCs
    
    def _extract_locations(self, data: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract key locations from campaign data"""
        
        locations = []
        
        if "locations" in data:
            location_data = data["locations"]
            if isinstance(location_data, list):
                for location in location_data:
                    if isinstance(location, dict):
                        locations.append({
                            "name": location.get("name", location.get("LOCATION_NAME", "Unknown Location")),
                            "type": location.get("type", location.get("LOCATION_TYPE", "Unknown")),
                            "description": location.get("description", location.get("DESCRIPTION", ""))
                        })
        
        # Extract from structured text format
        for key, value in data.items():
            if "location:" in key.lower():
                location_name = key.replace("location: ", "").replace("LOCATION: ", "")
                locations.append({
                    "name": location_name,
                    "type": "Campaign Location",
                    "description": str(value)[:150] + "..." if len(str(value)) > 150 else str(value)
                })
        
        return locations[:5]  # Limit to top 5 locations
    
    def _extract_encounters(self, data: Dict[str, Any]) -> List[str]:
        """Extract key encounters from campaign data"""
        
        encounters = []
        
        if "encounters" in data:
            encounter_data = data["encounters"]
            if isinstance(encounter_data, list):
                for encounter in encounter_data:
                    if isinstance(encounter, dict):
                        title = encounter.get("title", encounter.get("ENCOUNTER_TITLE", "Unknown Encounter"))
                        encounters.append(title)
                    else:
                        encounters.append(str(encounter))
        
        # Extract from structured text format
        for key, value in data.items():
            if "encounter:" in key.lower():
                encounter_name = key.replace("encounter: ", "").replace("ENCOUNTER: ", "")
                encounters.append(encounter_name)
        
        return encounters[:8]  # Limit to top 8 encounters
    
    def _extract_hooks(self, data: Dict[str, Any]) -> List[str]:
        """Extract campaign hooks for player engagement"""
        
        hooks = []
        
        if "hooks" in data or "campaign hooks" in data:
            hook_data = data.get("hooks", data.get("campaign hooks", []))
            if isinstance(hook_data, list):
                hooks.extend([str(hook) for hook in hook_data])
            elif isinstance(hook_data, str):
                # Split by common separators
                hooks.extend([hook.strip() for hook in hook_data.split('\n') if hook.strip()])
        
        # Extract numbered hooks from structured format
        for key, value in data.items():
            if "hook_" in key.lower():
                hooks.append(str(value))
        
        return hooks[:4]  # Limit to top 4 hooks
    
    def _extract_rewards(self, data: Dict[str, Any]) -> List[str]:
        """Extract campaign rewards information"""
        
        rewards = []
        
        if "rewards" in data:
            reward_data = data["rewards"]
            if isinstance(reward_data, list):
                rewards.extend([str(reward) for reward in reward_data])
            elif isinstance(reward_data, str):
                rewards.extend([reward.strip() for reward in reward_data.split('\n') if reward.strip()])
        
        # Extract numbered rewards from structured format
        for key, value in data.items():
            if "reward_" in key.lower():
                rewards.append(str(value))
        
        return rewards[:5]  # Limit to top 5 rewards
    
    def _extract_treasure_types(self, data: Dict[str, Any]) -> List[str]:
        """Infer treasure types from campaign content"""
        
        content_text = str(data).lower()
        treasure_types = []
        
        # Detect treasure themes from content
        if "magic" in content_text or "artifact" in content_text or "enchanted" in content_text:
            treasure_types.append("Magical Items")
        
        if "gold" in content_text or "coin" in content_text or "treasure" in content_text:
            treasure_types.append("Monetary Rewards")
        
        if "weapon" in content_text or "sword" in content_text or "armor" in content_text:
            treasure_types.append("Weapons & Armor")
        
        if "knowledge" in content_text or "lore" in content_text or "secret" in content_text:
            treasure_types.append("Knowledge & Lore")
        
        if "ally" in content_text or "friend" in content_text or "companion" in content_text:
            treasure_types.append("Allies & Contacts")
        
        return treasure_types if treasure_types else ["Standard Treasure"]
    
    def _assess_content_complexity(self, data: Dict[str, Any]) -> str:
        """Assess the complexity of campaign content for RAG enhancement"""
        
        total_content = sum(len(str(value)) for value in data.values())
        section_count = len(data)
        
        if total_content > 5000 and section_count > 10:
            return "Very High"
        elif total_content > 2000 and section_count > 5:
            return "High"
        elif total_content > 500 and section_count > 3:
            return "Medium"
        else:
            return "Basic"
    
    def _create_default_campaign(self) -> Dict[str, Any]:
        """Create default campaign if no campaigns are found"""
        
        return {
            "name": "The Forgotten Realms Adventure",
            "description": "A classic D&D adventure in the Forgotten Realms setting.",
            "story": "You enter a bustling tavern filled with adventurers, merchants, and locals. The air is thick with pipe smoke and the aroma of roasted meat. A fire crackles in the hearth, casting dancing shadows on weathered faces.",
            "location": "Tavern",
            "source": "default"
        }
    
    
    def _prompt_for_player_name(self) -> str:
        """Prompt for player name"""
        
        print("\n👤 Player Setup")
        print("-" * 40)
        
        try:
            player_name = input("Enter your character name (default: Adventurer): ").strip()
            return player_name or "Adventurer"
        except (KeyboardInterrupt, EOFError):
            return "Adventurer"


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
            print(f"Campaign: {config.campaign_data.get('name', 'Unknown')}")
            print(f"Player: {config.player_name}")
        elif config.game_mode == "load_saved":
            print(f"Save file: {config.save_file}")
            
    except Exception as e:
        print(f"❌ Initialization test failed: {e}")