"""
Shared D&D Orchestrator Data Contract (DTO)
Single source of truth for data shapes passed between all components
Enhanced for Fixed System Integration
"""

from typing import TypedDict, Literal, Optional, List, Dict, Any
import uuid
import time

# TypedDict definitions for Dict fields with defined structures

class ScenarioEffects(TypedDict, total=False):
    """Allowed keys for scenario effects"""
    # Flexible dict for scenario effects - various effect types allowed
    pass  # Keep flexible as effects can be highly variable

class ScenarioStateChanges(TypedDict, total=False):
    """Allowed keys for scenario state changes"""
    location: str
    flags: Dict[str, Any]
    story_hooks: List[str]
    quest_objectives: List[str]
    environment_updates: Dict[str, Any]
    character_updates: Dict[str, Any]

class RAGFilters(TypedDict, total=False):
    """Allowed keys for RAG filters"""
    type: str                    # "lore", "rules", "monsters", etc.
    relevance: str              # "high", "medium", "low"
    category: str               # Filter category
    source: str                 # Source filter
    difficulty: str             # Difficulty filter
    tags: List[str]             # Tag filters

class DocumentMetadata(TypedDict, total=False):
    """Structure for individual RAG document"""
    id: str
    title: str
    content: str
    score: float
    source: str
    category: str
    metadata: Dict[str, Any]

class RequestArguments(TypedDict, total=False):
    """Allowed keys for request arguments"""
    player_input: str
    action: str
    command: str
    context: Dict[str, Any]
    game_context: Dict[str, Any]
    target: str
    skill: str
    difficulty: str

class DebugInfo(TypedDict, total=False):
    """Allowed keys for debug information"""
    events: List[Dict[str, Any]]           # Debug events with timestamps
    intent: Dict[str, Any]                 # Intent analysis debug info
    rag_attempted: bool                    # RAG processing flag
    rag_error: str                         # RAG error message
    scenario_repaired: bool                # Scenario repair flag
    scenario_errors: List[str]             # Scenario validation errors
    scenario_generation_error: str         # Scenario generation error
    dto_debug: Dict[str, Any]              # Additional DTO debug info

class ResponseMetadata(TypedDict, total=False):
    """Allowed keys for response metadata"""
    dto_type: str
    route: str
    confidence: float
    processed_by: str
    processing_metadata: Dict[str, Any]
    correlation_id: str
    original_input: str
    request_type: str
    routing_info: Dict[str, Any]
    rag_info: Dict[str, Any]
    error_source: str

class NPCResponse(TypedDict, total=False):
    """Allowed keys for NPC response"""
    npc_id: str
    npc_name: str
    response_text: str
    mood: str
    relationship_change: int
    conversation_state: str
    available_topics: List[str]
    quest_updates: List[str]

class Choice(TypedDict, total=False):
    """
    IMPORTANT: Only the keys defined here are allowed.
    No additional keys should be used without updating this definition.
    """
    id: str
    title: str
    description: str
    skill_hints: List[str]
    suggested_dc: int
    combat_trigger: bool

class Scenario(TypedDict, total=False):
    """
    IMPORTANT: Only the keys defined here are allowed.
    No additional keys should be used without updating this definition.
    """
    scene: str
    choices: List[Choice]
    effects: ScenarioEffects                    # Structured effects
    hooks: List[str]
    
    # Additional fields from agent output
    gm_notes: Optional[str]
    state_changes: Optional[ScenarioStateChanges]  # Structured state changes
    difficulty_used: Optional[Dict[str, Any]]      # Keep flexible for difficulty info
    confidence: Optional[float]
    fallback: Optional[bool]

class RAGBlock(TypedDict, total=False):
    """
    IMPORTANT: Only the keys defined here are allowed.
    No additional keys should be used without updating this definition.
    """
    needed: bool
    query: str
    filters: RAGFilters                        # Structured filters
    docs: List[DocumentMetadata]               # Structured document list
    confidence: float
    category: str
    reasoning: str
    response: str
    rag_context: str

