"""
Base Agent for D&D Game Agents
Follows Haystack component patterns for consistency
"""

from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseDnDAgent(ABC):
    """Base class for all D&D game agents following Haystack patterns"""
    
    def __init__(self, name: str):
        self.name = name
        self.agent_type = "dnd_agent"
        
    @abstractmethod
    def run(self, **kwargs) -> Dict[str, Any]:
        """Process agent request and return structured response"""
        pass
    
    def get_agent_info(self) -> Dict[str, Any]:
        """Get agent metadata and status"""
        return {
            "name": self.name,
            "type": self.agent_type,
            "class": self.__class__.__name__
        }
    
    def validate_input(self, **kwargs) -> bool:
        """Validate input parameters - override in subclasses"""
        return True
    
    def format_output(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format output with agent metadata"""
        return {
            "agent": self.name,
            "data": data,
            "timestamp": self._get_timestamp()
        }
    
    def _get_timestamp(self) -> float:
        """Get current timestamp"""
        import time
        return time.time()