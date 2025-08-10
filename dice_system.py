"""
Dice System for DM Assistant
Comprehensive dice rolling system supporting all D&D dice types and complex expressions
"""
import random
import re
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum

from agent_framework import BaseAgent, MessageType, AgentMessage


class DiceType(Enum):
    """Standard D&D dice types"""
    D4 = 4
    D6 = 6
    D8 = 8
    D10 = 10
    D12 = 12
    D20 = 20
    D100 = 100


class AdvantageType(Enum):
    """Advantage/disadvantage types for d20 rolls"""
    NORMAL = "normal"
    ADVANTAGE = "advantage"
    DISADVANTAGE = "disadvantage"


@dataclass
class DiceRoll:
    """Represents a single dice roll with full details"""
    expression: str
    rolls: List[int] = field(default_factory=list)
    total: int = 0
    modifier: int = 0
    dice_count: int = 0
    dice_sides: int = 0
    advantage_type: AdvantageType = AdvantageType.NORMAL
    dropped_rolls: List[int] = field(default_factory=list)
    kept_rolls: List[int] = field(default_factory=list)
    critical_hit: bool = False
    critical_fail: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        """String representation of the dice roll"""
        if self.advantage_type != AdvantageType.NORMAL:
            return f"{self.expression} → {self.kept_rolls} ({self.advantage_type.value}) = {self.total}"
        elif self.dropped_rolls:
            return f"{self.expression} → {self.rolls} (kept: {self.kept_rolls}) = {self.total}"
        else:
            return f"{self.expression} → {self.rolls} = {self.total}"


class DiceParser:
    """Parses dice expressions into rollable components"""
    
    # Regex patterns for different dice expressions
    DICE_PATTERN = re.compile(r'(\d*)d(\d+)([kKhHlL]\d+)?([+-]\d+)?', re.IGNORECASE)
    MODIFIER_PATTERN = re.compile(r'([+-]\d+)')
    ADVANTAGE_PATTERN = re.compile(r'\b(adv|advantage|dis|disadvantage)\b', re.IGNORECASE)
    
    @classmethod
    def parse_expression(cls, expression: str) -> Dict[str, Any]:
        """Parse a dice expression into components"""
        expression = expression.strip().replace(' ', '')
        
        # Check for advantage/disadvantage
        advantage_type = AdvantageType.NORMAL
        adv_match = cls.ADVANTAGE_PATTERN.search(expression)
        if adv_match:
            adv_text = adv_match.group(1).lower()
            if adv_text in ['adv', 'advantage']:
                advantage_type = AdvantageType.ADVANTAGE
            elif adv_text in ['dis', 'disadvantage']:
                advantage_type = AdvantageType.DISADVANTAGE
            # Remove advantage/disadvantage from expression
            expression = cls.ADVANTAGE_PATTERN.sub('', expression)
        
        # Parse dice components
        dice_matches = cls.DICE_PATTERN.findall(expression)
        if not dice_matches:
            # Try to parse as just a number (modifier)
            try:
                modifier = int(expression)
                return {
                    'dice_count': 0,
                    'dice_sides': 0,
                    'modifier': modifier,
                    'keep_type': None,
                    'keep_count': 0,
                    'advantage_type': advantage_type,
                    'expression': expression
                }
            except ValueError:
                raise ValueError(f"Invalid dice expression: {expression}")
        
        # For now, handle single dice expression (most common case)
        count_str, sides_str, keep_str, mod_str = dice_matches[0]
        
        dice_count = int(count_str) if count_str else 1
        dice_sides = int(sides_str)
        modifier = int(mod_str) if mod_str else 0
        
        # Parse keep/drop modifiers
        keep_type = None
        keep_count = 0
        if keep_str:
            keep_type = keep_str[0].lower()
            keep_count = int(keep_str[1:])
        
        return {
            'dice_count': dice_count,
            'dice_sides': dice_sides,
            'modifier': modifier,
            'keep_type': keep_type,
            'keep_count': keep_count,
            'advantage_type': advantage_type,
            'expression': expression
        }


