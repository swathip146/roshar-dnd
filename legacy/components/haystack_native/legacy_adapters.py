"""
Adapter components to integrate existing game systems as native Haystack components.
Preserves authority-based state management while enabling Haystack pipeline integration.
"""

from haystack import component
from typing import Dict, Any, Optional

@component
class GameEngineAdapter:
    """Adapter for existing GameEngine as Haystack component"""
    
    def __init__(self, game_engine):
        self.game_engine = game_engine
    
    @component.output_types(state_context=Dict[str, Any])
    def run(self, request_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Get comprehensive context from authoritative GameEngine"""
        try:
            # Get all context from the authoritative game engine
            context = {
                "narrative_context": self.game_engine.get_narrative_context(),
                "location_context": self.game_engine.get_location_context(), 
                "quest_context": self.game_engine.get_quest_context(),
                "game_state": self.game_engine.get_game_state(),
                "session_info": getattr(self.game_engine, 'session_id', None)
            }
            return {"state_context": context}
        except Exception as e:
            # Fallback with minimal context
            return {
                "state_context": {
                    "narrative_context": {},
                    "location_context": {},
                    "quest_context": {},
                    "error": f"GameEngine adapter error: {str(e)}"
                }
            }

@component  
class CharacterManagerAdapter:
    """Adapter for existing CharacterManager as Haystack component"""
    
    def __init__(self, character_manager):
        self.character_manager = character_manager
    
    @component.output_types(party_context=Dict[str, Any])  
    def run(self, request_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Get party context from authoritative CharacterManager"""
        try:
            party_context = self.character_manager.get_party_snapshot()
            
            # Enhance with additional character data if available
            enhanced_context = {
                "party_snapshot": party_context,
                "active_character": getattr(self.character_manager, 'active_character', None),
                "party_size": len(party_context.get("characters", [])) if party_context else 0
            }
            
            return {"party_context": enhanced_context}
        except Exception as e:
            # Fallback with empty party context
            return {
                "party_context": {
                    "party_snapshot": {"characters": []},
                    "active_character": None,
                    "party_size": 0,
                    "error": f"CharacterManager adapter error: {str(e)}"
                }
            }

@component
class SkillCheckAdapter:
    """Adapter for existing rules enforcer as Haystack component"""
    
    def __init__(self, game_engine):
        self.rules_enforcer = game_engine.rules_enforcer
        self.game_engine = game_engine
    
    @component.output_types(skill_check_result=Dict[str, Any])
    def run(self, skill_request: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Process skill check through existing 7-step pipeline"""
        try:
            # Use the existing 7-step skill check pipeline
            result = self.game_engine.process_skill_check(skill_request)
            
            # Ensure result has expected structure
            if not isinstance(result, dict):
                result = {"success": False, "error": "Invalid skill check result"}
            
            return {"skill_check_result": result}
        except Exception as e:
            # Fallback skill check result
            return {
                "skill_check_result": {
                    "success": False,
                    "total": 0,
                    "dc": 15,
                    "roll_breakdown": {},
                    "error": f"Skill check error: {str(e)}"
                }
            }

@component
class PolicyEngineAdapter:
    """Adapter for existing PolicyEngine as Haystack component"""
    
    def __init__(self, policy_engine):
        self.policy_engine = policy_engine
    
    @component.output_types(policy_result=Dict[str, Any])
    def run(self, request_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Apply policy checks through existing PolicyEngine"""
        try:
            # Apply policy validation
            if hasattr(self.policy_engine, 'validate_request'):
                is_valid = self.policy_engine.validate_request(request_data)
                return {
                    "policy_result": {
                        "valid": is_valid,
                        "policies_applied": getattr(self.policy_engine, 'last_policies', [])
                    }
                }
            else:
                # Fallback: assume valid if no validation method
                return {"policy_result": {"valid": True, "policies_applied": []}}
        except Exception as e:
            return {
                "policy_result": {
                    "valid": False,
                    "error": f"Policy engine error: {str(e)}"
                }
            }

@component
class BypassComponent:
    """Simple bypass component for optional processing branches"""
    
    @component.output_types(bypass_result=Dict[str, Any])
    def run(self, **kwargs) -> Dict[str, Dict[str, Any]]:
        """Provide empty result for bypassed processing branches"""
        # Return minimal structure for bypassed operations
        return {"bypass_result": {"bypassed": True, "timestamp": self._get_timestamp()}}
    
    def _get_timestamp(self) -> str:
        """Get current timestamp for bypass tracking"""
        from datetime import datetime
        return datetime.now().isoformat()

@component
class RAGBypassComponent(BypassComponent):
    """Specialized bypass for RAG processing"""
    
    @component.output_types(rag_result=Dict[str, Any])
    def run(self, interface_result: Optional[dict] = None, **kwargs) -> Dict[str, Dict[str, Any]]:
        """Provide empty RAG result when RAG is not needed"""
        return {
            "rag_result": {
                "needed": False,
                "query": "",
                "response": "",
                "category": "bypassed",
                "confidence": 0.0,
                "bypassed": True
            }
        }

@component
class SkillCheckBypassComponent(BypassComponent):
    """Specialized bypass for skill check processing"""
    
    @component.output_types(skill_result=Dict[str, Any])
    def run(self, interface_result: Optional[dict] = None, **kwargs) -> Dict[str, Dict[str, Any]]:
        """Provide empty skill check result when skill check is not needed"""
        return {
            "skill_result": {
                "needed": False,
                "success": None,
                "total": None,
                "dc": None,
                "roll_breakdown": {},
                "bypassed": True
            }
        }

@component
class DocumentStoreAdapter:
    """Adapter for existing document store integration"""
    
    def __init__(self, document_store):
        self.document_store = document_store
    
    @component.output_types(document_context=Dict[str, Any])
    def run(self, query: str) -> Dict[str, Dict[str, Any]]:
        """Query document store and return formatted context"""
        try:
            if hasattr(self.document_store, 'search'):
                results = self.document_store.search(query)
                return {
                    "document_context": {
                        "query": query,
                        "results": results,
                        "found": len(results) if results else 0
                    }
                }
            else:
                return {
                    "document_context": {
                        "query": query,
                        "results": [],
                        "found": 0,
                        "error": "Document store search method not available"
                    }
                }
        except Exception as e:
            return {
                "document_context": {
                    "query": query,
                    "results": [],
                    "found": 0,
                    "error": f"Document store error: {str(e)}"
                }
            }

@component
class LegacyComponentWrapper:
    """Generic wrapper for legacy components that don't fit standard patterns"""
    
    def __init__(self, legacy_component, method_name: str = "run", output_key: str = "result"):
        self.legacy_component = legacy_component
        self.method_name = method_name
        self.output_key = output_key
    
    @component.output_types(result=Dict[str, Any])
    def run(self, **kwargs) -> Dict[str, Dict[str, Any]]:
        """Generic wrapper for any legacy component"""
        try:
            method = getattr(self.legacy_component, self.method_name)
            result = method(**kwargs)
            return {self.output_key: result}
        except Exception as e:
            return {
                self.output_key: {
                    "error": f"Legacy component error: {str(e)}",
                    "component": str(self.legacy_component),
                    "method": self.method_name
                }
            }