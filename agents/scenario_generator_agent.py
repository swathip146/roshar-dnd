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
        except Exception as e:
            debug_scenario_print("TOOL", f"⚠️ GameEngine access failed: {e}")
            # Fallback values
            narrative_context = {}
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
    consolidated_rag = rag.get("rag_context", "")
    
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

=== A. NARRATIVE CONTEXT (from GameEngine) ===
Player Action: "{player_action}"
Current Narrative Context: {narrative_context if narrative_context else "None established"}

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
- Weave in retrieved lore/context naturally: {consolidated_rag[:100] + "..." if consolidated_rag else "None"}
- Use vivid sensory details (sight, sound, smell, touch)
- Build narrative momentum from existing context: {narrative_context}
- Connect to active objectives where relevant: {active_objectives}

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
    
    @component.output_types(messages=List[ChatMessage])
    def run(self, dto: Dict[str, Any]) -> Dict[str, List[ChatMessage]]:
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
        return {"messages": messages}


@component
class ScenarioValidatorComponent:
    """
    Haystack component to validate and format scenario responses.
    Replaces format_scenario_response_tool for better pipeline performance.
    """
    
    @component.output_types(validated_scenario=dict)
    def run(self, messages: List[ChatMessage]) -> Dict[str, Dict[str, Any]]:
        """
        Validate and format scenario response from agent messages according to JSON schema.
        
        Args:
            messages: List of ChatMessage objects from scenario agent
            
        Returns:
            Dictionary with validated_scenario
        """
        debug_scenario_print("COMPONENT", "🎯 ScenarioValidatorComponent processing messages")
        
        # Extract scenario data from the last message
        scenario_data = {}
        if messages:
            last_message = messages[-1]
            response_text = ""
            if hasattr(last_message, 'content'):
                response_text = last_message.content
            elif hasattr(last_message, 'text'):
                response_text = last_message.text
            else:
                response_text = str(last_message)
            
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
                    
                    # Enhanced fallback: create structured scenario from text patterns
                    scene_text = "You find yourself in a moment of decision."
                    if response_text:
                        # Try to extract scene-like content
                        lines = response_text.split('\n')
                        for line in lines:
                            line = line.strip()
                            if len(line) > 50 and not line.startswith('"') and not line.startswith('{'):
                                scene_text = line[:300]  # Use first substantial line as scene
                                break
                    
                    scenario_data = {
                        "scene": scene_text,
                        "choices": [
                            {
                                "id": "c1",
                                "title": "Continue Forward",
                                "description": "Proceed with your original intention",
                                "skill_hints": ["general"],
                                "suggested_dc": 12,
                                "combat_trigger": False
                            },
                            {
                                "id": "c2",
                                "title": "Reassess the Situation",
                                "description": "Take time to carefully consider your options",
                                "skill_hints": ["insight"],
                                "suggested_dc": 10,
                                "combat_trigger": False
                            }
                        ],
                        "effects": {"immediate": "Your choice shapes what happens next"},
                        "hooks": ["The situation continues to develop"],
                        "gm_notes": "Fallback scenario - JSON parsing failed",
                        "state_changes": {},
                        "difficulty_used": {},
                        "fallback": True
                    }
                    debug_scenario_print("COMPONENT", "🔧 Created fallback scenario data")
            else:
                debug_scenario_print("COMPONENT", "❌ No response text from LLM")
                scenario_data = {
                    "scene": "A mysterious pause settles over the scene.",
                    "choices": [
                        {
                            "id": "c1",
                            "title": "Wait and Observe",
                            "description": "Take time to see what develops",
                            "skill_hints": ["perception"],
                            "suggested_dc": 10,
                            "combat_trigger": False
                        }
                    ],
                    "effects": {},
                    "hooks": [],
                    "gm_notes": "Empty response fallback",
                    "fallback": True
                }
        
        formatted_result = format_scenario_response(scenario_data)  # Reuse existing logic
        return {"validated_scenario": formatted_result}

