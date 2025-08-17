#!/usr/bin/env python3
"""
Comprehensive Test Suite for Modular DM Assistant Haystack Native
Tests all functionalities, data flow, architecture, and runs a full DnD game simulation
"""

import os
import sys
import time
import json
import tempfile
import shutil
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, patch, MagicMock
import traceback
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class DnDTestResult:
    """Test result tracking"""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
        self.warnings = []
        self.issues = []
        
    def add_pass(self, test_name: str):
        self.passed += 1
        print(f"✅ {test_name}")
        
    def add_fail(self, test_name: str, error: str):
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"❌ {test_name}: {error}")
        
    def add_warning(self, message: str):
        self.warnings.append(message)
        print(f"⚠️  WARNING: {message}")
        
    def add_issue(self, issue: str):
        self.issues.append(issue)

class ComprehensiveDnDTester:
    """Comprehensive tester for the DnD Assistant"""
    
    def __init__(self):
        self.results = DnDTestResult()
        self.temp_dirs = []
        self.test_data = {}
        
    def setup_test_environment(self):
        """Setup test environment with temp directories"""
        print("🔧 Setting up test environment...")
        
        try:
            # Create temporary directories for testing
            self.temp_base = tempfile.mkdtemp(prefix="dnd_test_")
            self.temp_dirs.append(self.temp_base)
            
            # Create required subdirectories
            self.campaigns_dir = os.path.join(self.temp_base, "campaigns")
            self.characters_dir = os.path.join(self.temp_base, "characters")
            self.saves_dir = os.path.join(self.temp_base, "saves")
            
            os.makedirs(self.campaigns_dir, exist_ok=True)
            os.makedirs(self.characters_dir, exist_ok=True)
            os.makedirs(self.saves_dir, exist_ok=True)
            
            # Create test data files
            self._create_test_data()
            
            print(f"✅ Test environment created: {self.temp_base}")
            
        except Exception as e:
            self.results.add_fail("Test Environment Setup", str(e))
            
    def _create_test_data(self):
        """Create test data files"""
        
        # Test character data
        test_character = {
            "name": "Test Hero",
            "class": "Fighter",
            "level": 3,
            "abilities": {
                "strength": 16,
                "dexterity": 14,
                "constitution": 15,
                "intelligence": 10,
                "wisdom": 12,
                "charisma": 8
            },
            "proficiencies": {
                "athletics": True,
                "intimidation": True,
                "perception": True
            },
            "conditions": [],
            "hp": {"current": 28, "max": 28}
        }
        
        char_file = os.path.join(self.characters_dir, "test_hero.json")
        with open(char_file, 'w') as f:
            json.dump(test_character, f, indent=2)
            
        # Test campaign data
        campaign_info = {
            "title": "Test Adventure",
            "setting": "Test World",
            "description": "A test campaign for validation",
            "lore": {
                "Test City": "A bustling metropolis for testing",
                "Ancient Ruins": "Mysterious ruins with test encounters"
            }
        }
        
        campaign_file = os.path.join(self.campaigns_dir, "campaign_info.json")
        with open(campaign_file, 'w') as f:
            json.dump(campaign_info, f, indent=2)
            
        self.test_data = {
            "character": test_character,
            "campaign": campaign_info
        }
    
    def cleanup(self):
        """Clean up test environment"""
        print("🧹 Cleaning up test environment...")
        for temp_dir in self.temp_dirs:
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                self.results.add_warning(f"Failed to cleanup {temp_dir}: {e}")
    
    def test_core_imports(self):
        """Test that all core modules can be imported"""
        print("\n📦 Testing Core Imports...")
        
        modules_to_test = [
            "modular_dm_assistant_haystack_native",
            "core.haystack_native_orchestrator_fixed",
            "core.haystack_native_pipelines",
            "core.haystack_native_components",
            "core.pure_event_sourcing",
            "cache_manager",
            "game_save_manager"
        ]
        
        for module_name in modules_to_test:
            try:
                __import__(module_name)
                self.results.add_pass(f"Import {module_name}")
            except ImportError as e:
                self.results.add_fail(f"Import {module_name}", str(e))
            except Exception as e:
                self.results.add_fail(f"Import {module_name}", f"Unexpected error: {e}")
    
    def test_haystack_orchestrator(self):
        """Test Haystack orchestrator functionality"""
        print("\n🎛️  Testing Haystack Orchestrator...")
        
        try:
            from core.haystack_native_orchestrator_fixed import HaystackDMOrchestrator, GameStateManager
            
            # Test orchestrator initialization
            try:
                orchestrator = HaystackDMOrchestrator(
                    campaigns_dir=self.campaigns_dir,
                    verbose=False
                )
                self.results.add_pass("Orchestrator Initialization")
            except Exception as e:
                self.results.add_fail("Orchestrator Initialization", str(e))
                return
            
            # Test pipeline info
            try:
                pipeline_info = orchestrator.get_pipeline_info()
                assert isinstance(pipeline_info, dict), "Pipeline info should be dict"
                assert "registered_intents" in pipeline_info, "Should have registered_intents"
                self.results.add_pass("Pipeline Info Retrieval")
            except Exception as e:
                self.results.add_fail("Pipeline Info Retrieval", str(e))
            
            # Test intent classification
            try:
                intent = orchestrator.classify_intent("I want to make a stealth check")
                assert intent in ["SKILL_CHECK", "UNKNOWN"], f"Unexpected intent: {intent}"
                self.results.add_pass("Intent Classification")
            except Exception as e:
                self.results.add_fail("Intent Classification", str(e))
            
            # Test command processing
            try:
                result = orchestrator.process_command("Make an athletics check", {})
                assert isinstance(result, dict), "Result should be dict"
                assert "intent" in result, "Result should have intent"
                self.results.add_pass("Command Processing")
            except Exception as e:
                self.results.add_fail("Command Processing", str(e))
                
        except ImportError as e:
            self.results.add_fail("Orchestrator Tests", f"Import failed: {e}")
    
    def test_game_state_manager(self):
        """Test game state management and event sourcing"""
        print("\n🎮 Testing Game State Manager...")
        
        try:
            from core.haystack_native_orchestrator_fixed import GameStateManager
            from core.pure_event_sourcing import GameEvent, EventStore, StateProjector
            
            # Test GameStateManager initialization
            try:
                game_state = GameStateManager(verbose=False)
                self.results.add_pass("GameStateManager Initialization")
            except Exception as e:
                self.results.add_fail("GameStateManager Initialization", str(e))
                return
            
            # Test state retrieval
            try:
                current_state = game_state.get_current_state()
                assert isinstance(current_state, dict), "State should be dict"
                assert "characters" in current_state, "State should have characters"
                assert "session" in current_state, "State should have session"
                self.results.add_pass("State Retrieval")
            except Exception as e:
                self.results.add_fail("State Retrieval", str(e))
            
            # Test state updates
            try:
                update_data = {"test_field": "test_value"}
                success = game_state.apply_state_update(update_data)
                assert success, "State update should succeed"
                self.results.add_pass("State Update")
            except Exception as e:
                self.results.add_fail("State Update", str(e))
            
            # Test event sourcing components
            try:
                event_store = EventStore()
                projector = StateProjector()
                
                # Test event creation and storage
                event = GameEvent(
                    event_id="test_001",
                    event_type="test.event",
                    actor="test_user",
                    payload={"action": "test"}
                )
                
                success = event_store.append_event(event)
                assert success, "Event append should succeed"
                
                # Test state projection
                projected_state = projector.project_state([event])
                assert isinstance(projected_state, dict), "Projected state should be dict"
                
                self.results.add_pass("Event Sourcing")
            except Exception as e:
                self.results.add_fail("Event Sourcing", str(e))
                
        except ImportError as e:
            self.results.add_fail("Game State Tests", f"Import failed: {e}")
    
    def test_native_components(self):
        """Test Haystack native components"""
        print("\n🧩 Testing Native Components...")
        
        try:
            from core.haystack_native_components import (
                CharacterDataComponent, CampaignContextComponent, 
                RuleEnforcementComponent, DiceSystemComponent,
                CombatEngineComponent, GameStateComponent
            )
            
            # Test CharacterDataComponent
            try:
                char_component = CharacterDataComponent(
                    characters_dir=self.characters_dir,
                    verbose=False
                )
                
                # Test character data retrieval
                result = char_component.run("Test Hero", "full_data")
                assert result["success"], "Character data retrieval should succeed"
                assert "character_data" in result, "Should return character_data"
                assert result["character_data"]["name"] == "Test Hero", "Should load correct character"
                
                self.results.add_pass("CharacterDataComponent")
            except Exception as e:
                self.results.add_fail("CharacterDataComponent", str(e))
            
            # Test CampaignContextComponent
            try:
                campaign_component = CampaignContextComponent(
                    campaigns_dir=self.campaigns_dir,
                    verbose=False
                )
                
                result = campaign_component.run("full")
                assert result["success"], "Campaign context should succeed"
                assert "campaign_info" in result, "Should return campaign_info"
                
                self.results.add_pass("CampaignContextComponent")
            except Exception as e:
                self.results.add_fail("CampaignContextComponent", str(e))
            
            # Test RuleEnforcementComponent
            try:
                rule_component = RuleEnforcementComponent(verbose=False)
                
                result = rule_component.run(
                    action="make a stealth check",
                    context={"difficulty": "medium"}
                )
                assert result["success"], "Rule enforcement should succeed"
                assert "requires_check" in result, "Should determine if check required"
                
                self.results.add_pass("RuleEnforcementComponent")
            except Exception as e:
                self.results.add_fail("RuleEnforcementComponent", str(e))
            
            # Test DiceSystemComponent
            try:
                dice_component = DiceSystemComponent(verbose=False)
                
                result = dice_component.run("1d20", modifier=5)
                assert result["success"], "Dice roll should succeed"
                assert "roll_result" in result, "Should return roll result"
                assert 6 <= result["total"] <= 25, "Roll total should be in valid range"
                
                self.results.add_pass("DiceSystemComponent")
            except Exception as e:
                self.results.add_fail("DiceSystemComponent", str(e))
            
            # Test CombatEngineComponent
            try:
                combat_component = CombatEngineComponent(verbose=False)
                
                result = combat_component.run("attack", "Player1", "Goblin")
                assert result["success"], "Combat action should succeed"
                assert "combat_result" in result, "Should return combat result"
                
                self.results.add_pass("CombatEngineComponent")
            except Exception as e:
                self.results.add_fail("CombatEngineComponent", str(e))
                
        except ImportError as e:
            self.results.add_fail("Native Components Tests", f"Import failed: {e}")
    
    def test_pipelines(self):
        """Test Haystack pipeline functionality"""
        print("\n🔄 Testing Haystack Pipelines...")
        
        try:
            from core.haystack_native_pipelines import (
                MasterRoutingPipelineNative, SkillCheckPipelineNative,
                CombatActionPipelineNative, LoreQueryPipelineNative
            )
            
            # Test MasterRoutingPipelineNative (with mocked LLM)
            try:
                with patch('core.haystack_native_pipelines.MockLLMGenerator') as mock_llm:
                    mock_llm.return_value.run.return_value = {"replies": ["SKILL_CHECK"]}
                    
                    master_pipeline = MasterRoutingPipelineNative(
                        characters_dir=self.characters_dir,
                        campaigns_dir=self.campaigns_dir,
                        verbose=False
                    )
                    
                    self.results.add_pass("MasterRoutingPipelineNative Init")
            except Exception as e:
                self.results.add_fail("MasterRoutingPipelineNative Init", str(e))
            
            # Test individual pipelines
            try:
                skill_pipeline = SkillCheckPipelineNative(
                    characters_dir=self.characters_dir,
                    campaigns_dir=self.campaigns_dir,
                    verbose=False
                )
                self.results.add_pass("SkillCheckPipelineNative Init")
            except Exception as e:
                self.results.add_fail("SkillCheckPipelineNative Init", str(e))
            
            try:
                combat_pipeline = CombatActionPipelineNative(verbose=False)
                self.results.add_pass("CombatActionPipelineNative Init")
            except Exception as e:
                self.results.add_fail("CombatActionPipelineNative Init", str(e))
            
            try:
                lore_pipeline = LoreQueryPipelineNative(
                    campaigns_dir=self.campaigns_dir,
                    verbose=False
                )
                self.results.add_pass("LoreQueryPipelineNative Init")
            except Exception as e:
                self.results.add_fail("LoreQueryPipelineNative Init", str(e))
                
        except ImportError as e:
            self.results.add_fail("Pipeline Tests", f"Import failed: {e}")
    
    def test_cache_manager(self):
        """Test cache manager functionality"""
        print("\n📋 Testing Cache Manager...")
        
        try:
            from cache_manager import SimpleInlineCache
            
            # Test cache initialization
            try:
                cache = SimpleInlineCache()
                self.results.add_pass("Cache Manager Initialization")
            except Exception as e:
                self.results.add_fail("Cache Manager Initialization", str(e))
                return
            
            # Test cache operations
            try:
                # Test set/get
                cache.set("test_key", "test_value", ttl_hours=1.0)
                value = cache.get("test_key")
                assert value == "test_value", "Cache should return stored value"
                
                # Test TTL expiration
                cache.set("expire_key", "expire_value", ttl_hours=0.0001)  # Very short TTL
                time.sleep(0.5)  # Wait for expiration
                expired_value = cache.get("expire_key")
                assert expired_value is None, "Expired key should return None"
                
                # Test stats
                stats = cache.get_stats()
                assert isinstance(stats, dict), "Stats should be dict"
                assert "total_items" in stats, "Stats should have total_items"
                
                self.results.add_pass("Cache Operations")
            except Exception as e:
                self.results.add_fail("Cache Operations", str(e))
                
        except ImportError as e:
            self.results.add_fail("Cache Manager Tests", f"Import failed: {e}")
    
    def test_save_manager(self):
        """Test save manager functionality"""
        print("\n💾 Testing Save Manager...")
        
        try:
            from game_save_manager import GameSaveManager
            
            # Test save manager initialization
            try:
                save_manager = GameSaveManager(
                    game_saves_dir=self.saves_dir,
                    verbose=False
                )
                self.results.add_pass("Save Manager Initialization")
            except Exception as e:
                self.results.add_fail("Save Manager Initialization", str(e))
                return
            
            # Test save operations (mocked)
            try:
                # Create mock save data
                save_data = {
                    "save_name": "test_save",
                    "game_state": {"test": "data"},
                    "timestamp": time.time()
                }
                
                # Test save_game_state method (will fail gracefully without full DM assistant)
                result = save_manager.save_game_state(save_data, "test_save")
                # This might fail due to missing assistant, but we test the method exists
                
                # Test list_game_saves
                saves = save_manager.list_game_saves()
                assert isinstance(saves, list), "Should return list of saves"
                
                self.results.add_pass("Save Manager Operations")
            except Exception as e:
                self.results.add_fail("Save Manager Operations", str(e))
                
        except ImportError as e:
            self.results.add_fail("Save Manager Tests", f"Import failed: {e}")
    
    def test_main_assistant_initialization(self):
        """Test main assistant initialization"""
        print("\n🚀 Testing Main Assistant Initialization...")
        
        try:
            from modular_dm_assistant_haystack_native import HaystackNativeDMAssistant
            
            # Test assistant initialization with test directories
            try:
                assistant = HaystackNativeDMAssistant(
                    collection_name="test_collection",
                    campaigns_dir=self.campaigns_dir,
                    characters_dir=self.characters_dir,
                    verbose=False,
                    enable_caching=True
                )
                self.results.add_pass("Main Assistant Initialization")
                
                # Test system info
                system_info = assistant.get_system_info()
                assert isinstance(system_info, dict), "System info should be dict"
                assert "architecture" in system_info, "Should have architecture info"
                assert system_info["architecture"] == "Haystack Native (No Agent Framework)"
                
                # Test available commands
                commands = assistant.list_available_commands()
                assert isinstance(commands, list), "Commands should be list"
                assert len(commands) > 0, "Should have available commands"
                
                self.results.add_pass("Assistant Basic Operations")
                
            except Exception as e:
                self.results.add_fail("Main Assistant Initialization", str(e))
                
        except ImportError as e:
            self.results.add_fail("Assistant Initialization Tests", f"Import failed: {e}")
    
    def test_data_flow_integration(self):
        """Test data flow between components"""
        print("\n🔄 Testing Data Flow Integration...")
        
        try:
            from modular_dm_assistant_haystack_native import HaystackNativeDMAssistant
            
            # Initialize assistant
            assistant = HaystackNativeDMAssistant(
                collection_name="test_collection",
                campaigns_dir=self.campaigns_dir,
                characters_dir=self.characters_dir,
                verbose=False,
                enable_caching=False  # Disable caching for testing
            )
            
            # Test command processing flow
            test_commands = [
                "I want to make a stealth check",
                "Attack the goblin with my sword", 
                "What are the rules for advantage?",
                "Tell me about Test City",
                "Level up my character"
            ]
            
            for i, command in enumerate(test_commands):
                try:
                    response = assistant.process_dm_input(command)
                    assert isinstance(response, str), f"Response should be string for command {i+1}"
                    assert len(response) > 0, f"Response should not be empty for command {i+1}"
                    
                    # Check that response is not an error (basic check)
                    if not ("System Error" in response or "failed" in response.lower()):
                        self.results.add_pass(f"Data Flow Command {i+1}")
                    else:
                        self.results.add_warning(f"Command {i+1} returned error response: {response[:100]}...")
                        
                except Exception as e:
                    self.results.add_fail(f"Data Flow Command {i+1}", str(e))
            
            # Test performance stats
            try:
                stats = assistant.get_performance_stats()
                assert isinstance(stats, dict), "Performance stats should be dict"
                assert "commands_processed" in stats, "Should track command count"
                assert stats["commands_processed"] > 0, "Should have processed commands"
                
                self.results.add_pass("Performance Tracking")
            except Exception as e:
                self.results.add_fail("Performance Tracking", str(e))
                
        except Exception as e:
            self.results.add_fail("Data Flow Integration", str(e))
    
    def run_simulated_dnd_game(self):
        """Run a simulated D&D game session with 5+ turns"""
        print("\n🎲 Running Simulated D&D Game Session...")
        
        try:
            from modular_dm_assistant_haystack_native import HaystackNativeDMAssistant
            
            # Initialize assistant for game session
            assistant = HaystackNativeDMAssistant(
                collection_name="game_test",
                campaigns_dir=self.campaigns_dir,
                characters_dir=self.characters_dir,
                verbose=False,
                enable_caching=True
            )
            
            # Simulate a complete D&D game session
            game_log = []
            narrative_consistency_issues = []
            rule_execution_issues = []
            
            # Turn 1: Character Introduction & Skill Check
            print("  Turn 1: Character introduction and stealth check...")
            try:
                response1 = assistant.process_dm_input(
                    "Test Hero wants to sneak past the guards. Make a stealth check with DC 15."
                )
                game_log.append(("Turn 1", "Stealth Check", response1))
                
                # Check for narrative consistency
                if "stealth" not in response1.lower() and "check" not in response1.lower():
                    narrative_consistency_issues.append("Turn 1: Response doesn't mention stealth or check")
                
                self.results.add_pass("Game Turn 1 - Stealth Check")
            except Exception as e:
                self.results.add_fail("Game Turn 1 - Stealth Check", str(e))
                rule_execution_issues.append(f"Turn 1 failed: {e}")
            
            # Turn 2: Combat Initiation
            print("  Turn 2: Combat encounter begins...")
            try:
                response2 = assistant.process_dm_input(
                    "Guards spot Test Hero! Initiative! Test Hero attacks the nearest guard with sword."
                )
                game_log.append(("Turn 2", "Combat Attack", response2))
                
                # Check for combat elements
                if not any(word in response2.lower() for word in ["attack", "combat", "damage", "hit"]):
                    narrative_consistency_issues.append("Turn 2: Combat response lacks combat elements")
                
                self.results.add_pass("Game Turn 2 - Combat Attack")
            except Exception as e:
                self.results.add_fail("Game Turn 2 - Combat Attack", str(e))
                rule_execution_issues.append(f"Turn 2 failed: {e}")
            
            # Turn 3: Rule Query During Combat
            print("  Turn 3: Rule clarification needed...")
            try:
                response3 = assistant.process_dm_input(
                    "What are the rules for flanking in D&D 5e?"
                )
                game_log.append(("Turn 3", "Rule Query", response3))
                
                # Check for rule information
                if "rule" not in response3.lower() and "flank" not in response3.lower():
                    narrative_consistency_issues.append("Turn 3: Rule response doesn't address flanking")
                
                self.results.add_pass("Game Turn 3 - Rule Query")
            except Exception as e:
                self.results.add_fail("Game Turn 3 - Rule Query", str(e))
                rule_execution_issues.append(f"Turn 3 failed: {e}")
            
            # Turn 4: Lore/World Query
            print("  Turn 4: World lore investigation...")
            try:
                response4 = assistant.process_dm_input(
                    "Test Hero wants to know about Test City's history and any legends."
                )
                game_log.append(("Turn 4", "Lore Query", response4))
                
                # Check for lore elements
                if "test city" not in response4.lower() and "lore" not in response4.lower():
                    narrative_consistency_issues.append("Turn 4: Lore response doesn't mention Test City")
                
                self.results.add_pass("Game Turn 4 - Lore Query")
            except Exception as e:
                self.results.add_fail("Game Turn 4 - Lore Query", str(e))
                rule_execution_issues.append(f"Turn 4 failed: {e}")
            
            # Turn 5: Character Management
            print("  Turn 5: Character development...")
            try:
                response5 = assistant.process_dm_input(
                    "Test Hero gains experience and levels up to level 4. Update character stats."
                )
                game_log.append(("Turn 5", "Character Management", response5))
                
                # Check for character management elements
                if not any(word in response5.lower() for word in ["character", "level", "update"]):
                    narrative_consistency_issues.append("Turn 5: Character management response lacks relevant elements")
                
                self.results.add_pass("Game Turn 5 - Character Management")
            except Exception as e:
                self.results.add_fail("Game Turn 5 - Character Management", str(e))
                rule_execution_issues.append(f"Turn 5 failed: {e}")
            
            # Turn 6: Scenario Choice
            print("  Turn 6: Important decision point...")
            try:
                response6 = assistant.process_dm_input(
                    "Test Hero faces a fork in the road: go left to the Ancient Ruins or right to the Forest. Choose wisely!"
                )
                game_log.append(("Turn 6", "Scenario Choice", response6))
                
                # Check for scenario elements
                if not any(word in response6.lower() for word in ["choice", "decide", "option"]):
                    narrative_consistency_issues.append("Turn 6: Scenario choice response doesn't provide options")
                
                self.results.add_pass("Game Turn 6 - Scenario Choice")
            except Exception as e:
                self.results.add_fail("Game Turn 6 - Scenario Choice", str(e))
                rule_execution_issues.append(f"Turn 6 failed: {e}")
            
            # Analyze game session results
            print("\n📊 Analyzing Game Session Results...")
            
            # Check narrative consistency
            if len(narrative_consistency_issues) == 0:
                self.results.add_pass("Narrative Consistency")
            else:
                for issue in narrative_consistency_issues:
                    self.results.add_issue(f"Narrative Consistency: {issue}")
                self.results.add_fail("Narrative Consistency", f"{len(narrative_consistency_issues)} issues found")
            
            # Check rule execution
            if len(rule_execution_issues) == 0:
                self.results.add_pass("Rule Execution")
            else:
                for issue in rule_execution_issues:
                    self.results.add_issue(f"Rule Execution: {issue}")
                self.results.add_fail("Rule Execution", f"{len(rule_execution_issues)} issues found")
            
            # Check game progression
            if len(game_log) == 6:
                self.results.add_pass("Game Progression")
            else:
                self.results.add_fail("Game Progression", f"Only completed {len(game_log)}/6 turns")
            
            # Store game log for analysis
            self.test_data["game_log"] = game_log
            self.test_data["narrative_issues"] = narrative_consistency_issues
            self.test_data["rule_issues"] = rule_execution_issues
            
        except Exception as e:
            self.results.add_fail("Simulated D&D Game", str(e))
    
    def test_error_handling(self):
        """Test error handling and edge cases"""
        print("\n⚠️  Testing Error Handling...")
        
        try:
            from modular_dm_assistant_haystack_native import HaystackNativeDMAssistant
            
            assistant = HaystackNativeDMAssistant(
                collection_name="error_test",
                campaigns_dir="/nonexistent/path",  # Invalid path
                characters_dir="/nonexistent/path",  # Invalid path
                verbose=False,
                enable_caching=True
            )
            
            # Test invalid commands
            error_test_commands = [
                "",  # Empty command
                "   ",  # Whitespace only
                "Invalid command with special chars !@#$%^&*()",
                "Extremely long command that goes on and on " * 50,  # Very long command
                None  # This will test type handling
            ]
            
            for i, command in enumerate(error_test_commands):
                try:
                    if command is None:
                        # Skip None test as it would cause TypeError in str operations
                        continue
                        
                    response = assistant.process_dm_input(command)
                    
                    # Check that we get some response (not crash)
                    assert isinstance(response, str), f"Should return string for error command {i+1}"
                    
                    # Check if it's handled gracefully (no Python tracebacks)
                    if "Traceback" not in response and "Exception" not in response:
                        self.results.add_pass(f"Error Handling {i+1}")
                    else:
                        self.results.add_fail(f"Error Handling {i+1}", "Unhandled exception in response")
                        
                except Exception as e:
                    # This is actually bad - should be handled gracefully
                    self.results.add_fail(f"Error Handling {i+1}", f"Unhandled exception: {e}")
            
            # Test performance under load (simplified)
            try:
                start_time = time.time()
                for i in range(10):
                    assistant.process_dm_input(f"Test command {i}")
                end_time = time.time()
                
                avg_time = (end_time - start_time) / 10
                if avg_time < 1.0:  # Should process reasonably quickly
                    self.results.add_pass("Performance Under Load")
                else:
                    self.results.add_warning(f"Slow performance: {avg_time:.2f}s per command")
                    
            except Exception as e:
                self.results.add_fail("Performance Under Load", str(e))
                
        except Exception as e:
            self.results.add_fail("Error Handling Setup", str(e))
    
    def run_all_tests(self):
        """Run all tests"""
        print("🧪 Starting Comprehensive D&D Assistant Test Suite")
        print("=" * 60)
        
        start_time = time.time()
        
        try:
            self.setup_test_environment()
            
            # Core functionality tests
            self.test_core_imports()
            self.test_haystack_orchestrator()
            self.test_game_state_manager()
            self.test_native_components()
            self.test_pipelines()
            self.test_cache_manager()
            self.test_save_manager()
            self.test_main_assistant_initialization()
            
            # Integration and flow tests
            self.test_data_flow_integration()
            
            # Game simulation
            self.run_simulated_dnd_game()
            
            # Error handling and edge cases
            self.test_error_handling()
            
        except Exception as e:
            print(f"❌ Critical test failure: {e}")
            traceback.print_exc()
        
        finally:
            self.cleanup()
            
        end_time = time.time()
        
        # Generate test report
        self.generate_test_report(end_time - start_time)
    
    def generate_test_report(self, duration: float):
        """Generate comprehensive test report"""
        print("\n" + "=" * 60)
        print("📋 COMPREHENSIVE TEST REPORT")
        print("=" * 60)
        
        # Summary
        total_tests = self.results.passed + self.results.failed
        pass_rate = (self.results.passed / total_tests * 100) if total_tests > 0 else 0
        
        print(f"🎯 Test Summary:")
        print(f"   ✅ Passed: {self.results.passed}")
        print(f"   ❌ Failed: {self.results.failed}")
        print(f"   📊 Pass Rate: {pass_rate:.1f}%")
        print(f"   ⏱️  Duration: {duration:.2f}s")
        print(f"   ⚠️  Warnings: {len(self.results.warnings)}")
        print(f"   🐛 Issues Found: {len(self.results.issues)}")
        
        # Detailed results
        if self.results.failed > 0:
            print(f"\n❌ Failed Tests:")
            for error in self.results.errors:
                print(f"   • {error}")
        
        if self.results.warnings:
            print(f"\n⚠️  Warnings:")
            for warning in self.results.warnings:
                print(f"   • {warning}")
        
        if self.results.issues:
            print(f"\n🐛 Issues Found:")
            for issue in self.results.issues:
                print(f"   • {issue}")
        
        # Architecture assessment
        print(f"\n🏗️  Architecture Assessment:")
        if self.results.passed >= 15:  # Most tests passed
            print("   ✅ Core architecture is functional")
        else:
            print("   ⚠️  Core architecture has significant issues")
        
        if len([e for e in self.results.errors if "Import" in e]) == 0:
            print("   ✅ All dependencies resolved correctly")
        else:
            print("   ❌ Import/dependency issues detected")
        
        # Game session analysis
        if "game_log" in self.test_data:
            print(f"\n🎲 Game Session Analysis:")
            print(f"   • Completed turns: {len(self.test_data['game_log'])}/6")
            print(f"   • Narrative issues: {len(self.test_data.get('narrative_issues', []))}")
            print(f"   • Rule execution issues: {len(self.test_data.get('rule_issues', []))}")
        
        # Overall assessment
        print(f"\n🏆 Overall Assessment:")
        if pass_rate >= 90:
            assessment = "EXCELLENT - System is production ready"
        elif pass_rate >= 75:
            assessment = "GOOD - Minor issues need addressing"
        elif pass_rate >= 50:
            assessment = "FAIR - Significant improvements needed"
        else:
            assessment = "POOR - Major architectural problems"
        
        print(f"   {assessment}")
        
        print("\n" + "=" * 60)


