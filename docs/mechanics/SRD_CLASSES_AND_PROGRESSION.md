# SRD 5.2.1 Classes & Progression — Mechanics Catalogue

Source: `parsed_data/srd_cc_v5.2.1/docling.md` (2024 D&D 5e SRD, "SRD 5.2.1"). All
line numbers below cite that file. This is a mechanics inventory for a
game-engine implementation audit — it is exhaustive by design, not a rules
summary. Full spell lists (cantrip/level 1-9 spell tables) are intentionally
**out of scope**; only spellcasting *mechanics* (slots, prep rules, ability,
focus, ritual casting) are captured, since spell-by-spell effects belong to a
separate spells catalogue.

2024-edition note: **Weapon Mastery** is new this edition. **Fighting Styles**
are now **feats** (Fighting Style Feat category), not baked-in class options —
classes that grant "a Fighting Style feat of choice" reference the feats
catalogued in §6, not inline text.

---

## 1. Character Creation Pipeline

Steps, in order, per lines 907-915, 953-1305:

| Step | What it computes | Lines |
|---|---|---|
| 1. Choose a Class | Sets primary ability, hit die, proficiencies, level-1 features | 911, 917-951 |
| 2. Determine Origin | Background (ability score increases ×3, Origin feat, 2 skill profs, 1 tool prof, equipment) + Species (creature type, size, speed, traits) + 2 chosen languages (+Common = 3 total) | 912, 953-1043 |
| 3. Determine Ability Scores | Generate 6 scores (Standard Array `15,14,13,12,10,8` / 4d6-drop-lowest ×6 / 27-point buy), assign to abilities, **then apply background's ability increases** (+2/+1 split or +1/+1/+1 across its 3 listed abilities, cap 20), then derive modifiers | 913, 1045-1109 |
| 4. Choose Alignment | One of 9 alignments (flavor only, no mechanical effect) | 914, 1111-1145 |
| 5. Fill in Details | Record level‑1 class features; compute saving throws (ability mod + Prof Bonus if proficient), skills (ability mod + Prof Bonus if proficient), Passive Perception (`10 + Wis(Perception) mod`), HP max (class table, `Level 1 Hit Points by Class`), Hit Dice (1 of class's die type), Initiative (Dex mod), AC (`10 + Dex mod` unarmored, or per armor/class feature), attack bonuses (`Str/Dex mod + Prof Bonus` for weapons), spellcasting (`Spell save DC = 8 + spellcasting ability mod + Prof Bonus`; `Spell attack bonus = spellcasting ability mod + Prof Bonus`), spell slots/cantrips/prepared spells from class table | 915, 1147-1204 |

**2024 rule change to flag for implementation**: ability score increases now
come from **Background**, not Species (species traits are purely narrative/
mechanical-trait, no ASI). See Backgrounds table in §7 — every background
lists exactly 3 abilities; the character gets +2/+1 split among any two of
those three, or +1/+1/+1 across all three, capped at 20 (line 1093, 5584).

### Starting at Higher Levels (lines 1277-1298)

| Starting Level | Equipment/Money | Magic Items | Line |
|---|---|---|---|
| 1 | Normal starting equipment | — | — |
| 2-4 | Normal starting equipment | 1 Common | 1289 |
| 5-10 | 500 GP + 1d10×25 GP + normal starting equipment | 1 Common, 1 Uncommon | 1290 |
| 11-16 | 5,000 GP + 1d10×250 GP + normal starting equipment | 2 Common, 3 Uncommon, 1 Rare | 1291 |
| 17-20 | 20,000 GP + 1d10×250 GP + normal starting equipment | 2 Common, 4 Uncommon, 3 Rare, 1 Very Rare | 1292 |

Character starts with the minimum XP for that level (e.g. level 10 → 64,000 XP). Line 1298.

Bonus feats past level 20: 1 feat per 30,000 XP earned above 355,000 XP (line 1296).

---

## 2. Universal Progression Mechanics

### Character Advancement table (lines 1212-1236)

| Level | XP required | Proficiency Bonus |
|---|---|---|
| 1 | 0 | +2 |
| 2 | 300 | +2 |
| 3 | 900 | +2 |
| 4 | 2,700 | +2 |
| 5 | 6,500 | +3 |
| 6 | 14,000 | +3 |
| 7 | 23,000 | +3 |
| 8 | 34,000 | +3 |
| 9 | 48,000 | +4 |
| 10 | 64,000 | +4 |
| 11 | 85,000 | +4 |
| 12 | 100,000 | +4 |
| 13 | 120,000 | +5 |
| 14 | 140,000 | +5 |
| 15 | 165,000 | +5 |
| 16 | 195,000 | +5 |
| 17 | 225,000 | +6 |
| 18 | 265,000 | +6 |
| 19 | 305,000 | +6 |
| 20 | 355,000 | +6 |

### Ability Score Improvement levels (universal pattern across all 12 classes)

Every class grants "Ability Score Improvement" (feat or +2/+1+1 ASI, capped at
20) at levels **4, 8, 12, 16**. Rogue is the sole exception — it also gets
**ASI at level 10** (Rogue Features table, line 3901-3913; Rogue's ASI text at
line 3947 explicitly lists "levels 8, 10, 12, and 16" in addition to 4).
**Epic Boon** (a feat category, prerequisite level 19+) is granted at level 19
by every class as its own named feature row.

### Hit Dice / HP per level (lines 1171-1184, 1242-1255)

| Class | Hit Die | Level‑1 HP max | Fixed HP/level (levels 2+) |
|---|---|---|---|
| Barbarian | d12 | 12 + Con mod | 7 + Con mod |
| Fighter, Paladin, Ranger | d10 | 10 + Con mod | 6 + Con mod |
| Bard, Cleric, Druid, Monk, Rogue, Warlock | d8 | 8 + Con mod | 5 + Con mod |
| Sorcerer, Wizard | d6 | 6 + Con mod | 4 + Con mod |

Roll option: roll the class's Hit Die + Con mod (minimum 1) instead of taking
the fixed value (line 1242). A Constitution modifier increase retroactively
adds +1 HP max **per level attained** (line 1255).

### Extra Attack stacking rule (multiclass, line 1342-1346)

Extra Attack from multiple classes does **not** stack — cap is 2 attacks
unless a feature explicitly grants more (e.g. Fighter's Two Extra Attacks /
Three Extra Attacks). Warlock's Thirsting Blade invocation (grants Extra
Attack with pact weapon only) also does not stack with a class-based Extra
Attack.

### Level-up procedure (lines 1237-1255)

1. Choose a class to gain a level in (may differ from current class — multiclass rules apply).
2. Roll or take fixed Hit Die + Con mod, add to HP max (min 1 per level).
3. Record new class features for the new level.
4. Adjust Proficiency Bonus if the Character Advancement table changed it.
5. Adjust ability modifiers if a feat changed a score; retroactively adjust HP max if Con mod changed.

---

## 3. Multiclassing Rules (lines 1306-1395)

- **Prerequisite** (line 1310-1312): score of 13+ in the primary ability of
  *both* the new class and all current classes.
- **XP cost** (1314-1316): based on total character level, not per-class level.
- **HP/Hit Dice** (1318-1322): gain new class's HP as "levels after 1" (never
  the level-1 value unless total character level is 1); Hit Dice pool by die
  type from all classes combined.
- **Proficiency Bonus** (1324-1326): from total character level.
- **Proficiencies gained** (1328-1330): only a subset of the new class's
  level-1 proficiencies — each class's own "As a Multiclass Character" bullet
  list specifies exactly which (see per-class Core Traits tables below).
- **Armor Class** (1338-1340): if multiple features offer alternate AC calcs
  (e.g. Monk's Unarmored Defense + Sorcerer's Draconic Resilience), only one
  may be used at a time.
- **Extra Attack** (1342-1346): does not stack across classes (see §2).
- **Spellcasting** (1348-1370):
  - **Spells Prepared**: computed per class individually, as if single-classed.
  - **Cantrip scaling**: uses total character level.
  - **Spell Slots**: sum (a) full levels in Bard/Cleric/Druid/Sorcerer/Wizard,
    (b) **half** (round up) of Paladin and Ranger levels; look up that total
    on the Multiclass Spellcaster table (below) for slots. Warlock's Pact
    Magic slots are entirely separate and are not part of this sum.
  - **Pact Magic** interaction: Warlock Pact Magic slots can cast prepared
    spells from Spellcasting-feature classes, and vice versa.

### Multiclass Spellcaster: Spell Slots per Spell Level (lines 1373-1394)

| Combined Level | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|
| 1 | 2 | - | - | - | - | - | - |
| 2 | 3 | - | - | - | - | - | - |
| 3 | 4 | 2 | - | - | - | - | - |
| 4 | 4 | 3 | - | - | - | - | - |
| 5 | 4 | 3 | 2 | - | - | - | - |
| 6 | 4 | 3 | 3 | - | - | - | - |
| 7 | 4 | 3 | 3 | 1 | - | - | - |
| 8 | 4 | 3 | 3 | 2 | - | - | - |
| 9 | 4 | 3 | 3 | 3 | 1 | - | - |
| 10 | 4 | 3 | 3 | 3 | 2 | - | - |
| 11 | 4 | 3 | 3 | 3 | 2 | 1 | - |
| 12 | 4 | 3 | 3 | 3 | 2 | 1 | - |
| 13 | 4 | 3 | 3 | 3 | 2 | 1 | 1 |
| 14 | 4 | 3 | 3 | 3 | 2 | 1 | 1 |
| 15 | 4 | 3 | 3 | 3 | 2 | 1 | 1 |
| 16 | 4 | 3 | 3 | 3 | 2 | 1 | 1 |
| 17 | 4 | 3 | 3 | 3 | 2 | 1 | 1 |
| 18 | 4 | 3 | 3 | 3 | 3 | 1 | 1 |
| 19 | 4 | 3 | 3 | 3 | 3 | 2 | 1 |
| 20 | 4 | 3 | 3 | 3 | 3 | 2 | 2 |

(Spell level 8-9 columns never populate under this table — those levels are
unreachable via multiclass spell-slot math and require single-class
progression.)

---

## 4. Per-Class Feature Inventory

Below: 12 classes × full level 1-20 table (including the one SRD-provided
subclass, fully detailed). Every row cites its SRD line(s).

### 4.1 Barbarian

**Core Traits** (1513-1522): Primary Str · d12 HP die · Saves Str/Con · Skills
choose 2 (Animal Handling, Athletics, Intimidation, Nature, Perception,
Survival) · Weapons Simple+Martial · Armor Light/Medium/Shield · Equipment (A)
Greataxe+4 Handaxes+Explorer's Pack+15 GP or (B) 75 GP. Multiclass grant
(1559): Hit Die, Martial weapon proficiency, Shield training only.

| Level | Feature | Line(s) | Effect | Recharge |
|---|---|---|---|---|
| 1 | Rage | 1566-1587 | Bonus Action, not in Heavy armor; Resistance to B/P/S; +2 Rage Damage on Str attacks; Advantage Str checks/saves; can't concentrate/cast; lasts to end of next turn, extendable by attack/forced save/Bonus Action, max 10 min; 2 uses | 1/Short Rest, all/Long Rest |
| 1 | Unarmored Defense | 1588-1590 | AC = 10 + Dex + Con mod unarmored (Shield OK) | Passive |
| 1 | Weapon Mastery | 1592-1596 | Mastery on 2 Simple/Martial Melee weapon kinds; count 2→3→4 at lvl 4/10 | Swap choice on Long Rest |
| 2 | Danger Sense | 1598-1600 | Advantage Dex saves unless Incapacitated | Passive |
| 2 | Reckless Attack | 1602-1604 | Advantage on Str attacks until next turn; attacks vs you also gain Advantage | At-will, 1/turn trigger |
| 3 | Barbarian Subclass | 1606-1608 | Choose Path of the Berserker | — |
| 3 | Primal Knowledge | 1610-1614 | +1 skill; while raging use Str for Acrobatics/Intimidation/Perception/Stealth/Survival | Passive/at-will while raging |
| 4 | Ability Score Improvement | 1616-1618 | ASI/feat; repeats 8, 12, 16 | — |
| 5 | Extra Attack | 1620-1622 | Attack twice | Passive |
| 5 | Fast Movement | 1624-1626 | +10 ft speed unarmored/no Heavy armor | Passive |
| 6 | Subclass feature | 1539 | Mindless Rage (see subclass) | — |
| 7 | Feral Instinct | 1628-1630 | Advantage on Initiative | Passive |
| 7 | Instinctive Pounce | 1632-1634 | Move ½ Speed as part of Rage's Bonus Action | At Rage entry |
| 9 | Brutal Strike | 1636-1642 | Forgo Reckless Attack Advantage on one Str attack (no Disadvantage); hit → extra 1d10 dmg + 1 effect: Forceful Blow (push 15 ft + move ½ Speed no OA) or Hamstring Blow (target Speed −15 ft to your next turn, latest overrides) | At-will (tied to Reckless Attack) |
| 10 | Subclass feature | 1543 | Retaliation (see subclass) | — |
| 11 | Relentless Rage | 1644-1648 | On drop to 0 HP while raging: DC 10 Con save; success → HP = 2× Barbarian level; DC +5 per subsequent use, resets to 10 on Short/Long Rest | Unlimited, escalating DC |
| 12 | Ability Score Improvement | 1545 | ASI/feat | — |
| 13 | Improved Brutal Strike | 1650-1656 | New options: Staggering Blow (target Disadvantage next save, no OA until your next turn); Sundering Blow (+5 to next attack vs target before your next turn, 1 bonus max) | At-will (tied to Brutal Strike) |
| 14 | Subclass feature | 1547 | Intimidating Presence (see subclass) | — |
| 15 | Persistent Rage | 1658-1662 | On Initiative roll, regain all Rage uses (1/Long Rest); Rage auto-lasts 10 min; ends only on Unconscious or Heavy armor | 1/Long Rest |
| 16 | Ability Score Improvement | 1549 | ASI/feat | — |
| 17 | Improved Brutal Strike | 1664-1666 | Extra damage → 2d10; use 2 different effects at once | Passive upgrade |
| 18 | Indomitable Might | 1668-1670 | Str check/save total < Str score → use score instead | Passive |
| 19 | Epic Boon | 1672-1674 | Epic Boon feat (Boon of Irresistible Offense recommended) | — |
| 20 | Primal Champion | 1676-1678 | Str and Con +4 each, max 25 | Passive |

