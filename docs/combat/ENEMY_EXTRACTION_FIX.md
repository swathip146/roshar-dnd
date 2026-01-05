# Enemy Extraction Fix - Full Scenario Context

**Date:** 2026-01-04
**Status:** Implemented - Full scenario context now stored in GameEngine and passed to combat

## Problem

The LLM was returning empty arrays `[]` when trying to extract enemies from combat scenarios because it only received minimal context:
- Just `scenario['scene']` and `scenario['gm_notes']`
- Missing the full DM narrative that the player responded to
- Missing the player's actual choice that triggered combat

### Example of Missing Context

**What DM showed:**
```
The wind howls across the Shattered Plains, carrying grit and the metallic tang of
distant storms. Before you lies a ravaged caravan... To the west, you see dark shapes
moving against the bruised sky – Voidbringers, their forms twisted and unnatural...

Choose your action:
1. Assess the Survivors **Skill Check (DC 13)**
2. Scout the Voidbringer Force **Skill Check (DC 14)**
3. Prepare for Ambush
4. Engage the Voidbringers **Combat**

Player> 4
```

**What LLM received for enemy extraction:**
```
Scene: Combat initiated: 4
GM Notes: Player wants to 4. Target: enemy
```

**Result:** LLM couldn't extract "Voidbringers" from this minimal context.

---

## Solution: Store Full Context in GameEngine (Authoritative Source)

Following the clean architecture pattern, we made GameEngine the authoritative source for:
1. **Full scenario text** (untruncated scene, choices, gm_notes)
2. **Player's last action** (what they chose that led to current state)

### Changes Made

#### 1. Extended GameEngine State Schema

**File:** `components/game_engine.py`

Added new fields to `NarrativeContext`:
```python
class NarrativeContext(TypedDict, total=False):
    current_scene: str  # Truncated for logs
    current_scene_full: str  # NEW: Full untruncated scene text
    last_scenario: Dict[str, Any]  # NEW: Complete last scenario with scene, choices, gm_notes
    last_player_action: str  # NEW: Last player input/choice
    # ... existing fields ...
```

#### 2. Updated GameEngine to Store Full Scenario

**File:** `components/game_engine.py` - `process_scenario_state_updates()`

```python
def process_scenario_state_updates(self, scenario_data: Dict[str, Any], turn_number: int):
    """Process scenario data and update authoritative game state"""

    scene_text = scenario_data.get("scene", "")
    narrative_updates = {
        "current_scene": scene_text[:100] + "..." if len(scene_text) > 100 else scene_text,
        "current_scene_full": scene_text,  # NEW: Full text
        "last_scenario": {  # NEW: Complete scenario
            "scene": scene_text,
            "choices": scenario_data.get("choices", []),
            "gm_notes": scenario_data.get("gm_notes", ""),
            "scenario_type": scenario_data.get("scenario_type", "unknown"),
            "confidence": scenario_data.get("confidence", 0)
        },
        "last_scenario_type": scenario_data.get("scenario_type", "unknown"),
        "scenario_confidence": scenario_data.get("confidence", 0),
        "turn_number": turn_number
    }
    self.update_narrative_context(narrative_updates)
```

#### 3. Store Player Actions in GameEngine

**File:** `haystack_dnd_game.py` - `_update_state_via_authorities()`

```python
def _update_state_via_authorities(self, processed_input: Dict[str, Any], response_data: Dict[str, Any]):
    """Update state via authoritative components following hierarchy"""

    if response_type == "scenario":
        scenario = response_data.get("scenario", {})
        self.game_engine.process_scenario_state_updates(scenario, self.turn_counter)

        # NEW: Store player's action in GameEngine (authoritative state)
        player_action = processed_input.get("processed_input", "")
        self.game_engine.update_narrative_context({
            "last_player_action": player_action
        })
```

#### 4. Combat Agent Retrieves Full Context from GameEngine

**File:** `agents/combat_agent.py` - `run()`

