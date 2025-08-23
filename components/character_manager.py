"""
Character Manager - Stage 3 Week 11-12
Character data management and skill calculations - From Original Plan
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

class AbilityScore(Enum):
    """D&D ability scores"""
    STRENGTH = "strength"
    DEXTERITY = "dexterity" 
    CONSTITUTION = "constitution"
    INTELLIGENCE = "intelligence"
    WISDOM = "wisdom"
    CHARISMA = "charisma"

@dataclass
class CharacterSkillData:
    """Complete skill data for a character"""
    skill_name: str
    ability_score: AbilityScore
    ability_modifier: int
    proficiency_bonus: int
    is_proficient: bool
    expertise: bool  # Double proficiency
    other_bonuses: Dict[str, int]
    total_modifier: int

@dataclass
class CharacterData:
    """Complete character information"""
    character_id: str
    name: str
    level: int
    proficiency_bonus: int
    ability_scores: Dict[str, int]
    ability_modifiers: Dict[str, int]
    skills: Dict[str, bool]  # Proficiency in skills
    expertise_skills: List[str]  # Skills with expertise
    conditions: List[str]
    features: List[str]  # Class features, racial traits, etc.

class CharacterManager:
    """
    Character data management and skill calculations - From Original Plan
    Manages character sheets and calculates skill modifiers
    """
    
    def __init__(self):
        self.characters: Dict[str, CharacterData] = {}
        
        # Standard D&D skill-to-ability mappings
        self.skill_abilities = {
            "acrobatics": AbilityScore.DEXTERITY,
            "animal_handling": AbilityScore.WISDOM,
            "arcana": AbilityScore.INTELLIGENCE,
            "athletics": AbilityScore.STRENGTH,
            "deception": AbilityScore.CHARISMA,
            "history": AbilityScore.INTELLIGENCE,
            "insight": AbilityScore.WISDOM,
            "intimidation": AbilityScore.CHARISMA,
            "investigation": AbilityScore.INTELLIGENCE,
            "medicine": AbilityScore.WISDOM,
            "nature": AbilityScore.INTELLIGENCE,
            "perception": AbilityScore.WISDOM,
            "performance": AbilityScore.CHARISMA,
            "persuasion": AbilityScore.CHARISMA,
            "religion": AbilityScore.INTELLIGENCE,
            "sleight_of_hand": AbilityScore.DEXTERITY,
            "stealth": AbilityScore.DEXTERITY,
            "survival": AbilityScore.WISDOM
        }
        
        print("👥 Character Manager initialized")
    
    def add_character(self, character_data: Dict[str, Any]) -> str:
        """Add or update a character"""
        char_id = character_data.get("character_id", character_data.get("name", "unknown"))
        
        # Calculate ability modifiers
        ability_scores = character_data.get("ability_scores", {})
        ability_modifiers = {}
        for ability, score in ability_scores.items():
            ability_modifiers[ability] = self._calculate_ability_modifier(score)
        
        # Calculate proficiency bonus from level
        level = character_data.get("level", 1)
        proficiency_bonus = self._calculate_proficiency_bonus(level)
        
        character = CharacterData(
            character_id=char_id,
            name=character_data.get("name", char_id),
            level=level,
            proficiency_bonus=proficiency_bonus,
            ability_scores=ability_scores,
            ability_modifiers=ability_modifiers,
            skills=character_data.get("skills", {}),
            expertise_skills=character_data.get("expertise_skills", []),
            conditions=character_data.get("conditions", []),
            features=character_data.get("features", [])
        )
        
        self.characters[char_id] = character
        print(f"👤 Added character: {character.name} (Level {level})")
        
        return char_id
    
    def get_skill_data(self, character_id: str, skill: str) -> Dict[str, Any]:
        """
        Get complete skill data for character - Step 2 of 7-step pipeline
        From Original Plan: "Character Manager → skill/ability mod, conditions"
        """
        if character_id not in self.characters:
            # Return default data for unknown characters
            return {
                "character_id": character_id,
                "skill": skill,
                "ability_modifier": 0,
                "proficiency_bonus": 0,
                "is_proficient": False,
                "expertise": False,
                "other_bonuses": {},
                "modifier": 0,
                "conditions": [],
                "error": f"Character {character_id} not found"
            }
        
        character = self.characters[character_id]
        
        # Get skill's associated ability
        ability = self.skill_abilities.get(skill.lower(), AbilityScore.INTELLIGENCE)
        ability_modifier = character.ability_modifiers.get(ability.value, 0)
        
        # Check proficiency
        is_proficient = character.skills.get(skill.lower(), False)
        expertise = skill.lower() in character.expertise_skills
        
        # Calculate skill modifier
        skill_modifier = ability_modifier
        
        if is_proficient:
            if expertise:
                skill_modifier += character.proficiency_bonus * 2  # Double proficiency
            else:
                skill_modifier += character.proficiency_bonus
        
        # Check for other bonuses (features, magic items, etc.)
        other_bonuses = {}
        
        # Example feature bonuses (would be expanded with actual D&D features)
        if "guidance" in character.features and skill in ["investigation", "perception"]:
            other_bonuses["guidance"] = 1  # Simplified guidance
        
        total_other_bonus = sum(other_bonuses.values())
        total_modifier = skill_modifier + total_other_bonus
        
        return {
            "character_id": character_id,
            "skill": skill,
            "ability": ability.value,
            "ability_modifier": ability_modifier,
            "proficiency_bonus": character.proficiency_bonus if is_proficient else 0,
            "is_proficient": is_proficient,
            "expertise": expertise,
            "other_bonuses": other_bonuses,
            "modifier": total_modifier,
            "conditions": character.conditions,
            "level": character.level,
            "breakdown": self._build_skill_breakdown(skill, ability_modifier, 
                                                   character.proficiency_bonus if is_proficient else 0,
                                                   expertise, other_bonuses)
        }
    
    def get_ability_modifier(self, character_id: str, ability: str) -> int:
        """Get ability modifier for character"""
        if character_id not in self.characters:
            return 0
        
        return self.characters[character_id].ability_modifiers.get(ability.lower(), 0)
    
    def get_saving_throw_modifier(self, character_id: str, save_type: str) -> Dict[str, Any]:
        """Get saving throw modifier"""
        if character_id not in self.characters:
            return {"modifier": 0, "proficient": False}
        
        character = self.characters[character_id]
        
        # Map save types to abilities
        save_abilities = {
            "strength": AbilityScore.STRENGTH,
            "dexterity": AbilityScore.DEXTERITY,
            "constitution": AbilityScore.CONSTITUTION,
            "intelligence": AbilityScore.INTELLIGENCE,
            "wisdom": AbilityScore.WISDOM,
            "charisma": AbilityScore.CHARISMA
        }
        
        ability = save_abilities.get(save_type.lower(), AbilityScore.CONSTITUTION)
        ability_modifier = character.ability_modifiers.get(ability.value, 0)
        
        # Check for save proficiency (would come from class features)
        save_proficiencies = getattr(character, 'save_proficiencies', [])
        is_proficient = save_type.lower() in save_proficiencies
        
        modifier = ability_modifier
        if is_proficient:
            modifier += character.proficiency_bonus
        
        return {
            "modifier": modifier,
            "ability_modifier": ability_modifier,
            "proficiency_bonus": character.proficiency_bonus if is_proficient else 0,
            "proficient": is_proficient,
            "breakdown": f"{ability_modifier} (ability) + {character.proficiency_bonus if is_proficient else 0} (prof) = {modifier}"
        }
    
    def update_character_condition(self, character_id: str, condition: str, add: bool = True):
        """Add or remove character condition"""
        if character_id not in self.characters:
            return False
        
        character = self.characters[character_id]
        
        if add and condition not in character.conditions:
            character.conditions.append(condition)
            print(f"➕ Added condition '{condition}' to {character.name}")
        elif not add and condition in character.conditions:
            character.conditions.remove(condition)
            print(f"➖ Removed condition '{condition}' from {character.name}")
        
        return True
    
    def get_passive_score(self, character_id: str, skill: str) -> Dict[str, Any]:
        """Calculate passive skill score (10 + modifiers)"""
        skill_data = self.get_skill_data(character_id, skill)
        
        passive_score = 10 + skill_data["modifier"]
        
        return {
            "passive_score": passive_score,
            "skill": skill,
            "modifier": skill_data["modifier"],
            "breakdown": f"10 + {skill_data['modifier']} = {passive_score}",
            "character_id": character_id
        }
    
    def _calculate_ability_modifier(self, ability_score: int) -> int:
        """Calculate D&D ability modifier from score"""
        return (ability_score - 10) // 2
    
    def _calculate_proficiency_bonus(self, level: int) -> int:
        """Calculate proficiency bonus from character level"""
        return 2 + ((level - 1) // 4)
    
    def _build_skill_breakdown(self, skill: str, ability_mod: int, 
                             prof_bonus: int, expertise: bool, 
                             other_bonuses: Dict[str, int]) -> str:
        """Build human-readable skill modifier breakdown"""
        parts = [f"{ability_mod} (ability)"]
        
        if prof_bonus > 0:
            if expertise:
                parts.append(f"{prof_bonus} (expertise)")
            else:
                parts.append(f"{prof_bonus} (proficiency)")
        
        for bonus_name, bonus_value in other_bonuses.items():
            if bonus_value != 0:
                parts.append(f"{bonus_value:+d} ({bonus_name})")
        
        total = ability_mod + prof_bonus + sum(other_bonuses.values())
        
        return " + ".join(parts) + f" = {total}"
    
    def get_character_summary(self, character_id: str) -> Dict[str, Any]:
        """Get complete character summary"""
        if character_id not in self.characters:
            return {"error": f"Character {character_id} not found"}
        
        character = self.characters[character_id]
        
        # Calculate some key passive scores
        passive_scores = {}
        key_skills = ["perception", "investigation", "insight"]
        for skill in key_skills:
            passive_data = self.get_passive_score(character_id, skill)
            passive_scores[skill] = passive_data["passive_score"]
        
        return {
            "character_id": character.character_id,
            "name": character.name,
            "level": character.level,
            "proficiency_bonus": character.proficiency_bonus,
            "ability_scores": character.ability_scores,
            "ability_modifiers": character.ability_modifiers,
            "passive_scores": passive_scores,
            "conditions": character.conditions,
            "skill_count": len([s for s, prof in character.skills.items() if prof]),
            "expertise_count": len(character.expertise_skills)
        }
    
    def list_characters(self) -> List[Dict[str, Any]]:
        """Get list of all managed characters"""
        return [
            {
                "character_id": char.character_id,
                "name": char.name,
                "level": char.level,
                "conditions": len(char.conditions)
            }
            for char in self.characters.values()
        ]


# Factory function for easy integration  
def create_character_manager() -> CharacterManager:
    """Factory function to create configured character manager"""
    return CharacterManager()


# Example usage for Stage 3 testing
if __name__ == "__main__":
    # Test character manager functionality
    manager = create_character_manager()
    
    # Add a sample character
    sample_character = {
        "character_id": "player1",
        "name": "Thorin Ironshield",
        "level": 3,
        "ability_scores": {
            "strength": 16,
            "dexterity": 12,
            "constitution": 14,
            "intelligence": 10,
            "wisdom": 13,
            "charisma": 8
        },
        "skills": {
            "athletics": True,
            "intimidation": True,
            "perception": True
        },
        "expertise_skills": ["athletics"],
        "conditions": [],
        "features": ["guidance"]
    }
    
    char_id = manager.add_character(sample_character)
    
    # Test skill data retrieval
    athletics_data = manager.get_skill_data(char_id, "athletics")
    print(f"Athletics skill data: {athletics_data}")
    
    # Test passive score
    passive_perception = manager.get_passive_score(char_id, "perception")
    print(f"Passive Perception: {passive_perception}")
    
    # Test character summary
    summary = manager.get_character_summary(char_id)
    print(f"Character summary: {summary}")