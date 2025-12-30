# Game Response System Implementation Plan (State Management Compliant)

## Overview
This plan adds numbered choice support to the existing D&D game system while strictly following the Clean Slate Architecture from GAME_STATE_ANALYSIS.md.

## State Management Compliance

### Following Option 2: State Hierarchy with Clear Ownership
```
CampaignConfig (immutable) ← parsed once during initialization
     ↓
GameState (runtime) ← authoritative for active gameplay
     ↓
SessionState (persistence) ← serializes GameState + metadata
```

### Compliance Rules Applied
- **CampaignConfig**: Read-only access via `self.game_engine.campaign_config`
- **GameState**: All runtime state updates through GameEngine (authoritative)
- **SessionState**: Only persistence and analytics, no game state business logic

## Available Infrastructure
- **Orchestrator Pipelines**: `_run_scenario_pipeline()`, `_run_rag_pipeline()`, `_handle_gameplay_turn_pipeline_dto()`
- **GameEngine Methods**: `update_narrative_context()`, `set_campaign_flag()`, `add_story_hook()`, `set_location()`
- **SessionManager Methods**: `add_routing_decision()`, `get_session_metadata()`, `save_session()`

## Component Enhancements (State Hierarchy Compliant)

### GameEngine Additions (Runtime State Authority)
Add new method to `components/game_engine.py`:
```python
def process_scenario_state_updates(self, scenario_data: Dict[str, Any], turn_number: int):
    """Process scenario data and update authoritative game state"""
    
    # GameEngine is authoritative for all runtime state updates
    narrative_updates = {
        "current_scene": scenario_data.get("scene", "")[:100] + "...",
        "last_scenario_type": scenario_data.get("scenario_type", "unknown"),
        "scenario_confidence": scenario_data.get("confidence", 0),
        "turn_number": turn_number
    }
    self.update_narrative_context(narrative_updates)
    
    # Process state changes using existing authoritative methods
    state_changes = scenario_data.get("state_changes", {})
    if state_changes:
        if "location" in state_changes:
            self.set_location(state_changes["location"])
            
        if "flags" in state_changes:
            for flag_name, flag_value in state_changes["flags"].items():
                self.set_campaign_flag(flag_name, flag_value)
        
        if "story_hooks" in state_changes:
            for hook in state_changes["story_hooks"]:
                self.add_story_hook(hook, "normal")
        
        if "quest_objectives" in state_changes:
            for objective in state_changes["quest_objectives"]:
                self.add_quest_objective(objective)
```

### SessionManager Additions (Persistence Only)
Add new method to `components/session_manager.py`:
```python
def record_turn_analytics(self, input_data: Dict[str, Any], response_type: str, confidence: float, turn_number: int):
    """Record turn analytics for persistence - no game state logic"""
    
    # SessionManager only handles persistence and analytics
    routing_data = {
        "route": response_type,
        "confidence": confidence,
        "player_input": input_data.get("original_input", ""),
        "input_type": input_data.get("type", "unknown"),
        "turn_number": turn_number,
        "timestamp": time.time()
    }
    
    # Use existing persistence method
    self.add_routing_decision(routing_data)
```

## Implementation Plan (State Hierarchy Compliant)

### Phase 1: Enhanced Response Handling

#### 1.1 Update HaystackDnDGame Class Structure
```python
class HaystackDnDGame:
    def __init__(self, ...):
        # Existing initialization
        
        # Add choice management fields (UI state only, not game state)
        self.current_scenario: Optional[Dict[str, Any]] = None
        self.current_choices: List[Dict[str, Any]] = []
        self.turn_counter: int = 0
```

