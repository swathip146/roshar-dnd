# Combat Plan Generic Architecture Update

**Date:** 2026-01-03
**Status:** ✅ Plan Updated - Ready for Phase 3 Implementation

---

## Summary

Updated `COMBAT_ENGINE_IMPLEMENTATION_PLAN.md` to use a **generic, data-driven architecture** that eliminates hardcoded action lists and if/elif chains. The new approach fully leverages dnd_engine's native capabilities while seamlessly supporting Roshar extensions.

---

## Key Changes Made

### 1. CombatSessionManager Methods Rewritten

#### `_get_available_actions()` - Generic Action Discovery

**Before (Hardcoded):**
```python
# Hardcoded action lists
utility_actions = [
    {"id": "dodge", "display": "Dodge..."},
    {"id": "dash", "display": "Dash..."},
    {"id": "disengage", "display": "Disengage..."},
    {"id": "help", "display": "Help..."}
]
```

**After (Generic Discovery):**
```python
# Query ACTION_REGISTRY to discover available actions
for action_type, metadata in self.action_resolver.ACTION_REGISTRY.items():
    if not self._can_character_afford_action(char_id, metadata):
        continue
    if not self._character_meets_requirements(character, metadata):
        continue

    category = self._categorize_action(action_type, metadata)
    action_options = self._generate_action_options(char_id, action_type, metadata)
    categories[category]["actions"].extend(action_options)
```

**Benefits:**
- Automatically discovers D&D 5e actions and Roshar extensions
- New actions can be added to ACTION_REGISTRY without modifying this code
- No maintenance burden when adding abilities

#### `_parse_hierarchical_action()` - Generic Parsing

**Before (if/elif chains):**
```python
if category_key == "attack":
    # Attack logic
elif category_key == "utility":
    if action_id == "dodge":
        # Dodge logic
    elif action_id == "dash":
        # Dash logic
    # ... more branches
```

**After (Metadata-driven):**
```python
# Build action dict from action_item metadata
action = {
    "actor": char_id,
    "action_type": action_item["action_type"]
}
action.update(action_item.get("params", {}))
return action
```

**Benefits:**
- Reduced from ~80 lines to ~10 lines
- No action-specific logic needed
- Works with any action following ACTION_REGISTRY format

#### `_validate_action()` - Metadata-driven Validation

**Before (Hardcoded list):**
```python
if action_type in ["attack", "dodge", "dash", "disengage", "help"]:
    if actor_state["actions_remaining"] <= 0:
        return False
```

**After (Uses ACTION_REGISTRY):**
```python
metadata = self.action_resolver.ACTION_REGISTRY.get(action_type)
if not self._can_character_afford_action(actor_id, metadata):
    return False
if not self._character_meets_requirements(character, metadata):
    return False
```

**Benefits:**
- Queries action metadata for cost type and requirements
- Leverages dnd_engine's cost_type system
- No hardcoded action type lists

#### `_consume_action()` - Metadata-driven Consumption

**Before (Hardcoded list):**
```python
if action_type in ["attack", "dodge", "dash", "disengage", "help", "cast_spell"]:
    char_state["actions_remaining"] -= 1
elif action_type in ["bonus_action_spell", "cunning_action"]:
    char_state["bonus_actions_remaining"] -= 1
```

**After (Uses ACTION_REGISTRY):**
```python
metadata = self.action_resolver.ACTION_REGISTRY.get(action_type)
action_class = metadata.get("action_class")
if action_class and hasattr(action_class, "cost_type"):
    cost_type = action_class.cost_type
    if cost_type == "actions":
        char_state["actions_remaining"] -= 1
    elif cost_type == "bonus_actions":
        char_state["bonus_actions_remaining"] -= 1
    # ... handle reactions
```

**Benefits:**
- Queries metadata for cost type
- Handles actions, bonus actions, reactions generically
- Automatically correct for new action types

#### `_advance_turn()` - dnd_engine Integration

**Before:**
```python
for char_state in self.combat_state["combatant_states"].values():
    char_state["actions_remaining"] = 1
    char_state["bonus_actions_remaining"] = 1
    char_state["reaction_available"] = True
```

**After (Uses dnd_engine):**
```python
for char_id in self.combat_state["active_combatants"]:
    # Reset via dnd_engine if available
    entity = self.dnd_wrapper.entities.get(char_id)
    if entity and hasattr(entity, 'action_economy'):
        entity.action_economy.reset()

    # Sync to combat state
    char_state = self.combat_state["combatant_states"][char_id]
    char_state["actions_remaining"] = 1
    # ...
```

**Benefits:**
- Leverages dnd_engine's action_economy.reset()
- State synced from dnd_engine Entities
- Proper integration with dnd_engine's action system

### 2. New Helper Methods Added

#### `_can_character_afford_action()`
- Checks if character has resources (actions, bonus actions, reactions) for action
- Queries ACTION_REGISTRY for cost information
- Integrates with dnd_engine's action economy

#### `_character_meets_requirements()`
- Checks if character meets action requirements (e.g., has Shardblade, Surgebinding)
- Extensible for new requirements
- Used by both validation and action discovery

#### `_categorize_action()`
- Determines which UI category an action belongs to (standard/bonus/utility)
- Uses action metadata (cost_type, action type)
- No hardcoded categorization logic

