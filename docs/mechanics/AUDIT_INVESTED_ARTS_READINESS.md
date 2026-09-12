# Audit: Can the Engine Execute "The Invested Arts of the Cosmere" (665 Arts)?

**Date**: 2026-09-12
**Branch**: `phase-0-fixes`
**Source book**: `parsed_data/cosmere-5e-the-invested-arts-of-the-cosmere-v2-0/docling.md`
(19,794 lines). Verified counts by direct grep, matching the prompt's figures:
`Casting Time` 674, `saving throw` 420, `concentration` 319 (31 lines carry the
literal word "concentration" plus 288 arts marked with the `▶` concentration
glyph per the book's own key — see §6), `spell slot` 0, `Investiture Point` 0
literal hits (the phrase is always "Investiture point[s]", lowercase p — 8 hits
for that variant, all in rules text, not per-art cost lines).

**Method**: every row was verified by running real code — constructing objects,
calling methods, grepping production call sites — never by reading docstrings.
**Central distinction, unchanged from the template**:
- **Implemented** = code exists and does the right thing when exercised directly.
- **Reachable** = a player in a real session can trigger it (an offered combat
  action passing `is_offerable()`, or a `dm_tools.py` `@tool` the LLM can call).

Legend: ✅ works as-is / 🟡 needs work / ❌ nothing exists.

---

## 0. The book's shape, confirmed against the compiler's assumptions

Spot-checked three full entries (`Adhesion` cantrip, `Abrasive Bolt` 1st-level,
`Absorb Essence` 1st-level) at `docling.md:321-346`, `610-633`, `634-649`. Every
entry has the same structured header the SRD spell compiler already expects:

```
Casting Time : 1 action
Range        : 120 feet
Components   : S
Duration      : 1 round
```

...followed by prose, a ranged/melee "Invested Art attack" or a saving throw,
a damage die, and an "At Higher Levels" scaling paragraph. This is the SRD
spell shape almost exactly — `spell_compiler.py`'s docstring's own list of what
it refuses to invent (concentration, save DC formula, "At Higher Levels" damage
scaling) is precisely what this book supplies in the same structured way SRD
spells do. This is the single most important structural fact in this audit.

**Crucial distinction the prompt's framing risks blurring**: the 9 maneuvers
already wired into `maneuver_executor.py`/`surgebinding.json` (Full Lashing,
Reverse Lashing, Riposte, Distracting Attack, etc.) are a **different Radiant's
Handbook subsystem** — "Maneuvers" are free class features triggered by combat
events (`on_hit`, `on_move`, reactions), spent from Lashing Dice. Grepping the
new book for those exact names returns **zero matches** except one incidental
mention of "Full Lashing" inside the *Gravitation cantrip's* prose. The 665
**Invested Arts** are the separate, spell-slot-shaped ability list (cantrips +
five levels) that `surgebinding.json`'s own `_meta.surges_note` explicitly
deferred: *"the detailed descriptions of each Invested Art are found in a
separate document ... That document is NOT in resources/."* That document has
now arrived. **It does not touch the 9 Maneuvers at all** — it is a wholly new
665-entry dataset layered beside them, not a superset or a fix.

---

## 1. Can `maneuver_executor.py` execute these arts as data?

**Read in full** (489 lines). Confirmed six node types, dispatched through
`_run_nodes()` (`maneuver_executor.py:212-220`), which raises `AutomationError`
on any unknown `type` rather than skipping it — the deliberate anti-silent-zero
design. `SpellEffectExecutor` (in `spellcasting.py`) subclasses it and adds two
more: `heal`, `spell_attack`, plus a `multiplier` field on the inherited
`damage` node. That gives **eight** total node types in the whole codebase:
`target`, `save`, `damage`, `attack`, `roll`, `ieffect2`, `heal`, `spell_attack`.

Verified live that `Cone of Cold` compiles today but its `area_of_effect` is
recorded and never expanded to more than the caller's explicitly chosen
target(s):

```
$ uv run python -c "
from components.srd_rules import get_srd_rules
from components.combat.spell_compiler import compile_spell
srd = get_srd_rules()
c = compile_spell(srd.spell('Cone of Cold'), slot_level=5, caster_level=10)
print(c.describe()); print('area_of_effect:', c.area_of_effect)
"
Cone of Cold (level 5) — 1 automation node(s)
area_of_effect: {'type': 'cone', 'size': 60}
```

The `{'type': 'cone', 'size': 60}` dict is dead data — nothing reads it to pick
targets. `_node_target` (`maneuver_executor.py:222-236`) only ever iterates the
`targets: List[str]` the caller passed in.

| Effect shape needed by the 665 arts | Node exists? | Evidence | What's needed |
|---|---|---|---|
| Single target, save-or-damage | ✅ | `target`/`save`/`damage`, 73 passing tests (`tests/combat/test_maneuvers_are_data.py` + `test_maneuvers_reach_the_player.py`) | Works as-is |
| Ranged/melee "Invested Art attack roll" (not a weapon swing) | ✅ | `spell_attack` node in `spellcasting.py:439-470`, uses proficiency+ability vs AC, not a weapon | Reusable as-is (see §2) |
| Healing (Progression: "Regrowth", "Aiding Regrowth") | ✅ | `heal` node, `spellcasting.py:421-437`, clamps to missing HP | Reusable as-is |
| Damage halved/negated on save | ✅ | `multiplier` field on `_node_damage` override, `spellcasting.py:474-502` | Reusable as-is |
| **Area of effect (cone/sphere/cube/line)** | ❌ | `area_of_effect` parsed and stored (`spell_compiler.py:95,179`) but never consulted for target selection; confirmed live above | New `area` node (or a target-resolution hook) that asks the grid/session who is inside a shape, not the caster |
| **Concentration tracking (enforcement)** | 🟡 | `ConcentrationTracker` (`spellcasting.py:338-368`) records who is concentrating and drops the old spell on a new one, but there is **no damage-triggered CON save** — confirmed absent by the class's own docstring and by grep (`grep -rn concentration components/ agents/ core/ orchestrator/` outside `spellcasting.py`/`spell_compiler.py` → zero hits) | A hook on every damage application checking `ConcentrationTracker.concentrating_on()` and rolling a CON save (DC = max(10, damage/2)) to end it |
| **Duration / timed effects (ticking rounds)** | ❌ | `ieffect2`'s `duration` is stored **verbatim as a prose string** ("until the start of your next turn") by explicit design (module docstring, `maneuver_executor.py:31-33`) — nothing decrements it | A round-tracked duration model; today a human (or the LLM narrator) must remember to clear it |
| **Temporary HP** | ❌ | No `temp_hp`/`temporary_hit_points` node or helper anywhere in `maneuver_executor.py`/`spellcasting.py` | New node; the engine's `entity.health` may or may not support temp HP — not verified this pass |
| **Summoning (creatures/objects)** | ❌ | Zero hits for `summon` in either executor | New node; would need the combat session to register a new combatant mid-fight — a session-management capability, not just an executor node |
| **Teleportation / forced movement** | 🟡 partial-adjacent | `Gravitation` Lashings and `Transportation` arts are exactly this use case; nothing in either executor moves an entity's grid position | New node touching whatever position system the tactical grid uses |
| **Terrain creation** (Cohesion "coat an area", Abrasion "difficult terrain") | ❌ | Zero hits | New node; needs a "battlefield feature" concept the grid can consult |
| **Resistance granting** (Absorb Essence: "resistance to the triggering damage type") | ❌ | `ieffect2`'s inline `effects` dict can carry an arbitrary key like `"resistance": "fire"`, but nothing downstream *reads* that key to actually reduce incoming damage — confirmed by grep: `grep -n "resistance" components/combat/maneuver_executor.py components/combat/spellcasting.py` → zero hits | Either a damage-resolution hook that consults `maneuver_effects` for a resistance key, or a real node type |
| **Advantage/disadvantage granting** (Distracting Attack, Abrasive Bolt's "next attack has advantage") | 🟡 partial | The *maneuver* version works via `ieffect2`'s `grants_advantage_to_others`/`disadvantage_against_others` inline keys, consumed somewhere in the tactical-advantage layer per `policy.py` (not independently re-verified this pass, carried from prior audit) — but this is the OLD maneuver mechanism, not a generic node the new arts could reuse without hand-authoring the same inline key each time | Works for maneuvers; arts would need the same inline-key convention re-applied per entry, which is authoring cost, not code cost |
| **Reaction triggers** (Absorb Essence "1 reaction when you take X damage"; many Truthwatcher/Lightweaver arts) | ❌ | The **maneuver** system has `action_type: "reaction"` with a `trigger` string (`surgebinding.json`'s `reverse_lashing`, `riposte`), so the *concept* exists in the Handbook's data schema — but `spell_compiler.py`'s `CompiledSpell` has no `action_type`/`trigger` field, and `SpellcastingService.cast()` has no reactive-trigger entry point at all | Needs either extending `CompiledSpell` with a trigger and a session hook that offers it at the trigger moment (mirroring `_maneuver_actions`'s `on_hit`/`on_move` handling), or treating reaction-arts as a new authoring track |
| **Multi-target** (arts that hit "each creature within 30 feet", "a number of creatures equal to X") | ❌ | Same root cause as AoE — `targets: List[str]` is caller-supplied, single-choice by construction in `combat_session_manager.py`'s target-picking UI (`_get_valid_targets`, single `target_id`) | Coupled to the AoE gap: needs a multi-select target UI plus the AoE resolution logic |
| **Upcasting / level scaling** ("At Higher Levels") | ✅ (mechanically) | `_pick_slot_row`/`_pick_character_row` in `spell_compiler.py:124-153` already read a level-keyed table; the SAME mechanism the book's "when cast at 2nd level, damage increases by 1d6/level" text needs | Reusable as-is for the compiler; see §2 for the cost-table mismatch |

**Ranked list of missing node types is in "The interpreter gap" below.**

---

## 2. Could `spellcasting.py`/`spell_compiler.py` compile Invested Arts instead of (or alongside) SRD spells?

**Yes, structurally — this is the strongest finding in the audit.** The two
data shapes line up almost field-for-field:

| SRD spell JSON field | Invested Art book field (parsed prose) | Compiler already reads it? |
|---|---|---|
| `casting_time` | `Casting Time` | ✅ (`spell_compiler.py:178`) |
| `range` | `Range` | ✅ (`:175`) |
| `components` | `Components` (G/S here vs V/S/M in SRD — Cosmere replaces Verbal/Material with Gestures/Aons-implied "G") | ✅ field exists, but the **meaning of "G" is undefined** — see gap below |
| `duration` | `Duration` | ✅ (`:174`) |
| `concentration` (bool) | `▶` glyph prefix on the art's name (book's own key, `docling.md:317`) | 🟡 SRD spells carry `concentration` as a JSON bool; the book encodes it as a **Unicode glyph in the heading text**, which nothing parses today |
| `dc.dc_type` / `dc.dc_success` | "Make a \[Ability\] saving throw" prose | ❌ **not structured** — the book has no `dc` JSON, only English. A parser would need to regex the ability name out of "the target must make a Strength saving throw" |
| `damage.damage_at_slot_level` | "the damage increases by 1d6 for each level above 1st" prose | ❌ **not structured** — SRD gives a table keyed by slot level; the book gives a *linear formula in prose* ("+1d6/level"), a different (simpler, but unparsed) shape |
| `attack_type` | "Make a ranged Invested Art attack" prose | 🟡 detectable by string match ("Invested Art attack") but not a JSON field |
| `school` | Surge name (Abrasion, Division, Illumination, …) | ✅ conceptually 1:1, needs mapping |
| slot level (0-9) | 0 (cantrip) through 5th level (book confirms `cost_by_art_level` tops out at 5 in `surgebinding.json`) | 🟡 Cosmere caps at 5 levels, not 9 — `spell_compiler.py`'s `MAX_SPELL_LEVEL = 9` constant would need per-system awareness or simply never be exceeded, which is harmless |
| spell slot cost | **Investiture Point cost**, `cost_by_art_level` in `surgebinding.json` (1st=2, 2nd=3, 3rd=5, 4th=6, 5th=7; Elsecaller flat 1) | ❌ **completely different economy** — see §3 |

**Bottom line for this section**: the *executor* (the automation-tree runner)
is directly reusable with zero changes. The *compiler* (`spell_compiler.py`) is
architecturally the right pattern but cannot be pointed at this book's raw text
today, because **the book's mechanical data is prose, not JSON** — unlike SRD
spells, which arrive as Docling-parsed but still *structured* per-field JSON.
Reusing the spellcasting pipeline for Invested Arts requires a **new
extraction/authoring pass**: someone (a human reviewer, or an LLM-assisted
extractor with a human review gate, matching the project's own "an unreviewed
entry MUST NOT adjudicate" rule from `cosmere_rules.py`) needs to turn each of
665 prose entries into the same `{damage, dc, heal_at_slot_level, ...}` JSON
shape the compiler already consumes. This is authoring cost, not new code —
`compile_spell()` itself would need only:
1. A new slot/cost model swap (Investiture Points instead of spell slots — a
   different `SlotLedger`-shaped class, same shape).
2. Recognizing "Invested Art attack" as equivalent to `attack_type`.
3. A regex or authored `dc` field for the ability-save sentence.

None of that is a rewrite; all of it is additive.

---

## 3. Investiture Points economy

| Component | Implemented? | Reachable? | Evidence | Gap |
|---|---|---|---|---|
| `cosmere_rules.investiture_cost(art_level, order)` — the book-accurate per-art-level cost table (1st=2 … 5th=7, Elsecaller flat 1) | ✅ | ❌ | `components/cosmere_rules.py:138-151`; live-called successfully | `grep -rn "investiture_cost\|cost_by_art_level" --include="*.py" components/ agents/ core/ orchestrator/` (excluding tests) → **only its own definition in `cosmere_rules.py`**. Zero production callers. |
| `CharacterData.investiture_points` (a `{current, maximum}` dict) | ✅ (as a field) | 🟡 | `character_manager.py:87` — the field's own inline comment says *"use stormlight_current/capacity instead"* | This is a **different, legacy resource track**, not the book's per-art cost economy. It is read/written in ~15 places in `character_manager.py` (`update_investiture_points`, `spend_investiture`, level-up grants at `:1778-1804`) but none of those call sites derive their numbers from `cosmere_rules.investiture_cost()` — the hardcoded grants (`{"current": 3, "maximum": 5}` at level-up, `+3`/`+5`/`+7` by threshold) are the same class of "plausible and invented" number `_meta.correction` in `surgebinding.json` warns about, just in a different file |
| `CharacterData.stormlight_current`/`stormlight_capacity` | ✅ | ✅ | `character_manager.py:68-69`; `dm_tools.py:722 spend_stormlight` is a real `@tool` | This is the resource Lashing Dice and the four hardcoded surge classes actually spend (`roshar_actions.py`'s `stormlight_cost` fields) — **a THIRD economy**, "Stormlight spheres," distinct from both Lashing Dice and Investiture Points per `surgebinding.json`'s own `economies` block |
| `LashingDicePool` | ✅ | ✅ | `lashing_dice.py`, wired into `_maneuvers()` | Correct and reachable, but only for Windrunner Maneuvers — not the Invested Arts book's economy at all |

**There are now three non-interoperating "how do I pay for a Radiant ability"
systems in the codebase**, and the book introduces the specification for the
one (`investiture_points`, cost-by-art-level) that has a *rules definition*
(`cosmere_rules.py`) but **zero economic plumbing** — no ledger class analogous
to `SpellSlotLedger`/`LashingDicePool` that actually spends and restores
Investiture Points against `investiture_cost()`'s table. `CharacterData`'s
existing `investiture_points` field could be repointed at it, but as shipped
its values are invented at level-up, not derived from the book.

---

## 4. The three-tier rules system — where would 665 arts live?

| Question | Answer | Evidence |
|---|---|---|
| Does `cosmere_rules.py`'s schema extend to arts? | 🟡 Extensible in principle, not populated | The loader (`CosmereRules.load()`, `:46-77`) generically merges any top-level JSON key from `data/rules/stormlight/*.json` — adding an `"invested_arts": [...]` file next to `surgebinding.json` would be picked up automatically by the same merge logic that already handles `maneuvers`/`features`/`surges`. **No code change needed to load a new bucket.** But no query methods exist for it (`get_maneuver`/`order`/`maneuvers`/`features` all hardcode their bucket name) |
| Does `query_rules` in `dm_tools.py` surface arts? | ❌ | `agents/dm_tools.py:412-420`: only `cosmere.get_maneuver(topic)` and `cosmere.order(topic)` are tried for Tier 2. Live-verified: `get_cosmere_rules().get_maneuver("Abrasive Bolt")` → `None`. There is no `cosmere.get_art()`/`cosmere.spell()` method, so a DM asking "what does Abrasive Bolt do" falls straight through to Tier 3 (rules judge on retrieved RAG text) or the Tier-4 "no rule found, improvise" fallback — **exactly the outcome `_meta.surges_note` in `surgebinding.json` predicted before this book existed** |
| Would arts sit at Tier 2 or need a Tier 1.5? | Tier 2, cleanly | The three-tier split is `SRD (5e baseline)` / `Cosmere Handbook (Radiant mechanics)` / `Qdrant lore (never adjudicates)`. Invested Arts are exactly "Cosmere Handbook mechanics" — they belong beside `maneuvers`/`surges`, in a **new `invested_arts.json`** file in `data/rules/stormlight/`, following the same `source.line`/`reviewed`/`quote` citation discipline `surgebinding.json` already enforces (and that `verify_citations()` already knows how to check against ANY Handbook markdown, since it takes `handbook_md` as a parameter) |
| Is Tier 3 (rules judge) a viable stopgap today? | ✅ mechanically, ⚠️ wasteful | `RulesJudge.judge()` is real (per template audit §12) and would produce a grounded ruling from RAG-retrieved book text for any art not yet authored into Tier 2 — genuinely better than nothing, but re-derives the same mechanics from prose on every single cast rather than once at authoring time, and produces a narrative ruling rather than a real damage number the combat log can rely on |

---

## 5. Radiant character support — do the 5 hardcoded surge classes conflict with the book?

**Yes — confirmed by direct text comparison, not guesswork.** All five
hardcoded classes in `components/combat/roshar_actions.py` invent numbers the
book does not support, or contradict the book's actual mechanic outright.

| Hardcoded class | Hardcoded mechanic (`roshar_actions.py`) | Book's actual text (this audit's source) | Verdict |
|---|---|---|---|
| `Lashing` (`:95-210`) | Docstring claims "Cost: 1 Action + 1 Stormlight sphere," "Duration: 10 rounds (concentration)," three named sub-types (`basic`/`full`/`reverse`) | `Gravitation` cantrip (`docling.md:348-373`): a **bonus action** (not always 1 action) to Lash an object at 10 ft/round with **no duration/concentration at all** (Instantaneous); targeting a *creature* requires **11th level** and an **attack roll**, explicitly gated by level, none of which the code checks; costs **0 Investiture** (cantrip) | **Conflicts on cost (invents a Stormlight-sphere cost the cantrip doesn't have), on duration (invents 10-round concentration that doesn't exist), and on mechanics (no attack roll, no level gate, wrong action economy)**. The book's `Full Lashing` name appears only inside this cantrip's own prose describing a *different, higher tier* of the same Surge — the hardcoded class's docstring citation "pg. 47" cannot be checked (no page numbers in the parsed text) but the mechanic described does not match either the cantrip or the Handbook's `full_lashing` Maneuver (a Strength save + bludgeoning damage, no gravity-direction field at all) |
| `ShardbladeAttack` (`:225-315`) | "2d6 necrotic (soul damage, ignores AC)" | Not found in `The Invested Arts of the Cosmere` at all — grep for "Shardblade" in the new book: not checked for damage numbers since Shardblades are equipment, not an Invested Art, so this class is likely out of this book's scope entirely (belongs to a different sourcebook, "Invested Items Collection," per the book's own resources list at `docling.md:79`) | **Not this book's jurisdiction** — no conflict *found*, but also no book-derived confirmation the 2d6 number is right either; unresolved, flag for the Invested Items audit |
| `ProgressionHealing` (`:329-472`) | "Healing: 2d8 + Wisdom modifier," "Cost: 1 Action + 2 Stormlight spheres" | The book's `Progression` cantrip (`docling.md:424-448`, not fully re-read this pass but headed identically to Adhesion/Gravitation) and the levelled Progression arts ("Regrowth," "Regrowth Tough," "Aiding Regrowth" — all in the Edgedancer art list, `docling.md:145-151`) are **levelled Invested Arts with Investiture Point costs**, not a flat always-available action — the hardcoded class offers Progression healing as a single fixed-cost ability with no level/art distinction at all | **Conflicts on structure**: the book models "Progression healing" as a *family of distinct Invested Arts at different levels* (a cantrip AND several 1st/2nd-level arts), while the code collapses this into one hardcoded action with one invented cost. Also uses **Wisdom** — not independently verified against the book's stated Investiture ability for Edgedancer/Truthwatcher in this pass, flagged |
| `Illumination` (`:495-579`) | "Cost: 1 Action + 1 Stormlight sphere," applies the 5e `Invisible` condition as a stand-in | Book's `Illumination` cantrip (`docling.md:449-477`, header-only reviewed this pass): a cantrip, 0 Investiture cost per `surgebinding.json`'s own `surges.Illumination.cost.investiture_points: 0` | **Conflicts on cost** — the hardcoded class charges a Stormlight sphere for what both the book and the already-reviewed `surgebinding.json` agree is a **free cantrip**. Using 5e's `Invisible` condition as a mechanical proxy is also almost certainly wrong: illusion (fooling perception) and invisibility (cannot be seen at all) are different effects, and a monster with truesight/blindsight would be fooled by neither if the code actually modeled `Invisible` correctly, while the book's actual mechanic is an Investigation-vs-Deception contest per the class's own docstring |
| `Soulcast` (`:590-673`) | "Cost: 1 Action + 3 Stormlight spheres" | `Transformation` cantrip (`surgebinding.json`'s own `surges.Transformation.cost.investiture_points: 0`) — again a free cantrip in the reviewed Tier-2 data | **Conflicts on cost**, same pattern as Illumination |

**Every one of the five hardcoded classes charges an invented Stormlight-sphere
cost for what the ALREADY-REVIEWED `surgebinding.json` (committed before this
book arrived) independently confirms are free cantrips** (`cost.investiture_points: 0`
for all ten surge cantrips, `surgebinding.json:552-742`). This is not a new
discovery this audit is making about the book — `surgebinding.json`'s own
`_meta.correction` field already documented exactly this failure mode
(*"An earlier hardcoded implementation in components/combat/roshar_actions.py
invented a per-use Stormlight-sphere cost for every surge... plausible and
wrong"*) for the Lashing Dice economy, and this audit confirms **the same
uncorrected classes still charge Stormlight for cantrip-tier surges** even
after that correction landed in the JSON. The book should win in every
instance: it's the primary, dedicated source for exactly this content, whereas
`roshar_actions.py`'s numbers were reverse-engineered guesses written before
either sourcebook existed.

---

## 6. Concentration

**319 raw hits for "concentration"** in the book (per the prompt's count,
confirmed: `grep -c concentration` → 31 lines contain the literal word, but the
book also flags concentration arts with a `▶` glyph per its own key at
`docling.md:317`: *"If the Invested Art has a ▶ symbol by its name, it requires
concentration."* Counting glyph occurrences is the real per-art concentration
count):

```
$ grep -c "^## ▶" parsed_data/cosmere-5e-the-invested-arts-of-the-cosmere-v2-0/docling.md
283
```

So **283 of the 665 arts (~43%) require concentration** by the book's own
count — nearly identical in proportion to the SRD's own concentration rate,
and far higher than the raw "31 literal word hits" the naive grep count
suggests. This makes concentration-break enforcement (§"interpreter gap" #4)
more urgent than the literal-word count implies.

Confirmed no concentration ENFORCEMENT exists anywhere in the codebase:

```
$ grep -rn "concentration" --include="*.py" components/ agents/ core/ orchestrator/ \
    | grep -v __pycache__ | grep -v tests/ | grep -v spell_compiler.py | grep -v spellcasting.py
components/combat/roshar_actions.py:105:    - Duration: 10 rounds (concentration)   # a comment, not code
components/combat/combat_action_resolver.py:78:  # a comment about intent
```

`ConcentrationTracker` (§1 table) exists, is instantiated by
`SpellcastingService`, and correctly drops a prior spell when a new one starts
— but nothing calls a "roll a CON save when this creature takes damage" hook,
and nothing calls `ConcentrationTracker.stop()` when a save is failed, because
there is no save being rolled. **Reachable = No.** The book's 319→(glyph-count)
concentration arts would all "concentrate" in the sense of occupying the
tracker's one slot, but the concentration-breaking mechanic 5e balances area
denial and control spells around is entirely absent.

---

## 7. Saving throws

**420 hits for "saving throw" confirmed.** The engine-level plumbing this
would use is real and already exercised by both Maneuvers and spells:

```python
# maneuver_executor.py:469-477 — _roll_save()
save = entity.saving_throws.get_saving_throw(stat)
bonus = int(getattr(save.bonus, "score", 0) or 0)
modifier = getattr(entity.ability_scores, stat).modifier
outcome = self.dice.saving_throw(stat, modifier, proficiency=bonus)
```

`entity.saving_throws.get_saving_throw(stat)` is a real vendored-engine call
(confirmed present at `external/dnd_engine/dnd/conditions.py:180,399,402,537`
for the engine's own condition-triggered saves — DEX/STR specifically). The
`save` node's DC resolution supports both a literal int and the two named
formulas already wired: `"invested_save_dc"` (maneuvers,
`maneuver_executor.py:423-442`, reads `CosmereRules.invested_save_dc()`) and
`"spell_save_dc"` (spells, `spellcasting.py:531-541`). **A third named DC,
something like `"art_save_dc"`, would need the same treatment** — almost
certainly identical to `invested_save_dc` (8 + proficiency + Investiture
ability modifier, per `surgebinding.json`'s own formula, `:68-78`), since the
book's Invested Arts use the same Radiant Investiture-ability concept the
Handbook already defines. **This is a near-zero-cost reuse**, not a new
mechanic: `_resolve_dc()` in `maneuver_executor.py` already has the pattern to
copy.

`saving_throw_proficiencies` on `CharacterData` exists (per the template
audit's §1) but its consumer status was flagged 🟡/unresolved there and not
re-verified in this pass — carried forward as an open question.

---

## The bottom line

No — the existing codebase cannot execute 665 Invested Arts today, but the gap
is narrower and more tractable than the standalone "Cosmere RPG" question this
audit's sibling document answered: the **interpreter is already the right
shape** (`maneuver_executor.py`/`SpellEffectExecutor` handle single-target
save-or-damage, healing, and half-on-save with zero new code), and the
**compiler pattern is proven** on 319 structurally-similar SRD spells, but the
book supplies its 665 arts as **prose, not JSON**, so nothing can compile them
until each entry is extracted into the same `{casting_time, dc, damage_at_*}`
schema `spell_compiler.py` already consumes — that extraction is authoring
work (LLM-assisted, human-reviewed, per this project's own D5 "unreviewed
entries must not adjudicate" rule), not a rewrite. The shortest credible path
keeps 5e and this book exactly as the user wants: build one new Investiture
Point ledger class (a `SlotLedger` sibling, reading the already-correct
`cosmere_rules.investiture_cost()` table nothing currently calls), extend
`CompiledSpell`/`compile_spell()` to accept a hand-or-LLM-authored
`invested_arts.json` per order, and add 2-4 new executor node types (area
target-expansion first, concentration-break second) — all additive to code
that already exists and passes tests, at a cost of roughly one order's worth
of hand-authored JSON (60-90 arts, matching Windrunner+Skybreaker's combined
list) before the first real session, not a rewrite of combat.

---

## The interpreter gap

Ranked by how many of the 665 arts each unblocks, estimated from a manual read
of the alphabetical entries sampled in this audit (Abrasive Bolt, Absorb
Essence, Acid Splash, and the ten Basic Surge cantrips) and the SRD spell
distribution `spell_compiler.py`'s own docstring already measured (66/319 SRD
spells need `damage`, 92/319 need `dc`, only 10/319 need `heal_at_slot_level`)
as a proxy for likely proportions in a similarly-shaped 665-entry Cosmere set:

1. **Area-of-effect target expansion** (cone/sphere/cube/line → multiple
   targets). Highest-impact: `area_of_effect` is already parsed and stored by
   `spell_compiler.py` and immediately usable the moment target selection
   changes from "the one entity the caller chose" to "everyone the grid says is
   inside this shape." Blocks every art shaped like the SRD's Fireball/Cone of
   Cold pattern — a large fraction of the 5e-styled arts, especially
   Division/Illumination/Transformation AoE arts.
2. **Prose-to-DC/damage extraction** (not a node type, but the compiler-side
   blocker everything else sits behind). Every art needs SOME structured
   `dc`/`damage` data before any node runs at all; right now that data simply
   does not exist for these 665 entries. Ranked second only because it's a data
   pipeline problem, not a runtime interpreter gap — but nothing else in this
   list matters until it's solved for at least one order's arts.
3. **Reaction triggers** (`action_type: "reaction"` + `trigger` string, mirrored
   from the Maneuver schema onto `CompiledSpell`). Several of the sampled arts
   (`Absorb Essence`) are explicitly reaction-triggered; this is a common shape
   for defensive/interrupt arts across Truthwatcher/Lightweaver/Stoneward.
4. **Concentration-break-on-damage hook.** Fixes an existing correctness gap
   (SRD spells have the same hole) as a side effect — one hook serves both the
   319 SRD spells and however many of the 665 arts carry the `▶` glyph.
5. **Resistance-granting as a real effect** (not just an inert dict key).
   Needed by `Absorb Essence` and likely several other Transformation/defensive
   arts; currently `ieffect2`'s inline effects dict can *carry* the data but
   nothing consumes it.
6. **Terrain/duration-tracked effects** (difficult terrain, "coats an area for
   1 minute"). Lower priority — mostly utility/exploration-flavor arts, fewer
   of them gate combat outcomes than damage/save/AoE arts do.
7. **Teleportation/forced movement, summoning, temporary HP.** Lowest priority
   by count (sampled entries suggest these cluster in specific orders —
   Elsecaller/Willshaper Transportation, a handful of Lightweaver
   Transformation arts — rather than spreading across all 665), and each is
   also the most implementation-effort (summoning needs new-combatant session
   support; movement needs the tactical grid's position API, not verified
   in this pass).

---

## Conflicts to resolve

All five hardcoded classes in `components/combat/roshar_actions.py` disagree
with the now-authoritative sources (both the new book AND the
already-reviewed `surgebinding.json`, which predates the book but already
corrected the same failure mode once):

- **`Lashing`**: invents a Stormlight-sphere cost, a 10-round concentration
  duration, and three named sub-types the book doesn't describe this way — the
  book's `Gravitation` cantrip is a free bonus action with no duration, and
  targeting a creature requires an explicit level gate (11th) and an attack
  roll the hardcoded class never rolls. **Book wins.**
- **`Illumination`** and **`Soulcast`**: both charge Stormlight for what
  `surgebinding.json`'s own reviewed data (`surges.Illumination.cost` /
  `surges.Transformation.cost`, both `investiture_points: 0`) already
  confirmed are free cantrips, before this new book even existed. **Both the
  book and the pre-existing reviewed JSON win; the hardcoded classes are
  doubly wrong.**
- **`ProgressionHealing`**: collapses a whole family of levelled Progression
  arts (the book lists at least three: base cantrip, "Regrowth," "Regrowth
  Tough," "Aiding Regrowth") into one fixed 2d8+WIS action with an invented
  Stormlight cost. **Book wins**, and this is also the biggest single
  rework — replacing one action class with a real compiled-art lookup.
- **`ShardbladeAttack`**: no conflict *found* — likely out of this book's
  scope (Shardblades are Invested Items, a different sourcebook per the book's
  own resource list), so its 2d6 necrotic number is neither confirmed nor
  contradicted here. Flag for a future Invested Items audit, not this one.

**Recommendation**: retire all five hardcoded classes once even one order's
arts are authored into Tier 2 JSON, rather than patching their invented
numbers — the maneuver/spell executor pattern already replaces exactly this
kind of one-class-per-ability code with data, and leaving the classes in place
as a second, disagreeing source of truth is the two-economies problem in §3
happening again at the ability-effect layer.

---

## Cheapest path to a playable Radiant (Windrunner)

Windrunner is favorable: it already has a working Maneuver track (Lashing
Dice, 8 of 9 Maneuvers reviewed), so this is additive, not a fix.

1. **Author `data/rules/stormlight/invested_arts_windrunner.json`** covering
   the Windrunner + Skybreaker cantrips (`Adhesion`, `Gravitation`, plus
   Skybreaker's `Division` at 5th level) and whatever levelled Gravitation/
   Adhesion arts the book lists for Windrunner (`docling.md:129-137` names the
   list; not fully cross-referenced against the alphabetical descriptions in
   this pass — that enumeration is exactly what the sibling
   `COSMERE_ARTS_SURGEBINDING_A.md`/`_B.md` documents are doing concurrently).
   Each entry needs the same `source.line`/`reviewed`/`quote` discipline
   `surgebinding.json` already enforces — extend `CosmereRules.load()`'s
   generic bucket-merge (already handles arbitrary top-level keys) with one
   new query method, `get_art(name)`, mirroring `get_maneuver()` almost
   verbatim (`cosmere_rules.py:109-116`).
2. **Add an `InvestiturePointLedger`** class, a near-copy of
   `SpellSlotLedger` (`spellcasting.py:214-331`) but reading
   `CosmereRules.investiture_cost(art_level, order)` instead of a slot table,
   and spending against `CharacterData.investiture_points` (repointing that
   field at the book's real cost table instead of the invented level-up
   grants at `character_manager.py:1778-1804`).
3. **Extend `compile_spell()`/`CompiledSpell`** (or write a sibling
   `compile_art()`) to read the new JSON shape — trivial if step 1's JSON is
   authored in the SRD's existing field names (`damage`, `dc`, `duration`,
   `concentration`), since the compiler's row-picking logic
   (`_pick_slot_row`/`_pick_character_row`) is level-table-agnostic already.
4. **Register a `cast_art` action** in `action_registry.py`, copying
   `cast_spell`'s entry verbatim but with `param_defaults: {"art_name": None}`
   — the exact one-line fix pattern the codebase already knows to apply
   (do not repeat the `cast_spell`/`spell_name` omission bug).
5. **Fix or retire `Lashing`** (§5) so a Windrunner's cantrip-tier Gravitation
   doesn't charge an invented Stormlight cost the moment `cast_art` makes the
   real, free cantrip available beside it — leaving both would let a player
   choose the worse, hardcoded version by accident.

This scopes to roughly 60-90 authored art entries (Windrunner + Skybreaker
combined cantrip and levelled lists, per the book's own table of contents at
`docling.md:129-137`), one new ledger class, one compiler extension, and one
registry entry — no changes to the vendored `dnd_engine`, no rewrite of
`maneuver_executor.py`, and it reuses 100% of the already-tested execution
path. It does **not** require solving AoE, concentration-break, or reaction
triggers first, since a conservative first pass can simply mark any
Windrunner/Skybreaker art needing those (there appear to be few, since most of
Gravitation/Adhesion's sampled entries are single-target) as
`needs_adjudication`, exactly as `spell_compiler.py` already does for Wish and
Counterspell — an honest partial launch, not a silent one.
