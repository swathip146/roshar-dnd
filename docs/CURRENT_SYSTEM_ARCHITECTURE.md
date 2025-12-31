# Roshar D&D Game System - Complete Architecture & Feature Guide

**Version:** 1.0.0
**Last Updated:** 2025-12-29
**Status:** Production-ready

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Core Components](#core-components)
4. [Agent System](#agent-system)
5. [Pipeline Architecture](#pipeline-architecture)
6. [Data Flow](#data-flow)
7. [State Management](#state-management)
8. [Implemented Features](#implemented-features)
9. [Unimplemented Features](#unimplemented-features)
10. [Technical Details](#technical-details)
11. [Development Guide](#development-guide)

---

## Executive Summary

The Roshar D&D Game System is a production-ready, AI-enhanced Dungeon Master assistant powered by Google Gemini and Haystack 2.0. It provides dynamic D&D 5e gameplay with Cosmere/Roshar extensions, featuring intelligent scenario generation, RAG-enhanced lore retrieval, and comprehensive state management.

### Key Capabilities

- **AI-Powered Scenario Generation**: Context-aware D&D scenarios with dynamic choices
- **Intelligent Routing**: LLM-based intent classification routes player input to appropriate pipelines
- **RAG-Enhanced World Knowledge**: Semantic search retrieves campaign-specific lore and rules
- **Complete D&D 5e Mechanics**: 7-step skill pipeline with full provenance tracking
- **Roshar/Cosmere Integration**: Knights Radiant, investiture, spren bonding, ideal progression
- **Clean Architecture**: No state duplication, direct engine access, clear separation of concerns
- **Comprehensive Logging**: Timestamped debug logs with dual output (console + file)
- **Session Persistence**: Multiple save slots with full game state serialization

---

## System Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Player Input (CLI)                        │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              HaystackDnDGame (Main Controller)              │
│  - Interactive game loop                                    │
│  - Command handling (save/load/quit/stats/help)            │
│  - Turn processing orchestration                            │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│           PipelineOrchestrator (Routing Hub)                │
│  - Creates RequestDTO with engine references                │
│  - Routes to appropriate pipeline                           │
│  - Returns GameResponseDTO                                  │
└──────────────────────────┬──────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Interface    │  │ Scenario     │  │ RAG          │
│ Pipeline     │  │ Pipeline     │  │ Pipeline     │
│              │  │              │  │              │
│ Routes to:   │  │ Generates    │  │ Retrieves    │
│ - Scenario   │  │ scenarios    │  │ lore/rules   │
│ - RAG        │  │ with choices │  │ documents    │
│ - NPC        │  │              │  │              │
└──────────────┘  └──────────────┘  └──────────────┘
           │               │               │
           └───────────────┼───────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   State Management Layer                     │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ GameEngine   │  │ Character    │  │ Session      │     │
│  │              │  │ Manager      │  │ Manager      │     │
│  │ (Runtime     │  │              │  │              │     │
│  │  State)      │  │ (Characters) │  │ (Persistence)│     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐                        │
│  │ PolicyEngine │  │ CampaignConf │                        │
│  │              │  │ ig           │                        │
│  │ (Rules)      │  │ (Immutable)  │                        │
│  └──────────────┘  └──────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

### File Structure

```
roshar-dnd/
├── haystack_dnd_game.py              # Main entry point & game loop
├── core/
│   └── game_initialization.py         # Interactive game setup
├── components/
│   ├── game_engine.py                 # Runtime state authority (7-step pipeline)
│   ├── character_manager.py           # Character sheet management
│   ├── session_manager.py             # Persistence coordination
│   ├── policy.py                      # Rule interpretation (RAW/HOUSE/EASY)
│   ├── campaign_config.py             # Immutable campaign data
│   ├── shared_contract.py             # DTO definitions & utilities
│   ├── dice.py                        # Dice rolling
│   └── rules.py                       # D&D rules enforcement
├── agents/
│   ├── main_interface_agent_fixed.py  # Intent classifier & router
│   ├── scenario_generator_agent.py    # Creative scenario generation
│   ├── rag_retriever_agent.py         # Document retrieval
│   └── npc_controller_agent.py        # NPC interactions
├── orchestrator/
│   └── pipeline_integration.py        # Pipeline routing coordinator
├── adapters/
│   └── world_state_adapter.py         # Context extraction for agents
├── config/
│   ├── llm_config.py                  # LLM configuration (Gemini)
│   ├── llm_utils.py                   # LLM utilities (function calling)
│   └── logging_config.py              # Centralized logging setup
├── storage/
│   └── simple_document_store.py       # Qdrant document store wrapper
├── logs/                              # Timestamped runtime logs
├── game_saves/                        # Saved game sessions
└── docs/                              # Documentation
```

---

## Core Components

### 1. GameEngine (Authoritative State Writer)

**Location:** `components/game_engine.py`
**Role:** Runtime game state authority with 7-step skill resolution pipeline

#### State Management

**GameState (Dataclass):**
```python
@dataclass
class GameState:
    characters: Dict[str, Any]          # Runtime character instances
    combat_state: Dict[str, Any]        # Combat tracking
    environment: Dict[str, Any]         # Weather, time, etc.
    campaign_flags: Dict[str, bool]     # Mutable flag tracking
    session_data: Dict[str, Any]        # Session-specific data
    narrative_context: Dict[str, Any]   # Current scene, pacing, tension
    location_context: Dict[str, Any]    # Current location details
    quest_context: Dict[str, Any]       # Active quests, objectives
```

**CampaignConfig Reference:**
- Frozen dataclass with campaign metadata
- Never modified after initialization
- Provides: name, story, NPCs, locations, quests, difficulty

#### 7-Step Skill Resolution Pipeline

**Purpose:** Deterministic, provenance-tracked D&D 5e skill checks

**Flow:**
1. **Rules Enforcer** → Determine if roll needed, derive base DC
2. **Character Manager** → Get skill modifiers, ability scores, conditions
3. **Policy Engine** → Compute advantage/disadvantage, house rules
4. **Dice Roller** → Execute roll (logged with provenance)
5. **Rules Enforcer** → Compare result vs DC, determine success/failure
6. **Game Engine** → Apply state changes, log outcome
7. **Decision Logger** → Record full breakdown for analytics

**Key Methods:**
- `process_skill_check(character_id, skill_name, dc, context)` → SkillCheckResult
- `add_character(character_data)` → Registers character
- `export_game_state()` → Dict for serialization
- `import_game_state(state_dict)` → Restores from save
- `process_scenario_state_updates(scenario, turn)` → Applies scenario outcomes

#### Context Methods

```python
def get_narrative_context() -> Dict[str, Any]:
    """Returns current_scene, pacing, tension_level, story_hooks"""

def get_location_context() -> Dict[str, Any]:
    """Returns current_location, description, features"""

def get_quest_context() -> Dict[str, Any]:
    """Returns active_quests, objectives, time_pressure, consequences"""

def get_scenario_context() -> Dict[str, Any]:
    """Comprehensive context for scenario generation"""
```

---

### 2. CharacterManager (Character Sheet Authority)

**Location:** `components/character_manager.py`
**Role:** Manages D&D 5e character sheets with Roshar extensions

#### CharacterData Structure

```python
@dataclass
class CharacterData:
    # Core D&D 5e
    name: str
    level: int
    char_class: str
    background: str
    race: str
    ability_scores: Dict[str, int]      # STR, DEX, CON, INT, WIS, CHA
    proficiency_bonus: int
    skill_proficiencies: List[str]
    armor_class: int
    hit_points: int
    max_hit_points: int

    # Roshar/Cosmere Extensions
    radiant_order: str                  # Windrunner, Skybreaker, etc.
    ideal_level: int                    # Oath progression (1-5)
    investiture_points: int
    spren: Optional[str]                # Bonded spren
    surges_known: List[str]             # Gravitation, Adhesion, etc.
```

#### Key Methods

```python
def get_skill_data(character_id, skill_name) -> Dict:
    """Returns skill modifier, proficiency, ability score for pipeline step 2"""

def get_party_snapshot() -> Dict:
    """Returns party_size, avg_level, party_roles for scenario context"""

def advance_ideal(character_id, new_level, oath_text):
    """Advances Radiant oath progression, unlocks abilities"""

def log_character_action(character_id, action_type, details):
    """Tracks action history for analytics"""
```

---

### 3. SessionManager (Persistence Coordinator)

**Location:** `components/session_manager.py`
**Role:** Coordinates saves/loads, tracks analytics (DOES NOT own state)

#### Key Principle

**SessionManager never owns game state.** It coordinates persistence only.

#### Methods

```python
def create_new_session(player_name, collection_name) -> Result:
    """Creates session metadata only"""

def save_session(filename, game_engine_state, character_manager_state) -> Result:
    """Collects state from authoritative sources, writes to disk"""

def load_session(filename) -> Result:
    """Returns state dict for GameEngine/CharacterManager to import"""

def record_turn_analytics(input_data, response_type, confidence, turn_num):
    """Records analytics for session statistics"""

def get_session_metadata() -> Dict:
    """Returns player_name, session_id, session_active, duration"""
```

#### Save File Format

```json
{
  "metadata": {
    "version": "1.0",
    "save_time": "2025-12-29T17:02:56",
    "session_id": "uuid",
    "player_name": "Aggi",
    "turns_played": 3
  },
  "game_engine_state": {
    "game_state": { ... },
    "campaign_config": { ... }
  },
  "character_manager_state": {
    "characters": { ... }
  }
}
```

---

### 4. PolicyEngine (Rule Interpreter)

**Location:** `components/policy.py`
**Role:** Mediates rule interpretation and difficulty scaling

#### Policy Profiles

```python
class PolicyProfile(Enum):
    RAW = "raw"          # Rules As Written (strict D&D 5e)
    HOUSE = "house"      # Balanced house rules
    EASY = "easy"        # Beginner-friendly adjustments
```

**Profile Effects:**
- **Flanking rules:** RAW=off, HOUSE=advantage, EASY=+2 bonus
- **Critical range:** RAW=20, HOUSE=19-20, EASY=18-20
- **DC adjustments:** EASY=-2, HOUSE=+0, RAW=+0
- **Scenario generation:** DC ranges, encounter budgets, choice counts

#### Methods

```python
def compute_advantage(context) -> AdvantageState:
    """Determines advantage/disadvantage for step 3 of pipeline"""

def adjust_difficulty(base_dc, context) -> int:
    """Scales DC based on profile and party context"""

def get_difficulty_policy(party_context) -> Dict:
    """Returns DC ranges, encounter budgets for scenario generation"""
```

---

### 5. CampaignConfig (Immutable Campaign Data)

**Location:** `components/campaign_config.py`
**Role:** Frozen dataclass with campaign metadata

```python
@dataclass(frozen=True)
class CampaignConfig:
    name: str
    theme: str
    story: str
    difficulty: str                     # Easy, Medium, Hard, Deadly
    starting_location: str
    key_npcs: List[Dict]
    locations: List[Dict]
    main_quest: str
    side_quests: List[str]
    campaign_hooks: List[str]
```

**Usage:** Read-only reference, never modified. GameEngine holds reference for scenario context.

---

## Agent System

### Overview

Four specialized agents using Haystack's Agent framework with Gemini LLM.

### 1. Main Interface Agent (Intent Classifier)

**Location:** `agents/main_interface_agent_fixed.py`
**Model:** gemini-2.0-flash
**Role:** Analyzes player input, routes to correct pipeline

#### Two-Step Workflow

**Step 1: Record Intent Analysis**
```python
def record_intent_analysis(primary, action_verb, arguments, target,
                          confidence, rationale, rag_needed, rag_reasoning):
    """LLM analyzes player input, extracts intent components"""
    # Returns: Dict with primary intent, action, target, RAG needs
```

**Intent Categories:**
- `scenario_action` → Player performing action (attack, persuade, etc.)
- `rag_query` → Asking about lore/rules
- `npc_interaction` → Talking to NPC
- `scenario_generation` → General continuation

**Step 2: Classify Player Intent**
```python
def classify_player_intent(player_input, rag_context):
    """Processes analysis into routing decision"""
    # Returns: Route (scenario_pipeline, rag_pipeline, npc_pipeline)
```

#### Routing Logic

```python
if rag_needed and primary in ["rag_query", "rules_query", "lore_query"]:
    route = "rag_pipeline"
elif primary == "npc_interaction":
    route = "npc_pipeline"
elif rag_needed and primary == "scenario_action":
    route = "scenario_with_rag_pipeline"
else:
    route = "scenario_pipeline"
```

#### System Prompt Principles

- **Selective RAG Usage:** Only trigger RAG when current context insufficient
- **Trust Game State:** GameEngine/CampaignConfig have comprehensive context
- **Prefer Scenario Generation:** Most actions should route to scenario pipeline

---

### 2. Scenario Generator Agent (Creative Scenario Generation)

**Location:** `agents/scenario_generator_agent.py`
**Model:** gemini-2.0-flash (temperature=0)
**Role:** Generates D&D scenarios with choices

#### Architecture

**LLM-Only Agent (No Tools):**
- Maximum creativity for narrative generation
- Structured JSON output
- 6-category context input (A-F)

#### Context Categories

**A. Narrative Context:**
- current_scene, pacing, tension_level
- story_hooks, narrative_beats
- campaign_started flag

**B. Location Context:**
- current_location, description, features
- environment conditions

**C. Quest Context:**
- active_quests, completed/pending objectives
- time_pressure, consequences, rewards

**D. Policy Context:**
- difficulty_target, DC ranges
- encounter_budget, choice_count_range
- policy_profile (RAW/HOUSE/EASY)

**E. RAG Context (Optional):**
- Retrieved lore snippets (if RAG pipeline ran first)

**F. Output Requirements:**
- JSON schema for scenario
- Choice structure with DCs
- Effects and hooks

#### Scenario JSON Schema

```json
{
  "scene": "string (narrative description)",
  "choices": [
    {
      "id": "c1",
      "title": "string (choice name)",
      "description": "string (what happens)",
      "skill_hints": ["skill1", "skill2"],
      "suggested_dc": 12,
      "combat_trigger": false
    }
  ],
  "effects": {
    "immediate": "string",
    "long_term": "string"
  },
  "hooks": ["string (future plot hooks)"],
  "gm_notes": "string (tactical info for GM)",
  "state_changes": {
    "narrative": "string (how story advances)",
    "location": "string (location changes)",
    "quests": "string (quest updates)"
  },
  "difficulty_used": {
    "dcs": {"c1": 12, "c2": 14},
    "encounter_budget": "medium",
    "policy_profile": "house"
  }
}
```

#### Components

**PromptBuilderComponent:**
```python
def create_scenario_from_dto(dto: RequestDTO) -> List[ChatMessage]:
    """Accesses GameEngine/PolicyEngine DIRECTLY (no state duplication)"""
    game_engine = dto.get("_game_engine_ref")
    policy_engine = dto.get("_policy_engine_ref")

    narrative = game_engine.get_narrative_context()
    location = game_engine.get_location_context()
    quest = game_engine.get_quest_context()
    policy = policy_engine.get_difficulty_policy(party_context)

    # Build 6-category prompt
    return [system_message, user_message]
```

**ScenarioValidatorComponent:**
```python
def validate_and_repair(messages: List[ChatMessage]) -> Scenario:
    """Parses LLM JSON output, validates schema, repairs if needed"""
    # Returns: Scenario TypedDict
```

---

### 3. RAG Retriever Agent (Document Retrieval)

**Location:** `agents/rag_retriever_agent.py`
**Model:** gemini-2.0-flash
**Role:** Retrieves relevant lore/rules from document store

#### Tools

```python
def retrieve_documents(query: str, context_type: str, top_k: int = 5) -> Dict:
    """Searches Qdrant vector database with intelligent filters"""
    # context_type: "lore", "rules", "monsters", "locations", "campaigns"
    # Returns: documents list with content and metadata
```

#### Workflow

1. **Query Analysis:**
   - Determine context_type from player query
   - Generate appropriate filters

2. **Document Search:**
   - Semantic search with embeddings (all-MiniLM-L6-v2)
   - Metadata filtering by context_type
   - Top-k retrieval (default: 5)

3. **Response Synthesis:**
   - Extract key information (150 word max)
   - Use direct quotes when appropriate
   - Cite sources if available
   - Return concise factual response

#### System Prompt

"You are a knowledgeable game master assistant that retrieves accurate information about D&D lore, rules, and campaign details. When answering queries:
- Be concise (150 words max)
- Use direct quotes from documents when available
- Cite specific sources if provided
- If information is uncertain, say so
- Focus on factual information relevant to the query"

---

### 4. NPC Controller Agent (NPC Interactions)

**Location:** `agents/npc_controller_agent.py`
**Model:** gemini-2.0-flash
**Role:** Handles NPC dialogue and behavior

#### Current Status

**Basic implementation:**
- Processes NPC interaction requests
- Generates dialogue responses
- References CampaignConfig for NPC data

**Future enhancements planned:**
- NPC personality tracking
- Relationship system
- Memory of past interactions
- Quest-giving capabilities

---

## Pipeline Architecture

### PipelineOrchestrator

**Location:** `orchestrator/pipeline_integration.py`
**Class:** `PipelineOrchestrator`
**Role:** Central routing hub for all player input

#### Initialization

```python
def __init__(self, collection_name, shared_document_store=None,
             game_engine=None, character_manager=None,
             session_manager=None, policy_engine=None):
    """Creates all agents and pipelines with engine references"""
```

**Steps:**
1. Create Gemini configuration
2. Initialize 4 agents
3. Create WorldStateAdapter
4. Build connected pipelines
5. Store engine references

#### Request Processing

```python
def process_request(self, dto: RequestDTO) -> Dict:
    """Main entry point for all game turns"""
    1. Extract type and route from DTO
    2. Route to appropriate pipeline
    3. Execute pipeline
    4. Format response
    5. Return GameResponseDTO
```

#### Pipeline Routes

**1. gameplay_turn_pipeline:**
```
Interface Agent (analyze input) → Route to appropriate pipeline
```

**2. scenario_pipeline:**
```
PromptBuilder → Scenario Agent → Validator → GameResponseDTO
```

**3. scenario_with_rag_pipeline:**
```
RAG Agent → Formatter
    ↓
PromptBuilder (with RAG results) → Scenario Agent → Validator
```

**4. rag_pipeline:**
```
RAG Agent → Formatter → GameResponseDTO
```

**5. npc_pipeline:**
```
PromptBuilder → NPC Agent → GameResponseDTO
```

---

### Connected Pipelines

**Implementation:** Haystack Pipeline objects with connected components

**Example - Scenario Pipeline:**
```python
scenario_pipeline = Pipeline()
scenario_pipeline.add_component("prompt_builder", PromptBuilderComponent())
scenario_pipeline.add_component("scenario_agent", scenario_agent)
scenario_pipeline.add_component("validator", ScenarioValidatorComponent())

scenario_pipeline.connect("prompt_builder", "scenario_agent.messages")
scenario_pipeline.connect("scenario_agent.replies", "validator.messages")
```

---

## Data Flow

### Player Input → Response Journey

**1. Input Capture** (`haystack_dnd_game.py:620`)
```python
player_input = input(f"\n{player_name}> ")
```

**2. DTO Creation** (`haystack_dnd_game.py:303`)
```python
request_dto = new_dto(input_text, {})
request_dto["_game_engine_ref"] = self.game_engine
request_dto["_policy_engine_ref"] = self.policy_engine
```

**3. Orchestrator Processing** (`pipeline_integration.py:286`)
```python
response_dict = orchestrator.process_request(request_dto)
```

**4. Interface Agent Routing** (`main_interface_agent_fixed.py`)
- LLM analyzes input
- Records intent (primary, action, target, RAG needs)
- Classifies to route

**5. Pipeline Execution**

**Scenario Path:**
```
PromptBuilder:
  - Accesses game_engine.get_narrative_context()
  - Accesses game_engine.get_location_context()
  - Accesses game_engine.get_quest_context()
  - Accesses policy_engine.get_difficulty_policy()
  - Builds 6-category prompt
    ↓
Scenario Agent:
  - Gemini generates JSON scenario
  - Temperature=0 for consistency
    ↓
Validator:
  - Parses JSON
  - Validates schema
  - Repairs if needed
  - Returns Scenario TypedDict
```

**RAG Path:**
```
RAG Agent:
  - Analyzes query
  - Calls retrieve_documents tool
  - Searches Qdrant with filters
  - Synthesizes concise response
    ↓
Formatter:
  - Formats RAGBlock
  - Returns GameResponseDTO
```

**6. Response Formatting** (`haystack_dnd_game.py:357`)
```python
formatted_result = self._handle_response(response_dict)
# Formats based on response_type (scenario, rag_query, npc_interaction)
```

**7. State Updates** (`haystack_dnd_game.py:264`)
```python
self._update_state_via_authorities(processed_input, response_data)
# - GameEngine.process_scenario_state_updates()
# - SessionManager.record_turn_analytics()
```

**8. Display** (`haystack_dnd_game.py:644`)
```python
print(f"\n🎭 DM:\n{dm_response}")
```

---

### Scenario Generation Detailed Flow

**1. Context Gathering** (`scenario_generator_agent.py:80-116`)
```python
# DIRECT ENGINE ACCESS (NO state duplication)
narrative_context = game_engine.get_narrative_context()
location_context = game_engine.get_location_context()
quest_context = game_engine.get_quest_context()
party_context = character_manager.get_party_snapshot()
difficulty_policy = policy_engine.get_difficulty_policy(party_context)
```

**2. Prompt Building** (`scenario_generator_agent.py:165`)
- **Category A (Narrative):** current_scene, pacing, tension, hooks
- **Category B (Location):** current_location, description, features
- **Category C (Quest):** active_quests, objectives, time_pressure
- **Category D (Policy):** DC ranges, encounter budget, profile
- **Category E (RAG):** Retrieved snippets if available
- **Category F (Output):** JSON schema requirements

**3. LLM Generation**
- Temperature=0 for consistency
- JSON output with scene, choices, effects, hooks
- Choice count: 2-4 based on policy
- DC ranges: Easy 8-12, Medium 10-15, Hard 13-18, Deadly 17-22

**4. Validation** (`ScenarioValidatorComponent:340`)
- Parse JSON from markdown code block
- Validate required fields (scene, choices)
- Repair common errors (missing fields, invalid DCs)
- Return Scenario TypedDict

**5. State Application** (`game_engine.py:1109`)
```python
def process_scenario_state_updates(scenario: Scenario, turn: int):
    """Applies scenario outcomes to GameEngine state"""
    - Update narrative_context (current_scene, last_scenario_type)
    - Update location_context (from state_changes.location)
    - Update quest_context (from state_changes.quests)
    - Add story hooks
    - Increment turn counter
```

---

## State Management

### State Hierarchy

```
CampaignConfig (Immutable, Frozen)
        │
        │ read-only
        ▼
  GameEngine.game_state (Runtime Authority)
        │
        ├─► Narrative Context (current scene, pacing)
        ├─► Location Context (current location)
        ├─► Quest Context (active quests, objectives)
        ├─► Combat State (turn order, HP tracking)
        ├─► Environment (weather, time)
        └─► Campaign Flags (mutable tracking)

  CharacterManager.characters (Character Authority)
        │
        ├─► Character Sheets (stats, skills)
        ├─► Skill Proficiencies
        ├─► Conditions & Effects
        └─► Action History

  SessionManager (Persistence Coordinator)
        │
        ├─► Session Metadata (player name, timestamps)
        ├─► Analytics (turn count, routing stats)
        └─► Save/Load Coordination

  PolicyEngine (Rule Interpreter)
        │
        ├─► Profile (RAW/HOUSE/EASY)
        ├─► DC Adjustments
        └─► Scenario Generation Rules
```

### Component Relationships

```python
# GameEngine reads from CampaignConfig
campaign_name = game_engine.campaign_config.name

# GameEngine queries CharacterManager for skill checks
skill_data = character_manager.get_skill_data(char_id, "Persuasion")

# SessionManager exports from GameEngine for saves
game_state = game_engine.export_game_state()
session_manager.save_session(filename, game_state, character_state)

# PolicyEngine provides rules for GameEngine
advantage_state = policy_engine.compute_advantage(context)

# All agents access GameEngine/PolicyEngine via DTO references
game_engine = dto["_game_engine_ref"]
narrative = game_engine.get_narrative_context()
```

### Key Principles

1. **Single Authority:** Each component has exactly one responsibility
2. **No State Duplication:** State lives in one place, accessed via references
3. **Direct Access:** Agents access engines directly via DTO refs, no copying
4. **Immutability Where Appropriate:** CampaignConfig is frozen
5. **Clear Ownership:** GameEngine owns runtime state, SessionManager coordinates persistence

---

## Implemented Features

### ✅ Core Game Loop

- [x] Interactive CLI with readline support
- [x] Command handling: help, save, load, quit, stats
- [x] Turn-based gameplay with turn counter
- [x] Numbered choice selection (1-4)
- [x] Free-form text input
- [x] DM response formatting

### ✅ Intelligent Routing

- [x] LLM-based intent classification
- [x] Two-step workflow (record_intent, classify)
- [x] Selective RAG triggering
- [x] Multi-pipeline routing:
  - scenario_pipeline
  - scenario_with_rag_pipeline
  - rag_pipeline
  - npc_pipeline
- [x] Confidence scoring (0.0-1.0)
- [x] Rationale generation

### ✅ Scenario Generation

- [x] Context-aware scenarios
- [x] Dynamic choice generation (2-4 choices)
- [x] DCs derived from policy profile
- [x] Skill hints for each choice
- [x] Combat trigger flags
- [x] Immediate and long-term effects
- [x] Story hooks for future scenarios
- [x] GM notes with tactical info
- [x] State change tracking
- [x] JSON validation and repair

### ✅ RAG System

- [x] Qdrant vector database integration
- [x] Semantic search with embeddings (all-MiniLM-L6-v2)
- [x] Metadata filtering (lore, rules, monsters, locations, campaigns)
- [x] Concise answer synthesis (150 word max)
- [x] Source citation
- [x] Confidence scoring
- [x] Fallback responses when no documents found

### ✅ Character Management

- [x] D&D 5e character sheets
- [x] Ability scores (STR, DEX, CON, INT, WIS, CHA)
- [x] Skill proficiencies
- [x] Armor Class (AC)
- [x] Hit Points (HP) tracking
- [x] Level and experience
- [x] Class, race, background
- [x] **Roshar/Cosmere Extensions:**
  - [x] Radiant orders (Windrunner, Skybreaker, etc.)
  - [x] Ideal progression (1-5)
  - [x] Investiture points
  - [x] Spren bonding
  - [x] Surges (Gravitation, Adhesion, etc.)
- [x] Party snapshot for scenario context
- [x] Action history logging

### ✅ 7-Step Skill Pipeline

- [x] Step 1: Rules Enforcer determines DC
- [x] Step 2: Character Manager provides modifiers
- [x] Step 3: Policy Engine computes advantage
- [x] Step 4: Dice Roller executes roll
- [x] Step 5: Rules Enforcer evaluates result
- [x] Step 6: Game Engine applies state changes
- [x] Step 7: Decision Logger records provenance
- [x] Full provenance tracking (DC source, advantage source)
- [x] Deterministic results

### ✅ Session Persistence

- [x] Save game state to JSON
- [x] Multiple save slots
- [x] Load game from save file
- [x] Save file browser with metadata
- [x] Session metadata tracking:
  - player_name
  - session_id
  - turns_played
  - save_time
  - location
- [x] Enhanced save format with version tracking

### ✅ Policy Profiles

- [x] RAW (Rules As Written)
- [x] HOUSE (Balanced house rules)
- [x] EASY (Beginner-friendly)
- [x] Flanking rules configuration
- [x] Critical hit range configuration
- [x] DC adjustment by profile
- [x] Scenario generation tuning:
  - DC ranges
  - Encounter budgets
  - Choice count ranges

### ✅ Campaign System

- [x] CampaignConfig (immutable, frozen dataclass)
- [x] Campaign file loading (JSON format)
- [x] Multiple campaign support
- [x] Campaign browser with descriptions
- [x] Campaign metadata:
  - name, theme, story
  - difficulty level
  - starting_location
  - key_npcs
  - locations
  - main_quest, side_quests
  - campaign_hooks

### ✅ Logging System

- [x] Centralized logging configuration
- [x] Timestamped log files (dnd_game_YYYYMMDD_HHMMSS.log)
- [x] Dual output: console (INFO+) and file (DEBUG+)
- [x] Detailed provenance in file logs
- [x] Clean console output
- [x] Haystack logging suppression (WARNING level)
- [x] Log levels: DEBUG, INFO, WARNING, ERROR
- [x] Module-level loggers

### ✅ Game Initialization

- [x] Interactive setup wizard
- [x] Document collection configuration
- [x] Game mode selection (new campaign vs load save)
- [x] Campaign browser with filtering
- [x] Character selection (Aggi, Kali)
- [x] Policy profile selection
- [x] Component initialization with fallbacks
- [x] Quest context initialization from campaign
- [x] Story hook injection

### ✅ DTO System

- [x] RequestDTO with engine references
- [x] GameResponseDTO with typed responses
- [x] RAGBlock for RAG results
- [x] Scenario TypedDict
- [x] NPCResponse TypedDict
- [x] DTO normalization utilities
- [x] DTO validation
- [x] Scenario repair utilities
- [x] DTO merging

### ✅ World State Adapter

- [x] Context extraction from GameEngine
- [x] Party context compilation
- [x] Narrative summary generation
- [x] Location summary generation
- [x] Quest summary generation

---

## Unimplemented Features

### 🔜 Combat System

- [ ] Initiative tracking
- [ ] Turn order management
- [ ] HP tracking UI
- [ ] Combat actions (Attack, Cast Spell, Dash, etc.)
- [ ] Advantage/disadvantage in combat
- [ ] Critical hit damage
- [ ] Death saving throws
- [ ] Multi-target attacks

### 🔜 Advanced NPC System

- [ ] NPC personality tracking
- [ ] Relationship system (faction, attitude)
- [ ] NPC memory of past interactions
- [ ] Quest-giving NPCs
- [ ] Dynamic NPC reactions based on party actions
- [ ] NPC combat AI

### 🔜 Inventory System

- [ ] Item tracking
- [ ] Equipment management
- [ ] Weight/encumbrance
- [ ] Currency tracking
- [ ] Item descriptions
- [ ] Magic item identification
- [ ] Crafting system

### 🔜 Magic System Enhancements

- [ ] Spell slot tracking
- [ ] Spell preparation
- [ ] Concentration tracking
- [ ] Spell components (V, S, M)
- [ ] Ritual casting
- [ ] Spell scrolls and wands

### 🔜 Advanced Quest System

- [ ] Quest tracking UI
- [ ] Quest objectives with checkboxes
- [ ] Quest rewards distribution
- [ ] Side quest branching
- [ ] Quest completion notifications
- [ ] Quest failure consequences

### 🔜 World Map & Travel

- [ ] Interactive world map
- [ ] Fast travel system
- [ ] Random encounters during travel
- [ ] Distance/time calculations
- [ ] Travel supplies management

### 🔜 Party Management

- [ ] Multiple character support (full party)
- [ ] Character switching
- [ ] Party formation
- [ ] Party roles auto-detection
- [ ] Party-wide buffs/debuffs

### 🔜 Enhanced RAG Features

- [ ] Document upload UI
- [ ] Campaign-specific document collections
- [ ] Automatic document indexing from campaign files
- [ ] Image/map document support
- [ ] Document versioning

### 🔜 Cosmere/Roshar Enhancements

- [ ] Stormlight tracking (charges)
- [ ] Lashing mechanics (Windrunners)
- [ ] Soulcasting mechanics (Lightweavers)
- [ ] Shardblade/Shardplate mechanics
- [ ] Spren manifestation system
- [ ] Oath-speaking ceremonies

### 🔜 Multiplayer Support

- [ ] Multiple players sharing one session
- [ ] Turn-based player switching
- [ ] Player-to-player interactions
- [ ] Shared party inventory
- [ ] Collaborative decision-making

### 🔜 Voice/Audio Features

- [ ] Text-to-speech for DM responses
- [ ] Voice input for player actions
- [ ] Background music/ambience
- [ ] Sound effects for actions

### 🔜 Web UI

- [ ] Web-based interface (replace CLI)
- [ ] Character sheet visualization
- [ ] Interactive map view
- [ ] Drag-and-drop actions
- [ ] Mobile-responsive design

---

## Technical Details

### Technology Stack

**Language:** Python 3.10+

**Core Libraries:**
- **Haystack 2.0:** Pipeline framework, Agent system
- **Google Gemini:** LLM (gemini-2.0-flash)
- **Qdrant:** Vector database for RAG
- **Sentence-Transformers:** Embeddings (all-MiniLM-L6-v2)
- **Pydantic:** Data validation (TypedDict)

**Storage:**
- **JSON:** Save files, campaign files, character sheets
- **Qdrant:** Document vectors for RAG

### Performance Characteristics

**Initialization Time:** ~5-10 seconds
- Component creation
- LLM config setup
- Agent initialization
- Pipeline building

**Turn Processing:** ~2-5 seconds per turn
- Interface agent (intent classification): ~1-2s
- Scenario generation: ~3-5s
- RAG retrieval: ~1-2s

**Memory Usage:** ~200-300 MB
- Embedding model: ~100 MB
- LLM API (streaming): minimal
- Game state: <1 MB

### API Usage

**Gemini API:**
- Model: gemini-2.0-flash
- Temperature: 0.0 (scenarios), 0.3 (interface)
- Max tokens: 2048 (responses)
- Function calling: Yes (interface agent tools)

**Token Usage Per Turn:**
- Interface agent: ~1200 prompt + 100 response
- Scenario generation: ~2200 prompt + 900 response
- Total: ~4400 tokens/turn

**Estimated Cost (Gemini 2.0 Flash):**
- ~$0.0002 per turn
- ~$0.01 per 50-turn session

---

## Development Guide

### Adding a New Agent

1. **Create agent file** in `agents/`:
```python
from haystack import component
from haystack.components.agents import Agent

@component
class MyNewAgent:
    """Agent description"""

    @component.output_types(result=Dict[str, Any])
    def run(self, dto: RequestDTO) -> Dict[str, Any]:
        # Agent logic
        return {"result": result}
```

2. **Add pipeline** in `orchestrator/pipeline_integration.py`:
```python
def create_my_pipeline(self):
    pipeline = Pipeline()
    pipeline.add_component("my_agent", self.agents["my_agent"])
    return pipeline
```

3. **Add routing** in orchestrator:
```python
if dto.get("route") == "my_pipeline":
    result = self.pipelines["my_pipeline"].run({"dto": dto})
```

### Adding a New Component

1. **Create component file** in `components/`:
```python
from dataclasses import dataclass
from typing import Dict, Any

class MyComponent:
    """Component description"""

    def __init__(self):
        # Initialization
        pass

    def my_method(self, param: str) -> Dict[str, Any]:
        # Component logic
        return result
```

2. **Initialize in game_initialization.py**:
```python
my_component = MyComponent()
```

3. **Pass to orchestrator** if needed:
```python
orchestrator = create_full_haystack_orchestrator(
    ...,
    my_component=my_component
)
```

### Adding a New Policy Profile

1. **Add to PolicyProfile enum** in `components/policy.py`:
```python
class PolicyProfile(Enum):
    MY_PROFILE = "my_profile"
```

2. **Add profile configuration**:
```python
PROFILE_CONFIGS = {
    PolicyProfile.MY_PROFILE: {
        "flanking_bonus": 2,
        "crit_range": 19,
        # ... other settings
    }
}
```

3. **Update difficulty policy method**:
```python
def get_difficulty_policy(self, party_context: Dict) -> Dict:
    if self.profile == PolicyProfile.MY_PROFILE:
        return {
            "dc_range_easy": (6, 10),
            # ... other ranges
        }
```

### Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python -m pytest tests/test_game_engine.py

# Run with coverage
python -m pytest --cov=components tests/
```

### Debugging

**Enable debug logging:**
```python
# In config/logging_config.py, change console level:
console_handler.setLevel(logging.DEBUG)
```

**Check logs:**
```bash
# View latest log
tail -f logs/dnd_game_*.log

# Search logs
grep "ERROR" logs/dnd_game_*.log
```

### Performance Profiling

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Run game turn
dm_response = game.play_turn(player_input)

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)
```

---

## Conclusion

The Roshar D&D Game System represents a sophisticated, production-ready AI-powered game master assistant. With clean architecture, comprehensive D&D 5e mechanics, Roshar/Cosmere integration, and extensible design, it provides an immersive and dynamic D&D experience.

**Key Strengths:**
- **Clean Architecture:** No state duplication, direct engine access
- **Intelligent AI:** Context-aware routing and generation
- **Complete D&D Mechanics:** 7-step skill pipeline with full provenance
- **Extensible Design:** Easy to add agents, policies, or features
- **Production Quality:** Comprehensive logging, error handling, persistence

**Development Roadmap:**
- Combat system implementation
- Advanced NPC interactions
- Inventory management
- Web UI development

For questions or contributions, see the documentation in `docs/` or contact the development team.

---

*Last Updated: 2025-12-29*
*Version: 1.0.0*
*Architecture Status: Production-Ready*
