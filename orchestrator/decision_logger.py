"""
Decision Logger - Stage 3 Week 11-12
Comprehensive decision logging - From Original Plan
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
import time
import json
from pathlib import Path

@dataclass
class SkillCheckDecision:
    """Complete skill check decision record"""
    correlation_id: str
    actor: str
    skill: str
    ability: str
    dc: int
    dc_source: str
    dc_adjustments: List[str]
    roll: int
    raw_rolls: List[int]
    selected_roll: int
    modifiers: Dict[str, int]
    total_modifier: int
    advantage_state: str
    advantage_sources: List[str]
    disadvantage_sources: List[str]
    final_result: bool
    final_total: int
    timestamp: float
    session_context: Dict[str, Any]

@dataclass
class SagaDecision:
    """Saga workflow decision record"""
    saga_id: str
    correlation_id: str
    saga_type: str
    step_number: int
    step_type: str
    handler: str
    input_context: Dict[str, Any]
    output_result: Dict[str, Any]
    step_duration: float
    timestamp: float

@dataclass
class PolicyDecision:
    """Policy engine decision record"""
    correlation_id: str
    decision_type: str  # "advantage", "dc_adjustment", "rule_application"
    input_data: Dict[str, Any]
    policy_rule: str
    rule_value: Any
    final_decision: Any
    reasoning: List[str]
    timestamp: float

class DecisionLogger:
    """
    Comprehensive decision logging - From Original Plan
    Tracks all game decisions with full provenance and audit trail
    """
    
    def __init__(self, log_directory: str = "logs"):
        self.log_directory = Path(log_directory)
        self.log_directory.mkdir(exist_ok=True)
        
        # In-memory decision stores
        self.skill_checks: List[SkillCheckDecision] = []
        self.saga_decisions: List[SagaDecision] = []
        self.policy_decisions: List[PolicyDecision] = []
        self.decision_chains: Dict[str, List[Dict]] = {}
        
        # Session tracking
        self.session_start = time.time()
        self.session_id = str(int(self.session_start))
        
        print(f"📝 Decision Logger initialized - Session: {self.session_id}")
    
    def log_skill_check(self, correlation_id: str, check_data: Dict[str, Any],
                       result: Dict[str, Any]):
        """
        Log skill check with full provenance - From Original Plan
        Step 7 of the 7-step pipeline integration
        """
        # Extract skill check details
        skill_name = check_data.get("skill", "ability_check")
        ability_name = result.get("ability", "unknown")
        
        decision = SkillCheckDecision(
            correlation_id=correlation_id,
            actor=check_data.get("actor", "unknown"),
            skill=skill_name,
            ability=ability_name,
            dc=result.get("dc", 0),
            dc_source=result.get("dc_source", "unknown"),
            dc_adjustments=result.get("dc_adjustments", []),
            roll=result.get("selected_roll", 0),
            raw_rolls=result.get("raw_rolls", []),
            selected_roll=result.get("selected_roll", 0),
            modifiers=result.get("modifiers", {}),
            total_modifier=result.get("character_modifier", 0),
            advantage_state=result.get("advantage_state", "normal"),
            advantage_sources=result.get("advantage_sources", []),
            disadvantage_sources=result.get("disadvantage_sources", []),
            final_result=result.get("success", False),
            final_total=result.get("roll_total", 0),
            timestamp=time.time(),
            session_context=check_data.get("context", {})
        )
        
        self.skill_checks.append(decision)
        self._add_to_chain(correlation_id, "skill_check", asdict(decision))
        
        # Auto-save critical decisions
        if len(self.skill_checks) % 10 == 0:
            self._auto_save_decisions()
    
    def log_saga_step(self, saga_id: str, correlation_id: str, saga_type: str,
                     step_number: int, step_type: str, handler: str,
                     input_context: Dict[str, Any], output_result: Dict[str, Any],
                     step_duration: float):
        """Log saga step execution"""
        decision = SagaDecision(
            saga_id=saga_id,
            correlation_id=correlation_id,
            saga_type=saga_type,
            step_number=step_number,
            step_type=step_type,
            handler=handler,
            input_context=input_context.copy(),
            output_result=output_result.copy(),
            step_duration=step_duration,
            timestamp=time.time()
        )
        
        self.saga_decisions.append(decision)
        self._add_to_chain(correlation_id, "saga_step", asdict(decision))
    
    def log_policy_decision(self, correlation_id: str, decision_type: str,
                           input_data: Dict[str, Any], policy_rule: str,
                           rule_value: Any, final_decision: Any,
                           reasoning: List[str]):
        """Log policy engine decisions"""
        decision = PolicyDecision(
            correlation_id=correlation_id,
            decision_type=decision_type,
            input_data=input_data.copy(),
            policy_rule=policy_rule,
            rule_value=rule_value,
            final_decision=final_decision,
            reasoning=reasoning.copy(),
            timestamp=time.time()
        )
        
        self.policy_decisions.append(decision)
        self._add_to_chain(correlation_id, "policy_decision", asdict(decision))
    
    def post_route_hook(self, request: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Hook for orchestrator integration - From Original Plan
        Automatically logs decisions based on request/result patterns
        """
        correlation_id = request.get("correlation_id", "")
        request_type = request.get("type", "")
        
        if request_type == "skill_check" and correlation_id:
            self.log_skill_check(correlation_id, request, result)
        
        elif request_type.startswith("saga_") and correlation_id:
            # Log saga-related decisions
            self._add_to_chain(correlation_id, "request_result", {
                "request": request,
                "result": result,
                "timestamp": time.time()
            })
        
        return result
    
    def _add_to_chain(self, correlation_id: str, decision_type: str, decision_data: Dict[str, Any]):
        """Add decision to correlation chain"""
        if correlation_id not in self.decision_chains:
            self.decision_chains[correlation_id] = []
        
        self.decision_chains[correlation_id].append({
            "type": decision_type,
            "data": decision_data,
            "sequence": len(self.decision_chains[correlation_id])
        })
    
    def get_decision_chain(self, correlation_id: str) -> List[Dict[str, Any]]:
        """Get complete decision chain for correlation ID"""
        return self.decision_chains.get(correlation_id, [])
    
    def get_skill_check_analysis(self, filter_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Analyze skill check patterns and statistics"""
        checks = self.skill_checks
        
        # Apply filters if provided
        if filter_params:
            if "actor" in filter_params:
                checks = [c for c in checks if c.actor == filter_params["actor"]]
            if "skill" in filter_params:
                checks = [c for c in checks if c.skill == filter_params["skill"]]
            if "since_timestamp" in filter_params:
                checks = [c for c in checks if c.timestamp >= filter_params["since_timestamp"]]
        
        if not checks:
            return {"message": "No skill checks match the filters"}
        
        # Calculate statistics
        total_checks = len(checks)
        successful_checks = len([c for c in checks if c.final_result])
        success_rate = successful_checks / total_checks if total_checks > 0 else 0
        
        # Roll analysis
        all_rolls = [c.selected_roll for c in checks]
        avg_roll = sum(all_rolls) / len(all_rolls) if all_rolls else 0
        
        # Advantage analysis
        advantage_checks = len([c for c in checks if c.advantage_state == "advantage"])
        disadvantage_checks = len([c for c in checks if c.advantage_state == "disadvantage"])
        
        # DC analysis
        dc_distribution = {}
        for check in checks:
            dc = check.dc
            dc_distribution[dc] = dc_distribution.get(dc, 0) + 1
        
        # Skill distribution
        skill_distribution = {}
        skill_success_rates = {}
        for check in checks:
            skill = check.skill
            skill_distribution[skill] = skill_distribution.get(skill, 0) + 1
            
            if skill not in skill_success_rates:
                skill_success_rates[skill] = {"total": 0, "successful": 0}
            
            skill_success_rates[skill]["total"] += 1
            if check.final_result:
                skill_success_rates[skill]["successful"] += 1
        
        # Calculate success rates per skill
        for skill_data in skill_success_rates.values():
            skill_data["rate"] = skill_data["successful"] / skill_data["total"]
        
        return {
            "total_checks": total_checks,
            "successful_checks": successful_checks,
            "success_rate": success_rate,
            "average_roll": avg_roll,
            "advantage_checks": advantage_checks,
            "disadvantage_checks": disadvantage_checks,
            "normal_checks": total_checks - advantage_checks - disadvantage_checks,
            "dc_distribution": dc_distribution,
            "skill_distribution": skill_distribution,
            "skill_success_rates": skill_success_rates,
            "analysis_timestamp": time.time()
        }
    
    def get_saga_analysis(self) -> Dict[str, Any]:
        """Analyze saga execution patterns"""
        if not self.saga_decisions:
            return {"message": "No saga decisions recorded"}
        
        # Group by saga type
        saga_types = {}
        for decision in self.saga_decisions:
            saga_type = decision.saga_type
            if saga_type not in saga_types:
                saga_types[saga_type] = {
                    "count": 0,
                    "total_duration": 0,
                    "steps": {},
                    "success_rate": 0
                }
            
            saga_types[saga_type]["count"] += 1
            saga_types[saga_type]["total_duration"] += decision.step_duration
            
            step_type = decision.step_type
            if step_type not in saga_types[saga_type]["steps"]:
                saga_types[saga_type]["steps"][step_type] = {
                    "count": 0,
                    "avg_duration": 0
                }
            saga_types[saga_type]["steps"][step_type]["count"] += 1
        
        # Calculate averages
        for saga_data in saga_types.values():
            if saga_data["count"] > 0:
                saga_data["avg_duration"] = saga_data["total_duration"] / saga_data["count"]
        
        return {
            "total_saga_steps": len(self.saga_decisions),
            "saga_types": saga_types,
            "analysis_timestamp": time.time()
        }
    
    def export_decisions(self, format: str = "json") -> str:
        """Export all decisions to file"""
        timestamp = int(time.time())
        
        export_data = {
            "session_id": self.session_id,
            "session_start": self.session_start,
            "export_timestamp": time.time(),
            "skill_checks": [asdict(check) for check in self.skill_checks],
            "saga_decisions": [asdict(decision) for decision in self.saga_decisions],
            "policy_decisions": [asdict(decision) for decision in self.policy_decisions],
            "decision_chains": self.decision_chains
        }
        
        if format == "json":
            filename = f"decisions_{self.session_id}_{timestamp}.json"
            filepath = self.log_directory / filename
            
            with open(filepath, 'w') as f:
                json.dump(export_data, f, indent=2)
            
            print(f"📄 Exported decisions to {filepath}")
            return str(filepath)
        
        return ""
    
    def _auto_save_decisions(self):
        """Auto-save decisions periodically"""
        try:
            self.export_decisions()
        except Exception as e:
            print(f"⚠️ Auto-save failed: {e}")
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Get comprehensive session summary"""
        session_duration = time.time() - self.session_start
        
        return {
            "session_id": self.session_id,
            "session_duration": session_duration,
            "session_start": self.session_start,
            "total_skill_checks": len(self.skill_checks),
            "total_saga_steps": len(self.saga_decisions),
            "total_policy_decisions": len(self.policy_decisions),
            "unique_correlations": len(self.decision_chains),
            "skill_check_analysis": self.get_skill_check_analysis(),
            "saga_analysis": self.get_saga_analysis()
        }
    
    def clear_session_data(self, older_than: Optional[float] = None):
        """Clear session data, optionally keeping recent decisions"""
        if older_than is None:
            # Clear all data
            old_count = len(self.skill_checks) + len(self.saga_decisions) + len(self.policy_decisions)
            
            self.skill_checks.clear()
            self.saga_decisions.clear()
            self.policy_decisions.clear()
            self.decision_chains.clear()
            
            print(f"🧹 Cleared all session data ({old_count} decisions)")
        else:
            # Clear data older than specified time
            cutoff_time = time.time() - older_than
            
            old_skill_count = len(self.skill_checks)
            self.skill_checks = [c for c in self.skill_checks if c.timestamp > cutoff_time]
            
            old_saga_count = len(self.saga_decisions)
            self.saga_decisions = [c for c in self.saga_decisions if c.timestamp > cutoff_time]
            
            old_policy_count = len(self.policy_decisions)
            self.policy_decisions = [c for c in self.policy_decisions if c.timestamp > cutoff_time]
            
            # Clean correlation chains
            active_correlations = set()
            for check in self.skill_checks:
                active_correlations.add(check.correlation_id)
            for decision in self.saga_decisions:
                active_correlations.add(decision.correlation_id)
            
            old_chains = len(self.decision_chains)
            self.decision_chains = {
                corr_id: chain for corr_id, chain in self.decision_chains.items()
                if corr_id in active_correlations
            }
            
            total_cleared = (old_skill_count - len(self.skill_checks) +
                           old_saga_count - len(self.saga_decisions) +
                           old_policy_count - len(self.policy_decisions))
            
            print(f"🧹 Cleared {total_cleared} old decisions (kept recent)")


# Factory function for easy integration
def create_decision_logger(log_directory: str = "logs") -> DecisionLogger:
    """Factory function to create configured decision logger"""
    return DecisionLogger(log_directory)


# Example usage for Stage 3 testing
if __name__ == "__main__":
    # Test decision logger functionality
    logger = create_decision_logger()
    
    # Test skill check logging
    test_check_request = {
        "action": "search for clues",
        "actor": "player1",
        "skill": "investigation",
        "context": {"difficulty": "medium"}
    }
    
    test_check_result = {
        "success": True,
        "roll_total": 18,
        "raw_rolls": [15],
        "selected_roll": 15,
        "dc": 15,
        "dc_source": "difficulty_medium",
        "advantage_state": "normal",
        "advantage_sources": [],
        "disadvantage_sources": [],
        "character_modifier": 3
    }
    
    logger.log_skill_check("test-correlation-1", test_check_request, test_check_result)
    
    # Test analysis
    analysis = logger.get_skill_check_analysis()
    print(f"Skill check analysis: {analysis}")
    
    # Test session summary
    summary = logger.get_session_summary()
    print(f"Session summary: {summary}")
    
    # Test export
    export_path = logger.export_decisions()
    print(f"Exported to: {export_path}")