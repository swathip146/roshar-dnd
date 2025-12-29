# Scenario Generator Enhancement Implementation Plan

## Overview
This plan enhances the scenario generator agent to create comprehensive D&D scenarios using 9 detailed categories of context information. The goal is to move from basic scenario generation to rich, contextually-aware D&D experiences.

## Current State Analysis

### Available DTO Fields and Enhanced Architecture
Based on `shared_contract.py` RequestDTO structure and enhanced game components:

**Current DTO Fields:**
- `player_input`: Raw player action text
- `action`: Processed action verb
- `target`: Target of action (NPC/object/place)
- `context`: Game context dictionary
- `rag`: RAG context with retrieved information
- `arguments`: Structured action parameters
- `correlation_id`, `ts`: Request tracking
- `confidence`: Classification confidence
- `metadata`: Additional processing info

**Enhanced Game Architecture Components:**
- **GameEngine**: [`components/game_engine.py:17`](components/game_engine.py:17) - GameState class with authoritative state
- **SessionManager**: [`components/session_manager.py:36`](components/session_manager.py:36) - Persistent session management
- **CharacterManager**: [`components/character_manager.py:45`](components/character_manager.py:45) - Party and character tracking
- **GameInitialization**: [`game_initialization.py:27`](game_initialization.py:27) - Campaign and save game setup

### Current Context Information Available
- **Basic**: Player input, action verb, target
- **Location**: Available in `context` dict (basic)
- **RAG**: Retrieved lore/rules information
- **Limited**: No enhanced game state, party stats, detailed environment, NPC states, quest tracking

### Enhanced Context Requirements (Per User Feedback)
**GameState Enhancements Needed:**
- `scene_summary`: Last 2-3 actions/events
- `unresolved_hooks`: Open plot threads
- `pacing_state`: Recent encounter types (combat/social/exploration)
- `tone`: Current atmosphere
- `location_tags`: Interior/exterior, dungeon/urban/wilderness
- `map_features`: Exits, cover, hazards, lighting
- `interactables`: Doors, levers, objects with affordances
- `alert_level`: Awareness state
- Enhanced `context.location`: Current location name with full details

**Party Context from CharacterManager:**
- `avg_level`: Party level for DC scaling
- `party_roles`: Tank/striker/support/control composition
- `hp_state`: Health status
- `resources`: Spell slots, consumables
- `stealth_profile`: Armor visibility/noise
- `morale/exhaustion`: Condition tracking

## Enhancement Categories Mapping

### A) Narrative & Pacing
**Current Coverage**: Minimal
**Available**:
- Scene context from `context.location`
- Previous action from `player_input`

**Missing**:
- `scene_summary`: Last 2-3 actions/events
- `unresolved_hooks`: Open plot threads
- `pacing_state`: Recent encounter types (combat/social/exploration)
- `tone`: Current atmosphere
- `fail_forward_rules`: How failures advance plot

**Implementation**: Extract from `context` or create defaults

### B) Player Intent  
**Current Coverage**: Good
**Available**:
- `action`: Action verb (search, attack, etc.)
- `target`: Target identification
- `player_input`: Full intent text
- `arguments`: Structured parameters

**Missing**:
- `goal_hint`: What player hopes to achieve
- `risk_preference`: Cautious vs bold approach

**Implementation**: Parse from `player_input` and `arguments`

### C) Party Snapshot
**Current Coverage**: None
**Missing**:
- `avg_level`: Party level for DC scaling
- `party_roles`: Tank/striker/support/control composition
- `hp_state`: Health status
- `resources`: Spell slots, consumables
- `stealth_profile`: Armor visibility/noise
- `morale/exhaustion`: Condition tracking

**Implementation**: Add to `context` structure or use defaults

### D) Location & Environment
**Current Coverage**: Basic
**Available**:
- `context.location`: Current location name
- RAG context may include location details

**Missing**:
- `location_tags`: Interior/exterior, dungeon/urban/wilderness
- `map_features`: Exits, cover, hazards, lighting
- `interactables`: Doors, levers, objects with affordances
- `alert_level`: Awareness state

**Implementation**: Enhance `context` structure, extract from RAG

### E) NPCs/Creatures Present
**Current Coverage**: Minimal
**Available**:
- `target`: If targeting NPC
- RAG may include NPC information

**Missing**:
- `actors`: ID, role, attitude, objectives
- `truths/rumors`: Known information
- `won't_do`: Behavioral limits

**Implementation**: Add to `context`, extract from RAG, create defaults

### F) Quests & Constraints
**Current Coverage**: None
**Missing**:
- `active_quests`: Quest tracking with stages/deadlines
- `taboos`: Content safety rules
- `spoiler_sensitivity`: Plot reveal limits

**Implementation**: Add quest tracking to context, safety defaults

### G) Mechanics Policy
**Current Coverage**: Basic
**Available**:
- Can infer difficulty from context

**Missing**:
- `difficulty_target`: Explicit difficulty setting
- `dc_policy`: Allowed DC ranges and skill mapping
- `combat_budget`: Encounter intensity guidelines
- `choice_count`: Target number of options

