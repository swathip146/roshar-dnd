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

import d20

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
        Parse and roll a damage expression, using avrae/d20 as the grammar.

        Supports everything d20's formal grammar does, which is a superset of what
        the previous hand-rolled parser managed:

          * "2d6", "1d8+3", "1d8-1", "1d6 + 2" (spaces), bare constants ("5")
          * keep/drop:      "4d6kh3", "2d20kl1", "4d6ph1" (drop highest)
          * EXPLODING:      "4d6e6"      -- was a silent 0, then a ValueError
          * REROLL:         "4d6ro1", "4d6rr1"
          * min/max:        "4d6mi2", "4d6ma5"
          * parentheses and multiplication: "(1d6+2)*2"
          * damage-type annotations: "2d6[fire]"
          * chained terms:  "1d8+1d6+3"

        Plan 0.11 — history of this method, because the shape of the old bugs is
        the reason the contract below is asserted so tightly:

          * "4d6kh3" raised ValueError: invalid literal for int(): '6kh3'
          * "1d6 + 2" (with spaces) raised ValueError: invalid literal: '+'
          * "1d8-1" on a roll of 3 returned the correct 2 but reported
            modifier=0 and printed "1d8-1 + 0 = 2" -- right answer, lying
            audit trail
          * "4d6e6"/"1d20r1" silently returned 0 damage with rolls=[] and no
            error, so a spell written with exploding dice dealt NOTHING and
            nothing reported it. That was later made a loud ValueError; now the
            notation simply WORKS.

        `d20` was listed in requirements.txt but never imported -- the entire
        point of plan 0.11. It is now actually used. It is also the reason the
        unsupported-notation ValueError is gone for e/r notation: d20 handles it.
        Genuinely malformed input ("garbage", "", "4d6!") still raises
        ValueError, because a silent zero remains the worst possible answer for
        an adjudicator.

        The returned dict shape is UNCHANGED from the hand-rolled version --
        `total_damage`, `damage_rolls`, `base_damage`, `dice_subtotal`,
        `static_modifier`, `modifier`, `breakdown`, `correlation_id` -- because
        `agents/dm_tools.roll_dice` and `combat/maneuver_executor._roll_total`
        read those keys by name.
        """
        expr = (damage_dice or "").strip()
        if not expr:
            # An EMPTY expression is not zero damage. `dm_tools.roll_dice`
            # forwards whatever the LLM wrote, so "" means the model OMITTED the
            # dice, not that the attack was harmless.
            raise ValueError(
                f"Empty or zero dice expression {damage_dice!r} — no dice to roll. "
                f"A damage roll must specify dice (e.g. '1d8+3').")

        try:
            result = d20.roll(expr)
        except d20.RollError as exc:
            # d20 refuses malformed input loudly; keep raising ValueError so the
            # existing callers' `except Exception -> {"error": ...}` and the
            # existing tests' `pytest.raises(ValueError)` still hold.
            raise ValueError(
                f"Unparseable dice expression {damage_dice!r} ({exc}). "
                f"Supported: NdM, kh/kl/ph/pl, exploding (e), reroll (ro/rr), "
                f"mi/ma, parentheses, +/- constants and [damage-type] "
                f"annotations — see plan 0.11.") from exc

        # Walk the AST to separate dice faces from static constants. `Dice.values`
        # holds one `Die` per rolled die; `Die.values` holds one Literal per FACE,
        # which is what makes exploding (extra faces) and dropped dice (kept=False
        # but still a real face) both reportable. A dropped die's `.total` is 0,
        # so the faces must come from `Die.values`, not `Die.total`.
        faces: List[int] = []
        dice_nodes: List[Any] = []
        static_total = 0

        def _collect(node: Any, sign: int = 1) -> None:
            nonlocal static_total
            if isinstance(node, d20.Dice):
                # Every dice group is a `Dice` node, even bare "d6" (measured),
                # so there is no standalone-`Die` case to handle here.
                dice_nodes.append(node)
                for die in node.values:
                    # `Literal.number` (values[-1]), NOT `.total`. A DROPPED
                    # literal — a die removed by kh/kl/p or replaced by a reroll —
                    # reports `.total == 0` while keeping its real face in
                    # `.values`. Measured: "4d6ro1" logged rolls=[5, 0, 4, 4, 4],
                    # a face of 0 on a d6, which is physically impossible and
                    # would have skewed the statistics log. `.number` also
                    # correctly reflects mi/ma clamping.
                    faces.extend(int(v.number) for v in die.values)
                return
            if isinstance(node, d20.Literal):
                static_total += sign * int(node.total)
                return
            if isinstance(node, d20.BinOp):
                left, right = node.children
                _collect(left, sign)
                # Only +/- keep the "static modifier" idea meaningful; for * / etc
                # the constant is not an additive modifier, so it is not counted
                # as one. `dice_subtotal + static_modifier == total_damage` is
                # asserted by tests, so mixed-operator expressions are handled by
                # deriving the subtotal from the real total instead (below).
                _collect(right, sign * (-1 if node.op == "-" else 1))
                return
            for child in getattr(node, "children", []) or []:
                _collect(child, sign)

        _collect(result.expr)

        # `0d6`/`0` are not "zero damage" either — same reasoning as the empty
        # expression above. d20 happily evaluates "0d6" to 0 with no faces, so the
        # refusal has to be explicit.
        if not faces and not static_total:
            raise ValueError(
                f"Empty or zero dice expression {damage_dice!r} — no dice to roll. "
                f"A damage roll must specify dice (e.g. '1d8+3').")

        # `total_damage` is d20's real arithmetic — never re-derived, so operator
        # precedence and parentheses stay correct.
        raw_total = int(result.total)

        # dice_subtotal is defined as "the total minus the additive constants", so
        # the invariant dice_subtotal + static_modifier == pre-clamp total holds
        # for every expression d20 can evaluate, including "(1d6+2)*2".
        dice_subtotal = raw_total - static_total

        # Preserve the audit trail: d20 rolls via the module-level `random`, so it
        # honours random.seed() but does NOT populate raw_roll_log. Record the
        # faces we extracted so get_roll_statistics()/clear_history() still see
        # every die this roller was responsible for.
        for face in faces:
            self.raw_roll_log.append(DiceRoll(
                die_type=self._die_size_for(face, dice_nodes),
                result=face,
                timestamp=time.time(),
                roll_id=str(uuid.uuid4()),
            ))

        # `modifier` is an ADDITIONAL caller-supplied bonus, distinct from any
        # constant embedded in the expression.
        total_damage = max(0, raw_total + modifier)  # damage never heals

        parts = [expr, f"rolls={faces}"]
        if static_total:
            parts.append(f"static={static_total:+d}")
        if modifier:
            parts.append(f"modifier={modifier:+d}")
        parts.append(f"[{result}]")
        breakdown = " ".join(parts) + f" = {total_damage}"

        return {
            "total_damage": total_damage,
            "damage_rolls": faces,
            "base_damage": damage_dice,
            "dice_subtotal": dice_subtotal,
            "static_modifier": static_total,
            "modifier": modifier,
            "breakdown": breakdown,
            "correlation_id": correlation_id,
        }

    @staticmethod
    def _die_size_for(face: int, dice_nodes: List[Any]) -> int:
        """
        Best-effort die size for the statistics log.

        `get_roll_statistics` filters `raw_roll_log` on `die_type == 20`, so a d20
        rolled through an expression must be recorded as a d20. When an expression
        mixes sizes the first node whose size can contain the face is used; this
        only affects statistics, never a damage total.
        """
        for node in dice_nodes:
            size = getattr(node, "size", None)
            if isinstance(size, int) and 1 <= face <= size:
                return size
        return 20 if face <= 20 else 100
    
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