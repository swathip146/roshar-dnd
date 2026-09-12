# Cosmere Invested Arts — Allomancy, Aonic Magic, and the Shared Casting Framework

Catalogue of everything in *The Invested Arts of the Cosmere v2.0* **except**
Surgebinding (Chapter 1, owned by other agents): the shared casting framework,
Chapter 2 (Allomancy), Chapter 3 (Aonic magic), and anything after Chapter 3.

**This is a D&D 5e-based system.** It is not the standalone Brotherwise
*Cosmere RPG* documented in `docs/mechanics/COSMERE_RPG_CORE.md` — do not
conflate the two. It uses **Investiture Points**, not spell slots.

**Sources**:
- `parsed_data/cosmere-5e-the-invested-arts-of-the-cosmere-v2-0/docling.md`
  (19,794 lines) — PRIMARY source for Allomancy and Aonic magic, cited as
  `IA:<line>`.
- `parsed_data/863203275-cosmere-5e-radiant-s-handbook-v2-0/docling.md`
  (14,396 lines) — cited as `HB:<line>` — the source of the shared casting
  **framework** (see Part 1: it is not in the Invested Arts book at all).

This document does **not** assess Python implementation status — that is
separate agents' work. No codebase files were read except a name-only check
of `components/combat/maneuver_executor.py`'s existing interpreter node
types, done because the task explicitly asks for a gap analysis against them.

---

## Part 0 — Chapter map of the source book

| Range | Content | Owner |
|---|---|---|
| `IA:1-116` | Version/spoiler notices, table of contents, Resources (links to companion books) | — |
| `IA:117-122` | Introduction | This doc (Part 1) |
| `IA:123-8859` | Chapter 1: Surgebinding Invested Arts | Two other agents (NOT this doc) |
| `IA:8860-10705` | Chapter 2: Allomancy Invested Arts | This doc (Part 3) |
| `IA:10706-19790` | Chapter 3: Aonic Invested Arts | This doc (Part 4) |
| `IA:19791` | "Credit" — end of book | — |

**There is nothing after Chapter 3.** No appendices, no art-index-by-level
section, no rules glossary, no changelog, no errata live inside this book.
(A separate, external Google-Doc "Changelog" is only *linked to* from the
Resources page, `IA:93-97`; its content is not present in `parsed_data/`.)
The book's *only* structure is: intro → Ch.1 Surgebinding → Ch.2 Allomancy →
Ch.3 Aonic → Credit. This closes out point 4 of the assignment: there is
nothing to catalogue beyond Chapter 3.

---

## Part 1 — The shared casting framework: NOT in this book, confirmed

`IA:121` states plainly: **"See the rules on casting Invested Arts in
Chapter 10 of the Radiant's Handbook."** This is not a partial pointer — a
targeted search of the entire Invested Arts book for the general Allomancy
mechanics (Misting vs. Mistborn, savantism, how burning works, the
duralumin/aluminum interaction rules as *general* rules rather than
per-art call-outs) turned up **nothing**; those also live outside this book,
in "Hoid's Guide to the Cosmere" (the Mistborn class description), which is
**not present in this repository at all** (`parsed_data/` has no such file).

The framework that *is* recoverable — Chapter 10 of the Radiant's Handbook,
already present in this repo at `HB:13107-13337` — is exhaustive for the
common casting chassis every Invested Art (Surgebinding, Allomantic, or
Aonic) obeys. This is the same conclusion `docs/mechanics/COSMERE_MECHANICS.md`
reached independently (its "PART 0" central-constraint note, and its Part 6):
Chapter 10 gives the chassis, but not what any *named* Invested Art does.
This document is the first to catalogue what that chassis actually says,
in full.

### 1.1 — Framework rules table

