# Stage 1 Implementation - Simple Foundation (Weeks 1-4)

## Overview

This implements **Stage 1** of the Progressive D&D Implementation Plan - creating the simplest possible working D&D game and building it into a structured foundation ready for Stage 2 expansion.

## What's Implemented

### ✅ Week 1: Minimal Working Game
- **File**: `simple_dnd_game.py`
- **Goal**: Absolute simplest D&D game possible
- **Features**:
  - Single-file implementation using hwtgenielib
  - Basic D&D conversation with AI DM
  - Simple game state management
  - Save/load functionality
  - Interactive command loop
  - Location tracking
  - Turn history

### ✅ Week 2: Basic Structure  
- **Directory**: `simple_dnd/`
- **Goal**: Separate components for better organization
- **Components**:
  - `config.py` - Centralized configuration management
  - `scenario_generator.py` - Structured scenario generation
  - `dice.py` - Comprehensive dice rolling system
  - `game.py` - Main structured game class
  - Demo and test files

## Architecture

### Week 1 Architecture (Monolithic)
```
simple_dnd_game.py
├── SimpleDnDGame class
├── hwtgenielib integration
├── Basic save/load
└── Interactive loop
```

### Week 2 Architecture (Modular)
```
simple_dnd/
├── config.py          # GameConfig class
├── scenario_generator.py  # SimpleScenarioGenerator
├── dice.py             # SimpleDice with statistics
├── game.py             # StructuredDnDGame
└── __init__.py
```

## Key Features Implemented

### 🎲 Dice System (`simple_dnd/dice.py`)
- Basic d20 rolls
- Skill checks with modifiers and DC
- Attack rolls with critical/fumble detection  
- Damage rolls with dice expression parsing
- Roll history and statistics
- Configurable difficulty settings

### 🎭 Scenario Generation (`simple_dnd/scenario_generator.py`)
- hwtgenielib-powered scene creation
- Structured choice generation
- Context-aware scenarios (tavern, forest, dungeon, etc.)
- Fallback scenarios for reliability
- Configurable prompts and contexts

### ⚙️ Configuration System (`simple_dnd/config.py`)
- Centralized game settings
- AI model configuration
- Default game parameters
- Context descriptions
- Easily extensible for Stage 2+

### 🎮 Game Engine (`simple_dnd/game.py`)
- Structured turn processing
- Command categorization (dice, scenario, general)
- Enhanced save/load with metadata
- Game statistics tracking
- Interactive command interface
- Turn-based state management

## Usage

### Running the Simple Game (Week 1)
```bash
python simple_dnd_game.py
```

### Running the Structured Game (Week 2)  
```bash
python demo_structured_game.py  # For demonstration
python -c "from simple_dnd.game import StructuredDnDGame; StructuredDnDGame().run_interactive()"
```

### Testing
```bash
python test_simple_game.py  # Test Week 1 implementation
python demo_structured_game.py  # Test Week 2 components
```

## Commands Available

### Game Commands
- Natural language actions: "I look around the tavern"
- Movement: "I go to the forest" 
- Dice rolling: "roll d20", "skill check"
- Scenario generation: "generate new scenario"

### Meta Commands
- `save` - Save current game
- `load` - Load saved game  
- `status` - Show game statistics
- `help` - Show help information
- `quit` - Exit game

## Framework Integration

### hwtgenielib Usage
- ✅ `AppleGenAIChatGenerator` for all AI text generation
- ✅ `ChatMessage` for structured prompt handling
- ✅ Configured for AWS Anthropic Claude Sonnet model
- ✅ Error handling for API failures

### Extension Points for Stage 2
- Hook systems in orchestrator (`pre_hooks`, `post_hooks`)
- Modular component architecture
- Configuration-driven behavior
- Structured data formats ready for enhancement

## File Structure
```
📁 Stage 1 Implementation
├── simple_dnd_game.py           # Week 1: Monolithic implementation
├── test_simple_game.py          # Week 1: Basic testing
├── demo_structured_game.py      # Week 2: Component demonstration
├── STAGE1_README.md             # This documentation
└── simple_dnd/                  # Week 2: Modular architecture
    ├── __init__.py
    ├── config.py                # Configuration management
    ├── scenario_generator.py    # AI-powered scenario creation  
    ├── dice.py                  # Dice rolling with statistics
    └── game.py                  # Main structured game class
```

## Stage 1 Success Criteria - ✅ COMPLETED

- [x] Player can have basic D&D conversation with LLM
- [x] Simple scenario generation works  
- [x] Basic dice rolling for simple checks
- [x] Game state saves/loads
- [x] Foundation ready for Stage 2 expansion

## Architectural Readiness for Stage 2

The Week 2 implementation provides extension points for Stage 2 enhancements:

### 🔌 Hook System Ready
- `pre_hooks` and `post_hooks` in orchestrator
- Ready for Saga Manager integration
- Decision logging integration points

### 📦 Modular Components  
- Separated concerns (dice, scenarios, config)
- Easy to extend without breaking existing functionality
- Configuration-driven behavior

### 💾 Enhanced Save System
- Structured save format with versioning
- Component statistics included
- Ready for complex game state

### 🎯 Framework Consistency
- hwtgenielib used throughout
- Consistent error handling
- Structured data formats

## What's Next (Stage 2)

Stage 2 will add:
- Haystack RAG integration for campaign context
- Simple orchestrator pattern
- Campaign selection system
- Enhanced scenario generation with RAG context

The current implementation provides a solid foundation that can be enhanced without breaking existing functionality.

## Dependencies

- `hwtgenielib` - For AI text generation
- Python 3.7+ - For dataclasses and type hints
- Standard library only (json, time, os, random)

## Configuration

The system uses AWS Anthropic Claude Sonnet by default:
```python
model="aws:anthropic.claude-sonnet-4-20250514-v1:0"
```

Ensure hwtgenielib is properly configured with AWS credentials for full functionality.