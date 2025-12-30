"""
Game Engine - Stage 3 Week 11-12
Authoritative state writer with 7-step pipeline - From Original Plan
"""

from typing import Dict, Any, Optional, List, TypedDict
import time
import uuid
from dataclasses import dataclass

from .policy import PolicyEngine, PolicyProfile
from .dice import DiceRoller
from .rules import RulesEnforcer
from .character_manager import CharacterManager
from .campaign_config import CampaignConfig

from config.logging_config import get_logger

# Initialize logger
logger = get_logger(__name__)


# TypedDict definitions for GameState Dict fields
class CharacterRuntimeState(TypedDict, total=False):
    """Allowed keys for individual character runtime state"""
    position: Dict[str, int]  # {"x": int, "y": int}
    hidden: bool
    initiative: int
    runtime_conditions: List[str]
    last_action: Optional[str]
    session_notes: List[str]

class CombatState(TypedDict, total=False):
    """Allowed keys for combat state"""
    active: bool
    initiative_order: List[str]
    current_turn: int
    round_number: int
    flanking: Dict[str, Any]

class Environment(TypedDict, total=False):
    """Allowed keys for environment state"""
    lighting: str
    terrain: str
    weather: str

class SessionData(TypedDict, total=False):
    """Allowed keys for session data"""
    start_time: float
    total_checks: int
    successful_checks: int

class NarrativeContext(TypedDict, total=False):
    """Allowed keys for narrative context"""
    current_scene: str
    pacing: str
    tension_level: str
    narrative_beats: List[str]
    story_hooks: List[Dict[str, Any]]  # Each hook: {"text": str, "priority": str, "added_time": float}
    last_scenario_type: str
    scenario_confidence: float
    turn_number: int

class LocationContext(TypedDict, total=False):
    """Allowed keys for location context"""
    current_location: str
    location_type: str
    description: str
    features: List[str]
    hazards: List[str]
    npcs_present: List[str]
    exits: List[str]
    entry_time: float

class QuestContext(TypedDict, total=False):
    """Allowed keys for quest context"""
    active_quests: List[str]
    completed_objectives: List[Dict[str, Any]]  # Each: {"text": str, "quest_name": str, "added_time": float, "completion_time": float}
    pending_objectives: List[Dict[str, Any]]    # Each: {"text": str, "quest_name": str, "added_time": float}
    quest_constraints: List[str]
    time_pressure: str
    consequences: List[str]
    rewards: List[str]

@dataclass
class GameState:
    """
    Complete game state structure - campaign data moved to GameEngine.campaign_config
    
    IMPORTANT: All Dict fields have strictly defined allowed keys via TypedDict.
    Only the keys defined in the corresponding TypedDict classes may be used:
    
    - characters: Keys defined in CharacterRuntimeState
    - combat_state: Keys defined in CombatState
    - environment: Keys defined in Environment
    - campaign_flags: Flexible Dict[str, Any] for various flag types
    - session_data: Keys defined in SessionData
    - narrative_context: Keys defined in NarrativeContext
    - location_context: Keys defined in LocationContext
    - quest_context: Keys defined in QuestContext
    
    NO additional keys should be used without updating the corresponding TypedDict definition.
    """
    characters: Dict[str, CharacterRuntimeState]
    combat_state: CombatState
    environment: Environment
    campaign_flags: Dict[str, Any]  # Flexible for various flag types
    session_data: SessionData
    narrative_context: NarrativeContext
    location_context: LocationContext
    quest_context: QuestContext
    
    
