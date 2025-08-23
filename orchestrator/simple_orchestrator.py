"""
Enhanced Orchestrator - Stage 3 Integration
Integrates Saga Manager, Policy Engine, 7-Step Pipeline, and Decision Logging
Maintains backward compatibility with Stage 2
"""

from typing import Dict, Any, List, Callable, Optional
from dataclasses import dataclass
import logging
import sys
import os

# Add components to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from components.policy import PolicyEngine, PolicyProfile
from components.game_engine import GameEngine
from .saga_manager import SagaManager
from .decision_logger import DecisionLogger


@dataclass
class GameRequest:
    """Enhanced request structure for game operations"""
    request_type: str  # 'scenario', 'skill_check', 'saga_start', etc.
    data: Dict[str, Any]
    context: Optional[Dict[str, Any]] = None
    correlation_id: Optional[str] = None
    saga_id: Optional[str] = None


@dataclass
class GameResponse:
    """Enhanced response structure with Stage 3 metadata"""
    success: bool
    data: Dict[str, Any]
    request_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    correlation_id: Optional[str] = None
    saga_id: Optional[str] = None


class SimpleOrchestrator:
    """
    Enhanced orchestrator integrating all Stage 3 components
    Maintains backward compatibility while adding sophisticated features
    """
    
    def __init__(self, policy_profile: PolicyProfile = PolicyProfile.RAW,
                 enable_stage3: bool = True):
        self.logger = logging.getLogger(__name__)
        self.enable_stage3 = enable_stage3
        
        # Stage 3 components (optional for backward compatibility)
        if enable_stage3:
            self.policy_engine = PolicyEngine(policy_profile)
            self.game_engine = GameEngine(policy_profile)
            self.saga_manager = SagaManager()
            self.decision_logger = DecisionLogger()
            
            # Connect decision logger to game engine
            self.game_engine.set_decision_logger(self.decision_logger)
            
            print(f"🎯 Enhanced Orchestrator initialized with Stage 3 components")
        else:
            self.policy_engine = None
            self.game_engine = None
            self.saga_manager = None
            self.decision_logger = None
            
            print("🎯 Simple Orchestrator initialized (Stage 2 compatibility mode)")
        
        # Extension points (now populated with Stage 3 components)
        self.pre_hooks: List[Callable[[Dict[str, Any]], Dict[str, Any]]] = []
        self.post_hooks: List[Callable[[Dict[str, Any]], Dict[str, Any]]] = []
        
        # Enhanced routing table
        self.handlers: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {}
        
        # Initialize handlers (Stage 2 + Stage 3)
        self._register_default_handlers()
        
        # Register Stage 3 hooks if enabled
        if enable_stage3:
            self._register_stage3_hooks()
    
    def _register_default_handlers(self):
        """Register default request handlers (Stage 2 + Stage 3)"""
        # Stage 2 handlers (backward compatibility)
        self.handlers.update({
            'scenario': self._handle_scenario_request,
            'dice_roll': self._handle_dice_request,
            'game_state': self._handle_state_request,
        })
        
        # Stage 3 enhanced handlers
        if self.enable_stage3:
            self.handlers.update({
                'skill_check': self._handle_skill_check_request,
                'character_add': self._handle_character_add,
                'character_update': self._handle_character_update,
                'saga_start': self._handle_saga_start,
                'saga_advance': self._handle_saga_advance,
                'policy_change': self._handle_policy_change,
                'contested_check': self._handle_contested_check,
                'game_statistics': self._handle_game_statistics
            })
    
    def _register_stage3_hooks(self):
        """Register Stage 3 hooks for saga and decision logging"""
        # Saga manager pre-hook
        self.pre_hooks.append(self.saga_manager.pre_route_hook)
        
        # Decision logger post-hook
        self.post_hooks.append(self.decision_logger.post_route_hook)
    
    def register_handler(self, request_type: str, handler: Callable[[Dict[str, Any]], Dict[str, Any]]):
        """Register a new request handler - extensibility for Stage 3+"""
        self.handlers[request_type] = handler
        self.logger.info(f"Registered handler for request type: {request_type}")
    
    def add_pre_hook(self, hook: Callable[[Dict[str, Any]], Dict[str, Any]]):
        """Add pre-processing hook - for Stage 3 saga manager"""
        self.pre_hooks.append(hook)
        self.logger.info("Added pre-processing hook")
    
    def add_post_hook(self, hook: Callable[[Dict[str, Any]], Dict[str, Any]]):
        """Add post-processing hook - for Stage 3 decision logging"""
        self.post_hooks.append(hook)
        self.logger.info("Added post-processing hook")
    
    def process_request(self, request) -> GameResponse:
        """
        Enhanced orchestration method with Stage 3 integration
        Maintains backward compatibility with Stage 2 format
        Handles both GameRequest objects and dictionary requests
        """
        request_type = "unknown"  # Initialize to avoid UnboundLocalError
        
        try:
            # Convert GameRequest objects to dictionaries before any processing
            if isinstance(request, GameRequest):
                # GameRequest object - convert to dictionary for processing
                processed_request = {
                    "type": request.request_type,
                    "request_type": request.request_type,
                    "data": request.data,
                    "context": request.context,
                    "correlation_id": request.correlation_id,
                    "saga_id": request.saga_id
                }
            else:
                # Dictionary request - copy for processing
                processed_request = request.copy()
            
            # Pre-processing hooks (Stage 3: saga context injection)
            for hook in self.pre_hooks:
                processed_request = hook(processed_request)
            
            # Route to appropriate handler
            request_type = processed_request.get("type", processed_request.get("request_type", ""))
            handler = self.handlers.get(request_type)
            if not handler:
                return GameResponse(
                    success=False,
                    data={"error": f"Unknown request type: {request_type}"},
                    correlation_id=processed_request.get("correlation_id")
                )
            
            # Execute handler
            response_dict = handler(processed_request)
            
            # Ensure response has correlation_id
            if "correlation_id" in processed_request:
                response_dict["correlation_id"] = processed_request["correlation_id"]
            
            # Post-processing hooks (Stage 3: decision logging, state updates)
            processed_response = response_dict
            for hook in self.post_hooks:
                processed_response = hook(processed_request, processed_response)
            
            # Convert dict response to GameResponse object
            return GameResponse(
                success=processed_response.get("success", True),
                data=processed_response.get("data", processed_response),
                correlation_id=processed_response.get("correlation_id"),
                metadata=processed_response.get("metadata")
            )
            
        except Exception as e:
            self.logger.error(f"Error processing request: {e}")
            # Get correlation_id safely from either object type
            correlation_id = None
            if isinstance(request, GameRequest):
                correlation_id = request.correlation_id
            elif isinstance(request, dict):
                correlation_id = request.get("correlation_id")
            
            return GameResponse(
                success=False,
                data={"error": str(e), "request_type": request_type},
                correlation_id=correlation_id
            )
    
    # Stage 2 handlers (backward compatibility)
    
    def _handle_scenario_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle scenario generation requests (Stage 2 compatibility)"""
        return {
            "success": True,
            "data": {
                "message": "Scenario request received - integrate with RAGScenarioGenerator",
                "request_data": request.get("data", request)
            }
        }
    
    def _handle_dice_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle dice rolling requests (Stage 2 compatibility)"""
        return {
            "success": True,
            "data": {
                "message": "Dice request received - integrate with DiceRoller", 
                "request_data": request.get("data", request)
            }
        }
    
    def _handle_state_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle game state requests (Stage 2 compatibility)"""
        if self.enable_stage3:
            # Stage 3: Return actual game state
            stats = self.game_engine.get_game_statistics()
            return {
                "success": True,
                "data": {
                    "message": "Game state retrieved",
                    "game_statistics": stats,
                    "session_summary": self.decision_logger.get_session_summary() if self.decision_logger else {}
                }
            }
        else:
            # Stage 2: Simple passthrough
            return {
                "success": True,
                "data": {
                    "message": "State request received - Stage 3+ persistent state",
                    "request_data": request.get("data", request)
                }
            }
    
    # Stage 3 enhanced handlers
    
    def _handle_skill_check_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle skill check through 7-step pipeline"""
        if not self.enable_stage3:
            return {"success": False, "data": {"error": "Stage 3 required for skill checks"}}
        
        try:
            result = self.game_engine.process_skill_check(request)
            return {
                "success": True,
                "data": {
                    "skill_check_result": result,
                    "pipeline": "7-step_deterministic"
                }
            }
        except Exception as e:
            return {
                "success": False,
                "data": {"error": f"Skill check failed: {e}"}
            }
    
    def _handle_character_add(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Add character to game"""
        if not self.enable_stage3:
            return {"success": False, "data": {"error": "Stage 3 required for character management"}}
        
        character_data = request.get("character_data", {})
        char_id = self.game_engine.add_character(character_data)
        
        return {
            "success": True,
            "data": {
                "character_id": char_id,
                "message": f"Added character: {character_data.get('name', char_id)}"
            }
        }
    
    def _handle_character_update(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Update character condition or state"""
        if not self.enable_stage3:
            return {"success": False, "data": {"error": "Stage 3 required for character management"}}
        
        char_id = request.get("character_id")
        condition = request.get("condition")
        active = request.get("active", True)
        
        success = self.game_engine.set_character_condition(char_id, condition, active)
        
        return {
            "success": success,
            "data": {
                "character_id": char_id,
                "condition": condition,
                "active": active,
                "message": f"{'Added' if active else 'Removed'} condition '{condition}'"
            }
        }
    
    def _handle_saga_start(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Start a new saga workflow"""
        if not self.enable_stage3:
            return {"success": False, "data": {"error": "Stage 3 required for saga management"}}
        
        saga_type = request.get("saga_type", "skill_challenge")
        context = request.get("context", {})
        
        saga_id = self.saga_manager.start_saga(saga_type, context)
        
        return {
            "success": True,
            "data": {
                "saga_id": saga_id,
                "saga_type": saga_type,
                "message": f"Started {saga_type} saga"
            }
        }
    
    def _handle_saga_advance(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Advance saga to next step"""
        if not self.enable_stage3:
            return {"success": False, "data": {"error": "Stage 3 required for saga management"}}
        
        saga_id = request.get("saga_id")
        step_result = request.get("step_result", {})
        
        result = self.saga_manager.advance_saga(saga_id, step_result)
        
        return {
            "success": True,
            "data": {
                "saga_advance_result": result,
                "message": "Saga advanced"
            }
        }
    
    def _handle_policy_change(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Change policy profile or rules"""
        if not self.enable_stage3:
            return {"success": False, "data": {"error": "Stage 3 required for policy management"}}
        
        if "profile" in request:
            from components.policy import PolicyProfile
            profile = PolicyProfile(request["profile"])
            self.policy_engine.change_profile(profile)
            
            return {
                "success": True,
                "data": {
                    "new_profile": profile.value,
                    "message": f"Changed to {profile.value} profile"
                }
            }
        
        if "custom_rule" in request:
            rule_name = request["rule_name"]
            rule_value = request["rule_value"]
            description = request.get("description", "Custom rule")
            
            self.policy_engine.set_custom_rule(rule_name, rule_value, description)
            
            return {
                "success": True,
                "data": {
                    "rule_name": rule_name,
                    "rule_value": rule_value,
                    "message": f"Set custom rule: {rule_name}"
                }
            }
        
        return {"success": False, "data": {"error": "No valid policy change specified"}}
    
    def _handle_contested_check(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle contested check between actors"""
        if not self.enable_stage3:
            return {"success": False, "data": {"error": "Stage 3 required for contested checks"}}
        
        actor1 = request.get("actor1")
        skill1 = request.get("skill1")
        actor2 = request.get("actor2")
        skill2 = request.get("skill2")
        context = request.get("context", {})
        
        result = self.game_engine.process_contested_check(actor1, skill1, actor2, skill2, context)
        
        return {
            "success": True,
            "data": {
                "contested_result": result,
                "message": f"Contested check: {skill1} vs {skill2}"
            }
        }
    
    def _handle_game_statistics(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Get comprehensive game statistics"""
        if not self.enable_stage3:
            return {"success": False, "data": {"error": "Stage 3 required for statistics"}}
        
        stats = self.game_engine.get_game_statistics()
        session_summary = self.decision_logger.get_session_summary()
        saga_stats = self.saga_manager.get_saga_stats()
        policy_info = self.policy_engine.get_profile_info()
        
        return {
            "success": True,
            "data": {
                "game_statistics": stats,
                "session_summary": session_summary,
                "saga_statistics": saga_stats,
                "policy_info": policy_info,
                "message": "Comprehensive statistics retrieved"
            }
        }
    
    def get_available_handlers(self) -> List[str]:
        """Get list of available request types"""
        return list(self.handlers.keys())
    
    def get_orchestrator_status(self) -> Dict[str, Any]:
        """Get comprehensive orchestrator status"""
        status = {
            "stage3_enabled": self.enable_stage3,
            "available_handlers": self.get_available_handlers(),
            "pre_hooks": len(self.pre_hooks),
            "post_hooks": len(self.post_hooks)
        }
        
        if self.enable_stage3:
            status.update({
                "policy_profile": self.policy_engine.active_profile_type.value,
                "active_sagas": len(self.saga_manager.active_sagas),
                "decision_logger_session": self.decision_logger.session_id,
                "game_characters": len(self.game_engine.game_state.characters)
            })
        
        return status
    
    def export_session_data(self) -> Dict[str, Any]:
        """Export complete session data for analysis"""
        if not self.enable_stage3:
            return {"error": "Stage 3 required for session export"}
        
        return {
            "orchestrator_status": self.get_orchestrator_status(),
            "game_state_export": self.game_engine.export_game_state(),
            "decision_summary": self.decision_logger.get_session_summary(),
            "saga_statistics": self.saga_manager.get_saga_stats(),
            "policy_info": self.policy_engine.get_profile_info()
        }


# Factory functions for different configurations

def create_orchestrator(enable_stage3: bool = True, 
                       policy_profile: PolicyProfile = PolicyProfile.RAW) -> SimpleOrchestrator:
    """Factory function to create configured orchestrator"""
    return SimpleOrchestrator(policy_profile, enable_stage3)

def create_stage2_orchestrator() -> SimpleOrchestrator:
    """Create Stage 2 compatible orchestrator (backward compatibility)"""
    return SimpleOrchestrator(enable_stage3=False)

def create_stage3_orchestrator(policy_profile: PolicyProfile = PolicyProfile.RAW) -> SimpleOrchestrator:
    """Create full Stage 3 orchestrator with all components"""
    return SimpleOrchestrator(policy_profile, enable_stage3=True)

def create_house_rules_orchestrator() -> SimpleOrchestrator:
    """Create orchestrator with house rules policy"""
    return SimpleOrchestrator(PolicyProfile.HOUSE, enable_stage3=True)

def create_beginner_orchestrator() -> SimpleOrchestrator:
    """Create beginner-friendly orchestrator"""
    return SimpleOrchestrator(PolicyProfile.EASY, enable_stage3=True)


# Example usage for Stage 3 testing
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("=== Stage 3 Orchestrator Demo ===")
    
    # Create Stage 3 orchestrator
    orchestrator = create_stage3_orchestrator(PolicyProfile.HOUSE)
    
    # Add a test character
    character_request = {
        "type": "character_add",
        "character_data": {
            "character_id": "test_hero",
            "name": "Test Hero",
            "level": 3,
            "ability_scores": {
                "strength": 14,
                "dexterity": 16,
                "constitution": 13,
                "intelligence": 12,
                "wisdom": 15,
                "charisma": 10
            },
            "skills": {
                "stealth": True,
                "perception": True
            },
            "expertise_skills": ["stealth"]
        }
    }
    
    char_response = orchestrator.process_request(character_request)
    print(f"Character added: {char_response}")
    
    # Test skill check with 7-step pipeline
    skill_request = {
        "type": "skill_check",
        "action": "sneak past guards",
        "actor": "test_hero",
        "skill": "stealth",
        "context": {
            "difficulty": "medium",
            "environment": {"lighting": "dim"}
        }
    }
    
    skill_response = orchestrator.process_request(skill_request)
    print(f"Skill check result: {skill_response}")
    
    # Test saga workflow
    saga_request = {
        "type": "saga_start",
        "saga_type": "skill_challenge",
        "context": {
            "challenge_type": "infiltration",
            "difficulty": "medium"
        }
    }
    
    saga_response = orchestrator.process_request(saga_request)
    print(f"Saga started: {saga_response}")
    
    # Show orchestrator status
    status = orchestrator.get_orchestrator_status()
    print(f"Orchestrator status: {status}")
    
    # Test backward compatibility with Stage 2 format
    print("\n=== Backward Compatibility Test ===")
    
    stage2_request = {
        "type": "scenario",
        "data": {"theme": "dungeon", "difficulty": "medium"}
    }
    
    stage2_response = orchestrator.process_request(stage2_request)
    print(f"Stage 2 compatibility: {stage2_response}")
    
    print("\n=== Stage 2 Only Mode ===")
    
    # Test Stage 2 only mode
    stage2_orchestrator = create_stage2_orchestrator()
    stage2_only_response = stage2_orchestrator.process_request(stage2_request)
    print(f"Stage 2 only response: {stage2_only_response}")
    
    print(f"Available handlers: {orchestrator.get_available_handlers()}")