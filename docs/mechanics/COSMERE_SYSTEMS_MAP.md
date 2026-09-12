# Cosmere Systems Map — which document applies to you

**Written 2026-09-12.** `docs/mechanics/` documents **two different games** that share the
same fiction. A reader who picks the wrong document will implement rules from a system this
project is not building. This file is the entry point for anything Cosmere.

## The project's decision

> **Implement Cosmere 5e** — the *Radiant's Handbook* plus *The Invested Arts of the
> Cosmere (v2.0)*. Keep the Cosmere RPG documents as reference only.

The reason is simply that the codebase already *is* a D&D 5e engine: it vendors
`external/dnd_engine`, carries 1,321 entries of 2014 SRD data, and computes AC, saving
throws, proficiency and concentration. Cosmere 5e is built on that same chassis, so these
books *pair* with the engine. The standalone Cosmere RPG would require replacing it — see
`AUDIT_COSMERE_RPG_FEASIBILITY.md`, which measured the cost and recommended against a
partial retrofit.

## The two systems

| | **Cosmere 5e** *(implement this)* | **Cosmere RPG** *(reference only)* |
|---|---|---|
| Publisher | Fan/licensed, built on D&D 5e | Brotherwise Games — official, standalone |
| Core roll | d20 + modifier vs DC / AC | d20 + skill modifier vs DC, plus a **plot die** |
| Defence | Armor Class | **three Defenses** = 10 + both attributes in a category |
| Saves | saving throws (420 refs in Invested Arts) | **none — the mechanic does not exist** |
| Initiative | rolled (d20 + DEX) | **not rolled** — a fast/slow phase choice each round |
| Casting resource | **Investiture Points** (no spell slots) | Investiture pool + Focus |
| Damage types | 5e's ~13 | **five** (energy, impact, keen, spirit, vital) |
| Partial hits | none — hit or miss | **grazing**, plus **Deflect** damage reduction |
| Abilities | STR DEX CON INT WIS CHA | Strength, Speed, Intellect, Willpower, Awareness, Presence |

**They are not interoperable.** Not a reskin — different resolution pipelines, turn-order
models and resource economies. Concretely: a Cosmere RPG attribute of `3` *is* a +3, while
5e's `(score-10)//2` would read it as **−4**. That failure is silent, which is why mixing
them is worse than choosing either one.

## Documents by system

### Cosmere 5e — authoritative for implementation

| Document | Covers |
|---|---|
| `COSMERE_MECHANICS.md` | The *Radiant's Handbook*: 9 playable orders, ~118 order features, ~26 Windrunner maneuvers, Lashing Dice and Investiture Point economies, Shardweapons, Stances, spren, Highstorms. **Carries a dated correction at the top** — its "surges cannot be authored" claim is obsolete. |
| `COSMERE_ARTS_SURGEBINDING_A.md` | Invested Arts for Windrunner, Skybreaker, Dustbringer, Edgedancer, Truthwatcher |
| `COSMERE_ARTS_SURGEBINDING_B.md` | Invested Arts for Lightweaver, Elsecaller, Willshaper, Stoneward, Bondsmith |
| `COSMERE_ARTS_OTHER_SYSTEMS.md` | Allomancy and Aonic arts, plus **the shared casting framework** (IP costs, components notation, concentration, DC formulas) |
| `AUDIT_INVESTED_ARTS_READINESS.md` | Whether the engine can execute the arts, and the interpreter gap |
| `AUDIT_HARDCODED_SURGE_ACCURACY.md` | Where the 5 hand-written surge classes disagree with the now-authoritative book |

### Cosmere RPG — reference only

| Document | Covers |
|---|---|
| `COSMERE_RPG_CORE.md` | Plot die, Defenses, Focus, grazing, Deflect, fast/slow turns, 13 conditions, injury rolls |
| `COSMERE_RPG_SURGEBINDING.md` | Its Radiant/setting material. **0 of 10 surges specified** — it defers to a full *Stormlight Handbook* (cited 20×) |
| `AUDIT_COSMERE_RPG_FEASIBILITY.md` | Why the 5e engine cannot host it, with live evidence of silent corruption |
| `AUDIT_STORMLIGHT_CONTENT.md` | **Content, not rules** — pregens, adversaries, locations, scenarios. Largely reusable regardless of system, since fiction ports even when mechanics don't |

`AUDIT_STORMLIGHT_CONTENT.md` stays useful under the Cosmere 5e decision: its findings about
unindexed lore, the Rosharan currency table, and the missing bestiary are system-independent.

## Which book supplies what

