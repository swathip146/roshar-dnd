# Cosmere RPG — Core System Mechanics Catalogue

**Scope of this document**: the core resolution system, character statistics, defenses,
resource pools, combat, injuries/recovery, progression, and scene types of the
**Cosmere RPG** (Plotweaver™ Game System, Brotherwise Games / Dragonsteel
Entertainment, © 2025), as described in the Stormlight Starter Rules and two
GM/player quick-reference sheets. Surgebinding, Radiant paths, and setting-specific
content are **out of scope** — covered by a separate document
(`COSMERE_MECHANICS.md`, owned by another agent).

**CRITICAL FRAMING**: The Cosmere RPG is **not** a D&D 5e supplement. It is a
standalone game system (the "Plotweaver" system) that happens to also use a d20.
Verified by direct search of the source text: the Stormlight Starter Rules contain
**zero** occurrences of "Armor Class," "saving throw," "proficiency bonus," "spell
slot," or "hit dice." No 5e term, mechanic, or number below should be read as
carrying over from 5e — where the source is silent, this document says so rather
than inferring a 5e answer.

Sources (all page/line citations are to the parsed markdown, not the original PDF
page numbers):
- **SL015** = `parsed_data/sl015-stormlight-starterrules-digital/docling.md` (2,435 lines) — primary source
- **CS007** = `parsed_data/cs007-gmrules-overview/docling.md` (143 lines)
- **CS006** = `parsed_data/cs006-player-quick-reference/docling.md` (130 lines)

---

## 1. Dice and Resolution

| Mechanic | Source | Rule | Notes |
|---|---|---|---|
| Dice set | SL015:253-257 | Standard polyhedral set (d4, d6, d8, d10, d12, d20) plus one custom six-sided **plot die**. | "3d6" notation means roll that many and sum, or roll one that many times in sequence (SL015:284). |
| Skill test procedure | SL015:259-267 | 5 steps: (1) pick a skill, roll 1d20 (+ any additional dice); (2) add skill modifier; (3) add bonuses/penalties; (4) compare total to the test's DC — meet or exceed to succeed; (5) resolve results (success/failure + any Opportunity/Complication side effects). | The core resolution loop for the entire system. |
| Additional dice categories | SL015:273-284 | Three kinds of "additional dice" can be added to a d20 test at the same time as the d20: **Plot Die** (GM raises stakes), **Advantage/Disadvantage Die** (extra copy of a chosen die, keep best/worst), **Damage Die** (on an attack). | Rolled simultaneously with the d20, not sequentially, unless stated otherwise. |
| Plot die faces | SL015:286-296; CS006:31-34; CS007:13-24 | Six sides: 2 blank, 2 Opportunity (O), 2 Complication (C). | Custom die; symbols did not survive OCR as text — see OCR flags below. |
| d6 substitution for plot die | SL015:292 | If you don't own the custom die, use a normal d6. Diagram maps results; 1 and 2 are the "worst" results but grant a **Complication Bonus** to offset the Complication. | The actual 1-6 → face mapping is presented only as an image ("Plot Die diagram") and is **not readable as text** in the parsed source — see OCR flags. |
| Raising the Stakes | SL015:298-309; CS007:19 | GM has a player add the plot die alongside the d20 for an "important" test. Can only be raised once per test, and never after the d20 has already been rolled. GM guidance: raise stakes on ~1/3 of tests (CS007:19), for tests tied to the mission, the character's purpose/obstacle/goals, or high dramatic tension (SL015:302-306). | Players can request a raise but GM has final call (SL015:316-318). |
| Resolving a plot die roll | SL015:310-314 | Blank = no effect, resolve test normally. Opportunity or Complication symbol → see Opportunities/Complications rules. | |
| Opportunities — triggers | SL015:324, 364-368 | Gained from: rolling Opportunity on plot die, an ability granting it, or rolling a natural 20 on the d20 (Opportunity range, default 20-20). Multiple Opportunities possible on one test (e.g., plot die + natural 20). | |
| Spending an Opportunity | SL015:326-338; CS006:35-45; CS007 (implied) | Applies regardless of whether the test succeeds or fails. Player chooses one: **Aid an Ally** (next ally test gains advantage), **Collect Yourself** (recover 1 focus), **Critically Hit** (attack-tests only — converts hit to critical hit), **Influence the Narrative** (GM-approved positive narrative effect). | Some abilities grant *additional* ways to spend an Opportunity, usable only if that ability's own test rolled the Opportunity. |
| Complications — triggers | SL015:324, 366-368 | Gained from: rolling Complication on plot die, an ability granting it, or rolling a natural 1 on the d20 (Complication range, default 1-1). A natural-1 Complication does **not** grant a Complication Bonus (unlike a plot-die Complication). | |
| Facing a Complication | SL015:340-352; CS006:47-53 | Applies regardless of success/failure. **GM** chooses one: **Hinder an Ally** (next PC test gains disadvantage), **Become Distracted** (target loses 1 focus), **Influence the Narrative** (GM-chosen negative narrative effect). | |
| Complication Bonus | SL015:358-360 | Rolling a Complication on the plot die also grants a bonus to the current d20 roll, equal to the number shown inside the Complication symbol: **+2 or +4**. Complications from other sources state their own bonus (if any) — a natural-1 Complication grants none. | The exact mapping of which d6 face gives +2 vs +4 is only shown in the (unreadable) plot-die diagram. |
| Opportunity/Complication ranges | SL015:362-368 | Default Opportunity range = natural 20 only; default Complication range = natural 1 only. Ranges are explicitly a tunable stat (implying abilities can widen them), though the starter rules give no example of a widened range. | |
| Choosing who spends O/C | SL015:370-374 | Anyone at the table may suggest an effect; final choice belongs to whoever is spending it (player for Opportunity, GM for Complication). GM has final say on narrative-effect proposals. | |
| Action symbols | SL015:354-356 | Distinct symbols denote action types (e.g. action, free action, reaction) alongside the O/C symbols; detailed in Part 3 (combat). | Symbols render as blank/missing glyphs in the OCR text throughout — see OCR flags. |
| Advantage — mechanic | SL015:675-684; CS007:27-29 | For each advantage on a test, the **player** picks one die about to be rolled (d20, plot die, or any other die such as a damage die), rolls **two** of that die, and keeps the better result, discarding the other. Each die can be chosen only once per test — 2 advantages require 2 different dice. | |
| Disadvantage — mechanic | SL015:685-688 | Mirror of advantage: **GM** picks the die, rolls two, and the **GM** chooses which of the two results to keep (the worse one implied). | |
| Advantage + Disadvantage cancel | SL015:689-691 | If both apply, they cancel 1-for-1 (each disadvantage cancels one advantage). | |
| Advantage/disadvantage vs. multiple targets | SL015:693-695 | If an ability targets multiple targets with a single test but advantage/disadvantage applies to only some, roll the base test once, then separately roll the extra dice for advantage/disadvantage and apply only to the affected targets. | Full rule deferred to SHB ch. 10, "Attacks With Multiple Targets." |
| Enemy NPC tests with adv/disadv | SL015:697-699 | Roles reverse for NPC tests: GM picks die for NPC advantage; a player (usually the most affected) picks for NPC disadvantage. | |
| Difficulty Class (DC) | SL015:635-639, 651-659 | Meet or exceed DC = success. DC examples table: Easy 10, Medium 15, Hard 20, Very Hard 25, Nearly Impossible 30. | DC set by: an ability's stated value, GM discretion, a target's defense, or an opposed test. |
| DC via target defense | SL015:641-645 | Default: the DC for a test against another character equals their defense in the **same category** as the skill used (e.g., Intimidation, a cognitive skill? — actually see note). GM can silently adjust a defense-derived DC without informing the player. | Correction/clarity note: source text's own example uses Intimidation (a Willpower/cognitive skill per SL015:758) tested against a target's *Cognitive* defense — consistent with same-category default. |
| Opposed tests | SL015:661-669 | Both sides roll; DC is the other side's result. Higher roll wins; a tie means **neither** meets the DC — result favors the defender in an aggressive contest. | |
| Automatic success/failure | SL015:671-673 | Some effects grant an automatic success (or, rarely, automatic failure): no roll, and no Opportunities/Complications are generated. | |
| Working together (non-combat) | SL015:701-706 | Outside combat: the lead character makes one test, gaining **one advantage per helper**. In combat, helping requires the Aid reaction instead. | |
| Round Down convention | SL015:386 | Whenever a value must be divided, round down unless stated otherwise. | Global game convention, not test-specific. |
| Minimum of Zero convention | SL015:384 | A reduced value cannot go below 0 unless stated otherwise (health, damage, etc.). | Note: injury rolls are an explicit *exception* — they can go negative (SL015:1073). |
| GM Has Final Say / Specific Beats General | SL015:380-382 | Standard adjudication conventions: GM resolves disputes; a specific rule overrides a conflicting general rule. | |
| Stacking similar effects | SL015:382 | Similar effects generally stack unless they share the same name. Full rules deferred to SHB ch. 4, "Stacking Talents and Effects." | Deferral — see §9. |