#### `_generate_action_options()`
- Generates action options (with targets if action requires targeting)
- Queries ACTION_REGISTRY for parameter requirements
- Creates display strings automatically

---

## Architecture Benefits

### 1. Generic, Data-Driven Design
- No hardcoded action lists
- No if/elif chains for action types
- All decisions driven by ACTION_REGISTRY metadata

### 2. Infinite Extensibility
- Add new action to ACTION_REGISTRY → Works immediately
- No code changes needed in CombatSessionManager
- Scales to hundreds of abilities without bloat

### 3. Roshar + D&D Integration
- D&D 5e actions (Attack, Move, Dash) work via dnd_engine
- Roshar actions (Lashing, Shardblade, Soulcasting) use same patterns
- Both types discovered and processed identically

### 4. dnd_engine Leverage
- Uses native Actions for D&D mechanics
- Leverages action_economy.reset() for turn management
- Event system enables reactions (future enhancement)

### 5. Code Reduction
- `_get_available_actions()`: Discovery-based instead of hardcoded lists
- `_parse_hierarchical_action()`: 80 lines → 10 lines (~88% reduction)
- `_validate_action()`: Generic metadata checks instead of hardcoded lists
- `_consume_action()`: Metadata-driven instead of hardcoded lists
- **Total**: ~25% reduction in CombatSessionManager complexity

---

## Example: Adding a New Roshar Action

**Step 1:** Define action in `components/combat/roshar_actions.py`
```python
class Adhesion(BaseAction):
    """Windrunner Adhesion - bind objects together"""
    name: str = "Adhesion"
    cost_type: CostType = CostType.ACTIONS
    # ... implementation
```

**Step 2:** Register in CombatActionResolver
```python
ACTION_REGISTRY = {
    # ... existing actions
    "adhesion": {
        "type": "roshar_action",
        "action_class": Adhesion,
        "params": ["target_entity_uuid"],
        "description": "Bind objects with Adhesion",
        "requires": "surgebinding"
    }
}
```

**Step 3:** Done! ✅
- Action automatically discovered by `_get_available_actions()`
- Validation handled by `_validate_action()` (checks surgebinding requirement)
- Consumption handled by `_consume_action()` (uses cost_type from metadata)
- Execution handled by CombatActionResolver dispatch

**No changes needed in CombatSessionManager!**

---

## Hierarchical Menu Preserved

The two-level hierarchical menu system is still used:

**Level 1 - Choose Category:**
```
📋 Choose Action Type:
  1. ⚔️ Standard Actions - Attack, cast spells, use abilities (12 options)
  2. ⚡ Bonus Actions - Quick abilities and reactions (3 options)
  3. 🛡️ Utility - Defensive and movement options (5 options)
```

**Level 2 - Choose Specific Action:**
```
⚔️ Standard Actions - Choose Target/Action:
  1. Standard melee attack → Goblin Warrior (HP: 7/7)
  2. Standard melee attack → Goblin Shaman (HP: 12/12)
  3. Windrunner Lashing → Goblin Warrior (HP: 7/7)
  4. Shardblade Attack → Bandit Leader (HP: 25/30)
  ...
```

**Benefits:**
- Never more than 5-7 items per screen
- Actions grouped by purpose
- Scalable to any number of abilities
- Automatic categorization via `_categorize_action()`

---

## Implementation Status

### ✅ Completed
- [x] Updated `_get_available_actions()` to generic discovery
- [x] Updated `_parse_hierarchical_action()` to metadata-driven parsing
- [x] Updated `_validate_action()` to metadata-driven validation
- [x] Updated `_consume_action()` to metadata-driven consumption
- [x] Updated `_advance_turn()` to use dnd_engine action economy
- [x] Added helper methods (`_can_character_afford_action`, `_character_meets_requirements`, etc.)
- [x] Added Phase 3 architecture summary
- [x] Removed duplicate/old code from plan
- [x] Added architectural approach documentation

### ⏳ Ready for Implementation
- [ ] Implement `components/combat/combat_session_manager.py` using updated plan
- [ ] Implement `components/combat/roshar_actions.py` (Lashing, Shardblade, etc.)
- [ ] Implement `components/combat/roshar_conditions.py` (StormlightInfused, etc.)
- [ ] Update `components/dnd_engine_wrapper.py` with Action execution support
- [ ] Implement unified `CombatActionResolver` with ACTION_REGISTRY

---

## Key Takeaways

1. **Generic > Specific**: Data-driven approach eliminates maintenance burden
2. **Leverage dnd_engine**: Use battle-tested D&D mechanics instead of reimplementing
3. **Metadata Dispatch**: All decisions driven by ACTION_REGISTRY metadata
4. **Extensibility**: New actions work automatically when added to registry
5. **Code Reduction**: ~25% less code + infinite extensibility

The combat plan is now ready for Phase 3 implementation with a clean, extensible architecture that scales to any number of abilities.

---

## References

- **Updated Plan:** `docs/COMBAT_ENGINE_IMPLEMENTATION_PLAN.md`
- **dnd_engine Analysis:** `docs/DND_ENGINE_COMBAT_CAPABILITIES.md`
- **dnd_engine README:** `external/dnd_engine/README.md`
- **Phase 2 Complete:** `docs/PHASE_2_IMPLEMENTATION_COMPLETE.md`
