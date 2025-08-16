# NPC Pipeline Separation Implementation Plan

## Executive Summary

This plan details the separation of NPC-specific functionality from the `HaystackPipelineAgent` into the `NPCControllerAgent`, creating a dedicated and enhanced NPC management system that can independently generate NPC behavior, create appropriate dialogues, manage NPC stats, and leverage RAG data retrieval when needed.

## Current State Analysis

### HaystackPipelineAgent NPC Integration
**Current NPC functionality embedded in HaystackPipelineAgent:**
- `_create_npc_prompt_builder()` (lines 160-174) - NPC-specific prompt templates
- `npc_pipeline` initialization in `_setup_specialized_pipelines()` (lines 262-276)
- `_handle_query_npc()` method (lines 334-349) - NPC query handler
- `_run_npc_pipeline()` method (lines 468-484) - NPC pipeline execution

**Current Pipeline Architecture:**
```
Query → Text Embedder → Retriever → Ranker → NPC Prompt Builder → LLM → Response
```

### NPCControllerAgent Current State
**Existing functionality:**
- Basic decision-making framework (`_make_npc_decision()`)
- Rule-based behavior patterns (`_rule_based_decision()`)
- Haystack integration attempt (`_haystack_based_decision()`)
- Simple NPC action generation

**Current Limitations:**
- No direct LLM integration for creative dialogue
- Limited to basic movement/engagement actions
- No stat tracking or persistent NPC state
- No dialogue generation capabilities
- Relies entirely on HaystackPipelineAgent for advanced behavior

## Implementation Plan

### Phase 1: NPC Pipeline Migration (Priority: High)

#### 1.1 Move Core NPC Pipeline Components
**Target: NPCControllerAgent Enhancement**

**New Methods to Add:**
```python
def _setup_npc_pipeline(self):
    """Initialize dedicated NPC pipeline with LLM integration"""
    
def _create_npc_prompt_builder(self):
    """Create NPC-specific prompt builder (moved from HaystackPipelineAgent)"""
    
def _run_npc_pipeline(self, query: str, npc_context: dict, game_state: dict):
    """Execute NPC pipeline for behavior generation"""
    
def _handle_generate_npc_behavior(self, message: AgentMessage):
    """New handler for NPC behavior generation requests"""
```

**Dependencies to Add:**
```python
# Direct LLM integration (similar to ScenarioGeneratorAgent)
from hwtgenielib.components.generators.chat import AppleGenAIChatGenerator
from hwtgenielib.dataclasses import ChatMessage

# Haystack components for RAG integration
from haystack.components.embedders import SentenceTransformersTextEmbedder
from haystack.components.builders import PromptBuilder
```

#### 1.2 Remove NPC Components from HaystackPipelineAgent
**Components to Remove:**
- `_create_npc_prompt_builder()` method
- `npc_pipeline` initialization
- `_handle_query_npc()` method  
- `_run_npc_pipeline()` method
- NPC pipeline setup in `_setup_specialized_pipelines()`

**Handler Registration Update:**
```python
# Remove from HaystackPipelineAgent._setup_handlers():
# self.register_handler("query_npc", self._handle_query_npc)
```

### Phase 2: Enhanced NPC Architecture (Priority: High)

#### 2.1 Direct LLM Integration
**New NPCControllerAgent Architecture:**
```
NPC Request → Context Gathering → [Optional RAG Query] → LLM Generation → Response Parsing → Action/Dialogue Output
```

**Enhanced Initialization:**
```python
def __init__(self, haystack_agent=None, verbose=False):
    super().__init__("npc_controller", "NPCController")
    self.haystack_agent = haystack_agent
    self.verbose = verbose
    
    # Direct LLM integration
    self.has_llm = CLAUDE_AVAILABLE
    self.chat_generator = None
    
    # NPC state management
    self.npc_states = {}  # Persistent NPC data
    self.dialogue_history = {}  # Conversation tracking
    
    # Initialize LLM and pipeline
    self._setup_llm_integration()
    self._setup_npc_pipeline()
```

#### 2.2 NPC State Management System
**New NPC Data Structure:**
```python
class NPCState:
    def __init__(self, npc_id: str, name: str):
        self.npc_id = npc_id
        self.name = name
        self.stats = {}  # HP, AC, abilities, etc.
        self.status_effects = []  # Conditions, buffs, debuffs
        self.personality = {}  # Traits, motivations, goals
        self.relationships = {}  # Player/NPC relationships
        self.dialogue_state = {}  # Current conversation context
        self.memory = []  # Important events/interactions
        self.location = ""
        self.current_action = None
        self.last_updated = time.time()
```

