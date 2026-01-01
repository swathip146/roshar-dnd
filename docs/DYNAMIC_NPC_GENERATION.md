# Dynamic NPC Generation System

## Overview

The Dynamic NPC Generation system automatically creates combat-ready NPCs based on:
1. **NPC Templates** (character sheets with stat ranges)
2. **Encounter Context** (scene description, difficulty, party level)
3. **Gameplay Scenario** (narrative needs, tactical requirements)

This enables the game to generate "3 Voidbringers around a caravan" with varied stats based on a single template, rather than manually defining each NPC.

---

## Design Goals

1. **Flexible NPC Creation:** Support both dynamic (procedurally generated) and static (hand-crafted) NPCs
2. **Template-Based:** Define NPC types once (Voidbringer, Bandit, Knight Radiant)
3. **Context-Aware:** Generate stats appropriate to the encounter (3 weak vs 1 strong)
4. **Tracked Lifecycle:** NPCs persist through combat and can be referenced later
5. **Variation:** Same template generates unique individuals with different stats
6. **Scalable:** Works for any number of NPCs in any encounter

---

## NPC Types Supported

### 1. **Dynamic NPCs** (Procedurally Generated)
Generated on-the-fly from templates with stat ranges. Perfect for:
- Generic enemies (bandits, voidbringers, soldiers)
- Encounter scaling (adjust difficulty based on party)
- Mass combat scenarios (10+ NPCs needed quickly)

**Example:** "3 Voidbringers" → Each gets unique rolled stats

