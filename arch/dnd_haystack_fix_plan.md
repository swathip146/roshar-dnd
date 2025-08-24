
# D&D Orchestrator & Agents — Stabilization & Upgrade Plan

**Goal:** turn your multi‑agent D&D system (Haystack + custom agents) from “often falls back” to **predictable, testable, schema‑driven** flows for: parsing → (optional) RAG → routing → NPC/scenario → rules/skills → response composition.

This document is written for a coding assistant to implement directly. It’s opinionated but **non‑breaking** where possible, and assumes you’re already injecting a Qdrant/DocStore object into agents.

---

## Table of Contents

1. [Design Objectives](#design-objectives)  
2. [New Shared Data Contract (DTO)](#new-shared-data-contract-dto)  
3. [Global Control Flow (State Machine)](#global-control-flow-state-machine)  
4. [Haystack Pipeline Wiring](#haystack-pipeline-wiring)  
5. [Per‑Module Changes](#per-module-changes)  
   - [5.1 `shared_contract.py` (NEW)](#51-shared_contractpy-new)  
   - [5.2 `main_interface_agent.py`](#52-main_interface_agentpy)  
   - [5.3 `context_broker.py`](#53-context_brokerpy)  
   - [5.4 `rag_retriever_agent.py`](#54-rag_retriever_agentpy)  
   - [5.5 `scenario_generator_agent.py`](#55-scenario_generator_agentpy)  
   - [5.6 `npc_controller_agent.py`](#56-npc_controller_agentpy)  
   - [5.7 `pipeline_integration.py`](#57-pipeline_integrationpy)  
   - [5.8 `decision_logger.py`](#58-decision_loggerpy)  
   - [5.9 `saga_manager.py`](#59-saga_managerpy)  
   - [5.10 `haystack_dnd_game.py`](#510-haystack_dnd_gamepy)  
6. [Metadata & Ingest Guidelines (Qdrant/DocStore)](#metadata--ingest-guidelines-qdrantdocstore)  
7. [Validation, Repair & Fallback Policy](#validation-repair--fallback-policy)  
8. [Config, Env & Feature Flags](#config-env--feature-flags)  
9. [Observability & Golden Tests](#observability--golden-tests)  
10. [Phased Rollout Checklist](#phased-rollout-checklist)  
11. [Appendix: Example Prompts & Test Fixtures](#appendix-example-prompts--test-fixtures)

---

## Design Objectives

- **Predictable orchestration**: strict DTO passed through every step; no free‑form opaque strings between tools.
- **Structured outputs**: Scenario/NPC tools must emit validated JSON; auto‑repair once; only then fallback.
- **RAG that actually fires**: permissive gating + meaningful **filters** derived from game context; never silently no‑op.
- **Testability**: golden test turns assert routing, RAG hits, schema validity, and no unwanted fallbacks.
- **Minimal churn**: keep your DI (you already inject Qdrant storage), add guards/validators, not a rewrite.

---

## New Shared Data Contract (DTO)

Create a single DTO type every hop must accept/return.

**`shared_contract.py`**
```python
from typing import TypedDict, Literal, Optional, List, Dict, Any
import uuid, time

RoleType = Literal["scenario","npc_interaction","rules_lookup","meta"]

class Choice(TypedDict, total=False):
    id: str
    title: str
    description: str
    skill_hints: List[str]
    suggested_dc: int
    combat_trigger: bool

class Scenario(TypedDict, total=False):
    scene: str
    choices: List[Choice]
    effects: Dict[str, Any]
    hooks: List[str]

class RAGBlock(TypedDict, total=False):
    needed: bool
    query: str
    filters: Dict[str, Any]
    docs: List[Dict[str, Any]]

class RequestDTO(TypedDict, total=False):
    correlation_id: str
    ts: float
    type: RoleType
    player_input: str
    action: str
    target: Optional[str]
    context: Dict[str, Any]
    rag: RAGBlock
    route: Optional[str]  # "npc" | "scenario" | "rules"
    debug: Dict[str, Any]

def new_dto(player_input: str, ctx: Dict[str, Any]) -> RequestDTO:
    return {
        "correlation_id": str(uuid.uuid4()),
        "ts": time.time(),
        "type": "meta",
        "player_input": player_input,
        "action": "",
        "target": None,
        "context": ctx or {},
        "rag": {"needed": False, "query": "", "filters": {}, "docs": []},
        "route": None,
        "debug": {},
    }
```

> **Rule:** Every tool returns a DTO (or dict with `"dto": ..."`). Never return a stringified dict inside text.

---

## Global Control Flow (State Machine)

Deterministic sequence per turn:

```
normalize_incoming
→ parse_intent (action, target, type)
→ context_broker.assess_rag_need (sets rag.needed/query/filters)
→ (if rag.needed) rag.retrieve (fills rag.docs, keeps filters)
→ route:
    - npc_controller (if target hits known NPC)
    - scenario_generator (default for in‑world actions)
    - rules_lookup (for explicit rules/spell queries)
→ rules/skill manager if any choice implies a check
→ response_compose (merge text + citations + state diffs)
```

On any schema invalidation: **single repair attempt** → if still invalid → fallback response tagged with reasons.

---

## Haystack Pipeline Wiring

Use a single Haystack `Pipeline` with dict payloads:

```
parser  -> broker -> (retriever?) -> router -> {npc | scenario | rules} -> composer
                 \_____________________________/ via DictJoiner
```

- Use `DictJoiner` to merge RAG output back into the DTO before routing.
- Use `ConditionalRouter` (predicate reads DTO fields) to pick the branch.
- All components are registered tools or callable nodes that accept/return DTO.

---

## Per‑Module Changes

### 5.1 `shared_contract.py` (NEW)

**Action:** Add the DTO types + `new_dto()` above.  
**Why:** Single source of truth for shapes, reused everywhere.

---

### 5.2 `main_interface_agent.py`

**Tasks**
1. **Normalize Input**
   ```python
   from shared_contract import new_dto
   def normalize_incoming(player_text: str, game_context: dict) -> dict:
       # lowercase, strip, coarse verb detection, preserve raw input
       return new_dto(player_text.strip(), game_context or {})
   ```

2. **Routing Decision (strict)**
   ```python
   def determine_response_routing(dto: dict, world_state) -> dict:
       # Hard rules first
       if "spell" in dto["action"] or dto["type"] == "rules_lookup":
           dto["route"] = "rules"
       elif dto.get("target") and dto["target"] in world_state.npcs:
           dto["route"] = "npc"
       else:
           dto["route"] = "scenario"
       return dto
   ```

3. **I/O hygiene**: ensure agents exchange DTO via metadata or direct dicts; no stringified JSON blobs.

4. **Register tools** on the Haystack Agent (if using `Agent`) so they are callable within prompts.

---

### 5.3 `context_broker.py`

**Tasks**
- Build filters from context. Loosen thresholds initially.
- Always populate `dto["rag"]` (even when `needed=False`).

```python
DEFAULT_THRESH = {"lore": 0.35, "rules": 0.35, "world": 0.25}

def _build_rag_filters(dto: dict) -> dict:
    ctx = dto.get("context", {})
    f = {}
    for k in ("campaign","location","chapter","faction"):
        v = ctx.get(k)
        if v: f[k] = [v]
    # optional: file_type hints
    if dto["type"] in ("rules_lookup","scenario"):
        f["file_type"] = ["rules","lore"]
    return f

def assess_rag_need(dto: dict) -> dict:
    text = dto["player_input"].lower()
    need = any(w in text for w in ("history","lore","legend","what is","who is","tell me about"))
    dto["rag"]["needed"] = need
    if need:
        dto["rag"]["query"] = dto["player_input"]
        dto["rag"]["filters"] = _build_rag_filters(dto)
    return dto
```

---

### 5.4 `rag_retriever_agent.py`

> You **already inject** the doc store — keep that. Add a guard and unified output.

**Tasks**
- Require a non‑None store or raise (fail fast).
- Use filters passed in the DTO.
- Return normalized `docs` with ids, scores, metadata.

```python
def retrieve_documents(dto: dict, store) -> dict:
    if store is None:
        raise RuntimeError("Document store not set (injected store is None).")
    rag = dto.get("rag", {})
    if not rag.get("needed"):
        return dto
    query = rag.get("query") or dto["player_input"]
    filters = rag.get("filters") or {}
    retriever = store.get_retriever(hybrid=True) if hasattr(store, "get_retriever") else store
    results = retriever.retrieve(query=query, top_k=5, filters=filters)
    dto["rag"]["docs"] = [
        {
            "id": getattr(r, "id", None),
            "score": float(getattr(r, "score", 0.0)),
            "title": getattr(getattr(r, "meta", {}), "get", lambda k, d=None: None)("title"),
            "project": getattr(getattr(r, "meta", {}), "get", lambda k, d=None: None)("project"),
            "file_type": getattr(getattr(r, "meta", {}), "get", lambda k, d=None: None)("file_type"),
            "chunk": getattr(r, "content", ""),
        } for r in results
    ]
    return dto
```

**Optional**: if hybrid not available, fall back to dense retriever.

---

### 5.5 `scenario_generator_agent.py`

**Tasks**
- Enforce **schema** (`Scenario`), add validator + single repair pass.
- Never return unstructured text.

```python
REQUIRED_KEYS = ["scene","choices","effects","hooks"]

def validate_scenario(s: dict) -> list[str]:
    errs = []
    for k in REQUIRED_KEYS:
        if k not in s: errs.append(f"missing {k}")
    if isinstance(s.get("choices"), list):
        for i,ch in enumerate(s["choices"]):
            for k in ("id","title","description","skill_hints","suggested_dc","combat_trigger"):
                if k not in ch: errs.append(f"choices[{i}] missing {k}")
    return errs

def repair_scenario(s: dict, errs: list[str]) -> dict:
    # Deterministic local repair (do not re‑ask LLM if you prefer):
    s.setdefault("scene", "You are in a nondescript chamber.")
    s.setdefault("choices", [])
    s.setdefault("effects", {})
    s.setdefault("hooks", [])
    for i,ch in enumerate(s["choices"]):
        ch.setdefault("id", f"c{i+1}")
        ch.setdefault("title", "Decide")
        ch.setdefault("description", "")
        ch.setdefault("skill_hints", [])
        ch.setdefault("suggested_dc", 12)
        ch.setdefault("combat_trigger", False)
    return s

def create_scenario(dto: dict) -> dict:
    # build prompt from dto + rag.docs (if any), generate scenario: <call your LLM/tool>
    scenario = generate_raw(dto)  # implementation specific
    errs = validate_scenario(scenario)
    if errs:
        scenario = repair_scenario(scenario, errs)
        errs = validate_scenario(scenario)
        dto["debug"]["scenario_repaired"] = True
    if errs:
        dto["debug"]["scenario_errors"] = errs
        dto["fallback"] = True
        dto["scenario"] = minimal_fallback(dto)
    else:
        dto["scenario"] = scenario
    return dto
```

---

### 5.6 `npc_controller_agent.py`

**Tasks**
- Accept DTO, use `dto["target"]` to resolve NPC.
- Emit structured result: `{"npc": {"id","dialogue","attitude_delta","knowledge_refs":[]}}`.
- If `rag.docs` exist and target is a “scholar/quest‑giver”, optionally stitch citations.

---

### 5.7 `pipeline_integration.py`

**Tasks**
- Build a single Pipeline where nodes pass DTO dicts.
- Use `DictJoiner` to merge retriever output.
- Use `ConditionalRouter` reading `dto["route"]`.

**Sketch**
```python
from haystack import Pipeline
from haystack.components.joiners import DictJoiner
from haystack.components.routers import ConditionalRouter

pipe = Pipeline()
pipe.add_component("parser", parser_node)          # normalize + parse intent
pipe.add_component("broker", broker_node)          # assess_rag_need
pipe.add_component("retriever", retriever_node)    # uses injected store, returns dto
pipe.add_component("join", DictJoiner(keys=["*"])) # merge broker+retriever (or pass-through)
pipe.add_component("router", ConditionalRouter(
    cases={
        "npc": lambda dto: dto.get("route") == "npc",
        "rules": lambda dto: dto.get("route") == "rules",
        "scenario": lambda dto: dto.get("route") == "scenario",
    },
    default_case="scenario",
))

pipe.add_component("npc", npc_node)
pipe.add_component("rules", rules_node)
pipe.add_component("scenario", scenario_node)
pipe.add_component("compose", compose_node)

pipe.connect("parser", "broker")
pipe.connect("broker", "retriever", condition=lambda dto: dto["rag"]["needed"])
pipe.connect("broker", "join")
pipe.connect("retriever", "join")
pipe.connect("join", "router")
pipe.connect("router.npc", "npc")
pipe.connect("router.rules", "rules")
pipe.connect("router.scenario", "scenario")
pipe.connect(["npc","rules","scenario"], "compose")
```

---

### 5.8 `decision_logger.py`

**Tasks**
- Log at each checkpoint with the **same** `correlation_id`.
- Prefer line‑delimited JSON for easy grep.

```python
def log_event(dto: dict, stage: str, extra: dict | None = None):
    payload = {
        "ts": dto.get("ts"),
        "cid": dto.get("correlation_id"),
        "stage": stage,
        "route": dto.get("route"),
        "rag_needed": dto.get("rag",{}).get("needed"),
        "rag_docs": len(dto.get("rag",{}).get("docs",[])),
        "flags": {k: dto.get(k) for k in ("fallback",)},
        "extra": extra or {},
    }
    print(json.dumps(payload, ensure_ascii=False))
```

---

### 5.9 `saga_manager.py`

**Tasks**
- Small state keeper per correlation id:
  - current scene, party stats, NPC disposition, pending checks.
- Expose methods:
  - `apply_scenario_effects(dto)`
  - `register_choice(dto, choice_id)`
  - `rollback_last_step(cid)` (optional).

---

### 5.10 `haystack_dnd_game.py`

**Tasks**
- Construct pipeline & inject store into retriever node.
- Expose `run_turn(player_input, game_context)` that:
  1) builds DTO, 2) runs the pipeline, 3) applies saga effects, 4) returns composed message + debug.

**Sketch**
```python
def run_turn(text: str, ctx: dict):
    dto = normalize_incoming(text, ctx)
    out = pipe.run(dto)
    saga.apply_scenario_effects(out)
    return out
```

---

## Metadata & Ingest Guidelines (Qdrant/DocStore)

Tag documents on ingest so filters work:

- `project` / `campaign` (string)
- `location` (e.g., “Baldur’s Gate”, “Dungeon‑Level‑2”)
- `chapter` (int or string)
- `faction` (e.g., “Zhentarim”)
- `file_type` ∈ {“rules”, “lore”, “notes”, “statblock”}
- `title`

> Ensure chunking with overlap (e.g., 512–800 tokens, 10–15% overlap). Keep title in metadata for better display.

---

## Validation, Repair & Fallback Policy

- **Always validate** outgoing structures.
- **Single repair attempt** (deterministic defaults or constrained LLM “fix JSON only” prompt).
- **Fallback** only when repair fails; include `dto["debug"]["scenario_errors"]`.

---

## Config, Env & Feature Flags

- `.env` keys:
  - `RAG_TOP_K=5`
  - `RAG_ENABLE_HYBRID=true`
  - `SCENARIO_DEFAULT_DC=12`
  - `BROKER_RULES_THRESHOLD=0.35`
  - `BROKER_LORE_THRESHOLD=0.35`
- Feature flags read once at start and injected.

---

## Observability & Golden Tests

**Golden tests** assert:
- routing (`npc` / `scenario` / `rules`)
- `rag.needed` correctness & `docs>=1` for lore asks
- schema validity (no missing keys)
- no fallback unless explicitly intended

**Example `tests/golden_turns.jsonl`**
```json
{"in":"talk to the bartender about rumors","ctx":{"location":"tavern"},"expect":{"route":"npc","fallback":false}}
{"in":"what is the legend of the Dragonbone Spire?","ctx":{"campaign":"C1"},"expect":{"rag_docs_min":1,"route":"scenario"}}
{"in":"cast fireball at level 5","ctx":{},"expect":{"route":"rules"}}
{"in":"search the alcove for hidden levers","ctx":{"location":"crypt"},"expect":{"scenario_choices_min":2}}
```

**PyTest sketch**
```python
def assert_basic(out, exp):
    if "route" in exp: assert out["route"] == exp["route"]
    if "rag_docs_min" in exp: assert len(out["rag"]["docs"]) >= exp["rag_docs_min"]
    if "scenario_choices_min" in exp: assert len(out["scenario"]["choices"]) >= exp["scenario_choices_min"]
    if "fallback" in exp: assert out.get("fallback", False) == exp["fallback"]
```

---

## Phased Rollout Checklist

**Phase 0 – Contracts & Guards**
- [ ] Add `shared_contract.py` and import everywhere.
- [ ] Ensure `normalize_incoming()` used at entry.
- [ ] Add non‑None store guard in `rag_retriever_agent`.

**Phase 1 – Broker & RAG**
- [ ] Implement `_build_rag_filters()` and permissive gating.
- [ ] Pass filters/query in DTO; retriever fills docs.

**Phase 2 – Routing**
- [ ] Hard rules for rules lookup, NPC resolution, default scenario.
- [ ] Add `route` to DTO.

**Phase 3 – Scenario Schema**
- [ ] Add `validate_scenario()` and `repair_scenario()`.
- [ ] Ensure non‑string structured return.

**Phase 4 – Pipeline**
- [ ] Single Haystack pipeline with `DictJoiner` + `ConditionalRouter`.
- [ ] Ensure each node passes DTO.

**Phase 5 – Observability & Tests**
- [ ] Add `decision_logger.log_event()` at parser, broker, retriever, router, node exit.
- [ ] Implement golden tests; wire CI check.

---

## Appendix: Example Prompts & Test Fixtures

**Scenario prompt scaffold (LLM)**
```
System: You are a strict scenario composer. Output ONLY JSON for the following schema:
{ "scene": str, "choices": [ { "id": str, "title": str, "description": str, "skill_hints": [str], "suggested_dc": int, "combat_trigger": bool } ], "effects": { ... }, "hooks": [str] }

User context:
- location: {{dto.context.location}}
- party avg level: {{dto.context.average_party_level}}
- lore snippets (if any): {{top3 rag.docs.chunk}}

User action: {{dto.action}}

Rules:
- No extra keys.
- At least 2 choices.
- suggested_dc ∈ [8..20].
- IDs c1..cN.
```

**NPC prompt scaffold**
```
System: You control {{target}}. Produce JSON:
{ "npc": { "id": str, "dialogue": str, "attitude_delta": int, "knowledge_refs": [str] } }
Constraints: No out-of-character text. If unknown, admit uncertainty.
```

---

**That’s it — implement top‑down (contract → broker/RAG → routing → scenario/NPC), then wire pipeline, then tests.**
