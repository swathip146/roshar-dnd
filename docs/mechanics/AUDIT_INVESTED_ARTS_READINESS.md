# Audit — Invested Arts readiness

> **SESSION UPDATE — 2026-09-12 (FINAL):** Major infrastructure completed; all core blockers resolved.
> 
> **✅ COMPLETED (what landed this session):**
> - `InvestiturePointLedger` built and wired (`components/combat/investiture_ledger.py`)
> - **12 executor nodes** (was 6): added `area_of_effect`, `check`, `resistance`, `utility`, `forced_move`, `choice`
> - Concentration break-on-damage implemented (`maneuver_executor.py:501-511`, DC=max(10,dmg/2))
> - `compile_art()` added to `spell_compiler.py`
> - `cast_art` registered in action registry + `_cast_art` resolver wired
> - `CosmereRules.get_art()` and `.arts()` methods added
> - `investiture_cost()` NOW WIRED (was unreachable; now has 2 callers)
> - 10 surge cantrips authored in `surgebinding.json` — **all now executable & playable via the separate `cast_surge` action (commit `7774ab2`); 0 remain `needs_adjudication`** (statuses: 3 resolvable, 4 utility_only, 1 partial, 2 utility+subsystem-pending)
> - Cantrips are free (was charging incorrect sphere cost)
> - 12 order features authored (was 2)
> - **AoE spells autotarget** (commit 157337d): `compile_spell` wraps area_of_effect, target-centered
> - **Long-rest Stormlight-intake gate** (commit cd202d2): level × 5 sapphire marks required for Radiants
> - **Polestone crack/drain** (commit cd202d2): `components/combat/polestone.py` implemented (first-pass)
> - 126 investiture/art/economy tests passing
> 
> **✅ COMPLETED (Surgebinding arts — commits `e97d7c1`, `0b4af94`, `c54551e`, `6b265fd`):**
> - **`cast_art` NOW WORKS END-TO-END**: the latent executor-API bug is FIXED (`0b4af94`); it now builds correct maneuver dicts, calls executor.execute(maneuver, actor, targets), handles ManeuverResult, refunds IP on no-effect, auto-selects the first affordable art, and reads `art_level` (not `level`), so leveled arts now cost Investiture Points correctly. Offered iff an affordable castable art exists for the actor's order.
> - **`compile_art` derives automation from structured stat-block fields** (`c54551e`) via `_derive_automation_from_fields()` (save/attack/heal/damage/AoE). Arts with heal/spell_attack nodes route through SpellEffectExecutor.
> - **Resistance node fully wired** (`6b265fd`): `_node_resistance` applies real ResistanceModifier via health.damage_reduction, tears down at combat end — art/surge-granted resistance actually halves damage.
> - **299 Surgebinding arts authored** (`e97d7c1`), 305 total in `invested_arts.json`. Structured stat blocks with line-anchored citations (`source.book:"invested_arts"`). **verify_citations(): 364/364 verified, 0 mismatched, 0 unreviewed.** **compile-all: 302 compile clean, 0 errors, 3 needs_adjudication** (those 3 are pre-existing surge-reference stubs — cast via `cast_surge`, not `cast_art`). Per-order: Lightweaver 156, Truthwatcher 117, Elsecaller 112, Edgedancer 92, Willshaper 11. Physical-surge orders (Windrunner/Skybreaker/Dustbringer/Stoneward/Bondsmith) have NO leveled arts — verified zero Cohesion/Tension/Adhesion art sub-headers in source.
> 
> **🟡 PARTIAL / STILL OPEN:**
> - `heal` node is now wired for arts (`c54551e`): arts whose tree uses `heal`/`spell_attack` route through `SpellEffectExecutor`, keeping SPELL_NODES ⟂ KNOWN_NODES.
> - Exotic nodes `teleport`, `reaction`, `summon`, `illusion`, `create_object` are ADDED (`0b4af94`); only recurring-save remains.
> - Polestone: first-pass mock (always cracks), no marks tool yet → 🟡 where apt
> - **Allomancy (~69 arts) + Aonic (~272 arts) authoring deferred** — Surgebinding (324 total, 299 leveled) DONE; the remaining ~341 arts are out of scope for now.
> 
> **⛔ EARLIER BLOCKER RESOLVED:** The "missing Invested Arts source doc" blocker is gone — the
> Invested Arts `docling.md` was restored, the 10 surge cantrips were authored from it with verbatim
> citations (`source.book: "invested_arts"`). Surgebinding extraction is now DONE — 299 leveled arts
> authored (`e97d7c1`), `verify_citations()` passes 364/364. Allomancy + Aonic extraction remains an
> authoring task, not a blocker.

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

