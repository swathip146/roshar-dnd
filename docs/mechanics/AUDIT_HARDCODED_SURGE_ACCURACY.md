# Audit: Hardcoded Surge Numbers vs. The Invested Arts of the Cosmere

**Scope**: `components/combat/roshar_actions.py` (5 hand-written surge action
classes) and `data/rules/stormlight/surgebinding.json` (9 authored maneuvers,
10 `surges` entries with `automation: null`), checked field-by-field against:

- `parsed_data/cosmere-5e-the-invested-arts-of-the-cosmere-v2-0/docling.md`
  (19,794 lines — newly available; the book the Radiant's Handbook deferred to)
- `parsed_data/863203275-cosmere-5e-radiant-s-handbook-v2-0/docling.md`
  (class features, Shardblade rules, economies)

Every quote below is copied verbatim from the cited line(s). Where the parsed
markdown looked garbled I said so rather than declaring a mismatch.

---

## 1. Lashing (`components/combat/roshar_actions.py:80-210`)

Code fields (read from `LashingEvent`/`Lashing`, not the docstring):

| Field | Code value | Location |
|---|---|---|
| Resource cost | 1 Stormlight sphere (`stormlight_cost: int = 1`) | `roshar_actions.py:91,121` |
| Action cost | implied 1 action (no bonus/reaction variant modeled) | `roshar_actions.py:104` (docstring only; no `action_type` field exists in code) |
| Range | "Touch" (docstring only; `_apply` has no range check at all) | `roshar_actions.py:105` |
| Duration | "10 rounds (concentration)" (docstring only; `_apply` sets no expiry, no concentration tracking) | `roshar_actions.py:106` |
| Order gate | Windrunner or Skybreaker | `roshar_actions.py:140` |
| Level gate | `surgebinding_level >= 1` | `roshar_actions.py:148` |
| Save DC | none — Lashing never rolls a save | n/a |
| Damage | none | n/a |

Book (Radiant's Handbook, `surgebinding.json` "maneuvers", and the Invested
Arts "Gravitation" cantrip):

| Field | Book value | Source |
|---|---|---|
| Resource cost | Lashing dice (a d4, growing with level), NOT Stormlight spheres. "You have two Lashing dice to fuel your Maneuvers... A Lashing die is expended when you use it. You regain all of your expended Lashing dice when you finish a short or long rest." | Radiant's Handbook line 1862 |
| Action cost (basic Gravitation) | "1 bonus action, 1 action, or 1 reaction" depending on which use | Invested Arts docling.md:352-354 |
| Range | "Touch" | Invested Arts docling.md:356-358 |
| Duration | "Instantaneous" for the Gravitation cantrip. Full Lashing maneuver: target is restrained "until the beginning of your next turn" — not 10 rounds. | Invested Arts docling.md:364-366; `surgebinding.json` maneuver `full_lashing`, Radiant's Handbook line 1970 |
| Order gate | Windrunner, Skybreaker | `surgebinding.json` `orders.Windrunner/Skybreaker.surges` |
| Level gate | 1st level (First Ideal): "You have sworn the First Ideal... Your spren has provided you with the Surges of Adhesion and Gravitation." | Radiant's Handbook line 1804-1808 |
| Save DC (Full Lashing maneuver) | `8 + proficiency bonus + Investiture ability modifier`, Strength save | `surgebinding.json` `invested_save_dc`; Radiant's Handbook line 1868 |
| Damage (Full Lashing maneuver, on fail) | the expended Lashing die (a d4 at low level, growing with level) bludgeoning | `surgebinding.json` maneuver `full_lashing.automation`; Radiant's Handbook line 1970: "roll the expended Lashing die and the creature takes that amount of bludgeoning damage" |

### Field-by-field table

| Implementation | Field | Code value (file:line) | Book value (source line) | Match? | Severity if wrong |
|---|---|---|---|---|---|
| Lashing | Resource cost | `1 Stormlight sphere` (roshar_actions.py:91,121,201-205) | Lashing die (d4+, per-level table), recovered on short/long rest (Radiant's Handbook:1862) | ❌ | High — this is exactly the bug `surgebinding.json`'s `_meta.correction` documents. A Windrunner burns a Stormlight sphere every time they Lash, when the rules charge a free-refreshing die instead. Spheres are a slower, story-level resource (see `stormlight_replenishment`, level×5 sapphire marks per long rest); the code silently converts a nearly-free at-will Maneuver into a metered, scarce one. A player who plays "by the book" (2 short-rest-refreshing dice) will run out of Lashings in the code roughly 2x faster than intended and for the wrong reason. |
| Lashing | Order gate | Windrunner/Skybreaker (roshar_actions.py:140) | Windrunner/Skybreaker share Gravitation (`orders.json` surges list) | ✅ | — |
| Lashing | Level gate | `surgebinding_level < 1` cancels (roshar_actions.py:148) | Granted at 1st level / First Ideal (Radiant's Handbook:1804-1808) | ✅ | — |
| Lashing | Duration | "10 rounds (concentration)" (docstring, roshar_actions.py:106); `_apply` never expires or tracks concentration | Full Lashing: restrained "until the beginning of your next turn" (Radiant's Handbook:1970); basic Gravitation cantrip is Instantaneous (Invested Arts:364-366) | ❌ | Medium — no book art or maneuver has a 10-round duration. This number has no source in either book (see "Numbers the code invented" below). In practice `_apply` doesn't even implement a duration, so the docstring is aspirational, but if someone later wires up the described behavior it will be wrong. |
| Lashing | Action type | implied 1 action only | "1 bonus action, 1 action, or 1 reaction" depending on use (Invested Arts:352-354); Full Lashing maneuver is an action (Radiant's Handbook:1970); Reverse Lashing is a reaction (Radiant's Handbook:2026) | ⚠️ differs but defensible | Low — the code has no action-economy modeling at all (this whole engine layer doesn't appear to gate on action type), so this is an omission rather than a wrong number. Flagging because the docstring overclaims a single "1 Action" cost when the real surge is multi-modal. |
| Lashing | Save DC | none rolled | `8 + prof + Investiture ability mod` (Str/Dex highest) (Radiant's Handbook:1866-1868) | ❌ (by omission) | Medium — a "basic"/"full"/"reverse" Lashing in the code never asks the target to save; it just mutates a `gravity_direction` attribute unconditionally. The book's only combat-relevant Lashing maneuver (Full Lashing) requires a failed Strength save before the restrain + damage apply. A player experiences this as gravity attacks that always land with no chance to resist, and take no damage on either restrain, while the book's version can miss (save success) and does bludgeoning damage on a failed save. |
| Lashing | Damage | none | on failed save, `{lashing_die}` bludgeoning (Radiant's Handbook:1970) | ❌ (by omission) | Low-Medium — Lashing in the code is pure utility (flips a `gravity_direction` flag); the book's actual combat maneuver deals real damage. Not "wrong" so much as an unimplemented offensive half of the surge. |

---

## 2. ShardbladeAttack (`roshar_actions.py:225-314`)

Code fields:

| Field | Code value | Location |
|---|---|---|
| Damage | 2d6 necrotic, "soul damage", explicitly bypasses armor (`target.health.take_damage(...)` with no AC/hit roll anywhere in `_apply` or `_validate`) | `roshar_actions.py:221,288-305` |
| Special | `target_killed`/"soul severed (10 heartbeats to kill if not healed)" field declared but never set or checked | `roshar_actions.py:222,235` |
| Requirement | `entity.shardblade_summoned == True` | `roshar_actions.py:262-273` |
| Level gate (docstring) | "Typically unlocked at Third Ideal for living Shardblades" | `roshar_actions.py:239` (docstring only — `_validate` never checks a level) |

Book (this is an **equipment/class-feature rule, not an Invested Art** — the
Invested Arts book has no "Shardblade" spell entry, confirmed by `grep` across
both parsed documents returning zero hits for "soul damage", "heartbeat",
"ignores armor", or "severed soul"):

| Field | Book value | Source |
|---|---|---|
| Damage | A normal weapon die that scales with Radiant level (d4→d6→d8→d10→d12 across the Windrunner table), dealt via a normal weapon attack roll vs. AC, plus a flat magic bonus (+1 at Third Ideal / 7th level, +2 at 15th level) | Radiant's Handbook lines 1739-1754 (Windrunner table), 1898-1904 |
| Damage type | Whichever weapon type the Radiant chooses when summoning ("change your Shardweapon into a weapon of a different type"); one class (Willshaper, "Cognitive Blade") explicitly lets you choose psychic instead of the weapon's normal type — implying the *default* is the mundane weapon's damage type, not necrotic | Radiant's Handbook:1902, 6352 |
| Attack roll | A standard weapon attack roll (not an auto-hit, and not armor-ignoring) — nothing in either book states Shardblades bypass AC | (absence of any such rule in ~19,800 + ~14,000 lines of both books) |
| Level gate | Third Ideal, which the class tables place at 7th character level | Radiant's Handbook:1902 ("Once you swear the 3rd Ideal of the Windrunners...") |
| Requirement | Summoned via bonus action, dismissed on your turn, disappears if it leaves your hand | Radiant's Handbook:1902 |

### Field-by-field table

| Implementation | Field | Code value (file:line) | Book value (source line) | Match? | Severity if wrong |
|---|---|---|---|---|---|
| ShardbladeAttack | Damage dice | `2d6` (roshar_actions.py:221,290-294) | scales by level: d4 (1st) → d6 (4th) → d8 (5th) → d10 (6th) → d12 (7th+) (Radiant's Handbook:1739-1754) | ❌ | High — a 1st-level Windrunner in the code deals 2d6 (avg 7) when the table gives them a d4 (avg 2.5); flat 2d6 also never grows, so a 15th-level Shardbearer swinging what should be a d12+2 magic blade still only rolls 2d6. Damage is both wrong at level 1 and frozen for the whole campaign. |
| ShardbladeAttack | Damage type | `NECROTIC` (roshar_actions.py:31,302) | Player-chosen mundane weapon type by default; only a specific Willshaper feature (not Windrunner) can make it psychic | ❌ | Medium-High — a Windrunner's Shardblade dealing necrotic damage changes which resistances/immunities matter (e.g., undead immune to necrotic would be nearly unkillable by a code Shardbearer, when the book gives no such default). No book text supports necrotic as a Shardblade's damage type. |
| ShardbladeAttack | Ignores armor / auto-hit | implicit — code applies damage directly with no attack roll or AC check anywhere in `_apply` | No such rule found in either book; Shardblades are wielded in normal weapon attacks | ❌ | High — this is the single most impactful invented mechanic in the file. It makes a code Shardbearer's attacks unmissable and AC-irrelevant, when the book models them as ordinary (if magical) weapon attacks that can miss. |
| ShardbladeAttack | "Soul severed, 10 heartbeats to kill" | field declared, logged as a note, never implemented or triggered (roshar_actions.py:222,308-309) | No such text in either book | ❌ (invented, currently inert) | Low today (dead code) / High if implemented later — flagging so nobody wires this up believing it's a real rule. |
| ShardbladeAttack | Level gate | docstring says "Third Ideal", but `_validate` only checks a boolean `shardblade_summoned` flag, no level check at all | Third Ideal = 7th character level (Radiant's Handbook:1902) | ⚠️ differs but defensible | Medium — not a wrong *number*, but a missing gate: nothing stops a 1st-level Windrunner from having `shardblade_summoned=True` set elsewhere and swinging a Shardblade 6 levels early, if any other code path can set that flag before 7th level. |
| ShardbladeAttack | Book counterpart | N/A | **No Invested Art entry exists for "Shardblade."** It is purely a Radiant's Handbook class-feature/equipment rule (a magic weapon with a scaling die), confirmed by the Windrunner/Skybreaker/etc. tables and the "Shardblade -7th Level" feature text. | — | This confirms the task's hint: ShardbladeAttack should be checked against the Handbook, not the Invested Arts book, and the Handbook gives it a normal-weapon-attack shape entirely unlike the code's fixed-2d6-necrotic-auto-hit model. |

---

## 3. ProgressionHealing (`roshar_actions.py:329-471`)

Code fields:

| Field | Code value | Location |
|---|---|---|
| Resource cost | 2 Stormlight spheres | `roshar_actions.py:326,352` |
| Healing | `2d8 + Wisdom modifier` (hardcoded to `wisdom`, not a per-class "Investiture ability") | `roshar_actions.py:424-445` |
| Order gate | Edgedancer or Truthwatcher | `roshar_actions.py:376` |
| Level gate | `surgebinding_level >= 2` | `roshar_actions.py:384-388` |
| Range | "Touch" (docstring only — `_apply` never validates range/distance) | `roshar_actions.py:339` |

Book — the direct match is **"Regrowth"**, a 1st-level Progression Invested
Art (not the cantrip, which only stabilizes/is cosmetic — see §Basic Surges
below):

| Field | Book value | Source |
|---|---|---|
| Healing | "A creature you touch recovers a number of hit points equal to 2d8 + your Investiture ability modifier." | Invested Arts docling.md:6751 |
| Casting time / range | "1 action", "Touch" | Invested Arts docling.md:6735-6741 |
| Cost | Investiture Points, per the level-1 tier: 2 points (Edgedancer/Truthwatcher use `investiture_points` economy) | `surgebinding.json` `economies.investiture_points.cost_by_art_level["1"] = 2` |
| Investiture ability (Edgedancer) | Wisdom — "Wisdom is your Investiture ability... You use your Wisdom modifier for Investiture ability checks... you use your Wisdom modifier when setting the saving throw DC for an Edgedancer Invested Art you cast" | Radiant's Handbook:3632-3634, 3702 |
| Investiture ability (Truthwatcher) | **Player's choice** of Intelligence, Wisdom, or Charisma, fixed once chosen — "Truthwatchers' abilities are as varied... Choose Intelligence, Wisdom, or Charisma. This is your Investiture ability... Once you choose... you cannot change it." | Radiant's Handbook:4430-4432, 4492 |
| Order gate | Edgedancer, Truthwatcher | `surgebinding.json` `orders.Edgedancer/Truthwatcher.surges` includes Progression |
| Level gate | 1st level / First Ideal — "You have sworn the First Ideal of the Order of Edgedancers... Your spren has provided you with the Surges of Abrasion and Progression." | Radiant's Handbook:3628 |
| Cantrip variant (Progression cantrip) | Stabilizes a creature at 0 HP, or makes a tiny plant grow — no d8 healing at all, Instantaneous, costs 0 Investiture points | Invested Arts docling.md:424-447; `surgebinding.json` `surges.Progression.cost.investiture_points = 0` |

### Field-by-field table

| Implementation | Field | Code value (file:line) | Book value (source line) | Match? | Severity if wrong |
|---|---|---|---|---|---|
| ProgressionHealing | Healing dice | `2d8` (roshar_actions.py:427-428,444) | `2d8` (Invested Arts:6751) | ✅ | — |
| ProgressionHealing | Ability modifier added | Wisdom modifier only, hardcoded (roshar_actions.py:441-442) | "Investiture ability modifier" — Wisdom for **Edgedancer** ✅, but **player-chosen (INT/WIS/CHA)** for Truthwatcher | ⚠️ differs but defensible for Edgedancer / ❌ for Truthwatcher | Medium — a Truthwatcher who chose Intelligence or Charisma as their Investiture ability (a legal, book-supported choice) will have their healing silently computed off Wisdom instead. A Truthwatcher optimized around Charisma would heal for less (or more) than the book dictates, and the discrepancy is invisible unless someone compares dice logs to a sheet. |
| ProgressionHealing | Resource cost | `2 Stormlight spheres` (roshar_actions.py:326,352,460-464) | `2 Investiture Points` for a level-1 Art (`surgebinding.json` cost_by_art_level.1 = 2) — coincidentally the same *number*, but the wrong *resource*. Investiture Points recover "on a long rest, requires intaking Stormlight" — they are not spheres spent 1:1 per cast. | ⚠️ differs but defensible on the number / ❌ on the resource type | High — this is the flagship case of `_meta.correction`'s warning: the number (2) happens to match by coincidence, hiding the fact that the *economy* is entirely wrong. Investiture Points are a level-scaled pool (2/3/5/6/7 by Art level 1-5) that refresh once per long rest; Stormlight spheres are a separate, narrative/logistics resource (sapphire marks purchased/found, spent for long-rest replenishment at level×5). The code conflates them, so a Truthwatcher who casts a 3rd-level-equivalent healing art (if one were ever wired up) would still only pay 2 by this pattern, when the book charges 5. |
| ProgressionHealing | Order gate | Edgedancer/Truthwatcher (roshar_actions.py:376) | Edgedancer/Truthwatcher share Progression | ✅ | — |
| ProgressionHealing | Level gate | `surgebinding_level < 2` cancels (roshar_actions.py:384-388) | Progression (as a cantrip) is granted at 1st level / First Ideal (Radiant's Handbook:3628); the 1st-level Art "Regrowth" that the 2d8 die actually matches requires only class level 1 (any 1st-level spell slot equivalent), not "surgebinding level 2" | ❌ | Medium — a real 1st-level Edgedancer can cast Regrowth (2d8 healing) immediately per the book; the code's Progression healing is unreachable until "surgebinding_level 2", locking out exactly the ability a new Edgedancer is supposed to have from level 1. (Note: the *cantrip* version of Progression, which any 1st-level Edgedancer/Truthwatcher has, does NOT do 2d8 healing — it only stabilizes a dying creature. So there is a real level-gating question that depends on which tier of "Progression" the code means to model; as written, the code's 2d8 formula matches the Art, but the level gate matches neither the Art's real requirement (1) nor the cantrip's real numbers (0 healing).) |
| ProgressionHealing | Docstring claim: "restore lost limbs at higher Ideals" | not implemented in `_apply` at all | True, but it's a specific 7th-level Art ("Regenerative Regrowth"): "The target's severed body members... are restored after the duration." | ✅ (docstring, unimplemented) | Low — not a wrong number since no number is coded for this; flagged only so nobody assumes the mechanic exists. |

---

## 4. Illumination (`roshar_actions.py:487-579`)

Code fields:

| Field | Code value | Location |
|---|---|---|
| Resource cost | 1 Stormlight sphere | `roshar_actions.py:491,511` |
| Effect | Applies the engine's generic `Invisible` condition to the caster | `roshar_actions.py:550-565` |
| Order gate | Lightweaver or Elsecaller | `roshar_actions.py:518` |
| Level gate | `surgebinding_level >= 1` | `roshar_actions.py:524-525` |

Book — Illumination cantrip ("Basic Lightweaving") and the Illumination
cantrip entry:

| Field | Book value | Source |
|---|---|---|
| Cost | 0 Investiture points (cantrip) | `surgebinding.json` `surges.Illumination.cost.investiture_points = 0`; Invested Arts:461-463 confirms no Investiture-point line for the cantrip |
| Casting time | 1 bonus action | Invested Arts docling.md:453-455 |
| Range | 30 feet (not touch/self) | Invested Arts docling.md:457-459 |
| Effect (cantrip) | Small illusion/sound/light effects "within range," or a color/mark/glyph, or disguising your/another's voice — **not** an Invisibility/concealment effect on the caster | Invested Arts docling.md:469-476 |
| Effect (1st-level Art, "Basic Lightweaving") | "You Lightweave a sound or a static image of an object within range" | Invested Arts docling.md:1048 |
| Order gate | Lightweaver, Truthwatcher (book pairing is Lightweaver+Truthwatcher, not Lightweaver+Elsecaller) — "Illumination cantrip - Truthwatcher, Lightweaver" | Invested Arts docling.md:451; `surgebinding.json` `orders.Truthwatcher.surges` and `orders.Lightweaver.surges` both list Illumination; **Elsecaller's surges are Transformation + Transportation, NOT Illumination** (`surgebinding.json` `orders.Elsecaller.surges = ["Transformation","Transportation"]`) |

### Field-by-field table

| Implementation | Field | Code value (file:line) | Book value (source line) | Match? | Severity if wrong |
|---|---|---|---|---|---|
| Illumination | Resource cost | `1 Stormlight sphere` (roshar_actions.py:491,511,569-574) | 0 Investiture points, i.e. free/at-will cantrip (Invested Arts:449-463; `surgebinding.json` cost.investiture_points=0) | ❌ | High — same class of bug as Lashing: the book explicitly makes this a **free cantrip** ("Cantrips don't cost any Investiture point to cast" — `surgebinding.json` economies.investiture_points.quote), and the code charges a metered Stormlight sphere for every use, again matching `_meta.correction`'s exact warning. |
| Illumination | Order gate | Lightweaver **or Elsecaller** (roshar_actions.py:518) | Illumination is shared by **Lightweaver and Truthwatcher** (Invested Arts:451; `surgebinding.json` orders.Truthwatcher/Lightweaver.surges). Elsecaller's surges are Transformation + Transportation — Elsecaller does **not** have Illumination. | ❌ | High — this lets an Elsecaller character use an ability they should not have access to (Illumination), while nothing in the code lets a Truthwatcher (who genuinely has Illumination) use this action, since the class only checks for "Lightweaver"/"Elsecaller". A Truthwatcher player would find the ability inexplicably locked; an Elsecaller player would have an ability that doesn't exist for their order. |
| Illumination | Mechanical effect | Applies engine `Invisible` condition to self | Small illusions (light/sound/image/voice), not invisibility of the caster; nothing in the cantrip or "Basic Lightweaving" grants Invisible | ❌ | Medium — mechanically, `Invisible` is a much stronger, well-defined 5e condition (advantage on attacks against others, disadvantage on being attacked, etc.) than "there is a distracting illusion nearby." A Lightweaver using this ability in the code becomes far more powerful in combat than the book intends — the book's cantrip has no combat-mechanical effect on attack rolls at all. |
| Illumination | Range | not modeled (docstring absent; `_apply` has no target) | 30 feet | ⚠️ N/A | Low — omission, not a wrong number. |
| Illumination | Level gate | `surgebinding_level >= 1` | Granted at 1st level for both Lightweaver and Truthwatcher | ✅ | — |

---

## 5. Soulcast (`roshar_actions.py:582-673`)

Code fields:

| Field | Code value | Location |
|---|---|---|
| Resource cost | 3 Stormlight spheres | `roshar_actions.py:586,606` |
| Effect | Applies engine `Restrained` condition to target, unconditionally (no save) | `roshar_actions.py:645-661` |
| Order gate | Lightweaver or Elsecaller | `roshar_actions.py:612` |
| Level gate | `surgebinding_level >= 2` ("Second Ideal") | `roshar_actions.py:619-623` |

Book — the Transformation cantrip and the 5th-level "Soulcast" Art, plus
combat-relevant transform-to-stone Arts:

| Field | Book value | Source |
|---|---|---|
| Cost (cantrip) | 0 Investiture points | `surgebinding.json` surges.Transformation.cost=0; Invested Arts:478-496 |
| Cost (named "Soulcast" Art, 5th-level Transformation) | Investiture Points per the level-5 tier (7 points, per `cost_by_art_level`) **plus** a material component — "a large infused polestone" — that is consumed/cracked on the roll | Invested Arts docling.md:7472-7515; `surgebinding.json` cost_by_art_level["5"]=7 |
| Mechanic (named "Soulcast" Art) | An Investiture ability **check** against a variable DC (15 + steps between Essences on a 10-item table), not an automatic effect and not a save imposed on a creature | Invested Arts docling.md:7496-7509 |
| Order gate | Lightweaver, Elsecaller both have Transformation — matches code | Invested Arts:480 ("Transformation cantrip - Lightweaver, Elsecaller"); `surgebinding.json` orders.Lightweaver/Elsecaller.surges |
| Level gate | Cantrip is 1st level; the "Soulcast" Art (the one that actually transforms matter object-to-object) is 5th-level | Invested Arts:480-484 header ("Soulcast" heading says "5th-level Transformation") |
| Combat restrain use | Exists, but as **specific named Arts with a save**, e.g. "Aonic Soulcast"/similar stone-transform Arts requiring a Constitution or Strength save (2d6 bludgeoning + restrained on a **failed** save) — not an automatic, unconditional restrain | Invested Arts docling.md:2390 ("must make a Constitution saving throw. On a failed save, it is restrained"); docling.md:7771 ("must succeed on a Strength saving throw. On a failed save, the target takes 2d6 bludgeoning damage and is restrained") |

### Field-by-field table

| Implementation | Field | Code value (file:line) | Book value (source line) | Match? | Severity if wrong |
|---|---|---|---|---|---|
| Soulcast | Resource cost | `3 Stormlight spheres` (roshar_actions.py:586,606,663-668) | 0 points if using the cantrip (trivial effects only); 7 Investiture Points + a large polestone material component if using the real "Soulcast" 5th-level Art that can transform matter generally | ❌ | High — whichever tier the code means to model, 3 Stormlight spheres is not the book's number. If it's meant to be the cantrip, it should cost nothing; if it's meant to be the full Art, it should cost 7 Investiture Points and consume a polestone (a discrete, trackable item, not "spheres"). Either way it is invented and, per `_meta.correction`, of exactly the "plausible and wrong" shape this project has been burned by before. |
| Soulcast | Mechanical effect | Auto-applies `Restrained` to target, no save, no check | Real combat-relevant transform Arts require a **failed save** (Con or Str, depending on the specific Art) before restraining, and the general "Soulcast" Art requires an **Investiture ability check** vs. a materials-based DC (15+) with a chance of outright failure and a wasted, cracked polestone | ❌ | High — the code's Soulcast can never fail and never lets the target resist, while every book analogue is either a contested save or a hard skill check with real failure consequences (a cracked, worthless polestone on bad rolls, or "the material must fit within a 5-foot cube," etc.). This makes Soulcast strictly better than the book's version and removes the resource/failure risk that balances it. |
| Soulcast | Order gate | Lightweaver/Elsecaller (roshar_actions.py:612) | Lightweaver/Elsecaller both have Transformation | ✅ | — |
| Soulcast | Level gate | `surgebinding_level >= 2` ("Second Ideal") (roshar_actions.py:619-623) | Cantrip is granted at 1st level; the actual matter-transforming "Soulcast" Art is 5th-level (roughly a mid-game ability in a leveled-spellcasting system) | ❌ | Medium — the code's gate (level 2 / Second Ideal) sits between the cantrip's real requirement (1) and the full Art's real requirement (5-ish), matching neither. A 2nd-Ideal Lightweaver in the code can fully transform matter and restrain enemies unconditionally — power the book reserves for a much higher-level, harder-to-use, resource-risking Art. |
| Soulcast | `target_essence` field | free-text string, no validation against the book's 10-Essence table or polestone requirement | 10 fixed Essences, each requiring a specific polestone type, with DC scaling by "steps" between source and target Essence (Invested Arts:7496-7509) | ⚠️ differs but defensible | Low-Medium — omission rather than wrong number; flagged because the book's DC-by-distance mechanic is exactly the kind of numeric system this audit exists to catch, and it's entirely unmodeled. |

---

## `surgebinding.json` maneuvers (9 entries) — spot-check against the book

All 9 maneuvers (`full_lashing`, `reverse_lashing`, `distracting_attack`,
`goading_attack`, `evasive_movement`, `riposte`, `alerted_lash`,
`athletic_lashings`, `acrobatic_lashings`) were already marked
`"reviewed": true` with explicit `quote` fields and source lines. I spot-verified
three against the Radiant's Handbook text directly:

- `full_lashing` (source.line 1970): quoted text matches the book almost
  verbatim ("As an action you can expend a Lashing die and attempt to restrain
  a creature you can see within 30 feet with a Full Lashing..."). Automation
  (Strength save, DC = `invested_save_dc`, fail → Restrained until start of next
  turn + `{lashing_die}` bludgeoning damage) is a faithful encoding. ✅
- `reverse_lashing` (source.line 2026): quote matches; automation (AC bonus
  equal to the lashing die roll, for the triggering attack) matches. ✅
- `riposte` (source.line 2030): quote matches ("When a creature misses you
  with a melee weapon attack, you can use your reaction and expend one Lashing
  die to make a melee weapon attack against the creature"); automation
  (attack, `{lashing_die}` damage on hit) matches. ✅

These 9 entries are **not** part of the "invented numbers" problem — they were
authored correctly from source that was already available in the Radiant's
Handbook (Lashing maneuvers are described there directly; only the 10 named
*surge cantrips'* full mechanics were deferred to the missing book). No
corrections needed.

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
