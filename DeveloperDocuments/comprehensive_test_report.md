
# D&D System Comprehensive Test Report
Generated: 2025-08-24T06:44:22.181661
Test Duration: 240.33s

## Summary
- Total Tests: 36
- Failed Tests: 1
- Success Rate: 97.2%
- Gameplay Rounds: 7
- Average Story Progression Score: 0.50/1.0

## Component Test Results

### SystemInit: 2/2 tests passed
- ✅ config_creation
- ✅ game_initialization

### Connectivity: 3/3 tests passed
- ✅ orchestrator_status
- ✅ session_manager
- ✅ game_engine

### Agents: 8/8 tests passed
- ✅ scenario_generator_availability
- ✅ scenario_generator_schema
- ✅ rag_retriever_availability
- ✅ rag_retriever_schema
- ✅ npc_controller_availability
- ✅ npc_controller_schema
- ✅ main_interface_availability
- ✅ main_interface_schema

### Pipeline: 3/3 tests passed
- ✅ request_1_gameplay_turn
- ✅ request_2_scenario_generation
- ✅ request_3_rag_query

### SessionMgmt: 3/3 tests passed
- ✅ save_game
- ✅ session_state
- ✅ game_statistics

### GameEngine: 2/2 tests passed
- ✅ skill_check
- ✅ state_export

### DocumentStore: 2/2 tests passed
- ✅ search
- ✅ enhanced_search

### Gameplay: 8/8 tests passed
- ✅ round_1
- ✅ round_2
- ✅ round_3
- ✅ round_4
- ✅ round_5
- ✅ round_6
- ✅ round_7
- ✅ full_session

### ErrorHandling: 4/4 tests passed
- ✅ error_empty_input
- ✅ error_null_input
- ✅ error_very_long_input
- ✅ error_invalid_unicode

### Performance: 0/1 tests passed
- ❌ average_response_time

## Gameplay Session Analysis

### Round 1
- Input: look around the tavern
- Response Length: 189 chars
- Story Progression Score: 0.50
- Narrative Elements: 0/5 present

### Round 2
- Input: talk to the bartender
- Response Length: 149 chars
- Story Progression Score: 0.50
- Narrative Elements: 0/5 present

### Round 3
- Input: ask about local rumors
- Response Length: 152 chars
- Story Progression Score: 0.50
- Narrative Elements: 0/5 present

### Round 4
- Input: investigate the mysterious door
- Response Length: 152 chars
- Story Progression Score: 0.50
- Narrative Elements: 0/5 present

### Round 5
- Input: search for clues about the missing merchant
- Response Length: 157 chars
- Story Progression Score: 0.50
- Narrative Elements: 0/5 present

### Round 6
- Input: examine the strange artifact on the table
- Response Length: 189 chars
- Story Progression Score: 0.50
- Narrative Elements: 0/5 present

### Round 7
- Input: listen to the conversation at the next table
- Response Length: 149 chars
- Story Progression Score: 0.50
- Narrative Elements: 0/5 present

## Failures and Issues

### Performance - Unknown error
```
No traceback available
```

## Performance Metrics
- game_initialization_time: 0.004055976867675781 seconds
- pipeline_gameplay_turn_time: 9.784263849258423 seconds
- pipeline_scenario_generation_time: 2.998253107070923 seconds
- pipeline_rag_query_time: 42.45855784416199 seconds
- skill_check_time: 0.00011372566223144531 seconds
- round_1_time: 11.54513692855835 seconds
- round_2_time: 9.85613489151001 seconds
- round_3_time: 10.12392783164978 seconds
- round_4_time: 11.316706895828247 seconds
- round_5_time: 16.006978034973145 seconds
- round_6_time: 13.182951211929321 seconds
- round_7_time: 15.10817265510559 seconds
- full_session_time: 90.6697289943695 seconds
- avg_response_time: 12.766035747528075 seconds

## Full Debug Data
Saved to: debug_test_data.json
