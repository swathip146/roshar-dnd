# Integration Test Strategy — full-gameplay coverage of every implemented mechanic

**Written 2026-09-13.** Plan only; no test code written yet. Every number below was
measured on branch `phase-0-fixes` during this session, not copied from prior docs.

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

### 4.1 Combat (from `AUDIT_COMBAT.md`)

| # | Mechanic | Suite A assertion |
|---|---|---|
| C1 | Attack rolls, hit/miss/crit, AC | Over N seeded attacks: hits and misses both occur; crit on natural 20 |
| C2 | Damage rolls & all 13 damage types | Damage lands in `[min,max]` per type |
| C3 | Resistance / vulnerability / immunity | Zombie poison immunity → 0; resistance halves; vulnerability doubles |
| C4 | Temp HP | Absorbs first, then real HP |
| C5 | Advantage / disadvantage | Seeded hit-rate delta ≥ +15pp vs base (measured +25.2pp) — guards the patched no-op |
| C6 | Action economy (action/bonus/reaction/move) | 2nd attack refused; reset restores |
| C7 | All 28 offerable registry actions | Each executes once and consumes its stated cost (§7 gate) |
| C8 | Grapple / Shove / Help / Disengage / Hide / Search / Ready / Two-weapon | Contested checks resolve; Help grants advantage; Disengage suppresses an OA |
| C9 | Spellcasting: slots, upcast, cantrips, save DC, attack bonus, concentration, ritual, AoE | Slot decrements; upcast scales; concentration breaks on damage; AoE hits all in radius, each saving |
| C10 | All 15 SRD conditions | Each applies and produces its mechanical effect |
| C11 | Death saves, stabilizing, unconscious-at-0 | 3 fails → dead; nat 20 → 1 HP; player at 0 ≠ dead |
| C12 | Initiative & turn order | Descending order; wraps to a new round |
| C13 | Grid, distance, movement cost, difficult terrain | Difficult terrain halves reachable distance |
| C14 | Cover (+2/+5 AC), flanking | Cover raises effective AC; flanking grants advantage |
| C15 | Opportunity attacks | Leaving reach triggers one; consumes the reaction; only once/round |
| C16 | Reach & ranged weapons | Reach attacks at 10 ft; ranged not blocked at distance |
| C17 | Multiattack (148/334 monsters) | A 2-attack monster rolls exactly twice per turn |
| C18 | Class features — 24 across 12 classes | Rage/Second Wind/Action Surge selectable; Sneak Attack & Divine Smite fire on hit; passives auto-apply |
| C19 | Monster senses (darkvision/blindsight/truesight) | Sense range gates visibility |
| C20 | CR / XP budget / encounter trim | Over-budget encounter is trimmed by dropping heads |

### 4.2 Character, progression, non-combat (from `AUDIT_CHARACTER_AND_NONCOMBAT.md`)

| # | Mechanic | Suite A assertion |
|---|---|---|
| P1 | XP award & level 1→20 | HP, proficiency, hit dice, features update at each level |
| P2 | ASI at 4/8/12/16/19 | Ability total rises exactly at those levels |
| P3 | Extra Attack → multiattack | Fighter 5 gets 2 attacks in a real turn |
| P4 | Proficiency bonus by level | +2 → +6, counted once (guards the double-count regression) |
| E1 | 18 skills, 7-step pipeline, DC scaling | RAW/HOUSE/EASY change outcome distribution |
| E2 | Expertise, tool gate, passive perception | Expertise doubles; missing tool blocks; passive used by Hide |
| E3 | Encumbrance | Speed penalty in combat **and** disadvantage on STR/DEX/CON checks |
| E4 | Rests | Short: hit dice; long: HP, slots, Stormlight, features, exhaustion −1 |
| E5 | Travel, clock, highstorms | Travel advances the clock; highstorms cycle |
| E6 | Social checks as real dice | Persuasion rolls and shifts attitude |
| E7 | Quests & endgame | Objective completes; endgame evaluated after an encounter |
| E8 | Inventory, equip → AC/attack, mid-combat re-equip | Armor changes AC; weapon changes damage die |
| E9 | Persistence round trip | 53-field character + quest/location/flags byte-identical |
| E10 | 3-tier rules lookup (Cosmere → SRD → judge → gap) | Each tier reachable; unresolved logs a gap |
| E11 | All 19 DM tools | Each invoked once via a scripted tool call (§7 gate) |

### 4.3 Cosmere / Roshar (from the two Cosmere audits)

