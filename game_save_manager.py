"""
Game Save Manager for Modular DM Assistant

Handles all game save and load functionality, keeping it separate from the main class.
"""

import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime


class GameSaveManager:
    """
    Manages game save and load operations for the DM Assistant.
    
    This class handles:
    - Listing available game saves
    - Loading game save files
    - Saving game state
    - Managing save file metadata
    """
    
    def __init__(self, game_saves_dir: str = "./game_saves", verbose: bool = False):
        """
        Initialize the game save manager.
        
        Args:
            game_saves_dir: Directory to store game save files
            verbose: Whether to print verbose output
        """
        self.game_saves_dir = game_saves_dir
        self.verbose = verbose
        self.current_save_file: Optional[str] = None
        self.game_save_data: Dict[str, Any] = {}
        
        # Ensure game saves directory exists
        os.makedirs(self.game_saves_dir, exist_ok=True)
    
    def list_game_saves(self) -> List[Dict[str, Any]]:
        """List all available game save files."""
        saves = []
        try:
            if not os.path.exists(self.game_saves_dir):
                return saves
            
            for filename in os.listdir(self.game_saves_dir):
                if filename.endswith('.json'):
                    filepath = os.path.join(self.game_saves_dir, filename)
                    try:
                        mod_time = os.path.getmtime(filepath)
                        mod_date = datetime.fromtimestamp(mod_time).strftime("%Y-%m-%d %H:%M")
                        
                        with open(filepath, 'r') as f:
                            save_data = json.load(f)
                        
                        saves.append({
                            'filename': filename,
                            'save_name': save_data.get('save_name', filename[:-5]),
                            'campaign': save_data.get('campaign_info', {}).get('title', 'Unknown Campaign'),
                            'last_modified': mod_date,
                            'scenario_count': save_data.get('game_state', {}).get('scenario_count', 0),
                            'players': len(save_data.get('players', [])),
                            'story_progression': len(save_data.get('game_state', {}).get('story_progression', []))
                        })
                    except (json.JSONDecodeError, IOError):
                        if self.verbose:
                            print(f"⚠️ Could not read save file {filename}")
                        continue
            
            # Sort by last modified date (newest first)
            saves.sort(key=lambda x: x['last_modified'], reverse=True)
            
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Error listing game saves: {e}")
        
        return saves
    
    def load_game_save(self, save_file: str, dm_assistant=None) -> bool:
        """
        Load a game save file.
        
        Args:
            save_file: Name of the save file to load
            dm_assistant: Reference to the main DM assistant for restoring state
            
        Returns:
            bool: True if load was successful, False otherwise
        """
        try:
            filepath = os.path.join(self.game_saves_dir, save_file)
            if not os.path.exists(filepath):
                if self.verbose:
                    print(f"❌ Save file not found: {save_file}")
                return False
            
            with open(filepath, 'r') as f:
                self.game_save_data = json.load(f)
            
            self.current_save_file = save_file
            
            # Restore game state to game engine if DM assistant is provided
            if dm_assistant and self.game_save_data.get('game_state'):
                response = dm_assistant._send_message_and_wait("game_engine", "update_game_state", {
                    "updates": self.game_save_data['game_state']
                }, timeout=20.0)
                
                if not (response and response.get("success")) and self.verbose:
                    error_msg = response.get('error', 'Unknown error') if response else 'Timeout'
                    print(f"⚠️ Game save restore failed: {error_msg}")
            
            # Restore command handler state if available
            if dm_assistant and hasattr(dm_assistant.command_handler, 'last_scenario_options'):
                if self.game_save_data.get('last_scenario_options'):
                    dm_assistant.command_handler.last_scenario_options = self.game_save_data['last_scenario_options']
            
            if self.verbose:
                save_name = self.game_save_data.get('save_name', save_file)
                campaign = self.game_save_data.get('campaign_info', {}).get('title', 'Unknown')
                print(f"💾 Successfully loaded save: {save_name} (Campaign: {campaign})")
            
            return True
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Error loading save file {save_file}: {e}")
            return False
    
    def save_game(self, save_name: str, dm_assistant, update_existing: bool = False) -> bool:
        """
        Save the current game state.
        
        Args:
            save_name: Name for the save file
            dm_assistant: Reference to the main DM assistant
            update_existing: Whether to update an existing save file
            
        Returns:
            bool: True if save was successful, False otherwise
        """
        try:
            # Generate filename
            if update_existing and self.current_save_file:
                filename = self.current_save_file
            else:
                # Create new save file
                safe_name = "".join(c for c in save_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                safe_name = safe_name.replace(' ', '_')
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{safe_name}_{timestamp}.json"
            
            filepath = os.path.join(self.game_saves_dir, filename)
            
            # Gather current game state
            current_game_state = {}
            if dm_assistant.game_engine_agent:
                state_response = dm_assistant._send_message_and_wait("game_engine", "get_game_state", {})
                if state_response and state_response.get("game_state"):
                    current_game_state = state_response["game_state"]
            
            # Gather campaign info
            campaign_info = {}
            campaign_response = dm_assistant._send_message_and_wait("campaign_manager", "get_campaign_info", {})
            if campaign_response and campaign_response.get("success"):
                campaign_info = campaign_response["campaign"]
            
            # Gather players info
            players_info = []
            players_response = dm_assistant._send_message_and_wait("campaign_manager", "list_players", {})
            if players_response and players_response.get("players"):
                players_info = players_response["players"]
            
            # Gather combat state if active
            combat_state = {}
            if dm_assistant.combat_agent:
                combat_response = dm_assistant._send_message_and_wait("combat_engine", "get_combat_status", {})
                if combat_response and combat_response.get("success"):
                    combat_state = combat_response["status"]
            
            # Get command handler state
            last_scenario_options = []
            if hasattr(dm_assistant.command_handler, 'last_scenario_options'):
                last_scenario_options = dm_assistant.command_handler.last_scenario_options
            
            # Create save data structure
            save_data = {
                'save_name': save_name,
                'save_date': datetime.now().isoformat(),
                'version': '1.0',
                'game_state': current_game_state,
                'campaign_info': campaign_info,
                'players': players_info,
                'combat_state': combat_state,
                'last_scenario_options': last_scenario_options,
                'assistant_config': {
                    'collection_name': dm_assistant.collection_name,
                    'campaigns_dir': dm_assistant.campaigns_dir,
                    'players_dir': dm_assistant.players_dir,
                    'enable_game_engine': dm_assistant.enable_game_engine,
                    'enable_caching': dm_assistant.enable_caching,
                    'enable_async': dm_assistant.enable_async
                }
            }
            
            # Write save file
            with open(filepath, 'w') as f:
                json.dump(save_data, f, indent=2)
            
            # Update current save file reference
            self.current_save_file = filename
            self.game_save_data = save_data
            
            if self.verbose:
                print(f"💾 Successfully saved game: {save_name} ({filename})")
            
            return True
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Error saving game: {e}")
            return False
    
    def get_save_data(self) -> Dict[str, Any]:
        """Get the current save data."""
        return self.game_save_data.copy()
    
    def get_current_save_file(self) -> Optional[str]:
        """Get the current save file name."""
        return self.current_save_file
    
    def has_save_loaded(self) -> bool:
        """Check if a save file is currently loaded."""
        return bool(self.current_save_file and self.game_save_data)
    
    def save_game_state(self, save_data: Dict[str, Any], save_name: str) -> bool:
        """
        Save game state data directly (method expected by tests).
        
        Args:
            save_data: Dictionary containing the game state to save
            save_name: Name for the save file
            
        Returns:
            bool: True if save was successful, False otherwise
        """
        try:
            # Create safe filename from save_name
            safe_name = "".join(c for c in save_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_name = safe_name.replace(' ', '_')
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{safe_name}_{timestamp}.json"
            
            filepath = os.path.join(self.game_saves_dir, filename)
            
            # Write save file
            with open(filepath, 'w') as f:
                json.dump(save_data, f, indent=2)
            
            # Update current save file reference
            self.current_save_file = filename
            self.game_save_data = save_data
            
            if self.verbose:
                print(f"💾 Game state saved: {save_name}")
            
            return True
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Error saving game state: {e}")
            return False
