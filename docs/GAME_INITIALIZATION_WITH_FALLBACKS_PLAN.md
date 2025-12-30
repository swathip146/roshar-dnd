# Game Initialization with Robust Fallback Options

## Overview
Create a robust game initialization system that gracefully handles component creation failures, missing data, and provides comprehensive fallback options to ensure the game always starts successfully.

## Core Principle: **Always Success with Degraded Features**
The game should NEVER fail to start. If enhanced components fail, fall back to basic functionality.

## Implementation Plan

### Phase 1: Enhanced GameInitConfig with Fallback Tracking

```python
@dataclass
class GameInitConfig:
    """Enhanced configuration with fallback status tracking"""
    # Core required fields (always present)
    collection_name: str = "dnd_documents"
    game_mode: str = "new_campaign" 
    player_name: str = "Adventurer"
    
    # Optional enhanced fields
    campaign_data: Optional[Dict[str, Any]] = None
    save_file: Optional[str] = None
    shared_document_store: Optional[Any] = None
    
    # Component instances with fallback tracking
    game_engine: Optional[Any] = None
    character_manager: Optional[Any] = None  
    session_manager: Optional[Any] = None
    policy_engine: Optional[Any] = None
    
    # NEW: Fallback status tracking
    component_status: Dict[str, str] = field(default_factory=lambda: {
        "game_engine": "not_initialized",
        "character_manager": "not_initialized", 
        "session_manager": "not_initialized",
        "policy_engine": "not_initialized",
        "document_store": "not_initialized"
    })
    
    # NEW: Fallback data for when components fail
    fallback_data: Dict[str, Any] = field(default_factory=lambda: {
        "basic_character": {
            "character_id": "player",
            "name": "Adventurer", 
            "level": 1,
            "ability_scores": {"strength": 14, "dexterity": 12, "constitution": 13, 
                             "intelligence": 11, "wisdom": 15, "charisma": 10},
            "skills": {"perception": True, "investigation": True},
            "conditions": [],
            "features": []
        },
        "basic_campaign": {
            "name": "Basic Adventure",
            "description": "A simple D&D adventure",
            "story": "You enter a tavern. The adventure begins!",
            "starting_location": "Tavern",
            "theme": "Fantasy",
            "difficulty": "Medium"
        },
        "basic_session": {
            "location": "Tavern",
            "story": "Welcome to your D&D adventure!",
            "history": [],
            "created_time": 0,
            "enhanced_features": False
        }
    })
    
    # NEW: Feature availability flags
    features_available: Dict[str, bool] = field(default_factory=lambda: {
        "enhanced_scenarios": False,
        "policy_driven_mechanics": False, 
        "comprehensive_character_tracking": False,
        "session_persistence": False,
        "rag_enhanced_content": False,
        "advanced_context_population": False
    })

    def get_status_summary(self) -> str:
        """Get human-readable status summary"""
        working_components = [k for k, v in self.component_status.items() if v == "success"]
        failed_components = [k for k, v in self.component_status.items() if v == "failed"]
        
        if len(working_components) == len(self.component_status):
            return "✅ All components operational - Full enhanced experience available"
        elif len(working_components) >= 2:
            return f"⚠️ Partial functionality - {len(working_components)}/{len(self.component_status)} components working"
        else:
            return f"🔧 Basic mode - {len(failed_components)} components failed, using fallback systems"
```

### Phase 2: Robust Component Creation with Fallbacks

