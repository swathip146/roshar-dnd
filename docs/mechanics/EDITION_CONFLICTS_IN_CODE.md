# Edition Conflicts Already Present in the Code

**Started 2026-09-12.** Findings verified against source while the mechanics audit ran.
This file exists because the conflict is not hypothetical — it is already implemented one
way, and the other way is equally defensible. Someone has to *decide*, and the decision
needs recording rather than rediscovering.

See `EDITION_DIFFERENCES.md` for the systematic 2014-vs-2024 differential.

## The setup

This project has two incompatible authorities on disk, both currently trusted by
different parts of the system:

| Source | Edition | Used by |
|---|---|---|
| `data/rules/srd/*.json` (vendored) | **2014-era — all 10 files, verified** | `components/srd_rules.py` (Tier 1 rules), `npc_stat_generator`, `combat_initializer`, `engine_conditions.py` |
| `parsed_data/srd_cc_v5.2.1/docling.md` | **2024 (SRD 5.2.1)** | the mechanics catalogue in this directory; nothing in code yet |
| `external/dnd_engine` (vendored) | **2014-era** | the whole combat engine |

**Every vendored dataset is 2014, with no exceptions.** Verified 2026-09-12 by checking
the `url` field on all 1,321 entries — every one points at `/api/2014/...` and not one
points at `/api/2024/...`:

```
  ability_scores.json        n=   6  2014=   6 2024=   0
  conditions.json            n=  15  2014=  15 2024=   0
  damage_types.json          n=  13  2014=  13 2024=   0
  equipment.json             n= 237  2014= 237 2024=   0
  magic_items.json           n= 362  2014= 362 2024=   0
  monsters.json              n= 334  2014= 334 2024=   0
  rules.json                 n=   6  2014=   6 2024=   0
  skills.json                n=  18  2014=  18 2024=   0
  spells.json                n= 319  2014= 319 2024=   0
  weapon_properties.json     n=  11  2014=  11 2024=   0
```

Corroborated independently for `spells.json`: it has exactly the 319 spells of the 2014
SRD and contains **none** of the 2024-only spells (Sorcerous Burst, Starry Wisp,
Elementalism, Ice Knife).

Anything implemented from the vendored JSON is 2014. Anything implemented from the newly
parsed SRD would be 2024. Mixing them silently produces a rules set that is neither.

## Conflict 1 — Exhaustion (CONFIRMED, already in code)

**2014** (`data/rules/srd/conditions.json`, and what the code does):
six discrete tiers — 1 disadvantage on ability checks, 2 speed halved, 3 disadvantage on
attacks and saves, 4 HP maximum halved, 5 speed 0, 6 death.

**2024** (`parsed_data/srd_cc_v5.2.1/docling.md`, verified verbatim at the
`## Exhaustion [Condition]` entry):

> *Exhaustion Levels.* This condition is cumulative. Each time you receive it, you gain 1
> Exhaustion level. You die if your Exhaustion level is 6.
> *D20 Tests Affected.* When you make a D20 Test, the roll is reduced by 2 times your
> Exhaustion level.
> *Speed Reduced.* Your Speed is reduced by a number of feet equal to 5 times your
> Exhaustion level.
> *Removing Exhaustion Levels.* Finishing a Long Rest removes 1 of your Exhaustion levels.

So 2024 is a flat, always-on `-2 × level` penalty to **every** d20 test and
`-5 ft × level` speed — mechanically simpler, and it hits saves and attacks from level 1
rather than level 3.

**What the code does:** `components/combat/../engine_conditions.py` implements the 2014
six-tier version (lines ~288-310: `if level >= 1` disadvantage on the 18 skills'
`skill_bonus`, `>= 2` speed halved, `>= 3` attack + save disadvantage, `>= 4` HP max
halved, `>= 5` speed 0). It is faithful to the vendored 2014 JSON it was written against,
and its tests assert the 2014 behaviour.

**Note:** the 2014 implementation is *not* a bug. It matches the vendored data. But if
this project intends to be a 2024 game, this needs rewriting AND its tests inverting —
and the difference is player-visible from exhaustion level 1.

**Status: UNDECIDED.** Do not "fix" this without a decision, or the tests and the data
will disagree with the code.

## Conflict 2 — Grapple and Shove (needs the same decision)

**2014:** an opposed check — attacker's Athletics vs target's choice of Athletics or
Acrobatics.

