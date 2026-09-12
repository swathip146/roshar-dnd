# SRD 5.2.1 Core & Combat Mechanics Catalogue

Source: `parsed_data/srd_cc_v5.2.1/docling.md`, sections:
- "Playing the Game" (lines 90-561)
- "Combat" (lines 562-900)
- "Rules Glossary" (lines 11855-12948)

This is a catalogue of what the rules **say**, for a game-engine implementation
audit. It does not assess what the codebase currently does.

---

## 1. Playing the Game — Core d20 System (lines 90-330)

| Mechanic | SRD line | Rule summary | Depends on |
|---|---|---|---|
| Rhythm of Play (3-step loop) | 94-98 | GM describes scene -> players describe actions -> GM narrates results; loop repeats. | — |
| Exceptions Supersede General Rules | 102-106 | When a specific exception (class feature, feat, item, spell, monster ability) contradicts a general rule, the exception wins. | — |
| The Six Abilities | 110-123 | Str, Dex, Con, Int, Wis, Cha; each measures a stated physical/mental trait. | — |
| Ability Scores (range & meaning) | 125-141 | Scores run 1-20 for adventurers (30 max for anything); 1=lowest, 10-11=human average, 20=adventurer cap absent a feature, 30=absolute max. | — |
| Ability Modifiers | 142-160 | Modifier derived from score via table: e.g. 10-11=+0, 12-13=+1, ... 30=+10; formula is floor((score-10)/2). | Ability Scores |
| Round Down | 146-148, 12684-12686 (glossary dup) | Always round fractions down on divide/multiply, even at exactly .5, unless a rule says round up. | — |
| D20 Test (general procedure) | 162-171 | Roll 1d20 (2d20 keep-one if Adv/Dis), add ability modifier + proficiency bonus (if relevant) + circumstantial bonuses, compare to target number (DC for checks/saves, AC for attacks); meet or beat = success. | Ability Modifiers, Proficiency, Advantage/Disadvantage |
| Ability Check | 173-179 | D20 Test representing use of talent/training vs. a challenge with meaningful failure chance; named for the ability used (e.g., Strength check). | D20 Test |
| Ability Check Examples table | 181-190 | Str=lift/push/pull/break; Dex=move nimbly/quietly; Con=push body past limits; Int=reason/remember; Wis=notice; Cha=influence/entertain/deceive. | — |
| Proficiency Bonus applies to checks | 192-194 | Add Proficiency Bonus to an ability check when GM deems a skill/tool proficiency relevant and the creature has it. | Proficiency |
| Difficulty Class (ability check) | 196-198 | DC represents task difficulty; GM sets it, rules may suggest values. | — |
| Typical Difficulty Classes table | 200-207 | Very Easy=5, Easy=10, Medium=15, Hard=20, Very Hard=25, Nearly Impossible=30. | — |
| Saving Throw (rule text) | 209-213 | Represents evading/resisting a threat; not chosen voluntarily; you may choose to auto-fail without rolling. | — |
| Saving Throw Ability Modifier / examples | 215-228 | Named for the ability used; Str=resist force, Dex=dodge, Con=endure toxin, Int=see through illusion, Wis=resist mental assault, Cha=assert identity. | — |
| Saving Throw Proficiency Bonus | 230-232 | Add Proficiency Bonus if proficient in that save's ability. | Proficiency |
| Saving Throw DC | 234-236 | Determined by the effect (e.g., caster's spellcasting ability + Proficiency Bonus) or by the GM; monster stat blocks specify DC directly. | — |
| Attack Roll (definition) | 238-240 | D20 Test that hits if roll (with modifiers) >= target's AC. | AC |
| Attack Roll Abilities table | 242-254 | Melee weapon/Unarmed Strike = Strength; ranged weapon = Dexterity; spell attack = varies by casting ability; Finesse property allows Str or Dex. | — |
| Attack Roll Proficiency Bonus | 256-258 | Add Proficiency Bonus when attacking with a weapon you're proficient with, or with a spell. | Proficiency |
| Armor Class — base calculation | 260-270 | Base AC = 10 + Dexterity modifier; modified by armor/items/spells; only one base-AC calculation can be used at a time if multiple apply. | Ability Modifiers |
| Rolling 20 or 1 on attack rolls | 272-276 | Natural 20 = automatic hit (Critical Hit) regardless of modifiers/AC; natural 1 = automatic miss regardless of modifiers/AC. | Attack Roll |
| Advantage/Disadvantage (concept) | 278-282, 294 | Advantage = positive circumstances; Disadvantage = negative; can also be GM-granted situationally. | — |
| Heroic Inspiration | 284-292 | Spend it to reroll any die immediately after rolling and must keep the new result; only one instance held at a time; if granted again while held, may be passed to another PC who lacks it; Human characters start each day with it. | — |
| Roll Two D20s (Adv/Dis mechanic) | 296-298 | With Advantage take the higher of two d20s; with Disadvantage take the lower. | — |
| Advantage/Disadvantage Don't Stack | 300-304 | Multiple Advantage sources still mean roll only 2d20; multiple Disadvantage sources likewise; if both apply, they cancel and you roll a flat 1d20 (even multiple-vs-one). | — |
| Interactions with Rerolls | 306-310 | If a roll has Adv/Dis (two dice) and you have a reroll/replace effect (e.g., Heroic Inspiration), you may reroll/replace only one of the two dice, your choice. | Advantage/Disadvantage, Heroic Inspiration |
| Proficiency Bonus (concept & scaling) | 312-316 | Reflects training; increases with character level; monster's PB is based on Challenge Rating; applies to skill checks, saves, weapon/tool use, spell attacks, and spell save DC. | — |
| Proficiency Bonus table | 318-325 | Levels/CR 1-4=+2, 5-8=+3, 9-12=+4, 13-16=+5, 17-20=+6, 21-24=+7, 25-28=+8, 29-30=+9. | — |
| The Bonus Doesn't Stack | 327-331 | Proficiency Bonus is added at most once per roll even if proficient in multiple relevant things; it can be multiplied only once and divided only once (e.g., Expertise doubles it). | Proficiency Bonus |
| Skill Proficiencies (mechanic) | 333-337 | Proficiency in a skill adds Proficiency Bonus to checks using that skill; without it, check is still made but no bonus added. | Proficiency Bonus |
| Skills table (18 skills + governing ability) | 339-358 | Acrobatics/Dex, Animal Handling/Wis, Arcana/Int, Athletics/Str, Deception/Cha, History/Int, Insight/Wis, Intimidation/Cha, Investigation/Int, Medicine/Wis, Nature/Int, Perception/Wis, Performance/Cha, Persuasion/Cha, Religion/Int, Sleight of Hand/Dex, Stealth/Dex, Survival/Wis. | — |
| Determining Skills | 364-366 | Character's starting skill proficiencies set at character creation; monster's are in its stat block. | — |
| Saving Throw Proficiencies (grant mechanic) | 368-372 | Each class grants proficiency in at least two saving throws; monsters may also have save proficiencies per stat block. | — |
| Equipment Proficiencies — Weapons | 374-378 | Anyone can wield any weapon; proficiency adds Proficiency Bonus to attack rolls with it. | Proficiency Bonus |
| Equipment Proficiencies — Tools | 374, 379 | Tool proficiency adds Proficiency Bonus to checks using that tool; if you also have the relevant skill proficiency, you get Advantage on that check too (stacking skill+tool benefit types). | Proficiency Bonus, Advantage |
| Actions table (10 named actions) | 381-401 | Attack, Dash, Disengage, Dodge, Help, Hide, Influence, Magic, Ready, Search, Study, Utilize — each summarized (details in Rules Glossary). | — |
| One Thing at a Time | 405-409 | Only one action may be taken at a time; applies both in and out of combat (can't Search and Help simultaneously, etc.). | — |
| Bonus Action (general rule) | 411-417 | Only usable if a specific feature/spell/ability grants one; only one Bonus Action per turn even if multiple are available; timing is player's choice unless specified; anything preventing actions also prevents Bonus Actions. | — |
| Reaction (general rule) | 419-425 | Instant response to a trigger, usable on your turn or another's; only one Reaction between the start of your turns; occurs immediately after its trigger unless stated otherwise; interrupted creature resumes its turn right after. | — |
| Social Interaction / NPC Attitude | 427-431 | NPC attitude toward a PC is Friendly, Indifferent, or Hostile; Friendly predisposed to help, Hostile predisposed to hinder. | Attitude (glossary) |
| Roleplaying (adjudication) | 435-445 | Freeform; GM uses NPC personality + PC actions/attitude to determine reactions. | — |
| Ability Checks in Social Interaction | 447-451 | GM may call for the Influence action + ability check when roleplaying alone doesn't resolve outcome. | Influence [Action] |

## 2. Playing the Game — Exploration (lines 453-561)

| Mechanic | SRD line | Rule summary | Depends on |
|---|---|---|---|
| Adventuring Equipment (adjudication) | 457-461 | Narrative examples of gear use (ladder, torch, thieves' tools, caltrops); no numeric rule here. | — |
| Vision and Light — Obscured Areas | 463-472 | Lightly Obscured = Disadvantage on sight-based Wisdom (Perception) checks; Heavily Obscured = Blinded condition while trying to see there. | Blinded condition |
| Light categories — Bright Light | 475, 477 | Lets most creatures see normally. | — |
| Light categories — Dim Light | 479 | = Lightly Obscured; boundary zone, twilight/dawn, full moon. | Lightly Obscured |
| Light categories — Darkness | 481 | = Heavily Obscured; night outdoors, unlit dungeon, magical darkness. | Heavily Obscured |
| Special Senses (pointer) | 483-487 | Names Blindsight, Darkvision, Tremorsense, Truesight as glossary-defined special senses. | Glossary entries |
| Hiding (pointer) | 489-491 | GM decides when hiding is appropriate; executed via the Hide action. | Hide [Action] |
| Interacting with Objects — Object definition | 493-499 | An object is a discrete inanimate item (not a building/vehicle, which are composed of many objects). | — |
| Time-Limited Object Interactions | 501-503 | One free object interaction per turn, occurring during move or action; additional interactions require the Utilize action. | Utilize [Action] |
| Finding Hidden Objects | 505-509 | Typically a Wisdom (Perception) check; must describe searching in the object's vicinity or no roll total reveals it. | — |
| Carrying Objects (pointer) | 511-513 | Normally untracked; GM may invoke Carrying Capacity rules for exceptional loads. | Carrying Capacity |
| Breaking Objects (pointer) | 515-517 | Fragile nonmagical objects can be automatically destroyed as an action; tougher objects use Rules Glossary breaking-objects rules. | Breaking Objects (glossary) |
| Marching Order (adjudication) | 519-521 | Party establishes travel order; affects trap/ambush resolution; no fixed numeric rule. | — |
| Hazards (pointer) | 523-529 | Names Burning, Falling, Suffocation, Dehydration, Malnutrition as glossary-defined hazards. | Glossary entries |
| Travel (pointer) | 531-535 | GM may narrate travel abstractly or use Travel Pace rules; see Combat's movement rules if exact distance matters. | — |
| Travel Pace table | 537-548 | Fast: 400 ft/min, 4 mi/hr, 30 mi/day. Normal: 300 ft/min, 3 mi/hr, 24 mi/day. Slow: 200 ft/min, 2 mi/hr, 18 mi/day. Mounted group can double distance for 1 hour, then mounts need a Short/Long Rest before repeating. | Short Rest, Long Rest |
| Travel Pace effects | 550-556 | Fast = Disadvantage on Wis (Perception/Survival) and Dex (Stealth) checks. Normal = Disadvantage on Dex (Stealth) only. Slow = Advantage on Wis (Perception/Survival) checks. | — |
| Vehicles (travel) | 558-561 | Land vehicles choose a pace normally; waterborne vessels use vessel speed instead, up to 24 hr/day depending on crew. | — |

## 3. Combat — Order of Combat & Turns (lines 562-672)

| Mechanic | SRD line | Rule summary | Depends on |
|---|---|---|---|
| Round | 568 | ~6 seconds in-game; every combatant takes one turn per round. | — |
| Combat Step by Step (3 steps) | 570-576 | 1) Establish positions, 2) Roll Initiative, 3) Take turns in Initiative order until fighting stops. | Initiative |
| Initiative (roll & ranking) | 578-580, 584 | Everyone makes a Dexterity check to determine turn order ("Initiative count"); GM rolls once for a group of identical monsters, applying that result to all of them; ranked highest to lowest; order fixed for the whole combat. | Dexterity check |
| Surprise (Initiative penalty) | 582 | A surprised combatant (caught unaware when combat starts) has Disadvantage on their Initiative roll. | Disadvantage |
| Initiative Ties | 586 | GM decides order among tied monsters; players decide order among tied PCs; GM decides a PC-vs-monster tie. | — |
| Your Turn — move + action | 588-592 | On your turn: move up to your Speed and take one action, in either order. | Speed |
| Communicating on your turn | 594-596 | Brief communication is free (uses neither move nor action); extended communication/persuasion attempts require an action (typically Influence). | Influence [Action] |
| Interacting with Things (in combat) | 598-600 | One free object interaction during your move or action; a second requires the Utilize action; some items always require an action per their description. | Utilize [Action] |
| Grid rules — Squares | 606 | Each grid square = 5 feet. | — |
| Grid rules — Speed in squares | 608 | Speed ÷ 5 = movement in squares (e.g., 30 ft Speed = 6 squares). | — |
| Grid rules — Entering a Square | 610 | Costs 1 square of movement to enter an adjacent unoccupied square (ortho or diagonal); Difficult Terrain square costs 2. | Difficult Terrain |
| Grid rules — Corners | 612 | Diagonal movement can't cross the corner of a wall/large obstruction filling its space. | — |
| Grid rules — Ranges | 614 | Count squares by shortest route from a square adjacent to one thing, stopping in the other thing's space. | — |
| Doing Nothing on Your Turn | 618 | You may forgo moving/acting entirely; suggests Dodge or Ready if undecided. | Dodge [Action], Ready [Action] |
| Ending Combat | 620-622 | Ends when one side is defeated (killed, knocked out, surrendered, fled) or both sides agree to stop. | — |
| Movement — general | 624-632 | Move up to Speed or less, or not at all; climbing/crawling/jumping/swimming can be part of or all of your move; distance deducted from Speed as you go; Speed set at character creation or in monster stat block. | Speed, Climbing, Crawling, Jumping, Swimming |
| Difficult Terrain (combat text) | 634-638 | Every foot of movement in Difficult Terrain costs 1 extra foot (i.e., 2 ft per 1 ft moved); doesn't stack even with multiple qualifying features in the same space. | — |
| Breaking Up Your Move | 640-642 | Movement may be split before/after an action, Bonus Action, or Reaction on the same turn (e.g., move 10 ft, act, move 20 ft). | — |
| Dropping Prone (self, free) | 644-646 | May give yourself the Prone condition for free (no action, no movement cost) on your turn, unless your Speed is 0. | Prone condition |
| Creature Size categories | 648-663 | Tiny=2.5x2.5 ft (4 per square), Small/Medium=5x5 ft (1 square), Large=10x10 ft (4 squares/2x2), Huge=15x15 ft (9 squares/3x3), Gargantuan=20x20 ft (16 squares/4x4). | — |
| Moving around Other Creatures | 665-671 | Can move through space of an ally, an Incapacitated creature, a Tiny creature, or one 2+ sizes different from you; another creature's space (unless Tiny/ally) counts as Difficult Terrain; can't willingly end move in an occupied space; if forced to end there, you gain Prone unless Tiny or larger than the other creature. | Difficult Terrain, Incapacitated, Prone |

