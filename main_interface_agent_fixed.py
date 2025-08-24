
"""
Deterministic Interface Agent - Haystack Integration
Enhanced version of the original fixed system integrated with Haystack Agent framework
- Uses a constrained JSON intent classifier (temperature=0) and sequential pipeline
- Integrates with WorldStateAdapter for entity resolution
- Provides single-tool routing for maximum performance
"""

from __future__ import annotations
from typing import Dict, Any, Optional, List, Tuple
import json
import time
import uuid

# Haystack imports
from haystack.components.agents import Agent
from haystack.dataclasses import ChatMessage
from haystack.tools import tool

# Local imports
from config.llm_config import get_global_config_manager
from shared_contract import new_fixed_dto, FixedSystemDTO
from adapters.world_state_adapter import WorldStateAdapter, MockWorldStateAdapter

# Debug control
DEBUG_FIXED_AGENT = True

def _log_event(dto: Dict[str, Any], event: str, data: Dict[str, Any]):
    """Log events for debugging"""
    if DEBUG_FIXED_AGENT:
        print(f"🔧 FIXED_AGENT [{event}]: {data}")
        if "debug" not in dto:
            dto["debug"] = {}
        if "events" not in dto["debug"]:
            dto["debug"]["events"] = []
        dto["debug"]["events"].append({"event": event, "data": data, "ts": time.time()})


# --- DTO (shared contract-lite) ------------------------------------------------------------------

# Use shared contract DTO creation
def _new_dto(player_input: str, ctx: Dict[str, Any]) -> FixedSystemDTO:
    """Create new DTO using shared contract"""
    return new_fixed_dto(player_input, ctx)

# --- Intent classification helpers ---------------------------------------------------------------

def _map_primary_to_type(primary: str) -> str:
    m = {
        "rules_lookup": "rules_lookup",
        "npc_interaction": "npc_interaction",
        "scenario_action": "scenario",
        "world_lore": "scenario",           # lore handled via scenario generation, with RAG
        "inventory_management": "scenario",
        "party_management": "scenario",
        "meta": "meta",
    }
    return m.get(primary, "scenario")

# --- Helper functions -----------------------------------------------------------------------------

# --- Target resolution (simple fuzzy) -------------------------------------------------------------

def _resolve_target(target_string: Optional[str], world_state) -> Tuple[Optional[str], str]:
    """Resolve a free-text target to a world entity id. world_state must expose .npcs (dict) and .places (list/dict)."""
    if not target_string:
        return None, "unknown"
    t = target_string.lower().strip()
    # NPCs
    if hasattr(world_state, "npcs"):
        for npc_id, npc in world_state.npcs.items():
            names = {npc_id.lower()}
            if isinstance(npc, dict):
                for alias in npc.get("aliases", []):
                    names.add(str(alias).lower())
                if "name" in npc:
                    names.add(str(npc["name"]).lower())
            if t in names:
                return npc_id, "npc"
    # Places
    places = getattr(world_state, "places", [])
    for p in places or []:
        if str(p).lower() == t:
            return str(p), "place"
    return target_string, "unknown"

# --- Haystack Agent Integration ------------------------------------------------------------------

