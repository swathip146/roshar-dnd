"""
Game Engine - Stage 3 Week 11-12
Authoritative state writer with 7-step pipeline - From Original Plan
"""

from typing import Dict, Any, Optional
import time
import uuid
from dataclasses import dataclass

from .policy import PolicyEngine, PolicyProfile
from .dice import DiceRoller
from .rules import RulesEnforcer
from .character_manager import CharacterManager

@dataclass
class GameState:
    """Complete game state structure"""
    characters: Dict[str, Any]
    combat_state: Dict[str, Any]
    environment: Dict[str, Any]
    campaign_flags: Dict[str, Any]
    session_data: Dict[str, Any]
    
class GameEngine:
    """
    Authoritative state writer with 7-step pipeline - From Original Plan
    Handles deterministic skill checks and maintains authoritative game state
    """
    
    def __init__(self, policy_profile: PolicyProfile = PolicyProfile.RAW):
        """Initialize game engine with all required components"""
        self.policy_engine = PolicyEngine(policy_profile)
        self.dice_roller = DiceRoller()
        self.rules_enforcer = RulesEnforcer()
        self.character_manager = CharacterManager()
        
        # Initialize authoritative game state
        self.game_state = GameState(
            characters={},
            combat_state={
                "active": False,
                "initiative_order": [],
                "current_turn": 0,
                "round_number": 0,
                "flanking": {}
            },
            environment={
                "lighting": "normal",
                "terrain": "normal",
                "weather": "clear"
            },
            campaign_flags={},
            session_data={
                "start_time": time.time(),
                "total_checks": 0,
                "successful_checks": 0
            }
        )
        
        # Decision logging hook (will be set by DecisionLogger)
        self.decision_logger = None
        
        print("⚙️ Game Engine initialized with 7-step skill pipeline")
    
    def process_skill_check(self, check_request: Dict[str, Any]) -> Dict[str, Any]:
        """
        7-step deterministic skill check pipeline - Exact from Original Plan
        
        Step 1: Rules Enforcer → do we need a check? derive DC
        Step 2: Character Manager → skill/ability mod, conditions  
        Step 3: Policy Engine → advantage/disadvantage, house rules
        Step 4: Dice Roller → raw rolls (logged)
        Step 5: Rules Enforcer → compare vs DC, success/fail
        Step 6: Game Engine → apply state, log outcome
        Step 7: Decision Log → roll breakdown, DC provenance, advantage sources
        """
        correlation_id = check_request.get("correlation_id", str(uuid.uuid4()))
        
        # Step 1: Rules Enforcer → do we need a check? derive DC
        rules_result = self.rules_enforcer.determine_check_needed(check_request)
        if not rules_result.check_needed:
            return {
                "success": True, 
                "auto_success": rules_result.auto_success,
                "auto_failure": rules_result.auto_failure,
                "reason": rules_result.reason,
                "correlation_id": correlation_id
            }
        
        dc = rules_result.dc
        dc_source = rules_result.dc_source
        
        # Step 2: Character Manager → skill/ability mod, conditions
        char_data = self.character_manager.get_skill_data(
            check_request["actor"], check_request.get("skill", "")
        )
        
        # Step 3: Policy Engine → advantage/disadvantage, house rules  
        advantage_state = self.policy_engine.compute_advantage(
            self._get_state_dict(), check_request["actor"], check_request.get("skill", ""),
            check_request.get("context", {})
        )
        
        adjusted_dc_result = self.policy_engine.adjust_difficulty(dc, check_request.get("context", {}))
        adjusted_dc = adjusted_dc_result["final_dc"]
        
        # Step 4: Dice Roller → raw rolls (logged)
        roll_result = self.dice_roller.skill_roll(
            check_request.get("skill", "ability_check"), 
            char_data["modifier"],
            advantage_state,
            correlation_id
        )
        
        # Step 5: Rules Enforcer → compare vs DC, success/fail
        success = roll_result["total"] >= adjusted_dc
        
        # Step 6: Game Engine → apply state, log outcome
        outcome = {
            "success": success,
            "roll_total": roll_result["total"],
            "raw_rolls": roll_result["raw_rolls"],
            "selected_roll": roll_result["selected_roll"],
            "dc": adjusted_dc,
            "dc_source": dc_source,
            "dc_adjustments": adjusted_dc_result["adjustments"],
            "advantage_state": advantage_state["final_state"],
            "advantage_sources": advantage_state["advantage_sources"],
            "disadvantage_sources": advantage_state["disadvantage_sources"],
            "character_modifier": char_data["modifier"],
            "modifier_breakdown": char_data["breakdown"],
            "roll_breakdown": roll_result["roll_breakdown"],
            "correlation_id": correlation_id,
            "actor": check_request["actor"],
            "skill": check_request.get("skill", ""),
            "timestamp": time.time()
        }
        
        self._apply_skill_check_outcome(check_request, outcome)
        
        # Step 7: Decision Log → roll breakdown, DC provenance, advantage sources
        self._log_skill_check_decision(correlation_id, check_request, outcome, roll_result)
        
        return outcome
    
    def _apply_skill_check_outcome(self, check_request: Dict[str, Any], outcome: Dict[str, Any]):
        """Apply skill check results to game state"""
        # Update session statistics
        self.game_state.session_data["total_checks"] += 1
        if outcome["success"]:
            self.game_state.session_data["successful_checks"] += 1
        
        # Apply contextual state changes based on skill check results
        skill = check_request.get("skill", "")
        actor = check_request["actor"]
        
        # Examples of state changes (would be expanded based on game logic)
        if skill == "stealth" and outcome["success"]:
            # Successful stealth might update environment state
            if actor not in self.game_state.characters:
                self.game_state.characters[actor] = {}
            self.game_state.characters[actor]["hidden"] = True
        
        elif skill == "perception" and outcome["success"]:
            # Successful perception might reveal information
            context = check_request.get("context", {})
            if "hidden_information" in context:
                self.game_state.campaign_flags["revealed_info"] = context["hidden_information"]
    
    def _log_skill_check_decision(self, correlation_id: str, check_request: Dict[str, Any],
                                outcome: Dict[str, Any], roll_result: Dict[str, Any]):
        """Step 7: Decision logging integration"""
        if self.decision_logger:
            self.decision_logger.log_skill_check(correlation_id, check_request, outcome)
    
    def _get_state_dict(self) -> Dict[str, Any]:
        """Convert GameState to dictionary for policy engine"""
        return {
            "characters": self.game_state.characters,
            "combat_state": self.game_state.combat_state,
            "environment": self.game_state.environment,
            "campaign_flags": self.game_state.campaign_flags
        }
    
    def add_character(self, character_data: Dict[str, Any]) -> str:
        """Add character to both character manager and game state"""
        char_id = self.character_manager.add_character(character_data)
        
        # Add to game state
        self.game_state.characters[char_id] = {
            "name": character_data.get("name", char_id),
            "level": character_data.get("level", 1),
            "conditions": character_data.get("conditions", []),
            "position": {"x": 0, "y": 0},  # For future combat positioning
            "hidden": False,
            "initiative": 0
        }
        
        return char_id
    
    def update_environment(self, environment_updates: Dict[str, Any]):
        """Update environmental conditions"""
        self.game_state.environment.update(environment_updates)
        print(f"🌍 Updated environment: {environment_updates}")
    
    def set_character_condition(self, character_id: str, condition: str, active: bool = True):
        """Set character condition in both character manager and game state"""
        self.character_manager.update_character_condition(character_id, condition, active)
        
        if character_id in self.game_state.characters:
            char_conditions = self.game_state.characters[character_id].get("conditions", [])
            if active and condition not in char_conditions:
                char_conditions.append(condition)
            elif not active and condition in char_conditions:
                char_conditions.remove(condition)
            
            self.game_state.characters[character_id]["conditions"] = char_conditions
    
    def set_campaign_flag(self, flag_name: str, value: Any):
        """Set campaign flag for tracking story progress"""
        self.game_state.campaign_flags[flag_name] = value
        print(f"🚩 Set campaign flag: {flag_name} = {value}")
    
    def get_campaign_flag(self, flag_name: str, default: Any = None) -> Any:
        """Get campaign flag value"""
        return self.game_state.campaign_flags.get(flag_name, default)
    
    def process_contested_check(self, actor1: str, skill1: str, 
                               actor2: str, skill2: str,
                               context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process contested check between two actors"""
        correlation_id = str(uuid.uuid4())
        context = context or {}
        
        # Process check for first actor
        check1_request = {
            "action": f"contest_{skill1}",
            "actor": actor1,
            "skill": skill1,
            "context": context,
            "correlation_id": f"{correlation_id}_actor1"
        }
        
        result1 = self.process_skill_check(check1_request)
        
        # Process check for second actor
        check2_request = {
            "action": f"contest_{skill2}",
            "actor": actor2,
            "skill": skill2,
            "context": context,
            "correlation_id": f"{correlation_id}_actor2"
        }
        
        result2 = self.process_skill_check(check2_request)
        
        # Determine winner
        total1 = result1.get("roll_total", 0)
        total2 = result2.get("roll_total", 0)
        
        if total1 > total2:
            winner = actor1
            margin = total1 - total2
        elif total2 > total1:
            winner = actor2
            margin = total2 - total1
        else:
            winner = None  # Tie
            margin = 0
        
        contest_result = {
            "winner": winner,
            "margin": margin,
            "actor1_result": result1,
            "actor2_result": result2,
            "correlation_id": correlation_id,
            "contest_type": f"{skill1}_vs_{skill2}"
        }
        
        return contest_result
    
    def get_game_statistics(self) -> Dict[str, Any]:
        """Get comprehensive game statistics"""
        session_data = self.game_state.session_data
        
        success_rate = 0
        if session_data["total_checks"] > 0:
            success_rate = session_data["successful_checks"] / session_data["total_checks"]
        
        # Get dice statistics
        dice_stats = self.dice_roller.get_roll_statistics()
        
        return {
            "session_duration": time.time() - session_data["start_time"],
            "total_skill_checks": session_data["total_checks"],
            "successful_checks": session_data["successful_checks"],
            "success_rate": success_rate,
            "dice_statistics": dice_stats,
            "active_characters": len(self.game_state.characters),
            "campaign_flags": len(self.game_state.campaign_flags),
            "environment": self.game_state.environment
        }
    
    def export_game_state(self) -> Dict[str, Any]:
        """Export complete game state for saving"""
        return {
            "game_state": {
                "characters": self.game_state.characters,
                "combat_state": self.game_state.combat_state,
                "environment": self.game_state.environment,
                "campaign_flags": self.game_state.campaign_flags,
                "session_data": self.game_state.session_data
            },
            "character_data": {
                char_id: self.character_manager.get_character_summary(char_id)
                for char_id in self.game_state.characters.keys()
            },
            "policy_profile": self.policy_engine.active_profile_type.value,
            "export_timestamp": time.time()
        }
    
    def set_decision_logger(self, decision_logger):
        """Set decision logger for step 7 of pipeline"""
        self.decision_logger = decision_logger
        print("📝 Decision logger connected to Game Engine")


# Factory function for easy integration
def create_game_engine(policy_profile: PolicyProfile = PolicyProfile.RAW) -> GameEngine:
    """Factory function to create configured game engine"""
    return GameEngine(policy_profile)


# Example usage for Stage 3 testing
if __name__ == "__main__":
    # Test game engine with 7-step pipeline
    engine = create_game_engine(PolicyProfile.HOUSE)
    
    # Add a test character
    test_character = {
        "character_id": "test_player",
        "name": "Test Character",
        "level": 5,
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
            "perception": True,
            "investigation": True
        },
        "expertise_skills": ["stealth"],
        "conditions": []
    }
    
    char_id = engine.add_character(test_character)
    
    # Test skill check with full 7-step pipeline
    skill_check = {
        "action": "sneak past the guards",
        "actor": char_id,
        "skill": "stealth",
        "context": {
            "difficulty": "medium",
            "environment": {"lighting": "dim"},
            "cover": True
        }
    }
    
    result = engine.process_skill_check(skill_check)
    print(f"7-step pipeline result: {result}")
    
    # Test contested check
    # Add second character for contest
    char2_data = test_character.copy()
    char2_data["character_id"] = "guard"
    char2_data["name"] = "Guard"
    char2_id = engine.add_character(char2_data)
    
    contest_result = engine.process_contested_check(
        char_id, "stealth", char2_id, "perception"
    )
    print(f"Contested check result: {contest_result}")
    
    # Show game statistics
    stats = engine.get_game_statistics()
    print(f"Game statistics: {stats}")