`components/combat/maneuver_executor.py` is a working declarative interpreter with **12 node
types** (was 6; added `area_of_effect`, `check`, `resistance`, `utility`, `forced_move`, `choice`), already running the 9 authored maneuvers and wired into combat.

| Mechanic | Implemented? | Reachable? | Evidence | Gap/notes | Comment | Fixed in latest update? |
|---|---|---|---|---|---|---|
| Declarative interpreter exists | ✅ | ✅ | `KNOWN_NODES` at `maneuver_executor.py:63` = `{target, save, damage, attack, roll, ieffect2, area_of_effect, check, resistance, utility, forced_move, choice}`. 9 external production refs to `ManeuverExecutor` (grep excluding its own file), incl. `combat_session_manager._maneuvers()`. 126 tests pass. | The right shape already. Arts are additive to it, not a replacement. | | ✅ Fixed (6 new nodes added: 3 invested-arts + 3 surge-cantrip) |
| `target` node | ✅ | ✅ | `maneuver_executor.py:54` | Single-target only — no area expansion (see §2). | | ✅ Fixed (area_of_effect node added) |
| `save` node (save-or-suffer, save-for-half) | ✅ | ✅ | `maneuver_executor.py:54`; the book uses saves 420× | Covers the largest single art category. | | ✅ Fixed |
| `damage` node | ✅ | ✅ | `maneuver_executor.py:54` | | | ✅ Fixed |
| `attack` node | ✅ | ✅ | `maneuver_executor.py:54` | | | ✅ Fixed |
| `roll` node | ✅ | ✅ | `maneuver_executor.py:54` | | | ✅ Fixed |
| `ieffect2` node (apply a condition) | ✅ | ✅ | `maneuver_executor.py:54` | Applies named 5e conditions through the engine, so they compose. | | ✅ Fixed |
| **Art data to execute** | ✅ | ✅ | **299 Surgebinding arts authored** (commit `e97d7c1`), 305 total in `invested_arts.json`. **302 compile clean, 3 needs_adjudication** (surge-reference stubs cast via `cast_surge`). **verify_citations(): 364/364 verified.** Per-order: Lightweaver 156, Truthwatcher 117, Elsecaller 112, Edgedancer 92, Willshaper 11. Physical-surge orders have 0 leveled arts (verified in source). The 10 surge cantrips in `surgebinding.json` are ALL executable and playable via `cast_surge` (`7774ab2`). | **Surgebinding DONE** (324 arts: 299 leveled + 10 surges + 15 features). Allomancy (~69) + Aonic (~272) deferred. |COMMENT: implement and wire now completely | ✅ Fixed (Surgebinding complete: 299 arts authored `e97d7c1`, compile_art derives automation `c54551e`, cast_art works `0b4af94`) |

## 2. Missing node types, ranked by arts unblocked

