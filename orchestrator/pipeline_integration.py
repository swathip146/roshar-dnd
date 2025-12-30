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

from dataclasses import dataclass
from components.policy import PolicyProfile
from components.game_engine import GameEngine
from agents.scenario_generator_agent import create_scenario_generator_agent, PromptBuilderComponent, ScenarioValidatorComponent
from agents.rag_retriever_agent import create_rag_retriever_agent_simplified, RAGFormatterComponent
from agents.npc_controller_agent import create_npc_controller_agent
from agents.main_interface_agent_fixed import create_fixed_interface_agent
from components.shared_contract import (
    normalize_incoming, new_dto, RequestDTO, GameResponseDTO, RAGBlock, Scenario,
    request_dto_from_game_request, game_response_from_dto,
    new_response_dto, merge_dto_updates,
    convert_rag_response_to_ragblock, convert_scenario_response_to_scenario,
    create_unified_game_response
)
from adapters.world_state_adapter import WorldStateAdapter, MockWorldStateAdapter
from config.llm_config import (
    create_gemini_config,
    LLMConfigManager,
    set_global_config_manager,
    get_global_config_manager
)
from config.logging_config import get_logger

# Initialize logger
logger = get_logger(__name__)


# DEBUG CONTROL - Set to True to enable detailed debugging
DEBUG_PIPELINE = True
DEBUG_AGENTS = True
DEBUG_REQUESTS = True
DEBUG_RESPONSES = True

