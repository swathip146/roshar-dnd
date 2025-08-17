"""
Scenario Choice Haystack Pipeline  
End-to-end scenario choice → skill check → consequence pipeline
"""

from typing import Dict, Any, Optional
from haystack import Pipeline
from haystack.components.routers import ConditionalRouter
from haystack.components.joiners import BranchJoiner

# Import pipeline and components
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from core.haystack_components.command_envelope_input import CommandEnvelopeInput
from core.haystack_components.scenario_choice_components import (
    ScenarioValidatorComponent,
    RAGContextRetrieverComponent, 
    ScenarioGeneratorComponent,
    ScenarioStateUpdaterComponent
)
from core.haystack_pipelines.skill_check_pipeline import create_skill_check_pipeline


def create_scenario_choice_pipeline(agent_orchestrator) -> Pipeline:
    """
    Create scenario choice pipeline using Haystack components
    
    This pipeline implements the complete orchestrated workflow:
    1. CommandEnvelope Input → Extract scenario choice
    2. Scenario Validator → Check if skill check is needed  
    3. Conditional Router → Route based on skill check requirement
    4. If skill check needed:
       a. Embed skill check pipeline as sub-pipeline
       b. RAG Context Retriever → Get relevant D&D knowledge
       c. Scenario Generator → Generate consequence with skill result + RAG
    5. If no skill check needed:
       a. RAG Context Retriever → Get relevant D&D knowledge  
       b. Scenario Generator → Generate direct consequence + RAG
    6. Scenario State Updater → Update game state
    7. Join results from both paths
    
    Args:
        agent_orchestrator: The AgentOrchestrator instance for agent communication
        
    Returns:
        Pipeline: Configured Haystack pipeline for scenario choices
    """
    
    # Initialize components
    command_input = CommandEnvelopeInput()
    scenario_validator = ScenarioValidatorComponent(agent_orchestrator)
    rag_retriever = RAGContextRetrieverComponent(agent_orchestrator)
    scenario_generator = ScenarioGeneratorComponent(agent_orchestrator)
    state_updater = ScenarioStateUpdaterComponent(agent_orchestrator)
    
    # Create skill check sub-pipeline for when needed
    skill_check_subpipeline = create_skill_check_pipeline(agent_orchestrator)
    
    # Conditional router for skill check requirement
    choice_router = ConditionalRouter(routes=[
        {
            "condition": "{{requires_skill_check}} == True",
            "output": "{{choice_info}}",
            "output_name": "skill_check_required",
            "output_type": Dict[str, Any],
        },
        {
            "condition": "{{requires_skill_check}} == False",
            "output": "{{choice_info}}",
            "output_name": "direct_consequence", 
            "output_type": Dict[str, Any],
        }
    ])
    
    # Result joiners
    skill_result_joiner = BranchJoiner(Dict[str, Any])
    final_result_joiner = BranchJoiner(Dict[str, Any])
    
    # Build pipeline
    pipeline = Pipeline()
    
    # Add components to pipeline
    pipeline.add_component("command_input", command_input)
    pipeline.add_component("scenario_validator", scenario_validator)
    pipeline.add_component("choice_router", choice_router)
    pipeline.add_component("skill_check_pipeline", skill_check_subpipeline)
    pipeline.add_component("rag_retriever_skill", rag_retriever)
    pipeline.add_component("rag_retriever_direct", RAGContextRetrieverComponent(agent_orchestrator))
    pipeline.add_component("scenario_generator_skill", scenario_generator)
    pipeline.add_component("scenario_generator_direct", ScenarioGeneratorComponent(agent_orchestrator))
    pipeline.add_component("state_updater", state_updater)
    pipeline.add_component("skill_result_joiner", skill_result_joiner)
    pipeline.add_component("final_result_joiner", final_result_joiner)
    
    # Connect components - Input to Validator
    pipeline.connect("command_input.correlation_id", "scenario_validator.correlation_id")
    pipeline.connect("command_input.entities", "scenario_validator.entities")
    pipeline.connect("command_input.context", "scenario_validator.context")
    
    # Validator to Router
    pipeline.connect("scenario_validator.requires_skill_check", "choice_router.requires_skill_check")
    pipeline.connect("scenario_validator.choice_info", "choice_router.choice_info")
    
    # Skill check required path
    pipeline.connect("choice_router.skill_check_required", "skill_check_pipeline.entities")
    pipeline.connect("command_input.correlation_id", "skill_check_pipeline.correlation_id")
    pipeline.connect("command_input.actor", "skill_check_pipeline.actor")
    pipeline.connect("command_input.intent", "skill_check_pipeline.intent")
    pipeline.connect("command_input.utterance", "skill_check_pipeline.utterance")
    pipeline.connect("command_input.context", "skill_check_pipeline.context")
    pipeline.connect("command_input.parameters", "skill_check_pipeline.parameters")
    pipeline.connect("command_input.metadata", "skill_check_pipeline.metadata")
    
    # Skill check result to RAG retriever
    pipeline.connect("skill_check_pipeline.applied_result", "skill_result_joiner.value")
    pipeline.connect("command_input.correlation_id", "rag_retriever_skill.correlation_id")
    pipeline.connect("scenario_validator.choice_info", "rag_retriever_skill.choice_info")
    pipeline.connect("command_input.utterance", "rag_retriever_skill.utterance")
    
    # RAG to Scenario Generator (skill path)
    pipeline.connect("rag_retriever_skill.rag_context", "scenario_generator_skill.rag_context")
    pipeline.connect("scenario_validator.choice_info", "scenario_generator_skill.choice_info")
    pipeline.connect("skill_result_joiner.value", "scenario_generator_skill.skill_check_result")
    pipeline.connect("command_input.correlation_id", "scenario_generator_skill.correlation_id")
    
    # Direct consequence path (no skill check)
    pipeline.connect("choice_router.direct_consequence", "rag_retriever_direct.choice_info")
    pipeline.connect("command_input.correlation_id", "rag_retriever_direct.correlation_id")
    pipeline.connect("command_input.utterance", "rag_retriever_direct.utterance")
    
    # RAG to Scenario Generator (direct path)  
    pipeline.connect("rag_retriever_direct.rag_context", "scenario_generator_direct.rag_context")
    pipeline.connect("choice_router.direct_consequence", "scenario_generator_direct.choice_info")
    pipeline.connect("command_input.correlation_id", "scenario_generator_direct.correlation_id")
    
    # Join scenario results from both paths
    pipeline.connect("scenario_generator_skill.scenario_result", "final_result_joiner.value")
    pipeline.connect("scenario_generator_direct.scenario_result", "final_result_joiner.value")
    
    # Final state update
    pipeline.connect("final_result_joiner.value", "state_updater.scenario_result")
    pipeline.connect("command_input.correlation_id", "state_updater.correlation_id")
    pipeline.connect("command_input.actor", "state_updater.actor")
    
    return pipeline