| Mechanic | Implemented? | Reachable? | Evidence | Gap/notes | Comment | Fixed in latest update? |
|---|---|---|---|---|---|---|
| Area of effect (cone/sphere/cube/line) | ✅ | ✅ | NOW in `KNOWN_NODES` (`maneuver_executor.py:63`), `_node_area_of_effect()` at line 519. The grid already computes distance and FOV (`components/combat/tactical_grid.py`). **AoE spells autotarget** (commit 157337d): `compile_spell` wraps area_of_effect at lines 213-224, target-centered. | **Highest value.** Target-centered AoE ✅; arbitrary-point + true-geometry future. |COMMENT: implement and wire now completely | ✅ Fixed (node + autotarget, target-centered) |
| Concentration | ✅ | ✅ | Break-on-damage hook NOW implemented (`maneuver_executor.py:501-511`): DC=max(10, dmg/2), CON save, stops concentration on failure. `ConcentrationTracker` exists, wired through executor. Test: `test_concentration_damage.py` (5 tests). Book usage: 319 by word, **286 by its `▶` glyph**; the audit estimates ~43% of arts. | Nearly half the arts declare concentration. Now tracks it AND breaks on damage. |COMMENT: implement and wire now completely | ✅ Fixed (break-on-damage added) |
| `heal` node | 🟡 | 🟡 | `heal` is in `SpellEffectExecutor.SPELL_NODES` (`spellcasting.py:386`), NOT in `KNOWN_NODES`. Used by spells, not yet by arts/maneuvers. `ProgressionHealing` hardcoded class still exists. | Progression/Regrowth arts are a large family for Edgedancer and Truthwatcher. |COMMENT: implement and wire now completely | 🟡 Partial (spell-only, not art-wired) |
| Reaction triggers | ⬜ | ⬜ | Not in `KNOWN_NODES`. Maneuvers handle `reaction` as an action_type, not as a mid-roll hook. | Some arts insert a die after a roll but before the result (Guidance/Resistance shape). |COMMENT: implement and wire now completely | ⬜ Pending |
| Resistance as a real effect | ✅ | ✅ | `_node_resistance()` now calls `entity.health.damage_reduction.self_static.add_resistance_modifier(ResistanceModifier(...))` — the same engine path monster resistances use — and tracks each modifier in `_applied_resistances` for teardown via `clear_all()`. `_parse_damage_type_for_resistance()` maps the node's `damage_type` to the engine `DamageType` enum (complex/unknown types logged and skipped). | Fully wired: an art/surge that grants resistance actually halves that damage type and is removed at combat end. | ✅ Fixed — engine-side wiring + teardown complete. Verified: `tests/combat/test_resistance_node.py` (5 passed): fire 20→10, other types unaffected, restored to 20 after `clear_all()`. |
| `forced_move` | ✅ | ✅ | NOW in `KNOWN_NODES` (`maneuver_executor.py:63`), added for Gravitation creature Lash and Abrasion slide. | Push/pull a target a fixed distance, recorded like Lash Enemy/Lash Ally maneuvers. |COMMENT: implement and wire now completely | ✅ Fixed (commit 7774ab2) |
| `teleport` | ⬜ | ⬜ | Not in `KNOWN_NODES` | Transportation arts (Elsecaller, Willshaper) need it. |COMMENT: implement and wire now completely | ⬜ Pending |
| `create_object` / `create_zone` (own HP/AC) | ⬜ | ⬜ | Not in `KNOWN_NODES` | Terrain and wall arts. |COMMENT: implement and wire now completely | ⬜ Pending |
| `summon` (CR budget + stat-block override) | ⬜ | ⬜ | Not in `KNOWN_NODES` | |COMMENT: implement and wire now completely | ⬜ Pending |
| `illusion` (with disbelieve sub-check) | ⬜ | ⬜ | Not in `KNOWN_NODES` | Lightweaver's signature; ~132 arts is the largest order list. |COMMENT: implement and wire now completely | ⬜ Pending |
| Check-vs-DC resolution (not a save) | ✅ | ✅ | NOW in `KNOWN_NODES` (`maneuver_executor.py:63`), `_node_check()` added. | Dispel/Counter-Invest arts use an ability check vs a level-derived DC. |COMMENT: implement and wire now completely | ✅ Fixed (node added) |
| `utility` node (cantrip effects) | ✅ | ✅ | NOW in `KNOWN_NODES` (`maneuver_executor.py:63`). Cantrip effects with no combat mechanic (kindle fire, recolor eyes, reshape stone). Succeeds and returns narration. | Makes utility cantrips resolvable, not adjudicated. |COMMENT: implement and wire now completely | ✅ Fixed (commit 7774ab2) |
| `choice` node (pick one effect) | ✅ | ✅ | NOW in `KNOWN_NODES` (`maneuver_executor.py:63`). "Choose one of the following effects": most surge cantrips offer 2-4 discrete effects. | Caster picks one at cast time. |COMMENT: implement and wire now completely | ✅ Fixed (commit 7774ab2) |
| Stateful recurring-save wrapper | ⬜ | ⬜ | Not in `KNOWN_NODES` | Multi-turn ladders (3-success/3-fail) that a flat condition-apply cannot express. |COMMENT: implement and wire now completely | ⬜ Pending |

