"""
Shared D&D Orchestrator Data Contract (DTO)
Single source of truth for data shapes passed between all components
"""

from typing import TypedDict, Literal, Optional, List, Dict, Any
import uuid
import time

RoleType = Literal["scenario", "npc_interaction", "rules_lookup", "meta"]

class Choice(TypedDict, total=False):
    id: str
    title: str
    description: str
    skill_hints: List[str]
    suggested_dc: int
    combat_trigger: bool

class Scenario(TypedDict, total=False):
    scene: str
    choices: List[Choice]
    effects: Dict[str, Any]
    hooks: List[str]

class RAGBlock(TypedDict, total=False):
    needed: bool
    query: str
    filters: Dict[str, Any]
    docs: List[Dict[str, Any]]

class RequestDTO(TypedDict, total=False):
    correlation_id: str
    ts: float
    type: RoleType
    player_input: str
    action: str
    target: Optional[str]
    context: Dict[str, Any]
    rag: RAGBlock
    route: Optional[str]  # "npc" | "scenario" | "rules"
    debug: Dict[str, Any]
    fallback: bool
    scenario: Optional[Scenario]
    npc: Optional[Dict[str, Any]]

def new_dto(player_input: str, ctx: Dict[str, Any]) -> RequestDTO:
    """Create a new DTO with default values"""
    return {
        "correlation_id": str(uuid.uuid4()),
        "ts": time.time(),
        "type": "meta",
        "player_input": player_input,
        "action": "",
        "target": None,
        "context": ctx or {},
        "rag": {"needed": False, "query": "", "filters": {}, "docs": []},
        "route": None,
        "debug": {},
        "fallback": False,
        "scenario": None,
        "npc": None,
    }

def normalize_incoming(raw_request: Dict[str, Any]) -> RequestDTO:
    """Normalize raw incoming request to DTO format"""
    
    # Extract player input from various possible fields
    player_input = ""
    if "player_input" in raw_request:
        player_input = raw_request["player_input"]
    elif "action" in raw_request:
        player_input = raw_request["action"]
    elif "data" in raw_request and isinstance(raw_request["data"], dict):
        data = raw_request["data"]
        if "player_input" in data:
            player_input = data["player_input"]
        elif "action" in data:
            player_input = data["action"]
    
    # Extract context from various possible locations
    context = {}
    if "context" in raw_request:
        context = raw_request["context"] or {}
    elif "data" in raw_request and isinstance(raw_request["data"], dict):
        if "context" in raw_request["data"]:
            context = raw_request["data"]["context"] or {}
        elif "game_context" in raw_request["data"]:
            context = raw_request["data"]["game_context"] or {}
    
    # Extract type information
    request_type = "meta"  # default
    if "type" in raw_request:
        type_val = raw_request["type"]
        if type_val in ["scenario", "npc_interaction", "rules_lookup", "meta"]:
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