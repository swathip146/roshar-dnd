
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
from haystack.tools import Tool

# Local imports
from config.llm_config import get_global_config_manager
from components.shared_contract import new_dto

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


# --- Intent classification helpers ---------------------------------------------------------------

def _map_primary_to_type(primary: str) -> str:
    m = {
        "rules_lookup": "rag_query",
        "npc_interaction": "npc_interaction",
        "scenario_action": "scenario",
        "scenario_generation": "scenario",
        "world_lore": "rag_query",
        "inventory_management": "scenario",
        "pure_query": "rag_query",
        "party_management": "scenario"
    }
    return m.get(primary, "scenario")

def _determine_final_route(intent_data: Dict[str, Any]) -> str:
    """Determine final route based on intent analysis"""
    
    primary = intent_data.get("type", "scenario")
    #extract rag.needed from intent_data
    rag = intent_data.get("rag", {})
    rag_needed = bool (rag.get("needed", False))
    
    # Rules lookup route
    if primary == "rag_query":
        return "rag_pipeline"
    
    # NPC interaction route
    if primary == "npc_interaction":
        return "npc_pipeline"
    
    if primary == "scenario":
        if rag_needed:
            return "scenario_with_rag_pipeline"
        else:
            return "scenario_pipeline"
    
    # Everything else goes to scenario (potentially with RAG)
    return "scenario_pipeline"

# --- Haystack Agent Integration ------------------------------------------------------------------

def record_intent_analysis(
    primary: str,
    action_verb: str,
    arguments: str,
    target: str = None,
    confidence: float = 0.8,
    rationale: str = "",
    rag_needed: bool = True,
    rag_query: str = "",
    rag_filters: str = "rules,general",  # Changed from List[str] to str
    rag_confidence: float = 0.8,
    rag_category: str = "general",
    rag_reasoning: str = ""
) -> Dict[str, Any]:
    """
    Record intent analysis in the proper format for classify_player_intent
    
    Args:
        primary: Primary intent category
        action_verb: Action verb extracted
        arguments: Arguments for the action
        target: Target of the action (optional)
        confidence: Confidence level (0.0-1.0)
        rationale: Explanation of classification
        rag_needed: Whether RAG is needed
        rag_query: Query for RAG system
        rag_filters: List of filter keywords
        rag_confidence: RAG confidence level
        rag_category: RAG category
        rag_reasoning: RAG reasoning
        
    Returns:
        Dict containing formatted intent_data for state storage
    """
    
    print("record_intent_analysis called")
    # Parse filters string into list
    filters_list = [f.strip() for f in rag_filters.split(",") if f.strip()] if rag_filters else []
    
    # Create the properly formatted intent_data
    intent_data = {
        "primary": primary,
        "action_verb": action_verb,
        "arguments": arguments,
        "target": target if target else None,
        "confidence": confidence,
        "rationale": rationale,
        "rag": {
            "needed": rag_needed,
            "query": rag_query,
            "filters": filters_list,
            "docs": [],
            "confidence": rag_confidence,
            "category": rag_category,
            "reasoning": rag_reasoning
        }
    }
    
    print(f"🔧 RECORDED INTENT: {intent_data}")
    
    return intent_data

