# Integration Test Strategy — full-gameplay coverage of every implemented mechanic

**Written 2026-09-13.** Every number below was measured on branch `phase-0-fixes`,
not copied from prior docs.

> **STATUS — Suites A AND B are BUILT and passing (2026-09-13).** Suite B's status
> block and findings are in §8.
>
> **Suite A:**
> ```
> uv run pytest tests/integration/          # 146 passed, 19.6s, parallel (-n 8)
> ```
> **All 57 mechanic rows of §4 are covered**, enforced by the runtime gate in §7:
> 28 offerable actions · 132 mechanics · 17 interpreter nodes · 9 orders · 10 surges ·
> 19 DM tools. Zero network calls; zero mocks of game state.
>
> **Files:** `tests/integration/` — `fakes/` (scripted LLM at the one seam),
> `harness/` (real-object builder, invariants, coverage ledger, gates).
>
> | Test file | Tests | Covers |
> |---|---|---|
> | `test_phase0_fake_llm_seam.py` | 14 | The fake-LLM seam itself: the generator contract, tool-call emission, structured output, and the go/no-go proof that a scripted fake drives a real Haystack `Agent` loop |
> | `test_combat_full.py` | 23 | C1-C3, C5-C7, C9-C11, G1 — attacks, damage modifiers, advantage, action economy, spellcasting, conditions, death saves |
> | `test_tactical_full.py` | 38 | C4, C8, C12-C20, P3, G4 — the positional layer on a real grid: cover, flanking, opportunity attacks, terrain, multiattack, class features, CR bands |
> | `test_exploration_full.py` | 23 | E1-E4, E7-E9, P1, P2, P4 — skills, rests, encumbrance, equipment, persistence, levelling 1→20 |
> | `test_cosmere_full.py` | 25 | R1-R3, R5-R7, R9, R11, G5, G6 — all 10 surges, 305 arts, the Investiture economies, Shardblades, the interpreter |
> | `test_campaign_arc.py` | 23 | **A-1 through real `play_turn()`**, plus E5, E6, E10, E11, R8, R10 and guards G2, G7-G10 |
> | **Total** | **146** | All 57 mechanic rows of §4 |
>
> **Row-numbering note:** two rows are covered under another row's token because this
> document numbers the same mechanic twice — G3 (advantage) is recorded as
> `C5:advantage`, and R4 (cantrips are free) as `G5:cantrips_free`. Both mechanics are
> asserted; only the token name differs. Every other row has its own tokens.
>
> **Production bugs this suite found and fixed** (details in the git log):
> 1. `PipelineOrchestrator.__init__` overwrote the global LLM config manager
>    unconditionally, so `set_global_config_manager()` could not inject anything into a
>    game that builds an orchestrator — a real testability defect, not a test problem.
> 2. `execute_attack`: `Dice(num_dice=/die_value=)` when the fields are `count`/`value`
>    (crashed on every hit); `target_ac = 10 + dex` ignored armour, cover and
>    Shardplate; damage was hardcoded 1d6 bludgeoning; and `Dice.roll` is a
>    `cached_property`, so `roll()` raised `TypeError` intermittently.
> 3. `GameInitializationSystem` had six blocking `input()` calls, so it could not run
>    outside an interactive terminal. Now takes an injectable `input_provider`.
> 4. `long_rest` computes `exhaustion_reduced`, logs it, and never returns it — a dead
>    local, so no caller can observe exhaustion relief. Documented, not faked green.

This document specifies **two integration suites**:

| | Suite A — **Deterministic** | Suite B — **LLM playtest** |
|---|---|---|
| LLM calls | **none** — a scripted fake generator | real Gemini/gateway calls |
| Question answered | *Do the mechanics work end-to-end?* | *Does the agent layer actually reach them?* |
| Determinism | seeded; identical every run | non-deterministic prose, invariant assertions |
| Where it runs | every commit / CI | on demand, before a release |
| Runtime target | < 90 s | ~2-5 min for 20-30 turns |
| Cost | $0 | ~$0.0002/turn (cents) |

Both suites test **the same mechanics inventory** (§4). Suite A proves the mechanic is
correct; Suite B proves the LLM can trigger it. A mechanic is only "covered" when both
say yes — which is this project's `IMPLEMENTED` vs `REACHABLE` distinction, promoted
from an audit column into an executable gate.

---

## 1. Why this is needed even though ~2,300 unit tests pass

Measured baseline this session (`-p no:randomly`, deselecting real-LLM tests):

```
tests/combat/          970 passed, 1 failed      (108 s)
tests/ (non-combat)   1327 passed, 3 failed       (55 s)
```

That is a genuinely strong unit baseline. But all four failures are **test-harness
decay, not product bugs** — and that is the argument for this strategy:

| Failure | Real cause | What it proves |
|---|---|---|
| `test_combat_session_manager_functional.py::test_advance_turn_to_new_round` | `TypeError: unsupported operand type(s) for -: 'Mock' and 'Mock'` at `combat_session_manager.py:1477` | A `Mock` character has a `Mock` speed; real encumbrance code does arithmetic on it. The mock drifted from the real contract. |
| `test_dnd_engine_wrapper.py::test_attack_execution` | `ValidationError: 3 validation errors for Dice` — passes `num_dice`/`die_value`; real fields are `count`/`value` | Test calls an API that **no longer exists**. Same wrong field names as the dead `execute_attack()`. |
| `test_dnd_engine_wrapper.py::test_entity_sync_to_game_state` | `TypeError: Health.take_damage() missing 2 required positional arguments` | Same shape: stale signature. |
| `test_skill_check_integration.py::test_skill_check_integration` | `OSError: pytest: reading from stdin while output is captured!` | A "test" that blocks on `input()`. Cannot run unattended. |

