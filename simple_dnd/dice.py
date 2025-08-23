#!/usr/bin/env python3
"""
Simple dice rolling for basic checks - Week 2 Implementation
"""
import random
import time
from typing import Dict, List, Any, Optional
from .config import GameConfig, DEFAULT_CONFIG

class SimpleDice:
    """Basic dice rolling for simple checks"""
    
    def __init__(self, config: Optional[GameConfig] = None):
        """Initialize the dice system"""
        self.config = config or DEFAULT_CONFIG
        self.roll_history = []
    
    def roll_d20(self) -> int:
        """Simple d20 roll"""
        roll = random.randint(1, 20)
        self._record_roll("d20", roll)
        return roll
    
    def roll_dice(self, sides: int, count: int = 1) -> List[int]:
        """Roll multiple dice"""
        rolls = []
        for _ in range(count):
            roll = random.randint(1, sides)
            rolls.append(roll)
            self._record_roll(f"d{sides}", roll)
        return rolls
    
    def skill_check(self, difficulty: Optional[int] = None, modifier: int = 0) -> Dict[str, Any]:
        """Basic skill check"""
        if difficulty is None:
            difficulty = self.config.default_difficulty
        
        roll = self.roll_d20()
        total = roll + modifier
        success = total >= difficulty
        
        result = {
            "roll": roll,
            "modifier": modifier,
            "total": total,
            "difficulty": difficulty,
            "success": success,
            "message": f"Rolled {roll} + {modifier} = {total} vs DC {difficulty}: {'Success!' if success else 'Failed!'}",
            "timestamp": time.time()
        }
        
        self.roll_history.append({
            "type": "skill_check",
            **result
        })
        
        return result
    
    def attack_roll(self, target_ac: int, modifier: int = 0) -> Dict[str, Any]:
        """Basic attack roll"""
        roll = self.roll_d20()
        total = roll + modifier
        hit = total >= target_ac
        critical = roll == 20
        fumble = roll == 1
        
        result = {
            "roll": roll,
            "modifier": modifier,
            "total": total,
            "target_ac": target_ac,
            "hit": hit,
            "critical": critical,
            "fumble": fumble,
            "message": self._format_attack_message(roll, total, target_ac, hit, critical, fumble),
            "timestamp": time.time()
        }
        
        self.roll_history.append({
            "type": "attack_roll",
            **result
        })
        
        return result
    
    def damage_roll(self, dice_expression: str = "1d6") -> Dict[str, Any]:
        """Basic damage roll from dice expression like '1d6', '2d8+3'"""
        try:
            # Parse simple dice expressions
            total_damage = 0
            rolls = []
            
            # Handle expressions like "1d6+2" or "2d8"
            parts = dice_expression.lower().replace(" ", "").replace("-", "+-").split("+")
            
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                    
                if "d" in part:
                    # Dice roll like "2d6"
                    count_str, sides_str = part.split("d")
                    count = int(count_str) if count_str else 1
                    sides = int(sides_str)
                    
                    dice_rolls = self.roll_dice(sides, count)
                    rolls.extend(dice_rolls)
                    total_damage += sum(dice_rolls)
                else:
                    # Static modifier
                    modifier = int(part)
                    total_damage += modifier
            
            result = {
                "expression": dice_expression,
                "rolls": rolls,
                "total": total_damage,
                "message": f"Damage: {dice_expression} = {total_damage}",
                "timestamp": time.time()
            }
            
            self.roll_history.append({
                "type": "damage_roll",
                **result
            })
            
            return result
            
        except Exception as e:
            # Fallback to simple 1d6
            roll = self.roll_d20()  # Using d20 as fallback
            return {
                "expression": "1d6 (fallback)",
                "rolls": [roll],
                "total": max(1, roll // 4),  # Scale d20 to roughly d6 range
                "message": f"Damage: 1d6 (fallback) = {max(1, roll // 4)}",
                "error": str(e),
                "timestamp": time.time()
            }
    
    def _record_roll(self, die_type: str, result: int):
        """Record individual die roll"""
        # Keep last 100 rolls to avoid memory bloat
        if len(self.roll_history) > 100:
            self.roll_history = self.roll_history[-50:]
    
    def _format_attack_message(self, roll: int, total: int, target_ac: int, 
                             hit: bool, critical: bool, fumble: bool) -> str:
        """Format attack roll message"""
        if critical:
            return f"🎯 CRITICAL HIT! Rolled {roll} (total {total}) vs AC {target_ac}"
        elif fumble:
            return f"💥 FUMBLE! Rolled {roll} (total {total}) vs AC {target_ac}"
        elif hit:
            return f"⚔️ HIT! Rolled {roll} (total {total}) vs AC {target_ac}"
        else:
            return f"❌ MISS! Rolled {roll} (total {total}) vs AC {target_ac}"
    
    def get_roll_statistics(self) -> Dict[str, Any]:
        """Get rolling statistics"""
        if not self.roll_history:
            return {"total_rolls": 0}
        
        total_rolls = len(self.roll_history)
        roll_types = {}
        
        for roll_entry in self.roll_history:
            roll_type = roll_entry.get("type", "unknown")
            roll_types[roll_type] = roll_types.get(roll_type, 0) + 1
        
        return {
            "total_rolls": total_rolls,
            "roll_types": roll_types,
            "recent_rolls": self.roll_history[-5:]  # Last 5 rolls
        }