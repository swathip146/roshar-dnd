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

# Run integration test (most comprehensive)
python3 tests/test_integration.py

# Specific test with verbose output
pytest -vv tests/test_integration.py::test_name
```

**Latest test status**: 8.5/10 overall rating (13/13 features tested, 85% fully working)

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

**Test report**: `docs/reports/TEST_REPORT_INTEGRATION.md` - Latest test results (8.5/10 rating)

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

From test report (`docs/reports/TEST_REPORT_INTEGRATION.md`):

1. **RAG System**: Functional but requires Qdrant setup for full lore retrieval
2. **Skill Pipeline**: 7-step resolution exists but not automatically triggered in basic gameplay
3. **Quest Progression**: System initialized but not actively advancing during play
4. **Combat System**: Not fully implemented (marked for future enhancement)

---

## Performance Metrics

- **Initialization**: 5-10 seconds
- **Turn processing**: 2-5 seconds per turn
- **Memory usage**: 200-300 MB
- **LLM tokens**: ~4400 tokens/turn
- **Cost**: ~$0.0002 per turn with Gemini 2.0 Flash

---

## Models & Dependencies

**LLM**: gemini-2.0-flash (via google-genai SDK)
**Embeddings**: BAAI/bge-large-en-v1.5 (1024-dim vectors)
**Vector DB**: Qdrant (local storage: `./qdrant_storage/`)
**Document Parser**: Docling 2.0+

See `requirements.txt` for complete dependency list.