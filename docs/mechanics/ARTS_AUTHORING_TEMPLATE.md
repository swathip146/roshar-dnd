# Invested Arts Authoring Template

**Purpose**: Canonical field schema and examples for authoring the ~300 real Surgebinding arts. This doc is the spec parallel authoring agents will follow.

---

## Field Schema Overview

Invested Arts share the SRD spell schema. Most arts can be authored with **structured fields** that compile to automation trees automatically. Only exotic effects (illusion, teleport, summon, buffs, utility) need hand-authored `automation` trees.

### Required Fields (All Arts)
```json
{
  "id": "snake_case_unique_id",
  "name": "Display Name",
  "art_level": 0,  // 0 = cantrip, 1-9 = leveled
  "orders": ["Edgedancer", "Truthwatcher"],  // Which Radiant orders get this art
  "surge": "Progression",  // Primary surge
  "casting_time": "1 action",
  "range": "60 feet",  // or "Touch", "Self", "30 feet", etc.
  "components": ["S"],  // S=somatic, V=verbal, G=gemstone
  "duration": "Instantaneous",  // or "1 minute", "Concentration, up to 10 minutes"
  "desc": "Full description from the docling...",
  "source": {
    "book": "invested_arts",  // Always "invested_arts" for arts from The Invested Arts book
    "line": 582,  // Exact line number in docling.md where this art begins (## ArtName)
    "reviewed": true
  },
  "quote": "Exact quote from docling (1-2 sentences) for citation verification"
}
```

### Citation Format (CRITICAL)

**verify_citations()** enforces a ±3-line window. The `quote` MUST be an exact substring from the docling within 3 lines of `source.line`.

**Example** (from Abrade at line 582):
```json
"source": {
  "book": "invested_arts",
  "line": 606,
  "reviewed": true
},
"quote": "You send Abrasion wildly, slicing through the air, toward a creature that you can see within range. The target must succeed on a Dexterity saving throw or take 1d8 axial damage."
```

**Line number**: Use the line where the art's **prose description** begins (not the `## Name` header line). Verify with:
```bash
grep -n "^## ArtName$" parsed_data/cosmere-5e-the-invested-arts-of-the-cosmere-v2-0/docling.md
```

---

## VARIANT 1: Save-Based Damage (Cantrips with Character-Level Scaling)

**Use for**: Cantrips that require a save and scale at 5th/11th/17th level.

**Example**: Abrade (DEX save, 1d8 axial, scales to 4d8)

```json
{
  "id": "abrade",
  "name": "Abrade",
  "art_level": 0,
  "orders": ["Edgedancer"],
  "surge": "Abrasion",
  "casting_time": "1 action",
  "range": "60 feet",
  "components": ["S"],
  "duration": "Instantaneous",
  "source": {
    "book": "invested_arts",
    "line": 606,
    "reviewed": true
  },
  "quote": "You send Abrasion wildly, slicing through the air, toward a creature that you can see within range. The target must succeed on a Dexterity saving throw or take 1d8 axial damage.",
  "desc": "You send Abrasion wildly, slicing through the air, toward a creature that you can see within range. The target must succeed on a Dexterity saving throw or take 1d8 axial damage. The target gains no benefit from one-quarter, half, or three-quarters cover for this saving throw. This Invested Art's damage increases by 1d8 when you reach 5th level (2d8), 11th level (3d8), and 17th level (4d8).",
  "dc": {
    "dc_type": "dex",  // "dex", "str", "con", "int", "wis", or "cha"
    "dc_success": "none"  // "none" = negates, "half" = save halves damage
  },
  "damage": {
    "damage_type": "axial",  // Any valid damage type (fire, cold, axial, spiritual, etc.)
    "damage_at_character_level": {
      "1": "1d8",
      "5": "2d8",
      "11": "3d8",
      "17": "4d8"
    }
  }
}
```

**Compiles to**: `target → save (DEX) → fail:[damage] | success:[]`

---

## VARIANT 2: Attack-Based Damage (Leveled Arts with Slot Scaling)

**Use for**: Leveled arts (1st-9th) with ranged/melee attack rolls and damage that scales with upcast level.

**Example**: Abrasive Bolt (ranged attack, 4d6 axial, +1d6/level)

