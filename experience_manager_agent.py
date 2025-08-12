"""
Experience Manager Agent
Handles experience points, leveling up, milestones, and character progression in D&D
"""
import json
import os
from typing import Dict, List, Any, Optional
from agent_framework import BaseAgent

class ExperienceManagerAgent(BaseAgent):
    """Agent for managing D&D experience and character advancement"""
    
    def __init__(self, xp_dir: str = "docs/experience", verbose: bool = False):
        super().__init__("experience_manager", "experience_manager")
        self.xp_dir = xp_dir
        self.character_xp = {}
        self.verbose = verbose
        
        # Ensure experience directory exists
        os.makedirs(self.xp_dir, exist_ok=True)
        
        # XP thresholds for each level (1-20)
        self.xp_thresholds = self._create_xp_thresholds()
        
        # CR to XP mapping for encounters
        self.cr_xp_table = self._create_cr_xp_table()
        
    def _setup_handlers(self):
        """Setup message handlers for this agent"""
        # Register message handlers
        self.register_handler("add_xp", self._handle_add_xp)
        self.register_handler("check_level_up", self._handle_check_level_up)
        self.register_handler("level_up", self._handle_level_up)
        self.register_handler("get_xp_status", self._handle_get_xp_status)
        self.register_handler("calculate_encounter_xp", self._handle_calculate_encounter_xp)
        self.register_handler("award_milestone", self._handle_award_milestone)
        self.register_handler("get_level_progression", self._handle_get_level_progression)
        self.register_handler("initialize_character_xp", self._handle_initialize_character_xp)
        self.register_handler("set_milestone_progression", self._handle_set_milestone_progression)
        self.register_handler("get_xp_to_next_level", self._handle_get_xp_to_next_level)
        self.register_handler("bulk_level_party", self._handle_bulk_level_party)
        self.register_handler("reset_xp", self._handle_reset_xp)
    
    def process_tick(self):
        """Process one tick/cycle of the agent's main loop"""
        # Check for automatic level-up notifications
        for character_name, char_data in self.character_xp.items():
            current_xp = char_data.get("current_xp", 0)
            current_level = char_data.get("current_level", 1)
            
            # Check if character has enough XP to level up
            if current_level < 20:
                next_level_xp = self.xp_thresholds.get(current_level + 1, float('inf'))
                if current_xp >= next_level_xp and not char_data.get("level_up_pending", False):
                    char_data["level_up_pending"] = True
                    if self.verbose:
                        print(f"🎉 {character_name} is ready to level up to level {current_level + 1}!")
    
    def handle_message(self, message):
        """Handle message - supports both AgentMessage objects and dict for testing"""
        if isinstance(message, dict):
            # For testing - convert dict to action and data
            action = message.get("action")
            data = message.get("data", {})
            handler = self.message_handlers.get(action)
            if handler:
                return handler(data)
            else:
                return {"success": False, "error": f"Unknown action: {action}"}
        else:
            # Normal AgentMessage handling
            return super().handle_message(message)
    
    def _handle_initialize_character_xp(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize XP tracking for a character"""
        try:
            character_name = message_data.get("character", "").strip().lower()
            starting_level = message_data.get("level", 1)
            starting_xp = message_data.get("xp", None)
            use_milestones = message_data.get("milestones", False)
            
            if not character_name:
                return {"success": False, "error": "Character name is required"}
            
            # Calculate starting XP based on level if not provided
            if starting_xp is None:
                starting_xp = self.xp_thresholds.get(starting_level, 0)
            
            # Initialize character XP data
            self.character_xp[character_name] = {
                "current_xp": starting_xp,
                "current_level": starting_level,
                "use_milestones": use_milestones,
                "milestones_completed": 0,
                "milestones_for_next_level": 2 if use_milestones else 0,
                "level_history": [{"level": starting_level, "xp": starting_xp, "timestamp": "initialization"}],
                "session_xp_gained": 0,
                "total_xp_gained": starting_xp,
                "encounters_survived": 0,
                "milestones_earned": []
            }
            
            if self.verbose:
                progression_type = "milestone" if use_milestones else "XP"
                print(f"✅ Initialized {progression_type} progression for {character_name} (Level {starting_level}, {starting_xp} XP)")
            
            return {
                "success": True,
                "message": f"Experience tracking initialized for {character_name}",
                "character_data": self.character_xp[character_name]
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to initialize character XP: {str(e)}"}
    
    def _handle_add_xp(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add experience points to a character"""
        try:
            character_name = message_data.get("character", "").strip().lower()
            xp_amount = message_data.get("xp", 0)
            source = message_data.get("source", "unknown")
            
            if not character_name:
                return {"success": False, "error": "Character name is required"}
            
            if character_name not in self.character_xp:
                return {"success": False, "error": f"XP tracking not initialized for {character_name}"}
            
            character_data = self.character_xp[character_name]
            
            # Check if using milestone progression
            if character_data["use_milestones"]:
                return {"success": False, "error": f"{character_name} uses milestone progression, not XP"}
            
            # Add XP
            old_xp = character_data["current_xp"]
            character_data["current_xp"] += xp_amount
            character_data["session_xp_gained"] += xp_amount
            character_data["total_xp_gained"] += xp_amount
            
            # Check for level up potential (but don't automatically level up)
            old_level = character_data["current_level"]
            new_level = self._calculate_level_from_xp(character_data["current_xp"])
            
            result = {
                "success": True,
                "message": f"Added {xp_amount} XP to {character_name}",
                "old_xp": old_xp,
                "new_xp": character_data["current_xp"],
                "xp_gained": xp_amount,
                "source": source
            }
            
            # Check if level up is possible (but don't do it automatically)
            if new_level > old_level:
                result["level_up"] = True
                result["level_up_available"] = True
                result["potential_new_level"] = new_level
                result["message"] += f" - Level up to {new_level} is now available!"
                
                if self.verbose:
                    print(f"⬆️ {character_name} can now level up to {new_level}!")
            else:
                result["level_up"] = False
                result["level_up_available"] = False
            
            if self.verbose:
                print(f"✅ Added {xp_amount} XP to {character_name} ({source})")
            
            return result
            
        except Exception as e:
            return {"success": False, "error": f"Failed to add XP: {str(e)}"}
    
    def _handle_check_level_up(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Check if character can level up"""
        try:
            character_name = message_data.get("character", "").strip().lower()
            
            if not character_name:
                return {"success": False, "error": "Character name is required"}
            
            if character_name not in self.character_xp:
                return {"success": False, "error": f"XP tracking not initialized for {character_name}"}
            
            character_data = self.character_xp[character_name]
            current_level = character_data["current_level"]
            current_xp = character_data["current_xp"]
            
            if character_data["use_milestones"]:
                # Milestone progression
                milestones_completed = character_data["milestones_completed"]
                milestones_needed = character_data["milestones_for_next_level"]
                can_level = milestones_completed >= milestones_needed
                
                return {
                    "success": True,
                    "can_level_up": can_level,
                    "current_level": current_level,
                    "progression_type": "milestone",
                    "milestones_completed": milestones_completed,
                    "milestones_needed": milestones_needed,
                    "next_level": current_level + 1 if can_level else None
                }
            else:
                # XP progression
                next_level = current_level + 1
                xp_needed = self.xp_thresholds.get(next_level, float('inf'))
                can_level = current_xp >= xp_needed and next_level <= 20
                
                return {
                    "success": True,
                    "can_level_up": can_level,
                    "current_level": current_level,
                    "current_xp": current_xp,
                    "progression_type": "xp",
                    "xp_to_next_level": max(0, xp_needed - current_xp) if next_level <= 20 else 0,
                    "next_level": next_level if can_level and next_level <= 20 else None,
                    "xp_needed_for_next": xp_needed if next_level <= 20 else None
                }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to check level up: {str(e)}"}
    
    def _handle_level_up(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Level up a character"""
        try:
            character_name = message_data.get("character", "").strip().lower()
            force = message_data.get("force", False)
            
            if not character_name:
                return {"success": False, "error": "Character name is required"}
            
            if character_name not in self.character_xp:
                return {"success": False, "error": f"XP tracking not initialized for {character_name}"}
            
            character_data = self.character_xp[character_name]
            
            # Check if level up is possible
            level_check = self._handle_check_level_up({"character": character_name})
            if not level_check["success"]:
                return level_check
            
            if not level_check["can_level_up"] and not force:
                current_level = character_data['current_level']
                current_xp = character_data['current_xp']
                next_level_xp = self.xp_thresholds.get(current_level + 1, float('inf'))
                return {
                    "success": False,
                    "error": f"Character cannot level up yet. Current level: {current_level}, XP: {current_xp}, need {next_level_xp} XP for level {current_level + 1}"
                }
            
            old_level = character_data["current_level"]
            new_level = old_level + 1
            
            if new_level > 20:
                return {"success": False, "error": "Maximum level (20) already reached"}
            
            # Level up the character
            character_data["current_level"] = new_level
            
            if character_data["use_milestones"]:
                # Reset milestone progress
                character_data["milestones_completed"] = 0
                # Milestones needed might change per level (typically 2-3)
                character_data["milestones_for_next_level"] = 2
            
            # Add to level history
            character_data["level_history"].append({
                "level": new_level,
                "xp": character_data["current_xp"],
                "timestamp": "manual_level_up",
                "forced": force
            })
            
            if self.verbose:
                print(f"🎉 {character_name} leveled up from {old_level} to {new_level}!")
            
            return {
                "success": True,
                "message": f"{character_name} leveled up to {new_level}!",
                "old_level": old_level,
                "new_level": new_level,
                "level_benefits": self._get_level_benefits(new_level)
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to level up: {str(e)}"}
    
    def _handle_get_xp_status(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get current XP status for a character"""
        try:
            character_name = message_data.get("character", "").strip().lower()
            
            if not character_name:
                return {"success": False, "error": "Character name is required"}
                
            if character_name not in self.character_xp:
                return {"success": True, "initialized": False}
            
            character_data = self.character_xp[character_name]
            current_level = character_data["current_level"]
            
            if character_data["use_milestones"]:
                return {
                    "success": True,
                    "initialized": True,
                    "character": character_name,
                    "current_level": current_level,
                    "progression_type": "milestone",
                    "milestones_completed": character_data["milestones_completed"],
                    "milestones_for_next_level": character_data["milestones_for_next_level"],
                    "milestones_earned": character_data["milestones_earned"],
                    "encounters_survived": character_data["encounters_survived"]
                }
            else:
                next_level_xp = self.xp_thresholds.get(current_level + 1, float('inf'))
                xp_to_next = max(0, next_level_xp - character_data["current_xp"])
                
                return {
                    "success": True,
                    "initialized": True,
                    "character": character_name,
                    "current_level": current_level,
                    "current_xp": character_data["current_xp"],
                    "progression_type": "xp",
                    "xp_to_next_level": xp_to_next if current_level < 20 else 0,
                    "next_level_xp": next_level_xp if current_level < 20 else None,
                    "session_xp_gained": character_data["session_xp_gained"],
                    "total_xp_gained": character_data["total_xp_gained"],
                    "encounters_survived": character_data["encounters_survived"]
                }
                
        except Exception as e:
            return {"success": False, "error": f"Failed to get XP status: {str(e)}"}
    
    def _handle_calculate_encounter_xp(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate XP reward for an encounter"""
        try:
            monsters = message_data.get("monsters", [])
            party_size = message_data.get("party_size", 4)
            
            if not monsters:
                return {"success": False, "error": "Monster list is required"}
            
            total_xp = 0
            encounter_details = []
            
            # Calculate total XP from monsters
            for monster in monsters:
                if isinstance(monster, dict):
                    cr = monster.get("cr", 0)
                    count = monster.get("count", 1)
                    name = monster.get("name", "Unknown")
                else:
                    # Assume it's just a CR value
                    cr = monster
                    count = 1
                    name = f"CR {cr} creature"
                
                monster_xp = self.cr_xp_table.get(str(cr), 0)
                total_monster_xp = monster_xp * count
                total_xp += total_monster_xp
                
                encounter_details.append({
                    "name": name,
                    "cr": cr,
                    "count": count,
                    "xp_per_monster": monster_xp,
                    "total_xp": total_monster_xp
                })
            
            # Apply encounter multiplier based on number of monsters
            total_monsters = sum(monster.get("count", 1) if isinstance(monster, dict) else 1 for monster in monsters)
            multiplier = self._get_encounter_multiplier(total_monsters)
            adjusted_xp = int(total_xp * multiplier)
            
            # Divide by party size
            xp_per_character = adjusted_xp // party_size
            
            return {
                "success": True,
                "total_base_xp": total_xp,
                "encounter_multiplier": multiplier,
                "adjusted_xp": adjusted_xp,
                "party_size": party_size,
                "xp_per_character": xp_per_character,
                "encounter_details": encounter_details
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to calculate encounter XP: {str(e)}"}
    
    def _handle_award_milestone(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Award a milestone to a character"""
        try:
            character_name = message_data.get("character", "").strip().lower()
            milestone_name = message_data.get("milestone", "Milestone")
            description = message_data.get("description", "")
            
            if not character_name:
                return {"success": False, "error": "Character name is required"}
            
            if character_name not in self.character_xp:
                return {"success": False, "error": f"XP tracking not initialized for {character_name}"}
            
            character_data = self.character_xp[character_name]
            
            if not character_data["use_milestones"]:
                return {"success": False, "error": f"{character_name} uses XP progression, not milestones"}
            
            # Award the milestone
            character_data["milestones_completed"] += 1
            character_data["milestones_earned"].append({
                "name": milestone_name,
                "description": description,
                "timestamp": "milestone_awarded"
            })
            
            # Check for level up
            milestones_needed = character_data["milestones_for_next_level"]
            milestones_completed = character_data["milestones_completed"]
            
            result = {
                "success": True,
                "message": f"Awarded milestone '{milestone_name}' to {character_name}",
                "milestone": milestone_name,
                "milestones_completed": milestones_completed,
                "milestones_needed": milestones_needed
            }
            
            if milestones_completed >= milestones_needed:
                result["can_level_up"] = True
                result["message"] += f" - {character_name} can now level up!"
                
                if self.verbose:
                    print(f"🎉 {character_name} can level up after earning '{milestone_name}'!")
            else:
                result["can_level_up"] = False
                remaining = milestones_needed - milestones_completed
                result["message"] += f" ({remaining} more needed to level up)"
            
            if self.verbose:
                print(f"✅ Awarded milestone '{milestone_name}' to {character_name}")
            
            return result
            
        except Exception as e:
            return {"success": False, "error": f"Failed to award milestone: {str(e)}"}
    
    def _handle_get_level_progression(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get level progression information"""
        try:
            character_name = message_data.get("character", "").strip().lower()
            
            if not character_name:
                return {"success": False, "error": "Character name is required"}
            
            if character_name not in self.character_xp:
                return {"success": False, "error": f"XP tracking not initialized for {character_name}"}
            
            character_data = self.character_xp[character_name]
            
            return {
                "success": True,
                "character": character_name,
                "level_history": character_data["level_history"],
                "current_level": character_data["current_level"],
                "progression_type": "milestone" if character_data["use_milestones"] else "xp"
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to get level progression: {str(e)}"}
    
    def _handle_set_milestone_progression(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Switch a character to milestone progression"""
        try:
            character_name = message_data.get("character", "").strip().lower()
            milestones_needed = message_data.get("milestones_needed", 2)
            
            if not character_name:
                return {"success": False, "error": "Character name is required"}
            
            if character_name not in self.character_xp:
                return {"success": False, "error": f"XP tracking not initialized for {character_name}"}
            
            character_data = self.character_xp[character_name]
            character_data["use_milestones"] = True
            character_data["milestones_completed"] = 0
            character_data["milestones_for_next_level"] = milestones_needed
            
            if self.verbose:
                print(f"✅ Switched {character_name} to milestone progression")
            
            return {
                "success": True,
                "message": f"Switched {character_name} to milestone progression",
                "milestones_needed": milestones_needed
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to set milestone progression: {str(e)}"}
    
    def _handle_get_xp_to_next_level(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get XP needed to reach next level"""
        try:
            character_name = message_data.get("character", "").strip().lower()
            
            if not character_name:
                return {"success": False, "error": "Character name is required"}
            
            if character_name not in self.character_xp:
                return {"success": False, "error": f"XP tracking not initialized for {character_name}"}
            
            character_data = self.character_xp[character_name]
            
            if character_data["use_milestones"]:
                return {
                    "success": True,
                    "progression_type": "milestone",
                    "milestones_completed": character_data["milestones_completed"],
                    "milestones_needed": character_data["milestones_for_next_level"],
                    "milestones_remaining": max(0, character_data["milestones_for_next_level"] - character_data["milestones_completed"])
                }
            
            current_level = character_data["current_level"]
            current_xp = character_data["current_xp"]
            
            if current_level >= 20:
                return {
                    "success": True,
                    "progression_type": "xp",
                    "at_max_level": True,
                    "current_level": current_level
                }
            
            next_level_xp = self.xp_thresholds.get(current_level + 1, float('inf'))
            xp_needed = max(0, next_level_xp - current_xp)
            
            return {
                "success": True,
                "progression_type": "xp",
                "current_level": current_level,
                "current_xp": current_xp,
                "next_level": current_level + 1,
                "next_level_xp": next_level_xp,
                "xp_needed": xp_needed,
                "progress_percentage": min(100, (current_xp / next_level_xp) * 100)
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to get XP to next level: {str(e)}"}
    
    def _handle_bulk_level_party(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Level up multiple characters at once"""
        try:
            characters = message_data.get("characters", [])
            levels = message_data.get("levels", 1)  # Number of levels to gain
            
            if not characters:
                return {"success": False, "error": "Character list is required"}
            
            results = []
            
            for character_name in characters:
                character_name = character_name.strip().lower()
                
                for _ in range(levels):
                    result = self._handle_level_up({"character": character_name, "force": True})
                    if result["success"]:
                        results.append({
                            "character": character_name,
                            "success": True,
                            "new_level": result["new_level"]
                        })
                    else:
                        results.append({
                            "character": character_name,
                            "success": False,
                            "error": result["error"]
                        })
                        break  # Stop leveling this character if an error occurs
            
            successful_levels = [r for r in results if r["success"]]
            failed_levels = [r for r in results if not r["success"]]
            
            return {
                "success": True,
                "message": f"Leveled {len(successful_levels)} characters",
                "successful": successful_levels,
                "failed": failed_levels,
                "levels_gained": levels
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to bulk level party: {str(e)}"}
    
    def _handle_reset_xp(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Reset character XP and level"""
        try:
            character_name = message_data.get("character", "").strip().lower()
            new_level = message_data.get("level", 1)
            new_xp = message_data.get("xp", None)
            
            if not character_name:
                return {"success": False, "error": "Character name is required"}
            
            if character_name not in self.character_xp:
                return {"success": False, "error": f"XP tracking not initialized for {character_name}"}
            
            # Calculate XP for new level if not provided
            if new_xp is None:
                new_xp = self.xp_thresholds.get(new_level, 0)
            
            character_data = self.character_xp[character_name]
            old_level = character_data["current_level"]
            old_xp = character_data["current_xp"]
            
            # Reset character data
            character_data["current_level"] = new_level
            character_data["current_xp"] = new_xp
            character_data["session_xp_gained"] = 0
            character_data["milestones_completed"] = 0
            
            # Add reset entry to history
            character_data["level_history"].append({
                "level": new_level,
                "xp": new_xp,
                "timestamp": "reset",
                "old_level": old_level,
                "old_xp": old_xp
            })
            
            if self.verbose:
                print(f"🔄 Reset {character_name} to level {new_level} ({new_xp} XP)")
            
            return {
                "success": True,
                "message": f"Reset {character_name} to level {new_level}",
                "old_level": old_level,
                "new_level": new_level,
                "old_xp": old_xp,
                "new_xp": new_xp
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to reset XP: {str(e)}"}
    
    # Helper methods
    def _create_xp_thresholds(self) -> Dict[int, int]:
        """Create XP thresholds for each level"""
        return {
            1: 0, 2: 300, 3: 900, 4: 2700, 5: 6500,
            6: 14000, 7: 23000, 8: 34000, 9: 48000, 10: 64000,
            11: 85000, 12: 100000, 13: 120000, 14: 140000, 15: 165000,
            16: 195000, 17: 225000, 18: 265000, 19: 305000, 20: 355000
        }
    
    def _create_cr_xp_table(self) -> Dict[str, int]:
        """Create CR to XP mapping table"""
        return {
            "0": 10, "1/8": 25, "1/4": 50, "1/2": 100,
            "1": 200, "2": 450, "3": 700, "4": 1100, "5": 1800,
            "6": 2300, "7": 2900, "8": 3900, "9": 5000, "10": 5900,
            "11": 7200, "12": 8400, "13": 10000, "14": 11500, "15": 13000,
            "16": 15000, "17": 18000, "18": 20000, "19": 22000, "20": 25000,
            "21": 33000, "22": 41000, "23": 50000, "24": 62000, "25": 75000,
            "26": 90000, "27": 105000, "28": 120000, "29": 135000, "30": 155000
        }
    
    def _calculate_level_from_xp(self, xp: int) -> int:
        """Calculate character level from total XP"""
        for level in range(20, 0, -1):
            if xp >= self.xp_thresholds[level]:
                return level
        return 1
    
    def _get_encounter_multiplier(self, monster_count: int) -> float:
        """Get encounter multiplier based on number of monsters"""
        if monster_count == 1:
            return 1.0
        elif monster_count == 2:
            return 1.5
        elif monster_count <= 6:
            return 2.0
        elif monster_count <= 10:
            return 2.5
        elif monster_count <= 14:
            return 3.0
        else:
            return 4.0
    
    def _get_level_benefits(self, level: int) -> Dict[str, Any]:
        """Get benefits gained at a specific level"""
        benefits = {
            "level": level,
            "proficiency_bonus": 2 + ((level - 1) // 4),
            "ability_score_improvement": level in [4, 8, 12, 16, 19],
            "general_benefits": []
        }
        
        # Add general level benefits
        if level == 2:
            benefits["general_benefits"].append("Class features unlock")
        if level == 3:
            benefits["general_benefits"].append("Subclass choice")
        if level == 5:
            benefits["general_benefits"].append("Cantrip damage increase, Extra Attack (for some classes)")
        if level == 11:
            benefits["general_benefits"].append("Cantrip damage increase again")
        if level == 17:
            benefits["general_benefits"].append("Cantrip damage increase again")
        if level == 20:
            benefits["general_benefits"].append("Maximum level reached!")
        
        return benefits