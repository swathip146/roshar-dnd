# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-powered Dungeon Master assistant for D&D 5e gameplay set in Brandon Sanderson's Cosmere (Roshar setting). Uses **Haystack 2.0** pipeline framework with **Google Gemini 2.0 Flash** LLM and **Qdrant** vector database for RAG-enhanced campaign lore.

**Tech Stack**: Python 3.10+, Haystack 2.0, Google Gemini API, Qdrant, Sentence-Transformers, Docling

---

## Essential Commands

### Setup & Run
```bash
# Initial setup (handles Conda/venv)
./install_dependencies.sh

# Run the game (recommended - sets env vars)
./run_game.sh

# Direct Python execution
python haystack_dnd_game.py
```

**Prerequisites**: Create `.env` file with `GEMINI_API_KEY=your_api_key_here`

### Testing
```bash
# Run all tests
pytest tests/

# Phase regression suites (the most informative; assert on observable state)
pytest tests/test_phase0_regressions.py tests/test_phase2_regressions.py tests/test_phase3_regressions.py

# Real-engine combat tests (no mocks)
pytest tests/combat/test_real_engine_combat.py

# Specific test with verbose output
pytest -vv tests/test_phase2_regressions.py::TestQuestProgression
```

**Latest test status**: 380 non-combat + 174 combat tests passing.

Note: tests that make REAL LLM calls have no timeout and must be deselected in
bulk runs — `test_gemini_*`, `test_llm_utils`, `test_tool_calling`,
`test_game_*rounds`, `test_api_connection`. Combat also takes several minutes.

### Document Indexing for RAG
```bash
# Index PDFs/text files into Qdrant
python generators/batch_qdrant_indexer.py

# Clear vector database
rm -rf ./qdrant_storage/
```

### Logging
```bash
# View live logs
tail -f logs/dnd_game_*.log
```

All logging uses centralized config from `config/logging_config.py` (dual console + file output).

---

## MUST FOLLOW INSTRUCTIONS

- Use Open Source license libraries only

- Follow the file directory structure and add code that belongs to the relevant directories. Example: Test scripts should be under tests, md files should be under docs, agentic code should be in agents, non agentic shared components should be components etc.

- For the codebase, always create modular code in a hierarchial style. Add new files whenever needed instead of huge changes to the top hierarchy files. Do not write long code files that are longer than a 1000 lines.

- Always write a test script for any new code or feature additions. The tests should always have logs that report the progress of the test.

- Add helpful logs whenever adding new features following the same logging features available in codebase.

## High-Level Architecture

### System Flow
```
Player Input (CLI)
    ↓
HaystackDnDGame.play_turn() → creates RequestDTO
    ↓
PipelineOrchestrator → routes to appropriate pipeline
    ↓
MainInterfaceAgent → classifies intent (scenario/rag/npc)
    ↓
ScenarioGeneratorAgent / RAGRetrieverAgent / NPCControllerAgent
    ↓
GameResponseDTO returned
    ↓
GameEngine updates state → SessionManager persists
```

### Four Pipeline System

1. **Interface Pipeline**: Intent classification (temperature=0 for deterministic routing)
   - Routes to: scenario_pipeline, rag_pipeline, npc_pipeline
   - Agent: `agents/main_interface_agent_fixed.py`

2. **Scenario Pipeline**: Dynamic D&D scenario generation
   - Agent: `agents/scenario_generator_agent.py`
   - Reads GameEngine state directly (no copying)
   - Uses PolicyEngine for difficulty scaling

3. **RAG Pipeline**: Semantic search over campaign documents
   - Agent: `agents/rag_retriever_agent.py`
   - Queries Qdrant vector DB (Sentence-Transformers embeddings)
   - Supports contextual filters (lore, rules, monsters, spells)

4. **NPC Pipeline**: NPC dialogue and interactions
   - Agent: `agents/npc_controller_agent.py`
   - Personality-driven responses

### Component Authority Pattern (Clean Architecture)

**Critical Design Principle**: Components own their domains with single sources of truth.

```python
# ❌ WRONG: State duplication
dto["character_data"] = game_engine.characters.copy()

# ✅ CORRECT: Pass engine references
dto["_game_engine_ref"] = game_engine
# Agents read directly from engine
state = game_engine.get_character_data()
```

**State Ownership**:
- **GameEngine** (`components/game_engine.py`): Runtime state authority
  - 7-step skill resolution pipeline
  - Character runtime state (position, hidden, initiative)
  - Location, Narrative, Quest contexts

- **CharacterManager** (`components/character_manager.py`): Character data authority
  - D&D 5e character sheets + Roshar extensions
  - Character summaries and snapshots