#### 1.2 Update play_turn() Method (State Hierarchy Compliant)
```python
def play_turn(self, player_input: str) -> str:
    """Enhanced turn processing following state hierarchy"""
    
    if not player_input or not isinstance(player_input, str) or not player_input.strip():
        return "The world waits for your action..."
    
    self.turn_counter += 1
    
    # Process input (UI logic only)
    processed_input = self._process_input(player_input)
    
    # Create DTO using existing pattern
    request_dto = self._create_dto(processed_input)
    
    # Use existing orchestrator
    response_dto: GameResponseDTO = self.orchestrator.process_request(request_dto)
    
    if response_dto.success:
        formatted_result = self._handle_response(response_dto.data)
        
        # COMPLIANCE: Delegate state updates to authoritative components
        self._update_state_via_authorities(processed_input, response_dto.data)
        
        return formatted_result["formatted_response"]
    else:
        return self._handle_error(response_dto.data)

def _update_state_via_authorities(self, processed_input: Dict[str, Any], response_data: Dict[str, Any]):
    """Update state via authoritative components following hierarchy"""
    
    response_type = response_data.get("response_type", "unknown")
    
    # COMPLIANCE: GameEngine is authoritative for runtime state
    if response_type == "scenario":
        scenario = response_data.get("scenario", {})
        self.game_engine.process_scenario_state_updates(scenario, self.turn_counter)
    
    # COMPLIANCE: SessionManager only for persistence/analytics  
    confidence = 0
    if response_type == "scenario":
        confidence = response_data.get("scenario", {}).get("confidence", 0)
    elif response_type == "rag_query":
        confidence = response_data.get("rag_result", {}).get("confidence", 0)
    
    self.session_manager.record_turn_analytics(processed_input, response_type, confidence, self.turn_counter)
```

#### 1.3 Input Processing Method (UI Logic Only)
```python
def _process_input(self, player_input: str) -> Dict[str, Any]:
    """Process player input - UI logic only, no state management"""
    
    input_stripped = player_input.strip()
    
    # Check if input is a number corresponding to a choice
    if input_stripped.isdigit() and self.current_choices:
        choice_num = int(input_stripped)
        if 1 <= choice_num <= len(self.current_choices):
            selected_choice = self.current_choices[choice_num - 1]
            # Convert choice to action text for pipeline
            action_text = selected_choice.get("title", "") + " " + selected_choice.get("description", "")
            return {
                "type": "choice_selection", 
                "original_input": player_input,
                "processed_input": action_text,
                "selected_choice": selected_choice
            }
    
    # Regular text input
    return {
        "type": "text_action",
        "original_input": player_input,
        "processed_input": input_stripped
    }
```

### Phase 2: Response Handling (UI Presentation Only)

#### 2.1 GameResponseDTO Handler
```python
def _handle_response(self, response_data: GameResponseDTO) -> Dict[str, Any]:
    """Handle GameResponseDTO - UI presentation only"""
    
    response_type = response_data.get("response_type", "unknown")
    
    if response_type == "scenario":
        return self._handle_scenario(response_data)
    elif response_type == "rag_query":  
        return self._handle_rag(response_data)
    elif response_type == "npc_interaction":
        return self._handle_npc(response_data)
    else:
        return self._handle_unknown(response_data)

def _handle_scenario(self, response_data: GameResponseDTO) -> Dict[str, Any]:
    """Handle scenario responses - UI state only"""
    
    scenario = response_data.get("scenario", {})
    scene = scenario.get("scene", "The adventure continues...")
    choices = scenario.get("choices", [])
    
    # Update UI state only (not game state - that's handled by GameEngine)
    self.current_scenario = scenario
    self.current_choices = choices
    
    # Format response with numbered choices
    formatted_response = scene
    if choices:
        formatted_response += "\n\n📋 Choose your action:"
        for i, choice in enumerate(choices, 1):
            title = choice.get("title", f"Option {i}")
            description = choice.get("description", "")
            formatted_response += f"\n{i}. {title}"
            if description:
                formatted_response += f" - {description}"
    
    return {
        "formatted_response": formatted_response,
        "response_type": "scenario", 
        "scenario_data": scenario,
        "choices": choices,
        "raw_data": response_data
    }

def _handle_rag(self, response_data: GameResponseDTO) -> Dict[str, Any]:
    """Handle RAG responses - UI presentation only"""
    
    rag_result = response_data.get("rag_result", {})
    rag_context = rag_result.get("response", "")
    query = rag_result.get("original_query", "")
    confidence = rag_result.get("confidence", 0)
    
    if rag_context:
        formatted_response = f"📚 {rag_context}"
        if confidence > 0:
            formatted_response += f"\n\n💡 Information confidence: {confidence:.1%}"
    else:
        formatted_response = f"I searched for information about '{query}', but couldn't find specific details."
    
    # Maintain current scenario context (UI state)
    if self.current_scenario and self.current_choices:
        formatted_response += "\n\n" + self._format_choices()
    
    return {
        "formatted_response": formatted_response,
        "response_type": "rag_query",
        "rag_data": rag_result,
        "raw_data": response_data
    }

def _format_choices(self) -> str:
    """Format current choices for display - UI only"""
    if not self.current_choices:
        return ""
    
    choice_text = "📋 Available actions:"
    for i, choice in enumerate(self.current_choices, 1):
        title = choice.get("title", f"Option {i}")
        choice_text += f"\n{i}. {title}"
    return choice_text
```

