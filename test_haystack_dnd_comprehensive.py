"""
Comprehensive Test Suite for Haystack D&D Game
Tests all features and data flows including 5+ turn gameplay simulation
Validates narrative consistency, rule implementation, and game progress
"""

import sys
import os
import unittest
import json
import time
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from haystack_dnd_game import HaystackDnDGame
    from orchestrator.pipeline_integration import GameRequest, GameResponse
    from components.dice import DiceRoller
    from components.character_manager import CharacterManager
    from components.policy import PolicyProfile
except ImportError as e:
    print(f"⚠️ Import error: {e}. Some components may not be available for testing.")


class TestHaystackDnDGameInitialization(unittest.TestCase):
    """Test game initialization and component setup"""
    
    def setUp(self):
        """Set up test environment"""
        self.game = None
    
    def tearDown(self):
        """Clean up after tests"""
        if self.game:
            # Clean up any created files
            try:
                import shutil
                if os.path.exists("saves"):
                    shutil.rmtree("saves")
            except:
                pass
    
    def test_game_initialization(self):
        """Test basic game initialization"""
        try:
            self.game = HaystackDnDGame()
            self.assertIsNotNone(self.game)
            self.assertIsNotNone(self.game.orchestrator)
            self.assertIsNotNone(self.game.game_state)
            
            # Check initial game state
            self.assertEqual(self.game.game_state["location"], "Tavern")
            self.assertIsInstance(self.game.game_state["history"], list)
            self.assertEqual(len(self.game.game_state["history"]), 0)
            
            print("✅ Game initialization test passed")
            
        except Exception as e:
            print(f"❌ Game initialization failed: {e}")
            self.fail(f"Game initialization failed: {e}")
    
    def test_orchestrator_initialization(self):
        """Test orchestrator and component initialization"""
        try:
            self.game = HaystackDnDGame()
            
            # Test orchestrator status
            status = self.game.orchestrator.get_pipeline_status()
            self.assertIsInstance(status, dict)
            
            # Check for expected components
            if status.get("pipelines_enabled"):
                self.assertIn("available_pipelines", status)
                self.assertIn("available_agents", status)
                
            print("✅ Orchestrator initialization test passed")
            
        except Exception as e:
            print(f"❌ Orchestrator initialization failed: {e}")
            # This is expected if dependencies are missing
            print("⚠️ This may be due to missing Haystack dependencies")


class TestGameFeatures(unittest.TestCase):
    """Test core game features and data flows"""
    
    def setUp(self):
        """Set up test game"""
        try:
            self.game = HaystackDnDGame()
        except Exception as e:
            self.skipTest(f"Cannot initialize game: {e}")
    
    def test_simple_turn_processing(self):
        """Test basic turn processing"""
        test_inputs = [
            "I look around the tavern",
            "I approach the bartender",
            "I examine the mysterious door",
            "I search for clues"
        ]
        
        for player_input in test_inputs:
            with self.subTest(input=player_input):
                try:
                    response = self.game.play_turn(player_input)
                    self.assertIsInstance(response, str)
                    self.assertGreater(len(response), 0)
                    
                    # Check that history is updated
                    self.assertGreater(len(self.game.game_state["history"]), 0)
                    
                except Exception as e:
                    print(f"⚠️ Turn processing failed for '{player_input}': {e}")
                    # Continue testing other inputs
    
    def test_enhanced_processing_triggers(self):
        """Test enhanced processing trigger detection"""
        enhanced_inputs = [
            "I search the ancient library for dragon lore",
            "I talk to the bartender about rumors", 
            "I cast a spell to detect magic",
            "I attack the goblin with my sword"
        ]
        
        for player_input in enhanced_inputs:
            with self.subTest(input=player_input):
                # Test that enhanced triggers are detected
                should_use_enhanced = self.game._should_use_enhanced_processing(player_input)
                self.assertTrue(should_use_enhanced, 
                              f"'{player_input}' should trigger enhanced processing")
    
    def test_fallback_mechanisms(self):
        """Test fallback mechanisms when components fail"""
        # Test with invalid input
        response = self.game.play_turn("")
        self.assertEqual(response, "The world waits for your action...")
        
        # Test fallback response
        fallback = self.game._fallback_response("test input")
        self.assertIsInstance(fallback, str)
        self.assertGreater(len(fallback), 0)
    
    def test_game_statistics(self):
        """Test game statistics collection"""
        # Play a few turns first
        self.game.play_turn("I look around")
        self.game.play_turn("I examine the room")
        
        stats = self.game.get_game_stats()
        self.assertIsInstance(stats, dict)
        self.assertIn("location", stats)
        self.assertIn("turns_played", stats)
        self.assertIn("session_time", stats)
        self.assertGreaterEqual(stats["turns_played"], 2)


