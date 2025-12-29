# RAG-Scenario Separation Implementation Plan (Corrected)

## Overview

After reviewing the actual refactored architecture (`modular_dm_assistant_refactored.py` and `agent_framework.py`), this corrected plan addresses the **actual current state** rather than assumptions. The agent separation (Phases 1 & 2 from original plan) has **not yet been implemented** - agents still have direct coupling. However, the new pluggable command handler architecture allows us to fix the immediate routing issue in Phase 3.

## Current Architecture Analysis (Actual State)

### 1. What's New in Refactored Architecture
- **Pluggable Command Handlers**: `BaseCommandHandler` interface with `ManualCommandHandler` 
- **Extracted Helper Classes**: `SimpleInlineCache`, `GameSaveManager`, `NarrativeContinuityTracker`
- **Simplified Main Class**: `ModularDMAssistant` delegates to command handler
- **Agent References**: Obtained from orchestrator (lines 81-93)

### 2. What Still Needs Separation (Not Yet Done)
**In `agent_framework.py` lines 344-347:**
```python
# 8. Initialize Scenario Generator Agent - STILL HAS DIRECT COUPLING
self.scenario_agent = ScenarioGeneratorAgent(
    haystack_agent=self.haystack_agent,  # <- Direct coupling still exists
    verbose=verbose
)
```

**This means:**
- Phase 1 (HaystackPipelineAgent simplification) - **NOT DONE**
- Phase 2 (ScenarioGeneratorAgent orchestrator integration) - **NOT DONE**  
- Phase 3 (Command routing) - **NEEDS IMMEDIATE FIX**

### 3. Immediate Issue: Wrong Command Routing
**In `input_parser/manual_command_handler.py` lines 69-75:**
```python
# Scenario generation - STILL INCORRECTLY ROUTED
'introduce scenario': ('haystack_pipeline', 'query_scenario'),
'generate scenario': ('haystack_pipeline', 'query_scenario'),
'create scenario': ('haystack_pipeline', 'query_scenario'),
'new scene': ('haystack_pipeline', 'query_scenario'),
'encounter': ('haystack_pipeline', 'query_scenario'),
'adventure': ('haystack_pipeline', 'query_scenario'),
```

## Corrected Implementation Strategy

### Phase 3: Fix Command Routing (Immediate Fix)

Since the agents still have direct coupling, we need to work with the current architecture while fixing the routing.

#### 3.1 Update ManualCommandHandler Command Map
**File:** `input_parser/manual_command_handler.py`

**Update lines 69-75:**
```python
# Scenario generation - Update to route to scenario_generator
'introduce scenario': ('scenario_generator', 'generate_scenario'),
'generate scenario': ('scenario_generator', 'generate_scenario'),
'create scenario': ('scenario_generator', 'generate_scenario'),
'new scene': ('scenario_generator', 'generate_scenario'),
'encounter': ('scenario_generator', 'generate_scenario'),
'adventure': ('scenario_generator', 'generate_scenario'),
```

**Note**: Using `generate_scenario` action since that's what the current ScenarioGeneratorAgent likely supports (we need to check the actual agent handlers).

#### 3.2 Update Command Routing Logic  
**Update `_route_command()` method around line 270:**
```python
elif agent_id == 'scenario_generator':
    if action == 'generate_scenario':
        return self._handle_scenario_generation(instruction)
    elif action == 'apply_player_choice':
        return self._handle_scenario_command(action, params)
    else:
        return f"❌ Unknown scenario action: {action}"
```

#### 3.3 Update Scenario Handler Method
**Replace `_handle_scenario_generation()` method around line 431:**
```python
def _handle_scenario_generation(self, instruction: str) -> str:
    """Handle scenario generation using ScenarioGeneratorAgent."""
    try:
        # Since agents still have direct coupling, we work with current architecture
        response = self._send_message_and_wait("scenario_generator", "generate_scenario", {
            "query": instruction,
            "use_rag": True  # Let ScenarioGeneratorAgent handle RAG integration internally
        }, timeout=25.0)
        
        if response and response.get("success"):
            # Check if response has the expected structure
            scenario_text = response.get("scenario", "") or response.get("result", {}).get("answer", "")
            
            # Extract and store options for later selection
            self._extract_and_store_options(scenario_text)
            
            # Format response
            output = f"🎭 SCENARIO:\n{scenario_text}\n\n"
            output += "📝 *Type 'select option [number]' to continue the story.*"
            
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

### Phase 4: Verify Current Agent Handlers

Before implementing, we need to check what handlers the current agents actually have.

#### 4.1 Check ScenarioGeneratorAgent Handlers
We need to verify what message handlers `ScenarioGeneratorAgent` actually implements:

```bash
# Check the scenario generator agent implementation
grep -n "register_handler\|def _handle" agents/scenario_generator.py
```

**Expected handlers might be:**
- `generate_scenario` 
- `apply_player_choice`
- `get_generator_status`

#### 4.2 Check HaystackPipelineAgent Handlers  
Verify current handlers:

```bash
# Check haystack agent handlers
grep -n "register_handler\|def _handle" agents/haystack_pipeline_agent.py
```

### Phase 5: Testing Strategy (Focused)

#### 5.1 Simple Routing Test
**Test File:** `tests/test_command_routing_fix.py`

```python
import pytest
from unittest.mock import Mock
from input_parser.manual_command_handler import ManualCommandHandler

