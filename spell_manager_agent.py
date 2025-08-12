"""
Spell Manager Agent
Handles spell casting, preparation, spell slots, and magic-related D&D mechanics
"""
import json
import os
import time
from typing import Dict, List, Any, Optional
from agent_framework import BaseAgent

class SpellManagerAgent(BaseAgent):
    """Agent for managing D&D spellcasting and magic"""
    
    def __init__(self, spells_dir: str = "docs/spells", verbose: bool = False):
        super().__init__("spell_manager", "spell_manager")
        self.spells_dir = spells_dir
        self.spell_database = {}
        self.character_spellcasting = {}
        self.verbose = verbose
        
        # Ensure spells directory exists
        os.makedirs(self.spells_dir, exist_ok=True)
        
        # Load spell database
        self._load_spell_database()
        
        # Spell slot progression tables for each class
        self.spell_slot_tables = self._create_spell_slot_tables()
        
    def _setup_handlers(self):
        """Setup message handlers for this agent"""
        # Register message handlers
        self.register_handler("prepare_spells", self._handle_prepare_spells)
        self.register_handler("cast_spell", self._handle_cast_spell)
        self.register_handler("get_prepared_spells", self._handle_get_prepared_spells)
        self.register_handler("get_spell_slots", self._handle_get_spell_slots)
        self.register_handler("restore_spell_slots", self._handle_restore_spell_slots)
        self.register_handler("learn_spell", self._handle_learn_spell)
        self.register_handler("get_known_spells", self._handle_get_known_spells)
        self.register_handler("search_spells", self._handle_search_spells)
        self.register_handler("get_spell_info", self._handle_get_spell_info)
        self.register_handler("initialize_spellcaster", self._handle_initialize_spellcaster)
        self.register_handler("upcast_spell", self._handle_upcast_spell)
        self.register_handler("get_spell_save_dc", self._handle_get_spell_save_dc)
        self.register_handler("get_spell_attack_bonus", self._handle_get_spell_attack_bonus)
    
    def process_tick(self):
        """Process one tick/cycle of the agent's main loop"""
        # Check for concentration spell durations and effects
        current_time = time.time()
        for character_name, spell_data in self.character_spellcasting.items():
            concentration_spell = spell_data.get("concentration_spell")
            if concentration_spell:
                duration = concentration_spell.get("duration", 0)
                start_time = concentration_spell.get("start_time", 0)
                if duration > 0 and current_time - start_time >= duration:
                    # Concentration spell expired
                    spell_data["concentration_spell"] = None
                    if self.verbose:
                        print(f"⏰ {character_name}'s concentration on {concentration_spell.get('name', 'spell')} ended")
    
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
    
    def _handle_initialize_spellcaster(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize spellcasting for a character"""
        try:
            character_name = message_data.get("character", "").strip().lower()
            character_class = message_data.get("class", "").lower()
            level = message_data.get("level", 1)
            spellcasting_ability = message_data.get("spellcasting_ability", "intelligence").lower()
            ability_modifier = message_data.get("ability_modifier", 0)
            proficiency_bonus = message_data.get("proficiency_bonus", 2)
            
            if not character_name or not character_class:
                return {"success": False, "error": "Character name and class are required"}
            
            # Get spell slot progression
            spell_slots = self._get_spell_slots_for_class_level(character_class, level)
            
            # Calculate spell save DC and spell attack bonus
            spell_save_dc = 8 + proficiency_bonus + ability_modifier
            spell_attack_bonus = proficiency_bonus + ability_modifier
            
            # Initialize spellcasting data
            self.character_spellcasting[character_name] = {
                "class": character_class,
                "level": level,
                "spellcasting_ability": spellcasting_ability,
                "ability_modifier": ability_modifier,
                "proficiency_bonus": proficiency_bonus,
                "spell_save_dc": spell_save_dc,
                "spell_attack_bonus": spell_attack_bonus,
                "spell_slots": spell_slots.copy(),
                "spell_slots_used": {str(i): 0 for i in range(1, 10)},
                "spells_known": [],
                "spells_prepared": [],
                "cantrips_known": [],
                "ritual_spells": [],
                "concentration_spell": None
            }
            
            if self.verbose:
                print(f"✅ Initialized spellcasting for {character_name} ({character_class} level {level})")
            
            return {
                "success": True,
                "message": f"Spellcasting initialized for {character_name}",
                "spellcasting": self.character_spellcasting[character_name]
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to initialize spellcaster: {str(e)}"}
    
    def _handle_prepare_spells(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare spells for a character"""
        try:
            character_name = message_data.get("character", "").strip().lower()
            spell_names = message_data.get("spells", [])
            
            if not character_name:
                return {"success": False, "error": "Character name is required"}
            
            if character_name not in self.character_spellcasting:
                return {"success": False, "error": f"Spellcasting not initialized for {character_name}"}
            
            spellcasting = self.character_spellcasting[character_name]
            
            # Calculate number of spells that can be prepared
            max_prepared = self._calculate_max_prepared_spells(spellcasting)
            
            if len(spell_names) > max_prepared:
                return {
                    "success": False, 
                    "error": f"Cannot prepare {len(spell_names)} spells. Maximum: {max_prepared}"
                }
            
            # Validate all spells
            valid_spells = []
            for spell_name in spell_names:
                spell_data = self._get_spell_data(spell_name.lower())
                if not spell_data:
                    return {"success": False, "error": f"Unknown spell: {spell_name}"}
                
                # Check if spell is in known spells (for classes that need to know spells)
                if self._requires_known_spells(spellcasting["class"]):
                    if spell_name.lower() not in [s.lower() for s in spellcasting["spells_known"]]:
                        return {"success": False, "error": f"Spell not known: {spell_name}"}
                
                valid_spells.append(spell_data)
            
            # Prepare the spells
            spellcasting["spells_prepared"] = [spell["name"] for spell in valid_spells]
            
            if self.verbose:
                print(f"✅ {character_name} prepared {len(valid_spells)} spells")
            
            return {
                "success": True,
                "message": f"Prepared {len(valid_spells)} spells",
                "prepared_spells": spellcasting["spells_prepared"]
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to prepare spells: {str(e)}"}
    
    def _handle_cast_spell(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Cast a spell"""
        try:
            character_name = message_data.get("character", "").strip().lower()
            spell_name = message_data.get("spell", "").strip().lower()
            spell_level = message_data.get("level", None)  # For upcasting
            is_ritual = message_data.get("ritual", False)
            
            if not character_name or not spell_name:
                return {"success": False, "error": "Character name and spell name are required"}
            
            if character_name not in self.character_spellcasting:
                return {"success": False, "error": f"Spellcasting not initialized for {character_name}"}
            
            spellcasting = self.character_spellcasting[character_name]
            spell_data = self._get_spell_data(spell_name)
            
            if not spell_data:
                return {"success": False, "error": f"Unknown spell: {spell_name}"}
            
            # Check if spell is prepared (cantrips don't need preparation)
            base_level = spell_data["level"]
            if base_level > 0:  # Not a cantrip
                if spell_data["name"] not in spellcasting["spells_prepared"]:
                    return {"success": False, "error": f"Spell not prepared: {spell_name}"}
            
            # Handle ritual casting
            if is_ritual and "ritual" in spell_data.get("tags", []):
                # Ritual spells don't consume spell slots but take longer to cast
                result = {
                    "success": True,
                    "message": f"Cast {spell_name} as a ritual (takes 10 additional minutes)",
                    "spell": spell_data,
                    "cast_as_ritual": True,
                    "spell_slot_used": None
                }
            else:
                # Determine spell level to cast at
                cast_level = spell_level if spell_level is not None else base_level
                
                if cast_level < base_level:
                    return {"success": False, "error": f"Cannot cast {spell_name} at level {cast_level} (minimum level {base_level})"}
                
                # Check and consume spell slot (cantrips don't use slots)
                if base_level > 0:
                    if not self._has_available_spell_slot(spellcasting, cast_level):
                        return {"success": False, "error": f"No level {cast_level} spell slots available"}
                    
                    # Consume spell slot
                    spellcasting["spell_slots_used"][str(cast_level)] += 1
                
                # Handle concentration
                if "concentration" in spell_data.get("tags", []):
                    # End previous concentration spell
                    if spellcasting["concentration_spell"]:
                        if self.verbose:
                            print(f"⚠️ Ending concentration on {spellcasting['concentration_spell']}")
                    
                    spellcasting["concentration_spell"] = spell_data["name"]
                
                result = {
                    "success": True,
                    "message": f"Cast {spell_name}" + (f" at level {cast_level}" if cast_level > base_level else ""),
                    "spell": spell_data,
                    "cast_at_level": cast_level,
                    "spell_slot_used": cast_level if base_level > 0 else None,
                    "requires_concentration": "concentration" in spell_data.get("tags", [])
                }
            
            if self.verbose:
                print(f"✅ {character_name} cast {spell_name}")
            
            return result
            
        except Exception as e:
            return {"success": False, "error": f"Failed to cast spell: {str(e)}"}
    
    def _handle_get_prepared_spells(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get list of prepared spells"""
        try:
            character_name = message_data.get("character", "").strip().lower()
            
            if not character_name:
                return {"success": False, "error": "Character name is required"}
            
            if character_name not in self.character_spellcasting:
                return {"success": True, "prepared_spells": [], "cantrips": []}
            
            spellcasting = self.character_spellcasting[character_name]
            
            return {
                "success": True,
                "prepared_spells": spellcasting["spells_prepared"],
                "cantrips": spellcasting["cantrips_known"]
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to get prepared spells: {str(e)}"}
    
    def _handle_get_spell_slots(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get current spell slot status"""
        try:
            character_name = message_data.get("character", "").strip().lower()
            
            if not character_name:
                return {"success": False, "error": "Character name is required"}
            
            if character_name not in self.character_spellcasting:
                return {"success": True, "spell_slots": {}, "spell_slots_used": {}}
            
            spellcasting = self.character_spellcasting[character_name]
            
            # Calculate available slots
            available_slots = {}
            for level, total in spellcasting["spell_slots"].items():
                used = spellcasting["spell_slots_used"].get(level, 0)
                available_slots[level] = max(0, total - used)
            
            return {
                "success": True,
                "spell_slots": spellcasting["spell_slots"],
                "spell_slots_used": spellcasting["spell_slots_used"],
                "available_slots": available_slots
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to get spell slots: {str(e)}"}
    
    def _handle_restore_spell_slots(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Restore spell slots (typically after a long rest)"""
        try:
            character_name = message_data.get("character", "").strip().lower()
            slot_level = message_data.get("level", None)  # Specific level, or None for all
            
            if not character_name:
                return {"success": False, "error": "Character name is required"}
            
            if character_name not in self.character_spellcasting:
                return {"success": False, "error": f"Spellcasting not initialized for {character_name}"}
            
            spellcasting = self.character_spellcasting[character_name]
            
            if slot_level is not None:
                # Restore specific level
                spellcasting["spell_slots_used"][str(slot_level)] = 0
                message = f"Restored level {slot_level} spell slots"
            else:
                # Restore all slots
                for level in spellcasting["spell_slots_used"]:
                    spellcasting["spell_slots_used"][level] = 0
                message = "Restored all spell slots"
            
            # End concentration
            spellcasting["concentration_spell"] = None
            
            if self.verbose:
                print(f"✅ {message} for {character_name}")
            
            return {"success": True, "message": message}
            
        except Exception as e:
            return {"success": False, "error": f"Failed to restore spell slots: {str(e)}"}
    
    def _handle_learn_spell(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Learn a new spell"""
        try:
            character_name = message_data.get("character", "").strip().lower()
            spell_name = message_data.get("spell", "").strip().lower()
            is_cantrip = message_data.get("cantrip", False)
            
            if not character_name or not spell_name:
                return {"success": False, "error": "Character name and spell name are required"}
            
            if character_name not in self.character_spellcasting:
                return {"success": False, "error": f"Spellcasting not initialized for {character_name}"}
            
            spellcasting = self.character_spellcasting[character_name]
            spell_data = self._get_spell_data(spell_name)
            
            if not spell_data:
                return {"success": False, "error": f"Unknown spell: {spell_name}"}
            
            # Add to appropriate list
            if spell_data["level"] == 0 or is_cantrip:
                if spell_data["name"] not in spellcasting["cantrips_known"]:
                    spellcasting["cantrips_known"].append(spell_data["name"])
                    list_name = "cantrips"
                else:
                    return {"success": False, "error": f"Cantrip already known: {spell_name}"}
            else:
                if spell_data["name"] not in spellcasting["spells_known"]:
                    spellcasting["spells_known"].append(spell_data["name"])
                    list_name = "spells"
                else:
                    return {"success": False, "error": f"Spell already known: {spell_name}"}
            
            if self.verbose:
                print(f"✅ {character_name} learned {spell_name}")
            
            return {
                "success": True,
                "message": f"Learned {spell_name}",
                "added_to": list_name
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to learn spell: {str(e)}"}
    
    def _handle_get_known_spells(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get all known spells for a character"""
        try:
            character_name = message_data.get("character", "").strip().lower()
            
            if not character_name:
                return {"success": False, "error": "Character name is required"}
            
            if character_name not in self.character_spellcasting:
                return {"success": True, "spells_known": [], "cantrips_known": []}
            
            spellcasting = self.character_spellcasting[character_name]
            
            return {
                "success": True,
                "spells_known": spellcasting["spells_known"],
                "cantrips_known": spellcasting["cantrips_known"]
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to get known spells: {str(e)}"}
    
    def _handle_search_spells(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Search for spells in the database"""
        try:
            query = message_data.get("query", "").lower()
            level = message_data.get("level", None)
            school = message_data.get("school", "").lower()
            character_class = message_data.get("class", "").lower()
            
            results = []
            for spell_name, spell_data in self.spell_database.items():
                # Text search
                if query and query not in spell_name and query not in spell_data.get("description", "").lower():
                    continue
                
                # Level filter
                if level is not None and spell_data["level"] != level:
                    continue
                
                # School filter
                if school and spell_data.get("school", "").lower() != school:
                    continue
                
                # Class filter
                if character_class and character_class not in [c.lower() for c in spell_data.get("classes", [])]:
                    continue
                
                results.append(spell_data)
            
            return {"success": True, "results": results, "count": len(results)}
            
        except Exception as e:
            return {"success": False, "error": f"Failed to search spells: {str(e)}"}
    
    def _handle_get_spell_info(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed information about a spell"""
        try:
            spell_name = message_data.get("spell", "").strip().lower()
            
            if not spell_name:
                return {"success": False, "error": "Spell name is required"}
            
            spell_data = self._get_spell_data(spell_name)
            if not spell_data:
                return {"success": False, "error": f"Spell '{spell_name}' not found"}
            
            return {"success": True, "spell": spell_data}
            
        except Exception as e:
            return {"success": False, "error": f"Failed to get spell info: {str(e)}"}
    
    def _handle_upcast_spell(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate upcasting effects for a spell"""
        try:
            spell_name = message_data.get("spell", "").strip().lower()
            cast_level = message_data.get("level", 1)
            
            spell_data = self._get_spell_data(spell_name)
            if not spell_data:
                return {"success": False, "error": f"Spell '{spell_name}' not found"}
            
            base_level = spell_data["level"]
            if cast_level < base_level:
                return {"success": False, "error": f"Cannot cast at level {cast_level} (minimum: {base_level})"}
            
            # Calculate upcasting effects
            upcast_info = {
                "base_level": base_level,
                "cast_level": cast_level,
                "levels_higher": cast_level - base_level,
                "effects": []
            }
            
            # Parse upcasting rules from spell description
            if "higher levels" in spell_data.get("description", "").lower():
                upcast_info["effects"].append("See spell description for upcasting effects")
            
            return {"success": True, "upcast_info": upcast_info}
            
        except Exception as e:
            return {"success": False, "error": f"Failed to calculate upcasting: {str(e)}"}
    
    def _handle_get_spell_save_dc(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get spell save DC for a character"""
        try:
            character_name = message_data.get("character", "").strip().lower()
            
            if not character_name:
                return {"success": False, "error": "Character name is required"}
            
            if character_name not in self.character_spellcasting:
                return {"success": False, "error": f"Spellcasting not initialized for {character_name}"}
            
            spellcasting = self.character_spellcasting[character_name]
            
            return {
                "success": True,
                "spell_save_dc": spellcasting["spell_save_dc"],
                "calculation": f"8 + {spellcasting['proficiency_bonus']} (prof) + {spellcasting['ability_modifier']} ({spellcasting['spellcasting_ability']})"
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to get spell save DC: {str(e)}"}
    
    def _handle_get_spell_attack_bonus(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get spell attack bonus for a character"""
        try:
            character_name = message_data.get("character", "").strip().lower()
            
            if not character_name:
                return {"success": False, "error": "Character name is required"}
            
            if character_name not in self.character_spellcasting:
                return {"success": False, "error": f"Spellcasting not initialized for {character_name}"}
            
            spellcasting = self.character_spellcasting[character_name]
            
            return {
                "success": True,
                "spell_attack_bonus": spellcasting["spell_attack_bonus"],
                "calculation": f"{spellcasting['proficiency_bonus']} (prof) + {spellcasting['ability_modifier']} ({spellcasting['spellcasting_ability']})"
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to get spell attack bonus: {str(e)}"}
    
    # Helper methods
    def _load_spell_database(self):
        """Load spell database"""
        # Basic spell database (simplified)
        self.spell_database = {
            "magic missile": {
                "name": "Magic Missile",
                "level": 1,
                "school": "evocation",
                "casting_time": "1 action",
                "range": "120 feet",
                "components": ["V", "S"],
                "duration": "Instantaneous",
                "classes": ["Sorcerer", "Wizard"],
                "description": "Three glowing darts of magical force. Each dart hits a creature of your choice within range. A dart deals 1d4 + 1 force damage. At Higher Levels: One more dart for each slot level above 1st.",
                "damage": "1d4+1",
                "damage_type": "force",
                "tags": []
            },
            "fireball": {
                "name": "Fireball",
                "level": 3,
                "school": "evocation",
                "casting_time": "1 action",
                "range": "150 feet",
                "components": ["V", "S", "M"],
                "duration": "Instantaneous",
                "classes": ["Sorcerer", "Wizard"],
                "description": "A bright flash of fire erupts from your point. Each creature in a 20-foot radius must make a Dexterity saving throw. On a failed save, a creature takes 8d6 fire damage. At Higher Levels: +1d6 damage for each slot level above 3rd.",
                "damage": "8d6",
                "damage_type": "fire",
                "save": "dexterity",
                "tags": []
            },
            "cure wounds": {
                "name": "Cure Wounds",
                "level": 1,
                "school": "evocation",
                "casting_time": "1 action",
                "range": "Touch",
                "components": ["V", "S"],
                "duration": "Instantaneous",
                "classes": ["Bard", "Cleric", "Druid", "Paladin", "Ranger"],
                "description": "A creature you touch regains hit points equal to 1d8 + your spellcasting ability modifier. At Higher Levels: +1d8 for each slot level above 1st.",
                "healing": "1d8",
                "tags": []
            },
            "shield": {
                "name": "Shield",
                "level": 1,
                "school": "abjuration",
                "casting_time": "1 reaction",
                "range": "Self",
                "components": ["V", "S"],
                "duration": "1 round",
                "classes": ["Sorcerer", "Wizard"],
                "description": "An invisible barrier of magical force appears and protects you. Until the start of your next turn, you have a +5 bonus to AC.",
                "tags": []
            },
            "mage hand": {
                "name": "Mage Hand",
                "level": 0,
                "school": "conjuration",
                "casting_time": "1 action",
                "range": "30 feet",
                "components": ["V", "S"],
                "duration": "1 minute",
                "classes": ["Bard", "Sorcerer", "Warlock", "Wizard"],
                "description": "A spectral, floating hand appears at a point you choose within range. The hand lasts for the duration or until you dismiss it as an action.",
                "tags": []
            },
            "detect magic": {
                "name": "Detect Magic",
                "level": 1,
                "school": "divination",
                "casting_time": "1 action",
                "range": "Self",
                "components": ["V", "S"],
                "duration": "Concentration, up to 10 minutes",
                "classes": ["Bard", "Cleric", "Druid", "Paladin", "Ranger", "Sorcerer", "Wizard"],
                "description": "For the duration, you sense the presence of magic within 30 feet of you.",
                "tags": ["concentration", "ritual"]
            }
        }
    
    def _create_spell_slot_tables(self) -> Dict[str, Dict[str, Dict[str, int]]]:
        """Create spell slot progression tables for each class"""
        return {
            "wizard": {
                1: {"1": 2}, 2: {"1": 3}, 3: {"1": 4, "2": 2}, 4: {"1": 4, "2": 3},
                5: {"1": 4, "2": 3, "3": 2}, 6: {"1": 4, "2": 3, "3": 3},
                7: {"1": 4, "2": 3, "3": 3, "4": 1}, 8: {"1": 4, "2": 3, "3": 3, "4": 2},
                9: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 1}, 10: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2},
                11: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1},
                12: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1},
                13: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1, "7": 1},
                14: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1, "7": 1},
                15: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1, "7": 1, "8": 1},
                16: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1, "7": 1, "8": 1},
                17: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1, "7": 1, "8": 1, "9": 1},
                18: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 3, "6": 1, "7": 1, "8": 1, "9": 1},
                19: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 3, "6": 2, "7": 1, "8": 1, "9": 1},
                20: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 3, "6": 2, "7": 2, "8": 1, "9": 1}
            },
            "sorcerer": {
                1: {"1": 2}, 2: {"1": 3}, 3: {"1": 4, "2": 2}, 4: {"1": 4, "2": 3},
                5: {"1": 4, "2": 3, "3": 2}, 6: {"1": 4, "2": 3, "3": 3},
                7: {"1": 4, "2": 3, "3": 3, "4": 1}, 8: {"1": 4, "2": 3, "3": 3, "4": 2},
                9: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 1}, 10: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2},
                11: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1},
                12: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1},
                13: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1, "7": 1},
                14: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1, "7": 1},
                15: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1, "7": 1, "8": 1},
                16: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1, "7": 1, "8": 1},
                17: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1, "7": 1, "8": 1, "9": 1},
                18: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 3, "6": 1, "7": 1, "8": 1, "9": 1},
                19: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 3, "6": 2, "7": 1, "8": 1, "9": 1},
                20: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 3, "6": 2, "7": 2, "8": 1, "9": 1}
            },
            "cleric": {
                1: {"1": 2}, 2: {"1": 3}, 3: {"1": 4, "2": 2}, 4: {"1": 4, "2": 3},
                5: {"1": 4, "2": 3, "3": 2}, 6: {"1": 4, "2": 3, "3": 3},
                7: {"1": 4, "2": 3, "3": 3, "4": 1}, 8: {"1": 4, "2": 3, "3": 3, "4": 2},
                9: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 1}, 10: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2},
                11: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1},
                12: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1},
                13: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1, "7": 1},
                14: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1, "7": 1},
                15: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1, "7": 1, "8": 1},
                16: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1, "7": 1, "8": 1},
                17: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1, "7": 1, "8": 1, "9": 1},
                18: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 3, "6": 1, "7": 1, "8": 1, "9": 1},
                19: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 3, "6": 2, "7": 1, "8": 1, "9": 1},
                20: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 3, "6": 2, "7": 2, "8": 1, "9": 1}
            }
        }
    
    def _get_spell_data(self, spell_name: str) -> Optional[Dict[str, Any]]:
        """Get spell data from database"""
        return self.spell_database.get(spell_name.lower())
    
    def _get_spell_slots_for_class_level(self, character_class: str, level: int) -> Dict[str, int]:
        """Get spell slots for a class at given level"""
        class_table = self.spell_slot_tables.get(character_class, {})
        return class_table.get(level, {})
    
    def _calculate_max_prepared_spells(self, spellcasting: Dict[str, Any]) -> int:
        """Calculate maximum number of prepared spells"""
        # Most classes: ability modifier + level (minimum 1)
        return max(1, spellcasting["ability_modifier"] + spellcasting["level"])
    
    def _requires_known_spells(self, character_class: str) -> bool:
        """Check if class requires learning spells before preparing them"""
        # Sorcerers and warlocks know spells, wizards and clerics can prepare any spell
        known_spell_classes = ["sorcerer", "warlock", "bard", "ranger"]
        return character_class in known_spell_classes
    
    def _has_available_spell_slot(self, spellcasting: Dict[str, Any], level: int) -> bool:
        """Check if character has available spell slot of given level"""
        level_str = str(level)
        total_slots = spellcasting["spell_slots"].get(level_str, 0)
        used_slots = spellcasting["spell_slots_used"].get(level_str, 0)
        return used_slots < total_slots