"""
Scenario Generator Agent - Creative scenario generation following revised plan contract
Uses proper Haystack Agent framework with tools and system prompts
"""

import json
from typing import Dict, Any, List, Optional
from haystack.components.agents import Agent
from haystack.dataclasses import ChatMessage
from haystack.tools import tool
from config.llm_config import get_global_config_manager
from shared_contract import Scenario, Choice, validate_scenario, repair_scenario, minimal_fallback


@tool(
    outputs_to_state={"scenario_result": {"source": "."}}
)
def create_scenario_from_dto(dto: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create scenario from DTO with integrated validation and repair.
    
    Args:
        dto: Request DTO with action, context, and RAG data
        
    Returns:
        Updated DTO with validated scenario or fallback
    """
    # Extract information from DTO
    player_action = dto.get("player_input", dto.get("action", ""))
    game_context = dto.get("context", {})
    rag_blocks = dto.get("rag_blocks", [])
    
    # Build context for scenario generation
    context_info = []
    if game_context.get("location"):
        context_info.append(f"Location: {game_context['location']}")
    if game_context.get("difficulty"):
        context_info.append(f"Difficulty: {game_context['difficulty']}")
    if rag_blocks:
        context_info.append(f"Retrieved context: {len(rag_blocks)} relevant documents")
    
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
    
    # Phase 3: Scenario Schema Validation with single repair attempt
    errors = validate_scenario(raw_scenario)
    
    if errors:
        # Single repair attempt
        raw_scenario = repair_scenario(raw_scenario, errors)
        dto["debug"]["scenario_repaired"] = True
        
        # Validate again after repair
        errors = validate_scenario(raw_scenario)
        
    if errors:
        # Still invalid after repair - use fallback
        dto["debug"]["scenario_errors"] = errors
        dto["fallback"] = True
        dto["scenario"] = minimal_fallback(dto)
    else:
        # Valid scenario
        dto["scenario"] = raw_scenario
        dto["fallback"] = False
    
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
    errors = validate_scenario(scenario)
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "can_repair": True,
        "repair_available": len(errors) > 0
    }


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