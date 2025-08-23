"""
Pipeline Integration for Orchestrator
Connects Haystack pipelines with existing orchestrator infrastructure
Enables seamless integration between agents and components
"""

from typing import Dict, Any, Optional, List
import logging
from haystack import Pipeline
from haystack.components.builders.chat_prompt_builder import ChatPromptBuilder
from haystack.dataclasses import ChatMessage

from .simple_orchestrator import SimpleOrchestrator, GameRequest, GameResponse
from .context_broker import ContextBroker
from components.policy import PolicyProfile
from agents.scenario_generator_agent import create_scenario_generator_agent
from agents.rag_retriever_agent import create_rag_retriever_agent
from agents.npc_controller_agent import create_npc_controller_agent
from agents.main_interface_agent import create_main_interface_agent


class PipelineOrchestrator(SimpleOrchestrator):
    """
    Enhanced orchestrator with Haystack pipeline integration
    Extends existing orchestrator while adding pipeline capabilities
    """
    
    def __init__(self, policy_profile=PolicyProfile.RAW, enable_stage3=True, enable_pipelines=True):
        super().__init__(policy_profile, enable_stage3)
        
        self.enable_pipelines = enable_pipelines
        self.logger = logging.getLogger(__name__)
        
        # Initialize pipeline infrastructure
        self.pipelines: Dict[str, Pipeline] = {}
        self.agents: Dict[str, Any] = {}
        self.context_broker: Optional[ContextBroker] = None
        
        if enable_pipelines:
            self._initialize_pipeline_infrastructure()
            self._register_pipeline_handlers()
            
        print(f"🔄 Pipeline Orchestrator initialized (pipelines: {'enabled' if enable_pipelines else 'disabled'})")
    
    def _initialize_pipeline_infrastructure(self):
        """Initialize Haystack agents and context broker"""
        
        try:
            # Initialize context broker
            self.context_broker = ContextBroker()
            
            # Initialize agents
            self.agents = {
                "scenario_generator": create_scenario_generator_agent(),
                "rag_retriever": create_rag_retriever_agent(),
                "npc_controller": create_npc_controller_agent(),
                "main_interface": create_main_interface_agent()
            }
            
            # Initialize pipelines
            self._create_pipelines()
            
            self.logger.info("Pipeline infrastructure initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize pipeline infrastructure: {e}")
            self.enable_pipelines = False
            # Still register basic handlers even if pipelines fail
            self._register_fallback_handlers()
    
    def _create_pipelines(self):
        """Create Haystack pipelines for different request types"""
        
        # Scenario Generation Pipeline
        scenario_pipeline = Pipeline()
        scenario_pipeline.add_component("rag_retriever", self.agents["rag_retriever"])
        scenario_pipeline.add_component("scenario_generator", self.agents["scenario_generator"])
        scenario_pipeline.add_component("prompt_builder", ChatPromptBuilder(
            template=[ChatMessage.from_user("""
            Player Action: {{ player_action }}
            Game Context: {{ game_context }}
            RAG Context: {{ rag_context }}
            
            Generate a D&D scenario response following the contract specification.
            """)],
            required_variables=["player_action", "game_context"]
        ))
        
        # Connect pipeline components (specify output connections)
        scenario_pipeline.connect("rag_retriever.last_message", "prompt_builder.rag_context")
        scenario_pipeline.connect("prompt_builder", "scenario_generator")
        
        self.pipelines["scenario_generation"] = scenario_pipeline
        
        # NPC Interaction Pipeline
        npc_pipeline = Pipeline()
        npc_pipeline.add_component("npc_controller", self.agents["npc_controller"])
        npc_pipeline.add_component("prompt_builder", ChatPromptBuilder(
            template=[ChatMessage.from_user("""
            NPC: {{ npc_id }}
            Player Action: {{ player_action }}
            NPC Context: {{ npc_context }}
            
            Generate appropriate NPC response including dialogue and behavior.
            """)],
            required_variables=["npc_id", "player_action", "npc_context"]
        ))
        
        npc_pipeline.connect("prompt_builder", "npc_controller")
        self.pipelines["npc_interaction"] = npc_pipeline
        
        # Interface Processing Pipeline
        interface_pipeline = Pipeline()
        interface_pipeline.add_component("interface_agent", self.agents["main_interface"])
        interface_pipeline.add_component("prompt_builder", ChatPromptBuilder(
            template=[ChatMessage.from_user("""
            Player Input: {{ player_input }}
            Game Context: {{ game_context }}
            
            Parse this input and determine how it should be processed.
            """)],
            required_variables=["player_input", "game_context"]
        ))
        
        interface_pipeline.connect("prompt_builder", "interface_agent")
        self.pipelines["interface_processing"] = interface_pipeline
        
        self.logger.info(f"Created {len(self.pipelines)} Haystack pipelines")
    
    def _register_pipeline_handlers(self):
        """Register pipeline-specific request handlers"""
        
        if not self.enable_pipelines:
            return
            
        # Add pipeline handlers to existing handlers
        pipeline_handlers = {
            'gameplay_turn': self._handle_gameplay_turn_pipeline,
            'scenario_generation': self._handle_scenario_pipeline,
            'npc_interaction': self._handle_npc_pipeline,
            'interface_processing': self._handle_interface_pipeline,
            'rag_query': self._handle_rag_pipeline
        }
        
        # Register handlers with base orchestrator
        for handler_type, handler_func in pipeline_handlers.items():
            self.register_handler(handler_type, handler_func)
        self.logger.info(f"Registered {len(pipeline_handlers)} pipeline handlers")
    
    def process_request(self, request) -> GameResponse:
        """
        Enhanced request processing with pipeline integration
        Maintains backward compatibility while adding pipeline capabilities
        """
        
        try:
            # Defensive programming - handle None request
            if request is None:
                self.logger.error("Received None request in pipeline orchestrator")
                return GameResponse(
                    success=False,
                    data={"error": "None request received"},
                    correlation_id=None
                )
            
            # Convert to standard format
            if isinstance(request, GameRequest):
                request_dict = {
                    "type": request.request_type,
                    "request_type": request.request_type,
                    "data": request.data,
                    "context": request.context,
                    "correlation_id": request.correlation_id,
                    "saga_id": request.saga_id
                }
            else:
                request_dict = request.copy() if request is not None else {}
            
            # Context enrichment if pipelines are enabled
            if self.enable_pipelines and self.context_broker and request_dict is not None:
                enriched_request_dict = self.context_broker.enrich_context(request_dict)
                # Only update if enrichment was successful
                if enriched_request_dict is not None:
                    request_dict = enriched_request_dict
            
            # Determine processing path
            if self._should_use_pipeline(request_dict):
                return self._process_with_pipeline(request_dict)
            else:
                # Use existing orchestrator processing
                return super().process_request(request)
                
        except Exception as e:
            self.logger.error(f"Pipeline orchestrator error: {e}")
            # Fallback to base orchestrator
            return super().process_request(request)
    
    def _should_use_pipeline(self, request: Dict[str, Any]) -> bool:
        """Determine if request should use pipeline processing"""
        
        if not self.enable_pipelines or request is None:
            return False
            
        request_type = request.get("type", request.get("request_type", ""))
        
        # Pipeline-enabled request types
        pipeline_types = [
            "gameplay_turn",
            "scenario_generation", 
            "npc_interaction",
            "interface_processing",
            "rag_query"
        ]
        
        # Check if request explicitly requests pipeline
        if request.get("use_pipeline", False):
            return True
            
        # Check request complexity
        complexity_indicators = [
            request.get("rag_context"),
            len(str(request.get("data", {}))) > 100,
            request.get("context", {}).get("complex", False) if request.get("context") is not None else False
        ]
        
        return request_type in pipeline_types or any(complexity_indicators)
    
    def _process_with_pipeline(self, request: Dict[str, Any]) -> GameResponse:
        """Process request using appropriate Haystack pipeline"""
        
        # Defensive programming - handle None request
        if request is None:
            return GameResponse(
                success=False,
                data={"error": "None request in pipeline processing"},
                correlation_id=None
            )
        
        request_type = request.get("type", request.get("request_type", ""))
        correlation_id = request.get("correlation_id")
        
        try:
            # Route to appropriate pipeline
            if request_type == "gameplay_turn":
                result = self._handle_gameplay_turn_pipeline(request)
            elif request_type == "scenario_generation" or request_type == "scenario":
                result = self._handle_scenario_pipeline(request)
            elif request_type == "npc_interaction":
                result = self._handle_npc_pipeline(request)
            elif request_type == "interface_processing":
                result = self._handle_interface_pipeline(request)
            elif request_type == "rag_query":
                result = self._handle_rag_pipeline(request)
            else:
                # Fallback to base orchestrator
                return super().process_request(request)
            
            return GameResponse(
                success=True,
                data=result,
                correlation_id=correlation_id,
                metadata={"processed_by": "pipeline", "pipeline_type": request_type}
            )
            
        except Exception as e:
            self.logger.error(f"Pipeline processing failed: {e}")
            self.logger.error(f"Request type: {type(request)}")
            self.logger.error(f"Request content: {request}")
            import traceback
            self.logger.error(f"Full traceback: {traceback.format_exc()}")
            return GameResponse(
                success=False,
                data={"error": str(e), "pipeline_error": True},
                correlation_id=correlation_id
            )
    
    def _handle_gameplay_turn_pipeline(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle full gameplay turn using pipeline integration"""
        
        data = request.get("data", {})
        player_input = data.get("player_input", "")
        context = data.get("context", {})
        
        # Step 1: Process input through interface agent
        interface_result = self._run_interface_pipeline({
            "player_input": player_input,
            "game_context": context
        })
        
        # Step 2: Determine routing based on interface analysis
        routing = interface_result.get("routing_strategy", "simple_response")
        
        if routing == "scenario_pipeline":
            # Generate scenario
            scenario_result = self._run_scenario_pipeline({
                "player_action": player_input,
                "game_context": context,
                "rag_context": request.get("rag_context", "")
            })
            return scenario_result
            
        elif routing == "npc_pipeline":
            # Handle NPC interaction
            npc_id = context.get("target_npc", "unknown_npc")
            npc_result = self._run_npc_pipeline({
                "npc_id": npc_id,
                "player_action": player_input,
                "npc_context": context.get("npc_data", {})
            })
            return npc_result
            
        elif routing == "skill_pipeline":
            # Process skill check through existing components
            skill_request = GameRequest(
                request_type="skill_check",
                data={
                    "action": player_input,
                    "actor": data.get("actor", "player"),
                    "skill": interface_result.get("primary_skill"),
                    "context": context
                }
            )
            skill_response = super().process_request(skill_request)
            return skill_response.data
            
        else:
            # Simple response
            return {
                "response": f"You {player_input}. The world responds accordingly.",
                "processed_by": "simple_pipeline"
            }
    
    def _handle_scenario_pipeline(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle scenario generation pipeline"""
        return self._run_scenario_pipeline(request.get("data", {}))
    
    def _handle_npc_pipeline(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle NPC interaction pipeline"""
        return self._run_npc_pipeline(request.get("data", {}))
    
    def _handle_interface_pipeline(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle interface processing pipeline"""
        return self._run_interface_pipeline(request.get("data", {}))
    
    def _handle_rag_pipeline(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle RAG query pipeline"""
        
        agent = self.agents["rag_retriever"]
        query = request.get("data", {}).get("query", "")
        
        try:
            result = agent.run(messages=[ChatMessage.from_user(f"Retrieve documents for: {query}")])
            return {"rag_result": result}
        except Exception as e:
            return {"error": f"RAG pipeline failed: {e}"}
    
    def _run_scenario_pipeline(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Run scenario generation pipeline"""
        
        pipeline = self.pipelines.get("scenario_generation")
        if not pipeline:
            return {"error": "Scenario pipeline not available"}
        
        try:
            result = pipeline.run({
                "player_action": data.get("player_action", ""),
                "game_context": data.get("game_context", {}),
                "rag_context": data.get("rag_context", "")
            })
            
            # Extract scenario data from pipeline result
            if "scenario_generator" in result:
                return result["scenario_generator"]
            else:
                return {"error": "No scenario data generated"}
                
        except Exception as e:
            return {"error": f"Scenario pipeline failed: {e}"}
    
    def _run_npc_pipeline(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Run NPC interaction pipeline"""
        
        pipeline = self.pipelines.get("npc_interaction")
        if not pipeline:
            return {"error": "NPC pipeline not available"}
        
        try:
            result = pipeline.run({
                "npc_id": data.get("npc_id", ""),
                "player_action": data.get("player_action", ""),
                "npc_context": data.get("npc_context", {})
            })
            
            if "npc_controller" in result:
                return result["npc_controller"]
            else:
                return {"error": "No NPC response generated"}
                
        except Exception as e:
            return {"error": f"NPC pipeline failed: {e}"}
    
    def _run_interface_pipeline(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Run interface processing pipeline"""
        
        pipeline = self.pipelines.get("interface_processing")
        if not pipeline:
            return {"error": "Interface pipeline not available"}
        
        try:
            result = pipeline.run({
                "player_input": data.get("player_input", ""),
                "game_context": data.get("game_context", {})
            })
            
            if "interface_agent" in result:
                return result["interface_agent"]
            else:
                return {"error": "No interface analysis generated"}
                
        except Exception as e:
            return {"error": f"Interface pipeline failed: {e}"}
    
    def _register_fallback_handlers(self):
        """Register fallback handlers when pipeline infrastructure fails"""
        
        fallback_handlers = {
            'gameplay_turn': self._handle_gameplay_turn_fallback,
            'scenario_generation': self._handle_scenario_fallback,
            'npc_interaction': self._handle_npc_fallback,
            'interface_processing': self._handle_interface_fallback,
        }
        
        # Register handlers with base orchestrator
        for handler_type, handler_func in fallback_handlers.items():
            self.register_handler(handler_type, handler_func)
        self.logger.info(f"Registered {len(fallback_handlers)} fallback handlers")
    
    def _handle_gameplay_turn_fallback(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback gameplay turn handler when pipelines are unavailable"""
        
        data = request.get("data", {})
        player_input = data.get("player_input", "")
        
        # Simple scenario generation fallback
        from agents.scenario_generator_agent import create_fallback_scenario
        scenario = create_fallback_scenario(player_input, {"difficulty": "medium"})
        
        return {
            "success": True,
            "data": scenario,
            "processed_by": "fallback_handler"
        }
    
    def _handle_scenario_fallback(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback scenario handler"""
        data = request.get("data", {})
        from agents.scenario_generator_agent import create_fallback_scenario
        scenario = create_fallback_scenario(data.get("player_action", ""), data.get("game_context", {}))
        return {"success": True, "data": scenario}
    
    def _handle_npc_fallback(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback NPC handler"""
        return {"success": True, "data": {"response": "The NPC responds thoughtfully to your words."}}
    
    def _handle_interface_fallback(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback interface handler"""
        return {"success": True, "data": {"routing_strategy": "simple_response"}}

    def get_pipeline_status(self) -> Dict[str, Any]:
        """Get comprehensive pipeline status"""
        
        status = {
            "pipelines_enabled": self.enable_pipelines,
            "available_pipelines": list(self.pipelines.keys()),
            "available_agents": list(self.agents.keys()),
            "context_broker_active": self.context_broker is not None
        }
        
        # Add base orchestrator status
        base_status = super().get_orchestrator_status()
        status.update(base_status)
        
        return status


# Factory functions for different configurations

def create_pipeline_orchestrator(policy_profile=PolicyProfile.RAW, enable_stage3=True,
                               enable_pipelines=True) -> PipelineOrchestrator:
    """Factory function to create pipeline-integrated orchestrator"""
    return PipelineOrchestrator(policy_profile, enable_stage3, enable_pipelines)

def create_full_haystack_orchestrator() -> PipelineOrchestrator:
    """Create orchestrator with all Haystack features enabled"""
    return PipelineOrchestrator(
        policy_profile=PolicyProfile.HOUSE,  # Use house rules for enhanced experience
        enable_stage3=True,
        enable_pipelines=True
    )

def create_backward_compatible_orchestrator() -> PipelineOrchestrator:
    """Create orchestrator that maintains backward compatibility"""
    return PipelineOrchestrator(
        policy_profile=PolicyProfile.RAW,
        enable_stage3=True,
        enable_pipelines=False  # Disable pipelines for compatibility
    )


# Example usage and testing
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("=== Pipeline Orchestrator Test ===")
    
    # Create pipeline orchestrator
    orchestrator = create_full_haystack_orchestrator()
    
    # Test pipeline status
    status = orchestrator.get_pipeline_status()
    print(f"Pipeline Status: {status}")
    
    # Test gameplay turn with pipeline
    gameplay_request = GameRequest(
        request_type="gameplay_turn",
        data={
            "player_input": "I want to search the ancient library for dragon lore",
            "actor": "player",
            "context": {
                "location": "Ancient Library",
                "difficulty": "medium",
                "complex": True
            }
        }
    )
    
    try:
        response = orchestrator.process_request(gameplay_request)
        print(f"Pipeline Response: {response.success}")
        print(f"Response Data: {response.data}")
        
    except Exception as e:
        print(f"Pipeline test failed: {e}")
    
    # Test backward compatibility
    print("\n=== Backward Compatibility Test ===")
    
    simple_request = GameRequest(
        request_type="dice_roll",
        data={"dice": "1d20", "modifier": 3}
    )
    
    compat_response = orchestrator.process_request(simple_request)
    print(f"Compatibility Response: {compat_response.success}")