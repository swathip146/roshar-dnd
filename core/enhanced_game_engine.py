"""
Enhanced Game Engine for Haystack Integration
Provides centralized state management and event sourcing as single source of truth
"""

import json
import threading
import time
import uuid
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path

from core.messaging import AgentMessage, MessageType
from agent_framework import BaseAgent


class EventType(Enum):
    """Types of game events for event sourcing"""
    PLAYER_ACTION = "player_action"
    SKILL_CHECK = "skill_check"
    SCENARIO_CHOICE = "scenario_choice"
    STATE_UPDATE = "state_update"
    NPC_ACTION = "npc_action"
    COMBAT_ACTION = "combat_action"
    GAME_START = "game_start"
    GAME_END = "game_end"
    SCENE_CHANGE = "scene_change"
    CHARACTER_UPDATE = "character_update"


@dataclass
class GameEvent:
    """Represents a single game event for event sourcing"""
    event_id: str
    event_type: EventType
    timestamp: float
    actor: str
    data: Dict[str, Any]
    correlation_id: Optional[str] = None
    processed: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "actor": self.actor,
            "data": self.data,
            "correlation_id": self.correlation_id,
            "processed": self.processed
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GameEvent':
        """Create from dictionary"""
        return cls(
            event_id=data["event_id"],
            event_type=EventType(data["event_type"]),
            timestamp=data["timestamp"],
            actor=data["actor"],
            data=data["data"],
            correlation_id=data.get("correlation_id"),
            processed=data.get("processed", False)
        )


class EventStore:
    """Event store for game event sourcing"""
    
    def __init__(self, storage_path: str = "./game_events.json"):
        self.storage_path = storage_path
        self.events: List[GameEvent] = []
        self.lock = threading.RLock()
        self.load_events()
    
    def append_event(self, event: GameEvent) -> str:
        """Append an event to the store"""
        with self.lock:
            self.events.append(event)
            self.save_events()
            return event.event_id
    
    def get_events_since(self, timestamp: float) -> List[GameEvent]:
        """Get events since a specific timestamp"""
        with self.lock:
            return [e for e in self.events if e.timestamp >= timestamp]
    
    def get_events_by_correlation(self, correlation_id: str) -> List[GameEvent]:
        """Get events by correlation ID"""
        with self.lock:
            return [e for e in self.events if e.correlation_id == correlation_id]
    
    def get_events_by_actor(self, actor: str) -> List[GameEvent]:
        """Get events by actor"""
        with self.lock:
            return [e for e in self.events if e.actor == actor]
    
    def save_events(self):
        """Save events to storage"""
        try:
            events_data = [event.to_dict() for event in self.events[-1000:]]  # Keep last 1000 events
            with open(self.storage_path, 'w') as f:
                json.dump(events_data, f, indent=2)
        except Exception:
            pass  # Silently fail for now
    
    def load_events(self):
        """Load events from storage"""
        try:
            if Path(self.storage_path).exists():
                with open(self.storage_path, 'r') as f:
                    events_data = json.load(f)
                    self.events = [GameEvent.from_dict(data) for data in events_data]
        except Exception:
            self.events = []