- **SessionManager** (`components/session_manager.py`): Persistence coordination only
  - Save/load in `game_saves/` directory
  - Analytics and routing statistics

- **CampaignConfig** (`core/game_initialization.py`): Immutable campaign metadata
  - NPCs, locations, story hooks
  - Never modified after initialization

- **PolicyEngine** (`components/policy.py`): Rule interpretation
  - RAW, HOUSE, EASY profiles for DC scaling

### Data Transfer Objects (DTOs)

Defined in `components/shared_contract.py`:

```python
class RequestDTO(TypedDict):
    player_input: str
    request_type: str  # "scenario_action", "rag_query", "npc_interaction"
    _game_engine_ref: GameEngine  # Direct engine access (no copying)
    _policy_engine_ref: PolicyEngine
    # ... other metadata

class GameResponseDTO(TypedDict):
    response_type: str  # "scenario", "rag_result", "npc_response"
    scenario: Optional[ScenarioResponseDTO]
    rag_result: Optional[RAGResponseDTO]
    npc_response: Optional[NPCResponseDTO]
    # ... response data
```

**Key Pattern**: DTOs pass engine references instead of state copies. Agents read state directly from engines.

---

## Critical File Reference

### Entry Points
- **`haystack_dnd_game.py`**: Main game loop and turn processing
- **`orchestrator/pipeline_integration.py`**: Pipeline routing hub (PipelineOrchestrator class)

### Core Components
- **`components/game_engine.py`**: Authoritative runtime state (7-step skill resolution)
- **`components/character_manager.py`**: D&D character management
- **`components/session_manager.py`**: Persistence coordination
- **`components/policy.py`**: Rule profiles (RAW/HOUSE/EASY)
- **`components/shared_contract.py`**: DTO definitions (RequestDTO, GameResponseDTO)

### Agents
- **`agents/main_interface_agent_fixed.py`**: Intent classification (deterministic)
- **`agents/scenario_generator_agent.py`**: Scenario generation
- **`agents/rag_retriever_agent.py`**: Document retrieval
- **`agents/npc_controller_agent.py`**: NPC dialogue

### Configuration
- **`config/llm_config.py`**: LLM configuration (Gemini 2.0 Flash)
- **`config/logging_config.py`**: Centralized logging (dual console + file)

### Document Processing
- **`generators/batch_qdrant_indexer.py`**: Main document indexer
- **`generators/docling_converter.py`**: PDF/text conversion (uses Docling)
- **`generators/gemini_vision_captioner.py`**: Image captioning

### Storage
- **`storage/simple_document_store.py`**: Qdrant wrapper for vector search

---

## Documentation

**Start here**: `docs/CURRENT_SYSTEM_ARCHITECTURE.md` - Complete system architecture with diagrams, all 15 implemented features, and development guide.

**Current plan**: `docs/REBUILD_PLAN_V5.md` — the authoritative status audit and
rebuild plan, superseding `COMBAT_ENGINE_IMPLEMENTATION_PLAN.md` v4.1. Read §13
(decisions D1-D6) first; it supersedes earlier text in that document.

**Full documentation index**: `docs/INDEX.md`

Key docs:
- `docs/guides/FRESH_REPO_SETUP_GUIDE.md` - Complete setup for new developers
- `docs/guides/INTEGRATION_GUIDE.md` - Adding new systems
- `docs/analysis/GAME_STATE_ANALYSIS.md` - State management patterns

---

## Common Modifications

### Adding a New Agent
1. Create agent in `agents/` directory
2. Add pipeline in `orchestrator/pipeline_integration.py`
3. Update intent classification in `agents/main_interface_agent_fixed.py`
4. Wire up in `PipelineOrchestrator.__init__()`

### Adding a Game Mechanic
1. Implement logic in appropriate component (`game_engine.py`, `character_manager.py`)
2. Update TypedDict schemas in `shared_contract.py` if needed
3. Add tests in `tests/`
4. Document in `docs/`

### Indexing New Campaign Documents
1. Place PDFs/text files in a directory
2. Run: `python generators/batch_qdrant_indexer.py`
3. Follow prompts to specify collection name and indexing options

### Changing LLM Configuration
Edit `config/llm_config.py`:
- Model name (default: `gemini-2.0-flash`)
- Temperature settings per agent
- Generation config (max_tokens, etc.)

---

## Type Safety Pattern

All state uses TypedDict for strict validation:

```python
class CharacterRuntimeState(TypedDict, total=False):
    """Enforced keys only"""
    position: Dict[str, int]
    hidden: bool
    initiative: int
    last_action: Optional[str]

# Raises error if wrong keys added
game_state.characters[char_id] = validated_state
```

---

## Logging Pattern

