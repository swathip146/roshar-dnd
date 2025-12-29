# RAG-Scenario Separation Implementation Plan (Updated)

## Overview

This updated plan reflects the new modular architecture with message-based communication, pluggable command handlers, and event-driven coordination. The separation of RAG functionality from scenario generation now must work within the new `AgentOrchestrator` and `MessageBus` architecture.

## Updated Current Architecture Analysis

### 1. New Communication Architecture
- **Message Bus**: All agent communication via `AgentMessage` objects
- **Agent Orchestrator**: Centralized agent lifecycle and communication management  
- **Async Processing**: Non-blocking message passing with response correlation
- **Event System**: Event-driven updates and notifications

### 2. New Command Processing Architecture
- **Pluggable Handlers**: `BaseCommandHandler` interface with `ManualCommandHandler` implementation
- **Separated Routing**: Command mapping moved from main assistant to command handler
- **Event Integration**: Command handlers can register for and handle system events

### 3. Current Scenario Routing (Still Needs Update)
**In `ManualCommandHandler.command_map` (lines 69-77):**
```python
# Scenario generation - STILL ROUTED TO HAYSTACK PIPELINE
'introduce scenario': ('haystack_pipeline', 'query_scenario'),
'generate scenario': ('haystack_pipeline', 'query_scenario'), 
'create scenario': ('haystack_pipeline', 'query_scenario'),
'new scene': ('haystack_pipeline', 'query_scenario'),
'encounter': ('haystack_pipeline', 'query_scenario'),
'adventure': ('haystack_pipeline', 'query_scenario'),
```

## Updated Implementation Steps

### Phase 3: Command Handler Updates (Revised)

#### 3.1 Update ManualCommandHandler Routing
**File:** `input_parser/manual_command_handler.py`

**Update Command Map (lines 69-77):**
```python
# OLD routing - Routes to haystack_pipeline
'introduce scenario': ('haystack_pipeline', 'query_scenario'),
'generate scenario': ('haystack_pipeline', 'query_scenario'),
'create scenario': ('haystack_pipeline', 'query_scenario'),
'new scene': ('haystack_pipeline', 'query_scenario'),
'encounter': ('haystack_pipeline', 'query_scenario'),
'adventure': ('haystack_pipeline', 'query_scenario'),

# NEW routing - Routes to scenario_generator
'introduce scenario': ('scenario_generator', 'generate_with_context'),
'generate scenario': ('scenario_generator', 'generate_with_context'),
'create scenario': ('scenario_generator', 'generate_with_context'),
'new scene': ('scenario_generator', 'generate_with_context'),
'encounter': ('scenario_generator', 'generate_with_context'),
'adventure': ('scenario_generator', 'generate_with_context'),
```

#### 3.2 Update Scenario Handler Method
**File:** `input_parser/manual_command_handler.py`

**Replace `_handle_scenario_generation()` method (lines 431-448):**
```python
def _handle_scenario_generation(self, instruction: str) -> str:
    """Handle scenario generation using ScenarioGeneratorAgent with RAG integration."""
    try:
        # Get context data for enhanced scenario generation
        campaign_context = self._get_campaign_context()
        game_state = self._get_current_game_state()
        
        # Send to scenario generator with RAG option
        response = self._send_message_and_wait("scenario_generator", "generate_with_context", {
            "query": instruction,
            "use_rag": True,
            "campaign_context": campaign_context,
            "game_state": game_state
        }, timeout=25.0)
        
        if response and response.get("success"):
            scenario = response["scenario"]
            rag_used = response.get("used_rag", False)
            source_count = response.get("source_count", 0)
            
            # Extract and store options for later selection
            self._extract_and_store_options(scenario.get("scenario_text", ""))
            
            # Format response
            output = f"🎭 SCENARIO:\n{scenario.get('scenario_text', '')}\n\n"
            
            if rag_used:
                output += f"📚 *Enhanced with {source_count} D&D references*\n"
            else:
                output += f"🎨 *Creative generation (RAG not used)*\n"
            
            output += "\n📝 *Type 'select option [number]' to continue the story.*"
            
            return output
        else:
            error_msg = response.get('error', 'Unknown error') if response else 'Timeout'
            return f"❌ Failed to generate scenario: {error_msg}"
            
    except Exception as e:
        if self.dm_assistant.verbose:
            print(f"⚠️ Scenario generation error: {e}")
        return self._generate_fallback_scenario(instruction)

def _generate_fallback_scenario(self, user_query: str) -> str:
    """Generate fallback scenario when ScenarioGeneratorAgent fails."""
    fallback_scenario = """The party finds themselves at a crossroads where four paths diverge into the unknown.

**1. Take the North Path** - Follow the well-worn trail toward distant mountains
**2. Take the East Path** - Head through the dense forest where strange sounds echo
**3. Take the West Path** - Follow the river downstream toward civilization
**4. Make Camp Here** - Rest and prepare before choosing a direction"""
    
    # Extract and store the fallback options
    self._extract_and_store_options(fallback_scenario)
    return f"🎭 SCENARIO (Fallback):\n{fallback_scenario}\n\n📝 *Type 'select option [number]' to choose a player option.*"
```

