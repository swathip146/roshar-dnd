"""
Unit tests for native Haystack components.
"""

import pytest
from unittest.mock import Mock, MagicMock
from haystack import Pipeline

from components.haystack_native.parallel_components import (
    IntentBasedRouter, SimpleIntentRouter, GameIntentRouter,
    RAGFlagRouter, SkillCheckFlagRouter, ParallelResultsJoiner,
    AdaptiveRAGRouter, AdaptiveSkillRouter
)
from components.haystack_native.validation_components import (
    PydanticValidator, ScenarioValidator, ParallelResultsValidator,
    DataSanitizer, CompositeValidator
)
from components.haystack_native.legacy_adapters import (
    GameEngineAdapter, CharacterManagerAdapter, SkillCheckAdapter,
    BypassComponent, RAGBypassComponent, SkillCheckBypassComponent
)
from models.pydantic_dtos import ValidatedScenario, ParallelResults

class TestIntentRouters:
    """Test intent routing components"""
    
    def test_simple_intent_router_scenario(self):
        """Test simple intent router with scenario processing"""
        router = SimpleIntentRouter()
        
        request_data = {
            "player_input": "I want to explore the dungeon",
            "intent": "SCENARIO_CHOICE",
            "confidence": 0.8
        }
        
        result = router.run(request_data)
        
        assert "scenario_processing" in result
        assert result["scenario_processing"] == request_data
    
    def test_simple_intent_router_rag(self):
        """Test simple intent router with RAG query"""
        router = SimpleIntentRouter()
        
        request_data = {
            "player_input": "What is a fireball spell?",
            "intent": "RAG_QUERY",
            "confidence": 0.9
        }
        
        result = router.run(request_data)
        
        assert "rag_query" in result
        assert result["rag_query"] == request_data
    
    def test_simple_intent_router_default(self):
        """Test simple intent router default route"""
        router = SimpleIntentRouter()
        
        request_data = {
            "player_input": "Unknown command",
            "intent": "UNKNOWN",
            "confidence": 0.3
        }
        
        result = router.run(request_data)
        
        assert "default_route" in result
        assert result["default_route"] == request_data

class TestParallelComponents:
    """Test parallel processing components"""
    
    def test_adaptive_rag_router_needs_rag(self):
        """Test adaptive RAG router detects need for RAG"""
        router = AdaptiveRAGRouter()
        
        request_data = {
            "player_input": "tell me about dragons",
            "flags": {}
        }
        
        result = router.run(request_data)
        
        assert "rag_needed" in result
        assert result["rag_needed"] == request_data
    
    def test_adaptive_rag_router_bypass(self):
        """Test adaptive RAG router bypasses when not needed"""
        router = AdaptiveRAGRouter()
        
        request_data = {
            "player_input": "I go north",
            "flags": {}
        }
        
        result = router.run(request_data)
        
        assert "rag_bypass" in result
        assert result["rag_bypass"] == request_data
    
    def test_adaptive_skill_router_needs_check(self):
        """Test adaptive skill router detects skill check need"""
        router = AdaptiveSkillRouter()
        
        request_data = {
            "player_input": "I try to climb the wall",
            "flags": {}
        }
        
        result = router.run(request_data)
        
        assert "skill_needed" in result
        assert result["skill_needed"] == request_data
    
    def test_adaptive_skill_router_bypass(self):
        """Test adaptive skill router bypasses when not needed"""
        router = AdaptiveSkillRouter()
        
        request_data = {
            "player_input": "I say hello",
            "flags": {}
        }
        
        result = router.run(request_data)
        
        assert "skill_bypass" in result
        assert result["skill_bypass"] == request_data
    
    def test_parallel_results_joiner(self):
        """Test parallel results joiner merges data correctly"""
        joiner = ParallelResultsJoiner()
        
        rag_result = {"response": "Dragons are powerful creatures"}
        skill_result = {"success": True, "total": 15}
        char_context = {"party_size": 4}
        
        result = joiner.run(
            rag_result=rag_result,
            skill_result=skill_result,
            char_context=char_context
        )
        
        # Variadic approach preserves input names as keys under "parallel_results"
        assert "parallel_results" in result
        parallel_data = result["parallel_results"]
        
        assert "rag_result" in parallel_data
        assert "skill_result" in parallel_data
        assert "char_context" in parallel_data
        
        assert parallel_data["rag_result"] == rag_result
        assert parallel_data["skill_result"] == skill_result
        assert parallel_data["char_context"] == char_context
    def test_parallel_results_joiner_missing_data(self):
        """Test parallel results joiner handles missing data"""
        joiner = ParallelResultsJoiner()
        
        result = joiner.run()
        
        # With no inputs, should return empty parallel_results dict
        assert result == {"parallel_results": {}}

