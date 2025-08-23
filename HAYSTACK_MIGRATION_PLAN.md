# Haystack Framework Migration Plan

## Overview
This plan outlines the migration of the D&D Assistant agent framework to use Haystack components more extensively while preserving existing hwtgenielib integrations and the custom agent communication framework.

## Current State Analysis

### Agent Framework Architecture
- **agent_framework.py**: Core framework with BaseAgent, MessageBus, AgentOrchestrator
- **Agent Communication**: Message-based communication between agents
- **Haystack Integration**: Currently limited to `haystack_pipeline_agent.py`
- **LLM Integration**: Uses hwtgenielib's AppleGenAIChatGenerator (preserve this)

### Agent Categorization by Haystack Potential

#### High Priority - Agents with Direct RAG/NLP Needs
1. **npc_controller.py**
   - Current: Basic RAG via orchestrator messaging
   - Opportunity: Direct Haystack pipelines for NPC behavior generation
   - Components: PromptBuilder, Retriever, Ranker, Custom generators

2. **scenario_generator.py** 
   - Current: Basic RAG via orchestrator messaging
   - Opportunity: Enhanced creative generation with Haystack pipelines
   - Components: PromptBuilder, Retriever, Document processing

3. **rule_enforcement_agent.py**
   - Current: Basic rule checking, some RAG integration
   - Opportunity: Advanced rule validation with semantic search
   - Components: EmbeddingRetriever, SimilarityRanker, PromptBuilder

4. **direct_campaign_generator.py**
   - Current: Already has some Haystack components
   - Opportunity: Standardize and enhance existing integration
   - Components: Already uses QdrantDocumentStore, embedders

#### Medium Priority - Agents with Text Processing Needs
5. **campaign_management.py**
   - Current: File-based campaign loading
   - Opportunity: Enhanced campaign parsing and analysis
   - Components: TextFileToDocument, DocumentCleaner

6. **character_manager_agent.py**
   - Current: JSON-based character management
   - Opportunity: Natural language character queries and generation
   - Components: PromptBuilder for character advice

7. **spell_manager_agent.py**
   - Current: Dictionary-based spell database
   - Opportunity: Semantic spell search and recommendations
   - Components: EmbeddingRetriever, SimilarityRanker

#### Low Priority - Agents with Minimal NLP Needs
8. **combat_engine.py** - Primarily rule-based, minimal NLP needs
9. **dice_system.py** - Mathematical operations, minimal NLP needs
10. **experience_manager_agent.py** - Calculation-based, minimal NLP needs
11. **game_engine.py** - State management, minimal NLP needs
12. **inventory_manager_agent.py** - CRUD operations, minimal NLP needs
13. **session_manager_agent.py** - Time/session tracking, minimal NLP needs

## Migration Strategy

### Phase 1: Infrastructure & High-Impact Agents (Priority 1)

#### 1.1 Enhance haystack_pipeline_agent.py
- **Status**: ✅ Already completed
- **Components**: QdrantDocumentStore, SentenceTransformersTextEmbedder, QdrantEmbeddingRetriever
- **Integration**: AppleGenAIChatGenerator preserved

#### 1.2 Upgrade npc_controller.py
**Current Issues:**
```python
# Current: Basic orchestrator communication
response = self.send_message("haystack_pipeline", "retrieve_documents", {
    "query": rag_query,
    "max_docs": 3
})
```

**Proposed Solution:**
```python
# Add direct Haystack pipeline for NPC-specific tasks
class NPCBehaviorPipeline:
    def __init__(self, document_store, chat_generator):
        self.pipeline = Pipeline()
        self.pipeline.add_component("embedder", SentenceTransformersTextEmbedder())
        self.pipeline.add_component("retriever", QdrantEmbeddingRetriever(document_store))
        self.pipeline.add_component("ranker", SentenceTransformersSimilarityRanker())
        self.pipeline.add_component("prompt_builder", self._create_npc_prompt_builder())
        self.pipeline.add_component("llm", chat_generator)
        # Connect components...
```

**Benefits:**
- Direct pipeline control for NPC-specific behavior
- Reduced orchestrator message overhead
- Enhanced context handling for NPCs

#### 1.3 Upgrade scenario_generator.py
**Current Issues:**
```python
# Current: Limited creative generation, orchestrator dependency
try:
    rag_response = self.send_message("haystack_pipeline", "retrieve_documents", {
        "query": prompt,
        "max_docs": 3
    })
```

**Proposed Solution:**
```python
class ScenarioGenerationPipeline:
    def __init__(self, document_store, chat_generator):
        self.pipeline = Pipeline()
        self.pipeline.add_component("context_embedder", SentenceTransformersTextEmbedder())
        self.pipeline.add_component("context_retriever", QdrantEmbeddingRetriever(document_store))
        self.pipeline.add_component("scenario_prompt_builder", self._create_scenario_prompt_builder())
        self.pipeline.add_component("creative_generator", chat_generator)
        # Connect for creative scenario generation
```

**Benefits:**
- Enhanced creative scenario generation
- Better context integration from D&D knowledge base
- Improved narrative coherence

#### 1.4 Upgrade rule_enforcement_agent.py
**Current Issues:**
```python
# Current: Basic rule checking with minimal RAG
rule_info = self.check_rule(rule_query, category)
```

