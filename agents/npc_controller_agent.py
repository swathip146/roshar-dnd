"""
NPC Controller Agent - NPC behavior and dialogue
Handles creative NPC interactions and responses using Haystack Agent framework
"""

from typing import Dict, Any, Optional
from haystack.components.agents import Agent
from haystack.components.generators.chat import OpenAIChatGenerator
from haystack.dataclasses import ChatMessage
from haystack.tools import tool


@tool
def generate_npc_response(npc_id: str, player_action: str, npc_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate an NPC's response to a player action.
    
    Args:
        npc_id: Identifier for the NPC
        player_action: What the player did or said
        npc_context: NPC's personality, memory, and current state
        
    Returns:
        NPC response with dialogue and metadata
    """
    # Extract NPC information
    personality = npc_context.get("personality", "neutral")
    attitude = npc_context.get("attitude_toward_player", "neutral")
    memory = npc_context.get("memory", {})
    current_mood = npc_context.get("mood", "neutral")
    
    # Generate contextual response (placeholder - will be enhanced by LLM)
    response_data = {
        "npc_id": npc_id,
        "dialogue": f"The {npc_id} responds to your action...",
        "action": "speaks",
        "attitude_change": 0,
        "memory_update": {"last_interaction": player_action},
        "emotional_state": current_mood,
        "personality_traits_shown": [personality]
    }
    
    return response_data


@tool
def update_npc_memory(npc_id: str, interaction_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update NPC's memory based on the interaction.
    
    Args:
        npc_id: NPC identifier
        interaction_data: Data about the interaction to remember
        
    Returns:
        Updated memory structure
    """
    player_action = interaction_data.get("player_action", "")
    npc_response = interaction_data.get("npc_response", "")
    outcome = interaction_data.get("outcome", "neutral")
    
    memory_entry = {
        "player_action": player_action,
        "npc_response": npc_response,
        "outcome": outcome,
        "importance": interaction_data.get("importance", "low"),
        "timestamp": interaction_data.get("timestamp", 0)
    }
    
    return {
        "npc_id": npc_id,
        "new_memory": memory_entry,
        "memory_updated": True
    }


@tool
def assess_attitude_change(npc_id: str, player_action: str, npc_personality: str, 
                          current_attitude: str) -> Dict[str, Any]:
    """
    Determine how the NPC's attitude toward the player should change.
    
    Args:
        npc_id: NPC identifier
        player_action: Player's action
        npc_personality: NPC's personality type
        current_attitude: Current attitude toward player
        
    Returns:
        Attitude assessment and changes
    """
    # Define personality-based responses
    personality_responses = {
        "friendly": {"positive_actions": +2, "negative_actions": -1},
        "hostile": {"positive_actions": +1, "negative_actions": -3},
        "neutral": {"positive_actions": +1, "negative_actions": -1},
        "suspicious": {"positive_actions": +1, "negative_actions": -2},
        "helpful": {"positive_actions": +3, "negative_actions": -1}
    }
    
    # Assess action type (simplified - would be enhanced by LLM)
    action_lower = player_action.lower()
    positive_triggers = ["help", "assist", "please", "thank", "gift", "compliment"]
    negative_triggers = ["threaten", "attack", "insult", "steal", "lie", "demand"]
    
    is_positive = any(trigger in action_lower for trigger in positive_triggers)
    is_negative = any(trigger in action_lower for trigger in negative_triggers)
    
    personality_mod = personality_responses.get(npc_personality, {"positive_actions": 1, "negative_actions": -1})
    
    attitude_change = 0
    if is_positive:
        attitude_change = personality_mod["positive_actions"]
    elif is_negative:
        attitude_change = personality_mod["negative_actions"]
    
    # Map attitude levels
    attitude_levels = ["hostile", "unfriendly", "neutral", "friendly", "helpful"]
    current_level = attitude_levels.index(current_attitude) if current_attitude in attitude_levels else 2
    new_level = max(0, min(len(attitude_levels) - 1, current_level + attitude_change))
    new_attitude = attitude_levels[new_level]
    
    return {
        "npc_id": npc_id,
        "attitude_change": attitude_change,
        "old_attitude": current_attitude,
        "new_attitude": new_attitude,
        "reasoning": f"Player action was {'positive' if is_positive else 'negative' if is_negative else 'neutral'}"
    }


@tool
def determine_npc_action(npc_context: Dict[str, Any], situation: Dict[str, Any]) -> Dict[str, Any]:
    """
    Determine what action the NPC should take in the current situation.
    
    Args:
        npc_context: NPC's state and personality
        situation: Current game situation
        
    Returns:
        Recommended NPC action
    """
    personality = npc_context.get("personality", "neutral")
    attitude = npc_context.get("attitude_toward_player", "neutral")
    current_mood = npc_context.get("mood", "neutral")
    
    # Determine action based on personality and situation
    action_type = "dialogue"  # Default
    
    if situation.get("combat", False):
        if attitude in ["hostile", "unfriendly"]:
            action_type = "attack"
        elif attitude in ["friendly", "helpful"]:
            action_type = "assist_player"
        else:
            action_type = "flee_or_hide"
    elif situation.get("social", False):
        if personality == "helpful":
            action_type = "offer_assistance"
        elif personality == "suspicious":
            action_type = "question_player"
        else:
            action_type = "dialogue"
    
    return {
        "action_type": action_type,
        "priority": "normal",
        "reasoning": f"Based on {personality} personality and {attitude} attitude"
    }


def create_npc_controller_agent(chat_generator: Optional[Any] = None) -> Agent:
    """
    Create a Haystack Agent for NPC control and dialogue generation.
    
    Args:
        chat_generator: Optional chat generator (defaults to OpenAI)
        
    Returns:
        Configured Haystack Agent for NPC control
    """
    
    if chat_generator is None:
        generator = OpenAIChatGenerator(model="gpt-4o-mini")
    else:
        generator = chat_generator
    
    system_prompt = """
You are an NPC (Non-Player Character) controller for a D&D game system.

Your role is to bring NPCs to life by:
1. Generating authentic dialogue and responses
2. Maintaining consistent personality and memory
3. Tracking attitude changes based on player interactions
4. Determining appropriate NPC actions in different situations

NPC PERSONALITY TYPES:
- friendly: Warm, welcoming, quick to help
- hostile: Aggressive, confrontational, distrusting
- neutral: Balanced, professional, cautious
- suspicious: Wary, questioning, slow to trust
- helpful: Eager to assist, knowledgeable, supportive

ATTITUDE LEVELS (toward player):
- hostile: Actively opposed, will hinder or attack
- unfriendly: Dislikes player, unhelpful, curt
- neutral: No strong feelings, professional
- friendly: Likes player, willing to help
- helpful: Actively supports player, goes out of way to assist

WORKFLOW:
1. Use assess_attitude_change to determine how the NPC feels about the player action
2. Use generate_npc_response to create dialogue and behavior
3. Use update_npc_memory to record the interaction
4. Use determine_npc_action if the situation requires specific actions

GUIDELINES:
- Stay in character based on NPC personality and background
- Remember past interactions and let them influence current behavior
- Make attitude changes feel natural and justified
- Provide meaningful dialogue that advances the story or provides information
- Consider the NPC's goals, fears, and motivations

Always use the available tools to process NPC interactions systematically.
"""

    agent = Agent(
        chat_generator=generator,
        tools=[generate_npc_response, update_npc_memory, assess_attitude_change, determine_npc_action],
        system_prompt=system_prompt,
        exit_conditions=["generate_npc_response"],
        max_agent_steps=4,
        raise_on_tool_invocation_failure=False
    )
    
    return agent


def create_npc_agent_for_orchestrator() -> Agent:
    """Create NPC controller agent configured for orchestrator integration"""
    return create_npc_controller_agent()


# Example usage and testing
if __name__ == "__main__":
    # Create the agent
    agent = create_npc_controller_agent()
    
    # Test NPC interactions
    test_cases = [
        {
            "npc_id": "tavern_keeper",
            "player_action": "I'd like to buy a room for the night, please",
            "npc_context": {
                "personality": "friendly",
                "attitude_toward_player": "neutral",
                "mood": "cheerful",
                "memory": {},
                "background": "Runs the local tavern, knows local gossip"
            },
            "situation": {"social": True, "location": "tavern"}
        },
        {
            "npc_id": "suspicious_guard",
            "player_action": "You didn't see me here, understand?",
            "npc_context": {
                "personality": "suspicious",
                "attitude_toward_player": "neutral",
                "mood": "alert",
                "memory": {"previous_encounters": 0},
                "background": "City guard, duty-bound but corruptible"
            },
            "situation": {"social": True, "location": "city_gate", "tension": True}
        }
    ]
    
    for i, test_case in enumerate(test_cases):
        print(f"\n=== NPC Agent Test {i+1} ===")
        
        user_message = f"""
        NPC: {test_case['npc_id']}
        Player Action: {test_case['player_action']}
        NPC Context: {test_case['npc_context']}
        Situation: {test_case['situation']}
        
        Generate an appropriate NPC response including dialogue, attitude changes, and memory updates.
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
            print(f"❌ NPC Agent test {i+1} failed: {e}")