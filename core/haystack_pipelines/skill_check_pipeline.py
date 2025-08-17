"""
Skill Check Haystack Pipeline
Deterministic skill check pipeline using Haystack components
"""

from typing import Dict, Any, Optional
from haystack import Pipeline
from haystack.components.routers import ConditionalRouter
from haystack.components.joiners import BranchJoiner

# Import our custom components
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from core.haystack_components.command_envelope_input import CommandEnvelopeInput
from core.haystack_components.skill_check_components import (
    RuleEnforcementComponent,
    GameEngineComponent,
    DiceSystemComponent,
    FinalResultComponent,
    StateApplierComponent
)


def create_skill_check_pipeline(agent_orchestrator) -> Pipeline:
    """
    Create deterministic skill check pipeline using Haystack components
    
    This pipeline implements the skill check workflow:
    1. CommandEnvelope Input -> Extract parameters
    2. Rule Enforcement -> Validate if check is needed
    3. Conditional Router -> Route based on whether check is required
    4. If check needed:
       a. Game Engine -> Get character data (modifiers, conditions)
       b. Dice System -> Roll dice with advantage/disadvantage
       c. Final Calculator -> Combine roll + modifiers vs DC
       d. State Applier -> Apply result to game state
    5. Join results from both paths
    
    Args:
        agent_orchestrator: The AgentOrchestrator instance for agent communication
        
    Returns:
        Pipeline: Configured Haystack pipeline for skill checks
    """
    
    # Initialize components
    command_input = CommandEnvelopeInput()
    rule_enforcement = RuleEnforcementComponent(agent_orchestrator)
    game_engine = GameEngineComponent(agent_orchestrator)
    dice_system = DiceSystemComponent(agent_orchestrator)
    final_calculator = FinalResultComponent(agent_orchestrator)
    state_applier = StateApplierComponent(agent_orchestrator)
    
    # Conditional router for skill check requirement
    skill_check_router = ConditionalRouter(routes=[
        {
            "condition": "{{requires_check}} == True",
            "output": "{{validation_result}}",
            "output_name": "requires_check",
            "output_type": Dict[str, Any],
        },
        {
            "condition": "{{requires_check}} == False", 
            "output": "{{validation_result}}",
            "output_name": "no_check_needed",
            "output_type": Dict[str, Any],
        }
    ])
    
    # Result joiner to combine both paths
    result_joiner = BranchJoiner(Dict[str, Any])
    
    # Build pipeline
    pipeline = Pipeline()
    
    # Add components to pipeline
    pipeline.add_component("command_input", command_input)
    pipeline.add_component("rule_enforcement", rule_enforcement)
    pipeline.add_component("skill_check_router", skill_check_router)
    pipeline.add_component("game_engine", game_engine)
    pipeline.add_component("dice_system", dice_system)
    pipeline.add_component("final_calculator", final_calculator)
    pipeline.add_component("state_applier", state_applier)
    pipeline.add_component("result_joiner", result_joiner)
    
    # Connect components - Input to Rule Enforcement
    pipeline.connect("command_input.correlation_id", "rule_enforcement.correlation_id")
    pipeline.connect("command_input.entities", "rule_enforcement.entities")
    pipeline.connect("command_input.utterance", "rule_enforcement.utterance")
    
    # Rule Enforcement to Router
    pipeline.connect("rule_enforcement.requires_check", "skill_check_router.requires_check")
    pipeline.connect("rule_enforcement.validation_result", "skill_check_router.validation_result")
    
    # Skill check required path
    pipeline.connect("skill_check_router.requires_check", "game_engine.correlation_id") 
    pipeline.connect("command_input.actor", "game_engine.actor")
    
    # Game Engine to Dice System
    pipeline.connect("game_engine.advantage", "dice_system.advantage")
    pipeline.connect("game_engine.disadvantage", "dice_system.disadvantage")
    pipeline.connect("command_input.correlation_id", "dice_system.correlation_id")
    
    # Dice System and Game Engine to Final Calculator
    pipeline.connect("dice_system.total", "final_calculator.roll_total")
    pipeline.connect("game_engine.modifiers", "final_calculator.modifiers")
    pipeline.connect("rule_enforcement.skill", "final_calculator.skill")
    pipeline.connect("rule_enforcement.dc", "final_calculator.dc")
    pipeline.connect("command_input.correlation_id", "final_calculator.correlation_id")
    
    # Final Calculator to State Applier
    pipeline.connect("final_calculator.final_result", "state_applier.final_result")
    pipeline.connect("command_input.correlation_id", "state_applier.correlation_id")
    pipeline.connect("command_input.actor", "state_applier.actor")
    
    # Join both paths at the end
    pipeline.connect("state_applier.applied_result", "result_joiner.value")
    pipeline.connect("skill_check_router.no_check_needed", "result_joiner.value")
    
    return pipeline


def test_skill_check_pipeline(agent_orchestrator, verbose: bool = False):
    """
    Test the skill check pipeline with a sample input
    
    Args:
        agent_orchestrator: The AgentOrchestrator instance
        verbose: Whether to print detailed test output
        
    Returns:
        Dict containing test results
    """
    try:
        # Create the pipeline
        pipeline = create_skill_check_pipeline(agent_orchestrator)
        
        if verbose:
            print("🧪 Testing Skill Check Pipeline")
        
        # Create test inputs
        test_inputs = {
            "command_envelope": None,  # Would be a real CommandEnvelope in practice
            "correlation_id": "test_123",
            "actor": {"name": "test_character"},
            "intent": "SKILL_CHECK",
            "entities": {"skill": "athletics", "dc": 15},
            "utterance": "I want to make an athletics check",
            "context": {},
            "parameters": {},
            "metadata": {"test": True}
        }
        
        # Run the pipeline
        if verbose:
            print(f"📝 Test inputs: {test_inputs}")
        
        result = pipeline.run(test_inputs)
        
        if verbose:
            print(f"✅ Pipeline result: {result}")
        
        return {
            "success": True,
            "result": result,
            "pipeline_components": len(pipeline.graph.nodes),
            "pipeline_connections": len(pipeline.graph.edges)
        }
        
    except Exception as e:
        if verbose:
            print(f"❌ Pipeline test failed: {e}")
        
        return {
            "success": False,
            "error": str(e),
            "pipeline_components": 0,
            "pipeline_connections": 0
        }


def get_skill_check_pipeline_info() -> Dict[str, Any]:
    """
    Get information about the skill check pipeline structure
    
    Returns:
        Dict containing pipeline metadata
    """
    return {
        "name": "Skill Check Pipeline",
        "description": "Deterministic D&D skill check processing with Haystack",
        "components": [
            "CommandEnvelopeInput",
            "RuleEnforcementComponent", 
            "ConditionalRouter",
            "GameEngineComponent",
            "DiceSystemComponent",
            "FinalResultComponent",
            "StateApplierComponent",
            "BranchJoiner"
        ],
        "inputs": [
            "command_envelope",
            "correlation_id", 
            "actor",
            "intent",
            "entities",
            "utterance",
            "context",
            "parameters",
            "metadata"
        ],
        "outputs": [
            "applied_result (skill check path)",
            "no_check_needed (direct path)"
        ],
        "features": [
            "Advantage/Disadvantage handling",
            "Skill modifier calculation",
            "DC comparison",
            "Game state integration",
            "Conditional routing",
            "Error handling"
        ]
    }