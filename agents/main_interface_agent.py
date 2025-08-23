"""
Main Interface Agent - User interaction management
Handles player input parsing, command interpretation, and response formatting using Haystack Agent framework
"""

from typing import Dict, Any, Optional, List
from haystack.components.agents import Agent
from haystack.components.generators.chat import OpenAIChatGenerator
from haystack.dataclasses import ChatMessage
from haystack.tools import tool


@tool
def parse_player_input(player_input: str, game_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse and interpret player input to determine intent and extract key information.
    
    Args:
        player_input: Raw player input text
        game_context: Current game state and context
        
    Returns:
        Parsed input with intent, action type, and extracted parameters
    """
    input_lower = player_input.lower().strip()
    
    # Determine input type and intent
    intent_mappings = {
        # Combat actions
        "combat": ["attack", "fight", "hit", "strike", "cast", "spell", "defend", "dodge"],
        # Movement actions
        "movement": ["go", "move", "walk", "run", "travel", "enter", "exit", "leave"],
        # Investigation actions
        "investigation": ["search", "look", "examine", "inspect", "investigate", "check"],
        # Social actions
        "social": ["talk", "speak", "say", "ask", "tell", "persuade", "intimidate", "negotiate"],
        # Skill actions
        "skill": ["climb", "jump", "swim", "hide", "sneak", "pick", "unlock", "disable"],
        # Meta commands
        "meta": ["help", "save", "load", "quit", "status", "inventory", "stats"]
    }
    
    # Determine primary intent
    primary_intent = "general"
    confidence = 0.0
    
    for intent, keywords in intent_mappings.items():
        matches = sum(1 for keyword in keywords if keyword in input_lower)
        intent_confidence = matches / len(keywords) if keywords else 0
        
        if intent_confidence > confidence:
            confidence = intent_confidence
            primary_intent = intent
    
    # Extract target/object if present
    target = None
    common_targets = ["door", "chest", "npc", "guard", "merchant", "dragon", "goblin", "treasure"]
    for potential_target in common_targets:
        if potential_target in input_lower:
            target = potential_target
            break
    
    # Determine if this needs skill check
    skill_check_needed = primary_intent in ["combat", "skill", "investigation"]
    
    return {
        "original_input": player_input,
        "primary_intent": primary_intent,
        "confidence": confidence,
        "target": target,
        "skill_check_needed": skill_check_needed,
        "processed_action": input_lower,
        "complexity": "complex" if len(player_input.split()) > 5 else "simple"
    }


@tool
def determine_response_routing(parsed_input: Dict[str, Any], game_context: Dict[str, Any]) -> Dict[str, str]:
    """
    Determine how the parsed input should be routed through the system.
    
    Args:
        parsed_input: Output from parse_player_input
        game_context: Current game context
        
    Returns:
        Routing instructions for the orchestrator
    """
    intent = parsed_input.get("primary_intent", "general")
    complexity = parsed_input.get("complexity", "simple")
    skill_check_needed = parsed_input.get("skill_check_needed", False)
    
    # Determine routing strategy
    if intent == "meta":
        routing = "orchestrator_direct"
    elif intent == "social" and parsed_input.get("target"):
        routing = "npc_pipeline"
    elif skill_check_needed:
        routing = "skill_pipeline"
    elif intent in ["investigation", "movement"] and complexity == "complex":
        routing = "scenario_pipeline"
    else:
        routing = "simple_response"
    
    # Determine required components
    components_needed = []
    if skill_check_needed:
        components_needed.extend(["rules_enforcer", "dice_roller", "character_manager"])
    if intent == "social":
        components_needed.append("npc_controller")
    if intent in ["investigation", "movement"]:
        components_needed.extend(["scenario_generator", "rag_retriever"])
    
    return {
        "routing_strategy": routing,
        "components_needed": components_needed,
        "pipeline_type": "full" if len(components_needed) > 2 else "simple",
        "priority": "high" if intent == "combat" else "normal"
    }


@tool
def format_response_for_player(response_data: Dict[str, Any], player_preferences: Dict[str, Any]) -> Dict[str, str]:
    """
    Format system responses into player-friendly output.
    
    Args:
        response_data: Raw response from game systems
        player_preferences: Player's display preferences
        
    Returns:
        Formatted response ready for display
    """
    # Extract key information
    scene = response_data.get("scene", "")
    choices = response_data.get("choices", [])
    skill_result = response_data.get("skill_check_result", {})
    npc_dialogue = response_data.get("npc_response", "")
    
    # Format main response
    main_response = ""
    
    if scene:
        main_response = f"🎭 {scene}"
    elif npc_dialogue:
        main_response = f"💬 {npc_dialogue}"
    elif skill_result:
        success = skill_result.get("success", False)
        total = skill_result.get("roll_total", 0)
        dc = skill_result.get("dc", 0)
        result_emoji = "✅" if success else "❌"
        main_response = f"{result_emoji} Skill Check: {total} vs DC {dc} - {'Success' if success else 'Failure'}"
    else:
        main_response = "The world awaits your next action..."
    
    # Format choices if present
    choices_text = ""
    if choices:
        choices_text = "\n📋 Available actions:"
        for i, choice in enumerate(choices, 1):
            title = choice.get("title", f"Option {i}")
            description = choice.get("description", "")
            choices_text += f"\n  {i}. {title}: {description}"
    
    # Format additional information
    additional_info = ""
    if skill_result and "roll_breakdown" in skill_result:
        additional_info = f"\n🎲 Roll: {skill_result['roll_breakdown']}"
    
    return {
        "main_response": main_response,
        "choices": choices_text,
        "additional_info": additional_info,
        "full_response": main_response + choices_text + additional_info
    }


@tool
def validate_player_command(command: str, available_commands: List[str]) -> Dict[str, Any]:
    """
    Validate if a player command is valid and available in the current context.
    
    Args:
        command: Player's command
        available_commands: List of commands available in current context
        
    Returns:
        Validation result with suggestions if command is invalid
    """
    command_lower = command.lower().strip()
    
    # Direct match
    if command_lower in [cmd.lower() for cmd in available_commands]:
        return {
            "valid": True,
            "matched_command": command_lower,
            "suggestions": []
        }
    
    # Fuzzy matching for close commands
    suggestions = []
    for available_cmd in available_commands:
        # Simple similarity check
        if available_cmd.lower().startswith(command_lower[:3]) or command_lower in available_cmd.lower():
            suggestions.append(available_cmd)
    
    return {
        "valid": False,
        "matched_command": None,
        "suggestions": suggestions[:3],  # Limit to top 3 suggestions
        "message": f"Command '{command}' not recognized" + (f". Did you mean: {', '.join(suggestions[:3])}?" if suggestions else "")
    }


def create_main_interface_agent(chat_generator: Optional[Any] = None) -> Agent:
    """
    Create a Haystack Agent for main interface and user interaction management.
    
    Args:
        chat_generator: Optional chat generator (defaults to OpenAI)
        
    Returns:
        Configured Haystack Agent for interface management
    """
    
    if chat_generator is None:
        generator = OpenAIChatGenerator(model="gpt-4o-mini")
    else:
        generator = chat_generator
    
    system_prompt = """
You are the main interface agent for a D&D game system, responsible for managing all player interactions.

Your primary responsibilities:
1. Parse and interpret player input to understand intent and extract key information
2. Determine how requests should be routed through the game system
3. Format responses from game systems into player-friendly output
4. Validate commands and provide helpful suggestions when needed

PLAYER INPUT TYPES:
- Meta commands: help, save, load, quit, status, inventory
- Combat actions: attack, cast spell, defend, use ability
- Movement: go, move, travel, enter, exit
- Investigation: search, look, examine, investigate
- Social: talk, speak, ask, persuade, intimidate
- Skills: climb, jump, hide, sneak, pick lock

ROUTING STRATEGIES:
- orchestrator_direct: Simple meta commands handled directly
- npc_pipeline: Social interactions requiring NPC agent
- skill_pipeline: Actions requiring dice rolls and skill checks
- scenario_pipeline: Complex actions needing scenario generation
- simple_response: Basic actions with simple responses

RESPONSE FORMATTING:
- Use appropriate emojis for visual appeal (🎭 for scenes, 💬 for dialogue, 🎲 for rolls)
- Present choices clearly with numbered options
- Include relevant mechanical information (dice rolls, DCs) when applicable
- Keep responses engaging but not overwhelming

WORKFLOW:
1. Use parse_player_input to understand what the player wants
2. Use determine_response_routing to decide how to process the request
3. Use format_response_for_player to present results clearly
4. Use validate_player_command for command validation when needed

Always maintain immersion while providing clear, helpful responses.
"""

    agent = Agent(
        chat_generator=generator,
        tools=[parse_player_input, determine_response_routing, format_response_for_player, validate_player_command],
        system_prompt=system_prompt,
        exit_conditions=["format_response_for_player", "determine_response_routing"],
        max_agent_steps=3,
        raise_on_tool_invocation_failure=False
    )
    
    return agent


def create_interface_agent_for_orchestrator() -> Agent:
    """Create main interface agent configured for orchestrator integration"""
    return create_main_interface_agent()


# Example usage and testing
if __name__ == "__main__":
    # Create the agent
    agent = create_main_interface_agent()
    
    # Test interface interactions
    test_cases = [
        {
            "player_input": "I want to search the ancient library for information about dragons",
            "game_context": {"location": "Library", "character": "player"}
        },
        {
            "player_input": "I attack the goblin with my sword",
            "game_context": {"location": "Combat", "enemies": ["goblin"]}
        },
        {
            "player_input": "talk to the bartender about rumors",
            "game_context": {"location": "Tavern", "npcs": ["bartender"]}
        },
        {
            "player_input": "help",
            "game_context": {"location": "General"}
        }
    ]
    
    for i, test_case in enumerate(test_cases):
        print(f"\n=== Interface Agent Test {i+1} ===")
        
        user_message = f"""
        Player Input: {test_case['player_input']}
        Game Context: {test_case['game_context']}
        
        Parse this input and determine how it should be processed by the game system.
        """
        
        try:
            # Run the agent
            response = agent.run(messages=[ChatMessage.from_user(user_message)])
            
            print("Messages:")
            for msg in response["messages"]:
                print(f"{msg.role}: {msg.text}")
            
            # Check for tool results
            for key, value in response.items():
                if key not in ["messages"] and value:
                    print(f"{key}: {value}")
                    
        except Exception as e:
            print(f"❌ Interface Agent test {i+1} failed: {e}")