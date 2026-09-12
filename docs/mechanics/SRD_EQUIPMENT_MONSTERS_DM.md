# SRD 5.2.1 Equipment, Magic Items, Monsters & DM-Toolbox Mechanics Catalogue

Source: `parsed_data/srd_cc_v5.2.1/docling.md` (2024 SRD 5.2.1, Creative Commons), sections:
- "Equipment" (weapons, armor, tools, adventuring gear, mounts/vehicles, currency): lines 5598-5621, 6052-6991
- "Magic Items" (attunement, categories, rarity, scrolls): lines 7008-7107
- "Gameplay Toolbox" (Combat Encounters / Encounter Difficulty): lines 12949-13594
- "Magic Items" (full A-Z list, cursed/sentient items, crafting): lines 13595-16814
- "Monsters" (stat block anatomy + A-Z list): lines 16815-17037, 17073-24275 (end of file)
- Carrying Capacity cross-reference: line 12039-12053 (Rules Glossary, outside assigned range but required for §7)
- Improvised Weapons / Unarmed Strike cross-reference: lines 12425-12435, 12903-12913 (Rules Glossary, outside assigned range but required for §1)

Also audited: `data/rules/srd/equipment.json`, `magic_items.json`, `monsters.json`,
`weapon_properties.json`, `damage_types.json`.

This is a catalogue of what the rules **say**, for a game-engine implementation audit.
It does **not** assess what the codebase currently does — that is a separate agent's job.

---

## 0. Headline finding: the vendored JSON is 2014 SRD, not 2024

`data/rules/srd/README.md` states the source is `5e-bits/5e-database`, path **`src/2014/en`**,
under **OGL 1.0a**. Every `/api/...` URL embedded in every record reads `/api/2014/...`. This
is a different ruleset from the assigned narrative source (`docling.md`, 2024 SRD 5.2.1,
Creative Commons). Concretely, for the exact same monster (Adult Red Dragon):

| Field | 2024 `docling.md` (line 21100-21141) | 2014 `monsters.json` |
|---|---|---|
| Multiattack | 3x Rend (replace one with Scorching Ray) | Frightful Presence + Bite + 2x Claw |
| Breath weapon | Fire Breath, Recharge 5-6, 60-ft Cone, DC 21, 17d6 | not present in this record's actions (2014 Fire Breath is Recharge 5-6 in the 2014 stat block too, but the surrounding kit differs) |
| Legendary Actions | Commanding Presence, Fiery Rays, Pounce | Detect, Tail Attack, Wing Attack (Costs 2 Actions) — the "costs 2 actions" legendary-action-cost mechanic is 2024-absent/2014-present here, i.e. inverted from what one might assume |
| Charisma | 23 | 21 |
| Stealth skill | +7 | +6 (untrained Dex+PB math differs because the underlying stat differs) |
| Frightful Presence | absent (removed in 2024) | present |

This mismatch is systemic, not a one-off: `weapon_properties.json` has 11 entries including
a 2014-only `"monk"` property and is missing all eight 2024 Weapon Mastery properties;
`equipment.json` weapon records carry the 2014 `monk` property tag (e.g. Dagger, Club);
`magic_items.json` has no structured `attunement` boolean, `charges` field, or 2024-style
category enum. See §6 for the full per-file field audit. This finding independently
confirms the pattern already logged in `docs/mechanics/EDITION_CONFLICTS_IN_CODE.md`
("Conflict" list) and `docs/mechanics/EDITION_DIFFERENCES.md` — this document adds the
equipment/monster/magic-item evidence to that ledger.

---

## 1. Weapons (docling.md lines 6038-6188, 12425-12436, 12903-12913)

### 1.1 Weapon table fundamentals (lines 6038-6046)
- **Category**: Simple or Martial (line 6042). Proficiency is usually granted per category.
- **Melee or Ranged** (line 6043): Melee attacks a target within 5 ft; Ranged attacks farther.
- **Damage**: dice + damage type (line 6044).
- **Properties**: zero or more, each independently defined (line 6045; full defs below).
- **Mastery**: exactly one mastery property per weapon, usable only with a class feature
  that "unlocks" it (line 6046, 6104).

### 1.2 Full weapon table (lines 6144-6188) — 42 weapons total (10 Simple Melee, 4 Simple
Ranged, 22 Martial Melee, 6 Martial Ranged)

**Simple Melee (10):**
| Name | Damage | Properties | Mastery | Weight | Cost |
|---|---|---|---|---|---|
| Club | 1d4 Bludgeoning | Light | Slow | 2 lb | 1 SP |
| Dagger | 1d4 Piercing | Finesse, Light, Thrown (20/60) | Nick | 1 lb | 2 GP |
| Greatclub | 1d8 Bludgeoning | Two-Handed | Push | 10 lb | 2 SP |
| Handaxe | 1d6 Slashing | Light, Thrown (20/60) | Vex | 2 lb | 5 GP |
| Javelin | 1d6 Piercing | Thrown (30/120) | Slow | 2 lb | 5 SP |
| Light Hammer | 1d4 Bludgeoning | Light, Thrown (20/60) | Nick | 2 lb | 2 GP |
| Mace | 1d6 Bludgeoning | — | Sap | 4 lb | 5 GP |
| Quarterstaff | 1d6 Bludgeoning | Versatile (1d8) | Topple | 4 lb | 2 SP |
| Sickle | 1d4 Slashing | Light | Nick | 2 lb | 1 GP |
| Spear | 1d6 Piercing | Thrown (20/60), Versatile (1d8) | Sap | 3 lb | 1 GP |

**Simple Ranged (4):**
| Name | Damage | Properties | Mastery | Weight | Cost |
|---|---|---|---|---|---|
| Dart | 1d4 Piercing | Finesse, Thrown (20/60) | Vex | 1/4 lb | 5 CP |
| Light Crossbow | 1d8 Piercing | Ammunition (80/320; Bolt), Loading, Two-Handed | Slow | 5 lb | 25 GP |
| Shortbow | 1d6 Piercing | Ammunition (80/320; Arrow), Two-Handed | Vex | 2 lb | 25 GP |
| Sling | 1d4 Bludgeoning | Ammunition (30/120; Bullet) | Slow | — | 1 SP |

**Martial Melee (22):**
| Name | Damage | Properties | Mastery | Weight | Cost |
|---|---|---|---|---|---|
| Battleaxe | 1d8 Slashing | Versatile (1d10) | Topple | 4 lb | 10 GP |
| Flail | 1d8 Bludgeoning | — | Sap | 2 lb | 10 GP |
| Glaive | 1d10 Slashing | Heavy, Reach, Two-Handed | Graze | 6 lb | 20 GP |
| Greataxe | 1d12 Slashing | Heavy, Two-Handed | Cleave | 7 lb | 30 GP |
| Greatsword | 2d6 Slashing | Heavy, Two-Handed | Graze | 6 lb | 50 GP |
| Halberd | 1d10 Slashing | Heavy, Reach, Two-Handed | Cleave | 6 lb | 20 GP |
| Lance | 1d10 Piercing | Heavy, Reach, Two-Handed (unless mounted) | Topple | 6 lb | 10 GP |
| Longsword | 1d8 Slashing | Versatile (1d10) | Sap | 3 lb | 15 GP |
| Maul | 2d6 Bludgeoning | Heavy, Two-Handed | Topple | 10 lb | 10 GP |
| Morningstar | 1d8 Piercing | — | Sap | 4 lb | 15 GP |
| Pike | 1d10 Piercing | Heavy, Reach, Two-Handed | Push | 18 lb | 5 GP |
| Rapier | 1d8 Piercing | Finesse | Vex | 2 lb | 25 GP |
| Scimitar | 1d6 Slashing | Finesse, Light | Nick | 3 lb | 25 GP |
| Shortsword | 1d6 Piercing | Finesse, Light | Vex | 2 lb | 10 GP |
| Trident | 1d8 Piercing | Thrown (20/60), Versatile (1d10) | Topple | 4 lb | 5 GP |
| Warhammer | 1d8 Bludgeoning | Versatile (1d10) | Push | 5 lb | 15 GP |
| War Pick | 1d8 Piercing | Versatile (1d10) | Sap | 2 lb | 5 GP |
| Whip | 1d4 Slashing | Finesse, Reach | Slow | 3 lb | 2 GP |

