# SRD 5.2.1 Spellcasting Mechanics Catalogue

Source: `parsed_data/srd_cc_v5.2.1/docling.md` (2024 SRD 5.2.1, 24,275 lines) and
`data/rules/srd/spells.json` (319 vendored spell entries).

Scope of this document: character-creation-level spellcasting rules, the full
"Spells" rules chapter and A-Z spell descriptions, monster spellcasting rules,
spellcasting services, the 8 player-class spellcasting feature blocks, the 10
Sorcerer Metamagic options, and a field-by-field audit of `spells.json` against
those rules. This document does **not** assess the game engine's Python
implementation — that is a separate audit.

All line numbers refer to `parsed_data/srd_cc_v5.2.1/docling.md`.

---

## 1. The Spellcasting Rules Engine

| Mechanic | SRD line | Rule (precise) | Notes |
|---|---|---|---|
| Gaining spells | 7110-7113 | Before casting, a spell must be prepared in mind or accessible via a magic item (e.g. Spell Scroll). Class features define what's accessible, what's always prepared, and whether the prepared list can change. | |
| Preparing spells | 7114-7132 | "Spell Preparation by Class" table dictates *when* the list changes and *how many* spells change: Bard/Sorcerer/Warlock = on level-up, one spell; Cleric/Druid/Wizard = on Long Rest, any number; Paladin/Ranger = on Long Rest, one spell. | Monsters usually don't change prepared lists (GM discretion). |
| Always-prepared spells | 7133-7135 | A spell granted as "always prepared" by a feature doesn't count against the class's normal prepared-spell count, but still counts as a spell of that class for the character. | E.g. Paladin's Divine Smite (3400), Druid's Speak with Animals (2535). |
| Casting in armor | 7141-7143 | Must have training with worn armor to cast spells in it; otherwise too hampered to cast at all. | Binary gate, not a penalty. |
| Spell level | 7145-7147 | Spells are level 0 (cantrip) through 9. Level indicates power; class rules gate access by character/class level. | |
| Spell slots | 7149-7156 | Casting a level-N+ spell expends one slot of level N or higher. A lower-level spell can fill a higher-level slot ("fits into a slot of any size ≥ its own"). Long Rest restores all expended slots. | Exception: Warlock Pact Magic slots restore on Short *or* Long Rest (4571); Sorcerer Sorcery Points restore on Long Rest, partially on Short Rest via Sorcerous Restoration (4175). |
| Casting without slots | 7157-7164 | Four routes: (1) Cantrips never use slots; (2) Rituals (spell has the Ritual tag, caster must have it prepared, takes +10 minutes, no slot spent); (3) special abilities (e.g. Paladin's free Divine Smite, limited uses/day); (4) magic items (Spell Scrolls, wands, etc., item description caps uses). | |
| Upcasting (higher-level slot) | 7165-7169 | Casting with a slot above the spell's base level makes the spell take on that higher level for the casting. Some spells have explicit "Using a Higher-Level Spell Slot" text describing the enhanced effect; if not, the spell simply becomes higher-level with no other change. | |
| School of magic | 7171-7187 | 8 schools, each with a "typical effects" one-liner: Abjuration (prevent/reverse harm), Conjuration (transport), Divination (reveal info), Enchantment (influence minds), Evocation (channel destructive energy), Illusion (deceive senses), Necromancy (life/death manipulation), Transmutation (transform). Schools are flavor/categorization only — "no rules of their own" except where other rules reference them (e.g. Globe of Invulnerability blocks by level not school; but some magic items/features do key off school). | |
| Class spell lists | 7188-7190 | A spell lists class names in parens after its school if that class can cast it (e.g. "Evocation (Sorcerer, Wizard)"). Some features add spells to a character's list outside their class (e.g. Paladin's Blessed Warrior granting Cleric cantrips, 3396). | |
| Casting time | 7192-7194 | Most spells need the Magic action; others need a Bonus Action, a Reaction, or 1+ minutes. | |
| One leveled spell slot per turn | 7196-7198 | On a single turn, only **one** spell slot can be expended total — can't cast a slotted spell via the Magic action *and* another slotted spell via a Bonus Action in the same turn. | Cantrips are unaffected since they don't expend slots. Sorcerer's Quickened Spell Metamagic (4229-4233) explicitly reinforces/interacts with this: converting a spell to a Bonus Action blocks casting another leveled spell that turn, in either order. |
| Reaction/Bonus Action triggers | 7200-7202 | A Reaction-cast spell fires on the trigger defined in its own Casting Time entry (e.g. Counterspell: "which you take when you see a creature... casting a spell", 8222). Some Bonus Action spells are also trigger-conditioned. | |
| Longer casting times (1+ minutes / Rituals) | 7204-7206 | Must take the Magic action every turn of the casting and maintain Concentration throughout. Breaking Concentration fails the spell (no slot expended) and casting must restart from scratch. | |
| Range | 7208-7219 | Three forms: Distance (feet), Touch (must touch within reach), Self (caster or emanates from caster). Movable spell effects aren't range-limited after creation unless stated otherwise. | |
| Components — general | 7221-7223 | V/S/M as specified per spell. Missing any required component type = can't cast. | |
| Verbal (V) | 7225-7227 | Chanted words in a normal speaking voice; gagged creatures or those in magical silence can't provide it. | |
| Somatic (S) | 7229-7231 | Forceful gesture requiring at least one free hand. | |
| Material (M) | 7233-7238 | Named material in parens; not consumed unless spell says so. Caster needs a free hand (can double as the S-component hand). If no cost is specified and materials aren't consumed, a Component Pouch or (if a class feature allows) a Spellcasting Focus can substitute. Focus must be held unless stated otherwise. | Costed/consumed materials (e.g. "diamond dust worth 100+ GP, which the spell consumes", 9305) can **never** be replaced by a pouch/focus — must be the literal, costed component. |
| Spellcasting Focus | 12760-12762 | An object substitutable for Material components that aren't consumed and have no listed cost; only usable if a class feature grants that substitution right. | Per-class focus types: Bard=Musical Instrument (1795), Cleric/Paladin=Holy Symbol (2188, 3384), Druid/Ranger=Druidic Focus (2531, 3665), Sorcerer/Warlock=Arcane Focus (implicit/4585), Wizard=Arcane Focus or spellbook itself (5119). |
| Duration | 7239-7245 | Three forms: Concentration (see below), Instantaneous (effect resolves once, no lingering), Time Span (explicit unit; a non-Incapacitated caster can dismiss a time-span spell early, no action required). | |
| Effects / Targets | 7247-7257 | Effects section defines outcome; targeting requires a clear path (no Total Cover); a spell targeting "a creature of your choice" can target self unless restricted to Hostile/others-only. | |
| Areas of effect | 7259, 12104-12768 | Six canonical shapes: **Cone** (width at any point = distance from origin; origin excluded unless stated, 12104-12108), **Cube** (side length; origin excluded unless stated, 12139-12143), **Cylinder** (radius of circular base + height; origin **included**, 12149-12153), **Emanation** (extends from a creature/object in all directions, moves with its source unless instantaneous/stationary; origin excluded unless stated, 12273-12279), **Line** (length × width; origin excluded unless stated, 12501-12505), **Sphere** (radius from point of origin; origin **included**, 12764-12768). | Distinct inclusion/exclusion-of-origin rules per shape are easy to get wrong in an engine. |
| Awareness of targeting | 7261 | A target only knows it was targeted if the effect is perceptible (e.g. lightning is obvious; a thought-reading attempt is not, unless the spell says otherwise). | |
| Invalid targets | 7263-7265 | Casting on an ineligible target: nothing happens, but a slot is still expended if used. If the spell would otherwise no-op on a successful save, the target *appears* to have succeeded (no tell that it was actually invalid). | |
| Saving throws | 7267-7271 | `Spell save DC = 8 + spellcasting ability modifier + Proficiency Bonus`. Spell specifies the ability used and success/failure effects. A target lacking the required ability score auto-fails (12694). | |
| Attack rolls | 7273-7277 | `Spell attack modifier = spellcasting ability modifier + Proficiency Bonus`. | |
| Combining spell effects | 7279-7281 | Different spells' effects stack while durations overlap. The *same* spell cast multiple times on one target does **not** stack — only the most potent instance applies (most recent wins on ties). | Named worked example: two Clerics both casting Bless on one target grants the benefit once, not doubled dice. |
| Identifying an ongoing spell | 7283-7286 | Take the Study action + succeed on a DC 15 Intelligence (Arcana) check to identify a non-instantaneous spell by its observable, ongoing effects. | |
| Concentration | 12081-12089 | Casting/activating a second Concentration effect ends the first automatically. Taking damage forces a Constitution save, `DC = max(10, floor(damage/2))`, capped at DC 30, to maintain Concentration. Concentration ends immediately if Incapacitated or dead. Caster may voluntarily end Concentration anytime, no action required. | |
| Ritual casting | 7161, 12680-12682 | Only spells with the Ritual tag; caster must have it prepared (Wizards are the sole exception — see Ritual Adept below); takes +10 minutes vs. normal casting time; never expends a slot; therefore **cannot** be upcast when cast as a Ritual. | |
| Counterspell | 8218-8233 | Level 3 Abjuration, Reaction (trigger: seeing a creature within 60 ft. cast a spell with V/S/M components), Range 60 ft, Components S. Target makes a Constitution save; on a failed save the interrupted spell dissipates with no effect and the action/Bonus Action/Reaction used to cast it is wasted; if a slot was spent on the countered spell, that slot is **not** refunded. Save DC uses the general spell save DC formula (8 + mod + PB) of the Counterspell caster. | **Confirmed rules change from 2014**: the 2024 entry (8218-8233) has no "Using a Higher-Level Spell Slot" paragraph at all — verified the text runs directly from "the slot isn't expended" (8232) to the next spell header, "Create Food and Water" (8234), with nothing omitted. 2024 Counterspell is a flat CON save regardless of the slot spent to cast it; it no longer auto-succeeds against lower-level spells the way 2014's version did. An engine must not port 2014 Counterspell-scaling logic. |
| Dispel Magic | 8472-8481 | Level 3 Abjuration, Action, 120 ft, V/S, Instantaneous. Targets one creature/object/effect: any ongoing spell of level ≤3 on it automatically ends. For each ongoing spell of level 4+, make an ability check with your spellcasting ability, `DC = 10 + that spell's level`; success ends it. Using a higher-level slot: automatically ends any spell whose level ≤ the slot's level (no check needed). | |
| Scribing Spell Scrolls | 7078-7107 | Time/cost by spell level (table): Cantrip 1 day/15gp, L1 1 day/25gp, L2 3 days/100gp, L3 5 days/150gp, L4 10 days/1,000gp, L5 25 days/1,500gp, L6 40 days/10,000gp, L7 50 days/12,500gp, L8 60 days/15,000gp, L9 120 days/50,000gp. 8 hrs/day of work; non-consecutive days allowed. Scribe needs Arcana proficiency OR Calligrapher's Supplies proficiency, and must have the spell prepared every day of inscription, with any required Material components in hand (consumed only on completion if the spell consumes them). The scroll uses the *scribe's* spell save DC and attack bonus. | Cantrip scrolls scale to the caster's level when made (7092). |
| Casting a Spell Scroll | 6803-6810, 4025-4039 | If the scroll's spell is on the reader's class list: cast at normal casting time, no Material components needed. The Rogue's level-13 **Use Magic Device** feature (4025-4039, not Wizard-specific — corrected from an earlier draft) separately lets a Rogue use *any* Spell Scroll via Intelligence regardless of class list: cantrip/L1 spells cast reliably, higher-level scroll spells require an Intelligence (Arcana) check, `DC = 10 + spell level`; failure **disintegrates** the scroll with no effect. | The generic "Spell Scroll" item rule (6803) is class-agnostic (any qualifying caster can use a scroll on their own list); the Rogue's Use Magic Device is the named exception that bypasses the class-list restriction entirely. Use Magic Device also raises the Rogue's Attunement cap to 4 items (4034) and gives a 1-in-6 chance to not expend charges (4036) — both adjacent magic-item mechanics worth modeling alongside scroll use. |
| Copying a scroll into a spellbook | 16280 | Wizard-only: DC = 10 + spell's level, Intelligence (Arcana) check. Success copies the spell; scroll is destroyed either way (success or failure). | |
| Magic items that cast spells | 13740-13742, 15932-15940, and per-item entries (e.g. 14487, 14508, 14629, 14784, 15076, 15233, 15316, 15793, 15829, 15917, 15972, 16302-16309) | Items with **Charges**: expend N charges to cast a named spell, usually at a **fixed save DC printed on the item** (independent of the wielder's own spellcasting stats), with charges regenerating on a schedule (commonly 1dX charges "daily at dawn"). Some items (e.g. crystal lenses, 14784) let extra charges upcast the spell. **Ring of Spell Storing** (15932-15940) is the odd case: any creature can cast a L1-5 spell *into* the ring; a wearer later casts it out using the **original caster's** slot level, DC, attack bonus, and spellcasting ability. Wands (13670-13674) double as an Arcane Focus by default. | |
| Attunement (gating magic-item spellcasting) | 7022-7030 | Some items require Attunement (a bonded Short Rest of focused use, in physical contact with the item) before magical properties — including spellcasting properties — function; an unattuned item that requires Attunement grants only nonmagical benefits. Base cap is **3 attuned items at once** (7028-7030); cannot attune to more than one copy of the same item. | The Rogue's Use Magic Device feature (4034) raises this personal cap to 4. |
| Monster spellcasting | 17038-17047 | A monster stat block lists its spells plus spellcasting ability, spell save DC, and spell attack bonus as needed. Unless stated otherwise, monster spells of level 1+ are always cast at their lowest possible level (no upcasting). Restrictions can be spell-specific (e.g. a green hag's Invisibility is "self only", 17042). Spell Components note (17044): the trait states whether the monster's casting ignores component requirements; if any are required, the GM narrates V/S/M cues, and a Material-requiring monster is assumed to possess them. Casting Times of 1+ minutes (17046) forces the monster to take the Magic action every turn and maintain Concentration exactly like a PC, unless its stat block explicitly overrides this. | |
| Spellcasting services | 6992-7007 | NPC spellcasters for hire, cost scaling by spell level and settlement size: Cantrip 30gp (village+), L1 50gp (village+), L2 200gp (village+), L3 300gp (town+), L4-5 2,000gp (town+), L6-8 20,000gp (city only), L9 100,000gp (city only). Expensive Material component costs are added on top. | |

---

## 2. Spell Mechanics Taxonomy (effect types an engine must model)

Derived from scanning all A-Z spell descriptions (lines 7289-11854).

| Effect type | Example spells (line) | Mechanic detail |
|---|---|---|
| **Attack-roll spells** | Fire Bolt (8953): ranged spell attack, 1d10 Fire, scales by character level. Chromatic Orb (7857): ranged spell attack, 3d8 chosen damage type. Scorching Ray (10744): multiple rays, each its own attack roll. Shocking Grasp (10960): melee spell attack, 1d8 Lightning, target loses Reactions until start of its next turn. | Attack vs. AC using `spell attack modifier`; on-hit damage or effect. |
| **Save-or-suffer** (no half-damage clause) | Command (7935): Wisdom save or follow a one-word command (Approach/Drop/Flee/Grovel→Prone/Halt) on its next turn. Color Spray (7927): CON save or Blinded. Sleep (11022): WIS save or Incapacitated→Unconscious, zero damage. Bane (7618): CHA save or -1d4 on attack/saves for duration. | Full effect applies only on a failed save; success = no effect at all. |
| **Save-for-half** | Fireball (8941): DEX save, 8d6 Fire, half on success. Cone of Cold (8001): CON save, 8d8 Cold, half on success. Shatter (10872): CON save, 3d8 Thunder, half on success. Meteor Swarm (10093): DEX save, 20d6+20d6, half on success. | Canonical phrase: "half as much damage on a successful save." |
| **Auto-effect** (no roll of any kind) | Magic Missile (9937): 3 darts auto-hit, 1d4+1 Force each, upcasts to +1 dart/slot level. Misty Step (10173): instant 30-ft teleport. Detect Magic (8388): senses magic auras automatically. | No attack roll or save gates the effect. |
| **Healing** | Cure Wounds (8292): 1d8 + spellcasting mod. Mass Cure Wounds (10011): 5d8+mod to up to 6 creatures. Healing Word (9450): 2d4+mod, Bonus Action. Heal (9440): flat 70 HP + cures Blinded/Deafened/Poisoned. | Restores current HP, sometimes with side-effect condition removal. |
| **Temporary HP granting** | False Life (8811): 2d4+4 Temp HP. Heroism (9502): grants mod Temp HP at the start of each of the target's turns while Concentration holds. Polymorph (10343)/Shapechange (10856)/True Polymorph (11537): target gains Temp HP equal to the new form's own HP total. | Distinct pool from current HP; does not stack with itself (per Combining Spell Effects, 7279). |
| **Condition application** | Hold Person (9546)/Hold Monster (9538): WIS save or Paralyzed. Flesh to Stone (9025): CON save or Restrained → (3 failed saves) Petrified. Hideous Laughter (9524): WIS save or Prone+Incapacitated. Banishment (7640): CHA save or effectively removed from play. | Applies one of the 13 named SRD conditions (12091-12102: Blinded, Charmed, Deafened, Exhaustion, Frightened, Grappled, Incapacitated, Invisible, Paralyzed, Petrified, Poisoned, Prone, Restrained, Stunned, Unconscious — conditions don't stack with themselves except Exhaustion). |
| **Summoning/creating creatures** | Find Familiar (8843), Find Steed (8871): permanent-ish companion creatures with their own stat blocks embedded. Conjure Elemental (8064)/Conjure Fey (8078)/Conjure Celestial (8044): temporary spirit allies, share caster's Initiative. Summon Dragon (11276): summons a "Draconic Spirit" stat block (11290). Animate Dead (7378): raises Skeleton/Zombie. | Summoned creatures typically act on the caster's Initiative count, immediately after the caster's turn, and vanish at 0 HP or spell end. |
| **Terrain/object creation** | Wall of Fire (11659), Wall of Stone (11701), Wall of Force (11675): solid/semi-solid barriers. Spike Growth (11152): converts terrain to a damaging hazard + Difficult Terrain. Floating Disk (9037): creates a persistent utility object. Creation (8270): conjures a real (or quasi-real, per Materials note at 8280) physical object from raw shadowstuff. | |
| **Movement/teleportation** | Dimension Door (8424): short-range self+one-ally teleport. Teleport (11405) + Teleportation Outcome table (11415): long-range teleport with a randomized mishap table by familiarity. Gust of Wind (9369)/Thunderwave (via Line/Cone push, cross-ref 7259): forced-movement pushes. Fly (9049): grants a Fly Speed. | Distinguish self-movement grants (Fly, Levitate) from forced-movement-of-others (Gust of Wind) and true teleport/plane-shift. |
| **Buffs/debuffs to rolls** | Bless (7726): +1d4 to attack rolls and saving throws. Bane (7618): -1d4 to attack rolls and saving throws. Haste (9430): +2 AC, Advantage on DEX saves, extra action (limited menu). Guidance (9351): +1d4 to one ability check. Foresight (9103): Advantage on all D20 Tests, imposes Disadvantage on attackers targeting the recipient. | Includes flat/dice bonuses and Advantage/Disadvantage grants; can target self, allies, or impose penalties on enemies. |
| **Resistance/immunity granting** | Protection from Energy (10558): Resistance to one chosen damage type. Death Ward (8342): negates being dropped to 0 HP once. Heroes' Feast (9484): Immunity to Frightened + Poisoned, Resistance to Poison. Mind Blank (10103): Immunity to Psychic damage and to being Charmed. | |
| **Dispelling/counter magic** | Counterspell (8218), Dispel Magic (8472), Antimagic Field (7431, suppresses magic in an area rather than ending a specific spell), Globe of Invulnerability (9243, blocks incoming spells of level ≤5 rather than dispelling existing ones). | Three distinct sub-mechanics: interrupt-before-cast (Counterspell), end-existing-effect (Dispel Magic), and area-suppression/block (Antimagic Field, Globe of Invulnerability) — an engine should not conflate them. |
| **Divination/information gathering** | Detect Magic (8388), Clairvoyance (7885, remote sensor), Scrying (10754, remote sensor + save to resist), Legend Lore (9752), Augury (7559, an omen die roll about a planned action). | |
| **Illusion** | Minor Illusion (10121), Major Image (9985), Mirror Image (10149, duplicate decoys with their own "hit chance" mechanic), Disguise Self (8436), Programmed Illusion (10530, triggered illusion), Phantasmal Killer (10255, psychic-damage illusion). | Illusions vary from purely cosmetic (no game-mechanical effect) to damaging (Phantasmal Killer, Weird at 11779) to decoy/defensive (Mirror Image). |
| **Shape-shifting/polymorph** | Alter Self (7330), Polymorph (10343), True Polymorph (11537, can be permanent), Shapechange (10856, into any creature caster has seen), Animal Shapes (7366, mass-polymorph allies into Beast forms), Gaseous Form (9137, form with unique movement/resistance package). | |
| **Ongoing/recurring damage** | Cloudkill (7913): 5d8 Poison/turn while in the Sphere. Spirit Guardians (11174): damage on entering/ending turn in the emanation. Contagion (8124): disease progression with repeated saves. Storm of Vengeance (11248): different, escalating damage effect per subsequent round. Searing Smite (10782): 1d6 Fire/turn until a CON save succeeds. | Two flavors: area-based (damage whenever a creature is in/enters the zone) and target-locked (damage each turn on a specific creature until a save succeeds). |
| **Reactions/triggered effects** | Counterspell (8218): Reaction to observed casting. Shield (10884): Reaction to being hit or targeted by Magic Missile, +5 AC retroactively. Hellish Rebuke (9472): Reaction to taking damage. Feather Fall (8831): Reaction to falling. Symbol (11341) and Glyph of Warding (9251): non-Reaction triggered traps that fire on a physical trigger condition (touch/step/proximity/password) chosen at casting. | Distinguish true action-economy Reactions (cast using the Reaction) from triggered/delayed effects baked into a spell's own duration (glyphs/symbols, which are not "Reactions" mechanically but do fire on an external trigger). |

---

## 3. The 10 Sorcerer Metamagic Options (lines 4191-4260)

All cost Sorcery Points (from Font of Magic, 4133-4143); a Sorcerer can normally
use only **one** Metamagic option per spell cast (4161), with the two named
exceptions below.

| Option | Line | Cost | Effect |
|---|---|---|---|
| Careful Spell | 4195-4199 | 1 SP | For a spell forcing saves, choose up to your CHA modifier (min 1) targets who auto-succeed their save and take no damage even on a normal-half-damage effect. |
| Distant Spell | 4201-4205 | 1 SP | Double the range of a spell with range ≥5 ft; or turn a Touch-range spell into a 30-ft-range spell. |
| Empowered Spell | 4207-4213 | 1 SP | Reroll up to CHA-modifier (min 1) damage dice, must use new rolls. **Stackable** with another Metamagic option used on the same casting. |
| Extended Spell | 4215-4221 | 1 SP | Double a spell's duration (≥1 minute) up to a 24-hour cap. If the spell requires Concentration, gain Advantage on Concentration saves for it. |
| Heightened Spell | 4223-4227 | 2 SP | One target of a save-requiring spell gets Disadvantage on that save. |
| Quickened Spell | 4229-4233 | 2 SP | Change an action-cast spell's casting time to a Bonus Action. Interacts with the "one leveled spell per turn" rule: can't modify this way if a leveled spell was already cast this turn, and can't cast another leveled spell afterward on the same turn. |
| Seeking Spell | 4235-4241 | 1 SP | On a missed spell attack roll, reroll the d20 and use the new result. **Stackable** with another Metamagic option used on the same casting. |
| Subtle Spell | 4243-4247 | 1 SP | Cast with no V, S, or M components, except Material components that are consumed or have a listed cost. |
| Transmuted Spell | 4249-4253 | 1 SP | Change a spell's damage type among Acid/Cold/Fire/Lightning/Poison/Thunder. |
| Twinned Spell | 4255-4259 | 1 SP | For a spell that already has a higher-slot mechanism to add a target (e.g. Charm Person), spend 1 SP to add a target as if using a slot one level higher, without actually spending a higher slot. |

---

## 4. Per-Class Spellcasting Differences

| Class | Prepared vs. known | Ritual casting | Spellcasting ability | Focus | Unique mechanic | Key lines |
|---|---|---|---|---|---|---|
| **Bard** | Prepared list (cantrips are a separate fixed "known" pool) | Only for spells with the Ritual tag that are on the *prepared* list (implicit; no Wizard-style "any spell you know" ritual freedom stated) | Charisma | Musical Instrument | Standard prepared-caster; cantrips replaceable on level-up | 1773-1795 |
| **Cleric** | Prepared list, changeable on **every Long Rest**, "Any" number | Same as Bard (prepared spell only) | Wisdom | Holy Symbol | **Channel Divinity** (2198-2210) is a separate, non-slot resource (Divine Spark / Turn Undead) whose save DC reuses the class's spell save DC | 2166-2210 |
| **Druid** | Prepared list, changeable on Long Rest, "Any" number | Same pattern | Wisdom | Druidic Focus | Always has Speak with Animals prepared for free (Druidic feature, 2535); **Wild Shape** (2547-2552) is a non-spell shape-shifting resource, not itself a spell | 2509-2552 |
| **Paladin** | Prepared list, changeable on Long Rest, **one** spell at a time | Not called out as available (Paladin spell list has few/no Ritual-tagged spells; no ritual-casting feature granted) | Charisma | Holy Symbol | **No cantrips.** Always has Divine Smite prepared and can cast it once per Long Rest without a slot (Paladin's Smite, 3398-3400); Blessed Warrior fighting style option grants 2 Cleric cantrips using CHA (3396) | 3368-3400 |
| **Ranger** | Prepared list, changeable on Long Rest, **one** spell at a time | Not called out as available | Wisdom | Druidic Focus | **No cantrips** from the base class. Half-caster progression (slots start at level 1, unusually — table at 3629-3653 — reaching only 5th-level slots by level 17) | 3623-3665 |
| **Sorcerer** | Prepared list, changeable on level-up, **one** spell at a time | Not available (no Ritual Adept-equivalent feature) | Charisma | (Arcane Focus, implied; not explicitly restated in the class block but consistent with Warlock/Wizard pattern) | **Font of Magic / Sorcery Points** (4133-4143): convert slots↔points; **Metamagic** (§3); **Innate Sorcery** (free CHA-based bonus at levels 1 and 7, referenced 4181-4189) | 4074-4260 |
| **Warlock** | Prepared list, changeable on level-up, **one** spell at a time | Not available at base | Charisma | Arcane Focus | **Pact Magic**: very few slots (max 4) but all slots are always the *same*, high level (scales by class level, e.g. level-5 Warlock = two level-3 slots, 4573); restores on **Short or Long Rest** (4571); **Magical Cunning** (4587-4589) grants a 1-minute Short-Rest-equivalent slot recovery; **Mystic Arcanum** (table, e.g. 4546-4552) grants one fixed level-6 to level-9 spell/day with no slot at all | 4536-4593 |
| **Wizard** | Prepared *subset* of a larger known pool (the **spellbook**) | **Ritual Adept** (5121-5123): can ritual-cast any Ritual-tagged spell in the spellbook **without** having it prepared, if reading from the book | Intelligence | Arcane Focus or the spellbook itself | **Spellbook** (5101-5119): starts with 6 L1 spells, gains +2 spells of eligible level per level-up (research), can also copy spells found on scrolls (Copying a Scroll into a Spellbook, DC 10+level, 16280); **Arcane Recovery** (5125-5129): once per Long Rest, after a Short Rest recover slots totaling ≤ half Wizard level (round up), none level 6+ | 5093-5141 |

Cross-class rule: **Multiclass Spellcasting** (1348-1394) computes a combined
caster level (full casters count all levels; Paladin/Ranger count half,
rounded up) against the Multiclass Spellcaster slot table (1371-1394), but each
class's *prepared-spell count* and *cantrips known* are still calculated
per-class as if single-classed (1352). **Pact Magic** slots and normal
Spellcasting-feature slots are explicitly usable interchangeably across a
Warlock/other-caster multiclass (1369).

---

## 5. `spells.json` Field Audit

**Total spells:** 319. Data is sourced from the **2014 5e SRD API schema**
(every `url` value is `/api/2014/spells/...`), **not** the 2024 SRD 5.2.1 that
this document otherwise catalogues. Wording, exact save-or-half phrasing, and
a few renamed/restructured 2024 mechanics (e.g. explicit "Cantrip Upgrade"
labeling) will differ from the source text even where the underlying number is
the same. `classes` covers only the 8 core PHB casting classes — no Artificer
(consistent with a 2014-edition source, which never had it in the base SRD).

All "always applicable" descriptive fields (`index`, `name`, `desc`, `range`,
`components`, `ritual`, `duration`, `concentration`, `casting_time`, `level`,
`school`, `classes`, `subclasses`, `url`) are present on all 319/319 entries.
Mechanic-specific fields are present only where the mechanic applies to that
spell (expected — e.g. a spell with no damage has no `damage` object).

| Rule requirement | Present in spells.json? | Field name | Example value | Gap |
|---|---|---|---|---|
| Spell level | Yes (319/319) | `level` | `3` | None |
| School of magic | Yes (319/319) | `school` (object) | `{"index":"evocation","name":"Evocation",...}` | None |
| Class spell list membership | Yes (319/319) | `classes` (array) | `[{"name":"Wizard"},{"name":"Sorcerer"}]` | No Artificer; no explicit expansion for feature-granted cross-class spells (e.g. Paladin/Cleric cantrip borrowing) |
| Casting time | Yes (319/319) | `casting_time` | `"1 action"` | Free text (only ~9 distinct values, easy to parse) |
| Range | Yes (319/319) | `range` | `"150 feet"`, `"Touch"`, `"Self"`, `"Sight"` | Free text; numeric distance vs. keyword needs parsing |
| Components (V/S/M) | Yes (319/319) | `components` (array) | `["V","S","M"]` | None |
| Material component text/cost/consumption | Partial (184/319 have `material`) | `material` (string) | `"Gold dust worth at least 25gp, which the spell consumes."` | Cost (gp) and "consumed" flag are embedded in free text, not structured booleans/numbers — needs parsing |
| Duration | Yes (319/319) | `duration` | `"Instantaneous"`, `"Up to 10 minutes"` | Free text |
| Concentration flag | Yes (319/319) | `concentration` (bool) | `true` | None |
| Ritual flag | Yes (319/319) | `ritual` (bool) | `true` | None |
| Saving throw ability + success/fail effect | Partial (92/319 have `dc`) | `dc.dc_type`, `dc.dc_success` | `{"dc_type":{"name":"DEX"},"dc_success":"half"}` | `dc_success` enum is only `half`/`none`/`other`; "other" cases (e.g. Contagion) require reading `desc` prose for the actual effect — no structured field for non-damage save outcomes (conditions, etc.) |
| Attack roll (spell attack) flag | Partial (16/319 have `attack_type`) | `attack_type` | `"ranged"` / `"melee"` | 3 spells (Contagion, Plane Shift, Ray of Enfeeblement) have **both** `attack_type` and `dc` — engine must not assume mutual exclusivity |
| Damage dice / type | Partial (66/319 have `damage`) | `damage.damage_type`, `damage.damage_at_slot_level` | `{"damage_type":{"name":"Fire"},"damage_at_slot_level":{"3":"8d6",...}}` | Dice strings (`"8d6"`) are not pre-tokenized into count/die-size |
| Damage/healing scaling by upcast slot | Partial | `higher_level` (prose, 90/319) and `damage.damage_at_slot_level` / `heal_at_slot_level` (structured maps, 56/319 and 10/319 respectively) | see above | Non-damage upcast effects (extra targets, extra duration, etc.) exist **only** as unstructured `higher_level` prose — no structured field at all for those |
| Cantrip scaling by character level | Yes, where applicable (10/319) | `damage.damage_at_character_level` | `{"1":"1d10","5":"2d10","11":"3d10","17":"4d10"}` | Only present for damage-dealing cantrips, as expected |
| Area of effect shape/size | Partial (88/319) | `area_of_effect.type`, `area_of_effect.size` | `{"type":"sphere","size":20}` | `size` is a single integer; shapes needing two dimensions (Line = length **and** width, Cylinder = radius **and** height) are not captured — that second dimension is only in `desc` prose |
| Raw effect description prose | Yes (319/319) | `desc` (array of paragraphs) | multi-paragraph array | None |
| Metamagic (Sorcerer) | **Absent** | — | — | No representation at all; not a per-spell property in 5e anyway (it's a Sorcerer class feature), so this is expected, not a spells.json gap — flagging for the class-feature layer instead |
| Multiclass slot table / Pact Magic slot table | **Absent** (out of scope for a spell-level file) | — | — | Expected; these are class-progression tables, not spell fields |

**Non-rules-required fields present:** `index` (slug id), `url` (2014 API path,
unused by an engine), and nested `url` sub-fields inside `school` / `classes` /
`subclasses` / `damage_type` / `dc_type` objects. `subclasses` (subclass
spell-list tagging) is present but wasn't asked about above — arguably useful
for subclass-granted spell lists (e.g. domain spells) but not further audited
here.

**Structural notes:** no null/empty values found among the "always present"
fields — the data that exists is clean. The dominant gap is that **rules logic
for the less-common cases (non-damage saves, non-damage upcast effects, second
AoE dimensions, material cost/consumption) lives only in unstructured `desc` /
`higher_level` prose**, not in dedicated fields, and the file's source edition
(2014) is one edition behind the SRD text this catalogue is built from.

---

## 6. OCR / Extraction Garbling Flagged in the Source (do not guess around these)

- **7299**: spell header rendered as `## Acid SplASh` (mixed-case garbling of "Acid Splash").
- **7406-7409**: Animated Object stat block (embedded in *Animate Objects*) has a severely corrupted ability-score table — columns/rows run together (e.g. `S tr 16 +3 +3`, `i nt 3 -4 -4`).
- **7411**: stray `![Image](assets/image_0.png)` reference mid-spell.
- **7417, 7421**: spurious `## Actions` and `## Antilife Shell` — the former is really the Animated Object's stat-block subsection, not a spell; a naive `## ` spell-boundary parser would misfire here.
- **7527**: `## Components: V, S, M (a small square of silk) Duration: 24 hours` — mid-spell metadata line incorrectly promoted to an H2 header, splitting *Arcanist's Magic Aura* into two false entries.
- **7941**: same pattern — `## Components: V Duration: Instantaneous` mid-*Command*.
- **8891, 8893, 8897**: `## Traits`, `## Actions`, `## Bonus Actions` are the *Find Steed* mount's embedded stat-block subsections promoted to spell-level headers.
- **9207-9217**: *Giant Insect*'s embedded stat block table is garbled/misaligned (column headers "MOD SAVE" repeat oddly; ability rows compressed).
- **10455, 10464**: *Prismatic Spray*'s "Prismatic Rays" table is split into two spurious H2 headers (`## Prismatic Rays`, `## 1d8 Ray`) rather than one nested table.
- **10485-10487**: `## Prismatic Layers` immediately followed by a second spurious H2, `## Order Effects` (really a table-column header).
- **9991-10001, 10309-10315, 10371-10385, 10403-10417, 10429-10431** (*Major Image, Plane Shift, Power Word Kill, Prayer of Healing, Prestidigitation*): stat-block metadata fields (Casting Time/Range/Components/Duration) are fragmented across multiple lines instead of the usual single inline line — cosmetic but could break a line-pattern-based field extractor.
- **11276-11309**: *Summon Dragon*'s embedded "Draconic Spirit" stat block promotes `## Draconic Spirit`, `## Traits`, `## Actions` to spell-level headers; its ability-score row (~11296-11299) is also garbled/run-together.
- **11415**: `## Teleportation Outcome` — a table caption for *Teleport* promoted to an H2 header.
- General pattern to defend against in any downstream parser: **whenever a spell embeds a creature stat block (Animate Objects, Find Steed, Giant Insect, Summon Dragon), Docling promotes that stat block's internal subsections (Traits/Actions/Bonus Actions) and even inline metadata labels (Components:/Duration:) to the same `##` heading level as real spell names.** A safe extraction strategy is to validate `##` headers against a known spell-name list (or the Class Spell List tables at 1843, 2252, 2630, 3470, 3747, 4823, 5173, 4261-4262 for Sorcerer) rather than trusting heading level alone.
- Minor: hyphenation/line-wrap artifacts scattered throughout (e.g. *Shatter* 10880-10882 "car-\n\nried", *True Strike* 11587 "profi -ciency", *Raise Dead* ~10600 dash-to-hyphen mangling) — cosmetic prose damage, not structural, but could corrupt substring matches (e.g. searching for "carried" would miss "car- ried").
- Minor sequencing anomaly: *Ray of Sickness* (10632) appears after *Regenerate* (10624) rather than in strict A-Z order relative to *Reincarnate* (10642) — suggests page-order extraction rather than guaranteed alphabetical sort; don't assume strict alphabetical ordering when chunking by spell.

No garbling was found severe enough to obscure a rule *number* (DC, dice,
duration) in the passages actually cited in §1-§2 above; all numeric rules
quoted were read directly and cross-checked against surrounding prose.
