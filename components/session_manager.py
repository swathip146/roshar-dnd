"""
Session Manager - Persistent game session handling with Fixed System Support
Integrates with orchestrator for complete state management using Haystack component patterns
Enhanced for Fixed System DTO compatibility and routing history tracking
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from haystack import component

@dataclass
class GameSession:
    """Simplified session metadata - BREAKING CHANGE: No state duplication"""
    session_id: str
    player_name: str
    created_time: float
    last_save_time: float


@component
class SessionManager:
    """
    Manages game session persistence and state following Haystack patterns
    Handles save/load operations with full state integration
    """
    
    def __init__(self, save_directory: str = "game_saves"):
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
        """Main Haystack component interface for session operations - BREAKING CHANGE"""
        
        if operation == "create_session":
            return self.create_new_session(kwargs.get("player_name", "Player"),
                                         kwargs.get("initial_state", {}))
        elif operation == "save_session":
            # BREAKING CHANGE: Requires authoritative state to be passed in
            return self.save_session(kwargs.get("filename"),
                                   kwargs.get("game_engine_state"),
                                   kwargs.get("character_manager_state"))
        elif operation == "load_session":
            return self.load_session(kwargs.get("filename", ""))
        elif operation == "list_saves":
            return {"success": True, "result": self.list_saves(), "message": "Saves listed"}
        elif operation == "get_stats":
            return {"success": True, "result": self.get_session_statistics(), "message": "Stats retrieved"}
        elif operation == "get_metadata":
            return {"success": True, "result": self.get_session_metadata(), "message": "Metadata retrieved"}
        else:
            return {"success": False, "result": {}, "message": f"Unknown operation: {operation}"}
    
    def create_new_session(self, player_name: str, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new game session - BREAKING CHANGE: Metadata only, no state duplication"""
        
        session_id = f"session_{int(time.time())}"
        current_time = time.time()
        
        # BREAKING CHANGE: Only store metadata, no state duplication
        session = GameSession(
            session_id=session_id,
            player_name=player_name,
            created_time=current_time,
            last_save_time=current_time
        )
        
        self.current_session = session
        self.session_stats["sessions_created"] += 1
        
        # Note: initial_state is ignored - GameEngine manages its own state
        
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
                    game_engine_state: Optional[Dict[str, Any]] = None,
                    character_manager_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Save complete session state - BREAKING CHANGE: Collects from authoritative sources"""
        
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
            
            # Update session timestamp
            self.current_session.last_save_time = time.time()
            
            # BREAKING CHANGE: Collect state from authoritative sources, don't duplicate
            save_data = {
                "session_metadata": {
                    "session_id": self.current_session.session_id,
                    "player_name": self.current_session.player_name,
                    "created_time": self.current_session.created_time,
                    "last_save_time": self.current_session.last_save_time,
                    "save_version": "4.0_clean_slate",  # Updated version for clean architecture
                    "session_manager_version": "3.0"
                },
                # State from authoritative sources (passed in by orchestrator)
                "game_state": game_engine_state or {},
                "character_data": character_manager_state or {},
                "session_stats": self.session_stats,
                
                # Fixed System routing history (SessionManager owns this)
                "fixed_system_data": {
                    "routing_history": getattr(self, '_routing_history', [])[-20:],  # Last 20 decisions
                }
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
        """Load session from file - BREAKING CHANGE: Returns data for authoritative sources"""
        
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
            
            # Create session from metadata only
            metadata = save_data["session_metadata"]
            
            session = GameSession(
                session_id=metadata["session_id"],
                player_name=metadata["player_name"],
                created_time=metadata["created_time"],
                last_save_time=metadata["last_save_time"]
            )
            
            self.current_session = session
            
            # Update session stats
            if "session_stats" in save_data:
                self.session_stats.update(save_data["session_stats"])
            
            # Restore routing history if available
            if "fixed_system_data" in save_data:
                self._routing_history = save_data["fixed_system_data"].get("routing_history", [])
            
            self.session_stats["successful_loads"] += 1
            
            # BREAKING CHANGE: Return state data for authoritative sources to import
            return {
                "success": True,
                "result": {
                    "session_metadata": {
                        "session_id": session.session_id,
                        "player_name": session.player_name,
                        "created_time": session.created_time,
                        "last_save_time": session.last_save_time
                    },
                    "game_state": save_data.get("game_state", {}),
                    "character_data": save_data.get("character_data", {}),
                    "orchestrator_state": save_data.get("orchestrator_state", {})  # Legacy compatibility
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
                            "fixed_system_compatible": metadata.get("fixed_system_compatible", False),
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
    
    def get_session_metadata(self) -> Dict[str, Any]:
        """Get current session metadata only - BREAKING CHANGE: No state management"""
        
        if not self.current_session:
            return {
                "session_active": False,
                "message": "No active session"
            }
        
        return {
            "session_active": True,
            "session_id": self.current_session.session_id,
            "player_name": self.current_session.player_name,
            "created_time": self.current_session.created_time,
            "last_save_time": self.current_session.last_save_time,
            "session_duration": time.time() - self.current_session.created_time
        }
    
    def get_session_statistics(self) -> Dict[str, Any]:
        """Get session manager statistics - persistence metrics only"""
        
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
            "available_saves": len(list(self.save_directory.glob("*.json"))),
            "routing_history_entries": len(getattr(self, '_routing_history', []))
        }
    
    def add_routing_decision(self, routing_data: Dict[str, Any]):
        """Add routing decision to history for Fixed System tracking"""
        if not hasattr(self, '_routing_history'):
            self._routing_history = []
        
        routing_entry = {
            "timestamp": time.time(),
            "route": routing_data.get("route", "unknown"),
            "confidence": routing_data.get("confidence", 0.0),
            "player_input": routing_data.get("player_input", ""),
            "type": routing_data.get("type", "unknown")
        }
        
        self._routing_history.append(routing_entry)
        
        # Keep only last 50 entries to manage memory
        if len(self._routing_history) > 50:
            self._routing_history = self._routing_history[-50:]
    
    def get_routing_statistics(self) -> Dict[str, Any]:
        """Get routing decision statistics for Fixed System analysis"""
        if not hasattr(self, '_routing_history'):
            return {"total_decisions": 0, "route_distribution": {}}
        
        total = len(self._routing_history)
        route_counts = {}
        confidence_sum = 0
        
        for entry in self._routing_history:
            route = entry.get("route", "unknown")
            route_counts[route] = route_counts.get(route, 0) + 1
            confidence_sum += entry.get("confidence", 0)
        
        return {
            "total_decisions": total,
            "route_distribution": route_counts,
            "average_confidence": confidence_sum / total if total > 0 else 0,
            "fixed_system_tracking": True
        }
    
    def record_turn_analytics(self, input_data: Dict[str, Any], response_type: str, confidence: float, turn_number: int):
        """Record turn analytics for persistence - no game state logic"""
        
        # SessionManager only handles persistence and analytics
        routing_data = {
            "route": response_type,
            "confidence": confidence,
            "player_input": input_data.get("original_input", ""),
            "input_type": input_data.get("type", "unknown"),
            "turn_number": turn_number,
            "timestamp": time.time()
        }
        
        # Use existing persistence method
        self.add_routing_decision(routing_data)


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
        return {"success": result["success"], "result": result}
    
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
        
        return {"success": result["success"], "result": result}
    
    def handle_list_saves(request: Dict[str, Any]) -> Dict[str, Any]:
        result = session_manager.list_saves()
        return {"success": True, "result": result}
    
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