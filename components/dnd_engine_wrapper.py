"""
dnd_engine Integration Wrapper for Roshar D&D

Bridges the gap between:
- Your GameEngine (state authority) and CharacterManager (character data)
- dnd_engine's Entity-Component-System (mechanics engine)

This wrapper:
1. Converts CharacterManager characters to dnd_engine Entities
2. Executes skill checks and combat via dnd_engine
3. Syncs results back to GameEngine state
4. Preserves your existing state hierarchy (no duplication)
"""

import sys
from pathlib import Path

# Python 3.9 compatibility: Patch typing module before importing dnd_engine
try:
    from typing import Self
except ImportError:
    # Python < 3.11: Add Self from typing_extensions to typing module
    from typing_extensions import Self
    import typing
    typing.Self = Self

# Add dnd_engine to path
dnd_engine_path = Path(__file__).parent.parent / "external" / "dnd_engine"
sys.path.insert(0, str(dnd_engine_path))

from dataclasses import dataclass, field
from typing import Dict, Optional, Any, List
import logging
from uuid import UUID

# Import dnd_engine components
from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.skills import SkillSetConfig
from dnd.blocks.saving_throws import SavingThrowSetConfig
from dnd.blocks.health import HealthConfig
from dnd.blocks.equipment import EquipmentConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.core.events import SkillCheckEvent, SkillName, AbilityName
from dnd.core.dice import Dice, RollType
from dnd.core.modifiers import DamageType

