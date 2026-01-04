"""
NPC Stat Generator with Haystack 2.0 + Pydantic Validation.

Generates D&D 5e NPC stats using LLM + RAG with automatic schema validation.
"""

from pydantic import BaseModel, Field, validator, ValidationError, ConfigDict
from typing import Dict, List, Any, Optional
from haystack.dataclasses import ChatMessage
import json
import re
from pathlib import Path

from config.logging_config import get_logger

logger = get_logger(__name__)


class NPCStats(BaseModel):
    """
    Pydantic model for NPC stats - enforces CharacterData format.

    This model ensures LLM-generated stats match the exact format
    required by CharacterManager.add_npc().
    """
    name: str
    level: int
    character_class: str = Field(..., description="D&D class (NOT 'class')")
    race: str
    background: str
    ability_scores: Dict[str, int]
    hit_points: Dict[str, int] = Field(..., description="Must have current, maximum, temporary")
    armor_class: int
    proficiency_bonus: int
    skills: Dict[str, bool] = Field(..., description="Must be dict, not list")
    attacks: List[Dict[str, Any]]
    special_abilities: List[str]
    challenge_rating: float

    class Config:
        # Allow field alias for backward compatibility
        allow_population_by_field_name = True

    @validator('hit_points')
    def validate_hp(cls, v):
        """Ensure hit_points has all required keys"""
        required_keys = {'current', 'maximum', 'temporary'}
        if not required_keys.issubset(v.keys()):
            missing = required_keys - set(v.keys())
            raise ValueError(f"hit_points missing keys: {missing}")

        # Validate values
        if v['maximum'] <= 0:
            raise ValueError("hit_points maximum must be > 0")
        if v['current'] > v['maximum']:
            raise ValueError("hit_points current cannot exceed maximum")
        if v['temporary'] < 0:
            raise ValueError("hit_points temporary cannot be negative")

        return v

    @validator('ability_scores')
    def validate_abilities(cls, v):
        """Ensure all 6 abilities present and in range"""
        required = {'strength', 'dexterity', 'constitution',
                   'intelligence', 'wisdom', 'charisma'}
        if not required.issubset(v.keys()):
            missing = required - set(v.keys())
            raise ValueError(f"Missing abilities: {missing}")

        for ability, score in v.items():
            if not 1 <= score <= 30:
                raise ValueError(f"{ability} score {score} out of range (1-30)")

        return v

    @validator('skills')
    def validate_skills(cls, v):
        """Ensure skills is dict with bool values"""
        if not isinstance(v, dict):
            raise ValueError("skills must be dict, not list or other type")

        for skill_name, is_proficient in v.items():
            if not isinstance(is_proficient, bool):
                raise ValueError(f"Skill {skill_name} must have bool value, not {type(is_proficient)}")

        return v

    @validator('attacks')
    def validate_attacks(cls, v):
        """Ensure attacks have required fields"""
        required_fields = {'name', 'attack_bonus', 'damage_dice',
                          'damage_bonus', 'damage_type'}

        for i, attack in enumerate(v):
            if not required_fields.issubset(attack.keys()):
                missing = required_fields - set(attack.keys())
                raise ValueError(f"Attack {i} missing fields: {missing}")

        return v


