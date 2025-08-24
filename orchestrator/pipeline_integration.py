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

# DEBUG CONTROL - Set to True to enable detailed debugging
DEBUG_PIPELINE = True
DEBUG_AGENTS = True
DEBUG_REQUESTS = True
DEBUG_RESPONSES = True

def debug_print(category: str, message: str, data: Any = None):
    """Centralized debug printing with categories"""
    if DEBUG_PIPELINE:
        timestamp = time.strftime('%H:%M:%S')
        print(f"🐛 [{timestamp}] {category}: {message}")
        if data is not None and (DEBUG_REQUESTS or DEBUG_RESPONSES):
            if isinstance(data, dict) and len(str(data)) > 200:
                print(f"    📊 Data keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
            else:
                print(f"    📊 Data: {data}")
from haystack import Pipeline
from haystack.components.builders.chat_prompt_builder import ChatPromptBuilder
from haystack.dataclasses import ChatMessage

from .simple_orchestrator import SimpleOrchestrator, GameRequest, GameResponse
from components.policy import PolicyProfile
from agents.scenario_generator_agent import create_scenario_generator_agent
from agents.rag_retriever_agent import create_rag_retriever_agent
from agents.npc_controller_agent import create_npc_controller_agent
from agents.main_interface_agent import create_main_interface_agent
from main_interface_agent_fixed import create_fixed_interface_agent
from shared_contract import normalize_incoming
from adapters.world_state_adapter import WorldStateAdapter, MockWorldStateAdapter
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
        self.world_state_adapter: Optional[WorldStateAdapter] = None
        
        if enable_pipelines:
            self._initialize_pipeline_infrastructure()
            self._register_pipeline_handlers()
        
        print(f"🔄 Pipeline Orchestrator initialized (pipelines: {'enabled' if enable_pipelines else 'disabled'})")
    
    def _initialize_pipeline_infrastructure(self) -> None:
        """Initialize Haystack agents and LLM configuration with fixed system integration"""
        try:
            # Create Custom GenAI configuration
            custom_config = create_custom_config()
            global_manager = LLMConfigManager(custom_config)
            set_global_config_manager(global_manager)
            
            # Create world state adapter for fixed system integration
            if hasattr(self, 'game_engine') and self.game_engine:
                self.world_state_adapter = WorldStateAdapter(self.game_engine)
                debug_print("ORCHESTRATOR", "✅ Created WorldStateAdapter with GameEngine")
            else:
                self.world_state_adapter = MockWorldStateAdapter()
                debug_print("ORCHESTRATOR", "⚠️ Created MockWorldStateAdapter (no GameEngine)")
            
            # Initialize agents - use fixed interface agent for improved performance
            scenario_agent = create_scenario_generator_agent()
            rag_agent = create_rag_retriever_agent(document_store=self.shared_document_store)
            npc_agent = create_npc_controller_agent()
            
            # Use the new fixed interface agent
            interface_agent = create_fixed_interface_agent()
            debug_print("ORCHESTRATOR", "✅ Created fixed interface agent")
            
            self.agents = {
                "scenario_generator": scenario_agent,
                "rag_retriever": rag_agent,
                "npc_controller": npc_agent,
                "main_interface": interface_agent  # Fixed system agent
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
        debug_print("PIPELINE", "🔄 Starting pipeline processing", {"request_keys": list(request.keys()) if request else None})
        
        # Defensive programming - handle None request
        if request is None:
            debug_print("PIPELINE", "❌ None request in pipeline processing")
            return GameResponse(
                success=False,
                data={"error": "None request in pipeline processing"},
                correlation_id=None
            )
        
        request_type = request.get("request_type", "")
        correlation_id = request.get("correlation_id")
        debug_print("PIPELINE", f"🎯 Request routing", {"type": request_type, "correlation_id": correlation_id})
        
        try:
            # Route to appropriate pipeline
            if request_type == "gameplay_turn":
                debug_print("PIPELINE", "🎮 Routing to gameplay_turn pipeline")
                result = self._handle_gameplay_turn_pipeline(request)
            elif request_type in ["scenario_generation", "scenario"]:
                debug_print("PIPELINE", "📖 Routing to scenario pipeline")
                result = self._handle_scenario_pipeline(request)
            elif request_type == "scenario_pipeline_with_rag_context":
                debug_print("PIPELINE", "📚 Routing to RAG-enhanced scenario pipeline")
                result = self._handle_rag_enhanced_scenario_pipeline(request)
            elif request_type == "npc_interaction":
                debug_print("PIPELINE", "👥 Routing to NPC pipeline")
                result = self._handle_npc_pipeline(request)
            elif request_type == "interface_processing":
                debug_print("PIPELINE", "🖥️ Routing to interface pipeline")
                result = self._handle_interface_pipeline(request)
            elif request_type == "rag_query":
                debug_print("PIPELINE", "🔍 Routing to RAG pipeline")
                result = self._handle_rag_pipeline(request)
            else:
                debug_print("PIPELINE", f"⬅️ Falling back to parent orchestrator for type: {request_type}")
                # Fall back to parent orchestrator for unknown request types
                return super().process_request(request)
            
            debug_print("PIPELINE", "✅ Pipeline processing successful", {"result_keys": list(result.keys()) if isinstance(result, dict) else type(result)})
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
            debug_print("PIPELINE", f"💥 Pipeline processing exception: {e}")
            debug_print("PIPELINE", f"📋 Exception traceback: {traceback.format_exc()}")
            pipeline_logger.error(f"Pipeline processing failed: {e}")
            return GameResponse(
                success=False,
                data={"error": str(e), "pipeline_error": True},
                correlation_id=correlation_id
            )
    
    def _handle_gameplay_turn_pipeline(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle full gameplay turn using fixed system integration"""
        data = request.get("data", {})
        player_input = data.get("player_input", "")
        context = data.get("context", {})
        
        debug_print("GAMEPLAY", f"🎮 Starting gameplay turn", {"input": player_input})
        
        try:
            # Step 1: Process input through fixed interface agent
            interface_result = self._run_interface_pipeline({
                "player_input": player_input,
                "game_context": context
            })
            
            debug_print("GAMEPLAY", f"📋 Interface result", {"routing": interface_result.get("routing_strategy"), "route": interface_result.get("route")})
            
            # Check for interface processing error
            if interface_result is None or "error" in interface_result:
                error_msg = interface_result.get("error", "Interface processing failed") if interface_result else "Interface processing returned None"
                debug_print("GAMEPLAY", f"❌ Interface error: {error_msg}")
                return {
                    "response": f"You {player_input}. The world responds accordingly.",
                    "processed_by": "fallback_pipeline",
                    "interface_error": error_msg
                }
            
            # Step 2: Route based on fixed system routing decision
            routing_strategy = interface_result.get("routing_strategy", "scenario_pipeline")
            route = interface_result.get("route", "scenario")
            
            debug_print("GAMEPLAY", f"🎯 Routing decision", {"strategy": routing_strategy, "route": route})
            
            # Enhanced routing with fixed system data
            if routing_strategy == "scenario_pipeline":
                scenario_data = {
                    "player_action": player_input,
                    "game_context": context,
                    "routing_context": interface_result,  # Pass routing context
                    "rag_assessment": interface_result.get("rag", {})
                }
                return self._run_scenario_pipeline(scenario_data)
                
            elif routing_strategy == "npc_pipeline":
                # Use resolved target from fixed system
                target_npc = interface_result.get("target", "unknown_npc")
                npc_data = {
                    "npc_id": target_npc,
                    "player_action": player_input,
                    "npc_context": context.get("npc_data", {}),
                    "routing_context": interface_result
                }
                return self._run_npc_pipeline(npc_data)
                
            elif routing_strategy == "rules_pipeline":
                # Enhanced skill check with fixed system context
                skill_request = GameRequest(
                    request_type="skill_check",
                    data={
                        "action": player_input,
                        "actor": data.get("actor", "player"),
                        "skill": interface_result.get("suggested_skill", "investigation"),
                        "context": context,
                        "routing_context": interface_result
                    }
                )
                skill_response = super().process_request(skill_request)
                return skill_response.data if skill_response.success else {
                    "error": "Skill check failed",
                    "attempted_skill": interface_result.get("suggested_skill", "investigation"),
                    "fallback_response": f"You attempt to {player_input} but encounter difficulties.",
                    "routing_context": interface_result
                }
                
            elif routing_strategy == "orchestrator_direct":
                # Handle meta commands directly through orchestrator
                meta_request = GameRequest(
                    request_type="meta_command",
                    data={
                        "command": player_input,
                        "context": context,
                        "routing_context": interface_result
                    }
                )
                meta_response = super().process_request(meta_request)
                return meta_response.data if meta_response.success else {
                    "response": f"Meta command '{player_input}' processed.",
                    "processed_by": "orchestrator_meta"
                }
                
            else:
                # Enhanced fallback with routing context
                debug_print("GAMEPLAY", f"🔄 Using enhanced fallback for strategy: {routing_strategy}")
                return {
                    "response": f"You {player_input}. The world responds in unexpected ways.",
                    "processed_by": "enhanced_fallback",
                    "routing_context": interface_result,
                    "confidence": interface_result.get("confidence", 0.5)
                }
                
        except Exception as e:
            debug_print("GAMEPLAY", f"💥 Gameplay pipeline exception: {e}")
            pipeline_logger.error(f"Gameplay turn pipeline failed: {e}")
            return {
                "response": f"You {player_input}. The world responds accordingly.",
                "processed_by": "error_fallback",
                "error": str(e),
                "debug_trace": traceback.format_exc()
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
        """Run scenario generation using proper agent invocation"""
        debug_print("SCENARIO", "🎭 Starting scenario generation", data)
        
        try:
            player_action = data.get("player_action", "")
            game_context = data.get("game_context", {})
            debug_print("SCENARIO", f"📝 Extracted data", {"action": player_action, "context_keys": list(game_context.keys()) if game_context else []})
            
            # Step 1: Normalize incoming data to DTO format
            debug_print("SCENARIO", "🔄 Normalizing incoming data to DTO format")
            request_dto = normalize_incoming({
                "action": player_action,
                "player_input": player_action,
                "context": game_context,
                "type": "scenario"
            })
            debug_print("SCENARIO", "✅ DTO normalization complete", {"dto_keys": list(request_dto.keys()) if request_dto else None})
            
            # Ensure debug field exists for the tool
            if "debug" not in request_dto:
                request_dto["debug"] = {}
            
            # Use the scenario generator agent properly instead of calling tool directly
            scenario_agent = self.agents.get("scenario_generator")
            if not scenario_agent:
                debug_print("SCENARIO", "❌ No scenario generator agent available, using manual fallback")
                return self._create_manual_scenario(player_action, game_context)
            
            debug_print("SCENARIO", "🤖 Found scenario generator agent, invoking...")
            
            try:
                # Create proper message for the scenario agent
                scenario_message = ChatMessage.from_user(f"""
                Player Action: {player_action}
                Game Context: {game_context}
                DTO: {request_dto}
                
                Use the create_scenario_from_dto tool to generate a D&D scenario.
                """)
                
                debug_print("SCENARIO", "📨 Running scenario agent with message")
                # Run the agent properly
                agent_result = scenario_agent.run(messages=[scenario_message])
                debug_print("SCENARIO", "📥 Agent execution complete", {"result_keys": list(agent_result.keys()) if isinstance(agent_result, dict) else type(agent_result)})
                
                # Extract scenario from agent state (using outputs_to_state feature)
                # Add null safety for agent_result
                if agent_result and isinstance(agent_result, dict) and "scenario_result" in agent_result:
                    debug_print("SCENARIO", "✅ Found scenario_result in agent output")
                    scenario_dto = agent_result["scenario_result"]
                    if scenario_dto and isinstance(scenario_dto, dict) and "scenario" in scenario_dto and scenario_dto["scenario"]:
                        debug_print("SCENARIO", "🎯 Valid scenario found in DTO, building response")
                        scenario = scenario_dto["scenario"]
                        result = {
                            "scene": scenario.get("scene", f"You {player_action}. The world responds with intrigue."),
                            "choices": scenario.get("choices", []),
                            "effects": scenario.get("effects", {}),
                            "hooks": scenario.get("hooks", []),
                            "fallback_used": scenario_dto.get("fallback", False),
                            "processing_metadata": {
                                "pipeline_path": "agent_tool_invocation",
                                "agent_used": "scenario_generator",
                                "validation_applied": True
                            }
                        }
                        debug_print("SCENARIO", "✅ Scenario pipeline success", {"scene_length": len(result.get("scene", "")), "choices_count": len(result.get("choices", []))})
                        return result
                    else:
                        debug_print("SCENARIO", "⚠️ No valid scenario in scenario_dto, using manual fallback")
                else:
                    debug_print("SCENARIO", "⚠️ No scenario_result in agent output, using manual fallback")
                
                # Agent succeeded but no scenario in state - use manual fallback
                debug_print("SCENARIO", "🔧 Using manual scenario fallback")
                return self._create_manual_scenario(player_action, game_context)
                    
            except Exception as agent_error:
                debug_print("SCENARIO", f"💥 Agent invocation exception: {agent_error}")
                print(f"⚠️ Agent invocation failed: {agent_error}")
                # Use manual scenario generation as ultimate fallback
                return self._create_manual_scenario(player_action, game_context)
                
        except Exception as e:
            debug_print("SCENARIO", f"💥 Scenario pipeline exception: {e}")
            pipeline_logger.error(f"Scenario pipeline failed: {e}")
            return self._create_manual_scenario(data.get("player_action", "act"), data.get("game_context", {}))
    
    def _create_manual_scenario(self, player_action: str, game_context: Dict[str, Any]) -> Dict[str, Any]:
        """Create a manual scenario when all automated methods fail"""
        location = game_context.get("location", "area")
        
        # Create varied responses based on action keywords
        action_lower = player_action.lower()
        
        if "look" in action_lower or "examine" in action_lower:
            scene = f"You carefully examine your surroundings in the {location}. The details become clearer as you focus your attention."
        elif "talk" in action_lower or "speak" in action_lower:
            scene = f"You engage in conversation, your words carrying weight in this {location}."
        elif "search" in action_lower:
            scene = f"You begin a methodical search of the {location}, looking for anything of interest."
        elif "listen" in action_lower:
            scene = f"You pause and listen carefully to the sounds around you in the {location}."
        else:
            scene = f"You take action in the {location}, and the world responds to your initiative."
            
        return {
            "scene": scene,
            "choices": [
                {
                    "id": "c1",
                    "title": "Continue exploring",
                    "description": "Keep investigating your surroundings",
                    "skill_hints": ["perception"],
                    "suggested_dc": 12,
                    "combat_trigger": False
                }
            ],
            "effects": {},
            "hooks": [],
            "processing_metadata": {
                "pipeline_path": "manual_scenario_generation",
                "reason": "All automated methods failed"
            }
        }
    
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
            
            # Extract formatted context with null safety
            rag_context = ""
            if rag_result and isinstance(rag_result, dict) and "formatted_context" in rag_result:
                formatted_ctx = rag_result["formatted_context"]
                if formatted_ctx and isinstance(formatted_ctx, dict):
                    rag_context = formatted_ctx.get("context", "")
            
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
        debug_print("RAG", "🔍 Starting RAG pipeline", data)
        
        try:
            query = data.get("query", "")
            context_type = data.get("context_type", "general")
            filters = data.get("filters", {})
            debug_print("RAG", f"📋 RAG parameters", {"query": query, "context_type": context_type, "filters": filters})
            
            if not query:
                debug_print("RAG", "❌ No query provided for RAG pipeline")
                return {
                    "error": "No query provided for RAG pipeline",
                    "rag_result": None
                }
            
            # Use RAG retriever agent for document retrieval and formatting
            rag_agent = self.agents.get("rag_retriever")
            if not rag_agent:
                debug_print("RAG", "❌ RAG retriever agent not available")
                return {"error": "RAG retriever agent not available"}
            
            debug_print("RAG", "🤖 Found RAG agent, creating message")
            # Create message for RAG agent
            rag_message = ChatMessage.from_user(f"""
            Query: {query}
            Context Type: {context_type}
            Filters: {filters}
            
            Retrieve relevant documents for this query and format them appropriately.
            """)
            
            debug_print("RAG", "📨 Running RAG agent")
            # Run RAG retrieval
            rag_result = rag_agent.run(messages=[rag_message])
            debug_print("RAG", "📥 RAG agent execution complete", {"result_type": type(rag_result), "result_keys": list(rag_result.keys()) if isinstance(rag_result, dict) else None})
            
            # Extract and format results with null safety
            formatted_context = {}
            if rag_result and isinstance(rag_result, dict) and "formatted_context" in rag_result:
                debug_print("RAG", "✅ Found formatted_context in RAG result")
                formatted_context = rag_result["formatted_context"]
            else:
                debug_print("RAG", "⚠️ No formatted_context in RAG result")
            
            # Build comprehensive response
            response = {
                "query": query,
                "context_type": context_type,
                "rag_context": formatted_context.get("context", "") if formatted_context else "",
                "source_count": formatted_context.get("source_count", 0) if formatted_context else 0,
                "relevance": formatted_context.get("relevance", "none") if formatted_context else "none",
                "processing_metadata": {
                    "pipeline_type": "rag_query",
                    "haystack_pipeline_used": True,
                    "filters_applied": filters,
                    "rag_result_status": "success" if rag_result else "null_result"
                }
            }
            debug_print("RAG", "✅ RAG pipeline success", {"context_length": len(response.get("rag_context", "")), "source_count": response.get("source_count", 0)})
            return response
            
        except Exception as e:
            debug_print("RAG", f"💥 RAG pipeline exception: {e}")
            debug_print("RAG", f"📋 RAG exception traceback: {traceback.format_exc()}")
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
        """Run interface processing with fixed system integration"""
        
        try:
            # Get fixed interface agent
            interface_agent = self.agents.get("main_interface")
            if not interface_agent:
                debug_print("INTERFACE", "❌ Interface agent not available")
                return {"error": "Interface agent not available"}
            
            player_input = data.get("player_input", "")
            game_context = data.get("game_context", {})
            
            debug_print("INTERFACE", f"🎯 Processing input: {player_input}")
            
            # Add world state adapter to context for fixed system
            enhanced_context = game_context.copy()
            enhanced_context["world_state_adapter"] = self.world_state_adapter
            
            # Create message for fixed interface agent
            interface_message = ChatMessage.from_user(f"""
            Player Input: {player_input}
            Game Context: {enhanced_context}
            
            Process this input using execute_deterministic_routing.
            """)
            
            # Run fixed interface agent (single step execution)
            result = interface_agent.run(messages=[interface_message])
            debug_print("INTERFACE", f"📥 Agent result keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")
            
            # Extract routing result from agent state
            if "routing_result" in result:
                routing_result = result["routing_result"]
                debug_print("INTERFACE", f"✅ Got routing result: {routing_result.get('route', 'unknown')}")
                
                if isinstance(routing_result, dict):
                    # Map fixed system route to pipeline routing strategy
                    route = routing_result.get('route', 'scenario')
                    route_mapping = {
                        "scenario": "scenario_pipeline",
                        "npc": "npc_pipeline",
                        "rules": "rules_pipeline",
                        "meta": "orchestrator_direct"
                    }
                    routing_strategy = route_mapping.get(route, "scenario_pipeline")
                    
                    # Enhanced routing decision with fixed system data
                    enhanced_result = routing_result.copy()
                    enhanced_result['routing_strategy'] = routing_strategy
                    enhanced_result['fixed_system_used'] = True
                    
                    return enhanced_result
            
            # If no routing result, use execute_deterministic_routing_direct
            debug_print("INTERFACE", "⚠️ No routing_result in agent state, using direct execution")
            from main_interface_agent_fixed import execute_deterministic_routing_direct
            routing_result = execute_deterministic_routing_direct(player_input, enhanced_context)
            
            # Map route to strategy
            route = routing_result.get('route', 'scenario')
            route_mapping = {
                "scenario": "scenario_pipeline",
                "npc": "npc_pipeline",
                "rules": "rules_pipeline",
                "meta": "orchestrator_direct"
            }
            routing_result['routing_strategy'] = route_mapping.get(route, "scenario_pipeline")
            routing_result['fixed_system_used'] = True
            
            return routing_result
                
        except Exception as e:
            debug_print("INTERFACE", f"💥 Interface pipeline exception: {e}")
            pipeline_logger.error(f"Fixed interface pipeline failed: {e}")
            
            # Enhanced fallback with graceful degradation
            return {
                "routing_strategy": "scenario_pipeline",
                "route": "scenario",
                "type": "scenario_action",
                "confidence": 0.3,
                "rationale": f"Error fallback - routing to scenario: {str(e)}",
                "fixed_system_used": False,
                "fallback_used": True
            }
    
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