# Merged Modular DM Assistant — Final Architecture & Implementation Instructions

This document contains:

1. A cleaned, merged architecture diagram (Mermaid) for the Modular DM Assistant.
2. A step-by-step **actionable** set of changes a coding assistant can apply to your codebase to implement the merged architecture and refactor the system.

---

## Merged Architecture Diagram

```mermaid
flowchart TB
    User[👤 DM User Input]
    User --> DMA[🎭 ModularDMAssistant]

    %% Command registry and cache middleware
    DMA --> CR[📜 CommandRegistry & Parser]
    CR --> Cache[💾 CacheManager Middleware]
    Cache --> AO[🤖 AgentOrchestrator]

    %% Agent Layer (core)
    AO --> CMA[📚 CampaignManagerAgent]
    AO --> GEA[⚙️ GameEngineAgent]
    AO --> SMA[🕒 SessionManagerAgent]
    AO --> ChMA[🧑‍🤝‍🧑 CharacterManagerAgent]
    AO --> InvA[🎒 InventoryManagerAgent]
    AO --> SpA[✨ SpellManagerAgent]
    AO --> XPA[📈 ExperienceManagerAgent]
    AO --> SGA[🎲 ScenarioGeneratorAgent]
    AO --> CEA[⚔️ CombatEngineAgent]
    AO --> DSA[🎲 DiceSystemAgent]
    AO --> NCA[👥 NPCControllerAgent]
    AO --> REA[📖 RuleEnforcementAgent]
    AO --> HPA[🔍 HaystackPipelineAgent]

    %% Narrative and context
    SGA --> NCT[📈 Narrative Continuity (enriched context)]
    NCT --> HPA

    %% Pipeline & error handling (lightweight)
    AO --> AER[🔧 AdaptiveErrorRecovery (optional light)]
    AO --> Logger[📝 Debug/Telemetry]

    %% Save/Load
    GEA --> Save[💾 Save/Load System]

    %% Monitoring toggles
    DMA --> PMD[📊 Debug Mode (lightweight logs)]
```

---

## Implementation Instructions — Overview

Goal: implement your D&D-focused architecture (Session, Inventory, Spells, XP, etc.), while adding the maintainability and debug improvements (CommandRegistry, CacheManager, lightweight logging and retry wrappers).

These instructions are ordered and formatted so a coding assistant can apply them directly: file edits, new files to add, functions to implement, tests to create.

> **Assumptions**: repository contains `modular_dm_assistant.py` and the agents described in your original architecture. Use the same package structure (`agents/` or root-level .py files). Adjust imports if your structure differs.

---

## Phase 0 — Repo & Safety Prep

1. Create a new Git branch: `feature/merged-architecture-refactor`.
2. Add `TODO` and `DEPRECATION` comments where old components will be removed.
3. Add a basic unit-test harness if not present (pytest). Create `tests/test_smoke.py` which imports `ModularDMAssistant` and asserts initialization.

---

## Phase 1 — Core Infrastructure

### 1. Add `command_registry.py`

**New file:** `command_registry.py`

- Export a `CommandRegistry` class with methods:
  - `register(pattern: str, handler: Callable, metadata: dict = None)`
  - `match(command_text: str) -> Optional[HandlerMatch]` (returns handler and extracted args)
  - `list_commands()`
- Provide a decorator helper `@command(pattern, metadata={})` to register functions.

### 2. Add `cache_manager.py`

**New file:** `cache_manager.py`

- Export `CacheManager` class with:
  - `get(key)` / `set(key, value, ttl=None)` / `invalidate(key)`
  - `make_key(agent_id, action, data)` helper
  - Simple TTL handling (in-memory dict + timestamps)
- Provide config for TTLs: `SCENARIO_TTL=3600`, `RULES_TTL=86400`, `CAMPAIGN_TTL=43200`.

### 3. Add `debug_logger.py`

**New file:** `debug_logger.py`

- Simple wrapper around Python `logging` with `enable_debug` toggle.
- Methods: `log_call(agent, action, data)`, `log_cache_hit(key)`, `log_error(err, context)`.

### 4. Modify `modular_dm_assistant.py`

- In `ModularDMAssistant.__init__`, instantiate `CommandRegistry`, `CacheManager`, and `DebugLogger`.
- Replace direct keyword routing inside `process_dm_input()` with `CommandRegistry.match(...)`.
- Route through cache: `key = cache.make_key(agent, action, data)` → `cache.get(key)` → if miss, call `AgentOrchestrator` and `cache.set(key, result, ttl)` (skip caching dice rolls).

---

## Phase 2 — Add Core D&D Agents

For each new agent below, create a file `agents/<agent_name>.py` (or root-level if preferred). Each agent must subclass a `BaseAgent` (create `agents/base_agent.py` if missing) with lifecycle hooks: `initialize()`, `handle(command)`, `on_load_campaign(data)`.

### 5. SessionManagerAgent (new)

**File:** `agents/session_manager_agent.py`

- Methods to implement: `start_session`, `end_session`, `process_rest(rest_type)`, `track_time(minutes)`, `get_session_status`.
- Persist session metadata to `GameEngineAgent` via orchestrator messages.

### 6. InventoryManagerAgent (new)

**File:** `agents/inventory_manager_agent.py`