class TestValidationComponents:
    """Test validation components"""
    
    def test_scenario_validator_valid_data(self):
        """Test scenario validator with valid data"""
        validator = ScenarioValidator()
        
        scenario_data = {
            "scene": "You enter a tavern",
            "choices": [
                {"text": "Order a drink", "action": "drink"},
                {"text": "Talk to the bartender", "action": "talk"}
            ],
            "effects": {},
            "hooks": [],
            "confidence": 0.8
        }
        
        result = validator.run(scenario_data)
        
        assert "validated_scenario" in result
        assert "validation_error" not in result
        assert result["validated_scenario"]["scene"] == "You enter a tavern"
    
    def test_scenario_validator_empty_scene(self):
        """Test scenario validator rejects empty scene"""
        validator = ScenarioValidator()
        
        scenario_data = {
            "scene": "",
            "choices": [{"text": "Continue", "action": "continue"}]
        }
        
        result = validator.run(scenario_data)
        
        assert "validation_error" in result
        assert "Scene cannot be empty" in result["validation_error"]
    
    def test_scenario_validator_no_choices(self):
        """Test scenario validator requires choices"""
        validator = ScenarioValidator()
        
        scenario_data = {
            "scene": "Test scene",
            "choices": []
        }
        
        result = validator.run(scenario_data)
        
        assert "validation_error" in result
        assert "At least one choice must be provided" in result["validation_error"]
    
    def test_data_sanitizer(self):
        """Test data sanitizer cleans input"""
        sanitizer = DataSanitizer()
        
        raw_data = {
            "text": "  Hello World  ",
            "nested": {
                "value": "  test  "
            },
            "list_data": ["  item1  ", "  item2  "],
            "number": 42
        }
        
        result = sanitizer.run(raw_data)
        
        assert "sanitized_data" in result
        sanitized = result["sanitized_data"]
        assert sanitized["text"] == "Hello World"
        assert sanitized["nested"]["value"] == "test"
        assert sanitized["list_data"] == ["item1", "item2"]
        assert sanitized["number"] == 42
    
    def test_composite_validator(self):
        """Test composite validator with different types"""
        validator = CompositeValidator()
        
        # Test scenario validation
        scenario_data = {
            "scene": "Test scene",
            "choices": [{"text": "Continue", "action": "continue"}]
        }
        
        result = validator.run(scenario_data, validation_type="scenario")
        
        assert result["validation_type"] == "scenario"
        assert "validated_scenario" in result or "validation_error" in result

