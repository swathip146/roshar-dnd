"""
Unit tests for Pydantic models and DTO validation.
"""

import pytest
from pydantic import ValidationError
from models.pydantic_dtos import (
    IntentAnalysis, RAGContext, SkillCheckResult, ParallelResults, 
    ValidatedScenario, HaystackRequestDTO, HaystackResponseDTO,
    convert_legacy_request_dto, convert_legacy_response_dto, convert_to_legacy_response_dto
)

class TestIntentAnalysis:
    """Test IntentAnalysis Pydantic model"""
    
    def test_valid_intent_analysis(self):
        """Test valid intent analysis creation"""
        intent = IntentAnalysis(
            intent="SCENARIO_CHOICE",
            confidence=0.85,
            flags={"need_rag": True},
            reasoning="Player is making a choice"
        )
        
        assert intent.intent == "SCENARIO_CHOICE"
        assert intent.confidence == 0.85
        assert intent.flags["need_rag"] is True
        assert intent.reasoning == "Player is making a choice"
    
    def test_invalid_intent(self):
        """Test invalid intent type raises validation error"""
        with pytest.raises(ValidationError):
            IntentAnalysis(
                intent="INVALID_INTENT",
                confidence=0.5
            )
    
    def test_invalid_confidence_range(self):
        """Test confidence must be between 0.0 and 1.0"""
        with pytest.raises(ValidationError):
            IntentAnalysis(
                intent="RAG_QUERY",
                confidence=1.5
            )
        
        with pytest.raises(ValidationError):
            IntentAnalysis(
                intent="RAG_QUERY",
                confidence=-0.1
            )

class TestRAGContext:
    """Test RAGContext Pydantic model"""
    
    def test_default_values(self):
        """Test RAGContext with default values"""
        rag = RAGContext()
        
        assert rag.needed is False
        assert rag.query == ""
        assert rag.category == "general"
        assert rag.confidence == 0.0
        assert rag.response == ""
    
    def test_valid_rag_context(self):
        """Test valid RAG context creation"""
        rag = RAGContext(
            needed=True,
            query="What is a fireball spell?",
            category="spells",
            confidence=0.9,
            response="Fireball is a 3rd level evocation spell..."
        )
        
        assert rag.needed is True
        assert rag.query == "What is a fireball spell?"
        assert rag.category == "spells"
        assert rag.confidence == 0.9

class TestSkillCheckResult:
    """Test SkillCheckResult Pydantic model"""
    
    def test_default_skill_check(self):
        """Test skill check with default values"""
        skill = SkillCheckResult()
        
        assert skill.needed is False
        assert skill.success is None
        assert skill.total is None
        assert skill.dc is None
        assert skill.roll_breakdown == {}
    
    def test_successful_skill_check(self):
        """Test successful skill check"""
        skill = SkillCheckResult(
            needed=True,
            success=True,
            total=18,
            dc=15,
            roll_breakdown={"d20": 12, "modifier": 6}
        )
        
        assert skill.needed is True
        assert skill.success is True
        assert skill.total == 18
        assert skill.dc == 15
        assert skill.roll_breakdown["d20"] == 12

class TestParallelResults:
    """Test ParallelResults Pydantic model"""
    
    def test_parallel_results_creation(self):
        """Test creating parallel results with nested models"""
        rag = RAGContext(needed=True, query="test query")
        skill = SkillCheckResult(needed=False)
        
        results = ParallelResults(
            rag=rag,
            skill_check=skill,
            character_context={"party_size": 4}
        )
        
        assert results.rag.needed is True
        assert results.skill_check.needed is False
        assert results.character_context["party_size"] == 4

class TestValidatedScenario:
    """Test ValidatedScenario Pydantic model"""
    
    def test_valid_scenario(self):
        """Test valid scenario creation"""
        scenario = ValidatedScenario(
            scene="You enter a dark tavern.",
            choices=[
                {"text": "Approach the bar", "action": "bar"},
                {"text": "Look around", "action": "investigate"}
            ],
            effects={"atmosphere": "tense"},
            hooks=["mysterious_patron"],
            confidence=0.9
        )
        
        assert scenario.scene == "You enter a dark tavern."
        assert len(scenario.choices) == 2
        assert scenario.confidence == 0.9
    
    def test_default_scenario_values(self):
        """Test scenario with minimal required fields"""
        scenario = ValidatedScenario(
            scene="Test scene",
            choices=[{"text": "Continue", "action": "continue"}]
        )
        
        assert scenario.effects == {}
        assert scenario.hooks == []
        assert scenario.confidence == 0.8

class TestHaystackDTOs:
    """Test Haystack DTO extensions"""
    
    def test_haystack_request_dto(self):
        """Test HaystackRequestDTO with metadata"""
        request = HaystackRequestDTO(
            player_input="I want to cast a spell",
            intent="SKILL_CHECK",
            confidence=0.8,
            flags={"need_check": True},
            pipeline_metadata={"test": True},
            component_trace=["component1", "component2"]
        )
        
        assert request.player_input == "I want to cast a spell"
        assert request.pipeline_metadata["test"] is True
        assert len(request.component_trace) == 2
    
    def test_haystack_response_dto(self):
        """Test HaystackResponseDTO with metadata"""
        response = HaystackResponseDTO(
            scene="You cast the spell successfully",
            choices=[{"text": "Continue", "action": "continue"}],
            success=True,
            pipeline_metadata={"execution_time": 0.5},
            processing_time=0.5
        )
        
        assert response.success is True
        assert response.processing_time == 0.5
        assert response.pipeline_metadata["execution_time"] == 0.5

class TestDTOConversions:
    """Test DTO conversion functions"""
    
    def test_convert_legacy_request(self):
        """Test converting legacy RequestDTO to HaystackRequestDTO"""
        legacy_request = {
            "player_input": "Test input",
            "intent": "SCENARIO_CHOICE",
            "confidence": 0.7,
            "flags": {"test": True}
        }
        
        haystack_request = convert_legacy_request_dto(legacy_request)
        
        assert isinstance(haystack_request, HaystackRequestDTO)
        assert haystack_request.player_input == "Test input"
        assert haystack_request.intent == "SCENARIO_CHOICE"
        assert haystack_request.confidence == 0.7
    
    def test_convert_legacy_response(self):
        """Test converting legacy GameResponseDTO to HaystackResponseDTO"""
        legacy_response = {
            "scene": "Test scene",
            "choices": [{"text": "Test", "action": "test"}],
            "success": True
        }
        
        haystack_response = convert_legacy_response_dto(legacy_response)
        
        assert isinstance(haystack_response, HaystackResponseDTO)
        assert haystack_response.scene == "Test scene"
        assert len(haystack_response.choices) == 1
        assert haystack_response.success is True
    
    def test_convert_to_legacy_response(self):
        """Test converting HaystackResponseDTO back to legacy format"""
        haystack_response = HaystackResponseDTO(
            scene="Test scene",
            choices=[{"text": "Test", "action": "test"}],
            success=True,
            processing_time=0.3
        )
        
        legacy_response = convert_to_legacy_response_dto(haystack_response)
        
        assert legacy_response["scene"] == "Test scene"
        assert legacy_response["success"] is True
        assert len(legacy_response["choices"]) == 1
        # Processing time should not be in legacy response
        assert "processing_time" not in legacy_response

if __name__ == "__main__":
    pytest.main([__file__])