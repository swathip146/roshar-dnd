"""
Base Command Handler for Modular DM Assistant

Abstract base class that defines the interface for command handlers.
This allows for pluggable parsing strategies (manual vs AI-based).
"""

import json
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseCommandHandler(ABC):
    """
    Abstract base class for command handlers.
    
    This defines the interface that all command handlers must implement,
    allowing for different parsing strategies while maintaining consistency.
    """
    
    def __init__(self, dm_assistant):
        """
        Initialize the command handler with a reference to the DM assistant.
        
        Args:
            dm_assistant: Reference to the main ModularDMAssistant instance
        """
        self.dm_assistant = dm_assistant
        self.last_command = ""
        self.last_scenario_options = []
    
    @abstractmethod
    def handle_command(self, user_command: str) -> str:
        """
        Process a user command and return the appropriate response.
        
        This is the main entry point for command processing. Different
        implementations can use different strategies (manual mapping,
        AI-based intent detection, etc.).
        
        Args:
            user_command: The raw user input string
            
        Returns:
            str: The response to display to the user
        """
        pass
    
    @abstractmethod
    def get_supported_commands(self) -> Dict[str, str]:
        """
        Get a dictionary of supported commands and their descriptions.
        
        Returns:
            Dict[str, str]: Mapping of command names to descriptions
        """
        pass
    
    def _send_message_and_wait(self, agent_id: str, action: str, data: Dict[str, Any], timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        """Send a message to an agent and wait for response"""
        try:
            # Check cache if enabled
            cache_key = None
            if self.dm_assistant.enable_caching and self.dm_assistant.cache_manager and self._should_cache(agent_id, action, data):
                cache_key = f"{agent_id}_{action}_{json.dumps(data, sort_keys=True)}"
                cached_result = self.dm_assistant.cache_manager.get(cache_key)
                if cached_result:
                    if self.dm_assistant.verbose:
                        print(f"📦 Cache hit for {agent_id}:{action}")
                    return cached_result
            
            # Send message through orchestrator
            message_id = self.dm_assistant.orchestrator.send_message_to_agent(agent_id, action, data)
            if not message_id:
                return {"success": False, "error": "Failed to send message"}
            
            # Wait for response
            start_time = time.time()
            result = None
            
            while time.time() - start_time < timeout:
                try:
                    history = self.dm_assistant.orchestrator.message_bus.get_message_history(limit=50)
                    for msg in reversed(history):
                        if (msg.get("response_to") == message_id and
                            msg.get("message_type") == "response"):
                            result = msg.get("data", {})
                            break
                    
                    if result:
                        break
                    
                except Exception as e:
                    if self.dm_assistant.verbose:
                        print(f"⚠️ Error checking message history: {e}")
                
                time.sleep(0.1)
            
            # Cache result if successful
            if result and cache_key and self.dm_assistant.cache_manager:
                ttl_hours = self._get_cache_ttl(agent_id, action)
                self.dm_assistant.cache_manager.set(cache_key, result, ttl_hours)
            
            return result
            
        except Exception as e:
            if self.dm_assistant.verbose:
                print(f"❌ Error sending message to {agent_id}:{action}: {e}")
            return {"success": False, "error": f"Communication error: {str(e)}"}
    
    def _send_message_and_wait_safe(self, agent_id: str, action: str, data: Dict[str, Any], timeout: float = 5.0) -> Dict[str, Any]:
        """
        Send a message to an agent and wait for response with safety wrapper.
        
        This method wraps _send_message_and_wait() with additional safety checks to handle:
        - None responses from message bus race conditions
        - Data type validation to prevent 'NoneType' object has no attribute 'get' errors
        - Consistent fallback response format
        
        Args:
            agent_id: Target agent identifier
            action: Action/handler name to invoke
            data: Message payload data
            timeout: Maximum wait time for response
            
        Returns:
            Dict[str, Any]: Always returns a valid dictionary with success/error indicators
        """
        try:
            # Call the underlying message sending method
            result = self._send_message_and_wait(agent_id, action, data, timeout)
            
            # Handle None response (message bus race condition)
            if result is None:
                if self.dm_assistant.verbose:
                    print(f"⚠️ Received None response from {agent_id}:{action} - possible message bus race condition")
                return {
                    "success": False,
                    "error": f"No response received from {agent_id}",
                    "timeout": True
                }
            
            # Validate response is a dictionary
            if not isinstance(result, dict):
                if self.dm_assistant.verbose:
                    print(f"⚠️ Received non-dict response from {agent_id}:{action}: {type(result)} - {result}")
                
                # Try to convert string responses to dict
                if isinstance(result, str):
                    try:
                        import json
                        result = json.loads(result)
                    except:
                        # Wrap string response in standard format
                        result = {"success": True, "response": result}
                else:
                    # Wrap other types in error format
                    result = {
                        "success": False,
                        "error": f"Invalid response type from {agent_id}: {type(result)}",
                        "raw_response": str(result)
                    }
            
            # Ensure required fields exist
            if "success" not in result:
                result["success"] = True  # Assume success if not explicitly failed
            
            return result
            
        except Exception as e:
            if self.dm_assistant.verbose:
                print(f"❌ Error in safe message sending to {agent_id}:{action}: {e}")
            return {
                "success": False,
                "error": f"Safe communication error: {str(e)}",
                "agent_id": agent_id,
                "action": action
            }
    
    def _check_agent_availability(self, agent_id: str, action: str) -> bool:
        """Check if agent is registered and has the required handler"""
        try:
            agent_status = self.dm_assistant.orchestrator.get_agent_status()
            if agent_id not in agent_status:
                return False
            
            if not agent_status[agent_id].get("running", False):
                return False
            
            handlers = agent_status[agent_id].get("handlers", [])
            if action not in handlers:
                return False
            
            return True
            
        except Exception as e:
            if self.dm_assistant.verbose:
                print(f"⚠️ Error checking agent availability: {e}")
            return False
    
    def _should_cache(self, agent_id: str, action: str, data: Dict[str, Any]) -> bool:
        """Determine if a query should be cached"""
        # Don't cache dice rolls or random content
        if agent_id == 'dice_system':
            return False
        
        # Don't cache scenario generation (creative content)
        if agent_id == 'haystack_pipeline' and action == 'query_scenario':
            return False
        
        # Don't cache if data contains random/time-sensitive elements
        query_text = json.dumps(data).lower()
        if any(keyword in query_text for keyword in ['roll', 'random', 'dice', 'turn', 'timestamp']):
            return False
        
        return True
    
    def _get_cache_ttl(self, agent_id: str, action: str) -> float:
        """Get cache TTL (time-to-live) in hours for different agent/action combinations"""
        if agent_id == 'rule_enforcement':
            return 24.0  # Rule queries can be cached longer
        elif agent_id == 'campaign_manager':
            return 12.0  # Campaign info can be cached for medium duration
        else:
            return 6.0   # General queries use shorter TTL
    
    def handle_game_state_updated(self, event_data: Dict[str, Any]) -> None:
        """
        Handle game_state_updated events from the message bus.
        
        This method is called when the game state changes, allowing command handlers
        to update their internal state, invalidate caches, or perform other
        synchronization tasks.
        
        Args:
            event_data: Event data containing game_state and timestamp
        """
        if self.dm_assistant.verbose:
            timestamp = event_data.get('timestamp', 'unknown')
            print(f"🔄 Game state updated at {timestamp}")
        
        # Invalidate game state related cache entries if caching is enabled
        if self.dm_assistant.enable_caching and self.dm_assistant.cache_manager:
            # Clear any cached game state queries
            cache_keys_to_remove = []
            cache_stats = self.dm_assistant.cache_manager.get_stats()
            
            for key in cache_stats.get('keys', []):
                # Remove cache entries related to game state, combat status, or scenario context
                if any(term in key.lower() for term in ['game_state', 'combat_status', 'scenario', 'current_scene']):
                    cache_keys_to_remove.append(key)
            
            for key in cache_keys_to_remove:
                self.dm_assistant.cache_manager.remove(key)
                if self.dm_assistant.verbose:
                    print(f"📦 Invalidated cache entry: {key}")
        
        # Update narrative continuity if available
        if hasattr(self.dm_assistant, 'narrative_tracker') and self.dm_assistant.narrative_tracker:
            game_state = event_data.get('game_state', {})
            if 'current_scenario' in game_state:
                self.dm_assistant.narrative_tracker.add_event(
                    event_type='game_state_update',
                    content=game_state.get('current_scenario', ''),
                    metadata={
                        'timestamp': event_data.get('timestamp'),
                        'location': game_state.get('session', {}).get('location', ''),
                        'players': list(game_state.get('players', {}).keys())
                    }
                )
        
        # Allow subclasses to implement custom game state update handling
        self._on_game_state_updated(event_data)
    
    def _on_game_state_updated(self, event_data: Dict[str, Any]) -> None:
        """
        Override this method in subclasses to implement custom game state update handling.
        
        Args:
            event_data: Event data containing game_state and timestamp
        """
        pass