### Phase 3: Initial Scenario (State Hierarchy Compliant)

#### 3.1 Initial Scenario Generation
```python
def __init__(self, policy_profile: str = "house", config: GameInitConfig = None):
    # ... existing initialization code ...
    
    # Generate initial scenario
    self._generate_initial_scenario()

def _generate_initial_scenario(self):
    """Generate initial scenario following state hierarchy"""
    
    try:
        print("🎬 Generating initial scenario...")
        
        initial_dto = self._create_initial_dto()
        response_dto: GameResponseDTO = self.orchestrator.process_request(initial_dto)
        
        if response_dto.success:
            formatted_result = self._handle_response(response_dto.data)
            
            # COMPLIANCE: Use authoritative components for state updates
            self._update_state_via_authorities(
                {"type": "initialization", "original_input": "GAME_START"}, 
                response_dto.data
            )
            
            self.initial_scenario = formatted_result
            print("✅ Initial scenario generated")
        else:
            print("⚠️ Failed to generate initial scenario")
            
    except Exception as e:
        print(f"❌ Error generating initial scenario: {e}")

def _create_initial_dto(self) -> RequestDTO:
    """Create DTO for initial scenario"""
    
    from shared_contract import new_dto
    
    request_dto = new_dto(
        "Generate the opening scenario for this campaign. Set the scene, introduce the setting, and provide initial choices for the player to begin their adventure.",
        {}
    )
    
    request_dto["_game_engine_ref"] = self.game_engine
    request_dto["_policy_engine_ref"] = self.policy_engine
    request_dto["type"] = "scenario"
    
    return request_dto
```

### Phase 4: Enhanced Interactive Loop (UI Only)

#### 4.1 Update Interactive Game Loop
```python
def run_interactive(self):
    """Enhanced interactive game loop - UI presentation only"""
    
    print("=" * 70)
    print("🎲 D&D GAME")
    print("=" * 70)
    print("🚀 Powered by: Orchestrator, Agents, Pipelines & Components")
    print("Type 'help' for commands, 'quit' to exit")
    print()
    
    # Display initial scenario if available
    if hasattr(self, 'initial_scenario') and self.initial_scenario:
        print("🎭 OPENING SCENE:")
        print(self.initial_scenario["formatted_response"])
    else:
        # COMPLIANCE: Use immutable CampaignConfig via GameEngine
        session_metadata = self.session_manager.get_session_metadata()
        if session_metadata.get("session_active"):
            story = "Welcome to your adventure!"
            if self.game_engine.campaign_config:  # Read-only access to immutable config
                story = self.game_engine.campaign_config.story
            print("🎭 SCENE:")
            print(story)
    
    print()
    
    # Main game loop with choice display
    while True:
        try:
            # COMPLIANCE: Use SessionManager for session metadata only
            session_metadata = self.session_manager.get_session_metadata()
            player_name = session_metadata.get("player_name", "Player") if session_metadata.get("session_active") else "Player"
            
            # Show current choices if available (UI state)
            if self.current_choices:
                print(f"\n📋 Available actions (enter number 1-{len(self.current_choices)}):")
                for i, choice in enumerate(self.current_choices, 1):
                    title = choice.get("title", f"Option {i}")
                    print(f"  {i}. {title}")
                print("Or enter your own action/question...")
            
            player_input = input(f"\n{player_name}> ").strip()
            
            if not player_input:
                continue
            
            # Handle system commands
            if player_input.lower() in ["quit", "exit", "q"]:
                print("💾 Saving game before exit...")
                self.save_game()  # Uses existing state hierarchy
                print("👋 Thanks for playing! Goodbye!")
                break
            elif player_input.lower() == "help":
                self._show_enhanced_help()
                continue
            elif player_input.lower() == "save":
                self.save_game()  # Uses existing state hierarchy
                continue
            elif player_input.lower() == "stats":
                self._show_stats()
                continue
            
            # Process game turn
            print("\n🎲 Processing...")
            dm_response = self.play_turn(player_input)
            print(f"\n🎭 DM:")
            print(dm_response)
            print()
            
        except KeyboardInterrupt:
            print("\n\n💾 Saving game before exit...")
            self.save_game()
            print("👋 Game interrupted. Goodbye!")
            break
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            print("The game continues...")
```

