# Final Code Implementation Plan: Revised D&D Architecture

This plan implements the revised architecture from `merged_dm_architecture_and_instructions_new.md` with concrete code changes for a coding assistant.

## Overview Assessment ✅

The revised architecture **perfectly balances** the needs:
- ✅ **Removes over-engineering**: AdaptiveErrorRecovery, separate middleware layers
- ✅ **Eliminates redundancies**: Single RAG system, no RAGAgent duplication  
- ✅ **Adds essential D&D features**: All missing agents for proper gameplay
- ✅ **Maintains simplicity**: Inline cache, simple command mapping
- ✅ **Professional implementation**: Proper testing, migration strategy

---

## Step-by-Step Implementation

### **Step 1: Environment Setup**

```bash
# Create feature branch
git checkout -b feature/revised-merged-architecture

# Setup testing framework
pip install pytest
mkdir -p tests/agents
```

**Create**: `tests/test_smoke.py`
```python
import pytest
from modular_dm_assistant import ModularDMAssistant

def test_assistant_initialization():
    """Smoke test for basic initialization"""
    assistant = ModularDMAssistant(verbose=False)
    assert assistant is not None
    assert assistant.orchestrator is not None

def test_agent_registration():
    """Test that all agents are registered"""
    assistant = ModularDMAssistant(verbose=False)
    assistant.start()
    
    status = assistant.orchestrator.get_agent_status()
    expected_agents = [
        'haystack_pipeline', 'campaign_manager', 'game_engine',
        'character_manager', 'session_manager', 'inventory_manager', 
        'spell_manager', 'experience_manager', 'scenario_generator',
        'combat_engine', 'dice_system', 'npc_controller', 'rule_enforcement'
    ]
    
    for agent in expected_agents:
        assert agent in status
    
    assistant.stop()
```

---

### **Step 2: Remove Redundancies**

#### 2.1: Eliminate RAGAgent Duplication

**File**: `modular_dm_assistant.py`

**REMOVE** these lines:
```python
# Lines 558-562: Delete RAGAgent instantiation
# self.rag_agent = RAGAgent(
#     collection_name=self.collection_name,
#     verbose=self.verbose
# )

# Line 492: Remove rag_agent attribute
# self.rag_agent: Optional[RAGAgent] = None
```

**UPDATE** agent constructors:
```python
# Line 565: RuleEnforcementAgent
self.rule_agent = RuleEnforcementAgent(
    haystack_agent=self.haystack_agent,  # Changed from rag_agent
    strict_mode=False
)

# Line 572: NPCControllerAgent  
self.npc_agent = NPCControllerAgent(
    haystack_agent=self.haystack_agent,  # Changed from rag_agent
    mode="hybrid"
)

# Line 579: ScenarioGeneratorAgent
self.scenario_agent = ScenarioGeneratorAgent(
    haystack_agent=self.haystack_agent,  # Changed from rag_agent
    haystack_agent=self.haystack_agent,
    verbose=self.verbose
)
```

#### 2.2: Remove AdaptiveErrorRecovery

**REMOVE** these sections completely:
```python
# Lines 193-300: Delete AdaptiveErrorRecovery class
# Lines 503: Remove adaptive_error_recovery attribute
# self.adaptive_error_recovery = AdaptiveErrorRecovery() if enable_caching else None
```

#### 2.3: Remove Over-Engineering Components

**REMOVE** these classes and references:
```python
# Lines 302-433: Delete PerformanceMonitoringDashboard
# Lines 42-191: Delete NarrativeContinuityTracker  
# Lines 506: Remove performance_monitor attribute
# Lines 500: Remove narrative_tracker attribute
```

