"""
Rules Enforcer - Stage 3 Week 11-12
Authoritative D&D rule interpretation - From Original Plan
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class CheckType(Enum):
    """Types of checks that can be required"""
    SKILL = "skill"
    ABILITY = "ability" 
    SAVING_THROW = "saving_throw"
    ATTACK = "attack"
    NONE = "none"

class DifficultyClass(Enum):
    """Standard D&D difficulty classes"""
    VERY_EASY = 5
    EASY = 10
    MEDIUM = 15
    HARD = 20
    VERY_HARD = 25
    NEARLY_IMPOSSIBLE = 30

@dataclass
class CheckRequirement:
    """Result of determining if a check is needed"""
    check_needed: bool
    check_type: CheckType
    dc: int
    dc_source: str
    skill_or_ability: str
    reason: str
    auto_success: bool = False
    auto_failure: bool = False

class RulesEnforcer:
    """
    Authoritative D&D rule interpretation - From Original Plan
    Determines when checks are needed and what the DC should be
    """
    
    def __init__(self):
        # Standard D&D skill-to-ability mappings
        self.skill_abilities = {
            "acrobatics": "dexterity",
            "animal_handling": "wisdom",
            "arcana": "intelligence",
            "athletics": "strength",
            "deception": "charisma",
            "history": "intelligence",
            "insight": "wisdom",
            "intimidation": "charisma",
            "investigation": "intelligence",
            "medicine": "wisdom",
            "nature": "intelligence",
            "perception": "wisdom",
            "performance": "charisma",
            "persuasion": "charisma",
            "religion": "intelligence",
            "sleight_of_hand": "dexterity",
            "stealth": "dexterity",
            "survival": "wisdom"
        }
        
        # Context-based DC guidelines
        self.context_dcs = {
            # Social interactions
            "persuade_friendly_npc": DifficultyClass.EASY.value,
            "persuade_neutral_npc": DifficultyClass.MEDIUM.value, 
            "persuade_hostile_npc": DifficultyClass.HARD.value,
            "intimidate_weak_enemy": DifficultyClass.EASY.value,
            "intimidate_equal_enemy": DifficultyClass.MEDIUM.value,
            "intimidate_strong_enemy": DifficultyClass.HARD.value,
            
            # Investigation and exploration
            "search_obvious_clues": DifficultyClass.EASY.value,
            "search_hidden_clues": DifficultyClass.MEDIUM.value,
            "search_secret_clues": DifficultyClass.HARD.value,
            "recall_common_knowledge": DifficultyClass.EASY.value,
            "recall_specialized_knowledge": DifficultyClass.MEDIUM.value,
            "recall_obscure_knowledge": DifficultyClass.HARD.value,
            
            # Physical challenges  
            "climb_rough_surface": DifficultyClass.EASY.value,
            "climb_typical_wall": DifficultyClass.MEDIUM.value,
            "climb_smooth_wall": DifficultyClass.HARD.value,
            "jump_long_distance": DifficultyClass.MEDIUM.value,
            "balance_narrow_ledge": DifficultyClass.MEDIUM.value,
            
            # Stealth and infiltration
            "hide_with_cover": DifficultyClass.EASY.value,
            "hide_without_cover": DifficultyClass.HARD.value,
            "sneak_past_guard": DifficultyClass.MEDIUM.value,
            "pick_simple_lock": DifficultyClass.MEDIUM.value,
            "pick_complex_lock": DifficultyClass.HARD.value,
        }
        
        print("⚖️ Rules Enforcer initialized")
    
    def determine_check_needed(self, check_request: Dict[str, Any]) -> CheckRequirement:
        """
        Step 1 of 7-step pipeline - Determine if check is needed and derive DC
        From Original Plan: "do we need a check? derive DC"
        """
        action = check_request.get("action", "")
        context = check_request.get("context", {})
        actor = check_request.get("actor", "")
        skill = check_request.get("skill", "")
        
        # Check for auto-success/failure conditions first
        auto_result = self._check_automatic_outcomes(check_request)
        if auto_result:
            return auto_result
        
        # Determine if a check is actually needed
        check_type, reason = self._determine_check_type(check_request)
        
        if check_type == CheckType.NONE:
            return CheckRequirement(
                check_needed=False,
                check_type=check_type,
                dc=0,
                dc_source="no_check_required",
                skill_or_ability="",
                reason=reason
            )
        
        # Determine DC and source
        dc, dc_source = self._derive_dc(check_request, check_type)
        
        return CheckRequirement(
            check_needed=True,
            check_type=check_type,
            dc=dc,
            dc_source=dc_source,
            skill_or_ability=skill,
            reason=f"Check required: {reason}"
        )
    
    def _check_automatic_outcomes(self, check_request: Dict[str, Any]) -> Optional[CheckRequirement]:
        """Check for conditions that result in automatic success/failure"""
        action = check_request.get("action", "")
        context = check_request.get("context", {})
        
        # Automatic failures
        if context.get("impossible", False):
            return CheckRequirement(
                check_needed=False,
                check_type=CheckType.NONE,
                dc=0,
                dc_source="impossible_task",
                skill_or_ability="",
                reason="Task is impossible",
                auto_failure=True
            )
        
        # Automatic successes
        if context.get("trivial", False):
            return CheckRequirement(
                check_needed=False,
                check_type=CheckType.NONE,
                dc=0,
                dc_source="trivial_task", 
                skill_or_ability="",
                reason="Task is trivial",
                auto_success=True
            )
        
        # Check for "take 10" or "take 20" conditions
        if context.get("unlimited_time", False) and not context.get("time_pressure", False):
            # In non-stressful situations with unlimited time, some tasks auto-succeed
            skill = check_request.get("skill", "")
            if skill in ["search", "investigation"] and not context.get("hidden", False):
                return CheckRequirement(
                    check_needed=False,
                    check_type=CheckType.NONE,
                    dc=0,
                    dc_source="take_20",
                    skill_or_ability=skill,
                    reason="Unlimited time allows thorough search",
                    auto_success=True
                )
        
        return None
    
    def _determine_check_type(self, check_request: Dict[str, Any]) -> Tuple[CheckType, str]:
        """Determine what type of check is needed"""
        action = check_request.get("action", "")
        skill = check_request.get("skill", "")
        check_type_hint = check_request.get("type", "")
        
        # Explicit type override
        if check_type_hint == "saving_throw":
            return CheckType.SAVING_THROW, "Saving throw requested"
        elif check_type_hint == "attack":
            return CheckType.ATTACK, "Attack roll requested"
        
        # Skill-based determination
        if skill and skill in self.skill_abilities:
            return CheckType.SKILL, f"Skill check: {skill}"
        
        # Action-based determination
        action_patterns = {
            "persuade": CheckType.SKILL,
            "intimidate": CheckType.SKILL, 
            "search": CheckType.SKILL,
            "climb": CheckType.SKILL,
            "jump": CheckType.SKILL,
            "hide": CheckType.SKILL,
            "sneak": CheckType.SKILL,
            "recall": CheckType.SKILL,
            "investigate": CheckType.SKILL,
            "attack": CheckType.ATTACK,
            "save": CheckType.SAVING_THROW
        }
        
        for pattern, check_type in action_patterns.items():
            if pattern in action.lower():
                return check_type, f"Action requires {check_type.value}: {action}"
        
        # Default to ability check if unclear
        if skill:
            return CheckType.ABILITY, f"General ability check: {skill}"
        
        return CheckType.NONE, "No check determined necessary"
    
    def _derive_dc(self, check_request: Dict[str, Any], check_type: CheckType) -> Tuple[int, str]:
        """Derive appropriate DC based on context and action"""
        action = check_request.get("action", "")
        context = check_request.get("context", {})
        
        # Check for explicit DC first
        if "dc" in context:
            return context["dc"], "explicit_dc"
        
        # Check for context-based DC
        context_key = self._build_context_key(check_request)
        if context_key in self.context_dcs:
            return self.context_dcs[context_key], f"context_{context_key}"
        
        # Difficulty-based DC derivation
        difficulty = context.get("difficulty", "medium")
        difficulty_mapping = {
            "trivial": DifficultyClass.VERY_EASY.value,
            "very_easy": DifficultyClass.VERY_EASY.value,
            "easy": DifficultyClass.EASY.value,
            "medium": DifficultyClass.MEDIUM.value,
            "hard": DifficultyClass.HARD.value,
            "very_hard": DifficultyClass.VERY_HARD.value,
            "nearly_impossible": DifficultyClass.NEARLY_IMPOSSIBLE.value
        }
        
        if difficulty in difficulty_mapping:
            return difficulty_mapping[difficulty], f"difficulty_{difficulty}"
        
        # Default DC based on check type
        default_dcs = {
            CheckType.SKILL: DifficultyClass.MEDIUM.value,
            CheckType.ABILITY: DifficultyClass.MEDIUM.value,
            CheckType.SAVING_THROW: DifficultyClass.MEDIUM.value,
            CheckType.ATTACK: 0  # AC determined elsewhere
        }
        
        return default_dcs.get(check_type, DifficultyClass.MEDIUM.value), "default_dc"
    
    def _build_context_key(self, check_request: Dict[str, Any]) -> str:
        """Build context key for DC lookup"""
        action = check_request.get("action", "").lower()
        context = check_request.get("context", {})
        
        # Try to match action patterns to context keys
        if "persuade" in action:
            npc_attitude = context.get("npc_attitude", "neutral")
            return f"persuade_{npc_attitude}_npc"
        elif "intimidate" in action:
            enemy_strength = context.get("enemy_strength", "equal")
            return f"intimidate_{enemy_strength}_enemy"
        elif "search" in action or "investigate" in action:
            clue_difficulty = context.get("clue_difficulty", "hidden") 
            return f"search_{clue_difficulty}_clues"
        elif "climb" in action:
            surface_type = context.get("surface_type", "typical")
            return f"climb_{surface_type}_surface"
        elif "hide" in action:
            cover_available = "with_cover" if context.get("cover", False) else "without_cover"
            return f"hide_{cover_available}"
        
        return ""
    
    def validate_check_request(self, check_request: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that check request has required components"""
        required_fields = ["action", "actor"]
        optional_fields = ["skill", "context", "type"]
        
        errors = []
        warnings = []
        
        # Check required fields
        for field in required_fields:
            if field not in check_request:
                errors.append(f"Missing required field: {field}")
        
        # Validate skill if provided
        skill = check_request.get("skill")
        if skill and skill not in self.skill_abilities:
            warnings.append(f"Unknown skill: {skill}")
        
        # Validate context structure
        context = check_request.get("context", {})
        if not isinstance(context, dict):
            errors.append("Context must be a dictionary")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def get_skill_ability(self, skill: str) -> str:
        """Get the ability score associated with a skill"""
        return self.skill_abilities.get(skill.lower(), "intelligence")
    
    def get_passive_dc(self, skill: str, context: Dict[str, Any]) -> int:
        """Get DC for passive skill checks (perception, insight, etc.)"""
        base_dc = self._derive_dc(
            {"action": f"passive_{skill}", "context": context, "skill": skill},
            CheckType.SKILL
        )[0]
        
        # Passive checks are typically easier
        return max(5, base_dc - 5)
    
    def contest_dc(self, opposing_actor: str, opposing_skill: str, 
                  opposing_modifier: int) -> Dict[str, Any]:
        """Calculate DC for contested checks (opposed rolls)"""
        # For contested checks, DC is typically 8 + ability modifier + proficiency
        # This is a simplified version - full implementation would need opposing actor's stats
        contested_dc = 8 + opposing_modifier
        
        return {
            "dc": contested_dc,
            "dc_source": f"contested_vs_{opposing_actor}_{opposing_skill}",
            "is_contested": True,
            "opposing_actor": opposing_actor,
            "opposing_skill": opposing_skill
        }


# Factory function for easy integration
def create_rules_enforcer() -> RulesEnforcer:
    """Factory function to create configured rules enforcer"""
    return RulesEnforcer()


# Example usage for Stage 3 testing
if __name__ == "__main__":
    # Test rules enforcer functionality
    enforcer = create_rules_enforcer()
    
    # Test check determination
    check_request = {
        "action": "persuade the guard to let us pass",
        "actor": "player1", 
        "skill": "persuasion",
        "context": {
            "npc_attitude": "neutral",
            "difficulty": "medium"
        }
    }
    
    result = enforcer.determine_check_needed(check_request)
    print(f"Check determination: {result}")
    
    # Test validation
    validation = enforcer.validate_check_request(check_request)
    print(f"Validation result: {validation}")
    
    # Test automatic outcomes
    trivial_request = {
        "action": "recall basic information about dragons",
        "actor": "player1",
        "skill": "arcana",
        "context": {"trivial": True}
    }
    
    trivial_result = enforcer.determine_check_needed(trivial_request)
    print(f"Trivial check result: {trivial_result}")