```python
class GameInitializationSystem:
    def create_game_components_with_fallbacks(self, config: GameInitConfig) -> GameInitConfig:
        """Create components with comprehensive fallback handling"""
        
        print(f"🔧 Creating game components with fallback protection...")
        
        # 1. PolicyEngine - Critical for enhanced features
        config = self._create_policy_engine_with_fallback(config)
        
        # 2. CharacterManager - Important for party tracking
        config = self._create_character_manager_with_fallback(config)
        
        # 3. SessionManager - Important for save/load
        config = self._create_session_manager_with_fallback(config)
        
        # 4. GameEngine - Advanced features
        config = self._create_game_engine_with_fallback(config)
        
        # 5. Initialize game state with available components
        config = self._initialize_game_state_with_fallbacks(config)
        
        # 6. Update feature availability based on successful components
        config = self._update_feature_availability(config)
        
        # 7. Show final status
        print(f"\n{config.get_status_summary()}")
        self._show_available_features(config)
        
        return config
    
    def _create_policy_engine_with_fallback(self, config: GameInitConfig) -> GameInitConfig:
        """Create PolicyEngine with fallback to basic policy system"""
        
        try:
            from components.policy import PolicyEngine, PolicyProfile
            config.policy_engine = PolicyEngine(PolicyProfile.HOUSE)
            config.component_status["policy_engine"] = "success"
            print(f"   ⚖️ PolicyEngine: ✅ Enhanced policy system active")
            
        except Exception as e:
            print(f"   ⚖️ PolicyEngine: ❌ Failed ({e})")
            config.component_status["policy_engine"] = "failed"
            
            # Fallback: Create basic policy object
            config.policy_engine = self._create_basic_policy_fallback()
            print(f"   ⚖️ PolicyEngine: 🔧 Using basic fallback policy system")
        
        return config
    
    def _create_character_manager_with_fallback(self, config: GameInitConfig) -> GameInitConfig:
        """Create CharacterManager with fallback to basic character tracking"""
        
        try:
            from components.character_manager import CharacterManager
            config.character_manager = CharacterManager()
            config.component_status["character_manager"] = "success"
            print(f"   👥 CharacterManager: ✅ Enhanced character system active")
            
        except Exception as e:
            print(f"   👥 CharacterManager: ❌ Failed ({e})")
            config.component_status["character_manager"] = "failed"
            
            # Fallback: Create basic character tracker
            config.character_manager = self._create_basic_character_fallback()
            print(f"   👥 CharacterManager: 🔧 Using basic fallback character tracking")
        
        return config
    
    def _create_session_manager_with_fallback(self, config: GameInitConfig) -> GameInitConfig:
        """Create SessionManager with fallback to basic session handling"""
        
        try:
            from components.session_manager import create_session_manager
            config.session_manager = create_session_manager(save_directory="game_saves")
            config.component_status["session_manager"] = "success"
            print(f"   📝 SessionManager: ✅ Enhanced session system active")
            
        except Exception as e:
            print(f"   📝 SessionManager: ❌ Failed ({e})")
            config.component_status["session_manager"] = "failed"
            
            # Fallback: Create basic session handler
            config.session_manager = self._create_basic_session_fallback()
            print(f"   📝 SessionManager: 🔧 Using basic fallback session handling")
        
        return config
    
    def _create_game_engine_with_fallback(self, config: GameInitConfig) -> GameInitConfig:
        """Create GameEngine with fallback to basic game state"""
        
        try:
            from components.game_engine import GameEngine
            
            # Try to create with available components
            kwargs = {}
            if config.component_status["policy_engine"] == "success":
                kwargs["policy_engine"] = config.policy_engine
            if config.component_status["character_manager"] == "success":  
                kwargs["character_manager"] = config.character_manager
                
            config.game_engine = GameEngine(**kwargs)
            config.component_status["game_engine"] = "success"
            print(f"   🎮 GameEngine: ✅ Enhanced game engine active")
            
        except Exception as e:
            print(f"   🎮 GameEngine: ❌ Failed ({e})")
            config.component_status["game_engine"] = "failed"
            
            # Fallback: Create basic game state container
            config.game_engine = self._create_basic_game_engine_fallback()
            print(f"   🎮 GameEngine: 🔧 Using basic fallback game state")
        
        return config

    def _initialize_game_state_with_fallbacks(self, config: GameInitConfig) -> GameInitConfig:
        """Initialize game state using available components with fallbacks"""
        
        if config.game_mode == "load_saved":
            return self._load_saved_with_fallbacks(config)
        else:
            return self._initialize_new_campaign_with_fallbacks(config)
    
    def _load_saved_with_fallbacks(self, config: GameInitConfig) -> GameInitConfig:
        """Load saved game with comprehensive fallback handling"""
        
        print(f"📁 Loading saved game with fallback protection...")
        
        if not config.save_file:
            print(f"   ⚠️ No save file specified, falling back to new campaign")
            config.game_mode = "new_campaign"
            return self._initialize_new_campaign_with_fallbacks(config)
        
        # Try to load with SessionManager if available
        if config.component_status["session_manager"] == "success":
            try:
                result = config.session_manager.load_session(config.save_file)
                if result["success"]:
                    self._restore_components_from_save(config, result["result"])
                    print(f"   ✅ Saved game loaded successfully")
                    return config
                else:
                    print(f"   ❌ SessionManager load failed: {result.get('message', 'Unknown error')}")
            except Exception as e:
                print(f"   ❌ SessionManager load exception: {e}")
        
        # Fallback: Try basic file loading
        try:
            import json
            import os
            
            save_path = os.path.join("game_saves", config.save_file)
            if not save_path.endswith(".json"):
                save_path += ".json"
                
            if os.path.exists(save_path):
                with open(save_path, 'r') as f:
                    save_data = json.load(f)
                
                self._restore_basic_state_from_save(config, save_data)
                print(f"   🔧 Basic save data loaded from file")
                return config
                
        except Exception as e:
            print(f"   ❌ Basic file load failed: {e}")
        
        # Ultimate fallback: New campaign
        print(f"   🆕 All load methods failed, starting new campaign instead")
        config.game_mode = "new_campaign"
        return self._initialize_new_campaign_with_fallbacks(config)
    
    def _initialize_new_campaign_with_fallbacks(self, config: GameInitConfig) -> GameInitConfig:
        """Initialize new campaign with fallback data"""
        
        print(f"🆕 Initializing new campaign with fallback protection...")
        
        # Use campaign data or fallback
        campaign_data = config.campaign_data or config.fallback_data["basic_campaign"]
        
        # Create initial state using best available method
        if config.component_status["session_manager"] == "success":
            try:
                initial_state = {
                    "location": campaign_data.get("starting_location", "Tavern"),
                    "story": campaign_data.get("story", "Welcome to your adventure!"),
                    "campaign_info": campaign_data,
                    "created_time": time.time(),
                    "enhanced_features": any(s == "success" for s in config.component_status.values()),
                    "document_collection": config.collection_name
                }
                
                result = config.session_manager.create_new_session(
                    player_name=config.player_name,
                    initial_state=initial_state
                )
                
                if result["success"]:
                    print(f"   📝 Enhanced session created")
                else:
                    print(f"   ⚠️ Session creation failed, using fallback: {result.get('message')}")
                    self._create_fallback_session_state(config)
                    
            except Exception as e:
                print(f"   ❌ Session creation failed: {e}")
                self._create_fallback_session_state(config)
        else:
            self._create_fallback_session_state(config)
        
        # Initialize components with available data
        self._initialize_components_for_new_campaign(config, campaign_data)
        
        return config

    def _create_fallback_session_state(self, config: GameInitConfig):
        """Create basic session state when SessionManager fails"""
        
        # Store basic session data in config for orchestrator to use
        config.fallback_data["current_session"] = {
            "session_id": f"basic_session_{int(time.time())}",
            "player_name": config.player_name,
            "session_active": True,
            "game_state": config.fallback_data["basic_session"].copy()
        }
        print(f"   🔧 Basic session state created")

    # Fallback component creators
    def _create_basic_policy_fallback(self):
        """Create basic policy object when PolicyEngine fails"""
        
        class BasicPolicyFallback:
            def get_difficulty_policy(self, party_context):
                return {
                    'difficulty_target': 'medium',
                    'dc_policy': {'easy': 8, 'medium': 12, 'hard': 16, 'very_hard': 20}
                }
            
            def get_encounter_budget(self, party_context):
                return {'xp_budgets': {'easy': 250, 'medium': 500, 'hard': 750, 'deadly': 1100}}
            
            def get_choice_count_policy(self, confidence, complexity="medium"):
                return {'choice_count': 3}
        
        return BasicPolicyFallback()
    
    def _create_basic_character_fallback(self):
        """Create basic character tracker when CharacterManager fails"""
        
        class BasicCharacterFallback:
            def __init__(self):
                self.characters = {}
            
            def add_character(self, char_data):
                char_id = char_data.get("character_id", "player")
                self.characters[char_id] = char_data
                return char_id
            
            def get_party_snapshot(self):
                return {
                    'avg_level': 1,
                    'party_size': len(self.characters),
                    'party_roles': {'striker': 1},
                    'hp_state': {'average_hp_percent': 100},
                    'resources': {'spell_slots_remaining': 'none'},
                    'stealth_profile': 'normal'
                }
        
        return BasicCharacterFallback()
    
    def _create_basic_session_fallback(self):
        """Create basic session handler when SessionManager fails"""
        
        class BasicSessionFallback:
            def __init__(self):
                self.session_data = None
            
            def get_session_state(self):
                return self.session_data or {"session_active": False}
            
            def create_new_session(self, player_name, initial_state):
                self.session_data = {
                    "session_id": f"basic_{int(time.time())}",
                    "player_name": player_name,
                    "session_active": True,
                    "game_state": initial_state
                }
                return {"success": True}
            
            def save_session(self, **kwargs):
                return {"success": False, "message": "Basic session handler cannot save"}
        
        return BasicSessionFallback()
    
    def _create_basic_game_engine_fallback(self):
        """Create basic game state container when GameEngine fails"""
        
        class BasicGameEngineFallback:
            def __init__(self):
                self.game_state = {"characters": {}, "environment": {}, "campaign_flags": {}}
            
            def export_game_state(self):
                return self.game_state
            
            def add_character(self, char_data):
                char_id = char_data.get("character_id", "player")
                self.game_state["characters"][char_id] = char_data
                return char_id
            
            def update_environment(self, env_data):
                self.game_state["environment"].update(env_data)
            
            def set_campaign_flag(self, flag, value):
                self.game_state["campaign_flags"][flag] = value
        
        return BasicGameEngineFallback()

    def _update_feature_availability(self, config: GameInitConfig) -> GameInitConfig:
        """Update feature flags based on component success"""
        
        config.features_available.update({
            "enhanced_scenarios": config.component_status["game_engine"] == "success",
            "policy_driven_mechanics": config.component_status["policy_engine"] == "success",
            "comprehensive_character_tracking": config.component_status["character_manager"] == "success", 
            "session_persistence": config.component_status["session_manager"] == "success",
            "rag_enhanced_content": config.shared_document_store is not None,
            "advanced_context_population": sum(1 for s in config.component_status.values() if s == "success") >= 3
        })
        
        return config
    
    def _show_available_features(self, config: GameInitConfig):
        """Show user what features are available"""
        
        print(f"\n🎯 Available Features:")
        
        available_features = [k for k, v in config.features_available.items() if v]
        unavailable_features = [k for k, v in config.features_available.items() if not v]
        
        for feature in available_features:
            feature_name = feature.replace('_', ' ').title()
            print(f"   ✅ {feature_name}")
        
        if unavailable_features:
            print(f"\n🔧 Features Using Fallbacks:")
            for feature in unavailable_features:
                feature_name = feature.replace('_', ' ').title()  
                print(f"   🔧 {feature_name} (Basic Mode)")
```

