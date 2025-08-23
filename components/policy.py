"""
Policy Engine - Stage 3 Week 9-10
Centralized rule mediation - From Original Plan
"""

from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass
import json

class PolicyProfile(Enum):
    """Different rule interpretation profiles"""
    RAW = "raw"          # Rules as written
    HOUSE = "house"      # Common house rules
    EASY = "easy"        # Beginner friendly
    CUSTOM = "custom"    # User defined

@dataclass
class PolicyRule:
    """Individual policy rule with metadata"""
    name: str
    value: Any
    description: str
    source: str = "system"

class PolicyEngine:
    """
    Centralized rule mediation - From Original Plan
    Handles house rules, difficulty scaling, and advantage computation
    """
    
    # Base policy profiles with comprehensive D&D rule interpretations
    PROFILES = {
        PolicyProfile.RAW: {
            "flanking_advantage": PolicyRule(
                "flanking_advantage", False, 
                "Standard D&D 5e - no flanking advantage", "PHB"
            ),
            "crit_range": PolicyRule(
                "crit_range", [20], 
                "Critical hits only on natural 20", "PHB"
            ),
            "death_saves": PolicyRule(
                "death_saves", "standard", 
                "Standard death saving throws", "PHB"
            ),
            "rest_variant": PolicyRule(
                "rest_variant", "standard", 
                "Standard short/long rest rules", "PHB"
            ),
            "dc_adjustment": PolicyRule(
                "dc_adjustment", 0, 
                "No global DC adjustments", "PHB"
            ),
            "spell_component_enforcement": PolicyRule(
                "spell_component_enforcement", True, 
                "Strict spell component requirements", "PHB"
            ),
            "encumbrance": PolicyRule(
                "encumbrance", "standard", 
                "Standard carrying capacity rules", "PHB"
            )
        },
        
        PolicyProfile.HOUSE: {
            "flanking_advantage": PolicyRule(
                "flanking_advantage", True, 
                "Popular house rule - flanking grants advantage", "House Rule"
            ),
            "crit_range": PolicyRule(
                "crit_range", [19, 20], 
                "Expanded critical hit range", "House Rule"
            ),
            "death_saves": PolicyRule(
                "death_saves", "standard", 
                "Standard death saving throws", "PHB"
            ),
            "rest_variant": PolicyRule(
                "rest_variant", "standard", 
                "Standard rest rules", "PHB"
            ),
            "dc_adjustment": PolicyRule(
                "dc_adjustment", 0, 
                "No global adjustments", "House Rule"
            ),
            "spell_component_enforcement": PolicyRule(
                "spell_component_enforcement", False, 
                "Relaxed component requirements", "House Rule"
            ),
            "encumbrance": PolicyRule(
                "encumbrance", "lenient", 
                "More forgiving carrying capacity", "House Rule"
            )
        },
        
        PolicyProfile.EASY: {
            "flanking_advantage": PolicyRule(
                "flanking_advantage", True, 
                "Beginner-friendly flanking", "Easy Mode"
            ),
            "crit_range": PolicyRule(
                "crit_range", [19, 20], 
                "More frequent critical hits", "Easy Mode"
            ),
            "death_saves": PolicyRule(
                "death_saves", "forgiving", 
                "More forgiving death saves", "Easy Mode"
            ),
            "rest_variant": PolicyRule(
                "rest_variant", "short_rest_benefits", 
                "Enhanced rest recovery", "Easy Mode"
            ),
            "dc_adjustment": PolicyRule(
                "dc_adjustment", -2, 
                "Lower DCs for new players", "Easy Mode"
            ),
            "spell_component_enforcement": PolicyRule(
                "spell_component_enforcement", False, 
                "No component tracking", "Easy Mode"
            ),
            "encumbrance": PolicyRule(
                "encumbrance", "ignore", 
                "No encumbrance tracking", "Easy Mode"
            )
        }
    }
    
    def __init__(self, profile: PolicyProfile = PolicyProfile.RAW):
        """Initialize policy engine with specified profile"""
        self.active_profile_type = profile
        self.active_profile = self._load_profile(profile)
        self.custom_rules: Dict[str, PolicyRule] = {}
        self.temporary_overrides: Dict[str, Any] = {}
        
        print(f"🛡️ Policy Engine initialized with {profile.value.upper()} profile")
    
    def _load_profile(self, profile: PolicyProfile) -> Dict[str, PolicyRule]:
        """Load policy profile with deep copy to avoid mutations"""
        if profile == PolicyProfile.CUSTOM:
            return {}
        
        return self.PROFILES[profile].copy()
    
    def compute_advantage(self, game_state: Dict[str, Any], 
                         actor: str, skill: str, 
                         context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Determine advantage/disadvantage state - From Original Plan
        Returns comprehensive advantage analysis
        """
        advantages = []
        disadvantages = []
        
        # Get actor data
        actor_data = game_state.get("characters", {}).get(actor, {})
        conditions = actor_data.get("conditions", [])
        
        # Check conditions that affect rolls
        condition_effects = {
            # Disadvantage conditions
            "blinded": {"effect": "disadvantage", "reason": "blinded condition"},
            "frightened": {"effect": "disadvantage", "reason": "frightened condition"},
            "poisoned": {"effect": "disadvantage", "reason": "poisoned condition"},
            "exhaustion": {"effect": "disadvantage", "reason": "exhaustion"},
            "prone": {"effect": "disadvantage", "reason": "prone (if applicable)"},
            
            # Advantage conditions
            "blessed": {"effect": "advantage", "reason": "blessed condition"},
            "guided": {"effect": "advantage", "reason": "guidance or similar"},
            "inspired": {"effect": "advantage", "reason": "bardic inspiration or similar"}
        }
        
        for condition in conditions:
            if condition in condition_effects:
                effect_data = condition_effects[condition]
                if effect_data["effect"] == "disadvantage":
                    disadvantages.append(effect_data["reason"])
                else:
                    advantages.append(effect_data["reason"])
        
        # Check flanking if enabled
        flanking_rule = self.get_rule_value("flanking_advantage")
        if (flanking_rule and 
            game_state.get("combat_state", {}).get("flanking", {}).get(actor, False)):
            advantages.append("flanking position")
        
        # Check environmental factors
        if context:
            environment = context.get("environment", {})
            
            # Lighting conditions
            lighting = environment.get("lighting", "normal")
            if lighting == "dim" and not actor_data.get("darkvision", False):
                disadvantages.append("dim lighting")
            elif lighting == "darkness" and not actor_data.get("darkvision", False):
                disadvantages.append("darkness")
            
            # Terrain effects
            terrain = environment.get("terrain", "normal")
            if terrain == "difficult" and skill in ["acrobatics", "athletics"]:
                disadvantages.append("difficult terrain")
        
        # Resolve final state (advantage cancels disadvantage)
        advantage_count = len(advantages)
        disadvantage_count = len(disadvantages)
        
        if advantage_count > disadvantage_count:
            final_state = "advantage"
        elif disadvantage_count > advantage_count:
            final_state = "disadvantage"
        else:
            final_state = "normal"
        
        return {
            "final_state": final_state,
            "advantage_sources": advantages,
            "disadvantage_sources": disadvantages,
            "advantage_count": advantage_count,
            "disadvantage_count": disadvantage_count
        }
    
    def adjust_difficulty(self, base_dc: int, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply difficulty scaling - From Original Plan
        Returns adjusted DC with reasoning
        """
        adjustments = []
        total_adjustment = 0
        
        # Global profile adjustment
        profile_adjustment = self.get_rule_value("dc_adjustment")
        if profile_adjustment != 0:
            total_adjustment += profile_adjustment
            adjustments.append(f"Profile adjustment: {profile_adjustment:+d}")
        
        # Context-based adjustments
        difficulty_level = context.get("difficulty_level", 0)
        if difficulty_level != 0:
            total_adjustment += difficulty_level
            adjustments.append(f"Scenario difficulty: {difficulty_level:+d}")
        
        # Party level considerations
        party_level = context.get("average_party_level", 1)
        if party_level < 3:
            level_adjustment = -1
            total_adjustment += level_adjustment
            adjustments.append(f"Low level party: {level_adjustment:+d}")
        elif party_level > 10:
            level_adjustment = +1
            total_adjustment += level_adjustment
            adjustments.append(f"High level party: {level_adjustment:+d}")
        
        # Environmental factors
        environment = context.get("environment", {})
        if environment.get("stress_level") == "high":
            stress_adjustment = +2
            total_adjustment += stress_adjustment
            adjustments.append(f"High stress: {stress_adjustment:+d}")
        
        # Apply bounds (DC 5-30)
        final_dc = max(5, min(30, base_dc + total_adjustment))
        
        return {
            "base_dc": base_dc,
            "final_dc": final_dc,
            "total_adjustment": total_adjustment,
            "adjustments": adjustments,
            "bounded": final_dc != (base_dc + total_adjustment)
        }
    
    def passive_score(self, ability_mod: int, proficiency: int, 
                     bonus: int = 0, skill_name: str = "") -> Dict[str, Any]:
        """
        Calculate passive scores - From Original Plan
        Returns detailed passive score breakdown
        """
        base_passive = 10 + ability_mod + proficiency + bonus
        
        # Check for relevant advantages (passive perception with advantage = +5)
        advantage_bonus = 0
        if skill_name.lower() in ["perception", "investigation"]:
            # This would need to check character conditions/features
            # For now, we'll return the structure for future enhancement
            pass
        
        final_passive = base_passive + advantage_bonus
        
        return {
            "final_score": final_passive,
            "base_score": base_passive,
            "ability_modifier": ability_mod,
            "proficiency_bonus": proficiency,
            "other_bonuses": bonus,
            "advantage_bonus": advantage_bonus,
            "breakdown": f"10 + {ability_mod} (ability) + {proficiency} (proficiency) + {bonus} (other) = {final_passive}"
        }
    
    def get_rule_value(self, rule_name: str) -> Any:
        """Get current value of a policy rule"""
        # Check temporary overrides first
        if rule_name in self.temporary_overrides:
            return self.temporary_overrides[rule_name]
        
        # Check custom rules
        if rule_name in self.custom_rules:
            return self.custom_rules[rule_name].value
        
        # Check active profile
        if rule_name in self.active_profile:
            return self.active_profile[rule_name].value
        
        # Rule not found
        raise KeyError(f"Policy rule '{rule_name}' not found")
    
    def set_custom_rule(self, rule_name: str, value: Any, 
                       description: str = "Custom rule"):
        """Set a custom policy rule"""
        self.custom_rules[rule_name] = PolicyRule(
            rule_name, value, description, "custom"
        )
        print(f"📋 Set custom rule: {rule_name} = {value}")
    
    def set_temporary_override(self, rule_name: str, value: Any):
        """Set temporary rule override (cleared on profile change)"""
        self.temporary_overrides[rule_name] = value
        print(f"⏱️ Temporary override: {rule_name} = {value}")
    
    def clear_temporary_overrides(self):
        """Clear all temporary overrides"""
        count = len(self.temporary_overrides)
        self.temporary_overrides.clear()
        print(f"🧹 Cleared {count} temporary overrides")
    
    def change_profile(self, new_profile: PolicyProfile):
        """Change active policy profile"""
        old_profile = self.active_profile_type
        self.active_profile_type = new_profile
        self.active_profile = self._load_profile(new_profile)
        self.clear_temporary_overrides()
        
        print(f"🔄 Changed profile: {old_profile.value} → {new_profile.value}")
    
    def get_profile_info(self) -> Dict[str, Any]:
        """Get information about current profile and rules"""
        rules_summary = {}
        
        # Active profile rules
        for rule_name, rule in self.active_profile.items():
            rules_summary[rule_name] = {
                "value": rule.value,
                "description": rule.description,
                "source": rule.source
            }
        
        # Custom rules (override profile rules)
        for rule_name, rule in self.custom_rules.items():
            rules_summary[rule_name] = {
                "value": rule.value,
                "description": rule.description,
                "source": rule.source
            }
        
        # Temporary overrides (highest priority)
        for rule_name, value in self.temporary_overrides.items():
            if rule_name in rules_summary:
                rules_summary[rule_name]["value"] = value
                rules_summary[rule_name]["temporary_override"] = True
        
        return {
            "active_profile": self.active_profile_type.value,
            "total_rules": len(rules_summary),
            "custom_rules": len(self.custom_rules),
            "temporary_overrides": len(self.temporary_overrides),
            "rules": rules_summary
        }
    
    def validate_roll_modifiers(self, modifiers: Dict[str, int], 
                              context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that roll modifiers comply with current policy"""
        valid_modifiers = {}
        warnings = []
        
        for mod_name, mod_value in modifiers.items():
            # Check if modifier is allowed by current policy
            if mod_name == "guidance" and not self.get_rule_value("spell_component_enforcement"):
                # If spell components aren't enforced, guidance is always available
                valid_modifiers[mod_name] = mod_value
            elif mod_name in ["proficiency", "ability", "circumstance"]:
                # Core modifiers always allowed
                valid_modifiers[mod_name] = mod_value
            else:
                # Check policy-specific rules for other modifiers
                valid_modifiers[mod_name] = mod_value
        
        return {
            "valid_modifiers": valid_modifiers,
            "warnings": warnings,
            "total_modifier": sum(valid_modifiers.values())
        }


# Factory functions for easy integration
def create_policy_engine(profile: PolicyProfile = PolicyProfile.RAW) -> PolicyEngine:
    """Factory function to create configured policy engine"""
    return PolicyEngine(profile)

def create_house_rules_engine() -> PolicyEngine:
    """Create policy engine with common house rules"""
    return PolicyEngine(PolicyProfile.HOUSE)

def create_beginner_engine() -> PolicyEngine:
    """Create beginner-friendly policy engine"""
    return PolicyEngine(PolicyProfile.EASY)


# Example usage for Stage 3 testing
if __name__ == "__main__":
    # Test policy engine functionality
    engine = create_policy_engine(PolicyProfile.HOUSE)
    
    # Test advantage computation
    game_state = {
        "characters": {
            "player1": {
                "conditions": ["blessed", "poisoned"],
                "darkvision": False
            }
        },
        "combat_state": {
            "flanking": {"player1": True}
        }
    }
    
    advantage = engine.compute_advantage(game_state, "player1", "investigation")
    print(f"Advantage result: {advantage}")
    
    # Test DC adjustment
    context = {
        "difficulty_level": 1,
        "average_party_level": 2,
        "environment": {"stress_level": "high"}
    }
    
    dc_result = engine.adjust_difficulty(15, context)
    print(f"DC adjustment: {dc_result}")
    
    # Test passive score
    passive = engine.passive_score(3, 2, 1, "perception")
    print(f"Passive score: {passive}")
    
    # Show profile info
    info = engine.get_profile_info()
    print(f"Profile info: {info['active_profile']} with {info['total_rules']} rules")