---

## 2. Character Statistics

| Mechanic | Source | Rule | Notes |
|---|---|---|---|
| Three realms/categories | SL015:415-419; CS007:39-41 | All stats fall into **Physical** (Strength, Speed), **Cognitive** (Intellect, Willpower), or **Spiritual** (Awareness, Presence) — mirroring the cosmere's Physical/Cognitive/Spiritual Realms. Skills inherit the category of their governing attribute. | |
| Attributes | SL015:427-435; CS007:45-49 | Six attributes: Strength, Speed, Intellect, Willpower, Awareness, Presence. Each is a single number (no separate "score" vs. "modifier" — unlike "similar d20 systems," explicitly called out at CS007:49). Typical humans/singers ≤ 2; PCs range up to 5 at higher levels; some singer forms/Invested characters/massive beasts can exceed 5. | CS007:49 explicitly flags this as a deliberate deviation from systems with paired ability score + modifier. |
| Skill modifier formula | SL015:629-633; CS007:49 | Skill modifier = attribute score (for that skill's governing attribute) + skill ranks (0-5). Added directly to d20 rolls and to attack damage. | No separate proficiency-bonus-like scaling term exists. |
| Strength | SL015:437-439 | Physical power, toughness, athleticism, constitution. Governs Lifting Capacity and Carrying Capacity. | Exact lifting/carrying numeric formula is **not given** in the starter rules — deferred implicitly to SHB (no explicit deferral sentence, but no table/formula appears). |
| Lifting Capacity | SL015:441-443 | Max weight liftable in one attempt overhead; can't be sustained. | No formula/number given in this text — silent. |
| Carrying Capacity | SL015:445-457 | Comfortable carry weight while walking; can temporarily exceed up to Lifting Capacity but this Slows you. Exceeding it while moving = **Slowed** condition. Cumulative 60 minutes over capacity = **Exhausted [-1]**; this cumulative timer resets after a long rest. | No numeric carrying-capacity formula given — silent (contrast with Health/Focus, which do have explicit formulas). |
| Speed | SL015:459-471 | Quickness/dexterity/finesse. Governs Movement Rate. | |
| Movement Rate | SL015:463-471 | In combat: Move action lets you move up to your movement rate. Out of combat: ~3 actions per 10 seconds; running distance in 10 seconds = movement rate × 3. Default walking/ground movement unless stated otherwise. | Base numeric movement rate (e.g., "30 feet") is not stated in the core attribute text — appears only in worked examples (e.g., 25 ft. in a stat block, SL015:386 example uses 25 ft.). |
| Intellect | SL015:473-475 | Applied intelligence/wit; storing/recalling knowledge, deduction. | |
| Willpower | SL015:477-483 | Determination/mental fortitude/cognitive resilience. Governs the **Recovery Die**. | |
| Recovery Die | SL015:481-483; CS007:117 | Determined by Willpower; used when resting to recover Health and/or Focus. Exact Willpower→die-size mapping table is **not present** in the starter rules — silent (only "determined by a character's Willpower" is stated, CS007:117). | Genuine gap — implementer needs the missing table (likely in SHB). |
| Awareness | SL015:485-491 | Wisdom/connection to surroundings. Governs **Senses Range**. | |
| Senses Range | SL015:489-491, 597-611 | Determines how far you can sense things when your primary sense is obscured (e.g., highstorm noise, moonless "hateful hour" darkness). Within range = normal senses; outside range = can't detect unless targeting without senses (gains disadvantage per SL015:611). No sight-vs-other-senses distinction is modeled — GM/player decide primary sense. | Exact Awareness→feet mapping not given in this text (example stat block shows "Senses: 10 ft. (sight)" for a Tier-1 Minion with Awareness 2 — SL015:2309, but no general formula). |
| Presence | SL015:493-495 | Charisma/bearing; influencing others, building rapport. | |
| Skills — count and structure | SL015:617-631, 708-822 | 18 total skills, each tied to one attribute (Physical, Cognitive, or Spiritual by inheritance), each with 0-5 ranks. | Full list: Agility (Speed), Athletics (Strength), Crafting (Intellect), Deception (Presence), Deduction (Intellect), Discipline (Willpower), Heavy Weaponry (Strength), Insight (Awareness), Intimidation (Willpower), Leadership (Presence), Light Weaponry (Speed), Lore (Intellect), Medicine (Intellect), Perception (Awareness), Persuasion (Presence), Stealth (Speed), Survival (Awareness), Thievery (Speed). |
| Expertises | SL015:517-553; CS007:31-35 | Represent specialized *knowledge* (vs. skills = *doing*). Grant: automatic knowledge of basic facts (no test), otherwise-impossible "Advanced Thinking" tests, item Expert Traits, known languages (for cultural expertises), and GM-adjudicated creative uses. No direct numeric bonus to any roll. | Weapons/armor don't need proficiency to use, but an expertise unlocks that item's Expert Trait (CS007:35). |

---

## 3. Defenses

| Mechanic | Source | Rule | Notes |
|---|---|---|---|
| Three defenses | SL015:497-509; CS007:59-65 | **Physical defense** (Strength + Speed), **Cognitive defense** (Intellect + Willpower), **Spiritual defense** (Awareness + Presence). | CS007:61 explicitly states this replaces "a single 'Armor Class.'" |
| Defense formula | SL015:503-505; CS007:63-65 | `10 + both attributes in that category + any bonuses or penalties`. | Identical structural formula for all three defenses — only the attribute pair differs. |
| Defenses as DC | SL015:501-509, 641-645 | When Character A tests a skill against Character B, B's defense in the *same category* as A's skill sets the DC by default (e.g., Physical skill vs. Physical defense). GM/specific rules can redirect to a different category (example given: Feinting Strike talent attacks Cognitive defense instead of the default Physical). | |
| Defense DC adjustment | SL015:645-649 | GM may raise/lower the DC from the base defense value using the Difficulty Class Examples table as guidance, without necessarily telling the player. | |
| Deflect | SL015:511-515; CS007:105-107 | A value (usually from armor) that reduces **impact, keen, and energy** damage by that amount per hit. Example: deflect 2 vs. 5 energy damage → 2 deflected, 3 taken. Also reduces the severity of injury rolls (adds to the injury-roll d20, CS006:78). Does **not** reduce **spirit** or **vital** damage (SL015:1051, 1053). | Deflect is armor/ability-granted, not attribute-derived. |

---

## 4. Health, Focus, and Investiture

| Mechanic | Source | Rule | Notes |
|---|---|---|---|
| Three resource pools | SL015:555-557; CS007:51-57 | Health (physical), Focus (cognitive), Investiture (spiritual). All primarily attribute-derived, modifiable by talents/effects. | |
| Health — formula | SL015:561-563 | Max Health = `10 + Strength + any bonuses or penalties`. | |
| Health — depletion/restoration | SL015:565-570; SL015:1034-1038 | Depleted by damage. At 0 Health: suffer an injury, become **Unconscious**. Restored via resting (Recovery Die) or specific talents/effects (e.g., Medicine in combat). | |
| Focus — formula | SL015:573-575 | Max Focus = `2 + Willpower + any bonuses or penalties`. | |
| Focus — depletion/restoration | SL015:571-582; §"Conversations" | Spent to fuel talents/abilities and to resist social influence (2 or 4 focus per the persuasiveness of the argument, SL015:1722). Restored via resting (Recovery Die). | Heavily used as the resource economy for reactions (Aid, Dodge, Reactive Strike each cost 1 focus) and combat options (offhand Strike costs 2, graze costs 1/target). |
| Investiture — pool | SL015:583-589; CS007:57 | Gained only by choosing a Radiant path and bonding a spren (Roshar-specific: "ability to breathe in and hold Stormlight"). Functions "much like Focus does" once possessed. No base formula given for non-Radiant characters (they simply have no Investiture pool). | Full rules explicitly deferred: "See 'Investiture and Stormlight' in chapter 5 of the Stormlight Handbook" (SL015:589) — see §9. |
| Recovering Health/Focus (short rest) | SL015:882-885 | Roll Recovery Die once; split the result freely between current Health and current Focus. | |
| Recovering Health/Focus (long rest) | SL015:902-904 | Recover **all** lost Health and Focus; Exhausted penalty reduces by 1. | |
| Recover action (in-combat) | SL015:1316-1320; CS006:19; CS007:117 | 2-action combat action: roll Recovery Die as if finishing a short rest. Usable **once per scene**. | |

---

## 5. Combat

| Mechanic | Source | Rule | Notes |
|---|---|---|---|
| Round/turn structure | SL015:1144-1168; CS007:82-91 | Round-based. Each round, 4 phases in strict order: (1) Fast PC turns, (2) Fast NPC turns, (3) Slow PC turns, (4) Slow NPC turns. PCs and NPCs each independently choose fast or slow per round (can change round to round). | No traditional single initiative roll/order — order is determined structurally by phase, with same-phase ties broken by "highest Speed goes first, tie → highest d20" (SL015:1158). |
| Actions per turn | SL015:1150-1156, 1188-1192; CS007:86-91 | Fast turn = 2 actions. Slow turn = 3 actions. Actions not spent by end of turn are lost (no carryover). | Symbol/glyph for "action" renders blank in OCR — see flags. |
| Reactions per round | SL015:1174-1184; CS006:5 | Each character gets 1 reaction at the start of combat (unless Surprised) and a fresh one at the start of each of their own turns; lasts until used or until the start of their next turn. Usable on or off your turn. | |
| Boss double-turn | SL015:2261 | Boss-role NPCs can take **both** a fast turn and a slow turn each round (see §7 stat blocks). | |
| Surprise | SL015:1200-1206; CS006 (Conditions) | Determined at combat start (e.g., opposed Stealth vs. Perception, or Deception vs. Insight). Surprised characters: no starting reaction, can't take a fast turn, one fewer action, no reactions at all — until end of their first turn (condition removed after). | |
| Actions — full enumerated list | SL015:1218-1341; CS006:9-22 | **Actions** (1 unless noted): Brace, Disengage, Gain Advantage, Interact (can repeat), Move (can repeat), Strike (can repeat, different hand each time), Grapple (2), Ready (1 + cost of readied action), Recover (2, once/scene), Shove (2). **Free actions** (0 cost, one use per name per turn): Banter, Drop. | Table at SL015:1220-1230 lists all by name; costs render as blank glyphs in text (see OCR flags) but are cross-confirmed numerically in CS006. |
| Brace | SL015:1248-1255 | Take cover (within 5 ft); all attacks against you gain disadvantage while behind cover; ends if you attack or move. Weapons with the Defensive trait can serve as mobile cover. | |
| Disengage | SL015:1256-1258; CS006:12 | Move 5 feet without provoking Reactive Strike. | |
| Gain Advantage | SL015:1260-1262 | Test a skill vs. target's corresponding defense; success grants advantage on your *next* test against that target using a **different** skill. | |
| Interact | SL015:1264-1276 | Non-skill-test manipulation of an object/environment (open door, draw weapon, etc.); repeatable per turn. | |
| Move | SL015:1278-1282 | Move up to movement rate; crawling/climbing/swimming/stealth applies Slowed for that portion; repeatable per turn. | |
| Strike | SL015:1284-1288, 1400-1413 | Melee/ranged/unarmed attack vs. target's Physical defense (default). Repeatable per turn using a different hand each time; offhand Strike costs 2 focus (or 1 with the Offhand weapon trait). | |
| Grapple | SL015:1302-1306 | 2-action: Athletics test vs. target's Physical defense; success = target **Restrained** until grappler is Unconscious, chooses to end it, or target leaves reach. | |
| Ready | SL015:1308-1315 | Pre-declare a trigger + a chosen action/free action to fire in response before your next turn; cost = 1 (for Ready) + the readied action's own cost. Unused readied action is lost (no refund). | |
| Recover (action) | See §4. | | |
| Shove | SL015:1322-1324 | 2-action: Athletics vs. target's Physical defense; success = push/pull target 5 ft.; ends a Grapple on the shover if used against the grappler. | |
| Banter (free) | SL015:1332-1336 | Speak freely; GM may cap to "a couple sentences" per turn (10-sec round). Anything requiring a test must use Use a Skill instead. | |
| Drop (free) | SL015:1338-1340 | Release held object(s); to drop on someone else's turn requires Readying it. | |
| Use a Skill (action) | SL015:1294-1298 | Catch-all for skill-based battlefield tasks (Perception search, Stealth hide, Medicine treat, etc.). | |
| Reactions — full enumerated list | SL015:1342-1372; CS006:26-29 | **Aid**: spend 1 focus before an ally's test to grant advantage. **Avoid Danger**: Agility test vs. DC 15 (or vs. a triggering test's result) to escape environmental danger. **Dodge**: spend 1 focus when targeted by a (non-area, single-target) attack to impose disadvantage on it. **Reactive Strike**: spend 1 focus to melee/unarmed-attack an enemy who voluntarily leaves your reach (not usable vs. instantaneous/Transportation movement). | Only 1 reaction usable per round by default (barring effects that grant extra); multiple copies of the same-named reaction can be used on separate triggers. |
| Attack test procedure | SL015:1380-1413; CS007:93-103 | 3 steps: (1) choose target(s) — melee needs reach, ranged needs range + line of effect; (2) roll the attack skill test *and* damage dice simultaneously (damage dice not added to the test total); (3) resolve damage based on outcome. | |
| Miss | SL015:1410 | Test fails → 0 damage (unless converted to a graze). | |
| Grazing | SL015:1411, 1457; CS007:97-99; CS006:16 | On a miss, spend **1 focus per target** to instead deal damage equal to the **total rolled on the damage dice only** (no skill modifier added). | Genuinely novel partial-miss mechanic — no 5e analogue. |
| Hit | SL015:1412 | Test succeeds → damage = damage dice total **+ skill modifier** used for the attack. | |
| Critical hit | SL015:1413; CS007:101-103; CS006:43 | Spend an **Opportunity** (from the attack's own test — natural 20 always grants one, CS007:101) to convert a hit into a critical hit. Effect: **all** damage dice for that attack are treated as if they rolled their **highest possible value** (i.e., max damage), across all targets of the attack. | Explicitly requires a hit first ("when you hit... you can spend O"); a miss can't crit even with an Opportunity (only graze). |
| Damage types | SL015:1040-1053 | Five damage types: **Energy** (heat/electrical), **Impact** (crushing/bludgeoning), **Keen** (slicing/piercing), **Spirit** (dual physical+spiritual harm, e.g. Shardblades — NOT reduced by deflect), **Vital** (constitution-testing, e.g. poison/suffocation/cold — NOT reduced by deflect). | Deflect only mitigates Impact/Keen/Energy. |
| Weapon attacks | SL015:1421-1429, 1860-1971 | Weapon determines the skill tested and damage dice (Weapons tables in Part 6). Requires target in reach (melee) or range (ranged) and in line of effect. | |
| Melee vs. ranged | SL015:1431-1447 | Melee = target within reach (default 5 ft; some weapons extend it). Ranged = target within weapon's short/long range; short range rolls normally, long range imposes disadvantage. Ranged attack while an enemy is within your reach: disadvantage. Ranged attack near an ally (within 5 ft of them): raise the stakes — a resulting Complication risks the GM making the attack graze the ally. | |
| Unstable footing | SL015:1451-1453 | Swimming/flying/precarious footing imposes disadvantage on ranged attacks. | |
| Multi-target / area attacks | SL015:1455-1461 | Roll the attack test + damage once, compare vs. each target's defense individually; grazing multiple targets costs 1 focus **per target** grazed. | |
| Reach & Size | SL015:1501-1503, 1529-1547 | Reach = 5 ft (Medium) default, extendable by weapon traits. Character sizes: Small (2.5 ft), Medium (5 ft), Large (10 ft), Huge (15 ft), Gargantuan (20+ ft, GM discretion). | |
| Falling | SL015:1597-1601 | Falling ≥10 ft: 1d6 impact damage per 10 ft fallen; lands Prone if any fall damage taken. | |
| Terrain effects | SL015:1605-1627 | Cover (enables Brace at within-5-ft range), Difficult Terrain (Slowed while moving through), Dangerous Terrain (damage on entry/turn-start — example table: wooden spikes 1d4 keen, blazing fire 1d8 energy, highstorm winds 1d12 impact). | |
| Grid variant | SL015:1629-1667 | Optional: 1-inch = 5-ft squares; diagonal movement costs the same as orthogonal (5 ft); corner-blocking rules; line-of-effect via corner-to-corner sightline. | Explicitly a "variant," not the default theater-of-the-mind assumption. |
| Equipment traits | SL015:1953-1971 | Weapon traits: Cumbersome [X] (Strength requirement or disadvantage+Slowed), Dangerous (spend Complication to graze an ally), Deadly (spend Opportunity to force an injury), Defensive (Brace without cover), Discreet, Fragile (spend Complication to break it), Indirect, Loaded [X] (ammo count), Momentum (advantage if moved 10+ ft toward target this turn), Offhand (1 focus instead of 2), Pierce (ignores deflect), Quickdraw, Thrown [X/Y], Two-Handed, Unique. Armor traits: Cumbersome [X], Dangerous, Presentable, Unique. | |

---

## 6. Injuries and Recovery

| Mechanic | Source | Rule | Notes |
|---|---|---|---|
| Injury trigger | SL015:1059-1061, 1034-1038 | Suffered when reduced to 0 Health, when damaged again while at 0 Health, or by specific talents/weapon traits (e.g., Deadly trait) or GM fiat. | |
| Injury roll procedure | SL015:1063-1075; CS006:76-80 | **Not a skill test.** Roll 1d20 and apply: **+deflect value** of worn armor, **+any ability modifiers**, **−5 per existing injury** already held. Unlike normal tests, the result **can go negative**. | |
| Injury Duration table | SL015:1077-1085; CS006:82-88 | ≤ −6: **Death**. −5 to 0: **Permanent Injury**. 1-5: **Vicious Injury** (6d6 days). 6-15: **Shallow Injury** (1d6 days). 16+: **Flesh Wound** (until after a long rest / "remainder of the day" per CS006). | |
| Injury Effects table (d8) | SL015:1093-1102; CS006:90-99 | 1-2: Exhausted [-1]. 3: Exhausted [-2]. 4-5: Slowed. 6: Disoriented. 7: Surprised. 8: Can only use one hand. Player chooses freely or rolls d8. | |
| Minor NPC injuries | SL015:1104-1108 | A minor NPC suffering an injury is immediately defeated (PC choice: dead, or Unconscious+injury). Unlike PCs, defeated NPCs can't wake themselves — must be healed to ≥1 Health by another source. | |
| Recovering from injuries | SL015:1110-1114 | Temporary injuries heal after their stated duration, or **twice as fast** during downtime (deferred to SHB ch. 9). Permanent injuries never heal without supernatural intervention, but can be adapted to (training, fabrials, support). | |
| Death | SL015:1116-1134 | A dying character gets final words before their Cognitive aspect departs to Shadesmar, then the soul returns to the Spiritual Realm. Framed as generally permanent ("aside from a few exceptional cases"). | |
| Returning to life | SL015:1124-1126 | Rare (e.g., Old Magic); more-Invested souls linger longer after death; the soul must be willing to be reattached. | |
| Recovery Die (resting) | See §2/§4. | Willpower-derived die size; used for short rests, the Recover action, and long rests (which auto-max instead). | |
| Short rest | SL015:876-896 | ≥1 hour uninterrupted. Roll Recovery Die, split between current Health/Focus, OR forgo it for: Tend to Others (ally adds your Medicine modifier to their Recovery Die roll), Forage (Survival test per SL015:816), or Other (any test-requiring task, at the cost of not resting). | |
| Long rest | SL015:898-908 | ≥8 hours uninterrupted meaningful rest. Full Health/Focus recovery; Exhausted penalty −1. | |
| Medicine — combat healing | SL015:788-790 | 1+ rank in Medicine: spend 2 focus + Use a Skill for a DC 15 Medicine test to heal a conscious ally in reach (or self, with disadvantage) — success restores Health equal to Medicine ranks. | |
| Medicine — injury treatment (rest) | SL015:790 | During a long rest: DC 20 Medicine test (disadvantage if self-treating) reduces a shallow/vicious injury's duration by 1d4 days. Each character can only be treated this way once per long rest. | |

### Conditions (full enumeration)

| Condition | Source | Exact Effect |
|---|---|---|
| **Afflicted [X]** | SL015:938-944; CS006:103 | Take the specified damage amount/type at the end of each of your turns (combat) or every 10 seconds + after each removal attempt (out of combat). Multiple instances stack and resolve separately (only condition explicitly stackable by multiple sources). |
| **Determined** | SL015:946-948; CS006:105 | On failing a test, you may add an Opportunity to the result, then the condition is removed. |
| **Disoriented** | SL015:950-952; CS006:106 | Can't use reactions. Senses always count as obscured. Perception (and similar sense-based) tests gain disadvantage. |
| **Empowered** | SL015:954-956; CS006:108 | Granted when a Knight Radiant swears an Ideal. Advantage on **all** tests; Investiture refills to max at the start of each of your turns. Removed at end of the current scene. |
| **Enhanced [+X Attribute]** | SL015:958-968; CS006:110 | The named attribute gains +X. Does **not** change defenses, max Health, max Focus, or max Investiture. Cumulative — multiple attributes can be Enhanced simultaneously (only condition besides Exhausted/Afflicted explicitly called cumulative). |
| **Exhausted [-X]** | SL015:970-978, 451-453; CS006:112 | Apply a penalty of X to test results (after rolling, before resolving). Cumulative across instances (penalties add together). Reduces by 1 after each long rest; removed when penalty reaches 0. Final test result floor is still 0 (Minimum of Zero convention). |
| **Focused** | SL015:980-982; CS006:113 | Abilities that cost focus cost 1 less while this condition is active. |
| **Immobilized** | SL015:984-986; CS006:115 | Movement rate becomes 0; can't move or be moved by any effect. |
| **Prone** | SL015:988-994, 117 (CS006), 1557 | Lying flat: Slowed, melee attacks against you gain advantage. Can Brace without needing cover. Standing up is a free action (0-cost) that also costs 5 ft of movement and ends the condition (CS006 phrasing: spend 5 ft of movement to stand as a free action). Falling while climbing/flying causes Prone (and fall damage). |
| **Restrained** | SL015:996-998; CS006:118 | Movement rate 0. Disadvantage on all tests except those to escape. Escape method (if any) is set by whatever applied the condition; otherwise GM discretion. |
| **Slowed** | SL015:1000-1002; CS006:120 | Movement rate halved. If Slowed mid-movement, remaining movement is halved (rounded up — exception to the default round-down convention). |
| **Stunned** | SL015:1004-1006; CS006:122 | In combat: lose all reactions; on your turn, gain **two fewer actions** and no reaction. Out of combat: GM-adjudicated general sluggishness. |
| **Surprised** | SL015:1010-1012, 1200-1206; CS006:126 | Lose all reactions; no reaction at combat start or on your turn; can't take a fast turn; one fewer action. Removed after your next turn ends. |
| **Unconscious** | SL015:1014-1022; CS006:126 | Movement rate 0; can't move, communicate, or perceive surroundings. Falls Prone and drops everything held on gaining the condition. Can't act except the Radiant-only Breathe Stormlight action / Regenerate free action. Always takes a "slow" designation in combat but does nothing on your turn. PCs can choose to wake at the end of any of their turns or upon healing to ≥1 Health (regains 1 Health if waking from 0). NPCs auto-wake only upon recovering ≥1 Health (never voluntarily). |

**Condition-duration convention** (SL015:1024-1028): round-based conditions persist "until the beginning of [the phase they began in] on the next round"; conditions with an explicit end trigger (e.g., "end of your next turn") end exactly at that trigger regardless of fast/slow phase.

---

## 7. Progression

| Mechanic | Source | Rule | Notes |
|---|---|---|---|
| No traditional classes | CS007:125-129 | Instead of classes: 6 **heroic paths** (Agent, Envoy, Hunter, Leader, Scholar, Warrior) and 9 playable **Radiant paths** (grant Investiture + surges), each a talent tree. "Multipathing" lets characters combine paths. | Radiant-path detail is out of this document's scope (see COSMERE_MECHANICS.md). |
| Talents | SL015:2401-2409; CS007:125-129 | Gained by leveling up or entering a new tier; chosen from a path of the character's choice. | Full talent content is not in the starter rules (pregenerated characters only) — deferred to SHB. |
| Character Advancement table | SL015:2409-2434 | Full level 1-21+ progression table: attribute points, health gained, max skill rank, skill ranks gained, talents gained per level, organized into 5 tiers (tier boundaries at levels 3, 6, 9(→11 per table structure), etc. — see table). Level 1: 12 attribute points, 10+STR health, max skill rank 2, 4 skill ranks (+1 from starting path), 1 talent from starting path + ancestry bonus talent(s). | This is the one place in the starter rules with genuine crunch for character creation, even though the rules text says pregenerated characters only (SL015:398-402) — likely included for GM/advancement reference. |
| Goals and Rewards | SL015:920-926; CS007:119-123 | Two advancement axes: (1) **levels**, gained at GM-set milestones; (2) **personal goals**, each with a unique **reward** upon completion (a Shardblade, fabrial, patron, squire, noble title, Radiant spren bond, etc.). Rewards are personal to each PC's story, not shared party loot. | Full rules deferred: "chapter 8 of the Stormlight Handbook" (SL015:926). |
| Equipment/weapon Rewards example | CS007:123 | Weapon/armor traits like Momentum and Deadly are framed as examples of what a Reward might grant. | |
| Downtime | SL015:912-918; CS007:76 | Time between scenes for personal recuperation/progression outside shared party objectives. Full rules deferred: "Chapter 9 of the Stormlight Handbook" (SL015:918). Per CS007:76, downtime activities include personal pursuits, earning income, recuperating from injuries, and "respec through self-reflection." | "Respec" terminology is notable — implies formal, rules-supported attribute/talent reallocation, detail not given here. |

---

## 8. Scene Types

| Scene Type | Source | Distinct Mechanics |
|---|---|---|
| **Combat** | SL015:862, 1138-1669; CS007:69-115 | Structured rounds/phases (fast/slow turns), actions/reactions/free actions, attack tests, damage/grazing/critical hits, movement/positioning/terrain, targeting/range/line-of-effect. Typically 3-4 fast-paced rounds per CS007:71. The only scene type with hard turn/phase structure. |
| **Conversations** | SL015:1673-1750 | No fast/slow turns — "Flexible Rounds": characters contribute one at a time; a round ends once everyone who wants to has had a turn. **Contributions** map to 5 outcome types: Influence a Person (skill test vs. target's Spiritual/Cognitive defense), Help or Hinder Efforts (grants advantage/disadvantage), Bolster an Ally (restores focus), Gather Information (skill test vs. defense), Interject Flavor (no mechanical effect). Core resource: **Focus**, spent by the target of influence to resist (2 focus for a "reasonably persuasive" argument, 4 for an "extremely strong" one); reaching 0 focus makes an NPC unable to resist and prone to conceding. |
| **Endeavors** | SL015:1758-1816 | Also uses flexible, informal "rounds" (like Conversations). Four common sub-types per SHB: Discovery, Exploration, Mission, Pursuit (detail deferred to SHB ch. 12). Core mechanic: **Collective Threshold** — GM secretly tracks cumulative successes vs. failures toward a goal; reaching the success threshold = the party succeeds, too many failures first = the endeavor resolves unfavorably. Thresholds are explicitly "flexible," not a hard rule (GM can award double-credit for a spectacular success, or require more on GM judgment). |

Non-scene "flow of time": faster-flowing narrative outside these three scene types (travel montages, downtime) is handled purely narratively, with no dice mechanics (SL015:846-854).

---

## How This Differs From D&D 5e

**Bottom line up front: these are two structurally incompatible resolution systems.** The Cosmere RPG has no Armor Class, no saving throws, no proficiency bonus, no spell slots, no hit dice, no advantage/disadvantage-as-currently-implemented-in-5e (it works, but is *applied per-die* and can hit the plot die or damage dice, not just the d20), and a fundamentally different action economy (fast/slow turns with 2 or 3 generic actions, not 5e's action/bonus action/reaction/movement categories). A game engine built for 5e's action economy, AC-vs-attack-roll model, and spell-slot resource economy would need new state fields, a new resolution pipeline, and a new turn-order model — not a reskin.

| D&D 5e Concept | Cosmere RPG Equivalent | Source |
|---|---|---|
| Armor Class (AC) | **No single equivalent.** Split into three category-specific **Defenses** (Physical/Cognitive/Spiritual), each = `10 + both attributes in that category + bonuses`. Deflect (armor-derived) separately reduces damage post-hit rather than affecting to-hit. | SL015:497-509, 511-515; CS007:61-65 |
| Saving throw | **No equivalent.** No "saving throw" mechanic or terminology exists anywhere in the source. The closest functional analogues are: (a) a skill test vs. a defense (e.g., Avoid Danger reaction = Agility test vs. DC 15 or a triggering test's result), or (b) spending Focus to resist influence/mechanical effects in conversations. Neither is called a "save," neither uses a dedicated saving-throw proficiency, and both route through the same unified skill-test pipeline as everything else. | SL015:1358-1364 (Avoid Danger), 1726-1728 (Resisting Mechanical Effects) |
| Proficiency bonus | **No equivalent.** Confirmed absent from the text (CS007:49 explicitly notes attributes have no separate "score"/"modifier" split, unlike "similar d20 systems"). Skill modifier = attribute + skill ranks (0-5) directly, with no separate level-scaling bonus layered on top. Character-level progression instead grants attribute points, skill ranks, and talents per the Advancement table. | SL015:629-633; CS007:49; SL015:2409-2434 |
| Spell slots | **No equivalent in this document's scope.** Magic (Surgebinding) draws from the **Investiture** resource pool, which behaves "much like Focus" (a refillable pool, not a slot-consumption system) — but full Investiture/surge rules are explicitly out of scope here (see COSMERE_MECHANICS.md) and are largely deferred to SHB ch. 5-6 regardless. | SL015:583-589 |
| Hit dice | **No equivalent.** Health recovery uses the **Recovery Die** (size determined by Willpower — mapping table not present in this source) rolled during rests/Recover action, not a per-level pool of dice spent to self-heal. | SL015:481-483, 882-885, 1316-1320 |
| Conditions | **Partial overlap, different rule text.** 13 named conditions exist (Afflicted, Determined, Disoriented, Empowered, Enhanced, Exhausted, Focused, Immobilized, Prone, Restrained, Slowed, Stunned, Surprised, Unconscious). Several share names with 5e (Prone, Restrained, Stunned, Unconscious, Exhausted) but their mechanical text is bespoke to this action-economy (e.g., Stunned removes "two fewer actions" from a 2-or-3-action turn, not "no actions/reactions" against 5e's fixed action+bonus+reaction budget). Several conditions have **no** 5e analogue at all (Determined, Empowered, Enhanced, Focused). | §6 table above |
| Advantage / Disadvantage | **Named the same, mechanically different.** In 5e: roll 2d20, keep higher/lower, applies only to d20 rolls. In Cosmere RPG: for *each* advantage/disadvantage, choose **any one die** in the test (d20, plot die, *or* a damage die) and roll two of that specific die, keeping better/worse. Multiple advantages must target different dice. Also: for disadvantage, the **GM** chooses the die (not the player); for NPC tests the roles invert. | SL015:675-699; CS007:27-29 |
| Initiative | **No equivalent (no initiative roll at all).** Replaced by a structural **4-phase turn order**: Fast PCs → Fast NPCs → Slow PCs → Slow NPCs, chosen freely by each side each round (not rolled). Same-phase ordering ties break on highest Speed, then a d20 roll — but this is a tiebreaker within a phase, not a global initiative order. | SL015:1144-1168 |
| Actions / Bonus Actions / Reactions | **No equivalent structure.** 5e's fixed action+bonus-action+reaction budget is replaced by a **generic pool of 2 or 3 actions per turn** (fast vs. slow turn choice) that can be spent on any combination of the enumerated actions (each cost 0/1/2/*), plus free actions (0-cost, one use per name) and **1 reaction per round** (not per turn's action economy — persists off-turn until spent or replaced). There is no bonus-action category; some actions cost more "action points" than others (Grapple/Recover/Shove cost 2, Ready costs 1 + the readied action's cost). | SL015:1150-1156, 1188-1192, 1218-1341 |
| Damage types | **Different taxonomy entirely.** 5e has ~13 damage types (slashing, piercing, bludgeoning, fire, cold, etc.). Cosmere RPG collapses this to **5**: Energy, Impact, Keen, Spirit, Vital — organized around what mitigates them (Deflect reduces Energy/Impact/Keen; Spirit and Vital bypass Deflect entirely) rather than around narrative flavor. | SL015:1040-1053 |
| Resistance / Vulnerability | **No explicit resistance/vulnerability mechanic in the starter rules.** The closest analogue is **Deflect** (a flat damage reduction against 3 of the 5 damage types) and the generic statement that "some enemies might have special protections (or weaknesses) against certain damage types" (unquantified, GM/stat-block-driven, not a formal doubling/halving rule like 5e resistance/vulnerability). | SL015:1415-1419 |
| Character level / XP | **Levels exist, but no XP economy is described.** Levels are gained "at certain milestones... when indicated by the GM" (narrative/milestone-based, not point-accumulation). A parallel, separate "Goals and Rewards" advancement track exists alongside leveling. | SL015:920-926 |
| Classes | **No equivalent.** Replaced by 6 heroic "paths" + 9 Radiant paths as flexible talent trees, explicitly supporting "multipathing" (mixing paths on one character) rather than single-class or even 5e-style multiclassing with hard prerequisites. | CS007:125-129 |
| Skills / skill proficiency | **Similar shape, different math.** Both systems have a skill list tied to an ability/attribute. 5e: proficiency is binary (proficient or not) plus a flat proficiency bonus. Cosmere RPG: skill ranks are a 0-5 granular investment added directly to the attribute score, with no proficiency/non-proficiency binary at all. | SL015:629-633 |
| Critical hit (natural 20) | **Reworked into the Opportunity economy.** A natural 20 on an attack always grants an Opportunity, which the player may (not must) spend to convert a hit into a crit (max all damage dice). A natural 20 does not auto-crit by itself — it must be hit *and* the Opportunity must be spent that way, and it competes with all the other things an Opportunity could be spent on. | SL015:1413; CS007:101-103 |

---

## Mechanics With No 5e Analogue At All

These require building genuinely new subsystems, not adapting existing 5e engine code:

1. **The Plot Die** — a third roll-type (alongside d20 and damage dice) with narrative-mechanical dual purpose (bonus + story hook). No 5e equivalent exists; nothing in a 5e engine's dice-rolling pipeline anticipates a die whose faces are blank/Opportunity/Complication rather than numbers. (SL015:286-296)
2. **Opportunities and Complications** — a structured, GM/player-negotiated "spend this narrative currency for one of N effects" system layered onto *every* test, win or lose. This is unlike 5e's binary success/fail + occasional exploding-crit; it requires tracking a menu of spendable effects (Aid an Ally, Collect Yourself, Critically Hit, Influence the Narrative / Hinder an Ally, Become Distracted, Influence the Narrative) and letting players/GM choose among them at resolution time. (SL015:320-374)
3. **Complication Bonus** — the paradoxical rule that a *negative* outcome (Complication) can simultaneously *help* the roll numerically (+2/+4 to the d20). No 5e concept combines a debuff-trigger with an immediate roll buff this way. (SL015:358-360)
4. **Grazing** — a "partial miss" resolution state that lets a failed attack still deal (unmodified) damage for a focus cost. 5e attacks are binary hit/miss; there is no partial-credit damage state in 5e's core rules. (SL015:1410-1411)
5. **Deflect** — flat, damage-type-gated post-hit mitigation (reduces Impact/Keen/Energy only, ignores Spirit/Vital) that is wholly separate from the to-hit roll. Superficially resembles 5e "resistance" but is a flat subtraction tied to gear rather than a halving rule tied to a damage-type list per creature. (SL015:511-515)
6. **Focus as a universal social/action/reaction currency** — one resource pool simultaneously fuels reactions (Aid, Dodge, Reactive Strike), combat options (offhand Strike, grazing), and social resistance (2/4 focus to resist persuasion) — collapsing 5e's separate "spell slots / reaction / concentration / no-social-resource" model into a single meter. (SL015:571-582, 1701-1748)
7. **Expertises** — a knowledge-flag system distinct from skills, granting automatic fact-recall, otherwise-impossible tests, item-specific "expert traits," and languages — with **no numeric bonus** to any roll. 5e's closest concept (tool proficiencies, languages) is fragmented across several unrelated subsystems rather than unified like this. (SL015:517-553)
8. **Injury Rolls** — a distinct, non-test d20 roll (can go negative!) triggered specifically by hitting 0 Health or certain crits, producing a duration-graded outcome (Death / Permanent / Vicious / Shallow / Flesh Wound) plus a randomly/manually chosen mechanical-condition effect. This entirely replaces 5e's death-saving-throw + exhaustion-from-massive-damage rules with a single unified roll. (SL015:1063-1108)
9. **Fast/Slow turn choice with phase-based turn order** — replacing initiative with a per-round tactical choice (go now for fewer actions, or go later for more) that also determines global turn order (all fast turns globally precede all slow turns). No 5e equivalent; this is a distinct action-economy/tempo trade-off baked into turn order itself. (SL015:1144-1168)
10. **Collective Thresholds (Endeavors)** — a hidden GM-tracked success/failure counter used to pace an entire multi-character skill-based scene (chases, investigations, infiltrations) toward a binary outcome, distinct from 5e's ad hoc skill-challenge homebrew (5e's core rules have no formal skill-challenge subsystem at all). (SL015:1786-1804)

---

## Explicit Deferrals to the Full Stormlight Handbook (SHB)

The starter rules repeatedly and explicitly punt detail to the full book. Every such deferral found in the sources:

> "See 'Stacking Talents and Effects' in chapter 4 of the Stormlight Handbook for the full rules on which effects stack in this game." — SL015:382

> "See 'Investiture and Stormlight' in chapter 5 of the Stormlight Handbook for more information on Investiture." — SL015:589

> "Crafting Complex Items... you need to have a corresponding expertise to make a Crafting test. The 'Crafting' section in chapter 7 of the Stormlight Handbook presents the full rules of crafting." — SL015:732

> "Chapter 9 of the Stormlight Handbook offers the full rules for downtime and downtime activities." — SL015:918

> "Full rules for goals and rewards appear in chapter 8 of the Stormlight Handbook." — SL015:926

> "Chapter 7 of the Stormlight Handbook presents rules for making attacks using weapons in your main hand and offhand." (Wielding Multiple Weapons) — SL015:1427

> "For more information, see 'Attacks With Multiple Targets' in chapter 10 of the Stormlight Handbook." — SL015:695

> "The four most common types of endeavor are Discovery, Exploration, Mission, and Pursuit, as described in chapter 12 of the Stormlight Handbook." — SL015:1762

> "Refer to chapter 12 of the Stormlight Handbook for more guidance on setting thresholds." — SL015:1804

> "For more weapons, see chapter 7 of the Stormlight Handbook." — SL015:1862

> "Temporary injuries heal after the specified duration—or if you recuperate during downtime, you heal twice as fast, as described in chapter 9 of the Stormlight Handbook." — SL015:1112

> "Consult chapter 13 of the Stormlight Handbook for a wealth of more advanced GMing techniques." — SL015:2223

> "If you want the flexibility of the full surge rules from the Stormlight Handbook, feel free to use them!" (re: adversary surge skills) — SL015:2353

> "This condensed rulebook does not contain rules for creating or advancing characters... For the full character creation experience, pick up the Stormlight Handbook." — SL015:398-402

> "When you're ready to advance your character, see the Stormlight Handbook for guidance on taking your character on to new adventures." — SL015:2405-2407

> CS007 (GM Rules Overview) repeatedly cites specific SHB page numbers for expansion: "SHB pages 8-9" (Opportunities/Complications, CS007:25), "SHB page 58" (advantage/disadvantage, CS007:29), "SHB page 54" (Health/Focus/Investiture, CS007:53), "SHB page 289" (three scene types, CS007:69), "SHB page 296" (Injuries, CS007:113), "SHB page 301" (Combat Turn Order, CS007:84).

**Net effect**: the starter rules are deliberately a subset. Numeric gaps confirmed genuinely absent from this source (not just deferred by name) include: the Willpower→Recovery-Die-size table, the Strength→Lifting/Carrying-capacity formula, the Awareness→Senses-Range formula, base Movement Rate by Speed score, and the full plot-die-diagram (1-6 → face) mapping.

---

## OCR / Garbling Flags

This is a Docling PDF-to-markdown conversion. The following passages are flagged as degraded, missing, or unreliable — treat them as **unverified** rather than guessing at the intended content:

1. **All action/reaction/free-action cost glyphs are missing throughout SL015 and CS006.** The source uses pictographic symbols for "1 action," "2 actions," "free action," and "reaction" (e.g., "○ Interact," "◇ Move") that did not survive OCR as text. Line SL015:1220-1230 (`Actions and Reactions` table) shows a `Type | Cost | Type | Cost` table where the **Cost column is entirely blank** for every row — the actual pip-counts had to be cross-inferred from body-text sentences elsewhere (e.g., "you must use 2 for the Ready action itself," SL015:1314) and confirmed against CS006's cleaner enumeration (which renders costs as literal digits: "1 Brace," "2 Grapple," CS006:11-22). **Confidence: high for the numbers reconstructed in §5/§6 of this document (cross-checked against CS006), but the original glyph shapes/iconography are unrecoverable from this text.**
2. **The plot die's Opportunity (O) and Complication (C) symbols are inconsistently rendered.** SL015 mostly shows blank glyphs where the symbol should be (e.g., "roll an [blank] or [blank] symbol," SL015:314); CS006 and CS007 more reliably substitute the literal letters "O" and "C" in parentheses (e.g., "Opportunity ( O )", CS006:37). This document uses "O"/"C" per the more legible CS006/CS007 convention, but the *original* plot-die iconography (whatever glyph or icon is printed on the actual die face) is not recoverable from any of the three sources.
3. **The Plot Die diagram (d6 substitution mapping) is entirely a lost image.** SL015:292-296 references "the Plot Die diagram" and captions it "Plot Die LINDA LITHÉN" (an illustrator credit) followed by an `![Image]` placeholder — the actual 1-6 → {blank, blank, Opportunity, Opportunity, Complication, Complication} face mapping, and specifically **which face(s) grant the +2 vs. +4 Complication Bonus**, exists only as an uncaptured image. This is a hard gap, not an inference opportunity.
4. **Sample stat block table (Spear Infantry, SL015:2299-2325) has garbled column alignment.** The markdown table renders "Physical / Cognitive / Spiritual" column headers duplicated oddly across cells, and skill lists are truncated/duplicated mid-cell (e.g., "Heavy Weaponry Weaponry +3," "Perception+4" concatenated oddly with "Cognitive Skills: Discipline / +2, Intimidation / +3"). The prose numbers (str 2, def 14, Health 14 (11-17), etc.) appear internally consistent and are usable, but the raw table structure should not be trusted for automated parsing without manual cleanup.
5. **Some body-text symbols for reach/melee/ranged icons are silently dropped**, e.g. SL015:1913 "a Melee [+5] weapon" reads fine, but inline references like "As ▷" (SL015:810, a free-action glyph rendered as a stray "▷" character) suggest the free-action glyph sometimes survives as an unrelated Unicode arrow rather than being dropped entirely — meaning some symbol substitutions are silently *wrong* rather than merely missing. Treat any standalone "▷" in the source as "presumably a free-action or similar glyph," not a meaningful arrow.
6. **Table of Contents page numbers (SL015:107-156) are original-PDF page numbers, not markdown line numbers** — do not confuse the "Part 3: Combat . . . 30" style entries with this document's SL015:line citations.

None of these gaps affect the *numeric* rules content already captured in the tables above (damage dice, DCs, action costs, condition effects) — those are corroborated across at least two of the three sources or by clean surrounding prose. The gaps are concentrated in: (a) iconography/glyphs with no numeric content, and (b) the one specific plot-die-diagram mapping noted in flag 3.
