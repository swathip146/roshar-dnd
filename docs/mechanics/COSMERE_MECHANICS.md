# Cosmere / Roshar Mechanics Catalogue

> ## CORRECTION — 2026-09-12
>
> **The central claim of this document (Part 0 and Final List (b) below) is
> obsolete.** They state that all 10 surge cantrip effects "CANNOT be
> authored" because *The Invested Arts of the Cosmere* was missing.
> **That book has since been added to the project** and is parsed at
> `parsed_data/cosmere-5e-the-invested-arts-of-the-cosmere-v2-0/docling.md`
> (19,794 lines). Verified directly: it contains roughly **661 Invested Art
> entries** (counted via `Casting Time` header occurrences, its per-entry
> delimiter), split across Surgebinding (~322), Allomancy (~69), and Aonic
> (~270) arts, and its Surgebinding section gives full mechanical write-ups —
> casting time, range, components, duration, save/attack, damage dice — for
> **all 10 Rosharan surges** (Adhesion, Gravitation, Division, Abrasion,
> Progression, Illumination, Transformation, Transportation, Cohesion,
> Tension), not just names.
>
> This document's own body is **left unmodified below** (per the instruction
> not to rewrite it) so its extraction work on the ~118 order features,
> maneuvers, and Stormlight economy remains intact and citable. But wherever
> it says a surge/Invested-Art mechanic "cannot be authored" or is "not in
> `parsed_data/`," read that as **historical, not current**. For the actual
> surge/Invested Art mechanics, see the new documents that extract *The
> Invested Arts of the Cosmere*:
> - `COSMERE_ARTS_SURGEBINDING_A.md`
> - `COSMERE_ARTS_SURGEBINDING_B.md`
> - `COSMERE_ARTS_OTHER_SYSTEMS.md` (Allomancy, Aonic)
>
> Two books cited below as "missing" in the same breath as the Invested Arts
> are **still genuinely absent** — do not assume they arrived too:
> **Invested Items Collection** (full Shardplate AC/HP/cost rules, 400+
> Invested items) and **Hoid's Guide to the Cosmere** (Honorblades,
> Nightblood, the Bondsmith class, non-Roshar classes). Confirmed by direct
> search: no file matching either title exists anywhere under `resources/rules/`
> or `parsed_data/` as of this correction. See `COSMERE_SYSTEMS_MAP.md` for
> the full "which book supplies what" table and current gap list.
>
> This document also assumes the Cosmere 5e system generally (d20, AC, saving
> throws) is the one this project implements, which remains the project's
> decision — see `COSMERE_SYSTEMS_MAP.md` for why, and for how the unrelated
> **Cosmere RPG** (Brotherwise Games' standalone Plotweaver system, covered by
> `COSMERE_RPG_CORE.md` / `COSMERE_RPG_SURGEBINDING.md`) fits in.

---

Exhaustive extraction of Cosmere 5e mechanics from the Radiant's Handbook, for a
game-engine implementation audit. This document does **not** assess what the
codebase has implemented — it only catalogues what the source material says.

**Sources**:
- `parsed_data/863203275-cosmere-5e-radiant-s-handbook-v2-0/docling.md` (14,396
  lines) — the main source, cited throughout as `HB:<line>`.
- `parsed_data/file_5035/docling.md` (620 lines) — a Cosmere RPG excerpt
  (highstorms, spheres, world info); not separately re-extracted here because
  every mechanical claim it could contain is already covered, in more detail,
  by the Handbook's own Appendix B "Storms" and Chapter 5 "Wealth" sections.
- `data/rules/stormlight/surgebinding.json` — the structured extraction that
  already exists (10 surges, 10 orders, 9 maneuvers, 2 features, economies).
  Its `_meta` documents the convention used below in the "In json?" column:
  `reviewed: true` means the mechanics were read verbatim from the Handbook;
  `automation: null` + `automation_status: "not_in_source"` means the rule is
  genuinely absent from our source material, not merely unauthored.

**OCR caveat**: the parsed markdown has heavy OCR/PDF-conversion damage,
concentrated in (a) every companion-spren stat block (all ten are rendered as
scrambled column fragments or literal embedded images) and (b) several
class-table "level number" columns (rendered as stray ordinal-suffix
fragments like `E`, `evel`, `th`). Every instance found is flagged inline
with its line number rather than guessed at.

---

## PART 0 — The central constraint (RESOLVED — see correction banner at top)

> **This section is preserved for historical/citation purposes only. Its
> conclusion no longer holds** — *The Invested Arts of the Cosmere (v2.0)* has
> since been added at
> `parsed_data/cosmere-5e-the-invested-arts-of-the-cosmere-v2-0/docling.md`
> and fully specifies all 10 surges' cantrip and leveled-Art effects. See the
> correction banner at the top of this document and `COSMERE_SYSTEMS_MAP.md`.
> The text below describes the state of the sources *before* that book was
> added, and remains accurate as a description of the Handbook alone.

**The 10 surge cantrip mechanics are not in the Handbook alone.** The Handbook
defers them to a separate document seven times, verbatim: *"See The Invested
Arts of the Cosmere for detailed information about these cantrips"* —
`HB:1808` (Windrunner), `HB:3630` (Edgedancer), `HB:4428` (Truthwatcher),
`HB:4904` (Lightweaver), `HB:5375` (Elsecaller), `HB:5934` (Willshaper),
`HB:6580` (Stoneward). `HB:279` confirms generally: *"the detailed
descriptions of each Invested Art are found in a separate document."*
`HB:13333-13337` (Chapter 10 close) restates it: full Invested Art write-ups,
including the two basic Surge cantrips every class gets for free, live in
*The Invested Arts of the Cosmere*, not this book.

**That document was not in `parsed_data/` at the time this catalogue was
written; it has since been added.** Confirmed independently by direct reading
(Part 6 below) — Chapter 10 ("Investiture Casting") gives the entire generic
casting *chassis* (levels, points, components, duration, targets, saves) but
at no point states what any specific surge, cantrip, or named Invested Art
actually does. The 10 surges (Adhesion, Gravitation, Division, Abrasion,
Progression, Illumination, Transformation, Transportation, Cohesion,
Tension) had, **in the Handbook alone**, names and order-assignments only.
Their spell effects are now available in the Invested Arts document — see
the correction banner and `COSMERE_ARTS_SURGEBINDING_A.md` /
`COSMERE_ARTS_SURGEBINDING_B.md`.

---

## PART 1 — Stormlight economy & resting

| Mechanic | Source line | Rule | Recharge/cost | In json? |
|---|---|---|---|---|
| Stormlight Replenishment gate | `HB:1806` (class-specific restatement), `HB:12339` (general Ch. 8 rule) | To recover HP/Hit Dice/features/Investiture Points on a long rest, must intake Stormlight = **character level × 5** sapphire marks' worth. Confirmed as the same rule stated twice, word-for-word equivalent. | Every long rest | Yes — `economies.stormlight_replenishment`, `reviewed: true` |
| Dunning spheres | `HB:12351-12367` | On waking from a long rest, dun (level×5) sm of infused spheres — but **only if** something needs replenishing; if nothing was expended, dun nothing. Worked ledger example given (500 total sm, 100 dun → 400 infused). | Per long rest | No — mechanic (the "why dun" conditional) is new |
| **Insufficient Stormlight** | `HB:12369-12371` | If infused spheres < level×5 on waking: **zero** recovery (no HP, no features, no dunning at all — explicitly no partial credit). Recovery path: find/see the shortfall in infused sm within 5 ft, spend an action breathing it in, then take a short rest that heals/restores as a long rest would. | n/a | **No** — entirely new, not in json |
| Infusing spheres | `HB:12373-12375` | Via highstorm exposure or moneychanger exchange. | n/a | No |
| Utilizing polestones | `HB:12377-12383` | Can dun infused polestones instead of own spheres, partially or fully. Worked example: 100-sm large heliodor dunned to 80/100; a partial polestone can't fuel "must be fully infused" requirements. | n/a | No |
| Stormlight Average / GM's Rule | `HB:12385-12399` | Flavor justification that level×5/day is an *average*; GM waiver options given (ambient Stormlight exposure, offworld Investiture, multi-day-travel abstraction 0 / 1d4×days / 1d12×days). | n/a | No (GM-discretion text, not a hard rule) |
| Keeping Track (ledger method) | `HB:12405-12426` | Total Stormlight capacity = sum of all sphere sm-equivalents + all polestone sm capacities; single "dun" counter tracks how much is currently dun. Full worked example (399 sm capacity, +35 dun after one rest for a 7th-level character). | n/a | No |
| Sphere denominations & exchange | `HB:8829-8851` | Diamond chip=copper, Topaz mark=silver, Ruby mark=electrum, Sapphire mark=gold, Emerald broam=platinum. Full 5×5 exchange table (e.g. 1 sapphire mark = 100 chips = 10 topaz = 2 ruby = 1/10 broam). | n/a | No |
| Sphere → Stormlight unit conversion | `HB:8861` | 1 sapphire mark's worth is the base Stormlight unit. Diamond chip = 1/100 sm; ruby mark = 1/10 sm; amethyst mark = 1/2 sm; emerald broam = 10 sm. | n/a | No |
| Moneychanger dun→infused fee | `HB:8859` | **2%** of value (round up to nearest diamond chip); rises to **5%** (round up to nearest ruby mark) during the Weeping. | n/a | No |
| Invested Save DC (universal formula) | `HB:1868` (class-specific), `HB:13319` (Ch. 10 general) | **8 + proficiency bonus + Investiture ability modifier.** Confirmed by Ch. 10 to be class-agnostic — only the ability score used varies per order. Invested attack bonus uses the identical prof+mod formula (`HB:13321-13323`). | n/a | Yes — `invested_save_dc.formula`, `reviewed: true`, but json currently scopes it only under Windrunner; should be generalized |

### Resting (general, non-Stormlight-specific)

| Mechanic | Line | Rule |
|---|---|---|
| Short rest | `HB:12327-12331` | ≥1 hr; spend Hit Dice (roll + Con mod, min 0) up to level in dice. |
| Long rest | `HB:12333-12341` | ≥8 hrs (6h sleep + ≤2h light activity); broken by ≥1h strenuous activity. Full HP restore + regain spent Hit Dice = half total (min 1). Max once per 20-hour Rosharan day; need ≥1 HP to start. |
| Leaking Light | `HB:12401-12403` | Flavor: dunning-after-rest doubles as the abstraction for natural polestone/sphere Stormlight leakage. |

