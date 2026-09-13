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

import sys
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
from uuid import UUID

# Add dnd_engine to path (required for dnd imports)
dnd_engine_path = Path(__file__).parent.parent.parent / "external" / "dnd_engine"
if str(dnd_engine_path) not in sys.path:
    sys.path.insert(0, str(dnd_engine_path))

from dnd.core.base_actions import BaseAction, ActionEvent
from dnd.core.events import EventPhase, EventType
from dnd.core.base_conditions import Duration, DurationType
from dnd.entity import Entity
from dnd.core.modifiers import DamageType

from config.logging_config import get_logger

logger = get_logger(__name__)


# ============================================================================
# SHARED BOOK-DERIVED SCALING HELPERS (Cosmere 5e)
#
# These read values straight off the mirrored dnd_engine Entity and map them to
# the book's own tables — no invented numbers. Each is cited at its use site.
# ============================================================================

def _proficiency_bonus(entity) -> int:
    """Proficiency bonus as a plain int (the entity field is a ModifiableValue)."""
    value = getattr(entity, "proficiency_bonus", None)
    if value is None:
        return 2
    return int(getattr(value, "normalized_score",
                       getattr(value, "score", value)) or 2)


def _character_level(entity) -> int:
    """Character level if mirrored onto the entity, else 0 (unknown)."""
    return int(getattr(entity, "level", 0) or 0)


def _radiant_ideal(entity) -> int:
    """Ideal/Surgebinding tier (Third Ideal == 3), else 0."""
    for attr in ("ideal_level", "surgebinding_level"):
        value = getattr(entity, attr, None)
        if value:
            return int(value)
    return 0


def _best_modifier(entity, abilities) -> int:
    """Highest ability modifier among `abilities`, or 0 if the block is absent."""
    scores = getattr(entity, "ability_scores", None)
    if scores is None:
        return 0
    mods = [int(getattr(scores, a).modifier)
            for a in abilities if hasattr(scores, a)]
    return max(mods) if mods else 0


def _shardblade_die_faces(entity) -> int:
    """
    Shardblade weapon die by proficiency band, per the Windrunner class table
    (HB:1739-1757): d4 (prof +2), d6 (+3), d8 (+4), d10 (+5), d12 (+6). The die
    column tracks the proficiency column one-for-one across all 20 rows.
    """
    prof = _proficiency_bonus(entity)
    return {2: 4, 3: 6, 4: 8, 5: 10, 6: 12}.get(prof, max(4, min(12, prof * 2)))


# ============================================================================
# EVENT CLASS WIRING
# ============================================================================

class _TypedEventAction(BaseAction):
    """
    Makes a surge use its OWN event class instead of the base `ActionEvent`.

    Every surge below declares a custom event (`LashingEvent`, `SoulcastEvent`, …)
    carrying surge-specific fields, and **not one of them was ever instantiated.**
    `BaseAction._create_declaration_event` hardcodes:

        return ActionEvent.from_costs(...)

    with the docstring "Override in subclasses if needed." Nobody overrode it, so all
    five custom event classes were dead code and every surge ran on a plain
    `ActionEvent`.

    That was invisible for four of the five, because they only READ their extra
    fields off `self`. `ProgressionHealing` WRITES one — `execution_event.healing_amount
    = healing` — and pydantic rejects an unknown field, so choosing Progression healing
    with an explicit amount raised:

        ValueError: "ActionEvent" object has no field "healing_amount"

    `from_costs` is a classmethod using `cls`, so declaring `event_class` is all that
    is needed to construct the right type.
    """

    #: The ActionEvent subclass this action's events should be.
    event_class: type = ActionEvent

    def _create_declaration_event(self, parent_event=None, use_register: bool = True):
        return self.event_class.from_costs(
            self.costs, self.source_entity_uuid, self.target_entity_uuid,
            parent_event, use_register=use_register)


# ============================================================================
# GRAVITATION SURGE - LASHING
# ============================================================================

