"""
Phase 1 & 2 native Haystack pipeline implementation.
Replaces custom orchestration with native Haystack v2 patterns including:
- ConditionalRouter for intent-based routing
- BranchJoiner for parallel processing 
- Pydantic validation components
- Legacy system adapters
"""

from haystack import Pipeline
from haystack.components.builders import ChatPromptBuilder
from haystack.components.generators.chat import OpenAIChatGenerator
from haystack.components.joiners import BranchJoiner
from typing import Optional, Dict, Any

# Import native Haystack components
from components.haystack_native.parallel_components import (
    IntentBasedRouter, SimpleIntentRouter, GameIntentRouter,
    RAGFlagRouter, SkillCheckFlagRouter, ParallelResultsJoiner,
    AdaptiveRAGRouter, AdaptiveSkillRouter
)
from components.haystack_native.validation_components import (
    PydanticValidator, ScenarioValidator, ParallelResultsValidator, DataSanitizer
)
from components.haystack_native.legacy_adapters import (
    GameEngineAdapter, CharacterManagerAdapter, SkillCheckAdapter, 
    RAGBypassComponent, SkillCheckBypassComponent, PolicyEngineAdapter
)

# Import existing agent factories
from agents.main_interface_agent_fixed import create_fixed_interface_agent
from agents.scenario_generator_agent import create_scenario_generator_agent
from agents.rag_retriever_agent import create_rag_retriever_agent_simplified

# Import Pydantic models
from models.pydantic_dtos import ParallelResults

def create_phase1_pipeline(
    game_engine=None,
    character_manager=None,
    policy_engine=None,
    document_store=None,
    use_adaptive_routing: bool = False  # DEBUG: Can be removed later
) -> Pipeline:
    """
    Create Phase 1 & 2 pipeline with native Haystack patterns.
    
    Args:
        game_engine: Existing GameEngine instance for authority-based state
        character_manager: Existing CharacterManager instance
        policy_engine: Existing PolicyEngine instance
        document_store: Document store for RAG operations
        use_adaptive_routing: DEBUG parameter for migration script compatibility
        
    Returns:
        Configured Haystack Pipeline with native Haystack ConditionalRouter components
    """
    
    pipeline = Pipeline()
    
    # === INPUT PROCESSING ===
    
    # Data sanitization and validation
    pipeline.add_component("data_sanitizer", DataSanitizer())
    
    # Main interface agent (existing, working agent)
    pipeline.add_component("interface_agent", create_fixed_interface_agent())
    
    # Intent-based routing using ConditionalRouter
    if use_adaptive_routing:
        print("🐛 DEBUG: Using adaptive routing components (can be removed later)")
        pipeline.add_component("intent_router", SimpleIntentRouter())
        # Use adaptive routing components for more intelligent decisions
        pipeline.add_component("rag_flag_router", AdaptiveRAGRouter())
        pipeline.add_component("skill_flag_router", AdaptiveSkillRouter())
    else:
        pipeline.add_component("intent_router", SimpleIntentRouter())
        # Use standard ConditionalRouter components
        pipeline.add_component("rag_flag_router", RAGFlagRouter())
        pipeline.add_component("skill_flag_router", SkillCheckFlagRouter())
    
    # Character context (always needed for game state)
    if character_manager:
        pipeline.add_component("character_manager", CharacterManagerAdapter(character_manager))
    
    # RAG Branch Components
    if document_store:
        pipeline.add_component("rag_agent", create_rag_retriever_agent_simplified(chat_generator=None, document_store=document_store))
    pipeline.add_component("rag_bypass", RAGBypassComponent())
    
    # Skill Check Branch Components
    if game_engine:
        pipeline.add_component("skill_check", SkillCheckAdapter(game_engine))
        pipeline.add_component("game_engine", GameEngineAdapter(game_engine))
    pipeline.add_component("skill_bypass", SkillCheckBypassComponent())
    
    # Policy validation (if available)
    if policy_engine:
        pipeline.add_component("policy_validator", PolicyEngineAdapter(policy_engine))
    
    # Join parallel results
    pipeline.add_component("results_joiner", ParallelResultsJoiner())
    pipeline.add_component("results_validator", ParallelResultsValidator())
    
    # === SCENARIO GENERATION (using working pattern) ===
    # Import the working components from the legacy system
    from agents.scenario_generator_agent import PromptBuilderComponent, ScenarioValidatorComponent
    
    pipeline.add_component("prompt_builder", PromptBuilderComponent())
    pipeline.add_component("scenario_agent", create_scenario_generator_agent())
    pipeline.add_component("scenario_validator", ScenarioValidatorComponent())
    
    # === PIPELINE CONNECTIONS ===
    
    # Input processing flow (skip data sanitizer connection for now - direct input to interface agent)
    # pipeline.connect("data_sanitizer.sanitized_data", "interface_agent.messages")
    pipeline.connect("interface_agent.interface_result", "intent_router.interface_result")
    
    # Route to parallel processing for scenario requests
    pipeline.connect("intent_router.scenario_processing", "rag_flag_router.interface_result")
    pipeline.connect("intent_router.scenario_processing", "skill_flag_router.interface_result")
    
    # Character manager connection (if available)
    if character_manager:
        pipeline.connect("intent_router.scenario_processing", "character_manager.request_data")
    
    # Policy validation connection (if available)
    if policy_engine:
        pipeline.connect("intent_router.scenario_processing", "policy_validator.request_data")
    
    # RAG branch connections
    if document_store:
        pipeline.connect("rag_flag_router.rag_needed", "rag_agent")
        pipeline.connect("rag_flag_router.rag_bypass", "rag_bypass.interface_result")
    else:
        # No document store available, always bypass
        pipeline.connect("rag_flag_router.rag_bypass", "rag_bypass.interface_result")
    
    # Skill check branch connections
    if game_engine:
        pipeline.connect("skill_flag_router.skill_needed", "skill_check.skill_request")
        pipeline.connect("skill_flag_router.skill_bypass", "skill_bypass.interface_result")
    else:
        # No game engine available, always bypass
        pipeline.connect("skill_flag_router.skill_bypass", "skill_bypass.interface_result")
    
    # Join all parallel results - each component gets its own input name
    if document_store:
        pipeline.connect("rag_agent.messages", "results_joiner.rag_agent_result")
    pipeline.connect("rag_bypass.rag_result", "results_joiner.rag_bypass_result")
    
    if game_engine:
        pipeline.connect("skill_check.skill_check_result", "results_joiner.skill_check_result")
    pipeline.connect("skill_bypass.skill_result", "results_joiner.skill_bypass_result")
    
    if character_manager:
        pipeline.connect("character_manager.party_context", "results_joiner.character_context")
    
    # Scenario generation using working pattern
    # Connect parallel results through validation then PromptBuilder (like the working legacy system)
    pipeline.connect("results_joiner.parallel_results", "results_validator.data")
    pipeline.connect("results_validator.validated_data", "prompt_builder.dto")
    pipeline.connect("prompt_builder.messages", "scenario_agent.messages")
    pipeline.connect("scenario_agent.messages", "scenario_validator.messages")
    
    return pipeline