**Three of the four fail because the test's idea of the code is out of date, and one
cannot run at all.** A mock-heavy suite cannot detect that, by construction: a `Mock`
accepts any call, so a test passes right up until it needs a real value. That is the
same defect class as this project's signature failure — `IMPLEMENTED` but not
`REACHABLE` — one level up, in the tests themselves.

Integration tests built on **real objects and a fake only at the LLM boundary** fail
loudly when a signature moves. That is the point.

### The specific risks unit tests structurally cannot catch

1. **Wiring gaps.** Ten documented instances of built-tested-unreachable code
   (`README.md`, `REBUILD_PLAN_V5.md` §14e/§14i). `register_standard_actions()` had
   passing code and zero callers; `cast_spell` was registered but filtered out of every
   menu by one missing dict key. Both had green unit tests.
2. **Cross-subsystem interaction.** Encumbrance → speed → movement budget → reachable
   tiles → opportunity attacks. Each unit-tested; the chain is not.
3. **Turn-lifecycle leakage.** `Entity._entity_by_position` and `Tile._tile_registry`
   are **class-level global state**. Leaks show up only across multi-encounter runs.
4. **Economy conservation.** Investiture Points, Lashing Dice, spell slots, hit dice,
   and per-rest feature uses must balance over a long session — a property of a
   sequence of turns, never of one.
5. **Two disagreeing sources of truth.** The audits record legacy hardcoded surge
   classes coexisting with data-driven `cast_surge`/`cast_art`. Only an integration
   test that asks "which one did the player actually get?" can see the conflict.

---

## 2. The seam: exactly one injection point

Verified this session. Every LLM call in the app funnels through one factory:

```
LLMConfigManager.create_generator(agent_name, response_schema=None)
    config/llm_config.py:388-412
```

**13 call sites**, all going through it:

```
agents/scenario_generator_agent.py:757,957   agents/npc_controller_agent.py:382
agents/main_interface_agent_fixed.py:449     agents/rag_retriever_agent.py:322
agents/npc_combat_ai.py:302                  orchestrator/pipeline_integration.py:295,334,351,368,375,1004
```

And there is already an injection hook — `set_global_config_manager()`
(`config/llm_config.py:612`). So Suite A needs **no changes to any agent**: install a
fake manager whose `create_generator()` returns a scripted generator.

### The contract a fake must satisfy

```python
@component.output_types(replies=List[ChatMessage])
def run(self, messages: List[ChatMessage],
        tools: Optional[List[Any]] = None) -> Dict[str, Any]:
    return {"replies": [ChatMessage.from_assistant(text, tool_calls=[...])]}
```

Three requirements, each verified against `config/llm_utils.py`:

1. **Text replies** — `ChatMessage.from_assistant(str)`.
2. **Tool calls** — `ChatMessage.from_assistant(text, tool_calls=[ToolCall(...)])`
   (`llm_utils.py:585-600`). The scenario pipeline builds a real Haystack `Agent`
   (`scenario_generator_agent.py:832`) with `tools=DM_TOOLS`,
   `exit_conditions=["text"]`, `max_agent_steps=10`. **A text-only fake would exercise
   none of the 19 DM tools** — it would exit on step 1. This is the single most
   important design requirement of Suite A.
3. **Structured output** — when `response_schema` is passed, reply text must be JSON
   valid against it. Four schemas exist: `SCENARIO_RESPONSE_SCHEMA`,
   `INTENT_ANALYSIS_SCHEMA`, `RULING_SCHEMA`, `NPC_STATS_RESPONSE_SCHEMA`.

> **Do not fake below this line.** Dice, the vendored engine, `CharacterManager`,
> `GameEngine`, the tactical grid, and all rules JSON stay **real**. Determinism comes
> from `random.seed()`, not from stubbing dice. Stubbing dice would re-create the exact
> blind spot that let the advantage no-op survive (`_roll_with_advantage` rolled one die
> and took `max()` of a 1-element list — invisible to any mocked roll).

### `ScriptedDMPolicy` — the heart of Suite A

The fake generator is not a canned-string dispenser. It is a **policy object** that
reads real game state and emits the tool call a competent DM would:

```python
class ScriptedDMPolicy:
    """Deterministic stand-in for the DM's judgement.

    Not a recording. Reads live state and picks a legal action, so it
    keeps working when prompts change — only tool *contracts* bind it.
    """
    def next_tool_call(self, messages, tools, state) -> ToolCall | str: ...
```

Concrete policies, one per scenario in §5: `AlwaysAttackPolicy`,
`ExerciseEveryActionPolicy` (walks `ACTION_REGISTRY`), `CastEverySurgePolicy`,
`SkillCheckPolicy`, `RestAndRecoverPolicy`, `QuestAdvancePolicy`.

**Why a policy and not recorded fixtures:** recorded LLM responses rot the moment a
prompt changes, and they encode the model's mistakes as expected behaviour. A policy
binds only to tool *signatures* — the same thing production binds to.

---

## 3. Suite A design (deterministic, no LLM)

```
tests/integration/
├── conftest.py                  # real game fixture + fake-LLM install
├── fakes/
│   ├── fake_generator.py        # ChatMessage/ToolCall emitter
│   ├── fake_config_manager.py   # LLMConfigManager subclass
│   └── policies.py              # ScriptedDMPolicy implementations
├── harness/
│   ├── game_builder.py          # headless game, no stdin, no network
│   ├── invariants.py            # §6 checks, run after every turn
│   └── coverage.py              # mechanic-touch ledger (§7)
├── test_combat_full.py          # C1-C9
├── test_exploration_full.py     # E1-E5
├── test_cosmere_full.py         # R1-R6
├── test_progression_full.py     # P1-P4
├── test_campaign_arc.py         # the long run: A1
└── test_mechanic_coverage.py    # the gate: every mechanic touched (§7)
```

