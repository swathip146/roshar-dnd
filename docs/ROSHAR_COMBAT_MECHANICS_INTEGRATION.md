# Roshar Combat Mechanics Integration

**Date:** 2026-01-03
**Status:** ✅ Combat Plan Updated with Official Cosmere 5e Rules
**Source:** Cosmere 5e: Radiant's Handbook v2.0

---

## Executive Summary

Updated the Combat Engine Implementation Plan to accurately reflect the official Cosmere 5e mechanics from the Radiant's Handbook. The key discovery is that **Surgebinding is already integrated into standard D&D 5e action economy** - Surges use the same action/bonus action/reaction system as D&D spells and abilities.

**Key Finding:** Roshar abilities don't need separate custom action tracking - they integrate seamlessly with dnd_engine's existing action economy system.

---

## Table of Contents

1. [Knights Radiant Orders](#knights-radiant-orders)
2. [Surgebinding Mechanics](#surgebinding-mechanics)
3. [Stormlight Mechanics](#stormlight-mechanics)
4. [Shardblade & Shardplate](#shardblade--shardplate)
5. [Combat Integration](#combat-integration)
6. [Updated ACTION_REGISTRY](#updated-action_registry)
7. [Implementation Changes](#implementation-changes)

---

## Knights Radiant Orders

### Nine Playable Orders

From Radiant's Handbook Chapter 3 (pages 30-122):

| Order | Primary Abilities | Hit Die | Surges | Description |
|-------|------------------|---------|--------|-------------|
| **Windrunner** | STR or DEX | d10 | Adhesion & Gravitation | Graceful flying fighters who protect others |
| **Skybreaker** | STR/DEX & INT | d10 | Gravitation & Division | Flying judges focused on destruction |
| **Dustbringer** | DEX & WIS | d8 | Division & Abrasion | Quick, lethal destructive warriors |
| **Edgedancer** | WIS | d8 | Abrasion & Progression | Fast healers who can change forms |
| **Truthwatcher** | INT/WIS/CHA | d8 | Progression & Illumination | Healers with illusory abilities |
| **Lightweaver** | CHA | d6 | Illumination & Transformation | Powerful illusionists and Soulcasters |
| **Elsecaller** | INT | d8 | Transformation & Transportation | Soulcasters who can teleport |
| **Willshaper** | DEX & CHA | d8 | Transportation & Cohesion | Nimble fighters using shadows |
| **Stoneward** | STR & CON | d12 | Cohesion & Tension | Durable tanks with extreme offense/defense |

**Note:** Bondsmith Order is intentionally not included as a playable class (too powerful).

---

## Surgebinding Mechanics

### The Ten Surges

Each Order has access to two Surges (magical abilities). From the handbook:

1. **Adhesion** - Binding objects/creatures together (pressure manipulation)
2. **Gravitation** - Altering direction/strength of gravity
3. **Division** - Destructive power (decomposition, friction, fire)
4. **Abrasion** - Reducing friction, increasing speed
5. **Progression** - Growth and healing
6. **Illumination** - Light and sound manipulation (illusions)
7. **Transformation** - Soulcasting (changing matter's form)
8. **Transportation** - Moving between Realms (Shadesmar)
9. **Cohesion** - Manipulating solid/liquid states
10. **Tension** - Hardness and flexibility control

### Action Economy Integration

**CRITICAL FINDING:** From handbook Chapter 9 (Combat):

- **Surges use standard D&D 5e action economy**
- Most Surge abilities cost **1 Action** or **1 Bonus Action**
- Some advanced abilities cost **1 Reaction**
- **No separate "Investiture Points"** - Surges are powered by Stormlight spheres

Example from Windrunner class:
```
Lashing (Gravitation Surge)
- Cost: 1 Action
- Stormlight: 1 sphere consumed
- Effect: Change gravity direction for target
```

Example from Edgedancer class:
```
Healing Touch (Progression Surge)
- Cost: 1 Bonus Action
- Stormlight: 1-3 spheres consumed
- Effect: Heal target 1d8 per sphere
```

---

## Stormlight Mechanics

### Stormlight Spheres

From Radiant's Handbook Chapter 5 (Equipment):

**Currency & Power Source:**
- Stormlight is stored in gemstones (spheres)
- **1 sphere = 1 Stormlight charge** for powering Surges
- Spheres are also currency (different denominations: chip, mark, broam)

**Sphere Capacity:**
- Characters have a **Stormlight Capacity** based on Radiant level
- Capacity = **Radiant Level × 2** spheres
- Example: Level 5 Windrunner can hold 10 spheres

**Replenishing Stormlight:**
- Spheres naturally infuse during **Highstorms** (every 4-5 days)
- Can be manually infused at Perpendicularities
- Dun (empty) spheres have no monetary value

### Stormlight Healing

**Passive Healing (Core Mechanic):**
- While holding **at least 1 sphere**, Radiants passively heal
- **Healing Rate:** 1 HP per sphere held, per Short Rest
- Example: Holding 5 spheres = heal 5 HP during Short Rest

**Active Healing (Progression Surge):**
- Edgedancers & Truthwatchers can actively heal
- Cost: 1 Bonus Action + Stormlight spheres
- Effect: Heal 1d8 HP per sphere consumed (up to proficiency bonus spheres)

---

## Shardblade & Shardplate

### Shardblades

From Radiant's Handbook Chapter 5 (Equipment) and class features:

**Radiant Shardblades (Spren Weapons):**
- **Summoning:** 1 Bonus Action (6 seconds = 1 round in standard D&D)
- **Dismissal:** Free action
- **Properties:**
  - Weapon damage varies by Order (e.g., 1d10 for Windrunner greatsword)
  - Finesse, Versatile, or other properties
  - **Soul Damage:** On hit, target must make CON save or take extra damage + stunned effect
  - **Living Shardplate Cutting:** Ignores AC bonus from living Shardplate

**Dead Shardblades (Ancient Blades):**
- Always physical (can't be dismissed)
- Same soul damage mechanics
- No Bond required (can be wielded by non-Radiants)

**Soul Damage Mechanics:**
```
On hit with Shardblade:
- Target makes Constitution Saving Throw
- DC = 8 + proficiency + STR or DEX modifier
- Failure:
  - Additional 2d6 necrotic damage (soul severing)
  - Stunned until end of next turn
  - Limb may be severed (GM discretion)
- Success: No additional effect
```

### Shardplate

From Radiant's Handbook Chapter 5 (Equipment):

**Living Shardplate (Radiant Armor):**
- **AC:** Base 18 (heavy armor)
- **Properties:**
  - STR requirement: None (bonded armor)
  - Stealth: No disadvantage
  - **Damage Resistance:** Resistant to all physical damage (slashing, piercing, bludgeoning)
  - **Plate HP:** Armor has HP pool (separate from wearer)
  - **Regeneration:** Plate regenerates when exposed to Stormlight

**Dead Shardplate (Ancient Armor):**
- Same AC and resistance
- No regeneration
- Can be worn by non-Radiants

**Shardplate HP System:**
```
Shardplate HP = Wearer's Level × 5
- When hit, player can choose: damage to self OR damage to Plate
- Plate breaks when HP reaches 0
- Repairs automatically during Long Rest if Stormlight available
```

---

## Combat Integration

### How Roshar Fits with D&D 5e / dnd_engine

The **key insight** is that Cosmere 5e is already a D&D 5e supplement. It doesn't add new action systems - it uses the existing ones:

#### Action Economy (Unchanged)
```
Turn Structure (same as D&D 5e):
- 1 Action (Attack, Surge ability, Dash, etc.)
- 1 Bonus Action (Summon Shardblade, Quick Surge, etc.)
- 1 Reaction (Opportunity Attack, defensive Surge, etc.)
- Movement (based on speed)
```

#### Radiant-Specific Additions
```
Resource Tracking:
- Stormlight Spheres (current / maximum capacity)
- Shardblade Summoned (yes/no)
- Shardplate HP (current / maximum)
- Ideal Level (determines available abilities)
```

#### Combat Flow Example
```
Windrunner's Turn:
1. Movement: Use Lashing to fly up 30 feet (1 Action + 1 sphere)
2. Attack: Standard melee attack with summoned Shardblade (already summoned)
3. Bonus Action: Apply Adhesion to stick enemy to wall (1 sphere)

NPC Skybreaker's Turn:
1. Action: Use Division to launch fire beam (1 Action + 2 spheres)
2. Movement: Fly toward target using Gravitation
3. Reaction: Shield self with gravitation field when attacked
```

---

## Updated ACTION_REGISTRY

Based on official Cosmere 5e rules, here's the corrected ACTION_REGISTRY for the combat system:

### D&D 5e Actions (Unchanged)
```python
ACTION_REGISTRY = {
    # ========================================
    # D&D 5e ACTIONS (via dnd_engine)
    # ========================================
    "attack": {
        "type": "dnd_action",
        "action_class": Attack,
        "params": ["target_entity_uuid", "weapon_slot"],
        "description": "Standard melee/ranged attack",
        "cost_type": "actions",
        "cost": 1
    },
    "move": {
        "type": "dnd_action",
        "action_class": Move,
        "params": ["end_position"],
        "description": "Move to a position",
        "cost_type": "movement"
    },
    "dash": {
        "type": "dnd_condition",
        "condition_class": Dashing,
        "duration": Duration(duration=1, duration_type=DurationType.TURNS),
        "description": "Double movement speed",
        "cost_type": "actions",
        "cost": 1
    },
    "dodge": {
        "type": "dnd_action",
        "description": "Impose disadvantage on attacks against you",
        "cost_type": "actions",
        "cost": 1
    },
    "disengage": {
        "type": "dnd_action",
        "description": "Move without provoking opportunity attacks",
        "cost_type": "actions",
        "cost": 1
    },

    # ========================================
    # ROSHAR ACTIONS - WINDRUNNER (Adhesion & Gravitation)
    # ========================================
    "basic_lashing": {
        "type": "roshar_surge",
        "surge_type": "Gravitation",
        "params": ["target_entity_uuid", "direction"],
        "description": "Change gravity direction for target",
        "cost_type": "actions",
        "cost": 1,
        "stormlight_cost": 1,
        "requires": "windrunner",
        "saving_throw": {"ability": "strength", "dc_formula": "8 + proficiency + wisdom"}
    },
    "full_lashing": {
        "type": "roshar_surge",
        "surge_type": "Gravitation",
        "params": ["target_entity_uuid"],
        "description": "Increase/decrease target's weight",
        "cost_type": "actions",
        "cost": 1,
        "stormlight_cost": 2,
        "requires": "windrunner",
        "saving_throw": {"ability": "strength", "dc_formula": "8 + proficiency + wisdom"}
    },
    "adhesion_bind": {
        "type": "roshar_surge",
        "surge_type": "Adhesion",
        "params": ["target_entity_uuid", "surface_type"],
        "description": "Bind target to surface using pressure",
        "cost_type": "bonus_actions",
        "cost": 1,
        "stormlight_cost": 1,
        "requires": "windrunner",
        "saving_throw": {"ability": "strength", "dc_formula": "8 + proficiency + wisdom"}
    },

    # ========================================
    # ROSHAR ACTIONS - SKYBREAKER (Gravitation & Division)
    # ========================================
    "division_blast": {
        "type": "roshar_surge",
        "surge_type": "Division",
        "params": ["target_entity_uuid"],
        "description": "Unleash destructive energy beam",
        "cost_type": "actions",
        "cost": 1,
        "stormlight_cost": 2,
        "requires": "skybreaker",
        "damage": "3d10 fire",
        "saving_throw": {"ability": "dexterity", "dc_formula": "8 + proficiency + intelligence"}
    },

    # ========================================
    # ROSHAR ACTIONS - EDGEDANCER (Abrasion & Progression)
    # ========================================
    "slickness": {
        "type": "roshar_surge",
        "surge_type": "Abrasion",
        "params": [],
        "description": "Reduce friction, increase speed",
        "cost_type": "bonus_actions",
        "cost": 1,
        "stormlight_cost": 1,
        "requires": "edgedancer",
        "duration": "1 round",
        "effect": "speed +10 feet, advantage on Acrobatics"
    },
    "healing_touch": {
        "type": "roshar_surge",
        "surge_type": "Progression",
        "params": ["target_entity_uuid", "spheres_consumed"],
        "description": "Heal target using Progression",
        "cost_type": "bonus_actions",
        "cost": 1,
        "stormlight_cost": "variable (1-proficiency)",
        "requires": "edgedancer",
        "healing": "1d8 per sphere"
    },

    # ========================================
    # ROSHAR ACTIONS - LIGHTWEAVER (Illumination & Transformation)
    # ========================================
    "lightweaving": {
        "type": "roshar_surge",
        "surge_type": "Illumination",
        "params": ["illusion_type", "target_location"],
        "description": "Create visual/auditory illusions",
        "cost_type": "actions",
        "cost": 1,
        "stormlight_cost": 1,
        "requires": "lightweaver",
        "duration": "concentration, up to 10 minutes"
    },
    "soulcast": {
        "type": "roshar_surge",
        "surge_type": "Transformation",
        "params": ["target_object", "new_substance"],
        "description": "Transform matter into different substance",
        "cost_type": "actions",
        "cost": 1,
        "stormlight_cost": 3,
        "requires": "lightweaver",
        "saving_throw": {"ability": "charisma", "dc_formula": "8 + proficiency + charisma"}
    },

    # ========================================
    # ROSHAR ACTIONS - ELSECALLER (Transformation & Transportation)
    # ========================================
    "elsecaller_soulcast": {
        "type": "roshar_surge",
        "surge_type": "Transformation",
        "params": ["target_object", "new_substance"],
        "description": "Transform matter (Elsecaller version)",
        "cost_type": "actions",
        "cost": 1,
        "stormlight_cost": 2,
        "requires": "elsecaller",
        "saving_throw": {"ability": "intelligence", "dc_formula": "8 + proficiency + intelligence"}
    },
    "shadesmar_step": {
        "type": "roshar_surge",
        "surge_type": "Transportation",
        "params": ["target_location"],
        "description": "Teleport via Cognitive Realm",
        "cost_type": "bonus_actions",
        "cost": 1,
        "stormlight_cost": 3,
        "requires": "elsecaller",
        "range": "60 feet"
    },

    # ========================================
    # ROSHAR ACTIONS - STONEWARD (Cohesion & Tension)
    # ========================================
    "stone_shaping": {
        "type": "roshar_surge",
        "surge_type": "Cohesion",
        "params": ["target_stone"],
        "description": "Manipulate stone structures",
        "cost_type": "actions",
        "cost": 1,
        "stormlight_cost": 2,
        "requires": "stoneward"
    },
    "tension_hardening": {
        "type": "roshar_surge",
        "surge_type": "Tension",
        "params": [],
        "description": "Harden skin to resist damage",
        "cost_type": "bonus_actions",
        "cost": 1,
        "stormlight_cost": 1,
        "requires": "stoneward",
        "duration": "1 round",
        "effect": "resistance to physical damage"
    },

    # ========================================
    # ROSHAR EQUIPMENT ACTIONS
    # ========================================
    "summon_shardblade": {
        "type": "roshar_equipment",
        "params": [],
        "description": "Summon bonded Shardblade",
        "cost_type": "bonus_actions",
        "cost": 1,
        "stormlight_cost": 0,
        "requires": "shardblade_bond",
        "summon_time": "1 round (6 seconds)"
    },
    "dismiss_shardblade": {
        "type": "roshar_equipment",
        "params": [],
        "description": "Dismiss Shardblade to mist",
        "cost_type": "free_action",
        "cost": 0,
        "stormlight_cost": 0,
        "requires": "shardblade_bond"
    },
    "shardblade_attack": {
        "type": "roshar_equipment",
        "params": ["target_entity_uuid"],
        "description": "Attack with Shardblade (soul damage)",
        "cost_type": "actions",
        "cost": 1,
        "stormlight_cost": 0,
        "requires": "shardblade_summoned",
        "weapon_damage": "1d10 + STR/DEX",
        "soul_damage": "2d6 necrotic on failed CON save",
        "saving_throw": {"ability": "constitution", "dc_formula": "8 + proficiency + strength_or_dex"}
    },

    # ========================================
    # ROSHAR CONDITIONS
    # ========================================
    "stormlight_infused": {
        "type": "roshar_condition",
        "description": "Passively healing while holding Stormlight",
        "effect": "heal 1 HP per sphere held during Short Rest",
        "trigger": "holding at least 1 sphere"
    },
    "shardplate_equipped": {
        "type": "roshar_condition",
        "description": "Wearing Shardplate armor",
        "ac_bonus": 18,
        "resistance": ["physical"],
        "plate_hp": "level × 5",
        "requires": "shardplate_bond"
    }
}
```

---

## Implementation Changes

### 1. Character Data Extensions

Add Roshar-specific fields to CharacterData:

```python
class RosharCharacterData(CharacterData):
    """Extended character data for Radiant characters"""

    # Radiant-specific
    radiant_order: Optional[str] = None  # "Windrunner", "Skybreaker", etc.
    ideal_level: int = 1  # Which Ideal they've sworn (1-5)

    # Stormlight
    stormlight_current: int = 0  # Current spheres held
    stormlight_capacity: int = 0  # Max spheres = level × 2

    # Equipment
    has_shardblade: bool = False
    shardblade_summoned: bool = False
    shardblade_type: Optional[str] = None  # "living" or "dead"

    has_shardplate: bool = False
    shardplate_hp_current: int = 0
    shardplate_hp_maximum: int = 0
    shardplate_type: Optional[str] = None  # "living" or "dead"

    # Surges (list of available Surge types)
    surges: List[str] = []  # e.g., ["Adhesion", "Gravitation"]
```

### 2. Stormlight Tracking Component

Create new component for Stormlight management:

```python
# components/stormlight_manager.py

class StormlightManager:
    """Manages Stormlight spheres for Radiant characters"""

    def __init__(self, character_manager):
        self.character_manager = character_manager
        self.logger = get_logger(__name__)

    def consume_stormlight(self, char_id: str, amount: int) -> bool:
        """
        Consume Stormlight spheres for Surge use.

        Returns:
            True if successful, False if insufficient Stormlight
        """
        character = self.character_manager.characters[char_id]

        if character.stormlight_current < amount:
            self.logger.warning(f"{char_id} has insufficient Stormlight ({character.stormlight_current}/{amount})")
            return False

        character.stormlight_current -= amount
        self.logger.debug(f"{char_id} consumed {amount} Stormlight ({character.stormlight_current} remaining)")
        return True

    def replenish_stormlight(self, char_id: str, amount: int):
        """Add Stormlight spheres (from Highstorm, loot, etc.)"""
        character = self.character_manager.characters[char_id]

        # Cap at maximum capacity
        new_amount = min(
            character.stormlight_current + amount,
            character.stormlight_capacity
        )

        gained = new_amount - character.stormlight_current
        character.stormlight_current = new_amount

        self.logger.info(f"{char_id} gained {gained} Stormlight ({character.stormlight_current}/{character.stormlight_capacity})")

    def apply_passive_healing(self, char_id: str, rest_type: str = "short"):
        """Apply passive Stormlight healing during rest"""
        character = self.character_manager.characters[char_id]

        if character.stormlight_current <= 0:
            return

        if rest_type == "short":
            # Heal 1 HP per sphere held
            healing = character.stormlight_current
            character.hit_points["current"] = min(
                character.hit_points["current"] + healing,
                character.hit_points["maximum"]
            )

            self.logger.info(f"{char_id} passively healed {healing} HP from Stormlight")
```

### 3. Roshar Action Implementation

Create Roshar-specific Actions following dnd_engine patterns:

```python
# components/combat/roshar_actions.py

from dnd.core.base_actions import BaseAction, ActionEvent
from dnd.core.events import EventPhase, EventType
from dnd.entity import Entity
from typing import Tuple, Optional

class LashingEvent(ActionEvent):
    """Event for Windrunner Lashing (Gravitation Surge)"""
    name: str = "Basic Lashing"
    event_type: EventType = EventType.CUSTOM  # Roshar-specific
    lashing_type: str  # "basic" or "full"
    stormlight_cost: int  # Spheres consumed
    target_direction: Optional[Tuple[int, int, int]] = None  # Gravity direction vector
    weight_multiplier: Optional[float] = None  # For full lashing

class BasicLashing(BaseAction):
    """
    Windrunner Basic Lashing - Change gravity direction

    From Radiant's Handbook:
    - Cost: 1 Action + 1 Stormlight sphere
    - Effect: Target's gravity changes to point in chosen direction
    - Duration: Concentration, up to 1 minute
    - Saving Throw: Strength DC 8 + proficiency + WIS modifier
    """
    name: str = "Basic Lashing"
    description: str = "Change target's gravity direction"
    cost_type: str = "actions"
    cost: int = 1
    stormlight_cost: int = 1

    target_entity_uuid: UUID
    direction: Tuple[int, int, int]  # Normalized direction vector

    def _validate(self, declaration_event: LashingEvent) -> LashingEvent:
        """Validate Lashing prerequisites"""
        source = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid)

        # Check Windrunner Order
        if not hasattr(source, 'radiant_order') or source.radiant_order != "Windrunner":
            return declaration_event.cancel(status_message="Only Windrunners can use Lashing")

        # Check Stormlight availability
        if not hasattr(source, 'stormlight_current') or source.stormlight_current < self.stormlight_cost:
            return declaration_event.cancel(status_message="Insufficient Stormlight")

        # Check range (touch or within 30 feet at higher Ideals)
        distance = self._calculate_distance(source.position, target.position)
        max_range = 5 if source.ideal_level < 3 else 30

        if distance > max_range:
            return declaration_event.cancel(status_message=f"Target too far (max {max_range} feet)")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message="Lashing validated"
        )

    def _apply(self, execution_event: LashingEvent) -> LashingEvent:
        """Apply Lashing effects"""
        source = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid)

        # Consume Stormlight
        source.stormlight_current -= self.stormlight_cost

        # Target makes Strength saving throw
        dc = 8 + source.proficiency_bonus + source.ability_modifier("wisdom")
        save_roll = target.saving_throw("strength", dc)

        if save_roll.success:
            return execution_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{target.name} resists the Lashing"
            )

        # Apply gravity direction change (via condition)
        lashed_condition = LashedCondition(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=target.uuid,
            gravity_direction=self.direction,
            duration=Duration(duration=10, duration_type=DurationType.ROUNDS)  # Concentration
        )
        lashed_condition.apply(execution_event)

        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Lashed {target.name} - gravity now points {self.direction}"
        )

class ShardbladeAttack(BaseAction):
    """
    Attack with Shardblade (soul-severing weapon)

    From Radiant's Handbook:
    - Cost: 1 Action (standard attack action)
    - Damage: Weapon damage (1d10 for greatsword) + soul damage
    - Soul Damage: 2d6 necrotic + stunned on failed CON save
    - DC: 8 + proficiency + STR or DEX modifier
    """
    name: str = "Shardblade Attack"
    description: str = "Attack with soul-severing Shardblade"
    cost_type: str = "actions"
    cost: int = 1

    target_entity_uuid: UUID

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        """Validate Shardblade attack prerequisites"""
        source = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid)

        # Check Shardblade summoned
        if not getattr(source, 'shardblade_summoned', False):
            return declaration_event.cancel(status_message="Shardblade not summoned")

        # Check range (melee)
        distance = self._calculate_distance(source.position, target.position)
        if distance > 5:
            return declaration_event.cancel(status_message="Target not in melee range")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message="Shardblade attack validated"
        )

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        """Execute Shardblade attack with soul damage"""
        source = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid)

        # Standard attack roll (using dnd_engine's attack system)
        attack_bonus = source.equipment.attack_bonus.normalized_score
        attack_roll = source.roll_d20(attack_bonus, RollType.ATTACK)

        target_ac = target.equipment.ac_bonus.normalized_score

        if attack_roll.total < target_ac:
            return execution_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"Shardblade attack missed (rolled {attack_roll.total} vs AC {target_ac})"
            )

        # Weapon damage
        weapon_damage = self._roll_damage("1d10", source.ability_modifier("strength"))
        target.health.take_damage(weapon_damage)

        # Soul damage (CON save)
        dc = 8 + source.proficiency_bonus + max(
            source.ability_modifier("strength"),
            source.ability_modifier("dexterity")
        )

        soul_save = target.saving_throw("constitution", dc)

        if not soul_save.success:
            # Soul damage
            soul_damage = self._roll_damage("2d6", 0, damage_type="necrotic")
            target.health.take_damage(soul_damage)

            # Apply Stunned condition
            stunned = StunnedCondition(
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=target.uuid,
                duration=Duration(duration=1, duration_type=DurationType.ROUNDS)
            )
            stunned.apply(execution_event)

            return execution_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"Shardblade severs soul! {weapon_damage + soul_damage} total damage, {target.name} stunned"
            )

        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Shardblade hit for {weapon_damage} damage (soul resisted)"
        )
```

### 4. Updated CombatActionResolver

No changes needed! The generic ACTION_REGISTRY approach already handles Roshar actions:

```python
# components/combat/combat_action_resolver.py

# ACTION_REGISTRY already set up for extensibility
ACTION_REGISTRY = {
    # D&D 5e actions
    "attack": {...},
    "move": {...},

    # Roshar actions automatically discovered
    "basic_lashing": {...},
    "shardblade_attack": {...},
    # ... etc
}

# Resolution logic is already generic - no changes needed!
def resolve_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
    action_type = action["action_type"]
    metadata = self.ACTION_REGISTRY.get(action_type)

    # Works for both D&D and Roshar actions
    if metadata["type"] in ["dnd_action", "roshar_action", "roshar_surge", "roshar_equipment"]:
        return self._execute_action(action, metadata)
```

### 5. UI Updates

Add Stormlight display to combat status:

```python
# components/combat/combat_narrative_generator.py

def generate_combat_status(self, combat_state: Dict) -> str:
    """Enhanced status with Stormlight tracking"""
    status = "\n=== COMBAT STATUS ===\n"
    status += f"Round: {combat_state['round_number']}\n\n"

    # Allies (with Stormlight)
    status += "🟢 Allies:\n"
    for ally_id in allies:
        char = self.character_manager.characters[ally_id]
        state = combat_state['combatant_states'][ally_id]

        status += f"  - {char.name}: {state['hp_current']}/{state['hp_max']} HP"

        # Show Stormlight if Radiant
        if hasattr(char, 'stormlight_current'):
            status += f" | ⚡ {char.stormlight_current}/{char.stormlight_capacity} Stormlight"

        # Show Shardblade status
        if hasattr(char, 'shardblade_summoned') and char.shardblade_summoned:
            status += " | 🗡️ Shardblade"

        status += "\n"

    return status
```

---

## Summary of Changes

### What Changed
1. **ACTION_REGISTRY:** Added accurate Roshar actions based on official rules
2. **Stormlight Mechanics:** Implemented sphere tracking and passive healing
3. **Shardblade/Shardplate:** Accurate soul damage and armor mechanics
4. **Surge Actions:** Each Order's Surges properly integrated with action economy
5. **Character Data:** Extended to support Radiant-specific fields

### What Didn't Change
1. **Core Architecture:** Generic, data-driven approach still works perfectly
2. **dnd_engine Integration:** Roshar actions use same patterns as D&D actions
3. **Action Economy:** Surges use standard D&D 5e action/bonus action/reaction system
4. **Combat Flow:** CombatSessionManager methods unchanged (already generic!)

### Key Insight
**Roshar mechanics are D&D 5e-compatible by design.** The Cosmere 5e handbook is a D&D 5e supplement, not a separate system. This means:
- ✅ No custom action economy needed
- ✅ No separate magic system
- ✅ Surges integrate seamlessly with dnd_engine
- ✅ Generic combat plan works without major changes

---

## Next Steps

### Implementation Priority
1. **Phase 3A:** Implement `StormlightManager` component
2. **Phase 3B:** Implement core Roshar actions (Lashing, Shardblade, basic Surges)
3. **Phase 3C:** Update CharacterData with Roshar extensions
4. **Phase 3D:** Add Stormlight UI display to combat status
5. **Phase 3E:** Test with Windrunner + Skybreaker NPCs

### Testing Checklist
- [ ] Lashing changes gravity correctly
- [ ] Stormlight consumption tracks properly
- [ ] Shardblade soul damage applies correctly
- [ ] Passive healing from Stormlight works
- [ ] Action economy tracks Surge usage
- [ ] Shardplate damage resistance applies
- [ ] Multiple Radiant Orders in same combat

---

## References

- **Source:** Cosmere 5e: Radiant's Handbook v2.0 (863203275-Cosmere-5e-Radiant-s-Handbook-v2-0.pdf)
- **Combat Plan:** `docs/COMBAT_ENGINE_IMPLEMENTATION_PLAN.md`
- **dnd_engine Integration:** `docs/DND_ENGINE_COMBAT_CAPABILITIES.md`
- **Generic Architecture:** `docs/COMBAT_PLAN_GENERIC_ARCHITECTURE_UPDATE.md`
