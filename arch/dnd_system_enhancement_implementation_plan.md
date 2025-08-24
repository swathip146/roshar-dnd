# D&D System Enhancement Implementation Plan
*Based on analysis of current architecture vs revised Haystack plan*

## Executive Summary

The current modular DM assistant already has a **sophisticated foundation** that closely aligns with the revised plan. This is an **enhancement project** focused on:
- Adding missing key components (Policy Engine, enhanced Saga Manager)
- Standardizing agent contracts and responses
- Improving determinism and observability
- Adding comprehensive testing infrastructure

**Key Finding**: The existing architecture is well-designed and requires targeted enhancements rather than a complete rewrite.

---

## Current Architecture Strengths

### ✅ Already Implemented (Strong Foundation)
- **Agent Framework**: Sophisticated message-based system with orchestrator
- **Agents vs Components Separation**: ScenarioGeneratorAgent, HaystackPipelineAgent (creative) vs DiceRoller, CombatEngine (deterministic)
- **Orchestrator**: Message bus, event handling, agent lifecycle management
- **RAG Integration**: Advanced Haystack pipelines with Qdrant vector store
- **Deterministic Systems**: Combat engine with structured outcomes, dice system with logging
- **Command Processing**: Comprehensive manual command handler (126+ commands)
- **Game State Management**: JSON persistence, checkpoint system
- **Modular Design**: Clean separation of concerns, pluggable components

### 🔧 Partially Implemented (Needs Enhancement)
- **Decision Logging**: Combat has basic logging, needs comprehensive provenance
- **Context Management**: Orchestrator has logic but needs Context Broker enhancement
- **Scenario Contracts**: Flexible but needs standardization per revised plan
- **Memory/Summaries**: Basic state tracking, needs world summary system

### ❌ Missing Components (Implementation Required)
- **Policy Engine**: House rules, difficulty scaling, advantage computation
- **Enhanced Saga Manager**: Multi-step flow tracking with correlation IDs
- **Decision Logs**: Comprehensive roll breakdown and DC provenance
- **Observability**: OpenTelemetry-style tracing and structured logging
- **Contract Testing**: Standardized input/output validation for all agents

---

## Implementation Roadmap

### Phase 1: Core Infrastructure (Weeks 1-2)
**Goal**: Add missing foundational components

#### 1.1 Policy Engine Implementation
```python
# New file: components/policy_engine.py
class PolicyEngine:
    def __init__(self, policy_profile: str = "RAW"):
        self.profile = policy_profile
        self.house_rules = {}
        self.difficulty_modifiers = {}
    
    def compute_advantage(self, state, actor, skill) -> str:
        # Returns "advantage", "disadvantage", or "normal"
    
    def adjust_difficulty(self, base_dc: int, context: dict) -> int:
        # Apply difficulty scaling based on context
    
    def passive_score(self, ability_mod: int, prof: int, bonus: int = 0) -> int:
        # Calculate passive scores (10 + mod + bonus)
```

#### 1.2 Enhanced Saga Manager
```python
# New file: orchestrator/saga_manager.py
class SagaManager:
    def __init__(self):
        self.active_sagas = {}
        self.correlation_tracker = {}
    
    def start_saga(self, saga_type: str, initial_data: dict) -> str:
        # Create correlation ID and track multi-step flow
    
    def advance_saga(self, correlation_id: str, step_result: dict):
        # Progress saga to next step
    
    def complete_saga(self, correlation_id: str, final_result: dict):
        # Complete and log saga outcome
```

#### 1.3 Decision Logging System  
```python
# New file: orchestrator/decision_logger.py
class DecisionLogger:
    def log_skill_check(self, check_data: dict, outcome: dict):
        # Log: DC source, roll breakdown, advantage sources, final result
    
    def log_combat_action(self, action_data: dict, outcome: dict):
        # Log: action legality, roll results, damage calculations
    
    def get_decision_history(self, correlation_id: str) -> List[dict]:
        # Retrieve all decisions for a saga/encounter
```

### Phase 2: Contract Standardization (Weeks 3-4)
**Goal**: Implement standardized agent contracts per revised plan

#### 2.1 Scenario Generator Contract
Update [`agents/scenario_generator.py`](agents/scenario_generator.py) to match revised plan format:

```python
# Enhanced output format matching revised plan
def generate_scenario_with_contract(self, query: str) -> dict:
    return {
        "scene": "Narrative description",
        "choices": [
            {
                "id": "c1",
                "title": "Action title",
                "description": "Detailed description",
                "skill_hints": ["Stealth", "Perception"],
                "suggested_dc": {"easy": 10, "medium": 15, "hard": 20},
                "combat_trigger": False
            }
        ],
        "effects": [
            {"type": "flag", "name": "alert_guard", "value": True}
        ],
        "hooks": [
            {"quest": "rescue_hostage", "progress": "advance"}
        ]
    }
```

#### 2.2 Skill Check Pipeline Enhancement
Update existing components to use Policy Engine:

```python
# In components/rules_enforcer.py (enhance existing)
class RuleEnforcer:
    def __init__(self, policy_engine: PolicyEngine):
        self.policy_engine = policy_engine
    
    def determine_skill_check(self, context: dict) -> dict:
        # 1. Determine if check needed
        # 2. Calculate base DC
        # 3. Apply policy adjustments
        # 4. Return structured check definition
```

### Phase 3: Combat Determinism (Weeks 5-6)
**Goal**: Make combat fully deterministic and auditable

#### 3.1 Enhanced Combat Pipeline
Extend [`agents/combat_engine.py`](agents/combat_engine.py):

```python
# Add to existing CombatEngine class
def execute_deterministic_action(self, action_request: dict) -> dict:
    # 1. Validate action legality (Rules Enforcer)
    # 2. Calculate modifiers (Policy Engine)  
    # 3. Execute rolls (Dice Roller with logging)
    # 4. Apply results (deterministic damage/effects)
    # 5. Log complete decision chain
    
    return {
        "success": True,
        "action_result": {...},
        "decision_log": {...},
        "state_changes": {...}
    }
```

#### 3.2 NPC Action Proposals
Extend [`agents/npc_controller.py`](agents/npc_controller.py):

```python
# Add to existing NPCControllerAgent
def propose_combat_actions(self, game_state: dict) -> List[dict]:
    # Creative: Generate action proposals
    # Return structured actions for Combat Engine validation
```

### Phase 4: Observability & Testing (Weeks 7-8)
**Goal**: Add comprehensive testing and observability

#### 4.1 Observability Framework
```python
# New file: orchestrator/observability.py
class ObservabilityManager:
    def start_trace(self, operation: str) -> str:
        # Start OpenTelemetry-style trace
    
    def add_span(self, trace_id: str, component: str, operation: str):
        # Add span to trace
    
    def log_structured(self, level: str, message: str, context: dict):
        # Structured logging with correlation IDs
```

#### 4.2 Contract Testing Framework
```python
# New file: tests/contracts/
# - test_scenario_contracts.py
# - test_combat_contracts.py  
# - test_agent_contracts.py

def test_scenario_generator_contract():
    # Validate scenario output matches expected schema
    # Test with various inputs
    # Verify deterministic components produce consistent outputs
```

#### 4.3 Golden Scenario Tests
```python
# New file: tests/golden/
# - test_tavern_encounter.py
# - test_combat_scenario.py
# - test_skill_challenge.py

def test_complete_tavern_encounter():
    # Full end-to-end scenario with expected outcomes
    # Regression testing for consistent behavior
```

---

## Detailed Component Designs

### Policy Engine Architecture

