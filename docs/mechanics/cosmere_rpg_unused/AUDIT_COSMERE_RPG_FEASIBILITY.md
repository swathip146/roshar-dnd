# Audit: Can This 5e Engine Host the Standalone Cosmere RPG?

**Date**: 2026-09-12
**Branch**: `phase-0-fixes`
**Method**: every row was verified by running real code (`uv run python ...`, `uv run
pytest ...`) or grepping production call sites — not by reading docstrings. Where a
docstring's claim and live behavior disagreed, live behavior wins.

**Framing.** This is *not* the same audit as `AUDIT_CHARACTER_AND_NONCOMBAT.md`. That
audit asked "is 5e mechanic X implemented and reachable" inside a 5e engine. This audit
asks a harder question: the user's newly-added rulebooks (Stormlight Starter Rules,
sl019 pregens) are the **standalone Cosmere RPG** (Brotherwise Games) — a system with
zero occurrences of "Armor Class," "saving throw," "proficiency bonus," "spell slot," or
"hit dice." It uses a plot die (Opportunities/Complications), three attribute categories
(Physical/Cognitive/Spiritual), six attributes (Strength/Speed/Intellect/Willpower/
Awareness/Presence), Defenses = `10 + two attributes`, Deflect, grazing, Focus and
Investiture pools, Expertises, injury rolls, and a Recovery Die. Meanwhile this codebase
vendors `external/dnd_engine` (2014 5e), 1,321 entries of 2014 SRD JSON, computes
AC/saving-throws/proficiency/spell-slots, and wraps a 5e `Attack` action. The question is
which parts of the existing 5e machinery could serve the Cosmere RPG, which are useless
for it, and which Cosmere RPG mechanics have no home at all.

**Central distinction applied throughout** (same as the template):
- **Implemented** = the code exists and does the right thing when exercised directly.
- **Reachable** = a player in a real session can trigger it.

Legend: ✅ reusable as-is / 🟡 reusable with work / ❌ nothing exists.

---

## 1. Dice / resolution