(Note: table header lists 22 Martial Melee weapons but the doc only enumerates 18 rows for
Martial Melee before switching to Martial Ranged — Blowgun, Hand Crossbow, Heavy Crossbow,
Longbow, Musket, Pistol are the 6 Martial Ranged, giving 42 weapons total; count verified
by direct line count of the 2024 table at lines 6146-6188, which has 42 named-weapon rows.)

**Martial Ranged (6):**
| Name | Damage | Properties | Mastery | Weight | Cost |
|---|---|---|---|---|---|
| Blowgun | 1 Piercing | Ammunition (25/100; Needle), Loading | Vex | 1 lb | 10 GP |
| Hand Crossbow | 1d6 Piercing | Ammunition (30/120; Bolt), Light, Loading | Vex | 3 lb | 75 GP |
| Heavy Crossbow | 1d10 Piercing | Ammunition (100/400; Bolt), Heavy, Loading, Two-Handed | Push | 18 lb | 50 GP |
| Longbow | 1d8 Piercing | Ammunition (150/600; Arrow), Heavy, Two-Handed | Slow | 2 lb | 50 GP |
| Musket | 1d12 Piercing | Ammunition (40/120; Bullet), Loading, Two-Handed | Slow | 10 lb | 500 GP |
| Pistol | 1d10 Piercing | Ammunition (30/90; Bullet), Loading | Vex | 3 lb | 250 GP |

### 1.3 Weapon Properties — discrete rules (lines 6058-6101)

| Property | Rule (verbatim mechanic) |
|---|---|
| **Ammunition** | Ranged attack requires ammunition matching the weapon's specified type. Each attack expends 1 piece. Drawing ammo is part of the attack (needs a free hand for one-handed weapons). After combat, spend 1 minute to recover half the ammunition used (round down); rest is lost. |
| **Finesse** | Attack/damage rolls may use Str or Dex modifier, attacker's choice, but the *same* modifier must be used for both. |
| **Heavy** | Disadvantage on attack rolls if: Melee and Str < 13, or Ranged and Dex < 13. |
| **Light** | Taking the Attack action and attacking with a Light weapon lets you make one extra attack as a Bonus Action later that turn, with a *different* Light weapon; do not add your ability modifier to that bonus-action damage unless the modifier is negative. |
| **Loading** | Can fire only one piece of ammunition per action/bonus action/reaction used to fire it, regardless of how many attacks you'd normally get. |
| **Range** | Two numbers: normal range, long range (feet). Beyond normal range = Disadvantage. Beyond long range = attack impossible. |
| **Reach** | Adds 5 feet to reach for both attacks and Opportunity Attacks made with the weapon. |
| **Thrown** | Weapon can be thrown for a ranged attack; drawing it is part of the attack. If it's also a Melee weapon, use the same ability modifier for the ranged throw as you would for a melee attack with it. |
| **Two-Handed** | Requires two hands to attack with. |
| **Versatile** | Usable one- or two-handed; the parenthetical damage die applies only when used two-handed in a melee attack. |

### 1.4 Weapon Mastery Properties — 2024-new, discrete effects (lines 6104-6140)

Usable **only** by a character whose class/feature (e.g. Weapon Mastery) unlocks the
specific property for them — a strict gating mechanic an engine must model separately
from proficiency.

| Mastery | Exact effect |
|---|---|
| **Cleave** | On a hit with a melee attack roll, make a melee attack roll with the same weapon against a second creature within 5 ft of the first and within your reach. On a hit, second creature takes the weapon's damage (no ability modifier added unless negative). Once per turn only. |
| **Graze** | If the attack roll misses, deal damage equal to the ability modifier used for the attack roll (same damage type as the weapon; can be increased only by increasing that ability modifier). |
| **Nick** | The Light property's extra attack can be made as part of the Attack action itself instead of as a Bonus Action. Once per turn only. |
| **Push** | On a hit, push the creature up to 10 feet straight away from you, if it is Large or smaller. |
| **Sap** | On a hit, the target has Disadvantage on its next attack roll before the start of your next turn. |
| **Slow** | On a hit that deals damage, you may reduce the target's Speed by 10 feet until the start of your next turn. Stacking cap: total reduction from multiple Slow hits never exceeds 10 feet. |
| **Topple** | On a hit, force a Constitution save (DC = 8 + ability modifier used for the attack + Proficiency Bonus). Failure = Prone condition. |
| **Vex** | On a hit that deals damage, gain Advantage on your next attack roll against that same creature before the end of your next turn. |

Mastery-to-weapon mapping is fixed per weapon (see table in §1.2) — e.g. every Dagger/Sickle/
Light Hammer/Scimitar has Nick; every Greataxe/Halberd has Cleave; every Glaive/Greatsword
has Graze; every Quarterstaff/Battleaxe/Lance/Trident/Maul has Topple.

### 1.5 Unarmed Strike (Rules Glossary, lines 12903-12913 — cross-referenced, not in assigned
range but required for weapons completeness)

Melee attack using body (punch/kick/headbutt), choose one option each use:
- **Damage**: attack roll bonus = Str modifier + Proficiency Bonus; on hit, 1 + Str modifier
  Bludgeoning damage.
