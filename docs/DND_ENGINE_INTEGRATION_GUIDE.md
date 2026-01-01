# dnd_engine Integration Guide
## Minimal Changes Approach for Roshar D&D (Updated for Current Architecture)

**Repository:** https://github.com/furlat/dnd_engine
**Language:** Python
**Integration Complexity:** Medium
**Estimated Effort:** 2 weeks (4 phases)
**Risk Level:** Low
**Current System Status:** Production-Ready (8.5/10) - See [CURRENT_SYSTEM_ARCHITECTURE.md](CURRENT_SYSTEM_ARCHITECTURE.md)

---

## Table of Contents
1. [Overview](#overview)
2. [Current System Analysis](#current-system-analysis)
3. [What dnd_engine Provides](#what-dnd_engine-provides)
4. [Architecture Compatibility](#architecture-compatibility)
5. [Integration Strategy](#integration-strategy)
6. [Step-by-Step Implementation](#step-by-step-implementation)
7. [Code Changes Required](#code-changes-required)
8. [Testing Strategy](#testing-strategy)
9. [Roshar-Specific Extensions](#roshar-specific-extensions)
10. [Success Metrics](#success-metrics)

---

## Overview

### Why dnd_engine?

Based on comprehensive testing (see [Integration Test Report](reports/TEST_REPORT_INTEGRATION.md)), your system has **critical gaps** that dnd_engine solves:

**Current Gaps (from architecture doc):**
- ❌ **Combat Resolution:** No attack rolls, damage calculation, or HP tracking
- ⚠️ **Skill Check Integration:** 7-step pipeline exists but not triggered during scenario choices
- ❌ **Spell Casting:** No spell slot consumption or surge mechanics
- ❌ **Condition Effects:** No mechanical implementation of prone, stunned, etc.

**What dnd_engine solves:**
- ✅ Complete combat resolution (attack rolls, damage, conditions)
- ✅ Sophisticated skill check system with advantage/disadvantage
- ✅ Action economy management (actions, bonus actions, reactions)
- ✅ Event-driven architecture for Roshar-specific rules
- ✅ ModifiableValue system for complex modifier tracking

**What you preserve (your strengths from 8.5/10 rating):**
- ✅ **AI-powered scenario generation** (Gemini + 6-category context)
- ✅ **Intelligent routing** (LLM-based intent classification)
- ✅ **RAG system** (Qdrant semantic search)
- ✅ **Clean architecture** (no state duplication, direct engine access)
- ✅ **Session persistence** (save/load working)
- ✅ **Policy profiles** (RAW/HOUSE/EASY)
- ✅ **Roshar integration** (Radiant orders, ideals, investiture)

---

## Current System Analysis

### Your Production-Ready Foundation (8.5/10)

From [CURRENT_SYSTEM_ARCHITECTURE.md](CURRENT_SYSTEM_ARCHITECTURE.md):

**Fully Working (11/13 features):**
- ✅ Core game loop with turn processing
- ✅ Intelligent routing (36 LLM calls in test)
- ✅ Scenario generation (4 distinct scenarios tested)
- ✅ Character management (Aggi, Level 1 Lightweaver)
- ✅ Session persistence (save/load working)
- ✅ Policy profiles (HOUSE profile active)
- ✅ Campaign system (Shards of Honor loaded)
- ✅ Logging system (1053 lines, 0 errors)
- ✅ DTO system (RequestDTO/GameResponseDTO)
- ✅ World State Adapter
- ✅ Game initialization with fallbacks

**Requires Enhancement (2/13 features):**
- ⚠️ **RAG System:** Functional but needs Qdrant setup
- ⚠️ **Skill Pipeline:** Implemented but not auto-triggered
- ⚠️ **Quest Progression:** Initialized but not activated

**Missing (identified gaps):**
- ❌ **Combat System:** Initiative exists, but no attack/damage resolution
- ❌ **Spell Casting:** No slot tracking or surge mechanics
- ❌ **Inventory System:** Moved to legacy

### Your State Hierarchy (Clean Architecture)

```
CampaignConfig (Frozen, Immutable)
    ↓ (provides campaign data)
GameEngine (Runtime State Authority)
    ├─ game_state.narrative_context
    ├─ game_state.location_context
    ├─ game_state.quest_context
    ├─ game_state.combat_state      ← Basic, needs enhancement
    ├─ game_state.environment
    └─ game_state.campaign_flags
    ↓ (uses for skill checks)
CharacterManager (Character Authority)
    ├─ characters (D&D 5e + Roshar extensions)
    ├─ ability_scores, skills
    ├─ radiant_order, ideal_level
    └─ investiture_points, surges_known
    ↓ (independent tracking)
SessionManager (Persistence Only)
    ├─ save/load coordination
    └─ analytics tracking
```

**Key Strength:** No state duplication, clear ownership, direct engine access.

---

## What dnd_engine Provides

### Core Components

#### 1. Entity-Component-System (ECS)
```python
from dnd_engine import Entity, Component

# Entities represent game objects
character = Entity(uuid="aggi_001")

# Components are specialized behaviors
character.add_component(AbilityScores(
    strength=10, dexterity=16, constitution=12,
    intelligence=14, wisdom=13, charisma=17
))
character.add_component(Skills(
    persuasion=5, insight=3, deception=7
))
character.add_component(Health(max_hp=25, current_hp=25))
```

#### 2. Event-Driven System
```python
from dnd_engine import EventQueue, AttackEvent

# All state changes flow through events
event_queue = EventQueue()

# Events can be intercepted for custom rules
attack_event = AttackEvent(attacker=character, target=enemy)
event_queue.process(attack_event)
# Fires: Declaration → Execution → Effect → Completion phases
```

#### 3. ModifiableValue System
```python
from dnd_engine import ModifiableValue, Modifier

# Track complex modifier chains
ac = ModifiableValue(base=10)
ac.add_modifier(Modifier(value=3, source="dex", type="ability"))
ac.add_modifier(Modifier(value=2, source="armor", type="armor"))
ac.add_modifier(Modifier(value=2, source="stormlight", type="enhancement"))  # Roshar!

print(ac.total())  # 17
```

#### 4. Action System
```python
from dnd_engine import Action, ActionResult

class SkillCheckAction(Action):
    def execute(self, actor, context):
        # Roll d20 + skill modifier
        roll = self.roll_d20()
        modifier = actor.get_skill_modifier(self.skill)

        # Apply advantage/disadvantage
        if context.has_advantage:
            roll = max(roll, self.roll_d20())

        total = roll + modifier
        success = total >= self.dc

        return ActionResult(success=success, roll=total)
```

#### 5. Condition System
```python
from dnd_engine import Condition

# Conditions apply effects and modifiers
prone = ProneCondition(target=character)
prone.apply()
# Automatically adds:
# - Disadvantage on attack rolls
# - Advantage for melee attackers within 5ft
# - Disadvantage for ranged attackers
```

---

## Architecture Compatibility

### Current Architecture (from your docs)

```
Player Input (CLI)
    ↓
HaystackDnDGame (Main Controller)
    ↓
RequestDTO (with _game_engine_ref, _policy_engine_ref)
    ↓
PipelineOrchestrator (Routing Hub)
    ↓
Main Interface Agent (gemini-2.0-flash)
    ├─ record_intent_analysis (Step 1)
    └─ classify_player_intent (Step 2)
    ↓
Route Decision:
    ├─ scenario_pipeline → Scenario Generator Agent
    ├─ rag_pipeline → RAG Retriever Agent
    ├─ npc_pipeline → NPC Controller Agent
    └─ scenario_with_rag_pipeline → RAG + Scenario
    ↓
GameResponseDTO
    ↓
_update_state_via_authorities()
    ├─ GameEngine.process_scenario_state_updates()
    └─ SessionManager.record_turn_analytics()
```

### After dnd_engine Integration

```
Player Input (CLI)
    ↓
HaystackDnDGame (Main Controller)
    ↓
RequestDTO (with _game_engine_ref, _policy_engine_ref, _dnd_engine_wrapper_ref)  ← NEW
    ↓
PipelineOrchestrator (Routing Hub)
    ↓
Main Interface Agent (gemini-2.0-flash)
    ↓
Route Decision:
    ├─ scenario_pipeline → Scenario Generator Agent
    ├─ combat_pipeline → Combat Agent (NEW)  ← Executes via dnd_engine
    ├─ rag_pipeline → RAG Retriever Agent
    ├─ npc_pipeline → NPC Controller Agent
    └─ scenario_with_rag_pipeline → RAG + Scenario
    ↓
GameResponseDTO
    ↓
_update_state_via_authorities()
    ├─ GameEngine.process_scenario_state_updates()
    ├─ DnDEngineWrapper.sync_entities_to_game_state()  ← NEW
    └─ SessionManager.record_turn_analytics()
```

**Key Changes:**
1. Add `_dnd_engine_wrapper_ref` to RequestDTO
2. Add `combat_pipeline` to PipelineOrchestrator
3. Add sync step after state updates
4. **Preserve everything else** (your AI strengths remain untouched)

---

## Integration Strategy

### 4-Phase Approach (Minimal Risk)

#### Phase 1: Foundation (Week 1, Days 1-3)
**Goal:** Install dnd_engine, create wrapper, no code changes yet

- Install dnd_engine repository
- Create `DnDEngineWrapper` class
- Map CharacterManager data to dnd_engine Entities
- Unit test wrapper in isolation

**Risk:** None (no existing code modified)

#### Phase 2: Skill Check Integration (Week 1, Days 4-5)
**Goal:** Connect your existing 7-step pipeline to dnd_engine

- Enhance `GameEngine.process_skill_check()` to use wrapper
- Auto-trigger skill checks from scenario choices
- Test with existing campaigns

**Risk:** Low (fallback to old system if wrapper unavailable)

#### Phase 3: Combat System (Week 2, Days 1-3)
**Goal:** Add combat resolution pipeline

- Create `CombatAgent` (Haystack component)
- Add combat intent classification to Interface Agent
- Add combat_pipeline to PipelineOrchestrator
- Test attack/damage mechanics

**Risk:** Low (new pipeline, doesn't affect existing flows)

#### Phase 4: Roshar Extensions (Week 2, Days 4-5)
**Goal:** Custom Conditions and Actions for Roshar

- Create `StormlightInfusedCondition`
- Create `LashingAction` (Windrunner surge)
- Create `SoulcastingAction` (Lightweaver surge)
- Test Radiant abilities

**Risk:** Low (additive features)

---

## Step-by-Step Implementation

### Phase 1: Foundation (Days 1-3)

#### Step 1.1: Install dnd_engine

```bash
cd /Users/patnaiku/projects/roshar-dnd\ copy

# Clone dnd_engine
mkdir -p external
git clone https://github.com/furlat/dnd_engine.git external/dnd_engine

# Add to .gitignore
echo "external/dnd_engine/" >> .gitignore

# Verify installation
python -c "import sys; sys.path.append('./external/dnd_engine'); from dnd_engine import Entity; print('Success!')"
```

#### Step 1.2: Create DnDEngineWrapper

**New file:** `components/dnd_engine_wrapper.py`

```python
"""
dnd_engine Integration Wrapper for Roshar D&D

Bridges the gap between:
- Your GameEngine (state authority) and CharacterManager (character data)
- dnd_engine's Entity-Component-System (mechanics engine)

This wrapper:
1. Converts CharacterManager characters to dnd_engine Entities
2. Executes skill checks and combat via dnd_engine
3. Syncs results back to GameEngine state
4. Preserves your existing state hierarchy (no duplication)
"""

import sys
sys.path.append('./external/dnd_engine')

from dataclasses import dataclass, field
from typing import Dict, Optional, Any
import logging

from dnd_engine import Entity, EventQueue
from dnd_engine.components import AbilityScores, Skills, Health, ArmorClass
from dnd_engine.actions import SkillCheckAction, AttackAction

# Your existing imports
from components.game_engine import GameEngine
from components.character_manager import CharacterManager

logger = logging.getLogger(__name__)


@dataclass
class DnDEngineWrapper:
    """
    Wrapper that integrates dnd_engine with Roshar GameEngine.

    Responsibilities:
    - Translate CharacterManager data → dnd_engine Entities
    - Execute skill checks via dnd_engine Action system
    - Execute combat via dnd_engine Combat system
    - Sync results back to GameEngine state
    - Preserve existing state hierarchy (GameEngine remains authority)
    """

    game_engine: GameEngine
    character_manager: CharacterManager
    event_queue: EventQueue = field(default_factory=EventQueue)
    entities: Dict[str, Entity] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize entities from existing characters."""
        logger.info("Initializing DnDEngineWrapper")
        self._sync_characters_to_entities()
        logger.info(f"Synced {len(self.entities)} characters to dnd_engine entities")

    def _sync_characters_to_entities(self):
        """
        Convert CharacterManager characters to dnd_engine Entities.

        Maps:
        - CharacterData.ability_scores → AbilityScores component
        - CharacterData.skills → Skills component
        - CharacterData.hit_points → Health component
        - CharacterData.armor_class → ArmorClass component
        """
        for char_id, character in self.character_manager.characters.items():
            entity = Entity(uuid=char_id, name=character.name)

            # Add ability scores component
            entity.add_component(AbilityScores(
                strength=character.ability_scores["strength"],
                dexterity=character.ability_scores["dexterity"],
                constitution=character.ability_scores["constitution"],
                intelligence=character.ability_scores["intelligence"],
                wisdom=character.ability_scores["wisdom"],
                charisma=character.ability_scores["charisma"]
            ))

            # Add skills component
            # Note: CharacterManager has skill proficiencies, need to compute modifiers
            skills_dict = self._compute_skill_modifiers(character)
            entity.add_component(Skills(**skills_dict))

            # Add health component
            entity.add_component(Health(
                max_hp=character.max_hit_points,
                current_hp=character.hit_points  # Assumes current HP tracked
            ))

            # Add armor class component
            entity.add_component(ArmorClass(
                base=10,
                armor_bonus=character.armor_class - 10  # Simplified for now
            ))

            self.entities[char_id] = entity
            logger.debug(f"Created entity for {character.name} (ID: {char_id})")

    def _compute_skill_modifiers(self, character) -> Dict[str, int]:
        """
        Compute skill modifiers from character data.

        Uses CharacterManager.get_skill_data() for proficiency bonuses.
        """
        skills = {}
        skill_names = [
            "acrobatics", "animal_handling", "arcana", "athletics",
            "deception", "history", "insight", "intimidation",
            "investigation", "medicine", "nature", "perception",
            "performance", "persuasion", "religion", "sleight_of_hand",
            "stealth", "survival"
        ]

        for skill_name in skill_names:
            skill_data = self.character_manager.get_skill_data(character.name, skill_name)
            skills[skill_name] = skill_data.get("modifier", 0)

        return skills

    def _sync_entity_to_game_state(self, char_id: str):
        """
        Sync dnd_engine Entity state back to GameEngine.

        Updates:
        - Character HP (if changed in combat)
        - Conditions (if applied via dnd_engine)
        """
        entity = self.entities[char_id]

        # Update HP in GameEngine combat_state
        health_component = entity.get_component(Health)
        if health_component:
            current_hp = health_component.current_hp

            # Update GameEngine's character runtime state
            if char_id in self.game_engine.game_state.characters:
                self.game_engine.game_state.characters[char_id]["current_hp"] = current_hp
                logger.debug(f"Synced HP for {char_id}: {current_hp}")

    def execute_skill_check(
        self,
        character_id: str,
        skill: str,
        dc: int,
        advantage: bool = False,
        disadvantage: bool = False
    ) -> Dict[str, Any]:
        """
        Execute skill check using dnd_engine mechanics.

        Integrates with your existing 7-step pipeline:
        - Step 1-3: GameEngine determines DC, advantage (already done)
        - Step 4: THIS METHOD executes roll via dnd_engine
        - Step 5-7: GameEngine evaluates result, logs outcome

        Args:
            character_id: Character UUID
            skill: Skill name (e.g., "athletics", "persuasion")
            dc: Difficulty class
            advantage: Roll with advantage
            disadvantage: Roll with disadvantage

        Returns:
            {
                "success": bool,
                "roll": int (total roll),
                "natural_roll": int (d20 result),
                "modifier": int,
                "dc": int,
                "advantage": bool,
                "disadvantage": bool
            }
        """
        entity = self.entities.get(character_id)
        if not entity:
            logger.error(f"Character {character_id} not found in entities")
            return {"success": False, "error": "Character not found"}

        # Create skill check action
        action = SkillCheckAction(
            skill=skill,
            difficulty_class=dc,
            advantage=advantage,
            disadvantage=disadvantage
        )

        # Execute via event queue
        result = action.execute(entity, self.event_queue)

        # Sync back to GameEngine (in case of state changes)
        self._sync_entity_to_game_state(character_id)

        logger.info(f"Skill check: {character_id} rolled {skill} vs DC {dc}: {result.roll_total} ({'Success' if result.success else 'Failure'})")

        return {
            "success": result.success,
            "roll": result.roll_total,
            "natural_roll": result.natural_roll,
            "modifier": result.modifier,
            "dc": dc,
            "advantage": advantage,
            "disadvantage": disadvantage,
            "breakdown": result.breakdown  # Detailed provenance
        }

    def execute_attack(
        self,
        attacker_id: str,
        target_id: str,
        weapon: str = "unarmed",
        advantage: bool = False,
        disadvantage: bool = False
    ) -> Dict[str, Any]:
        """
        Execute attack using dnd_engine combat mechanics.

        Handles:
        - Attack roll (d20 + attack bonus)
        - AC comparison
        - Damage roll (weapon dice + modifiers)
        - HP reduction
        - Critical hits

        Args:
            attacker_id: Attacker character UUID
            target_id: Target character UUID
            weapon: Weapon name (default: "unarmed")
            advantage: Attack with advantage
            disadvantage: Attack with disadvantage

        Returns:
            {
                "hit": bool,
                "attack_roll": int,
                "natural_roll": int,
                "target_ac": int,
                "damage": int,
                "damage_type": str,
                "critical": bool,
                "target_hp_remaining": int
            }
        """
        attacker = self.entities.get(attacker_id)
        target = self.entities.get(target_id)

        if not attacker or not target:
            logger.error(f"Attack failed: attacker={attacker_id} or target={target_id} not found")
            return {"hit": False, "error": "Attacker or target not found"}

        # Create attack action
        action = AttackAction(
            weapon=weapon,
            advantage=advantage,
            disadvantage=disadvantage
        )

        # Execute via event queue
        result = action.execute(attacker, target, self.event_queue)

        # Sync both entities back to GameEngine
        self._sync_entity_to_game_state(attacker_id)
        self._sync_entity_to_game_state(target_id)

        logger.info(f"Attack: {attacker_id} attacked {target_id} with {weapon}: {'HIT' if result.hit else 'MISS'} (Roll: {result.attack_roll} vs AC {result.target_ac})")

        return {
            "hit": result.hit,
            "attack_roll": result.attack_roll,
            "natural_roll": result.natural_roll,
            "target_ac": result.target_ac,
            "damage": result.damage if result.hit else 0,
            "damage_type": result.damage_type,
            "critical": result.critical,
            "target_hp_remaining": target.get_component(Health).current_hp
        }

    def apply_condition(self, character_id: str, condition_name: str, duration: int = -1):
        """
        Apply a condition to a character.

        Args:
            character_id: Character UUID
            condition_name: Condition name (e.g., "prone", "stunned", "stormlight_infused")
            duration: Duration in rounds (-1 = permanent until removed)
        """
        entity = self.entities.get(character_id)
        if not entity:
            logger.error(f"Cannot apply condition: character {character_id} not found")
            return

        # Create condition instance
        # Note: dnd_engine condition classes need to be imported
        condition = self._create_condition(condition_name, entity, duration)

        if condition:
            condition.apply()
            logger.info(f"Applied condition '{condition_name}' to {character_id}")
        else:
            logger.warning(f"Unknown condition: {condition_name}")

    def _create_condition(self, condition_name: str, target: Entity, duration: int):
        """Factory method for creating condition instances."""
        # Import standard D&D conditions
        from dnd_engine.conditions import ProneCondition, StunnedCondition

        # Map condition names to classes
        condition_map = {
            "prone": ProneCondition,
            "stunned": StunnedCondition,
            # Add Roshar-specific conditions later
        }

        condition_class = condition_map.get(condition_name.lower())
        if condition_class:
            return condition_class(target=target, duration=duration)
        return None
```

#### Step 1.3: Unit Test Wrapper

**New file:** `tests/test_dnd_engine_wrapper.py`

```python
import pytest
from components.dnd_engine_wrapper import DnDEngineWrapper
from components.game_engine import GameEngine
from components.character_manager import CharacterManager
from components.campaign_config import CampaignConfig

@pytest.fixture
def test_config():
    """Create minimal campaign config for testing."""
    return CampaignConfig(
        name="Test Campaign",
        theme="Testing",
        story="Test story",
        difficulty="Medium",
        starting_location="Test Location",
        key_npcs=[],
        locations=[],
        main_quest="Test quest",
        side_quests=[],
        campaign_hooks=[]
    )

@pytest.fixture
def game_engine(test_config):
    """Create GameEngine with test config."""
    engine = GameEngine(test_config)
    return engine

@pytest.fixture
def character_manager():
    """Create CharacterManager with test character."""
    manager = CharacterManager()
    # Add test character (Aggi from your tests)
    manager.add_character({
        "name": "Aggi",
        "level": 1,
        "char_class": "Lightweaver",
        "radiant_order": "Lightweaver",
        "ability_scores": {
            "strength": 10,
            "dexterity": 16,
            "constitution": 12,
            "intelligence": 14,
            "wisdom": 13,
            "charisma": 17
        },
        "armor_class": 13,
        "max_hit_points": 25,
        "hit_points": 25,
        "skills": {
            "persuasion": 5,
            "deception": 7,
            "insight": 3
        }
    })
    return manager

@pytest.fixture
def wrapper(game_engine, character_manager):
    """Create DnDEngineWrapper."""
    return DnDEngineWrapper(
        game_engine=game_engine,
        character_manager=character_manager
    )

def test_wrapper_initialization(wrapper):
    """Test that wrapper initializes and syncs characters."""
    assert len(wrapper.entities) == 1
    assert "aggi" in wrapper.entities  # Character ID

def test_skill_check_execution(wrapper):
    """Test skill check via dnd_engine."""
    result = wrapper.execute_skill_check(
        character_id="aggi",
        skill="persuasion",
        dc=15
    )

    assert "success" in result
    assert "roll" in result
    assert result["dc"] == 15
    assert isinstance(result["success"], bool)

def test_attack_execution(wrapper, character_manager):
    """Test attack via dnd_engine."""
    # Add target enemy
    character_manager.add_character({
        "name": "Test Enemy",
        "level": 1,
        "char_class": "Barbarian",
        "armor_class": 14,
        "max_hit_points": 20,
        "hit_points": 20,
        "ability_scores": {
            "strength": 16, "dexterity": 10,
            "constitution": 14, "intelligence": 8,
            "wisdom": 10, "charisma": 8
        }
    })

    # Re-sync to add new entity
    wrapper._sync_characters_to_entities()

    result = wrapper.execute_attack(
        attacker_id="aggi",
        target_id="test_enemy",
        weapon="spear"
    )

    assert "hit" in result
    assert "damage" in result
    assert isinstance(result["hit"], bool)
```

**Run tests:**
```bash
pytest tests/test_dnd_engine_wrapper.py -v
```

---

### Phase 2: Skill Check Integration (Days 4-5)

#### Step 2.1: Enhance GameEngine

**Modify:** `components/game_engine.py`

```python
# ADD to imports
from typing import Optional

class GameEngine:
    def __init__(
        self,
        campaign_config: CampaignConfig,
        character_manager: CharacterManager,
        dnd_engine_wrapper: Optional[Any] = None  # NEW
    ):
        self.campaign_config = campaign_config
        self.character_manager = character_manager
        self.dnd_engine_wrapper = dnd_engine_wrapper  # NEW
        # ... rest of initialization unchanged

    def process_skill_check(
        self,
        character_id: str,
        skill_name: str,
        dc: int,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute 7-step skill check pipeline.

        NOW ENHANCED: Uses dnd_engine_wrapper for step 4 (dice rolling)
        if available, otherwise falls back to old system.
        """
        logger.info(f"=== Starting 7-Step Skill Check Pipeline ===")
        logger.info(f"Character: {character_id}, Skill: {skill_name}, DC: {dc}")

        # Step 1: Rules Enforcer - Determine if roll needed
        if not self.rules_enforcer.is_check_needed(context):
            logger.info("Step 1: Check not needed (auto-success)")
            return {"success": True, "auto_success": True}

        # Step 2: Character Manager - Get skill data
        skill_data = self.character_manager.get_skill_data(character_id, skill_name)
        logger.info(f"Step 2: Skill modifier = {skill_data['modifier']}")

        # Step 3: Policy Engine - Compute advantage/disadvantage
        advantage_state = self.policy_engine.compute_advantage(context)
        logger.info(f"Step 3: Advantage state = {advantage_state}")

        # Step 4: Dice Roller - Execute roll
        if self.dnd_engine_wrapper:
            # NEW: Use dnd_engine for mechanically accurate rolls
            logger.info("Step 4: Using dnd_engine for roll execution")
            roll_result = self.dnd_engine_wrapper.execute_skill_check(
                character_id=character_id,
                skill=skill_name,
                dc=dc,
                advantage=advantage_state.get("advantage", False),
                disadvantage=advantage_state.get("disadvantage", False)
            )
        else:
            # Fallback: Use old dice roller
            logger.info("Step 4: Using fallback dice roller")
            roll_result = self.dice_roller.roll_skill_check(
                modifier=skill_data["modifier"],
                advantage=advantage_state.get("advantage", False),
                disadvantage=advantage_state.get("disadvantage", False)
            )

        logger.info(f"Step 4: Roll result = {roll_result['roll']}")

        # Step 5: Rules Enforcer - Evaluate success/failure
        success = roll_result["roll"] >= dc
        logger.info(f"Step 5: {'Success' if success else 'Failure'} ({roll_result['roll']} vs DC {dc})")

        # Step 6: Game Engine - Apply state changes
        if success:
            self._apply_skill_check_success(character_id, skill_name, context)

        # Step 7: Decision Logger - Record provenance
        self._log_skill_check_decision(
            character_id=character_id,
            skill_name=skill_name,
            dc=dc,
            roll_result=roll_result,
            success=success
        )

        logger.info("=== Skill Check Pipeline Complete ===")

        return {
            "success": success,
            "roll": roll_result["roll"],
            "dc": dc,
            "advantage": advantage_state.get("advantage", False),
            "disadvantage": advantage_state.get("disadvantage", False),
            "breakdown": roll_result.get("breakdown", {})
        }
```

#### Step 2.2: Update Game Initialization

**Modify:** `core/game_initialization.py`

```python
# ADD to imports
from components.dnd_engine_wrapper import DnDEngineWrapper

def initialize_game_systems(campaign_config, character_manager):
    """
    Initialize all game systems.

    NEW: Creates dnd_engine_wrapper and passes to GameEngine.
    """
    logger.info("Initializing game systems")

    # Create GameEngine (without wrapper first)
    game_engine = GameEngine(
        campaign_config=campaign_config,
        character_manager=character_manager
    )

    # NEW: Create dnd_engine_wrapper
    try:
        dnd_wrapper = DnDEngineWrapper(
            game_engine=game_engine,
            character_manager=character_manager
        )
        logger.info("✅ dnd_engine wrapper initialized")

        # Attach wrapper to GameEngine
        game_engine.dnd_engine_wrapper = dnd_wrapper
    except Exception as e:
        logger.warning(f"⚠️ dnd_engine wrapper initialization failed: {e}")
        logger.warning("Continuing without dnd_engine (will use fallback mechanics)")
        dnd_wrapper = None

    # Create SessionManager
    session_manager = SessionManager(game_engine=game_engine)

    # Create PolicyEngine
    policy_engine = PolicyEngine(profile="HOUSE")

    return {
        "game_engine": game_engine,
        "character_manager": character_manager,
        "session_manager": session_manager,
        "policy_engine": policy_engine,
        "dnd_wrapper": dnd_wrapper  # NEW
    }
```

#### Step 2.3: Update RequestDTO

**Modify:** `components/shared_contract.py`

```python
@dataclass
class RequestDTO:
    """
    Request Data Transfer Object.

    Carries player input and references to game systems through pipelines.

    NEW: Added _dnd_engine_wrapper_ref for combat/skill mechanics.
    """
    player_input: str
    request_type: str
    player_character_name: str = ""

    # Engine references (passed by reference, never copied)
    _game_engine_ref: Any = None
    _policy_engine_ref: Any = None
    _character_manager_ref: Any = None
    _dnd_engine_wrapper_ref: Any = None  # NEW

    # Optional context
    rag_context: Optional[Dict[str, Any]] = None
    scenario_context: Optional[Dict[str, Any]] = None
```

#### Step 2.4: Update Main Game Loop

**Modify:** `haystack_dnd_game.py`

```python
class HaystackDnDGame:
    def __init__(self, ...):
        # ... existing initialization ...

        # NEW: Store dnd_wrapper reference
        self.dnd_wrapper = game_systems.get("dnd_wrapper")
        logger.info(f"DnD Engine Wrapper: {'✅ Active' if self.dnd_wrapper else '❌ Inactive'}")

    def _create_request_dto(self, player_input: str) -> Dict:
        """Create RequestDTO with all engine references."""
        dto = {
            "player_input": player_input,
            "request_type": "game_action",
            "player_character_name": self.player_character_name,
            "_game_engine_ref": self.game_engine,
            "_policy_engine_ref": self.policy_engine,
            "_character_manager_ref": self.character_manager,
            "_dnd_engine_wrapper_ref": self.dnd_wrapper,  # NEW
        }
        return dto
```

---

### Phase 3: Combat System (Week 2, Days 1-3)

#### Step 3.1: Create Combat Agent

**New file:** `agents/combat_agent.py`

```python
"""
Combat Agent for Roshar D&D

Handles combat resolution using dnd_engine mechanics.
Integrates with your existing Haystack pipeline architecture.
"""

from haystack import component
from haystack.dataclasses import ChatMessage
from typing import Dict, Any
import logging

from config.llm_config import get_gemini_chat_generator

logger = logging.getLogger(__name__)


@component
class CombatAgent:
    """
    Agent that handles combat resolution using dnd_engine.

    Workflow:
    1. Receive combat intent from Interface Agent routing
    2. Parse combat action (attack, cast spell, use ability)
    3. Execute action via dnd_engine_wrapper
    4. Generate narrative description via LLM
    5. Return GameResponseDTO with combat results

    Tools:
    - None (uses dnd_engine_wrapper directly from DTO)

    LLM:
    - gemini-2.0-flash for narrative generation only
    """

    def __init__(self):
        self.llm = get_gemini_chat_generator(
            model_name="gemini-2.0-flash",
            temperature=0.7  # Higher for creative combat descriptions
        )
        logger.info("CombatAgent initialized with gemini-2.0-flash")

    @component.output_types(response=Dict[str, Any])
    def run(self, dto: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process combat action.

        Args:
            dto: RequestDTO with player_input and _dnd_engine_wrapper_ref

        Returns:
            GameResponseDTO with combat_result and narrative
        """
        player_input = dto.get("player_input", "")
        dnd_wrapper = dto.get("_dnd_engine_wrapper_ref")
        character_name = dto.get("player_character_name", "Unknown")

        if not dnd_wrapper:
            logger.error("No dnd_engine_wrapper available for combat")
            return {
                "response": {
                    "response_type": "error",
                    "content": "Combat system unavailable (dnd_engine not initialized)"
                }
            }

        logger.info(f"Processing combat action: {player_input}")

        # Parse combat intent (simple pattern matching for now)
        combat_result = self._execute_combat_action(player_input, dnd_wrapper, character_name)

        # Generate narrative description
        narrative = self._generate_combat_narrative(player_input, combat_result)

        return {
            "response": {
                "response_type": "combat_result",
                "narrative": narrative,
                "combat_result": combat_result,
                "player_input": player_input
            }
        }

    def _execute_combat_action(
        self,
        player_input: str,
        dnd_wrapper,
        character_name: str
    ) -> Dict[str, Any]:
        """
        Parse player input and execute combat action.

        Supported actions:
        - Attack: "I attack [target] with [weapon]"
        - Ability: "I use [ability]" (future)
        - Spell: "I cast [spell]" (future)
        """
        # Simple pattern matching
        # TODO: Enhance with LLM parsing for complex actions

        if "attack" in player_input.lower():
            # Extract target (simplified)
            # In real implementation, use LLM to extract target
            target = self._extract_target(player_input)
            weapon = self._extract_weapon(player_input)

            result = dnd_wrapper.execute_attack(
                attacker_id=character_name.lower(),
                target_id=target,
                weapon=weapon
            )

            return {
                "action_type": "attack",
                "target": target,
                "weapon": weapon,
                **result
            }

        # Default: unrecognized action
        return {
            "action_type": "unknown",
            "error": "Could not parse combat action"
        }

    def _extract_target(self, player_input: str) -> str:
        """
        Extract target from player input.

        TODO: Use LLM for sophisticated parsing.
        For now, simple keyword matching.
        """
        # Simplified: look for common enemy names
        enemies = ["parshendi", "voidbringer", "enemy", "soldier"]

        for enemy in enemies:
            if enemy in player_input.lower():
                return f"{enemy}_001"  # Default to first instance

        return "unknown_target"

    def _extract_weapon(self, player_input: str) -> str:
        """Extract weapon from player input."""
        weapons = ["spear", "sword", "shardblade", "bow", "knife"]

        for weapon in weapons:
            if weapon in player_input.lower():
                return weapon

        return "unarmed"

    def _generate_combat_narrative(
        self,
        player_input: str,
        combat_result: Dict[str, Any]
    ) -> str:
        """
        Generate vivid combat narrative using LLM.

        Takes mechanical results and transforms into engaging story.
        """
        # Build prompt for narrative generation
        system_prompt = """You are a master Dungeon Master narrating combat in Brandon Sanderson's Stormlight Archive world.

Generate vivid, exciting combat descriptions based on mechanical results. Include:
- Atmospheric details (weather, environment, emotions)
- Character actions and reactions
- Impact of attacks (hits, misses, damage)
- Roshar-specific elements (Stormlight, spren, surges if applicable)

Keep descriptions concise (2-3 sentences) but evocative."""

        user_prompt = f"""Player Action: {player_input}

Combat Result:
- Action: {combat_result.get('action_type', 'unknown')}
- Hit: {combat_result.get('hit', False)}
- Damage: {combat_result.get('damage', 0)}
- Attack Roll: {combat_result.get('attack_roll', 0)}
- Target AC: {combat_result.get('target_ac', 0)}
- Critical: {combat_result.get('critical', False)}

Generate combat narrative:"""

        messages = [
            ChatMessage.from_system(system_prompt),
            ChatMessage.from_user(user_prompt)
        ]

        response = self.llm.run(messages=messages)
        narrative = response["replies"][0].content

        logger.debug(f"Generated combat narrative: {narrative[:100]}...")

        return narrative
```

#### Step 3.2: Add Combat Pipeline to Orchestrator

**Modify:** `orchestrator/pipeline_integration.py`

```python
# ADD to imports
from agents.combat_agent import CombatAgent

class PipelineOrchestrator:
    def __init__(self, ...):
        # ... existing initialization ...

        # NEW: Create combat agent
        self.agents["combat"] = CombatAgent()
        logger.info("✅ Combat Agent created")

        # NEW: Create combat pipeline
        self.pipelines["combat_pipeline"] = self._create_combat_pipeline()
        logger.info("✅ Combat Pipeline created")

    def _create_combat_pipeline(self) -> Pipeline:
        """
        Create combat pipeline.

        Flow:
        RequestDTO → Combat Agent → GameResponseDTO
        """
        pipeline = Pipeline()
        pipeline.add_component("combat_agent", self.agents["combat"])

        logger.debug("Combat pipeline created")
        return pipeline

    def process_request(self, dto: Dict) -> Dict:
        """
        Process request by routing to appropriate pipeline.

        NEW: Added combat_pipeline routing.
        """
        route = dto.get("route", "scenario_pipeline")

        logger.info(f"Routing to: {route}")

        if route == "combat_pipeline":
            # NEW: Route to combat
            result = self.pipelines["combat_pipeline"].run({"dto": dto})
            return result["combat_agent"]["response"]

        elif route == "scenario_pipeline":
            # Existing scenario routing
            result = self.pipelines["scenario_pipeline"].run({"dto": dto})
            return result["validator"]["scenario"]

        # ... rest of routing unchanged
```

#### Step 3.3: Update Interface Agent for Combat Detection

**Modify:** `agents/main_interface_agent_fixed.py`

```python
# In system prompt, add combat intent category

SYSTEM_PROMPT = """You are the Main Interface Agent for a D&D game...

Intent Categories:
- scenario_action: Player performing action (persuade, investigate, search)
- combat_action: Player performing combat (attack, cast spell, use ability)  # NEW
- rag_query: Player asking about lore/rules
- npc_interaction: Player talking to NPC
- scenario_generation: General continuation
"""

# In classify_player_intent tool

@tool
def classify_player_intent(...):
    """Classify player intent and route to appropriate pipeline."""

    primary = intent_analysis.get("primary_intent")

    # NEW: Combat routing
    if primary == "combat_action":
        return {
            "route": "combat_pipeline",
            "confidence": confidence,
            "rationale": rationale
        }

    # ... rest of routing unchanged
```

---

### Phase 4: Roshar Extensions (Week 2, Days 4-5)

#### Step 4.1: Stormlight Infused Condition

**New file:** `roshar_extensions/stormlight_conditions.py`

```python
"""
Roshar-Specific Conditions for dnd_engine

Custom Condition implementations for Stormlight Archive mechanics.
"""

import sys
sys.path.append('./external/dnd_engine')

from dnd_engine import Condition, Modifier, Event


class StormlightInfusedCondition(Condition):
    """
    Character is infused with Stormlight.

    Effects:
    - +2 bonus to all ability checks (Stormlight enhancement)
    - Advantage on death saving throws (healing aura)
    - Regenerates 5 HP at start of each turn
    - Glowing appearance (cosmetic)

    Duration: Until Stormlight is exhausted (tracked separately)
    """

    def __init__(self, target, stormlight_charges: int = 10):
        super().__init__(target=target, duration=-1)  # Permanent until removed
        self.stormlight_charges = stormlight_charges

    def apply(self):
        """Apply Stormlight effects to character."""
        # Add +2 bonus to all skills (Stormlight enhancement)
        skills_component = self.target.get_component(Skills)
        if skills_component:
            for skill_name in skills_component.all_skills():
                skill = getattr(skills_component, skill_name)
                skill.add_modifier(Modifier(
                    value=2,
                    source="stormlight_infusion",
                    type="enhancement",
                    description="Stormlight flows through your body, enhancing your abilities"
                ))

        # Register regeneration handler
        self.event_queue.register_handler(
            event_type="turn_start",
            handler=self._regenerate_hp,
            source="stormlight_regen"
        )

        logger.info(f"{self.target.name} is infused with Stormlight ({self.stormlight_charges} charges)")

    def remove(self):
        """Remove Stormlight effects when exhausted."""
        # Remove modifiers
        skills_component = self.target.get_component(Skills)
        if skills_component:
            for skill_name in skills_component.all_skills():
                skill = getattr(skills_component, skill_name)
                skill.remove_modifier(source="stormlight_infusion")

        # Unregister regeneration handler
        self.event_queue.unregister_handler(source="stormlight_regen")

        logger.info(f"{self.target.name}'s Stormlight is exhausted")

    def _regenerate_hp(self, event):
        """Regenerate HP at start of turn."""
        if self.stormlight_charges <= 0:
            self.remove()
            return

        health = self.target.get_component(Health)
        if health and health.current_hp < health.max_hp:
            heal_amount = min(5, health.max_hp - health.current_hp)
            health.heal(heal_amount)
            self.stormlight_charges -= 1

            logger.info(f"{self.target.name} regenerates {heal_amount} HP (Stormlight charges: {self.stormlight_charges})")


class SprenBondedCondition(Condition):
    """
    Character is bonded to a spren (Radiant bond).

    Effects vary by spren type:
    - Honorspren (Windrunner): +1 to Athletics, +1 AC
    - Cryptics (Lightweaver): +1 to Deception/Performance, advantage on Illusion
    - Cultivationspren (Edgedancer): +1 to Acrobatics, +1 to Healing

    Duration: Permanent (unless oath broken)
    """

    def __init__(self, target, spren_type: str):
        super().__init__(target=target, duration=-1)
        self.spren_type = spren_type
        self.oath_level = 1  # First Ideal by default

    def apply(self):
        """Apply spren bond effects based on type."""
        if self.spren_type == "honorspren":
            self._apply_honorspren_bond()
        elif self.spren_type == "cryptic":
            self._apply_cryptic_bond()
        elif self.spren_type == "cultivationspren":
            self._apply_cultivationspren_bond()

    def _apply_honorspren_bond(self):
        """Windrunner bond effects."""
        # +1 to Athletics
        skills = self.target.get_component(Skills)
        skills.athletics.add_modifier(Modifier(
            value=1,
            source="honorspren_bond",
            type="bond"
        ))

        # +1 AC (bond armor)
        ac = self.target.get_component(ArmorClass)
        ac.add_modifier(Modifier(
            value=1,
            source="honorspren_bond",
            type="bond"
        ))

    def _apply_cryptic_bond(self):
        """Lightweaver bond effects."""
        skills = self.target.get_component(Skills)
        skills.deception.add_modifier(Modifier(value=1, source="cryptic_bond", type="bond"))
        skills.performance.add_modifier(Modifier(value=1, source="cryptic_bond", type="bond"))

    def _apply_cultivationspren_bond(self):
        """Edgedancer bond effects."""
        skills = self.target.get_component(Skills)
        skills.acrobatics.add_modifier(Modifier(value=1, source="cultivationspren_bond", type="bond"))
        skills.medicine.add_modifier(Modifier(value=1, source="cultivationspren_bond", type="bond"))

    def advance_oath(self, new_level: int):
        """Advance to next Ideal level (1-5)."""
        self.oath_level = new_level
        logger.info(f"{self.target.name} advances to Ideal {new_level}!")
        # Future: Add new abilities based on oath level
```

#### Step 4.2: Radiant Surge Actions

**New file:** `roshar_extensions/radiant_actions.py`

```python
"""
Radiant Surge Actions for dnd_engine

Custom Action implementations for Stormlight Archive surge abilities.
"""

import sys
sys.path.append('./external/dnd_engine')

from dnd_engine import Action, ActionResult, Prerequisite


class HasStormlightPrerequisite(Prerequisite):
    """Check if character has Stormlight charges."""

    def __init__(self, minimum_charges: int = 1):
        self.minimum_charges = minimum_charges

    def check(self, actor) -> bool:
        # Check for StormlightInfusedCondition
        stormlight_condition = actor.get_condition("stormlight_infused")
        if stormlight_condition:
            return stormlight_condition.stormlight_charges >= self.minimum_charges
        return False


class LashingAction(Action):
    """
    Windrunner Surge: Gravitation (Lashing)

    Lash a target in a direction, causing them to "fall" that way.

    Prerequisites:
    - Character is Windrunner (Gravitation surge)
    - Has 10 Stormlight charges
    - Target within 30 feet

    Effects:
    - Target is Lashed in chosen direction
    - Target moves up to 30 feet in that direction
    - Stormlight cost: 10 charges

    Saving Throw: Strength DC 15 to resist
    """

    prerequisites = [
        HasStormlightPrerequisite(minimum=10),
        # TargetInRange(30)  # Would need to implement
    ]

    def __init__(self, direction: str = "upward"):
        self.direction = direction  # upward, downward, north, south, etc.
        self.stormlight_cost = 10
        self.save_dc = 15

    def execute(self, actor, target, context) -> ActionResult:
        """Execute Lashing."""
        # Consume Stormlight
        stormlight_condition = actor.get_condition("stormlight_infused")
        if stormlight_condition:
            stormlight_condition.stormlight_charges -= self.stormlight_cost

        # Target makes Strength save
        save_roll = target.roll_saving_throw("strength")

        if save_roll < self.save_dc:
            # Lashing succeeds
            # Apply Lashed condition (would need to implement)
            description = f"{target.name} is Lashed {self.direction}! They begin to fall in that direction."
            success = True
        else:
            # Lashing resisted
            description = f"{target.name} resists the Lashing!"
            success = False

        return ActionResult(
            success=success,
            description=description,
            stormlight_used=self.stormlight_cost
        )


class SoulcastAction(Action):
    """
    Lightweaver/Elsecaller Surge: Transformation (Soulcasting)

    Transform one substance into another.

    Prerequisites:
    - Character knows Transformation surge
    - Has 20 Stormlight charges (costly surge)
    - Target object within 10 feet

    Effects:
    - Transform object from one substance to another
    - Stormlight cost: 20 charges

    Difficulty: Intelligence check DC varies by transformation complexity
    """

    prerequisites = [
        HasStormlightPrerequisite(minimum=20),
    ]

    def __init__(self, from_substance: str, to_substance: str):
        self.from_substance = from_substance
        self.to_substance = to_substance
        self.stormlight_cost = 20

        # DC based on complexity
        self.dc = self._calculate_dc()

    def _calculate_dc(self) -> int:
        """Calculate DC based on transformation complexity."""
        # Simple transformations (stone to stone): DC 12
        # Medium (stone to metal): DC 15
        # Complex (stone to food): DC 18
        # Impossible (stone to living): DC 25

        simple_pairs = [("stone", "rock"), ("wood", "plant")]
        complex_pairs = [("stone", "food"), ("stone", "water")]

        if (self.from_substance, self.to_substance) in simple_pairs:
            return 12
        elif (self.from_substance, self.to_substance) in complex_pairs:
            return 18
        else:
            return 15  # Default medium

    def execute(self, actor, target_object, context) -> ActionResult:
        """Execute Soulcasting."""
        # Consume Stormlight
        stormlight_condition = actor.get_condition("stormlight_infused")
        if stormlight_condition:
            stormlight_condition.stormlight_charges -= self.stormlight_cost

        # Intelligence check
        check_roll = actor.roll_ability_check("intelligence")

        if check_roll >= self.dc:
            # Soulcasting succeeds
            description = f"The {self.from_substance} shimmers and transforms into {self.to_substance}!"
            success = True
        else:
            # Soulcasting fails (Stormlight wasted)
            description = f"The Soulcasting fails. The {self.from_substance} resists transformation."
            success = False

        return ActionResult(
            success=success,
            description=description,
            stormlight_used=self.stormlight_cost
        )
```

#### Step 4.3: Integrate Roshar Extensions with Wrapper

**Modify:** `components/dnd_engine_wrapper.py`

```python
# ADD to imports
from roshar_extensions.stormlight_conditions import StormlightInfusedCondition, SprenBondedCondition
from roshar_extensions.radiant_actions import LashingAction, SoulcastAction

class DnDEngineWrapper:
    # ... existing code ...

    def infuse_with_stormlight(self, character_id: str, charges: int = 10):
        """
        Infuse character with Stormlight.

        Applies StormlightInfusedCondition.
        """
        entity = self.entities.get(character_id)
        if not entity:
            logger.error(f"Cannot infuse: character {character_id} not found")
            return

        condition = StormlightInfusedCondition(target=entity, stormlight_charges=charges)
        entity.add_condition(condition)
        condition.apply()

        logger.info(f"✨ {entity.name} is infused with {charges} Stormlight charges")

    def execute_lashing(
        self,
        character_id: str,
        target_id: str,
        direction: str = "upward"
    ) -> Dict[str, Any]:
        """
        Execute Windrunner Lashing surge.

        Args:
            character_id: Windrunner character
            target_id: Target to lash
            direction: Direction to lash ("upward", "downward", "north", etc.)

        Returns:
            {
                "success": bool,
                "description": str,
                "stormlight_used": int,
                "save_roll": int (if target resisted)
            }
        """
        actor = self.entities.get(character_id)
        target = self.entities.get(target_id)

        if not actor or not target:
            return {"success": False, "error": "Actor or target not found"}

        action = LashingAction(direction=direction)
        result = action.execute(actor, target, self.event_queue)

        # Sync entities
        self._sync_entity_to_game_state(character_id)
        self._sync_entity_to_game_state(target_id)

        logger.info(f"🌀 Lashing executed: {character_id} → {target_id} ({direction})")

        return {
            "success": result.success,
            "description": result.description,
            "stormlight_used": result.stormlight_used
        }

    def execute_soulcasting(
        self,
        character_id: str,
        from_substance: str,
        to_substance: str
    ) -> Dict[str, Any]:
        """
        Execute Soulcasting surge.

        Returns:
            {
                "success": bool,
                "description": str,
                "stormlight_used": int,
                "check_roll": int
            }
        """
        actor = self.entities.get(character_id)
        if not actor:
            return {"success": False, "error": "Actor not found"}

        action = SoulcastAction(
            from_substance=from_substance,
            to_substance=to_substance
        )
        result = action.execute(actor, None, self.event_queue)

        self._sync_entity_to_game_state(character_id)

        logger.info(f"✨ Soulcasting: {from_substance} → {to_substance}")

        return {
            "success": result.success,
            "description": result.description,
            "stormlight_used": result.stormlight_used
        }
```

---

## Code Changes Required

### Summary Checklist

#### New Files (9 files)
- [ ] `components/dnd_engine_wrapper.py` (wrapper layer, ~300 lines)
- [ ] `agents/combat_agent.py` (combat pipeline, ~150 lines)
- [ ] `roshar_extensions/stormlight_conditions.py` (Roshar conditions, ~150 lines)
- [ ] `roshar_extensions/radiant_actions.py` (surge abilities, ~150 lines)
- [ ] `tests/test_dnd_engine_wrapper.py` (unit tests, ~100 lines)
- [ ] `tests/test_combat_agent.py` (integration tests)
- [ ] `tests/test_roshar_extensions.py` (Roshar mechanics tests)

#### Modified Files (7 files)
- [ ] `components/game_engine.py` (add wrapper support, ~20 lines)
- [ ] `components/shared_contract.py` (add wrapper ref to DTO, ~1 line)
- [ ] `core/game_initialization.py` (init wrapper, ~15 lines)
- [ ] `haystack_dnd_game.py` (pass wrapper to DTO, ~5 lines)
- [ ] `orchestrator/pipeline_integration.py` (add combat pipeline, ~30 lines)
- [ ] `agents/main_interface_agent_fixed.py` (add combat routing, ~10 lines)
- [ ] `.gitignore` (ignore external/dnd_engine)

#### Configuration Files
- [ ] Add to `.gitignore`: `external/dnd_engine/`
- [ ] Update `README.md` with dnd_engine installation instructions

---

## Testing Strategy

### Phase 1: Unit Tests (Wrapper)
```bash
pytest tests/test_dnd_engine_wrapper.py -v
```

**Tests:**
- Wrapper initialization with characters
- Entity synchronization (CharacterManager → dnd_engine)
- Skill check execution
- Attack execution
- State sync back to GameEngine

### Phase 2: Integration Tests (Combat Pipeline)
```bash
pytest tests/test_combat_agent.py -v
```

**Tests:**
- Combat agent creation
- Combat intent parsing
- Attack execution via wrapper
- Narrative generation
- GameResponseDTO formatting

### Phase 3: Roshar Extensions Tests
```bash
pytest tests/test_roshar_extensions.py -v
```

**Tests:**
- Stormlight infusion
- Stormlight regeneration
- Lashing execution
- Soulcasting with different substances
- Spren bond effects

### Phase 4: End-to-End Gameplay Test

**Manual test scenario:**

```python
from haystack_dnd_game import HaystackDnDGame

# Start game
game = HaystackDnDGame(campaign_name="shards_of_honor")

# Test 1: Skill check (via dnd_engine)
response = game.process_input("I try to persuade the guard")
print(response)
# Should show: skill check result with dnd_engine breakdown

# Test 2: Combat (via dnd_engine + CombatAgent)
response = game.process_input("I attack the Parshendi with my spear")
print(response)
# Should show: combat narrative + damage + HP remaining

# Test 3: Radiant ability (Roshar extension)
response = game.process_input("I infuse myself with Stormlight and use Lashing on the enemy")
print(response)
# Should show: Stormlight usage + Lashing effect

# Test 4: Save/load (verify wrapper state persists)
game.save_game("test_save")
game2 = HaystackDnDGame.load_game("test_save")
# Verify dnd_engine entities restored correctly
```

**Expected results:**
- ✅ All skill checks use dnd_engine mechanics
- ✅ Combat resolves with proper D&D 5e rules
- ✅ Roshar abilities work (Stormlight, Lashing)
- ✅ State persists across save/load
- ✅ No regression in existing features (scenario generation, RAG, NPC)

---

## Roshar-Specific Extensions

### Implemented
- ✅ `StormlightInfusedCondition` (regeneration, bonuses)
- ✅ `SprenBondedCondition` (Radiant bonds)
- ✅ `LashingAction` (Windrunner Gravitation surge)
- ✅ `SoulcastAction` (Transformation surge)

### Future Extensions (After Phase 4)

#### Additional Conditions
- **ShardbearerCondition** (Shardplate/Shardblade bonuses)
- **BurningRhythmsCondition** (Parshendi forms)
- **VoidbringerFormCondition** (Fused powers)

#### Additional Actions
- **AdhesionAction** (Windrunner - stick things together)
- **ProgressionAction** (Edgedancer - healing surge)
- **IlluminationAction** (Lightweaver - create illusions)
- **TransportationAction** (Elsecaller - teleportation)

#### Integration with Scenario Generation
```python
# In scenario_generator_agent.py
# Add Roshar-specific scenario types

ROSHAR_SCENARIO_TYPES = [
    "highstorm_approach",  # Stormlight opportunities
    "spren_interaction",   # Spren dialogue/bonding
    "oath_progression",    # Ideal advancement
    "radiant_training",    # Surge practice
    "shardblade_discovery" # Finding/bonding Shards
]
```

---

## Success Metrics

After complete integration, your system should achieve:

### Combat System ✅
- [ ] Attack rolls calculate automatically with modifiers
- [ ] Damage applied with resistances/vulnerabilities
- [ ] Critical hits deal double damage
- [ ] HP tracking updates in real-time
- [ ] Combat log shows full breakdown

### Skill Check System ✅
- [ ] 7-step pipeline uses dnd_engine for rolls
- [ ] Automatic triggering from scenario choices
- [ ] Advantage/disadvantage applied correctly
- [ ] Full provenance tracking maintained

### Roshar Mechanics ✅
- [ ] Stormlight infusion working
- [ ] At least 2 surge abilities functional (Lashing, Soulcasting)
- [ ] Spren bonds apply bonuses
- [ ] Investiture points tracked

### System Stability ✅
- [ ] No regression in existing features (8.5/10 rating maintained)
- [ ] Save/load includes dnd_engine state
- [ ] Logging comprehensive (no errors)
- [ ] Performance acceptable (<10s per turn)

### Narrative Quality ✅
- [ ] Combat descriptions vivid and Roshar-themed
- [ ] Surge abilities described narratively
- [ ] Integration seamless with scenario generation

**Target Rating:** 9.5/10 (from current 8.5/10)

---

## Rollback Plan

### If Integration Fails

Your existing system is **production-ready (8.5/10)**. Integration is additive, not destructive.

#### Rollback Steps:

1. **Disable wrapper in game_initialization.py:**
```python
# Set dnd_wrapper = None to use fallback systems
dnd_wrapper = None  # Disable dnd_engine integration
```

2. **Revert routing changes:**
```python
# Remove combat_pipeline from orchestrator
# Interface agent falls back to scenario_pipeline
```

3. **Continue with existing system:**
- Your 7-step skill pipeline still works (fallback dice roller)
- Scenario generation unchanged
- RAG, NPC, persistence all functional

**Zero risk to production system.**

---

## Next Steps After Integration

### Week 3: Polish & Enhancement
1. Add spell slot tracking for Radiant surges
2. Implement inventory system (Shardblades, spheres)
3. Advanced NPC memory (SQLite persistence)
4. Quest progression activation

### Week 4: Advanced Features
1. Multi-character party support
2. Legendary creatures (Fused, Unmade)
3. Environmental hazards (Highstorms)
4. Lair actions for boss fights

### Month 2: Production Deployment
1. Web UI (replace CLI)
2. Voice integration (TTS for DM narration)
3. Multiplayer support
4. Campaign builder tools

---

## Conclusion

This integration approach:
- ✅ **Preserves your strengths** (AI agents, 8.5/10 rating)
- ✅ **Fills critical gaps** (combat, spell casting, conditions)
- ✅ **Enables Roshar mechanics** (Stormlight, surges, spren bonds)
- ✅ **Minimal risk** (gradual phases, fallback systems)
- ✅ **Python-native** (no language barriers)
- ✅ **Production-ready timeline** (2 weeks to 9.5/10 system)

**Recommended Timeline:**
- **Week 1:** Foundation + Skill Integration
- **Week 2:** Combat System + Roshar Extensions
- **Result:** Production-grade Roshar D&D with comprehensive mechanics

**Expected Outcome:** Upgrade from 8.5/10 to 9.5/10 system rating.

Ready to begin Phase 1?
