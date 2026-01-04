# Combat Plan NPC Integration - Critical Gaps Analysis

**Date:** 2026-01-03
**Updated:** 2026-01-03 (JSON conversion complete)
**Status:** 🟡 PARTIALLY RESOLVED - JSON Files Available, Loader Component Still Needed

---

## Executive Summary

The Combat Engine Implementation Plan (Phase 2) has **critical mismatches** between:
1. How NPCs are stored in campaign configuration
2. How the plan expects to load predefined NPCs
3. What data is available in NPC definition files

**Key Finding**: The plan assumes `campaign_npc['stats']` exists with full D&D character data, but campaign NPCs only have basic metadata (name, role, description, motivation). Full NPC stats were in separate `.txt` files in `data/players/`.

**✅ UPDATE 2026-01-03:** Herald NPC stat files have been **converted to JSON format** matching CharacterData schema. See section "JSON Format Resolution" below.

---

## Current NPC Data Architecture

### 1. Campaign NPC Structure (JSON)
**File:** `data/current_campaign/shards_of_honor.json`

```json
{
  "key_npcs": [
    {
      "name": "Kalak the Herald",
      "role": "Herald Mentor",
      "description": "One of the ten Heralds...",
      "motivation": "Seeks to train new Knights Radiant..."
    }
  ]
}
```

**Fields Available:**
- ✅ `name` - NPC name
- ✅ `role` - NPC role/title
- ✅ `description` - Brief description
- ✅ `motivation` - NPC motivation
- ❌ `stats` - **DOES NOT EXIST**

### 2. NPC Stat Files (NOW JSON ✅)
**Original Files:** `data/players/*.txt` (kalak_herald.txt, nale_herald.txt, etc.)
**✅ Converted Files:** `data/players/*.json` (kalak_herald.json, nale_herald.json)

**Contains Full D&D Character Data:**
- ✅ Character name, race, class, level
- ✅ All 6 ability scores + modifiers
- ✅ Hit points (current/max/temporary dict)
- ✅ Armor class
- ✅ Proficiency bonus
- ✅ Skills, equipment, features
- ✅ Personality, backstory
- ✅ Cosmere-specific attributes (investiture, surges, spren)

**✅ FORMAT RESOLVED:** Now available in CharacterData-compliant JSON format
**Original Format:** Structured text (`.txt` files - still available)
**New Format:** JSON dict ready for `json.load()` → `CharacterManager.add_npc()`

### 3. CampaignConfig.key_npcs
**File:** `components/campaign_config.py:282-328`

```python
@staticmethod
def _extract_npcs(data: Dict[str, Any]) -> List[Dict[str, str]]:
    """Extract key NPCs from campaign data"""
    # Returns list of dicts with only:
    # - name
    # - role
    # - description
```

**Returns:** `List[Dict[str, str]]` with basic metadata only

---

## Combat Plan Assumptions (INCORRECT)

### From COMBAT_ENGINE_IMPLEMENTATION_PLAN.md:1143-1168

```python
def _load_predefined_npcs(self, enemies: List[Dict]) -> List[str]:
    """
    Load predefined NPC stats from campaign configuration.

    Checks:
    1. CampaignConfig.key_npcs for name matches
    2. If enemy is_predefined=True
    """
    campaign_npcs = self.game_engine.campaign_config.key_npcs

    for campaign_npc in campaign_npcs:
        if 'stats' in campaign_npc:  # ❌ THIS NEVER EXISTS
            # Add to CharacterManager
            char_id = self.character_manager.add_npc(campaign_npc['stats'])
            # ...
```

**Problem:** The plan assumes `campaign_npc['stats']` exists, but it doesn't.

---

## Actual NPC Loading in Codebase

### game_initialization.py Does NOT Load NPC Stats

**Lines 178-256:** Campaign initialization
- ✅ Loads CampaignConfig (basic NPC metadata only)
- ✅ Loads player character from hardcoded selection
- ❌ Does NOT load NPC stat files from `data/players/`
- ❌ Does NOT parse `.txt` files into CharacterData format
- ❌ NPCs remain unavailable for combat initialization

### NPC Controller Agent Does NOT Use Full Stats

**File:** `agents/npc_controller_agent.py`

**Purpose:** NPC dialogue and behavior only
- Generates NPC responses to player actions
- Tracks NPC memory and attitude
- Does NOT manage NPC combat stats
- Does NOT integrate with CharacterManager

**Tools:**
- `generate_npc_response()` - dialogue only
- `update_npc_memory()` - memory tracking
- `assess_attitude_change()` - relationship tracking
- `determine_npc_action()` - action suggestions

