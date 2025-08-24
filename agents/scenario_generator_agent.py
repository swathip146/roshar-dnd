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
from haystack.tools import tool
from config.llm_config import get_global_config_manager
from shared_contract import Scenario, Choice, validate_scenario, repair_scenario, minimal_fallback

def debug_scenario_print(category: str, message: str, data: Any = None):
    """Centralized debug printing for scenario agent"""
    if DEBUG_SCENARIO_AGENT:
        timestamp = time.strftime('%H:%M:%S')
        print(f"🐛 SCENARIO [{timestamp}] {category}: {message}")
        if data is not None and DEBUG_SCENARIO_TOOLS:
            if isinstance(data, dict) and len(str(data)) > 300:
                print(f"    📊 Data keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
            else:
                print(f"    📊 Data: {data}")


@tool(
    outputs_to_state={"scenario_result": {"source": "."}}
)
def create_scenario_from_dto(dto: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create scenario from DTO with integrated validation and repair.
    
    Args:
        dto: Request DTO with action, context, and RAG data (can be dict or JSON string)
        
    Returns:
        Updated DTO with validated scenario or fallback
    """
    debug_scenario_print("TOOL", "🎭 create_scenario_from_dto called", {"dto_type": type(dto), "dto_preview": str(dto)[:100] if dto else None})
    
    # Handle string representation of DTO (parse JSON)
    if isinstance(dto, str):
        debug_scenario_print("TOOL", "🔄 Converting string DTO to dict")
        try:
            import json
            dto = json.loads(dto.replace("'", '"'))  # Handle single quotes
            debug_scenario_print("TOOL", "✅ String DTO conversion successful")
        except (json.JSONDecodeError, ValueError) as e:
            debug_scenario_print("TOOL", f"💥 Failed to parse DTO string: {e}")
            return {
                "scenario": minimal_fallback({}),
                "fallback": True,
                "debug": {"error": f"Failed to parse DTO string: {e}", "original_dto": str(dto)[:200]}
            }
    
    # Handle None or invalid DTO
    if not dto or not isinstance(dto, dict):
        debug_scenario_print("TOOL", f"❌ Invalid DTO: {type(dto)}")
        return {
            "scenario": minimal_fallback({}),
            "fallback": True,
            "debug": {"error": f"Invalid DTO type: {type(dto)}, expected dict", "dto_content": str(dto)[:200]}
        }
    
    # Ensure debug section exists
    if "debug" not in dto:
        dto["debug"] = {}
    
    # Extract information from DTO with null safety
    player_action = dto.get("player_input", dto.get("action", ""))
    game_context = dto.get("context", {})
    rag_blocks = dto.get("rag_blocks", [])
    
    # Ensure context is a dict
    if not isinstance(game_context, dict):
        game_context = {}
    
    # Ensure rag_blocks is a list
    if not isinstance(rag_blocks, list):
        rag_blocks = []
    
    debug_scenario_print("TOOL", f"📋 Extracted DTO data", {"player_action": player_action, "context_keys": list(game_context.keys()) if game_context else [], "rag_blocks_count": len(rag_blocks)})
    
    # Build context for scenario generation with null safety
    context_info = []
    if game_context and isinstance(game_context, dict):
        if game_context.get("location"):
            context_info.append(f"Location: {game_context['location']}")
        if game_context.get("difficulty"):
            context_info.append(f"Difficulty: {game_context['difficulty']}")
    if rag_blocks and isinstance(rag_blocks, list):
        context_info.append(f"Retrieved context: {len(rag_blocks)} relevant documents")
    
    debug_scenario_print("TOOL", f"🏗️ Building scenario with context", {"context_info": context_info})
    
    # Generate raw scenario (this would normally call LLM)
    # For now, create a structured example that follows the schema
    raw_scenario = {
        "scene": f"As you {player_action.lower()}, the environment around you responds. {' '.join(context_info)}",
        "choices": [
            {
                "id": "c1",
                "title": "Proceed carefully",
                "description": f"Continue with your action but remain cautious about potential consequences",
                "skill_hints": ["perception", "stealth"],
                "suggested_dc": 12,
                "combat_trigger": False
            },
            {
                "id": "c2",
                "title": "Act decisively",
                "description": f"Take bold action without hesitation",
                "skill_hints": ["athletics", "intimidation"],
                "suggested_dc": 15,
                "combat_trigger": False
            }
        ],
        "effects": {},
        "hooks": []
    }
    
    debug_scenario_print("TOOL", f"🎯 Raw scenario created", {"scene_length": len(raw_scenario["scene"]), "choices_count": len(raw_scenario["choices"])})
    
    # Phase 3: Scenario Schema Validation with single repair attempt
    if DEBUG_VALIDATION:
        debug_scenario_print("VALIDATION", "🔍 Starting scenario validation")
    errors = validate_scenario(raw_scenario)
    
    if errors:
        debug_scenario_print("VALIDATION", f"⚠️ Validation errors found: {errors}")
        # Single repair attempt
        raw_scenario = repair_scenario(raw_scenario, errors)
        dto["debug"]["scenario_repaired"] = True
        debug_scenario_print("VALIDATION", "🔧 Scenario repair attempted")
        
        # Validate again after repair
        errors = validate_scenario(raw_scenario)
        if errors:
            debug_scenario_print("VALIDATION", f"❌ Validation still failing after repair: {errors}")
        else:
            debug_scenario_print("VALIDATION", "✅ Scenario repair successful")
        
    if errors:
        # Still invalid after repair - use fallback
        debug_scenario_print("TOOL", "🆘 Using minimal fallback due to persistent validation errors")
        dto["debug"]["scenario_errors"] = errors
        dto["fallback"] = True
        dto["scenario"] = minimal_fallback(dto)
    else:
        # Valid scenario
        debug_scenario_print("TOOL", "✅ Valid scenario created")
        dto["scenario"] = raw_scenario
        dto["fallback"] = False
    
    debug_scenario_print("TOOL", f"🏁 Scenario creation complete", {"fallback_used": dto.get("fallback", False)})
    return dto


@tool
def validate_scenario_output(scenario: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate scenario output using shared contract validation.
    
    Args:
        scenario: Scenario data to validate
        
    Returns:
        Validation results with errors and repair suggestions
    """
    debug_scenario_print("TOOL", "🔍 validate_scenario_output called", {"scenario_keys": list(scenario.keys()) if scenario else None})
    
    errors = validate_scenario(scenario)
    result = {
        "valid": len(errors) == 0,
        "errors": errors,
        "can_repair": True,
        "repair_available": len(errors) > 0
    }
    
    debug_scenario_print("TOOL", f"✅ Validation complete", {"valid": result["valid"], "error_count": len(errors)})
    return result


def create_scenario_generator_agent(chat_generator: Optional[Any] = None) -> Agent:
    """
    Create a Haystack Agent for D&D scenario generation with Phase 3 validation.
    
    Args:
        chat_generator: Optional chat generator (uses LLM config if None)
        
    Returns:
        Configured Haystack Agent for scenario generation with validation
    """
    
    # Use LLM config manager to get appropriate generator
    if chat_generator is None:
        config_manager = get_global_config_manager()
        generator = config_manager.create_generator("scenario_generator")
    else:
        generator = chat_generator
    
    system_prompt = """
You are a D&D scenario generator that MUST output valid JSON following the exact schema.

WORKFLOW:
1. Use create_scenario_from_dto to generate scenarios with built-in validation
2. The tool will automatically validate and repair scenarios if needed
3. If validation fails after repair, a fallback scenario will be provided

SCENARIO SCHEMA (strict):
{
  "scene": "string (2-3 sentences)",
  "choices": [
    {
      "id": "c1",
      "title": "string",
      "description": "string",
      "skill_hints": ["skill1", "skill2"],
      "suggested_dc": 12,
      "combat_trigger": false
    }
  ],
  "effects": {},
  "hooks": []
}

VALIDATION RULES:
- scene, choices, effects, hooks are REQUIRED
- Each choice MUST have: id, title, description, skill_hints, suggested_dc, combat_trigger
- suggested_dc must be integer 8-20
- skill_hints must be array of strings
- combat_trigger must be boolean

The create_scenario_from_dto tool handles all validation and repair automatically.
Always use this tool - never return raw JSON directly.
"""

    agent = Agent(
        chat_generator=generator,
        tools=[create_scenario_from_dto, validate_scenario_output],
        system_prompt=system_prompt,
        exit_conditions=["create_scenario_from_dto"],
        max_agent_steps=3,
        raise_on_tool_invocation_failure=False,
        state_schema={
            "scenario_result": {"type": dict}
        }
    )
    
    return agent


def create_fallback_scenario(action: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a validated fallback scenario when the agent fails to generate one.
    This function always produces a valid scenario according to the schema.
    
    Args:
        action: Player action
        context: Game context
        
    Returns:
        Fallback scenario following validated contract specification
    """
    difficulty = context.get("difficulty", "medium")
    location = context.get("location", "area")
    
    # Set DCs based on difficulty (simplified to integer)
    dc_map = {
        "easy": 10,
        "medium": 15,
        "hard": 18
    }
    
    base_dc = dc_map.get(difficulty, 15)
    
    # Create scenario that will pass validation
    scenario = {
        "scene": f"You consider your options in this {location}, weighing the consequences of your intended action: '{action}'.",
        "choices": [
            {
                "id": "c1",
                "title": "Proceed carefully",
                "description": "Move forward with your plan, but take precautions to avoid complications",
                "skill_hints": ["perception", "stealth"],
                "suggested_dc": base_dc,
                "combat_trigger": False
            },
            {
                "id": "c2",
                "title": "Act boldly",
                "description": "Take direct action without hesitation",
                "skill_hints": ["intimidation", "athletics"],
                "suggested_dc": base_dc + 2,
                "combat_trigger": False
            }
        ],
        "effects": {},
        "hooks": []
    }
    
    # Ensure the fallback passes validation
    errors = validate_scenario(scenario)
    if errors:
        scenario = repair_scenario(scenario, errors)
    
    return scenario


# Factory function for integration with existing orchestrator
def create_scenario_agent_for_orchestrator() -> Agent:
    """Create scenario generator agent configured for orchestrator integration"""
    return create_scenario_generator_agent()


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
            print(f"{msg.role}: {msg.text}")
        
        # Check if scenario structure was created
        if hasattr(response, 'get') and response.get("scenario_structure"):
            print("\n✅ Scenario Structure Created:")
            print(json.dumps(response["scenario_structure"], indent=2))
        
    except Exception as e:
        print(f"❌ Agent test failed: {e}")
        print("Using fallback scenario:")
        fallback = create_fallback_scenario(test_action, test_context)
        print(json.dumps(fallback, indent=2))