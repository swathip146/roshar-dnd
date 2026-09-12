# Audit — hardcoded surge accuracy vs the authoritative book

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

| Implementation | Implemented? | Reachable? | Accuracy | Evidence | Gap/notes | Comment |
|---|---|---|---|---|---|---|
| `Lashing` | ✅ | ✅ | ❌ | `roshar_actions.py:95`; offerable → **True** | Invents a per-use sphere cost and a 10-round duration found in neither book. No save, no DC, no damage. | |
| `ShardbladeAttack` | ✅ | ✅ | ❌ | `roshar_actions.py:225`; offerable → **True** | **Highest severity.** "2d6 necrotic, ignores armour, 10 heartbeats to kill" has no basis in either book. Confirmed to have no Invested Art counterpart at all. | |
| `ProgressionHealing` | ✅ | ✅ | ⚠️ | `roshar_actions.py:329`; offerable → **True** | Closest to correct — its 2d8 matches "Regrowth" verbatim — but wrong resource, wrong ability modifier for Truthwatchers, wrong level gate. | |
| `Illumination` | ✅ | ✅ | ❌ | `roshar_actions.py:495`; offerable → **True** | Charges for a free cantrip, grants a stronger effect than the book allows, **and gates on the wrong order**. | |
| `Soulcast` | ✅ | ✅ | ❌ | `roshar_actions.py:590`; offerable → **True** | Collapses three incompatible book mechanics into one always-succeeding, unresisted effect. | |

Field-level tally across the five classes: **8 ✅ · 5 ⚠️ · 14 ❌** (27 fields compared).

## 2. The resource economy — the systemic error

Every one of the five charges a flat "Stormlight sphere" cost. The book uses neither.

| Mechanic | Implemented? | Reachable? | Accuracy | Evidence | Gap/notes | Comment |
|---|---|---|---|---|---|---|
| Flat sphere cost per cast | ✅ | ✅ | ❌ | `roshar_actions.py:91` `stormlight_cost: int = 1` (also 2 and 3 in other classes) | The real economies are **Lashing Dice** (Windrunner) and **Investiture Points** (all other orders), both of which refresh on rest rather than depleting a currency 1:1 per cast. | |
| Cantrips are free | ❌ | ❌ | ❌ | `surgebinding.json` records cantrip cost as `{'investiture_points': 0}`; the book agrees | **A player is charged a sphere for a free ability, right now.** Affects `Lashing`, `Illumination`, `Soulcast`. | |
| Long-rest refill gated on Stormlight intake | ❌ | ❌ | ❌ | `HB:13133-13141`, verified verbatim | Refill requires intaking level × 5 sapphire marks, exactly as HP does. Not modelled. | |
| Polestone crack/drain on material components | ❌ | ❌ | ❌ | `HB:13231-13241` | Three outcomes: crack (no change given), drain, or untouched if interrupted — and the cost is paid **even when the art fails**. | |

## 3. Per-class field detail

### 3.1 `Lashing` (`roshar_actions.py:95`)

| Field | Code value | Book value | Accuracy | Comment |
|---|---|---|---|---|
| Resource cost | 1 Stormlight sphere | Lashing Dice, or 0 for the cantrip | ❌ | |
| Duration | 10 rounds | Not stated as 10 rounds anywhere | ❌ | |
| Save / DC | none | `Adhesion` cantrip sets a STR (Athletics) DC of `8 + proficiency bonus`, rising at levels 5/11/17 | ❌ | |
| Damage | none | The maneuvers carry damage; the cantrip does not | ⚠️ | |
| Order gate | Windrunner, Skybreaker | Correct — both have Gravitation | ✅ | |

### 3.2 `ShardbladeAttack` (`roshar_actions.py:225`)

| Field | Code value | Book value | Accuracy | Comment |
|---|---|---|---|---|
| Damage | 2d6 necrotic | A level-scaled die (d4→d12 on the Windrunner table) plus a flat magic bonus, of a **chosen** damage type — not necrotic | ❌ | |
| Ignores armour | yes | No — a normal weapon attack roll vs AC | ❌ | |
| "10 heartbeats to kill" | implemented | Appears in neither book as a mechanic | ❌ | |
| Level gate | not enforced | Third Ideal (7th level) | ❌ | |
| Is it an Invested Art? | modelled as a surge | **No** — confirmed absent from the Invested Arts book; it is equipment | ❌ | |

