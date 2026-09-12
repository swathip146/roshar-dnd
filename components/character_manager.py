"""
Character Manager - Stage 3 Week 11-12
Character data management and skill calculations - From Original Plan
"""

import copy
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict, fields
from enum import Enum

from config.logging_config import get_logger

# Initialize logger
logger = get_logger(__name__)


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

    # Roshar-specific and general state extensions (UPDATED 2026-01-03 for Combat Plan v4.0)
    rulebook: str = "Cosmere 5e (Roshar)"
    identity: str = "Unknown"  # Roshar cultural identity, e.g., Alethi, Azish
    radiant_order: Optional[str] = None  # e.g., Lightweaver, Windrunner
    ideal_level: int = 0  # Radiant ideal progression: 0=no oaths, 1=First Ideal, 2=Second, etc.

    # Stormlight tracking (Combat Plan v4.0 requirement)
    stormlight_current: int = 0  # Current spheres held
    stormlight_capacity: int = 0  # Max spheres = Radiant Level × 2

    # Shardblade tracking (Combat Plan v4.0 requirement)
    has_shardblade: bool = False
    shardblade_summoned: bool = False
    shardblade_type: Optional[str] = None  # "living" (bonded) or "dead" (ancient)
    shardblade_name: Optional[str] = None  # Name of the blade

    # Shardplate tracking (Combat Plan v4.0 requirement)
    has_shardplate: bool = False
    shardplate_hp_current: int = 0
    shardplate_hp_maximum: int = 0  # Typically Level × 5
    shardplate_type: Optional[str] = None  # "living" (bonded) or "dead" (ancient)

    # Surgebinding progression (Combat Plan v4.0 requirement)
    surgebinding_level: int = 0  # Derived from ideal_level for combat checks

    # Legacy field - kept for backward compatibility
    investiture_points: Dict[str, int] = None  # {"current": X, "maximum": Y} - use stormlight_current/capacity instead

    spren: Dict[str, Any] = None  # {"type": "Cryptic", "name": "...", "status": "active"}
    surges_known: List[str] = None  # e.g., ["Illumination", "Transformation"]
    cantrips_known: List[str] = None  # Surgebinding cantrips (0-level Invested Arts)
    spells_known: List[str] = None  # Invested Arts known
    languages: List[str] = None
    equipment: List[str] = None
    currency: Dict[str, int] = None  # {"gp": X, "sp": Y, "cp": Z, "pp": W, "ep": V}
    personality: Dict[str, Any] = None  # {traits:[], ideals:[], bonds:[], flaws:[]}
    backstory: str = ""
    speed: int = 30
    tool_proficiencies: List[str] = None
    armor_proficiencies: List[str] = None
    weapon_proficiencies: List[str] = None
    
    # Action tracking for game session
    action_history: List[Dict[str, Any]] = None  # Track all actions taken during the session

    # Class features (Rage, Second Wind, Sneak Attack, ...).
    #
    # `features` above is a list of NAMES and nothing ever read it -- a grep for
    # class_features across components/agents/core returned zero production hits,
    # so a Barbarian and a Wizard of the same level fought identically. That list
    # stays (saves and prompts already carry it); what was missing is the
    # RESOURCE: how many rages are left, whether Second Wind has been spent.
    #
    # Keyed by feature id -> uses spent since the last recovery. Spent rather than
    # remaining because the MAXIMUM scales with level (a 6th-level barbarian has
    # four rages, not two), so storing "remaining" would silently cap a character
    # at whatever their maximum was when the field was written.
    class_feature_uses: Dict[str, int] = None

    # Progression and survival (plan 2.5). All of this was entirely absent:
    # grep for award_xp / def level_up / def long_rest returned zero hits, so
    # characters were permanently level 1 and hp<=0 meant instantly out.
    experience_points: int = 0
    hit_dice_remaining: Optional[int] = None  # None = full (level); spent on short rests
    death_save_successes: int = 0
    death_save_failures: int = 0
    is_stable: bool = False   # Stabilised at 0 HP, no longer rolling death saves
    is_dead: bool = False     # 3 failed death saves (or massive damage)

    # Monster stat-block mechanics (plan 0, audit row: resistance/senses)
    # These fields are surfaced from SRD monster data and applied by the
    # dnd_engine wrapper so resistance/immunity/vulnerability actually affect damage.
    damage_resistances: List[str] = None
    damage_vulnerabilities: List[str] = None
    damage_immunities: List[str] = None
    senses: Dict[str, str] = None  # e.g., {"darkvision": "60 ft."}

    # ------------------------------------------------------------------
    # Serialization (Plan 0.3)
    #
    # Saves previously went through get_character_summary(), which is an
    # ANALYTICS view: it drops hit_points, equipment, armor_class, spell_slots
    # and every Roshar field, and collapses skills to a count. Loading such a
    # save resurrected the character at 0 HP with class "Unknown".
    # These two methods are the real round-trip contract.
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Full lossless serialization of this character."""
        data = asdict(self)
        # JSON object keys must be strings; spell_slots is keyed by int level.
        if data.get("spell_slots"):
            data["spell_slots"] = {str(k): v for k, v in data["spell_slots"].items()}
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CharacterData":
        """Rebuild a character from to_dict() output, tolerating schema drift."""
        known = {f.name for f in fields(cls)}
        payload = {k: v for k, v in data.items() if k in known}

        # Restore int keys on spell_slots (JSON stringifies them).
        slots = payload.get("spell_slots")
        if isinstance(slots, dict):
            payload["spell_slots"] = {
                int(k): v for k, v in slots.items() if str(k).lstrip("-").isdigit()
            }

        # Required (non-default) fields must be present; supply safe empties so a
        # partial/legacy save degrades instead of raising.
        defaults = {
            "character_id": data.get("name", "unknown"),
            "name": "Unknown",
            "level": 1,
            "proficiency_bonus": 2,
            "ability_scores": {},
            "ability_modifiers": {},
            "skills": {},
            "expertise_skills": [],
            "conditions": [],
            "features": [],
            "hit_points": {"current": 0, "maximum": 0, "temporary": 0},
            "armor_class": 10,
            "saving_throw_proficiencies": [],
            "character_class": "Unknown",
            "race": "Unknown",
            "background": "Unknown",
        }
        for key, fallback in defaults.items():
            payload.setdefault(key, fallback)

        return cls(**payload)

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
        # Deep-copy first: the nested dicts and lists (hit_points, ability_scores,
        # equipment, conditions, ...) were previously stored BY REFERENCE, so two
        # engines built from one character template shared live state — damaging a
        # character in one mutated the other, and a caller that reused its own
        # template dict saw the game write back into it. Found via a test where
        # `add_character(dict(TEMPLATE))` on two GameEngines produced distinct
        # CharacterData objects that shared a single hit_points dict.
        character_data = copy.deepcopy(character_data)

        char_id = character_data.get("character_id", character_data.get("name", "unknown"))

        # Calculate ability modifiers
        ability_scores = character_data.get("ability_scores", {})
        ability_modifiers = {}
        for ability, score in ability_scores.items():
            ability_modifiers[ability] = self._calculate_ability_modifier(score)

        # Calculate proficiency bonus from level
        level = character_data.get("level", 1)
        proficiency_bonus = self._calculate_proficiency_bonus(level)

        # Normalize hit_points format (support both dict and simple int)
        hp_data = character_data.get("hit_points", {"current": 0, "maximum": 0, "temporary": 0})
        if isinstance(hp_data, int):
            # Convert simple int to dict format
            hp_data = {"current": hp_data, "maximum": hp_data, "temporary": 0}
        elif isinstance(hp_data, dict):
            # Ensure all required keys exist
            hp_data.setdefault("temporary", 0)

            # `current` must never exceed `maximum` — 5e has no way for it to,
            # short of temporary HP, which is a SEPARATE field.
            #
            # A live run reported `Aggi's current HP (13) is higher than max (8)`
            # in the DM's own gm_notes, from a stale save whose HP keys did not
            # match the authored sheet. The DM noticed and worked around it, which
            # is worse than a crash: the contradiction reached the prompt and the
            # model had to guess which number to believe.
            current = hp_data.get("current")
            maximum = hp_data.get("maximum")
            if isinstance(current, int) and isinstance(maximum, int):
                if maximum <= 0 and current > 0:
                    # A maximum of 0 with positive current means `maximum` was
                    # never populated; trust `current` rather than killing them.
                    logger.warning(
                        f"⚠️ {char_id}: hit_points maximum is {maximum} with "
                        f"current {current}; setting maximum to {current}")
                    hp_data["maximum"] = current
                elif current > maximum:
                    logger.warning(
                        f"⚠️ {char_id}: hit_points current ({current}) exceeds "
                        f"maximum ({maximum}); clamping to maximum")
                    hp_data["current"] = maximum
                elif current < 0:
                    hp_data["current"] = 0

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
            hit_points=hp_data,
            armor_class=character_data.get("armor_class", 10),
            saving_throw_proficiencies=character_data.get("saving_throw_proficiencies", []),
            character_class=character_data.get("character_class", "Unknown"),
            race=character_data.get("race", "Unknown"),
            background=character_data.get("background", "Unknown"),
            spell_slots=character_data.get("spell_slots", {}),

            # Roshar + general state (UPDATED 2026-01-03 for Combat Plan v4.0)
            rulebook=character_data.get("rulebook", "Cosmere 5e (Roshar)"),
            identity=character_data.get("identity", character_data.get("race", "Unknown")),
            radiant_order=character_data.get("radiant_order"),
            ideal_level=character_data.get("ideal_level", 0),

            # Stormlight tracking (Combat Plan v4.0)
            stormlight_current=character_data.get("stormlight_current", 0),
            stormlight_capacity=character_data.get("stormlight_capacity", 0),

            # Shardblade tracking (Combat Plan v4.0)
            has_shardblade=character_data.get("has_shardblade", False),
            shardblade_summoned=character_data.get("shardblade_summoned", False),
            shardblade_type=character_data.get("shardblade_type"),
            shardblade_name=character_data.get("shardblade_name"),

            # Shardplate tracking (Combat Plan v4.0)
            has_shardplate=character_data.get("has_shardplate", False),
            shardplate_hp_current=character_data.get("shardplate_hp_current", 0),
            shardplate_hp_maximum=character_data.get("shardplate_hp_maximum", 0),
            shardplate_type=character_data.get("shardplate_type"),

            # Surgebinding progression (Combat Plan v4.0)
            surgebinding_level=character_data.get("surgebinding_level", character_data.get("ideal_level", 0)),

            # Plan 2.16: progression/survival fields must be read here too, or
            # they are silently dropped on load — XP reset to 0 and hit dice to
            # None, so a restored party lost all its earned progress.
            experience_points=character_data.get("experience_points", 0),
            hit_dice_remaining=character_data.get("hit_dice_remaining"),
            death_save_successes=character_data.get("death_save_successes", 0),
            death_save_failures=character_data.get("death_save_failures", 0),
            is_stable=character_data.get("is_stable", False),
            is_dead=character_data.get("is_dead", False),

            # Legacy field - kept for backward compatibility
            investiture_points=character_data.get("investiture_points", {"current": 0, "maximum": 0}),

            spren=character_data.get("spren", {"type": None, "name": None, "status": "dormant"}),
            surges_known=character_data.get("surges_known", []),
            cantrips_known=character_data.get("cantrips_known", []),
            spells_known=character_data.get("spells_known", []),
            languages=character_data.get("languages", []),
            equipment=character_data.get("equipment", []),
            currency=character_data.get("currency", {"gp": 0, "sp": 0, "cp": 0, "pp": 0, "ep": 0}),
            personality=character_data.get("personality", {"traits": [], "ideals": [], "bonds": [], "flaws": []}),
            backstory=character_data.get("backstory", ""),
            speed=character_data.get("speed", 30),
            tool_proficiencies=character_data.get("tool_proficiencies", []),
            armor_proficiencies=character_data.get("armor_proficiencies", []),
            weapon_proficiencies=character_data.get("weapon_proficiencies", []),

            # Initialize action tracking
            action_history=character_data.get("action_history", []),

            # Class-feature use counters, restored from a save when present.
            class_feature_uses=character_data.get("class_feature_uses") or {},

            # Monster stat-block mechanics (plan 0)
            damage_resistances=character_data.get("damage_resistances", []),
            damage_vulnerabilities=character_data.get("damage_vulnerabilities", []),
            damage_immunities=character_data.get("damage_immunities", []),
            senses=character_data.get("senses", {}),
        )

        # Auto-migrate investiture_points to stormlight if needed (backward compatibility)
        if character.investiture_points and character.stormlight_capacity == 0:
            character.stormlight_current = character.investiture_points.get("current", 0)
            character.stormlight_capacity = character.investiture_points.get("maximum", 0)
            logger.debug(f"   Migrated investiture_points to stormlight for {character.name}")

        # Calculate stormlight capacity from level if Radiant and not set
        if character.radiant_order and character.stormlight_capacity == 0:
            character.stormlight_capacity = level * 2
            character.stormlight_current = min(character.stormlight_current, character.stormlight_capacity)
            logger.debug(f"   Calculated stormlight capacity for {character.name}: {character.stormlight_capacity}")

        # Set surgebinding_level from ideal_level if not explicitly set
        if character.surgebinding_level == 0 and character.ideal_level > 0:
            character.surgebinding_level = character.ideal_level
            logger.debug(f"   Set surgebinding_level from ideal_level for {character.name}: {character.surgebinding_level}")

        # Calculate Shardplate HP if has_shardplate but HP not set
        if character.has_shardplate and character.shardplate_hp_maximum == 0:
            character.shardplate_hp_maximum = level * 5
            character.shardplate_hp_current = character.shardplate_hp_maximum
            logger.debug(f"   Calculated Shardplate HP for {character.name}: {character.shardplate_hp_maximum}")

        # Populate saving throw proficiencies from class if empty
        if not character.saving_throw_proficiencies and character.character_class != "Unknown":
            character.saving_throw_proficiencies = self._saving_throw_proficiencies_for_class(
                character.character_class)
            logger.debug(f"   Set saving throw proficiencies for {character.name}: "
                        f"{character.saving_throw_proficiencies}")

        self.characters[char_id] = character

        # Grant the class features this class and level entitles them to. Nothing
        # did this: `core/game_initialization.py` authors
        # `"features": ["Fighting Style", "Second Wind"]` on the shipped Fighter,
        # and that list was written and never read, so no character had a usable
        # feature. Granting here means every character built through the ONE
        # entry point the game uses gets them.
        self.grant_class_features(char_id)

        logger.info(f"👤 Added character: {character.name} (Level {level})")

        return char_id

    def add_npc(self, npc_data: Dict[str, Any]) -> str:
        """
        Add NPC with full D&D stats to CharacterManager.

        Supports both "class" and "character_class" field names for backward compatibility.
        NPC-specific data (attacks, special_abilities, challenge_rating) are stored as
        attributes on the CharacterData object.

        Args:
            npc_data: Dict with D&D stats from NPCStatGenerator or templates
                Required: name, ability_scores, hit_points (dict format)
                Optional: level, character_class (or class), race, background, etc.

        Returns:
            char_id: Unique ID for NPC (e.g., "goblin_001")
        """
        # Create a copy to avoid modifying input
        npc_data_copy = npc_data.copy()

        # Generate unique ID if not provided
        if "character_id" not in npc_data_copy:
            base_name = npc_data_copy['name'].lower().replace(' ', '_')
            # Find next available ID
            counter = 1
            char_id = f"{base_name}_{counter:03d}"
            while char_id in self.characters:
                counter += 1
                char_id = f"{base_name}_{counter:03d}"
            npc_data_copy["character_id"] = char_id

        # Support both "class" and "character_class" field names
        if "class" in npc_data_copy and "character_class" not in npc_data_copy:
            npc_data_copy["character_class"] = npc_data_copy["class"]

        # Ensure hit_points is in dict format
        if isinstance(npc_data_copy.get("hit_points"), dict):
            # Ensure temporary key exists
            if "temporary" not in npc_data_copy["hit_points"]:
                npc_data_copy["hit_points"]["temporary"] = 0

        # Use add_character to create the base CharacterData
        char_id = self.add_character(npc_data_copy)

        # Store NPC-specific data as attributes
        character = self.characters[char_id]
        character.attacks = npc_data.get("attacks", [])
        character.special_abilities = npc_data.get("special_abilities", [])
        character.challenge_rating = npc_data.get("challenge_rating", 0.5)
        # MULTIATTACK (components/combat/multiattack.py). Without this the combat
        # layer has no way to know a monster's stat block grants more than one
        # attack, and every monster swings once regardless of its CR. Defaults to
        # the 5e baseline of one.
        character.attacks_per_turn = npc_data.get("attacks_per_turn", 1)
        character.multiattack = npc_data.get("multiattack")

        logger.info(f"🧟 Added NPC: {character.name} (CR {character.challenge_rating})")

        return char_id

    def remove_npc(self, char_id: str) -> bool:
        """
        Remove NPC from CharacterManager (e.g., when combat ends).

        Args:
            char_id: Character ID to remove

        Returns:
            True if removed, False if not found
        """
        if char_id in self.characters:
            npc_name = self.characters[char_id].name
            del self.characters[char_id]
            logger.info(f"🗑️ Removed NPC: {char_id} ({npc_name})")
            return True
        return False

    def get_npcs(self) -> List[str]:
        """
        Return list of NPC char_ids (for cleanup after combat).

        NPCs have numeric suffixes like "_001", "_002" from add_npc().
        """
        import re
        npc_pattern = re.compile(r'.*_\d{3}$')
        return [cid for cid in self.characters.keys() if npc_pattern.match(cid)]
    
    def resolve_character_id(self, identifier: str) -> Optional[str]:
        """
        Map a loose identifier onto a real character id.

        The DM tools are driven by an LLM, so the "actor" it supplies is whatever
        the narration used: "aggi", "Aggi", "Aggi the Lightweaver". An exact dict
        lookup missed all but the stored spelling, and the resulting unknown-actor
        path then raised KeyError: 'breakdown' — four skill checks were lost to
        this in one live playtest.

        Returns the canonical id, or None if nothing matches confidently.
        """
        if not identifier or not isinstance(identifier, str):
            return None

        needle = identifier.strip()
        if needle in self.characters:
            return needle

        lowered = needle.lower()

        # Case-insensitive id match.
        for char_id in self.characters:
            if char_id.lower() == lowered:
                return char_id

        # Exact name match.
        for char_id, character in self.characters.items():
            if (getattr(character, "name", "") or "").lower() == lowered:
                return char_id

        # The id or name appears as a whole word in the identifier
        # ("Aggi the Lightweaver" -> "Aggi"). Whole words only: a substring test
        # matches "A" inside almost anything.
        words = set(lowered.replace(",", " ").replace(".", " ").split())
        for char_id, character in self.characters.items():
            candidates = {char_id.lower(),
                          (getattr(character, "name", "") or "").lower()}
            for candidate in candidates:
                if candidate and candidate in words:
                    return char_id

        return None

    def get_skill_data(self, character_id: str, skill: str) -> Dict[str, Any]:
        """
        Get complete skill data for character - Step 2 of 7-step pipeline
        From Original Plan: "Character Manager → skill/ability mod, conditions"
        """
        if character_id not in self.characters:
            # Resolve by name or case-insensitive id before giving up: the DM
            # tools are driven by an LLM, which says "aggi" or "Aggi" for the
            # character stored as "Aggi". A live playtest lost four skill checks
            # to this.
            resolved = self.resolve_character_id(character_id)
            if resolved:
                character_id = resolved

        if character_id not in self.characters:
            # Return default data for unknown characters.
            # NOTE: "breakdown" MUST be present. game_engine's 7-step pipeline
            # reads char_data["breakdown"] by direct subscript, so omitting it
            # here raised KeyError: 'breakdown' and killed the whole skill check
            # instead of degrading to a modifier of 0.
            return {
                "character_id": character_id,
                "skill": skill,
                "ability_modifier": 0,
                "proficiency_bonus": 0,
                "is_proficient": False,
                "expertise": False,
                "other_bonuses": {},
                "modifier": 0,
                "breakdown": {"unknown_character": 0},
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
            logger.info(f"➕ Added condition '{condition}' to {character.name}")
        elif not add and condition in character.conditions:
            character.conditions.remove(condition)
            logger.info(f"➖ Removed condition '{condition}' from {character.name}")
        
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
    
    # ------------------------------------------------------------------
    # Progression: XP and levelling (plan 2.5)
    #
    # None of this existed: characters were permanently level 1 with their
    # starting HP, so the 1-10 progression that is Shards of Honor's spine
    # (D6) was impossible.
    # ------------------------------------------------------------------

    # D&D 5e XP thresholds, index = level - 1.
    XP_THRESHOLDS = [
        0, 300, 900, 2700, 6500, 14000, 23000, 34000, 48000, 64000,
        85000, 100000, 120000, 140000, 165000, 195000, 225000, 265000,
        305000, 355000,
    ]
    MAX_LEVEL = 20

    def level_for_xp(self, xp: int) -> int:
        """The level a given XP total corresponds to (plan 2.5)."""
        level = 1
        for i, threshold in enumerate(self.XP_THRESHOLDS, start=1):
            if xp >= threshold:
                level = i
            else:
                break
        return min(level, self.MAX_LEVEL)

    def award_xp(self, character_id: str, amount: int) -> Dict[str, Any]:
        """
        Award XP and level up if a threshold is crossed (plan 2.5).

        Returns {"xp", "level", "levels_gained", "leveled_up"}.
        """
        character = self.characters.get(character_id)
        if character is None:
            logger.warning(f"⚠️ Cannot award XP: unknown character {character_id}")
            return {"error": f"Unknown character {character_id}"}

        amount = max(0, int(amount or 0))
        before_level = character.level
        character.experience_points = (character.experience_points or 0) + amount

        new_level = self.level_for_xp(character.experience_points)
        levels_gained = 0
        while character.level < new_level:
            self._apply_level_up(character)
            levels_gained += 1

        logger.info(
            f"✨ {character.name} gained {amount} XP "
            f"(total {character.experience_points})"
            + (f" — LEVEL UP to {character.level}!" if levels_gained else "")
        )
        return {
            "xp": character.experience_points,
            "level": character.level,
            "levels_gained": levels_gained,
            "leveled_up": levels_gained > 0,
            "previous_level": before_level,
        }

    def _apply_level_up(self, character: "CharacterData") -> None:
        """
        Advance one level: HP, proficiency, hit dice, Stormlight capacity, ASI, Extra Attack.
        """
        character.level += 1

        con_mod = character.ability_modifiers.get("constitution", 0)
        hit_die = self._hit_die_for_class(character.character_class)
        # Average HP per level (the 5e "take the average" option), min 1.
        hp_gain = max(1, hit_die // 2 + 1 + con_mod)

        character.hit_points["maximum"] = character.hit_points.get("maximum", 0) + hp_gain
        character.hit_points["current"] = min(
            character.hit_points["maximum"],
            character.hit_points.get("current", 0) + hp_gain)
        character.proficiency_bonus = self._calculate_proficiency_bonus(character.level)
        character.hit_dice_remaining = character.level

        # Roshar: capacity is Radiant level x 2
        if getattr(character, "radiant_order", None):
            character.stormlight_capacity = character.level * 2

        # Ability Score Improvement at levels 4, 8, 12, 16, 19 (standard 5e).
        # Fighters get an extra ASI at 6 and 14, Rogues at 10 (not implemented yet,
        # treating all classes uniformly for now per audit requirement).
        # Rule: +2 to primary ability (highest score), or +1/+1 to top two if tied.
        if character.level in {4, 8, 12, 16, 19}:
            self._apply_asi(character)

        # Extra Attack: grant at class-appropriate levels
        self._grant_extra_attack_if_eligible(character)

        # New level, new class features. A Fighter reaching 2nd gains Action
        # Surge; without this the feature table is consulted only at character
        # creation, so a party that levelled during play never gained anything.
        self.grant_class_features(character.character_id)

        logger.info(
            f"   ⬆️  {character.name} -> level {character.level} "
            f"(+{hp_gain} HP, proficiency +{character.proficiency_bonus})"
        )

    def _apply_asi(self, character: "CharacterData") -> None:
        """
        Apply Ability Score Improvement (ASI).

        Deterministic rule to avoid choice paralysis in a text game:
        - Find the highest ability score(s)
        - If one clear winner: +2 to that ability
        - If tied for highest: +1 to each of the top two

        Recalculate modifiers after applying.
        """
        if not character.ability_scores:
            return

        # Find the highest score(s)
        sorted_abilities = sorted(
            character.ability_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        if not sorted_abilities:
            return

        top_ability, top_score = sorted_abilities[0]
        # Check if there's a tie for highest
        tied_abilities = [name for name, score in sorted_abilities if score == top_score]

        if len(tied_abilities) == 1:
            # Clear winner: +2 to highest
            old_value = character.ability_scores[top_ability]
            character.ability_scores[top_ability] = min(20, character.ability_scores[top_ability] + 2)
            new_value = character.ability_scores[top_ability]
            logger.info(f"   📈 ASI: {character.name} {top_ability} +2 "
                       f"({old_value} → {new_value})")
        else:
            # Tie: +1 to top two
            first = tied_abilities[0]
            second = tied_abilities[1] if len(tied_abilities) > 1 else tied_abilities[0]
            old_first = character.ability_scores[first]
            old_second = character.ability_scores[second]
            character.ability_scores[first] = min(20, character.ability_scores[first] + 1)
            character.ability_scores[second] = min(20, character.ability_scores[second] + 1)
            logger.info(f"   📈 ASI: {character.name} {first} +1, {second} +1 "
                       f"({old_first} → {character.ability_scores[first]}, "
                       f"{old_second} → {character.ability_scores[second]})")

        # Recalculate modifiers
        for ability, score in character.ability_scores.items():
            character.ability_modifiers[ability] = self._calculate_ability_modifier(score)

    def _grant_extra_attack_if_eligible(self, character: "CharacterData") -> None:
        """
        Grant Extra Attack at class-appropriate levels.

        Sets the `attacks_per_turn` attribute that `components/combat/multiattack.py`
        reads via `attacks_per_turn_for()`.

        5e progression:
        - Fighter: 2 attacks at 5, 3 at 11, 4 at 20
        - Barbarian, Paladin, Ranger: 2 attacks at 5
        - Monk: 1 attack (but can use bonus action for unarmed strikes)
        - Others: 1 attack

        Roshar Radiants follow their closest 5e equivalent.
        """
        class_name = (character.character_class or "").strip().lower()
        level = character.level

        # Define extra attack progression by class
        extra_attack_table = {
            # Standard 5e classes
            "fighter": {5: 2, 11: 3, 20: 4},
            "barbarian": {5: 2},
            "paladin": {5: 2},
            "ranger": {5: 2},
            "monk": {5: 2},  # Technically bonus action, but treat as extra attack
            # Roshar classes (mapped to 5e equivalents)
            "herald": {5: 2},  # Like Barbarian
            "windrunner": {5: 2},  # Like Fighter/Ranger
            "skybreaker": {5: 2},  # Like Paladin
            "stoneward": {5: 2, 11: 3, 20: 4},  # Like Fighter
            "dustbringer": {5: 2},  # Combat-focused
        }

        if class_name in extra_attack_table:
            progression = extra_attack_table[class_name]
            if level in progression:
                new_attacks = progression[level]
                # Set the attribute that multiattack.py reads
                character.attacks_per_turn = new_attacks
                logger.info(f"   ⚔️  {character.name} gains Extra Attack: "
                           f"{new_attacks} attacks per turn")
        else:
            # Classes without extra attack default to 1
            if not hasattr(character, "attacks_per_turn"):
                character.attacks_per_turn = 1

    # ------------------------------------------------------------------
    # Class features
    #
    # CharacterManager is the authority for character data, so the feature
    # RESOURCE (how many rages are left) lives here and combat reads it. See
    # components/combat/class_features.py for the table and the engine-side
    # effects; this half is only bookkeeping the sheet owns.
    # ------------------------------------------------------------------

    def grant_class_features(self, character_id: str) -> List[str]:
        """
        Add the features this character's class and level entitle them to.

        Names are appended to `features` (the list saves and prompts already
        carry) and a use counter is seeded. Idempotent, because it runs both at
        creation and on every level-up.

        Returns the feature names newly granted.
        """
        character = self.characters.get(character_id)
        if character is None:
            return []

        try:
            from components.combat.class_features import get_feature_table
            table = get_feature_table()
        except Exception as e:
            logger.debug(f"   Class-feature table unavailable: {e}")
            return []

        if character.features is None:
            character.features = []
        if character.class_feature_uses is None:
            character.class_feature_uses = {}

        existing = {str(f).strip().lower() for f in character.features}
        granted = []
        for entry in table.for_character(character.character_class,
                                        character.level):
            character.class_feature_uses.setdefault(entry["id"], 0)
            if entry["name"].strip().lower() in existing:
                continue
            character.features.append(entry["name"])
            granted.append(entry["name"])

        if granted:
            logger.info(f"   🎖️  {character.name} gains: {', '.join(granted)}")
        return granted

    def class_feature_status(self, character_id: str) -> Dict[str, Any]:
        """
        Every class feature this character has, with uses remaining.

        This is what a UI or the DM prompt should read: the point of the whole
        subsystem is that "Rage (2/3 left)" is visible somewhere.
        """
        character = self.characters.get(character_id)
        if character is None:
            return {}
        try:
            from components.combat.class_features import (get_feature_table,
                                                          max_uses)
        except Exception:
            return {}

        out = {}
        for entry in get_feature_table().for_character(
                character.character_class, character.level):
            maximum = max_uses(entry, character)
            spent = int((character.class_feature_uses or {}).get(entry["id"], 0))
            out[entry["id"]] = {
                "name": entry["name"],
                "activation": entry.get("activation"),
                "uses_remaining": -1 if maximum < 0 else max(0, maximum - spent),
                "uses_maximum": maximum,
            }
        return out

    def recharge_class_features(self, character_id: str,
                                long_rest: bool = False) -> List[str]:
        """
        Reset the use counters whose `recovery` this rest satisfies.

        A long rest also recovers everything a short rest would — 5e says so, and
        forgetting it is why "once per short rest" features are usually the ones
        that end up permanently spent.

        Returns the feature ids recharged.
        """
        character = self.characters.get(character_id)
        if character is None or not character.class_feature_uses:
            return []
        try:
            from components.combat.class_features import get_feature_table
            table = get_feature_table()
        except Exception:
            return []

        satisfied = {"short_rest", "long_rest"} if long_rest else {"short_rest"}
        recharged = []
        for feature_id, spent in list(character.class_feature_uses.items()):
            entry = table.get(feature_id)
            if entry is None or not spent:
                continue
            if str(entry.get("recovery")) in satisfied:
                character.class_feature_uses[feature_id] = 0
                recharged.append(feature_id)

        if recharged:
            logger.info(f"   🎖️  {character.name} recovers: {', '.join(recharged)}")
        return recharged

    @staticmethod
    def _hit_die_for_class(character_class: str) -> int:
        """Hit die by class; mirrors DnDEngineWrapper._HIT_DIE_BY_CLASS."""
        table = {
            "barbarian": 12, "herald": 12,
            "fighter": 10, "paladin": 10, "ranger": 10, "radiant": 10,
            "windrunner": 10, "skybreaker": 10, "stoneward": 10,
            "dustbringer": 10, "bondsmith": 10,
            "bard": 8, "cleric": 8, "druid": 8, "monk": 8, "rogue": 8,
            "warlock": 8, "edgedancer": 8, "truthwatcher": 8, "willshaper": 8,
            "sorcerer": 6, "wizard": 6, "lightweaver": 6, "elsecaller": 6,
        }
        return table.get((character_class or "").strip().lower(), 8)

    @staticmethod
    def _saving_throw_proficiencies_for_class(character_class: str) -> List[str]:
        """
        Saving throw proficiencies by class per 5e PHB.
        Each class gets exactly two.
        """
        table = {
            "barbarian": ["strength", "constitution"],
            "bard": ["dexterity", "charisma"],
            "cleric": ["wisdom", "charisma"],
            "druid": ["intelligence", "wisdom"],
            "fighter": ["strength", "constitution"],
            "monk": ["strength", "dexterity"],
            "paladin": ["wisdom", "charisma"],
            "ranger": ["strength", "dexterity"],
            "rogue": ["dexterity", "intelligence"],
            "sorcerer": ["constitution", "charisma"],
            "warlock": ["wisdom", "charisma"],
            "wizard": ["intelligence", "wisdom"],
            # Roshar/Cosmere classes (mapped to nearest 5e equivalents)
            "herald": ["strength", "constitution"],  # Like Barbarian
            "radiant": ["wisdom", "charisma"],  # Like Paladin
            "windrunner": ["strength", "dexterity"],  # Like Ranger
            "skybreaker": ["wisdom", "charisma"],  # Like Paladin
            "stoneward": ["strength", "constitution"],  # Like Fighter
            "dustbringer": ["constitution", "charisma"],  # Like Sorcerer
            "bondsmith": ["wisdom", "charisma"],  # Like Cleric
            "edgedancer": ["dexterity", "wisdom"],  # Like Monk/Druid
            "truthwatcher": ["intelligence", "wisdom"],  # Like Druid
            "willshaper": ["dexterity", "wisdom"],  # Like Ranger
            "lightweaver": ["intelligence", "charisma"],  # Like Bard/Rogue
            "elsecaller": ["intelligence", "wisdom"],  # Like Wizard
        }
        class_key = (character_class or "").strip().lower()
        return table.get(class_key, ["strength", "dexterity"])  # Default fallback

    def xp_to_next_level(self, character_id: str) -> Optional[int]:
        """XP still needed for the next level, or None at max level."""
        character = self.characters.get(character_id)
        if character is None or character.level >= self.MAX_LEVEL:
            return None
        return max(0, self.XP_THRESHOLDS[character.level] - (character.experience_points or 0))

    # ------------------------------------------------------------------
    # Rests (plan 2.5)
    # ------------------------------------------------------------------

    def short_rest(self, character_id: str, hit_dice_to_spend: int = 1) -> Dict[str, Any]:
        """
        Take a short rest: spend hit dice to heal (plan 2.5).

        5e: roll hit dice + CON per die. Uses the average so results are
        predictable for a text game.
        """
        character = self.characters.get(character_id)
        if character is None:
            return {"error": f"Unknown character {character_id}"}

        if character.hit_dice_remaining is None:
            character.hit_dice_remaining = character.level

        spend = max(0, min(int(hit_dice_to_spend or 0), character.hit_dice_remaining))
        hit_die = self._hit_die_for_class(character.character_class)
        con_mod = character.ability_modifiers.get("constitution", 0)

        healed = 0
        maximum = character.hit_points.get("maximum", 0)
        for _ in range(spend):
            healed += max(1, hit_die // 2 + 1 + con_mod)
        character.hit_dice_remaining -= spend

        before = character.hit_points.get("current", 0)
        character.hit_points["current"] = min(maximum, before + healed)
        actually_healed = character.hit_points["current"] - before

        # A short rest also clears death-save progress once you are conscious.
        if character.hit_points["current"] > 0:
            self._reset_death_saves(character)

        # Second Wind and Action Surge come back on a short rest. Without this a
        # Fighter gets exactly one Second Wind per campaign, which is how a
        # "once per rest" feature becomes "once, ever".
        recharged = self.recharge_class_features(character_id, long_rest=False)

        logger.info(
            f"🏕️  {character.name} short rest: spent {spend} hit dice, "
            f"healed {actually_healed} ({character.hit_points['current']}/{maximum})"
        )
        return {
            "healed": actually_healed,
            "hit_dice_spent": spend,
            "hit_dice_remaining": character.hit_dice_remaining,
            "hit_points": dict(character.hit_points),
            "class_features_recharged": recharged,
        }

    def long_rest(self, character_id: str) -> Dict[str, Any]:
        """
        Take a long rest: full HP, half hit dice back, spell slots and
        Stormlight restored, death saves cleared (plan 2.5).
        """
        character = self.characters.get(character_id)
        if character is None:
            return {"error": f"Unknown character {character_id}"}

        maximum = character.hit_points.get("maximum", 0)
        before = character.hit_points.get("current", 0)
        character.hit_points["current"] = maximum
        character.hit_points["temporary"] = 0

        # 5e: regain half your total hit dice (minimum 1)
        if character.hit_dice_remaining is None:
            character.hit_dice_remaining = character.level
        regained = max(1, character.level // 2)
        character.hit_dice_remaining = min(character.level,
                                           character.hit_dice_remaining + regained)

        # Spell slots back to full
        for level_slots in (character.spell_slots or {}).values():
            if isinstance(level_slots, dict) and "maximum" in level_slots:
                level_slots["current"] = level_slots["maximum"]

        # Roshar: a night with spheres refills Stormlight
        if getattr(character, "stormlight_capacity", 0):
            character.stormlight_current = character.stormlight_capacity

        self._reset_death_saves(character)

        # Every class feature recovers on a long rest, including the ones a short
        # rest would already have restored (Rage is long-rest only; Second Wind is
        # short-rest and must come back here too).
        recharged = self.recharge_class_features(character_id, long_rest=True)

        # 5e PHB: a long rest reduces exhaustion by 1 level
        # Exhaustion is tracked as "Exhaustion" in conditions with level managed
        # by engine_conditions.py. The condition string format is case-insensitive
        # and the level is tracked separately by that system.
        exhaustion_reduced = False
        if character.conditions:
            # Check if any condition contains "exhaustion" (case-insensitive)
            for i, condition in enumerate(character.conditions):
                if "exhaustion" in str(condition).lower():
                    # The actual exhaustion level manipulation is handled by
                    # engine_conditions.py when it applies/removes the condition.
                    # For now, we just note that the character has exhaustion
                    # and the game engine should reduce it.
                    exhaustion_reduced = True
                    logger.info(f"   😌 {character.name}'s exhaustion reduced by long rest")
                    break

        logger.info(
            f"🌙 {character.name} long rest: HP {before} -> {maximum}, "
            f"hit dice {character.hit_dice_remaining}/{character.level}"
        )
        return {
            "hit_points": dict(character.hit_points),
            "hit_dice_remaining": character.hit_dice_remaining,
            "stormlight_current": getattr(character, "stormlight_current", 0),
            "class_features_recharged": recharged,
        }

    def rest_party(self, long: bool = True) -> Dict[str, Any]:
        """Rest every character (D3: rests are a party-wide activity)."""
        results = {}
        for char_id in list(self.characters):
            results[char_id] = (self.long_rest(char_id) if long
                                else self.short_rest(char_id))
        return results

    # ------------------------------------------------------------------
    # Death saves (plan 2.5)
    #
    # PolicyEngine declares a death_saves policy and NOTHING consumed it;
    # combat treated hp<=0 as instantly out, so dropping was the same as dying.
    # ------------------------------------------------------------------

    @staticmethod
    def _reset_death_saves(character: "CharacterData") -> None:
        character.death_save_successes = 0
        character.death_save_failures = 0
        character.is_stable = False

    def roll_death_save(self, character_id: str,
                        roll: Optional[int] = None) -> Dict[str, Any]:
        """
        Roll one death saving throw (plan 2.5).

        5e: DC 10. Three successes stabilise; three failures kill. A natural 20
        restores 1 HP; a natural 1 counts as two failures.
        """
        character = self.characters.get(character_id)
        if character is None:
            return {"error": f"Unknown character {character_id}"}

        if character.hit_points.get("current", 0) > 0:
            return {"skipped": "character is conscious"}
        if character.is_dead:
            return {"dead": True, "reason": "already dead"}
        if character.is_stable:
            return {"stable": True, "reason": "already stabilised"}

        if roll is None:
            from .dice import DiceRoller
            roll = DiceRoller().roll_die(20).result

        result = {"roll": roll, "dead": False, "stable": False, "revived": False}

        if roll == 20:
            character.hit_points["current"] = 1
            self._reset_death_saves(character)
            result["revived"] = True
            logger.info(f"✨ {character.name} rolled a natural 20 and revives at 1 HP!")
            return result

        if roll == 1:
            character.death_save_failures += 2
            logger.warning(f"💀 {character.name} rolled a natural 1 — two failures")
        elif roll >= 10:
            character.death_save_successes += 1
            logger.info(f"🩹 {character.name} succeeds a death save "
                        f"({character.death_save_successes}/3)")
        else:
            character.death_save_failures += 1
            logger.warning(f"💔 {character.name} fails a death save "
                           f"({character.death_save_failures}/3)")

        if character.death_save_failures >= 3:
            character.is_dead = True
            result["dead"] = True
            logger.warning(f"☠️  {character.name} has died")
        elif character.death_save_successes >= 3:
            character.is_stable = True
            result["stable"] = True
            logger.info(f"🛡️  {character.name} is stable")

        result["successes"] = character.death_save_successes
        result["failures"] = character.death_save_failures
        return result

    def stabilize(self, character_id: str) -> bool:
        """Stabilise a dying character, e.g. a successful Medicine check."""
        character = self.characters.get(character_id)
        if character is None or character.is_dead:
            return False
        self._reset_death_saves(character)
        character.is_stable = True
        logger.info(f"🛡️  {character.name} has been stabilised")
        return True

    @staticmethod
    def enforce_hp_invariant(character) -> bool:
        """
        Hold `0 <= current <= maximum`. Returns True if anything was corrected.

        `add_character()` enforces this on LOAD, which was not enough: HP is mutated
        in a dozen places, and a live run reached combat with `current 13 / maximum
        8` — the DM noticed the contradiction and wrote about it in its own notes.
        An inconsistency that reaches the prompt makes the model guess which number
        to believe.

        Call this after any bulk HP mutation. Cheap, idempotent, and the only place
        the rule is expressed.
        """
        hp = getattr(character, "hit_points", None)
        if not isinstance(hp, dict):
            return False

        current, maximum = hp.get("current"), hp.get("maximum")
        if not (isinstance(current, int) and isinstance(maximum, int)):
            return False

        if maximum <= 0 and current > 0:
            # `maximum` was never populated; trust current rather than killing them.
            hp["maximum"] = current
            return True
        if current > maximum:
            logger.warning(
                f"⚠️ {getattr(character, 'name', '?')}: HP current ({current}) "
                f"exceeded maximum ({maximum}); clamped")
            hp["current"] = maximum
            return True
        if current < 0:
            hp["current"] = 0
            return True
        return False

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
        
        logger.info(f"🌟 Updated {character.name}'s investiture: {character.investiture_points}")
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
            logger.info(f"⚡ {character.name} spent {amount} investiture ({character.investiture_points['current']} remaining)")
            return True
        
        logger.error(f"{character.name} doesn't have enough investiture ({current} < {amount})")
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
        
        logger.info(f"🧚 Updated {character.name}'s spren bond: {character.spren}")
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
            logger.info(f"⚡ {character.name} learned surge: {surge_name}")
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
                logger.info(f"✨ {character.name} learned invested art: {art_name}")
                return True
        
        print(f"ℹ️ {character.name} already knows: {art_name}")
        return False
    
    # Plan 2.8: the Radiant orders. A character whose CLASS is their order
    # (both shipped PCs are "Lightweaver", not "Radiant") was rejected as
    # "Not a Radiant", so oaths were unreachable for the actual party.
    RADIANT_ORDERS = frozenset({
        "windrunner", "skybreaker", "dustbringer", "edgedancer",
        "truthwatcher", "lightweaver", "elsecaller", "willshaper",
        "stoneward", "bondsmith", "radiant",
    })

    def _is_radiant(self, character) -> bool:
        """Whether a character can hold Ideals (plan 2.8)."""
        char_class = (getattr(character, "character_class", "") or "").strip().lower()
        order = (getattr(character, "radiant_order", "") or "").strip().lower()
        return char_class in self.RADIANT_ORDERS or order in self.RADIANT_ORDERS

    def advance_ideal(self, character_id: str, oath_text: str = None) -> bool:
        """Advance character to next ideal level"""
        if character_id not in self.characters:
            return False
        
        character = self.characters[character_id]
        
        # Only Radiants can advance ideals (plan 2.8: accept the order in
        # either character_class or radiant_order).
        if not self._is_radiant(character):
            logger.error(f"{character.name} is not a Radiant and cannot speak oaths")
            return False
        
        # Maximum of 5 ideals (0-4, where 4 is typically theoretical)
        if character.ideal_level >= 4:
            logger.error(f"{character.name} has already reached the highest known ideal")
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
        
        # Plan 2.8: a new Ideal must actually grant power. surgebinding_level
        # gates every surge (roshar_actions checks it), and Stormlight capacity
        # grows with the bond — without this the Oath was narratively momentous
        # and mechanically inert, so e.g. Soulcasting stayed locked.
        character.surgebinding_level = max(character.surgebinding_level or 0,
                                           character.ideal_level)
        character.stormlight_capacity = max(character.stormlight_capacity or 0,
                                            character.level * 2)
        logger.info(f"🌟 {character.name} spoke their {self._get_ideal_name(character.ideal_level)} Ideal!")
        logger.info(f"   ⚡ Surgebinding level {character.surgebinding_level}, "
                    f"Stormlight capacity {character.stormlight_capacity}")
        print(f"   Oath: \"{oath_spoken}\"")
        logger.debug(f"   Advanced from {self._get_ideal_name(old_level)} to {self._get_ideal_name(character.ideal_level)}")
        
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
            logger.debug(f"   ✨ {character.name} gains basic Radiant abilities")
            # Increase investiture if not already set
            if not character.investiture_points or character.investiture_points.get("maximum", 0) == 0:
                character.investiture_points = {"current": 3, "maximum": 5}
                logger.debug(f"   🌟 Gained investiture points: {character.investiture_points}")
            
        elif ideal_level == 2:
            # Second Ideal - Enhanced abilities, more investiture
            logger.debug(f"   ✨ {character.name} gains enhanced Radiant abilities")
            if character.investiture_points:
                character.investiture_points["maximum"] += 3
                character.investiture_points["current"] = character.investiture_points["maximum"]
                logger.debug(f"   🌟 Investiture increased: {character.investiture_points}")
            
        elif ideal_level == 3:
            # Third Ideal - Shardblade manifestation
            logger.debug(f"   ⚔️ {character.name} can now manifest a Shardblade!")
            if character.investiture_points:
                character.investiture_points["maximum"] += 5
                character.investiture_points["current"] = character.investiture_points["maximum"]
                logger.debug(f"   🌟 Investiture increased: {character.investiture_points}")
            
        elif ideal_level == 4:
            # Fourth Ideal - Shardplate manifestation
            logger.debug(f"   🛡️ {character.name} can now manifest Shardplate!")
            if character.investiture_points:
                character.investiture_points["maximum"] += 7
                character.investiture_points["current"] = character.investiture_points["maximum"]
                logger.debug(f"   🌟 Investiture increased: {character.investiture_points}")
    
    def can_advance_ideal(self, character_id: str) -> Dict[str, Any]:
        """Check if character can advance to next ideal"""
        if character_id not in self.characters:
            return {"can_advance": False, "reason": "Character not found"}
        
        character = self.characters[character_id]
        
        if not self._is_radiant(character):
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
        logger.info(f"🎒 Added {item_name} to {character.name}'s equipment")
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

    def add_currency(self, character_id: str, gp: int = 0, sp: int = 0, cp: int = 0,
                     pp: int = 0, ep: int = 0) -> bool:
        """
        Add currency to character.

        Args:
            character_id: Character ID
            gp: Gold pieces to add
            sp: Silver pieces to add
            cp: Copper pieces to add
            pp: Platinum pieces to add
            ep: Electrum pieces to add

        Returns:
            True if successful, False if character not found
        """
        if character_id not in self.characters:
            return False

        character = self.characters[character_id]
        if character.currency is None:
            character.currency = {"gp": 0, "sp": 0, "cp": 0, "pp": 0, "ep": 0}

        character.currency["gp"] = character.currency.get("gp", 0) + gp
        character.currency["sp"] = character.currency.get("sp", 0) + sp
        character.currency["cp"] = character.currency.get("cp", 0) + cp
        character.currency["pp"] = character.currency.get("pp", 0) + pp
        character.currency["ep"] = character.currency.get("ep", 0) + ep

        logger.info(f"💰 {character.name} gained {gp}gp {sp}sp {cp}cp {pp}pp {ep}ep")
        return True

    def spend_currency(self, character_id: str, gp: int = 0, sp: int = 0, cp: int = 0,
                      pp: int = 0, ep: int = 0) -> Dict[str, Any]:
        """
        Spend currency. Returns success status and remaining currency.

        Automatically converts between denominations (10 cp = 1 sp, 10 sp = 1 gp,
        10 gp = 1 pp).

        Args:
            character_id: Character ID
            gp/sp/cp/pp/ep: Amount to spend in each denomination

        Returns:
            Dict with "success" (bool), "currency" (current), "error" (if failed)
        """
        if character_id not in self.characters:
            return {"success": False, "error": "Character not found"}

        character = self.characters[character_id]
        if character.currency is None:
            character.currency = {"gp": 0, "sp": 0, "cp": 0, "pp": 0, "ep": 0}

        # Convert everything to copper for arithmetic (1 pp = 1000 cp, 1 gp = 100 cp,
        # 1 ep = 50 cp, 1 sp = 10 cp)
        current_cp = (character.currency.get("pp", 0) * 1000 +
                     character.currency.get("gp", 0) * 100 +
                     character.currency.get("ep", 0) * 50 +
                     character.currency.get("sp", 0) * 10 +
                     character.currency.get("cp", 0))

        cost_cp = pp * 1000 + gp * 100 + ep * 50 + sp * 10 + cp

        if current_cp < cost_cp:
            return {
                "success": False,
                "error": f"Insufficient funds (have {current_cp}cp, need {cost_cp}cp)",
                "currency": dict(character.currency)
            }

        # Subtract cost
        remaining_cp = current_cp - cost_cp

        # Convert back to denominations (prefer gold as standard, avoid platinum unless large)
        # This matches player expectations: spending 30gp from 100gp leaves 70gp, not 7pp.
        character.currency["pp"] = 0
        character.currency["ep"] = 0

        character.currency["gp"] = remaining_cp // 100
        remaining_cp %= 100
        character.currency["sp"] = remaining_cp // 10
        character.currency["cp"] = remaining_cp % 10

        logger.info(f"💸 {character.name} spent {gp}gp {sp}sp {cp}cp {pp}pp {ep}ep")
        return {"success": True, "currency": dict(character.currency)}

    def get_carrying_capacity(self, character_id: str) -> Optional[int]:
        """
        Calculate carrying capacity in pounds (STR × 15 per 5e PHB).

        Returns:
            Capacity in pounds, or None if character not found
        """
        if character_id not in self.characters:
            return None

        character = self.characters[character_id]
        str_score = character.ability_scores.get("strength", 10)
        return str_score * 15

    def is_encumbered(self, character_id: str, weight: int) -> Dict[str, Any]:
        """
        Check if a given weight would encumber the character.

        5e encumbrance (variant rule, PHB 176):
        - Normal: up to STR × 5
        - Encumbered (speed -10): STR × 5 to STR × 10
        - Heavily encumbered (speed -20, disadvantage): STR × 10 to STR × 15
        - Over capacity: cannot carry

        Args:
            character_id: Character ID
            weight: Total weight in pounds

        Returns:
            Dict with "encumbrance_level", "speed_penalty", "has_disadvantage", "capacity"
        """
        capacity = self.get_carrying_capacity(character_id)
        if capacity is None:
            return {"error": "Character not found"}

        normal_limit = capacity // 3  # STR × 5
        encumbered_limit = (capacity * 2) // 3  # STR × 10

        if weight <= normal_limit:
            return {
                "encumbrance_level": "normal",
                "speed_penalty": 0,
                "has_disadvantage": False,
                "capacity": capacity,
                "weight": weight
            }
        elif weight <= encumbered_limit:
            return {
                "encumbrance_level": "encumbered",
                "speed_penalty": 10,
                "has_disadvantage": False,
                "capacity": capacity,
                "weight": weight
            }
        elif weight <= capacity:
            return {
                "encumbrance_level": "heavily_encumbered",
                "speed_penalty": 20,
                "has_disadvantage": True,
                "capacity": capacity,
                "weight": weight
            }
        else:
            return {
                "encumbrance_level": "over_capacity",
                "speed_penalty": 0,
                "has_disadvantage": False,
                "capacity": capacity,
                "weight": weight,
                "error": "Weight exceeds carrying capacity"
            }

    def recalculate_ac(self, character_id: str, armor_name: Optional[str] = None,
                      shield: bool = False) -> Optional[int]:
        """
        Recalculate AC from equipped armor and DEX modifier.

        5e armor categories:
        - No armor: 10 + DEX
        - Light armor: base + DEX (e.g., leather 11, studded 12)
        - Medium armor: base + DEX (max +2) (e.g., hide 12, chain shirt 13)
        - Heavy armor: base only (e.g., chain mail 16, plate 18)
        - Shield: +2 to any of the above

        Args:
            character_id: Character ID
            armor_name: Name of equipped armor (None = unarmored)
            shield: Whether a shield is equipped

        Returns:
            New AC value, or None if character not found
        """
        if character_id not in self.characters:
            return None

        character = self.characters[character_id]
        dex_mod = character.ability_modifiers.get("dexterity", 0)

        # Armor base AC and type (simplified common armors)
        armor_table = {
            # Light armor (full DEX)
            "padded": (11, "light"),
            "leather": (11, "light"),
            "studded leather": (12, "light"),
            # Medium armor (DEX capped at +2)
            "hide": (12, "medium"),
            "chain shirt": (13, "medium"),
            "scale mail": (14, "medium"),
            "breastplate": (14, "medium"),
            "half plate": (15, "medium"),
            # Heavy armor (no DEX)
            "ring mail": (14, "heavy"),
            "chain mail": (16, "heavy"),
            "splint": (17, "heavy"),
            "plate": (18, "heavy"),
        }

        if armor_name is None or armor_name.lower() not in armor_table:
            # Unarmored: 10 + DEX
            ac = 10 + dex_mod
        else:
            base_ac, armor_type = armor_table[armor_name.lower()]
            if armor_type == "light":
                ac = base_ac + dex_mod
            elif armor_type == "medium":
                ac = base_ac + min(dex_mod, 2)
            else:  # heavy
                ac = base_ac

        # Shield adds +2
        if shield:
            ac += 2

        character.armor_class = ac
        logger.debug(f"   🛡️  {character.name} AC recalculated: {ac} "
                    f"(armor={armor_name or 'none'}, shield={shield})")
        return ac
    
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
                logger.info(f"🔧 {character.name} gained tool proficiency: {proficiency_name}")
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
        logger.info(f"📝 Logged action for {character.name}: {action_description}")
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

    # Stormlight Management Methods (Combat Plan v4.0)

    def consume_stormlight(self, character_id: str, amount: int) -> bool:
        """
        Consume Stormlight spheres for Surge use.

        Args:
            character_id: Character ID
            amount: Number of spheres to consume

        Returns:
            True if successful, False if insufficient Stormlight
        """
        if character_id not in self.characters:
            return False

        character = self.characters[character_id]
        if character.stormlight_current < amount:
            logger.warning(f"{character.name} has insufficient Stormlight ({character.stormlight_current}/{amount})")
            return False

        character.stormlight_current -= amount
        logger.info(f"⚡ {character.name} consumed {amount} Stormlight ({character.stormlight_current} remaining)")
        return True

    def replenish_stormlight(self, character_id: str, amount: int) -> bool:
        """
        Add Stormlight spheres (from Highstorm, loot, etc.).

        Args:
            character_id: Character ID
            amount: Number of spheres to add

        Returns:
            True if successful, False if character not found
        """
        if character_id not in self.characters:
            return False

        character = self.characters[character_id]

        # Cap at maximum capacity
        new_amount = min(
            character.stormlight_current + amount,
            character.stormlight_capacity
        )

        gained = new_amount - character.stormlight_current
        character.stormlight_current = new_amount

        logger.info(f"⚡ {character.name} gained {gained} Stormlight ({character.stormlight_current}/{character.stormlight_capacity})")
        return True

    def set_stormlight_capacity(self, character_id: str, capacity: int) -> bool:
        """
        Set character's Stormlight capacity (typically Level × 2 for Radiants).

        Args:
            character_id: Character ID
            capacity: New capacity value

        Returns:
            True if successful, False if character not found
        """
        if character_id not in self.characters:
            return False

        character = self.characters[character_id]
        character.stormlight_capacity = max(0, capacity)

        # Ensure current doesn't exceed capacity
        character.stormlight_current = min(character.stormlight_current, character.stormlight_capacity)

        logger.info(f"💎 {character.name}'s Stormlight capacity set to {character.stormlight_capacity}")
        return True

    def apply_passive_stormlight_healing(self, character_id: str, rest_type: str = "short") -> int:
        """
        Apply passive Stormlight healing during rest (1 HP per sphere held).

        Args:
            character_id: Character ID
            rest_type: "short" or "long" (currently only short rest applies passive healing)

        Returns:
            Amount of HP healed
        """
        if character_id not in self.characters:
            return 0

        character = self.characters[character_id]

        if character.stormlight_current <= 0:
            return 0

        if rest_type == "short":
            # Heal 1 HP per sphere held
            healing = character.stormlight_current
            character.hit_points["current"] = min(
                character.hit_points["current"] + healing,
                character.hit_points["maximum"]
            )

            logger.info(f"✨ {character.name} passively healed {healing} HP from Stormlight")
            return healing

        return 0

    # Shardblade Management Methods (Combat Plan v4.0)

    def summon_shardblade(self, character_id: str) -> bool:
        """
        Summon bonded Shardblade (1 Bonus Action in combat, 6 seconds).

        Args:
            character_id: Character ID

        Returns:
            True if successful, False if doesn't have Shardblade or already summoned
        """
        if character_id not in self.characters:
            return False

        character = self.characters[character_id]

        if not character.has_shardblade:
            logger.warning(f"{character.name} does not have a Shardblade")
            return False

        if character.shardblade_summoned:
            logger.info(f"{character.name}'s Shardblade is already summoned")
            return False

        character.shardblade_summoned = True
        logger.info(f"⚔️ {character.name} summoned their Shardblade!")

        if character.shardblade_name:
            logger.debug(f"   Blade: {character.shardblade_name}")

        return True

    def dismiss_shardblade(self, character_id: str) -> bool:
        """
        Dismiss Shardblade to mist (free action).

        Args:
            character_id: Character ID

        Returns:
            True if successful, False if character not found or blade not summoned
        """
        if character_id not in self.characters:
            return False

        character = self.characters[character_id]

        if not character.shardblade_summoned:
            logger.debug(f"{character.name}'s Shardblade is not currently summoned")
            return False

        character.shardblade_summoned = False
        logger.info(f"💨 {character.name} dismissed their Shardblade")
        return True

    def grant_shardblade(self, character_id: str, blade_type: str = "living", blade_name: str = None) -> bool:
        """
        Grant Shardblade to character (typically at Third Ideal for living blades).

        Args:
            character_id: Character ID
            blade_type: "living" (bonded) or "dead" (ancient)
            blade_name: Optional name for the blade

        Returns:
            True if successful, False if character not found
        """
        if character_id not in self.characters:
            return False

        character = self.characters[character_id]
        character.has_shardblade = True
        character.shardblade_type = blade_type
        character.shardblade_name = blade_name

        logger.info(f"⚔️ {character.name} has been granted a {blade_type} Shardblade!")
        if blade_name:
            logger.debug(f"   Blade Name: {blade_name}")

        return True

    # Shardplate Management Methods (Combat Plan v4.0)

    def damage_shardplate(self, character_id: str, damage: int) -> Dict[str, Any]:
        """
        Apply damage to Shardplate HP.

        Args:
            character_id: Character ID
            damage: Amount of damage to apply

        Returns:
            Dict with shattered status and remaining HP
        """
        if character_id not in self.characters:
            return {"error": "Character not found"}

        character = self.characters[character_id]

        if not character.has_shardplate:
            return {"error": "Character does not have Shardplate"}

        old_hp = character.shardplate_hp_current
        character.shardplate_hp_current = max(0, character.shardplate_hp_current - damage)

        shattered = character.shardplate_hp_current == 0

        if shattered:
            logger.warning(f"🛡️ {character.name}'s Shardplate shattered!")
        else:
            logger.info(f"🛡️ {character.name}'s Shardplate damaged: {old_hp} → {character.shardplate_hp_current} HP")

        return {
            "shattered": shattered,
            "hp_current": character.shardplate_hp_current,
            "hp_maximum": character.shardplate_hp_maximum,
            "damage_dealt": old_hp - character.shardplate_hp_current
        }

    def repair_shardplate(self, character_id: str, amount: int = None) -> bool:
        """
        Repair Shardplate HP (typically during Long Rest with Stormlight).

        Args:
            character_id: Character ID
            amount: Amount to repair (None = full repair)

        Returns:
            True if successful, False if character not found or no Shardplate
        """
        if character_id not in self.characters:
            return False

        character = self.characters[character_id]

        if not character.has_shardplate:
            logger.warning(f"{character.name} does not have Shardplate")
            return False

        if amount is None:
            # Full repair
            character.shardplate_hp_current = character.shardplate_hp_maximum
            logger.info(f"🛡️ {character.name}'s Shardplate fully repaired to {character.shardplate_hp_maximum} HP")
        else:
            old_hp = character.shardplate_hp_current
            character.shardplate_hp_current = min(
                character.shardplate_hp_current + amount,
                character.shardplate_hp_maximum
            )
            repaired = character.shardplate_hp_current - old_hp
            logger.info(f"🛡️ {character.name}'s Shardplate repaired by {repaired} HP ({character.shardplate_hp_current}/{character.shardplate_hp_maximum})")

        return True

    def grant_shardplate(self, character_id: str, plate_type: str = "living") -> bool:
        """
        Grant Shardplate to character (typically at Fourth Ideal for living plate).

        Args:
            character_id: Character ID
            plate_type: "living" (bonded) or "dead" (ancient)

        Returns:
            True if successful, False if character not found
        """
        if character_id not in self.characters:
            return False

        character = self.characters[character_id]
        character.has_shardplate = True
        character.shardplate_type = plate_type

        # Set HP based on level (Level × 5)
        character.shardplate_hp_maximum = character.level * 5
        character.shardplate_hp_current = character.shardplate_hp_maximum

        logger.info(f"🛡️ {character.name} has been granted {plate_type} Shardplate!")
        logger.debug(f"   Plate HP: {character.shardplate_hp_maximum}")

        return True


# ----------------------------------------------------------------------
# Class-feature use counters
#
# Module-level so components/combat/class_features.py can read and debit them
# without importing CharacterManager (which would be a cycle: the manager
# imports the feature table). CharacterData remains the single store; these are
# just the two operations combat needs.
# ----------------------------------------------------------------------

def feature_uses_left(character: "CharacterData",
                      entry: Dict[str, Any]) -> int:
    """
    Uses remaining before this feature's next recovery. -1 means unlimited.

    Computed as maximum-minus-spent rather than stored, because the MAXIMUM
    scales with level: a 6th-level barbarian has four rages. Storing "remaining"
    would cap a character at whatever their maximum was when the field was last
    written, so levelling up would not grant the extra rage.
    """
    from components.combat.class_features import max_uses

    maximum = max_uses(entry, character)
    if maximum < 0:
        return -1
    spent = int((getattr(character, "class_feature_uses", None) or {}).get(
        entry["id"], 0))
    return max(0, maximum - spent)


def spend_feature_use(character: "CharacterData",
                      entry: Dict[str, Any]) -> bool:
    """
    Debit one use. False (and nothing spent) when none remain.

    Returning False rather than raising keeps a refused feature the same shape as
    a refused action: the caller reports it and the turn continues.
    """
    remaining = feature_uses_left(character, entry)
    if remaining == 0:
        return False
    if character.class_feature_uses is None:
        character.class_feature_uses = {}
    if remaining > 0:            # unlimited features need no counter
        character.class_feature_uses[entry["id"]] = (
            character.class_feature_uses.get(entry["id"], 0) + 1)
    return True


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
    logger.info(f"Athletics skill data: {athletics_data}")
    
    # Test passive score
    passive_perception = manager.get_passive_score(char_id, "perception")
    logger.info(f"Passive Perception: {passive_perception}")
    
    # Test character summary
    summary = manager.get_character_summary(char_id)
    logger.info(f"Character summary: {summary}")