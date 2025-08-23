"""
Enhanced Orchestrator Package
Includes Stage 3 components plus Haystack pipeline integration
"""

from .simple_orchestrator import (
    SimpleOrchestrator,
    GameRequest, 
    GameResponse,
    create_orchestrator,
    create_stage2_orchestrator,
    create_stage3_orchestrator,
    create_house_rules_orchestrator,
    create_beginner_orchestrator
)

from .saga_manager import SagaManager, create_saga_manager
from .decision_logger import DecisionLogger, create_decision_logger
from .context_broker import ContextBroker, create_context_broker

from .pipeline_integration import (
    PipelineOrchestrator,
    create_pipeline_orchestrator,
    create_full_haystack_orchestrator,
    create_backward_compatible_orchestrator
)

__all__ = [
    # Core orchestrator components
    "SimpleOrchestrator",
    "GameRequest", 
    "GameResponse",
    
    # Stage 3 components
    "SagaManager",
    "DecisionLogger", 
    "ContextBroker",
    
    # Pipeline integration
    "PipelineOrchestrator",
    
    # Factory functions
    "create_orchestrator",
    "create_stage2_orchestrator", 
    "create_stage3_orchestrator",
    "create_house_rules_orchestrator",
    "create_beginner_orchestrator",
    "create_saga_manager",
    "create_decision_logger",
    "create_context_broker",
    "create_pipeline_orchestrator",
    "create_full_haystack_orchestrator",
    "create_backward_compatible_orchestrator"
]