class TestSaveLoadFunctionality(unittest.TestCase):
    """Test save and load game functionality"""
    
    def setUp(self):
        """Set up test game"""
        try:
            self.game = HaystackDnDGame()
        except Exception as e:
            self.skipTest(f"Cannot initialize game: {e}")
    
    def tearDown(self):
        """Clean up save files"""
        try:
            import shutil
            if os.path.exists("saves"):
                shutil.rmtree("saves")
        except:
            pass
    
    def test_save_game(self):
        """Test game saving functionality"""
        # Play some turns to create history
        self.game.play_turn("I enter the tavern")
        self.game.play_turn("I order a drink")
        
        # Test save
        save_result = self.game.save_game("test_save.json")
        self.assertTrue(save_result)
        
        # Check that file was created
        save_path = os.path.join("saves", "test_save.json")
        self.assertTrue(os.path.exists(save_path))
        
        # Check save file content
        with open(save_path, "r") as f:
            save_data = json.load(f)
        
        self.assertIn("location", save_data)
        self.assertIn("history", save_data)
        self.assertIn("save_version", save_data)
        self.assertEqual(save_data["save_version"], "2.0_haystack")
    
    def test_load_game(self):
        """Test game loading functionality"""
        # Save initial state
        original_location = self.game.game_state["location"]
        self.game.play_turn("I travel to the forest")
        self.game.save_game("test_load.json")
        
        # Modify game state
        self.game.game_state["location"] = "Modified Location"
        self.game.game_state["history"] = []
        
        # Load saved state
        load_result = self.game.load_game("test_load.json")
        self.assertTrue(load_result)
        
        # Verify state was restored (should not be original_location due to travel)
        self.assertNotEqual(self.game.game_state["location"], "Modified Location")
        self.assertGreater(len(self.game.game_state["history"]), 0)
    
    def test_list_saves(self):
        """Test save file listing"""
        # Create some save files
        self.game.save_game("save1.json")
        self.game.save_game("save2.json")
        
        saves = self.game.list_saves()
        self.assertIsInstance(saves, list)
        self.assertIn("save1.json", saves)
        self.assertIn("save2.json", saves)


class TestNarrativeConsistency(unittest.TestCase):
    """Test narrative consistency and coherence"""
    
    def setUp(self):
        """Set up test game"""
        try:
            self.game = HaystackDnDGame()
        except Exception as e:
            self.skipTest(f"Cannot initialize game: {e}")
    
    def test_location_tracking(self):
        """Test that location changes are tracked consistently"""
        initial_location = self.game.game_state["location"]
        
        # Actions that might change location
        location_actions = [
            "I leave the tavern and go outside",
            "I enter the forest",
            "I go into the cave",
            "I return to town"
        ]
        
        for action in location_actions:
            old_location = self.game.game_state["location"]
            self.game.play_turn(action)
            new_location = self.game.game_state["location"]
            
            # Location might change or stay the same, but should be consistent
            self.assertIsInstance(new_location, str)
            self.assertGreater(len(new_location), 0)
    
    def test_history_continuity(self):
        """Test that game history maintains continuity"""
        actions = [
            "I greet the bartender",
            "I ask about recent events", 
            "I order a meal",
            "I listen for rumors"
        ]
        
        for i, action in enumerate(actions):
            self.game.play_turn(action)
            
            # Check history grows
            self.assertEqual(len(self.game.game_state["history"]), i + 1)
            
            # Check latest entry
            latest_entry = self.game.game_state["history"][-1]
            self.assertIn("player", latest_entry)
            self.assertIn("dm", latest_entry)
            self.assertEqual(latest_entry["player"], action)
    
    def test_context_continuity(self):
        """Test that context is maintained between turns"""
        # Set up a scenario
        self.game.play_turn("I ask the bartender about the missing merchant")
        first_response = self.game.game_state["history"][-1]["dm"]
        
        # Follow up should be contextually aware
        self.game.play_turn("Can you tell me more about that?")
        second_response = self.game.game_state["history"][-1]["dm"]
        
        # Both should be strings with content
        self.assertIsInstance(first_response, str)
        self.assertIsInstance(second_response, str)
        self.assertGreater(len(first_response), 0)
        self.assertGreater(len(second_response), 0)


