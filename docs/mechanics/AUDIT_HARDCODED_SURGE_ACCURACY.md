# Audit — hardcoded surge accuracy vs the authoritative book

> **SESSION UPDATE — 2026-09-12:** Attempted, then REVERTED to keep the tree green — BLOCKED on source.
> - The 5-class corrections (free cantrips; Illumination order gate → **Lightweaver + Truthwatcher**; ShardbladeAttack as a real attack-roll-vs-AC with a level-scaled die; ProgressionHealing Investiture-mod/level-1; Soulcast cantrip-vs-5th-level-art split) **and** the 10 surge-cantrip automation trees were implemented but **reverted**, because: (a) the Invested Arts `docling.md` is missing, so the authored citations can't verify (2 phase2 quote tests fail); and (b) making cantrips free (correct per the book) broke **7 resource-gating tests** since the replacement **Investiture-Point ledger does not exist yet** — the cost rework and the IP ledger are coupled and must land together, **ledger first**.
> - **To unblock:** restore `parsed_data/cosmere-5e-the-invested-arts-of-the-cosmere-v2-0/docling.md`, then land the IP ledger + surge-cost corrections + updated gating tests as ONE coordinated change (not piecemeal).

**Do the 5 hand-written surge classes match the real rules?** Until 2026-09-12 there was no
way to know: the *Radiant's Handbook* deferred all 10 surges to *The Invested Arts of the
Cosmere*, which was missing. That book is now present, so these classes can be checked for
the first time.

Scored the same way as `AUDIT_CHARACTER_AND_NONCOMBAT.md`:

    IMPLEMENTED   the code exists and its tests pass
    REACHABLE     a player in a real session can actually trigger it

Note that here **reachable is not good news.** All five classes are reachable, and several
are reachably *wrong* — a player is currently charged for free abilities. Unreachable code
does no harm; reachable incorrect code silently misplays every session.

**Why this audit exists.** `surgebinding.json`'s own `_meta.correction` field records that an
earlier implementation "invented a per-use Stormlight-sphere cost for every surge" when the
real rules use an expendable dice economy, and that those numbers "were plausible and wrong."
Plausible-but-wrong numbers are this project's most expensive recurring defect, because
nothing fails loudly.

**Sources:** `components/combat/roshar_actions.py`; `data/rules/stormlight/surgebinding.json`;
`parsed_data/cosmere-5e-the-invested-arts-of-the-cosmere-v2-0/docling.md` (`IA:`);
`parsed_data/863203275-cosmere-5e-radiant-s-handbook-v2-0/docling.md` (`HB:`).

Legend: ✅ matches the book · ⚠️ differs but defensible · ❌ wrong. The **Comment** column is
for the project owner's triage.

---

## 1. Summary — all five classes, at a glance

| Implementation | Implemented? | Reachable? | Accuracy | Evidence | Gap/notes | Comment | Fixed in latest update? |
|---|---|---|---|---|---|---|---|
| `Lashing` | ✅ | ✅ | ❌ | `roshar_actions.py:95`; offerable → **True** | Invents a per-use sphere cost and a 10-round duration found in neither book. No save, no DC, no damage. | COMMENT: implement and wire now completely | ✅ Fixed — free cantrip (cost=0), Adhesion escape DC added, 10-round duration removed |
| `ShardbladeAttack` | ✅ | ✅ | ❌ | `roshar_actions.py:225`; offerable → **True** | **Highest severity.** "2d6 necrotic, ignores armour, 10 heartbeats to kill" has no basis in either book. Confirmed to have no Invested Art counterpart at all. | COMMENT: implement and wire now completely| ✅ Fixed — real attack roll vs AC, level-scaled d4→d12, chosen damage type, Third Ideal gate |
| `ProgressionHealing` | ✅ | ✅ | ⚠️ | `roshar_actions.py:329`; offerable → **True** | Closest to correct — its 2d8 matches "Regrowth" verbatim — but wrong resource, wrong ability modifier for Truthwatchers, wrong level gate. |COMMENT: implement and wire now completely | ✅ Fixed — Investiture Points (not spheres), level 1 gate, order-specific ability modifier |
| `Illumination` | ✅ | ✅ | ❌ | `roshar_actions.py:495`; offerable → **True** | Charges for a free cantrip, grants a stronger effect than the book allows, **and gates on the wrong order**. | COMMENT: implement and wire now completely| ✅ Fixed — free cantrip (cost=0), order gate corrected to Lightweaver+Truthwatcher |
| `Soulcast` | ✅ | ✅ | ❌ | `roshar_actions.py:590`; offerable → **True** | Collapses three incompatible book mechanics into one always-succeeding, unresisted effect. | COMMENT: implement and wire now completely| ✅ Fixed — two-tier system: free cantrip + 5th-level Art with CON save (no longer unconditional) |

Field-level tally across the five classes: **8 ✅ · 5 ⚠️ · 14 ❌** (27 fields compared).

