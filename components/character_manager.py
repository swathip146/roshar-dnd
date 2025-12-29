"""
Character Manager - Stage 3 Week 11-12
Character data management and skill calculations - From Original Plan
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

class AbilityScore(Enum):
    """D&D ability scores"""
    STRENGTH = "strength"
    DEXTERITY = "dexterity" 
    CONSTITUTION = "constitution"
    INTELLIGENCE = "intelligence"
    WISDOM = "wisdom"
    CHARISMA = "charisma"

@dataclass
class CharacterSkillData:
    """Complete skill data for a character"""
    skill_name: str
    ability_score: AbilityScore
    ability_modifier: int
    proficiency_bonus: int
    is_proficient: bool
    expertise: bool  # Double proficiency
    other_bonuses: Dict[str, int]
    total_modifier: int

@dataclass
class CharacterData:
    """Complete character information"""
    character_id: str
    name: str
    level: int
    proficiency_bonus: int
    ability_scores: Dict[str, int]
    ability_modifiers: Dict[str, int]
    skills: Dict[str, bool]  # Proficiency in skills
    expertise_skills: List[str]  # Skills with expertise
    conditions: List[str]
    features: List[str]  # Class features, racial traits, etc.
    
    # Enhanced fields for comprehensive character tracking
    hit_points: Dict[str, int]  # {"current": X, "maximum": Y, "temporary": Z}
    armor_class: int
    saving_throw_proficiencies: List[str]  # Save types the character is proficient in
    character_class: str
    race: str
    background: str
    spell_slots: Dict[int, Dict[str, int]] = None  # {level: {"current": X, "maximum": Y}}

    # Roshar-specific and general state extensions
    rulebook: str = "Cosmere 5e (Roshar)"
    identity: str = "Unknown"  # Roshar cultural identity, e.g., Alethi, Azish
    radiant_order: Optional[str] = None  # e.g., Lightweaver, Windrunner
    ideal_level: int = 0  # Radiant ideal progression: 0=no oaths, 1=First Ideal, 2=Second, etc.
    investiture_points: Dict[str, int] = None  # {"current": X, "maximum": Y}
    spren: Dict[str, Any] = None  # {"type": "Cryptic", "name": "...", "status": "active"}
    surges_known: List[str] = None  # e.g., ["Illumination", "Transformation"]
    cantrips_known: List[str] = None  # Surgebinding cantrips (0-level Invested Arts)
    spells_known: List[str] = None  # Invested Arts known
    languages: List[str] = None
    equipment: List[str] = None
    personality: Dict[str, Any] = None  # {traits:[], ideals:[], bonds:[], flaws:[]}
    backstory: str = ""
    speed: int = 30
    tool_proficiencies: List[str] = None
    armor_proficiencies: List[str] = None
    weapon_proficiencies: List[str] = None
    
    # Action tracking for game session
    action_history: List[Dict[str, Any]] = None  # Track all actions taken during the session

class CharacterManager:
    """
    Character data management and skill calculations - From Original Plan
    Manages character sheets and calculates skill modifiers
    """
    
    def __init__(self):
        self.characters: Dict[str, CharacterData] = {}
        
        # Standard D&D skill-to-ability mappings
        self.skill_abilities = {
            "acrobatics": AbilityScore.DEXTERITY,
            "animal_handling": AbilityScore.WISDOM,
            "arcana": AbilityScore.INTELLIGENCE,
            "athletics": AbilityScore.STRENGTH,
            "deception": AbilityScore.CHARISMA,
            "history": AbilityScore.INTELLIGENCE,
            "insight": AbilityScore.WISDOM,
            "intimidation": AbilityScore.CHARISMA,
            "investigation": AbilityScore.INTELLIGENCE,
            "medicine": AbilityScore.WISDOM,
            "nature": AbilityScore.INTELLIGENCE,
            "perception": AbilityScore.WISDOM,
            "performance": AbilityScore.CHARISMA,
            "persuasion": AbilityScore.CHARISMA,
            "religion": AbilityScore.INTELLIGENCE,
            "sleight_of_hand": AbilityScore.DEXTERITY,
            "stealth": AbilityScore.DEXTERITY,
            "survival": AbilityScore.WISDOM
        }
        self.hit_points = {"current": 0, "maximum": 0, "temporary": 0}
        self.spell_slots = {}
        
        print("👥 Character Manager initialized")
    
    def add_character(self, character_data: Dict[str, Any]) -> str:
        """Add or update a character"""
        char_id = character_data.get("character_id", character_data.get("name", "unknown"))
        
        # Calculate ability modifiers
        ability_scores = character_data.get("ability_scores", {})
        ability_modifiers = {}
        for ability, score in ability_scores.items():
            ability_modifiers[ability] = self._calculate_ability_modifier(score)
        
        # Calculate proficiency bonus from level
        level = character_data.get("level", 1)
        proficiency_bonus = self._calculate_proficiency_bonus(level)
        
        character = CharacterData(
            character_id=char_id,
            name=character_data.get("name", char_id),
            level=level,
            proficiency_bonus=proficiency_bonus,
            ability_scores=ability_scores,
            ability_modifiers=ability_modifiers,
            skills=character_data.get("skills", {}),
            expertise_skills=character_data.get("expertise_skills", []),
            conditions=character_data.get("conditions", []),
            features=character_data.get("features", []),
            
            # Enhanced fields with defaults
            hit_points=character_data.get("hit_points", {"current": 0, "maximum": 0, "temporary": 0}),
            armor_class=character_data.get("armor_class", 10),
            saving_throw_proficiencies=character_data.get("saving_throw_proficiencies", []),
            character_class=character_data.get("character_class", "Unknown"),
            race=character_data.get("race", "Unknown"),
            background=character_data.get("background", "Unknown"),
            spell_slots=character_data.get("spell_slots", {}),

            # Roshar + general state
            rulebook=character_data.get("rulebook", "Cosmere 5e (Roshar)"),
            identity=character_data.get("identity", character_data.get("race", "Unknown")),
            radiant_order=character_data.get("radiant_order"),
            ideal_level=character_data.get("ideal_level", 0),
            investiture_points=character_data.get("investiture_points", {"current": 0, "maximum": 0}),
            spren=character_data.get("spren", {"type": None, "name": None, "status": "dormant"}),
            surges_known=character_data.get("surges_known", []),
            cantrips_known=character_data.get("cantrips_known", []),
            spells_known=character_data.get("spells_known", []),
            languages=character_data.get("languages", []),
            equipment=character_data.get("equipment", []),
            personality=character_data.get("personality", {"traits": [], "ideals": [], "bonds": [], "flaws": []}),
            backstory=character_data.get("backstory", ""),
            speed=character_data.get("speed", 30),
            tool_proficiencies=character_data.get("tool_proficiencies", []),
            armor_proficiencies=character_data.get("armor_proficiencies", []),
            weapon_proficiencies=character_data.get("weapon_proficiencies", []),
            
            # Initialize action tracking
            action_history=character_data.get("action_history", [])
        )
        
        self.characters[char_id] = character
        print(f"👤 Added character: {character.name} (Level {level})")
        
        return char_id
    
    def get_skill_data(self, character_id: str, skill: str) -> Dict[str, Any]:
        """
        Get complete skill data for character - Step 2 of 7-step pipeline
        From Original Plan: "Character Manager → skill/ability mod, conditions"
        """
        if character_id not in self.characters:
            # Return default data for unknown characters
            return {
                "character_id": character_id,
                "skill": skill,
                "ability_modifier": 0,
                "proficiency_bonus": 0,
                "is_proficient": False,
                "expertise": False,
                "other_bonuses": {},
                "modifier": 0,
                "conditions": [],
                "error": f"Character {character_id} not found"
            }
        
        character = self.characters[character_id]
        
        # Get skill's associated ability
        ability = self.skill_abilities.get(skill.lower(), AbilityScore.INTELLIGENCE)
        ability_modifier = character.ability_modifiers.get(ability.value, 0)
        
        # Check proficiency
        is_proficient = character.skills.get(skill.lower(), False)
        expertise = skill.lower() in character.expertise_skills
        
        # Calculate skill modifier
        skill_modifier = ability_modifier
        
        if is_proficient:
            if expertise:
                skill_modifier += character.proficiency_bonus * 2  # Double proficiency
            else:
                skill_modifier += character.proficiency_bonus
        
        # Check for other bonuses (features, magic items, etc.)
        other_bonuses = {}
        
        # Example feature bonuses (would be expanded with actual D&D features)
        if "guidance" in character.features and skill in ["investigation", "perception"]:
            other_bonuses["guidance"] = 1  # Simplified guidance
        
        total_other_bonus = sum(other_bonuses.values())
        total_modifier = skill_modifier + total_other_bonus
        
        return {
            "character_id": character_id,
            "skill": skill,
            "ability": ability.value,
            "ability_modifier": ability_modifier,
            "proficiency_bonus": character.proficiency_bonus if is_proficient else 0,
            "is_proficient": is_proficient,
            "expertise": expertise,
            "other_bonuses": other_bonuses,
            "modifier": total_modifier,
            "conditions": character.conditions,
            "level": character.level,
            "breakdown": self._build_skill_breakdown(skill, ability_modifier, 
                                                   character.proficiency_bonus if is_proficient else 0,
                                                   expertise, other_bonuses)
        }
    
    def get_ability_modifier(self, character_id: str, ability: str) -> int:
        """Get ability modifier for character"""
        if character_id not in self.characters:
            return 0
        
        return self.characters[character_id].ability_modifiers.get(ability.lower(), 0)
    
    def get_saving_throw_modifier(self, character_id: str, save_type: str) -> Dict[str, Any]:
        """Get saving throw modifier"""
        if character_id not in self.characters:
            return {"modifier": 0, "proficient": False}
        
        character = self.characters[character_id]
        
        # Map save types to abilities
        save_abilities = {
            "strength": AbilityScore.STRENGTH,
            "dexterity": AbilityScore.DEXTERITY,
            "constitution": AbilityScore.CONSTITUTION,
            "intelligence": AbilityScore.INTELLIGENCE,
            "wisdom": AbilityScore.WISDOM,
            "charisma": AbilityScore.CHARISMA
        }
        
        ability = save_abilities.get(save_type.lower(), AbilityScore.CONSTITUTION)
        ability_modifier = character.ability_modifiers.get(ability.value, 0)
        
        # Check for save proficiency (would come from class features)
        save_proficiencies = getattr(character, 'saving_throw_proficiencies', [])
        is_proficient = save_type.lower() in [s.lower() for s in save_proficiencies]
        
        modifier = ability_modifier
        if is_proficient:
            modifier += character.proficiency_bonus
        
        return {
            "modifier": modifier,
            "ability_modifier": ability_modifier,
            "proficiency_bonus": character.proficiency_bonus if is_proficient else 0,
            "proficient": is_proficient,
            "breakdown": f"{ability_modifier} (ability) + {character.proficiency_bonus if is_proficient else 0} (prof) = {modifier}"
        }
    
    def update_character_condition(self, character_id: str, condition: str, add: bool = True):
        """Add or remove character condition"""
        if character_id not in self.characters:
            return False
        
        character = self.characters[character_id]
        
        if add and condition not in character.conditions:
            character.conditions.append(condition)
            print(f"➕ Added condition '{condition}' to {character.name}")
        elif not add and condition in character.conditions:
            character.conditions.remove(condition)
            print(f"➖ Removed condition '{condition}' from {character.name}")
        
        return True
    
    def get_passive_score(self, character_id: str, skill: str) -> Dict[str, Any]:
        """Calculate passive skill score (10 + modifiers)"""
        skill_data = self.get_skill_data(character_id, skill)
        
        passive_score = 10 + skill_data["modifier"]
        
        return {
            "passive_score": passive_score,
            "skill": skill,
            "modifier": skill_data["modifier"],
            "breakdown": f"10 + {skill_data['modifier']} = {passive_score}",
            "character_id": character_id
        }
    
    def _calculate_ability_modifier(self, ability_score: int) -> int:
        """Calculate D&D ability modifier from score"""
        return (ability_score - 10) // 2
    
    def _calculate_proficiency_bonus(self, level: int) -> int:
        """Calculate proficiency bonus from character level"""
        return 2 + ((level - 1) // 4)
    
    def _build_skill_breakdown(self, skill: str, ability_mod: int, 
                             prof_bonus: int, expertise: bool, 
                             other_bonuses: Dict[str, int]) -> str:
        """Build human-readable skill modifier breakdown"""
        parts = [f"{ability_mod} (ability)"]
        
        if prof_bonus > 0:
            if expertise:
                parts.append(f"{prof_bonus} (expertise)")
            else:
                parts.append(f"{prof_bonus} (proficiency)")
        
        for bonus_name, bonus_value in other_bonuses.items():
            if bonus_value != 0:
                parts.append(f"{bonus_value:+d} ({bonus_name})")
        
        total = ability_mod + prof_bonus + sum(other_bonuses.values())
        
        return " + ".join(parts) + f" = {total}"
    
    def get_character_summary(self, character_id: str) -> Dict[str, Any]:
        """Get complete character summary"""
        if character_id not in self.characters:
            return {"error": f"Character {character_id} not found"}
        
        character = self.characters[character_id]
        
        # Calculate some key passive scores
        passive_scores = {}
        key_skills = ["perception", "investigation", "insight"]
        for skill in key_skills:
            passive_data = self.get_passive_score(character_id, skill)
            passive_scores[skill] = passive_data["passive_score"]
        
        return {
            "character_id": character.character_id,
            "name": character.name,
            "level": character.level,
            "proficiency_bonus": character.proficiency_bonus,
            "ability_scores": character.ability_scores,
            "ability_modifiers": character.ability_modifiers,
            "passive_scores": passive_scores,
            "conditions": character.conditions,
            "skill_count": len([s for s, prof in character.skills.items() if prof]),
            "expertise_count": len(character.expertise_skills)
        }
    
    def list_characters(self) -> List[Dict[str, Any]]:
        """Get list of all managed characters"""
        return [
            {
                "character_id": char.character_id,
                "name": char.name,
                "level": char.level,
                "conditions": len(char.conditions)
            }
            for char in self.characters.values()
        ]
    
    def get_party_composition(self) -> Dict[str, Any]:
        """
        Analyze party composition for scenario context
        Enhanced method for comprehensive party analysis
        """
        if not self.characters:
            return {
                "party_size": 0,
                "average_level": 0,
                "level_range": [0, 0],
                "classes": {},
                "roles": {},
                "party_strengths": [],
                "party_weaknesses": []
            }
        
        levels = [char.level for char in self.characters.values()]
        party_size = len(self.characters)
        average_level = sum(levels) / party_size
        level_range = [min(levels), max(levels)]
        
        # Class distribution
        classes = {}
        roles = {"tank": 0, "healer": 0, "dps": 0, "support": 0, "scout": 0}
        
        for char in self.characters.values():
            char_class = char.character_class.lower()
            classes[char_class] = classes.get(char_class, 0) + 1
            
            # Role assignment based on class (simplified)
            role_mapping = {
                "fighter": "tank", "paladin": "tank", "barbarian": "tank",
                "cleric": "healer", "druid": "healer", "bard": "support",
                "wizard": "dps", "sorcerer": "dps", "warlock": "dps",
                "ranger": "scout", "rogue": "scout",
                "monk": "dps"  # Can be flexible
            }
            
            role = role_mapping.get(char_class, "dps")
            roles[role] += 1
        
        # Analyze party strengths and weaknesses
        party_strengths = []
        party_weaknesses = []
        
        if roles["healer"] >= 1:
            party_strengths.append("Strong healing capabilities")
        else:
            party_weaknesses.append("Limited healing resources")
        
        if roles["tank"] >= 1:
            party_strengths.append("Good front-line defense")
        else:
            party_weaknesses.append("Fragile front line")
        
        if roles["scout"] >= 1:
            party_strengths.append("Good reconnaissance and stealth")
        else:
            party_weaknesses.append("Limited scouting abilities")
        
        if party_size >= 4:
            party_strengths.append("Well-rounded party size")
        elif party_size <= 2:
            party_weaknesses.append("Small party - vulnerable to setbacks")
        
        return {
            "party_size": party_size,
            "average_level": round(average_level, 1),
            "level_range": level_range,
            "level_spread": max(levels) - min(levels),
            "classes": classes,
            "roles": roles,
            "party_strengths": party_strengths,
            "party_weaknesses": party_weaknesses,
            "balanced_party": len([r for r in roles.values() if r > 0]) >= 3
        }
    
    def get_individual_character_analysis(self, character_id: str) -> Dict[str, Any]:
        """
        Get detailed individual character analysis for scenario context
        Enhanced method for comprehensive character assessment
        """
        if character_id not in self.characters:
            return {"error": f"Character {character_id} not found"}
        
        character = self.characters[character_id]
        
        # Analyze key capabilities
        primary_abilities = []
        secondary_abilities = []
        
        for ability, modifier in character.ability_modifiers.items():
            if modifier >= 3:
                primary_abilities.append(f"{ability} (+{modifier})")
            elif modifier >= 1:
                secondary_abilities.append(f"{ability} (+{modifier})")
        
        # Analyze skill proficiencies
        skill_categories = {
            "social": ["deception", "intimidation", "persuasion", "performance"],
            "knowledge": ["arcana", "history", "nature", "religion"],
            "physical": ["acrobatics", "athletics", "sleight_of_hand", "stealth"],
            "perception": ["insight", "investigation", "medicine", "perception", "survival"]
        }
        
        skill_strengths = {}
        for category, skills in skill_categories.items():
            category_skills = [s for s in skills if character.skills.get(s, False)]
            if category_skills:
                skill_strengths[category] = category_skills
        
        # Assess combat capabilities
        combat_assessment = {
            "armor_class": character.armor_class,
            "hit_points": character.hit_points,
            "survivability": "high" if character.hit_points.get("maximum", 0) > (character.level * 8) else "moderate",
            "has_spells": bool(character.spell_slots),
            "has_investiture": bool(character.investiture_points and character.investiture_points.get("maximum", 0) > 0),
            "radiant_order": character.radiant_order,
            "spren_bond": character.spren.get("status", "dormant") if character.spren else "none"
        }
        
        # Roleplay potential
        roleplay_hooks = []
        if character.background != "Unknown":
            roleplay_hooks.append(f"Background: {character.background}")
        if character.race != "Unknown":
            roleplay_hooks.append(f"Race: {character.race}")
        if character.identity != "Unknown" and character.identity != character.race:
            roleplay_hooks.append(f"Identity: {character.identity}")
        if character.radiant_order:
            roleplay_hooks.append(f"Radiant Order: {character.radiant_order}")
        if character.spren and character.spren.get("type"):
            roleplay_hooks.append(f"Spren Bond: {character.spren.get('type', 'Unknown')}")
        
        return {
            "character_id": character_id,
            "name": character.name,
            "level": character.level,
            "class": character.character_class,
            "primary_abilities": primary_abilities,
            "secondary_abilities": secondary_abilities,
            "skill_strengths": skill_strengths,
            "combat_assessment": combat_assessment,
            "roleplay_hooks": roleplay_hooks,
            "conditions": character.conditions,
            "special_features": len(character.features),
            "expertise_count": len(character.expertise_skills)
        }
    
    def get_party_snapshot(self) -> Dict[str, Any]:
        """Get comprehensive party information for scenario generation"""
        if not self.characters:
            return self._default_party_snapshot()
            
        characters = list(self.characters.values())
        levels = [char.level for char in characters]
        
        return {
            'avg_level': sum(levels) // len(levels) if levels else 3,
            'party_size': len(characters),
            'level_range': f"{min(levels)}-{max(levels)}" if levels else "1-3",
            'party_roles': self._analyze_party_roles(),
            'hp_state': self._analyze_hp_status(),
            'resources': self._analyze_party_resources(),
            'stealth_profile': self._analyze_stealth_capability(),
            'conditions_summary': self._summarize_conditions(),
            'party_dynamics': self._assess_party_dynamics(),
            'characters': [self._get_character_for_scenario(char) for char in characters]
        }

    def _analyze_party_roles(self) -> Dict[str, int]:
        """Analyze tank/striker/support/control composition"""
        roles = {'tank': 0, 'striker': 0, 'support': 0, 'control': 0}
        
        for char in self.characters.values():
            # Determine role based on class (simplified)
            char_class = getattr(char, 'character_class', 'Fighter').lower()
            
            if char_class in ['fighter', 'paladin', 'barbarian']:
                roles['striker'] += 1
            elif char_class in ['cleric', 'druid', 'bard']:
                roles['support'] += 1
            elif char_class in ['wizard', 'sorcerer', 'warlock']:
                roles['control'] += 1
            elif char_class == 'radiant':
                # Radiant role depends on order
                radiant_order = getattr(char, 'radiant_order', '').lower()
                if radiant_order in ['windrunner', 'stoneward']:
                    roles['tank'] += 1
                elif radiant_order in ['edgedancer', 'truthwatcher']:
                    roles['support'] += 1
                elif radiant_order in ['lightweaver', 'elsecaller']:
                    roles['control'] += 1
                else:
                    roles['striker'] += 1  # Default for unknown orders
            else:
                roles['striker'] += 1  # Default
        
        return roles
    
    def _analyze_hp_status(self) -> Dict[str, Any]:
        """Analyze party health status"""
        if not self.characters:
            return {'average_hp_percent': 85, 'wounded_members': 0, 'critical_members': 0, 'healing_available': True}
        
        hp_percentages = []
        wounded_count = 0
        critical_count = 0
        
        for char in self.characters.values():
            # Use basic hp values or defaults
            hp_max = getattr(char, 'hp_max', 10)
            hp_current = getattr(char, 'hp_current', hp_max)
            
            if hp_max > 0:
                hp_percent = (hp_current / hp_max) * 100
                hp_percentages.append(hp_percent)
                
                if hp_percent < 50:
                    wounded_count += 1
                if hp_percent < 25:
                    critical_count += 1
        
        avg_hp = sum(hp_percentages) / len(hp_percentages) if hp_percentages else 85
        
        return {
            'average_hp_percent': int(avg_hp),
            'wounded_members': wounded_count,
            'critical_members': critical_count,
            'healing_available': True  # Assume some healing available
        }
    
    def _analyze_party_resources(self) -> Dict[str, Any]:
        """Analyze spell slots, investiture, consumables for encounter planning"""
        total_spell_slots = 0
        total_investiture = 0
        
        for char in self.characters.values():
            # Count spell slots
            if char.spell_slots:
                for level_slots in char.spell_slots.values():
                    total_spell_slots += level_slots.get('current', 0)
            
            # Count investiture points
            if char.investiture_points:
                total_investiture += char.investiture_points.get('current', 0)
        
        # Determine resource levels
        spell_level = 'high' if total_spell_slots > 10 else 'medium' if total_spell_slots > 5 else 'low'
        investiture_level = 'high' if total_investiture > 20 else 'medium' if total_investiture > 10 else 'low'
        
        return {
            'spell_slots_remaining': spell_level,
            'investiture_remaining': investiture_level,
            'consumables': ['healing_potion(2)', 'rope(50ft)'],
            'special_abilities_available': True,
            'long_rest_needed': spell_level == 'low' and investiture_level == 'low'
        }
    
    def _analyze_stealth_capability(self) -> str:
        """Analyze party stealth profile"""
        return 'normal'  # Simplified for now
    
    def _summarize_conditions(self) -> List[str]:
        """Summarize active conditions across the party"""
        all_conditions = []
        for char in self.characters.values():
            all_conditions.extend(char.conditions)
        
        # Return unique conditions
        return list(set(all_conditions))
    
    def _assess_party_dynamics(self) -> Dict[str, Any]:
        """Assess party composition balance"""
        party_size = len(self.characters)
        
        if party_size >= 3 and party_size <= 5:
            effectiveness = 'optimal'
        elif party_size == 2:
            effectiveness = 'small_but_viable'
        elif party_size == 1:
            effectiveness = 'solo_challenge'
        else:
            effectiveness = 'large_group'
        
        return {
            'balance': 'decent',
            'size_effectiveness': effectiveness,
            'role_coverage': self._analyze_party_roles()
        }
    
    def _get_character_for_scenario(self, char: CharacterData) -> Dict[str, Any]:
        """Get character summary for scenario generation"""
        return {
            'name': char.name,
            'level': char.level,
            'class': getattr(char, 'character_class', 'Fighter'),
            'hp_percent': 100,  # Simplified
            'conditions': char.conditions,
            'stealth_capable': 'stealth' in char.skills
        }
    
    def _default_party_snapshot(self) -> Dict[str, Any]:
        """Return default party snapshot when no characters available"""
        return {
            'avg_level': 3,
            'party_size': 1,
            'level_range': "1-3",
            'party_roles': {'tank': 0, 'striker': 1, 'support': 0, 'control': 0},
            'hp_state': {'average_hp_percent': 85, 'wounded_members': 0, 'critical_members': 0, 'healing_available': False},
            'resources': {'spell_slots_remaining': 'none', 'consumables': [], 'special_abilities_available': False, 'long_rest_needed': False},
            'stealth_profile': 'normal',
            'conditions_summary': [],
            'party_dynamics': {'balance': 'unknown', 'size_effectiveness': 'solo_challenge'},
            'characters': []
        }
    
    def get_party_context(self) -> Dict[str, Any]:
        """
        Get comprehensive party context for scenario generation
        Combines party composition and individual analyses
        """
        party_composition = self.get_party_composition()
        
        individual_analyses = {}
        for char_id in self.characters.keys():
            individual_analyses[char_id] = self.get_individual_character_analysis(char_id)
        
        # Calculate party-wide capabilities
        party_skills = {}
        for char_analysis in individual_analyses.values():
            if "error" not in char_analysis:
                for category, skills in char_analysis.get("skill_strengths", {}).items():
                    if category not in party_skills:
                        party_skills[category] = []
                    party_skills[category].extend(skills)
        
        # Remove duplicates and count coverage
        for category in party_skills:
            party_skills[category] = list(set(party_skills[category]))
        
        return {
            "party_composition": party_composition,
            "individual_characters": individual_analyses,
            "party_capabilities": {
                "skill_coverage": party_skills,
                "total_characters": len(individual_analyses),
                "healthy_characters": len([c for c in individual_analyses.values()
                                          if "error" not in c and not c.get("conditions", [])])
            },
            "scenario_recommendations": self._generate_scenario_recommendations(party_composition, individual_analyses)
        }
    
    def _generate_scenario_recommendations(self, composition: Dict[str, Any],
                                         analyses: Dict[str, Any]) -> List[str]:
        """Generate scenario recommendations based on party analysis"""
        recommendations = []
        
        # Based on party size
        if composition["party_size"] <= 2:
            recommendations.append("Focus on roleplay and investigation over combat")
            recommendations.append("Provide escape routes and alternatives to direct confrontation")
        elif composition["party_size"] >= 5:
            recommendations.append("Can handle complex multi-part encounters")
            recommendations.append("Consider group coordination challenges")
        
        # Based on roles
        if composition["roles"]["healer"] == 0:
            recommendations.append("Include healing potions or rest opportunities")
        
        if composition["roles"]["scout"] == 0:
            recommendations.append("Avoid scenarios requiring extensive stealth")
        
        if composition["roles"]["tank"] == 0:
            recommendations.append("Consider ranged combat scenarios or defensive positions")
        
        # Based on level spread
        if composition["level_spread"] > 2:
            recommendations.append("Balance challenges to engage both high and low level characters")
        
        return recommendations

    # Roshar/Cosmere-specific methods
    
    def update_investiture_points(self, character_id: str, current: Optional[int] = None, 
                                maximum: Optional[int] = None) -> bool:
        """Update character's investiture points"""
        if character_id not in self.characters:
            return False
        
        character = self.characters[character_id]
        if not character.investiture_points:
            character.investiture_points = {"current": 0, "maximum": 0}
        
        if current is not None:
            character.investiture_points["current"] = max(0, current)
        if maximum is not None:
            character.investiture_points["maximum"] = max(0, maximum)
            # Ensure current doesn't exceed maximum
            character.investiture_points["current"] = min(
                character.investiture_points["current"], 
                character.investiture_points["maximum"]
            )
        
        print(f"🌟 Updated {character.name}'s investiture: {character.investiture_points}")
        return True
    
    def spend_investiture(self, character_id: str, amount: int) -> bool:
        """Spend investiture points for surgebinding"""
        if character_id not in self.characters:
            return False
        
        character = self.characters[character_id]
        if not character.investiture_points:
            return False
        
        current = character.investiture_points.get("current", 0)
        if current >= amount:
            character.investiture_points["current"] = current - amount
            print(f"⚡ {character.name} spent {amount} investiture ({character.investiture_points['current']} remaining)")
            return True
        
        print(f"❌ {character.name} doesn't have enough investiture ({current} < {amount})")
        return False
    
    def update_spren_bond(self, character_id: str, spren_type: Optional[str] = None,
                         spren_name: Optional[str] = None, status: Optional[str] = None) -> bool:
        """Update character's spren bond information"""
        if character_id not in self.characters:
            return False
        
        character = self.characters[character_id]
        if not character.spren:
            character.spren = {"type": None, "name": None, "status": "dormant"}
        
        if spren_type is not None:
            character.spren["type"] = spren_type
        if spren_name is not None:
            character.spren["name"] = spren_name
        if status is not None:
            character.spren["status"] = status
        
        print(f"🧚 Updated {character.name}'s spren bond: {character.spren}")
        return True
    
    def add_surge(self, character_id: str, surge_name: str) -> bool:
        """Add a surge to character's known surges"""
        if character_id not in self.characters:
            return False
        
        character = self.characters[character_id]
        if not character.surges_known:
            character.surges_known = []
        
        if surge_name not in character.surges_known:
            character.surges_known.append(surge_name)
            print(f"⚡ {character.name} learned surge: {surge_name}")
            return True
        
        print(f"ℹ️ {character.name} already knows surge: {surge_name}")
        return False
    
    def add_invested_art(self, character_id: str, art_name: str, is_cantrip: bool = False) -> bool:
        """Add an invested art (spell) to character's known arts"""
        if character_id not in self.characters:
            return False
        
        character = self.characters[character_id]
        
        if is_cantrip:
            if not character.cantrips_known:
                character.cantrips_known = []
            if art_name not in character.cantrips_known:
                character.cantrips_known.append(art_name)
                print(f"🕯️ {character.name} learned cantrip: {art_name}")
                return True
        else:
            if not character.spells_known:
                character.spells_known = []
            if art_name not in character.spells_known:
                character.spells_known.append(art_name)
                print(f"✨ {character.name} learned invested art: {art_name}")
                return True
        
        print(f"ℹ️ {character.name} already knows: {art_name}")
        return False
    
    def advance_ideal(self, character_id: str, oath_text: str = None) -> bool:
        """Advance character to next ideal level"""
        if character_id not in self.characters:
            return False
        
        character = self.characters[character_id]
        
        # Only Radiants can advance ideals
        if character.character_class.lower() != "radiant":
            print(f"❌ {character.name} is not a Radiant and cannot speak oaths")
            return False
        
        # Maximum of 5 ideals (0-4, where 4 is typically theoretical)
        if character.ideal_level >= 4:
            print(f"❌ {character.name} has already reached the highest known ideal")
            return False
        
        old_level = character.ideal_level
        character.ideal_level += 1
        
        # Define the standard oaths
        standard_oaths = {
            1: "Life before death, strength before weakness, journey before destination",
            2: "I will protect those who cannot protect themselves",  # Generic Second Ideal
            3: "I will protect even those I hate, so long as it is right",  # Generic Third Ideal
            4: "I accept that there will be those I cannot protect"  # Generic Fourth Ideal
        }
        
        oath_spoken = oath_text or standard_oaths.get(character.ideal_level, "A personal oath")
        
        print(f"🌟 {character.name} spoke their {self._get_ideal_name(character.ideal_level)} Ideal!")
        print(f"   Oath: \"{oath_spoken}\"")
        print(f"   Advanced from {self._get_ideal_name(old_level)} to {self._get_ideal_name(character.ideal_level)}")
        
        # Grant benefits based on ideal level
        self._grant_ideal_benefits(character_id, character.ideal_level)
        
        return True
    
    def get_ideal_level(self, character_id: str) -> int:
        """Get character's current ideal level"""
        if character_id not in self.characters:
            return 0
        
        return self.characters[character_id].ideal_level
    
    def get_ideal_name(self, character_id: str) -> str:
        """Get the name of character's current ideal level"""
        ideal_level = self.get_ideal_level(character_id)
        return self._get_ideal_name(ideal_level)
    
    def _get_ideal_name(self, ideal_level: int) -> str:
        """Convert ideal level number to name"""
        ideal_names = {
            0: "No Oaths",
            1: "First",
            2: "Second", 
            3: "Third",
            4: "Fourth",
            5: "Fifth"
        }
        return ideal_names.get(ideal_level, f"Unknown ({ideal_level})")
    
    def _grant_ideal_benefits(self, character_id: str, ideal_level: int):
        """Grant benefits when advancing to a new ideal"""
        character = self.characters[character_id]
        
        if ideal_level == 1:
            # First Ideal - Basic Radiant abilities
            print(f"   ✨ {character.name} gains basic Radiant abilities")
            # Increase investiture if not already set
            if not character.investiture_points or character.investiture_points.get("maximum", 0) == 0:
                character.investiture_points = {"current": 3, "maximum": 5}
                print(f"   🌟 Gained investiture points: {character.investiture_points}")
            
        elif ideal_level == 2:
            # Second Ideal - Enhanced abilities, more investiture
            print(f"   ✨ {character.name} gains enhanced Radiant abilities")
            if character.investiture_points:
                character.investiture_points["maximum"] += 3
                character.investiture_points["current"] = character.investiture_points["maximum"]
                print(f"   🌟 Investiture increased: {character.investiture_points}")
            
        elif ideal_level == 3:
            # Third Ideal - Shardblade manifestation
            print(f"   ⚔️ {character.name} can now manifest a Shardblade!")
            if character.investiture_points:
                character.investiture_points["maximum"] += 5
                character.investiture_points["current"] = character.investiture_points["maximum"]
                print(f"   🌟 Investiture increased: {character.investiture_points}")
            
        elif ideal_level == 4:
            # Fourth Ideal - Shardplate manifestation
            print(f"   🛡️ {character.name} can now manifest Shardplate!")
            if character.investiture_points:
                character.investiture_points["maximum"] += 7
                character.investiture_points["current"] = character.investiture_points["maximum"]
                print(f"   🌟 Investiture increased: {character.investiture_points}")
    
    def can_advance_ideal(self, character_id: str) -> Dict[str, Any]:
        """Check if character can advance to next ideal"""
        if character_id not in self.characters:
            return {"can_advance": False, "reason": "Character not found"}
        
        character = self.characters[character_id]
        
        if character.character_class.lower() != "radiant":
            return {"can_advance": False, "reason": "Not a Radiant"}
        
        if character.ideal_level >= 4:
            return {"can_advance": False, "reason": "Already at maximum ideal"}
        
        # Check spren bond status
        if not character.spren or character.spren.get("status") != "active":
            return {"can_advance": False, "reason": "Spren bond not active"}
        
        return {
            "can_advance": True,
            "current_level": character.ideal_level,
            "next_level": character.ideal_level + 1,
            "next_ideal_name": self._get_ideal_name(character.ideal_level + 1)
        }
    
    def add_equipment(self, character_id: str, item_name: str) -> bool:
        """Add equipment to character"""
        if character_id not in self.characters:
            return False
        
        character = self.characters[character_id]
        if not character.equipment:
            character.equipment = []
        
        character.equipment.append(item_name)
        print(f"🎒 Added {item_name} to {character.name}'s equipment")
        return True
    
    def remove_equipment(self, character_id: str, item_name: str) -> bool:
        """Remove equipment from character"""
        if character_id not in self.characters:
            return False
        
        character = self.characters[character_id]
        if character.equipment and item_name in character.equipment:
            character.equipment.remove(item_name)
            print(f"🗑️ Removed {item_name} from {character.name}'s equipment")
            return True
        
        return False
    
    def add_proficiency(self, character_id: str, proficiency_type: str, proficiency_name: str) -> bool:
        """Add proficiency to character (tool, armor, weapon)"""
        if character_id not in self.characters:
            return False
        
        character = self.characters[character_id]
        
        if proficiency_type == "tool":
            if not character.tool_proficiencies:
                character.tool_proficiencies = []
            if proficiency_name not in character.tool_proficiencies:
                character.tool_proficiencies.append(proficiency_name)
                print(f"🔧 {character.name} gained tool proficiency: {proficiency_name}")
                return True
        elif proficiency_type == "armor":
            if not character.armor_proficiencies:
                character.armor_proficiencies = []
            if proficiency_name not in character.armor_proficiencies:
                character.armor_proficiencies.append(proficiency_name)
                print(f"🛡️ {character.name} gained armor proficiency: {proficiency_name}")
                return True
        elif proficiency_type == "weapon":
            if not character.weapon_proficiencies:
                character.weapon_proficiencies = []
            if proficiency_name not in character.weapon_proficiencies:
                character.weapon_proficiencies.append(proficiency_name)
                print(f"⚔️ {character.name} gained weapon proficiency: {proficiency_name}")
                return True
        
        return False
    
    def get_roshar_character_summary(self, character_id: str) -> Dict[str, Any]:
        """Get Roshar-specific character summary"""
        if character_id not in self.characters:
            return {"error": f"Character {character_id} not found"}
        
        character = self.characters[character_id]
        
        return {
            "character_id": character_id,
            "name": character.name,
            "identity": character.identity,
            "radiant_order": character.radiant_order,
            "ideal_level": character.ideal_level,
            "ideal_name": self._get_ideal_name(character.ideal_level),
            "rulebook": character.rulebook,
            "investiture_points": character.investiture_points,
            "spren_bond": character.spren,
            "surges_known": character.surges_known or [],
            "cantrips_known": character.cantrips_known or [],
            "spells_known": character.spells_known or [],
            "languages": character.languages or [],
            "equipment_count": len(character.equipment or []),
            "proficiencies": {
                "tools": character.tool_proficiencies or [],
                "armor": character.armor_proficiencies or [],
                "weapons": character.weapon_proficiencies or []
            },
            "personality": character.personality,
            "backstory": character.backstory
        }
    
    def get_party_roshar_context(self) -> Dict[str, Any]:
        """Get party context with Roshar-specific information"""
        if not self.characters:
            return {"error": "No characters in party"}
        
        identities = {}
        radiant_orders = {}
        total_investiture = 0
        active_spren_bonds = 0
        
        for char in self.characters.values():
            # Count identities
            identity = char.identity or "Unknown"
            identities[identity] = identities.get(identity, 0) + 1
            
            # Count radiant orders
            if char.radiant_order:
                radiant_orders[char.radiant_order] = radiant_orders.get(char.radiant_order, 0) + 1
            
            # Sum investiture
            if char.investiture_points:
                total_investiture += char.investiture_points.get("current", 0)
            
            # Count active spren bonds
            if char.spren and char.spren.get("status") == "active":
                active_spren_bonds += 1
        
        return {
            "party_size": len(self.characters),
            "cultural_identities": identities,
            "radiant_orders": radiant_orders,
            "total_investiture": total_investiture,
            "active_spren_bonds": active_spren_bonds,
            "roshar_party_type": "Radiant Knights" if radiant_orders else "Mixed Adventurers"
        }
    
    # Action Tracking Methods
    
    def log_character_action(self, character_id: str, action_type: str, action_description: str, 
                           turn_number: int = None, additional_data: Dict[str, Any] = None) -> bool:
        """Log an action taken by a character"""
        if character_id not in self.characters:
            return False
        
        character = self.characters[character_id]
        if not character.action_history:
            character.action_history = []
        
        import time
        action_entry = {
            "turn_number": turn_number,
            "timestamp": time.time(),
            "action_type": action_type,  # e.g., "movement", "attack", "skill_check", "spell_cast", "oath_spoken", "dialogue"
            "description": action_description,
            "character_name": character.name,
            "additional_data": additional_data or {}
        }
        
        character.action_history.append(action_entry)
        print(f"📝 Logged action for {character.name}: {action_description}")
        return True
    
    def get_character_action_history(self, character_id: str, limit: int = None) -> List[Dict[str, Any]]:
        """Get character's action history, optionally limited to recent actions"""
        if character_id not in self.characters:
            return []
        
        character = self.characters[character_id]
        if not character.action_history:
            return []
        
        history = character.action_history.copy()
        if limit:
            history = history[-limit:]  # Get most recent actions
        
        return history
    
    def get_party_action_history(self, limit_per_character: int = None) -> Dict[str, List[Dict[str, Any]]]:
        """Get action history for all party members"""
        party_history = {}
        
        for char_id, character in self.characters.items():
            party_history[char_id] = self.get_character_action_history(char_id, limit_per_character)
        
        return party_history
    
    def get_recent_party_actions(self, turn_limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent actions across all party members, sorted by turn/timestamp"""
        all_actions = []
        
        for char_id, character in self.characters.items():
            if character.action_history:
                for action in character.action_history:
                    action_copy = action.copy()
                    action_copy["character_id"] = char_id
                    all_actions.append(action_copy)
        
        # Sort by turn number (if available) then by timestamp
        all_actions.sort(key=lambda x: (x.get("turn_number", 0), x.get("timestamp", 0)))
        
        # Filter to recent turns if turn_limit specified
        if turn_limit and all_actions:
            latest_turn = max(action.get("turn_number", 0) for action in all_actions)
            cutoff_turn = max(1, latest_turn - turn_limit + 1)
            all_actions = [action for action in all_actions 
                          if action.get("turn_number", 0) >= cutoff_turn]
        
        return all_actions
    
    def clear_character_action_history(self, character_id: str) -> bool:
        """Clear a character's action history (useful for new sessions)"""
        if character_id not in self.characters:
            return False
        
        character = self.characters[character_id]
        character.action_history = []
        print(f"🗑️ Cleared action history for {character.name}")
        return True
    
    def get_action_summary(self, character_id: str) -> Dict[str, Any]:
        """Get a summary of character's actions"""
        if character_id not in self.characters:
            return {"error": "Character not found"}
        
        character = self.characters[character_id]
        if not character.action_history:
            return {
                "character_name": character.name,
                "total_actions": 0,
                "action_types": {},
                "first_action": None,
                "last_action": None
            }
        
        # Count action types
        action_types = {}
        for action in character.action_history:
            action_type = action.get("action_type", "unknown")
            action_types[action_type] = action_types.get(action_type, 0) + 1
        
        return {
            "character_name": character.name,
            "total_actions": len(character.action_history),
            "action_types": action_types,
            "first_action": character.action_history[0] if character.action_history else None,
            "last_action": character.action_history[-1] if character.action_history else None,
            "turns_active": len(set(action.get("turn_number") for action in character.action_history 
                                  if action.get("turn_number") is not None))
        }


# Factory function for easy integration
def create_character_manager() -> CharacterManager:
    """Factory function to create configured character manager"""
    return CharacterManager()


# Example usage for Stage 3 testing
if __name__ == "__main__":
    # Test character manager functionality
    manager = create_character_manager()
    
    # Add a sample character
    sample_character = {
        "character_id": "player1",
        "name": "Thorin Ironshield",
        "level": 3,
        "ability_scores": {
            "strength": 16,
            "dexterity": 12,
            "constitution": 14,
            "intelligence": 10,
            "wisdom": 13,
            "charisma": 8
        },
        "skills": {
            "athletics": True,
            "intimidation": True,
            "perception": True
        },
        "expertise_skills": ["athletics"],
        "conditions": [],
        "features": ["guidance"]
    }
    
    char_id = manager.add_character(sample_character)
    
    # Test skill data retrieval
    athletics_data = manager.get_skill_data(char_id, "athletics")
    print(f"Athletics skill data: {athletics_data}")
    
    # Test passive score
    passive_perception = manager.get_passive_score(char_id, "perception")
    print(f"Passive Perception: {passive_perception}")
    
    # Test character summary
    summary = manager.get_character_summary(char_id)
    print(f"Character summary: {summary}")