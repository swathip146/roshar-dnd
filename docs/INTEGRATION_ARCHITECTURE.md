# DnD Engine Integration Architecture

## Overview
This document explains how dnd_engine integrates with the Roshar D&D game, including data flow, state management, and class responsibilities.

## State Management Hierarchy

### Data Flow Diagram
```
┌─────────────────────────────────────────────────────────────────────┐
│                    USER INPUT (haystack_dnd_game.py)                │
│  - Player selects action from choices                               │
│  - Creates RequestDTO with action details                           │
└──────────────────────────┬──────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────────┐
│              HAYSTACK DND GAME (Main Game Loop)                     │
│  Class: HaystackDnDGame                                             │
│  - Processes user input                                             │
│  - Creates RequestDTO with _dnd_engine_wrapper_ref                  │
│  - Routes to appropriate handler                                    │
└──────────────────────────┬──────────────────────────────────────────┘
                           ↓
          ┌────────────────┴────────────────┐
          ↓ skill check                     ↓ combat action
┌─────────────────────────────┐   ┌─────────────────────────────┐
│   GAME ENGINE               │   │   GAME ENGINE               │
│   process_skill_check()     │   │   process_combat_action()   │
│   (PHASE 2: ✅ COMPLETE)    │   │   (PHASE 3: 🚧 TODO)        │
└──────────┬──────────────────┘   └──────────┬──────────────────┘
           ↓                                  ↓
┌──────────────────────────────────────────────────────────────────┐
│                   DND_ENGINE_WRAPPER                             │
│  - execute_skill_check()     ✅ Working                          │
│  - execute_attack()          🚧 TODO: Wire to GameEngine         │
│  - execute_saving_throw()    🚧 TODO                             │
│  - apply_damage()            🚧 TODO                             │
└──────────┬───────────────────────────────────────────────────────┘
           ↓
┌──────────────────────────────────────────────────────────────────┐
│                   DND_ENGINE (External Library)                  │
│  - Entity.roll_d20()         ✅ Used for skill checks            │
│  - Entity.skill_bonus()      ✅ Used for skill checks            │
│  - Entity.attack()           🚧 Available, not wired             │
│  - Health.take_damage()      🚧 Available, not wired             │
└──────────┬───────────────────────────────────────────────────────┘
           ↓ results
┌──────────────────────────────────────────────────────────────────┐
│           SYNC BACK TO CHARACTER MANAGER                         │
│  - _sync_entity_to_game_state()                                  │
│  - Updates character.hit_points["current"]                       │
│  - Updates character conditions (TODO)                           │
└──────────────────────────────────────────────────────────────────┘
```

## Class Responsibilities

### 1. **CharacterManager** (Authority)
**File:** `components/character_manager.py`

**Responsibilities:**
- Source of truth for ALL character data (PCs and eventually NPCs)
- Stores: ability_scores, skills, HP, AC, proficiencies, etc.
- Structure: `Dict[character_id: str, CharacterData]`

**Current State:**
- ✅ Tracks player characters
- ❌ Does NOT track NPCs (they only exist in campaign_config as metadata)

**For Phase 3 Combat:**
```python
# TODO: Add NPC tracking to CharacterManager
def add_npc(self, npc_data: Dict[str, Any]) -> str:
    """Add NPC with full D&D stats (not just metadata)"""
    # Convert campaign NPC metadata → full CharacterData
    # Returns npc_id for tracking
```

### 2. **DnDEngineWrapper** (Mechanics Engine)
**File:** `components/dnd_engine_wrapper.py`

**Responsibilities:**
- Translates CharacterManager data → dnd_engine Entities
- Executes D&D 5e mechanics (skill checks, combat, damage)
- Syncs results back to CharacterManager
- Structure: `Dict[character_id: str, Entity]`

**Current Implementation:**
```python
@dataclass
class DnDEngineWrapper:
    game_engine: Any
    character_manager: Any
    entities: Dict[str, Entity]  # Maps char_id → Entity

    def __post_init__(self):
        # Syncs all CharacterManager.characters → entities
        self._sync_characters_to_entities()

    def execute_skill_check(self, character_id, skill, dc):
        # ✅ WORKING: Uses Entity.skill_bonus() + Entity.roll_d20()
        entity = self.entities[character_id]
        skill_bonus = entity.skill_bonus(None, skill)
        roll = entity.roll_d20(skill_bonus, RollType.CHECK)
        # Syncs HP back (in case of state changes)
        self._sync_entity_to_game_state(character_id)
        return results

    def execute_attack(self, attacker_id, target_id, weapon):
        # 🚧 IMPLEMENTED but not wired to GameEngine yet
        attacker = self.entities[attacker_id]
        target = self.entities[target_id]
        # Rolls attack, damage, applies HP changes
        # Syncs both entities back to CharacterManager
```

**For Phase 3:**
- Need to wire `execute_attack()` to `GameEngine.process_combat_action()`
- Need to add NPCs to `self.entities` when combat starts