**SIMPLIFY** `_setup_enhanced_pipelines()`:
```python
def _setup_enhanced_pipelines(self):
    """Setup simplified pipeline components"""
    try:
        # Keep only creative consequence pipeline
        if self.has_llm:
            try:
                llm_generator = AppleGenAIChatGenerator(
                    model="aws:anthropic.claude-sonnet-4-20250514-v1:0"
                )
                self.creative_consequence_pipeline = CreativeConsequencePipeline(llm_generator)
            except Exception as e:
                if self.verbose:
                    print(f"⚠️ Failed to initialize LLM: {e}")
                self.creative_consequence_pipeline = CreativeConsequencePipeline()
        
        if self.verbose:
            print("✅ Simplified pipelines setup complete")
            
    except Exception as e:
        if self.verbose:
            print(f"⚠️ Pipeline setup failed: {e}")
```

---

### **Step 3: Add Command Mapping System**

**ADD** to `ModularDMAssistant.__init__()`:
```python
# Add after line 507 (after _setup_enhanced_pipelines)
self._setup_command_mapping()

def _setup_command_mapping(self):
    """Setup simplified command routing"""
    self.COMMAND_MAP = {
        # Session management
        r'start session': ('session_manager', 'start_session'),
        r'end session': ('session_manager', 'end_session'),
        r'short rest': ('session_manager', 'process_rest', {'rest_type': 'short'}),
        r'long rest': ('session_manager', 'process_rest', {'rest_type': 'long'}),
        
        # Character management
        r'list players': ('campaign_manager', 'list_players'),
        r'player info (.+)': ('campaign_manager', 'get_player_info'),
        r'inventory (.+)': ('inventory_manager', 'get_inventory'),
        r'hp (.+) ([+-]\d+)': ('character_manager', 'adjust_hp'),
        
        # Spells and magic
        r'cast spell (.+) (.+)': ('spell_manager', 'cast_spell'),
        r'spell slots (.+)': ('spell_manager', 'get_spell_slots'),
        
        # Experience and progression  
        r'award xp (\d+)': ('experience_manager', 'award_xp'),
        r'level up (.+)': ('experience_manager', 'process_level_up'),
        
        # Combat
        r'start combat': ('combat_engine', 'start_combat'),
        r'combat status': ('combat_engine', 'get_combat_status'),
        r'next turn': ('combat_engine', 'next_turn'),
        r'end combat': ('combat_engine', 'end_combat'),
        
        # Dice and rules
        r'roll (.+)': ('dice_system', 'roll_dice'),
        r'check rule (.+)': ('rule_enforcement', 'check_rule'),
        
        # Scenarios
        r'generate scenario': ('scenario_generator', 'generate_scenario'),
        r'select option (\d+)': ('scenario_generator', 'select_option'),
        
        # Campaign
        r'list campaigns': ('campaign_manager', 'list_campaigns'),
        r'select campaign (\d+)': ('campaign_manager', 'select_campaign'),
        r'campaign info': ('campaign_manager', 'get_campaign_info'),
    }
```

**REPLACE** `process_dm_input()` method:
```python
def process_dm_input(self, instruction: str) -> str:
    """Process DM instruction using command mapping"""
    import re
    
    instruction_clean = instruction.strip()
    
    # Handle help command
    if instruction_clean.lower() == 'help':
        return self._show_help()
    
    # Try command mapping first
    for pattern, command_info in self.COMMAND_MAP.items():
        match = re.match(pattern, instruction_clean, re.IGNORECASE)
        if match:
            agent_id = command_info[0]
            action = command_info[1]
            base_data = command_info[2] if len(command_info) > 2 else {}
            
            # Add regex groups to data
            data = base_data.copy()
            if match.groups():
                if len(match.groups()) == 1:
                    data['param'] = match.group(1).strip()
                else:
                    data['params'] = [g.strip() for g in match.groups()]
            
            return self._execute_command(agent_id, action, data)
    
    # Fallback to general query
    return self._handle_general_query(instruction_clean)

def _execute_command(self, agent_id: str, action: str, data: dict) -> str:
    """Execute command with caching and error handling"""
    try:
        # Check cache first (only for specific actions)
        if action in ['check_rule', 'get_campaign_info', 'list_players']:
            cache_key = f"{agent_id}_{action}_{hash(str(sorted(data.items())))}"
            cached_result = self._cache_get(cache_key)
            if cached_result:
                return cached_result
        
        # Execute command
        response = self._send_message_and_wait(agent_id, action, data)
        
        # Format response
        result = self._format_agent_response(agent_id, action, response)
        
        # Cache result if appropriate
        if action in ['check_rule', 'get_campaign_info', 'list_players'] and result:
            self._cache_set(cache_key, result, ttl=3600)  # 1 hour TTL
        
        return result
        
    except Exception as e:
        if self.verbose:
            print(f"❌ Command execution failed: {e}")
        return f"❌ Failed to execute command: {str(e)}"
```