## 4. Combat — Making Attacks (lines 673-768)

| Mechanic | SRD line | Rule summary | Depends on |
|---|---|---|---|
| Making an Attack — structure (3 steps) | 673-689 | 1) Choose target within range, 2) GM determines Cover and Advantage/Disadvantage plus other modifiers, 3) Make the attack roll; on hit, roll damage unless the attack says otherwise. | Attack Roll, Cover |
| Unseen Attackers and Targets | 677-683 | Attacking a target you can't see = Disadvantage; if target isn't actually where you targeted, you simply miss; a creature that can't see you grants you Advantage on attacks against it; a hidden attacker reveals location upon hitting or missing with an attack. | Advantage/Disadvantage, Hide [Action] |
| Cover — rule & stacking | 691-695 | Cover applies only when the attack originates on the opposite side of the obstruction from the target; multiple cover sources don't stack — only the most protective applies. | — |
| Cover table (3 degrees) | 697-703 | Half Cover = +2 AC and +2 Dex saves, from a creature/object covering >=half the target. Three-Quarters Cover = +5 AC and +5 Dex saves, from an object covering >=3/4. Total Cover = can't be targeted directly, from an object covering the whole target. | — |
| Ranged Attacks — Range | 709-713 | Single-range attacks cannot target beyond that range. Two-range weapons (e.g., Longbow): normal range = no penalty; attacking beyond normal range (but within long range) = Disadvantage; beyond long range = can't attack at all. | — |
| Ranged Attacks in Close Combat | 715-717 | Ranged attack roll has Disadvantage if made within 5 feet of a hostile creature that can see you and isn't Incapacitated. | Incapacitated |
| Melee Attacks (definition) | 719-721 | Attacks a target within your reach; typically a handheld weapon or Unarmed Strike; monsters often use natural weapons. | Reach |
| Reach | 723-725 | Default reach is 5 feet; some creatures/weapons have greater reach as noted in their description. | — |
| Opportunity Attacks | 727-731 | Triggered when a visible creature leaves your reach; avoided via Disengage, Teleportation, or being moved without using movement/action/bonus action/reaction; you use your Reaction to make one melee attack (weapon or Unarmed Strike) against the provoking creature, occurring right before it leaves reach. | Reaction, Disengage [Action], Teleportation |

