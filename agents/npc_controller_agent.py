"""
NPC Controller Agent - NPC behavior and dialogue
Handles creative NPC interactions and responses using Haystack Agent framework
"""

from typing import Dict, Any, Optional
from haystack.components.agents import Agent
from haystack.dataclasses import ChatMessage
from haystack.tools import tool
from config.llm_config import get_global_config_manager

from config.logging_config import get_logger

# Initialize logger
logger = get_logger(__name__)

# Context for accessing game_engine (similar to dm_tools pattern)
_NPC_CONTEXT: Dict[str, Any] = {}


def set_npc_tool_context(*, game_engine=None) -> None:
    """Wire the game engine for social skill checks (plan 0.3 §8)."""
    if game_engine is not None:
        _NPC_CONTEXT["game_engine"] = game_engine
    logger.info(f"🔧 NPC tool context set: {sorted(_NPC_CONTEXT)}")


def clear_npc_tool_context() -> None:
    _NPC_CONTEXT.clear()



@tool(
    # `source` names a KEY IN THIS TOOL'S RETURN DICT; omitting it sends the WHOLE
    # result to state (Haystack 2.31 `Tool.outputs_to_state` docs).
    #
    # This was `{"source": "."}`, and there is no "." key in the returned dict — so
    # nothing was ever written to state. `npc_response` was absent entirely
    # (`STATE_KEYS = ['last_message', 'messages']`), the orchestrator read None, and
    # every NPC conversation returned "NPC produced no dialogue", surfacing to the
    # player as "The world seems momentarily confused by your action."
    #
    # The model was doing its part correctly the whole time: it called
    # generate_npc_response, the tool ran, and the result was discarded on the way
    # into state. The orchestrator calls `.get()` on the response, so it wants the
    # whole dict — hence no `source`.
    outputs_to_state={"npc_response": {}}
)
def generate_npc_response(
    npc_id: str,
    player_action: str,
    dialogue: str,
    npc_context: Optional[Dict[str, Any]] = None,
    action: str = "speaks",
    attitude_change: int = 0,
    emotional_state: str = "neutral",
) -> Dict[str, Any]:
    """
    Record an NPC's response to a player action.

    Plan 2.4: this used to IGNORE the model entirely and return a hardcoded
    f"The {npc_id} responds to your action..." — and because it is the agent's
    exit condition, that literal placeholder is what the player saw. The LLM's
    actual prose never reached them.

    `dialogue` is now a REQUIRED argument, so the model must supply the words it
    wants the NPC to say.

    Args:
        npc_id: Identifier for the NPC
        player_action: What the player did or said
        dialogue: What the NPC actually says — the model writes this
        npc_context: NPC personality, memory and current state
        action: What the NPC does alongside speaking
        attitude_change: -3..+3 shift in attitude toward the player
        emotional_state: The NPC's mood after this exchange

    Returns:
        NPC response with dialogue and metadata
    """
    npc_context = npc_context or {}
    personality = npc_context.get("personality", "neutral")
    current_mood = npc_context.get("mood", "neutral")

    spoken = (dialogue or "").strip()
    if not spoken:
        # Degrade honestly rather than inventing filler prose.
        logger.warning(f"⚠️ NPC {npc_id}: model supplied no dialogue")
        spoken = f"{npc_id} says nothing."

    return {
        "npc_id": npc_id,
        "dialogue": spoken,
        "action": action or "speaks",
        "attitude_change": int(attitude_change or 0),
        "memory_update": {"last_interaction": player_action},
        "emotional_state": emotional_state or current_mood,
        "personality_traits_shown": [personality],
    }


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
def roll_social_check(skill: str, dc: int, actor: str = "") -> Dict[str, Any]:
    """
    Roll a social skill check (Persuasion, Deception, Intimidation, or Insight).

    Use this when the player attempts to influence, deceive, intimidate, or read
    an NPC. The result determines whether the attempt succeeds and should affect
    the NPC's attitude and response.

    Args:
        skill: "persuasion", "deception", "intimidation", or "insight"
        dc: Difficulty Class (10=easy, 15=moderate, 20=hard, 25=very hard)
        actor: Character id performing the check (usually the player)

    Returns:
        success, roll_total, dc, character_modifier, selected_roll
    """
    try:
        engine = _NPC_CONTEXT.get("game_engine")
        if engine is None:
            logger.warning("⚠️ roll_social_check: game_engine not available")
            return {"error": "game_engine not available", "success": False}

        # Default to first party member if no actor specified
        if not actor:
            manager = getattr(engine, "character_manager", None)
            if manager:
                try:
                    npcs = set(manager.get_npcs() or [])
                except Exception:
                    npcs = set()
                for char_id in manager.characters:
                    if char_id not in npcs:
                        actor = char_id
                        break

        result = engine.process_skill_check({
            "actor": actor,
            "skill": skill.lower(),
            "dc": int(dc),
            "context": {"source": "npc_social_interaction"},
        })

        success = bool(result.get("success"))
        logger.info(f"🎲 Social check ({skill}): {'success' if success else 'failure'} "
                   f"(rolled {result.get('roll_total')} vs DC {dc})")

        return {
            "actor": actor,
            "skill": skill,
            "dc": result.get("dc", dc),
            "selected_roll": result.get("selected_roll"),
            "roll_total": result.get("roll_total"),
            "character_modifier": result.get("character_modifier", 0),
            "success": success,
            "advantage_state": result.get("advantage_state", "normal"),
        }
    except Exception as e:
        logger.warning(f"⚠️ roll_social_check failed: {e}")
        return {"error": str(e), "success": False}


