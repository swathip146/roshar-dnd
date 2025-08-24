"""
Phase 5: Decision Logger for Comprehensive Observability
Tracks all routing decisions, RAG triggers, and validation outcomes
"""

import json
import time
import uuid
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class DecisionLogEntry:
    """Single decision log entry"""
    timestamp: float
    correlation_id: str
    phase: str
    component: str
    decision_type: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    confidence: float
    reasoning: str
    duration_ms: float
    success: bool
    errors: List[str]


class DecisionLogger:
    """
    Comprehensive decision logger for observability
    Tracks all major decisions through the pipeline
    """
    
    def __init__(self):
        self.entries: List[DecisionLogEntry] = []
        self.session_id = str(uuid.uuid4())
        self.start_time = time.time()
    
    def log_decision(self,
                    correlation_id: str,
                    phase: str,
                    component: str, 
                    decision_type: str,
                    input_data: Dict[str, Any],
                    output_data: Dict[str, Any],
                    confidence: float = 1.0,
                    reasoning: str = "",
                    duration_ms: float = 0.0,
                    success: bool = True,
                    errors: List[str] = None) -> None:
        """Log a decision with full context"""
        
        entry = DecisionLogEntry(
            timestamp=time.time(),
            correlation_id=correlation_id,
            phase=phase,
            component=component,
            decision_type=decision_type,
            input_data=input_data,
            output_data=output_data,
            confidence=confidence,
            reasoning=reasoning,
            duration_ms=duration_ms,
            success=success,
            errors=errors or []
        )
        
        self.entries.append(entry)
    
    def log_routing_decision(self, correlation_id: str, dto: Dict[str, Any], route: str, confidence: float, reasoning: str):
        """Log Phase 2 routing decision"""
        self.log_decision(
            correlation_id=correlation_id,
            phase="phase_2_routing",
            component="routing_decision_maker",
            decision_type="route_selection",
            input_data={"player_input": dto.get("player_input"), "action": dto.get("action")},
            output_data={"route": route, "confidence": confidence},
            confidence=confidence,
            reasoning=reasoning
        )
    
    def log_rag_decision(self, correlation_id: str, dto: Dict[str, Any], rag_needed: bool, triggers: List[str]):
        """Log Phase 1 RAG gating decision"""
        self.log_decision(
            correlation_id=correlation_id,
            phase="phase_1_rag_gating", 
            component="rag_gatekeeper",
            decision_type="rag_trigger_assessment",
            input_data={"player_input": dto.get("player_input"), "context": dto.get("context")},
            output_data={"rag_needed": rag_needed, "triggers": triggers},
            confidence=1.0 if triggers else 0.5,
            reasoning=f"Triggers detected: {triggers}" if triggers else "No RAG triggers found"
        )
    
    def log_validation_result(self, correlation_id: str, scenario: Dict[str, Any], errors: List[str], repaired: bool):
        """Log Phase 3 schema validation result"""
        self.log_decision(
            correlation_id=correlation_id,
            phase="phase_3_validation",
            component="schema_validator",
            decision_type="schema_validation",
            input_data={"scenario_keys": list(scenario.keys()) if scenario else []},
            output_data={"errors": errors, "repaired": repaired, "valid": len(errors) == 0},
            confidence=1.0 if len(errors) == 0 else 0.5,
            reasoning=f"Validation errors: {errors}" if errors else "Schema validation passed",
            success=len(errors) == 0
        )
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Get summary of current session"""
        total_decisions = len(self.entries)
        successful_decisions = sum(1 for e in self.entries if e.success)
        
        # Group by phase
        phase_stats = {}
        for entry in self.entries:
            phase = entry.phase
            if phase not in phase_stats:
                phase_stats[phase] = {"count": 0, "success": 0, "avg_confidence": 0.0}
            
            phase_stats[phase]["count"] += 1
            if entry.success:
                phase_stats[phase]["success"] += 1
            phase_stats[phase]["avg_confidence"] += entry.confidence
        
        # Calculate averages
        for phase in phase_stats:
            stats = phase_stats[phase]
            stats["success_rate"] = stats["success"] / stats["count"] if stats["count"] > 0 else 0
            stats["avg_confidence"] = stats["avg_confidence"] / stats["count"] if stats["count"] > 0 else 0
        
        return {
            "session_id": self.session_id,
            "duration_seconds": time.time() - self.start_time,
            "total_decisions": total_decisions,
            "successful_decisions": successful_decisions,
            "overall_success_rate": successful_decisions / total_decisions if total_decisions > 0 else 0,
            "phase_statistics": phase_stats,
            "latest_entries": [asdict(e) for e in self.entries[-5:]]  # Last 5 entries
        }
    
    def get_decision_trace(self, correlation_id: str) -> List[DecisionLogEntry]:
        """Get all decisions for a specific request correlation ID"""
        return [entry for entry in self.entries if entry.correlation_id == correlation_id]
    
    def export_logs(self, filepath: str = None) -> str:
        """Export logs to JSON file"""
        if not filepath:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"decision_logs_{timestamp}.json"
        
        export_data = {
            "session_summary": self.get_session_summary(),
            "all_entries": [asdict(entry) for entry in self.entries]
        }
        
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        return filepath
    
    def clear_logs(self):
        """Clear all logged entries"""
        self.entries.clear()


# Global logger instance
_global_logger = DecisionLogger()

def get_decision_logger() -> DecisionLogger:
    """Get the global decision logger instance"""
    return _global_logger

def log_routing_decision(correlation_id: str, dto: Dict[str, Any], route: str, confidence: float, reasoning: str):
    """Convenience function for logging routing decisions"""
    _global_logger.log_routing_decision(correlation_id, dto, route, confidence, reasoning)

def log_rag_decision(correlation_id: str, dto: Dict[str, Any], rag_needed: bool, triggers: List[str]):
    """Convenience function for logging RAG decisions"""
    _global_logger.log_rag_decision(correlation_id, dto, rag_needed, triggers)

def log_validation_result(correlation_id: str, scenario: Dict[str, Any], errors: List[str], repaired: bool):
    """Convenience function for logging validation results"""
    _global_logger.log_validation_result(correlation_id, scenario, errors, repaired)


# Example usage and testing
if __name__ == "__main__":
    logger = DecisionLogger()
    
    # Simulate some decisions
    test_correlation_id = str(uuid.uuid4())
    
    # Simulate routing decision
    test_dto = {"player_input": "I examine the artifact", "context": {}}
    logger.log_routing_decision(test_correlation_id, test_dto, "scenario", 0.8, "Action-based scenario request")
    
    # Simulate RAG decision  
    logger.log_rag_decision(test_correlation_id, test_dto, True, ["artifact", "ancient"])
    
    # Simulate validation
    test_scenario = {"scene": "test", "choices": [], "effects": {}, "hooks": []}
    logger.log_validation_result(test_correlation_id, test_scenario, [], False)
    
    # Show results
    print("=== Decision Logger Test ===")
    summary = logger.get_session_summary()
    print(f"Total decisions: {summary['total_decisions']}")
    print(f"Success rate: {summary['overall_success_rate']:.2%}")
    
    print("\n=== Decision Trace ===")
    trace = logger.get_decision_trace(test_correlation_id)
    for entry in trace:
        print(f"{entry.phase}: {entry.decision_type} -> {entry.reasoning}")
    
    # Export logs
    filepath = logger.export_logs()
    print(f"\n✅ Logs exported to: {filepath}")