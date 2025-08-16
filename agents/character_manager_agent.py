"""
Character Manager Agent
Handles character creation, progression, stats, and character-specific D&D mechanics
"""
import json
import os
from typing import Dict, List, Any, Optional
from pathlib import Path
from agent_framework import BaseAgent

class CharacterManagerAgent(BaseAgent):
    """Agent for managing D&D character creation, progression, and stats"""
    
    def __init__(self, characters_dir: str = "docs/characters", verbose: bool = False):
        super().__init__("character_manager", "character_manager")
        self.characters_dir = characters_dir
        self.characters_cache = {}
        self.verbose = verbose
        
        # Ensure characters directory exists
        os.makedirs(self.characters_dir, exist_ok=True)
        
        # D&D 5e race data
        self.races = {
            "human": {"ability_bonus": {"all": 1}, "size": "Medium", "speed": 30},
            "elf": {"ability_bonus": {"dexterity": 2}, "size": "Medium", "speed": 30},
            "dwarf": {"ability_bonus": {"constitution": 2}, "size": "Medium", "speed": 25},
            "halfling": {"ability_bonus": {"dexterity": 2}, "size": "Small", "speed": 25},
            "dragonborn": {"ability_bonus": {"strength": 2, "charisma": 1}, "size": "Medium", "speed": 30},
            "gnome": {"ability_bonus": {"intelligence": 2}, "size": "Small", "speed": 25},
            "half-elf": {"ability_bonus": {"charisma": 2}, "size": "Medium", "speed": 30},
            "half-orc": {"ability_bonus": {"strength": 2, "constitution": 1}, "size": "Medium", "speed": 30},
            "tiefling": {"ability_bonus": {"intelligence": 1, "charisma": 2}, "size": "Medium", "speed": 30}
        }
        
        # D&D 5e class data
        self.classes = {
            "barbarian": {"hit_die": 12, "primary_ability": "strength", "saving_throws": ["strength", "constitution"]},
            "bard": {"hit_die": 8, "primary_ability": "charisma", "saving_throws": ["dexterity", "charisma"]},
            "cleric": {"hit_die": 8, "primary_ability": "wisdom", "saving_throws": ["wisdom", "charisma"]},
            "druid": {"hit_die": 8, "primary_ability": "wisdom", "saving_throws": ["intelligence", "wisdom"]},
            "fighter": {"hit_die": 10, "primary_ability": "strength", "saving_throws": ["strength", "constitution"]},
            "monk": {"hit_die": 8, "primary_ability": "dexterity", "saving_throws": ["strength", "dexterity"]},
            "paladin": {"hit_die": 10, "primary_ability": "strength", "saving_throws": ["wisdom", "charisma"]},
            "ranger": {"hit_die": 10, "primary_ability": "dexterity", "saving_throws": ["strength", "dexterity"]},
            "rogue": {"hit_die": 8, "primary_ability": "dexterity", "saving_throws": ["dexterity", "intelligence"]},
            "sorcerer": {"hit_die": 6, "primary_ability": "charisma", "saving_throws": ["constitution", "charisma"]},
            "warlock": {"hit_die": 8, "primary_ability": "charisma", "saving_throws": ["wisdom", "charisma"]},
            "wizard": {"hit_die": 6, "primary_ability": "intelligence", "saving_throws": ["intelligence", "wisdom"]}
        }
        
    def _setup_handlers(self):
        """Setup message handlers for this agent"""
        # Register message handlers
        self.register_handler("create_character", self._handle_create_character)
        self.register_handler("get_character", self._handle_get_character)
        self.register_handler("update_character", self._handle_update_character)
        self.register_handler("list_characters", self._handle_list_characters)
        self.register_handler("level_up_character", self._handle_level_up_character)
        self.register_handler("roll_ability_scores", self._handle_roll_ability_scores)
        self.register_handler("calculate_modifier", self._handle_calculate_modifier)
        self.register_handler("get_character_stats", self._handle_get_character_stats)
        self.register_handler("update_ability_scores", self._handle_update_ability_scores)
    
    def process_tick(self):
        """Process one tick/cycle of the agent's main loop"""
        # Character manager doesn't need active processing
        pass
    
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
    
    def _handle_create_character(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new D&D character"""
        try:
            character_name = message_data.get("name", "").strip()
            race = message_data.get("race", "human").lower()
            character_class = message_data.get("class", "fighter").lower()
            level = message_data.get("level", 1)
            ability_scores = message_data.get("ability_scores", {})
            
            if not character_name:
                return {"success": False, "error": "Character name is required"}
            
            if race not in self.races:
                return {"success": False, "error": f"Unknown race: {race}"}
            
            if character_class not in self.classes:
                return {"success": False, "error": f"Unknown class: {character_class}"}
            
            # Generate ability scores if not provided
            if not ability_scores:
                ability_scores = self._generate_ability_scores()
            
            # Apply racial bonuses
            ability_scores = self._apply_racial_bonuses(ability_scores, race)
            
            # Create character data structure
            character_data = {
                "name": character_name,
                "race": race,
                "class": character_class,
                "level": level,
                "ability_scores": ability_scores,
                "hit_points": self._calculate_hit_points(character_class, level, ability_scores),
                "armor_class": 10 + self._get_modifier(ability_scores.get("dexterity", 10)),
                "proficiency_bonus": self._get_proficiency_bonus(level),
                "saving_throws": self._calculate_saving_throws(character_class, ability_scores, level),
                "skills": {},
                "equipment": [],
                "spells": [],
                "features": [],
                "background": message_data.get("background", "folk hero"),
                "experience_points": self._get_xp_for_level(level),
                "created_date": __import__('datetime').datetime.now().isoformat(),
                "last_updated": __import__('datetime').datetime.now().isoformat()
            }
            
            # Save character to file
            character_file = os.path.join(self.characters_dir, f"{character_name.lower().replace(' ', '_')}.json")
            with open(character_file, 'w') as f:
                json.dump(character_data, f, indent=2)
            
            # Cache character
            self.characters_cache[character_name.lower()] = character_data
            
            if self.verbose:
                print(f"✅ Created character: {character_name} ({race} {character_class} level {level})")
            
            return {
                "success": True,
                "character": character_data,
                "message": f"Character {character_name} created successfully"
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to create character: {str(e)}"}
    
    def _handle_get_character(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get character data by name"""
        try:
            character_name = message_data.get("name", "").strip().lower()
            
            if not character_name:
                return {"success": False, "error": "Character name is required"}
            
            # Check cache first
            if character_name in self.characters_cache:
                return {"success": True, "character": self.characters_cache[character_name]}
            
            # Load from file
            character_file = os.path.join(self.characters_dir, f"{character_name.replace(' ', '_')}.json")
            if os.path.exists(character_file):
                with open(character_file, 'r') as f:
                    character_data = json.load(f)
                
                # Cache for future use
                self.characters_cache[character_name] = character_data
                return {"success": True, "character": character_data}
            
            return {"success": False, "error": f"Character '{character_name}' not found"}
            
        except Exception as e:
            return {"success": False, "error": f"Failed to get character: {str(e)}"}
    
    def _handle_update_character(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update character data"""
        try:
            character_name = message_data.get("name", "").strip().lower()
            updates = message_data.get("updates", {})
            
            if not character_name:
                return {"success": False, "error": "Character name is required"}
            
            # Get current character data
            result = self._handle_get_character({"name": character_name})
            if not result["success"]:
                return result
            
            character_data = result["character"].copy()
            
            # Apply updates
            for key, value in updates.items():
                if key in character_data:
                    character_data[key] = value
            
            character_data["last_updated"] = __import__('datetime').datetime.now().isoformat()
            
            # Save updated character
            character_file = os.path.join(self.characters_dir, f"{character_name.replace(' ', '_')}.json")
            with open(character_file, 'w') as f:
                json.dump(character_data, f, indent=2)
            
            # Update cache
            self.characters_cache[character_name] = character_data
            
            return {"success": True, "character": character_data, "message": "Character updated successfully"}
            
        except Exception as e:
            return {"success": False, "error": f"Failed to update character: {str(e)}"}
    
    def _handle_list_characters(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """List all available characters"""
        try:
            characters = []
            
            if os.path.exists(self.characters_dir):
                for filename in os.listdir(self.characters_dir):
                    if filename.endswith('.json'):
                        filepath = os.path.join(self.characters_dir, filename)
                        try:
                            with open(filepath, 'r') as f:
                                character_data = json.load(f)
                            characters.append({
                                "name": character_data["name"],
                                "race": character_data["race"],
                                "class": character_data["class"],
                                "level": character_data["level"],
                                "hit_points": character_data["hit_points"]
                            })
                        except (json.JSONDecodeError, KeyError):
                            continue
            
            return {"success": True, "characters": characters}
            
        except Exception as e:
            return {"success": False, "error": f"Failed to list characters: {str(e)}"}
    
    def _handle_level_up_character(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Level up a character"""
        try:
            character_name = message_data.get("name", "").strip().lower()
            
            result = self._handle_get_character({"name": character_name})
            if not result["success"]:
                return result
            
            character_data = result["character"].copy()
            current_level = character_data["level"]
            new_level = current_level + 1
            
            if new_level > 20:
                return {"success": False, "error": "Character is already at maximum level (20)"}
            
            # Calculate new hit points
            character_class = character_data["class"]
            hit_die = self.classes[character_class]["hit_die"]
            con_modifier = self._get_modifier(character_data["ability_scores"]["constitution"])
            
            # Average hit point increase (can be customized)
            hp_increase = (hit_die // 2 + 1) + con_modifier
            new_hp = character_data["hit_points"] + hp_increase
            
            # Update character data
            updates = {
                "level": new_level,
                "hit_points": new_hp,
                "proficiency_bonus": self._get_proficiency_bonus(new_level),
                "experience_points": self._get_xp_for_level(new_level)
            }
            
            # Recalculate saving throws
            updates["saving_throws"] = self._calculate_saving_throws(
                character_class, character_data["ability_scores"], new_level
            )
            
            # Update character
            update_result = self._handle_update_character({
                "name": character_name,
                "updates": updates
            })
            
            if update_result["success"]:
                return {
                    "success": True,
                    "character": update_result["character"],
                    "message": f"Character leveled up to level {new_level}! Gained {hp_increase} hit points.",
                    "level_up_details": {
                        "old_level": current_level,
                        "new_level": new_level,
                        "hp_gained": hp_increase,
                        "new_proficiency_bonus": updates["proficiency_bonus"]
                    }
                }
            
            return update_result
            
        except Exception as e:
            return {"success": False, "error": f"Failed to level up character: {str(e)}"}
    
    def _handle_roll_ability_scores(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Roll ability scores using 4d6 drop lowest method"""
        try:
            method = message_data.get("method", "4d6_drop_lowest")
            
            if method == "4d6_drop_lowest":
                ability_scores = self._generate_ability_scores()
            elif method == "point_buy":
                # Point buy system (simplified)
                ability_scores = {
                    "strength": 13, "dexterity": 13, "constitution": 13,
                    "intelligence": 12, "wisdom": 12, "charisma": 12
                }
            elif method == "standard_array":
                # Standard array
                scores = [15, 14, 13, 12, 10, 8]
                abilities = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]
                ability_scores = dict(zip(abilities, scores))
            else:
                return {"success": False, "error": f"Unknown method: {method}"}
            
            return {"success": True, "ability_scores": ability_scores, "method": method}
            
        except Exception as e:
            return {"success": False, "error": f"Failed to roll ability scores: {str(e)}"}
    
    def _handle_calculate_modifier(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate ability modifier from ability score"""
        try:
            ability_score = message_data.get("ability_score", 10)
            modifier = self._get_modifier(ability_score)
            
            return {"success": True, "ability_score": ability_score, "modifier": modifier}
            
        except Exception as e:
            return {"success": False, "error": f"Failed to calculate modifier: {str(e)}"}
    
    def _handle_get_character_stats(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed character statistics"""
        try:
            character_name = message_data.get("name", "").strip().lower()
            
            result = self._handle_get_character({"name": character_name})
            if not result["success"]:
                return result
            
            character_data = result["character"]
            
            # Calculate derived stats
            stats = {
                "basic_info": {
                    "name": character_data["name"],
                    "race": character_data["race"],
                    "class": character_data["class"],
                    "level": character_data["level"],
                    "experience_points": character_data["experience_points"]
                },
                "combat_stats": {
                    "hit_points": character_data["hit_points"],
                    "armor_class": character_data["armor_class"],
                    "proficiency_bonus": character_data["proficiency_bonus"]
                },
                "ability_scores": character_data["ability_scores"],
                "ability_modifiers": {
                    ability: self._get_modifier(score) 
                    for ability, score in character_data["ability_scores"].items()
                },
                "saving_throws": character_data["saving_throws"],
                "skills": character_data.get("skills", {}),
                "equipment": character_data.get("equipment", []),
                "spells": character_data.get("spells", []),
                "features": character_data.get("features", [])
            }
            
            return {"success": True, "stats": stats}
            
        except Exception as e:
            return {"success": False, "error": f"Failed to get character stats: {str(e)}"}
    
    def _handle_update_ability_scores(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update character ability scores"""
        try:
            character_name = message_data.get("name", "").strip().lower()
            ability_scores = message_data.get("ability_scores", {})
            
            if not character_name:
                return {"success": False, "error": "Character name is required"}
            
            if character_name not in self.characters_cache:
                # Try to load from file
                result = self._handle_get_character({"name": character_name})
                if not result["success"]:
                    return {"success": False, "error": f"Character '{character_name}' not found"}
            
            # Update ability scores
            character = self.characters_cache[character_name]
            for ability, score in ability_scores.items():
                if ability in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
                    character["ability_scores"][ability] = score
            
            # Recalculate derived stats
            character["armor_class"] = 10 + self._get_modifier(character["ability_scores"].get("dexterity", 10))
            character["hit_points"] = self._calculate_hit_points(
                character["class"],
                character["level"],
                character["ability_scores"]
            )
            character["saving_throws"] = self._calculate_saving_throws(
                character["class"],
                character["ability_scores"],
                character["level"]
            )
            
            # Save updated character
            character_file = os.path.join(self.characters_dir, f"{character_name.replace(' ', '_')}.json")
            with open(character_file, 'w') as f:
                json.dump(character, f, indent=2)
            
            if self.verbose:
                print(f"✅ Updated ability scores for {character_name}")
            
            return {
                "success": True,
                "message": f"Updated ability scores for {character_name}",
                "character": character
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to update ability scores: {str(e)}"}
    
    # Helper methods
    def _generate_ability_scores(self) -> Dict[str, int]:
        """Generate ability scores using 4d6 drop lowest"""
        import random
        
        abilities = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]
        ability_scores = {}
        
        for ability in abilities:
            # Roll 4d6, drop lowest
            rolls = [random.randint(1, 6) for _ in range(4)]
            rolls.sort(reverse=True)
            ability_scores[ability] = sum(rolls[:3])
        
        return ability_scores
    
    def _apply_racial_bonuses(self, ability_scores: Dict[str, int], race: str) -> Dict[str, int]:
        """Apply racial ability score bonuses"""
        race_data = self.races.get(race, {})
        bonuses = race_data.get("ability_bonus", {})
        
        for ability, bonus in bonuses.items():
            if ability == "all":
                # Human variant - +1 to all abilities
                for ab in ability_scores:
                    ability_scores[ab] += bonus
            else:
                ability_scores[ability] = ability_scores.get(ability, 10) + bonus
        
        return ability_scores
    
    def _calculate_hit_points(self, character_class: str, level: int, ability_scores: Dict[str, int]) -> int:
        """Calculate character hit points"""
        hit_die = self.classes[character_class]["hit_die"]
        con_modifier = self._get_modifier(ability_scores.get("constitution", 10))
        
        # Max HP at level 1, average for subsequent levels
        hp = hit_die + con_modifier
        if level > 1:
            avg_roll = (hit_die // 2) + 1
            hp += (level - 1) * (avg_roll + con_modifier)
        
        return max(hp, 1)  # Minimum 1 HP
    
    def _get_modifier(self, ability_score: int) -> int:
        """Calculate ability modifier from ability score"""
        return (ability_score - 10) // 2
    
    def _calculate_ability_modifier(self, ability_score: int) -> int:
        """Calculate ability modifier from ability score (alias for _get_modifier)"""
        return self._get_modifier(ability_score)
    
    def _get_proficiency_bonus(self, level: int) -> int:
        """Get proficiency bonus for given level"""
        return 2 + ((level - 1) // 4)
    
    def _calculate_saving_throws(self, character_class: str, ability_scores: Dict[str, int], level: int) -> Dict[str, int]:
        """Calculate saving throw bonuses"""
        saving_throws = {}
        proficiency_bonus = self._get_proficiency_bonus(level)
        proficient_saves = self.classes[character_class]["saving_throws"]
        
        for ability, score in ability_scores.items():
            modifier = self._get_modifier(score)
            if ability in proficient_saves:
                saving_throws[ability] = modifier + proficiency_bonus
            else:
                saving_throws[ability] = modifier
        
        return saving_throws
    
    def _get_xp_for_level(self, level: int) -> int:
        """Get required XP for given level"""
        xp_table = [
            0, 300, 900, 2700, 6500, 14000, 23000, 34000, 48000, 64000,
            85000, 100000, 120000, 140000, 165000, 195000, 225000, 265000, 305000, 355000
        ]
        return xp_table[min(level - 1, len(xp_table) - 1)]