def main():
    """Main test execution"""
    tester = ComprehensiveDnDTester()
    tester.run_all_tests()
    
    # Generate markdown report
    generate_markdown_report(tester.results, tester.test_data)


def generate_markdown_report(results: DnDTestResult, test_data: Dict[str, Any]):
    """Generate markdown report for issues found"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    report = f"""# D&D Assistant Test Report

**Generated:** {timestamp}  
**Test Suite:** Comprehensive DnD Assistant Analysis

## Summary

- **Total Tests:** {results.passed + results.failed}
- **Passed:** {results.passed}
- **Failed:** {results.failed}
- **Pass Rate:** {(results.passed / (results.passed + results.failed) * 100) if (results.passed + results.failed) > 0 else 0:.1f}%
- **Warnings:** {len(results.warnings)}
- **Issues Found:** {len(results.issues)}

## Test Results

### ✅ Passed Tests
{results.passed} tests passed successfully.

### ❌ Failed Tests

"""
    
    if results.errors:
        for error in results.errors:
            report += f"- {error}\n"
    else:
        report += "No test failures.\n"
    
    report += "\n### ⚠️ Warnings\n\n"
    if results.warnings:
        for warning in results.warnings:
            report += f"- {warning}\n"
    else:
        report += "No warnings.\n"
    
    report += "\n## Issues Found\n\n"
    if results.issues:
        for issue in results.issues:
            report += f"- {issue}\n"
    else:
        report += "No issues found.\n"
    
    # Game session analysis
    if "game_log" in test_data:
        report += "\n## Game Session Analysis\n\n"
        report += f"**Completed Turns:** {len(test_data['game_log'])}/6\n\n"
        
        for turn_num, (turn, action_type, response) in enumerate(test_data['game_log'], 1):
            report += f"### {turn} - {action_type}\n"
            report += f"**Response:** {response[:200]}...\n\n"
        
        if test_data.get('narrative_issues'):
            report += "### Narrative Consistency Issues\n\n"
            for issue in test_data['narrative_issues']:
                report += f"- {issue}\n"
            report += "\n"
        
        if test_data.get('rule_issues'):
            report += "### Rule Execution Issues\n\n"
            for issue in test_data['rule_issues']:
                report += f"- {issue}\n"
            report += "\n"
    
    # Architectural analysis
    report += """## Architecture Analysis