Full progression columns (Barbarian Features table, 1532-1553): **Rages** =
2,2,3,3,3,4,4,4,4,4,4,5,5,5,5,5,6,6,6,6 (lvl 1-20). **Rage Damage** = +2
(1-8), +3 (9-15), +4 (16-20). **Weapon Mastery slots** = 2 (1-3), 3 (4-9), 4
(10-20).

**Subclass: Path of the Berserker** (1680-1703)

| Level | Feature | Line | Effect | Recharge |
|---|---|---|---|---|
| 3 | Frenzy | 1686-1688 | While raging + Reckless Attack: first Str-attack hit deals extra damage = Rage Damage bonus in d6s, weapon's damage type | At-will while raging |
| 6 | Mindless Rage | 1690-1692 | Immune Charmed/Frightened while raging; entering Rage ends those conditions | Passive |
| 10 | Retaliation | 1694-1696 | Reaction: melee attack vs a creature that damages you within 5 ft | 1/trigger, Reaction |
| 14 | Intimidating Presence | 1698-1702 | Bonus Action, 30-ft Emanation, Wis save DC 8+Str mod+Prof; fail → Frightened 1 min, repeat save each turn end | 1/Long Rest, refreshable by expending a Rage use |

**Resource types**: Rage uses (2-6; 1/Short Rest, all/Long Rest), Weapon
Mastery slots (2-4, swap on Long Rest), Relentless Rage (escalating DC,
resets on rest), Intimidating Presence (1/Long Rest, refreshable via Rage).

---

### 4.2 Bard

**Core Traits** (1706-1716): Primary Cha · d8 HP die · Saves Dex/Cha · Skills
choose any 3 · Tools choose 3 Musical Instruments · Weapons Simple · Armor
Light · Equipment (A) Leather Armor+2 Daggers+Instrument+Entertainer's
Pack+19 GP or (B) 90 GP. Multiclass grant (1754): Hit Die, 1 skill, 1
Instrument, Light armor training.

| Level | Feature | Line(s) | Effect | Recharge |
|---|---|---|---|---|
| 1 | Bardic Inspiration | 1761-1771 | Bonus Action, target within 60 ft that sees/hears you gets a d6 die; within 1 hr add to a failed d20 Test; 1 die/creature max; uses = Cha mod (min 1) | All/Long Rest (until lvl5) |
| 1 | Spellcasting | 1773-1795 | 2 cantrips (+1 at 4, +1 at 10); prepare 4 spells scaling per table (4,5,6,7,9,10,11,12,14,15,16,16,17,17,18,18,19,20,21,22 for lvl 1-20); slots per table; Cha-based; Musical Instrument focus | Slots: Long Rest |
| 2 | Expertise | 1797-1801 | Double Prof Bonus on 2 chosen skills; +2 more at lvl 9 | Passive |
| 2 | Jack of All Trades | 1803-1807 | +½ Prof Bonus (round down) on checks with skills you lack, that don't already add Prof Bonus | Passive |
| 3 | Bard Subclass | 1809-1811 | Choose College of Lore | — |
| 4 | Ability Score Improvement | 1813-1815 | ASI/feat; repeats 8, 12, 16 | — |
| 5 | Font of Inspiration | 1817-1821 | Inspiration regains on Short or Long Rest; spend a spell slot (no action) to regain 1 use; die → d8 | Short/Long Rest |
| 6 | Subclass feature | 1734 | Magical Discoveries (see subclass) | — |
| 7 | Countercharm | 1823-1825 | Reaction: reroll (w/ Advantage) a failed save vs Charmed/Frightened for self or ally within 30 ft | At-will, Reaction |
| 8 | Ability Score Improvement | 1736 | ASI/feat | — |
| 9 | Expertise | 1801 | +2 more skills gain Expertise (total 4) | Passive |
| 10 | Magical Secrets | 1827-1829 | New prepared spells may come from Bard/Cleric/Druid/Wizard lists; die → d10 | — |
| 11 | — | 1739 | No new feature | — |
| 12 | Ability Score Improvement | 1740 | ASI/feat | — |
| 13 | — | 1741 | No new feature | — |
| 14 | Subclass feature | 1742 | Peerless Skill (see subclass) | — |
| 15 | — | 1743 | No new feature; die → d12 | — |
| 16 | Ability Score Improvement | 1744 | ASI/feat | — |
| 17 | — | 1745 | No new feature | — |
| 18 | Superior Inspiration | 1831-1833 | On Initiative roll, regain uses up to 2 if below | Passive trigger |
| 19 | Epic Boon | 1835-1837 | Epic Boon feat (Boon of Spell Recall recommended) | — |
| 20 | Words of Creation | 1839-1841 | Always prepared: Power Word Heal & Power Word Kill; can hit 2nd target within 10 ft of first | Passive/spell-tied |

Bardic Die: d6 (1-4), d8 (5-9), d10 (10-14), d12 (15-20). Cantrips known: 2
(1-3), 3 (4-9), 4 (10-20).

**Subclass: College of Lore** (2087-2109)

| Level | Feature | Line | Effect | Recharge |
|---|---|---|---|---|
| 3 | Bonus Proficiencies | 2093-2095 | Proficiency w/ 3 skills | — |
| 3 | Cutting Words | 2097-2099 | Reaction, expend Inspiration use: see a creature within 60 ft roll damage/check/attack; roll die, subtract from that roll | 1/trigger, consumes Inspiration use |
| 6 | Magical Discoveries | 2101-2105 | Learn 2 spells (Cleric/Druid/Wizard list) always prepared; replace 1/level gained | — |
| 14 | Peerless Skill | 2107-2109 | On failed check/attack, expend Inspiration use: roll die, add to d20; if still fails, use not expended | Consumes Inspiration use (refunded on failure) |

**Resource types**: Bardic Inspiration uses (= Cha mod, min 1; Long Rest only
until lvl5, then Short/Long Rest; die d6→d8→d10→d12), spell slots (full
caster, Long Rest), Expertise (permanent, not consumable).

**OCR garbling flagged**: Lines 1960, 1982-2065 — the Level 5/6/7 Bard spell
tables are malformed. Line 1960 merges "Level 5 Bard Spells Spell" into one
header cell; lines 1982-2065 (Level 6 & 7) collapse entirely into disjoint
plain-text runs — spell names, School, and Special columns are dumped as
separate line lists rather than aligned table rows (e.g. line 2024 runs
"Teleport School Necromancy Divination... Special" as one garbled line
followed by orphaned "C", "C, M", "M" fragments). Not reconstructed since
spell lists are out of scope; flagged here in case a downstream reader infers
spell-level mechanics from this section.

---

### 4.3 Cleric

**Core Traits** (2113-2122): Primary Wis · d8 HP die · Saves Wis/Cha · Skills
choose 2 (History, Insight, Medicine, Persuasion, Religion) · Weapons Simple ·
Armor Light/Medium/Shield · Equipment (A) Chain Shirt+Shield+Mace+Holy
Symbol+Priest's Pack+7 GP or (B) 110 GP. Multiclass grant (2159): Hit Die,
Light/Medium armor + Shield training.

