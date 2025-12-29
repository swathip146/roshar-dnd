"""
Pipeline factory for creating different types of native Haystack pipelines.
Provides a clean factory pattern following existing naming conventions.
"""

from haystack import Pipeline
from typing import Optional, Dict, Any, Literal, List
from .phase1_pipeline import (
    create_phase1_pipeline, 
    create_simplified_pipeline,
    create_rag_only_pipeline,
    create_skill_check_only_pipeline,
    create_debug_pipeline
)

PipelineType = Literal[
    "phase1", "simplified", "rag_only", "skill_check_only", "debug"
]

class PipelineFactory:
    """Factory for creating native Haystack pipelines with consistent patterns"""
    
    def __init__(self, 
                 game_engine=None,
                 character_manager=None,
                 policy_engine=None,
                 document_store=None):
        """
        Initialize factory with game components.
        
        Args:
            game_engine: GameEngine instance for authority-based state
            character_manager: CharacterManager instance
            policy_engine: PolicyEngine instance  
            document_store: Document store for RAG operations
        """
        self.game_engine = game_engine
        self.character_manager = character_manager
        self.policy_engine = policy_engine
        self.document_store = document_store
    
    def create_pipeline(self,
                       pipeline_type: PipelineType = "phase1",
                       use_adaptive_routing: bool = False,  # DEBUG: For migration script
                       **kwargs) -> Pipeline:
        """
        Create a pipeline of the specified type.
        
        Args:
            pipeline_type: Type of pipeline to create
            use_adaptive_routing: DEBUG parameter for migration script compatibility
            **kwargs: Additional arguments passed to pipeline creation
            
        Returns:
            Configured Haystack Pipeline with native ConditionalRouter components
        """
        
        if pipeline_type == "phase1":
            return create_phase1_pipeline(
                game_engine=self.game_engine,
                character_manager=self.character_manager,
                policy_engine=self.policy_engine,
                document_store=self.document_store,
                use_adaptive_routing=use_adaptive_routing,
                **kwargs
            )
        
        elif pipeline_type == "simplified":
            return create_simplified_pipeline(
                game_engine=self.game_engine,
                character_manager=self.character_manager,
                **kwargs
            )
        
        elif pipeline_type == "rag_only":
            if not self.document_store:
                raise ValueError("Document store required for RAG-only pipeline")
            return create_rag_only_pipeline(self.document_store, **kwargs)
        
        elif pipeline_type == "skill_check_only":
            if not self.game_engine:
                raise ValueError("Game engine required for skill check-only pipeline")
            return create_skill_check_only_pipeline(self.game_engine, **kwargs)
        
        elif pipeline_type == "debug":
            return create_debug_pipeline(**kwargs)
        
        else:
            raise ValueError(f"Unknown pipeline type: {pipeline_type}")
    
    def get_available_types(self) -> List[str]:
        """Get list of available pipeline types based on available components"""
        
        available = ["debug", "simplified"]
        
        if self.game_engine and self.character_manager:
            available.append("phase1")
        
        if self.document_store:
            available.append("rag_only")
        
        if self.game_engine:
            available.append("skill_check_only")
        
        return available
    
    def validate_requirements(self, pipeline_type: PipelineType) -> bool:
        """Validate that required components are available for pipeline type"""
        
        requirements = {
            "phase1": ["game_engine", "character_manager"],
            "simplified": [],
            "rag_only": ["document_store"],
            "skill_check_only": ["game_engine"],
            "debug": []
        }
        
        required_components = requirements.get(pipeline_type, [])
        
        for component in required_components:
            if not getattr(self, component):
                return False
        
        return True

def create_native_pipeline(
    pipeline_type: PipelineType = "phase1",
    game_engine=None,
    character_manager=None,
    policy_engine=None,
    document_store=None,
    use_adaptive_routing: bool = False,  # DEBUG: For migration script
    **kwargs
) -> Pipeline:
    """
    Convenience function to create a native pipeline without factory instantiation.
    Matches existing naming pattern: create_full_haystack_orchestrator()
    
    Args:
        pipeline_type: Type of pipeline to create
        game_engine: GameEngine instance
        character_manager: CharacterManager instance
        policy_engine: PolicyEngine instance
        document_store: Document store instance
        use_adaptive_routing: DEBUG parameter for migration script compatibility
        **kwargs: Additional pipeline configuration
        
    Returns:
        Configured native Haystack Pipeline with ConditionalRouter components
    """
    
    factory = PipelineFactory(
        game_engine=game_engine,
        character_manager=character_manager,
        policy_engine=policy_engine,
        document_store=document_store
    )
    
    return factory.create_pipeline(
        pipeline_type=pipeline_type,
        use_adaptive_routing=use_adaptive_routing,
        **kwargs
    )

def get_pipeline_info(pipeline_type: PipelineType) -> Dict[str, Any]:
    """Get information about a specific pipeline type"""
    
    pipeline_info = {
        "phase1": {
            "description": "Full Phase 1 & 2 pipeline with parallel processing",
            "features": [
                "Intent-based routing",
                "Parallel RAG + skill checks", 
                "Pydantic validation",
                "Legacy system adapters"
            ],
            "requirements": ["game_engine", "character_manager"],
            "optional": ["policy_engine", "document_store"],
            "performance": "43% faster parallel processing"
        },
        "simplified": {
            "description": "Basic pipeline for minimal functionality",
            "features": [
                "Interface agent",
                "Scenario generation",
                "Optional game engine"
            ],
            "requirements": [],
            "optional": ["game_engine", "character_manager"],
            "performance": "Lightweight, fast startup"
        },
        "rag_only": {
            "description": "RAG-focused pipeline for document retrieval testing",
            "features": [
                "Document retrieval",
                "RAG agent processing",
                "Scenario enhancement"
            ],
            "requirements": ["document_store"],
            "optional": [],
            "performance": "Optimized for document queries"
        },
        "skill_check_only": {
            "description": "Skill check pipeline for game mechanics testing",
            "features": [
                "7-step skill check pipeline",
                "Rules enforcement", 
                "Game engine integration"
            ],
            "requirements": ["game_engine"],
            "optional": [],
            "performance": "Fast skill resolution"
        },
        "debug": {
            "description": "Minimal pipeline for component debugging",
            "features": [
                "Data sanitization",
                "Validation testing",
                "Component isolation"
            ],
            "requirements": [],
            "optional": [],
            "performance": "Fastest, minimal overhead"
        }
    }
    
    return pipeline_info.get(pipeline_type, {"description": "Unknown pipeline type"})

def list_all_pipeline_types() -> Dict[str, str]:
    """List all available pipeline types with descriptions"""
    
    return {
        pipeline_type: get_pipeline_info(pipeline_type)["description"]
        for pipeline_type in ["phase1", "simplified", "rag_only", "skill_check_only", "debug"]
    }