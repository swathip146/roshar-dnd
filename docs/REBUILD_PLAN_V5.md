# Roshar D&D — Status Audit & Rebuild Plan v5

**Date:** 2026-09-07
**Supersedes:** `docs/COMBAT_ENGINE_IMPLEMENTATION_PLAN.md` v4.1 (2026-01-03)
**Method:** Parallel code audit (5 agents) + web survey of OSS alternatives, with every critical claim independently verified by direct execution — against the real `dnd_engine` API, the live Qdrant store, the dice parser, and upstream repos/package source.

| § | Contents |
|---|---|
| [1](#1-executive-summary) | Executive summary — the six findings that matter |
| [2](#2-verified-status-by-subsystem) | Verified status by subsystem |
| [3](#3-is-it-agentic-no) | Is it agentic? |
| [4](#4-recommendation-fix-in-place-then-migrate-the-agent-layer) | Recommendation: fix in place, then migrate the agent layer |
| [5](#5-the-plan) | **The plan — Phases 0-4** |
| [6](#6-effort-summary) | Effort summary |
| [7](#7-framework--oss-survey-completed-2026-09-07) | Framework & OSS survey |
| [8](#8-oss-adoption-guide-for-a-homebrew-cosmere-5e-campaign) | OSS adoption guide (homebrew campaign) |
| [9](#9-lore-storage--rules-extraction--recommended-approach) | Lore storage & rules extraction |
| [10](#10-re-indexing-runbook-fresh-embed) | **Re-indexing runbook** |
| [11](#11-parallelization-guide) | **Parallelization guide** |
| [12](#12-verification-strategy--how-each-item-gets-proven) | **Verification strategy** — tests + automated playtest gates |
| [13](#13-decisions-log) | **Decisions log (D1-D6)** — read this first; supersedes earlier text |
| [14](#14-delivery-log) | **Delivery log** — what shipped, and the 11 bugs the audit missed |

---

## 1. Executive Summary

The project is **not 85% complete**, as v4.1 claims. Measured against "a playable LLM-driven D&D game," it is roughly **35-40% complete**, and several subsystems are **broken in ways that make the game unplayable end-to-end**.

The architecture is sound. The prose quality is good. The problem is that a large amount of correct, well-tested D&D machinery is **wired to nothing**, and the test suite validates a mock API that does not match the real engine — which is why the breakage went unnoticed.

### The six findings that matter

| # | Finding | Impact | Verified by |
|---|---|---|---|
| 1 | **Every attack cancels.** Entities are created without `position` or senses, so `validate_line_of_sight` always fails. | Combat cannot deal damage. | Live execution: `EventPhase.CANCEL, 'Target entity not in line of sight'` |
| 2 | **Retrieved lore never reaches the DM.** Written to `dto["rag"]["response"]`, read from `rag["rag_context"]`. | RAG is paid for and discarded every turn. | `pipeline_integration.py:680` vs `scenario_generator_agent.py:208` |
| 3 | **The Cosmere ruleset was never indexed.** 0 of 3,062 chunks come from the Radiant's Handbook. The 394 stormlight/surge mentions are all novel prose and wiki summaries — lore, not rules. | The DM has never had access to a single Surgebinding *rule*. | Direct scan of `qdrant_storage/.../storage.sqlite` |
| 4 | **Save/load destroys the character.** Serialized via `get_character_summary()` (an analytics view). | Save file has **zero** HP/equipment/AC/spell-slot/stormlight keys. Load resurrects at 0 HP, class "Unknown". | Direct JSON key scan of `game_saves/haystack_save.json` |
| 5 | **No dice are rolled outside combat.** The 7-step skill pipeline has **zero production callers**. The LLM's `suggested_dc` is read by nothing. | The game is freeform improv wearing a d20 costume. | grep: only caller is in `legacy/` |
| 6 | **Tests validate an imagined API.** 8 combat test files `Mock()` the engine wrapper; `Mock` auto-creates `is_dead()`, `reset()`, `.value`, `cost_type` — none of which exist. | v4.1's "121/126 passing (96%)" is measuring nothing. Real: **65 failed, 131 passed, 6 errors**. | Confirmed non-existent via `inspect` on the real classes |

Findings 2 and 3 compound: even once the Handbook *is* indexed, the retrieved text is still discarded before reaching the prompt. **Fix them together or neither is observable.**

### Engine API mismatches (verified by direct introspection)

```
ActionEconomy.reset          -> False   (real name: reset_all_costs)
ModifiableValue.value        -> False   (real: normalized_score / score)
Attack.cost_type / .costs    -> False / False
Health.is_dead               -> False
Health.take_damage(self, damage, damage_type, source_entity_uuid)  # code passes 1 arg
```

Each of these is called in production code. Each raises at runtime or silently dead-branches.

---

## 2. Verified Status by Subsystem

Legend: ✅ works · 🟡 partial · 🔴 broken/unreachable · ⬜ absent

### Combat (the v4.1 plan's scope)

| Item | v4.1 claims | Reality |
|---|---|---|
| Phase 0 format standardization | ✅ | ✅ Confirmed |
| Phase 1 NPC stat generation | ✅ 8/8 | ✅ Code + templates exist |
| **Phase 1.5 NPC registry** | ✅ 10/10 | 🔴 **Loads 0 NPCs.** Commit `8bad122` moved JSONs to `data/current_campaign/npcs/`; loader still points at `data/players/` (`game_initialization.py:274`), which now holds only `.txt`. Heralds always fall through to LLM generation. **One-line fix.** |
| Phase 2 combat initializer | ✅ 21/21 | ✅ All 13 methods present |
| Phase 3 action registry | ✅ | ✅ 7 actions |
| Phase 3 attack resolution | ✅ | 🔴 **Always cancels** (finding #1) |
| Phase 4 CombatAgent | ⬜ not started | ✅ **Actually shipped** — doc is stale |
| Phase 5 NL action input | ⬜ | ⬜ Correctly open |
| Roshar Stormlight economy | ✅ | 🔴 **No-op.** Guards on `hasattr(entity,'stormlight_current')`; that attr lives on `CharacterData`, never synced to `Entity`. Stormlight is free and untracked. |
| Shardblade | ✅ | 🔴 `shardblade_summoned` never set → always cancels |
| `apply_condition` | ✅ | 🔴 Pure stub, `# TODO`, returns None. 12 of 14 engine conditions unused. |
| Action economy enforcement | ✅ "no fallbacks" | 🔴 Guard on `cost_type` never matches → `_can_character_afford_action` **always returns True** |
| "All fallbacks removed" | ✅ checked | 🟡 4 `.get()` fallbacks survive |
| Combat playable end-to-end | — | 🔴 Blocking `input()` at `combat_session_manager.py:197` **inside the pipeline** — unsavable, untestable (hangs CI), unusable from any non-CLI UI |

### Non-combat

| Subsystem | Status | Key evidence |
|---|---|---|
| Skill checks / DCs | 🔴 | 7-step pipeline correct, **0 callers**. `PolicyEngine.compute_advantage`/`adjust_difficulty`: 0 callers. `suggested_dc` decorative. |
| XP / leveling | ⬜ | `grep award_xp\|def level_up` → 0 hits. Permanently level 1. |
| Rest (short/long) | ⬜ | 0 hits. Policy strings only. |
| Death saves | ⬜ | Policy declares them; no consumer. `hp<=0` = instantly out. |
| Inventory / gold / equip | 🟡/⬜ | Flat `List[str]`, test-only callers. **No currency field at all.** AC is a static int. |
| Spell slots | 🟡 | Field exists, ships `{}`, no expenditure path. |
| Quests | 🔴 | `complete_quest_objective`: 0 callers. Prompt emits `"quests"`, code reads `"quest_objectives"` — silently discarded. `CampaignConfig` is `frozen=True`, so runtime quests are impossible. |
| Narrative memory | 🔴 | `last_scenario` = **single overwritten slot**. `narrative_beats` declared, never written or read. Interface agent sees 100 chars. |
| Location / travel | 🔴 | `exits`/`hazards` declared, never written. No travel verb. `set_location` wipes description. |
| Time / highstorms | ⬜ | `update_environment`: 0 callers. Campaign specifies `WEATHER: Highstorm-approaching` — never loaded. |
| Social NPCs | 🔴 | `generate_npc_response` returns a **hardcoded placeholder string** (`npc_controller_agent.py:43`) and is the agent's **exit condition** — the LLM's actual prose never reaches the player. `npc_context` always `{}`. Attitude/memory written nowhere. |
| Oaths / Ideals | 🔴 | `speak_oath`, `check_oath_readiness` fully implemented, **0 callers**. |
| Radiant orders | 🟡 | Only Windrunner/Skybreaker/Edgedancer/Truthwatcher surges exist. **Both shipped PCs are Lightweavers → zero usable Surges.** |
| RAG vectors | 🟡 | 3,062 points, 1024-dim, model matches — the layer works. **But:** the Cosmere ruleset (Radiant's Handbook) is **not indexed at all** (0 chunks); `WaysOfKings.txt` is a byte-identical duplicate of `RhythmOfWar.txt` so book 1 is missing; and chunking is unbounded (median 1,404 chars, **max 34,586**) because `DocumentSplitter` is imported and never used. See §9a. |
| RAG → prompt | 🔴 | Finding #2. Also: filters string-concatenated into the query, not Qdrant metadata filters; "confidence %" is `len(text)/200`; reranker commented out. |
| Persistence | 🔴 | Finding #3, plus: restore passes the whole char map to `add_character()` → creates one character named `"unknown"`. No autosave. Combat unsavable. |
| UI | 🟡 | CLI, 4 commands (`help/save/stats/quit`). **No load command.** Opening scene commented out (`haystack_dnd_game.py:192`). Single character, no party. |

### Routing bugs (all verified by execution)

- `intent_classifier.py:36` — `"combat" in str(intent_dto).lower()` substring-matches the **whole stringified DTO**. A rationale saying the player *avoids* combat routes into combat.
- `intent_classifier.py:13-25` — `_map_primary_to_type` has **no `"combat"` key**, so a genuine `primary="combat"` falls through to `"scenario"`. The intended path is unreachable; combat only fires by accident via the bug above.
- `pipeline_integration.py:449-466` — `interface_dto` bound only inside `if not route:`, read unconditionally → `UnboundLocalError` on any pre-set route.

---

## 3. Is it agentic? No.

Grepping `max_agent_steps|exit_conditions|tools=` across all of `agents/` returns hits in **one file**.

| "Agent" | What it actually is |
|---|---|
| `main_interface_agent_fixed` | One-shot classifier — `tools=[]`, `max_agent_steps=1` |
| `scenario_generator_agent` | One-shot generator — `tools=[]`, `max_agent_steps=1` |
| `rag_retriever_agent` | Real but shallow loop — 1 tool, `max_agent_steps=2` (logs show it hits the cap **before synthesizing**) |
| `npc_controller_agent` | Tool loop misconfigured — exits at step 2 on the placeholder, so `update_npc_memory` (step 3) is unreachable |
| `combat_agent` | Not an LLM agent — plain class, zero LLM calls |
| `intent_classifier` | Not an agent — a dict lookup |

**No planning. No self-correction.** Every failure path substitutes a canned fallback rather than feeding the error back for a retry. Routing is a hardcoded `if/elif`. Conversation is flattened to a single string (`llm_utils.py:314-348`), and since Gemini has no system role, system prompts are prepended as user text. Every call is stateless.

**Haystack is used decoratively — but that is a configuration choice, not a framework ceiling.** Pipelines are 1-3 node linear chains; `combat_pipeline` contains exactly one component. No `ConditionalRouter`, no `JsonSchemaValidator` — all branching happens in Python above the pipelines. Two fully-defined `Tool` objects in `main_interface_agent_fixed.py` are never passed to anything.

**Important, and it cuts against staying:** the installed Haystack (**2.21.0**, confirmed via `pip show` and `haystack.__version__`) does ship `AgentBreakpoint`/`AgentSnapshot`/`PipelineSnapshot` — verified by import. **But Haystack 3.0 deleted that API.** Verified by fetching `haystack/dataclasses/breakpoints.py` at tag `v3.1.1`: it defines only `Breakpoint`, `PipelineState`, and `PipelineSnapshot`. The v3.0.0 release notes are explicit — *"pausing and resuming execution inside an Agent (at the chat generator or tool invoker) is no longer supported."* Its replacement, `ConfirmationHook` with `BlockingConfirmationStrategy`, is a **blocking console prompt in a live process** — the opposite of durable cross-process resume.

So "stay on Haystack and configure it properly" is **not actually an available option** for a game whose turns must survive process exit. See §4.

**Structured output is the one genuinely modern piece** — Gemini `response_schema` at `llm_utils.py:190-193` works and is used for intent and scenario.

---

## 4. Recommendation: Fix in place, then migrate the agent layer

### Why not a rewrite

The expensive, hard-won assets are all sound and framework-independent:
- A working Docling→Qdrant pipeline and 379k tokens of curated Cosmere lore (the *index* needs re-chunking and the Handbook added, but the corpus and tooling are the hard part)
- `dnd_engine` (MIT, ~15k LOC of real 5e mechanics) — barely tapped, ~12% used
- Character/campaign data models, PolicyEngine's RAW/HOUSE/EASY profiles, the rules DC layer
- The 7-step skill resolution pipeline — **correct, just uncalled** (the dice module underneath it is buggy; → 0.11)

A rewrite discards all of that to fix bugs that are, in several cases, one line each. The problem is **wiring, not architecture**.

### Why not migrate frameworks *first*

Migrating would not fix findings #1-#5. You would port the same broken wiring onto a new substrate and still have no attacks, no lore, no save. Framework choice is a **Phase 3** question, and by then you will have deleted enough code to make the port cheap.

**But when you get there, migrate to LangGraph.** This reverses an earlier draft of this plan, on evidence:

- **Haystack deleted the capability we were counting on.** 2.21.0 (installed) has `AgentBreakpoint`/`AgentSnapshot`. **3.0 removed them** — verified by fetching `breakpoints.py` at `v3.1.1`, which defines only `Breakpoint`/`PipelineState`/`PipelineSnapshot`. Release notes: *"pausing and resuming execution inside an Agent... is no longer supported."* So the choice is: freeze on an unsupported 2.21 branch (which also pins you below the minimum for current Gemini integrations — `google-genai-haystack` ≥5.0 needs Haystack ≥3.0), or upgrade through a breaking migration and **lose** durable agent resume. Upgrading in place is *also* a breaking migration that leaves you worse off on the one axis that matters.
- **LangGraph's core thesis is exactly our constraint.** `interrupt()` + `Command(resume=...)` + a checkpointer; resume is a new client call keyed only by `thread_id`, so nothing in-memory need survive. `SqliteSaver.from_conn_string(...)` is file-backed durability in one line — right for a local single-player game, swappable to Postgres later. MIT, 41k stars, actively pushed. Gemini via `langchain-google-genai`.
- **Bonus:** checkpoint forking gives "rewind the campaign / alternate timeline" for free. Nothing else evaluated offers it.
- **Known gotcha to design around:** on resume, LangGraph *re-executes the node from the top*. Put `interrupt()` first in its own node and keep dice rolls, LLM calls, and state mutation in separate nodes — otherwise a resumed turn re-rolls dice and re-bills tokens.

**Rejected:** OpenAI Agents SDK (Gemini is a *"best-effort, beta"* adapter; its HITL is tool-approval-shaped, not "the story waits for the player"). Claude Agent SDK (Anthropic-only; 191 MB closed-source binary under commercial ToS, conflicting with CLAUDE.md's open-source-only rule; alpha). LlamaIndex Workflows (capable, but mid-rebrand packaging churn toward a hosted platform).

**Fallback if LangChain-ecosystem lock-in is a dealbreaker:** Pydantic AI. Native cross-process resume via `DeferredToolRequests` — and contrary to a common assumption, **Temporal is not required** for that; it's one of five optional durability backends. First-party Gemini support, lowest lock-in. Cost: you write your own checkpoint store and give up time-travel.

**Keep Haystack for RAG.** Qdrant indexing, Docling conversion, and retrieval work and are orthogonal to agency. Wrap retrieval as a LangGraph *tool*. This makes Phase 3 an incremental migration of the agent layer — a few hundred lines — not a 30k-LOC rewrite, and it preserves the `GameEngine`/`CharacterManager`/`PolicyEngine` component-authority design.

### The `dnd_engine` dependency is a real risk

Verified from GitHub's API and the vendored clone's git history:

- **24 stars, 6 forks, 1 watcher.** MIT, not archived.
- Last real commit **2025-08-22** (confirmed via the commits endpoint — the API's `pushed_at` of "today" is a proxy artifact). Before that, nothing since May 2025.
- **Single author**, abandoned-burst pattern: **129 of 221 commits in May 2025**, one since.
- **3 ad-hoc `examples/` scripts, no test suite**, for ~15k LOC across 56 files.
- **`setup.py` is a 4-line stub** — no version, no `install_requires`. It cannot be pinned or published; vendoring is the only consumption path.

An untested engine is precisely why attacks fail for want of position/senses. **Recommendation: keep it through Phase 1** (it is real 5e mechanics and rewriting now would stall everything), but treat it as **frozen third-party code**: `DnDEngineWrapper` is the single seam, cover that seam with your own tests (Phase 1.3), then absorb the subset you actually use — `Attack`/`Move`, `Entity`/`EntityConfig`, the `blocks.*` configs, `core.dice`, `core.events`, `core.modifiers`, `conditions` — into your own package and delete `external/`. MIT means you can lift the sound parts directly.

### The one structural change that *is* required

`input()` inside `CombatSessionManager` is not a style issue. It makes combat unsavable, untestable (it hung a 10-minute CI run to zero output), and impossible to drive from any non-CLI UI. **Combat must become a resumable state machine** that returns `awaiting_player_input` rather than blocking. Do this before any framework decision — it is exactly the "durable, pauseable turn" shape that LangGraph/Agent SDK checkpointing would later plug into.

---

## 5. The Plan

### Phase 0 — Stop the bleeding (3-4 days)

Highest value-per-character-changed. Every item is a small, verifiable fix. Grouped into three **independent workstreams** (A/B/C) that can run in parallel — see §11.

#### 0-A · Persistence & routing (code)

| # | Fix | File |
|---|---|---|
| 0.1 | Point NPC loader at `data/current_campaign/npcs/` | `game_initialization.py:274`, `npc_stat_loader.py:28` |
| 0.2 | Align RAG key: write `rag_context`, or read `response` | `pipeline_integration.py:680` |
| 0.3 | Real `to_dict()`/`from_dict()` on `CharacterData`; stop serializing the analytics summary | `character_manager.py:503` |
| 0.4 | Fix restore to iterate the character map | `game_initialization.py:153` |
| 0.5 | Read the save key that is actually written (`game_state`, not `orchestrator_state`) | `game_initialization.py:139` |
| 0.6 | Add `"combat"` to `_map_primary_to_type`; delete the substring match | `intent_classifier.py:13-36` |
| 0.7 | Bind `interface_dto` unconditionally | `pipeline_integration.py:449` |
| 0.8 | Guard `sys.exit(pytest.main(...))` behind `__main__` so `pytest tests/` runs at all | `tests/run_llm_test.py:25` |
| 0.9 | Autosave every turn | `haystack_dnd_game.py` |
| 0.10 | Add a `load` command | `haystack_dnd_game.py` |
| 0.11 | **Swap `components/dice.py` for `avrae/d20`** (MIT, pure-Python, `lark-parser` + `cachetools`). The current parser crashes on valid 5e notation — verified live: `damage_roll("4d6kh3")` → `ValueError: invalid literal for int(): '6kh3'`; `damage_roll("1d6 + 2")` (with spaces) → `ValueError: '+'`. And its audit trail lies: `1d8-1` on a roll of 3 correctly returns 2, but reports `modifier: 0` and prints `"1d8-1 + 0 = 2"`. d20 handles keep/drop, exploding, reroll, and `[fire]`/`[piercing]` damage-type annotations, and returns a traversable AST so you keep the audit trail. Keep your `DiceRoll`/`SkillRollResult` dataclasses; delegate only parsing/rolling. Only two consumers (`components/__init__.py`, `game_engine.py:127`). *Caveat: d20's last commit is 2022-11 — stable-and-finished, not abandoned-and-broken; MIT means you can fork it.* |

#### 0-B · Indexing pipeline fixes (code — do these BEFORE the re-embed)

These are prerequisites for 0-C. Full runbook in §10.

| # | Fix | File |
|---|---|---|
| 0.12 | **Structure-aware chunking.** ✅ DONE. Two rounds: (a) `DocumentSplitter` was imported at line 23 and **never used**, so Docling output went straight to the embedder — chunks ran to **34,586 chars**. Wiring it up bounded sizes, but (b) `split_by="word"` is structure-**blind**: measured on the Handbook, **812 of 1,041 chunks (78%) started mid-word** (`ustbringer`, `gedancer`), **0% started at a heading**, and 92 table headers were severed from their rows — which is why the surge mechanics tables were unusable. Replaced with `_split_markdown_structurally()`, following **pkg-wiki-cli's own cascade** (`narrator/generator.py`: `_split_child_by_h2` → `_split_child_by_paragraphs` → `_hard_split_by_words`): headings first, then paragraphs, then word count **on line boundaries, never mid-word**. Markdown tables are kept whole. **Result: mid-word 78%→0%, at-heading 0%→83%, orphan tables 92→0.** | `generators/batch_qdrant_indexer.py` |
| 0.13 | **Strip wiki markup** (`[[…]]`, `{{…}}`, `== … ==`, `{{anchor}}`, `[[File:…]]`) from `resources/lore/*.txt` before embedding — it currently pollutes the vectors and wastes retrieval tokens. | new preprocessor |
| 0.14 | **Preserve structure as metadata** — carry `book`/`chapter`/`section` headers into chunk `meta` so they can be filtered, not just searched. | `generators/docling_converter.py` |
| 0.15 | **Use real Qdrant payload filters.** Filters are currently string-concatenated into the query text and embedded — a silent no-op. `document_tag == "rules"` must be a payload filter. | `agents/rag_retriever_agent.py:105` |

#### 0-C · Corpus repair & fresh embed (data — owner-driven, runs in parallel)

| # | Fix |
|---|---|
| 0.16 | **`WaysOfKings.txt` is a byte-identical duplicate of `RhythmOfWar.txt`** (md5 `40734d49…`). *The Way of Kings* — book one — is **entirely missing**, and Rhythm of War is double-weighted in the embeddings (47 wasted chunks + retrieval bias). Re-source the real WoK summary. |
| 0.17 | **Index the Radiant's Handbook.** `resources/rules/863203275-Cosmere-5e-Radiant-s-Handbook-v2-0.pdf` — the entire custom Stormlight ruleset — **is not in Qdrant.** Verified: 0 of 3,062 chunks, no `parsed_data/` entry. The 394 chunks mentioning stormlight/surge/radiant are all *novel prose and Coppermind wiki* (lore), not rules. The PDF is valid and text-bearing (348 font objects, 14 images — not a scan). **Combined with 0.2, this is why the DM has never once cited a real Surgebinding rule.** |
| 0.18 | **Re-parse the whole corpus with the new parser**, then **fresh re-embed**. Run `./scripts/parse_resources.sh` (see §10) — it walks `resources/` → `parsed_data/<slug>/docling.md` using `pkgwiki-parse`, which extracts tables to Parquet and images to `assets/`, and writes a `source.json` provenance sidecar carrying `document_tag`/`folder_tags` through to the embedder. Then run the Qdrant indexer over `parsed_data/` — **twice**, once per collection (D1): `dnd_documents` (rules+lore+campaign, ~200-word chunks) and `dnd_reference` (campaigns+characters, large chunks). ~1-3 hrs total on CPU. Runbook + verification script in §10. Expect chunk count to rise from 3,062 to ~8-12k. |
| 0.19 | **Write the campaign bible** — a hand-authored ~2-3k-token markdown file (party, active NPCs, current location, what has happened) injected into *every* prompt. RAG only surfaces what you think to query; this is the persistent context that fixes "narrative memory is one overwritten slot." Feeds 2.2. |

**Exit criteria:** save → quit → load preserves HP, inventory, location, and quests. `pytest tests/` completes without INTERNALERROR. Verification script (§10) shows Radiant Handbook chunks > 0 and max chunk < ~2,000 chars. RAG text is visibly present in the scenario prompt.

⚠️ **0.2 and 0.17 must ship together.** Until 0.2 is fixed, retrieved text is discarded before reaching the DM — you would finish a 3-hour re-index and observe no behavioural change at all.

### Phase 1 — Make combat actually work (4-6 days)

| # | Fix |
|---|---|
| 1.1 | **Set `position` in `EntityConfig`**; assign grid positions at combat start; call `Entity.update_all_entities_senses()` after creation and after every move. *Unblocks Attack, Move, LOS, reactions, AoE.* |
| 1.2 | Fix the 5 signature bugs: `reset`→`reset_all_costs`, `.value`→`.normalized_score`, `cost_type`→`costs`, both `take_damage` call sites |
| 1.3 | **Replace the mocked wrapper in `tests/combat/` with the real `DnDEngineWrapper`.** Add one E2E test asserting an attack deals damage. Non-negotiable — this is why the breakage survived. |
| 1.4 | Equip real weapons/armor via `equipment.equip()`; delete the hand-rolled `execute_attack` (~110 lines of worse 5e math) and route through the engine's `Attack` |
| 1.5 | Implement `apply_condition` against all 14 engine conditions |
| 1.6 | Sync Roshar attrs (stormlight, order, shardblade) to `Entity`, or read one source of truth |
| 1.7 | Hit dice by class/CR instead of hardcoded `8` |
| 1.8 | **Convert combat to a resumable state machine** — remove `input()`, return `awaiting_player_input` |

**Exit criteria:** a scripted encounter runs start→finish, attacks hit and deal damage, stormlight is consumed, combat state survives a save/load.

### Phase 2 — Make it a game (1.5-2 weeks)

| # | Work |
|---|---|
| 2.1 | **Wire `process_skill_check` into choice selection.** Everything exists; only the call is missing. Roll against `suggested_dc`, feed the outcome into the next prompt. |
| 2.2 | Real narrative memory: bounded deque + rolling summarization into `narrative_beats`; activate the dormant `action_history` subsystem |
| 2.3 | Quest advancement: fix the `quests`/`quest_objectives` key mismatch, un-freeze `CampaignConfig`, call `complete_quest_objective` |
| 2.4 | Social NPCs: delete the placeholder so the LLM's prose reaches the player; populate `npc_context` from `key_npcs`; persist attitude + memory |
| 2.5 | XP, `level_up()`, short/long rest, death saves |
| 2.6 | Location graph + travel verb; game clock + highstorm cycle (campaign data exists and is being dropped) |
| 2.7 | Lightweaver surges (Illumination/Transformation), or ship a PC whose order has an implemented surge |
| 2.8 | Wire oaths to player input |
| 2.9 | **Three-tier rules architecture** (§8, §9c). **Tier 2 DONE**, Tier 1 outstanding. Tier 3: Qdrant for narrative lore only. **Rules are adjudicated from Tiers 1-2; the vector DB never adjudicates.**<br><br>**Tier 2 ✅** `data/rules/stormlight/surgebinding.json` + `components/cosmere_rules.py`: 9 Maneuvers, 2 features, 3 economies, 10 orders, extracted from the **parsed Handbook markdown** (not the embedded chunks — the full document preserves the tables). Every entry carries `source.line` + the **verbatim quote**; all 15 reviewed citations verified against the source, 7 marked `reviewed:false` and excluded from adjudication per D5. `verify_citations()` catches drift if the Handbook is re-parsed.<br><br>⚠️ **This corrected a real error of mine.** My earlier hardcoded surges invented per-use Stormlight-sphere costs (Lashing 1, Soulcast 3). The Handbook actually uses an expendable **dice** economy recovered on rest — Lashing Dice (2d4, scaling) for Windrunners, Investiture Points (1st=2 … 5th=7; Elsecaller always 1) for Invested Arts, plus Stormlight replenishment of `level × 5` sapphire marks per long rest. Plausible-but-wrong numbers are exactly what D5 exists to prevent.<br><br>**Tier 1 ⬜** Vendor `5e-bits/5e-database` (932★, MIT, data OGL 1.0a) — 334 monsters, spells, conditions, equipment as structured JSON. **Do not hand-author this**; clone the maintained dataset. `github.com` is allowlisted. |
| 2.10 | **LLM-assisted extraction of the rules long tail.** Once the Handbook is indexed (0.17), batch-prompt Gemini per rules section with a JSON schema to *draft* Tier-2 entries. **Review every one by hand** — this drafts, it does not decide. Every entry carries `"source": {"page": N, "reviewed": true}`; an unreviewed entry may never adjudicate. |
| 2.11 | **Instrument the rules gap.** When the DM needs a mechanic with no Tier-2 entry, log it and fall back to RAG + LLM interpretation, clearly marked unofficial. The logs then rank exactly which rules to structure next, by real usage. This is the answer to "extraction will miss rules" — it will, and the system will tell you which. |

### Phase 3 — Make it agentic (1-2 weeks, *after* Phases 0-2)

Only now is the framework question worth answering, because by this point the mechanics are tools worth calling.

1. **Give the DM agent real tools**: `roll_skill_check`, `query_rules`, `get_character_state`, `apply_damage`, `advance_quest`, `search_lore`. The LLM narrates; **code adjudicates**. This is the single highest-leverage change for quality — it eliminates invented DCs and hallucinated mechanics.

   **Adopt Avrae's declarative automation schema for this.** `avrae/avrae` (466★, GPL-3.0 — *copy the design, not the code*) is the most battle-tested open-source 5e adjudication engine. Actions are a **recursive JSON tree of effect nodes** with a `type` discriminator (`target`, `attack`, `save`, `check`, `damage`, `temphp`, `ieffect2`, `roll`, `text`, `condition`). Branching is data: `attack` has `hit`/`miss` arrays, `save` has `fail`/`success`. Fireball, entirely as data:

   ```json
   [{"type": "roll", "dice": "8d6[fire]", "name": "damage",
     "higher": {"4": "1d6[fire]", "5": "2d6[fire]"}},
    {"type": "target", "target": "all", "effects": [
      {"type": "save", "stat": "dex",
       "fail":    [{"type": "damage", "damage": "{damage}"}],
       "success": [{"type": "damage", "damage": "({damage})/2"}]}]}]
   ```

   The LLM's job shrinks to *selecting* a tree and narrating the returned event log — it never decides hit/miss or damage. Two string types carry the dynamism without code: AnnotatedString (`{damage}`, `{{floor(dexterityMod+spell)}}`) and IntExpression (`8 + proficiencyBonus + dexterityMod`). `ieffect2` makes conditions/buffs declarative too, with `to_hit_bonus`, `resistances`, `ac_bonus`, `save_adv`, plus stacking and duration semantics. **Your Roshar extensions fit cleanly**: custom surges become new effect-tree *data*, not new adjudication *code* — which is what `roshar_actions.py` is failing to be today. Reference: https://avrae.readthedocs.io/en/latest/automation_ref.html

2. **A real orchestrator loop**: `while not done: plan → act → observe → revise`. Today `max_agent_steps=1` forecloses this by construction.
3. **Retry-with-reasoning** instead of canned fallbacks.
4. **Persistent message history**; stop flattening to a single string.
5. **Durable turns.** This is where the LangGraph migration lands (see §4): one graph, `interrupt()` at the top of its own node for the player's turn, `SqliteSaver`, `thread_id` = campaign/session ID, `langchain-google-genai` for Gemini. A few hundred lines. Keep Haystack for RAG and expose retrieval as a tool.

**Architecture worth adopting regardless of framework** (LangGraph, Pydantic AI, and the OpenAI/Claude SDKs all converged on it independently): an append-only per-session transcript; an interrupt that returns the pending action **as data** rather than blocking a live process; and fork-with-remapping for branching saves. This maps cleanly onto the existing `session_manager.py`.

### Phase 4 — Hygiene (2-3 days, parallelizable)

- Delete `legacy/` (8,978 lines, tracked, 0 production imports), `debug/`, empty dirs (`models/`, `examples/`, `integration/`)
- **Make `external/dnd_engine` a git submodule or pinned pip install** — it is currently an untracked nested clone, so a fresh clone gets no engine and nothing pins the version. The build is not reproducible.
- Migrate `google.generativeai` → `google-genai` (code still gates on the dead SDK, which emits an end-of-support warning; `requirements.txt` already declares the replacement)
- Add `pyproject.toml`/`pytest.ini` (marks are unregistered)
- Merge `docs/arch` + `docs/architecture`; prune `docs/legacy/` (41 files)
- Fix CLAUDE.md: it cites `tests/test_integration.py` and `docs/reports/TEST_REPORT_INTEGRATION.md` — **neither exists** — and an unsupported "8.5/10" claim
- Correct v4.1's status header: Phase 1.5 is broken, Phase 3 is not complete, Phase 4 shipped

---

## 6. Effort Summary

Revised for decisions D1-D6 (§13). **v1 = `Shards of Honor` playable start to authored finish** (D6).

| Phase | Effort (solo) | Wall-clock if parallelized | Outcome |
|---|---|---|---|
| 0 — Stop the bleeding | 4-5 days | ~4 days (3 tracks) | Saves work (party-wide, D3); lore reaches the DM *and* includes the Cosmere ruleset; two collections (D1); chunking fixed; dice stop lying |
| 1 — Combat works | 5-7 days | overlaps Phase 0 | Attacks land; party-aware turn order; combat resumable and testable |
| 2 — Make it a game | 3-4 weeks | ~2-2.5 weeks | Oaths, XP/levels 1-10, rests, death saves, travel, quests, structured campaign schema + endgame (D2), party roster (D3), Lightweaver surges |
| 3 — Make it agentic | ✅ **DONE** | — | 13 DM tools; grounded rules-judge with binding precedent (D5); LangGraph durable turns **wired into `play_turn()`** and surviving process exit; UI-agnostic `begin_turn()`/`resume_turn()` (D4); retry-with-reasoning; persistent history |
| 4 — Hygiene | ✅ **DONE** | — | 10,934 lines of dead code deleted; **ported to the current `google-genai` SDK**; pytest marks + global timeout; `dnd_engine` pinned; three false claims removed from CLAUDE.md |
| **v1 total** | **~8-11 weeks** | **~6-8 weeks** | vs. ~3-4 months to rewrite and re-earn the lore index and engine integration |
| *5 — Web app (D4)* | *3-5 days+* | *after v1* | *Streamlit over the D4 turn API — **not in v1*** |

Grew from the pre-review estimate (~7-9 weeks) because D2, D3, and D5 added real scope: structured campaign schema + endgame detection, party support, and the rules-judge with its ruling store. D3 was cheaper than feared — the party plumbing already exists below the narrowing at `pipeline_integration.py:879`.

**Sequencing rules:**
- Do not start Phase 3 before **1.3** (real-engine tests). The mock suite is what let five subsystems break silently.
- **D5 Tier 3** (rules-judge) is unusable before **0.17 + 0.2** — it must retrieve the Handbook to rule from it.
- Do not start **Phase 5** before the CLI is fully working.

See §11 for the dependency spine and wave plan, §12 for verification gates, §13 for the decisions these rest on.

---

## 7. Framework & OSS Survey (completed 2026-09-07)

### Agent frameworks

Evaluated against the defining constraint: **a turn blocks on human input for minutes to days and must resume in a new process.**

| | LangGraph | Pydantic AI | LlamaIndex Workflows | OpenAI Agents SDK | Haystack 3.x |
|---|---|---|---|---|---|
| Stars / pushed | 41.2k / 2026-09-06 | 19.8k / 2026-09-08 | 52.1k / 2026-09-05 | 29.3k / 2026-09-08 | 26.4k / 2026-09-07 |
| Version | 1.2.11 | 2.41.0 | 2.23.3 | 0.22.0 | 3.1.1 |
| License | MIT | MIT | MIT | MIT | Apache-2.0 |
| Gemini | ✅ `langchain-google-genai` | ✅ **first-party** | ✅ | ⚠️ *"best-effort, beta"* adapter | ✅ |
| **Durable cross-process resume** | ✅✅ **core design** | ✅ native | ✅ Context serialize | ✅ `RunState` JSON | ❌ **removed in 3.0** |
| Mechanism | `interrupt()` + `Command(resume=)` + checkpointer | `DeferredToolRequests` | `ctx.to_dict()` | `to_state()`/`from_json()` | blocking console prompt |
| Batteries-included store | ✅✅ SQLite + Postgres | ⚠️ you persist | ⚠️ you persist | ⚠️ you persist | n/a |
| Time travel / branching | ✅ fork any checkpoint | ❌ | ❌ | ❌ | ❌ |
| Lock-in | Medium | **Low** | Medium | **High** | Low |

**Verdict: LangGraph**, for the reasons in §4. **Fallback: Pydantic AI.** **Rejected:** OpenAI Agents SDK, Claude Agent SDK, LlamaIndex Workflows.

### OSS D&D repos

| Repo | Stars | Last real commit | License | Verdict |
|---|---|---|---|---|
| [5e-bits/5e-database](https://github.com/5e-bits/5e-database) | 932 | 2026-09-07 | MIT (data OGL 1.0a) | **Adopt** — SRD as JSON for rules lookup (§Phase 2.9) |
| [avrae/avrae](https://github.com/avrae/avrae) | 466 | 2026-08-18 | **GPL-3.0** | **Copy the schema, not the code** — best 5e adjudication design in OSS (§Phase 3.1) |
| [open5e/open5e-api](https://github.com/open5e/open5e-api) | 213 | 2026-08-23 | Modified MIT | Fallback only; license carves out 3rd-party SRD |
| [avrae/d20](https://github.com/avrae/d20) | 141 | 2022-11-20 | MIT | **Adopt** — replaces buggy `components/dice.py` (§Phase 0.11) |
| [furlat/dnd_engine](https://github.com/furlat/dnd_engine) | **24** | **2025-08-22** | MIT | **Abandon in place** — see §4 |
| [neuralinitiative/claude-dnd-skill](https://github.com/neuralinitiative/claude-dnd-skill) | 156 | 2026-09-07 | AGPL-3.0 | Closest analogue; viral license — read, don't copy |
| [MoonlightByte/NeverEndingQuest](https://github.com/MoonlightByte/NeverEndingQuest) | 74 | 2026-09-07 | Fair Source→Apache-2.0 | **Cautionary tale** — LLM does the math; author admits broken combat on weaker models |
| [eddiefiggie/srd-rules-engine](https://github.com/eddiefiggie/srd-rules-engine) | 0 | 2026-09-06 | MIT | Tiny, but exactly our thesis and honestly documented — worth reading |
| [calypso-aiide-artifact](https://github.com/northern-lights-province/calypso-aiide-artifact) | 28 | 2023-08-23 | MIT | Dead, but the published AIIDE paper on LLMs as DM *assistants* |

### On "LLM narrates, code adjudicates"

The evidence for this split is the field's own failure mode: `NeverEndingQuest` lets the LLM do the arithmetic, and its author documents combat math breaking on weaker models. Avrae — by far the most-used open-source 5e engine — went the other way: **every mechanic is declarative data walked by code**, and the LLM (or user) only selects and narrates. This project already demonstrates the problem locally: the LLM emits a `suggested_dc` every turn that nothing reads or enforces.

**Caveat on sourcing:** `docs.langchain.com`, `pydantic.dev/docs`, and `developers.llamaindex.ai` redirect off-allowlist, so framework claims were verified against **in-repo source at specific tags** (e.g. `interrupt()`'s docstring, `breakpoints.py` at `v3.1.1`) rather than prose docs — stronger evidence, but it means LangGraph's `durability=` modes and LlamaIndex's `WorkflowCheckpointer` were **not** verified and are not asserted here. GitHub's API rate-limited near the end of the OSS sweep.

---

## 8. OSS Adoption Guide for a Homebrew (Cosmere 5e) Campaign

The standard advice — "use SRD JSON instead of RAG" — is **not sufficient here**, because the ruleset is SRD *plus* a homebrew supplement (`resources/rules/863203275-Cosmere-5e-Radiant-s-Handbook-v2-0.pdf`) that no OSS dataset will ever contain. This section answers: what to adopt, what to reference, what to build.

### The finding that reframes everything

**Your custom ruleset is not in the vector database.** Verified against `qdrant_storage/collection/dnd_documents/storage.sqlite`:

| | chunks |
|---|---|
| Total indexed | 3,062 |
| **From the Radiant's Handbook** | **0** |
| Mentioning stormlight/surge/radiant/spren | 394 — *all from novels + Coppermind wiki* |

Indexed sources are `SRD_CC_v5.2.1.pdf` (1,282), `DnD_BasicRules_2018.pdf` (609), `FILE_5035.pdf` (97), the five novels as `.txt` (264 total), and adventure modules. By `document_tag`: rules 1,891 / characters 581 / lore 364 / campaigns 214.

So the DM has **never had access to a single Surgebinding rule** — only novel prose describing Surgebinding narratively. Combined with the §1 finding that retrieved text is discarded anyway (`rag["response"]` vs `rag["rag_context"]`), the Cosmere ruleset has had zero influence on gameplay. The PDF is valid and text-bearing (348 font objects, 14 images — not a scan), and `batch_qdrant_indexer.py` already `rglob`s `*.pdf`. It was simply never indexed. → **Phase 0.17.**

### Three-tier rules architecture

The mistake to avoid is treating all three of these as one RAG corpus. They have different failure modes and need different storage.

| Tier | Content | Storage | Source | Who adjudicates |
|---|---|---|---|---|
| **1. Baseline SRD** | Monsters, spells, conditions, equipment, core rules | **JSON** | `5e-bits/5e-database` (adopt) | Code |
| **2. Cosmere homebrew** | Surges, Stormlight economy, Radiant orders, Ideals, Shardblades/plate, spren bonds | **JSON you author** | Hand-extracted from the Radiant's Handbook | Code |
| **3. Narrative lore** | Novels, Coppermind, world history, characters, places | **Qdrant vectors** | Already indexed and healthy | Nobody — it only flavors prose |

**Rule: Tiers 1-2 adjudicate. Tier 3 never adjudicates.** A vector search returning "Stormlight can be used to heal wounds" is useful narrative color and useless as a mechanic — it has no cost, no die, no DC. That ambiguity is precisely where the LLM invents numbers today.

### What to adopt, reference, or build

| Repo | Action | Why, for *this* project |
|---|---|---|
| [avrae/d20](https://github.com/avrae/d20) — 141★, MIT | **ADOPT (dependency)** | Drop-in for the buggy `components/dice.py`. Domain-neutral: `2d6[fire]` and a homebrew `4d8[investiture]` parse identically. Damage-type annotations are what Tier 2 needs. → Phase 0.11 |
| [5e-bits/5e-database](https://github.com/5e-bits/5e-database) — 932★, MIT (OGL 1.0a data) | **ADOPT (vendor the JSON)** | Tier 1 baseline. Cosmere 5e is *additive* to SRD — you still need standard conditions, skills, and monster stat blocks. Vendor the files; don't run their API. → Phase 2.9 |
| [avrae/avrae](https://github.com/avrae/avrae) — 466★, **GPL-3.0** | **REFERENCE (copy the schema, never the code)** | **The single most valuable item here.** Its declarative effect tree is *content-agnostic* — a Lashing is a JSON tree exactly like Fireball. This is how you encode homebrew as data instead of `roshar_actions.py`'s bespoke Python. GPL-3.0 is viral: read `automation_ref.html`, reimplement the schema clean-room. → Phase 3.1 |
| [furlat/dnd_engine](https://github.com/furlat/dnd_engine) — 24★, MIT | **ABSORB, then delete** | See §4. Its `ModifiableValue`/modifier-stacking design *is* worth keeping — it's the right shape for "Stormlight grants +2 AC while Invested." Lift that MIT code into your own package with tests. |
| [open5e/open5e-api](https://github.com/open5e/open5e-api) — 213★, modified MIT | **SKIP** | Modified MIT explicitly carves out third-party SRD content — the exact category homebrew falls into. Licensing risk with no benefit over 5e-bits. |
| [neuralinitiative/claude-dnd-skill](https://github.com/neuralinitiative/claude-dnd-skill) — 156★, **AGPL-3.0** | **REFERENCE ONLY** | Closest analogue to your goal. AGPL is viral even over a network — do not copy code. |
| [MoonlightByte/NeverEndingQuest](https://github.com/MoonlightByte/NeverEndingQuest) — 74★ | **REFERENCE (cautionary)** | Lets the LLM do combat math; the author documents it breaking on weaker models. This is the failure you are currently reproducing. |
| [eddiefiggie/srd-rules-engine](https://github.com/eddiefiggie/srd-rules-engine) — 0★, MIT | **REFERENCE** | Tiny, but the exact thesis, honestly documented. Cheap read. |
| **Cosmere Tier-2 JSON** | **BUILD — no OSS substitute exists** | ~20-40 entries: 10 Surges, 10 orders, Ideals, Stormlight costs, Shardblade/plate, spren bonds. Hand-author from the Handbook. |

### Why hand-author Tier 2 rather than RAG it

The Handbook is ~2.3 MB of homebrew, but the *mechanically adjudicable* surface is small — on the order of 20-40 entries. Hand-extracting them into JSON is **1-2 days** and yields something code can execute:

```json
{
  "id": "lashing_basic",
  "name": "Basic Lashing",
  "orders": ["windrunner", "skybreaker"],
  "cost": {"stormlight": 1},
  "automation": [
    {"type": "target", "target": "self", "effects": [
      {"type": "ieffect2", "name": "Lashed",
       "duration": 10,
       "effects": {"speed_bonus": 20}}]}]
}
```

That is adjudicable, testable, and diffable. A vector chunk saying *"a Windrunner may Lash themselves to fall in any direction"* is none of those things. Keep the Handbook in Qdrant too (→ Phase 0.17) so the DM can *quote* flavor text — but never let it *decide* mechanics.

This also fixes a real defect: `roshar_actions.py` today hardcodes each surge as bespoke Python, and its Stormlight guards silently no-op (§2). Under the Avrae-style model, adding a Lightweaver Illumination surge is **a new JSON file**, not new adjudication code — which is exactly why both shipped PCs currently have zero usable Surges.

### Licensing summary

| License | Repos | Constraint |
|---|---|---|
| MIT | d20, 5e-bits, dnd_engine, srd-rules-engine | Free to vendor and modify |
| OGL 1.0a | 5e-bits *data* | Fine for SRD content; include the notice |
| **GPL-3.0** | avrae | **Schema only, clean-room** |
| **AGPL-3.0** | claude-dnd-skill | **Read only** |
| Modified MIT | open5e | Avoid |

CLAUDE.md mandates open-source-only. All *adopted* items are MIT; the copyleft repos are reference-only, which keeps that rule intact.

---

## 9. Lore Storage & Rules Extraction — Recommended Approach

Two questions, two different answers, because lore and rules fail differently. **Lore failing = bland prose. Rules failing = wrong numbers the player can't detect.**

### 9a. Data-quality problems found while assessing this

| Problem | Evidence | Fix |
|---|---|---|
| **`WaysOfKings.txt` is a byte-identical duplicate of `RhythmOfWar.txt`** | Same md5 `40734d49…`. Book 1 of the series is **entirely missing**; RoW is double-weighted in embeddings (47 wasted chunks + retrieval bias toward RoW). | Re-source *The Way of Kings* summary |
| Lore files are **Coppermind wiki chapter summaries**, not novel prose | All six open with *"This page contains a chapter by chapter summary of…"* and carry `{{wiki}}`/`[[link]]` markup | Fine for RAG — arguably *better* than raw prose — but strip markup before embedding |
| **Chunking is wildly inconsistent** | median 1,404 chars, p90 5,017, **max 34,586** | A 34k-char chunk is a whole document; its embedding means nothing. Re-chunk to ~800-1,200 chars with overlap |
| Radiant's Handbook not indexed | 0 of 3,062 chunks (§8) | Phase 0.17 |

Lore corpus is only **~379k tokens total** — small. That matters for 9b.

### 9b. Lore → keep in Qdrant, but fix the pipeline

**Answer: Qdrant, not markdown files.** Reasoning:

- Lore queries are *semantic* ("what does Kaladin think of Amaram?"), which is exactly what vectors are for. Markdown would need grep/keyword, which fails on paraphrase.
- 379k tokens is too big for every prompt (~$0.10+/turn at Gemini rates, and it would swamp the context), so "just stuff it in" is not viable at turn scale.
- It's already indexed and working — 364 lore chunks retrieving correctly. The failure was downstream (`rag["response"]` never read), not in the vector layer.

**But do these three things:**
1. **Strip wiki markup** (`[[…]]`, `{{…}}`, `== … ==`) before embedding — it pollutes the vectors and wastes tokens on retrieval.
2. **Re-chunk to ~800-1,200 chars with ~150 overlap.** Preserve section headers as metadata (`book`, `chapter`, `character`) so you can filter, not just search.
3. **Add real Qdrant metadata filters.** Today filters are string-concatenated into the query text and embedded (§2) — a no-op. Filtering `document_tag == "lore"` should be a payload filter.

**Keep a small hand-written markdown file *in addition*** — a ~2-3k-token campaign bible (current party, active NPCs, where they are, what's happened) injected into *every* prompt. That's the persistent context RAG can't provide because it only surfaces what you happen to query for. This is the real fix for the "narrative memory is one overwritten slot" finding.

### 9c. Rules → JSON *and* RAG. Your instinct is right.

**You are correct that a one-time extraction won't capture everything.** 299 pages will not reduce cleanly to 40 JSON entries. But the conclusion isn't "use RAG for rules" — it's **use both, with a strict split by function**:

| | JSON (Tier 2) | RAG over the Handbook |
|---|---|---|
| **Purpose** | *Adjudicate* — resolve a mechanic | *Answer* — explain a rule |
| **Consumer** | Code (dice, costs, effects) | LLM narration, player Q&A |
| **Covers** | The hot path: ~10 Surges, orders, Stormlight costs, Ideals, Shardblades | The long tail: everything else in 299 pages |
| **Failure mode** | Missing entry → obvious, loud | Wrong retrieval → plausible, silent |

**The rule: if code needs to compute with it, it must be JSON. If the LLM only needs to talk about it, RAG is fine.**

You cannot adjudicate from RAG. A retrieved chunk saying *"Lashings cost Stormlight"* has no number — code can't subtract it. So the hot path *must* be structured. But you don't need all 299 pages structured, only what the engine actually executes.

**Recommended sequence — extraction with a RAG safety net:**

1. **Index the Handbook first** (Phase 0.17). This is cheap and immediately useful for player Q&A even before any JSON exists.
2. **Extract the hot path to JSON** — start with what the code already references: the 10 Surges, Radiant orders, Ideals, Stormlight economy, Shardblades/plate. **1-2 days.** Don't aim for completeness; aim for what `roshar_actions.py` needs.
3. **LLM-assisted extraction for the rest.** Since the Handbook is now indexed, run a batch pass: for each rules section, prompt Gemini with the chunks and a JSON schema, and have it emit candidate entries. **Review every one by hand** — this drafts, it doesn't decide. Converts weeks of transcription into days of review.
4. **Instrument the gap.** When the DM needs a mechanic with no JSON entry, log it and fall back to RAG + LLM interpretation, clearly marked as unofficial. Your logs then tell you exactly which rules to structure next, ranked by real usage. This is the answer to "I might miss some rules" — you will, and the system will tell you which.

That inverts the problem: instead of trying to extract 299 pages perfectly up front, you structure the ~40 entries you know you need, ship, and let play reveal the rest.

**One caution on step 3:** LLM-extracted rules that are never reviewed are worse than no rules — they're confidently wrong and indistinguishable from correct ones. Keep a `"source": {"page": N, "reviewed": true}` field on every entry, and never let an unreviewed entry adjudicate.

---

## 10. Re-indexing Runbook (fresh embed)

Two stages: **parse** (`resources/` → `parsed_data/`), then **embed** (`parsed_data/` → Qdrant).

### Stage 1 — Parse with `pkgwiki-parse`

```bash
cd /Users/scj/Documents/Projects/AI/DnD_new/roshar-dnd/roshar-dnd
./scripts/parse_resources.sh --dry-run     # preview
./scripts/parse_resources.sh               # parse everything (skips already-done)
./scripts/parse_resources.sh -j 4          # 4 parallel workers
./scripts/parse_resources.sh --only rules  # just resources/rules/**
./scripts/parse_resources.sh --force       # re-parse even if output exists
```

Wraps `uv run --project /Users/scj/Documents/Projects/AI/pkg-wiki-cli pkgwiki-parse`, which is single-file, so the script walks the tree. Per document it writes:

```
parsed_data/<slug>/docling.md    # markdown text — this is what gets embedded
parsed_data/<slug>/tagged.md     # structure-tagged markdown (richer formats)
parsed_data/<slug>/meta.json     # parser metadata
parsed_data/<slug>/assets/       # extracted images + tables as Parquet
parsed_data/<slug>/source.json   # provenance we add: source_file, folder_tags, document_tag
```

`source.json` is the important addition — it carries the `resources/` subdirectory (`rules`, `lore`, `campaigns`, …) through as `document_tag`, which is what §2's status table and the retriever's filters depend on. The indexer must read it (plan 0.14).

**Two gotchas already handled in the script, verified live:**
- **Docling's layout model download is proxy-blocked** (`httpx.ProxyError: 403 Forbidden`), which fails *every PDF* while text files pass through fine. The models are already cached at `~/.cache/docling/models`, so the script exports `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `HF_HOME=~/.cache/huggingface`. Confirmed: without these `FILE_5035.pdf` fails; with them it parses to 27,721 chars / 88 images / 2 tables.
- `.txt` passthrough yields only `docling.md` + `raw.txt` (no `meta.json`/`tagged.md`), so the script keys success on `docling.md`.

Smoke-tested: `resources/lore` → **7/7 parsed, 0 failures, 27s**. Expect the full 190-file run (172 PDFs, incl. the 299-page Handbook) to take considerably longer — run it in a terminal you can leave.

### Stage 2 — Embed into Qdrant

**`generators/batch_qdrant_indexer.py`** — run it directly; it is fully interactive (no CLI flags):

```bash
conda run -n dndenv python generators/batch_qdrant_indexer.py
```

It prompts for four things:

| Prompt | Answer for a fresh run |
|---|---|
| `Enter the root folder path containing documents:` | **`parsed_data`** (not `resources` — parsing already happened) |
| `Use Qdrant vector storage? (y/n, default: y)` | `y` |
| `Qdrant collection name (default: dnd_documents)` | *(Enter)* — must stay `dnd_documents`; the game hardcodes it |
| `Clear existing documents in collection? (y/n, default: n)` | **`y`** |

**Collection name must remain `dnd_documents`** — `core/game_initialization.py` looks it up by that name. If you index under a different name the game silently retrieves nothing.

### Before you run

```bash
# 1. Back up the current index (80 MB) — the clear is irreversible
cp -r qdrant_storage qdrant_storage.bak

# 2. Fix the duplicate: WaysOfKings.txt is byte-identical to RhythmOfWar.txt
md5 -q resources/lore/WaysOfKings.txt resources/lore/RhythmOfWar.txt   # same hash = still broken
# replace WaysOfKings.txt with the real Way of Kings summary, or delete it

# 3. Confirm the Handbook will be picked up (it was missed last time)
ls -la resources/rules/863203275-Cosmere-5e-Radiant-s-Handbook-v2-0.pdf
```

`clear_existing=y` calls `shutil.rmtree()` on `qdrant_storage/dnd_documents`. **There is no undo.** Take the backup.

Note the clear path is `Path(storage_path) / collection_name` → `qdrant_storage/dnd_documents`, but the live data sits at `qdrant_storage/collection/dnd_documents`. **Verify the clear actually emptied the collection** (count check below); if not, `rm -rf qdrant_storage/` and let it rebuild.

### ⚠️ Fix chunking BEFORE the fresh run

`DocumentSplitter` is **imported at line 23 and never used.** `store_in_qdrant()` (line 94) sends Docling's raw output straight to the embedder. That is why chunks range from tiny to **34,586 chars** — a 34k-char chunk embeds to a meaningless average and will never retrieve precisely.

Since you are re-indexing anyway, fix it in the same pass — insert a splitter in `store_in_qdrant()` before embedding:

```python
from haystack.components.preprocessors import DocumentSplitter

def store_in_qdrant(documents, document_store):
    splitter = DocumentSplitter(
        split_by="word", split_length=200, split_overlap=30,
    )
    splitter.warm_up()
    documents = splitter.run(documents=documents)["documents"]

    embedder = SentenceTransformersDocumentEmbedder(
        model="BAAI/bge-large-en-v1.5", progress_bar=False
    )
    ...
```

~200 words ≈ 1,000-1,300 chars, comfortably inside bge-large's 512-token window. Chunk count will rise from 3,062 to roughly 8-12k — expected and good.

Also strip wiki markup (`[[…]]`, `{{…}}`, `== … ==`) from `resources/lore/*.txt` before indexing; it currently pollutes the embeddings.

### Runtime expectations

- **bge-large-en-v1.5 on CPU**: expect **1-3 hours** for the full corpus (Docling PDF parsing dominates; the 299-page Handbook alone is slow). Run it in a terminal you can leave alone, not in a tool call that may time out.
- First run downloads the model (~1.3 GB) if not cached.
- Docling emits `parsed_data/<name>_<timestamp>/` markdown + metadata per document — useful for spot-checking extraction quality before trusting the vectors.

### Verify after the run

```bash
conda run -n dndenv python -c "
import sqlite3, pickle, ast, collections
c = sqlite3.connect('qdrant_storage/collection/dnd_documents/storage.sqlite')
src = collections.Counter(); tag = collections.Counter(); lens = []
for (blob,) in c.execute('select point from points'):
    p = pickle.loads(blob)
    pl = p.get('payload') if isinstance(p, dict) else getattr(p, 'payload', None)
    if not pl: continue
    m = pl.get('meta')
    if isinstance(m, str):
        try: m = ast.literal_eval(m)
        except Exception: m = {}
    src[(m or {}).get('source_file','?')] += 1
    tag[(m or {}).get('document_tag','?')] += 1
    lens.append(len(str(pl.get('content',''))))
lens.sort()
print('total chunks:', len(lens))
print('median chars:', lens[len(lens)//2], '| max:', max(lens))
print('Radiant Handbook chunks:', sum(v for k,v in src.items() if 'Radiant' in k or '863203275' in k))
print('by tag:', dict(tag))
"
```

**Pass criteria:**
- `Radiant Handbook chunks` > 0 — *this is the whole point of the re-index*
- `max` chars < ~2,000 — proves the splitter is active
- `total chunks` ≈ 8-12k
- `by tag` shows rules / lore / characters / campaigns as before

Then confirm the game still retrieves: run one turn and check `logs/dnd_game_*.log` for retrieval hits. Note that until Phase 0.2 is fixed, retrieved text is still discarded before reaching the DM prompt — so **fix 0.2 and 0.12 together**, or you will re-index and see no behavioural change.

---

## 11. Parallelization Guide

### The dependency spine

Only three hard ordering constraints exist. Everything else is parallelizable.

```
0.12-0.15 (splitter/markup/metadata/filters)  ──▶  0.18 (fresh embed)  ──▶  2.10 (LLM extraction)
0.2 (RAG key)  ─────────────────────────────────▶  [ship together with 0.17]
1.1 (position/senses)  ─▶  1.4 (equip+native Attack)  ─▶  1.3 (real-engine tests)  ─▶  Phase 3
```

**Rule:** never start Phase 3 before 1.3. The mock-based suite is what let five subsystems break silently; adding agentic complexity to an unverifiable base repeats the failure at greater cost.

### Four independent tracks

| Track | Scope | Touches | Conflicts with |
|---|---|---|---|
| **A · Data/RAG** | 0.12-0.19, 2.9-2.11 | `generators/`, `resources/`, `qdrant_storage/`, `data/rules/` | nothing |
| **B · Persistence & routing** | 0.1, 0.3-0.10 | `character_manager.py`, `session_manager.py`, `game_initialization.py`, `intent_classifier.py` | light overlap with D on `pipeline_integration.py` |
| **C · Combat engine** | 1.1-1.8 | `components/combat/`, `dnd_engine_wrapper.py`, `tests/combat/` | nothing |
| **D · Game systems** | 2.1-2.8 | `game_engine.py`, `agents/`, `haystack_dnd_game.py` | needs 0.11 (dice) for 2.1 |

A and C share no files at all — those two can run fully concurrently with zero coordination. B and D both touch `pipeline_integration.py`; keep them on separate branches and merge B first (it is smaller).

### Suggested wave plan

**Wave 1 (parallel, ~4 days)** — A: 0.12-0.15 code fixes, then 0.16-0.18 re-embed (the 1-3 hr embed runs unattended). B: all of 0-A. C: 1.1 + 1.2 (unblocks everything else in combat).
→ *Gate:* verification script passes; save/load round-trips; one attack deals damage.

**Wave 2 (parallel, ~1.5 weeks)** — A: 2.9 + start 2.10. C: 1.3-1.8. D: 2.1-2.5 (needs 0.11 from Wave 1).
→ *Gate:* scripted encounter runs end-to-end; skill checks roll real dice.

**Wave 3 (~2-3 weeks)** — D: 2.6-2.8, 2.11. Then Phase 3 as a single focused track — the LangGraph migration is not parallelizable against itself.

Phase 4 hygiene is independent throughout; slot it wherever there is slack. One caveat: `parsed_data/` is now a build output of `scripts/parse_resources.sh` — keep it gitignored, and do not delete it between the parse (0.18) and the embed.

### If you are working solo

Sequence by *unblocking power*, not by phase number: **0.12-0.18** (starts the long embed early, and it runs while you code) → **0.2** → **1.1 + 1.2** → **0.3-0.5** → everything else. Kick off the re-embed first every time; it is the only multi-hour wall-clock item.

---

## 12. Verification Strategy — how each item gets proven

Every plan item ships with a check. Three tiers, cheapest first.

### Tier 1 · Unit / integration tests (most items)

Standard `pytest`. Two prerequisites before this tier is trustworthy at all:

- **0.8** — `pytest tests/` currently aborts with `INTERNALERROR` because three files call `pytest.main()`/`sys.exit()` at import scope. Fix first or you cannot measure anything.
- **1.3** — replace the `Mock()` engine wrapper in `tests/combat/` with the real `DnDEngineWrapper`. **This is the single most important item in the plan.** The current suite auto-creates `is_dead()`, `reset()`, `.value`, `cost_type` — none of which exist — which is exactly how five subsystems broke while reporting "96% passing."

Baseline to beat: **65 failed / 131 passed / 6 errors**. Record the number after each phase; it must go monotonically up.

### Tier 2 · Targeted assertions on the real subsystem (no LLM)

For items where a unit test can pass while the feature is still dead, assert against real state. Examples that would have caught the actual bugs:

```python
# 0.3-0.5 — save/load round-trip (would have caught finding #4)
save_game(path); state = load_game(path)
assert state.characters["aggi"].hit_points["current"] == 24
assert state.characters["aggi"].character_class != "Unknown"
assert "aggi" in state.characters            # not a character named "unknown"

# 1.1-1.4 — an attack must actually land (would have caught finding #1)
result = wrapper.execute_attack(attacker, target)
assert result["outcome"] in ("hit", "miss", "crit")   # never "cancelled"
assert target.health.get_total_hit_points(con_mod) < start_hp   # damage applied

# 0.2 + 0.17 — retrieved lore reaches the prompt (findings #2, #3)
prompt = create_scenario_from_dto(dto)
assert retrieved_snippet in prompt

# 0.12 — chunking is bounded
assert max(len(c.content) for c in chunks) < 2000
```

**Rule: assert on observable end state, not on "the function was called."** Every one of the six findings was a case where the call happened and the effect did not.

### Tier 3 · Automated playtest (per-phase gate, uses the LLM)

`haystack_dnd_game.py:291` exposes `play_turn(player_input) -> str` — call it directly rather than piping stdin (`tests/run_automated_test.py` shows the older stdin approach; the programmatic one is more assertable). Build `tests/test_playthrough_smoke.py`:

```python
game = HaystackDnDGame(...)
transcript = [game.play_turn(t) for t in [
    "look around", "talk to the guard", "search the room", "1",
]]
# Structural assertions — cheap, deterministic, no LLM judging
assert all(r and not r.startswith("Error") for r in transcript)
assert "The guard responds to your action" not in " ".join(transcript)  # 2.4 placeholder
assert log_has_no_errors(latest_log())
```

Costs ~4-8 LLM calls per run at ~$0.0002/turn — negligible. Run it at every phase gate.

**Phase gates:**

| After | Playtest must show |
|---|---|
| Phase 0 | 4 turns, no errors; save→quit→load preserves HP/inventory/location; retrieved lore text appears in the prompt; Handbook chunks > 0 |
| Phase 1 | A scripted encounter runs start→finish; attacks deal damage; stormlight is consumed; combat state survives save/load |
| Phase 2 | Skill checks roll real dice against `suggested_dc`; a quest objective completes; an NPC's *actual* LLM prose reaches the player; XP is awarded |
| Phase 3 | The DM calls tools instead of inventing numbers; a turn survives process exit and resumes |

**Do not gate on prose quality.** Assert on structure (no errors, no placeholders, state changed as expected). LLM-judging narrative quality is expensive, flaky, and not what these gates are for.

### Regression guard

After each phase, append the real test count and the playtest result to a running table in this document. If a number goes down, stop and fix before continuing — that is precisely the failure mode v4.1 hit.

---

## 13. Decisions Log

Resolved during plan review. Each supersedes any earlier text in this document.

### D1 · Two Qdrant collections, not one *(2026-09-07)*

**Decision:** split the vector store by consumer.

| Collection | Contents | Consumer | Chunking |
|---|---|---|---|
| `dnd_documents` | `resources/rules/`, `resources/lore/`, `data/current_campaign/` | **DM at play** (every turn) | small & precise — ~200 words |
| `dnd_reference` | `resources/campaigns/` (Faerûn modules), `resources/characters/` (170 pre-gen sheets) | **`generators/campaign_generator.py`** (offline) | large — a whole arc per retrieval |

**Why.** The adventure modules are not noise: `campaign_generator.py:3` exists to learn campaign *structure* from them — how a hook opens, how acts escalate, how a campaign closes. That is a real requirement. But the DM must never surface Waterdeep during a Roshar scene, and the two consumers want opposite chunk sizes.

Rejected: one collection + payload filters. That makes correctness depend on every query path remembering to filter — and filters are currently a silent no-op (0.15) that went unnoticed for months. Separate collections make cross-contamination structurally impossible instead of disciplinary.

**Cheap to implement:** `CampaignGenerator.__init__` already takes `collection_name` (`generators/campaign_generator.py:24`), and `core/game_initialization.py:44` already parameterizes the game's. This is configuration, not refactoring.

**Plan impact:**
- 0.18 becomes **two indexer passes** — one per collection, different `split_length`.
- 0.15 (payload filters) stays worth doing for within-collection filtering (`rules` vs `lore`), but is no longer load-bearing for cross-domain isolation.
- §10 verification must assert `dnd_documents` contains **zero** chunks whose `document_tag` is `campaigns` or `characters`.
- Campaign generation is now a **first-class supported use case**, not an afterthought — see D2.

### D2 · Campaign authoring is offline; the DM extends but does not author or end *(2026-09-07)*

**Decision:** three-way split of authority over the campaign.

| Concern | Owner | Mechanism |
|---|---|---|
| **Authoring** a new campaign | Offline — you, running `generators/campaign_generator.py` | Produces a campaign JSON. Retrieves from `dnd_reference` (D1) for structural few-shots. |
| **Extending** the current campaign in play | The DM, at runtime | Add quests / NPCs / locations to the *active* campaign. **Requires un-freezing `CampaignConfig`** (`components/campaign_config.py:18`) — already plan item 2.3. |
| **Closing** the story | **Authored, code-detected** | The campaign JSON declares an endgame condition; code evaluates it. The LLM narrates the ending, it does not decide when to end. |

**Why.** Same principle as rules adjudication: the LLM narrates, code adjudicates. A model that currently invents DCs nothing enforces should not hold authority over whether your campaign is over. Rejected full runtime authoring (the DM calling `generate_campaign` as a tool) — it surrenders authorial control of the ending for little gain.

**Gap this exposes.** `data/current_campaign/shards_of_honor.json` has `main_plot`, `encounters`, `hooks`, `rewards` — **all prose, no structure**. There is no endgame condition, no acts, and no quest *objects* (quests are bare title strings, `campaign_config.py:42`). Detecting "the campaign is over" is impossible against the current schema.

**New plan items** (fold into Phase 2, alongside 2.3):

| # | Work |
|---|---|
| 2.12 | **Structured campaign schema.** Promote quests from strings to objects (`id`, `title`, `objectives[]`, `prereqs[]`, `status`). Add an `endgame` block: a declarative condition (e.g. `{"all_of": ["quest:veden_crisis:complete", "npc:nale:defeated"]}`) plus authored closing narration. Migrate `shards_of_honor.json`. |
| 2.13 | **Endgame detection.** Evaluate the `endgame` condition after each state change; on satisfaction, hand the DM the authored closing beat to narrate. Pairs with `complete_quest_objective` (2.3), which currently has zero callers. |
| 2.14 | **Teach the generator the new schema** so freshly generated campaigns emit structured quests + an endgame condition, not prose. Otherwise every generated campaign needs hand-migration. |

**Consequence for D1:** `dnd_reference` is now definitively worth indexing — campaign generation is a supported workflow, not a side tool.

### D3 · Build for N-player parties from day one; ship single-player first *(2026-09-07)*

**Decision:** the architecture must support large parties. Single-PC is a *configuration* of the party path, never a separate code path. Ship 1-PC first, but no design may assume `party_size == 1`.

**This is much cheaper than it looks — the party path already exists below the waterline.** Verified:

- `CombatInitializer.initialize_combat(player_character_ids: List[str], ...)` (`combat_initializer.py:76`) is already party-shaped, and does party-level CR balancing (`_get_party_level`, `:443`).
- `CharacterManager` already has `get_party_snapshot()` (`:692`), `party_size`, `party_roles`, and party-size-aware difficulty (`:602`, `:817`).

**The narrowing to one PC is exactly two lines:**

| Location | Current | Fix |
|---|---|---|
| `orchestrator/pipeline_integration.py:879` | `dto["player_character_id"] = player_chars[0]` | pass the whole list as `player_character_ids` |
| `agents/combat_agent.py:177` | `player_character_ids=[player_char_id]` | forward the list unchanged |

**What genuinely needs building** (the rest is already there):

| # | Work | Phase |
|---|---|---|
| 1.9 | **Party-aware combat turn loop.** Initiative already interleaves all combatants; the player-turn branch must prompt for *the character whose turn it is*, not "the first non-NPC." Folds into 1.8 (resumable state machine) — the resume payload carries `awaiting_input_for: char_id`. | 1 |
| 2.15 | **Party roster + active-character UI.** Out of combat: who is the party, whose action is this, a `switch`/`party` command. Startup selects a *party*, not a character. | 2 |
| 2.16 | **Party-wide state.** Rest, XP, and loot apply to the party; quest state is shared, not per-character. Save/load must round-trip the full roster (0.3-0.5 must serialize *all* characters, not the active one). | 2 |

**Design rule for every item in this plan:** any signature taking a character ID takes a **list**, or takes one ID with the caller iterating. No new code may hardcode `[0]`.

**Consequence:** 0.3-0.5 (save/load) must be built party-first. The current bug — restore creates one character named `"unknown"` — is partly *because* the save path was written single-character. Fixing it correctly means round-tripping the whole roster, which is the same work.

Effort: **+2-3 days across Phases 1-2** (less than the 3-4 estimated before finding the existing party plumbing).

### D4 · UI-agnostic turn API now; simple web app as Phase 5 *(2026-09-07)*

**Decision:** the CLI stays the only interface in this plan, but **no game logic may own the interface**. Every turn — narrative and combat — goes through an API that returns *data*; the CLI is one renderer among future others.

**The contract:**

```python
# Nothing below the interface layer may call input() or print().
result = game.play_turn(player_input)          # -> TurnResult
result = combat.advance(action)                # -> TurnResult

TurnResult = {
  "status": "ok" | "awaiting_input",
  "awaiting_input_for": char_id | None,        # which PC must act (D3: party-aware)
  "prompt": str | None,                        # what to ask them
  "choices": [...] | None,                     # structured, not prose
  "narration": str,
  "state_delta": {...},                        # what changed this turn
}
```

**Why this is nearly free.** Item 1.8 already requires removing the blocking `input()` from `CombatSessionManager` and returning `awaiting_player_input`. D4 only generalizes that from "combat" to "everything." The marginal cost is small; the cost of *not* doing it is rewriting the turn loop a third time.

**Why it is not optional.** D3 commits to large parties. Several people cannot share one terminal, and Phase 3's durable cross-process resume is pointless if nothing can reconnect to a paused game. A UI-coupled turn loop would waste both.

**Rules:**
- `haystack_dnd_game.py` may call `input()`/`print()`. Nothing in `components/`, `agents/`, `orchestrator/`, or `core/` may.
- Combat's resume payload carries `awaiting_input_for: char_id` — the party-aware hook from D3.
- Choices are structured data, never pre-rendered strings.

### Phase 5 — Simple web app *(future; after Phases 0-4)*

Explicitly **out of scope for this plan**, recorded so the API above is built to accommodate it.

| Item | Notes |
|---|---|
| 5.1 | **Streamlit app** (or equivalent) over the D4 turn API — chat-style narration, structured choice buttons, character sheet sidebar, party roster with whose-turn-it-is highlighting. Streamlit is the right first choice: pure Python, no frontend build, and it re-renders from state each interaction, which matches a turn-based game. |
| 5.2 | **Session/campaign picker** — list saves, resume one. Depends on multi-slot saves (currently a single hardcoded `haystack_save.json`). |
| 5.3 | **Party play.** Streamlit's single-session model is the limitation here, not the backend. If several people need to act from different browsers, this becomes FastAPI + a real frontend; the D4 API supports either. |
| 5.4 | **Combat view** — initiative order, HP bars, positions on a grid (Phase 1.1 gives entities real positions, so a map view becomes possible). |

Prerequisite: **Phases 0-4 complete and the CLI fully working.** Do not start the UI while the backend is still returning placeholder NPC strings and discarding retrieved lore — you would be building a window onto a broken game.

Rough effort: 3-5 days for 5.1-5.2 given a clean D4 API; 5.3 is a larger piece.

### D5 · Tiered adjudication with an LLM rules-judge and a promotable ruling log *(2026-09-07)*

**Decision:** never block play for a missing rule. Resolve through four tiers, always record which one fired, and let the LLM act as a **rules judge** — but a *grounded* one that must consult the source before ruling.

| Tier | Resolver | Trust | Player sees |
|---|---|---|---|
| **1 · Canonical** | Tier-2 JSON automation tree (§8) | Authoritative | nothing special |
| **2 · Composed** | DM composes from existing primitives (Lashing + improvised-weapon attack) | High — every part is canonical | nothing special |
| **3 · Judged** | **LLM rules-judge**: retrieves the Handbook/SRD, reasons, rules legal-or-not, sets a DC/cost, and **writes the ruling to the log** | Provisional | *"House ruling"* marker |
| **4 · Narrative** | No mechanical resolution; pure narration | Flavor only | *"No mechanical effect"* |

**The rules-judge (Tier 3) — mandatory constraints.** This is the part that makes it trustworthy rather than a hallucination with a badge:

1. **Grounded, never from memory.** The judge is a *tool-using* call that must first retrieve from `dnd_documents` (rules tag: Handbook + SRD). It rules *from retrieved text*, and its output cites the chunk(s) it relied on. A ruling with no citation is downgraded to Tier 4. This is the whole reason 0.17 (index the Handbook) and 0.2 (make retrieval reach the prompt) are prerequisites — **Tier 3 cannot work until both ship.**
2. **Structured output, not prose.** The judge emits a real ruling object, so code — not the model — applies the mechanics:
   ```json
   {"legal": true, "reason": "Basic Lashing can affect objects; treat the boulder as an improvised weapon.",
    "cost": {"stormlight": 1}, "resolution": {"type": "attack", "dc": 13, "damage": "2d6[bludgeoning]"},
    "cites": ["radiant-handbook#p47", "srd#improvised-weapons"], "confidence": "high"}
   ```
3. **Consistency via the ruling log.** Every Tier-3 ruling is appended to `data/rules/rulings.json`. **Before judging, the judge searches prior rulings for the same situation and must follow one if it exists.** This is what stops the classic failure — the same action costing 1 Stormlight today and 3 tomorrow. Precedent binds.
4. **The judge may say no.** `legal: false` is a valid, expected outcome — it rules on legality, it does not rubber-stamp. But a refusal must cite a rule, exactly like an approval.

**Promotion path — this is the payoff.** Rulings are not a dead log; they are a queue:

```
Tier 3 ruling fires → appended to rulings.json with a use counter
     → recurs (used ≥ N times, or you flag it) → you review it
     → promoted into data/rules/stormlight/*.json as a canonical Tier-1 entry
```

The ruleset **grows by play**. This is the concrete answer to "one-time extraction won't capture all the rules" (§9c): it won't, and the rules you actually need are exactly the ones that keep coming up. Supersedes the passive logging in 2.11.

**Why this is safe enough.** Three properties, none of which the current system has: rulings are *grounded* (cited retrieval), *consistent* (precedent binds), and *legible* (the player sees the marker, you review before promotion). The model gets discretion; it does not get to be invisible or inconsistent about it.

**New plan items:**

| # | Work | Phase |
|---|---|---|
| 3.6 | **Rules-judge tool** — retrieval-grounded, structured `Ruling` output, refuses without citations. One of the Phase 3.1 DM tools. | 3 |
| 3.7 | **`rulings.json` store** — append, search-by-situation, use counters. Precedent lookup runs *before* every Tier-3 judgment. | 3 |
| 3.8 | **Provenance on every adjudication** — tier + citations recorded; Tier 3/4 surfaced to the player as "House ruling" / "No mechanical effect." | 3 |
| 2.11 | *(revised)* Rank recurring Tier-3 rulings as the promotion backlog, instead of merely logging gaps. | 2 |

**Dependency:** Tier 3 is unusable before 0.17 + 0.2. Until then the system runs on Tiers 1/2/4 only — which is still strictly better than today.

### D6 · "Done" = one complete campaign, start to authored finish *(2026-09-07)*

**Decision:** v1 ships when **`Shards of Honor: The Veden Crisis` is playable from opening hook to authored endgame** — with a party, real combat, real skill checks, and rulings that promote. Everything the campaign does not exercise is v2.

**Acceptance test (runnable, not a judgment call):** an automated playthrough reaches the endgame condition (D2) with no crash, no placeholder string, and no unhandled error in the log.

**The campaign defines the scope.** From `data/current_campaign/shards_of_honor.json` — levels **1-10**, **5 sessions**, 4 key NPCs, 3 locations, 4 encounters. Its plot dictates what v1 must support:

| Campaign requirement | Plan item | v1? |
|---|---|---|
| "first spren bond… speaking their First Oath" | 2.8 oaths wired to input | **Required** — this is session 1's inciting mechanic, and `speak_oath` currently has 0 callers |
| "speaking higher oaths and growing in power" | 2.5 XP + `level_up()` | **Required** — 1→10 progression is the campaign's spine |
| "gather three ancient artifacts" / 3 locations | 2.6 location graph + travel | **Required** |
| "travelling to three key locations" over 5 sessions | 2.5 short/long rest | **Required** — multi-session attrition is meaningless without recovery |
| 4 encounters + a mass-battle finale | Phase 1 (all) | **Required** |
| Radiant powers as the central fantasy | 2.7 Lightweaver surges | **Required** — both shipped PCs are Lightweavers with zero implemented Surges |
| Party of Radiants fighting together | D3 party support | **Required** |
| Voidbringers / corrupted singers as enemies | 1.x NPC stat generation | **Required** (exists; needs the registry fix 0.1) |
| Death and consequence across 5 sessions | 2.5 death saves | **Required** |
| — | Currency / shops / economy | **v2** — campaign has `rewards`, no merchants |
| — | Crafting, downtime, strongholds | **v2** — not in the plot |
| — | Multiclassing | **v2** — single-class Radiants |
| — | Mounted / vehicle / aerial combat | **v2** — though Windrunner flight brushes this; keep Lashing narrative-only in v1 |
| — | Full spellcasting + slot management | **v2 (partial in v1)** — Surges are the magic system here; standard 5e slots only as far as the classes need |

**v2 backlog** (recorded so v1 can close cleanly):

1. **Economy** — currency (no field exists today), shops, loot tables, encumbrance.
2. **Downtime** — crafting, research, faction work between sessions.
3. **Multiclassing** — `character_class` is a single string today.
4. **Tactical combat depth** — cover, opportunity attacks, reactions (Shield/Counterspell), grapple/shove, AoE templates, aerial movement for Windrunners.
5. **Full spell system** — slots, preparation, concentration, rituals for non-Radiant classes.
6. **Campaign #2** — proving `campaign_generator` output is playable end-to-end (D2's 2.14 is the prerequisite).
7. **Phase 5 web app** (D4) — Streamlit, then multi-browser party play.
8. **Absorb-and-delete `dnd_engine`** (§4) — port the used subset into first-party code under real tests.
9. **The remaining 12 of 14 engine conditions**, if the campaign's encounters don't exercise them.
10. **Bulk rules extraction** — beyond what D5 promotion surfaces during play.

**Consequence for 2.10 (LLM-assisted extraction):** it now has a stopping point. Extract the rules `Shards of Honor` actually exercises — Surgebinding, oaths, the four encounter types — and let D5's promotion path handle the long tail as it comes up in play. Do **not** try to structure all 299 pages before v1.


---

## 14. Delivery Log

### Phases 0-4: complete

| Phase | Result |
|---|---|
| **0** Stop the bleeding | Saves preserve state; lore reaches the DM *and* includes the Cosmere ruleset; two collections (D1); structure-aware chunking; dice stop lying |
| **1** Combat works | Attacks land and deal damage; party-aware; resumable; conditions and surges functional |
| **2** Make it a game | Skill checks, memory, quests, XP/levels/rests/death saves, travel, three-tier rules, party support |
| **3** Make it agentic | Tool-using DM, grounded rules-judge, durable turns, retry-with-reasoning |
| **4** Hygiene | Dead code deleted, current SDK, reproducible build, honest docs |

**Tests: 380 non-combat + 174 combat, 0 failures.** Baseline at audit was
65 failed / 131 passed / 6 errors, with `pytest tests/` aborting entirely.

### Bugs found during implementation that the audit missed

The audit found six. Implementation found eleven more, each verified by execution:

1. **Every character had all six ability scores stuck at 10.** `AbilityConfig`'s field is `ability_score`, not `score`; pydantic silently ignored the value. No STR on attacks, no DEX on AC, no CON on HP.
2. **All three Roshar surges were unconstructible.** Hand-written `__init__` without `super().__init__()`, so pydantic never initialised the model — *no surge had ever worked*, independent of the guard problem.
3. **The requested DC was discarded.** DC 5 and DC 25 both resolved as 14 and both succeeded ~58%; difficulty had no effect on outcomes.
4. **Max HP was under-reported everywhere.** `get_max_hit_dices_points()` omits `max_hit_points_bonus`; a 7 HP goblin read as 17 at all four call sites.
5. **The resolver never received the combat state.** Built with `combat_state={}` and a comment saying "will be set by session manager" — nothing ever set it, so HP never synced.
6. **The turn loop could spin 1001 iterations** when an action failed to consume the economy, then report `outcome: "unknown"`.
7. **`campaign_generator.py` was unimportable** — it imports a module that does not exist, which is why D1's `dnd_reference` collection had no working consumer.
8. **My own Cosmere costs were wrong.** Extraction from the Handbook proved the real system is an expendable *dice* economy, not per-use spheres. Also: Dustbringer's surges, and Bondsmith being unplayable (nine orders, not ten).
9. **Party progress was silently lost on load.** `add_character` ignored the 2.5 fields, so XP reset to 0 while levels survived — making it look correct.
10. **The endgame could never fire.** Conditions use quest IDs; the engine stores titles.
11. **Chunking was structure-blind.** 78% of Handbook chunks started mid-word, 0% at a heading, 92 table headers severed from their rows.

Plus two in my own work, caught by tests I wrote: the rules-judge's grounding
regex captured whole sentences as single tokens (leaving it ungrounded on every
call), and the SDK port broke on `ChatMessage.content`, which Haystack removed —
caught only by a **live** API call, not by unit tests.

### The methodological point

Every one of these was a case where **the call happened and the effect did not**.
That is why §12's rule is to assert on observable end state, and why plan 1.3
(replacing the mocked engine wrapper with the real one) mattered more than any
feature: the mock-based suite reported "96% passing" while five subsystems were
silently broken.

### Known-open

- `test_combat_integration.py::test_full_combat_session` — its generated NPCs
  never get engine entities. Verified in isolation that the real code path works;
  this is test-harness wiring. **Left failing rather than papered over.**
- **Phase 5** (Streamlit UI) and D6's v2 backlog remain by design.

### The 12th missed bug: a component built but never adopted *(2026-09-09)*

`components/durable_turns.py` was delivered with passing tests that genuinely
prove cross-process resume — and **nothing imported it**. `play_turn()` called
the orchestrator directly, so the running game had no durable turns at all;
`grep -rn DurableTurnLoop` outside the module matched only its own tests. Phase 3
was nevertheless marked ✅ DONE on the strength of those tests.

This is the same failure mode as the other eleven, one level up: *the component
worked and was not connected*. A unit test proving a component works says nothing
about whether the product uses it. The fix (wiring `play_turn()` through the loop
via `resolve_turn()`, plus `begin_turn()`/`resume_turn()` for D4) is covered by
`tests/test_durable_turn_wiring.py`, which asserts on the WIRING — including a
test that spawns two interpreters against one checkpoint file, because that is
the only way to prove a turn survives process exit.

Corollary for §12: two Phase-3 tests asserted on `inspect.getsource(play_turn)`
containing `_remember("user"`. They broke on this refactor while the behaviour
was intact, and would equally have passed on a call that recorded nothing. Both
now assert on the conversation history itself.

### Live-API findings *(2026-09-09)*

Once `scripts/playtest.py` ran against the real API, six further defects surfaced
that no offline test could reach — every one of them a 200 OK or a config value
that never applied:

1. `tools` + `response_mime_type="application/json"` → 400. The scenario agent
   had both, so **every** scenario turn fell back to a canned scene.
2. Tool schemas carried `additionalProperties`/`anyOf` (from `Dict[str, Any]` and
   `Optional[...]`), which Gemini's dialect rejects — killed the NPC pipeline.
3. `content.parts` present but `None` on a 200 OK → `TypeError`, reported as
   "Gemini API error", blaming the API for a parsing bug.
4. Reasoning tokens counted against `max_output_tokens`: `thoughts_token_count`
   of 802 and 956 against a 1000-token cap truncated the intent JSON mid-string.
5. **The tuned per-agent LLM settings were dead code.** `load_config_from_environment()`
   — the path `get_global_config_manager()` actually takes — rebuilt every config
   from scratch, so with env vars unset `max_tokens` and `temperature` were `None`
   for every agent. The scenario agent never received its 8000-token cap.
6. `get_skill_data()`'s unknown-actor branch omitted `"breakdown"`, which the
   7-step pipeline subscripts directly → `KeyError` destroyed four skill checks,
   because the LLM wrote `"aggi"` for the character stored as `"Aggi"`.

