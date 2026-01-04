"""
NPC Stat Loader - Loads predefined NPC stats from JSON files

Provides a registry system for loading NPC character data from JSON files
in the data/players/ directory. Supports case-insensitive name lookups
and partial name matching.
"""

import json
import os
from typing import Dict, Any, Optional, List
from pathlib import Path

from config.logging_config import get_logger

logger = get_logger(__name__)


class NPCStatLoader:
    """
    Load and manage predefined NPC stats from JSON files.

    Loads NPC character data from JSON files in CharacterData format,
    providing a registry for fast lookups by name. Supports both exact
    and partial name matching (e.g., "Kalak" matches "Kalak the Herald").
    """

    def __init__(self, npc_directory: str = "data/players/"):
        """
        Initialize NPC loader with directory of JSON files.

        Args:
            npc_directory: Path to directory containing NPC JSON files
        """
        self.npc_directory = npc_directory
        self.npc_registry: Dict[str, Dict[str, Any]] = {}
        self._load_all_npcs()

    def _load_all_npcs(self):
        """
        Load all JSON NPC files into registry.

        Scans the npc_directory for .json files and loads them into the registry.
        NPCs are indexed by lowercase name for case-insensitive lookup.
        Skips player character files (aggi.json, kali.json).
        """
        if not os.path.exists(self.npc_directory):
            logger.warning(f"NPC directory not found: {self.npc_directory}")
            return

        player_char_files = ['aggi.json', 'kali.json']  # Player characters, not NPCs
        loaded_count = 0

        try:
            for filename in os.listdir(self.npc_directory):
                # Skip non-JSON files and player character files
                if not filename.endswith('.json'):
                    continue
                if filename in player_char_files:
                    logger.debug(f"Skipping player character file: {filename}")
                    continue

                filepath = os.path.join(self.npc_directory, filename)

                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        npc_data = json.load(f)

                    # Validate required fields
                    if not self._validate_npc_data(npc_data, filename):
                        continue

                    # Register by name (case-insensitive)
                    npc_name = npc_data.get('name', '')
                    if npc_name:
                        npc_name_lower = npc_name.lower()
                        self.npc_registry[npc_name_lower] = npc_data
                        loaded_count += 1
                        logger.debug(f"Loaded NPC: {npc_name} from {filename}")
                    else:
                        logger.warning(f"NPC file {filename} missing 'name' field")

                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON in {filename}: {e}")
                except Exception as e:
                    logger.warning(f"Failed to load NPC file {filename}: {e}")

        except Exception as e:
            logger.error(f"Failed to read NPC directory {self.npc_directory}: {e}")

        logger.info(f"Loaded {loaded_count} predefined NPCs from {self.npc_directory}")

    def _validate_npc_data(self, npc_data: Dict[str, Any], filename: str) -> bool:
        """
        Validate that NPC data has required CharacterData fields.

        Args:
            npc_data: NPC character data dict
            filename: Source filename for logging

        Returns:
            True if valid, False otherwise
        """
        required_fields = [
            'name', 'character_class', 'level', 'ability_scores',
            'hit_points', 'armor_class', 'proficiency_bonus'
        ]

        missing_fields = [field for field in required_fields if field not in npc_data]

        if missing_fields:
            logger.warning(f"NPC file {filename} missing required fields: {missing_fields}")
            return False

        # Validate hit_points structure
        hp = npc_data.get('hit_points', {})
        if not isinstance(hp, dict) or not all(k in hp for k in ['current', 'maximum', 'temporary']):
            logger.warning(f"NPC file {filename} has invalid hit_points structure")
            return False

        # Validate ability_scores structure
        abilities = npc_data.get('ability_scores', {})
        required_abilities = {'strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma'}
        if not isinstance(abilities, dict) or not required_abilities.issubset(abilities.keys()):
            logger.warning(f"NPC file {filename} has invalid ability_scores structure")
            return False

        return True

    def get_npc_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get NPC stats by name (case-insensitive with partial matching).

        Supports both exact matching and partial matching. For example:
        - "Kalak" will match "Kalak the Herald"
        - "kalak the herald" will match "Kalak the Herald" (case-insensitive)

        Args:
            name: NPC name to search for

        Returns:
            Copy of NPC character data dict, or None if not found
        """
        if not name:
            return None

        name_lower = name.lower().strip()

        # Try exact match first
        if name_lower in self.npc_registry:
            return self.npc_registry[name_lower].copy()

        # Try partial match (search in both directions)
        for npc_name, npc_data in self.npc_registry.items():
            if name_lower in npc_name or npc_name in name_lower:
                logger.debug(f"Partial match: '{name}' matched '{npc_data['name']}'")
                return npc_data.copy()

        logger.debug(f"No NPC found matching name: {name}")
        return None

    def has_npc(self, name: str) -> bool:
        """
        Check if NPC exists in registry.

        Args:
            name: NPC name to check

        Returns:
            True if NPC exists, False otherwise
        """
        return self.get_npc_by_name(name) is not None

    def list_available_npcs(self) -> List[str]:
        """
        Get list of all available NPC names.

        Returns:
            List of NPC names (proper case)
        """
        return [npc_data['name'] for npc_data in self.npc_registry.values()]

    def get_npc_count(self) -> int:
        """
        Get count of loaded NPCs.

        Returns:
            Number of NPCs in registry
        """
        return len(self.npc_registry)

    def reload(self):
        """
        Reload all NPC files from directory.

        Useful for development when NPC files are modified.
        """
        self.npc_registry.clear()
        self._load_all_npcs()
        logger.info(f"Reloaded NPC registry: {self.get_npc_count()} NPCs")


# Module-level convenience functions
_global_npc_loader: Optional[NPCStatLoader] = None


def get_npc_loader(npc_directory: str = "data/players/") -> NPCStatLoader:
    """
    Get or create global NPC loader instance.

    Args:
        npc_directory: Path to NPC directory

    Returns:
        Global NPCStatLoader instance
    """
    global _global_npc_loader
    if _global_npc_loader is None:
        _global_npc_loader = NPCStatLoader(npc_directory)
    return _global_npc_loader


def load_npc(name: str) -> Optional[Dict[str, Any]]:
    """
    Convenience function to load NPC by name using global loader.

    Args:
        name: NPC name to load

    Returns:
        NPC character data dict, or None if not found
    """
    loader = get_npc_loader()
    return loader.get_npc_by_name(name)


# Example usage and testing
if __name__ == "__main__":
    print("=" * 60)
    print("NPC Stat Loader - Testing")
    print("=" * 60)

    # Create loader
    loader = NPCStatLoader()

    print(f"\n📊 Loaded {loader.get_npc_count()} NPCs")
    print(f"Available NPCs: {', '.join(loader.list_available_npcs())}")

    # Test exact match
    print("\n--- Test 1: Exact name match ---")
    kalak = loader.get_npc_by_name("Kalak")
    if kalak:
        print(f"✅ Found: {kalak['name']}")
        print(f"   Level: {kalak['level']}, HP: {kalak['hit_points']['maximum']}, AC: {kalak['armor_class']}")
    else:
        print("❌ Not found")

    # Test case-insensitive
    print("\n--- Test 2: Case-insensitive match ---")
    nale = loader.get_npc_by_name("NALE THE HERALD")
    if nale:
        print(f"✅ Found: {nale['name']}")
        print(f"   Level: {nale['level']}, HP: {nale['hit_points']['maximum']}, AC: {nale['armor_class']}")
    else:
        print("❌ Not found")

    # Test partial match
    print("\n--- Test 3: Partial name match ---")
    herald = loader.get_npc_by_name("Kalak the")
    if herald:
        print(f"✅ Found: {herald['name']}")
    else:
        print("❌ Not found")

    # Test missing NPC
    print("\n--- Test 4: Missing NPC ---")
    missing = loader.get_npc_by_name("Dragon")
    if missing:
        print(f"✅ Found: {missing['name']}")
    else:
        print("❌ Not found (expected)")

    # Test has_npc
    print("\n--- Test 5: has_npc() check ---")
    print(f"Has 'Kalak': {loader.has_npc('Kalak')}")
    print(f"Has 'Dragon': {loader.has_npc('Dragon')}")

    print("\n" + "=" * 60)
    print("Testing complete")
    print("=" * 60)