| Level | Feature | Line(s) | Effect | Recharge |
|---|---|---|---|---|
| 1 | Spellcasting | 2166-2188 | 3 cantrips (+1 at 4, +1 at 10, total 5 by lvl18); prepare 4 spells scaling per table (4,5,6,7,9,10,11,12,14,15,16,16,17,17,18,18,19,20,21,22); slots per table, Long Rest; full prepared-list swap on Long Rest; Wis-based; Holy Symbol focus | Long Rest |
| 1 | Divine Order | 2190-2196 | Choose Protector (Martial weapon prof + Heavy armor training) OR Thaumaturge (+1 cantrip; bonus to Int Arcana/Religion checks = Wis mod, min +1) | Passive, permanent |
| 2 | Channel Divinity | 2198-2210 | 2 uses; Divine Spark (Magic action, 30 ft: 1d8+Wis mod heal OR force Con save, fail=Necrotic/Radiant dmg=total, success=half; extra d8 at lvl 7/13/18→2d8/3d8/4d8) + Turn Undead (Magic action, 30 ft, Wis save DC=spell DC, fail=Frightened+Incapacitated 1 min, ends on damage/your Incap/death) | 1/Short Rest, all/Long Rest |
| 3 | Cleric Subclass | 2212-2214 | Choose Life Domain | — |
| 4 | Ability Score Improvement | 2216-2218 | ASI/feat; repeats 8, 12, 16 | — |
| 5 | Sear Undead | 2220-2222 | Turn Undead: roll Wis-mod d8s (min 1d8); failed-save Undead take Radiant dmg=total; doesn't end Turn effect | Tied to Turn Undead (Channel Div use) |
| 6 | Subclass feature | 2141 | Blessed Healer (see subclass) | — |
| 7 | Blessed Strikes | 2224-2230 | Choose once: Divine Strike (1/turn weapon hit, extra 1d8 Necrotic/Radiant) OR Potent Spellcasting (+Wis mod dmg on cantrips) | Passive; 1/turn |
| 8 | Ability Score Improvement | 2143 | ASI/feat | — |
| 9 | — | 2144 | No new feature | — |
| 10 | Divine Intervention | 2232-2234 | Magic action: cast any Cleric spell ≤lvl5 (no Reaction req'd) free of slot/Material cost | 1/Long Rest |
| 11 | — | 2146 | No new feature | — |
| 12 | Ability Score Improvement | 2147 | ASI/feat | — |
| 13 | — | 2148 | No new feature | — |
| 14 | Improved Blessed Strikes | 2236-2242 | Divine Strike→2d8; OR Potent Spellcasting grants Temp HP=2×Wis mod on cantrip dmg to self/ally within 60 ft | Passive |
| 15 | — | 2150 | No new feature | — |
| 16 | Ability Score Improvement | 2151 | ASI/feat | — |
| 17 | Subclass feature | 2152 | Supreme Healing (see subclass) | — |
| 18 | — | 2153 | No new feature (Channel Div uses→4) | — |
| 19 | Epic Boon | 2244-2246 | Epic Boon feat (Boon of Fate recommended) | — |
| 20 | Greater Divine Intervention | 2248-2250 | Divine Intervention may select Wish; if used, unusable again until 2d4 Long Rests | Recharge: 2d4 Long Rests (only if Wish chosen) |

Channel Divinity uses: 2 (lvl2-5), 3 (lvl6-17), 4 (lvl18-20).

**Subclass: Life Domain** (2416-2452)

| Level | Feature | Line | Effect | Recharge |
|---|---|---|---|---|
| 3 | Disciple of Life | 2424-2426 | Slot-cast healing spells grant additional HP on cast = 2 + slot level | Passive |
| 3 | Life Domain Spells | 2428-2439 | Always-prepared bonus spells: lvl3 Aid/Bless/Cure Wounds/Lesser Restoration; lvl5 Mass Healing Word/Revivify; lvl7 Aura of Life/Death Ward; lvl9 Greater Restoration/Mass Cure Wounds | Passive, doesn't count against prep total |
| 3 | Preserve Life | 2441-2443 | Magic action, expend Channel Div use: HP pool = 5× Cleric level, split among Bloodied within 30 ft (self OK); none restored above half max | Consumes 1 Channel Divinity use |
| 6 | Blessed Healer | 2445-2447 | After slot-cast heal on another, regain HP = 2 + slot level | Passive, triggered |
| 17 | Supreme Healing | 2449-2451 | Healing dice use max value instead of rolling | Passive |

**Resource types**: Spell slots (Long Rest), Channel Divinity uses (2-4;
1/Short Rest, all/Long Rest), Divine Intervention (1/Long Rest, or 2d4-Long-
Rest cadence at lvl20 if Wish used), Preserve Life pool (5×level, consumes 1
Channel Divinity use).

---

### 4.4 Druid

**Core Traits** (2455-2465): Primary Wis · d8 HP die · Saves Int/Wis · Skills
choose 2 (Animal Handling, Arcana, Insight, Medicine, Nature, Perception,
Religion, Survival) · Weapons Simple · Tools Herbalism Kit · Armor
Light/Shield · Equipment (A) Leather Armor+Shield+Sickle+Druidic Focus
(Quarterstaff)+Explorer's Pack+Herbalism Kit+9 GP or (B) 50 GP. Multiclass
grant (2502): Hit Die, Light armor + Shield training.

| Level | Feature | Line(s) | Effect | Recharge |
|---|---|---|---|---|
| 1 | Spellcasting | 2509-2531 | 2 cantrips (+1 at 4, +1 at 10); prepare 4 spells scaling per table (4,5,6,7,9,10,11,12,14,15,16,16,17,17,18,18,19,20,21,22); slots per table, Long Rest; full swap on Long Rest; Wis-based; Druidic Focus | Long Rest |
| 1 | Druidic | 2533-2537 | Know Druidic secret language; always have Speak with Animals prepared; hidden-message DC 15 Int(Investigation) to spot presence | Passive |
| 1 | Primal Order | 2539-2545 | Choose Magician (+1 cantrip; bonus to Int Arcana/Nature = Wis mod, min +1) OR Warden (Martial weapon prof + Medium armor training) | Passive, permanent |
| 2 | Wild Shape | 2547-2559 | Bonus Action, shape-shift into known Beast form; duration = ½ Druid level (hrs) or until reuse/Incapacitated/death; 2 uses at lvl2; know 4 forms (max CR 1/4, no Fly), swappable 1/Long Rest | 1/Short Rest, all/Long Rest |
| 2 | Wild Companion | 2576-2580 | Magic action, expend a spell slot or Wild Shape use: cast Find Familiar (no Material); familiar is Fey, disappears on Long Rest | Consumes slot or Wild Shape use |
| 3 | Druid Subclass | 2582-2584 | Choose Circle of the Land | — |
| 4 | Ability Score Improvement | 2586-2588 | ASI/feat; repeats 8, 12, 16 | — |
| 5 | Wild Resurgence | 2590-2594 | 1/turn: if 0 Wild Shape uses left, expend a spell slot (no action) for 1 use; also 1/Long Rest expend a Wild Shape use (no action) for a level-1 slot | Long Rest (2nd effect) |
| 6 | Subclass feature | 2477 | Natural Recovery (see subclass) | — |
| 7 | Elemental Fury | 2596-2602 | Choose once: Potent Spellcasting (+Wis mod dmg on cantrips) OR Primal Strike (1/turn extra 1d8 Cold/Fire/Lightning/Thunder on weapon or Beast-form hit) | Passive; 1/turn |
| 8 | Ability Score Improvement | 2479 | ASI/feat | — |
| 9 | — | 2480 | No new feature | — |
| 10 | Subclass feature | 2481 | Nature's Ward (see subclass) | — |
| 11 | — | 2482 | No new feature | — |
| 12 | Ability Score Improvement | 2483 | ASI/feat | — |
| 13 | — | 2484 | No new feature | — |
| 14 | Subclass feature | 2485 | Nature's Sanctuary (see subclass) | — |
| 15 | Improved Elemental Fury | 2604-2610 | Potent Spellcasting: cantrip range ≥10 ft gets +300 ft; OR Primal Strike →2d8 | Passive |
| 16 | Ability Score Improvement | 2487 | ASI/feat | — |
| 17 | — | 2488 | No new feature (Wild Shape uses→4) | — |
| 18 | Beast Spells | 2612-2614 | Can cast spells while in Wild Shape (except costly/consumed Material components) | Passive |
| 19 | Epic Boon | 2616-2618 | Epic Boon feat (Boon of Dimensional Travel recommended) | — |
| 20 | Archdruid | 2620-2628 | Evergreen Wild Shape (regain 1 use on Initiative roll if none left); Nature Magician (convert Wild Shape uses into a slot, 2 levels/use, 1/Long Rest); Longevity (ages 1 yr per 10) | Nature Magician: 1/Long Rest |

Wild Shape uses progression: 2 (lvl2-5), 3 (lvl6-16), 4 (lvl17-20). **Beast
Shapes table** (2561-2567): Known Forms/Max CR/Fly — lvl2: 4 forms, CR 1/4, no
Fly; lvl4: 6 forms, CR 1/2, no Fly; lvl8: 8 forms, CR 1, Fly allowed.

**Subclass: Circle of the Land** (2796-2927)

| Level | Feature | Line | Effect | Recharge |
|---|---|---|---|---|
| 3 | Circle of the Land Spells | 2802-2886 | On Long Rest choose a land type (arid/polar/temperate/tropical); always-prepared spell list per land per Druid level (3/5/7/9) | Reselect on Long Rest |
| 3 | Land's Aid | 2899-2903 | Magic action, expend Wild Shape use: 10-ft Sphere within 60 ft, Con save vs spell DC, fail=2d6 Necrotic (half on success), 1 chosen creature heals 2d6; scales to 3d6 at lvl10, 4d6 at lvl14 | Consumes 1 Wild Shape use |
| 6 | Natural Recovery | 2905-2909 | 1/Long Rest cast a prepared Circle Spell free; also on Short Rest recover slots totalling ≤½ Druid level (round up), none level 6+ | 1/Long Rest each |
| 10 | Nature's Ward | 2911-2920 | Immune Poisoned; Resistance to land-associated type: Arid=Fire, Polar=Cold, Temperate=Lightning, Tropical=Poison | Passive |
| 14 | Nature's Sanctuary | 2922-2927 | Magic action, expend Wild Shape use: 15-ft Cube within 120 ft, Half Cover + Nature's Ward Resistance for allies, lasts 1 min; move Cube 60 ft as Bonus Action | Consumes 1 Wild Shape use |

**Resource types**: Spell slots (Long Rest), Wild Shape uses (2-4; 1/Short
Rest, all/Long Rest, convertible to/from spell slots via Wild Resurgence and
Archdruid), Natural Recovery (1/Long Rest to free-cast, 1/Short Rest to
recover slots).

**OCR garbling flagged**: Lines 2760-2795 — Level 6-9 Druid spell tables
collapse into run-on prose similar to Bard's issue. Lines 2806-2895 (Circle of
the Land per-land spell tables) are severely garbled: land names, level
numbers, and spell names are scattered across disconnected lines (e.g. lines
2828-2897 interleave "Circle Spells", isolated commas, and spell names
divorced from their land/level pairing — the Tropical Land table at 2880-2885
is the only one that parsed as a clean table). Reconstructed only the
Tropical Land table cleanly; Arid/Polar/Temperate entries above are
best-effort re-pairing from context and should be verified against the
official 2024 PHB before being trusted as ground truth.

---

### 4.5 Fighter

**Core Traits** (2930-2939): Primary Str or Dex · d10 HP die · Saves Str/Con ·
Skills choose 2 (Acrobatics, Animal Handling, Athletics, History, Insight,
Intimidation, Persuasion, Perception, Survival) · Weapons Simple+Martial ·
Armor Light/Medium/Heavy/Shield · Equipment (A) Chain Mail+Greatsword+
Flail+8 Javelins+Dungeoneer's Pack+4 GP, (B) Studded Leather+Scimitar+
Shortsword+Longbow+20 Arrows+Quiver+Dungeoneer's Pack+11 GP, or (C) 155 GP.
Multiclass grant (2975): Hit Die, Martial weapon proficiency, Light/Medium
armor + Shield training.

| Level | Feature | Line(s) | Effect | Recharge |
|---|---|---|---|---|
| 1 | Fighting Style | 2982-2986 | Gain a Fighting Style feat (Defense recommended); swappable each level gained | — |
| 1 | Second Wind | 2988-2994 | Bonus Action: regain 1d10 + Fighter level HP; 2 uses | 1/Short Rest, all/Long Rest |
| 1 | Weapon Mastery | 2996-3000 | Mastery on 3 Simple/Martial weapon kinds; count 3→4→5→6 at lvl 4/10/16 | Swap on Long Rest |
| 2 | Action Surge | 3002-3006 | Extra action (not Magic action) on your turn; 1 use; 2 uses (once/turn) from lvl17 | 1/Short or Long Rest |
| 2 | Tactical Mind | 3008-3010 | Expend Second Wind use on failed check: roll 1d10, add to check; not expended if still fails | Consumes Second Wind use (refunded on failure) |
| 3 | Fighter Subclass | 3012-3014 | Choose Champion | — |
| 4 | Ability Score Improvement | 3016-3018 | ASI/feat; repeats 6, 8, 12, 14, 16 | — |
| 5 | Extra Attack | 3020-3022 | Attack twice | Passive |
| 5 | Tactical Shift | 3024-3026 | Bonus-Action Second Wind → move ½ Speed, no OA | Tied to Second Wind |
| 9 | Indomitable | 3028-3032 | Reroll a failed save w/ bonus = Fighter level; must use new roll; 1 use; 2 uses from lvl13, 3 from lvl17 | Long Rest |
| 9 | Tactical Master | 3034-3036 | Replace a weapon's mastery property with Push/Sap/Slow for one attack | At-will |
| 11 | Two Extra Attacks | 3038-3040 | Attack three times | Passive |
| 13 | Studied Attacks | 3042-3044 | Miss vs a creature → Advantage on next attack vs it before end of next turn | Passive/triggered |
| 19 | Epic Boon | 3046-3048 | Epic Boon feat (Boon of Combat Prowess recommended) | — |
| 20 | Three Extra Attacks | 3050-3052 | Attack four times | Passive |

Second Wind uses: 2 (lvl1-9), 3 (lvl10-16 — table shows 3? see note below), 4
(lvl10-20 per table col). **Note**: table (2943-2964) shows Second Wind column
= 2,2,2,3,3,3,3,3,3,4,4,4,4,4,4,4,4,4,4,4 for levels 1-20 (jump to 3 at lvl4,
to 4 at lvl10). Weapon Mastery slots = 3 (lvl1-3), 4 (lvl4-9), 5 (lvl10-15), 6
(lvl16-20).

**Subclass: Champion** (3054-3089)

| Level | Feature | Line | Effect | Recharge |
|---|---|---|---|---|
| 3 | Improved Critical | 3060-3062 | Crit on 19-20 | Passive |
| 3 | Remarkable Athlete | 3064-3068 | Advantage Initiative + Str(Athletics); after a Crit, move ½ Speed no OA | Passive |
| 7 | Additional Fighting Style | 3070-3072 | Gain another Fighting Style feat | — |
| 10 | Heroic Warrior | 3074-3076 | Give self Heroic Inspiration at start of turn if lacking it | At-will (combat only) |
| 15 | Superior Critical | 3078-3080 | Crit on 18-20 | Passive |
| 18 | Survivor | 3082-3088 | Defy Death (Advantage Death Saves; 18-20 = auto-20 result); Heroic Rally (regain 5+Con mod HP at start of turn if Bloodied & alive) | Passive |

**Resource types**: Second Wind uses (2-4; 1/Short Rest, all/Long Rest),
Action Surge (1-2 uses/rest, only 1/turn), Weapon Mastery slots (3-6, swap on
Long Rest), Indomitable (1-3 uses/Long Rest).

---

### 4.6 Monk

**Core Traits** (3092-3102): Primary Dex+Wis · d8 HP die · Saves Str/Dex ·
Skills choose 2 (Acrobatics, Athletics, History, Insight, Religion, Stealth) ·
Weapons Simple + Martial-with-Light · Tools choose 1 Artisan's Tools/Musical
Instrument · Armor None · Equipment (A) Spear+5 Daggers+chosen tool+
Explorer's Pack+11 GP or (B) 50 GP. Multiclass grant (3113): Hit Die only.

