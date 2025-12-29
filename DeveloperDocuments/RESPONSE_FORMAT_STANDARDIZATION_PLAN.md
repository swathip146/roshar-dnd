# Response Format Standardization Plan

## Overview
Create a unified response format system that properly converts agent responses into standardized TypedDict formats and updates the orchestrator to use these consistently.

## Current State Analysis

### Issues Identified:
1. **RAG Agent Response Inconsistency**: Returns mixed formats that don't match `RAGBlock` TypedDict
2. **Scenario Agent Response Inconsistency**: Returns formats that partially match `Scenario` TypedDict but with extra fields
3. **GameResponseDTO Generic Structure**: Too generic with just `data: Dict[str, Any]`
4. **No Converter Functions**: Missing standardization layer between agent outputs and DTO formats
5. **Pipeline Response Inconsistency**: orchestrator returns different formats for different pipelines

## Plan Implementation

### Phase 1: Update GameResponseDTO Structure

**File**: `shared_contract.py`

```python
# Update GameResponseDTO to support unified response types
class GameResponseDTO(TypedDict, total=False):
    success: bool
    correlation_id: Optional[str]
    metadata: Optional[Dict[str, Any]]
    error: Optional[str]
    
    # Unified response data fields
    response_type: str  # "scenario", "rag_query", "npc_interaction"
    
    # Type-specific response data
    scenario: Optional[Scenario]           # For scenario responses
    rag_result: Optional[RAGBlock]        # For RAG responses  
    npc_response: Optional[Dict[str, Any]] # For NPC responses
```

### Phase 2: Extend TypedDict Definitions

**File**: `shared_contract.py`

```python
# Extend Scenario to match actual agent output
class Scenario(TypedDict, total=False):
    scene: str
    choices: List[Choice]
    effects: Dict[str, Any] 
    hooks: List[str]
    
    # Additional fields from agent output
    gm_notes: Optional[str]
    state_changes: Optional[Dict[str, Any]]
    difficulty_used: Optional[Dict[str, Any]]
    confidence: Optional[float]
    fallback: Optional[bool]

# Extend RAGBlock to match actual agent output  
class RAGBlock(TypedDict, total=False):
    needed: bool
    query: str
    filters: Dict[str, Any]
    docs: List[Dict[str, Any]]
    confidence: float
    category: str
    reasoning: str
    response: str
    rag_context: str
    
    # Additional fields from agent output
    original_query: Optional[str]
    context_summary: Optional[str]
    source: Optional[str]
    error: Optional[str]
```

### Phase 3: Create Response Converter Functions

**File**: `shared_contract.py`

```python
def convert_rag_response_to_ragblock(agent_response: Dict[str, Any]) -> RAGBlock:
    """Convert RAG agent response to standardized RAGBlock format"""
    return {
        "needed": True,  # If we're converting, RAG was needed
        "query": agent_response.get("query", ""),
        "filters": agent_response.get("filters", {}),
        "docs": agent_response.get("documents", []),
        "confidence": agent_response.get("confidence", 0.0),
        "category": agent_response.get("context_type", "general"),
        "reasoning": f"Retrieved {len(agent_response.get('documents', []))} documents",
        "response": agent_response.get("rag_context", ""),
        "rag_context": agent_response.get("rag_context", ""),
        "original_query": agent_response.get("original_query"),
        "context_summary": agent_response.get("context_summary"),
        "source": agent_response.get("source"),
        "error": agent_response.get("error")
    }

def convert_scenario_response_to_scenario(agent_response: Dict[str, Any]) -> Scenario:
    """Convert scenario agent response to standardized Scenario format"""
    return {
        "scene": agent_response.get("scene", ""),
        "choices": agent_response.get("choices", []),
        "effects": agent_response.get("effects", {}),
        "hooks": agent_response.get("hooks", []),
        "gm_notes": agent_response.get("gm_notes"),
        "state_changes": agent_response.get("state_changes"),
        "difficulty_used": agent_response.get("difficulty_used"),
        "confidence": agent_response.get("confidence"),
        "fallback": agent_response.get("fallback")
    }

def create_unified_game_response(
    response_type: str,
    scenario: Optional[Scenario] = None,
    rag_result: Optional[RAGBlock] = None,
    npc_response: Optional[Dict[str, Any]] = None,
    success: bool = True,
    correlation_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None
) -> GameResponseDTO:
    """Create unified GameResponseDTO with proper type-specific fields"""
    return {
        "success": success,
        "correlation_id": correlation_id,
        "metadata": metadata or {},
        "error": error,
        "response_type": response_type,
        "scenario": scenario,
        "rag_result": rag_result,
        "npc_response": npc_response
    }
```

### Phase 4: Update Agent Response Processing