| Cosmere RPG mechanic | Existing 5e capability | Reusable? | Evidence | What's needed |
|---|---|---|---|---|
| Numeric dice (2d6+mod, etc. — Cosmere RPG's core roll is 2d20-take-higher-plus-lower-as-complication-tracker... actually the core roll is d20-based: roll 1d20, add attribute+skill, vs. a target number) | `components/dice.py` `DiceRoller`, backed by the `d20` library | ✅ | `components/dice.py:60-142` `skill_roll()`; live: `d20.roll('1d6').total` → works; `d20.roll` grammar supports `NdM`, `kh/kl/ph/pl`, exploding (`e`), reroll (`ro/rr`), `mi/ma`, parentheses, `+/-` constants — see docstring at `dice.py:170-182` | The numeric plumbing (roll N dice, sum, add modifier, compare to target) is fully reusable |
| **Plot die** (a d6 with faces: 2 blank, 2 Opportunity, 2 Complication — rolled alongside the action die on every check) | Nothing | ❌ | `grep -rln "plot_die\|Opportunity\|Complication" components/ agents/ core/ orchestrator/` → the only hits are false positives: `core/game_initialization.py:885,903` ("Opportunity lost" narrative flavor text, "Opportunity: {story hook}"), and `components/combat/standard_actions.py:496` (5e "opportunity attacks", an unrelated mechanic). Zero real hits. | A plot die is a symbolic-face concept the `d20` library cannot express (it is a pure numeric dice grammar — confirmed: `d20.roll` only parses `NdM`-style expressions, there is no face-labeling). Needs a small bespoke roller: `random.choice(["blank","blank","opportunity","opportunity","complication","complication"])`, or a `d6` mapped through a face table. Trivial to build, but does not exist and nothing in `DiceRoller` anticipates it |
| Non-numeric / symbolic die faces (generic capability) | None | ❌ | Confirmed above — `d20`'s `roll()` signature (`expr, stringifier, allow_comments, advantage`) and grammar are entirely numeric; `DiceRoll`/`SkillRollResult` dataclasses (`dice.py:27-43`) store `result: int` and `die_type: int` — no slot for a symbolic outcome | A new `SymbolicDie`/`PlotDieResult` type (or extending `DiceRoll` with an optional `face_label: Optional[str]`) is needed before Opportunities/Complications can be logged the way the rest of the audit trail works |
| Target-number resolution (vs. DC) | `game_engine.py` 7-step skill pipeline (`process_skill_check`), `PolicyEngine` DC scaling | 🟡 | `AUDIT_CHARACTER_AND_NONCOMBAT.md` §5: `roll_skill_check(skill='athletics', dc=12, ...)` live-verified working | The "roll d20 + two-attribute-sum vs. target number" shape is close to 5e's "d20 + mod vs. DC" shape structurally, but the modifier composition (see §2) is wrong for Cosmere RPG without rework |

---

## 2. Attributes

| Cosmere RPG mechanic | Existing 5e capability | Reusable? | Evidence | What's needed |
|---|---|---|---|---|
| Six attributes: Strength, Speed, Intellect, Willpower, Awareness, Presence, in three categories (Physical: Str/Spd; Cognitive: Int/Wil... actually Cognitive: Int/Awa; Spiritual: Wil/Pre — per the Starter Rules) | `CharacterData.ability_scores: Dict[str, int]` — untyped, so it *accepts* arbitrary string keys | 🟡 field / ❌ everywhere else | Live-tested: `CharacterData(ability_scores={'strength':3,'speed':2,'intellect':1,'willpower':3,'awareness':2,'presence':1}, ...)` constructs without error, because the dataclass field is `Dict[str, int]`, not an enum-keyed structure | The *field* is a free dict and accepts anything. But `_calculate_ability_modifier` (`character_manager.py:677-679`) hardcodes 5e's `(score-10)//2`, and `self.skill_abilities` (`character_manager.py:196-213`) hardcodes an 18-entry dict mapping only 5e skill names to `AbilityScore` enum values. Both must change, not just the field |
| Attribute values ARE the check bonus (Cosmere RPG attributes run roughly 0-5, and the raw score is the dice-pool/bonus size — no "modifier" derivation step) | `_calculate_ability_modifier(score) -> (score-10)//2` | ❌ | Live-tested: constructed the Alethi Duelist (STR 3) through `CharacterManager.add_character()`; `ability_modifiers` came back `{'strength': -4, ...}` for a raw score of 3 — the 5e formula assumes scores in the 3-20 range where 10 is average, but Cosmere RPG's "3" *is* the intended bonus (rank 3 in a 6-attribute-max system), not "3 out of 20" | The whole ability-modifier derivation step must be bypassed or replaced for Cosmere RPG characters: the raw attribute value *is* the number used in a check, no `(x-10)//2` |
| `AbilityConfig`/`Ability` block in the vendored 5e engine | `external/dnd_engine/dnd/blocks/abilities.py:18` | ❌ | `abilities = Literal['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma']` — a hardcoded `typing.Literal`, not an enum a caller can extend, and not something `mypy`/pydantic will accept a 7th value for | Structurally locked. The vendored engine's ability system cannot represent Speed, Willpower, Awareness, or Presence without editing vendored code (against the "don't fork/patch the vendored engine" grain of the project's own architecture) |
| Overlap between the two attribute sets | — | 🟡 | Direct comparison: 5e {STR, DEX, CON, INT, WIS, CHA} vs. Cosmere RPG {Strength, Speed, Intellect, Willpower, Awareness, Presence}. Strength is a literal 1:1 name match; Intellect≈Intelligence is a near-miss; nothing else lines up (Speed has no 5e analog — it fuses DEX-agility and reflexes; Willpower is closer to a WIS/CHA hybrid depending on the Starter Rules text; Awareness≈WIS's perception half; Presence≈CHA) | Roughly 1 of 6 clean matches. A mechanical remap table (not a rename) would be needed, and even then the derivation formula (see row above) breaks it |
| Skill list and skill→attribute mapping (Cosmere RPG's ~19 skills: Agility, Athletics, Heavy Weaponry, Light Weaponry, Stealth, Thievery, Crafting, Deduction, Discipline, Intimidation, Lore, Medicine, Deception, Insight, Leadership, Perception, Persuasion, Survival, + specialty blank) | `self.skill_abilities` dict, 18 5e skill names → `AbilityScore` enum | ❌ | Live-tested: `get_skill_data(char_id, 'heavy_weaponry')` → the dict has no `heavy_weaponry` key, `.get()` silently falls back to `AbilityScore.INTELLIGENCE` (the hardcoded default), returning `ability_modifier: 0, ability: 'intelligence'` — semantically wrong (Cosmere RPG's Heavy Weaponry uses Strength) and silent, no error. Separately, `get_skill_data(char_id, 'athletics')` — a name that happens to exist in **both** systems — returned `ability_modifier: -4` because it ran the 5e derivation formula against the raw Cosmere score of 3 | Every one of the ~19 Cosmere RPG skills needs its own mapping entry, and skills that share a name with a 5e skill (Athletics, Perception, Deception, Insight, Persuasion, Survival, Intimidation) will silently produce a *plausible-looking, wrong* number instead of an error, because the name collision routes through the existing 5e-shaped code path undetected |

---

## 3. Defenses vs. Armor Class

| Cosmere RPG mechanic | Existing 5e capability | Reusable? | Evidence | What's needed |
|---|---|---|---|---|
| Three Defenses (Physical, Cognitive, Spiritual), each = `10 + the two attributes in that category` | `armor_class: int` field, `unarmored_ac` | ❌ | `character_manager.py:54` `armor_class: int` — a single scalar, not three; `components/dnd_engine_wrapper.py:753-754`: `EquipmentConfig(unarmored_ac=character.armor_class)` — copies a pre-baked static number in at entity-sync time. Exhaustive grep for `Armor(`/`equip_armor` in the wrapper: **zero hits** (per `AUDIT_CHARACTER_AND_NONCOMBAT.md` §11) | Nothing about `armor_class` is parameterized by attributes — it's authored once per character and never recalculated. Cosmere RPG's `10 + attr + attr` formula would need three brand-new scalar fields (or a `Dict[str,int]` keyed `physical/cognitive/spiritual`) computed fresh from the (also-nonexistent, see §2) Cosmere attribute set, not a rename of `armor_class` |
| Is the AC path parameterizable? | `EquipmentConfig(unarmored_ac=...)` | ❌ hardcoded | Confirmed: `armor_class` is a single int copied verbatim into a single `unarmored_ac` slot; there is exactly one "defense number" in the entire data model, not three, and it is never derived from attributes at all (5e or Cosmere) — it is set once at character creation and static thereafter | A parallel, entirely new computation path is required — not a parameter tweak to the existing one |

---

## 4. Deflect / grazing

| Cosmere RPG mechanic | Existing 5e capability | Reusable? | Evidence | What's needed |
|---|---|---|---|---|
| Deflect (flat damage reduction from armor/talents, subtracted from incoming physical damage) | `health.damage_reduction` (vendored engine), `ResistanceModifier`/`ResistanceStatus` | 🟡 | `external/dnd_engine/dnd/blocks/health.py:474` `damage_reduction.self_static.add_value_modifier(...)` — a genuine flat-number damage-reduction slot exists; also used by `components/combat/class_features.py:621` (Rage's resistance) | Structurally the closest match in the whole audit: a numeric damage-reduction pool that isn't tied to AC/hit-or-miss already exists and is exercised in production (Rage). Reusable as the *storage/arithmetic* mechanism; the trigger conditions (Deflect only applies before an injury roll, is reduced by certain effects, doesn't apply to grazes) would need new logic layered on top |
| ResistanceStatus (RESISTANCE/VULNERABILITY/IMMUNITY = damage multipliers, keyed per damage type) | `external/dnd_engine/dnd/core/modifiers.py:26 class ResistanceStatus` | 🟡 | Confirmed enum exists and is wired (`health.py:476-480`) | This is a *different* mechanic from Deflect (multiplier vs. flat subtraction) but the plumbing pattern (a modifier list on `damage_reduction`) generalizes to both |
| **Grazing** — a specific 5e-absent concept: an attack that misses the target number by a small margin (or that beats the target's Deflect) still deals *reduced* damage, structurally distinct from "half damage on a successful save" | Nothing | ❌ | `grep -rni "grazing\|graze\|partial hit"` across `components/`, `agents/`, `core/` → zero hits. The nearest existing concept, `spell_compiler.py:61` (`"half" -> a successful save takes half damage`), is 5e's save-for-half, which triggers off a *save*, not off an *attack roll falling short of a threshold* — a different trigger entirely | A wholly new outcome branch is needed in the attack-resolution path: currently every attack resolves to exactly hit-or-miss (confirmed by reading the resolver's binary branching in `combat_action_resolver.py`/`maneuver_executor.py`); grazing needs a third outcome band |
| Partial/graze outcome between hit and miss (general capability) | None | ❌ | Same finding as above — 5e's binary hit/miss model has no partial-success concept anywhere in the resolver | New resolution branch required from scratch |

---

## 5. Focus / Investiture pools

| Cosmere RPG mechanic | Existing 5e capability | Reusable? | Evidence | What's needed |
|---|---|---|---|---|
| Focus pool (spent to activate Talents/stances/reactions, refills on rest) | `LashingDicePool` (`components/combat/lashing_dice.py`) | 🟡 | `lashing_dice.py:34-49` `LashingDice` dataclass: `total`, `size`, `remaining`, `spend(count)`, `restore()` — a pool with spend/restore semantics already exists and is exercised by 9 authored Surgebinding maneuvers (`data/rules/stormlight/surgebinding.json`) | Structurally almost exactly what Focus needs (a small integer pool, decremented on use, restored on rest) — but it is a **dice pool** (rolls a d4 per spend, per the Surgebinding-specific mechanic), whereas Cosmere RPG's Focus is a **flat point pool** (spend N points, no roll). The `spend`/`restore` API generalizes; the "rolls a die when spent" behavior does not apply and would need to be split out |
| Investiture pool (separate resource for Invested abilities/Surges, distinct from Focus) | `stormlight_current`/`stormlight_capacity` on `CharacterData` | 🟡 | `character_manager.py:68-69`; live-verified accounting: capacity set to `level * 2` (`:759`), spent via `spend_stormlight` tool, restored on long rest (`:984-985`) | This is the closest 1:1 conceptual match in the entire audit — a capacity/current integer pair, restored on rest, spent via an `@tool`. However it's *Roshar-specific* Stormlight-as-spheres economy (narrative fluff: "spheres held"), not generic Investiture-the-resource; reusable as the **pattern**, and arguably renameable, but the Radiant-order-gating logic (`radiant_order`) around it is Cosmere-5e-Handbook-specific, not standalone-Cosmere-RPG shaped |
| Spell slots (5e resource, for comparison) | `spell_slots: Dict[int, Dict[str,int]]`, `SlotTable` in `spellcasting.py` | ❌ not applicable | Confirmed real and tested (`AUDIT_CHARACTER_AND_NONCOMBAT.md` §4: 64/72 tests pass) but keyed by 5e *spell level* (1st-9th), a concept Cosmere RPG doesn't have | Not reusable for Focus/Investiture — different shape (leveled slots vs. flat pools) |
| **Recommendation for reuse** | — | 🟡 | — | `LashingDice`'s spend/restore skeleton (strip the "rolls a die" part) plus `stormlight_current/capacity`'s capacity-tracking pattern are the two best starting points; neither is a drop-in, both need the Surgebinding/Roshar-specific coupling removed |

---

## 6. Expertises

| Cosmere RPG mechanic | Existing 5e capability | Reusable? | Evidence | What's needed |
|---|---|---|---|---|
| Expertise (a specific, narrow tag — e.g. "Greatswords," "Alethi Culture" — that grants a flat bonus or unlocks narrative options when it applies; distinct from a skill rank) | `expertise_skills: List[str]` = 5e's "double proficiency bonus on this skill" | ❌ | `character_manager.py:48,566` — confirmed wired: `if expertise: skill_modifier += character.proficiency_bonus * 2` (`:571-572`) | Conceptually different mechanics sharing a name. 5e Expertise is "this skill's proficiency bonus, doubled." Cosmere RPG Expertise is a *separate tag* layered onto a skill (e.g. the Alethi Duelist's sheet shows "[Weapon] Greatsword" and "[Cultural] Alethi, Veden" as Expertises distinct from the skill-rank list) that doesn't scale with proficiency bonus at all — it's binary has/doesn't-have, tied to a narrow trigger the GM adjudicates narratively as much as mechanically |
| Data model impact | `expertise_skills: List[str]` (flat list of skill names only) | ❌ | Same field | Cosmere RPG Expertises are typed (`[Cultural]`, `[Weapon]`, etc.) and free-text-scoped (a specific weapon, a specific culture) — the existing field can't represent "Expertise: Greatsword" as distinct from "Expertise: Perception," because it isn't a skill-name list, it needs its own tagged list |

---

## 7. Injuries and conditions

| Cosmere RPG mechanic | Existing 5e capability | Reusable? | Evidence | What's needed |
|---|---|---|---|---|
| 5e's 15 conditions (Blinded, Charmed, ..., Unconscious) | `external/dnd_engine/dnd/conditions.py` | ✅ (for 5e only) | `grep -n "^class .*Condition"` → 15 classes confirmed: Blinded, Charmed, Dashing, Deafened, Dodging, Frightened, Grappled, Incapacitated, Invisible, Paralyzed, Poisoned, Prone, Stunned, Restrained, Unconscious | Fully built for 5e, but these are 5e's specific condition semantics (e.g. Grappled sets speed 0, tied to a 5e-shaped grapple mechanic) |
| `components/engine_conditions.py` (only 2 conditions actually implemented, per the template audit) | `Petrified`, `Exhaustion` | 🟡 | `engine_conditions.py:115,232` — confirmed only these two exist here, the rest of the 15 live in the vendored `dnd/conditions.py` above | Same caveat as above |
| **Injury roll table** — Cosmere RPG's core "you took a solid hit" resolution: roll on an injury table (e.g. broken bone, gruesome wound) instead of, or in addition to, HP loss, with lasting mechanical effects until healed | Nothing | ❌ | No injury table, injury roll, or wound-severity concept found anywhere in `components/` or `data/rules/` | Entirely new subsystem: a table (data file), a roll trigger (attacks tagged "Deadly," per the Alethi Duelist's Greatsword: "Deadly: on a hit, cause an injury"), and a lasting-effect application path onto the character |
| Cosmere RPG's own condition list (Cosmere RPG has its own smaller condition set — distinct names/effects from 5e's 15, e.g. its own Slowed/Enraged/etc. drawn from the Starter Rules) | The 15 5e conditions above | ❌ overlap | The Alethi Duelist's armor text references "Slowed" (`Chain armor... makes you Slowed and gives you a disadvantage on all Speed tests`) — "Slowed" is not one of the 15 5e conditions implemented; a full Cosmere RPG condition list was not located in this codebase's `data/rules/` at all | Cosmere RPG's condition set needs to be authored from scratch as data + effects; it does not map onto the 5e 15 in any but a coincidental few (e.g. both systems probably have some form of Prone) |

---

## 8. Combat loop

| Cosmere RPG mechanic | Existing 5e capability | Reusable? | Evidence | What's needed |
|---|---|---|---|---|
| Turn order / initiative | `combat_initializer.py:949 _roll_initiative()` | ❌ hardcoded 5e | `combat_initializer.py:982,991`: `initiative = self._roll_d20() + dex_mod` — literally "d20 + DEX modifier," 5e's exact formula, with DEX hardcoded by name | Cosmere RPG's initiative (if attribute-based at all — the Starter Rules text wasn't independently reviewed in this pass, but it is not DEX-based since DEX doesn't exist) needs its own formula; the `_roll_initiative` function's core line must change, not just its inputs |
| Turn structure (whose turn, advancing) | `combat_session_manager.py:1590-1629` | ✅ | `combat_state["initiative_order"]`, `combat_state["current_turn_index"]` — a generic "list of combatants, advance an index" loop with no 5e-specific logic in the advance step itself | The turn-advancing *mechanism* (an ordered list + index) is system-agnostic and reusable as-is |
| Action economy (Action / Bonus Action / Reaction / Movement) | `external/dnd_engine/dnd/blocks/action_economy.py:15-23` `ActionEconomyConfig`: `actions: int = 1`, `bonus_actions: int = 1`, `reactions: int = 1` | 🟡 | Confirmed hardcoded 5e categories; `action_registry.py`'s only two `cost_type` values across every entry are `"actions"` and `"movement"` (`grep "cost_type"` → exactly those two strings) | Cosmere RPG's economy is simpler (one Action per turn, plus Reactions gated by spending Focus, no separate Bonus Action category) — closer to a subset of the 5e model than an incompatible one. The container (`ActionEconomy` block, an int-counter-per-category pattern) is reusable; the specific categories (`bonus_actions`) don't map and would sit unused, while Focus-gated reactions need new logic since 5e reactions aren't resource-gated the same way |
| `ACTION_REGISTRY` / `is_offerable()` menu-filtering mechanism | `components/combat/action_registry.py` | ✅ | Generic dict-of-dicts keyed by action name, with `requires`/`cost_type`/`param_defaults` — nothing in the *mechanism* (register an action, check its cost, check its params, filter into a menu) assumes 5e; only the *entries themselves* (Attack, cast_spell, Surges) are 5e/Roshar-5e-shaped | The filtering architecture (register → offerability check → present to player/NPC) is system-agnostic and could host Cosmere RPG actions (Skill actions like Bash, Grab; Reactions like Dodge, Reactive Strike) with new entries, reusing the same `is_offerable`/`required_caller_params` functions |
| Attack resolution (roll vs. AC, binary hit/miss, then damage) | `Attack` action wrapping the vendored engine | ❌ | Per §4, resolution is strictly binary; Cosmere RPG's is roll vs. Defense, with three outcomes (miss, graze-on-a-beat-Deflect-but-not-Defense-style-margin, hit) per its own resolution rule, plus the plot die's Complication/Opportunity layered on every roll | The resolver's hit/miss branch point needs a third branch, and the roll itself needs the plot die bolted on — not a small patch |

---

## 9. Recovery Die / rests

| Cosmere RPG mechanic | Existing 5e capability | Reusable? | Evidence | What's needed |
|---|---|---|---|---|
| Recovery Die (a die size — e.g. the Alethi Duelist's sheet shows `1d8` — rolled to heal HP during a rest, similar in *shape* to 5e's Hit Die) | `hit_dice_remaining`, `short_rest`/`long_rest` in `character_manager.py`, `take_rest` `@tool` in `agents/dm_tools.py:607` | 🟡 | `AUDIT_CHARACTER_AND_NONCOMBAT.md` §6: live-tested, 15/15 rest tests pass; short rest "spends hit dice for healing," long rest recovers half | Structurally very close: both are "roll a class/character-specific die to heal HP, limited uses, recovered on rest." The `hit_dice_remaining` counter and the rest-triggering `@tool` plumbing are reusable; the die *size* is currently derived from 5e class (`_hit_die_for_class`, e.g. d10 for Fighter) rather than being a directly-authored per-character field the way Cosmere RPG's Recovery Die is (`1d8` printed directly on the sheet, not derived from a class table) |
| Rest cadence (short/long) | Same `take_rest` tool, `kind: "long"/"short"` | ✅ mechanism / ❓ semantics | Confirmed reachable via `@tool`, iterates the whole party by default | Cosmere RPG's rest structure (the Starter Rules' short/long rest equivalents were not independently verified against the parsed text in this pass) would need its exact HP/Focus/Investiture recovery amounts re-authored, but the *plumbing* (a tool that iterates characters and calls recovery methods) is reusable |

---

## 10. Character sheet fidelity — concrete test with a real pregen

**Sheet used**: `parsed_data/sl019-warrior-alethi-duelist/docling.md` — a level-1 (with a
level-2 upgrade block) Human Warrior (Shardbearer), the "Alethi Duelist," one of the 20
sl019 pregens. Extracted stat block (OCR'd from the docling conversion, cross-checked
against the two duplicate copies on the same page):

```
Ancestry: Human          Path: Warrior (Shardbearer)      Level: 1 (→2 block included)
Attributes: Strength 3, Speed 2, Intellect 1, Willpower 3, Awareness 2, Presence 1
Defenses: Physical 13, Cognitive 14, Spiritual (value ran together with layout in OCR)
Health: 15 max            Focus: 2 max            Investiture: 5 max
Deflect: 2 (from Chain armor)      Recovery Die: 1d8
Movement: 25 ft.          Senses range: 10 ft.
Skills: Agility 2, Athletics 5, Heavy Weaponry 5, Light Weaponry 2, Stealth 2,
        Thievery 2, Crafting 1, Deduction 1, Discipline 3, Intimidation 3, Lore 1,
        Medicine 1, Deception 1, Insight 2, Leadership 1, Perception 3, Persuasion 1,
        Survival 2
Expertises: [Cultural] Alethi/Veden, [Weapon] Greatsword
Talents: Vigilant Stance, Stonestance (both Focus-gated stances)
Weapons: Greatsword (melee, two-handed, +5 vs. Physical, 1d10+5 keen, Deadly: causes
         an injury on hit), Crossbow (ranged 100/400, +5 vs. Physical, 1d8+5 keen,
         Loaded [1])
Armor: Alethi Uniform (Presentable — no conversation disadvantage), Chain armor
       (Deflect 2, Cumbersome [3])
Equipment: Military Kit (Backpack, Common clothes, Waterskin, Whetstone, Blanket,
           10 days food, Flint and steel)
Level-2 grant: +5 health, +1 rank Perception, +1 rank Intimidation, "The Mighty" talent
```

**Attempted mapping into `CharacterData`** (live-tested, see command below):

```python
CharacterData(
    character_id='alethi_duelist_01', name='Alethi Duelist', level=1,
    proficiency_bonus=2,   # NO COSMERE RPG EQUIVALENT — see below
    ability_scores={'strength': 3, 'speed': 2, 'intellect': 1,
                     'willpower': 3, 'awareness': 2, 'presence': 1},
    skills={'heavy_weaponry': True, 'athletics': True, 'intimidation': True,
            'discipline': True, 'perception': True},
    hit_points={'current': 15, 'maximum': 15, 'temporary': 0},
    armor_class=13,   # forced Physical Defense into a single scalar meant for AC
    character_class='Warrior (Shardbearer)', race='Human',
)
```

This **constructs without a Python error** — `ability_scores` and `skills` are untyped
dicts, so nothing stops arbitrary keys — but every downstream consumer breaks or lies
silently, live-verified:

```
$ uv run python -c "... mgr.get_skill_data(char_id, 'heavy_weaponry') ..."
{'ability': 'intelligence', 'ability_modifier': 0, ...}   # WRONG: falls back to the
                                                            # hardcoded Intelligence
                                                            # default; Heavy Weaponry
                                                            # should use Strength

$ uv run python -c "... mgr.get_skill_data(char_id, 'athletics') ..."
{'ability': 'strength', 'ability_modifier': -4, 'modifier': -2, ...}   # WRONG: found
   # the right attribute name by coincidence (both systems call it "athletics"), but
   # ran (3-10)//2 = -4 on a raw Cosmere score of 3 that should BE the bonus, not an
   # input to a modifier formula
```

**Fields with no home at all** (present on the sheet, no `CharacterData` field, no
computation path, nothing close):

| Sheet field | Status |
|---|---|
| Physical / Cognitive / Spiritual Defense (3 separate numbers) | ❌ only one scalar (`armor_class`) exists; forced 13 into it, discarding Cognitive/Spiritual entirely |
| Focus (current/max) | ❌ no field. Nearest concept, `LashingDicePool`, is a dice pool, not a flat point pool, and is Surgebinding-specific |
| Investiture (current/max, as a generic resource — separate from Stormlight-the-Roshar-sphere-currency) | 🟡 `stormlight_current/capacity` exists but is semantically Roshar spheres-as-currency, not a generic character resource pool; forcing "Investiture 5" into it conflates two different concepts |
| Deflect | ❌ no field; closest analog is the vendored engine's `damage_reduction` (§4), not exposed on `CharacterData` at all |
| Recovery Die (explicit `1d8` on the sheet) | 🟡 `hit_dice_remaining` (a count) exists but the die *size* is derived from a 5e class table, not authored per-character the way this sheet does it |
| Expertises as typed tags (`[Cultural]`, `[Weapon]`) | ❌ `expertise_skills: List[str]` is a flat skill-name list; cannot represent "Expertise: Greatsword" (not a skill at all) |
| Talents (Vigilant Stance, Stonestance) as Focus-gated stances | ❌ `features: List[str]` can hold the names as strings (decorative only, per the template audit §1) but nothing models "costs 1 Focus to activate, mutually exclusive with other stances" |
| Weapon traits: "Deadly: on a hit, cause an injury"; "Loaded [1]" (ammo-in-a-shot capacity distinct from 5e ammunition) | ❌ no injury-trigger tag on weapons found in the equipment data model |
| Armor traits: "Cumbersome [3]" (a Strength threshold below which the armor imposes Slowed + disadvantage), "Presentable" (social-scene bonus) | ❌ armor is a static AC number (per §3); no conditional-trait system on armor exists |
| Senses range (10 ft.) | ❌ no field; 5e has no equivalent single number either (5e splits vision types instead) |
| Lifting capacity (500 lb., derived from Strength) | ❌ no encumbrance/carrying-capacity system at all (confirmed absent in the template audit §7) |
| Level-2 grant structure ("+5 health, +1 rank in two named skills, gain a named Talent" — a fixed, per-level, per-Path advancement table) | ❌ `_apply_level_up` (5e) grants HP by class hit-die averaging and 5e class features by level-threshold tables; Cosmere RPG's flat "+5 HP, +1 skill rank x2, +1 talent" per-Path-per-level table is a different shape of progression data entirely |
| Purpose / Obstacle / Goals (narrative character-creation fields on the back of the sheet) | 🟡 could fit in `personality: Dict[str, Any]` or `backstory: str` (both free-form), but nothing currently reads or surfaces "Obstacle" the way `background`/`personality` are surfaced to the LLM |

**Fields that map cleanly**: `name`, `level`, `race`→Ancestry, `character_class`→Path,
`hit_points` (Health max/current), `equipment` (flat list — Military Kit contents fit
the existing `List[str]`), `languages` (Alethi/Veden culture reference), `conditions`
(list-of-strings, could hold Cosmere RPG condition names once authored per §7).

**Bottom line for this section**: roughly 11 of the ~20 sheet sections have **no home**
in `CharacterData` even as a mis-shaped field, and 2 more (`skills`, `ability_scores`)
technically accept the data but silently corrupt it on first read because of hardcoded
5e formulas underneath the untyped dict. This is not a "some fields missing" gap — it is
a "the type signature is a bag of strings, so nothing stops the assignment, but every
consumer downstream is 5e-shaped" gap, which is worse because it fails silently instead
of loudly.

---

## 11. The rules tiers

| Tier | Existing content | Reusable for Cosmere RPG? | Evidence | What's needed |
|---|---|---|---|---|
| Tier 1 (`components/srd_rules.py`, `data/rules/srd/*.json`) | 1,321 entries, **all 2014 5e SRD**, verified via `url` field: every entry points at `/api/2014/...` | ❌ | `docs/mechanics/EDITION_CONFLICTS_IN_CODE.md` (§"Every vendored dataset is 2014"): `ability_scores.json n=6 2014=6 2024=0`, and eight other datasets the same way | Wrong system, not just wrong edition. None of this data (5e monsters, 5e spells, 5e conditions) is Cosmere-RPG-shaped; a Cosmere RPG Tier 1 would need entirely new datasets (Cosmere RPG's own conditions, its own equipment list, its own "monster"/adversary stat-block shape) |
| Tier 2 (`components/cosmere_rules.py`, `data/rules/stormlight/surgebinding.json`) | Reads `parsed_data/863203275-cosmere-5e-radiant-s-handbook-v2-0/docling.md` — confirmed by the module docstring and `HANDBOOK_MD` path constant (`cosmere_rules.py:32-33`) | ❌ | The docstring is explicit about its own scope: `Tier 2  data/rules/stormlight/  -> Cosmere/Surgebinding`, sourced from the "**Cosmere 5e** Radiant's Handbook" — a *5e supplement*, not the standalone Cosmere RPG. `maneuvers()`, `features()`, `orders()` (`cosmere_rules.py` queries) assume a 5e-shaped action-cost model (`"lashing_dice"` cost, per `lashing_dice.py`'s own docstring quoting Handbook line 1862) | `cosmere_rules.py`'s *loader mechanism* (glob a rules directory, merge JSON, track reviewed/unreviewed provenance with line-cited quotes) is generic and reusable as a pattern for a new `data/rules/cosmere_rpg/` tier. But the *schema* it reads (maneuvers costing lashing dice, Radiant orders gated by ideal_level) is entirely Cosmere-5e-Handbook-specific and does not describe the standalone Cosmere RPG's Talents/Paths/Expertises at all |
| Where would Cosmere RPG rules live? | — | — | — | A new Tier (call it Tier 2b or a parallel Tier 2) reading a new `data/rules/cosmere_rpg/*.json` schema (Paths, Talents, Expertises, the Plot Die table, Injury table) is needed. The reviewed/unreviewed provenance-tracking pattern in `cosmere_rules.py` (lines cited against a parsed docling.md, a `verify_citations()` self-check) is worth copying wholesale — that part is system-agnostic engineering discipline, not 5e logic |
| `query_rules` tool routing (`dm_tools.py:388-477`) | Tier 2 Cosmere → Tier 1 SRD → Tier 3 rules judge → gap tracker | 🟡 | Confirmed working end-to-end for the existing tiers (`AUDIT_CHARACTER_AND_NONCOMBAT.md` §12) | The routing *shape* (try specific, fall back to general, fall back to judge, log gaps) is reusable; a Cosmere RPG tier would slot in as an additional early-checked tier, but only after its own data model exists |

---

## The bottom line

**No, not as-is, and the cost of making it work is closer to a rewrite of the character
and combat-resolution core than an extension of it.** The three options: **(a) keep 5e,
ignore the new books** — cheapest (zero engineering cost), but then the 20 sl019 pregens,
the Stormlight Starter Rules, and the whole standalone-Cosmere-RPG premise the user
clearly wants are simply unusable, which defeats the purpose of having added them.
**(b) dual-system support** — technically possible but expensive and risky: every layer
audited above (attribute derivation, skill-to-attribute mapping, AC/Defense computation,
hit/miss/graze resolution, resource pools, rest recovery, the rules-tier schema) would
need a parallel Cosmere RPG code path *and* a system-selector threaded through
`CharacterData`, `dnd_engine_wrapper.py`, `action_registry.py`, and `combat_session_manager.py`
— realistically 6-10 weeks of focused work given how deeply 5e assumptions are load-bearing
(§ below), with high risk of the exact silent-wrong-number failure mode demonstrated live
in §10 (`heavy_weaponry` silently defaulting to Intelligence, `athletics` silently running
a nonsensical modifier formula) recurring anywhere a name coincidentally overlaps between
systems. **(c) migrate fully to Cosmere RPG** — cheaper than (b) in the long run (one
code path, not two) but throws away the entire vendored `external/dnd_engine`, all 1,321
SRD entries, and the 379-passing 5e combat test suite, and is a multi-month rewrite of the
combat core, not a refactor. **Recommendation: (b) is not worth it; choose between (a) and
(c) based on which player base matters — if this is meant to actually run the Stormlight
Starter Rules sessions with the sl019 pregens, do (c) incrementally (new `CharacterData`
subtype + new resolution path, gated by a system flag, built fresh rather than
retrofitted), because §10 proves retrofitting produces silent wrong numbers, not loud
errors, which is the worst possible failure mode for a game engine.**

---

## Load-bearing 5e assumptions

Every place this audit found `d20 + AC/Defense + saves`-shaped logic that would have to
change for Cosmere RPG:

1. **`_calculate_ability_modifier`** (`character_manager.py:677-679`) — hardcodes
   `(score-10)//2`. Cosmere RPG attribute scores ARE the bonus; applying this formula to
   them produces large negative numbers (live-verified: STR 3 → modifier -4).
2. **`self.skill_abilities`** (`character_manager.py:196-213`) — hardcoded dict of
   exactly the 18 5e skill names. Any Cosmere RPG skill not in this list (Heavy Weaponry,
   Light Weaponry, Thievery, Deduction, Leadership, ...) silently falls back to
   Intelligence rather than erroring (live-verified).
3. **`armor_class` as a single scalar** (`character_manager.py:54`, `dnd_engine_wrapper.py:753`)
   — Cosmere RPG needs three (Physical/Cognitive/Spiritual Defense), each independently
   computed from two attributes; the existing field is one static, hand-authored number
   never recalculated from anything.
4. **Binary hit/miss resolution** — no graze/partial-success branch exists anywhere in
   the attack resolver; Cosmere RPG's core combat loop has one.
5. **`_roll_initiative`** (`combat_initializer.py:982,991`) — literally `d20 + dex_mod`
   by name; Cosmere RPG has no DEX attribute at all.
6. **`abilities` Literal type** (`external/dnd_engine/dnd/blocks/abilities.py:18`) — a
   vendored, hardcoded `typing.Literal['strength','dexterity','constitution',
   'intelligence','wisdom','charisma']`. Cannot represent Speed, Willpower, Awareness, or
   Presence without editing vendored code.
7. **`ActionEconomyConfig`** (`external/dnd_engine/dnd/blocks/action_economy.py:15-23`)
   — `actions`/`bonus_actions`/`reactions` as separate hardcoded counters matching 5e's
   specific three-category turn structure.
8. **`d20` dice library's grammar** — purely numeric (`NdM`, `kh/kl`, exploding, reroll,
   min/max); has no concept of a symbolic-face die, which the Cosmere RPG plot die
   fundamentally is.
9. **Spell slots** (`spellcasting.py` `SlotTable`) — keyed by 5e spell level (1st-9th);
   Cosmere RPG has no leveled-slot resource at all (Focus/Investiture are flat pools).
10. **`cosmere_rules.py`/`surgebinding.json`** — despite the name, this is a *5e
    supplement's* rules (the "Cosmere 5e Radiant's Handbook"), not the standalone
    Cosmere RPG; its maneuver-cost model (`lashing_dice`) and order-gating
    (`ideal_level`) are both 5e-Handbook-specific and do not describe the standalone
    game's Paths/Talents structure.
11. **`_apply_level_up`** (5e hit-die-averaging HP gain, class-feature-table lookups by
    level) — Cosmere RPG's per-Path, per-level advancement is a flat fixed-grant table
    (e.g. "+5 health, +1 rank in two named skills, gain a named Talent"), a different
    data shape entirely.

---

## What's genuinely system-agnostic

Parts of the codebase that would survive a move to Cosmere RPG (or dual support)
largely unchanged:

- **Persistence** (`SessionManager`, `CharacterData.to_dict()/from_dict()` round-trip
  mechanism) — a generic dataclass-to-JSON serializer; doesn't care what the fields mean.
- **The LLM/DM-tool layer architecture** (`agents/dm_tools.py`'s `@tool` registration
  pattern, the Haystack `Agent(tools=..., max_agent_steps=...)` wiring) — the *shape* of
  "expose a Python function as an LLM-callable tool" doesn't encode 5e assumptions; only
  some individual tools' *arguments* do (e.g. `spell_name`, `at_level`).
- **The tactical grid / battle map** (`components/combat/battle_map.py`,
  `tactical_grid.py`, `map_templates.py`) — position tracking, distance calculation,
  line-of-sight; grid mechanics are not edition-specific.
- **`ACTION_REGISTRY`/`is_offerable()` filtering mechanism** (§8) — register an action
  with a cost and requirements, filter by whether the actor can pay/qualify; the
  mechanism generalizes even though every current entry is 5e/Roshar-5e-shaped.
- **Turn-order advancing** (`combat_session_manager.py`'s index-into-a-list loop) — once
  initiative is computed by whatever formula, advancing through the list has no 5e logic
  in it.
- **Narrative pipelines** (`agents/scenario_generator_agent.py`, `agents/npc_controller_agent.py`,
  RAG retrieval via Qdrant) — pure LLM narrative generation and lore lookup; system-agnostic
  by construction, already proven to work across the Cosmere setting generally.
- **Campaign state** (`Narrative`/`Location`/`Quest` TypedDicts in `game_engine.py`,
  `CampaignConfig` in `core/game_initialization.py`) — quest objectives, location graphs,
  NPC attitude tracking; none of this encodes ability scores, AC, or dice mechanics.
- **The rules-tier provenance/citation-tracking *pattern*** in `cosmere_rules.py` (glob a
  directory, merge JSON, track reviewed/unreviewed status with line-cited quotes against
  a parsed source document, `verify_citations()` self-check) — the engineering discipline
  is reusable for an eventual Cosmere-RPG-native rules tier even though the current
  *schema* it reads is not.
- **Gap tracking** (`data/rules/gaps.json`, recording unresolved rules queries) — a
  logging mechanism, indifferent to which ruleset triggered the gap.

---

## Report

**File written**: `docs/mechanics/AUDIT_COSMERE_RPG_FEASIBILITY.md`

**Counts**: 11 numbered sections, ~45 individual mechanic rows audited; roughly
6 ✅ reusable-as-is, 14 🟡 reusable-with-significant-work, 25 ❌ nothing-exists-or-actively-wrong.
One dedicated concrete test (§10, the Alethi Duelist pregen) found **11 of ~20 sheet
sections with literally no field to hold them**, plus 2 more fields (`ability_scores`,
`skills`) that *accept* the data structurally but silently corrupt it through hardcoded
5e formulas — live-reproduced twice (`heavy_weaponry` → wrong attribute via silent
fallback; `athletics` → right attribute name, wrong value via a nonsensical formula
applied to it).

**Bottom-line recommendation**: do not attempt dual-system support (b) — the codebase's
5e assumptions are too deep and too silent-failure-prone (demonstrated live, not
theorized) for a safe retrofit. Choose between keeping 5e only (a, cheap, but abandons
the new books entirely) or a real migration to the standalone Cosmere RPG (c, expensive
but the only option that actually delivers what the new rulebooks promise) based on
which player experience the project actually wants; a partial migration will produce
exactly the kind of plausible-looking-wrong-number bugs this audit reproduced on the
first character sheet tried.

**Biggest surprise**: the codebase already *has* a "Cosmere" rules tier
(`components/cosmere_rules.py`) with a docstring that reads as if it solves this exact
problem — but it is scoped to the **"Cosmere 5e Radiant's Handbook,"** a 5e supplement,
not the standalone Cosmere RPG the user's new books actually are. A future maintainer
skimming module names (`cosmere_rules.py`, `CharacterData.rulebook = "Cosmere 5e
(Roshar)"`) could easily conclude Cosmere RPG support already exists in some form. It
does not — every "Cosmere" reference in the current codebase means "5e reskinned for
Roshar," never "the standalone Brotherwise Games system," and the two are mechanically
unrelated (d20+AC+levels+slots vs. d20+plot-die+Defenses+Focus+Expertises). Second
surprise: the untyped `Dict[str, int]` on `ability_scores`/`skills` means a Cosmere RPG
character *appears* to load without any error at all — the corruption is entirely
silent until a specific skill or attribute is actually rolled, which is the worst
possible place for a game engine to fail quietly.
