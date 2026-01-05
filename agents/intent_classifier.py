"""
Intent Classification Utility - Converts structured intent analysis to routing DTO
Separates classification logic from agent definition for better modularity
"""

from typing import Dict, Any
from components.shared_contract import new_dto
from config.logging_config import get_logger

logger = get_logger(__name__)


def _map_primary_to_type(primary: str) -> str:
    """Map primary intent to DTO type"""
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


def _determine_final_route(intent_dto: Dict[str, Any]) -> str:
    """Determine final route based on intent analysis"""

    primary = intent_dto.get("type", "scenario")
    rag = intent_dto.get("rag", {})
    rag_needed = bool(rag.get("needed", False))

    # Combat route (highest priority)
    if primary == "combat" or "combat" in str(intent_dto).lower():
        return "combat_pipeline"

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

    # Everything else goes to scenario
    return "scenario_pipeline"


def classify_player_intent_from_structured_output(
    player_input: str,
    rag_context: str,
    intent_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Convert structured intent analysis to routing DTO.
    Designed to work with structured output from LLM (no tool calls needed).

    Args:
        player_input: Raw player input text
        rag_context: Current game context as descriptive string
        intent_data: Structured intent analysis from LLM (matches INTENT_ANALYSIS_SCHEMA)

    Returns:
        Complete routing DTO with decision data
    """

    logger.debug(f"🔧 classify_player_intent_from_structured_output called")
    logger.debug(f"   Input: {player_input}")
    logger.debug(f"   Intent data keys: {list(intent_data.keys())}")

    # Create base DTO
    context_dict = {}
    dto = new_dto(player_input, context_dict)

    # Extract and validate intent data
    conf = float(max(0.0, min(1.0, intent_data.get("confidence", 0.0))))
    primary = str(intent_data.get("primary", "scenario") or "scenario")

    # Map to fixed system types
    dto["type"] = _map_primary_to_type(primary)
    dto["action"] = intent_data.get("action_verb", "") or ""
    dto["arguments"] = intent_data.get("arguments", "") or ""
    dto["target"] = intent_data.get("target", "") or None
    dto["confidence"] = conf
    dto["rationale"] = intent_data.get("rationale", "") or ""
    dto["debug"]["intent"] = {"primary": primary, "confidence": conf, "raw": intent_data}

    # Update RAG block fields
    dto["rag"]["category"] = intent_data.get("rag_category", "")
    dto["rag"]["needed"] = bool(intent_data.get("rag_needed", False))
    dto["rag"]["query"] = intent_data.get("rag_query", "")

    # Parse rag_filters from comma-separated string
    rag_filters_str = intent_data.get("rag_filters", "")
    filters_list = [f.strip() for f in rag_filters_str.split(",") if f.strip()] if rag_filters_str else []
    dto["rag"]["filters"] = filters_list

    dto["rag"]["docs"] = []
    dto["rag"]["reasoning"] = intent_data.get("rag_reasoning", "")
    dto["rag"]["confidence"] = float(max(0.0, min(1.0, intent_data.get("rag_confidence", 0.0))))
    dto["rag"]["response"] = ""
    dto["rag"]["rag_context"] = rag_context or "No context provided"

    # Debug output
    logger.debug(f"🔧 INTENT CLASSIFICATION DEBUG:")
    logger.debug(f"   Input: {player_input}")
    logger.debug(f"   Primary: {primary}")
    logger.debug(f"   Mapped Type: {dto['type']}")
    logger.debug(f"   Confidence: {conf}")
    logger.debug(f"   RAG Needed: {dto['rag']['needed']}")

    # Determine route
    route = _determine_final_route(dto)
    dto["route"] = route

    logger.debug(f"🔧 CLASSIFICATION RESULT: {route} (confidence: {conf})")

    return dto