```python
class PolicyEngine:
    """Centralized rule mediation with profile support"""
    
    PROFILES = {
        "RAW": {  # Rules As Written
            "flanking_advantage": False,
            "crit_range": [20],
            "death_saves": "standard"
        },
        "HOUSE": {  # Common house rules
            "flanking_advantage": True,
            "crit_range": [19, 20],
            "death_saves": "forgiving"
        },
        "EASY": {  # Beginner-friendly
            "flanking_advantage": True,
            "crit_range": [19, 20],
            "dc_adjustment": -2
        }
    }
    
    def __init__(self, profile: str = "RAW"):
        self.active_profile = self.PROFILES.get(profile, self.PROFILES["RAW"])
        self.custom_overrides = {}
    
    def compute_advantage(self, context: dict) -> str:
        """Determine advantage/disadvantage from context"""
        advantages = []
        disadvantages = []
        
        # Check flanking
        if context.get("flanking") and self.active_profile.get("flanking_advantage"):
            advantages.append("flanking")
        
        # Check conditions
        if "blinded" in context.get("conditions", []):
            disadvantages.append("blinded")
            
        # Resolve final state
        if len(advantages) > len(disadvantages):
            return "advantage"
        elif len(disadvantages) > len(advantages):
            return "disadvantage"
        else:
            return "normal"
    
    def adjust_difficulty(self, base_dc: int, context: dict) -> int:
        """Apply difficulty scaling"""
        adjustment = self.active_profile.get("dc_adjustment", 0)
        
        # Context-specific adjustments
        if context.get("party_level", 1) < 3:
            adjustment -= 1  # Easier for low-level parties
            
        return max(5, base_dc + adjustment)  # Minimum DC 5
```

### Enhanced Saga Manager

```python
from typing import Dict, List, Optional, Callable
import uuid
import time

class SagaStep:
    def __init__(self, step_type: str, handler: Callable, timeout: float = 30.0):
        self.step_type = step_type
        self.handler = handler
        self.timeout = timeout
        self.attempts = 0
        self.max_attempts = 3

class Saga:
    def __init__(self, saga_id: str, saga_type: str):
        self.saga_id = saga_id
        self.saga_type = saga_type
        self.current_step = 0
        self.steps: List[SagaStep] = []
        self.context = {}
        self.start_time = time.time()
        self.status = "active"
        self.decision_log = []

class SagaManager:
    """Enhanced saga manager for multi-step game flows"""
    
    def __init__(self):
        self.active_sagas: Dict[str, Saga] = {}
        self.completed_sagas: List[Saga] = []
        self.saga_templates = {
            "skill_challenge": self._build_skill_challenge_saga,
            "combat_encounter": self._build_combat_saga,
            "social_encounter": self._build_social_saga
        }
    
    def start_saga(self, saga_type: str, initial_context: dict) -> str:
        """Start a new multi-step saga"""
        saga_id = str(uuid.uuid4())
        saga = Saga(saga_id, saga_type)
        saga.context = initial_context.copy()
        
        # Build saga steps from template
        if saga_type in self.saga_templates:
            saga.steps = self.saga_templates[saga_type](initial_context)
        
        self.active_sagas[saga_id] = saga
        return saga_id
    
    def advance_saga(self, saga_id: str, step_result: dict) -> dict:
        """Advance saga to next step"""
        if saga_id not in self.active_sagas:
            return {"success": False, "error": "Saga not found"}
        
        saga = self.active_sagas[saga_id]
        
        # Log the step result
        saga.decision_log.append({
            "step": saga.current_step,
            "timestamp": time.time(),
            "result": step_result
        })
        
        # Update context with step results
        saga.context.update(step_result.get("context_updates", {}))
        
        # Check if saga is complete
        if saga.current_step >= len(saga.steps) - 1:
            return self._complete_saga(saga_id, step_result)
        
        # Advance to next step
        saga.current_step += 1
        next_step = saga.steps[saga.current_step]
        
        return {
            "success": True,
            "saga_id": saga_id,
            "next_step": next_step.step_type,
            "context": saga.context
        }
    
    def _build_skill_challenge_saga(self, context: dict) -> List[SagaStep]:
        """Build skill challenge saga template"""
        return [
            SagaStep("present_challenge", self._present_challenge),
            SagaStep("player_choice", self._handle_player_choice),
            SagaStep("skill_check", self._execute_skill_check),
            SagaStep("resolve_outcome", self._resolve_skill_outcome)
        ]
    
    def _build_combat_saga(self, context: dict) -> List[SagaStep]:
        """Build combat encounter saga template"""
        return [
            SagaStep("combat_start", self._start_combat),
            SagaStep("initiative", self._handle_initiative),
            SagaStep("combat_round", self._process_combat_round),
            SagaStep("combat_end", self._end_combat)
        ]
```

### Decision Logger System