class RequestDTO(TypedDict, total=False):
    """
    Streamlined request DTO preserving interface analysis, eliminating state duplication
    
    IMPORTANT: Only the keys defined here are allowed.
    No additional keys should be used without updating this definition.
    """
    
    # === CORE REQUEST IDENTIFICATION ===
    correlation_id: str                      # Unique request identifier
    ts: float                               # Request timestamp
    type: str                               # Request type: "scenario", "rag_query", "npc_interaction", gameplay_turn
    player_input: str                       # Original user input/command
    
    # === INTERFACE AGENT ANALYSIS RESULTS (PRESERVE) ===
    action: str                             # Extracted intent from main_interface_agent
    target: Optional[str]                   # Identified target from main_interface_agent
    arguments: RequestArguments             # Structured parameters from main_interface_agent
    route: Optional[str]                    # Pipeline routing decision from main_interface_agent
    confidence: float                       # Interface analysis confidence from main_interface_agent
    rationale: Optional[str]                # Interface analysis reasoning from main_interface_agent
    
    # === PROCESSING COORDINATION ===
    rag: RAGBlock                           # Document retrieval coordination
    saga_id: Optional[str]                  # Multi-turn saga identifier
    fallback: bool                          # Use fallback processing if true
    debug: DebugInfo                        # Debug flags and information
    
    # === ENGINE REFERENCES (NEW - replaces context duplication) ===
    _game_engine_ref: Optional[Any]         # GameEngine reference for direct access
    _policy_engine_ref: Optional[Any]       # PolicyEngine reference for direct access
    _dnd_engine_wrapper_ref: Optional[Any]  # PHASE 2: dnd_engine wrapper for skill checks/combat

    # === LEGACY COMPATIBILITY ===
    context: Dict[str, Any]                 # Legacy context field (keep flexible for compatibility)
    
class GameResponseDTO(TypedDict, total=False):
    """
    IMPORTANT: Only the keys defined here are allowed.
    No additional keys should be used without updating this definition.
    """
    success: bool
    correlation_id: Optional[str]
    metadata: Optional[ResponseMetadata]    # Structured metadata
    error: Optional[str]
    
    # Unified response data fields
    response_type: str  # "scenario", "rag_query", "npc_interaction"
    
    # Type-specific response data
    scenario: Optional[Scenario]           # For scenario responses
    rag_result: Optional[RAGBlock]        # For RAG responses
    npc_response: Optional[NPCResponse]   # For NPC responses (structured)

def new_dto(player_input: str, ctx: Dict[str, Any]) -> RequestDTO:
    """Create a new streamlined DTO with default values - DTO COMPLIANCE"""
    return {
        # === CORE REQUEST IDENTIFICATION ===
        "correlation_id": str(uuid.uuid4()),
        "ts": time.time(),
        "type": "",                 # "rag_query", "npc_interaction", "scenario", "gameplay_turn"
        "player_input": player_input,
        
        # === INTERFACE AGENT ANALYSIS RESULTS (PRESERVE) ===
        "action": "",
        "target": None,
        "arguments": {},
        "route": None,
        "confidence": 0.0,
        "rationale": "",
        
        # === PROCESSING COORDINATION ===
        "rag": {
            "needed": False,
            "query": "",
            "filters": {},
            "docs": [],
            "confidence": 0.0,
            "category": "none",
            "reasoning": "",
            "response": "",
            "rag_context": ""
        },
        "saga_id": None,
        "fallback": False,
        "debug": {},
        
        # === ENGINE REFERENCES (NEW - replaces context duplication) ===
        "_game_engine_ref": None,
        "_policy_engine_ref": None,
        
        # === LEGACY COMPATIBILITY ===
        "context": ctx or {},
        
        # === REMOVED FIELDS - NO LONGER POPULATED ===
        # All enhanced context fields and response fields removed
    }

def new_response_dto(success: bool = True, correlation_id: str = None,
                    metadata: Dict[str, Any] = None, error: str = None,
                    response_type: str = "unknown", scenario: Optional[Scenario] = None,
                    rag_result: Optional[RAGBlock] = None,
                    npc_response: Optional[Dict[str, Any]] = None) -> GameResponseDTO:
    """Create a new response DTO with default values"""
    return {
        "success": success,
        "correlation_id": correlation_id,
        "metadata": metadata or {},
        "error": error,
        "response_type": response_type,
        "scenario": scenario,
        "rag_result": rag_result,
        "npc_response": npc_response
    }

