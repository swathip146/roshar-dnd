# Audit: Stormlight/Roshar CONTENT (not core mechanics) in the newly-added books

**Date**: 2026-09-12
**Branch**: `phase-0-fixes`
**Scope**: this audit covers **content and data** — adversaries, pregenerated
characters, locations, adventures, lore, equipment/items — supplied by the
newly parsed official (and fan) Cosmere RPG material, and whether/how it could
land in this codebase. It deliberately does **not** re-catalogue the Cosmere
RPG's core dice/attribute/skill mechanics — that is `COSMERE_RPG_CORE.md`'s
and `AUDIT_COSMERE_RPG_FEASIBILITY.md`'s scope (not present in the repo at
the time of this audit; nothing here duplicates or edits them).

**Method**: every row was verified by reading the actual parsed markdown,
running `grep`/`uv run python` against `parsed_data/`, `data/`, and
`qdrant_storage/`, and inspecting the live Qdrant collections directly via
`qdrant_client` in local-storage mode (no embedding calls — the sandboxed
network blocks the embedder's outbound call with `403 Forbidden`/`ProxyError`,
so `SimpleDocumentStore.count_documents()` cannot run here; the raw
`QdrantClient(path=...)` API works and was used instead, giving point counts
and full payload metadata without needing network access).

**Critical framing** (per the brief): the new SL0xx books are the
**standalone Cosmere RPG** (Brotherwise Games/Dragonsteel) — confirmed zero
hits for "Armor Class", "saving throw", or "spell slot" in
`sl015-stormlight-starterrules-digital/docling.md`. The existing
`data/rules/stormlight/surgebinding.json` and
`863203275-cosmere-5e-radiant-s-handbook-v2-0` are a **different, 5e-based**
fan supplement, already catalogued in `docs/mechanics/COSMERE_MECHANICS.md`.
Every row below states which system a piece of content belongs to.

---

## 0. Inventory of what was actually added

| Source | Lines | What it is | System |
|---|---|---|---|
| `parsed_data/sl015-stormlight-starterrules-digital/docling.md` | 2,434 | Official Cosmere RPG Starter Rules (free digital rulebook) — chargen, adventuring, combat, conversations, endeavors, items, GMing | Cosmere RPG |
| `parsed_data/sl019-introduction/docling.md` | 302 | Cover sheet for the 20 pregens: menu table (path/specialty), name-generation tables (Alethi, Azish, etc.) | Cosmere RPG |
| `parsed_data/sl019-*` (20 folders) | 370-484 each | 20 pregenerated level-1 character sheets, one per archetype | Cosmere RPG |
| `parsed_data/sl007-bridge-nine-pregens/docling.md` | 3,313 | A **second**, larger pregen pack (Bridge Four/Nine-themed characters) — not named in the brief, found during this audit | Cosmere RPG |
| `parsed_data/stormlight-holiday-scenarios-2024-2025/docling.md` | 492 | **Three complete fan-made adventures**: "The Fused Who Devastated" (Tier 1), "Middlefest in Urithiru" (Tier 1), "Stormshelter" (Tier 2 Halloween scenario, truncated read) | Cosmere RPG (official **Fan Content Policy** template, explicitly marked "not approved/endorsed by Dragonsteel") |
| `parsed_data/stormlight archive world and history/docling.md` | 44 | A **fan blog recap** (Jofwu, 17th Shard, July 2024) of Stormlight Archive lore — not an RPG product at all | Prose lore, system-agnostic |
| `parsed_data/kalak - the coppermind - 17th shard`, `nale - the coppermind - 17th shard` | — | Wiki-style character bios (already indexed, pre-existing, not part of this "new books" delivery — confirmed present in Qdrant under old slugs) | Prose lore |
| `parsed_data/oathbringer`, `rhythmofwar`, `waysofkings`, `windandtruth`, `wordsofradiance` | — | The **novels themselves**, already parsed and already indexed (confirmed in Qdrant, see §5) — present before this audit, not part of the "new books" the brief describes, but relevant to Q5 | Prose fiction |