| Level | Feature | Line(s) | Effect | Recharge |
|---|---|---|---|---|
| 1 | Martial Arts | 3145-3158 | Unarmed/Monk-weapon-only, no armor/Shield: Bonus Action Unarmed Strike; 1d6 die (scales, see below) usable in place of normal dmg; use Dex instead of Str for attack/damage/Grapple-Shove DC | Passive |
| 1 | Unarmored Defense | 3160-3162 | AC = 10 + Dex + Wis mod, no armor/Shield | Passive |
| 2 | Monk's Focus | 3164-3178 | Focus Points pool (2 at lvl2, scales — see below); fuels Flurry of Blows (1 pt: 2 Unarmed Strikes as Bonus Action), Patient Defense (free: Disengage as Bonus Action; 1 pt: + Dodge too), Step of the Wind (free: Dash as Bonus Action; 1 pt: + Disengage, double jump distance); save DC = 8+Wis mod+Prof | 1/Short or Long Rest for all points |
| 2 | Unarmored Movement | 3180-3182 | +10 ft speed unarmored/no Shield; scales (see below) | Passive |
| 2 | Uncanny Metabolism | 3184-3188 | On Initiative roll: regain all Focus Points + roll Martial Arts die, heal Monk level + roll | 1/Long Rest |
| 3 | Deflect Attacks | 3190-3194 | Reaction on B/P/S hit: reduce dmg by 1d10+Dex mod+Monk level; if reduced to 0, spend 1 Focus Point to redirect: target Dex save or take 2× Martial Arts die + Dex mod dmg (same type) | Reaction at-will; redirect consumes 1 Focus Point |
| 3 | Monk Subclass | 3196-3198 | Choose Warrior of the Open Hand | — |
| 4 | Ability Score Improvement | 3200-3202 | ASI/feat; repeats 8, 12, 16 | — |
| 4 | Slow Fall | 3204-3206 | Reaction on fall: reduce dmg by 5× Monk level | Reaction at-will |
| 5 | Extra Attack | 3208-3210 | Attack twice | Passive |
| 5 | Stunning Strike | 3212-3214 | 1/turn on weapon/Unarmed hit, expend 1 Focus Point: Con save, fail=Stunned until your next turn, success=Speed halved+next attack vs it has Advantage | Consumes 1 Focus Point |
| 6 | Empowered Strikes | 3216-3218 | Unarmed Strike dmg can be Force type or normal | Passive |
| 7 | Evasion | 3220-3224 | Dex save for half → no dmg on success, half on fail (unless Incapacitated) | Passive |
| 9 | Acrobatic Movement | 3226-3228 | Move on vertical surfaces/liquids without falling, unarmored/no Shield | Passive |
| 10 | Heightened Focus | 3230-3238 | Flurry of Blows→3 Unarmed Strikes (1 pt); Patient Defense grants Temp HP=2× Martial Arts die; Step of the Wind can bring a willing Large-or-smaller creature along | Passive upgrade (tied to Focus Point spends) |
| 10 | Self-Restoration | 3240-3244 | End of each turn: remove Charmed/Frightened/Poisoned from self; no Exhaustion from lack of food/drink | At-will (1 condition/turn) |
| 11 | Subclass feature | 3134 | Fleet Step (see subclass) | — |
| 12 | Ability Score Improvement | 3135 | ASI/feat | — |
| 13 | Deflect Energy | 3246-3248 | Deflect Attacks now works vs any damage type | Passive |
| 14 | Disciplined Survivor | 3250-3254 | Proficiency in all saving throws; expend 1 Focus Point to reroll a failed save (must use new roll) | Consumes 1 Focus Point per reroll |
| 15 | Perfect Focus | 3256-3258 | On Initiative roll (if not using Uncanny Metabolism), regain Focus Points up to 4 if ≤3 | Passive trigger |
| 16 | Ability Score Improvement | 3139 | ASI/feat | — |
| 17 | Subclass feature | 3140 | Quivering Palm (see subclass) | — |
| 18 | Superior Defense | 3260-3262 | Start of turn, expend 3 Focus Points: Resistance to all dmg except Force, 1 min or until Incapacitated | Consumes 3 Focus Points |
| 19 | Epic Boon | 3264-3266 | Epic Boon feat (Boon of Irresistible Offense recommended) | — |
| 20 | Body and Mind | 3268-3270 | Dex and Wis +4 each, max 25 | Passive |

Martial Arts die: 1d6 (1-4), 1d8 (5-9), 1d10 (10-16), 1d12 (17-20). Focus
Points: equal to Monk level (2 at lvl2 → 20 at lvl20, i.e. Focus Points =
Monk level for levels 2+). Unarmored Movement bonus: +10 ft (2-5), +15 ft
(6-9), +20 ft (10-13), +25 ft (14-17), +30 ft (18-20).

**Subclass: Warrior of the Open Hand** (3272-3302)

| Level | Feature | Line | Effect | Recharge |
|---|---|---|---|---|
| 3 | Open Hand Technique | 3278-3286 | On Flurry of Blows hit, impose: Addle (no OA until its next turn), Push (Str save or pushed 15 ft), or Topple (Dex save or Prone) | At-will (tied to Flurry) |
| 6 | Wholeness of Body | 3288-3292 | Bonus Action: roll Martial Arts die, heal roll+Wis mod (min 1); uses = Wis mod (min 1) | All/Long Rest |
| 11 | Fleet Step | 3294-3296 | Can use Step of the Wind immediately after any other Bonus Action | Passive |
| 17 | Quivering Palm | 3298-3302 | On Unarmed Strike hit, expend 4 Focus Points: vibrations last Monk-level days; end (action, or forgo an Attack-action attack) → Con save, fail=10d12 Force dmg (half on success); 1 target at a time; can end harmlessly free | Consumes 4 Focus Points to start |

**Resource types**: Focus Points (2-20 = Monk level from lvl2+; 1/Short or
Long Rest, regain all), Martial Arts die (scales, not a consumable), Deflect
Attacks redirect (consumes 1 Focus Point), Wholeness of Body (Wis-mod uses,
Long Rest), Uncanny Metabolism (1/Long Rest), Perfect Focus (Initiative
trigger).

---

### 4.7 Paladin

**Core Traits** (3306-3315): Primary Str+Cha · d10 HP die · Saves Wis/Cha ·
Skills choose 2 (Athletics, Insight, Intimidation, Medicine, Persuasion,
Religion) · Weapons Simple+Martial · Armor Light/Medium/Heavy/Shield ·
Equipment (A) Chain Mail+Shield+Longsword+6 Javelins+Holy Symbol+Priest's
Pack+9 GP or (B) 150 GP. Multiclass grant (3353): Hit Die, Martial weapon
proficiency, Light/Medium armor + Shield training.

| Level | Feature | Line(s) | Effect | Recharge |
|---|---|---|---|---|
| 1 | Lay On Hands | 3360-3366 | Healing pool = 5× Paladin level, refills on Long Rest; Bonus Action touch: restore up to remaining pool HP; or spend 5 HP from pool to cure Poisoned (no heal) | Long Rest |
| 1 | Spellcasting | 3368-3384 | Prepare 2 spells at lvl1, scaling per table (2,3,4,5,6,6,7,7,9,9,10,10,11,11,12,12,14,14,15,15 for lvl1-20); slots per table, Long Rest; full-list swap on Long Rest; Cha-based; Holy Symbol focus | Long Rest |
| 1 | Weapon Mastery | 3386-3390 | Mastery on 2 weapon kinds (proficient); swap on Long Rest | Long Rest |
| 2 | Fighting Style | 3392-3396 | Gain Fighting Style feat, or Blessed Warrior option (2 Cleric cantrips as Paladin spells, Cha-based, swappable per level) | — |
| 2 | Paladin's Smite | 3398-3400 | Always has Divine Smite prepared; cast once free of slot cost | 1/Long Rest |
| 3 | Channel Divinity | 3402-3406 | 2 uses; starts with Divine Sense (Bonus Action, 10 min: detect Celestials/Fiends/Undead + consecrated/desecrated sites within 60 ft); +1 use at lvl11 | 1/Short Rest, all/Long Rest |
| 3 | Paladin Subclass | 3420-3422 | Choose Oath of Devotion | — |
| 4 | Ability Score Improvement | 3424-3426 | ASI/feat; repeats 8, 12, 16 | — |
| 5 | Extra Attack | 3428-3430 | Attack twice | Passive |
| 5 | Faithful Steed | 3432-3436 | Always has Find Steed prepared; cast free once | 1/Long Rest |
| 6 | Aura of Protection | 3438-3444 | 10-ft Emanation (inactive if Incapacitated): self+allies gain save bonus = Cha mod (min +1); only 1 Paladin's aura benefits a creature at a time | Passive |
| 9 | Abjure Foes | 3446-3448 | Magic action, expend Channel Div use: target Cha-mod (min 1) creatures within 60 ft, Wis save or Frightened 1 min/until damaged; while Frightened, only move OR action OR bonus action per turn | Consumes 1 Channel Divinity use |
| 10 | Aura of Courage | 3450-3452 | Immunity to Frightened while in aura (suppresses existing) | Passive |
| 11 | Radiant Strikes | 3454-3456 | Melee/Unarmed hits deal extra 1d8 Radiant | Passive |
| 14 | Restoring Touch | 3458-3460 | Lay On Hands can also remove Blinded/Charmed/Deafened/Frightened/Paralyzed/Stunned, 5 HP from pool per condition (no heal) | Consumes pool HP |
| 18 | Aura Expansion | 3462-3464 | Aura of Protection → 30-ft Emanation | Passive |
| 19 | Epic Boon | 3466-3468 | Epic Boon feat (Boon of Truesight recommended) | — |
| 20 | Subclass feature | 3347 | Holy Nimbus (see subclass) | — |

Channel Divinity uses: 2 (lvl3-10), 3 (lvl11-20). Prepared Spells column:
2,3,4,5,6,6,7,7,9,9,10,10,11,11,12,12,14,14,15,15 (lvl1-20).

**Subclass: Oath of Devotion** (3540-3593)

| Level | Feature | Line | Effect | Recharge |
|---|---|---|---|---|
| 3 | Oath of Devotion Spells | 3554-3566 | Always-prepared bonus spells: lvl3 Protection from Evil and Good/Shield of Faith; lvl5 Aid/Zone of Truth; lvl9 Beacon of Hope/Dispel Magic; lvl13 Freedom of Movement/Guardian of Faith; lvl17 Commune/Flame Strike | Passive |
| 3 | Sacred Weapon | 3568-3574 | Attack action, expend Channel Div use: imbue 1 held Melee weapon, +Cha mod to attack rolls (min +1), dmg type or Radiant, Bright Light 20 ft/Dim 20 ft more, 10 min or until reused | Consumes 1 Channel Divinity use |
| 7 | Aura of Devotion | 3576-3578 | Immunity to Charmed while in Aura of Protection (suppresses existing) | Passive |
| 15 | Smite of Protection | 3580-3582 | On Divine Smite cast, aura grants Half Cover to self+allies until start of next turn | Passive/triggered |
| 20 | Holy Nimbus | 3584-3593 | Bonus Action, imbue aura 10 min or until ended: Advantage on saves forced by Fiend/Undead; enemies starting turn in aura take Radiant dmg=Cha mod+Prof; aura becomes sunlight | 1/Long Rest, restorable via a level-5 spell slot (no action) |

**Resource types**: Spell slots (Long Rest), Lay On Hands pool (5×level,
refills Long Rest), Channel Divinity uses (2-3; 1/Short Rest, all/Long Rest),
Paladin's Smite free-cast (1/Long Rest), Faithful Steed free-cast (1/Long
Rest), Holy Nimbus (1/Long Rest or via lvl5 slot).

---

### 4.8 Ranger

**Core Traits** (3596-3605): Primary Dex+Wis · d10 HP die · Saves Str/Dex ·
Skills choose 3 (Animal Handling, Athletics, Insight, Investigation, Nature,
Perception, Stealth, Survival) · Weapons Simple+Martial · Armor
Light/Medium/Shield · Equipment (A) Studded Leather+Scimitar+Shortsword+
Longbow+20 Arrows+Quiver+Druidic Focus (mistletoe)+Explorer's Pack+7 GP or (B)
150 GP. Multiclass grant (3616): Hit Die, Martial weapon proficiency, 1
Ranger-list skill, Light/Medium armor + Shield training.

| Level | Feature | Line(s) | Effect | Recharge |
|---|---|---|---|---|
| 1 | Spellcasting | 3623-3665 | Prepare 2 spells at lvl1, scaling per table (2,3,4,5,6,6,7,7,9,9,10,10,11,11,12,12,14,14,15,15); slots per table, Long Rest; full-list swap on Long Rest; Wis-based; Druidic Focus | Long Rest |
| 1 | Favored Enemy | 3667-3671 | Always has Hunter's Mark prepared; cast free 2×; scales (see below) | All/Long Rest |
| 1 | Weapon Mastery | 3673-3677 | Mastery on 2 proficient weapon kinds; swap on Long Rest | Long Rest |
| 2 | Deft Explorer | 3679-3685 | Expertise in 1 skill lacking it; know 2 more languages | Passive |
| 2 | Fighting Style | 3687-3691 | Gain Fighting Style feat, or Druidic Warrior option (2 Druid cantrips as Ranger spells, Wis-based, swappable) | — |
| 3 | Ranger Subclass | 3693-3695 | Choose Hunter | — |
| 4 | Ability Score Improvement | 3697-3699 | ASI/feat; repeats 8, 12, 16 | — |
| 5 | Extra Attack | 3701-3703 | Attack twice | Passive |
| 6 | Roving | 3705-3707 | +10 ft Speed unarmored-of-Heavy; gain Climb + Swim Speed = Speed | Passive |
| 7 | Subclass feature | 3640 | Defensive Tactics (see subclass) | — |
| 9 | Expertise | 3709-3711 | Expertise in 2 more skills lacking it | Passive |
| 10 | Tireless | 3713-3719 | Magic action: Temp HP = 1d8+Wis mod (min 1); uses=Wis mod (min 1); also Exhaustion −1 on Short Rest | All/Long Rest (Temp HP uses); Short Rest (Exhaustion) |
| 11 | Subclass feature | 3644 | Superior Hunter's Prey (see subclass) | — |
| 13 | Relentless Hunter | 3721-3723 | Damage can't break Concentration on Hunter's Mark | Passive |
| 14 | Nature's Veil | 3725-3729 | Bonus Action: Invisible until end of next turn; uses=Wis mod (min 1) | All/Long Rest |
| 15 | Subclass feature | 3648 | Superior Hunter's Defense (see subclass) | — |
| 17 | Precise Hunter | 3731-3733 | Advantage on attacks vs Hunter's Mark target | Passive |
| 18 | Feral Senses | 3735-3737 | Blindsight 30 ft | Passive |
| 19 | Epic Boon | 3739-3741 | Epic Boon feat (Boon of Dimensional Travel recommended) | — |
| 20 | Foe Slayer | 3743-3745 | Hunter's Mark die → d10 | Passive |

Favored Enemy free-casts: 2 (lvl1-4), 3 (lvl5-8), 4 (lvl9-12), 5 (lvl13-16), 6
(lvl17-20). Prepared Spells: 2,3,4,5,6,6,7,7,9,9,10,10,11,11,12,12,14,14,15,15
(lvl1-20).