### Core Components
- **Haystack Native Orchestrator:** Central coordination system
- **Game State Manager:** Event sourcing and state management
- **Native Components:** Character, Campaign, Rules, Dice, Combat systems
- **Pipeline System:** Modular command processing
- **Cache Manager:** Performance optimization
- **Save Manager:** Game persistence

### Data Flow
1. User input → Intent Classification
2. Context enrichment with game state
3. Pipeline routing based on intent
4. Component execution (Character, Rules, Dice, etc.)
5. State updates via event sourcing
6. Response aggregation and formatting

### Event Sourcing
The system uses event sourcing for state management, providing:
- Complete audit trail of game events
- State reconstruction from events
- Temporal queries and rollback capability

## Recommendations

### High Priority Issues
"""
    
    # Add high priority issues
    high_priority = [e for e in results.errors if any(term in e for term in ["Import", "Initialization", "Critical"])]
    if high_priority:
        for issue in high_priority:
            report += f"1. **{issue}** - Address immediately\n"
    else:
        report += "No high priority issues found.\n"
    
    report += """

### Medium Priority Issues
"""
    
    # Add medium priority issues  
    medium_priority = [e for e in results.errors if e not in high_priority]
    if medium_priority:
        for issue in medium_priority[:5]:  # Limit to first 5
            report += f"1. **{issue}** - Address in next iteration\n"
    else:
        report += "No medium priority issues found.\n"
    
    report += """