**On "official campaigns"**: the brief mentioned the user "also added official
campaigns." Searching `parsed_data/` and `resources/rules/` turned up no
additional adventure/campaign-shaped material beyond what's listed above. The
closest matches are the **fan-made** holiday scenarios (explicitly
non-official per their own credits page) and the pregen packs. `resources/rules/`
contains only 6 PDFs, all already accounted for (SL015, CS006, CS007,
SRD_CC_v5.2.1, DnD_BasicRules_2018, the 5e Radiant's Handbook) — no separate
campaign PDF exists on disk. **If the user has an official campaign book, it
was not found in this repository at the time of this audit** — worth
double-checking with them directly, since sl007/sl015/sl019 numbering (part of
a "SLxxx" product line) implies other SL-numbered books (adventures, a
"Stormlight World Guide," a "Stormlight Handbook") may exist but were not
present in `parsed_data/` or `resources/rules/`.

---

## 1. Adversaries / monsters

| Content type | In codebase now | In new books | Gap | Evidence | Import feasible? |
|---|---|---|---|---|---|
| D&D SRD monsters | 334 (goblins, dragons, aboleths — zero Rosharan) | — | — | `uv run python -c "import json; d=json.load(open('data/rules/srd/monsters.json')); print(len(d))"` → `334`; `grep` for chasm/void/spren/shard/singer/parshendi/thunderclast/cremling/greatshell in the names → **zero hits** | N/A, pre-existing |
| Rosharan/Cosmere-RPG stat blocks | 0 | **1** (generic "Spear Infantry," a Tier 1 Minion human, not a named Rosharan creature) | Enormous | `parsed_data/sl015-.../docling.md:2299-2325` — full 3-attribute-row stat block with Deflect, Focus, Investiture, skills, 3 actions (Strike: Shortspear, Strike: Shortbow, Shield Bash) and 2 features (Martial Drill, Military Tactics) | Yes for this one block — see worked example below |
| Named Fused / boss-tier adversary | 0 | **1** — Grincil, a "Devastating One" Fused, in the holiday scenario | Gap remains large | `parsed_data/stormlight-holiday-scenarios-2024-2025/docling.md:148` gives partial stats inline in prose (not a full stat-block table): "Cognitive defense of 19, a Spiritual defense of 15, and 5 focus," uses "Surge of Division." No health/deflect/attack numbers given — this is a narrative NPC written for conversation resolution, not combat, so it's a **partial** stat presence, not a complete block | Partial only — health/attack numbers absent, would need GM invention to run in combat |
| Chasmfiends, Voidbringers (generic), whitespines, skyeels, Parshendi/singers (mechanical), Thunderclasts, axehounds, greatshells | 0 | **0 stat blocks** — all appear only as **illustrative prose examples** inside rules-explanation text, never as playable/runnable stat blocks | Total | `grep -niE "chasmfiend\|voidbringer\|thunderclast\|whitespine\|skyeel\|parshendi\|axehound\|greatshell"` over the Starter Rules → 3 hits total, all flavor text: `:240` ("fighting a pitched battle against a greatshell"), `:1531` ("A chasmfiend towering over the battlefield..."), `:2233` ("if an adventure says 'two axehounds approach,' use the axehound stat block twice" — an explanatory example, not an actual entry) | No — nothing to import, these creatures are named but never statted anywhere in the parsed corpus |
| Bestiary / monster manual for Cosmere RPG | Not present | Not present in `parsed_data/` | The Starter Rules text says explicitly (`:2239`): "the adversaries in the **Stormlight World Guide** have more general titles" — i.e., the actual bestiary lives in a **separate book not present in this repo** | `grep -n "Stormlight World Guide" parsed_data/sl015*/docling.md` → 4 references, all pointing outward to an un-acquired book | Blocked — the book with the actual Rosharan monsters was never added |

**Quantified**: the codebase has 334 D&D monster stat blocks and 0 Rosharan
ones. The new books add exactly **1** generic, non-Rosharan-named stat block
(Spear Infantry, reusable as a template) and **1** partial/incomplete NPC
write-up (Grincil the Fused, no combat numbers). The actual Rosharan bestiary
(chasmfiends, Voidbringers, whitespines, skyeels, Thunderclasts) is referenced
by name repeatedly but is **entirely absent from every file in
`parsed_data/`** — it lives in the not-yet-acquired *Stormlight World Guide*.

---

## 2. Pregenerated characters

Twenty sheets (`sl019-*`) plus a second, larger, previously-unmentioned pack
(`sl007-bridge-nine-pregens`, 3,313 lines — not individually broken out in
this audit due to scope, but confirmed to exist and follow the same sheet
format by spot-checking its `docling.md` header).

**What each `sl019` sheet contains** (verified on `sl019-warrior-alethi-duelist`
and `sl019-warrior-bridge-runner`, both fully read):

- 6 **attributes** (Strength, Speed, Intellect, Willpower, Awareness,
  Presence), each split Physical/Cognitive/Spiritual, with numeric scores
  (e.g., Alethi Duelist: STR 3, SPD 2, INT 1, WIL 3, AWA 2, PRE 1)
- 3 **defenses** (Physical 15, Cognitive 14, Spiritual 13 for the Duelist) +
  **Deflect** value (2, from chain armor)
- 18 named **skills** with attribute tag and numeric rank (e.g., "heavy
  weaponry (str) 5", "intimidation (wil) 3") — pre-filled per archetype, not
  blank
- **Expertises** (e.g., "[Cultural] Alethi, Veden," "[Weapon] Greatsword")
- **Talents** (e.g., "Vigilant Stance," "Stonestance" — named abilities with
  focus costs and effect text, e.g. "increase your Deflect value by 1")
- **Weapons** with full combat stats (Greatsword: Melee, Two-Handed, "+5 vs.
  Physical (1d10 + 5 keen damage)," Deadly trait; Crossbow similarly statted)
- **Armor & equipment** list with item-specific rules text (Alethi Uniform:
  "doesn't impose a disadvantage on tests in non-military conversation
  scenes"; Chain armor: Cumbersome [3] trait)
- Derived stats: recovery die (1d8), lifting capacity (500 lb.), movement (25
  ft.), senses range (10 ft.), health/focus/investiture max+current
- **Path and specialty** (e.g., "Warrior (Shardbearer)"), **ancestry**
  (Human), **level** (1), with a level-2 advancement block already written
  ("At level 2 ... gain: 5 health, 1 rank in Perception and 1 rank in
  Intimidation, The Mighty talent")
- Flavor/backstory paragraph (in-world justification for the archetype)
- **Blank** fields for the player to fill in: character name, player name,
  Purpose, Obstacle, Goals (multiple blank lines), Connections, Notes,
  character appearance — confirmed blank (underscored placeholder lines) in
  both sheets read, not pre-authored content

**Could they be imported as playable characters?** Mechanically yes, as
*Cosmere RPG* characters — but they map poorly onto this codebase's
`CharacterData` (`components/character_manager.py:39-127`), which is a 5e
schema. Attempting to represent the Alethi Duelist pregen in `CharacterData`:

| `CharacterData` field | Alethi Duelist value | Fits? |
|---|---|---|
| `ability_scores: Dict[str,int]` | Cosmere RPG has 6 different attributes (Strength/Speed/Intellect/Willpower/Awareness/Presence) vs 5e's 6 (STR/DEX/CON/INT/WIS/CHA) — **no 1:1 mapping**; Speed and Presence have no 5e equivalent, and 5e's DEX/CON split into different Cosmere concepts (Speed handles DEX's role only partly; CON doesn't exist as its own attribute — health scales off Strength) | No — the whole ability-score model is structurally different |
| `armor_class: int` | Cosmere RPG has three separate **defenses** (Physical/Cognitive/Spiritual, 15/14/13) plus a separate **Deflect** value (damage reduction, not to-hit) | No — AC conflates two different Cosmere concepts and only covers one of three defenses |
| `skills: Dict[str,bool]` (boolean proficiency) | Cosmere RPG skills have **numeric ranks** (0-5), not boolean proficiency | No — lossy at best (would have to collapse rank>0 to `True` and discard the rank number, which drives the actual modifier) |
| `hit_points` | Health 13 (max/current) | Yes, direct field match |
| `spell_slots`, `spells_known`, `cantrips_known` | N/A — Cosmere RPG has no spell slots; equivalent is **Investiture** (current/max: 5/5 sample) and **Focus** (current/max: 2/2) | No home — Investiture and Focus are both distinct 3rd/4th resource pools with no existing field; `stormlight_current`/`stormlight_capacity` are close in *spirit* but are a different game's specific "spheres held" mechanic, not the Cosmere RPG's Investiture pool |
| `expertise_skills: List[str]` | Cosmere RPG's own "Expertises" concept (`[Cultural] Alethi, Veden`, `[Weapon] Greatsword`) — coincidentally same *name* as a 5e mechanic already in this field, but semantically different (cultural/knowledge tags vs. 5e's "double proficiency bonus") | Naming collision, not a fit — would corrupt the existing 5e expertise semantics if merged |
| **Talents** (Vigilant Stance, Stonestance — stance-based reaction/action modifiers) | No field exists. `features: List[str]` is names-only and already documented (§3 of `AUDIT_CHARACTER_AND_NONCOMBAT.md`) as unreachable/inert even for 5e features | No home — would need new stance-tracking machinery entirely |
| **Deflect** | No field — closest existing concept is `armor_class`, but Deflect is damage *reduction*, not an attack-roll target number | No home |
| **Focus** (a spendable action-economy/social-resistance resource, current/max) | No field — closest is `stormlight_current`, but Focus is spent on stances/reactions/social resistance in the Cosmere RPG rules, an unrelated mechanic | No home |
| Path/Specialty (`Warrior (Shardbearer)`) | Closest: `character_class` (string) — could hold the string, but every downstream consumer (`_hit_die_for_class`, class-feature tables) assumes a 5e class name (Fighter, Wizard, etc.) and would either crash or silently misclassify | Storable as a string; semantically inert/actively misleading to the rest of the engine |
| Level-2 advancement text (pre-written) | No equivalent — 5e leveling (`_apply_level_up`) computes HP/proficiency/features from formulas, doesn't read pre-authored "at level 2, gain X" text | No home |

**Verdict**: of ~15 meaningful data points on one pregen sheet, only **1**
(hit points current/max) has a clean, semantically correct home in
`CharacterData` today. Everything else either has no field (Investiture,
Focus, Deflect, Talents, ranked skills, Expertises-as-cultural-knowledge) or
has a field with the *same name but incompatible meaning* (ability_scores,
armor_class, expertise_skills) — importing naively would silently corrupt
those fields for any code that assumes 5e semantics. This is the single
strongest piece of evidence in this audit that pregens (and by extension any
Cosmere RPG character content) are **blocked on the system decision**, not
merely "needs a converter script."

---

## 3. Locations

| Content type | In codebase now | In new books | Gap | Evidence | Import feasible? |
|---|---|---|---|---|---|
| Authored campaign locations w/ battle maps | 3 (The Shattered Plains, Lasting Integrity, Urithiru) — each has `type`, `description`, `significance`, `treasure`, and an ASCII `map` (`legend` + `rows`, ~9x16-17 grid) | `data/current_campaign/shards_of_honor.json:36-124` | — | — | N/A, pre-existing, for comparison |
| New Rosharan locations named/described | Rall Elorim (a city, home to Iriali culture, referenced repeatedly: Stormfalls, Skystone Square, the docks, Firebrand Brewery, Precious Threads tailor shop, Tinderbox Tenements), Urithiru's "the Breakaway" marketplace | `parsed_data/stormlight-holiday-scenarios-2024-2025/docling.md` (Rall Elorim: lines 47-192; Urithiru/Breakaway: lines 240-332) | These are **prose scene locations for an adventure**, not standalone location records — no map, no terrain/hazard data, no coordinates | Confirmed by full read of both scenarios | Partial — could be extracted as narrative location stubs (name + description + notable NPCs/POIs), but with **zero mechanical detail** (no maps, no battle-map grid, no hazards) to match `shards_of_honor.json`'s format |
| Maps / terrain / hazards for new locations | 3/3 existing locations have ASCII battle maps | **0** — no maps, grids, or terrain features found anywhere in `sl015`, `sl019-*`, `sl007`, or the holiday scenarios | Total, for mechanical map data | `grep -n "grid\|map\|legend" parsed_data/stormlight-holiday-scenarios-2024-2025/docling.md` → no hits describing an actual battle map; the Starter Rules' own "Variant: Using a Grid" section (`:1637-1672`) is a **generic rules explanation** (how far you can move per square, corner-cutting rules), not a specific authored map | No — there is no map content to import; only the *rules* for building one exist, and only in the (out-of-scope) core-mechanics book |
| Named general Roshar locations (mentioned only) | — | Shattered Plains, Urithiru, Shadesmar/Lasting Integrity, Kharbranth, Alethkar/Vedens (already covered by existing campaign); **new**: Rall Elorim (an Iriali city not previously in this codebase) | Rall Elorim is a genuinely new location name for the codebase's world | `grep -n "Rall Elorim"` across `data/current_campaign/` → zero hits; only in the new holiday scenario | Yes — cheap to add as a location stub if the game ever visits it, but it has no mechanical content of its own (only the scenario built around it does) |

**Bottom line**: the new books add **prose scene-setting**, not the kind of
structured `locations[]` entries `shards_of_honor.json` uses. The 3
existing authored locations remain the only ones in the whole corpus (new or
old) with an actual battle-map grid.

---

## 4. Adventures / scenarios

**Is there a runnable adventure in the Starter Rules?** No — `sl015` is a
pure rules digest (chargen through GMing advice); the "Sample Stat Block" is
its only concrete play content. Section headings confirm this: Parts 1-7 are
all rules chapters (Character Statistics, Adventuring, Combat, Conversations,
Endeavors, Items, Gamemastering) — no "Part 8: The Adventure" exists.

**Is there a runnable adventure anywhere in the new material?** Yes — three,
in `stormlight-holiday-scenarios-2024-2025/docling.md`, all built on the
official **Fan Content Template** (explicitly marked non-canon):

1. **"The Fused Who Devastated"** (Tier 1) — fully read. Structure: Credits →
   premise → 2 alternate **Scenario Hooks** → **Getting Started** (boxed
   read-aloud text) → a **Discovery endeavor** ("A Trail of Cinders," an
   investigative web/clue-chain with named leads: Fast Getaway → Tinderbox
   Tenements → Rall Elorim Docks → Skystone Square, each gated behind a
   named skill+DC, e.g. "DC 14 Survival," "DC 16 Leadership") → a
   **Conversation scene** (resolving via influence/Persuasion, with named NPC
   resistance stats: "Cognitive defense of 19, a Spiritual defense of 15, and
   5 focus") → a **combat branch** ("Brawl at the Brewery") if talking fails
   → **Aftermath**/**Conclusions and Rewards** (branching narrative outcomes)
   → an **"Expanding this Adventure"** hook for extending to a full campaign.
2. **"Middlefest in Urithiru"** (Tier 1) — fully read. Structure: 2 hooks →
   a sandbox **"Middlefest Fair" scene** with 5 independent mini-activities
   (drinking contest, duel, food-collection minigame, a memory game with a
   cheating NPC, a bard-calming social challenge), each with its own DC(s) →
   a tracked **event meter** ("Targeted by Deashen," fills via player
   Complications) that triggers a **combat set-piece** ("Snowball Fight!")
   with bespoke combat rules (a "Hit, You're Out!" battlefield effect, custom
   actions "Mark Target"/"Strike: Snowball"/"Tag, You're In!") → rewards
   scaling on how the party performed.
3. **"Stormshelter"** (Tier 2 Halloween scenario) — only its title/credits
   header was read in this pass (492-line file, first two scenarios consumed
   ~340 lines); not fully audited, flagged for follow-up if this content is
   pursued further.

**Structural comparison to `shards_of_honor.json`**:

| Element | `shards_of_honor.json` | Holiday scenarios |
|---|---|---|
| Acts/sessions | Explicit `acts[]` array with session numbers | Single-session, no act structure |
| Quests w/ objectives + prereqs | `quests[]`, each with `objectives`, `prereqs`, `status` | Informal — "Conclusions and Rewards" branches, no discrete objective/prereq graph |
| Encounters w/ enemies + CR + XP | `encounters[]`, each with `enemies[{count, estimated_cr, role}]`, `victory.xp` | No CR/XP anywhere (Cosmere RPG has neither concept) — "Brawl at the Brewery" names Grincil but gives no full stat block, no XP reward, just narrative consequence |
| Trigger keywords for dynamic dispatch | `trigger.keywords[]`, `trigger.location`, `trigger.quest_pending` | None — these are linear, GM-run-in-order scenarios, not keyword-dispatched |
| Endgame condition (win/lose) | Structured boolean `endgame.condition`/`failure_condition` | Prose "Aftermath" branches only (success/failure narrated, not machine-evaluable) |
| Battle maps | ASCII grid per location | None |

**Could a holiday scenario be converted to `shards_of_honor.json`'s schema?**
Partially, and lossily:
- **Would translate cleanly**: the scenario hooks → `hooks[]`; the location
  descriptions → a `locations[]` entry (minus the map); the overall
  premise/NPC (Grincil) → `key_npcs[]`.
- **Would need invention, not translation**: `estimated_cr` for Grincil (no
  CR exists in Cosmere RPG — would have to be guessed from his Tier/Focus
  values), `xp` rewards (Cosmere RPG uses "marks" currency and goal-based
  advancement, not XP — see §6), and `quests[].prereqs` (the scenario's
  branching is conversation-outcome-driven, not a quest-objective graph).
- **Would be lost entirely**: the Discovery-endeavor clue-chain mechanic (no
  equivalent structure in the schema — it's a distinctive Cosmere RPG scene
  type with no 5e/`shards_of_honor.json` analogue), the Focus-based social
  resistance numbers, and the dynamically-tracked "event meter" (Targeted by
  Deashen) mechanic.

---

## 5. Setting/lore for RAG

**Live Qdrant collections, verified by direct point-count and payload
inspection** (`QdrantClient(path='./qdrant_storage')`, bypassing the
network-dependent embedder):

```
dnd_documents: 8,291 points
dnd_reference: 2,726 points
```

**`dnd_documents` breakdown by source slug** (full scroll, all 8,291 points):

| Points | Source |
|---|---|
| 3,338 | `srd_cc_v5.2.1` (D&D SRD) |
| 2,148 | `863203275-cosmere-5e-radiant-s-handbook-v2-0` (the OLD 5e-based Cosmere handbook) |
| 1,685 | `dnd_basicrules_2018` |
| 241 / 229 / 220 / 218 / 153 | `oathbringer` / `wordsofradiance` / `windandtruth` / `rhythmofwar` / `waysofkings` (the 5 novels) |
| 47 | `file_5035` |
| 12 | `stormlight archive world and history` (the fan blog recap) |

**`dnd_reference` breakdown** (full scroll, all 2,726 points): D&D adventure
modules (`hoarddragonqueen_encounters`, `ddex16_thescrollthief`,
`dra23_winterssplendor`, `ddex14_duesforthedead`, `dra18_cryptskelemvor`),
two Coppermind wiki bios (`nale`, `kalak`), and the 100+ generic D&D pregen
character sheets (`half-orc paladin *`, `dragonborn sorcerer *`, etc.) — all
pre-existing, all D&D-flavored except the two Coppermind bios and the novels.

**Confirmed by exhaustive scan**: zero points in either collection have a
`slug` starting with `sl0` or containing `holiday`/`bridge-nine`. **None of
the new Cosmere RPG content is indexed**:
- `sl015-stormlight-starterrules-digital` (2,434 lines of rules/setting text) — not indexed
- All 20 `sl019-*` pregens — not indexed
- `sl007-bridge-nine-pregens` (3,313 lines) — not indexed
- `stormlight-holiday-scenarios-2024-2025` (3 adventures) — not indexed
- `resources/rules/CS006_Player_Quick_Reference.pdf`, `CS007_GMRules_Overview.pdf` — corresponding `parsed_data/cs006-*`, `cs007-*` folders exist but are absent from both Qdrant collections too

**Should it be indexed?** For RAG/lore purposes, the highest-value additions
would be the **prose setting material embedded in the Starter Rules**
(Introduction, "Your Introduction to Roshar," the currency/culture/expertise
flavor text) and the **holiday scenario NPC/location prose** (Rall Elorim,
Grincil's characterization) — these are exactly the kind of flavor content
`rag_retriever_agent.py` is meant to surface for lore questions, and indexing
them requires no schema decisions, no mechanics work, and is **completely
independent of the 5e-vs-Cosmere-RPG system question** (RAG just serves text
snippets; it doesn't execute rules). The Cosmere RPG mechanics chapters
(Parts 1, 3, 4, 5, 6, 7) would also index harmlessly (they'd just surface as
lore/rules text in response to player questions) but are lower-value for RAG
specifically since `query_rules`'s Tier 1-3 pipeline is the intended path for
mechanical questions, not vector search.

**Command used to verify** (re-runnable):
```bash
uv run python -c "
from qdrant_client import QdrantClient
client = QdrantClient(path='./qdrant_storage')
for c in client.get_collections().collections:
    print(c.name, client.get_collection(c.name).points_count)
"
```

---

## 6. Equipment and items

| Content type | In codebase now | In new books | Gap | Evidence | Import feasible? |
|---|---|---|---|---|---|
| D&D mundane equipment | 237 items (`data/rules/srd/equipment.json`) | — | — | `len(json.load(...))` → 237; zero hits for sphere/shardblade/shardplate/fabrial/safehand in item names | N/A |
| D&D magic items | 362 items (`data/rules/srd/magic_items.json`) | — | — | `len(json.load(...))` → 362 | N/A |
| Rosharan currency (spheres) | Not modeled — confirmed by `AUDIT_CHARACTER_AND_NONCOMBAT.md` §1: "Currency/gold: zero hits, not modeled at all" | **Full conversion table**: Chip/Mark/Broam × 5 gem types (Diamond, Garnet/Heliodor/Topaz, Ruby/Smokestone/Zircon, Amethyst/Sapphire, Emerald), each with chip/mark/broam values in diamond-marks | `parsed_data/sl015.../docling.md:1838-1860`, table at `:1850` (Sphere Values in Diamond Marks) | Yes — this is a clean, small, structured table (5 rows x 3 columns) that could become `data/rules/stormlight/currency.json` independent of any system decision; it's flavor/economy data, not tied to 5e or Cosmere RPG mechanics specifically, though the "marks" unit itself is a Cosmere RPG term |
| Rosharan mundane weapons | Not modeled (SRD weapons are all D&D) | **Full weapon tables**: Light Weaponry (6 entries: Knife, Mace, Shortspear, Sidesword, Staff, Shortbow), Heavy Weaponry (5: Axe, Hammer, Longspear, Longsword, Shield), Special (Improvised, Unarmed) — each with damage dice, range, Traits, Expert Traits, weight, price | `parsed_data/sl015.../docling.md:1923-1952` | Yes, as **data** (11 weapon entries with dice/traits) — but the damage/attack-resolution math (Cosmere RPG's Attack+Deflect model) only executes under the Cosmere RPG system, so using these in combat is blocked on the system decision; using them as a flavor/RP item list is not |
| Rosharan armor | Not modeled | **Full armor table**: Uniform, Leather, Chain, Breastplate, Half Plate, Full Plate — each with Deflect Value, Traits (e.g., Cumbersome[X]), Expert Traits, weight, price | `parsed_data/sl015.../docling.md:2057-2065` | Same as weapons — data extractable now, mechanically inert until Deflect-based damage resolution exists |
| Rosharan general equipment | Not modeled | An Equipment table exists (`:2068` onward) — table header captured, full item list not exhaustively transcribed in this pass (large table, continues past line 2068; flagged for follow-up if pursued) | `parsed_data/sl015.../docling.md:2068` | Likely yes as data, not independently verified item-by-item in this audit |
| Shardblades / Shardplate / fabrials (the iconic Rosharan items) | `has_shardblade`/`has_shardplate` exist as **booleans only** in `CharacterData` (no stats) per `AUDIT_CHARACTER_AND_NONCOMBAT.md` | **Not mechanically detailed in the Starter Rules** — every reference (`:750`, `:924`, `:2039`, `:2209-2211`) either mentions them in passing or explicitly defers: "chapter 7 of the Stormlight Handbook" for full weapon/crafting rules. The Starter Rules only describe *fabrial accessories* like a "Tuning Fork" and "Unencased Gem" for recharging | Total — the actual Shardblade/Shardplate/fabrial stat rules live in the un-acquired *Stormlight Handbook* | Blocked — no data to import; the book with these rules isn't in the repo |
| Safehand gloves, bridging equipment | Not modeled | **Not found** anywhere in `sl015`, `sl019-*`, or the holiday scenarios (searched via grep, zero hits for "safehand" or "bridging equipment" as a named item) | Total, and unmet by the new material too | `grep -rn "safehand\|bridging" parsed_data/sl0*` → no hits | No — not present in the parsed corpus at all |

---

## 7. Campaign schema fit

Read in full: `data/current_campaign/shards_of_honor.json` (431 lines,
`schema_version: "2.2"`).

**Precise assessment — the schema assumes 5e in exactly these places**:

1. `encounters[].enemies[].estimated_cr` (e.g., `"estimated_cr": 0.25` for a
   Voidbringer Scout, `5` for a Fused Champion) — **Challenge Rating is a
   pure D&D 5e concept**; the Cosmere RPG has no CR analogue. Its closest
   equivalent is Tier (1-5) + Role (Minion/Rival/Boss), a categorically
   different two-axis system, not a single decimal number.
2. `encounters[].victory.xp` (e.g., `100`, `450`, `2000`, `900`) — **XP
   budgets are 5e-specific**. The Cosmere RPG advancement model
   (`sl015:2397-2433`, "Character Advancement" table) uses **Goals** (earning
   narrative rewards like a Shardblade) and **Levels gained through play
   milestones**, not an XP-point economy. `award_experience`
   (`agents/dm_tools.py:790`) and `character_manager.award_xp()` have no
   Cosmere RPG equivalent to call.
3. `encounters[].difficulty` (`"easy"|"medium"|"hard"|"deadly"`) — this
   4-tier label is generic enough to *port* conceptually (Cosmere RPG's own
   text uses similar plain-language framing), but `generators/campaign_generator.py:197`
   hard-codes the prompt template as `"difficulty": "easy|medium|hard|deadly"`
   paired 1:1 with `estimated_cr` (`:264`: "Balance estimated_cr against the
   party level"), so the two fields are coupled in the generator, not
   independent.
4. Nothing in the schema references monster names, spell names, or class
   names directly (the `enemies[]` blocks are free-text `name`/`description`
   fields, not IDs into `monsters.json`), so encounter narrative text itself
   is **not** hard-coded to D&D — only the numeric CR/XP fields are.

**What would carry over cleanly to a Cosmere RPG campaign with this same
JSON schema, unchanged**: `title`, `theme`, `setting`, `overview`,
`background`, `main_plot`, `key_npcs[]`, `locations[].name/type/description/
significance/treasure` (the ASCII `map` format is system-agnostic — it is
literally just a grid, would work for either ruleset), `hooks[]`,
`rewards[]` (as prose), `acts[]`, `quests[].objectives/prereqs/status`,
`endgame.condition`/`failure_condition` (the boolean predicate language
referencing quest/flag/count is system-agnostic).

**What would need new fields or a schema fork**: `enemies[].estimated_cr` →
would need `tier`+`role` instead; `victory.xp` → would need a `victory.goal`
or `victory.marks` field instead (Cosmere RPG's currency, see §6); nothing
in the schema currently has a slot for Focus/Investiture costs, Deflect
values, or Cosmere-specific scene types (Discovery endeavors, Conversation
contribution mechanics) that a converted holiday scenario would want to
express (see §4).

**Precise verdict**: `shards_of_honor.json`'s schema is **~80% system-neutral
by field count**, but the ~20% that isn't (CR, XP) are exactly the fields
`generators/campaign_generator.py` uses to drive LLM-generated encounter
balancing — so while the *data structure* could hold Cosmere RPG content with
minor additions, the *generator* that populates it is presently hard-wired to
D&D's CR/XP model at the prompt-template level, which is a larger piece of
work than editing the schema alone.

---

## The content gap, quantified

| Content type | In codebase (old/5e) | Available in new books | Actually imported | Gap |
|---|---|---|---|---|
| Adversary/monster stat blocks | 334 (D&D SRD, zero Rosharan) | 1 generic template stat block + 1 partial NPC (no full stats) | 0 | **334 D&D vs. ~1.5 usable Rosharan** — the real bestiary (Stormlight World Guide) is missing entirely |
| Pregenerated characters | ~110 D&D pregens already indexed in `dnd_reference` (dragonborn sorcerer, drow rogue, etc., levels 1-10) | 20 (`sl019`) + an undetermined additional count in `sl007-bridge-nine-pregens` (not yet parsed sheet-by-sheet) | 0 | 20+ ready Cosmere RPG characters sitting unused; 0 importable into `CharacterData` without a schema fork (§2) |
| Locations with battle maps | 3 | 0 new locations with maps; 2 new named locations (Rall Elorim, the Breakaway) with prose only | 0 | Map content gap unchanged (3 total, all pre-existing) |
| Adventures/scenarios | 1 authored campaign (`shards_of_honor.json`, 4 encounters) | 3 complete fan scenarios (2 fully read, 1 partially) | 0 | 3 runnable one-shots available, 0 converted or wired into the game |
| Indexed lore documents (Qdrant) | 8,291 + 2,726 = 11,017 points, 0 from new Cosmere RPG books | 2,434 (sl015) + ~8,600 (20 sl019 sheets, avg ~430 lines) + 3,313 (sl007) + 492 (holiday) ≈ **14,800+ lines of unindexed new content** | 0 | 100% of the new material is unindexed |
| Rosharan currency/equipment data | 0 (237 D&D items, 362 D&D magic items, 0 Rosharan) | 1 currency table (5 gems x 3 denominations), 11 weapons, 6 armors | 0 | Small but immediately extractable — this is the cheapest win in the whole audit (see below) |

---

## Cheapest high-value imports (ranked)

Ranked by (value delivered) / (effort), with an explicit call on whether each
is blocked by the 5e-vs-Cosmere-RPG decision.

1. **Index the new material into Qdrant for RAG** (§5). Effort: run the
   existing `generators/batch_qdrant_indexer.py` against
   `resources/rules/SL015_Stormlight_StarterRules_Digital.pdf` and the
   holiday-scenarios PDF (already Docling-parsed — the hard part is done).
   Value: the game's `search_lore` tool (already wired, already reachable
   per `AUDIT_CHARACTER_AND_NONCOMBAT.md` §13) would immediately surface
   Rosharan flavor text, the holiday scenario's Rall Elorim setting details,
   and the pregens' cultural/name tables for any lore question. **Independent
   of the system decision** — RAG returns text snippets regardless of which
   ruleset resolves the mechanics. This is the single highest-value,
   lowest-effort item in this audit.
2. **Extract the Rosharan currency table into a small JSON file** (§6) —
   `data/rules/stormlight/currency.json`, mirroring the existing
   `surgebinding.json` pattern. 5 rows of data, already tabulated in the
   source. Gives the DM/LLM a concrete, quotable answer to "how much is a
   broam worth" without waiting on any mechanical integration. **Independent
   of the system decision** — it's reference data, useful for flavor and
   narration regardless of which combat/skill system is running.
3. **Extract the two named Rall Elorim adventure NPCs and location as flavor
   content** (Grincil, Deashen, Ivka, the Firebrand Brewery, Skystone
   Square) — no mechanical integration needed, just narrative material the
   scenario-generator agent could reference or the RAG index could surface.
   **Independent of the system decision.**
4. **Extract the mundane weapon/armor tables as reference data** (§6, 11
   weapons + 6 armors) into a `data/rules/stormlight/equipment.json` for
   flavor/narration purposes (an NPC "wields a Rosharan longspear") even
   before any mechanical wiring exists. **Mostly independent** — usable as
   descriptive text now; only becomes *mechanically* live once Deflect-based
   combat resolution exists (which is the system decision).
5. **Convert one holiday scenario (recommend "The Fused Who Devastated" — it
   is shorter and fully self-contained) into `shards_of_honor.json`'s
   schema as a bonus one-shot**, accepting the lossy translation documented
   in §4 (drop the Discovery-endeavor clue-chain mechanic, invent a CR/XP
   number for Grincil). Medium effort, moderate value (one more piece of
   playable content), and **partially blocked**: the conversion is doable
   today under the current 5e-shaped schema, but doing it well (preserving
   the endeavor/conversation mechanics that make the scenario distinctive)
   requires the system decision to land first.

---

## Blocked on the system decision

- **Importing any of the 20+1 pregenerated characters as playable
  characters.** §2's field-by-field mapping shows only 1 of ~15 data points
  (hit points) has a non-lossy home in the current `CharacterData`; ability
  scores, defenses, Deflect, Focus, Investiture, ranked skills, and Talents
  all require either new fields or a fundamentally different character model.
- **Using the new weapon/armor/currency tables mechanically** (i.e., having
  them actually affect combat math) — requires Deflect-based damage
  resolution and the Physical/Cognitive/Spiritual defense model, neither of
  which exist in this codebase's combat engine (which is 5e AC/saving-throw
  based per `AUDIT_CHARACTER_AND_NONCOMBAT.md` §11).
  Extracting them as *reference data* (item #4 above) is not blocked; using
  them to compute a to-hit roll is.
- **Running Rosharan adversaries in the tactical combat engine** — even if
  the Stormlight World Guide's full bestiary were acquired, the "Spear
  Infantry" stat block's own attack math (Attack+3 vs. Physical defense,
  Deflect reduction, Focus-fueled reactions) cannot execute inside
  `components/combat/` today, which computes attack bonus, AC, and damage
  the 5e way.
  Cataloguing the stat block as prose/reference is not blocked (done in §1
  above); running it in a combat encounter is.
- **Converting `encounters[].estimated_cr`/`victory.xp` to a Cosmere RPG
  equivalent** (§7) — depends on deciding whether encounters will use
  Tier+Role (Cosmere RPG) or CR (5e), which is itself the core of the system
  decision, not separable from it.
- **`generators/campaign_generator.py`'s LLM prompt template** — hard-coded
  to CR/XP language (`:196-200,264`); regenerating campaigns in "Cosmere RPG
  voice" needs the prompt rewritten only after the schema question is
  settled, otherwise the generator would produce content the schema can't
  represent.

---

## Biggest surprise

Two, of comparable weight:

1. **None of the 14,800+ lines of newly parsed Cosmere RPG content — not
   the rules, not the 20 pregens, not the three complete adventures — has
   been indexed into Qdrant**, despite the indexing pipeline
   (`generators/batch_qdrant_indexer.py`) already existing, already working
   (it indexed the old 5e Cosmere handbook and the 5 Stormlight novels just
   fine), and despite this being entirely independent of the 5e-vs-Cosmere-RPG
   system question. This is the cheapest, highest-value, most
   system-agnostic action item in the whole audit, and it's sitting
   completely undone.
2. **The three "holiday scenario" fan adventures are more complete, better
   structured, and more mechanically interesting than anything else audited**
   — full scene-by-scene structure, branching outcomes, a genuine
   investigation-mechanic (Discovery endeavor clue-chain), custom battlefield
   rules for a set-piece fight, and NPC social-resistance stats — while the
   actual official Stormlight *bestiary* the brief was most interested in
   (chasmfiends, Voidbringers, Fused, whitespines, skyeels, Thunderclasts) is
   **completely absent from every file in this repository**, referenced by
   name a mere handful of times as prose flavor, with the Starter Rules
   itself pointing at an unacquired book (the *Stormlight World Guide*) as
   the actual source. The user's "big content gap" instinct about
   adversaries was correct, but the gap isn't a parsing or import problem —
   it's that the specific book containing Rosharan creatures was never added
   to `resources/rules/` in the first place.