#### 2.3 Message Handlers Enhancement
**New Handler Methods:**
```python
def _handle_generate_npc_behavior(self, message: AgentMessage):
    """Generate NPC behavior with context awareness"""
    
def _handle_generate_npc_dialogue(self, message: AgentMessage):
    """Generate contextual NPC dialogue"""
    
def _handle_update_npc_stats(self, message: AgentMessage):
    """Update NPC stats and status effects"""
    
def _handle_get_npc_state(self, message: AgentMessage):
    """Retrieve current NPC state information"""
    
def _handle_npc_social_interaction(self, message: AgentMessage):
    """Handle complex social interactions with NPCs"""
```

### Phase 3: Advanced NPC Capabilities (Priority: Medium)

#### 3.1 Dialogue Generation System
**Dialogue Architecture:**
```python
def _generate_npc_dialogue(self, npc_id: str, context: dict, player_input: str = None):
    """Generate contextually appropriate NPC dialogue"""
    # 1. Gather NPC personality and current state
    # 2. Query RAG for relevant background information
    # 3. Consider dialogue history and relationships
    # 4. Generate response using LLM with persona prompt
    # 5. Update dialogue state and memory
```

**Dialogue Context Building:**
```python
def _build_dialogue_context(self, npc_id: str, situation: str):
    """Build comprehensive context for dialogue generation"""
    context = {
        'npc_personality': self.npc_states[npc_id].personality,
        'current_location': self.npc_states[npc_id].location,
        'relationship_with_players': self.npc_states[npc_id].relationships,
        'recent_events': self.npc_states[npc_id].memory[-5:],
        'current_situation': situation,
        'dialogue_history': self.dialogue_history.get(npc_id, [])
    }
    return context
```

#### 3.2 RAG-Enhanced Context Retrieval
**Intelligent Context Gathering:**
```python
def _gather_npc_context_from_rag(self, npc_id: str, query_context: str):
    """Query RAG system for relevant NPC background information"""
    if not self.haystack_agent:
        return {}
    
    # Build focused query for NPC-specific information
    rag_query = f"NPC {self.npc_states[npc_id].name} background, personality, history, relationships context: {query_context}"
    
    response = self.send_message("haystack_pipeline", "retrieve_documents", {
        "query": rag_query,
        "max_docs": 3
    })
    
    if response and response.get("success"):
        return self._process_rag_context(response.get("documents", []))
    return {}
```

#### 3.3 Stat Management and Combat Integration
**NPC Stat Updates:**
```python
def _update_npc_stats(self, npc_id: str, stat_updates: dict):
    """Update NPC statistics and handle status effects"""
    if npc_id not in self.npc_states:
        return False
    
    npc = self.npc_states[npc_id]
    
    # Update basic stats
    for stat, value in stat_updates.items():
        if stat in ['hp', 'max_hp', 'ac', 'initiative']:
            npc.stats[stat] = value
        elif stat == 'conditions':
            npc.status_effects = value
        elif stat == 'location':
            npc.location = value
    
    # Handle HP changes and unconscious/death conditions
    if 'hp' in stat_updates:
        self._handle_hp_change(npc_id, stat_updates['hp'])
    
    npc.last_updated = time.time()
    return True

def _handle_hp_change(self, npc_id: str, new_hp: int):
    """Handle NPC HP changes and status effects"""
    npc = self.npc_states[npc_id]
    old_hp = npc.stats.get('hp', 0)
    
    # Add unconscious condition if HP drops to 0
    if new_hp <= 0 and old_hp > 0:
        npc.status_effects.append('unconscious')
        npc.memory.append(f"Became unconscious at {time.time()}")
    elif new_hp > 0 and 'unconscious' in npc.status_effects:
        npc.status_effects.remove('unconscious')
        npc.memory.append(f"Regained consciousness at {time.time()}")
```

### Phase 4: Command Routing Updates (Priority: High)

#### 4.1 Update modular_dm_assistant.py
**Command Mapping Changes:**
```python
# Current NPC-related routing (to be updated):
# Lines 540-545: NPC agent initialization
# Command routing for NPC interactions

# New command mappings to add:
COMMAND_MAP.update({
    'talk to npc': ('npc_controller', 'generate_npc_dialogue'),
    'npc behavior': ('npc_controller', 'generate_npc_behavior'),
    'npc status': ('npc_controller', 'get_npc_state'),
    'update npc': ('npc_controller', 'update_npc_stats'),
    'npc interaction': ('npc_controller', 'npc_social_interaction'),
})
```

**Handler Method Updates:**
```python
def _handle_npc_dialogue(self, instruction: str, params: dict) -> str:
    """Handle NPC dialogue generation requests"""
    npc_name = params.get('param_1', '').strip()
    player_input = params.get('param_2', '').strip()
    
    if not npc_name:
        return "❌ Please specify NPC name. Usage: talk to npc [name] [optional: what to say]"
    
    response = self._send_message_and_wait("npc_controller", "generate_npc_dialogue", {
        "npc_name": npc_name,
        "player_input": player_input,
        "context": "dialogue"
    })
    
    if response and response.get("success"):
        return f"💬 **{npc_name}:** {response['dialogue']}\n\n📊 **Mood:** {response.get('mood', 'neutral')}"
    else:
        return f"❌ Could not generate dialogue for {npc_name}"

def _handle_npc_behavior_generation(self, instruction: str, params: dict) -> str:
    """Handle NPC behavior generation requests"""
    response = self._send_message_and_wait("npc_controller", "generate_npc_behavior", {
        "context": instruction,
        "game_state": self._get_current_game_state()
    })
    
    if response and response.get("success"):
        return f"🎭 **NPC BEHAVIOR:**\n{response['behavior_description']}\n\n📋 **Actions:** {response.get('actions', 'No specific actions')}"
    else:
        return "❌ Failed to generate NPC behavior"
```

