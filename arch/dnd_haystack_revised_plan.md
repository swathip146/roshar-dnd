
# Modular D&D Game/Assistant — Revised Haystack Architecture & Phased Plan
_Last updated: 2025-08-23T07:09:42Z_

This revision strengthens the architecture by:
- Separating **Agents (creative, AI-driven)** from **Components (deterministic, rules-driven)**.
- Adding a **Policy Engine** for house rules and difficulty scaling.
- Defining **Scenario Generator contracts** with metadata and effects.
- Making **Skill Checks & Combat deterministic**, with **decision logs**.
- Introducing **Saga Manager** and **Observability** into the Orchestrator.
- Structuring a **phased rollout** from a minimal playable loop to full-featured system.

---

## 1) High-Level Architecture

```mermaid
flowchart TB
  UI[Main Interface AI (Chat/UI/API)]
  ORCH[Orchestrator (Router + Saga Manager + Context Broker)]

  subgraph Agents [Creative Agents]
    RAG[RAG Retriever Agent]
    SCEN[Scenario Generator Agent]
    NPC[NPC & Enemy Controller Agent]
    IFACE[Main Interface Agent]
  end

  subgraph Components [Deterministic Components]
    CM[Character Manager]
    DICE[Dice Roller]
    INV[Inventory/Loot Manager]
    XP[Experience/Leveling]
    GE[Game Engine (state, events)]
    CAMP[Campaign Manager]
    RULES[Rules Enforcer]
    POLICY[Policy Engine]
    SPELL[Spell Manager]
    SESS[Session Manager]
    COMBAT[Combat Engine]
    MEM[Memory/World Summaries]
    KB[Document Store / Vector DB]
  end

  UI --> ORCH
  ORCH --> IFACE
  ORCH --> RAG
  ORCH --> SCEN
  ORCH --> NPC

  ORCH --> CM
  ORCH --> DICE
  ORCH --> INV
  ORCH --> XP
  ORCH --> GE
  ORCH --> CAMP
  ORCH --> RULES
  ORCH --> POLICY
  ORCH --> SPELL
  ORCH --> SESS
  ORCH --> COMBAT
  ORCH --> MEM
  RAG --> KB
```

**Principles**
- **Single orchestrator**: all requests routed here; no lateral agent calls.
- **Agents = creative**, **Components = deterministic**.
- **Policy Engine** mediates house rules, difficulty, and overrides.
- **Game Engine is authoritative state writer**.
- **Decision logs**: every roll, check, and outcome has a provenance trail.

---

## 2) Scenario Generator Contract

Output always includes:
```json
{
  "scene": "Narrative description of the situation",
  "choices": [
    {
      "id": "c1",
      "title": "Sneak across the ledge",
      "description": "Try to cross quietly without alerting the guard.",
      "skill_hints": ["Stealth"],
      "suggested_dc": {"easy": 10, "medium": 15, "hard": 20},
      "combat_trigger": false
    }
  ],
  "effects": [
    {"type": "flag", "name": "alert_guard", "value": true}
  ],
  "hooks": [
    {"quest": "rescue_hostage", "progress": "advance"}
  ]
}
```

---

## 3) Skill Check & Combat Determinism

- **Skill Check Pipeline**
  1. Rules Enforcer → do we need a check? derive DC or contested target.
  2. Character Manager → skill/ability mod, conditions.
  3. Policy Engine → advantage/disadvantage, house rule adjustments.
  4. Dice Roller → raw rolls (logged).
  5. Rules Enforcer → compare vs DC, success/fail.
  6. Game Engine → apply state, log outcome.
  7. Decision Log → roll breakdown, DC provenance, advantage sources.

- **Combat Pipeline**
  1. Combat Engine → initiative, turn order, legal actions.
  2. NPC Agent → proposes actions (creative).
  3. Combat Engine → validates, applies deterministically.
  4. Game Engine → records results, awards XP/loot.
  5. Scenario Generator → post-combat consequence.

---

## 4) Orchestrator Enhancements

- **Saga Manager**: tracks multi-step flows (choice → check → consequence).  
- **Context Broker**: decides when to query RAG/Rules.  
- **Dead Letter Queue**: stores failed messages.  
- **Observability**: structured logs with correlation IDs, tracing, decision logs.

---

## 5) Policy Engine

Centralized ruleset with profiles:
- RAW (rules-as-written).
- House rules (crit on 19–20, flanking advantage, custom rests).
- Difficulty scaler (adjust DCs, enemy CR, loot).

```python
class PolicyEngine:
    def compute_advantage(self, state, actor, skill): ...
    def passive_score(self, ability_mod, prof, bonus=0): ...
    def adjust_difficulty(self, base_dc, context): ...
```

---

## 6) Phased Rollout

### Phase 1 — Core Narrative Loop (MVP)
- Orchestrator + Router + Saga Manager.
- Campaign selection → Scenario Generator → Choices → Skill Checks → Consequences.
- Character Manager, Dice, Rules, Policy, Game Engine minimal versions.
- Save/Load with Session Manager.
- Tests: parser → scenario → choice → consequence.

### Phase 2 — Combat MVP
- Combat Engine (initiative, basic actions, HP, damage).
- NPC Agent for simple combat actions.
- XP and Inventory integration.
- Scenario Generator → combat flags → combat pipeline → post-combat scene.

### Phase 3 — Depth Expansion
- Spell Manager, concentration rules.
- Richer NPC Agent (dialogue, attitudes).
- Memory module (summarize campaign history for context).
- Policy profiles for house rules & difficulty scaling.

### Phase 4 — Content & Modding
- Campaign builder tools.
- Encounter & loot table editor.
- Quest/flag system.
- Modding API (plug-in rules, scenarios, campaigns).

---

## 7) Testing & Observability

- **Contract Tests**: each component’s input/output validated.  
- **Golden Scenario Tests**: sample adventures produce consistent outcomes.  
- **Chaos Tests**: simulate agent/dice failures; orchestrator recovers.  
- **Decision Logs**: every roll and ruling logged for replay/debug.  
- **Tracing**: OpenTelemetry spans for each pipeline hop.  

---

## 8) Repo Layout

```
dnd/
  orchestrator/
    router.py
    saga_manager.py
    context_broker.py
  agents/
    rag_agent.py
    scenario_agent.py
    npc_agent.py
    interface_agent.py
  components/
    character_manager.py
    dice.py
    rules.py
    policy.py
    game_engine.py
    campaign_manager.py
    combat_engine.py
    inventory.py
    xp.py
    spell_manager.py
    session_manager.py
  prompts/
    scenario.md
    npc.md
  storage/
    document_store.py
    state_repo.py
  tests/
    e2e/
    contracts/
    golden/
```

---

## ✅ Summary

This revised plan:
- Keeps **agents creative**, **components deterministic**.  
- Adds a **Policy Engine** for house rules and scaling.  
- Makes **Skill Checks & Combat deterministic and auditable**.  
- Strengthens the **Scenario Generator contract** with metadata and hooks.  
- Builds a **phased roadmap**: MVP → combat → depth → modding.  

This ensures the game is **playable early**, then matures safely into a comprehensive D&D assistant/game platform.