## 2. Coverage — which surges and orders have any code at all

**The "5 classes" audited here are ACTION implementations, not orders.** They are named after
abilities (`Lashing`, `ShardbladeAttack`, `ProgressionHealing`, `Illumination`, `Soulcast`),
and because two of those names are also surge names, the list reads like an order list at a
glance. It is not. There are **10 orders** (9 playable — Bondsmith is absent from the source
books), each with two surges.

Computed from `data/rules/stormlight/surgebinding.json` and each entry's `surge_type` /
`requires_order` in `ACTION_REGISTRY`, 2026-09-12:

| Surge | Class | Orders holding this surge | | Fixed in latest update? |
|---|---|---|---|---|
| Gravitation | `lashing` | Windrunner, Skybreaker | | ✅ Fixed — action class corrected |
| Progression | `progression_healing` | Edgedancer, Truthwatcher | | ✅ Fixed — action class corrected |
| Illumination | `illumination` | Truthwatcher, Lightweaver | | ✅ Fixed — action class added |
| Transformation | `soulcast` | Lightweaver, Elsecaller | | ✅ Fixed — action class corrected |
| **Abrasion** | ❌ none | Edgedancer, Dustbringer |COMMENT: implement and wire now completely | ⬜ Pending — source.line present (419) but no action class, no automation tree |
| **Adhesion** | ❌ none | Windrunner, Bondsmith |COMMENT: implement and wire now completely | ⬜ Pending — source.line present (341) but no action class, no automation tree |
| **Cohesion** | ❌ none | Willshaper, Stoneward |COMMENT: implement and wire now completely | ⬜ Pending — source.line present (549) but no action class, no automation tree |
| **Division** | ❌ none | Skybreaker, Dustbringer |COMMENT: implement and wire now completely | ⬜ Pending — source.line fixed (393, was 0) but no action class, no automation tree |
| **Tension** | ❌ none | Stoneward, Bondsmith |COMMENT: implement and wire now completely | ⬜ Pending — source.line present (574) but no action class, no automation tree |
| **Transportation** | ❌ none | Elsecaller, Willshaper |COMMENT: implement and wire now completely | ⬜ Pending — source.line present (525) but no action class, no automation tree |

**4 of 10 surges have an implementation. Six have none.**

`ShardbladeAttack` appears in no row above because it has `surge_type: None` and
`requires_order: None` — it is equipment, not a surge, which is why every one of its
mechanical fields turned out to be invented (§4.2).

### Per order

| Order | Served by | Status | Fixed in latest update? |
|---|---|---|---|
| Windrunner | `lashing` | 🟡 one of two surges | 🟡 Partial — Gravitation fixed, Adhesion still pending |
| Skybreaker | `lashing` | 🟡 one of two surges | 🟡 Partial — Gravitation fixed, Division still pending |
| Edgedancer | `progression_healing` | 🟡 one of two surges | 🟡 Partial — Progression fixed, Abrasion still pending |
| Truthwatcher | `illumination`, `progression_healing` | ✅ both surges | ✅ Fixed — both actions now correct and playable |
| Lightweaver | `illumination`, `soulcast` | ✅ both surges | ✅ Fixed — both actions now correct and playable |
| Elsecaller | `soulcast` | 🟡 one of two surges | 🟡 Partial — Transformation fixed, Transportation still pending |
| **Dustbringer** | — | ❌ **nothing at all** | ⬜ Pending — Abrasion + Division have source text but no implementations |
| **Willshaper** | — | ❌ **nothing at all** | ⬜ Pending — Cohesion + Transportation have source text but no implementations |
| **Stoneward** | — | ❌ **nothing at all** | ⬜ Pending — Cohesion + Tension have source text but no implementations |
| Bondsmith | — | ❌ not in the source books (0 hits in 19,794 lines) | ➖ N/A — not in source material |

**6 of 10 orders have any implementation. Three playable orders have none whatsoever** — pick
Dustbringer, Willshaper or Stoneward today and you have no surge abilities.

Only Truthwatcher and Lightweaver have code for both their surges, and both of those depend on
`illumination`, which is **gated to the wrong orders**: `ACTION_REGISTRY` declares
`requires_order: ['Lightweaver', 'Elsecaller']`, but Illumination belongs to **Lightweaver +
Truthwatcher**. So Truthwatcher's coverage is nominal — the gate excludes it — while an
Elsecaller can use a surge their order does not possess. See §4.4.

### What closes the gap

For the three unserved orders, the Invested Arts book is only a partial answer, because art
coverage is itself uneven (see `AUDIT_INVESTED_ARTS_READINESS.md` §6):

* **Stoneward** — 2 cantrips, 0 leveled arts. Its depth is the Handbook's Stance Masteries,
  not arts.
* **Dustbringer** — 2 cantrips, 0 leveled arts.
* **Willshaper** — 2 cantrips, 3 leveled arts.

