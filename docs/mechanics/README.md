# D&D 5e + Cosmere Mechanics: Requirements and Implementation Audit

**Generated 2026-09-12.** This directory answers two questions, kept deliberately separate:

1. **What mechanics does a complete D&D 5e (+ Cosmere/Roshar) game need?** — extracted
   directly from the rulebooks in `parsed_data/`, not from memory or from prior docs.
2. **Which of those does this codebase actually implement, and which can a player
   actually reach?** — audited by reading and *running* the code.

## Why these are separate, and why prior docs were not trusted

Every document here was produced by reading source material directly. Prior markdown in
this repo has been wrong in ways that mattered:

- an audit declared the Avrae automation schema "never started, zero hits" — it was
  fully authored in JSON; the grep had only searched `.py` files
- an audit said one PHB condition was missing (Petrified); two were (also Exhaustion)
- a subsystem's own summary called 7-of-9 failing tests "flaky, marginal"

So: **treat any claim without a `file:line` or a command-and-output as unverified.**

## The distinction that matters most

    IMPLEMENTED   the code exists and its unit tests pass
    REACHABLE     a player in a real session can actually trigger it

These come apart constantly in this codebase — there are **eight documented instances**
of a subsystem that was built, tested, and unreachable (see `REBUILD_PLAN_V5.md` §14e
and §14i). A module with passing tests and zero production callers is not a capability.
Both audit documents report both columns for every mechanic.

## Source material

| Source | Path | Lines | Role |
|---|---|---|---|
| **SRD 5.2.1 (2024)** | `parsed_data/srd_cc_v5.2.1/docling.md` | 24,275 | Most authoritative and detailed. Its **Rules Glossary (~167 entries)** is the canonical mechanics checklist. |
| **D&D Basic Rules (2018/2014-era)** | `parsed_data/dnd_basicrules_2018/docling.md` | 13,162 | The edition much of this codebase was written against. |
| **Cosmere 5e Radiant's Handbook v2.0** | `parsed_data/863203275-cosmere-5e-radiant-s-handbook-v2-0/docling.md` | 14,396 | Roshar: 10 orders, ~118 order features, ~26 Windrunner maneuvers, Lashing Dice / Investiture economies. |
| **Cosmere RPG excerpt** | `parsed_data/file_5035/docling.md` | 620 | Highstorms, spheres, world mechanics. |

**Known gap in the sources:** the Handbook defers all 10 surge *cantrip* mechanics to
*The Invested Arts of the Cosmere* — the phrase "See The Invested Arts of the Cosmere"
appears **16 times** (lines 1808, 2421, 2523, 3030, 3111, 3630, 3644, 4428, 4446, 4904,
4918, 5375, 5391, 5469, 5934, 6580), and line 279 states it outright: *"Because of Google
Docs character limitations, the detailed descriptions of each Invested Art are found in a
separate document, The Invested Arts of the Cosmere."* **That document is not in
`parsed_data/`.** So the 10 surges have names and order assignments but no effects, and
they cannot be authored without it. The project owner is sourcing it separately.
Everything else in the Handbook — the ~118 order features and ~26 maneuvers — *is* fully
specified and can be implemented today.

All four sources are PDF-to-markdown conversions with OCR artifacts (mangled headings
like `ONORSPREN`, `S KYBREAKER`, `ExpandinG and rEplacinG a spEllBook`, and at least one
maneuver — "Quiet Lashing" — whose body text did not survive extraction). Every document
here flags garbled passages rather than guessing at the rule.

## Documents

> **Anything Cosmere: start at `COSMERE_SYSTEMS_MAP.md`.** This directory documents **two
> different games** that share the same fiction — Cosmere 5e (which the project implements)
> and the standalone Cosmere RPG (reference only). Picking the wrong document means
> implementing rules from a system this project is not building, and the two fail silently
> when mixed rather than loudly.

### Requirements — what the rules say