class TestCommandRoutingFix:
    """Test the command routing fix for scenario generation."""
    
    def setup_method(self):
        self.mock_assistant = Mock()
        self.mock_assistant.verbose = True
        self.mock_assistant.enable_caching = False
        self.mock_assistant.orchestrator = Mock()
        self.handler = ManualCommandHandler(self.mock_assistant)
    
    def test_scenario_commands_route_to_generator(self):
        """Test that scenario commands now route to scenario_generator."""
        scenario_commands = [
            "generate scenario",
            "create scenario", 
            "new scene",
            "encounter",
            "adventure"
        ]
        
        for command in scenario_commands:
            agent_id, action, params = self.handler._parse_command(command)
            assert agent_id == "scenario_generator", f"'{command}' should route to scenario_generator, got {agent_id}"
            assert action == "generate_scenario", f"'{command}' should use generate_scenario action, got {action}"
    
    def test_rag_queries_still_route_correctly(self):
        """Test that RAG queries still work correctly."""
        rag_query = "What are the rules for concentration checks?"
        agent_id, action, params = self.handler._parse_command(rag_query)
        
        # Should go to general query handling (which uses haystack for RAG)
        assert agent_id is None  # General query fallback
```

#### 5.2 Integration Test
```python
def test_scenario_generation_flow():
    """Test actual scenario generation through new routing."""
    assistant = ModularDMAssistant(verbose=True)
    assistant.start()
    
    try:
        # Test scenario generation
        response = assistant.process_dm_input("generate scenario")
        
        # Should not contain haystack-specific errors
        assert "Pipeline not available" not in response
        assert "query_scenario" not in response
        
        # Should contain scenario content or proper error
        assert ("🎭 SCENARIO:" in response or 
                "❌ Failed to generate scenario:" in response or
                "🎭 SCENARIO (Fallback):" in response)
                
    finally:
        assistant.stop()
```

### Migration Steps (Corrected)

#### Step 1: Verify Current Agent Handlers
```bash
# Check what handlers agents actually have
grep -n "register_handler" agents/scenario_generator.py agents/haystack_pipeline_agent.py

# Check agent IDs used in orchestrator
grep -n "agent_id" agents/scenario_generator.py agents/haystack_pipeline_agent.py
```

#### Step 2: Update Command Routing Only
```bash
# Backup current command handler
cp input_parser/manual_command_handler.py input_parser/manual_command_handler.py.backup

# Apply minimal routing fix
# - Update command_map lines 69-75
# - Update _route_command() method
# - Update _handle_scenario_generation() method
```

#### Step 3: Test Minimal Fix
```bash
# Run routing tests
python -m pytest tests/test_command_routing_fix.py -v

# Test interactive mode
python modular_dm_assistant_refactored.py
# Try: "generate scenario"
# Should not see haystack pipeline errors
```

#### Step 4: Verify Agent Communication
```bash
# Check message bus for proper routing
# In verbose mode, should see messages going to scenario_generator, not haystack_pipeline for scenarios
```

## Remaining Work (Future Phases)

The original Phases 1 & 2 still need to be implemented:

### Future Phase 1: Remove Direct Agent Coupling
- Update `agent_framework.py` line 344-347 to remove direct `haystack_agent` parameter
- Update `ScenarioGeneratorAgent` to use orchestrator communication instead of direct agent references

### Future Phase 2: Implement Pure Agent Separation
- Remove scenario-specific handlers from `HaystackPipelineAgent`
- Implement `retrieve_documents` handler for RAG-only functionality
- Update `ScenarioGeneratorAgent` to query RAG via message bus

## Key Differences from Previous Plan

1. **Agent Coupling Still Exists**: The refactored architecture kept the direct agent coupling
2. **Simpler Fix Required**: Only command routing needs immediate fixing
3. **Working with Current State**: We work with existing agent interfaces rather than assuming changes
4. **Focused Testing**: Test only the routing changes, not architectural changes that haven't been made
5. **Helper Classes**: Plan accounts for extracted helper classes (`SimpleInlineCache`, `GameSaveManager`, etc.)

## Expected Immediate Outcome

After this fix:
- ✅ Scenario commands route to `scenario_generator` instead of `haystack_pipeline`
- ✅ No more "query_scenario handler not found" errors
- ✅ Scenario generation works through proper agent
- ⚠️ Agents still have direct coupling (to be addressed in future phases)
- ✅ RAG queries continue to work through `haystack_pipeline`

This provides a working system while maintaining the goal of eventual clean separation.