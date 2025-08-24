"""
Pipeline Integration for Orchestrator
Connects Haystack pipelines with existing orchestrator infrastructure
Enables seamless integration between agents and components
"""

from typing import Dict, Any, Optional, List
import logging
import time
import traceback
from haystack import Pipeline
from haystack.components.builders.chat_prompt_builder import ChatPromptBuilder
from haystack.components.tools import ToolInvoker
from haystack.components.routers import ConditionalRouter
from haystack.dataclasses import ChatMessage

from .simple_orchestrator import SimpleOrchestrator, GameRequest, GameResponse
from .context_broker import ContextBroker
from components.policy import PolicyProfile
from agents.scenario_generator_agent import create_scenario_generator_agent
from agents.rag_retriever_agent import create_rag_retriever_agent, assess_rag_need
from agents.npc_controller_agent import create_npc_controller_agent
from agents.main_interface_agent import create_main_interface_agent
from shared_contract import normalize_incoming
from config.llm_config import create_custom_config, LLMConfigManager, set_global_config_manager, get_global_config_manager

# Simple logging for errors only
pipeline_logger = logging.getLogger("PipelineOrchestrator")
pipeline_logger.setLevel(logging.WARNING)


class PipelineOrchestrator(SimpleOrchestrator):
    """
    Enhanced orchestrator with Haystack pipeline integration
    Extends existing orchestrator while adding pipeline capabilities
    """
    
    def __init__(self, policy_profile=PolicyProfile.RAW, enable_stage3=True, enable_pipelines=True, collection_name=None):
        super().__init__(policy_profile, enable_stage3)
        
        self.enable_pipelines = enable_pipelines
        self.logger = pipeline_logger
        self.collection_name = collection_name  # Store collection name for agent creation
        
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
            # Try to create Custom GenAI configuration
            custom_config = create_custom_config()
            global_manager = LLMConfigManager(custom_config)
            set_global_config_manager(global_manager)
     
            # Initialize context broker
            self.context_broker = ContextBroker()
            
            # Initialize agents
            scenario_agent = create_scenario_generator_agent()
            rag_agent = create_rag_retriever_agent(collection_name=self.collection_name)
            npc_agent = create_npc_controller_agent()
            interface_agent = create_main_interface_agent()
            
            self.agents = {
                "scenario_generator": scenario_agent,
                "rag_retriever": rag_agent,
                "npc_controller": npc_agent,
                "main_interface": interface_agent
            }
            
            # Initialize pipelines
            self._create_pipelines()
            
        except Exception as e:
            pipeline_logger.error(f"Failed to initialize pipeline infrastructure: {e}")
            self.enable_pipelines = False
    
    def _create_pipelines(self):
        """Create Haystack pipelines for different request types"""
        
        try:
            # Scenario Generation Pipeline
            scenario_pipeline = Pipeline()
            scenario_pipeline.add_component("rag_retriever", self.agents["rag_retriever"])
            scenario_pipeline.add_component("scenario_generator", self.agents["scenario_generator"])
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
            
        except Exception as e:
            pipeline_logger.error(f"Failed to create pipelines: {e}")
            raise
    
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
                return GameResponse(
                    success=False,
                    data={"error": "None request received"},
                    correlation_id=None
                )
            
            # Convert to standard format
            if isinstance(request, GameRequest):
                request_dict = {
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
                    
            result = self._process_with_pipeline(request_dict)
            
            # Determine processing path
            # use_pipeline = self._should_use_pipeline(request_dict)
            
            # if use_pipeline:
            #     result = self._process_with_pipeline(request_dict)
            # else:
            #     # Use existing orchestrator processing
            #     result = super().process_request(request)
            
            return result
                
        except Exception as e:
            pipeline_logger.error(f"Pipeline orchestrator error: {e}")
            correlation_id = None
            try:
                correlation_id = request_dict.get("correlation_id") if 'request_dict' in locals() and request_dict else None
            except:
                pass
            return GameResponse(
                    success=False,
                    data={"error": f"Pipeline orchestrator error: {str(e)}"},
                    correlation_id=correlation_id
                )
    
    def _should_use_pipeline(self, request: Dict[str, Any]) -> bool:
        """Determine if request should use pipeline processing"""
        
        if not self.enable_pipelines or request is None:
            return False
            
        request_type = request.get("request_type", "")
        
        # Pipeline-enabled request types
        pipeline_types = [
            "gameplay_turn",
            "scenario_generation",
            "npc_interaction",
            "interface_processing",
            "rag_query"
        ]
        
        # Check if request explicitly requests pipeline
        explicit_pipeline = request.get("use_pipeline", False)
        if explicit_pipeline:
            return True
            
        # Check request complexity
        rag_context_present = bool(request.get("rag_context"))
        data_size = len(str(request.get("data", {})))
        context_complex = request.get("context", {}).get("complex", False) if request.get("context") is not None else False
        
        complexity_indicators = [
            rag_context_present,
            data_size > 100,
            context_complex
        ]
        
        type_match = request_type in pipeline_types
        complexity_match = any(complexity_indicators)
        
        return type_match or complexity_match
    
    def _process_with_pipeline(self, request: Dict[str, Any]) -> GameResponse:
        """Process request using appropriate Haystack pipeline"""
        
        # Defensive programming - handle None request
        if request is None:
            return GameResponse(
                success=False,
                data={"error": "None request in pipeline processing"},
                correlation_id=None
            )
        
        request_type = request.get("request_type", "")
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
                return GameResponse(
                    success=False,
                    data={"error": "Error in pipeline processing"}
                )
            
            return GameResponse(
                success=True,
                data=result,
                correlation_id=correlation_id,
                metadata={
                    "processed_by": "pipeline",
                    "pipeline_type": request_type
                }
            )
            
        except Exception as e:
            pipeline_logger.error(f"Pipeline processing failed: {e}")
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
            
            # Use state schema for easy access to RAG results
            if "formatted_context" in result:
                return {"rag_result": result["formatted_context"]}
            elif "rag_assessment" in result:
                return {"rag_result": result["rag_assessment"]}
            else:
                return {"rag_result": result}
        except Exception as e:
            return {"error": f"RAG pipeline failed: {e}"}
    
    def _run_scenario_pipeline(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Run scenario generation pipeline using Haystack tool framework with connected components"""
        
        pipeline_start = time.time()
        
        try:
            player_action = data.get("player_action", "")
            game_context = data.get("game_context", {})
            
            # Step 1: Normalize incoming data to DTO format
            request_dto = normalize_incoming({
                "action": player_action,
                "player_input": player_action,
                "context": game_context,
                "type": "scenario"
            })
            
            # Step 3: Create chat generator with RAG tools
            config_manager = get_global_config_manager()
            chat_generator = config_manager.create_generator("rag_retriever")
            # chat_generator.tools = assess_rag_need
            
            # Step 4: Create ToolInvoker with RAG tools
            tool_invoker = ToolInvoker(tools=[assess_rag_need])
            
            # Step 5: Define routing conditions based on tool call results
            routes = [
                {
                    "condition": "{{ tool_calls|length > 0 }}",
                    "output": "{{ messages }}",
                    "output_name": "rag_needed_path",
                    "output_type": List[ChatMessage],
                },
                {
                    "condition": "{{ tool_calls|length == 0 }}",
                    "output": "{{ messages }}",
                    "output_name": "no_rag_path",
                    "output_type": List[ChatMessage],
                },
            ]
            
            # Step 6: Create ConditionalRouter for RAG routing
            rag_router = ConditionalRouter(routes, unsafe=True)
            
            # Step 7: Create the RAG assessment pipeline
            scenario_gen_pipeline = Pipeline()
            scenario_gen_pipeline.add_component("generator", chat_generator)
            scenario_gen_pipeline.add_component("router", rag_router)
            scenario_gen_pipeline.add_component("tool_invoker", tool_invoker)
            scenario_gen_pipeline.add_component("rag_retriever", self.agents["rag_retriever"])
            scenario_gen_pipeline.add_component("scenario_generator", self.agents["scenario_generator"])
            
            
            scenario_gen_pipeline.add_component("assessment_prompt", ChatPromptBuilder(
                template=[ChatMessage.from_user("""
                Please use assess_rag_need tool to evaluate if RAG retrieval is needed for:
                Action: {{ player_action }}
                Context: {{ game_context }}
                
                """)],
                required_variables=["player_action", "game_context"]
            ))
            
            scenario_gen_pipeline.add_component("rag_prompt", ChatPromptBuilder(
                template=[ChatMessage.from_user("""
                Player Action: {{ player_action }}
                Game Context: {{ game_context }}
                
                Retrieve the relevant rules, context, or lore for the following D&D scenario:
                """)],
                required_variables=["player_action", "game_context"]
            ))
            
            scenario_gen_pipeline.add_component("rag_scenario_prompt", ChatPromptBuilder(
                template=[ChatMessage.from_user("""
                Player Action: {{ player_action }}
                Game Context: {{ game_context }}
                RAG Context: {{ rag_data }}
                
                Use the provided RAG context, Game context, and player action to generate a detailed D&D scenario:
                """)],
                required_variables=["player_action", "game_context", "rag_data"]
            ))
            
            scenario_gen_pipeline.add_component("standard_prompt", ChatPromptBuilder(
                template=[ChatMessage.from_user("""
                Player Action: {{ player_action }}
                Game Context: {{ game_context }}
                
                Generate detailed D&D scenario using the player action and game context:
                """)],
                required_variables=["player_action", "game_context"]
            ))
            
             # Connect components in proper flow
            scenario_gen_pipeline.connect("assessment_prompt.prompt", "generator.messages")
            scenario_gen_pipeline.connect("generator.replies", "tool_invoker.messages")
            scenario_gen_pipeline.connect("tool_invoker.tool_calls", "router.tool_calls")
            
            scenario_gen_pipeline.connect("router.rag_needed_path", "rag_prompt.player_action")
            scenario_gen_pipeline.connect("rag_prompt.prompt", "rag_retriever")
            scenario_gen_pipeline.connect("rag_retriever.formatted_context", "rag_scenario_prompt.rag_data")
            scenario_gen_pipeline.connect("rag_scenario_prompt.prompt", "scenario_generator")
            
            scenario_gen_pipeline.connect("router.no_rag_path", "standard_prompt.player_action")
            scenario_gen_pipeline.connect("standard_prompt.prompt", "scenario_generator")
            
            scenario_result = scenario_gen_pipeline.run({
                "assessment_prompt": {
                    "player_action": player_action,
                    "game_context": game_context
                },
                "rag_prompt": {
                    "player_action": player_action,
                    "game_context": game_context
                },
                "rag_scenario_prompt": {
                    "player_action": player_action,
                    "game_context": game_context
                },
                "standard_prompt": {
                    "player_action": player_action,
                    "game_context": game_context
                }
            })
            
            # Extract scenario text
            scenario_text = f"You {player_action}. The world responds with mysterious energy."
            if "scenario_generator" in scenario_result:
                scenario_data = scenario_result["scenario_generator"]
                if isinstance(scenario_data, dict) and "replies" in scenario_data:
                    replies = scenario_data["replies"]
                    if replies and len(replies) > 0:
                        scenario_text = replies[0].content
                elif isinstance(scenario_data, dict) and "scene" in scenario_data:
                    scenario_text = scenario_data["scene"]
            
            # Determine which path was used
            pipeline_path = "standard"
            if "router" in scenario_result:
                router_result = scenario_result["router"]
                if "rag_needed_path" in router_result:
                    pipeline_path = "rag_enhanced"
            
            # Build response
            return {
                "scene": scenario_text,
                "processing_metadata": {
                    "pipeline_path": pipeline_path,
                    "haystack_pipeline_used": True,
                    "pipeline_components": ["ConditionalRouter", "ChatPromptBuilder", "Generator"]
                }
            }
                
        except Exception as e:
            pipeline_logger.error(f"Haystack pipeline-based scenario generation failed: {e}")
            pipeline_logger.error(f"Full traceback: {traceback.format_exc()}")
            return {"error": f"Haystack pipeline-based scenario generation failed: {e}"}
    
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
                agent_result = result["npc_controller"]
                
                # Use state schema for easy access to NPC response
                if "npc_response" in agent_result:
                    return agent_result["npc_response"]
                else:
                    return {"error": "No NPC response in state"}
            else:
                return {"error": "No NPC controller result"}
                
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
                agent_result = result["interface_agent"]
                
                # Use state schema values for easy access to routing decision
                if "routing_decision" in agent_result:
                    routing_decision = agent_result["routing_decision"]
                    
                    # Extract routing strategy from the routing decision
                    if isinstance(routing_decision, dict):
                        # Map agent route to pipeline routing strategy
                        route = routing_decision['route']
                        route_mapping = {
                            "scenario": "scenario_pipeline",
                            "npc": "npc_pipeline",
                            "rules": "skill_pipeline",
                            "meta": "orchestrator_direct"
                        }
                        routing_strategy = route_mapping.get(route, "simple_response")
                        routing_decision['routing_strategy'] = routing_strategy
                        return routing_decision
                
                else:
                    return {"routing_strategy": "simple_response"}
            else:
                return {"error": "No interface analysis generated"}
                
        except Exception as e:
            pipeline_logger.error(f"Interface pipeline failed: {e}")
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
        
        # Add initialization metrics if available
        if hasattr(self, 'initialization_metrics'):
            status["initialization_metrics"] = self.initialization_metrics
        
        # Add base orchestrator status
        try:
            base_status = super().get_orchestrator_status()
            status.update(base_status)
        except Exception as e:
            pass
        
        return status


# Factory functions for different configurations

def create_pipeline_orchestrator(policy_profile=PolicyProfile.RAW, enable_stage3=True,
                               enable_pipelines=True) -> PipelineOrchestrator:
    """Factory function to create pipeline-integrated orchestrator"""
    return PipelineOrchestrator(policy_profile, enable_stage3, enable_pipelines)

def create_full_haystack_orchestrator(collection_name=None) -> PipelineOrchestrator:
    """Create orchestrator with all Haystack features enabled"""
    return PipelineOrchestrator(
        policy_profile=PolicyProfile.HOUSE,  # Use house rules for enhanced experience
        enable_stage3=True,
        enable_pipelines=True,
        collection_name=collection_name
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