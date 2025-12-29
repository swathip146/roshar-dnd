# Scenario Generator Option Selection - Issue Analysis & Fix Plan

## Problem Summary

The scenario generation system has multiple critical bugs that prevent correct player option selection and proper scenario continuation. When a user types "select option 2", the system incorrectly processes option 1 instead, and fails to generate new scenario options for continued play.

## Issue Analysis

### Issue #1: Wrong Option Number Selected
**Symptom**: User selects "option 2" but system processes "choice 1"
**Root Cause**: Command parsing conflict in `manual_command_handler.py`

```
Terminal Output: 
DM> select option 2
⚡ ScenarioGenerator: Processing choice 1 for DM  <-- Should be choice 2
```

**Technical Details**:
1. `manual_command_handler.py:84-86` - Command map contains static entries:
   ```python
   'select option': ('scenario_generator', 'apply_player_choice'),
   'choose option': ('scenario_generator', 'apply_player_choice'),
   'option': ('scenario_generator', 'apply_player_choice'),
   ```

2. `manual_command_handler.py:512-515` - Command map matching happens BEFORE regex extraction:
   ```python
   for pattern, (agent, action) in sorted_patterns:
       if pattern in instruction_lower:
           params = self._extract_params(instruction)  # Returns empty {} for 'select option'
   ```

3. `manual_command_handler.py:1029-1031` - Default value used when params empty:
   ```python
   if action == 'apply_player_choice':
       option_number = params.get('option_number', 1)  # Defaults to 1!
   ```

4. `manual_command_handler.py:524-527` - Regex extraction never reached:
   ```python
   elif instruction_lower.startswith('select option'):
       match = re.search(r'select option (\d+)', instruction_lower)
       if match:
           return 'scenario_generator', 'apply_player_choice', {'option_number': int(match.group(1))}
   ```

### Issue #2: Response Handling Warning
**Symptom**: "No response sent for apply_player_choice" warning appears
**Root Cause**: Message bus timing and response detection issues

```
Terminal Output:
🔍 scenario_generator: Handler returned: <class 'NoneType'> for apply_player_choice
⚠️ scenario_generator: No response sent for apply_player_choice
```

**Technical Details**:
- `agents/scenario_generator.py:426-449` - Handler calls `send_response()` directly
- `agent_framework.py:159-243` - Framework tries to detect if response was already sent
- Timing race condition: Framework checks message history before `send_response()` completes

### Issue #3: No New Scenario Options Generated
**Symptom**: After selecting an option, no new player choices are presented
**Root Cause**: `apply_player_choice` only returns consequence text, not new scenario structure

**Technical Details**:
- `agents/scenario_generator.py:615-657` - `apply_player_choice()` returns only text string
- Missing: New options generation after consequence
- Missing: Proper scenario structure with formatted options

## Implementation Plan

### Phase 1: Fix Option Number Parsing
**Objective**: Ensure correct option number is extracted and processed

**Changes Required**:

1. **Update `manual_command_handler.py`** - Move regex patterns before command_map matching:
   ```python
   def _parse_command(self, instruction: str) -> tuple:
       instruction_lower = instruction.lower().strip()
       
       # PRIORITY 1: Handle parameterized patterns FIRST
       if instruction_lower.startswith('select option'):
           match = re.search(r'select option (\d+)', instruction_lower)
           if match:
               return 'scenario_generator', 'apply_player_choice', {'option_number': int(match.group(1))}
       
       # PRIORITY 2: Then check command map for exact matches
       sorted_patterns = sorted(self.command_map.items(), key=lambda x: len(x[0]), reverse=True)
       for pattern, (agent, action) in sorted_patterns:
           if pattern in instruction_lower:
               params = self._extract_params(instruction)
               return agent, action, params
   ```

2. **Remove conflicting command_map entries**:
   ```python
   # Remove these lines from command_map:
   'select option': ('scenario_generator', 'apply_player_choice'),
   'choose option': ('scenario_generator', 'apply_player_choice'),
   'option': ('scenario_generator', 'apply_player_choice'),
   ```