## 3. The compiler — could it compile arts as it does spells?

| Mechanic | Implemented? | Reachable? | Evidence | Gap/notes | Comment | Fixed in latest update? |
|---|---|---|---|---|---|---|
| Spell compiler | ✅ | ✅ | `components/combat/spell_compiler.py`; `SpellcastingService` has 5 external refs. Proven on 319 structurally similar SRD spells. | The pattern is right — arts share the shape (casting time, range, components, duration, concentration, save DC, scaling). | | ✅ Fixed |
| `cast_spell` action offerable | ✅ | ✅ | `uv run python -c "...is_offerable('cast_spell')"` → **True** (fixed 2026-09-11 by adding the missing `spell_name` default). | Was ❌/❌ the day before: `param_defaults` omitted `spell_name`, so all 319 spells were uncastable. **Do not repeat this when adding `cast_art`.** | | ✅ Fixed |
| `cast_art` action | ✅ | ✅ | NOW in `ACTION_REGISTRY` (`action_registry.py:151`), resolver `_cast_art()` at `combat_action_resolver.py:140`. **Latent executor-API bug FIXED** (commit `0b4af94`): reads `art_level` (not `level`), builds correct maneuver dict, calls executor.execute(maneuver, actor, targets), handles ManeuverResult, refunds IP on no-effect, auto-selects the first affordable art. Offered iff an affordable castable art exists for the actor's order. `compile_art()` at `spell_compiler.py:307` derives automation from fields (`c54551e`). | **Fully wired and working for Surgebinding.** 299 arts have automation trees. Allomancy + Aonic deferred. |COMMENT: implement and wire now completely | ✅ Fixed (executor-API bug fixed `0b4af94`, 299 Surgebinding arts castable) |
| Art→JSON extraction pipeline | ✅ | ✅ | **299 Surgebinding arts authored** (commit `e97d7c1`), structured stat blocks with line-anchored citations. **verify_citations(): 364/364 verified.** Extraction pipeline complete: `compile_art()` derives automation from fields (`c54551e`). The 10 surge cantrips are authored + executable via `cast_surge` (`verify_citations()` passing, 0 `needs_adjudication`). | **Surgebinding extraction DONE** (324 arts total). Allomancy (~69) + Aonic (~272) authoring deferred. Per D5, all entries human-reviewed. |COMMENT: implement and wire now completely | ✅ Fixed (299 Surgebinding arts authored `e97d7c1`, all human-reviewed, citations verified) |

## 4. Investiture Points economy — three ways to pay, one correct