def request_dto_from_game_request(game_request, context: Dict[str, Any] = None) -> RequestDTO:
    """Convert GameRequest-like object to RequestDTO format"""
    if hasattr(game_request, 'request_type'):
        # Handle actual GameRequest object
        request_type = game_request.request_type
        arguments = getattr(game_request, 'arguments', {}) or {}
        context = context or getattr(game_request, 'context', {}) or {}
        correlation_id = getattr(game_request, 'correlation_id', None)
        saga_id = getattr(game_request, 'saga_id', None)
    else:
        # Handle dict-like object
        request_type = game_request.get('request_type', 'scenario')
        arguments = game_request.get('arguments', {}) or {}
        context = context or game_request.get('context', {}) or {}
        correlation_id = game_request.get('correlation_id')
        saga_id = game_request.get('saga_id')
    
    # Extract player input from various possible fields
    player_input = ""
    if "player_input" in arguments:
        player_input = arguments["player_input"]
    elif "action" in arguments:
        player_input = arguments["action"]
    elif "command" in arguments:
        player_input = arguments["command"]
    
    # Create DTO using new_dto function
    dto = new_dto(player_input, context)
    
    # Map request type to DTO type
    if request_type == "gameplay_turn":
        dto["type"] = "scenario"
    elif request_type == "scenario_generation":
        dto["type"] = "scenario"
    elif request_type == "npc_interaction":
        dto["type"] = "npc_interaction"
    elif request_type == "rag_query":
        dto["type"] = "rag_query"
    else:
        dto["type"] = "scenario"
    
    # Set only valid RequestDTO fields for compatibility
    dto["correlation_id"] = correlation_id or dto["correlation_id"]
    dto["saga_id"] = saga_id
    dto["arguments"] = arguments
    
    return dto

def game_response_from_dto(dto: RequestDTO, pipeline_result: Dict[str, Any] = None) -> GameResponseDTO:
    """Convert RequestDTO and pipeline result to GameResponseDTO format"""
    pipeline_result = pipeline_result or {}
    
    # Handle error cases
    if "error" in pipeline_result:
        return new_response_dto(
            success=False,
            correlation_id=dto.get("correlation_id"),
            metadata={
                "dto_type": dto.get("type"),
                "error_source": "pipeline_processing"
            },
            error=pipeline_result["error"],
            response_type=dto.get("type", "unknown")
        )
    
    # Extract key information from DTO for metadata
    metadata = {
        "dto_type": dto.get("type"),
        "route": dto.get("route"),
        "confidence": dto.get("confidence", 0.0),
        "processed_by": pipeline_result.get("processed_by", "pipeline"),
        "processing_metadata": pipeline_result.get("processing_metadata", {}),
        "correlation_id": dto.get("correlation_id"),
        "original_input": dto.get("player_input", ""),
        "request_type": dto.get("type", "unknown"),
        "routing_info": {
            "route": dto.get("route"),
            "confidence": dto.get("confidence", 0.0),
            "rationale": dto.get("rationale", "")
        }
    }
    
    # Add DTO debug information if available
    if "debug" in dto and dto["debug"]:
        metadata["dto_debug"] = dto["debug"]
    
    # Add RAG information if available
    if "rag" in dto and dto["rag"]:
        rag_info = dto["rag"]
        if rag_info.get("needed", False):
            metadata["rag_info"] = {
                "category": rag_info.get("category", ""),
                "query": rag_info.get("query", ""),
                "confidence": rag_info.get("confidence", 0.0)
            }
    
    # Determine response type and extract type-specific data
    request_type = dto.get("type", "unknown")
    
    # Initialize response components
    scenario = None
    rag_result = None
    npc_response = None
    
    if request_type == "scenario" and "scenario" in pipeline_result:
        scenario = pipeline_result["scenario"]
    elif request_type == "rag_query" and "rag_result" in pipeline_result:
        rag_result = pipeline_result["rag_result"]
    elif request_type == "npc_interaction" and "npc_response" in pipeline_result:
        npc_response = pipeline_result["npc_response"]
    
    return new_response_dto(
        success=True,
        correlation_id=dto.get("correlation_id"),
        metadata=metadata,
        response_type=request_type,
        scenario=scenario,
        rag_result=rag_result,
        npc_response=npc_response
    )

def dto_to_dict(dto: RequestDTO) -> Dict[str, Any]:
    """Convert RequestDTO to regular Dict for Haystack pipeline compatibility"""
    return dict(dto)