# Your existing imports
from config.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class DnDEngineWrapper:
    """
    Wrapper that integrates dnd_engine with Roshar GameEngine.

    Responsibilities:
    - Translate CharacterManager data → dnd_engine Entities
    - Execute skill checks via dnd_engine Action system
    - Execute combat via dnd_engine Combat system
    - Sync results back to GameEngine state
    - Preserve existing state hierarchy (GameEngine remains authority)
    """

    game_engine: Any  # GameEngine instance
    character_manager: Any  # CharacterManager instance
    entities: Dict[str, Entity] = field(default_factory=dict)
    _spawn_index: int = 0  # Plan 1.1: hands out distinct provisional positions

    def __post_init__(self):
        """Initialize entities from existing characters."""
        logger.info("Initializing DnDEngineWrapper")
        self._sync_characters_to_entities()
        # Plan 1.1: senses must be computed AFTER all entities exist, or each
        # entity's sense map is missing everyone created after it.
        self.refresh_senses()
        logger.info(f"Synced {len(self.entities)} characters to dnd_engine entities")

    def _next_spawn_position(self) -> tuple:
        """
        Hand out distinct provisional grid positions (plan 1.1).

        Entities previously all defaulted to (0,0), which broke line of sight
        for every attack. Real tactical placement happens in CombatInitializer;
        this only guarantees distinctness so senses can be computed at all.
        """
        idx = self._spawn_index
        self._spawn_index += 1
        # Spread along a line, ADJACENT (1 tile apart) rather than spaced: melee
        # reach is 5 ft = 1 tile, and a 2-tile gap made every unarmed/melee
        # attack fail with 'Target entity not in reach'. CombatInitializer
        # assigns real tactical positions at encounter start; this default just
        # has to be distinct AND within melee reach of a neighbour.
        return (idx, 0)

    # D&D 5e hit die by class. Plan 1.7: this was hardcoded to d8 for every
    # character regardless of class or CR.
    _HIT_DIE_BY_CLASS = {
        "barbarian": 12,
        "fighter": 10, "paladin": 10, "ranger": 10, "radiant": 10,
        "bard": 8, "cleric": 8, "druid": 8, "monk": 8, "rogue": 8, "warlock": 8,
        "sorcerer": 6, "wizard": 6,
        # Roshar / Cosmere orders
        "windrunner": 10, "skybreaker": 10, "stoneward": 10, "dustbringer": 10,
        "edgedancer": 8, "truthwatcher": 8, "lightweaver": 6, "elsecaller": 6,
        "willshaper": 8, "bondsmith": 10,
        "herald": 12,
        # Common monster shorthand
        "goblin": 6, "beast": 8, "undead": 8, "construct": 10,
    }

    def _hit_die_for_class(self, character_class: str) -> int:
        """Hit die size for a class (plan 1.7). Defaults to d8."""
        return self._HIT_DIE_BY_CLASS.get((character_class or "").strip().lower(), 8)

    @staticmethod
    def get_entity_max_hp(entity) -> int:
        """
        An entity's TRUE maximum HP.

        `Health.get_max_hit_dices_points()` returns only the hit-dice component
        and ignores `max_hit_points_bonus`. Since plan 1.7 uses that bonus to
        reconcile the engine to CharacterManager's authored max_hp, calling
        get_max_hit_dices_points() alone under-reports (or over-reports) max HP:
        a 7 HP goblin read as 17. Always use this helper for "max HP".
        """
        con_mod = entity.ability_scores.constitution.modifier
        return (entity.health.get_max_hit_dices_points(con_mod)
                + entity.health.max_hit_points_bonus.score)

    @staticmethod
    def get_entity_current_hp(entity) -> int:
        """An entity's current HP (counterpart to get_entity_max_hp)."""
        return entity.health.get_total_hit_points(
            entity.ability_scores.constitution.modifier
        )

    def refresh_senses(self, max_distance: int = 30) -> None:
        """
        Recompute every entity's sense map (plan 1.1).

        `dnd/actions.py:40 validate_line_of_sight` requires
        `target.uuid in source.senses.entities`, and only
        Entity.update_all_entities_senses() populates that. It must be called
        after entity creation and after ANY movement, or attacks silently
        cancel with 'Target entity not in line of sight'.
        """
        try:
            Entity.update_all_entities_senses(max_distance=max_distance)
            logger.debug(f"👁️  Refreshed senses for {len(self.entities)} entities "
                         f"(range {max_distance})")
        except Exception as e:
            logger.error(f"❌ Failed to refresh entity senses: {e}")

    def set_entity_position(self, char_id: str, position: tuple) -> bool:
        """
        Move an entity and refresh senses (plan 1.1).

        Always go through this rather than assigning `entity.position` directly,
        so the sense maps stay consistent with the grid.
        """
        entity = self.entities.get(char_id)
        if entity is None:
            logger.warning(f"⚠️ Cannot position unknown entity: {char_id}")
            return False
        entity.position = tuple(position)
        self.refresh_senses()
        logger.debug(f"📍 {char_id} -> {tuple(position)}")
        return True

    def _sync_characters_to_entities(self):
        """
        Convert CharacterManager characters to dnd_engine Entities.

        Maps:
        - CharacterData.ability_scores → AbilityScores block
        - CharacterData.skills → Skills block
        - CharacterData.hit_points → Health block
        - CharacterData.armor_class → Equipment block (shield bonus)
        """
        from dnd.blocks.skills import SkillConfig

        for char_id, character in self.character_manager.characters.items():
            # Create entity configuration
            # AbilityConfig's field is `ability_score`, NOT `score`. Passing
            # score=N is silently ignored by pydantic and the ability defaults
            # to 10 -- so EVERY character had all six abilities stuck at 10:
            # no STR on attacks, no DEX on AC, no CON on HP. (Found while
            # chasing the plan-1.7 HP mismatch; not in the original audit.)
            ability_scores_config = AbilityScoresConfig(
                strength=AbilityConfig(
                    ability_score=character.ability_scores.get("strength", 10)),
                dexterity=AbilityConfig(
                    ability_score=character.ability_scores.get("dexterity", 10)),
                constitution=AbilityConfig(
                    ability_score=character.ability_scores.get("constitution", 10)),
                intelligence=AbilityConfig(
                    ability_score=character.ability_scores.get("intelligence", 10)),
                wisdom=AbilityConfig(
                    ability_score=character.ability_scores.get("wisdom", 10)),
                charisma=AbilityConfig(
                    ability_score=character.ability_scores.get("charisma", 10))
            )

            # Create skill configurations
            skill_names = [
                "acrobatics", "animal_handling", "arcana", "athletics",
                "deception", "history", "insight", "intimidation",
                "investigation", "medicine", "nature", "perception",
                "performance", "persuasion", "religion", "sleight_of_hand",
                "stealth", "survival"
            ]

            skill_configs = {}
            for skill_name in skill_names:
                is_proficient = character.skills.get(skill_name, False)
                has_expertise = skill_name in character.expertise_skills
                skill_configs[skill_name] = SkillConfig(
                    proficiency=is_proficient,
                    expertise=has_expertise
                )

            skill_set_config = SkillSetConfig(**skill_configs)

            # Create saving throw configurations
            from dnd.blocks.saving_throws import SavingThrowConfig
            saving_throw_proficiencies = character.saving_throw_proficiencies

            saving_throws_config = SavingThrowSetConfig(
                strength_saving_throw=SavingThrowConfig(
                    proficiency="strength" in saving_throw_proficiencies
                ),
                dexterity_saving_throw=SavingThrowConfig(
                    proficiency="dexterity" in saving_throw_proficiencies
                ),
                constitution_saving_throw=SavingThrowConfig(
                    proficiency="constitution" in saving_throw_proficiencies
                ),
                intelligence_saving_throw=SavingThrowConfig(
                    proficiency="intelligence" in saving_throw_proficiencies
                ),
                wisdom_saving_throw=SavingThrowConfig(
                    proficiency="wisdom" in saving_throw_proficiencies
                ),
                charisma_saving_throw=SavingThrowConfig(
                    proficiency="charisma" in saving_throw_proficiencies
                )
            )

            # LOG CHARACTER HP VALUES BEFORE CREATING ENTITY
            char_hp = character.hit_points
            max_hp = char_hp.get("maximum", 10)
            current_hp = char_hp.get("current", 10)

            logger.info(f"   🏥 Creating dnd_engine entity for {character.name} (ID: {char_id})")
            logger.info(f"      CharacterManager HP data: {char_hp}")
            logger.info(f"      Extracted max_hp: {max_hp}")
            logger.info(f"      Extracted current_hp: {current_hp}")

            # dnd_engine models HP as hit dice, not a flat max_hp, so we must
            # translate. Plan 1.7: hit_dice_value was hardcoded to 8, so max HP
            # became level * 4.5 REGARDLESS of the character's real HP — a
            # 7 HP level-3 goblin came out with 18. CharacterManager and the
            # engine then disagreed about how much HP everyone had.
            #
            # Fix: pick the hit die from the class, then use
            # max_hit_points_bonus to reconcile EXACTLY to the authored max_hp.
            # CharacterManager stays the authority on HP; the engine matches it.
            from dnd.blocks.health import HitDiceConfig

            # damage_taken carries the current/max delta
            damage_taken = max(0, max_hp - current_hp)

            hit_dice_count = max(1, character.level)
            hit_dice_value = self._hit_die_for_class(character.character_class)
            con_mod = (character.ability_scores.get("constitution", 10) - 10) // 2

            # Mirror dnd_engine's own arithmetic exactly (dnd/blocks/health.py):
            #   HitDice.hit_points  = full die at level 1
            #                       + (count - 1) * (die // 2 + 1)   [average mode]
            #   Health.get_max_hit_dices_points = hit_points + con_mod * count
            # Getting this wrong by even the con term leaves CharacterManager and
            # the engine disagreeing about everyone's HP.
            dice_hp = hit_dice_value + (hit_dice_count - 1) * (hit_dice_value // 2 + 1)
            derived_hp = dice_hp + con_mod * hit_dice_count

            # Close the gap so the engine's total matches the authored max_hp
            # exactly. May be negative (a low-HP monster at a high level).
            max_hit_points_bonus = max_hp - derived_hp

            hit_dice_config = HitDiceConfig(
                hit_dice_value=hit_dice_value,
                hit_dice_count=hit_dice_count,
                mode="average"  # Use average HP calculation
            )

            health_config = HealthConfig(
                hit_dices=[hit_dice_config],
                max_hit_points_bonus=max_hit_points_bonus,
                temporary_hit_points=char_hp.get("temporary", 0),
                damage_reduction=0
            )

            logger.info(f"      Converted to hit dice model:")
            logger.info(f"         Hit dice: {hit_dice_count}d{hit_dice_value} "
                        f"(derived {derived_hp} + bonus {max_hit_points_bonus} "
                        f"= {max_hp} authored)")
            logger.info(f"         Damage taken: {damage_taken}")

            # Create equipment configuration
            equipment_config = EquipmentConfig(
                unarmored_ac=character.armor_class
            )

            # Create action economy configuration (standard D&D 5e)
            action_economy_config = ActionEconomyConfig(
                actions=1,  # Standard action
                bonus_actions=1,  # Bonus action
                reactions=1,  # Reaction
                movement=character.speed  # Movement speed
            )

            # Plan 1.1: every entity MUST have a distinct position.
            #
            # This was the root cause of audit finding #1: EntityConfig was built
            # without `position`, so every entity defaulted to (0,0) with empty
            # senses. dnd/actions.py:40 validate_line_of_sight() requires
            # `target.uuid in source.senses.entities`, which is only populated by
            # Entity.update_all_entities_senses(). With no positions and no sense
            # update, that check ALWAYS failed:
            #     EventPhase.CANCEL 'Target entity not in line of sight'
            # i.e. no attack in the game could ever land.
            #
            # Positions are provisional here (a spaced line); combat_initializer
            # assigns real tactical positions at encounter start. What matters is
            # that they are distinct and non-default so senses can be computed.
            position = self._next_spawn_position()

            entity_config = EntityConfig(
                ability_scores=ability_scores_config,
                skill_set=skill_set_config,
                saving_throws=saving_throws_config,
                health=health_config,
                equipment=equipment_config,
                action_economy=action_economy_config,
                proficiency_bonus=character.proficiency_bonus,
                position=position,
            )

            # Create entity using the config
            from uuid import uuid4
            entity = Entity.create(
                source_entity_uuid=uuid4(),  # Generate new UUID
                name=character.name,
                config=entity_config
            )

            # Set damage_taken to match current HP
            entity.health.damage_taken = damage_taken

            # LOG ENTITY HP VALUES AFTER CREATION
            con_mod = entity.ability_scores.constitution.modifier
            entity_max_hp = self.get_entity_max_hp(entity)
            entity_total_hp = entity.health.get_total_hit_points(con_mod)

            logger.info(f"      ✅ Entity created:")
            logger.info(f"         Constitution modifier: {con_mod}")
            logger.info(f"         entity.health.get_max_hit_dices_points(con_mod): {entity_max_hp}")
            logger.info(f"         entity.health.damage_taken: {entity.health.damage_taken}")
            logger.info(f"         entity.health.get_total_hit_points(con_mod): {entity_total_hp}")

            self.entities[char_id] = entity
            logger.debug(f"Created entity for {character.name} (ID: {char_id})")

    def _sync_entity_to_game_state(self, char_id: str):
        """
        Sync dnd_engine Entity state back to GameEngine.

        Updates:
        - Character HP (if changed in combat)
        - Conditions (if applied via dnd_engine)
        """
        entity = self.entities.get(char_id)
        if not entity:
            return

        # Update HP in CharacterManager
        # Get constitution modifier from entity
        con_modifier = entity.ability_scores.constitution.modifier
        if hasattr(con_modifier, 'normalized_score'):
            con_mod_value = int(con_modifier.normalized_score)
        else:
            con_mod_value = int(con_modifier)
        current_hp = entity.health.get_total_hit_points(con_mod_value)

        character = self.character_manager.characters.get(char_id)
        if character:
            character.hit_points["current"] = int(current_hp)
            logger.debug(f"Synced HP for {char_id}: {current_hp}")

    def execute_skill_check(
        self,
        character_id: str,
        skill: str,
        dc: int,
        advantage: bool = False,
        disadvantage: bool = False
    ) -> Dict[str, Any]:
        """
        Execute skill check using dnd_engine mechanics.

        Integrates with your existing 7-step pipeline:
        - Step 1-3: GameEngine determines DC, advantage (already done)
        - Step 4: THIS METHOD executes roll via dnd_engine
        - Step 5-7: GameEngine evaluates result, logs outcome

        Args:
            character_id: Character UUID
            skill: Skill name (e.g., "athletics", "persuasion")
            dc: Difficulty class
            advantage: Roll with advantage
            disadvantage: Roll with disadvantage

        Returns:
            {
                "success": bool,
                "roll": int (total roll),
                "natural_roll": int (d20 result),
                "modifier": int,
                "dc": int,
                "advantage": bool,
                "disadvantage": bool
            }
        """
        entity = self.entities.get(character_id)
        if not entity:
            logger.error(f"Character {character_id} not found in entities")
            return {"success": False, "error": "Character not found"}

        # SkillName is a Literal type, not an enum - just use the string directly
        valid_skills = [
            "acrobatics", "animal_handling", "arcana", "athletics",
            "deception", "history", "insight", "intimidation",
            "investigation", "medicine", "nature", "perception",
            "performance", "persuasion", "religion", "sleight_of_hand",
            "stealth", "survival"
        ]

        skill_name = skill.lower()
        if skill_name not in valid_skills:
            logger.error(f"Invalid skill name: {skill}")
            return {"success": False, "error": f"Invalid skill: {skill}"}

        # For self-skill-checks, we need to get the skill bonus and roll directly
        # Get the skill bonus modifiable value
        skill_bonus_value = entity.skill_bonus(target_entity_uuid=None, skill_name=skill_name)

        # Roll d20 with modifiers
        roll = entity.roll_d20(skill_bonus_value, RollType.CHECK)

        # Determine success
        success = roll.total >= dc
        from dnd.core.dice import AttackOutcome
        outcome = AttackOutcome.HIT if success else AttackOutcome.MISS

        # Sync back to GameEngine (in case of state changes)
        self._sync_entity_to_game_state(character_id)

        logger.info(f"Skill check: {character_id} rolled {skill} vs DC {dc}: {roll.total} ({'Success' if success else 'Failure'})")

        return {
            "success": success,
            "roll": roll.total,
            "natural_roll": roll.results,
            "modifier": roll.total - roll.results,
            "dc": dc,
            "advantage": advantage,
            "disadvantage": disadvantage,
            "breakdown": {
                "natural": roll.results,
                "modifier": roll.total - roll.results,
                "total": roll.total
            }
        }

    def execute_attack(
        self,
        attacker_id: str,
        target_id: str,
        weapon: str = "unarmed",
        advantage: bool = False,
        disadvantage: bool = False
    ) -> Dict[str, Any]:
        """
        Execute attack using dnd_engine combat mechanics.

        Handles:
        - Attack roll (d20 + attack bonus)
        - AC comparison
        - Damage roll (weapon dice + modifiers)
        - HP reduction
        - Critical hits

        Args:
            attacker_id: Attacker character UUID
            target_id: Target character UUID
            weapon: Weapon name (default: "unarmed")
            advantage: Attack with advantage
            disadvantage: Attack with disadvantage

        Returns:
            {
                "hit": bool,
                "attack_roll": int,
                "natural_roll": int,
                "target_ac": int,
                "damage": int,
                "damage_type": str,
                "critical": bool,
                "target_hp_remaining": int
            }
        """
        attacker = self.entities.get(attacker_id)
        target = self.entities.get(target_id)

        if not attacker or not target:
            logger.error(f"Attack failed: attacker={attacker_id} or target={target_id} not found")
            return {"hit": False, "error": "Attacker or target not found"}

        # For now, use simple attack mechanics using entity's roll_d20 method
        # Get attack bonus
        str_mod = attacker.ability_scores.strength.modifier
        attack_modifier = int(str_mod) if not hasattr(str_mod, 'normalized_score') else int(str_mod.normalized_score)

        # Create a modifiable value for attack bonus
        from dnd.core.values import ModifiableValue
        attack_bonus = ModifiableValue.create(
            source_entity_uuid=attacker.uuid,
            base_value=attack_modifier,
            value_name="Attack Bonus"
        )

        # Roll attack
        attack_roll = attacker.roll_d20(attack_bonus, RollType.ATTACK)
        attack_total = attack_roll.total

        # Get target AC
        dex_mod = target.ability_scores.dexterity.modifier
        dex_modifier = int(dex_mod) if not hasattr(dex_mod, 'normalized_score') else int(dex_mod.normalized_score)
        target_ac = 10 + dex_modifier

        hit = attack_total >= target_ac
        critical = attack_roll.results == 20

        damage = 0
        if hit:
            # Create damage dice (1d6 + strength modifier for unarmed)
            damage_dice = Dice(
                num_dice=1,
                die_value=6,
                source_entity_uuid=attacker.uuid,
                target_entity_uuid=target.uuid,
                roll_type=RollType.DAMAGE
            )
            damage_roll = damage_dice.roll()
            damage = damage_roll.total + attack_modifier
            if critical:
                damage *= 2

            # Apply damage to target.
            # Plan 1.2: take_damage's real signature is
            # (damage, damage_type, source_entity_uuid) -- passing only the
            # amount raised TypeError, so damage was never actually applied.
            target.health.take_damage(
                damage,
                DamageType.BLUDGEONING,
                attacker.uuid,
            )

        # Sync both entities back to GameEngine
        self._sync_entity_to_game_state(attacker_id)
        self._sync_entity_to_game_state(target_id)

        logger.info(f"Attack: {attacker_id} attacked {target_id} with {weapon}: {'HIT' if hit else 'MISS'} (Roll: {attack_total} vs AC {target_ac})")

        # Get target's remaining HP
        target_con_mod = target.ability_scores.constitution.modifier
        target_con_value = int(target_con_mod) if not hasattr(target_con_mod, 'normalized_score') else int(target_con_mod.normalized_score)
        target_hp_remaining = target.health.get_total_hit_points(target_con_value)

        return {
            "hit": hit,
            "attack_roll": attack_total,
            "natural_roll": attack_roll.results,
            "target_ac": target_ac,
            "damage": damage if hit else 0,
            "damage_type": "bludgeoning",
            "critical": critical,
            "target_hp_remaining": int(target_hp_remaining)
        }

    # Plan 1.5: the 15 conditions dnd_engine actually implements, keyed by the
    # lowercase names callers use. apply_condition() previously logged
    # "(not yet implemented)" and returned None, so 13 of these were unused and
    # no condition ever affected play.
    _CONDITION_ALIASES = {
        "blinded": "Blinded", "blind": "Blinded",
        "charmed": "Charmed",
        "dashing": "Dashing", "dash": "Dashing",
        "deafened": "Deafened", "deaf": "Deafened",
        "dodging": "Dodging", "dodge": "Dodging",
        "frightened": "Frightened", "afraid": "Frightened",
        "grappled": "Grappled",
        "incapacitated": "Incapacitated",
        "invisible": "Invisible",
        "paralyzed": "Paralyzed",
        "poisoned": "Poisoned",
        "prone": "Prone",
        "restrained": "Restrained",
        "stunned": "Stunned",
        "unconscious": "Unconscious",
    }

    def apply_condition(self, character_id: str, condition_name: str,
                        duration: int = -1, source_id: Optional[str] = None) -> bool:
        """
        Apply a D&D 5e condition to a character (plan 1.5).

        Args:
            character_id: Character key in self.entities
            condition_name: Condition name, case-insensitive ("prone", "stunned",
                …). See _CONDITION_ALIASES for accepted spellings.
            duration: Duration in rounds; -1 means until removed.
            source_id: Character causing the condition (defaults to the target,
                which is correct for self-applied states like Dodging).

        Returns:
            True if the condition was applied.

        Was a stub that logged "(not yet implemented)". Roshar-specific
        conditions (Stormlight-infused, spren-bonded) are NOT in dnd_engine and
        remain unimplemented — this reports False for them rather than
        pretending, so callers can tell the difference.
        """
        entity = self.entities.get(character_id)
        if not entity:
            logger.error(f"Cannot apply condition: character {character_id} not found")
            return False

        key = (condition_name or "").strip().lower().replace(" ", "_")
        class_name = self._CONDITION_ALIASES.get(key)
        if class_name is None:
            logger.warning(
                f"⚠️ Condition '{condition_name}' is not implemented by dnd_engine "
                f"(available: {sorted(set(self._CONDITION_ALIASES.values()))})"
            )
            return False

        try:
            import dnd.conditions as conditions_module
            condition_class = getattr(conditions_module, class_name)

            source_entity = self.entities.get(source_id) if source_id else None
            source_uuid = source_entity.uuid if source_entity else entity.uuid

            # Do NOT pass an explicit Duration. The condition wires up its own
            # (setting owned_by_condition); handing in a pre-built Duration makes
            # condition.apply() return None and the condition is silently
            # dropped. Verified: Prone(source, target) applies; the same call
            # plus duration=Duration(...) does not.
            kwargs = {
                "source_entity_uuid": source_uuid,
                "target_entity_uuid": entity.uuid,
            }
            condition = condition_class(**kwargs)

            # Set the round count on the condition's OWN duration object.
            if duration is not None and duration > 0:
                try:
                    condition.duration.duration = duration
                except Exception:
                    logger.debug(f"   Could not set duration on {class_name}")

            # Apply via the condition itself, matching the working path in
            # combat_action_resolver._apply_condition(). Entity.add_condition()
            # is NOT usable here: it only stores the condition if
            # condition.apply() returns an event, but it builds its own
            # declaration_event first and that comes back None outside the
            # engine's event context -- so add_condition() returned None and
            # silently stored nothing.
            event = condition.apply()
            applied = event is not None and not getattr(event, "canceled", False)

            if applied:
                # Mirror what add_condition() would have recorded, so
                # get_conditions()/remove_condition() can see it.
                entity.active_conditions[condition.name] = condition
                entity.active_conditions_by_uuid[condition.uuid] = condition
                # active_conditions_by_source must be populated too, or
                # Entity.remove_condition() raises
                # "ValueError: list.remove(x): x not in list".
                entity.active_conditions_by_source[condition.source_entity_uuid].append(
                    condition.name
                )
                logger.info(
                    f"✨ Applied condition '{class_name}' to {character_id}"
                    + (f" for {duration} round(s)" if duration and duration > 0 else "")
                )
            else:
                logger.warning(
                    f"⚠️ Condition '{class_name}' on {character_id} was not applied: "
                    f"{getattr(event, 'status_message', 'no event returned')}"
                )
            return applied
        except Exception as e:
            logger.error(f"❌ Failed to apply condition '{condition_name}' to "
                         f"{character_id}: {e}")
            return False

    def remove_condition(self, character_id: str, condition_name: str) -> bool:
        """Remove a previously applied condition (plan 1.5)."""
        entity = self.entities.get(character_id)
        if not entity:
            logger.error(f"Cannot remove condition: character {character_id} not found")
            return False

        key = (condition_name or "").strip().lower().replace(" ", "_")
        class_name = self._CONDITION_ALIASES.get(key)
        if class_name is None:
            return False

        try:
            # Entity.remove_condition takes the condition NAME as registered.
            # It returns None on success, so report based on whether the
            # condition is actually gone rather than on the return value.
            if class_name not in getattr(entity, "active_conditions", {}):
                logger.debug(f"   {character_id} does not have '{class_name}'")
                return False

            entity.remove_condition(class_name)
            removed = class_name not in entity.active_conditions
            if removed:
                logger.info(f"✨ Removed condition '{class_name}' from {character_id}")
            else:
                logger.warning(f"⚠️ Condition '{class_name}' still present after removal")
            return removed
        except Exception as e:
            logger.error(f"❌ Failed to remove condition '{condition_name}': {e}")
            return False

    def get_conditions(self, character_id: str) -> List[str]:
        """Names of the conditions currently active on a character (plan 1.5)."""
        entity = self.entities.get(character_id)
        if not entity:
            return []
        active = getattr(entity, "active_conditions", None) or {}
        try:
            return sorted(str(name) for name in active.keys())
        except Exception:
            return []


# Factory function for easy integration
def create_dnd_engine_wrapper(game_engine, character_manager) -> DnDEngineWrapper:
    """Factory function to create configured wrapper"""
    return DnDEngineWrapper(
        game_engine=game_engine,
        character_manager=character_manager
    )
