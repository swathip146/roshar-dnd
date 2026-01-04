# NPC JSON Conversion - Herald Stat Files

**Date:** 2026-01-03
**Status:** ✅ COMPLETE

---

## Summary

Successfully converted Herald NPC stat files from structured `.txt` format to JSON format matching the CharacterData schema used in the game.

---

## Files Created

### 1. kalak_herald.json
**Source:** `data/players/kalak_herald.txt` (114 lines)
**Output:** `data/players/kalak_herald.json` (valid JSON)

**Character Details:**
- **Name:** Kalak
- **Race:** Herald
- **Class:** Herald (Level 20)
- **Background:** Herald Mentor
- **HP:** 400 (current/max), AC: 22
- **Ability Scores:** STR 22, DEX 18, CON 24, INT 20, WIS 16, CHA 19
- **Skills:** 10 skills with 3 expertise (athletics, history, religion)
- **Equipment:** 8 legendary items including Kalak's Honorblade
- **Features:** 13 Herald-level abilities
- **Cosmere Attributes:** 100 investiture points, Honorblade bond, 4 surges

### 2. nale_herald.json
**Source:** `data/players/nale_herald.txt` (120 lines)
**Output:** `data/players/nale_herald.json` (valid JSON)

**Character Details:**
- **Name:** Nale
- **Race:** Herald
- **Class:** Herald (Level 20)
- **Background:** Conflicted Herald
- **HP:** 380 (current/max), AC: 24
- **Ability Scores:** STR 18, DEX 24, CON 22, INT 23, WIS 14, CHA 17
- **Skills:** 10 skills with 5 expertise (deception, history, insight, intimidation, investigation)
- **Equipment:** 10 judicial items including Nale's Honorblade
- **Features:** 14 Herald-level abilities
- **Cosmere Attributes:** 100 investiture points, Honorblade bond, Division and Abrasion surges

---

## Format Validation

### ✅ CharacterData Schema Compliance

Both JSON files match the required CharacterData format:

**Required Fields:**
- ✅ `character_id` - Unique identifier
- ✅ `name` - Character name
- ✅ `race` - Character race
- ✅ `character_class` - NOT "class" (correct field name)
- ✅ `level` - Character level
- ✅ `background` - Character background
- ✅ `ability_scores` - Dict with all 6 abilities
- ✅ `hit_points` - Dict with current/maximum/temporary
- ✅ `armor_class` - Integer AC value
- ✅ `proficiency_bonus` - Integer proficiency
- ✅ `skills` - Dict of {skill_name: bool}

**Additional Fields:**
- ✅ `expertise_skills` - List of expertise skills
- ✅ `equipment` - List of equipment items
- ✅ `features` - List of class/racial features
- ✅ `saving_throw_proficiencies` - List of proficient saves
- ✅ `languages` - List of known languages
- ✅ `speed` - Movement speed
- ✅ `conditions` - List of active conditions (empty)
- ✅ `tool_proficiencies` - List of tool proficiencies
- ✅ `personality_traits` - String describing personality
- ✅ `ideals` - String describing ideals
- ✅ `bonds` - String describing bonds
- ✅ `flaws` - String describing flaws
- ✅ `backstory` - String with character backstory
- ✅ `rulebook` - Source rulebook

**Cosmere-Specific Fields:**
- ✅ `identity` - Roshar identity
- ✅ `radiant_order` - Radiant order (or "None" for Heralds)
- ✅ `ideal_level` - Oath progression level
- ✅ `investiture_points` - Dict with current/maximum
- ✅ `spren` - Dict with type/name/status
- ✅ `surges_known` - List of known surges
- ✅ `cantrips_known` - List of cantrips
- ✅ `invested_arts_known` - List of invested arts
- ✅ `tags` - List of indexing tags

---

## Validation Results

### Python Validation Script Output:

```
✅ kalak_herald.json
   Name: Kalak
   Level: 20
   Class: Herald
   HP: 400
   AC: 22
   Skills: 10 skills
   Equipment: 8 items
   Features: 13 features

✅ nale_herald.json
   Name: Nale
   Level: 20
   Class: Herald
   HP: 380
   AC: 24
   Skills: 10 skills
   Equipment: 10 items
   Features: 14 features

🎉 All JSON files are valid and complete!
```

### Format Comparison with aggi.json:

```
=== Field Validation ===
✅ Aggi: All required fields present
✅ Kalak: All required fields present
✅ Nale: All required fields present

=== Hit Points Structure ===
✅ Aggi: {'current': 8, 'maximum': 8, 'temporary': 0}
✅ Kalak: {'current': 400, 'maximum': 400, 'temporary': 0}
✅ Nale: {'current': 380, 'maximum': 380, 'temporary': 0}

=== Ability Scores Structure ===
✅ Aggi: All 6 ability scores present
✅ Kalak: All 6 ability scores present
✅ Nale: All 6 ability scores present

=== Format Compatibility ===
✅ All Herald JSON files match CharacterData format
✅ Ready for CharacterManager.add_npc()
```