```json
{
  "id": "abrasive_bolt",
  "name": "Abrasive Bolt",
  "art_level": 1,
  "orders": ["Edgedancer"],
  "surge": "Abrasion",
  "casting_time": "1 action",
  "range": "120 feet",
  "components": ["S"],
  "duration": "1 round",
  "source": {
    "book": "invested_arts",
    "line": 630,
    "reviewed": true
  },
  "quote": "You infuse the air with Abrasion and direct it toward a creature of your choice within range. Make a ranged Invested Art attack against the target. On a hit, the target takes 4d6 axial damage",
  "desc": "You infuse the air with Abrasion and direct it toward a creature of your choice within range. Make a ranged Invested Art attack against the target. On a hit, the target takes 4d6 axial damage, and the next attack roll made against the target before the end of your next turn has advantage, due to the Surge increasing the friction of the target's body. At Higher Levels: When you cast this Invested Art at 2nd level or higher, the damage increases by 1d6 for each level above 1st.",
  "attack_type": "ranged",  // "ranged" or "melee"
  "damage": {
    "damage_type": "axial",
    "damage_at_slot_level": {
      "1": "4d6",
      "2": "5d6",
      "3": "6d6",
      "4": "7d6",
      "5": "8d6",
      "6": "9d6",
      "7": "10d6",
      "8": "11d6",
      "9": "12d6"
    }
  }
}
```

**Compiles to**: `target → spell_attack (ranged) → hit:[damage] | miss:[]`

---

## VARIANT 3: Healing (Leveled Arts with Slot Scaling)

**Use for**: Arts that restore hit points, scaling with upcast level.

**Example**: Regrowth (2d8 + MOD healing, +2d8/level)

```json
{
  "id": "regrowth",
  "name": "Regrowth",
  "art_level": 1,
  "orders": ["Edgedancer", "Truthwatcher"],
  "surge": "Progression",
  "casting_time": "1 action",
  "range": "Touch",
  "components": ["S"],
  "duration": "Instantaneous",
  "source": {
    "book": "invested_arts",
    "line": 6751,
    "reviewed": true
  },
  "quote": "A creature you touch recovers a number of hit points equal to 2d8 + your Investiture ability modifier. This Invested Art has no effect on splinters or entities.",
  "desc": "A creature you touch recovers a number of hit points equal to 2d8 + your Investiture ability modifier. This Invested Art has no effect on splinters or entities. At Higher Levels: When you cast this Invested Art at 2nd level or higher, the healing increases by 2d8 for each level above 1st.",
  "heal_at_slot_level": {
    "1": "2d8 + MOD",
    "2": "4d8 + MOD",
    "3": "6d8 + MOD",
    "4": "8d8 + MOD",
    "5": "10d8 + MOD",
    "6": "12d8 + MOD",
    "7": "14d8 + MOD",
    "8": "16d8 + MOD",
    "9": "18d8 + MOD"
  }
}
```

**Note**: `MOD` is a placeholder for the caster's Investiture ability modifier. The executor substitutes it at runtime.

**Compiles to**: `target → heal`

---

## VARIANT 4: Area of Effect

**Use for**: Arts that affect multiple targets in a radius/cone/line.

**Add to any damage/heal variant**:
```json
{
  "area_of_effect": {
    "type": "sphere",  // "sphere", "cone", "line", "cube"
    "size": 20  // Radius in feet
  }
}
```

**Example**: A save-based AoE damage art:
```json
{
  "id": "explosive_abrasion",
  "name": "Explosive Abrasion",
  "art_level": 2,
  "orders": ["Edgedancer"],
  "surge": "Abrasion",
  "casting_time": "1 action",
  "range": "60 feet",
  "components": ["S"],
  "duration": "Instantaneous",
  "area_of_effect": {
    "type": "sphere",
    "size": 20
  },
  "dc": {
    "dc_type": "dex",
    "dc_success": "half"
  },
  "damage": {
    "damage_type": "axial",
    "damage_at_slot_level": {
      "2": "3d8",
      "3": "4d8",
      "4": "5d8"
    }
  }
}
```

**Compiles to**: `target → area_of_effect (sphere 20ft) → [save → fail:[damage] | success:[damage×0.5]]`

---

## VARIANT 5: Exotic Effects (Hand-Authored Automation)

**Use for**: Effects that DON'T fit the field schema (illusion, teleport, summon, create_object, buffs via ieffect2, utility).

These need an explicit `automation` tree using the nodes from `components/combat/maneuver_executor.py` KNOWN_NODES.

### Available Nodes

**Standard nodes**: `target`, `save`, `damage`, `attack`, `roll`, `ieffect2`, `spell_attack`, `heal`

**Invested Arts additions**: `area_of_effect`, `check`, `resistance`

**Exotic nodes** (arts-infra Phase 0.5):
- `illusion` — create an illusion with disbelief DC
- `teleport` — move actor/target up to distance_ft
- `summon` — summon a creature for duration
- `create_object` — Soulcast-style object creation
- `reaction` — mark as reaction-triggered
- `utility` — narrative-only effects (kindle fire, recolor eyes)
- `forced_move` — push/pull target X feet
- `choice` — "choose one of the following effects"

### Example: Illusion Art

