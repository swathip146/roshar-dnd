# Roshar D&D Game System

An AI-enhanced D&D Game Master Assistant powered by Haystack and Gemini.

## Quick Start

1. **Setup**: See [docs/FRESH_REPO_SETUP_GUIDE.md](docs/FRESH_REPO_SETUP_GUIDE.md)
2. **Install Dependencies**: See [docs/DEPENDENCIES_INSTALLATION_GUIDE.md](docs/DEPENDENCIES_INSTALLATION_GUIDE.md)
3. **Run the game**:
   ```bash
   ./run_game.sh
   ```

## Documentation

All project documentation is located in the **[docs/](docs/)** directory.

- **[Documentation Index](docs/INDEX.md)** - Complete guide to all documentation
- **[Architecture Report](docs/dnd_game_architecture_report.md)** - System architecture overview
- **[Logging System](docs/LOGGING_IMPLEMENTATION.md)** - Logging configuration and usage

## Project Structure

```
roshar-dnd/
├── agents/                 # AI agent implementations
├── components/             # Game components (engine, policy, dice, etc.)
├── config/                 # Configuration and LLM setup
├── core/                   # Core game initialization
├── orchestrator/           # Pipeline orchestration
├── docs/                   # 📚 All documentation
├── logs/                   # Runtime log files (timestamped)
├── legacy/                 # Archived legacy code
├── game_saves/             # Saved game files
└── haystack_dnd_game.py   # Main entry point
```

## Features

- **AI-Powered Scenario Generation**: Dynamic D&D scenarios using Gemini
- **RAG-Enhanced Lore**: Retrieve campaign-specific knowledge
- **Comprehensive Logging**: Detailed runtime logs in `logs/`
- **State Management**: Persistent game state and character data
- **Haystack Integration**: Modern pipeline architecture

## Development

- **Architecture**: See [docs/dnd_game_architecture_report.md](docs/dnd_game_architecture_report.md)
- **Migration Plan**: See [docs/dnd_haystack_full_phased_plan.md](docs/dnd_haystack_full_phased_plan.md)
- **Logging**: See [docs/LOGGING_IMPLEMENTATION.md](docs/LOGGING_IMPLEMENTATION.md)

## System Requirements

- Python 3.10+
- Gemini API key
- Virtual environment recommended

## License

[Your License Here]

---

*For detailed documentation, see the [docs/](docs/) directory and [Documentation Index](docs/INDEX.md)*