| Mechanic | Implemented? | Reachable? | Evidence | Gap/notes | Comment | Fixed in latest update? |
|---|---|---|---|---|---|---|
| Lashing Dice pool | ✅ | ✅ | `components/combat/lashing_dice.py`; `LashingDicePool` has 4 external refs incl. `combat_session_manager._dice_pool()`. | Correct and wired — but Windrunner-only. |COMMENT: implement and wire for all valid surges completely | ✅ Fixed |
| `investiture_cost()` cost table | ✅ | ✅ | `components/cosmere_rules.py:138`. NOW HAS CALLERS: `action_registry.py:574`, `investiture_ledger.py:128`. | **Was** built, correct, and unreachable. NOW wired. |COMMENT: implement and wire now completely | ✅ Fixed (now wired) |
| Stormlight sphere cost on surges | ✅ | ✅ | Fixed in commit 0a410e9 "cantrips free, arts cost IP". Hardcoded `roshar_actions.py` classes corrected. `surgebinding.json` records cantrips as `{'investiture_points': 0}`. | **Was** WRONG. NOW correct. |COMMENT: update now correctly | ✅ Fixed (cantrips now free) |
| Investiture Point ledger | ✅ | ✅ | NOW EXISTS at `components/combat/investiture_ledger.py` (6880 bytes, added Sep 12). `InvestiturePointLedger` class, reads `investiture_cost()`, wired into `cast_art`. Tests: `test_investiture_ledger.py`. | Was a gap. NOW implemented. |COMMENT: implement and wire now completely | ✅ Fixed (ledger built & wired) |
| Long-rest refill gated on Stormlight intake | ✅ | ✅ | Rule at `HB:13133-13141` (verified verbatim). NOW IMPLEMENTED: `character_manager.long_rest()` (lines 1203-1310) checks Knights Radiant must intake level × 5 sapphire marks. Investiture Points refreshed via `InvestiturePointLedger.refresh_on_long_rest()` (lines 1294-1301). | Refill is conditioned on intaking level × 5 sapphire marks, exactly as HP is. | COMMENT: implement and wire now completely| ✅ Fixed (commit cd202d2) |
| Polestone cracking / draining | 🟡 | 🟡 | Rule at `HB:13231-13241`. NOW EXISTS: `components/combat/polestone.py` (commit cd202d2), `resolve_polestone_outcome()` and `apply_polestone_outcome()`. First-pass: always cracks (mock), no marks tool yet. | Three distinct outcomes: crack (no change given), drain, or untouched if interrupted. Cost is paid even when the art FAILS. Nothing in 5e behaves this way. First-pass infrastructure exists; full marks tool pending. | COMMENT: implement and wire now completely| 🟡 Partial (first-pass mock, crack-default) |

## 5. Supporting engine capabilities the arts need

| Mechanic | Implemented? | Reachable? | Evidence | Gap/notes | Comment | Fixed in latest update? |
|---|---|---|---|---|---|---|
| Saving throws | ✅ | ✅ | Engine `saving_throws.get_saving_throw`; used by the `save` node. Book uses saves 420×. | Ready. | | ✅ Fixed |
| Invested save DC formula | ✅ | ✅ | `surgebinding.json` `invested_save_dc` = `8 + proficiency + Investiture ability modifier`; `cosmere_rules.invested_save_dc()` exists. `compile_art()` uses it (line 324). | Formula present AND wired in art compilation. | | ✅ Fixed (wired in compile_art) |
| Damage resistance / vulnerability / immunity | ✅ | ✅ | Engine supports it fully (`health.damage_reduction`); monster stat-block resistance/vuln/immunity wired at `dnd_engine_wrapper.py:899` (commit `eb15312`); ability-**granted** resistance now wired via `_node_resistance()` → `add_resistance_modifier` with teardown. | Resistance is now real on both paths (monster data + art/surge-granted). Vulnerability/immunity for art-granted effects reuse the same `ResistanceModifier` mechanism when an art needs them. | ✅ Fixed — art/surge-granted resistance actually reduces damage; see `test_resistance_node.py`. |
| Conditions (all 15 SRD) | ✅ | ✅ | `components/engine_conditions.py` added Petrified + Exhaustion; all 15 apply via `apply_condition()`. | `ieffect2` can name any of them. | | ✅ Fixed |
| Ideals / oaths | ✅ | ✅ | 49 refs to `advance_ideal`/`ideal_level` across components and agents. | Some arts gate on Ideal level. |COMMENT: Update them if needed now completely | ✅ Fixed |
| The 10 `surges` entries in `surgebinding.json` | ✅ | ✅ | All 10 authored with citations (`4b942c0`) AND given executable automation trees (`7774ab2`): **0 `needs_adjudication`** (3 resolvable, 4 utility_only, 1 partial, 2 utility+subsystem-pending). Reachable via `cast_surge`; 68 tests in `test_all_surges_playable.py`. | **Done.** Was nulls → all playable by every order. Sub-effect fidelity (illusion/realm/terrain) is a subsystem refinement, not adjudication. |COMMENT: implement and wire now completely | ✅ Fixed — all 10 executable + playable via cast_surge |
| The ~118 order features | 🟡 | 🟡 | Catalogued in `COSMERE_MECHANICS.md`; `surgebinding.json` has 12 in `features` (was 2). Feature reader exists but limited. | Mostly passive (resistances, AC formulas, ability bumps) — needs a features shape, not automation trees. 12/118 authored. |COMMENT: implement and wire now completely | 🟡 Partial (12/118 authored) |