class LashingEvent(ActionEvent):
    """Event for Windrunner/Skybreaker Lashing (Surgebinding)"""
    name: str = "Lashing"
    event_type: EventType = EventType.BASE_ACTION  # Roshar-specific action
    lashing_type: str = "basic"  # "basic", "full", "reverse"
    # A cantrip is FREE — the earlier per-use Stormlight-sphere cost was invented
    # (AUDIT_HARDCODED_SURGE_ACCURACY.md §4.1; surgebinding.json Gravitation.cost
    # is {investiture_points: 0}). The field is kept at 0 so `from_costs` — which
    # passes only source/target/costs/parent — can still construct the event.
    stormlight_cost: int = 0
    target_direction: Optional[Tuple[int, int, int]] = None  # Gravity direction vector
    # Adhesion cantrip's "stick an object" escape check (IA:345-346): the STR
    # (Athletics) DC to pull a Lashed object free. 0 until computed in _apply.
    escape_dc: int = 0


class Lashing(_TypedEventAction):
    """
    Windrunner/Skybreaker Lashing - Roshar Surgebinding ability

    Manipulates gravity through Surgebinding (the Basic Lashing / Gravitation and
    Full Lashing / Adhesion cantrips). Requires the Windrunner or Skybreaker Order.

    **Mechanics (Cosmere 5e — Invested Arts, Gravitation cantrip IA:348-373,
    Adhesion cantrip IA:321-346):**
    - Cost: FREE (a cantrip costs 0 Investiture — the old 1-sphere cost and the
      "10 rounds" duration were invented; see AUDIT_HARDCODED_SURGE_ACCURACY.md §4.1)
    - Range: Touch
    - Duration: Instantaneous
    - Effect: Lash an object/creature in a chosen direction; a Lashed/stuck object
      is freed with a Strength (Athletics) check vs an escape DC of `8 + proficiency`,
      rising to 9/10/11 + proficiency at 5th/11th/17th level (Adhesion, IA:345-346).

    **Types:**
    - basic: Change gravity direction for target
    - full: Reverse gravity completely (up becomes down)
    - reverse: Create gravity source on object
    """

    event_class: type = LashingEvent
    name: str = "Lashing"
    description: str = "Manipulate gravity through Surgebinding"
    lashing_type: str = "basic"  # "basic", "full", "reverse"
    target_direction: Tuple[int, int, int] = (0, 0, -1)  # Default: down
    stormlight_cost: int = 0  # Free cantrip (IA:368; surgebinding.json Gravitation)

    # NOTE: no custom __init__.
    # The original hand-wrote one that assigned fields directly and never
    # called super().__init__(), so pydantic never initialised the model:
    # constructing ANY surge raised
    #   AttributeError: object has no attribute '__pydantic_fields_set__'
    # i.e. no Roshar surge was ever usable. The class attributes above are
    # already pydantic fields with defaults, so BaseAction's generated
    # __init__ handles construction correctly.

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

        # NO Stormlight gate: Gravitation/Adhesion are cantrips and cost nothing
        # (IA:368; surgebinding.json Gravitation.cost = {investiture_points: 0}).
        # A drained Radiant can still use a cantrip — the old 1-sphere gate was
        # the invented cost this rewrite removes.

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

        # Adhesion cantrip escape DC (IA:345-346): STR (Athletics) DC to pull a
        # Lashed/stuck object free is 8 + proficiency, rising to 9/10/11 at levels
        # 5/11/17. Recorded on the event so the DM/session can adjudicate a break.
        level = _character_level(entity)
        bump = (level >= 5) + (level >= 11) + (level >= 17)
        escape_dc = 8 + bump + _proficiency_bonus(entity)
        execution_event.escape_dc = escape_dc
        logger.debug(f"   Adhesion escape DC (STR/Athletics): {escape_dc}")

        # NO Stormlight consumption — a cantrip is free (IA:368).

        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Lashing applied to {target.name}"
        )


# ============================================================================
# SHARDBLADE ATTACK
# ============================================================================

class ShardbladeAttackEvent(ActionEvent):
    """
    Event for a Shardblade attack — a REAL weapon attack roll vs AC.

    The old "2d6 necrotic, ignores armour, 10 heartbeats to kill" was invented
    wholesale (AUDIT_HARDCODED_SURGE_ACCURACY.md §4.2). A Shardweapon is a normal
    attack: roll to hit against AC, and on a hit deal a level-scaled weapon die of
    the wielder's CHOSEN damage type plus the Shardweapon's magic bonus.
    """
    name: str = "Shardblade Attack"
    event_type: EventType = EventType.ATTACK
    attack_roll: int = 0
    target_ac: int = 0
    hit: bool = False
    soul_damage: int = 0  # damage dealt (name kept: the resolver reads it)
    damage_type: str = "slashing"  # the wielder's chosen weapon type, not necrotic


