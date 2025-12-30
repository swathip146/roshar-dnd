# Full Haystack Migration Plan for D&D Assistant

## Current Architecture Analysis

### Core Dependencies
- **AgentOrchestrator**: Message bus-based agent coordination system
- **BaseCommandHandler**: Pluggable command processing system  
- **13+ Agents**: All using BaseAgent + message bus communication
- **Helper Classes**: NarrativeContinuityTracker, SimpleInlineCache, GameSaveManager

### Current Flow
```
User Input → CommandHandler → AgentOrchestrator → MessageBus → Individual Agents → Response
```

### Problems with Current Approach
1. **Dual Architecture**: Running both Haystack pipelines AND legacy message bus
2. **Complex Routing**: Command intent determination happens in multiple places
3. **Backward Compatibility Overhead**: Maintaining both systems creates complexity
4. **Inefficient Communication**: Message bus adds latency vs direct pipeline flow
5. **Duplicate State Management**: Both agents and pipelines managing game state

## Migration Strategy

### Phase 1: Core Haystack Orchestrator
**Goal**: Replace AgentOrchestrator with pure Haystack-based orchestration

#### 1.1 Create HaystackDMOrchestrator
```python
class HaystackDMOrchestrator:
    """Pure Haystack-based orchestration for D&D Assistant"""
    
    def __init__(self):
        self.pipeline_registry = HaystackPipelineRegistry()
        self.document_store = QdrantDocumentStore()
        self.retriever = QdrantHybridRetriever()
        self.llm = OpenAIGenerator()
        
    def process_command(self, command: str, context: Dict) -> Dict:
        """Process command through appropriate Haystack pipeline"""
        intent = self.classify_intent(command)
        pipeline = self.pipeline_registry.get_pipeline(intent)
        return pipeline.run({"query": command, "context": context})
```

#### 1.2 Intent Classification Pipeline
```python
@component
class IntentClassificationComponent:
    """Classify user commands into intents using LLM"""
    
    def run(self, query: str, context: Dict) -> Dict:
        intents = [
            "SKILL_CHECK", "SCENARIO_CHOICE", "RULE_QUERY", 
            "COMBAT_ACTION", "LORE_LOOKUP", "CHARACTER_MANAGEMENT",
            "INVENTORY_ACTION", "SPELL_CASTING", "SESSION_MANAGEMENT"
        ]
        # Use LLM to classify intent with context
```

### Phase 2: Command Processing Migration
**Goal**: Replace BaseCommandHandler with Haystack pipeline-based command processing

#### 2.1 Command Processing Pipeline
```python
class CommandProcessingPipeline(Pipeline):
    """Main command processing pipeline"""
    
    def __init__(self):
        self.add_component("intent_classifier", IntentClassificationComponent())
        self.add_component("context_enricher", ContextEnrichmentComponent())
        self.add_component("router", ConditionalRouter())
        
        # Add specialized pipelines for each intent
        self.add_component("skill_check_pipeline", SkillCheckPipeline())
        self.add_component("scenario_pipeline", ScenarioChoicePipeline())
        self.add_component("rule_query_pipeline", RuleQueryPipeline())
        # ... etc for all command types
```

#### 2.2 Context Management Component
```python
@component  
class ContextEnrichmentComponent:
    """Enrich commands with game state context"""
    
    def __init__(self, game_state_manager):
        self.game_state = game_state_manager
        
    def run(self, query: str, user_context: Dict) -> Dict:
        # Add current game state, character info, campaign context
        enriched_context = {
            **user_context,
            "current_characters": self.game_state.get_active_characters(),
            "campaign_info": self.game_state.get_campaign_context(),
            "session_state": self.game_state.get_session_state()
        }
        return {"query": query, "context": enriched_context}
```

### Phase 3: Agent-to-Component Migration
**Goal**: Convert all 13+ agents to pure Haystack components

#### 3.1 Core D&D Components
```python
# Replace individual agents with focused components

@component
class CharacterDataComponent:
    """Unified character data management"""
    
@component  
class CampaignContextComponent:
    """Campaign and world state management"""
    
@component
class RuleEnforcementComponent:
    """D&D rules validation and enforcement"""
    
@component
class DiceSystemComponent:
    """Dice rolling and probability calculations"""
    
@component
class CombatEngineComponent:
    """Combat mechanics and initiative tracking"""
    
@component
class NPCBehaviorComponent:
    """NPC dialogue and behavior generation"""
    
@component
class ScenarioGenerationComponent:
    """Dynamic scenario and encounter generation"""
```