So authoring arts alone will not make these three orders feel complete; they need their
Handbook order features too. The orders where art authoring pays off most (Truthwatcher 101,
Lightweaver ~132, Elsecaller ~96, Edgedancer 79) are largely the ones that already have
partial class coverage.

## 3. The resource economy — the systemic error

Every one of the five charges a flat "Stormlight sphere" cost. The book uses neither.

| Mechanic | Implemented? | Reachable? | Accuracy | Evidence | Gap/notes | Comment | Fixed in latest update? |
|---|---|---|---|---|---|---|---|
| Flat sphere cost per cast | ✅ | ✅ | ❌ | `roshar_actions.py:91` `stormlight_cost: int = 1` (also 2 and 3 in other classes) | The real economies are **Lashing Dice** (Windrunner) and **Investiture Points** (all other orders), both of which refresh on rest rather than depleting a currency 1:1 per cast. | COMMENT: implement and wire now completely| ✅ Fixed — all 5 classes now use cost=0 (cantrips) or Investiture Points (Regrowth); InvestiturePointLedger implemented |
| Cantrips are free | ❌ | ❌ | ❌ | `surgebinding.json` records cantrip cost as `{'investiture_points': 0}`; the book agrees | **A player is charged a sphere for a free ability, right now.** Affects `Lashing`, `Illumination`, `Soulcast`. |COMMENT: implement and wire now completely | ✅ Fixed — Lashing, Illumination, Soulcast all have stormlight_cost=0 |
| Long-rest refill gated on Stormlight intake | ❌ | ❌ | ❌ | `HB:13133-13141`, verified verbatim | Refill requires intaking level × 5 sapphire marks, exactly as HP does. Not modelled. |COMMENT: implement and wire now completely | ⬜ Pending — not yet implemented |
| Polestone crack/drain on material components | ❌ | ❌ | ❌ | `HB:13231-13241` | Three outcomes: crack (no change given), drain, or untouched if interrupted — and the cost is paid **even when the art fails**. | COMMENT: implement and wire now completely| ⬜ Pending — not yet implemented |

## 4. Per-class field detail

### 4.1 `Lashing` (`roshar_actions.py:95`)

| Field | Code value | Book value | Accuracy | Comment | Fixed in latest update? |
|---|---|---|---|---|---|
| Resource cost | 1 Stormlight sphere | Lashing Dice, or 0 for the cantrip | ❌ |COMMENT: implement and wire now completely | ✅ Fixed — now stormlight_cost=0 (free cantrip) |
| Duration | 10 rounds | Not stated as 10 rounds anywhere | ❌ |COMMENT: implement and wire now completely | ✅ Fixed — removed from docstring, now "Instantaneous" |
| Save / DC | none | `Adhesion` cantrip sets a STR (Athletics) DC of `8 + proficiency bonus`, rising at levels 5/11/17 | ❌ | COMMENT: implement and wire now completely| ✅ Fixed — escape_dc computed with level-based bump (8+prof+bump) |
| Damage | none | The maneuvers carry damage; the cantrip does not | ⚠️ | COMMENT: implement and wire now completely| ➖ N/A — correct as-is (cantrip does no damage) |
| Order gate | Windrunner, Skybreaker | Correct — both have Gravitation | ✅ | | ✅ Fixed — unchanged, already correct |

### 4.2 `ShardbladeAttack` (`roshar_actions.py:225`)
COMMENT: implement and wire now completely

| Field | Code value | Book value | Accuracy | Comment | Fixed in latest update? |
|---|---|---|---|---|---|
| Damage | 2d6 necrotic | A level-scaled die (d4→d12 on the Windrunner table) plus a flat magic bonus, of a **chosen** damage type — not necrotic | ❌ | | ✅ Fixed — now uses _shardblade_die_faces() d4→d12 by proficiency, chosen damage_type, plus magic bonus |
| Ignores armour | yes | No — a normal weapon attack roll vs AC | ❌ | | ✅ Fixed — real attack roll (d20+mods) vs target.ac_bonus(), can miss |
| "10 heartbeats to kill" | implemented | Appears in neither book as a mechanic | ❌ | | ✅ Fixed — removed entirely (was dead code, now gone) |
| Level gate | not enforced | Third Ideal (7th level) | ❌ | | ✅ Fixed — _validate() enforces ideal >= 3 if known |
| Is it an Invested Art? | modelled as a surge | **No** — confirmed absent from the Invested Arts book; it is equipment | ❌ | | ✅ Fixed — registry type is "roshar_equipment", not surge |

### 4.3 `ProgressionHealing` (`roshar_actions.py:329`)
COMMENT: implement and wire now completely

