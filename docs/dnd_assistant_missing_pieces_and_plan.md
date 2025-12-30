
# D&D Assistant — Missing Pieces & Implementation Plan (Modular, Orchestrator‑First)

> Goal: make every agent talk only through the Orchestrator, add a robust Input Parser that compiles natural language to structured commands, and wire deterministic routing for tasks like *“player chooses an option → (maybe) skill check → character lookup → roll/compare → optional RAG context → scenario consequence”*.

---

## 1) Quick Recap of Current Shape (what we’ll build on)

- **Multi‑agent** design with an Orchestrator + Message Bus.
- **Rich agents** for Rules/Combat/Characters/Scenario/RAG/etc.
- **Manual command handler** that maps text to actions.
- **JSON persistence**, caching, and resilience patterns.

> We will **not** change the domains; we’ll add *contracts, routing, and a compiler layer* to make flows explicit, testable, and modular.

---

## 2) What’s Missing / Gaps to Close

### A. Input → Command Compilation
- Natural language currently maps to actions, but lacks a **formal command envelope** (headers, correlation, intent type) and **typed parameters**.
- No **slot‑filling & disambiguation** pipeline (entity/number/target extraction, advantage state, DC source).

### B. Orchestrator as the Single Integration Surface
- Make the **Orchestrator the only caller** between agents (no side‑calls).
- Add **routing rules**, **capability registry**, **timeouts**, **retries**, and **backpressure**.
- Introduce **Sagas** for multi‑step tasks (skill checks, complex actions).

### C. Agent Contracts (Stable Interfaces)
- **IDL-like contracts** for messages and results (schemas for `COMMAND`, `QUERY`, `EVENT`, `RESULT`, `ERROR`).
- **Versioned capabilities** (e.g., CharacterManager v1 advertises: `get_character`, `get_skill_bonus`, `get_passive_score`).
- **Idempotency** and **exactly‑once semantics** guidelines (retries with `message_id` + dedupe).

### D. Context Broker & Policy for RAG/Rules
- Deterministic **Context Broker** that decides *if/when* to call RAG or Rules based on **policy** (e.g., “DC source is missing → query Rules; lore gap → query RAG”).

### E. Deterministic Skill‑Check Pipeline
- **Choice → NeedsCheck? → Ability/Skill source → Advantage/Disadvantage → DC source → Roll & Compare → Consequence**.
- Standardize **DC provenance**: fixed by scenario, table‑derived, contested vs passive score, or GM override.
- **GameState write isolation**: consequences applied via **GameEngine** only.

### F. Event Model & Auditability
- Normalize **GameEvent** types (`STATE_CHANGED`, `ROLL_PERFORMED`, `RULES_REFERENCED`, `RAG_REFERENCED`, `SCENARIO_EMITTED`).
- **Structured logs + traces** (correlation/causation IDs) and **decision logs** for adjudication transparency.

### G. Persistence & Read Models
- Add a **Repository interface**; keep JSON as an adapter initially.
- Optional **CQRS**: Commands write through GameEngine; read models are projected for fast UI/agent reads.

### H. Policy/House‑Rules Layer
- Central **Policy Engine** to layer house rules (e.g., crit rules, passive perception formulae, advantage stacking).

### I. Security / Roles
- **Role‑aware commands** (Player vs DM vs System), **session binding**, and **permission checks** in Orchestrator.

### J. Test Harness
- **Contract tests** for each agent.
- **End‑to‑end saga tests** (happy path + timeouts + retries + compensation).
- **Golden transcripts** for narrative/stability checks.

---

## 3) Command Model & Input Parser (Compiler)

