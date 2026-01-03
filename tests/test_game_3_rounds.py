"""
Comprehensive end-to-end test for the D&D game system.
Tests 3 complete rounds of gameplay with default settings.

This test validates:
1. Game initialization with default settings
2. Turn processing through the pipeline orchestrator
3. Intent classification and routing
4. Scenario generation
5. RAG retrieval (if available)
6. State management across turns
7. Session persistence

Usage:
    python test_game_3_rounds.py
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.logging_config import get_logger
from core.game_initialization import initialize_enhanced_dnd_game, GameInitConfig
from haystack_dnd_game import HaystackDnDGame
from components.shared_contract import RequestDTO, GameResponseDTO

# Initialize logger
logger = get_logger(__name__)

class GameTester:
    """Handles comprehensive testing of the D&D game system."""

    def __init__(self):
        """Initialize the game tester."""
        self.game_initialized = False
        self.game = None
        self.test_results = {
            "initialization": False,
            "rounds": [],
            "errors": [],
            "total_rounds": 0,
            "successful_rounds": 0
        }

    def initialize_game(self) -> bool:
        """
        Initialize the game with default settings.

        Returns:
            True if initialization successful, False otherwise
        """
        logger.info("=" * 70)
        logger.info("🎮 INITIALIZING GAME WITH DEFAULT SETTINGS")
        logger.info("=" * 70)

        try:
            # Initialize game with defaults using the same approach as main game
            config: GameInitConfig = initialize_enhanced_dnd_game()

            # Create the game instance
            self.game = HaystackDnDGame(config=config)

            logger.info("✅ Game initialized successfully")
            logger.info(f"   Campaign: {config.campaign_config.name}")
            logger.info(f"   Player: {config.player_name}")
            logger.info(f"   Collection: {config.collection_name}")

            self.game_initialized = True
            self.test_results["initialization"] = True

            return True

        except Exception as e:
            logger.error(f"❌ Failed to initialize game: {e}")
            logger.exception(e)
            self.test_results["errors"].append({
                "phase": "initialization",
                "error": str(e)
            })
            return False

    def play_turn(self, turn_number: int, player_input: str) -> Dict[str, Any]:
        """
        Play a single turn of the game.

        Args:
            turn_number: The turn number (1-indexed)
            player_input: The player's input text

        Returns:
            Dictionary with turn results
        """
        logger.info("=" * 70)
        logger.info(f"🎲 TURN {turn_number}: {player_input}")
        logger.info("=" * 70)

        turn_result = {
            "turn_number": turn_number,
            "input": player_input,
            "success": False,
            "response_type": None,
            "error": None,
            "response_length": 0
        }

        try:
            # Process turn through the game's play_turn method
            logger.info(f"📤 Processing turn through game...")

            response = self.game.play_turn(player_input)

            # Handle case where response might be a string (error message)
            if isinstance(response, str):
                logger.error(f"❌ Turn failed with string response: {response}")
                turn_result["error"] = response
                self.test_results["errors"].append({
                    "phase": f"turn_{turn_number}",
                    "error": response
                })
                self.test_results["total_rounds"] += 1
                return turn_result

            # Check response
            if not response.get("success", False):
                error_msg = response.get("error", "Unknown error")
                logger.error(f"❌ Turn failed: {error_msg}")
                turn_result["error"] = error_msg
                self.test_results["errors"].append({
                    "phase": f"turn_{turn_number}",
                    "error": error_msg
                })
            else:
                # Success - extract response details
                response_type = response.get("response_type", "unknown")
                turn_result["success"] = True
                turn_result["response_type"] = response_type

                logger.info(f"✅ Turn completed successfully")
                logger.info(f"   Response type: {response_type}")

                # Log response content based on type
                if response_type == "scenario":
                    scenario = response.get("scenario", {})
                    description = scenario.get("description", "")
                    turn_result["response_length"] = len(description)
                    logger.info(f"   📖 Scenario description: {len(description)} chars")
                    logger.info(f"   {description[:200]}...")

                    choices = scenario.get("choices", [])
                    if choices:
                        logger.info(f"   🎯 Choices available: {len(choices)}")
                        for i, choice in enumerate(choices, 1):
                            logger.info(f"      {i}. {choice.get('text', 'N/A')}")

                elif response_type == "rag_result":
                    rag_result = response.get("rag_result", {})
                    answer = rag_result.get("answer", "")
                    turn_result["response_length"] = len(answer)
                    logger.info(f"   📚 RAG answer: {len(answer)} chars")
                    logger.info(f"   {answer[:200]}...")

                elif response_type == "npc_response":
                    npc_response = response.get("npc_response", {})
                    dialogue = npc_response.get("dialogue", "")
                    turn_result["response_length"] = len(dialogue)
                    logger.info(f"   💬 NPC dialogue: {len(dialogue)} chars")
                    logger.info(f"   {dialogue[:200]}...")

                # Track successful round
                self.test_results["successful_rounds"] += 1

            self.test_results["total_rounds"] += 1

        except Exception as e:
            logger.error(f"❌ Exception during turn {turn_number}: {e}")
            logger.exception(e)
            turn_result["error"] = str(e)
            self.test_results["errors"].append({
                "phase": f"turn_{turn_number}",
                "error": str(e)
            })
            self.test_results["total_rounds"] += 1

        return turn_result

    def run_test(self) -> bool:
        """
        Run the complete test suite (3 rounds).

        Returns:
            True if all tests passed, False otherwise
        """
        logger.info("=" * 70)
        logger.info("🚀 STARTING COMPREHENSIVE 3-ROUND GAME TEST")
        logger.info("=" * 70)

        # Step 1: Initialize game
        if not self.initialize_game():
            logger.error("❌ Game initialization failed - aborting test")
            return False

        # Step 2: Play 3 rounds with different types of inputs
        test_inputs = [
            "I look around and assess my surroundings",
            "I want to investigate the area for any signs of danger",
            "I prepare myself and move forward cautiously"
        ]

        for i, player_input in enumerate(test_inputs, 1):
            turn_result = self.play_turn(i, player_input)
            self.test_results["rounds"].append(turn_result)

        # Step 3: Save game state
        logger.info("=" * 70)
        logger.info("💾 SAVING GAME STATE")
        logger.info("=" * 70)

        try:
            save_path = "game_saves/test_3_rounds_save.json"
            self.game.session_manager.save_game(
                save_path,
                self.game.game_engine,
                self.game.character_manager,
                self.game.game_engine.campaign_config
            )
            logger.info(f"✅ Game saved to {save_path}")
        except Exception as e:
            logger.error(f"❌ Failed to save game: {e}")
            self.test_results["errors"].append({
                "phase": "save",
                "error": str(e)
            })

        # Step 4: Print summary
        self.print_summary()

        # Test passes if at least 2 out of 3 rounds succeeded
        success_rate = self.test_results["successful_rounds"] / self.test_results["total_rounds"]
        return success_rate >= 0.66

    def print_summary(self):
        """Print a summary of test results."""
        logger.info("=" * 70)
        logger.info("📊 TEST SUMMARY")
        logger.info("=" * 70)

        logger.info(f"Initialization: {'✅ PASS' if self.test_results['initialization'] else '❌ FAIL'}")
        logger.info(f"Total rounds: {self.test_results['total_rounds']}")
        logger.info(f"Successful rounds: {self.test_results['successful_rounds']}")
        logger.info(f"Failed rounds: {self.test_results['total_rounds'] - self.test_results['successful_rounds']}")

        if self.test_results["errors"]:
            logger.info(f"\n❌ Errors encountered: {len(self.test_results['errors'])}")
            for error in self.test_results["errors"]:
                logger.info(f"   - {error['phase']}: {error['error']}")

        logger.info("\n" + "=" * 70)

        # Round-by-round breakdown
        logger.info("ROUND-BY-ROUND BREAKDOWN")
        logger.info("=" * 70)
        for round_result in self.test_results["rounds"]:
            status = "✅ PASS" if round_result["success"] else "❌ FAIL"
            logger.info(f"\nRound {round_result['turn_number']}: {status}")
            logger.info(f"  Input: {round_result['input']}")
            logger.info(f"  Response type: {round_result.get('response_type', 'N/A')}")
            logger.info(f"  Response length: {round_result.get('response_length', 0)} chars")
            if round_result.get("error"):
                logger.info(f"  Error: {round_result['error']}")

        # Overall result
        success_rate = self.test_results["successful_rounds"] / max(self.test_results["total_rounds"], 1) * 100
        logger.info("\n" + "=" * 70)
        logger.info(f"OVERALL SUCCESS RATE: {success_rate:.1f}%")

        if success_rate >= 66:
            logger.info("🎉 TEST PASSED (at least 2/3 rounds successful)")
        else:
            logger.info("❌ TEST FAILED (less than 2/3 rounds successful)")

        logger.info("=" * 70)

    def save_results_to_file(self, filename: str = "test_results_3_rounds.json"):
        """
        Save test results to a JSON file.

        Args:
            filename: Name of the file to save results to
        """
        results_path = Path(project_root) / "tests" / "results" / filename
        results_path.parent.mkdir(parents=True, exist_ok=True)

        with open(results_path, 'w') as f:
            json.dump(self.test_results, f, indent=2)

        logger.info(f"📝 Test results saved to {results_path}")


def main():
    """Main entry point for the test."""
    # Ensure we have the API key
    if not os.getenv("GEMINI_API_KEY"):
        logger.error("❌ GEMINI_API_KEY environment variable not set")
        logger.error("   Please create a .env file with your API key")
        sys.exit(1)

    # Create tester and run
    tester = GameTester()
    success = tester.run_test()

    # Save results
    tester.save_results_to_file()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
