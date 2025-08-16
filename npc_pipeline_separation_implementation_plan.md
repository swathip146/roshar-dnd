# NPC Pipeline Separation Implementation Plan

## Executive Summary

This plan details the refactoring of NPC-specific functionality to eliminate RAG component duplication in the `NPCControllerAgent`. Instead of creating independent RAG pipelines, the NPC Controller will use the existing `HaystackPipelineAgent` through the agent orchestrator framework, maintaining NPC-specific capabilities while ensuring proper separation of concerns.

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
- **CRITICAL**: Duplicates RAG components (embedders, retrievers, rankers) from HaystackPipelineAgent
- Creates separate document store connections instead of using agent messaging
- Uses non-existent "query_npc" handler in HaystackPipelineAgent
- Direct agent coupling instead of proper orchestrator communication
- Inefficient resource usage with duplicate pipeline components

## Implementation Plan

### Phase 1: Remove RAG Duplication (Priority: High)

#### 1.1 Remove Duplicate RAG Components from NPCControllerAgent
**Components to Remove:**
```python
# REMOVE: Direct Haystack imports that duplicate functionality
from haystack import Pipeline
from haystack.components.embedders import SentenceTransformersTextEmbedder
from haystack.components.rankers import SentenceTransformersSimilarityRanker

# REMOVE: _setup_npc_pipeline() RAG components (lines 134-189)
- SentenceTransformersTextEmbedder initialization
- QdrantEmbeddingRetriever setup
- SentenceTransformersSimilarityRanker setup
- Pipeline component connections for retrieval
- Direct document_store access

# REMOVE: Direct document store access (lines 144-152)
if self.haystack_agent and hasattr(self.haystack_agent, 'document_store'):
    # This bypasses the agent framework

# REMOVE: Pipeline retrieval execution (lines 555-573)
if "text_embedder" in self.npc_pipeline.get_component_names():
    # Direct pipeline component access
```

#### 1.2 Replace with Agent Framework Communication
**New Communication Pattern:**
```python
def _gather_npc_context_from_rag(self, npc_id: str, query_context: str) -> Dict[str, Any]:
    """Query RAG system via orchestrator instead of direct access"""
    npc_name = self.npc_states[npc_id].name
    rag_query = f"NPC {npc_name} background personality history {query_context}"
    
    # GOOD: Use agent framework messaging
    response = self.send_message("haystack_pipeline", "retrieve_documents", {
        "query": rag_query,
        "max_docs": 3
    })
    
    if response and response.get("success"):
        return self._process_rag_context(response.get("documents", []))
    return {}
```

#### 1.3 Fix Non-Existent Handler Usage
**Replace Broken Calls:**
```python
# REMOVE: Uses non-existent "query_npc" handler
response = self.haystack_agent.send_message_and_wait("haystack_pipeline", "query_npc", {
    "query": prompt,
    "npc_context": str(npc),
    "game_state": str(game_state)
})

# REPLACE: Use existing handlers
response = self.send_message("haystack_pipeline", "query_rag", {
    "query": behavioral_query
})
```

### Phase 2: Enhanced NPC Architecture (Priority: High)

#### 2.1 Direct LLM Integration
**New NPCControllerAgent Architecture:**
```
NPC Request → Context Gathering → [Optional RAG Query] → LLM Generation → Response Parsing → Action/Dialogue Output
```

**Simplified Initialization:**
```python
def __init__(self, verbose=False):
    super().__init__("npc_controller", "NPCController")
    # REMOVE: haystack_agent parameter - use orchestrator instead
    self.verbose = verbose
    
    # Direct LLM integration (KEEP)
    self.has_llm = CLAUDE_AVAILABLE
    self.chat_generator = None
    self.npc_pipeline = None  # Simplified - LLM only
    
    # NPC state management (KEEP)
    self.npc_states = {}  # Persistent NPC data
    self.dialogue_history = {}  # Conversation tracking
    
    # Initialize LLM and simplified pipeline
    self._setup_llm_integration()
    self._setup_npc_pipeline()  # Simplified version - NO RAG components
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

#### 3.2 RAG Integration Through Orchestrator
**Multi-Type Context Gathering:**
```python
def _gather_npc_context_from_rag(self, npc_id: str, query_context: str):
    """Query RAG system via orchestrator for NPC background information"""
    npc_name = self.npc_states[npc_id].name
    rag_query = f"NPC {npc_name} background personality history relationships {query_context}"
    
    # Route through orchestrator to HaystackPipelineAgent
    response = self.send_message("haystack_pipeline", "retrieve_documents", {
        "query": rag_query,
        "max_docs": 3
    })
    
    if response and response.get("success"):
        return self._process_rag_context(response.get("documents", []))
    return {}