**Implementation**: Add mechanics policy to context, use defaults

### H) RAG Snippets
**Current Coverage**: Good
**Available**:
- `rag.response`: Retrieved context
- `rag.docs`: Document list
- `rag.confidence`: Relevance score

**Missing**:
- Structured lore facts with priorities
- Contradiction constraints
- Source hierarchy

**Implementation**: Parse RAG response into structured facts

### I) Output Contract
**Current Coverage**: Basic
**Available**:
- JSON schema definition exists

**Missing**:
- Enhanced schema with GM notes
- Validation requirements
- State diff tracking

**Implementation**: Extend current schema

## Implementation Plan

### Phase 1: Context Extraction Enhancement
1. **Update `create_scenario_from_dto` function** to extract comprehensive context
2. **Map available DTO fields** to the 9 categories
3. **Create intelligent defaults** for missing information
4. **Parse RAG context** into structured lore facts

### Phase 2: Prompt Template Development
1. **Design comprehensive prompt template** covering all 9 categories
2. **Include conditional sections** for missing information
3. **Add detailed examples** for each category
4. **Ensure consistent formatting** and clear instructions

### Phase 3: Enhanced JSON Schema
1. **Extend output schema** with additional fields:
   - `gm_notes`: Hidden DM information
   - `state_effects`: Explicit state changes
   - `difficulty_scaling`: Actual DCs used
   - `narrative_threads`: Hook progression
2. **Add validation requirements**
3. **Include metadata** for debugging

### Phase 4: Context Integration Points
1. **Session Manager Integration**: Track party state, quests, narrative threads
2. **Game Engine Integration**: Extract party composition, resources, location details
3. **Campaign Context**: Access quest status, world state, NPC relationships

## Detailed Implementation Steps

### Step 1: Enhance Context Extraction
```python
def extract_comprehensive_context(dto: Dict[str, Any]) -> Dict[str, Any]:
    """Extract all 9 categories of context from DTO"""
    context = {
        'narrative': extract_narrative_context(dto),
        'player_intent': extract_player_intent(dto),
        'party': extract_party_context(dto),
        'location': extract_location_context(dto),
        'npcs': extract_npc_context(dto),
        'quests': extract_quest_context(dto),
        'mechanics': extract_mechanics_policy(dto),
        'rag': extract_structured_rag(dto),
        'output_contract': get_output_requirements()
    }
    return context
```

### Step 2: Enhanced Prompt Template
Create comprehensive prompt with sections for:
- **Context Summary**: All 9 categories formatted
- **Generation Guidelines**: Specific instructions per category
- **Output Schema**: Detailed JSON requirements
- **Examples**: Sample scenarios demonstrating format

### Step 3: Default Value System
Implement intelligent defaults for missing information:
- **Party Level**: Default to 3 if unknown
- **Difficulty**: Infer from context or default to medium
- **Location Tags**: Parse from location name
- **Tone**: Infer from recent actions or default to heroic

### Step 4: RAG Enhancement
Parse RAG responses into structured format:
- **Lore Facts**: Extract key information with confidence
- **Constraints**: Identify what not to contradict
- **Source Priority**: Campaign > module > core rules

## Integration Requirements

### Context Sources
1. **Session Manager**: Party state, resources, quest progress
2. **Game Engine**: Character sheets, location details, NPC states  
3. **Campaign Data**: Quest definitions, world state, narrative threads
4. **RAG System**: Lore facts, rules clarifications, NPC information

### Enhanced DTO Structure
Consider extending RequestDTO with:
```python
party_state: Dict[str, Any]  # HP, resources, conditions
quest_context: Dict[str, Any]  # Active quests, progress
narrative_state: Dict[str, Any]  # Hooks, pacing, tone
mechanics_policy: Dict[str, Any]  # DC ranges, difficulty
```

## Success Metrics

### Quality Indicators
- **Context Utilization**: All 9 categories represented in prompts
- **Scenario Richness**: Multiple interaction types per scenario
- **Narrative Continuity**: Proper hook progression and pacing
- **Mechanical Consistency**: Appropriate DCs and skill usage

### Technical Metrics
- **Prompt Completeness**: All available context included
- **Default Handling**: Graceful degradation with missing info
- **RAG Integration**: Proper lore fact incorporation
- **Schema Compliance**: Valid JSON output generation

## Risk Mitigation

### Missing Context Handling
- **Graceful Defaults**: Always provide meaningful fallbacks
- **Context Prioritization**: Focus on available high-quality information
- **Progressive Enhancement**: Better scenarios with more context

### Performance Considerations
- **Prompt Length**: Balance comprehensiveness with token limits
- **Context Parsing**: Efficient extraction without over-processing
- **Caching**: Reuse extracted context where appropriate

## Next Steps

1. **Implement Phase 1**: Enhanced context extraction
2. **Create comprehensive prompt template**
3. **Test with existing DTO structure**
4. **Iterate based on scenario quality**
5. **Plan integration with broader context sources**

This plan provides a roadmap for transforming basic scenario generation into rich, contextually-aware D&D experiences while maintaining compatibility with the existing system architecture.