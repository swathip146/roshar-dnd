"""
Enhanced Command Infrastructure for Haystack Integration
Provides correlation, security, and traceability for D&D Assistant commands
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum
import uuid
import time
import json


class CommandStatus(Enum):
    """Status of command processing"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class CommandHeader:
    """
    Command header providing correlation, security, and traceability information
    """
    correlation_id: str
    intent: str
    actor: Dict[str, Any]
    timestamp: float
    priority: int = 0
    timeout_seconds: float = 30.0
    retry_count: int = 0
    max_retries: int = 3
    source_system: str = "dnd_assistant"
    trace_id: Optional[str] = None
    
    def __post_init__(self):
        if self.trace_id is None:
            self.trace_id = f"trace_{uuid.uuid4().hex[:8]}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CommandHeader':
        """Create from dictionary"""
        return cls(**data)


@dataclass
class CommandBody:
    """
    Command body containing the actual command data and parameters
    """
    utterance: str
    entities: Dict[str, Any]
    context: Dict[str, Any]
    parameters: Dict[str, Any]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CommandBody':
        """Create from dictionary"""
        return cls(**data)


@dataclass
class CommandEnvelope:
    """
    Command envelope that wraps commands with enhanced infrastructure for
    correlation, security, and traceability in the Haystack-powered D&D Assistant
    """
    header: CommandHeader
    body: CommandBody
    status: CommandStatus = CommandStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    processing_history: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.processing_history is None:
            self.processing_history = []
            self.add_processing_event("created", {"timestamp": time.time()})
    
    def add_processing_event(self, event_type: str, data: Dict[str, Any]):
        """Add an event to the processing history"""
        self.processing_history.append({
            "event_type": event_type,
            "timestamp": time.time(),
            "correlation_id": self.header.correlation_id,
            "data": data
        })
    
    def mark_processing(self):
        """Mark command as being processed"""
        self.status = CommandStatus.PROCESSING
        self.add_processing_event("processing_started", {
            "intent": self.header.intent,
            "actor": self.header.actor.get("name", "unknown")
        })
    
    def mark_completed(self, result: Dict[str, Any]):
        """Mark command as completed with result"""
        self.status = CommandStatus.COMPLETED
        self.result = result
        self.add_processing_event("completed", {
            "result_size": len(str(result)),
            "success": result.get("success", True)
        })
    
    def mark_failed(self, error: str):
        """Mark command as failed with error"""
        self.status = CommandStatus.FAILED
        self.error = error
        self.add_processing_event("failed", {
            "error": error,
            "retry_count": self.header.retry_count
        })
    
    def should_retry(self) -> bool:
        """Check if command should be retried"""
        return (self.status == CommandStatus.FAILED and 
                self.header.retry_count < self.header.max_retries)
    
    def increment_retry(self):
        """Increment retry count"""
        self.header.retry_count += 1
        self.add_processing_event("retry_attempted", {
            "retry_count": self.header.retry_count,
            "max_retries": self.header.max_retries
        })
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "header": self.header.to_dict(),
            "body": self.body.to_dict(),
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "processing_history": self.processing_history
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CommandEnvelope':
        """Create from dictionary"""
        return cls(
            header=CommandHeader.from_dict(data["header"]),
            body=CommandBody.from_dict(data["body"]),
            status=CommandStatus(data["status"]),
            result=data.get("result"),
            error=data.get("error"),
            processing_history=data.get("processing_history", [])
        )
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'CommandEnvelope':
        """Create from JSON string"""
        return cls.from_dict(json.loads(json_str))


def create_command_envelope(
    intent: str,
    utterance: str,
    actor: Dict[str, Any],
    entities: Optional[Dict[str, Any]] = None,
    context: Optional[Dict[str, Any]] = None,
    parameters: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    priority: int = 0,
    timeout_seconds: float = 30.0
) -> CommandEnvelope:
    """
    Factory function to create a CommandEnvelope with proper defaults
    
    Args:
        intent: The command intent (e.g., "SKILL_CHECK", "SCENARIO_CHOICE")
        utterance: The original user input
        actor: Information about who issued the command
        entities: Extracted entities from the command
        context: Additional context information
        parameters: Command parameters
        metadata: Additional metadata
        priority: Command priority (higher = more important)
        timeout_seconds: How long to wait for completion
    
    Returns:
        CommandEnvelope: Fully constructed command envelope
    """
    correlation_id = str(uuid.uuid4())
    
    header = CommandHeader(
        correlation_id=correlation_id,
        intent=intent,
        actor=actor,
        timestamp=time.time(),
        priority=priority,
        timeout_seconds=timeout_seconds
    )
    
    body = CommandBody(
        utterance=utterance,
        entities=entities or {},
        context=context or {},
        parameters=parameters or {},
        metadata=metadata or {}
    )
    
    return CommandEnvelope(header=header, body=body)