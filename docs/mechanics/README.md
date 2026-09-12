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

### Requirements — what the rules say

| Document | Covers |
|---|---|
| `SRD_CORE_AND_COMBAT.md` | d20 tests, ability checks/saves/attacks, AC, advantage, proficiency, the full combat chapter, and all ~167 **Rules Glossary** entries |
| `SRD_SPELLCASTING.md` | Slots, upcasting, concentration, rituals, components, the per-class casting differences, Metamagic, a spell-effect taxonomy, and a field audit of the 319-spell `spells.json` |
| `SRD_CLASSES_AND_PROGRESSION.md` | Character creation, multiclassing, and every feature at every level for all 12 classes; feats; species; Weapon Mastery; a cross-class resource inventory |
| `SRD_EQUIPMENT_MONSTERS_DM.md` | Weapons/properties/mastery, armor + Armor Training, magic items and attunement, monster stat-block anatomy, and the **encounter XP budget** rules |
| `COSMERE_MECHANICS.md` | The 10 orders and their Investiture abilities, ~118 order features, ~26 maneuvers, Lashing Dice and Investiture Points, Stormlight, Shardblades/Shardplate, spren, Ideals |
| `EDITION_DIFFERENCES.md` | Where 2014 and 2024 disagree, and which this project should follow. **Read before implementing anything** — mixing editions silently produces an incoherent rules set |

### Audit — what the code does

| Document | Covers |
|---|---|
| `AUDIT_COMBAT.md` | Attack resolution, advantage, action economy, conditions, death/dying, initiative, the tactical grid, multiattack, monsters/CR/encounter difficulty |
| `AUDIT_CHARACTER_AND_NONCOMBAT.md` | Character sheet fidelity, progression/XP/levelling, class features, spellcasting reachability, skills, rests, exploration, social, quests, persistence, the rules tiers, DM tools |

## How to use this

- **Implementing a mechanic?** Find it in the requirements doc for the exact rule and
  line number, check `EDITION_DIFFERENCES.md` for which version to follow, then check the
  audit doc for what already exists.
- **Deciding what to build next?** The audit docs' "Built but unreachable" sections are
  the cheapest wins — the code already exists and just needs wiring.
- **Adding to these docs?** Cite `file:line` or show the command and its output. That
  standard is the whole point of this directory.
