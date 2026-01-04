"""
Roshar-Specific Combat Actions

Custom Action classes for Roshar/Cosmere 5e mechanics, following dnd_engine patterns.
These actions extend the base D&D 5e action system with Surgebinding abilities.

Based on: Cosmere 5e - Radiant's Handbook v2.0

**Implemented Actions:**
1. Lashing - Windrunner/Skybreaker gravity manipulation (Gravitation Surge)
2. ShardbladeAttack - Shardblade soul damage attack
3. ProgressionHealing - Edgedancer/Truthwatcher healing (Progression Surge)

**Future Actions:** See docs/ROSHAR_COMBAT_MECHANICS_INTEGRATION.md for full list
"""

from typing import Tuple, Optional, Dict, Any
from uuid import UUID

from dnd.core.base_actions import BaseAction, ActionEvent
from dnd.core.events import EventPhase, EventType
from dnd.core.base_conditions import Duration, DurationType
from dnd.entity import Entity
from dnd.core.modifiers import DamageType

from config.logging_config import get_logger

logger = get_logger(__name__)


# ============================================================================
# GRAVITATION SURGE - LASHING
# ============================================================================

class LashingEvent(ActionEvent):
    """Event for Windrunner/Skybreaker Lashing (Surgebinding)"""
    name: str = "Lashing"
    event_type: EventType = EventType.BASE_ACTION  # Roshar-specific action
    lashing_type: str  # "basic", "full", "reverse"
    stormlight_cost: int  # Stormlight spheres consumed
    target_direction: Optional[Tuple[int, int, int]] = None  # Gravity direction vector


class Lashing(BaseAction):
    """
    Windrunner/Skybreaker Lashing - Roshar Surgebinding ability

    Manipulates gravity through Surgebinding (Gravitation Surge).
    Consumes Stormlight spheres and requires Windrunner or Skybreaker Order.

    **Mechanics:**
    - Cost: 1 Action + 1 Stormlight sphere
    - Range: Touch
    - Duration: 10 rounds (concentration)
    - Effect: Changes target's gravity direction

    **Types:**
    - basic: Change gravity direction for target
    - full: Reverse gravity completely (up becomes down)
    - reverse: Create gravity source on object

    Based on: Cosmere 5e Radiant's Handbook v2.0, pg. 47
    """

    name: str = "Lashing"
    description: str = "Manipulate gravity through Surgebinding"
    lashing_type: str  # "basic", "full", "reverse"
    target_direction: Tuple[int, int, int] = (0, 0, -1)  # Default: down
    stormlight_cost: int = 1

    def __init__(
        self,
        source_entity_uuid: UUID,
        target_entity_uuid: UUID,
        lashing_type: str = "basic",
        target_direction: Tuple[int, int, int] = (0, 0, -1)
    ):
        """
        Initialize Lashing action.

        Args:
            source_entity_uuid: Entity performing the Lashing (must be Windrunner/Skybreaker)
            target_entity_uuid: Entity to be Lashed
            lashing_type: Type of Lashing ("basic", "full", "reverse")
            target_direction: Gravity direction vector (x, y, z)
        """
        self.source_entity_uuid = source_entity_uuid
        self.target_entity_uuid = target_entity_uuid
        self.lashing_type = lashing_type
        self.target_direction = target_direction

    def _validate(self, declaration_event: LashingEvent) -> LashingEvent:
        """Validate Lashing prerequisites"""
        entity = Entity.get(self.source_entity_uuid)

        # Check Windrunner/Skybreaker Order
        # Note: This check assumes character has radiant_order attribute
        # If not available, we skip the check (fail gracefully)
        if hasattr(entity, 'radiant_order'):
            if entity.radiant_order not in ["Windrunner", "Skybreaker"]:
                logger.warning(f"Entity {entity.name} cannot use Lashing (not Windrunner/Skybreaker)")
                return declaration_event.cancel(
                    status_message=f"Only Windrunners and Skybreakers can use Lashing"
                )

        # Check Surgebinding level
        if hasattr(entity, 'surgebinding_level'):
            if entity.surgebinding_level < 1:
                logger.warning(f"Entity {entity.name} has insufficient Surgebinding level")
                return declaration_event.cancel(
                    status_message="Insufficient Windrunner/Skybreaker attunement"
                )

        # Check Stormlight availability
        if hasattr(entity, 'stormlight_current'):
            if entity.stormlight_current < self.stormlight_cost:
                logger.warning(f"Entity {entity.name} has insufficient Stormlight ({entity.stormlight_current}/{self.stormlight_cost})")
                return declaration_event.cancel(
                    status_message=f"Insufficient Stormlight ({entity.stormlight_current}/{self.stormlight_cost} needed)"
                )

        logger.debug(f"✅ Lashing validated for {entity.name}")
        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message="Lashing validated"
        )

    def _apply(self, execution_event: LashingEvent) -> LashingEvent:
        """Apply Lashing effects"""
        entity = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid)

        logger.info(f"⚡ {entity.name} uses Lashing on {target.name} ({self.lashing_type})")

        # Apply gravity manipulation
        # Note: This is a simplified implementation
        # Full implementation would interact with dnd_engine's position/movement system
        if self.lashing_type == "basic":
            # Change target's gravity direction
            if hasattr(target, 'gravity_direction'):
                target.gravity_direction = execution_event.target_direction
                logger.debug(f"   Changed gravity direction for {target.name}")

        elif self.lashing_type == "full":
            # Reverse gravity completely
            if hasattr(target, 'gravity_direction'):
                target.gravity_direction = (0, 0, 1)  # Up
                logger.debug(f"   Reversed gravity for {target.name}")

        elif self.lashing_type == "reverse":
            # Create gravity source on object
            if hasattr(target, 'is_gravity_source'):
                target.is_gravity_source = True
                logger.debug(f"   Made {target.name} a gravity source")

        # Consume Stormlight
        if hasattr(entity, 'stormlight_current'):
            entity.stormlight_current -= self.stormlight_cost
            logger.debug(f"   Consumed {self.stormlight_cost} Stormlight ({entity.stormlight_current} remaining)")

        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Lashing applied to {target.name}"
        )