---

## PART 2 — Investiture Casting framework (Chapter 10)

The generic spellcasting-analogue chassis, distinct from any surge's actual
effects.

| Mechanic | Line | Rule | In json? |
|---|---|---|---|
| Invested Art levels | `HB:13121-13125` | 0 (cantrip) – 9. Character level ≠ Art level directly (9th-level Art needs 17th character level). | No |
| Investiture Point cost table | `HB:13149-13161` | 1st:2, 2nd:3, 3rd:5, 4th:6, 5th:7, 6th:8, 7th:10, 8th:11, 9th:13. Stated to apply to Edgedancer/Truthwatcher/Lightweaver. | **Yes, exact match** — `economies.investiture_points.cost_by_art_level`, `reviewed: true` |
| Elsecaller exception | `HB:13147`, `13173` | Always pays exactly **1** Investiture Point regardless of level cast; always casts at the *highest* level possible for their Elsecaller level (≤5th). Worked example: 7th-level Elsecaller casts a 1st-level Art at 4th level. | Yes — `economies.investiture_points.special`, `reviewed: true` |
| 6th+ level Arts | `HB:13163-13165` | Castable only **once each** per long rest regardless of remaining Investiture Points. | No |
| Upcasting | `HB:13167-13173` | Casting above base level costs the higher level's IP; effect scales if the Art supports it. | No |
| Cantrips | `HB:13175-13177` | Level 0, at-will, 0 IP. **Every class**, even non-casters, gets 2 free cantrips from their basic Surges. | Partially — surges marked `cantrip: true`, `cost.investiture_points: 0` |
| Casting in Armor | `HB:13179-13181` | Must be proficient with worn armor/shield or cannot cast at all. | No |
| Components — Glow (G) | `HB:13219-13223` | Cosmere reskin of Verbal: exposed skin/nose/mouth/eyes glow with Stormlight; 5 ft dim light for cast duration; onlookers in bright light need Wis (Perception) at **disadvantage, DC 10** to notice. | No |
| Components — Somatic (S) | `HB:13225-13229` | Free hand; a small (not medium) shield doesn't block it. | No |
| Components — Material (M) | `HB:13231-13241` | Infused polestones, must be fully infused, correct size/type. Casting **cracks/consumes** the stone (worked example: *revivify* needs 300 sm diamonds — a 500-sm diamond fully cracks/wastes excess). Consumption happens regardless of the Art's success/failure, but not at all if the cast is interrupted before completion. | No |
| Duration — Concentration | `HB:13251-13263` | Constitution save to maintain. Broken by: casting another concentration Art, taking damage (DC = 10 or half damage, whichever higher, per source), incapacitation/death. GM may add environmental DC-10 Con saves. | No |
| Areas of Effect | `HB:13279-13313` | 5 shapes: cone, cube, cylinder, line, sphere — standard 5e-style geometry (cylinder/sphere origin *included* in AoE; cone/cube/line origin *not*, unless stated). | No |
| Saving Throws / Attack Rolls | `HB:13315-13325` | DC = 8+prof+Investiture mod (same universal formula as Part 1). Attack bonus = prof+Investiture mod. | Yes (see Part 1 row) |
| Combining Invested Effects | `HB:13327-13331` | Different Arts stack while durations overlap; the **same** Art cast multiple times does **not** stack — highest/most-recent applies. | No |

---

## PART 3 — The 10 Radiant Orders

Every order below: swears the **First Ideal** at 1st level (grants its two
Surges + companion spren), the **Second Ideal** partway through (grants an
"Ideal Feat" track), then further Ideals up to the **Fifth** by high level.
The **Bondsmith** (Tension + Adhesion) is confirmed **not playable** in this
book — `HB:1631`, `Bondsmith.playable: false` in json, `reviewed: true`;
Hoid's Guide to the Cosmere has it instead. Nine orders are playable.

### Order summary table

| Order | Surges | Investiture Ability | Spren | Polestone | Economy | Source | In json? |
|---|---|---|---|---|---|---|---|
| Windrunner | Adhesion, Gravitation | higher of STR/DEX | Honorspren | — | Lashing Dice | `HB:1812` | Yes, `reviewed:true` |
| Skybreaker | Gravitation, Division (Div. at 5th) | Intelligence | Highspren | — | Lashing Dice (Skybreaks) | `HB:2423` | Yes, `reviewed:true` |
| Dustbringer ("Releaser") | Abrasion, Division (Div. at 5th) | Wisdom | Ashspren | — | Releases (Lashing-Dice-like) | `HB:3030` | Yes, `reviewed:true` |
| Edgedancer | Abrasion, Progression | Wisdom | Cultivationspren | Diamond | Investiture Points | `HB:3632` | Yes, `reviewed:true` |
| Truthwatcher | Progression, Illumination | player's choice of INT/WIS/CHA, fixed forever once chosen | Mistspren | Emerald | Investiture Points | `HB:4430` | Yes, `reviewed:true` |
| Lightweaver | Illumination, Transformation | Charisma | Cryptic | Garnet | Investiture Points | `HB:4972` | Yes, `reviewed:true` |
| Elsecaller | Transformation, Transportation | Intelligence | Inkspren | — | Investiture Points (flat 1/cast) | `HB:5371` | Yes, `reviewed:true` |
| Willshaper | Transportation, Cohesion | Charisma | Reacher | Amethyst | Cogni Dice | `HB:5930` | Yes, `reviewed:true` |
| Stoneward | Cohesion, Tension | Constitution | Peakspren | Topaz | Wards (self-resource, not a "point pool") | `HB:6582` | Yes, `reviewed:true` |
| Bondsmith (NOT PLAYABLE) | Tension, Adhesion | — | — | — | — | `HB:1631` | Yes, `playable:false` |

All 9 playable orders confirmed to grant their 2 named Surge cantrips at 1st
level, always-prepared, free of the normal cantrip-known count — but see Part
0: none of the 10 surges' actual mechanical effects are in this source.

---

### 3.1 Windrunner (`HB:1677-2283`)

**Table** (`HB:1711-1757`): 20-level progression of Prof. Bonus, Features,
Maneuvers Known, Lashing Dice count (2→7), Lashing Die size (d4→d12),
Focuses. *(Flagged: raw table has one fewer row than 20 character levels —
level assignment below is reconstructed from prose cross-references, not a
verbatim table read.)*