def _create_intent_classification_dto(intent_data: Dict[str, Any], player_input: str, game_context: Dict[str, Any]) -> Dict[str, Any]:
    """Process LLM intent classification result into routing DTO"""
    
    # Get world state adapter from context
    world_state_adapter = game_context.get("world_state_adapter")
    if not world_state_adapter:
        world_state_adapter = MockWorldStateAdapter()
    
    # Create base DTO
    dto = _new_dto(player_input, game_context)
    _log_event(dto, "start", {"text": player_input})
    
    # Extract and validate intent data
    conf = float(max(0.0, min(1.0, intent_data.get("confidence", 0.0))))
    primary = str(intent_data.get("primary", "scenario_action") or "scenario_action")
    
    # Map to fixed system types
    dto["type"] = _map_primary_to_type(primary)
    dto["action"] = intent_data.get("action_verb", "") or ""
    dto["target"] = intent_data.get("target_string") or None
    dto["target_kind"] = intent_data.get("target_kind", "unknown") or "unknown"
    dto["arguments"] = intent_data.get("arguments", {}) or {}
    dto["confidence"] = conf
    dto["rationale"] = intent_data.get("rationale", "") or ""
    dto["debug"]["intent"] = {"primary": primary, "confidence": conf, "raw": intent_data}

    # Debug output
    print(f"🔧 INTENT CLASSIFICATION DEBUG:")
    print(f"   Input: {player_input}")
    print(f"   Primary: {primary}")
    print(f"   Mapped Type: {dto['type']}")
    print(f"   Confidence: {conf}")
    print(f"   Action Verb: {intent_data.get('action_verb', 'N/A')}")
    print(f"   Target: {intent_data.get('target_string', 'N/A')}")
    print(f"   Rationale: {intent_data.get('rationale', 'N/A')}")

    _log_event(dto, "intent", {"type": dto["type"], "conf": conf})

    # Deterministic target resolution
    resolved_id, resolved_kind = _resolve_target(dto.get("target"), world_state_adapter)
    dto["target"] = resolved_id
    dto["target_kind"] = resolved_kind
    dto["debug"]["target_resolution"] = {"original": intent_data.get("target_string"), "resolved": resolved_id, "kind": resolved_kind}

    # Route determination (simplified - no RAG prediction for now)
    route = _determine_final_route(intent_data, resolved_kind, {"needed": False})
    dto["route"] = route
    
    _log_event(dto, "route", {"route": route})
    
    return dto