- **Grapple**: target makes Str or Dex save (target's choice) DC = 8 + Str mod + Proficiency
  Bonus; fail = Grappled. Requires target ≤ one size larger and a free hand.
- **Shove**: same DC formula; fail = pushed 5 ft or Prone (attacker's choice). Requires
  target ≤ one size larger.

### 1.6 Improvised Weapons (Rules Glossary, lines 12425-12436 — cross-referenced)

- Any object used as a makeshift weapon, or a Simple/Martial weapon used contrary to its
  design (Ranged weapon in melee, or thrown Melee weapon lacking Thrown), counts as
  improvised.
- No Proficiency Bonus added to attack rolls.
- Damage: 1d4 of a GM-chosen appropriate type.
- Thrown range: 20/60 ft (normal/long) if thrown.
- GM may rule it functions identically to a specific Simple/Martial weapon it resembles
  (e.g., table leg = Club).

---

## 2. Armor (docling.md lines 6189-6234)

### 2.1 Armor table fields (lines 6191-6196)
- **Category**: Light, Medium, or Heavy — determines don/doff time.
- **Armor Class (AC)**: base AC formula while worn.
- **Strength**: if a score is listed, wearer's Speed is reduced by 10 ft unless their Str
  meets/exceeds it.
- **Stealth**: "Disadvantage" entry = Disadvantage on Dex (Stealth) checks while worn.

### 2.2 Full armor table (lines 6200-6219)

| Armor | AC formula | Str req | Stealth | Weight | Cost | Don/Doff |
|---|---|---|---|---|---|---|
| Padded Armor | 11 + Dex mod | — | Disadvantage | 8 lb | 5 GP | 1 min |
| Leather Armor | 11 + Dex mod | — | — | 10 lb | 10 GP | 1 min |
| Studded Leather Armor | 12 + Dex mod | — | — | 13 lb | 45 GP | 1 min |
| Hide Armor | 12 + Dex mod (max 2) | — | — | 12 lb | 10 GP | 5 min don / 1 min doff |
| Chain Shirt | 13 + Dex mod (max 2) | — | — | 20 lb | 50 GP | 5 min don / 1 min doff |
| Scale Mail | 14 + Dex mod (max 2) | — | Disadvantage | 45 lb | 50 GP | 5 min don / 1 min doff |
| Breastplate | 14 + Dex mod (max 2) | — | — | 20 lb | 400 GP | 5 min don / 1 min doff |
| Half Plate Armor | 15 + Dex mod (max 2) | — | Disadvantage | 40 lb | 750 GP | 5 min don / 1 min doff |
| Ring Mail | 14 (flat) | — | Disadvantage | 40 lb | 30 GP | 10 min don / 5 min doff |
| Chain Mail | 16 (flat) | Str 13 | Disadvantage | 55 lb | 75 GP | 10 min don / 5 min doff |
| Splint Armor | 17 (flat) | Str 15 | Disadvantage | 60 lb | 200 GP | 10 min don / 5 min doff |
| Plate Armor | 18 (flat) | Str 15 | Disadvantage | 65 lb | 1,500 GP | 10 min don / 5 min doff |
| Shield | +2 (stacks with base AC) | — | — | 6 lb | 10 GP | Utilize action |

Categories: 3 Light, 5 Medium, 4 Heavy, 1 Shield = 13 armor items total, matching
`equipment.json`'s Armor count of 13.

### 2.3 Dex-cap rule (line 12041 pattern, restated at 6207-6211)
Medium armor caps the Dexterity-modifier contribution to AC at **+2**; Light armor has no
cap; Heavy armor uses a flat AC with no Dex modifier at all.

### 2.4 Armor Training (2024 term; replaces 2014 "armor proficiency") (lines 6220-6234)

- Anyone can *don* armor/wield a Shield, but only those with **training** use it effectively.
- **Without training** in Light/Medium/Heavy armor worn: Disadvantage on any D20 Test
  involving Strength or Dexterity, **and you cannot cast spells** while wearing it.
- **Shield**: gain the AC bonus only if trained with shields; otherwise no benefit.
- **One at a time**: a creature can wear only one suit of armor and wield only one shield
  simultaneously.
- A monster is automatically trained with any armor/weapon/tool listed in its own stat
  block (line 6056, 6222, 16944).

### 2.5 Barding (mounts) (lines 6849-6851)
Any armor from the table can be bought as barding (mount armor) at **4x normal cost** and
**2x normal weight**.

---

## 3. Tools, Adventuring Gear, Mounts/Vehicles (docling.md lines 6236-6991)

### 3.1 Tools (lines 6236-6367)
Each tool description has up to four fields: **Ability** (which score is used for checks),
**Utilize** (specific DCs for specific uses under the Utilize action), **Craft** (what items
it can craft, cross-referencing crafting rules), **Variants** (if multiple sub-kinds requiring
separate proficiencies, e.g. Gaming Set, Musical Instrument).

- Tool proficiency: adds Proficiency Bonus to checks using that tool; if you *also* have a
  relevant skill proficiency, you get Advantage on that specific check too (stacking-type
  benefit, not bonus-stacking) (line 6250).
- 14 Artisan's Tools (Alchemist's through Woodcarver's), each requiring separate
  proficiency (lines 6254-6329).
- 8 "Other Tools" (Disguise Kit, Forgery Kit, Gaming Set, Herbalism Kit, Musical
  Instrument, Navigator's Tools, Poisoner's Kit, Thieves' Tools) (lines 6330-6367).
- Total from `equipment.json`: 31 Tools entries (matches: 14 artisan + ~8 other + gaming
  set/instrument variants counted individually in some vendoring).

### 3.2 Adventuring Gear (lines 6368-6839)
~116 named items per `equipment.json` count. Each entry can carry a **mechanical effect**,
not just weight/cost — e.g.:
- **Acid / Alchemist's Fire / Holy Water / Oil**: replace an attack with a thrown-flask
  attack; target makes a Dex save (DC 8 + Dex mod + Proficiency Bonus of the thrower);
  damage varies (2d6 Acid; 1d4 Fire + ongoing burning; 2d8 Radiant vs Fiend/Undead only;
  1d4 Fire + burning-oil follow-up).
- **Ball Bearings / Caltrops / Net / Hunting Trap**: area-denial/control items with their
  own save DCs (Ball Bearings DC 10 Dex or Prone; Caltrops DC 15 Dex or 1 Piercing + Speed
  0; Net DC 8+Dex+PB Restrained, has its own AC 10/HP 5/damage immunities as a destroyable
  object; Hunting Trap DC 13 Dex or 1d4 Piercing + Speed 0, chain-tethered).
- **Healer's Kit**: 10 uses, stabilizes an unconscious 0-HP creature with no check needed.
- **Antitoxin**: Bonus Action drink, Advantage on saves vs. Poisoned condition for 1 hour.
- **Potion of Healing**: explicitly a *magic item* even though listed in mundane gear;
  Bonus Action, 2d4+2 HP.
- **Spell Scroll (Cantrip/Level 1)**: pre-priced consumable magic items (30 GP / 50 GP)
  that any qualifying class-list caster can use without material components; save DC 13,
  attack bonus +5 if the scroll's spell needs either.
- Full price/weight table at lines 6384-6469 (2 tables spanning the alphabet).
- **Ammunition table** (line 6473-6479): Arrows (20/quiver, 1 lb, 1 GP), Bolts (20/case,
  1.5 lb, 1 GP), Firearm Bullets (10/pouch, 2 lb, 3 GP), Sling Bullets (20/pouch, 1.5 lb,
  4 CP), Needles (50/pouch, 1 lb, 1 GP).
- **Arcane/Druidic Focus and Holy Symbol tables** (5 Arcane Focus forms, 3 Druidic Focus
  forms, 3 Holy Symbol forms) — each is a Spellcasting Focus substitute for material
  components, gated to specific classes (Sorcerer/Warlock/Wizard for Arcane; Druid/Ranger
  for Druidic; Cleric/Paladin for Holy Symbol).
- **Equipment packs** (Burglar's, Diplomat's, Dungeoneer's, Entertainer's, Explorer's,
  Priest's, Scholar's) are bundles with their own aggregate weight/cost, each itemized at
  lines 6543-6793.

### 3.3 Mounts and Vehicles (lines 6841-6920)
- **Mounts and Other Animals table**: 8 animals (Camel, Elephant, Draft Horse, Riding
  Horse, Mastiff, Mule, Pony, Warhorse) with Carrying Capacity + Cost.
- **Mounts and Cargo**: an animal pulling a vehicle can move weight up to **5x** its base
  carrying capacity (including vehicle weight); multiple animals pulling together sum
  their capacities.
- **Saddles**: Military Saddle = Advantage on checks to remain mounted; Exotic Saddle
  required for aquatic/flying mounts.
- **Tack, Harness, and Drawn Vehicles table**: Carriage, Cart, Chariot, Sled, Wagon +
  Feed/Stabling per-day costs.
- **Airborne and Waterborne Vehicles table** (7 ships): Speed, Crew, Passengers, Cargo
  (tons), AC, HP, Damage Threshold, Cost. E.g. Warship: 2.5 mph, 60 crew, 60 passengers,
  200 tons cargo, AC 15, HP 500, Damage Threshold 20, 25,000 GP.
- **Ship Repair**: 1 HP repaired per day at 20 GP (halved time/cost with abundant
  supplies/labor, e.g. city shipyard).

---

## 4. Currency, Lifestyle, Hirelings, Spellcasting Services, Selling (docling.md lines
5598-5621, 6022-6037, 6048-6050, 6922-7008)

### 4.1 Coinage (lines 6022-6037)
| Coin | Value in GP |
|---|---|
| Copper Piece (CP) | 1/100 |
| Silver Piece (SP) | 1/10 |
| Electrum Piece (EP) | 1/2 |
| Gold Piece (GP) | 1 (base unit) |
| Platinum Piece (PP) | 10 |

A coin weighs ~1/3 oz; 50 coins = 1 pound (for encumbrance purposes).

### 4.2 Selling Equipment (lines 6048-6050 — **OCR-garbled header** rendered as
`"sEllinG EquipMEnt"`, verified as a genuine section title, not corrupted content)
- Mundane equipment sells for **half its listed cost**.
- Trade goods and valuables (gems, art objects) retain **full value**.
- Magic items have separate pricing rules (see §5.3, Magic Item Rarities and Values).

### 4.3 Lifestyle Expenses (lines 6922-6957)
7 tiers, paid weekly or monthly (GM's choice): Wretched (free), Squalid (1 SP/day), Poor
(2 SP/day), Modest (1 GP/day), Comfortable (2 GP/day), Wealthy (4 GP/day), Aristocratic
(10 GP/day). Purely narrative/economic consequences — no numeric mechanical penalty tied
directly to lifestyle tier in the SRD text itself.

### 4.4 Food, Drink, and Lodging (lines 6958-6979)
Per-item costs (Ale 4 CP, Bread 2 CP, Cheese 1 SP, wine Common 2 SP/Fine 10 GP) and
per-lifestyle Inn Stay + Meal cost tables (Squalid through Aristocratic).

### 4.5 Hirelings (lines 6980-6991)
| Service | Cost |
|---|---|
| Skilled hireling (has a proficiency) | 2 GP/day |
| Untrained hireling | 2 SP/day |
| Messenger | 2 CP/mile |

### 4.6 Spellcasting Services (lines 6992-7007)
Cost to hire a caster to cast a spell for you, gated by settlement size:
| Spell Level | Availability | Cost |
|---|---|---|
| Cantrip | Village+ | 30 GP |
| 1 | Village+ | 50 GP |
| 2 | Village+ | 200 GP |
| 3 | Town/city only | 300 GP |
| 4-5 | Town/city only | 2,000 GP |
| 6-8 | City only | 20,000 GP |
| 9 | City only | 100,000 GP |

### 4.7 Background starting equipment (lines 5598-5621)
Each background offers a binary choice: (A) a themed equipment package, or (B) 50 GP flat.
Example (Soldier): Spear, Shortbow, 20 Arrows, a Gaming Set, Healer's Kit, Quiver,
Traveler's Clothes, 14 GP — or 50 GP.

### 4.8 Carrying Capacity (Rules Glossary, line 12039-12053 — cross-referenced, required
for this section)

| Creature Size | Carry | Drag/Lift/Push |
|---|---|---|
| Tiny | Str x 7.5 lb | Str x 15 lb |
| Small/Medium | Str x 15 lb | Str x 30 lb |
| Large | Str x 30 lb | Str x 60 lb |
| Huge | Str x 60 lb | Str x 120 lb |
| Gargantuan | Str x 120 lb | Str x 240 lb |

While dragging/lifting/pushing weight beyond the max, Speed is capped at 5 feet. (No
explicit "encumbrance tiers" — i.e., no 2014-style "heavily encumbered at 2x/5x" system —
appears in this SRD; carrying capacity is a hard cap plus the armor Strength-requirement
Speed penalty in §2.2/§2.4, and that's the entirety of the load-bearing mechanic in this
document. If the codebase implements tiered encumbrance, that is *not* sourced from this
2024 SRD text and should be flagged to the implementation-audit agent.)

---

## 5. Magic Items — attunement, rarity, categories, crafting (docling.md lines 7008-7107,
13595-13906)