# ============================================================================
# SHARDBLADE ATTACK
# ============================================================================

class ShardbladeAttackEvent(ActionEvent):
    """Event for Shardblade attack"""
    name: str = "Shardblade Attack"
    event_type: EventType = EventType.ATTACK
    soul_damage: int = 0  # 2d6 necrotic damage (ignores armor)
    target_killed: bool = False  # If soul severed (10 heartbeats)


class ShardbladeAttack(BaseAction):
    """
    Shardblade Attack - Soul-severing weapon attack

    Attacks with a summoned Shardblade, dealing soul damage that ignores armor.

    **Mechanics:**
    - Cost: 1 Action
    - Range: Reach (5 ft)
    - Damage: 2d6 necrotic (soul damage, ignores AC)
    - Special: Severs soul on hit (10 heartbeats to kill if not healed)

    **Requirements:**
    - Must have shardblade_summoned = True
    - Typically unlocked at Third Ideal for living Shardblades

    Based on: Cosmere 5e Radiant's Handbook v2.0, pg. 82
    """

    name: str = "Shardblade Attack"
    description: str = "Attack with Shardblade (soul damage)"

    def __init__(
        self,
        source_entity_uuid: UUID,
        target_entity_uuid: UUID
    ):
        """
        Initialize Shardblade attack.

        Args:
            source_entity_uuid: Entity performing the attack (must have summoned Shardblade)
            target_entity_uuid: Entity being attacked
        """
        self.source_entity_uuid = source_entity_uuid
        self.target_entity_uuid = target_entity_uuid

    def _validate(self, declaration_event: ShardbladeAttackEvent) -> ShardbladeAttackEvent:
        """Validate Shardblade attack prerequisites"""
        entity = Entity.get(self.source_entity_uuid)

        # Check Shardblade summoned
        if hasattr(entity, 'shardblade_summoned'):
            if not entity.shardblade_summoned:
                logger.warning(f"Entity {entity.name} has no summoned Shardblade")
                return declaration_event.cancel(
                    status_message="Shardblade not summoned (use 1 Bonus Action to summon)"
                )
        else:
            # If attribute doesn't exist, assume no Shardblade
            logger.warning(f"Entity {entity.name} does not have a Shardblade")
            return declaration_event.cancel(
                status_message="No Shardblade bonded"
            )

        logger.debug(f"✅ Shardblade attack validated for {entity.name}")
        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message="Shardblade attack validated"
        )

    def _apply(self, execution_event: ShardbladeAttackEvent) -> ShardbladeAttackEvent:
        """Apply Shardblade attack effects"""
        entity = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid)

        logger.info(f"⚔️  {entity.name} attacks {target.name} with Shardblade")

        # Roll soul damage: 2d6 necrotic
        import random
        d6_1 = random.randint(1, 6)
        d6_2 = random.randint(1, 6)
        soul_damage = d6_1 + d6_2

        logger.debug(f"   Rolled soul damage: {d6_1} + {d6_2} = {soul_damage}")

        # Apply damage directly to health (ignores AC)
        if hasattr(target, 'health'):
            target.health.take_damage(soul_damage, DamageType.NECROTIC)
            logger.info(f"   💀 {target.name} takes {soul_damage} soul damage (ignores armor)")

        # Track soul damage for potential instant kill
        # (In full implementation, would track if target has been soul-damaged for 10 heartbeats)
        execution_event.soul_damage = soul_damage

        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Shardblade attack dealt {soul_damage} soul damage"
        )


