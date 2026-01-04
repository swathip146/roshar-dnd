# CharacterManager Roshar Combat Update

**Date:** 2026-01-03
**Purpose:** Combat Plan v4.0 Phase 3 preparation
**Status:** ✅ Complete and tested

---

## Summary

Updated `components/character_manager.py` to fully support Roshar-specific combat mechanics from Combat Plan v4.0. All changes are backward compatible with existing character data.

---

## Changes Made

### 1. New CharacterData Fields (lines 60-86)

Added 10 new fields to support Roshar combat mechanics:

#### Stormlight Tracking (lines 66-68)
```python
stormlight_current: int = 0      # Current spheres held
stormlight_capacity: int = 0     # Max spheres = Radiant Level × 2
```

#### Shardblade Tracking (lines 70-74)
```python
has_shardblade: bool = False
shardblade_summoned: bool = False
shardblade_type: Optional[str] = None     # "living" or "dead"
shardblade_name: Optional[str] = None
```

#### Shardplate Tracking (lines 76-80)
```python
has_shardplate: bool = False
shardplate_hp_current: int = 0
shardplate_hp_maximum: int = 0            # Typically Level × 5
shardplate_type: Optional[str] = None     # "living" or "dead"
```

#### Surgebinding Progression (lines 82-83)
```python
surgebinding_level: int = 0               # Derived from ideal_level
```

#### Legacy Field (line 86)
```python
investiture_points: Dict[str, int] = None # Legacy - use stormlight instead
```

### 2. Auto-Migration Logic (lines 228-249)

Added backward compatibility logic in `add_character()` method:

1. **Migrate investiture_points → stormlight** (lines 228-232)
   - If character has `investiture_points` but `stormlight_capacity == 0`
   - Copies `investiture_points["current"]` → `stormlight_current`
   - Copies `investiture_points["maximum"]` → `stormlight_capacity`

2. **Calculate stormlight capacity for Radiants** (lines 234-238)
   - If `radiant_order` is set and `stormlight_capacity == 0`
   - Sets `stormlight_capacity = level × 2`
   - Caps `stormlight_current` at new capacity

3. **Derive surgebinding_level from ideal_level** (lines 240-243)
   - If `surgebinding_level == 0` and `ideal_level > 0`
   - Sets `surgebinding_level = ideal_level`

4. **Calculate Shardplate HP** (lines 245-249)
   - If `has_shardplate == True` and `shardplate_hp_maximum == 0`
   - Sets `shardplate_hp_maximum = level × 5`
   - Sets `shardplate_hp_current = shardplate_hp_maximum`

### 3. New Methods (9 total)

#### Stormlight Management (4 methods, lines 1391-1497)

**`consume_stormlight(character_id, amount)`** (lines 1393-1414)
- Consumes Stormlight spheres for Surge use
- Validates sufficient Stormlight available
- Returns `bool` (success/failure)
- Logs consumption with emoji ⚡

**`replenish_stormlight(character_id, amount)`** (lines 1416-1442)
- Adds Stormlight spheres (from Highstorm, loot, etc.)
- Caps at `stormlight_capacity`
- Returns `bool` (success/failure)
- Logs amount gained with emoji ⚡

**`set_stormlight_capacity(character_id, capacity)`** (lines 1444-1465)
- Sets character's Stormlight capacity
- Typical value: `Level × 2` for Radiants
- Ensures `stormlight_current` doesn't exceed new capacity
- Returns `bool` (success/failure)
- Logs with emoji 💎

**`apply_passive_stormlight_healing(character_id, rest_type)`** (lines 1467-1497)
- Applies passive healing during short rest (1 HP per sphere)
- Caps healing at max HP
- Returns `int` (amount healed)
- Logs with emoji ✨

#### Shardblade Management (3 methods, lines 1499-1579)

**`summon_shardblade(character_id)`** (lines 1501-1530)
- Summons bonded Shardblade (1 Bonus Action in combat)
- Validates character has Shardblade
- Prevents double summoning
- Returns `bool` (success/failure)
- Logs with emoji ⚔️

**`dismiss_shardblade(character_id)`** (lines 1532-1553)
- Dismisses Shardblade to mist (free action)
- Returns `bool` (success/failure)
- Logs with emoji 💨