#### 3.2 State Management Components
```python
@component
class GameStateComponent:
    """Centralized game state using event sourcing"""
    
    def __init__(self):
        self.event_store = EventStore()
        self.state_projector = StateProjector()
        
    def apply_event(self, event: GameEvent) -> Dict:
        self.event_store.append_event(event)
        current_state = self.state_projector.project_state(
            self.event_store.events
        )
        return {"updated_state": current_state}
```

### Phase 4: Pipeline Architecture
**Goal**: Create comprehensive pipeline system for all D&D operations

#### 4.1 Specialized Pipelines

##### Skill Check Pipeline
```python
class SkillCheckPipeline(Pipeline):
    def __init__(self):
        self.add_component("rule_validator", RuleEnforcementComponent())
        self.add_component("character_data", CharacterDataComponent())  
        self.add_component("dice_roller", DiceSystemComponent())
        self.add_component("result_calculator", SkillCheckCalculatorComponent())
        self.add_component("state_updater", GameStateComponent())
        self.add_component("narrative_generator", NarrativeGeneratorComponent())
```

##### Combat Action Pipeline
```python
class CombatActionPipeline(Pipeline):
    def __init__(self):
        self.add_component("action_validator", CombatRuleValidatorComponent())
        self.add_component("initiative_tracker", InitiativeTrackerComponent())
        self.add_component("damage_calculator", DamageCalculatorComponent())
        self.add_component("status_effects", StatusEffectComponent())
        self.add_component("combat_state", CombatStateComponent())
```

##### Lore Query Pipeline
```python
class LoreQueryPipeline(Pipeline):
    def __init__(self):
        self.add_component("retriever", QdrantHybridRetriever())
        self.add_component("context_filter", CampaignContextComponent())
        self.add_component("llm_generator", OpenAIGenerator())
        self.add_component("response_formatter", LoreResponseFormatterComponent())
```

#### 4.2 Pipeline Routing
```python
class MasterRoutingPipeline(Pipeline):
    """Master pipeline that routes to specialized pipelines"""
    
    def __init__(self):
        self.add_component("intent_classifier", IntentClassificationComponent())
        self.add_component("context_enricher", ContextEnrichmentComponent())
        
        self.add_component("router", ConditionalRouter(routes=[
            {
                "condition": "{{intent == 'SKILL_CHECK'}}",
                "output": "{{skill_check_result}}",
                "output_name": "skill_check_pipeline",
                "output_type": Dict[str, Any]
            },
            {
                "condition": "{{intent == 'COMBAT_ACTION'}}",
                "output": "{{combat_result}}",
                "output_name": "combat_pipeline", 
                "output_type": Dict[str, Any]
            },
            # ... routes for all intents
        ]))
        
        self.add_component("skill_check_pipeline", SkillCheckPipeline())
        self.add_component("combat_pipeline", CombatActionPipeline())
        # ... all specialized pipelines
```

### Phase 5: ModularDMAssistant Refactor
**Goal**: Simplify main class to use pure Haystack orchestration

#### 5.1 New ModularDMAssistant
```python
class ModularDMAssistant:
    """Haystack-native D&D Assistant"""
    
    def __init__(self, 
                 collection_name: str = "dnd_documents",
                 campaigns_dir: str = "resources/current_campaign",
                 verbose: bool = False):
        
        # Initialize Haystack document store
        self.document_store = QdrantDocumentStore(
            host="localhost",
            port=6333,
            index=collection_name
        )
        
        # Initialize master orchestrator
        self.orchestrator = HaystackDMOrchestrator(
            document_store=self.document_store,
            campaigns_dir=campaigns_dir
        )
        
        # Initialize master pipeline
        self.master_pipeline = MasterRoutingPipeline()
        
        # Game state management (event sourcing)
        self.game_state = GameStateManager()
        
        # Helper managers (simplified)
        self.cache_manager = HaystackCacheManager()
        self.save_manager = GameSaveManager()
        
    def process_dm_input(self, instruction: str) -> str:
        """Process DM instruction through Haystack pipelines"""
        
        # Get current game context
        context = {
            "game_state": self.game_state.get_current_state(),
            "timestamp": time.time(),
            "session_id": self.game_state.get_session_id()
        }
        
        # Run through master pipeline
        result = self.master_pipeline.run({
            "query": instruction,
            "context": context
        })
        
        # Update game state if needed
        if "updated_state" in result:
            self.game_state.apply_state_update(result["updated_state"])
        
        # Format response
        return self._format_response(result)
```