def classify_player_intent(player_input: str, rag_context: str = None, intent_data: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Process LLM intent classification result into routing decision
    
    Args:
        player_input: Raw player input text
        rag_context: Current game context as descriptive string
        intent_data: LLM classification result with primary, confidence, etc.
        
    Returns:
        Complete routing DTO with decision data
    """
    
    print(f"🔧 TOOL CALLED: classify_player_intent")
    print(f"   Input: {player_input}")
    print(f"   RAG Context: {rag_context}")
    print(f"   Intent data: {intent_data}")
    
    # Use provided parameters or defaults
    if rag_context is None:
        rag_context = "Player is in world"
    if intent_data is None:
        intent_data = {}
    
    # Convert string context to dict format for DTO creation
    context_dict = {}
    
    # Create base DTO (combined _create_intent_classification_dto logic)
    dto = new_dto(player_input, context_dict)
    _log_event(dto, "start", {"text": player_input})
    
    # Extract and validate intent data
    conf = float(max(0.0, min(1.0, intent_data.get("confidence", 0.0))))
    primary = str(intent_data.get("primary", "scenario") or "scenario")
    
    # Map to fixed system types
    dto["type"] = _map_primary_to_type(primary)
    dto["action"] = intent_data.get("action_verb", "") or ""
    dto["arguments"] = intent_data.get("arguments", {}) or {}
    dto["target"] = intent_data.get("target", None)
    dto["confidence"] = conf
    dto["rationale"] = intent_data.get("rationale", "") or ""
    dto["debug"]["intent"] = {"primary": primary, "confidence": conf, "raw": intent_data}
    
    # Update RAG block fields to match RequestDTO structure
    rag_data = intent_data.get("rag", {}) or {}
    dto["rag"]["category"] = rag_data.get("category", "")
    dto["rag"]["needed"] = bool(rag_data.get("needed", False))
    dto["rag"]["query"] = rag_data.get("query", "")
    dto["rag"]["filters"] = rag_data.get("filters", {})
    dto["rag"]["docs"] = rag_data.get("docs", [])  # Should be list, not dict
    dto["rag"]["reasoning"] = rag_data.get("reasoning", "")  # Fixed typo from "resoning"
    dto["rag"]["confidence"] = float(max(0.0, min(1.0, rag_data.get("confidence", 0.0))))
    dto["rag"]["response"] = rag_data.get("response", "")  # Ensure answer field is set
    dto["rag"]["rag_context"] = rag_context or "No context provided"

    # Debug output
    print(f"🔧 INTENT CLASSIFICATION DEBUG:")
    print(f"   Input: {player_input}")
    print(f"   Primary: {primary}")
    print(f"   Mapped Type: {dto['type']}")
    print(f"   Confidence: {conf}")
    print(f"   Action Verb: {intent_data.get('action_verb', 'N/A')}")
    print(f"   Target: {intent_data.get('target', 'N/A')}")
    print(f"   Rationale: {intent_data.get('rationale', 'N/A')}")

    _log_event(dto, "intent", {"type": dto["type"], "conf": conf})

    route = _determine_final_route(dto)
    dto["route"] = route
    
    _log_event(dto, "route", {"route": route})
    
    print(f"🔧 TOOL RESULT: {dto.get('route', 'unknown')} (confidence: {dto.get('confidence', 0)})")
    print(f"   Classification: {dto.get('type', 'unknown')}")

    # Return the RequestDTO wrapped in a dict for Haystack state management
    return {"interface_result": dto}


# Create Tool instances
record_intent_analysis_tool = Tool(
    name="record_intent_analysis",
    description="Record intent analysis in the proper format for classify_player_intent",
    parameters={
        "type": "object",
        "properties": {
            "primary": {
                "type": "string",
                "description": "Primary intent category"
            },
            "action_verb": {
                "type": "string",
                "description": "Action verb extracted"
            },
            "arguments": {
                "type": "string",
                "description": "Arguments for the action"
            },
            "target": {
                "type": "string",
                "description": "Target of the action (optional)"
            },
            "confidence": {
                "type": "number",
                "description": "Confidence level (0.0-1.0)",
                "default": 0.8
            },
            "rationale": {
                "type": "string",
                "description": "Explanation of classification",
                "default": ""
            },
            "rag_needed": {
                "type": "boolean",
                "description": "Whether RAG is needed",
                "default": True
            },
            "rag_query": {
                "type": "string",
                "description": "Query for RAG system",
                "default": ""
            },
            "rag_filters": {
                "type": "string",
                "description": "List of filter keywords as comma-separated string",
                "default": "rules,general"
            },
            "rag_confidence": {
                "type": "number",
                "description": "RAG confidence level",
                "default": 0.8
            },
            "rag_category": {
                "type": "string",
                "description": "RAG category",
                "default": "general"
            },
            "rag_reasoning": {
                "type": "string",
                "description": "RAG reasoning",
                "default": ""
            }
        },
        "required": ["primary", "action_verb", "arguments"]
    },
    function=record_intent_analysis,
    outputs_to_state={"intent_data": {}}
)

classify_player_intent_tool = Tool(
    name="classify_player_intent",
    description="Process LLM intent classification result into routing decision",
    parameters={
        "type": "object",
        "properties": {
            "player_input": {
                "type": "string",
                "description": "Raw player input text",
                "default": ""
            },
            "rag_context": {
                "type": "string",
                "description": "Current game context and situational information as a descriptive string",
                "default": "Player is in world"
            }
        },
        "required": []
    },
    function=classify_player_intent,
    inputs_from_state={
        "intent_data": "intent_data",
        "player_input": "player_input",
        "rag_context": "rag_context"
    },
    outputs_to_state={"interface_result": {"source": "interface_result"}}
)

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
1. Analyze the player input and current game context for intent classification
2. Extract key information: action verb, arguments, questions, target
3. CRITICALLY EVALUATE: Does the current game context and quest context provide sufficient information, or would additional RAG context genuinely help?
4. STEP 1: Call record_intent_analysis with your analysis
5. STEP 2: Call classify_player_intent to process the recorded analysis

INTENT CATEGORIES:
    - rules_lookup: Questions about game mechanics, spells, damage, stats, rules
    - npc_interaction: Talking to, asking, or interacting with NPCs
    - scenario_action: Physical actions in the game world
    - world_lore: Questions about places, history, or world information
    - scenario_generation: generation of scenarios, interactions, consequences
    - inventory_management: managing inventory, equipment, loot
    - pure_query: General questions not related to game mechanics

RAG DECISION CRITERIA (BE SELECTIVE):
ONLY set rag_needed=true when:
✓ Player asks direct questions about rules/mechanics not covered in current context
✓ Player actions involve specific locations/NPCs/lore not already described in current context
✓ Scenario generation needs specific campaign details, monster stats, or encounter information not available
✓ Complex rule clarifications that require detailed mechanics
✓ Additional RAG context greatly enriches context for scenario generation

AVOID RAG when:
✗ Current game context already provides sufficient information for the scenario
✗ Player is taking simple actions that don't require additional world knowledge
✗ Basic social interactions or movement that can be handled with existing context
✗ Quest context already contains the necessary details for scenario generation

RAG CATEGORIES:
    - rules: Spell mechanics, game rules, abilities, combat mechanics, skill checks
    - lore: World history, legends, stories, character backgrounds, past events
    - monsters: Creature information, bestiary entries, monster behaviors
    - locations: Place descriptions, geography, notable locations
    - campaigns: Encounters, quests, storylines
    - general: Catch-all for other content

EXAMPLE WORKFLOWS:

EXAMPLE 1 - RAG NOT NEEDED:
For "I attack the orc with my sword" (current context: "in combat with orc"):
STEP 1: record_intent_analysis(
    primary="scenario_action",
    action_verb="attack",
    arguments="sword attack",
    target="orc",
    confidence=0.95,
    rationale="Simple combat action with sufficient context",
    rag_needed=false,
    rag_reasoning="Current combat context provides sufficient information for scenario generation"
)

EXAMPLE 2 - RAG NEEDED:
For "what is the damage of longsword" (player asking about mechanics):
STEP 1: record_intent_analysis(
    primary="rules_lookup",
    action_verb="lookup",
    arguments="longsword damage",
    target="longsword",
    confidence=0.95,
    rationale="Player asking for weapon statistics",
    rag_needed=true,
    rag_query="longsword weapon damage statistics",
    rag_filters="rules,weapons,damage",
    rag_confidence=0.9,
    rag_category="rules",
    rag_reasoning="Need specific weapon stats from rules database"
)

EXAMPLE 3 - RAG NOT NEEDED:
For "I look around the room" (current context: "in tavern with detailed description"):
STEP 1: record_intent_analysis(
    primary="scenario_action",
    action_verb="look",
    arguments="examine surroundings",
    confidence=0.9,
    rationale="Simple perception action in described environment",
    rag_needed=false,
    rag_reasoning="Current location context sufficient for describing what player sees"
)

Always do BOTH steps in order.
"""

    agent = Agent(
        chat_generator=generator,
        tools=[record_intent_analysis_tool, classify_player_intent_tool],
        system_prompt=system_prompt,
        exit_conditions=["classify_player_intent"],
        max_agent_steps=3,  # Allow for analysis, record, then classify
        raise_on_tool_invocation_failure=False,
        state_schema={
            "intent_data": {"type": dict},
            "interface_result": {"type": dict},
            "player_input": {"type": str},
            "rag_context": {"type": str}
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

    decide = create_fixed_interface_agent()
    for text in [
        "cast fireball at level 5",
        "ask the bartender about rumors",
        "what is the Dragonbone Spire?",
        "search the alcove for levers",
    ]:
        out = decide(text, {"location":"Tavern"})
        print(text, "→", out["type"], out["route"], out["rag"])
