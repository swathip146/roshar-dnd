"""
Scenario Generator Agent - Creative scenario generation following revised plan contract
Uses proper Haystack Agent framework with tools and system prompts
"""

# DEBUG CONTROL - Set to True to enable detailed debugging
DEBUG_SCENARIO_AGENT = True
DEBUG_SCENARIO_TOOLS = True
DEBUG_VALIDATION = True

import json
import time
from typing import Dict, Any, List, Optional
from haystack.components.agents import Agent
from haystack.dataclasses import ChatMessage
from haystack.tools import Tool
from haystack import component
from config.llm_config import get_global_config_manager
from components.shared_contract import Scenario, Choice, RAGBlock, validate_scenario, repair_scenario, minimal_fallback

from config.logging_config import get_logger

# Initialize logger
logger = get_logger(__name__)

# JSON Schema for structured scenario output (enforces valid JSON from LLM)
# Uses Gemini-compatible schema format (no min/max, only basic JSON Schema)
SCENARIO_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "scene": {
            "type": "string",
            "description": "Rich scene description incorporating action results and all context categories"
        },
        "choices": {
            "type": "array",
            "description": "Array of player choices that emerge naturally from the scene",
            "items": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "Unique identifier for the choice (e.g., 'c1', 'c2')"
                    },
                    "title": {
                        "type": "string",
                        "description": "Clear action name (add **Skill Check (DC X)** or **Combat** when applicable)"
                    },
                    "description": {
                        "type": "string",
                        "description": "Specific explanation of what this choice involves"
                    },
                    "skill_hints": {
                        "type": "array",
                        "description": "Relevant D&D 5e skills that might apply",
                        "items": {"type": "string"}
                    },
                    "suggested_dc": {
                        "type": "integer",
                        "description": "Difficulty Class for skill checks between 0-30 (0 if not applicable)"
                    },
                    "combat_trigger": {
                        "type": "boolean",
                        "description": "True if this choice initiates combat, false otherwise"
                    }
                },
                "required": ["id", "title", "description", "skill_hints", "suggested_dc", "combat_trigger"]
            }
        },
        "gm_notes": {
            "type": "string",
            "description": "Hidden information for DM (include enemy details for combat: name, count, CR)"
        },
        "hooks": {
            "type": "array",
            "description": "Future story possibilities based on context",
            "items": {"type": "string"}
        }
    },
    "required": ["scene", "choices", "gm_notes"]
}