**File**: `agents/rag_retriever_agent.py`

```python
# Update RAGFormatterComponent to return standardized format
@component
class RAGFormatterComponent:
    def run(self, messages: List[ChatMessage]) -> dict:
        # ... existing logic ...
        
        # Return in format that can be easily converted to RAGBlock
        return {"rag_formatted_response": {
            "response": response_text,
            "confidence": confidence,
            "query": extracted_query,
            "category": extracted_category,
            "docs": extracted_docs,
            "rag_context": response_text,
            "original_query": extracted_query,
            "context_summary": f"Retrieved {len(extracted_docs)} documents",
            "source": "rag_pipeline"
        }}
```

**File**: `agents/scenario_generator_agent.py`

```python
# Update ScenarioValidatorComponent to return standardized format
@component
class ScenarioValidatorComponent:
    def run(self, messages: List[ChatMessage]) -> Dict[str, Dict[str, Any]]:
        # ... existing logic ...
        
        # Ensure format matches Scenario TypedDict exactly
        validated_scenario = {
            "scene": scenario_data.get("scene", ""),
            "choices": scenario_data.get("choices", []),
            "effects": scenario_data.get("effects", {}),
            "hooks": scenario_data.get("hooks", []),
            "gm_notes": scenario_data.get("gm_notes"),
            "state_changes": scenario_data.get("state_changes"),
            "difficulty_used": scenario_data.get("difficulty_used"),
            "confidence": scenario_data.get("confidence", 0.8),
            "fallback": scenario_data.get("fallback", False)
        }
        
        return {"scenario_validated_response": validated_scenario}

# Update PromptBuilderComponent to accept RAGBlock TypedDict
@component
class PromptBuilderComponent:
    @component.output_types(scenario_prompt=str)
    def run(self, dto: Dict[str, Any], rag_block: Optional[RAGBlock] = None) -> Dict[str, str]:
        """
        Build comprehensive scenario generation prompt with RAGBlock TypedDict input.
        
        Args:
            dto: Streamlined DTO with engine references
            rag_block: Optional RAGBlock TypedDict from RAG pipeline
            
        Returns:
            Dictionary with scenario_prompt string
        """
        # Extract RAG context from RAGBlock TypedDict instead of DTO
        consolidated_rag = ""
        if rag_block:
            consolidated_rag = rag_block.get("response", "") or rag_block.get("rag_context", "")
        
        # Update create_scenario_from_dto to accept RAG separately
        prompt = create_scenario_from_dto_with_rag(dto, consolidated_rag)
        return {"scenario_prompt": prompt}

# Update create_scenario_from_dto to accept RAG from RAGBlock
def create_scenario_from_dto_with_rag(dto: Dict[str, Any], rag_context: str = "") -> str:
    """
    Generate scenario using direct GameEngine access and RAGBlock context.
    Eliminates RAG retrieval from DTO - architecture compliant.
    
    Args:
        dto: Streamlined DTO with engine references instead of state copies
        rag_context: RAG context extracted from RAGBlock TypedDict
        
    Returns:
        Formatted prompt string for LLM to generate scenario
    """
    # Remove RAG extraction from DTO (lines 134-136 in current code):
    # OLD: rag = dto.get("rag", {})
    # OLD: consolidated_rag = rag.get("rag_context", "")
    
    # NEW: Use provided RAG context from RAGBlock parameter
    consolidated_rag = rag_context
    
    # ... rest of existing engine access and prompt generation logic unchanged ...
```

### Phase 5: Update Pipeline Integration

**File**: `orchestrator/pipeline_integration.py`

```python
from shared_contract import (
    normalize_incoming, new_dto, RequestDTO, GameResponseDTO,
    request_dto_from_game_request, game_response_from_dto,
    new_response_dto, merge_dto_updates,
    convert_rag_response_to_ragblock, convert_scenario_response_to_scenario,
    create_unified_game_response
)

def _run_rag_pipeline(self, dto: RequestDTO) -> Dict[str, Any]:
    # ... existing pipeline logic ...
    
    # Convert agent response to RAGBlock format
    rag_block = convert_rag_response_to_ragblock(formatted_response)
    
    return {
        "response_type": "rag_query", 
        "rag_result": rag_block,
        "processing_metadata": {
            "pipeline_type": "connected_rag_query",
            "haystack_components_used": True,
            "pipeline_architecture": "connected_agent_plus_components",
            "filters_applied": filters
        }
    }

def _run_scenario_pipeline(self, dto: RequestDTO) -> Dict[str, Any]:
    # ... existing pipeline logic ...
    
    # Convert agent response to Scenario format  
    scenario = convert_scenario_response_to_scenario(validated_scenario["scenario"])
    
    return {
        "response_type": "scenario",
        "scenario": scenario, 
        "processing_metadata": {
            "pipeline_type": "connected_scenario_generation",
            "haystack_components_used": True,
            "pipeline_architecture": "connected_prompt_builder_plus_agent_plus_validator"
        }
    }

def _run_rag_enhanced_scenario_pipeline(self, dto: RequestDTO) -> Dict[str, Any]:
    # ... existing pipeline logic ...
    
    # Convert scenario response to standardized format
    scenario = convert_scenario_response_to_scenario(scenario_data)
    
    return {
        "response_type": "scenario",
        "scenario": scenario,
        "processing_metadata": {
            "pipeline_type": "rag_enhanced_scenario_generation",
            "rag_type": rag_type,
            "query_used": query,
            "haystack_pipeline_used": True,
            "validation_applied": True
        }
    }
```

