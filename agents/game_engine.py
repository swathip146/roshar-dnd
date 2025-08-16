"""
Game Engine for DM Assistant
Manages game state, action processing, and real-time game loop
"""
import json
import threading
import time
import os
from typing import Dict, List, Any, Optional
from pathlib import Path

from agent_framework import BaseAgent, MessageType, AgentMessage


class JSONPersister:
    """File-based JSON persistence for game state"""
    
    def __init__(self, path: str = "./game_state_checkpoint.json"):
        self.path = path

    def save(self, game_state: Dict[str, Any]):
        """Save game state to JSON file"""
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(game_state, f, indent=2)
        except Exception:
            pass

    def load(self) -> Optional[Dict[str, Any]]:
        """Load game state from JSON file"""
        if not os.path.exists(self.path):
            return None
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None


class GameEngineAgent(BaseAgent):
    """Game Engine as an agent that manages game state and processes actions"""
    
    DEFAULT_TICK_SECONDS = 0.8
    
    def __init__(self, 
                 initial_state: Optional[Dict[str, Any]] = None,
                 persister: Optional[JSONPersister] = None,
                 tick_seconds: float = None):
        super().__init__("game_engine", "GameEngine")
        
        self.tick_seconds = tick_seconds or self.DEFAULT_TICK_SECONDS
        self.persister = persister or JSONPersister()
        
        # Initialize game state
        self.game_state = initial_state or self._build_default_state()
        
        # Try to load existing state
        if self.persister:
            saved_state = self.persister.load()
            if saved_state:
                self.game_state.update(saved_state)
        
        self.lock = threading.RLock()
        self.last_tick = time.time()
    
    def _setup_handlers(self):
        """Setup message handlers for game engine"""
        self.register_handler("enqueue_action", self._handle_enqueue_action)
        self.register_handler("get_game_state", self._handle_get_game_state)
        self.register_handler("update_game_state", self._handle_update_game_state)
        self.register_handler("process_player_action", self._handle_process_player_action)
        self.register_handler("should_generate_scene", self._handle_should_generate_scene)
        self.register_handler("add_scene_to_history", self._handle_add_scene_to_history)
    
    def _build_default_state(self) -> Dict[str, Any]:
        """Build default game state"""
        return {
            "players": {},
            "npcs": {},
            "world": {"locations": []},
            "story_arc": "",
            "scene_history": [],
            "current_scenario": "",
            "current_options": "",
            "session": {"location": "unknown", "time": "", "events": []},
            "action_queue": []
        }
    
    def enqueue_action(self, action: Dict[str, Any]):
        """Enqueue an action for processing"""
        with self.lock:
            self.game_state["action_queue"].append(action)
    
    def _handle_enqueue_action(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle action enqueue request"""
        action = message.data.get("action")
        if action:
            self.enqueue_action(action)
            return {"success": True, "message": "Action enqueued"}
        return {"success": False, "error": "No action provided"}
    
    def _handle_get_game_state(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle game state request"""
        with self.lock:
            return {"game_state": self.game_state.copy()}
    
    def _handle_update_game_state(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle game state update request"""
        updates = message.data.get("updates")
        if updates:
            with self.lock:
                self.game_state.update(updates)
            return {"success": True, "message": "Game state updated"}
        return {"success": False, "error": "No updates provided"}
    
    def _handle_process_player_action(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle player action processing request"""
        action = message.data.get("action")
        if action:
            result = self._process_player_action(action)
            return {"success": True, "result": result}
        return {"success": False, "error": "No action provided"}
    
    def _handle_should_generate_scene(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle scene generation check request"""
        should_generate = self._should_generate_scene()
        return {"should_generate": should_generate}
    
    def _handle_add_scene_to_history(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle adding scene to history"""
        scene_data = message.data.get("scene_data")
        options_text = message.data.get("options_text")
        
        if scene_data:
            with self.lock:
                self.game_state["scene_history"].append(scene_data)
                self.game_state["current_scenario"] = scene_data
                if options_text:
                    self.game_state["current_options"] = options_text
                self.game_state["session"]["events"].append("New scene generated")
            return {"success": True, "message": "Scene added to history"}
        return {"success": False, "error": "No scene data provided"}
    
    def _process_player_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Process a player action and update game state"""
        with self.lock:
            action_type = action.get("type")
            actor = action.get("actor")
            args = action.get("args", {})
            
            if action_type == "move":
                new_loc = args.get("to")
                if actor in self.game_state["players"]:
                    self.game_state["players"][actor]["location"] = new_loc
                    self.game_state["session"]["events"].append(f"{actor} moved to {new_loc}")
                    return {"success": True, "message": f"{actor} moved to {new_loc}"}
            
            elif action_type == "choose_option":
                choice = args.get("choice")
                # Notify scenario generator about player choice
                self.send_message("scenario_generator", "apply_player_choice", {
                    "game_state": self.game_state.copy(),
                    "player": actor,
                    "choice": choice
                })
                return {"success": True, "message": f"{actor} chose option {choice}"}
            
            elif action_type == "raw_event":
                event = args.get("text")
                if event:
                    self.game_state["session"]["events"].append(event)
                    return {"success": True, "message": f"Event added: {event}"}
            
            else:
                error_msg = f"Unhandled action type: {action_type}"
                self.game_state["session"]["events"].append(error_msg)
                return {"success": False, "error": error_msg}
    
    def _should_generate_scene(self) -> bool:
        """Check if a new scene should be generated"""
        if not self.game_state.get("current_scenario"):
            return True
        
        recent_events = self.game_state["session"].get("events", [])[-4:]
        return any("chose" in e.lower() or "new scene requested" in e.lower() 
                  for e in recent_events)
    
    def process_tick(self):
        """Process one game engine tick"""
        current_time = time.time()
        
        # Only process if enough time has passed
        if current_time - self.last_tick < self.tick_seconds:
            return
        
        self.last_tick = current_time
        
        with self.lock:
            # Process action queue FIFO
            while self.game_state.get("action_queue"):
                action = self.game_state["action_queue"].pop(0)
                try:
                    self._process_player_action(action)
                except Exception as e:
                    self.game_state["session"]["events"].append(f"Error processing action: {e}")
            
            # Check if NPCs need to make decisions
            if self.game_state.get("npcs"):
                self.send_message("npc_controller", "make_decisions", {
                    "game_state": self.game_state.copy()
                })
            
            # Check if scenario generation is needed
            if self._should_generate_scene():
                self.send_message("scenario_generator", "generate_scenario", {
                    "game_state": self.game_state.copy()
                })
            
            # Persist game state
            if self.persister:
                try:
                    self.persister.save(self.game_state)
                except Exception:
                    pass
            
            # Broadcast game state update
            self.broadcast_event("game_state_updated", {
                "game_state": self.game_state.copy(),
                "timestamp": current_time
            })


class GameEngine:
    """Traditional GameEngine class for backward compatibility"""
    
    def __init__(self,
                 initial_state: Optional[Dict[str, Any]] = None,
                 npc_controller=None,
                 scenario_generator=None,
                 persister: Optional[JSONPersister] = None,
                 tick_seconds: float = GameEngineAgent.DEFAULT_TICK_SECONDS):
        
        self.game_state = initial_state or {
            "players": {},
            "npcs": {},
            "world": {"locations": []},
            "story_arc": "",
            "scene_history": [],
            "current_scenario": "",
            "current_options": "",
            "session": {"location": "unknown", "time": "", "events": []},
            "action_queue": []
        }
        
        self.npc_controller = npc_controller
        self.scenario_generator = scenario_generator
        self.persister = persister
        self.tick_seconds = tick_seconds
        self.running = False
        self.lock = threading.RLock()
    
    def enqueue_action(self, action: Dict[str, Any]):
        """Enqueue an action for processing"""
        with self.lock:
            self.game_state["action_queue"].append(action)
    
    def _process_player_action(self, action: Dict[str, Any]):
        """Process a player action"""
        action_type = action.get("type")
        actor = action.get("actor")
        args = action.get("args", {})
        
        if action_type == "move":
            new_loc = args.get("to")
            if actor in self.game_state["players"]:
                self.game_state["players"][actor]["location"] = new_loc
                self.game_state["session"]["events"].append(f"{actor} moved to {new_loc}")
        
        elif action_type == "choose_option":
            choice = args.get("choice")
            if self.scenario_generator:
                cont = self.scenario_generator.apply_player_choice(self.game_state, actor, choice)
                if cont:
                    self.game_state["scene_history"].append(cont)
                    self.game_state["current_scenario"] = cont
        
        elif action_type == "raw_event":
            event = args.get("text")
            if event:
                self.game_state["session"]["events"].append(event)
        
        else:
            self.game_state["session"]["events"].append(f"Unhandled action type: {action_type}")
    
    def _process_npcs(self):
        """Process NPC decisions"""
        if not self.npc_controller:
            return
        
        decisions = []
        try:
            decisions = self.npc_controller.decide(self.game_state)
        except Exception as e:
            self.game_state["session"]["events"].append(f"NPC controller error: {e}")
        
        for decision in decisions:
            self._process_player_action(decision)
    
    def _should_generate_scene(self) -> bool:
        """Check if a new scene should be generated"""
        if not self.game_state.get("current_scenario"):
            return True
        
        recent_events = self.game_state["session"].get("events", [])[-4:]
        return any("chose" in e.lower() or "new scene requested" in e.lower() 
                  for e in recent_events)
    
    def tick(self):
        """Process one game engine tick"""
        with self.lock:
            # Process action queue FIFO
            while self.game_state.get("action_queue"):
                action = self.game_state["action_queue"].pop(0)
                try:
                    self._process_player_action(action)
                except Exception as e:
                    self.game_state["session"]["events"].append(f"Error processing action: {e}")
            
            # NPCs
            self._process_npcs()
            
            # Scenario generation
            if self.scenario_generator and self._should_generate_scene():
                try:
                    scene_json, options_text = self.scenario_generator.generate(self.game_state)
                    self.game_state["scene_history"].append(scene_json)
                    self.game_state["current_scenario"] = scene_json
                    self.game_state["current_options"] = options_text
                    self.game_state["session"]["events"].append("New scene generated")
                except Exception as e:
                    self.game_state["session"]["events"].append(f"Scenario generation error: {e}")
            
            # Persist
            if self.persister:
                try:
                    self.persister.save(self.game_state)
                except Exception:
                    pass
    
    def start(self):
        """Start the game engine loop"""
        self.running = True
        def loop():
            while self.running:
                self.tick()
                time.sleep(self.tick_seconds)
        thread = threading.Thread(target=loop, daemon=True)
        thread.start()
    
    def stop(self):
        """Stop the game engine loop"""
        self.running = False