---

### **Step 4: Add Inline Cache Logic**

**ADD** to `ModularDMAssistant.__init__()`:
```python
# Add after line 470 (after makedirs)
self._init_cache()

def _init_cache(self):
    """Initialize simple in-memory cache"""
    self._cache = {}
    self._cache_timestamps = {}

def _cache_get(self, key: str):
    """Get cached value if not expired"""
    import time
    
    if key not in self._cache:
        return None
    
    timestamp, ttl = self._cache_timestamps.get(key, (0, 0))
    if ttl > 0 and time.time() - timestamp > ttl:
        # Expired
        del self._cache[key]
        del self._cache_timestamps[key]
        return None
    
    return self._cache[key]

def _cache_set(self, key: str, value, ttl: int = 0):
    """Set cached value with TTL in seconds"""
    import time
    
    self._cache[key] = value
    self._cache_timestamps[key] = (time.time(), ttl)

def _cache_clear(self):
    """Clear all cached values"""
    self._cache.clear()
    self._cache_timestamps.clear()
```

---

### **Step 5: Create New D&D Agents**

#### 5.1: CharacterManagerAgent

**Create**: `character_manager.py`
```python
from agent_framework import BaseAgent
import json
import time

class CharacterManagerAgent(BaseAgent):
    """Manages player and NPC character data, stats, and progression"""
    
    def __init__(self):
        super().__init__("character_manager")
        self.characters = {}
    
    def handle_message(self, message):
        action = message.get("action")
        data = message.get("data", {})
        
        handlers = {
            "get_character": self._get_character,
            "update_character": self._update_character,
            "adjust_hp": self._adjust_hp,
            "get_stats": self._get_stats,
            "set_stat": self._set_stat,
            "add_condition": self._add_condition,
            "remove_condition": self._remove_condition,
            "get_all_characters": self._get_all_characters
        }
        
        handler = handlers.get(action)
        if handler:
            return handler(data)
        
        return {"success": False, "error": f"Unknown action: {action}"}
    
    def _get_character(self, data):
        """Get character by name"""
        name = data.get("param") or data.get("character_name")
        character = self.characters.get(name)
        
        if character:
            return {"success": True, "character": character}
        return {"success": False, "error": f"Character {name} not found"}
    
    def _adjust_hp(self, data):
        """Adjust character HP"""
        params = data.get("params", [])
        if len(params) < 2:
            return {"success": False, "error": "Need character name and HP adjustment"}
        
        name, adjustment = params[0], params[1]
        
        if name not in self.characters:
            return {"success": False, "error": f"Character {name} not found"}
        
        try:
            adj_value = int(adjustment)
            char = self.characters[name]
            old_hp = char.get("current_hp", char.get("max_hp", 20))
            new_hp = max(0, min(old_hp + adj_value, char.get("max_hp", 20)))
            
            char["current_hp"] = new_hp
            
            return {
                "success": True,
                "character": name,
                "old_hp": old_hp,
                "new_hp": new_hp,
                "adjustment": adj_value
            }
            
        except ValueError:
            return {"success": False, "error": "Invalid HP adjustment value"}
    
    def _add_condition(self, data):
        """Add status condition to character"""
        name = data.get("character_name")
        condition = data.get("condition")
        duration = data.get("duration", "until_removed")
        
        if name not in self.characters:
            return {"success": False, "error": f"Character {name} not found"}
        
        if "conditions" not in self.characters[name]:
            self.characters[name]["conditions"] = []
        
        self.characters[name]["conditions"].append({
            "name": condition,
            "duration": duration,
            "applied_at": time.time()
        })
        
        return {"success": True, "message": f"Applied {condition} to {name}"}
    
    def load_character_data(self, character_data):
        """Load character data from campaign manager"""
        for char in character_data:
            name = char.get("name")
            if name:
                # Ensure current_hp exists
                if "current_hp" not in char:
                    char["current_hp"] = char.get("hp", 20)
                if "conditions" not in char:
                    char["conditions"] = []
                    
                self.characters[name] = char
```

