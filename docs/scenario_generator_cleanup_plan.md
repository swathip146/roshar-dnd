# ScenarioGeneratorAgent Cleanup Implementation Plan

## Overview
This plan removes the backward compatibility `ScenarioGenerator` class and ensures the `ScenarioGeneratorAgent` is fully compatible with orchestrator communication without any direct agent coupling.

## Current State Analysis

### ✅ Already Correct
1. **ScenarioGeneratorAgent** (lines 30-520) is properly implemented with:
   - `__init__(self, verbose: bool = False)` - no haystack_agent parameter
   - Uses `self.send_message()` calls to `haystack_pipeline` agent
   - Proper message handlers for orchestrator communication
   - All RAG queries go through message bus: `self.send_message("haystack_pipeline", "retrieve_documents", ...)`

2. **agent_framework.py** (lines 342-346) correctly initializes:
   ```python
   self.scenario_agent = ScenarioGeneratorAgent(
       verbose=verbose
   )
   ```

3. **All agent communication** already uses orchestrator messaging instead of direct references

### ❌ Needs Cleanup
1. **Backward compatibility class** `ScenarioGenerator` (lines 522-649) needs complete removal
2. **modular_dm_assistant_refactored.py** needs verification for any old references

## Implementation Tasks

### Task 1: Remove Backward Compatibility Class
**File:** `agents/scenario_generator.py`
**Action:** Delete lines 522-649 (entire `ScenarioGenerator` class)

**Lines to Remove:**
```python
class ScenarioGenerator:
    """Traditional ScenarioGenerator class for backward compatibility - orchestrator communication"""
    
    def __init__(self, haystack_agent=None, verbose: bool = False):
        # ... entire class implementation ...
```

### Task 2: Check modular_dm_assistant_refactored.py
**File:** `modular_dm_assistant_refactored.py`
**Action:** Verify no references to old `ScenarioGenerator` class

**Expected:** Should only use `ScenarioGeneratorAgent` via orchestrator

### Task 3: Verify Clean Implementation
**File:** `agents/scenario_generator.py`
**Expected Result:** File should contain:
- Import statements (lines 1-28)
- `ScenarioGeneratorAgent` class only (lines 30-520)
- No backward compatibility code

## Key Benefits
1. **Removes complexity** - eliminates dual code paths
2. **Pure orchestrator communication** - all agent interactions via message bus
3. **Cleaner architecture** - single responsibility per class
4. **Better maintainability** - no legacy compatibility code

## Files to Modify
1. `agents/scenario_generator.py` - Remove ScenarioGenerator class
2. `modular_dm_assistant_refactored.py` - Verify/update any old references

## Validation
After changes, verify:
1. No import errors
2. ScenarioGeneratorAgent works via orchestrator
3. All RAG queries use message bus
4. No direct agent coupling remains