class ShardbladeAttack(_TypedEventAction):
    """
    Shardblade Attack - Soul-severing weapon attack

    Attacks with a summoned Shardblade as a normal weapon attack against AC.

    **Mechanics (Cosmere 5e — Radiant's Handbook; corrections per
    AUDIT_HARDCODED_SURGE_ACCURACY.md §4.2):**
    - Cost: 1 Action
    - Range: Reach (5 ft)
    - To hit: a real attack roll (d20 + Investiture ability modifier +
      proficiency) vs the target's AC — NOT armour-ignoring, NOT auto-hit
    - Damage: one level-scaled weapon die (d4->d12 across the Windrunner table,
      HB:1739-1757) + the Investiture ability modifier + the Shardweapon's magic
      bonus (+1 at the Third Ideal, +2 at the Fourth; HB:1898-1902), of the
      wielder's CHOSEN damage type (default slashing — a blade), not necrotic

    **Requirements:**
    - shardblade_summoned = True
    - Third Ideal (7th level): a Windrunner's honorspren manifests a Shardweapon
      only on swearing the 3rd Ideal (HB:1898-1902)
    """

    event_class: type = ShardbladeAttackEvent
    name: str = "Shardblade Attack"
    description: str = "Attack with a summoned Shardblade"
    #: The wielder's chosen weapon damage type (a Shardblade is a bladed weapon).
    damage_type: str = "slashing"

    # NOTE: no custom __init__.
    # The original hand-wrote one that assigned fields directly and never
    # called super().__init__(), so pydantic never initialised the model:
    # constructing ANY surge raised
    #   AttributeError: object has no attribute '__pydantic_fields_set__'
    # i.e. no Roshar surge was ever usable. The class attributes above are
    # already pydantic fields with defaults, so BaseAction's generated
    # __init__ handles construction correctly.

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

        # Third Ideal (7th-level) gate (HB:1898-1902): the honorspren manifests a
        # Shardweapon only on swearing the 3rd Ideal. Enforced by the Ideal tier
        # when it is known; if the tier is absent we defer to shardblade_summoned.
        ideal = _radiant_ideal(entity)
        if ideal and ideal < 3:
            logger.warning(f"Entity {entity.name} below Third Ideal for a Shardblade")
            return declaration_event.cancel(
                status_message="A Shardblade requires the Third Ideal"
            )

        logger.debug(f"✅ Shardblade attack validated for {entity.name}")
        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message="Shardblade attack validated"
        )

    def _apply(self, execution_event: ShardbladeAttackEvent) -> ShardbladeAttackEvent:
        """Apply a Shardblade attack: a real attack roll vs AC, then scaled damage."""
        import random

        entity = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid)
        if target is None:
            return execution_event.cancel(status_message="No target for the Shardblade")

        # Real attack roll vs AC (no armour-ignoring auto-hit). To hit:
        # d20 + Investiture ability modifier (highest of STR/DEX for a Windrunner)
        # + proficiency, against the target's real AC.
        attack_mod = _best_modifier(entity, ("strength", "dexterity"))
        prof = _proficiency_bonus(entity)
        d20 = random.randint(1, 20)
        attack_total = d20 + attack_mod + prof
        try:
            target_ac = int(target.ac_bonus().normalized_score)
        except Exception:
            target_ac = 10

        crit = d20 == 20
        hit = crit or (d20 != 1 and attack_total >= target_ac)
        execution_event.attack_roll = attack_total
        execution_event.target_ac = target_ac
        execution_event.hit = hit

        if not hit:
            execution_event.soul_damage = 0
            logger.info(f"⚔️  {entity.name}'s Shardblade misses {target.name} "
                        f"({attack_total} vs AC {target_ac})")
            return execution_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"Shardblade attack missed {target.name}"
            )

        # Damage: one level-scaled weapon die (HB Windrunner table d4->d12) + the
        # Investiture ability modifier + the Shardweapon's magic bonus (+1 at the
        # Third Ideal, +2 at the Fourth). Crit doubles the weapon dice.
        faces = _shardblade_die_faces(entity)
        dice_count = 2 if crit else 1
        die_total = sum(random.randint(1, faces) for _ in range(dice_count))
        magic_bonus = 2 if _radiant_ideal(entity) >= 4 else 1
        damage = max(1, die_total + attack_mod + magic_bonus)

        damage_type = getattr(self, "damage_type", "slashing")
        try:
            resolved = DamageType(damage_type.capitalize())
        except ValueError:
            resolved = DamageType.SLASHING

        if hasattr(target, 'health'):
            # take_damage requires source_entity_uuid as a third positional arg.
            target.health.take_damage(damage, resolved, self.source_entity_uuid)

        execution_event.soul_damage = damage
        execution_event.damage_type = damage_type
        logger.info(
            f"⚔️  {entity.name}'s Shardblade {'CRITS' if crit else 'hits'} "
            f"{target.name} for {damage} {damage_type} "
            f"(d{faces}, {attack_total} vs AC {target_ac})")

        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Shardblade dealt {damage} {damage_type} damage"
        )


