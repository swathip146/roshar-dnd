"""
Game Engine - Stage 3 Week 11-12
Authoritative state writer with 7-step pipeline - From Original Plan
"""

from typing import Dict, Any, Optional, List, TypedDict
import re
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
    current_scene_full: str  # Full untruncated scene text for combat/scenario continuity
    last_scenario: Dict[str, Any]  # Complete last scenario with scene, choices, gm_notes
    last_player_action: str  # Last player input/choice
    pacing: str
    tension_level: str
    narrative_beats: List[str]
    # Plan 2.2: compressed record of beats that aged out of the verbatim
    # window, so a long campaign keeps its spine instead of losing it.
    narrative_chronicle: List[str]
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
                "narrative_chronicle": [],
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

        # Plan 2.1: honour an explicitly requested DC.
        #
        # This used to be `dc = rules_result.dc` unconditionally, so the DC the
        # caller passed in was silently discarded and EVERY check resolved
        # against the Rules Enforcer's derived DC. Measured before the fix:
        # DC 5 and DC 25 both became 14 and both succeeded ~58% of the time —
        # i.e. difficulty had no effect on outcomes.
        #
        # The LLM's suggested_dc is the whole point of 2.1, so an explicit DC
        # wins; the derived value stays the default when none is given.
        requested_dc = check_request.get("dc")
        if requested_dc is not None:
            try:
                requested_dc = int(requested_dc)
                if requested_dc > 0:
                    dc = requested_dc
                    dc_source = "requested"
            except (TypeError, ValueError):
                logger.warning(f"⚠️ Ignoring non-numeric requested DC: {requested_dc!r}")
        
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
        # PHASE 2: Use dnd_engine_wrapper if available, otherwise fallback to dice_roller
        dnd_wrapper = check_request.get("_dnd_engine_wrapper_ref")
        if dnd_wrapper:
            # Use dnd_engine for mechanically accurate rolls
            wrapper_result = dnd_wrapper.execute_skill_check(
                character_id=check_request["actor"],
                skill=check_request.get("skill", ""),
                dc=adjusted_dc,
                advantage=advantage_state.get("advantage", False),
                disadvantage=advantage_state.get("disadvantage", False)
            )

            # Convert wrapper result to expected format
            roll_result = {
                "total": wrapper_result["roll"],
                "raw_rolls": [wrapper_result["natural_roll"]],
                "selected_roll": wrapper_result["natural_roll"],
                "roll_breakdown": wrapper_result.get("breakdown", {})
            }
        else:
            # Fallback: Use original dice roller
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
                "campaign_npcs": [npc.get("name", "") for npc in self.campaign_config.key_npcs],
                "campaign_locations": [loc.get("name", "") for loc in self.campaign_config.locations],
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
            # Plan 0.3 fix: use to_dict() for lossless serialization, not get_character_summary()
            # which is an analytics view that drops HP, equipment, AC, spell_slots, and Roshar fields
            "character_data": {
                char_id: self.character_manager.characters[char_id].to_dict()
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
                    description: str = None, features: List[str] = None):
        """
        Set current location with context.

        Plan 2.6: `description` and `features` used to default to "" and [], so
        calling set_location(name) — which is what state_changes.location does —
        WIPED the current location's description and features. They now default
        to None and are only overwritten when actually supplied.
        """
        updates = {
            "current_location": location_name,
            "location_type": location_type,
            "entry_time": time.time(),
        }
        if description is not None:
            updates["description"] = description
        if features is not None:
            updates["features"] = features
        self.game_state.location_context.update(updates)
        logger.info(f"🏔️ Moved to location: {location_name} ({location_type})")

    # ------------------------------------------------------------------
    # Travel and the world graph (plan 2.6)
    #
    # `exits`, `hazards` and `npcs_present` were declared in LocationContext
    # and NEVER written, and no travel verb existed at all.
    # ------------------------------------------------------------------

    def register_location(self, name: str, description: str = "",
                          features: List[str] = None, exits: List[str] = None,
                          hazards: List[str] = None,
                          location_type: str = "general") -> None:
        """Add a location to the world graph (plan 2.6)."""
        graph = self.game_state.location_context.setdefault("known_locations", {})
        graph[name] = {
            "name": name,
            "description": description,
            "features": features or [],
            "exits": exits or [],
            "hazards": hazards or [],
            "location_type": location_type,
            "visited": graph.get(name, {}).get("visited", False),
        }
        logger.debug(f"🗺️  Registered location '{name}' "
                     f"(exits: {exits or []})")

    def load_locations_from_campaign(self) -> int:
        """
        Build the world graph from CampaignConfig (plan 2.6).

        Campaign locations were parsed, counted and logged, then never turned
        into anything the player could travel between.
        """
        campaign = self.campaign_config
        if not campaign:
            return 0

        entries = getattr(campaign, "locations", None) or []
        names = []
        for entry in entries:
            if isinstance(entry, dict):
                name = str(entry.get("name", "")).strip()
                description = entry.get("description", "")
                features = entry.get("features") or []
                hazards = entry.get("hazards") or []
            else:
                name, description, features, hazards = str(entry).strip(), "", [], []
            if name:
                names.append(name)
                self.register_location(name, description, features,
                                       exits=[], hazards=hazards)

        # With no authored adjacency, make campaign locations mutually
        # reachable — better than a graph with no edges at all.
        graph = self.game_state.location_context.get("known_locations", {})
        for name in names:
            graph[name]["exits"] = [n for n in names if n != name]

        logger.info(f"🗺️  Loaded {len(names)} campaign location(s) into the world graph")
        return len(names)

    def get_available_exits(self) -> List[str]:
        """Where the party can go from here (plan 2.6)."""
        graph = self.game_state.location_context.get("known_locations", {})
        current = self.game_state.location_context.get("current_location", "")
        node = graph.get(current)
        if node:
            return list(node.get("exits", []))
        # Unknown current location: offer everything known.
        return [n for n in graph if n != current]

    def travel_to(self, destination: str) -> Dict[str, Any]:
        """
        Move the party to a new location (plan 2.6).

        No travel verb existed before, so the party could never actually go
        anywhere — the three-artifact structure of Shards of Honor (D6) was
        unreachable.
        """
        graph = self.game_state.location_context.setdefault("known_locations", {})
        current = self.game_state.location_context.get("current_location", "")

        # Tolerate case and partial names from an LLM or a player.
        match = None
        target = destination.strip().lower()
        for name in graph:
            if name.lower() == target:
                match = name
                break
        if match is None:
            # Partial match on WHOLE WORDS only. A naive substring test matched
            # "A" inside "Shattered Plains" (same bug class as the combat
            # routing substring match), so travelling anywhere new was refused.
            target_words = set(target.replace(",", " ").split())
            best = None
            for name in graph:
                name_words = set(name.lower().replace(",", " ").split())
                shared = target_words & name_words
                if shared and (len(max(shared, key=len)) >= 4):
                    if best is None or len(shared) > best[0]:
                        best = (len(shared), name)
            match = best[1] if best else None

        discovered = False
        if match is None:
            # Travel somewhere unregistered: record it rather than refuse, so
            # the DM can invent places mid-story, and link it to where we are.
            self.register_location(destination, exits=[current] if current else [])
            match = destination
            discovered = True
            if current and current in graph:
                current_exits = graph[current].setdefault("exits", [])
                if match not in current_exits:
                    current_exits.append(match)
            logger.info(f"🗺️  Discovered new location '{destination}'")

        exits = self.get_available_exits()
        # A freshly discovered location is reachable by definition.
        reachable = discovered or (not exits) or (match in exits)

        if not reachable:
            logger.warning(f"⚠️ '{match}' is not reachable from '{current}'")
            return {"success": False, "reason": f"{match} is not reachable from {current}",
                    "available_exits": exits}

        node = graph[match]
        node["visited"] = True
        self.set_location(
            match,
            location_type=node.get("location_type", "general"),
            description=node.get("description") or None,
            features=node.get("features") or None,
        )
        self.game_state.location_context["hazards"] = node.get("hazards", [])
        self.game_state.location_context["exits"] = node.get("exits", [])

        # Travel takes time.
        self.advance_time(hours=4, reason=f"travel to {match}")

        logger.info(f"🚶 Travelled from '{current}' to '{match}'")
        return {
            "success": True,
            "from": current,
            "to": match,
            "description": node.get("description", ""),
            "hazards": node.get("hazards", []),
            "available_exits": node.get("exits", []),
        }

    # ------------------------------------------------------------------
    # Game clock and highstorms (plan 2.6)
    #
    # There was no clock and no day counter. update_environment() had zero
    # callers, so weather never changed, and the campaign's own
    # "WEATHER: Highstorm-approaching" was parsed and dropped.
    # ------------------------------------------------------------------

    # Rosharan highstorms recur roughly every few days.
    HIGHSTORM_INTERVAL_DAYS = 5

    def get_game_time(self) -> Dict[str, Any]:
        """Current in-world time (plan 2.6)."""
        env = self.game_state.environment
        total_hours = env.get("elapsed_hours", 0)
        day = total_hours // 24 + 1
        hour = total_hours % 24
        if hour < 6:
            part = "night"
        elif hour < 12:
            part = "morning"
        elif hour < 18:
            part = "afternoon"
        else:
            part = "evening"
        return {
            "day": day,
            "hour": hour,
            "part_of_day": part,
            "elapsed_hours": total_hours,
            "days_until_highstorm": self.days_until_highstorm(),
        }

    def days_until_highstorm(self) -> int:
        """Days until the next highstorm (plan 2.6)."""
        day = self.game_state.environment.get("elapsed_hours", 0) // 24 + 1
        into_cycle = (day - 1) % self.HIGHSTORM_INTERVAL_DAYS
        # 0 means the storm lands TODAY. Without this the counter jumped
        # 1 -> 5 and the weather never actually became "highstorm".
        return into_cycle if into_cycle == 0 else (
            self.HIGHSTORM_INTERVAL_DAYS - into_cycle
        )

    def advance_time(self, hours: int = 0, days: int = 0,
                     reason: str = "") -> Dict[str, Any]:
        """
        Advance the game clock, updating weather as highstorms approach (2.6).
        """
        env = self.game_state.environment
        added = max(0, int(hours)) + max(0, int(days)) * 24
        env["elapsed_hours"] = env.get("elapsed_hours", 0) + added

        time_info = self.get_game_time()
        until = time_info["days_until_highstorm"]
        if until <= 0:
            weather = "highstorm"
        elif until == 1:
            weather = "highstorm-imminent"
        elif until == 2:
            weather = "highstorm-approaching"
        else:
            weather = "clear"

        # Daylight follows the clock.
        lighting = {"night": "dark", "morning": "bright",
                    "afternoon": "bright", "evening": "dim"}[time_info["part_of_day"]]

        self.update_environment({"weather": weather, "lighting": lighting})

        logger.info(
            f"🕐 +{added}h ({reason or 'time passes'}) -> day {time_info['day']} "
            f"{time_info['part_of_day']}, weather {weather}"
        )
        return {**time_info, "weather": weather, "lighting": lighting}

    def load_environment_from_campaign(self) -> bool:
        """
        Apply the campaign's authored starting weather/lighting (plan 2.6).

        `WEATHER: Highstorm-approaching` and `LIGHTING: stormlit-dusk` were in
        the campaign file and never loaded.
        """
        campaign = self.campaign_config
        if not campaign:
            return False
        updates = {}
        for key in ("weather", "lighting", "terrain"):
            value = getattr(campaign, key, None)
            if value:
                updates[key] = value
        if updates:
            self.update_environment(updates)
            logger.info(f"🌦️  Loaded campaign environment: {updates}")
            return True
        return False
    
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
    
    # Plan 2.2: how many narrative beats to keep verbatim. Enough for the DM to
    # reference recent history without unbounded prompt growth.
    MAX_NARRATIVE_BEATS = 12
    BEAT_SUMMARY_CHARS = 400
    # Beats that age out of the window are folded into a rolling chronicle rather
    # than deleted (see _append_narrative_beat). Bounded too, or the prompt grows
    # without limit over a long campaign.
    MAX_CHRONICLE_ENTRIES = 20
    CHRONICLE_ENTRY_CHARS = 160

    def _append_narrative_beat(self, scene_text: str, turn_number: int) -> None:
        """
        Record one narrative beat, with ROLLING SUMMARIZATION (plan 2.2).

        Two problems, fixed in order:

        1. `last_scenario` was a single slot each turn overwrote, so turn N-2 was
           gone and the DM had a one-turn memory. `narrative_beats` existed in the
           schema and nothing ever wrote to it.
        2. Beats past the window were then `del`'d outright. That bounded the
           prompt but silently destroyed the early campaign: by turn 30 the DM had
           no idea the party had ever sworn an oath or lost a companion, which is
           precisely the continuity 2.2 promised. The plan said "rolling
           summarization"; truncate-and-drop is not that.

        A beat leaving the verbatim window is now compressed into
        `narrative_chronicle` — a shorter, older-first record that survives. The
        chronicle is itself bounded, so prompt size stays predictable while the
        campaign's spine is preserved.

        Compression is DETERMINISTIC (first sentence, then a character cap), not an
        LLM call. Summarising with the LLM here would bill a token on every turn,
        could fail mid-turn, and would make the same campaign produce different
        history on a replay.
        """
        if not scene_text:
            return
        try:
            narrative = self.game_state.narrative_context
            beats = narrative.setdefault("narrative_beats", [])
            summary = scene_text.strip()
            if len(summary) > self.BEAT_SUMMARY_CHARS:
                summary = summary[:self.BEAT_SUMMARY_CHARS].rstrip() + "…"
            beats.append(f"[Turn {turn_number}] {summary}")

            # Fold anything past the window into the chronicle instead of dropping.
            while len(beats) > self.MAX_NARRATIVE_BEATS:
                self._chronicle(beats.pop(0))

            logger.debug(f"📖 Narrative beats: {len(beats)} verbatim, "
                         f"{len(narrative.get('narrative_chronicle', []))} chronicled")
        except Exception as e:
            logger.warning(f"⚠️ Could not record narrative beat: {e}")

    def _chronicle(self, beat: str) -> None:
        """Compress one aged-out beat into the rolling chronicle."""
        narrative = self.game_state.narrative_context
        chronicle = narrative.setdefault("narrative_chronicle", [])
        entry = self._compress_beat(beat)
        if entry:
            chronicle.append(entry)
        if len(chronicle) > self.MAX_CHRONICLE_ENTRIES:
            # The chronicle is itself bounded. Drop from the MIDDLE, keeping the
            # opening of the campaign (how it began) and the recent past, which is
            # what continuity actually needs.
            keep_head = self.MAX_CHRONICLE_ENTRIES // 4
            keep_tail = self.MAX_CHRONICLE_ENTRIES - keep_head
            narrative["narrative_chronicle"] = (
                chronicle[:keep_head] + chronicle[-keep_tail:])

    def _compress_beat(self, beat: str) -> str:
        """
        One beat -> one short line. Deterministic: first sentence, then a cap.

        Keeps the `[Turn N]` prefix so the chronicle stays ordered and the DM can
        tell how long ago something happened.
        """
        text = (beat or "").strip()
        if not text:
            return ""

        prefix = ""
        match = re.match(r"(\[Turn \d+\])\s*(.*)", text, flags=re.DOTALL)
        if match:
            prefix, text = match.group(1), match.group(2)

        # First sentence carries the event; the rest is usually scene-setting.
        sentence = re.split(r"(?<=[.!?])\s", text.strip(), maxsplit=1)[0]
        if len(sentence) > self.CHRONICLE_ENTRY_CHARS:
            sentence = sentence[:self.CHRONICLE_ENTRY_CHARS].rstrip() + "…"
        return f"{prefix} {sentence}".strip()

    def _apply_location_change(self, raw_location: Any) -> bool:
        """
        Apply the model's `state_changes.location`, rejecting narration.

        The scenario prompt lists "location" directly beneath "narrative", so the
        model wrote sentences into it and set_location() took them verbatim:

            🏔️ Moved to location: Playtest Ridge is now understood as a site of
               recent and significant conflict, a gateway to the wider devastation.

        That corrupts the location graph, because `known_locations` is keyed by
        name and travel_to() matches against those keys — every exit stops
        resolving once a key is a paragraph. A place NAME is short; anything
        sentence-shaped is narration that belongs in the beat log.

        Returns True if the location was changed.
        """
        if not isinstance(raw_location, str):
            return False

        # Strip wrapping punctuation in any order: '"Kholinar".' shows up as
        # often as 'Kholinar.' or '"Kholinar"'.
        candidate = raw_location.strip().strip('\'" .\t\n')
        if not candidate:
            return False

        current = self.game_state.location_context.get("current_location", "")
        if candidate == current:
            return False

        graph = self.game_state.location_context.setdefault("known_locations", {})

        # An exact (case-insensitive) hit on a known place is always safe, even
        # if it were long, so check that before any shape heuristics.
        for name in graph:
            if name.lower() == candidate.lower():
                if name != current:
                    self.set_location(name)
                    return True
                return False

        # Shape check. Real Rosharan place names are short ("Kholinar", "Urithiru",
        # "The Shattered Plains"); prose is not.
        words = candidate.split()
        looks_like_prose = (
            len(words) > 6
            or len(candidate) > 60
            or any(marker in candidate.lower() for marker in
                   (" is ", " are ", " was ", " now ", " remains ", " becomes ",
                    " has ", " the player ", " you ", ", but ", " which "))
        )

        if looks_like_prose:
            # Salvage a known location mentioned inside the sentence rather than
            # discarding the update outright — the model often names the right
            # place and merely wraps it in narration.
            salvaged = self._known_location_named_in(candidate)
            if salvaged and salvaged != current:
                logger.warning(
                    f"⚠️ Rejected narrative location text; matched known "
                    f"location '{salvaged}' instead of: {candidate[:80]!r}"
                )
                self.set_location(salvaged)
                return True
            logger.warning(
                f"⚠️ Ignored narrative text in state_changes.location "
                f"(expected a place name): {candidate[:80]!r}"
            )
            return False

        self.set_location(candidate)
        return True

    def _known_location_named_in(self, text: str) -> Optional[str]:
        """The known location mentioned in `text`, if exactly one is."""
        graph = self.game_state.location_context.get("known_locations", {}) or {}
        lowered = text.lower()
        matches = [name for name in graph if name.lower() in lowered]
        if not matches:
            return None
        # Prefer the longest match: "Shattered Plains" over "Plains".
        return max(matches, key=len)

    def get_narrative_beats(self, limit: int = 6) -> List[str]:
        """The most recent narrative beats, oldest first (plan 2.2)."""
        beats = self.game_state.narrative_context.get("narrative_beats", []) or []
        return list(beats[-limit:])

    def get_narrative_chronicle(self, limit: int = 20) -> List[str]:
        """The compressed older history, oldest first (plan 2.2)."""
        chronicle = self.game_state.narrative_context.get(
            "narrative_chronicle", []) or []
        return list(chronicle[-limit:])

    def get_story_so_far(self, limit: int = 6) -> str:
        """
        Recent beats as a single block for the DM prompt (plan 2.2).

        This is what gives the DM continuity beyond the previous turn.

        Includes the CHRONICLE — the compressed record of beats that have aged out
        of the verbatim window. Without it, rolling summarization would preserve
        the early campaign in state and never show it to the DM, which is the same
        "the component works and the product does not reach it" failure that hid
        four subsystems in this project.
        """
        sections = []

        chronicle = self.get_narrative_chronicle()
        if chronicle:
            sections.append("EARLIER (summarised):\n" + "\n".join(chronicle))

        beats = self.get_narrative_beats(limit)
        if beats:
            sections.append("RECENTLY:\n" + "\n".join(beats) if chronicle
                            else "\n".join(beats))

        return "\n\n".join(sections)

    def process_scenario_state_updates(self, scenario_data: Dict[str, Any], turn_number: int):
        """Process scenario data and update authoritative game state"""

        # GameEngine is authoritative for all runtime state updates
        scene_text = scenario_data.get("scene", "")
        narrative_updates = {
            "current_scene": scene_text[:100] + "..." if len(scene_text) > 100 else scene_text,  # Truncated for logs
            "current_scene_full": scene_text,  # Full text for combat/scenario continuity
            "last_scenario": {
                "scene": scene_text,
                "choices": scenario_data.get("choices", []),
                "gm_notes": scenario_data.get("gm_notes", ""),
                "scenario_type": scenario_data.get("scenario_type", "unknown"),
                "confidence": scenario_data.get("confidence", 0)
            },
            "last_scenario_type": scenario_data.get("scenario_type", "unknown"),
            "scenario_confidence": scenario_data.get("confidence", 0),
            "turn_number": turn_number
        }
        self.update_narrative_context(narrative_updates)

        # Plan 2.2: keep a rolling history of narrative beats.
        #
        # `last_scenario` is a SINGLE overwritten slot, so turn N-2 was
        # unrecoverable: the DM had a one-turn memory and no way to reference
        # anything earlier. `narrative_beats` was declared in the state schema
        # and never written or read by anything.
        self._append_narrative_beat(scene_text, turn_number)

        # Process state changes using existing authoritative methods
        state_changes = scenario_data.get("state_changes", {})
        if state_changes:
            if "location" in state_changes:
                self._apply_location_change(state_changes["location"])

            if "flags" in state_changes:
                for flag_name, flag_value in state_changes["flags"].items():
                    self.set_campaign_flag(flag_name, flag_value)

            if "story_hooks" in state_changes:
                for hook in state_changes["story_hooks"]:
                    self.add_story_hook(hook, "normal")

            # Plan 2.3: quest progression.
            #
            # Two bugs made quests read-only prompt decoration:
            #  1. this only read "quest_objectives", but the prompt template
            #     told the model to emit "quests" -- so every quest update the
            #     LLM produced was silently discarded;
            #  2. complete_quest_objective() had ZERO callers, so nothing ever
            #     moved an objective from pending to completed.
            # Accept both keys, and handle completions as well as additions.
            for key in ("quest_objectives", "quests"):
                if key not in state_changes:
                    continue
                self._apply_quest_updates(state_changes[key])
    def _apply_quest_updates(self, updates: Any) -> None:
        """
        Apply the model's quest updates (plan 2.3).

        Tolerant of shape, because the LLM emits any of these:
          "Find the artifact"                                  -> add
          ["Find the artifact", "Speak to Kalak"]              -> add each
          {"add": [...], "complete": [...]}                    -> explicit
          [{"text": "...", "status": "completed"}]             -> per-item status
        """
        if not updates:
            return

        def _add(text: str) -> None:
            text = str(text).strip()
            if text:
                self.add_quest_objective(text)

        def _complete(text: str) -> None:
            text = str(text).strip()
            if text:
                self.complete_quest_objective(text)

        try:
            if isinstance(updates, str):
                _add(updates)
                return

            if isinstance(updates, dict):
                for text in (updates.get("add") or updates.get("new") or []):
                    _add(text)
                for text in (updates.get("complete")
                             or updates.get("completed") or []):
                    _complete(text)
                # A bare {"text": ..., "status": ...} object
                if "text" in updates:
                    if str(updates.get("status", "")).lower().startswith("complet"):
                        _complete(updates["text"])
                    else:
                        _add(updates["text"])
                return

            if isinstance(updates, list):
                for item in updates:
                    if isinstance(item, dict):
                        text = item.get("text") or item.get("objective") or ""
                        if str(item.get("status", "")).lower().startswith("complet"):
                            _complete(text)
                        else:
                            _add(text)
                    else:
                        _add(item)
        except Exception as e:
            logger.warning(f"⚠️ Could not apply quest updates {updates!r}: {e}")

    def get_quest_progress(self) -> Dict[str, Any]:
        """Quest completion summary (plan 2.3)."""
        quest = self.game_state.quest_context
        pending = quest.get("pending_objectives", []) or []
        completed = quest.get("completed_objectives", []) or []
        total = len(pending) + len(completed)
        return {
            "pending": [o.get("text", "") if isinstance(o, dict) else str(o)
                        for o in pending],
            "completed": [o.get("text", "") if isinstance(o, dict) else str(o)
                          for o in completed],
            "pending_count": len(pending),
            "completed_count": len(completed),
            "total": total,
            "percent_complete": round(100 * len(completed) / total) if total else 0,
        }


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