```python
# COMPLIANCE: Get full scenario context from GameEngine (authoritative source)
if not scenario and self.game_engine:
    narrative_ctx = self.game_engine.get_narrative_context()

    # Get complete last scenario with all choices
    last_scenario = narrative_ctx.get("last_scenario", {})
    last_player_action = narrative_ctx.get("last_player_action", player_input)

    if last_scenario:
        scenario = {
            "scene": last_scenario.get("scene", ""),
            "gm_notes": last_scenario.get("gm_notes", ""),
            "choices": last_scenario.get("choices", []),
            "player_choice": last_player_action,
            "full_context": {
                "previous_scenario": last_scenario.get("scene", ""),
                "player_choice": last_player_action
            }
        }
```

**Logging output:**
```
📋 Combat Agent Input:
   Player input: '4'
   📖 Retrieving full scenario from GameEngine (authoritative source)...
   ✅ Retrieved full scenario from GameEngine:
      Scene length: 623 chars
      Choices: 4 options
      Player chose: 'Engage the Voidbringers Combat'
```

#### 5. Enemy Extraction Uses Full Context

**File:** `components/combat/combat_initializer.py` - `_parse_enemies_from_scenario()`

Now builds comprehensive prompt with:
- Full DM scenario narrative
- All choice options player saw
- Specific choice player made

```python
scene_text = scenario.get('scene', '')
gm_notes = scenario.get('gm_notes', '')
player_choice = scenario.get('player_choice', '')

# Get all choice options to provide full context
choices = scenario.get('choices', [])
choices_text = ""
if choices:
    choices_text = "\n\nAvailable choices player saw:\n"
    for i, choice in enumerate(choices, 1):
        title = choice.get('title', f'Option {i}')
        desc = choice.get('description', '')
        choices_text += f"{i}. {title}"
        if desc:
            choices_text += f" - {desc}"
        choices_text += "\n"

# Build comprehensive context for LLM
combined_text = f"""PREVIOUS DM SCENARIO:
{scene_text}

GM NOTES:
{gm_notes}

{choices_text}

PLAYER CHOSE:
{player_choice}
"""
```

**LLM now receives:**
```
PREVIOUS DM SCENARIO:
The wind howls across the Shattered Plains, carrying grit and the metallic tang of
distant storms. Before you lies a ravaged caravan... To the west, you see dark shapes
moving against the bruised sky – Voidbringers, their forms twisted and unnatural...

Available choices player saw:
1. Assess the Survivors **Skill Check (DC 13)**
2. Scout the Voidbringer Force **Skill Check (DC 14)**
3. Prepare for Ambush
4. Engage the Voidbringers **Combat**

PLAYER CHOSE:
Engage the Voidbringers Combat
```

**Enhanced system prompt:**
```
Rules:
- Extract enemy type, count, and description from the DM's scenario narrative
- Estimate CR based on description (Voidbringer=3-5, etc.)
- Look at ALL the text: scene, GM notes, choices, and what player chose
```

---

## Architecture Compliance

This fix follows the clean architecture pattern:

1. **GameEngine is Authoritative**: Stores all runtime state including full scenarios
2. **No State Duplication**: UI layer (`haystack_dnd_game.py`) no longer keeps its own copy
3. **Single Source of Truth**: Combat system reads from GameEngine, not UI state
4. **Consistent Pattern**: All agents access state via `dto["_game_engine_ref"]`

### Before (WRONG)
```
haystack_dnd_game.py:
  self.current_scenario = scenario  # UI state
  self.current_choices = choices    # UI state

combat_agent.py:
  scenario = dto.get("scenario_context", {})  # Empty or minimal
  # LLM receives insufficient context
```

### After (CORRECT)
```
haystack_dnd_game.py:
  self.game_engine.process_scenario_state_updates(scenario)  # Store in engine
  self.game_engine.update_narrative_context({"last_player_action": player_action})

combat_agent.py:
  narrative_ctx = self.game_engine.get_narrative_context()
  last_scenario = narrative_ctx.get("last_scenario", {})  # Authoritative source
  # LLM receives complete context
```