def test_scenario_choice_pipeline(agent_orchestrator, verbose: bool = False):
    """
    Test the scenario choice pipeline with sample inputs
    
    Args:
        agent_orchestrator: The AgentOrchestrator instance
        verbose: Whether to print detailed test output
        
    Returns:
        Dict containing test results
    """
    try:
        # Create the pipeline
        pipeline = create_scenario_choice_pipeline(agent_orchestrator)
        
        if verbose:
            print("🧪 Testing Scenario Choice Pipeline")
        
        # Test case 1: Choice that requires skill check
        skill_check_inputs = {
            "command_envelope": None,
            "correlation_id": "test_scenario_skill_123",
            "actor": {"name": "test_adventurer"},
            "intent": "SCENARIO_CHOICE",
            "entities": {"choice": 1, "skill": "athletics"},
            "utterance": "I choose to climb the cliff (option 1)",
            "context": {
                "current_scenario": {
                    "options": [
                        "Climb the cliff (Athletics DC 15)",
                        "Go around the long way",
                        "Look for another path"
                    ]
                }
            },
            "parameters": {},
            "metadata": {"test": "skill_check_required"}
        }
        
        # Test case 2: Choice that doesn't require skill check
        direct_inputs = {
            "command_envelope": None,
            "correlation_id": "test_scenario_direct_456", 
            "actor": {"name": "test_adventurer"},
            "intent": "SCENARIO_CHOICE",
            "entities": {"choice": 2},
            "utterance": "I choose to go around the long way (option 2)",
            "context": {
                "current_scenario": {
                    "options": [
                        "Climb the cliff (Athletics DC 15)",
                        "Go around the long way", 
                        "Look for another path"
                    ]
                }
            },
            "parameters": {},
            "metadata": {"test": "direct_consequence"}
        }
        
        test_results = {}
        
        # Run both test cases
        for test_name, test_inputs in [("skill_check_required", skill_check_inputs), ("direct_consequence", direct_inputs)]:
            try:
                if verbose:
                    print(f"📝 Running test: {test_name}")
                
                result = pipeline.run(test_inputs)
                
                test_results[test_name] = {
                    "success": True,
                    "result": result,
                    "inputs": test_inputs
                }
                
                if verbose:
                    print(f"✅ Test {test_name} completed successfully")
                    
            except Exception as e:
                test_results[test_name] = {
                    "success": False,
                    "error": str(e),
                    "inputs": test_inputs
                }
                
                if verbose:
                    print(f"❌ Test {test_name} failed: {e}")
        
        # Overall results
        successful_tests = sum(1 for result in test_results.values() if result["success"])
        total_tests = len(test_results)
        
        return {
            "success": successful_tests == total_tests,
            "test_results": test_results,
            "successful_tests": successful_tests,
            "total_tests": total_tests,
            "pipeline_components": len(pipeline.graph.nodes) if hasattr(pipeline, 'graph') else 0,
            "pipeline_connections": len(pipeline.graph.edges) if hasattr(pipeline, 'graph') else 0
        }
        
    except Exception as e:
        if verbose:
            print(f"❌ Pipeline test setup failed: {e}")
        
        return {
            "success": False,
            "error": str(e),
            "test_results": {},
            "successful_tests": 0,
            "total_tests": 0,
            "pipeline_components": 0,
            "pipeline_connections": 0
        }