```python
from config.logging_config import get_logger
logger = get_logger(__name__)

# Logs to both console (INFO+) and file (DEBUG+)
logger.info(f"🎲 Game starting...")
logger.debug(f"📊 Detailed state: {state}")
logger.warning(f"⚠️ Issue detected")
logger.error(f"❌ Failed: {error}")
```

Logs written to: `logs/dnd_game_YYYYMMDD_HHMMSS.log`

---

## Known Limitations

See `docs/REBUILD_PLAN_V5.md` §2 for verified per-subsystem status. Historically
reported limitations, and where they now stand:

1. ~~**RAG System**~~ — FIXED (plan 0.2/0.17). Retrieved lore was written to
   `rag["response"]` and read from `rag["rag_context"]`, so every document was
   discarded; and the Cosmere Radiant's Handbook was never indexed at all.
2. ~~**Skill Pipeline**~~ — FIXED (plan 2.1). It had zero production callers, so
   no dice were rolled outside combat. Also: the requested DC was discarded, so
   difficulty had no effect on outcomes.
3. ~~**Quest Progression**~~ — FIXED (plan 2.3). The prompt emitted `"quests"`
   while the code read `"quest_objectives"`, and `complete_quest_objective()`
   had no callers.
4. ~~**Combat System**~~ — FIXED (plan 1.1-1.8). Every attack cancelled because
   entities had no position or senses; `AbilityConfig(score=...)` was silently
   ignored so all six ability scores were stuck at 10; and no Roshar surge could
   even be constructed.

Genuinely open: see `docs/REBUILD_PLAN_V5.md` §6 and D6's v2 backlog (economy,
downtime, multiclassing, tactical depth, full spellcasting, Phase 5 web UI).

---

## Performance Metrics

- **Initialization**: 5-10 seconds
- **Turn processing**: 2-5 seconds per turn
- **Memory usage**: 200-300 MB
- **LLM tokens**: ~4400 tokens/turn
- **Cost**: ~$0.0002 per turn with Gemini 2.0 Flash

---

## LLM provider switch (Gemini direct vs gateway)

Two transports reach the same Gemini models. gateway exists because the direct
API returned HTTP 500 on every combat-AI call during a live playtest, which
silently reduced every NPC to "attack the nearest player".

```bash
# Direct Gemini API (default) — needs GEMINI_API_KEY
export LLM_PROVIDER=gemini

# Via the organisation gateway (native Gemini API at the-optional-gateway)
export LLM_PROVIDER=gateway

# Prefer gateway when a token resolves, else fall back to the direct API
export LLM_PROVIDER=auto
```

Credential resolution (`config/gateway.py`), all **outside** the repo:

1. `GATEWAY_TOKEN` or `GATEWAY_API_KEY`
2. **`the-sso-helper getToken`** — the path that works here; mints a fresh
   OAuth **ID** token (not the access token) via PKCE, cached 25 minutes
3. `gateway-lib.perform_login()` (SSO, if installed)
4. `~/.gateway-cli` — may be stale; an expired token is detected and reported

**Corporate TLS**: the network terminates TLS with an internal root that is in
the macOS keychain but not in `certifi`'s bundle, so requests fail with
`CERTIFICATE_VERIFY_FAILED ... self-signed certificate in certificate chain`.
`config/gateway.py` assembles a bundle from the system keychains (cached at
`~/.cache/roshar-dnd/gateway-ca.pem`) and passes a real `SSLContext`.
Verification is never disabled. Override with `GATEWAY_CA_BUNDLE=/path.pem`,
or `pip install a-vendor-certifi-package` and it will be preferred. Set `GEMINI_CA_BUNDLE=1`
to apply the same trust to the direct API.

`gateway-cli` is **not** a command on this machine — don't run `gateway-cli login`.
The the-sso-helper mechanism is borrowed from `pkg-wiki-cli`
(`src/pkgwiki/core/auth.py`), which reaches the same gateway. gateway rejects
the access token, so the ID token is required.

`.env`, `.gateway-cli*`, `gateway_token*` and `secrets/` are gitignored. Check the
active transport without printing any secret:

```bash
python -c "from config.gateway import describe; print(describe())"
```

`GatewayChatGenerator` mirrors `GeminiChatGenerator`'s constructor, `run()`
contract and `GeminiAPIError` failures, so switching transports needs no changes
to agents, schemas or the retry path. Both retry 408/429/5xx with backoff and
deliberately do NOT retry 400/403.

---

## Models & Dependencies

**LLM**: gemini-2.5-flash (via google-genai SDK)
**Embeddings**: BAAI/bge-large-en-v1.5 (1024-dim vectors)
**Vector DB**: Qdrant (local storage: `./qdrant_storage/`)
**Document Parser**: Docling 2.0+

See `requirements.txt` for complete dependency list.