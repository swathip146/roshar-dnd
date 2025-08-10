"""
Combat Engine for DM Assistant
Handles turn-based D&D combat with initiative, actions, conditions, and rule enforcement
"""
import time
import uuid
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum

from agent_framework import BaseAgent, MessageType, AgentMessage
from dice_system import DiceRoller, quick_roll


class CombatState(Enum):
    """States of combat"""
    INACTIVE = "inactive"
    INITIATIVE = "initiative"
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"


class ActionType(Enum):
    """Types of actions in combat"""
    ACTION = "action"
    BONUS_ACTION = "bonus_action"
    REACTION = "reaction"
    MOVEMENT = "movement"
    FREE_ACTION = "free_action"


class DamageType(Enum):
    """Types of damage in D&D"""
    ACID = "acid"
    BLUDGEONING = "bludgeoning"
    COLD = "cold"
    FIRE = "fire"
    FORCE = "force"
    LIGHTNING = "lightning"
    NECROTIC = "necrotic"
    PIERCING = "piercing"
    POISON = "poison"
    PSYCHIC = "psychic"
    RADIANT = "radiant"
    SLASHING = "slashing"
    THUNDER = "thunder"


@dataclass
class Condition:
    """Represents a condition/status effect"""
    name: str
    description: str
    duration: int = -1  # -1 = permanent, 0 = expires this turn, >0 = turns remaining
    source: str = ""
    effects: Dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """Check if condition has expired"""
        return self.duration == 0


@dataclass
class Combatant:
    """Represents a combatant in combat"""
    id: str
    name: str
    max_hp: int
    current_hp: int
    armor_class: int
    initiative: int = 0
    initiative_bonus: int = 0
    
    # Action economy
    has_action: bool = True
    has_bonus_action: bool = True
    has_reaction: bool = True
    movement_remaining: int = 30
    max_movement: int = 30
    
    # Combat stats
    attack_bonus: int = 0
    damage_dice: str = "1d6"
    damage_bonus: int = 0
    
    # Status tracking
    conditions: List[Condition] = field(default_factory=list)
    is_player: bool = False
    is_unconscious: bool = False
    is_dead: bool = False
    death_saves_successes: int = 0
    death_saves_failures: int = 0
    
    # Additional data
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_alive(self) -> bool:
        """Check if combatant is alive"""
        return not self.is_dead and self.current_hp > 0
    
    def take_damage(self, damage: int, damage_type: str = "untyped") -> Dict[str, Any]:
        """Apply damage to combatant"""
        # TODO: Apply damage resistances/immunities based on conditions
        actual_damage = max(0, damage)
        
        self.current_hp -= actual_damage
        
        result = {
            "damage_taken": actual_damage,
            "new_hp": self.current_hp,
            "unconscious": False,
            "dead": False
        }
        
        if self.current_hp <= 0:
            self.current_hp = 0
            if self.is_player:
                self.is_unconscious = True
                result["unconscious"] = True
            else:
                # NPCs typically die at 0 HP
                self.is_dead = True
                result["dead"] = True
        
        return result
    
    def heal(self, healing: int) -> Dict[str, Any]:
        """Apply healing to combatant"""
        if self.is_dead:
            return {"healing_applied": 0, "new_hp": self.current_hp, "revived": False}
        
        old_hp = self.current_hp
        self.current_hp = min(self.max_hp, self.current_hp + healing)
        actual_healing = self.current_hp - old_hp
        
        # Check if this brings them back from unconsciousness
        revived = False
        if self.is_unconscious and self.current_hp > 0:
            self.is_unconscious = False
            self.death_saves_successes = 0
            self.death_saves_failures = 0
            revived = True
        
        return {
            "healing_applied": actual_healing,
            "new_hp": self.current_hp,
            "revived": revived
        }
    
    def add_condition(self, condition: Condition):
        """Add a condition to the combatant"""
        # Remove existing condition of same name
        self.conditions = [c for c in self.conditions if c.name != condition.name]
        self.conditions.append(condition)
    
    def remove_condition(self, condition_name: str) -> bool:
        """Remove a condition by name"""
        original_count = len(self.conditions)
        self.conditions = [c for c in self.conditions if c.name != condition_name]
        return len(self.conditions) < original_count
    
    def has_condition(self, condition_name: str) -> bool:
        """Check if combatant has a specific condition"""
        return any(c.name == condition_name for c in self.conditions)
    
    def update_conditions(self):
        """Update condition durations and remove expired ones"""
        active_conditions = []
        for condition in self.conditions:
            if condition.duration > 0:
                condition.duration -= 1
            
            if not condition.is_expired():
                active_conditions.append(condition)
        
        self.conditions = active_conditions
    
    def reset_turn(self):
        """Reset action economy for new turn"""
        self.has_action = True
        self.has_bonus_action = True
        self.has_reaction = True
        self.movement_remaining = self.max_movement
        
        # Update conditions
        self.update_conditions()


