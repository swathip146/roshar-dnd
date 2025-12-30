# NPC Pipeline Separation - Architectural Diagrams

## Current Architecture (Before Separation)

### Current NPC Processing Flow
```mermaid
graph TD
    A[User Input: NPC Query] --> B[ModularDMAssistant]
    B --> C[Command Router]
    C --> D[HaystackPipelineAgent]
    D --> E[_handle_query_npc]
    E --> F[_run_npc_pipeline]
    F --> G[Text Embedder]
    G --> H[Document Retriever]
    H --> I[Document Ranker]
    I --> J[NPC Prompt Builder]
    J --> K[Claude LLM]
    K --> L[NPC Response]
    L --> M[NPCControllerAgent._haystack_based_decision]
    M --> N[Simple Action Parser]
    N --> O[Basic Move/Engage Action]
    O --> P[Game State Update]
    
    style D fill:#ffcccc
    style E fill:#ffcccc
    style F fill:#ffcccc
    style J fill:#ffcccc
    style M fill:#ffffcc
```

### Current Agent Responsibilities
```mermaid
graph LR
    A[HaystackPipelineAgent] --> B[RAG Queries]
    A --> C[NPC Pipeline ❌]
    A --> D[Rules Pipeline]
    A --> E[Document Retrieval]
    
    F[NPCControllerAgent] --> G[Basic Decision Making]
    F --> H[Rule-based Behavior]
    F --> I[Simple Action Generation]
    
    C -.-> G
    
    style A fill:#ffcccc
    style C fill:#ff9999
    style F fill:#ffffcc
```

## Proposed Architecture (After Separation)

### Enhanced NPC Processing Flow
```mermaid
graph TD
    A[User Input: NPC Query] --> B[ModularDMAssistant]
    B --> C[Command Router]
    C --> D[NPCControllerAgent]
    D --> E[Message Handler Routing]
    
    E --> F[generate_npc_behavior]
    E --> G[generate_npc_dialogue]
    E --> H[update_npc_stats]
    E --> I[get_npc_state]
    
    F --> J[Context Gathering]
    G --> J
    J --> K{RAG Needed?}
    K -->|Yes| L[Query HaystackPipelineAgent]
    L --> M[retrieve_documents]
    M --> N[RAG Context]
    K -->|No| O[Local Context]
    N --> P[Context Compilation]
    O --> P
    
    P --> Q[NPC State Retrieval]
    Q --> R[Personality & Memory]
    R --> S[Direct LLM Generation]
    S --> T[Claude Sonnet 4]
    T --> U[Response Parsing]
    U --> V[Action/Dialogue Output]
    V --> W[State Management]
    W --> X[NPC Stats Update]
    X --> Y[Game State Integration]
    
    style D fill:#ccffcc
    style J fill:#ccffcc
    style P fill:#ccffcc
    style S fill:#ccffcc
    style W fill:#ccffcc
```

### Separated Agent Responsibilities
```mermaid
graph LR
    A[HaystackPipelineAgent] --> B[RAG Queries]
    A --> C[Rules Pipeline]
    A --> D[Document Retrieval]
    A --> E[General Knowledge]
    
    F[NPCControllerAgent] --> G[NPC Behavior Generation]
    F --> H[Dialogue Creation]
    F --> I[Stat Management]
    F --> J[Personality Tracking]
    F --> K[Combat Integration]
    F --> L[Memory & Relationships]
    
    F -.->|RAG Context Requests| A
    A -.->|Document Data| F
    
    style A fill:#ccffff
    style F fill:#ccffcc
```

## Data Flow Architecture

### NPC State Management System
```mermaid
graph TD
    A[NPC Request] --> B[NPCControllerAgent]
    B --> C[NPC State Manager]
    
    C --> D[Memory System]
    C --> E[Personality Database]
    C --> F[Stats Tracker]
    C --> G[Relationship Map]
    
    D --> H[Recent Events]
    D --> I[Important Interactions]
    
    E --> J[Traits & Motivations]
    E --> K[Speech Patterns]
    
    F --> L[HP/AC/Stats]
    F --> M[Status Effects]
    
    G --> N[Player Relationships]
    G --> O[NPC Relationships]
    
    H --> P[Context Builder]
    I --> P
    J --> P
    K --> P
    L --> P
    M --> P
    N --> P
    O --> P
    
    P --> Q[Enhanced Prompt]
    Q --> R[LLM Generation]
    R --> S[Response Parser]
    S --> T[Action Executor]
    T --> U[State Updater]
    U --> C
    
    style C fill:#ffeecc
    style P fill:#eeffcc
    style R fill:#ccefff
    style U fill:#ffccee
```

