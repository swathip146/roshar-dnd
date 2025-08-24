"""
World State Adapter - Interface between GameEngine and Fixed System
Provides clean abstraction for world state access in routing decisions
"""

from typing import Dict, Any, List, Optional
from components.game_engine import GameEngine


class WorldStateAdapter:
    """Adapter between GameEngine and fixed system interface"""
    
    def __init__(self, game_engine: GameEngine):
        """
        Initialize adapter with GameEngine instance
        
        Args:
            game_engine: The main game engine containing world state
        """
        self.game_engine = game_engine
    
    @property
    def npcs(self) -> Dict[str, Dict[str, Any]]:
        """
        NPC data with aliases support
        
        Returns:
            Dict mapping NPC IDs to NPC data with name and aliases
        """
        npcs = {}
        
        # Extract NPCs from character data
        for char_id, char_data in self.game_engine.character_data.items():
            # Assume NPCs unless explicitly marked as player characters
            is_npc = char_data.get("is_npc", True)
            is_player = char_data.get("is_player", False)
            
            if is_npc and not is_player:
                npcs[char_id] = {
                    "name": char_data.get("name", char_id),
                    "aliases": char_data.get("aliases", []),
                    "character_class": char_data.get("character_class", ""),
                    "level": char_data.get("level", 1),
                    **char_data  # Include all original data
                }
        
        return npcs
    
    @property
    def places(self) -> List[str]:
        """
        Available location names
        
        Returns:
            List of location names from game environment
        """
        locations = []
        
        # Get locations from environment
        env_locations = self.game_engine.environment.get("locations", [])
        if isinstance(env_locations, list):
            locations.extend(env_locations)
        elif isinstance(env_locations, dict):
            locations.extend(env_locations.keys())
        
        # Add current location if not in list
        current_loc = self.game_engine.environment.get("current_location")
        if current_loc and current_loc not in locations:
            locations.append(current_loc)
        
        # Add any locations from campaign flags
        campaign_flags = self.game_engine.game_state.get("campaign_flags", {})
        for flag_name, flag_value in campaign_flags.items():
            if flag_name.startswith("location_") and flag_value:
                location_name = flag_name.replace("location_", "").replace("_", " ").title()
                if location_name not in locations:
                    locations.append(location_name)
        
        return locations
    
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
        Get current world context for routing decisions
        
        Returns:
            Context dictionary with current world state
        """
        return {
            "current_location": self.game_engine.environment.get("current_location", "Unknown"),
            "active_npcs": len(self.npcs),
            "known_locations": len(self.places),
            "campaign_flags": self.game_engine.game_state.get("campaign_flags", {}),
            "environment_state": self.game_engine.environment,
            "session_active": True
        }


class MockWorldStateAdapter(WorldStateAdapter):
    """Mock adapter for testing when GameEngine not available"""
    
    def __init__(self, mock_data: Optional[Dict[str, Any]] = None):
        """
        Initialize with mock data instead of GameEngine
        
        Args:
            mock_data: Optional mock world state data
        """
        self.mock_data = mock_data or {}
        # Don't call super().__init__() since we don't have a real game_engine
        
    @property
    def npcs(self) -> Dict[str, Dict[str, Any]]:
        return self.mock_data.get("npcs", {
            "bartender": {
                "name": "Bartender",
                "aliases": ["barkeep", "innkeeper"],
                "character_class": "Commoner",
                "level": 1
            }
        })
    
    @property
    def places(self) -> List[str]:
        return self.mock_data.get("places", ["Tavern", "Town Square", "Forest"])
    
    def get_current_context(self) -> Dict[str, Any]:
        return {
            "current_location": self.mock_data.get("current_location", "Tavern"),
            "active_npcs": len(self.npcs),
            "known_locations": len(self.places),
            "campaign_flags": {},
            "environment_state": {},
            "session_active": True
        }