### Phase 3: Orchestrator Fallback Integration

Update the orchestrator creation to handle component failures gracefully:

```python
# In haystack_dnd_game.py
def __init__(self, config: GameInitConfig = None):
    """Initialize with comprehensive fallback support"""
    
    if config is None:
        config = initialize_enhanced_dnd_game()
    
    self.config = config
    
    # Store component references (may be fallback implementations)
    self.game_engine = config.game_engine
    self.character_manager = config.character_manager  
    self.session_manager = config.session_manager
    self.policy_engine = config.policy_engine
    
    # Create orchestrator with whatever components are available
    # The orchestrator already handles None components gracefully
    self.orchestrator = create_full_haystack_orchestrator(
        collection_name=config.collection_name,
        shared_document_store=config.shared_document_store,
        game_engine=config.game_engine if config.component_status["game_engine"] == "success" else None,
        character_manager=config.character_manager if config.component_status["character_manager"] == "success" else None,
        session_manager=config.session_manager if config.component_status["session_manager"] == "success" else None,
        policy_engine=config.policy_engine if config.component_status["policy_engine"] == "success" else None
    )
    
    print(f"🎮 Game initialized: {config.get_status_summary()}")
```

## Key Benefits

✅ **Never Fails to Start**: Game always launches, even with all components failed  
✅ **Graceful Degradation**: Each component failure reduces features but doesn't break the game  
✅ **Clear Status Reporting**: Users know exactly what features are available  
✅ **Robust Save/Load**: Multiple fallback layers for loading saved games  
✅ **Component Isolation**: Failed components don't affect working ones  
✅ **Basic Functionality Preserved**: Core game mechanics work even in fallback mode  

## Fallback Hierarchy

1. **Full Enhanced Mode**: All components working - complete feature set
2. **Partial Enhanced Mode**: Some components working - reduced but enhanced features  
3. **Basic Enhanced Mode**: Orchestrator + fallback components - basic enhanced features
4. **Compatibility Mode**: Pure fallback implementations - basic D&D game functionality

This ensures the game provides the best possible experience given the available components while never failing to start.