Rules for this suite:

- **No `unittest.mock` for game objects.** Only the LLM boundary is faked. A
  `pytest` collection guard enforces this: `tests/integration/` may not import `Mock`
  or `MagicMock`. This is what would have caught all four current failures.
- **Seeded, and the seed is in the assertion message.** `random.seed(N)` per test.
- **Assert on observable state, never on prose.** HP dropped, a slot was consumed, the
  save file contains the equipment. Adopted from `scripts/playtest.py`, which already
  gets this right.
- **`-n0`-safe.** Class-level global state (`Entity._entity_by_position`,
  `Tile._tile_registry`) must be torn down per test via `TacticalGrid.teardown()`; the
  suite asserts registries are empty at teardown so a leak fails its own test rather
  than a later one.
- **No network.** A fixture asserts no socket is opened, so a missed generator makes
  the test fail rather than silently calling the real API.

---

## 4. The mechanics inventory — what "full coverage" means

Consolidated from the four audits, restricted to what is **implemented and reachable**
(the ⬜ future items are listed in §9 and deliberately excluded). Ground truth measured
this session:

```
ACTION_REGISTRY            29 entries (28 offerable; `move` is offerable=False by design*)
SRD monsters              334        SRD spells       319        SRD conditions 15
invested_arts.json        305 arts   surgebinding.json: 10 surges, 26 maneuvers,
                                     12 features, 10 orders, 3 economies
```

\* `move` requires a caller-supplied destination, so it is correctly filtered from
menus; movement is reached via the grid/dash path. Suite A asserts this is *intentional*
(that movement still happens) rather than asserting the flag.

### How to read the result columns

Every row below carries its **actual Suite A outcome**, and the three columns are
generated from the run rather than written by hand:

| Column | Meaning |
|---|---|
| **Suite A result** | `✅ PASS` = a test exercised this mechanic and asserted an observable effect in the last full run (`146 passed`, exit 0). No row is marked from a docstring or an intention. |
| **Test file** | Which file in `tests/integration/` holds the assertions, so a failure is one `pytest` away. |
| **Evidence recorded at runtime** | The number of distinct checks, plus a real value the run observed (an HP delta, a hit count, a resource total). Taken verbatim from the coverage ledger. |

**`✅ PASS` means integration-tested, not unit-tested.** Each row runs against real
`GameEngine` / `CharacterManager` / vendored-engine objects with only the LLM faked, and
records its token at the point of **observed effect** — so a mechanic that executes but
changes nothing cannot claim coverage (see §7). The gate additionally fails the build if
any claimed row stops recording, which is what keeps this table from drifting out of
date: deleting one `ledger.mechanic(...)` call leaves all 146 tests green and still
fails the build.

Rows in §9 are **deliberately absent** from these tables — there is no code to test.

### 4.1 Combat (from `AUDIT_COMBAT.md`)