```python
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
import time
import json

@dataclass
class SkillCheckDecision:
    check_type: str
    ability: str
    skill: Optional[str]
    dc: int
    dc_source: str
    actor: str
    roll_result: int
    modifiers: Dict[str, int]
    advantage_state: str
    advantage_sources: List[str]
    final_result: bool
    timestamp: float
    correlation_id: str

@dataclass
class CombatDecision:
    action_type: str
    actor: str
    target: Optional[str]
    attack_roll: Optional[int]
    damage_roll: Optional[int]
    conditions_applied: List[str]
    state_changes: Dict[str, Any]
    legality_check: Dict[str, Any]
    timestamp: float
    correlation_id: str

class DecisionLogger:
    """Comprehensive decision logging for audit trail"""
    
    def __init__(self):
        self.skill_check_log: List[SkillCheckDecision] = []
        self.combat_log: List[CombatDecision] = []
        self.session_logs: Dict[str, List] = {}
    
    def log_skill_check(self, 
                       check_type: str,
                       ability: str, 
                       skill: Optional[str],
                       dc: int,
                       dc_source: str,
                       actor: str,
                       roll_result: int,
                       modifiers: Dict[str, int],
                       advantage_state: str,
                       advantage_sources: List[str],
                       final_result: bool,
                       correlation_id: str) -> None:
        """Log skill check with complete provenance"""
        
        decision = SkillCheckDecision(
            check_type=check_type,
            ability=ability,
            skill=skill,
            dc=dc,
            dc_source=dc_source,
            actor=actor,
            roll_result=roll_result,
            modifiers=modifiers,
            advantage_state=advantage_state,
            advantage_sources=advantage_sources,
            final_result=final_result,
            timestamp=time.time(),
            correlation_id=correlation_id
        )
        
        self.skill_check_log.append(decision)
    
    def log_combat_action(self,
                         action_type: str,
                         actor: str,
                         target: Optional[str],
                         attack_roll: Optional[int],
                         damage_roll: Optional[int],
                         conditions_applied: List[str],
                         state_changes: Dict[str, Any],
                         legality_check: Dict[str, Any],
                         correlation_id: str) -> None:
        """Log combat action with validation results"""
        
        decision = CombatDecision(
            action_type=action_type,
            actor=actor,
            target=target,
            attack_roll=attack_roll,
            damage_roll=damage_roll,
            conditions_applied=conditions_applied,
            state_changes=state_changes,
            legality_check=legality_check,
            timestamp=time.time(),
            correlation_id=correlation_id
        )
        
        self.combat_log.append(decision)
    
    def get_decision_history(self, correlation_id: str) -> Dict[str, List]:
        """Get all decisions for a correlation ID"""
        skill_checks = [
            asdict(decision) for decision in self.skill_check_log 
            if decision.correlation_id == correlation_id
        ]
        
        combat_actions = [
            asdict(decision) for decision in self.combat_log
            if decision.correlation_id == correlation_id
        ]
        
        return {
            "skill_checks": skill_checks,
            "combat_actions": combat_actions
        }
    
    def export_session_log(self, session_id: str) -> str:
        """Export complete session log as JSON"""
        session_data = {
            "session_id": session_id,
            "skill_checks": [asdict(d) for d in self.skill_check_log],
            "combat_actions": [asdict(d) for d in self.combat_log],
            "export_timestamp": time.time()
        }
        
        return json.dumps(session_data, indent=2)
```

---

## Testing Strategy

### Contract Testing Framework

```python
# tests/contracts/test_scenario_contracts.py
import pytest
from agents.scenario_generator import ScenarioGeneratorAgent

class TestScenarioContracts:
    
    def test_scenario_output_schema(self):
        """Test scenario generator produces correct schema"""
        agent = ScenarioGeneratorAgent()
        
        result = agent.generate_scenario_with_contract("tavern encounter")
        
        # Validate required fields
        assert "scene" in result
        assert "choices" in result
        assert "effects" in result
        assert "hooks" in result
        
        # Validate choice structure
        for choice in result["choices"]:
            assert "id" in choice
            assert "title" in choice
            assert "description" in choice
            assert "skill_hints" in choice
            assert "suggested_dc" in choice
            assert "combat_trigger" in choice
            
            # Validate DC structure
            dc = choice["suggested_dc"]
            assert "easy" in dc
            assert "medium" in dc  
            assert "hard" in dc
            assert dc["easy"] < dc["medium"] < dc["hard"]
    
    def test_deterministic_components_consistency(self):
        """Test deterministic components produce consistent results"""
        from agents.dice_system import DiceRoller
        
        roller = DiceRoller()
        
        # Same seed should produce same results
        result1 = roller.roll("1d20+5", "test", seed=12345)
        result2 = roller.roll("1d20+5", "test", seed=12345)
        
        assert result1.total == result2.total
        assert result1.rolls == result2.rolls
```

