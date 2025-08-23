"""
Session Manager - Persistent game session handling
Integrates with orchestrator for complete state management using Haystack component patterns
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from haystack import component


@dataclass
class GameSession:
    """Complete game session data structure"""
    session_id: str
    player_name: str
    created_time: float
    last_save_time: float
    game_state: Dict[str, Any]
    character_data: Dict[str, Any]
    orchestrator_state: Dict[str, Any]
    statistics: Dict[str, Any]


@component
class SessionManager:
    """
    Manages game session persistence and state following Haystack patterns
    Handles save/load operations with full state integration
    """
    
    def __init__(self, save_directory: str = "saves"):
        self.save_directory = Path(save_directory)
        self.save_directory.mkdir(exist_ok=True)
        
        self.current_session: Optional[GameSession] = None
        self.session_metadata: Dict[str, Any] = {}
        
        # Session statistics
        self.session_stats = {
            "sessions_created": 0,
            "successful_saves": 0,
            "successful_loads": 0,
            "failed_operations": 0
        }
        
        print("💾 Session Manager initialized")
    
    @component.output_types(success=bool, result=dict, message=str)
    def run(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Main Haystack component interface for session operations"""
        
        if operation == "create_session":
            return self.create_new_session(kwargs.get("player_name", "Player"),
                                         kwargs.get("initial_state", {}))
        elif operation == "save_session":
            return self.save_session(kwargs.get("filename"),
                                   kwargs.get("orchestrator_state"))
        elif operation == "load_session":
            return self.load_session(kwargs.get("filename", ""))
        elif operation == "list_saves":
            return {"success": True, "result": self.list_saves(), "message": "Saves listed"}
        elif operation == "get_stats":
            return {"success": True, "result": self.get_session_statistics(), "message": "Stats retrieved"}
        else:
            return {"success": False, "result": {}, "message": f"Unknown operation: {operation}"}
    
    def create_new_session(self, player_name: str, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new game session"""
        
        session_id = f"session_{int(time.time())}"
        current_time = time.time()
        
        session = GameSession(
            session_id=session_id,
            player_name=player_name,
            created_time=current_time,
            last_save_time=current_time,
            game_state=initial_state.copy(),
            character_data={},
            orchestrator_state={},
            statistics={}
        )
        
        self.current_session = session
        self.session_stats["sessions_created"] += 1
        
        return {
            "success": True,
            "result": {
                "session_id": session_id,
                "player_name": player_name,
                "created_time": current_time
            },
            "message": f"New session created for {player_name}"
        }
    
    def save_session(self, filename: Optional[str] = None,
                    orchestrator_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Save complete session state to file"""
        
        if not self.current_session:
            return {
                "success": False,
                "filepath": "",
                "message": "No active session to save"
            }
        
        try:
            # Generate filename if not provided
            if not filename:
                timestamp = int(time.time())
                filename = f"haystack_session_{timestamp}.json"
            
            filepath = self.save_directory / filename
            
            # Update session with latest data
            if orchestrator_state:
                self.current_session.orchestrator_state = orchestrator_state
            
            self.current_session.last_save_time = time.time()
            
            # Prepare save data
            save_data = {
                "session_metadata": {
                    "session_id": self.current_session.session_id,
                    "player_name": self.current_session.player_name,
                    "created_time": self.current_session.created_time,
                    "last_save_time": self.current_session.last_save_time,
                    "save_version": "2.0_haystack",
                    "session_manager_version": "1.0"
                },
                "game_state": self.current_session.game_state,
                "character_data": self.current_session.character_data,
                "orchestrator_state": self.current_session.orchestrator_state,
                "statistics": self.current_session.statistics,
                "session_stats": self.session_stats
            }
            
            # Write to file
            with open(filepath, 'w') as f:
                json.dump(save_data, f, indent=2)
            
            self.session_stats["successful_saves"] += 1
            
            return {
                "success": True,
                "result": {"filepath": str(filepath)},
                "message": f"Session saved successfully to {filename}"
            }
            
        except Exception as e:
            self.session_stats["failed_operations"] += 1
            return {
                "success": False,
                "result": {"filepath": ""},
                "message": f"Save failed: {str(e)}"
            }
    
    def load_session(self, filename: str) -> Dict[str, Any]:
        """Load session from file"""
        
        try:
            filepath = self.save_directory / filename
            
            if not filepath.exists():
                return {
                    "success": False,
                    "result": {},
                    "message": f"Save file not found: {filename}"
                }
            
            # Load save data
            with open(filepath, 'r') as f:
                save_data = json.load(f)
            
            # Validate save data structure
            if not self._validate_save_data(save_data):
                return {
                    "success": False,
                    "result": {},
                    "message": "Invalid save file format"
                }
            
            # Create session from save data
            metadata = save_data["session_metadata"]
            
            session = GameSession(
                session_id=metadata["session_id"],
                player_name=metadata["player_name"],
                created_time=metadata["created_time"],
                last_save_time=metadata["last_save_time"],
                game_state=save_data.get("game_state", {}),
                character_data=save_data.get("character_data", {}),
                orchestrator_state=save_data.get("orchestrator_state", {}),
                statistics=save_data.get("statistics", {})
            )
            
            self.current_session = session
            
            # Update session stats
            if "session_stats" in save_data:
                self.session_stats.update(save_data["session_stats"])
            
            self.session_stats["successful_loads"] += 1
            
            return {
                "success": True,
                "result": {
                    "session_id": session.session_id,
                    "player_name": session.player_name,
                    "game_state": session.game_state,
                    "character_data": session.character_data,
                    "orchestrator_state": session.orchestrator_state
                },
                "message": f"Session loaded successfully from {filename}"
            }
            
        except Exception as e:
            self.session_stats["failed_operations"] += 1
            return {
                "success": False,
                "result": {},
                "message": f"Load failed: {str(e)}"
            }
    
    def _validate_save_data(self, save_data: Dict[str, Any]) -> bool:
        """Validate save file structure"""
        
        required_fields = ["session_metadata", "game_state"]
        
        # Check required top-level fields
        for field in required_fields:
            if field not in save_data:
                return False
        
        # Check session metadata
        metadata = save_data["session_metadata"]
        required_metadata = ["session_id", "player_name", "created_time"]
        
        for field in required_metadata:
            if field not in metadata:
                return False
        
        return True
    
    def list_saves(self) -> Dict[str, List[Dict[str, Any]]]:
        """List available save files with metadata"""
        
        save_files = []
        
        try:
            for filepath in self.save_directory.glob("*.json"):
                try:
                    with open(filepath, 'r') as f:
                        save_data = json.load(f)
                    
                    if "session_metadata" in save_data:
                        metadata = save_data["session_metadata"]
                        save_files.append({
                            "filename": filepath.name,
                            "player_name": metadata.get("player_name", "Unknown"),
                            "created_time": metadata.get("created_time", 0),
                            "last_save_time": metadata.get("last_save_time", 0),
                            "save_version": metadata.get("save_version", "1.0"),
                            "file_size": filepath.stat().st_size
                        })
                    else:
                        # Legacy save file
                        save_files.append({
                            "filename": filepath.name,
                            "player_name": "Legacy Save",
                            "created_time": filepath.stat().st_mtime,
                            "last_save_time": filepath.stat().st_mtime,
                            "save_version": "legacy",
                            "file_size": filepath.stat().st_size
                        })
                        
                except Exception:
                    # Skip corrupted files
                    continue
        
        except Exception:
            pass
        
        # Sort by last save time (newest first)
        save_files.sort(key=lambda x: x["last_save_time"], reverse=True)
        
        return {"save_files": save_files}
    
    def update_session_state(self, state_updates: Dict[str, Any]):
        """Update current session state"""
        
        if self.current_session:
            self.current_session.game_state.update(state_updates)
    
    def update_character_data(self, character_data: Dict[str, Any]):
        """Update session character data"""
        
        if self.current_session:
            self.current_session.character_data.update(character_data)
    
    def get_session_state(self) -> Dict[str, Any]:
        """Get current session state for pipeline processing"""
        
        if not self.current_session:
            return {
                "session_active": False,
                "message": "No active session"
            }
        
        return {
            "session_active": True,
            "session_id": self.current_session.session_id,
            "player_name": self.current_session.player_name,
            "session_duration": time.time() - self.current_session.created_time,
            "game_state": self.current_session.game_state,
            "character_data": self.current_session.character_data
        }
    
    def get_session_statistics(self) -> Dict[str, Any]:
        """Get session manager statistics"""
        
        current_session_info = {}
        if self.current_session:
            current_session_info = {
                "session_id": self.current_session.session_id,
                "player_name": self.current_session.player_name,
                "session_duration": time.time() - self.current_session.created_time,
                "time_since_save": time.time() - self.current_session.last_save_time
            }
        
        return {
            "session_stats": self.session_stats,
            "current_session": current_session_info,
            "save_directory": str(self.save_directory),
            "available_saves": len(list(self.save_directory.glob("*.json")))
        }


# Factory function for easy integration
def create_session_manager(save_directory: str = "saves") -> SessionManager:
    """Factory function to create configured session manager"""
    return SessionManager(save_directory)


# Integration helper for orchestrator
def integrate_session_manager_with_orchestrator(orchestrator, session_manager: SessionManager):
    """Helper function to integrate session manager with orchestrator"""
    
    # Add session management handlers to orchestrator
    def handle_save_session(request: Dict[str, Any]) -> Dict[str, Any]:
        filename = request.get("filename")
        orchestrator_state = orchestrator.export_session_data()
        
        result = session_manager.save_session(filename, orchestrator_state)
        return {"success": result["success"], "data": result}
    
    def handle_load_session(request: Dict[str, Any]) -> Dict[str, Any]:
        filename = request.get("filename", "")
        result = session_manager.load_session(filename)
        
        if result["success"]:
            # Restore orchestrator state if available
            session_data = result["session_data"]
            if "orchestrator_state" in session_data:
                try:
                    orchestrator.import_session_data(session_data["orchestrator_state"])
                except:
                    pass  # Graceful degradation if import fails
        
        return {"success": result["success"], "data": result}
    
    def handle_list_saves(request: Dict[str, Any]) -> Dict[str, Any]:
        result = session_manager.list_saves()
        return {"success": True, "data": result}
    
    # Register handlers with orchestrator
    orchestrator.register_handler("save_session", handle_save_session)
    orchestrator.register_handler("load_session", handle_load_session)
    orchestrator.register_handler("list_saves", handle_list_saves)
    
    print("🔗 Session Manager integrated with orchestrator")


# Example usage and testing
if __name__ == "__main__":
    # Test session manager functionality
    manager = create_session_manager()
    
    # Create new session
    result = manager.create_new_session("Test Player", {
        "location": "Starting Area",
        "level": 1,
        "inventory": []
    })
    
    print("=== Session Manager Test ===")
    print(f"Create session: {result['success']} - {result['message']}")
    
    # Test save
    save_result = manager.save_session("test_session.json")
    print(f"Save session: {save_result['success']} - {save_result['message']}")
    
    # Test list saves
    saves_result = manager.list_saves()
    print(f"Available saves: {len(saves_result['save_files'])}")
    
    # Test load
    if saves_result["save_files"]:
        filename = saves_result["save_files"][0]["filename"]
        load_result = manager.load_session(filename)
        print(f"Load session: {load_result['success']} - {load_result['message']}")
    
    # Show statistics
    stats = manager.get_session_statistics()
    print(f"Session statistics: {stats}")