### 3.1 Command Envelope (standard)
```json
{
  "header": {
    "message_id": "uuid",
    "timestamp": "iso-8601",
    "intent": "SKILL_CHECK|ACTION|RULE_QUERY|SCENARIO_CHOICE|NPC_DIALOGUE|...",
    "actor": {"player_id": "p1", "role": "PLAYER|DM|SYSTEM"},
    "correlation_id": "uuid",
    "saga_id": "uuid",
    "ttl_ms": 8000,
    "priority": "normal|high",
    "version": "1.0"
  },
  "body": {
    "utterance": "I try to pick the lock quietly",
    "entities": {
      "target": "storeroom lock",
      "skill": "sleight_of_hand",
      "ability": "dexterity",
      "advantage": "none|adv|disadv|from_help",
      "dc": null,
      "context_hints": ["stealthy", "time_pressure"]
    },
    "options": {
      "allow_rag": true,
      "allow_rules_lookup": true,
      "house_rules_profile": "default"
    }
  }
}
```

### 3.2 Parser Pipeline
1. **Lex/Normalize** (lower, strip noise, standardize synonyms).
2. **Intent Classifier** (regex + rules + ML optional).
3. **Entity Extraction** (skills/abilities/targets/quantities).
4. **Slot Filling & Defaults** (advantage state from conditions; infer contested vs fixed DC).
5. **Validation** (missing mandatory fields → `DISAMBIGUATE` command to UI/DM).

### 3.3 Command → Sub‑Commands
- Compile high‑level intents into **agent‑addressable sub‑commands**; the Orchestrator will fan‑out/fan‑in per saga.

---

## 4) Routing & Sagas (Orchestrator‑Only IPC)

### 4.1 Message Types
- `COMMAND`, `QUERY`, `EVENT`, `RESULT`, `ERROR`, `HEARTBEAT`

### 4.2 Standard Headers
- `message_id`, `correlation_id`, `causation_id`, `saga_id`, `ttl_ms`, `attempt`, `reply_to`

### 4.3 Capability Registry (examples)
```yaml
CharacterManager@1:
  get_character: {in: {character_id}, out: {sheet}}
  get_skill_bonus: {in: {character_id, skill}, out: {bonus, expertise, prof}}

DiceAgent@1:
  roll_check: {in: {kind: ability|skill|save, mod, adv_state}, out: {rolls, total}}

RulesAgent@1:
  derive_dc: {in: {task, env, contested_vs: passive|skill|ac}, out: {dc, source, notes}}

GameEngine@1:
  apply_effects: {in: {effects[]}, out: {new_state, events[]}}

ScenarioAgent@1:
  consequence: {in: {context, outcome}, out: {narrative, hooks[], effects[]}}
```

### 4.4 Core Sagas (sketches)

#### Saga: **Player Choice With Possible Skill Check**
1. `SCENARIO_CHOICE` (from Parser) enters Orchestrator.
2. **Check** scenario metadata for `requires_check` + `skill_hint`.
3. If unknown, call **RulesAgent** to **derive DC**; if *contested*, ask **CharacterManager** for defender/passive score.
4. Call **CharacterManager** for actor’s **skill/ability mod** + bonuses; compute adv/disadv from state & policy.
5. Call **DiceAgent** → roll.
6. Compare vs DC (Orchestrator does the math or delegates to **GameEngine** for authoritative compare).
7. Optional **Context Broker**: if `context_needed`, query **RAG** for lore/rules snippets → attach to decision log.
8. Call **ScenarioAgent.consequence** with `{outcome, context}` to generate narrative + effects.
9. Call **GameEngine.apply_effects** (state changes only happen here).
10. Emit **events**; return deterministic **Result** to UI.

#### Saga: **Skill Contest (e.g., Stealth vs Passive Perception)**
- Derive opponent **passive** via **CharacterManager** (and policy).
- Rules/Policy determines perception advantage from light/conditions; adjust passive accordingly.
- Roll stealth, compare, apply consequences (visibility flag, alert level).

#### Saga: **NPC Dialogue With Persuasion Check**
- Parser → `NPC_DIALOGUE` with `intent: persuade`.
- Rules/Policy set DC from NPC attitude; CharacterManager gives CHA mod + prof.
- Roll, compare, call **ScenarioAgent** to branch dialogue; **GameEngine** updates relationship meter.

---

## 5) Context Broker & Policy

