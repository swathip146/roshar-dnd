"""
Native Haystack orchestrator replacing custom pipeline orchestration.
Uses proper Haystack v2 Pipeline patterns with parallel processing capabilities.
"""

from haystack import Pipeline
from typing import Dict, Any, Optional, List
import time
from datetime import datetime

from pipelines.pipeline_factory import create_native_pipeline, PipelineFactory
from models.pydantic_dtos import (
    HaystackRequestDTO, HaystackResponseDTO, 
    convert_legacy_request_dto, convert_to_legacy_response_dto
)
from components.shared_contract import RequestDTO, GameResponseDTO

class HaystackNativeOrchestrator:
    """
    Native Haystack orchestrator using Pipeline instead of custom orchestration.
    Replaces the existing PipelineOrchestrator with proper Haystack v2 patterns.
    """
    
    def __init__(self,
                 game_engine=None,
                 character_manager=None,
                 policy_engine=None,
                 document_store=None,
                 pipeline_type: str = "phase1",
                 use_adaptive_routing: bool = False):  # DEBUG: For migration script
        """
        Initialize native orchestrator with game components.
        
        Args:
            game_engine: GameEngine instance for authority-based state
            character_manager: CharacterManager instance
            policy_engine: PolicyEngine instance
            document_store: Document store for RAG operations
            pipeline_type: Type of pipeline to create ("phase1", "simplified", etc.)
            use_adaptive_routing: DEBUG parameter for migration script compatibility
        """
        self.game_engine = game_engine
        self.character_manager = character_manager
        self.policy_engine = policy_engine
        self.document_store = document_store
        self.pipeline_type = pipeline_type
        self.use_adaptive_routing = use_adaptive_routing
        
        # Create the native Haystack pipeline
        self.pipeline = self._create_pipeline()
        
        # Performance tracking
        self.request_count = 0
        self.total_processing_time = 0.0
        self.component_timings = {}
        
    def _create_pipeline(self) -> Pipeline:
        """Create the native Haystack pipeline based on configuration"""
        
        return create_native_pipeline(
            pipeline_type=self.pipeline_type,
            game_engine=self.game_engine,
            character_manager=self.character_manager,
            policy_engine=self.policy_engine,
            document_store=self.document_store,
            use_adaptive_routing=self.use_adaptive_routing
        )
    
    def process_request(self, request: RequestDTO) -> GameResponseDTO:
        """
        Process a game request through the native Haystack pipeline.
        
        Args:
            request: Legacy RequestDTO from existing system
            
        Returns:
            GameResponseDTO compatible with existing system
        """
        start_time = time.time()
        
        try:
            # Convert legacy request to Pydantic model
            haystack_request = convert_legacy_request_dto(request)
            
            # Add orchestrator metadata
            haystack_request.pipeline_metadata = {
                "orchestrator_type": "haystack_native",
                "pipeline_type": self.pipeline_type,
                "routing_type": "adaptive_router" if self.use_adaptive_routing else "conditional_router",
                "adaptive_routing": self.use_adaptive_routing,  # DEBUG info
                "request_id": self._generate_request_id(),
                "timestamp": datetime.now().isoformat()
            }
            
            # Run through native Haystack pipeline
            pipeline_input = self._prepare_pipeline_input(haystack_request)
            pipeline_result = self.pipeline.run(pipeline_input)
            
            # Process pipeline output
            haystack_response = self._process_pipeline_output(pipeline_result, haystack_request)
            
            # Convert back to legacy format
            legacy_response = convert_to_legacy_response_dto(haystack_response)
            
            # Update performance metrics
            processing_time = time.time() - start_time
            self._update_metrics(processing_time)
            
            return legacy_response
            
        except Exception as e:
            # Fallback error response
            processing_time = time.time() - start_time
            self._update_metrics(processing_time)
            
            return {
                "scene": f"An error occurred while processing your request: {str(e)}",
                "choices": [{"text": "Continue", "action": "continue"}],
                "success": False
            }
    
    def _prepare_pipeline_input(self, request: HaystackRequestDTO) -> Dict[str, Any]:
        """Prepare input for the Haystack pipeline"""
        
        # Basic pipeline input structure
        pipeline_input = {
            "messages": [{"role": "user", "content": request.player_input}],
            "player_input": request.player_input,
            "intent": request.intent,
            "confidence": request.confidence,
            "flags": request.flags
        }
        
        # Add sanitizer input for data cleaning
        if "data_sanitizer" in self.pipeline.graph.nodes():
            pipeline_input["raw_data"] = request.model_dump()
        
        return pipeline_input
    
    def _process_pipeline_output(self, 
                                pipeline_result: Dict[str, Any], 
                                original_request: HaystackRequestDTO) -> HaystackResponseDTO:
        """Process the output from the Haystack pipeline"""
        
        # Extract scenario data from pipeline output
        scenario_data = self._extract_scenario_data(pipeline_result)
        
        # Create response with metadata
        response = HaystackResponseDTO(
            scene=scenario_data.get("scene", "No scenario generated"),
            choices=scenario_data.get("choices", [{"text": "Continue", "action": "continue"}]),
            success=scenario_data.get("success", True),
            pipeline_metadata={
                "pipeline_components": list(self.pipeline.graph.nodes()),
                "execution_order": self._get_execution_order(pipeline_result),
                "parallel_branches": self._detect_parallel_branches(pipeline_result)
            },
            component_trace=original_request.component_trace,
            processing_time=self.total_processing_time / max(self.request_count, 1)
        )
        
        return response
    
    def _extract_scenario_data(self, pipeline_result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract scenario data from complex pipeline result structure"""
        
        # Try to find scenario data in various possible output locations
        scenario_locations = [
            "scenario_validator",
            "scenario_agent", 
            "validated_scenario",
            "scenario"
        ]
        
        for location in scenario_locations:
            if location in pipeline_result:
                data = pipeline_result[location]
                if isinstance(data, dict) and "scene" in data:
                    return data
        
        # Fallback: look for any dict with required fields
        for key, value in pipeline_result.items():
            if isinstance(value, dict) and "scene" in value:
                return value
        
        # Final fallback
        return {
            "scene": "Pipeline completed successfully but no scenario was generated.",
            "choices": [{"text": "Continue", "action": "continue"}],
            "success": True
        }
    
    #Remove this after initial debug    
    def _get_execution_order(self, pipeline_result: Dict[str, Any]) -> List[str]:
        """Determine the execution order of pipeline components"""
        
        # This is a simplified approach - in reality Haystack provides execution metadata
        executed_components = []
        
        for component_name in self.pipeline.graph.nodes():
            if component_name in pipeline_result:
                executed_components.append(component_name)
        
        return executed_components
    
    #Remove this after initial debug    
    def _detect_parallel_branches(self, pipeline_result: Dict[str, Any]) -> List[str]:
        """Detect which parallel branches were executed"""
        
        parallel_branches = []
        
        # Check for parallel processing results
        if "results_joiner" in pipeline_result:
            joiner_result = pipeline_result["results_joiner"]
            if isinstance(joiner_result, dict):
                if "rag" in joiner_result:
                    parallel_branches.append("rag_branch")
                if "skill_check" in joiner_result:
                    parallel_branches.append("skill_check_branch")
                if "character_context" in joiner_result:
                    parallel_branches.append("character_branch")
        
        return parallel_branches
    
    def _generate_request_id(self) -> str:
        """Generate unique request ID for tracking"""
        return f"native_{int(time.time() * 1000)}_{self.request_count}"
    
    def _update_metrics(self, processing_time: float):
        """Update performance metrics"""
        self.request_count += 1
        self.total_processing_time += processing_time
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get orchestrator performance metrics"""
        
        avg_processing_time = self.total_processing_time / max(self.request_count, 1)
        
        return {
            "orchestrator_type": "haystack_native",
            "pipeline_type": self.pipeline_type,
            "request_count": self.request_count,
            "total_processing_time": self.total_processing_time,
            "average_processing_time": avg_processing_time,
            "pipeline_components": list(self.pipeline.graph.nodes()),
            "component_timings": self.component_timings
        }
    
    def reset_metrics(self):
        """Reset performance metrics"""
        self.request_count = 0
        self.total_processing_time = 0.0
        self.component_timings = {}
    
    def validate_pipeline(self) -> Dict[str, Any]:
        """Validate pipeline configuration and components"""
        
        try:
            # Check pipeline structure
            nodes = list(self.pipeline.graph.nodes())
            edges = list(self.pipeline.graph.edges())
            
            # Validate required components
            required_components = ["interface_agent", "scenario_agent"]
            missing_components = [comp for comp in required_components if comp not in nodes]
            
            # Check for parallel processing capabilities
            has_parallel_processing = "results_joiner" in nodes
            
            validation_result = {
                "valid": len(missing_components) == 0,
                "component_count": len(nodes),
                "connection_count": len(edges),
                "missing_components": missing_components,
                "has_parallel_processing": has_parallel_processing,
                "pipeline_type": self.pipeline_type,
                "routing_type": "conditional_router"
            }
            
            return validation_result
            
        except Exception as e:
            return {
                "valid": False,
                "error": str(e),
                "pipeline_type": self.pipeline_type
            }
    
    def get_pipeline_graph_info(self) -> Dict[str, Any]:
        """Get detailed information about the pipeline graph structure"""
        
        try:
            return {
                "nodes": list(self.pipeline.graph.nodes()),
                "edges": [(edge[0], edge[1]) for edge in self.pipeline.graph.edges()],
                "pipeline_type": self.pipeline_type,
                "component_types": {
                    node: str(type(self.pipeline.get_component(node)))
                    for node in self.pipeline.graph.nodes()
                }
            }
        except Exception as e:
            return {"error": str(e)}

def create_native_haystack_orchestrator(
    game_engine=None,
    character_manager=None,
    policy_engine=None,
    document_store=None,
    pipeline_type: str = "phase1",
    use_adaptive_routing: bool = False  # DEBUG: For migration script
) -> HaystackNativeOrchestrator:
    """
    Factory function to create native Haystack orchestrator.
    Matches existing naming pattern: create_full_haystack_orchestrator()
    
    Args:
        game_engine: GameEngine instance
        character_manager: CharacterManager instance
        policy_engine: PolicyEngine instance
        document_store: Document store instance
        pipeline_type: Type of pipeline to create
        use_adaptive_routing: DEBUG parameter for migration script compatibility
        
    Returns:
        Configured HaystackNativeOrchestrator with ConditionalRouter components
    """
    
    return HaystackNativeOrchestrator(
        game_engine=game_engine,
        character_manager=character_manager,
        policy_engine=policy_engine,
        document_store=document_store,
        pipeline_type=pipeline_type,
        use_adaptive_routing=use_adaptive_routing
    )