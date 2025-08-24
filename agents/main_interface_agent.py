"""
Main Interface Agent - User interaction management
Handles player input parsing, command interpretation, and response formatting using Haystack Agent framework
Updated to use shared DTO contract for predictable data flow
"""

from typing import Dict, Any, Optional, List
from haystack.components.agents import Agent
from haystack.dataclasses import ChatMessage
from haystack.tools import tool
from config.llm_config import get_global_config_manager
from shared_contract import RequestDTO, new_dto


@tool
def normalize_incoming(player_input: str, game_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize incoming player input into DTO format.
    
    Args:
        player_input: Raw player input text
        game_context: Current game state and context (can be dict or JSON string)
        
    Returns:
        Normalized DTO with parsed action and intent
    """
    # Handle string input - parse JSON if needed
    if isinstance(game_context, str):
        try:
            import json
            import ast
            # Try AST first for Python dict strings with single quotes
            try:
                game_context = ast.literal_eval(game_context)
            except (ValueError, SyntaxError):
                # Fallback to JSON parsing
                game_context = json.loads(game_context)
        except (json.JSONDecodeError, ValueError, SyntaxError):
            game_context = {}
    
    # Create new DTO
    dto = new_dto(player_input.strip(), game_context or {})
    
    input_lower = player_input.lower().strip()
    
    # Extract action verb and target
    words = input_lower.split()
    if words:
        # First word is usually the action
        dto["action"] = words[0]
        
        # Look for common targets
        common_targets = [
            # NPCs
            "bartender", "innkeeper", "merchant", "guard", "wizard", "priest",
            "captain", "noble", "king", "queen", "dragon", "goblin",
            # Objects
            "door", "chest", "book", "scroll", "lever", "button", "statue"
        ]
        
        for target in common_targets:
            if target in input_lower:
                dto["target"] = target
                break
    
    # Determine type based on content
    if any(word in input_lower for word in ["spell", "cast", "magic", "rules", "mechanic"]):
        dto["type"] = "rules_lookup"
    elif dto.get("target") in ["bartender", "innkeeper", "merchant", "guard", "wizard", "priest"]:
        dto["type"] = "npc_interaction"
    else:
        dto["type"] = "scenario"
    
    return dto


@tool(
    outputs_to_state={"rag_assessment": {"source": "."}}
)
def assess_rag_need_llm(action: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    LLM-based assessment of whether RAG retrieval is needed for the given action and context.
    This replaces the rule-based approach with intelligent LLM reasoning.
    
    Args:
        action: Player action or query
        context: Game context (dict or string representation)
        
    Returns:
        Assessment of whether RAG is needed, what type, and recommended filters
    """
    # Handle string input - parse JSON if needed
    if isinstance(context, str):
        try:
            import json
            import ast
            # Try AST first for Python dict strings with single quotes
            try:
                context = ast.literal_eval(context)
            except (ValueError, SyntaxError):
                # Fallback to JSON parsing
                context = json.loads(context)
        except (json.JSONDecodeError, ValueError, SyntaxError):
            context = {}
    
    # This tool uses the LLM's reasoning to determine RAG needs
    # The system prompt will guide the LLM to make this assessment
    assessment_prompt = f"""
    Analyze this player action and determine if RAG (Retrieval-Augmented Generation) document retrieval is needed:
    
    Player Action: "{action}"
    Game Context: {context}
    
    Consider these categories for RAG retrieval:
    - LORE: Requests about world history, legends, stories, character backgrounds, past events
    - RULES: Spell mechanics, game rules, abilities, combat mechanics, skill checks
    - MONSTERS: Creature information, bestiary entries, monster behaviors
    - LOCATIONS: Place descriptions, geography, notable locations
    - NONE: Simple actions that don't require external knowledge
    
    Respond with a JSON object containing:
    {{
        "rag_needed": true/false,
        "rag_type": "lore|rules|monsters|locations|none",
        "confidence": 0.0-1.0,
        "reasoning": "Brief explanation of why RAG is/isn't needed",
        "recommended_filters": {{
            "document_type": ["list", "of", "types"],
            "content_category": ["list", "of", "categories"]
        }},
        "query_suggestions": ["suggested", "search", "queries"]
    }}
    
    Examples:
    - "Tell me about the history of Roshar" → rag_needed: true, rag_type: "lore"
    - "I cast fireball" → rag_needed: true, rag_type: "rules"
    - "I look around" → rag_needed: false, rag_type: "none"
    - "What creatures live in this forest?" → rag_needed: true, rag_type: "monsters"
    """
    
    # The actual LLM processing will happen when this tool is called by the agent
    # For now, return a structured response that the LLM will populate
    return {
        "action": action,
        "context": context,
        "assessment_prompt": assessment_prompt,
        "needs_llm_processing": True
    }


@tool(
    outputs_to_state={"routing_decision": {"source": "."}}
)
def determine_response_routing(dto: Dict[str, Any], world_state: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Determine routing for the request based on DTO content using hard rules.
    
    Args:
        dto: Request DTO (can be dict or JSON string)
        world_state: Current world/game state (optional)
        
    Returns:
        Updated DTO with routing decision and routing metadata
    """
    # Handle string input - parse JSON if needed
    if isinstance(dto, str):
        try:
            import json
            dto = json.loads(dto)
        except (json.JSONDecodeError, TypeError):
            return {"error": "Invalid DTO format", "route": "simple_response"}
    
    if not isinstance(dto, dict):
        return {"error": "DTO must be dict or JSON string", "route": "simple_response"}
    
    # Initialize routing metadata
    routing_metadata = {
        "rules_checked": [],
        "confidence": 0.0,
        "fallback_used": False
    }
    
    player_input = dto.get("player_input", "").lower()
    action = dto.get("action", "").lower()
    target = dto.get("target")
    request_type = dto.get("type")
    
    # Hard Rule 1: Explicit rules/spell queries
    rules_keywords = [
        "spell", "cast", "magic", "rule", "mechanic", "how does", "what happens if",
        "stats", "ability", "skill check", "dc", "damage", "range", "duration",
        "components", "concentration", "ritual", "level", "school"
    ]
    
    rules_matches = [kw for kw in rules_keywords if kw in player_input or kw in action]
    if rules_matches or request_type == "rules_lookup":
        dto["route"] = "rules"
        routing_metadata["rules_checked"] = rules_matches
        routing_metadata["confidence"] = 0.9
        routing_metadata["reason"] = "Explicit rules/spell query detected"
        dto["debug"]["routing"] = routing_metadata
        return dto
    
    # Hard Rule 2: NPC interaction detection
    npc_keywords = [
        "talk to", "speak to", "ask", "tell", "say to", "whisper to",
        "persuade", "intimidate", "deceive", "insight", "conversation"
    ]
    
    # Check for explicit NPC targets
    common_npcs = [
        "bartender", "innkeeper", "merchant", "guard", "wizard", "priest",
        "captain", "noble", "king", "queen", "shopkeeper", "blacksmith",
        "mayor", "elder", "scout", "sage", "healer", "bard"
    ]
    
    # World state NPC check
    world_npcs = world_state.get("npcs", []) if world_state else []
    
    npc_interaction = False
    npc_reason = ""
    
    # Check for NPC keywords
    if any(kw in player_input for kw in npc_keywords):
        npc_interaction = True
        npc_reason = "NPC interaction keywords detected"
        routing_metadata["confidence"] = 0.8
    
    # Check for known NPC targets
    elif target and (target in common_npcs or target in world_npcs):
        npc_interaction = True
        npc_reason = f"Known NPC target: {target}"
        routing_metadata["confidence"] = 0.9
    
    # Check for common NPC names in input
    elif any(npc in player_input for npc in common_npcs):
        npc_interaction = True
        detected_npc = next(npc for npc in common_npcs if npc in player_input)
        npc_reason = f"Common NPC detected: {detected_npc}"
        dto["target"] = detected_npc  # Auto-set target
        routing_metadata["confidence"] = 0.7
    
    # Check request type
    elif request_type == "npc_interaction":
        npc_interaction = True
        npc_reason = "Request type indicates NPC interaction"
        routing_metadata["confidence"] = 0.8
    
    if npc_interaction:
        dto["route"] = "npc"
        routing_metadata["reason"] = npc_reason
        dto["debug"]["routing"] = routing_metadata
        return dto
    
    # Hard Rule 3: Meta commands (should go to orchestrator direct)
    meta_keywords = ["help", "save", "load", "quit", "status", "inventory", "stats", "info"]
    meta_matches = [kw for kw in meta_keywords if kw in player_input or kw in action]
    
    if meta_matches:
        dto["route"] = "meta"
        routing_metadata["reason"] = f"Meta command detected: {meta_matches}"
        routing_metadata["confidence"] = 0.95
        dto["debug"]["routing"] = routing_metadata
        return dto
    
    # Hard Rule 4: Check if RAG assessment has been performed
    rag_assessment = dto.get("rag_assessment")
    if rag_assessment and rag_assessment.get("rag_needed"):
        rag_type = rag_assessment.get("rag_type", "general")
        
        # Route based on RAG assessment results
        if rag_type == "rules":
            dto["route"] = "rules"
            routing_metadata["reason"] = "RAG assessment indicates rules query"
            routing_metadata["confidence"] = rag_assessment.get("confidence", 0.8)
            routing_metadata["rag_enhanced"] = True
            dto["debug"]["routing"] = routing_metadata
            return dto
        elif rag_type in ["lore", "monsters", "locations"]:
            dto["route"] = "scenario_pipeline_with_rag_context"
            routing_metadata["reason"] = f"RAG assessment indicates {rag_type} query requiring context"
            routing_metadata["confidence"] = rag_assessment.get("confidence", 0.8)
            routing_metadata["rag_enhanced"] = True
            routing_metadata["rag_type"] = rag_type
            dto["debug"]["routing"] = routing_metadata
            return dto
    
    # Hard Rule 5: Pure knowledge/RAG queries (dedicated RAG route)
    pure_rag_keywords = [
        "tell me about", "what is", "who is", "information about", "know about",
        "query about", "research", "lookup", "find information", "search for"
    ]
    
    pure_rag_matches = [kw for kw in pure_rag_keywords if kw in player_input]
    if pure_rag_matches:
        dto["route"] = "rag_query"
        routing_metadata["reason"] = f"Pure knowledge query detected: {pure_rag_matches}"
        routing_metadata["confidence"] = 0.85
        routing_metadata["requires_rag_assessment"] = True
        dto["debug"]["routing"] = routing_metadata
        return dto
    
    # Hard Rule 6: Lore/Knowledge queries (should use RAG-enhanced scenario)
    lore_keywords = [
        "lore", "history", "legend", "story", "past", "ancient", "origin",
        "background", "explain", "describe"
    ]
    
    lore_matches = [kw for kw in lore_keywords if kw in player_input]
    if lore_matches:
        dto["route"] = "scenario_pipeline_with_rag_context"
        routing_metadata["reason"] = f"Lore/knowledge query detected: {lore_matches}"
        routing_metadata["confidence"] = 0.9
        routing_metadata["requires_rag_assessment"] = True
        dto["debug"]["routing"] = routing_metadata
        return dto
    
    # Default Rule: Everything else goes to scenario (potentially with RAG assessment)
    dto["route"] = "scenario"
    routing_metadata["reason"] = "Default routing - in-world action"
    routing_metadata["confidence"] = 0.6
    routing_metadata["fallback_used"] = True
    
    # Enhance confidence based on action words
    action_keywords = [
        "search", "look", "examine", "investigate", "explore", "enter", "exit",
        "attack", "fight", "defend", "hide", "sneak", "climb", "jump",
        "open", "close", "take", "drop", "use", "interact", "touch"
    ]
    
    if any(kw in player_input for kw in action_keywords):
        routing_metadata["confidence"] = 0.8
        routing_metadata["fallback_used"] = False
        routing_metadata["reason"] = "Clear action-based scenario request"
        
        # Some actions might benefit from RAG assessment
        investigation_keywords = ["search", "examine", "investigate", "explore"]
        if any(kw in player_input for kw in investigation_keywords):
            routing_metadata["may_need_rag"] = True
    
    dto["debug"]["routing"] = routing_metadata
    return dto


@tool(
    outputs_to_state={"formatted_response": {"source": "."}}
)
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
        chat_generator: Optional chat generator (uses LLM config if None)
        
    Returns:
        Configured Haystack Agent for interface management
    """
    
    # Use LLM config manager to get appropriate generator
    if chat_generator is None:
        config_manager = get_global_config_manager()
        generator = config_manager.create_generator("main_interface")
    else:
        generator = chat_generator
    
    system_prompt = """
You are the main interface agent for a D&D game system with advanced RAG assessment capabilities, responsible for managing all player interactions intelligently.

Your primary responsibilities:
1. Parse and interpret player input to understand intent and extract key information
2. Perform intelligent LLM-based assessment of RAG (Retrieval-Augmented Generation) needs
3. Determine optimal routing through the game system based on input analysis and RAG requirements
4. Format responses from game systems into player-friendly output
5. Validate commands and provide helpful suggestions when needed

PLAYER INPUT TYPES:
- Meta commands: help, save, load, quit, status, inventory
- Combat actions: attack, cast spell, defend, use ability
- Movement: go, move, travel, enter, exit
- Investigation: search, look, examine, investigate
- Social: talk, speak, ask, persuade, intimidate
- Skills: climb, jump, hide, sneak, pick lock
- Knowledge queries: lore questions, rule clarifications, information requests
- Pure research: "tell me about", "what is", "who are", information lookup

ENHANCED ROUTING STRATEGIES WITH RAG INTEGRATION:
- meta: Meta commands handled directly by orchestrator
- npc: Social interactions processed by NPC controller agent
- rules: Rules/spell queries with optional RAG enhancement for complex mechanics
- scenario: Standard scenario generation for basic in-world actions
- scenario_pipeline_with_rag_context: RAG-enhanced scenario generation for knowledge-intensive actions
- rag_query: Pure knowledge requests handled primarily by RAG retrieval system
- simple_response: Basic actions requiring minimal processing

RAG ASSESSMENT CAPABILITIES:
- Use assess_rag_need_llm for intelligent determination of RAG requirements
- Analyze player actions for knowledge enhancement opportunities (lore, rules, monsters, locations)
- Provide confidence scores (0.0-1.0) and detailed reasoning for RAG decisions
- Recommend specific document filters and search queries when RAG is beneficial
- Consider contextual clues (location, environment, previous actions) in assessment

RAG ASSESSMENT CATEGORIES:
- LORE: World history, character backgrounds, legends, past events, cultural information
- RULES: Spell mechanics, combat rules, skill checks, game mechanics clarifications
- MONSTERS: Creature information, behaviors, stats, encounter details
- LOCATIONS: Place descriptions, geography, environmental details
- NONE: Simple actions, basic interactions, meta commands that don't benefit from external knowledge

RESPONSE FORMATTING:
- Use contextual emojis: 🎭 scenes, 💬 dialogue, 🎲 dice rolls, 📚 lore, ⚔️ combat
- Present choices clearly with numbered options
- Include relevant mechanical information when applicable
- Maintain narrative immersion while being informative

ENHANCED WORKFLOW:
1. normalize_incoming: Parse and structure player input into standardized DTO format
2. assess_rag_need_llm: Perform intelligent LLM-based analysis of RAG requirements (when applicable)
3. determine_response_routing: Route based on input analysis and RAG assessment results
4. format_response_for_player: Structure final output for optimal player experience
5. validate_player_command: Validate commands and suggest alternatives when needed

RAG ASSESSMENT GUIDELINES:
- Use assess_rag_need_llm when player input suggests potential knowledge enhancement
- Analyze context clues to determine if external documents would improve response quality
- Consider both explicit knowledge requests and implicit information needs
- Provide detailed reasoning to aid system transparency and debugging

ROUTING DECISION LOGIC:
1. If RAG assessment indicates high-value knowledge enhancement → scenario_pipeline_with_rag_context
2. If pure information request detected → rag_query
3. If NPC interaction identified → npc
4. If rules/mechanics query → rules (with potential RAG support)
5. If meta command → meta
6. Default → scenario (standard generation)

Always prioritize player experience while ensuring accurate, contextually-appropriate responses with intelligent knowledge integration.
"""

    agent = Agent(
        chat_generator=generator,
        tools=[normalize_incoming, assess_rag_need_llm, determine_response_routing, format_response_for_player, validate_player_command],
        system_prompt=system_prompt,
        exit_conditions=["format_response_for_player", "determine_response_routing"],
        max_agent_steps=5,  # Increased to accommodate RAG assessment step
        raise_on_tool_invocation_failure=False,
        state_schema={
            "routing_decision": {"type": dict},
            "formatted_response": {"type": dict},
            "rag_assessment": {"type": dict}
        }
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