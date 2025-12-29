# Game Initialization Fix Plan - Use Existing Component Interfaces

## Problem Analysis
The `game_initialization.py` is trying to call methods that don't exist:
1. ~~`set_campaign_expectations` on CharacterManager~~ - **REMOVE ENTIRELY (not needed)**
2. `initialize_campaign_state` on GameEngine - **FIX using existing methods**

## Solution: Fix game_initialization.py to use existing methods

### 1. Remove CharacterManager Campaign Expectations (Lines 243-260)

**Current Problem**:
```python
# Update CharacterManager with campaign expectations
if config.component_status["character_manager"] == "success":
    level_range = campaign_data.get("level_range", "1-5")
    if hasattr(config.character_manager, 'set_campaign_expectations'):
        # This method doesn't exist and is not needed!
        config.character_manager.set_campaign_expectations(expectations)
```

**Fix - REMOVE ENTIRELY**:
```python
# CharacterManager doesn't need campaign expectations
# The existing get_party_snapshot(), get_party_composition() methods work fine
# Just print what we're doing for user feedback
level_range = campaign_data.get("level_range", "1-5")
print(f"   👥 CharacterManager: Ready for levels {level_range}, {difficulty} difficulty")
```

### 2. Fix GameEngine Integration (Lines 271-303)

**Current Problem**:
```python
if hasattr(config.game_engine, 'initialize_campaign_state'):
    # This method doesn't exist!
    config.game_engine.initialize_campaign_state(world_state)
```

**Fix - Use existing GameEngine methods**:
```python
# Use existing GameEngine methods to populate campaign data
config.game_engine.update_narrative_context({
    "current_scene": "Campaign Start",
    "pacing": "moderate", 
    "tension_level": "normal",
    "narrative_beats": campaign_data.get("campaign_hooks", [])[:2],
    "session_goals": [f"Begin {campaign_name}"],
    "story_hooks": campaign_data.get("campaign_hooks", [])[:3]
})

config.game_engine.update_location_context({
    "current_location": campaign_data.get("starting_location", "Tavern"),
    "location_type": "campaign_location",
    "description": campaign_data.get("story", "Welcome to your adventure!"),
    "features": [],
    "hazards": [],
    "npcs_present": [npc.get("name", "Unknown") for npc in npcs[:3]],
    "exits": [loc.get("name", "Unknown") for loc in locations[:3]]
})

config.game_engine.update_quest_context({
    "active_quests": [{"name": campaign_name, "status": "active"}],
    "completed_objectives": [],
    "pending_objectives": campaign_data.get("campaign_hooks", [])[:3],
    "quest_constraints": [f"Level range: {level_range}"],
    "time_pressure": "none" if difficulty == "Easy" else "low",
    "consequences": []
})

# Store campaign data using existing campaign flags
config.game_engine.set_campaign_flag("campaign_npcs", npcs)
config.game_engine.set_campaign_flag("campaign_locations", locations) 
config.game_engine.set_campaign_flag("campaign_encounters", encounters)
config.game_engine.set_campaign_flag("campaign_difficulty", difficulty)
config.game_engine.set_campaign_flag("campaign_theme", campaign_data.get("theme", "Fantasy Adventure"))
config.game_engine.set_campaign_flag("level_range", level_range)
```

### 3. Enhance SessionManager Integration

**Add campaign data to session state**:
```python
# After session creation, update with campaign data using existing methods
if config.component_status["session_manager"] == "success":
    try:
        campaign_session_data = {
            "campaign_name": campaign_name,
            "campaign_difficulty": difficulty,
            "campaign_theme": campaign_data.get("theme", "Fantasy Adventure"),
            "campaign_npcs": {npc.get("name", f"npc_{i}"): npc for i, npc in enumerate(npcs)},
            "campaign_locations": {loc.get("name", f"loc_{i}"): loc for i, loc in enumerate(locations)},
            "campaign_encounters": encounters,
            "campaign_level_range": level_range,
            "campaign_hooks": campaign_data.get("campaign_hooks", [])
        }
        config.session_manager.update_session_state(campaign_session_data)
        print(f"   📝 SessionManager: Campaign data stored in session")
    except Exception as e:
        print(f"   ⚠️ SessionManager: Failed to store campaign data: {e}")
```

## Implementation Changes

### 1. Remove Lines 243-260 (CharacterManager expectations)

**Replace this entire block**:
```python
# Update CharacterManager with campaign expectations
if config.component_status["character_manager"] == "success":
    level_range = campaign_data.get("level_range", "1-5")
    if hasattr(config.character_manager, 'set_campaign_expectations'):
        try:
            min_level, max_level = (int(x) for x in level_range.split("-")) if "-" in level_range else (1, 5)
            expectations = {
                "min_level": min_level,
                "max_level": max_level,
                "expected_party_size": 3,
                "campaign_difficulty": difficulty,
                "campaign_theme": campaign_data.get("theme", "Fantasy Adventure")
            }
            config.character_manager.set_campaign_expectations(expectations)
            print(f"   👥 CharacterManager: Updated for levels {level_range}, {difficulty} difficulty")
        except Exception as e:
            print(f"   👥 CharacterManager: Failed to set expectations: {e}")
```

**With this simple block**:
```python
# CharacterManager is ready - existing methods work fine for campaign
level_range = campaign_data.get("level_range", "1-5")
print(f"   👥 CharacterManager: Ready for levels {level_range}, {difficulty} difficulty")
```

### 2. Replace Lines 286-303 (GameEngine initialization)

**Replace the hasattr block with direct method calls** using existing GameEngine methods as shown above.

### 3. Add SessionManager campaign data storage

**After line 330** (after session creation), add the campaign data update.

## Expected Results

- ✅ Remove non-existent method calls that cause silent failures
- ✅ GameEngine gets full campaign data through existing interfaces  
- ✅ SessionManager stores campaign data for persistence
- ✅ CharacterManager works as-is (no campaign expectations needed)
- ✅ All components use existing interfaces - no new methods required
- ✅ Campaign NPCs, locations, encounters available for scenario generation

This approach is minimal, uses only existing component methods, and removes unnecessary complexity while ensuring campaign data flows properly.