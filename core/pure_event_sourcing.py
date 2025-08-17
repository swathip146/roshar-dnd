"""
Pure Event Sourcing Components for Haystack D&D Assistant
No external dependencies to avoid circular imports
"""

import time
import uuid
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class GameEvent:
    """
    Immutable event representing a change in game state
    Pure implementation without external dependencies
    """
    event_id: str
    event_type: str
    actor: str
    payload: Dict[str, Any]
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GameEvent':
        """Create event from dictionary"""
        return cls(**data)


class EventStore:
    """
    Simple in-memory event store for game events
    Pure implementation without external dependencies
    """
    
    def __init__(self):
        self.events: List[GameEvent] = []
        self.event_index: Dict[str, GameEvent] = {}
    
    def append_event(self, event: GameEvent) -> bool:
        """Append event to store"""
        try:
            # Ensure unique event ID
            if event.event_id in self.event_index:
                # Generate new ID if duplicate
                event.event_id = f"{event.event_id}_{len(self.events)}"
            
            self.events.append(event)
            self.event_index[event.event_id] = event
            return True
            
        except Exception:
            return False
    
    def get_events_by_type(self, event_type: str) -> List[GameEvent]:
        """Get all events of a specific type"""
        return [event for event in self.events if event.event_type == event_type]
    
    def get_events_by_actor(self, actor: str) -> List[GameEvent]:
        """Get all events from a specific actor"""
        return [event for event in self.events if event.actor == actor]
    
    def get_events_since(self, timestamp: float) -> List[GameEvent]:
        """Get all events since a timestamp"""
        return [event for event in self.events if event.timestamp >= timestamp]
    
    def get_event_count(self) -> int:
        """Get total event count"""
        return len(self.events)
    
    def clear(self):
        """Clear all events"""
        self.events.clear()
        self.event_index.clear()


class StateProjector:
    """
    Project current state from event stream
    Pure implementation without external dependencies
    """
    
    def __init__(self):
        self.initial_state = {
            "characters": {},
            "campaign": {},
            "session": {
                "active": False,
                "start_time": None,
                "session_id": None
            },
            "combat": {
                "active": False,
                "turn_order": [],
                "current_turn": 0
            },
            "world_state": {},
            "last_projected": 0
        }
    
    def project_state(self, events: List[GameEvent]) -> Dict[str, Any]:
        """Project current state from event stream"""
        
        # Start with initial state
        current_state = self.initial_state.copy()
        
        # Apply events in chronological order
        sorted_events = sorted(events, key=lambda e: e.timestamp)
        
        for event in sorted_events:
            current_state = self._apply_event_to_state(current_state, event)
        
        # Update projection timestamp
        current_state["last_projected"] = time.time()
        
        return current_state
    
    def _apply_event_to_state(self, state: Dict[str, Any], event: GameEvent) -> Dict[str, Any]:
        """Apply single event to state"""
        
        try:
            if event.event_type == "game_state.updated":
                # Direct state update
                for key, value in event.payload.items():
                    if key in state:
                        if isinstance(state[key], dict) and isinstance(value, dict):
                            state[key].update(value)
                        else:
                            state[key] = value
            
            elif event.event_type == "character.created":
                char_data = event.payload
                char_id = char_data.get("character_id", event.actor)
                state.setdefault("characters", {})[char_id] = char_data
            
            elif event.event_type == "character.updated":
                char_data = event.payload
                char_id = char_data.get("character_id", event.actor)
                if char_id in state.get("characters", {}):
                    state["characters"][char_id].update(char_data)
            
            elif event.event_type == "session.started":
                state["session"].update({
                    "active": True,
                    "start_time": event.timestamp,
                    "session_id": event.payload.get("session_id", str(uuid.uuid4()))
                })
            
            elif event.event_type == "session.ended":
                state["session"].update({
                    "active": False,
                    "end_time": event.timestamp
                })
            
            elif event.event_type == "combat.started":
                state["combat"].update({
                    "active": True,
                    "turn_order": event.payload.get("turn_order", []),
                    "current_turn": 0
                })
            
            elif event.event_type == "combat.ended":
                state["combat"].update({
                    "active": False,
                    "turn_order": [],
                    "current_turn": 0
                })
            
            elif event.event_type == "campaign.loaded":
                state["campaign"].update(event.payload)
            
            # Add more event type handlers as needed
            
        except Exception:
            # Ignore events that can't be applied
            pass
        
        return state
    
    def get_character_state(self, state: Dict[str, Any], character_id: str) -> Optional[Dict[str, Any]]:
        """Get specific character state from projected state"""
        return state.get("characters", {}).get(character_id)
    
    def get_session_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Get session state from projected state"""
        return state.get("session", {})
    
    def get_combat_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Get combat state from projected state"""
        return state.get("combat", {})