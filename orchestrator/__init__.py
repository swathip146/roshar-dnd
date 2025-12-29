"""
Enhanced Orchestrator Package
Includes Stage 3 components plus Haystack pipeline integration
"""

from .pipeline_integration import (
    PipelineOrchestrator,
    create_full_haystack_orchestrator
)

create_orchestrator = create_full_haystack_orchestrator
create_stage3_orchestrator = create_full_haystack_orchestrator
create_house_rules_orchestrator = create_full_haystack_orchestrator
create_beginner_orchestrator = create_full_haystack_orchestrator

# Legacy function for stage2 compatibility
def create_stage2_orchestrator():
    """Create Stage 2 compatible orchestrator (backward compatibility)"""
    return PipelineOrchestrator(enable_stage3=False, enable_pipelines=False)

from .pipeline_integration import (
    PipelineOrchestrator,
    create_full_haystack_orchestrator
)

__all__ = [
    
    # Pipeline integration
    "PipelineOrchestrator",
    
    # Factory functions
    "create_orchestrator",
    "create_stage2_orchestrator", 
    "create_stage3_orchestrator",
    "create_house_rules_orchestrator",
    "create_beginner_orchestrator",
    "create_pipeline_orchestrator",
    "create_full_haystack_orchestrator",
    "create_backward_compatible_orchestrator"
]