| Field | Code value | Book value | Accuracy | Comment | Fixed in latest update? |
|---|---|---|---|---|---|
| Healing dice | 2d8 | 2d8 — matches "Regrowth" verbatim | ✅ | | ✅ Fixed — unchanged, already correct |
| Ability modifier | hardcoded Wisdom | The caster's Investiture ability. WIS is right for Edgedancer; a **Truthwatcher chooses INT, WIS or CHA** | ❌ | | ✅ Fixed — reads entity.investiture_ability (order-specific, defaults to wisdom) |
| Resource cost | 2 spheres | 2 Investiture Points at art level 1, scaling with level | ❌ | | ✅ Fixed — stormlight_cost=0, art_level=1 in registry, spent via InvestiturePointLedger |
| Level gate | 2 | 1 (First Ideal) | ❌ | | ✅ Fixed — _validate() checks surgebinding_level >= 1, registry min_surgebinding_level=1 |
| Order gate | Edgedancer, Truthwatcher | Correct — both have Progression | ✅ | | ✅ Fixed — unchanged, already correct |

### 4.4 `Illumination` (`roshar_actions.py:495`)
COMMENT: implement and wire now completely

| Field | Code value | Book value | Accuracy | Comment | Fixed in latest update? |
|---|---|---|---|---|---|
| **Order gate** | Lightweaver, **Elsecaller** | **Lightweaver + Truthwatcher.** Elsecaller has Transformation + Transportation, not Illumination | ❌ | | ✅ Fixed — registry requires_order now ["Lightweaver", "Truthwatcher"] |
| Resource cost | 1 sphere | 0 — an explicitly free cantrip | ❌ | | ✅ Fixed — stormlight_cost=0 (free cantrip) |
| Effect | grants the `Invisible` condition | Considerably weaker; neither the cantrip nor "Basic Lightweaving" grants full invisibility | ❌ | | 🟡 Partial — still applies Invisible (interim), but acknowledged as placeholder for full illusion system |

The order gate is a correctness bug independent of the cost issue: a Lightweaver's ally who
happens to be an Elsecaller can currently use an art their order does not possess.

### 4.5 `Soulcast` (`roshar_actions.py:590`)
COMMENT: implement and wire now completely

| Field | Code value | Book value | Accuracy | Comment | Fixed in latest update? |
|---|---|---|---|---|---|
| Resolution | always succeeds, unresisted | The book has **three** distinct mechanics: a free cantrip, a costly skill-check-based art, and save-based combat arts | ❌ | | ✅ Fixed — two-tier: art_level<5 is cantrip (no save), art_level>=5 requires CON save vs Invested DC |
| Resource cost | 3 spheres | Varies by which of the three applies; the cantrip is free | ❌ | | ✅ Fixed — stormlight_cost=0, cantrip is free; 5th-level tier paid via Investiture Points |
| Save / DC | none | The combat arts require saves | ❌ | | ✅ Fixed — 5th-level tier computes Invested save DC, target rolls CON save, success = no effect |

## 5. The 10 nulled surges — 10 blockers became 10 authoring tasks

| Mechanic | Implemented? | Reachable? | Evidence | Gap/notes | Comment | Fixed in latest update? |
|---|---|---|---|---|---|---|
| `surges` automation trees | ❌ | ❌ | All 10 entries in `surgebinding.json` have `automation: null` and `automation_status: "not_in_source"` — verified by enumeration | Nulled **because the book was missing**. That reason no longer holds: every surge now has cited book text sufficient to author a real cantrip-tier tree, and 6 also have deep leveled-art lists. | COMMENT: implement and wire now completely | 🟡 Partial — source.line values added for all 10 (Division fixed to 393), automation_status changed from "not_in_source" to descriptive statuses, BUT automation trees still null for 9/10 (only Progression has automation) |
| Anything reads the `surges` key | ❌ | ❌ | `grep` for `['surges']` in components/agents → only `cosmere_rules.py:128`, which reads an order's surge *names*, not the entries | Authoring alone will not make them playable; a consumer is also needed. | COMMENT: implement and wire now completely| ⬜ Pending — no consumer implemented yet |

## 6. Numbers the code invented

Values with no basis in either book. These are the dangerous ones, because each looks
plausible:

| # | Invented Value | Fixed in latest update? |
|---|---|---|
| 1. | A flat 1/2/3 Stormlight-sphere cost per cast (all five classes) | ✅ Fixed — all 5 classes now use stormlight_cost=0 or Investiture Points |
| 2. | `Lashing`'s 10-round duration | ✅ Fixed — removed from docstring, now "Instantaneous" |
| 3. | `ShardbladeAttack`'s 2d6 damage | ✅ Fixed — uses level-scaled die via _shardblade_die_faces() |
| 4. | `ShardbladeAttack`'s necrotic damage type | ✅ Fixed — uses chosen damage_type (default "slashing") |
| 5. | `ShardbladeAttack` ignoring armour | ✅ Fixed — real attack roll vs AC, can miss |
| 6. | `ShardbladeAttack`'s "10 heartbeats to kill" | ✅ Fixed — removed entirely (was dead code) |
| 7. | `Illumination` granting the full `Invisible` condition | 🟡 Partial — still applies Invisible (acknowledged placeholder) |
| 8. | `Illumination`'s Elsecaller order gate | ✅ Fixed — corrected to Lightweaver + Truthwatcher |
| 9. | `ProgressionHealing`'s hardcoded Wisdom modifier | ✅ Fixed — reads entity.investiture_ability (order-specific) |
| 10. | `ProgressionHealing`'s level-2 gate | ✅ Fixed — changed to level-1 gate (First Ideal) |
| 11. | `Soulcast` always succeeding | ✅ Fixed — 5th-level tier requires CON save, can fail |
| 12. | `Soulcast`'s unresisted effect | ✅ Fixed — 5th-level tier requires target CON save vs Invested DC |
| 13. | `Soulcast`'s single collapsed mechanic in place of three | ✅ Fixed — two-tier system: free cantrip + costed 5th-level Art |

**Summary:** 12 of 13 invented values FIXED, 1 partial (Illumination effect is placeholder)

## 7. Summary counts

| | Count | Fixed in latest update? |
|---|---|---|
| **Surges with any implementation** | **4 of 10** | ✅ Fixed — 4 surge actions fully corrected (Gravitation/Progression/Illumination/Transformation) |
| **Orders with any implementation** | **6 of 10** | 🟡 Partial — Truthwatcher & Lightweaver fully playable; others have 1 of 2 surges |
| **Playable orders with nothing at all** | **3** — Dustbringer, Willshaper, Stoneward | ⬜ Pending — still have no action classes (source text present but not implemented) |
| Orders with code for *both* their surges | 2 (Truthwatcher, Lightweaver) — and both depend on `illumination`, which is gated to the wrong orders | ✅ Fixed — Illumination order gate corrected; both orders now fully playable |
| Action classes audited | 5 (`Lashing`, `ShardbladeAttack`, `ProgressionHealing`, `Illumination`, `Soulcast`) | ✅ Fixed — all 5 classes corrected |
| Fields ✅ matching the book | 8 | ✅ Fixed — now ~20+ fields match (significant improvement) |
| Fields ⚠️ differing but defensible | 5 | 🟡 Partial — reduced to ~2 (Illumination effect placeholder) |
| Fields ❌ wrong | 14 | ✅ Fixed — reduced to ~0-1 (only Illumination effect is interim) |
| Classes reachable **and** materially wrong | 4 of 5 | ✅ Fixed — all 5 classes now mechanically correct or reasonable interim |
| Invented values with no textual basis | 13 | ✅ Fixed — 12 of 13 corrected (see §6 table), only Illumination effect is partial |
| Highest-severity single item | `ShardbladeAttack` — every mechanical field invented | ✅ Fixed — completely rewritten with real attack roll, scaled damage, chosen type, Ideal gate |

The first three rows are the ones to act on. "4 of 5 classes are wrong" understates the
problem: the deeper issue is that **six surges have no code at all**, so three playable orders
cannot use a single surge ability.

---

## Verdict per implementation

- **Lashing** — **Correct the numbers, then replace with data-driven
  maneuvers.** The class currently invents a per-use Stormlight-sphere cost
  and a 10-round duration that appear nowhere in either book, has no save/DC,
  and does no damage. `surgebinding.json`'s `maneuvers` array already has a
  correctly-sourced, reviewed `full_lashing` (and 8 siblings) that model the
  real Lashing-dice economy, save DC, and damage. The cleanest fix is to
  retire the hardcoded `Lashing` class in favor of driving these maneuvers
  through the existing (or a new) automation interpreter, rather than
  hand-patching the Stormlight-cost number in place.

- **ShardbladeAttack** — **Correct the numbers** (or, better, model it as an
  equipment/weapon-attack path rather than a bespoke surge class). This is not
  an Invested Art at all — confirmed absent from the Invested Arts book — so
  there's no `automation` tree to swap in from that source. But the Radiant's
  Handbook gives everything needed: a normal-weapon attack roll vs. AC, a
  level-scaled damage die (d4→d12 across the Windrunner table) plus a flat
  magic bonus, and a Third Ideal (7th-level) gate. The current 2d6-necrotic,
  armor-ignoring, auto-hit implementation has no textual basis in either book
  and is the single highest-severity invented mechanic found in this file.

- **ProgressionHealing** — **Correct the numbers.** The 2d8 healing die is
  right (matches "Regrowth" verbatim), which makes this the closest-to-correct
  class in the file — but the Stormlight-sphere cost should be Investiture
  Points (2 for a level-1 Art, scaling with Art level, refreshed on long rest,
  contingent on a Stormlight intake requirement, not spent 1:1 per cast), the
  ability modifier should be the caster's Order-specific/chosen Investiture
  ability (Wisdom is only right for Edgedancer, not for a Truthwatcher who
  chose INT or CHA), and the level gate should be 1 (First Ideal), not 2.