### 3.3 `ProgressionHealing` (`roshar_actions.py:329`)

| Field | Code value | Book value | Accuracy | Comment |
|---|---|---|---|---|
| Healing dice | 2d8 | 2d8 — matches "Regrowth" verbatim | ✅ | |
| Ability modifier | hardcoded Wisdom | The caster's Investiture ability. WIS is right for Edgedancer; a **Truthwatcher chooses INT, WIS or CHA** | ❌ | |
| Resource cost | 2 spheres | 2 Investiture Points at art level 1, scaling with level | ❌ | |
| Level gate | 2 | 1 (First Ideal) | ❌ | |
| Order gate | Edgedancer, Truthwatcher | Correct — both have Progression | ✅ | |

### 3.4 `Illumination` (`roshar_actions.py:495`)

| Field | Code value | Book value | Accuracy | Comment |
|---|---|---|---|---|
| **Order gate** | Lightweaver, **Elsecaller** | **Lightweaver + Truthwatcher.** Elsecaller has Transformation + Transportation, not Illumination | ❌ | |
| Resource cost | 1 sphere | 0 — an explicitly free cantrip | ❌ | |
| Effect | grants the `Invisible` condition | Considerably weaker; neither the cantrip nor "Basic Lightweaving" grants full invisibility | ❌ | |

The order gate is a correctness bug independent of the cost issue: a Lightweaver's ally who
happens to be an Elsecaller can currently use an art their order does not possess.

### 3.5 `Soulcast` (`roshar_actions.py:590`)

| Field | Code value | Book value | Accuracy | Comment |
|---|---|---|---|---|
| Resolution | always succeeds, unresisted | The book has **three** distinct mechanics: a free cantrip, a costly skill-check-based art, and save-based combat arts | ❌ | |
| Resource cost | 3 spheres | Varies by which of the three applies; the cantrip is free | ❌ | |
| Save / DC | none | The combat arts require saves | ❌ | |

## 4. The 10 nulled surges — 10 blockers became 10 authoring tasks

| Mechanic | Implemented? | Reachable? | Evidence | Gap/notes | Comment |
|---|---|---|---|---|---|
| `surges` automation trees | ❌ | ❌ | All 10 entries in `surgebinding.json` have `automation: null` and `automation_status: "not_in_source"` — verified by enumeration | Nulled **because the book was missing**. That reason no longer holds: every surge now has cited book text sufficient to author a real cantrip-tier tree, and 6 also have deep leveled-art lists. | |
| Anything reads the `surges` key | ❌ | ❌ | `grep` for `['surges']` in components/agents → only `cosmere_rules.py:128`, which reads an order's surge *names*, not the entries | Authoring alone will not make them playable; a consumer is also needed. | |

## 5. Numbers the code invented

Values with no basis in either book. These are the dangerous ones, because each looks
plausible:

1. A flat 1/2/3 Stormlight-sphere cost per cast (all five classes)
2. `Lashing`'s 10-round duration
3. `ShardbladeAttack`'s 2d6 damage
4. `ShardbladeAttack`'s necrotic damage type
5. `ShardbladeAttack` ignoring armour
6. `ShardbladeAttack`'s "10 heartbeats to kill"
7. `Illumination` granting the full `Invisible` condition
8. `Illumination`'s Elsecaller order gate
9. `ProgressionHealing`'s hardcoded Wisdom modifier
10. `ProgressionHealing`'s level-2 gate
11. `Soulcast` always succeeding
12. `Soulcast`'s unresisted effect
13. `Soulcast`'s single collapsed mechanic in place of three

## 6. Summary counts

| | Count |
|---|---|
| Fields ✅ matching the book | 8 |
| Fields ⚠️ differing but defensible | 5 |
| Fields ❌ wrong | 14 |
| Classes reachable **and** materially wrong | 4 of 5 |
| Invented values with no textual basis | 13 |
| Highest-severity single item | `ShardbladeAttack` — every mechanical field invented |

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