# ============================================================================
# PROGRESSION SURGE - HEALING
# ============================================================================

class ProgressionHealingEvent(ActionEvent):
    """Event for Progression healing (the 1st-level Regrowth Art)."""
    name: str = "Progression Healing"
    event_type: EventType = EventType.HEAL
    healing_amount: int = 0
    # Regrowth is a costed Invested Art (2 Investiture Points at Art level 1,
    # IA:6731-6753 + surgebinding.json economies.investiture_points), NOT a
    # Stormlight-sphere cost. The IP is spent by the resolver through
    # InvestiturePointLedger; this field is kept at 0 so the class no longer
    # deducts a sphere (AUDIT_HARDCODED_SURGE_ACCURACY.md §4.3).
    stormlight_cost: int = 0


class ProgressionHealing(_TypedEventAction):
    """
    Progression Healing - Edgedancer/Truthwatcher healing ability

    Heals wounds using the Progression Surge — the 1st-level "Regrowth" Art.
    Requires the Edgedancer or Truthwatcher Order.

    **Mechanics (Cosmere 5e — Regrowth, IA:6731-6753):**
    - Cost: 1 Action + 2 Investiture Points (Art level 1) — spent through
      InvestiturePointLedger by the resolver, NOT a Stormlight sphere
    - Range: Touch
    - Healing: 2d8 + the caster's Investiture ability modifier (WIS for an
      Edgedancer; a Truthwatcher's chosen ability)
    - Level gate: 1st level / First Ideal (not 2nd)
    """

    event_class: type = ProgressionHealingEvent
    name: str = "Progression Healing"
    description: str = "Heal wounds with Progression (Regrowth)"
    stormlight_cost: int = 0
    # Declared HERE, not only on ProgressionHealingEvent. _apply() reads
    # `self.healing_amount` to decide whether to roll 2d8 or use a fixed value,
    # but the field existed only on the Event class — so a live combat crashed
    # with "'ProgressionHealing' object has no attribute 'healing_amount'" the
    # first time a player chose Progression healing. Pydantic raises on unknown
    # attribute access, so the None default is what makes the roll path work.
    healing_amount: Optional[int] = None

    # NOTE: no custom __init__.
    # The original hand-wrote one that assigned fields directly and never
    # called super().__init__(), so pydantic never initialised the model:
    # constructing ANY surge raised
    #   AttributeError: object has no attribute '__pydantic_fields_set__'
    # i.e. no Roshar surge was ever usable. The class attributes above are
    # already pydantic fields with defaults, so BaseAction's generated
    # __init__ handles construction correctly.

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

        # Check Surgebinding level - fix per AUDIT_HARDCODED_SURGE_ACCURACY.md §4.3:
        # Progression is available at First Ideal (level 1), not Second Ideal (level 2)
        if hasattr(entity, 'surgebinding_level'):
            if entity.surgebinding_level < 1:
                logger.warning(f"Entity {entity.name} has insufficient Surgebinding level for Progression")
                return declaration_event.cancel(
                    status_message="Insufficient Surgebinding level (need 1+)"
                )

        # NO Stormlight gate: Regrowth is paid in Investiture Points, and the
        # resolver spends them through InvestiturePointLedger BEFORE this action
        # runs (refunding if it cancels). The old per-cast sphere cost was invented.

        logger.debug(f"✅ Progression healing validated for {entity.name}")
        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message="Progression healing validated"
        )

    def _apply(self, execution_event: ProgressionHealingEvent) -> ProgressionHealingEvent:
        """Apply Progression healing effects"""
        entity = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid)

        # A heal with no target is not a heal. The NPC AI produced exactly this in
        # a live combat — `Decision: progression_healing (target: None)` — and
        # `target.name` raised AttributeError on NoneType, which the resolver
        # reported as "Action execution failed" while the narrator described the
        # surge anyway. Validation passed because it only checked the CASTER's
        # level and Stormlight, never that there was someone to heal.
        if target is None:
            logger.warning(
                f"⚠️ Progression healing has no target "
                f"(target_entity_uuid={execution_event.target_entity_uuid})")
            return execution_event.cancel(
                status_message="No target to heal")

        logger.info(f"✨ {entity.name} uses Progression to heal {target.name}")

        # Roll healing: 2d8 + WIS modifier
        if self.healing_amount is None:
            import random
            d8_1 = random.randint(1, 8)
            d8_2 = random.randint(1, 8)

            # Get Investiture ability modifier. Per AUDIT_HARDCODED_SURGE_ACCURACY.md §4.3:
            # should use the caster's Investiture ability (order-specific), not always WIS.
            # WIS is correct for Edgedancer; Truthwatcher chooses INT, WIS, or CHA.
            #
            # `Ability` exposes `.modifier`, NOT `.score` — it is a computed field on
            # the block, and there is no `score` attribute at all.
            ability_mod = 0
            if hasattr(entity, 'ability_scores'):
                # Try to read the investiture_ability field (e.g., "wisdom", "intelligence")
                investiture_ability = getattr(entity, 'investiture_ability', 'wisdom')
                if hasattr(entity.ability_scores, investiture_ability):
                    ability_mod = getattr(entity.ability_scores, investiture_ability).modifier

            healing = d8_1 + d8_2 + ability_mod
            logger.debug(f"   Rolled healing: {d8_1} + {d8_2} + {ability_mod} = {healing}")
        else:
            healing = self.healing_amount
            logger.debug(f"   Using specified healing: {healing}")

        # Apply healing
        if hasattr(target, 'health'):
            target.health.heal(healing)
            logger.info(f"   💚 {target.name} healed for {healing} HP")

        # NO Stormlight consumption — Regrowth's cost is Investiture Points, spent
        # by the resolver via InvestiturePointLedger (see combat_action_resolver).

        execution_event.healing_amount = healing

        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Healed {target.name} for {healing} HP"
        )


