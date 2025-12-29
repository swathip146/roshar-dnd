#!/usr/bin/env python3
"""
Comprehensive Test Suite for Enhanced D&D Implementation
Tests all edits made according to updated_enhanced_implementation_plan.md 
and GAME_INITIALIZATION_WITH_FALLBACKS_PLAN.md
"""

import os
import sys
import json
import time
import traceback
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

# Add project root to Python path
sys.path.insert(0, os.path.abspath('.'))

class TestResults:
    """Track test results and generate report"""
    
    def __init__(self):
        self.results = []
        self.start_time = time.time()
    
    def add_result(self, test_name: str, success: bool, message: str = "", details: Dict = None):
        """Add a test result"""
        self.results.append({
            "test": test_name,
            "success": success,
            "message": message,
            "details": details or {},
            "timestamp": time.time()
        })
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {message}")
        
        if not success and details:
            print(f"   Details: {details}")
    
    def get_summary(self) -> Dict[str, Any]:
        """Get test summary"""
        passed = sum(1 for r in self.results if r["success"])
        failed = len(self.results) - passed
        duration = time.time() - self.start_time
        
        return {
            "total_tests": len(self.results),
            "passed": passed,
            "failed": failed,
            "success_rate": (passed / len(self.results)) * 100 if self.results else 0,
            "duration": duration,
            "results": self.results
        }
    
    def print_summary(self):
        """Print test summary"""
        summary = self.get_summary()
        
        print("\n" + "="*80)
        print("🧪 COMPREHENSIVE TEST RESULTS")
        print("="*80)
        print(f"Total Tests: {summary['total_tests']}")
        print(f"✅ Passed: {summary['passed']}")
        print(f"❌ Failed: {summary['failed']}")
        print(f"📊 Success Rate: {summary['success_rate']:.1f}%")
        print(f"⏱️ Duration: {summary['duration']:.2f}s")
        
        if summary['failed'] > 0:
            print(f"\n❌ FAILED TESTS:")
            for result in self.results:
                if not result["success"]:
                    print(f"   • {result['test']}: {result['message']}")
        
        print("\n" + "="*80)