class StateProjector:
    """Projects game state from event stream"""
    
    def __init__(self):
        self.state_handlers = {
            EventType.PLAYER_ACTION: self._handle_player_action,
            EventType.SKILL_CHECK: self._handle_skill_check,
            EventType.SCENARIO_CHOICE: self._handle_scenario_choice,
            EventType.STATE_UPDATE: self._handle_state_update,
            EventType.CHARACTER_UPDATE: self._handle_character_update,
            EventType.SCENE_CHANGE: self._handle_scene_change
        }
    
    def project_state(self, events: List[GameEvent], initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """Project current state from event stream"""
        state = initial_state.copy()
        
        for event in sorted(events, key=lambda e: e.timestamp):
            if event.processed:
                continue
                
            handler = self.state_handlers.get(event.event_type)
            if handler:
                try:
                    handler(state, event)
                    event.processed = True
                except Exception as e:
                    # Log error but continue processing
                    state.setdefault("errors", []).append({
                        "event_id": event.event_id,
                        "error": str(e),
                        "timestamp": time.time()
                    })
        
        # Update metadata
        state["last_projected"] = time.time()
        state["event_count"] = len(events)
        
        return state
    
    def _handle_player_action(self, state: Dict[str, Any], event: GameEvent):
        """Handle player action event"""
        action_data = event.data
        actor = event.actor
        
        # Ensure player exists in state
        if actor not in state.setdefault("players", {}):
            state["players"][actor] = {"name": actor, "actions": []}
        
        # Record the action
        state["players"][actor]["actions"].append({
            "action": action_data,
            "timestamp": event.timestamp,
            "event_id": event.event_id
        })
        
        # Update session events
        state.setdefault("session", {}).setdefault("events", []).append(
            f"{actor} performed action: {action_data.get('type', 'unknown')}"
        )
    
    def _handle_skill_check(self, state: Dict[str, Any], event: GameEvent):
        """Handle skill check event"""
        skill_data = event.data
        actor = event.actor
        
        # Ensure player exists
        if actor not in state.setdefault("players", {}):
            state["players"][actor] = {"name": actor}
        
        # Record skill check result
        state["players"][actor].setdefault("skill_checks", []).append({
            "skill": skill_data.get("skill"),
            "total": skill_data.get("total"),
            "success": skill_data.get("success"),
            "timestamp": event.timestamp,
            "event_id": event.event_id
        })
        
        # Update session
        success_text = "succeeded" if skill_data.get("success") else "failed"
        state.setdefault("session", {}).setdefault("events", []).append(
            f"{actor} {success_text} {skill_data.get('skill', 'unknown')} check"
        )
    
    def _handle_scenario_choice(self, state: Dict[str, Any], event: GameEvent):
        """Handle scenario choice event"""
        choice_data = event.data
        actor = event.actor
        
        # Update current scenario
        state["current_scenario"] = choice_data.get("consequence_text", "")
        state["current_options"] = choice_data.get("new_options", [])
        
        # Record in scene history
        state.setdefault("scene_history", []).append({
            "actor": actor,
            "choice": choice_data.get("choice"),
            "consequence": choice_data.get("consequence_text"),
            "timestamp": event.timestamp,
            "event_id": event.event_id
        })
        
        # Update session
        state.setdefault("session", {}).setdefault("events", []).append(
            f"{actor} made scenario choice {choice_data.get('choice', '?')}"
        )
    
    def _handle_state_update(self, state: Dict[str, Any], event: GameEvent):
        """Handle direct state update event"""
        updates = event.data.get("updates", {})
        state.update(updates)
    
    def _handle_character_update(self, state: Dict[str, Any], event: GameEvent):
        """Handle character update event"""
        character_data = event.data
        character_name = event.actor
        
        # Update character in players
        if character_name not in state.setdefault("players", {}):
            state["players"][character_name] = {"name": character_name}
        
        state["players"][character_name].update(character_data)
    
    def _handle_scene_change(self, state: Dict[str, Any], event: GameEvent):
        """Handle scene change event"""
        scene_data = event.data
        
        state["current_scenario"] = scene_data.get("scenario_text", "")
        state["current_options"] = scene_data.get("options", [])
        state.setdefault("session", {})["location"] = scene_data.get("location", "unknown")


class EnhancedGameEngineAgent(BaseAgent):
    """
    Enhanced Game Engine Agent with centralized state management and event sourcing
    
    Serves as the single source of truth for all game state in the D&D Assistant,
    with full integration with Haystack pipelines.
    """
    
    def __init__(self, 
                 initial_state: Optional[Dict[str, Any]] = None,
                 event_store: Optional[EventStore] = None,
                 projector: Optional[StateProjector] = None,
                 tick_seconds: float = 0.5,
                 verbose: bool = False):
        super().__init__("enhanced_game_engine", "EnhancedGameEngine", verbose=verbose)
        
        # Core components
        self.event_store = event_store or EventStore()
        self.projector = projector or StateProjector()
        self.tick_seconds = tick_seconds
        
        # State management
        self.base_state = initial_state or self._build_default_state()
        self.current_state = self.base_state.copy()
        self.lock = threading.RLock()
        self.last_projection = time.time()
        
        # Event handlers
        self.event_listeners: Dict[EventType, List[Callable]] = {}
        
        # State change tracking
        self.state_version = 0
        self.last_state_hash = self._hash_state(self.current_state)
        
        # Rebuild state from events
        self._rebuild_state_from_events()
    
    def _setup_handlers(self):
        """Setup message handlers for enhanced game engine"""
        # Core game engine handlers
        self.register_handler("get_game_state", self._handle_get_game_state)
        self.register_handler("update_game_state", self._handle_update_game_state)
        self.register_handler("get_character_data", self._handle_get_character_data)
        
        # Event sourcing handlers
        self.register_handler("emit_event", self._handle_emit_event)
        self.register_handler("get_events", self._handle_get_events)
        self.register_handler("rebuild_state", self._handle_rebuild_state)
        
        # Haystack integration handlers
        self.register_handler("apply_skill_check_result", self._handle_apply_skill_check_result)
        self.register_handler("update_scenario_state", self._handle_update_scenario_state)
        self.register_handler("apply_character_update", self._handle_apply_character_update)
        
        # State validation
        self.register_handler("validate_state", self._handle_validate_state)
        self.register_handler("get_state_health", self._handle_get_state_health)
    
    def _build_default_state(self) -> Dict[str, Any]:
        """Build default game state structure"""
        return {
            "players": {},
            "npcs": {},
            "world": {
                "locations": [],
                "current_location": "starting_area"
            },
            "story_arc": "",
            "scene_history": [],
            "current_scenario": "",
            "current_options": [],
            "session": {
                "location": "unknown", 
                "time": "day_1",
                "events": [],
                "started_at": time.time()
            },
            "combat": {
                "active": False,
                "participants": [],
                "round": 0
            },
            "metadata": {
                "version": "1.0",
                "created_at": time.time(),
                "engine": "enhanced_game_engine"
            }
        }
    
    def _rebuild_state_from_events(self):
        """Rebuild current state from event store"""
        with self.lock:
            events = self.event_store.events
            self.current_state = self.projector.project_state(events, self.base_state.copy())
            self.state_version += 1
            self.last_state_hash = self._hash_state(self.current_state)
            
            if self.verbose:
                print(f"🔄 State rebuilt from {len(events)} events")
    
    def emit_event(self, event_type: EventType, actor: str, data: Dict[str, Any], 
                   correlation_id: Optional[str] = None) -> str:
        """Emit a new game event"""
        event = GameEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            timestamp=time.time(),
            actor=actor,
            data=data,
            correlation_id=correlation_id
        )
        
        # Store event
        self.event_store.append_event(event)
        
        # Trigger listeners
        listeners = self.event_listeners.get(event_type, [])
        for listener in listeners:
            try:
                listener(event)
            except Exception as e:
                if self.verbose:
                    print(f"⚠️ Event listener error: {e}")
        
        # Schedule state rebuild
        self._schedule_state_rebuild()
        
        if self.verbose:
            print(f"📢 Event emitted: {event_type.value} by {actor}")
        
        return event.event_id
    
    def add_event_listener(self, event_type: EventType, listener: Callable):
        """Add an event listener"""
        if event_type not in self.event_listeners:
            self.event_listeners[event_type] = []
        self.event_listeners[event_type].append(listener)
    
    def _schedule_state_rebuild(self):
        """Schedule a state rebuild on next tick"""
        # For now, rebuild immediately for consistency
        # Could be optimized to batch rebuilds
        self._rebuild_state_from_events()
    
    def _hash_state(self, state: Dict[str, Any]) -> str:
        """Create a hash of the state for change detection"""
        import hashlib
        state_str = json.dumps(state, sort_keys=True, default=str)
        return hashlib.md5(state_str.encode()).hexdigest()
    
    # Message Handlers
    
    def _handle_get_game_state(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle game state request"""
        with self.lock:
            return {
                "success": True,
                "game_state": self.current_state.copy(),
                "state_version": self.state_version,
                "last_updated": self.last_projection
            }
    
    def _handle_update_game_state(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle game state update request"""
        updates = message.data.get("updates", {})
        correlation_id = message.data.get("correlation_id")
        
        if not updates:
            return {"success": False, "error": "No updates provided"}
        
        # Emit state update event
        event_id = self.emit_event(
            EventType.STATE_UPDATE,
            "system",
            {"updates": updates},
            correlation_id
        )
        
        return {
            "success": True, 
            "message": "Game state updated",
            "event_id": event_id,
            "state_version": self.state_version
        }
    
    def _handle_get_character_data(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle character data request"""
        actor_name = message.data.get("actor", "unknown")
        
        with self.lock:
            character = self.current_state.get("players", {}).get(actor_name, {})
            
            if not character:
                # Create default character
                character = {
                    "name": actor_name,
                    "level": 1,
                    "class": "fighter",
                    "hp": 20,
                    "modifiers": {
                        "strength": 2,
                        "dexterity": 1, 
                        "constitution": 2,
                        "intelligence": 0,
                        "wisdom": 1,
                        "charisma": 0
                    },
                    "proficiencies": ["athletics", "intimidation"],
                    "conditions": []
                }
        
        return {
            "success": True,
            "character_data": character,
            "modifiers": character.get("modifiers", {}),
            "proficiencies": character.get("proficiencies", []),
            "conditions": character.get("conditions", [])
        }
    
    def _handle_emit_event(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle direct event emission request"""
        event_type_str = message.data.get("event_type")
        actor = message.data.get("actor", "unknown")
        event_data = message.data.get("data", {})
        correlation_id = message.data.get("correlation_id")
        
        try:
            event_type = EventType(event_type_str)
            event_id = self.emit_event(event_type, actor, event_data, correlation_id)
            
            return {
                "success": True,
                "event_id": event_id,
                "message": f"Event {event_type_str} emitted"
            }
        except ValueError:
            return {
                "success": False,
                "error": f"Invalid event type: {event_type_str}"
            }
    
    def _handle_get_events(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle event retrieval request"""
        since_timestamp = message.data.get("since", 0)
        correlation_id = message.data.get("correlation_id")
        actor = message.data.get("actor")
        
        with self.lock:
            if correlation_id:
                events = self.event_store.get_events_by_correlation(correlation_id)
            elif actor:
                events = self.event_store.get_events_by_actor(actor)
            else:
                events = self.event_store.get_events_since(since_timestamp)
        
        return {
            "success": True,
            "events": [event.to_dict() for event in events],
            "count": len(events)
        }
    
    def _handle_rebuild_state(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle state rebuild request"""
        self._rebuild_state_from_events()
        
        return {
            "success": True,
            "message": "State rebuilt from events",
            "state_version": self.state_version,
            "event_count": len(self.event_store.events)
        }
    
    def _handle_apply_skill_check_result(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle skill check result from Haystack pipeline"""
        payload = message.data.get("payload", {})
        actor = payload.get("actor", "unknown")
        correlation_id = message.data.get("correlation_id")
        
        # Emit skill check event
        event_id = self.emit_event(
            EventType.SKILL_CHECK,
            actor,
            payload,
            correlation_id
        )
        
        return {
            "success": True,
            "event_id": event_id,
            "message": f"Skill check result applied for {actor}"
        }
    
    def _handle_update_scenario_state(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle scenario state update from Haystack pipeline"""
        payload = message.data.get("payload", {})
        actor = payload.get("actor", "system")
        correlation_id = message.data.get("correlation_id")
        
        # Emit scenario choice event
        event_id = self.emit_event(
            EventType.SCENARIO_CHOICE,
            actor,
            payload.get("scenario_result", {}),
            correlation_id
        )
        
        return {
            "success": True,
            "event_id": event_id,
            "message": f"Scenario state updated for {actor}"
        }
    
    def _handle_apply_character_update(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle character update"""
        character_data = message.data.get("character_data", {})
        character_name = message.data.get("character_name")
        correlation_id = message.data.get("correlation_id")
        
        if not character_name:
            return {"success": False, "error": "No character name provided"}
        
        # Emit character update event
        event_id = self.emit_event(
            EventType.CHARACTER_UPDATE,
            character_name,
            character_data,
            correlation_id
        )
        
        return {
            "success": True,
            "event_id": event_id,
            "message": f"Character {character_name} updated"
        }
    
    def _handle_validate_state(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle state validation request"""
        with self.lock:
            issues = []
            
            # Check required fields
            required_fields = ["players", "session", "world"]
            for field in required_fields:
                if field not in self.current_state:
                    issues.append(f"Missing required field: {field}")
            
            # Check state consistency
            current_hash = self._hash_state(self.current_state)
            if current_hash != self.last_state_hash:
                issues.append("State hash mismatch - state may have been modified externally")
            
            return {
                "success": len(issues) == 0,
                "issues": issues,
                "state_version": self.state_version,
                "validation_timestamp": time.time()
            }
    
    def _handle_get_state_health(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle state health check request"""
        with self.lock:
            return {
                "success": True,
                "health": {
                    "state_version": self.state_version,
                    "event_count": len(self.event_store.events),
                    "player_count": len(self.current_state.get("players", {})),
                    "last_projection": self.last_projection,
                    "uptime_seconds": time.time() - self.current_state.get("metadata", {}).get("created_at", time.time())
                }
            }
    
    def process_tick(self):
        """Process one enhanced game engine tick"""
        current_time = time.time()
        
        # Check if state needs rebuilding
        if current_time - self.last_projection > self.tick_seconds:
            with self.lock:
                # Check for new events and rebuild if needed
                new_events = self.event_store.get_events_since(self.last_projection)
                if new_events:
                    self._rebuild_state_from_events()
                
                # Broadcast state update if changed
                new_hash = self._hash_state(self.current_state)
                if new_hash != self.last_state_hash:
                    self.broadcast_event("game_state_updated", {
                        "game_state": self.current_state.copy(),
                        "timestamp": current_time,
                        "state_version": self.state_version
                    })
                    self.last_state_hash = new_hash
                
                self.last_projection = current_time
    
    def get_state_summary(self) -> Dict[str, Any]:
        """Get a summary of the current game state"""
        with self.lock:
            return {
                "players": list(self.current_state.get("players", {}).keys()),
                "current_location": self.current_state.get("world", {}).get("current_location", "unknown"),
                "scenario_active": bool(self.current_state.get("current_scenario")),
                "combat_active": self.current_state.get("combat", {}).get("active", False),
                "event_count": len(self.event_store.events),
                "state_version": self.state_version,
                "last_updated": self.last_projection
            }