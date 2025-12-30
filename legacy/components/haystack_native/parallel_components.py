"""
Native Haystack routing and parallel processing components.
Consolidates all ConditionalRouter-based routing logic and parallel processing capabilities.
"""

from haystack import component
from haystack.components.routers import ConditionalRouter
from haystack.components.joiners import BranchJoiner
from typing import Dict, Any, List, Optional

# === INTENT-BASED ROUTING COMPONENTS ===

@component
class IntentBasedRouter(ConditionalRouter):
    """Route based on player intent classification using native ConditionalRouter"""
    
    def __init__(self):
        routes = [
            {
                "condition": "{{ intent == 'RAG_QUERY' }}",
                "output": "{{ player_input }}",
                "output_name": "rag_query",
                "output_type": str,
            },
            {
                "condition": "{{ intent == 'NPC_INTERACT' }}",
                "output": "{{ player_input }}",
                "output_name": "npc_interaction",
                "output_type": str,
            },
            {
                "condition": "{{ intent == 'SCENARIO_CHOICE' or intent == 'SKILL_CHECK' }}",
                "output": "{{ player_input }}",
                "output_name": "scenario_processing",
                "output_type": str,
            }
        ]
        super().__init__(routes=routes)

@component
class GameIntentRouter(ConditionalRouter):
    """Advanced intent router with enhanced condition checking"""
    
    def __init__(self):
        routes = [
            {
                "condition": "{{ intent_data.get('type') == 'rag_query' }}",
                "output": "{{ request }}",
                "output_name": "rag_pipeline",
                "output_type": dict,
            },
            {
                "condition": "{{ intent_data.get('type') == 'npc_interaction' }}",
                "output": "{{ request }}",
                "output_name": "npc_pipeline",
                "output_type": dict,
            },
            {
                "condition": "{{ intent_data.get('rag', {}).get('needed', False) }}",
                "output": "{{ request }}",
                "output_name": "scenario_with_rag_pipeline",
                "output_type": dict,
            }
        ]
        default_route = "scenario_pipeline"
        super().__init__(routes=routes, default_route=default_route)

@component
class SimpleIntentRouter:
    """Simple custom intent router for basic routing needs"""
    
    @component.output_types(
        scenario_processing=Dict[str, Any],
        rag_query=Dict[str, Any],
        npc_interaction=Dict[str, Any],
        default_route=Dict[str, Any]
    )
    def run(self, interface_result: dict) -> Dict[str, Dict[str, Any]]:
        """Route request based on intent with fallback logic"""
        
        # Handle both direct dict and nested interface_result structure
        if isinstance(interface_result, dict) and "interface_result" in interface_result:
            request_data = interface_result["interface_result"]
        else:
            request_data = interface_result
        
        intent = request_data.get("intent", "").upper()
        
        # Route based on intent type
        if intent == "RAG_QUERY":
            return {"rag_query": request_data}
        elif intent == "NPC_INTERACT":
            return {"npc_interaction": request_data}
        elif intent in ["SCENARIO_CHOICE", "SKILL_CHECK"]:
            return {"scenario_processing": request_data}
        else:
            # Default route for unknown intents
            return {"scenario_processing": request_data}  # Changed from default_route to scenario_processing

# === FLAG-BASED ROUTING COMPONENTS ===

@component
class RAGFlagRouter(ConditionalRouter):
    """Route RAG processing based on need_rag flag"""
    
    def __init__(self):
        routes = [
            {
                "condition": "{{ flags.get('need_rag', False) }}",
                "output": "{{ query }}",
                "output_name": "rag_needed",
                "output_type": str,
            }
        ]
        default_route = "rag_bypass"
        super().__init__(routes=routes, default_route=default_route)

@component
class SkillCheckFlagRouter(ConditionalRouter):
    """Route skill check processing based on need_check flag"""
    
    def __init__(self):
        routes = [
            {
                "condition": "{{ flags.get('need_check', False) }}",
                "output": "{{ action }}",
                "output_name": "skill_needed",
                "output_type": str,
            }
        ]
        default_route = "skill_bypass"
        super().__init__(routes=routes, default_route=default_route)