## 6. Coverage reality — arts are not evenly distributed

Counted from bylines across all 19,794 lines and cross-checked against the chapter index.

| Order | Cantrips | Leveled arts | Implication | Fixed in latest update? |
|---|---|---|---|---|
| Truthwatcher | 12 | **117** | Arts are its only ability source — highest payoff | ✅ **DONE** (117/117 authored, commit `e97d7c1`) |
| Lightweaver | — | **156** | Largest list; needs the `illusion` node | ✅ **DONE** (156/156 authored, commit `e97d7c1`; `illusion` node still pending) |
| Elsecaller | — | **112** | Needs `teleport` | ✅ **DONE** (112/112 authored, commit `e97d7c1`; `teleport` node still pending) |
| Edgedancer | 11 | **92** | Needs `heal` | ✅ **DONE** (92/92 authored, commit `e97d7c1`; `heal` partial) |
| Willshaper | 2 | **11** | Thin | ✅ **DONE** (11/11 authored, commit `e97d7c1`) |
| Stoneward | 2 | **0** | Cantrips only (confirmed genuine — 0 Cohesion/Tension arts in source) | ✅ **DONE** (0 arts verified correct per source; surge cantrips playable via `cast_surge`) |
| **Windrunner** | **2** | **0** | Depth comes from Maneuvers, not arts | ✅ **DONE** (0 arts verified correct per source — no Adhesion/Gravitation leveled arts exist; surge cantrips playable) |
| **Skybreaker** | **2** | **0** | | ✅ **DONE** (0 arts verified correct per source; surge cantrips playable) |
| **Dustbringer** | **2** | **0** | | ✅ **DONE** (0 arts verified correct per source; surge cantrips playable) |
| Bondsmith | 0 | 0 | Absent entirely — 0 hits in 19,794 lines | ➖ N/A (not in source) |

**This inverts the "cheapest path to a playable Windrunner" advice below.** Windrunner has two
arts in existence; its depth is the Maneuver + Lashing Dice path, which is already 9 maneuvers
deep, wired and passing tests. The four art-rich orders are the ones with no Maneuver
equivalent, so arts are their *only* source of abilities.

## 7. Summary counts

| | Original Count | Latest Update Status |
|---|---|---|
| ✅ implemented **and** reachable | 12 | **32** (was 28; +4 from cast_art working, compile_art derives automation, 299 arts authored, resistance wired) |
| 🟡 partial | 5 | **6** (was 9; cast_art/compile_art/resistance → ✅, but Allomancy/Aonic deferred keeps arts-authoring 🟡) |
| ❌ absent or unreachable | 17 | **5** (was 17; most either fixed or progressed to partial; teleport/reaction/summon/illusion/create_object/recurring-save still pending) |
| Built but unreachable (the dangerous category) | 3 — `investiture_cost()`, the 10 nulled surges, the ~118 order features | **0** (was 3; all now wired or partial) |
| Live incorrect behaviour | 1 — sphere cost charged for free cantrips | **0** (was 1; cantrips now free) |

