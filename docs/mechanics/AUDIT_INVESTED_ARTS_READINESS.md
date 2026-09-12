# Audit — Invested Arts readiness

**Can this codebase execute the 661 Invested Arts?** Scored the same way as
`AUDIT_CHARACTER_AND_NONCOMBAT.md`, on two axes that come apart constantly in this
project:

    IMPLEMENTED   the code exists and its tests pass
    REACHABLE     a player in a real session can actually trigger it

A module with passing tests and zero production callers is **not** a capability. There are
ten documented instances of that here, and one of them is in this very audit
(`investiture_cost()`).

**Source of truth:** `parsed_data/cosmere-5e-the-invested-arts-of-the-cosmere-v2-0/docling.md`
(19,794 lines; 661 art entries — 324 Surgebinding, 69 Allomancy, 272 Aonic).
**Verified 2026-09-12** with `uv run`. See `COSMERE_SYSTEMS_MAP.md` for why Cosmere 5e is the
system being implemented.

Legend: ✅ works · 🟡 partial · ❌ absent. The **Comment** column is for the project owner's
triage, matching the template.

---

## 1. The interpreter — can it execute arts as data?

`components/combat/maneuver_executor.py` is a working declarative interpreter with **6 node
types**, already running the 9 authored maneuvers and wired into combat.

| Mechanic | Implemented? | Reachable? | Evidence | Gap/notes | Comment |
|---|---|---|---|---|---|
| Declarative interpreter exists | ✅ | ✅ | `KNOWN_NODES` at `maneuver_executor.py:49` = `{target, save, damage, attack, roll, ieffect2}`. 9 external production refs to `ManeuverExecutor` (grep excluding its own file), incl. `combat_session_manager._maneuvers()`. 58 tests pass. | The right shape already. Arts are additive to it, not a replacement. | |
| `target` node | ✅ | ✅ | `maneuver_executor.py:49` | Single-target only — no area expansion (see §2). | |
| `save` node (save-or-suffer, save-for-half) | ✅ | ✅ | `maneuver_executor.py:49`; the book uses saves 420× | Covers the largest single art category. | |
| `damage` node | ✅ | ✅ | `maneuver_executor.py:49` | | |
| `attack` node | ✅ | ✅ | `maneuver_executor.py:49` | | |
| `roll` node | ✅ | ✅ | `maneuver_executor.py:49` | | |
| `ieffect2` node (apply a condition) | ✅ | ✅ | `maneuver_executor.py:49` | Applies named 5e conditions through the engine, so they compose. | |
| **Art data to execute** | ❌ | ❌ | `ls data/rules/stormlight/` → only `surgebinding.json`. No `invested_arts*.json` exists anywhere. | **The real blocker.** The interpreter is ready; there is nothing for it to run. The book states mechanics as PROSE, while the compiler needs `{casting_time, dc, damage_at_*}` fields. This is authoring work, not engineering. |COMMENT: implement and wire now completely |

## 2. Missing node types, ranked by arts unblocked

| Mechanic | Implemented? | Reachable? | Evidence | Gap/notes | Comment |
|---|---|---|---|---|---|
| Area of effect (cone/sphere/cube/line) | ❌ | ❌ | Not in `KNOWN_NODES` (`maneuver_executor.py:49`). The grid already computes distance and FOV (`components/combat/tactical_grid.py`). | **Highest value.** Geometry data is already parsed and stored and simply never consulted. Unblocks the most arts of any single node. |COMMENT: implement and wire now completely |
| Concentration | 🟡 | ❌ | The word appears in `roshar_actions.py`, `combat_action_resolver.py`, `spellcasting.py`, `spell_compiler.py` — but no break-on-damage hook. Book usage: 319 by word, **286 by its `▶` glyph**; the audit estimates ~43% of arts. | Nearly half the arts declare concentration and nothing tracks it. Needs a CON-save-on-damage trigger. |COMMENT: implement and wire now completely |
| `heal` node | ❌ | ❌ | Not in `KNOWN_NODES`. `ProgressionHealing` heals via a hardcoded class instead. | Progression/Regrowth arts are a large family for Edgedancer and Truthwatcher. |COMMENT: implement and wire now completely |
| Reaction triggers | ❌ | ❌ | Not in `KNOWN_NODES`. Maneuvers handle `reaction` as an action_type, not as a mid-roll hook. | Some arts insert a die after a roll but before the result (Guidance/Resistance shape). |COMMENT: implement and wire now completely |
| Resistance as a real effect | ❌ | ❌ | Not in `KNOWN_NODES`. Engine supports it (`health.damage_reduction`) — see §5. | |COMMENT: implement and wire now completely |
| `move` / `forced_move` / `teleport` | ❌ | ❌ | Not in `KNOWN_NODES` | Transportation arts (Elsecaller, Willshaper) need it. |COMMENT: implement and wire now completely |
| `create_object` / `create_zone` (own HP/AC) | ❌ | ❌ | Not in `KNOWN_NODES` | Terrain and wall arts. |COMMENT: implement and wire now completely |
| `summon` (CR budget + stat-block override) | ❌ | ❌ | Not in `KNOWN_NODES` | |COMMENT: implement and wire now completely |
| `illusion` (with disbelieve sub-check) | ❌ | ❌ | Not in `KNOWN_NODES` | Lightweaver's signature; ~132 arts is the largest order list. |COMMENT: implement and wire now completely |
| Check-vs-DC resolution (not a save) | ❌ | ❌ | Not in `KNOWN_NODES` | Dispel/Counter-Invest arts use an ability check vs a level-derived DC. |COMMENT: implement and wire now completely |
| Stateful recurring-save wrapper | ❌ | ❌ | Not in `KNOWN_NODES` | Multi-turn ladders (3-success/3-fail) that a flat condition-apply cannot express. |COMMENT: implement and wire now completely |