# ==========================================================================
# Lightweaver surges (plan 2.7)
#
# Only Windrunner/Skybreaker (Lashing) and Edgedancer/Truthwatcher
# (Progression) surges existed. BOTH shipped PCs — Aggi and Kali — are
# Lightweavers, so the party had ZERO usable Surges and the central fantasy
# of the setting was invisible in play.
#
# Lightweavers wield Illumination (light, sound, illusion) and Transformation
# (Soulcasting). Based on Cosmere 5e Radiant's Handbook v2.0.
# ==========================================================================


class IlluminationEvent(ActionEvent):
    """Event for a Lightweaver Illumination (illusion) — a free cantrip."""
    name: str = "Illumination"
    event_type: EventType = EventType.BASE_ACTION
    stormlight_cost: int = 0  # free cantrip (IA:469; surgebinding.json Illumination)
    illusion_type: str = "visual"


class Illumination(_TypedEventAction):
    """
    Illumination — Lightweaver light/sound illusion.

    **Mechanics (Cosmere 5e — Illumination cantrip, IA:449-476):**
    - Cost: FREE (a cantrip costs 0 Investiture)
    - Effect: a sensory illusion; observers contest with Intelligence
      (Investigation) vs the Lightweaver's Invested save DC
    - At higher Ideals the illusion can include sound and motion

    **Requirements:** Lightweaver or Truthwatcher Order, Surgebinding level 1+
    """

    event_class: type = IlluminationEvent
    name: str = "Illumination"
    description: str = "Weave light and sound into an illusion (Lightweaver)"
    stormlight_cost: int = 0  # free cantrip (IA:469)
    illusion_type: str = "visual"

    def _validate(self, declaration_event: IlluminationEvent) -> IlluminationEvent:
        entity = Entity.get(self.source_entity_uuid)

        if hasattr(entity, 'radiant_order'):
            # Fix per AUDIT_HARDCODED_SURGE_ACCURACY.md §4.4: Illumination belongs to
            # Lightweaver + Truthwatcher, not Lightweaver + Elsecaller. Elsecaller has
            # Transformation + Transportation.
            if entity.radiant_order not in ["Lightweaver", "Truthwatcher"]:
                logger.warning(f"Entity {entity.name} cannot use Illumination")
                return declaration_event.cancel(
                    status_message="Illumination requires the Lightweaver or Truthwatcher Order"
                )

        if hasattr(entity, 'surgebinding_level'):
            if entity.surgebinding_level < 1:
                return declaration_event.cancel(
                    status_message="Insufficient Lightweaver attunement"
                )

        # NO Stormlight gate: Illumination is a free cantrip (IA:469).

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message="Illumination prerequisites satisfied",
        )

    def _apply(self, execution_event: IlluminationEvent) -> IlluminationEvent:
        entity = Entity.get(self.source_entity_uuid)
        logger.info(f"✨ {entity.name} weaves an illusion ({self.illusion_type})")

        # An illusion makes the weaver harder to pin down: Invisible models
        # "observers cannot reliably see the real you" well enough for now.
        try:
            from dnd.conditions import Invisible
            condition = Invisible(
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.source_entity_uuid,
            )
            applied = condition.apply()
            if applied and not getattr(applied, "canceled", False):
                entity.active_conditions[condition.name] = condition
                entity.active_conditions_by_uuid[condition.uuid] = condition
                entity.active_conditions_by_source[condition.source_entity_uuid].append(
                    condition.name
                )
                logger.info(f"   🌫️  {entity.name} is obscured by the illusion")
        except Exception as e:
            logger.debug(f"   Could not apply illusion concealment: {e}")

        # NO Stormlight consumption — a cantrip is free (IA:469).

        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{entity.name} weaves an illusion",
        )