#### 4.2 Integration Testing Updates
**New Test Scenarios:**
```python
# Test NPC pipeline separation
def test_npc_pipeline_separation():
    # Verify HaystackPipelineAgent no longer handles NPC queries
    # Verify NPCControllerAgent handles all NPC functionality
    # Test RAG integration for NPC context retrieval
    
# Test enhanced NPC capabilities
def test_enhanced_npc_capabilities():
    # Test dialogue generation
    # Test stat management
    # Test behavior generation with context
```

### Phase 5: Migration Strategy (Priority: High)

#### 5.1 Migration Steps
1. **Backup Current System**
   - Create backup branch: `backup-before-npc-separation`
   - Document current NPC command flows

2. **Phase 1 Implementation**
   - Enhance NPCControllerAgent with LLM integration
   - Add new message handlers
   - Implement NPC state management

3. **Phase 2 Implementation**
   - Remove NPC components from HaystackPipelineAgent
   - Update handler registrations
   - Test basic NPC functionality

4. **Phase 3 Implementation**
   - Update modular_dm_assistant.py command routing
   - Add new command mappings
   - Implement new handler methods

5. **Phase 4 Implementation**
   - Add advanced features (dialogue, stat management)
   - Integrate with combat system
   - Add comprehensive testing

#### 5.2 Compatibility Considerations
**Backward Compatibility:**
- Maintain existing NPC decision-making API
- Ensure existing game saves continue to work
- Provide fallback mechanisms for missing data

**Error Handling:**
- Graceful degradation when LLM unavailable
- Fallback to rule-based behavior when needed
- Comprehensive error logging and recovery

### Architecture Benefits

#### Performance Improvements
- **Specialized Processing:** Dedicated NPC pipeline optimized for character behavior
- **Reduced Load:** Removes NPC processing overhead from RAG pipeline
- **Parallel Processing:** NPCs can be processed independently of other RAG queries

#### Enhanced Capabilities
- **Rich Dialogue:** Context-aware dialogue generation with personality consistency
- **Stat Management:** Real-time NPC stat tracking and status effect handling
- **Relationship Tracking:** Persistent memory of player-NPC interactions
- **Combat Integration:** Seamless integration with combat system for NPC actions

#### Maintainability
- **Clear Separation:** Distinct responsibilities between RAG and NPC systems
- **Modular Design:** Easy to extend NPC capabilities independently
- **Better Testing:** Isolated testing of NPC functionality

## Implementation Timeline

### Week 1: Core Migration
- [ ] Phase 1.1: Move NPC pipeline components
- [ ] Phase 1.2: Remove components from HaystackPipelineAgent
- [ ] Basic functionality testing

### Week 2: Enhanced Architecture
- [ ] Phase 2.1: Direct LLM integration
- [ ] Phase 2.2: NPC state management system
- [ ] Phase 2.3: Message handlers enhancement

### Week 3: Advanced Features
- [ ] Phase 3.1: Dialogue generation system
- [ ] Phase 3.2: RAG-enhanced context retrieval
- [ ] Phase 3.3: Stat management and combat integration

### Week 4: Integration and Testing
- [ ] Phase 4.1: Update modular_dm_assistant.py
- [ ] Phase 4.2: Integration testing updates
- [ ] Phase 5: Migration and compatibility testing

## Success Metrics

### Technical Metrics
- [ ] NPC queries no longer processed by HaystackPipelineAgent
- [ ] All existing NPC functionality preserved
- [ ] New dialogue generation capabilities working
- [ ] Stat management system operational
- [ ] Integration tests passing

### User Experience Metrics
- [ ] Faster NPC response times
- [ ] More engaging NPC interactions
- [ ] Consistent NPC personalities
- [ ] Seamless combat integration
- [ ] Improved error handling

## Risk Mitigation

### Technical Risks
- **LLM Integration Issues:** Implement robust fallback to rule-based behavior
- **State Management Complexity:** Use proven patterns from existing agents
- **Performance Degradation:** Monitor and optimize pipeline performance

### Compatibility Risks
- **Breaking Changes:** Maintain existing APIs during transition
- **Save Game Issues:** Test thoroughly with existing save files
- **Command Routing:** Ensure all existing commands continue to work

This implementation plan provides a comprehensive roadmap for separating NPC functionality into a dedicated, enhanced system while maintaining compatibility and improving capabilities.