# Enhanced Scenario Generator Implementation Plan
*Comprehensive architecture integration based on user feedback and existing component analysis*

## Overview

This enhanced implementation plan integrates the scenario generator with the existing game architecture components to provide comprehensive D&D scenario generation using all 9 categories of context information. The plan focuses on leveraging existing components while adding minimal new complexity.

## Enhanced Architecture Integration

### Core Components Integration

**GameEngine** ([`components/game_engine.py:17`](components/game_engine.py:17))
- **Current**: Basic GameState with characters, combat_state, environment, campaign_flags, session_data
- **Enhancement**: Add narrative_context, location_context, quest_context fields

**SessionManager** ([`components/session_manager.py:36`](components/session_manager.py:36))  
- **Current**: Session persistence and state management
- **Enhancement**: Track narrative progression, quest updates, hook continuation

**CharacterManager** ([`components/character_manager.py:45`](components/character_manager.py:45))
- **Current**: Character data and skill calculations
- **Enhancement**: Party-level analysis methods for scenario generation

**Main Interface Agent** ([`agents/main_interface_agent_fixed.py`](agents/main_interface_agent_fixed.py))
- **Current**: Intent classification and DTO creation
- **Enhancement**: Populate DTO with enhanced game context during extraction

**Game Initialization** ([`game_initialization.py:27`](game_initialization.py:27))
- **Current**: Campaign setup and save file management  
- **Enhancement**: Initialize enhanced game state and maintain it across player turns

## Phase 1: Core Architecture Updates

### 1.1 GameState Enhancement
Update [`components/game_engine.py:17`](components/game_engine.py:17) GameState class:

```python
@dataclass
class GameState:
    """Enhanced game state structure for comprehensive scenario generation"""
    # Existing fields
    characters: Dict[str, Any]
    combat_state: Dict[str, Any]
    environment: Dict[str, Any]
    campaign_flags: Dict[str, Any]
    session_data: Dict[str, Any]
    
    # NEW: Narrative context for scenario generation
    narrative_context: Dict[str, Any] = field(default_factory=lambda: {
        'scene_summary': [],  # Last 2-3 actions/events
        'unresolved_hooks': [],  # Open plot threads
        'pacing_state': 'exploration',  # combat/social/exploration/rest
        'tone': 'heroic',  # heroic/dark/mysterious/comedic
        'recent_events': [],  # Chronological action history
        'narrative_momentum': 'steady'  # building/climactic/resolving/steady
    })
    
    # NEW: Enhanced location context  
    location_context: Dict[str, Any] = field(default_factory=lambda: {
        'current_location': 'Unknown',
        'location_tags': [],  # interior/exterior, dungeon/urban/wilderness
        'map_features': {  # exits, cover, hazards, lighting
            'exits': [],
            'cover': [],
            'hazards': [],
            'lighting': 'normal'
        },
        'interactables': [],  # doors, levers, objects with affordances
        'alert_level': 'calm',  # calm/suspicious/alert/hostile
        'atmosphere': {},  # sounds, smells, notable features
        'visibility': 'clear'  # clear/dim/dark/fog/etc
    })
    
    # NEW: Quest and campaign tracking
    quest_context: Dict[str, Any] = field(default_factory=lambda: {
        'active_quests': [],  # Current quest objectives
        'quest_progress': {},  # Quest ID -> progress markers
        'campaign_hooks': [],  # Available story hooks
        'completed_milestones': [],  # Story progression tracking
        'content_safety': {  # Content guidelines
            'violence_level': 'standard',
            'mature_themes': False,
            'horror_elements': False
        },
        'spoiler_sensitivity': 'medium'  # low/medium/high
    })
```

### 1.2 CharacterManager Enhancement
Add party-level methods to [`components/character_manager.py:45`](components/character_manager.py:45):