#### 3.3 Add Helper Methods for Context Gathering
**Add to `ManualCommandHandler` class:**
```python
def _get_campaign_context(self) -> str:
    """Get current campaign context for scenario generation."""
    try:
        response = self._send_message_and_wait("campaign_manager", "get_campaign_context", {}, timeout=5.0)
        if response and response.get("success"):
            return json.dumps(response["context"])
        return ""
    except Exception as e:
        if self.dm_assistant.verbose:
            print(f"⚠️ Failed to get campaign context: {e}")
        return ""

def _get_current_game_state(self) -> str:
    """Get current game state for scenario generation."""
    try:
        response = self._send_message_and_wait("game_engine", "get_game_state", {}, timeout=5.0)
        if response and response.get("game_state"):
            return json.dumps(response["game_state"])
        return ""
    except Exception as e:
        if self.dm_assistant.verbose:
            print(f"⚠️ Failed to get game state: {e}")
        return ""
```

#### 3.4 Update Command Routing Logic
**Update `_route_command()` method (lines 270-310):**
```python
def _route_command(self, agent_id: str, action: str, instruction: str, params: dict) -> str:
    """Route command to appropriate agent handler."""
    try:
        # Check if agent is available
        if not self._check_agent_availability(agent_id, action):
            return f"❌ Agent {agent_id} not available or missing handler for {action}"
        
        # Route to appropriate handler based on agent and action
        if agent_id == 'campaign_manager':
            return self._handle_campaign_command(action, params)
        elif agent_id == 'combat_engine':
            return self._handle_combat_command(action, params)
        elif agent_id == 'dice_system':
            return self._handle_dice_roll(instruction)
        elif agent_id == 'rule_enforcement':
            return self._handle_rule_query(instruction)
        elif agent_id == 'game_engine':
            return self._handle_game_engine_command(action, params)
        elif agent_id == 'haystack_pipeline':
            # Only handle pure RAG queries, not scenario generation
            return self._handle_general_query(instruction)
        elif agent_id == 'scenario_generator':
            if action == 'generate_with_context':
                return self._handle_scenario_generation(instruction)
            elif action == 'apply_player_choice':
                return self._handle_scenario_command(action, params)
            else:
                return f"❌ Unknown scenario action: {action}"
        elif agent_id == 'session_manager':
            return self._handle_session_command(action, params)
        elif agent_id == 'inventory_manager':
            return self._handle_inventory_command(action, params)
        elif agent_id == 'spell_manager':
            return self._handle_spell_command(action, params)
        elif agent_id == 'character_manager':
            return self._handle_character_command(action, params)
        elif agent_id == 'experience_manager':
            return self._handle_experience_command(action, params)
        elif agent_id == 'orchestrator':
            return self._get_system_status()
        else:
            return self._handle_general_query(instruction)
            
    except Exception as e:
        if self.dm_assistant.verbose:
            print(f"❌ Error routing command: {e}")
        return f"❌ Error processing command: {str(e)}"
```

### Phase 4: Testing & Integration (Updated)

#### 4.1 Message Bus Testing Strategy
**New Test File:** `tests/test_message_bus_scenario_separation.py`