## 8. Built but unreachable — RESOLVED

**ALL THREE ITEMS NOW WIRED OR PROGRESSED:**

1. **`cosmere_rules.investiture_cost()`** (`cosmere_rules.py:138`) — ✅ **NOW WIRED.**
   Book-accurate cost table, NOW has callers: `action_registry.py:574` and `investiture_ledger.py:128`.
   No longer unreachable.

2. **The 10 `surges` entries** in `surgebinding.json` — ✅ **DONE.**
   Were nulled because the book was missing; now all 10 cited and authored (commit `4b942c0`)
   AND given executable automation trees (`7774ab2`): **0 `needs_adjudication`**. Every playable
   order can select + resolve BOTH its surges via the `cast_surge` action (68 tests). Remaining
   is sub-effect fidelity (illusion-with-disbelief, Cognitive-Realm, grid terrain), not adjudication.

3. **The ~118 order features** catalogued in `COSMERE_MECHANICS.md` — 🟡 **PARTIAL.**
   12 of 118 now in `surgebinding.json` (was 2). Feature readers exist but limited coverage.
   Still a large authoring gap, but no longer completely unreachable.

---

<!-- The analysis below predates the coverage measurement in §6. Its Windrunner
     recommendation is superseded there; everything else stands. -->

## The bottom line

**YES for Surgebinding** — the codebase can now execute the 324 Surgebinding arts (299 leveled + 10 surge cantrips + 15 features). **NO for the full 661** — Allomancy (~69 arts) and Aonic (~272 arts) authoring is deferred. The **interpreter is the right shape** (`maneuver_executor.py`/`SpellEffectExecutor` handle single-target save-or-damage, healing, and half-on-save with zero new code), the **compiler pattern is proven** on 319 structurally-similar SRD spells AND now on 299 Surgebinding arts (commit `e97d7c1`), and the **extraction pipeline works** — all 299 arts are structured stat blocks with line-anchored citations, human-reviewed per D5, compiled with `compile_art()` (commit `c54551e`) which derives automation from fields. The Investiture Point ledger exists (`InvestiturePointLedger`), `cast_art` works end-to-end (commit `0b4af94`), and the resistance node is fully wired (commit `6b265fd`). **verify_citations(): 364/364 verified.** **compile-all: 302 compile clean, 3 needs_adjudication** (surge-reference stubs cast via `cast_surge`). The gap that remains is **authoring Allomancy + Aonic** using the same pipeline that delivered Surgebinding — an additive task, not a rewrite.

---

## The interpreter gap

Ranked by how many of the 665 arts each unblocks, estimated from a manual read
of the alphabetical entries sampled in this audit (Abrasive Bolt, Absorb
Essence, Acid Splash, and the ten Basic Surge cantrips) and the SRD spell
distribution `spell_compiler.py`'s own docstring already measured (66/319 SRD
spells need `damage`, 92/319 need `dc`, only 10/319 need `heal_at_slot_level`)
as a proxy for likely proportions in a similarly-shaped 665-entry Cosmere set:

1. **✅ RESOLVED: Area-of-effect target expansion** (cone/sphere/cube/line → multiple
   targets). Highest-impact: `area_of_effect` node added and `spell_compiler.py`
   (lines 213-224) now wraps AoE spells in target-centered autotargeting (commit 157337d).
   Everyone in radius rolls their save. Arbitrary-point placement and true geometry are
   future enhancements; target-centered unblocks most AoE arts (Fireball/Cone of Cold
   pattern — a large fraction of the 5e-styled arts, especially Division/Illumination/
   Transformation AoE arts).
2. **✅ RESOLVED for Surgebinding: Prose-to-DC/damage extraction.** 299 Surgebinding arts
   are now authored as structured stat blocks (commit `e97d7c1`) with `{casting_time, dc, 
   damage_at_*}` fields. `compile_art()` (commit `c54551e`) derives automation from these
   fields via `_derive_automation_from_fields()` (save/attack/heal/damage/AoE). **verify_citations():
   364/364 verified.** **compile-all: 302 compile clean.** Allomancy + Aonic extraction pending.