### Phase 6: Data Migration
**Goal**: Migrate existing data structures to Haystack-compatible formats

#### 6.1 Document Store Migration
```python
class DataMigrationUtility:
    """Migrate existing data to Haystack document store"""
    
    def migrate_campaign_data(self, campaigns_dir: str):
        """Migrate campaign files to document store"""
        
    def migrate_character_data(self, characters_dir: str):
        """Migrate character sheets to document store"""
        
    def migrate_rule_data(self, rules_dir: str):
        """Migrate D&D rules to searchable documents"""
```

#### 6.2 State Migration
```python
class StateMigrationUtility:
    """Migrate existing game state to event sourcing"""
    
    def migrate_game_state(self, old_state: Dict) -> List[GameEvent]:
        """Convert old state format to event stream"""
```

## Implementation Steps

### Step 1: Core Infrastructure (Week 1)
1. Create `HaystackDMOrchestrator` class
2. Implement `IntentClassificationComponent`
3. Create `MasterRoutingPipeline` structure
4. Set up `GameStateManager` with event sourcing

### Step 2: Component Migration (Week 2-3)
1. Convert top 5 agents to Haystack components:
   - Character management → `CharacterDataComponent`
   - Rule enforcement → `RuleEnforcementComponent`  
   - Dice system → `DiceSystemComponent`
   - Game engine → `GameStateComponent`
   - Scenario generation → `ScenarioGenerationComponent`

2. Create specialized pipelines:
   - `SkillCheckPipeline`
   - `CombatActionPipeline` 
   - `LoreQueryPipeline`

### Step 3: Pipeline Integration (Week 4)
1. Implement complete routing system
2. Test end-to-end pipeline flow
3. Add error handling and fallbacks
4. Performance optimization

### Step 4: UI Integration (Week 5)
1. Update `ModularDMAssistant` to use pure Haystack
2. Remove all message bus dependencies
3. Update command processing flow
4. Test interactive session

### Step 5: Data Migration & Testing (Week 6)
1. Migrate existing campaign/character data
2. Convert existing game saves
3. Comprehensive testing of all features
4. Performance benchmarking

## Expected Benefits

### Performance Improvements
- **50% reduction** in command processing latency
- **Eliminate** message bus overhead
- **Direct pipeline flow** instead of multi-hop agent communication

### Code Simplification  
- **Remove 2000+ lines** of agent framework code
- **Eliminate** backward compatibility layers
- **Single source of truth** for orchestration logic

### Enhanced Capabilities
- **Better error handling** through Haystack pipeline error management
- **Improved observability** with Haystack pipeline tracing
- **Enhanced caching** through Haystack's built-in caching mechanisms
- **Better scalability** with Haystack's component composition model

### Maintainability
- **Single framework** instead of hybrid approach
- **Standard Haystack patterns** for easier onboarding
- **Component reusability** across different pipelines
- **Better testing** with Haystack's component testing utilities

## Risk Mitigation

### Technical Risks
1. **Data Loss**: Complete backup and migration testing
2. **Performance Regression**: Benchmark existing vs new system
3. **Feature Parity**: Comprehensive feature mapping and testing

### Migration Risks  
1. **Gradual Migration**: Implement feature flags for rollback
2. **Parallel Systems**: Run both systems temporarily for validation
3. **User Impact**: Maintain save game compatibility during transition

## Success Metrics

### Performance Metrics
- Command processing time < 500ms (vs current ~1s)
- Memory usage reduction > 30%
- Pipeline throughput > 100 commands/minute

### Quality Metrics
- 100% feature parity with current system
- Zero data loss during migration
- <5% user workflow disruption

### Code Quality Metrics
- Lines of code reduction > 40%
- Cyclomatic complexity reduction > 50%
- Test coverage > 90% for all pipelines

This migration plan provides a comprehensive roadmap to transform the D&D Assistant from a hybrid agent/Haystack system to a pure Haystack-native architecture, eliminating complexity while enhancing performance and maintainability.