```python
import asyncio
import pytest
from agent_framework import AgentOrchestrator, MessageType
from input_parser.manual_command_handler import ManualCommandHandler
from modular_dm_assistant_refactored import ModularDMAssistant

class TestMessageBusScenarioSeparation:
    """Test scenario separation in the new message-based architecture."""
    
    def setup_method(self):
        """Setup test environment with message bus."""
        self.assistant = ModularDMAssistant(verbose=True)
        self.assistant.start()
        self.handler = self.assistant.command_handler
    
    def teardown_method(self):
        """Cleanup after test."""
        self.assistant.stop()
    
    def test_scenario_routing_to_generator(self):
        """Test that scenario commands route to scenario_generator agent."""
        # Test that scenario generation routes correctly
        response = self.handler.handle_command("generate scenario")
        
        # Should not contain haystack-specific messaging
        assert "Pipeline not available" not in response
        assert "not connected" not in response
        
        # Should indicate scenario generator usage
        assert "🎭 SCENARIO:" in response or "❌ Failed to generate scenario:" in response
    
    def test_rag_queries_to_haystack(self):
        """Test that pure RAG queries still route to haystack agent."""
        response = self.handler.handle_command("What are the rules for concentration checks?")
        
        # Should use RAG system
        assert "💡" in response or "❌ Failed to process query:" in response
    
    def test_scenario_with_rag_integration(self):
        """Test that scenario generation can integrate RAG data."""
        response = self.handler.handle_command("generate a tavern encounter")
        
        # Should indicate scenario generation
        assert "🎭 SCENARIO:" in response or "🎭 SCENARIO (Fallback):" in response
        
        # Should provide options for selection
        assert "select option" in response.lower()
    
    def test_agent_communication_flow(self):
        """Test message flow between agents for scenario generation."""
        # Generate scenario to trigger agent communication
        response = self.handler.handle_command("create a dungeon scenario")
        
        # Check message bus history for proper routing
        history = self.assistant.orchestrator.message_bus.get_message_history(limit=20)
        
        # Should have messages to scenario_generator, not haystack for scenarios
        scenario_messages = [m for m in history if m.get('receiver_id') == 'scenario_generator']
        haystack_scenario_messages = [m for m in history 
                                    if m.get('receiver_id') == 'haystack_pipeline' 
                                    and m.get('action') == 'query_scenario']
        
        assert len(scenario_messages) > 0, "Should have messages to scenario_generator"
        assert len(haystack_scenario_messages) == 0, "Should not have scenario queries to haystack"
    
    def test_event_system_integration(self):
        """Test that events are properly forwarded in new architecture."""
        # Trigger an action that should generate events
        self.handler.handle_command("start combat")
        
        # Check for events in the system
        self.assistant.orchestrator.check_and_forward_events(verbose=True)
        
        # Should not raise exceptions
        assert True  # If we get here, event system is working
```

#### 4.2 Command Handler Testing
**New Test File:** `tests/test_command_handler_routing.py`

```python
import pytest
from unittest.mock import Mock, patch
from input_parser.manual_command_handler import ManualCommandHandler

class TestCommandHandlerRouting:
    """Test the updated command handler routing logic."""
    
    def setup_method(self):
        """Setup test environment."""
        self.mock_assistant = Mock()
        self.mock_assistant.verbose = True
        self.mock_assistant.enable_caching = False
        self.mock_assistant.orchestrator = Mock()
        
        self.handler = ManualCommandHandler(self.mock_assistant)
    
    def test_scenario_command_parsing(self):
        """Test that scenario commands parse to correct agent."""
        test_commands = [
            "generate scenario",
            "create scenario", 
            "new scene",
            "encounter",
            "adventure"
        ]
        
        for command in test_commands:
            agent_id, action, params = self.handler._parse_command(command)
            assert agent_id == "scenario_generator", f"Command '{command}' should route to scenario_generator"
            assert action == "generate_with_context", f"Command '{command}' should use generate_with_context action"
    
    def test_rag_command_parsing(self):
        """Test that RAG queries parse correctly."""
        rag_commands = [
            "What are the rules for spellcasting?",
            "How does stealth work?",
            "Explain concentration checks"
        ]
        
        for command in rag_commands:
            agent_id, action, params = self.handler._parse_command(command)
            # Should either go to rule_enforcement or be handled as general query
            assert agent_id in [None, "rule_enforcement"], f"RAG command '{command}' routing issue"
    
    def test_option_selection_parsing(self):
        """Test that option selection parses correctly."""
        command = "select option 2"
        agent_id, action, params = self.handler._parse_command(command)
        
        assert agent_id == "scenario_generator"
        assert action == "apply_player_choice"
        assert params.get("option_number") == 2
    
    @patch.object(ManualCommandHandler, '_send_message_and_wait')
    def test_scenario_generation_flow(self, mock_send):
        """Test the complete scenario generation flow."""
        # Mock successful responses
        mock_send.side_effect = [
            {"success": True, "context": {"title": "Test Campaign"}},  # campaign context
            {"game_state": {"location": "tavern", "players": {}}},      # game state
            {
                "success": True, 
                "scenario": {"scenario_text": "You enter a tavern.\n\n1. Approach the bar\n2. Find a table"},
                "used_rag": True,
                "source_count": 2
            }  # scenario generation
        ]
        
        response = self.handler._handle_scenario_generation("generate tavern scenario")
        
        # Should have called scenario_generator with correct parameters
        assert mock_send.call_count == 3
        scenario_call = mock_send.call_args_list[2]
        assert scenario_call[0][0] == "scenario_generator"
        assert scenario_call[0][1] == "generate_with_context" 
        assert scenario_call[0][2]["use_rag"] == True
        
        # Should format response correctly
        assert "🎭 SCENARIO:" in response
        assert "📚 *Enhanced with 2 D&D references*" in response
```