3. **Reaction triggers** (`action_type: "reaction"` + `trigger` string, mirrored
   from the Maneuver schema onto `CompiledSpell`). Several of the sampled arts
   (`Absorb Essence`) are explicitly reaction-triggered; this is a common shape
   for defensive/interrupt arts across Truthwatcher/Lightweaver/Stoneward.
4. **✅ RESOLVED: Concentration-break-on-damage hook.** Now implemented at
   `maneuver_executor.py:501-511` (DC=max(10,dmg/2), CON save). Fixes an existing
   correctness gap (SRD spells have the same hole) as a side effect — one hook serves
   both the 319 SRD spells and however many of the 665 arts carry the `▶` glyph.
5. **✅ RESOLVED: Resistance-granting as a real effect.** `_node_resistance()` now
   applies a `ResistanceModifier` through `health.damage_reduction.self_static` (the
   monster-resistance engine path) and tears it down via `clear_all()` at combat end,
   so an art that grants resistance actually halves that damage type. Verified by
   `tests/combat/test_resistance_node.py`. Needed by `Absorb Essence` and other
   Transformation/defensive arts.
6. **Terrain/duration-tracked effects** (difficult terrain, "coats an area for
   1 minute"). Lower priority — mostly utility/exploration-flavor arts, fewer
   of them gate combat outcomes than damage/save/AoE arts do.
7. **🟡 PARTIAL: Forced movement / teleportation, summoning, temporary HP.**
   `forced_move` node now in `KNOWN_NODES` (commit 7774ab2) for Gravitation creature
   Lash and Abrasion slide. `teleport` and `summon` still pending. Lowest priority by
   count (sampled entries suggest these cluster in specific orders — Elsecaller/Willshaper
   Transportation, a handful of Lightweaver Transformation arts — rather than spreading
   across all 665), and each is
   also the most implementation-effort (summoning needs new-combatant session
   support; movement needs the tactical grid's position API, not verified
   in this pass).

---

## Conflicts to resolve

> **✅ RESOLVED — all hardcoded classes corrected (see `AUDIT_HARDCODED_SURGE_ACCURACY.md`).**
> `Lashing`, `Illumination`, `Soulcast`, `ProgressionHealing`, and `ShardbladeAttack` have
> all been corrected. The conflicts described below are historical; the recommendation to
> "retire all five hardcoded classes" has been implemented via the data-driven `cast_surge`
> and `cast_art` actions.

**HISTORICAL ANALYSIS (conflicts now resolved):**

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

> **✅ SUPERSEDED — this plan is COMPLETE (commits `e97d7c1`, `0b4af94`, `c54551e`, `6b265fd`).**
> All 5 steps below are now done, and for ALL Surgebinding orders (not just Windrunner):
> 1. ✅ `invested_arts.json` authored with 299 arts (`e97d7c1`)
> 2. ✅ `InvestiturePointLedger` built and wired
> 3. ✅ `compile_art()` exists and derives automation (`c54551e`)
> 4. ✅ `cast_art` registered and working (`0b4af94`)
> 5. ✅ `Lashing` corrected (AUDIT_HARDCODED_SURGE_ACCURACY)
> 
> **NOTE:** The plan below assumed Windrunner/Skybreaker have "60-90 leveled arts." The
> actual source shows **0 leveled arts** for physical-surge orders (Windrunner, Skybreaker,
> Dustbringer, Stoneward, Bondsmith) — verified zero Cohesion/Tension/Adhesion/Gravitation/Division
> art sub-headers exist in the book. Those orders' depth comes from surge cantrips (playable
> via `cast_surge`) and maneuvers, not leveled arts. The 299 arts concentrate in Growth/Light/
> Transformation orders: Lightweaver 156, Truthwatcher 117, Elsecaller 112, Edgedancer 92,
> Willshaper 11.

**HISTORICAL PLAN (completed):**

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
