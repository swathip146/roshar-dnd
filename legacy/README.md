# Legacy Code Archive

This directory contains code that has been superseded or is no longer used by the active D&D game system.

## Moved on: 2025-12-29

## What's in Legacy

### Tier 1: Legacy Orchestrator Implementation
- `orchestrator/haystack_native_orchestrator.py` - Replaced by `orchestrator/pipeline_integration.py`
- `models/pydantic_dtos.py` - Replaced by `components/shared_contract.py`

### Tier 2: Superseded Pipeline Implementations
- `pipelines/phase1_pipeline.py` - Old pipeline design
- `pipelines/pipeline_factory.py` - Old factory pattern
- `components/haystack_native/` - Legacy Haystack components that were replaced

### Tier 3: Unintegrated Components
- `components/inventory_manager.py` - Inventory system that was never implemented

### Tier 4: Integration/Migration Code
- `integration/migration_script.py` - One-time migration utility
- `integration/haystack_integration_example.py` - Example code

### Tier 5: Example Files
- `examples/` - Example pipeline implementations

### Tier 6: Test/Debug Files
- `debug/` - Old test and debug scripts
- `tests/` - Deprecated test files

## Active System (19 files)

The current working D&D game uses only 19 core files:

**Entry Point:**
- `haystack_dnd_game.py`

**Core Game:**
- `core/game_initialization.py`
- `components/game_engine.py`
- `components/character_manager.py`
- `components/session_manager.py`
- `components/policy.py`
- `components/campaign_config.py`
- `components/shared_contract.py`
- `components/dice.py`
- `components/rules.py`

**Configuration:**
- `config/llm_config.py`
- `config/llm_utils.py`

**Orchestration:**
- `orchestrator/pipeline_integration.py`

**Agents:**
- `agents/scenario_generator_agent.py`
- `agents/rag_retriever_agent.py`
- `agents/npc_controller_agent.py`
- `agents/main_interface_agent_fixed.py`

**Storage & Adapters:**
- `storage/simple_document_store.py`
- `adapters/world_state_adapter.py`

## Potential Future Use

Files in this directory may be useful for:
- Historical reference
- Extracting specific logic or patterns
- Understanding design evolution
- Recovering accidentally removed functionality

## Restoration

If you need to restore any file:
```bash
git mv legacy/path/to/file.py original/path/to/file.py
```