# The below methods are for creating different types of simple pipelines for debug
def create_simplified_pipeline(
    game_engine=None,
    character_manager=None
) -> Pipeline:
    """
    Create a simplified pipeline for basic functionality without advanced features.
    Useful for testing or when some components are not available.
    """
    
    pipeline = Pipeline()
    
    # Minimal components
    pipeline.add_component("interface_agent", create_fixed_interface_agent())
    pipeline.add_component("scenario_agent", create_scenario_generator_agent())
    
    # Optional game engine integration
    if game_engine:
        pipeline.add_component("game_engine", GameEngineAdapter(game_engine))
        pipeline.connect("interface_agent.interface_result", "game_engine.request_data")
        pipeline.connect("game_engine.state_context", "scenario_agent.messages")
    else:
        pipeline.connect("interface_agent.interface_result", "scenario_agent.messages")
    
    return pipeline

def create_rag_only_pipeline(document_store) -> Pipeline:
    """Create a pipeline focused only on RAG operations for testing RAG functionality."""
    
    pipeline = Pipeline()
    
    pipeline.add_component("interface_agent", create_fixed_interface_agent())
    pipeline.add_component("rag_agent", create_rag_retriever_agent_simplified(chat_generator=None, document_store=document_store))
    pipeline.add_component("scenario_agent", create_scenario_generator_agent())
    
    pipeline.connect("interface_agent", "rag_agent")
    pipeline.connect("rag_agent", "scenario_agent")
    
    return pipeline

def create_skill_check_only_pipeline(game_engine) -> Pipeline:
    """Create a pipeline focused only on skill check operations for testing game mechanics."""
    
    pipeline = Pipeline()
    
    pipeline.add_component("interface_agent", create_fixed_interface_agent())
    pipeline.add_component("skill_check", SkillCheckAdapter(game_engine))
    pipeline.add_component("scenario_agent", create_scenario_generator_agent())
    
    pipeline.connect("interface_agent", "skill_check")
    pipeline.connect("skill_check", "scenario_agent")
    
    return pipeline

def create_debug_pipeline() -> Pipeline:
    """Create a minimal pipeline for debugging component interactions."""
    
    pipeline = Pipeline()
    
    # Add only sanitizer and validator for debugging
    pipeline.add_component("sanitizer", DataSanitizer())
    pipeline.add_component("validator", ScenarioValidator())
    
    # Simple connection for testing
    pipeline.connect("sanitizer", "validator")
    
    return pipeline