@dataclass
class CombatAction:
    """Represents an action taken in combat"""
    id: str
    combatant_id: str
    action_type: ActionType
    name: str
    description: str
    target_ids: List[str] = field(default_factory=list)
    roll_results: Dict[str, Any] = field(default_factory=dict)
    damage_results: Dict[str, Any] = field(default_factory=dict)
    effects: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


class CombatEngine:
    """Core combat engine managing turn-based combat"""
    
    def __init__(self, dice_roller: Optional[DiceRoller] = None):
        self.dice_roller = dice_roller or DiceRoller()
        
        # Combat state
        self.state = CombatState.INACTIVE
        self.combatants: Dict[str, Combatant] = {}
        self.initiative_order: List[str] = []
        self.current_turn_index: int = 0
        self.round_number: int = 0
        
        # Action tracking
        self.combat_log: List[CombatAction] = []
        self.pending_reactions: List[CombatAction] = []
        
        # Combat settings
        self.auto_roll_initiative: bool = True
        self.auto_end_dead_turns: bool = True
    
    def add_combatant(self, name: str, max_hp: int, armor_class: int, 
                     initiative_bonus: int = 0, is_player: bool = False,
                     **kwargs) -> str:
        """Add a combatant to combat"""
        combatant_id = str(uuid.uuid4())
        
        combatant = Combatant(
            id=combatant_id,
            name=name,
            max_hp=max_hp,
            current_hp=max_hp,
            armor_class=armor_class,
            initiative_bonus=initiative_bonus,
            is_player=is_player,
            **kwargs
        )
        
        self.combatants[combatant_id] = combatant
        return combatant_id
    
    def remove_combatant(self, combatant_id: str) -> bool:
        """Remove a combatant from combat"""
        if combatant_id in self.combatants:
            del self.combatants[combatant_id]
            # Remove from initiative order
            self.initiative_order = [id for id in self.initiative_order if id != combatant_id]
            # Adjust current turn if needed
            if self.current_turn_index >= len(self.initiative_order):
                self.current_turn_index = 0
            return True
        return False
    
    def start_combat(self) -> Dict[str, Any]:
        """Start combat and roll initiative"""
        if not self.combatants:
            return {"success": False, "error": "No combatants added"}
        
        self.state = CombatState.INITIATIVE
        
        # Roll initiative for all combatants
        initiative_results = {}
        for combatant_id, combatant in self.combatants.items():
            if self.auto_roll_initiative:
                roll_result = self.dice_roller.roll(f"1d20+{combatant.initiative_bonus}", 
                                                   f"Initiative for {combatant.name}")
                combatant.initiative = roll_result.total
                initiative_results[combatant_id] = {
                    "name": combatant.name,
                    "roll": roll_result.rolls[0],
                    "bonus": combatant.initiative_bonus,
                    "total": combatant.initiative
                }
        
        # Sort by initiative (highest first)
        self.initiative_order = sorted(self.combatants.keys(), 
                                     key=lambda x: self.combatants[x].initiative, 
                                     reverse=True)
        
        self.state = CombatState.ACTIVE
        self.current_turn_index = 0
        self.round_number = 1
        
        # Reset all combatants for first turn
        for combatant in self.combatants.values():
            combatant.reset_turn()
        
        return {
            "success": True,
            "initiative_results": initiative_results,
            "initiative_order": [(id, self.combatants[id].name, self.combatants[id].initiative) 
                               for id in self.initiative_order],
            "current_combatant": self.get_current_combatant_info()
        }
    
    def get_current_combatant(self) -> Optional[Combatant]:
        """Get the combatant whose turn it is"""
        if (self.state == CombatState.ACTIVE and 
            self.initiative_order and 
            0 <= self.current_turn_index < len(self.initiative_order)):
            combatant_id = self.initiative_order[self.current_turn_index]
            return self.combatants.get(combatant_id)
        return None
    
    def get_current_combatant_info(self) -> Optional[Dict[str, Any]]:
        """Get info about current combatant"""
        combatant = self.get_current_combatant()
        if combatant:
            return {
                "id": combatant.id,
                "name": combatant.name,
                "hp": f"{combatant.current_hp}/{combatant.max_hp}",
                "ac": combatant.armor_class,
                "conditions": [c.name for c in combatant.conditions],
                "is_player": combatant.is_player,
                "is_unconscious": combatant.is_unconscious,
                "is_dead": combatant.is_dead
            }
        return None
    
    def next_turn(self) -> Dict[str, Any]:
        """Advance to the next turn"""
        if self.state != CombatState.ACTIVE:
            return {"success": False, "error": "Combat is not active"}
        
        # Move to next combatant
        self.current_turn_index += 1
        
        # Check if we've completed a round
        if self.current_turn_index >= len(self.initiative_order):
            self.current_turn_index = 0
            self.round_number += 1
            
            # Update all combatant conditions at start of new round
            for combatant in self.combatants.values():
                combatant.update_conditions()
        
        # Reset current combatant's turn
        current_combatant = self.get_current_combatant()
        if current_combatant:
            current_combatant.reset_turn()
            
            # Skip dead combatants
            if self.auto_end_dead_turns and not current_combatant.is_alive():
                return self.next_turn()
        
        return {
            "success": True,
            "round": self.round_number,
            "current_combatant": self.get_current_combatant_info(),
            "message": f"Round {self.round_number}: {current_combatant.name}'s turn" if current_combatant else "Turn advanced"
        }
    
    def make_attack(self, attacker_id: str, target_id: str, 
                   advantage: bool = False, disadvantage: bool = False) -> Dict[str, Any]:
        """Make an attack roll"""
        attacker = self.combatants.get(attacker_id)
        target = self.combatants.get(target_id)
        
        if not attacker or not target:
            return {"success": False, "error": "Invalid attacker or target"}
        
        if not attacker.has_action:
            return {"success": False, "error": "No action available"}
        
        # Roll attack
        attack_expression = f"1d20+{attacker.attack_bonus}"
        if advantage and not disadvantage:
            attack_expression += " advantage"
        elif disadvantage and not advantage:
            attack_expression += " disadvantage"
        
        attack_roll = self.dice_roller.roll(attack_expression, 
                                           f"{attacker.name} attacks {target.name}")
        
        hit = attack_roll.total >= target.armor_class
        critical_hit = attack_roll.critical_hit
        
        result = {
            "success": True,
            "attacker": attacker.name,
            "target": target.name,
            "attack_roll": attack_roll.total,
            "target_ac": target.armor_class,
            "hit": hit,
            "critical_hit": critical_hit,
            "description": f"{attacker.name} attacks {target.name}: {attack_roll}"
        }
        
        # Roll damage if hit
        if hit:
            damage_roll = self.dice_roller.roll(attacker.damage_dice, "Damage")
            if critical_hit:
                # Double dice for critical hits
                crit_damage_roll = self.dice_roller.roll(attacker.damage_dice, "Critical Damage")
                total_damage = damage_roll.total + crit_damage_roll.total + attacker.damage_bonus
                result["damage_rolls"] = [damage_roll.total, crit_damage_roll.total]
            else:
                total_damage = damage_roll.total + attacker.damage_bonus
                result["damage_rolls"] = [damage_roll.total]
            
            result["damage_bonus"] = attacker.damage_bonus
            result["total_damage"] = total_damage
            
            # Apply damage
            damage_result = target.take_damage(total_damage)
            result.update(damage_result)
            result["target_hp"] = f"{target.current_hp}/{target.max_hp}"
        
        # Use attacker's action
        attacker.has_action = False
        
        # Log the action
        action = CombatAction(
            id=str(uuid.uuid4()),
            combatant_id=attacker_id,
            action_type=ActionType.ACTION,
            name="Attack",
            description=result["description"],
            target_ids=[target_id],
            roll_results={"attack": attack_roll.total},
            damage_results=result.get("damage_result", {}),
            effects=[]
        )
        self.combat_log.append(action)
        
        return result
    
    def cast_spell(self, caster_id: str, spell_name: str, targets: List[str] = None,
                   spell_level: int = 1) -> Dict[str, Any]:
        """Cast a spell (basic implementation)"""
        caster = self.combatants.get(caster_id)
        if not caster:
            return {"success": False, "error": "Invalid caster"}
        
        if not caster.has_action:
            return {"success": False, "error": "No action available"}
        
        # This is a basic implementation - full spell system would be more complex
        result = {
            "success": True,
            "caster": caster.name,
            "spell": spell_name,
            "level": spell_level,
            "description": f"{caster.name} casts {spell_name}"
        }
        
        caster.has_action = False
        
        # Log the action
        action = CombatAction(
            id=str(uuid.uuid4()),
            combatant_id=caster_id,
            action_type=ActionType.ACTION,
            name=f"Cast {spell_name}",
            description=result["description"],
            target_ids=targets or [],
            effects=[f"Cast {spell_name} at level {spell_level}"]
        )
        self.combat_log.append(action)
        
        return result
    
    def end_turn(self, combatant_id: str) -> Dict[str, Any]:
        """End the current combatant's turn"""
        current = self.get_current_combatant()
        if not current or current.id != combatant_id:
            return {"success": False, "error": "Not this combatant's turn"}
        
        return self.next_turn()
    
    def end_combat(self) -> Dict[str, Any]:
        """End combat"""
        self.state = CombatState.ENDED
        
        # Generate combat summary
        alive_combatants = [c for c in self.combatants.values() if c.is_alive()]
        dead_combatants = [c for c in self.combatants.values() if not c.is_alive()]
        
        return {
            "success": True,
            "rounds": self.round_number,
            "actions_taken": len(self.combat_log),
            "survivors": [{"name": c.name, "hp": f"{c.current_hp}/{c.max_hp}"} for c in alive_combatants],
            "casualties": [c.name for c in dead_combatants]
        }
    
    def get_combat_status(self) -> Dict[str, Any]:
        """Get current combat status"""
        return {
            "state": self.state.value,
            "round": self.round_number,
            "combatants": [
                {
                    "id": c.id,
                    "name": c.name,
                    "hp": f"{c.current_hp}/{c.max_hp}",
                    "ac": c.armor_class,
                    "initiative": c.initiative,
                    "conditions": [cond.name for cond in c.conditions],
                    "is_alive": c.is_alive(),
                    "is_current": c.id == (self.initiative_order[self.current_turn_index] 
                                         if self.initiative_order and 
                                         0 <= self.current_turn_index < len(self.initiative_order) 
                                         else None)
                }
                for c in self.combatants.values()
            ],
            "current_combatant": self.get_current_combatant_info()
        }