# === AVOID USING THESE ROUTING COMPONENTS ===
@component
class AdaptiveRAGRouter:
    """Adaptive router that decides RAG necessity based on context analysis"""
    
    @component.output_types(
        rag_needed=Dict[str, Any],
        rag_bypass=Dict[str, Any]
    )
    def run(self, interface_result: dict, context: dict = None) -> Dict[str, Dict[str, Any]]:
        """Intelligently route RAG based on request analysis"""
        
        # Handle both direct dict and nested interface_result structure
        if isinstance(interface_result, dict) and "interface_result" in interface_result:
            request_data = interface_result["interface_result"]
        else:
            request_data = interface_result
        
        # Analyze if RAG is needed based on request content
        player_input = request_data.get("player_input", "").lower()
        
        # Keywords that typically require RAG lookup
        rag_keywords = [
            "what is", "tell me about", "explain", "describe",
            "history", "lore", "background", "rules", "spell",
            "ability", "class", "race", "item", "location"
        ]
        
        needs_rag = any(keyword in player_input for keyword in rag_keywords)
        
        # Check explicit flags
        flags = request_data.get("flags", {})
        needs_rag = needs_rag or flags.get("need_rag", False)
        
        if needs_rag:
            return {"rag_needed": request_data}
        else:
            return {"rag_bypass": request_data}

@component
class AdaptiveSkillRouter:
    """Adaptive router that decides skill check necessity based on action analysis"""
    
    @component.output_types(
        skill_needed=Dict[str, Any],
        skill_bypass=Dict[str, Any]
    )
    def run(self, interface_result: dict) -> Dict[str, Dict[str, Any]]:
        """Intelligently route skill checks based on action analysis"""
        
        # Handle both direct dict and nested interface_result structure
        if isinstance(interface_result, dict) and "interface_result" in interface_result:
            request_data = interface_result["interface_result"]
        else:
            request_data = interface_result
        
        player_input = request_data.get("player_input", "").lower()
        
        # Action keywords that typically require skill checks
        skill_keywords = [
            "roll", "check", "attempt", "try to", "sneak",
            "persuade", "climb", "jump", "search", "investigate",
            "cast", "attack", "dodge", "hide", "listen"
        ]
        
        needs_skill_check = any(keyword in player_input for keyword in skill_keywords)
        
        # Check explicit flags
        flags = request_data.get("flags", {})
        needs_skill_check = needs_skill_check or flags.get("need_check", False)
        
        if needs_skill_check:
            return {"skill_needed": request_data}
        else:
            return {"skill_bypass": request_data}

# === PARALLEL PROCESSING COMPONENTS ===

@component
class ParallelResultsJoiner:
    """
    Variadic merge component for parallel processing results.
    Collect all incoming named inputs and return a single dict
    where each input is preserved under its input name.
    Can handle any number of parallel branches - very flexible!
    """
    
    @component.output_types(parallel_results=Dict[str, Any])
    def run(self,
            rag_agent_result: Optional[Dict[str, Any]] = None,
            rag_bypass_result: Optional[Dict[str, Any]] = None,
            skill_check_result: Optional[Dict[str, Any]] = None,
            skill_bypass_result: Optional[Dict[str, Any]] = None,
            character_context: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, Any]]:
        """Join all parallel results into a single dictionary"""
        # Collect all provided results
        combined_results = {}
        
        if rag_agent_result is not None:
            combined_results["rag_agent_result"] = rag_agent_result
        if rag_bypass_result is not None:
            combined_results["rag_bypass_result"] = rag_bypass_result
        if skill_check_result is not None:
            combined_results["skill_check_result"] = skill_check_result
        if skill_bypass_result is not None:
            combined_results["skill_bypass_result"] = skill_bypass_result
        if character_context is not None:
            combined_results["character_context"] = character_context
            
        return {"parallel_results": combined_results}

# Note: BranchJoiner is for selecting ONE value from multiple branches
# ParallelResultsJoiner is for MERGING multiple values - different use case
def create_branch_selector() -> BranchJoiner:
    """Create native BranchJoiner for selecting one value from multiple branches (not merging)"""
    return BranchJoiner(type_=Dict[str, Any])