### Golden Scenario Testing

```python
# tests/golden/test_tavern_encounter.py
class TestTavernEncounter:
    
    def test_complete_tavern_scenario(self):
        """Test complete tavern encounter produces expected flow"""
        
        # Initialize system
        dm_assistant = ModularDMAssistant(verbose=False)
        dm_assistant.start()
        
        # Generate tavern scenario
        response = dm_assistant.process_dm_input("generate tavern encounter")
        
        # Validate scenario structure
        assert "tavern" in response.lower()
        assert "option" in response.lower()
        
        # Select an option
        choice_response = dm_assistant.process_dm_input("select option 1")
        
        # Validate consequence
        assert "selected" in choice_response.lower()
        assert len(choice_response) > 50  # Substantive response
        
        dm_assistant.stop()
    
    def test_skill_check_pipeline(self):
        """Test complete skill check pipeline with decision logging"""
        
        # This would test the full pipeline:
        # 1. Scenario generation
        # 2. Player choice
        # 3. Skill check determination  
        # 4. Policy engine consultation
        # 5. Dice rolling with logging
        # 6. Result application
        # 7. Decision log verification
        
        pass  # Implementation would follow similar pattern
```

---

## Implementation Timeline

### Week 1-2: Core Infrastructure
- [ ] Implement Policy Engine (`components/policy_engine.py`)
- [ ] Create Enhanced Saga Manager (`orchestrator/saga_manager.py`)  
- [ ] Build Decision Logger (`orchestrator/decision_logger.py`)
- [ ] Add correlation ID tracking to message framework

### Week 3-4: Contract Standardization  
- [ ] Update Scenario Generator with standardized contracts
- [ ] Enhance Rules Enforcer to use Policy Engine
- [ ] Modify Combat Engine for deterministic processing
- [ ] Update all agents to use structured response formats

### Week 5-6: Combat Enhancement
- [ ] Implement deterministic combat pipeline
- [ ] Add NPC action proposal system
- [ ] Integrate decision logging throughout combat
- [ ] Create combat validation framework

### Week 7-8: Testing & Observability
- [ ] Build contract testing framework
- [ ] Create golden scenario tests
- [ ] Implement observability manager
- [ ] Add structured logging throughout system

---

## Migration Strategy

### 1. Backward Compatibility
- Keep existing interfaces working during transition
- Add new standardized methods alongside legacy ones
- Gradual migration of command handlers to use new contracts

### 2. Incremental Deployment
- Deploy components independently 
- Test each component thoroughly before integration
- Maintain rollback capability for each component

### 3. Configuration Management
- Policy profiles configurable via JSON files
- Feature flags for enabling/disabling new components
- Environment-specific configurations (dev/test/prod)

---

## Success Metrics

### Technical Metrics
- [ ] 100% of agents follow standardized contracts
- [ ] All combat actions have complete decision provenance
- [ ] Policy Engine covers all major D&D mechanics
- [ ] 95%+ test coverage on new components

### Functional Metrics  
- [ ] Consistent scenario generation across sessions
- [ ] Deterministic combat outcomes (same inputs = same outputs)
- [ ] Complete audit trail for all game decisions
- [ ] Sub-200ms response time for non-LLM operations

### User Experience Metrics
- [ ] No breaking changes to existing command interface
- [ ] Enhanced scenario quality with standardized contracts
- [ ] Improved combat flow with better action validation
- [ ] Rich decision history for session review

---

## Conclusion

This implementation plan transforms the existing sophisticated foundation into a production-ready D&D system that fully aligns with the revised Haystack plan. The focus on **enhancement rather than rewrite** leverages the substantial existing investment while adding the missing pieces for a complete, deterministic, and observable D&D game system.

The phased approach allows for iterative development and testing, ensuring stability throughout the enhancement process while building toward the comprehensive vision outlined in the revised plan.