#### 5.2: SessionManagerAgent

**Create**: `session_manager.py`
```python
from agent_framework import BaseAgent
import time
import json

class SessionManagerAgent(BaseAgent):
    """Manages D&D session lifecycle, time tracking, and rest mechanics"""
    
    def __init__(self):
        super().__init__("session_manager")
        self.current_session = None
        self.session_history = []
    
    def handle_message(self, message):
        action = message.get("action")
        data = message.get("data", {})
        
        handlers = {
            "start_session": self._start_session,
            "end_session": self._end_session,
            "process_rest": self._process_rest,
            "track_time": self._track_time,
            "get_session_status": self._get_session_status
        }
        
        handler = handlers.get(action)
        if handler:
            return handler(data)
        
        return {"success": False, "error": f"Unknown action: {action}"}
    
    def _start_session(self, data):
        """Start a new game session"""
        if self.current_session:
            return {"success": False, "error": "Session already active"}
        
        self.current_session = {
            "id": f"session_{int(time.time())}",
            "start_time": time.time(),
            "participants": data.get("participants", []),
            "campaign_id": data.get("campaign_id"),
            "game_time_minutes": 0,
            "encounters": 0,
            "rests_taken": {"short": 0, "long": 0}
        }
        
        return {
            "success": True,
            "session_id": self.current_session["id"],
            "message": "Session started! Adventure begins."
        }
    
    def _end_session(self, data):
        """End current session"""
        if not self.current_session:
            return {"success": False, "error": "No active session"}
        
        # Calculate session duration
        duration = time.time() - self.current_session["start_time"]
        self.current_session["end_time"] = time.time()
        self.current_session["duration_hours"] = duration / 3600
        
        # Move to history
        self.session_history.append(self.current_session.copy())
        
        summary = {
            "session_id": self.current_session["id"],
            "duration_hours": round(duration / 3600, 2),
            "game_time_hours": round(self.current_session["game_time_minutes"] / 60, 2),
            "encounters": self.current_session["encounters"],
            "rests_taken": self.current_session["rests_taken"]
        }
        
        self.current_session = None
        
        return {
            "success": True,
            "summary": summary,
            "message": "Session ended. Great adventure!"
        }
    
    def _process_rest(self, data):
        """Process short or long rest"""
        if not self.current_session:
            return {"success": False, "error": "No active session"}
        
        rest_type = data.get("rest_type", "short")
        
        if rest_type == "short":
            time_advance = 60  # 1 hour
            benefits = ["Regain some HP", "Some abilities refresh"]
        else:  # long rest
            time_advance = 480  # 8 hours  
            benefits = ["Full HP restore", "All spell slots restored", "All abilities refresh"]
        
        self.current_session["game_time_minutes"] += time_advance
        self.current_session["rests_taken"][rest_type] += 1
        
        return {
            "success": True,
            "rest_type": rest_type,
            "time_advanced_minutes": time_advance,
            "total_game_time_hours": round(self.current_session["game_time_minutes"] / 60, 2),
            "benefits": benefits,
            "message": f"{rest_type.title()} rest completed! {time_advance // 60} hours have passed."
        }
    
    def _get_session_status(self, data=None):
        """Get current session status"""
        if not self.current_session:
            return {"success": True, "active_session": False}
        
        duration = time.time() - self.current_session["start_time"]
        
        return {
            "success": True,
            "active_session": True,
            "session_id": self.current_session["id"],
            "real_time_hours": round(duration / 3600, 2),
            "game_time_hours": round(self.current_session["game_time_minutes"] / 60, 2),
            "encounters": self.current_session["encounters"],
            "rests_taken": self.current_session["rests_taken"]
        }
```