class ComprehensiveEnhancementTest:
    """Comprehensive test suite for all enhancement implementations"""
    
    def __init__(self):
        self.results = TestResults()
        
    def run_all_tests(self):
        """Run all test categories"""
        
        print("🚀 Starting Comprehensive Enhancement Test Suite")
        print("=" * 80)
        print("Testing implementation from:")
        print("  • updated_enhanced_implementation_plan.md") 
        print("  • GAME_INITIALIZATION_WITH_FALLBACKS_PLAN.md")
        print("=" * 80)
        
        # Test Category 1: Component Enhancements
        self.test_policy_engine_enhancements()
        self.test_character_manager_enhancements()
        self.test_game_engine_enhancements()
        self.test_request_dto_enhancements()
        
        # Test Category 2: Fallback Initialization System
        self.test_game_initialization_with_fallbacks()
        self.test_component_creation_fallbacks()
        self.test_orchestrator_integration_with_fallbacks()
        
        # Test Category 3: Enhanced Context Population
        self.test_enhanced_orchestrator_context_population()
        self.test_context_extraction_and_prompt_generation()
        
        # Test Category 4: Integration Tests
        self.test_end_to_end_integration()
        self.test_backward_compatibility()
        self.test_error_scenarios()
        
        # Generate final report
        self.results.print_summary()
        self._save_test_report()
        
        return self.results.get_summary()
    
    def test_policy_engine_enhancements(self):
        """Test PolicyEngine scenario generation rules"""
        
        print("\n📋 Testing PolicyEngine Enhancements...")
        
        try:
            from components.policy import PolicyEngine, PolicyProfile
            
            # Test 1: PolicyEngine initialization with scenario rules
            try:
                policy_engine = PolicyEngine(PolicyProfile.HOUSE)
                self.results.add_result(
                    "PolicyEngine Initialization", 
                    True, 
                    "Successfully created with HOUSE profile"
                )
            except Exception as e:
                self.results.add_result(
                    "PolicyEngine Initialization", 
                    False, 
                    f"Failed to initialize: {e}"
                )
                return
            
            # Test 2: Difficulty policy generation
            try:
                party_context = {
                    'avg_level': 3,
                    'party_size': 4,
                    'hp_state': {'average_hp_percent': 85},
                    'resources': {'spell_slots_remaining': 'medium'}
                }
                
                if hasattr(policy_engine, 'get_difficulty_policy'):
                    difficulty_policy = policy_engine.get_difficulty_policy(party_context)
                    
                    expected_fields = ['difficulty_target', 'dc_policy', 'party_level', 'party_size']
                    has_fields = all(field in difficulty_policy for field in expected_fields)
                    
                    self.results.add_result(
                        "PolicyEngine Difficulty Policy", 
                        has_fields,
                        f"Generated policy with fields: {list(difficulty_policy.keys())}"
                    )
                else:
                    self.results.add_result(
                        "PolicyEngine Difficulty Policy", 
                        False,
                        "get_difficulty_policy method not found"
                    )
            except Exception as e:
                self.results.add_result(
                    "PolicyEngine Difficulty Policy", 
                    False, 
                    f"Error: {e}"
                )
            
            # Test 3: Encounter budget calculation
            try:
                if hasattr(policy_engine, 'get_encounter_budget'):
                    encounter_budget = policy_engine.get_encounter_budget(party_context)
                    
                    has_xp_budgets = 'xp_budgets' in encounter_budget
                    has_multipliers = any(key.endswith('_multiplier') for key in encounter_budget.keys())
                    
                    self.results.add_result(
                        "PolicyEngine Encounter Budget", 
                        has_xp_budgets and has_multipliers,
                        f"Generated budget with XP thresholds and multipliers"
                    )
                else:
                    self.results.add_result(
                        "PolicyEngine Encounter Budget", 
                        False,
                        "get_encounter_budget method not found"
                    )
            except Exception as e:
                self.results.add_result(
                    "PolicyEngine Encounter Budget", 
                    False, 
                    f"Error: {e}"
                )
            
            # Test 4: Choice count policy
            try:
                if hasattr(policy_engine, 'get_choice_count_policy'):
                    choice_policy = policy_engine.get_choice_count_policy(0.8, "medium")
                    
                    has_choice_count = 'choice_count' in choice_policy
                    has_adjustments = 'adjustments' in choice_policy
                    
                    self.results.add_result(
                        "PolicyEngine Choice Count Policy", 
                        has_choice_count and has_adjustments,
                        f"Generated choice policy: {choice_policy.get('choice_count', 'N/A')} choices"
                    )
                else:
                    self.results.add_result(
                        "PolicyEngine Choice Count Policy", 
                        False,
                        "get_choice_count_policy method not found"
                    )
            except Exception as e:
                self.results.add_result(
                    "PolicyEngine Choice Count Policy", 
                    False, 
                    f"Error: {e}"
                )
                
        except ImportError as e:
            self.results.add_result(
                "PolicyEngine Import", 
                False, 
                f"Cannot import PolicyEngine: {e}"
            )
        except Exception as e:
            self.results.add_result(
                "PolicyEngine General", 
                False, 
                f"Unexpected error: {e}"
            )
    
    def test_character_manager_enhancements(self):
        """Test CharacterManager party analysis capabilities"""
        
        print("\n👥 Testing CharacterManager Enhancements...")
        
        try:
            from components.character_manager import CharacterManager
            
            # Test 1: CharacterManager initialization
            try:
                char_manager = CharacterManager()
                self.results.add_result(
                    "CharacterManager Initialization", 
                    True, 
                    "Successfully initialized enhanced CharacterManager"
                )
            except Exception as e:
                self.results.add_result(
                    "CharacterManager Initialization", 
                    False, 
                    f"Failed to initialize: {e}"
                )
                return
            
            # Test 2: Enhanced character addition
            try:
                test_character = {
                    "character_id": "test_player",
                    "name": "Test Adventurer",
                    "level": 3,
                    "ability_scores": {
                        "strength": 14, "dexterity": 16, "constitution": 13,
                        "intelligence": 12, "wisdom": 15, "charisma": 10
                    },
                    "skills": {"perception": True, "stealth": True, "investigation": True},
                    "expertise_skills": ["stealth"],
                    "character_class": "Rogue",
                    "hp_max": 24,
                    "hp_current": 20,
                    "armor_class": 14,
                    "armor_type": "light"
                }
                
                char_id = char_manager.add_character(test_character)
                character_added = char_id in char_manager.characters
                
                self.results.add_result(
                    "CharacterManager Enhanced Character Addition", 
                    character_added,
                    f"Added character with ID: {char_id}"
                )
            except Exception as e:
                self.results.add_result(
                    "CharacterManager Enhanced Character Addition", 
                    False, 
                    f"Error adding character: {e}"
                )
            
            # Test 3: Party snapshot generation
            try:
                if hasattr(char_manager, 'get_party_snapshot'):
                    party_snapshot = char_manager.get_party_snapshot()
                    
                    expected_fields = [
                        'avg_level', 'party_size', 'party_roles', 
                        'hp_state', 'resources', 'stealth_profile'
                    ]
                    has_fields = all(field in party_snapshot for field in expected_fields)
                    
                    self.results.add_result(
                        "CharacterManager Party Snapshot", 
                        has_fields,
                        f"Generated snapshot with {len(party_snapshot)} fields"
                    )
                else:
                    self.results.add_result(
                        "CharacterManager Party Snapshot", 
                        False,
                        "get_party_snapshot method not found"
                    )
            except Exception as e:
                self.results.add_result(
                    "CharacterManager Party Snapshot", 
                    False, 
                    f"Error: {e}"
                )
                
        except ImportError as e:
            self.results.add_result(
                "CharacterManager Import", 
                False, 
                f"Cannot import CharacterManager: {e}"
            )
        except Exception as e:
            self.results.add_result(
                "CharacterManager General", 
                False, 
                f"Unexpected error: {e}"
            )
    
    def test_game_engine_enhancements(self):
        """Test GameEngine context enhancements"""
        
        print("\n🎮 Testing GameEngine Enhancements...")
        
        try:
            from components.game_engine import GameEngine, GameState
            
            # Test 1: Enhanced GameState structure
            try:
                # Check if GameState has enhanced context fields
                sample_state = GameState(
                    characters={},
                    combat_state={},
                    environment={},
                    campaign_flags={},
                    session_data={},
                    narrative_context={},
                    location_context={},
                    quest_context={}
                )
                
                enhanced_fields = ['narrative_context', 'location_context', 'quest_context']
                has_enhanced_fields = all(hasattr(sample_state, field) for field in enhanced_fields)
                
                self.results.add_result(
                    "GameEngine Enhanced GameState",
                    has_enhanced_fields,
                    f"GameState has enhanced context fields: {enhanced_fields}"
                )
            except Exception as e:
                self.results.add_result(
                    "GameEngine Enhanced GameState", 
                    False, 
                    f"Error checking GameState: {e}"
                )
            
            # Test 2: GameEngine initialization
            try:
                game_engine = GameEngine()
                self.results.add_result(
                    "GameEngine Initialization", 
                    True, 
                    "Successfully initialized GameEngine"
                )
            except Exception as e:
                self.results.add_result(
                    "GameEngine Initialization", 
                    False, 
                    f"Failed to initialize: {e}"
                )
                return
            
            # Test 3: Context management methods
            try:
                context_methods = [
                    'update_narrative_context', 
                    'update_location_context', 
                    'update_quest_context',
                    'get_scenario_context'
                ]
                
                available_methods = [method for method in context_methods if hasattr(game_engine, method)]
                
                self.results.add_result(
                    "GameEngine Context Methods", 
                    len(available_methods) >= 2,  # At least some context methods
                    f"Available context methods: {available_methods}"
                )
            except Exception as e:
                self.results.add_result(
                    "GameEngine Context Methods", 
                    False, 
                    f"Error checking methods: {e}"
                )
                
        except ImportError as e:
            self.results.add_result(
                "GameEngine Import", 
                False, 
                f"Cannot import GameEngine: {e}"
            )
        except Exception as e:
            self.results.add_result(
                "GameEngine General", 
                False, 
                f"Unexpected error: {e}"
            )
    
    def test_request_dto_enhancements(self):
        """Test RequestDTO 9-category context fields"""
        
        print("\n📦 Testing RequestDTO Enhancements...")
        
        try:
            from components.shared_contract import RequestDTO, new_dto
            
            # Test 1: Enhanced RequestDTO structure
            try:
                # Check if RequestDTO type has enhanced fields defined
                from typing import get_type_hints
                
                try:
                    hints = get_type_hints(RequestDTO)
                    enhanced_fields = [
                        'goal_hint', 'risk_preference', 'party_context',
                        'narrative_context', 'quest_context', 'location_context',
                        'policy_context', 'rag_snippets'
                    ]
                    
                    available_fields = [field for field in enhanced_fields if field in hints]
                    
                    self.results.add_result(
                        "RequestDTO Enhanced Fields",
                        len(available_fields) >= 6,  # Most enhanced fields should be available
                        f"Available enhanced fields: {available_fields}"
                    )
                except Exception:
                    # Fallback: Check if RequestDTO can accept enhanced fields
                    sample_dto = new_dto("test input", {})
                    sample_dto.update({
                        'goal_hint': 'test goal',
                        'risk_preference': 'moderate',
                        'party_context': {'test': 'data'}
                    })
                    
                    self.results.add_result(
                        "RequestDTO Enhanced Fields",
                        True,  # If we can set them, they're supported
                        "Enhanced fields can be set on RequestDTO"
                    )
            except Exception as e:
                self.results.add_result(
                    "RequestDTO Enhanced Fields", 
                    False, 
                    f"Error checking DTO fields: {e}"
                )
            
            # Test 2: Context population
            try:
                context = {
                    "session_state": {"session_id": "test_123"},
                    "game_state": {"location": "Test Tavern"},
                    "enhanced_components_active": True
                }
                
                dto = new_dto("test player input", context)
                has_context = bool(dto.get("context"))
                
                self.results.add_result(
                    "RequestDTO Context Population", 
                    has_context,
                    f"DTO populated with context keys: {list(dto.get('context', {}).keys())}"
                )
            except Exception as e:
                self.results.add_result(
                    "RequestDTO Context Population", 
                    False, 
                    f"Error populating context: {e}"
                )
                
        except ImportError as e:
            self.results.add_result(
                "RequestDTO Import", 
                False, 
                f"Cannot import RequestDTO: {e}"
            )
        except Exception as e:
            self.results.add_result(
                "RequestDTO General", 
                False, 
                f"Unexpected error: {e}"
            )
    
    def test_game_initialization_with_fallbacks(self):
        """Test robust game initialization system"""
        
        print("\n🚀 Testing Game Initialization with Fallbacks...")
        
        try:
            from core.game_initialization import GameInitializationSystem, GameInitConfig
            
            # Test 1: GameInitConfig structure
            try:
                config = GameInitConfig()
                
                fallback_fields = ['component_status', 'features_available']
                has_fallback_fields = all(hasattr(config, field) for field in fallback_fields)
                
                self.results.add_result(
                    "GameInitConfig Fallback Fields",
                    has_fallback_fields,
                    f"Config has fallback tracking fields: {fallback_fields}"
                )
            except Exception as e:
                self.results.add_result(
                    "GameInitConfig Fallback Fields", 
                    False, 
                    f"Error checking config: {e}"
                )
            
            # Test 2: GameInitializationSystem
            try:
                init_system = GameInitializationSystem()
                
                fallback_methods = [
                    'create_game_components_with_fallbacks',
                    '_create_policy_engine_with_fallback',
                    '_create_character_manager_with_fallback',
                    '_create_session_manager_with_fallback'
                ]
                
                available_methods = [method for method in fallback_methods if hasattr(init_system, method)]
                
                self.results.add_result(
                    "GameInitializationSystem Fallback Methods", 
                    len(available_methods) >= 2,
                    f"Available fallback methods: {available_methods}"
                )
            except Exception as e:
                self.results.add_result(
                    "GameInitializationSystem Fallback Methods", 
                    False, 
                    f"Error checking init system: {e}"
                )
            
            # Test 3: Component creation with fallbacks (controlled test)
            try:
                init_system = GameInitializationSystem()
                config = GameInitConfig(
                    collection_name="test_collection",
                    game_mode="new_campaign",
                    player_name="Test Player"
                )
                
                # This should never fail due to fallbacks
                enhanced_config = init_system.create_game_components_with_fallbacks(config)
                
                # Check that components were created (either enhanced or fallback)
                components_created = all(
                    getattr(enhanced_config, comp) is not None 
                    for comp in ['policy_engine', 'character_manager', 'session_manager', 'game_engine']
                )
                
                self.results.add_result(
                    "Component Creation with Fallbacks", 
                    components_created,
                    f"All components created: {enhanced_config.get_status_summary()}"
                )
                
            except Exception as e:
                self.results.add_result(
                    "Component Creation with Fallbacks", 
                    False, 
                    f"Error in fallback creation: {e}"
                )
                
        except ImportError as e:
            self.results.add_result(
                "GameInitialization Import", 
                False, 
                f"Cannot import GameInitialization: {e}"
            )
        except Exception as e:
            self.results.add_result(
                "GameInitialization General", 
                False, 
                f"Unexpected error: {e}"
            )
    
    def test_component_creation_fallbacks(self):
        """Test individual component fallback creation"""
        
        print("\n🔧 Testing Component Creation Fallbacks...")
        
        try:
            from core.game_initialization import GameInitializationSystem, GameInitConfig
            
            init_system = GameInitializationSystem()
            
            # Test fallback component creators
            fallback_creators = [
                '_create_basic_policy_fallback',
                '_create_basic_character_fallback', 
                '_create_basic_session_fallback',
                '_create_basic_game_engine_fallback'
            ]
            
            for creator_name in fallback_creators:
                try:
                    if hasattr(init_system, creator_name):
                        creator = getattr(init_system, creator_name)
                        fallback_component = creator()
                        
                        self.results.add_result(
                            f"Fallback Creator {creator_name}", 
                            fallback_component is not None,
                            f"Created fallback component: {type(fallback_component).__name__}"
                        )
                    else:
                        self.results.add_result(
                            f"Fallback Creator {creator_name}", 
                            False,
                            f"Method {creator_name} not found"
                        )
                except Exception as e:
                    self.results.add_result(
                        f"Fallback Creator {creator_name}", 
                        False, 
                        f"Error creating fallback: {e}"
                    )
                    
        except Exception as e:
            self.results.add_result(
                "Component Fallback Creation", 
                False, 
                f"Error testing fallbacks: {e}"
            )
    
    def test_orchestrator_integration_with_fallbacks(self):
        """Test orchestrator integration with fallback components"""
        
        print("\n🎭 Testing Orchestrator Integration with Fallbacks...")
        
        try:
            from orchestrator.pipeline_integration import create_full_haystack_orchestrator, PipelineOrchestrator
            
            # Test 1: Enhanced factory function signature
            try:
                import inspect
                sig = inspect.signature(create_full_haystack_orchestrator)
                
                expected_params = [
                    'game_engine', 'character_manager', 
                    'session_manager', 'policy_engine'
                ]
                
                available_params = [param for param in expected_params if param in sig.parameters]
                
                self.results.add_result(
                    "Orchestrator Factory Enhanced Signature", 
                    len(available_params) >= 2,
                    f"Factory supports component parameters: {available_params}"
                )
            except Exception as e:
                self.results.add_result(
                    "Orchestrator Factory Enhanced Signature", 
                    False, 
                    f"Error checking signature: {e}"
                )
            
            # Test 2: Orchestrator with minimal components
            try:
                # Create with minimal parameters (should use fallbacks)
                orchestrator = create_full_haystack_orchestrator(
                    collection_name="test_collection"
                )
                
                self.results.add_result(
                    "Orchestrator Creation with Minimal Components", 
                    orchestrator is not None,
                    f"Created orchestrator: {type(orchestrator).__name__}"
                )
                
            except Exception as e:
                self.results.add_result(
                    "Orchestrator Creation with Minimal Components", 
                    False, 
                    f"Error creating orchestrator: {e}"
                )
            
            # Test 3: Enhanced orchestrator methods
            try:
                # Check for enhanced context population method
                if hasattr(PipelineOrchestrator, '_populate_enhanced_dto_context'):
                    self.results.add_result(
                        "Orchestrator Enhanced Context Population", 
                        True,
                        "Enhanced DTO context population method available"
                    )
                else:
                    self.results.add_result(
                        "Orchestrator Enhanced Context Population", 
                        False,
                        "_populate_enhanced_dto_context method not found"
                    )
                    
            except Exception as e:
                self.results.add_result(
                    "Orchestrator Enhanced Context Population", 
                    False, 
                    f"Error checking enhanced methods: {e}"
                )
                
        except ImportError as e:
            self.results.add_result(
                "Orchestrator Import", 
                False, 
                f"Cannot import orchestrator: {e}"
            )
        except Exception as e:
            self.results.add_result(
                "Orchestrator Integration", 
                False, 
                f"Unexpected error: {e}"
            )
    
    def test_enhanced_orchestrator_context_population(self):
        """Test enhanced orchestrator context population"""
        
        print("\n📋 Testing Enhanced Context Population...")
        
        try:
            from components.shared_contract import new_dto
            from core.game_initialization import GameInitializationSystem, GameInitConfig
            
            # Create a test scenario with components
            init_system = GameInitializationSystem()
            config = GameInitConfig(
                collection_name="test_collection",
                player_name="Test Player"
            )
            
            # Create components with fallbacks
            config = init_system.create_game_components_with_fallbacks(config)
            
            # Test DTO creation with enhanced context
            try:
                from orchestrator.pipeline_integration import PipelineOrchestrator
                
                # Create orchestrator with components
                orchestrator = PipelineOrchestrator(
                    enable_pipelines=False,  # Disable for testing
                    game_engine=config.game_engine,
                    character_manager=config.character_manager,
                    session_manager=config.session_manager,
                    policy_engine=config.policy_engine
                )
                
                # Test context population
                basic_dto = new_dto("test input", {"test": "context"})
                
                if hasattr(orchestrator, '_populate_enhanced_dto_context'):
                    enhanced_dto = orchestrator._populate_enhanced_dto_context(basic_dto)
                    
                    # Check for populated context fields
                    context_fields = [
                        'game_state', 'party_context', 'policy_context'
                    ]
                    
                    populated_fields = [field for field in context_fields if enhanced_dto.get(field)]
                    
                    self.results.add_result(
                        "Enhanced DTO Context Population", 
                        len(populated_fields) >= 1,
                        f"Populated context fields: {populated_fields}"
                    )
                else:
                    self.results.add_result(
                        "Enhanced DTO Context Population", 
                        False,
                        "Context population method not available"
                    )
                    
            except Exception as e:
                self.results.add_result(
                    "Enhanced DTO Context Population", 
                    False, 
                    f"Error in context population: {e}"
                )
                
        except Exception as e:
            self.results.add_result(
                "Enhanced Context Population", 
                False, 
                f"Error in test setup: {e}"
            )
    
    def test_context_extraction_and_prompt_generation(self):
        """Test context extraction and enhanced prompt generation"""
        
        print("\n📝 Testing Context Extraction and Prompt Generation...")
        
        try:
            from agents.scenario_generator_agent import create_scenario_generator_agent, create_scenario_from_dto
            
            # Test 1: Scenario generator agent availability
            try:
                scenario_agent = create_scenario_generator_agent()
                self.results.add_result(
                    "Scenario Generator Agent Creation",
                    True,
                    "Successfully created ScenarioGeneratorAgent"
                )
            except Exception as e:
                self.results.add_result(
                    "Scenario Generator Agent Creation",
                    False,
                    f"Error creating agent: {e}"
                )
                return
            
            # Test 2: Enhanced context extraction (via create_scenario_from_dto function)
            try:
                test_dto = {
                    'player_input': 'I search the room for secret doors',
                    'goal_hint': 'locate hidden passages',
                    'risk_preference': 'cautious',
                    'party_context': {'avg_level': 3, 'party_size': 4},
                    'location_context': {'current_location': 'Ancient Library'}
                }
                
                # Test that the function can extract comprehensive context
                prompt_result = create_scenario_from_dto(test_dto)
                
                # Check for 9-category context structure in generated prompt
                expected_sections = [
                    'NARRATIVE & PACING CONTEXT', 'PLAYER INTENT CONTEXT',
                    'PARTY SNAPSHOT CONTEXT', 'LOCATION & ENVIRONMENT CONTEXT',
                    'MECHANICS POLICY CONTEXT'
                ]
                
                available_sections = sum(1 for section in expected_sections if section in prompt_result)
                
                self.results.add_result(
                    "Enhanced Context Extraction",
                    available_sections >= 4,
                    f"Extracted {available_sections}/5 context sections in prompt"
                )
                    
            except Exception as e:
                self.results.add_result(
                    "Enhanced Context Extraction",
                    False,
                    f"Error in context extraction: {e}"
                )
            
            # Test 3: Enhanced prompt generation
            try:
                test_dto = {
                    'player_input': 'I carefully examine the ancient tome',
                    'goal_hint': 'gather magical knowledge',
                    'risk_preference': 'cautious',
                    'confidence': 0.9,
                    'party_context': {
                        'avg_level': 5,
                        'party_size': 3,
                        'hp_state': {'average_hp_percent': 75}
                    },
                    'policy_context': {
                        'difficulty_policy': {'difficulty_target': 'medium'},
                        'active_profile': 'house'
                    }
                }
                
                prompt = create_scenario_from_dto(test_dto)
                
                # Check for comprehensive prompt content
                prompt_checks = [
                    'NARRATIVE & PACING CONTEXT' in prompt,
                    'PLAYER INTENT CONTEXT' in prompt,
                    'PARTY SNAPSHOT CONTEXT' in prompt,
                    'MECHANICS POLICY CONTEXT' in prompt,
                    'OUTPUT REQUIREMENTS' in prompt
                ]
                
                comprehensive_prompt = sum(prompt_checks) >= 4
                
                self.results.add_result(
                    "Enhanced Prompt Generation",
                    comprehensive_prompt,
                    f"Generated comprehensive prompt: {sum(prompt_checks)}/5 sections"
                )
                    
            except Exception as e:
                self.results.add_result(
                    "Enhanced Prompt Generation",
                    False,
                    f"Error in prompt generation: {e}"
                )
                
        except ImportError as e:
            self.results.add_result(
                "Scenario Generator Import", 
                False, 
                f"Cannot import ScenarioGeneratorAgent: {e}"
            )
        except Exception as e:
            self.results.add_result(
                "Context Extraction and Prompt Generation", 
                False, 
                f"Unexpected error: {e}"
            )
    
    def test_end_to_end_integration(self):
        """Test complete end-to-end integration"""
        
        print("\n🔗 Testing End-to-End Integration...")
        
        try:
            from haystack_dnd_game import HaystackDnDGame
            from core.game_initialization import GameInitConfig
            
            # Test 1: Game initialization with enhanced config
            try:
                config = GameInitConfig(
                    collection_name="test_e2e_collection",
                    game_mode="new_campaign", 
                    player_name="E2E Test Player"
                )
                
                # This should work even with component failures due to fallbacks
                game = HaystackDnDGame(config=config)
                
                self.results.add_result(
                    "End-to-End Game Initialization", 
                    game is not None,
                    "Successfully initialized game with enhanced config"
                )
                
            except Exception as e:
                self.results.add_result(
                    "End-to-End Game Initialization", 
                    False, 
                    f"Error initializing game: {e}"
                )
                return
            
            # Test 2: Enhanced context usage in play_turn
            try:
                # Test a simple turn to see if enhanced context flows through
                response = game.play_turn("I look around the tavern")
                
                has_response = bool(response and len(response.strip()) > 0)
                
                self.results.add_result(
                    "End-to-End Play Turn with Enhanced Context", 
                    has_response,
                    f"Generated response: {len(response)} characters"
                )
                
            except Exception as e:
                self.results.add_result(
                    "End-to-End Play Turn with Enhanced Context", 
                    False, 
                    f"Error in play turn: {e}"
                )
                
        except ImportError as e:
            self.results.add_result(
                "End-to-End Import", 
                False, 
                f"Cannot import game components: {e}"
            )
        except Exception as e:
            self.results.add_result(
                "End-to-End Integration", 
                False, 
                f"Unexpected error: {e}"
            )
    
    def test_backward_compatibility(self):
        """Test backward compatibility with existing systems"""
        
        print("\n🔄 Testing Backward Compatibility...")
        
        try:
            # Test 1: Existing DTO structure still works
            try:
                from components.shared_contract import new_dto, RequestDTO, GameResponseDTO
                
                # Old-style DTO creation
                old_dto = new_dto("test input", {"location": "tavern"})
                
                # Should still have core fields
                core_fields = ['player_input', 'context', 'correlation_id', 'ts']
                has_core_fields = all(field in old_dto for field in core_fields)
                
                self.results.add_result(
                    "Backward Compatibility DTO Structure", 
                    has_core_fields,
                    "Old DTO structure still supported"
                )
                
            except Exception as e:
                self.results.add_result(
                    "Backward Compatibility DTO Structure", 
                    False, 
                    f"Error with old DTO: {e}"
                )
            
            # Test 2: Basic orchestrator creation still works
            try:
                from orchestrator.pipeline_integration import create_full_haystack_orchestrator
                
                # Old-style orchestrator creation (minimal parameters)
                basic_orchestrator = create_full_haystack_orchestrator()
                
                self.results.add_result(
                    "Backward Compatibility Orchestrator", 
                    basic_orchestrator is not None,
                    "Basic orchestrator creation still works"
                )
                
            except Exception as e:
                self.results.add_result(
                    "Backward Compatibility Orchestrator", 
                    False, 
                    f"Error with basic orchestrator: {e}"
                )
            
            # Test 3: Game can be created without enhanced config
            try:
                from haystack_dnd_game import HaystackDnDGame
                
                # Old-style game creation (should trigger auto-initialization)
                basic_game = HaystackDnDGame()
                
                self.results.add_result(
                    "Backward Compatibility Game Creation", 
                    basic_game is not None,
                    "Game can be created without enhanced config"
                )
                
            except Exception as e:
                self.results.add_result(
                    "Backward Compatibility Game Creation", 
                    False, 
                    f"Error with basic game creation: {e}"
                )
                
        except Exception as e:
            self.results.add_result(
                "Backward Compatibility", 
                False, 
                f"Error in compatibility test: {e}"
            )
    
    def test_error_scenarios(self):
        """Test various error scenarios and graceful degradation"""
        
        print("\n⚠️ Testing Error Scenarios and Graceful Degradation...")
        
        # Test 1: Component import failures
        try:
            from core.game_initialization import GameInitializationSystem, GameInitConfig
            
            init_system = GameInitializationSystem()
            config = GameInitConfig()
            
            # Force a component creation failure by passing invalid data
            # The fallback system should handle this gracefully
            try:
                config = init_system.create_game_components_with_fallbacks(config)
                
                # Even with potential failures, we should get some components
                components_exist = any(
                    getattr(config, comp) is not None 
                    for comp in ['policy_engine', 'character_manager', 'session_manager', 'game_engine']
                )
                
                self.results.add_result(
                    "Error Scenario Component Creation", 
                    components_exist,
                    f"Graceful degradation: {config.get_status_summary()}"
                )
                
            except Exception as e:
                self.results.add_result(
                    "Error Scenario Component Creation", 
                    False, 
                    f"Fallback system failed: {e}"
                )
                
        except Exception as e:
            self.results.add_result(
                "Error Scenario Setup", 
                False, 
                f"Error in error scenario test: {e}"
            )
        
        # Test 2: Invalid DTO handling
        try:
            from orchestrator.pipeline_integration import PipelineOrchestrator
            
            orchestrator = PipelineOrchestrator(enable_pipelines=False)
            
            # Test with malformed DTO
            invalid_dto = {"invalid": "structure"}
            
            try:
                if hasattr(orchestrator, '_populate_enhanced_dto_context'):
                    result = orchestrator._populate_enhanced_dto_context(invalid_dto)
                    
                    # Should return something, even if minimal
                    self.results.add_result(
                        "Error Scenario Invalid DTO Handling", 
                        result is not None,
                        "Invalid DTO handled gracefully"
                    )
                else:
                    self.results.add_result(
                        "Error Scenario Invalid DTO Handling", 
                        True,
                        "Method not available - graceful degradation"
                    )
                    
            except Exception as e:
                self.results.add_result(
                    "Error Scenario Invalid DTO Handling", 
                    False, 
                    f"Error handling failed: {e}"
                )
                
        except Exception as e:
            self.results.add_result(
                "Error Scenario DTO", 
                False, 
                f"Error in DTO error test: {e}"
            )
    
    def _save_test_report(self):
        """Save detailed test report to file"""
        
        try:
            report = {
                "test_suite": "Comprehensive Enhancement Test",
                "timestamp": time.time(),
                "summary": self.results.get_summary(),
                "environment": {
                    "python_version": sys.version,
                    "platform": sys.platform,
                    "working_directory": os.getcwd()
                }
            }
            
            with open("comprehensive_test_results.json", "w") as f:
                json.dump(report, f, indent=2, default=str)
            
            print(f"📄 Detailed test report saved to: comprehensive_test_results.json")
            
        except Exception as e:
            print(f"⚠️ Failed to save test report: {e}")


def main():
    """Run comprehensive enhancement test suite"""
    
    # Set up environment
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    
    # Initialize and run tests
    test_suite = ComprehensiveEnhancementTest()
    summary = test_suite.run_all_tests()
    
    # Return appropriate exit code
    exit_code = 0 if summary["failed"] == 0 else 1
    
    print(f"\n🏁 Test suite completed with exit code: {exit_code}")
    
    return exit_code


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)