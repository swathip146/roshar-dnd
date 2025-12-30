# Roshar D&D Game System

An AI-enhanced D&D Game Master Assistant powered by Haystack 2.0 and Google Gemini, set in Brandon Sanderson's Stormlight Archive world.

## 🎯 Overview

The Roshar D&D Game System is a production-ready, AI-powered Dungeon Master assistant that provides dynamic D&D 5e gameplay with Cosmere/Roshar extensions. It features intelligent scenario generation, RAG-enhanced lore retrieval, and comprehensive state management.

### Key Features

- **AI-Powered Scenario Generation**: Context-aware D&D scenarios with dynamic choices
- **Intelligent Routing**: LLM-based intent classification routes player input to appropriate pipelines
- **RAG-Enhanced World Knowledge**: Semantic search retrieves campaign-specific lore and rules
- **Complete D&D 5e Mechanics**: 7-step skill pipeline with full provenance tracking
- **Roshar/Cosmere Integration**: Knights Radiant, investiture, spren bonding, ideal progression
- **Clean Architecture**: No state duplication, direct engine access, clear separation of concerns
- **Comprehensive Logging**: Timestamped debug logs with dual output (console + file)
- **Session Persistence**: Multiple save slots with full game state serialization

## 🚀 Quick Start

### 1. Setup

Follow the setup guide: **[docs/guides/FRESH_REPO_SETUP_GUIDE.md](docs/guides/FRESH_REPO_SETUP_GUIDE.md)**

### 2. Install Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

See detailed instructions: **[docs/guides/DEPENDENCIES_INSTALLATION_GUIDE.md](docs/guides/DEPENDENCIES_INSTALLATION_GUIDE.md)**

### 3. Configure API Key

Create a `.env` file in the project root:

```bash
GEMINI_API_KEY=your_api_key_here
```

The `run_game.sh` script will automatically load this file.

### 4. Run the Game

```bash
./run_game.sh
```

## 📚 Documentation

### ⭐ Start Here

**[docs/CURRENT_SYSTEM_ARCHITECTURE.md](docs/CURRENT_SYSTEM_ARCHITECTURE.md)** - Complete system architecture, all features, and implementation guide

This comprehensive document covers:
- System architecture with diagrams
- All core components (GameEngine, CharacterManager, SessionManager, PolicyEngine)
- Agent system (4 agents with workflows)
- Pipeline architecture and data flow
- ✅ All implemented features (15 categories)
- 🔜 Unimplemented features (11 categories)
- Technical details and development guide

### Documentation Index

**[docs/INDEX.md](docs/INDEX.md)** - Complete documentation index with all guides, architecture docs, and analysis

### Organized Documentation

All documentation is now organized in logical folders:

#### 📖 Guides (`docs/guides/`)
- **FRESH_REPO_SETUP_GUIDE.md** - Complete setup guide for new installations
- **DEPENDENCIES_INSTALLATION_GUIDE.md** - Dependency installation instructions
- **INTEGRATION_GUIDE.md** - Integration guide for the system
- **LOGGING_IMPLEMENTATION.md** - Logging system documentation
- **LOGGING_NOISE_REDUCTION.md** - Logging noise reduction details

#### 🏗️ Architecture (`docs/architecture/`)
- **dnd_game_architecture_report.md** - Current system architecture overview
- **dnd_haystack_full_phased_plan.md** - Full phased implementation plan

#### 🔍 Analysis (`docs/analysis/`)
- **GAME_STATE_ANALYSIS.md** - Game state architecture analysis
- **DTO_ANALYSIS_AND_REDESIGN.md** - Data transfer object design
- **WORLD_STATE_ADAPTER_ANALYSIS.md** - World state adapter analysis
- **agent_architecture_analysis.md** - Agent architecture overview
- **agent_communication_analysis.md** - Agent communication patterns
- **interface_agent_routing_strategy_analysis.md** - Routing strategy analysis

#### 🔄 Workflows (`docs/workflows/`)
- **HAYSTACK_INTEGRATION_README.md** - Haystack integration overview
- **RAG_FIRST_WORKFLOW_DOCUMENTATION.md** - RAG workflow documentation

#### 🏛️ Detailed Architecture (`docs/arch/`)
Detailed architectural documentation including phase summaries, architecture plans, and system enhancements.

#### 📦 Legacy Documentation (`docs/legacy/`)
Outdated documentation moved for historical reference. See **[docs/legacy/README.md](docs/legacy/README.md)** for details.

## 🏗️ Project Structure

