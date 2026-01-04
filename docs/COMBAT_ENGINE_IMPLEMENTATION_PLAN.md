# Combat Engine Implementation Plan
**Version:** 4.1 (Simplified - No Fallbacks, dnd_engine Only)
**Date:** 2026-01-03
**Last Updated:** 2026-01-03 (Removed all fallback logic)
**Status:** Phase 1 Complete ✅ | Phase 1.5 Complete ✅ | Phase 2 Complete ✅ | Phase 3 Ready ✅

---

## 🎯 Implementation Progress

### ✅ Phase 1: COMPLETE (NPC Stat Generation)
**Completed:** 2026-01-03
**Time Taken:** ~2 hours (faster than estimated due to Haystack + Pydantic efficiency)

**Deliverables Implemented:**
- ✅ `components/combat/npc_stat_generator.py` (475 lines) - Haystack + Pydantic validation
- ✅ `data/npc_templates.json` (174 lines) - 5 standardized templates (Goblin, Bandit, Skeleton, Wolf, Guard)
- ✅ `tests/combat/test_npc_stat_generator.py` (358 lines) - 8/8 unit tests passing
- ✅ `run_llm_test.py` - Helper script for real LLM testing
- ✅ NPCStats Pydantic model with comprehensive validators
- ✅ Automatic repair logic for common LLM mistakes
- ✅ Template loading system
- ✅ RAG integration for creature stats

**Test Results:** 8/8 unit tests passing (100% success rate)

**Key Achievements:**
- Zero migration cost - same Haystack 2.0 patterns as existing agents
- Pydantic validation enforces CharacterData format automatically
- Repair logic fixes common mistakes (class→character_class, int HP→dict, list skills→dict)

---

### ✅ Phase 1.5: NPC Registry Integration (BONUS PHASE)
**Completed:** 2026-01-03
**Time Taken:** ~1.5 hours

**Problem Identified:** Combat Plan assumed `campaign_npc['stats']` exists, but campaign NPCs only have basic metadata. Full stats were in separate `.txt` files that needed conversion and loading infrastructure.

**Solutions Implemented:**
- ✅ `data/players/kalak_herald.json` - Converted Kalak Herald to CharacterData format (400 HP, Level 20)
- ✅ `data/players/nale_herald.json` - Converted Nale Herald to CharacterData format (380 HP, Level 20)
- ✅ `core/npc_stat_loader.py` (200 lines) - NPCStatLoader for loading predefined NPCs
- ✅ `core/game_initialization.py` - Integrated NPC registry loading (lines 273-284)
- ✅ `tests/test_npc_registry_integration.py` (290 lines) - 10/10 integration tests passing
- ✅ Case-insensitive and partial name matching
- ✅ Validation of CharacterData format
- ✅ Integration with CharacterManager

**Test Results:** 10/10 integration tests passing (100% success rate)

**Documentation:**
- ✅ `docs/COMBAT_PLAN_NPC_INTEGRATION_GAPS.md` - Gap analysis and resolution
- ✅ `docs/NPC_JSON_CONVERSION_COMPLETE.md` - JSON conversion report
- ✅ `docs/PHASE_1_IMPLEMENTATION_COMPLETE.md` - Phase 1 completion report

**Key Achievements:**
- Eliminated 3-4 hours of parsing complexity by converting to JSON format
- NPC registry available globally via `GameInitConfig.npc_registry`
- Predefined NPCs (Heralds) ready for combat encounters
- Graceful fallback to generated NPCs if predefined not found

---

### ✅ Phase 2: COMPLETE (Combat Initialization)
**Started:** 2026-01-03
**Completed:** 2026-01-03
**Status:** Implementation complete with all tests passing

**Deliverables Implemented:**
- ✅ `components/combat/combat_initializer.py` (649 lines)
- ✅ `tests/combat/test_combat_initializer.py` (21/21 tests passing - 100% success rate)

**Test Results:** 21/21 unit tests passing (100% success rate)

**Key Features:**
- ✅ Combat trigger detection (supports combat_trigger flag + keyword fallback)
- ✅ Enemy parsing from scenario text via LLM (handles markdown, invalid JSON)
- ✅ Predefined NPC loading from NPC registry (case-insensitive lookup)
- ✅ NPC generation for undefined enemies (multiple instances supported)
- ✅ Initiative rolling for all combatants (sorted descending)
- ✅ Combat state initialization (combatant states, end conditions)
- ✅ Graceful fallback handling (no registry, no enemies, no trigger)

**Integration:**
- ✅ NPCStatLoader integration for predefined NPCs (Heralds, etc.)
- ✅ NPCStatGenerator integration for dynamic NPC creation
- ✅ CharacterManager integration for NPC storage
- ✅ DnDEngineWrapper integration for initiative rolls
- ✅ GameEngine integration for state management

**Test Coverage:**
- Combat trigger detection (4 tests)
- Enemy parsing (4 tests)
- Predefined NPC loading (3 tests)
- NPC generation (3 tests)
- Initiative rolling (2 tests)
- Combatant state initialization (2 tests)
- Full combat initialization (2 tests)
- Factory function (1 test)

---

### ✅ Phase 3: ARCHITECTURE READY (Combat Session Manager - SIMPLIFIED)
**Completed:** 2026-01-03 (Architecture, Optimization, and Simplification)
**Status:** Ready for implementation with simplified dnd_engine-only approach

**Key Simplification (v4.1):** Removed ALL fallback logic. Assumes dnd_engine is always available and properly initialized. Direct entity access (`entities[char_id]`) instead of defensive `entities.get(char_id)`.

**Documentation:**
- ✅ `docs/COMBAT_PLAN_METHOD_OPTIMIZATION_ANALYSIS.md` - Complete optimization analysis
- ✅ `docs/ROSHAR_COMBAT_MECHANICS_INTEGRATION.md` - Official Roshar rules integration
- ✅ `docs/DND_ENGINE_COMBAT_CAPABILITIES.md` - dnd_engine capabilities analysis
- ✅ `docs/COMBAT_PLAN_GENERIC_ARCHITECTURE_UPDATE.md` - Generic architecture design
- ✅ `docs/COMBAT_SYSTEM_READINESS_REPORT.md` - Overall readiness assessment

**Major Architectural Improvements:**
1. **Generic, Data-Driven Design** - ACTION_REGISTRY eliminates hardcoded action lists (~25% code reduction)
2. **dnd_engine Native Integration** - Leverage battle-tested D&D mechanics (health, action economy, conditions)
3. **Official Roshar Rules** - Based on Cosmere 5e: Radiant's Handbook v2.0 (D&D 5e-compatible)
4. **Simplified Methods** - 8 methods improved, ALL fallbacks removed (~55-60 lines saved, 8-9% reduction)
5. **Fail Fast Design** - Entity lookup failures raise exceptions immediately for easier debugging

**Simplified Methods (No Fallbacks):**
1. ✅ **`_check_end_conditions()`** - Use `entity.health.is_dead()/is_unconscious()` exclusively
2. ✅ **`_is_combatant_dead()`** - dnd_engine death save system only (no combat_state fallback)
3. ✅ **`_can_character_afford_action()`** - `entity.action_economy.can_afford()` exclusively
4. ✅ **`_consume_action()`** - Direct entity access, sync to combat_state for UI only
5. ✅ **`_has_actions_remaining()`** - Query dnd_engine directly, no fallback
6. ✅ **`_build_npc_context()`** - dnd_engine HP only, dynamic action discovery
7. ✅ **`_validate_action()`** - Leverage Action._validate() prerequisites
8. ✅ **`_advance_turn()`** - Trigger TURN_START events

**Architectural Benefits:**
- ✅ **Code Reduction:** ~55-60 lines saved (8-9% reduction from original ~700 lines)
- ✅ **Simplified Logic:** No conditional checks for dnd_engine availability
- ✅ **Cleaner Code:** Direct entity access, less defensive programming
- ✅ **New Capabilities:** Death saves, temporary HP, damage resistance, range/LoS, condition events
- ✅ **Single Source of Truth:** dnd_engine is authoritative, combat_state is UI-only
- ✅ **Better D&D 5e Compliance:** Proper death/unconscious/stabilized mechanics
- ✅ **Fail Fast Debugging:** Entity lookup failures raise exceptions immediately

**Implementation Timeline (Updated):**
- **Phase 3A: Core Session Manager** - 1.5 days (simplified implementation)
- **Phase 3B: Roshar Extensions** - 2 days (roshar_actions.py, stormlight_manager.py)
- **Phase 3C: Testing** - 1 day
- **Total:** ~4.5 days for simplified Phase 3 implementation (0.5 days faster due to no fallback logic)

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

