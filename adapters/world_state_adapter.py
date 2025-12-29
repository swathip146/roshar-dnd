"""
Routing Context Adapter - Interface for External Systems
Provides specialized interface to authoritative game state for routing and intent classification.
NO STATE STORAGE - Pure transformation layer that queries authoritative sources.

This adapter serves external systems (orchestrator, routing, intent classification) that need
specialized data formats without duplicating or storing game state.
"""

from typing import Dict, Any, List, Optional
from components.game_engine import GameEngine
from components.campaign_config import CampaignConfig


class RoutingContextAdapter:
    """
    Interface adapter for routing and intent classification systems.
    
    Provides specialized data formats for external systems by querying authoritative sources:
    - CampaignConfig: Immutable campaign data (NPCs, locations, quests)
    - GameEngine: Runtime state (current location, environment, campaign flags)
    - CharacterManager: Character sheet data (names, classes, levels)
    
    NO STATE STORAGE: Pure interface adapter - always queries fresh data from authorities.
    
    Usage Patterns:
    - Orchestrator routing decisions
    - Intent classification entity resolution
    - External system integration
    - Testing with MockRoutingContextAdapter
    
    Authority Hierarchy Integration:
    CampaignConfig (Immutable) → GameEngine (Runtime) → SessionManager (Persistence)
            ↓
    CharacterManager (Character Authority)
            ↓
    RoutingContextAdapter (Interface Layer) ← External Systems
    """
    
    def __init__(self, campaign_config: CampaignConfig, game_engine: GameEngine, character_manager=None):
        """
        Initialize adapter with all authoritative sources for complete world context.
        
        Args:
            campaign_config: Immutable campaign configuration (authoritative campaign data)
            game_engine: The main game engine containing runtime world state
            character_manager: Character manager containing character sheet data (authority)
            
        Design Notes:
            - Stores references to authoritative sources, not copies of data
            - All properties perform live queries to ensure fresh data
            - CampaignConfig provides NPCs, locations, and quest context
            - GameEngine provides runtime state and environment
            - CharacterManager provides character sheet details
        """
        self.campaign_config = campaign_config
        self.game_engine = game_engine
        self.character_manager = character_manager
    
    @property
    def npcs(self) -> Dict[str, Dict[str, Any]]:
        """
        NPC data for routing and intent classification - Enhanced with CampaignConfig authority.
        
        Data Sources (Priority Order):
        1. CampaignConfig.npcs_by_name - Immutable campaign NPCs (primary source)
        2. CharacterManager.characters - Runtime character data (secondary source)
        
        Returns:
            Dict mapping NPC identifiers to NPC data with name, aliases, and game details
            
        Design Notes:
            - CampaignConfig NPCs take priority as they're the authoritative campaign definition
            - CharacterManager NPCs supplement with runtime character sheet data
            - No data duplication - live queries only
        """
        npcs = {}
        
        # Primary source: CampaignConfig NPCs (immutable campaign data)
        if self.campaign_config and hasattr(self.campaign_config, 'npcs_by_name'):
            for npc_name, npc_data in self.campaign_config.npcs_by_name.items():
                npc_id = npc_name.lower().replace(' ', '_')
                npcs[npc_id] = {
                    "name": npc_data.get("name", npc_name),
                    "aliases": npc_data.get("aliases", []),
                    "role": npc_data.get("role", "NPC"),
                    "location": npc_data.get("location", "Unknown"),
                    "description": npc_data.get("description", ""),
                    "source": "campaign_config"
                }
        
        # Secondary source: CharacterManager NPCs (runtime character sheets)
        if self.character_manager and hasattr(self.character_manager, 'characters'):
            for char_id, character_data in self.character_manager.characters.items():
                # Skip if already in campaign config to avoid duplication
                if char_id in npcs:
                    continue
                    
                # Assume NPCs unless explicitly marked as player characters
                is_npc = getattr(character_data, 'is_npc', True)
                is_player = getattr(character_data, 'is_player', False)
                
                if is_npc and not is_player:
                    npcs[char_id] = {
                        "name": getattr(character_data, 'name', char_id),
                        "aliases": getattr(character_data, 'aliases', []),
                        "character_class": getattr(character_data, 'character_class', ""),
                        "level": getattr(character_data, 'level', 1),
                        "race": getattr(character_data, 'race', "Unknown"),
                        "background": getattr(character_data, 'background', "Unknown"),
                        "source": "character_manager"
                    }
        
        return npcs
    
    @property
    def places(self) -> List[str]:
        """
        Available location names for routing and intent classification - Enhanced with CampaignConfig.
        
        Data Sources (Merged):
        1. CampaignConfig.locations_by_type - Immutable campaign locations (primary)
        2. GameEngine.environment - Runtime location state (secondary)
        3. GameEngine.campaign_flags - Dynamic location discovery (tertiary)
        
        Returns:
            List of unique location names available for player interaction
            
        Design Notes:
            - CampaignConfig provides the canonical set of campaign locations
            - GameEngine adds current location and discovered locations
            - Duplicates are automatically removed
        """
        locations = set()  # Use set to automatically handle duplicates
        
        # Primary source: CampaignConfig locations (immutable campaign data)
        if self.campaign_config and hasattr(self.campaign_config, 'locations_by_type'):
            for location_type, location_list in self.campaign_config.locations_by_type.items():
                for location_data in location_list:
                    if isinstance(location_data, dict):
                        locations.add(location_data.get("name", "Unknown Location"))
                    else:
                        # Handle string location names
                        locations.add(str(location_data))
        
        # Secondary source: GameEngine environment locations (runtime state)
        if self.game_engine and hasattr(self.game_engine, 'environment'):
            env_locations = self.game_engine.environment.get("locations", [])
            if isinstance(env_locations, list):
                locations.update(env_locations)
            elif isinstance(env_locations, dict):
                locations.update(env_locations.keys())
            
            # Add current location if not in list
            current_loc = self.game_engine.environment.get("current_location")
            if current_loc:
                locations.add(current_loc)
        
        # Tertiary source: Dynamic location discovery via campaign flags
        if self.game_engine and hasattr(self.game_engine, 'game_state'):
            campaign_flags = getattr(self.game_engine.game_state, 'campaign_flags', {})
            for flag_name, flag_value in campaign_flags.items():
                if flag_name.startswith("location_") and flag_value:
                    location_name = flag_name.replace("location_", "").replace("_", " ").title()
                    locations.add(location_name)
        
        return sorted(list(locations))  # Return sorted list for consistent ordering
    
    @property
    def npc_names(self) -> List[str]:
        """
        List of all NPC names and aliases for intent classification
        
        Returns:
            Flattened list of all NPC names and aliases
        """
        names = []
        for npc_data in self.npcs.values():
            # Add primary name
            primary_name = npc_data.get("name", "")
            if primary_name:
                names.append(primary_name)
            
            # Add aliases
            aliases = npc_data.get("aliases", [])
            if isinstance(aliases, list):
                names.extend(aliases)
        
        return list(set(names))  # Remove duplicates
    
    @property
    def place_names(self) -> List[str]:
        """
        List of place names for intent classification
        
        Returns:
            List of place names
        """
        return self.places
    
    def get_npc_by_name(self, name: str) -> Optional[tuple]:
        """
        Find NPC by name or alias
        
        Args:
            name: Name or alias to search for
            
        Returns:
            Tuple of (npc_id, npc_data) if found, None otherwise
        """
        name_lower = name.lower().strip()
        
        for npc_id, npc_data in self.npcs.items():
            # Check primary name
            if npc_data.get("name", "").lower() == name_lower:
                return (npc_id, npc_data)
            
            # Check aliases
            aliases = npc_data.get("aliases", [])
            for alias in aliases:
                if str(alias).lower() == name_lower:
                    return (npc_id, npc_data)
        
        return None
    
    def get_location_info(self, location: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a location
        
        Args:
            location: Location name to look up
            
        Returns:
            Location data if found, None otherwise
        """
        # Check if location exists in our places
        if location not in self.places:
            return None
        
        # Try to get location details from environment
        env_locations = self.game_engine.environment.get("locations", {})
        if isinstance(env_locations, dict) and location in env_locations:
            return env_locations[location]
        
        # Return basic info if detailed data not available
        return {
            "name": location,
            "type": "location",
            "current": location == self.game_engine.environment.get("current_location")
        }
    
    def get_current_context(self) -> Dict[str, Any]:
        """
        Get comprehensive current world context for routing decisions - Enhanced with CampaignConfig.
        
        Provides complete context for external systems by combining data from all authoritative sources:
        - Campaign information from CampaignConfig
        - Runtime state from GameEngine
        - Character data from CharacterManager
        
        Returns:
            Context dictionary with comprehensive world state for routing and intent classification
            
        Design Notes:
            - Optimized for external system consumption (orchestrator, routing, etc.)
            - All data sourced from authoritative components
            - No state storage - live aggregation only
        """
        context = {}
        
        # Campaign-level context from CampaignConfig (immutable authority)
        if self.campaign_config:
            context.update({
                "campaign_name": self.campaign_config.name,
                "campaign_theme": self.campaign_config.theme,
                "campaign_difficulty": self.campaign_config.difficulty,
                "total_campaign_npcs": len(getattr(self.campaign_config, 'npcs_by_name', {})),
                "total_campaign_locations": sum(len(locs) for locs in getattr(self.campaign_config, 'locations_by_type', {}).values()),
                "campaign_quests": len(getattr(self.campaign_config, 'quests', [])),
            })
        else:
            context.update({
                "campaign_name": "Unknown Campaign",
                "campaign_theme": "generic",
                "campaign_difficulty": "medium",
                "total_campaign_npcs": 0,
                "total_campaign_locations": 0,
                "campaign_quests": 0,
            })
        
        # Runtime context from GameEngine (runtime authority)
        if self.game_engine and hasattr(self.game_engine, 'environment'):
            context.update({
                "current_location": self.game_engine.environment.get("current_location", "Unknown"),
                "environment_state": self.game_engine.environment,
            })
            
            # Add campaign flags if available
            if hasattr(self.game_engine, 'game_state'):
                context["campaign_flags"] = getattr(self.game_engine.game_state, 'campaign_flags', {})
            else:
                context["campaign_flags"] = {}
        else:
            context.update({
                "current_location": "Unknown",
                "environment_state": {},
                "campaign_flags": {},
            })
        
        # Aggregated counts from live queries
        context.update({
            "active_npcs": len(self.npcs),
            "known_locations": len(self.places),
            "npc_names_available": len(self.npc_names),
            "place_names_available": len(self.place_names),
            "session_active": True,
            "data_sources": {
                "campaign_config": bool(self.campaign_config),
                "game_engine": bool(self.game_engine),
                "character_manager": bool(self.character_manager)
            }
        })
        
        return context


class MockRoutingContextAdapter(RoutingContextAdapter):
    """
    Mock adapter for testing when GameEngine/CampaignConfig not available.
    
    Provides same interface as RoutingContextAdapter but with configurable mock data.
    Useful for unit testing and development without full game system initialization.
    """
    
    def __init__(self, mock_data: Optional[Dict[str, Any]] = None):
        """
        Initialize with mock data instead of real game components.
        
        Args:
            mock_data: Optional mock world state data
            
        Mock Data Structure:
            {
                "campaign": {"name": "Test Campaign", "theme": "fantasy", "difficulty": "medium"},
                "npcs": {"npc_id": {"name": "NPC Name", "aliases": [...]}},
                "places": ["Location1", "Location2"],
                "current_location": "Test Location",
                "campaign_flags": {"flag": True}
            }
        """
        self.mock_data = mock_data or {}
        # Don't call super().__init__() since we don't have real components
        self.campaign_config = None
        self.game_engine = None
        self.character_manager = None
        
    @property
    def npcs(self) -> Dict[str, Dict[str, Any]]:
        """Mock NPC data for testing"""
        return self.mock_data.get("npcs", {
            "bartender": {
                "name": "Bartender",
                "aliases": ["barkeep", "innkeeper"],
                "character_class": "Commoner",
                "level": 1,
                "source": "mock"
            },
            "merchant": {
                "name": "Merchant",
                "aliases": ["trader", "shopkeeper"],
                "character_class": "Commoner",
                "level": 2,
                "source": "mock"
            }
        })
    
    @property
    def places(self) -> List[str]:
        """Mock location data for testing"""
        return self.mock_data.get("places", ["Tavern", "Town Square", "Forest", "Shop"])
    
    def get_current_context(self) -> Dict[str, Any]:
        """Mock context data for testing"""
        campaign_data = self.mock_data.get("campaign", {})
        return {
            # Campaign context (mocked)
            "campaign_name": campaign_data.get("name", "Test Campaign"),
            "campaign_theme": campaign_data.get("theme", "fantasy"),
            "campaign_difficulty": campaign_data.get("difficulty", "medium"),
            "total_campaign_npcs": len(self.npcs),
            "total_campaign_locations": len(self.places),
            "campaign_quests": campaign_data.get("quests", 2),
            
            # Runtime context (mocked)
            "current_location": self.mock_data.get("current_location", "Tavern"),
            "campaign_flags": self.mock_data.get("campaign_flags", {}),
            "environment_state": self.mock_data.get("environment_state", {}),
            
            # Aggregated data
            "active_npcs": len(self.npcs),
            "known_locations": len(self.places),
            "npc_names_available": len(self.npc_names),
            "place_names_available": len(self.place_names),
            "session_active": True,
            "data_sources": {
                "campaign_config": False,
                "game_engine": False,
                "character_manager": False
            }
        }


# Backward Compatibility Aliases
# Maintain compatibility with existing code that imports WorldStateAdapter
WorldStateAdapter = RoutingContextAdapter
MockWorldStateAdapter = MockRoutingContextAdapter