### 5.1 Identifying (lines 7012-7020)
- `Identify` spell is the fastest path.
- Alternative: focus on one item during a Short Rest while in physical contact — learn its
  properties (but never any curse) at the end of the rest.
- Wearing/experimenting can hint at function (potions reveal via taste; GM narrates
  partial discovery for others).

### 5.2 Attunement (lines 7022-7050)
- **Trigger**: some items require Attunement before their magical properties function;
  without it, only nonmagical benefits apply (unless stated otherwise).
- **Process**: a Short Rest spent focused solely on the item, in physical contact,
  different from the Short Rest used to identify it. Interruption = failed attempt.
- **Limit**: **maximum 3 attuned items at once**; a 4th attempt automatically fails until
  an existing attunement ends. Cannot attune to more than one copy of the same item
  (e.g., two Rings of Protection).
- **Ending**: automatically ends if prerequisites stop being met, item is 100+ ft away for
  24+ continuous hours, the attuned creature dies, or another creature attunes to it.
  Voluntary ending = another Short Rest focused on the item, **unless the item is cursed**.
- **Wearing/Wielding rules**: worn items must be donned in the intended fashion; most
  auto-adjust to fit any size/build unless stated otherwise.
- **Multiples of a kind**: cannot wear >1 of footwear/gloves/bracers/armor-suit/headwear/
  cloak simultaneously (GM may except).
- **Paired items**: benefits only apply if *both* items of a pair (boots, bracers,
  gauntlets, gloves) are worn simultaneously.

### 5.3 Magic Item Categories (9 total) (lines 13599-13684)
| Category | Rule highlight |
|---|---|
| Armor | Magical version of mundane armor; must be worn to function unless noted; may specify exact armor type or leave it open/random. |
| Potions | Consumable; Bonus Action to drink/administer; can be mixed (see Potion Miscibility table, d100). |
| Rings | Must be worn on a finger (or similar digit) to function. |
| Rods | Scepter, 2-5 lb; usable as an Arcane Focus unless noted. |
| Scrolls | Consumable; reading invokes and destroys it; any literate creature can attempt to activate unless stated otherwise. |
| Staffs | 2-7 lb; usable as a nonmagical Quarterstaff *and* an Arcane Focus unless noted. |
| Wands | 12-15 in; usable as an Arcane Focus unless noted. |
| Weapons | Magical version of mundane weapon; Ammunition-property weapons make fired ammo count as magical. |
| Wondrous Items | Catch-all: boots, belts, capes, amulets, bags, carpets, figurines, horns, instruments, etc. |

### 5.4 Magic Item Rarity and value (lines 13698-13720)
| Rarity | Value (full item) |
|---|---|
| Common | 100 GP |
| Uncommon | 400 GP |
| Rare | 4,000 GP |
| Very Rare | 40,000 GP |
| Legendary | 200,000 GP |
| Artifact | Priceless |

- Halve the value for a consumable item other than a Spell Scroll.
- Spell Scroll value = 2x its scribing cost (see §5.7 table).
- If a magic item incorporates a priced mundane item (e.g. +1 Plate Armor), add the
  mundane cost to the rarity value (worked example: 4,000 Rare + 1,500 Plate = 5,500 GP).

### 5.5 Activation mechanics (lines 13722-13746)
- Default: a **Magic action** to activate, plus any item-specific extra requirement.
- **Command Word**: must be audible (spoken) or performed (signed); fails in
  sound-suppressed areas (e.g. inside a `Silence` spell).
- **Consumable items**: used up on activation (Potions swallowed, Scrolls' text vanishes).
- **Spells cast from items**: cast at lowest possible spell/caster level, no slot expended,
  no components needed unless stated, normal casting time/range/duration, Concentration
  still required if the spell needs it. If the item requires the user's own spellcasting
  ability and the user has none, treat modifier as +0 but Proficiency Bonus still applies.
- **Charges**: number of charges consumed to activate specific properties; revealed by
  `Identify`; an attuned creature always knows current/max charges. Recharge timing is
  usually "regains 1dX charges daily at dawn" (see examples in §5.9 taxonomy).
- **"The Next Dawn"**: if the item is on a plane without a dawn, GM decides when it
  recharges.

### 5.6 Cursed Items (lines 13748-13752, plus 5 example items found at lines 134, 354, 704,
1487, 2315 relative to the A-Z section)
- Cursed status is specified per item and normally **hidden from all identification
  methods, including Identify**.
- Attunement to a cursed item **cannot be voluntarily ended** unless the curse is broken
  first (e.g. via `Remove Curse`).