| Feature | Level | Rule | Recharge |
|---|---|---|---|
| Adhesion & Gravitation | 1 | Surges granted; 2 cantrips known, always prepared. Investiture ability = higher of STR/DEX. | — |
| Honorspren | 1 | Nahel-bond companion. | — |
| Windrun | 1 | Bonus action: fly speed = walking+10 ft + hover, 10 min. 6th: +20 ft, can group-fly companions (1 min setup, 3× fly speed, 1 hr, sustain via action+bonus+reaction/turn). 14th: permanent fly speed = walking+20 ft. | Uses = prof bonus / short-or-long rest |
| Fighting Style | 1 | Choose one (Ch. 6); swappable via Jezrien's Initiative; improves at 10th per style. | — |
| Stormlight Healing | 1 | Bonus action: 1d10 + Windrunner level HP. 6th: 2×/rest. 14th: 3×/rest. | 1(→2→3)/rest |
| Action Surge | 2 | One extra action. 10th: 2×/rest (1/turn cap). 17th: 3×/rest (1/turn cap). | 1(→2→3)/rest |
| Maneuvers (+ Lashing Dice + Investiture Ability) | 2 | Know Maneuvers per table; 1 Maneuver/attack, once/turn each. **Lashing Dice**: start 2×d4, scale per table columns; regain all on short/long rest — matches json exactly. Invested save DC formula confirmed identical to json. | Full recharge, short or long rest |
| Second Ideal buff | 2 | On swearing (GM-approved), 1 min: heal `prof-bonus`d6/turn, free Windrun even at 0 uses (+10 fly speed), advantage on attacks, 1 free Maneuver/turn. | 1 min |
| Windrunner Focus | 3 | Choose a Focus (list below); more per table; permanent once chosen. | — |
| General Feat | 4,8,12,**14 or 16**\*,19 | ASI or feat. *(Flagged: this heading literally says "14th" at `HB:1876` while the paired Jezrien's Initiative heading says "16th" at `HB:1880` — a genuine source inconsistency, not OCR.)* | — |
| Jezrien's Initiative | 4,8,12,16,19 | Swap a fighting style or a known Maneuver. | — |
| Extra Attack | 5 | 2 attacks; 3 at 11th; 4 at 20th. | — |
| Shardblade Stance | 5 | Choose 1 (Ch. 6, Part 5 below); +1 more at 10th, +1 more at 17th. | — |
| Shardblade | 7 | Honorspren → Shardweapon +1 (bonus action summon/dismiss/change); also small/medium Shardshield (action). +2 at 15th. Not usable in Cognitive Realm. | — |
| Indomitable | 9 | Reroll a failed save, must keep new roll. 13th: 2×/long rest. 17th: 3×/long rest. | 1(→2→3)/long rest |
| Invested Potency | 11 | +2 to Str/Dex saves; +2 to any other save w/o proficiency/expertise (not death saves). Scales to +3 at prof+5, +4 at prof+6. | — |
| Windplate | 15 | Reaction vs. a B/P/S attack within 30 ft: halve on self / zero on ally; crit downgraded to normal hit (with the halving/zeroing still applying). Not in Cognitive Realm. 18th: 40 ft, 2 uses. 20th: 60 ft, 3 uses. | 1(→2→3)/long rest |
| Defender of the Skies | 20 | Str/Dex +4 (choice); Lashing Dice partial-refund on initiative if below 3; eyes permanently bright blue. | — |

**Maneuvers (26 confirmed, full list)** — each expends 1 Lashing die:
Agile Lashings (Acrobatics check bonus), Alerted Lash (initiative bonus),
Athletic Lashings (Athletics check bonus), Distracting Attack (damage +
advantage-to-others on target), Evasive Movement (AC bonus while moving),
Feinting Attack (advantage on next attack), Flourish (Sleight of Hand check
bonus), **Full Lashing** (action, 30 ft, Str save or restrained + bludgeoning
damage — this is the fully-automated one already in json), Goading Attack
(damage + Wis save or disadvantage vs. others), Invested Focus (Knowledge
check bonus), Invested Perception (skill-check bonus; source literally says
"Dexterity (Perception)" — flagged as likely a should-be-Wisdom typo, `HB:1984`),
Lash Ally (move + AC-bonus ally 30/60 ft), Lash Enemy (damage + Str save or
forced move), Lunging Strike (+5 reach), Parry (reaction, reduce melee
damage), Precision Attack (attack-roll bonus), **Quiet Lashing** (Stealth
check bonus — *confirmed NOT empty in this parse, contrary to the
task's flagged prior concern; full text present at `HB:2006-2010`*), Rally
(temp HP to ally), Rampage (bonus attack on kill), Rescuing Wind (swap
places + AC bonus), **Reverse Lashing** (reaction, 30 ft, AC bonus vs.
triggering attack — already in json), Riposte (reaction attack on a miss —
already in json), Saving Lash (reaction, boost an ally's Str/Dex save),
Slowing Lash (speed reduction on hit), Thrown Lashing (bonus-action ranged
attack), Tripping Lash (damage + Str save or prone).

**Windrunner Focus options (14 confirmed)**: Armor (+1 AC), Deftness (Dash as
bonus action while flying), Endurance (3-hr long rest, exhaustion-save
advantage), Evasion (disadvantage on OAs vs. you while flying), Fighting
(extra fighting style), Health (+2 HP/level retroactive), Maneuvers (+1 bonus
Maneuver, swappable), Practice (skill+tool proficiency package), Protection
(Guard as bonus action), Range (thrown Shardweapon returns), Resistance
(resist one non-Invested B/P/S type), Speed (+5 ft), Study (expertise in a
known skill/tool), the Winds (Windrun uses ×2).

**Honorspren stat block** (`HB:2114-2190`) — **badly garbled**: headings
"ONORSPREN"→Honorspren, "AITS"→Traits, "CTIONS"→Actions, "ONUS
ACTIONS"→Bonus Actions all lost their leading letters (likely swallowed by an
adjacent unOCR'd border image at `HB:2118`). Recoverable: AC 17, HP =
Windrunner level + prof bonus, Fly 60 ft, STR 10 (+0), INT 6 (-2), Passive
Perception 11, Languages Common, Prof Bonus +2, Size Tiny/Small/Medium, Type
Splinter. Traits: standard "Radiant Spren" boilerplate (doesn't need to
breathe/eat/drink/sleep; at 0 HP tries to return to your space instead of
dying); Aide of Wind (squeeze through tiny openings); Telepathic Link (7th
level). Actions: Stormsense (1/long rest, 3rd level, DC 14 Wis check to sense
next highstorm's arrival day); Spren Hand (3rd level, Adhesion-based object
manipulation up to 5 lb, 10 lb at 7th); Full Lashing (7th level, infuse a
small unworn item, DC 10 Str check to pull free, improves at 15th to 10 lb /
1 min / DC 12). Bonus Actions: Shiftshape (resize Tiny↔Medium, can mimic an
object if Tiny). **A second, apparently unrelated garbled stat-block
fragment** (DEX 24, CON 1, WIS 12, CHA 12, Necrotic/Poison/Psychic
resistance, long condition-immunity list) is interleaved at `HB:2204-2248`
inside the Ideal Feats section — likely cross-contamination from a different
creature elsewhere in the source PDF, not part of the Honorspren block;
flagged as a content-integrity defect worth a fresh OCR pass.

**Ideal of Protection Feats**: 3rd (Improved Critical, Unarmored Defense,
Extra Proficiencies), 7th (Shard Shielding, Stormlight Explosion, Inspired
Healing), 15th (Bonus Surge, Infused Surge, Dashing Surge), 18th (Shardstorm,
Wind's Endurance, Jezrien's Survivor — oath text itself is a literal `'???'`
at `HB:2276`, a genuine source gap).

---

### 3.2 Skybreaker (`HB:2284-2919`)

| Feature | Level | Rule |
|---|---|---|
| Gravitation | 1 | Surge granted (no Division until 5th); cantrip Gravitation. Investiture ability = Intelligence. |
| Highspren | 1 | Companion. |
| Skyward | 1 | Fly speed = walking+hover, 10 min; uses = Int mod (min 1)/short rest. 6th: +10 ft, group-fly. 14th: permanent +10 ft. |
| Stormlight Healing | 1 | Reserve pool = level×5 HP, refills on long rest; action to heal up to max. 5th: 25 pts removes poison/disease instead. |
| Skybreaking | 2 | On melee-Attack-action hit, spend Skybreaks (max = prof bonus/attack) for 1d8 axial damage each; not on OAs/non-Attack-action hits. Regain on long rest. |
| Skybreak Augmentations | 2 | Augment a Skybreaking hit with one known Augmentation, once/turn; uses = Int mod(min 1)/long rest; max Skybreaks/attack = prof bonus. Augmentation bonus damage does NOT double on crit (base Skybreak damage does). |
| Brand of Judgment | 2 | Bonus action, touch, concentrate 10 min: use Int instead of Wis for one chosen skill (Insight/Perception/Survival) vs. branded creature. 10th: 30 ft no-touch, 30 min. 14th: know direction (not distance) cross-Realm. |
| Ideal of Justice | 3,7,15,18 | Second Ideal at 3rd. Buff on new-Ideal-swear: heal `prof`d6/turn, free Skyward, free 1d8 Skybreak/hit, free Augmentation/turn — 1 min. |
| Skies | 3 | Gain a Sky (list below); radius scales 5→25 ft; can't change once chosen. |
| Division | 5 | Grants Surge + cantrip; unlocks higher-tier Augmentations. |
| Extra Attack, Shardblade Stance | 5 | Standard. |
| High Vigilance | 6 | On unsurprised initiative: free fly or free Shardweapon summon. |
| Shardblade | 7 | Standard summon/dismiss; +2 at 15th. |
| Ceaseless Lashings | 11 | Melee hits always +1d8 axial. |
| Invested Potency | 11 | +2 Con/Int saves (+3/+4 scaling), standard pattern. |
| Gravityplate | 15 | Reaction vs. crit (B/P/S): downgrade to normal hit for that damage type. |
| Enforcer of Justice | 20 | Str-or-Dex +2, Int +2; Forced Justice (force a save to fail once/rest, after result revealed). |

**Skybreak Augmentations (24 confirmed)**: Burdening, Calamitous, Crackling,
Crippling, Debilitating, Defensive, Distracting, Explosive, Gleaming,
Igniting (9th), Implosive, Launching (9th), Pernicious, Plunging, Pushing,
Revitalizing, Rotting (13th), Rushing, Slowing, Stupefying (9th),
Terrorizing, Thunderous, Volatile, Weakening — full per-die mechanics
extracted by the fork (each scales bonus damage/effect by Skybreaks spent,
gated at prereq levels 5th/9th/13th where noted).

**Skies (16 confirmed)**: Accuracy (17th), Armor (17th), Confidence (10th),
Courage, Destruction (10th), Distraction (10th), Division (10th, 1d4→1d6
necrotic at 18th), Fear, Focus (10th), Guarding, Haste, Liberation,
Protection (10th), Saving, Vigilance, Warding (17th).

**Highspren stat block** (`HB:2796-2851`) — **severely garbled**, worse than
Honorspren: only AC 14 is a trustworthy recovered number; all ability scores,
Speed, Senses, Languages lost to fragment debris. Traits/Actions partially
reconstructable: Empathetic Link (3rd), Highspren Warden (3/long rest, merge
senses with spren, darkvision 120 ft, extends to 30 min at 3rd/1 hr at 7th),
Invested Sight (1/long rest, 7th level, sense Surgebinders/Corruptions within
100 ft for 1 min, narrows to 30 ft/10 min at 15th).

**Ideal of Justice Feats**: 3rd (Furtive Justice, Inexorable Justice, Keen
Justice). **Flagged structural defect** (`HB:2868-2880`): the "Level 3" and
"Level 7" headers appear transposed/misordered in the source — Sky Focus,
Stormlight Efficiency, and Skybreak Overpower read mechanically like 7th-level
content but sit under a "Level 3" label. 15th (Mighty Lashings, Perfect
Vigilance, Stormlight Body). 18th (Sky's Conqueror, Sky's Savior, Sky's
Tempest).

---

### 3.3 Dustbringer / "Releaser" (`HB:2914-3499`)

**Naming note**: mechanically titled "Dustbringer" (class heading, table
header), but flavor text and even some feature names use "Releaser"
throughout — confirmed intentional in-fiction naming at `HB:2926`: *"Due to
their name's similarity to 'Voidbringer,' they usually prefer to be called
Releasers."*

| Feature | Level | Rule |
|---|---|---|
| Abrasion | 1 | Surge granted (no Division until 5th); cantrip Abrasion. Investiture ability = Wisdom. |
| Ashspren | 1 | Companion. |
| Infused Skin | 1 | Unarmored/unshielded AC = 10 + Dex mod + Wis mod. |
| Infused Hands | 1 | Unarmed/proficient-weapon + no armor/shield: Dex for attack/damage; roll Infused die (d4→d10 scaling) instead of normal damage die; bonus-action unarmed strike on Attack action. |
| Release Abilities | 2 | Pool of Releases (2, scaling per table) fuels Release Abilities; regain all on short/long rest. Know 3 abilities at 2nd, scale per table. Invested save DC = 8+prof+Wis. |
| Infused Feet | 2 | +10 ft speed unarmored/unshielded, scales per table. |
| Stormlight Healing | 2 | Bonus action + 2 Releases: roll Infused die + Wis mod heal; extra Releases (from 5th) add extra dice, capped at prof bonus/turn. |
| Self-Masteries | 2 | Choose 1 (permanent, list below) at 2nd; scale per table. |
| Ideal of Discipline | 3,7,11,18 | Buff on swear: heal `prof`d6/turn, +10 speed, advantage on attacks, free Release Abilities — 1 min. |
| Division | 5 | Grants Surge + cantrip; unlocks higher Release Abilities. |
| Invested Strikes | 6 | Unarmed strikes count as Invested (bypass non-Invested resistance/immunity). |
| Evasion | 6 | Standard (Dex save: success=no dmg, fail=half). |
| Shardblade | 7 | Standard; eyes bright red. |
| Control of Abrasion | 10 | Move on vertical surfaces/liquids without falling while moving. |
| Invested Potency | 11 | +2 Dex/Str saves, standard scaling. |
| Flameplate | 11 | Improves Infused Skin: summon Flameplate (initiative or at-will bonus action), AC = 11+Dex+Wis. |
| Elusive Abrasion | 14 | Ranged attacks (weapon + Invested Art) against you at disadvantage while not incapacitated. |
| Divisive Hands | 15 | Unarmed hits: +1 Infused die (fire or necrotic, chosen per use). |
| Controlled Destroyer | 20 | Dex/Wis +2; Release-refund on low-initiative roll; eyes permanently bright red. |

**Release Abilities (19 confirmed)**: Abrasive Air, Abrasive Strikes,
Courageous Resolve (9th), Decaying Strike (13th), Elusive Defense, Infused
Blood (9th), Infused Strength, Insightful Focus, Invested Toughness (17th),
Mindful Resolve (5th), Refocus (5th), Ruby Strike (5th), Slick Agility,
Slippery Trip (9th), Slowed Fall (5th), Stillness of Mind (13th), Stunning
Strike (9th), Surged Accuracy (17th), Surged Protection — each expends 1-3
Releases for a discrete tactical effect (damage add-ons, conditions,
mobility, saves).

**Self-Masteries (14 confirmed, permanent/unswappable)**: Mastery of
Abrasion, Composure (17th), a Craft (5th), Fate (5th), Fire (5th), Focus
(17th), Infusion (9th, +1 die size), Intuition, Necrosis, Perception (5th),
Precision (5th, crit range +1), Shardblades (9th), Speed, Study.

**Ashspren stat block** (`HB:3347-3431`) — garbled like the others; AC 18, HP
= Dustbringer level + prof bonus, Fly 30 ft/Climb 30 ft are trustworthy; a
suspicious "22" value appears amid ability-score fragments and should not be
trusted without a source-PDF check. Traits: Infused Being (AC = 10+Dex+Wis),
Inner Workings (enter an item), Telepathic Link. Action: Ember's Light
(variable bright/dim light control, disables own invisibility while active).

**Ideal of Discipline Feats**: 3rd tier includes Quick Distraction/Guard/
Stealth (Help/Guard/Hide as bonus action for 1 Release each — level
attribution ambiguous per a flagged heading-order defect) plus Deluge of
Abrasion, Explosive Division, Visage of Ash (AoE control/damage, scaling
3rd→11th→18th, 1/long rest else 3 Releases). 11th: Counter Release,
Releaser's Blade, Release of Luck. 18th: Shield of Light, Strike of Weakness,
Touch of Death.

---

### 3.4 Edgedancer (`HB:3499-4230`, spren block gap noted below)

| Feature | Level | Rule |
|---|---|---|
| Abrasion & Progression | 1 | Surges + cantrips. Investiture ability = **Wisdom** (confirms CLAUDE.md). |
| Cultivationspren | 1 | Companion. |
| Invested Arts | 1 | Prepare = Wis mod + level (min 1) Arts; swap = Wis mod (min 1) on long rest. IP cost table matches Part 2 exactly. |
| Edgedance | 2 | Action: enter a Form (10 forms below), gain separate Form-HP pool, up to 1 hr; uses = prof bonus/rest; unlimited at 20th. |
| Form Progressions | 2 | 10 forms, each Starting→2nd→3rd(lvl 5)→4th(lvl 11)→5th(lvl 17). Choose 2 initially, scale per table. |
| Ideal of Advocation | 3,6,10,14 | Buff on swear: free-form-entry double-HP, +10 speed, cast up to Max Level in form, double healing dice — 1 min. *(Feat detail text for this tier fell in an unread gap, `HB:4229-4321` — flagged, not fabricated.)* |
| Shardblade | 6 | Standard; eyes light gray/near-white. |
| Invested Potency | 11 | +2 Wis/Cha saves, standard scaling. |
| Lifeplate | 11 | Entering a 4th-Progression-or-higher form: bonus Form-HP = Edgedancer level. |
| Resistance of Regrowth | 18 | Daily choice of resistance (acid/cold/fire/lightning/poison/thunder). |
| Limitless Dancer | 20 | Wis +4; unlimited form entry (from normal form only); eyes permanent. |

**The 10 Edgedance Forms** (each: Starting/2nd/3rd(5th)/4th(11th)/5th(17th)
progression, own Form-HP formula and effects) — **Blood** (melee/HP tank,
extra weapon damage die), **Foil** (pure Form-HP scaling, confirmed it *does*
reach 5th Progression contrary to the initial premise), **Lucentia**
(healing — Lucentia Dice d4→d8, Vev's Protection reaction; flagged internal
60-vs-50-ft range inconsistency at `HB:3906/3908`), **Pulp** (casting-level
boost + Wis-for-Con concentration swap), **Sinew** (size/reach control,
difficult-terrain aura), **Spark** (Wis-for-weapon-attacks, flanking
advantage), **Tallow** (aquatic/no-breathing), **Talus** (defense/AC,
prone-immune, anti-forced-movement), **Vapor** (climbing/falling/Stealth),
**Zephyr** (speed/Dash-Disengage utility, ally speed aura). Full per-tier
numbers extracted by the fork.

**Flagged gaps**: Cultivationspren stat block and the Edgedancer's own Ideal
of Advocation Feats detail text both fall in the unread range `HB:4229-4321`
(between the Edgedancer and Truthwatcher read windows) — not fabricated,
simply not yet extracted. Recommend a targeted follow-up read of that range.
Recurring OCR token "gtets" in weapon-proficiency lists across multiple
classes is an unresolved garbled weapon name, not guessed at.

---

### 3.5 Truthwatcher (`HB:4322-4776`)

| Feature | Level | Rule |
|---|---|---|
| Progression & Illumination | 1 | Surges + cantrips. Investiture ability = **player's choice of Int/Wis/Cha, fixed permanently once chosen** (`HB:4430`, confirms CLAUDE.md). |
| Mistspren | 1 | Companion. |
| Invested Arts | 1 | Standard IP-cost table (Part 2); swap via Pailiah's Study. |
| Truth Dice | 1 | Bonus action: give another creature within 60 ft a Truth die (size scales d4→d10); usable within 10 min on one check/attack/save, consumed on use; one die/creature at a time. Uses = prof+Investiture mod (min 1)/long rest. |
| Truth's Favors | 2 | Choose 2 Favors (list below); scale per table. |
| Illusory Elusion | 2 | Base AC = 11+Dex (12+Dex at 10th). |
| Ideal of Verity | 3,6,14,18 | Buff on swear: heal `prof`d4/turn + free Truth-die-roll-adds for self/ally within 60 ft — 1 min. |
| Truthwatch | 5 | Action+concentration: Bewildering (disadvantage on attacks near you) or Exacting (advantage) variant, radius/uses scale 30ft/1 → 60ft/2(10th) → /3(18th). |
| Shardblade | 6 | Standard; eyes bright green. |
| Invested Potency | 11 | +2 Wis/Int saves, standard scaling. |
| Concentrationplate | 14 | Bonus action, 1 min: AC = 14+Dex. Uses = Investiture mod(min 1)/long rest. |
| Scholar of the Highest Truth | 20 | Investiture ability +4; Truth Dice partial refund on low initiative; eyes permanent. |

**Favors (14 confirmed)**: Abundance of Truth (5th, extra uses), Armor's
Favor (5th), Copious Favor (5th, gift 2 dice), Favor of Instinct (10th, free
initiative gift), Favor of the Beyond (10th, death-save save), Favorable
Speed (5th), Favorable Tumult (10th), Font of Truth (5th, short-rest refill),
Truth's Regrowth (healing), Infectious Truth (10th), Investiture's Favor
(Art damage/heal boost), Reliable Favor (10th, floor the die), Steel's Favor
(weapon damage add), Unfailing Truth (10th, keep die on failed use).

**Mistspren stat block** (`HB:4658-4709`) — the source explicitly rendered
this stat block as `assets/image_5.png` rather than text; only Size (Tiny)
and Type (Splinter) survived as clean text, plus a fragmentary reaction
guessed as "Trust's/Truthspren's Favor" (6th level, reroll a Truth die,
scaling 2/rest at 14th, 3/rest at 18th). Recommend manual transcription from
the source image.

**Ideal of Verity Feats** — all four tier headings render as literal `'???'`
(`HB:4714, 4734, 4746, 4760`), a genuine content gap. 3rd: Study of
Abilities, Study of Battle, Study of the Cognitive Realm. 6th: Blade Prowess,
Cognitive Allure, Essence Regrowth. 14th: Psychic Strike, Recoiling Mists,
Truthful Skill. 18th: Intrepid/Ruinous/Vivid Truthwatch (three new Truthwatch
options).

---

### 3.6 Lightweaver (`HB:4776-5236`)

| Feature | Level | Rule |
|---|---|---|
| Illumination & Transformation | 1 | Surges + cantrips. Investiture ability = **Charisma** (confirms CLAUDE.md). |
| Cryptic | 1 | Companion. |
| Invested Arts | 1 | Standard IP table. |
| Innate Lightweaving | 2 | Free at-will *Lightweave self* (visual disguise, detectable via Int(Investigation) vs. DC). Uses=prof bonus/long rest; unlimited at 9th. |
| Stormlight Healing | 2 | Action, 3 IP: 1d4+Cha heal (or neutralize a poison instead, no heal); +1d4/extra 3 IP. |
| Surgebinding Study | 2 | Know 2 Techniques (list below, metamagic-analogue); +1 at 5th/10th/17th. |
| Ideal of Honesty | 3,6,14,18 | Buff on swear: heal `prof`d4/turn, free/discounted Art cast, stackable Techniques — 1 min. |
| Surge Experimentation | 3 | +1 extra prepared Art slot (1st-5th, swappable each rest); +1 more at 9th, +1 more at 17th. |
| Shardblade | 6 | Standard; eyes crimson. |
| Castweaving / Conjure Castweaving | 10 | Soulcast while Lightweaving (physical illusions); always-known *conjure Castweaving* Art (summons controllable creatures). |
| Invested Potency | 11 | +2 Con/Cha saves, standard scaling. |
| Creationplate | 14 | Reaction, AC bonus = prof+Cha(min 1) vs. one hit; 1/long rest, 2× at 18th, 3× at 20th. |
| Resonant Radiant | 20 | Cha +4; 6th/7th-level Arts castable twice/rest; one Surge Experimentation slot can hold a 6th-level Art. |

**Surgebinding Techniques (14 confirmed)**: Deliberate Surge (auto-succeed a
save), Distant Surge (double range), Empowered Surge (reroll damage),
Extended Surge (double duration), Focused Surge (boost concentration save),
Lingering Surge (delay an Art's end past lost concentration), "Precise Suge"
[sic, OCR-dropped 'r' — single-target an area save], Quickened Surge (action
→ bonus action), Relentless Surge (impose disadvantage on a save), Secret
Surge (cast without G/S components), Seeking Surge (reroll a missed attack),
Soulcasted Surge (swap elemental damage type), Twinned Surge (2nd target),
Widened Surge (+50% AoE dimensions).

**Cryptic stat block** (`HB:5129-5169`) — badly garbled; no ability scores
recoverable at all (only header fragments survived). Traits/Actions
partially legible: Cryptic Translation (language assist), Spren Pick (3rd,
lockpicking assist), Voice Mimic (6th, 3/long rest, mimic a heard voice),
Absorb Lightweaving (6th, project the disguise onto a companion).

**Ideal of Honesty Feats** — heading confirmed identical ("Speak an
individual truth about yourself") at all 4 tiers. 3rd: Eyes of the Dark,
Infused Poise, Soulcasted Resilience. 6th: Essence Inclination, Restorative
Cast, Strengthened Flesh. 14th: Erratic Essence, Shadowstep, Trance of Focus.
18th: Cognitive Form, Essenceplate, Surge of Triumph.

---

### 3.7 Elsecaller (`HB:5236-5799`)

| Feature | Level | Rule |
|---|---|---|
| Transformation & Transportation | 1 | Surges + cantrips. Investiture ability = **Intelligence** (confirms CLAUDE.md). |
| Inkspren | 1 | Companion. |
| Invested Arts | 1 | Casts every 1st-5th Art at its **highest possible level** (per Part 3 order-summary), flat **1 IP** per cast regardless of level. |
| Inksurges | 2 | Gain 2 (list below); scale per table. |
| Stormlight Healing | 2 | Action, 1 IP: heal `Art-level`d6 + Int mod. |
| Ideal of Potential | 3,6,10,14 | Buff on swear: heal `prof`d4/turn, free/half-Max-Level Art cast, attack/save die-boost — 1 min. |
| Elsecall | 5 | Create Physical↔Cognitive perpendicularity (1 min setup, Medium-or-smaller, lasts to end of next turn). 9th: action-only, 1 min duration, Large creatures, bidirectional, 2-way usable during window. 1/long rest. |
| Shardblade | 6 | Standard; eyes teal. |
| Adept Soulcasting | 9 | Free *Soulcast* Art; needs only Medium (not Large) polestone; cracks only on failing by 10+ (not 5+). |
| Logicplate | 10 | Reaction, AC bonus = prof bonus, 1/long rest (or 1 IP if no uses left). |
| Cognitive Discoveries | 11,13,15,17 | One free 6th/7th/8th/9th-level Art each, 1 use/long rest, doesn't count against normal known Arts. |
| Invested Potency | 11 | +2 Wis/Int saves, standard scaling. |
| Realmatic Mastermind | 20 | Int +4; 6th-level Discoveries slot becomes swappable; Discoveries slots can cast lower-level Arts too. |

**Inksurges (30 confirmed)**: Agonizing Cast, Bead Sight, Blade Prowess
(5th), Casted Plate, Chains of Shade (15th), Cognition's Whisper (5th),
Cognitive Focus, Elsecast Explosion (18th), Elsecast Fighter (15th),
Elsecast Hinder/Pull/Push/Snipe, Fall into Shadow (5th), Improved Blade
(12th), Inksight, Inkspren Insight, Inkstep (7th), Investiture Peek (5th),
Maddening Ink (5th), One with Shadow (5th), Realmatic Knowledge (9th),
Rotting Blade (12th), Shade Gaze (9th), Shadesight (15th), Shadesmar Peek,
Shadowtouch (15th), Shattercast (5th), Soulcasted Protection/Regression/Vex
(5th), Ultimate Blade (18th), Watercasting (5th).

**Inkspren stat block** (`HB:5663-5757`) — AC 13 recovered cleanly; ability
scores unreliable (fragments only). Traits: Size and Speed (Tiny=10ft,
Small=20ft, Medium=30ft, bonus-action resize), Deliver touch (3rd, reaction,
deliver a touch-range Art for you; 2/rest at 10th, 3/rest at 14th).

**Ideal of Potential Feats** — all 4 tier headings are literal `'???'`
(`HB:5717, 5759, 5773, 5787`), a genuine gap. 3rd: Breath of Shadesmar,
Cognimessage, Elsecast Experimentation. 6th: Cognitive Luck, Inky Escape,
Realmatic Shift. 10th: Essence Protection, Force of Cognition, Soulcasted
Blood. 14th: Body of Stormlight, Inky Vengeance, Spiraling Mind.

---

### 3.8 Willshaper (`HB:5799-6438`)

| Feature | Level | Rule |
|---|---|---|
| Transportation & Cohesion | 1 | Surges + cantrips. Investiture ability = **Charisma** (confirms CLAUDE.md). |
| Reacher | 1 | Companion. |
| Axi Attack | 1 | Once/turn extra damage die (1d6→10d6 scaling) on advantage-attack hit with finesse/ranged weapon; also triggers on ally-flanking condition. |
| Cunning Action | 2 | Dash/Disengage/Hide as bonus action. |
| Willshape | 2 | Action: invisibility (broken by attack/damage/forced-save), up to 10 min extendable; uses = Cha mod(min 1)/long rest. 10th: bonus action, up to 1 hr. |
| Cognitive Powers (+ Cogni Dice) | 2 | Know 1 (list below), scale per table. **Cogni Dice**: count = Cha mod + prof bonus, base d4, scales d4→d10; regain all on long rest. |
| Stormlight Healing | 2 | Bonus action: expend ≤2 (scaling to ≤prof bonus) Cogni Dice, heal + Cha mod. |
| Ideal of Liberation | 3,7,13,17 | Buff on swear: heal `prof`d6/turn, extra Axi-Attack dice, free Cognitive Power/turn — 1 min. |
| Realmatic Dodge | 5 | Reaction: halve one attack's damage. |
| Elsecall | 6 | Same mechanic as Elsecaller's (Part 3.7), improved at 10th. |
| Shardblade | 7 | Standard; eyes purple. |
| Evasion | 9 | Standard. |
| Invested Potency | 11 | +2 Dex/Cha saves, standard scaling. |
| Joyplate | 13 | Stacks with Realmatic Dodge reaction: halves damage again (net ¼); 1/rest→2×(17th)→3×(20th). |
| Shadowsight | 14 | Sense hidden/invisible creatures within 10 ft. |
| Knight of Shadow | 20 | Dex/Cha +2; reroll Axi-Attack/Cogni dice; eyes permanent. |

**Expressions (12 confirmed)**: Accurate (18th), Armored, Cognitive (6th, +1
die + short-rest partial recharge), Devastating (11th, crit range +1),
Elusive (18th), Expert (repeatable expertise), Fighting (6th), Fortifying
(15th, Wis-save expertise), Freeing, Illicit, Stoic (15th), Talented (11th).

**Cognitive Powers (17 confirmed — more than the ~14 estimated)**: Analyzing
Axi (7th), Cogni Door (15th), Cogni Impalement (15th), Cogni Jump (7th),
Cogni-Powered Knack, Cogni Shadows (11th), Cogni Whispers, Cognitive Help
(7th), Cognitive Location (7th), Counter-Cognition (18th), Enervating Axi
(11th), Extracting Axi, Focused Cognition (5th), Homing Attack (11th),
Invested Sight (7th), Stunning Axi (18th), Vulnerable Axi (18th) — each
expends 1-3 Cogni Dice.

**Reacher stat block** (`HB:6280-6346`) — garbled; AC 16, Fly 30 ft,
Passive Perception 9, Prof Bonus +2, Size Tiny, Type Splinter recoverable.
Traits: Cognitive Pulses (telepathic light-pulse communication); Actions:
[Open] Hand (Adhesion-style object manipulation), Light (bonus action,
variable brightness).

**Ideal of Liberation Feats** — **flagged structural defect**
(`HB:6348-6437`): Level 3/Level 7 headers appear back-to-back with no clear
content boundary and a stray unrelated stat-block fragment bleeds in;
attribution of Healing from the Cognitive Realm / Speed from Shadesmar /
Strength from the Beyond between "3rd" and "7th" is ambiguous in the source
itself. 13th (confirmed): Cognitive Piercing, Ghostly Willshape, Imposter.
17th (confirmed): Axi Strike, Heraldic Reflexes, Sudden Strike.

---

### 3.9 Stoneward (`HB:6438-6829` features, `HB:6829-7727` Stance Masteries, `HB:7729-7787` spren/feats)

| Feature | Level | Rule |
|---|---|---|
| Cohesion & Tension | 1 | Surges + cantrips. Investiture ability = **Constitution** (confirms CLAUDE.md). |
| Peakspren | 1 | Companion. |
| Ward | 1 | Bonus action (not in heavy armor): (1) advantage on Str checks/saves, (2) bonus damage die (scales d4→d10) on Str-based melee hit, doubled on crit, (3) **resistance to non-Invested B/P/S** — all three clauses confirm CLAUDE.md's summary exactly, `HB:6592-6604`. Can't cast/concentrate on Arts while in Ward. 1 min, uses per table, full recharge on long rest. |
| Unarmored Defense | 1 | AC = 10+Dex+Con unarmored; shield-compatible; Shardplate doesn't break it at 10th. |
| Shardblade Stance | 1 | **Confirmed: granted at 1st level** (unlike the base 5th-level grant most other orders use) — choose 2 initially. |
| Stonewalking | 2 | Climb speed 15 ft (vertical/inverted, hard surfaces); = full walking speed at 9th. |
| Stormlight Healing | 2 | Dice = 2×prof bonus, size = current Ward die; bonus action, expend any number. |
| Senses of Resolve | 2 | Choose 1 (list below, permanent), scale per table. |
| Stance Masteries (+ Investiture Ability) | 2 | Know 3 (stance-gated), scale per table; framework detailed below. Investiture ability = **Constitution**, confirmed. |
| Ideal of Dependability | 3,6,10,14 | Buff on swear: heal `prof`d6/turn, free Ward-entry (extends if already active, can add free Shardblade at 6th+), crit range +1, double Ward-die on hit, auto-stance-entry — 1 min. |
| Extra Attack | 5 | Standard. |
| Shardblade | 6 | Standard; +2 at 10th, +3 at 18th; eyes orange. |
| Battle Prowess | 6 | Once/turn bonus action: do 2 of {enter Ward, enter a stance, summon Shardweapon, change Shardweapon form}. |
| Bindplate | 10 | Auto-summons alongside Ward if unarmored; resistance extends to **Invested** B/P/S too while both active. |
| Relentless Ward | 11 | 0-HP-in-Ward save (DC 10, +5/use, resets on rest) → drop to 1 HP instead. |
| Invested Potency | 11 | +2 Con/Str saves, standard scaling. |
| Champion of Stone | 20 | Str/Con +2; +10 speed in Ward; can extend Ward past 1 min without bonus action (except after unconsciousness/heavy-armor-donning); eyes permanent. |

**Senses of Resolve (19 confirmed)**: Body (11th, exhaustion mitigation),
Battle (initiative advantage, no-surprise), Bravery (7th), Cognitive (15th,
+2 INT/WIS/CHA saves), Danger (Dex-save advantage), Darkness (7th,
darkvision), Defense (11th, AC boost), Focused (15th), Intimidation
(Str-for-Cha), Light (11th, +2 healing dice), Nature (double travel pace),
Predator (hearing Perception advantage), Savagery (15th, Ward-die upsize),
Sentry (11th, long-range vision), Speed (7th, +5 ft), Strength (15th, floor
Str checks at the score), Surged (7th, extend Ward to 5 min once/rest), Tough
(7th, HP scaling), Tracker (7th), Vitality (15th, cheaper Relentless Ward).

#### Stance Masteries subsystem (`HB:6829-7727`, ~150 abilities)

Each of the 10 base Shardblade Stances (Part 5) gates its own Mastery list;
text confirms this ties directly into the Chapter 6 Shardblade Stances system
(*"You can learn the following [X]stance Masteries if you know the [X]stance
Shardblade stance"*). No separate flavor blurb per stance beyond that gating
line. Counts: **Bloodstance** 11 (3 Attack Masteries + 8 named), **Crystalstance**
12 (0+12), **Flamestance** 13 (3+10), **Ironstance** 12 (3+9), **Oilstance**
12 (0+12), **Smokestance** 13 (3+10), **Stonestance** 13 (3+9 expected +1
unlisted "Stone Efficiency" = 10 named — flagged below), **Thewstance** 12
(3+9), **Vinestance** 12 (0+12), **Windstance** 13 (3+10). All named masteries
were extracted with full verbatim mechanics by the dedicated fork (dice
bonuses, save DCs, reaction economies, stance-exit conditions) — full per-
stance tables live in the fork's report; representative pattern: each Stance
grants an entry method (bonus action, sometimes with a resource cost like
Stonestance's 15-ft movement expenditure), an exit condition (usually a
critical failure on an attack), and its Masteries either buff the Stance's
signature mechanic (bonus opportunity-attack reactions for
Blood/Crystal/Oil/Vinestance; extra "free" attacks for Flamestance;
crit-range shifts for Ironstance; movement-triggered bonus damage for
Smoke/Windstance; unarmed-strike options for Thewstance; reduced-attack/
increased-damage tradeoffs for Stonestance).

**Flagged source defects in Stonestance specifically**: an unlisted mastery
"Stone Efficiency" appears merged inline with Stone Body's text at
`HB:7401` with no heading break — a genuine 10th named mastery beyond the
9 originally catalogued, needs verification against the physical book; "Stone
Ferocity"'s body text is split by a page-reflow artifact, with an orphan
fragment displaced after "Stone Slide"; "Attack Mastery: Shattering" mixes
a Bludgeoning weapon-requirement heading with slashing-weapon/"seizing
attack" body text (apparent copy-paste bleed from Smokestance's "Seizing"
entry); "Stone Perfection" references "the Efficiency Stone mastery"
(reversed word order from "Stone Efficiency"). Also flagged: Windstance's
"Attack Mastery: Whirling" body text twice mislabels itself a "swiping
attack" (name collision with the preceding, mechanically distinct "Swiping"
entry); Vinestance's "Vine Haste" describes "reactions to make opportunity
attacks," inconsistent with Vinestance's actual damage-reduction mechanic —
likely a templating error copied from the other stances' "Haste" masteries.

**Peakspren stat block** (`HB:7729-7787`) — the **worst-preserved** of all
ten companion blocks: Senses/Languages fields are replaced entirely by an
embedded image (`assets/image_9.png`); ability scores unrecoverable as
numbers; only AC 14 (header) and Size Tiny / Type Splinter survive cleanly.
A **possible in-source contradiction** is flagged: the header states "Armor
Class 14" while the "Splinter of Rock" trait gives a formula (AC = 10+Str
mod+Con mod) that isn't reconcilable without the (missing) actual ability
scores. Traits: Speak Through Stone (3rd, telepathy through touched
stone/dirt/brick). Actions: Detect Tremors (6th, 1/long rest, tremorsense 30
ft/10 min, scaling to 50ft/30min at 10th and 100ft/1hr at 14th — note the
source lists the 14th-level upgrade before the 10th-level one, an ordering
oddity in the text itself).

**Ideal of Dependability Feats** (`HB:7779-7787`) — printed as one dense
unbroken paragraph with per-feat line delineation lost; three of four tier
headers (6th, 10th, 14th) have unresolved `'???'` subtitle placeholders (only
3rd's "I will be where I am needed" survived). 3rd: Companions Stonewalking,
Extra Proficiencies, Invested Awareness. 6th: Surge of Axi/Health/Movement
(aura effects on Ward-entry). 10th: Determined Stoicism, Inspiring Beacon,
Threatening Visage (all: half-prof-bonus uses/long rest, roll-and-apply a
Ward-die). 14th: Unstoppable Ward, Vital Ward, Ward Beyond Death.

---

## PART 4 — Shardweapons & Shardplate

| Mechanic | Line | Rule | In json? |
|---|---|---|---|
| Shardweapon baseline | `HB:9058-9067` | Cosmere's equivalent of magic weapons; minimum +1 (attack & damage); can reach +2/+3 via specific class features. Invested, so bypass non-Invested resistance/immunity. Cannot easily cut non-living material or sever limbs/instant-kill spiritwebs (a Shardweapon-accuracy variant rule exists in Appendix B for GMs who want the book-accurate lethality). | No |
| Three Shardweapon categories | `HB:9062-9064` | (1) living-spren weapons (`spren` property, from a Radiant's bonded spren — every order's Shardblade feature uses this), (2) true Shardblades (`Shard` property, from a dead spren — rare, owned by nobility, e.g. Honorblades/Nightblood detailed elsewhere), (3) Shardbearer-only heavy weapons (Shardhammer, Grandbow — mimic Shardweapons but require intact Shardplate chest+both arms). | No |
| `spren` weapon property | `HB:9038` | Appears as a bonus action, immediately; changeable to a different spren-weapon form with another bonus action; can become a Shardshield with an action; disappears if dropped or if the bonded spren leaves the wielder's space; **cannot form or be used in the Cognitive Realm**; can activate Oathgates; always a +1 Invested weapon. | Partially — orders' Shardblade features restate parts of this |
| `Shard` weapon property | `HB:9038` | True dead-spren Shardblade: summoned via **two consecutive bonus actions** (must be used on directly-sequential turns for the Blade to appear); disappears if it ever leaves the owner's hand; cannot form/be used in Cognitive Realm; reappears next to the owner's body on death; always a +1 Invested weapon. | No |
| Versatile Shardweapons | `HB:9148-9152` | A living spren can manifest as any solid metal object/weapon (Shardtrident, Shardglaive, Shardstaff, even non-weapons like a Shardkey/Shardchisel), subject to GM; retains the base weapon's stats plus `hidden`+`spren` properties and +1 Invested; classified simple or martial matching its base form. | No |
| Shardweapon table | `HB:9124-9147` | Full stat lines for Sharddagger, Shardspear, Shardaxe, Shardblade (both spren- and Shard-property variants, differing die/properties), Shardgtet, Shardhalberd, Shardhammer (both a spren-version 1d8 versatile and a Shardbearer-only 2d12 heavy version), Shardlongsword, Shardsword, Shardcrossbow (hand/large), Shardbow, Shardlongbow, Grandbow. All spren/Shard-property weapons show `-` cost (not purchasable); Shardbearer-only weapons (Shardhammer heavy, Grandbow) show literal `???` costs — a genuine unset-price gap in the source, not an OCR error. | No |
| `Shardbearer` property | `HB:9038` | Usable only if wearing Shardplate with at least the chest and both arms intact. | No |
| Shardplate | `HB:9005-9022` | Full mechanical details deferred to *Invested Items Collection* (a separate, also-missing sourcebook — same pattern as the Invested Arts gap). Confirmed present here: don/doff time = **15 minutes** each (vs. 1/5/10 min for light/medium/heavy armor, 1 action for shields); no class grants Shardplate proficiency (`HB:8905`, campaign-specific/GM-arbitrated). | No — AC/HP formulas not in this source at all |
| Order-specific living Shardplate | Various (Windplate, Gravityplate, Flameplate, Lifeplate, Concentrationplate, Creationplate, Logicplate, Joyplate, Bindplate) | Each order's living-Shardplate feature (cited individually in Part 3) is a **class feature**, not the generic Shardplate item — typically reaction-triggered AC/damage-mitigation, distinct mechanically from purchased/found Shardplate (whose full rules are in the missing Invested Items Collection). | Partially — only in the sense that Windrunner's Windplate is catalogued above |
| Living-Shardplate spren composition | `HB:13974-13991` (Spren flavor list) | Confirms which spren type composes each order's living Shardplate: bindspren (Stoneward), concentrationspren (Truthwatcher), creationspren (Lightweaver), flamespren (Dustbringer), gravitationspren (Skybreaker), joyspren (Willshaper), lifespren (Edgedancer), logicspren (Elsecaller), windspren (Windrunner). | No |

---

## PART 5 — Shardblade Stances (base 10, Ch. 6, `HB:11353-11532`)

Entered as a bonus action while wielding a proficient melee weapon; lasts
until start of your next turn; exiting is free-action, forced by
incapacitation/dropping the weapon, or a per-stance failure condition; cannot
hold two stances at once (entering a new one exits the old); can never
re-pick an already-known stance.

| Stance | Core mechanic | Exit condition |
|---|---|---|
| Bloodstance | +1 extra reaction, OA-only; OA trigger widens to "moves within reach" (not just leaves it) | Both extra reactions used, or a critical-failure OA |
| Crystalstance | +1 extra reaction, OA-only; OA trigger widens to "hits you with a melee attack while in reach" | Both extra reactions used, or a critical-failure OA |
| Flamestance | Each melee hit → free disadvantage second attack (same weapon, same target, capped at your normal Attack-action count); damage dice-only, no modifiers | Any critical failure (normal or free attack) |
| Ironstance | Crit range +2 (max 3) on melee attacks; crit-fail range also +1 | Critical failure, or (separately) landing a critical hit |
| Oilstance | +1 extra reaction, OA-only; OA trigger = "misses you with a melee attack while in reach" | Both extra reactions used, or a critical-failure OA (still misses) |
| Smokestance | Bonus damage (= attack's ability mod) on a hit immediately after moving ≥5 ft; reaction: +½ prof bonus (rounded down) AC vs. one melee attack, decided pre-roll | Critical failure, or still getting hit after using the AC reaction |
| Stonestance | Entry costs 15 ft of movement; immovable + advantage vs. forced-prone; attack rolls at -1d6 but +1 extra damage die on hit | Critical failure, or moving at all while in the stance |
| Thewstance | One-handed weapon only, empty off-hand; melee hit within 5 ft → free special unarmed strike (damage / 5-ft push / 5-ft pull-swap) | Any critical failure (weapon or unarmed) |
| Vinestance | +1 extra reaction, damage-reduction only (1d6+prof bonus vs. one melee hit, attacker must be visible & in reach) | Rolling a 1 on the reduction die |
| Windstance | Melee hit → optional bonus damage (=weapon's ability mod) to a second creature in reach whose AC the same attack roll would also have beaten | Any critical failure |

---

## PART 6 — Radiant Spren (general companion rules, `HB:7787-7966`)

| Mechanic | Line | Rule |
|---|---|---|
| Ideals / bond strength | `HB:7791-7801` | Going against your Order's Ideals weakens the spren bond; if it breaks entirely, all Investiture-based features stop working (spren becomes a "deadeye") until a new Nahel bond is sworn (months/years later per GM) — functionally as drastic as character death; changing Order entirely takes even longer. |
| Per-order Ideal philosophy | `HB:7803-7853` | Full flavor text for what each of the 9 playable orders' Ideals demand (Windrunner=protect the defenseless, Skybreaker=administer chosen justice, Releaser=self-mastery of destructive power, Edgedancer=advocate for ordinary people, Truthwatcher=uncover universal truths, Lightweaver=individual/personal honesty, Elsecaller=potential of self and humanity, Willshaper=freedom in all forms, Stoneward=dependability). |
| Position / sharing space | `HB:7933-7938` | Default: spren shares your space, immune to targeting/damage while doing so (even AoE) except specific anti-spren effects (example given: an "anti-Stormlight raysium dagger"). Leaving your space makes it a normal, targetable creature. |
| Initiative | `HB:7939-7941` | Spren's initiative slot is always directly after yours. |
| Range | `HB:7943-7945` | Max distance from you: 30 ft (base) → 50 ft (5th level) → 100 ft (11th level) → 250 ft (17th level). Exceeding it: spren senses the breach and knows your direction, can only move/Dash, and **you lose all your class features** until it returns; already-active continuous effects (e.g. Windrun flight, Art concentration) may persist at GM's discretion. |
| Appearance & movement | `HB:7947-7953` | Some spren can go invisible; those sharing your space are assumed hidden in your clothing regardless. Movement type/speed on the spren's own stat block; while sharing your space its speed is irrelevant (treated as "in your pocket"). |
| Actions & special abilities | `HB:7955-7961` | Spren cannot take the Attack action and never count as an ally for combat-enhancing features (explicit example: they don't enable the optional flanking rule). Each stat block lists exactly which actions/bonus actions/reactions it has; anything unlisted, it cannot do. |
| Taking damage / 0 HP | `HB:7963-7966` | Spren away from your space can be damaged; at 0 HP it doesn't die — it must spend its turn (Dashing if needed) returning to your space, can't act/lose more HP/draw OAs while at 0, and **you lose all class features** until reunited. |
| Per-spren flavor/appearance/naming | `HB:7863-7928` | Full physical-description and name-list text for all 9 companion spren types (Honorspren, Highspren, Ashspren, Cultivationspren, Mistspren, Cryptic, Inkspren, Reacher, Peakspren) — flavor only, no additional mechanics beyond what's in Part 3's per-order stat-block entries. |

---

## PART 7 — Stormlight itself, spheres, Highstorms, Everstorm (Appendix B, `HB:13993-14232`)

Already itemized with full numbers in Part 1 (economy) and here for the
storm-specific combat/hazard content:

| Mechanic | Line | Rule |
|---|---|---|
| The Weeping | `HB:13997-14011` | 4-week no-highstorm period (2 wks year-end + 2 wks year-start) with constant rain instead; **Lightday** (the single day between halves) is calm/sunny on even years, has a highstorm on odd years. Rain effect: lightly obscured, disadvantage on sight-based Perception, extinguishes open flames. |
| Highstorm structure | `HB:14013-14029` | Travels east→west at **~370 mph**, weakens westward. Stormwall (100 ft wall, **10 min**) → main body (**1d2 hours**) → centerbeat (still eye, Stormfather can speak) → riddens (**1 hour** tail). Infusion rate **1,000 sm/hr (~17 sm/min)**; bundled items infuse as one unit. No infusion during riddens. |
| Highstorm frequency | `HB:14031-14035` | Next highstorm = 1d4+3 days out (3-6 day range). |
| Regional damage modifier | `HB:14043-14045` | Unclaimed Hills & adjacent: **+1 damage die** to all storm-effect damage. Far-west regions (Aimia, Shinovar, Iri, western Yezier/Tashikk, Liafor, Steen, western Tukar isles): **-1 damage die**. |
| Highstorm Stormwall effects/initiative | `HB:14047-14076` | Ranged-disadvantage, difficult terrain, torrential rain/roaring 75-mph wind; Stormlight healing **2d6**/action; Stormwall-slam (DC 18 Con, 10d6 bludgeoning/half + prone unless DC 19 Acrobatics). Initiative 49; d20 table: nothing / Gust of Wind (DC 16 Str, 15 ft push, 3d10 if blocked) / Shrapnel Wind (DC 16 Dex, 3d8 piercing) / Devastating Boulder (DC 16 Dex, 6d6 bludgeoning + prone). |
| Highstorm body effects/initiative | `HB:14077-14109` | Same obscurement, 50-mph wind; Stormlight healing **4d6**. Initiative 49; d20: nothing / Gust (DC 12 Str, 2d8) / Shrapnel (DC 12 Dex, 2d6 piercing) / Lightning Explosion (DC 14 Dex, 2d12 lightning) / Devastating Boulder (DC 14 Dex, 4d6 + prone). |
| Centerbeat | `HB:14111-14113` | GM discretion or d100≥93; Stormfather can speak to non-Bondsmiths here. |
| Highstorm Riddens | `HB:14115-14121` | 1 hour; light rain (extinguishes flames), mild ~10 mph wind; no combat-initiative table given. |
| The Everstorm | `HB:14123-14232` | West→east at **~120 mph**; does **not** infuse Stormlight *or* Voidlight. Frequency 4d4 days clamped 6-14 (flagged minor internal-arithmetic inconsistency vs. the text's own "5 days minimum" claim). Duration **2d4 hours**, no sub-phases (binary on/off). Fused Resurrection (possesses a willing singer, full HP). Singer form-change mirrors highstorm rule. Type roll 1d8 (1-4 rainy, 5-7 lightning, 8 fiery), can shift mid-storm. Each type has its own effects + initiative-50 d20 table (full numbers extracted; Rainy mirrors highstorm-body severity, Lightning drops rain/adds targeted lightning-bolt attacks, Fiery adds ember rain/meteoric explosions). |

---

## PART 8 — Realms of the Cosmere (Appendix C, `HB:14232-14396`)

| Mechanic | Line | Rule |
|---|---|---|
| Three Realms | `HB:14232-14243` | Physical (matter), Cognitive/Shadesmar (perception), Spiritual (soul/Connection — narrative only, no defined mechanics). |
| Perpendicularities | `HB:14248-14256` | Cultivation's (stable, Horneater Peaks pool) and Honor's (unstable, roams, summonable by a Bondsmith). Passing through **renews all dun spheres/polestones/fabrials** carried. |
| Oathgates | `HB:14258-14296` | 300 ft diameter, 15-ft-radius control building (≤28 Medium/Small creatures). Living Shardblade or Honorblade required to activate/lock/unlock (both sides simultaneously for unlock). Transport cost by Ideal sworn: 3rd=500sm(building)/5,000sm(platform), 4th=250/2,500, 5th-or-Honorblade=100/1,000. 1st/2nd Ideal Radiants can't use them (no living Shardblade yet). 10 named cities; only Narak unlocked during True Desolation. |
| Elsecalling | `HB:14297-14299` | Elsecaller/Willshaper feature (Part 3.7/3.8) creates a mini-perpendicularity; Physical→Cognitive easier than the reverse. |
| Cognitive Realm compression | `HB:14311-14319` | **1/5th scale** — 100 miles walked in Shadesmar = 500 Physical-Realm miles. |
| Cognitive Realm limitations | `HB:14321-14323` | **Shardblades and living Shardplate cannot manifest here** — a hard combat-relevant restriction not previously in structured form. |
| Beads | `HB:14337-14369` | Shadesmar's "ocean," each bead = one Physical-Realm object's Cognitive representation. Reading a bead: DC 14 Int(Investiture) or Investiture-casting check; Lightweaver/Elsecaller auto-know via Transformation cantrip and can manifest it (10 min × sm fed). Forcing a bead into the Physical Realm: resists, 1d6 force damage/bead to obstructions. **Commanding Beads table** (full numeric table): Tiny(2½×2½ft/1 action/10sm) → Small(5×5/1 action/50sm) → Medium(5×5/12s/100sm) → Large(10×10/30s/250sm) → Huge(15×15/1min/1,000sm); halved cost for Elsecaller/Lightweaver/Willshaper. |
| Shadesmar economy | `HB:14381-14385` | Stormlight (not spheres) is the currency; items cost ~2-4× Physical-Realm price in pure Light; Translightocators extract Stormlight as payment. |

---

## PART 9 — Cross-checks against `surgebinding.json`

Confirmed **exact matches** (upgrade candidates from `reviewed:false`/scoped
too narrowly, to fully general and verified):

- `invested_save_dc.formula` — verified universal (Ch. 10, `HB:13319`), not
  Windrunner-specific as the json's current structure implies.
- `economies.investiture_points.cost_by_art_level` — verified exact digit-for-
  digit match against `HB:13149-13161`.
- `economies.investiture_points.special` (Elsecaller flat-1-IP rule) —
  verified against `HB:13147, 13173`.
- `economies.stormlight_replenishment` — verified as the same rule stated
  twice in the source (class-boilerplate line 1806 and general-rule line
  12339), word-for-word equivalent.
- All 9 playable orders' `surges`/`economy`/`investiture_ability`/`spren`
  fields — verified against each order's own class-feature text.
- `Bondsmith.playable: false` — verified (`HB:1631`).
- The 9 automated Windrunner Maneuvers already in json (Full Lashing,
  Reverse Lashing, Distracting Attack, Goading Attack, Evasive Movement,
  Riposte, Alerted Lash, Athletic Lashings, Acrobatic Lashings) — verified
  against the fork's from-scratch re-read; mechanics match, no discrepancies
  found.
- `features.windrun` and `features.second_ideal_surge` — verified.

**Genuinely new mechanics found, not represented anywhere in json**:
- The Insufficient-Stormlight failure/recovery path (Part 1).
- Shardblades/living Shardplate cannot manifest in the Cognitive Realm
  (Part 8) — relevant to any Shadesmar-travel or combat logic.
- Oathgate transport-cost table and Commanding Beads table (Part 8) — fully
  numeric, zero prior structured form.
- The other 17 Windrunner Maneuvers beyond the 9 already automated (Agile
  Lashings, Athletic Lashings — wait, already listed — see full list in Part
  3.1; net: Feinting Attack, Flourish, Invested Focus, Invested Perception,
  Lash Ally, Lash Enemy, Lunging Strike, Parry, Precision Attack, Quiet
  Lashing, Rally, Rampage, Rescuing Wind, Saving Lash, Slowing Lash, Thrown
  Lashing, Tripping Lash) plus all 14 Focus options.
- Every other order's entire feature/subsystem list (Skybreak Augmentations
  & Skies, Dustbringer Release Abilities & Self-Masteries, Edgedancer's 10
  Forms, Truthwatcher's Truth Dice & Favors, Lightweaver's Surgebinding
  Techniques, Elsecaller's Inksurges, Willshaper's Cogni Dice & Cognitive
  Powers & Expressions, Stoneward's Ward/Senses of Resolve/~150-entry Stance
  Masteries subsystem) — none of this is in json at all; json currently only
  covers Windrunner in any depth.
- The base 10 Shardblade Stances (Part 5) and the Shardweapon/Shardplate
  general rules (Part 4).
- Highstorm/Everstorm hazard tables (Part 7) and the full Realms chapter
  content (Part 8).

---

## Final lists

### (a) Mechanics fully specified in our source, ready to implement

- Stormlight economy end-to-end: dunning, insufficient-Stormlight recovery,
  polestone substitution, ledger tracking (Part 1).
- Investiture Casting chassis: levels, IP costs, upcasting, cantrips,
  components, duration/concentration, targets/AoE, saves/attacks (Part 2).
- All 9 playable orders' complete non-surge-cantrip kit: every class
  feature, resource pool (Lashing Dice, Releases, Truth Dice, Cogni Dice,
  Wards, Investiture Points), maneuver/augmentation/technique/power/mastery/
  sense list, and Ideal Feat tree (Part 3) — with the specific, listed gaps
  below.
- Shardweapon rules, the base 10 Shardblade Stances, and the Stoneward
  Stance Masteries subsystem (Parts 4-5).
- Radiant Spren general companion rules — position, range, damage-at-0,
  initiative (Part 6).
- Highstorm, Everstorm, and Weeping hazard/initiative tables (Part 7).
- Realms chapter: Perpendicularities, Oathgates, Elsecalling, Cognitive
  Realm compression/limitations, Beads (Part 8).

### (b) Mechanics that could not be authored from the Handbook alone — STATUS AS OF 2026-09-12

> This section originally asserted these mechanics "CANNOT be authored"
> because *The Invested Arts of the Cosmere* was missing from `parsed_data/`.
> **That premise is now false for the first two bullets** — the book has been
> added (`parsed_data/cosmere-5e-the-invested-arts-of-the-cosmere-v2-0/docling.md`,
> 19,794 lines, ~661 Invested Art entries) and fully specifies all 10 surges
> and their named Invested Arts. The remaining bullets are **still accurate**:
> those books were independently confirmed absent by direct search of both
> `resources/rules/` and `parsed_data/` as of this correction — no file or
> directory matching "Invested Items Collection" or "Hoid" exists anywhere in
> either tree.

- ~~All 10 surge effects... names and order-assignments only exist in our
  source.~~ **RESOLVED.** All 10 surges (Adhesion, Gravitation, Division,
  Abrasion, Progression, Illumination, Transformation, Transportation,
  Cohesion, Tension) now have full mechanical write-ups — casting time,
  range, components, duration, attack/save, damage — in the Invested Arts
  document. See `COSMERE_ARTS_SURGEBINDING_A.md` /
  `COSMERE_ARTS_SURGEBINDING_B.md` for the extraction.
- ~~Every named Invested Art referenced in passing... none has a stat block
  here.~~ **RESOLVED for Surgebinding Arts** (*ice shard*, *fireball*,
  *revivify*, *conjure Castweaving*, *Soulcast*, etc. are now stat-blocked in
  the Invested Arts document's Surgebinding section). The same document also
  covers **Allomancy** and **Aonic** Invested Arts (Mistborn/Elantrian
  content) — out of scope for a Roshar-only campaign but present if needed;
  see `COSMERE_ARTS_OTHER_SYSTEMS.md`.
- **Still missing — verified by direct search, not assumed:** Full Shardplate
  item rules (AC formula, HP, cost, and the other 400+ Invested items) —
  explicitly deferred to *Invested Items Collection* (`HB:9007`); only the
  generic don/doff time and no-default-proficiency rule are in the Handbook.
  No file for this book exists under `resources/rules/` or `parsed_data/`.
- **Still missing:** Honorblades, Nightblood, and other named legendary
  Shardblades — deferred to *Hoid's Guide to the Cosmere* (`HB:9064`). No
  file for this book exists under `resources/rules/` or `parsed_data/`.
- **Still missing:** The Bondsmith class in full (surges Tension+Adhesion) —
  deferred to *Hoid's Guide to the Cosmere* (`HB:1631`). Same absence as
  above; the Invested Arts document does **not** add a Bondsmith class or
  fill this gap (it supplies Art *effects* keyed to surges, not new classes).
- **Still missing:** Voidbringer/Fused ability stat blocks — not found
  anywhere in the read ranges of the Handbook, nor in the Invested Arts
  document (which is a spell-effect reference, not a monster manual); only
  their storm-mechanical interactions (Fused Resurrection during an
  Everstorm) are present.

See `COSMERE_SYSTEMS_MAP.md` for the authoritative, currently-maintained
"which book supplies what" table across every Cosmere source in the repo.

### Data-integrity gaps worth a second OCR pass (not missing-document issues — the content likely exists in the source PDF, just didn't survive this conversion)

- **All 10 companion-spren stat blocks** are damaged to varying degrees;
  Mistspren and Peakspren are the worst (rendered as images, near-zero
  numeric stats recovered).
- Cultivationspren's stat block and the Edgedancer's Ideal of Advocation
  Feats text fell in an unread gap (`HB:4229-4321`) — not fabricated, simply
  not yet pulled.
- Several class tables' level-number columns are unreadable as OCR debris
  (Windrunner, Edgedancer, Truthwatcher, Lightweaver, Elsecaller, Willshaper,
  Stoneward) — feature/level pairings were reconstructed from prose
  cross-references, which is reliable, but the raw tables themselves should
  be re-OCR'd for verification.
- A handful of internal source inconsistencies were found and flagged in
  place rather than silently resolved: Windrunner's General-Feat-level
  mismatch (14th vs 16th), Lucentia Form's 50-vs-60-ft range conflict,
  Dustbringer's Releases-column progression anomaly (15→17, skipping 16),
  the Skybreaker/Dustbringer Level-3/Level-7 Ideal-feat header transpositions,
  Stonestance's "Stone Efficiency" unlisted mastery and its Attack Mastery:
  Shattering weapon-type contradiction, and Windstance's "Whirling"/"Swiping"
  name collision.
- Several `'???'` literal placeholders appear in the source where oath quotes
  or feat-tier subtitles should be (Windrunner 18th, Dustbringer 3rd/11th/18th,
  Truthwatcher all 4 tiers, Elsecaller all 4 tiers, Stoneward 6th/10th/14th) —
  these are gaps in the source PDF itself, not conversion artifacts.
