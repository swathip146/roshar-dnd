"""
Haystack Command Processing Pipeline
Phase 2: Replace BaseCommandHandler with Haystack pipeline-based command processing
"""

import time
from typing import Dict, Any, List, Optional
from haystack import Pipeline, component
from haystack.components.routers import ConditionalRouter

# Import Phase 1 components (fixed version)
from core.haystack_native_orchestrator_fixed import IntentClassificationComponent, GameStateManager


class CommandProcessingPipeline(Pipeline):
    """Main command processing pipeline that routes to specialized pipelines"""
    
    def __init__(self, 
                 game_state_manager: GameStateManager,
                 llm_generator,
                 verbose: bool = False):
        super().__init__()
        
        self.verbose = verbose
        
        # Add core processing components
        self.add_component("intent_classifier", IntentClassificationComponent(llm_generator))
        self.add_component("context_enricher", ContextEnrichmentComponent(game_state_manager))
        
        # Add conditional router for pipeline selection
        self.add_component("pipeline_router", ConditionalRouter(routes=[
            {
                "condition": "{{intent == 'SKILL_CHECK'}}",
                "output": "{{skill_check_input}}",
                "output_name": "skill_check_pipeline",
                "output_type": Dict[str, Any]
            },
            {
                "condition": "{{intent == 'COMBAT_ACTION'}}",
                "output": "{{combat_input}}",
                "output_name": "combat_pipeline",
                "output_type": Dict[str, Any]
            },
            {
                "condition": "{{intent == 'RULE_QUERY'}}",
                "output": "{{rule_query_input}}",
                "output_name": "rule_query_pipeline",
                "output_type": Dict[str, Any]
            },
            {
                "condition": "{{intent == 'LORE_LOOKUP'}}",
                "output": "{{lore_input}}",
                "output_name": "lore_pipeline",
                "output_type": Dict[str, Any]
            },
            {
                "condition": "{{intent == 'CHARACTER_MANAGEMENT'}}",
                "output": "{{character_input}}",
                "output_name": "character_pipeline",
                "output_type": Dict[str, Any]
            },
            {
                "condition": "{{intent == 'SCENARIO_CHOICE'}}",
                "output": "{{scenario_input}}",
                "output_name": "scenario_pipeline",
                "output_type": Dict[str, Any]
            },
            {
                "condition": "{{intent == 'INVENTORY_ACTION'}}",
                "output": "{{inventory_input}}",
                "output_name": "inventory_pipeline",
                "output_type": Dict[str, Any]
            },
            {
                "condition": "{{intent == 'SPELL_CASTING'}}",
                "output": "{{spell_input}}",
                "output_name": "spell_pipeline",
                "output_type": Dict[str, Any]
            },
            {
                "condition": "{{intent == 'SESSION_MANAGEMENT'}}",
                "output": "{{session_input}}",
                "output_name": "session_pipeline",
                "output_type": Dict[str, Any]
            },
            {
                "condition": "{{intent == 'DICE_ROLL'}}",
                "output": "{{dice_input}}",
                "output_name": "dice_pipeline",
                "output_type": Dict[str, Any]
            }
        ]))
        
        # Add specialized pipelines (will be implemented in Phase 3)
        self.add_component("skill_check_pipeline", SkillCheckPipelineNative())
        self.add_component("combat_pipeline", CombatActionPipelineNative())
        self.add_component("rule_query_pipeline", RuleQueryPipelineNative())
        self.add_component("lore_pipeline", LoreQueryPipelineNative())
        self.add_component("character_pipeline", CharacterManagementPipelineNative())
        self.add_component("scenario_pipeline", ScenarioChoicePipelineNative())
        self.add_component("inventory_pipeline", InventoryActionPipelineNative())
        self.add_component("spell_pipeline", SpellCastingPipelineNative())
        self.add_component("session_pipeline", SessionManagementPipelineNative())
        self.add_component("dice_pipeline", DiceRollPipelineNative())
        
        # Add response formatter
        self.add_component("response_formatter", ResponseFormatterComponent())
        
        # Connect the pipeline
        self._connect_pipeline()
        
        if verbose:
            print("🔧 CommandProcessingPipeline initialized")
    
    def _connect_pipeline(self):
        """Connect the pipeline components"""
        
        # Intent classification -> Context enrichment
        self.connect("intent_classifier", "context_enricher")
        
        # Context enrichment -> Router
        self.connect("context_enricher", "pipeline_router")
        
        # Router -> Specialized pipelines
        self.connect("pipeline_router.skill_check_pipeline", "skill_check_pipeline")
        self.connect("pipeline_router.combat_pipeline", "combat_pipeline") 
        self.connect("pipeline_router.rule_query_pipeline", "rule_query_pipeline")
        self.connect("pipeline_router.lore_pipeline", "lore_pipeline")
        self.connect("pipeline_router.character_pipeline", "character_pipeline")
        self.connect("pipeline_router.scenario_pipeline", "scenario_pipeline")
        self.connect("pipeline_router.inventory_pipeline", "inventory_pipeline")
        self.connect("pipeline_router.spell_pipeline", "spell_pipeline")
        self.connect("pipeline_router.session_pipeline", "session_pipeline")
        self.connect("pipeline_router.dice_pipeline", "dice_pipeline")
        
        # All specialized pipelines -> Response formatter
        self.connect("skill_check_pipeline", "response_formatter")
        self.connect("combat_pipeline", "response_formatter")
        self.connect("rule_query_pipeline", "response_formatter")
        self.connect("lore_pipeline", "response_formatter")
        self.connect("character_pipeline", "response_formatter")
        self.connect("scenario_pipeline", "response_formatter")
        self.connect("inventory_pipeline", "response_formatter")
        self.connect("spell_pipeline", "response_formatter")
        self.connect("session_pipeline", "response_formatter")
        self.connect("dice_pipeline", "response_formatter")