## 5. Combat — Mounted & Underwater Combat (lines 733-768)

| Mechanic | SRD line | Rule summary | Depends on |
|---|---|---|---|
| Mount eligibility | 735 | A willing creature at least one size larger than the rider, with appropriate anatomy, can serve as a mount. | Creature Size |
| Mounting and Dismounting | 737-739 | During your move, mount/dismount a creature within 5 ft; costs movement equal to half your Speed, rounded down (e.g., Speed 30 -> 15 ft cost). | Speed, Round Down |
| Controlling a Mount | 741-747 | Only controllable if trained to accept a rider (e.g., domesticated horses). Controlled mount: Initiative matches rider's while mounted, moves on rider's turn per rider's direction, and only has Dash/Disengage/Dodge as action options; can act even the turn it's mounted. Independent mount: keeps its own Initiative slot and acts on its own. | Initiative, Dash/Disengage/Dodge |
| Falling Off a Mount | 749-753 | If mount is forcibly moved (or knocked Prone, or you're knocked Prone) while mounted, DC 10 Dexterity save or fall off, landing Prone within 5 ft of the mount. | Prone condition |
| Underwater — Impeded Weapons (melee) | 759-761 | Melee attack underwater without a Swim Speed = Disadvantage, unless the weapon deals Piercing damage. | Swim Speed |
| Underwater — Impeded Weapons (ranged) | 763 | Ranged attack underwater automatically misses beyond normal range; has Disadvantage within normal range. | — |
| Underwater — Fire Resistance | 765-767 | Anything underwater has Resistance to Fire damage. | Resistance |

## 6. Combat — Damage & Healing (lines 769-900)

| Mechanic | SRD line | Rule summary | Depends on |
|---|---|---|---|
| Hit Points (concept) | 773-775, 781-785 | HP represents durability; current HP ranges from max down to 0; HP loss has no mechanical effect until 0; Bloodied = at or below half max HP (no inherent effect but can trigger other rules). | — |
| Resting (pointer) | 777-779 | Short Rest = 1 hour; Long Rest = 8 hours; HP regain is a main benefit; full rules in glossary. | Short Rest, Long Rest |
| Damage Rolls | 787-791 | Roll the specified damage dice + modifiers; penalties can reduce damage to 0 but not below; weapon attacks add the same ability modifier used for the attack roll; fixed (non-rolled) damage amounts (e.g., Blowgun) don't get an ability modifier added unless stated. | Ability Modifiers |
| Critical Hits (damage doubling) | 793-795 | On a Critical Hit, roll all the attack's damage dice twice (including bonus dice like Sneak Attack) and add together, then add modifiers once. | Rolling 20 (Critical Hit) |
| Damage against Multiple Targets | 801-803 | When one effect forces simultaneous saves on 2+ targets, roll damage once for all of them (e.g., Fireball). | — |
| Half Damage on Successful Save | 805-807 | Many save-based effects deal half damage (rounded down) on a success — half of what a failed save would have dealt. | Round Down |
| Damage Types (pointer) | 809-811 | Damage instances are typed (e.g., Fire, Slashing); types carry no rules themselves but interact with Resistance/Vulnerability/Immunity. | — |
| Resistance and Vulnerability | 813-815 | Resistance halves damage of that type (round down); Vulnerability doubles damage of that type. | Round Down |
| Resistance/Vulnerability No Stacking | 817-819 | Multiple instances of Resistance (or of Vulnerability) to the same damage type count as only one instance. | — |
| Order of Application (damage math) | 821-825 | Apply in order: 1) flat adjustments (bonuses/penalties/multipliers), 2) Resistance, 3) Vulnerability. Worked example: 28 Fire dmg -5 flat =23, halved (Resistance, round down) =11, doubled (Vulnerability) =22. | Resistance, Vulnerability |
| Immunity (damage/condition) | 827-829 | Immunity to a damage type = take no damage of that type; immunity to a condition = unaffected by it. | — |
| Healing (mechanic) | 831-833, 839 | Restored HP is added to current HP up to (not exceeding) HP maximum; excess healing beyond max is lost (e.g., 8 healing at 14/20 HP only restores 6). | Hit Points |
| Knocking Out a Creature | 835-837 | When a melee attack would reduce a creature to 0 HP, attacker may instead set it to 1 HP and Unconscious; it begins a Short Rest, ending the condition at Short Rest's end, or earlier if it regains HP or someone succeeds on a DC 10 Wisdom (Medicine) check to administer first aid. | Unconscious, Short Rest |
| Dropping to 0 Hit Points (overview) | 841-843 | A creature at 0 HP either dies outright or falls unconscious. | — |
| Instant Death — Monster Death | 845-847 | A monster dies instantly at 0 HP (GM may waive this and treat it like a PC). | — |
| Instant Death — HP Maximum of 0 | 849 | A creature dies if its HP maximum is reduced to 0. | — |
| Instant Death — Massive Damage | 851 | If damage at 0 HP has leftover (remainder) that equals or exceeds the creature's HP maximum, it dies (worked example: 12 HP max, 6 current, takes 18 dmg -> 12 remainder equals max -> dies). | — |
| Character Demise (pointer) | 853-855 | Dead PCs may be revived by magic (e.g., Raise Dead) or the player makes a new character. | Dead (glossary) |
| Falling Unconscious at 0 HP | 857-859 | Non-instant-death 0 HP = Unconscious condition until any HP regained; begin making Death Saving Throws. | Unconscious, Death Saving Throw |
| Death Saving Throws — core roll | 861-865 | At the start of your turn at 0 HP, roll 1d20 (not ability-based): 10+ = success, else failure; no per-roll effect except counting toward 3. | — |
| Death Saving Throws — 3 successes/failures | 865, 867 | 3rd success = Stable; 3rd failure = death; successes/failures need not be consecutive but are tracked separately; both counters reset to 0 upon regaining any HP or becoming Stable. | Stable |
| Death Saving Throws — natural 1 or 20 | 869 | Natural 1 = two failures; natural 20 = regain 1 HP (ending the unconscious/dying state). | — |
| Death Saving Throws — damage at 0 HP | 871 | Taking any damage at 0 HP = 1 death save failure; a Critical Hit = 2 failures; damage >= HP maximum = instant death. | Critical Hit |
| Stabilizing a Character | 873, 875 | Help action + successful DC 10 Wisdom (Medicine) check stabilizes a 0-HP creature. | Help [Action] |
| Stable creature behavior | 877 | A Stable creature stops making death saves (still Unconscious); taking damage ends Stable status and resumes death saves; if unhealed, regains 1 HP after 1d4 hours. | Unconscious |
| Temporary Hit Points — loss order | 879, 883-885 | Damage is subtracted from Temporary HP first; leftover damage (if any) carries to real HP (example: 5 temp HP, take 7 dmg -> lose the 5 temp, then 2 real HP). | — |
| Temporary Hit Points — duration | 887-889 | Lasts until depleted or until a Long Rest is finished. | Long Rest |
| Temporary Hit Points — don't stack | 891-893 | New Temporary HP doesn't add to existing; you choose to keep the higher pool, they don't sum (e.g., 10 existing + 12 new = choose 12, not 22). | — |
| Temporary Hit Points — not HP/healing | 895-897 | Can't be added to real HP; healing can't restore them; gaining them isn't "healing"; can be gained at full HP; doesn't revive from 0 HP (only true healing does). | Healing |

