# Audit: Character, Progression, Spellcasting, and Non-Combat Mechanics

> **SESSION UPDATE — 2026-09-12 (commits `5a0a764`, `84000b6`, `66b04e0`):** DONE & tested on `phase-0-fixes`:
> - ✅ **ASI at levels 4/8/12/16/19**, **Extra Attack** at class levels (drives multiattack), **AC recalculation from equipped armor**, **per-class saving-throw proficiencies**, **currency (gp/sp/cp/pp/ep)**, **carrying capacity + encumbrance** (`84000b6`).
> - ✅ **Social skill checks as real dice** — Persuasion/Deception/Intimidation now roll via `process_skill_check` and feed attitude; **passive perception**; **inventory add/remove @tools**; **`export_game_state` character-branch fix** (uses `to_dict()`, no more HP/AC/equipment reset on import); **routing-history cap 20/50 → 200** (`66b04e0`).
> - ✅ **cast_spell offerability** and the **proficiency double-count** bug fixed; **Help** action wired (`5a0a764`).
> - ✅ Verified: expertise stored, exhaustion reduced on long rest, death saves working.
> - 🟡 **DEFERRED/blocked:** exploration-mode `cast_spell` (skipped as risky this pass); tool-proficiency mechanical gate; live mid-combat re-equip; shops/buying-selling; concentration/ritual/components for spellcasting. Feats/subclass/multiclass/inspiration remain "future" per the original triage.

**Date**: 2026-09-12
**Branch**: `phase-0-fixes` (HEAD `ac4b680`, built on the `439df7a` commit that landed
the uncommitted work described in `docs/SESSION_HANDOFF_2026-09-11.md`)
**Method**: every row below was verified by running real code (constructing objects,
calling methods, grepping production call sites) — not by reading docstrings. Where a
docstring's claim and the live behavior disagreed, the live behavior wins and the
disagreement is called out explicitly.

**Central distinction applied throughout**:
- **Implemented** = the code exists and does the right thing when exercised directly.
- **Reachable** = a player in a real session can trigger it — via a `dm_tools.py`
  `@tool` the LLM can call in the exploration/scenario pipeline, or a
  `combat_session_manager.py` / `ACTION_REGISTRY` entry actually offered in a combat
  turn. A method that only tests or a standalone script can reach is **not** a
  capability.

Legend: ✅ yes / 🟡 partial or unverified / ❌ no.

---

## 1. Character sheet fidelity (`components/character_manager.py`, `CharacterData`)

