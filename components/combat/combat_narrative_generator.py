"""
Combat Narrative Generator - LLM-Powered Combat Storytelling

Generates vivid, Brandon Sanderson-style combat narratives from mechanical combat results.
Transforms dice rolls and damage numbers into immersive action descriptions.

Based on: COMBAT_ENGINE_IMPLEMENTATION_PLAN.md Phase 3
"""

from typing import Dict, Any
from haystack.dataclasses import ChatMessage

from config.logging_config import get_logger

logger = get_logger(__name__)


class CombatNarrativeGenerator:
    """
    Generates vivid combat narratives from mechanical results.

    Uses LLM to transform combat mechanics (attack rolls, damage, etc.) into
    engaging 2-3 sentence action descriptions in the style of Brandon Sanderson's
    Stormlight Archive.
    """

    def __init__(self, llm, character_manager):
        """
        Initialize Combat Narrative Generator.

        Args:
            llm: Haystack LLM component (GeminiChatGenerator)
            character_manager: CharacterManager for accessing character names
        """
        self.llm = llm
        self.character_manager = character_manager
        self.logger = get_logger(__name__)

    def generate_action_narrative(
        self,
        action: Dict[str, Any],
        result: Dict[str, Any],
        combat_state: Dict[str, Any]
    ) -> str:
        """
        Generate narrative for combat action.

        Args:
            action: {
                "actor": "char_id",
                "action_type": "attack" | "lashing" | etc,
                "target": "target_char_id"  # Optional
            }
            result: {
                "success": True/False,
                "damage": 10,  # Optional
                "critical": False,  # Optional
                "description": "Hit! Dealt 10 damage"
            }
            combat_state: Current combat state dict

        Returns:
            2-3 sentence vivid description with mechanical summary.
            Example: "The blade flashes through the air... 💥 Hit! 10 damage dealt."
        """
        # Get character names
        actor_name = self._get_character_name(action["actor"])
        target_name = self._get_character_name(action.get("target", ""))

        # Build LLM prompt
        system_prompt = """You are a Dungeon Master narrating D&D combat.

Generate vivid, exciting combat descriptions (2-3 sentences max).

Include:
- Action description (swing, thrust, dodge, spell cast, etc.)
- Environmental details (dust, blood, sparks, light)
- Emotional impact (fear, determination, pain, triumph)

Style: Brandon Sanderson's Stormlight Archive
Tone: Action-focused, concise, vivid, epic fantasy"""

        user_prompt = f"""Narrate this combat action:

Actor: {actor_name}
Action: {action['action_type']}
Target: {target_name if target_name else 'N/A'}

Result:
- Success: {result.get('success', False)}
- Damage: {result.get('damage', 0)}
- Critical: {result.get('critical', False)}

Round: {combat_state['round_number']}

Generate 2-3 sentence narrative:"""

        try:
            response = self.llm.run(
                messages=[
                    ChatMessage.from_system(system_prompt),
                    ChatMessage.from_user(user_prompt)
                ]
            )

            # Extract narrative from response
            narrative = response['replies'][0].content.strip()

        except Exception as e:
            self.logger.error(f"LLM narrative generation failed: {e}")
            # Fallback to simple description
            narrative = f"{actor_name} uses {action['action_type']}"
            if target_name:
                narrative += f" against {target_name}"

        # Add mechanical summary based on action type
        if action["action_type"] == "attack":
            if result.get("success"):
                damage = result.get("damage", 0)
                narrative += f"\n💥 Hit! {damage} damage dealt."
                if result.get("critical"):
                    narrative += " ⭐ CRITICAL HIT!"
            else:
                narrative += f"\n🎯 Miss!"

            # Check if target defeated
            if "target" in action and action["target"]:
                target_state = combat_state["combatant_states"].get(action["target"])
                if target_state and target_state.get("hp_current", 1) <= 0:
                    narrative += f"\n💀 {target_name} is defeated!"

        elif action["action_type"] in ["lashing", "shardblade_attack", "progression_healing"]:
            # Roshar-specific action summaries
            if result.get("success"):
                if "soul_damage" in result:
                    narrative += f"\n💀 Soul damage: {result['soul_damage']}"
                elif "healing_amount" in result:
                    narrative += f"\n💚 Healed: {result['healing_amount']} HP"
                elif "stormlight_consumed" in result:
                    narrative += f"\n⚡ Stormlight consumed: {result['stormlight_consumed']}"
            else:
                narrative += f"\n❌ {result.get('description', 'Action failed')}"

        else:
            # Generic action summary
            if result.get("success"):
                narrative += f"\n✅ {result.get('description', 'Action succeeded')}"
            else:
                narrative += f"\n❌ {result.get('description', 'Action failed')}"

        return narrative

    def generate_combat_status(self, combat_state: Dict) -> str:
        """
        Generate combat status display.

        Args:
            combat_state: Current combat state dict

        Returns:
            Formatted combat status string:

            === COMBAT STATUS ===
            Round: 3
            Current Turn: Aggi

            🟢 Allies:
              - Aggi (Lightweaver): 25/25 HP

            🔴 Enemies:
              - Goblin_001: 0/7 HP (defeated)
              - Goblin_002: 5/7 HP
        """
        status = "\n=== COMBAT STATUS ===\n"
        status += f"Round: {combat_state['round_number']}\n"

        # Show current turn
        current_idx = combat_state['current_turn_index']
        current_actor_id = combat_state['initiative_order'][current_idx]['char_id']
        current_actor_name = self._get_character_name(current_actor_id)
        status += f"Current Turn: {current_actor_name}\n\n"

        # Allies
        allies = [
            cid for cid, state in combat_state['combatant_states'].items()
            if not state['is_hostile']
        ]

        status += "🟢 Allies:\n"
        for ally_id in allies:
            state = combat_state['combatant_states'][ally_id]
            ally_name = self._get_character_name(ally_id)

            status += f"  - {ally_name}: {state['hp_current']}/{state['hp_max']} HP"

            # Show conditions if any
            if state.get('conditions'):
                status += f" ({', '.join(state['conditions'])})"

            status += "\n"

        # Enemies
        enemies = [
            cid for cid, state in combat_state['combatant_states'].items()
            if state['is_hostile']
        ]

        status += "\n🔴 Enemies:\n"
        for enemy_id in enemies:
            state = combat_state['combatant_states'][enemy_id]
            enemy_name = self._get_character_name(enemy_id)

            status += f"  - {enemy_name}: {state['hp_current']}/{state['hp_max']} HP"

            # Show defeated status
            if state['hp_current'] <= 0:
                status += " (defeated)"

            # Show conditions if any
            if state.get('conditions'):
                status += f" ({', '.join(state['conditions'])})"

            status += "\n"

        return status

    def _get_character_name(self, char_id: str) -> str:
        """
        Get character name from character ID.

        Args:
            char_id: Character ID

        Returns:
            Character name or char_id if not found
        """
        if not char_id:
            return "Unknown"

        char = self.character_manager.characters.get(char_id)
        if char and hasattr(char, 'name'):
            return char.name
        else:
            # Fallback to char_id
            return char_id