**2024:** per the core-and-combat catalogue, these became a fixed-DC mechanic under
Unarmed Strike (`DC 8 + Strength modifier + Proficiency Bonus`, target saves), not an
opposed roll.

**Relevance:** grapple/shove are currently unimplemented (`components/combat/standard_actions.py`
exists but `register_standard_actions()` is never called), so this one can be decided
*before* writing code rather than after. That makes it the cheaper decision.

## Conflict 3 — Encounter difficulty / XP budget

**2014:** XP thresholds per character level × difficulty, then a **group-size multiplier**
(×1.5 for 2 monsters, ×2 for 3-6, etc.).

**2024:** a flat XP budget per character level per difficulty tier (Low/Moderate/High),
with **no** group multiplier.

**What the code does:** `components/combat/combat_initializer.py` implements the 2014
system, including `_GROUP_MULTIPLIER`. This was deliberately tuned against measured
time-to-kill (see `REBUILD_PLAN_V5.md` §14c) after a level-1 character died in an
encounter marked "easy" — so the 2014 numbers here are *empirically calibrated for this
game*, which is an argument for keeping them regardless of edition.

## Recommendation

**Stay on 2014, and say so explicitly in `CLAUDE.md`.** The evidence makes this close to
forced rather than a judgment call:

1. **All 1,321 vendored data entries across all 10 datasets are 2014** (verified above).
   Migrating means re-vendoring everything — and `scripts/vendor_srd_data.py` currently
   pulls the 2014 API.
2. The vendored engine (`external/dnd_engine`) is 2014 and is treated as frozen
   third-party code (plan §4). Its `Attack`, conditions and action economy encode 2014
   assumptions.
3. The Cosmere Radiant's Handbook is built on the 2014 chassis — its class features assume
   2014 Fighting Styles, 2014 Action Surge, 2014 proficiency structure. **Roshar content is
   the point of this project** and would not survive a 2024 migration cleanly.
4. Encounter difficulty is already empirically tuned against 2014 numbers (§14c), after a
   level-1 character died in an encounter the system had marked "easy".

The 2024 SRD remains valuable as the **most complete and best-organised statement of the
mechanics** — its 166-entry Rules Glossary is the checklist this whole audit is built on —
even where we implement the 2014 version of a specific rule. Where a 2024 rule is merely
*better specified* than its 2014 equivalent and the two do not actually conflict, prefer
the 2024 text as documentation.

### Safe isolated adoptions from 2024

Per `EDITION_DIFFERENCES.md`, a few 2024 rules can be adopted without touching coupled
systems, because 2014 has no conflicting mechanic at all:

* the **Influence action** — useful for the NPC pipeline, which currently has no
  structured social mechanic
* an explicit **DC 15** for optional terrain/hazard checks where 2014 left it to the GM
* the explicit **concentration DC cap of 30**

### Combinations that would be actively worse than not migrating

* **2024 Surprise without giving monsters an initiative field** — 2014 suppresses the
  surprised creature's whole first turn; 2024 only gives disadvantage on the initiative
  roll. Adopt one half and surprise either does nothing or double-penalises.
* **Renaming `hidden` to Invisible cosmetically** — 2024 merged Hidden into the Invisible
  condition with a full effect list (initiative advantage, broader concealment). CLAUDE.md's
  own `CharacterRuntimeState` example carries `hidden` as an independent boolean, i.e. the
  2014 model. A rename without the effects is strictly worse than leaving it.
* **Mixing Exhaustion models** — the two are irreconcilable; a partial migration means the
  condition is computed differently depending on which code path applied it.
* **Using the string "Two-Weapon Fighting" as a dual-wield gate** — 2024 repurposes that
  name as an unrelated *feat*, having moved the base dual-wield rule into the **Light**
  weapon property. Code or data keying on that string misfires against 2024 text.

**What this means practically:** when a requirements doc in this directory cites a 2024
rule that conflicts with 2014, implement 2014 and note the divergence. Do not silently
follow whichever doc you read last. That is exactly how a codebase ends up computing
Exhaustion two different ways in two different files.

**One caveat worth stating plainly:** this recommendation means the project implements a
version of D&D that Wizards has superseded. That is a legitimate choice for a Cosmere game
built on a 2014-era licensed handbook — but it should be a *stated* choice in `CLAUDE.md`,
not an accident of which files happened to get vendored first.