**Subclass: Hunter** (3822-3855)

| Level | Feature | Line | Effect | Recharge |
|---|---|---|---|---|
| 3 | Hunter's Lore | 3828-3830 | While Hunter's Mark active, know target's Immunities/Resistances/Vulnerabilities | Passive |
| 3 | Hunter's Prey | 3832-3838 | Choose (swap on Short/Long Rest): Colossus Slayer (1/turn extra 1d8 on a hit vs a creature missing any HP) OR Horde Breaker (1/turn extra attack vs a different creature within 5 ft of original target) | Swap on Short/Long Rest; effect itself at-will |
| 7 | Defensive Tactics | 3840-3846 | Choose (swap on Short/Long Rest): Escape the Horde (OA vs you have Disadvantage) OR Multiattack Defense (a creature that hits you has Disadvantage on other attacks vs you this turn) | Swap on Short/Long Rest |
| 11 | Superior Hunter's Prey | 3848-3850 | 1/turn, Hunter's Mark dmg to marked target also hits a 2nd creature within 30 ft | At-will, 1/turn |
| 15 | Superior Hunter's Defense | 3852-3854 | Reaction on taking damage: Resistance to that damage type until end of current turn | Reaction at-will |

**Resource types**: Spell slots (Long Rest), Favored Enemy free Hunter's Mark
casts (2-6, Long Rest), Weapon Mastery slots (2, swap Long Rest), Tireless
Temp HP uses (Wis mod, Long Rest), Nature's Veil uses (Wis mod, Long Rest).

---

### 4.9 Rogue

**Core Traits** (3858-3868): Primary Dex · d8 HP die · Saves Dex/Int · Skills
choose 4 (Acrobatics, Athletics, Deception, Insight, Intimidation,
Investigation, Perception, Persuasion, Sleight of Hand, Stealth) · Weapons
Simple + Martial-with-Finesse-or-Light · Tools Thieves' Tools · Armor Light ·
Equipment (A) Leather Armor+2 Daggers+Shortsword+Shortbow+20 Arrows+Quiver+
Thieves' Tools+Burglar's Pack+8 GP or (B) 100 GP. Multiclass grant (3879): Hit
Die, 1 Rogue-list skill, Thieves' Tools proficiency, Light armor training.