| # | Mechanic | Suite A assertion |
|---|---|---|
| R1 | All 10 surges via `cast_surge` | Each surge resolves for each order that holds it |
| R2 | 9 playable orders × 2 surges | Every order can invoke both; **Illumination gate = Lightweaver + Truthwatcher, not Elsecaller** |
| R3 | `cast_art` over 305 arts | A sample per order compiles and resolves; IP charged; refund on no-effect |
| R4 | Cantrips are free | IP unchanged after a cantrip — guards the "charged for a free ability" regression |
| R5 | Investiture Points ledger | Spend → refuse when short → long-rest refresh |
| R6 | Lashing Dice (Windrunner) + 26 maneuvers | Dice spent and restored; maneuvers resolve |
| R7 | Long-rest Stormlight intake gate | Below level×5 sapphire marks → no refill |
| R8 | Polestone crack/drain | Cost paid even when the art fails |
| R9 | Shardblade | Real attack roll vs AC (can miss); level-scaled die; Third-Ideal gate |
| R10 | Ideals / oaths | Advancing an Ideal ungates its abilities |
| R11 | 12 interpreter node types | Each node type executed at least once |

### 4.4 Adversarial regression guards

These encode bugs the audits record as *fixed*. Each would have been caught by one
assertion, and each is cheap to re-break:

| # | Guard |
|---|---|
| G1 | Every `ACTION_REGISTRY` entry is offerable to *some* legal actor (the `cast_spell`/`spell_name` class of bug) |
| G2 | No module in `components/`, `agents/`, `core/`, `orchestrator/` defines a public callable with zero non-test callers (the reachability test, automated) |
| G3 | Advantage delta ≥ +15pp (the no-op patch) |
| G4 | Proficiency counted exactly once on an attack |
| G5 | Cantrip costs 0; no surge charges a flat sphere |
| G6 | Illumination's order gate excludes Elsecaller |
| G7 | Save/load loses nothing via the real path; `export_game_state`'s character branch is lossless too |
| G8 | Class-level entity/tile registries are empty after teardown |
| G9 | Max HP never under-reported (a documented past bug) |
| G10 | No `verify=False` anywhere (existing security invariant, kept) |

---

## 5. Suite A scenarios — the actual test bodies

Each is a **full game session**, driven through `play_turn()` with the fake generator.

| ID | Scenario | Mechanics exercised |
|---|---|---|
| **C-1** | *Skirmish, 5 rounds, seeded* — 2 PCs vs 3 monsters on a grid with cover and difficult terrain | C1-C6, C10-C16 |
| **C-2** | *Every action* — one contrived encounter that walks all 28 offerable actions | C7, C8, G1 |
| **C-3** | *Caster's turn* — cantrip, leveled spell, upcast, concentration broken by damage, AoE on 3 targets | C9 |
| **C-4** | *Monster fidelity* — zombie (poison immunity), a resistant and a vulnerable target, a 2-attack multiattacker, a darkvision monster in the dark | C3, C17, C19 |
| **C-5** | *Death spiral* — PC to 0, death saves across rounds, stabilize, nat-20 revive | C11 |
| **C-6** | *Class feature tour* — Barbarian rage, Fighter Second Wind + Action Surge, Rogue Sneak Attack, Paladin Divine Smite | C18 |
| **E-1** | *Exploration turn* — skill checks at 3 policy profiles, tool-gated check, travel, clock, highstorm | E1, E2, E5 |
| **E-2** | *Camp* — short rest then long rest; every resource verified before/after | E4 |
| **E-3** | *Social* — persuade, deceive, intimidate; attitude shifts | E6 |
| **E-4** | *Quest + endgame* — objective completes, XP awarded, endgame evaluated | E7, P1 |
| **E-5** | *Save/load mid-combat* — save, tear down, reload, finish the fight | E9, G7, G8 |
| **P-1** | *Level 1→20* — assert per level; ASI at 4/8/12/16/19; Extra Attack at 5 | P1-P4 |
| **R-1** | *Ten surges* — every surge, for every order holding it | R1, R2, G6 |
| **R-2** | *Art sampler* — a leveled art per art-bearing order; IP debited; refund on no-effect | R3, R11 |
| **R-3** | *Radiant economy* — cantrip free; IP exhausted; refused when short; long-rest gate at level×5 marks; polestone charged on failure | R4, R5, R7, R8, G5 |
| **R-4** | *Windrunner* — Lashing Dice + maneuvers across rounds | R6 |
| **R-5** | *Shardbearer* — Shardblade misses sometimes; die scales with level; gated below Third Ideal | R9, R10 |
| **A-1** | *Campaign arc, ~30 turns* — explore → social → combat → rest → level → combat → save/load → endgame | Everything, plus §6 invariants every turn |

**A-1 is the flagship.** Most of the ten historical wiring bugs would have been caught
by one long, honest run rather than by any single-mechanic test.

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