@tool(outputs_to_state={"routing_result": {"source": "routing_result"}})
def classify_player_intent(player_input: str, game_context: Any, intent_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process LLM intent classification result into routing decision
    
    Args:
        player_input: Raw player input text
        game_context: Current game context (may be serialized as string)
        intent_data: LLM classification result with primary, confidence, etc.
        
    Returns:
        Complete routing DTO with decision data
    """
    print(f"🔧 TOOL CALLED: classify_player_intent")
    print(f"   Input: {player_input}")
    print(f"   Intent data: {intent_data}")
    
    # Handle serialization issue
    if isinstance(game_context, str):
        print(f"🔧 FIXING: game_context received as string")
        actual_context = {"location": "unknown", "world_state_adapter": None}
    elif isinstance(game_context, dict):
        actual_context = game_context
    else:
        actual_context = {}
    
    # Process intent classification into routing DTO
    routing_result = _create_intent_classification_dto(intent_data, player_input, actual_context)
    
    print(f"🔧 TOOL RESULT: {routing_result.get('route', 'unknown')} (confidence: {routing_result.get('confidence', 0)})")
    print(f"   Classification: {routing_result.get('type', 'unknown')}")
    
    return {"routing_result": routing_result}


@tool(outputs_to_state={"routing_result": {"source": "routing_result"}})
def execute_deterministic_routing_fallback(player_input: str, game_context: Any) -> Dict[str, Any]:
    """
    Fallback routing using keyword-based classification when LLM fails
    
    Args:
        player_input: Raw player input text
        game_context: Current game context (may be serialized as string)
        
    Returns:
        Basic routing DTO with keyword-based decision
    """
    print(f"🔧 FALLBACK TOOL CALLED: execute_deterministic_routing_fallback")
    print(f"   Input: {player_input}")
    
    # Handle serialization issue
    if isinstance(game_context, str):
        actual_context = {"location": "unknown", "world_state_adapter": None}
    elif isinstance(game_context, dict):
        actual_context = game_context
    else:
        actual_context = {}
    
    # Keyword-based classification for fallback
    input_lower = player_input.lower()
    
    if any(word in input_lower for word in ["damage", "rule", "spell", "cast", "mechanics", "how does", "what does"]):
        intent_data = {
            "primary": "rules_lookup",
            "action_verb": "query",
            "target_string": "rules",
            "target_kind": "object",
            "arguments": {},
            "confidence": 0.9,
            "rationale": "Rules or mechanics question (keyword-based)"
        }
    elif any(word in input_lower for word in ["bartender", "talk to", "ask", "speak to"]):
        intent_data = {
            "primary": "npc_interaction",
            "action_verb": "talk",
            "target_string": "bartender" if "bartender" in input_lower else "npc",
            "target_kind": "npc",
            "arguments": {},
            "confidence": 0.85,
            "rationale": "NPC interaction (keyword-based)"
        }
    elif any(word in input_lower for word in ["what is", "who are", "tell me about", "explain"]):
        intent_data = {
            "primary": "world_lore",
            "action_verb": "query",
            "target_string": player_input,
            "target_kind": "place",
            "arguments": {},
            "confidence": 0.8,
            "rationale": "World lore query (keyword-based)"
        }
    else:
        intent_data = {
            "primary": "scenario_action",
            "action_verb": "act",
            "target_string": "",
            "target_kind": "unknown",
            "arguments": {},
            "confidence": 0.7,
            "rationale": "General scenario action (keyword-based)"
        }
    
    # Process into routing DTO
    routing_result = _create_intent_classification_dto(intent_data, player_input, actual_context)
    
    print(f"🔧 FALLBACK RESULT: {routing_result.get('route', 'unknown')} (confidence: {routing_result.get('confidence', 0)})")
    
    return {"routing_result": routing_result}

# Direct callable version for orchestrator integration
def execute_deterministic_routing_direct(player_input: str, game_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Direct callable version for orchestrator and testing using keyword-based classification
    
    Args:
        player_input: Raw player input text
        game_context: Current game context including world_state_adapter
        
    Returns:
        Complete routing DTO with decision data
    """
    print(f"🔧 DIRECT CALL: execute_deterministic_routing_direct")
    print(f"   Input: {player_input}")
    
    # Use keyword-based classification
    input_lower = player_input.lower()
    
    if any(word in input_lower for word in ["damage", "rule", "spell", "cast", "mechanics", "how does", "what does"]):
        intent_data = {
            "primary": "rules_lookup",
            "action_verb": "query",
            "target_string": "rules",
            "target_kind": "object",
            "arguments": {},
            "confidence": 0.9,
            "rationale": "Rules or mechanics question (keyword-based)"
        }
    elif any(word in input_lower for word in ["bartender", "talk to", "ask", "speak to"]):
        intent_data = {
            "primary": "npc_interaction",
            "action_verb": "talk",
            "target_string": "bartender" if "bartender" in input_lower else "npc",
            "target_kind": "npc",
            "arguments": {},
            "confidence": 0.85,
            "rationale": "NPC interaction (keyword-based)"
        }
    elif any(word in input_lower for word in ["what is", "who are", "tell me about", "explain"]):
        intent_data = {
            "primary": "world_lore",
            "action_verb": "query",
            "target_string": player_input,
            "target_kind": "place",
            "arguments": {},
            "confidence": 0.8,
            "rationale": "World lore query (keyword-based)"
        }
    else:
        intent_data = {
            "primary": "scenario_action",
            "action_verb": "act",
            "target_string": "",
            "target_kind": "unknown",
            "arguments": {},
            "confidence": 0.7,
            "rationale": "General scenario action (keyword-based)"
        }
    
    # Process into routing DTO
    routing_result = _create_intent_classification_dto(intent_data, player_input, game_context)
    
    print(f"🔧 DIRECT RESULT: {routing_result.get('route', 'unknown')} (confidence: {routing_result.get('confidence', 0)})")
    
    return routing_result

def _determine_final_route(intent_data: Dict[str, Any], resolved_kind: str, rag_data: Dict[str, Any]) -> str:
    """Determine final route based on intent analysis"""
    
    primary = intent_data.get("primary", "scenario_action")
    
    # Rules lookup route
    if primary == "rules_lookup":
        return "rules"
    
    # NPC interaction route
    if primary == "npc_interaction" or resolved_kind == "npc":
        return "npc"
    
    # Meta commands route
    if primary == "meta":
        return "meta"
    
    # Everything else goes to scenario (potentially with RAG)
    return "scenario"

def create_fixed_interface_agent(chat_generator=None) -> Agent:
    """
    Create Haystack Agent using fixed system logic with proper LLM integration
    
    Args:
        chat_generator: Optional Haystack chat generator
        
    Returns:
        Configured Haystack Agent with deterministic routing
    """
    
    # Use LLM config manager to get appropriate generator
    if chat_generator is None:
        config_manager = get_global_config_manager()
        generator = config_manager.create_generator("main_interface")
    else:
        generator = chat_generator
    
    system_prompt = """
You are a D&D intent classification agent that analyzes player input and determines routing decisions.

WORKFLOW:
1. Analyze the player input for intent classification
2. Extract key information: action verb, target, arguments
3. Use classify_player_intent tool with your analysis
4. If classification fails, use execute_deterministic_routing_fallback

INTENT CATEGORIES:
- rules_lookup: Questions about game mechanics, spells, damage, stats, rules
- npc_interaction: Talking to, asking, or interacting with NPCs
- scenario_action: Physical actions in the game world
- world_lore: Questions about places, history, or world information
- inventory_management: Managing items, equipment
- party_management: Group actions, character management
- meta: Out-of-character commands

OUTPUT FORMAT (for classify_player_intent tool):
{
  "primary": "category_name",
  "action_verb": "verb describing the action",
  "target_string": "what the action targets",
  "target_kind": "npc|object|place|unknown",
  "arguments": {},
  "confidence": 0.0-1.0,
  "rationale": "brief explanation"
}

EXAMPLES:
- "what is the damage of longsword" → rules_lookup, high confidence
- "ask the bartender about rumors" → npc_interaction, target="bartender"
- "search the room for traps" → scenario_action, target="room"
- "what are the ideals of Knights Radiant" → world_lore, target="Knights Radiant"

Always analyze the input first, then call the appropriate tool. Use high confidence for clear classifications.
"""

    agent = Agent(
        chat_generator=generator,
        tools=[classify_player_intent, execute_deterministic_routing_fallback],
        system_prompt=system_prompt,
        exit_conditions=["classify_player_intent", "execute_deterministic_routing_fallback"],
        max_agent_steps=2,  # Allow for analysis then tool call
        raise_on_tool_invocation_failure=False,
        state_schema={
            "routing_result": {"type": dict}
        }
    )
    return agent

# --- Simple smoke test (optional) -----------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    class _World:
        def __init__(self):
            self.npcs = {"bartender": {"name": "Bart", "aliases": ["barkeep", "bartender"]}}
            self.places = ["Dragonbone Spire", "Tavern"]
    world = _World()

    # Dummy cfg stub if running standalone (replace with real cfg in your app)
    class _LLMStub:
        def __call__(self, prompt, temperature=0.0, max_tokens=None):
            if "cast fireball" in prompt:
                return json.dumps({"primary":"rules_lookup","secondary":[],"action_verb":"cast","target_string":"fireball","target_kind":"object","arguments":{"spell":"fireball","level":5},"confidence":0.9,"rationale":""})
            if "bartender" in prompt:
                return json.dumps({"primary":"npc_interaction","secondary":[],"action_verb":"ask","target_string":"bartender","target_kind":"npc","arguments":{},"confidence":0.8,"rationale":""})
            if "Dragonbone Spire" in prompt:
                return json.dumps({"primary":"world_lore","secondary":[],"action_verb":"query","target_string":"Dragonbone Spire","target_kind":"place","arguments":{},"confidence":0.8,"rationale":""})
            return json.dumps({"primary":"scenario_action","secondary":[],"action_verb":"search","target_string":"","target_kind":"unknown","arguments":{},"confidence":0.6,"rationale":""})

    class _Cfg:
        llm = _LLMStub()
        embedder = None
        intent_centroids = {}

    # monkeypatch
    def _get_cfg():
        return _Cfg()
    globals()['get_global_config_manager'] = _get_cfg

    decide = build_interface_agent(world)
    for text in [
        "cast fireball at level 5",
        "ask the bartender about rumors",
        "what is the Dragonbone Spire?",
        "search the alcove for levers",
    ]:
        out = decide(text, {"location":"Tavern"})
        print(text, "→", out["type"], out["route"], out["rag"])