class SoulcastEvent(ActionEvent):
    """Event for a Lightweaver/Elsecaller Transformation (Soulcasting)."""
    name: str = "Soulcast"
    event_type: EventType = EventType.BASE_ACTION
    stormlight_cost: int = 0  # cantrip tier is free (IA:498)
    target_essence: str = "stone"
    # 0 = the free Transformation cantrip; >=5 = the costed 5th-level Soulcast Art.
    art_level: int = 0
    save_dc: int = 0        # Invested save DC the target rolls against (art tier)
    saved: bool = False     # True if the target's save succeeded (no effect)
    restrained: bool = False


class Soulcast(_TypedEventAction):
    """
    Soulcast — the Transformation Surge, in TWO tiers (the old single
    always-succeeding, unresisted "apply Restrained" collapsed three different
    book mechanics; AUDIT_HARDCODED_SURGE_ACCURACY.md §4.5).

    **Cantrip tier — `art_level = 0` (the default):** the free Transformation
    cantrip (IA:478-503). Minor effects only (clean/soil an object, warm/chill
    material, flicker flames). No cost, no save, no combat restraint.

    **Costed Art tier — `art_level = 5`:** the 5th-level "Soulcast" Art
    (IA:7472-7515), costed in Investiture Points and spent through
    InvestiturePointLedger. Soulcasting a creature toward stone forces a
    Constitution saving throw against the caster's Invested save DC; on a FAILED
    save the target is Restrained as its flesh hardens, and on a success there is
    no effect (the save-based combat Soulcast, IA:2386-2392). It is no longer an
    unconditional, auto-success effect.

    **Requirements:** Lightweaver or Elsecaller Order.
    """

    event_class: type = SoulcastEvent
    name: str = "Soulcast"
    description: str = "Transform matter with the Transformation Surge"
    stormlight_cost: int = 0
    target_essence: str = "stone"
    #: 0 = free cantrip; >=5 = the costed, save-based 5th-level Soulcast Art.
    art_level: int = 0
    #: Whether this casting requires a polestone (5th-level Art requires a large polestone)
    requires_polestone: bool = False

    def _validate(self, declaration_event: SoulcastEvent) -> SoulcastEvent:
        entity = Entity.get(self.source_entity_uuid)

        if hasattr(entity, 'radiant_order'):
            if entity.radiant_order not in ["Lightweaver", "Elsecaller"]:
                return declaration_event.cancel(
                    status_message="Soulcasting requires the Lightweaver or Elsecaller Order"
                )

        # The menu Surge is gated at the Second Ideal (registry min_surgebinding_level);
        # the free cantrip is available from there and the 5th-level Art tier above it.
        if hasattr(entity, 'surgebinding_level'):
            if entity.surgebinding_level < 2:
                return declaration_event.cancel(
                    status_message="Soulcasting requires the Second Ideal or higher"
                )

        # NO Stormlight gate: the cantrip is free and the Art tier is paid in
        # Investiture Points (spent by the resolver), never a Stormlight sphere.

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message="Soulcast prerequisites satisfied",
        )

    def _apply(self, execution_event: SoulcastEvent) -> SoulcastEvent:
        entity = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid)
        execution_event.art_level = int(self.art_level or 0)

        # ---- Cantrip tier: a free, minor transformation. No save, no restraint.
        if execution_event.art_level < 5:
            logger.info(f"✨ {entity.name} Soulcasts (cantrip) toward {self.target_essence}")
            return execution_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=(f"{entity.name} Soulcasts {self.target_essence} "
                                f"(minor transformation)"),
            )

        # ---- 5th-level Art tier: Soulcast a creature toward stone. The target
        # makes a Constitution saving throw vs the caster's Invested save DC; only
        # a FAILURE restrains it (IA:2386-2392). No target => nothing to resist.
        if target is None:
            logger.warning("⚠️ Soulcast (Art) has no target to affect")
            return execution_event.cancel(status_message="No target to Soulcast")

        import random
        from components.cosmere_rules import get_cosmere_rules

        prof = _proficiency_bonus(entity)
        investiture_mod = _best_modifier(entity, ("intelligence", "wisdom", "charisma"))
        save_dc = get_cosmere_rules().invested_save_dc(prof, investiture_mod)
        execution_event.save_dc = save_dc

        con_mod = int(target.ability_scores.constitution.modifier)
        save_prof = 0
        try:
            st = target.saving_throws.get_saving_throw("constitution")
            bonus = getattr(st, "bonus", None)
            save_prof = int(getattr(bonus, "normalized_score",
                                    getattr(bonus, "score", 0)) or 0)
        except Exception:
            save_prof = 0
        save_roll = random.randint(1, 20) + con_mod + save_prof
        saved = save_roll >= save_dc
        execution_event.saved = saved

        logger.info(f"✨ {entity.name} Soulcasts {target.name} toward stone — "
                    f"CON save {save_roll} vs DC {save_dc}: "
                    f"{'SAVED' if saved else 'FAILED'}")

        art_succeeded = not saved  # Art succeeded if target failed save

        # HB:13231-13241: 5th-level Soulcast requires a large polestone as material
        # component. The polestone outcome (crack/drain/untouched) is resolved AFTER
        # casting, and the cost is paid even if the art fails (target saves).
        if self.requires_polestone or execution_event.art_level >= 5:
            from components.combat.polestone import (
                Polestone, consume_polestone_for_art, resolve_polestone_outcome
            )

            # For testing/demo: create a mock large polestone
            # In production, this would come from entity's inventory
            polestone = Polestone(
                type="generic",
                size="large",
                value_sm=100,
                infused=True,
                cracked=False
            )

            # Resolve polestone outcome (cost paid regardless of success/failure)
            polestone_result = consume_polestone_for_art(
                polestone=polestone,
                art_name="Soulcast (5th-level)",
                interrupted=False,  # Art was fully cast
                art_succeeded=art_succeeded
            )

            if polestone_result.get("success"):
                outcome = polestone_result.get("outcome")
                logger.info(f"   💎 Polestone {outcome}: {polestone_result.get('message', '')}")
            else:
                logger.warning(f"   ⚠️ Polestone error: {polestone_result.get('error', 'unknown')}")

        if saved:
            return execution_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{target.name} resists the Soulcast",
            )

        try:
            from dnd.conditions import Restrained
            condition = Restrained(
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=target.uuid,
            )
            applied = condition.apply()
            if applied and not getattr(applied, "canceled", False):
                target.active_conditions[condition.name] = condition
                target.active_conditions_by_uuid[condition.uuid] = condition
                target.active_conditions_by_source[
                    condition.source_entity_uuid
                ].append(condition.name)
                execution_event.restrained = True
                logger.info(f"   🪨 {target.name} is restrained as its flesh hardens")
        except Exception as e:
            logger.debug(f"   Could not apply Soulcast restraint: {e}")

        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{entity.name} Soulcasts {target.name} into hardening stone",
        )
