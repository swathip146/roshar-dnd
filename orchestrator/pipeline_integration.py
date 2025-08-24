"""
Pipeline Integration for Orchestrator
Connects Haystack pipelines with existing orchestrator infrastructure
Enables seamless integration between agents and components
"""

from typing import Dict, Any, Optional, List
import logging
import os
import time
import traceback
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
from shared_contract import RequestDTO, normalize_incoming, validate_scenario

# Debug configuration for pipeline orchestrator
PIPELINE_DEBUG_MODE = os.getenv("PIPELINE_DEBUG", "False").lower() in ("true", "1", "yes")
# PIPELINE_DEBUG_MODE = True  # Debug mode disabled - RAG routing fixed

if PIPELINE_DEBUG_MODE:
    pipeline_logger = logging.getLogger("PipelineOrchestrator")
    pipeline_logger.setLevel(logging.DEBUG)
    
    # Create file handler for pipeline debug logs
    if not pipeline_logger.handlers:
        handler = logging.FileHandler('pipeline_orchestrator_debug.log', mode='a')
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
        )
        handler.setFormatter(formatter)
        pipeline_logger.addHandler(handler)
else:
    pipeline_logger = logging.getLogger("PipelineOrchestrator")
    pipeline_logger.setLevel(logging.WARNING)