class DiceRoller:
    """Core dice rolling engine"""
    
    def __init__(self, seed: Optional[int] = None):
        """Initialize dice roller with optional seed for reproducibility"""
        if seed is not None:
            random.seed(seed)
        self.roll_history: List[DiceRoll] = []
    
    def roll(self, expression: str, context: Optional[str] = None) -> DiceRoll:
        """Roll dice based on expression"""
        try:
            parsed = DiceParser.parse_expression(expression)
            result = self._execute_roll(parsed, context)
            self.roll_history.append(result)
            return result
        except Exception as e:
            # Create error roll result
            error_roll = DiceRoll(
                expression=expression,
                total=0,
                metadata={'error': str(e), 'context': context}
            )
            self.roll_history.append(error_roll)
            return error_roll
    
    def _execute_roll(self, parsed: Dict[str, Any], context: Optional[str] = None) -> DiceRoll:
        """Execute the actual dice roll"""
        dice_count = parsed['dice_count']
        dice_sides = parsed['dice_sides']
        modifier = parsed['modifier']
        keep_type = parsed['keep_type']
        keep_count = parsed['keep_count']
        advantage_type = parsed['advantage_type']
        expression = parsed['expression']
        
        # Handle pure modifier (no dice)
        if dice_count == 0:
            return DiceRoll(
                expression=expression,
                total=modifier,
                modifier=modifier,
                metadata={'context': context}
            )
        
        # Roll the dice
        if advantage_type != AdvantageType.NORMAL and dice_sides == 20:
            # Roll twice for advantage/disadvantage on d20
            rolls = [random.randint(1, dice_sides) for _ in range(2)]
            if advantage_type == AdvantageType.ADVANTAGE:
                kept_roll = max(rolls)
                dropped_roll = min(rolls)
            else:  # disadvantage
                kept_roll = min(rolls)
                dropped_roll = max(rolls)
            
            total = kept_roll + modifier
            
            # Check for critical hit/fail on d20
            critical_hit = kept_roll == 20
            critical_fail = kept_roll == 1
            
            return DiceRoll(
                expression=expression,
                rolls=rolls,
                total=total,
                modifier=modifier,
                dice_count=2,
                dice_sides=dice_sides,
                advantage_type=advantage_type,
                dropped_rolls=[dropped_roll],
                kept_rolls=[kept_roll],
                critical_hit=critical_hit,
                critical_fail=critical_fail,
                metadata={'context': context}
            )
        else:
            # Normal dice rolling
            rolls = [random.randint(1, dice_sides) for _ in range(dice_count)]
            
            # Handle keep/drop modifiers
            kept_rolls = rolls[:]
            dropped_rolls = []
            
            if keep_type and keep_count > 0:
                if keep_type in ['k', 'h']:  # keep highest
                    sorted_rolls = sorted(rolls, reverse=True)
                    kept_rolls = sorted_rolls[:keep_count]
                    dropped_rolls = sorted_rolls[keep_count:]
                elif keep_type == 'l':  # keep lowest
                    sorted_rolls = sorted(rolls)
                    kept_rolls = sorted_rolls[:keep_count]
                    dropped_rolls = sorted_rolls[keep_count:]
            
            dice_total = sum(kept_rolls)
            total = dice_total + modifier
            
            # Check for critical hit/fail on single d20
            critical_hit = dice_sides == 20 and dice_count == 1 and rolls[0] == 20
            critical_fail = dice_sides == 20 and dice_count == 1 and rolls[0] == 1
            
            return DiceRoll(
                expression=expression,
                rolls=rolls,
                total=total,
                modifier=modifier,
                dice_count=dice_count,
                dice_sides=dice_sides,
                advantage_type=advantage_type,
                dropped_rolls=dropped_rolls,
                kept_rolls=kept_rolls,
                critical_hit=critical_hit,
                critical_fail=critical_fail,
                metadata={'context': context}
            )
    
    def roll_ability_score(self, method: str = "4d6_drop_lowest") -> int:
        """Roll ability scores using various methods"""
        if method == "4d6_drop_lowest":
            roll = self.roll("4d6l3")
            return roll.total
        elif method == "3d6":
            roll = self.roll("3d6")
            return roll.total
        elif method == "point_buy":
            return 8  # Base score for point buy
        else:
            roll = self.roll("3d6")  # Default
            return roll.total
    
    def roll_hit_points(self, hit_die: int, level: int, con_modifier: int) -> int:
        """Roll hit points for a character"""
        if level == 1:
            # Max HP at level 1
            return hit_die + con_modifier
        else:
            # Roll for additional levels
            hp = hit_die + con_modifier  # Level 1 max
            for _ in range(level - 1):
                roll = self.roll(f"1d{hit_die}")
                hp += roll.total + con_modifier
            return max(1, hp)  # Minimum 1 HP
    
    def get_roll_history(self, limit: int = 10) -> List[DiceRoll]:
        """Get recent roll history"""
        return self.roll_history[-limit:] if self.roll_history else []
    
    def clear_history(self):
        """Clear roll history"""
        self.roll_history.clear()


