"""
Haystack Pipeline Registry for D&D Assistant
Central registry for all Haystack-based D&D pipelines
"""

from typing import Dict, Any, Optional, List
from haystack import Pipeline

# Import pipeline creation functions
from .haystack_pipelines.skill_check_pipeline import create_skill_check_pipeline, get_skill_check_pipeline_info
from .haystack_pipelines.scenario_choice_pipeline import create_scenario_choice_pipeline, get_scenario_choice_pipeline_info


class HaystackPipelineRegistry:
    """
    Central registry for all Haystack-based D&D pipelines
    
    This class manages the registration, retrieval, and lifecycle of
    Haystack pipelines used throughout the D&D Assistant system.
    """
    
    def __init__(self, agent_orchestrator, verbose: bool = False):
        """
        Initialize the pipeline registry
        
        Args:
            agent_orchestrator: The AgentOrchestrator instance for agent communication
            verbose: Whether to enable verbose logging
        """
        self.orchestrator = agent_orchestrator
        self.verbose = verbose
        self.pipelines: Dict[str, Pipeline] = {}
        self.pipeline_metadata: Dict[str, Dict[str, Any]] = {}
        self.initialization_errors: Dict[str, str] = {}
        
        # Register default pipelines
        self._register_default_pipelines()
    
    def _register_default_pipelines(self):
        """Register all standard D&D pipelines"""
        
        pipeline_configs = [
            {
                "intent": "SKILL_CHECK",
                "factory": create_skill_check_pipeline,
                "metadata_func": get_skill_check_pipeline_info,
                "description": "Handles D&D skill checks with dice rolling and modifiers"
            },
            {
                "intent": "SCENARIO_CHOICE",
                "factory": create_scenario_choice_pipeline,
                "metadata_func": get_scenario_choice_pipeline_info,
                "description": "Handles scenario choices and consequences with embedded skill checks"
            },
            # Future pipelines will be added here
            # {
            #     "intent": "RULE_QUERY",
            #     "factory": create_rule_query_pipeline,
            #     "metadata_func": get_rule_query_pipeline_info, 
            #     "description": "Queries D&D rules using RAG"
            # },
            # {
            #     "intent": "COMBAT_ACTION",
            #     "factory": create_combat_action_pipeline,
            #     "metadata_func": get_combat_action_pipeline_info,
            #     "description": "Handles combat actions and resolution"
            # },
            # {
            #     "intent": "LORE_LOOKUP",
            #     "factory": create_rag_lookup_pipeline,
            #     "metadata_func": get_rag_lookup_pipeline_info,
            #     "description": "Pure Haystack RAG for lore queries"
            # }
        ]
        
        for config in pipeline_configs:
            try:
                self._register_pipeline_from_config(config)
            except Exception as e:
                error_msg = f"Failed to register {config['intent']} pipeline: {str(e)}"
                self.initialization_errors[config['intent']] = error_msg
                if self.verbose:
                    print(f"⚠️ {error_msg}")
        
        if self.verbose:
            successful_pipelines = len(self.pipelines)
            failed_pipelines = len(self.initialization_errors)
            print(f"✅ Pipeline Registry initialized: {successful_pipelines} successful, {failed_pipelines} failed")
    
    def _register_pipeline_from_config(self, config: Dict[str, Any]):
        """
        Register a pipeline from configuration
        
        Args:
            config: Pipeline configuration dictionary
        """
        intent = config["intent"]
        factory_func = config["factory"]
        metadata_func = config.get("metadata_func")
        description = config.get("description", "No description available")
        
        # Create the pipeline
        pipeline = factory_func(self.orchestrator)
        
        # Register the pipeline
        self.pipelines[intent] = pipeline
        
        # Store metadata
        metadata = {
            "intent": intent,
            "description": description,
            "created_at": self._get_current_timestamp(),
            "factory_function": factory_func.__name__,
            "component_count": len(pipeline.graph.nodes) if hasattr(pipeline, 'graph') else 0,
            "connection_count": len(pipeline.graph.edges) if hasattr(pipeline, 'graph') else 0
        }
        
        # Add detailed metadata if available
        if metadata_func:
            try:
                detailed_metadata = metadata_func()
                metadata.update(detailed_metadata)
            except Exception as e:
                if self.verbose:
                    print(f"⚠️ Could not get detailed metadata for {intent}: {e}")
        
        self.pipeline_metadata[intent] = metadata
        
        if self.verbose:
            print(f"🔧 Registered pipeline for intent: {intent}")
    
    def get_pipeline(self, intent: str) -> Optional[Pipeline]:
        """
        Get pipeline for intent
        
        Args:
            intent: The command intent (e.g., "SKILL_CHECK", "SCENARIO_CHOICE")
            
        Returns:
            Pipeline instance or None if not found
        """
        return self.pipelines.get(intent)
    
    def register_pipeline(self, intent: str, pipeline: Pipeline, metadata: Optional[Dict[str, Any]] = None):
        """
        Register a custom pipeline
        
        Args:
            intent: The command intent this pipeline handles
            pipeline: The Haystack pipeline instance
            metadata: Optional metadata about the pipeline
        """
        self.pipelines[intent] = pipeline
        
        # Store metadata
        pipeline_metadata = {
            "intent": intent,
            "description": metadata.get("description", "Custom pipeline") if metadata else "Custom pipeline",
            "created_at": self._get_current_timestamp(),
            "custom": True,
            "component_count": len(pipeline.graph.nodes) if hasattr(pipeline, 'graph') else 0,
            "connection_count": len(pipeline.graph.edges) if hasattr(pipeline, 'graph') else 0
        }
        
        if metadata:
            pipeline_metadata.update(metadata)
            
        self.pipeline_metadata[intent] = pipeline_metadata
        
        if self.verbose:
            print(f"🔧 Registered custom pipeline for intent: {intent}")
    
    def unregister_pipeline(self, intent: str) -> bool:
        """
        Unregister a pipeline
        
        Args:
            intent: The intent to unregister
            
        Returns:
            True if pipeline was found and removed, False otherwise
        """
        if intent in self.pipelines:
            del self.pipelines[intent]
            if intent in self.pipeline_metadata:
                del self.pipeline_metadata[intent]
            
            if self.verbose:
                print(f"🗑️ Unregistered pipeline for intent: {intent}")
            return True
        
        return False
    
    def get_registered_intents(self) -> List[str]:
        """
        Get list of all registered pipeline intents
        
        Returns:
            List of intent strings
        """
        return list(self.pipelines.keys())
    
    def get_pipeline_info(self, intent: Optional[str] = None) -> Dict[str, Any]:
        """
        Get information about pipelines
        
        Args:
            intent: Specific intent to get info for, or None for all pipelines
            
        Returns:
            Dictionary containing pipeline information
        """
        if intent:
            # Return info for specific pipeline
            if intent not in self.pipelines:
                return {"error": f"Pipeline not found for intent: {intent}"}
            
            return {
                "intent": intent,
                "registered": True,
                "metadata": self.pipeline_metadata.get(intent, {}),
                "pipeline_type": str(type(self.pipelines[intent]).__name__)
            }
        else:
            # Return info for all pipelines
            return {
                "total_pipelines": len(self.pipelines),
                "registered_intents": self.get_registered_intents(),
                "metadata": self.pipeline_metadata.copy(),
                "initialization_errors": self.initialization_errors.copy(),
                "registry_status": "operational" if self.pipelines else "empty"
            }
    
    def test_pipeline(self, intent: str, test_inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Test a specific pipeline
        
        Args:
            intent: The intent of the pipeline to test
            test_inputs: Optional test inputs, will use defaults if not provided
            
        Returns:
            Test results dictionary
        """
        if intent not in self.pipelines:
            return {
                "success": False,
                "error": f"Pipeline not found for intent: {intent}",
                "intent": intent
            }
        
        try:
            pipeline = self.pipelines[intent]
            
            # Use provided inputs or create default test inputs
            if test_inputs is None:
                test_inputs = self._get_default_test_inputs(intent)
            
            if self.verbose:
                print(f"🧪 Testing pipeline for intent: {intent}")
            
            # Run the pipeline
            result = pipeline.run(test_inputs)
            
            return {
                "success": True,
                "intent": intent,
                "test_inputs": test_inputs,
                "result": result,
                "execution_info": {
                    "pipeline_used": True,
                    "component_count": len(pipeline.graph.nodes) if hasattr(pipeline, 'graph') else 0
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "intent": intent,
                "test_inputs": test_inputs or {}
            }
    
    def _get_default_test_inputs(self, intent: str) -> Dict[str, Any]:
        """
        Get default test inputs for a pipeline
        
        Args:
            intent: The pipeline intent
            
        Returns:
            Dictionary of default test inputs
        """
        default_inputs = {
            "command_envelope": None,
            "correlation_id": f"test_{intent.lower()}_{self._get_current_timestamp()}",
            "actor": {"name": "test_character", "type": "player"},
            "intent": intent,
            "context": {"test": True},
            "parameters": {},
            "metadata": {"source": "pipeline_registry_test"}
        }
        
        # Intent-specific defaults
        if intent == "SKILL_CHECK":
            default_inputs.update({
                "entities": {"skill": "athletics", "dc": 15},
                "utterance": "I want to make an athletics check to climb the wall"
            })
        elif intent == "SCENARIO_CHOICE":
            default_inputs.update({
                "entities": {"choice": 1},
                "utterance": "I choose option 1"
            })
        elif intent == "RULE_QUERY":
            default_inputs.update({
                "entities": {"rule_topic": "advantage"},
                "utterance": "How does advantage work in D&D?"
            })
        else:
            # Generic defaults
            default_inputs.update({
                "entities": {},
                "utterance": f"Test command for {intent}"
            })
        
        return default_inputs
    
    def _get_current_timestamp(self) -> float:
        """Get current timestamp"""
        import time
        return time.time()
    
    def get_registry_status(self) -> Dict[str, Any]:
        """
        Get overall registry status
        
        Returns:
            Dictionary containing registry status information
        """
        return {
            "total_pipelines": len(self.pipelines),
            "operational_pipelines": len(self.pipelines),
            "failed_initializations": len(self.initialization_errors),
            "registered_intents": self.get_registered_intents(),
            "initialization_errors": self.initialization_errors.copy(),
            "memory_usage": {
                "pipelines": len(self.pipelines),
                "metadata_entries": len(self.pipeline_metadata)
            },
            "capabilities": {
                "skill_checks": "SKILL_CHECK" in self.pipelines,
                "scenario_choices": "SCENARIO_CHOICE" in self.pipelines,  
                "rule_queries": "RULE_QUERY" in self.pipelines,
                "combat_actions": "COMBAT_ACTION" in self.pipelines,
                "lore_lookups": "LORE_LOOKUP" in self.pipelines
            }
        }