"""
Pipeline Integration for Orchestrator
Connects Haystack pipelines with existing orchestrator infrastructure
Enables seamless integration between agents and components
"""

# Set tokenizers parallelism to avoid fork warnings - MUST be set before any imports
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from typing import Dict, Any, Optional, List, Union
import logging
import time
import traceback
from haystack import Pipeline
from haystack.components.builders.chat_prompt_builder import ChatPromptBuilder
from haystack.dataclasses import ChatMessage

from .simple_orchestrator import SimpleOrchestrator, GameRequest, GameResponse
from components.policy import PolicyProfile
from agents.scenario_generator_agent import create_scenario_generator_agent
from agents.rag_retriever_agent import create_rag_retriever_agent
from agents.npc_controller_agent import create_npc_controller_agent
from agents.main_interface_agent import create_main_interface_agent
from shared_contract import normalize_incoming
from config.llm_config import (
    create_custom_config,
    LLMConfigManager,
    set_global_config_manager,
    get_global_config_manager
)

# Simple logging for errors only
pipeline_logger = logging.getLogger("PipelineOrchestrator")
pipeline_logger.setLevel(logging.WARNING)


class PipelineOrchestrator(SimpleOrchestrator):
    """
    Enhanced orchestrator with Haystack pipeline integration
    Extends existing orchestrator while adding pipeline capabilities
    """
    
    def __init__(self, policy_profile: PolicyProfile = PolicyProfile.RAW,
                 enable_stage3: bool = True, enable_pipelines: bool = True,
                 collection_name: Optional[str] = None,
                 shared_document_store: Optional[Any] = None):
        super().__init__(policy_profile, enable_stage3)
        
        self.enable_pipelines = enable_pipelines
        self.logger = pipeline_logger
        self.collection_name = collection_name
        self.shared_document_store = shared_document_store
        
        # Initialize pipeline infrastructure
        self.pipelines: Dict[str, Pipeline] = {}
        self.agents: Dict[str, Any] = {}
        
        if enable_pipelines:
            self._initialize_pipeline_infrastructure()
            self._register_pipeline_handlers()
        
        print(f"🔄 Pipeline Orchestrator initialized (pipelines: {'enabled' if enable_pipelines else 'disabled'})")
    
    def _initialize_pipeline_infrastructure(self) -> None:
        """Initialize Haystack agents and LLM configuration"""
        try:
            # Create Custom GenAI configuration
            custom_config = create_custom_config()
            global_manager = LLMConfigManager(custom_config)
            set_global_config_manager(global_manager)
            
            # Initialize agents with shared document store to avoid resource conflicts
            scenario_agent = create_scenario_generator_agent()
            rag_agent = create_rag_retriever_agent(document_store=self.shared_document_store)
            npc_agent = create_npc_controller_agent()
            interface_agent = create_main_interface_agent()
            
            self.agents = {
                "scenario_generator": scenario_agent,
                "rag_retriever": rag_agent,
                "npc_controller": npc_agent,
                "main_interface": interface_agent
            }
            
            if self.shared_document_store:
                print(f"📚 Pipeline Orchestrator: Using shared document store for '{self.shared_document_store.collection_name}'")
            else:
                print("⚠️ Pipeline Orchestrator: No shared document store provided - RAG will use fallback responses")
            
            # Initialize pipelines
            self._create_pipelines()
            
        except Exception as e:
            pipeline_logger.error(f"Failed to initialize pipeline infrastructure: {e}")
            self.enable_pipelines = False
    
    def _create_pipelines(self) -> None:
        """Create Haystack pipelines for different request types"""
        try:
            # Scenario Generation Pipeline
            scenario_pipeline = Pipeline()
            scenario_pipeline.add_component("scenario_generator", self.agents["scenario_generator"])
            self.pipelines["scenario_generation"] = scenario_pipeline
            
            # RAG Query Pipeline
            rag_pipeline = Pipeline()
            rag_pipeline.add_component("rag_retriever", self.agents["rag_retriever"])
            self.pipelines["rag_retriever"] = rag_pipeline
            
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
    
    def _register_pipeline_handlers(self) -> None:
        """Register pipeline-specific request handlers"""
        if not self.enable_pipelines:
            return
            
        # Add pipeline handlers to existing handlers
        pipeline_handlers = {
            'gameplay_turn': self._handle_gameplay_turn_pipeline,
            'scenario_generation': self._handle_scenario_pipeline,
            'scenario_pipeline_with_rag_context': self._handle_rag_enhanced_scenario_pipeline,
            'npc_interaction': self._handle_npc_pipeline,
            'interface_processing': self._handle_interface_pipeline,
            'rag_query': self._handle_rag_pipeline
        }
        
        # Register handlers with base orchestrator
        for handler_type, handler_func in pipeline_handlers.items():
            self.register_handler(handler_type, handler_func)
        self.logger.info(f"Registered {len(pipeline_handlers)} pipeline handlers")
    
    def process_request(self, request: Union[GameRequest, Dict[str, Any], None]) -> GameResponse:
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
                    
            result = self._process_with_pipeline(request_dict)
            return result
                
        except Exception as e:
            pipeline_logger.error(f"Pipeline orchestrator error: {e}")
            correlation_id = None
            try:
                correlation_id = request_dict.get("correlation_id") if 'request_dict' in locals() and request_dict else None
            except Exception:
                pass
            return GameResponse(
                success=False,
                data={"error": f"Pipeline orchestrator error: {str(e)}"},
                correlation_id=correlation_id
            )
     
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
            elif request_type in ["scenario_generation", "scenario"]:
                result = self._handle_scenario_pipeline(request)
            elif request_type == "scenario_pipeline_with_rag_context":
                result = self._handle_rag_enhanced_scenario_pipeline(request)
            elif request_type == "npc_interaction":
                result = self._handle_npc_pipeline(request)
            elif request_type == "interface_processing":
                result = self._handle_interface_pipeline(request)
            elif request_type == "rag_query":
                result = self._handle_rag_pipeline(request)
            else:
                # Fall back to parent orchestrator for unknown request types
                return super().process_request(request)
            
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
        
        try:
            # Step 1: Process input through interface agent
            interface_result = self._run_interface_pipeline({
                "player_input": player_input,
                "game_context": context
            })
            
            # Check for interface processing error
            if interface_result is None or "error" in interface_result:
                error_msg = interface_result.get("error", "Interface processing returned None") if interface_result else "Interface processing returned None"
                return {
                    "response": f"You {player_input}. The world responds accordingly.",
                    "processed_by": "fallback_pipeline",
                    "interface_error": error_msg
                }
            
            # Step 2: Determine routing based on interface analysis
            routing = interface_result.get("routing_strategy", "simple_response") if interface_result else "simple_response"
            
            if routing == "scenario_pipeline":
                return self._run_scenario_pipeline({
                    "player_action": player_input,
                    "game_context": context,
                    "rag_context": request.get("rag_context", "")
                })
                
            elif routing == "npc_pipeline":
                npc_id = context.get("target_npc", "unknown_npc")
                return self._run_npc_pipeline({
                    "npc_id": npc_id,
                    "player_action": player_input,
                    "npc_context": context.get("npc_data", {})
                })
                
            elif routing == "skill_pipeline":
                # Process skill check through existing components
                primary_skill = interface_result.get("primary_skill", "investigation")  # Default skill
                skill_request = GameRequest(
                    request_type="skill_check",
                    data={
                        "action": player_input,
                        "actor": data.get("actor", "player"),
                        "skill": primary_skill,
                        "context": context
                    }
                )
                skill_response = super().process_request(skill_request)
                return skill_response.data if skill_response.success else {
                    "error": "Skill check failed",
                    "attempted_skill": primary_skill,
                    "fallback_response": f"You attempt to {player_input} but encounter difficulties."
                }
                
            else:
                # Simple response
                return {
                    "response": f"You {player_input}. The world responds accordingly.",
                    "processed_by": "simple_pipeline"
                }
                
        except Exception as e:
            pipeline_logger.error(f"Gameplay turn pipeline failed: {e}")
            return {
                "response": f"You {player_input}. The world responds accordingly.",
                "processed_by": "error_fallback",
                "error": str(e)
            }
    
    def _handle_scenario_pipeline(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle scenario generation pipeline"""
        return self._run_scenario_pipeline(request.get("data", {}))
    
    def _handle_rag_enhanced_scenario_pipeline(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle RAG-enhanced scenario generation pipeline"""
        return self._run_rag_enhanced_scenario_pipeline(request)
    
    def _handle_npc_pipeline(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle NPC interaction pipeline"""
        return self._run_npc_pipeline(request.get("data", {}))
    
    def _handle_interface_pipeline(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle interface processing pipeline"""
        return self._run_interface_pipeline(request.get("data", {}))
    
    def _handle_rag_pipeline(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle RAG query pipeline"""
        return self._run_rag_pipeline(request.get("data", {}))
    
    def _run_scenario_pipeline(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Run scenario generation pipeline using Haystack tool framework with connected components"""
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
            
            # Ensure debug field exists for the tool
            if "debug" not in request_dto:
                request_dto["debug"] = {}
            
            # Get scenario agent
            scenario_agent = self.agents.get("scenario_generator")
            if not scenario_agent:
                return {"error": "Scenario generator agent not available"}
            
            # Create scenario generation message with DTO data
            scenario_message = ChatMessage.from_user(f"""
            Player Action: {player_action}
            Game Context: {game_context}
            DTO: {request_dto}
            
            Use the create_scenario_from_dto tool to generate a validated D&D scenario.
            """)
            
            # Run scenario generation
            scenario_result = scenario_agent.run(messages=[scenario_message])
            
            # Extract scenario from agent state (using outputs_to_state feature)
            if "scenario_result" in scenario_result:
                scenario_dto = scenario_result["scenario_result"]
                if "scenario" in scenario_dto:
                    scenario = scenario_dto["scenario"]
                    return {
                        "scene": scenario.get("scene", f"You {player_action}. The world responds accordingly."),
                        "choices": scenario.get("choices", []),
                        "effects": scenario.get("effects", {}),
                        "hooks": scenario.get("hooks", []),
                        "fallback_used": scenario_dto.get("fallback", False),
                        "processing_metadata": {
                            "pipeline_path": "standard_scenario",
                            "haystack_pipeline_used": True,
                            "pipeline_components": ["ScenarioGenerator"],
                            "validation_applied": True
                        }
                    }
            
            # Fallback if no scenario in state
            return {
                "scene": f"You {player_action}. The world responds accordingly.",
                "processing_metadata": {
                    "pipeline_path": "fallback_scenario",
                    "haystack_pipeline_used": False,
                    "error": "No scenario result in agent state"
                }
            }
                
        except Exception as e:
            pipeline_logger.error(f"Scenario pipeline failed: {e}")
            return {"error": f"Haystack pipeline-based scenario generation failed: {e}"}
    
    def _run_rag_enhanced_scenario_pipeline(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle RAG-enhanced scenario generation pipeline"""
        data = request.get("data", {})
        player_action = data.get("player_action", "")
        game_context = data.get("game_context", {})
        rag_assessment = data.get("rag_assessment", {})
        
        try:
            # Step 1: Use RAG retriever to get relevant documents
            rag_agent = self.agents.get("rag_retriever")
            if not rag_agent:
                return {"error": "RAG retriever agent not available"}
            
            # Determine query and context type from RAG assessment
            rag_type = rag_assessment.get("rag_type", "general")
            query_suggestions = rag_assessment.get("query_suggestions", [player_action])
            query = query_suggestions[0] if query_suggestions else player_action
            
            # Get RAG context
            rag_message = ChatMessage.from_user(f"Query: {query}, Context Type: {rag_type}")
            rag_result = rag_agent.run(messages=[rag_message])
            
            # Extract formatted context
            rag_context = ""
            if "formatted_context" in rag_result:
                rag_context = rag_result["formatted_context"].get("context", "")
            
            # Step 2: Create enhanced DTO with RAG context
            enhanced_dto = normalize_incoming({
                "action": player_action,
                "player_input": player_action,
                "context": game_context,
                "type": "scenario"
            })
            # Add RAG context to the DTO after normalization
            enhanced_dto["rag_blocks"] = [{"context": rag_context, "type": rag_type}]
            
            # Ensure debug field exists for the tool
            if "debug" not in enhanced_dto:
                enhanced_dto["debug"] = {}
            
            # Step 3: Generate scenario with RAG context using scenario agent
            scenario_agent = self.agents.get("scenario_generator")
            if not scenario_agent:
                return {"error": "Scenario generator agent not available"}
            
            scenario_message = ChatMessage.from_user(f"""
            Player Action: {player_action}
            Game Context: {game_context}
            RAG Context: {rag_context}
            DTO: {enhanced_dto}
            
            Use the create_scenario_from_dto tool to generate a RAG-enhanced D&D scenario.
            """)
            
            scenario_result = scenario_agent.run(messages=[scenario_message])
            
            # Extract scenario from agent state (using outputs_to_state feature)
            if "scenario_result" in scenario_result:
                scenario_dto = scenario_result["scenario_result"]
                if "scenario" in scenario_dto:
                    scenario = scenario_dto["scenario"]
                    return {
                        "scene": scenario.get("scene", "You take action in the world..."),
                        "choices": scenario.get("choices", []),
                        "effects": scenario.get("effects", {}),
                        "hooks": scenario.get("hooks", []),
                        "rag_context_used": rag_context,
                        "fallback_used": scenario_dto.get("fallback", False),
                        "processing_metadata": {
                            "pipeline_type": "rag_enhanced_scenario",
                            "rag_type": rag_type,
                            "query_used": query,
                            "haystack_pipeline_used": True,
                            "validation_applied": True
                        }
                    }
            
            # Fallback if no scenario in state
            return {
                "scene": f"You {player_action}. Something happens in response.",
                "rag_context_used": rag_context,
                "processing_metadata": {
                    "pipeline_type": "rag_enhanced_scenario_fallback",
                    "rag_type": rag_type,
                    "query_used": query,
                    "error": "No scenario result in agent state"
                }
            }
            
        except Exception as e:
            pipeline_logger.error(f"RAG-enhanced scenario pipeline failed: {e}")
            return {
                "error": f"RAG-enhanced scenario generation failed: {e}",
                "fallback_scene": f"You {player_action}. Something happens in response."
            }
    
    def _run_rag_pipeline(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Run RAG query pipeline for pure knowledge retrieval"""
        try:
            query = data.get("query", "")
            context_type = data.get("context_type", "general")
            filters = data.get("filters", {})
            
            if not query:
                return {
                    "error": "No query provided for RAG pipeline",
                    "rag_result": None
                }
            
            # Use RAG retriever agent for document retrieval and formatting
            rag_agent = self.agents.get("rag_retriever")
            if not rag_agent:
                return {"error": "RAG retriever agent not available"}
            
            # Create message for RAG agent
            rag_message = ChatMessage.from_user(f"""
            Query: {query}
            Context Type: {context_type}
            Filters: {filters}
            
            Retrieve relevant documents for this query and format them appropriately.
            """)
            
            # Run RAG retrieval
            rag_result = rag_agent.run(messages=[rag_message])
            
            # Extract and format results
            formatted_context = {}
            if "formatted_context" in rag_result:
                formatted_context = rag_result["formatted_context"]
            
            # Build comprehensive response
            return {
                "query": query,
                "context_type": context_type,
                "rag_context": formatted_context.get("context", ""),
                "source_count": formatted_context.get("source_count", 0),
                "relevance": formatted_context.get("relevance", "none"),
                "processing_metadata": {
                    "pipeline_type": "rag_query",
                    "haystack_pipeline_used": True,
                    "filters_applied": filters
                }
            }
            
        except Exception as e:
            pipeline_logger.error(f"RAG pipeline failed: {e}")
            return {
                "error": f"RAG query pipeline failed: {e}",
                "query": data.get("query", ""),
                "rag_result": None
            }
    
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
            pipeline_logger.error(f"NPC pipeline failed: {e}")
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
                        route = routing_decision.get('route', 'simple_response')
                        route_mapping = {
                            "scenario": "scenario_pipeline",
                            "scenario_pipeline_with_rag_context": "scenario_pipeline_with_rag_context",
                            "rag_query": "rag_query",
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
    
    def get_pipeline_status(self) -> Dict[str, Any]:
        """Get comprehensive pipeline status"""
        status = {
            "pipelines_enabled": self.enable_pipelines,
            "available_pipelines": list(self.pipelines.keys()),
            "available_agents": list(self.agents.keys()),
        }
        
        # Add initialization metrics if available
        if hasattr(self, 'initialization_metrics'):
            status["initialization_metrics"] = self.initialization_metrics
        
        # Add base orchestrator status
        try:
            base_status = super().get_orchestrator_status()
            status.update(base_status)
        except Exception as e:
            pipeline_logger.warning(f"Could not get base orchestrator status: {e}")
        
        return status


def create_full_haystack_orchestrator(collection_name: Optional[str] = None,
                                     shared_document_store: Optional[Any] = None) -> PipelineOrchestrator:
    """Create orchestrator with all Haystack features enabled"""
    return PipelineOrchestrator(
        policy_profile=PolicyProfile.HOUSE,  # Use house rules for enhanced experience
        enable_stage3=True,
        enable_pipelines=True,
        collection_name=collection_name,
        shared_document_store=shared_document_store
    )

# Example usage and testing
def main() -> None:
    """Main function for testing the pipeline orchestrator"""
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("=== Pipeline Orchestrator Test ===")
    
    try:
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
        
        response = orchestrator.process_request(gameplay_request)
        print(f"Pipeline Response: {response.success}")
        print(f"Response Data: {response.data}")
        
        # Test backward compatibility
        print("\n=== Backward Compatibility Test ===")
        
        simple_request = GameRequest(
            request_type="dice_roll",
            data={"dice": "1d20", "modifier": 3}
        )
        
        compat_response = orchestrator.process_request(simple_request)
        print(f"Compatibility Response: {compat_response.success}")
        
    except Exception as e:
        print(f"Pipeline test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()