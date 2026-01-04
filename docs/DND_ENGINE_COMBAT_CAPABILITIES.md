# dnd_engine Combat Capabilities Analysis

**Date:** 2026-01-03
**Purpose:** Document dnd_engine's native combat capabilities to inform Combat Engine implementation

---

## Executive Summary

The `external/dnd_engine` repository is a **fully-featured D&D 5e game engine** with sophisticated combat support. Instead of reimplementing combat mechanics, we should **leverage dnd_engine's native Action framework**.

**Key Discovery:** dnd_engine uses an **event-driven architecture** where all combat actions flow through:
```
DECLARATION → EXECUTION → EFFECT → COMPLETION
```

This is far more sophisticated than our current dnd_engine_wrapper approach.

---

## 1. Core Architecture

### 1.1 Event-Driven System

**File:** `external/dnd_engine/dnd/core/events.py`

All game actions are Events with phases:
```python
class Event(BaseObject):
    name: str
    event_type: EventType  # ATTACK, MOVEMENT, DAMAGE, etc.
    phase: EventPhase      # DECLARATION, EXECUTION, EFFECT, COMPLETION
    source_entity_uuid: UUID
    target_entity_uuid: Optional[UUID]
    parent_event: Optional[UUID]
```

**Phases:**
1. **DECLARATION** - Intent declaration (e.g., "I want to attack")
2. **EXECUTION** - Action execution (e.g., rolling dice)
3. **EFFECT** - Applying effects (e.g., dealing damage)
4. **COMPLETION** - Finalizing (e.g., updating state, consuming action economy)

**Benefit:** Reactions can intercept at any phase (Shield spell during EXECUTION, Counterspell during DECLARATION, etc.)

### 1.2 Action Framework

**File:** `external/dnd_engine/dnd/actions.py`

Actions are structured objects with prerequisites and consequences:

```python
class BaseAction(BaseObject):
    name: str
    description: str
    prerequisites: OrderedDict[str, EventProcessor]  # Checks before action
    consequences: OrderedDict[str, EventProcessor]   # Effects of action
    cost_type: CostType  # actions, bonus_actions, reactions, movement
    cost: int
```

**Flow:**
```
Action.apply()
  └── Creates Declaration Event
      └── Checks Prerequisites (range, line of sight, action economy)
          └── Applies Consequences (attack roll, damage)
              └── Consumes Action Economy
```

---

## 2. Native Combat Actions

### 2.1 Attack Action

**File:** `external/dnd_engine/dnd/actions.py:219-400`

**Fully implemented:**
- ✅ Range validation (melee vs ranged)
- ✅ Line of sight checks
- ✅ Attack roll with advantage/disadvantage
- ✅ Critical hit detection
- ✅ Damage calculation with resistances
- ✅ HP tracking and damage application
- ✅ Action economy consumption

**Usage:**
```python
from dnd.actions import Attack, WeaponSlot

# Create attack action
attack = Attack(
    source_entity_uuid=attacker.uuid,
    target_entity_uuid=target.uuid,
    weapon_slot=WeaponSlot.MAIN_HAND
)

# Execute attack (returns AttackEvent with full resolution)
attack_event = attack.apply()

# Access results
if attack_event.attack_outcome == AttackOutcome.HIT:
    damage_dealt = sum(roll.total for roll in attack_event.damage_rolls)
    print(f"Hit! Dealt {damage_dealt} damage")
```

**Event Structure:**
```python
class AttackEvent(ActionEvent):
    weapon_slot: WeaponSlot
    range: Optional[Range]
    attack_bonus: Optional[ModifiableValue]
    ac: Optional[ModifiableValue]
    dice_roll: Optional[DiceRoll]
    attack_outcome: Optional[AttackOutcome]  # HIT, MISS, CRIT_HIT, CRIT_MISS
    damages: Optional[List[Damage]]
    damage_rolls: Optional[List[DiceRoll]]
```

### 2.2 Movement Action

**File:** `external/dnd_engine/dnd/actions.py:68-202`

**Fully implemented:**
- ✅ Pathfinding (uses entity.senses.paths)
- ✅ Movement cost calculation
- ✅ Position updates
- ✅ Line of sight updates for all entities
- ✅ Movement validation

**Usage:**
```python
from dnd.actions import Move

# Create movement action
move = Move(
    source_entity_uuid=entity.uuid,
    end_position=(10, 15),
    use_movement_cost=True
)

# Execute movement
movement_event = move.apply()
if not movement_event.canceled:
    print(f"Moved to {movement_event.end_position}")
```

### 2.3 Dodge, Dash, Disengage (via Conditions)

**File:** `external/dnd_engine/dnd/conditions.py`

These are implemented as **Conditions** that apply modifiers:

