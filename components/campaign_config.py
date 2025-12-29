"""
Campaign Configuration - Immutable campaign data structure
Part of Option 2: State Hierarchy with Clear Ownership implementation
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from pathlib import Path
import json


@dataclass(frozen=True)
class CampaignConfig:
    """
    Immutable campaign configuration - parsed once during initialization
    Contains all campaign metadata, NPCs, locations, quests, and hooks
    """
    
    # Basic campaign information
    name: str
    description: str
    story: str
    source_file: str
    
    # Game configuration
    level_range: str
    starting_location: str
    theme: str
    setting: str
    difficulty: str
    recommended_party_size: str
    
    # Campaign content (immutable lists/dicts)
    key_npcs: List[Dict[str, str]] = field(default_factory=list)
    locations: List[Dict[str, str]] = field(default_factory=list) 
    quests: List[str] = field(default_factory=list)
    campaign_hooks: List[str] = field(default_factory=list)
    rewards: List[str] = field(default_factory=list)
    
    # Story elements
    main_plot: str = ""
    dm_notes: str = ""
    
    # Enhanced features metadata
    enhanced_features: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate campaign configuration after creation"""
        if not self.name:
            raise ValueError("Campaign name cannot be empty")
        if not self.starting_location:
            raise ValueError("Starting location cannot be empty")
        if self.difficulty not in ["Easy", "Medium", "High"]:
            raise ValueError(f"Invalid difficulty: {self.difficulty}")
        
        # Validate level range format (e.g., "1-5")
        if not self._validate_level_range(self.level_range):
            raise ValueError(f"Invalid level range format: {self.level_range}")
    
    def _validate_level_range(self, level_range: str) -> bool:
        """Validate level range format (e.g., '1-5', '3-10')"""
        try:
            if "-" not in level_range:
                return False
            start, end = level_range.split("-")
            start_level = int(start.strip())
            end_level = int(end.strip())
            return 1 <= start_level <= end_level <= 20
        except (ValueError, IndexError):
            return False
    
    def get_npc_by_name(self, npc_name: str) -> Optional[Dict[str, str]]:
        """Get NPC data by name (case-insensitive)"""
        npc_name_lower = npc_name.lower()
        for npc in self.key_npcs:
            if npc.get("name", "").lower() == npc_name_lower:
                return npc
        return None
    
    def get_location_by_name(self, location_name: str) -> Optional[Dict[str, str]]:
        """Get location data by name (case-insensitive)"""
        location_name_lower = location_name.lower()
        for location in self.locations:
            if location.get("name", "").lower() == location_name_lower:
                return location
        return None
    
    def get_npcs_by_role(self, role: str) -> List[Dict[str, str]]:
        """Get all NPCs with a specific role"""
        role_lower = role.lower()
        return [npc for npc in self.key_npcs if npc.get("role", "").lower() == role_lower]
    
    def get_locations_by_type(self, location_type: str) -> List[Dict[str, str]]:
        """Get all locations of a specific type"""
        type_lower = location_type.lower()
        return [loc for loc in self.locations if loc.get("type", "").lower() == type_lower]
    
    def get_starting_level(self) -> int:
        """Extract starting level from level range"""
        try:
            return int(self.level_range.split("-")[0])
        except (ValueError, IndexError):
            return 1
    
    def get_max_level(self) -> int:
        """Extract maximum level from level range"""
        try:
            return int(self.level_range.split("-")[1])
        except (ValueError, IndexError):
            return 5
    
    def is_high_level_campaign(self) -> bool:
        """Check if this is a high-level campaign (starts above level 5)"""
        return self.get_starting_level() > 5
    
    def get_campaign_summary(self) -> Dict[str, Any]:
        """Get a summary of campaign statistics for debugging"""
        return {
            "name": self.name,
            "difficulty": self.difficulty,
            "level_range": self.level_range,
            "theme": self.theme,
            "npc_count": len(self.key_npcs),
            "location_count": len(self.locations),
            "quest_count": len(self.quests),
            "hook_count": len(self.campaign_hooks),
            "source_file": self.source_file,
            "enhanced_features": self.enhanced_features
        }
    
    @classmethod
    def create_from_parsed_data(cls, parsed_data: Dict[str, Any], 
                               source_file: str = "unknown") -> 'CampaignConfig':
        """
        Factory method to create CampaignConfig from parsed campaign data
        This replaces the campaign population logic from game_initialization.py
        """
        
        # Enhanced extraction for structured vectordb.txt format
        name = parsed_data.get("title", parsed_data.get("name", "Unknown Campaign"))
        description = parsed_data.get("description", "")
        story = cls._extract_story_content(parsed_data)
        
        # Extract game configuration with enhanced field detection
        level_range = parsed_data.get("level_range", "1-5")
        starting_location = cls._extract_starting_location(parsed_data)
        theme = parsed_data.get("theme", "Fantasy Adventure")
        setting = parsed_data.get("setting", "Fantasy World")
        difficulty = cls._assess_campaign_difficulty(parsed_data)
        recommended_party_size = cls._extract_party_size(parsed_data)
        
        # Extract campaign content
        key_npcs = cls._extract_npcs(parsed_data)
        locations = cls._extract_locations(parsed_data)
        quests = cls._extract_quests(parsed_data)
        campaign_hooks = cls._extract_hooks(parsed_data)
        rewards = cls._extract_rewards(parsed_data)
        
        # Extract story elements
        main_plot = parsed_data.get("main_plot", "")
        dm_notes = parsed_data.get("dm_notes", "")
        
        # Enhanced features metadata
        enhanced_features = {
            "content_complexity": cls._assess_content_complexity(parsed_data),
            "npc_count": len(key_npcs),
            "location_count": len(locations),
            "total_content_length": sum(len(str(v)) for v in parsed_data.values()),
            "file_size": sum(len(str(v)) for v in parsed_data.values())
        }
        
        return cls(
            name=name,
            description=description,
            story=story,
            source_file=source_file,
            level_range=level_range,
            starting_location=starting_location,
            theme=theme,
            setting=setting,
            difficulty=difficulty,
            recommended_party_size=recommended_party_size,
            key_npcs=key_npcs,
            locations=locations,
            quests=quests,
            campaign_hooks=campaign_hooks,
            rewards=rewards,
            main_plot=main_plot,
            dm_notes=dm_notes,
            enhanced_features=enhanced_features
        )
    
    @staticmethod
    def _extract_story_content(data: Dict[str, Any]) -> str:
        """Extract the main story/opening content for game initialization"""
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
        
        # Fallback to default opening
        return "You enter a bustling tavern filled with adventurers, merchants, and locals. The air is thick with pipe smoke and the aroma of roasted meat. A fire crackles in the hearth, casting dancing shadows on weathered faces."
    
    @staticmethod
    def _extract_starting_location(data: Dict[str, Any]) -> str:
        """Extract or infer starting location from campaign data"""
        # Look for explicit starting location in standalone field
        if "starting_location" in data:
            location = data["starting_location"]
            if isinstance(location, str) and location.strip():
                return location.strip()
        
        # Look for other location hint fields
        location_hints = ["start_location", "beginning"]
        for hint in location_hints:
            if hint in data and data[hint]:
                return str(data[hint]).strip()
        
        # Extract from locations list
        if "locations" in data:
            locations = data["locations"]
            if isinstance(locations, list) and locations:
                first_location = locations[0]
                if isinstance(first_location, dict):
                    return first_location.get("name", "Tavern")
                return str(first_location).split('\n')[0] if first_location else "Tavern"
        
        return "Tavern"
    
    @staticmethod 
    def _assess_campaign_difficulty(data: Dict[str, Any]) -> str:
        """Extract campaign difficulty from campaign file data"""
        difficulty_fields = ["difficulty", "DIFFICULTY", "campaign_difficulty", "level"]
        
        for field in difficulty_fields:
            if field in data and data[field]:
                difficulty = str(data[field]).strip()
                
                # Normalize difficulty values
                difficulty_lower = difficulty.lower()
                if difficulty_lower in ["easy", "beginner", "simple", "low"]:
                    return "Easy"
                elif difficulty_lower in ["hard", "difficult", "challenging", "high"]:
                    return "High"
                elif difficulty_lower in ["medium", "moderate", "normal", "average"]:
                    return "Medium"
                else:
                    # If we have a value but it doesn't match expected terms, return it as-is (capitalized)
                    return difficulty.capitalize()
        
        # Default if no difficulty field found
        return "Medium"
    
    @staticmethod
    def _extract_party_size(data: Dict[str, Any]) -> str:
        """Extract recommended party size"""
        content_text = str(data).lower()
        
        if "single player" in content_text or "solo" in content_text:
            return "1 player"
        elif "large group" in content_text or "6+" in content_text:
            return "5-6 players"
        else:
            return "3-5 players"  # Standard D&D party
    
    @staticmethod
    def _extract_npcs(data: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract key NPCs from campaign data - enhanced for vectordb.txt format"""
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
        
        # Enhanced extraction from structured text format (=== NPC: Name === sections)
        for key, value in data.items():
            if "npc:" in key.lower():
                # Extract NPC name from section header
                npc_name = key.replace("npc: ", "").replace("NPC: ", "").strip()
                
                # Parse NPC data from the structured content
                npc_info = {"name": npc_name, "role": "Important NPC", "description": ""}
                
                if isinstance(value, str):
                    lines = value.split('\n')
                    for line in lines:
                        line = line.strip()
                        if line.startswith("NPC_NAME:"):
                            npc_info["name"] = line.split(":", 1)[1].strip()
                        elif line.startswith("NPC_ROLE:"):
                            npc_info["role"] = line.split(":", 1)[1].strip()
                        elif line.startswith("DESCRIPTION:"):
                            npc_info["description"] = line.split(":", 1)[1].strip()
                        elif line.startswith("MOTIVATION:"):
                            # Add motivation to description
                            motivation = line.split(":", 1)[1].strip()
                            if npc_info["description"]:
                                npc_info["description"] += f" | Motivation: {motivation}"
                            else:
                                npc_info["description"] = f"Motivation: {motivation}"
                
                npcs.append(npc_info)
                
        print(f"   🎭 Extracted {len(npcs)} NPCs from campaign data")
        return npcs[:6]  # Limit to top 6 NPCs
    
    @staticmethod
    def _extract_locations(data: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract key locations from campaign data - enhanced for vectordb.txt format"""
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
        
        # Enhanced extraction from structured text format (=== LOCATION: Name === sections)
        for key, value in data.items():
            if "location:" in key.lower():
                # Extract location name from section header
                location_name = key.replace("location: ", "").replace("LOCATION: ", "").strip()
                
                # Parse location data from the structured content
                location_info = {"name": location_name, "type": "Campaign Location", "description": ""}
                
                if isinstance(value, str):
                    lines = value.split('\n')
                    for line in lines:
                        line = line.strip()
                        if line.startswith("LOCATION_NAME:"):
                            location_info["name"] = line.split(":", 1)[1].strip()
                        elif line.startswith("LOCATION_TYPE:"):
                            location_info["type"] = line.split(":", 1)[1].strip()
                        elif line.startswith("DESCRIPTION:"):
                            location_info["description"] = line.split(":", 1)[1].strip()
                        elif line.startswith("SIGNIFICANCE:"):
                            # Add significance to description
                            significance = line.split(":", 1)[1].strip()
                            if location_info["description"]:
                                location_info["description"] += f" | Significance: {significance}"
                            else:
                                location_info["description"] = f"Significance: {significance}"
                
                locations.append(location_info)
                
        print(f"   🗺️ Extracted {len(locations)} locations from campaign data")
        return locations[:5]  # Limit to top 5 locations
    
    @staticmethod
    def _extract_quests(data: Dict[str, Any]) -> List[str]:
        """Extract key quests from campaign data"""
        quests = []
        
        # Look for quests list first
        if "quests" in data:
            quest_data = data["quests"]
            if isinstance(quest_data, str):
                # Split by lines and clean up
                quest_lines = quest_data.split('\n')
                for line in quest_lines:
                    line = line.strip()
                    if line and line.startswith('-'):
                        quest_title = line[1:].strip()  # Remove leading dash
                        if quest_title:
                            quests.append(quest_title)
            elif isinstance(quest_data, list):
                for quest in quest_data:
                    if isinstance(quest, dict):
                        title = quest.get("title", quest.get("QUEST_TITLE", "Unknown quest"))
                        quests.append(title)
                    else:
                        quests.append(str(quest))
        
        # Extract from individual quest sections (=== QUEST: Title === sections)
        for key, value in data.items():
            if "quest:" in key.lower():
                quest_name = key.replace("quest: ", "").replace("QUEST: ", "").strip()
                
                # Try to extract QUEST_TITLE from content if available
                if isinstance(value, str) and "QUEST_TITLE:" in value:
                    lines = value.split('\n')
                    for line in lines:
                        if line.strip().startswith("QUEST_TITLE:"):
                            quest_name = line.split(":", 1)[1].strip()
                            break
                
                quests.append(quest_name)
        
        return quests[:8]  # Limit to top 8 quests
    
    @staticmethod
    def _extract_hooks(data: Dict[str, Any]) -> List[str]:
        """Extract campaign hooks for player engagement"""
        hooks = []
        
        # Look for campaign hooks section
        if "campaign hooks" in data:
            hook_data = data["campaign hooks"]
            if isinstance(hook_data, str):
                # Parse HOOK_1, HOOK_2, etc. from the content
                lines = hook_data.split('\n')
                for line in lines:
                    line = line.strip()
                    if line.startswith("HOOK_"):
                        hook_text = line.split(":", 1)[1].strip() if ":" in line else line
                        hooks.append(hook_text)
            elif isinstance(hook_data, list):
                hooks.extend([str(hook) for hook in hook_data])
        
        # Also check for "hooks" without "campaign"
        elif "hooks" in data:
            hook_data = data["hooks"]
            if isinstance(hook_data, str):
                # Parse HOOK_1, HOOK_2, etc. from the content
                lines = hook_data.split('\n')
                for line in lines:
                    line = line.strip()
                    if line.startswith("HOOK_"):
                        hook_text = line.split(":", 1)[1].strip() if ":" in line else line
                        hooks.append(hook_text)
            elif isinstance(hook_data, list):
                hooks.extend([str(hook) for hook in hook_data])
        
        # Extract numbered hooks from structured format
        for key, value in data.items():
            if "hook_" in key.lower():
                hooks.append(str(value))
        
        return hooks[:4]  # Limit to top 4 hooks
    
    @staticmethod
    def _extract_rewards(data: Dict[str, Any]) -> List[str]:
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
    
    @staticmethod
    def _assess_content_complexity(data: Dict[str, Any]) -> str:
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


def create_default_campaign_config() -> CampaignConfig:
    """Create a default campaign configuration for fallback purposes"""
    return CampaignConfig(
        name="The Forgotten Realms Adventure",
        description="A classic D&D adventure in the Forgotten Realms setting.",
        story="You enter a bustling tavern filled with adventurers, merchants, and locals. The air is thick with pipe smoke and the aroma of roasted meat. A fire crackles in the hearth, casting dancing shadows on weathered faces.",
        source_file="default",
        level_range="1-5",
        starting_location="Tavern",
        theme="Fantasy Adventure",
        setting="Fantasy World",
        difficulty="Medium",
        recommended_party_size="3-5 players",
        key_npcs=[],
        locations=[],
        quests=[],
        campaign_hooks=[],
        rewards=[],
        main_plot="",
        dm_notes="",
        enhanced_features={"content_complexity": "Basic"}
    )