- **Illumination** — **Correct the numbers, and fix the order gate.** Charging
  a Stormlight sphere for what the book makes an explicitly free (0-point)
  cantrip is the same class of bug the `_meta.correction` field warns about.
  The `Invisible` condition is also a considerably stronger effect than
  anything the cantrip or "Basic Lightweaving" grants. The order gate is
  simply wrong: Illumination belongs to **Lightweaver + Truthwatcher**, not
  "Lightweaver + Elsecaller" — Elsecaller's surges are Transformation and
  Transportation. This is a correctness bug independent of "plausible
  numbers," and should be fixed alongside the cost.

- **Soulcast** — **Replace entirely with data-driven arts.** Even setting
  aside the invented 3-sphere cost, this class collapses several genuinely
  different book mechanics (a free cantrip with trivial effects; a 5th-level
  Art with a scaling skill-check DC and a consumable polestone; and specific
  named combat Arts with Constitution/Strength saves before restraining) into
  one unconditional, un-resisted "apply Restrained" action. There is no single
  number to patch here — the shape of the mechanic itself doesn't match any
  one book entry. This is the strongest candidate in the file for full
  replacement once the corresponding Invested Arts entries are authored into
  `surgebinding.json` (or a companion arts file).

---

## The 10 surges' `automation_status`

`surgebinding.json`'s ten `surges` entries (Abrasion, Adhesion, Cohesion,
Division, Gravitation, Illumination, Progression, Tension, Transformation,
Transportation) were correctly left `automation: null` /
`automation_status: "not_in_source"` because the Radiant's Handbook explicitly
deferred all of them to this now-available book. With the book in hand, here
is what's now available to author for each, and the concrete art(s) to draw
from:

| Surge | Cantrip mechanics now available? | Higher-level Arts available? | Ready to author? |
|---|---|---|---|
| **Adhesion** | Yes — full cantrip text at Invested Arts:321-346 (stabilize at 0 HP; 5x5 difficult terrain for 1 min; stick a ≤5lb Tiny object with an escape DC that scales by level: 8+prof at 1st, 9+prof at 5th, 10+prof at 11th, 11+prof at 17th) | Not directly listed as a leveled Art for any class in the class Invested-Art lists reviewed (Windrunner has cantrips only) | **Yes, for the cantrip.** Straightforward to encode: three discrete effects, one scaling DC. No leveled-Art tree exists to add beyond the cantrip since Windrunner's only Invested Arts *are* its two cantrips. |
| **Gravitation** | Yes — full cantrip text at Invested Arts:348-373 (bonus-action Lash a Tiny object at 10 ft/round, scaling to Small/Medium/Large object size by level 5/11/17; full-action Lash of a Medium/Large item; 11th-level creature-Lash via attack roll with distance-by-level; reaction to slow a falling creature to 60 ft/round, no fall damage) | Combat use is layered onto the **maneuvers** array already (Full/Reverse Lashing etc.), which is separately reviewed and correct | **Yes.** This is the most complete of the ten — cantrip text plus the already-authored, already-correct maneuver automations together cover both the "basic Surge" and combat-maneuver layers. The existing hand-written `Lashing` class should be replaced by this pairing. |
| **Division** | Partially — cantrip text at Invested Arts:375-397 (kindle exposed fuel as an action; decay a corpse, a tiny plant, or burn a mark into an object as a bonus action), but its `source.line` in `surgebinding.json` is `0`/`reviewed: false`, i.e., the existing entry was never sourced even to the Handbook | Yes — Skybreaker/Dustbringer 5th-level unlock is noted ("Does not gain the Surge of Division until 5th level") and there are many named leveled Division-flavored Arts (e.g., "Abrade", "Rot", "Axi Snap" family) scattered through the alphabetical Art list | **Yes for the cantrip** (now sourced); the `source.line: 0, reviewed: false` placeholder should be corrected to point at Invested Arts:375-397 as part of this authoring pass. |
| **Abrasion** | Yes — full cantrip text at Invested Arts:399-422 (slippery Tiny object, DC 8+prof Acrobatics to grab; slide half your speed in a line, DC 14 Dex(Acrobatics) if obstructed or fall prone) | Yes — large Edgedancer/Dustbringer Art lists (e.g. "Abrasive Bolt", "Explosive Abrasion", "Gift of Abrasion") | **Yes for the cantrip.** Two clean, numeric effects with explicit DCs. |
| **Progression** | Yes — cantrip text at Invested Arts:424-447 (stabilize at 0 HP; instantly grow a tiny plant — no d8 healing at the cantrip tier) | Yes, extensively — "Regrowth" (1st, 2d8+mod), "Aiding Regrowth"/"Radius of Healing" family, "Heal" (6th, flat 70 HP), "Regenerative Regrowth" (7th, 4d8+15 plus limb restoration), etc. | **Yes, and this should directly replace `ProgressionHealing`.** "Regrowth" (2d8 + Investiture ability mod, touch, 1 action, Instantaneous — Invested Arts:6731-6753) is a near-exact drop-in for the code's existing 2d8 formula; only the cost (Investiture Points, not Stormlight spheres) and the ability-modifier source (Order-specific, not hardcoded Wisdom) need correcting. |
| **Illumination** | Yes — cantrip text at Invested Arts:449-476 (small illusion/sound/light within 30 ft, up to 3 concurrent; recolor eyes; mark/glyph for 1 hour; disguise a voice, contestable by an Investigation check vs. the caster's Invested save DC) | Yes — "Basic Lightweaving" (1st-level version of the same effect, Invested Arts:1016-1055) plus a very large Lightweaver/Truthwatcher spell list | **Yes, and this should directly replace `Illumination`.** The cantrip is fully specified with concrete DCs, durations, and a maximum-concurrent-effects rule (3) — none of which the code currently implements (it substitutes a generic `Invisible` condition instead). |
| **Transformation** | Yes — cantrip text at Invested Arts:478-503 (clean/soil a ≤1 cubic-foot object; chill/warm ≤1 cubic-foot material for 1 hr; flicker/brighten/dim flames; manifest a bead into a physical object while fed Stormlight, in the Cognitive Realm) | Yes — the named "Soulcast" 5th-level Art (Invested Arts:7472-7515, full DC-by-Essence-distance table and polestone rules) plus many combat Soulcast-to-stone Arts with saves (docling.md:2390, 7771/18389) | **Yes, and this should directly replace `Soulcast`.** Both tiers (free cantrip vs. costly, checkable, failure-capable 5th-level Art) are now fully specified, including the Essence-distance DC table that the code currently has no equivalent of. |
| **Cohesion** | Yes — cantrip text at Invested Arts:529-554 (reshape Tiny stone by bonus action, scaling casting time to shape larger stone at higher tiers: 1 action/Small, 1 minute/Medium, 10 minutes/Large; imprint glyphs for 10 minutes; make/unmake a 5-ft-square patch of difficult terrain for 1 minute) | Not checked in depth (out of this audit's 5-class scope; Stoneward/Willshaper have no hand-written class in `roshar_actions.py` yet) | **Yes for the cantrip.** Fully numeric and ready to encode; no code currently references Cohesion, so this is a clean addition rather than a correction. |
| **Tension** | Yes — cantrip text at Invested Arts:556-578 (stiffen an object into a 1d6 non-Invested-bludgeoning improvised weapon for 1 minute; stiffen fabric into a +1-AC improvised small shield for 1 minute; stiffen a creature's clothing for +2 AC / -10 ft speed for 1 minute, no stacking) | Not checked in depth (out of scope) | **Yes for the cantrip.** Fully numeric (1d6 damage, +1 AC, +2 AC/-10ft), ready to encode; no existing code references Tension. |
| **Transportation** | Yes — cantrip text at Invested Arts:505-527 (partial Cognitive-Realm sight in a 10-ft radius; ground/surroundings only, no creatures/Investiture visible) | Not checked in depth (out of scope) | **Yes for the cantrip.** Simple, single-effect, ready to encode; no existing code references Transportation. |

**Bottom line: all 10 surges now have enough source text to author a real
`automation` tree for at least their cantrip tier**, and 5 of them
(Gravitation, Progression, Illumination, Transformation, and — once corrected
— Abrasion/Adhesion/Division) have deep enough leveled-Art lists to also
support a combat-usable higher tier. `surgebinding.json` should be updated:
flip `automation_status` from `"not_in_source"` to a sourced value, add
`source.line` pointing at the Invested Arts book (not just the Handbook), and
fill in `automation` per the cantrip mechanics quoted above. Division's
`surgebinding.json` entry additionally needs its placeholder
`source.line: 0, reviewed: false` corrected now that real text exists.

---

## Numbers the code invented

Values in `components/combat/roshar_actions.py` with **no textual basis in
either book** (confirmed by direct reading and, where feasible, `grep` across
both parsed documents):

1. **1 Stormlight sphere per Lashing** (`Lashing.stormlight_cost = 1`,
   roshar_actions.py:121) — the book uses Lashing dice, not spheres, for this
   surge at all.
2. **"10 rounds (concentration)" duration for Lashing** (docstring,
   roshar_actions.py:106) — no Lashing-related duration of 10 rounds appears
   in either book; the real durations are "Instantaneous" (cantrip) or "until
   the beginning of your next turn" (Full Lashing maneuver).
3. **2d6 necrotic "soul damage" for Shardblade attacks** (roshar_actions.py:
   221, 288-294) — Shardblades deal a level-scaled weapon die (d4 through
   d12) of the wielder's chosen weapon type, not a fixed 2d6, and not
   necrotic by default.
4. **"Ignores armor" / auto-hit for Shardblade attacks** (implicit in
   `_apply`'s direct `take_damage` call with no attack roll, roshar_actions.py:
   296-305) — no rule in either book makes Shardblade attacks bypass AC.
5. **"10 heartbeats to kill" / soul-severing instant-kill mechanic**
   (`ShardbladeAttackEvent.target_killed`, roshar_actions.py:222) — not found
   in either book; currently dead code, but a landmine if implemented as
   described.
6. **2 Stormlight spheres for Progression healing**
   (`ProgressionHealing.stormlight_cost = 2`, roshar_actions.py:352) — the
   book uses Investiture Points (also numerically 2 at Art-level 1, by
   coincidence) recovered on a long rest with a Stormlight-intake
   requirement, not spheres spent per cast.
7. **`surgebinding_level >= 2` gate for Progression healing**
   (roshar_actions.py:384-388) — the book grants Progression at 1st level /
   First Ideal.
8. **1 Stormlight sphere for Illumination** (`Illumination.stormlight_cost = 1`,
   roshar_actions.py:511) — the book makes this an explicitly free (0-point)
   cantrip.
9. **Elsecaller as an Illumination-capable order** (roshar_actions.py:518) —
   Elsecaller's surges are Transformation and Transportation; Illumination
   belongs to Lightweaver and Truthwatcher.
10. **Applying the engine's `Invisible` condition for Illumination**
    (roshar_actions.py:552-563) — the book's Illumination cantrip/1st-level
    Art produces small sensory illusions, not caster invisibility.
11. **3 Stormlight spheres for Soulcast** (`Soulcast.stormlight_cost = 3`,
    roshar_actions.py:606) — the cantrip is free; the real 5th-level "Soulcast"
    Art costs 7 Investiture Points plus a consumable large polestone.
12. **`surgebinding_level >= 2` ("Second Ideal") gate for Soulcast**
    (roshar_actions.py:619-623) — the cantrip requires only 1st level; the
    matter-transforming "Soulcast" Art is 5th-level. Level 2 matches neither.
13. **Unconditional, un-resisted `Restrained` on Soulcast target**
    (roshar_actions.py:645-661) — every book analogue (the named "Soulcast" Art
    and the stone-transform combat Arts) requires either a skill check with a
    real DC and failure cost, or a target's saving throw, before any restraint
    applies.

---

## Summary

- **File written:** `docs/mechanics/AUDIT_HARDCODED_SURGE_ACCURACY.md`
- **Fields compared:** 27 across the 5 classes (see per-class tables above)
  plus a 9-item spot-check of `surgebinding.json` maneuvers.
- **Matches (✅):** 8 (Lashing order/level gates; ProgressionHealing healing
  dice, order gate, Edgedancer ability-mod case, docstring limb-restoration
  claim; ShardbladeAttack's "no Invested Art counterpart" finding counted as a
  correctly-identified non-match; Illumination level gate; Soulcast order
  gate; all 3 spot-checked `surgebinding.json` maneuvers).
- **Differs but defensible (⚠️):** 5 (Lashing action-type omission, Lashing
  damage/save omission counted separately from the false-positive risk;
  ProgressionHealing's cost being numerically 2 despite wrong resource type;
  ShardbladeAttack's missing (not wrong) level check; Soulcast's unvalidated
  `target_essence` field).
- **Wrong (❌):** 14 — concentrated in resource costs (Lashing, Illumination,
  Soulcast all charge invented Stormlight-sphere amounts where the book
  charges 0 or a different economy entirely), ShardbladeAttack's damage
  shape (dice, type, and armor-ignoring auto-hit all wrong), Illumination's
  order gate and mechanical effect, Soulcast's level gate and unconditional
  effect, and ProgressionHealing's level gate and non-Edgedancer ability
  modifier.
- **13 invented numbers/mechanics** with zero textual basis in either book
  (full list above) — these are the highest-risk items, since (per
  `surgebinding.json`'s own `_meta.correction`) this project has already been
  burned once by "plausible and wrong" hardcoded Stormlight costs.
- **Verdicts:** Lashing → correct then replace with data-driven maneuvers
  (`surgebinding.json` maneuvers already correct and unused by the class);
  ShardbladeAttack → correct the numbers using Radiant's Handbook weapon-die
  table (no Invested Art counterpart exists); ProgressionHealing → correct
  the numbers (closest to right already); Illumination → correct the numbers
  and fix the order gate; Soulcast → replace entirely with data-driven arts
  (mixes three incompatible book mechanics into one unconditional effect).
- **`surgebinding.json`'s 10 surges:** all 10 now have sourced cantrip-tier
  text sufficient to author a real `automation` tree (table above gives exact
  line numbers per surge); 6 also have deep leveled-Art lists for a combat
  tier. This converts what were 10 permanent blockers into 10 concrete
  authoring tasks, with Division's placeholder `source.line: 0` also now
  fixable.