### 2. **Static NPCs** (Hand-Crafted)
Pre-defined with exact stats. Perfect for:
- Named villains (Odium, Moash, Amaram)
- Quest-critical NPCs (Captain Kholinar, Shallan's brothers)
- Recurring characters (same NPC appears in multiple sessions)
- Unique builds (specific tactics, unusual stat distributions)

**Example:** "Moash" → Always has STR 18, DEX 14, HP 85, specific abilities

### 3. **Hybrid Approach**
Static NPC as base + dynamic scaling. Perfect for:
- Boss encounters that scale with party level
- Recurring enemies that grow stronger over time

**Example:** "Captain Kholinar (Elite)" → Base stats + level modifier

---

## Architecture

### 1. NPC Template Structure

NPC templates define stat **ranges** rather than fixed values:

```json
{
  "template_id": "voidbringer_soldier",
  "name_pattern": "Voidbringer {variant}",
  "variants": ["Scout", "Warrior", "Brute", "Archer"],
  "description": "Corrupted humanoid infused with voidlight",
  "type": "combat_npc",
  "challenge_rating_range": [1, 3],

  "stats": {
    "level_range": [1, 5],
    "class_options": ["Fighter", "Barbarian"],

    "ability_scores": {
      "strength": {"min": 14, "max": 18, "distribution": "normal"},
      "dexterity": {"min": 10, "max": 14, "distribution": "normal"},
      "constitution": {"min": 12, "max": 16, "distribution": "normal"},
      "intelligence": {"min": 6, "max": 10, "distribution": "low"},
      "wisdom": {"min": 8, "max": 12, "distribution": "normal"},
      "charisma": {"min": 6, "max": 8, "distribution": "low"}
    },

    "hit_points": {
      "formula": "level * 8 + CON_modifier * level",
      "min_multiplier": 0.8,
      "max_multiplier": 1.2
    },

    "armor_class": {
      "base": 14,
      "variance": 2,
      "calculation": "base + DEX_modifier"
    },

    "proficiency_bonus": {
      "formula": "floor((level - 1) / 4) + 2"
    },

    "skills": {
      "athletics": {"proficiency": 0.8, "expertise": 0.0},
      "intimidation": {"proficiency": 0.6, "expertise": 0.0},
      "perception": {"proficiency": 0.5, "expertise": 0.0}
    },

    "saving_throws": ["strength", "constitution"],

    "attacks": [
      {
        "name": "Corrupted Blade",
        "type": "melee_weapon",
        "damage_dice": "1d8",
        "damage_bonus": "STR",
        "damage_type": "slashing",
        "additional_damage": {
          "dice": "1d4",
          "type": "void",
          "chance": 0.5
        }
      },
      {
        "name": "Void Bolt",
        "type": "ranged_spell",
        "range": 60,
        "damage_dice": "2d6",
        "damage_type": "void",
        "available_above_level": 3
      }
    ],

    "special_abilities": [
      {
        "name": "Voidlight Resilience",
        "description": "Resistance to radiant damage",
        "effect": "damage_resistance",
        "damage_types": ["radiant"]
      },
      {
        "name": "Corrupted Regeneration",
        "description": "Heals 1d4 HP at start of turn if below half HP",
        "trigger": "start_of_turn",
        "condition": "hp < max_hp / 2",
        "healing": "1d4",
        "chance": 0.3
      }
    ]
  },

  "behavior": {
    "aggression": "high",
    "tactics": "swarm_attack",
    "morale_threshold": 0.25,
    "flee_below_hp": 0.1
  },

  "loot_table": {
    "currency": {"min": 10, "max": 50, "unit": "spheres"},
    "items": [
      {"name": "Corrupted Blade", "chance": 0.5},
      {"name": "Voidlight Shard", "chance": 0.2}
    ]
  }
}
```

### 2. Encounter Definition

Encounters specify **what** NPCs to generate and **how many**:

```json
{
  "encounter_id": "caravan_ambush_001",
  "scene_description": "Voidbringers attack a merchant caravan on the Shattered Plains",
  "trigger": "player_enters_location:shattered_plains",

  "difficulty": "medium",
  "environment": {
    "location": "Shattered Plains",
    "terrain": "rocky",
    "weather": "storm_approaching",
    "time_of_day": "dusk"
  },

  "npcs": [
    {
      "template_id": "voidbringer_soldier",
      "count": 3,
      "scaling": "party_size",
      "role": "primary_threat",
      "positioning": "surrounding_caravan",
      "stat_bias": {
        "strength": "+2",
        "level_modifier": 0
      }
    },
    {
      "template_id": "voidbringer_archer",
      "count": 1,
      "scaling": "fixed",
      "role": "ranged_support",
      "positioning": "elevated_rock",
      "stat_bias": {
        "dexterity": "+3",
        "level_modifier": +1
      }
    }
  ],

  "objectives": {
    "primary": "defeat_all_enemies",
    "secondary": ["protect_caravan", "minimize_casualties"],
    "failure_conditions": ["caravan_destroyed"]
  },

  "rewards": {
    "experience": "standard",
    "loot": "combine_all_npcs",
    "story_progression": "unlock_location:warcamp_7"
  }
}
```

### 3. Generation Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│  1. ENCOUNTER TRIGGER                                       │
│  - Scene requires NPCs (combat, dialogue, etc.)            │
│  - GameEngine detects encounter                             │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│  2. LOAD ENCOUNTER DEFINITION                               │
│  - Read encounter JSON                                      │
│  - Parse NPC requirements (templates, counts, roles)        │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│  3. NPC GENERATOR - For each NPC in encounter               │
│  - Load template (e.g., voidbringer_soldier)               │
│  - Apply context modifiers (party level, difficulty)        │
│  - Roll stats within ranges (normal distribution)           │
│  - Generate unique identifier (voidbringer_001, _002)       │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│  4. CHARACTER MANAGER - Register NPC                        │
│  - Convert generated stats → CharacterData                  │
│  - Add to CharacterManager.characters[npc_id]               │
│  - Tag as temporary (cleanup after combat) or persistent    │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│  5. DND_ENGINE_WRAPPER - Create Entity                      │
│  - Sync new NPC to dnd_engine Entity                        │
│  - Add to wrapper.entities[npc_id]                          │
│  - Ready for combat mechanics                               │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│  6. GAME ENGINE - Initialize Combat                         │
│  - Add NPCs to combat_state.active_combatants               │
│  - Roll initiative for all combatants                       │
│  - Track NPC lifecycle (in_combat → defeated → cleanup)     │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation Classes

### 1. **NPCTemplate** (New Class)
**File:** `components/npc_template.py`

```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Literal
import random

@dataclass
class StatRange:
    """Defines a stat with min/max and distribution"""
    min: int
    max: int
    distribution: Literal["uniform", "normal", "low", "high"] = "uniform"

    def roll(self) -> int:
        """Roll a value within range using specified distribution"""
        if self.distribution == "uniform":
            return random.randint(self.min, self.max)
        elif self.distribution == "normal":
            # Normal distribution centered at midpoint
            midpoint = (self.min + self.max) / 2
            std_dev = (self.max - self.min) / 4
            value = int(random.gauss(midpoint, std_dev))
            return max(self.min, min(self.max, value))
        elif self.distribution == "low":
            # Bias toward lower values
            return int(random.triangular(self.min, self.max, self.min))
        elif self.distribution == "high":
            # Bias toward higher values
            return int(random.triangular(self.min, self.max, self.max))

@dataclass
class NPCTemplate:
    """Template for generating NPC instances"""
    template_id: str
    name_pattern: str  # e.g., "Voidbringer {variant}"
    variants: List[str]
    description: str
    type: str  # "combat_npc", "friendly_npc", "neutral_npc"
    challenge_rating_range: tuple[int, int]

    # Stats as ranges
    level_range: tuple[int, int]
    class_options: List[str]
    ability_scores: Dict[str, StatRange]
    hp_formula: str
    ac_base: int
    ac_variance: int

    skills: Dict[str, Dict[str, float]]  # skill_name → {proficiency_chance, expertise_chance}
    saving_throws: List[str]
    attacks: List[Dict[str, Any]]
    special_abilities: List[Dict[str, Any]]

    behavior: Dict[str, Any]
    loot_table: Dict[str, Any]

    def generate_instance(
        self,
        instance_id: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate a unique NPC instance from this template.

        Args:
            instance_id: Unique ID for this instance (e.g., "voidbringer_001")
            context: {
                "party_level": int,
                "difficulty": str,
                "role": str,
                "stat_bias": Dict[str, int]
            }

        Returns:
            CharacterData-compatible dictionary
        """
        # Choose variant
        variant = random.choice(self.variants)
        name = self.name_pattern.format(variant=variant)

        # Roll level
        level = random.randint(*self.level_range)

        # Apply context modifiers
        if context.get("difficulty") == "hard":
            level = min(level + 2, self.level_range[1])
        elif context.get("difficulty") == "easy":
            level = max(level - 2, self.level_range[0])

        # Roll ability scores
        ability_scores = {}
        for ability, stat_range in self.ability_scores.items():
            base_value = stat_range.roll()
            # Apply stat bias from context
            bias = context.get("stat_bias", {}).get(ability, 0)
            ability_scores[ability] = max(3, min(20, base_value + bias))

        # Calculate HP
        con_modifier = (ability_scores["constitution"] - 10) // 2
        max_hp = level * 8 + con_modifier * level

        # Calculate AC
        dex_modifier = (ability_scores["dexterity"] - 10) // 2
        ac = self.ac_base + dex_modifier + random.randint(-self.ac_variance, self.ac_variance)

        # Proficiency bonus
        proficiency_bonus = ((level - 1) // 4) + 2

        # Roll skills
        character_skills = {}
        for skill_name, probabilities in self.skills.items():
            if random.random() < probabilities["proficiency"]:
                character_skills[skill_name] = True

        # Build CharacterData-compatible dict
        return {
            "character_id": instance_id,
            "name": name,
            "level": level,
            "class": random.choice(self.class_options),
            "race": "Voidbringer",  # Template-specific

            "ability_scores": ability_scores,
            "hit_points": {
                "maximum": max_hp,
                "current": max_hp,
                "temporary": 0
            },
            "armor_class": ac,
            "proficiency_bonus": proficiency_bonus,
            "speed": 30,

            "skills": character_skills,
            "expertise_skills": [],
            "saving_throw_proficiencies": self.saving_throws,

            "attacks": self._generate_attacks(ability_scores, proficiency_bonus, level),
            "special_abilities": self.special_abilities,

            # Metadata
            "is_npc": True,
            "template_id": self.template_id,
            "variant": variant,
            "behavior": self.behavior,
            "loot_table": self.loot_table
        }

    def _generate_attacks(self, ability_scores: Dict, prof_bonus: int, level: int) -> List[Dict]:
        """Generate attack definitions with calculated bonuses"""
        attacks = []
        for attack_template in self.attacks:
            # Skip attacks not available at this level
            if attack_template.get("available_above_level", 0) > level:
                continue

            # Calculate attack bonus
            ability = attack_template.get("damage_bonus", "STR")
            ability_modifier = (ability_scores.get(ability.lower(), 10) - 10) // 2
            attack_bonus = prof_bonus + ability_modifier

            attacks.append({
                "name": attack_template["name"],
                "type": attack_template["type"],
                "attack_bonus": attack_bonus,
                "damage_dice": attack_template["damage_dice"],
                "damage_bonus": ability_modifier,
                "damage_type": attack_template["damage_type"],
                "range": attack_template.get("range", 5)
            })

        return attacks
```

### 2. **NPCGenerator** (New Class)
**File:** `components/npc_generator.py`

```python
from typing import Dict, List, Any, Optional
from pathlib import Path
import json
from components.npc_template import NPCTemplate
from config.logging_config import get_logger

logger = get_logger(__name__)

class NPCGenerator:
    """
    Generates NPC instances from templates based on encounter context.
    """

    def __init__(self, templates_dir: str = "data/npc_templates"):
        self.templates_dir = Path(templates_dir)
        self.templates: Dict[str, NPCTemplate] = {}
        self._load_templates()

        # Track generated NPCs for lifecycle management
        self.active_npcs: Dict[str, Dict[str, Any]] = {}
        self._npc_counter = 0

    def _load_templates(self):
        """Load all NPC templates from JSON files"""
        if not self.templates_dir.exists():
            logger.warning(f"Templates directory not found: {self.templates_dir}")
            return

        for template_file in self.templates_dir.glob("*.json"):
            try:
                with open(template_file) as f:
                    template_data = json.load(f)

                # Parse stat ranges
                from components.npc_template import StatRange
                ability_scores = {}
                for ability, range_data in template_data["stats"]["ability_scores"].items():
                    ability_scores[ability] = StatRange(**range_data)

                template = NPCTemplate(
                    template_id=template_data["template_id"],
                    name_pattern=template_data["name_pattern"],
                    variants=template_data["variants"],
                    description=template_data["description"],
                    type=template_data["type"],
                    challenge_rating_range=tuple(template_data["challenge_rating_range"]),
                    level_range=tuple(template_data["stats"]["level_range"]),
                    class_options=template_data["stats"]["class_options"],
                    ability_scores=ability_scores,
                    hp_formula=template_data["stats"]["hit_points"]["formula"],
                    ac_base=template_data["stats"]["armor_class"]["base"],
                    ac_variance=template_data["stats"]["armor_class"]["variance"],
                    skills=template_data["stats"]["skills"],
                    saving_throws=template_data["stats"]["saving_throws"],
                    attacks=template_data["stats"]["attacks"],
                    special_abilities=template_data["stats"]["special_abilities"],
                    behavior=template_data["behavior"],
                    loot_table=template_data["loot_table"]
                )

                self.templates[template.template_id] = template
                logger.info(f"Loaded NPC template: {template.template_id}")

            except Exception as e:
                logger.error(f"Failed to load template {template_file}: {e}")

    def generate_encounter_npcs(
        self,
        encounter_definition: Dict[str, Any],
        party_level: int = 1,
        party_size: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Generate all NPCs for an encounter.

        Args:
            encounter_definition: Encounter JSON data
            party_level: Average level of player party
            party_size: Number of players

        Returns:
            List of CharacterData-compatible dictionaries
        """
        generated_npcs = []

        for npc_spec in encounter_definition.get("npcs", []):
            template_id = npc_spec["template_id"]
            template = self.templates.get(template_id)

            if not template:
                logger.error(f"Template not found: {template_id}")
                continue

            # Determine count (may scale with party size)
            count = npc_spec["count"]
            if npc_spec.get("scaling") == "party_size":
                count = max(1, count + (party_size - 4) // 2)  # Scale from baseline of 4 players

            # Generate context for this NPC group
            context = {
                "party_level": party_level,
                "difficulty": encounter_definition.get("difficulty", "medium"),
                "role": npc_spec.get("role", "standard"),
                "stat_bias": npc_spec.get("stat_bias", {}),
                "positioning": npc_spec.get("positioning")
            }

            # Generate each instance
            for i in range(count):
                self._npc_counter += 1
                instance_id = f"{template_id}_{self._npc_counter:03d}"

                npc_data = template.generate_instance(instance_id, context)
                npc_data["encounter_id"] = encounter_definition["encounter_id"]
                npc_data["role"] = context["role"]
                npc_data["positioning"] = context["positioning"]

                generated_npcs.append(npc_data)
                self.active_npcs[instance_id] = npc_data

                logger.info(f"Generated NPC: {npc_data['name']} ({instance_id})")

        return generated_npcs

    def cleanup_encounter_npcs(self, encounter_id: str):
        """Remove NPCs from a completed encounter"""
        to_remove = [
            npc_id for npc_id, npc_data in self.active_npcs.items()
            if npc_data.get("encounter_id") == encounter_id
        ]

        for npc_id in to_remove:
            del self.active_npcs[npc_id]
            logger.info(f"Cleaned up NPC: {npc_id}")

    def get_template(self, template_id: str) -> Optional[NPCTemplate]:
        """Get template by ID"""
        return self.templates.get(template_id)
```

### 3. **CharacterManager Extension**
**File:** `components/character_manager.py` (modify existing)

```python
# Add to existing CharacterManager class

def add_npc_from_data(self, npc_data: Dict[str, Any]) -> str:
    """
    Add NPC generated by NPCGenerator.

    Args:
        npc_data: CharacterData-compatible dictionary from NPCGenerator

    Returns:
        npc_id
    """
    character_data = CharacterData(
        name=npc_data["name"],
        level=npc_data["level"],
        class_name=npc_data["class"],
        race=npc_data.get("race", "Unknown"),
        background=npc_data.get("background", "NPC"),

        ability_scores=npc_data["ability_scores"],
        hit_points=npc_data["hit_points"],
        armor_class=npc_data["armor_class"],
        proficiency_bonus=npc_data["proficiency_bonus"],
        speed=npc_data.get("speed", 30),

        skills=npc_data["skills"],
        expertise_skills=npc_data.get("expertise_skills", []),
        saving_throw_proficiencies=npc_data["saving_throw_proficiencies"],

        # NPC-specific metadata
        is_npc=True,
        template_id=npc_data.get("template_id"),
        encounter_id=npc_data.get("encounter_id")
    )

    npc_id = npc_data["character_id"]
    self.characters[npc_id] = character_data

    logger.info(f"Added NPC to CharacterManager: {npc_id} ({character_data.name})")
    return npc_id

def remove_npcs_by_encounter(self, encounter_id: str) -> int:
    """Remove all NPCs from a specific encounter"""
    to_remove = [
        char_id for char_id, char_data in self.characters.items()
        if getattr(char_data, "encounter_id", None) == encounter_id
    ]

    for char_id in to_remove:
        del self.characters[char_id]

    logger.info(f"Removed {len(to_remove)} NPCs from encounter {encounter_id}")
    return len(to_remove)
```

---

## Data File Structure

```
data/
├── npc_templates/
│   ├── voidbringer_soldier.json
│   ├── voidbringer_archer.json
│   ├── bandit_thug.json
│   ├── knight_radiant_windrunner.json
│   └── parshendi_warrior.json
│
├── encounters/
│   ├── caravan_ambush_001.json
│   ├── warcamp_raid_002.json
│   └── tower_defense_003.json
│
└── current_campaign/
    └── shards_of_honor.json (references encounters)
```

---

## Integration with Existing Systems

### GameEngine Integration

```python
# In GameEngine class

def initialize_encounter(self, encounter_id: str, party_level: int, party_size: int):
    """Initialize combat encounter with generated NPCs"""

    # Load encounter definition
    encounter_data = self._load_encounter(encounter_id)

    # Generate NPCs
    generated_npcs = self.npc_generator.generate_encounter_npcs(
        encounter_data,
        party_level=party_level,
        party_size=party_size
    )

    # Add NPCs to CharacterManager
    npc_ids = []
    for npc_data in generated_npcs:
        npc_id = self.character_manager.add_npc_from_data(npc_data)
        npc_ids.append(npc_id)

    # Sync NPCs to dnd_engine_wrapper
    if self.dnd_engine_wrapper:
        self.dnd_engine_wrapper._sync_characters_to_entities()

    # Initialize combat state
    self.game_state.combat_state = {
        "in_combat": True,
        "encounter_id": encounter_id,
        "active_combatants": npc_ids + [self.player_character_id],
        "npc_combatants": npc_ids,
        "initiative_order": self._roll_initiative(npc_ids + [self.player_character_id]),
        "current_turn": 0,
        "round_number": 1
    }

    logger.info(f"Initialized encounter {encounter_id} with {len(npc_ids)} NPCs")
    return generated_npcs

def end_encounter(self, encounter_id: str):
    """Clean up encounter NPCs after combat"""
    # Remove NPCs from CharacterManager
    self.character_manager.remove_npcs_by_encounter(encounter_id)

    # Cleanup generator tracking
    self.npc_generator.cleanup_encounter_npcs(encounter_id)

    # Reset combat state
    self.game_state.combat_state["in_combat"] = False
    self.game_state.combat_state["active_combatants"] = []

    # Re-sync dnd_engine_wrapper (removes NPC entities)
    if self.dnd_engine_wrapper:
        self.dnd_engine_wrapper._sync_characters_to_entities()
```

---

## Lifecycle Management

```
┌─────────────────────────────────────────────────────────┐
│  ENCOUNTER START                                        │
│  - Load encounter definition                            │
│  - NPCGenerator.generate_encounter_npcs()               │
│  - CharacterManager.add_npc_from_data() for each        │
│  - DnDEngineWrapper._sync_characters_to_entities()      │
│  - GameEngine.combat_state = in_combat                  │
└──────────────────────┬──────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────┐
│  DURING COMBAT                                          │
│  - NPCs tracked in CharacterManager.characters          │
│  - NPCs tracked in DnDEngineWrapper.entities            │
│  - NPCs tracked in GameEngine.combat_state              │
│  - HP updates synced between Entity ↔ CharacterManager  │
└──────────────────────┬──────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────┐
│  ENCOUNTER END                                          │
│  - GameEngine.end_encounter(encounter_id)               │
│  - CharacterManager.remove_npcs_by_encounter()          │
│  - NPCGenerator.cleanup_encounter_npcs()                │
│  - DnDEngineWrapper re-syncs (NPC entities removed)     │
│  - GameEngine.combat_state.in_combat = False            │
└─────────────────────────────────────────────────────────┘
```

**Optional: Persistent NPCs**
- Tag NPCs as `persistent: true` in encounter definition
- Skip cleanup for persistent NPCs (e.g., recurring villain)
- Keep in CharacterManager until explicitly removed

---

## Example Usage

### 1. Create Voidbringer Template

Save as `data/npc_templates/voidbringer_soldier.json`:
```json
{
  "template_id": "voidbringer_soldier",
  "name_pattern": "Voidbringer {variant}",
  "variants": ["Scout", "Warrior", "Brute"],
  "description": "Corrupted humanoid infused with voidlight",
  "type": "combat_npc",
  "challenge_rating_range": [1, 3],
  "stats": {
    "level_range": [1, 5],
    "class_options": ["Fighter"],
    "ability_scores": {
      "strength": {"min": 14, "max": 18, "distribution": "normal"},
      "dexterity": {"min": 10, "max": 14, "distribution": "normal"},
      "constitution": {"min": 12, "max": 16, "distribution": "normal"},
      "intelligence": {"min": 6, "max": 10, "distribution": "low"},
      "wisdom": {"min": 8, "max": 12, "distribution": "normal"},
      "charisma": {"min": 6, "max": 8, "distribution": "low"}
    },
    "hit_points": {
      "formula": "level * 8 + CON_modifier * level"
    },
    "armor_class": {
      "base": 14,
      "variance": 2
    },
    "skills": {
      "athletics": {"proficiency": 0.8, "expertise": 0.0},
      "intimidation": {"proficiency": 0.6, "expertise": 0.0}
    },
    "saving_throws": ["strength", "constitution"],
    "attacks": [
      {
        "name": "Corrupted Blade",
        "type": "melee_weapon",
        "damage_dice": "1d8",
        "damage_bonus": "STR",
        "damage_type": "slashing"
      }
    ],
    "special_abilities": []
  },
  "behavior": {
    "aggression": "high",
    "tactics": "swarm_attack"
  },
  "loot_table": {
    "currency": {"min": 10, "max": 50, "unit": "spheres"}
  }
}
```

### 2. Create Encounter

Save as `data/encounters/caravan_ambush_001.json`:
```json
{
  "encounter_id": "caravan_ambush_001",
  "scene_description": "Voidbringers attack a merchant caravan",
  "difficulty": "medium",
  "npcs": [
    {
      "template_id": "voidbringer_soldier",
      "count": 3,
      "scaling": "party_size",
      "role": "primary_threat"
    }
  ]
}
```

### 3. Trigger Encounter in Game

```python
# In GameEngine when encounter triggers
game_engine.initialize_encounter(
    encounter_id="caravan_ambush_001",
    party_level=3,
    party_size=1
)

# Result: 3 unique Voidbringers generated:
# - voidbringer_soldier_001: STR 16, DEX 12, CON 14, HP 28, AC 15
# - voidbringer_soldier_002: STR 15, DEX 13, CON 15, HP 30, AC 16
# - voidbringer_soldier_003: STR 18, DEX 11, CON 13, HP 26, AC 14
```

---

## Benefits

1. **Reusability:** Define Voidbringer template once, generate infinite instances
2. **Variety:** Each instance has unique stats (no identical twins)
3. **Scalability:** Automatically adjusts to party level/size
4. **Narrative Consistency:** "3 Voidbringers" in story = 3 actual tracked NPCs
5. **Memory Efficient:** Templates are small, instances created on-demand
6. **Cleanup:** NPCs removed after encounter (or kept if persistent)
7. **Integration:** Works seamlessly with existing CharacterManager/DnDEngineWrapper

---

## Future Enhancements

1. **AI-Generated Variants:** Use LLM to generate unique names/descriptions
2. **Dynamic Difficulty:** Adjust stats in real-time based on combat performance
3. **NPC Relationships:** Track alliances, rivalries between NPC instances
4. **Persistent World:** Some NPCs persist across sessions (e.g., recurring villains)
5. **Loot Generation:** Procedurally generate loot based on template loot tables
6. **Behavior AI:** Use behavior profiles for combat tactics

---

## Static NPC Support

### Static NPC Definition

Static NPCs are defined with **exact values** instead of ranges:

```json
{
  "npc_id": "moash_betrayer",
  "name": "Moash",
  "type": "static_npc",
  "description": "Former Bridge Four member, now servant of Odium",

  "stats": {
    "level": 10,
    "class": "Fighter",
    "race": "Alethi",

    "ability_scores": {
      "strength": 18,
      "dexterity": 14,
      "constitution": 16,
      "intelligence": 12,
      "wisdom": 10,
      "charisma": 8
    },

    "hit_points": {
      "maximum": 95,
      "current": 95
    },

    "armor_class": 18,
    "proficiency_bonus": 4,
    "speed": 30,

    "skills": {
      "athletics": true,
      "intimidation": true,
      "perception": true
    },

    "expertise_skills": ["athletics"],
    "saving_throw_proficiencies": ["strength", "constitution"],

    "attacks": [
      {
        "name": "Honorblade Strike",
        "type": "melee_weapon",
        "attack_bonus": 8,
        "damage_dice": "2d8",
        "damage_bonus": 4,
        "damage_type": "radiant",
        "range": 5,
        "special": "Can use Windrunner abilities"
      }
    ],

    "special_abilities": [
      {
        "name": "Surge of Gravitation",
        "description": "Can manipulate gravity (Windrunner surge)",
        "uses_per_day": 5
      },
      {
        "name": "Odium's Blessing",
        "description": "Advantage on saving throws vs fear/charm",
        "passive": true
      }
    ]
  },

  "behavior": {
    "aggression": "calculated",
    "tactics": "duel_focused",
    "morale_threshold": 0.0,
    "flee_below_hp": 0.0,
    "dialogue_tags": ["vengeful", "nihilistic", "ruthless"]
  },

  "persistent": true,
  "can_level_up": true
}
```

### Using Static NPCs in Encounters

Mix static and dynamic NPCs in the same encounter:

```json
{
  "encounter_id": "moash_ambush_001",
  "scene_description": "Moash leads a squad of Voidbringers to ambush the party",
  "difficulty": "deadly",

  "npcs": [
    {
      "type": "static",
      "npc_id": "moash_betrayer",
      "positioning": "center",
      "role": "boss"
    },
    {
      "type": "dynamic",
      "template_id": "voidbringer_soldier",
      "count": 4,
      "positioning": "flanking",
      "role": "minions"
    }
  ]
}
```

### NPCGenerator Support for Static NPCs

Update the `NPCGenerator` class to handle both types:

```python
class NPCGenerator:
    def __init__(self, templates_dir: str = "data/npc_templates", static_npcs_dir: str = "data/static_npcs"):
        self.templates_dir = Path(templates_dir)
        self.static_npcs_dir = Path(static_npcs_dir)

        # Load both types
        self.templates: Dict[str, NPCTemplate] = {}
        self.static_npcs: Dict[str, Dict[str, Any]] = {}

        self._load_templates()
        self._load_static_npcs()

    def _load_static_npcs(self):
        """Load pre-defined static NPCs from JSON files"""
        if not self.static_npcs_dir.exists():
            logger.warning(f"Static NPCs directory not found: {self.static_npcs_dir}")
            return

        for npc_file in self.static_npcs_dir.glob("*.json"):
            try:
                with open(npc_file) as f:
                    npc_data = json.load(f)

                npc_id = npc_data["npc_id"]
                self.static_npcs[npc_id] = npc_data
                logger.info(f"Loaded static NPC: {npc_id} ({npc_data['name']})")

            except Exception as e:
                logger.error(f"Failed to load static NPC {npc_file}: {e}")

    def generate_encounter_npcs(
        self,
        encounter_definition: Dict[str, Any],
        party_level: int = 1,
        party_size: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Generate all NPCs for an encounter (both static and dynamic).
        """
        generated_npcs = []

        for npc_spec in encounter_definition.get("npcs", []):
            npc_type = npc_spec.get("type", "dynamic")

            if npc_type == "static":
                # Load pre-defined static NPC
                npc_id = npc_spec["npc_id"]
                static_npc = self.static_npcs.get(npc_id)

                if not static_npc:
                    logger.error(f"Static NPC not found: {npc_id}")
                    continue

                # Create instance from static definition
                npc_data = self._create_static_npc_instance(
                    static_npc,
                    npc_spec,
                    encounter_definition
                )
                generated_npcs.append(npc_data)
                self.active_npcs[npc_id] = npc_data

                logger.info(f"Added static NPC: {npc_data['name']} ({npc_id})")

            elif npc_type == "dynamic":
                # Generate from template (existing code)
                template_id = npc_spec["template_id"]
                template = self.templates.get(template_id)

                if not template:
                    logger.error(f"Template not found: {template_id}")
                    continue

                # ... existing dynamic generation code ...

        return generated_npcs

    def _create_static_npc_instance(
        self,
        static_npc: Dict[str, Any],
        npc_spec: Dict[str, Any],
        encounter_definition: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create NPC instance from static definition.

        Optionally apply level scaling or difficulty modifiers.
        """
        # Copy base stats
        stats = static_npc["stats"].copy()

        # Optional: Apply scaling if specified
        if npc_spec.get("apply_scaling", False):
            level_modifier = encounter_definition.get("level_modifier", 0)
            stats["level"] += level_modifier
            # Recalculate HP, attack bonuses, etc.

        # Build CharacterData-compatible dict
        return {
            "character_id": static_npc["npc_id"],
            "name": static_npc["name"],
            "level": stats["level"],
            "class": stats["class"],
            "race": stats.get("race", "Unknown"),

            "ability_scores": stats["ability_scores"],
            "hit_points": stats["hit_points"],
            "armor_class": stats["armor_class"],
            "proficiency_bonus": stats["proficiency_bonus"],
            "speed": stats["speed"],

            "skills": stats["skills"],
            "expertise_skills": stats.get("expertise_skills", []),
            "saving_throw_proficiencies": stats["saving_throw_proficiencies"],

            "attacks": stats.get("attacks", []),
            "special_abilities": stats.get("special_abilities", []),

            # Metadata
            "is_npc": True,
            "is_static": True,
            "encounter_id": encounter_definition["encounter_id"],
            "role": npc_spec.get("role", "standard"),
            "positioning": npc_spec.get("positioning"),
            "behavior": static_npc.get("behavior", {}),
            "persistent": static_npc.get("persistent", False)
        }

    def cleanup_encounter_npcs(self, encounter_id: str):
        """Remove NPCs from encounter (skip persistent ones)"""
        to_remove = []

        for npc_id, npc_data in self.active_npcs.items():
            # Skip persistent NPCs (e.g., recurring villains)
            if npc_data.get("persistent", False):
                logger.info(f"Keeping persistent NPC: {npc_id}")
                continue

            if npc_data.get("encounter_id") == encounter_id:
                to_remove.append(npc_id)

        for npc_id in to_remove:
            del self.active_npcs[npc_id]
            logger.info(f"Cleaned up NPC: {npc_id}")
```

### Data File Structure (Updated)

```
data/
├── npc_templates/              # Dynamic templates
│   ├── voidbringer_soldier.json
│   ├── voidbringer_archer.json
│   └── bandit_thug.json
│
├── static_npcs/                # Hand-crafted NPCs
│   ├── moash_betrayer.json
│   ├── amaram_highlord.json
│   ├── szeth_truthless.json
│   └── kaladin_stormblessed.json  (if NPC in other player's game)
│
├── encounters/
│   ├── caravan_ambush_001.json      (dynamic only)
│   ├── moash_ambush_001.json        (static + dynamic mix)
│   └── boss_fight_amaram.json       (static boss only)
│
└── current_campaign/
    └── shards_of_honor.json
```

---

## Use Cases by NPC Type

### Dynamic NPCs - When to Use
- ✅ Generic enemy groups (3-10 bandits)
- ✅ Scaling encounters (adjust to party strength)
- ✅ Random encounters (wilderness patrol)
- ✅ Mass combat (army battles)
- ✅ Disposable enemies (won't appear again)

### Static NPCs - When to Use
- ✅ Named villains (Moash, Amaram, Szeth)
- ✅ Important allies (Dalinar, Adolin, Shallan)
- ✅ Recurring characters (same merchant in every town)
- ✅ Unique mechanics (custom abilities/tactics)
- ✅ Story-critical NPCs (must survive/die at specific point)

### Hybrid - When to Use
- ✅ Boss + minions (Moash + 4 Voidbringers)
- ✅ Elite variants (Captain = static, soldiers = dynamic)
- ✅ Scaling bosses (static base + level modifier)

---

## Benefits of Unified System

1. **Same Pipeline:** Static and dynamic NPCs use identical code paths
2. **Mix and Match:** One encounter can have both types
3. **Lifecycle Management:** All NPCs tracked the same way
4. **Easy Authoring:** Choose approach based on NPC importance
5. **Performance:** Only generate what's needed (static NPCs skip generation)
6. **Flexibility:** Convert dynamic → static if NPC becomes important

---

## Implementation Checklist

- [ ] Create `components/npc_template.py` (StatRange, NPCTemplate)
- [ ] Create `components/npc_generator.py` (NPCGenerator with static NPC support)
- [ ] Extend `components/character_manager.py` (add_npc_from_data, remove_npcs_by_encounter, persistent flag)
- [ ] Add NPCGenerator to `core/game_initialization.py`
- [ ] Add encounter methods to `components/game_engine.py`
- [ ] Create `data/npc_templates/` directory with sample templates
- [ ] Create `data/static_npcs/` directory with sample static NPCs
- [ ] Create `data/encounters/` directory with sample encounters (both types)
- [ ] Update `DnDEngineWrapper._sync_characters_to_entities()` to handle NPC cleanup
- [ ] Create integration tests for both NPC types
- [ ] Add encounter trigger logic to `haystack_dnd_game.py`

---

**Status:** Design Complete - Ready for Implementation (Phase 3+)