def create_scenario_generator_agent(chat_generator: Optional[Any] = None) -> Agent:
    """
    Create a simplified scenario agent that focuses only on LLM creativity.
    Designed for pipeline integration with PromptBuilderComponent and ScenarioValidatorComponent.
    
    Args:
        chat_generator: Optional chat generator (uses LLM config if None)
        
    Returns:
        Simplified Haystack Agent focused on creative generation only
    """
    
    # Use LLM config manager to get appropriate generator
    if chat_generator is None:
        config_manager = get_global_config_manager()
        generator = config_manager.create_generator("scenario_generator")
    else:
        generator = chat_generator
    
    simplified_system_prompt = """
You are an expert D&D Dungeon Master creating engaging, immersive scenarios that respond naturally to player actions.

CORE MISSION:
Generate scenarios where choices emerge organically from the narrative situation, using comprehensive context to create meaningful player agency.

CONTEXT INTEGRATION APPROACH:
You'll receive prompts with 6 categories of context (A-F). Use ALL categories to inform your scenario creation:
A. **Narrative Context** - Advance story momentum based on player action and current state
B. **Location Context** - Use environmental features and atmosphere meaningfully in scene and choices
C. **Quest Context** - Progress objectives, respect time constraints and consequences
D. **Policy Context** - Apply appropriate DC scaling and encounter budgets based on difficulty target
E. **RAG Context** - Integrate retrieved lore and world information authentically into scenarios
F. **Output Requirements** - Follow exact formatting specifications and choice count targets. Make sure output is valid a JSON object.

KEY PRINCIPLES:
1. **Narrative Logic First**: Choices should emerge naturally from the scene, not follow artificial formulas
2. **Comprehensive Integration**: Weave all provided context meaningfully into the scenario
3. **Player Agency**: Each choice should lead to meaningfully different outcomes
4. **Atmospheric Immersion**: Use vivid sensory details to bring scenes to life
5. **Appropriate Challenge**: Match difficulty and DCs to specified levels and policy profiles

CHOICE GENERATION PHILOSOPHY:
- Ask: "Given this scene and all the context, what would players naturally want to do?"
- Don't force skill checks if the situation doesn't call for them
- Don't mandate combat if no threats are present
- Don't require social interaction if no NPCs are available
- Let environmental factors, quest objectives, and retrieved lore suggest authentic options
- Consider different player approaches: bold vs cautious, direct vs indirect, immediate vs patient

CRITICAL OUTPUT FORMAT:
Respond with ONLY a valid JSON object. No explanations, no markdown, no extra text.

JSON STRUCTURE:
{
  "scene": "Rich scene description incorporating action results and ALL context categories",
  "choices": [
    {
      "id": "c1",
      "title": "Clear action name (add **Skill Check** or **Combat** only when naturally applicable)",
      "description": "Specific explanation of what this choice involves",
      "skill_hints": ["relevant_d20_skills"],
      "suggested_dc": 12,
      "combat_trigger": false
    }
  ],
  "effects": {"immediate": "...", "long_term": "..."},
  "hooks": ["Future story possibilities based on context"],
  "gm_notes": "Hidden information for DM",
  "state_changes": {"narrative": "...", "location": "...", "quests": "..."},
  "difficulty_used": {"dcs": {}, "encounter_budget": "", "policy_profile": ""}
}

DC SCALING GUIDELINES:
- Easy: 8-11, Medium: 12-15, Hard: 16-19, Very Hard: 20+
- Adjust based on policy profile: "raw" = stricter, "house" = more forgiving
- Consider environmental factors that might modify checks
- Match the specified difficulty target in the prompt

SCENE WRITING REQUIREMENTS:
- Show immediate consequences of the player's specific action
- Use multiple senses to create immersion (sight, sound, smell, touch)
- Integrate location atmosphere and environmental factors
- Weave in retrieved lore and quest context naturally
- End at a natural decision point

Remember: Create scenarios that feel like authentic story progression using ALL the rich context provided!
"""


    agent = Agent(
        chat_generator=generator,
        tools=[],  # No tools - direct LLM generation for creativity
        system_prompt=simplified_system_prompt,
        exit_conditions=[],  # No specific exit conditions
        max_agent_steps=1,  # Just generate scenario
        raise_on_tool_invocation_failure=False,
        state_schema={}  # Minimal state
    )
    
    return agent


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