Verified against `resources/rules/` and `parsed_data/` on 2026-09-12.

| Book | Present? | Supplies |
|---|---|---|
| Cosmere 5e Radiant's Handbook v2.0 | ✅ | Orders, order features, maneuvers, resource economies, Shardweapons, Stances |
| **Cosmere 5e: The Invested Arts of the Cosmere v2.0** | ✅ **newly added** | **661 art entries** — all 10 surges, plus Allomancy and Aonic magic |
| D&D SRD 5.2.1 (2024) | ✅ | The 2024 rules baseline (note: the code implements **2014** — see `EDITION_CONFLICTS_IN_CODE.md`) |
| D&D Basic Rules (2014-era) | ✅ | The edition the codebase actually implements |
| SL015 Stormlight Starter Rules | ✅ | Cosmere RPG core — *different system* |
| CS006 Player Quick Reference | ✅ | Cosmere RPG — *different system* |
| CS007 GM Rules Overview | ✅ | Cosmere RPG — *different system* |
| SL019 pregens (20) + SL007 Bridge Nine pregens | ✅ | Cosmere RPG characters — *content, reusable* |
| **Hoid's Guide to the Cosmere** | ❌ missing | Honorblades, Nightblood, possibly Bondsmith |
| **Invested Items Collection** | ❌ missing | Full Shardplate rules (AC formula, HP, cost) |
| **Creature Compendium** | ❌ missing | The Rosharan bestiary — chasmfiends, Fused, Thunderclasts |
| Stormlight World Guide / Stonewalkers | ❌ missing | Cosmere RPG lore and campaign content |

### What the remaining gaps actually cost

- **Creature Compendium** is the most player-visible. The codebase has 334 D&D monsters and
  **zero Rosharan creatures**. A Roshar campaign currently fights goblins.
- **Invested Items Collection** blocks full Shardplate. Shardblades are covered by the
  Radiant's Handbook; Plate is not.
- **Hoid's Guide** remains the Bondsmith blocker. **Verified 2026-09-12: "Bondsmith" appears
  0 times in all 19,794 lines of the Invested Arts book.** Its canonical surges show up only
  as other orders' arts (Tension → Stoneward, Adhesion → Windrunner), never attributed to
  Bondsmith. So the project stays at **9 playable orders, not 10**, until that book arrives.

## Standard for this directory

Every claim carries a `file:line` citation or a command and its output. Treat anything
without one as unverified — prior documents in this repo have been confidently wrong
(a subsystem declared "never started" was fully authored in JSON; one missing PHB condition
was actually two). If you find an error here, correct it in place and date the correction,
as `COSMERE_MECHANICS.md` now does.

---

## Schema constraint found while verifying the extractions (2026-09-12)

An Invested Art's **level and surge depend on which order casts it**. This is not an
edge case — **17 bylines** in the book carry split attributions. Examples, verbatim:

```
line 1876  9th-level Progression - Edgedancer, Truthwatcher
         / 9th-level Transformation - Elsecaller, Lightweaver
line 1926  2nd-level Illumination & Transformation - Lightweaver
         / 2nd-level Transformation & Transportation - Elsecaller
line 2676  1st-level Transformation - Lightweaver
         / 1st-level Transportation - Elsecaller Inksurge, Willshaper Cognitive Power
```

**Consequences for whoever implements this:**

1. An art **cannot** be stored with a single `level` field. It needs a per-order mapping,
   e.g. `availability: [{order, surge, level}, ...]`. Since Investiture Point cost derives
   from art level, a flat `level` would charge the wrong cost for at least one order.
2. Ten bylines name **order-specific sub-powers** (`Elsecaller Inksurge`,
   `Willshaper Cognitive Power`, and one `10th-Level Class Feature`). These are gates, not
   flavour, and the schema must carry them.
3. **The per-order index lists are not a reliable inventory.** *Detect Investiture*,
   *Locate Object* and *Realmatic Door* appear under the **Lightweaver** index while their
   bylines also grant them to Elsecaller and Willshaper. Enumerating from the index alone
   undercounts some orders and overcounts others — extract from **bylines**, then reconcile
   against the index rather than the reverse.

### A verification note worth keeping

Art headings often carry a `▶` concentration glyph, so `## <Art Name>` does **not** match
them — `## ▶ Detect Investiture` does. A naive grep for headings silently misses ~286
concentration arts. This tripped up my own spot-check of an agent's work: I concluded three
arts were absent from the body when they were present at exactly the lines cited. Anyone
scripting an extraction from this book must account for the glyph.