```
roshar-dnd/
├── agents/                      # AI agent implementations
│   ├── main_interface_agent_fixed.py    # Intent classifier & router
│   ├── scenario_generator_agent.py      # Creative scenario generation
│   ├── rag_retriever_agent.py           # Document retrieval
│   └── npc_controller_agent.py          # NPC interactions
├── components/                  # Game components
│   ├── game_engine.py                   # Runtime state authority
│   ├── character_manager.py             # Character sheet management
│   ├── session_manager.py               # Persistence coordination
│   ├── policy.py                        # Rule interpretation
│   ├── campaign_config.py               # Immutable campaign data
│   ├── dice.py                          # Dice rolling
│   └── rules.py                         # D&D rules enforcement
├── config/                      # Configuration and LLM setup
│   ├── llm_config.py                    # LLM configuration (Gemini)
│   ├── llm_utils.py                     # LLM utilities
│   └── logging_config.py                # Centralized logging setup
├── core/                        # Core game initialization
│   └── game_initialization.py           # Interactive game setup
├── orchestrator/                # Pipeline orchestration
│   └── pipeline_integration.py          # Pipeline routing coordinator
├── adapters/                    # Adapter layer
│   └── world_state_adapter.py           # Context extraction for agents
├── storage/                     # Storage layer
│   └── simple_document_store.py         # Qdrant document store wrapper
├── docs/                        # 📚 All documentation (organized)
│   ├── CURRENT_SYSTEM_ARCHITECTURE.md   # ⭐ Main architecture doc
│   ├── INDEX.md                         # Documentation index
│   ├── guides/                          # Setup and usage guides
│   ├── architecture/                    # Architecture documentation
│   ├── analysis/                        # Component analysis docs
│   ├── workflows/                       # Workflow documentation
│   ├── arch/                            # Detailed architecture docs
│   └── legacy/                          # Historical documentation
├── logs/                        # Runtime log files (timestamped)
├── legacy/                      # Archived legacy code
├── game_saves/                  # Saved game files
├── .env                         # API keys (create this file)
├── run_game.sh                  # Game launcher script
└── haystack_dnd_game.py         # Main entry point
```

## 🎮 System Architecture

### High-Level Flow

```
Player Input (CLI)
    ↓
HaystackDnDGame (Main Controller)
    ↓
PipelineOrchestrator (Routing Hub)
    ↓
┌─────────────┬─────────────┬─────────────┐
│  Interface  │  Scenario   │     RAG     │
│  Pipeline   │  Pipeline   │  Pipeline   │
└─────────────┴─────────────┴─────────────┘
    ↓
State Management Layer
- GameEngine (Runtime State)
- CharacterManager (Characters)
- SessionManager (Persistence)
- PolicyEngine (Rules)
- CampaignConfig (Immutable)
```

### Core Components

1. **GameEngine** - Authoritative runtime state with 7-step skill resolution
2. **CharacterManager** - D&D 5e character sheets with Roshar extensions
3. **SessionManager** - Save/load coordination and analytics
4. **PolicyEngine** - Rule interpretation (RAW/HOUSE/EASY profiles)
5. **CampaignConfig** - Immutable campaign metadata

### Agent System

- **Main Interface Agent** - Intent classification and routing
- **Scenario Generator Agent** - Context-aware scenario generation
- **RAG Retriever Agent** - Document retrieval with Qdrant
- **NPC Controller Agent** - NPC dialogue and behavior

## 🔧 Technology Stack

- **Language**: Python 3.10+
- **Pipeline Framework**: Haystack 2.0
- **LLM**: Google Gemini (gemini-2.0-flash)
- **Vector Database**: Qdrant (for RAG)
- **Embeddings**: Sentence-Transformers (all-MiniLM-L6-v2)
- **Data Validation**: Pydantic TypedDict
- **Storage**: JSON (saves, campaigns, characters)

## 🎯 Key Features Status

### ✅ Implemented

- Core game loop with CLI interface
- Intelligent routing with LLM-based intent classification
- AI-powered scenario generation
- RAG system with semantic search
- Complete D&D 5e character management
- Roshar/Cosmere extensions (Knights Radiant, spren, surges)
- 7-step skill resolution pipeline
- Session persistence with multiple save slots
- Policy profiles (RAW/HOUSE/EASY)
- Campaign system with CampaignConfig
- Comprehensive logging system
- Game initialization with fallbacks

### 🔜 Planned

- Combat system with initiative tracking
- Advanced NPC system with personality/relationships
- Inventory management
- Magic system enhancements (spell slots, concentration)
- Advanced quest system
- World map & travel
- Party management (multiple characters)
- Web UI

See **[docs/CURRENT_SYSTEM_ARCHITECTURE.md](docs/CURRENT_SYSTEM_ARCHITECTURE.md)** for complete feature lists.

## 💻 Development

### Running Tests

```bash
python -m pytest tests/
```

### Debugging

Enable debug logging by checking the latest log file:

```bash
tail -f logs/dnd_game_*.log
```

### Adding New Components

See the Development Guide section in **[docs/CURRENT_SYSTEM_ARCHITECTURE.md](docs/CURRENT_SYSTEM_ARCHITECTURE.md)** for:
- Adding a new agent
- Adding a new component
- Adding a new policy profile
- Performance profiling

## 📊 Performance

- **Initialization Time**: ~5-10 seconds
- **Turn Processing**: ~2-5 seconds per turn
- **Memory Usage**: ~200-300 MB
- **Token Usage**: ~4400 tokens/turn (~$0.0002 per turn with Gemini 2.0 Flash)

## 🔐 API Keys

This project requires a Google Gemini API key. Get yours at: https://makersuite.google.com/app/apikey

Store it in `.env`:

```bash
GEMINI_API_KEY=your_api_key_here
```

## 📝 License

[Your License Here]

## 🤝 Contributing

Contributions are welcome! Please see our contributing guidelines in the docs folder.

## 📞 Support

For questions, bug reports, or feature requests, please open an issue on the project repository.

---

**⭐ For complete system understanding, start with [docs/CURRENT_SYSTEM_ARCHITECTURE.md](docs/CURRENT_SYSTEM_ARCHITECTURE.md)**

*Last Updated: 2025-12-29*
