#!/usr/bin/env python3
"""
Comprehensive Test Case for D&D Game using modular_dm_assistant.py
Tests at least 5 rounds of gameplay and identifies all issues that need fixing
"""

import sys
import os
import json
import time
import traceback
from datetime import datetime
from typing import List, Dict, Any

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from modular_dm_assistant import ModularDMAssistant
except ImportError as e:
    print(f"❌ Failed to import ModularDMAssistant: {e}")
    print("Make sure all required dependencies are installed and available")
    sys.exit(1)

class DnDGameTester:
    """Comprehensive tester for D&D game functionality"""
    
    def __init__(self):
        self.assistant = None
        self.test_results = []
        self.issues_found = []
        self.round_count = 0
        self.start_time = None
        self.test_log = []
        
    def log_test(self, test_name: str, success: bool, message: str, error: str = None):
        """Log test results"""
        result = {
            'test_name': test_name,
            'success': success,
            'message': message,
            'error': error,
            'timestamp': datetime.now().isoformat(),
            'round': self.round_count
        }
        self.test_results.append(result)
        self.test_log.append(f"{'✅' if success else '❌'} {test_name}: {message}")
        
        if not success:
            issue = f"**{test_name}**: {message}"
            if error:
                issue += f" - Error: {error}"
            self.issues_found.append(issue)
        
        print(f"{'✅' if success else '❌'} {test_name}: {message}")
        if error and not success:
            print(f"   Error Details: {error}")
    
    def setup_test_environment(self):
        """Set up the test environment"""
        print("🚀 Setting up D&D Game Test Environment...")
        
        try:
            # Create test directories
            test_dirs = [
                "docs/current_campaign",
                "docs/players", 
                "docs/characters",
                "docs/sessions",
                "docs/inventory",
                "docs/spells",
                "docs/experience",
                "game_saves"
            ]
            
            for dir_path in test_dirs:
                os.makedirs(dir_path, exist_ok=True)
            
            # Create minimal test campaign
            self.create_test_campaign()
            self.create_test_players()
            
            self.log_test("Environment Setup", True, "Test directories and files created")
            return True
            
        except Exception as e:
            self.log_test("Environment Setup", False, "Failed to create test environment", str(e))
            return False
    
    def create_test_campaign(self):
        """Create a test campaign file"""
        campaign_data = {
            "title": "Test Adventure Campaign",
            "theme": "Fantasy Adventure",
            "setting": "Forgotten Realms",
            "level_range": "1-5",
            "overview": "A test campaign for comprehensive system testing.",
            "npcs": [
                {
                    "name": "Elara the Wise",
                    "role": "Village Elder",
                    "location": "Greenville"
                },
                {
                    "name": "Grimjaw the Bandit",
                    "role": "Antagonist", 
                    "location": "Forest Road"
                }
            ],
            "locations": [
                {
                    "name": "Greenville",
                    "location_type": "Village",
                    "description": "A peaceful farming village"
                },
                {
                    "name": "Darkwood Forest",
                    "location_type": "Wilderness",
                    "description": "A dangerous forest filled with bandits"
                }
            ]
        }
        
        with open("docs/current_campaign/campaign.json", "w") as f:
            json.dump(campaign_data, f, indent=2)
    
    def create_test_players(self):
        """Create test player files"""
        players = [
            {
                "name": "Thorin Ironforge",
                "race": "Dwarf",
                "character_class": "Fighter",
                "level": 3,
                "background": "Soldier",
                "rulebook": "Player's Handbook",
                "hp": 28,
                "ability_scores": {
                    "strength": 16,
                    "dexterity": 12,
                    "constitution": 15,
                    "intelligence": 10,
                    "wisdom": 13,
                    "charisma": 8
                },
                "combat_stats": {
                    "armor_class": 18,
                    "proficiency_bonus": 2,
                    "speed": 25
                }
            },
            {
                "name": "Luna Silverleaf",
                "race": "Elf",
                "character_class": "Ranger",
                "level": 3,
                "background": "Outlander",
                "rulebook": "Player's Handbook",
                "hp": 24,
                "ability_scores": {
                    "strength": 12,
                    "dexterity": 16,
                    "constitution": 14,
                    "intelligence": 12,
                    "wisdom": 15,
                    "charisma": 10
                },
                "combat_stats": {
                    "armor_class": 15,
                    "proficiency_bonus": 2,
                    "speed": 30
                }
            }
        ]
        
        for i, player in enumerate(players):
            with open(f"docs/players/player_{i+1}.json", "w") as f:
                json.dump(player, f, indent=2)
    
    def initialize_assistant(self):
        """Initialize the ModularDMAssistant"""
        print("\n🤖 Initializing Modular DM Assistant...")
        
        try:
            self.assistant = ModularDMAssistant(
                collection_name="dnd_documents",
                campaigns_dir="docs/current_campaign",
                players_dir="docs/players",
                verbose=True,
                enable_game_engine=True,
                enable_caching=True,
                enable_async=True
            )
            
            # Start the assistant
            self.assistant.start()
            time.sleep(2)  # Give agents time to initialize
            
            self.log_test("Assistant Initialization", True, "ModularDMAssistant initialized and started")
            return True
            
        except Exception as e:
            self.log_test("Assistant Initialization", False, "Failed to initialize assistant", str(e))
            return False
    
    def test_basic_commands(self):
        """Test basic commands functionality"""
        print("\n📋 Testing Basic Commands...")
        
        # Test help command
        try:
            response = self.assistant.process_dm_input("help")
            if "AVAILABLE COMMANDS" in response:
                self.log_test("Help Command", True, "Help command returned command list")
            else:
                self.log_test("Help Command", False, "Help command did not return expected format")
        except Exception as e:
            self.log_test("Help Command", False, "Help command failed", str(e))
        
        # Test agent status
        try:
            response = self.assistant.process_dm_input("agent status")
            if "AGENT STATUS" in response:
                self.log_test("Agent Status", True, "Agent status command working")
            else:
                self.log_test("Agent Status", False, "Agent status returned unexpected format")
        except Exception as e:
            self.log_test("Agent Status", False, "Agent status command failed", str(e))
    
    def test_campaign_management(self):
        """Test campaign management functionality"""
        print("\n📚 Testing Campaign Management...")
        
        # Test list campaigns
        try:
            response = self.assistant.process_dm_input("list campaigns")
            if "AVAILABLE CAMPAIGNS" in response or "campaign" in response.lower():
                self.log_test("List Campaigns", True, "Campaign listing working")
            else:
                self.log_test("List Campaigns", False, "No campaigns found or unexpected format")
        except Exception as e:
            self.log_test("List Campaigns", False, "List campaigns failed", str(e))
        
        # Test campaign info
        try:
            response = self.assistant.process_dm_input("campaign info")
            if "CAMPAIGN" in response or "No campaign selected" in response:
                self.log_test("Campaign Info", True, "Campaign info command working")
            else:
                self.log_test("Campaign Info", False, "Campaign info returned unexpected format")
        except Exception as e:
            self.log_test("Campaign Info", False, "Campaign info failed", str(e))
        
        # Test list players
        try:
            response = self.assistant.process_dm_input("list players")
            if "PLAYERS" in response or "player" in response.lower():
                self.log_test("List Players", True, "Player listing working")
            else:
                self.log_test("List Players", False, "No players found or unexpected format")
        except Exception as e:
            self.log_test("List Players", False, "List players failed", str(e))
    
    def test_dice_system(self):
        """Test dice rolling functionality"""
        print("\n🎲 Testing Dice System...")
        
        dice_tests = [
            ("roll 1d20", "Basic d20 roll"),
            ("roll 3d6", "Multiple dice roll"),
            ("roll 1d20+5", "Roll with modifier"),
            ("roll stealth", "Skill check roll"),
            ("roll perception", "Perception check"),
            ("roll damage", "Damage roll")
        ]
        
        for dice_command, test_desc in dice_tests:
            try:
                response = self.assistant.process_dm_input(dice_command)
                if "Result:" in response or "ROLL" in response.upper():
                    self.log_test(f"Dice: {test_desc}", True, f"'{dice_command}' working correctly")
                else:
                    self.log_test(f"Dice: {test_desc}", False, f"'{dice_command}' unexpected response format")
            except Exception as e:
                self.log_test(f"Dice: {test_desc}", False, f"'{dice_command}' failed", str(e))
    
    def test_scenario_generation(self):
        """Test scenario generation and choice system"""
        print("\n🎭 Testing Scenario Generation...")
        
        # Test basic scenario generation
        try:
            response = self.assistant.process_dm_input("generate scenario")
            if "SCENARIO" in response:
                self.log_test("Scenario Generation", True, "Basic scenario generation working")
                # Check if options were extracted
                if hasattr(self.assistant, 'last_scenario_options') and self.assistant.last_scenario_options:
                    self.log_test("Option Extraction", True, f"Extracted {len(self.assistant.last_scenario_options)} options")
                else:
                    self.log_test("Option Extraction", False, "No options extracted from scenario")
            else:
                self.log_test("Scenario Generation", False, "Scenario generation failed or unexpected format")
        except Exception as e:
            self.log_test("Scenario Generation", False, "Scenario generation failed", str(e))
        
        # Test scenario with specific context
        try:
            response = self.assistant.process_dm_input("create a tavern encounter")
            if "SCENARIO" in response or "tavern" in response.lower():
                self.log_test("Contextual Scenario", True, "Contextual scenario generation working")
            else:
                self.log_test("Contextual Scenario", False, "Contextual scenario failed or unexpected format")
        except Exception as e:
            self.log_test("Contextual Scenario", False, "Contextual scenario generation failed", str(e))
    
    def test_player_choice_system(self):
        """Test player choice selection and consequences"""
        print("\n🎯 Testing Player Choice System...")
        
        # First generate a scenario to have options
        try:
            self.assistant.process_dm_input("generate scenario with combat options")
            time.sleep(1)  # Give time for processing
        except Exception as e:
            self.log_test("Choice Setup", False, "Failed to generate scenario for choice testing", str(e))
            return
        
        # Test option selection
        if hasattr(self.assistant, 'last_scenario_options') and self.assistant.last_scenario_options:
            try:
                response = self.assistant.process_dm_input("select option 1")
                if "SELECTED" in response and "STORY CONTINUES" in response:
                    self.log_test("Option Selection", True, "Player choice system working")
                else:
                    self.log_test("Option Selection", False, "Choice selection unexpected format")
            except Exception as e:
                self.log_test("Option Selection", False, "Option selection failed", str(e))
        else:
            self.log_test("Option Selection", False, "No options available for selection")
    
    def test_combat_system(self):
        """Test combat functionality"""
        print("\n⚔️ Testing Combat System...")
        
        # Test start combat
        try:
            response = self.assistant.process_dm_input("start combat")
            if "COMBAT STARTED" in response or "combat" in response.lower():
                self.log_test("Start Combat", True, "Combat initialization working")
            else:
                self.log_test("Start Combat", False, "Combat start failed or unexpected format")
        except Exception as e:
            self.log_test("Start Combat", False, "Start combat failed", str(e))
        
        # Test combat status
        try:
            response = self.assistant.process_dm_input("combat status")
            if "Combat Status" in response or "combatants" in response.lower():
                self.log_test("Combat Status", True, "Combat status working")
            else:
                self.log_test("Combat Status", False, "Combat status unexpected format")
        except Exception as e:
            self.log_test("Combat Status", False, "Combat status failed", str(e))
        
        # Test next turn
        try:
            response = self.assistant.process_dm_input("next turn")
            if "active" in response.lower() or "turn" in response.lower():
                self.log_test("Next Turn", True, "Turn advancement working")
            else:
                self.log_test("Next Turn", False, "Turn advancement unexpected format")
        except Exception as e:
            self.log_test("Next Turn", False, "Next turn failed", str(e))
        
        # Test end combat
        try:
            response = self.assistant.process_dm_input("end combat")
            if "COMBAT ENDED" in response or "ended" in response.lower():
                self.log_test("End Combat", True, "Combat ending working")
            else:
                self.log_test("End Combat", False, "Combat end unexpected format")
        except Exception as e:
            self.log_test("End Combat", False, "End combat failed", str(e))
    
    def test_rule_system(self):
        """Test rule lookup functionality"""
        print("\n📖 Testing Rule System...")
        
        rule_tests = [
            ("rule stealth", "Stealth rules"),
            ("how does combat work", "Combat rules"),
            ("check rule advantage", "Advantage rules"),
            ("what happens when poisoned", "Condition rules")
        ]
        
        for rule_command, test_desc in rule_tests:
            try:
                response = self.assistant.process_dm_input(rule_command)
                if "RULE" in response.upper() or "rule" in response.lower():
                    self.log_test(f"Rule: {test_desc}", True, f"'{rule_command}' working")
                else:
                    self.log_test(f"Rule: {test_desc}", False, f"'{rule_command}' unexpected format")
            except Exception as e:
                self.log_test(f"Rule: {test_desc}", False, f"'{rule_command}' failed", str(e))
    
    def test_game_state_management(self):
        """Test game state and save functionality"""
        print("\n💾 Testing Game State Management...")
        
        # Test game state
        try:
            response = self.assistant.process_dm_input("game state")
            if "GAME STATE" in response or "state" in response.lower():
                self.log_test("Game State", True, "Game state retrieval working")
            else:
                self.log_test("Game State", False, "Game state unexpected format")
        except Exception as e:
            self.log_test("Game State", False, "Game state failed", str(e))
        
        # Test save game
        try:
            response = self.assistant.process_dm_input("save game Test Session")
            if "saved" in response.lower() or "save" in response.lower():
                self.log_test("Save Game", True, "Game save working")
            else:
                self.log_test("Save Game", False, "Game save unexpected format")
        except Exception as e:
            self.log_test("Save Game", False, "Save game failed", str(e))
        
        # Test list saves
        try:
            response = self.assistant.process_dm_input("list saves")
            if "SAVES" in response or "save" in response.lower():
                self.log_test("List Saves", True, "Save listing working")
            else:
                self.log_test("List Saves", False, "Save listing unexpected format")
        except Exception as e:
            self.log_test("List Saves", False, "List saves failed", str(e))
    
    def run_gameplay_round(self, round_num: int):
        """Run a complete gameplay round"""
        print(f"\n🎮 ROUND {round_num}: Complete Gameplay Test")
        self.round_count = round_num
        
        # Generate scenario
        try:
            scenario_prompt = f"The party encounters a mysterious situation (Round {round_num})"
            response = self.assistant.process_dm_input(f"generate scenario {scenario_prompt}")
            if "SCENARIO" in response:
                self.log_test(f"Round {round_num} Scenario", True, "Scenario generated successfully")
            else:
                self.log_test(f"Round {round_num} Scenario", False, "Scenario generation failed")
                return False
        except Exception as e:
            self.log_test(f"Round {round_num} Scenario", False, "Scenario generation error", str(e))
            return False
        
        # Make a choice
        try:
            if hasattr(self.assistant, 'last_scenario_options') and self.assistant.last_scenario_options:
                choice_num = min(2, len(self.assistant.last_scenario_options))  # Choose 2nd option or available
                response = self.assistant.process_dm_input(f"select option {choice_num}")
                if "SELECTED" in response:
                    self.log_test(f"Round {round_num} Choice", True, f"Option {choice_num} selected successfully")
                else:
                    self.log_test(f"Round {round_num} Choice", False, "Choice selection failed")
            else:
                self.log_test(f"Round {round_num} Choice", False, "No options available for selection")
        except Exception as e:
            self.log_test(f"Round {round_num} Choice", False, "Choice selection error", str(e))
        
        # Test dice roll during round
        try:
            response = self.assistant.process_dm_input("roll 1d20")
            if "Result:" in response:
                self.log_test(f"Round {round_num} Dice", True, "Dice roll successful")
            else:
                self.log_test(f"Round {round_num} Dice", False, "Dice roll failed")
        except Exception as e:
            self.log_test(f"Round {round_num} Dice", False, "Dice roll error", str(e))
        
        return True
    
    def run_comprehensive_test(self):
        """Run the complete comprehensive test suite"""
        print("=" * 80)
        print("🧪 COMPREHENSIVE D&D GAME TEST SUITE")
        print("=" * 80)
        
        self.start_time = time.time()
        
        # Setup phase
        if not self.setup_test_environment():
            print("❌ Test environment setup failed. Aborting tests.")
            return
        
        if not self.initialize_assistant():
            print("❌ Assistant initialization failed. Aborting tests.")
            return
        
        # Basic functionality tests
        self.test_basic_commands()
        self.test_campaign_management()
        self.test_dice_system()
        self.test_scenario_generation()
        self.test_player_choice_system()
        self.test_combat_system()
        self.test_rule_system()
        self.test_game_state_management()
        
        # Multi-round gameplay test
        print("\n" + "=" * 50)
        print("🎯 MULTI-ROUND GAMEPLAY TESTING")
        print("=" * 50)
        
        for round_num in range(1, 6):  # Test 5 rounds
            success = self.run_gameplay_round(round_num)
            if not success:
                print(f"⚠️ Round {round_num} had issues but continuing...")
            time.sleep(1)  # Brief pause between rounds
        
        # Cleanup
        try:
            if self.assistant:
                self.assistant.stop()
                self.log_test("Cleanup", True, "Assistant stopped successfully")
        except Exception as e:
            self.log_test("Cleanup", False, "Assistant cleanup failed", str(e))
        
        # Generate results
        self.generate_test_report()
    
    def generate_test_report(self):
        """Generate comprehensive test report"""
        end_time = time.time()
        duration = end_time - self.start_time if self.start_time else 0
        
        print("\n" + "=" * 80)
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 80)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - passed_tests
        
        print(f"📈 Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"⏱️ Duration: {duration:.2f} seconds")
        print(f"📍 Issues Found: {len(self.issues_found)}")
        
        # Save detailed results to JSON
        self.save_detailed_results()
        
        if self.issues_found:
            print("\n🚨 CRITICAL ISSUES FOUND:")
            for i, issue in enumerate(self.issues_found, 1):
                print(f"{i}. {issue}")
    
    def save_detailed_results(self):
        """Save detailed test results to files"""
        # Save JSON results
        results_data = {
            'test_summary': {
                'total_tests': len(self.test_results),
                'passed_tests': sum(1 for r in self.test_results if r['success']),
                'failed_tests': sum(1 for r in self.test_results if not r['success']),
                'duration_seconds': time.time() - self.start_time if self.start_time else 0,
                'test_date': datetime.now().isoformat()
            },
            'test_results': self.test_results,
            'issues_found': self.issues_found,
            'test_log': self.test_log
        }
        
        with open('test_results_detailed.json', 'w') as f:
            json.dump(results_data, f, indent=2)
        
        print(f"\n💾 Detailed results saved to: test_results_detailed.json")

def main():
    """Main test execution function"""
    print("🧪 Starting Comprehensive D&D Game Test Suite...")
    
    tester = DnDGameTester()
    
    try:
        tester.run_comprehensive_test()
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Critical test failure: {e}")
        traceback.print_exc()
    finally:
        if tester.assistant:
            try:
                tester.assistant.stop()
            except:
                pass
        print("\n🏁 Test suite completed.")

if __name__ == "__main__":
    main()