### RAG Integration Flow
```mermaid
sequenceDiagram
    participant UI as User Interface
    participant DM as ModularDMAssistant
    participant NPC as NPCControllerAgent
    participant RAG as HaystackPipelineAgent
    participant LLM as Claude LLM
    
    UI->>DM: "talk to npc Gandalf about magic"
    DM->>NPC: generate_npc_dialogue(npc="Gandalf", topic="magic")
    
    NPC->>NPC: Check NPC state & personality
    NPC->>NPC: Determine if RAG context needed
    
    alt RAG Context Required
        NPC->>RAG: retrieve_documents(query="Gandalf magic knowledge")
        RAG->>RAG: Embed query & retrieve relevant docs
        RAG->>NPC: Return context documents
    end
    
    NPC->>NPC: Build enhanced prompt with personality + context
    NPC->>LLM: Generate dialogue with persona
    LLM->>NPC: Return contextual dialogue
    
    NPC->>NPC: Parse response & update memory
    NPC->>NPC: Update relationship tracking
    NPC->>DM: Return formatted dialogue
    DM->>UI: Display NPC response with personality
```

## Component Migration Map

### Files to Modify

```mermaid
graph TD
    A[HaystackPipelineAgent] --> B[Remove NPC Components]
    B --> C[_create_npc_prompt_builder ❌]
    B --> D[npc_pipeline ❌]
    B --> E[_handle_query_npc ❌]
    B --> F[_run_npc_pipeline ❌]
    
    G[NPCControllerAgent] --> H[Add Enhanced Components]
    H --> I[Direct LLM Integration ✅]
    H --> J[NPC State Management ✅]
    H --> K[Dialogue Generation ✅]
    H --> L[RAG Context Retrieval ✅]
    H --> M[Stat Tracking ✅]
    
    N[ModularDMAssistant] --> O[Update Command Routing]
    O --> P[New NPC Commands ✅]
    O --> Q[Handler Methods ✅]
    O --> R[Integration Logic ✅]
    
    style B fill:#ffcccc
    style C fill:#ff9999
    style D fill:#ff9999
    style E fill:#ff9999
    style F fill:#ff9999
    style H fill:#ccffcc
    style I fill:#99ff99
    style J fill:#99ff99
    style K fill:#99ff99
    style L fill:#99ff99
    style M fill:#99ff99
    style O fill:#ccffff
    style P fill:#99ccff
    style Q fill:#99ccff
    style R fill:#99ccff
```

## Performance Comparison

### Before Separation (Current)
```mermaid
graph LR
    A[NPC Query] --> B[HaystackPipelineAgent]
    B --> C[Full RAG Pipeline]
    C --> D[Document Processing]
    D --> E[LLM Generation]
    E --> F[Basic Action Parse]
    F --> G[Simple Response]
    
    H[Performance Issues:]
    H --> I[Mixed responsibilities]
    H --> J[RAG overhead for simple queries]
    H --> K[Limited NPC capabilities]
    H --> L[No state persistence]
    
    style B fill:#ffcccc
    style C fill:#ffcccc
    style H fill:#ffffcc
```

### After Separation (Proposed)
```mermaid
graph LR
    A[NPC Query] --> B[NPCControllerAgent]
    B --> C[Smart Context Routing]
    C --> D{Complex Query?}
    D -->|Yes| E[RAG Integration]
    D -->|No| F[Direct LLM]
    E --> G[Enhanced Context]
    F --> G
    G --> H[Persona-based Generation]
    H --> I[Rich Response + State Update]
    
    J[Performance Benefits:]
    J --> K[Dedicated NPC processing]
    J --> L[Optional RAG usage]
    J --> M[Advanced capabilities]
    J --> N[Persistent state management]
    
    style B fill:#ccffcc
    style C fill:#ccffcc
    style J fill:#ccffee
```

## Integration Testing Strategy

### Test Scenarios Flow
```mermaid
graph TD
    A[Test Suite] --> B[Unit Tests]
    A --> C[Integration Tests]
    A --> D[Performance Tests]
    
    B --> E[NPC State Management]
    B --> F[Dialogue Generation]
    B --> G[Stat Updates]
    B --> H[RAG Integration]
    
    C --> I[End-to-End NPC Interactions]
    C --> J[Command Routing Verification]
    C --> K[Backward Compatibility]
    C --> L[Error Handling]
    
    D --> M[Response Time Comparison]
    D --> N[Memory Usage Analysis]
    D --> O[Concurrent NPC Processing]
    
    style A fill:#eeeeff
    style B fill:#ccffcc
    style C fill:#ffccff
    style D fill:#ffffcc
```

These architectural diagrams illustrate the comprehensive transformation from the current embedded NPC functionality to a dedicated, enhanced NPC management system that provides superior capabilities while maintaining clean separation of concerns.