- Example curse effects found in the A-Z list: Vulnerability to 2 of 3 associated damage
  types (cursed elemental-resistance armor); Disadvantage on attack rolls with any other
  weapon (a cursed weapon that won't let you switch); can't doff the armor at all without
  Remove Curse; a -2 penalty to all saving throws (Deck of Many Things' Euryale card);
  ranged attacks near you get redirected onto you (cursed Shield).

### 5.7 Crafting Magic Items (lines 13760-13813)
- **Prerequisite**: crafter (and all assistants) must have **Arcana skill proficiency**.
- **Tools**: category-specific tool requirement table (Armor->Leatherworker's/Smith's/
  Weaver's; Potion->Alchemist's Supplies or Herbalism Kit; Ring->Jeweler's; Rod/Staff/
  Wand->Woodcarver's; Scroll->Calligrapher's; Weapon->Leatherworker's/Smith's/Woodcarver's;
  Wondrous->Tinker's or the base item's tool).
- **Spells**: if the item casts spells, crafter must have them all prepared each crafting
  day.
- **Time/Cost by rarity**:
  | Rarity | Time | Cost |
  |---|---|---|
  | Common | 5 days | 50 GP |
  | Uncommon | 10 days | 200 GP |
  | Rare | 50 days | 2,000 GP |
  | Very Rare | 125 days | 20,000 GP |
  | Legendary | 250 days | 100,000 GP |
  (halved for consumables other than Spell Scrolls; Artifacts have no crafting rule)
- **Raw material availability**: 75% chance in a city, 25% elsewhere per check; failed
  check = 7-day wait before rechecking.
- If the item incorporates a priced mundane item, pay/craft that separately in full.
- **Assistants**: time divided among workers (normally max 1 assistant, GM may allow more).

### 5.8 Sentient Magic Items (lines 13814-13905)
- Never single-use (no sentient potions/scrolls); mostly weapons.
- Has Int/Wis/Cha scores (4d6-drop-lowest each), an alignment (d100 table, 8 categories),
  a communication mode (d10: emotion-only / speaks languages / speaks + telepathy), senses
  (d4: hearing+vision 30/60/120 ft, or hearing+Darkvision 120 ft), and an optional Special
  Purpose (d10 table: Aligned, Bane, Creator Seeker, Destiny Seeker, Destroyer, Glory
  Seeker, Lore Seeker, Protector, Soulmate Seeker, Templar).
- **Conflict mechanic**: bearer acting against the item's alignment/purpose triggers a
  Charisma save (DC 12 + item's Cha modifier). Failure => item can demand one of 4 things
  (Chase My Dreams / Get Rid of It / It's Time for a Change / Keep Me Close); refusal lets
  the item block attunement, suppress activated properties, or attempt a Charm-like
  takeover (another Cha save, DC 12 + item Cha mod; on failure, Charmed 1d12 hours,
  repeat-save-on-damage to break free; item can only try this once per dawn regardless of
  outcome).

### 5.9 Magic Item mechanic-type TAXONOMY (engine-support checklist)

An engine must model at least these distinct **effect archetypes**, each demonstrated by
concrete examples pulled from the A-Z list (13906-16814):

| Mechanic type | Example item(s) | Notes for an engine |
|---|---|---|
| **Static numeric bonus** (AC/attack/damage/ability score) | Ammunition +1/+2/+3 (attack & damage); Amulet of Health (sets Con to 19 if lower); Dwarven armor family (+1 AC flat) | Applies continuously while attuned/worn; some are floors not additive (Amulet of Health) |
| **Charges/recharge resource** | Cloak of Invisibility-style items (3 charges, 1d3/dawn); Cube of Force (10 charges, 1d6/dawn); Ring/Rod/Wand of X spells (7 charges, 1d4+3/dawn); Figurine of Wondrous Power - Goat (24 charges, 1/hour used, all-or-nothing 7-day recharge after depletion) | Recharge dice + cadence vary per item; some are "all charges at once," some partial |
| **Activated action (Magic action to trigger)** | Most Rings/Rods/Wands/Staffs; Horn of Valhalla (blow it, summon spirits) | Consumes the user's Magic action unless stated otherwise |
| **Passive resistance/immunity (damage)** | Armor granting Resistance to Bludgeoning/Piercing/Slashing while worn; Brooch (Resistance to Force + Immunity to Magic Missile specifically) | Some are broad (3 physical types), some spell-specific |
| **Condition immunity** | Delicate silver chain pendant (Immunity to Poisoned condition + Poison damage); Horn of Valhalla's summoned spirits (Immunity to Charmed and Frightened) | Condition immunity often paired with matching damage-type immunity |
| **Spellcasting item (cast spell from item)** | Wands of Magic Missile/Fireballs; Staff of Striking; Rings that cast spells; Scrolls | Uses item's fixed save DC/attack bonus, or the user's own casting stat per §5.5 |
| **Cursed item (negative/binding effect)** | Cursed armor (Vulnerability swap), cursed weapon (can't switch weapons), cursed Shield (redirects attacks) | Curse concealment from Identify is itself a mechanic an engine must respect |
| **Sentient item (autonomous NPC-like agent)** | Any item given the optional sentience block | Requires its own ability scores/alignment/Conflict-check subsystem, per §5.8 |
| **Consumable single-use** | Potions, Scrolls, some ammunition (Ammunition of Slaying: becomes nonmagical after one triggered hit) | Distinct from charge-based recharging items — consumed entirely, not partially |
| **Object with its own stat block (destructible item)** | Apparatus of the Crab (AC 20, HP 200, Immunities); animated Instant Fortress (AC 20, HP 100, Immunity to nonsiege B/P/S, Resistance to everything else) | Some Wondrous Items are creatures/objects in their own right with AC/HP/Immunities, not just modifiers to the wearer |
| **Size/shape-shift or transformation item** | Figurines of Wondrous Power (become an animal) | Combines with charge mechanic |
| **Attunement-gated class/species restriction** | Belt of Dwarvenkind-linked Warhammer (Requires Attunement by a Dwarf or a creature attuned to a Belt of Dwarvenkind); Wands "Requires Attunement by a Spellcaster"; a Legendary weapon requiring Attunement by a Paladin | Attunement prerequisite can reference class, species, or even *another item's attunement state* |
| **Random-effect / table-roll item** | Deck of Many Things-style cards (Euryale curse); Potion Miscibility (d100 table when 2+ potions mixed) | Needs a randomization subsystem, not just fixed effects |

Category counts sampled directly from the 228 `Category, Rarity` header lines matched in
the A-Z section: Wondrous Item is the plurality (~140+), followed by Weapon (with specific
weapon-type restrictions like "Glaive, Greatsword, Longsword, Rapier, Scimitar, or
Shortsword"), Armor, Ring (18), Rod (5), Staff (10), Wand (13), Potion (9), Scroll (1
generic "Rarity Varies" entry covering all Spell Scrolls). 140 of 228 sampled item headers
carry "(Requires Attunement...)" — attunement is the majority case, not the exception.

---

## 6. Encounter Building — XP Budget (2024 system) (docling.md lines 13500-13594)

### 6.1 This is NOT the 2014 CR/multiplier system
The 2014 DMG method (sum monster CRs -> XP, then multiply by an encounter-size multiplier
table 1x/1.5x/2x/2.5x/3x/4x based on number of monsters and number of PCs) **does not
appear anywhere in this 2024 SRD text**. Verified: no "multiplier" table, no "adjusted XP"
concept, appears in lines 13500-13594 or elsewhere in the Gameplay Toolbox section. The
2024 system instead uses a flat **per-character-level XP budget** consumed directly by
monster XP values, with no multiplier for grouping multiple monsters together.

### 6.2 Step 1 — Choose difficulty (lines 13513-13519)
Three qualitative tiers, each with narrative guidance (not just numeric): **Low** (1-2
scary moments, no casualties expected, may need healing), **Moderate** (could go badly
without resources; weaker PCs may go down; slim death chance), **High** (potentially
lethal; requires smart tactics/luck to survive).

### 6.3 Step 2 — XP Budget per Character table (lines 13525-13549) — full table

| Party Level | Low | Moderate | High |
|---|---|---|---|
| 1 | 50 | 75 | 100 |
| 2 | 100 | 150 | 200 |
| 3 | 150 | 225 | 400 |
| 4 | 250 | 375 | 500 |
| 5 | 500 | 750 | 1,100 |
| 6 | 600 | 1,000 | 1,400 |
| 7 | 750 | 1,300 | 1,700 |
| 8 | 1,000 | 1,700 | 2,100 |
| 9 | 1,300 | 2,000 | 2,600 |
| 10 | 1,600 | 2,300 | 3,100 |
| 11 | 1,900 | 2,900 | 4,100 |
| 12 | 2,200 | 3,700 | 4,700 |
| 13 | 2,600 | 4,200 | 5,400 |
| 14 | 2,900 | 4,900 | 6,200 |
| 15 | 3,300 | 5,400 | 7,800 |
| 16 | 3,800 | 6,100 | 9,800 |
| 17 | 4,500 | 7,200 | 11,700 |
| 18 | 5,000 | 8,700 | 14,200 |
| 19 | 5,500 | 10,700 | 17,200 |
| 20 | 6,400 | 13,200 | 22,000 |

**Formula**: `XP budget = table[party_level][difficulty] * number_of_characters_in_party`.
No group-size multiplier is applied afterward — this is the entire calculation.

### 6.4 Step 3 — Spend the budget (lines 13551-13566)
- Every creature's stat block has a fixed XP value (from CR, see §6.5 mapping).
- Subtract each added creature's XP from the budget; stop when you can't add another
  creature without exceeding it (a small unspent remainder is fine/expected).
- Three fully worked examples given (4x level-1 Low = 200 XP total budget; 5x level-3
  Moderate = 1,125 XP; 6x level-15 High = 46,800 XP), each showing 2-3 valid creature
  combinations that spend at or near the budget.

### 6.5 CR-to-XP mapping table (lines 16968-16992) — full table, CR 0 through 30

| CR | XP | CR | XP |
|---|---|---|---|
| 0 | 0 or 10 | 14 | 11,500 |
| 1/8 | 25 | 15 | 13,000 |
| 1/4 | 50 | 16 | 15,000 |
| 1/2 | 100 | 17 | 18,000 |
| 1 | 200 | 18 | 20,000 |
| 2 | 450 | 19 | 22,000 |
| 3 | 700 | 20 | 25,000 |
| 4 | 1,100 | 21 | 33,000 |
| 5 | 1,800 | 22 | 41,000 |
| 6 | 2,300 | 23 | 50,000 |
| 7 | 2,900 | 24 | 62,000 |
| 8 | 3,900 | 25 | 75,000 |
| 9 | 5,000 | 26 | 90,000 |
| 10 | 5,900 | 27 | 105,000 |
| 11 | 7,200 | 28 | 120,000 |
| 12 | 8,400 | 29 | 135,000 |
| 13 | 10,000 | 30 | 155,000 |

CR 0 is worth 0 XP normally, or 10 XP for specific "worth 10 XP" CR-0 monsters per stat
block notation (line 16972 shows "0 or 10" — the specific value is per-monster, not
universal).

Note: a monster's stat block XP is sometimes higher **"in Lair"** — e.g. Adult Red Dragon
is CR 17 = 18,000 XP normally, "or 20,000 in lair" (line 13563 example / line 21111
stat-block confirmation). This is the *only* surviving "lair" mechanic found in this SRD —
it changes CR/XP and Legendary Resistance uses/day, but there is **no accompanying "Lair
Actions" or "Regional Effects" mechanic anywhere in the document** (see §7.7).

### 6.6 Encounter-building troubleshooting guidance (lines 13567-13593) — qualitative, not
numeric: watch for >2 creatures per PC (favor fragile ones at low level), adjust on the fly
for absent players (remove creatures) or lucky/unlucky rolls (add reinforcements / have
enemies flee), avoid using many CR-0 creatures individually (use swarms instead), be wary
of a single creature whose CR exceeds party level dealing a one-shot kill (worked example:
CR-2 Ogre can one-shot a level-1 Wizard), and avoid monsters with features low-level
parties can't overcome at all.

---

## 7. Monster Stat Block Anatomy (docling.md lines 16815-17072)

Every field an engine must be able to store/compute, per the "Stat Block Overview" and
"Parts of a Stat Block" sections:

| Field | Line(s) | Rule |
|---|---|---|
| **Name** | 16821 | — |
| **Size** | 16834-16836 | Tiny/Small/Medium/Large/Huge/Gargantuan; some monsters offer a size choice. |
| **Creature Type** | 16838-16857 | 13 fixed types: Aberration, Beast, Celestial, Construct, Dragon, Elemental, Fey, Fiend, Giant, Humanoid, Monstrosity, Ooze, Plant, Undead. No inherent rules per type but referenced by spells/items/features. |
| **Descriptive Tags** | 16859-16861 | Parenthetical subtags after type (e.g. "Dragon (Chromatic)"); no rules of their own but effects may reference them. |
| **Alignment** | 16863-16867 | Default roleplay suggestion, changeable by GM; includes "Unaligned." |
| **Armor Class (AC)** | 16869-16871 | Includes natural armor, Dex, gear, other defenses — single final number. |
| **Initiative** | 16873-16877 | Modifier + a pre-rolled Initiative *score* in parentheses (GMs may skip rolling and just use the score); usually = Dex modifier but some monsters add extra (e.g. Proficiency Bonus). |
| **Hit Points** | 16879-16898 | Fixed number, or roll the parenthetical Hit Dice expression — never both. Hit Die size keyed to monster size (Tiny d4 through Gargantuan d20 per the Hit Dice by Size table); Con modifier x number of Hit Dice is added. |
| **Speed** | 16900-16902 | Base (walk) plus optional Burrow/Climb/Fly/Swim — all as separate named speeds. |
| **Ability Scores** | 16904-16906 | All six (Str/Dex/Con/Int/Wis/Cha), each with modifier and a separate saving-throw modifier column (proficient saves differ from raw ability modifier). |
| **Skills** | 16908-16910 | Named skill bonuses (ability modifier + Proficiency Bonus + any extra), listed only if present. |
| **Resistances/Vulnerabilities** | 16912-16914 | Per-damage-type entries, listed only if present. |
| **Immunities** | 16924-16926 | Combined entry: damage-type immunities listed before condition immunities in the same line. |
| **Gear** | 16928-16942 | Retrievable equipment list; stat-block flourishes for an item apply only while the monster wields it — a looted item reverts to plain 'Equipment' rules. Gear entry is non-exhaustive (cosmetic clothing excluded); anything described *outside* Gear is supernatural/non-recoverable. |
| **Senses** | 16946-16948 | Passive Perception always present; special senses (Darkvision, Blindsight, Tremorsense, Truesight) each carry a range in feet. |
| **Languages** | 16950-16952 | List, or "None"; a monster may understand but not speak a language (noted specially). |
| **Telepathy** | 16954-16956 | Range-limited mental communication, a distinct field from Languages. |
| **Challenge Rating (CR)** | 16958-16960 | Threat-level summary vs. a 4-PC party; drives PB and XP. |
| **Experience Points (XP)** | 16962-16986 | Derived from CR via the fixed table (§6.5); summoned-monster XP uses its own stat-block value unless a rule overrides. |
| **Proficiency Bonus (PB)** | 16993-17004 | Derived from CR via its own table (CR 0-4:+2, 5-8:+3, 9-12:+4, 13-16:+5, 17-20:+6, 21-24:+7, 25-28:+8, 29-30:+9) — note this table's CR bands do NOT align 1:1 with the XP table's bands. |
| **Traits** | 17006-17008 | Always-on or conditional passive features. |
| **Actions** | 17010-17032 | Attack Notation (melee/ranged, bonus, reach/range, Hit/Miss/Hit-or-Miss effect text), Saving Throw Effect Notation (DC, who saves, fail/success effect, "half damage only" shorthand), Damage Notation (flat number with die expression in parentheses — use one, not both). |
| **Multiattack** | 17034-17037 | A named Actions-list entry describing which/how-many sub-attacks (and any bundled special ability use) are made as part of one Attack action. |
| **Spellcasting** | 17038-17047 | Lists known/preparable spells, spellcasting ability, spell save DC (if needed), spell attack bonus (if needed); notes any component-ignoring shortcut; spells with 1+ minute cast times still require the Magic action each turn plus Concentration unless the action text overrides this. |
| **Bonus Action** | 17048-17050 | Separate stat-block section, only present if the monster has any. |
| **Reactions** | 17052-17054 | Separate section with explicit triggers. |
| **Legendary Actions** | 17056-17061 | Limited-use pool (count specified), one used immediately after another creature's turn ends, never while Incapacitated, refills fully at the start of the monster's own turn. Some named legendary actions cost more than 1 use ("Costs 2 Actions" pattern, observed in the 2014 JSON data but *not* observed anywhere in the 2024 docling.md monster entries sampled — see caveat below). |
| **Legendary Resistance** | 17098, 17287, etc. (not in the anatomy-overview text itself, but a near-universal Trait on legendary creatures) | "(N/Day, or N+1/Day in Lair)" — if the monster fails a save, it can choose to succeed instead; consumes one use. |
| **Limited Usage notations** | 17062-17072 | X/Day (Long Rest to regain); Recharge X-Y (roll 1d6 at the start of each of its turns, regains on X-Y, also recharges on Short/Long Rest); "Recharge after a Short or Long Rest" (no per-turn roll, just needs a rest). |

### 7.1 Hit Dice by Size table (line 16887-16894)
| Size | Hit Die | Avg HP/Die |
|---|---|---|
| Tiny | d4 | 2.5 |
| Small | d6 | 3.5 |
| Medium | d8 | 4.5 |
| Large | d10 | 5.5 |
| Huge | d12 | 6.5 |
| Gargantuan | d20 | 10.5 |

### 7.2 "Running a Monster" tactical AI guidance (lines 16916-16923) — not stat but behavior
rules an AI-controlled monster should follow: use limited-use high-damage abilities as
early/often as possible; use Multiattack whenever not using something stronger; use all
available Bonus Actions/Reactions/Legendary Actions as often as possible.

### 7.3 Full stat-block worked example verified (Adult Red Dragon, lines 21100-21141)
AC 19, Initiative +12 (22), HP 256 (19d12+133), Speed 40 ft / Climb 40 ft / Fly 80 ft,
Str 27/Dex 10/Con 25/Int 16/Wis 13/Cha 23 with separate save columns, Senses Blindsight 60
ft + Darkvision 120 ft + Passive Perception 23, Languages Common+Draconic, CR 17 (XP
18,000 or 20,000 in lair; PB +6). Traits: Legendary Resistance (3/Day, or 4/Day in Lair).
Actions: Multiattack (3x Rend, may replace one with Spellcasting->Scorching Ray), Rend
(melee +14, reach 10 ft, 1d10+8 Slashing + 2d4 Fire), Fire Breath (Recharge 5-6, DC 21 Dex
save, 60-ft Cone, 17d6 Fire / half on success), Spellcasting (Charisma, no material
components, DC 20, +12 to hit; At Will: Command lvl2/Detect Magic/Scorching Ray; 1/Day
Fireball). Legendary Actions: 3 uses (4 in Lair) — Commanding Presence (cast Command),
Fiery Rays (cast Scorching Ray), Pounce (move half Speed + one Rend).

### 7.4 Ancient Red Dragon comparison (lines 21144-21184) confirms scaling pattern: same
action *names* (Rend, Fire Breath, Spellcasting, same 3 Legendary Actions) but larger dice,
higher DCs, Gargantuan size, and an added `Skills` line (Perception +16, Stealth +7) and
`Immunities Fire` line not present on the Adult version — i.e., Skills/Immunities/
Vulnerabilities are all **optional per-monster fields**, confirmed present-when-relevant,
absent-when-not, exactly as documented at line 16824.

### 7.5 Non-dragon multiattack/spellcasting/trait sample (Priest, lines 20921-20939):
Multiattack (Mace or Radiant Flame in any combination), Spellcasting (Wisdom, DC 13, At
Will: Light/Thaumaturgy, 1/Day: Spirit Guardians), Bonus Actions: Divine Aid (3/Day) casts
one of 4 named spells using the same spellcasting stat.

### 7.6 Vulnerability/Immunity field format sample (Warhorse Skeleton, lines 21593-21609):
`Vulnerabilities Bludgeoning` / `Immunities Poison; Exhaustion, Poisoned` — confirms damage
types and condition names are semicolon-separated within one combined Immunities line, and
Vulnerabilities is its own separate line, exactly matching the anatomy description.

### 7.7 Confirmed absence: Lair Actions and Regional Effects
Grepped the entire monster section (lines 17073-24275, file end) and the full document for
`Lair Action`, `Regional Effect`, and `## Lair` headers: **zero matches anywhere**. Every
occurrence of "lair" in the whole file (54 total) is the "(N/Day, or N+1/Day in Lair)"
Legendary Resistance/XP modifier pattern only. This 2024 Creative-Commons SRD text does
**not** include the classic (2014 MM-style) Lair Actions / Regional Effects subsystem for
legendary creatures at all — this is a genuine content omission in the source document,
not a parsing/OCR failure (verified by checking the file's final 20 lines are intact prose,
not truncated). An engine targeting only this SRD text has no lair-action mechanic to
implement; if the codebase implements one, it was sourced from elsewhere (2014 MM, homebrew,
or another Cosmere/3rd-party doc).

### 7.8 Monster count
858 `##`-header lines fall in the A-Z monster range (17073-24275); after excluding the 6
repeating structural subheadings (Traits/Actions/Bonus Actions/Reactions/Legendary
Actions/Legendary Resistance), **252 distinct named monster/NPC stat-block entries**
remain (some entries, like "Skeletons" or "Bandits," bundle multiple named variants — e.g.
Skeleton + Warhorse Skeleton + Minotaur Skeleton under one shared header block — so 252 is
a header count, not a strict unique-creature count; some multi-column tables pack 2-3
statblocks side by side, as seen with Skeleton/Warhorse Skeleton/Minotaur Skeleton at
lines 21573-21620).

---

## 8. JSON Field Audit

### 8.1 `data/rules/srd/equipment.json` (237 entries: 37 Weapon, 13 Armor, 116 Adventuring
Gear, 31 Tools, 40 Mounts and Vehicles)

| Rule requirement | Present? | Field | Gap |
|---|---|---|---|
| Weapon damage dice + type | Yes | `damage.damage_dice`, `damage.damage_type.name` | — |
| Weapon category (Simple/Martial) | Yes | `weapon_category` | — |
| Melee/Ranged | Yes | `weapon_range` | — |
| Weapon properties | Yes | `properties[]` (index/name) | Only 2014's 11 properties possible (see weapon_properties.json audit); no 2024 additions |
| **Weapon Mastery property** | **No** | — | 2024-only concept; no `mastery` key anywhere on any weapon record |
| Thrown range (normal/long) | Yes | `throw_range.normal/long` | — |
| Ammunition range (normal/long) | Yes | `range.normal/long` (for ranged weapons) | — |
| Two-Handed / Versatile bonus damage | Partial | `two_handed_damage` key exists in schema | Not verified populated on every Versatile weapon; 2024 Versatile dice differ in a few cases from 2014 (schema drift risk) |
| Armor category (Light/Med/Heavy) | Yes | `armor_category` | — |
| Armor AC base + Dex bonus flag | Yes | `armor_class.base`, `armor_class.dex_bonus` | — |
| **Armor Dex cap (Medium armor max+2)** | Yes | `armor_class.max_bonus` | Present and correctly populated (verified on Chain Shirt: `max_bonus: 2`) |
| Armor Strength requirement | Yes | `str_minimum` | — |
| Armor Stealth disadvantage | Yes | `stealth_disadvantage` (bool) | — |
| **Armor Training gating (2024 concept)** | **No** | — | Schema has no field distinguishing "trained" vs "proficient" — irrelevant for 2014 data (2014 uses plain proficiency, not a training/no-training D20-Test-disadvantage rule) |
| Tool Ability/Utilize DC/Craft list | Partial | `desc[]` freetext for some; no structured DC field | Utilize DCs are only recoverable by parsing prose, not a queryable field |
| Coinage / currency conversion table | **No** | — | Not represented in this file at all; would need to be hardcoded elsewhere |
| Carrying capacity table | **No** | — | Not equipment-item data; absent from this file (expected — it's a Rules Glossary mechanic, not per-item) |
| Vehicle AC/HP/Damage Threshold | Yes | `speed`, `capacity`, `special` (varies) | Some ship-specific fields (Damage Threshold) not confirmed populated per-record; needs spot check |

### 8.2 `data/rules/srd/magic_items.json` (362 entries)

| Rule requirement | Present? | Field | Gap |
|---|---|---|---|
| Item category (Armor/Weapon/Ring/etc.) | Partial | `equipment_category.name` | Only 10 raw category strings, no distinction like "Wondrous Item" is present as its own literal string but categories aren't a closed validated enum in this file the way the 2024 rulebook's 9-category table is |
| Rarity | Yes | `rarity.name` | Includes a `"Varies"` literal for rarity-varies items (e.g. Spell Scrolls) — consumer code must special-case this string |
| **Attunement requirement (boolean/structured)** | **No** | — | Not a field at all; only recoverable by regex-scanning `desc[]` text for the substring "attunement" (176/362 items mention it in free text) |
| **Charges (count + recharge rule)** | **No** | — | Entirely absent as structured data; buried in `desc[]` prose only |
| **Curse flag** | **No** | — | No boolean; must string-search `desc[]` for "curse" |
| Weapon/armor type restriction (e.g. "Any Simple or Martial") | Partial | `variants[]` / `variant` (bool) exist but are empty arrays on most sampled records | The restriction text lives only in `desc[]`'s first line (e.g. "Armor (medium or heavy, but not hide), uncommon") |
| Mechanic-type taxonomy (static bonus/charges/spellcasting/etc., per §5.9) | **No** | — | No classification field of any kind; every mechanical effect is unstructured prose in `desc[]` |
| Sentient item block (Int/Wis/Cha/alignment/purpose) | **No** | — | Not represented; would need to be entirely hand-authored if implemented |
| Value in GP by rarity | **No** | — | Rarity-to-GP mapping (Common=100GP...Artifact=priceless) is not embedded; must be hardcoded from §5.4 separately |

### 8.3 `data/rules/srd/monsters.json` (334 entries)

| Rule requirement | Present? | Field | Gap |
|---|---|---|---|
| AC | Yes | `armor_class[].value` (+ `.type`, e.g. "natural") | — |
| HP (fixed + rollable) | Yes | `hit_points`, `hit_dice`, `hit_points_roll` | — |
| All movement speeds | Yes | `speed.walk/climb/fly/swim/burrow` | — |
| Six ability scores | Yes | `strength`...`charisma` (flat ints) | — |
| Saving throw bonuses | Yes | `proficiencies[]` filtered to `saving-throw-*` | Requires filtering a mixed proficiencies array rather than a dedicated saves object |
| Skill bonuses | Yes | `proficiencies[]` filtered to `skill-*` | Same mixed-array caveat |
| Damage resistances/immunities/vulnerabilities | Yes | `damage_resistances[]`, `damage_immunities[]`, `damage_vulnerabilities[]` | — |
| Condition immunities | Yes | `condition_immunities[]` | — |
| Senses (Darkvision/Blindsight/Tremorsense/Truesight + passive Perception) | Yes | `senses.{darkvision,blindsight,tremorsense,truesight,passive_perception}` | — |
| Languages | Yes | `languages` (single freetext string, not an array) | Comma-joined string, not a structured list — harder to query "does this monster speak Draconic" |
| CR / XP / Proficiency Bonus | Yes | `challenge_rating`, `xp`, `proficiency_bonus` | — |
| Traits ("special_abilities") | Yes | `special_abilities[]` (name, desc, optional `usage.type`/`usage.times`) | Usage/recharge encoded reasonably; matches X/Day pattern from §7's Limited Usage notation |
| Actions | Yes | `actions[]` (name, desc, attack_bonus, damage[], optional dc, optional multiattack sub-structure) | — |
| **Multiattack sub-structure** | Yes | `actions[].multiattack_type`, `.actions[]` (action_name/count/type) | Present and reasonably structured (verified on Adult Red Dragon) |
| Bonus actions | Yes | (implied by schema; not directly inspected but `reactions`/`legendary_actions` keys exist as siblings) | — |
| Reactions | Yes | `reactions` key present in schema | — |
| Legendary actions | Yes | `legendary_actions[]` (name, desc, optional dc, optional damage[]) | Encodes 2014's "Costs 2 Actions" pattern inline in the `name` string (e.g. `"Wing Attack (Costs 2 Actions)"`) rather than as a structured cost field |
| **Legendary Resistance uses/day** | Partial | Present as a `special_abilities[]` entry with `usage.times` | Works, but indistinguishable from any other X/Day trait without name-matching "Legendary Resistance" |
| **Lair Actions** | **No** | — | No `lair_actions` key anywhere in the schema (confirmed via full key enumeration) — consistent with this mechanic's absence from the assigned 2024 SRD text too (see §7.7), though for the *opposite* reason: 2014 Monster Manual does have lair actions for many legendary creatures, so this is a vendoring gap, not a rules gap, for the 2014 edition this file claims to represent |
| **Regional Effects** | **No** | — | Same as above |
| **CR/edition version tag** | **No** | — | No field states "this is 2014 data"; only inferable from the `/api/2014/` URL strings embedded in nested reference objects — an engine reading only top-level fields would not detect the edition |
| Forms (e.g. for shapechangers) | Yes | `forms` key present | Not inspected in depth; flagged for the implementation-audit agent |

### 8.4 `data/rules/srd/weapon_properties.json` (11 entries)

| Rule requirement | Present? | Field | Gap |
|---|---|---|---|
| Ammunition, Finesse, Heavy, Light, Loading, Reach, Thrown, Two-Handed, Versatile | Yes (9 of 10 2024 core properties) | `index`, `name` | "Range" is not listed as its own weapon property in this file (it's folded into the weapon record's own `range`/`throw_range` fields instead, which is actually consistent with how the 2024 rulebook treats Range as a sub-clause of Ammunition/Thrown rather than a standalone property — not a bug) |
| 2014-only "Monk" property | Present (extra) | `monk` | Not a 2024 concept; 2024 weapons no longer have a Monk tag (Monk class instead defines its own weapon list narratively) — this is dead weight for a 2024 implementation |
| 2014 "Special" property | Present (extra) | `special` | 2024 has no generic "Special" weapon property either |
| **All 8 Weapon Mastery properties (Cleave, Graze, Nick, Push, Sap, Slow, Topple, Vex)** | **No** | — | Completely absent — 0 of 8; this is the single largest structural gap between this file and the 2024 rules text, since Mastery is a first-class column in every 2024 weapon table row |

### 8.5 `data/rules/srd/damage_types.json` (13 entries)

| Rule requirement | Present? | Field | Gap |
|---|---|---|---|
| All 13 SRD damage types (Acid, Bludgeoning, Cold, Fire, Force, Lightning, Necrotic, Piercing, Poison, Psychic, Radiant, Slashing, Thunder) | Yes, all 13 | `index`, `name` | None — this file matches the 2024 damage type list exactly, since damage types didn't change between 2014 and 2024. This is the one file in the audited set with **no edition drift**. |

---

## 9. Cross-cutting engineering notes for the implementation-audit agent

1. **Weapon Mastery is a wholesale gap** in the vendored data (§8.4) even though it's a
   core 2024 combat mechanic baked into every single weapon (§1.4) — any code path that
   reads `weapon_properties.json` for mastery info will find nothing.
2. **Magic item mechanics are 100% unstructured prose** in the vendored JSON (§8.2) — an
   engine cannot programmatically distinguish a charge-based ring from a static-bonus
   ring without either an NLP layer or hand-authored overlay data. The taxonomy in §5.9
   is intended as the target schema for such an overlay.
3. **The 2024 encounter-difficulty system (§6) is fundamentally incompatible with the 2014
   CR-multiplier system.** If `components/policy.py` or any scenario/combat-difficulty
   code implements group-size multipliers, it is implementing the *wrong* system relative
   to the 2024 rulebook this project also vendors as its "most authoritative" source
   (per `docs/mechanics/README.md`).
4. **Lair Actions / Regional Effects are absent from the 2024 rules text entirely** (§7.7)
   but conspicuous by their absence from the 2014 JSON too, for the opposite reason
   (vendoring gap vs. genuine 2024 removal). Either way, there is no source in this repo's
   *current* SRD JSON to drive a lair-actions feature; one would need the 2014 Monster
   Manual text or a hand-authored table.
5. **`monsters.json`'s `languages` field is a single string, not a list** (§8.3) — any
   code doing `if "Draconic" in monster["languages"]` works but `for lang in
   monster["languages"]` would iterate characters, not languages; worth flagging as a
   subtle bug surface.
6. **No edition tag exists in any vendored JSON file** (§8.3) — the *only* way code can
   detect "this is 2014 data" is by string-matching `/api/2014/` inside nested reference
   URLs, which is fragile and easy to silently break during a future re-vendor.
