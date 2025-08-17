"""
Shared Messaging Components
Provides message types and classes that can be imported by any module without circular dependencies
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import time


class MessageType(Enum):
    """Types of messages that can be sent between agents"""
    REQUEST = "request"
    RESPONSE = "response"
    EVENT = "event"
    BROADCAST = "broadcast"
    ERROR = "error"


@dataclass
class AgentMessage:
    """Message passed between agents"""
    id: str
    sender_id: str
    receiver_id: str
    message_type: MessageType
    action: str
    data: Dict[str, Any]
    timestamp: float
    response_to: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary"""
        return {
            "id": self.id,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "message_type": self.message_type.value,
            "action": self.action,
            "data": self.data,
            "timestamp": self.timestamp,
            "response_to": self.response_to
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentMessage':
        """Create message from dictionary"""
        return cls(
            id=data["id"],
            sender_id=data["sender_id"],
            receiver_id=data["receiver_id"],
            message_type=MessageType(data["message_type"]),
            action=data["action"],
            data=data["data"],
            timestamp=data["timestamp"],
            response_to=data.get("response_to")
        )