### Phase 6: Update Response Conversion

**File**: `orchestrator/pipeline_integration.py`

```python
def _convert_dto_to_response(self, dto: RequestDTO, pipeline_result: Dict[str, Any]) -> GameResponse:
    """Enhanced conversion using unified response format"""
    
    # Determine response type
    response_type = pipeline_result.get("response_type", "scenario")
    
    # Create unified response using new converter function
    response_dto = create_unified_game_response(
        response_type=response_type,
        scenario=pipeline_result.get("scenario"),
        rag_result=pipeline_result.get("rag_result"), 
        npc_response=pipeline_result.get("npc_response"),
        correlation_id=dto.get("correlation_id"),
        metadata=pipeline_result.get("processing_metadata", {})
    )
    
    # Convert to GameResponse 
    return GameResponse(
        success=response_dto["success"],
        data=response_dto,  # Now contains structured data
        correlation_id=response_dto["correlation_id"],
        metadata=response_dto["metadata"]
    )
```

### Phase 7: Update haystack_dnd_game.py Response Handling

**File**: `haystack_dnd_game.py`

```python
def _format_enhanced_response(self, response_data: Dict[str, Any]) -> Dict[str, str]:
    """Format enhanced response data using new unified structure"""
    
    formatted_response = ""
    
    # Handle new unified response structure
    response_type = response_data.get("response_type", "unknown")
    
    if response_type == "scenario":
        scenario = response_data.get("scenario", {})
        formatted_response = scenario.get("scene", "The adventure continues...")
        
        # Add choices
        choices = scenario.get("choices", [])
        if choices:
            formatted_response += "\n\n📋 Available actions:"
            for choice in choices:
                title = choice.get("title", "Action")
                description = choice.get("description", "")
                formatted_response += f"\n• {title}: {description}"
                
    elif response_type == "rag_query":
        rag_result = response_data.get("rag_result", {})
        rag_context = rag_result.get("response", "")
        query = rag_result.get("query", "")
        confidence = rag_result.get("confidence", 0)
        
        if rag_context:
            formatted_response = f"📚 {rag_context}"
        else:
            formatted_response = f"I searched for information about '{query}', but couldn't find specific details."
            
    elif response_type == "npc_interaction":
        npc_response = response_data.get("npc_response", {})
        dialogue = npc_response.get("dialogue", "The NPC responds...")
        formatted_response = f"💬 {dialogue}"
    
    else:
        formatted_response = "The adventure continues in unexpected ways..."
    
    return {
        "formatted_response": formatted_response,
        "response_type": response_type,
        "confidence": response_data.get("scenario", {}).get("confidence", 0) or 
                      response_data.get("rag_result", {}).get("confidence", 0)
    }
```

## Implementation Order

1. **Phase 1**: Update GameResponseDTO structure 
2. **Phase 2**: Extend TypedDict definitions to match agent outputs
3. **Phase 3**: Create converter functions in shared_contract.py 
4. **Phase 4**: Update agent components to return standardized formats
5. **Phase 5**: Update pipeline integration to use converters
6. **Phase 6**: Update response conversion logic
7. **Phase 7**: Update main game response handling

## Benefits

- **Type Safety**: Proper TypedDict compliance across all responses
- **Consistency**: Unified response format regardless of pipeline
- **Maintainability**: Clear converter functions for format transformations
- **Clean Architecture**: No legacy cruft, modern structure throughout
- **Future-Proof**: Extensible structure for new response types

## Testing Strategy

After implementation:
1. Test scenario generation pipeline with new format
2. Test RAG query pipeline with new format  
3. Test NPC interaction pipeline with new format
4. Verify main game integration displays responses correctly
5. Validate all TypedDict compliance with type checking tools

This plan creates a clean, unified response format system without backward compatibility concerns, ensuring type safety and consistency throughout the D&D game system.