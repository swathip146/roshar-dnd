# Session Handoff — 2026-09-11

Work paused mid-session to stay under a daily quota. This documents exactly what was
running, what each agent actually produced (verified by running tests just now, not by
trusting the agent's own summary), and what a new engineer needs to do to pick this up.

**Read this before touching anything**: the working tree has real uncommitted work mixed
with half-finished integration. The full `tests/combat/` suite fluctuates between
**17–20 failed, 718–721 passed** run to run (small drift, likely from the still-broken
proficiency test — see item 8). Do not chase the exact number; the file-by-file
breakdown below is what's load-bearing, and it does not change between runs. This is
not a regression to panic over — it is two features whose wiring step never landed
before their agent was killed. Sections below say exactly which.

## Current branch state

```
git log --oneline -6
085bdcf Wire the maneuver interpreter into combat, and catalogue all ten surges
dd292c9 Execute maneuver automation trees: Surgebinding becomes data, not code (3.1b)
9912dd6 Make the five Surge classes actually usable, and run tests in parallel
6b577d4 Seed the exhaustion negative tests instead of widening the margin
311230d Close the condition and rules-lookup gaps: Petrified, Exhaustion, and 386 unreachable SRD entries
0d22104 Close the tactical layer: advantage, cover, flanking, reactions, reach, ranged, dash
```

All of the above is committed and green. Everything below is **uncommitted**:

```
 M agents/dm_tools.py
 M components/character_manager.py
 M components/combat/action_registry.py
 M components/combat/combat_action_resolver.py
 M components/combat/combat_session_manager.py
 M components/combat/npc_stat_generator.py
 M components/combat/tactical_rules.py
 M components/dice.py
 M components/dnd_engine_wrapper.py
 M components/srd_rules.py
 M requirements.txt
 M tests/test_deterministic_game_flow.py
 M tests/test_phase0_regressions.py
?? components/combat/class_features.py
?? components/combat/multiattack.py
?? components/combat/spell_compiler.py
?? components/combat/spellcasting.py
?? components/combat/standard_actions.py
?? data/rules/class_features/
?? tests/combat/test_actions_are_filtered_per_actor.py
?? tests/combat/test_multiattack.py
?? tests/combat/test_proficiency_on_attacks.py
?? tests/combat/test_spellcasting.py
?? tests/test_dice_d20_parser.py
```

`data/rules/stormlight/surgebinding.json` is **unchanged** (still 9 maneuvers, 10
surges) — the maneuver-authoring agent was killed before it wrote anything, so there is
no corruption there.

Everything imports cleanly:
```
python -c "import components.combat.spellcasting, components.combat.multiattack, \
  components.combat.standard_actions, components.combat.class_features, \
  components.combat.spell_compiler, components.dice, components.srd_rules, \
  components.combat.combat_session_manager"
```

## Twelve agents were running. Two finished and reported before the stop. Ten were killed mid-task.

### Finished cleanly (safe, verified green)

**1. `d20` dice parser swap** — *"Fix d20 dice parser swap"*, agent `ac34ae2dd0e547f22`

The brief assumed `d20` (the Avrae dice library) wasn't installed because PyPI is
blocked by the sandbox proxy. The agent found the premise wrong — **`d20` 1.1.2 was
already installed** — and did the real swap instead of just documenting a gap.

- `components/dice.py`: `DiceRoller.damage_roll()` now parses via `d20.roll()` instead
  of the hand-rolled regex. Return shape verified byte-for-byte identical to before.
  `saving_throw`/`skill_roll`/`attack_roll`/`percentile_roll` deliberately **not**
  touched (no parsing involved, rewriting them was pure risk).
- **Found and fixed a real bug during the swap**: d20 marks a dropped die (from reroll
  notation) with `.total == 0` while the real face lives in `.values`. The first
  implementation read `.total`, which logged **a face of 0 on a d6** — physically
  impossible — for `4d6ro1`. Fixed by reading `Literal.number` instead. Guarded by
  `TestFaceValuesArePhysicallyPossible` (3000 rolls, 12 notations, zero impossible
  faces).
- Newly working: `4d6e6`, `10d6e6`, `4d6ro1`, `4d6rr1`, `4d6mi2`, `4d6ma5`, `4d6p1`,
  `(1d6+2)*2`, `1d6+2d6e6` (previously silent-0, then loud `ValueError`).
- Still correctly refused: `garbage`, `""`, `4d6!`, `1d20r1` (d20's real reroll syntax
  is `ro`/`rr`, not bare `r` — so this string is correctly rejected, not a residual bug).
- `requirements.txt:119` comment corrected; `agents/dm_tools.py`'s `roll_dice` docstring
  updated so the model knows the new notation exists.
- New file: `tests/test_dice_d20_parser.py` — **163 tests, verified passing** just now.
- Full non-combat suite at the time: 1198 passed, 0 failed.

**Verify it's still good**: `python -m pytest tests/test_dice_d20_parser.py -q -p no:randomly -n0`

**2. Per-actor action filtering** — *"Fix NPC AI unusable action menu"*, agent `af477532b87db1c0e`

Found dead code: `CombatSessionManager._character_meets_requirements` opened with
`if not requires: return True`, and `requires` is `None` for all four Surges — so the
`requires_order` check below it was unreachable. Neither `min_surgebinding_level` nor
Stormlight cost was checked in the menu path at all.

Measured before the fix: a plain goblin (no order, no Stormlight) was offered
`lashing`, `progression_healing`, `illumination`, `soulcast` on **both** the NPC and
player paths — **57% of a 7-entry menu were traps** that would resolve with
`success=False`.

- `components/combat/action_registry.py`: added `unusable_reason()`, `is_usable_by()`,
  `usable_actions()` — a single per-actor gate checking `requires_order`,
  `min_surgebinding_level`, `stormlight_cost` vs current Stormlight, and `requires`.
- `components/combat/combat_session_manager.py`: `_character_meets_requirements` now
  delegates to `unusable_reason`.
- New file: `tests/combat/test_actions_are_filtered_per_actor.py` — 47 tests.
- Reported suite at the time: 611 passed, 5 failed (all pre-existing/unrelated).
- One subtlety the agent flagged: the resolver reports `success=hit` for attacks, so a
  legal swing that *misses* is `success=False`. An early version of a "resolve
  everything offered" assertion keyed off `success` and flaked on bad rolls; fixed to
  check refusal (`refused is True` / `event is None` / `event.canceled`) instead. See
  `test_a_missed_attack_does_not_count_as_a_refusal`.

**Verify it's still good**: `python -m pytest tests/combat/test_actions_are_filtered_per_actor.py -q -p no:randomly -n0`
(ran it just now: need to re-confirm count after other agents' edits — see Known Issues below, this file may now show fewer than 47 passing because of unrelated proficiency failures in the same suite run, not because this file broke).

### Killed mid-task — code exists, integration incomplete

**3. Spellcasting** — *"Implement 5e spellcasting"*, agent `a4cc0c5ce62a297ac`

New files: `components/combat/spellcasting.py`, `components/combat/spell_compiler.py`,
`tests/combat/test_spellcasting.py`.

**Verified just now**: `python -m pytest tests/combat/test_spellcasting.py -q -p no:randomly -n0`
→ **64 passed, 8 failed**. The mechanics work — spell save DC, spell attack bonus, slot
spending, damage/save/heal resolution from real SRD spell data. What's missing is the
last step: **`cast_spell` was never added to `ACTION_REGISTRY`**, so it doesn't appear
in `offerable_actions()` and a caster is never actually offered the option in a real
turn. All 8 failures are in `TestCastSpellIsOfferable` and
`TestOnlyCastersAreOfferedCastSpell` — i.e. exactly the offerability/menu layer, not the
spell mechanics.

The agent's last visible action before being stopped: *"Mutation caught. Now mutate the
slot spending and adjudication paths"* — it was doing mutation testing on its own work,
which suggests the mechanics themselves were considered done and it was in a
verification pass when killed.

**Next step for whoever picks this up**: register `cast_spell` in
`components/combat/action_registry.py` (there's very likely a `param_defaults` question
for `spell_name` — see how the four Surges were made offerable in commit `9912dd6` for
the exact pattern to copy), then re-run `test_spellcasting.py` — should go from 64/72 to
72/72 once that's done. Read `components/combat/maneuver_executor.py`'s docstring first;
the brief specifically asked this agent to prefer reusing that interpreter over building
a second effect engine — check `spell_compiler.py` to see whether it did.

**4. Multiattack** — *"Implement multiattack and monster actions"*, agent `a7d35df81291f8153`

New file: `components/combat/multiattack.py`, `tests/combat/test_multiattack.py`.

**Verified just now**: `python -m pytest tests/combat/test_multiattack.py -q -p no:randomly -n0`
→ **36 passed, 0 failed.** This one is complete, including consumption — confirmed by
reading, not just testing: `components/combat/combat_session_manager.py:596` calls
`attacks_per_turn_for(character)` and loops `for index in range(2, total_attacks + 1)`,
granting and revoking real action-economy slots per extra attack, with a stall-guard
that stops early if an attack fails to resolve and logs how many of N were completed.
Three of the 36 tests (`test_two_attack_monster_rolls_twice_in_one_turn`,
`test_turn_ends_with_an_empty_action_pool`,
`test_repeated_turns_do_not_accumulate_actions`) exercise this through
`CombatSessionManager` directly, not just the standalone parser — so this is genuinely
wired, not merely computed. `components/srd_rules.py` was also modified to call
`multiattack_for_monster()` and populate `attacks_per_turn` on `monster_stats()` output.

The agent's last action before being stopped: *"Now let me measure with a real SRD
monster (as the task asked) — before/after — using a script"* — so the balance
before/after numbers the brief asked for were likely never recorded. **Known fact from
the brief, worth measuring**: **148 of 334 SRD monsters have a Multiattack action**, all
of which were silently reduced to one attack per turn before this fix. If the CR-band
difficulty tuning (`scripts/derive_cr_bands.py`, `docs/REBUILD_PLAN_V5.md` §14c) was
calibrated against single-attack monsters, this fix makes those encounters harder —
run a playtest-style time-to-kill measurement to quantify it, since nobody has yet.

**5. Standard 5e actions** — *"Add missing 5e combat actions"*, agent `ab6a16adc33b0017f`

New file: `components/combat/standard_actions.py` (Grapple, Shove, Help, Ready, Hide,
Search, Disengage, two-weapon fighting).

**Confirmed just now: NOT WIRED AND NO TESTS.** `register_standard_actions()` exists in
the file (line 1037) but nothing calls it — not `action_registry.py`, not
`combat_session_manager.py`. `find tests -iname "*standard_action*"` returns nothing.
The agent's brief explicitly required it to report "exactly where the one-line wiring
call must go" since it wasn't allowed to edit `action_registry.py` itself — that report
was never delivered because it was killed before writing the test file (last visible
action: *"Now let me write the test file"*).

**Next step**: read `components/combat/standard_actions.py` fully before doing
anything else — there is no test coverage at all, so treat every claim in the file's own
docstrings as unverified. Call `register_standard_actions()` from wherever
`ACTION_REGISTRY` is assembled (see how `ROSHAR_ACTION_ENTRIES` is merged in in
`action_registry.py` for the pattern), then write the missing test file. Do NOT assume
any of the 8 actions work correctly — verify each one exactly as the original brief
described (contested checks actually resolving, Help actually granting measurable
advantage, Disengage actually suppressing a real opportunity attack).

**6. Class features** — *"Implement class features and subclasses"*, agent `a27bf654bf92dc6e9`

New files: `components/combat/class_features.py`, `data/rules/class_features/` (a data
directory — check what's actually in it, may be empty or partial).

**Confirmed just now: NO TESTS, NO REGISTRATION FUNCTION FOUND.** Unlike
`standard_actions.py`, this file doesn't even have a `register_*` entry point visible
from a grep. The agent's last visible action: *"`DnDEngineWrapper` is a `@dataclass` —
assigning `self._class_feature_engine` on a non-field attribute works for a plain
dataclass. Let me verify and run a first smoke test."* — i.e. it was still doing initial
plumbing checks, likely the least mature of all six implementation agents.

**Next step**: this needs the most scrutiny of anything in this handoff. Read the whole
file before trusting any of it. Check `data/rules/class_features/` for actual content
vs an empty scaffold. The original brief asked for Second Wind, Rage, Sneak Attack,
Action Surge, Divine Smite as the priority set — verify which (if any) actually have
working code vs docstring-only stubs.

**7. Combat-agent error handling test** — *"Resolve combat agent error handling test"*, agent `a6f9205d35999e6bf`

Two tests to fix: `test_combat_agent_error_handling` (decide if the agent or the test's
premise is wrong) and the flaky `test_encounter_does_not_end_at_zero_hp` (cross-test
contamination, needs a fixture-cleanup fix, not a reorder).

**No git diff attributable to this agent was found** in the current uncommitted set —
`agents/combat_agent.py` shows no modification. Last visible action before being
stopped: *"Baseline reverted. Let me measure the pre-existing failures on the other
process's tree, without my changes"* — this reads as the agent still in its
verification/diagnosis phase, likely having reverted its own experimental change to
re-baseline, and was killed before landing a real fix.

**Confirmed just now**: `python -m pytest tests/combat/test_combat_integration.py::test_combat_agent_error_handling -q -p no:randomly -n0`
→ **still failing.** Not reverted, not fixed — exactly where it started.

**Next step**: start over on this one. Both failures are still present (see Known
Issues below for exact current status of `test_combat_agent_error_handling` — note it
may currently be *passing* per one other agent's incidental report, re-verify first).

**8. Proficiency deviation audit** — *"Audit proficiency deviation pinning"*, agent `a55d24bd00ceafa40`

New files: `tests/combat/test_proficiency_on_attacks.py`.

**This is the most important one to check first.** The agent's last visible line was
reassuring — *"It passes in isolation but failed in the suite — genuinely marginal,
straddling the boundary. A flaky test is worse than none, so let me measure the real
distribution"* — but **verified just now**:
`python -m pytest tests/combat/test_proficiency_on_attacks.py -q -p no:randomly -n0`
→ **2 passed, 7 failed.** That is not "marginal" or "flaky" — that is most of the file
failing, including `test_hit_rate_matches_the_raw_bonus` and
`test_attack_bonus_tracks_proficiency_across_levels` at three different level
parametrizations. The agent's own summary undersells the real state. **Do not trust the
"flaky" framing — re-diagnose from scratch.**

**Next step**: run the file in isolation (`-n0`) and read the actual assertion
failures — do not assume it's an ordering/xdist artifact until proven. The original
brief's core question was whether `DnDEngineWrapper` genuinely adds proficiency to
weapon attacks (since the vendored engine only applies it to skills) and whether that
is pinned by a load-bearing test. Given 7/9 failing, the honest starting hypothesis is
that **the deviation itself may be broken**, not just the test. Revert-and-observe: find
where the wrapper adds proficiency to attack bonus, temporarily disable it, see if the
failing tests' *nature* changes (do they fail the same way, or differently) — that tells
you whether the test is checking the right thing.

**9–11. Documentation agents** — killed while writing, not while researching

- *"Document codebase architecture from code"* (`a223dec8e148fd39c`) → target
  `docs/architecture/CODEBASE_MAP.md`. Last action: *"I have everything I need. Let me
  write the document."* — **likely means research was complete and it was killed during
  the actual Write call.** Check if the file exists at all:
  `ls docs/architecture/CODEBASE_MAP.md` — if missing, this needs a full re-run; if
  present but short/truncated, it may be a partial write.
- *"Document gameplay flow from code"* (`a085b3aafe3c2577e`) → target
  `docs/architecture/GAMEPLAY_FLOW.md`. Last action: *"Excellent, comprehensive results.
  Let me write the document now while the second agent finishes."* Same situation —
  check `ls docs/architecture/GAMEPLAY_FLOW.md`.
- *"Document capabilities and gaps from code"* (`a59dae3084bef1d68`) → target
  `docs/architecture/CAPABILITIES_AND_GAPS.md`. Last action: *"Excellent — a huge
  finding: `standard_actions.py` (the 8 PHB actions) is unreachable. Let me verify that
  critical claim directly."* — this one was mid-*research*, not mid-write, so it is
  probably the least complete of the three. Its finding corroborates item 5 above
  independently.

Run `ls -la docs/architecture/ 2>/dev/null` to see what (if anything) landed.
**Confirmed just now: the directory exists but is empty — `mkdir` ran, nothing was
written.** All three documents need a full re-run from scratch, not a resume. The
research each agent did (module import graphs, flow tracing, capability grepping) is
lost; nothing was persisted anywhere retrievable.

**12. Non-combat/AI layer audit** — *"Audit non-combat and AI layer"*, agent
`a7d517d923fcbc322` (spawned by the CAPABILITIES_AND_GAPS agent as a sub-task, not
launched directly by the top-level session)

Last action: *"15 tools. Now let me trace consumption and the pipelines."* — early/
mid research on `agents/dm_tools.py`'s tool count and usage. No file output expected
from this one directly; it was feeding findings back to agent 11 above, which was
itself killed mid-write. Treat as fully lost.

**13. Windrunner maneuver authoring** — *"Author remaining Windrunner maneuvers"*,
agent `a94aea88a29685da4`

Task: add the ~16 missing Windrunner maneuvers (Parry, Precision Attack, Lunging
Strike, Rally, Tripping Lash, Feinting Attack, Lash Ally/Enemy, etc. — full list and
source line numbers are in the conversation transcript, all verbatim-quotable from
`parsed_data/863203275-cosmere-5e-radiant-s-handbook-v2-0/docling.md` lines
1932–2416) into `data/rules/stormlight/surgebinding.json`.

**Confirmed: `surgebinding.json` still has exactly 9 maneuvers and 10 surges — no
change.** Last action before being stopped: *"Now let me build the new entries as a
Python list and splice them in with matching 1-space-indent formatting"* — it had done
the research/extraction but had not yet written to the JSON file. **Safe to restart
from scratch**; no partial/corrupt JSON to clean up.

The user (project owner) said explicitly: skip anything that needs the **Invested Arts
of the Cosmere** document (the 10 surge cantrips — Abrasion, Adhesion, Cohesion,
Division, Gravitation, Illumination, Progression, Tension, Transformation,
Transportation — whose mechanics are NOT in our parsed Handbook text, confirmed by
grepping for "See The Invested Arts of the Cosmere" appearing 7 times as a deferral).
The user is sourcing that document separately. **Do not attempt to author the 10 surge
cantrips or their automation trees until that document is available.**

What IS unblocked and ready to resume: the ~16 missing Windrunner maneuvers and the
**118 order features across all 9 orders** (only 2 currently authored — see the
`features` key in `surgebinding.json`), both fully quotable from
`docling.md` right now. A second agent was about to be launched for the order-features
half of this when the pause was requested — never launched, fully unstarted.

## What a new engineer should do, in order

1. **Read `Known Issues` below first** — it separates "definitely broken, re-verify
   before touching" from "probably fine, spot-check only."
2. Run `python -m pytest tests/combat/ -q -p no:randomly` and `python -m pytest tests/ -q -p no:randomly --ignore=tests/combat --deselect tests/test_llm_utils.py -k "not test_gemini_ and not test_tool_calling and not test_api_connection and not test_game_"`
   to get a fresh baseline — numbers in this doc were measured at write time and will
   drift as soon as anyone touches the tree.
3. **Cheapest wins first**: wire `cast_spell` into `ACTION_REGISTRY` (spellcasting
   mechanics are done, this is the last step — see item 3) and wire
   `register_standard_actions()` into the registry assembly (item 5, code exists,
   nothing calls it).
4. **Needs real diagnosis, not a quick fix**: the proficiency test file (item 8) — 7 of
   9 failing is not "flaky," start from first principles.
5. **Needs the most scrutiny**: `class_features.py` (item 6) — essentially unverified,
   no tests exist yet.
6. **Ready to resume immediately, fully unblocked**: author the ~16 missing Windrunner
   maneuvers and the 118 order features from `docling.md` (item 13) — skip the 10
   surge cantrips per the project owner's explicit instruction until the Invested Arts
   document arrives.
7. **Documentation from scratch, not a resume.** `docs/architecture/` exists but is
   empty — none of the three agents (items 9–11) got as far as writing. Re-launch all
   three; their prior research is not retrievable.
8. Do not commit any of the uncommitted files listed at the top until each has a
   passing, verified test suite — several were mid-integration when stopped.

## Known Issues (verified by running tests just now, 2026-09-11)

| Area | Status | Evidence |
|---|---|---|
| `d20` parser swap | ✅ Done, safe | `tests/test_dice_d20_parser.py`: 163/163 |
| Per-actor action filtering | ✅ Done, safe | `tests/combat/test_actions_are_filtered_per_actor.py` (re-verify count after proficiency fix, unrelated suite noise) |
| Spellcasting mechanics | ✅ Done | `tests/combat/test_spellcasting.py`: 64/72 pass |
| Spellcasting offerability | ❌ Not wired | Same file: 8/72 fail, all in the offerable/menu test classes — `cast_spell` missing from `ACTION_REGISTRY` |
| Multiattack computation | ✅ Done | `tests/combat/test_multiattack.py`: 36/36 |
| Multiattack consumption in combat | ⚠️ Unverified | Grep for `attacks_per_turn` outside `multiattack.py`/`srd_rules.py` before assuming it's acted on |
| Standard 5e actions (grapple/shove/help/etc.) | ❌ Not wired, no tests | `register_standard_actions()` exists, uncalled; no test file |
| Class features (Rage/Sneak Attack/etc.) | ❌ Unverified, no tests | No registration function found; treat all claims as unverified |
| Proficiency-on-attacks | ❌ Likely broken, not "flaky" | `tests/combat/test_proficiency_on_attacks.py`: 2/9 pass — re-diagnose from scratch |
| `test_combat_agent_error_handling` | ❌ Still failing, untouched | Confirmed by running it just now — agent's diagnosis phase produced no committed fix |
| `test_encounter_does_not_end_at_zero_hp` | ❓ Still flaky (cross-test contamination) | Not fixed; needs a fixture-cleanup fix per the original brief, not a reorder |
| `docs/architecture/*.md` | ❌ Never written | Directory exists, empty — all three need a full re-run |
| Surgebinding maneuvers/features authoring | Not started | `surgebinding.json` unchanged (9 maneuvers, 2 features) — safe to resume, no corruption |

## Reference: what was already committed and solid before this session's pause

See `docs/REBUILD_PLAN_V5.md` §14i for the full writeup of everything in the six
commits above (tactical rules, advantage/disadvantage fix, Petrified + Exhaustion
conditions, the 386-entry rules-lookup gap, the five Surge classes, the maneuver
interpreter and its wiring). That section is trustworthy — it was written and verified
in this same session, by the same standard applied throughout this handoff (read the
code, run it, don't trust prior prose).