**`grant_shardblade(character_id, blade_type, blade_name)`** (lines 1555-1579)
- Grants Shardblade to character
- Typically at Third Ideal for living blades
- `blade_type`: "living" (bonded) or "dead" (ancient)
- Optional blade name
- Returns `bool` (success/failure)
- Logs with emoji ⚔️

#### Shardplate Management (3 methods, lines 1581-1679)

**`damage_shardplate(character_id, damage)`** (lines 1583-1617)
- Applies damage to Shardplate HP
- Detects if Shardplate shatters (HP reaches 0)
- Returns `Dict[str, Any]`:
  - `shattered`: `bool`
  - `hp_current`: `int`
  - `hp_maximum`: `int`
  - `damage_dealt`: `int`
- Logs with emoji 🛡️

**`repair_shardplate(character_id, amount)`** (lines 1619-1652)
- Repairs Shardplate HP (typically during Long Rest)
- `amount=None` → full repair
- `amount=int` → partial repair
- Returns `bool` (success/failure)
- Logs with emoji 🛡️

**`grant_shardplate(character_id, plate_type)`** (lines 1654-1679)
- Grants Shardplate to character
- Typically at Fourth Ideal for living plate
- `plate_type`: "living" (bonded) or "dead" (ancient)
- Auto-calculates HP: `Level × 5`
- Returns `bool` (success/failure)
- Logs with emoji 🛡️

---

## Testing

**Test File:** `tests/test_roshar_combat_integration.py`

**Test Results:** ✅ 6/6 test categories passed

### Test Coverage

1. **Stormlight Tracking** (5 tests)
   - Auto-calculation of capacity
   - Consumption validation
   - Over-consumption prevention
   - Replenishment with capping
   - Capacity updates

2. **Passive Stormlight Healing** (2 tests)
   - 1 HP per sphere healing
   - Healing capped at max HP

3. **Shardblade Mechanics** (4 tests)
   - Granting Shardblade with name
   - Summoning validation
   - Double-summoning prevention
   - Dismissal

4. **Shardplate Mechanics** (5 tests)
   - Granting with auto HP calculation
   - Damage tracking
   - Shattering detection
   - Partial repair
   - Full repair

5. **Backward Compatibility** (2 tests)
   - investiture_points migration
   - Auto-calculation for Radiants

6. **Surgebinding Level** (1 test)
   - Auto-derivation from ideal_level

**Test Output:**
```
✅ ALL ROSHAR COMBAT TESTS PASSED (6/6 test categories)
```

---

## Usage Examples

### Creating a Windrunner with Stormlight

```python
from components.character_manager import CharacterManager

manager = CharacterManager()

windrunner_data = {
    "character_id": "kaladin",
    "name": "Kaladin Stormblessed",
    "level": 5,
    "ability_scores": {"strength": 16, "dexterity": 14, ...},
    "character_class": "Radiant",
    "radiant_order": "Windrunner",
    "ideal_level": 3,
    "stormlight_current": 5,
    "stormlight_capacity": 10  # Level 5 × 2
}

char_id = manager.add_character(windrunner_data)

# Consume Stormlight for Lashing
manager.consume_stormlight(char_id, 2)  # Returns True, 3 remaining

# Replenish after Highstorm
manager.replenish_stormlight(char_id, 5)  # Returns True, capped at 10
```

### Granting Third Ideal Shardblade

```python
# Radiant speaks Third Ideal, unlocks Shardblade
manager.grant_shardblade(char_id, blade_type="living", blade_name="Sylspear")

# In combat: summon blade (1 Bonus Action)
manager.summon_shardblade(char_id)  # Returns True

# Check if summoned
character = manager.characters[char_id]
if character.shardblade_summoned:
    print("Shardblade is ready for soul damage!")

# After combat: dismiss blade
manager.dismiss_shardblade(char_id)
```

### Shardplate HP Tracking

```python
# Radiant speaks Fourth Ideal, unlocks Shardplate
manager.grant_shardplate(char_id, plate_type="living")
# Auto-calculates HP: Level 15 × 5 = 75 HP

# During combat: take damage
result = manager.damage_shardplate(char_id, 30)
# result = {"shattered": False, "hp_current": 45, "hp_maximum": 75, "damage_dealt": 30}

# Check if shattered
if result["shattered"]:
    print("Shardplate has shattered! AC reduced!")

# During Long Rest: repair with Stormlight
manager.repair_shardplate(char_id, amount=None)  # Full repair to 75 HP
```