| Document | Covers |
|---|---|
| `SRD_CORE_AND_COMBAT.md` | d20 tests, ability checks/saves/attacks, AC, advantage, proficiency, the full combat chapter, and all ~167 **Rules Glossary** entries |
| `SRD_SPELLCASTING.md` | Slots, upcasting, concentration, rituals, components, the per-class casting differences, Metamagic, a spell-effect taxonomy, and a field audit of the 319-spell `spells.json` |
| `SRD_CLASSES_AND_PROGRESSION.md` | Character creation, multiclassing, and every feature at every level for all 12 classes; feats; species; Weapon Mastery; a cross-class resource inventory |
| `SRD_EQUIPMENT_MONSTERS_DM.md` | Weapons/properties/mastery, armor + Armor Training, magic items and attunement, monster stat-block anatomy, and the **encounter XP budget** rules |
| `EDITION_DIFFERENCES.md` | Where 2014 and 2024 disagree, and which this project should follow. **Read before implementing anything** — mixing editions silently produces an incoherent rules set |
| `EDITION_CONFLICTS_IN_CODE.md` | The edition conflicts already shipped in the code (Exhaustion, grapple/shove, XP budget), and the decision each needs |

### Cosmere — two systems, one of them authoritative

| Document | Covers |
|---|---|
| **`COSMERE_SYSTEMS_MAP.md`** | **Start here.** Which system the project implements and why, how the documents divide, and which source books are still missing |
| `COSMERE_MECHANICS.md` | *Radiant's Handbook*: 9 playable orders, ~118 order features, ~26 maneuvers, Lashing Dice / Investiture Points, Shardweapons, Stances, spren, Ideals. **Carries a dated correction** — its "surges cannot be authored" claim is obsolete |
| `COSMERE_ARTS_SURGEBINDING_A.md` | Invested Arts: Windrunner, Skybreaker, Dustbringer, Edgedancer, Truthwatcher |
| `COSMERE_ARTS_SURGEBINDING_B.md` | Invested Arts: Lightweaver, Elsecaller, Willshaper, Stoneward, Bondsmith |
| `COSMERE_ARTS_OTHER_SYSTEMS.md` | Allomancy and Aonic arts, plus the **shared casting framework** (IP costs, components, concentration, DC formulas) |
| `COSMERE_RPG_CORE.md` | *Reference only.* The standalone Brotherwise system: plot die, Defenses, Focus, grazing, Deflect, fast/slow turns |
| `COSMERE_RPG_SURGEBINDING.md` | *Reference only.* Its Radiant material — **0 of 10 surges specified**, deferred to a book we don't have |

### Audit — what the code does

| Document | Covers |
|---|---|
| `AUDIT_COMBAT.md` | Attack resolution, advantage, action economy, conditions, death/dying, initiative, the tactical grid, multiattack, monsters/CR/encounter difficulty |
| `AUDIT_CHARACTER_AND_NONCOMBAT.md` | Character sheet fidelity, progression/XP/levelling, class features, spellcasting reachability, skills, rests, exploration, social, quests, persistence, the rules tiers, DM tools |
| `AUDIT_INVESTED_ARTS_READINESS.md` | Whether the engine can execute the 661 Invested Arts, and precisely which interpreter node types are missing |
| `AUDIT_HARDCODED_SURGE_ACCURACY.md` | Where the 5 hand-written surge classes disagree with the now-authoritative book |
| `AUDIT_COSMERE_RPG_FEASIBILITY.md` | Why the 5e engine cannot host the standalone Cosmere RPG — with live evidence of silent corruption |
| `AUDIT_STORMLIGHT_CONTENT.md` | Rosharan **content** rather than rules: pregens, adversaries, locations, scenarios, unindexed lore. Largely system-independent |

## How to use this

- **Implementing a mechanic?** Find it in the requirements doc for the exact rule and
  line number, check `EDITION_DIFFERENCES.md` for which version to follow, then check the
  audit doc for what already exists.
- **Implementing anything Cosmere?** Read `COSMERE_SYSTEMS_MAP.md` first, or you may build
  from the wrong system.
- **Deciding what to build next?** The audit docs' "Built but unreachable" sections are
  the cheapest wins — the code already exists and just needs wiring.
- **Adding to these docs?** Cite `file:line` or show the command and its output. That
  standard is the whole point of this directory.