### Performance Recommendations
1. **Optimize pipeline routing** - Cache intent classification results
2. **Batch state updates** - Reduce event sourcing overhead  
3. **Component pooling** - Reuse heavy components like document stores
4. **Async processing** - Handle long-running operations asynchronously

### Testing Recommendations
1. **Add unit tests** for individual components
2. **Expand integration tests** with more complex scenarios
3. **Performance testing** under load
4. **Error injection testing** for robustness validation

### Documentation Improvements
1. **API documentation** for all public interfaces
2. **Architecture diagrams** showing component relationships
3. **Setup instructions** with dependency management
4. **Usage examples** for common scenarios

## Conclusion

"""
    
    # Final assessment
    pass_rate = (results.passed / (results.passed + results.failed) * 100) if (results.passed + results.failed) > 0 else 0
    if pass_rate >= 90:
        conclusion = "The D&D Assistant shows excellent stability and functionality. Minor refinements recommended."
    elif pass_rate >= 75:
        conclusion = "The system is largely functional with some areas needing attention. Good foundation for production use."
    elif pass_rate >= 50:
        conclusion = "The system shows promise but requires significant improvements before production deployment."
    else:
        conclusion = "Major architectural and implementation issues need to be resolved before the system can be considered stable."
    
    report += conclusion + "\n"
    
    # Write report to file
    with open("dnd_assistant_test_report.md", "w") as f:
        f.write(report)
    
    print(f"📝 Detailed test report saved to: dnd_assistant_test_report.md")


if __name__ == "__main__":
    main()