**Dashing Condition:**
```python
class Dashing(BaseCondition):
    name: str = "Dashing"
    description: str = "Doubles movement speed"

    def _apply(self, event):
        # Adds movement bonus equal to base speed
        base_speed = target_entity.action_economy.movement.get_base_modifier()
        extra_modifier = NumericalModifier(name="Dashing", value=base_speed)
        target_entity.action_economy.movement.self_static.add_value_modifier(extra_modifier)
```

**To implement Dodge/Disengage:**
- Create similar conditions that apply appropriate modifiers
- Dodge: Adds advantage to attackers' rolls against entity, advantage to entity's DEX saves
- Disengage: Disables opportunity attacks (would need OpportunityAttack action first)

---

## 3. Action Economy System

**File:** `external/dnd_engine/dnd/blocks/action_economy.py`

**Capabilities:**
- ✅ Tracks actions, bonus actions, reactions, movement per turn
- ✅ `can_afford()` - Check if entity has resources
- ✅ `consume()` - Consume action resources
- ✅ `reset()` - Reset at start of turn

**Usage:**
```python
# Check if entity can attack
if entity.action_economy.can_afford(CostType.ACTIONS, 1):
    # Execute attack
    attack.apply()
    # Action economy automatically consumed on COMPLETION phase

# Reset at start of turn
entity.action_economy.reset()
```

---

## 4. Condition System

**File:** `external/dnd_engine/dnd/conditions.py`

**Built-in Conditions:**
- ✅ Blinded - Attack disadvantage, attackers have advantage
- ✅ Charmed - Can't attack charmer, charmer has advantage on social checks
- ✅ Dashing - Double movement speed
- ✅ Deafened - Auto-fail hearing checks
- ✅ And more...

**Architecture:**
```
Parent Condition
├── Applies base modifiers (on apply)
├── Creates Event Handlers (on apply)
│   └── Handlers trigger subcondition changes
└── Registers subconditions (children)
    └── Subconditions apply specific modifiers
```

**Key Insight:** Conditions apply modifiers through the **ModifiableValue system**, affecting:
- Attack rolls
- AC
- Skill checks
- Saving throws
- Damage
- Movement speed

---

## 5. Value Modification System

**File:** `external/dnd_engine/README.md:49-95`

All values (AC, attack bonus, skill checks) use **ModifiableValue** with four modification channels:

```
ModifiableValue
├── self_static         (always applies to self)
├── self_contextual     (applies to self based on context)
├── to_target_static    (always applies to targets)
└── to_target_contextual (applies to targets based on context)
```

**Example: Blinded Condition**
```python
# Attacker is blinded
attacker.equipment.attack_bonus.self_static.add_advantage_modifier(
    AdvantageModifier(name="Blinded", value=AdvantageStatus.DISADVANTAGE)
)

# Attackers targeting blinded entity have advantage
blinded_entity.equipment.ac_bonus.to_target_static.add_advantage_modifier(
    AdvantageModifier(name="Blinded", value=AdvantageStatus.ADVANTAGE)
)
```

---

## 6. What Our dnd_engine_wrapper Currently Does

**File:** `components/dnd_engine_wrapper.py`

**Current Implementation (Simplified):**
- ✅ `execute_attack()` - Manually calculates attack/damage
- ✅ `execute_skill_check()` - Manually rolls skill checks
- ✅ Entity syncing - Converts CharacterManager → dnd_engine Entities

**Problem:** Bypasses dnd_engine's Action framework, missing:
- ❌ Event system (no reaction support)
- ❌ Action economy tracking
- ❌ Condition system integration
- ❌ Prerequisite validation (range, line of sight)
- ❌ Cross-entity value propagation

---

## 7. Recommended Architecture Changes

### 7.1 Use dnd_engine Actions Directly

**Instead of:**
```python
# Current approach in dnd_engine_wrapper
result = self.dnd_wrapper.execute_attack(attacker_id, target_id, weapon)
```

**Do this:**
```python
# Use native dnd_engine Action
from dnd.actions import Attack, WeaponSlot

attack = Attack(
    source_entity_uuid=attacker.uuid,
    target_entity_uuid=target.uuid,
    weapon_slot=WeaponSlot.MAIN_HAND
)
attack_event = attack.apply()

# All mechanics handled by dnd_engine:
# - Range validation
# - Line of sight
# - Attack rolls with advantage/disadvantage
# - Critical hits
# - Damage with resistances
# - HP tracking
# - Action economy consumption
```

### 7.2 Leverage Condition System

**For Dodge, Dash, Disengage:**
```python
from dnd.conditions import Dashing
from dnd.core.base_conditions import Duration, DurationType

# Apply Dash condition
dash_condition = Dashing(
    source_entity_uuid=entity.uuid,
    target_entity_uuid=entity.uuid,
    duration=Duration(duration=1, duration_type=DurationType.TURNS)
)
dash_event = dash_condition.apply(parent_event=None)

# Movement speed now doubled automatically
```

### 7.3 Update CombatActionResolver