**Missing:**
- ❌ No integration with CharacterManager
- ❌ No loading of NPC stats from files
- ❌ No conversion of `.txt` files to CharacterData
- ❌ No combat stat management

---

## Critical Gaps Identified

### ✅ Gap 1: NPC Stat File Format - RESOLVED
~~**Problem:** No system to load NPC stats from `data/players/*.txt` files~~

**✅ RESOLUTION (2026-01-03):**
- Herald NPC files converted to JSON format
- Files now match CharacterData schema exactly
- Can be loaded with simple `json.load()`
- Ready for `CharacterManager.add_npc()`

**Files Converted:**
- ✅ `data/players/kalak_herald.json` - 400 HP, Level 20, complete stats
- ✅ `data/players/nale_herald.json` - 380 HP, Level 20, complete stats

**Format Validation:**
- ✅ All required CharacterData fields present
- ✅ Hit points: `{current, maximum, temporary}` structure
- ✅ Skills: `{skill_name: bool}` dict format
- ✅ Field name: `character_class` (not `class`)
- ✅ All 6 ability scores present
- ✅ Cosmere attributes included

**Next Required:**
- ⬜ Create NPCStatLoader to load JSON files
- ⬜ No parsing needed - direct JSON load

### ~~Gap 2: NPC File Format Mismatch - RESOLVED~~
~~**Problem:** `.txt` files use structured text, not CharacterData dict format~~

**✅ RESOLUTION:** JSON files now available in correct format

**Before:**
```
CHARACTER: Kalak the Herald
BASIC INFORMATION:
Name: Kalak
Race: Herald
...
```

**After:**
```json
{
  "character_id": "kalak_herald",
  "name": "Kalak",
  "race": "Herald",
  "character_class": "Herald",
  "level": 20,
  "ability_scores": {
    "strength": 22,
    "dexterity": 18,
    ...
  },
  "hit_points": {"current": 400, "maximum": 400, "temporary": 0},
  ...
}
```

**Result:** No parser needed - direct JSON loading

### Gap 3: Campaign NPC Linking
**Problem:** No link between campaign NPC metadata and stat files

**Current State:**
- Campaign has `"Kalak the Herald"` with basic info
- Stat file is `kalak_herald.txt`
- No automatic linking mechanism

**Required:**
- Naming convention to map campaign NPC → stat file
- Fallback if stat file not found
- Registry of available NPC stat files

### Gap 4: NPC Availability Check
**Problem:** No way to check if NPC stat file exists before combat

**Required:**
- NPC registry loaded at game initialization
- `has_npc_stats(npc_name)` method
- Graceful fallback to generated stats if unavailable

### Gap 5: NPC Controller Integration
**Problem:** NPC Controller Agent only handles dialogue, not stats

**Current Scope:** Dialogue and behavior only
**Missing:** Combat stat management

**Required:**
- Decide if NPC Controller should manage stats
- OR create separate NPC Stat Manager component
- OR integrate with CharacterManager directly

---

## Recommendations

### Phase 2 Must Include:

#### 1. **NPC Stat File Loader** (SIMPLIFIED - NEW COMPONENT)
**File:** `components/combat/npc_stat_loader.py`

**✅ Simplified Requirements (JSON available):**
- Load JSON files from `data/players/`
- ~~No parsing needed~~ - use `json.load()`
- Validate required fields present
- Case-insensitive name lookup

**Methods:**
```python
import json
import os
from typing import Dict, Any, Optional

class NPCStatLoader:
    def __init__(self, npc_directory: str = "data/players/"):
        """Initialize NPC loader with directory of JSON files"""
        self.npc_directory = npc_directory
        self.npc_registry = {}
        self._load_all_npcs()

    def _load_all_npcs(self):
        """Load all JSON NPC files into registry"""
        for filename in os.listdir(self.npc_directory):
            if filename.endswith('.json') and filename not in ['aggi.json']:  # Skip non-NPC files
                filepath = os.path.join(self.npc_directory, filename)
                try:
                    with open(filepath, 'r') as f:
                        npc_data = json.load(f)

                    # Register by name (case-insensitive)
                    npc_name = npc_data.get('name', '').lower()
                    if npc_name:
                        self.npc_registry[npc_name] = npc_data

                except Exception as e:
                    logger.warning(f"Failed to load NPC file {filename}: {e}")

    def get_npc_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get NPC stats by name (case-insensitive)"""
        name_lower = name.lower()

        # Exact match
        if name_lower in self.npc_registry:
            return self.npc_registry[name_lower].copy()

        # Partial match (e.g., "Kalak" matches "Kalak the Herald")
        for npc_name, npc_data in self.npc_registry.items():
            if name_lower in npc_name or npc_name in name_lower:
                return npc_data.copy()

        return None

    def has_npc(self, name: str) -> bool:
        """Check if NPC exists in registry"""
        return self.get_npc_by_name(name) is not None

    def list_available_npcs(self) -> List[str]:
        """Get list of all available NPC names"""
        return [npc_data['name'] for npc_data in self.npc_registry.values()]
```