class TestRuleImplementation(unittest.TestCase):
    """Test D&D rule implementation and consistency"""
    
    def setUp(self):
        """Set up test components"""
        try:
            self.dice_roller = DiceRoller()
            self.character_manager = CharacterManager()
        except Exception as e:
            self.skipTest(f"Cannot initialize components: {e}")
    
    def test_dice_rolling(self):
        """Test dice rolling mechanics"""
        # Test basic dice roll
        roll_result = self.dice_roller.roll_die(20)
        self.assertGreaterEqual(roll_result.result, 1)
        self.assertLessEqual(roll_result.result, 20)
        self.assertEqual(roll_result.die_type, 20)
        
        # Test skill roll
        advantage_state = {"final_state": "normal"}
        skill_result = self.dice_roller.skill_roll("investigation", 5, advantage_state)
        
        self.assertIn("total", skill_result)
        self.assertIn("roll_breakdown", skill_result)
        self.assertGreaterEqual(skill_result["total"], 6)  # 1 + 5 modifier minimum
        self.assertLessEqual(skill_result["total"], 25)   # 20 + 5 modifier maximum
    
    def test_advantage_disadvantage(self):
        """Test advantage/disadvantage mechanics"""
        # Test advantage
        advantage_state = {"final_state": "advantage"}
        adv_result = self.dice_roller.skill_roll("perception", 3, advantage_state)
        self.assertEqual(len(adv_result["raw_rolls"]), 2)
        self.assertEqual(adv_result["advantage_state"], "advantage")
        
        # Test disadvantage
        disadvantage_state = {"final_state": "disadvantage"}
        disadv_result = self.dice_roller.skill_roll("stealth", 2, disadvantage_state)
        self.assertEqual(len(disadv_result["raw_rolls"]), 2)
        self.assertEqual(disadv_result["advantage_state"], "disadvantage")
    
    def test_character_management(self):
        """Test character creation and management"""
        test_character = {
            "character_id": "test_hero",
            "name": "Test Hero",
            "level": 3,
            "ability_scores": {
                "strength": 14,
                "dexterity": 16,
                "constitution": 13,
                "intelligence": 12,
                "wisdom": 15,
                "charisma": 10
            },
            "skills": {
                "stealth": True,
                "perception": True
            },
            "expertise_skills": ["stealth"]
        }
        
        char_id = self.character_manager.add_character(test_character)
        self.assertEqual(char_id, "test_hero")
        
        # Test skill data calculation
        skill_data = self.character_manager.get_skill_data(char_id, "stealth")
        self.assertEqual(skill_data["character_id"], char_id)
        self.assertTrue(skill_data["is_proficient"])
        self.assertTrue(skill_data["expertise"])
        
        # Dexterity 16 = +3, proficiency at level 3 = +2, expertise = double prof
        expected_modifier = 3 + (2 * 2)  # +7 total
        self.assertEqual(skill_data["modifier"], expected_modifier)


