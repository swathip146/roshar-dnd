"""
Pydantic models extending the existing TypedDict system for Haystack v2 integration.
These models provide type-safe validation while preserving existing DTO structures.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Literal
from components.shared_contract import RequestDTO as RequestDTOTyped, GameResponseDTO as GameResponseDTOTyped

class IntentAnalysis(BaseModel):
    """Pydantic model for intent analysis results"""
    intent: Literal["SCENARIO_CHOICE", "RAG_QUERY", "NPC_INTERACT", "SKILL_CHECK"]
    confidence: float = Field(ge=0.0, le=1.0)
    flags: Dict[str, bool] = Field(default_factory=dict)
    reasoning: str = ""

class RAGContext(BaseModel):
    """Pydantic model for RAG context"""
    needed: bool = False
    query: str = ""
    category: str = "general"
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    response: str = ""

class SkillCheckResult(BaseModel):
    """Pydantic model for skill check results"""
    needed: bool = False
    success: Optional[bool] = None
    total: Optional[int] = None
    dc: Optional[int] = None
    roll_breakdown: Dict[str, Any] = Field(default_factory=dict)

class ParallelResults(BaseModel):
    """Pydantic model for joined parallel processing results"""
    rag: RAGContext
    skill_check: SkillCheckResult
    character_context: Dict[str, Any] = Field(default_factory=dict)

class ValidatedScenario(BaseModel):
    """Pydantic model for validated scenario output"""
    scene: str
    choices: List[Dict[str, Any]]
    effects: Dict[str, Any] = Field(default_factory=dict)
    hooks: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)

class HaystackRequestDTO(BaseModel):
    """Extended RequestDTO with Haystack pipeline metadata"""
    # Core request data (mirrors existing RequestDTO)
    player_input: str
    intent: str = ""
    confidence: float = 0.0
    flags: Dict[str, bool] = Field(default_factory=dict)
    
    # Haystack-specific extensions
    pipeline_metadata: Dict[str, Any] = Field(default_factory=dict)
    component_trace: List[str] = Field(default_factory=list)
    validation_results: Dict[str, Any] = Field(default_factory=dict)

class HaystackResponseDTO(BaseModel):
    """Extended GameResponseDTO with Haystack pipeline metadata"""
    # Core response data (mirrors existing GameResponseDTO)
    scene: str
    choices: List[Dict[str, Any]]
    success: bool = True
    
    # Haystack-specific extensions
    pipeline_metadata: Dict[str, Any] = Field(default_factory=dict)
    component_trace: List[str] = Field(default_factory=list)
    validation_results: Dict[str, Any] = Field(default_factory=dict)
    processing_time: float = 0.0

# Conversion utilities for seamless integration
def convert_legacy_request_dto(legacy_dto: RequestDTOTyped) -> HaystackRequestDTO:
    """Convert legacy RequestDTO to Pydantic HaystackRequestDTO"""
    return HaystackRequestDTO(
        player_input=legacy_dto.get("player_input", ""),
        intent=legacy_dto.get("intent", ""),
        confidence=legacy_dto.get("confidence", 0.0),
        flags=legacy_dto.get("flags", {}),
    )

def convert_legacy_response_dto(legacy_dto: GameResponseDTOTyped) -> HaystackResponseDTO:
    """Convert legacy GameResponseDTO to Pydantic HaystackResponseDTO"""
    return HaystackResponseDTO(
        scene=legacy_dto.get("scene", ""),
        choices=legacy_dto.get("choices", []),
        success=legacy_dto.get("success", True),
    )

def convert_to_legacy_response_dto(haystack_dto: HaystackResponseDTO) -> GameResponseDTOTyped:
    """Convert HaystackResponseDTO back to legacy GameResponseDTO format"""
    return {
        "scene": haystack_dto.scene,
        "choices": haystack_dto.choices,
        "success": haystack_dto.success,
    }