def get_scenario_choice_pipeline_info() -> Dict[str, Any]:
    """
    Get information about the scenario choice pipeline structure
    
    Returns:
        Dict containing pipeline metadata
    """
    return {
        "name": "Scenario Choice Pipeline",
        "description": "Complete D&D scenario choice processing with embedded skill checks and RAG enhancement",
        "components": [
            "CommandEnvelopeInput",
            "ScenarioValidatorComponent",
            "ConditionalRouter", 
            "SkillCheckSubPipeline",
            "RAGContextRetrieverComponent (x2)",
            "ScenarioGeneratorComponent (x2)",
            "ScenarioStateUpdaterComponent",
            "BranchJoiner (x2)"
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
            "updated_state (final game state)",
            "scenario_result (consequence details)"
        ],
        "features": [
            "Conditional skill check routing",
            "Embedded skill check sub-pipeline", 
            "RAG-enhanced consequence generation",
            "Dual-path processing (skill vs direct)",
            "Game state integration",
            "D&D lore integration",
            "Error handling and fallbacks"
        ],
        "workflow": [
            "1. Validate scenario choice",
            "2. Route based on skill check requirement",
            "3a. Execute skill check pipeline (if needed)",
            "3b. Direct to consequence generation (if not needed)",
            "4. Retrieve relevant D&D context via RAG",
            "5. Generate consequence with full context",
            "6. Update game state",
            "7. Return final result"
        ]
    }