class CombatEngineAgent(BaseAgent):
    """Combat Engine Agent that provides combat services to other agents"""
    
    def __init__(self, dice_roller: Optional[DiceRoller] = None):
        super().__init__("combat_engine", "CombatEngine")
        self.combat_engine = CombatEngine(dice_roller)
    
    def _setup_handlers(self):
        """Setup message handlers for combat engine"""
        self.register_handler("add_combatant", self._handle_add_combatant)
        self.register_handler("start_combat", self._handle_start_combat)
        self.register_handler("make_attack", self._handle_make_attack)
        self.register_handler("cast_spell", self._handle_cast_spell)
        self.register_handler("next_turn", self._handle_next_turn)
        self.register_handler("end_turn", self._handle_end_turn)
        self.register_handler("end_combat", self._handle_end_combat)
        self.register_handler("get_combat_status", self._handle_get_combat_status)
        self.register_handler("apply_damage", self._handle_apply_damage)
        self.register_handler("apply_healing", self._handle_apply_healing)
        self.register_handler("add_condition", self._handle_add_condition)
        self.register_handler("remove_condition", self._handle_remove_condition)
    
    def _handle_add_combatant(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle add combatant request"""
        name = message.data.get("name")
        max_hp = message.data.get("max_hp", 10)
        armor_class = message.data.get("armor_class", 10)
        initiative_bonus = message.data.get("initiative_bonus", 0)
        is_player = message.data.get("is_player", False)
        
        if not name:
            return {"success": False, "error": "Name is required"}
        
        try:
            combatant_id = self.combat_engine.add_combatant(
                name=name,
                max_hp=max_hp,
                armor_class=armor_class,
                initiative_bonus=initiative_bonus,
                is_player=is_player,
                **{k: v for k, v in message.data.items() 
                   if k not in ["name", "max_hp", "armor_class", "initiative_bonus", "is_player"]}
            )
            
            return {
                "success": True,
                "combatant_id": combatant_id,
                "message": f"Added {name} to combat"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_start_combat(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle start combat request"""
        try:
            result = self.combat_engine.start_combat()
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_make_attack(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle attack request"""
        attacker_id = message.data.get("attacker_id")
        target_id = message.data.get("target_id")
        advantage = message.data.get("advantage", False)
        disadvantage = message.data.get("disadvantage", False)
        
        if not attacker_id or not target_id:
            return {"success": False, "error": "Attacker and target IDs are required"}
        
        try:
            result = self.combat_engine.make_attack(attacker_id, target_id, advantage, disadvantage)
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_cast_spell(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle spell casting request"""
        caster_id = message.data.get("caster_id")
        spell_name = message.data.get("spell_name")
        targets = message.data.get("targets", [])
        spell_level = message.data.get("spell_level", 1)
        
        if not caster_id or not spell_name:
            return {"success": False, "error": "Caster ID and spell name are required"}
        
        try:
            result = self.combat_engine.cast_spell(caster_id, spell_name, targets, spell_level)
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_next_turn(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle next turn request"""
        try:
            result = self.combat_engine.next_turn()
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_end_turn(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle end turn request"""
        combatant_id = message.data.get("combatant_id")
        if not combatant_id:
            return {"success": False, "error": "Combatant ID is required"}
        
        try:
            result = self.combat_engine.end_turn(combatant_id)
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_end_combat(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle end combat request"""
        try:
            result = self.combat_engine.end_combat()
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_get_combat_status(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle combat status request"""
        try:
            status = self.combat_engine.get_combat_status()
            return {"success": True, "status": status}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_apply_damage(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle apply damage request"""
        target_id = message.data.get("target_id")
        damage = message.data.get("damage", 0)
        damage_type = message.data.get("damage_type", "untyped")
        
        if not target_id:
            return {"success": False, "error": "Target ID is required"}
        
        try:
            target = self.combat_engine.combatants.get(target_id)
            if not target:
                return {"success": False, "error": "Target not found"}
            
            result = target.take_damage(damage, damage_type)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_apply_healing(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle apply healing request"""
        target_id = message.data.get("target_id")
        healing = message.data.get("healing", 0)
        
        if not target_id:
            return {"success": False, "error": "Target ID is required"}
        
        try:
            target = self.combat_engine.combatants.get(target_id)
            if not target:
                return {"success": False, "error": "Target not found"}
            
            result = target.heal(healing)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_add_condition(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle add condition request"""
        target_id = message.data.get("target_id")
        condition_name = message.data.get("condition_name")
        description = message.data.get("description", "")
        duration = message.data.get("duration", -1)
        source = message.data.get("source", "")
        
        if not target_id or not condition_name:
            return {"success": False, "error": "Target ID and condition name are required"}
        
        try:
            target = self.combat_engine.combatants.get(target_id)
            if not target:
                return {"success": False, "error": "Target not found"}
            
            condition = Condition(
                name=condition_name,
                description=description,
                duration=duration,
                source=source
            )
            
            target.add_condition(condition)
            return {"success": True, "message": f"Added {condition_name} to {target.name}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_remove_condition(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle remove condition request"""
        target_id = message.data.get("target_id")
        condition_name = message.data.get("condition_name")
        
        if not target_id or not condition_name:
            return {"success": False, "error": "Target ID and condition name are required"}
        
        try:
            target = self.combat_engine.combatants.get(target_id)
            if not target:
                return {"success": False, "error": "Target not found"}
            
            removed = target.remove_condition(condition_name)
            return {
                "success": True,
                "removed": removed,
                "message": f"{'Removed' if removed else 'Did not find'} {condition_name} on {target.name}"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def process_tick(self):
        """Process combat engine tick - handle ongoing effects"""
        if self.combat_engine.state == CombatState.ACTIVE:
            # Process ongoing effects, condition timers, etc.
            pass


if __name__ == "__main__":
    # Test the combat engine
    combat = CombatEngine()
    
    print("=== Combat Engine Test ===")
    
    # Add combatants
    player_id = combat.add_combatant("Kali", 25, 16, 3, is_player=True)
    orc_id = combat.add_combatant("Orc Warrior", 15, 13, 0)
    
    print("Added combatants")
    
    # Start combat
    result = combat.start_combat()
    print(f"Combat started: {result}")
    
    # Show status
    status = combat.get_combat_status()
    print(f"Combat status: {status}")
    
    # Make some attacks
    if combat.get_current_combatant():
        current_id = combat.get_current_combatant().id
        other_id = orc_id if current_id == player_id else player_id
        
        attack_result = combat.make_attack(current_id, other_id)
        print(f"Attack result: {attack_result}")
        
        # Next turn
        turn_result = combat.next_turn()
        print(f"Next turn: {turn_result}")
    
    # End combat
    end_result = combat.end_combat()
    print(f"Combat ended: {end_result}")