class DiceSystemAgent(BaseAgent):
    """Dice System Agent that provides dice rolling services to other agents"""
    
    def __init__(self, seed: Optional[int] = None):
        super().__init__("dice_system", "DiceSystem")
        self.dice_roller = DiceRoller(seed)
    
    def _setup_handlers(self):
        """Setup message handlers for dice system"""
        self.register_handler("roll_dice", self._handle_roll_dice)
        self.register_handler("roll_ability_score", self._handle_roll_ability_score)
        self.register_handler("roll_hit_points", self._handle_roll_hit_points)
        self.register_handler("roll_attack", self._handle_roll_attack)
        self.register_handler("roll_damage", self._handle_roll_damage)
        self.register_handler("roll_saving_throw", self._handle_roll_saving_throw)
        self.register_handler("roll_skill_check", self._handle_roll_skill_check)
        self.register_handler("get_roll_history", self._handle_get_roll_history)
        self.register_handler("clear_roll_history", self._handle_clear_roll_history)
    
    def _handle_roll_dice(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle general dice roll request"""
        expression = message.data.get("expression")
        context = message.data.get("context", "")
        
        if not expression:
            return {"success": False, "error": "No dice expression provided"}
        
        try:
            result = self.dice_roller.roll(expression, context)
            return {
                "success": True,
                "result": {
                    "expression": result.expression,
                    "rolls": result.rolls,
                    "total": result.total,
                    "modifier": result.modifier,
                    "critical_hit": result.critical_hit,
                    "critical_fail": result.critical_fail,
                    "advantage_type": result.advantage_type.value,
                    "description": str(result)
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_roll_ability_score(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle ability score roll request"""
        method = message.data.get("method", "4d6_drop_lowest")
        
        try:
            score = self.dice_roller.roll_ability_score(method)
            return {"success": True, "score": score, "method": method}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_roll_hit_points(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle hit points roll request"""
        hit_die = message.data.get("hit_die", 8)
        level = message.data.get("level", 1)
        con_modifier = message.data.get("con_modifier", 0)
        
        try:
            hp = self.dice_roller.roll_hit_points(hit_die, level, con_modifier)
            return {"success": True, "hit_points": hp, "hit_die": hit_die, "level": level}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_roll_attack(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle attack roll request"""
        attack_bonus = message.data.get("attack_bonus", 0)
        advantage = message.data.get("advantage", False)
        disadvantage = message.data.get("disadvantage", False)
        context = message.data.get("context", "Attack Roll")
        
        try:
            # Determine advantage type
            if advantage and not disadvantage:
                expression = f"1d20+{attack_bonus} advantage"
            elif disadvantage and not advantage:
                expression = f"1d20+{attack_bonus} disadvantage"
            else:
                expression = f"1d20+{attack_bonus}"
            
            result = self.dice_roller.roll(expression, context)
            
            return {
                "success": True,
                "result": {
                    "total": result.total,
                    "roll": result.kept_rolls[0] if result.kept_rolls else result.rolls[0],
                    "modifier": attack_bonus,
                    "critical_hit": result.critical_hit,
                    "critical_fail": result.critical_fail,
                    "advantage_type": result.advantage_type.value,
                    "description": str(result)
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_roll_damage(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle damage roll request"""
        damage_dice = message.data.get("damage_dice", "1d6")
        damage_bonus = message.data.get("damage_bonus", 0)
        critical = message.data.get("critical", False)
        context = message.data.get("context", "Damage Roll")
        
        try:
            if critical:
                # Double the dice for critical hits
                parsed = DiceParser.parse_expression(damage_dice)
                crit_expression = f"{parsed['dice_count'] * 2}d{parsed['dice_sides']}+{damage_bonus}"
                context += " (Critical Hit)"
            else:
                crit_expression = f"{damage_dice}+{damage_bonus}" if damage_bonus else damage_dice
            
            result = self.dice_roller.roll(crit_expression, context)
            
            return {
                "success": True,
                "result": {
                    "total": result.total,
                    "rolls": result.rolls,
                    "modifier": damage_bonus,
                    "critical": critical,
                    "description": str(result)
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_roll_saving_throw(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle saving throw request"""
        save_bonus = message.data.get("save_bonus", 0)
        advantage = message.data.get("advantage", False)
        disadvantage = message.data.get("disadvantage", False)
        dc = message.data.get("dc", 10)
        save_type = message.data.get("save_type", "Saving Throw")
        
        try:
            if advantage and not disadvantage:
                expression = f"1d20+{save_bonus} advantage"
            elif disadvantage and not advantage:
                expression = f"1d20+{save_bonus} disadvantage"
            else:
                expression = f"1d20+{save_bonus}"
            
            result = self.dice_roller.roll(expression, f"{save_type} (DC {dc})")
            success = result.total >= dc
            
            return {
                "success": True,
                "result": {
                    "total": result.total,
                    "roll": result.kept_rolls[0] if result.kept_rolls else result.rolls[0],
                    "modifier": save_bonus,
                    "dc": dc,
                    "success": success,
                    "critical_success": result.total == 20,
                    "critical_failure": result.total == 1,
                    "advantage_type": result.advantage_type.value,
                    "description": str(result) + f" vs DC {dc} ({'Success' if success else 'Failure'})"
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_roll_skill_check(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle skill check request"""
        skill_bonus = message.data.get("skill_bonus", 0)
        advantage = message.data.get("advantage", False)
        disadvantage = message.data.get("disadvantage", False)
        dc = message.data.get("dc", 10)
        skill_name = message.data.get("skill_name", "Skill Check")
        
        try:
            if advantage and not disadvantage:
                expression = f"1d20+{skill_bonus} advantage"
            elif disadvantage and not advantage:
                expression = f"1d20+{skill_bonus} disadvantage"
            else:
                expression = f"1d20+{skill_bonus}"
            
            result = self.dice_roller.roll(expression, f"{skill_name} (DC {dc})")
            success = result.total >= dc
            
            return {
                "success": True,
                "result": {
                    "total": result.total,
                    "roll": result.kept_rolls[0] if result.kept_rolls else result.rolls[0],
                    "modifier": skill_bonus,
                    "dc": dc,
                    "success": success,
                    "critical_success": result.total == 20,
                    "critical_failure": result.total == 1,
                    "advantage_type": result.advantage_type.value,
                    "description": str(result) + f" vs DC {dc} ({'Success' if success else 'Failure'})"
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_get_roll_history(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle roll history request"""
        limit = message.data.get("limit", 10)
        
        try:
            history = self.dice_roller.get_roll_history(limit)
            return {
                "success": True,
                "history": [
                    {
                        "expression": roll.expression,
                        "total": roll.total,
                        "rolls": roll.rolls,
                        "critical_hit": roll.critical_hit,
                        "critical_fail": roll.critical_fail,
                        "description": str(roll),
                        "context": roll.metadata.get("context", "")
                    }
                    for roll in history
                ]
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_clear_roll_history(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle clear roll history request"""
        try:
            self.dice_roller.clear_history()
            return {"success": True, "message": "Roll history cleared"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def process_tick(self):
        """Process dice system tick - no regular processing needed"""
        pass


# Utility functions for quick dice rolling
def quick_roll(expression: str, context: Optional[str] = None) -> DiceRoll:
    """Quick dice roll function for standalone use"""
    roller = DiceRoller()
    return roller.roll(expression, context)


def roll_stats() -> Dict[str, int]:
    """Roll a complete set of ability scores"""
    roller = DiceRoller()
    return {
        "strength": roller.roll_ability_score(),
        "dexterity": roller.roll_ability_score(), 
        "constitution": roller.roll_ability_score(),
        "intelligence": roller.roll_ability_score(),
        "wisdom": roller.roll_ability_score(),
        "charisma": roller.roll_ability_score()
    }


if __name__ == "__main__":
    # Test the dice system
    roller = DiceRoller()
    
    print("=== Dice System Test ===")
    
    # Test basic rolls
    print("\n--- Basic Rolls ---")
    print(roller.roll("1d20"))
    print(roller.roll("3d6"))
    print(roller.roll("2d8+3"))
    
    # Test advantage/disadvantage
    print("\n--- Advantage/Disadvantage ---")
    print(roller.roll("1d20+5 advantage"))
    print(roller.roll("1d20+2 disadvantage"))
    
    # Test keep/drop mechanics
    print("\n--- Keep/Drop Mechanics ---")
    print(roller.roll("4d6k3"))  # Keep highest 3
    print(roller.roll("4d6l3"))  # Keep lowest 3
    
    # Test ability scores
    print("\n--- Ability Scores ---")
    stats = roll_stats()
    for ability, score in stats.items():
        print(f"{ability.capitalize()}: {score}")
    
    # Test hit points
    print("\n--- Hit Points ---")
    print(f"Fighter Level 1: {roller.roll_hit_points(10, 1, 2)} HP")
    print(f"Wizard Level 3: {roller.roll_hit_points(6, 3, 1)} HP")
    
    print("\n--- Roll History ---")
    for roll in roller.get_roll_history(5):
        print(f"  {roll}")