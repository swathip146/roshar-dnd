"""
Enhanced Dice Roller - Stage 3 Week 11-12
Comprehensive dice system with logging and advantage handling - From Original Plan
"""

import random
import time
import uuid
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class AdvantageState(Enum):
    NORMAL = "normal"
    ADVANTAGE = "advantage"
    DISADVANTAGE = "disadvantage"

@dataclass
class DiceRoll:
    """Individual dice roll result with metadata"""
    die_type: int
    result: int
    timestamp: float
    roll_id: str

@dataclass
class SkillRollResult:
    """Complete skill roll result with breakdown"""
    raw_rolls: List[DiceRoll]
    selected_roll: DiceRoll
    modifiers: Dict[str, int]
    total: int
    advantage_state: AdvantageState
    correlation_id: str
    skill_name: str

class DiceRoller:
    """
    Enhanced dice system with logging and advantage - From Original Plan
    Handles all dice mechanics with complete audit trail
    """
    
    def __init__(self):
        self.roll_history: List[SkillRollResult] = []
        self.raw_roll_log: List[DiceRoll] = []
        
        # Random seed for reproducibility in testing
        self.rng = random.Random()
        
        print("🎲 Enhanced Dice Roller initialized")
    
    def roll_die(self, die_type: int, correlation_id: str = "") -> DiceRoll:
        """Roll a single die with logging"""
        result = self.rng.randint(1, die_type)
        roll_id = str(uuid.uuid4())
        
        dice_roll = DiceRoll(
            die_type=die_type,
            result=result,
            timestamp=time.time(),
            roll_id=roll_id
        )
        
        self.raw_roll_log.append(dice_roll)
        return dice_roll
    
    def roll_multiple(self, die_type: int, count: int, correlation_id: str = "") -> List[DiceRoll]:
        """Roll multiple dice of the same type"""
        return [self.roll_die(die_type, correlation_id) for _ in range(count)]
    
    def skill_roll(self, skill: str, modifier: int, 
                  advantage_state: Dict[str, Any], 
                  correlation_id: str = "") -> Dict[str, Any]:
        """
        Complete skill roll with advantage/disadvantage - From Original Plan
        Returns detailed roll breakdown for decision logging
        """
        # Determine number of d20s to roll
        adv_state = advantage_state.get("final_state", "normal")
        
        if adv_state == "advantage":
            num_rolls = 2
            select_highest = True
        elif adv_state == "disadvantage":
            num_rolls = 2
            select_highest = False
        else:
            num_rolls = 1
            select_highest = True
        
        # Roll the d20(s)
        raw_rolls = self.roll_multiple(20, num_rolls, correlation_id)
        
        # Select the appropriate roll
        if num_rolls == 1:
            selected_roll = raw_rolls[0]
        elif select_highest:
            selected_roll = max(raw_rolls, key=lambda r: r.result)
        else:
            selected_roll = min(raw_rolls, key=lambda r: r.result)
        
        # Build modifiers breakdown
        modifiers = {
            "base_modifier": modifier,
            "total": modifier
        }
        
        # Calculate total
        total = selected_roll.result + modifiers["total"]
        
        # Create skill roll result
        skill_result = SkillRollResult(
            raw_rolls=raw_rolls,
            selected_roll=selected_roll,
            modifiers=modifiers,
            total=total,
            advantage_state=AdvantageState(adv_state),
            correlation_id=correlation_id,
            skill_name=skill
        )
        
        # Store in history
        self.roll_history.append(skill_result)
        
        # Return format expected by GameEngine
        return {
            "raw_rolls": [r.result for r in raw_rolls],
            "selected_roll": selected_roll.result,
            "total": total,
            "modifiers": modifiers,
            "advantage_state": adv_state,
            "roll_breakdown": f"1d20{'+' if modifier >= 0 else ''}{modifier} = {selected_roll.result}{'+' if modifier >= 0 else ''}{modifier} = {total}",
            "correlation_id": correlation_id
        }
    
    def ability_check(self, ability_mod: int, proficiency: int = 0, 
                     advantage_state: str = "normal", 
                     correlation_id: str = "") -> Dict[str, Any]:
        """General ability check (no specific skill)"""
        total_modifier = ability_mod + proficiency
        
        advantage_data = {"final_state": advantage_state}
        return self.skill_roll("ability_check", total_modifier, advantage_data, correlation_id)
    
    def saving_throw(self, save_type: str, ability_mod: int, 
                    proficiency: int = 0, advantage_state: str = "normal",
                    correlation_id: str = "") -> Dict[str, Any]:
        """Saving throw roll"""
        total_modifier = ability_mod + proficiency
        
        advantage_data = {"final_state": advantage_state}
        result = self.skill_roll(f"{save_type}_save", total_modifier, advantage_data, correlation_id)
        
        # Add save-specific metadata
        result["save_type"] = save_type
        result["is_saving_throw"] = True
        
        return result
    
    def attack_roll(self, attack_bonus: int, advantage_state: str = "normal",
                   correlation_id: str = "") -> Dict[str, Any]:
        """Attack roll (for future combat system)"""
        advantage_data = {"final_state": advantage_state}
        result = self.skill_roll("attack", attack_bonus, advantage_data, correlation_id)
        
        # Check for critical hit/miss
        selected_roll = result["selected_roll"]
        result["is_critical_hit"] = selected_roll == 20
        result["is_critical_miss"] = selected_roll == 1
        result["is_attack_roll"] = True
        
        return result
    
    def damage_roll(self, damage_dice: str, modifier: int = 0,
                   correlation_id: str = "") -> Dict[str, Any]:
        """
        Damage roll parsing and execution
        damage_dice format: "2d6", "1d8+2", etc.
        """
        # Simple damage dice parser
        total_damage = 0
        rolls = []
        
        # Basic parsing (supports formats like "2d6", "1d8+3")
        if "d" in damage_dice:
            parts = damage_dice.replace("+", " +").replace("-", " -").split()
            
            for part in parts:
                if "d" in part:
                    # Parse dice (e.g., "2d6")
                    count_str, die_str = part.split("d")
                    count = int(count_str) if count_str else 1
                    die_type = int(die_str)
                    
                    dice_rolls = self.roll_multiple(die_type, count, correlation_id)
                    rolls.extend(dice_rolls)
                    total_damage += sum(r.result for r in dice_rolls)
                    
                elif part.startswith(("+", "-")) or part.isdigit():
                    # Static modifier
                    total_damage += int(part)
        
        # Add explicit modifier
        total_damage += modifier
        
        return {
            "total_damage": total_damage,
            "damage_rolls": [r.result for r in rolls],
            "base_damage": damage_dice,
            "modifier": modifier,
            "breakdown": f"{damage_dice} + {modifier} = {total_damage}",
            "correlation_id": correlation_id
        }
    
    def percentile_roll(self, correlation_id: str = "") -> Dict[str, Any]:
        """Percentile (d100) roll"""
        tens = self.roll_die(10, correlation_id)
        ones = self.roll_die(10, correlation_id)
        
        # Handle 00 as 100
        result = (tens.result % 10) * 10 + (ones.result % 10)
        if result == 0:
            result = 100
        
        return {
            "result": result,
            "tens_die": tens.result,
            "ones_die": ones.result,
            "breakdown": f"d100: {tens.result}{ones.result} = {result}",
            "correlation_id": correlation_id
        }
    
    def get_roll_statistics(self, correlation_id: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics about rolls, optionally filtered by correlation ID"""
        relevant_rolls = self.roll_history
        
        if correlation_id:
            relevant_rolls = [r for r in self.roll_history if r.correlation_id == correlation_id]
        
        if not relevant_rolls:
            return {"message": "No rolls found"}
        
        # Calculate statistics
        d20_rolls = []
        for roll_result in relevant_rolls:
            d20_rolls.extend([r.result for r in roll_result.raw_rolls if r.die_type == 20])
        
        if d20_rolls:
            stats = {
                "total_skill_rolls": len(relevant_rolls),
                "total_d20_rolls": len(d20_rolls),
                "average_d20": sum(d20_rolls) / len(d20_rolls),
                "min_d20": min(d20_rolls),
                "max_d20": max(d20_rolls),
                "natural_20s": d20_rolls.count(20),
                "natural_1s": d20_rolls.count(1),
                "advantage_rolls": len([r for r in relevant_rolls if r.advantage_state == AdvantageState.ADVANTAGE]),
                "disadvantage_rolls": len([r for r in relevant_rolls if r.advantage_state == AdvantageState.DISADVANTAGE])
            }
            
            # Add distribution
            distribution = {}
            for result in d20_rolls:
                distribution[result] = distribution.get(result, 0) + 1
            stats["d20_distribution"] = distribution
            
            return stats
        
        return {"message": "No d20 rolls found"}
    
    def clear_history(self, older_than: Optional[float] = None):
        """Clear roll history, optionally keeping recent rolls"""
        if older_than is None:
            self.roll_history.clear()
            self.raw_roll_log.clear()
            print("🧹 Cleared all roll history")
        else:
            cutoff_time = time.time() - older_than
            
            old_count = len(self.roll_history)
            self.roll_history = [r for r in self.roll_history if r.raw_rolls[0].timestamp > cutoff_time]
            self.raw_roll_log = [r for r in self.raw_roll_log if r.timestamp > cutoff_time]
            
            cleared_count = old_count - len(self.roll_history)
            print(f"🧹 Cleared {cleared_count} old roll records")


# Factory function for easy integration
def create_dice_roller() -> DiceRoller:
    """Factory function to create configured dice roller"""
    return DiceRoller()


# Example usage for Stage 3 testing
if __name__ == "__main__":
    # Test enhanced dice roller functionality
    roller = create_dice_roller()
    
    # Test skill roll with advantage
    advantage_state = {"final_state": "advantage"}
    result = roller.skill_roll("investigation", 5, advantage_state, "test-correlation-1")
    print(f"Skill roll result: {result}")
    
    # Test attack roll
    attack_result = roller.attack_roll(7, "normal", "test-correlation-2")
    print(f"Attack roll: {attack_result}")
    
    # Test damage roll
    damage_result = roller.damage_roll("2d6+3", 0, "test-correlation-3")
    print(f"Damage roll: {damage_result}")
    
    # Show statistics
    stats = roller.get_roll_statistics()
    print(f"Roll statistics: {stats}")