class NPCStatGenerator:
    """
    Generates D&D 5e NPC stats using Haystack LLM + RAG with Pydantic validation.

    Process:
    1. Parse scenario text for enemy descriptions
    2. Query RAG for similar creature stats
    3. Use Haystack LLM to generate complete D&D stat block
    4. Validate with Pydantic (automatic schema enforcement)
    5. Repair if validation fails
    6. Return NPC data dict
    """

    def __init__(self, llm, document_store=None):
        self.llm = llm  # Haystack GeminiChatGenerator
        self.document_store = document_store
        self.logger = get_logger(__name__)  # Initialize logger first
        self.templates = self._load_templates()

    def generate_npc_stats(
        self,
        npc_description: str,
        challenge_rating: float,
        role: str = "combatant",
        context: Dict = None
    ) -> Dict[str, Any]:
        """
        Generate NPC stats via Haystack LLM with Pydantic validation.

        Args:
            npc_description: "goblin warrior with scimitar"
            challenge_rating: 0.25
            role: "combatant|minion|boss|support"
            context: {"party_level": 1, "scenario": {...}}

        Returns:
            Validated NPC stats dict matching CharacterData format
        """
        self.logger.info(f"Generating NPC stats: {npc_description} (CR {challenge_rating})")

        # Step 1: RAG query for reference stats
        rag_results = self._query_creature_database(npc_description)

        # Step 2: Build structured LLM prompt with Pydantic schema
        system_prompt = f"""You are a D&D 5e stat block generator.

Generate complete, balanced NPC stats following D&D 5e rules.

Output MUST be valid JSON matching this EXACT schema:
{NPCStats.schema_json(indent=2)}

CRITICAL REQUIREMENTS:
- Use "character_class" field (NOT "class")
- hit_points MUST be dict with current, maximum, temporary (all required!)
- skills MUST be dict of {{skill_name: true/false}}, NOT array
- All 6 ability scores required (strength, dexterity, constitution, intelligence, wisdom, charisma)
- Ability scores must be 1-30
- Attacks must have name, attack_bonus, damage_dice, damage_bonus, damage_type

Rules:
- HP = (level × class HD) + (CON mod × level)
- AC = 10 + DEX mod + armor bonus
- Attack bonus = proficiency + relevant ability mod
- CR should match difficulty target
- Balance stats for party level"""

        user_prompt = f"""Generate D&D 5e stats for:

Description: {npc_description}
Challenge Rating: {challenge_rating}
Role: {role}
Party Level: {context.get('party_level', 1) if context else 1}

Reference stats from database:
{self._format_rag_results(rag_results)}

Generate complete stat block:"""

        # Step 3: Haystack LLM call
        response = self.llm.run(
            messages=[
                ChatMessage.from_system(system_prompt),
                ChatMessage.from_user(user_prompt)
            ]
        )

        # Step 4: Parse JSON from response
        npc_dict = self._parse_json_response(response['replies'][0].content)

        # Step 5: Validate with Pydantic
        try:
            npc = NPCStats(**npc_dict)
            self.logger.info(f"✅ Generated valid NPC: {npc.name} (AC {npc.armor_class}, HP {npc.hit_points['maximum']})")
            return npc.dict()

        except ValidationError as e:
            self.logger.warning(f"⚠️ Validation failed, attempting repair: {e}")
            # Attempt to repair
            repaired = self.validate_and_repair(npc_dict, challenge_rating)
            return repaired

    def validate_and_repair(self, npc_data: Dict, target_cr: float) -> Dict:
        """
        Validate NPC stats and repair common issues.

        This method attempts to fix common LLM mistakes:
        - Using "class" instead of "character_class"
        - hit_points as int instead of dict
        - skills as list instead of dict
        - Missing ability scores
        - Out-of-range ability scores
        - Missing attacks

        Returns:
            Validated NPC stats dict (guaranteed to pass NPCStats validation)
        """
        # Fix common field name issues
        if "class" in npc_data and "character_class" not in npc_data:
            npc_data["character_class"] = npc_data.pop("class")
            self.logger.debug("Fixed: Renamed 'class' to 'character_class'")

        # Fix hit_points format
        if isinstance(npc_data.get("hit_points"), int):
            hp = npc_data["hit_points"]
            npc_data["hit_points"] = {
                "current": hp,
                "maximum": hp,
                "temporary": 0
            }
            self.logger.debug(f"Fixed: Converted hit_points from int to dict")
        elif isinstance(npc_data.get("hit_points"), dict):
            # Ensure all keys present
            hp = npc_data["hit_points"]
            hp.setdefault("temporary", 0)
            if "current" not in hp or "maximum" not in hp:
                max_hp = hp.get("maximum", hp.get("current", 10))
                hp["current"] = hp.get("current", max_hp)
                hp["maximum"] = max_hp
                self.logger.debug("Fixed: Added missing hit_points keys")

        # Fix skills format
        if isinstance(npc_data.get("skills"), list):
            # Convert list to dict
            skills_dict = {skill: True for skill in npc_data["skills"]}
            npc_data["skills"] = skills_dict
            self.logger.debug(f"Fixed: Converted skills from list to dict")
        elif not npc_data.get("skills"):
            npc_data["skills"] = {}

        # Validate and clamp ability scores
        if "ability_scores" in npc_data:
            for ability in ["strength", "dexterity", "constitution",
                          "intelligence", "wisdom", "charisma"]:
                if ability not in npc_data["ability_scores"]:
                    npc_data["ability_scores"][ability] = 10
                    self.logger.warning(f"Fixed: Added missing {ability} score (default 10)")
                else:
                    score = npc_data["ability_scores"][ability]
                    if score < 1:
                        npc_data["ability_scores"][ability] = 1
                        self.logger.warning(f"Fixed: Clamped {ability} to minimum 1")
                    elif score > 30:
                        npc_data["ability_scores"][ability] = 30
                        self.logger.warning(f"Fixed: Clamped {ability} to maximum 30")

        # Recalculate HP if invalid
        if npc_data.get("hit_points", {}).get("maximum", 0) <= 0:
            level = npc_data.get("level", 1)
            con_mod = (npc_data["ability_scores"]["constitution"] - 10) // 2
            max_hp = max(1, (level * 6) + (con_mod * level))  # Assume d8 HD
            npc_data["hit_points"] = {
                "current": max_hp,
                "maximum": max_hp,
                "temporary": 0
            }
            self.logger.warning(f"Fixed: Recalculated HP: {max_hp}")

        # Ensure minimum AC
        if npc_data.get("armor_class", 0) < 8:
            dex_mod = (npc_data["ability_scores"]["dexterity"] - 10) // 2
            npc_data["armor_class"] = 10 + dex_mod
            self.logger.warning(f"Fixed: Set minimum AC: {npc_data['armor_class']}")

        # Ensure at least one attack
        if not npc_data.get("attacks"):
            str_mod = (npc_data["ability_scores"]["strength"] - 10) // 2
            npc_data["attacks"] = [{
                "name": "Unarmed Strike",
                "attack_bonus": 2 + str_mod,
                "damage_dice": "1d4",
                "damage_bonus": str_mod,
                "damage_type": "bludgeoning"
            }]
            self.logger.warning("Fixed: Added default unarmed strike")

        # Ensure required fields
        npc_data.setdefault("name", "Unknown NPC")
        npc_data.setdefault("level", 1)
        npc_data.setdefault("character_class", "Warrior")
        npc_data.setdefault("race", "Unknown")
        npc_data.setdefault("background", "Unknown")
        npc_data.setdefault("proficiency_bonus", 2)
        npc_data.setdefault("special_abilities", [])
        npc_data.setdefault("challenge_rating", target_cr)

        # Try Pydantic validation again
        try:
            npc = NPCStats(**npc_data)
            self.logger.info(f"✅ Repair successful: {npc.name}")
            return npc.dict()
        except ValidationError as e:
            self.logger.error(f"❌ Repair failed: {e}")
            # Return fallback stats
            return self._get_fallback_stats(target_cr)

    def _get_fallback_stats(self, target_cr: float) -> Dict:
        """Return minimal valid fallback stats"""
        return NPCStats(
            name="Unknown NPC",
            level=1,
            character_class="Warrior",
            race="Unknown",
            background="Unknown",
            ability_scores={
                "strength": 10, "dexterity": 10, "constitution": 10,
                "intelligence": 10, "wisdom": 10, "charisma": 10
            },
            hit_points={"current": 10, "maximum": 10, "temporary": 0},
            armor_class=10,
            proficiency_bonus=2,
            skills={},
            attacks=[{
                "name": "Unarmed Strike",
                "attack_bonus": 2,
                "damage_dice": "1d4",
                "damage_bonus": 0,
                "damage_type": "bludgeoning"
            }],
            special_abilities=[],
            challenge_rating=target_cr
        ).dict()

    def get_npc_from_template(self, template_name: str) -> Optional[Dict]:
        """
        Load predefined NPC template.

        Args:
            template_name: "goblin"|"bandit"|"skeleton"|etc

        Returns:
            NPC stat dict from templates file, or None if not found
        """
        if template_name.lower() in self.templates:
            return self.templates[template_name.lower()].copy()
        else:
            self.logger.warning(f"Template not found: {template_name}")
            return None

    def _load_templates(self) -> Dict[str, Dict]:
        """Load NPC templates from data/npc_templates.json"""
        template_path = Path(__file__).parent.parent.parent / "data" / "npc_templates.json"

        if template_path.exists():
            with open(template_path, 'r') as f:
                templates = json.load(f)
            self.logger.info(f"Loaded {len(templates)} NPC templates")
            return templates
        else:
            self.logger.warning("NPC templates file not found, returning empty dict")
            return {}

    def _query_creature_database(self, description: str) -> List[Dict]:
        """Query RAG for similar creature stats"""
        if not self.document_store:
            return []

        try:
            results = self.document_store.query(
                query=description,
                filters={"category": "monsters"},
                top_k=3
            )
            return results
        except Exception as e:
            self.logger.warning(f"RAG query failed: {e}")
            return []

    def _format_rag_results(self, results: List[Dict]) -> str:
        """Format RAG results for LLM prompt"""
        if not results:
            return "No reference data available"

        formatted = []
        for i, result in enumerate(results, 1):
            formatted.append(f"{i}. {result.get('content', '')[:200]}")

        return "\n".join(formatted)

    def _parse_json_response(self, response: str) -> Dict:
        """Parse LLM JSON response"""
        # Extract JSON from markdown code block if present
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = response

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse NPC JSON: {e}")
            # Return minimal fallback
            return {
                "name": "Unknown NPC",
                "level": 1,
                "character_class": "Warrior",
                "race": "Unknown",
                "background": "Unknown",
                "ability_scores": {
                    "strength": 10, "dexterity": 10, "constitution": 10,
                    "intelligence": 10, "wisdom": 10, "charisma": 10
                },
                "hit_points": {"maximum": 10, "current": 10, "temporary": 0},
                "armor_class": 10,
                "proficiency_bonus": 2,
                "skills": {},
                "attacks": [],
                "special_abilities": [],
                "challenge_rating": 0.5
            }
