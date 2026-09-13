# mnehmos.rpg.mcp Integration Guide
## Minimal Changes Approach for Roshar D&D

**Repository:** https://github.com/Mnehmos/mnehmos.rpg.mcp
**Language:** TypeScript (MCP Server) + Python (Client)
**Integration Complexity:** Medium-High
**Estimated Effort:** 2-3 weeks
**Risk Level:** Medium

---

## Table of Contents
1. [Overview](#overview)
2. [What mnehmos.rpg.mcp Provides](#what-mnemosrpgmcp-provides)
3. [Architecture Compatibility](#architecture-compatibility)
4. [Integration Strategy](#integration-strategy)
5. [Step-by-Step Implementation](#step-by-step-implementation)
6. [Code Changes Required](#code-changes-required)
7. [MCP Tools Reference](#mcp-tools-reference)
8. [Roshar Adaptation Strategy](#roshar-adaptation-strategy)
9. [Testing Strategy](#testing-strategy)
10. [Rollback Plan](#rollback-plan)

---

## Overview

### Why mnehmos.rpg.mcp?

**Solves ALL critical gaps:**
- ✅ Complete combat system (initiative, attacks, damage, death saves)
- ✅ Spell casting with slot tracking (15+ SRD spells)
- ✅ Persistent NPC memory with relationship tracking
- ✅ Full inventory system (theft, loot, corpses, harvesting)
- ✅ Procedurally generated worlds (28+ biomes)
- ✅ SQLite state persistence with multi-world support
- ✅ Event-driven architecture with audit trails
- ✅ 145+ MCP tools ready for LLM integration

**Key Advantage:** **Rules-enforced backend** - LLMs propose actions, mnehmos validates and executes. No hallucinated mechanics.

**Trade-off:** TypeScript microservice architecture (requires running separate server).

---

## What mnehmos.rpg.mcp Provides

### Core Systems

#### 1. Combat Engine
```typescript
// Full D&D 5e combat mechanics
- Initiative tracking with dexterity tiebreakers
- Attack rolls (melee, ranged, spell attacks)
- Damage calculation with resistances/vulnerabilities
- Death saving throws (3 successes/failures)
- Advantage/disadvantage system
- Critical hits (double damage dice)
- Opportunity attacks
- Legendary actions and lair actions
```

#### 2. Spellcasting System
```typescript
// Spell slot management
- Spell levels 0-9 (cantrips through 9th level)
- Slot consumption and restoration
- 15+ SRD spells implemented:
  - Fireball, Lightning Bolt, Cure Wounds
  - Shield, Mage Armor, Magic Missile
  - Thunderwave, Burning Hands, etc.
- Concentration tracking
- Spell save DC calculation
```

#### 3. NPC Memory System
```typescript
// Persistent NPC relationships
- Conversation history (who said what, when)
- Relationship scores (-100 to +100)
- Memory importance weighting
- Cross-session persistence
- Faction affiliations
- Attitude tracking (hostile, unfriendly, neutral, friendly, helpful)
```

#### 4. Inventory & Economy
```typescript
// Complete item management
- Inventory capacity (weight/bulk)
- Equipment slots (armor, weapons, accessories)
- Theft mechanics with heat system
- Fence economy (sell stolen goods)
- Corpse looting
- Harvestable resources (monster parts)
- Item durability
```

#### 5. World State Persistence
```typescript
// SQLite database storage
- Multi-tenant (multiple DMs/campaigns)
- Multi-world (parallel universes, branching timelines)
- Forking support (create "what-if" scenarios)
- Full audit trail (every event logged)
- Snapshots for time travel
- World state versioning
```

### MCP (Model Context Protocol)

**What is MCP?**
- Anthropic's protocol for connecting LLMs to external tools/data
- Client-server architecture: LLM calls tools, server executes logic
- Ensures LLMs cannot directly mutate state (security/integrity)

**Architecture:**
```
LLM (Claude/Gemini) → MCP Client → HTTP/IPC → MCP Server (mnehmos) → SQLite DB
```

---

## Architecture Compatibility

### Current Roshar Architecture
```
Player Input → HaystackDnDGame
    ↓
RequestDTO (with _game_engine_ref)
    ↓
PipelineOrchestrator
    ↓
Main Interface Agent (Gemini LLM)
    ↓
[scenario_pipeline | rag_pipeline | npc_pipeline]
    ↓
GameResponseDTO
    ↓
_update_state_via_authorities()
```

### After mnehmos Integration (Hybrid Approach)
```
Player Input → HaystackDnDGame
    ↓
RequestDTO (with _mcp_client_ref)  ← NEW: MCP client
    ↓
PipelineOrchestrator
    ↓
Main Interface Agent (Gemini LLM)
    ↓
[scenario_pipeline | combat_pipeline | rag_pipeline | npc_pipeline]
    ↓                          ↓
    ↓                    MCP Tool Calls
    ↓                          ↓
    ↓              mnehmos Server (TypeScript)
    ↓                          ↓
    ↓                    SQLite Database
    ↓                          ↓
    ↓←──── Combat Results ─────┘
    ↓
GameResponseDTO
```

**Key Insight:** mnehmos becomes your **authoritative game state**, while your Python layer handles **AI orchestration and narrative generation**.

---

## Integration Strategy

### Three Approaches (Choose One)

#### **Approach A: Full Replacement** (Most powerful, highest effort)
- Replace GameEngine, CharacterManager with mnehmos state
- All game mechanics handled by mnehmos
- Python layer becomes thin LLM orchestration only
- **Effort:** 3-4 weeks | **Risk:** High | **Benefit:** Production-grade engine

#### **Approach B: Hybrid Python/TypeScript** (RECOMMENDED)
- Run mnehmos as microservice
- Python agents call mnehmos MCP tools for mechanics
- Keep Haystack pipelines and RAG
- Map Roshar concepts to D&D 5e equivalents in mnehmos
- **Effort:** 2 weeks | **Risk:** Medium | **Benefit:** Best-in-class mechanics without full rewrite

#### **Approach C: Selective Feature Adoption**
- Use mnehmos only for specific features (e.g., NPC memory, combat)
- Keep GameEngine for Roshar-specific mechanics
- Sync state between systems
- **Effort:** 1-2 weeks | **Risk:** Low | **Benefit:** Targeted improvements

**This guide focuses on Approach B (Hybrid).**

---

## Step-by-Step Implementation

### Phase 1: Setup mnehmos Server (Days 1-2)

#### Install mnehmos
```bash
# Clone repository
cd /path/to/your/project
git clone https://github.com/Mnehmos/mnehmos.rpg.mcp.git external/mnehmos

cd external/mnehmos

# Install dependencies
npm install

# Build
npm run build
```

#### Start mnehmos Server
```bash
# Run in background
npm run start:server -- --port 3000

# Or use pre-built binary (if available)
./dist/mnehmos-server --port 3000
```

#### Verify Server
```bash
curl http://localhost:3000/health
# Should return: {"status": "ok", "version": "1.0.0"}
```

---

### Phase 2: Python MCP Client (Days 3-4)

#### Install MCP Python SDK
```bash
pip install anthropic-mcp  # Official Anthropic MCP client
# OR build custom REST client
```

#### Create MCP Client Wrapper

**New file:** `adapters/mcp_client.py`

```python
import requests
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

@dataclass
class MCPClient:
    """
    Python client for mnehmos MCP server.

    Provides high-level methods for calling mnehmos tools.
    """

    server_url: str = "http://localhost:3000"
    world_id: str = "roshar_campaign_001"

    def call_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call an MCP tool on mnehmos server.

        Args:
            tool_name: Name of the MCP tool (e.g., "combat_attack")
            params: Tool parameters as dict

        Returns:
            Tool result as dict
        """
        response = requests.post(
            f"{self.server_url}/mcp/tools/{tool_name}",
            json={
                "world_id": self.world_id,
                **params
            }
        )
        response.raise_for_status()
        return response.json()

    # ===== Combat Tools =====

    def start_combat(self, combatants: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Initialize combat encounter.

        Args:
            combatants: List of {entity_id, initiative_bonus}

        Returns:
            {encounter_id, initiative_order, current_turn}
        """
        return self.call_tool("combat_start", {"combatants": combatants})

    def execute_attack(self, attacker_id: str, target_id: str, weapon: str = "unarmed") -> Dict[str, Any]:
        """
        Execute attack roll and damage.

        Returns:
            {
                "hit": bool,
                "attack_roll": int,
                "damage": int,
                "critical": bool,
                "target_hp_remaining": int
            }
        """
        return self.call_tool("combat_attack", {
            "attacker": attacker_id,
            "target": target_id,
            "weapon": weapon
        })

    def cast_spell(self, caster_id: str, spell_name: str, targets: List[str], slot_level: int) -> Dict[str, Any]:
        """
        Cast a spell (consumes slot, applies effects).

        Returns:
            {
                "success": bool,
                "damage": int (if applicable),
                "affected_targets": List[str],
                "slot_consumed": bool
            }
        """
        return self.call_tool("spell_cast", {
            "caster": caster_id,
            "spell": spell_name,
            "targets": targets,
            "slot_level": slot_level
        })

    # ===== NPC Memory Tools =====

    def add_npc_memory(self, npc_id: str, memory: str, importance: int = 5) -> Dict[str, Any]:
        """
        Add memory to NPC (conversation, event).

        Args:
            npc_id: NPC identifier
            memory: Memory text
            importance: 1-10 (higher = more memorable)

        Returns:
            {memory_id, timestamp}
        """
        return self.call_tool("npc_memory_add", {
            "npc_id": npc_id,
            "memory": memory,
            "importance": importance
        })

    def get_npc_memories(self, npc_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve NPC memories (sorted by importance/recency).

        Returns:
            [
                {memory_id, text, importance, timestamp},
                ...
            ]
        """
        result = self.call_tool("npc_memory_retrieve", {
            "npc_id": npc_id,
            "limit": limit
        })
        return result.get("memories", [])

    def update_relationship(self, npc_id: str, character_id: str, delta: int) -> Dict[str, Any]:
        """
        Update NPC relationship score.

        Args:
            delta: -100 to +100 (negative = worse, positive = better)

        Returns:
            {new_score, attitude}  # attitude: hostile, unfriendly, neutral, friendly, helpful
        """
        return self.call_tool("npc_relationship_update", {
            "npc_id": npc_id,
            "character_id": character_id,
            "delta": delta
        })

    # ===== Inventory Tools =====

    def add_item(self, character_id: str, item_name: str, quantity: int = 1) -> Dict[str, Any]:
        """Add item to character inventory."""
        return self.call_tool("inventory_add", {
            "character": character_id,
            "item": item_name,
            "quantity": quantity
        })

    def remove_item(self, character_id: str, item_name: str, quantity: int = 1) -> Dict[str, Any]:
        """Remove item from inventory."""
        return self.call_tool("inventory_remove", {
            "character": character_id,
            "item": item_name,
            "quantity": quantity
        })

    # ===== World State Tools =====

    def create_character(self, character_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create character in mnehmos world.

        Args:
            character_data: {
                "name": str,
                "race": str,
                "class": str,
                "level": int,
                "ability_scores": {str, dex, con, int, wis, cha},
                "max_hp": int,
                "armor_class": int
            }

        Returns:
            {character_id, created_at}
        """
        return self.call_tool("character_create", character_data)

    def save_world_state(self, snapshot_name: str) -> Dict[str, Any]:
        """Create snapshot of current world state."""
        return self.call_tool("world_snapshot", {"name": snapshot_name})

    def load_world_state(self, snapshot_id: str) -> Dict[str, Any]:
        """Restore world to previous snapshot."""
        return self.call_tool("world_restore", {"snapshot_id": snapshot_id})
```

---

### Phase 3: Integrate with GameEngine (Days 5-7)

#### Modify GameEngine to use MCP

**File:** `components/game_engine.py`

```python
from adapters.mcp_client import MCPClient

@dataclass
class GameEngine:
    campaign_config: CampaignConfig
    game_state: GameState
    character_manager: CharacterManager
    mcp_client: Optional[MCPClient] = None  # NEW

    def __init__(self, campaign_config, use_mcp=True):
        self.campaign_config = campaign_config
        self.game_state = self._initialize_state()
        self.character_manager = CharacterManager(campaign_config)

        # NEW: Initialize MCP client
        if use_mcp:
            self.mcp_client = MCPClient(
                server_url="http://localhost:3000",
                world_id=f"roshar_{campaign_config.campaign_name}"
            )
            self._sync_characters_to_mcp()

    def _sync_characters_to_mcp(self):
        """Sync existing characters to mnehmos world."""
        for char_id, character in self.character_manager.characters.items():
            self.mcp_client.create_character({
                "character_id": char_id,
                "name": character.name,
                "race": character.race,
                "class": character.character_class,
                "level": character.level,
                "ability_scores": character.ability_scores,
                "max_hp": character.hit_points,
                "armor_class": 10 + character.ability_modifiers["dexterity"]  # Simplified
            })

    def execute_skill_check(self, character_id, skill, dc):
        """Execute skill check (optionally via MCP)."""
        if self.mcp_client:
            # Use mnehmos for mechanics
            result = self.mcp_client.call_tool("skill_check", {
                "character": character_id,
                "skill": skill,
                "dc": dc
            })
            return result
        else:
            # Fallback to old system
            return self._old_execute_skill_check(character_id, skill, dc)
```

---

### Phase 4: Add Combat Pipeline with MCP (Days 8-10)

**New file:** `agents/mcp_combat_agent.py`

```python
from haystack import component
from haystack.dataclasses import ChatMessage
from config.llm_config import get_gemini_chat_generator

@component
class MCPCombatAgent:
    """
    Combat agent that delegates mechanics to mnehmos MCP server.

    LLM parses intent → MCP tools execute mechanics → LLM generates narrative.
    """

    def __init__(self):
        self.llm = get_gemini_chat_generator("gemini-2.5-flash")

    @component.output_types(response=str, combat_result=dict)
    def run(self, request_dto):
        mcp_client = request_dto._mcp_client_ref
        player_input = request_dto.player_input

        # Step 1: LLM parses combat intent
        intent = self._parse_combat_intent(player_input)

        # Step 2: Execute via MCP
        if intent["action"] == "attack":
            result = mcp_client.execute_attack(
                attacker_id=request_dto.character_id,
                target_id=intent["target"],
                weapon=intent.get("weapon", "unarmed")
            )
        elif intent["action"] == "cast_spell":
            result = mcp_client.cast_spell(
                caster_id=request_dto.character_id,
                spell_name=intent["spell"],
                targets=intent["targets"],
                slot_level=intent["slot_level"]
            )
        else:
            result = {"error": "Unknown combat action"}

        # Step 3: Generate narrative description
        narrative = self._generate_narrative(intent, result)

        return {
            "response": narrative,
            "combat_result": result
        }

    def _parse_combat_intent(self, player_input):
        """Use LLM to extract structured combat intent."""
        messages = [
            ChatMessage.from_system("""
                Extract combat intent from player input.
                Return JSON: {"action": "attack"|"cast_spell", "target": str, "weapon": str, ...}
            """),
            ChatMessage.from_user(player_input)
        ]
        response = self.llm.run(messages)
        # Parse JSON from LLM response
        return self._parse_json(response["replies"][0].content)

    def _generate_narrative(self, intent, result):
        """Use LLM to create vivid combat description."""
        messages = [
            ChatMessage.from_system("You are a D&D narrator. Describe combat results dramatically."),
            ChatMessage.from_user(f"Intent: {intent}\nResult: {result}")
        ]
        response = self.llm.run(messages)
        return response["replies"][0].content
```

---

### Phase 5: NPC Memory Integration (Days 11-12)

**Modify:** `agents/npc_controller_agent.py`

```python
@tool
def generate_npc_response(context, npc_id, player_action):
    mcp_client = context["_mcp_client_ref"]

    # Retrieve NPC memories from mnehmos
    memories = mcp_client.get_npc_memories(npc_id, limit=5)

    # Build context for LLM
    memory_context = "\n".join([m["text"] for m in memories])

    # Generate response (existing LLM logic)
    # ...

    # Store new memory in mnehmos
    interaction_memory = f"Player: {player_action}. NPC responded: {npc_response}"
    mcp_client.add_npc_memory(
        npc_id=npc_id,
        memory=interaction_memory,
        importance=7  # Moderate importance
    )

    # Update relationship if needed
    if attitude_changed:
        mcp_client.update_relationship(
            npc_id=npc_id,
            character_id=context["character_id"],
            delta=attitude_delta  # e.g., +10 for friendly action
        )

    return npc_response
```

---

### Phase 6: State Persistence (Days 13-14)

**Modify:** `storage/session_manager.py`

```python
def save_game(self, save_name: str):
    """Save game state (delegates to mnehmos for world state)."""

    # Save session metadata locally
    self._save_session_metadata(save_name)

    # Save world state to mnehmos
    if self.game_engine.mcp_client:
        snapshot_result = self.game_engine.mcp_client.save_world_state(
            snapshot_name=f"{save_name}_{datetime.now().isoformat()}"
        )
        print(f"World state saved to mnehmos: {snapshot_result['snapshot_id']}")

def load_game(self, save_name: str):
    """Load game state (restores from mnehmos snapshot)."""

    # Load session metadata
    metadata = self._load_session_metadata(save_name)

    # Restore world state from mnehmos
    if self.game_engine.mcp_client:
        self.game_engine.mcp_client.load_world_state(
            snapshot_id=metadata["mnehmos_snapshot_id"]
        )
```

---

## Code Changes Required

### New Files
- [ ] `adapters/mcp_client.py` (MCP client wrapper)
- [ ] `agents/mcp_combat_agent.py` (combat pipeline with MCP)
- [ ] `scripts/start_mnehmos.sh` (server startup script)
- [ ] `tests/test_mcp_integration.py` (integration tests)

### Modified Files

**`core/game_init.py`**
```python
from adapters.mcp_client import MCPClient

def initialize_game_systems(campaign_config, use_mcp=True):
    # ... existing code ...

    if use_mcp:
        mcp_client = MCPClient(world_id=f"roshar_{campaign_config.campaign_name}")
        game_engine.mcp_client = mcp_client

    return {
        "game_engine": game_engine,
        "mcp_client": mcp_client if use_mcp else None
    }
```

**`haystack_dnd_game.py`**
```python
request_dto = RequestDTO(
    player_input=player_input,
    request_type=RequestType.GAME_ACTION,
    _game_engine_ref=self.game_engine,
    _mcp_client_ref=self.mcp_client,  # NEW
    # ... rest unchanged
)
```

**`shared_contract.py`**
```python
@dataclass
class RequestDTO:
    player_input: str
    request_type: RequestType
    _game_engine_ref: Any
    _mcp_client_ref: Any = None  # NEW
```

**`requirements.txt`**
```
# ADD
requests>=2.28.0  # For HTTP calls to mnehmos
anthropic-mcp>=0.1.0  # Optional: official MCP SDK
```

**`docker-compose.yml`** (NEW - optional)
```yaml
version: '3.8'
services:
  mnehmos:
    build: ./external/mnehmos
    ports:
      - "3000:3000"
    volumes:
      - ./data/mnehmos_db:/app/data
    environment:
      - NODE_ENV=production
```

---

## MCP Tools Reference

### Most Useful Tools for Roshar (145+ total)

#### Combat (8 tools)
- `combat_start` - Initialize encounter
- `combat_attack` - Execute attack roll
- `combat_damage` - Apply damage
- `combat_end_turn` - Advance initiative
- `combat_flee` - Escape combat
- `combat_grapple` - Grapple attempt
- `combat_shove` - Shove attempt
- `combat_legendary_action` - Use legendary action

#### Spellcasting (12 tools)
- `spell_cast` - Cast spell (consumes slot)
- `spell_prepare` - Prepare spells
- `spell_slots_restore` - Long rest
- `spell_concentration_check` - Maintain concentration
- `spell_counterspell` - Attempt counterspell
- `spell_ritual_cast` - Ritual casting (no slot)

#### NPC Memory (14 tools)
- `npc_memory_add` - Add memory
- `npc_memory_retrieve` - Get memories
- `npc_memory_search` - Search by keyword
- `npc_relationship_update` - Change attitude
- `npc_relationship_get` - Check current relationship
- `npc_faction_assign` - Set faction
- `npc_conversation_log` - Record dialogue

#### Inventory (15 tools)
- `inventory_add` - Add item
- `inventory_remove` - Remove item
- `inventory_transfer` - Give to another character
- `inventory_equip` - Equip weapon/armor
- `inventory_unequip` - Unequip
- `loot_corpse` - Loot dead enemy
- `harvest_resource` - Harvest monster parts

#### World Management (12 tools)
- `world_create` - New world
- `world_fork` - Branch timeline
- `world_snapshot` - Save state
- `world_restore` - Load state
- `world_time_advance` - Progress time
- `location_create` - Add location
- `location_travel` - Move to location

---

## Roshar Adaptation Strategy

### Mapping D&D 5e to Roshar

mnehmos uses standard D&D 5e rules. Here's how to adapt Roshar concepts:

#### 1. Character Classes → Radiant Orders
```python
# In mcp_client.py
ROSHAR_CLASS_MAPPING = {
    "Windrunner": "Fighter",  # Similar combat focus
    "Lightweaver": "Bard",     # Illusion magic
    "Edgedancer": "Rogue",     # Agility, mobility
    "Bondsmith": "Cleric",     # Support, healing
    "Dustbringer": "Sorcerer", # Elemental damage
    "Truthwatcher": "Wizard",  # Knowledge, insight
    "Willshaper": "Druid",     # Terrain manipulation
    "Stoneward": "Barbarian",  # Durability
    "Skybreaker": "Paladin",   # Law, justice
    "Elsecaller": "Wizard"     # Teleportation
}

def create_roshar_character(self, character_data):
    # Map Radiant order to D&D class
    dnd_class = ROSHAR_CLASS_MAPPING[character_data["radiant_order"]]

    return self.call_tool("character_create", {
        **character_data,
        "class": dnd_class
    })
```

#### 2. Stormlight → Spell Slots
```python
# Treat Stormlight as spell slots
# Level 1 Radiant = 2 Stormlight points = 2 spell slots
# Surge abilities = spells

SURGE_TO_SPELL_MAPPING = {
    "Adhesion": "Mage_Armor",      # Windrunner
    "Gravitation": "Levitate",     # Windrunner (Lashing)
    "Division": "Fireball",        # Dustbringer
    "Abrasion": "Haste",           # Edgedancer
    "Progression": "Cure_Wounds",  # Edgedancer
    "Illumination": "Minor_Illusion",  # Lightweaver
    "Transformation": "Alter_Self",    # Lightweaver
    "Transportation": "Misty_Step",    # Elsecaller
    "Cohesion": "Stone_Shape",         # Willshaper
    "Tension": "Blade_Ward"            # Stoneward
}

def use_surge(self, character_id, surge_name, targets):
    spell_name = SURGE_TO_SPELL_MAPPING.get(surge_name)
    return self.cast_spell(
        caster_id=character_id,
        spell_name=spell_name,
        targets=targets,
        slot_level=1  # Most surges are level 1
    )
```

#### 3. Shardblades → Magic Weapons
```python
# Create custom "Shardblade" weapon
def create_shardblade(self, character_id):
    return self.call_tool("inventory_add", {
        "character": character_id,
        "item": {
            "name": "Shardblade",
            "type": "weapon",
            "damage_dice": "3d8",  # Powerful!
            "damage_type": "slashing",
            "properties": ["versatile", "finesse"],
            "magical": True,
            "rarity": "legendary"
        }
    })
```

#### 4. Spren Bonds → NPC Companions
```python
# Track spren as special NPC with relationship
def bond_spren(self, character_id, spren_type):
    # Create spren NPC
    spren_id = f"spren_{character_id}"
    self.call_tool("character_create", {
        "character_id": spren_id,
        "name": f"{spren_type} Spren",
        "race": "Fey",  # Closest equivalent
        "class": "Companion"
    })

    # Set max relationship
    self.update_relationship(
        npc_id=spren_id,
        character_id=character_id,
        delta=100  # Perfect bond
    )

    # Add memory
    self.add_npc_memory(
        npc_id=spren_id,
        memory=f"Bonded with {character_id} as their {spren_type} spren",
        importance=10
    )
```

---

## Testing Strategy

### Unit Tests
```python
# tests/test_mcp_integration.py
import pytest
from adapters.mcp_client import MCPClient

@pytest.fixture
def mcp_client():
    return MCPClient(world_id="test_world")

def test_combat_attack(mcp_client):
    # Create characters
    mcp_client.create_character({
        "character_id": "test_kaladin",
        "name": "Kaladin",
        "class": "Fighter",
        "level": 5,
        "max_hp": 50,
        "armor_class": 16
    })

    mcp_client.create_character({
        "character_id": "test_enemy",
        "name": "Parshendi",
        "class": "Barbarian",
        "level": 3,
        "max_hp": 30,
        "armor_class": 14
    })

    # Execute attack
    result = mcp_client.execute_attack(
        attacker_id="test_kaladin",
        target_id="test_enemy"
    )

    assert "hit" in result
    assert "damage" in result

def test_npc_memory(mcp_client):
    mcp_client.add_npc_memory(
        npc_id="syl",
        memory="Met Kaladin at Bridge Four",
        importance=8
    )

    memories = mcp_client.get_npc_memories("syl")
    assert len(memories) == 1
    assert "Kaladin" in memories[0]["text"]
```

### Integration Tests
```bash
# Start mnehmos server
./scripts/start_mnehmos.sh

# Run integration tests
pytest tests/test_mcp_integration.py -v

# Run full game scenario
python tests/test_full_game_with_mcp.py
```

---

## Rollback Plan

### If mnehmos Integration Fails

#### Step 1: Stop mnehmos Server
```bash
pkill -f mnehmos-server
```

#### Step 2: Disable MCP in Code
```python
# In core/game_init.py
initialize_game_systems(campaign_config, use_mcp=False)
```

#### Step 3: Fallback to Old System
All agents check for `mcp_client` existence:
```python
if context.get("_mcp_client_ref"):
    # Use MCP
else:
    # Use old GameEngine methods
```

**Zero risk:** Your existing system remains functional.

---

## Success Metrics

After integration:

✅ **Combat working via mnehmos**
- Attacks resolved with proper D&D 5e mechanics
- Damage applied with resistances
- Death saves tracked

✅ **NPC memory persistent**
- Conversations saved across sessions
- Relationship changes tracked
- SQLite database growing

✅ **Spell casting functional**
- Slot consumption working
- Spell effects applied correctly
- Concentration tracked

✅ **State persistence**
- Save/load via snapshots
- Multi-session continuity
- Audit trail visible

---

## Pros & Cons Summary

### Pros
- ✅ Production-grade D&D 5e engine (800+ tests)
- ✅ Persistent NPC memory (SQLite)
- ✅ Full combat, spells, inventory
- ✅ Event audit trail (debugging, rewind)
- ✅ Multi-world support (multiple campaigns)
- ✅ Rules enforcement (no LLM hallucinations)

### Cons
- ❌ TypeScript microservice (added complexity)
- ❌ D&D 5e specific (requires Roshar adaptation)
- ❌ Network latency (HTTP calls)
- ❌ Learning curve (MCP protocol)
- ❌ Deployment complexity (two services)

---

## Next Steps After Integration

1. **Extend MCP Tools**
   - Custom tools for Roshar mechanics (Shardplate, Rhythms)
   - Spren interaction tools

2. **Optimize Performance**
   - Cache frequent MCP calls
   - Batch operations where possible

3. **UI Improvements**
   - Display combat log from mnehmos
   - Show NPC relationship meters
   - Inventory management UI

4. **Advanced Features**
   - Forking for "what-if" scenarios
   - Time travel debugging
   - Multi-party campaigns

---

## Conclusion

mnehmos.rpg.mcp provides a **complete, battle-tested game engine** with features far beyond what you'd build yourself. The TypeScript microservice architecture adds complexity but ensures:
- **Separation of concerns** (mechanics vs narrative)
- **Rules integrity** (LLMs can't cheat)
- **Production-ready persistence** (SQLite with migrations)

**Recommended if:**
- You want a comprehensive solution
- You're comfortable running TypeScript services
- You value rules enforcement over full control

**Timeline:** 2-3 weeks for hybrid integration.