---

## Conversion Methodology

### Structured Text to JSON Mapping:

**BASIC INFORMATION Section:**
```
Name: Kalak → "name": "Kalak"
Race: Herald → "race": "Herald"
Class: Herald → "character_class": "Herald"
Level: 20 → "level": 20
Background: Herald Mentor → "background": "Herald Mentor"
```

**ABILITY SCORES Section:**
```
Strength: 22 (modifier: +6) → "strength": 22
Dexterity: 18 (modifier: +4) → "dexterity": 18
...
```

**COMBAT STATISTICS Section:**
```
Hit Points: 400 → "hit_points": {"current": 400, "maximum": 400, "temporary": 0}
Armor Class: 22 → "armor_class": 22
Proficiency Bonus: +6 → "proficiency_bonus": 6
```

**SKILLS Section:**
```
- Athletics (Legendary) → "athletics": true (+ added to expertise_skills)
- History (Legendary) → "history": true (+ added to expertise_skills)
- Insight (Expert) → "insight": true
```

**FEATURES AND TRAITS Section:**
```
- **Immortal:** Description → "Immortal: Description" (in features array)
- **Honorblade Bond:** Description → "Honorblade Bond: Description"
```

**EQUIPMENT Section:**
```
- Item name (description) → "Item name (description)" (in equipment array)
```

**COSMERE/ROSHAR ATTRIBUTES Section:**
```
Identity: Herald → "identity": "Herald"
Investiture Points: 100/100 → "investiture_points": {"current": 100, "maximum": 100}
Spren Bond: Type - Name (status) → "spren": {"type": "Type", "name": "Name", "status": "status"}
```

**PERSONALITY Section:**
```
Personality Traits: Long text → "personality_traits": "Long text"
Ideals: Text → "ideals": "Text"
Bonds: Text → "bonds": "Text"
Flaws: Text → "flaws": "Text"
```

**BACKSTORY Section:**
```
Multiple paragraphs → "backstory": "Condensed summary"
```

---

## Usage

### Loading NPCs in Game Code:

```python
import json

# Load Kalak
with open('data/players/kalak_herald.json', 'r') as f:
    kalak_data = json.load(f)

# Add to CharacterManager
char_id = character_manager.add_npc(kalak_data)

# Add to GameEngine for combat
game_engine.add_character(kalak_data)
```

### Integration with Combat Initializer:

```python
# In CombatInitializer._load_predefined_npcs()
def _load_predefined_npcs(self, enemies: List[Dict]) -> List[str]:
    predefined_ids = []

    for enemy in enemies:
        if not enemy.get('is_predefined', False):
            continue

        # Load from JSON file
        npc_file = f"data/players/{enemy['name'].lower().replace(' ', '_')}.json"
        if os.path.exists(npc_file):
            with open(npc_file, 'r') as f:
                npc_data = json.load(f)

            # Add to CharacterManager
            char_id = self.character_manager.add_npc(npc_data)
            predefined_ids.append(char_id)

            enemy['processed'] = True

    return predefined_ids
```

---

## Next Steps

### Immediate (Unblocks Phase 2):
1. ✅ Convert Herald .txt files to JSON format (DONE)
2. ⬜ Create NPCStatLoader component to load JSON files
3. ⬜ Update game_initialization.py to load NPC registry
4. ⬜ Update Combat Plan with correct NPC loading logic

### Optional Enhancements:
- Convert remaining NPC .txt files (aggi.txt, kali.txt) to JSON
- Create automated .txt → JSON converter
- Add validation script to CI/CD
- Create NPC registry cache for faster loading

---

## Files Affected

### Created:
- `data/players/kalak_herald.json` (new)
- `data/players/nale_herald.json` (new)

### Referenced:
- `data/aggi.json` (format reference)
- `data/players/kalak_herald.txt` (source)
- `data/players/nale_herald.txt` (source)

### To Update:
- `docs/COMBAT_ENGINE_IMPLEMENTATION_PLAN.md` (NPC loading section)
- `docs/COMBAT_PLAN_NPC_INTEGRATION_GAPS.md` (mark conversions complete)

---

## Validation Checklist

- [x] JSON syntax is valid
- [x] All required CharacterData fields present
- [x] Hit points structure correct (current/maximum/temporary)
- [x] All 6 ability scores present
- [x] Skills format correct (dict of {skill: bool})
- [x] character_class field (not "class")
- [x] Equipment array populated
- [x] Features array populated
- [x] Cosmere-specific fields included
- [x] Personality/ideals/bonds/flaws present
- [x] Backstory included
- [x] Matches format of aggi.json
- [x] Ready for CharacterManager.add_npc()

---

## Conclusion

✅ **Herald NPC JSON conversion complete**

Both Kalak and Nale Herald stat files have been successfully converted from structured `.txt` format to JSON format that matches the CharacterData schema.

**Status:** Ready for integration with Combat Initializer and NPC loading system.

**Next Action:** Create NPCStatLoader component to load these JSON files at game initialization.