**Proposed Solution:**
```python
class RuleValidationPipeline:
    def __init__(self, document_store):
        self.pipeline = Pipeline()
        self.pipeline.add_component("rule_embedder", SentenceTransformersTextEmbedder())
        self.pipeline.add_component("rule_retriever", QdrantEmbeddingRetriever(document_store))
        self.pipeline.add_component("rule_ranker", SentenceTransformersSimilarityRanker())
        self.pipeline.add_component("rule_analyzer", self._create_rule_analysis_component())
```

**Benefits:**
- Semantic rule validation
- Context-aware rule interpretation
- Better rule conflict detection

### Phase 2: Document Processing & Knowledge Management

#### 2.1 Enhance campaign_management.py
**Proposed Components:**
- `TextFileToDocument` for campaign file processing
- `DocumentCleaner` for structured campaign data
- `DocumentSplitter` for large campaign texts

#### 2.2 Upgrade direct_campaign_generator.py
**Current State**: Already has Haystack components
**Improvements:**
- Standardize pipeline patterns
- Add better error handling
- Integrate with main document store

### Phase 3: Semantic Enhancement for Supporting Agents

#### 3.1 Upgrade spell_manager_agent.py
**Add Components:**
- Semantic spell search using embeddings
- Spell recommendation system
- Natural language spell queries

#### 3.2 Upgrade character_manager_agent.py
**Add Components:**
- Character concept generation
- Build optimization suggestions
- Natural language character queries

## Implementation Details

### Shared Infrastructure

#### Document Store Strategy
```python
# Centralized document store access
class DocumentStoreManager:
    def __init__(self, collection_name="dnd_documents"):
        self.document_store = QdrantDocumentStore(
            path="../qdrant_storage",
            index=collection_name,
            embedding_dim=384,
            recreate_index=False
        )
    
    def get_document_store(self):
        return self.document_store
```

#### Pipeline Factory Pattern
```python
class HaystackPipelineFactory:
    @staticmethod
    def create_rag_pipeline(document_store, chat_generator, prompt_template):
        pipeline = Pipeline()
        pipeline.add_component("embedder", SentenceTransformersTextEmbedder())
        pipeline.add_component("retriever", QdrantEmbeddingRetriever(document_store))
        pipeline.add_component("ranker", SentenceTransformersSimilarityRanker())
        pipeline.add_component("prompt_builder", PromptBuilder(template=prompt_template))
        pipeline.add_component("generator", chat_generator)
        # Connect components
        return pipeline
```

### Integration Patterns

#### Hybrid Architecture Pattern
```python
class HaystackEnhancedAgent(BaseAgent):
    def __init__(self, agent_id, agent_type):
        super().__init__(agent_id, agent_type)
        self.document_store_manager = DocumentStoreManager()
        self.pipelines = {}
        self._setup_haystack_pipelines()
    
    def _setup_haystack_pipelines(self):
        # Setup agent-specific Haystack pipelines
        pass
    
    def _fallback_to_orchestrator(self, action, data):
        # Fallback to orchestrator communication when needed
        return self.send_message("haystack_pipeline", action, data)
```

### Preservation of Existing Components

#### hwtgenielib Integration
- **AppleGenAIChatGenerator**: Maintain as primary LLM
- **ChatMessage**: Continue using for LLM communication
- **Existing prompt patterns**: Preserve successful templates

#### Agent Framework
- **BaseAgent**: No changes to core agent pattern
- **MessageBus**: Preserve agent communication
- **AgentOrchestrator**: Maintain for coordination

## Migration Phases & Timeline

### Phase 1: Core RAG Agents (Weeks 1-2)
- [x] haystack_pipeline_agent.py (Completed)
- [ ] npc_controller.py Haystack integration
- [ ] scenario_generator.py Haystack integration  
- [ ] rule_enforcement_agent.py Haystack integration

### Phase 2: Document Processing (Week 3)
- [ ] campaign_management.py document processing
- [ ] direct_campaign_generator.py standardization

### Phase 3: Semantic Enhancement (Week 4)
- [ ] spell_manager_agent.py semantic search
- [ ] character_manager_agent.py NLP features

### Phase 4: Testing & Optimization (Week 5)
- [ ] Integration testing
- [ ] Performance optimization
- [ ] Documentation updates

## Risk Mitigation

### Compatibility Risks
1. **Agent Communication**: Maintain existing message patterns
2. **hwtgenielib Dependencies**: Preserve all existing integrations
3. **Performance**: Monitor pipeline initialization overhead
4. **Error Handling**: Implement graceful fallbacks to orchestrator

### Migration Safety
1. **Feature Flags**: Enable/disable Haystack features per agent
2. **Gradual Rollout**: Agent-by-agent migration
3. **Rollback Plan**: Preserve original implementations during transition
4. **Testing**: Comprehensive integration tests

## Success Metrics

### Technical Metrics
1. **Response Quality**: Improved RAG relevance scores
2. **Performance**: Pipeline execution times < 2s
3. **Reliability**: 99%+ agent availability
4. **Integration**: Successful hwtgenielib preservation

### Functional Metrics
1. **NPC Behavior**: More contextual and dynamic responses
2. **Scenario Generation**: Enhanced creativity and D&D authenticity
3. **Rule Enforcement**: Better rule interpretation accuracy
4. **Overall UX**: Improved DM assistant capabilities

## Next Steps

1. **Immediate**: Begin Phase 1 implementation with npc_controller.py
2. **Setup**: Create shared DocumentStoreManager infrastructure
3. **Testing**: Establish integration test framework
4. **Documentation**: Update agent documentation with Haystack patterns

This migration plan provides a systematic approach to integrating Haystack components while preserving the successful elements of the existing architecture.