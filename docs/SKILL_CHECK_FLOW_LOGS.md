# Skill Check Flow - Expected Log Trace

This document shows the complete log trace you should see when a skill check is auto-triggered through dnd_engine and passed to the scenario generator.

## Implementation Status: ✅ COMPLETE

All logging and data flow has been implemented:
- ✅ Skill check execution in `haystack_dnd_game.py`
- ✅ Result passed through DTO to scenario generator
- ✅ Scenario generator uses result to create appropriate outcomes
- ✅ Comprehensive logging at each step

---

## Expected Log Flow

When you select a choice with a skill check (e.g., "3. Rally the Townsfolk **Skill Check (DC 12)**"), you should see this sequence in the logs:

### 1. Input Processing (haystack_dnd_game.py)

```
INFO - 🎲 Skill check detected: persuasion DC 12
INFO - ✅ Executing skill check via GameEngine
```

**Location**: `haystack_dnd_game.py:264-268` in `_check_for_skill_check()`

**Triggered by**: Player selecting a numbered choice that has `skill_hints` and `suggested_dc`

---

### 2. GameEngine Processing (components/game_engine.py)

```
INFO - 🎲 GAME_ENGINE: Step 4 - Using dnd_engine_wrapper for skill check
INFO -    Actor: Aggi
INFO -    Skill: persuasion
INFO -    DC: 12
```

**Location**: `components/game_engine.py:235-238` in `process_skill_check()`

**Triggered by**: `_check_for_skill_check()` calling `GameEngine.process_skill_check()`

---

### 3. DnD Engine Wrapper Execution (components/dnd_engine_wrapper.py)

```
INFO - 🎲 ==> DND_ENGINE_WRAPPER: execute_skill_check() called
INFO -     Character: Aggi
INFO -     Skill: persuasion
INFO -     DC: 12
INFO -     Advantage: False, Disadvantage: False
INFO - ✅ DND_ENGINE_WRAPPER: Entity found, executing dnd_engine skill check
INFO -    Skill bonus value: 5
INFO -    Rolling d20 with skill bonus...
INFO -    Roll result: <RollResult object>
INFO - 🎯 DND_ENGINE_WRAPPER: Skill check complete!
INFO -    Character: Aggi
INFO -    Skill: persuasion
INFO -    Total Roll: 17
INFO -    DC: 12
INFO -    Result: ✅ SUCCESS
```

**Location**: `components/dnd_engine_wrapper.py:243-294` in `execute_skill_check()`

**Triggered by**: `GameEngine.process_skill_check()` calling `wrapper.execute_skill_check()`

---

### 4. Result Returned to GameEngine

```
INFO - ✅ GAME_ENGINE: dnd_engine_wrapper returned result
INFO -    Roll: 17
INFO -    Success: True
```

**Location**: `components/game_engine.py:248-250`

---

### 5. Result Passed to Scenario Generator (haystack_dnd_game.py)

```
INFO - 🎯 Skill check result: {'success': True, 'roll_total': 17, 'dc': 12, ...}
INFO - 🎲 Passing skill check result to scenario generator: True
```

**Location**: `haystack_dnd_game.py:320` in `_check_for_skill_check()` and `haystack_dnd_game.py:410` in `play_turn()`

---

### 6. Scenario Generator Receives Result (agents/scenario_generator_agent.py)

```
DEBUG - 🐛 SCENARIO [18:45:23] TOOL: 🔧 Accessing engines directly
       📊 Data: {'game_engine_available': True, 'policy_engine_available': True,
                 'skill_check_result_available': True, 'state_duplication_eliminated': True}
DEBUG - 🐛 SCENARIO [18:45:23] TOOL: 🎲 Adding skill check result to prompt: True
```

**Location**: `agents/scenario_generator_agent.py:76-186`

**Triggered by**: Scenario generator building prompt with skill check result

---

## Complete Log Example

Here's what a full skill check trace looks like in the log file:

```
2025-12-31 18:45:23 - __main__ - INFO - 🎲 Skill check detected: persuasion DC 12
2025-12-31 18:45:23 - __main__ - INFO - ✅ Executing skill check via GameEngine
2025-12-31 18:45:23 - components.game_engine - INFO - 🎲 GAME_ENGINE: Step 4 - Using dnd_engine_wrapper for skill check
2025-12-31 18:45:23 - components.game_engine - INFO -    Actor: Aggi
2025-12-31 18:45:23 - components.game_engine - INFO -    Skill: persuasion
2025-12-31 18:45:23 - components.game_engine - INFO -    DC: 12
2025-12-31 18:45:23 - components.dnd_engine_wrapper - INFO - 🎲 ==> DND_ENGINE_WRAPPER: execute_skill_check() called
2025-12-31 18:45:23 - components.dnd_engine_wrapper - INFO -     Character: Aggi
2025-12-31 18:45:23 - components.dnd_engine_wrapper - INFO -     Skill: persuasion
2025-12-31 18:45:23 - components.dnd_engine_wrapper - INFO -     DC: 12
2025-12-31 18:45:23 - components.dnd_engine_wrapper - INFO -     Advantage: False, Disadvantage: False
2025-12-31 18:45:23 - components.dnd_engine_wrapper - INFO - ✅ DND_ENGINE_WRAPPER: Entity found, executing dnd_engine skill check
2025-12-31 18:45:23 - components.dnd_engine_wrapper - INFO -    Skill bonus value: 5
2025-12-31 18:45:23 - components.dnd_engine_wrapper - INFO -    Rolling d20 with skill bonus...
2025-12-31 18:45:23 - components.dnd_engine_wrapper - INFO -    Roll result: RollResult(total=17, natural=12, modifier=5)
2025-12-31 18:45:23 - components.dnd_engine_wrapper - INFO - 🎯 DND_ENGINE_WRAPPER: Skill check complete!
2025-12-31 18:45:23 - components.dnd_engine_wrapper - INFO -    Character: Aggi
2025-12-31 18:45:23 - components.dnd_engine_wrapper - INFO -    Skill: persuasion
2025-12-31 18:45:23 - components.dnd_engine_wrapper - INFO -    Total Roll: 17
2025-12-31 18:45:23 - components.dnd_engine_wrapper - INFO -    DC: 12
2025-12-31 18:45:23 - components.dnd_engine_wrapper - INFO -    Result: ✅ SUCCESS
2025-12-31 18:45:23 - components.game_engine - INFO - ✅ GAME_ENGINE: dnd_engine_wrapper returned result
2025-12-31 18:45:23 - components.game_engine - INFO -    Roll: 17
2025-12-31 18:45:23 - components.game_engine - INFO -    Success: True
2025-12-31 18:45:23 - __main__ - INFO - 🎯 Skill check result: {'success': True, 'roll_total': 17, 'dc': 12, 'selected_roll': 12, 'roll_breakdown': {}}
2025-12-31 18:45:23 - __main__ - INFO - 🎲 Passing skill check result to scenario generator: True
2025-12-31 18:45:23 - agents.scenario_generator_agent - DEBUG - 🐛 SCENARIO [18:45:23] TOOL: 🔧 Accessing engines directly
2025-12-31 18:45:23 - agents.scenario_generator_agent - DEBUG -     📊 Data: {'game_engine_available': True, 'policy_engine_available': True, 'skill_check_result_available': True, 'state_duplication_eliminated': True}
2025-12-31 18:45:23 - agents.scenario_generator_agent - DEBUG - 🐛 SCENARIO [18:45:23] TOOL: 🎲 Adding skill check result to prompt: True
```

---

## What You'll See in the Game UI

After the skill check executes, the player sees a scenario that **reflects the result**:

### Example: SUCCESS (rolled 17 vs DC 12)

```
🎭 DM:
Your impassioned words echo across the Shattered Plains, cutting through the fear and despair.
The townsfolk, who moments ago stood frozen in terror, now rally to your call. Weapons are
gripped with renewed determination, and you see hope returning to their eyes. The defenders
straighten their backs and reform their lines with newfound courage.

"For our homes! For our families!" they shout, emboldened by your leadership.

📋 Choose your action:
  1. Lead the Charge - With morale high, press the advantage
  2. Coordinate Defenses - Organize the newly inspired defenders
  3. Tend to the Wounded - Help the injured while spirits are high
  4. Scout Enemy Positions - Use this moment to gather intelligence
```

### Example: FAILURE (rolled 8 vs DC 12)

```
🎭 DM:
Your words ring out across the Shattered Plains, but they fall on deaf ears. The townsfolk,
paralyzed by fear, barely acknowledge your presence. Some turn away, while others slump
further in despair. The breach in the barricade widens as the Voidbringers press their
advantage, sensing the defenders' wavering resolve.

Your attempt to rally them has failed - now the situation grows more desperate.

📋 Choose your action:
  1. Try Again - Make another desperate attempt to inspire them
  2. Defend the Breach Yourself - Lead by example through action
  3. Organize a Retreat - Get civilians to safety
  4. Call for Help - Signal for reinforcements
```

**Key Point**: The scenario generator creates **different outcomes** based on success/failure!

---

## Troubleshooting

### If you DON'T see these logs:

1. **Check if dnd_engine_wrapper is initialized**
   - Look for: `INFO - 🎲 DnD Engine Wrapper: ✅ Created with 1 entities`
   - If missing, wrapper initialization failed

2. **Check if choice has skill check metadata**
   - Choice must have both `skill_hints` and `suggested_dc` fields
   - Look for: `DEBUG - Choice data: {...}`

3. **Check for errors in wrapper**
   - Look for: `ERROR - ❌ DND_ENGINE_WRAPPER: ...`
   - Common issue: Character ID mismatch

### If skill check is not triggered:

Look for this log:
```
INFO - 🎲 Skill check detected: <skill> DC <dc>
```

**If NOT present**: Choice doesn't have skill check metadata, or `_process_input()` is not detecting it.

**If present but no wrapper logs**: `_check_for_skill_check()` is failing before calling GameEngine.

---

## Log File Location

All logs are written to:
```
logs/dnd_game_YYYYMMDD_HHMMSS.log
```