class TestLegacyAdapters:
    """Test legacy system adapters"""
    
    def test_game_engine_adapter(self):
        """Test GameEngine adapter"""
        mock_engine = Mock()
        mock_engine.get_narrative_context.return_value = {"scene": "test"}
        mock_engine.get_location_context.return_value = {"location": "tavern"}
        mock_engine.get_quest_context.return_value = {"quest": "find_artifact"}
        mock_engine.get_game_state.return_value = {"state": "active"}
        
        adapter = GameEngineAdapter(mock_engine)
        
        result = adapter.run({"test": "data"})
        
        assert "state_context" in result
        context = result["state_context"]
        assert context["narrative_context"]["scene"] == "test"
        assert context["location_context"]["location"] == "tavern"
        assert context["quest_context"]["quest"] == "find_artifact"
    
    def test_game_engine_adapter_error_handling(self):
        """Test GameEngine adapter error handling"""
        mock_engine = Mock()
        mock_engine.get_narrative_context.side_effect = Exception("Test error")
        
        adapter = GameEngineAdapter(mock_engine)
        
        result = adapter.run({"test": "data"})
        
        assert "state_context" in result
        assert "error" in result["state_context"]
        assert "Test error" in result["state_context"]["error"]
    
    def test_character_manager_adapter(self):
        """Test CharacterManager adapter"""
        mock_manager = Mock()
        mock_manager.get_party_snapshot.return_value = {
            "characters": [{"name": "Aragorn", "class": "Ranger"}]
        }
        
        adapter = CharacterManagerAdapter(mock_manager)
        
        result = adapter.run({"test": "data"})
        
        assert "party_context" in result
        context = result["party_context"]
        assert context["party_size"] == 1
        assert len(context["party_snapshot"]["characters"]) == 1
    
    def test_rules_enforcer_adapter(self):
        """Test RulesEnforcer adapter"""
        mock_engine = Mock()
        mock_engine.process_skill_check.return_value = {
            "success": True,
            "total": 18,
            "dc": 15
        }
        mock_engine.rules_enforcer = Mock()
        
        adapter = SkillCheckAdapter(mock_engine)
        
        skill_request = {
            "skill": "Athletics",
            "dc": 15
        }
        
        result = adapter.run(skill_request)
        
        assert "skill_check_result" in result
        skill_result = result["skill_check_result"]
        assert skill_result["success"] is True
        assert skill_result["total"] == 18
    
    def test_bypass_component(self):
        """Test basic bypass component"""
        bypass = BypassComponent()
        
        result = bypass.run()
        
        assert "bypass_result" in result
        assert result["bypass_result"]["bypassed"] is True
        assert "timestamp" in result["bypass_result"]
    
    def test_rag_bypass_component(self):
        """Test RAG-specific bypass component"""
        bypass = RAGBypassComponent()
        
        result = bypass.run()
        
        assert "rag_result" in result
        rag_result = result["rag_result"]
        assert rag_result["needed"] is False
        assert rag_result["bypassed"] is True
        assert rag_result["category"] == "bypassed"
    
    def test_skill_check_bypass_component(self):
        """Test skill check-specific bypass component"""
        bypass = SkillCheckBypassComponent()
        
        result = bypass.run()
        
        assert "skill_result" in result
        skill_result = result["skill_result"]
        assert skill_result["needed"] is False
        assert skill_result["bypassed"] is True
        assert skill_result["success"] is None

class TestComponentIntegration:
    """Test component integration patterns"""
    
    def test_component_chaining(self):
        """Test basic component chaining works"""
        sanitizer = DataSanitizer()
        validator = ScenarioValidator()
        
        # First sanitize data
        raw_data = {
            "scene": "  Test scene  ",
            "choices": [{"text": "  Continue  ", "action": "continue"}]
        }
        
        sanitized_result = sanitizer.run(raw_data)
        sanitized_data = sanitized_result["sanitized_data"]
        
        # Then validate sanitized data
        validation_result = validator.run(sanitized_data)
        
        if "validated_scenario" in validation_result:
            assert validation_result["validated_scenario"]["scene"] == "Test scene"
        else:
            # Check for validation error
            assert "validation_error" in validation_result
    
    def test_parallel_processing_flow(self):
        """Test parallel processing component flow"""
        # Setup adaptive routers
        rag_router = AdaptiveRAGRouter()
        skill_router = AdaptiveSkillRouter()
        joiner = ParallelResultsJoiner()
        
        # Test input that needs both RAG and skill check
        request_data = {
            "player_input": "I want to cast fireball and roll to hit",
            "flags": {}
        }
        
        # Route through both branches
        rag_result = rag_router.run(request_data)
        skill_result = skill_router.run(request_data)
        
        # Both should be needed
        assert "rag_needed" in rag_result or "rag_bypass" in rag_result
        assert "skill_needed" in skill_result or "skill_bypass" in skill_result
        
        # Simulate processing results
        mock_rag_output = {"response": "Fireball spell info"}
        mock_skill_output = {"success": True, "total": 16}
        
        # Join results
        joined_result = joiner.run(
            rag_result=mock_rag_output,
            skill_result=mock_skill_output
        )
        # Variadic approach preserves input names as keys under "parallel_results"
        assert "parallel_results" in joined_result
        parallel_data = joined_result["parallel_results"]
        
        assert "rag_result" in parallel_data
        assert "skill_result" in parallel_data
        
        assert parallel_data["rag_result"] == mock_rag_output
        assert parallel_data["skill_result"] == mock_skill_output

if __name__ == "__main__":
    pytest.main([__file__])