### Backward Compatibility (Old Characters)

```python
# Old character with investiture_points
old_radiant_data = {
    "character_id": "renarin",
    "name": "Renarin Kholin",
    "level": 6,
    "character_class": "Radiant",
    "radiant_order": "Truthwatcher",
    "ideal_level": 2,
    "investiture_points": {"current": 8, "maximum": 12}  # Old format
}

char_id = manager.add_character(old_radiant_data)

# Auto-migrated to new format
character = manager.characters[char_id]
print(f"Stormlight: {character.stormlight_current}/{character.stormlight_capacity}")
# Output: "Stormlight: 8/12"

# Can now use new methods
manager.consume_stormlight(char_id, 2)  # Works seamlessly
```

---

## Integration with Combat Plan v4.0

These changes enable the following Combat Plan v4.0 requirements:

### Phase 3: CombatSessionManager

**`_character_meets_requirements()` method** (lines 2358-2387 of combat plan):
```python
def _character_meets_requirements(self, character: CharacterData, action_metadata: Dict) -> bool:
    """Check character requirements using new CharacterManager fields"""

    # Check Stormlight availability
    if action_metadata.get("stormlight_cost", 0) > 0:
        if character.stormlight_current < action_metadata["stormlight_cost"]:
            return False

    # Check Shardblade requirements
    if action_metadata.get("requires") == "shardblade_summoned":
        if not character.shardblade_summoned:
            return False

    # Check Radiant Order
    if action_metadata.get("requires_order"):
        if character.radiant_order != action_metadata["requires_order"]:
            return False

    # Check Surgebinding level
    if action_metadata.get("min_surgebinding_level", 0) > 0:
        if character.surgebinding_level < action_metadata["min_surgebinding_level"]:
            return False

    return True
```

### ACTION_REGISTRY Integration

New fields enable metadata-driven validation:

```python
ACTION_REGISTRY = {
    "basic_lashing": {
        "type": "roshar_surge",
        "surge_type": "Gravitation",
        "cost_type": "actions",
        "cost": 1,
        "stormlight_cost": 1,           # ✅ Validated via stormlight_current
        "requires_order": "Windrunner",  # ✅ Validated via radiant_order
        "min_surgebinding_level": 1      # ✅ Validated via surgebinding_level
    },

    "shardblade_attack": {
        "type": "roshar_equipment",
        "cost_type": "actions",
        "cost": 1,
        "requires": "shardblade_summoned"  # ✅ Validated via shardblade_summoned
    }
}
```

---

## Compatibility Notes

### Backward Compatibility

- ✅ **Existing characters work unchanged** - auto-migration handles old data
- ✅ **investiture_points still supported** - migrated to stormlight on load
- ✅ **No breaking changes** - all new fields have default values

### Forward Compatibility

- ✅ **Ready for Phase 3 implementation** - all required fields present
- ✅ **Extensible** - can add more Roshar mechanics without breaking changes
- ✅ **Type-safe** - all fields properly typed with TypedDict

---

## Documentation References

- **Master Plan:** `docs/COMBAT_ENGINE_IMPLEMENTATION_PLAN.md` (Version 4.0)
- **Optimization Analysis:** `docs/COMBAT_PLAN_METHOD_OPTIMIZATION_ANALYSIS.md`
- **Roshar Rules:** `docs/ROSHAR_COMBAT_MECHANICS_INTEGRATION.md`
- **Readiness Report:** `docs/COMBAT_SYSTEM_READINESS_REPORT.md`

---

## Next Steps

With CharacterManager fully updated, Phase 3 implementation can proceed:

1. ✅ **CharacterManager Roshar Support** - COMPLETE
2. ⏭️ **Implement CombatSessionManager** - Use updated `_character_meets_requirements()`
3. ⏭️ **Implement roshar_actions.py** - Define Surge actions using new fields
4. ⏭️ **Implement CombatActionResolver** - Resolve Roshar actions via ACTION_REGISTRY
5. ⏭️ **Integration Testing** - Full combat session with Roshar mechanics

**Status:** ✅ CharacterManager ready for Combat Plan v4.0 Phase 3 implementation

---

*Last Updated: 2026-01-03*
*Test Status: 6/6 categories passing*
*Version: Combat Plan v4.0*