**✅ ARCHITECTURE UPDATE (2026-01-03):** Phase 2 has been simplified thanks to the NPC Registry integration completed in Phase 1.5:
- Old approach tried to access `campaign_npc['stats']` which doesn't exist
- New approach uses `NPCStatLoader` (npc_registry) with case-insensitive lookup
- Predefined NPCs (Heralds) are loaded from JSON files in `data/players/`
- Graceful fallback to NPC generation if predefined NPC not found
- ~30% reduction in complexity for _load_predefined_npcs()

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
        npc_registry,  # ✅ ADDED (2026-01-03): NPCStatLoader for predefined NPCs
        llm
    ):
        self.game_engine = game_engine
        self.character_manager = character_manager
        self.dnd_wrapper = dnd_engine_wrapper
        self.npc_generator = npc_stat_generator
        self.npc_registry = npc_registry  # ✅ ADDED
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
        Load NPCs from NPC registry if they match enemy names.

        ✅ UPDATED (2026-01-03): Now uses NPCStatLoader instead of campaign_npc['stats']

        Checks:
        1. NPCStatLoader (npc_registry) for name matches
        2. If enemy is_predefined=True

        Returns:
            List of char_ids for predefined NPCs added to CharacterManager
        """
        predefined_ids = []

        if not self.npc_registry:
            self.logger.warning("⚠️ No NPC registry available, skipping predefined NPC loading")
            return predefined_ids

        for enemy in enemies:
            if not enemy.get('is_predefined', False):
                continue

            enemy_name = enemy.get('name', '')

            # Try to load from NPC registry (uses case-insensitive + partial matching)
            npc_stats = self.npc_registry.get_npc_by_name(enemy_name)

            if npc_stats:
                # Found predefined NPC - add to CharacterManager
                char_id = self.character_manager.add_npc(npc_stats)
                predefined_ids.append(char_id)

                self.logger.info(f"✅ Loaded predefined NPC: {npc_stats['name']} ({char_id})")

                # Mark as processed so we don't generate it
                enemy['processed'] = True
            else:
                self.logger.warning(f"⚠️ No NPC file found for '{enemy_name}', will generate")
                enemy['is_predefined'] = False  # Fallback to generation

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

**ARCHITECTURAL APPROACH (2026-01-03):**
- ✅ **Generic, Data-Driven Design** - No hardcoded action lists or if/elif chains
- ✅ **Leverages dnd_engine** - Uses native Actions for D&D 5e mechanics
- ✅ **Metadata Dispatch** - All decisions driven by ACTION_REGISTRY metadata
- ✅ **Infinite Extensibility** - New actions added to registry work automatically
- ✅ **Roshar + D&D** - Seamless integration of custom and standard actions

#### Architecture Decision: Use dnd_engine Native Actions + Roshar Extensions

**MAJOR UPDATE (2026-01-03)**: After reviewing `external/dnd_engine/`, discovered it has a **fully-featured Action framework** with event-driven combat. We should use dnd_engine's native Actions instead of reimplementing mechanics.

**ROSHAR MECHANICS INTEGRATION (2026-01-03)**: Reviewed official Cosmere 5e: Radiant's Handbook v2.0. Roshar mechanics (Surgebinding, Stormlight, Shardblades) are **already D&D 5e-compatible** and integrate seamlessly with dnd_engine's action economy. Surges use standard action/bonus action/reaction costs, Stormlight is tracked as consumable resource (not separate magic system), and Shardblades work as special weapons with soul damage effects.

**See:**
- `docs/DND_ENGINE_COMBAT_CAPABILITIES.md` for dnd_engine analysis
- `docs/ROSHAR_COMBAT_MECHANICS_INTEGRATION.md` for complete Roshar rules integration

---

### What dnd_engine Provides (D&D 5e Foundation)

**File:** `external/dnd_engine/dnd/actions.py`

**Native Actions:**
- ✅ **Attack** (lines 219-400) - Full attack resolution with range validation, line of sight, advantage/disadvantage, critical hits, damage with resistances, HP tracking
- ✅ **Move** (lines 68-202) - Pathfinding, movement costs, position updates, line of sight recalculation
- ✅ **Event System** - All actions flow through `DECLARATION → EXECUTION → EFFECT → COMPLETION` phases
- ✅ **Action Economy** - Tracks actions, bonus actions, reactions, movement with `can_afford()`, `consume()`, `reset()`
- ✅ **Condition System** - Dashing, Blinded, Charmed, etc. with proper modifier application

**Example Usage:**
```python
from dnd.actions import Attack, WeaponSlot

# Use native dnd_engine Action
attack = Attack(
    source_entity_uuid=attacker.uuid,
    target_entity_uuid=target.uuid,
    weapon_slot=WeaponSlot.MAIN_HAND
)
attack_event = attack.apply()  # Returns AttackEvent with full resolution

# All mechanics handled by dnd_engine:
# - Range/line of sight validation
# - Attack roll (d20 + modifiers)
# - Advantage/disadvantage
# - Critical hits
# - Damage with resistances
# - HP tracking
# - Action economy consumption
```

---

### Roshar Extensions (Our Custom Implementation)

**Design Principle:** Extend dnd_engine using its native patterns (Actions, Conditions, Modifiers) instead of bypassing it.

#### 1. Roshar-Specific Actions

**File:** `components/combat/roshar_actions.py` (~400 lines)

```python
from dnd.core.base_actions import BaseAction, ActionEvent
from dnd.core.events import EventPhase, EventType
from dnd.entity import Entity

class LashingEvent(ActionEvent):
    """Event for Windrunner Lashing (Surgebinding)"""
    name: str = "Lashing"
    event_type: EventType = EventType.CUSTOM  # Roshar-specific
    lashing_type: str  # "basic", "full", "reverse"
    stormlight_cost: int  # Stormlight spheres consumed
    target_direction: Tuple[int, int, int]  # Gravity direction vector

class Lashing(BaseAction):
    """
    Windrunner Lashing - Roshar Surgebinding ability

    Extends dnd_engine Action framework with Stormlight mechanics.
    """
    name: str = "Lashing"
    description: str = "Manipulate gravity through Surgebinding"
    lashing_type: str  # "basic", "full", "reverse"
    costs: List[Cost] = [
        Cost(name="Stormlight Cost", cost_type="stormlight", cost=1, evaluator=stormlight_cost_evaluator),
        Cost(name="Action Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ]

    def _validate(self, declaration_event: LashingEvent) -> LashingEvent:
        """Validate Lashing prerequisites"""
        entity = Entity.get(self.source_entity_uuid)

        # Check Windrunner level
        if not hasattr(entity, 'surgebinding_level'):
            return declaration_event.cancel(status_message="Entity cannot use Surgebinding")

        if entity.surgebinding_level < 1:
            return declaration_event.cancel(status_message="Insufficient Windrunner attunement")

        # Check Stormlight availability
        if entity.stormlight_spheres < self.costs[0].cost:
            return declaration_event.cancel(status_message="Insufficient Stormlight")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message="Lashing validated"
        )

    def _apply(self, execution_event: LashingEvent) -> LashingEvent:
        """Apply Lashing effects"""
        entity = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid)

        # Apply gravity manipulation
        if self.lashing_type == "basic":
            # Change target's gravity direction
            target.gravity_direction = execution_event.target_direction

            # Apply condition for duration
            lashed_condition = LashedCondition(
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=target.uuid,
                gravity_direction=execution_event.target_direction,
                duration=Duration(duration=10, duration_type=DurationType.SECONDS)
            )
            lashed_condition.apply(execution_event)

        # Consume Stormlight
        entity.stormlight_spheres -= self.costs[0].cost

        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Lashing applied to {target.name}"
        )
```

**Other Roshar Actions to Implement:**
- `ShardbladeAttack` - Shardblade combat (ignores armor, severs soul)
- `ShardplateBoost` - Shardplate strength enhancement
- `Soulcasting` - Elsecaller/Lightweaver transmutation
- `Adhesion` - Windrunner object binding
- `StormFormLightning` - Parshendi storm form lightning
- `VoidbindingCorruption` - Fused powers

#### 2. Roshar-Specific Conditions

**File:** `components/combat/roshar_conditions.py` (~300 lines)

```python
from dnd.core.base_conditions import BaseCondition, Duration, DurationType
from dnd.core.modifiers import NumericalModifier, AdvantageModifier

class StormlightInfused(BaseCondition):
    """
    Entity is infused with Stormlight (Surgebinder healing/enhancement)

    Effects:
    - Regenerates HP each turn
    - Advantage on physical checks
    - Glowing aura (disadvantage on Stealth)
    """
    name: str = "Stormlight Infused"
    stormlight_amount: int  # Spheres infused

    def _apply(self, event):
        entity = Entity.get(self.target_entity_uuid)
        modifiers = []

        # Add regeneration (handled via event handler)
        regen_handler = EventHandler(
            trigger_conditions=[Trigger(
                event_types=[EventType.TURN_START],
                source_entity_uuids=[self.target_entity_uuid]
            )],
            handler_function=self.regenerate_hp
        )
        entity.add_event_handler(regen_handler)
        handler_uuids = [regen_handler.uuid]

        # Advantage on STR/DEX/CON checks
        for ability in ['strength', 'dexterity', 'constitution']:
            ability_score = getattr(entity.ability_scores, ability)
            modifier_uuid = ability_score.self_static.add_advantage_modifier(
                AdvantageModifier(name="Stormlight Infused", value=AdvantageStatus.ADVANTAGE)
            )
            modifiers.append((ability_score.uuid, modifier_uuid))

        # Disadvantage on Stealth (glowing)
        stealth = entity.skill_set.get_skill('stealth')
        modifier_uuid = stealth.skill_bonus.self_static.add_advantage_modifier(
            AdvantageModifier(name="Stormlight Infused", value=AdvantageStatus.DISADVANTAGE)
        )
        modifiers.append((stealth.skill_bonus.uuid, modifier_uuid))

        return modifiers, handler_uuids, [], event

    def regenerate_hp(self, event, entity_uuid):
        """Event handler for HP regeneration"""
        entity = Entity.get(entity_uuid)

        # Regenerate HP based on Stormlight amount
        regen_amount = min(self.stormlight_amount, 5)  # Max 5 HP/turn
        entity.health.heal(regen_amount)

        # Consume Stormlight
        self.stormlight_amount -= 1
        if self.stormlight_amount <= 0:
            # Remove condition when Stormlight depleted
            entity.remove_condition(self.name)

class ShardplateArmored(BaseCondition):
    """Shardplate armor condition - bonus AC, resistance to non-Shardblade damage"""
    name: str = "Shardplate Armored"

    def _apply(self, event):
        entity = Entity.get(self.target_entity_uuid)

        # +5 AC bonus
        ac_modifier = NumericalModifier(name="Shardplate", value=5)
        ac_uuid = entity.equipment.ac_bonus.self_static.add_value_modifier(ac_modifier)

        # Resistance to physical damage (except Shardblade)
        # TODO: Add resistance modifier with contextual check

        return [(entity.equipment.ac_bonus.uuid, ac_uuid)], [], [], event
```

**Other Roshar Conditions:**
- `Lashed` - Altered gravity direction
- `Soulcast` - Temporarily transmuted material
- `VoidbindingCorrupted` - Fused corruption effects
- `RhythmOfWar` - Listener/Singer rhythm bonuses

---

### Architectural Benefits

**1. Use dnd_engine's Battle-Tested Foundation:**
- ✅ D&D 5e mechanics (attacks, movement, conditions) work correctly
- ✅ Event system enables reactions (Shield spell, Parry)
- ✅ Action economy properly tracks resources
- ✅ Advantage/disadvantage stacking works
- ✅ Critical hits calculated correctly

**2. Extend with Roshar Mechanics:**
- ✅ Custom Actions (Lashing, Soulcasting) follow dnd_engine patterns
- ✅ Custom Conditions (Stormlight Infused) use modifier system
- ✅ Custom costs (Stormlight spheres) integrate with action economy
- ✅ Event handlers enable complex interactions (Stormlight regen)

**3. Code Reduction:**
- **Original plan:** ~400 lines for CombatActionResolver (reimplementing D&D)
- **With dnd_engine:** ~150 lines (thin wrapper) + ~400 lines (Roshar extensions)
- **Net:** Same total lines, but D&D mechanics are battle-tested, only Roshar code is custom

---

### Implementation Strategy

**Phase 3A: Update dnd_engine_wrapper** (~2 days)
```python
# components/dnd_engine_wrapper.py - Add native Action support

def execute_dnd_action(self, action_class, **kwargs) -> Event:
    """
    Execute native dnd_engine Action.

    Args:
        action_class: Attack, Move, etc.
        **kwargs: Action parameters

    Returns:
        Event with results
    """
    action = action_class(**kwargs)
    event = action.apply()

    # Sync state back to CharacterManager
    if hasattr(event, 'source_entity_uuid'):
        self._sync_entity_to_game_state(event.source_entity_uuid)
    if hasattr(event, 'target_entity_uuid') and event.target_entity_uuid:
        self._sync_entity_to_game_state(event.target_entity_uuid)

    return event

def apply_condition(self, condition_class, **kwargs) -> Event:
    """Apply dnd_engine Condition (Dashing, Blinded, etc.)"""
    condition = condition_class(**kwargs)
    event = condition.apply()
    self._sync_entity_to_game_state(kwargs['target_entity_uuid'])
    return event
```

**Phase 3B: Implement Roshar Extensions** (~3 days)
- Create `components/combat/roshar_actions.py` - Lashing, Shardblade, Soulcasting
- Create `components/combat/roshar_conditions.py` - Stormlight, Shardplate, etc.
- Add Roshar-specific cost types (Stormlight spheres)
- Add custom event types for Roshar mechanics

**Phase 3C: Unified CombatActionResolver** (~1 day)
```python
class CombatActionResolver:
    """Dispatches to dnd_engine Actions + Roshar extensions"""

    ACTION_REGISTRY = {
        # D&D 5e actions (via dnd_engine)
        "attack": {"action_class": Attack, "params": ["target_entity_uuid", "weapon_slot"]},
        "move": {"action_class": Move, "params": ["end_position"]},

        # D&D conditions (via dnd_engine)
        "dash": {"condition_class": Dashing, "duration": Duration(1, DurationType.TURNS)},
        "dodge": {"condition_class": Dodging, "duration": Duration(1, DurationType.TURNS)},

        # Roshar actions (custom)
        "lashing": {"action_class": Lashing, "params": ["target_entity_uuid", "lashing_type"]},
        "shardblade_attack": {"action_class": ShardbladeAttack, "params": ["target_entity_uuid"]},

        # Roshar conditions (custom)
        "infuse_stormlight": {"condition_class": StormlightInfused, "params": ["stormlight_amount"]}
    }

    def resolve_action(self, action: Dict) -> Dict:
        action_type = action["action_type"]
        metadata = self.ACTION_REGISTRY[action_type]

        if "action_class" in metadata:
            return self._execute_action(action, metadata)
        elif "condition_class" in metadata:
            return self._apply_condition(action, metadata)
```

---

### Benefits of This Approach

1. **Correctness** - D&D mechanics from dnd_engine are battle-tested
2. **Extensibility** - Roshar abilities follow same patterns as D&D actions
3. **Maintainability** - Update dnd_engine for D&D fixes, only maintain Roshar code
4. **Feature-rich** - Event system enables reactions, interrupts, complex triggers
5. **Proper Integration** - Roshar mechanics (Stormlight) integrate with action economy naturally

#### Deliverables

**1. components/combat/combat_session_manager.py** (~700 lines)

```python
class CombatSessionManager:
    """
    Manages internal combat turn loop.

    **ARCHITECTURE (2026-01-03): Generic Data-Driven Design**

    This class uses a fully generic approach that leverages dnd_engine and ACTION_REGISTRY:
    - ✅ No hardcoded action lists - discovers actions from ACTION_REGISTRY
    - ✅ No if/elif chains for action types - uses metadata dispatch
    - ✅ Works with both D&D 5e actions and Roshar extensions seamlessly
    - ✅ New actions can be added to ACTION_REGISTRY without modifying this code

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
        Execute player's turn using hierarchical menu navigation.

        **UPDATED (2026-01-03)**: Implemented two-level menu system to prevent
        UI overload when many targets/abilities exist.

        Process:
        1. Display combat status
        2. Show action categories (Level 1)
        3. Get category selection
        4. Show specific actions in category (Level 2)
        5. Get action selection
        6. Parse and validate action
        7. Execute via action resolver
        8. Generate and display narrative
        9. Update combat state
        """
        self.logger.info(f"🎮 Player turn: {player_char_id}")

        # Display status
        print("\n" + "="*60)
        print(self.narrative_gen.generate_combat_status(self.combat_state))
        print("="*60)

        # Get available action categories
        action_categories = self._get_available_actions(player_char_id)

        if not action_categories:
            print("❌ No actions available (no actions remaining)")
            return

        # LEVEL 1: Choose action category
        print("\n📋 Choose Action Type:")
        category_keys = list(action_categories.keys())
        for i, category_key in enumerate(category_keys, 1):
            category = action_categories[category_key]
            action_count = len(category["actions"])
            print(f"  {i}. {category['name']} - {category['description']} ({action_count} options)")

        selected_category_key = None
        while True:
            try:
                choice = input(f"\n{player_char_id}> Choose action type (1-{len(category_keys)}): ").strip()

                if not choice.isdigit():
                    print("❌ Please enter a number")
                    continue

                choice_idx = int(choice) - 1

                if choice_idx < 0 or choice_idx >= len(category_keys):
                    print(f"❌ Please choose 1-{len(category_keys)}")
                    continue

                selected_category_key = category_keys[choice_idx]
                break

            except (ValueError, KeyError) as e:
                print(f"❌ Invalid choice: {e}")

        # LEVEL 2: Choose specific action within category
        selected_category = action_categories[selected_category_key]
        specific_actions = selected_category["actions"]

        print(f"\n{selected_category['name']} - Choose Target/Action:")
        for i, action_item in enumerate(specific_actions, 1):
            print(f"  {i}. {action_item['display']}")

        selected_action_item = None
        while True:
            try:
                choice = input(f"\n{player_char_id}> Choose action (1-{len(specific_actions)}): ").strip()

                if not choice.isdigit():
                    print("❌ Please enter a number")
                    continue

                choice_idx = int(choice) - 1

                if choice_idx < 0 or choice_idx >= len(specific_actions):
                    print(f"❌ Please choose 1-{len(specific_actions)}")
                    continue

                selected_action_item = specific_actions[choice_idx]
                break

            except (ValueError, KeyError) as e:
                print(f"❌ Invalid choice: {e}")

        # Parse action from selection
        action = self._parse_hierarchical_action(
            player_char_id,
            selected_category_key,
            selected_action_item
        )

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

    def _get_available_actions(self, char_id: str) -> Dict[str, Dict[str, Any]]:
        """
        Get hierarchical action categories for character using ACTION_REGISTRY.

        **UPDATED (2026-01-03)**: Generic data-driven approach that queries
        ACTION_REGISTRY to discover available actions dynamically.

        Returns action categories with sub-options:
        {
            "standard_actions": {
                "name": "⚔️ Standard Actions",
                "description": "Attack, cast spells, use abilities",
                "cost_type": "actions",
                "actions": [...]
            },
            "bonus_actions": {
                "name": "⚡ Bonus Actions",
                "description": "Quick abilities and reactions",
                "cost_type": "bonus_actions",
                "actions": [...]
            },
            "utility": {
                "name": "🛡️ Utility",
                "description": "Defensive and movement options",
                "cost_type": "actions",
                "actions": [...]
            }
        }
        """
        categories = {
            "standard_actions": {
                "name": "⚔️ Standard Actions",
                "description": "Attack, cast spells, use abilities",
                "cost_type": "actions",
                "actions": []
            },
            "bonus_actions": {
                "name": "⚡ Bonus Actions",
                "description": "Quick abilities and reactions",
                "cost_type": "bonus_actions",
                "actions": []
            },
            "utility": {
                "name": "🛡️ Utility",
                "description": "Defensive and movement options",
                "cost_type": "actions",
                "actions": []
            }
        }

        char_state = self.combat_state["combatant_states"][char_id]
        character = self.character_manager.characters[char_id]

        # Query ACTION_REGISTRY to discover available actions
        for action_type, metadata in self.action_resolver.ACTION_REGISTRY.items():
            # Check if character can afford this action
            if not self._can_character_afford_action(char_id, metadata):
                continue

            # Check if character meets requirements
            if not self._character_meets_requirements(character, metadata):
                continue

            # Determine which category this action belongs to
            category = self._categorize_action(action_type, metadata)

            # Generate action options (with targets if needed)
            action_options = self._generate_action_options(
                char_id, action_type, metadata
            )

            categories[category]["actions"].extend(action_options)

        # Remove empty categories
        return {k: v for k, v in categories.items() if v["actions"]}

    def _can_character_afford_action(self, char_id: str, action_metadata: Dict) -> bool:
        """
        Check if character has resources for action using dnd_engine.

        **SIMPLIFIED (2026-01-03):** Uses entity.action_economy.can_afford() exclusively.
        No fallback to manual checking.

        Args:
            char_id: Character ID
            action_metadata: Action metadata from ACTION_REGISTRY

        Returns:
            True if character can afford the action, False otherwise
        """
        entity = self.dnd_wrapper.entities[char_id]
        action_class = action_metadata.get("action_class")

        if action_class and hasattr(action_class, "cost_type") and hasattr(action_class, "cost"):
            cost_type = action_class.cost_type
            cost = action_class.cost

            # Use dnd_engine's native can_afford() method
            return entity.action_economy.can_afford(cost_type, cost)

        # Action has no cost defined, assume it's free
        return True

    def _character_meets_requirements(self, character, action_metadata: Dict) -> bool:
        """Check if character meets action requirements (e.g., has Shardblade)."""
        requires = action_metadata.get("requires")
        if not requires:
            return True

        # Check character has required ability/item
        if requires == "surgebinding":
            return hasattr(character, "surgebinding_level") and character.surgebinding_level > 0
        elif requires == "shardblade":
            return hasattr(character, "has_shardblade") and character.has_shardblade
        elif requires == "stormlight_spheres":
            return hasattr(character, "stormlight_spheres") and character.stormlight_spheres > 0

        return True

    def _categorize_action(self, action_type: str, metadata: Dict) -> str:
        """Determine which UI category an action belongs to."""
        # Check if it's a bonus action
        action_class = metadata.get("action_class")
        if action_class and hasattr(action_class, "cost_type"):
            if action_class.cost_type == "bonus_actions":
                return "bonus_actions"

        # Categorize based on action characteristics
        if metadata.get("type") in ["dnd_condition", "roshar_condition"]:
            # Conditions like Dash, Dodge are utility
            return "utility"
        elif action_type in ["attack", "shardblade_attack", "lashing", "soulcasting"]:
            # Offensive actions
            return "standard_actions"

        return "utility"

    def _generate_action_options(
        self,
        char_id: str,
        action_type: str,
        metadata: Dict
    ) -> List[Dict[str, Any]]:
        """
        Generate action options (with targets if action requires targeting).

        Returns list of action options:
        [
            {
                "action_type": "attack",
                "display": "Attack Goblin Warrior (HP: 7/7)",
                "params": {"target": "goblin_001"}
            }
        ]
        """
        requires_target = "target_entity_uuid" in metadata.get("params", [])

        if requires_target:
            # Generate option for each valid target
            options = []
            targets = self._get_valid_targets(char_id)

            for target_id in targets:
                target_char = self.character_manager.characters[target_id]
                target_state = self.combat_state["combatant_states"][target_id]
                hp_current = target_state["hp_current"]
                hp_max = target_state["hp_max"]

                # Get action description from metadata
                description = metadata.get("description", action_type)
                display = f"{description} → {target_char.name} (HP: {hp_current}/{hp_max})"

                options.append({
                    "action_type": action_type,
                    "display": display,
                    "params": {"target": target_id}
                })

            return options
        else:
            # Single option (no targeting)
            description = metadata.get("description", action_type)
            return [{
                "action_type": action_type,
                "display": description,
                "params": {}
            }]

    def _parse_hierarchical_action(
        self,
        char_id: str,
        category_key: str,
        action_item: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Parse hierarchical menu selection into action dict.

        **UPDATED (2026-01-03)**: Generic data-driven approach that uses
        action_item metadata directly (no hardcoded if/elif chains).

        Args:
            char_id: Actor char_id
            category_key: Selected category ("standard_actions", "utility", "bonus_actions")
            action_item: Selected action dict from _generate_action_options()

        Returns:
            {
                "actor": "aggi",
                "action_type": "attack",
                "target": "goblin_001"
            }
        """
        # Build action dict from action_item metadata
        action = {
            "actor": char_id,
            "action_type": action_item["action_type"]
        }

        # Merge in any parameters (target, weapon, etc.)
        action.update(action_item.get("params", {}))

        return action

    def _validate_action(self, action: Dict) -> bool:
        """
        Validate action is legal in current combat state.

        **OPTIMIZED (2026-01-03):** For dnd_engine actions, leverages their native
        _validate() method which checks range, line of sight, and prerequisites.
        This reduces validation code and improves correctness.

        Args:
            action: Action dict with actor, action_type, target, etc.

        Returns:
            True if action is valid, False otherwise
        """
        actor_id = action["actor"]
        action_type = action["action_type"]

        # Get action metadata from ACTION_REGISTRY
        metadata = self.action_resolver.ACTION_REGISTRY.get(action_type)
        if not metadata:
            self.logger.warning(f"Unknown action type: {action_type}")
            return False

        # Check action economy via metadata
        if not self._can_character_afford_action(actor_id, metadata):
            return False

        # Check character meets requirements
        character = self.character_manager.characters.get(actor_id)
        if not self._character_meets_requirements(character, metadata):
            return False

        # For dnd_engine/Roshar actions, let Action._validate() handle detailed checks
        if metadata.get("type") in ["dnd_action", "roshar_action"]:
            # dnd_engine Actions validate:
            # - Range/line of sight
            # - Action economy (via prerequisites)
            # - Target validity
            # - Resource costs
            # We only check high-level requirements here; Action.apply() will validate everything else
            return True

        # For non-dnd_engine actions, do manual validation
        # Validate target (if action requires targeting)
        if "target" in action:
            target_id = action["target"]

            # Target must be in combat
            if target_id not in self.combat_state["active_combatants"]:
                return False

            # Target must be alive
            if self._is_combatant_dead(target_id):
                return False

        return True

    def _consume_action(self, char_id: str, action_type: str):
        """
        Sync action economy from dnd_engine to combat state.

        **SIMPLIFIED (2026-01-03)**: dnd_engine Actions automatically consume action economy
        during action.apply(). This method syncs that state to combat_state for UI display only.

        Note: Action economy is ONLY tracked in dnd_engine. combat_state values are read-only
        mirrors for UI purposes.
        """
        entity = self.dnd_wrapper.entities[char_id]

        # Sync from dnd_engine to combat_state (UI display only)
        char_state = self.combat_state["combatant_states"][char_id]
        char_state["actions_remaining"] = entity.action_economy.actions
        char_state["bonus_actions_remaining"] = entity.action_economy.bonus_actions
        char_state["reaction_available"] = entity.action_economy.reactions > 0

    def _has_actions_remaining(self, char_id: str) -> bool:
        """
        Check if combatant has actions/bonus actions remaining.

        **SIMPLIFIED (2026-01-03):** Queries dnd_engine directly. No fallback.
        """
        entity = self.dnd_wrapper.entities[char_id]
        return (entity.action_economy.actions > 0 or
                entity.action_economy.bonus_actions > 0)

    def _advance_turn(self):
        """
        Advance to next combatant in initiative order.

        **OPTIMIZED (2026-01-03):** Uses dnd_engine's action_economy.reset() and enables
        TURN_START event triggers for condition durations.

        Process:
        1. Increment current_turn_index
        2. If wrapped around, new round (reset action economy via dnd_engine)
        3. Trigger TURN_START events for condition processing
        4. Skip unconscious/dead combatants
        """
        self.combat_state["current_turn_index"] += 1

        # Check if new round
        if self.combat_state["current_turn_index"] >= len(self.combat_state["initiative_order"]):
            self.combat_state["current_turn_index"] = 0
            self.combat_state["round_number"] += 1

            # Reset action economy for all combatants via dnd_engine
            for char_id in self.combat_state["active_combatants"]:
                entity = self.dnd_wrapper.entities.get(char_id)
                if entity and hasattr(entity, 'action_economy'):
                    entity.action_economy.reset()

                    # TODO: Trigger TURN_START events for conditions
                    # This is where dnd_engine's event system would fire TURN_START events
                    # for conditions that have turn-based duration (e.g., Blinded, Stormlight Infused)

                # Sync to combat state
                char_state = self.combat_state["combatant_states"][char_id]
                char_state["actions_remaining"] = 1
                char_state["bonus_actions_remaining"] = 1
                char_state["reaction_available"] = True

            self.logger.info(f"🔄 Round {self.combat_state['round_number']} begins")
            print(f"\n{'='*60}")
            print(f"  🔄 ROUND {self.combat_state['round_number']}")
            print(f"{'='*60}")

        # Skip unconscious/dead combatants
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
        Check end conditions using dnd_engine health system.

        **OPTIMIZED (2026-01-03):** Uses entity.health.is_dead()/is_unconscious() instead
        of manual HP checking. Enables proper D&D 5e death saves, temporary HP, and
        damage resistance tracking.

        Returns:
            (combat_ended: bool, reason: str)
        """
        # Check all hostiles defeated
        hostile_ids = [
            cid for cid, state in self.combat_state["combatant_states"].items()
            if state["is_hostile"]
        ]

        # Use dnd_engine's authoritative health system
        all_hostiles_dead = all(
            self._is_combatant_dead(hid)
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
            self._is_combatant_dead(pid)
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
        """
        Check if combatant is dead/unconscious using dnd_engine.

        **SIMPLIFIED (2026-01-03):** Uses entity.health system exclusively. No fallback.
        D&D 5e death save mechanics are handled entirely by dnd_engine.

        Returns:
            True if combatant is unconscious or dead, False otherwise
        """
        entity = self.dnd_wrapper.entities[char_id]
        return entity.health.is_unconscious() or entity.health.is_dead()

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
        """
        Build context for NPC AI decision.

        **SIMPLIFIED (2026-01-03):** Uses dnd_engine HP exclusively and dynamically discovers
        available actions from ACTION_REGISTRY (enables NPCs to use Roshar abilities automatically).

        Args:
            npc_char_id: NPC character ID

        Returns:
            Context dict for NPC AI with available actions and targets
        """
        npc_char = self.character_manager.characters[npc_char_id]
        entity = self.dnd_wrapper.entities[npc_char_id]

        # Get HP from dnd_engine
        npc_hp = entity.health.get_current_hit_points()
        npc_max_hp = entity.health.get_max_hit_points()

        # Dynamically get available actions from ACTION_REGISTRY
        available_actions = [
            action_type
            for action_type, metadata in self.action_resolver.ACTION_REGISTRY.items()
            if (self._can_character_afford_action(npc_char_id, metadata) and
                self._character_meets_requirements(npc_char, metadata))
        ]

        return {
            "npc": npc_char,
            "npc_hp": npc_hp,
            "npc_max_hp": npc_max_hp,
            "available_targets": self._get_valid_targets(npc_char_id),
            "available_actions": available_actions,  # Dynamic action discovery
            "allies": self._get_allies(npc_char_id),
            "enemies": self._get_enemies(npc_char_id),
            "round_number": self.combat_state["round_number"]
        }

    def _get_valid_targets(self, char_id: str) -> List[str]:
        """
        Get list of valid targets for character.

        **OPTIMIZED (2026-01-03):** Uses entity.health for proper death checks and enables
        optional range/line of sight validation via entity.senses.

        Args:
            char_id: Character ID

        Returns:
            List of valid target character IDs
        """
        entity = self.dnd_wrapper.entities.get(char_id)
        is_hostile = self.combat_state["combatant_states"][char_id]["is_hostile"]

        targets = []
        for cid, state in self.combat_state["combatant_states"].items():
            if cid == char_id:
                continue  # Can't target self

            # Use dnd_engine health check for proper death state
            if self._is_combatant_dead(cid):
                continue  # Can't target dead/unconscious

            # Hostiles target players, players target hostiles
            if is_hostile != state["is_hostile"]:
                # TODO: Optional range/line of sight check
                # if entity and hasattr(entity, 'senses'):
                #     target_entity = self.dnd_wrapper.entities.get(cid)
                #     if target_entity and entity.senses.can_see(target_entity):
                #         targets.append(cid)
                # else:
                #     targets.append(cid)

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

---

### Phase 3 Optimization Summary

**Completion Date:** 2026-01-03
**Analysis Document:** `docs/COMBAT_PLAN_METHOD_OPTIMIZATION_ANALYSIS.md`

The CombatSessionManager implementation above incorporates comprehensive optimizations identified through method-by-method analysis of all 28 methods. The optimizations maximize leverage of dnd_engine's battle-tested D&D mechanics while maintaining the generic, data-driven architecture.

#### Methods Optimized (8 total)

**High Priority Optimizations (4 methods):**

1. **`_check_end_conditions()`** (lines 2569-2609)
   - **Change:** Uses `entity.health.is_dead()/is_unconscious()` instead of manual HP checking
   - **Benefit:** Enables proper D&D 5e death saves, temporary HP, damage resistance tracking
   - **Lines Saved:** ~15 lines

2. **`_is_combatant_dead()`** (lines 2633-2649)
   - **Change:** Uses dnd_engine death save system to distinguish dead/unconscious/stabilized
   - **Benefit:** Proper D&D 5e unconscious mechanics, death save tracking, stabilization support
   - **Lines Saved:** ~3 lines

3. **`_can_character_afford_action()`** (lines 2289-2334)
   - **Change:** Uses `entity.action_economy.can_afford()` when available
   - **Benefit:** Eliminates sync issues between combat_state and dnd_engine, single source of truth
   - **Lines Saved:** ~10 lines

4. **`_validate_action()`** (lines 2456-2511)
   - **Change:** Leverages Action._validate() prerequisites for dnd_engine actions
   - **Benefit:** Range/LoS validation for free, reduces validation code, improves correctness
   - **Lines Saved:** ~20 lines

**Medium Priority Optimizations (2 methods):**

5. **`_get_valid_targets()`** (lines 2746-2783)
   - **Change:** Uses entity.health for death checks, enables optional range/LoS via entity.senses
   - **Benefit:** Proper death state checking, future range/LoS support ready
   - **Lines Changed:** ~5 lines

6. **`_advance_turn()`** (lines 2565-2612)
   - **Change:** Triggers TURN_START events for condition processing
   - **Benefit:** Condition events work correctly (duration tracking, turn-based effects)
   - **Lines Added:** ~3 lines (TODO marker for event trigger)

**Low Priority Optimizations (2 methods):**

7. **`_has_actions_remaining()`** (lines 2549-2563)
   - **Change:** Queries dnd_engine directly when available
   - **Benefit:** Consistency with authoritative source
   - **Lines Saved:** ~2 lines

8. **`_build_npc_context()`** (lines 2730-2772)
   - **Change:** Dynamic action discovery from ACTION_REGISTRY, dnd_engine HP
   - **Benefit:** NPCs can use Roshar abilities automatically, better AI decisions
   - **Lines Changed:** ~5 lines

#### Methods Already Optimal (16 total)

The following methods use the generic, data-driven architecture and don't require changes:

- `run_combat_loop()` - High-level orchestration
- `_execute_player_turn()` - UI/input handling
- `_execute_npc_turn()` - AI decision logic
- `_get_available_actions()` - Already uses ACTION_REGISTRY dynamically
- `_parse_hierarchical_action()` - Already metadata-driven
- `_consume_action()` - Already syncs from dnd_engine
- `_log_combat_action()` - Simple logging
- `_display_combat_start()` - UI output
- `_determine_outcome()` - Game logic mapping
- `_get_current_actor()` - Simple accessor
- `_is_player()` - Simple check
- `_get_allies()` / `_get_enemies()` - Simple filtering
- `_get_fallback_action()` - AI safety net
- `_categorize_action()` - UI categorization
- `_generate_action_options()` - UI generation
- `_character_meets_requirements()` - Game-specific logic

#### Impact Summary

**Code Reduction:**
- **High Priority Changes:** ~55-60 lines saved (including fallback removal)
- **Total Savings:** ~55-60 lines (8-9% reduction from original ~700 lines)
- **Final Size:** ~640-645 lines for CombatSessionManager

**Simplification:**
- ✅ **No Fallbacks** - All methods assume dnd_engine is available and working
- ✅ **Direct Entity Access** - Use `entities[char_id]` instead of `entities.get(char_id)`
- ✅ **Simpler Logic** - Removed conditional checks for dnd_engine availability
- ✅ **Cleaner Code** - Less defensive programming, more straightforward implementation

**New Capabilities Enabled:**
- ✅ **Death Saves** - Proper D&D 5e unconscious/stabilized mechanics
- ✅ **Temporary HP** - Automatically tracked by dnd_engine
- ✅ **Damage Resistance** - Applied correctly via health system
- ✅ **Range/Line of Sight** - Actions validate targeting automatically (future)
- ✅ **Condition Events** - Turn-based conditions work correctly
- ✅ **Dynamic NPC Actions** - NPCs can use Roshar abilities without code changes

**Architectural Improvements:**
- ✅ **Single Source of Truth** - dnd_engine is authoritative for HP, action economy, conditions
- ✅ **No State Duplication** - combat_state is UI-only, dnd_engine is authoritative
- ✅ **Better D&D 5e Compliance** - Proper death/unconscious/stabilized rules
- ✅ **Event System Ready** - Reactions and interrupts work when implemented
- ✅ **Improved Maintainability** - Less code to maintain, more reliance on battle-tested dnd_engine
- ✅ **Fail Fast** - Entity lookup failures raise exceptions immediately for easier debugging

#### Implementation Approach

The optimizations are integrated directly into the Phase 3 implementation plan above. When implementing:

1. **Start with High Priority methods** - These provide the most benefit and reduce risk of HP sync issues
2. **Add Medium Priority enhancements** - Enable condition events and improved targeting
3. **Polish with Low Priority changes** - Consistency improvements and dynamic NPC actions
4. **Test thoroughly** - Verify HP tracking, death saves, action economy consumption, range/LoS
5. **Document edge cases** - Note any differences between dnd_engine and combat_state behavior

**Risk Mitigation:**
- All methods assume dnd_engine is available and properly initialized
- Comprehensive logging for debugging any entity lookup failures
- Unit tests for each optimized method before integration testing

---

**2. components/combat/combat_action_resolver.py** (~150 lines - SIMPLIFIED)

**MAJOR UPDATE (2026-01-03)**: Unified dispatcher for dnd_engine Actions + Roshar extensions.
**UPDATE (v4.1)**: ACTION_REGISTRY moved to separate modular file for easier expansion.

```python
from dnd.actions import Attack, Move, WeaponSlot
from dnd.conditions import Dashing
from dnd.core.base_conditions import Duration, DurationType
from components.combat.roshar_actions import Lashing, ShardbladeAttack, ProgressionHealing
from components.combat.action_registry import ACTION_REGISTRY  # Modular registry
from config.logging_config import get_logger

logger = get_logger(__name__)


class CombatActionResolver:
    """
    Unified action resolver: dnd_engine foundation + Roshar extensions.

    **Design Philosophy:**
    - D&D 5e actions → Use dnd_engine native Actions
    - Roshar abilities → Custom Actions following dnd_engine patterns
    - Both types integrate seamlessly via event system
    - ACTION_REGISTRY is external for modular expansion

    **Action Registry:**
    - Minimal initial registry (5-7 core actions) - Phase 3
    - Expanded post-Phase 3 with full Surge abilities (~30+ actions)
    - See: components/combat/action_registry.py and docs/ROSHAR_COMBAT_MECHANICS_INTEGRATION.md
    """

    def __init__(self, dnd_engine_wrapper, character_manager, combat_state):
        self.dnd_wrapper = dnd_engine_wrapper
        self.character_manager = character_manager
        self.combat_state = combat_state
        self.logger = get_logger(__name__)


    def resolve_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Unified action resolution for D&D + Roshar.

        Args:
            action: {
                "actor": "char_id",
                "action_type": "attack" | "lashing" | "progression_healing",
                "target": "target_char_id",  # Optional
                ...params
            }

        Returns:
            {
                "success": True,
                "event": AttackEvent | LashingEvent | ...,
                "description": "Human-readable result"
            }
        """
        action_type = action["action_type"]

        # Lookup in external registry
        if action_type not in ACTION_REGISTRY:
            self.logger.error(f"Unknown action type: {action_type}")
            return {
                "success": False,
                "error": f"Unknown action: {action_type}"
            }

        metadata = ACTION_REGISTRY[action_type]

        # Dispatch based on type
        if metadata["type"] in ["dnd_action", "roshar_action"]:
            return self._execute_action(action, metadata)
        elif metadata["type"] in ["dnd_condition", "roshar_condition"]:
            return self._apply_condition(action, metadata)
        else:
            return {
                "success": False,
                "error": f"Invalid action type metadata: {metadata['type']}"
            }

    def _execute_action(self, action: Dict, metadata: Dict) -> Dict:
        """
        Execute Action (D&D or Roshar) via dnd_engine event system.

        Uses: dnd_wrapper.execute_dnd_action(action_class, **kwargs)
        """
        action_class = metadata["action_class"]
        actor_uuid = self._get_entity_uuid(action["actor"])

        # Build action parameters
        kwargs = {
            "source_entity_uuid": actor_uuid
        }

        # Add target if present
        if "target" in action and action["target"]:
            kwargs["target_entity_uuid"] = self._get_entity_uuid(action["target"])

        # Add additional parameters from metadata
        for param in metadata.get("params", []):
            if param in action:
                kwargs[param] = action[param]
            elif param == "weapon_slot":
                # Default to main hand
                kwargs[param] = WeaponSlot.MAIN_HAND

        # Execute via dnd_engine
        try:
            event = self.dnd_wrapper.execute_dnd_action(action_class, **kwargs)

            # Check if action succeeded
            success = not event.canceled

            # Extract results based on action type
            if isinstance(event, AttackEvent):
                result = {
                    "success": success,
                    "event": event,
                    "attack_outcome": event.attack_outcome,
                    "damage": sum(roll.total for roll in event.damage_rolls) if event.damage_rolls else 0,
                    "critical": event.attack_outcome == AttackOutcome.CRIT_HIT,
                    "description": self._format_attack_result(event)
                }
            elif isinstance(event, LashingEvent):
                result = {
                    "success": success,
                    "event": event,
                    "lashing_type": event.lashing_type,
                    "stormlight_consumed": event.stormlight_cost,
                    "description": f"Lashing applied to {event.target_entity_uuid}"
                }
            else:
                # Generic result
                result = {
                    "success": success,
                    "event": event,
                    "description": event.status_message
                }

            # Update combat state HP if damage dealt
            if hasattr(event, 'target_entity_uuid') and hasattr(event, 'damage_rolls'):
                self._sync_hp_to_combat_state(event.target_entity_uuid)

            return result

        except Exception as e:
            self.logger.error(f"Action execution failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _apply_condition(self, action: Dict, metadata: Dict) -> Dict:
        """Apply Condition (D&D or Roshar) via dnd_engine condition system"""
        condition_class = metadata["condition_class"]
        actor_uuid = self._get_entity_uuid(action["actor"])

        # Build condition parameters
        kwargs = {
            "source_entity_uuid": actor_uuid,
            "target_entity_uuid": actor_uuid  # Most conditions target self
        }

        # Add duration if specified in metadata
        if metadata.get("duration"):
            kwargs["duration"] = metadata["duration"]

        # Add custom parameters
        for param in metadata.get("params", []):
            if param in action:
                kwargs[param] = action[param]

        # Apply via dnd_engine
        try:
            event = self.dnd_wrapper.apply_condition(condition_class, **kwargs)

            success = not event.canceled

            return {
                "success": success,
                "event": event,
                "condition": condition_class.__name__,
                "description": metadata.get("description", "Condition applied")
            }

        except Exception as e:
            self.logger.error(f"Condition application failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _get_entity_uuid(self, char_id: str) -> UUID:
        """Get dnd_engine entity UUID from character ID"""
        entity = self.dnd_wrapper.entities.get(char_id)
        if entity:
            return entity.uuid
        else:
            raise ValueError(f"Entity not found for character {char_id}")

    def _sync_hp_to_combat_state(self, target_uuid: UUID):
        """Sync HP from dnd_engine entity to combat state"""
        # Find character by UUID
        for char_id, entity in self.dnd_wrapper.entities.items():
            if entity.uuid == target_uuid:
                char = self.character_manager.characters.get(char_id)
                if char:
                    self.combat_state["combatant_states"][char_id]["hp_current"] = char.hit_points["current"]
                break

    def _format_attack_result(self, event: AttackEvent) -> str:
        """Format attack event into human-readable description"""
        if event.attack_outcome == AttackOutcome.HIT:
            damage = sum(roll.total for roll in event.damage_rolls)
            return f"Hit! Dealt {damage} damage."
        elif event.attack_outcome == AttackOutcome.CRIT_HIT:
            damage = sum(roll.total for roll in event.damage_rolls)
            return f"Critical Hit! Dealt {damage} damage!"
        elif event.attack_outcome == AttackOutcome.MISS:
            return "Miss!"
        elif event.attack_outcome == AttackOutcome.CRIT_MISS:
            return "Critical Miss!"
        else:
            return event.status_message
```

**Key Changes:**
1. **Unified Registry** - Single ACTION_REGISTRY for D&D + Roshar actions
2. **Type-based Dispatch** - `dnd_action`, `roshar_action`, `dnd_condition`, `roshar_condition`
3. **Event-based Resolution** - All actions return Events with standardized structure
4. **Automatic State Sync** - HP and other state synced from dnd_engine to combat_state
5. **Extensibility** - Add new Roshar actions by creating custom Action classes and registering

**Benefits:**
- **~200 lines** (down from ~400 in original plan)
- **Battle-tested D&D mechanics** from dnd_engine
- **Seamless Roshar integration** using same patterns
- **Event system** enables reactions (Shield, Counterspell, etc.)
- **Easy to extend** - just add to ACTION_REGISTRY

**3. components/combat/action_registry.py** (~150 lines - NEW v4.1)

**ADDED (2026-01-03)**: Modular ACTION_REGISTRY for easier expansion and maintenance.

```python
"""
Combat Action Registry - Modular Action Definitions

This file defines all available combat actions for the Roshar D&D combat system.
Actions are registered here with metadata for generic discovery and validation.

**Design Philosophy:**
- D&D 5e actions use dnd_engine native implementations
- Roshar-specific actions implemented as custom Action classes
- Registry enables metadata-driven discovery (no hardcoded action lists)

**Expansion Plan:**
- Phase 3: Minimal registry (5-7 core actions)
- Post-Phase 3: Full Surge abilities (~30+ actions)
- See: docs/ROSHAR_COMBAT_MECHANICS_INTEGRATION.md for complete Surge list
"""

from dnd.actions import Attack, Move, WeaponSlot
from dnd.conditions import Dashing, Dodging
from dnd.core.base_conditions import Duration, DurationType

# Import Roshar actions (to be implemented in Phase 3)
from components.combat.roshar_actions import (
    Lashing,
    ShardbladeAttack,
    ProgressionHealing
)


# ============================================================================
# MINIMAL INITIAL REGISTRY (Phase 3)
# ============================================================================

ACTION_REGISTRY = {
    # ========================================================================
    # D&D 5e STANDARD ACTIONS (via dnd_engine)
    # ========================================================================

    "attack": {
        "type": "dnd_action",
        "action_class": Attack,
        "description": "Attack with weapon",
        "params": ["target_entity_uuid", "weapon_slot"],
        "cost_type": "actions",
        "cost": 1,
        "requires": None
    },

    "move": {
        "type": "dnd_action",
        "action_class": Move,
        "description": "Move to new position",
        "params": ["end_position"],
        "cost_type": "movement",
        "cost": None,  # Variable based on distance
        "requires": None
    },

    # ========================================================================
    # D&D 5e STANDARD CONDITIONS (via dnd_engine)
    # ========================================================================

    "dash": {
        "type": "dnd_condition",
        "condition_class": Dashing,
        "description": "Double movement speed",
        "duration": Duration(1, DurationType.TURNS),
        "cost_type": "actions",
        "cost": 1,
        "requires": None
    },

    "dodge": {
        "type": "dnd_condition",
        "condition_class": Dodging,
        "description": "Impose disadvantage on attacks against you",
        "duration": Duration(1, DurationType.TURNS),
        "cost_type": "actions",
        "cost": 1,
        "requires": None
    },

    # ========================================================================
    # ROSHAR-SPECIFIC ACTIONS (Custom implementations)
    # ========================================================================

    "lashing": {
        "type": "roshar_action",
        "action_class": Lashing,
        "description": "Manipulate gravity (Windrunner/Skybreaker)",
        "params": ["target_entity_uuid", "lashing_type", "target_direction"],
        "cost_type": "actions",
        "cost": 1,
        "stormlight_cost": 1,
        "requires_order": ["Windrunner", "Skybreaker"],
        "min_surgebinding_level": 1,
        "surge_type": "Gravitation"
    },

    "shardblade_attack": {
        "type": "roshar_equipment",
        "action_class": ShardbladeAttack,
        "description": "Attack with Shardblade (soul damage)",
        "params": ["target_entity_uuid"],
        "cost_type": "actions",
        "cost": 1,
        "requires": "shardblade_summoned"
    },

    "progression_healing": {
        "type": "roshar_action",
        "action_class": ProgressionHealing,
        "description": "Heal wounds with Progression (Edgedancer/Truthwatcher)",
        "params": ["target_entity_uuid", "healing_amount"],
        "cost_type": "actions",
        "cost": 1,
        "stormlight_cost": 2,
        "requires_order": ["Edgedancer", "Truthwatcher"],
        "min_surgebinding_level": 2,
        "surge_type": "Progression"
    }
}


# ============================================================================
# FUTURE EXPANSION (Post-Phase 3)
# ============================================================================
"""
Planned additions (~30+ actions total):

GRAVITATION SURGE (Windrunner, Skybreaker):
- full_lashing: Reverse personal gravity completely
- reverse_lashing: Create gravity source on object
- gravitation_jump: Launch into air with partial lashing

ADHESION SURGE (Windrunner, Bondsmith):
- adhesion_bind: Stick objects together
- adhesion_shield: Create pressure barrier
- adhesion_climb: Stick to surfaces

DIVISION SURGE (Dustbringer, Skybreaker):
- division_blast: Disintegrate object
- division_flame: Create controlled fire
- friction_manipulation: Reduce friction

PROGRESSION SURGE (Edgedancer, Truthwatcher):
- regrowth_major: Heal critical wounds (3d8+mod)
- regrowth_minor: Heal light wounds (1d8+mod)
- life_sense: Detect living creatures

TRANSFORMATION SURGE (Lightweaver, Elsecaller):
- soulcasting_stone: Transform to stone
- soulcasting_smoke: Transform to smoke
- soulcasting_fire: Transform to fire

TRANSPORTATION SURGE (Elsecaller, Willshaper):
- elsecalling: Teleport through Cognitive Realm
- cognitive_step: Short-range teleport (30 ft)

ILLUMINATION SURGE (Lightweaver, Truthwatcher):
- illusion_visual: Create visual illusion
- illusion_sound: Create auditory illusion
- illusion_full: Create full sensory illusion

TENSION SURGE (Stoneward, Willshaper):
- tension_harden: Increase object durability
- tension_soften: Weaken object structure

COHESION SURGE (Stoneward, Dustbringer):
- cohesion_mold: Shape stone/crystal
- cohesion_shatter: Break crystalline structures

SPIRITUAL ADHESION (Bondsmith - unique):
- spiritual_connection: Form Connection bond
- spiritual_healing: Heal spirit/Connection damage

SHARDPLATE ACTIONS:
- shardplate_summon: Summon living Shardplate (4th Ideal)
- shardplate_repair: Repair Shardplate with Stormlight
- shardplate_strength: Enhanced strength burst (+4 STR for 1 turn)

SHARDBLADE ACTIONS:
- shardblade_summon: Summon Shardblade (1 Bonus Action)
- shardblade_dismiss: Dismiss to mist (Free Action)
- shardblade_form_change: Change living blade form (Bonus Action)

VOIDBINDING (Fused - enemy abilities):
- voidbinding_corruption: Spread Voidlight corruption
- gravity_spren: Manipulate gravity (similar to Lashing)
- destruction_surge: Enhanced Division-like power

See docs/ROSHAR_COMBAT_MECHANICS_INTEGRATION.md for complete specifications.
"""


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_actions_by_type(action_type: str) -> Dict[str, Dict]:
    """Get all actions of specified type."""
    return {
        name: metadata
        for name, metadata in ACTION_REGISTRY.items()
        if metadata["type"] == action_type
    }


def get_actions_for_radiant_order(order: str) -> Dict[str, Dict]:
    """Get all actions available to specific Radiant Order."""
    return {
        name: metadata
        for name, metadata in ACTION_REGISTRY.items()
        if ("requires_order" in metadata and
            order in metadata["requires_order"])
    }


def get_actions_requiring_stormlight() -> Dict[str, Dict]:
    """Get all actions that consume Stormlight."""
    return {
        name: metadata
        for name, metadata in ACTION_REGISTRY.items()
        if "stormlight_cost" in metadata
    }
```

**Registry Structure:**

Each action entry contains:
- `type`: `"dnd_action"`, `"dnd_condition"`, `"roshar_action"`, `"roshar_equipment"`
- `action_class`/`condition_class`: Python class implementing the action
- `description`: Human-readable description
- `params`: List of required parameters
- `cost_type`: `"actions"`, `"bonus_actions"`, `"reactions"`, `"movement"`
- `cost`: Action economy cost (integer or None for variable)
- `stormlight_cost`: Stormlight spheres consumed (Roshar actions only)
- `requires`: Prerequisites (e.g., `"shardblade_summoned"`)
- `requires_order`: Radiant Orders that can use (Roshar actions only)
- `min_surgebinding_level`: Minimum Ideal level required
- `surge_type`: Which Surge this action uses

**Expansion Path:**

1. **Phase 3 (Initial)**: 7 core actions
   - 2 D&D actions (attack, move)
   - 2 D&D conditions (dash, dodge)
   - 3 Roshar actions (lashing, shardblade_attack, progression_healing)

2. **Post-Phase 3 (Full Surge System)**: ~30+ actions
   - 10 Surges × 3-4 abilities each
   - Shardplate actions (summon, repair, strength)
   - Shardblade actions (summon, dismiss, form change)
   - Voidbinding (enemy abilities)

3. **Future (Advanced)**: ~50+ actions
   - Resonance abilities (Order-specific synergies)
   - Herald abilities (advanced powers)
   - Fused forms (Regal powers)
   - Listener Rhythms (Singer abilities)

**Benefits:**
- ✅ **Modular:** Add actions without modifying CombatSessionManager
- ✅ **Discoverable:** Helper functions for querying by type/order/requirements
- ✅ **Maintainable:** Single file for all action definitions
- ✅ **Extensible:** Clear path from minimal (7) to full (~30+) to advanced (~50+)
- ✅ **Type-Safe:** Enforced metadata structure for validation

**4. components/combat/combat_narrative_generator.py** (~400 lines)

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

#### UI Improvement: Hierarchical Action Menu

**UPDATED (2026-01-03)**: Changed action selection from flat list to hierarchical menu system.

**Problem Identified:**
- Original plan used `_get_available_actions()` returning flat list of ALL possible actions
- With 5 enemies + 10 abilities = **20+ menu items**, causing UI overload
- Example: "1. Attack Goblin 1", "2. Attack Goblin 2", "3. Attack Goblin 3", "4. Attack Shaman 1", "5. Attack Shaman 2", "6. Dodge", "7. Dash", "8. Disengage", "9. Help", "10. Cast Healing Word on self", "11. Cast Shield", etc.

**Solution: Two-Level Hierarchical Menu**

**Level 1 - Action Categories:**
```
📋 Choose Action Type:
  1. ⚔️ Attack - Attack a target with your weapon (5 options)
  2. 🛡️ Defend/Move - Defensive and movement actions (4 options)
  3. ⚡ Bonus Actions - Special bonus action abilities (2 options)

aggi> Choose action type (1-3): 1
```

**Level 2 - Specific Actions:**
```
⚔️ Attack - Choose Target/Action:
  1. Goblin Warrior (HP: 7/7)
  2. Goblin Warrior (HP: 7/7)
  3. Goblin Shaman (HP: 12/12)
  4. Bandit Leader (HP: 25/30)
  5. Bandit Archer (HP: 18/18)

aggi> Choose action (1-5): 3
```

**Benefits:**
- **Reduced cognitive load**: Never more than 5-7 items per screen
- **Better organization**: Actions grouped by purpose
- **Scalability**: Works with 1 enemy or 20 enemies
- **Clarity**: Visual icons and HP indicators for quick scanning

**Implementation Changes:**
1. `_get_available_actions()` returns `Dict[str, Dict]` (categories) instead of `List[str]` (flat list)
2. `_execute_player_turn()` implements two-level menu navigation
3. `_parse_hierarchical_action()` replaces `_parse_action_choice()` to handle structured selection

**User Experience Example:**
```
Level 1: Choose broad category (Attack? Defend? Special ability?)
   ↓
Level 2: Choose specific target/action within that category
   ↓
Action executed with clear feedback
```

#### Phase 3 Architecture Summary

**Key Architectural Improvements (2026-01-03):**

1. **Generic Action Discovery**
   - `_get_available_actions()` queries ACTION_REGISTRY instead of hardcoding action lists
   - Automatically discovers D&D 5e actions and Roshar extensions
   - New actions can be added to registry without modifying combat session code

2. **Metadata-Driven Validation**
   - `_validate_action()` uses ACTION_REGISTRY metadata for requirements checking
   - Leverages dnd_engine's cost_type for action economy
   - No hardcoded action type lists

3. **Metadata-Driven Consumption**
   - `_consume_action()` queries action metadata for cost type
   - Delegates to dnd_engine's action economy system
   - Handles actions, bonus actions, reactions generically

4. **dnd_engine Integration**
   - `_advance_turn()` uses entity.action_economy.reset()
   - All action resolution delegated to CombatActionResolver
   - Combat state synced from dnd_engine Entities

5. **Extensibility**
   - Adding new Roshar action: Just add to ACTION_REGISTRY
   - No code changes needed in CombatSessionManager
   - Works with any action following dnd_engine patterns

**Code Reduction:**
- Old approach: ~400 lines with hardcoded if/elif chains for each action
- New approach: ~300 lines with generic metadata dispatch
- ~25% reduction + infinite extensibility

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

### Phase 1 ✅ COMPLETE
- [x] NPC generation creates valid D&D stats
- [x] Template loading works (5 templates: Goblin, Bandit, Skeleton, Wolf, Guard)
- [x] Stat validation catches errors
- [x] All Phase 1 tests pass (8/8 unit tests passing - 100% success rate)
- [x] Pydantic validation enforces CharacterData format
- [x] Automatic repair logic handles LLM mistakes
- [x] Haystack 2.0 integration consistent with existing agents

### Phase 1.5 (NPC Registry) ✅ COMPLETE
- [x] NPCStatLoader created and tested
- [x] Herald NPCs converted to JSON format (Kalak, Nale)
- [x] Integration with game initialization (lines 273-284)
- [x] Case-insensitive and partial name matching
- [x] All integration tests pass (10/10 tests passing - 100% success rate)
- [x] CharacterData format validation
- [x] Integration with CharacterManager verified
- [x] Documentation complete (3 new docs created)

### Phase 2 (Combat Initialization) ✅ COMPLETE
- [x] Combat initializes from scenario
- [x] Enemies extracted from scene/gm_notes (LLM parsing with JSON validation)
- [x] Predefined NPCs loaded from NPC registry (simplified approach)
- [x] Generated NPCs created for undefined enemies (multiple instances supported)
- [x] Initiative rolls correctly (d20 + DEX mod, sorted descending)
- [x] Combat state dict created properly (combatants, initiative order, states)
- [x] All Phase 2 tests pass (21/21 tests passing - 100% success rate)
- [x] Combat trigger detection (flag + keyword fallback)
- [x] Graceful fallback handling (no registry, no enemies, no trigger)

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
│   │   ├── __init__.py                            ✅ Created
│   │   ├── npc_stat_generator.py                 ✅ Created (475 lines)
│   │   ├── combat_initializer.py                 ✅ Created (649 lines)
│   │   ├── action_registry.py                    ⬜ Phase 3 (~150 lines) NEW v4.1
│   │   ├── combat_session_manager.py             ⬜ Phase 3 (~700 lines)
│   │   ├── combat_action_resolver.py             ⬜ Phase 3 (~150 lines)
│   │   ├── combat_narrative_generator.py         ⬜ Phase 3 (~400 lines)
│   │   └── roshar_actions.py                     ⬜ Phase 3 (~400 lines)
│   ├── character_manager.py                       ✅ Updated (+NPC methods)
│   └── game_engine.py                             (no changes needed)
│
├── core/
│   ├── npc_stat_loader.py                         ✅ Created (200 lines) - NEW
│   └── game_initialization.py                     ✅ Updated (NPC registry)
│
├── agents/
│   ├── combat_agent.py                            ⬜ Phase 4 (~400 lines) NEW
│   ├── npc_ai_agent.py                            ⬜ Phase 4 (~200 lines) NEW
│   └── scenario_generator_agent.py                (+30 lines - prompt)
│
├── orchestrator/
│   └── pipeline_integration.py                    ⬜ Phase 4 (+50 lines)
│
├── data/
│   ├── npc_templates.json                         ✅ Created (174 lines) NEW
│   └── players/
│       ├── kalak_herald.json                      ✅ Created NEW
│       ├── nale_herald.json                       ✅ Created NEW
│       ├── kalak_herald.txt                       (original - retained)
│       └── nale_herald.txt                        (original - retained)
│
├── tests/
│   ├── combat/                                    # NEW
│   │   ├── __init__.py                            ✅ Created
│   │   ├── test_npc_stat_generator.py            ✅ Created (358 lines)
│   │   ├── test_combat_initializer.py            ✅ Created (21/21 tests passing)
│   │   ├── test_combat_session_manager.py        ⬜ Phase 3 (~400 lines)
│   │   ├── test_combat_action_resolver.py        ⬜ Phase 3 (~200 lines)
│   │   ├── test_combat_integration.py            ⬜ Phase 4 (~300 lines)
│   │   └── test_combat_e2e.py                    ⬜ Phase 4 (~200 lines)
│   └── test_npc_registry_integration.py           ✅ Created (290 lines) NEW
│
├── docs/
│   ├── COMBAT_ENGINE_IMPLEMENTATION_PLAN.md       ✅ Updated (THIS FILE)
│   ├── COMBAT_PLAN_NPC_INTEGRATION_GAPS.md        ✅ Created NEW
│   ├── NPC_JSON_CONVERSION_COMPLETE.md            ✅ Created NEW
│   ├── PHASE_1_IMPLEMENTATION_COMPLETE.md         ✅ Created NEW
│   └── COMBAT_AGENT_ARCHITECTURE_DECISION.md      ✅ Created
│
└── haystack_dnd_game.py                            (no changes needed yet)

✅ NEW FILES CREATED: 12 (includes combat_initializer.py)
✅ MODIFIED FILES: 3
✅ TOTAL NEW LINES: ~2,400 (includes 649 lines from combat_initializer.py)
⬜ REMAINING FILES: 11 (includes action_registry.py)
⬜ REMAINING LINES: ~3,550
```

**Progress Summary:**
- **Phase 1:** 100% Complete (4 files, 8/8 tests passing)
- **Phase 1.5:** 100% Complete (7 files, 10/10 tests passing)
- **Phase 2:** 100% Complete (1 file, 21/21 tests passing) ✅
- **Overall:** ~40% Complete (up from 30%)

**v4.1 Updates:**
- ✅ All fallback logic removed (simplified implementation)
- ✅ ACTION_REGISTRY moved to modular file (easier expansion)
- ✅ Minimal registry defined (7 core actions)
- ✅ Expansion path documented (~30+ actions post-Phase 3)

---

## Phase 5: Future Enhancements

### Natural Language Action Input (Future)

**ADDED (2026-01-03)**: Future enhancement for free-form action input using LLM parsing.

**Current Approach:** Hierarchical menu system (implemented in Phase 3)
- Works well for structured action selection
- Prevents UI overload with 2-level navigation
- Clear and predictable UX

**Future Enhancement:** Natural language + LLM action parser
- Allow players to type free-form actions: `"I attack the goblin shaman with my longsword"`
- LLM parses intent and maps to game action
- Fallback to hierarchical menu if parsing fails

#### Benefits of Natural Language Input

**Improved Immersion:**
```
Current (Menu):
  📋 Choose Action Type:
    1. ⚔️ Attack
  aggi> 1
  ⚔️ Attack - Choose Target:
    1. Goblin Shaman (HP: 12/12)
  aggi> 1

Future (Natural Language):
  aggi> I attack the goblin shaman with my longsword
  ✅ Attacking Goblin Shaman with longsword... [rolls dice]
```

**More Expressive:**
- "I attack the goblin while positioning myself to protect the cleric"
- "I dodge behind the pillar and shout a warning to my allies"
- "I cast Healing Word on myself and move toward the exit"

**Flexible Intent:**
- Parser can infer targets: "attack the wounded one" → selects lowest HP enemy
- Parser can suggest alternatives: "cast fireball" → "You don't have spell slots. Use menu?"
- Parser can handle creative actions: "throw sand in their eyes" → improvised action

#### Implementation Design

**1. Action Parser Component** (`components/combat/action_parser.py` ~300 lines)

```python
class NaturalLanguageActionParser:
    """
    Parse natural language action input using LLM.

    Process:
    1. Get player text input: "I attack the goblin with my sword"
    2. LLM extracts action structure
    3. Validate against game rules
    4. Return action dict or error
    5. Fallback to hierarchical menu if parsing fails
    """

    def __init__(self, llm, character_manager, combat_state):
        self.llm = llm
        self.character_manager = character_manager
        self.combat_state = combat_state

    def parse_action(self, player_input: str, actor_id: str) -> Dict[str, Any]:
        """
        Parse natural language action into structured action dict.

        Args:
            player_input: "I attack the goblin shaman with my longsword"
            actor_id: "aggi"

        Returns:
            {
                "actor": "aggi",
                "action_type": "attack",
                "target": "goblin_002",
                "weapon": "longsword",
                "confidence": 0.95
            }
            or
            {
                "error": "Could not parse action",
                "fallback_to_menu": True
            }
        """
        # Build context for LLM
        context = self._build_combat_context(actor_id)

        # LLM prompt
        system_prompt = """You are a D&D combat action parser.

Given a player's natural language input, extract the structured action.

Context:
- Available targets: {targets}
- Character weapons: {weapons}
- Character abilities: {abilities}
- Current HP: {hp}

Player input: "{input}"

Output JSON:
{
    "action_type": "attack" | "dodge" | "dash" | "cast_spell" | "use_item",
    "target": "char_id" or null,
    "weapon": "weapon_name" or null,
    "spell": "spell_name" or null,
    "confidence": 0.0-1.0
}

If ambiguous or invalid, return:
{"error": "reason", "confidence": 0.0}
"""

        # Call LLM
        response = self.llm.run(messages=[
            ChatMessage.from_system(system_prompt.format(**context)),
            ChatMessage.from_user(player_input)
        ])

        # Parse response
        try:
            action = json.loads(response['replies'][0].content)

            if "error" in action or action.get("confidence", 0) < 0.7:
                # Low confidence - fallback to menu
                return {"error": action.get("error", "Low confidence"), "fallback_to_menu": True}

            # Validate action
            if not self._validate_parsed_action(action, actor_id):
                return {"error": "Invalid action", "fallback_to_menu": True}

            return action

        except Exception as e:
            return {"error": str(e), "fallback_to_menu": True}

    def _build_combat_context(self, actor_id: str) -> Dict[str, Any]:
        """Build context for LLM action parser"""
        # Get available targets
        targets = self._get_valid_targets(actor_id)
        target_names = [
            f"{self.character_manager.characters[tid].name} ({tid})"
            for tid in targets
        ]

        # Get character weapons and abilities
        character = self.character_manager.characters[actor_id]
        weapons = [w["name"] for w in character.attacks] if hasattr(character, 'attacks') else []

        return {
            "targets": target_names,
            "weapons": weapons,
            "abilities": [],  # TODO: Get from character
            "hp": self.combat_state["combatant_states"][actor_id]["hp_current"]
        }

    def _validate_parsed_action(self, action: Dict, actor_id: str) -> bool:
        """Validate parsed action is legal"""
        # Check target exists
        if action.get("target") and action["target"] not in self.combat_state["active_combatants"]:
            return False

        # Check actor has actions remaining
        actor_state = self.combat_state["combatant_states"][actor_id]
        if actor_state["actions_remaining"] <= 0:
            return False

        return True
```

**2. Integration with CombatSessionManager**

Update `_execute_player_turn()` to offer natural language option:

```python
def _execute_player_turn(self, player_char_id: str):
    """Execute player turn with natural language option"""

    # Display status
    print("\n" + "="*60)
    print(self.narrative_gen.generate_combat_status(self.combat_state))
    print("="*60)

    # Offer input mode selection
    print("\n📋 Choose Input Mode:")
    print("  1. 💬 Natural Language (type your action)")
    print("  2. 📋 Menu Selection (guided menus)")

    mode = input(f"\n{player_char_id}> Choose mode (1-2): ").strip()

    if mode == "1":
        # Natural language mode
        action = self._get_action_natural_language(player_char_id)
    else:
        # Hierarchical menu mode (default)
        action = self._get_action_hierarchical_menu(player_char_id)

    # Rest of execution remains same
    self._execute_action(action)
```

**3. Example Flow**

```
⚔️ COMBAT - Round 2

Current combatants:
  • Aggi (HP: 18/25) - Your turn
  • Goblin Warrior (HP: 7/7)
  • Goblin Shaman (HP: 12/12)

📋 Choose Input Mode:
  1. 💬 Natural Language (type your action)
  2. 📋 Menu Selection (guided menus)

aggi> Choose mode (1-2): 1

aggi> I attack the goblin shaman with my longsword

🎲 Parsing action...
✅ Action understood: Attack Goblin Shaman with longsword

🎲 Rolling attack: d20(15) + 5 = 20 vs AC 13 → HIT!
🎲 Rolling damage: 1d8(6) + 3 = 9 slashing damage

⚔️ You swing your longsword at the Goblin Shaman, striking true!
   The blade bites deep into the creature's shoulder.

   Goblin Shaman: 12 → 3 HP (wounded!)
```

#### Implementation Estimate

- **Effort:** 2-3 days
- **Files:** 1 new component + tests
- **Dependencies:** Requires Phase 3 complete (hierarchical menu as fallback)
- **Risk:** Low (fallback ensures combat never breaks)

#### When to Implement

**Recommended Timeline:**
1. **Phase 3 Complete:** Hierarchical menu system working
2. **User Testing:** Gather feedback on menu UX
3. **If requested:** Add natural language as enhancement

**Not blocking combat system launch** - hierarchical menu provides excellent UX on its own.

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
