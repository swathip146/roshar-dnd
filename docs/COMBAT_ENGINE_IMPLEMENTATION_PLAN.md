# Combat Engine Implementation Plan
**Version:** 3.0 (Complete Rewrite)
**Date:** 2026-01-03
**Status:** Design Complete - Ready for Implementation

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Analysis of Previous Plans](#analysis-of-previous-plans)
3. [Combat System Architecture](#combat-system-architecture)
4. [Implementation Phases](#implementation-phases)
5. [File Structure](#file-structure)
6. [Component Specifications](#component-specifications)
7. [Integration Points](#integration-points)
8. [Testing Strategy](#testing-strategy)
9. [Success Metrics](#success-metrics)

---

## Executive Summary

This plan provides a comprehensive combat engine implementation that runs combat as a **single atomic operation** within one pipeline call. Combat is self-contained, managing its own turn loop internally without returning to the orchestrator between turns.

### Key Design Principles

1. **Single Combat Session** - Combat pipeline handles entire encounter from start to finish
2. **Internal Turn Loop** - Combat agent manages all turns, gets player input directly
3. **Self-Contained State** - No reliance on orchestrator between combat turns
4. **Leverage Existing DnDEngineWrapper** - Phase 2 integration complete, use it
5. **NPC Management via LLM+RAG** - Intelligent NPC stat generation from scenario text
6. **Modular Design** - Each file <1000 lines, single responsibility
7. **Comprehensive Testing** - Unit tests, integration tests, end-to-end tests
8. **🆕 Haystack + Pydantic Architecture** - Use existing Haystack 2.0 with Pydantic validation for structured output

### Architecture Decision: Haystack 2.0 + Pydantic Validation ✅

**Rationale:** After evaluating Haystack 2.0 vs LangChain (see `COMBAT_AGENT_ARCHITECTURE_DECISION.md`), we chose to:
- ✅ **Continue with Haystack 2.0** - Consistency with 4 existing agents, zero migration cost
- ✅ **Add Pydantic validation** - Get structured output benefits without framework migration
- ✅ **Best of both worlds** - Haystack's simplicity + Pydantic's type safety

**Key Benefits:**
- **Zero Migration Risk** - No need to rewrite 4 existing agents
- **Consistency** - Same patterns as MainInterfaceAgent, ScenarioGeneratorAgent, RAGRetrieverAgent, NPCControllerAgent
- **Type Safety** - Pydantic models enforce correct JSON schema from LLM
- **Faster Development** - 10 days vs 18 days with LangChain migration
- **Team Productivity** - No learning curve, proven infrastructure

### Core Architectural Difference from Previous Plan

**❌ Old Approach (Wrong):**
```
Turn 1: User → Orchestrator → Combat Pipeline → Attack → Return
Turn 2: User → Orchestrator → Combat Pipeline → Attack → Return
Turn 3: User → Orchestrator → Combat Pipeline → Attack → Return
```

**✅ New Approach (Correct):**
```
User triggers combat → Combat Pipeline TAKES OVER
    ↓
Combat Pipeline runs complete combat:
    - Initialize (NPCs, initiative)
    - Turn Loop (player input collected internally)
    - Combat End (cleanup)
    ↓
Single return → Back to main game loop
```

### Implementation Timeline

- **Phase 1 (Foundation):** 2-3 days - NPC stat generation system
- **Phase 2 (Combat Init):** 2-3 days - Combat initialization with initiative
- **Phase 3 (Combat Session):** 4-5 days - Self-contained combat loop
- **Phase 4 (Polish):** 2-3 days - Narrative, UI, testing

**Total Estimated Time:** 10-14 days

---

## Analysis of Previous Plans

### Your Combat_Engine_plan.md

#### ✅ Advantages

1. **Three-Phase Structure** - Clear separation: Init → Turns → End
2. **Single Combat Session** - Combat runs to completion in one call
3. **Deterministic NPC Loading** - Prioritizes predefined NPCs from quest data
4. **LLM-Based NPC Generation** - For undefined enemies with RAG support
5. **Combat End Conditions** - Multiple win conditions (all hostile dead, objective achieved)
6. **Character Entity Tracking** - Uses dnd_engine Entity system properly
7. **Internal Turn Loop** - Player input collected inside combat, not via orchestrator
8. **AI-Controlled NPCs** - Separate logic for NPC actions with validation

#### ✅ What We're Keeping

- Single combat session approach
- Three-phase structure (Init → Loop → End)
- NPC generation via LLM+RAG
- Internal turn management
- Direct player input during combat

### Previous Integration Plans - What Was Wrong

#### ❌ DND_ENGINE_INTEGRATION_GUIDE.md Problem

**Issue:** Treated combat as multiple orchestrator calls per turn
```python
# Wrong - returns after every action
def process_combat_action(self, combat_request: RequestDTO):
    result = dnd_wrapper.execute_attack()
    return result  # ❌ Returns to orchestrator
```

**Should Be:** Combat agent handles entire combat internally
```python
# Correct - completes entire combat
def run(self, dto: RequestDTO):
    combat_state = self.initialize_combat()

    while not combat_over:
        # Handle turns internally
        pass

    return final_result  # ✅ Returns after combat complete
```

---

## Combat System Architecture

### High-Level Flow

```
Player selects choice with combat_trigger=True
    ↓
HaystackDnDGame detects combat
    ↓
PipelineOrchestrator routes to combat_pipeline (ONE TIME)
    ↓
CombatAgent.run() TAKES OVER:
    │
    ├─ Phase 1: Combat Initialization
    │  - Parse enemies from scenario (LLM)
    │  - Generate NPC stats (LLM+RAG)
    │  - Add to CharacterManager
    │  - Sync to DnDEngineWrapper
    │  - Roll initiative
    │  - Display combat start
    │
    ├─ Phase 2: Combat Turn Loop (INTERNAL)
    │  │
    │  └─ while not combat_over:
    │      │
    │      ├─ Get current actor from initiative
    │      │
    │      ├─ If PLAYER turn:
    │      │  - Display combat status
    │      │  - Get input() directly (no orchestrator)
    │      │  - Parse action
    │      │  - Execute via DnDEngineWrapper
    │      │  - Generate narrative
    │      │  - Display immediately
    │      │
    │      └─ If NPC turn:
    │         - NPC AI decides action (LLM)
    │         - Execute via DnDEngineWrapper
    │         - Generate narrative
    │         - Display immediately
    │      │
    │      ├─ Update combat state
    │      ├─ Check end conditions
    │      └─ Advance turn
    │
    └─ Phase 3: Combat End
       - Display victory/defeat
       - Update character HP in CharacterManager
       - Remove NPCs from CharacterManager
       - Mark combat as ended in GameEngine
       - Return combat_complete result
    ↓
GameResponseDTO returned (ONCE)
    ↓
Back to main game loop
```

### Component Architecture

```
components/combat/
├── combat_initializer.py       # Phase 1: Setup, NPC generation
├── combat_session_manager.py   # Phase 2: Internal turn loop
├── combat_action_resolver.py   # Phase 3: Attack/spell execution
├── combat_narrative_generator.py # Phase 4: Combat storytelling
└── npc_stat_generator.py       # NPC creation via LLM+RAG

agents/
└── combat_agent.py             # Main: Orchestrates entire combat session

tests/combat/
├── test_npc_stat_generator.py
├── test_combat_initializer.py
├── test_combat_session_manager.py
├── test_combat_action_resolver.py
└── test_combat_integration.py
```

### State Management

**GameEngine.game_state.combat_state:**
```python
{
    "in_combat": bool,
    "combat_id": str,
    "active_combatants": List[str],     # char_ids
    "initiative_order": List[Dict],      # [{char_id, initiative}, ...]
    "current_turn_index": int,
    "round_number": int,
    "combat_log": List[Dict],           # Full action history
    "combatant_states": Dict[str, Dict], # Per-combatant tracking
    "end_conditions": Dict[str, bool]
}
```

**Key Difference from Previous Plan:**
- Combat state is **managed entirely within CombatAgent.run()**
- No state persistence needed between orchestrator calls
- State only written to GameEngine at combat end

---

## Implementation Phases

### Phase 1: Foundation - NPC Stat Generation (2-3 days)

**Goal:** Create NPC stat generation system using LLM + RAG with Pydantic validation

**🆕 Architecture:** Haystack 2.0 + Pydantic for structured output validation

#### Deliverables

**1. components/combat/npc_stat_generator.py** (~450 lines)

```python
from pydantic import BaseModel, Field, validator
from typing import Dict, List, Any, Optional
from haystack.dataclasses import ChatMessage

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

    def __init__(self, llm, document_store):
        self.llm = llm  # Haystack GeminiChatGenerator
        self.document_store = document_store
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
        logger.info(f"Generating NPC stats: {npc_description} (CR {challenge_rating})")

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
- All 6 ability scores required (str, dex, con, int, wis, cha)
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
            logger.info(f"✅ Generated valid NPC: {npc.name} (AC {npc.armor_class}, HP {npc.hit_points['maximum']})")
            return npc.dict()

        except ValidationError as e:
            logger.warning(f"⚠️ Validation failed, attempting repair: {e}")
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
            logger.debug("Fixed: Renamed 'class' to 'character_class'")

        # Fix hit_points format
        if isinstance(npc_data.get("hit_points"), int):
            hp = npc_data["hit_points"]
            npc_data["hit_points"] = {
                "current": hp,
                "maximum": hp,
                "temporary": 0
            }
            logger.debug(f"Fixed: Converted hit_points from int to dict")
        elif isinstance(npc_data.get("hit_points"), dict):
            # Ensure all keys present
            hp = npc_data["hit_points"]
            hp.setdefault("temporary", 0)
            if "current" not in hp or "maximum" not in hp:
                max_hp = hp.get("maximum", hp.get("current", 10))
                hp["current"] = hp.get("current", max_hp)
                hp["maximum"] = max_hp
                logger.debug("Fixed: Added missing hit_points keys")

        # Fix skills format
        if isinstance(npc_data.get("skills"), list):
            # Convert list to dict
            skills_dict = {skill: True for skill in npc_data["skills"]}
            npc_data["skills"] = skills_dict
            logger.debug(f"Fixed: Converted skills from list to dict")
        elif not npc_data.get("skills"):
            npc_data["skills"] = {}

        # Validate and clamp ability scores
        if "ability_scores" in npc_data:
            for ability in ["strength", "dexterity", "constitution",
                          "intelligence", "wisdom", "charisma"]:
                if ability not in npc_data["ability_scores"]:
                    npc_data["ability_scores"][ability] = 10
                    logger.warning(f"Fixed: Added missing {ability} score (default 10)")
                else:
                    score = npc_data["ability_scores"][ability]
                    if score < 1:
                        npc_data["ability_scores"][ability] = 1
                        logger.warning(f"Fixed: Clamped {ability} to minimum 1")
                    elif score > 30:
                        npc_data["ability_scores"][ability] = 30
                        logger.warning(f"Fixed: Clamped {ability} to maximum 30")

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
            logger.warning(f"Fixed: Recalculated HP: {max_hp}")

        # Ensure minimum AC
        if npc_data.get("armor_class", 0) < 8:
            dex_mod = (npc_data["ability_scores"]["dexterity"] - 10) // 2
            npc_data["armor_class"] = 10 + dex_mod
            logger.warning(f"Fixed: Set minimum AC: {npc_data['armor_class']}")

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
            logger.warning("Fixed: Added default unarmed strike")

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
            logger.info(f"✅ Repair successful: {npc.name}")
            return npc.dict()
        except ValidationError as e:
            logger.error(f"❌ Repair failed: {e}")
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

    # ... rest of methods remain the same (RAG query, template loading, etc.)
```

**Key Improvements with Pydantic:**
- ✅ **Automatic Validation** - Pydantic ensures LLM output matches schema
- ✅ **Clear Error Messages** - Validation errors show exactly what's wrong
- ✅ **Type Safety** - Guaranteed correct data types
- ✅ **Field Aliases** - Support both "class" and "character_class"
- ✅ **Custom Validators** - Enforce D&D rules (ability scores 1-30, etc.)
- ✅ **Repair Logic** - Attempts to fix common LLM mistakes automatically

**2. CharacterManager Extension** (~50 lines)

**✅ Already Completed in Phase 0** - See `components/character_manager.py`

The following methods were added during format standardization:
- `add_npc()` - Adds NPC with unique ID generation
- `remove_npc()` - Removes NPC after combat
- `get_npcs()` - Returns list of NPC IDs

No additional work needed for Phase 1.

**3. NPC Templates JSON** (~200 lines)

**✅ Already Completed in Phase 0** - See `data/npc_templates.json` format in plan

Format was updated during Phase 0 to match CharacterData structure:
- Uses `"character_class"` (not `"class"`)
- `hit_points` as dict with current/maximum/temporary
- `skills` as dict (not list)
- `background` field added

Example template structure (to be created in `data/npc_templates.json`):

```json
{
  "goblin": {
    "name": "Goblin",
    "level": 1,
    "character_class": "Warrior",
    "race": "Goblin",
    "background": "Tribal Warrior",
    "ability_scores": {
      "strength": 8,
      "dexterity": 14,
      "constitution": 10,
      "intelligence": 10,
      "wisdom": 8,
      "charisma": 8
    },
    "hit_points": {"maximum": 7, "current": 7, "temporary": 0},
    "armor_class": 15,
    "proficiency_bonus": 2,
    "skills": {
      "stealth": true,
      "survival": true
    },
    "attacks": [
      {
        "name": "Scimitar",
        "attack_bonus": 4,
        "damage_dice": "1d6",
        "damage_bonus": 2,
        "damage_type": "slashing"
      },
      {
        "name": "Shortbow",
        "attack_bonus": 4,
        "damage_dice": "1d6",
        "damage_bonus": 2,
        "damage_type": "piercing"
      }
    ],
    "special_abilities": ["Nimble Escape"],
    "challenge_rating": 0.25
  },
  "bandit": {
    "name": "Bandit",
    "level": 1,
    "character_class": "Rogue",
    "race": "Human",
    "background": "Criminal",
    "ability_scores": {
      "strength": 11,
      "dexterity": 12,
      "constitution": 12,
      "intelligence": 10,
      "wisdom": 10,
      "charisma": 10
    },
    "hit_points": {"maximum": 11, "current": 11, "temporary": 0},
    "armor_class": 12,
    "proficiency_bonus": 2,
    "skills": {
      "stealth": true,
      "deception": true
    },
    "attacks": [
      {
        "name": "Scimitar",
        "attack_bonus": 3,
        "damage_dice": "1d6",
        "damage_bonus": 1,
        "damage_type": "slashing"
      },
      {
        "name": "Light Crossbow",
        "attack_bonus": 3,
        "damage_dice": "1d8",
        "damage_bonus": 1,
        "damage_type": "piercing"
      }
    ],
    "special_abilities": [],
    "challenge_rating": 0.125
  },
  "skeleton": {
    "name": "Skeleton",
    "level": 1,
    "character_class": "Warrior",
    "race": "Undead",
    "background": "Reanimated",
    "ability_scores": {
      "strength": 10,
      "dexterity": 14,
      "constitution": 15,
      "intelligence": 6,
      "wisdom": 8,
      "charisma": 5
    },
    "hit_points": {"maximum": 13, "current": 13, "temporary": 0},
    "armor_class": 13,
    "proficiency_bonus": 2,
    "skills": {},
    "attacks": [
      {
        "name": "Shortsword",
        "attack_bonus": 4,
        "damage_dice": "1d6",
        "damage_bonus": 2,
        "damage_type": "piercing"
      },
      {
        "name": "Shortbow",
        "attack_bonus": 4,
        "damage_dice": "1d6",
        "damage_bonus": 2,
        "damage_type": "piercing"
      }
    ],
    "special_abilities": ["Undead Fortitude"],
    "challenge_rating": 0.25
  },
  "wolf": {
    "name": "Wolf",
    "level": 1,
    "character_class": "Beast",
    "race": "Wolf",
    "background": "Wild",
    "ability_scores": {
      "strength": 12,
      "dexterity": 15,
      "constitution": 12,
      "intelligence": 3,
      "wisdom": 12,
      "charisma": 6
    },
    "hit_points": {"maximum": 11, "current": 11, "temporary": 0},
    "armor_class": 13,
    "proficiency_bonus": 2,
    "skills": {
      "perception": true,
      "stealth": true
    },
    "attacks": [
      {
        "name": "Bite",
        "attack_bonus": 4,
        "damage_dice": "2d4",
        "damage_bonus": 2,
        "damage_type": "piercing"
      }
    ],
    "special_abilities": ["Pack Tactics", "Keen Hearing and Smell"],
    "challenge_rating": 0.25
  },
  "guard": {
    "name": "Guard",
    "level": 2,
    "character_class": "Fighter",
    "race": "Human",
    "background": "Soldier",
    "ability_scores": {
      "strength": 13,
      "dexterity": 12,
      "constitution": 12,
      "intelligence": 10,
      "wisdom": 11,
      "charisma": 10
    },
    "hit_points": {"maximum": 16, "current": 16, "temporary": 0},
    "armor_class": 16,
    "proficiency_bonus": 2,
    "skills": {
      "athletics": true,
      "perception": true
    },
    "attacks": [
      {
        "name": "Spear",
        "attack_bonus": 3,
        "damage_dice": "1d6",
        "damage_bonus": 1,
        "damage_type": "piercing"
      }
    ],
    "special_abilities": [],
    "challenge_rating": 0.125
  }
}
```

**4. Tests** (~300 lines)

```python
# tests/combat/test_npc_stat_generator.py

import pytest
from components.combat.npc_stat_generator import NPCStatGenerator
from unittest.mock import Mock, MagicMock

@pytest.fixture
def llm_mock():
    """Mock LLM for testing"""
    llm = Mock()
    response = Mock()
    response.content = """```json
{
    "name": "Goblin Warrior",
    "level": 1,
    "class": "Warrior",
    "race": "Goblin",
    "ability_scores": {
        "strength": 8,
        "dexterity": 14,
        "constitution": 10,
        "intelligence": 10,
        "wisdom": 8,
        "charisma": 8
    },
    "hit_points": {"maximum": 7, "current": 7},
    "armor_class": 15,
    "proficiency_bonus": 2,
    "attacks": [
        {
            "name": "Scimitar",
            "attack_bonus": 4,
            "damage_dice": "1d6",
            "damage_bonus": 2,
            "damage_type": "slashing"
        }
    ],
    "special_abilities": ["Nimble Escape"],
    "challenge_rating": 0.25
}
```"""
    llm.generate.return_value = response
    return llm

@pytest.fixture
def npc_generator(llm_mock):
    """Create NPCStatGenerator with mocked LLM"""
    return NPCStatGenerator(llm=llm_mock, document_store=None)

def test_generate_goblin_stats(npc_generator):
    """Test NPC generation for goblin"""
    npc = npc_generator.generate_npc_stats(
        npc_description="A small goblin warrior with a rusty scimitar",
        challenge_rating=0.25,
        role="combatant",
        context={"party_level": 1}
    )

    assert npc["name"] == "Goblin Warrior"
    assert npc["level"] == 1
    assert npc["ability_scores"]["dexterity"] == 14
    assert npc["hit_points"]["maximum"] == 7
    assert npc["armor_class"] == 15
    assert len(npc["attacks"]) == 1
    assert npc["attacks"][0]["name"] == "Scimitar"

def test_validate_and_repair_invalid_stats(npc_generator):
    """Test stat validation and repair"""
    invalid_npc = {
        "name": "Test NPC",
        "ability_scores": {
            "strength": 50,  # Invalid (too high)
            "dexterity": -5,  # Invalid (too low)
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10
        },
        "hit_points": {"maximum": -5, "current": -5},  # Invalid (negative)
        "armor_class": 0,  # Invalid (too low)
        "attacks": []  # Missing attacks
    }

    repaired = npc_generator.validate_and_repair(invalid_npc, target_cr=1)

    # Verify repairs
    assert repaired["ability_scores"]["strength"] == 30  # Clamped
    assert repaired["ability_scores"]["dexterity"] == 1  # Clamped
    assert repaired["hit_points"]["maximum"] > 0  # Fixed
    assert repaired["armor_class"] >= 8  # Fixed
    assert len(repaired["attacks"]) >= 1  # Added default

def test_load_template(npc_generator):
    """Test loading predefined NPC template"""
    # Mock templates
    npc_generator.templates = {
        "goblin": {
            "name": "Goblin",
            "armor_class": 15,
            "hit_points": {"maximum": 7, "current": 7}
        }
    }

    goblin = npc_generator.get_npc_from_template("goblin")

    assert goblin is not None
    assert goblin["name"] == "Goblin"
    assert goblin["armor_class"] == 15

def test_template_not_found(npc_generator):
    """Test handling of missing template"""
    result = npc_generator.get_npc_from_template("dragon")
    assert result is None

def test_parse_json_with_code_block(npc_generator):
    """Test parsing JSON from markdown code block"""
    response = """```json
{
    "name": "Test",
    "level": 1
}
```"""

    parsed = npc_generator._parse_json_response(response)
    assert parsed["name"] == "Test"
    assert parsed["level"] == 1

def test_parse_json_fallback(npc_generator):
    """Test fallback when JSON parsing fails"""
    response = "Invalid JSON {{{{"

    parsed = npc_generator._parse_json_response(response)

    # Should return fallback dict
    assert parsed["name"] == "Unknown NPC"
    assert parsed["level"] == 1
    assert "ability_scores" in parsed
```

---

### Phase 2: Combat Initialization (2-3 days)

**Goal:** Create combat state initialization system with NPC loading and initiative

#### Deliverables

**1. components/combat/combat_initializer.py** (~600 lines)

```python
class CombatInitializer:
    """
    Initializes combat state from scenario context.

    Process:
    1. Parse scenario for combat trigger and enemy descriptions
    2. Extract enemy info from scene + gm_notes using LLM
    3. Check for predefined NPCs in campaign data
    4. Generate stats for undefined NPCs via NPCStatGenerator
    5. Add all NPCs to CharacterManager
    6. Sync entities to DnDEngineWrapper
    7. Roll initiative for all combatants
    8. Create combat_state dict
    """

    def __init__(
        self,
        game_engine,
        character_manager,
        dnd_engine_wrapper,
        npc_stat_generator,
        llm
    ):
        self.game_engine = game_engine
        self.character_manager = character_manager
        self.dnd_wrapper = dnd_engine_wrapper
        self.npc_generator = npc_stat_generator
        self.llm = llm
        self.logger = get_logger(__name__)

    def initialize_combat(
        self,
        scenario: Dict[str, Any],
        player_character_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Initialize combat from scenario.

        Args:
            scenario: Scenario dict with scene, choices, gm_notes
            player_character_ids: List of PC char_ids participating

        Returns:
            combat_state: Initialized combat state dict
        """
        self.logger.info("⚔️ Initializing combat...")

        # Step 1: Check if combat should trigger
        if not self._should_trigger_combat(scenario):
            self.logger.warning("No combat trigger found in scenario")
            return None

        # Step 2: Parse enemies from scenario text
        enemies = self._parse_enemies_from_scenario(scenario)
        self.logger.info(f"Parsed {len(enemies)} enemy types from scenario")

        # Step 3: Load predefined NPCs from campaign
        predefined_npc_ids = self._load_predefined_npcs(enemies)
        self.logger.info(f"Loaded {len(predefined_npc_ids)} predefined NPCs")

        # Step 4: Generate undefined NPCs
        generated_npc_ids = self._generate_undefined_npcs(enemies, player_character_ids)
        self.logger.info(f"Generated {len(generated_npc_ids)} new NPCs")

        # Step 5: Sync all to DnDEngineWrapper
        self.dnd_wrapper._sync_characters_to_entities()
        self.logger.info("Synced all combatants to dnd_engine entities")

        # Step 6: Roll initiative
        all_combatant_ids = player_character_ids + predefined_npc_ids + generated_npc_ids
        initiative_order = self._roll_initiative(all_combatant_ids)
        self.logger.info(f"Initiative order: {[f'{entry['char_id']}({entry['initiative']})' for entry in initiative_order]}")

        # Step 7: Create combat state
        combat_state = {
            "in_combat": True,
            "combat_id": str(uuid.uuid4()),
            "active_combatants": all_combatant_ids,
            "initiative_order": initiative_order,
            "current_turn_index": 0,
            "round_number": 1,
            "combat_log": [],
            "combatant_states": self._initialize_combatant_states(all_combatant_ids),
            "end_conditions": self._determine_end_conditions(
                player_character_ids,
                predefined_npc_ids + generated_npc_ids
            )
        }

        self.logger.info("✅ Combat initialization complete")
        return combat_state

    def _should_trigger_combat(self, scenario: Dict) -> bool:
        """Check if any choice has combat_trigger=True"""
        return any(
            choice.get('combat_trigger', False)
            for choice in scenario.get('choices', [])
        )

    def _parse_enemies_from_scenario(self, scenario: Dict) -> List[Dict]:
        """
        Extract enemy information from scenario using LLM parsing.

        Scenarios don't have structured enemy data. Instead:
        - scenario['scene']: Narrative text mentioning enemies
        - scenario['gm_notes']: DM notes describing enemies
        - scenario['choices'][*]['combat_trigger']: Boolean flag

        Process:
        1. Combine scene + gm_notes text
        2. Use LLM to extract structured enemy data
        3. Return list of enemy dicts with name, count, CR

        Returns:
            [
                {
                    "name": "Goblin Warrior",
                    "description": "small goblin with rusty scimitar",
                    "count": 2,
                    "estimated_cr": 0.25,
                    "role": "combatant",
                    "keywords": ["goblin", "warrior", "scimitar"],
                    "is_predefined": False
                }
            ]
        """
        scene_text = scenario.get('scene', '')
        gm_notes = scenario.get('gm_notes', '')
        combined_text = f"Scene: {scene_text}\n\nGM Notes: {gm_notes}"

        # LLM prompt to extract enemy data
        system_prompt = """You are a D&D combat analyzer. Extract enemy/hostile creature information from scenario text.

Output JSON array with enemies:
[
    {
        "name": "Goblin Warrior",
        "description": "small goblin with rusty scimitar",
        "count": 2,
        "estimated_cr": 0.25,
        "role": "combatant|minion|boss|support",
        "keywords": ["goblin", "warrior", "scimitar"],
        "is_predefined": false
    }
]

Rules:
- Extract enemy type, count, and description
- Estimate CR based on description (goblin=0.25, bandit=0.125, guard=0.125, etc.)
- Role: combatant (normal), minion (weak), boss (strong), support (healer/buffer)
- Keywords: words that might match templates or campaign NPCs
- is_predefined: true if named NPC mentioned (e.g., "Captain Kholinar"), false otherwise

If no enemies mentioned, return empty array: []"""

        user_prompt = f"""Extract enemy information from this D&D scenario:

{combined_text}

Return JSON array of enemies:"""

        response = self.llm.generate(
            messages=[
                ChatMessage.from_system(system_prompt),
                ChatMessage.from_user(user_prompt)
            ],
            temperature=0.1
        )

        # Parse JSON
        try:
            enemies = json.loads(response.content.strip())
            if not isinstance(enemies, list):
                enemies = []
        except json.JSONDecodeError:
            self.logger.warning("Failed to parse enemies from LLM response")
            enemies = []

        return enemies

    def _load_predefined_npcs(self, enemies: List[Dict]) -> List[str]:
        """
        Load NPCs from campaign data if they match enemy names.

        Checks:
        1. CampaignConfig.key_npcs for name matches
        2. If enemy is_predefined=True

        Returns:
            List of char_ids for predefined NPCs added to CharacterManager
        """
        predefined_ids = []
        campaign_npcs = self.game_engine.campaign_config.key_npcs

        for enemy in enemies:
            if not enemy.get('is_predefined', False):
                continue

            # Look for matching campaign NPC
            enemy_name_lower = enemy['name'].lower()

            for campaign_npc in campaign_npcs:
                npc_name_lower = campaign_npc['name'].lower()

                if npc_name_lower in enemy_name_lower or enemy_name_lower in npc_name_lower:
                    # Found match - check if has full stats
                    if 'stats' in campaign_npc:
                        # Add to CharacterManager
                        char_id = self.character_manager.add_npc(campaign_npc['stats'])
                        predefined_ids.append(char_id)

                        self.logger.info(f"Loaded predefined NPC: {campaign_npc['name']} ({char_id})")

                        # Mark as processed
                        enemy['processed'] = True
                        break

        return predefined_ids

    def _generate_undefined_npcs(
        self,
        enemies: List[Dict],
        player_character_ids: List[str]
    ) -> List[str]:
        """
        Generate NPC stats for undefined enemies.

        For each enemy not processed by _load_predefined_npcs:
        1. Generate stats via NPCStatGenerator
        2. Create multiple instances if count > 1
        3. Add to CharacterManager

        Returns:
            List of char_ids for generated NPCs
        """
        generated_ids = []

        # Get party level for CR balancing
        party_level = self._get_party_level(player_character_ids)

        for enemy in enemies:
            if enemy.get('processed', False):
                continue  # Skip predefined NPCs

            count = enemy.get('count', 1)

            # Generate stats once
            npc_stats = self.npc_generator.generate_npc_stats(
                npc_description=enemy['description'],
                challenge_rating=enemy.get('estimated_cr', 0.5),
                role=enemy.get('role', 'combatant'),
                context={
                    'party_level': party_level,
                    'enemy_count': count
                }
            )

            # Create multiple instances
            for i in range(count):
                # Add to CharacterManager
                char_id = self.character_manager.add_npc(npc_stats)
                generated_ids.append(char_id)

                self.logger.info(f"Generated NPC {i+1}/{count}: {char_id} ({npc_stats['name']})")

        return generated_ids

    def _roll_initiative(self, combatant_ids: List[str]) -> List[Dict]:
        """
        Roll initiative for all combatants using DnDEngineWrapper.

        Returns sorted list (high to low):
        [
            {"char_id": "aggi", "initiative": 18},
            {"char_id": "goblin_001", "initiative": 15},
            ...
        ]
        """
        from dnd.enums import RollType

        initiative_rolls = []

        for char_id in combatant_ids:
            entity = self.dnd_wrapper.entities[char_id]

            # Get DEX modifier
            dex_mod = entity.ability_modifier("dexterity")

            # Roll d20 + DEX mod
            roll_result = entity.roll_d20(dex_mod, RollType.CHECK)

            initiative_rolls.append({
                "char_id": char_id,
                "initiative": roll_result.total
            })

            self.logger.debug(f"{char_id} initiative: {roll_result.total} (d20={roll_result.natural_roll} + {dex_mod})")

        # Sort by initiative (high to low)
        initiative_rolls.sort(key=lambda x: x['initiative'], reverse=True)

        return initiative_rolls

    def _initialize_combatant_states(self, combatant_ids: List[str]) -> Dict:
        """
        Create per-combatant state tracking.

        Returns:
            {
                "aggi": {
                    "hp_current": 25,
                    "hp_max": 25,
                    "conditions": [],
                    "actions_remaining": 1,
                    "bonus_actions_remaining": 1,
                    "reaction_available": True,
                    "is_hostile": False
                },
                "goblin_001": {
                    "hp_current": 7,
                    "hp_max": 7,
                    ...
                    "is_hostile": True
                }
            }
        """
        states = {}

        for char_id in combatant_ids:
            character = self.character_manager.characters[char_id]

            # Determine if hostile (NPCs are hostile by default)
            is_npc = any(char_id.endswith(f"_{i:03d}") for i in range(1, 100))

            states[char_id] = {
                "hp_current": character.hit_points,
                "hp_max": character.max_hit_points,
                "conditions": [],
                "actions_remaining": 1,
                "bonus_actions_remaining": 1,
                "reaction_available": True,
                "is_hostile": is_npc  # NPCs are hostile, PCs are not
            }

        return states

    def _determine_end_conditions(
        self,
        player_ids: List[str],
        npc_ids: List[str]
    ) -> Dict[str, bool]:
        """
        Determine combat victory/defeat conditions.

        Default conditions:
        - all_hostiles_defeated: All NPCs at 0 HP
        - all_players_defeated: All PCs at 0 HP
        """
        return {
            "all_hostiles_defeated": False,
            "all_players_defeated": False,
            "objective_achieved": False,
            "fled": False
        }

    def _get_party_level(self, player_character_ids: List[str]) -> int:
        """Get average party level for CR balancing"""
        if not player_character_ids:
            return 1

        levels = [
            self.character_manager.characters[cid].level
            for cid in player_character_ids
        ]

        return sum(levels) // len(levels)
```

**2. Tests** (~400 lines)

```python
# tests/combat/test_combat_initializer.py

def test_initialize_combat_with_goblins():
    """Test combat initialization with goblins extracted from scenario"""
    scenario = {
        "scene": "Two goblins leap out from behind rocks, scimitars drawn!",
        "gm_notes": "Two goblin warriors (CR 1/4 each). Armed with scimitars. Fight until half HP.",
        "choices": [
            {
                "id": "c1",
                "title": "Fight the goblins **Combat**",
                "combat_trigger": True
            },
            {
                "id": "c2",
                "title": "Try to flee",
                "combat_trigger": False
            }
        ]
    }

    initializer = CombatInitializer(
        game_engine=game_engine,
        character_manager=character_manager,
        dnd_engine_wrapper=dnd_wrapper,
        npc_stat_generator=npc_generator,
        llm=llm_mock
    )

    combat_state = initializer.initialize_combat(
        scenario=scenario,
        player_character_ids=["aggi"]
    )

    # Verify combat state created
    assert combat_state is not None
    assert combat_state["in_combat"] == True
    assert len(combat_state["active_combatants"]) == 3  # 1 PC + 2 NPCs
    assert len(combat_state["initiative_order"]) == 3
    assert combat_state["round_number"] == 1

    # Verify goblins extracted and generated
    goblin_ids = [cid for cid in combat_state["active_combatants"] if "goblin" in cid]
    assert len(goblin_ids) == 2

def test_predefined_npc_loading():
    """Test loading predefined NPC from campaign"""
    # Setup campaign with Captain Kholinar
    campaign_config.key_npcs = [
        {
            "name": "Captain Kholinar",
            "role": "Antagonist",
            "stats": {
                "name": "Captain Kholinar",
                "level": 5,
                "class": "Fighter",
                "ability_scores": {"strength": 16, "dexterity": 14, "constitution": 14,
                                   "intelligence": 10, "wisdom": 12, "charisma": 13},
                "hit_points": {"maximum": 45, "current": 45},
                "armor_class": 18,
                "proficiency_bonus": 3,
                "attacks": [{"name": "Longsword", "attack_bonus": 6, "damage_dice": "1d8",
                            "damage_bonus": 3, "damage_type": "slashing"}]
            }
        }
    ]

    scenario = {
        "scene": "Captain Kholinar blocks your path, hand on sword hilt.",
        "gm_notes": "Captain Kholinar (level 5 fighter) is hostile. Will fight to defend his position.",
        "choices": [{"id": "c1", "combat_trigger": True}]
    }

    combat_state = initializer.initialize_combat(scenario, ["aggi"])

    # Verify Captain loaded from campaign, not generated
    captain_ids = [cid for cid in combat_state["active_combatants"] if "kholinar" in cid.lower()]
    assert len(captain_ids) == 1

    # Verify stats match campaign data
    captain_id = captain_ids[0]
    captain_char = character_manager.characters[captain_id]
    assert captain_char.level == 5
    assert captain_char.char_class == "Fighter"

def test_initiative_order_sorted():
    """Test initiative rolls are sorted high to low"""
    scenario = {
        "scene": "Combat begins!",
        "choices": [{"combat_trigger": True}],
        "gm_notes": "One goblin"
    }

    combat_state = initializer.initialize_combat(scenario, ["aggi"])

    initiatives = [entry["initiative"] for entry in combat_state["initiative_order"]]
    assert initiatives == sorted(initiatives, reverse=True)

def test_no_combat_trigger():
    """Test combat doesn't initialize if no combat_trigger"""
    scenario = {
        "scene": "You see a peaceful village.",
        "choices": [
            {"id": "c1", "title": "Enter village", "combat_trigger": False}
        ]
    }

    combat_state = initializer.initialize_combat(scenario, ["aggi"])
    assert combat_state is None
```

---

### Phase 3: Combat Session Manager (4-5 days)

**Goal:** Implement self-contained combat loop that handles all turns internally

**This is the CRITICAL phase that differs from previous plan.**

#### Deliverables

**1. components/combat/combat_session_manager.py** (~700 lines)

```python
class CombatSessionManager:
    """
    Manages internal combat turn loop.

    IMPORTANT: This runs INSIDE CombatAgent.run() and handles
    ALL combat turns without returning to orchestrator.

    Responsibilities:
    - Run combat turn loop
    - Get player input directly (input() calls)
    - Execute NPC AI actions
    - Advance turns
    - Check end conditions
    - Display combat status after each turn
    """

    def __init__(
        self,
        combat_state: Dict[str, Any],
        game_engine,
        character_manager,
        dnd_engine_wrapper,
        combat_action_resolver,
        combat_narrative_generator,
        npc_ai_agent
    ):
        self.combat_state = combat_state
        self.game_engine = game_engine
        self.character_manager = character_manager
        self.dnd_wrapper = dnd_engine_wrapper
        self.action_resolver = combat_action_resolver
        self.narrative_gen = combat_narrative_generator
        self.npc_ai = npc_ai_agent
        self.logger = get_logger(__name__)

    def run_combat_loop(self) -> Dict[str, Any]:
        """
        Run complete combat from start to finish.

        Process:
        1. Display combat start
        2. Loop through turns until combat ends
        3. Return final combat result

        Returns:
            {
                "outcome": "victory|defeat|fled",
                "rounds": 5,
                "combat_log": [...],
                "final_states": {...}
            }
        """
        self.logger.info("🗡️ Combat loop starting...")

        # Display combat start
        self._display_combat_start()

        # Main combat loop
        while not self._is_combat_over():
            # Get current actor
            current_actor_id = self._get_current_actor()

            # Execute turn based on actor type
            if self._is_player(current_actor_id):
                self._execute_player_turn(current_actor_id)
            else:
                self._execute_npc_turn(current_actor_id)

            # Check if combatant has more actions
            if not self._has_actions_remaining(current_actor_id):
                # Advance to next combatant
                self._advance_turn()

        # Combat ended
        outcome = self._determine_outcome()
        self.logger.info(f"⚔️ Combat ended: {outcome}")

        return {
            "outcome": outcome,
            "rounds": self.combat_state["round_number"],
            "combat_log": self.combat_state["combat_log"],
            "final_states": self.combat_state["combatant_states"]
        }

    def _execute_player_turn(self, player_char_id: str):
        """
        Execute player's turn by getting input directly.

        Process:
        1. Display combat status
        2. Show available actions
        3. Get input() from player
        4. Parse action
        5. Validate action
        6. Execute via action resolver
        7. Generate and display narrative
        8. Update combat state
        """
        self.logger.info(f"🎮 Player turn: {player_char_id}")

        # Display status
        print("\n" + "="*60)
        print(self.narrative_gen.generate_combat_status(self.combat_state))
        print("="*60)

        # Get available actions
        available_actions = self._get_available_actions(player_char_id)

        # Display actions
        print("\n📋 Available Actions:")
        for i, action_desc in enumerate(available_actions, 1):
            print(f"  {i}. {action_desc}")

        # Get player input directly
        while True:
            try:
                choice = input(f"\n{player_char_id}> Choose action (1-{len(available_actions)}): ").strip()

                if not choice.isdigit():
                    print("❌ Please enter a number")
                    continue

                choice_idx = int(choice) - 1

                if choice_idx < 0 or choice_idx >= len(available_actions):
                    print(f"❌ Please choose 1-{len(available_actions)}")
                    continue

                # Parse action
                action = self._parse_action_choice(player_char_id, choice_idx, available_actions)
                break

            except (ValueError, KeyError) as e:
                print(f"❌ Invalid choice: {e}")

        # Validate action
        if not self._validate_action(action):
            print("❌ Action not valid in current state")
            return  # Try again

        # Execute action
        result = self.action_resolver.resolve_action(action)

        # Log action
        self._log_combat_action(action, result)

        # Generate narrative
        narrative = self.narrative_gen.generate_action_narrative(
            action=action,
            result=result,
            combat_state=self.combat_state
        )

        # Display narrative
        print(f"\n{narrative}")

        # Consume action
        self._consume_action(player_char_id, action["action_type"])

        self.logger.info(f"✅ Player action executed: {action['action_type']}")

    def _execute_npc_turn(self, npc_char_id: str):
        """
        Execute NPC's turn using AI decision.

        Process:
        1. Build context for NPC AI
        2. LLM decides action
        3. Validate action
        4. Execute action
        5. Generate and display narrative
        6. Update combat state
        """
        self.logger.info(f"🤖 NPC turn: {npc_char_id}")

        # Build context for AI
        context = self._build_npc_context(npc_char_id)

        # Get AI decision
        ai_decision = self.npc_ai.decide_action(context)

        # Convert to action dict
        action = {
            "actor": npc_char_id,
            "action_type": ai_decision["action_type"],
            "target": ai_decision.get("target"),
            "weapon": ai_decision.get("weapon"),
            "reasoning": ai_decision.get("reasoning", "")
        }

        # Validate
        if not self._validate_action(action):
            # Fallback to basic attack
            self.logger.warning(f"NPC AI action invalid, using fallback")
            action = self._get_fallback_action(npc_char_id)

        # Execute action
        result = self.action_resolver.resolve_action(action)

        # Log action
        self._log_combat_action(action, result)

        # Generate narrative
        narrative = self.narrative_gen.generate_action_narrative(
            action=action,
            result=result,
            combat_state=self.combat_state
        )

        # Display narrative
        print(f"\n{narrative}")

        # Consume action
        self._consume_action(npc_char_id, action["action_type"])

        self.logger.info(f"✅ NPC action executed: {action['action_type']}")

    def _get_available_actions(self, char_id: str) -> List[str]:
        """
        Get list of available actions for character.

        Returns human-readable action descriptions:
        [
            "Attack goblin_001 with longsword",
            "Attack goblin_002 with longsword",
            "Cast Healing Word on self",
            "Dodge",
            "Disengage"
        ]
        """
        actions = []
        char_state = self.combat_state["combatant_states"][char_id]
        character = self.character_manager.characters[char_id]

        # Attack actions (if have action remaining)
        if char_state["actions_remaining"] > 0:
            # Get all valid targets (hostile enemies)
            targets = self._get_valid_targets(char_id)

            for target_id in targets:
                target_char = self.character_manager.characters[target_id]
                target_hp = self.combat_state["combatant_states"][target_id]["hp_current"]

                actions.append(f"Attack {target_char.name} (HP: {target_hp}) with weapon")

            # Utility actions
            actions.extend([
                "Dodge (gain advantage on DEX saves, attacks against you have disadvantage)",
                "Dash (double movement speed)",
                "Disengage (move without opportunity attacks)",
                "Help (give ally advantage on next check)"
            ])

        # Bonus actions
        if char_state["bonus_actions_remaining"] > 0:
            # Add bonus action options if character has them
            # e.g., "Use Second Wind (bonus action)" for fighters
            pass

        return actions

    def _parse_action_choice(
        self,
        char_id: str,
        choice_idx: int,
        available_actions: List[str]
    ) -> Dict[str, Any]:
        """
        Parse player's numeric choice into action dict.

        Args:
            char_id: Actor char_id
            choice_idx: Index into available_actions
            available_actions: List of action descriptions

        Returns:
            {
                "actor": "aggi",
                "action_type": "attack",
                "target": "goblin_001",
                "weapon": "longsword"
            }
        """
        action_desc = available_actions[choice_idx]

        # Parse action description
        if action_desc.startswith("Attack "):
            # Extract target name
            import re
            match = re.search(r"Attack (.*?) \(", action_desc)
            if match:
                target_name = match.group(1)

                # Find target char_id
                target_id = self._find_char_id_by_name(target_name)

                # Get character's weapon
                character = self.character_manager.characters[char_id]
                weapon = self._get_equipped_weapon(character)

                return {
                    "actor": char_id,
                    "action_type": "attack",
                    "target": target_id,
                    "weapon": weapon
                }

        elif "Dodge" in action_desc:
            return {
                "actor": char_id,
                "action_type": "dodge"
            }

        elif "Dash" in action_desc:
            return {
                "actor": char_id,
                "action_type": "dash"
            }

        elif "Disengage" in action_desc:
            return {
                "actor": char_id,
                "action_type": "disengage"
            }

        elif "Help" in action_desc:
            return {
                "actor": char_id,
                "action_type": "help"
            }

        # Fallback
        return {
            "actor": char_id,
            "action_type": "dodge"
        }

    def _validate_action(self, action: Dict) -> bool:
        """Validate action is legal in current combat state"""
        actor_id = action["actor"]
        action_type = action["action_type"]

        # Check actor has actions remaining
        actor_state = self.combat_state["combatant_states"][actor_id]

        if action_type in ["attack", "dodge", "dash", "disengage", "help"]:
            if actor_state["actions_remaining"] <= 0:
                return False

        # Check target is valid (if targeting action)
        if "target" in action:
            target_id = action["target"]

            # Target must be in combat
            if target_id not in self.combat_state["active_combatants"]:
                return False

            # Target must be alive
            target_state = self.combat_state["combatant_states"][target_id]
            if target_state["hp_current"] <= 0:
                return False

        return True

    def _consume_action(self, char_id: str, action_type: str):
        """Mark action as consumed"""
        char_state = self.combat_state["combatant_states"][char_id]

        if action_type in ["attack", "dodge", "dash", "disengage", "help", "cast_spell"]:
            char_state["actions_remaining"] -= 1
        elif action_type in ["bonus_action_spell", "cunning_action"]:
            char_state["bonus_actions_remaining"] -= 1

    def _has_actions_remaining(self, char_id: str) -> bool:
        """Check if combatant has actions/bonus actions remaining"""
        char_state = self.combat_state["combatant_states"][char_id]
        return (char_state["actions_remaining"] > 0 or
                char_state["bonus_actions_remaining"] > 0)

    def _advance_turn(self):
        """
        Advance to next combatant in initiative order.

        Process:
        1. Increment current_turn_index
        2. If wrapped around, new round (reset action economy)
        3. Skip dead combatants
        """
        self.combat_state["current_turn_index"] += 1

        # Check if new round
        if self.combat_state["current_turn_index"] >= len(self.combat_state["initiative_order"]):
            self.combat_state["current_turn_index"] = 0
            self.combat_state["round_number"] += 1

            # Reset action economy for all combatants
            for char_state in self.combat_state["combatant_states"].values():
                char_state["actions_remaining"] = 1
                char_state["bonus_actions_remaining"] = 1
                char_state["reaction_available"] = True

            self.logger.info(f"🔄 Round {self.combat_state['round_number']} begins")
            print(f"\n{'='*60}")
            print(f"  🔄 ROUND {self.combat_state['round_number']}")
            print(f"{'='*60}")

        # Skip dead combatants
        while self._is_combatant_dead(self._get_current_actor()):
            self.combat_state["current_turn_index"] += 1

            if self.combat_state["current_turn_index"] >= len(self.combat_state["initiative_order"]):
                self.combat_state["current_turn_index"] = 0
                self.combat_state["round_number"] += 1

    def _is_combat_over(self) -> bool:
        """Check if combat should end"""
        ended, reason = self._check_end_conditions()

        if ended:
            self.combat_state["end_reason"] = reason
            return True

        return False

    def _check_end_conditions(self) -> Tuple[bool, Optional[str]]:
        """
        Check end conditions.

        Returns:
            (combat_ended: bool, reason: str)
        """
        # Check all hostiles defeated
        hostile_ids = [
            cid for cid, state in self.combat_state["combatant_states"].items()
            if state["is_hostile"]
        ]

        all_hostiles_dead = all(
            self.combat_state["combatant_states"][hid]["hp_current"] <= 0
            for hid in hostile_ids
        )

        if all_hostiles_dead:
            return (True, "all_hostiles_defeated")

        # Check all players defeated
        player_ids = [
            cid for cid, state in self.combat_state["combatant_states"].items()
            if not state["is_hostile"]
        ]

        all_players_dead = all(
            self.combat_state["combatant_states"][pid]["hp_current"] <= 0
            for pid in player_ids
        )

        if all_players_dead:
            return (True, "all_players_defeated")

        return (False, None)

    def _determine_outcome(self) -> str:
        """Determine combat outcome"""
        reason = self.combat_state.get("end_reason", "unknown")

        if reason == "all_hostiles_defeated":
            return "victory"
        elif reason == "all_players_defeated":
            return "defeat"
        elif reason == "fled":
            return "fled"
        else:
            return "unknown"

    def _get_current_actor(self) -> str:
        """Get char_id of current actor from initiative order"""
        idx = self.combat_state["current_turn_index"]
        return self.combat_state["initiative_order"][idx]["char_id"]

    def _is_player(self, char_id: str) -> bool:
        """Check if char_id is a player character"""
        return not self.combat_state["combatant_states"][char_id]["is_hostile"]

    def _is_combatant_dead(self, char_id: str) -> bool:
        """Check if combatant is at 0 HP"""
        return self.combat_state["combatant_states"][char_id]["hp_current"] <= 0

    def _log_combat_action(self, action: Dict, result: Dict):
        """Log action to combat log"""
        self.combat_state["combat_log"].append({
            "round": self.combat_state["round_number"],
            "actor": action["actor"],
            "action_type": action["action_type"],
            "target": action.get("target"),
            "result": result
        })

    def _display_combat_start(self):
        """Display combat start message"""
        print("\n" + "="*60)
        print("  ⚔️  COMBAT BEGINS!")
        print("="*60)

        # Show initiative order
        print("\n📊 Initiative Order:")
        for entry in self.combat_state["initiative_order"]:
            char_name = self.character_manager.characters[entry["char_id"]].name
            print(f"  {entry['initiative']}: {char_name}")

        print("\n" + "="*60)

    def _build_npc_context(self, npc_char_id: str) -> Dict:
        """Build context for NPC AI decision"""
        npc_char = self.character_manager.characters[npc_char_id]
        npc_state = self.combat_state["combatant_states"][npc_char_id]

        return {
            "npc": npc_char,
            "npc_hp": npc_state["hp_current"],
            "npc_max_hp": npc_state["hp_max"],
            "available_targets": self._get_valid_targets(npc_char_id),
            "available_actions": ["attack", "dodge", "disengage"],
            "allies": self._get_allies(npc_char_id),
            "enemies": self._get_enemies(npc_char_id),
            "round_number": self.combat_state["round_number"]
        }

    def _get_valid_targets(self, char_id: str) -> List[str]:
        """Get list of valid targets for character"""
        is_hostile = self.combat_state["combatant_states"][char_id]["is_hostile"]

        targets = []
        for cid, state in self.combat_state["combatant_states"].items():
            if cid == char_id:
                continue  # Can't target self

            if state["hp_current"] <= 0:
                continue  # Can't target dead

            # Hostiles target players, players target hostiles
            if is_hostile != state["is_hostile"]:
                targets.append(cid)

        return targets

    def _get_allies(self, char_id: str) -> List[str]:
        """Get list of allies (same hostility status)"""
        is_hostile = self.combat_state["combatant_states"][char_id]["is_hostile"]

        return [
            cid for cid, state in self.combat_state["combatant_states"].items()
            if cid != char_id and state["is_hostile"] == is_hostile
        ]

    def _get_enemies(self, char_id: str) -> List[str]:
        """Get list of enemies (opposite hostility status)"""
        return self._get_valid_targets(char_id)

    def _get_fallback_action(self, npc_char_id: str) -> Dict:
        """Get fallback action if AI decision fails"""
        targets = self._get_valid_targets(npc_char_id)

        if targets:
            return {
                "actor": npc_char_id,
                "action_type": "attack",
                "target": targets[0],  # Attack first valid target
                "weapon": "unarmed"
            }
        else:
            return {
                "actor": npc_char_id,
                "action_type": "dodge"
            }

    def _find_char_id_by_name(self, name: str) -> Optional[str]:
        """Find char_id by character name"""
        for char_id, character in self.character_manager.characters.items():
            if character.name == name:
                return char_id
        return None

    def _get_equipped_weapon(self, character) -> str:
        """Get character's equipped weapon"""
        if hasattr(character, 'attacks') and character.attacks:
            return character.attacks[0]["name"]
        return "unarmed"
```

**2. components/combat/combat_action_resolver.py** (~400 lines)

```python
class CombatActionResolver:
    """
    Resolves combat actions using DnDEngineWrapper.

    Supported Actions:
    - Attack (melee/ranged)
    - Dodge (advantage for attackers until next turn)
    - Dash (double movement - narrative only)
    - Help (give ally advantage)
    - Disengage (avoid opportunity attacks)
    """

    def __init__(self, dnd_engine_wrapper, character_manager):
        self.dnd_wrapper = dnd_engine_wrapper
        self.character_manager = character_manager
        self.logger = get_logger(__name__)

    def resolve_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve combat action.

        Args:
            action: {
                "actor": "aggi",
                "action_type": "attack",
                "target": "goblin_001",
                "weapon": "longsword"
            }

        Returns:
            result: {
                "action_type": "attack",
                "hit": True,
                "damage": 8,
                "target_hp_remaining": 0,
                "critical": False,
                ...
            }
        """
        action_type = action["action_type"]

        if action_type == "attack":
            return self._resolve_attack(action)
        elif action_type == "dodge":
            return self._resolve_dodge(action)
        elif action_type == "dash":
            return self._resolve_dash(action)
        elif action_type == "help":
            return self._resolve_help(action)
        elif action_type == "disengage":
            return self._resolve_disengage(action)
        else:
            self.logger.warning(f"Unknown action type: {action_type}")
            return {"success": False, "error": f"Unknown action: {action_type}"}

    def _resolve_attack(self, action: Dict) -> Dict:
        """
        Resolve attack using DnDEngineWrapper.

        Uses: dnd_wrapper.execute_attack(attacker_id, target_id, weapon)
        """
        result = self.dnd_wrapper.execute_attack(
            attacker_id=action["actor"],
            target_id=action["target"],
            weapon=action.get("weapon", "unarmed"),
            advantage=action.get("advantage", False),
            disadvantage=action.get("disadvantage", False)
        )

        self.logger.info(
            f"Attack: {action['actor']} → {action['target']}: "
            f"{'HIT' if result['hit'] else 'MISS'} "
            f"({result.get('damage', 0)} damage)"
        )

        return result

    def _resolve_dodge(self, action: Dict) -> Dict:
        """Resolve dodge action (narrative only for now)"""
        return {
            "action_type": "dodge",
            "success": True,
            "message": f"{action['actor']} focuses on defense"
        }

    def _resolve_dash(self, action: Dict) -> Dict:
        """Resolve dash action (narrative only)"""
        return {
            "action_type": "dash",
            "success": True,
            "message": f"{action['actor']} moves quickly"
        }

    def _resolve_help(self, action: Dict) -> Dict:
        """Resolve help action (narrative only)"""
        return {
            "action_type": "help",
            "success": True,
            "message": f"{action['actor']} assists an ally"
        }

    def _resolve_disengage(self, action: Dict) -> Dict:
        """Resolve disengage action (narrative only)"""
        return {
            "action_type": "disengage",
            "success": True,
            "message": f"{action['actor']} carefully withdraws"
        }
```

**3. components/combat/combat_narrative_generator.py** (~400 lines)

```python
class CombatNarrativeGenerator:
    """
    Generates vivid combat narratives from mechanical results.
    """

    def __init__(self, llm):
        self.llm = llm
        self.logger = get_logger(__name__)

    def generate_action_narrative(
        self,
        action: Dict[str, Any],
        result: Dict[str, Any],
        combat_state: Dict[str, Any]
    ) -> str:
        """
        Generate narrative for combat action.

        Returns 2-3 sentence vivid description with mechanical summary.
        """
        system_prompt = """You are a Dungeon Master narrating D&D combat.

Generate vivid, exciting combat descriptions (2-3 sentences max).

Include:
- Action description (swing, thrust, dodge, etc.)
- Environmental details (dust, blood, sparks)
- Emotional impact (fear, determination, pain)

Style: Brandon Sanderson's Stormlight Archive
Tone: Action-focused, concise, vivid"""

        user_prompt = f"""Narrate this combat action:

Actor: {action['actor']}
Action: {action['action_type']}
Target: {action.get('target', 'N/A')}

Result:
- Success: {result.get('hit', result.get('success', False))}
- Damage: {result.get('damage', 0)}
- Critical: {result.get('critical', False)}
- Target HP: {result.get('target_hp_remaining', 'N/A')}

Round: {combat_state['round_number']}

Generate 2-3 sentence narrative:"""

        response = self.llm.generate(
            messages=[
                ChatMessage.from_system(system_prompt),
                ChatMessage.from_user(user_prompt)
            ],
            temperature=0.7
        )

        narrative = response.content.strip()

        # Add mechanical summary
        if action["action_type"] == "attack":
            if result.get("hit"):
                narrative += f"\n💥 Hit! {result['damage']} damage dealt."
                if result.get("critical"):
                    narrative += " ⭐ CRITICAL HIT!"
            else:
                narrative += f"\n🎯 Miss! (Roll: {result.get('attack_roll', 0)} vs AC {result.get('target_ac', 0)})"

            if result.get("target_hp_remaining", 1) <= 0:
                narrative += f"\n💀 {action['target']} is defeated!"

        return narrative

    def generate_combat_status(self, combat_state: Dict) -> str:
        """
        Generate combat status display.

        Returns:

        === COMBAT STATUS ===
        Round: 3
        Current Turn: Aggi

        🟢 Allies:
          - Aggi (Lightweaver): 25/25 HP

        🔴 Enemies:
          - Goblin_001: 0/7 HP (defeated)
          - Goblin_002: 5/7 HP
        """
        status = "\n=== COMBAT STATUS ===\n"
        status += f"Round: {combat_state['round_number']}\n"

        current_idx = combat_state['current_turn_index']
        current_actor_id = combat_state['initiative_order'][current_idx]['char_id']
        status += f"Current Turn: {current_actor_id}\n\n"

        # Allies
        allies = [
            cid for cid, state in combat_state['combatant_states'].items()
            if not state['is_hostile']
        ]

        status += "🟢 Allies:\n"
        for ally_id in allies:
            state = combat_state['combatant_states'][ally_id]
            char = self.character_manager.characters.get(ally_id)
            char_name = char.name if char else ally_id

            status += f"  - {char_name}: {state['hp_current']}/{state['hp_max']} HP"
            if state['conditions']:
                status += f" ({', '.join(state['conditions'])})"
            status += "\n"

        # Enemies
        enemies = [
            cid for cid, state in combat_state['combatant_states'].items()
            if state['is_hostile']
        ]

        status += "\n🔴 Enemies:\n"
        for enemy_id in enemies:
            state = combat_state['combatant_states'][enemy_id]
            char = self.character_manager.characters.get(enemy_id)
            char_name = char.name if char else enemy_id

            status += f"  - {char_name}: {state['hp_current']}/{state['hp_max']} HP"
            if state['hp_current'] <= 0:
                status += " (defeated)"
            if state['conditions']:
                status += f" ({', '.join(state['conditions'])})"
            status += "\n"

        return status
```

**4. agents/npc_ai_agent.py** (~200 lines)

```python
@component
class NPCAIAgent:
    """
    LLM-based NPC combat AI.

    Decides NPC actions during combat.
    """

    def __init__(self, llm):
        self.llm = llm
        self.logger = get_logger(__name__)

    def decide_action(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decide NPC action based on tactical situation.

        Args:
            context: {
                "npc": CharacterData,
                "npc_hp": 5,
                "npc_max_hp": 7,
                "available_targets": ["aggi"],
                "available_actions": ["attack", "dodge"],
                "allies": [],
                "enemies": ["aggi"]
            }

        Returns:
            {
                "action_type": "attack",
                "target": "aggi",
                "weapon": "scimitar",
                "reasoning": "Target is only enemy, attack to deal damage"
            }
        """
        system_prompt = """You are a tactical combat AI for D&D NPCs.

Decide the most tactically sound action for the NPC.

Tactics:
- Low HP (<50%): Consider dodge/disengage
- Multiple enemies: Focus wounded targets
- Outnumbered: Defensive actions
- Strong position: Aggressive actions

Output JSON:
{
    "action_type": "attack|dodge|disengage",
    "target": "char_id" (if attack),
    "weapon": "weapon_name" (if attack),
    "reasoning": "brief tactical explanation"
}"""

        npc = context["npc"]
        hp_percent = (context["npc_hp"] / context["npc_max_hp"]) * 100

        user_prompt = f"""Decide action for NPC:

NPC: {npc.name}
HP: {context['npc_hp']}/{context['npc_max_hp']} ({hp_percent:.0f}%)

Targets: {context['available_targets']}
Actions: {context['available_actions']}
Allies: {len(context['allies'])}
Enemies: {len(context['enemies'])}

Decide action:"""

        response = self.llm.generate(
            messages=[
                ChatMessage.from_system(system_prompt),
                ChatMessage.from_user(user_prompt)
            ],
            temperature=0.3
        )

        # Parse JSON
        try:
            decision = json.loads(response.content.strip())
        except json.JSONDecodeError:
            # Fallback: attack first target
            decision = {
                "action_type": "attack",
                "target": context["available_targets"][0] if context["available_targets"] else None,
                "weapon": "unarmed",
                "reasoning": "Fallback action"
            }

        self.logger.info(f"NPC AI decision: {decision['action_type']} ({decision.get('reasoning', '')})")

        return decision
```

**5. Tests** (~600 lines)

See test section below for complete test implementations.

---

### Phase 4: Combat Agent & Integration (2-3 days)

**Goal:** Create main CombatAgent that orchestrates entire combat session

#### Deliverables

**1. agents/combat_agent.py** (~400 lines)

```python
@component
class CombatAgent:
    """
    Main combat orchestration agent.

    CRITICAL: This agent runs ENTIRE combat in one call.
    Does NOT return to orchestrator between turns.

    Process:
    1. Initialize combat (NPCs, initiative)
    2. Run combat loop (internal turn management)
    3. Clean up and return final result
    """

    def __init__(
        self,
        game_engine,
        character_manager,
        dnd_engine_wrapper,
        combat_initializer,
        combat_action_resolver,
        combat_narrative_generator,
        npc_ai_agent
    ):
        self.game_engine = game_engine
        self.character_manager = character_manager
        self.dnd_wrapper = dnd_engine_wrapper
        self.initializer = combat_initializer
        self.action_resolver = combat_action_resolver
        self.narrative_gen = combat_narrative_generator
        self.npc_ai = npc_ai_agent
        self.logger = get_logger(__name__)

    @component.output_types(response=Dict[str, Any])
    def run(self, dto: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute COMPLETE combat session.

        Args:
            dto: RequestDTO with:
                - scenario_context: Scenario with combat trigger
                - player_character_id: PC char_id

        Returns:
            GameResponseDTO with:
                - response_type: "combat_complete"
                - outcome: "victory"|"defeat"
                - rounds: 5
                - combat_log: [...]
        """
        self.logger.info("⚔️ CombatAgent.run() - Starting complete combat session")

        scenario = dto.get("scenario_context", {})
        player_char_id = dto.get("player_character_id", "")

        # Phase 1: Initialize Combat
        self.logger.info("Phase 1: Combat Initialization")
        combat_state = self.initializer.initialize_combat(
            scenario=scenario,
            player_character_ids=[player_char_id]
        )

        if combat_state is None:
            self.logger.warning("Combat initialization failed or no combat trigger")
            return {
                "response": {
                    "response_type": "error",
                    "message": "No combat to initialize"
                }
            }

        # Phase 2: Run Combat Loop
        self.logger.info("Phase 2: Combat Loop (internal turn management)")

        session_manager = CombatSessionManager(
            combat_state=combat_state,
            game_engine=self.game_engine,
            character_manager=self.character_manager,
            dnd_engine_wrapper=self.dnd_wrapper,
            combat_action_resolver=self.action_resolver,
            combat_narrative_generator=self.narrative_gen,
            npc_ai_agent=self.npc_ai
        )

        combat_result = session_manager.run_combat_loop()

        # Phase 3: Combat End & Cleanup
        self.logger.info("Phase 3: Combat Cleanup")
        self._cleanup_combat(combat_state)

        # Generate end narrative
        end_narrative = self._generate_end_narrative(combat_result)

        # Display to user
        print("\n" + "="*60)
        print(end_narrative)
        print("="*60)

        self.logger.info(f"✅ Combat complete: {combat_result['outcome']} in {combat_result['rounds']} rounds")

        # Update GameEngine
        self._update_game_engine(combat_result)

        return {
            "response": {
                "response_type": "combat_complete",
                "outcome": combat_result["outcome"],
                "rounds": combat_result["rounds"],
                "combat_log": combat_result["combat_log"],
                "narrative": end_narrative
            }
        }

    def _cleanup_combat(self, combat_state: Dict):
        """
        Clean up after combat.

        - Remove NPCs from CharacterManager
        - Mark combat as ended in GameEngine
        - Sync final HP to CharacterManager
        """
        # Get all NPC IDs
        npc_ids = [
            cid for cid, state in combat_state["combatant_states"].items()
            if state["is_hostile"]
        ]

        # Remove NPCs
        for npc_id in npc_ids:
            self.character_manager.remove_npc(npc_id)

        self.logger.info(f"Removed {len(npc_ids)} NPCs from CharacterManager")

        # Update GameEngine
        self.game_engine.game_state.combat_state = {
            "in_combat": False,
            "last_combat_outcome": combat_state.get("end_reason", "unknown")
        }

    def _update_game_engine(self, combat_result: Dict):
        """Update GameEngine with combat results"""
        # Update narrative context
        if combat_result["outcome"] == "victory":
            self.game_engine.game_state.narrative_context["last_event"] = "Won combat"
        elif combat_result["outcome"] == "defeat":
            self.game_engine.game_state.narrative_context["last_event"] = "Lost combat"

        self.logger.info("Updated GameEngine with combat results")

    def _generate_end_narrative(self, combat_result: Dict) -> str:
        """Generate combat end narrative"""
        outcome = combat_result["outcome"]
        rounds = combat_result["rounds"]

        if outcome == "victory":
            return f"🎉 VICTORY! You defeated your enemies in {rounds} rounds."
        elif outcome == "defeat":
            return f"💀 DEFEAT! You were overwhelmed after {rounds} rounds..."
        elif outcome == "fled":
            return f"🏃 You managed to escape after {rounds} rounds."
        else:
            return f"Combat ended after {rounds} rounds."
```

**2. Integration with PipelineOrchestrator** (~50 lines)

```python
# In orchestrator/pipeline_integration.py

class PipelineOrchestrator:
    def __init__(self, ...):
        # ... existing init ...

        # Create combat components
        self.combat_initializer = CombatInitializer(...)
        self.combat_action_resolver = CombatActionResolver(...)
        self.combat_narrative_gen = CombatNarrativeGenerator(self.llm)
        self.npc_ai_agent = NPCAIAgent(self.llm)
        self.npc_stat_generator = NPCStatGenerator(self.llm, shared_document_store)

        # Create combat agent
        self.agents["combat"] = CombatAgent(
            game_engine=game_engine,
            character_manager=character_manager,
            dnd_engine_wrapper=dnd_engine_wrapper,
            combat_initializer=self.combat_initializer,
            combat_action_resolver=self.combat_action_resolver,
            combat_narrative_generator=self.combat_narrative_gen,
            npc_ai_agent=self.npc_ai_agent
        )

        # Create combat pipeline
        self.pipelines["combat_pipeline"] = self._create_combat_pipeline()

    def _create_combat_pipeline(self) -> Pipeline:
        """Create combat pipeline (single component)"""
        pipeline = Pipeline()
        pipeline.add_component("combat_agent", self.agents["combat"])
        return pipeline

    def process_request(self, dto: RequestDTO) -> Dict:
        """Process request with combat routing"""
        route = dto.get("route", "scenario_pipeline")

        if route == "combat_pipeline":
            # Run complete combat session
            result = self.pipelines["combat_pipeline"].run({"dto": dto})
            return result["combat_agent"]["response"]

        # ... existing routing ...
```

**3. Integration with HaystackDnDGame** (~30 lines)

```python
# In haystack_dnd_game.py

class HaystackDnDGame:
    def play_turn(self, player_input: str) -> str:
        """Process player turn"""

        # Create DTO
        dto = self._create_request_dto(player_input)

        # Check if player selected combat choice
        if self._is_combat_choice(player_input):
            # Add scenario context to DTO
            dto["scenario_context"] = self.last_scenario
            dto["player_character_id"] = self.player_character_name

            # Route to combat pipeline
            dto["route"] = "combat_pipeline"

        # Process via orchestrator
        response = self.orchestrator.process_request(dto)

        # Handle response
        if response.get("response_type") == "combat_complete":
            # Combat finished
            return self._format_combat_result(response)
        else:
            # Regular scenario
            return self._format_scenario(response)

    def _is_combat_choice(self, player_input: str) -> bool:
        """Check if player selected a choice with combat_trigger"""
        if not self.last_scenario:
            return False

        # Parse choice number
        try:
            choice_idx = int(player_input) - 1
            if 0 <= choice_idx < len(self.last_scenario.get("choices", [])):
                choice = self.last_scenario["choices"][choice_idx]
                return choice.get("combat_trigger", False)
        except ValueError:
            pass

        return False
```

---

## Integration Points

### 1. Scenario Generator Enhancement

**No schema changes needed** - `combat_trigger` already exists as boolean on Choice.

Just enhance system prompt:

```python
# In agents/scenario_generator_agent.py

# Add to system prompt:
"""
COMBAT SCENARIO GUIDELINES:

When generating scenarios with combat:
1. Set choice.combat_trigger = true for combat choices
2. Describe enemies clearly in scene text
3. Include enemy details in gm_notes (count, CR, equipment)

Example:
{
  "scene": "Two goblin warriors leap out, scimitars drawn!",
  "choices": [
    {
      "title": "Fight the goblins **Combat**",
      "combat_trigger": true  // ← Triggers combat
    }
  ],
  "gm_notes": "Two goblin warriors (CR 1/4 each). Scimitars, leather armor."
}
"""
```

### 2. GameEngine

Add combat result processing:

```python
# In components/game_engine.py

def process_combat_result(self, combat_result: Dict):
    """Process combat results after combat ends"""
    # Update narrative context
    if combat_result["outcome"] == "victory":
        self.game_state.narrative_context["last_event"] = "Won combat"
        self.game_state.narrative_context["pacing"] = "Triumphant"

    # Update quest objectives if combat-related
    # ...
```

---

## Testing Strategy

### Unit Tests

**Phase 1 - NPC Generation:**
```bash
pytest tests/combat/test_npc_stat_generator.py -v
```

Tests:
- NPC stat generation with LLM
- Stat validation and repair
- Template loading
- JSON parsing

**Phase 2 - Combat Init:**
```bash
pytest tests/combat/test_combat_initializer.py -v
```

Tests:
- Enemy parsing from scenario
- Predefined NPC loading
- NPC generation
- Initiative rolling
- Combat state creation

**Phase 3 - Combat Session:**
```bash
pytest tests/combat/test_combat_session_manager.py -v
```

Tests:
- Turn advancement
- Action validation
- End condition checking
- Player action parsing
- NPC AI integration

### Integration Tests

```python
# tests/combat/test_combat_integration.py

def test_full_combat_session():
    """
    Test complete combat from trigger to end.

    Verifies:
    - Combat initialization
    - Turn loop execution
    - NPC generation
    - Combat ends correctly
    - Cleanup happens
    """
    # Create scenario with combat
    scenario = {
        "scene": "Two goblins attack!",
        "gm_notes": "Two goblins (CR 1/4)",
        "choices": [{"combat_trigger": True}]
    }

    # Create DTO
    dto = {
        "scenario_context": scenario,
        "player_character_id": "aggi"
    }

    # Run combat agent (will block until combat complete)
    combat_agent = CombatAgent(...)
    result = combat_agent.run(dto)

    # Verify result
    assert result["response"]["response_type"] == "combat_complete"
    assert result["response"]["outcome"] in ["victory", "defeat"]
    assert result["response"]["rounds"] >= 1

    # Verify NPCs removed
    remaining_npcs = character_manager.get_npcs()
    assert len(remaining_npcs) == 0
```

### End-to-End Test

```python
# tests/test_combat_e2e.py

def test_game_with_combat():
    """
    Test full game flow with combat.

    Steps:
    1. Start game
    2. Generate scenario with combat
    3. Player selects combat choice
    4. Complete combat (simulated inputs)
    5. Verify game continues after combat
    """
    game = HaystackDnDGame(config)

    # Regular turn
    response = game.play_turn("I explore the area")
    assert "combat" not in response.lower()

    # Trigger combat (assume choice 1 has combat_trigger)
    with patch('builtins.input', side_effect=['1', '1', '1', '1', '1']):
        # 5 simulated combat actions
        response = game.play_turn("1")  # Select combat choice

    # Verify combat completed
    assert "victory" in response.lower() or "defeat" in response.lower()

    # Verify game continues
    response = game.play_turn("I rest")
    assert response  # Game still works
```

---

## Success Metrics

### Phase 1
- [ ] NPC generation creates valid D&D stats
- [ ] Template loading works
- [ ] Stat validation catches errors
- [ ] All Phase 1 tests pass (>90% coverage)

### Phase 2
- [ ] Combat initializes from scenario
- [ ] Enemies extracted from scene/gm_notes
- [ ] Initiative rolls correctly
- [ ] All Phase 2 tests pass (>90% coverage)

### Phase 3
- [ ] Combat loop runs to completion
- [ ] Player can input actions
- [ ] NPC AI makes decisions
- [ ] Combat ends correctly
- [ ] All Phase 3 tests pass (>90% coverage)

### Phase 4
- [ ] CombatAgent runs full combat
- [ ] Integration with orchestrator works
- [ ] Cleanup happens correctly
- [ ] E2E test passes

### Overall
- [ ] Combat playable from scenario to end
- [ ] No regression in existing features
- [ ] All tests pass (>85% coverage)
- [ ] Manual testing complete
- [ ] Documentation updated

---

## File Structure Summary

```
roshar-dnd/
├── components/
│   ├── combat/                                    # NEW
│   │   ├── __init__.py
│   │   ├── npc_stat_generator.py                 (~400 lines)
│   │   ├── combat_initializer.py                 (~600 lines)
│   │   ├── combat_session_manager.py             (~700 lines)
│   │   ├── combat_action_resolver.py             (~400 lines)
│   │   └── combat_narrative_generator.py         (~400 lines)
│   ├── character_manager.py                       (+50 lines)
│   └── game_engine.py                             (+50 lines)
│
├── agents/
│   ├── combat_agent.py                            (~400 lines) NEW
│   ├── npc_ai_agent.py                            (~200 lines) NEW
│   └── scenario_generator_agent.py                (+30 lines - prompt)
│
├── orchestrator/
│   └── pipeline_integration.py                    (+50 lines)
│
├── data/
│   └── npc_templates.json                         (~200 lines) NEW
│
├── tests/
│   └── combat/                                     # NEW
│       ├── __init__.py
│       ├── test_npc_stat_generator.py            (~300 lines)
│       ├── test_combat_initializer.py            (~400 lines)
│       ├── test_combat_session_manager.py        (~400 lines)
│       ├── test_combat_action_resolver.py        (~200 lines)
│       ├── test_combat_integration.py            (~300 lines)
│       └── test_combat_e2e.py                    (~200 lines)
│
├── docs/
│   └── COMBAT_ENGINE_IMPLEMENTATION_PLAN.md       (THIS FILE)
│
└── haystack_dnd_game.py                            (+30 lines)

NEW FILES: 15
MODIFIED FILES: 4
TOTAL NEW LINES: ~5,800
```

---

## Conclusion

This rewritten plan provides a **robust, self-contained combat system** that:

1. **Runs combat as single atomic operation** - No orchestrator round-trips per turn
2. **Manages turns internally** - Combat agent gets player input directly
3. **Self-contained state** - Combat state managed within CombatAgent.run()
4. **Intelligent NPC generation** - LLM+RAG for dynamic enemies
5. **Tactical NPC AI** - NPCs make smart decisions
6. **Engaging narratives** - LLM-generated combat descriptions
7. **Clean integration** - New pipeline, no disruption to existing features

The key architectural improvement is **treating combat as a complete session** rather than multiple discrete turns through the orchestrator. This eliminates failure points, improves performance, and provides better UX.

**Total Estimated Time:** 10-14 days

**Ready for implementation.**
