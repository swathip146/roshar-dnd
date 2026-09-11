"""
The two PHB conditions the vendored engine never implemented: Petrified and Exhaustion.

`data/rules/srd/conditions.json` lists 15 conditions. `dnd.conditions` implements 13.
The gap was found by comparing the two sets rather than by reading the engine's docs:

    SRD 15   Blinded Charmed Deafened Exhaustion Frightened Grappled Incapacitated
             Invisible Paralyzed Petrified Poisoned Prone Restrained Stunned Unconscious
    engine   the same, MINUS Exhaustion and Petrified

Both are written here rather than in `external/dnd_engine`, which plan §4 treats as
frozen third-party code, and are registered into `dnd.conditions` so
`wrapper.apply_condition("petrified")` finds them exactly like the built-in thirteen.

Each condition is built out of the same seams the engine's own `Paralyzed` uses, so
they compose with everything else instead of being a parallel system:

    advantage against       equipment.ac_bonus.to_target_static
    auto-fail a save        saving_throws.get_saving_throw(x).bonus  (AUTOMISS)
    damage resistance       health.damage_reduction.self_static     (RESISTANCE)
    disadvantage on X       the matching self_static value
    speed / HP maximum      max constraints on the matching value

`_apply` returns `(value_modifier_pairs, [], sub_condition_uuids, event)`, and the
engine's own `BaseCondition._remove` undoes everything in the first list — which is why
every modifier below is appended to `outs`. A modifier that is applied but not returned
is a permanent one.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from config.logging_config import get_logger

logger = get_logger(__name__)

# 5e PHB p.291: exhaustion is measured in six levels, and a creature suffers the
# effects of its current level AND all lower levels.
MAX_EXHAUSTION_LEVEL = 6

# The 18 SRD skills. Exhaustion level 1 is disadvantage on ability CHECKS, which in
# this engine means each skill's own `skill_bonus` — not the shared ability score,
# which attack rolls also read.
_SKILLS = ("acrobatics", "animal_handling", "arcana", "athletics", "deception",
           "history", "insight", "intimidation", "investigation", "medicine",
           "nature", "perception", "performance", "persuasion", "religion",
           "sleight_of_hand", "stealth", "survival")

_ABILITIES = ("strength", "dexterity", "constitution",
              "intelligence", "wisdom", "charisma")


def register_missing_conditions() -> List[str]:
    """
    Define Petrified and Exhaustion and register them into `dnd.conditions`.

    Returns the names registered. Idempotent: re-registering would rebind the classes
    and orphan any instance already applied to an entity.
    """
    import dnd.conditions as conditions

    registered: List[str] = []
    for name, factory in (("Petrified", _build_petrified),
                          ("Exhaustion", _build_exhaustion)):
        if getattr(conditions, name, None) is not None:
            continue
        setattr(conditions, name, factory())
        registered.append(name)

    return registered


def _imports():
    """The engine symbols both conditions need. Imported late — see module docstring."""
    from dnd.core.base_conditions import BaseCondition
    from dnd.core.events import Event, EventPhase
    from dnd.core.modifiers import (AdvantageModifier, AdvantageStatus,
                                    AutoHitModifier, AutoHitStatus, DamageType,
                                    NumericalModifier, ResistanceModifier,
                                    ResistanceStatus)
    from dnd.entity import Entity
    return (BaseCondition, Event, EventPhase, AdvantageModifier, AdvantageStatus,
            AutoHitModifier, AutoHitStatus, DamageType, NumericalModifier,
            ResistanceModifier, ResistanceStatus, Entity)


# ---------------------------------------------------------------------------
# Petrified
# ---------------------------------------------------------------------------

def _build_petrified():
    """
    PHB: a petrified creature is transformed into stone. It is incapacitated, can't
    move or speak, and is unaware of its surroundings; attack rolls against it have
    advantage; it automatically fails Strength and Dexterity saving throws; it has
    resistance to ALL damage; and it is immune to poison and disease.

    Three of those five clauses are shared with `Paralyzed`, so this reuses that
    structure. The differences are the ones that matter:

      * resistance to all damage — Paralyzed has none, and this is the clause that
        makes Petrified survivable rather than a death sentence. Applied across all
        13 damage types, because the engine stores resistance per type.
      * NO auto-crit within 5 feet. Paralyzed grants it, Petrified does not. Copying
        Paralyzed wholesale would have made every hit on a statue a critical.
    """
    (BaseCondition, Event, EventPhase, AdvantageModifier, AdvantageStatus,
     AutoHitModifier, AutoHitStatus, DamageType, NumericalModifier,
     ResistanceModifier, ResistanceStatus, Entity) = _imports()

    from dnd.conditions import Incapacitated

    class Petrified(BaseCondition):
        """A petrified creature is transformed, along with any nonmagical object it is
        wearing or carrying, into a solid inanimate substance (usually stone). Its
        weight increases by a factor of ten, and it ceases aging. The creature is
        incapacitated, can't move or speak, and is unaware of its surroundings. Attack
        rolls against the creature have advantage. The creature automatically fails
        Strength and Dexterity saving throws. The creature has resistance to all
        damage. The creature is immune to poison and disease."""

        name: str = "Petrified"
        description: str = (
            "A petrified creature is transformed into a solid inanimate substance. It "
            "is incapacitated, can't move or speak, and is unaware of its "
            "surroundings. Attack rolls against it have advantage. It automatically "
            "fails Strength and Dexterity saving throws. It has resistance to all "
            "damage and is immune to poison and disease.")

        def _apply(self, declaration_event: "Event") -> Tuple[
                List[Tuple[UUID, UUID]], List[UUID], List[UUID], Optional["Event"]]:
            if not self.target_entity_uuid:
                raise ValueError("Target entity UUID is not set")

            target = Entity.get(self.target_entity_uuid)
            if not isinstance(target, Entity):
                return [], [], [], declaration_event.cancel(
                    status_message=f"Target entity {self.target_entity_uuid} not found")

            outs: List[Tuple[UUID, UUID]] = []
            sub_conditions: List[UUID] = []

            event = declaration_event.phase_to(
                EventPhase.EXECUTION, update={"condition": self},
                status_message=f"Applying Petrified to {target.name}")

            # "Incapacitated, can't move or speak" — delegate to the engine's own
            # Incapacitated, which already zeroes actions, bonus actions, reactions
            # and speed. Reimplementing it here would drift from the built-in one.
            incapacitated = Incapacitated(
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
                parent_condition=self.uuid)
            sub_event = target.add_condition(incapacitated, parent_event=event)
            if sub_event is not None and sub_event.phase == EventPhase.COMPLETION:
                sub_conditions.append(incapacitated.uuid)

            # "Attack rolls against the creature have advantage."
            outs.append((
                target.equipment.ac_bonus.uuid,
                target.equipment.ac_bonus.to_target_static.add_advantage_modifier(
                    AdvantageModifier(
                        name="Petrified", value=AdvantageStatus.ADVANTAGE,
                        source_entity_uuid=self.target_entity_uuid,
                        target_entity_uuid=self.source_entity_uuid))))

            # "Automatically fails Strength and Dexterity saving throws."
            for ability in ("strength", "dexterity"):
                save = target.saving_throws.get_saving_throw(ability)
                outs.append((
                    save.bonus.uuid,
                    save.bonus.self_static.add_auto_hit_modifier(
                        AutoHitModifier(
                            name="Petrified", value=AutoHitStatus.AUTOMISS,
                            source_entity_uuid=self.target_entity_uuid,
                            target_entity_uuid=self.source_entity_uuid))))

            # "Resistance to all damage" + "immune to poison".
            #
            # The engine keys resistance by damage type with no "all" wildcard, so
            # every type is set explicitly. Poison is IMMUNITY, not RESISTANCE — the
            # PHB lists that separately, and a stone statue takes no poison at all.
            reduction = target.health.damage_reduction
            for damage_type in DamageType:
                status = (ResistanceStatus.IMMUNITY
                          if damage_type == DamageType.POISON
                          else ResistanceStatus.RESISTANCE)
                outs.append((
                    reduction.uuid,
                    reduction.self_static.add_resistance_modifier(
                        ResistanceModifier(
                            name="Petrified", value=status,
                            damage_type=damage_type,
                            source_entity_uuid=self.target_entity_uuid,
                            target_entity_uuid=self.source_entity_uuid))))

            return outs, [], sub_conditions, event.phase_to(
                EventPhase.EFFECT, update={"condition": self},
                status_message=f"{target.name} is petrified")

    return Petrified


# ---------------------------------------------------------------------------
# Exhaustion
# ---------------------------------------------------------------------------

def _build_exhaustion():
    """
    PHB p.291, six cumulative levels:

        1  disadvantage on ability checks
        2  speed halved
        3  disadvantage on attack rolls and saving throws
        4  hit point maximum halved
        5  speed reduced to 0
        6  death

    "A creature suffers the effect of its current level as well as all lower levels",
    so level 3 means levels 1, 2 AND 3 — the effects are applied cumulatively in one
    pass rather than as three stacked conditions.

    Note this depends on the advantage fix in `engine_patches.py`: before it,
    `_roll_with_disadvantage` rolled a single die, so levels 1 and 3 did nothing at all.
    """
    (BaseCondition, Event, EventPhase, AdvantageModifier, AdvantageStatus,
     AutoHitModifier, AutoHitStatus, DamageType, NumericalModifier,
     ResistanceModifier, ResistanceStatus, Entity) = _imports()

    class Exhaustion(BaseCondition):
        """Exhaustion is measured in six levels, and a creature suffers the effects of
        its current level as well as all lower levels. 1: disadvantage on ability
        checks. 2: speed halved. 3: disadvantage on attack rolls and saving throws.
        4: hit point maximum halved. 5: speed reduced to 0. 6: death."""

        name: str = "Exhaustion"
        description: str = (
            "Exhaustion in six cumulative levels: 1 disadvantage on ability checks, "
            "2 speed halved, 3 disadvantage on attack rolls and saving throws, "
            "4 hit point maximum halved, 5 speed reduced to 0, 6 death.")
        level: int = 1

        def _apply(self, declaration_event: "Event") -> Tuple[
                List[Tuple[UUID, UUID]], List[UUID], List[UUID], Optional["Event"]]:
            if not self.target_entity_uuid:
                raise ValueError("Target entity UUID is not set")

            target = Entity.get(self.target_entity_uuid)
            if not isinstance(target, Entity):
                return [], [], [], declaration_event.cancel(
                    status_message=f"Target entity {self.target_entity_uuid} not found")

            level = max(1, min(MAX_EXHAUSTION_LEVEL, int(self.level)))
            outs: List[Tuple[UUID, UUID]] = []

            event = declaration_event.phase_to(
                EventPhase.EXECUTION, update={"condition": self},
                status_message=f"Applying Exhaustion {level} to {target.name}")

            def disadvantage(value, label: str) -> None:
                outs.append((
                    value.uuid,
                    value.self_static.add_advantage_modifier(
                        AdvantageModifier(
                            name=f"Exhaustion {level} ({label})",
                            value=AdvantageStatus.DISADVANTAGE,
                            source_entity_uuid=self.target_entity_uuid,
                            target_entity_uuid=self.source_entity_uuid))))

            def constrain_max(value, cap: int, label: str) -> None:
                outs.append((
                    value.uuid,
                    value.self_static.add_max_constraint(
                        constraint=NumericalModifier(
                            name=f"Exhaustion {level} ({label})", value=cap,
                            source_entity_uuid=self.target_entity_uuid,
                            target_entity_uuid=self.source_entity_uuid))))

            # Level 1 — disadvantage on ability checks, and ONLY checks.
            #
            # This must NOT be applied to `ability_scores.<x>.ability_score`, even
            # though that reads like "the ability". Attack rolls derive from the same
            # value, so doing that gave level 1 attack disadvantage too — measured at
            # a hit rate of 0.63 -> 0.35, when RAW does not touch attacks until level
            # 3. The per-skill `skill_bonus` is the seam that affects checks alone.
            if level >= 1:
                for skill_name in _SKILLS:
                    skill = target.skill_set.get_skill(skill_name)
                    if skill is not None:
                        disadvantage(skill.skill_bonus, "ability checks")

            # Levels 2 and 5 — speed halved, then zero. Level 5 wins, so it is applied
            # as a single constraint rather than halving twice.
            movement = target.action_economy.movement
            if level >= 5:
                constrain_max(movement, 0, "speed 0")
            elif level >= 2:
                constrain_max(movement, max(0, movement.score // 2), "speed halved")

            # Level 3 — disadvantage on attack rolls and saving throws.
            if level >= 3:
                disadvantage(target.equipment.attack_bonus, "attacks")
                for ability_name in _ABILITIES:
                    save = target.saving_throws.get_saving_throw(ability_name)
                    disadvantage(save.bonus, "saves")

            # Level 4 — hit point maximum halved. Expressed as a NEGATIVE bonus on
            # max_hit_points_bonus, because the engine derives the maximum from hit
            # dice and there is no writable maximum to cap.
            #
            # Max HP must come from `DnDEngineWrapper.get_entity_max_hp`, NOT from
            # `health.get_max_hit_dices_points()` — the latter ignores
            # max_hit_points_bonus, which is the very value being written here, so
            # halving twice would compound off a stale figure.
            if level >= 4:
                from components.dnd_engine_wrapper import DnDEngineWrapper

                current_max = DnDEngineWrapper.get_entity_max_hp(target)
                outs.append((
                    target.health.max_hit_points_bonus.uuid,
                    target.health.max_hit_points_bonus.self_static
                    .add_value_modifier(NumericalModifier(
                        name=f"Exhaustion {level} (HP max halved)",
                        value=-(current_max // 2),
                        source_entity_uuid=self.target_entity_uuid,
                        target_entity_uuid=self.source_entity_uuid))))

            # Level 6 — death. Recorded, not enacted: killing the entity is the
            # session's call (it owns death saves and the endgame), so this surfaces
            # the fact rather than silently removing a character mid-resolution.
            if level >= MAX_EXHAUSTION_LEVEL:
                logger.warning(
                    f"💀 {target.name} has reached exhaustion level 6 (death)")

            logger.info(f"   😫 {target.name}: exhaustion level {level}")
            return outs, [], [], event.phase_to(
                EventPhase.EFFECT, update={"condition": self},
                status_message=f"{target.name} has exhaustion {level}")

    return Exhaustion