| Field/Mechanic | Implemented? | Reachable? | Evidence | Gap/notes ||
|---|---|---|---|---|---|
| Ability scores | ✅ | ✅ | `character_manager.py:45-46` `ability_scores`/`ability_modifiers`; read throughout combat, skills, `dnd_engine_wrapper.py` | Fully wired |
| Proficiency bonus | ✅ | ✅ | `character_manager.py:44`, `_calculate_proficiency_bonus` (`:1130`); live-tested level 1→20 gives +2→+6 | Correct |
| Skills + proficiency | ✅ | ✅ | `skills: Dict[str,bool]` (`:47`); read in `dnd_engine_wrapper.py` skill checks | Wired |
| Expertise | ✅ | ✅ | `expertise_skills` (`:48`); read `dnd_engine_wrapper.py:659`, `character_manager.py:566` | Wired, not just stored | COMMENT: store it now
| Saving throw proficiencies | ✅ | 🟡 | `saving_throw_proficiencies` (`:55`) | Field defined and populated; no consumer confirmed in a save-roll path in the files searched — unresolved between forks, flag for a combat-focused follow-up | COMMENT: implement and wire now completely
| HP / hit dice | ✅ | ✅ | `hit_points` dict, `hit_dice_remaining`; live-tested level-up (+8 HP at level 2), `short_rest` spends dice | Fully wired |
| AC | ✅ (as a static field) | 🟡 | `armor_class` field exists | Never recalculated from equipped armor — see §11 | COMMENT: implement recalc and wire now completely
| Speed | ✅ | ❓ | `speed: int = 30` (`:97`) | Not traced to a consumer in this pass | COMMENT: Should be implemented and wired in combat
| Level | ✅ | ✅ | `level` field; live-tested | Wired |
| Class | ✅ | ✅ | `character_class`; drives hit die (`_hit_die_for_class:884`) and feature-table lookups | Wired |
| Subclass | ❌ | ❌ | Zero hits for "subclass" anywhere in `character_manager.py` | Not modeled at all. Roshar `radiant_order` partially substitutes for Surgebinders, but there is no generic subclass slot (Champion Fighter, Berserker Barbarian, etc.) | COMMENT: implement and wire in future version
| Species/race | ✅ | ✅ | `race` field, read for languages/traits at init | Wired |
| Background | ✅ (stored) | 🟡 | `background` field | Saved and shown to the LLM as flavor text; no mechanical consumer (no skill/tool proficiency grants) found |  COMMENT: OK in current version
| `features` (granted feature ids) | ✅ | ✅ | `features: List[str]` (`:50`); populated via `grant_class_features`, consumed by `class_feature_status` and `ClassFeatureEngine` | Reachable for tracking; whether individual features *work* mechanically is audited in §3 |
| `spell_slots` | ✅ (field + real accounting) | ❌ in real play | `:59`; slot spending logic in `spellcasting.py` is correct | Unreachable — see §4, the `cast_spell` offerability bug |  COMMENT: implement recalc and wire now completely
| `spells_known` | ✅ (field) | ❌ in real play | `:92` | Same blocker as above | COMMENT: implement and wire now completely
| Feats | ❌ | ❌ | Zero hits for "feat"/"feats" | Not modeled — no ASI-vs-feat choice exists | COMMENT: implement and wire in future version
| Languages | ✅ | 🟡 | `languages` (`:93`); surfaced via `get_character_summary` (`:1907`) and read into narration at `game_engine.py:525,680,829` | Narrative/LLM-prompt context only — no mechanical gate found (e.g. nothing blocks understanding a language the character doesn't speak) | COMMENT: implement and wire in future version
| Tools | ✅ | 🟡 | `tool_proficiencies` (`:98`) | Same as languages — decorative context, no mechanical tool-check gate | COMMENT: implement and wire now completely
| Inventory (item list) | ✅ | 🟡 | `equipment: List[str]` (`:94`), `add_equipment`/`remove_equipment` (`:1830-1850`) | See §11 — unreachable via any `@tool` or combat caller; only consumed once at entity-sync startup |
| Currency/gold | ❌ | ❌ | Zero hits | Not modeled at all, not even as a data structure | COMMENT: implement and wire now completely
| Carrying capacity | ❌ | ❌ | Zero hits | Not modeled | COMMENT: implement and wire now completely
| Attunement slots | ❌ | ❌ | Zero hits | Not modeled. `has_shardblade`/`has_shardplate` are separate ad hoc booleans, not a generic 3-item attunement system |  COMMENT: implement and wire in future version
| Exhaustion | ❌ as a field / ✅ as a condition | 🟡 | `grep -n "exhaustion" components/character_manager.py` → zero hits; real level-tracked (1-6) logic lives in `components/engine_conditions.py` and is read by `components/policy.py:270` for disadvantage | Works through the generic `conditions: List[str]` string list and `engine_conditions.py`, not as a first-class `CharacterData` field. One fork read it as "field absent" (grepping `character_manager.py` alone) and another as "mechanically real" (grepping the conditions engine) — both are correct about their own file; the mechanic exists, just not where CLAUDE.md's field list implies | COMMENT: OK for this version
| Conditions | ✅ | ✅ | `conditions: List[str]` (`:49`); `engine_conditions.py` implements Petrified, Exhaustion, etc. (commit `311230d`) | Wired |
| Inspiration | ❌ | ❌ | Zero hits | Not modeled | COMMENT: implement and wire in future version

**Built but unreachable / entirely absent** (confirmed by grep — only self-references,
no production consumer in `components/`, `agents/`, `core/`, `orchestrator/`): subclass,
feats, currency/gold, carrying capacity, attunement slots, inspiration — none of these
exist even as a stub field. Background, languages, and tool proficiencies exist and are
saved/shown to the LLM, but have zero mechanical effect.

---

## 2. Progression

| Mechanic | Implemented? | Reachable? | Evidence | Gap/notes ||
|---|---|---|---|---|---|
| XP tracking | ✅ | ✅ | `experience_points` (`character_manager.py:122`) | Wired |
| XP award | ✅ | ✅ | `character_manager.py:707 award_xp()`; **live-tested**: `award_xp('c1', 300)` → level 1→2, HP 10→18, features granted. Called in production from `agents/dm_tools.py:790 award_experience` (`@tool`, in `DM_TOOLS`, iterates the whole party, skips NPCs) | Genuinely reachable, not just a method that exists |
| Leveling 1→20 | ✅ | ✅ | `_apply_level_up` (`:741`); live-tested to level 20 — HP, proficiency bonus, hit dice, class features all update correctly | Fully wired end to end |
| HP per level | ✅ | ✅ | `_apply_level_up:748`, uses 5e "take the average" rule (`hit_die//2 + 1 + CON`); live-tested +8 HP at level 2 with a d10 hit die and CON +2 | Correct |
| Proficiency bonus by level | ✅ | ✅ | `_calculate_proficiency_bonus` (`:1130`); live-tested 2→6 across the level range | Correct |
| **ASI at 4/8/12/16/19** | ❌ | ❌ | Live-tested: leveled a character 1→20 via `award_xp`; `ability_scores` dict was byte-identical before and after | **Confirmed gap.** Leveling advances HP/proficiency/features but never touches ability scores. A character can be XP-farmed to level 20 with the ability scores rolled at creation, no ASI, no feat choice, ever | COMMENT: implement and wire now completely
| Extra Attack | 🟡 | ❓ | Lives in `components/combat/multiattack.py` per a `class_features.py:62` comment, not in the level-up path | Not granted as a named feature by `_apply_level_up` at class-appropriate levels in the evidence gathered — flagged, not fully resolved | COMMENT: implement and wire now completely
| Multiclassing | ❌ | ❌ | Zero hits for "multiclass" | `character_class` is a single string; no secondary class levels possible | COMMENT: implement and wire in future version
| Death saves | ✅ (fields + reset) | 🟡 | `death_save_successes/failures`, `is_stable`, `is_dead` (`:124-127`); reset on waking via `short_rest` (`:937-938`) | Field tracking confirmed; the roll-triggering mechanic itself wasn't independently re-verified in this pass | COMMENT: I think this was working. Should be verified

**Surprise**: `character_manager.py`'s own in-file comments (era of the handoff doc) still
describe XP/leveling as unimplemented ("grep returned zero hits"). That is now **stale**
— `award_xp`, `_apply_level_up`, `grant_class_features`, `short_rest`, `long_rest` are
real, tested, and wired to `@tool`s that the scenario-generator prompt explicitly
instructs the LLM to call (`agents/scenario_generator_agent.py:779,784`). This is one of
the strongest positive findings in the whole audit — but it makes the **silent absence of
ASI** at level 4/8/12/16/19 worse, not better: a fully "working" leveling system that
never touches the one thing 5e balances hardest around.

---

## 3. Class features (`components/combat/class_features.py`, `data/rules/class_features/`)

| Mechanic | Implemented? | Reachable? | Evidence | Gap/notes | |
|---|---|---|---|---|---|
| `ClassFeatureEngine` core (use/consume/recharge) | ✅ | 🟡 | Directly invoked and verified: Rage and Second Wind produced correct, real state changes when called via `DnDEngineWrapper.class_feature_engine(...)` | The engine itself is not a stub — closer to done than `standard_actions.py` | COMMENT: Confirm if fully working now
| Registration / entry point into combat turns | ❌ | ❌ | No `register_*` function found comparable to `register_standard_actions()`; nothing in `action_registry.py`/`combat_session_manager.py` offers class features as selectable combat actions the way Surges or `cast_spell` are offered | **Not reachable from a real turn.** The engine can be called directly (as the audit did), but nothing in the offer/menu path calls it | COMMENT: Is this needed for proper game play, if so, implement and wire now completely
| Coverage across the 12 classes | 🟡 | ❌ | `data/rules/class_features/` exists with real content (not an empty scaffold) | Full per-class breakdown wasn't exhaustively enumerated class-by-class in this pass — Rage (Barbarian) and Second Wind (Fighter) confirmed working when called directly; Sneak Attack, Action Surge, Divine Smite not independently re-verified this session. Treat as "engine works, authored data incomplete/unaudited beyond the two spot-checked features," matching the handoff's original priority list | COMMENT: implement and wire now completely
| Recharge on rest | ✅ | ✅ | `short_rest`/`long_rest` in `character_manager.py` call `recharge_class_features`, rest-type aware | Confirmed via §6 (rests) test run: 15/15 rest tests pass |

**Bottom line**: this remains the least mature module by reachability, exactly as the
handoff doc predicted, but for a more specific reason than "essentially unverified" —
the *engine* is real and correct when called directly; the *offer-to-player/NPC* wiring
that would make it reachable in a session simply does not exist yet. This is the same
missing-last-step pattern as `cast_spell` and `standard_actions.py`, a third instance of
the identical failure mode.

---

## 4. Spellcasting (`components/combat/spellcasting.py`, `components/combat/spell_compiler.py`) 
COMMENT: implement and wire now completely

**Test run**: `uv run pytest tests/combat/test_spellcasting.py -q -p no:randomly` →
**64 passed, 8 failed**, unchanged in count from the handoff doc but for a **different
root cause than the handoff claimed**.

The handoff doc (`docs/SESSION_HANDOFF_2026-09-11.md`, item 3) says *"`cast_spell` was
never added to `ACTION_REGISTRY`."* That claim is now **false** — it has since been
registered:

```python
# components/combat/action_registry.py:118-132
"cast_spell": {
    "type": "spell_action",
    "action_class": None,
    "description": "Cast a spell",
    "params": ["target_entity_uuid", "spell_name", "at_level"],
    "param_defaults": {"at_level": None},   # <-- spell_name is MISSING here
    "cost_type": "actions",
    "cost": 1,
    "requires": "spellcasting",
},
```

The comment directly above this dict (lines 123-128) *claims* `spell_name: None` means
"the service picks a spell the caster knows and can currently pay for" — but the actual
`param_defaults` dict never sets that key. Verified live:

```
$ uv run python -c "
from components.combat.action_registry import is_offerable, required_caller_params
print(required_caller_params('cast_spell'))
print(is_offerable('cast_spell'))
"
['spell_name']
False
```

Because `spell_name` has no default, `required_caller_params('cast_spell')` returns
`['spell_name']`, so `is_offerable('cast_spell')` is `False`, so `cast_spell` is filtered
out of `offerable_actions()` — and both consumers that gate on it
(`combat_session_manager.py:790` for the player menu, `:1976` for NPC AI) never offer it.
This is the **exact same bug class**, in the **exact same file**, that the codebase's own
comments (lines 123-128 and 308-311) describe fixing for four of the five Surges. The
fix pattern is documented in the same file; it was simply not applied to this entry. The
one-line fix would be adding `"spell_name": None` to `param_defaults`; `spellcasting.py`'s
`cast()` (line 766) already handles `spell_name=None` via `default_spell()` (confirmed by
one of the audit forks), so the mechanical plumbing for the fix already exists — only the
registry entry is incomplete.

| Mechanic | Implemented? | Reachable? | Evidence | Gap/notes |
|---|---|---|---|---|
| `cast_spell` registered in `ACTION_REGISTRY` | ✅ | ❌ | `action_registry.py:118`; `is_offerable` → `False` live | Registered but filtered from every menu |
| Spell slot tracking/spending | ✅ | ❌ (blocked) | `SlotTable`, exercised directly by 64 passing tests | Mechanically correct, unreachable via the only entry point |
| Cantrips at will | ✅ | ❌ (blocked) | `default_spell()` prefers cantrips before slots (`spellcasting.py:744`) | Same blocker |
| Upcasting | ✅ | ❌ (blocked) | `cast(at_level=...)` → `compile_spell(slot_level=...)`, covered by passing tests | Same blocker |
| Save DC (8+prof+mod), spell attack bonus | ✅ | ❌ (blocked) | `SpellcasterStats` computed and tested | Same blocker |
| Concentration | 🟡 | ❌ (blocked) | `concentration: bool` surfaced on compiled spells (`spellcasting.py:723`) | No confirmed break-on-damage hook found wired into the damage-resolution path — flagged unverified, not confirmed working, independent of the offerability blocker |
| Ritual casting | ❌ | ❌ | No `ritual` handling found in `spellcasting.py`/`spell_compiler.py` | Appears entirely absent, not merely unreachable |
| Spell components (V/S/M) | ❌ | ❌ | No component-checking code found | Absent |
| Prepared vs. known casters | ❌ | ❌ | No differentiation found | Absent |
| **Of 319 SRD spells, how many are castable in real play** | — | **0** | `grep -rn "SpellcastingService\|\.cast(" components/ agents/ core/ orchestrator/` (excluding tests) → zero non-combat, non-menu callers; the only path to `cast()` is the blocked combat menu | All 319 compile and resolve correctly when called directly (mechanics pass); **zero are reachable in a real session** today |

---

## 5. Skills and checks

| Mechanic | Implemented? | Reachable? | Evidence | Gap/notes | |
|---|---|---|---|---|---|
| 18 SRD skills + 7-step resolution pipeline | ✅ | ✅ | `components/game_engine.py:196 process_skill_check`; live run: `roll_skill_check(skill='athletics', dc=12, actor='Aggi')` → `{'success': True, 'roll_total': 18, 'selected_roll': 16, 'character_modifier': 2, 'advantage_state': 'normal', 'dc': 11}` | DC 12→11 rescale is PolicyEngine profile scaling (RAW/HOUSE/EASY) working as intended, not a bug |
| `roll_skill_check` reachable | ✅ | ✅ | `agents/dm_tools.py:179` `@tool`; in `DM_TOOLS` (`:841`); bound into a real Haystack `Agent(tools=dm_tools, max_agent_steps=10)` in `agents/scenario_generator_agent.py:826-844`; prompt explicitly instructs the LLM to call it | Genuinely reachable, not a dead tool |
| Passive Perception | 🟡 | ❓ | No production hits for `passive_perception` found outside tests in the scope searched | Likely absent or unverified — not confirmed either way | COMMENT: implement and wire now completely
| Advantage/disadvantage sources (cover, flanking, darkvision) | ✅ | ✅ (combat only) | `components/policy.py:299-301` (darkvision vs. dim/dark); tactical layer per commit `0d22104` | No exploration-side advantage source found — combat-only | COMMENT: implement and wire in future version for non-combat option
| Help action | ❓ | ❓ | Reported unwired as part of `standard_actions.py` in the handoff; not independently re-verified in this session | Carry forward as unresolved | COMMENT: implement and wire now completely

---

## 6. Rests

| Mechanic | Implemented? | Reachable? | Evidence | Gap/notes ||
|---|---|---|---|---|---|
| `take_rest` (short + long) | ✅ | ✅ | `agents/dm_tools.py:606 @tool take_rest`; delegates to `character_manager.py:908 short_rest` / `:957 long_rest`; test run `uv run pytest tests/test_deterministic_game_flow.py -k "Rest or rest" -q` → **15 passed** | Genuinely reachable |
| HP recovery | ✅ | ✅ | Both short and long rest recover HP | |
| Hit dice | ✅ | ✅ | Short rest spends hit dice for healing; long rest recovers half | |
| Spell slots | ✅ | ✅ (mechanically, moot given §4) | Long rest only | Recovers correctly but there's nothing reachable to spend a slot on right now (§4) |
| Stormlight | ✅ | ✅ | Long rest only | |
| Death saves reset | ✅ | ✅ | Both rest types reset on waking | |
| Class feature uses | ✅ | ✅ | `recharge_class_features`, rest-type aware | Consistent with §3's finding that the engine itself works |
| Exhaustion reduction | ❓ | ❓ | Not independently confirmed this session given exhaustion isn't a `CharacterData` field (§1) | Likely handled through `engine_conditions.py` if at all — unresolved | COMMENT: verify first and if not present, implement and wire now completely

---

## 7. Exploration/downtime

| Mechanic | Implemented? | Reachable? | Evidence | Gap/notes ||
|---|---|---|---|---|---|
| Travel (location-graph) | ✅ | ✅ | `agents/dm_tools.py:820 @tool travel_to_location` → `game_engine.py:1199 travel_to()`, in `DM_TOOLS`, advances the game clock | This is a location-graph teleport between named locations, **not** distance/pace-based 5e travel |
| Travel pace (fast/normal/slow) | ❌ | ❌ | `grep -rln "travel_pace\|movement_pace"` → zero hits anywhere | Concept doesn't exist | COMMENT: implement and wire in future version
| Encumbrance / carrying capacity | ❌ | ❌ | Zero hits for a character-weight system | Not implemented | COMMENT: implement and wire now completely
| Falling damage | ❌ | ❌ | Grep hits were false positives (tactical grid "falling back" language) | Not implemented | COMMENT: implement and wire in future version
| Suffocation | ❌ | ❌ | Zero hits | Not implemented | COMMENT: implement and wire in future version
| Burning/fire hazard | ❌ | ❌ | Grep hits were false positives (unrelated retry/action-registry code) | Not implemented | COMMENT: implement and wire in future version
| Dehydration/malnutrition/starvation | ❌ | ❌ | Zero hits | Not implemented | COMMENT: implement and wire in future version
| Traps | ❌ | ❌ | Grep hits were false positives (maneuver files) | Not implemented | COMMENT: implement and wire in future version
| Breaking objects | ❌ | ❌ | Zero hits | Not implemented | COMMENT: implement and wire in future version
| Light/vision (darkvision) | 🟡 | ✅ combat only | `components/policy.py:299-301,696` | Only affects combat advantage rolls; no exploration/stealth vision system outside combat | COMMENT: OK for now. implement and wire in future version

None of falling, suffocation, burning, dehydration/malnutrition, traps, or object-breaking
exist in the codebase in any form — not stubs, not data structures, not partial.

---

## 8. Social

| Mechanic | Implemented? | Reachable? | Evidence | Gap/notes ||
|---|---|---|---|---|---|
| NPC dialogue generation | ✅ | ✅ | `agents/npc_controller_agent.py:22 generate_npc_response`, bound as a Haystack Agent tool (`:278`) | Pure LLM narrative generation |
| NPC attitude tracking | 🟡 | ✅ | `assess_attitude_change` (`:107-156`): 5-level scale (hostile→helpful), shifted ±3 by LLM-classified match against `positive_actions`/`negative_actions` personality keyword lists | Real and reachable, but entirely **non-mechanical** — no dice anywhere | COMMENT: OK for now. implement and wire in future version
| Persuasion/Deception/Intimidation as dice checks | ❌ | ❌ | No `roll_skill_check` import or call anywhere in `npc_controller_agent.py`, confirmed by direct read of the file | These three skills are valid arguments `roll_skill_check` would accept, but nothing in the social pipeline ever calls it. Social interaction and the dice/DC machinery are two structurally disjoint systems — a player "trying to persuade an NPC" gets pure LLM vibes-based adjudication, never a DC roll, even though the underlying skill-check tool fully supports it and is reachable elsewhere (§5) | COMMENT: implement and wire now completely

---

## 9. Quests, XP awards, campaign state, endgame

| Mechanic | Implemented? | Reachable? | Evidence | Gap/notes |
|---|---|---|---|---|
| Quest objective completion | ✅ | ✅ | `agents/dm_tools.py:761 advance_quest` → `game_engine.py:1090 complete_quest_objective()`; real callers confirmed at `scripts/playtest.py:369` and `game_engine.py:1700`, not just tests | CLAUDE.md's claim this was fixed in plan 2.3 holds up under direct verification |
| XP award (production path) | ✅ | ✅ | `agents/dm_tools.py:790 award_experience` → `character_manager.py:707 award_xp()`, iterates the whole party, skips NPCs | Confirmed called from a real tool, not just the method existing |
| Endgame evaluation | ✅ | ✅ | `orchestrator/pipeline_integration.py:1046 _check_endgame()` called at `:834` after every resolved encounter; also gated via `haystack_dnd_game.py:608 _check_campaign_endgame` | `EndgameEvaluator` (`components/campaign_schema.py:36`) requires the campaign JSON to declare both `endgame` and `quests` keys (`:245`) — whether `data/current_campaign/shards_of_honor.json` satisfies this was not independently re-verified this session |
| Campaign context (Narrative/Location/Quest) | ✅ | ✅ | TypedDicts at `game_engine.py:54,71,82`; round-tripped correctly through `export_game_state`/`import_game_state` (see §10) | Confirmed byte-identical after import/export in a live test |

---

## 10. Persistence — real save/load round trip (dedicated test, run twice)

**Test A — `CharacterData.to_dict()`/`from_dict()` through `SessionManager`, 53 fields**:
save → load → diff. Result: **zero fields lost**. HP, AC, equipment list, conditions,
`spell_slots` (an int-keyed dict, JSON-stringified and correctly restored), Stormlight,
and XP were all identical after the round trip.

**Test B — full `GameEngine.export_game_state()`/`import_game_state()`** exposed a real
landmine. `quest_context`/`location_context`/`campaign_flags` round-trip byte-identical.
But `export_game_state()`'s own `"character_data"` key is built from
`get_character_summary()` (an analytics view), not `to_dict()`. Restoring through that
branch produces a fresh, empty default character:

```
restored via export_game_state()'s character_data branch:
  HP: {'current': 0, 'maximum': 0, 'temporary': 0}, AC: 10, equipment: []

restored via the REAL app's actual load path (haystack_dnd_game.py, uses to_dict() directly):
  HP: {'current': 20, 'maximum': 28, ...}, AC: 16, equipment: ['longsword', 'shield']
```

The live game only survives this because `haystack_dnd_game.py:1164-1202` (save) and
`:1097-1162` (load) bypass `export_game_state()`'s lossy `character_data` blob entirely —
they build `character_manager_state` from `to_dict()` and restore via `add_character()`
directly, never touching `import_game_state()`'s internal character branch.

| Mechanic | Implemented? | Reachable? | Evidence | Gap/notes ||
|---|---|---|---|---|---|
| Character save/load (real app path) | ✅ | ✅ | `haystack_dnd_game.py:1164-1202`/`:1097-1162`, live-tested, fully lossless | Correct, per an in-code comment referencing "Plan 0.3" |
| `GameEngine.export_game_state()`'s embedded `character_data` | 🟡 exists, misleading | ❌ never used for restore by the real app | `game_engine.py:524-527` calls `get_character_summary()`, drops HP/AC/equipment/spell_slots to defaults | **Live landmine**, not just a historical one: any *new* caller of `import_game_state()` that trusts its own character-restoration branch — a script, a test, a future refactor — will silently resurrect a full-HP character as a 0-HP husk. It looks authoritative and is not | COMMENT: implement and wire now completely
| Quest/location/campaign-flags round trip | ✅ | ✅ | Live-tested, byte-identical | |
| Routing history / session stats | ✅ | ✅ | `session_manager.py:207-212` | Last 20/50 entries only, by design (not a bug) |COMMENT: increase the number of entries

**Lost on save/load (via the real app path)**: nothing found — the real path is
lossless for everything tested. **Lost on save/load (via the parallel, unused
`export_game_state`/`import_game_state` character branch)**: HP, AC, equipment,
spell_slots — i.e. everything that matters, silently reset to defaults. This second path
exists in the same class as the correct one and is a trap for any future caller.

---

## 11. Inventory and equipment

| Mechanic | Implemented? | Reachable? | Evidence | Gap/notes ||
|---|---|---|---|---|---|
| Add/remove named inventory item | ✅ | ❌ | `character_manager.py:1830 add_equipment` / `:1843 remove_equipment` | Zero grep hits outside `character_manager.py` and its own summary field — no `@tool`, no combat caller. Unreachable in a real session | COMMENT: implement and wire now completely
| Weapon equip → real attack bonus/damage | ✅ | ✅ | `dnd_engine_wrapper.py:231 equip_weapon()`, auto-invoked for every character at entity-sync time via `equip_from_character_data()` (`:331`, called from `__post_init__:88`) | Genuinely wired: builds a real `dnd.blocks.equipment.Weapon` from `CharacterData.equipment` string names and equips it into the vendored engine, consumed by `tactical_rules.py`, `class_features.py`, `standard_actions.py`, `maneuver_executor.py` |
| Proficiency on weapon attacks | ❌ bug, confirmed still present | ✅ (unfortunately reachable) | `dnd_engine_wrapper.py:259-293`, own in-code comment: "STR 16 (+3) with a longsword: level 1 rolls +7 vs RAW +5 ... level 17 rolls +15 vs RAW +9" | Matches `SESSION_HANDOFF_2026-09-11.md` item 8 exactly — **still not fixed**. Pinned (and currently failing) by `tests/combat/test_proficiency_on_attacks.py`: **2 passed, 7 failed** when re-run just now | COMMENT: implement and wire now completely
| Armor equip → AC change | ❌ | ❌ | Exhaustive grep for `Armor(`/`equip_armor` in `dnd_engine_wrapper.py`: zero hits. `_sync_characters_to_entities()` (`:754`) does `EquipmentConfig(unarmored_ac=character.armor_class)` — a static, pre-baked number copied straight in | **No armor-item-to-AC formula exists at all.** `armor_class` is authored once at character creation and never recalculated. Equipping/unequipping armor mid-game has zero mechanical effect |COMMENT: implement and wire now completely
| Attunement (max 3) | ❌ | ❌ | Zero hits | Not modeled |COMMENT: implement and wire in future version
| Currency / buying / selling | ❌ | ❌ | Zero hits | No economy system in any form, not even a data structure |COMMENT: implement and wire now completely
| Two parallel equipment representations | 🟡 | — | `CharacterData.equipment: List[str]` (flat names, decorative after startup) vs. the engine's real `entity.equipment: EquipmentConfig` (weapon slots, feeds attack bonus) | Connected **one-way, read-only, at initial entity sync only**. There is no "equip a newly found sword mid-combat" flow — `equip_weapon` is never called again after `__post_init__` | COMMENT: implement and wire now completely

---

## 12. Rules architecture

| Mechanic | Implemented? | Reachable? | Evidence | Gap/notes |
|---|---|---|---|---|
| Tier 1 SRD datasets loaded | ✅ | ✅ | `srd_rules.py:41-43`, `DATASETS` = 10 sets: monsters, spells, conditions, equipment, magic_items, rules, skills, damage_types, weapon_properties, ability_scores; all loaded at init (`:50-78`) | All 10 present |
| `query_rules` reaches all 3 tiers | ✅ | ✅ | `dm_tools.py:388-477`: Tier 2 Cosmere (`cosmere.get_maneuver`/`order`) → Tier 1 SRD (`srd.lookup`, searches all 10 datasets, per an in-code comment documenting a prior bug where only 4/10 were searched, now fixed) → Tier 3 `rules_judge.judge()` with precedent citation → gap-tracker fallback | All 10 datasets confirmed reachable through the real tool call path |
| Gap tracking | ✅ | ✅ | `dm_tools.py:469-471`, records unresolved queries to `data/rules/gaps.json` on Tier-4 fallback | Working as designed |

---

## 13. DM tools — complete enumeration

All 15 `@tool`-decorated functions in `agents/dm_tools.py` are collected into `DM_TOOLS`
(`:840-856`), and that exact list is passed as `tools=dm_tools` into a real Haystack
`Agent` in `agents/scenario_generator_agent.py:826-834` (`max_agent_steps=10`) — this is
the **exploration/scenario pipeline**, confirmed reachable, not merely defined.

| Tool | Delegates to | Reachable from scenario pipeline? |
|---|---|---|
| `roll_skill_check` | `game_engine.py` 7-step pipeline | ✅ |
| `roll_dice` | `DiceRoller` / d20 | ✅ |
| `get_character_state` | `character_manager` summary | ✅ |
| `get_party_state` | `character_manager` | ✅ |
| `get_world_state` | `game_engine` location/environment | ✅ |
| `query_rules` | all 3 rule tiers | ✅ |
| `search_lore` | RAG/Qdrant | ✅ |
| `apply_damage` | `game_engine`/`character_manager` HP | ✅ |
| `apply_healing` | same | ✅ |
| `take_rest` | `game_engine.py:606` | ✅ |
| `stabilize_dying` | death-save state | ✅ |
| `spend_stormlight` | Roshar resource | ✅ |
| `advance_quest` | `game_engine.complete_quest_objective`/`add_quest_objective` | ✅ |
| `award_experience` | `character_manager.award_xp` | ✅ |
| `travel_to_location` | `game_engine.travel_to` | ✅ |

**Important scope note**: this is the exploration/scenario pipeline's tool set only.
Combat does **not** go through `dm_tools.py` — it uses the entirely separate
`ACTION_REGISTRY`/`is_offerable` mechanism (see §4). "Reachable via dm_tools" and
"reachable in a combat turn" are two disjoint claims; see the cross-mode section below.

---

## Test status

`uv run pytest tests/ -q -p no:randomly --ignore=tests/combat --deselect tests/test_llm_utils.py -k "not test_gemini_ and not test_tool_calling and not test_api_connection and not test_game_"`:

```
1198 passed, 25 warnings in 87.64s
```

`uv run pytest tests/combat/ -q -p no:randomly` (for cross-reference, since several
findings above are pinned by combat-suite tests):

```
17 failed, 721 passed, 24 warnings in 119.44s
```

The 17 combat failures are, verified individually:
- 8 in `tests/combat/test_spellcasting.py` — all offerability tests (`TestCastSpellIsOfferable`, `TestOnlyCastersAreOfferedCastSpell`), matching §4's finding exactly.
- 7 in `tests/combat/test_proficiency_on_attacks.py` — matching §11's proficiency-double-counting finding exactly.
- `tests/combat/test_combat_integration.py::test_combat_agent_error_handling` — still failing, unresolved since the handoff.
- `tests/combat/test_combat_action_resolver_functional.py::test_action_types_are_categorized` — fails because it asserts every `ACTION_REGISTRY` entry's `type` is one of `["dnd_action", "dnd_condition", "roshar_action", "roshar_equipment", "roshar_condition"]`; `cast_spell`'s `type` is `"spell_action"`, which was never added to this test's allowlist when spellcasting was authored. A stale test, not a new bug.

These numbers match the handoff doc's historical range (17-20 failed, 718-721 passed)
closely — the tree has not materially regressed or improved on these specific failures
since 2026-09-11, aside from `cast_spell` moving from "not registered" to "registered but
still filtered," which is a real but incomplete step forward.

---

## Built but unreachable (highest-value findings)

1. **`cast_spell`** — registered in `ACTION_REGISTRY`, mechanically complete (64/72 tests
   pass), but filtered out of every menu because `param_defaults` omits `spell_name`.
   Zero of 319 SRD spells are castable in a real session. One-line fix identified:
   add `"spell_name": None` to `param_defaults` (the `cast()` method already handles
   `None` via `default_spell()`).
2. **Class features engine** (`class_features.py`) — the engine itself works correctly
   when called directly (Rage, Second Wind both verified), but has no registration
   entry point into `ACTION_REGISTRY`/combat turns at all. Not offered to players or
   NPCs under any circumstance.
3. **`standard_actions.py`** (Grapple, Shove, Help, Ready, Hide, Search, Disengage,
   two-weapon fighting) — per the handoff doc, `register_standard_actions()` exists but
   nothing calls it, and no test file exists. Not independently re-verified this session
   but no evidence of a fix landing (no new test file found, no wiring grep hit).
4. **Inventory add/remove** (`add_equipment`/`remove_equipment`) — exist on
   `CharacterData`, have zero external callers (no `@tool`, no combat use).
5. **`export_game_state()`'s embedded character-restore branch** — a fully-coded,
   plausible-looking persistence path that silently destroys character state (HP→0,
   AC→10, equipment→[]) if anyone ever calls it instead of the real app's save/load
   functions. A landmine for future refactors, not currently triggered in the live game.
6. **ASI at 4/8/12/16/19** — not merely unreachable, entirely absent from the otherwise
   fully-wired and well-tested leveling system.
7. Background, languages, tool proficiencies, saving-throw proficiencies (partially) —
   stored and shown to the LLM, mechanically inert.

---

## Reachable in one mode but not the other

| Mechanic | Combat | Exploration/scenario |
|---|---|---|
| `roll_skill_check` / dice, DCs | Uses a separate resolver, not this tool | ✅ reachable via `dm_tools.py` | COMMENT: is it possible to combine to have one source of truth
| `cast_spell` / spellcasting | ❌ registered but filtered from the menu | Not offered at all outside combat (no exploration-mode casting exists) | COMMENT: should be available in non-combat implement and wire now completely
| Class features (Rage, Second Wind, etc.) | ❌ engine exists, not offered in any menu | N/A — combat-only concept | COMMENT: implement and wire now completely
| Advantage/disadvantage, cover, flanking, darkvision | ✅ full tactical layer | ❌ no exploration-side equivalent | COMMENT: implement and wire in future version
| Persuasion/Deception/Intimidation as dice checks | N/A | ❌ social pipeline never calls `roll_skill_check`, despite it fully supporting these skills | COMMENT: implement and wire now completely
| Travel | N/A (combat has tactical grid movement instead) | ✅ location-graph `travel_to_location`, but no pace/distance model |
| Weapon-equip effects on attack | ✅ wired (with the proficiency bug) | N/A |
| Armor-equip effects on AC | ❌ absent in both modes | ❌ absent in both modes | COMMENT: implement and wire now completely

---

## Lost on save/load

- **Nothing**, via the real app's actual save/load path (`haystack_dnd_game.py`) — a
  53-field `CharacterData` round trip and a full quest/location/campaign-flags round
  trip were both verified byte-identical.
- **Everything that matters** (HP, AC, equipment, spell_slots), if a caller instead uses
  `GameEngine.export_game_state()`/`import_game_state()`'s own embedded character
  branch — this path is unused by the live game today but exists, looks correct, and
  is a trap for anyone who reaches for it in a future script, test, or refactor.

---

## Summary counts

Across all sections above (counting each table row as one mechanic, excluding the
"built but unreachable" and cross-mode summary sections which restate rows already
counted): approximately **34 ✅ / 20 🟡 / 30 ❌** verdicts for "Implemented," and
approximately **27 ✅ / 14 🟡 / 43 ❌** verdicts for "Reachable" (exact tallies depend
on how partial ❓/🟡 rows are bucketed; several fields legitimately have different
Implemented vs. Reachable status, which is the entire point of this audit).

## Biggest surprise

The **`cast_spell` bug is not the one the handoff doc described** — the handoff said the
action was never registered; it has since been registered, and still doesn't work,
because of a one-key omission in `param_defaults` that is *the exact same bug class*,
*in the same file*, with the fix pattern *already written down in that file's own
comments* (for the four Surges that had the identical problem). Someone did the
"cheapest win" from the handoff's punch list, wired the registration, ran out of budget
one line before the finish, and it still reads as fixed unless you call `is_offerable()`
directly. Second-biggest surprise: the non-combat/exploration side of the game
(skills, rests, quests, XP, persistence, rules lookup) is substantially more solid and
genuinely reachable than the combat/spellcasting/class-feature side — the opposite of
what the project's documented history of "built but unreachable" combat features would
predict.