# ============================================================================
# PROGRESSION SURGE - HEALING
# ============================================================================

class ProgressionHealingEvent(ActionEvent):
    """Event for Progression healing"""
    name: str = "Progression Healing"
    event_type: EventType = EventType.HEAL
    healing_amount: int = 0
    stormlight_cost: int = 2


class ProgressionHealing(BaseAction):
    """
    Progression Healing - Edgedancer/Truthwatcher healing ability

    Heals wounds using Progression Surge (Surgebinding).
    Consumes Stormlight spheres and requires Edgedancer or Truthwatcher Order.

    **Mechanics:**
    - Cost: 1 Action + 2 Stormlight spheres
    - Range: Touch
    - Healing: 2d8 + Wisdom modifier
    - Special: Can restore lost limbs at higher Ideals

    **Requirements:**
    - Edgedancer or Truthwatcher Order
    - Surgebinding level 2+

    Based on: Cosmere 5e Radiant's Handbook v2.0, pg. 53
    """

    name: str = "Progression Healing"
    description: str = "Heal wounds with Progression Surge"
    stormlight_cost: int = 2

    def __init__(
        self,
        source_entity_uuid: UUID,
        target_entity_uuid: UUID,
        healing_amount: Optional[int] = None
    ):
        """
        Initialize Progression healing.

        Args:
            source_entity_uuid: Entity performing the healing (Edgedancer/Truthwatcher)
            target_entity_uuid: Entity to be healed
            healing_amount: Specific healing amount (if None, rolls 2d8 + WIS)
        """
        self.source_entity_uuid = source_entity_uuid
        self.target_entity_uuid = target_entity_uuid
        self.healing_amount = healing_amount

    def _validate(self, declaration_event: ProgressionHealingEvent) -> ProgressionHealingEvent:
        """Validate Progression healing prerequisites"""
        entity = Entity.get(self.source_entity_uuid)

        # Check Edgedancer/Truthwatcher Order
        if hasattr(entity, 'radiant_order'):
            if entity.radiant_order not in ["Edgedancer", "Truthwatcher"]:
                logger.warning(f"Entity {entity.name} cannot use Progression healing")
                return declaration_event.cancel(
                    status_message="Only Edgedancers and Truthwatchers can use Progression"
                )

        # Check Surgebinding level
        if hasattr(entity, 'surgebinding_level'):
            if entity.surgebinding_level < 2:
                logger.warning(f"Entity {entity.name} has insufficient Surgebinding level for Progression")
                return declaration_event.cancel(
                    status_message="Insufficient Surgebinding level (need 2+)"
                )

        # Check Stormlight availability
        if hasattr(entity, 'stormlight_current'):
            if entity.stormlight_current < self.stormlight_cost:
                logger.warning(f"Entity {entity.name} has insufficient Stormlight ({entity.stormlight_current}/{self.stormlight_cost})")
                return declaration_event.cancel(
                    status_message=f"Insufficient Stormlight ({entity.stormlight_current}/{self.stormlight_cost} needed)"
                )

        logger.debug(f"✅ Progression healing validated for {entity.name}")
        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message="Progression healing validated"
        )

    def _apply(self, execution_event: ProgressionHealingEvent) -> ProgressionHealingEvent:
        """Apply Progression healing effects"""
        entity = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid)

        logger.info(f"✨ {entity.name} uses Progression to heal {target.name}")

        # Roll healing: 2d8 + WIS modifier
        if self.healing_amount is None:
            import random
            d8_1 = random.randint(1, 8)
            d8_2 = random.randint(1, 8)

            # Get Wisdom modifier if available
            wis_mod = 0
            if hasattr(entity, 'ability_scores') and hasattr(entity.ability_scores, 'wisdom'):
                wis_score = entity.ability_scores.wisdom.score
                wis_mod = (wis_score - 10) // 2

            healing = d8_1 + d8_2 + wis_mod
            logger.debug(f"   Rolled healing: {d8_1} + {d8_2} + {wis_mod} = {healing}")
        else:
            healing = self.healing_amount
            logger.debug(f"   Using specified healing: {healing}")

        # Apply healing
        if hasattr(target, 'health'):
            target.health.heal(healing)
            logger.info(f"   💚 {target.name} healed for {healing} HP")

        # Consume Stormlight
        if hasattr(entity, 'stormlight_current'):
            entity.stormlight_current -= self.stormlight_cost
            logger.debug(f"   Consumed {self.stormlight_cost} Stormlight ({entity.stormlight_current} remaining)")

        execution_event.healing_amount = healing

        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Healed {target.name} for {healing} HP"
        )
