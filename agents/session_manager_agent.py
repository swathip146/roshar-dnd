"""
Session Manager Agent
Handles rest mechanics, session tracking, and time-based D&D mechanics
"""
import json
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
from agent_framework import BaseAgent

class SessionManagerAgent(BaseAgent):
    """Agent for managing D&D game sessions, rests, and time tracking"""
    
    def __init__(self, sessions_dir: str = "docs/sessions", verbose: bool = False):
        super().__init__("session_manager", "session_manager")
        self.sessions_dir = sessions_dir
        self.verbose = verbose
        
        # Ensure sessions directory exists
        import os
        os.makedirs(self.sessions_dir, exist_ok=True)
        
        # Session tracking
        self.current_session = None
        self.session_history = []
        self.rest_tracking = {}
        
        # Time tracking
        self.game_time = {
            "day": 1,
            "hour": 8,  # Start at 8 AM
            "minute": 0
        }
        
        # CRITICAL FIX: Setup message handlers
        self._setup_handlers()
        
    def _setup_handlers(self):
        """Setup message handlers for this agent"""
        # Register message handlers
        self.register_handler("start_session", self._handle_start_session)
        self.register_handler("end_session", self._handle_end_session)
        self.register_handler("get_session_info", self._handle_get_session_info)
        self.register_handler("take_short_rest", self._handle_take_short_rest)
        self.register_handler("take_long_rest", self._handle_take_long_rest)
        self.register_handler("check_rest_eligibility", self._handle_check_rest_eligibility)
        self.register_handler("advance_time", self._handle_advance_time)
        self.register_handler("get_game_time", self._handle_get_game_time)
        self.register_handler("set_game_time", self._handle_set_game_time)
        self.register_handler("get_rest_status", self._handle_get_rest_status)
        self.register_handler("add_time", self._handle_add_time)
        self.register_handler("get_session_status", self._handle_get_session_status)
        self.register_handler("take_long_rest", self._handle_take_long_rest)
        self.register_handler("game_state_updated", self._handle_game_state_updated)
    
    def process_tick(self):
        """Process one tick/cycle of the agent's main loop"""
        # Session manager doesn't need active processing
        pass
    
    def handle_message(self, message):
        """Handle message - supports both AgentMessage objects and dict for testing"""
        if isinstance(message, dict):
            # For testing - convert dict to action and data
            action = message.get("action")
            data = message.get("data", {})
            handler = self.message_handlers.get(action)
            if handler:
                return handler(data)
            else:
                return {"success": False, "error": f"Unknown action: {action}"}
        else:
            # Normal AgentMessage handling
            return super().handle_message(message)
    
    def _handle_start_session(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Start a new game session"""
        try:
            session_name = message_data.get("name", f"Session {len(self.session_history) + 1}")
            players = message_data.get("players", [])
            
            if self.current_session:
                return {"success": False, "error": "A session is already active. End current session first."}
            
            self.current_session = {
                "name": session_name,
                "start_time": datetime.now().isoformat(),
                "players": players,
                "events": [],
                "encounters": 0,
                "rests_taken": {"short": 0, "long": 0},
                "game_time_start": self.game_time.copy()
            }
            
            # Initialize rest tracking for players
            for player in players:
                self.rest_tracking[player] = {
                    "last_short_rest": None,
                    "last_long_rest": None,
                    "short_rests_today": 0,
                    "can_short_rest": True,
                    "can_long_rest": True,
                    "hit_dice_used": 0,
                    "spell_slots_used": {}
                }
            
            if self.verbose:
                print(f"✅ Started session: {session_name} with {len(players)} players")
            
            return {
                "success": True,
                "session": self.current_session,
                "message": f"Session '{session_name}' started successfully"
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to start session: {str(e)}"}
    
    def _handle_end_session(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """End the current game session"""
        try:
            if not self.current_session:
                return {"success": False, "error": "No active session to end"}
            
            # Finalize session data
            self.current_session["end_time"] = datetime.now().isoformat()
            self.current_session["duration_minutes"] = self._calculate_session_duration()
            self.current_session["game_time_end"] = self.game_time.copy()
            
            # Add to session history
            self.session_history.append(self.current_session.copy())
            
            session_name = self.current_session["name"]
            self.current_session = None
            
            if self.verbose:
                print(f"✅ Ended session: {session_name}")
            
            return {
                "success": True,
                "message": f"Session '{session_name}' ended successfully",
                "session_summary": self.session_history[-1]
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to end session: {str(e)}"}
    
    def _handle_get_session_info(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get current session information"""
        try:
            if not self.current_session:
                return {"success": False, "error": "No active session"}
            
            session_info = self.current_session.copy()
            session_info["current_duration_minutes"] = self._calculate_session_duration()
            
            return {"success": True, "session": session_info}
            
        except Exception as e:
            return {"success": False, "error": f"Failed to get session info: {str(e)}"}
    
    def _handle_take_short_rest(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle short rest mechanics"""
        try:
            players = message_data.get("players", [])
            if not players:
                return {"success": False, "error": "No players specified for short rest"}
            
            # Check rest eligibility
            ineligible_players = []
            for player in players:
                if player not in self.rest_tracking:
                    self.rest_tracking[player] = self._create_default_rest_tracking()
                
                if not self._can_take_short_rest(player):
                    ineligible_players.append(player)
            
            if ineligible_players:
                return {
                    "success": False, 
                    "error": f"Players not eligible for short rest: {', '.join(ineligible_players)}"
                }
            
            # Process short rest
            rest_results = {}
            for player in players:
                # Track rest
                self.rest_tracking[player]["last_short_rest"] = time.time()
                self.rest_tracking[player]["short_rests_today"] += 1
                
                # Calculate benefits (simplified)
                hit_dice_available = message_data.get("hit_dice", {}).get(player, 1)
                hit_points_recovered = self._roll_hit_dice(hit_dice_available)
                
                rest_results[player] = {
                    "hit_points_recovered": hit_points_recovered,
                    "hit_dice_used": hit_dice_available,
                    "short_rest_abilities_recovered": True
                }
                
                # Track hit dice usage
                self.rest_tracking[player]["hit_dice_used"] += hit_dice_available
            
            # Advance game time by 1 hour
            self._advance_game_time(60)
            
            # Add to session events
            if self.current_session:
                self.current_session["events"].append({
                    "type": "short_rest",
                    "timestamp": datetime.now().isoformat(),
                    "players": players,
                    "game_time": self.game_time.copy()
                })
                self.current_session["rests_taken"]["short"] += 1
            
            if self.verbose:
                print(f"✅ Short rest completed for {len(players)} players")
            
            return {
                "success": True,
                "rest_type": "short",
                "players": players,
                "results": rest_results,
                "game_time_advanced": "1 hour",
                "new_game_time": self.game_time,
                "message": "Short rest completed successfully"
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to take short rest: {str(e)}"}
    
    def _handle_take_long_rest(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle long rest mechanics"""
        try:
            players = message_data.get("players", [])
            if not players:
                return {"success": False, "error": "No players specified for long rest"}
            
            # Check rest eligibility
            ineligible_players = []
            for player in players:
                if player not in self.rest_tracking:
                    self.rest_tracking[player] = self._create_default_rest_tracking()
                
                if not self._can_take_long_rest(player):
                    ineligible_players.append(player)
            
            if ineligible_players:
                return {
                    "success": False, 
                    "error": f"Players not eligible for long rest: {', '.join(ineligible_players)}"
                }
            
            # Process long rest
            rest_results = {}
            for player in players:
                # Track rest
                self.rest_tracking[player]["last_long_rest"] = time.time()
                self.rest_tracking[player]["short_rests_today"] = 0  # Reset short rests
                self.rest_tracking[player]["hit_dice_used"] = 0  # Reset hit dice
                self.rest_tracking[player]["spell_slots_used"] = {}  # Reset spell slots
                
                rest_results[player] = {
                    "hit_points_fully_recovered": True,
                    "spell_slots_recovered": True,
                    "hit_dice_recovered": True,
                    "long_rest_abilities_recovered": True,
                    "exhaustion_levels_removed": 1
                }
            
            # Advance game time by 8 hours
            self._advance_game_time(8 * 60)
            
            # Add to session events
            if self.current_session:
                self.current_session["events"].append({
                    "type": "long_rest",
                    "timestamp": datetime.now().isoformat(),
                    "players": players,
                    "game_time": self.game_time.copy()
                })
                self.current_session["rests_taken"]["long"] += 1
            
            if self.verbose:
                print(f"✅ Long rest completed for {len(players)} players")
            
            return {
                "success": True,
                "rest_type": "long",
                "players": players,
                "results": rest_results,
                "game_time_advanced": "8 hours",
                "new_game_time": self.game_time,
                "message": "Long rest completed successfully"
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to take long rest: {str(e)}"}
    
    def _handle_check_rest_eligibility(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Check if players can take rests"""
        try:
            players = message_data.get("players", [])
            rest_type = message_data.get("rest_type", "both")
            
            eligibility = {}
            for player in players:
                if player not in self.rest_tracking:
                    self.rest_tracking[player] = self._create_default_rest_tracking()
                
                eligibility[player] = {
                    "can_short_rest": self._can_take_short_rest(player),
                    "can_long_rest": self._can_take_long_rest(player),
                    "short_rests_today": self.rest_tracking[player]["short_rests_today"],
                    "time_since_last_short_rest": self._time_since_last_rest(player, "short"),
                    "time_since_last_long_rest": self._time_since_last_rest(player, "long")
                }
            
            return {"success": True, "eligibility": eligibility}
            
        except Exception as e:
            return {"success": False, "error": f"Failed to check rest eligibility: {str(e)}"}
    
    def _handle_advance_time(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Advance game time"""
        try:
            minutes = message_data.get("minutes", 0)
            hours = message_data.get("hours", 0)
            days = message_data.get("days", 0)
            
            total_minutes = minutes + (hours * 60) + (days * 24 * 60)
            
            old_time = self.game_time.copy()
            self._advance_game_time(total_minutes)
            
            return {
                "success": True,
                "old_time": old_time,
                "new_time": self.game_time,
                "minutes_advanced": total_minutes
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to advance time: {str(e)}"}
    
    def _handle_get_game_time(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get current game time"""
        try:
            return {
                "success": True,
                "game_time": self.game_time,
                "formatted_time": self._format_game_time()
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to get game time: {str(e)}"}
    
    def _handle_set_game_time(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Set game time"""
        try:
            day = message_data.get("day", self.game_time["day"])
            hour = message_data.get("hour", self.game_time["hour"])
            minute = message_data.get("minute", self.game_time["minute"])
            
            self.game_time = {"day": day, "hour": hour, "minute": minute}
            
            return {
                "success": True,
                "game_time": self.game_time,
                "formatted_time": self._format_game_time()
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to set game time: {str(e)}"}
    
    def _handle_get_rest_status(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get rest status for all tracked players"""
        try:
            return {"success": True, "rest_tracking": self.rest_tracking}
            
        except Exception as e:
            return {"success": False, "error": f"Failed to get rest status: {str(e)}"}
    
    def _handle_add_time(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add time to the current session"""
        try:
            hours = message_data.get("hours", 0)
            minutes = message_data.get("minutes", 0)
            activity = message_data.get("activity", "unknown")
            
            if not self.current_session:
                return {"success": False, "error": "No active session"}
            
            # Add time to game time
            total_minutes = self.game_time["minute"] + minutes + (hours * 60)
            additional_hours = total_minutes // 60
            self.game_time["minute"] = total_minutes % 60
            self.game_time["hour"] += additional_hours
            
            # Handle day overflow
            if self.game_time["hour"] >= 24:
                additional_days = self.game_time["hour"] // 24
                self.game_time["day"] += additional_days
                self.game_time["hour"] = self.game_time["hour"] % 24
            
            # Update session duration
            session_time = hours + (minutes / 60.0)
            self.current_session["duration"] = self.current_session.get("duration", 0) + session_time
            
            if self.verbose:
                print(f"⏰ Added {hours}h {minutes}m to session ({activity})")
            
            return {
                "success": True,
                "message": f"Added {hours} hours, {minutes} minutes to session",
                "current_time": self.game_time.copy(),
                "activity": activity
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to add time: {str(e)}"}
    
    def _handle_get_session_status(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get current session status"""
        try:
            if not self.current_session:
                return {"success": False, "error": "No active session"}
            
            # Calculate total time in hours
            total_time_hours = self.current_session.get("duration", 0)
            
            session_info = self.current_session.copy()
            session_info["total_time_hours"] = total_time_hours
            
            return {
                "success": True,
                "session": session_info,
                "game_time": self.game_time.copy(),
                "session_count": len(self.session_history)
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to get session status: {str(e)}"}
    
    def _handle_take_long_rest(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle long rest for party members"""
        try:
            party = message_data.get("party", [])
            
            if not party:
                return {"success": False, "error": "Party list is required"}
            
            # Add 8 hours for long rest
            self.game_time["hour"] += 8
            if self.game_time["hour"] >= 24:
                self.game_time["day"] += self.game_time["hour"] // 24
                self.game_time["hour"] = self.game_time["hour"] % 24
            
            # Track rest for each character
            for character in party:
                char_name = character.strip().lower()
                if char_name not in self.rest_tracking:
                    self.rest_tracking[char_name] = {}
                
                self.rest_tracking[char_name]["last_long_rest"] = {
                    "day": self.game_time["day"],
                    "hour": self.game_time["hour"],
                    "benefits": ["full_hp", "spell_slots_restored", "abilities_restored"]
                }
            
            if self.verbose:
                print(f"🛌 Party took a long rest. Time advanced to Day {self.game_time['day']}, Hour {self.game_time['hour']}")
            
            return {
                "success": True,
                "message": f"Party completed long rest",
                "party": party,
                "time_advanced": "8 hours",
                "current_time": self.game_time.copy(),
                "benefits": ["HP restored", "Spell slots restored", "Abilities restored"]
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to process long rest: {str(e)}"}
    
    # Helper methods
    def _create_default_rest_tracking(self) -> Dict[str, Any]:
        """Create default rest tracking data for a player"""
        return {
            "last_short_rest": None,
            "last_long_rest": None,
            "short_rests_today": 0,
            "can_short_rest": True,
            "can_long_rest": True,
            "hit_dice_used": 0,
            "spell_slots_used": {}
        }
    
    def _can_take_short_rest(self, player: str) -> bool:
        """Check if player can take a short rest"""
        tracking = self.rest_tracking.get(player, {})
        
        # Can't take more than one short rest per hour (simplified rule)
        last_short_rest = tracking.get("last_short_rest")
        if last_short_rest and (time.time() - last_short_rest) < 3600:  # 1 hour in seconds
            return False
        
        return True
    
    def _can_take_long_rest(self, player: str) -> bool:
        """Check if player can take a long rest"""
        tracking = self.rest_tracking.get(player, {})
        
        # Can only take one long rest per 24 hours
        last_long_rest = tracking.get("last_long_rest")
        if last_long_rest and (time.time() - last_long_rest) < 86400:  # 24 hours in seconds
            return False
        
        return True
    
    def _time_since_last_rest(self, player: str, rest_type: str) -> Optional[float]:
        """Get time since last rest in hours"""
        tracking = self.rest_tracking.get(player, {})
        last_rest_key = f"last_{rest_type}_rest"
        last_rest = tracking.get(last_rest_key)
        
        if last_rest:
            return (time.time() - last_rest) / 3600  # Convert to hours
        return None
    
    def _roll_hit_dice(self, num_dice: int, die_size: int = 8) -> int:
        """Roll hit dice for healing during short rest"""
        import random
        return sum(random.randint(1, die_size) for _ in range(num_dice))
    
    def _advance_game_time(self, minutes: int):
        """Advance game time by specified minutes"""
        self.game_time["minute"] += minutes
        
        # Handle minute overflow
        if self.game_time["minute"] >= 60:
            hours_to_add = self.game_time["minute"] // 60
            self.game_time["minute"] = self.game_time["minute"] % 60
            self.game_time["hour"] += hours_to_add
        
        # Handle hour overflow
        if self.game_time["hour"] >= 24:
            days_to_add = self.game_time["hour"] // 24
            self.game_time["hour"] = self.game_time["hour"] % 24
            self.game_time["day"] += days_to_add
    
    def _format_game_time(self) -> str:
        """Format game time as readable string"""
        day_suffix = self._get_day_suffix(self.game_time["day"])
        hour = self.game_time["hour"]
        minute = self.game_time["minute"]
        
        # Convert to 12-hour format
        if hour == 0:
            time_str = f"12:{minute:02d} AM"
        elif hour < 12:
            time_str = f"{hour}:{minute:02d} AM"
        elif hour == 12:
            time_str = f"12:{minute:02d} PM"
        else:
            time_str = f"{hour-12}:{minute:02d} PM"
        
        return f"Day {self.game_time['day']}{day_suffix}, {time_str}"
    
    def _get_day_suffix(self, day: int) -> str:
        """Get suffix for day number (1st, 2nd, 3rd, etc.)"""
        if 10 <= day % 100 <= 20:
            return "th"
        else:
            return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    
    def _calculate_session_duration(self) -> int:
        """Calculate current session duration in minutes"""
        if not self.current_session or "start_time" not in self.current_session:
            return 0
        
        start_time = datetime.fromisoformat(self.current_session["start_time"])
        duration = datetime.now() - start_time
        return int(duration.total_seconds() / 60)
    
    def _handle_game_state_updated(self, message):
        """Handle game_state_updated event - no action needed for session manager"""
        # Session manager doesn't need to respond to game state updates
        # This handler exists only to prevent "no handler" error messages
        pass