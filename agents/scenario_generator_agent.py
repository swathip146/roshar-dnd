"""
Scenario Generator Agent - Creative scenario generation following revised plan contract
Uses proper Haystack Agent framework with tools and system prompts
"""

import json
from typing import Dict, Any, List, Optional
from haystack.components.agents import Agent
from haystack.components.generators.chat import OpenAIChatGenerator
from haystack.dataclasses import ChatMessage
from haystack.tools import tool
from hwtgenielib.components.generators.chat import AppleGenAIChatGenerator


@tool
def create_scenario_structure(scene: str, choices: List[Dict[str, Any]], 
                            effects: List[Dict[str, Any]], hooks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Create a structured D&D scenario following the revised plan contract.
    
    Args:
        scene: Narrative description of what happens
        choices: List of player choices with skill hints and DCs
        effects: List of game state effects
        hooks: List of quest progression hooks
    
    Returns:
        Structured scenario data matching contract specification
    """
    return {
        "scene": scene,
        "choices": choices,
        "effects": effects,
        "hooks": hooks
    }


@tool 
def validate_scenario_contract(scenario_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Validate that scenario data matches the revised plan contract.
    
    Args:
        scenario_data: The scenario data to validate
        
    Returns:
        Validation results with any errors or warnings
    """
    errors = []
    warnings = []
    
    # Check required fields
    required_fields = ["scene", "choices", "effects", "hooks"]
    for field in required_fields:
        if field not in scenario_data:
            errors.append(f"Missing required field: {field}")
    
    # Validate choices structure
    if "choices" in scenario_data:
        for i, choice in enumerate(scenario_data["choices"]):
            choice_required = ["id", "title", "description", "skill_hints", "suggested_dc", "combat_trigger"]
            for field in choice_required:
                if field not in choice:
                    errors.append(f"Choice {i} missing field: {field}")
            
            # Validate DC structure
            if "suggested_dc" in choice:
                dc_data = choice["suggested_dc"]
                if not isinstance(dc_data, dict):
                    errors.append(f"Choice {i} suggested_dc must be a dictionary")
                else:
                    expected_dcs = ["easy", "medium", "hard"]
                    for dc_level in expected_dcs:
                        if dc_level not in dc_data:
                            warnings.append(f"Choice {i} missing DC level: {dc_level}")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }


def create_scenario_generator_agent(chat_generator: Optional[Any] = None) -> Agent:
    """
    Create a Haystack Agent for D&D scenario generation following the revised plan contract.
    
    Args:
        chat_generator: Optional chat generator (defaults to OpenAI)
        
    Returns:
        Configured Haystack Agent for scenario generation
    """
    
    # Use OpenAI by default, but allow override for hwtgenielib
    if chat_generator is None:
        generator = OpenAIChatGenerator(model="gpt-4o-mini")
    else:
        generator = chat_generator
    
    system_prompt = """
You are a D&D Dungeon Master assistant specializing in scenario generation.

Your task is to generate structured D&D scenarios that follow the exact contract specification:

SCENARIO CONTRACT:
- scene: A narrative description (2-3 sentences) of what happens
- choices: 2-4 meaningful player options, each with:
  - id: Unique identifier (c1, c2, etc.)
  - title: Short action title
  - description: Detailed description of the action
  - skill_hints: Array of relevant D&D skills
  - suggested_dc: Object with "easy", "medium", "hard" DC values
  - combat_trigger: Boolean indicating if this leads to combat
- effects: Array of game state changes:
  - type: "flag", "condition", or "state_change"
  - name: Effect name
  - value: Effect value
- hooks: Array of quest progression updates:
  - quest: Quest identifier
  - progress: "advance", "complete", "fail", or "branch"

IMPORTANT RULES:
1. Always use the create_scenario_structure tool to format your response
2. DCs should be appropriate for the context (easy: 8-12, medium: 13-17, hard: 18-22)
3. Include realistic skill hints for each choice
4. Effects should reflect logical consequences of player actions
5. Hooks should advance relevant story elements
6. Keep scenes engaging but concise
7. Provide meaningful choices that matter

When given a player action and context, generate an appropriate scenario response using the tools available.
"""

    agent = Agent(
        chat_generator=generator,
        tools=[create_scenario_structure, validate_scenario_contract],
        system_prompt=system_prompt,
        exit_conditions=["create_scenario_structure"],
        max_agent_steps=5,
        raise_on_tool_invocation_failure=False
    )
    
    return agent


def create_fallback_scenario(action: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a fallback scenario when the agent fails to generate one.
    
    Args:
        action: Player action
        context: Game context
        
    Returns:
        Fallback scenario following contract specification
    """
    difficulty = context.get("difficulty", "medium")
    location = context.get("location", "area")
    
    # Set DCs based on difficulty
    dc_map = {
        "easy": {"easy": 8, "medium": 12, "hard": 16},
        "medium": {"easy": 10, "medium": 15, "hard": 20},
        "hard": {"easy": 12, "medium": 17, "hard": 22}
    }
    
    dcs = dc_map.get(difficulty, dc_map["medium"])
    
    return {
        "scene": f"You consider your options in this {location}, weighing the consequences of your intended action: '{action}'.",
        "choices": [
            {
                "id": "c1",
                "title": "Proceed carefully",
                "description": "Move forward with your plan, but take precautions to avoid complications",
                "skill_hints": ["perception", "stealth"],
                "suggested_dc": dcs,
                "combat_trigger": False
            },
            {
                "id": "c2",
                "title": "Act boldly",
                "description": "Take direct action without hesitation",
                "skill_hints": ["intimidation", "athletics"],
                "suggested_dc": {k: v + 2 for k, v in dcs.items()},
                "combat_trigger": False
            },
            {
                "id": "c3",
                "title": "Reconsider approach",
                "description": "Step back and look for alternative solutions",
                "skill_hints": ["investigation", "insight"],
                "suggested_dc": {k: v - 2 for k, v in dcs.items()},
                "combat_trigger": False
            }
        ],
        "effects": [
            {
                "type": "flag",
                "name": "fallback_scenario_used",
                "value": True
            }
        ],
        "hooks": [
            {
                "quest": "current_situation",
                "progress": "advance"
            }
        ]
    }


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