def normalize_incoming(raw_request: Dict[str, Any]) -> RequestDTO:
    """Normalize raw incoming request to DTO format"""
    
    # Extract player input from various possible fields
    player_input = ""
    if "player_input" in raw_request:
        player_input = raw_request["player_input"]
    elif "action" in raw_request:
        player_input = raw_request["action"]
    elif "arguments" in raw_request and isinstance(raw_request["arguments"], dict):
        arguments = raw_request["arguments"]
        if "player_input" in arguments:
            player_input = arguments["player_input"]
        elif "action" in arguments:
            player_input = arguments["action"]
    
    # Extract context from various possible locations
    context = {}
    if "context" in raw_request:
        context = raw_request["context"] or {}
    elif "arguments" in raw_request and isinstance(raw_request["arguments"], dict):
        if "context" in raw_request["arguments"]:
            context = raw_request["arguments"]["context"] or {}
        elif "game_context" in raw_request["arguments"]:
            context = raw_request["arguments"]["game_context"] or {}
    
    # Extract type information
    request_type = "scenario"  # default
    if "type" in raw_request:
        type_val = raw_request["type"]
        if type_val in ["scenario", "npc_interaction", "rules_lookup"]:
            request_type = type_val
    elif "request_type" in raw_request:
        type_val = raw_request["request_type"]
        if type_val == "scenario_generation" or type_val == "scenario":
            request_type = "scenario"
        elif type_val == "npc_interaction":
            request_type = "npc_interaction"
        elif type_val == "rules_lookup":
            request_type = "rules_lookup"
    
    # Create normalized DTO
    dto = new_dto(player_input, context)
    dto["type"] = request_type
    dto["action"] = player_input  # Set action same as player_input for compatibility
    
    # Copy over correlation_id if provided
    if "correlation_id" in raw_request:
        dto["correlation_id"] = raw_request["correlation_id"]
    
    return dto

# Validation functions
REQUIRED_SCENARIO_KEYS = ["scene", "choices", "effects", "hooks"]

def validate_scenario(s: Dict[str, Any]) -> List[str]:
    """Validate scenario structure and return list of errors"""
    errs = []
    for k in REQUIRED_SCENARIO_KEYS:
        if k not in s:
            errs.append(f"missing {k}")
    
    if isinstance(s.get("choices"), list):
        for i, ch in enumerate(s["choices"]):
            for k in ("id", "title", "description", "skill_hints", "suggested_dc", "combat_trigger"):
                if k not in ch:
                    errs.append(f"choices[{i}] missing {k}")
    else:
        errs.append("choices must be a list")
    
    return errs

def repair_scenario(s: Dict[str, Any], errs: List[str]) -> Dict[str, Any]:
    """Deterministic repair of scenario structure"""
    s.setdefault("scene", "You are in a nondescript chamber.")
    s.setdefault("choices", [])
    s.setdefault("effects", {})
    s.setdefault("hooks", [])
    
    # Ensure choices is a list
    if not isinstance(s["choices"], list):
        s["choices"] = []
    
    # Repair each choice
    for i, ch in enumerate(s["choices"]):
        if not isinstance(ch, dict):
            s["choices"][i] = ch = {}
        ch.setdefault("id", f"c{i+1}")
        ch.setdefault("title", "Decide")
        ch.setdefault("description", "")
        ch.setdefault("skill_hints", [])
        ch.setdefault("suggested_dc", 12)
        ch.setdefault("combat_trigger", False)
    
    # Ensure at least one choice exists
    if not s["choices"]:
        s["choices"] = [{
            "id": "c1",
            "title": "Continue",
            "description": "Proceed with your adventure",
            "skill_hints": [],
            "suggested_dc": 12,
            "combat_trigger": False
        }]
    
    return s

def minimal_fallback(dto: RequestDTO) -> Scenario:
    """Create minimal fallback scenario"""
    return {
        "scene": f"You {dto['player_input']}. The world responds in unexpected ways.",
        "choices": [{
            "id": "c1",
            "title": "Continue",
            "description": "Proceed with your adventure",
            "skill_hints": [],
            "suggested_dc": 12,
            "combat_trigger": False
        }],
        "effects": {},
        "hooks": []
    }