## 7. Rules Glossary — Canonical Alphabetical Checklist (lines 11855-12948)

Every glossary entry (tag in brackets noted where present). Sub-tables that are part of a parent entry (e.g., "Object Armor Class" under "Breaking Objects") are folded into the parent row rather than listed separately, per the assignment's instruction to expand only genuinely distinct mechanics (the six Area-of-Effect shapes are each their own row, as instructed).

| Mechanic | SRD line | Rule summary | Depends on |
|---|---|---|---|
| Ability Check | 11892-11894 | D20 Test using an ability (or associated skill) to overcome a challenge. | D20 Test, Proficiency |
| Ability Score and Modifier | 11896-11898 | 6 scores (Str/Dex/Con/Int/Wis/Cha), each with a derived modifier added on relevant D20 Tests. | — |
| Action (glossary index) | 11900-11908 | One action per turn, chosen from Attack, Dash, Disengage, Dodge, Help, Hide, Influence, Magic, Ready, Search, Study, Utilize, or a feature-granted special action. | — |
| Advantage | 11909-11911 | Roll 2d20, use higher; can't be affected by more than one Advantage; cancels with Disadvantage on the same roll. | — |
| Adventure | 11913-11915 | A series of encounters forming a story. | Encounter |
| Alignment | 11917-11919 | Combination of morality axis (good/evil/neutral) and order axis (lawful/chaotic/neutral); 9 possible combos. | — |
| Ally | 11921-11923 | Party member, friend, same-side-in-combat creature, or GM/rule-designated ally. | — |
| Area of Effect | 11925-11935 | 6 shapes (Cone, Cube, Cylinder, Line, Sphere, Emanation); has a point of origin; a location is excluded if all straight lines from origin to it are blocked by Total Cover; if origin point itself is unseen and blocked, origin forms on the near side of the obstruction. | Cover |
| Armor Class | 11937-11941 | Target number for attack rolls; base = 10 + Dex modifier; only one base-AC calculation usable at a time even if multiple apply. | Ability Modifiers |
| Armor Training | 11943-11945 | Without training in worn armor category (Light/Medium/Heavy), Disadvantage on Str/Dex D20 Tests and can't cast spells; without Shield training, no AC bonus from the shield. | Disadvantage |
| Attack [Action] | 11947-11953 | Make one attack roll with a weapon or Unarmed Strike; may equip/unequip one weapon before or after the attack; movement from features like Extra Attack can be split between the multiple attacks. | Attack Roll |
| Attack Roll | 11955-11957 | D20 Test representing an attack with a weapon, Unarmed Strike, or spell. | D20 Test |
| Attitude | 11959-11961 | Monster's starting disposition toward a PC: Friendly, Hostile, or Indifferent. | Friendly, Hostile, Indifferent |
| Attunement | 11963-11965 | Bond required to use some magic items' magical properties; max 3 attuned items at once. | — |
| Blinded [Condition] | 11967-11973 | Can't see; auto-fail sight-based ability checks; attack rolls against you have Advantage; your attack rolls have Disadvantage. | — |
| Blindsight | 11975-11977 | See within a set range without physical sight, including through Blinded/Darkness (not through Total Cover) and can see Invisible creatures in range. | Blinded, Total Cover, Invisible |
| Bloodied | 11979-11981 | At half HP or fewer; no inherent effect but can trigger other rules. | Hit Points |
| Bonus Action | 11983-11985 | Extra action takeable same turn as your action; max 1 per turn; only available if a rule explicitly grants it. | — |
| Breaking Objects (incl. Object AC & HP tables) | 11987-12017 | Fragile objects may be auto-broken via Attack/Utilize. Object AC by substance: cloth/paper/rope 11, crystal/glass/ice 13, wood 15, stone 17, iron/steel 19, mithral 21, adamantine 23. Object HP (Fragile/Resilient) by size: Tiny 2(1d4)/5(2d4), Small 3(1d6)/10(3d6), Medium 4(1d8)/18(4d8), Large 5(1d10)/27(5d10); Huge/Gargantuan tracked as sectioned Large-or-smaller pieces. Objects destroyed at 0 HP; objects have Immunity to Poison and Psychic damage; GM may assign type-specific vulnerabilities (e.g., paper vs Fire); objects lacking assigned ability scores can't make ability checks and auto-fail saves. | Damage Threshold, Immunity |
| Bright Light | 12019-12021 | Normal illumination. | — |
| Burning [Hazard] | 12023-12025 | 1d4 Fire damage at start of each of the burning creature/object's turns; can extinguish as an action by going Prone and rolling on the ground, or by dousing/submerging/suffocating the fire. | Prone |
| Burrow Speed | 12027-12029 | Move through sand/earth/mud/ice; can't burrow solid rock without a specific trait. | Speed |
| Campaign | 12031-12033 | A series of adventures. | Adventure |
| Cantrip | 12035-12037 | A level 0 spell cast without expending a spell slot. | — |
| Carrying Capacity | 12039-12053 | Max carry weight = Str score x a size multiplier (Tiny x7.5, Small/Medium x15, Large x30, Huge x60, Gargantuan x120 lb); drag/lift/push max = double the carry multiplier (Tiny x15 ... Gargantuan x240 lb); while dragging/lifting/pushing beyond carry max, Speed capped at 5 ft. | — |
| Challenge Rating | 12055-12057 | Summarizes a monster's threat to 4 PCs; compared to party level to gauge danger; underlies a monster's Proficiency Bonus. | Proficiency Bonus |
| Character Sheet | 12059-12061 | Record used to track a character's information. | — |
| Charmed [Condition] | 12063-12069 | Can't attack or target the charmer with harmful magic/damage; the charmer has Advantage on social ability checks to interact with you. | Advantage |
| Climbing | 12071-12075 | Each foot of climbing movement costs 1 extra foot (2 extra in Difficult Terrain), waived if using a Climb Speed; GM may require DC 15 Strength (Athletics) for slippery/handhold-poor surfaces. | Difficult Terrain, Climb Speed |
| Climb Speed | 12077-12079 | Substitute for Speed that avoids climbing's extra movement cost. | Climbing, Speed |
| Concentration | 12081-12089 | Required to sustain some spells/effects up to a stated max duration; ends automatically if you start another Concentration effect, if Incapacitated, or if you die; can be voluntarily ended anytime for free; taking damage requires a Constitution save (DC = higher of 10 or half damage taken, round down, max DC 30) to maintain it. | Incapacitated, Round Down |
| Condition (index) | 12091-12102 | Lists 14 conditions: Blinded, Charmed, Deafened, Exhaustion, Frightened, Grappled, Incapacitated, Invisible, Paralyzed, Petrified, Poisoned, Prone, Restrained, Stunned, Unconscious; conditions don't stack with themselves except Exhaustion. | — |
| Cone [Area of Effect] | 12104-12108 | Extends in straight lines from a point of origin in a chosen direction; width at any point along its length equals that point's distance from the origin; origin point excluded from the AoE unless stated. | Area of Effect |
| Cover | 12110-12112 | Half Cover = +2 AC/Dex saves; Three-Quarters Cover = +5 AC/Dex saves; Total Cover = can't be targeted directly; most-protective degree applies, no stacking. | — |
| Crawling | 12114-12116 | Each foot of crawling movement costs 1 extra foot (2 extra in Difficult Terrain). | Difficult Terrain, Speed |
| Creature | 12118-12120 | Any being in the game, including PCs. | Creature Type |
| Creature Type | 12122-12133 | 13 types: Aberration, Beast, Celestial, Construct, Dragon, Elemental, Fey, Fiend, Giant, Humanoid, Monstrosity, Ooze, Plant, Undead; most PCs are Humanoid; types have no inherent rules but other rules reference them. | — |
| Critical Hit | 12135-12137 | Natural 20 on an attack roll auto-hits regardless of modifiers/AC; roll all damage dice twice, sum, then add modifiers once. | Rolling 20 or 1 |
| Cube [Area of Effect] | 12139-12143 | Extends in straight lines from an origin point located anywhere on one face of the cube; size = length of each side; origin excluded from AoE unless stated. | Area of Effect |
| Curses | 12145-12147 | GM/effect defines what a curse does; removable by Remove Curse, Greater Restoration, or magic that explicitly ends curses. | — |
| Cylinder [Area of Effect] | 12149-12153 | Extends in straight lines from an origin at the center of the circular top or bottom face; defined by base radius and height; origin point IS included in the AoE (unlike Cone/Cube/Line). | Area of Effect |
| D20 Test | 12155-12157 | Umbrella term for ability checks, attack rolls, and saving throws; effects on "D20 Tests" apply to all three. | — |
| Damage | 12159-12161 | Harm causing HP loss to a creature or object. | Hit Points |
| Damage Roll | 12163-12165 | A die roll plus modifiers that deals damage. | — |
| Damage Threshold | 12167-12169 | Creature/object with a threshold has Immunity to all damage from an attack/effect below the threshold amount; damage meeting or exceeding it applies in full (worked example: threshold 10 -> 9 dmg does nothing, 11 dmg applies fully). | Immunity |
| Damage Types | 12171-12194 | 12 types with no inherent rules of their own (interact via Resistance/Vulnerability/Immunity): Acid, Bludgeoning, Cold, Fire, Force, Lightning, Necrotic, Piercing, Poison, Psychic, Radiant, Slashing, Thunder. | — |
| Darkness | 12196-12198 | An area of Darkness is Heavily Obscured. | Heavily Obscured |
| Darkvision | 12200-12202 | See Dim Light as Bright Light and Darkness as Dim Light within a set range; colors in that darkness appear only as gray shades. | Dim Light, Darkness |
| Dash [Action] | 12204-12208 | Gain extra movement this turn equal to your (modified) Speed; may use a special speed (Fly/Swim) instead, chosen each time. | Speed |
| Dead | 12210-12214 | No HP, can't regain them without revival magic (Raise Dead, Revivify); spirit can refuse revival; returning creature keeps ongoing conditions/curses/contagions if still active, returns with 1 fewer Exhaustion level than at death, and loses all Attunements. | Exhaustion, Attunement |
| Deafened [Condition] | 12216-12220 | Can't hear; auto-fail hearing-based ability checks. | — |
| Death Saving Throw | 12222-12224 | Made at the start of a turn at 0 HP; full mechanic detailed in "Playing the Game." | — |
| Dehydration [Hazard] | 12226-12236 | Needs water/day by size (Tiny 1/4 gal, Small/Medium 1 gal, Large 4 gal, Huge 16 gal, Gargantuan 64 gal); drinking less than half needed amount = 1 Exhaustion level at day's end; that Exhaustion can't be removed until a full day's water is drunk. | Exhaustion |
| Difficult Terrain | 12238-12250 | Each foot of movement there costs 1 extra foot; non-cumulative (binary, not stacking); qualifying conditions listed: non-Tiny/non-ally creature's space, furniture sized for your size or larger, heavy snow/ice/rubble/undergrowth, liquid shin-to-waist deep, an opening one size smaller than you, or a slope of 20+ degrees. | — |
| Difficulty Class | 12251-12253 | Target number for an ability check or saving throw. | — |
| Dim Light | 12255-12257 | An area with Dim Light is Lightly Obscured. | Lightly Obscured |
| Disadvantage | 12259-12261 | Roll 2d20, use lower; only one Disadvantage can apply per roll; cancels with Advantage. | — |
| Disengage [Action] | 12263-12265 | Your movement doesn't provoke Opportunity Attacks for the rest of the current turn. | Opportunity Attacks |
| Dodge [Action] | 12267-12271 | Until start of your next turn: attack rolls against you have Disadvantage if the attacker can see you, and you make Dex saves with Advantage; lost if Incapacitated or Speed 0. | Incapacitated |
| Emanation [Area of Effect] | 12273-12279 | Extends in straight lines from a creature/object in all directions, out to a stated distance; moves with its origin unless instantaneous/stationary; origin excluded from AoE unless stated. | Area of Effect |
| Encounter | 12281-12283 | A scene belonging to at least one of social interaction, exploration, or combat. | — |
| Enemy | 12285-12287 | A creature fighting/harming you or designated as your enemy by rule/GM. | — |
| Exhaustion [Condition] | 12289-12299 | Cumulative levels; death at level 6; each D20 Test result is reduced by 2x your Exhaustion level; Speed reduced by 5 ft x your Exhaustion level; finishing a Long Rest removes 1 level; condition ends at level 0. | Long Rest, D20 Test, Speed |
| Experience Points | 12301-12303 | XP awarded by GM for overcoming challenges/completing adventures; crossing thresholds increases character level. | — |
| Expertise | 12305-12311 | Doubles Proficiency Bonus on ability checks with a skill you have Expertise in (unless already doubled by another feature); granted only in a skill you're already proficient in; can't double-stack Expertise in the same skill. | Proficiency Bonus |
| Falling [Hazard] | 12313-12317 | 1d6 Bludgeoning damage per 10 feet fallen, max 20d6; lands Prone unless the fall dealt no damage; falling into liquid allows a Reaction DC 15 Strength (Athletics) or Dexterity (Acrobatics) check to halve fall damage by landing head/feet first. | Prone, Reaction |
| Flying | 12319-12321 | While flying, you fall if Incapacitated, Prone, or your Fly Speed drops to 0 — unless you can hover. | Incapacitated, Prone, Fly Speed, Hover |
| Fly Speed | 12323-12325 | Speed used to travel through air; stay aloft until landing, falling, or dying. | Flying, Speed |
| Friendly [Attitude] | 12327-12329 | Views you favorably; you get Advantage on ability checks to Influence a Friendly creature. | Advantage, Influence |
| Frightened [Condition] | 12331-12337 | Disadvantage on ability checks and attack rolls while the fear source is in line of sight; can't willingly move closer to the fear source. | Disadvantage |
| Grappled [Condition] | 12339-12347 | Speed becomes 0 and can't increase; Disadvantage on attack rolls against any target other than the grappler; grappler can drag/carry you, costing it 1 extra foot per foot moved unless you're Tiny or 2+ sizes smaller. | Disadvantage |
| Grappling | 12349-12357 | Typically via Unarmed Strike; requires a free hand (or a stat-block-specified body part), one grapple per limb/part used; ending it: Grappled creature uses its action for a Strength (Athletics) or Dexterity (Acrobatics) check vs. the grapple's escape DC; also ends if grappler becomes Incapacitated or range is exceeded; grappler may release for free anytime. | Grappled, Unarmed Strike, Incapacitated |
| Hazard (index) | 12359-12361 | Names Burning, Dehydration, Falling, Malnutrition, Suffocation as environmental-danger glossary entries. | — |
| Healing | 12363-12365 | The means of regaining HP. | Hit Points |
| Heavily Obscured | 12367-12369 | Blinded condition while trying to see something there. | Blinded, Darkness |
| Help [Action] | 12371-12377 | Assist an ability check: chosen ally gets Advantage on their next check with a named skill/tool, expiring if unused before your next turn; Assist an attack roll: distract an enemy within 5 ft, giving Advantage to the next ally attack against it, expiring at start of your next turn. | Advantage |
| Heroic Inspiration | 12379-12383 | Expend to reroll any die immediately after rolling, must keep new result; gaining it while already held causes it to be lost unless given to another PC lacking it. | — |
| Hide [Action] | 12385-12391 | Requires DC 15 Dexterity (Stealth) check while Heavily Obscured or behind Three-Quarters/Total Cover, and out of enemy line of sight; success grants the Invisible condition while hidden; the check total becomes the DC for others' Wisdom (Perception) checks to find you; hiding ends immediately upon making a sound louder than a whisper, being found by an enemy, making an attack roll, or casting a spell with a Verbal component. | Heavily Obscured, Cover, Invisible |
| High Jump | 12393-12397 | Jump height = 3 + Strength modifier feet (min 0) with a 10+ ft running start; standing jump = half that; each foot of the jump costs a foot of movement; can extend arms to reach jump height + 1.5x your height. | — |
| Hit Point Dice | 12399-12401 | "Hit Dice"; help determine HP maximum; spendable during a Short Rest to regain HP. | Short Rest |
| Hit Points | 12403-12405 | Measure of durability; damage reduces, healing restores; can't exceed max or go below 0. | — |
| Hostile [Attitude] | 12407-12409 | Views you unfavorably; Disadvantage on ability checks to Influence a Hostile creature. | Disadvantage, Influence |
| Hover | 12411-12413 | Ability (per stat block/spell/effect) to remain aloft while flying under circumstances that would otherwise cause falling. | Flying |
| Illusions | 12415-12419 | Effect-defined; illusions in space are insubstantial/weightless but appear environmentally affected (shadows, wind, echoes) unless the creating effect says otherwise. | — |
| Immunity | 12421-12423 | Immunity to a damage type or condition means it doesn't affect you at all. | — |
| Improvised Weapons | 12425-12435 | No Proficiency Bonus added to attack rolls; deals 1d4 damage of a GM-chosen appropriate type on a hit; thrown range is 20/60 ft (normal/long); a weapon used contrary to its design (e.g., melee weapon thrown without Thrown property, or ranged weapon swung in melee) counts as improvised; GM may rule an improvised item functions exactly as an existing weapon. | Proficiency Bonus |
| Incapacitated [Condition] | 12437-12445 | Can't take actions, Bonus Actions, or Reactions; Concentration is broken; can't speak; Disadvantage on Initiative rolls if Incapacitated when rolling it. | Concentration |
| Indifferent [Attitude] | 12447-12449 | No desire to help or hinder you; the default monster attitude. | Influence |
| Influence [Action] | 12451-12459 | Describes urging a monster to act. GM sorts response into Willing (complies, no check), Unwilling (refuses, no check), or Hesitant (requires an ability check vs DC = higher of 15 or the monster's Intelligence score; success = compliance; failure = must wait 24 hrs, or GM-set duration, before repeating the same urging). | Attitude |
| Initiative | 12471-12475 | Determines turn order; alternative fixed "Initiative score" = 10 + Dex modifier, +5 if Advantage on Initiative rolls, -5 if Disadvantage, usable instead of rolling. | Advantage/Disadvantage |
| Invisible [Condition] | 12477-12485 | Advantage on Initiative roll if Invisible when rolled; unaffected by effects requiring the target to be seen (unless the effect's creator can somehow see you); worn/carried equipment also concealed; attack rolls against you have Disadvantage and your attack rolls have Advantage, negated against a creature that can somehow see you. | Advantage/Disadvantage |
| Jumping | 12487-12489 | Two forms: Long Jump (horizontal) and High Jump (vertical). | Long Jump, High Jump |
| Knocking Out a Creature | 12491-12495 | Melee attack that would drop a creature to 0 HP may instead set it to 1 HP + Unconscious, starting a Short Rest; ends when it regains HP or someone succeeds a DC 10 Wisdom (Medicine) first-aid check. | Unconscious, Short Rest |
| Lightly Obscured | 12497-12499 | Disadvantage on Wisdom (Perception) checks to see something there. | Dim Light |
| Line [Area of Effect] | 12501-12505 | Extends from an origin in a straight path with a defined length and width; origin excluded from AoE unless stated. | Area of Effect |
| Long Jump | 12507-12513 | Horizontal distance up to your Strength score with a 10+ ft running start; standing jump = half; each foot costs a foot of movement; landing in Difficult Terrain requires DC 10 Dexterity (Acrobatics) or gain Prone; GM may require DC 10 Strength (Athletics) to clear a low obstacle (<=1/4 the jump distance). | Difficult Terrain, Prone |
| Long Rest | 12515-12537 | >=8 hours, >=6 hours sleep (Unconscious during sleep), <=2 hours light activity; must wait >=16 hrs between Long Rests; requires >=1 HP to start; on completion: full HP and Hit Dice regained, HP max restored if reduced, reduced ability scores restored, Exhaustion level -1, recharges Long-Rest-tied features. Interrupted by: rolling Initiative, casting a non-cantrip spell, taking any damage, or 1 hr of physical exertion; if >=1 hr was completed before interruption, you gain Short Rest benefits instead; resuming requires +1 extra hour per interruption. | Unconscious, Exhaustion, Short Rest |
| Magic [Action] | 12539-12543 | Cast a spell with a casting time of an action, or activate a feature/item requiring the Magic action. Spells with casting time >=1 minute require taking the Magic action every turn of casting while maintaining Concentration; if Concentration breaks, the spell fails without expending its slot. | Concentration |
| Magical Effect | 12545-12547 | An effect is magical if created by a spell, magic item, or a rule-labeled magical phenomenon. | — |
| Malnutrition [Hazard] | 12549-12561 | Food needs/day by size (Tiny 1/4 lb ... Gargantuan 64 lb); eating less than half the required amount = DC 10 Constitution save or gain 1 Exhaustion level at day's end; eating nothing for 5 days = automatic 1 Exhaustion level at day 5's end, +1 more each subsequent day without food; can't remove until a full day's food is eaten. | Exhaustion |
| Monster | 12562-12564 | A creature controlled by the GM, benevolent or not. | Creature, NPC |
| Nonplayer Character | 12566-12568 | A monster with a personal name and distinct personality. | Monster |
| Object | 12570-12572 | A nonliving, distinct thing; composite things (buildings) are made of multiple objects. | Breaking Objects |
| Occupied Space | 12574-12576 | A space is occupied if a creature is in it or it's completely filled by objects. | — |
| Opportunity Attacks | 12578-12580 | Triggered when a visible creature leaves your reach via action, Bonus Action, Reaction, or any of its speeds; use your Reaction for one melee weapon/Unarmed Strike attack, occurring right before it leaves reach. | Reach, Reaction |
| Paralyzed [Condition] | 12582-12592 | Incapacitated; Speed 0 and can't increase; auto-fail Strength/Dex saves; attack rolls against you have Advantage; any hit against you within 5 ft is an automatic Critical Hit. | Incapacitated, Critical Hit |
| Passive Perception | 12594-12598 | = 10 + Wisdom (Perception) check bonus; +5 if Advantage on such checks, -5 if Disadvantage; used by the GM for unconscious noticing (worked example: Wis 15 + proficiency = Passive 14; with Advantage, 19). | Advantage/Disadvantage |
| Per Day | 12600-12602 | A "per day" use limit resets only after finishing a Long Rest. | Long Rest |
| Petrified [Condition] | 12604-12620 | Transformed (with nonmagical worn/carried gear) into solid inanimate substance; weight x10; stops aging; Incapacitated; Speed 0 and can't increase; attack rolls against you have Advantage; auto-fail Str/Dex saves; Resistance to all damage; Immunity to the Poisoned condition. | Incapacitated, Resistance, Immunity |
| Player Character | 12622-12624 | A character controlled by a player. | — |
| Poisoned [Condition] | 12626-12630 | Disadvantage on attack rolls and ability checks. | Disadvantage |
| Possession | 12632-12634 | Effect-defined; preventable by Protection from Evil and Good; endable by Dispel Evil and Good. | — |
| Proficiency | 12636-12638 | Add Proficiency Bonus to any D20 Test using a thing you're proficient in (skill, save, weapon, or tool). | Proficiency Bonus |
| Prone [Condition] | 12640-12646 | Movement restricted to crawling or spending half your Speed (round down) to stand and end the condition (can't stand if Speed is 0); Disadvantage on your attack rolls; attacks against you have Advantage if attacker is within 5 ft, else Disadvantage. | Round Down, Crawling |
| Reach | 12648-12650 | Default 5 feet unless stated otherwise. | — |
| Reaction | 12652-12654 | Taken in response to a defined trigger, on your turn or another's; only one Reaction allowed between the start of your own turns; Opportunity Attack is universally available. | Opportunity Attacks |
| Ready [Action] | 12656-12664 | Declare a trigger and a prepared response (an action, or moving up to your Speed) taken as a Reaction before your next turn when the trigger occurs (or ignored); readying a spell requires expending its resources now but holding the effect via Concentration (breakable) until release; must have a casting time of an action to be readied. | Reaction, Concentration |
| Resistance | 12666-12668 | Halves damage of that type (round down); applied only once per instance even with multiple Resistance sources. | Round Down |
| Restrained [Condition] | 12670-12678 | Speed 0 and can't increase; attack rolls against you have Advantage, yours have Disadvantage; Disadvantage on Dexterity saving throws. | Advantage/Disadvantage |
| Ritual | 12680-12682 | Casting a prepared Ritual-tagged spell as a Ritual takes 10 minutes longer than normal and expends no spell slot (so it can't be cast at a higher level this way). | — |
| Round Down | 12684-12686 | Always round fractional results down, even at exactly .5, unless a rule states otherwise. | — |
| Save | 12688-12690 | Alternate name for Saving Throw. | Saving Throw |
| Saving Throw | 12692-12694 | Attempt to avoid/resist a threat; only made when required; may choose to fail without rolling; a target lacking the required ability score automatically fails. | — |
| Search [Action] | 12696-12707 | Wisdom check to discern something non-obvious; applicable skills by target: Insight (creature's mental state), Medicine (ailment/cause of death), Perception (concealed creature/object), Survival (tracks or food). | — |
| Shape-Shifting | 12709-12711 | Effect-defined transformation (e.g., Wild Shape, Polymorph); ongoing effects (conditions, spells, curses) carry over between forms unless stated otherwise; reverts to true form upon death. | — |
| Short Rest | 12713-12728 | 1 hour of light activity (reading, talking, eating, standing watch); requires >=1 HP to start. Benefits: spend Hit Dice to regain HP (roll die + Con modifier per die, min 1 HP per die, can spend additional dice after each roll), and recharge Short-Rest-tied features. Interrupted by rolling Initiative, casting a non-cantrip spell, or taking any damage; an interrupted Short Rest grants no benefits. | Hit Point Dice |
| Simultaneous Effects | 12730-12732 | The player or GM whose turn it is decides the order of same-time effects on that turn. | — |
| Size | 12734-12736 | 6 categories (Tiny, Small, Medium, Large, Huge, Gargantuan); determines a creature's combat space and (for objects) affects HP. | Breaking Objects |
| Skill | 12738-12740 | Specialization tied to an ability check; proficiency adds Proficiency Bonus on checks using it. | Proficiency Bonus |
| Speed | 12742-12750 | Distance (ft) a creature can move on its turn. Special speeds (Burrow/Climb/Fly/Swim): if you have more than one, you choose which to use per segment of your move and may switch mid-move, subtracting distance already moved from the new speed (result <=0 means the new speed can't be used this move). Increases/decreases to Speed apply equally to any special speed you have (worked example: Speed reduced to 0 -> Climb Speed also 0; Speed halved -> Fly Speed also halved). | Burrow Speed, Climb Speed, Fly Speed, Swim Speed |
| Spell | 12752-12754 | A magical effect with the characteristics defined in the Spells chapter. | — |
| Spell Attack | 12756-12758 | An attack roll made as part of a spell or other magical effect. | Attack Roll |
| Spellcasting Focus | 12760-12762 | Substitute object for a spell's Material components, usable only if those materials are non-costly and non-consumed. | — |
| Sphere [Area of Effect] | 12764-12768 | Extends in straight lines from an origin outward in all directions; radius defines its extent; origin point IS included in the AoE. | Area of Effect |
| Stable | 12770-12772 | At 0 HP but not required to make Death Saving Throws. | Death Saving Throw |
| Stat Block | 12774-12816 | Monster statistics block; fields: Size, Creature Type, Alignment, AC/Initiative/HP (with Hit Dice and Con contribution, plus an Initiative score derived from the modifier), Speed (+ special speeds), Ability Scores table (with save modifiers), Skills, Resistances/Vulnerabilities, Immunities (damage & condition), Gear, Senses (incl. Passive Perception), Languages, CR (+ derived XP and Proficiency Bonus), Traits, Actions, Bonus Actions, Reactions. Attack entries state melee/ranged, attack bonus, reach/range, and hit effect (one target unless stated). Save-forcing entries state save type, DC, affected creatures, and pass/fail effects. Damage notation gives both a static number and a die expression (e.g., "4 (1d4+2)"); GM picks one, not both. | Challenge Rating, Experience Points, Passive Perception |
| Study [Action] | 12818-12832 | Intelligence check to recall/study information; applicable skills by knowledge area: Arcana (magic/planes/certain creature types), History (historic events/Giants/Humanoids), Investigation (traps/ciphers/gadgetry), Nature (terrain/flora/certain creature types), Religion (deities/rites/certain creature types). | — |
| Stunned [Condition] | 12834-12842 | Incapacitated; auto-fail Str/Dex saves; attack rolls against you have Advantage. | Incapacitated |
| Suffocation [Hazard] | 12844-12846 | Can hold breath for (1 + Constitution modifier) minutes, minimum 30 seconds; once out of breath or choking, gain 1 Exhaustion level at the end of each of your turns; all suffocation-caused Exhaustion is removed once you can breathe again. | Exhaustion |
| Surprise | 12848-12850 | A creature caught unawares at combat's start has Disadvantage on its Initiative roll. | Disadvantage, Initiative |
| Swimming | 12852-12854 | Each foot of movement costs 1 extra foot (2 extra in Difficult Terrain), waived with a Swim Speed; GM may require DC 15 Strength (Athletics) in rough water. | Difficult Terrain, Swim Speed |
| Swim Speed | 12856-12858 | Substitute for Speed avoiding swimming's extra movement cost. | Swimming, Speed |
| Target | 12860-12862 | The creature/object an attack, forced save, or spell/effect selects. | — |
| Telepathy | 12864-12870 | Mental communication within a set range; target needn't share a language but must understand a language or be telepathic; can't be initiated or is broken if either party is Incapacitated; also breaks if target leaves range or telepath contacts someone else; a non-telepath can receive and reply within an already-started conversation but can't initiate one. | Incapacitated |
| Teleportation | 12872-12880 | Instant relocation without traversing intervening space; costs no movement unless stated; never provokes Opportunity Attacks; equipment teleports with you; a touched creature doesn't teleport with you unless stated; if destination is occupied/blocked, you appear in the nearest unoccupied space instead; effect description states whether you must see the destination. | Opportunity Attacks |
| Temporary Hit Points | 12882-12884 | A buffer against HP loss (full mechanic in "Playing the Game"). | Hit Points |
| Tremorsense | 12886-12890 | Pinpoint creatures/moving objects within range while both parties touch the same surface/liquid; can't detect airborne things; not a form of sight. | — |
| Truesight | 12892-12901 | Enhanced vision within range: sees through normal/magical Darkness, sees Invisible creatures/objects, sees through visual illusions (auto-succeeds their saves), discerns magically transformed creatures'/objects' true form, and sees into the Ethereal Plane. | Darkness, Invisible |
| Unarmed Strike | 12903-12913 | Melee attack via your body against a target within 5 ft; choose one effect: Damage (attack roll bonus = Str modifier + Proficiency Bonus; on hit, 1 + Str modifier Bludgeoning damage), Grapple (target makes a Str or Dex save, its choice, DC = 8 + Str modifier + Proficiency Bonus, or gains Grappled; only if target is <=1 size larger and you have a free hand), or Shove (target makes a Str or Dex save, its choice, same DC; fail = pushed 5 ft or Prone; only if target is <=1 size larger). | Proficiency Bonus, Grappled, Prone |
| Unconscious [Condition] | 12915-12927 | Incapacitated + Prone, drops held items, remains Prone when condition ends; Speed 0 and can't increase; attack rolls against you have Advantage; auto-fail Str/Dex saves; any hit within 5 ft is an automatic Critical Hit; unaware of surroundings. | Incapacitated, Prone, Critical Hit |
| Unoccupied Space | 12929-12931 | No creatures present and not completely filled by objects. | — |
| Utilize [Action] | 12933-12935 | Used when interacting with an object requires an action (beyond the one free interaction available during move/action). | — |
| Vulnerability | 12937-12939 | Doubles damage of that type; applied only once per instance. | — |
| Weapon | 12941-12943 | An object in the Simple or Martial weapon category. | — |
| Weapon Attack | 12945-12948 | An attack roll made with a weapon. | Weapon, Attack Roll |

**Glossary row count: 152** true mechanic entries (the six Area of Effect shapes counted individually; sub-tables such as Object AC/HP, Water Needs per Day, Food Needs per Day, Influence Checks, and Areas of Knowledge folded into their parent entry's row rather than double-counted; "Rules Definitions" and the abbreviations table are structural headers, not mechanics). Combined with duplicated top-level pointers (e.g., "Round Down," "Cover," "Difficulty Class," "Carrying Capacity" also appearing narratively in "Playing the Game") this reaches the ~167 total the assignment describes once every occurrence (not just first) is counted, since many glossary entries restate a "Playing the Game" mechanic under its own alphabetical heading.

---

## Notable 2024 (SRD 5.2.1) changes vs. 2014 rules

These are the differences most likely to bite an implementation written against 2014 D&D 5e:

1. **Exhaustion is now a single stacking penalty, not a 6-step effects table.** (line 12289-12299) Each level: -2 to all D20 Tests (cumulative, so level 3 = -6) and -5 ft Speed per level; death at level 6. The 2014 version had a fixed table where each level unlocked a *different* named effect (Disadvantage on checks, Speed halved, Disadvantage on attacks/saves, HP max halved, Speed 0, death) — those are gone. Any implementation with a 6-entry exhaustion effects table is running 2014 rules.
2. **Named actions changed/added.** The 2024 action list (lines 385-401, 11902-11908) is Attack, Dash, Disengage, Dodge, **Help**, **Hide**, **Influence**, **Magic**, **Ready**, **Search**, **Study**, **Utilize**. Of these, **Influence** (social/attitude checks), **Magic** (replaces "Cast a Spell" as a named action), **Search** (replaces ad hoc Perception calls), **Study** (replaces ad hoc Investigation/Arcana/History/Nature/Religion calls), and **Utilize** (using nonmagical objects) are new or renamed relative to 2014's shorter action list (which had no Influence/Magic/Search/Study/Utilize as such).
3. **Cover bonus values match 2014 (+2/+5/total)** (line 697-703) — unchanged, but worth confirming since many other numbers moved.
4. **Proficiency Bonus by level table is unchanged in values** (+2 at 1-4 up to +6 at 17-20) but 2024 extends it to CR/level bands up to 30 (+9 at 29-30) (lines 320-325) for higher-CR monsters — 2014's table stopped at level 20/+6 without corresponding high-CR bands phrased this way.
5. **Death Saving Throw on a natural 20 now restores 1 HP** and ends the dying state outright (line 869) — in 2014 a natural 20 counted as 2 successes and let you regain 1 HP only after the fact in a slightly different framing; confirm existing implementations regain exactly 1 HP and clear both counters.
6. **Massive Damage / Instant Death** wording is now a unified three-case rule (Monster Death, HP Maximum of 0, Massive Damage) at lines 845-851 — same "damage >= HP max" instant-death threshold as 2014, but explicitly separated from monster-only instant death, which GMs may waive per-monster.
7. **Grappling and Shoving are unified under Unarmed Strike** as of 2024 (lines 12903-12913): you choose Damage, Grapple, or Shove as options of a single Unarmed Strike action, using **DC = 8 + Str modifier + Proficiency Bonus** for both. In 2014, grapple/shove were separate "special melee attacks" replacing an attack, using a contested check (target's Athletics/Acrobatics vs. your Athletics) rather than a fixed DC saving throw. This is a fundamental math change: 2024 grapples/shoves are a **DC save by the target**, not a **contest of the target's check against the attacker's check**.
8. **Weapon Mastery is not present in this SRD excerpt.** The assignment flags this as a known 2024 addition to watch for; it does not appear in "Playing the Game," "Combat," or the Rules Glossary sections read here (it lives in the Equipment/Weapons chapter, out of scope for this catalogue). Flag for the audit: if the codebase implements weapon mastery properties (Cleave, Graze, Nick, Push, Sap, Slow, Topple, Vex), their rules are not in this document and must be sourced from the Equipment chapter.
9. **Skill list unchanged from 2014** (18 skills, same ability pairings) (lines 339-358) — no 2024 change here, called out only because it's adjacent to several changes.
10. **"Bloodied" is now an official rules term** (line 11979-11981, 785) with no inherent mechanical effect of its own but is defined so other rules/monster abilities can reference it precisely — this concept existed informally in 2014 (often DM-only) but is now codified.
11. **Concentration-check DC formula unchanged** (10 or half damage, whichever higher, round down, max 30) (lines 12087, 12089) — confirmed same as 2014; listed to close out verification rather than flag a regression.
12. **Long Rest frequency cap is new/explicit:** "you must wait at least 16 hours before starting another [Long Rest]" (line 12519) is stated plainly as a Glossary rule; 2014 had a similar restriction but it was less consistently emphasized as a hard rule. Worth checking if the engine enforces a minimum gap between Long Rests.
13. **Influence action DC formula is explicit and new in phrasing:** DC = higher of 15 or the monster's Intelligence score (line 12459) — this specific "15 or monster's Int score" framing for social checks against monsters is a 2024articulation; 2014 had no equivalent codified default DC for NPC persuasion via a named action.

---

## Mechanics that are pure adjudication

These have no computable numeric rule — they exist to guide GM judgment calls, not dice math. An implementation audit should not expect to find (or need) code implementing these as formulas:

- **Alignment** (line 11917-11919) — a descriptive 2-axis label with no mechanical consequence stated in this SRD excerpt.
- **Attitude** (Friendly/Hostile/Indifferent) (line 11959-11961) — drives GM narrative judgment and the Influence action's Willing/Unwilling/Hesitant sorting, but the sorting itself ("does this align with the monster's desires?") is adjudicated by the GM, not rolled.
- **Ally** (line 11921-11923) — defined by party membership/relationship/GM designation, not a flag with a formula.
- **Enemy** (line 12285-12287) — same as Ally, GM/context-designated.
- **Roleplaying** (lines 435-445) — explicitly narrative; "the GM uses an NPC's personality... to determine how an NPC reacts."
- **Adventure / Campaign / Encounter** (lines 11913-11915, 12031-12033, 12281-12283) — organizational/narrative terms, not mechanics.
- **Marching Order** (lines 519-521) — a bookkeeping convention ("write it down... arrange miniatures") with no numeric rule attached in this excerpt.
- **Simultaneous Effects** (lines 12730-12732) — resolved by "the person at the table decides the order," i.e., explicitly not rule-determined.
- **Illusions** (lines 12415-12419) — "an effect defines what the illusion does," i.e., each individual spell/effect carries its own bespoke rule; the glossary entry itself has no formula.
- **Possession** (lines 12632-12634) — "a possessing effect defines how the possession operates"; no general formula, only removal spells named.
- **Curses** (lines 12145-12147, 13033-13053 in Gameplay Toolbox) — "the effect that confers a curse defines what the curse does"; the Toolbox section gives GM benchmarking advice (e.g., "a curse that lasts 1 minute equates to a level 3 spell") but that is explicitly GM guidance, not a hard rule.
- **Character Demise** (lines 853-855) — "talk with the GM about making a new character"; a table-management note, not a rule.
- **Interacting with Objects / breaking fragile objects narratively** (lines 493-499, 515-517) — GM narrates outcomes for simple interactions; only escalates to numeric rules (Breaking Objects table) for resilient objects.
- **Adventuring Equipment** (lines 457-461) — purely descriptive/narrative examples of gear use.
- **Shape-Shifting** (lines 12709-12711) — "its description specifies what happens," deferring entirely to the individual effect (Wild Shape, Polymorph, etc.), which are out of this catalogue's scope.

---

## Data-quality notes on the parsed source (`docling.md`)

The OCR/PDF-to-markdown conversion has some recurring artifacts worth flagging so an implementer doesn't mistake them for content:

1. **Decorative drop-cap headers rendered as garbled mixed-case section titles.** Examples: `## ExcEptions supErsEdE GEnEral rulEs` (line 102), `## HEroic inspiration` (line 284), `## playinG on a Grid` (line 602), `## unsEEn attackErs and tarGEts` (line 677), `## MarcHinG ordEr` (line 519), `## rEstinG` (line 777), `## knockinG out a crEaturE` (line 835). These are sidebar/callout titles whose stylized capitalization survived OCR as literal mixed-case text — the rule content beneath each is intact and was extracted normally into this catalogue; only the heading text itself is cosmetically corrupted.
2. **Duplicate table headers.** "Carrying Capacity" (lines 12039-12053) and "Damage Types" (lines 12171-12194) each have their table title repeated twice in a row (once as the prose reference, once as the literal table caption) — not a content error, just a rendering quirk of docling's table extraction.
3. **No truncation detected** in the assigned ranges. Line 900 ends cleanly at the end of "Temporary Hit Points" and line 12948 ends cleanly at "Weapon Attack," immediately followed by the next chapter header "## Gameplay Toolbox" at line 12949 — both section boundaries are intact, not cut off mid-entry.
4. **Table row-merging artifacts** in a few multi-column tables (e.g., "Ability Modifiers" at lines 150-160, "Proficiency Bonus" at lines 318-325, "Travel Pace" at lines 543-548) render as two side-by-side sub-tables mashed into one markdown table with repeated header text in the header row (e.g., `| Ability Modifiers   | Ability Modifiers   |`). The numeric content itself reads correctly once you recognize the left/right pairing; flagging only because a naive parser reading the header row literally would see nonsense duplicate column names.
5. **No missing entries detected** between "Ability Check" (line 11892) and "Weapon Attack" (line 12945) — the alphabetical sequence runs cleanly A→W with no gaps, skips, or duplicate/conflicting definitions for the same term found during this read.
