# Stage 2: RAG Integration and Simple Orchestrator

**Progressive D&D Implementation - Weeks 5-8**

## Overview

Stage 2 enhances the basic D&D game from Stage 1 with Haystack RAG (Retrieval Augmented Generation) capabilities and introduces a simple orchestrator pattern with extension hooks for future stages. This follows the "start simple and expand" philosophy while maintaining full backward compatibility.

## Key Components Added

### 1. RAG Document Store (`storage/simple_document_store.py`)

**Purpose**: Haystack-based document storage and retrieval system using Qdrant vector database

**Key Features**:
- QdrantDocumentStore for vector embeddings
- SentenceTransformersTextEmbedder for document encoding  
- Retrieval pipeline for semantic content search
- Document loading and indexing capabilities

**Usage**:
```python
from storage.simple_document_store import SimpleDocumentStore

doc_store = SimpleDocumentStore()
documents = [{"content": "dungeon content...", "meta": {"type": "dungeon"}}]
doc_store.load_documents(documents)
results = doc_store.retrieve_documents("dragon cave", top_k=3)
```

### 2. RAG-Enhanced Scenario Generator (`simple_dnd/scenario_generator_rag.py`)

**Purpose**: Enhances scenario generation with document-based context using RAG

**Key Features**:
- Integrates SimpleDocumentStore with hwtgenielib generation
- Context-aware scenario creation using retrieved documents
- Maintains compatibility with original ScenarioGenerator interface
- Fallback to simple generation when no relevant documents found

**Usage**:
```python
from simple_dnd.scenario_generator_rag import RAGScenarioGenerator

generator = RAGScenarioGenerator(doc_store)
scenario = generator.generate_scenario(theme="dungeon", difficulty="medium")
```

### 3. Simple Orchestrator (`orchestrator/simple_orchestrator.py`)

**Purpose**: Basic request routing with extension hooks for Stage 3+ enhancements

**Key Features**:
- Request/Response standardization with `GameRequest`/`GameResponse`
- Hook system for pre/post processing (saga manager, decision logging)
- Handler registration system for extensibility
- Basic routing for scenario, dice, and state requests

**Extension Points**:
- **Pre-hooks**: For Stage 3 saga manager integration
- **Post-hooks**: For Stage 3 decision logging system  
- **Handler registration**: For new request types in future stages

**Usage**:
```python
from orchestrator.simple_orchestrator import SimpleOrchestrator, GameRequest

orchestrator = SimpleOrchestrator()
request = GameRequest("scenario", {"theme": "dungeon", "difficulty": "medium"})
response = orchestrator.process_request(request)
```

## Architecture

```
Stage 2 Architecture (Weeks 5-8)
├── Stage 1 Components (Unchanged)
│   ├── simple_dnd_game.py          # Still works independently
│   └── simple_dnd/                 # Original structured components
│       ├── config.py
│       ├── dice.py
│       ├── scenario_generator.py
│       └── game.py
├── RAG Integration (New)
│   ├── storage/
│   │   └── simple_document_store.py    # Haystack + Qdrant
│   └── simple_dnd/
│       └── scenario_generator_rag.py   # RAG-enhanced generation
└── Orchestration (New)
    └── orchestrator/
        └── simple_orchestrator.py      # Request routing + hooks
```

## Technology Stack

- **Haystack Framework**: RAG pipelines, document stores, embeddings
- **Qdrant**: Vector database for document embeddings
- **hwtgenielib**: AI generation with AWS Anthropic Claude Sonnet
- **SentenceTransformers**: Text embeddings for similarity search

## Demo and Testing

### Run Stage 2 Demo
```bash
python demo_stage2_rag.py
```

**Demo Features**:
- RAG document store initialization and retrieval
- RAG-enhanced scenario generation examples
- Orchestrator request routing with hooks
- Integration pattern demonstrations

### Backward Compatibility Testing
```bash
# Stage 1 still works unchanged
python simple_dnd_game.py
python demo_structured_game.py
```

## Extension Points for Stage 3+

### 1. Saga Manager Integration (Week 9-12)
```python
# Pre-hook for saga context injection
def saga_context_hook(request: GameRequest) -> GameRequest:
    # Add saga state and context to request
    return enhanced_request

orchestrator.add_pre_hook(saga_context_hook)
```

### 2. Decision Logging System (Week 9-12)  
```python
# Post-hook for decision tracking
def decision_logging_hook(response: GameResponse) -> GameResponse:
    # Log decisions for saga continuity
    return response

orchestrator.add_post_hook(decision_logging_hook)
```

### 3. Handler Registration (Future Stages)
```python
# Register new request types as capabilities expand
orchestrator.register_handler("combat", combat_handler)
orchestrator.register_handler("character_sheet", character_handler)
```

## Progressive Development Timeline

- ✅ **Week 5-6**: RAG document store and retrieval system
- ✅ **Week 7-8**: Simple orchestrator with extension hooks  
- 🚧 **Week 9-12**: Advanced saga manager integration (Stage 3)
- 📅 **Week 13-16**: Persistent campaign state (Stage 4)
- 📅 **Week 17-20**: Advanced AI orchestration (Stage 5)
- 📅 **Week 21-24**: Full feature integration (Stage 6)

## Key Design Principles

1. **Progressive Enhancement**: Each stage builds upon previous without breaking compatibility
2. **Extension Hooks**: Pre/post hooks enable future functionality without code changes
3. **Technology Integration**: Consistent use of Haystack + hwtgenielib throughout
4. **Simple First**: Basic implementations with clear upgrade paths

## Next Steps to Stage 3

Stage 3 will enhance the orchestrator with:
- Advanced saga manager with persistent narrative state
- Decision logging and continuity tracking  
- Enhanced RAG with campaign-specific document collections
- Character progression and party management

The hook system and handler registration patterns established in Stage 2 provide clean integration points for these enhancements.