#### 4.3 Integration Test Scenarios
**Updated Test Scenarios:**

1. **Pure RAG Query Flow**: 
   - User: "What are the rules for concentration checks?"
   - Expected: Route to `haystack_pipeline` → `query_rag`
   - Verify: No scenario generation, returns rule information

2. **Scenario Generation with RAG**: 
   - User: "Generate a tavern encounter with bandits"
   - Expected: Route to `scenario_generator` → `generate_with_context`
   - Internal: ScenarioGenerator queries `haystack_pipeline` → `retrieve_documents`
   - Verify: Creative scenario with RAG enhancement noted

3. **Scenario Generation without RAG**: 
   - User: "Create a mystery in a haunted forest" (when RAG unavailable)
   - Expected: Route to `scenario_generator` → `generate_with_context`
   - Fallback: Creative generation without RAG, fallback scenario if needed
   - Verify: Scenario generated with creativity note

4. **Option Selection Flow**:
   - User: "select option 2" 
   - Expected: Route to `scenario_generator` → `apply_player_choice`
   - Verify: Story continuation generated

### Migration Steps (Updated)

#### Step 1: Update Command Handler
```bash
# Backup current implementation
cp input_parser/manual_command_handler.py input_parser/manual_command_handler.py.backup

# Apply routing changes to ManualCommandHandler
# Update command_map, _handle_scenario_generation, _route_command methods
```

#### Step 2: Verify Agent Message Handlers
```bash
# Ensure ScenarioGeneratorAgent has generate_with_context handler
# Ensure HaystackPipelineAgent has retrieve_documents handler
# Check agent initialization in AgentOrchestrator
```

#### Step 3: Test Message Bus Communication
```bash
# Run message bus tests
python -m pytest tests/test_message_bus_scenario_separation.py -v

# Run command handler tests  
python -m pytest tests/test_command_handler_routing.py -v
```

#### Step 4: Integration Testing
```bash
# Test complete flow
python modular_dm_assistant_refactored.py

# Test commands:
# - "generate scenario" (should route to scenario_generator)
# - "What are concentration rules?" (should route to haystack RAG)
# - "select option 1" (should work with scenario_generator)
```

## Key Architectural Benefits of Update

### 1. **Clean Separation**
- **RAG Queries**: `haystack_pipeline` → Pure document retrieval and knowledge
- **Scenario Generation**: `scenario_generator` → Creative content with optional RAG integration
- **Clear Boundaries**: No mixed responsibilities

### 2. **Message-Based Decoupling** 
- **Loose Coupling**: Agents communicate via messages, not direct calls
- **Fault Tolerance**: Failures in one agent don't crash others
- **Scalability**: Easy to add new agents or modify existing ones

### 3. **Event-Driven Coordination**
- **Reactive Updates**: Components can react to system events
- **State Synchronization**: Game state changes trigger appropriate updates
- **Extensibility**: Easy to add new event handlers

### 4. **Pluggable Command Processing**
- **Flexible Parsing**: Can swap out command handlers (manual → AI-based)
- **Testable Logic**: Command routing logic isolated and testable
- **Maintainable**: Clear separation between parsing and execution

## Expected Outcomes

1. **Cleaner Architecture**: Each agent has single, well-defined responsibility
2. **Better Performance**: RAG queries faster without scenario overhead
3. **Enhanced Flexibility**: Scenario generation with optional RAG enhancement  
4. **Improved Testability**: Message-based communication easier to test
5. **Future-Ready**: Architecture supports adding new agents and capabilities

---

This updated implementation plan leverages the new modular, message-based architecture while achieving the original goal of separating RAG functionality from scenario generation.