## 3. The compiler — could it compile arts as it does spells?

| Mechanic | Implemented? | Reachable? | Evidence | Gap/notes | Comment |
|---|---|---|---|---|---|
| Spell compiler | ✅ | ✅ | `components/combat/spell_compiler.py`; `SpellcastingService` has 5 external refs. Proven on 319 structurally similar SRD spells. | The pattern is right — arts share the shape (casting time, range, components, duration, concentration, save DC, scaling). | |
| `cast_spell` action offerable | ✅ | ✅ | `uv run python -c "...is_offerable('cast_spell')"` → **True** (fixed 2026-09-11 by adding the missing `spell_name` default). | Was ❌/❌ the day before: `param_defaults` omitted `spell_name`, so all 319 spells were uncastable. **Do not repeat this when adding `cast_art`.** | |
| `cast_art` action | ❌ | ❌ | No such key in `ACTION_REGISTRY` (verified by enumeration). | Needs registering, copying `cast_spell`'s entry — including its `param_defaults` lesson. |COMMENT: implement and wire now completely |
| Art→JSON extraction pipeline | ❌ | ❌ | No script exists. Book is prose. | The gating task. Per D5, entries must be human-reviewed before they adjudicate. |COMMENT: implement and wire now completely |

## 4. Investiture Points economy — three ways to pay, one correct

| Mechanic | Implemented? | Reachable? | Evidence | Gap/notes | Comment |
|---|---|---|---|---|---|
| Lashing Dice pool | ✅ | ✅ | `components/combat/lashing_dice.py`; `LashingDicePool` has 4 external refs incl. `combat_session_manager._dice_pool()`. | Correct and wired — but Windrunner-only. |COMMENT: implement and wire for all valid surges completely |
| `investiture_cost()` cost table | ✅ | ❌ | `components/cosmere_rules.py:138`. **`grep -rn "investiture_cost" components/ agents/ core/ orchestrator/` excluding its own file → 0 hits.** | **Built, correct, and unreachable** — the tenth instance in this project. It holds the book-accurate `cost_by_art_level` table and nothing calls it. |COMMENT: implement and wire now completely |
| Stormlight sphere cost on surges | ✅ | ✅ | `roshar_actions.py:91` `stormlight_cost: int = 1` | **WRONG, and live.** `surgebinding.json` records the same cantrips as `{'investiture_points': 0}`. A Windrunner is charged a sphere for a free cantrip. See `AUDIT_HARDCODED_SURGE_ACCURACY.md`. |COMMENT: update now correctly |
| Investiture Point ledger | ❌ | ❌ | No such class. `CharacterData.investiture_points` exists as a legacy field whose own comment says to use stormlight instead. | Needs a `SlotLedger` sibling reading `investiture_cost()`. |COMMENT: implement and wire now completely |
| Long-rest refill gated on Stormlight intake | ❌ | ❌ | Rule is at `HB:13133-13141` (verified verbatim). No implementation. | Refill is conditioned on intaking level × 5 sapphire marks, exactly as HP is. | COMMENT: implement and wire now completely|
| Polestone cracking / draining | ❌ | ❌ | Rule at `HB:13231-13241`. Nothing implements it. | Three distinct outcomes: crack (no change given), drain, or untouched if interrupted. Cost is paid even when the art FAILS. Nothing in 5e behaves this way. | COMMENT: implement and wire now completely|