To view in real-time:
```bash
tail -f logs/dnd_game_*.log
```

To grep for skill check traces:
```bash
grep -E "skill check|GAME_ENGINE|DND_ENGINE_WRAPPER" logs/dnd_game_*.log
```

---

## Verification Checklist

When testing skill checks, verify you see ALL of these in the logs:

- [ ] `🎲 Skill check detected: <skill> DC <dc>`
- [ ] `✅ Executing skill check via GameEngine`
- [ ] `🎲 GAME_ENGINE: Step 4 - Using dnd_engine_wrapper`
- [ ] `🎲 ==> DND_ENGINE_WRAPPER: execute_skill_check() called`
- [ ] `✅ DND_ENGINE_WRAPPER: Entity found, executing dnd_engine skill check`
- [ ] `Rolling d20 with skill bonus...`
- [ ] `🎯 DND_ENGINE_WRAPPER: Skill check complete!`
- [ ] `✅ GAME_ENGINE: dnd_engine_wrapper returned result`
- [ ] `🎯 Skill check result: {...}`
- [ ] `🎲 Passing skill check result to scenario generator: <True/False>`
- [ ] `🐛 SCENARIO: skill_check_result_available: True`
- [ ] `🐛 SCENARIO: 🎲 Adding skill check result to prompt`

If ALL are present: ✅ **Skill check integration is working correctly!**

---

## Complete Data Flow Diagram

```
Player selects choice #3 → "Rally the Townsfolk **Skill Check (DC 12)**"
         │
         ↓
[haystack_dnd_game.py:342] _process_input()
         │
         ├─ Detects: skill_hints=["persuasion"], suggested_dc=12
         ↓
[haystack_dnd_game.py:299] _check_for_skill_check()
         │
         ├─ LOG: 🎲 Skill check detected: persuasion DC 12
         ├─ LOG: ✅ Executing skill check via GameEngine
         ↓
[components/game_engine.py:235] process_skill_check()
         │
         ├─ LOG: 🎲 GAME_ENGINE: Step 4 - Using dnd_engine_wrapper
         ↓
[components/dnd_engine_wrapper.py:243] execute_skill_check()
         │
         ├─ LOG: 🎲 ==> DND_ENGINE_WRAPPER: execute_skill_check() called
         ├─ LOG: ✅ DND_ENGINE_WRAPPER: Entity found
         ├─ LOG: Rolling d20 with skill bonus...
         ├─ **ACTUAL D&D 5E MECHANICS EXECUTED HERE**
         ├─ LOG: 🎯 DND_ENGINE_WRAPPER: Skill check complete!
         ├─ LOG:    Result: ✅ SUCCESS (17 vs DC 12)
         ↓
[components/game_engine.py:248] Receive result
         │
         ├─ LOG: ✅ GAME_ENGINE: dnd_engine_wrapper returned result
         ↓
[haystack_dnd_game.py:320] Return to _check_for_skill_check()
         │
         ├─ LOG: 🎯 Skill check result: {'success': True, ...}
         ↓
[haystack_dnd_game.py:351] Add to processed_input
         │
         └─ processed_input["skill_check_result"] = {...}
         ↓
[haystack_dnd_game.py:409] play_turn() adds to DTO
         │
         ├─ request_dto["skill_check_result"] = skill_check_result
         ├─ LOG: 🎲 Passing skill check result to scenario generator: True
         ↓
[orchestrator/pipeline_integration.py] Route to scenario_pipeline
         ↓
[agents/scenario_generator_agent.py:74] create_scenario_from_dto()
         │
         ├─ skill_check_result = dto.get("skill_check_result")
         ├─ LOG: 🔧 Accessing engines directly
         ├─ LOG:    skill_check_result_available: True
         ├─ LOG: 🎲 Adding skill check result to prompt: True
         ↓
[agents/scenario_generator_agent.py:176] Build prompt with result
         │
         ├─ Add section: "=== SKILL CHECK RESULT (CRITICAL) ==="
         ├─ Prompt includes: "Result: SUCCESS, Roll: 17 vs DC 12"
         ├─ Prompt instructs: "Scene MUST show consequences of success"
         ↓
[LLM: gemini-2.0-flash] Generate scenario
         │
         ├─ Reads skill check result
         ├─ Creates outcome based on SUCCESS
         ├─ Generates appropriate narrative
         ↓
[Response] Scenario with success outcome returned
         │
         ↓
[Player sees] DM narrative showing successful rally + new choices
```

---

## Next Steps

Once you verify the logs show the complete flow:

1. **Test different skills**: Try Athletics, Stealth, Perception, etc.
2. **Test with advantage/disadvantage**: Verify the logs show the correct state
3. **Test success and failure**: Verify both outcomes work correctly
4. **Test DC scaling**: Verify PolicyEngine adjustments are applied

After verification, you're ready to proceed with **Phase 3: Combat System Integration** from the [DND_ENGINE_INTEGRATION_GUIDE.md](DND_ENGINE_INTEGRATION_GUIDE.md#phase-3-combat-system-week-2-days-1-3).