### 5.1 Context Broker Decision Table (simplified)
| Need | Source | Trigger |
|---|---|---|
| DC for task | RulesAgent | `requires_check && !dc` |
| Lore gap | RAGAgent | `entities.target not in state && allow_rag` |
| House rule | PolicyEngine | Always consulted for overrides |
| Advantage state | PolicyEngine + CharacterManager | Conditions, help, class features |

### 5.2 House‑Rule Profiles (examples)
- `default`: RAW passive = `10 + mod + prof?`  
- `gritty`: Travel exhaustion thresholds; long rest rules.
- `cinematic`: Wider success bands; bonus inspiration triggers.

---

## 6) Code Structure (modular, packages)

```
dnd/
  core/
    messages.py           # envelopes, headers, schemas
    bus.py                # orchestrator-only routing
    orchestrator.py       # sagas, timeouts, retries
    registry.py           # capability registry
    policy.py             # house rules engine
    context_broker.py     # RAG/Rules decision layer
  parser/
    compiler.py           # NL → CommandEnvelope
    entities.py           # extractors, slot filling
    intents.py            # intent classification
  agents/
    character_manager/
    dice/
    rules/
    scenario/
    rag/
    game_engine/
    combat/
    npc/
    ... (adapters per contract)
  storage/
    repo.py               # interfaces
    json_adapter.py       # keep existing JSON impl
  observability/
    logging.py            # structured logs
    tracing.py            # correlation/causation
    metrics.py            # latency, error rates
  tests/
    contracts/
    e2e_sagas/
    golden_transcripts/
```

---

## 7) Key Interfaces & Pseudocode

### 7.1 Message & Orchestrator
```python
@dataclass
class Header:
    message_id: str
    timestamp: str
    intent: str
    actor: dict
    correlation_id: str
    saga_id: str
    ttl_ms: int
    attempt: int = 0
    reply_to: str | None = None
    version: str = "1.0"

@dataclass
class Message:
    header: Header
    body: dict

class Orchestrator:
    def __init__(self, bus, registry, policy, ctx_broker):
        self.bus, self.registry, self.policy, self.ctx = bus, registry, policy, ctx_broker

    def handle(self, msg: Message):
        if msg.header.intent == "SCENARIO_CHOICE":
            return self._saga_choice_with_check(msg)
        # ... other intent switches

    def _send(self, target, msg) -> Message:
        # add correlation/causation, timeout, retries
        return self.bus.request(target, msg, timeout_ms=msg.header.ttl_ms)

    def _saga_choice_with_check(self, msg: Message):
        sctx = SagaContext.from_message(msg)

        need_check = self._discover_need_check(sctx)   # scenario metadata or parser hint
        if not need_check:
            return self._finalize_without_check(sctx)

        dc = sctx.input.dc or self._derive_dc(sctx)    # RulesAgent + Policy
        actor_mod = self._get_skill_mod(sctx.actor, sctx.skill)
        adv_state = self.policy.compute_advantage(sctx.state, sctx.actor, sctx.skill)
        roll = self._roll_check(actor_mod, adv_state)  # DiceAgent
        outcome = "success" if roll.total >= dc else "failure"

        ctx = self.ctx.build_context_if_needed(sctx)   # RAG/Rules fetch (optional)
        cons = self._scenario_consequence(outcome, ctx) # ScenarioAgent
        effects = cons.effects

        applied = self._apply_effects(effects)         # GameEngine
        return self._result(sctx, applied, logs=[dc, roll, ctx])
```

### 7.2 Input Parser (Compiler)
```python
def compile_utterance(utt: str, state) -> Message:
    intent = classify_intent(utt, state)
    entities = extract_entities(utt, state)  # target, skill, ability, dc hints, etc.
    filled = fill_slots(entities, state)     # advantage from help/conditions, contested?
    validate(filled)
    return Message(header=mk_header(intent), body={"utterance": utt, "entities": filled})
```

### 7.3 Policy Examples
```python
class PolicyEngine:
    def compute_advantage(self, state, actor, skill):
        # help, conditions, features → adv/disadv/none
        ...
    def passive_score(self, ability_mod, proficient, bonus=0):
        return 10 + ability_mod + (bonus if proficient else 0)
```