```json
{
  "id": "lightweaving_illusion",
  "name": "Lightweaving Illusion",
  "art_level": 1,
  "orders": ["Lightweaver"],
  "surge": "Illumination",
  "casting_time": "1 action",
  "range": "60 feet",
  "components": ["S"],
  "duration": "10 minutes",
  "source": {
    "book": "invested_arts",
    "line": 1234,
    "reviewed": true
  },
  "quote": "You create a visual illusion...",
  "desc": "You create a visual illusion of an object, creature, or phenomenon within range. A creature that uses an action to examine the illusion can make an Investigation check against your Invested save DC to disbelieve it.",
  "automation": [
    {
      "type": "illusion",
      "description": "visual illusion of object/creature/phenomenon",
      "dc": 15,
      "duration": "10 minutes"
    }
  ]
}
```

### Example: Buff (Using ieffect2)

```json
{
  "id": "toughskin",
  "name": "Toughskin",
  "art_level": 1,
  "orders": ["Edgedancer"],
  "surge": "Progression",
  "casting_time": "1 action",
  "range": "Touch",
  "components": ["S"],
  "duration": "1 hour",
  "source": {
    "book": "invested_arts",
    "line": 5678,
    "reviewed": true
  },
  "quote": "Your touch accelerates a creature's natural healing...",
  "desc": "Your touch accelerates a creature's natural healing, granting +2 AC for the duration.",
  "automation": [
    {
      "type": "target",
      "target": "chosen",
      "effects": [
        {
          "type": "ieffect2",
          "name": "Toughskin",
          "duration": "1 hour",
          "effects": {
            "ac_bonus": 2
          }
        }
      ]
    }
  ]
}
```

### Example: Utility Cantrip

```json
{
  "id": "kindle_flame",
  "name": "Kindle Flame",
  "art_level": 0,
  "orders": ["Skybreaker"],
  "surge": "Division",
  "casting_time": "1 action",
  "range": "Touch",
  "components": ["S"],
  "duration": "Instantaneous",
  "source": {
    "book": "invested_arts",
    "line": 393,
    "reviewed": true
  },
  "quote": "You can use your action to kindle a fire, lighting a torch, kindling, or something else with abundant, exposed fuel.",
  "desc": "You can use your action to kindle a fire, lighting a torch, kindling, or something else with abundant, exposed fuel.",
  "automation": [
    {
      "type": "utility",
      "narration": "kindles a fire (torch, kindling, or exposed fuel)"
    }
  ]
}
```

---

## Authoring Workflow

1. **Find the art in docling.md**:
   ```bash
   grep -n "^## ArtName$" parsed_data/cosmere-5e-the-invested-arts-of-the-cosmere-v2-0/docling.md
   ```

2. **Extract fields** from the prose:
   - Casting Time / Range / Components / Duration: directly from docling
   - Damage: look for XdY notation and "At Higher Levels" text
   - Save: "must succeed on a [Ability] saving throw"
   - Attack: "Make a ranged/melee Invested Art attack"
   - Healing: "regains X hit points"

3. **Determine which orders get it**: Read the order art lists (docling lines 123-312)

4. **Choose variant**:
   - **Save + damage with character scaling** → VARIANT 1
   - **Attack + damage with slot scaling** → VARIANT 2
   - **Healing with slot scaling** → VARIANT 3
   - **Exotic (illusion/teleport/buff/utility)** → VARIANT 5
   - **AoE** → Add `area_of_effect` block

5. **Write the entry** following the template above

6. **Verify citation**:
   ```bash
   uv run python -c "from components.cosmere_rules import get_cosmere_rules as g; print(g().verify_citations())"
   ```
   Should show `verified == checked` and `mismatched == []`

---

## Common Damage Types

**Standard D&D**: acid, bludgeoning, cold, fire, force, lightning, necrotic, piercing, poison, psychic, radiant, slashing, thunder

**Cosmere-specific**: axial, spiritual (used in Surgebinding arts)

---

## Testing New Arts

After authoring, test that:
1. Art compiles to automation tree (NOT `needs_adjudication`)
2. Can be cast through `_cast_art`
3. IP is spent for leveled arts
4. Damage/heal is applied and HP syncs
5. Custom damage types (axial, spiritual) work through the engine

Run:
```bash
uv run pytest tests/combat/test_cast_art_pipeline.py -p no:randomly -n0 -q
```

---

## Summary Checklist

- [ ] All required fields present (`id`, `name`, `art_level`, `orders`, `surge`, `casting_time`, `range`, `components`, `duration`, `desc`, `source`, `quote`)
- [ ] `source.line` points to the prose description (within ±3 lines of `quote`)
- [ ] `quote` is an exact substring from docling
- [ ] Either structured fields (`dc`/`damage`/`heal_at_slot_level`/`attack_type`) OR hand-authored `automation` tree
- [ ] `damage_at_character_level` for cantrips (1/5/11/17), `damage_at_slot_level` for leveled (1-9)
- [ ] `heal_at_slot_level` uses `MOD` placeholder if it includes ability modifier
- [ ] `orders` list matches the order art lists in docling
- [ ] `reviewed: true` only after citation verification passes

---

**End of Template**