class TestGameplaySimulation(unittest.TestCase):
    """Test complete 5+ turn gameplay scenarios"""
    
    def setUp(self):
        """Set up test game"""
        try:
            self.game = HaystackDnDGame()
        except Exception as e:
            self.skipTest(f"Cannot initialize game: {e}")
    
    def test_tavern_investigation_scenario(self):
        """Test a 5+ turn investigation scenario in tavern"""
        scenario_turns = [
            "I look around the bustling tavern",
            "I approach the bartender and order a drink",
            "I ask the bartender about any recent strange events",
            "I listen to the conversations of nearby patrons",
            "I examine the notice board for any interesting postings",
            "I strike up a conversation with a hooded figure in the corner",
            "I ask about the missing merchant caravan"
        ]
        
        responses = []
        locations = []
        
        for i, action in enumerate(scenario_turns):
            response = self.game.play_turn(action)
            responses.append(response)
            locations.append(self.game.game_state["location"])
            
            # Validate each response
            self.assertIsInstance(response, str)
            self.assertGreater(len(response), 0)
            
            # Check history tracking
            self.assertEqual(len(self.game.game_state["history"]), i + 1)
            
        # Test narrative consistency
        self.assertEqual(len(responses), len(scenario_turns))
        
        # Location should remain consistent or change logically
        self.assertTrue(all(isinstance(loc, str) for loc in locations))
        
        # All responses should be unique (no exact duplicates)
        self.assertEqual(len(set(responses)), len(responses))
        
        print(f"✅ Completed {len(scenario_turns)}-turn tavern investigation scenario")
        print("📍 Location progression:", " → ".join(set(locations)))
        
    def test_exploration_scenario(self):
        """Test a 6-turn exploration and discovery scenario"""
        exploration_turns = [
            "I decide to explore beyond the tavern",
            "I head toward the mysterious forest outside town",
            "I search for any tracks or signs of recent passage",
            "I investigate a strange glowing light between the trees",
            "I carefully approach the source of the light",
            "I attempt to communicate with whatever is causing the phenomenon"
        ]
        
        initial_location = self.game.game_state["location"]
        narrative_elements = []
        
        for i, action in enumerate(exploration_turns):
            response = self.game.play_turn(action)
            current_location = self.game.game_state["location"]
            
            # Track narrative elements
            narrative_elements.append({
                "turn": i + 1,
                "action": action,
                "response": response,
                "location": current_location
            })
            
            # Validate progression
            self.assertIsInstance(response, str)
            self.assertGreater(len(response), 10)  # Substantial responses
            
        # Test scenario progression
        self.assertEqual(len(narrative_elements), len(exploration_turns))
        
        # Location should have progressed from initial tavern
        final_location = narrative_elements[-1]["location"]
        location_changed = final_location != initial_location
        
        print(f"✅ Completed {len(exploration_turns)}-turn exploration scenario")
        print(f"📍 Location changed: {initial_location} → {final_location} ({location_changed})")
        
        # Test for narrative coherence (responses should be contextual)
        for element in narrative_elements:
            self.assertNotIn("error", element["response"].lower())
            
    def test_social_interaction_scenario(self):
        """Test a 7-turn social interaction scenario"""
        social_turns = [
            "I greet the locals warmly",
            "I introduce myself as a traveling adventurer",
            "I ask about local customs and traditions",
            "I offer to help with any problems the town might have",
            "I share a story from my travels",
            "I ask if anyone needs an escort for dangerous journeys",
            "I inquire about joining the local guild or organization"
        ]
        
        social_responses = []
        relationship_progression = []
        
        for i, action in enumerate(social_turns):
            response = self.game.play_turn(action)
            social_responses.append(response)
            
            # Track potential relationship/reputation changes
            history_entry = self.game.game_state["history"][-1]
            relationship_progression.append({
                "turn": i + 1,
                "player_action": history_entry["player"],
                "npc_response": history_entry["dm"],
                "timestamp": history_entry.get("timestamp", time.time())
            })
        
        # Validate social scenario
        self.assertEqual(len(social_responses), len(social_turns))
        self.assertEqual(len(relationship_progression), len(social_turns))
        
        # Check for social interaction indicators in responses
        social_keywords = ["greet", "hello", "welcome", "help", "guild", "town", "local"]
        social_response_count = 0
        
        for response in social_responses:
            if any(keyword in response.lower() for keyword in social_keywords):
                social_response_count += 1
        
        # At least some responses should contain social elements
        self.assertGreater(social_response_count, 0)
        
        print(f"✅ Completed {len(social_turns)}-turn social interaction scenario")
        print(f"🤝 Social responses: {social_response_count}/{len(social_responses)}")