```python
def get_party_snapshot(self) -> Dict[str, Any]:
    """Get comprehensive party information for scenario generation"""
    if not self.characters:
        return self._default_party_snapshot()
        
    characters = list(self.characters.values())
    levels = [char.level for char in characters]
    
    return {
        'avg_level': sum(levels) // len(levels) if levels else 3,
        'party_size': len(characters),
        'level_range': f"{min(levels)}-{max(levels)}" if levels else "1-3",
        'party_roles': self._analyze_party_roles(),
        'hp_state': self._analyze_hp_status(),
        'resources': self._analyze_party_resources(),
        'stealth_profile': self._analyze_stealth_capability(),
        'conditions_summary': self._summarize_conditions(),
        'party_dynamics': self._assess_party_dynamics()
    }

def _analyze_party_roles(self) -> Dict[str, int]:
    """Analyze tank/striker/support/control composition"""
    roles = {'tank': 0, 'striker': 0, 'support': 0, 'control': 0}
    # Role analysis logic based on character classes/abilities
    return roles

def _analyze_hp_status(self) -> Dict[str, Any]:
    """Analyze party health status for difficulty scaling"""
    # HP analysis logic
    return {
        'average_hp_percent': 85,
        'wounded_members': 0,
        'critical_members': 0,
        'healing_available': True
    }

def _analyze_party_resources(self) -> Dict[str, Any]:
    """Analyze spell slots, consumables, special abilities"""
    # Resource analysis logic  
    return {
        'spell_slots_remaining': 'high',  # high/medium/low/none
        'consumables': ['healing_potions', 'other'],
        'special_abilities_available': True,
        'long_rest_needed': False
    }
```

### 1.3 SessionManager Enhancement  
Update [`components/session_manager.py:36`](components/session_manager.py:36) to track narrative state:

```python
def update_narrative_context(self, narrative_updates: Dict[str, Any]):
    """Update narrative context based on player actions and scenario outcomes"""
    if not self.current_session:
        return
        
    game_state = self.current_session.game_state
    
    # Update scene summary (keep last 3 events)
    if 'new_event' in narrative_updates:
        scene_events = game_state.get('narrative_context', {}).get('scene_summary', [])
        scene_events.append(narrative_updates['new_event'])
        if len(scene_events) > 3:
            scene_events = scene_events[-3:]
        
    # Update hooks and quest progress
    if 'quest_progress' in narrative_updates:
        quest_context = game_state.get('quest_context', {})
        quest_context.update(narrative_updates['quest_progress'])
        
    # Update pacing state based on recent actions
    if 'pacing_change' in narrative_updates:
        narrative_context = game_state.get('narrative_context', {})
        narrative_context['pacing_state'] = narrative_updates['pacing_change']

def get_narrative_history(self) -> Dict[str, Any]:
    """Get narrative progression for scenario continuity"""
    if not self.current_session:
        return {}
        
    return {
        'scene_summary': self.current_session.game_state.get('narrative_context', {}).get('scene_summary', []),
        'quest_progress': self.current_session.game_state.get('quest_context', {}).get('quest_progress', {}),
        'unresolved_hooks': self.current_session.game_state.get('narrative_context', {}).get('unresolved_hooks', []),
        'pacing_state': self.current_session.game_state.get('narrative_context', {}).get('pacing_state', 'exploration')
    }
```

### 1.4 RequestDTO Enhancement
Update [`shared_contract.py`](shared_contract.py) RequestDTO structure:

```python
@dataclass  
class RequestDTO:
    # Existing core fields
    player_input: str
    action: str = ""
    target: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    rag: Dict[str, Any] = field(default_factory=dict)
    arguments: Dict[str, Any] = field(default_factory=dict)
    correlation_id: str = ""
    ts: float = 0.0
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # NEW: Enhanced game context fields
    game_state: Optional[Dict[str, Any]] = None  # From GameEngine.export_game_state()
    party_context: Optional[Dict[str, Any]] = None  # From CharacterManager.get_party_snapshot()
    narrative_context: Optional[Dict[str, Any]] = None  # From GameState.narrative_context
    quest_context: Optional[Dict[str, Any]] = None  # From GameState.quest_context
    location_context: Optional[Dict[str, Any]] = None  # From GameState.location_context
    
    # Enhanced metadata
    session_id: str = ""
    game_engine_available: bool = False
    character_manager_available: bool = False
    session_manager_available: bool = False
```

## Phase 2: Integration Updates

### 2.1 Main Interface Agent Enhancement
Update [`agents/main_interface_agent_fixed.py`](agents/main_interface_agent_fixed.py) classify_player_intent function:

```python
def classify_player_intent(player_input: str, rag_context: str = None, 
                         intent_data: Dict[str, Any] = None,
                         game_engine: Optional[Any] = None,
                         character_manager: Optional[Any] = None,
                         session_manager: Optional[Any] = None) -> Dict[str, Any]:
    """Enhanced intent classification with game state population"""
    
    # Create base DTO as before
    dto = new_dto(player_input, {})
    
    # NEW: Populate enhanced context if components available
    if game_engine:
        dto["game_state"] = game_engine.export_game_state()
        dto["narrative_context"] = game_engine.game_state.narrative_context
        dto["quest_context"] = game_engine.game_state.quest_context  
        dto["location_context"] = game_engine.game_state.location_context
        dto["game_engine_available"] = True
        
    if character_manager:
        dto["party_context"] = character_manager.get_party_snapshot()
        dto["character_manager_available"] = True
        
    if session_manager:
        session_state = session_manager.get_session_state()
        dto["session_id"] = session_state.get("session_id", "")
        dto["session_manager_available"] = True
    
    # Continue with existing intent classification logic...
    # [rest of function unchanged]
    
    return dto
```

### 2.2 Game Initialization Enhancement  
Update [`game_initialization.py`](game_initialization.py) to initialize enhanced game state:

```python
def initialize_enhanced_game_state(campaign_data: Dict[str, Any]) -> Dict[str, Any]:
    """Initialize enhanced game state from campaign data"""
    
    # Extract narrative context from campaign
    narrative_context = {
        'scene_summary': [],
        'unresolved_hooks': campaign_data.get('campaign_hooks', [])[:3],  # Start with campaign hooks
        'pacing_state': 'exploration',
        'tone': campaign_data.get('theme', 'heroic').lower(),
        'recent_events': [],
        'narrative_momentum': 'building'
    }
    
    # Extract location context from campaign
    starting_location = campaign_data.get('starting_location', 'Tavern')
    location_context = {
        'current_location': starting_location,
        'location_tags': _infer_location_tags(starting_location),
        'map_features': _get_default_map_features(starting_location),
        'interactables': _get_default_interactables(starting_location),
        'alert_level': 'calm',
        'atmosphere': _get_location_atmosphere(starting_location),
        'visibility': 'clear'
    }
    
    # Initialize quest context from campaign
    quest_context = {
        'active_quests': [],  # Will be populated as quests are given
        'quest_progress': {},
        'campaign_hooks': campaign_data.get('campaign_hooks', []),
        'completed_milestones': [],
        'content_safety': {
            'violence_level': campaign_data.get('difficulty', 'standard'),
            'mature_themes': False,
            'horror_elements': False
        },
        'spoiler_sensitivity': 'medium'
    }
    
    return {
        'narrative_context': narrative_context,
        'location_context': location_context,
        'quest_context': quest_context
    }

def _infer_location_tags(location: str) -> List[str]:
    """Infer location tags from location name"""
    location_lower = location.lower()
    tags = []
    
    if any(word in location_lower for word in ['tavern', 'inn', 'shop', 'house']):
        tags.extend(['interior', 'urban', 'social'])
    elif any(word in location_lower for word in ['forest', 'woods', 'field', 'road']):
        tags.extend(['exterior', 'wilderness', 'travel'])  
    elif any(word in location_lower for word in ['dungeon', 'cave', 'tomb', 'ruins']):
        tags.extend(['interior', 'dungeon', 'dangerous'])
    elif any(word in location_lower for word in ['city', 'town', 'village']):
        tags.extend(['exterior', 'urban', 'populated'])
        
    return tags
```

## Phase 3: Scenario Generator Enhancement

### 3.1 Enhanced Context Extraction
Update scenario generator's context extraction function:

```python
def extract_comprehensive_context(dto: Dict[str, Any]) -> Dict[str, Any]:
    """Extract all 9 categories of context from enhanced DTO"""
    
    context = {}
    
    # A) Narrative & Pacing
    context['narrative'] = {
        'scene_summary': dto.get('narrative_context', {}).get('scene_summary', []),
        'unresolved_hooks': dto.get('narrative_context', {}).get('unresolved_hooks', []),
        'pacing_state': dto.get('narrative_context', {}).get('pacing_state', 'exploration'),
        'tone': dto.get('narrative_context', {}).get('tone', 'heroic'),
        'narrative_momentum': dto.get('narrative_context', {}).get('narrative_momentum', 'steady')
    }
    
    # B) Player Intent  
    context['player_intent'] = {
        'action_verb': dto.get('action', 'explore'),
        'target': dto.get('target'),
        'player_input': dto.get('player_input', ''),
        'arguments': dto.get('arguments', {}),
        'confidence': dto.get('confidence', 0.8)
    }
    
    # C) Party Snapshot
    party_data = dto.get('party_context', {})
    context['party'] = {
        'avg_level': party_data.get('avg_level', 3),
        'party_size': party_data.get('party_size', 1),
        'party_roles': party_data.get('party_roles', {}),
        'hp_state': party_data.get('hp_state', {'average_hp_percent': 85}),
        'resources': party_data.get('resources', {'spell_slots_remaining': 'medium'}),
        'stealth_profile': party_data.get('stealth_profile', 'normal'),
        'conditions': party_data.get('conditions_summary', [])
    }
    
    # D) Location & Environment  
    location_data = dto.get('location_context', {})
    context['location'] = {
        'current_location': location_data.get('current_location', dto.get('context', {}).get('location', 'Unknown')),
        'location_tags': location_data.get('location_tags', []),
        'map_features': location_data.get('map_features', {}),
        'interactables': location_data.get('interactables', []),
        'alert_level': location_data.get('alert_level', 'calm'),
        'atmosphere': location_data.get('atmosphere', {}),
        'visibility': location_data.get('visibility', 'clear')
    }
    
    # E) NPCs/Creatures Present
    # Extract from game state or context
    game_state = dto.get('game_state', {})
    context['npcs'] = {
        'present_npcs': game_state.get('characters', {}),
        'npc_attitudes': {},  # Would be populated from game state
        'npc_objectives': {},  # Would be populated from game state
        'relationship_status': {}  # Would be populated from session history
    }
    
    # F) Quests & Constraints
    quest_data = dto.get('quest_context', {})  
    context['quests'] = {
        'active_quests': quest_data.get('active_quests', []),
        'quest_progress': quest_data.get('quest_progress', {}),
        'campaign_hooks': quest_data.get('campaign_hooks', []),
        'content_safety': quest_data.get('content_safety', {}),
        'spoiler_sensitivity': quest_data.get('spoiler_sensitivity', 'medium')
    }
    
    # G) Mechanics Policy
    context['mechanics'] = {
        'difficulty_target': _calculate_difficulty_from_party(party_data),
        'dc_policy': _get_dc_ranges_for_level(party_data.get('avg_level', 3)),
        'combat_budget': _calculate_encounter_budget(party_data),
        'choice_count': _determine_choice_count(dto.get('confidence', 0.8))
    }
    
    # H) RAG Snippets  
    rag_data = dto.get('rag', {})
    context['rag'] = {
        'response': rag_data.get('response', ''),
        'lore_facts': _parse_rag_into_facts(rag_data.get('response', '')),
        'confidence': rag_data.get('confidence', 0.0),
        'contradiction_constraints': _extract_constraints(rag_data),
        'source_priority': _assess_source_hierarchy(rag_data)
    }
    
    # I) Output Contract
    context['output_contract'] = {
        'required_fields': ['scene', 'choices', 'effects', 'hooks'],
        'optional_fields': ['gm_notes', 'state_changes', 'difficulty_used'],
        'validation_rules': _get_validation_requirements(),
        'format_requirements': 'strict_json'
    }
    
    return context
```

### 3.2 Enhanced Prompt Template
Create comprehensive prompt template using extracted context:

```python
def create_scenario_from_dto(dto: Dict[str, Any]) -> str:
    """Generate comprehensive scenario prompt from enhanced DTO context"""
    
    context = extract_comprehensive_context(dto)
    
    prompt = f"""
# D&D Scenario Generation

## A) NARRATIVE CONTEXT
**Current Scene**: {_format_scene_summary(context['narrative'])}
**Pacing State**: {context['narrative']['pacing_state']} ({context['narrative']['narrative_momentum']})
**Tone**: {context['narrative']['tone']}
**Unresolved Hooks**: {_format_hooks(context['narrative']['unresolved_hooks'])}

## B) PLAYER INTENT  
**Action**: {context['player_intent']['action_verb']}
**Target**: {context['player_intent']['target'] or 'general environment'}
**Input**: "{context['player_intent']['player_input']}"
**Confidence**: {context['player_intent']['confidence']:.1f}

## C) PARTY SNAPSHOT
**Level**: {context['party']['avg_level']} (party of {context['party']['party_size']})
**Composition**: {_format_party_roles(context['party']['party_roles'])}
**Health**: {context['party']['hp_state']['average_hp_percent']}% average HP
**Resources**: {_format_resources(context['party']['resources'])}
**Conditions**: {', '.join(context['party']['conditions']) or 'None'}

## D) LOCATION & ENVIRONMENT
**Location**: {context['location']['current_location']}
**Tags**: {', '.join(context['location']['location_tags']) or 'Unknown'}
**Features**: {_format_map_features(context['location']['map_features'])}
**Interactables**: {', '.join(context['location']['interactables']) or 'Standard objects'}
**Alert Level**: {context['location']['alert_level']}
**Atmosphere**: {_format_atmosphere(context['location']['atmosphere'])}

## E) NPCs & CREATURES
{_format_npc_context(context['npcs'])}

## F) QUESTS & CONSTRAINTS  
**Active Quests**: {_format_active_quests(context['quests']['active_quests'])}
**Available Hooks**: {_format_hooks(context['quests']['campaign_hooks'])}
**Content Guidelines**: {_format_content_safety(context['quests']['content_safety'])}

## G) MECHANICS POLICY
**Difficulty**: {context['mechanics']['difficulty_target']}
**DC Range**: {context['mechanics']['dc_policy']['easy']}-{context['mechanics']['dc_policy']['hard']}
**Encounter Budget**: {context['mechanics']['combat_budget']}
**Choice Count**: {context['mechanics']['choice_count']} options

## H) RELEVANT LORE
{_format_rag_context(context['rag'])}

## I) OUTPUT REQUIREMENTS
Generate a JSON response with these exact fields:
- `scene`: Rich description of what happens (150-300 words)
- `choices`: Array of {context['mechanics']['choice_count']} player options
- `effects`: Consequences and state changes  
- `hooks`: New plot threads or quest developments
- `gm_notes`: Hidden information for the DM
- `state_changes`: Explicit game state updates needed
- `difficulty_used`: Actual DCs and mechanics applied

**GENERATION GUIDELINES**:
1. Respect the current tone and pacing state
2. Scale difficulty to party level and composition  
3. Advance unresolved hooks when appropriate
4. Include environmental details and interactables
5. Consider party resources and conditions
6. Maintain narrative momentum and continuity
7. Provide meaningful choices that matter
8. Include state changes for persistent effects

Generate scenario:
"""
    
    return prompt.strip()
```

## Phase 4: Testing and Integration

### 4.1 Component Integration Testing
- Test enhanced DTO population across all components
- Verify graceful degradation when components unavailable  
- Validate state synchronization between components
- Test save/load with enhanced game state

### 4.2 Scenario Quality Testing  
- Generate scenarios with full enhanced context
- Generate scenarios with partial context (fallback testing)
- Validate mechanical consistency (DC scaling, party consideration)
- Test narrative continuity and hook progression

### 4.3 Performance Testing
- Measure context extraction time (target: <100ms)
- Test memory usage with enhanced state
- Validate token usage efficiency in prompts
- Test concurrent session handling

## Implementation Timeline

### Week 1: Core Architecture
- Days 1-2: Update GameState structure
- Days 3-4: Enhance CharacterManager and SessionManager  
- Days 5-7: Update RequestDTO and main interface agent

### Week 2: Integration and Enhancement
- Days 1-3: Update scenario generator with enhanced context extraction
- Days 4-5: Create comprehensive prompt templates
- Days 6-7: Integration testing and bug fixes

### Week 3: Testing and Refinement  
- Days 1-3: Quality testing and scenario validation
- Days 4-5: Performance optimization
- Days 6-7: Documentation and final integration testing

## Success Metrics

### Technical Success
- ✅ All 9 context categories populated when components available
- ✅ Graceful degradation with partial context (scenarios still generated)
- ✅ Context extraction under 100ms
- ✅ No breaking changes to existing functionality
- ✅ Save/load compatibility maintained

### Quality Success  
- ✅ Scenarios show clear party level consideration
- ✅ Environmental details match location context
- ✅ Narrative hooks progress appropriately
- ✅ Mechanical consistency (appropriate DCs)
- ✅ Enhanced immersion and detail quality

This comprehensive plan leverages the existing robust architecture while adding the enhanced scenario generation capabilities through systematic integration of game state, party context, and narrative tracking.