def _get_behavioral_context_from_rag(self, npc_id: str, situation: str):
    """Get behavioral guidance via orchestrator"""
    npc_name = self.npc_states[npc_id].name
    rag_query = f"NPC behavior {npc_name} {situation} actions dialogue"
    
    # Use query_rag for LLM-processed behavioral guidance
    response = self.send_message("haystack_pipeline", "query_rag", {
        "query": rag_query
    })
    
    if response and response.get("success"):
        result = response.get("result", {})
        return {
            "behavioral_guidance": result.get("answer", ""),
            "sources": result.get("sources", [])
        }
    return {}

def _get_npc_rules_context(self, interaction_type: str, npc_context: str):
    """Get D&D rules context for NPC interactions"""
    rules_query = f"D&D rules {interaction_type} NPC {npc_context} social interaction"
    
    # Use query_rules for rules-specific guidance
    response = self.send_message("haystack_pipeline", "query_rules", {
        "query": rules_query
    })
    
    if response and response.get("success"):
        result = response.get("result", {})
        return {
            "rules_guidance": result.get("answer", ""),
            "rule_sources": result.get("sources", [])
        }
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

## Detailed Refactoring Steps

### Step 1: Remove Duplicate RAG Components (Priority: Critical)

#### 1.1 Clean Up Imports in `npc_controller.py`
```python
# REMOVE these duplicate imports:
from haystack import Pipeline
from haystack.components.embedders import SentenceTransformersTextEmbedder
from haystack.components.rankers import SentenceTransformersSimilarityRanker

# KEEP these NPC-specific imports:
from hwtgenielib.components.generators.chat import AppleGenAIChatGenerator
from hwtgenielib.dataclasses import ChatMessage
from haystack.components.builders import PromptBuilder  # For local prompt building only
```

#### 1.2 Simplify Constructor
```python
# CHANGE from:
def __init__(self, haystack_agent=None, verbose: bool = False):
    self.haystack_agent = haystack_agent

# TO:
def __init__(self, verbose: bool = False):
    # Remove haystack_agent parameter - use orchestrator messaging instead
```

#### 1.3 Replace `_setup_npc_pipeline()` Method
```python
# REPLACE entire method (lines 134-189) with simplified version:
def _setup_npc_pipeline(self):
    """Initialize simplified NPC pipeline with local LLM only"""
    if not self.has_llm:
        return
    
    try:
        # Create NPC-specific pipeline (NO RAG components)
        self.npc_pipeline = Pipeline()
        
        # Add ONLY NPC-specific prompt builder and LLM
        prompt_builder = self._create_npc_prompt_builder()
        string_to_chat = StringToChatMessages()
        
        self.npc_pipeline.add_component("prompt_builder", prompt_builder)
        self.npc_pipeline.add_component("string_to_chat", string_to_chat)  
        self.npc_pipeline.add_component("chat_generator", self.chat_generator)
        
        # Connect ONLY prompt and LLM components (NO retrieval)
        self.npc_pipeline.connect("prompt_builder.prompt", "string_to_chat.prompt")
        self.npc_pipeline.connect("string_to_chat.messages", "chat_generator.messages")
        
        if self.verbose:
            print("✅ NPC pipeline initialized with local LLM only")
            
    except Exception as e:
        if self.verbose:
            print(f"⚠️ Failed to initialize NPC pipeline: {e}")
        self.npc_pipeline = None
```

### Step 2: Replace Direct RAG Access with Agent Messaging

#### 2.1 Update `_gather_npc_context_from_rag()` Method
```python
# REPLACE lines 656-678 with:
def _gather_npc_context_from_rag(self, npc_id: str, query_context: str) -> Dict[str, Any]:
    """Query RAG system via orchestrator for NPC background information"""
    npc_name = self.npc_states[npc_id].name
    
    # Build focused query for NPC-specific information
    rag_query = f"NPC {npc_name} background personality history relationships {query_context}"
    
    # GOOD: Use agent framework messaging
    response = self.send_message("haystack_pipeline", "retrieve_documents", {
        "query": rag_query,
        "max_docs": 3
    })
    
    if response and response.get("success"):
        return self._process_rag_context(response.get("documents", []))
    return {}
```