class GameEngine:
    """
    Authoritative state writer with 7-step pipeline - From Original Plan
    Handles deterministic skill checks and maintains authoritative game state
    """
    
    def __init__(self, policy_profile: PolicyProfile = PolicyProfile.RAW,
                 campaign_config: Optional[CampaignConfig] = None):
        """Initialize game engine with all required components and CampaignConfig"""
        self.policy_engine = PolicyEngine(policy_profile)
        self.dice_roller = DiceRoller()
        self.rules_enforcer = RulesEnforcer()
        self.character_manager = CharacterManager()
        
        # BREAKING CHANGE: Store CampaignConfig as immutable reference
        self.campaign_config = campaign_config
        
        # Initialize authoritative game state (campaign data removed - now in campaign_config)
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
            },
            narrative_context = {
                "current_scene": "Unknown",
                "pacing": "moderate",
                "tension_level": "normal",
                "narrative_beats": [],
                "story_hooks": []
            },
            location_context = {
                "current_location": "Unknown",
                "description": "",
                "features": [],
                "hazards": [],
                "npcs_present": [],
                "exits": []
            },
            quest_context = {
                "active_quests": [],
                "completed_objectives": [],
                "pending_objectives": [],
                "quest_constraints": [],
                "time_pressure": "none",
                "consequences": [],
                "rewards":[]
            }
        )
        
        # Initialize location if campaign_config provided
        if self.campaign_config:
            self.game_state.location_context["current_location"] = self.campaign_config.starting_location
            self.game_state.location_context["description"] = self.campaign_config.story
        
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
        """Apply skill check results to game state - BREAKING CHANGE: Runtime state only"""
        # Update session statistics
        self.game_state.session_data["total_checks"] += 1
        if outcome["success"]:
            self.game_state.session_data["successful_checks"] += 1
        
        # Apply contextual state changes based on skill check results
        skill = check_request.get("skill", "")
        actor = check_request["actor"]
        
        # Examples of state changes (would be expanded based on game logic)
        if skill == "stealth" and outcome["success"]:
            # Successful stealth updates RUNTIME state only
            if actor in self.game_state.characters:
                self.game_state.characters[actor]["hidden"] = True
                self.game_state.characters[actor]["last_action"] = "stealth_success"
        
        elif skill == "perception" and outcome["success"]:
            # Successful perception might reveal information
            context = check_request.get("context", {})
            if "hidden_information" in context:
                self.game_state.campaign_flags["revealed_info"] = context["hidden_information"]
            
            # Track perception success in runtime state
            if actor in self.game_state.characters:
                self.game_state.characters[actor]["last_action"] = "perception_success"
    
    def _log_skill_check_decision(self, correlation_id: str, check_request: Dict[str, Any],
                                outcome: Dict[str, Any], roll_result: Dict[str, Any]):
        """Step 7: Decision logging integration"""
        if self.decision_logger:
            self.decision_logger.log_skill_check(correlation_id, check_request, outcome)
    
    def _get_state_dict(self) -> Dict[str, Any]:
        """Convert GameState to dictionary for policy engine"""
        # BREAKING CHANGE: Use campaign_config instead of campaign_data
        campaign_data = {}
        if self.campaign_config:
            campaign_data = {
                "campaign_started": True,
                "campaign_name": self.campaign_config.name,
                "campaign_npcs": [npc.name for npc in self.campaign_config.key_npcs],
                "campaign_locations": [loc.name for loc in self.campaign_config.locations],
                "campaign_quests": self.campaign_config.quests,
                "campaign_difficulty": self.campaign_config.difficulty,
                "campaign_theme": self.campaign_config.theme,
                "level_range": self.campaign_config.level_range
            }
        
        return {
            "characters": self.game_state.characters,
            "combat_state": self.game_state.combat_state,
            "environment": self.game_state.environment,
            "campaign_flags": self.game_state.campaign_flags,
            "campaign_data": campaign_data
        }
    
    def add_character(self, character_data: Dict[str, Any]) -> str:
        """Add character to CharacterManager and initialize runtime state in GameState"""
        
        # Use CharacterManager as the authoritative source for character data
        char_id = self.character_manager.add_character(character_data)
        
        # GameState only stores RUNTIME state - no character sheet duplication
        self.game_state.characters[char_id] = {
            "position": {"x": 0, "y": 0},  # Combat positioning
            "hidden": False,  # Stealth state
            "initiative": 0,  # Combat initiative
            "runtime_conditions": [],  # Temporary conditions added during play
            "last_action": None,  # Track last action for scenario context
            "session_notes": [],  # Session-specific notes
            
            # Roshar-specific runtime state
            "investiture_spent_this_turn": 0,  # Track investiture usage per turn
            "surges_used_this_scene": [],  # Track surge usage for cooldowns
            "spren_interaction_state": "normal",  # Track spren bond status changes
            "oaths_spoken": [],  # Track oath progression history
            
            # Action tracking for current session
            "current_turn_actions": [],  # Actions taken in the current turn
            "turn_action_count": 0  # Number of actions taken this turn
        }
        
        logger.info(f"🎮 GameEngine: Added character {character_data.get('name', char_id)} to game state")
        return char_id
    
    def update_environment(self, environment_updates: Dict[str, Any]):
        """Update environmental conditions"""
        self.game_state.environment.update(environment_updates)
        logger.info(f"🌍 Updated environment: {environment_updates}")
    
    def set_character_condition(self, character_id: str, condition: str, active: bool = True):
        """Set character condition - BREAKING CHANGE: Uses CharacterManager as authority"""
        # CharacterManager handles persistent conditions
        self.character_manager.update_character_condition(character_id, condition, active)
        
        # GameState only tracks if this is a runtime condition added during session
        if character_id in self.game_state.characters:
            runtime_conditions = self.game_state.characters[character_id].get("runtime_conditions", [])
            if active and condition not in runtime_conditions:
                runtime_conditions.append(condition)
                self.game_state.characters[character_id]["runtime_conditions"] = runtime_conditions
            elif not active and condition in runtime_conditions:
                runtime_conditions.remove(condition)
                self.game_state.characters[character_id]["runtime_conditions"] = runtime_conditions
    
    def set_campaign_flag(self, flag_name: str, value: Any):
        """Set campaign flag for tracking story progress"""
        self.game_state.campaign_flags[flag_name] = value
        logger.info(f"🚩 Set campaign flag: {flag_name} = {value}")
    
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
        """Export complete game state for saving - BREAKING CHANGE: Clear authority separation"""
        exported_data = {
            "game_state": {
                "characters": self.game_state.characters,  # Runtime state only
                "combat_state": self.game_state.combat_state,
                "environment": self.game_state.environment,
                "campaign_flags": self.game_state.campaign_flags,
                "session_data": self.game_state.session_data,
                "narrative_context": self.game_state.narrative_context,
                "location_context": self.game_state.location_context,
                "quest_context": self.game_state.quest_context
            },
            # BREAKING CHANGE: Export full character data from CharacterManager (authority)
            "character_data": {
                char_id: self.character_manager.get_character_summary(char_id)
                for char_id in self.character_manager.characters.keys()
            },
            "policy_profile": self.policy_engine.active_profile_type.value,
            "export_timestamp": time.time()
        }
        
        # Include campaign_config data if available for compatibility
        if self.campaign_config:
            exported_data["campaign_config_data"] = {
                "name": self.campaign_config.name,
                "difficulty": self.campaign_config.difficulty,
                "theme": self.campaign_config.theme,
                "level_range": self.campaign_config.level_range,
                "starting_location": self.campaign_config.starting_location
            }
        
        return exported_data
    
    def import_game_state(self, state_data: Dict[str, Any]):
        """Import complete game state from saved data - BREAKING CHANGE: No campaign_data restoration"""
        if not isinstance(state_data, dict):
            logger.error("Invalid state data format for import")
            return
        
        # Restore game state fields
        if "game_state" in state_data:
            saved_game_state = state_data["game_state"]
            
            # Update each game state component
            if "characters" in saved_game_state:
                self.game_state.characters.update(saved_game_state["characters"])
            
            if "combat_state" in saved_game_state:
                self.game_state.combat_state.update(saved_game_state["combat_state"])
            
            if "environment" in saved_game_state:
                self.game_state.environment.update(saved_game_state["environment"])
            
            if "campaign_flags" in saved_game_state:
                self.game_state.campaign_flags.update(saved_game_state["campaign_flags"])
            
            if "session_data" in saved_game_state:
                self.game_state.session_data.update(saved_game_state["session_data"])
            
            # BREAKING CHANGE: Skip campaign_data - now managed by CampaignConfig
            # if "campaign_data" in saved_game_state:
            #     self.game_state.campaign_data.update(saved_game_state["campaign_data"])
            
            # Update narrative, location, and quest context if they exist
            if "narrative_context" in saved_game_state:
                self.game_state.narrative_context.update(saved_game_state["narrative_context"])
            
            if "location_context" in saved_game_state:
                self.game_state.location_context.update(saved_game_state["location_context"])
            
            if "quest_context" in saved_game_state:
                self.game_state.quest_context.update(saved_game_state["quest_context"])
        
        # BREAKING CHANGE: Restore character data to CharacterManager (authority)
        if "character_data" in state_data:
            for char_id, char_data in state_data["character_data"].items():
                try:
                    # CharacterManager is authority for character sheet data
                    restored_char_id = self.character_manager.add_character(char_data)
                    
                    # Initialize runtime state if not present
                    if restored_char_id not in self.game_state.characters:
                        self.game_state.characters[restored_char_id] = {
                            "position": {"x": 0, "y": 0},
                            "hidden": False,
                            "initiative": 0,
                            "runtime_conditions": [],
                            "last_action": None,
                            "session_notes": []
                        }
                except Exception as e:
                    logger.warning(f"Failed to restore character {char_id}: {e}")
        
        # Restore policy profile if specified
        if "policy_profile" in state_data:
            try:
                from .policy import PolicyProfile
                profile_name = state_data["policy_profile"]
                if profile_name == "house":
                    new_profile = PolicyProfile.HOUSE
                elif profile_name == "raw":
                    new_profile = PolicyProfile.RAW
                elif profile_name == "easy":
                    new_profile = PolicyProfile.EASY
                else:
                    new_profile = PolicyProfile.HOUSE  # Default fallback
                
                self.policy_engine.change_profile(new_profile)
                print(f"🛡️ Restored policy profile: {profile_name}")
            except Exception as e:
                logger.warning(f"Failed to restore policy profile: {e}")
        
        print("📥 Game state imported successfully")
    
    def set_decision_logger(self, decision_logger):
        """Set decision logger for step 7 of pipeline"""
        self.decision_logger = decision_logger
        print("📝 Decision logger connected to Game Engine")
    
    # Roshar-specific state management methods
    
    def spend_character_investiture(self, character_id: str, amount: int, surge_name: str = None) -> bool:
        """Spend investiture points and track usage in runtime state"""
        # Use CharacterManager as authority for investiture spending
        success = self.character_manager.spend_investiture(character_id, amount)
        
        if success and character_id in self.game_state.characters:
            # Track runtime usage
            runtime_state = self.game_state.characters[character_id]
            runtime_state["investiture_spent_this_turn"] += amount
            
            # Track surge usage if specified
            if surge_name and surge_name not in runtime_state["surges_used_this_scene"]:
                runtime_state["surges_used_this_scene"].append(surge_name)
            
            logger.info(f"🌟 {character_id} spent {amount} investiture for {surge_name or 'unknown surge'}")
        
        return success
    
    def update_spren_interaction(self, character_id: str, interaction_type: str):
        """Update spren interaction state in runtime"""
        if character_id in self.game_state.characters:
            self.game_state.characters[character_id]["spren_interaction_state"] = interaction_type
            logger.info(f"🧚 Updated spren interaction for {character_id}: {interaction_type}")
    
    def reset_turn_resources(self, character_id: str):
        """Reset per-turn resources (called at start of new turn)"""
        if character_id in self.game_state.characters:
            runtime_state = self.game_state.characters[character_id]
            runtime_state["investiture_spent_this_turn"] = 0
            logger.info(f"🔄 Reset turn resources for {character_id}")
    
    def reset_scene_resources(self, character_id: str):
        """Reset per-scene resources (called at start of new scene)"""
        if character_id in self.game_state.characters:
            runtime_state = self.game_state.characters[character_id]
            runtime_state["surges_used_this_scene"] = []
            runtime_state["spren_interaction_state"] = "normal"
            logger.info(f"🎬 Reset scene resources for {character_id}")
    
    def get_character_runtime_state(self, character_id: str) -> Dict[str, Any]:
        """Get character's runtime state from GameEngine"""
        if character_id in self.game_state.characters:
            return self.game_state.characters[character_id].copy()
        return {}
    
    def get_character_full_state(self, character_id: str) -> Dict[str, Any]:
        """Get complete character state (CharacterManager + runtime state)"""
        # Get persistent character data from CharacterManager
        char_summary = self.character_manager.get_character_summary(character_id)
        roshar_summary = self.character_manager.get_roshar_character_summary(character_id)
        
        # Get runtime state from GameEngine
        runtime_state = self.get_character_runtime_state(character_id)
        
        return {
            "character_data": char_summary,
            "roshar_data": roshar_summary,
            "runtime_state": runtime_state,
            "timestamp": time.time()
        }
    
    # Radiant Oath Progression Methods
    
    def speak_oath(self, character_id: str, oath_text: str, trigger_event: str = None) -> Dict[str, Any]:
        """Handle a character speaking an oath to advance their ideal"""
        if character_id not in self.game_state.characters:
            return {"success": False, "reason": "Character not found in game state"}
        
        # Check if character can advance
        can_advance = self.character_manager.can_advance_ideal(character_id)
        if not can_advance["can_advance"]:
            return {"success": False, "reason": can_advance["reason"]}
        
        # Advance the ideal through CharacterManager
        success = self.character_manager.advance_ideal(character_id, oath_text)
        
        if success:
            # Update game state to track oath progression
            runtime_state = self.game_state.characters[character_id]
            if "oaths_spoken" not in runtime_state:
                runtime_state["oaths_spoken"] = []
            
            oath_record = {
                "ideal_level": self.character_manager.get_ideal_level(character_id),
                "oath_text": oath_text,
                "trigger_event": trigger_event or "Unknown trigger",
                "timestamp": time.time()
            }
            runtime_state["oaths_spoken"].append(oath_record)
            
            # Set campaign flag for story progression
            ideal_level = self.character_manager.get_ideal_level(character_id)
            self.set_campaign_flag(f"{character_id}_ideal_level", ideal_level)
            self.set_campaign_flag(f"{character_id}_last_oath", oath_text)
            
            # Add narrative context
            self.update_narrative_context({
                "last_oath_event": f"{self.character_manager.characters[character_id].name} spoke their {self.character_manager.get_ideal_name(character_id)} Ideal",
                "oath_progression_active": True
            })
            
            logger.info(f"🎮 GameEngine: Recorded oath progression for {character_id}")
            
            return {
                "success": True,
                "new_ideal_level": ideal_level,
                "ideal_name": self.character_manager.get_ideal_name(character_id),
                "oath_text": oath_text,
                "benefits_granted": True
            }
        
        return {"success": False, "reason": "Failed to advance ideal"}
    
    def check_oath_readiness(self, character_id: str) -> Dict[str, Any]:
        """Check if character is ready to speak their next oath"""
        if character_id not in self.game_state.characters:
            return {"ready": False, "reason": "Character not found"}
        
        # Use CharacterManager to check advancement eligibility
        can_advance = self.character_manager.can_advance_ideal(character_id)
        
        if can_advance["can_advance"]:
            # Additional game state checks could go here
            # (e.g., story progression, recent events, etc.)
            return {
                "ready": True,
                "current_level": can_advance["current_level"],
                "next_level": can_advance["next_level"],
                "next_ideal_name": can_advance["next_ideal_name"],
                "requirements_met": True
            }
        
        return {
            "ready": False,
            "reason": can_advance["reason"],
            "current_level": self.character_manager.get_ideal_level(character_id)
        }
    
    def get_oath_history(self, character_id: str) -> List[Dict[str, Any]]:
        """Get history of oaths spoken by character"""
        if character_id not in self.game_state.characters:
            return []
        
        runtime_state = self.game_state.characters[character_id]
        return runtime_state.get("oaths_spoken", [])
    
    def trigger_oath_opportunity(self, character_id: str, trigger_description: str, 
                                suggested_oath: str = None) -> Dict[str, Any]:
        """Create an opportunity for character to speak their next oath"""
        readiness = self.check_oath_readiness(character_id)
        
        if not readiness["ready"]:
            return {
                "opportunity_created": False,
                "reason": readiness["reason"]
            }
        
        # Update narrative context to reflect oath opportunity
        character_name = self.character_manager.characters[character_id].name
        next_ideal = readiness["next_ideal_name"]
        
        self.update_narrative_context({
            "oath_opportunity_active": True,
            "oath_opportunity_character": character_name,
            "oath_opportunity_trigger": trigger_description,
            "oath_opportunity_ideal": next_ideal
        })
        
        # Add story hook for oath progression
        self.add_story_hook(
            f"{character_name} faces a moment that could lead to speaking their {next_ideal} Ideal",
            "high"
        )
        
        logger.info(f"🌟 Oath opportunity created for {character_name} ({next_ideal} Ideal)")
        logger.debug(f"   Trigger: {trigger_description}")
        
        return {
            "opportunity_created": True,
            "character_name": character_name,
            "next_ideal": next_ideal,
            "trigger": trigger_description,
            "suggested_oath": suggested_oath
        }
    
    def debug_print_party_summary(self, turn_number: int = None):
        """Print a condensed summary of all party members"""
        if not self.game_state.characters:
            logger.error("DEBUG: No characters in party")
            return
        
        turn_info = f" - Turn {turn_number}" if turn_number else ""
        logger.info(f"\n{'='*50}")
        logger.info(f"🎭 PARTY SUMMARY{turn_info}")
        logger.info(f"{'='*50}")
        
        for char_id in self.game_state.characters.keys():
            char_summary = self.character_manager.get_character_summary(char_id)
            roshar_summary = self.character_manager.get_roshar_character_summary(char_id)
            runtime_state = self.get_character_runtime_state(char_id)
            
            name = char_summary.get('name', 'Unknown')
            level = char_summary.get('level', 0)
            ideal_name = roshar_summary.get('ideal_name', 'No Oaths')
            
            hp = char_summary.get('hit_points', {})
            hp_current = hp.get('current', 0)
            hp_max = hp.get('maximum', 0)
            
            investiture = roshar_summary.get('investiture_points', {})
            inv_current = investiture.get('current', 0)
            inv_max = investiture.get('maximum', 0)
            
            conditions = char_summary.get('conditions', []) + runtime_state.get('runtime_conditions', [])
            condition_str = f" [{', '.join(conditions)}]" if conditions else ""
            
            # Get action count for this turn
            turn_actions = len(runtime_state.get('current_turn_actions', []))
            action_str = f" | {turn_actions} actions this turn" if turn_actions > 0 else ""
            
            # Get last action
            last_action = runtime_state.get('last_action', 'No recent action')
            if last_action and len(last_action) > 40:
                last_action = last_action[:37] + "..."
            
            logger.info(f"👤 {name} (L{level} {ideal_name}): HP {hp_current}/{hp_max}, Investiture {inv_current}/{inv_max}{condition_str}{action_str}")
            logger.debug(f"   Last Action: {last_action}")
        
        logger.info(f"{'='*50}")
    
    # Action Tracking Methods
    
    def log_character_action(self, character_id: str, action_type: str, action_description: str, 
                           turn_number: int = None, additional_data: Dict[str, Any] = None) -> bool:
        """Log an action taken by a character during gameplay"""
        # Log to CharacterManager (persistent storage)
        success = self.character_manager.log_character_action(
            character_id, action_type, action_description, turn_number, additional_data
        )
        
        # Also track in runtime state for current turn
        if success and character_id in self.game_state.characters:
            runtime_state = self.game_state.characters[character_id]
            
            action_entry = {
                "action_type": action_type,
                "description": action_description,
                "turn_number": turn_number,
                "timestamp": time.time(),
                "additional_data": additional_data or {}
            }
            
            runtime_state["current_turn_actions"].append(action_entry)
            runtime_state["turn_action_count"] += 1
            runtime_state["last_action"] = action_description
            
            logger.info(f"🎬 GameEngine: Logged action for {character_id}: {action_description}")
        
        return success
    
    def log_player_input_as_action(self, character_id: str, player_input: str, turn_number: int = None) -> bool:
        """Log player input as a character action"""
        return self.log_character_action(
            character_id=character_id,
            action_type="player_input",
            action_description=player_input,
            turn_number=turn_number,
            additional_data={"raw_input": player_input}
        )
    
    def log_skill_check_action(self, character_id: str, skill: str, dc: int, result: bool, 
                              turn_number: int = None, context: str = "") -> bool:
        """Log a skill check as an action"""
        result_text = "succeeded" if result else "failed"
        description = f"Made a {skill} check (DC {dc}) and {result_text}"
        if context:
            description += f" - {context}"
        
        return self.log_character_action(
            character_id=character_id,
            action_type="skill_check",
            action_description=description,
            turn_number=turn_number,
            additional_data={
                "skill": skill,
                "dc": dc,
                "success": result,
                "context": context
            }
        )
    
    def log_combat_action(self, character_id: str, action_description: str, target: str = None,
                         damage: int = None, turn_number: int = None) -> bool:
        """Log a combat action"""
        return self.log_character_action(
            character_id=character_id,
            action_type="combat",
            action_description=action_description,
            turn_number=turn_number,
            additional_data={
                "target": target,
                "damage": damage
            }
        )
    
    def log_dialogue_action(self, character_id: str, dialogue_text: str, npc_target: str = None,
                           turn_number: int = None) -> bool:
        """Log dialogue/roleplay action"""
        return self.log_character_action(
            character_id=character_id,
            action_type="dialogue",
            action_description=dialogue_text,
            turn_number=turn_number,
            additional_data={
                "npc_target": npc_target,
                "dialogue_type": "speech"
            }
        )
    
    def log_movement_action(self, character_id: str, from_position: Dict[str, int], 
                           to_position: Dict[str, int], turn_number: int = None) -> bool:
        """Log movement action"""
        description = f"Moved from ({from_position.get('x', 0)}, {from_position.get('y', 0)}) to ({to_position.get('x', 0)}, {to_position.get('y', 0)})"
        
        return self.log_character_action(
            character_id=character_id,
            action_type="movement",
            action_description=description,
            turn_number=turn_number,
            additional_data={
                "from_position": from_position,
                "to_position": to_position
            }
        )
    
    def log_investiture_action(self, character_id: str, surge_name: str, investiture_spent: int,
                              effect_description: str, turn_number: int = None) -> bool:
        """Log investiture/surgebinding action"""
        description = f"Used {surge_name} surge, spending {investiture_spent} investiture: {effect_description}"
        
        return self.log_character_action(
            character_id=character_id,
            action_type="surgebinding",
            action_description=description,
            turn_number=turn_number,
            additional_data={
                "surge_name": surge_name,
                "investiture_spent": investiture_spent,
                "effect": effect_description
            }
        )
    
    def start_new_turn(self, turn_number: int):
        """Start a new turn - reset turn-specific action tracking"""
        for char_id in self.game_state.characters.keys():
            runtime_state = self.game_state.characters[char_id]
            runtime_state["current_turn_actions"] = []
            runtime_state["turn_action_count"] = 0
            runtime_state["investiture_spent_this_turn"] = 0
        
        logger.info(f"🔄 Started turn {turn_number} - reset turn-specific tracking")
    
    def get_character_turn_actions(self, character_id: str) -> List[Dict[str, Any]]:
        """Get actions taken by character in current turn"""
        if character_id in self.game_state.characters:
            return self.game_state.characters[character_id].get("current_turn_actions", [])
        return []
    
    def get_character_action_history(self, character_id: str, limit: int = None) -> List[Dict[str, Any]]:
        """Get character's full action history from CharacterManager"""
        return self.character_manager.get_character_action_history(character_id, limit)
    
    def get_recent_party_actions(self, turn_limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent actions across all party members"""
        return self.character_manager.get_recent_party_actions(turn_limit)
    
    def update_narrative_context(self, context_updates: Dict[str, Any]):
        """Update narrative context for scenario generation"""
        self.game_state.narrative_context.update(context_updates)
        logger.debug(f"📖 Updated narrative context: {list(context_updates.keys())}")
    
    def update_location_context(self, context_updates: Dict[str, Any]):
        """Update location context for scenario generation"""
        self.game_state.location_context.update(context_updates)
        logger.info(f"📍 Updated location context: {list(context_updates.keys())}")
    
    def update_quest_context(self, context_updates: Dict[str, Any]):
        """Update quest context for scenario generation"""
        self.game_state.quest_context.update(context_updates)
        logger.debug(f"🎯 Updated quest context: {list(context_updates.keys())}")
    
    def get_scenario_context(self) -> Dict[str, Any]:
        """
        Get comprehensive scenario context for enhanced scenario generation
        Returns all context needed for the 9-category system - BREAKING CHANGE: Uses campaign_config
        """
        # Get party context from character manager
        party_context = self.character_manager.get_party_context()
        
        # Get Roshar-specific party context
        roshar_party_context = self.character_manager.get_party_roshar_context()
        
        # Build campaign data from CampaignConfig
        campaign_data = {}
        if self.campaign_config:
            campaign_data = {
                "campaign_started": True,
                "campaign_name": self.campaign_config.name,
                "campaign_npcs": [npc.name for npc in self.campaign_config.key_npcs],
                "campaign_locations": [loc.name for loc in self.campaign_config.locations],
                "campaign_quests": self.campaign_config.quests,
                "campaign_difficulty": self.campaign_config.difficulty,
                "campaign_theme": self.campaign_config.theme,
                "level_range": self.campaign_config.level_range
            }
        
        # Collect runtime state for all characters
        character_runtime_states = {}
        for char_id in self.game_state.characters.keys():
            character_runtime_states[char_id] = self.get_character_runtime_state(char_id)
        
        return {
            "narrative_context": self.game_state.narrative_context,
            "location_context": self.game_state.location_context,
            "quest_context": self.game_state.quest_context,
            "party_context": party_context,
            "roshar_party_context": roshar_party_context,
            "character_runtime_states": character_runtime_states,
            "environment": self.game_state.environment,
            "campaign_flags": self.game_state.campaign_flags,
            "campaign_data": campaign_data,
            "session_data": self.game_state.session_data,
            "policy_profile": self.policy_engine.active_profile_type.value,
            "timestamp": time.time()
        }
    
    def add_story_hook(self, hook: str, priority: str = "normal"):
        """Add a story hook to narrative context"""
        if "story_hooks" not in self.game_state.narrative_context:
            self.game_state.narrative_context["story_hooks"] = []
        
        hook_entry = {"text": hook, "priority": priority, "added_time": time.time()}
        self.game_state.narrative_context["story_hooks"].append(hook_entry)
        logger.info(f"🎣 Added story hook: {hook} (priority: {priority})")
    
    def add_quest_objective(self, objective: str, quest_name: str = "Main Quest"):
        """Add a quest objective to quest context"""
        if "pending_objectives" not in self.game_state.quest_context:
            self.game_state.quest_context["pending_objectives"] = []
        
        objective_entry = {
            "text": objective,
            "quest_name": quest_name,
            "added_time": time.time()
        }
        self.game_state.quest_context["pending_objectives"].append(objective_entry)
        logger.info(f"✓ Added quest objective: {objective} ({quest_name})")
    
    def complete_quest_objective(self, objective_text: str):
        """Move objective from pending to completed"""
        pending = self.game_state.quest_context.get("pending_objectives", [])
        completed = self.game_state.quest_context.get("completed_objectives", [])
        
        for i, obj in enumerate(pending):
            if obj["text"] == objective_text:
                completed_obj = obj.copy()
                completed_obj["completion_time"] = time.time()
                completed.append(completed_obj)
                pending.pop(i)
                logger.info(f"✅ Completed objective: {objective_text}")
                break
        
        self.game_state.quest_context["completed_objectives"] = completed
        self.game_state.quest_context["pending_objectives"] = pending
    
    def set_location(self, location_name: str, location_type: str = "general",
                    description: str = "", features: List[str] = None):
        """Set current location with context"""
        self.game_state.location_context.update({
            "current_location": location_name,
            "location_type": location_type,
            "description": description,
            "features": features or [],
            "entry_time": time.time()
        })
        logger.info(f"🏔️ Moved to location: {location_name} ({location_type})")
    
    def get_campaign_data(self, key: str, default: Any = None) -> Any:
        """Get campaign data value from CampaignConfig - BREAKING CHANGE: Read-only"""
        if not self.campaign_config:
            return default
            
        # Map key to CampaignConfig attributes
        if key == "campaign_name":
            return self.campaign_config.name
        elif key == "campaign_difficulty":
            return self.campaign_config.difficulty
        elif key == "campaign_theme":
            return self.campaign_config.theme
        elif key == "level_range":
            return self.campaign_config.level_range
        elif key == "campaign_npcs":
            return [npc.name for npc in self.campaign_config.key_npcs]
        elif key == "campaign_locations":
            return [loc.name for loc in self.campaign_config.locations]
        elif key == "campaign_quests":
            return self.campaign_config.quests
        elif key == "starting_location":
            return self.campaign_config.starting_location
        elif key == "campaign_started":
            return True if self.campaign_config else False
        else:
            return default
    
    def get_narrative_context(self) -> Dict[str, Any]:
        """Get current narrative context"""
        return self.game_state.narrative_context
    
    def get_location_context(self) -> Dict[str, Any]:
        """Get current location context"""
        return self.game_state.location_context
    
    def get_quest_context(self) -> Dict[str, Any]:
        """Get current quest context"""
        return self.game_state.quest_context
    
    def process_scenario_state_updates(self, scenario_data: Dict[str, Any], turn_number: int):
        """Process scenario data and update authoritative game state"""
        
        # GameEngine is authoritative for all runtime state updates
        narrative_updates = {
            "current_scene": scenario_data.get("scene", "")[:100] + "...",
            "last_scenario_type": scenario_data.get("scenario_type", "unknown"),
            "scenario_confidence": scenario_data.get("confidence", 0),
            "turn_number": turn_number
        }
        self.update_narrative_context(narrative_updates)
        
        # Process state changes using existing authoritative methods
        state_changes = scenario_data.get("state_changes", {})
        if state_changes:
            if "location" in state_changes:
                self.set_location(state_changes["location"])
                
            if "flags" in state_changes:
                for flag_name, flag_value in state_changes["flags"].items():
                    self.set_campaign_flag(flag_name, flag_value)
            
            if "story_hooks" in state_changes:
                for hook in state_changes["story_hooks"]:
                    self.add_story_hook(hook, "normal")
            
            if "quest_objectives" in state_changes:
                for objective in state_changes["quest_objectives"]:
                    self.add_quest_objective(objective)


# Factory function for easy integration - BREAKING CHANGE: Accepts CampaignConfig
def create_game_engine(policy_profile: PolicyProfile = PolicyProfile.RAW,
                      campaign_config: Optional[CampaignConfig] = None) -> GameEngine:
    """Factory function to create configured game engine with CampaignConfig"""
    return GameEngine(policy_profile, campaign_config)


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
    logger.info(f"7-step pipeline result: {result}")
    
    # Test contested check
    # Add second character for contest
    char2_data = test_character.copy()
    char2_data["character_id"] = "guard"
    char2_data["name"] = "Guard"
    char2_id = engine.add_character(char2_data)
    
    contest_result = engine.process_contested_check(
        char_id, "stealth", char2_id, "perception"
    )
    logger.info(f"Contested check result: {contest_result}")
    
    # Show game statistics
    stats = engine.get_game_statistics()
    logger.info(f"Game statistics: {stats}")