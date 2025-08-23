"""
Saga Manager - Stage 3 Week 9-10
Multi-step flow tracking with correlation IDs - From Original Plan
"""

from typing import Dict, List, Any, Optional
import uuid
import time
from dataclasses import dataclass
from enum import Enum

class SagaStatus(Enum):
    ACTIVE = "active"
    COMPLETED = "completed" 
    FAILED = "failed"
    COMPENSATING = "compensating"

@dataclass
class SagaStep:
    """Individual step in a multi-step saga workflow"""
    step_type: str
    handler: str
    timeout: float = 30.0
    retry_count: int = 0
    max_retries: int = 3
    compensation_handler: Optional[str] = None

@dataclass  
class Saga:
    """Multi-step saga with correlation tracking"""
    id: str
    type: str
    current_step: int
    steps: List[SagaStep]
    context: Dict[str, Any]
    correlation_id: str
    start_time: float
    status: SagaStatus = SagaStatus.ACTIVE
    error_message: Optional[str] = None

class SagaManager:
    """
    Multi-step flow tracking with correlation IDs - From Original Plan
    Handles complex D&D interactions that span multiple steps
    """
    
    def __init__(self):
        self.active_sagas: Dict[str, Saga] = {}
        self.completed_sagas: List[Saga] = []
        self.failed_sagas: List[Saga] = []
        
        # Saga templates for different D&D interaction types
        self.saga_templates = {
            "skill_challenge": self._build_skill_challenge_saga,
            "combat_encounter": self._build_combat_saga,
            "social_encounter": self._build_social_saga,
            "exploration": self._build_exploration_saga,
            "rest_sequence": self._build_rest_saga
        }
    
    def start_saga(self, saga_type: str, context: Dict[str, Any]) -> str:
        """Start multi-step saga with correlation tracking"""
        if saga_type not in self.saga_templates:
            raise ValueError(f"Unknown saga type: {saga_type}")
        
        saga_id = str(uuid.uuid4())
        correlation_id = str(uuid.uuid4())
        
        saga = Saga(
            id=saga_id,
            type=saga_type,
            current_step=0,
            steps=self.saga_templates[saga_type](context),
            context=context,
            correlation_id=correlation_id,
            start_time=time.time()
        )
        
        self.active_sagas[saga_id] = saga
        
        print(f"🎯 Started {saga_type} saga: {saga_id}")
        return saga_id
    
    def advance_saga(self, saga_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """Advance saga to next step based on current step result"""
        if saga_id not in self.active_sagas:
            return {"error": f"Saga {saga_id} not found or not active"}
        
        saga = self.active_sagas[saga_id]
        
        # Store step result in context
        step_key = f"step_{saga.current_step}_result"
        saga.context[step_key] = result
        
        # Move to next step
        saga.current_step += 1
        
        # Check if saga is complete
        if saga.current_step >= len(saga.steps):
            return self._complete_saga(saga_id, "success")
        
        # Get next step info
        next_step = saga.steps[saga.current_step]
        
        return {
            "saga_id": saga_id,
            "correlation_id": saga.correlation_id,
            "next_step": next_step.step_type,
            "handler": next_step.handler,
            "context": saga.context,
            "step_number": saga.current_step + 1,
            "total_steps": len(saga.steps)
        }
    
    def _complete_saga(self, saga_id: str, outcome: str) -> Dict[str, Any]:
        """Complete a saga and move it to appropriate storage"""
        saga = self.active_sagas.pop(saga_id)
        
        if outcome == "success":
            saga.status = SagaStatus.COMPLETED
            self.completed_sagas.append(saga)
            print(f"✅ Completed saga: {saga.type} ({saga_id})")
        else:
            saga.status = SagaStatus.FAILED
            saga.error_message = outcome
            self.failed_sagas.append(saga)
            print(f"❌ Failed saga: {saga.type} ({saga_id}) - {outcome}")
        
        return {
            "saga_id": saga_id,
            "status": saga.status.value,
            "completion_time": time.time(),
            "duration": time.time() - saga.start_time,
            "context": saga.context
        }
    
    def get_saga_status(self, saga_id: str) -> Dict[str, Any]:
        """Get current status of a saga"""
        if saga_id in self.active_sagas:
            saga = self.active_sagas[saga_id]
            return {
                "saga_id": saga_id,
                "status": saga.status.value,
                "type": saga.type,
                "current_step": saga.current_step,
                "total_steps": len(saga.steps),
                "correlation_id": saga.correlation_id
            }
        
        # Check completed/failed sagas
        all_finished = self.completed_sagas + self.failed_sagas
        for saga in all_finished:
            if saga.id == saga_id:
                return {
                    "saga_id": saga_id,
                    "status": saga.status.value,
                    "type": saga.type,
                    "error": saga.error_message
                }
        
        return {"error": f"Saga {saga_id} not found"}
    
    def pre_route_hook(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Hook for orchestrator integration - detects multi-step requests
        This is called by the orchestrator before routing requests
        """
        if self._is_multi_step_request(request):
            saga_type = self._determine_saga_type(request)
            saga_id = self.start_saga(saga_type, request)
            request["saga_id"] = saga_id
            
            # Get first step info
            saga = self.active_sagas[saga_id]
            first_step = saga.steps[0]
            request["correlation_id"] = saga.correlation_id
            request["step_type"] = first_step.step_type
            request["handler"] = first_step.handler
        
        return request
    
    def _is_multi_step_request(self, request: Dict[str, Any]) -> bool:
        """Determine if a request requires multi-step saga processing"""
        # Check for explicit saga type
        if request.get("saga_type"):
            return True
        
        # Check request patterns that indicate multi-step flows
        request_type = request.get("type", "")
        multi_step_patterns = [
            "skill_challenge",
            "combat_start",
            "social_encounter",
            "exploration_start",
            "rest_attempt"
        ]
        
        return request_type in multi_step_patterns
    
    def _determine_saga_type(self, request: Dict[str, Any]) -> str:
        """Determine appropriate saga type from request"""
        if request.get("saga_type"):
            return request["saga_type"]
        
        request_type = request.get("type", "")
        type_mapping = {
            "skill_challenge": "skill_challenge",
            "combat_start": "combat_encounter", 
            "social_encounter": "social_encounter",
            "exploration_start": "exploration",
            "rest_attempt": "rest_sequence"
        }
        
        return type_mapping.get(request_type, "skill_challenge")
    
    # Saga Template Builders - Define multi-step workflows
    
    def _build_skill_challenge_saga(self, context: Dict[str, Any]) -> List[SagaStep]:
        """Multi-step skill challenge workflow"""
        return [
            SagaStep("present_scenario", "scenario_generator"),
            SagaStep("player_choice", "interface"),
            SagaStep("skill_check", "game_engine"),
            SagaStep("generate_consequence", "scenario_generator")
        ]
    
    def _build_combat_saga(self, context: Dict[str, Any]) -> List[SagaStep]:
        """Combat encounter workflow"""
        return [
            SagaStep("initialize_combat", "combat_engine"),
            SagaStep("roll_initiative", "combat_engine"),
            SagaStep("combat_turn_loop", "combat_engine"),
            SagaStep("end_combat", "combat_engine"),
            SagaStep("award_xp", "xp_manager"),
            SagaStep("distribute_loot", "inventory_manager")
        ]
    
    def _build_social_saga(self, context: Dict[str, Any]) -> List[SagaStep]:
        """Social encounter workflow"""
        return [
            SagaStep("npc_introduction", "npc_agent"),
            SagaStep("dialogue_exchange", "npc_agent"),
            SagaStep("relationship_check", "npc_agent"),
            SagaStep("consequence_generation", "scenario_generator")
        ]
    
    def _build_exploration_saga(self, context: Dict[str, Any]) -> List[SagaStep]:
        """Exploration sequence workflow"""
        return [
            SagaStep("area_description", "scenario_generator"),
            SagaStep("perception_checks", "game_engine"),
            SagaStep("discovery_resolution", "scenario_generator"),
            SagaStep("next_area_options", "scenario_generator")
        ]
    
    def _build_rest_saga(self, context: Dict[str, Any]) -> List[SagaStep]:
        """Rest sequence workflow"""
        return [
            SagaStep("rest_validation", "game_engine"),
            SagaStep("recovery_calculation", "character_manager"),
            SagaStep("spell_slot_recovery", "spell_manager"),
            SagaStep("rest_interruption_check", "scenario_generator")
        ]
    
    def get_active_sagas(self) -> List[Dict[str, Any]]:
        """Get list of currently active sagas"""
        return [
            {
                "saga_id": saga.id,
                "type": saga.type,
                "current_step": saga.current_step,
                "total_steps": len(saga.steps),
                "correlation_id": saga.correlation_id,
                "duration": time.time() - saga.start_time
            }
            for saga in self.active_sagas.values()
        ]
    
    def get_saga_stats(self) -> Dict[str, Any]:
        """Get saga manager statistics"""
        return {
            "active_sagas": len(self.active_sagas),
            "completed_sagas": len(self.completed_sagas),
            "failed_sagas": len(self.failed_sagas),
            "total_sagas": len(self.active_sagas) + len(self.completed_sagas) + len(self.failed_sagas),
            "available_saga_types": list(self.saga_templates.keys())
        }


# Factory function for easy integration
def create_saga_manager() -> SagaManager:
    """Factory function to create configured saga manager"""
    return SagaManager()


# Example usage for Stage 3 testing
if __name__ == "__main__":
    # Test basic saga functionality
    manager = create_saga_manager()
    
    # Start a skill challenge saga
    saga_id = manager.start_saga("skill_challenge", {
        "difficulty": "medium",
        "skill": "investigation",
        "context": "searching ancient library"
    })
    
    print(f"Started saga: {saga_id}")
    print(f"Stats: {manager.get_saga_stats()}")
    
    # Simulate advancing through steps
    result = manager.advance_saga(saga_id, {"scenario": "generated"})
    print(f"Advanced: {result}")