### 3. **GameEngine** (Orchestrator)
**File:** `components/game_engine.py`

**Responsibilities:**
- Orchestrates all game systems
- Processes skill checks (7-step pipeline) ✅
- Processes combat actions (TODO for Phase 3) 🚧
- Maintains GameState (combat_state, environment, flags)

**Current Implementation:**
```python
class GameEngine:
    def __init__(self, character_manager, policy_engine, ...):
        self.character_manager = character_manager
        self.game_state = GameState(
            characters={},  # Runtime character states
            combat_state={
                "in_combat": False,
                "active_combatants": [],  # char_ids in combat
                "initiative_order": [],
                "current_turn": None
            },
            environment={
                "location": "",
                "npcs_present": []  # Just names, no stats!
            }
        )

    def process_skill_check(self, check_request: RequestDTO):
        # ✅ PHASE 2 COMPLETE
        # Step 1-3: Character data, DC adjustment, advantage
        # Step 4: dnd_wrapper.execute_skill_check() if available
        # Step 5-7: Compare vs DC, log outcome

    def process_combat_action(self, combat_request: RequestDTO):
        # 🚧 PHASE 3 TODO
        # Would call: dnd_wrapper.execute_attack()
        # Update: game_state.combat_state
        # Sync: HP changes back to CharacterManager
```

**GameState Structure:**
```python
@dataclass
class GameState:
    characters: Dict[str, Dict]  # Runtime state per character
    combat_state: Dict[str, Any] = field(default_factory=lambda: {
        "in_combat": False,
        "active_combatants": [],  # List[char_id]
        "initiative_order": [],    # List[Tuple[char_id, initiative_roll]]
        "current_turn": None,      # char_id whose turn it is
        "round_number": 0
    })
    environment: Dict[str, Any] = field(default_factory=lambda: {
        "location": "",
        "time_of_day": "",
        "weather": "",
        "npcs_present": []  # ❌ Only names, not Entity references!
    })
    campaign_flags: Dict[str, Any] = field(default_factory=dict)
```

### 4. **HaystackDnDGame** (Main Loop)
**File:** `haystack_dnd_game.py`

**Responsibilities:**
- Main game loop
- Processes user input
- Creates RequestDTO with wrapper reference
- Routes to GameEngine methods

**Current Implementation:**
```python
class HaystackDnDGame:
    def __init__(self, config: GameInitConfig):
        self.game_engine = config.game_engine
        self.character_manager = config.character_manager
        self.dnd_engine_wrapper = config.dnd_engine_wrapper  # ✅ Phase 2

    def process_input(self, user_input: str):
        # Create RequestDTO with wrapper reference
        request_dto = RequestDTO(
            actor=self.character_id,
            action_type="parsed_from_input",
            _dnd_engine_wrapper_ref=self.dnd_engine_wrapper  # ✅
        )

        # Route to appropriate handler
        if is_skill_check:
            result = self.game_engine.process_skill_check(request_dto)
        elif is_combat:
            result = self.game_engine.process_combat_action(request_dto)  # 🚧 TODO
```

### 5. **SessionManager** (Persistence)
**File:** `components/session_manager.py`

**Responsibilities:**
- Saves/loads game sessions to disk
- NOT the source of truth during gameplay
- Only used for persistence

**Note:** During gameplay, CharacterManager is authority, not SessionManager.

## Data Synchronization Flow

### Phase 2 (Skill Checks) - Current State ✅

```
1. User selects choice with skill check
   ↓
2. HaystackDnDGame creates RequestDTO
   - Includes: actor, skill, dc, _dnd_engine_wrapper_ref
   ↓
3. GameEngine.process_skill_check(request_dto)
   - Step 1-3: Get character data, adjust DC, compute advantage
   - Step 4: Call dnd_wrapper.execute_skill_check()
   ↓
4. DnDEngineWrapper.execute_skill_check()
   - Get Entity from self.entities[character_id]
   - Execute: entity.skill_bonus() + entity.roll_d20()
   - Call: self._sync_entity_to_game_state(character_id)
   ↓
5. _sync_entity_to_game_state()
   - Read: entity.health.get_total_hit_points()
   - Update: character_manager.characters[char_id].hit_points["current"]
   ↓
6. GameEngine continues pipeline
   - Step 5: Compare roll vs DC
   - Step 6: Apply outcome to GameState
   - Step 7: Log to DecisionLogger
   ↓
7. Return results to HaystackDnDGame
   - Generate narrative response
   - Present next choices
```

### Phase 3 (Combat) - Proposed Flow 🚧