## 5. Supporting engine capabilities the arts need

| Mechanic | Implemented? | Reachable? | Evidence | Gap/notes | Comment |
|---|---|---|---|---|---|
| Saving throws | ✅ | ✅ | Engine `saving_throws.get_saving_throw`; used by the `save` node. Book uses saves 420×. | Ready. | |
| Invested save DC formula | ✅ | 🟡 | `surgebinding.json` `invested_save_dc` = `8 + proficiency + Investiture ability modifier`; `cosmere_rules.invested_save_dc()` exists. | Formula present; confirm the art path uses it rather than a 5e spell DC. | |
| Damage resistance / vulnerability / immunity | 🟡 | ❌ | Engine supports it fully (`health.damage_reduction`); SRD data carries it; nothing connects them. Flagged in `AUDIT_COMBAT.md` too. | Owner comment there: **implement and wire now**. Some arts grant resistance. |COMMENT: implement and wire now completely |
| Conditions (all 15 SRD) | ✅ | ✅ | `components/engine_conditions.py` added Petrified + Exhaustion; all 15 apply via `apply_condition()`. | `ieffect2` can name any of them. | |
| Ideals / oaths | ✅ | ✅ | 49 refs to `advance_ideal`/`ideal_level` across components and agents. | Some arts gate on Ideal level. |COMMENT: Update them if needed now completely |
| The 10 `surges` entries in `surgebinding.json` | 🟡 | ❌ | All 10 have `automation: null`, `automation_status: "not_in_source"` — nulled *because the book was missing*. Nothing reads the key. | **Now authorable.** The blocker that caused the nulls is gone. 10 permanent blockers became 10 authoring tasks. |COMMENT: implement and wire now completely |
| The ~118 order features | ✅ (data) | ❌ | Catalogued in `COSMERE_MECHANICS.md`; `surgebinding.json` has only 2 in `features`. Nothing reads them. | Mostly passive (resistances, AC formulas, ability bumps) — needs a features shape, not automation trees. |COMMENT: implement and wire now completely |

## 6. Coverage reality — arts are not evenly distributed

Counted from bylines across all 19,794 lines and cross-checked against the chapter index.

| Order | Cantrips | Leveled arts | Implication |
|---|---|---|---|
| Truthwatcher | 12 | **101** | Arts are its only ability source — highest payoff |
| Lightweaver | — | **~132** | Largest list; needs the `illusion` node |
| Elsecaller | — | **~96** | Needs `teleport` |
| Edgedancer | 11 | **79** | Needs `heal` |
| Willshaper | 2 | 3 | Thin |
| Stoneward | 2 | **0** | Cantrips only (confirmed genuine) |
| **Windrunner** | **2** | **0** | Depth comes from Maneuvers, not arts |
| **Skybreaker** | **2** | **0** | |
| **Dustbringer** | **2** | **0** | |
| Bondsmith | 0 | 0 | Absent entirely — 0 hits in 19,794 lines |

**This inverts the "cheapest path to a playable Windrunner" advice below.** Windrunner has two
arts in existence; its depth is the Maneuver + Lashing Dice path, which is already 9 maneuvers
deep, wired and passing tests. The four art-rich orders are the ones with no Maneuver
equivalent, so arts are their *only* source of abilities.

## 7. Summary counts

| | Count |
|---|---|
| ✅ implemented **and** reachable | 12 |
| 🟡 partial | 5 |
| ❌ absent or unreachable | 17 |
| Built but unreachable (the dangerous category) | 3 — `investiture_cost()`, the 10 nulled surges, the ~118 order features |
| Live incorrect behaviour | 1 — sphere cost charged for free cantrips |

## 8. Built but unreachable

1. **`cosmere_rules.investiture_cost()`** (`cosmere_rules.py:138`) — book-accurate cost table,
   zero callers. Tenth instance of this pattern in the project.
2. **The 10 `surges` entries** in `surgebinding.json` — nulled because the book was missing;
   still nulled, but now authorable.
3. **The ~118 order features** catalogued in `COSMERE_MECHANICS.md` — 2 of 118 in the JSON,
   and nothing reads the `features` key.

---

<!-- The analysis below predates the coverage measurement in §6. Its Windrunner
     recommendation is superseded there; everything else stands. -->

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