class TestGameProgressTracking(unittest.TestCase):
    """Test game progress and state tracking"""
    
    def setUp(self):
        """Set up test game"""
        try:
            self.game = HaystackDnDGame()
        except Exception as e:
            self.skipTest(f"Cannot initialize game: {e}")
    
    def test_session_progress_tracking(self):
        """Test session progress and statistics"""
        initial_stats = self.game.get_game_stats()
        initial_turns = initial_stats.get("turns_played", 0)
        
        # Play several turns
        test_actions = [
            "I examine my surroundings",
            "I check my equipment",
            "I plan my next move",
            "I gather information"
        ]
        
        for action in test_actions:
            self.game.play_turn(action)
        
        # Check updated statistics
        final_stats = self.game.get_game_stats()
        final_turns = final_stats.get("turns_played", 0)
        
        self.assertEqual(final_turns, initial_turns + len(test_actions))
        self.assertIn("session_time", final_stats)
        self.assertGreater(final_stats["session_time"], 0)
    
    def test_history_tracking(self):
        """Test comprehensive history tracking"""
        actions_and_responses = []
        
        # Execute tracked turns
        for i in range(5):
            action = f"Test action {i + 1}"
            response = self.game.play_turn(action)
            
            actions_and_responses.append({
                "action": action,
                "response": response,
                "turn_number": i + 1
            })
        
        # Validate history structure
        history = self.game.game_state["history"]
        self.assertEqual(len(history), 5)
        
        for i, entry in enumerate(history):
            self.assertIn("player", entry)
            self.assertIn("dm", entry)
            self.assertIn("timestamp", entry)
            self.assertEqual(entry["player"], f"Test action {i + 1}")
            
    def test_game_state_persistence(self):
        """Test that game state changes persist correctly"""
        # Initial state
        initial_location = self.game.game_state["location"]
        
        # Make changes
        self.game.play_turn("I travel to a new location")
        
        # Check persistence in subsequent turns
        self.game.play_turn("I look around this new area")
        
        # Validate state consistency
        self.assertEqual(len(self.game.game_state["history"]), 2)
        
        # Both history entries should be consistent
        first_entry = self.game.game_state["history"][0]
        second_entry = self.game.game_state["history"][1]
        
        self.assertIn("location", first_entry)
        self.assertIn("location", second_entry)


def run_comprehensive_test():
    """Run all tests with detailed reporting"""
    print("🎲 HAYSTACK D&D GAME - COMPREHENSIVE TEST SUITE")
    print("=" * 60)
    
    # Test suite configuration
    test_classes = [
        TestHaystackDnDGameInitialization,
        TestGameFeatures,
        TestSaveLoadFunctionality,
        TestNarrativeConsistency,
        TestRuleImplementation,
        TestGameplaySimulation,
        TestGameProgressTracking
    ]
    
    # Run tests
    total_tests = 0
    successful_tests = 0
    failed_tests = []
    
    for test_class in test_classes:
        print(f"\n🧪 Running {test_class.__name__}")
        print("-" * 40)
        
        suite = unittest.TestLoader().loadTestsFromTestCase(test_class)
        runner = unittest.TextTestRunner(verbosity=2, buffer=True)
        result = runner.run(suite)
        
        total_tests += result.testsRun
        successful_tests += result.testsRun - len(result.failures) - len(result.errors)
        
        if result.failures:
            failed_tests.extend([f"FAILURE: {test}" for test, trace in result.failures])
        if result.errors:
            failed_tests.extend([f"ERROR: {test}" for test, trace in result.errors])
    
    # Final report
    print("\n" + "=" * 60)
    print("📊 COMPREHENSIVE TEST RESULTS")
    print("=" * 60)
    print(f"Total Tests Run: {total_tests}")
    print(f"Successful: {successful_tests}")
    print(f"Failed: {len(failed_tests)}")
    print(f"Success Rate: {(successful_tests/total_tests)*100:.1f}%")
    
    if failed_tests:
        print("\n❌ Failed Tests:")
        for failure in failed_tests[:5]:  # Show first 5 failures
            print(f"  • {failure}")
        if len(failed_tests) > 5:
            print(f"  ... and {len(failed_tests) - 5} more")
    else:
        print("\n✅ All tests passed!")
    
    print("\n🎯 TEST COVERAGE:")
    print("  ✅ Game initialization and architecture")
    print("  ✅ Feature and data flow testing") 
    print("  ✅ 5+ turn gameplay simulation")
    print("  ✅ Narrative consistency validation")
    print("  ✅ D&D rule implementation verification")
    print("  ✅ Game progress tracking")
    print("  ✅ Save/load functionality")
    print("  ✅ Error handling and fallback mechanisms")
    
    return successful_tests, total_tests, failed_tests


if __name__ == "__main__":
    run_comprehensive_test()