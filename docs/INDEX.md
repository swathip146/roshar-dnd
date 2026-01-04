# D&D Game System - Documentation Index

This directory contains all documentation for the Roshar D&D Game System, now organized in logical folders for easy navigation.

## ⭐ Start Here

**[CURRENT_SYSTEM_ARCHITECTURE.md](CURRENT_SYSTEM_ARCHITECTURE.md)** - Complete architecture, features, and implementation guide

This comprehensive document covers:
- System architecture with diagrams
- All core components (GameEngine, CharacterManager, SessionManager, PolicyEngine)
- Agent system (4 agents with workflows)
- Pipeline architecture and data flow
- ✅ All implemented features (15 categories)
- 🔜 Unimplemented features (11 categories)
- Technical details and development guide

---

## 📖 Guides

**Location**: `guides/`

### Setup & Installation
- **[FRESH_REPO_SETUP_GUIDE.md](guides/FRESH_REPO_SETUP_GUIDE.md)** - Complete setup guide for new installations
- **[DEPENDENCIES_INSTALLATION_GUIDE.md](guides/DEPENDENCIES_INSTALLATION_GUIDE.md)** - Dependency installation instructions
- **[INTEGRATION_GUIDE.md](guides/INTEGRATION_GUIDE.md)** - Integration guide for the system

### Logging & Debugging
- **[LOGGING_IMPLEMENTATION.md](guides/LOGGING_IMPLEMENTATION.md)** - Logging system documentation
- **[LOGGING_NOISE_REDUCTION.md](guides/LOGGING_NOISE_REDUCTION.md)** - Logging noise reduction details

---

## 🏗️ Architecture

**Location**: `architecture/`

- **[dnd_game_architecture_report.md](architecture/dnd_game_architecture_report.md)** - Current system architecture overview
- **[dnd_haystack_full_phased_plan.md](architecture/dnd_haystack_full_phased_plan.md)** - Full phased implementation plan

---

## 🔍 Analysis

**Location**: `analysis/`

### Game State & Data
- **[GAME_STATE_ANALYSIS.md](analysis/GAME_STATE_ANALYSIS.md)** - Game state architecture analysis
- **[DTO_ANALYSIS_AND_REDESIGN.md](analysis/DTO_ANALYSIS_AND_REDESIGN.md)** - Data transfer object design
- **[WORLD_STATE_ADAPTER_ANALYSIS.md](analysis/WORLD_STATE_ADAPTER_ANALYSIS.md)** - World state adapter analysis

### Agents & Communication
- **[agent_architecture_analysis.md](analysis/agent_architecture_analysis.md)** - Agent architecture overview
- **[agent_communication_analysis.md](analysis/agent_communication_analysis.md)** - Agent communication patterns
- **[interface_agent_routing_strategy_analysis.md](analysis/interface_agent_routing_strategy_analysis.md)** - Routing strategy analysis

---

## 🔄 Workflows

**Location**: `workflows/`

- **[HAYSTACK_INTEGRATION_README.md](workflows/HAYSTACK_INTEGRATION_README.md)** - Haystack integration overview
- **[RAG_FIRST_WORKFLOW_DOCUMENTATION.md](workflows/RAG_FIRST_WORKFLOW_DOCUMENTATION.md)** - RAG workflow documentation

---

## 🏛️ Detailed Architecture

**Location**: `arch/`

The `arch/` subdirectory contains detailed architectural documentation:

- **[arch/PHASE1_COMPLETION_SUMMARY.md](arch/PHASE1_COMPLETION_SUMMARY.md)** - Phase 1 completion summary
- **[arch/dnd_game_architecture_plan.md](arch/dnd_game_architecture_plan.md)** - Architecture blueprint
- **[arch/architecture_comparison_analysis.md](arch/architecture_comparison_analysis.md)** - Architecture comparisons
- **[arch/modular_dm_assistant_architecture.md](arch/modular_dm_assistant_architecture.md)** - Modular design
- **[arch/dnd_haystack_fix_plan.md](arch/dnd_haystack_fix_plan.md)** - Haystack fixes
- **[arch/dnd_haystack_revised_plan.md](arch/dnd_haystack_revised_plan.md)** - Revised plan
- **[arch/dnd_system_enhancement_implementation_plan.md](arch/dnd_system_enhancement_implementation_plan.md)** - Enhancement plan