@tool
def assess_attitude_change(npc_id: str, player_action: str, npc_personality: str,
                          current_attitude: str, skill_check_success: Optional[bool] = None) -> Dict[str, Any]:
    """
    Determine how the NPC's attitude toward the player should change.

    Plan 0.3 §8: Now considers real skill check results. If skill_check_success
    is provided (from roll_social_check), it affects the outcome.

    Args:
        npc_id: NPC identifier
        player_action: Player's action
        npc_personality: NPC's personality type
        current_attitude: Current attitude toward player
        skill_check_success: Whether a social skill check succeeded (if one was rolled)

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

    # Apply skill check modifier: success boosts positive or mitigates negative,
    # failure reduces positive or worsens negative
    if skill_check_success is not None:
        if skill_check_success:
            # Success: enhance positive interactions, mitigate negative ones
            if is_positive:
                attitude_change += 1
            elif is_negative:
                attitude_change = max(attitude_change + 1, 0)  # Reduce penalty
        else:
            # Failure: reduce positive gains, worsen negative impacts
            if is_positive:
                attitude_change = max(attitude_change - 1, 0)  # Reduce benefit
            elif is_negative:
                attitude_change -= 1  # Worsen penalty

    # Map attitude levels
    attitude_levels = ["hostile", "unfriendly", "neutral", "friendly", "helpful"]
    current_level = attitude_levels.index(current_attitude) if current_attitude in attitude_levels else 2
    new_level = max(0, min(len(attitude_levels) - 1, current_level + attitude_change))
    new_attitude = attitude_levels[new_level]

    reasoning_parts = []
    if is_positive:
        reasoning_parts.append("positive action")
    elif is_negative:
        reasoning_parts.append("negative action")
    else:
        reasoning_parts.append("neutral action")

    if skill_check_success is not None:
        reasoning_parts.append(f"skill check {'succeeded' if skill_check_success else 'failed'}")

    return {
        "npc_id": npc_id,
        "attitude_change": attitude_change,
        "old_attitude": current_attitude,
        "new_attitude": new_attitude,
        "reasoning": ", ".join(reasoning_parts)
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




# Module-level so the LangGraph backend reuses this prompt VERBATIM.
NPC_SYSTEM_PROMPT = """
You are an NPC (Non-Player Character) controller for a D&D game system.

Your role is to bring NPCs to life by:
1. Generating authentic dialogue and responses
2. Maintaining consistent personality and memory
3. Tracking attitude changes based on player interactions
4. Determining appropriate NPC actions in different situations

CRITICAL — YOU WRITE THE WORDS:
When you call generate_npc_response you MUST pass a `dialogue` argument
containing the NPC's ACTUAL spoken words, in character. Do not describe what
they say; write what they say. One to four sentences.

  Good: dialogue="You're the one from the bridge crews, aren't you? Keep your
        voice down. Not everyone here wishes you well."
  Bad:  dialogue="The guard responds to your question."

Also set `attitude_change` (-3..+3) to reflect how the interaction landed, and
`emotional_state` to the NPC's mood afterwards.

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
1. If the player is attempting PERSUASION, DECEPTION, or INTIMIDATION, use
   roll_social_check FIRST to determine if the attempt succeeds
   - Set an appropriate DC: 10 (easy), 15 (moderate), 20 (hard), 25 (very hard)
   - Consider the NPC's personality, current attitude, and the difficulty of what's being asked
2. Use assess_attitude_change to determine how the NPC feels about the player action
   - Pass skill_check_success if you rolled a social check in step 1
3. Use generate_npc_response to create dialogue and behavior that reflects the check result
4. Use update_npc_memory to record the interaction
5. Use determine_npc_action if the situation requires specific actions

GUIDELINES:
- Stay in character based on NPC personality and background
- Remember past interactions and let them influence current behavior
- Make attitude changes feel natural and justified
- Provide meaningful dialogue that advances the story or provides information
- Consider the NPC's goals, fears, and motivations

Always use the available tools to process NPC interactions systematically.
"""

def create_npc_controller_agent(chat_generator: Optional[Any] = None) -> Agent:
    """
    Create a Haystack Agent for NPC control and dialogue generation.
    
    Args:
        chat_generator: Optional chat generator (uses LLM config if None)
        
    Returns:
        Configured Haystack Agent for NPC control
    """
    
    # Use LLM config manager to get appropriate generator
    if chat_generator is None:
        config_manager = get_global_config_manager()
        generator = config_manager.create_generator("npc_controller")
    else:
        generator = chat_generator
    
    system_prompt = NPC_SYSTEM_PROMPT

    agent = Agent(
        chat_generator=generator,
        tools=[roll_social_check, generate_npc_response, update_npc_memory, assess_attitude_change, determine_npc_action],
        system_prompt=system_prompt,
        exit_conditions=["generate_npc_response"],
        max_agent_steps=6,  # Raised from 4 to allow for skill check + response
        raise_on_tool_invocation_failure=False,
        state_schema={
            "npc_response": {"type": dict}
        }
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
        logger.info(f"\n=== NPC Agent Test {i+1} ===")
        
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
                logger.info(f"{msg.role}: {msg.text}")
            
            # Check for tool results
            for key, value in response.items():
                if key not in ["messages"] and value:
                    logger.info(f"{key}: {value}")
                    
        except Exception as e:
            logger.error(f"NPC Agent test {i+1} failed: {e}")