- Methods: `get_inventory`, `add_item`, `use_item`, `equip_item`, `transfer_item`.
- Ensure items have schema `{id, name, type, effects, quantity, equipped}`.
- Hook into `CombatEngineAgent` to adjust modifiers.

### 7. SpellManagerAgent (new)

**File:** `agents/spell_manager_agent.py`

- Methods: `get_spell_slots`, `cast_spell`, `restore_spell_slots`, `get_known_spells`, `apply_spell_effect`.
- Represent spell effects with expiry timestamps stored in game state.

### 8. ExperienceManagerAgent (new)

**File:** `agents/experience_manager_agent.py`

- Methods: `award_xp`, `check_level_up`, `process_level_up`, `get_xp_status`.
- Provide hooks for both milestone and XP-based progression.

---

## Phase 3 — Gameplay Integration & Refactor

### 9. Move Combat Parsing into CombatEngineAgent

- Add `start_combat_from_text(scenario_text: str, context: dict)` to `CombatEngineAgent`.
- Refactor `_handle_combat_option()` in `modular_dm_assistant.py` to call orchestrator with `action: start_combat_from_text` and remove parsing logic there.

### 10. ScenarioGeneratorAgent & Narrative Continuity

- Keep `ScenarioGeneratorAgent` as the single authority for narrative continuity (enriched context module inside SGA). Implement `get_enriched_context(campaign_id, game_state)` which aggregates: campaign, recent events, important NPCs and player statuses.
- Remove separate `NarrativeContinuityTracker` file if it exists; migrate tests and logic to SGA.

### 11. Hook Character/Inventory/Spells/XP into Scenario Outcomes

- After scenario resolution, orchestrator should trigger:
  - `ExperienceManagerAgent.award_xp(...)`
  - `InventoryManagerAgent.add_item(...)` (loot)
  - `SpellManagerAgent.apply_spell_effect(...)` (ongoing effects)

### 12. Save/Load Centralization

- Move save serialization to `GameEngineAgent.save_game(name)` and `load_game(name)`. Update `modular_dm_assistant` to call these methods for save/load commands.
- Ensure `GameEngineAgent` snapshot includes all agent minimal state or references for reconstruction.

---

## Phase 4 — Reliability & Debugging

### 13. Lightweight Adaptive Error Recovery

- Implement a small `retry_wrapper` in `AgentOrchestrator` call path that:
  - Catches transient exceptions (network/timeout)
  - Retries once with a backoff
  - Logs to `DebugLogger`
- Keep more advanced `AdaptiveErrorRecovery` disabled by default; implement as an opt-in strategy if `config.adaptive_recovery = True`.

### 14. Debug Mode & Logging

- Add CLI/config flag `--debug` or `ModularDMAssistant(debug=True)`.
- When enabled, `DebugLogger` logs: command matched, cache hits/misses, agent calls and durations, errors, and payload sizes.

### 15. Unit & Integration Tests

- Add unit tests for every new agent in `tests/agents/test_<agent>.py` covering nominal behaviors.
- Integration test: `tests/test_scenario_flow.py` which simulates: start session → load characters → generate scenario → pick combat → start combat → award xp → save game.

---

## Phase 5 — Cleanup and Migration

### 16. Deprecation & Removal

- Mark old components for removal, keep compatibility shims that forward to new agents for at least one minor release.
- Remove `RAGAgent`, `SmartPipelineRouter`, `PerformanceMonitoringDashboard` only after integration tests pass.

### 17. Documentation

- Update README with new command syntax and toggles.
- Add agent-level docs in `/docs/agents.md`.

### 18. Release & Rollout Plan

- Merge branch to `develop`, run CI tests.
- Stage rollout: enable `debug=True` in staging to audit behavior for 1–3 full sessions.
- Then flip `debug=False` in production.

---

## Implementation Notes & Code Snippets

Include these snippets where appropriate. Adjust names to match your codebase.

**Command registration example:**

```python
# command_registry usage
registry.register(r"^roll\s+(?P<expr>d\d+)$", handler=dice_handler, metadata={"agent":"dice"})

# decorator
@registry.command(r"^start session$")
def start_session_handler(match, assistant):
    return assistant.orchestrator.send("session_manager", "start_session", {})
```

**Cache manager usage in ModularDMAssistant:**

```python
key = cache.make_key(agent_id, action, data)
result = cache.get(key)
if result is None:
    result = orchestrator.send(agent_id, action, data)
    if should_cache(agent_id, action):
        cache.set(key, result, ttl=TTL_MAP[action_type])
return result
```

**Combat delegation:**

```python
# in modular_dm_assistant
if command_type == "combat_intent":
    return orchestrator.send("combat_engine", "start_combat_from_text", {"text": scenario_text, "context": ctx})
```

---

## Acceptance Criteria (checks a coding assistant can use)

1. `CommandRegistry` supports registration and matching for existing commands.
2. `CacheManager` correctly caches scenario and rules queries per TTL and never caches dice rolls.
3. New agents exist and expose the methods listed above.
4. Combat parsing/initialization is fully inside `CombatEngineAgent`.
5. Save files can be produced and restored with `GameEngineAgent.save_game()`/`load_game()`.
6. Integration test reproduces a full session flow.

---

## Next Steps

- Run the unit tests created in `tests/`.
- Execute the integration test and address issues.
- After verified, remove compatibility shims and deprecated components.

---

*End of document.*

