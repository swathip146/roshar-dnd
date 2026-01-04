"""
NPC Combat AI Agent - Tactical Combat Decision Making

Provides intelligent NPC combat decision-making using LLM for tactical analysis.
Used by CombatSessionManager for NPC turns during combat.

Design: Simple class-based approach (not Haystack Agent) for performance.
Combat decisions are time-sensitive and need straightforward tactical evaluation.
"""

import json
from typing import Dict, Any, Optional, List

from config.logging_config import get_logger

logger = get_logger(__name__)


class NPCCombatAI:
    """
    NPC AI decision-making for combat.

    Uses LLM to make intelligent tactical decisions based on:
    - NPC stats and abilities
    - Combat situation (HP, allies, enemies)
    - Available actions from ACTION_REGISTRY
    """

    def __init__(self, llm_generator):
        """
        Initialize NPC Combat AI Agent.

        Args:
            llm_generator: Haystack LLM generator component (GeminiChatGenerator)
        """
        self.llm = llm_generator
        self.logger = get_logger(__name__)

    def decide_action(self, npc_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decide NPC's action for current turn.

        Args:
            npc_context: {
                "npc": CharacterData object,
                "npc_hp": 5,
                "npc_max_hp": 7,
                "available_actions": ["attack", "dodge", "dash", "lashing"],
                "available_targets": ["aggi"],
                "allies": ["goblin_002"],
                "enemies": ["aggi"],
                "round_number": 2
            }

        Returns:
            {
                "action_type": "attack",
                "target": "aggi",
                "weapon": "scimitar",
                "reasoning": "Target is only enemy, attack to deal damage"
            }
        """
        self.logger.info(f"🤖 NPC AI deciding action for {npc_context.get('npc').name}")

        # Build prompt for LLM
        prompt = self._build_decision_prompt(npc_context)

        # Get LLM decision
        try:
            response = self.llm.run(messages=[{"role": "user", "content": prompt}])

            # Parse response
            action = self._parse_llm_response(response, npc_context)

            self.logger.info(f"   Decision: {action['action_type']} (target: {action.get('target')})")
            return action

        except Exception as e:
            self.logger.error(f"❌ NPC AI decision failed: {e}")
            # Return fallback action
            return self._get_fallback_action(npc_context)

    def _build_decision_prompt(self, context: Dict) -> str:
        """
        Build LLM prompt for NPC decision.

        Creates a comprehensive tactical situation description for the LLM
        to analyze and make the best combat decision.
        """
        npc = context['npc']
        hp_percent = (context['npc_hp'] / context['npc_max_hp']) * 100 if context['npc_max_hp'] > 0 else 0

        # Format available actions
        actions_list = ", ".join(context['available_actions'])

        # Format targets with HP if available
        targets_info = []
        for target_id in context['available_targets']:
            targets_info.append(target_id)
        targets_str = ", ".join(targets_info) if targets_info else "None"

        # Determine tactical situation
        ally_count = len(context.get('allies', []))
        enemy_count = len(context.get('enemies', []))

        if hp_percent < 30:
            situation = "Critical HP - survival is priority"
        elif hp_percent < 50:
            situation = "Low HP - defensive actions recommended"
        elif enemy_count > ally_count + 1:
            situation = "Outnumbered - tactical retreat or defensive stance advised"
        elif ally_count > enemy_count:
            situation = "Numerical advantage - press the attack"
        else:
            situation = "Even fight - aggressive tactics viable"

        prompt = f"""You are controlling {npc.name} ({npc.character_class} Level {npc.level}) in D&D 5e combat.

CURRENT STATUS:
- HP: {context['npc_hp']}/{context['npc_max_hp']} ({hp_percent:.0f}%)
- Situation: {situation}
- Round: {context.get('round_number', '?')}

AVAILABLE ACTIONS:
{actions_list}

AVAILABLE TARGETS:
{targets_str}

ALLIES: {len(context.get('allies', []))} allies present
ENEMIES: {len(context.get('enemies', []))} enemies present

TACTICAL GUIDELINES:
- Low HP (<50%): Consider dodge/defensive actions
- Critical HP (<30%): Prioritize survival
- Multiple enemies: Focus fire on wounded targets
- Outnumbered: Use defensive actions
- Strong position: Aggressive actions recommended
- Special abilities: Use them strategically (e.g., Lashing for control, Shardblade for damage)

Choose the BEST tactical action. Respond ONLY with valid JSON (no markdown, no code blocks):
{{
  "action_type": "attack",
  "target": "char_id or null",
  "weapon": "weapon_name or null",
  "reasoning": "brief tactical explanation"
}}

IMPORTANT:
- action_type MUST be one of: {actions_list}
- target MUST be one of: {targets_str} (or null for non-targeted actions)
- Provide clear reasoning for your choice"""

        return prompt

    def _parse_llm_response(self, response: Dict, context: Dict) -> Dict:
        """
        Parse LLM response into action dict.

        Args:
            response: LLM response with 'replies' key
            context: NPC context for fallback

        Returns:
            Parsed action dict
        """
        try:
            # Extract content from Haystack response format
            if 'replies' in response and len(response['replies']) > 0:
                content = response['replies'][0].content
            else:
                raise ValueError("No replies in LLM response")

            # Clean up content (remove markdown code blocks if present)
            content = content.strip()
            if content.startswith('```'):
                # Remove markdown code blocks
                lines = content.split('\n')
                # Find JSON content between ``` markers
                json_lines = []
                in_code_block = False
                for line in lines:
                    if line.strip().startswith('```'):
                        in_code_block = not in_code_block
                        continue
                    if in_code_block or (not line.strip().startswith('```')):
                        json_lines.append(line)
                content = '\n'.join(json_lines)

            # Parse JSON
            action = json.loads(content)

            # Validate action_type
            if 'action_type' not in action:
                raise ValueError("Missing action_type in response")

            if action['action_type'] not in context['available_actions']:
                self.logger.warning(f"Invalid action_type '{action['action_type']}', using fallback")
                return self._get_fallback_action(context)

            # Validate target if present
            if 'target' in action and action['target']:
                if action['target'] not in context['available_targets']:
                    self.logger.warning(f"Invalid target '{action['target']}', using first available")
                    action['target'] = context['available_targets'][0] if context['available_targets'] else None

            # Ensure required fields
            action.setdefault('target', None)
            action.setdefault('weapon', None)
            action.setdefault('reasoning', 'Tactical decision')

            return action

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON from LLM: {e}")
            self.logger.debug(f"Raw content: {content}")
            return self._get_fallback_action(context)
        except Exception as e:
            self.logger.error(f"Failed to parse LLM response: {e}")
            return self._get_fallback_action(context)

    def _get_fallback_action(self, context: Dict) -> Dict:
        """
        Get fallback action if AI decision fails.

        Fallback logic:
        1. If targets available and can attack -> attack first target
        2. If low HP (<50%) -> dodge
        3. Otherwise -> dodge (safest default)
        """
        self.logger.info("Using fallback action logic")

        npc = context['npc']
        hp_percent = (context['npc_hp'] / context['npc_max_hp']) * 100 if context['npc_max_hp'] > 0 else 0

        # Check if can attack
        if context['available_targets'] and 'attack' in context['available_actions']:
            target = context['available_targets'][0]

            # Get weapon (prefer first attack if available)
            weapon = "unarmed"
            if hasattr(npc, 'attacks') and npc.attacks:
                weapon = npc.attacks[0].get('name', 'unarmed')

            return {
                "action_type": "attack",
                "target": target,
                "weapon": weapon,
                "reasoning": "Fallback: Attack nearest enemy"
            }

        # Low HP - dodge if available
        if hp_percent < 50 and 'dodge' in context['available_actions']:
            return {
                "action_type": "dodge",
                "target": None,
                "weapon": None,
                "reasoning": "Fallback: Low HP, defensive action"
            }

        # Default: dodge if available, otherwise first available action
        if 'dodge' in context['available_actions']:
            return {
                "action_type": "dodge",
                "target": None,
                "weapon": None,
                "reasoning": "Fallback: Defensive action"
            }

        # Last resort: use first available action
        if context['available_actions']:
            return {
                "action_type": context['available_actions'][0],
                "target": context['available_targets'][0] if context['available_targets'] else None,
                "weapon": None,
                "reasoning": "Fallback: First available action"
            }

        # Should never reach here
        return {
            "action_type": "dodge",
            "target": None,
            "weapon": None,
            "reasoning": "Fallback: No valid actions"
        }


# Factory function for easy instantiation
def create_npc_combat_ai(llm_generator=None):
    """
    Create NPC Combat AI instance.

    Args:
        llm_generator: Optional LLM generator. If None, creates default from config.

    Returns:
        NPCCombatAI instance
    """
    if llm_generator is None:
        from config.llm_config import get_global_config_manager
        global_manager = get_global_config_manager()
        llm_generator = global_manager.create_generator(
            agent_name="npc_combat_ai",
            temperature=0.3  # Lower temperature for more deterministic tactical decisions
        )

    return NPCCombatAI(llm_generator)


# Example usage for testing
if __name__ == "__main__":
    print("=" * 60)
    print("NPC Combat AI - Testing")
    print("=" * 60)

    # Create mock LLM generator for testing
    class MockLLM:
        def run(self, messages):
            return {
                'replies': [
                    type('obj', (object,), {
                        'content': '{"action_type": "attack", "target": "hero", "weapon": "scimitar", "reasoning": "Test attack"}'
                    })()
                ]
            }

    # Create mock NPC data
    class MockNPC:
        name = "Goblin Warrior"
        character_class = "Warrior"
        level = 1
        attacks = [{"name": "Scimitar", "attack_bonus": 4}]

    # Test context
    context = {
        "npc": MockNPC(),
        "npc_hp": 5,
        "npc_max_hp": 7,
        "available_actions": ["attack", "dodge", "dash"],
        "available_targets": ["hero"],
        "allies": [],
        "enemies": ["hero"],
        "round_number": 1
    }

    # Create AI
    ai = NPCCombatAI(MockLLM())

    # Test decision
    print("\n--- Test 1: Normal decision ---")
    decision = ai.decide_action(context)
    print(f"Action: {decision['action_type']}")
    print(f"Target: {decision.get('target')}")
    print(f"Reasoning: {decision.get('reasoning')}")

    # Test fallback (low HP)
    print("\n--- Test 2: Low HP fallback ---")
    context['npc_hp'] = 2
    decision = ai.decide_action(context)
    print(f"Action: {decision['action_type']}")
    print(f"Reasoning: {decision.get('reasoning')}")

    print("\n" + "=" * 60)
    print("Testing complete")
    print("=" * 60)