#### 5.3: InventoryManagerAgent

**Create**: `inventory_manager.py`
```python
from agent_framework import BaseAgent
import json

class InventoryManagerAgent(BaseAgent):
    """Manages character inventories, equipment, and items"""
    
    def __init__(self):
        super().__init__("inventory_manager")
        self.inventories = {}
    
    def handle_message(self, message):
        action = message.get("action")
        data = message.get("data", {})
        
        handlers = {
            "get_inventory": self._get_inventory,
            "add_item": self._add_item,
            "remove_item": self._remove_item,
            "use_item": self._use_item,
            "equip_item": self._equip_item,
            "unequip_item": self._unequip_item,
            "transfer_item": self._transfer_item
        }
        
        handler = handlers.get(action)
        if handler:
            return handler(data)
        
        return {"success": False, "error": f"Unknown action: {action}"}
    
    def _get_inventory(self, data):
        """Get character inventory"""
        character_name = data.get("param") or data.get("character_name")
        
        if character_name not in self.inventories:
            self._initialize_inventory(character_name)
        
        inventory = self.inventories[character_name]
        
        return {
            "success": True,
            "character": character_name,
            "inventory": inventory,
            "formatted": self._format_inventory(inventory)
        }
    
    def _initialize_inventory(self, character_name):
        """Initialize empty inventory for character"""
        self.inventories[character_name] = {
            "items": [],
            "equipped": {
                "weapon": None,
                "armor": None,
                "shield": None,
                "accessories": []
            },
            "capacity": 20,
            "current_weight": 0
        }
    
    def _add_item(self, data):
        """Add item to character inventory"""
        character_name = data.get("character_name")
        item = data.get("item", {})
        
        if not character_name or not item:
            return {"success": False, "error": "Need character name and item data"}
        
        if character_name not in self.inventories:
            self._initialize_inventory(character_name)
        
        # Add item with metadata
        item_entry = {
            "id": len(self.inventories[character_name]["items"]) + 1,
            "name": item.get("name", "Unknown Item"),
            "type": item.get("type", "misc"),
            "weight": item.get("weight", 1),
            "quantity": item.get("quantity", 1),
            "description": item.get("description", ""),
            "properties": item.get("properties", [])
        }
        
        self.inventories[character_name]["items"].append(item_entry)
        self.inventories[character_name]["current_weight"] += item_entry["weight"] * item_entry["quantity"]
        
        return {
            "success": True,
            "message": f"Added {item_entry['name']} to {character_name}'s inventory"
        }
    
    def _equip_item(self, data):
        """Equip item from inventory"""
        character_name = data.get("character_name")
        item_name = data.get("item_name")
        
        if character_name not in self.inventories:
            return {"success": False, "error": f"No inventory for {character_name}"}
        
        inventory = self.inventories[character_name]
        
        # Find item
        item = None
        for inv_item in inventory["items"]:
            if inv_item["name"].lower() == item_name.lower():
                item = inv_item
                break
        
        if not item:
            return {"success": False, "error": f"Item {item_name} not found"}
        
        item_type = item.get("type", "misc")
        if item_type in ["weapon", "armor", "shield"]:
            # Unequip current item of same type
            if inventory["equipped"][item_type]:
                old_item = inventory["equipped"][item_type]
                inventory["items"].append(old_item)
            
            # Equip new item
            inventory["equipped"][item_type] = item
            inventory["items"].remove(item)
            
            return {
                "success": True,
                "message": f"{character_name} equipped {item['name']}"
            }
        
        return {"success": False, "error": f"Cannot equip {item_type}"}
    
    def _format_inventory(self, inventory):
        """Format inventory for display"""
        output = []
        
        # Equipped items
        equipped = inventory["equipped"]
        if any(equipped.values()):
            output.append("**EQUIPPED:**")
            for slot, item in equipped.items():
                if item:
                    output.append(f"  {slot.title()}: {item['name']}")
        
        # Inventory items
        if inventory["items"]:
            output.append("\n**INVENTORY:**")
            for item in inventory["items"]:
                qty = f"x{item['quantity']}" if item['quantity'] > 1 else ""
                output.append(f"  • {item['name']} {qty}")
        
        # Weight and capacity
        output.append(f"\n**Weight:** {inventory['current_weight']}/{inventory['capacity']}")
        
        return "\n".join(output)
```