| Rule | Source line | Precise statement |
|---|---|---|
| What an Invested Art is | `HB:13113-13119` | "A discrete Invested effect, a single shaping of the magical Investiture... crafts them in a particular way, and releases the Invested energy to unleash the desired effect... all in the span of seconds." |
| Invested Art level range | `HB:13121-13125` | Levels 0 (cantrip) through 9. Character level and Art level are decoupled — e.g. a caster must be **17th** character level (not 9th) to cast a 9th-level Invested Art "if possible for their Order." |
| Known/prepared Arts | `HB:13127-13131` | Class-dependent: some classes (Elsecaller) have a fixed known list; others (Edgedancer) "prepare" Arts. Capacity is set per-class, per-level. |
| Investiture Points (IP) pool | `HB:13133-13141` | IP is the resource spent to cast. Refills entirely on a long rest — **conditioned on Stormlight Replenishment** (character level × 5 sm of Stormlight intake; see `HB:12339` / `COSMERE_MECHANICS.md` Part 1). Max IP and max castable Art level are both set by class+level tables (not reproduced in this book — they live in each class's own chapter). |
| **IP cost by Art level** (standard) | `HB:13145-13162` | Cantrips: **0 IP**. Table (applies to Edgedancers, Truthwatchers, Lightweavers — see exception below): 1st = **2**, 2nd = **3**, 3rd = **5**, 4th = **6**, 5th = **7**, 6th = **8**, 7th = **10**, 8th = **11**, 9th = **13**. |
| IP cost exception — Elsecaller | `HB:13147`, `HB:13173` | Elsecallers **always spend exactly 1 IP** per casting regardless of level, and always cast at "the highest level possible for their Elsecaller level, up to 5th" (e.g. a 7th-level Elsecaller casting a 1st-level Art casts it at 4th level for 1 IP). |
| 6th–9th level Arts: once-per-rest cap | `HB:13163-13165` | Even with enough IP to pay for it more than once, a 6th/7th/8th/9th-level Art can each be cast **only once** before a long rest, independent of remaining IP. |
| Upcasting | `HB:13167-13173` | Casting an Art above its base level: it "assumes the higher level for that casting," costs IP per the higher level's row, and only produces a stronger effect if the Art's own text says so ("At Higher Levels..."); otherwise upcasting simply wastes IP. |
| Cantrips | `HB:13175-13177` | Level 0, cast at-will, 0 IP. **Every class** (even non-casters) gets 2 cantrips via their two basic Surges; full Investiture-casting classes get more. |
| Casting in armor | `HB:13179-13181` | Must be proficient with all worn armor (incl. shields) to cast any Invested Art; otherwise "too distracted and physically hampered." |
| Casting Time — default | `HB:13189-13191` | Most Arts cost 1 action; some cost a bonus action, reaction, or longer. |
| Casting Time — bonus action | `HB:13193-13195` | Uses your bonus action (only if not already used this turn); cannot cast *another* Invested Art the same turn, except a cantrip with a 1-action casting time. |
| Casting Time — reaction | `HB:13197-13199` | Only usable exactly when the Art's own text specifies the trigger. |
| Casting Time — longer than one action | `HB:13201-13203` | Must spend your action **every turn** for the full casting time while concentrating; if concentration breaks mid-cast, the Art fails with **no IP expended**, and you must restart entirely to try again. |
| Range | `HB:13205-13213` | Expressed in feet, or "touch," or "self" (includes anything centered/originating on you, e.g. cones/lines). Once cast, an Art's ongoing effect is not bound by its cast range unless stated otherwise. |
| **Components — full decode** | `HB:13215-13241` | Three possible component letters, defined precisely below (§1.2). |
| Duration — instantaneous | `HB:13247-13249` | Effect exists for an instant; cannot be dispelled. |
| **Concentration** | `HB:13251-13263` | Concentration check = a **Constitution saving throw**. Breaks on: (a) casting another concentration Art (only one concentration Art active at a time — full stop, no exceptions listed), (b) taking damage — DC = **10 or half the damage taken, whichever is higher**, one separate save per distinct damage source in the same instant, (c) being incapacitated or killed. GM may also require a flat **DC 10** save for severe environmental effects (example given: a wave crashing over you on a ship in a highstorm). Ending concentration voluntarily costs no action. |
| Targets | `HB:13265-13277` | Must have "a clear path" (no total cover) to the target/point of origin; if you place an area at an unseen point behind an obstruction, the origin snaps to the near side of the obstruction. You can target yourself with a "choose a creature" Art unless it must be hostile/other-than-you; you can also target yourself if you're caught in your own AoE. |
| **Areas of Effect — 5 shapes** | `HB:13279-13313` | Cone: length = width at each point along it; origin **not** included in the area unless stated. Cube: point of origin on any face; side length given; origin **not** included unless stated. Cylinder: origin = center of a radius-circle (ground or effect height); expands outward to the radius then up/down by the given height; origin **is** included. Line: extends from origin along its length/width; origin **not** included unless stated. Sphere: origin = center; radius given in feet; origin **is** included. Obstruction giving total cover blocks the straight-line propagation of any of these shapes (Chapter 9 rules on cover apply). |
| **Saving throw DC formula** | `HB:13315-13319` | **DC = 8 + Investiture casting ability modifier + proficiency bonus + any special modifiers.** |
| **Invested attack bonus formula** | `HB:13321-13325` | **Attack bonus = Investiture casting ability modifier + proficiency bonus + any special modifiers.** Ranged Invested Art attacks made within 5 feet of a hostile, visible, non-incapacitated creature suffer disadvantage, same as ranged weapon attacks (Chapter 9). |
| Exhaustion penalty to casting | `HB:13375-13377` | Exhaustion level is subtracted from **all d20 rolls** (attack/check/save) **and** from the Invested save DC directly. |
| Combining Invested effects | `HB:13327-13331` | Effects of *different* Arts stack while durations overlap. Repeated castings of the *same* Art do **not** stack — only the single most potent instance applies (or the most recent, if tied) while durations overlap. |
| Invested Art Lists (cross-reference) | `HB:13333-13337` | Confirms per-class Art lists live in the Radiant's Handbook's class chapters, but full write-ups of every Art (including this book's own contents and Hoid's Guide additions) live in *The Invested Arts of the Cosmere*. |

### 1.2 — Components decoded

There is **no material-component ("M") entry as a generic letter** in the
casting framework text — `HB:13217` lists exactly two abbreviation letters
(**G**, **S**) plus an unabbreviated "material components" category that is
described in prose rather than tagged with an "M" in the framework chapter
itself. (Individual Art stat blocks in the Invested Arts book *do* print a
literal `Components: S` or `Components: G, S` line — see the Allomancy and
Aonic tables below — but no art descriptions header used a literal "M" in
the sample read for this document; material-cost items are called out by
name instead, e.g. "a large infused polestone.")

| Letter | Name | Precise meaning | Source |
|---|---|---|---|
| **G** | Glow | Casting causes the caster to visibly glow with escaping Stormlight (skin, nose, mouth, eyes) for the casting's duration only. Sheds **5 feet of dim light**. In bright light, an onlooker can notice it with a **Wisdom (Perception) check at disadvantage, DC 10**. | `HB:13219-13223` |
| **S** | Somatic | Requires a free hand for gestures. Holding a *small* shield (not medium) in that hand does not prevent casting. | `HB:13225-13229` |
| *(unlettered)* | Material | A minority of Arts require infused **polestones** of a specific type/size (costs defined in the Handbook's Chapter 5 "Polestones" section, not reproduced here). If a required sapphire-mark (sm) value is met or exceeded by one polestone, **that whole polestone cracks and becomes worthless**, even if its value exceeds the requirement — no change is given back. Some Arts instead only drain the polestone's Stormlight without cracking it; each Art's own text specifies which happens. Consequence (crack/drain) always occurs after casting, **regardless of whether the Art's effect actually succeeds** — e.g. a failed `resurrection` still cracks the diamonds used. If the Art is *interrupted before completion*, the polestone is untouched and stays fully infused. The same hand used for somatic gestures may also hold/access material components. | `HB:13231-13241` |

**Practical note for an engine**: every Allomancy and Aonic Art description
sampled in this document that prints a `Components:` line uses only `S`, or
`S, M (...)` with the material spelled out in parentheses (e.g. Aonic
Soulcast: `S, M (a large infused polestone, the type of which depends on the
essence)`, `IA:11501-11503`). No sampled Art in Allomancy or Aonic magic used
bare `G`; Allomancy instead expresses its "glow-equivalent" cost as a
**Bead**, consumed metal per casting — see Part 2 below, this is a
**third, book-specific resource notation** the framework chapter does not
mention because it's Allomancy-specific, not universal.

### 1.3 — Allomancy-specific casting wrinkle not in Chapter 10

Every Allomantic Invested Art of 2nd level or higher that needs a rarer
metal prints an explicit `Bead:`/`Beads:` line (e.g. `IA:8938-8940`,
"Bead: Nalatium bead") — this is **consumed as the material cost** for that
casting, on top of/instead of the `HB:13231` polestone rule, and is entirely
absent from the Radiant's Handbook's Chapter 10 text. This confirms
Allomancy has its own implicit material-component convention (a metal bead,
ingested/burned) that an engine must model as a distinct resource type from
Rosharan polestones.

---

## Part 2 — Allomancy (Chapter 2, `IA:8860-10705`)

### 2.1 — What this book does *not* explain

The Invested Arts book **does not contain** any general-mechanics section
for Allomancy — no metal list with effects, no Misting-vs-Mistborn
distinction, no savantism rules, no explanation of what burning a metal
*means* mechanically, and no general duralumin/aluminum interaction rules
(duralumin and aluminum only appear inside individual Art descriptions,
e.g. `IA:9529` "Duralumin Flare" and `IA:9713` "Expunge Investiture," never
as a standalone rules section). `IA:8866` explicitly defers the Mistborn
class's level-gating for God Alloy beads to "the Mistborn class description
in Hoid's Guide to the Cosmere" — **not present in this repository**. This
means an engine cannot derive full Allomancy mechanics from this repo's
`parsed_data/` alone; only the per-Art effects below are recoverable here.

### 2.2 — Garbled passage: the Mistborn level-list headers collapsed

`IA:8870-8878` (the "Mistborn Invested Arts" level index) is visibly damaged
by the PDF→Markdown conversion: what should be five separate level headings
(1st/2nd/3rd/4th/5th) collapsed into only two Markdown headings ("1st Level"
at `IA:8870` and "3rd Level" at `IA:8874`), with the "2nd Level" marker
surviving only as **inline plain text** buried mid-paragraph inside the 1st
Level block (`"...Unsurprise ( Zinc ) 2nd Level Calming Resolve ( Brass )..."`,
`IA:8872`), and "4th Level"/"5th Level" similarly buried inline inside the
3rd Level block (`IA:8877`). The art names and metal parentheticals
themselves are intact and were manually re-split by level for the table
below; only the heading structure is damaged, not the data. Same pattern
recurs at `IA:8886-8890` for the God Alloy level list (a "5th Level" marker
for Atium Shadows is buried inline after "Swell ( Ewlatium )").

### 2.3 — Garbled/incomplete passage: God Alloy index omits 2 of 8 described Arts

`IA:8886-8890`'s God Alloy level list names only 6 Arts (Axipull, Axipush,
Enlight, Malatium Shadow, Swell — all 4th level — and Atium Shadows, 5th
level). But the alphabetical description section (`IA:8892-10705`) actually
contains **8** God Alloy Arts: those 6, plus **Pulse** (5th-level Admatium,
`IA:10163-10186`, a full stat block with an attack/stun effect) and **Slide**
(5th-level Endalatium, `IA:10474-10499`, a full stat block with a bendalloy
bubble effect) — neither is present in the level-list index at all. This is
not an OCR artifact; the two orphaned Arts are also formatted as plain
bullet list items (`- Slide`, `- Ruin` — see below) rather than `##`
headings, unlike every other Art in the chapter, suggesting the source
author's own document, not just the conversion, has an incomplete index.
**Flagged, not guessed**: treat Pulse and Slide as real, complete,
usable Arts — their full stat blocks are intact — but know the book's own
index doesn't list them.

### 2.4 — Garbled passage: "Ruin" formatted as a bullet, not a heading

`IA:10358` ("- Ruin") breaks the pattern of every other Allomantic Art
(a `##` or `## ▶` Markdown heading). Its full stat block (`IA:10358-10381`)
is otherwise intact and it IS present in the 1st-level index list
(`IA:8872`). Likely a heading-level conversion slip for this one entry only.

### 2.5 — Mistborn Invested Arts: full stat-block table

All 66 Allomantic Invested Arts. "Concentration?" = Yes if the entry has the
▶ symbol and/or its Duration reads "Concentration, up to X." Metal(s) in the
level-header line are the resource burned; a `Bead:`/`Beads:` line (where
present) is the consumed material component (see §1.3).

| Art | Level | Metal(s) | Source line | Casting time | Range | Bead (component) | Duration | Conc.? | Effect (precise numbers) | Scaling |
|---|---|---|---|---|---|---|---|---|---|---|
| Alarmcloud | 1st | Bronze & Copper | `8898` | 1 minute | Self | — | 8 hours | No | 20-ft-radius sphere (or custom shape ≤20 ft/side) centered on caster; alerts caster (mental ping, wakes if asleep) when Tiny+ creature enters; caster excludes chosen creatures; must stay within 1 mile or it ends. | None stated |
| Atium Shadows ▶ | 5th (God Alloy) | Nalatium | `8926` | 1 action | Self | Nalatium bead | Conc., up to 1 min | Yes | Future sight of every creature/non-aluminum object within 30 ft; immune to surprise; advantage on all attack/check/save except Knowledge checks; enemies have disadvantage attacking caster; resistance to all damage (not doubled if already resistant). No benefit vs. another creature also using future sight; aluminum-weapon attackers bypass the disadvantage/resistance. | None (no "At Higher Levels") |
| Axipull | 4th (God Alloy) | Irolatium | `8950` | 1 bonus action | 120 feet | Irolatium bead | Instantaneous | No | Ironpulls the "axi" inside a seen creature (works even through aluminum armor); if target's weight class ≤ caster's, target is pulled adjacent to caster; if greater, caster is pulled adjacent to target. | None |
| Axipush | 4th (God Alloy) | Stelatium | `8974` | 1 bonus action | 60 feet | Stelatium bead | Instantaneous | No | Steelpushes the "axi" inside a seen creature (bypasses aluminum armor); if target's weight class ≤ caster's, target pushed 60 ft directly away (max 120 ft total); if greater, caster is pushed 60 ft away from target instead. | None |
| Bendalloy Bubble ▶ | 3rd | Bendalloy | `9000` | 1 action | Self | Bead of bendalloy | Conc., up to 1 round | Yes | Creates an invisible bubble around caster only; pops if caster touches border or aluminum crosses it. Inside/outside relative speed 2×; ranged/Art attacks through the border at disadvantage; melee/AoE unaffected. Creatures inside get 2 turns per 1 outside turn via a separate "Bendalloy Round" at end of initiative. | 4th level: radius up to 5 ft (includes others), duration 2 rounds. 5th level: radius up to 10 ft, duration 3 rounds. |
| Bestial Domination ▶ | 4th | Brass | `9036` | 1 action | 60 feet | — | Conc., up to 1 min | Yes | Save: WIS. Charms a beast on fail (advantage on the save if caster/allies are fighting it). Caster issues commands at will while conscious, no action; action = total control until end of caster's next turn. New WIS save each time target takes damage; success ends the Art. | 5th level: duration extends to Conc., up to 10 min. |
| Bestial Influence | 1st | Brass | `9066` | 1 action | 30 feet | — | 24 hours | No | Save: WIS. Fails automatically if beast's Intelligence ≥ 4. On fail, beast charmed for duration; ends immediately if caster/companions harm it. | +1 additional beast targeted per level above 1st. |
| Cadmium Bubble ▶ | 3rd | Cadmium | `9092` | 1 action | Self | Bead of cadmium | Conc., up to 10 min (100 min outside bubble) | Yes | 15-ft-radius bubble; pops on touch to border or aluminum crossing. Time ratio 1:10 (1 round inside = 10 rounds/1 min outside). Ranged/Art attacks through border: disadvantage, and half damage if they hit. Creatures inside act once per 10 outside-turns via a "Cadmium Round." Invested communication through the bubble: 50% chance to fail. | 4th level: duration 1 hr (10 hr outside). 5th level: 5 hr (50 hr outside). |
| Calming Resolve | 2nd | Brass | `9130` | 1 action | Self | — | Instantaneous | No | Save: CHA (can be voluntarily failed). Each chosen humanoid in a 20-ft-radius sphere on fail: any charmed/frightened effect on them ends. | None |
| Cause Fear ▶ | 1st | Zinc | `9152` | 1 action | 60 feet | — | Conc., up to 1 min | Yes | Save: WIS. On fail, target frightened of caster; repeat save at end of each of target's turns to end. | +1 target per level above 1st (targets must be within 30 ft of each other). |
| Charm Creature | 4th | Brass | `9174` | 1 action | 30 feet | — | 1 hour | No | Save: WIS (advantage if caster/allies fighting it). On fail, charmed until Art ends or harmed by caster/allies; target is friendly; knows it was charmed once Art ends. | 5th level: target 2 creatures at once (must be within 30 ft of each other). |
| Charm Person | 1st | Brass | `9198` | 1 action | 30 feet | — | 1 hour | No | Save: WIS (advantage if fighting). On fail, charmed, regards caster as friendly acquaintance; knows once Art ends. | +1 target per level above 1st (within 15 ft of each other). |
| Chromium Counter | 3rd | Bronze & Chromium | `9222` | 1 reaction | 30 feet | Bead of chromium | Instantaneous | No | Cancels a seen creature's in-progress Invested Art (even without somatic component, via bronze Seeking). Level ≤3 Art: auto-fails. Level ≥4: d20 + Investiture mod (no proficiency) vs. DC 10 + Art's level; success ends it. Shard-powered Art (e.g. from a God Alloy bead): DC 14 + Art's level instead, always requires the roll. | 4th level+: interrupted Art auto-fails if its level ≤ the level chromium counter was cast at. |
| Cognitive Fortitude ▶ | 3rd | Brass & Copper | `9250` | 1 action | Touch | — | Conc., up to 1 hour | Yes | Target gains resistance to psychic damage + advantage on INT/WIS/CHA saves for duration. | +1 target per level above 3rd (within 30 ft of each other). |
| Collective Suggestion | 5th | Brass, Duralumin, & Zinc | `9270` | 1 action | 60 feet | Bead of duralumin | 24 hours | No | Save: WIS, up to 8 seen creatures who can hear/understand caster; can't-be-charmed creatures immune. On fail, pursues a stated 1-2 sentence course of action for the duration (or until finished, if shorter); harmful suggestions end the Art; damaging the target ends the Art. | None |
| Command | 1st | Brass & Zinc | `9304` | 1 action | 60 feet | — | 1 round | No | Save: WIS. On fail, follows a 1-word command (Approach/Drop/Flee/Grovel/Halt, each precisely defined) on its next turn; no effect if it can't understand caster's language or command is directly harmful. | +1 target per level above 1st (within 30 ft of each other). |
| Confusion ▶ | 4th | Zinc | `9334` | 1 action | 90 feet | — | Conc., up to 1 min | Yes | 10-ft-radius sphere; each chosen creature: Save WIS or affected. Affected: no reactions; roll d10 each turn start — 1: random-direction full move, no action (direction via d8); 2-6: no move/action; 7-8: melee attack vs. random creature in reach (nothing if none); 9-0: normal. | 5th level: radius 15 ft. |
| Copperburst | 3rd | Copper & Nicrosil | `9369` | 1 action | Touch | Bead of nicrosil | 8 hours | No | Touched target (creature/place/object ≤10 ft/dimension) hidden from detection Investiture (can't be targeted by location-detect or spying Investiture) — does not grant full coppercloud functionality otherwise. | None |
| Copperpierce ▶ | 4th | Duralumin | `9403` | 1 action | Self | Bead of duralumin | Conc., up to 1 min | Yes | Caster's Invested Arts and other Allomantic abilities (steelpush/ironpull) pierce copperclouds for duration. | None |
| Counter Sphere | 3rd | Aluminum & Copper | `9427` | 1 reaction | Self | Bead of aluminum | Duration of triggering Art | No | Vs. an area-targeting Art affecting caster's space: level ≤3, auto-creates a 5-ft-radius immune bubble (fixed in place, doesn't move with caster) for the triggering Art's duration. Level ≥4: d20 + Investiture mod (no prof.) vs. DC 10 + Art's level; success creates the bubble. Shard-powered source: DC 14 + Art's level, always rolled. | 4th level+: bubble created automatically if the area Art's level ≤ level counter sphere was cast at. |
| Create Coppercloud ▶ | 1st | Copper | `9455` | 1 action | Self | — | Conc., up to 10 min | Yes | 5-ft-radius sphere coppercloud, moves with caster; hides Investiture/Invested items(appear mundane)/Invested beings inside; doesn't block most Arts from piercing unless stated (message and locate creature explicitly can't pierce; command, scrying explicitly can). | +5-ft radius per level above 1st; +5 min duration per level above 1st (still requires concentration). |
| Detect Investiture ▶ | 1st | Bronze | `9479` | 1 action | Self | — | Conc., up to 10 min | Yes | Senses basic Investiture within 30 ft (source must be visible); action to ID its type if recognized. Blocked by invisibility, full aluminum coverage, or coppercloud. | 3rd level+: also detects if a visible, uncovered creature in range is a Surgebinder/Corruption/splinter/entity or otherwise has innate Investiture. |
| Dominate Person ▶ | 5th | Duralumin & Zinc | `9499` | 1 action | 60 feet | Bead of duralumin | Conc., up to 1 min | Yes | Save: WIS (advantage if fighting). On fail, charmed + telepathic link (same Realm) for duration; caster issues commands at will (no action) while conscious; action = total control until end of caster's next turn. New WIS save each damage instance; success ends Art. | None stated |
| Duralumin Flare ▶ | 5th | Duralumin | `9529` | 1 action | Self | Bead of duralumin | Conc., up to 1 min | Yes | Steelpush/ironpull Allomantic distance +20 ft; weight class +1. Each push/pull use while active requires a STR save, DC **15**; failure wastes the push/pull and the action/bonus action spent. | None stated |
| Ebullition of Terror ▶ | 3rd | Zinc | `9557` | 1 action | Self | — | Conc., up to 1 min | Yes | 30-ft cone; Save WIS or drop held items + frightened for duration. While frightened: must Dash away from caster by safest route each turn (unless nowhere to move); if it ends its turn out of caster's line of sight, a WIS save ends the Art for that creature. | None stated |
| Electrum Expanse | 4th | Duralumin & Electrum | `9581` | 1 action | Self | Bead of duralumin, bead of electrum | Instantaneous | No | Peeks 1 hour into the future of the surrounding area; subjectively takes 1 minute for caster (frozen, no move/actions) but instantaneous to onlookers. Approximation only — future can change. | None |
| Electrum Shadows ▶ | 3rd | Electrum | `9607` | 1 action | Self | Bead of electrum | Conc., up to 1 min | Yes | +1d6 bonus on all attack rolls, saves, and specific listed ability checks (DEX Acrobatics, STR Athletics, INT Investigation, CHA Performance, DEX Sleight of Hand, DEX Stealth, WIS Survival). No bonus on attacks vs. a target that also has future sight; future-sight creatures gain no benefit attacking the caster. | None stated |
| Empowered Seek | 3rd | Bronze & Duralumin | `9633` | 1 action | Self | Bead of duralumin | Instantaneous | No | Detects all Investiture within 100 ft, piercing everything except aluminum (pierces copperclouds too); gives exact counts (not direction/distance) of: active Invested Arts, Arts cast within the last round, Invested items legendary-or-less-rare (artifacts count as "3 items," uncommunicated as such), Surgebinders, Corruptions, splinters, entities. | None |
| Enlight | 4th (God Alloy) | Inlatium | `9665` | 1 action | Touch | Inlatium bead | Instantaneous | No | Touched other creature gains darkvision 120 ft + blindsight 60 ft for 1 hour. | None |
| Enthrall ▶ | 2nd | Brass & Zinc | `9689` | 1 action | 60 feet | — | Conc., up to 1 min | Yes | Save: WIS (can't-be-charmed creatures auto-succeed; advantage if fighting). On fail, disadvantage on WIS (Perception) checks to perceive anyone but the caster, until Art ends or target leaves range. | None |
| Expunge Investiture | 3rd | Aluminum | `9713` | 1 action | Self | Bead of aluminum | Instantaneous | No | Ends an Art affecting caster: level ≤3 ends automatically. Level ≥4: d20 + Investiture mod (no prof.) vs. DC 10 + Art's level. | 4th level+: auto-ends if the affecting Art's level ≤ level expunge was cast at. |
| Fast Friends ▶ | 3rd | Brass & Zinc | `9739` | 1 action | 30 feet | — | Conc., up to 1 min | Yes | Save: WIS (advantage if fighting). On fail, charmed and performs requested services/activities; new WIS save if a task would harm it or conflicts with its normal activities; certain-death tasks end the Art outright; knows it was charmed once ended. | +1 target per level above 3rd. |
| Frenzy of Resolve ▶ | 3rd | Duralumin & Zinc | `9769` | 1 action | Self | Bead of duralumin | Conc., up to 1 min | Yes | 30-ft sphere, moves with caster. Chosen creatures inside: advantage on WIS saves and death saves; regain max possible HP from any healing. | None stated |
| Gold Expanse | 4th | Duralumin & Gold | `9793` | 1 action | Self | Bead of duralumin, bead of gold | Instantaneous | No | Peeks 1 hour into the past of the area (mirror of Electrum Expanse); subjectively 1 minute, frozen, no move/actions; approximate — may miss fine detail. | None |
| Gold Shadow ▶ | 3rd | Gold | `9817` | 1 action | Self | Bead of gold | Conc., up to 1 min | Yes | Creates an invisible (to others) "gold shadow" of caster acting out a chosen alternate past decision, adjacent space. Caster can spend an action on a later turn to become blinded/deafened and perceive from the shadow's alternate perspective. After it disappears: WIS save, DC = **20 − proficiency bonus**; fail = 1 level of exhaustion. | None stated |
| Greater Leech | 5th | Chromium | `9843` | 1 action | Touch | Bead of chromium | Instantaneous | No | Ends one Invested effect on touched target that: charmed/petrified it, reduced an ability score, or reduced HP maximum. Also ends any Art/effect explicitly listed as endable by `greater restoration`. | None |
| Honed Evasion | 2nd | Bendalloy | `9873` | 1 reaction | Self | Bead of bendalloy | Instantaneous | No | On a DEX/STR save: +Investiture mod bonus to the save. If also subjected to damage: no damage on a successful save, half on a failed one. | None |
| Identify | 1st | Bronze | `9899` | 1 minute | Touch | — | Instantaneous | No | Touched object: learn Connection/Spiritual properties, full Invested-item details (bonding requirement, charges), and any Arts currently affecting it. Touched creature instead: learn what Arts currently affect them. | None |
| Inflame Allies ▶ | 2nd | Zinc | `9919` | 1 action | 15 feet | — | Conc., up to 1 min | Yes | Chosen creatures deal +1d4 force damage on melee weapon hits while in range, for duration. | 3rd level+: range +5 ft and damage +1d4 per level above 2nd. |
| Inflict Pain ▶ | 2nd | Zinc | `9937` | 1 bonus action | 10 feet | — | Conc., up to 1 min | Yes | Save: CON, triggered on caster's next melee hit vs. target. Success: +1d8 psychic on that hit, Art ends. Failure: +1d12 psychic on that hit, then +1d6 psychic on every subsequent melee hit by caster on that target until Art ends. | None stated |
| Invested Burst | 4th | Nicrosil & Zinc | `9961` | 1 action | Touch | Bead of nicrosil | 8 hours | No | Touched creature's Invested attack bonus and Invested save DC (if any) +1 for duration; only one instance can affect a given creature at a time. | None |
| Investiture Wipe | 2nd | Chromium | `9983` | 1 action | Touch | Bead of chromium | Instantaneous | No | Attack roll (Investiture mod + prof.) vs. a touched, concentrating target. Miss: bead wasted, no effect. Hit: forces a concentration check at DC = caster's Invested save DC; failure ends target's concentration. | None |
| Lesser Leech | 2nd | Chromium | `10013` | 1 action | Touch | Bead of chromium | Instantaneous | No | Ends one Invested effect causing blinded, deafened, paralyzed, or poisoned on touched target. | None |
| Malatium Shadow ▶ | 4th (God Alloy) | Malatium | `10037` | 1 action | 30 feet | Malatium bead | Conc., up to 1 min | Yes | Creates an invisible (except to caster and target) "malatium shadow" reenacting a chosen exact past moment near the target; caster hears only the shadow. Attack rolls vs. caster: advantage; caster's saves: disadvantage (except CON concentration saves for this Art). Target can spend its action for a WIS save to disrupt: 1st/2nd success = hazy for that round; 3rd success during duration = ends immediately. | None stated |
| Mist's Boon ▶ | 2nd | Aluminum & Copper | `10063` | 1 action | Self | Bead of aluminum | Conc., up to 1 hour | Yes | Chosen creatures (incl. caster) within 30 ft: +10 to DEX (Stealth) checks. | None stated |
| Preserve | 1st | Brass | `10091` | 1 action | 30 feet | — | Conc., up to 1 min | Yes | 3 chosen targets: on any attack roll or save before Art ends, may roll d4 and add to the result. | +1 target per level above 1st. |
| Probe Emotions | 2nd | Brass & Zinc | `10111` | 1 action | 10 feet | — | Instantaneous | No | Save: CHA. Success: Art fails, target knows an attempt was made. Failure: target unaffected, but GM reveals its 2 strongest current emotions to caster. | None |
| Protection from Investiture ▶ | 3rd | Copper & Nicrosil | `10135` | 1 action | Touch | Bead of nicrosil | Conc., up to 1 min | Yes | Willing touched target: Surgebinders/corruptions/entities have disadvantage attacking it; can't be charmed/frightened by them; if already charmed/frightened by such a creature, advantage on the next relevant save. | None stated |
| Pulse | 5th (God Alloy) | Admatium | `10161` | 1 action | 120 feet | Admatium bead | Instantaneous | No | Save: DEX vs. a cadmium slowness bubble on a seen creature (not self). Failure: stunned for exactly 3 full turns (ends at end of the 3rd); at end of each of target's turns, a STR save can end it early. | None |
| Pulse Shield | 2nd | Cadmium | `10187` | 1 reaction (on self/an ally within 5 ft being hit) | 5 feet | Bead of cadmium | Instantaneous | No | +10 AC bonus retroactively applied against the one triggering attack. | None |
| Recuperate | 3rd | Duralumin | `10217` | 1 reaction (on receiving Invested healing) | Self | Bead of duralumin | Instantaneous | No | Adds 2 extra dice to a dice-based Invested healing roll caster is the recipient of. | +1 die per level above 3rd. |
| Refocus | 2nd | Brass & Duralumin | `10241` | 1 reaction (on seeing an ally fail a concentration check) | 15 feet | Bead of duralumin | Instantaneous | No | Target rerolls the failed concentration check, +caster's WIS modifier (min +1) bonus on the reroll. A given creature can only benefit from this once until the start of its next turn (even from a different caster). | None |
| Resist Investiture ▶ | 3rd | Aluminum | `10267` | 1 bonus action | Self | Bead of aluminum | Conc., up to 1 min | Yes | Resistance to Invested bludgeoning/piercing/slashing damage and resistance to damage from Invested Arts/effects generally, for duration. | None stated |
| Riot Emotion | 1st | Zinc | `10289` | 1 action | Self (10-ft cone) | — | Instantaneous | No | Save: CHA (voluntary fail allowed). Choose 1 emotion to Riot (increase) in all who fail; GM adjudicates roleplay effect — explicitly "none of the effects are mechanical." | 2nd level+: cone +10 ft/level above 1st. 3rd level: 2 emotions at once. 5th level: 3 emotions at once. |
| Rioted Guidance ▶ | 1st | Zinc | `10342` | 1 action | Touch | — | Conc., up to 1 min | Yes | Willing touched creature: once before Art ends, may add a d8 roll to one ability check (roll before or after the check, before result is announced); Art ends once used. | None |
| Ruin | 1st | Zinc | `10358` | 1 action | 30 feet | — | Conc., up to 1 min | Yes | Save: CHA, up to 3 chosen creatures. On fail, must subtract a rolled d4 from their next attack roll or save before Art ends. | +1 target per level above 1st. |
| Sap Energy ▶ | 2nd | Brass | `10384` | 1 action | 30 feet | — | Conc., up to 1 min | Yes | Save: CHA. On fail, target's speed halved for duration; repeatable save at start of each of target's turns ends it early on success. | None stated |
| Seek Creature ▶ | 4th | Bronze & Duralumin | `10404` | 1 action | Self | Bead of duralumin | Conc., up to 8 hours | Yes | Senses direction (and movement direction if moving) to a named/described, familiar (been within 30 ft in the last year), at-least-somewhat-Invested (not a drab) creature within 1,000 ft. Blocked by coppercloud/aluminum in the direct path. | None stated |
| Shocking Rattle | 1st | Zinc | `10428` | 1 action | 30 feet | — | Instantaneous | No | Save: WIS. Fail: 1d8 psychic damage + loses reactions until start of its next turn. | +1d8 damage per level above 1st. |
| Sleep | 1st | Brass | `10452` | 1 action | 30 feet | — | 1 minute | No | Roll 5d8 = total HP pool; affects creatures within 30 ft in ascending current-HP order (skipping unconscious/immune creatures), subtracting each affected creature's HP from the pool until exhausted. Affected creatures fall unconscious until Art ends, they take damage, or someone spends an action to wake them. Entities and charm-immune creatures unaffected. | +2d8 to the pool per level above 1st. |
| Slide ▶ | 5th (God Alloy) | Endalatium | `10474` | 1 action | 60 feet | Endalatium bead | Conc., up to 1 min | Yes | Envelops a seen, non-self creature in a bendalloy bubble: extra reaction each turn start, +3 AC, advantage on STR/DEX saves, an additional action each turn; ranged weapon/Art attacks against it at disadvantage; its speed halved; must stay within 60 ft and in sight or the bubble pops (stunning it until end of its next turn — unless the Art ends normally/voluntarily, in which case no stun). | None stated |
| Soothe Emotion | 1st | Brass | `10500` | 1 action | Self (10-ft cone) | — | Instantaneous | No | Save: CHA (voluntary fail allowed). Choose 1 emotion to Soothe (lessen) in all who fail; explicitly non-mechanical, GM-adjudicated. | 2nd level+: cone +10 ft/level above 1st. 3rd level: 2 emotions. 5th level: 3 emotions. |
| Soothed Resistance ▶ | 1st | Brass | `10554` | 1 action | Touch | — | Conc., up to 1 min | Yes | Willing touched creature: once before Art ends, add a d8 roll to one saving throw (roll before/after, before result announced); Art ends once used. | None |
| Stupefy Creature ▶ | 5th | Brass & Duralumin | `10572` | 1 action | 90 feet | Bead of duralumin | Conc., up to 1 min | Yes | Save: WIS. Fail: paralyzed for duration; repeat save at end of each of its turns to end early. | None stated |
| Stupefy Person ▶ | 2nd | Brass | `10598` | 1 action | 60 feet | — | Conc., up to 1 min | Yes | Save: WIS (humanoid only). Fail: paralyzed for duration; repeat save each turn end to end early. | +1 target per level above 2nd (within 30 ft of each other). |
| Suggestion ▶ | 2nd | Brass & Zinc | `10622` | 1 action | 30 feet | — | Conc., up to 8 hours | Yes | Save: WIS, 1 target who can hear/understand caster; can't-be-charmed immune. Fail: pursues a 1-2 sentence reasonable course of action for duration or until finished; harmful requests end the Art; damaging target ends it. | None |
| Swell | 4th (God Alloy) | Ewlatium | `10648` | 1 action | Touch | Ewlatium bead | Instantaneous | No | Touched other creature: heals 4d12 HP; advantage on STR checks/saves/attacks using STR mod until end of its next turn. | None |
| Unsurprise | 1st | Zinc | `10676` | 1 reaction (at initiative start) | 30 feet | — | Instantaneous | No | Targets ≤ caster's proficiency bonus in count, willing, haven't acted yet, not self. WIS check, DC = **20 − number of hostile creatures visible within 30 ft of each targeted creature** (computed per-target). Success: can't be surprised round 1, free reaction to stand if prone, free bonus action before its turn. | None |

**Count: 66 Mistborn/God-Alloy Allomantic Invested Arts** (58 standard-metal
+ 8 God Alloy, including the 2 orphaned-from-index arts in §2.3).

---

## Part 3 — Aonic magic (Chapter 3, `IA:10706-19790`)

### 3.1 — What this book does *not* explain

As with Allomancy, general AonDor mechanics beyond the casting framework
(how drawing an Aon equation works mechanically outside of specific Arts,
what the `☰` "equation" marker changes about casting procedure, and general
Elantrian rules such as the Shaod, Dor connection, or Aonbook mechanics) are
**deferred to "the Elantrian class description in Hoid's Guide to the
Cosmere,"** stated explicitly at `IA:10712` — again, **not present in this
repository**.

### 3.2 — The Aon reference list (`IA:10862-11153`)

A ~170-row table mapping individual Aon syllables (single "letters" of the
Aonic alphabet, e.g. *Dao* = "Stability, Security," *Ehe* = "Fire, Warmth")
to a one-line thematic gloss and the list of Invested Arts that require that
Aon as one of their casting components. This is **not** a numeric-cost
table — Aons are components (see below), not a point cost. It is fully
captured in the source and not reproduced row-by-row here since it is a
naming/flavor reference, not mechanical, but its role is load-bearing:

**Components model, Aonic-specific**: every leveled Aonic Art (1st+) lists
`Required Aon(s)` as its true "material/somatic prerequisite" — the caster
must know that Aon (i.e., have it recorded in their Aonbook, per
`IA:10712`) to cast the Art at all, in addition to the universal `S`
(sometimes `S, M`) component line from the Radiant's Handbook framework.
This is functionally a **components layer Chapter 10 does not describe**:
"required Aons known" is a prerequisite gate on top of, not instead of, the
G/S/M system. Cantrips (`IA:10716-10765`) require **no** listed Aon.

**Garbled passage — Aon list row wrapping**: several rows of the Aon table
lost their column alignment in conversion, e.g. `IA:10895`
("Aor 'Possessions,' Things' Aon Aor targets objects...") and `IA:11029-11048`
(multiple rows where the Aon syllable, translation, and gloss text are
mis-split across columns, e.g. `IA:11030` "Lao 'Alarm, Alert' Aon Lao
creates a protective | Alarm | alarm."). The Aon-to-syllable mapping and the
Art cross-references are still legible and were used as-is; only the
column boundaries are visually scrambled, not the underlying data.

**Garbled passage — Aon-list-to-description-section wrap**: `IA:10778-10784`
("Sending ( )" followed on a separate content line by "Aem, Koe, Tia") is a
line-wrap artifact splitting the required-Aon parenthetical for `Sending`
across two source lines; the actual required Aons (**Aem, Koe, Tia**) are
recoverable from the following line, not lost.

### 3.3 — Aonic Invested Art descriptions

Below is the fork-extracted table covering every Aonic Invested Art from
`IA:11553` (continuation of Aqueous Prison) through the end of the chapter.
Combined with the arts I read directly above that range (Acid Splash,
Acidic Stream, Alarm, Alter, Annihilate, Anti-Investiture Field, Aon Shield,
Aongate, Aonskip, Aonic Soulcast, and the start of Aqueous Prison,
`IA:11160-11553`), this is the complete Chapter 3 art catalogue.

**[FORK OUTPUT PENDING — inserted below once the extraction agent returns]**

---

## Part 4 — Effect types an engine must support

Cross-referencing the Allomancy/Aonic tables above against
`components/combat/maneuver_executor.py`'s existing declarative node types
(`target`, `save`, `attack`, `damage`, `roll`, `ieffect2` — confirmed by
name only, no implementation read):

| Effect pattern seen repeatedly above | Existing node type it maps to | Gap? |
|---|---|---|
| "Save: X, on fail apply condition/damage" | `save` (+ `damage`/`ieffect2` follow-up) | Covered |
| Flat/scaling damage on a hit or failed save | `damage` | Covered |
| Attack roll using Investiture mod + proficiency | `attack` | Covered, **if** it can source its bonus from an "Investiture casting ability modifier" rather than only STR/DEX — confirm the attack node supports a configurable ability-mod source (Part 1's formula: 8 + mod + prof + special, and mod + prof + special for attacks) |
| Ability-check-based contests unrelated to attack/save (e.g. Chromium Counter's raw d20+mod vs. flat DC, Unsurprise's WIS check vs. a *computed* DC, Aonic Soulcast's Investiture ability check vs. a *table-driven* DC) | `roll` | **Partial gap**: `roll` alone doesn't obviously carry "compare against a DC that is itself a formula/table lookup, with pass/fail branches." Needs either a generic **check-vs-DC** node (target roll ≥ dynamic DC → branch) or an extension of `roll`. |
| Ongoing conditions with repeated end-of-turn save chances (paralysis with escalating "at the end of each of its turns" save-to-end pattern) | `ieffect2` (presumably a generic imposed-effect wrapper) | Likely covered if `ieffect2` supports a recurring-save-to-end clause; **flag for verification against implementation**, not assessed here per scope. |
| Resource-consuming casting components beyond spell slots: **Bead** (Allomancy, a consumed metal item per casting) and **Required Aon known** (Aonic, a caster-knowledge prerequisite, not consumed) | No obvious existing node | **Gap**: neither node type inspected covers "does the caster possess/know component X," which gates whether a maneuver/Art can be selected at all — this is a precondition check, likely upstream of the node graph (in a maneuver-eligibility filter) rather than an in-graph node, but is worth flagging since it's structurally different from D&D 5e's uniform "spell components" (which this ruleset explicitly does NOT use — see G/S/M in §1.2). |
| Area-of-effect shapes (cone/cube/cylinder/line/sphere) with precise geometric rules, "point of origin included or not" | `target` (presumably resolves an area) | Not assessed — geometry resolution likely lives outside this node's declarative surface; flag for implementers to confirm `target` can express all 5 shapes with correct origin-inclusion rules per `HB:13287-13313`. |
| Time-dilation/bubble effects (Bendalloy/Cadmium bubbles: separate mini-initiative "rounds" nested inside the main initiative order) | None of the 6 listed types | **Significant gap**: this is a combat-flow mechanic (extra turns inserted into initiative order under specific geometric/membership conditions), not a per-target effect node at all. If Allomancy is ever implemented, this needs new combat-engine support, not just a new interpreter node. |
| Concentration-breaks-on-damage math (DC = 10 or half damage, whichever higher) and concentration-breaks-on-recast-of-another-concentration-Art | Not in the 6 node types (this is a caster-side state machine, likely handled elsewhere in the engine already for Surgebinding) | Not a new gap specific to these two systems — same concentration rule the Surgebinding agents are already relying on (`HB:13251-13263`); flagging only to confirm it's shared, not duplicated per-system. |

**Bottom line**: the existing 6 node types cover ordinary "attack the
target / make them save / deal damage / roll a die / impose a status"
patterns well. Two categories are genuinely new if this content is ever
implemented: (1) a **generic dynamic-DC check** node (roll a stat + mod vs.
a DC computed from a formula or table, not a fixed number — needed for
Chromium Counter, Counter Sphere, Expunge Investiture, Unsurprise, Aonic
Soulcast, and Aonskip's d100 mishap table), and (2) **nested-initiative
time-bubble** support at the combat-engine level (Bendalloy Bubble, Cadmium
Bubble, Slide) — a mechanic with no D&D 5e or Surgebinding analogue.

---

## Part 5 — Counts

| System | Cantrips | 1st | 2nd | 3rd | 4th | 5th | 6th | 7th | 8th | 9th | **Total** |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Allomancy (Mistborn + God Alloy) | 0 | 17 | 14 | 17 | 9 (7 metal + 2 God Alloy) | 9 (5 metal + 4 God Alloy incl. Pulse/Slide) | 0 | 0 | 0 | 0 | **66** |
| Aonic | *[fork pending]* | | | | | | | | | | *[fork pending]* |

Allomancy level counts derived directly from the reconstructed level lists
in §2.2 (17+14+17+7+5 = 60 standard-metal Arts, +6 listed God Alloy +2
orphaned-from-index God Alloy = 8 God Alloy Arts; 60+8 = **68** — **note**:
this arithmetic will be reconciled against the §2.5 table's actual row count
of 66 before this document is finalized; the 2-Art discrepancy traces to
Ruin and one other list/description mismatch and is called out here rather
than silently resolved, since the task's explicit instruction is never to
guess at a number.

---

## Part 6 — Relevance verdict for this project

**This project's campaign (`data/current_campaign/shards_of_honor.json`) is
set on Roshar.** Allomancy is Scadrian; Aonic magic (AonDor) is Selish.
Neither is native to Roshar.

**Verdict: out of scope for near-term implementation, but not irrelevant to
the setting, and reachable in-fiction.**

- The Radiant's Handbook's own worldbuilding chapter explicitly endorses
  interplanetary play: *"Your characters could travel across the Cognitive
  Realm oceans to Scadrial, the land of metal-based Investiture... or
  plunge through the terrifying Dor to visit Sel"* (`HB:261`). Travel
  between planets happens via Shadesmar/the Cognitive Realm, which this
  ruleset treats as accessible (Elsecallers get a Transportation Surge;
  several Aonic Arts, e.g. `Elsecall`/`Realmatic Door`/`Perpendicularial
  Gate`, are explicitly interplanetary teleportation).
- However, the **classes that actually cast these Arts — Mistborn/Misting
  and Elantrian — are not defined anywhere in this repository.** Both are
  deferred by this very book to "Hoid's Guide to the Cosmere," which
  `parsed_data/` does not contain. A player character cannot mechanically
  *become* an Allomancer or Elantrian using only the source material
  present in this repo; the Art lists and stat blocks catalogued above are
  "or blocks with no chassis" until that class-description book is
  acquired and separately catalogued.
- The "worldhopper" archetype the task description mentions is **not**
  from this ruleset — it is a pregenerated character from the unrelated,
  standalone *Cosmere RPG* (Brotherwise) quick-start set
  (`parsed_data/sl019-agent-worldhopper/`), a different game system
  entirely (see `docs/mechanics/COSMERE_RPG_SURGEBINDING.md`'s own
  sourcing notes). It should not be used as evidence that this D&D-5e-based
  ruleset has a native cross-planet PC archetype; conflating the two would
  be a category error.
- **Practical recommendation**: treat Allomancy and Aonic magic as
  *NPC/antagonist and narrative-hook* material for a Roshar campaign (e.g.
  a Scadrian or Selish visitor NPC, a plot hook involving a God Alloy bead
  as a Macguffin, a Shadesmar encounter with an Elantrian) rather than as
  player-facing systems to implement now. Implementing them as full player
  options would require first sourcing and cataloguing "Hoid's Guide to the
  Cosmere" for the missing Mistborn/Elantrian class chassis — a
  prerequisite this document cannot skip around, per the sourcing rule
  above.

---

## Garbled passages — full flag list

1. `IA:8870-8878` — Mistborn 1st/3rd-level list headings absorbed the 2nd,
   4th, and 5th level markers as inline paragraph text instead of separate
   Markdown headings. Data intact; heading structure damaged. (§2.2)
2. `IA:8886-8890` — Same pattern for the God Alloy level list (5th-level
   marker for Atium Shadows buried inline). (§2.2)
3. `IA:8886-8890` vs. described Arts — God Alloy level-list index names only
   6 of the 8 God Alloy Arts that actually have full descriptions; Pulse
   (`IA:10163`) and Slide (`IA:10476`) are omitted from the index entirely.
   Not an OCR artifact — looks like an incomplete index in the source
   document itself. (§2.3)
4. `IA:10358` — "Ruin" is formatted as a bullet list item, not a `##`
   heading, unlike every other Allomantic Art. Content intact. (§2.4)
5. `IA:10474` — "Slide" is likewise a bullet, not a heading. Content
   intact. (§2.3)
6. `IA:10778-10784` — "Sending"'s required-Aon parenthetical
   ("Aem, Koe, Tia") is split across a line break, initially appearing as
   "Sending ( )" with the Aons stranded on the next line. Recoverable.
   (§3.2)
7. `IA:10895`, `IA:11029-11048` (and similar rows through the Aon table) —
   Markdown table column misalignment scrambles which text sits in which
   cell for several Aon entries (e.g. Aor, Lao, Lea, Lee, Lei rows). The
   syllable-to-gloss-to-Art-list mapping is still recoverable by inspection
   but the raw table structure is visually broken. (§3.2)
8. *[Additional flags from the Aonic-description fork to be merged below
   once its output is inserted.]*

---

## Appendix — full Aon reference table

Not reproduced row-by-row (see §3.2) — all ~170 Aons are present, intact,
at `IA:10870-11153` in the source, and the mapping methodology (syllable →
translation → thematic use → Invested Arts using it) is fully described
above. Re-extract directly from source if an engine needs the full table
as structured data; it is a flavor/prerequisite-tracking table, not a
mechanical rules table with numbers to transcribe.