**New Design:**
```python
class CombatActionResolver:
    """Thin wrapper around dnd_engine Actions"""

    ACTION_HANDLERS = {
        "attack": {
            "action_class": Attack,
            "params": ["target_entity_uuid", "weapon_slot"]
        },
        "move": {
            "action_class": Move,
            "params": ["end_position"]
        },
        "dash": {
            "condition_class": Dashing,
            "duration": Duration(duration=1, duration_type=DurationType.TURNS)
        }
    }

    def resolve_action(self, action: Dict) -> Dict:
        action_type = action["action_type"]
        metadata = self.ACTION_HANDLERS[action_type]

        if "action_class" in metadata:
            # Use dnd_engine Action
            return self._resolve_via_action(action, metadata)
        elif "condition_class" in metadata:
            # Apply condition
            return self._resolve_via_condition(action, metadata)
```

---

## 8. Benefits of Using Native dnd_engine

### 8.1 Immediate Benefits
1. **Correct D&D mechanics** - dnd_engine implements official rules
2. **Reaction support** - Event system allows Shield, Counterspell, etc.
3. **Condition integration** - Blinded, Prone, etc. work automatically
4. **Action economy** - Proper tracking of actions/bonus actions/reactions
5. **Advantage/Disadvantage** - Properly stacks and resolves
6. **Critical hits** - Correct damage doubling on nat 20

### 8.2 Long-term Benefits
1. **Spellcasting support** - When dnd_engine adds spells, they work immediately
2. **Opportunity attacks** - Event system makes this straightforward
3. **Complex interactions** - Conditions affecting multiple values work correctly
4. **Extensibility** - Add custom conditions/actions following dnd_engine patterns

### 8.3 Code Reduction
- **Current plan:** ~400 lines for CombatActionResolver
- **With dnd_engine:** ~150 lines (thin wrapper)
- **Savings:** ~60% less code to maintain

---

## 9. Migration Path

### Phase 1: Update dnd_engine_wrapper
- Add `execute_action()` method that uses native Actions
- Keep legacy `execute_attack()` for backward compatibility
- Add `apply_condition()` method for Dodge/Dash/Disengage

### Phase 2: Update CombatActionResolver
- Change from custom resolvers to dnd_engine Action dispatch
- Map action types to dnd_engine Action classes
- Handle event → result conversion

### Phase 3: Add Condition Support
- Implement missing standard conditions (Dodge as condition)
- Integrate with turn management (reset action economy)
- Add condition duration tracking

### Phase 4: Enable Reactions
- Expose event system to combat UI
- Allow players to respond to enemy actions
- Implement Shield, Counterspell, etc.

---

## 10. Example: Full Combat Turn

```python
# Turn Start
entity.action_economy.reset()

# Player Action: Attack
from dnd.actions import Attack, WeaponSlot

attack = Attack(
    source_entity_uuid=player.uuid,
    target_entity_uuid=goblin.uuid,
    weapon_slot=WeaponSlot.MAIN_HAND
)

attack_event = attack.apply()

if attack_event.canceled:
    print(f"Attack failed: {attack_event.status_message}")
elif attack_event.attack_outcome == AttackOutcome.HIT:
    damage = sum(roll.total for roll in attack_event.damage_rolls)
    print(f"Hit! Dealt {damage} damage")
    print(f"Goblin HP: {goblin.health.get_total_hit_points()}")
else:
    print("Miss!")

# Action economy automatically consumed
print(f"Actions remaining: {player.action_economy.actions}")  # 0

# Player Bonus Action: Dash
from dnd.conditions import Dashing
from dnd.core.base_conditions import Duration, DurationType

dash = Dashing(
    source_entity_uuid=player.uuid,
    target_entity_uuid=player.uuid,
    duration=Duration(duration=1, duration_type=DurationType.TURNS)
)
dash_event = dash.apply()

# Movement speed doubled for this turn
base_speed = player.action_economy.movement.get_base_modifier().value
current_speed = player.action_economy.movement.normalized_score
print(f"Base speed: {base_speed}, Current speed: {current_speed}")  # e.g., 30, 60
```

---

## 11. Conclusion

**Recommendation:** Rewrite Combat Engine plan to use dnd_engine's native Action framework instead of custom action resolvers.

**Impact:**
- **Complexity:** Reduced by ~60%
- **Correctness:** Matches official D&D 5e rules
- **Maintainability:** dnd_engine handles rule updates
- **Features:** Reactions, conditions, spells come for free
- **Timeline:** Likely faster implementation (less code to write)

**Next Steps:**
1. Update COMBAT_ENGINE_IMPLEMENTATION_PLAN.md to use dnd_engine Actions
2. Extend dnd_engine_wrapper with Action execution support
3. Implement thin CombatActionResolver that dispatches to dnd_engine
4. Add standard D&D conditions (Dodge, Help, Disengage)
5. Integrate action economy reset with turn management

**Key Principle:** Don't reinvent D&D mechanics - use dnd_engine's battle-tested implementation.
