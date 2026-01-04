"""
Combat Action Resolver - Unified Action Resolution

Dispatches combat actions to appropriate handlers:
- D&D 5e actions via dnd_engine native implementations
- Roshar-specific actions via custom Action classes
- Both integrate seamlessly via dnd_engine's event system

Based on: COMBAT_ENGINE_IMPLEMENTATION_PLAN.md Phase 3
"""

from typing import Dict, Any, Optional
from uuid import UUID
import json

from dnd.actions import Attack, WeaponSlot, AttackEvent
from dnd.core.dice import AttackOutcome
from dnd.core.modifiers import DamageType

from components.combat.action_registry import ACTION_REGISTRY
from components.combat.roshar_actions import (
    LashingEvent,
    ShardbladeAttackEvent,
    ProgressionHealingEvent
)
from config.logging_config import get_logger

logger = get_logger(__name__)


class CombatActionResolver:
    """
    Unified action resolver: dnd_engine foundation + Roshar extensions.

    **Design Philosophy:**
    - D&D 5e actions → Use dnd_engine native Actions
    - Roshar abilities → Custom Actions following dnd_engine patterns
    - Both types integrate seamlessly via event system
    - ACTION_REGISTRY is external for modular expansion

    **Action Registry:**
    - Minimal initial registry (7 core actions) - Phase 3
    - Expanded post-Phase 3 with full Surge abilities (~30+ actions)
    - See: components/combat/action_registry.py and docs/ROSHAR_COMBAT_MECHANICS_INTEGRATION.md
    """

    def __init__(self, dnd_engine_wrapper, character_manager, combat_state):
        """
        Initialize Combat Action Resolver.

        Args:
            dnd_engine_wrapper: DnDEngineWrapper instance for entity access
            character_manager: CharacterManager instance for character data
            combat_state: Current combat state dict
        """
        self.dnd_wrapper = dnd_engine_wrapper
        self.character_manager = character_manager
        self.combat_state = combat_state
        self.logger = get_logger(__name__)
        self.ACTION_REGISTRY = ACTION_REGISTRY  # Expose for CombatSessionManager

    def resolve_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Unified action resolution for D&D + Roshar.

        Args:
            action: {
                "actor": "char_id",
                "action_type": "attack" | "lashing" | "progression_healing",
                "target": "target_char_id",  # Optional
                ...params
            }

        Returns:
            {
                "success": True,
                "event": AttackEvent | LashingEvent | ...,
                "description": "Human-readable result"
            }
        """
        action_type = action["action_type"]

        # Lookup in external registry
        if action_type not in ACTION_REGISTRY:
            self.logger.error(f"Unknown action type: {action_type}")
            return {
                "success": False,
                "error": f"Unknown action: {action_type}"
            }

        metadata = ACTION_REGISTRY[action_type]

        # Dispatch based on type
        if metadata["type"] in ["dnd_action", "roshar_action", "roshar_equipment"]:
            return self._execute_action(action, metadata)
        elif metadata["type"] in ["dnd_condition", "roshar_condition"]:
            return self._apply_condition(action, metadata)
        else:
            return {
                "success": False,
                "error": f"Invalid action type metadata: {metadata['type']}"
            }

    def _execute_action(self, action: Dict, metadata: Dict) -> Dict:
        """
        Execute Action (D&D or Roshar) via dnd_engine event system.

        Uses: dnd_wrapper.execute_dnd_action(action_class, **kwargs)
        """
        action_class = metadata["action_class"]
        actor_uuid = self._get_entity_uuid(action["actor"])

        # Build action parameters
        kwargs = {
            "source_entity_uuid": actor_uuid
        }

        # Add target if present
        if "target" in action and action["target"]:
            kwargs["target_entity_uuid"] = self._get_entity_uuid(action["target"])

        # Add additional parameters from metadata
        for param in metadata.get("params", []):
            if param == "target_entity_uuid":
                continue  # Already handled above
            elif param in action:
                kwargs[param] = action[param]
            elif param == "weapon_slot":
                # Default to main hand
                kwargs[param] = WeaponSlot.MAIN_HAND

        # Execute via dnd_engine
        try:
            # Instantiate and apply action
            action_instance = action_class(**kwargs)
            event = action_instance.apply()

            # Check if action succeeded
            success = not event.canceled

            # Extract results based on action type
            if isinstance(event, AttackEvent):
                result = {
                    "success": success,
                    "event": event,
                    "attack_outcome": event.attack_outcome if hasattr(event, 'attack_outcome') else None,
                    "damage": sum(roll.total for roll in event.damage_rolls) if hasattr(event, 'damage_rolls') and event.damage_rolls else 0,
                    "critical": event.attack_outcome == AttackOutcome.CRIT_HIT if hasattr(event, 'attack_outcome') else False,
                    "description": self._format_attack_result(event)
                }
            elif isinstance(event, LashingEvent):
                result = {
                    "success": success,
                    "event": event,
                    "lashing_type": event.lashing_type if hasattr(event, 'lashing_type') else None,
                    "stormlight_consumed": event.stormlight_cost if hasattr(event, 'stormlight_cost') else 0,
                    "description": f"Lashing applied" if success else event.status_message
                }
            elif isinstance(event, ShardbladeAttackEvent):
                result = {
                    "success": success,
                    "event": event,
                    "soul_damage": event.soul_damage if hasattr(event, 'soul_damage') else 0,
                    "description": f"Shardblade dealt {event.soul_damage} soul damage" if success and hasattr(event, 'soul_damage') else event.status_message
                }
            elif isinstance(event, ProgressionHealingEvent):
                result = {
                    "success": success,
                    "event": event,
                    "healing_amount": event.healing_amount if hasattr(event, 'healing_amount') else 0,
                    "description": f"Healed {event.healing_amount} HP" if success and hasattr(event, 'healing_amount') else event.status_message
                }
            else:
                # Generic result
                result = {
                    "success": success,
                    "event": event,
                    "description": event.status_message if hasattr(event, 'status_message') else "Action executed"
                }

            # Update combat state HP if damage dealt or healing applied
            if hasattr(event, 'target_entity_uuid') and event.target_entity_uuid:
                self._sync_hp_to_combat_state(event.target_entity_uuid)

            return result

        except Exception as e:
            self.logger.error(f"Action execution failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def _apply_condition(self, action: Dict, metadata: Dict) -> Dict:
        """Apply Condition (D&D or Roshar) via dnd_engine condition system"""
        condition_class = metadata["condition_class"]
        actor_uuid = self._get_entity_uuid(action["actor"])

        # Build condition parameters
        kwargs = {
            "source_entity_uuid": actor_uuid,
            "target_entity_uuid": actor_uuid  # Most conditions target self
        }

        # Add duration if specified in metadata
        if metadata.get("duration"):
            kwargs["duration"] = metadata["duration"]

        # Add custom parameters
        for param in metadata.get("params", []):
            if param in action:
                kwargs[param] = action[param]

        # Apply via dnd_engine
        try:
            condition = condition_class(**kwargs)
            event = condition.apply()

            success = not event.canceled if hasattr(event, 'canceled') else True

            return {
                "success": success,
                "event": event,
                "condition": condition_class.__name__,
                "description": metadata.get("description", "Condition applied")
            }

        except Exception as e:
            self.logger.error(f"Condition application failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def _get_entity_uuid(self, char_id: str) -> UUID:
        """
        Get dnd_engine entity UUID from character ID.

        Args:
            char_id: Character ID

        Returns:
            Entity UUID

        Raises:
            ValueError: If entity not found for character
        """
        entity = self.dnd_wrapper.entities.get(char_id)
        if entity:
            return entity.uuid
        else:
            raise ValueError(f"Entity not found for character {char_id}")

    def _sync_hp_to_combat_state(self, target_uuid: UUID):
        """
        Sync HP from dnd_engine entity to combat state.

        Args:
            target_uuid: Target entity UUID
        """
        # Find character by UUID
        for char_id, entity in self.dnd_wrapper.entities.items():
            if entity.uuid == target_uuid:
                char = self.character_manager.characters.get(char_id)
                if char and char_id in self.combat_state["combatant_states"]:
                    # Sync current HP from entity to combat state
                    current_hp = entity.health.get_current_hit_points()
                    max_hp = entity.health.get_max_hit_points()

                    self.combat_state["combatant_states"][char_id]["hp_current"] = current_hp
                    self.combat_state["combatant_states"][char_id]["hp_max"] = max_hp

                    self.logger.debug(f"Synced HP for {char_id}: {current_hp}/{max_hp}")
                break

    def _format_attack_result(self, event: AttackEvent) -> str:
        """
        Format attack event into human-readable description.

        Args:
            event: AttackEvent from dnd_engine

        Returns:
            Human-readable description string
        """
        if not hasattr(event, 'attack_outcome'):
            return event.status_message if hasattr(event, 'status_message') else "Attack executed"

        if event.attack_outcome == AttackOutcome.HIT:
            damage = sum(roll.total for roll in event.damage_rolls) if hasattr(event, 'damage_rolls') and event.damage_rolls else 0
            return f"Hit! Dealt {damage} damage."
        elif event.attack_outcome == AttackOutcome.CRIT_HIT:
            damage = sum(roll.total for roll in event.damage_rolls) if hasattr(event, 'damage_rolls') and event.damage_rolls else 0
            return f"Critical Hit! Dealt {damage} damage!"
        elif event.attack_outcome == AttackOutcome.MISS:
            return "Miss!"
        elif event.attack_outcome == AttackOutcome.CRIT_MISS:
            return "Critical Miss!"
        else:
            return event.status_message if hasattr(event, 'status_message') else "Attack outcome unknown"