| Level | Feature | Line(s) | Effect | Recharge |
|---|---|---|---|---|
| 1 | Expertise | 3886-3890 | Double Prof Bonus on 2 chosen skills; +2 more at lvl6 | Passive |
| 1 | Sneak Attack | 3892-3921 | 1/turn extra 1d6 dmg on Advantage hit w/ Finesse/Ranged weapon (or w/o Advantage if an ally is adjacent, undisadvantaged); scales by level (see below) | 1/turn |
| 1 | Thieves' Cant | 3923-3925 | Know Thieves' Cant + 1 other language | Passive |
| 1 | Weapon Mastery | 3927-3931 | Mastery on 2 proficient weapon kinds; swap on Long Rest | Long Rest |
| 2 | Cunning Action | 3933-3935 | Bonus Action: Dash, Disengage, or Hide | At-will |
| 3 | Rogue Subclass | 3937-3939 | Choose Thief | — |
| 3 | Steady Aim | 3941-3943 | Bonus Action (no movement this turn): Advantage on next attack this turn; Speed→0 rest of turn | At-will |
| 4 | Ability Score Improvement | 3945-3947 | ASI/feat; repeats 8, 10, 12, 16 | — |
| 5 | Cunning Strike | 3949-3961 | On Sneak Attack dmg, forgo dice to add effect: Poison (1d6, Con save/Poisoned 1 min, needs Poisoner's Kit), Trip (1d6, Dex save/Prone if Large-), Withdraw (1d6, move ½ Speed no OA); DC=8+Dex mod+Prof | At-will (die cost paid from Sneak Attack pool) |
| 5 | Uncanny Dodge | 3963-3965 | Reaction on seen-attacker hit: halve damage (round down) | Reaction at-will |
| 6 | Expertise | 3890 | +2 more skills gain Expertise (total 4) | Passive |
| 7 | Evasion | 3967-3969 | Dex save for half → no dmg on success, half on fail (not if Incapacitated) | Passive |
| 7 | Reliable Talent | 3971-3973 | Treat d20 roll of 9 or lower as 10 on proficient skill/tool checks | Passive |
| 9 | Subclass feature | 3906 | Supreme Sneak (see subclass) | — |
| 11 | Improved Cunning Strike | 3975-3977 | Use up to 2 Cunning Strike effects per Sneak Attack, paying each die cost | At-will |
| 13 | Subclass feature | 3910 | Use Magic Device (see subclass) | — |
| 14 | Devious Strikes | 3979-3987 | New Cunning Strike options: Daze (2d6, Con save or move-OR-action-OR-bonus only next turn), Knock Out (6d6, Con save or Unconscious 1 min/until damaged), Obscure (3d6, Dex save or Blinded until end of next turn) | At-will (die cost) |
| 15 | Slippery Mind | 3989-3991 | Proficiency in Wis and Cha saves | Passive |
| 17 | Subclass feature | 3914 | Thief's Reflexes (see subclass) | — |
| 18 | Elusive | 3993-3995 | No attack roll gains Advantage vs you unless you're Incapacitated | Passive |
| 19 | Epic Boon | 3997-3999 | Epic Boon feat (Boon of the Night Spirit recommended) | — |
| 20 | Stroke of Luck | 4001-4005 | Failed D20 Test → turn into a 20 | 1/Short or Long Rest |

Sneak Attack dice: 1d6 (1-2), 2d6 (3-4), 3d6 (5-6), 4d6 (7-8), 5d6 (9-10), 6d6
(11-12), 7d6 (13-14), 8d6 (15-16), 9d6 (17-18), 10d6 (19-20).

**Subclass: Thief** (4007-4044)

| Level | Feature | Line | Effect | Recharge |
|---|---|---|---|---|
| 3 | Fast Hands | 4013-4017 | Bonus Action: Sleight of Hand check (lock/trap/pickpocket) OR Utilize action OR Magic action to use a magic item | At-will |
| 3 | Second-Story Work | 4019-4025 | Climb Speed = Speed; jump distance uses Dex instead of Str | Passive |
| 9 | Supreme Sneak | 4027-4029 | New Cunning Strike: Stealth Attack (1d6) — attacking from Hide doesn't break Invisible if ending turn in ¾/Total Cover | At-will (die cost) |
| 13 | Use Magic Device | 4031-4039 | Attune to 4 items; on charge use, 1d6, roll 6 = free use; can cast from any Spell Scroll (Int-based; cantrip/lvl1 reliable; higher = DC 10+spell level Int(Arcana) check, fail=scroll destroyed) | Passive |
| 17 | Thief's Reflexes | 4041-4044 | 2 turns in first combat round: normal Initiative, then Initiative−10 | Passive (round 1 only) |

**Resource types**: Sneak Attack dice (1d6-10d6, 1/turn, consumed for Cunning
Strike effects), Weapon Mastery slots (2, Long Rest swap), Uncanny Dodge
(Reaction, at-will), Stroke of Luck (1/Short or Long Rest).

---

### 4.10 Sorcerer

**Core Traits** (4047-4056): Primary Cha · d6 HP die · Saves Con/Cha · Skills
choose 2 (Arcana, Deception, Insight, Intimidation, Persuasion, Religion) ·
Weapons Simple · Armor None · Equipment (A) Spear+2 Daggers+Arcane Focus
(crystal)+Dungeoneer's Pack+28 GP or (B) 50 GP. Multiclass grant (4067): Hit
Die only.

| Level | Feature | Line(s) | Effect | Recharge |
|---|---|---|---|---|
| 1 | Spellcasting | 4074-4123 | 4 cantrips (+1 at 4, +1 at 10); prepare 2 spells at lvl1 scaling per table (2,4,6,7,9,10,11,12,14,15,16,16,17,17,18,18,19,20,21,22); slots per table, Long Rest; replace 1/level gained; Cha-based; Arcane Focus | Long Rest |
| 1 | Innate Sorcery | 4124-4131 | Bonus Action, 1 min: spell save DC +1, Advantage on spell attack rolls; 2 uses | All/Long Rest |
| 2 | Font of Magic | 4133-4147 | Sorcery Points pool (2 at lvl2, = level thereafter, see table); convert slot→points (1:1 per level, no action); Bonus Action convert points→slot (cost table below, max slot level 5); created slots vanish on Long Rest | All Sorcery Points/Long Rest |
| 2 | Metamagic | 4157-4163 | Know 2 Metamagic options (from 10 listed below); 1/spell unless noted; swap 1/level; +2 more at lvl10, +2 more at lvl17 (total 6 by lvl17) | — |
| 3 | Sorcerer Subclass | 4165-4167 | Choose Draconic Sorcery | — |
| 4 | Ability Score Improvement | 4169-4171 | ASI/feat; repeats 8, 12, 16 | — |
| 5 | Sorcerous Restoration | 4173-4175 | On Short Rest, regain Sorcery Points up to ½ Sorcerer level (round down); 1/Long Rest | 1/Long Rest |
| 6 | Subclass feature | 4094 | Elemental Affinity (see subclass) | — |
| 7 | Sorcery Incarnate | 4177-4181 | If no Innate Sorcery uses left, activate by spending 2 Sorcery Points instead; while active, use up to 2 Metamagic options/spell | Consumes 2 Sorcery Points (if no free use) |
| 8 | Ability Score Improvement | 4096 | ASI/feat | — |
| 9 | — | 4097 | No new feature | — |
| 10 | Metamagic | 4163 | +2 more Metamagic options known | — |
| 11 | — | 4099 | No new feature | — |
| 12 | Ability Score Improvement | 4100 | ASI/feat | — |
| 13 | — | 4101 | No new feature | — |
| 14 | Subclass feature | 4102 | Dragon Wings (see subclass) | — |
| 15 | — | 4103 | No new feature | — |
| 16 | Ability Score Improvement | 4104 | ASI/feat | — |
| 17 | Metamagic | 4163 | +2 more Metamagic options known (total 6) | — |
| 18 | Subclass feature | 4106 | Dragon Companion (see subclass) | — |
| 19 | Epic Boon | 4183-4185 | Epic Boon feat (Boon of Dimensional Travel recommended) | — |
| 20 | Arcane Apotheosis | 4187-4189 | While Innate Sorcery active, use 1 Metamagic option/turn free of Sorcery Point cost | Passive |

Sorcery Points = Sorcerer level starting at lvl2 (2 at lvl2 → 20 at lvl20).
**Creating Spell Slots table** (4147-4155): slot lvl1=2 pts (min lvl2),
lvl2=3 pts (min lvl3), lvl3=5 pts (min lvl5), lvl4=6 pts (min lvl7), lvl5=7
pts (min lvl9).

**Metamagic Options** (full list, 4191-4260):

| Option | Cost | Effect | Line |
|---|---|---|---|
| Careful Spell | 1 SP | Chosen creatures (up to Cha mod, min 1) auto-succeed save, no half-dmg | 4195-4199 |
| Distant Spell | 1 SP | Double range (≥5ft range spells), or Touch→30ft | 4201-4205 |
| Empowered Spell | 1 SP | Reroll damage dice up to Cha mod (min 1), must use new rolls; stackable with another Metamagic | 4207-4213 |
| Extended Spell | 1 SP | Double duration (≥1 min spells) up to 24 hrs; Advantage on Concentration saves if applicable | 4215-4221 |
| Heightened Spell | 2 SP | 1 target gets Disadvantage on its save vs the spell | 4223-4227 |
| Quickened Spell | 2 SP | Change casting time (Action→Bonus Action); can't also cast a lvl1+ spell same turn | 4229-4233 |
| Seeking Spell | 2 SP (labeled "Cost: 1 Sorcery Point" at 4237 — see note) | Reroll a missed spell attack d20, must use new roll; stackable with another Metamagic | 4235-4241 |
| Subtle Spell | 1 SP | Cast without Verbal/Somatic/Material (except costed/consumed Material) | 4243-4247 |
| Transmuted Spell | 1 SP | Change damage type among Acid/Cold/Fire/Lightning/Poison/Thunder | 4249-4253 |
| Twinned Spell | 1 SP | Increase effective spell level by 1 (for spells with a higher-slot "additional target" clause) | 4255-4259 |

**Subclass: Draconic Sorcery** (4452-4494)

| Level | Feature | Line | Effect | Recharge |
|---|---|---|---|---|
| 3 | Draconic Resilience | 4458-4462 | HP max +3 (then +1/level gained); unarmored AC = 10+Dex+Cha mod | Passive |
| 3 | Draconic Spells | 4464-4476 | Always-prepared bonus spells: lvl3 Alter Self/Chromatic Orb/Command/Dragon's Breath; lvl5 Fear/Fly; lvl7 Arcane Eye/Charm Monster; lvl9 Legend Lore/Summon Dragon | Passive |
| 6 | Elemental Affinity | 4477-4481 | Choose Acid/Cold/Fire/Lightning/Poison: Resistance to it; +Cha mod to one damage roll of a spell of that type | Passive |
| 14 | Dragon Wings | 4483-4487 | Bonus Action: Fly Speed 60 ft, 1 hr or dismiss | 1/Long Rest, or 3 Sorcery Points to restore |
| 18 | Dragon Companion | 4489-4494 | Summon Dragon w/o Material; cast free once/Long Rest; can drop Concentration requirement (duration becomes 1 min) | 1/Long Rest for free cast |

**Resource types**: Spell slots (Long Rest), Sorcery Points (2-20 = Sorcerer
level from lvl2+; Long Rest; convertible both directions to/from spell
slots), Innate Sorcery uses (2, Long Rest, or 2-SP-triggered from lvl7),
Metamagic options known (2/4/6, permanent knowledge not a per-use resource),
Dragon Wings (1/Long Rest or 3 SP).

---

### 4.11 Warlock

**Core Traits** (4497-4506): Primary Cha · d8 HP die · Saves Wis/Cha · Skills
choose 2 (Arcana, Deception, History, Intimidation, Investigation, Nature,
Religion) · Weapons Simple · Armor Light · Equipment (A) Leather Armor+
Sickle+2 Daggers+Arcane Focus (orb)+Book (occult lore)+Scholar's Pack+15 GP or
(B) 100 GP. Multiclass grant (4517): Hit Die, Light armor training.

| Level | Feature | Line(s) | Effect | Recharge |
|---|---|---|---|---|
| 1 | Eldritch Invocations | 4524-4530, 4557-4561 | Gain 1 invocation of choice (from list below); prerequisites gate availability; swap 1/level gained (unless it's a prerequisite for another held invocation) | — |
| 1 | Pact Magic | 4563-4585 | 2 cantrips (+1 at 4, +1 at 10); Spell Slots: **all same level**, count+level per table below — regains on **Short or Long Rest** (distinct from standard Spellcasting!); prepare 2 spells at lvl1 scaling per table; slot level caps prepared-spell level; Cha-based; Arcane Focus | **Short or Long Rest** |
| 2 | Magical Cunning | 4587-4589 | 1-min rite: regain expended Pact Magic slots up to ½ max (round up) | 1/Long Rest |
| 3 | Warlock Subclass | 4591-4593 | Choose Fiend Patron | — |
| 4 | Ability Score Improvement | 4595-4597 | ASI/feat; repeats 8, 12, 16 | — |
| 9 | Contact Patron | 4599-4603 | Always has Contact Other Plane prepared; cast free, auto-succeed its save | 1/Long Rest |
| 11 | Mystic Arcanum (lvl6 spell) | 4605-4611 | Choose 1 lvl6 Warlock spell; cast free once; +1 more arcanum at lvl13 (lvl7 spell), 15 (lvl8), 17 (lvl9); swap 1/level gained | All uses/Long Rest |
| 19 | Epic Boon | 4615-4617 | Epic Boon feat (Boon of Fate recommended) | — |
| 20 | Eldritch Master | 4619-4621 | Magical Cunning now restores ALL expended Pact Magic slots | Passive upgrade |

**Warlock Pact Magic table** (4534-4555) — the class's signature distinct
resource, **recharges on Short OR Long Rest** unlike standard full-caster
Spellcasting:

| Warlock Level | Spell Slots | Slot Level |
|---|---|---|
| 1 | 1 | 1 |
| 2 | 2 | 1 |
| 3 | 2 | 2 |
| 4 | 2 | 2 |
| 5 | 2 | 3 |
| 6 | 2 | 3 |
| 7 | 2 | 4 |
| 8 | 2 | 4 |
| 9 | 2 | 5 |
| 10 | 2 | 5 |
| 11-16 | 3 | 5 |
| 17-20 | 4 | 5 |

Eldritch Invocations known: 1 (lvl1), 3 (lvl2-4), 5 (lvl5-6), 6 (lvl7-8), 7
(lvl9-11), 8 (lvl12-14), 9 (lvl15-17), 10 (lvl18-20).

**Eldritch Invocation Options — full list** (4623-4822):

| Invocation | Prerequisite | Effect | Line |
|---|---|---|---|
| Agonizing Blast | Lvl2+, a damaging cantrip | +Cha mod to that cantrip's damage rolls; repeatable (different cantrip) | 4627-4634 |
| Armor of Shadows | — | Cast Mage Armor on self, no slot | 4635-4638 |
| Ascendant Step | Lvl5+ | Cast Levitate on self, no slot | 4639-4644 |
| Devil's Sight | Lvl2+ | See normally in Dim Light/Darkness within 120 ft | 4645-4650 |
| Devouring Blade | Lvl12+, Thirsting Blade | Thirsting Blade's Extra Attack → 2 extra attacks | 4651-4656 |
| Eldritch Mind | — | Advantage on Concentration saves | 4657-4660 |
| Eldritch Smite | Lvl5+, Pact of the Blade | 1/turn on pact-weapon hit, expend a Pact Magic slot: extra 1d8 Force + 1d8/slot level, Prone if Huge or smaller | 4661-4666 |
| Eldritch Spear | Lvl2+, a damaging cantrip w/ range ≥10ft | Range +30ft × Warlock level; repeatable (different cantrip) | 4667-4674 |
| Fiendish Vigor | Lvl2+ | Cast False Life on self free, auto-max Temp HP die | 4675-4680 |
| Gaze of Two Minds | Lvl5+ | Bonus Action: perceive through a willing touched creature's senses until end of next turn; maintainable via Bonus Action; can cast spells from its space within 60 ft | 4681-4688 |
| Gift of the Depths | Lvl5+ | Water breathing + Swim Speed = Speed; cast Water Breathing free 1/Long Rest | 4689-4696 |
| Gift of the Protectors | Lvl9+, Pact of the Tome | A page holds Cha-mod names; a named creature dropped to 0 HP instead drops to 1 HP once, until Long Rest | 4697-4706 |
| Investment of the Chain Master | Lvl5+, Pact of the Chain | Familiar gains Fly/Swim 40ft, Bonus-Action Attack command, Necrotic/Radiant dmg option, uses your save DC, Reaction-grantable Resistance | 4707-4721 |
| Lessons of the First Ones | Lvl2+ | Gain 1 Origin feat; repeatable (different feat) | 4723-4729 |
| Lifedrinker | Lvl9+, Pact of the Blade | 1/turn on pact-weapon hit: extra 1d6 Necrotic/Psychic/Radiant; expend a Hit Die to heal roll+Con mod (min 1) | 4731-4735 |
| Mask of Many Faces | Lvl2+ | Cast Disguise Self free | 4737-4741 |
| Master of Myriad Forms | Lvl5+ | Cast Alter Self free | 4743-4747 |
| Misty Visions | Lvl2+ | Cast Silent Image free | 4749-4753 |
| One with Shadows | Lvl5+ | In Dim Light/Darkness, cast Invisibility on self free | 4755-4759 |
| Otherworldly Leap | Lvl2+ | Cast Jump on self free | 4761-4765 |
| Pact of the Blade | — | Bonus Action: conjure/bond a Melee weapon; Cha mod for attack/damage; dmg type Necrotic/Psychic/Radiant or normal; bond ends on reuse, weapon >5ft for 1 min, or death | 4767-4774 |
| Pact of the Chain | — | Learn Find Familiar, cast free (Magic action); special forms (Imp, Pseudodragon, Quasit, Skeleton, Sphinx of Wonder, Sprite, Venomous Snake); forgo an attack to let familiar Reaction-attack | 4775-4782 |
| Pact of the Tome | — | Conjure Book of Shadows (Short/Long Rest): 3 cantrips + 2 lvl1 Ritual spells, any class list, always prepared as Warlock spells; usable as Spellcasting Focus | 4783-4790 |
| Repelling Blast | Lvl2+, a damaging-via-attack-roll cantrip | On hit vs Large-or-smaller, push 10ft; repeatable (different cantrip) | 4791-4798 |
| Thirsting Blade | Lvl5+, Pact of the Blade | Extra Attack for pact weapon only (2 attacks) | 4799-4804 |
| Visions of Distant Realms | Lvl9+ | Cast Arcane Eye free | 4805-4810 |
| Whispers of the Grave | Lvl7+ | Cast Speak with Dead free | 4811-4816 |
| Witch Sight | Lvl15+ | Truesight 30 ft | 4817-4822 |

**Subclass: Fiend Patron** (5001-5037)

| Level | Feature | Line | Effect | Recharge |
|---|---|---|---|---|
| 3 | Dark One's Blessing | 5007-5009 | On reducing an enemy to 0 HP (self or ally within 10 ft), gain Temp HP = Cha mod + Warlock level (min 1) | Passive, triggered |
| 3 | Fiend Spells | 5011-5021 | Always-prepared bonus spells: lvl3 Burning Hands/Command/Scorching Ray/Suggestion; lvl5 Fireball/Stinking Cloud; lvl7 Fire Shield/Wall of Fire; lvl9 Geas/Insect Plague | Passive |
| 6 | Dark One's Own Luck | 5022-5026 | Add 1d10 to an ability check or save after seeing the roll; uses=Cha mod (min 1), 1/roll max | All/Long Rest |
| 10 | Fiendish Resilience | 5028-5030 | Choose 1 damage type (not Force) on Short/Long Rest: Resistance to it until changed | Reselect on Short/Long Rest |
| 14 | Hurl Through Hell | 5032-5036 | 1/turn on hit: Cha save vs your spell DC, fail=target vanishes, 8d10 Psychic (unless Fiend) + Incapacitated until end of your next turn, then returns | 1/Long Rest, or expend a Pact Magic slot to restore |

**Resource types**: Pact Magic slots (all same level, count 1→4, level 1→5;
**Short or Long Rest** — distinct recharge from every other full-caster class
in this document), Eldritch Invocations known (1-10, permanent not
consumable), Magical Cunning (1/Long Rest, restores ≤½ Pact Magic slots, all
of them from lvl20), Mystic Arcanum casts (1 each of 4 spell levels by lvl17,
all/Long Rest), Contact Patron (1/Long Rest), Dark One's Own Luck (Cha-mod
uses/Long Rest), Hurl Through Hell (1/Long Rest or Pact Magic slot).

**OCR garbling flagged**: Lines 4827-4844 (Warlock cantrip list) and
4886-4944 (Level 2-3 Warlock spell lists) collapse into disjoint
Spell/School/Special column dumps identical in pattern to the Bard's Level
6-7 garbling (e.g. line 4896 runs "Fly School Necromancy Evocation
Conjuration..." merging spell name, multiple schools, and "Special" header
into one line). Not reconstructed; spell lists are out of scope for this
catalogue, but flagged since it's more severe here than in most other
classes.

---

### 4.12 Wizard

**Core Traits** (5040-5049): Primary Int · d6 HP die · Saves Int/Wis · Skills
choose 2 (Arcana, History, Insight, Investigation, Medicine, Nature,
Religion) · Weapons Simple · Armor None · Equipment (A) 2 Daggers+Arcane
Focus (Quarterstaff)+Robe+Spellbook+Scholar's Pack+5 GP or (B) 55 GP.
Multiclass grant (5086): Hit Die only.

| Level | Feature | Line(s) | Effect | Recharge |
|---|---|---|---|---|
| 1 | Spellcasting | 5093-5119 | 3 cantrips (+1 at 4, +1 at 10); Spellbook holds all known lvl1+ spells (starts with 6 lvl1 spells; +2 spells/level gained thereafter); prepare 4 from spellbook, scaling per table (4,5,6,7,9,10,11,12,14,15,16,16,17,18,19,21,22,23,24,25 for lvl1-20 — note larger jumps at 16/20 than other casters); slots per table, Long Rest; full swap on Long Rest; Int-based; Arcane Focus or spellbook as focus | Long Rest |
| 1 | Ritual Adept | 5121-5123 | Cast any Ritual-tagged spell in spellbook as a Ritual without preparing it (must read from book) | Passive |
| 1 | Arcane Recovery | 5125-5129 | On Short Rest, recover slots totalling ≤½ Wizard level (round up), none level 6+ | 1/Long Rest |
| 2 | Scholar | 5131-5133 | Expertise in 1 proficient skill: Arcana/History/Investigation/Medicine/Nature/Religion | Passive |
| 3 | Wizard Subclass | 5135-5137 | Choose Evoker | — |
| 4 | Ability Score Improvement | 5151-5153 | ASI/feat; repeats 8, 12, 16 | — |
| 5 | Memorize Spell | 5155-5157 | On Short Rest, swap 1 prepared spell for another from spellbook | Short Rest |
| 6 | Subclass feature | 5068 | Sculpt Spells (see subclass) | — |
| 7 | — | 5069 | No new feature | — |
| 8 | Ability Score Improvement | 5070 | ASI/feat | — |
| 9 | — | 5071 | No new feature | — |
| 10 | Subclass feature | 5072 | Empowered Evocation (see subclass) | — |
| 11 | — | 5073 | No new feature | — |
| 12 | Ability Score Improvement | 5074 | ASI/feat | — |
| 13 | — | 5075 | No new feature | — |
| 14 | Subclass feature | 5076 | Overchannel (see subclass) | — |
| 15 | — | 5077 | No new feature | — |
| 16 | Ability Score Improvement | 5078 | ASI/feat | — |
| 17 | — | 5079 | No new feature | — |
| 18 | Spell Mastery | 5159-5163 | Choose a lvl1 + lvl2 spell (action casting time) in spellbook: always prepared, cast at lowest level free of slot cost; swap 1/Long Rest | Passive; free-cast at-will |
| 19 | Epic Boon | 5165-5167 | Epic Boon feat (Boon of Spell Recall recommended) | — |
| 20 | Signature Spells | 5169-5171 | Choose 2 lvl3 spells: always prepared, cast each once/Short-or-Long-Rest at lvl3 free of slot cost | 1 each/Short or Long Rest |

Prepared Spells column (5058-5082): 4,5,6,7,9,10,11,12,14,15,16,16,17,18,19,
21,22,23,24,25 for lvl 1-20 (irregular jumps of +2 at levels 16 and 20 unlike
other full casters — verified directly from the table, not a transcription
error).

**Spellbook mechanics** (5101-5147, in detail):

- Physical object: Tiny, 3 lbs, 100 pages, readable only by owner or via
  Identify (5101).
- Starts with 6 level-1 Wizard spells of choice (5103).
- Gains 2 new Wizard spells of choice per Wizard level gained after 1st, of a
  level for which the Wizard has slots (5105).
- **Copying a Spell into the Book** (5143): found spell of a preparable
  level, if time allows — 2 hours + 50 GP **per spell level**.
- **Copying the Book** (copying from your book into another book, 5145): 1
  hour + 10 GP per spell level (faster since you already know the spell).
- **Lost spellbook**: same transcription procedure to rebuild currently-
  prepared spells into a new book; remainder must be found again — hence
  "many wizards keep a backup spellbook" (5147).
- **Ritual Adept** (5121-5123) lets any Ritual spell in the book be cast
  without being prepared.

**Resource types**: Spell slots (Long Rest), Arcane Recovery (1/Long Rest,
recovers ≤½ level worth of slots, none level 6+), Memorize Spell (swap
1/Short Rest from lvl5), Spell Mastery (2 spells free-castable at-will from
lvl18), Signature Spells (2 spells, 1 free cast each per Short-or-Long Rest
from lvl20).

**Subclass: Evoker** (5540-5570)

| Level | Feature | Line | Effect | Recharge |
|---|---|---|---|---|
| 3 | Evocation Savant | 5546-5550 | 2 free Evocation spells (≤lvl2) added to spellbook; +1 free Evocation spell added whenever a new spell-slot level is gained | Passive |
| 3 | Potent Cantrip | 5552-5554 | Miss/save-success vs a damaging cantrip still deals half damage, no secondary effect | Passive |
| 6 | Sculpt Spells | 5556-5558 | When casting a multi-target Evocation spell, 1+spell-level chosen creatures auto-succeed save + no damage | At-will (per applicable cast) |
| 10 | Empowered Evocation | 5560-5562 | +Int mod to one damage roll of an Evocation spell cast | Passive |
| 14 | Overchannel | 5564-5570 | Max damage on a lvl1-5 damaging spell cast; 1st use/Long Rest free; subsequent uses before Long Rest deal 2d12 Necrotic/slot-level self-damage (ignores Resistance/Immunity), increasing +1d12 per repeat use | 1 free use/Long Rest, extra uses self-damaging |

**OCR issues flagged** (Wizard section specifically):

1. **Line 5139**: heading rendered as `## ExpandinG and rEplacinG a spEllBook`
   — mangled mixed-case artifact of the source PDF parse. Correct heading is
   almost certainly "Expanding and Replacing a Spellbook" based on the
   section's content (copying spells, replacing a lost spellbook), but the
   mixed-case string is quoted verbatim here rather than silently
   "corrected," per instructions.
2. Lines 5306-5344 (Level 4 Wizard Spells) and 5444-5505 (Level 7 Wizard
   Spells) collapse into the same disjoint Spell/School/Special run-on
   pattern seen in Bard/Warlock (e.g. line 5344 runs "Phantasmal Killer
   School Divination Abjuration Conjuration... Special" as one garbled
   line). Not reconstructed; spell lists are out of scope.

---

## 5. Cross-Class Resource-Mechanic Summary

An engine must track the following distinct resource types. "Recharge" is the
event that fully or partially restores the resource; "Uses/scale" gives the
count formula or table reference.

| Resource | Granting class/level | Uses / scale | Recharge |
|---|---|---|---|
| **Spell Slots (standard)** | Bard(1), Cleric(1), Druid(1), Sorcerer(1), Wizard(1), Paladin(1, half-caster), Ranger(1, half-caster) | Per-class table, up to lvl9 (full) or lvl5 (half) | Long Rest (all) |
| **Pact Magic slots (Warlock)** | Warlock(1) | Table in §4.11 — all slots same level, 1-4 slots, level 1-5 | **Short or Long Rest** (distinct from all other casters) |
| **Rage uses** | Barbarian(1) | 2→6 by level (§4.1) | 1/Short Rest, all/Long Rest |
| **Rage Damage bonus** | Barbarian(1) | +2→+4 by level | N/A (passive scalar) |
| **Weapon Mastery slots** | Barbarian(1), Fighter(1), Paladin(1), Ranger(1), Rogue(1) | 2-6 kinds depending on class/level | Swap choices on Long Rest (count itself doesn't "recharge") |
| **Superiority Dice** | *Not present in this SRD* — 2024 Fighter has no Battle Master subclass in the provided text; no Superiority Dice mechanic appears in lines 1509-5573. | — | — |
| **Second Wind** | Fighter(1) | 2→4 uses (§4.5) | 1/Short Rest, all/Long Rest |
| **Action Surge** | Fighter(2) | 1 use, 2 (1/turn) from lvl17 | Short or Long Rest |
| **Indomitable** | Fighter(9) | 1→3 uses | Long Rest |
| **Ki/Focus Points** (2024 renamed from "Ki") | Monk(2) | = Monk level from lvl2+ (2-20) | 1/Short or Long Rest, regain all |
| **Sorcery Points** | Sorcerer(2) | = Sorcerer level from lvl2+ (2-20) | Long Rest; convertible to/from spell slots |
| **Metamagic options known** | Sorcerer(2) | 2→6 (permanent knowledge, not a per-use pool) | N/A |
| **Channel Divinity uses** | Cleric(2), Paladin(3) | Cleric 2-4; Paladin 2-3 | 1/Short Rest, all/Long Rest |
| **Bardic Inspiration** | Bard(1) | = Cha mod, min 1 (die scales d6→d12) | Long Rest only until lvl5, then Short or Long Rest |
| **Lay on Hands pool** | Paladin(1) | 5 × Paladin level (HP pool) | Long Rest |
| **Wild Shape uses** | Druid(2) | 2→4 by level | 1/Short Rest, all/Long Rest; convertible to/from spell slots (Wild Resurgence, Archdruid) |
| **Sneak Attack** | Rogue(1) | 1d6→10d6 by level, 1/turn | N/A (at-will, once/turn); dice consumable for Cunning Strike effects |
| **Divine Smite** | Paladin (via Paladin's Smite feature, lvl2 free cast) + spell-slot-consuming Divine Smite spell itself | 1 free cast/Long Rest; otherwise consumes a spell slot per cast | Long Rest (free-cast use) |
| **Eldritch Invocations known** | Warlock(1) | 1→10 (permanent, not consumable) | N/A |
| **Mystic Arcanum** | Warlock(11) | 1 spell each of level 6/7/8/9 by lvl17, 1 free cast each | All/Long Rest |
| **Arcane Recovery** | Wizard(1) | Recover ≤½ level worth of slots, none lvl6+ | 1/Long Rest |
| **Hit Dice (short-rest recovery pool)** | All classes (Level Advancement / multiclass rules) | Pool = sum of all class levels' Hit Dice | Spend during Short Rest to heal; regain roughly half on Long Rest (see core rules, not in class tables) |
| **Innate Sorcery** | Sorcerer(1) | 2 uses | All/Long Rest (or 2 SP re-trigger from lvl7) |
| **Divine Intervention** | Cleric(10) | 1 use | Long Rest (or 2d4 Long Rests at lvl20 if Wish chosen) |

---

## 6. Weapon Mastery (2024-only mechanic)

Mastery properties (definitions, lines 6102-6141) — usable only via a class
feature (e.g. Weapon Mastery) that unlocks them:

| Property | Effect | Line |
|---|---|---|
| Cleave | On melee hit, make a 2nd melee attack roll (no ability-mod damage unless negative) vs a 2nd creature within 5 ft of the first and within reach; 1/turn | 6110-6112 |
| Graze | On a miss, still deal damage = the ability modifier used for the attack (weapon's damage type; scalable only via that ability mod) | 6114-6116 |
| Nick | The Light property's extra attack can be made as part of the Attack action instead of a Bonus Action; 1/turn | 6118-6120 |
| Push | On hit, push the creature up to 10 ft straight away if Large or smaller | 6122-6124 |
| Sap | On hit, target has Disadvantage on its next attack roll before start of your next turn | 6126-6128 |
| Slow | On hit + damage, reduce target's Speed by 10 ft until start of your next turn; multiple Slow hits don't stack beyond 10 ft | 6130-6132 |
| Topple | On hit, target makes Con save (DC 8 + ability mod used + Prof Bonus) or falls Prone | 6134-6136 |
| Vex | On hit + damage, gain Advantage on your next attack vs that target before end of your next turn | 6138-6140 |

**Which classes get Weapon Mastery** (and how many weapon kinds, by level —
see each class's table in §4): Barbarian (2→4), Fighter (3→6), Paladin
(2, fixed), Ranger (2, fixed), Rogue (2, fixed). Bard, Cleric, Druid, Monk,
Sorcerer, Warlock, Wizard do **not** get a Weapon Mastery class feature in
this SRD text. Which specific property applies to which weapon is determined
by the **Weapons table** (a "Mastery" column per weapon, referenced at line
6046 but the full per-weapon table itself is outside the assigned Classes/
Feats/Species line range — see Equipment section, out of scope for this
document).

---

## 7. Character Backgrounds (lines 5574-5621)

Only **4 backgrounds** are detailed in this SRD text (a minimal starter set —
the 2024 PHB proper has 16; this parse only includes these 4):

| Background | Ability Scores | Feat | Skills | Tool | Equipment | Line |
|---|---|---|---|---|---|---|
| Acolyte | Int, Wis, Cha | Magic Initiate (Cleric) | Insight, Religion | Calligrapher's Supplies | (A) Calligrapher's Supplies+Book(prayers)+Holy Symbol+Parchment(10)+Robe+8 GP or (B) 50 GP | 5604-5606 |
| Criminal | Dex, Con, Int | Alert | Sleight of Hand, Stealth | Thieves' Tools | (A) 2 Daggers+Thieves' Tools+Crowbar+2 Pouches+Traveler's Clothes+16 GP or (B) 50 GP | 5608-5610 |
| Sage | Con, Int, Wis | Magic Initiate (Wizard) | Arcana, History | Calligrapher's Supplies | (A) Quarterstaff+Calligrapher's Supplies+Book(history)+Parchment(8)+Robe+8 GP or (B) 50 GP | 5612-5614 |
| Soldier | Str, Dex, Con | Savage Attacker | Athletics, Intimidation | 1 Gaming Set (choice) | (A) Spear+Shortbow+20 Arrows+Gaming Set+Healer's Kit+Quiver+Traveler's Clothes+14 GP or (B) 50 GP | 5616-5620 |

Every background applies the ability-score rule from §1: +2/+1 split across
two of its three listed abilities, or +1/+1/+1 across all three (cap 20;
line 5584).

---

## 8. Character Species (lines 5622-5837)

All 9 species named at line 995 appear here in full. Every species is
Humanoid creature type (line 5638). Note: species grant **no ability score
increases** in this edition (that moved to Background, §1/§7).

### Dragonborn (5654-5680)

Size Medium (5-7 ft), Speed 30 ft.

| Trait | Effect | Line |
|---|---|---|
| Draconic Ancestry | Choose a dragon type from the table below; determines Breath Weapon/Resistance damage type | 5660-5671 |
| Breath Weapon | Replace one Attack-action attack: 15-ft Cone or 30-ft×5-ft Line, Dex save DC=8+Con mod+Prof; fail=1d10 dmg (type per ancestry), success=half; scales 2d10(lvl5)/3d10(lvl11)/4d10(lvl17); uses=Prof Bonus | 5672-5674 (Long Rest) |
| Damage Resistance | Resistance to ancestry's damage type | 5676 |
| Darkvision | 60 ft | 5678 |
| Draconic Flight | From char level 5: Bonus Action, Fly Speed = Speed for 10 min or until retracted/Incapacitated | 5680 (1/Long Rest) |

**Draconic Ancestors table** (5662-5671): Black=Acid, Blue=Lightning,
Brass=Fire, Bronze=Lightning, Copper=Acid, Gold=Fire, Green=Poison, Red=Fire,
Silver=Cold, White=Cold.

### Dwarf (5682-5696)

Size Medium (4-5 ft), Speed 30 ft.

| Trait | Effect | Line |
|---|---|---|
| Darkvision | 120 ft | 5688 |
| Dwarven Resilience | Resistance to Poison damage; Advantage on saves to avoid/end Poisoned | 5690 |
| Dwarven Toughness | HP max +1, +1 again every level gained | 5692 |
| Stonecunning | Bonus Action: Tremorsense 60 ft for 10 min, while on/touching stone; uses=Prof Bonus | 5694-5696 (Long Rest) |

### Elf (5698-5724)

Size Medium (5-6 ft), Speed 30 ft.

| Trait | Effect | Line |
|---|---|---|
| Darkvision | 60 ft | 5704 |
| Elven Lineage | Choose a lineage (table below); gain lvl1 benefit; learn a higher-level spell at char lvl3 and lvl5, always prepared, 1 free cast/Long Rest, spellcasting ability chosen from Int/Wis/Cha | 5706-5718 |
| Fey Ancestry | Advantage on saves to avoid/end Charmed | 5720 |
| Keen Senses | Proficiency in Insight, Perception, or Survival (choice) | 5722 |
| Trance | No sleep needed, immune to magical sleep; Long Rest in 4 hrs of trance | 5724 |

**Elven Lineages table** (5710-5718): Drow — lvl1: Darkvision→120ft + Dancing
Lights cantrip; lvl3: Faerie Fire; lvl5: Darkness. High Elf — lvl1:
Prestidigitation cantrip (swappable on Long Rest); lvl3: Detect Magic; lvl5:
Misty Step. Wood Elf — lvl1: Speed→35ft + Druidcraft cantrip; lvl3:
Longstrider; lvl5: Pass without Trace.

### Gnome (5726-5740)

Size Small (3-4 ft), Speed 30 ft.

| Trait | Effect | Line |
|---|---|---|
| Darkvision | 60 ft | 5732 |
| Gnomish Cunning | Advantage on Int, Wis, Cha saves | 5734 |
| Gnomish Lineage | Choose Forest Gnome or Rock Gnome (below); spellcasting ability chosen from Int/Wis/Cha | 5736-5740 |

**Forest Gnome** (5738): know Minor Illusion; always have Speak with Animals
prepared, castable free = Prof Bonus times/Long Rest, or via a spell slot.

**Rock Gnome** (5740): know Mending + Prestidigitation; spend 10 min casting
Prestidigitation to create a Tiny clockwork device (AC 5, 1 HP) with one
chosen Prestidigitation effect, activated via touch + Bonus Action; max 3
devices at once, each lasts 8 hrs or until dismantled (Utilize action).

### Goliath (5742-5765)

Size Medium (7-8 ft), Speed 35 ft.

| Trait | Effect | Line |
|---|---|---|
| Giant Ancestry | Choose 1 of 6 giant-type benefits below; uses=Prof Bonus | 5748-5761 (Long Rest) |
| Large Form | From char level 5: Bonus Action, become Large (if space allows), 10 min or dismiss: Advantage Str checks, +10 ft Speed | 5762 (1/Long Rest) |
| Powerful Build | Advantage on checks to end Grappled; count as 1 size larger for carrying capacity | 5764 |

**Giant Ancestry options** (5750-5760): Cloud's Jaunt (Cloud Giant) — Bonus
Action teleport 30 ft to seen unoccupied space. Fire's Burn (Fire Giant) — on
damaging hit, +1d10 Fire. Frost's Chill (Frost Giant) — on damaging hit,
+1d6 Cold + target Speed −10ft until your next turn. Hill's Tumble (Hill
Giant) — on damaging hit vs Large-or-smaller, target Prone. Stone's
Endurance (Stone Giant) — Reaction on taking damage: roll 1d12+Con mod,
reduce damage by that. Storm's Thunder (Storm Giant) — Reaction on taking
damage from within 60 ft: deal 1d8 Thunder back.

### Halfling (5766-5780)

Size Small (2-3 ft), Speed 30 ft.

| Trait | Effect | Line |
|---|---|---|
| Brave | Advantage on saves to avoid/end Frightened | 5774 |
| Halfling Nimbleness | Move through space of a creature 1 size larger, can't stop there | 5776 |
| Luck | On a natural 1 (d20 Test), reroll and must use new result | 5778 |
| Naturally Stealthy | Can Hide while obscured only by a creature ≥1 size larger | 5780 |

### Human (5782-5794)

Size Medium (4-7 ft) or Small (2-4 ft), chosen at creation. Speed 30 ft.

| Trait | Effect | Line |
|---|---|---|
| Resourceful | Gain Heroic Inspiration on finishing a Long Rest | 5790 |
| Skillful | Proficiency in 1 chosen skill | 5792 |
| Versatile | Gain an Origin feat of choice (Skilled recommended) | 5794 |

### Orc (5804-5817)

Size Medium (6-7 ft), Speed 30 ft.

| Trait | Effect | Line |
|---|---|---|
| Adrenaline Rush | Bonus Action Dash; gain Temp HP = Prof Bonus; uses=Prof Bonus | 5810-5812 (Short or Long Rest) |
| Darkvision | 120 ft | 5814 |
| Relentless Endurance | On drop to 0 HP (not killed outright), drop to 1 HP instead; 1 use | 5816 (Long Rest) |

### Tiefling (5818-5837)

Size Medium (4-7 ft) or Small (3-4 ft), chosen at creation. Speed 30 ft.

| Trait | Effect | Line |
|---|---|---|
| Darkvision | 60 ft | 5826-5828 |
| Fiendish Legacy | Choose a legacy (table below); gain lvl1 benefit; learn higher-level spell at char lvl3/lvl5, always prepared, 1 free cast/Long Rest; spellcasting ability chosen from Int/Wis/Cha | 5830-5834 |
| Otherworldly Presence | Know Thaumaturgy cantrip, cast using Fiendish Legacy's chosen ability | 5836 |

**Fiendish Legacies table** (5798-5802): Abyssal — lvl1: Resistance Poison +
Poison Spray cantrip; lvl3: Ray of Sickness; lvl5: Hold Person. Chthonic —
lvl1: Resistance Necrotic + Chill Touch cantrip; lvl3: False Life; lvl5: Ray
of Enfeeblement. Infernal — lvl1: Resistance Fire + Fire Bolt cantrip; lvl3:
Hellish Rebuke; lvl5: Darkness.

---

## 9. Feats (lines 5838-6021)

Categories per line 5842: Origin, General, Fighting Style, Epic Boon.

### Origin Feats

| Feat | Prerequisite | Effect | Line |
|---|---|---|---|
| Alert | — | Initiative Proficiency (add Prof Bonus to Initiative roll); Initiative Swap (swap your rolled Initiative with a willing, non-Incapacitated ally's) | 5858-5866 |
| Magic Initiate | — | Learn 2 cantrips from Cleric/Druid/Wizard list (choose 1 list); learn 1 lvl1 spell from same list, always prepared, 1 free cast/Long Rest, or via a slot; swap 1 spell/level gained; **Repeatable** (different list each time) | 5868-5880 |
| Savage Attacker | — | 1/turn on weapon hit, roll damage dice twice, use either result | 5882-5886 |
| Skilled | — | Proficiency in any combination of 3 skills/tools; **Repeatable** | 5888-5894 |

### General Feats

| Feat | Prerequisite | Effect | Line |
|---|---|---|---|
| Ability Score Improvement | Level 4+ | +2 to one ability score, or +1 to two ability scores (cap 20); **Repeatable** | 5898-5904 |
| Grappler | Level 4+, Str or Dex 13+ | +1 Str or Dex (max 20); Punch and Grab (Unarmed Strike hit as part of Attack action can apply both Damage and Grapple, 1/turn); Attack Advantage (Advantage vs creatures you've Grappled); Fast Wrestler (no extra movement cost to move a same-size-or-smaller Grappled creature) | 5906-5918 |

*(Note: this SRD excerpt provides only 2 General Feats — Ability Score
Improvement and Grappler. The full 2024 PHB has many more (Actor, Athlete,
Charger, Chef, Crusher, Durable, Elemental Adept, etc.); those are not
present in this parsed text and must not be assumed to exist in this
codebase's data.)*

### Fighting Style Feats

All four require the "Fighting Style Feature" as prerequisite (i.e. a class
feature that says "gain a Fighting Style feat," such as Fighter lvl1, Paladin
lvl2, Ranger lvl2).

| Feat | Effect | Line |
|---|---|---|
| Archery | +2 to attack rolls with Ranged weapons | 5922-5926 |
| Defense | +1 AC while wearing Light/Medium/Heavy armor | 5928-5932 |
| Great Weapon Fighting | Treat a 1 or 2 on a damage die as a 3, for two-handed/Versatile Melee weapons held two-handed | 5934-5938 |
| Two-Weapon Fighting | Add ability modifier to damage of the extra Light-property attack (if not already added) | 5940-5944 |

### Epic Boon Feats

All require Level 19+.

| Feat | Effect | Line |
|---|---|---|
| Boon of Combat Prowess | +1 ability score (max 30); Peerless Aim: turn a missed attack into a hit, 1/until start of next turn | 5948-5956 |
| Boon of Dimensional Travel | +1 ability score (max 30); Blink Steps: teleport 30 ft to a seen unoccupied space immediately after Attack or Magic action | 5958-5966 |
| Boon of Fate | +1 ability score (max 30); Improve Fate: roll 2d4, apply as bonus/penalty to a nearby (60 ft) D20 Test result after seeing it; 1/until Initiative roll or Short/Long Rest | 5968-5976 |
| Boon of Irresistible Offense | +1 Str or Dex (max 30); Overcome Defenses (B/P/S damage ignores Resistance always); Overwhelming Strike (nat-20 attack deals extra damage = the boosted ability score) | 5978-5988 |
| Boon of Spell Recall | Prereq also Spellcasting feature; +1 Int/Wis/Cha (max 30); Free Casting: on casting w/ a lvl1-4 slot, roll 1d4 — matching the slot's level means the slot isn't expended | 5990-5998 |
| Boon of the Night Spirit | +1 ability score (max 30); Merge with Shadows (Bonus Action Invisible in Dim Light/Darkness, ends after an action/bonus/reaction); Shadowy Form (Resistance to all but Psychic/Radiant in Dim Light/Darkness) | 6000-6010 |
| Boon of Truesight | +1 ability score (max 30); Truesight 60 ft | 6012-6020 |

**OCR garbling flagged**: Line 1133 (`## unaliGnEd crEaturEs`, within Character
Creation's Alignment section, not Feats) — same mixed-case-mangling pattern
as line 5139's Wizard heading; flagged per instructions even though it falls
outside the Feats section proper, since it's an instance of the same known
artifact class. Line 6048 (`## sEllinG EquipMEnt`) is the same artifact
pattern, appearing in the Equipment section just past the Feats boundary —
noted here for completeness but not catalogued further since Equipment is
out of scope.

---

## 10. Weapon Mastery — Full Class Cross-Reference

(Consolidated from §4 and §6 for convenience.)

| Class | Weapon Mastery? | Slot progression | Line |
|---|---|---|---|
| Barbarian | Yes | 2 (1-3) → 3 (4-9) → 4 (10-20) | 1532-1553 |
| Bard | No | — | — |
| Cleric | No | — | — |
| Druid | No | — | — |
| Fighter | Yes | 3 (1-3) → 4 (4-9) → 5 (10-15) → 6 (16-20) | 2943-2964 |
| Monk | No (Monk instead has Martial Arts die + Ki/Focus Points, not Weapon Mastery) | — | — |
| Paladin | Yes | 2 (fixed, all levels) | 3386-3390 |
| Ranger | Yes | 2 (fixed, all levels) | 3673-3677 |
| Rogue | Yes | 2 (fixed, all levels) | 3927-3931 |
| Sorcerer | No | — | — |
| Warlock | No | — | — |
| Wizard | No | — | — |

---

## Summary of OCR/Parsing Issues Found (all flagged, none silently corrected)

1. **Line 1133** — `## unaliGnEd crEaturEs` (mixed-case mangled heading, Character Creation §Alignment).
2. **Line 1960, 1982-2065** — Bard Level 5/6/7 spell tables collapse into disjoint Spell/School/Special line dumps.
3. **Lines 2760-2795** — Druid Level 6-9 spell tables show the same collapse pattern.
4. **Lines 2806-2897** — Druid's Circle of the Land per-land-type Circle Spells tables are severely garbled/interleaved; only the Tropical Land table parsed cleanly. Arid/Polar/Temperate entries in §4.4 are best-effort reconstructions from surrounding context and need verification against the official 2024 PHB.
5. **Line 5139** — `## ExpandinG and rEplacinG a spEllBook` (mixed-case mangled heading, Wizard class).
6. **Lines 5306-5344, 5444-5505** — Wizard Level 4 and Level 7 spell tables collapse into disjoint line dumps.
7. **Lines 4827-4844, 4886-4944** — Warlock cantrip list and Level 2-3 spell tables collapse into disjoint line dumps (worse than most other classes).
8. **Line 6048** — `## sEllinG EquipMEnt` (mixed-case mangled heading, Equipment section, just past this document's assigned scope).
9. **Line 3408** — `## BrEakinG your oatH` (mixed-case mangled heading, Paladin class, preceding the Level 3 Channel Divinity/Divine Sense text). Correct heading is almost certainly "Breaking Your Oath." The prose under this heading is flavor/procedural text (seek absolution, talk to your GM, possibly reflavor/abandon the class) with no independent dice, DC, or resource mechanic of its own — the one mechanical sentence it contains ("If a Channel Divinity effect requires a saving throw, the DC equals the spell save DC from this class's Spellcasting feature") is already captured via the Channel Divinity rows in §4.7. Flagged for completeness per the same mixed-case-mangling pattern as items 1, 5, and 8.

None of these affect the class-feature mechanics tables in §4 (which come from prose, not the garbled tabular spell lists) — they only affect spell-list transcription and a handful of purely-narrative subheadings, which were explicitly out of scope or non-mechanical.