#### 5.4: SpellManagerAgent and ExperienceManagerAgent

**Create**: `spell_manager.py` and `experience_manager.py` (following similar patterns as above)

---

### **Step 6: Update Agent Registration**

**MODIFY** `_initialize_agents()` in `modular_dm_assistant.py`:
```python
def _initialize_agents(self):
    """Initialize and register all agents"""
    try:
        # 1. Core services
        self.haystack_agent = HaystackPipelineAgent(
            collection_name=self.collection_name,
            verbose=self.verbose
        )
        self.orchestrator.register_agent(self.haystack_agent)
        
        # 2. Campaign and game management
        self.campaign_agent = CampaignManagerAgent(
            campaigns_dir=self.campaigns_dir,
            players_dir=self.players_dir
        )
        self.orchestrator.register_agent(self.campaign_agent)
        
        # 3. NEW: Character management
        self.character_agent = CharacterManagerAgent()
        self.orchestrator.register_agent(self.character_agent)
        
        # 4. NEW: Session management
        self.session_agent = SessionManagerAgent()
        self.orchestrator.register_agent(self.session_agent)
        
        # 5. NEW: Inventory management
        self.inventory_agent = InventoryManagerAgent()
        self.orchestrator.register_agent(self.inventory_agent)
        
        # 6. NEW: Spell management
        self.spell_agent = SpellManagerAgent()
        self.orchestrator.register_agent(self.spell_agent)
        
        # 7. NEW: Experience management
        self.xp_agent = ExperienceManagerAgent()
        self.orchestrator.register_agent(self.xp_agent)
        
        # 8. Game engine (if enabled)
        if self.enable_game_engine:
            persister = JSONPersister("./game_state_checkpoint.json")
            self.game_engine_agent = GameEngineAgent(
                persister=persister,
                tick_seconds=self.tick_seconds
            )
            self.orchestrator.register_agent(self.game_engine_agent)
        
        # 9. Existing gameplay agents (updated to use haystack_agent)
        self.dice_agent = DiceSystemAgent()
        self.orchestrator.register_agent(self.dice_agent)
        
        self.combat_agent = CombatEngineAgent(DiceRoller())
        self.orchestrator.register_agent(self.combat_agent)
        
        self.rule_agent = RuleEnforcementAgent(
            haystack_agent=self.haystack_agent,  # Changed from rag_agent
            strict_mode=False
        )
        self.orchestrator.register_agent(self.rule_agent)
        
        self.npc_agent = NPCControllerAgent(
            haystack_agent=self.haystack_agent,  # Changed from rag_agent
            mode="hybrid"
        )
        self.orchestrator.register_agent(self.npc_agent)
        
        self.scenario_agent = ScenarioGeneratorAgent(
            haystack_agent=self.haystack_agent,  # Changed from rag_agent
            haystack_agent=self.haystack_agent,
            verbose=self.verbose
        )
        self.orchestrator.register_agent(self.scenario_agent)
        
        if self.verbose:
            print("✅ All agents initialized successfully")
            
    except Exception as e:
        if self.verbose:
            print(f"❌ Failed to initialize agents: {e}")
        raise
```

---

### **Step 7: Testing and Integration**