class PipelineOrchestrator(SimpleOrchestrator):
    """
    Enhanced orchestrator with Haystack pipeline integration
    Extends existing orchestrator while adding pipeline capabilities
    """
    
    def __init__(self, policy_profile=PolicyProfile.RAW, enable_stage3=True, enable_pipelines=True, debug_mode=None, collection_name=None):
        self.debug_mode = debug_mode if debug_mode is not None else PIPELINE_DEBUG_MODE
        
        pipeline_logger.info(f"🔄 Initializing Pipeline Orchestrator (debug: {self.debug_mode})...")
        init_start_time = time.time()
        
        super().__init__(policy_profile, enable_stage3)
        
        self.enable_pipelines = enable_pipelines
        self.logger = pipeline_logger
        self.collection_name = collection_name  # Store collection name for agent creation
        
        # Track initialization metrics
        self.initialization_metrics = {
            "start_time": init_start_time,
            "pipeline_creation_time": None,
            "agent_creation_time": None,
            "total_init_time": None
        }
        
        # Initialize pipeline infrastructure
        self.pipelines: Dict[str, Pipeline] = {}
        self.agents: Dict[str, Any] = {}
        self.context_broker: Optional[ContextBroker] = None
        
        if enable_pipelines:
            pipeline_logger.info("Starting pipeline infrastructure initialization")
            self._initialize_pipeline_infrastructure()
            self._register_pipeline_handlers()
        else:
            pipeline_logger.warning("Pipelines disabled - running in compatibility mode")
            
        total_init_time = time.time() - init_start_time
        self.initialization_metrics["total_init_time"] = total_init_time
        
        pipeline_logger.info(f"Pipeline Orchestrator initialization completed in {total_init_time:.2f}s")
        print(f"🔄 Pipeline Orchestrator initialized (pipelines: {'enabled' if enable_pipelines else 'disabled'})")
        
        if self.debug_mode:
            print(f"🐛 Pipeline Debug mode: ENABLED (logs: pipeline_orchestrator_debug.log)")
    
    def _initialize_pipeline_infrastructure(self):
        """Initialize Haystack agents and context broker"""
        
        pipeline_logger.debug("Starting pipeline infrastructure initialization")
        
        try:
            # CRITICAL: Initialize global LLM configuration manager BEFORE creating agents
            pipeline_logger.debug("Setting up global LLM configuration...")
            from config.llm_config import create_apple_genai_config, LLMConfigManager, set_global_config_manager
            
            try:
                # Try to create Apple GenAI configuration
                apple_config = create_apple_genai_config()
                global_manager = LLMConfigManager(apple_config)
                set_global_config_manager(global_manager)
                pipeline_logger.info("✅ Global LLM config set to Apple GenAI")
                
                # Log the configuration for debugging
                config_summary = global_manager.get_config_summary()
                for agent, config in config_summary.items():
                    if not agent.endswith('_available'):
                        pipeline_logger.debug(f"  {agent}: {config}")
                        
            except Exception as config_e:
                pipeline_logger.warning(f"Failed to setup Apple GenAI config: {config_e}")
                pipeline_logger.info("Falling back to default LLM configuration")
                # Let get_global_config_manager() handle the fallback
                
            # Initialize context broker
            broker_start = time.time()
            pipeline_logger.debug("Creating context broker...")
            self.context_broker = ContextBroker()
            broker_time = time.time() - broker_start
            pipeline_logger.debug(f"Context broker created in {broker_time:.2f}s")
            
            # Initialize agents
            agent_start = time.time()
            pipeline_logger.debug("Creating agents...")
            
            agent_creation_times = {}
            
            pipeline_logger.debug("Creating scenario generator agent...")
            scenario_start = time.time()
            scenario_agent = create_scenario_generator_agent()
            agent_creation_times["scenario_generator"] = time.time() - scenario_start
            
            pipeline_logger.debug("Creating RAG retriever agent...")
            rag_start = time.time()
            rag_agent = create_rag_retriever_agent(collection_name=self.collection_name)
            agent_creation_times["rag_retriever"] = time.time() - rag_start
            
            # Log collection name status
            if self.collection_name:
                pipeline_logger.info(f"✅ RAG agent configured with collection: {self.collection_name}")
            else:
                pipeline_logger.warning("⚠️ RAG agent created without collection name (fallback mode)")
            
            pipeline_logger.debug("Creating NPC controller agent...")
            npc_start = time.time()
            npc_agent = create_npc_controller_agent()
            agent_creation_times["npc_controller"] = time.time() - npc_start
            
            pipeline_logger.debug("Creating main interface agent...")
            interface_start = time.time()
            interface_agent = create_main_interface_agent()
            agent_creation_times["main_interface"] = time.time() - interface_start
            
            self.agents = {
                "scenario_generator": scenario_agent,
                "rag_retriever": rag_agent,
                "npc_controller": npc_agent,
                "main_interface": interface_agent
            }
            
            total_agent_time = time.time() - agent_start
            self.initialization_metrics["agent_creation_time"] = total_agent_time
            pipeline_logger.info(f"All agents created in {total_agent_time:.2f}s")
            
            if self.debug_mode:
                for agent_name, creation_time in agent_creation_times.items():
                    pipeline_logger.debug(f"  {agent_name}: {creation_time:.2f}s")
            
            # Initialize pipelines
            pipeline_start = time.time()
            self._create_pipelines()
            pipeline_time = time.time() - pipeline_start
            self.initialization_metrics["pipeline_creation_time"] = pipeline_time
            pipeline_logger.info(f"Pipelines created in {pipeline_time:.2f}s")
            
            pipeline_logger.info("Pipeline infrastructure initialized successfully")
            
        except Exception as e:
            pipeline_logger.error(f"Failed to initialize pipeline infrastructure: {e}")
            pipeline_logger.error(f"Full traceback: {traceback.format_exc()}")
            self.enable_pipelines = False
            # Still register basic handlers even if pipelines fail
            self._register_fallback_handlers()
    
    def _create_pipelines(self):
        """Create Haystack pipelines for different request types"""
        
        pipeline_logger.debug("Creating Haystack pipelines...")
        
        try:
            # Scenario Generation Pipeline - Simplified approach without complex connections
            pipeline_logger.debug("Creating scenario generation pipeline...")
            scenario_pipeline = Pipeline()
            
            # Add RAG retriever component
            scenario_pipeline.add_component("rag_retriever", self.agents["rag_retriever"])
            
            # Add scenario generator component
            scenario_pipeline.add_component("scenario_generator", self.agents["scenario_generator"])
            
            self.pipelines["scenario_generation"] = scenario_pipeline
            pipeline_logger.debug("Scenario generation pipeline created with direct agent integration")
            
            # NPC Interaction Pipeline
            pipeline_logger.debug("Creating NPC interaction pipeline...")
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
            pipeline_logger.debug("NPC interaction pipeline created")
            
            # Interface Processing Pipeline
            pipeline_logger.debug("Creating interface processing pipeline...")
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
            pipeline_logger.debug("Interface processing pipeline created")
            
            pipeline_logger.info(f"Created {len(self.pipelines)} Haystack pipelines successfully")
            
        except Exception as e:
            pipeline_logger.error(f"Failed to create pipelines: {e}")
            pipeline_logger.error(f"Full traceback: {traceback.format_exc()}")
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
        
        request_start_time = time.time()
        pipeline_logger.debug(f"Processing request: {type(request).__name__}")
        
        try:
            # Defensive programming - handle None request
            if request is None:
                pipeline_logger.error("Received None request in pipeline orchestrator")
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
                pipeline_logger.debug(f"Converted GameRequest: {request.request_type}")
            else:
                request_dict = request.copy() if request is not None else {}
                pipeline_logger.debug(f"Using dict request: {request_dict.get('type', 'unknown')}")
            
            # Context enrichment if pipelines are enabled
            enrichment_time = 0
            if self.enable_pipelines and self.context_broker and request_dict is not None:
                enrichment_start = time.time()
                pipeline_logger.debug("Starting context enrichment")
                enriched_request_dict = self.context_broker.enrich_context(request_dict)
                enrichment_time = time.time() - enrichment_start
                
                # Only update if enrichment was successful
                if enriched_request_dict is not None:
                    request_dict = enriched_request_dict
                    pipeline_logger.debug(f"Context enriched in {enrichment_time:.3f}s")
                else:
                    pipeline_logger.warning("Context enrichment returned None")
            
            # Determine processing path
            use_pipeline = self._should_use_pipeline(request_dict)
            pipeline_logger.debug(f"Pipeline decision: use_pipeline={use_pipeline}")
            
            if use_pipeline:
                result = self._process_with_pipeline(request_dict)
            else:
                # Use existing orchestrator processing
                pipeline_logger.debug("Using base orchestrator processing")
                result = super().process_request(request)
            
            total_time = time.time() - request_start_time
            pipeline_logger.info(f"Request processed in {total_time:.3f}s (enrichment: {enrichment_time:.3f}s)")
            return result
                
        except Exception as e:
            pipeline_logger.error(f"Pipeline orchestrator error: {e}")
            pipeline_logger.error(f"Full traceback: {traceback.format_exc()}")
            # Fallback to base orchestrator
            pipeline_logger.debug("Falling back to base orchestrator")
            return super().process_request(request)
    
    def _should_use_pipeline(self, request: Dict[str, Any]) -> bool:
        """Determine if request should use pipeline processing"""
        
        if not self.enable_pipelines or request is None:
            pipeline_logger.debug("Pipeline processing disabled or None request")
            return False
            
        request_type = request.get("type", request.get("request_type", ""))
        pipeline_logger.debug(f"Evaluating pipeline use for request type: {request_type}")
        
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
            pipeline_logger.debug("Explicit pipeline request detected")
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
        
        decision = type_match or complexity_match
        
        pipeline_logger.debug(f"Pipeline decision factors:")
        pipeline_logger.debug(f"  - Type match ({request_type}): {type_match}")
        pipeline_logger.debug(f"  - RAG context: {rag_context_present}")
        pipeline_logger.debug(f"  - Data size: {data_size}")
        pipeline_logger.debug(f"  - Complex context: {context_complex}")
        pipeline_logger.debug(f"  - Final decision: {decision}")
        
        return decision
    
    def _process_with_pipeline(self, request: Dict[str, Any]) -> GameResponse:
        """Process request using appropriate Haystack pipeline"""
        
        pipeline_start_time = time.time()
        
        # Defensive programming - handle None request
        if request is None:
            pipeline_logger.error("None request in pipeline processing")
            return GameResponse(
                success=False,
                data={"error": "None request in pipeline processing"},
                correlation_id=None
            )
        
        request_type = request.get("type", request.get("request_type", ""))
        correlation_id = request.get("correlation_id")
        
        pipeline_logger.info(f"Processing with pipeline: {request_type}")
        
        try:
            # Route to appropriate pipeline
            if request_type == "gameplay_turn":
                pipeline_logger.debug("Routing to gameplay turn pipeline")
                result = self._handle_gameplay_turn_pipeline(request)
            elif request_type == "scenario_generation" or request_type == "scenario":
                pipeline_logger.debug("Routing to scenario pipeline")
                result = self._handle_scenario_pipeline(request)
            elif request_type == "npc_interaction":
                pipeline_logger.debug("Routing to NPC pipeline")
                result = self._handle_npc_pipeline(request)
            elif request_type == "interface_processing":
                pipeline_logger.debug("Routing to interface pipeline")
                result = self._handle_interface_pipeline(request)
            elif request_type == "rag_query":
                pipeline_logger.debug("Routing to RAG pipeline")
                result = self._handle_rag_pipeline(request)
            else:
                pipeline_logger.debug(f"Unknown pipeline type {request_type}, falling back to base orchestrator")
                # Fallback to base orchestrator
                return super().process_request(request)
            
            pipeline_time = time.time() - pipeline_start_time
            pipeline_logger.info(f"Pipeline processing completed in {pipeline_time:.3f}s")
            
            return GameResponse(
                success=True,
                data=result,
                correlation_id=correlation_id,
                metadata={
                    "processed_by": "pipeline",
                    "pipeline_type": request_type,
                    "processing_time": pipeline_time
                }
            )
            
        except Exception as e:
            pipeline_logger.error(f"Pipeline processing failed: {e}")
            pipeline_logger.error(f"Request type: {type(request)}")
            pipeline_logger.error(f"Request content: {request}")
            pipeline_logger.error(f"Full traceback: {traceback.format_exc()}")
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
        
        pipeline_logger.debug(f"Interface pipeline result: {interface_result}")
        pipeline_logger.debug(f"Interface result keys: {list(interface_result.keys()) if isinstance(interface_result, dict) else 'Not a dict'}")
        
        # Step 2: Determine routing based on interface analysis
        routing = interface_result.get("routing_strategy", "simple_response")
        pipeline_logger.debug(f"Extracted routing strategy: {routing}")
        
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
        """Run scenario generation pipeline with DTO-based RAG flow"""
        
        pipeline_logger.debug("Running DTO-based scenario generation pipeline")
        pipeline_start = time.time()
        
        try:
            player_action = data.get("player_action", "")
            game_context = data.get("game_context", {})
            
            pipeline_logger.debug(f"Processing player_action: '{player_action[:50]}...'")
            
            # Step 1: Normalize incoming data to DTO format
            request_dto = normalize_incoming({
                "action": player_action,
                "player_input": player_action,
                "context": game_context,
                "type": "scenario"
            })
            
            pipeline_logger.debug(f"Normalized to DTO: {request_dto}")
            
            # Step 2: Use context broker for enhanced RAG assessment
            rag_assessment = self.context_broker._assess_rag_need(request_dto) if self.context_broker else {"needed": False}
            pipeline_logger.debug(f"RAG assessment: {rag_assessment}")
            
            rag_context = ""
            rag_blocks = []
            
            if rag_assessment.get("needed", False):
                # Step 3: Get contextual filters from context broker
                filters = self.context_broker._build_rag_filters(request_dto, rag_assessment.get("type", "lore"))
                pipeline_logger.debug(f"Built RAG filters: {filters}")
                
                # Step 4: Enhanced RAG retrieval with filters
                rag_agent = self.agents["rag_retriever"]
                rag_query = rag_assessment.get("query", f"Player action: {player_action}. Retrieve relevant D&D lore and context.")
                
                pipeline_logger.debug("Step 4: Running enhanced RAG retrieval with filters")
                rag_result = rag_agent.run(messages=[ChatMessage.from_user(rag_query)])
                
                # Extract RAG context from agent response
                if 'last_message' in rag_result:
                    last_msg = rag_result['last_message']
                    if hasattr(last_msg, '_content') and last_msg._content:
                        for content in last_msg._content:
                            if hasattr(content, 'result'):
                                try:
                                    import json
                                    import ast
                                    # Try multiple parsing approaches for robustness
                                    tool_result = None
                                    
                                    # First try: direct JSON parsing
                                    try:
                                        tool_result = json.loads(content.result)
                                    except json.JSONDecodeError:
                                        pass
                                    
                                    # Second try: AST literal_eval for Python dict strings
                                    if tool_result is None:
                                        try:
                                            tool_result = ast.literal_eval(content.result)
                                        except (ValueError, SyntaxError):
                                            pass
                                    
                                    # Third try: crude string replacement (fallback)
                                    if tool_result is None:
                                        try:
                                            tool_result = json.loads(content.result.replace("'", '"'))
                                        except json.JSONDecodeError:
                                            pipeline_logger.warning(f"Could not parse tool result as JSON: {content.result[:100]}...")
                                            continue
                                    
                                    if tool_result and 'context' in tool_result:
                                        rag_context = tool_result['context']
                                        pipeline_logger.debug(f"Extracted RAG context: {len(rag_context)} characters")
                                        
                                        # Create RAG blocks for DTO
                                        rag_blocks = [{
                                            "content": rag_context,
                                            "source": tool_result.get("source", "unknown"),
                                            "relevance": tool_result.get("relevance", "medium"),
                                            "context_type": rag_assessment.get("type", "lore")
                                        }]
                                        break
                                except Exception as e:
                                    pipeline_logger.warning(f"Failed to parse RAG result: {e}")
            
            # Step 5: Build enhanced DTO for scenario generation
            scenario_dto = {
                "action": player_action,
                "context": game_context,
                "rag_blocks": rag_blocks,
                "rag_enhanced": bool(rag_blocks),
                "filters_applied": filters if rag_assessment.get("needed") else {}
            }
            
            # Step 6: Generate scenario using scenario generator with enhanced context
            scenario_agent = self.agents["scenario_generator"]
            scenario_prompt = f"""
            Player Action: {player_action}
            Game Context: {str(game_context) if isinstance(game_context, dict) else game_context}
            RAG Enhanced: {bool(rag_blocks)}
            RAG Retrieved Context: {rag_context}
            Context Filters Applied: {scenario_dto.get('filters_applied', {})}
            
            Generate a detailed D&D scenario response using the retrieved context to enhance the narrative.
            Incorporate the lore and information from the retrieved context into the response.
            Create a structured response with choices and consequences.
            """
            
            pipeline_logger.debug("Step 6: Running scenario generation with DTO-enhanced context")
            scenario_result = scenario_agent.run(messages=[ChatMessage.from_user(scenario_prompt)])
            
            # Extract and validate scenario response
            scenario_text = ""
            if hasattr(scenario_result, 'get') and 'messages' in scenario_result:
                messages = scenario_result['messages']
                for msg in reversed(messages):  # Check from most recent
                    if hasattr(msg, '_content') and msg._content:
                        for content in msg._content:
                            if hasattr(content, 'text') and content.text:
                                scenario_text = content.text
                                break
                        if scenario_text:
                            break
            
            # Build final response with DTO structure
            response = {
                "scene": scenario_text or f"You {player_action}. The world responds with mysterious energy.",
                "rag_enhanced": bool(rag_blocks),
                "rag_blocks": rag_blocks,
                "filters_applied": scenario_dto.get('filters_applied', {}),
                "processing_metadata": {
                    "rag_assessment": rag_assessment,
                    "dto_normalized": True,
                    "context_broker_used": self.context_broker is not None
                }
            }
            
            pipeline_time = time.time() - pipeline_start
            pipeline_logger.debug(f"DTO-based scenario pipeline completed in {pipeline_time:.3f}s")
            
            return response
                
        except Exception as e:
            pipeline_logger.error(f"DTO-based scenario pipeline failed: {e}")
            pipeline_logger.error(f"Full traceback: {traceback.format_exc()}")
            return {"error": f"DTO-based scenario pipeline failed: {e}"}
    
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
            pipeline_logger.error("Interface pipeline not available")
            return {"error": "Interface pipeline not available"}
        
        try:
            pipeline_logger.debug(f"Running interface pipeline with: player_input='{data.get('player_input', '')[:50]}...', game_context={data.get('game_context', {})}")
            
            result = pipeline.run({
                "player_input": data.get("player_input", ""),
                "game_context": data.get("game_context", {})
            })
            
            pipeline_logger.debug(f"Interface pipeline raw result keys: {list(result.keys())}")
            
            if "interface_agent" in result:
                agent_result = result["interface_agent"]
                pipeline_logger.debug(f"Interface agent result type: {type(agent_result)}")
                pipeline_logger.debug(f"Interface agent result: {agent_result}")
                
                # Extract routing information from agent response
                # The agent returns messages with tool call results in last_message
                if 'last_message' in agent_result:
                    last_msg = agent_result['last_message']
                    if hasattr(last_msg, '_content') and last_msg._content:
                        for content in last_msg._content:
                            if hasattr(content, 'result'):
                                try:
                                    # Parse the tool result with robust approach
                                    import json
                                    import ast
                                    tool_result = None
                                    
                                    # First try: direct JSON parsing
                                    try:
                                        tool_result = json.loads(content.result)
                                    except json.JSONDecodeError:
                                        pass
                                    
                                    # Second try: AST literal_eval for Python dict strings
                                    if tool_result is None:
                                        try:
                                            tool_result = ast.literal_eval(content.result)
                                        except (ValueError, SyntaxError):
                                            pass
                                    
                                    # Third try: crude string replacement (fallback)
                                    if tool_result is None:
                                        try:
                                            tool_result = json.loads(content.result.replace("'", '"'))
                                        except json.JSONDecodeError:
                                            pipeline_logger.warning(f"Could not parse tool result as JSON: {content.result[:100]}...")
                                            continue
                                    
                                    pipeline_logger.debug(f"Parsed tool result: {tool_result}")
                                    
                                    # Check for routing_strategy first, then route field
                                    routing_strategy = None
                                    if tool_result and 'routing_strategy' in tool_result:
                                        routing_strategy = tool_result['routing_strategy']
                                    elif tool_result and 'route' in tool_result:
                                        # Map agent route to pipeline routing strategy
                                        route = tool_result['route']
                                        route_mapping = {
                                            "scenario": "scenario_pipeline",
                                            "npc": "npc_pipeline",
                                            "rules": "skill_pipeline",
                                            "meta": "orchestrator_direct"
                                        }
                                        routing_strategy = route_mapping.get(route, "simple_response")
                                        tool_result['routing_strategy'] = routing_strategy  # Add for consistency
                                    
                                    if routing_strategy:
                                        pipeline_logger.debug(f"Found routing strategy: {routing_strategy}")
                                        return tool_result  # Return the full parsed result
                                except (json.JSONDecodeError, AttributeError) as e:
                                    pipeline_logger.warning(f"Failed to parse tool result: {e}")
                                    
                # Fallback: look for routing in replies
                if hasattr(agent_result, 'replies') and agent_result.replies:
                    reply_text = agent_result.replies[0].content if hasattr(agent_result.replies[0], 'content') else str(agent_result.replies[0])
                    pipeline_logger.debug(f"Interface agent reply text: {reply_text}")
                    
                    if "scenario_pipeline" in reply_text.lower():
                        return {"routing_strategy": "scenario_pipeline"}
                    elif "npc_pipeline" in reply_text.lower():
                        return {"routing_strategy": "npc_pipeline"}
                    elif "skill_pipeline" in reply_text.lower():
                        return {"routing_strategy": "skill_pipeline"}
                
                pipeline_logger.warning("Could not extract routing strategy, defaulting to simple_response")
                return {"routing_strategy": "simple_response"}
            else:
                pipeline_logger.warning("No interface_agent in pipeline result")
                return {"error": "No interface analysis generated"}
                
        except Exception as e:
            pipeline_logger.error(f"Interface pipeline failed: {e}")
            pipeline_logger.error(f"Full traceback: {traceback.format_exc()}")
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
        
        pipeline_logger.debug("Getting pipeline status")
        
        status = {
            "pipelines_enabled": self.enable_pipelines,
            "available_pipelines": list(self.pipelines.keys()),
            "available_agents": list(self.agents.keys()),
            "context_broker_active": self.context_broker is not None,
            "debug_mode": self.debug_mode
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
        
        pipeline_logger.debug(f"Status compiled: {len(status)} fields")
        return status


# Factory functions for different configurations

def create_pipeline_orchestrator(policy_profile=PolicyProfile.RAW, enable_stage3=True,
                               enable_pipelines=True) -> PipelineOrchestrator:
    """Factory function to create pipeline-integrated orchestrator"""
    return PipelineOrchestrator(policy_profile, enable_stage3, enable_pipelines)

def create_full_haystack_orchestrator(debug_mode=None, collection_name=None) -> PipelineOrchestrator:
    """Create orchestrator with all Haystack features enabled"""
    pipeline_logger.info("Creating full Haystack orchestrator")
    return PipelineOrchestrator(
        policy_profile=PolicyProfile.HOUSE,  # Use house rules for enhanced experience
        enable_stage3=True,
        enable_pipelines=True,
        debug_mode=debug_mode,
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