---

## Files Modified

1. **components/game_engine.py**
   - Extended `NarrativeContext` TypedDict (lines 53-65)
   - Updated `process_scenario_state_updates()` (lines 1133-1170)

2. **haystack_dnd_game.py**
   - Updated `_update_state_via_authorities()` to store player actions (lines 266-289)

3. **agents/combat_agent.py**
   - Added GameEngine retrieval logic for full scenario (lines 94-162)
   - Enhanced logging for scenario context

4. **components/combat/combat_initializer.py**
   - Updated `_parse_enemies_from_scenario()` to use full context (lines 185-290)
   - Enhanced LLM prompt with choices and player action
   - Added comprehensive logging

---

## Expected Results

### Before Fix
```
📋 Calling LLM to extract enemies from scenario...
   Scene text length: 29 chars
   GM notes length: 38 chars
   Combined text length: 67 chars
   LLM response: "[]"
   ⚠️  No enemies found in scenario text!
```

### After Fix
```
📋 Calling LLM to extract enemies from scenario...
   Scene text length: 623 chars
   GM notes length: 89 chars
   Player choice length: 29 chars
   Combined text length: 784 chars
   ✅ Successfully extracted 1 enemy types
      1. Voidbringers x3 (CR 4)
```

---

## Testing

### Manual Test
```bash
# Start game
./run_game.sh

# When presented with combat choice:
# 1. Note the full DM narrative
# 2. Select combat option (e.g., "4")
# 3. Check logs for enemy extraction

# Expected log output:
# ✅ Retrieved full scenario from GameEngine:
#    Scene length: 600+ chars
#    Choices: 4 options
#    Player chose: 'Engage the Voidbringers Combat'
# ✅ Successfully extracted N enemy types
```

### Automated Test
```bash
# Run combat integration tests
PYTHONPATH=. python -m pytest tests/combat/test_combat_pipeline_integration.py -v -s

# Run full test suite
PYTHONPATH=. python -m pytest tests/combat/ -v
```

---

## Success Criteria

- ✅ GameEngine stores full scenario (untruncated scene + all choices)
- ✅ GameEngine stores player's last action
- ✅ Combat agent retrieves full context from GameEngine
- ✅ Enemy extraction LLM receives complete scenario narrative
- ✅ Enemy extraction LLM receives all choice options
- ✅ Enemy extraction LLM receives player's specific choice
- ✅ No state duplication in UI layer
- ⏳ LLM successfully extracts enemies from full context (test with actual game run)

---

## Next Steps

1. Run actual game with combat scenario
2. Verify enemies are extracted correctly
3. Test with various combat scenarios:
   - Multiple enemy types
   - Named NPCs (predefined)
   - Generic enemies (generated)
4. Monitor LLM token usage (longer prompts)
5. Consider caching scenario context if memory becomes an issue

---

## Rollback Plan

If issues occur, revert these commits in order:

1. `components/combat/combat_initializer.py` - Revert enemy extraction changes
2. `agents/combat_agent.py` - Revert GameEngine retrieval logic
3. `haystack_dnd_game.py` - Revert player action storage
4. `components/game_engine.py` - Revert NarrativeContext extension

Note: This is a breaking change for any code that accessed `self.current_scenario` in `haystack_dnd_game.py` directly (should now use `game_engine.get_narrative_context()["last_scenario"]`).

---

## Related Documentation

- **COMBAT_INTEGRATION_FIXES.md** - Initial combat system integration
- **COMBAT_ENGINE_IMPLEMENTATION_PLAN.md** - Overall combat system architecture
- **CURRENT_SYSTEM_ARCHITECTURE.md** - Clean architecture patterns
- **GAME_STATE_ANALYSIS.md** - State management patterns