**Estimated Implementation Time:** 1-2 hours (greatly simplified from 2-3 hours)

#### 2. **NPC Registry Initialization** (UPDATE game_initialization.py)
**Add to GameInitializationSystem.initialize_game():**

```python
# After campaign config loading (line ~195):
# Load NPC stat files
npc_registry = NPCStatLoader()
available_npcs = npc_registry.load_all_npcs("data/players/")
config.npc_registry = npc_registry

logger.info(f"   🎭 Loaded {len(available_npcs)} predefined NPCs")
```

#### 3. **Update CombatInitializer._load_predefined_npcs()** (FIX PLAN)
**Change from:**
```python
if 'stats' in campaign_npc:  # ❌ Never exists
    char_id = self.character_manager.add_npc(campaign_npc['stats'])
```

**✅ Change to (simplified with JSON):**
```python
# Try to load from NPC registry (loads JSON file)
npc_stats = self.npc_registry.get_npc_by_name(campaign_npc['name'])
if npc_stats:
    # Direct load - no parsing needed, already CharacterData format
    char_id = self.character_manager.add_npc(npc_stats)
    predefined_ids.append(char_id)
    self.logger.info(f"✅ Loaded predefined NPC: {npc_stats['name']} ({char_id})")
    enemy['processed'] = True
else:
    self.logger.warning(f"⚠️ No JSON file for {campaign_npc['name']}, will generate")
    enemy['is_predefined'] = False  # Fallback to generation
```

**Result:** Clean, simple code with no parsing overhead

#### 4. **Update Combat Plan Documentation**
**Add Phase 2 Task:**
- Task 2.1: Create NPCStatLoader component (JSON loading only)
- ~~Task 2.2: Parse NPC .txt files to CharacterData~~ ✅ Already done
- Task 2.3: Integrate NPC registry with game initialization
- Task 2.4: Update _load_predefined_npcs() to use registry

---

## ✅ JSON Format Resolution (2026-01-03)

### Files Created

**Herald NPC JSON Files:**
1. `data/players/kalak_herald.json`
   - Converted from `kalak_herald.txt`
   - 400 HP, AC 22, Level 20
   - 10 skills, 13 features, 8 equipment items
   - Full Cosmere attributes

2. `data/players/nale_herald.json`
   - Converted from `nale_herald.txt`
   - 380 HP, AC 24, Level 20
   - 10 skills, 14 features, 10 equipment items
   - Full Cosmere attributes

### Validation Completed

**Format Compliance:**
```python
# All checks passed:
✅ character_id field present
✅ name, race, character_class, level
✅ ability_scores: all 6 abilities present
✅ hit_points: {current, maximum, temporary}
✅ skills: dict format {skill_name: bool}
✅ equipment: list of items
✅ features: list of abilities
✅ personality_traits, ideals, bonds, flaws
✅ backstory included
✅ Cosmere fields: investiture_points, spren, surges_known
```

### Impact on Implementation

**Before JSON Conversion:**
- ⚠️ Estimated 4-6 hours for NPC loading infrastructure
- Needed complex .txt parser
- Regex patterns for field extraction
- Manual validation and type conversion

**After JSON Conversion:**
- ✅ Estimated 1-2 hours for simple JSON loader
- Just `json.load()` - no parsing
- Automatic type validation from JSON
- Direct `CharacterManager.add_npc()` compatibility

**Time Savings:** 3-4 hours of development + testing

---

## ~~File Format Parsing Requirements~~ - NO LONGER NEEDED

~~### Fields to Extract from .txt Files:~~ ✅ JSON format handles all fields

**✅ JSON files include all required fields automatically:**
- Basic Information (name, race, class, level, background)
- Ability Scores (all 6 with proper structure)
- Combat Statistics (HP dict, AC, proficiency)
- Skills (dict format)
- Equipment (list)
- Cosmere Attributes (investiture, spren, surges)
- Personality (traits, ideals, bonds, flaws)
- Backstory

---

## Testing Requirements

### Unit Tests Needed:

1. **test_npc_stat_loader.py** (Simplified)
   - ✅ Load kalak_herald.json successfully
   - ✅ Load nale_herald.json successfully
   - ✅ Validate CharacterData format
   - ✅ Case-insensitive name lookup ("Kalak" matches "Kalak the Herald")
   - ✅ Partial name matching
   - ✅ Handle missing JSON files gracefully
   - ~~✅ Parse .txt files~~ - No longer needed
   - ~~✅ Convert to CharacterData format~~ - Already in correct format

2. **test_npc_registry_integration.py**
   - ✅ Load all NPCs from data/players/
   - ✅ Find NPC by campaign name
   - ✅ Skip non-NPC JSON files (e.g., aggi.json for players)
   - ✅ List available NPCs

3. **test_combat_initializer_npc_loading.py**
   - ✅ Load predefined NPC (Kalak) from JSON
   - ✅ Load predefined NPC (Nale) from JSON
   - ✅ Fallback to generation if no JSON file
   - ✅ Add to CharacterManager correctly
   - ✅ Verify CharacterData structure

**Estimated Testing Time:** 1-2 hours (reduced from 2-3 hours)

---

## Implementation Priority

### Critical Path (Blocks Phase 2):
1. ~~✅ **NPCStatLoader component**~~ - Simplified, just loads JSON
2. ✅ **Update game_initialization.py** - Load NPC registry at startup
3. ✅ **Update Combat Plan** - Fix _load_predefined_npcs() implementation

**✅ Gap 1 & 2 RESOLVED:** JSON files eliminate parsing complexity

### Optional Enhancements:
4. ⭐ Convert remaining NPC .txt files to JSON (aggi.txt, kali.txt)
5. ⭐ NPC Controller integration with stat management
6. ⭐ Hot-reload NPC stats during development
7. ⭐ Automated .txt → JSON converter for future NPCs

---

## Updated Phase 2 Task List

### ~~Original Plan:~~
~~1. Create CombatInitializer class~~
~~2. Implement scenario parsing~~
~~3. Roll initiative~~
~~4. Create combat state~~

### ✅ Updated Plan (with JSON NPC files):
1. **Create NPCStatLoader component** ← SIMPLIFIED (JSON only, 1-2 hours)
2. **Integrate NPC registry with game initialization** ← NEW (30 min)
3. Create CombatInitializer class
4. Implement scenario parsing (enemy extraction)
5. **Update _load_predefined_npcs() to use registry** ← SIMPLIFIED
6. Implement _generate_undefined_npcs()
7. Roll initiative
8. Create combat state

**Time Reduction:** ~3-4 hours saved by JSON conversion

---

## Conclusion

**Status:** 🟡 **PARTIALLY RESOLVED** - JSON format available, loader component still needed

**Major Progress:**
- ✅ JSON files created and validated
- ✅ Format parsing eliminated
- ✅ CharacterData compliance verified
- ✅ 3-4 hour time savings

**Remaining Work:**
- ⬜ Create simple NPCStatLoader (1-2 hours)
- ⬜ Update game_initialization.py (30 min)
- ⬜ Update Combat Plan documentation (30 min)

**Impact:** Phase 2 can now be implemented with **significantly reduced complexity**

**Action Required:**
1. ~~Create NPCStatLoader component~~ (simplified to JSON loader)
2. Update game initialization to load NPC registry
3. Revise Combat Plan _load_predefined_npcs() implementation
4. Add tests for NPC loading (simplified test suite)

**✅ Estimated Total Work:** 2-3 hours (down from 4-6 hours)

---

## Next Steps

1. ✅ **Create gap analysis document** - DONE
2. ✅ **Convert Herald .txt files to JSON** - DONE (kalak_herald.json, nale_herald.json)
3. ⬜ Create NPCStatLoader component (simplified)
4. ⬜ Write tests for NPC JSON loading
5. ⬜ Update game_initialization.py
6. ⬜ Update COMBAT_ENGINE_IMPLEMENTATION_PLAN.md
7. ⬜ Implement Phase 2 with corrected NPC loading

---

## References

**Related Documentation:**
- `docs/NPC_JSON_CONVERSION_COMPLETE.md` - Detailed conversion report
- `docs/COMBAT_ENGINE_IMPLEMENTATION_PLAN.md` - Phase 2 plan (needs update)
- `docs/PHASE_1_IMPLEMENTATION_COMPLETE.md` - Phase 1 completion report

**NPC Files:**
- `data/players/kalak_herald.json` - Kalak Herald stats (JSON)
- `data/players/nale_herald.json` - Nale Herald stats (JSON)
- `data/players/kalak_herald.txt` - Original format (retained)
- `data/players/nale_herald.txt` - Original format (retained)
- `data/aggi.json` - Format reference
