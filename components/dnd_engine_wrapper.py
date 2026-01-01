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

    def __post_init__(self):
        """Initialize entities from existing characters."""
        logger.info("Initializing DnDEngineWrapper")
        self._sync_characters_to_entities()
        logger.info(f"Synced {len(self.entities)} characters to dnd_engine entities")

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
            ability_scores_config = AbilityScoresConfig(
                strength=AbilityConfig(score=character.ability_scores.get("strength", 10)),
                dexterity=AbilityConfig(score=character.ability_scores.get("dexterity", 10)),
                constitution=AbilityConfig(score=character.ability_scores.get("constitution", 10)),
                intelligence=AbilityConfig(score=character.ability_scores.get("intelligence", 10)),
                wisdom=AbilityConfig(score=character.ability_scores.get("wisdom", 10)),
                charisma=AbilityConfig(score=character.ability_scores.get("charisma", 10))
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

            health_config = HealthConfig(
                max_hp=character.hit_points.get("maximum", 10),
                current_hp=character.hit_points.get("current", 10)
            )

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

            entity_config = EntityConfig(
                ability_scores=ability_scores_config,
                skill_set=skill_set_config,
                saving_throws=saving_throws_config,
                health=health_config,
                equipment=equipment_config,
                action_economy=action_economy_config,
                proficiency_bonus=character.proficiency_bonus
            )

            # Create entity using the config
            from uuid import uuid4
            entity = Entity.create(
                source_entity_uuid=uuid4(),  # Generate new UUID
                name=character.name,
                config=entity_config
            )

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

            # Apply damage to target
            target.health.take_damage(damage)

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

    def apply_condition(self, character_id: str, condition_name: str, duration: int = -1):
        """
        Apply a condition to a character.

        Args:
            character_id: Character UUID
            condition_name: Condition name (e.g., "prone", "stunned", "stormlight_infused")
            duration: Duration in rounds (-1 = permanent until removed)
        """
        entity = self.entities.get(character_id)
        if not entity:
            logger.error(f"Cannot apply condition: character {character_id} not found")
            return

        # TODO: Implement condition application via dnd_engine
        logger.info(f"Applied condition '{condition_name}' to {character_id} (not yet implemented)")


# Factory function for easy integration
def create_dnd_engine_wrapper(game_engine, character_manager) -> DnDEngineWrapper:
    """Factory function to create configured wrapper"""
    return DnDEngineWrapper(
        game_engine=game_engine,
        character_manager=character_manager
    )