#### 2.2 Add New RAG Query Methods
```python
# ADD these new methods after _gather_npc_context_from_rag():
def _get_behavioral_context_from_rag(self, npc_id: str, situation: str) -> Dict[str, Any]:
    """Get behavioral guidance via orchestrator"""
    npc_name = self.npc_states[npc_id].name
    rag_query = f"NPC behavior {npc_name} {situation} actions dialogue personality"
    
    response = self.send_message("haystack_pipeline", "query_rag", {
        "query": rag_query
    })
    
    if response and response.get("success"):
        result = response.get("result", {})
        return {
            "behavioral_guidance": result.get("answer", ""),
            "sources": result.get("sources", [])
        }
    return {}

def _get_npc_rules_context(self, interaction_type: str, npc_context: str) -> Dict[str, Any]:
    """Get D&D rules context for NPC interactions"""
    rules_query = f"D&D rules {interaction_type} NPC {npc_context} social interaction skills"
    
    response = self.send_message("haystack_pipeline", "query_rules", {
        "query": rules_query
    })
    
    if response and response.get("success"):
        result = response.get("result", {})
        return {
            "rules_guidance": result.get("answer", ""),
            "rule_sources": result.get("sources", [])
        }
    return {}
```

### Step 3: Fix Broken Handler References

#### 3.1 Replace Non-Existent `query_npc` Calls
```python
# FIND and REPLACE in _haystack_based_decision() (lines 867-868):
# REMOVE:
response = self.haystack_agent.send_message_and_wait("haystack_pipeline", "query_npc", {
    "query": prompt,
    "npc_context": str(npc),
    "game_state": str(game_state)
})

# REPLACE with:
response = self.send_message("haystack_pipeline", "query_rag", {
    "query": prompt
})
```

#### 3.2 Update Deprecated NPCController Class
```python
# FIND and REPLACE in lines 1008-1009:
# REMOVE:
response = self.haystack_agent.send_message_and_wait("haystack_pipeline", "query_npc", {
    "query": prompt,
    "npc_context": str(npc_obj),
    "game_state": str(game_state)
})

# REPLACE with:
response = self.send_message("haystack_pipeline", "query_rag", {
    "query": prompt
})
```

### Step 4: Enhanced Behavior Generation

#### 4.1 Update `_generate_npc_behavior()` Method
```python
# REPLACE method (lines 471-501) with enhanced version:
def _generate_npc_behavior(self, npc_id: str, context: str, game_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Generate NPC behavior using local LLM + orchestrator RAG"""
    if not self.npc_pipeline or not self.has_llm:
        return None
    
    try:
        # Step 1: Get RAG context if needed
        rag_context = {}
        behavioral_context = {}
        
        if self._needs_rag_context(context):
            rag_context = self._gather_npc_context_from_rag(npc_id, context)
        
        if self._needs_behavioral_guidance(context):
            behavioral_context = self._get_behavioral_context_from_rag(npc_id, context)
        
        # Step 2: Build enhanced prompt with contexts
        npc_state = self.npc_states[npc_id]
        
        # Step 3: Run local NPC pipeline (LLM only)
        result = self._run_simplified_npc_pipeline(
            query=context,
            npc_name=npc_state.name,
            personality=npc_state.personality,
            location=npc_state.location,
            current_state=f"HP: {npc_state.stats.get('hp', '?')}",
            dialogue_history=self.dialogue_history.get(npc_id, [])[-3:],
            game_state=str(game_state),
            rag_context=rag_context,
            behavioral_context=behavioral_context
        )
        
        if result and result.get("success"):
            return self._parse_npc_response(result.get("response", ""))
        
    except Exception as e:
        if self.verbose:
            print(f"⚠️ NPC behavior generation failed: {e}")
    
    return None

# ADD helper methods:
def _needs_rag_context(self, context: str) -> bool:
    """Determine if RAG context retrieval is needed"""
    rag_triggers = ["talk", "conversation", "history", "relationship", "background"]
    return any(trigger in context.lower() for trigger in rag_triggers)

def _needs_behavioral_guidance(self, context: str) -> bool:
    """Determine if behavioral guidance from RAG is needed"""
    behavior_triggers = ["decision", "choose", "react", "respond", "behavior"]
    return any(trigger in context.lower() for trigger in behavior_triggers)
```