### 7.4 Context Broker
```python
class ContextBroker:
    def build_context_if_needed(self, sctx):
        if sctx.flags.need_rules:
            rules = ask("RulesAgent", {...})
        lore = None
        if sctx.flags.need_lore:
            lore = ask("RAGAgent", {...})
        return {"rules": rules, "lore": lore}
```

---

## 8) Implementation Phases & Deliverables

### Phase 1 — **Contracts & Core Messaging**
- Message/headers schemas, envelopes, types
- Capability registry + health/heartbeat
- Orchestrator wraps timeouts/retries/backpressure
- Unit tests for bus + orchestrator

### Phase 2 — **Input Parser / Command Compiler**
- Intent classification + entity extraction + slot filling
- CommandEnvelope + validation + disambiguation prompts
- Golden tests for common player utterances

### Phase 3 — **Skill‑Check Saga (golden path)**
- Rules DC derivation + passive contests policy
- Character mod fetch + advantage computation
- DiceAgent integration → compare → GameEngine write
- ScenarioAgent consequence + event emission
- E2E tests: success/failure/edge cases/timeouts

### Phase 4 — **Context Broker + Policy Engine**
- RAG/Rules decision tables
- House‑rules profiles with toggles
- Decision logs for transparency

### Phase 5 — **Observability**
- Structured logs, traces (corr/causation IDs), metrics
- Decision logs for checks and consequences

### Phase 6 — **Persistence Ports & CQRS (optional)**
- Repository interface + JSON adapter
- Projectors for fast read models

### Phase 7 — **Hardening**
- Idempotency keys, dedupe store
- Retry & compensation strategies
- Security/roles enforcement

### Phase 8 — **Test Harness & Tooling**
- Contract tests for each agent
- Saga simulators
- Load tests for bursty inputs

---

## 9) Acceptance Criteria (excerpt)

- **All inter‑agent calls** flow through Orchestrator (enforced by code review/linter).
- **Every user utterance** compiles to a **validated CommandEnvelope**.
- **Skill‑check saga** is deterministic, test‑covered, and logs DC provenance, roll breakdown, and applied effects.
- **GameEngine** is the **only writer** of game state.
- **Context Broker** adds RAG/Rules context only when policy says so.
- **Observability** surfaces correlation IDs and decision logs for every saga.

---

## 10) Worked Example: “I try to pick the lock quietly”

1. Parser → `SCENARIO_CHOICE` with entities `{skill:sleight_of_hand, target:lock, ability:dex}`.
2. Orchestrator → discovers `requires_check=True` from scenario metadata.
3. RulesAgent → `derive_dc(lock_quality, tools, time_pressure)` → `dc=15`.
4. CharacterManager → `get_skill_bonus(pc, sleight_of_hand)` → `+7` (expertise).  
   Policy → advantage? None.
5. DiceAgent → roll d20 → `13+7=20` → success.
6. ContextBroker → not needed (no lore/rule ambiguity).
7. ScenarioAgent → consequence: “door opens silently; guard remains unaware” with `effects=[world.alert_level:-1, inventory:lockpicks-1(durable check)]`.
8. GameEngine → apply `effects`, emit events, persist snapshot.
9. Return **Result** with structured breakdown + narrative.

---

## 11) Nice‑to‑Have Extensions

- **Explain Mode**: attach rule/lore snippets to the result (toggle).
- **What‑if Simulation**: ask Orchestrator to simulate advantage or alternate DCs.
- **Inspiration Hooks**: auto‑offer inspiration on cinematic play (policy).

---

## 12) Risks & Mitigations (brief)

- **Hidden cross‑agent calls** → enforce import lint rules, dependency graph CI check.
- **LLM latency** → cache, parallelize non‑dependent steps, short‑circuit when DC known.
- **State races** → Orchestrator serializes write intents, GameEngine uses transactions.
- **House‑rule drift** → versioned policy profiles + acceptance tests.

---

*End of plan.*