### Phase 2: Fix Response Handling
**Objective**: Eliminate "No response sent" warnings

**Changes Required**:

1. **Update `agents/scenario_generator.py`** - Return `None` when sending response directly:
   ```python
   def _handle_apply_player_choice(self, message: AgentMessage):
       # ... existing validation code ...
       
       try:
           continuation = self.apply_player_choice(game_state, player, choice)
           self.send_response(message, {"success": True, "continuation": continuation})
           return None  # Indicate response was sent directly
       except Exception as e:
   ```

2. **Update `agent_framework.py`** - Improve response detection timing:
   ```python
   # Increase delay to allow send_response to complete
   time.sleep(0.05)  # Increase from 0.01 to 0.05 seconds
   ```

### Phase 3: Generate New Scenario Options
**Objective**: Provide new player choices after each option selection

**Changes Required**:

1. **Enhance `apply_player_choice()` method** to return structured scenario:
   ```python
   def apply_player_choice(self, state: Dict[str, Any], player: str, choice_value: int) -> Dict[str, Any]:
       # ... existing choice processing ...
       
       # Generate consequence with new options
       consequence_prompt = self._build_creative_choice_prompt(state, target, player)
       consequence_scenario = self._generate_creative_scenario(consequence_prompt, [], state.get('story_arc', ''), str(state))
       
       return {
           "consequence": consequence_scenario.get("scenario_text", f"{player} chose: {target}"),
           "new_options": consequence_scenario.get("options", []),
           "formatted_response": self._format_consequence_with_options(consequence_scenario)
       }
   ```

2. **Add option formatting helper**:
   ```python
   def _format_consequence_with_options(self, scenario: Dict[str, Any]) -> str:
       consequence = scenario.get("scenario_text", "")
       options = scenario.get("options", [])
       
       if options:
           formatted_options = "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(options)])
           return f"{consequence}\n\n## Player Options\n{formatted_options}\n\n*Type 'select option [number]' to choose.*"
       else:
           return consequence
   ```

3. **Update response handling** to store new options:
   ```python
   def _handle_apply_player_choice(self, message: AgentMessage):
       # ... existing code ...
       
       try:
           result = self.apply_player_choice(game_state, player, choice)
           
           # Store new options for future selection
           if result.get("new_options"):
               # Update last_scenario_options in command handler via message bus
               self.send_message("orchestrator", "update_scenario_options", {
                   "options": result["new_options"]
               })
           
           self.send_response(message, {
               "success": True, 
               "continuation": result["formatted_response"]
           })
           return None
   ```

## Testing Plan

### Test Case 1: Correct Option Selection
```
Input: "select option 2"
Expected: System processes choice 2, not choice 1
Verification: Check terminal output shows "Processing choice 2"
```

### Test Case 2: Response Handling
```
Input: Any valid option selection
Expected: No "No response sent" warnings
Verification: Clean terminal output without framework warnings
```

### Test Case 3: Continuous Scenario Flow
```
Input: Generate scenario → Select option → Should get new options
Expected: New numbered options presented after consequence
Verification: Player can continue selecting from new options
```

## Risk Assessment

**Low Risk**:
- Option parsing fix (isolated change)
- Response timing adjustment (minimal impact)

**Medium Risk**:
- Scenario structure changes (affects multiple components)
- Need to ensure backward compatibility

**Mitigation Strategies**:
- Implement changes incrementally
- Test each phase before proceeding
- Maintain fallback behavior for edge cases

## Success Criteria

1. ✅ User types "select option 2" → System processes choice 2
2. ✅ No warning messages in terminal output
3. ✅ After selecting an option, new options are presented
4. ✅ Scenario flow continues seamlessly
5. ✅ All existing functionality remains intact

---

**Next Steps**: Implement Phase 1 (option parsing fix) first, then test before proceeding to subsequent phases.