@component  
class ContextEnrichmentComponent:
    """Enrich commands with game state context"""
    
    def __init__(self, game_state_manager: GameStateManager):
        self.game_state = game_state_manager
        
    @component.output_types(
        query=str,
        intent=str,
        enriched_context=Dict[str, Any],
        characters=List[Dict[str, Any]],
        campaign_info=Dict[str, Any],
        session_state=Dict[str, Any]
    )
    def run(self, query: str, intent: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Enrich command with current game state context"""
        
        # Get current game state components
        current_characters = self.game_state.get_active_characters()
        campaign_info = self.game_state.get_campaign_context()
        session_state = self.game_state.get_session_state()
        
        # Build enriched context
        enriched_context = {
            **(context or {}),
            "timestamp": time.time(),
            "characters_count": len(current_characters),
            "session_active": session_state.get("active", False),
            "campaign_loaded": bool(campaign_info),
            "intent": intent
        }
        
        # Add character names for easy reference
        if current_characters:
            enriched_context["character_names"] = [
                char.get("name", "Unknown") for char in current_characters
            ]
        
        return {
            "query": query,
            "intent": intent,
            "enriched_context": enriched_context,
            "characters": current_characters,
            "campaign_info": campaign_info,
            "session_state": session_state
        }


@component
class ResponseFormatterComponent:
    """Format pipeline responses into consistent format"""
    
    @component.output_types(
        formatted_response=str,
        response_data=Dict[str, Any],
        success=bool
    )
    def run(self, **kwargs) -> Dict[str, Any]:
        """Format response from any specialized pipeline"""
        
        # Extract the actual response from whichever pipeline produced output
        pipeline_result = None
        pipeline_name = "unknown"
        
        # Check for results from different pipelines
        for key, value in kwargs.items():
            if isinstance(value, dict) and value:
                pipeline_result = value
                pipeline_name = key
                break
        
        if not pipeline_result:
            return {
                "formatted_response": "❌ No response generated from pipeline",
                "response_data": {"error": "No pipeline response"},
                "success": False
            }
        
        # Format based on pipeline type and result structure
        success = pipeline_result.get("success", True)
        
        if success:
            # Format successful response
            formatted_text = self._format_success_response(pipeline_result, pipeline_name)
        else:
            # Format error response
            formatted_text = self._format_error_response(pipeline_result, pipeline_name)
        
        return {
            "formatted_response": formatted_text,
            "response_data": pipeline_result,
            "success": success
        }
    
    def _format_success_response(self, result: Dict[str, Any], pipeline: str) -> str:
        """Format successful pipeline response"""
        
        # Different formatting based on pipeline type
        if "skill_check" in pipeline:
            return self._format_skill_check_response(result)
        elif "combat" in pipeline:
            return self._format_combat_response(result)
        elif "rule_query" in pipeline or "lore" in pipeline:
            return self._format_query_response(result)
        else:
            return self._format_generic_response(result)
    
    def _format_skill_check_response(self, result: Dict[str, Any]) -> str:
        """Format skill check response"""
        
        if "applied_result" in result and "data" in result["applied_result"]:
            data = result["applied_result"]["data"]
            
            roll = data.get("roll", "?")
            modifier = data.get("modifier", "?")
            total = data.get("total", "?")
            success = data.get("success", False)
            skill = data.get("skill", "unknown")
            
            status_emoji = "✅" if success else "❌"
            
            return (f"{status_emoji} **{skill.title()} Check**\n"
                   f"🎲 Roll: {roll} + {modifier} = **{total}**\n"
                   f"{'Success!' if success else 'Failure!'}")
        
        return "🎲 Skill check completed"
    
    def _format_combat_response(self, result: Dict[str, Any]) -> str:
        """Format combat action response"""
        
        action_type = result.get("action_type", "Combat Action")
        success = result.get("success", True)
        
        if success:
            return f"⚔️ **{action_type}** executed successfully"
        else:
            return f"❌ **{action_type}** failed: {result.get('error', 'Unknown error')}"
    
    def _format_query_response(self, result: Dict[str, Any]) -> str:
        """Format rule/lore query response"""
        
        if "answer" in result:
            return f"📖 **Query Result**\n{result['answer']}"
        elif "response" in result:
            return f"📖 {result['response']}"
        else:
            return "📖 Query processed successfully"
    
    def _format_generic_response(self, result: Dict[str, Any]) -> str:
        """Format generic pipeline response"""
        
        if "message" in result:
            return f"✅ {result['message']}"
        else:
            return "✅ Command processed successfully"
    
    def _format_error_response(self, result: Dict[str, Any], pipeline: str) -> str:
        """Format error response"""
        
        error = result.get("error", "Unknown error occurred")
        return f"❌ **{pipeline.replace('_', ' ').title()} Error**\n{error}"


# Placeholder pipeline implementations (to be fully implemented in Phase 3)

class SkillCheckPipelineNative(Pipeline):
    """Native Haystack skill check pipeline"""
    
    def __init__(self):
        super().__init__()
        self.add_component("processor", SkillCheckProcessorComponent())
        
    @component.output_types(result=Dict[str, Any])
    def run(self, **kwargs) -> Dict[str, Any]:
        # Simplified implementation for now
        return {
            "applied_result": {
                "data": {
                    "roll": 15,
                    "modifier": 3,
                    "total": 18,
                    "success": True,
                    "skill": kwargs.get("enriched_context", {}).get("skill", "athletics")
                }
            },
            "success": True
        }


@component
class SkillCheckProcessorComponent:
    """Process skill checks"""
    
    @component.output_types(result=Dict[str, Any])
    def run(self, **kwargs) -> Dict[str, Any]:
        return {"result": {"processed": True}}


class CombatActionPipelineNative(Pipeline):
    """Native Haystack combat action pipeline"""
    
    def __init__(self):
        super().__init__()
        
    def run(self, **kwargs) -> Dict[str, Any]:
        return {
            "action_type": "Attack",
            "success": True,
            "damage": 8
        }


class RuleQueryPipelineNative(Pipeline):
    """Native Haystack rule query pipeline"""
    
    def __init__(self):
        super().__init__()
        
    def run(self, **kwargs) -> Dict[str, Any]:
        query = kwargs.get("query", "")
        return {
            "answer": f"Rule information for: {query}",
            "success": True
        }


class LoreQueryPipelineNative(Pipeline):
    """Native Haystack lore query pipeline"""
    
    def __init__(self):
        super().__init__()
        
    def run(self, **kwargs) -> Dict[str, Any]:
        query = kwargs.get("query", "")
        return {
            "answer": f"Lore information for: {query}",
            "success": True
        }


class CharacterManagementPipelineNative(Pipeline):
    """Native Haystack character management pipeline"""
    
    def __init__(self):
        super().__init__()
        
    def run(self, **kwargs) -> Dict[str, Any]:
        return {
            "message": "Character management action completed",
            "success": True
        }


class ScenarioChoicePipelineNative(Pipeline):
    """Native Haystack scenario choice pipeline"""
    
    def __init__(self):
        super().__init__()
        
    def run(self, **kwargs) -> Dict[str, Any]:
        return {
            "message": "Scenario choice processed",
            "success": True
        }


class InventoryActionPipelineNative(Pipeline):
    """Native Haystack inventory action pipeline"""
    
    def __init__(self):
        super().__init__()
        
    def run(self, **kwargs) -> Dict[str, Any]:
        return {
            "message": "Inventory action completed",
            "success": True
        }


class SpellCastingPipelineNative(Pipeline):
    """Native Haystack spell casting pipeline"""
    
    def __init__(self):
        super().__init__()
        
    def run(self, **kwargs) -> Dict[str, Any]:
        return {
            "message": "Spell casting completed",
            "success": True
        }


class SessionManagementPipelineNative(Pipeline):
    """Native Haystack session management pipeline"""
    
    def __init__(self):
        super().__init__()
        
    def run(self, **kwargs) -> Dict[str, Any]:
        return {
            "message": "Session management action completed",
            "success": True
        }


class DiceRollPipelineNative(Pipeline):
    """Native Haystack dice roll pipeline"""
    
    def __init__(self):
        super().__init__()
        
    def run(self, **kwargs) -> Dict[str, Any]:
        return {
            "roll_result": 15,
            "message": "🎲 Rolled: 15",
            "success": True
        }