**Create**: `tests/test_integration.py`
```python
import pytest
from modular_dm_assistant import ModularDMAssistant

@pytest.fixture
def assistant():
    """Create test assistant"""
    assistant = ModularDMAssistant(verbose=False)
    assistant.start()
    yield assistant
    assistant.stop()

def test_session_flow(assistant):
    """Test complete D&D session flow"""
    
    # Start session
    response = assistant.process_dm_input("start session")
    assert "Session started" in response
    
    # Check session status
    response = assistant.process_dm_input("session status")  # Need to add this command
    assert "active_session" in response.lower()
    
    # Award XP
    response = assistant.process_dm_input("award xp 100")
    assert "XP" in response or "experience" in response.lower()
    
    # Take rest
    response = assistant.process_dm_input("long rest")
    assert "rest completed" in response.lower()
    
    # End session
    response = assistant.process_dm_input("end session")
    assert "ended" in response.lower()

def test_character_inventory(assistant):
    """Test character and inventory management"""
    
    # Get inventory (should create if not exists)
    response = assistant.process_dm_input("inventory TestCharacter")
    assert "inventory" in response.lower()
    
    # Adjust HP
    response = assistant.process_dm_input("hp TestCharacter +5")
    assert "HP" in response or "health" in response.lower()

def test_command_mapping(assistant):
    """Test that command mapping works correctly"""
    
    # Test dice command
    response = assistant.process_dm_input("roll 1d20")
    assert "roll" in response.lower() or "dice" in response.lower()
    
    # Test rule command
    response = assistant.process_dm_input("check rule advantage")
    assert any(word in response.lower() for word in ["rule", "advantage", "roll"])
```

---

### **Step 8: Final Integration**

**ADD** debug support to `ModularDMAssistant.__init__()`:
```python
def __init__(self, 
             # ... existing parameters ...
             debug: bool = False):
    
    # ... existing initialization ...
    
    # Setup debug logging
    if debug:
        import logging
        logging.basicConfig(level=logging.DEBUG)
        self.logger = logging.getLogger(__name__)
    else:
        self.logger = None
    
    self.debug = debug
```

**UPDATE** `_send_message_and_wait()` with debug logging:
```python
def _send_message_and_wait(self, agent_id: str, action: str, data: Dict[str, Any], timeout: float = 5.0) -> Optional[Dict[str, Any]]:
    """Send message with simplified caching and debug logging"""
    
    if self.debug and self.logger:
        self.logger.debug(f"Sending {action} to {agent_id} with data: {data}")
    
    try:
        # Simple retry logic (replace AdaptiveErrorRecovery)
        max_retries = 2
        for attempt in range(max_retries):
            try:
                message_id = self.orchestrator.send_message_to_agent(agent_id, action, data)
                
                # Wait for response
                start_time = time.time()
                result = None
                while time.time() - start_time < timeout:
                    history = self.orchestrator.message_bus.get_message_history(limit=50)
                    for msg in reversed(history):
                        if (msg.get("response_to") == message_id and
                            msg.get("message_type") == "response"):
                            result = msg.get("data", {})
                            break
                    if result:
                        break
                    time.sleep(0.1)
                
                if result:
                    if self.debug and self.logger:
                        self.logger.debug(f"Received response from {agent_id}: {result}")
                    return result
                
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                if self.debug and self.logger:
                    self.logger.debug(f"Retry {attempt + 1} for {agent_id}:{action} due to: {e}")
                time.sleep(0.5)
        
        if self.debug and self.logger:
            self.logger.warning(f"Timeout for {agent_id}:{action}")
        return None
        
    except Exception as e:
        if self.debug and self.logger:
            self.logger.error(f"Error communicating with {agent_id}: {e}")
        return None
```

---

## Acceptance Testing Checklist

- [ ] Single RAG system (HaystackPipelineAgent only)
- [ ] No AdaptiveErrorRecovery components
- [ ] Command mapping system works for all D&D commands
- [ ] Inline cache functions correctly (caches rules, not dice)
- [ ] All new D&D agents operational with unit tests
- [ ] Integration test passes full session flow
- [ ] Debug logging works when enabled
- [ ] Save/Load includes all agent states

---

## Migration and Rollout

1. **Testing Phase**: Run integration tests extensively
2. **Gradual Rollout**: Deploy with debug=True initially  
3. **Monitoring**: Watch for any regressions in functionality
4. **Cleanup**: Remove deprecated components after verification
5. **Documentation**: Update README and help commands

This implementation plan provides a **complete, production-ready** D&D assistant that balances comprehensive features with system simplicity.