#### 4.2 Replace `_run_npc_pipeline()` Method
```python
# REPLACE method (lines 535-573) with simplified version:
def _run_simplified_npc_pipeline(self, query: str, npc_name: str, personality: Dict, 
                                location: str, current_state: str, dialogue_history: List, 
                                game_state: str, rag_context: Dict = None, 
                                behavioral_context: Dict = None) -> Dict[str, Any]:
    """Execute simplified NPC pipeline for behavior/dialogue generation"""
    if not self.npc_pipeline:
        return {"success": False, "error": "NPC pipeline not available"}
    
    try:
        # Prepare pipeline inputs (NO retrieval components)
        pipeline_inputs = {
            "prompt_builder": {
                "query": query,
                "npc_name": npc_name,
                "personality": str(personality),
                "location": location,
                "current_state": current_state,
                "dialogue_history": dialogue_history,
                "game_state": game_state,
                "rag_context": str(rag_context) if rag_context else "",
                "behavioral_context": str(behavioral_context) if behavioral_context else ""
            }
        }
        
        # Run simplified pipeline (LLM only)
        result = self.npc_pipeline.run(pipeline_inputs)
        
        # Extract response
        if "chat_generator" in result and "replies" in result["chat_generator"]:
            response = result["chat_generator"]["replies"][0].text
            return {"success": True, "response": response}
        else:
            return {"success": False, "error": "No response generated"}
            
    except Exception as e:
        return {"success": False, "error": str(e)}
```

### Step 5: Update Prompt Template

#### 5.1 Enhance `_create_npc_prompt_builder()` Template
```python
# UPDATE template in lines 193-231 to include RAG contexts:
def _create_npc_prompt_builder(self) -> PromptBuilder:
    """Create NPC-specific prompt builder"""
    template = """You are an advanced NPC behavior and dialogue specialist. Generate authentic, contextual responses for D&D NPCs with distinct personalities.

{% if rag_context %}
Background Context from Knowledge Base:
{{ rag_context }}
---
{% endif %}

{% if behavioral_context %}
Behavioral Guidance:
{{ behavioral_context }}
---
{% endif %}

NPC Profile:
Name: {{ npc_name }}
Personality: {{ personality }}
Location: {{ location }}
Current State: {{ current_state }}

{% if dialogue_history %}
Recent Conversation:
{% for exchange in dialogue_history %}
  {{ exchange.speaker }}: {{ exchange.content }}
{% endfor %}
{% endif %}

Situation: {{ query }}
{% if game_state %}Game Context: {{ game_state }}{% endif %}

Generate an appropriate response as this NPC. Include:
1. Dialogue (what the NPC says)
2. Action (what the NPC does)
3. Mood (current emotional state)
4. Memory (what to remember about this interaction)

Respond in JSON format:
{
  "dialogue": "NPC's spoken words",
  "action": "NPC's physical action or behavior",
  "mood": "emotional state",
  "memory": "key information to remember"
}"""
    return PromptBuilder(template=template)
```

## Migration Checklist

### Pre-Migration Verification
- [ ] Backup current `npc_controller.py`
- [ ] Test current NPC functionality works
- [ ] Verify HaystackPipelineAgent handlers exist (`retrieve_documents`, `query_rag`, `query_rules`)

### Migration Steps (Execute in Order)
- [ ] **Step 1:** Remove duplicate RAG imports and components
- [ ] **Step 2:** Replace direct RAG access with agent messaging  
- [ ] **Step 3:** Fix broken handler references
- [ ] **Step 4:** Implement enhanced behavior generation
- [ ] **Step 5:** Update prompt template with context support

### Post-Migration Testing
- [ ] Test NPC dialogue generation
- [ ] Test NPC behavior generation
- [ ] Test RAG context retrieval through orchestrator
- [ ] Verify no duplicate components exist
- [ ] Performance testing (should be faster)

This comprehensive refactoring plan eliminates RAG duplication while maintaining enhanced NPC capabilities through proper agent orchestration.