def debug_scenario_print(category: str, message: str, data: Any = None):
    """Centralized debug printing for scenario agent"""
    if DEBUG_SCENARIO_AGENT:
        timestamp = time.strftime('%H:%M:%S')
        logger.debug(f"🐛 SCENARIO [{timestamp}] {category}: {message}")
        if data is not None and DEBUG_SCENARIO_TOOLS:
            if isinstance(data, dict) and len(str(data)) > 300:
                logger.debug(f"    📊 Data keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
            else:
                logger.debug(f"    📊 Data: {data}")


def _campaign_bible_for(game_engine) -> str:
    """
    Build the persistent campaign context for this prompt (plan 0.19).

    Derived from the structured campaign rather than hand-authored, so it cannot
    drift from `shards_of_honor.json`: when a quest completes or a character
    levels, the bible follows. Returns "" on any failure — a missing bible must
    degrade the prompt, never break the turn.
    """
    try:
        from components.campaign_bible import build_campaign_bible

        campaign = None
        for attr in ("campaign_config", "campaign", "campaign_data"):
            candidate = getattr(game_engine, attr, None)
            if candidate is not None:
                campaign = (candidate if isinstance(candidate, dict)
                            else getattr(candidate, "raw", None)
                            or getattr(candidate, "data", None))
                if campaign:
                    break

        if campaign is None:
            campaign = _load_campaign_file()

        return build_campaign_bible(
            campaign=campaign,
            character_manager=getattr(game_engine, "character_manager", None),
            game_engine=game_engine)
    except Exception as e:
        logger.debug(f"   No campaign bible available: {e}")
        return ""


def _load_campaign_file() -> Optional[Dict[str, Any]]:
    """Read the authored campaign directly when the engine does not carry it."""
    import json
    from pathlib import Path

    directory = Path("data/current_campaign")
    if not directory.exists():
        return None
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("title"):
                return data
        except Exception:
            continue
    return None


def create_scenario_from_dto(dto: Dict[str, Any]) -> str:
    """
    Generate scenario using direct GameEngine access instead of DTO context duplication.
    Eliminates state duplication violations while preserving functionality - DTO COMPLIANCE.
    
    Args:
        dto: Streamlined DTO with engine references instead of state copies
        
    Returns:
        Formatted prompt string for LLM to generate scenario
    """
    debug_scenario_print("TOOL", "🎭 Direct engine access scenario generation called", {"dto_type": type(dto), "architecture_compliant": True})
    
    # Handle string representation of DTO (parse JSON)
    if isinstance(dto, str):
        debug_scenario_print("TOOL", "🔄 Converting string DTO to dict")
        try:
            import json
            dto = json.loads(dto.replace("'", '"'))  # Handle single quotes
            debug_scenario_print("TOOL", "✅ String DTO conversion successful")
        except (json.JSONDecodeError, ValueError) as e:
            debug_scenario_print("TOOL", f"💥 Failed to parse DTO string: {e}")
            return "Generate a basic D&D scenario with 2-3 choices due to parsing error."
    
    # Handle None or invalid DTO
    if not dto or not isinstance(dto, dict):
        debug_scenario_print("TOOL", f"❌ Invalid DTO: {type(dto)}")
        return "Generate a basic D&D scenario with 2-3 choices due to invalid input."
    
    # ✅ GET ENGINE REFERENCES (NOT STATE COPIES) - DTO COMPLIANCE
    game_engine = dto.get("_game_engine_ref")
    policy_engine = dto.get("_policy_engine_ref")
    player_action = dto.get("player_input", dto.get("action", "take an action"))
    
    debug_scenario_print("TOOL", "🔧 Accessing engines directly", {
        "game_engine_available": bool(game_engine),
        "policy_engine_available": bool(policy_engine),
        "state_duplication_eliminated": True
    })
    
    # ✅ ACCESS STATE DIRECTLY FROM AUTHORITATIVE SOURCES - NO DUPLICATION
    if game_engine:
        try:
            narrative_context = game_engine.get_narrative_context()
            # Plan 2.2: recent beats, so the DM has memory beyond the last turn.
            story_so_far = (game_engine.get_story_so_far(6)
                            if hasattr(game_engine, "get_story_so_far") else "")
            location_context = game_engine.get_location_context()
            quest_context = game_engine.get_quest_context()
            current_location = location_context.get("current_location", "unknown location")
            environmental_factors = location_context.get("features", [])
            active_objectives = quest_context.get("pending_objectives", [])
            quest_consequences = quest_context.get("consequences", [])
            time_constraints = {
                "time_pressure": quest_context.get("time_pressure", "none"),
                "constraints": quest_context.get("quest_constraints", [])
            }
            debug_scenario_print("TOOL", "✅ Accessed GameEngine state directly")

            # Plan 0.19: the persistent campaign context. RAG only surfaces what
            # you think to query, and this prompt previously had NO campaign
            # section at all — the DM never saw the party, the key NPCs, the acts
            # or how the campaign ends, so it improvised those every turn and the
            # story had no spine.
            campaign_bible = _campaign_bible_for(game_engine)
        except Exception as e:
            debug_scenario_print("TOOL", f"⚠️ GameEngine access failed: {e}")
            # Fallback values
            narrative_context = {}
            story_so_far = ""
            campaign_bible = ""
            location_context = {}
            quest_context = {}
            current_location = "unknown location"
            environmental_factors = []
            active_objectives = []
            quest_consequences = []
            time_constraints = {}
    else:
        debug_scenario_print("TOOL", "⚠️ No GameEngine reference available")
        # Fallback values when no engine available
        narrative_context = {}
        story_so_far = ""
        campaign_bible = ""
        location_context = {}
        quest_context = {}
        current_location = "unknown location"
        environmental_factors = []
        active_objectives = []
        quest_consequences = []
        time_constraints = {}
    
    # ✅ ACCESS POLICY DIRECTLY FROM AUTHORITATIVE SOURCES - NO DUPLICATION
    if policy_engine:
        try:
            policy_profile = policy_engine.get_current_profile()
            mock_party_context = {"avg_level": 3, "party_size": 4}
            
            # Use safe access to policy methods with fallbacks
            try:
                difficulty_policy = policy_engine.get_difficulty_policy(mock_party_context)
                difficulty_target = difficulty_policy.get("difficulty_target", "medium")
            except:
                difficulty_target = "medium"
                
            try:
                choice_policy = policy_engine.get_choice_count_policy(0.8, "medium")
                choice_count_range = [max(2, choice_policy.get("choice_count", 3)-1), choice_policy.get("choice_count", 3)+1]
            except:
                choice_count_range = [2, 4]
                
            debug_scenario_print("TOOL", "✅ Accessed PolicyEngine state directly")
        except Exception as e:
            debug_scenario_print("TOOL", f"⚠️ PolicyEngine access failed: {e}")
            # Fallback values
            policy_profile = "house"
            difficulty_target = "medium"
            choice_count_range = [2, 4]
    else:
        debug_scenario_print("TOOL", "⚠️ No PolicyEngine reference available")
        # Fallback values when no engine available
        policy_profile = "house"
        difficulty_target = "medium"
        choice_count_range = [2, 4]
    
    rag = dto.get("rag", {})
    # Plan 0.2: retrieved lore is written to rag["response"] by the RAG pipeline
    # (pipeline_integration.py:680 / :792), while rag["rag_context"] only ever held
    # the game/quest summary string set during intent classification (:573).
    # Reading rag_context alone meant every retrieved document was silently discarded.
    # Prefer real retrieval; fall back to the game-context summary when RAG didn't run.
    retrieved_lore = (rag.get("response") or "").strip()
    game_context = (rag.get("rag_context") or "").strip()
    consolidated_rag = retrieved_lore or game_context
    # Bound prompt growth. ~4000 chars ≈ 1k tokens — enough for several retrieved
    # chunks, far more than the old 100-char truncation which discarded everything.
    MAX_RAG_CHARS = 4000
    if len(consolidated_rag) > MAX_RAG_CHARS:
        consolidated_rag = consolidated_rag[:MAX_RAG_CHARS] + "\n…[truncated]"
    
    debug_scenario_print("TOOL", f"📋 Direct engine access context extracted", {
        "player_action": player_action,
        "current_location": current_location,
        "difficulty_target": difficulty_target,
        "narrative_context": narrative_context,
        "quest_context": quest_context,
        "rag_snippets_count": len(consolidated_rag)
    })
    logger.debug(f"Narrative context: {narrative_context}\n")
    logger.debug(f"Quest context: {quest_context}\n")
    
    # Build comprehensive prompt using directly accessed context (same format, different source)
    prompt = f"""Generate a D&D scenario using direct engine access context system:

{campaign_bible if campaign_bible else "=== NO CAMPAIGN BIBLE AVAILABLE ==="}

=== A. NARRATIVE CONTEXT (from GameEngine) ===
Player Action: "{player_action}"
Current Narrative Context: {narrative_context if narrative_context else "None established"}

STORY SO FAR (most recent turns, oldest first — maintain continuity with these):
{story_so_far if story_so_far else "This is the opening scene."}

=== B. LOCATION & ENVIRONMENT CONTEXT (from GameEngine) ===
Current Location: {current_location}
Environmental Factors: {environmental_factors if environmental_factors else "Standard conditions"}

=== C. QUESTS & CONSTRAINTS CONTEXT (from GameEngine) ===
Active Objectives: {active_objectives if active_objectives else "No specific objectives"}
Time Constraints: {time_constraints if time_constraints else "None"}
Quest Consequences: {quest_consequences if quest_consequences else "Unknown"}

=== D. MECHANICS POLICY CONTEXT (from PolicyEngine) ===
Policy Profile: {policy_profile} (determines house rules and difficulty scaling)
Target Difficulty: {difficulty_target}
Choice Count Target: {choice_count_range[0]}-{choice_count_range[1]} options

=== E. RAG CONTEXT (Retrieved Lore/Rules/Information) ===
RAG Context: {consolidated_rag if consolidated_rag else "No specific information retrieved"}

=== F. OUTPUT REQUIREMENTS ===
Choice Count: {choice_count_range[0]}-{choice_count_range[1]} choices required
Output Format: Standard D&D scenario JSON

SCENARIO GENERATION REQUIREMENTS:

Create a JSON response with this exact structure:
{{
  "scene": "Scene description incorporating action results and all context",
  "choices": [
    {{
      "id": "c1",
      "title": "Choice title (include **Skill Check (DC X)** or **Combat** when applicable)",
      "description": "Detailed description of what this choice entails",
      "skill_hints": ["relevant_skill1", "relevant_skill2"],
      "suggested_dc": 12,
      "combat_trigger": false
    }},
    {{
      "id": "c2",
      "title": "Attack the enemies **Combat**",
      "description": "Engage in combat with hostile creatures",
      "skill_hints": [],
      "suggested_dc": 0,
      "combat_trigger": true
    }}
  ],
  "effects": {{}},
  "hooks": ["Future story hooks based on party strengths/weaknesses"],
  "gm_notes": "Hidden information for DM - describe enemies (name, count, CR) for combat encounters",
  "state_changes": {{}},
  "difficulty_used": {{}}
}}

ENHANCED GENERATION GUIDELINES:

SCENE CREATION:
- Show immediate consequences of the player's action: "{player_action}"
- Reflect the {current_location} atmosphere and mood
- Integrate environmental factors meaningfully: {environmental_factors}
- Weave in the RETRIEVED LORE below naturally — do not contradict it
- Use vivid sensory details (sight, sound, smell, touch)
- Build narrative momentum from existing context: {narrative_context}
- Connect to active objectives where relevant: {active_objectives}

RETRIEVED LORE (canonical — prefer this over your own recollection):
{consolidated_rag if consolidated_rag else "None retrieved for this turn."}

CHOICE GENERATION - NARRATIVE-DRIVEN APPROACH ({choice_count_range[0]}-{choice_count_range[1]} choices):
**KEY PRINCIPLE**: Generate choices that emerge naturally from the scene and situation, not from a formula.

- Ask: "Given this scene, what would players realistically want to do?"
- Each choice should feel meaningfully different and lead to distinct outcomes
- Consider different approaches: cautious vs bold, direct vs indirect, immediate vs patient
- Only include skill checks, combat, or social elements if they naturally fit the situation
- Reference quest objectives and time constraints when relevant: {active_objectives}
- Use environmental factors as opportunities or obstacles: {environmental_factors}

CHOICE VARIETY GUIDANCE:
- **Don't force artificial variety** - let the situation dictate the options
- **Skill-based choices**: Only when investigation, physical action, or expertise naturally applies
- **Social choices**: Only when NPCs or communication opportunities exist
- **Combat choices**: Only when threats or aggressive options make narrative sense
  - Set "combat_trigger": true for choices that initiate combat
  - Include **Combat** marker in title for combat choices
  - Describe enemies in gm_notes (name, count, estimated CR)
  - Examples: "Attack the goblins **Combat**", "Engage in battle **Combat**"
- **Creative/risky choices**: Think outside the box for clever or unconventional approaches

COMBAT TRIGGER RULES:
- Set "combat_trigger": true ONLY when:
  1. The choice directly initiates combat (e.g., "Attack", "Fight", "Engage enemies")
  2. Hostile creatures are present and the action leads to battle
  3. The scene describes an imminent threat requiring combat resolution
- Set "combat_trigger": false for:
  1. Non-combat actions (diplomacy, sneaking, fleeing, investigating)
  2. Skill checks that might avoid combat
  3. Peaceful or neutral interactions
- When combat_trigger is true, include enemy details in gm_notes for combat initialization

DC SCALING (based on {difficulty_target} and {policy_profile}):
- Easy: 8-11, Medium: 12-15, Hard: 16-19, Very Hard: 20+
- Policy adjustments: {difficulty_target}
- Consider environmental modifiers from: {environmental_factors}

CONTEXT INTEGRATION REQUIREMENTS:
- **Narrative Context**: Advance story momentum based on player action and current state
- **Location Context**: Use environmental features and atmosphere meaningfully in scene and choices
- **Quest Context**: Progress objectives, respect time constraints and consequences
- **Policy Context**: Apply appropriate DC scaling and encounter budgets based on difficulty target
- **RAG Context**: Integrate retrieved lore and world information authentically into scenarios
- **Output Requirements**: Follow exact formatting specifications and choice count targets. Respond with ONLY a valid JSON object.

Generate the enhanced scenario now:"""
    
    debug_scenario_print("TOOL", f"🎯 Direct engine access prompt generated", {"prompt_length": len(prompt), "architecture_compliant": True})
    return prompt


# --------------------------------------------------------------------------- #
# Backstop: make the fiction true when the adjudicator forgot to
# --------------------------------------------------------------------------- #

#: Phrases in the adjudicator's findings that assert a STATE CHANGE, mapped to the
#: tool that must have been called to make it true. Deliberately narrow: only
#: unambiguous, mechanically-consequential claims, so a passing mention of the word
#: "rest" in scene-setting does not trigger a real long rest.
_STATE_CLAIM_PATTERNS: Dict[str, tuple] = {
    "take_rest": (
        "took a long rest", "takes a long rest", "take a long rest",
        "completed a long rest", "completes a long rest",
        "took a short rest", "takes a short rest",
        "rested until", "rests until", "made camp and rested",
        "night's rest", "nights rest", "slept until", "sleeps until",
    ),
    "travel_to_location": (
        "travelled to", "traveled to", "travels to", "journeyed to",
        "arrived at", "arrives at", "set out for", "sets out for",
        "made their way to", "reached the",
    ),
}


def _apply_unapplied_state_changes(findings: str, messages, game_engine=None) -> None:
    """Apply a state change the adjudicator DESCRIBED but never applied with a tool.

    The prompt forbids this in three places and cites a measured failure. It happened
    anyway: in a live Suite B run, "make camp and rest until morning" produced 1561
    chars describing a night's rest, `take_rest` was offered three times and never
    called, and no HP or clock movement followed. Prose cannot enforce a contract the
    model honours only most of the time, so the state gets the last word.

    Conservative by construction:
      * Only fires when the findings make an UNAMBIGUOUS claim (see the patterns).
      * Only fires when the corresponding tool was NOT already called this turn —
        double-applying a rest would be worse than missing one.
      * Goes through the real `@tool`, so the same validation, logging and clamping
        apply as when the model calls it. No parallel code path to drift.
      * Never raises: a backstop that breaks the turn is worse than the drift it
        prevents.
    """
    text = (findings or "").lower()
    if not text.strip():
        return

    already_called = set()
    for message in (messages or []):
        for call in (getattr(message, "tool_calls", None) or []):
            name = getattr(call, "tool_name", None)
            if name:
                already_called.add(name)

    try:
        from agents.dm_tools import DM_TOOLS
    except Exception:  # pragma: no cover - defensive
        return
    by_name = {getattr(t, "name", None): t for t in DM_TOOLS}

    for tool_name, phrases in _STATE_CLAIM_PATTERNS.items():
        if tool_name in already_called:
            continue
        matched = next((p for p in phrases if p in text), None)
        if matched is None:
            continue
        tool = by_name.get(tool_name)
        if tool is None:
            continue

        try:
            if tool_name == "take_rest":
                kind = "short" if "short rest" in text else "long"
                result = tool.invoke(kind=kind)
                logger.warning(
                    "🩹 Backstop: findings claimed %r but take_rest was never "
                    "called; applied a %s rest -> %s",
                    matched, kind, str(result)[:120])
            elif tool_name == "travel_to_location":
                # Only act on a destination we can name; guessing a place would be
                # worse than leaving the clock alone.
                destination = _destination_in(text)
                if not destination:
                    continue
                result = tool.invoke(destination=destination)
                logger.warning(
                    "🩹 Backstop: findings claimed %r but travel_to_location was "
                    "never called; travelled to %r -> %s",
                    matched, destination, str(result)[:120])
        except Exception as exc:  # noqa: BLE001 - never break the turn
            logger.debug("Backstop for %s did not apply: %s", tool_name, exc)


def _destination_in(text: str) -> str:
    """The named location the findings say the party reached, if any.

    Matched against the campaign's own locations rather than parsed out of prose, so
    the backstop can only ever travel somewhere that actually exists.
    """
    try:
        from agents.dm_tools import _CONTEXT

        engine = _CONTEXT.get("game_engine")
        locations = getattr(engine, "locations", None) or {}
        names = list(locations.keys()) if isinstance(locations, dict) else list(locations)
        if not names:
            context = getattr(engine, "get_location_context", None)
            if callable(context):
                names = list((context() or {}).get("known_locations") or [])
    except Exception:  # pragma: no cover - defensive
        return ""

    for name in names:
        if isinstance(name, str) and name and name.lower() in text:
            return name
    return ""


def format_scenario_response(scenario_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format the scenario response according to the required JSON schema.
    
    Args:
        scenario_data: Dictionary containing the scenario information
        
    Returns:
        Formatted dictionary with the complete scenario structure
    """
    debug_scenario_print("FORMAT_TOOL", "🎯 Formatting scenario response", {"scenario_keys": list(scenario_data.keys()) if scenario_data else None})
    
    # Handle None or invalid scenario_data
    if not scenario_data or not isinstance(scenario_data, dict):
        debug_scenario_print("FORMAT_TOOL", f"❌ Invalid scenario_data: {type(scenario_data)}")
        return {"error": "Invalid scenario data provided"}
    
    # Create properly formatted scenario according to shared contract
    formatted_scenario = {
        "scene": scenario_data.get("scene", "A mysterious scene unfolds before you."),
        "choices": scenario_data.get("choices", []),
        "effects": scenario_data.get("effects", {}),
        "hooks": scenario_data.get("hooks", []),
        "gm_notes": scenario_data.get("gm_notes", ""),
        "state_changes": scenario_data.get("state_changes", {}),
        "difficulty_used": scenario_data.get("difficulty_used", {}),
        "confidence": scenario_data.get("confidence", 0.8),
        "fallback": scenario_data.get("fallback", False)
    }
    
    # Validate and repair scenario structure using shared contract functions
    validation_errors = validate_scenario(formatted_scenario)
    if validation_errors:
        debug_scenario_print("FORMAT_TOOL", f"⚠️ Validation errors found: {validation_errors}")
        formatted_scenario = repair_scenario(formatted_scenario, validation_errors)
        debug_scenario_print("FORMAT_TOOL", "🔧 Scenario repaired after validation")
    
    debug_scenario_print("FORMAT_TOOL", "✅ Scenario formatted successfully", {"choices_count": len(formatted_scenario.get("choices", []))})
    
    return {"scenario": formatted_scenario}

# Haystack Components to replace Tools - Phase 2 Implementation
@component
class PromptBuilderComponent:
    """
    Haystack component to build comprehensive prompts for scenario generation.
    DTO COMPLIANCE: Uses direct engine access and RAGBlock parameter instead of DTO RAG access.
    """
    
    # `prompt_context` is emitted alongside the messages so Phase B (narration)
    # can see the same location/quest/lore/policy block the adjudication phase
    # saw. Without it the narration call would be told what happened but not
    # where, and would invent the setting.
    @component.output_types(messages=List[ChatMessage], prompt_context=str,
                            recent_scenes=List[str])
    def run(self, dto: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build comprehensive scenario generation prompt with RAGBlock TypedDict input.
        DTO COMPLIANCE: Uses engine references and separate RAG input.
        
        Args:
            dto: Streamlined DTO with engine references instead of context copies
            
        Returns:
            Dictionary with messages list for agent input
        """
        debug_scenario_print("COMPONENT", "🎭 PromptBuilderComponent with RAGBlock parameter - DTO COMPLIANT")
        
        
        # Use updated create_scenario_from_dto
        prompt = create_scenario_from_dto(dto)
        # Convert string prompt to ChatMessage list
        messages = [ChatMessage.from_user(prompt)]

        # Scenes the player has already been shown. Phase B rejects a reply that
        # repeats one: turns 8 and 9 of a 12-turn playtest returned a
        # byte-identical scene despite different player actions and fresh rolls.
        recent_scenes: List[str] = []
        engine = dto.get("_game_engine_ref")
        if engine is not None and hasattr(engine, "get_narrative_beats"):
            try:
                recent_scenes = list(engine.get_narrative_beats(4) or [])
            except Exception as e:
                debug_scenario_print("COMPONENT",
                                     f"could not read narrative beats: {e}")

        return {"messages": messages, "prompt_context": prompt,
                "recent_scenes": recent_scenes}


@component
class ScenarioValidatorComponent:
    """
    Haystack component to validate and format scenario responses.
    Replaces format_scenario_response_tool for better pipeline performance.
    """
    
    @component.output_types(validated_scenario=dict)
    def run(self, messages: List[ChatMessage],
            prompt_context: str = "",
            recent_scenes: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
        """
        Turn the adjudication phase's output into a validated scenario.

        Two-phase turn (see create_scenario_generator_agent): `messages` now
        carries Phase A's FACTUAL SUMMARY, not scene JSON. If it already contains
        JSON we use it (covers a caller that still does it in one call, and any
        test that feeds JSON directly); otherwise we run Phase B — narrate_scene,
        which has the schema enforced and no tools — to produce the scene.

        Args:
            messages: ChatMessages from the adjudication agent
            prompt_context: The original context block, passed to Phase B

        Returns:
            Dictionary with validated_scenario
        """
        debug_scenario_print("COMPONENT", "🎯 ScenarioValidatorComponent processing messages")
        
        # Extract scenario data from the messages.
        scenario_data = {}
        if messages:
            # Scan BACKWARDS for the last message that actually carries text.
            #
            # This used to read messages[-1] only. When the agent exhausts
            # max_agent_steps mid-loop the final message is a TOOL RESULT with no
            # text, so a scene the model had already written in an earlier message
            # was thrown away and the player got "A mysterious pause settles over
            # the scene." Two turns of a six-turn playtest ended that way.
            def _text_of(message) -> str:
                for attribute in ("text", "content"):
                    value = getattr(message, attribute, None)
                    if isinstance(value, str) and value.strip():
                        return value
                return ""

            response_text = ""
            for message in reversed(messages):
                # Skip tool-call/result messages; only assistant prose can hold
                # the scene JSON.
                if getattr(message, "tool_calls", None):
                    continue
                candidate = _text_of(message)
                if candidate:
                    response_text = candidate
                    break

            if not response_text:
                # Nothing anywhere: fall back to the plain last-message read so
                # behaviour is unchanged for the ordinary single-message case.
                response_text = _text_of(messages[-1]) or str(messages[-1])
            
            # DEBUG: Print the actual LLM response
            # debug_scenario_print("COMPONENT", "📝 LLM Response Text:")
            # logger.info(f"🔍 RAW LLM OUTPUT:\n{response_text}")
            # logger.info(f"🔍 Response Length: {len(response_text) if response_text else 0}")
            
            # Try to parse JSON from response with improved error handling
            if response_text:
                try:
                    import json
                    import re
                    
                    # Clean up the response text first
                    cleaned_text = response_text.strip()
                    
                    # Try multiple JSON extraction methods
                    json_str = None
                    
                    # Method 1: Find complete JSON object with proper bracket matching
                    bracket_count = 0
                    json_start = cleaned_text.find('{')
                    if json_start >= 0:
                        json_end = json_start
                        for i in range(json_start, len(cleaned_text)):
                            if cleaned_text[i] == '{':
                                bracket_count += 1
                            elif cleaned_text[i] == '}':
                                bracket_count -= 1
                                if bracket_count == 0:
                                    json_end = i + 1
                                    break
                        
                        if bracket_count == 0:  # Found complete JSON
                            json_str = cleaned_text[json_start:json_end]
                    
                    # Method 2: If bracket matching failed, try regex extraction
                    if not json_str:
                        json_match = re.search(r'\{.*\}', cleaned_text, re.DOTALL)
                        if json_match:
                            json_str = json_match.group(0)
                    
                    # Method 3: If still no JSON found, try simple start/end extraction
                    if not json_str:
                        json_start = cleaned_text.find('{')
                        json_end = cleaned_text.rfind('}') + 1
                        if json_start >= 0 and json_end > json_start:
                            json_str = cleaned_text[json_start:json_end]
                    
                    # DEBUG: Print extracted JSON string
                    # debug_scenario_print("COMPONENT", f"📝 Extracted JSON String:")
                    # logger.info(f"🔍 EXTRACTED JSON:\n{json_str}")
                    
                    # Parse the extracted JSON
                    if json_str:
                        # Try to fix common JSON issues before parsing
                        json_str = re.sub(r',\s*}', '}', json_str)  # Remove trailing commas before }
                        json_str = re.sub(r',\s*]', ']', json_str)  # Remove trailing commas before ]
                        
                        # Fix range values like "13-14" which are invalid JSON
                        json_str = re.sub(r':\s*(\d+)-(\d+)', r': \1', json_str)  # Replace ranges with first number
                        
                        # DEBUG: Print cleaned JSON
                        # debug_scenario_print("COMPONENT", f"📝 Cleaned JSON String:")
                        # logger.info(f"🔍 CLEANED JSON:\n{json_str}")
                        
                        scenario_data = json.loads(json_str)
                        debug_scenario_print("COMPONENT", "✅ Successfully parsed scenario JSON")
                    else:
                        raise ValueError("No JSON structure found in response")
                        
                except Exception as e:
                    debug_scenario_print("COMPONENT", f"⚠️ Failed to parse scenario JSON: {e}")

                    # Do NOT fabricate a scene from this text. In the two-phase
                    # turn this branch is the EXPECTED path: Phase A returns a
                    # terse factual summary ("Stealth 14 vs DC 13, success"), not
                    # JSON. The old code lifted the first long line into "scene",
                    # which meant the player could be shown the DM's mechanical
                    # notes verbatim, dressed up with two canned choices.
                    #
                    # Leave it empty and let Phase B narrate properly below.
                    scenario_data = {}
            else:
                debug_scenario_print("COMPONENT", "❌ No response text from LLM")
                scenario_data = {}

        # PHASE B. If we do not have a usable scene yet, the adjudication phase
        # gave us findings (or nothing) rather than scene JSON — that is the
        # NORMAL path now, not an error. Run the narration call, which has the
        # schema enforced and no tools.
        #
        # This replaces "A mysterious pause settles over the scene.", which two
        # turns of a six-turn playtest received because the single combined call
        # exhausted its steps without ever emitting JSON.
        if not str(scenario_data.get("scene", "")).strip():
            findings = ""
            if messages:
                parts = []
                for message in messages:
                    if getattr(message, "tool_calls", None):
                        continue
                    for attribute in ("text", "content"):
                        value = getattr(message, attribute, None)
                        if isinstance(value, str) and value.strip():
                            parts.append(value.strip())
                            break
                findings = "\n".join(parts[-3:])

            # BACKSTOP: apply a state change the adjudicator described but never
            # applied with a tool.
            #
            # The prompt already forbids this explicitly ("NEVER say the party
            # travelled, rested, or that time passed, unless you called the tool that
            # made it so"), and cites a live run where six turns advanced the clock by
            # zero hours. Measured again in a Suite B run AFTER that prompt was
            # written: "make camp and rest until morning" produced 1561 chars of
            # narration describing a night's rest, `take_rest` was offered to the
            # model three times, and it was never called — no HP restored, no clock
            # movement. Prose alone cannot enforce this; the model complies most of
            # the time and silently does not the rest of the time.
            #
            # So the state, not the prompt, gets the last word: if the findings say a
            # rest or a journey happened and no tool made it true, make it true here.
            _apply_unapplied_state_changes(findings, messages, game_engine=None)

            # recent_scenes lets Phase B reject a scene the player has already
            # been shown (turns 8 and 9 of a 12-turn playtest were identical).
            narrated = narrate_scene(findings, prompt_context,
                                     recent_scenes=recent_scenes)
            if str(narrated.get("scene", "")).strip():
                debug_scenario_print("COMPONENT", "✅ Phase B produced the scene")
                scenario_data = narrated
            else:
                # Genuinely nothing worked. Keep a fallback so a turn never
                # returns empty, but make it honest rather than mysterious.
                logger.error("❌ Both adjudication and narration failed to "
                             "produce a scene")
                scenario_data = {
                    "scene": ("The storm's noise swallows the moment; the "
                              "world seems to hold its breath."),
                    "choices": [
                        {
                            "id": "c1",
                            "title": "Try again",
                            "description": "Restate what you want to do",
                            "skill_hints": [],
                            "suggested_dc": 0,
                            "combat_trigger": False,
                        }
                    ],
                    "effects": {},
                    "hooks": [],
                    "gm_notes": "Both turn phases failed to produce a scene",
                    "fallback": True,
                }

        formatted_result = format_scenario_response(scenario_data)  # Reuse existing logic
        return {"validated_scenario": formatted_result}

def create_scenario_generator_agent(chat_generator: Optional[Any] = None) -> Agent:
    """
    Phase A of the turn: ADJUDICATE. Tools, no response schema.

    THE DESIGN ERROR THIS FIXES — this one call used to try to be two things at
    once: agentic (13 DM tools) and structured-output (a JSON schema). Gemini
    rejects that combination outright:

        400 INVALID_ARGUMENT "Function calling with a response mime type:
        'application/json' is unsupported"

    An earlier patch of mine papered over the 400 by silently DROPPING the schema
    whenever tools were present. That left the model told-by-prompt to emit
    schema-shaped JSON with nothing enforcing it, so it kept calling tools hunting
    for certainty and never wrote the plain-text message that satisfies
    exit_conditions=["text"]. Live turns burned all 10 steps and the player got
    "A mysterious pause settles over the scene." Caching the reads and raising the
    ceiling 6->10 treated symptoms; the two modes were fighting.

    Now each call does ONE job:
      Phase A (this agent)      tools, NO schema   -> gather facts, roll, mutate
      Phase B (narrate_scene)   schema, NO tools   -> write the scene JSON

    Note this is a Gemini API constraint, not a Haystack one: the same request
    from LangGraph or the raw SDK returns the same 400.

    Args:
        chat_generator: Optional chat generator (uses LLM config if None)

    Returns:
        A Haystack Agent that adjudicates and then summarises what it did.
    """

    # NO response_schema here: this phase must be free to call tools, and the
    # schema would make every call 400.
    if chat_generator is None:
        config_manager = get_global_config_manager()
        generator = config_manager.create_generator("scenario_generator")
        logger.info("🎯 Scenario adjudication generator created (tools, no schema)")
    else:
        generator = chat_generator

    simplified_system_prompt = """
You are the adjudication half of a D&D Dungeon Master. Your job is to establish
FACTS, not to write prose. Another call will write the scene from your findings.

WHAT TO DO, IN ORDER:
1. Read the state you need — get_world_state, get_party_state,
   get_character_state. Call each AT MOST ONCE; they cannot change while you work.
2. Look up any rule the action depends on — query_rules. Never invent a rule,
   cost or DC.
3. Resolve the player's attempt — roll_skill_check for anything uncertain. You do
   not decide outcomes; the dice do.
4. APPLY the consequences with a tool. This step is NOT optional — narrating a
   change you did not apply leaves the fiction and the game state disagreeing, and
   the player will notice on the next turn.

   Map the player's action to the tool that makes it TRUE:
     goes somewhere / sets out / heads for      -> travel_to_location
     rests / makes camp / sleeps                -> take_rest
     is hurt / takes a hit / falls              -> apply_damage
     is healed / bandaged / Regrowth            -> apply_healing
     uses a Surge / draws in Stormlight         -> spend_stormlight
     finishes an objective / achieves a goal    -> advance_quest
     earns a reward / defeats a foe / learns    -> award_experience
     tends a companion at 0 HP                  -> stabilize_dying

   If the action moves the party, time, HP, Stormlight, XP or a quest, a tool call
   is REQUIRED. If it genuinely changes nothing, say so in your summary.
5. THEN STOP CALLING TOOLS and write a short plain-text summary of what actually
   happened: the rolls and their results, what changed, what is now true.

Hard rules:
- NEVER state that an attempt succeeded or failed without calling
  roll_skill_check.
- NEVER describe damage or healing you did not apply with a tool, or the fiction
  and the character sheets will drift apart.
- NEVER say the party travelled, rested, or that time passed, unless you called the
  tool that made it so. Measured in a live run: six turns including an explicit
  "I travel onwards" and "I make camp and take a long rest" advanced the in-world
  clock by ZERO hours, because the model narrated both instead of applying them.
- spend_stormlight can REFUSE. If affordable is false, say the Surge failed for
  want of Stormlight.
- search_lore answers "who/what/where" questions about the world. USE IT when the
  player asks about Roshar rather than about a rule, and ground the answer in what it
  returns. It has no dice or DCs, so never derive a mechanic from it — that is what
  query_rules is for.
- If a tool reports "unchanged": true, you have already called it. Stop gathering
  and write your summary.

YOUR OUTPUT IS NOT PLAYER-FACING. Write a terse factual summary — a few
sentences. Do NOT write scene prose, do NOT offer choices, do NOT emit JSON.
Writing that summary is how you end your turn; if you keep calling tools you will
run out of steps and the player will get a generic fallback instead of a scene.
"""


    # Plan 3.1/3.2: give the DM real tools and a real loop.
    #
    # This was `tools=[], max_agent_steps=1` — a single-shot call with no way to
    # check state or roll dice. The audit's blunt verdict ("this is an LLM-call
    # pipeline, not an agentic system") was exactly this line. The model emitted
    # a suggested_dc nothing enforced and described mechanics it could not
    # resolve.
    #
    # Now it can look up real state, query canonical rules and roll real dice
    # before writing the scene: the model decides WHAT is attempted, code
    # decides WHAT HAPPENS.
    try:
        from agents.dm_tools import DM_TOOLS
        dm_tools = DM_TOOLS
    except Exception as e:  # pragma: no cover - defensive
        logger.warning(f"⚠️ DM tools unavailable, falling back to one-shot: {e}")
        dm_tools = []

    agent = Agent(
        chat_generator=generator,
        tools=dm_tools,
        system_prompt=simplified_system_prompt,
        # Exit as soon as the model writes text instead of calling a tool. That
        # text is now a short FACTUAL SUMMARY, not the scene — which is why this
        # phase can actually reach an exit: summarising is a much easier target
        # than producing schema-shaped JSON with no schema to guide it.
        exit_conditions=["text"],
        # Adjudication only: read state, look up a rule, roll, apply, summarise.
        # 6 was too tight when this call also had to write the scene; that job
        # now belongs to narrate_scene(), so the budget is for tools alone.
        max_agent_steps=10 if dm_tools else 1,
        raise_on_tool_invocation_failure=False,
        state_schema={}
    )
    logger.info(
        f"🎯 Scenario agent created with {len(dm_tools)} DM tools, "
        f"max_agent_steps={10 if dm_tools else 1}"
    )

    return agent


# ---------------------------------------------------------------------------
# Phase B of the turn: NARRATE. Schema enforced, no tools.
# ---------------------------------------------------------------------------

NARRATION_SYSTEM_PROMPT = """
You are an expert D&D Dungeon Master writing the player-facing scene for one turn
on Roshar. The mechanics have ALREADY been resolved by another call; you are given
its findings. Your only job is to turn them into vivid prose and real choices.

YOU MAY NOT CHANGE WHAT HAPPENED. The findings are authoritative:
- If a roll failed, narrate the failure. Do not soften or reverse it.
- If damage was applied, the character is hurt by exactly that much.
- If a Surge was refused for want of Stormlight, it did not happen.
- Never invent a roll, a rule, a DC or a state change that is not in the findings.

SCENE WRITING:
- Open with the immediate consequence of the player's specific action.
- Use several senses; make the highstorm-scarred world feel physical.
- Weave in the location, the quest, and any retrieved lore naturally.
- End at a genuine decision point.
- 2-5 paragraphs. Vivid, not florid.

THIS SCENE MUST BE NEW. You are shown recent scenes for CONTINUITY — to know what
has already happened, what the party learned, and what is still unresolved. They
are context, NOT a template:
- NEVER repeat a previous scene's wording. Do not restate its opening sentence.
- The player has just done something specific. Describe THAT action's outcome,
  which by definition has not been narrated before.
- If the action closely resembles an earlier one, show what is DIFFERENT this
  time: what the party now knows, what has changed, what the repetition costs
  them. Time has passed; the world has moved.
- Advance the situation. A scene that leaves the party exactly where it started
  has failed, even if the prose is good.

CHOICES:
- Offer 3-4 choices that emerge from THIS scene, not a template.
- Vary the approach: bold vs cautious, direct vs indirect, patient vs immediate.
- Mark a choice **Skill Check (DC X)** or **Combat** only when it genuinely is one.
- DC guidance: Easy 8-11, Medium 12-15, Hard 16-19, Very Hard 20+.

state_changes.location must be a bare place NAME (e.g. "Kholinar") and must be
omitted entirely unless the party actually MOVED. Never a sentence.

Return ONLY the JSON object required by the schema.
"""


def _scenes_are_duplicates(scene: str, earlier: str) -> bool:
    """
    True if `scene` is a repeat of `earlier`.

    Not just an exact match: the observed failure was byte-identical, but a model
    told "don't repeat" will happily change three words and re-send the same
    scene. Two independent signals, either of which is damning:

      - the opening 120 characters match (a scene that starts identically reads
        as identical to the player, whatever happens later)
      - overall similarity is very high

    The 0.90 threshold is deliberately high. Consecutive scenes in one location
    legitimately share vocabulary — wind, rockbuds, the smell of ozone — so a
    lower bar would reject good, genuinely new prose.
    """
    from difflib import SequenceMatcher

    def _normalise(text: str) -> str:
        return " ".join(text.lower().split())

    left, right = _normalise(scene), _normalise(earlier)
    if not left or not right:
        return False
    if left == right:
        return True
    if len(left) >= 120 and len(right) >= 120 and left[:120] == right[:120]:
        return True
    return SequenceMatcher(None, left, right).ratio() >= 0.90


def narrate_scene(findings: str, prompt_context: str,
                  chat_generator: Optional[Any] = None,
                  recent_scenes: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Turn Phase A's adjudicated findings into scene JSON (Phase B).

    This call has the response schema ENFORCED and NO tools, which is the whole
    point of the split: Gemini rejects tools+schema together, so the previous
    single call had its schema silently dropped and never converged on an output.
    Here the schema is real, there is no tool loop, and therefore no way to spin.

    Args:
        findings: Phase A's factual summary of what actually happened
        prompt_context: The original context block (location, quest, lore, policy)
        chat_generator: Optional override, for tests
        recent_scenes: Scenes already shown to the player. A reply that repeats
            one is REJECTED and retried — see below.

    Returns:
        Parsed scenario dict, or {} if the call could not produce one.
    """
    if chat_generator is None:
        config_manager = get_global_config_manager()
        generator = config_manager.create_generator(
            "scenario_generator", response_schema=SCENARIO_RESPONSE_SCHEMA)
    else:
        generator = chat_generator

    user_message = (
        f"{prompt_context}\n\n"
        f"=== WHAT ACTUALLY HAPPENED (authoritative, do not contradict) ===\n"
        f"{findings or '(no mechanical resolution was needed this turn)'}\n\n"
        f"Write the scene and choices as JSON."
    )

    messages = [
        ChatMessage.from_system(NARRATION_SYSTEM_PROMPT),
        ChatMessage.from_user(user_message),
    ]

    def _validate(text: str) -> Dict[str, Any]:
        from components.retry_with_reasoning import (
            extract_json, require_keys, ValidationFailure)

        payload = extract_json(text)
        require_keys(payload, ["scene", "choices"])
        scene = str(payload.get("scene", "")).strip()
        if not scene:
            raise ValidationFailure(
                "Your 'scene' was empty.",
                hint="Write 2-5 paragraphs of scene prose in the 'scene' field.")

        # REJECT A REPEAT. In a 12-turn playtest turns 8 and 9 returned a
        # byte-identical 2339-char scene, even though turn 9 had a different
        # player action ("listen carefully" vs "search the area") and rolled two
        # fresh skill checks. The prompt shows recent scenes for continuity and
        # says "maintain continuity with these", so the model had the previous
        # scene in front of it and echoed it.
        #
        # Prompt wording alone is not enough (that lesson has been learned
        # repeatedly here), so a duplicate is rejected and fed back with the
        # reason, which is exactly what the 3.3 retry path is for.
        for previous in (recent_scenes or []):
            earlier = str(previous or "").strip()
            if not earlier:
                continue
            if _scenes_are_duplicates(scene, earlier):
                raise ValidationFailure(
                    "That scene repeats one the player has already been shown.",
                    hint=("Write a NEW scene describing the outcome of the "
                          "player's CURRENT action. Recent scenes are context for "
                          "continuity, not text to reuse. Show what is different "
                          "this time and move the situation forward."),
                )
        return payload

    try:
        # Reuse the 3.3 retry path: a rejected response is fed back with the
        # specific reason rather than replaced by a canned scene.
        from components.retry_with_reasoning import generate_with_retry

        scenario, info = generate_with_retry(
            generator, messages, validate=_validate,
            max_attempts=2, fallback=lambda: {}, label="scene narration")
        if info.get("used_fallback"):
            logger.error("❌ Narration failed after retries; no scene produced")
            return {}
        if info.get("recovered"):
            logger.info(f"✅ Narration recovered on attempt {info['attempts']}")
        return scenario
    except Exception as e:
        logger.error(f"❌ Narration call failed: {e}")
        return {}


# Factory function for integration with existing orchestrator
def create_scenario_agent_for_orchestrator() -> Agent:
    """Create scenario generator agent configured for orchestrator integration"""
    return create_scenario_generator_agent()

def create_fallback_scenario(player_input: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Create a fallback scenario when the main agent fails
    Used by test suite and error handling
    """
    if context is None:
        context = {}
        
    location = context.get("location", "unknown area")
    
    return {
        "scene": f"You {player_input} in the {location}. The world responds to your action.",
        "choices": [
            {
                "id": "c1",
                "title": "Continue exploring",
                "description": "Look around and see what happens next",
                "skill_hints": ["perception"],
                "suggested_dc": 12,
                "combat_trigger": False
            },
            {
                "id": "c2",
                "title": "Be cautious",
                "description": "Proceed carefully and watch for danger",
                "skill_hints": ["insight"],
                "suggested_dc": 10,
                "combat_trigger": False
            }
        ],
        "effects": {},
        "hooks": [],
        "processing_metadata": {
            "type": "fallback_scenario",
            "reason": "Agent failure or missing components"
        }
    }

# Compatibility alias for test suite
ScenarioGeneratorAgent = create_scenario_generator_agent


# Example usage and testing
if __name__ == "__main__":
    # Create the agent
    agent = create_scenario_generator_agent()
    
    # Test scenario generation
    test_action = "I want to search the ancient library for clues about the missing artifact"
    test_context = {
        "difficulty": "medium",
        "location": "Ancient Library",
        "environment": {"lighting": "dim", "atmosphere": "dusty"},
        "average_party_level": 3
    }
    
    # Create test message
    user_message = f"""
    Player Action: {test_action}
    Game Context: {test_context}
    
    Generate a D&D scenario response for this action.
    """
    
    try:
        # Run the agent
        response = agent.run(messages=[ChatMessage.from_user(user_message)])
        
        print("=== Scenario Generator Agent Test ===")
        print("Messages:")
        for msg in response["messages"]:
            logger.info(f"{msg.role}: {msg.text}")
        
        # Check if scenario structure was created
        if hasattr(response, 'get') and response.get("scenario_structure"):
            print("\n✅ Scenario Structure Created:")
            print(json.dumps(response["scenario_structure"], indent=2))
        
    except Exception as e:
        logger.error(f"Scenario Agent test failed: {e}")