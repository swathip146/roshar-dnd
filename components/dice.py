"""
Enhanced Dice Roller - Stage 3 Week 11-12
Comprehensive dice system with logging and advantage handling - From Original Plan
"""

import random
import re
import time
import uuid
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from config.logging_config import get_logger

# Initialize logger
logger = get_logger(__name__)


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
        Parse and roll a damage expression.

        Supports: "2d6", "1d8+3", "1d8-1", "1d6 + 2" (spaces), "4d6kh3"
        (keep highest), "4d6kl1" (keep lowest), bare constants ("5"), and
        damage-type annotations ("2d6[fire]"). Multiple terms may be chained:
        "1d8+1d6+3".

        Plan 0.11 — the previous implementation was substantively broken:
          * "4d6kh3" raised ValueError: invalid literal for int(): '6kh3'
          * "1d6 + 2" (with spaces) raised ValueError: invalid literal: '+'
          * the reported audit trail lied: "1d8-1" on a roll of 3 returned the
            correct 2 but reported modifier=0 and printed "1d8-1 + 0 = 2"
        Silent wrong numbers are the worst failure mode for an adjudicator, so
        this now reports exactly what it rolled.

        (The plan recommended swapping in avrae/d20, which handles all of this
        plus exploding/reroll. That install is currently blocked by the sandbox
        proxy — files.pythonhosted.org is not allowlisted — so the parser is
        fixed in place. The returned contract is unchanged, so switching to d20
        later remains a drop-in.)
        """
        expr = (damage_dice or "").strip()
        # Strip damage-type annotations, e.g. "2d6[fire]" -> "2d6"
        expr_clean = re.sub(r"\[[^\]]*\]", "", expr)
        # Drop all whitespace so "1d6 + 2" parses like "1d6+2"
        expr_clean = re.sub(r"\s+", "", expr_clean)

        dice_total = 0
        static_total = 0
        rolls: List[int] = []
        kept_detail: List[str] = []

        # Split into signed terms: 1d8, +1d6, -1, +3 ...
        terms = re.findall(r"[+-]?[^+-]+", expr_clean) if expr_clean else []

        for term in terms:
            if not term:
                continue
            sign = -1 if term.startswith("-") else 1
            body = term.lstrip("+-")
            if not body:
                continue

            # NdM with optional keep-highest/keep-lowest: 4d6kh3, 2d20kl1
            m = re.fullmatch(r"(\d*)d(\d+)(?:(kh|kl)(\d+))?", body, re.IGNORECASE)
            if m:
                count = int(m.group(1)) if m.group(1) else 1
                die_type = int(m.group(2))
                keep_mode = (m.group(3) or "").lower()
                keep_n = int(m.group(4)) if m.group(4) else None

                if count <= 0 or die_type <= 0:
                    logger.warning(f"🎲 Ignoring invalid dice term '{term}' in '{expr}'")
                    continue

                dice_rolls = self.roll_multiple(die_type, count, correlation_id)
                values = [r.result for r in dice_rolls]
                rolls.extend(values)

                if keep_mode and keep_n:
                    ordered = sorted(values, reverse=(keep_mode == "kh"))
                    kept = ordered[:keep_n]
                    kept_detail.append(f"{body}={kept} of {values}")
                else:
                    kept = values

                dice_total += sign * sum(kept)
                continue

            # Bare constant
            if body.isdigit():
                static_total += sign * int(body)
                continue

            logger.warning(f"🎲 Ignoring unparseable term '{term}' in '{expr}'")

        # `modifier` is an ADDITIONAL caller-supplied bonus, distinct from any
        # constant embedded in the expression.
        total_damage = dice_total + static_total + modifier
        total_damage = max(0, total_damage)  # damage never heals

        parts = [f"{expr}"]
        if kept_detail:
            parts.append(f"({'; '.join(kept_detail)})")
        parts.append(f"rolls={rolls}")
        if static_total:
            parts.append(f"static={static_total:+d}")
        if modifier:
            parts.append(f"modifier={modifier:+d}")
        breakdown = " ".join(parts) + f" = {total_damage}"

        return {
            "total_damage": total_damage,
            "damage_rolls": rolls,
            "base_damage": damage_dice,
            "dice_subtotal": dice_total,
            "static_modifier": static_total,
            "modifier": modifier,
            "breakdown": breakdown,
            "correlation_id": correlation_id,
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
            logger.info(f"🧹 Cleared {cleared_count} old roll records")


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
    logger.info(f"Skill roll result: {result}")
    
    # Test attack roll
    attack_result = roller.attack_roll(7, "normal", "test-correlation-2")
    logger.info(f"Attack roll: {attack_result}")
    
    # Test damage roll
    damage_result = roller.damage_roll("2d6+3", 0, "test-correlation-3")
    logger.info(f"Damage roll: {damage_result}")
    
    # Show statistics
    stats = roller.get_roll_statistics()
    logger.info(f"Roll statistics: {stats}")