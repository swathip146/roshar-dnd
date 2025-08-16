"""
Base Command Handler for Modular DM Assistant

Abstract base class that defines the interface for command handlers.
This allows for pluggable parsing strategies (manual vs AI-based).
"""

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
        """
        Convenience method to send messages through the DM assistant.
        
        Args:
            agent_id: Target agent identifier
            action: Action to perform
            data: Data payload for the action
            timeout: Timeout in seconds
            
        Returns:
            Optional response data from the agent
        """
        return self.dm_assistant._send_message_and_wait(agent_id, action, data, timeout)
    
    def _check_agent_availability(self, agent_id: str, action: str) -> bool:
        """
        Check if an agent is available and has the required handler.
        
        Args:
            agent_id: Target agent identifier
            action: Action to check for
            
        Returns:
            bool: True if agent is available and has the handler
        """
        return self.dm_assistant._check_agent_availability(agent_id, action)