```
1. User selects combat action (Attack, Dodge, etc.)
   ↓
2. HaystackDnDGame creates RequestDTO
   - Includes: actor, action_type="attack", target, weapon, _dnd_engine_wrapper_ref
   ↓
3. GameEngine.process_combat_action(request_dto)
   - Check if in combat (game_state.combat_state["in_combat"])
   - If not, initialize combat:
     * Roll initiative for all combatants
     * Add NPCs to CharacterManager (convert metadata → CharacterData)
     * Call dnd_wrapper._sync_characters_to_entities() to add NPC entities
   - Verify it's actor's turn
   - Call dnd_wrapper.execute_attack()
   ↓
4. DnDEngineWrapper.execute_attack(attacker_id, target_id, weapon)
   - Get entities: attacker = self.entities[attacker_id]
                   target = self.entities[target_id]
   - Roll attack: attacker.roll_d20(attack_bonus, RollType.ATTACK)
   - Compare vs target AC
   - If hit: Roll damage, target.health.take_damage(damage)
   - Sync both entities: _sync_entity_to_game_state(attacker_id)
                        _sync_entity_to_game_state(target_id)
   ↓
5. GameEngine updates combat_state
   - Check if target is at 0 HP → remove from active_combatants
   - Advance to next turn in initiative_order
   - Check for combat end condition
   ↓
6. Return results to HaystackDnDGame
   - Generate combat narrative
   - Present next combat choices
```

## NPC Management - Current Gap ❌

### Current State:
NPCs exist only as metadata in `CampaignConfig.key_npcs`:
```python
key_npcs: List[Dict[str, str]] = [
    {
        "name": "Captain Kholinar",
        "role": "Quest Giver",
        "description": "Grizzled veteran..."
    }
]
```

**Problem:** No D&D stats (HP, AC, abilities, etc.)!

### Proposed Solution for Phase 3:

1. **Extend NPC Metadata:**
```python
# In campaign JSON files
"key_npcs": [
    {
        "name": "Bandit Leader",
        "role": "Combat Encounter",
        "description": "...",
        "stats": {  # NEW: D&D stats for combat NPCs
            "level": 3,
            "class": "Fighter",
            "ability_scores": {"strength": 16, "dexterity": 12, ...},
            "hit_points": {"maximum": 25, "current": 25},
            "armor_class": 15,
            "proficiency_bonus": 2,
            "attacks": [
                {"name": "Longsword", "damage": "1d8+3", "type": "slashing"}
            ]
        }
    }
]
```

2. **Add NPCs to CharacterManager when combat starts:**
```python
# In GameEngine.process_combat_action()
if not self.game_state.combat_state["in_combat"]:
    # Initialize combat
    for npc_name in self.game_state.environment["npcs_present"]:
        npc_metadata = self.campaign_config.get_npc_by_name(npc_name)
        if npc_metadata.get("stats"):
            # Convert to CharacterData
            npc_id = self.character_manager.add_npc(npc_metadata["stats"])
            # Wrapper will auto-sync on next call
            self.dnd_engine_wrapper._sync_characters_to_entities()
```

3. **Track NPC entities same as PC entities:**
```python
# DnDEngineWrapper already supports this!
# It syncs ALL characters in CharacterManager.characters
# So adding NPCs to CharacterManager automatically creates NPC entities
```

## Key Classes and Their Locations

| Class | File | Responsibility | Phase |
|-------|------|----------------|-------|
| `HaystackDnDGame` | `haystack_dnd_game.py` | Main game loop, user input | Core |
| `GameEngine` | `components/game_engine.py` | Orchestrates all systems | Core |
| `CharacterManager` | `components/character_manager.py` | Character data authority | Core |
| `DnDEngineWrapper` | `components/dnd_engine_wrapper.py` | D&D mechanics integration | Phase 1-2 ✅ |
| `GameState` | `components/game_engine.py` | Runtime state (combat, env) | Core |
| `SessionManager` | `components/session_manager.py` | Save/load persistence | Core |
| `PolicyEngine` | `components/policy.py` | House rules, difficulty | Core |
| `CampaignConfig` | `components/campaign_config.py` | Campaign metadata | Core |
| `RequestDTO` | `components/shared_contract.py` | Data transfer object | Core |
| `Entity` | `external/dnd_engine/dnd/entity.py` | dnd_engine character | External |

## What's Next: Phase 3 Combat Integration

### Required Changes:

1. **Extend NPC metadata in campaign files** (add D&D stats)
2. **Add `GameEngine.process_combat_action()` method**
3. **Add `CharacterManager.add_npc()` method**
4. **Wire `DnDEngineWrapper.execute_attack()` to combat flow**
5. **Update combat state management in GameEngine**
6. **Create combat-specific RequestDTO handling**

### Integration Points:

- **Input:** User selects combat action → HaystackDnDGame
- **Processing:** GameEngine.process_combat_action() → DnDEngineWrapper.execute_attack()
- **Mechanics:** dnd_engine Entity combat system
- **State Updates:** Sync HP/conditions back to CharacterManager
- **Output:** Combat narrative + next turn choices

---

**Status Summary:**
- ✅ Phase 1: Foundation (wrapper created, entities synced)
- ✅ Phase 2: Skill Check Integration (fully working)
- 🚧 Phase 3: Combat System Integration (next step)
- 🔮 Phase 4: Roshar Extensions (Stormlight, Surges)