def merge_dto_updates(original_dto: RequestDTO, updated_dto: RequestDTO) -> RequestDTO:
    """
    Generic DTO merge function that intelligently updates original DTO with new meaningful values
    
    Args:
        original_dto: The base DTO to preserve
        updated_dto: The DTO with potential updates
        
    Returns:
        Merged DTO with meaningful updates applied
    """
    # Start with original DTO to preserve all existing data
    result_dto = original_dto.copy()
    
    # Go through all fields in updated DTO and check for meaningful updates
    for field, new_value in updated_dto.items():
        original_value = result_dto.get(field)
        
        # Determine if we should update based on field type and content
        should_update = False
        
        if field.startswith("_"):
            # Preserve engine references and private fields from original
            continue
        elif new_value is None:
            # Don't update with None values unless original was also None
            continue
        elif isinstance(new_value, str):
            # Update if new string is non-empty and different
            should_update = new_value.strip() and new_value != original_value
        elif isinstance(new_value, (int, float)):
            # Update if new number is meaningful (> 0 for confidence, or different)
            if field == "confidence":
                should_update = new_value > 0 and new_value != original_value
            else:
                should_update = new_value != original_value
        elif isinstance(new_value, bool):
            # Update if boolean value changed
            should_update = new_value != original_value
        elif isinstance(new_value, dict):
            # Special handling for dict fields
            if field == "rag":
                # Merge RAG block intelligently
                original_rag = result_dto.get("rag", {})
                merged_rag = original_rag.copy()
                
                for rag_field, rag_value in new_value.items():
                    original_rag_value = merged_rag.get(rag_field)
                    
                    if rag_field == "needed":
                        # Always update boolean
                        merged_rag[rag_field] = rag_value
                    elif rag_field == "confidence":
                        # Update if > 0
                        if isinstance(rag_value, (int, float)) and rag_value > 0:
                            merged_rag[rag_field] = rag_value
                    elif isinstance(rag_value, str):
                        # Update if non-empty string
                        if rag_value.strip():
                            merged_rag[rag_field] = rag_value
                    elif isinstance(rag_value, (dict, list)):
                        # Update if has content
                        if rag_value:
                            merged_rag[rag_field] = rag_value
                    else:
                        # Update other types if different
                        if rag_value != original_rag_value:
                            merged_rag[rag_field] = rag_value
                
                result_dto["rag"] = merged_rag
                continue
            elif field == "debug":
                # Merge debug info
                original_debug = result_dto.get("debug", {})
                merged_debug = original_debug.copy()
                merged_debug.update(new_value)
                result_dto["debug"] = merged_debug
                continue
            elif field == "arguments" or field == "context":
                # Update if new dict has content
                should_update = bool(new_value) and new_value != original_value
            else:
                # Other dicts - update if different and has content
                should_update = bool(new_value) and new_value != original_value
        elif isinstance(new_value, list):
            # Update if new list has content and is different
            should_update = bool(new_value) and new_value != original_value
        else:
            # For other types, update if different
            should_update = new_value != original_value
        
        # Apply the update if determined to be meaningful
        if should_update:
            result_dto[field] = new_value
    
    return result_dto

# Response Format Standardization Converter Functions

def convert_rag_response_to_ragblock(agent_response: Dict[str, Any]) -> RAGBlock:
    """Convert RAG agent response to standardized RAGBlock format"""
    return {
        "needed": True,  # If we're converting, RAG was needed
        "query": agent_response.get("query", ""),
        "filters": agent_response.get("filters", {}),
        "docs": agent_response.get("documents", []),
        "confidence": agent_response.get("confidence", 0.0),
        "category": agent_response.get("context_type", "general"),
        "reasoning": f"Retrieved {len(agent_response.get('documents', []))} documents",
        "response": agent_response.get("rag_context", ""),
        "rag_context": agent_response.get("rag_context", "")
    }

def convert_scenario_response_to_scenario(agent_response: Dict[str, Any]) -> Scenario:
    """Convert scenario agent response to standardized Scenario format"""
    return {
        "scene": agent_response.get("scene", ""),
        "choices": agent_response.get("choices", []),
        "effects": agent_response.get("effects", {}),
        "hooks": agent_response.get("hooks", []),
        "gm_notes": agent_response.get("gm_notes"),
        "state_changes": agent_response.get("state_changes"),
        "difficulty_used": agent_response.get("difficulty_used"),
        "confidence": agent_response.get("confidence"),
        "fallback": agent_response.get("fallback")
    }

def create_unified_game_response(
    response_type: str,
    scenario: Optional[Scenario] = None,
    rag_result: Optional[RAGBlock] = None,
    npc_response: Optional[Dict[str, Any]] = None,
    success: bool = True,
    correlation_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None
) -> GameResponseDTO:
    """Create unified GameResponseDTO with proper type-specific fields"""
    return {
        "success": success,
        "correlation_id": correlation_id,
        "metadata": metadata or {},
        "error": error,
        "response_type": response_type,
        "scenario": scenario,
        "rag_result": rag_result,
        "npc_response": npc_response
    }