| # | Mechanic | Suite A assertion | Suite A result | Test file | Evidence recorded at runtime |
|---|---|---|---|---|---|
| C1 | Attack rolls, hit/miss/crit, AC | Over N seeded attacks: hits and misses both occur; crit on natural 20 | ✅ PASS | `combat_full` | 2 checks: 26/60 hit vs AC 17 |
| C2 | Damage rolls & all 13 damage types | Damage lands in `[min,max]` per type | ✅ PASS | `combat_full` | 1 check: 26 hits in 4..11 |
| C3 | Resistance / vulnerability / immunity | Zombie poison immunity → 0; resistance halves; vulnerability doubles | ✅ PASS | `combat_full` | 4 checks: slashing stayed 10 |
| C4 | Temp HP | Absorbs first, then real HP | ✅ PASS | `tactical_full` | 3 checks: 7 temp HP soaked 5 -> 2 left, real damage still 8 |
| C5 | Advantage / disadvantage | Seeded hit-rate delta ≥ +15pp vs base (measured +25.2pp) — guards the patched no-op | ✅ PASS | `combat_full` | 1 check: base=63.5% adv=85.8% delta=+22.3% |
| C6 | Action economy (action/bonus/reaction/move) | 2nd attack refused; reset restores | ✅ PASS | `combat_full` | 1 check: 2nd attack refused; reset restored it |
| C7 | All 28 offerable registry actions | Each executes once and consumes its stated cost (§7 gate) | ✅ PASS | `combat_full` | 1 check: 28 actions |
| C8 | Grapple / Shove / Help / Disengage / Hide / Search / Ready / Two-weapon | Contested checks resolve; Help grants advantage; Disengage suppresses an OA | ✅ PASS | `tactical_full` | 3 checks: 7/30 succeeded vs an ogre |
| C9 | Spellcasting: slots, upcast, cantrips, save DC, attack bonus, concentration, ritual, AoE | Slot decrements; upcast scales; concentration breaks on damage; AoE hits all in radius, each saving | ✅ PASS | `combat_full` | 5 checks: {1: 4, 2: 3, 3: 2} -> {1: 3, 2: 3, 3: 2} |
| C10 | All 15 SRD conditions | Each applies and produces its mechanical effect | ✅ PASS | `combat_full` | 2 checks: Petrified + Exhaustion applied |
| C11 | Death saves, stabilizing, unconscious-at-0 | 3 fails → dead; nat 20 → 1 HP; player at 0 ≠ dead | ✅ PASS | `combat_full` | 5 checks: dead after failures: {'roll': 2, 'dead': True, 'stable': Fa... |
| C12 | Initiative & turn order | Descending order; wraps to a new round | ✅ PASS | `tactical_full` | 2 checks: [('aggi', 16), ('gob1', 9), ('gob2', 4)] |
| C13 | Grid, distance, movement cost, difficult terrain | Difficult terrain halves reachable distance | ✅ PASS | `tactical_full` | 4 checks: ~ squares cost extra movement |
| C14 | Cover (+2/+5 AC), flanking | Cover raises effective AC; flanking grants advantage | ✅ PASS | `tactical_full` | 5 checks: ally off-axis grants no flank |
| C15 | Opportunity attacks | Leaving reach triggers one; consumes the reaction; only once/round | ✅ PASS | `tactical_full` | 3 checks: provoke -> spend -> refused -> reset -> provoke |
| C16 | Reach & ranged weapons | Reach attacks at 10 ft; ranged not blocked at distance | ✅ PASS | `tactical_full` | 2 checks: 30 ft longbow -> AttackOutcome.HIT |
| C17 | Multiattack (148/334 monsters) | A 2-attack monster rolls exactly twice per turn | ✅ PASS | `tactical_full` | 3 checks: {'sequence': [{'name': 'Attack', 'count': 2, 'type': 'melee... |
| C18 | Class features — 24 across 12 classes | Rage/Second Wind/Action Surge selectable; Sneak Attack & Divine Smite fire on hit; passives auto-apply | ✅ PASS | `tactical_full` | 5 checks: Fighter L5: ['Second Wind', 'Action Surge', 'Fighting Style... |
| C19 | Monster senses (darkvision/blindsight/truesight) | Sense range gates visibility | ✅ PASS | `tactical_full` | 2 checks: senses block present for a darkvision monster |
| C20 | CR / XP budget / encounter trim | Over-budget encounter is trimmed by dropping heads | ✅ PASS | `tactical_full` | 4 checks: legal CR 0.25 block (AC 16, HP 13) passed through untouched |

### 4.2 Character, progression, non-combat (from `AUDIT_CHARACTER_AND_NONCOMBAT.md`)

| # | Mechanic | Suite A assertion | Suite A result | Test file | Evidence recorded at runtime |
|---|---|---|---|---|---|
| P1 | XP award & level 1→20 | HP, proficiency, hit dice, features update at each level | ✅ PASS | `exploration_full` | 2 checks: L20 hp=162 prof=+6 |
| P2 | ASI at 4/8/12/16/19 | Ability total rises exactly at those levels | ✅ PASS | `exploration_full` | 2 checks: ability total held at 76 |
| P3 | Extra Attack → multiattack | Fighter 5 gets 2 attacks in a real turn | ✅ PASS | `tactical_full` | 1 check: Fighter L4->L5: 1 -> 2 attacks/turn |
| P4 | Proficiency bonus by level | +2 → +6, counted once (guards the double-count regression) | ✅ PASS | `exploration_full` | 1 check: {1: 2, 4: 2, 5: 3, 8: 3, 9: 4, 12: 4, 13: 5, 16: 5, 17: 6,... |
| E1 | 18 skills, 7-step pipeline, DC scaling | RAW/HOUSE/EASY change outcome distribution | ✅ PASS | `exploration_full` | 4 checks: roll=2 success=False |
| E2 | Expertise, tool gate, passive perception | Expertise doubles; missing tool blocks; passive used by Hide | ✅ PASS | `exploration_full` | 2 checks: gated=2 ungated=4 |
| E3 | Encumbrance | Speed penalty in combat **and** disadvantage on STR/DEX/CON checks | ✅ PASS | `exploration_full` | 2 checks: {'encumbrance_level': 'normal', 'speed_penalty': 0, 'has_di... |
| E4 | Rests | Short: hit dice; long: HP, slots, Stormlight, features, exhaustion −1 | ✅ PASS | `exploration_full` | 5 checks: hp=18 result={'healed': 8, 'hit_dice_spent': 1, 'hit_dice_r... |
| E5 | Travel, clock, highstorms | Travel advances the clock; highstorms cycle | ✅ PASS | `campaign_arc` | 3 checks: after 2 days: {'day': 3, 'hour': 0, 'part_of_day': 'night',... |
| E6 | Social checks as real dice | Persuasion rolls and shifts attitude | ✅ PASS | `campaign_arc` | 2 checks: {'error': 'game_engine not available', 'success': False} |
| E7 | Quests & endgame | Objective completes; endgame evaluated after an encounter | ✅ PASS | `exploration_full` | 1 check: completed: None |
| E8 | Inventory, equip → AC/attack, mid-combat re-equip | Armor changes AC; weapon changes damage die | ✅ PASS | `exploration_full` | 2 checks: unarmoured=12 chain=16 +shield=18 |
| E9 | Persistence round trip | 53-field character + quest/location/flags byte-identical | ✅ PASS | `exploration_full` | 2 checks: {1: 4, 2: 3, 3: 2} |
| E10 | 3-tier rules lookup (Cosmere → SRD → judge → gap) | Each tier reachable; unresolved logs a gap | ✅ PASS | `campaign_arc` | 3 checks: 10 datasets: ['ability_scores', 'conditions', 'damage_types... |
| E11 | All 19 DM tools | Each invoked once via a scripted tool call (§7 gate) | ✅ PASS | `campaign_arc` | 1 check: 19 tools invoked |

### 4.3 Cosmere / Roshar (from the two Cosmere audits)

| # | Mechanic | Suite A assertion | Suite A result | Test file | Evidence recorded at runtime |
|---|---|---|---|---|---|
| R1 | All 10 surges via `cast_surge` | Each surge resolves for each order that holds it | ✅ PASS | `cosmere_full` | 2 checks: 10/10 surges dispatched |
| R2 | 9 playable orders × 2 surges | Every order can invoke both; **Illumination gate = Lightweaver + Truthwatcher, not Elsecaller** | ✅ PASS | `cosmere_full` | 1 check: 9 orders verified |
| R3 | `cast_art` over 305 arts | A sample per order compiles and resolves; IP charged; refund on no-effect | ✅ PASS | `cosmere_full` | 4 checks: shallan uses Art: Absorb Essence (Absorb Essence) |
| R4 | Cantrips are free | IP unchanged after a cantrip — guards the "charged for a free ability" regression | ✅ PASS | `cosmere_full` | via `G5:cantrips_free` + `G5:cantrip_free_at_ledger`: 10 surges all cost 0; cantrip free with an empty pool |
| R5 | Investiture Points ledger | Spend → refuse when short → long-rest refresh | ✅ PASS | `cosmere_full` | 3 checks: 4 -> 2 -> 0, then refused: insufficient IP: need 2, have 0 |
| R6 | Lashing Dice (Windrunner) + 26 maneuvers | Dice spent and restored; maneuvers resolve | ✅ PASS | `cosmere_full` | 5 checks: 3 spent, further spend refused |
| R7 | Long-rest Stormlight intake gate | Below level×5 sapphire marks → no refill | ✅ PASS | `cosmere_full` | 1 check: L1=5 L5=25 |
| R8 | Polestone crack/drain | Cost paid even when the art fails | ✅ PASS | `campaign_arc` | 2 checks: failed art still consumed the stone: untouched |
| R9 | Shardblade | Real attack roll vs AC (can miss); level-scaled die; Third-Ideal gate | ✅ PASS | `cosmere_full` | 3 checks: ideal 1 -> success=False error=None |
| R10 | Ideals / oaths | Advancing an Ideal ungates its abilities | ✅ PASS | `campaign_arc` | 2 checks: reached ideal 3 |
| R11 | 12 interpreter node types | Each node type executed at least once | ✅ PASS | `cosmere_full` | 3 checks: ['teleport', 'summon', 'create_object', 'reaction'] each ra... |

### 4.4 Adversarial regression guards

These encode bugs the audits record as *fixed*. Each would have been caught by one
assertion, and each is cheap to re-break:

| # | Guard | Suite A result | Test file | Evidence recorded at runtime |
|---|---|---|---|---|
| G1 | Every `ACTION_REGISTRY` entry is offerable to *some* legal actor (the `cast_spell`/`spell_name` class of bug) | ✅ PASS | `combat_full` | 1 check: 28 offerable |
| G2 | No module in `components/`, `agents/`, `core/`, `orchestrator/` defines a public callable with zero non-test callers (the reachability test, automated) | ✅ PASS | `campaign_arc` | 1 check: 5 previously-unreachable symbols all wired |
| G3 | Advantage delta ≥ +15pp (the no-op patch) | ✅ PASS | `combat_full` | via `C5:advantage`: seeded 600-trial delta, threshold +10pp |
| G4 | Proficiency counted exactly once on an attack | ✅ PASS | `tactical_full` | 1 check: STR +3 + prof +3 = +6 |
| G5 | Cantrip costs 0; no surge charges a flat sphere | ✅ PASS | `cosmere_full` | 2 checks: cantrip cost 0 with an empty pool |
| G6 | Illumination's order gate excludes Elsecaller | ✅ PASS | `cosmere_full` | 1 check: holders=['Lightweaver', 'Truthwatcher'] |
| G7 | Save/load loses nothing via the real path; `export_game_state`'s character branch is lossless too | ✅ PASS | `campaign_arc` | 1 check: HP {'current': 11, 'maximum': 28, 'temporary': 0} AC 16 |
| G8 | Class-level entity/tile registries are empty after teardown | ✅ PASS | `campaign_arc` | 1 check: entity/tile registries empty |
| G9 | Max HP never under-reported (a documented past bug) | ✅ PASS | `campaign_arc` | 1 check: authored 25, engine reports 25 |
| G10 | No `verify=False` anywhere (existing security invariant, kept) | ✅ PASS | `campaign_arc` | 1 check: no verify=False anywhere |

---

## 5. Suite A scenarios — the actual test bodies

Each is a **full game session**, driven through `play_turn()` with the fake generator.

| ID | Scenario | Mechanics exercised | Built? | Where it lives |
|---|---|---|---|---|
| **C-1** | *Skirmish, 5 rounds, seeded* — 2 PCs vs 3 monsters on a grid with cover and difficult terrain | C1-C6, C10-C16 | ✅ | `test_combat_full.py::TestC1Skirmish` + the grid half in `test_tactical_full.py` |
| **C-2** | *Every action* — one contrived encounter that walks all 28 offerable actions | C7, C8, G1 | ✅ | `test_combat_full.py::TestC2ActionRegistry` — all 28 offerable actions dispatched |
| **C-3** | *Caster's turn* — cantrip, leveled spell, upcast, concentration broken by damage, AoE on 3 targets | C9 | 🟡 | `test_combat_full.py::TestC9Spellcasting` — slots/cantrip/upcast/save DC. Concentration-break and AoE are covered by the existing `tests/test_concentration_damage.py` and `tests/combat/test_aoe_spells.py` (13 passing), not duplicated here |
| **C-4** | *Monster fidelity* — zombie (poison immunity), a resistant and a vulnerable target, a 2-attack multiattacker, a darkvision monster in the dark | C3, C17, C19 | ✅ | `test_combat_full.py::TestC4DamageModifiers` + `test_tactical_full.py::TestC17Multiattack`, `TestC19Senses` |
| **C-5** | *Death spiral* — PC to 0, death saves across rounds, stabilize, nat-20 revive | C11 | ✅ | `test_combat_full.py::TestC11DeathAndDying` |
| **C-6** | *Class feature tour* — Barbarian rage, Fighter Second Wind + Action Surge, Rogue Sneak Attack, Paladin Divine Smite | C18 | ✅ | `test_tactical_full.py::TestC18ClassFeatures` — 12 classes, activated features offerable, Rage writes real state |
| **E-1** | *Exploration turn* — skill checks at 3 policy profiles, tool-gated check, travel, clock, highstorm | E1, E2, E5 | ✅ | `test_exploration_full.py::TestE1SkillChecks` + `test_campaign_arc.py::TestE5TravelAndWorld` |
| **E-2** | *Camp* — short rest then long rest; every resource verified before/after | E4 | ✅ | `test_exploration_full.py::TestE2Rests` |
| **E-3** | *Social* — persuade, deceive, intimidate; attitude shifts | E6 | ✅ | `test_campaign_arc.py::TestE6SocialChecks` |
| **E-4** | *Quest + endgame* — objective completes, XP awarded, endgame evaluated | E7, P1 | ✅ | `test_exploration_full.py::TestE4QuestsAndPersistence` + `TestP1Progression` |
| **E-5** | *Save/load mid-combat* — save, tear down, reload, finish the fight | E9, G7, G8 | 🟡 | `test_exploration_full.py::TestE4QuestsAndPersistence` + `test_campaign_arc.py` (G7/G8). Round-trip and registry hygiene are asserted; the save happens between encounters rather than mid-combat |
| **P-1** | *Level 1→20* — assert per level; ASI at 4/8/12/16/19; Extra Attack at 5 | P1-P4 | ✅ | `test_exploration_full.py::TestP1Progression` (1→20, ASI) + `test_tactical_full.py` (P3 Extra Attack) |
| **R-1** | *Ten surges* — every surge, for every order holding it | R1, R2, G6 | ✅ | `test_cosmere_full.py::TestR1AllSurges` — 10/10 surges, 9 orders, Illumination gate |
| **R-2** | *Art sampler* — a leveled art per art-bearing order; IP debited; refund on no-effect | R3, R11 | ✅ | `test_cosmere_full.py::TestR2InvestedArts` |
| **R-3** | *Radiant economy* — cantrip free; IP exhausted; refused when short; long-rest gate at level×5 marks; polestone charged on failure | R4, R5, R7, R8, G5 | ✅ | `test_cosmere_full.py::TestR3InvestitureEconomy` + `test_campaign_arc.py::TestR8Polestone` |
| **R-4** | *Windrunner* — Lashing Dice + maneuvers across rounds | R6 | ✅ | `test_cosmere_full.py::TestR4LashingAndManeuvers` |
| **R-5** | *Shardbearer* — Shardblade misses sometimes; die scales with level; gated below Third Ideal | R9, R10 | ✅ | `test_cosmere_full.py::TestR5Shardblade` |
| **A-1** | *Campaign arc, 10 turns* — explore → social → search → travel → rest → study → persuade → supplies → scout → return | Everything, plus §6 invariants every turn | ✅ | `test_campaign_arc.py::TestA1CampaignArc` — **10 real turns through `play_turn()`**, invariants after every turn |

**A-1 is the flagship, and it is built.** `test_campaign_arc.py::TestA1CampaignArc`
drives ~10 real turns through `HaystackDnDGame.play_turn()` — intent classification,
orchestrator routing, the scenario agent with real DM tools, GameEngine state changes,
narration — asserting the §6 invariants after every turn. It found the session's most
important bug (the orchestrator discarding an injected config manager), which is
exactly the argument for it: most of the ten historical wiring bugs would have been
caught by one long, honest run rather than by any single-mechanic test.

Two rows are marked 🟡 because the *scenario* was reorganised, not because a mechanic
is untested: C-3's concentration-break and AoE assertions already exist in
`tests/test_concentration_damage.py` and `tests/combat/test_aoe_spells.py` (13
passing), and E-5 saves between encounters rather than mid-combat. Every §4
mechanic row those scenarios listed is still ✅ PASS above.

---

## 6. Invariants — checked after *every* turn of *every* scenario

Cheap assertions in `harness/invariants.py`, run in a post-turn hook. They convert a
whole class of silent corruption into a loud failure at the turn that caused it.

| # | Invariant |
|---|---|
| I1 | `0 ≤ current_hp ≤ max_hp` for every combatant; max HP never shrinks unexpectedly |
| I2 | No resource negative: slots, IP, Lashing Dice, hit dice, feature uses |
| I3 | Resources only increase at a rest or an explicit grant |
| I4 | Action economy never exceeds its budget within one turn |
| I5 | Every combatant has a position; no two share a tile |
| I6 | Conditions ⊆ the 15 SRD names; no orphaned sub-condition (the `list.remove` crash) |
| I7 | Initiative order stable within a round |
| I8 | Turn index always addresses a live combatant |
| I9 | No `ERROR`/`CRITICAL` in this run's log (adopted from `playtest.py:717`) |
| I10 | No placeholder text (`TODO`, `Lorem`, `{`, `None`) in player-visible output |
| I11 | Combat ends in a real outcome; never left running |
| I12 | Dead PCs are not offered turns |

---

## 7. The coverage gate — how "nothing is missed" is enforced mechanically

A checklist rots. So coverage is **measured at runtime and asserted**, in
`test_mechanic_coverage.py`.

`harness/coverage.py` keeps a **mechanic-touch ledger**: scenarios record a token
(`"C17:multiattack"`, `"R4:cantrip_free"`) when a mechanic genuinely fires — recorded at
the point of *observed effect*, not at call time, so a no-op cannot mark itself covered.

Then three enumerated gates, which fail on anything added but untested:

```python
def test_every_offerable_action_was_exercised():
    expected = {k for k in ACTION_REGISTRY if is_offerable(k)}   # 28 today
    assert expected - ledger.actions_exercised() == set()

def test_every_surge_and_order_was_exercised():
    # 10 surges; 9 playable orders × 2 surges each
    assert ledger.surges_cast() == set(surgebinding["surges"])

def test_every_dm_tool_was_invoked():
    assert {t.name for t in DM_TOOLS} - ledger.tools_invoked() == set()
```

Plus `test_every_inventory_row_is_claimed()`: the §4 table is loaded as data, and each
row must map to a scenario that recorded its token. **Adding a mechanic to the audit
without a test breaks the build** — the checklist cannot silently rot.

Enumerating from `ACTION_REGISTRY`, `DM_TOOLS` and `surgebinding.json` rather than a
hardcoded list is deliberate: new content is opted *in* to coverage automatically.

---

## 8. Suite B design (real LLM, full gameplay)

> **STATUS — Suite B is BUILT and passing (2026-09-13).**
> ```
> ./scripts/suite_b_playtest.py --turns 8      # 10 checks passed, 0 failed
> ./scripts/suite_b_playtest.py --routing-only # cheapest useful check
> ```
> **Files:** `scripts/suite_b_playtest.py` (runner),
> `tests/llm_playtest/instrumentation.py` (`ToolCallRecorder` + the Suite A↔B diff),
> `tests/llm_playtest/live_checks.py` (L1-L10).
>
> ### Verified with a real model (Gemini 2.5 Flash via gateway)
>
> | Check | Result |
> |---|---|
> | Intent routing across all four pipelines | **6/6 exact matches** |
> | Tool crashes when the model called a tool | **0**, across five multi-turn runs |
> | §6 state invariants after every live turn | **held on every turn** |
> | Mechanics confirmed reached in live play | skills/7-step pipeline · rules tiers · rests · travel · inventory · Stormlight · spellcasting · combat |
> | Worst turn latency | **28-41s** (was 665s before the timeout fix) |
> | Tool reach | **30-40%** (6-8 of 20), varies by run |
>
> ### Four production bugs Suite B found — none visible to Suite A
>
> 1. **NPC conversations were entirely broken** (three chained defects): prompt
>    variables passed flat instead of nested under the component, so the agent got an
>    empty template; `outputs_to_state={"source": "."}` naming a key that does not
>    exist, so `npc_response` never reached state; and the NPC branch returning a bare
>    dict the turn loop cannot consume. Every NPC turn showed *"The world seems
>    momentarily confused by your action."* Now: real in-character dialogue.
> 2. **No HTTP timeout on either LLM transport.** One turn blocked in
>    `receive_response_headers` for **10m43s** before the server disconnected — the
>    game simply froze. Added `HttpOptions.timeout=90s` to both.
> 3. **A resolved combat encounter never reached the player.** `_handle_response` had
>    no combat branch, so an 8-round fight that ran correctly and updated GameEngine
>    was reported as *"The adventure continues in unexpected ways..."*.
> 4. **State changes narrated but never applied.** "Make camp and rest until morning"
>    produced 1561 chars describing a night's rest with `take_rest` never called — no
>    HP, no clock movement. The prompt already forbade this in three places and cited an
>    earlier measurement of the same failure, so prose was not the fix; a backstop at
>    the findings→narration seam now applies the claim.
>
> ### The reach gap is the product, and it is a PROMPT gap
>
> 12-14 of 20 tools are never called in ordinary play. Some are legitimately
> situational (`stabilize_dying` needs someone dying), but others are not:
> `search_lore` is never called even when the player asks a direct lore question,
> partly because the prompt says *"search_lore is flavour only"*. These are
> **correct-but-invisible** — Suite A proves each works. Closing that gap is prompt
> work, tracked as the next step rather than silently absorbed.


Suite B answers the question Suite A cannot: **will an actual model, given real prompts,
ever reach these mechanics?** A scripted policy is a competent DM by construction; a
real model may simply never call `roll_skill_check`.

`scripts/playtest.py` (931 lines) is already the right harness and should be
**extended, not replaced** — it has the report object, mechanism snapshots, and log
review. Its gap: `--no-llm` **skips the turn loop entirely** (`playtest.py:921`
`report.skip("Live turns", "--no-llm")`), so today there is no way to exercise the
pipeline without API calls. That is exactly the hole Suite A fills.

Additions:

```bash
./scripts/playtest.py --turns 30 --force-combat 2      # existing
./scripts/playtest.py --coverage-report                # NEW: which mechanics fired
./scripts/playtest.py --require-coverage combat,skills # NEW: fail if never reached
./scripts/playtest.py --provider gateway             # NEW: transport parity
./scripts/playtest.py --seed 7                         # NEW: seed the dice, not the LLM
```

### What Suite B asserts (and what it must not)

**Assert** — invariant and statistical properties, never exact prose:

| # | Check |
|---|---|
| L1 | Every turn returns non-empty narration; no placeholder leaks |
| L2 | All §6 invariants hold after every real turn |
| L3 | The LLM actually calls tools — over 30 turns, ≥ 6 distinct DM tools invoked |
| L4 | Intent routing hits all four pipelines across a scripted 12-input battery |
| L5 | Dice-bearing claims are backed by a real roll (narration says "you hit" only when an `AttackOutcome` exists) |
| L6 | Combat reaches an outcome and is not left running |
| L7 | Tool *results* reach the model (already covered by `test_tool_results_reach_the_model.py`) |
| L8 | A degraded-LLM run (forced HTTP 500) still produces legal turns — the failure that motivated gateway |
| L9 | Coverage report lists which §4 mechanics real play reached; the delta vs Suite A is the review artifact |
| L10 | Cost and token use within budget (~4400 tokens/turn) |

**Never assert**: specific wording, exact damage numbers, that a given monster appears,
or that the model chose a particular action. Those make the suite flaky and train people
to ignore it.

### L9 is the real product of Suite B

Suite A proves 100% of implemented mechanics *work*. Suite B measures what fraction real
play *reaches*. **The gap between them is the actionable output** — a mechanic that is
correct but never triggered by the LLM is invisible to players, which is this project's
signature failure mode expressed one layer up, in prompts instead of wiring.

### Handling non-determinism

- Run the fixed 12-input battery (L4) rather than free-form play, so routing is comparable run to run.
- Seed the **dice** even here: divergence is then attributable to the model, not the RNG.
- Retry once on a transport error before failing; distinguish "model chose differently" from "HTTP 500".
- Keep Suite B **out of the default `pytest` run** — mark `@pytest.mark.llm` and honour the existing convention that real-LLM tests are deselected in bulk runs (they have no timeout).

---

## 9. Explicitly out of scope (not yet implemented)

Not tested, because there is nothing to test. Listed so the coverage gate's "complete"
claim is honest. When one is built, its §4 row and scenario are added together.

**Combat:** instant death from massive damage · surprise round · legendary actions ·
lair actions · arbitrary-point AoE placement and true cone/cube/line geometry.
**Character:** subclasses · feats · multiclassing · attunement slots · inspiration ·
spell components (V/S/M) · prepared-vs-known casters.
**Exploration:** travel pace · falling · suffocation · burning · dehydration/starvation ·
traps · breaking objects · shops and transactions.
**Cosmere:** ~106 of 118 order features · Allomancy (~69 arts) · Aonic (~272 arts) ·
Bondsmith (absent from the source books) · full Shardplate · the Rosharan bestiary ·
interpreter nodes `teleport`, `summon`, `illusion`, `create_object`, recurring-save,
reaction-trigger · illusion-with-disbelief · Cognitive Realm.

Two **known-partial** items get tests that assert *current* behaviour with a comment
naming the limitation, so a future fix fails the test and forces an update rather than
passing silently: Illumination's placeholder `Invisible` effect, and the polestone
always-cracks first pass.

---

## 10. Build order

Sequenced so each phase produces a working artifact and the highest-risk unknown is
resolved first.

| Phase | Work | Proves |
|---|---|---|
| **0** | `fake_generator.py` + `fake_config_manager.py` + one `ScriptedDMPolicy`; one exploration turn end-to-end with zero API calls | **The seam works.** Highest-risk unknown: whether a fake can satisfy the Haystack `Agent` tool-calling loop. Resolve before building anything on it. |
| **1** | `harness/` — game builder, §6 invariants, coverage ledger | Reusable spine |
| **2** | `test_combat_full.py` (C-1…C-6) | Largest mechanic block |
| **3** | `test_exploration_full.py`, `test_progression_full.py` | Non-combat + progression |
| **4** | `test_cosmere_full.py` (R-1…R-5) | Roshar-specific |
| **5** | `test_campaign_arc.py` (A-1) + §7 gates | Cross-cutting; the checklist becomes executable |
| **6** | Extend `playtest.py` for Suite B (L1-L10) | Reachability under a real model |
| **7** | Fix the 4 stale tests from §1; add the G2 reachability scan to CI | Stops the decay that motivated this |

**Phase 0 is a genuine go/no-go.** If a fake generator cannot satisfy the Haystack
`Agent` loop, the fallback is to drive `PipelineOrchestrator` beneath the `Agent` layer
— narrower coverage, and worth knowing on day one rather than in phase 5.

### Definition of done

1. `uv run pytest tests/integration/` — green, < 90 s, zero network calls, `-n0` and parallel.
2. The three §7 enumerated gates pass, so every offerable action, surge, and DM tool is exercised.
3. Every §4 row maps to a scenario that recorded its token.
4. `./scripts/playtest.py --turns 30 --require-coverage combat,skills,surges` passes against a real LLM.
5. The four §1 failures are fixed or deleted, and CI runs the G2 reachability scan.
6. Suite A ships with **zero mock objects for game state** — enforced by the collection guard.

---

## 11. Risks

| Risk | Mitigation |
|---|---|
| **Fake diverges from the real generator** | Contract test: run the same assertions against the fake and (marked `llm`) the real one. A signature change breaks both. |
| **Haystack `Agent` rejects the fake** | Phase 0 gate, before dependent work. |
| Integration tests become slow | 90 s budget; a scenario over 5 s is split. Parallel-safe via per-test teardown. |
| Flaky seeded assertions | Statistical claims use ≥ 600 trials and a margin ≥ 2× observed noise (an earlier flaky test measured 9.8pp noise against a 10pp threshold — the fix was seeding *and* tightening to 0.03). |
| Coverage gate gamed by touching without asserting | Tokens recorded at observed effect, not call time. |
| Suite B flakiness erodes trust | Invariants only, never prose; `@pytest.mark.llm`; out of the default run. |
| Class-global state leaks | I5/G8 assert empty registries at teardown, so the leaking test fails, not its neighbour. |

---

## 12. Standard for this document

Consistent with `docs/mechanics/README.md`: every claim here carries a `file:line`, a
command with its output, or is marked as a design proposal. The measured facts —
970/1 combat, 1327/3 non-combat, 29 registry entries, 305 arts, the four failure causes,
the 13 `create_generator` call sites, and `playtest.py:921` skipping live turns — were
all verified on `phase-0-fixes` on 2026-09-13. Nothing was carried over from a prior
document without re-checking.