def debug_print(category: str, message: str, data: Any = None):
    """Centralized debug printing with categories"""
    if DEBUG_PIPELINE:
        timestamp = time.strftime('%H:%M:%S')
        logger.debug(f"🐛 [{timestamp}] {category}: {message}")
        if data is not None and (DEBUG_REQUESTS or DEBUG_RESPONSES):
            if isinstance(data, dict) and len(str(data)) > 200:
                logger.debug(f"    📊 Data keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
            else:
                logger.debug(f"    📊 Data: {data}")

# Simple logging for errors only
pipeline_logger = logging.getLogger("PipelineOrchestrator")
pipeline_logger.setLevel(logging.WARNING)

class PipelineOrchestrator:
    """
    Enhanced orchestrator with Haystack pipeline integration
    Extends existing orchestrator while adding pipeline capabilities
    """
    
    def __init__(self, policy_profile: PolicyProfile = PolicyProfile.RAW,
                 enable_stage3: bool = True, enable_pipelines: bool = True,
                 collection_name: Optional[str] = None,
                 shared_document_store: Optional[Any] = None,
                 game_engine: Optional[Any] = None,
                 character_manager: Optional[Any] = None,
                 session_manager: Optional[Any] = None,
                 policy_engine: Optional[Any] = None):
        
        self.logger = logging.getLogger(__name__)
        self.enable_stage3 = enable_stage3
        
        # Use provided components directly (no inheritance, no fresh component creation!)
        self.game_engine = game_engine
        self.character_manager = character_manager
        self.session_manager = session_manager
        self.policy_engine = policy_engine
        
        # Pipeline-specific initialization
        self.enable_pipelines = enable_pipelines
        self.collection_name = collection_name
        self.shared_document_store = shared_document_store
        
        # Initialize pipeline infrastructure
        self.pipelines: Dict[str, Pipeline] = {}
        self.agents: Dict[str, Any] = {}
        self.world_state_adapter: Optional[WorldStateAdapter] = None
        
        if enable_pipelines:
            self._initialize_pipeline_infrastructure()
        
        logger.info(f"🔄 Enhanced Pipeline Orchestrator initialized (pipelines: {'enabled' if enable_pipelines else 'disabled'})")
        logger.debug(f"   📊 Components available: GameEngine={bool(self.game_engine)}, CharacterManager={bool(self.character_manager)}, SessionManager={bool(self.session_manager)}, PolicyEngine={bool(self.policy_engine)}")
    
    def _initialize_pipeline_infrastructure(self) -> None:
        """Initialize Haystack agents and LLM configuration with Gemini integration"""
        logger.debug("🔧 Starting pipeline infrastructure initialization...")
        try:
            # Create Gemini configuration
            debug_print("ORCHESTRATOR", "🤖 Creating Gemini configuration...")
            logger.debug("🔧 Step 1: Creating Gemini configuration...")
            gemini_config = create_gemini_config()
            debug_print("ORCHESTRATOR", "✅ Gemini config created")
            print("✅ Step 1 complete: Gemini config created")
            
            debug_print("ORCHESTRATOR", "🔧 Creating LLM config manager...")
            logger.debug("🔧 Step 2: Creating LLM config manager...")
            global_manager = LLMConfigManager(gemini_config)
            debug_print("ORCHESTRATOR", "✅ LLM config manager created")
            print("✅ Step 2 complete: LLM config manager created")
            
            debug_print("ORCHESTRATOR", "🌐 Setting global config manager...")
            logger.debug("🔧 Step 3: Setting global config manager...")
            set_global_config_manager(global_manager)
            debug_print("ORCHESTRATOR", "✅ Global config manager set")
            print("✅ Step 3 complete: Global config manager set")
            
            # Create routing context adapter for fixed system integration - ENHANCED: Add CampaignConfig authority
            if hasattr(self, 'game_engine') and self.game_engine:
                # Get CampaignConfig from GameEngine if available
                campaign_config = getattr(self.game_engine, 'campaign_config', None)
                
                if campaign_config:
                    self.world_state_adapter = WorldStateAdapter(campaign_config, self.game_engine, self.character_manager)
                    debug_print("ORCHESTRATOR", "✅ Created enhanced RoutingContextAdapter with CampaignConfig, GameEngine and CharacterManager")
                else:
                    # Fallback: Create without CampaignConfig (will work with partial data)
                    self.world_state_adapter = WorldStateAdapter(None, self.game_engine, self.character_manager)
                    debug_print("ORCHESTRATOR", "⚠️ Created RoutingContextAdapter without CampaignConfig (partial functionality)")
            else:
                self.world_state_adapter = MockWorldStateAdapter()
                debug_print("ORCHESTRATOR", "⚠️ Created MockRoutingContextAdapter (no components)")
            
            # Initialize agents - use fixed interface agent for improved performance
            logger.debug("🔧 Step 4: Creating scenario generator agent...")
            scenario_agent = create_scenario_generator_agent()
            print("✅ Step 4 complete: Scenario generator agent created")
            
            logger.debug("🔧 Step 5: Creating RAG retriever agent...")
            rag_agent = create_rag_retriever_agent_simplified(
                document_store=self.shared_document_store
            )
            debug_print("ORCHESTRATOR", "✅ RAG retriever agent created")
            print("✅ Step 5 complete: RAG retriever agent created")
            
            debug_print("ORCHESTRATOR", "🎭 Creating NPC controller agent...")
            logger.debug("🔧 Step 6: Creating NPC controller agent...")
            npc_agent = create_npc_controller_agent()
            debug_print("ORCHESTRATOR", "✅ NPC controller agent created")
            print("✅ Step 6 complete: NPC controller agent created")
            
            # Use the new fixed interface agent
            debug_print("ORCHESTRATOR", "🔧 Creating fixed interface agent...")
            logger.debug("🔧 Step 7: Creating fixed interface agent...")
            logger.debug(f"   Checking global config manager...")
            config_manager = get_global_config_manager()
            if config_manager is None:
                raise RuntimeError("Global config manager is None - cannot create interface agent")
            logger.debug(f"   Global config manager found: {type(config_manager).__name__}")
            
            logger.debug(f"   Creating generator for main_interface...")
            try:
                generator = config_manager.create_generator("main_interface")
                logger.debug(f"   Generator created: {type(generator).__name__}")
            except Exception as gen_error:
                logger.debug(f"   ❌ Generator creation failed: {type(gen_error).__name__}: {gen_error}")
                import traceback
                traceback.print_exc()
                raise
            
            logger.debug(f"   Creating interface agent...")
            interface_agent = create_fixed_interface_agent()
            debug_print("ORCHESTRATOR", "✅ Created fixed interface agent")
            print("✅ Step 7 complete: Fixed interface agent created")
            
            logger.debug("🔧 Step 8: Storing agents in agents dict...")
            self.agents = {
                "scenario_generator": scenario_agent,
                "rag_retriever": rag_agent,
                "npc_controller": npc_agent,
                "main_interface": interface_agent  # Fixed system agent
            }
            logger.info(f"✅ Step 8 complete: Agents stored. Keys: {list(self.agents.keys())}")
            
            if self.shared_document_store:
                logger.info(f"📚 Pipeline Orchestrator: Using shared document store for '{self.shared_document_store.collection_name}'")
            else:
                logger.warning("Pipeline Orchestrator: No shared document store provided - RAG will use fallback responses")
            
            # Initialize pipelines
            logger.debug("🔧 Step 9: Creating pipelines...")
            self._create_pipelines()
            print("✅ Step 9 complete: Pipelines created")
            print("✅ Pipeline infrastructure initialization complete!")
            
        except Exception as e:
            pipeline_logger.error(f"Failed to initialize pipeline infrastructure: {e}")
            logger.error(f"Pipeline initialization error: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Error details:")
            import traceback
            traceback.print_exc()
            print(f"\n❌ Pipeline initialization FAILED - this must be fixed before continuing")
            logger.error(f"Available agents so far: {list(self.agents.keys())}")
            self.enable_pipelines = False
            # Re-raise to ensure the error is visible and not silently swallowed
            raise RuntimeError(f"Pipeline infrastructure initialization failed: {e}") from e
    
    def _create_pipelines(self) -> None:
        """Create Haystack pipelines with proper component connections"""
        try:
            # RAG Pipeline with proper connections
            rag_pipeline = Pipeline()
            rag_pipeline.add_component("retriever_agent", create_rag_retriever_agent_simplified(document_store=self.shared_document_store))
            rag_pipeline.add_component("formatter", RAGFormatterComponent())
            
            # Connect: Agent messages → Formatter messages input
            rag_pipeline.connect("retriever_agent.messages", "formatter.messages")
            self.pipelines["rag_retriever"] = rag_pipeline
            debug_print("PIPELINES", "✅ Created connected RAG pipeline")
            
            # Scenario Pipeline with proper connections
            scenario_pipeline = Pipeline()
            scenario_pipeline.add_component("prompt_builder", PromptBuilderComponent())
            scenario_pipeline.add_component("scenario_agent", create_scenario_generator_agent())
            scenario_pipeline.add_component("validator", ScenarioValidatorComponent())
            
            # Connect: DTO → Prompt Builder → Agent → Validator
            scenario_pipeline.connect("prompt_builder.messages", "scenario_agent.messages")
            scenario_pipeline.connect("scenario_agent.messages", "validator.messages")
            self.pipelines["scenario_generation"] = scenario_pipeline
            debug_print("PIPELINES", "✅ Created connected Scenario pipeline")
            
            # NPC Interaction Pipeline (keep existing structure)
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
            debug_print("PIPELINES", "✅ Created NPC pipeline")
            
            # Interface Processing Pipeline (keep existing structure)
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
            debug_print("PIPELINES", "✅ Created Interface pipeline")
            
            debug_print("PIPELINES", f"🔗 All pipelines created with proper connections: {list(self.pipelines.keys())}")
            
        except Exception as e:
            pipeline_logger.error(f"Failed to create connected pipelines: {e}")
            raise
    
    def process_request(self, dto: RequestDTO) -> GameResponseDTO:
        """
        Enhanced request processing with DTO-based pipeline integration
        Processes DTOs directly through appropriate pipelines
        """
        try:
            # Process DTO through appropriate pipeline
            debug_print("PIPELINE", "🔄 Starting DTO pipeline processing", {"dto_type": dto.get("type"), "correlation_id": dto.get("correlation_id")})
            
            dto_type = dto.get("type", "scenario")
            route = dto.get("route")
            correlation_id = dto.get("correlation_id")
            debug_print("PIPELINE", f"🎯 DTO routing", {"type": dto_type, "route": route, "correlation_id": correlation_id})
            
            # Route based on DTO type or explicit route
            if route == "rag_pipeline" or dto_type == "rag_query":
                debug_print("PIPELINE", "🔍 Routing to RAG pipeline")
                pipeline_result = self._run_rag_pipeline(dto)
            elif route == "npc_pipeline" or dto_type == "npc_interaction":
                debug_print("PIPELINE", "👥 Routing to NPC pipeline")
                pipeline_result = self._run_npc_pipeline(dto)
            elif route in ["scenario_pipeline", "scenario_with_rag_pipeline"] or dto_type == "scenario":
                if route == "scenario_with_rag_pipeline" or (dto.get("rag", {}).get("needed", False)):
                    debug_print("PIPELINE", "📚 Routing to RAG-enhanced scenario pipeline")
                    pipeline_result = self._run_rag_enhanced_scenario_pipeline(dto)
                else:
                    debug_print("PIPELINE", "📖 Routing to scenario pipeline")
                    pipeline_result = self._run_scenario_pipeline(dto)
            elif dto_type == "gameplay_turn":
                debug_print("PIPELINE", "🎮 Routing to gameplay turn pipeline")
                pipeline_result = self._handle_gameplay_turn_pipeline_dto(dto)
            else:
                debug_print("PIPELINE", f"🎮 Routing to gameplay turn pipeline (default)")
                pipeline_result = self._handle_gameplay_turn_pipeline_dto(dto)
            
            debug_print("PROCESS", "📥 Pipeline processing complete", {"result_keys": list(pipeline_result.keys()) if isinstance(pipeline_result, dict) else type(pipeline_result)})
            
            return pipeline_result
                
        except Exception as e:
            debug_print("PIPELINE", f"💥 Pipeline processing exception: {e}")
            debug_print("PIPELINE", f"📋 Exception traceback: {traceback.format_exc()}")
            pipeline_logger.error(f"Pipeline orchestrator error: {e}")
            
            # Extract correlation_id for error response
            correlation_id = dto.get("correlation_id") if isinstance(dto, dict) else None
            
            return create_unified_game_response(
                response_type="error",
                success=False,
                correlation_id=correlation_id,
                metadata={"error_source": "process_request_exception"},
                error=str(e)
            )
    
    def _handle_gameplay_turn_pipeline_dto(self, dto: RequestDTO) -> Dict[str, Any]:
        """Handle full gameplay turn using DTO format"""
        player_input = dto.get("player_input", "")
        context = dto.get("context", {})
        
        debug_print("GAMEPLAY", f"🎮 Starting gameplay turn with DTO", {"input": player_input, "dto_type": dto.get("type")})
        
        try:
            # Step 1: Check if we need interface processing or already have routing info
            route = dto.get("route")
            if not route:
                # Process through interface agent to get routing decision
                interface_dto = self._run_interface_pipeline(dto)
                route = interface_dto["route"]
            
            debug_print("GAMEPLAY", f"🎯 Using route: {route}")
            
            # Step 2: Route based on decision
            if route == "scenario_pipeline":
                return self._run_scenario_pipeline(interface_dto)
            elif route == "scenario_with_rag_pipeline":
                return self._run_rag_enhanced_scenario_pipeline(interface_dto)
            elif route == "npc_pipeline":
                return self._run_npc_pipeline(interface_dto)
            elif route == "rag_pipeline":
                return self._run_rag_pipeline(interface_dto)
            else:
                raise Exception("💥 Gameplay DTO pipeline exception")
                
        except Exception as e:
            debug_print("GAMEPLAY", f"💥 Gameplay DTO pipeline exception: {e}")
            return create_unified_game_response(
                response_type="error",
                error=f"Gameplay DTO pipeline exception: {e}"
            )

    def _run_interface_pipeline(self, dto: RequestDTO) -> RequestDTO:
        """Run interface processing with fixed system integration"""
        
        try:
            # Get fixed interface agent
            interface_agent = self.agents.get("main_interface")
            if not interface_agent:
                error_msg = f"Interface agent not available. Available agents: {list(self.agents.keys())}"
                debug_print("INTERFACE", f"❌ {error_msg}")
                logger.error(f"{error_msg}")
                logger.error(f"Agents dict keys: {list(self.agents.keys())}")
                logger.error(f"Agents dict: {self.agents}")
                logger.error(f"Pipeline enabled: {self.enable_pipelines}")
                raise RuntimeError(f"Interface agent not initialized: {error_msg}")
            
            # Extract data from DTO using correct field names
            player_input = dto.get("player_input", "")
            
            # DTO COMPLIANCE: Get game context from GameEngine directly, not from DTO
            game_context = {}
            game_engine = dto.get("_game_engine_ref")
            game_context = game_engine.get_narrative_context().get("current_scene","")
            quest_context = game_engine.get_quest_context().get("active_quests","")
            
            debug_print("INTERFACE", f"🎯 Processing input: {player_input}")
            
            # Create message for fixed interface agent with two-step process
            interface_message = ChatMessage.from_user(f"""
            Analyze this player input and game context to classify player intent using the two-step workflow:
            
            Player Input: "{player_input}"
            Game Context: "{game_context}"
            Quest Context: "{quest_context}"
            
            STEP 1: Call record_intent_analysis with your analysis parameters
            STEP 2: Call classify_player_intent with the player_input
            
            Follow the examples in the system prompt.
            """)
            
            # Run fixed interface agent with state values as direct kwargs
            response = interface_agent.run(
                messages=[interface_message],
                intent_data={},
                interface_result={}
            )
            
            # Extract the RequestDTO from the interface agent response
            interface_dto = response.get("interface_result") or {}
            result_dto = merge_dto_updates(dto,interface_dto)
            route = result_dto.get("route", "scenario_pipeline")
            
            debug_print("INTERFACE", f"📥 Agent DTO keys: {list(result_dto.keys()) if isinstance(result_dto, dict) else type(result_dto)}")
            debug_print("INTERFACE", f"✅ Got routing result: {route}")
            
            # Return the complete interface DTO directly - much cleaner!
            debug_print("INTERFACE", f"📦 Interface DTO keys: {list(result_dto.keys())}")
            
            return result_dto
                
        except Exception as e:
            debug_print("INTERFACE", f"💥 Interface pipeline exception: {e}")
            pipeline_logger.error(f"Fixed interface pipeline failed: {e}")
            # Return original DTO with error info
            error_dto = dto.copy()
            error_dto["error"] = f"Interface pipeline failed: {e}"
            return error_dto

    def _run_scenario_pipeline(self, dto: RequestDTO) -> GameResponseDTO:
        """Run connected scenario pipeline with standardized response format"""
        
        debug_print("SCENARIO", "🎭 Starting connected scenario generation pipeline")
        
        try:
            
            # Step 2: Use connected scenario pipeline
            scenario_pipeline = self.pipelines.get("scenario_generation")
            if not scenario_pipeline:
                debug_print("SCENARIO", "❌ Connected scenario pipeline not available")
                return create_unified_game_response(
                    response_type="error",
                    error="Connected scenario pipeline not available"
                )
            
            debug_print("SCENARIO", "🔗 Running connected scenario pipeline")
            
            # Run connected pipeline with proper inputs
            pipeline_result = scenario_pipeline.run({
                "prompt_builder": {"dto": dto}
            })
            
            debug_print("SCENARIO", "📥 Connected pipeline execution complete", {"result_keys": list(pipeline_result.keys()) if isinstance(pipeline_result, dict) else None})
            
            # Extract final validated scenario from pipeline
            validated_scenario = {}
            if pipeline_result and "validator" in pipeline_result:
                validator_output = pipeline_result["validator"]
                if "validated_scenario" in validator_output:
                    validated_scenario = validator_output["validated_scenario"]
            
            # Process validated scenario
            if validated_scenario and "scenario" in validated_scenario:
                scenario_data = validated_scenario["scenario"]
                
                # # BREAKING CHANGE: Update GameEngine directly (SessionManager is persistence-only)
                # if self.game_engine and scenario_data.get("state_changes"):
                #     try:
                #         if hasattr(self.game_engine, 'update_narrative_context'):
                #             self.game_engine.update_narrative_context(scenario_data["state_changes"])
                #     except Exception as e:
                #         debug_print("SCENARIO", f"⚠️ Failed to update game narrative: {e}")
                
                # Convert agent response to Scenario format using standardized converter
                scenario = convert_scenario_response_to_scenario(scenario_data)
                
                # Return standardized response format
                return create_unified_game_response(
                    response_type= "scenario",
                    scenario = scenario,
                    metadata={
                        "pipeline_type": "connected_scenario_generation",
                        "pipeline_architecture": "connected_prompt_builder_plus_agent_plus_validator"
                    }
                )
            
            # Fallback if no validated scenario
            return create_unified_game_response(
                response_type="error",
                error="No validated scenario found"
            )
            
        except Exception as e:
            debug_print("SCENARIO", f"💥 Connected scenario pipeline exception: {e}")
            return create_unified_game_response(
                response_type="error",
                error=f"Connected scenario pipeline exception: {e}"
            )
     
    def _run_rag_enhanced_scenario_pipeline(self, dto: RequestDTO) -> GameResponseDTO:
        """Handle RAG-enhanced scenario generation with RAGBlock parameter passing"""
        debug_print("RAG_SCENARIO", "📚 Starting RAG-enhanced scenario generation")
        
        try:
            
            # Step 2: Get RAG information first using RAG pipeline
            rag_info = dto.get("rag", {})
            rag_type = rag_info.get("category", "general")
            query = rag_info.get("query", dto.get("player_input", ""))
            
            # Run RAG pipeline to get standardized RAGBlock
            rag_pipeline = self._run_rag_pipeline(dto)
            rag_pipeline_result = rag_pipeline.get("rag_result")
            
            debug_print("RAG_RETRIVAL", "📥 RAG retrieval pipeline execution complete", {"result_keys": list(rag_pipeline_result.keys()) if isinstance(rag_pipeline_result, dict) else None})
            
            # formatted_response = rag_pipeline_result.get("rag_result").get("formatted_response","")
            dto["rag"]["response"] = rag_pipeline_result.get("response","")
            dto["rag"]["confidence"] = rag_pipeline_result.get("confidence",0)

            # Step 3: Use connected scenario pipeline with RAGBlock parameter
            scenario_pipeline = self.pipelines.get("scenario_generation")
            if not scenario_pipeline:
                debug_print("RAG_SCENARIO", "❌ Connected scenario pipeline not available")
                return create_unified_game_response(
                    response_type="error",
                    error="Connected scenario pipeline not available for RAG-enhanced scenario"
                )
            
            debug_print("RAG_SCENARIO", "🔗 Running connected scenario pipeline with RAGBlock")
            
            # Run connected pipeline
            pipeline_result = scenario_pipeline.run({
                "prompt_builder": {
                    "dto": dto
                }
            })
            
            debug_print("RAG_SCENARIO", "📥 Connected pipeline execution complete", {"result_keys": list(pipeline_result.keys()) if isinstance(pipeline_result, dict) else None})
            
            # Extract final validated scenario from pipeline
            validated_scenario = {}
            if pipeline_result and "validator" in pipeline_result:
                validator_output = pipeline_result["validator"]
                if "validated_scenario" in validator_output:
                    validated_scenario = validator_output["validated_scenario"]
            
            # Process validated scenario
            if validated_scenario and "scenario" in validated_scenario:
                scenario_data = validated_scenario["scenario"]
                
                # # BREAKING CHANGE: Update GameEngine directly (SessionManager is persistence-only)
                # if self.game_engine and scenario_data.get("state_changes"):
                #     try:
                #         if hasattr(self.game_engine, 'update_narrative_context'):
                #             self.game_engine.update_narrative_context(scenario_data["state_changes"])
                #     except Exception as e:
                #         debug_print("RAG_SCENARIO", f"⚠️ Failed to update game narrative: {e}")
                
                # Convert scenario response to standardized format
                scenario = convert_scenario_response_to_scenario(scenario_data)
                
                return create_unified_game_response(
                    response_type= "scenario",
                    scenario = scenario,
                    metadata={
                        "pipeline_type": "rag_enhanced_scenario_generation",
                        "rag_type": rag_type,
                        "query_used": query,
                        "haystack_pipeline_used": True,
                        "validation_applied": True
                    }
                )
            
        except Exception as e:
            debug_print("RAG_SCENARIO", f"💥 RAG-enhanced scenario pipeline exception: {e}")
            pipeline_logger.error(f"RAG-enhanced scenario pipeline failed: {e}")
            return create_unified_game_response(
                response_type="error",
                error=f"RAG-enhanced scenario pipeline exception: {e}"
            )
    def _run_rag_pipeline(self, dto: RequestDTO) -> GameResponseDTO:
        """Run connected RAG query pipeline with standardized response format"""
        debug_print("RAG", "🔍 Starting connected RAG pipeline")
        
        try:
            # Extract parameters directly from DTO
            rag_info = dto.get("rag", {})
            query = rag_info.get("query", dto.get("player_input", ""))
            context_type = rag_info.get("category", "general")
            filters = rag_info.get("filters", {})
            
            debug_print("RAG", f"📋 RAG parameters", {"query": query, "context_type": context_type, "filters": filters})

            # Use connected RAG pipeline
            rag_pipeline = self.pipelines.get("rag_retriever")
            
            debug_print("RAG", "🔗 Running connected RAG pipeline")
            
            # Run connected pipeline with proper inputs
            pipeline_result = rag_pipeline.run({
                "retriever_agent": {
                    "messages": [ChatMessage.from_user(f"Query: {query}, Context Type: {context_type}, Filters: {filters}")],
                    "context_type": context_type,
                    "filters": filters
                }
            })
            
            debug_print("RAG", "📥 Connected pipeline execution complete", {"result_keys": list(pipeline_result.keys()) if isinstance(pipeline_result, dict) else None})
            
            # Extract final formatted result from pipeline
            formatted_response = pipeline_result.get("formatter").get("formatted_response","")
            dto["rag"]["response"] = formatted_response.get("response","")
            dto["rag"]["confidence"] = formatted_response.get("confidence",0)
            rag_block = dto.get("rag")
            
            return create_unified_game_response(
                response_type="rag_query",
                rag_result=rag_block,
                metadata={
                    "pipeline_type": "connected_rag_query",
                    "haystack_components_used": True,
                    "pipeline_architecture": "connected_agent_plus_components",
                    "filters_applied": filters
                }
            )
            
        except Exception as e:
            debug_print("RAG", f"💥 Connected RAG pipeline exception: {e}")
            debug_print("RAG", f"📋 Exception traceback: {traceback.format_exc()}")
            pipeline_logger.error(f"Connected RAG pipeline failed: {e}")
    
    def _run_npc_pipeline(self, dto: RequestDTO) -> Dict[str, Any]:
        """Run NPC interaction pipeline"""
        pipeline = self.pipelines.get("npc_interaction")
        if not pipeline:
            return {"error": "NPC pipeline not available"}
        
        try:
            # Extract parameters directly from DTO
            npc_id = dto.get("target", "unknown_npc")
            player_action = dto.get("player_input", "")
            npc_context = dto.get("context", {}).get("npc_data", {})
            
            result = pipeline.run({
                "npc_id": npc_id,
                "player_action": player_action,
                "npc_context": npc_context,
                "interface_context": dto  # Pass DTO for additional context
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

    def _create_enhanced_manual_scenario(self, dto: RequestDTO) -> Dict[str, Any]:
        """Create enhanced manual scenario using available context"""
        player_action = dto.get("player_input", "act")
        
        # Use enhanced context if available
        party_context = dto.get("party_context", {})
        location_context = dto.get("location_context", {})
        policy_context = dto.get("policy_context", {})
        
        # Determine location from enhanced context
        location = location_context.get("current_location", dto.get("context", {}).get("location", "area"))
        
        # Get difficulty policy if available
        difficulty_policy = policy_context.get("difficulty_policy", {})
        choice_policy = policy_context.get("choice_policy", {})
        
        # Use policy-driven DCs if available
        dc_policy = difficulty_policy.get("dc_policy", {"easy": 8, "medium": 12, "hard": 16})
        choice_count = choice_policy.get("choice_count", 3)
        
        # Create varied responses based on action keywords and context
        action_lower = player_action.lower()
        
        # Factor in party context for scene description
        party_size = party_context.get("party_size", 1)
        avg_level = party_context.get("avg_level", 3)
        
        if "look" in action_lower or "examine" in action_lower:
            scene = f"You carefully examine your surroundings in the {location}. The details become clearer as you focus your attention."
            if party_size > 1:
                scene += f" Your party of {party_size} spreads out to get different perspectives."
        elif "talk" in action_lower or "speak" in action_lower:
            scene = f"You engage in conversation, your words carrying weight in this {location}."
            if party_size > 1:
                scene += f" Your companions listen carefully, ready to support your approach."
        elif "search" in action_lower:
            scene = f"You begin a methodical search of the {location}, looking for anything of interest."
            if party_context.get("stealth_profile") == "good":
                scene += " Your party's stealth expertise helps you search without drawing attention."
        elif "listen" in action_lower:
            scene = f"You pause and listen carefully to the sounds around you in the {location}."
        else:
            scene = f"You take action in the {location}, and the world responds to your initiative."
            if avg_level >= 5:
                scene += " Your experience guides your approach."
        
        # Create policy-aware choices
        choices = []
        for i in range(choice_count):
            if i == 0:
                choices.append({
                    "id": f"c{i+1}",
                    "title": "Continue exploring",
                    "description": "Keep investigating your surroundings",
                    "skill_hints": ["perception"],
                    "suggested_dc": dc_policy.get("easy", 8),
                    "combat_trigger": False
                })
            elif i == 1:
                choices.append({
                    "id": f"c{i+1}",
                    "title": "Be cautious",
                    "description": "Proceed carefully and watch for danger",
                    "skill_hints": ["insight", "stealth"],
                    "suggested_dc": dc_policy.get("medium", 12),
                    "combat_trigger": False
                })
            elif i == 2:
                choices.append({
                    "id": f"c{i+1}",
                    "title": "Take direct action",
                    "description": "Address the situation head-on",
                    "skill_hints": ["athletics", "intimidation"],
                    "suggested_dc": dc_policy.get("medium", 12),
                    "combat_trigger": False
                })
            else:
                choices.append({
                    "id": f"c{i+1}",
                    "title": f"Alternative approach {i-2}",
                    "description": "Try a different strategy",
                    "skill_hints": ["investigation"],
                    "suggested_dc": dc_policy.get("hard", 16),
                    "combat_trigger": False
                })
        
        return {
            "scene": scene,
            "choices": choices,
            "effects": {},
            "hooks": [],
            "processing_metadata": {
                "pipeline_path": "enhanced_manual_scenario_generation",
                "reason": "Enhanced manual fallback with available context",
                "context_used": {
                    "party_context": bool(party_context),
                    "location_context": bool(location_context),
                    "policy_context": bool(policy_context)
                },
                "policy_profile": policy_context.get("active_profile", "fallback")
            }
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
        
        # Add basic orchestrator status
        if self.enable_stage3 and self.policy_engine:
            try:
                status.update({
                    "stage3_enabled": self.enable_stage3,
                    "policy_profile": self.policy_engine.active_profile_type.value if hasattr(self.policy_engine, 'active_profile_type') else "unknown",
                    "game_characters": len(self.game_engine.game_state.characters) if self.game_engine and hasattr(self.game_engine, 'game_state') else 0
                })
            except Exception as e:
                pipeline_logger.warning(f"Could not get enhanced orchestrator status: {e}")
        
        return status

def create_full_haystack_orchestrator(collection_name: Optional[str] = None,
                                     shared_document_store: Optional[Any] = None,
                                     game_engine: Optional[Any] = None,
                                     character_manager: Optional[Any] = None,
                                     session_manager: Optional[Any] = None,
                                     policy_engine: Optional[Any] = None) -> PipelineOrchestrator:
    """Create enhanced orchestrator with comprehensive game component integration"""
    return PipelineOrchestrator(
        policy_profile=PolicyProfile.HOUSE,  # Use house rules for enhanced experience
        enable_stage3=True,
        enable_pipelines=True,
        collection_name=collection_name,
        shared_document_store=shared_document_store,
        game_engine=game_engine,
        character_manager=character_manager,
        session_manager=session_manager,
        policy_engine=policy_engine
    )

# Example usage and testing
def main() -> None:
    """Main function for testing the pipeline orchestrator"""
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("=== Pipeline Orchestrator Test ===")
    
if __name__ == "__main__":
    main()