#### 4.2 Enhanced Statistics (Read-Only Access)
```python
def _show_stats(self):
    """Enhanced stats display - read-only access to authoritative sources"""
    
    # COMPLIANCE: Get stats from authoritative GameEngine
    stats = self.get_game_stats()  # Uses existing method that accesses GameEngine
    
    print(f"\n📊 Game Statistics:")
    print(f"Location: {stats.get('location', 'Unknown')}")
    print(f"Turn: {self.turn_counter}")
    print(f"Session time: {stats.get('session_duration', 0):.1f}s")
    
    # UI state only
    if self.current_scenario:
        print(f"Current scenario: {self.current_scenario.get('scenario_type', 'Unknown')}")
        print(f"Choices available: {len(self.current_choices)}")
    
    # COMPLIANCE: Get analytics from SessionManager (persistence layer)
    session_stats = self.session_manager.get_session_statistics()
    routing_stats = self.session_manager.get_routing_statistics()
    if routing_stats["total_decisions"] > 0:
        print(f"Average routing confidence: {routing_stats['average_confidence']:.1%}")
```

## State Management Compliance Summary

### ✅ Following Clean Slate Architecture
- **CampaignConfig**: Read-only access via `self.game_engine.campaign_config`
- **GameState Authority**: All state updates via `GameEngine.process_scenario_state_updates()`
- **SessionManager Persistence**: Only analytics via `SessionManager.record_turn_analytics()`
- **No State Duplication**: Each piece of data exists in exactly one place
- **UI Separation**: Main game class handles only UI/presentation logic

### ✅ Implementation Philosophy Compliance
- **Clean Slate**: No redundant code paths
- **Single Source of Truth**: GameEngine authoritative for runtime state
- **Simple Persistence**: SessionManager only handles serialization and analytics
- **No Business Logic in SessionManager**: Only persistence and analytics methods added

## Implementation Timeline

### Week 1: Component Methods and Core Response Handling
- [ ] Add `process_scenario_state_updates()` method to GameEngine (authoritative state)
- [ ] Add `record_turn_analytics()` method to SessionManager (persistence only)
- [ ] Update HaystackDnDGame class structure (UI state only)
- [ ] Implement choice input processing (UI logic only)
- [ ] Update play_turn() method (state hierarchy compliant)

### Week 2: Response Management  
- [ ] Implement GameResponseDTO handlers (UI presentation only)
- [ ] Add choice display and management (UI state only)
- [ ] Test scenario and RAG response handling
- [ ] Verify choice persistence across turns

### Week 3: Initial Scenario and Polish
- [ ] Implement initial scenario generation (state hierarchy compliant)
- [ ] Update interactive loop (UI presentation only)
- [ ] Add enhanced statistics (read-only authoritative access)
- [ ] Comprehensive testing

## Success Criteria (State Hierarchy Compliance)

1. **Authoritative State**: All runtime state updates through GameEngine methods
2. **Immutable Campaign**: Read-only access to CampaignConfig via GameEngine
3. **Persistence Only**: SessionManager handles only analytics and serialization
4. **UI Separation**: Main game class contains no game state business logic
5. **No State Duplication**: Each piece of data exists in exactly one authoritative location
6. **Choice Management**: Add numbered choice support without violating state hierarchy

This plan strictly follows the Clean Slate Architecture and maintains clear separation between UI logic, authoritative game state, and persistence layers.