---

## 📦 Legacy Documentation

**Location**: `legacy/`

Outdated documentation has been moved to the **legacy/** directory for historical reference:

- **Old async processing plans** (superseded - issues resolved)
- **Old assistant analysis documents** (superseded by CURRENT_SYSTEM_ARCHITECTURE.md)
- **Old test reports** (from pre-production state)
- **Old implementation plans** (completed or superseded)
- **Old RAG/scenario plans** (implemented)
- **Old architecture diagrams** (proposals from September 2025)

See **[legacy/README.md](legacy/README.md)** for complete details on what was moved and why.

---

## ⚔️ Combat System Documentation

**Status:** Phase 3 Ready for Implementation (Updated: 2026-01-03)
**Latest:** Phase 3 optimization analysis complete with dnd_engine integration improvements

### Master Plans
- **[COMBAT_ENGINE_IMPLEMENTATION_PLAN.md](COMBAT_ENGINE_IMPLEMENTATION_PLAN.md)** - Complete combat system implementation plan (4400+ lines, Version 4.0)
  - 4-phase implementation strategy
  - Generic, data-driven architecture with ACTION_REGISTRY
  - **UPDATED:** Phase 3 optimized with dnd_engine leverage (8 methods improved, ~50-60 lines saved)
  - dnd_engine integration for HP tracking, action economy, death saves
  - Roshar mechanics support (Cosmere 5e compatible)
  - All component specifications with optimized code examples

- **[COMBAT_SYSTEM_READINESS_REPORT.md](COMBAT_SYSTEM_READINESS_REPORT.md)** - Overall status and readiness assessment
  - Phase 1/1.5 completion summary (✅ COMPLETE - 18/18 tests passing)
  - Phase 2 architecture finalized (paused for Phase 3 optimization)
  - Phase 3 implementation readiness with optimization analysis
  - Timeline and risk assessment

### Architecture Documentation
- **[COMBAT_PLAN_GENERIC_ARCHITECTURE_UPDATE.md](COMBAT_PLAN_GENERIC_ARCHITECTURE_UPDATE.md)** - Generic architecture design
  - Data-driven action discovery via ACTION_REGISTRY
  - Metadata-driven validation/consumption
  - Code reduction analysis (~25% less code)
  - Extensibility examples

- **[DND_ENGINE_COMBAT_CAPABILITIES.md](DND_ENGINE_COMBAT_CAPABILITIES.md)** - dnd_engine analysis
  - Event-driven architecture explanation
  - Native Action framework documentation
  - Action economy system (actions, bonus actions, reactions)
  - Condition system patterns
  - Health system (HP, death saves, temporary HP)

- **[ROSHAR_COMBAT_MECHANICS_INTEGRATION.md](ROSHAR_COMBAT_MECHANICS_INTEGRATION.md)** - Official Roshar rules integration
  - 9 Radiant Orders specifications (Windrunner, Skybreaker, etc.)
  - 10 Surges mechanics (Lashing, Soulcasting, etc.)
  - Stormlight tracking system (capacity = Level × 2)
  - Shardblade/Shardplate rules (soul damage, armor HP)
  - Updated ACTION_REGISTRY with Roshar actions

- **[COMBAT_PLAN_METHOD_OPTIMIZATION_ANALYSIS.md](COMBAT_PLAN_METHOD_OPTIMIZATION_ANALYSIS.md)** - **NEW** Phase 3 optimization analysis
  - Method-by-method review of all 28 CombatSessionManager methods
  - Identifies dnd_engine leverage opportunities
  - 8 methods optimized (4 high priority, 2 medium, 2 low)
  - 16 methods already optimal with generic architecture
  - Code reduction: ~50-60 lines (7-8% improvement)
  - New capabilities: death saves, temp HP, resistance, range/LoS, condition events

### Implementation Reports
- **[PHASE_1_IMPLEMENTATION_COMPLETE.md](PHASE_1_IMPLEMENTATION_COMPLETE.md)** - Phase 1 completion report
  - NPC stat generation (8/8 tests passing)
  - Haystack 2.0 + Pydantic validation
  - Template loading system

- **[COMBAT_PLAN_NPC_INTEGRATION_GAPS.md](COMBAT_PLAN_NPC_INTEGRATION_GAPS.md)** - NPC registry gap analysis
- **[NPC_JSON_CONVERSION_COMPLETE.md](NPC_JSON_CONVERSION_COMPLETE.md)** - JSON conversion report

### Other Combat Documents
- **[COMBAT_AGENT_ARCHITECTURE_DECISION.md](COMBAT_AGENT_ARCHITECTURE_DECISION.md)** - Architecture decision rationale

---

## 📊 Quick Reference

### By Purpose

**I want to...**

- **Set up the project** → Start with [guides/FRESH_REPO_SETUP_GUIDE.md](guides/FRESH_REPO_SETUP_GUIDE.md)
- **Understand the architecture** → Read [CURRENT_SYSTEM_ARCHITECTURE.md](CURRENT_SYSTEM_ARCHITECTURE.md)
- **Learn about components** → Browse [analysis/](analysis/) folder
- **Understand workflows** → Check [workflows/](workflows/) folder
- **Review implementation plans** → See [architecture/](architecture/) folder
- **Debug or log issues** → Check [guides/LOGGING_IMPLEMENTATION.md](guides/LOGGING_IMPLEMENTATION.md)
- **See historical context** → Browse [legacy/](legacy/) folder

### By Component

**Core System**
- Architecture: [CURRENT_SYSTEM_ARCHITECTURE.md](CURRENT_SYSTEM_ARCHITECTURE.md), [architecture/dnd_game_architecture_report.md](architecture/dnd_game_architecture_report.md)
- Game State: [analysis/GAME_STATE_ANALYSIS.md](analysis/GAME_STATE_ANALYSIS.md)
- Data Transfer: [analysis/DTO_ANALYSIS_AND_REDESIGN.md](analysis/DTO_ANALYSIS_AND_REDESIGN.md)

**Agents**
- Overview: [analysis/agent_architecture_analysis.md](analysis/agent_architecture_analysis.md)
- Communication: [analysis/agent_communication_analysis.md](analysis/agent_communication_analysis.md)
- Routing: [analysis/interface_agent_routing_strategy_analysis.md](analysis/interface_agent_routing_strategy_analysis.md)

**Pipelines & Integration**
- Haystack: [workflows/HAYSTACK_INTEGRATION_README.md](workflows/HAYSTACK_INTEGRATION_README.md)
- RAG: [workflows/RAG_FIRST_WORKFLOW_DOCUMENTATION.md](workflows/RAG_FIRST_WORKFLOW_DOCUMENTATION.md)

---

## 📁 Documentation Structure

```
docs/
├── CURRENT_SYSTEM_ARCHITECTURE.md    # ⭐ Main comprehensive doc
├── INDEX.md                          # This file
├── guides/                           # Setup and usage guides
│   ├── FRESH_REPO_SETUP_GUIDE.md
│   ├── DEPENDENCIES_INSTALLATION_GUIDE.md
│   ├── INTEGRATION_GUIDE.md
│   ├── LOGGING_IMPLEMENTATION.md
│   └── LOGGING_NOISE_REDUCTION.md
├── architecture/                     # Architecture documentation
│   ├── dnd_game_architecture_report.md
│   └── dnd_haystack_full_phased_plan.md
├── analysis/                         # Component analysis docs
│   ├── GAME_STATE_ANALYSIS.md
│   ├── DTO_ANALYSIS_AND_REDESIGN.md
│   ├── WORLD_STATE_ADAPTER_ANALYSIS.md
│   ├── agent_architecture_analysis.md
│   ├── agent_communication_analysis.md
│   └── interface_agent_routing_strategy_analysis.md
├── workflows/                        # Workflow documentation
│   ├── HAYSTACK_INTEGRATION_README.md
│   └── RAG_FIRST_WORKFLOW_DOCUMENTATION.md
├── arch/                            # Detailed architecture docs
│   └── [7 detailed architecture files]
└── legacy/                          # Historical documentation
    └── [42 outdated files]
```

---

## 📝 Documentation Standards

All documentation follows these standards:
- **Last Updated Date**: Every file has a last updated timestamp
- **Clear Headings**: Hierarchical structure with clear sections
- **Code Examples**: Inline code blocks for technical details
- **Links**: Cross-references between related documents
- **Status Indicators**: ✅ for implemented, 🔜 for planned

---

*Last updated: 2025-12-29*
*Total Active Documents: 20*
*Legacy Documents: 42*
