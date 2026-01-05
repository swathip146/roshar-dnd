#!/usr/bin/env python3
"""
Automated Game Test Script

Runs the game with automated inputs to test game initialization and basic gameplay.
This simulates a player going through:
1. Game setup (collection, character, campaign selection)
2. Starting first encounter
3. Making choices for 3 turns
4. Exiting

Usage:
    python tests/test_game_automated.py
"""

import subprocess
import time
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def run_game_automated():
    """Run game with automated inputs"""

    print("=" * 60)
    print("AUTOMATED GAME TEST")
    print("=" * 60)
    print()

    # Inputs to send to the game
    inputs = [
        "dnd_documents",      # Collection name
        "1",                  # Select character 1
        "1",                  # Select campaign 1
        "1",                  # Select difficulty 1
        "start first encounter",  # First action
        "2",                  # Choice 2 (turn 1)
        "2",                  # Choice 2 (turn 2)
        "2",                  # Choice 2 (turn 3)
        "exit",               # Exit game
    ]

    print("📋 Test Inputs:")
    for i, inp in enumerate(inputs, 1):
        print(f"   {i}. {inp}")
    print()

    # Join inputs with newlines
    input_data = "\n".join(inputs) + "\n"

    print("🎮 Starting game...")
    print("=" * 60)
    print()

    try:
        # Run the game script with inputs
        # Using run_game.sh which handles conda environment
        process = subprocess.Popen(
            ["bash", "./run_game.sh"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=project_root
        )

        # Send all inputs at once
        output, _ = process.communicate(input=input_data, timeout=120)

        print(output)

        print()
        print("=" * 60)
        print("📊 TEST RESULTS")
        print("=" * 60)

        # Check for success indicators
        success_indicators = [
            ("Game initialized", "🎮 ENHANCED D&D GAME INITIALIZATION" in output or "Game starting" in output),
            ("Character loaded", "Character:" in output or "Aggi" in output or "character_id" in output),
            ("Campaign loaded", "campaign" in output.lower() or "Campaign:" in output),
            ("First turn processed", "Turn 1" in output or "turn 1" in output.lower()),
            ("Choices displayed", "choice" in output.lower() or "option" in output.lower()),
            ("Game exited cleanly", process.returncode == 0 or "Exiting" in output or "exit" in output.lower())
        ]

        passed = 0
        failed = 0

        for check_name, check_result in success_indicators:
            if check_result:
                print(f"✅ {check_name}")
                passed += 1
            else:
                print(f"❌ {check_name}")
                failed += 1

        print()
        print(f"Results: {passed}/{len(success_indicators)} checks passed")

        # Check for errors
        error_indicators = [
            "Traceback",
            "Error:",
            "Exception:",
            "FAILED",
            "ModuleNotFoundError",
            "AttributeError"
        ]

        errors_found = [err for err in error_indicators if err in output]

        if errors_found:
            print()
            print("⚠️  Errors detected:")
            for err in errors_found:
                print(f"   - {err}")

        print()
        print("=" * 60)

        if passed == len(success_indicators) and not errors_found:
            print("✅ TEST PASSED: Game runs successfully!")
            return 0
        elif passed >= len(success_indicators) // 2:
            print("⚠️  TEST PARTIAL: Some checks failed but game mostly works")
            return 1
        else:
            print("❌ TEST FAILED: Major issues detected")
            return 2

    except subprocess.TimeoutExpired:
        print()
        print("=" * 60)
        print("⏰ TEST TIMEOUT: Game took too long (> 120s)")
        print("=" * 60)
        process.kill()
        return 3
    except Exception as e:
        print()
        print("=" * 60)
        print(f"❌ TEST ERROR: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return 4


def run_combat_test():
    """Run game and trigger combat"""

    print("=" * 60)
    print("AUTOMATED COMBAT TEST")
    print("=" * 60)
    print()

    # Inputs to trigger combat
    inputs = [
        "dnd_documents",      # Collection name
        "1",                  # Select character 1
        "1",                  # Select campaign 1
        "1",                  # Select difficulty 1
        "I attack the enemy with my sword!",  # Combat action
        "1",                  # Combat choice 1
        "1",                  # Combat choice 1
        "exit",               # Exit game
    ]

    print("📋 Combat Test Inputs:")
    for i, inp in enumerate(inputs, 1):
        print(f"   {i}. {inp}")
    print()

    input_data = "\n".join(inputs) + "\n"

    print("⚔️  Starting combat test...")
    print("=" * 60)
    print()

    try:
        process = subprocess.Popen(
            ["bash", "./run_game.sh"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=project_root
        )

        output, _ = process.communicate(input=input_data, timeout=120)

        print(output)

        print()
        print("=" * 60)
        print("📊 COMBAT TEST RESULTS")
        print("=" * 60)

        # Check for combat indicators
        combat_indicators = [
            ("Combat pipeline detected", "combat_pipeline" in output.lower() or "combat" in output.lower()),
            ("Combat agent invoked", "combat agent" in output.lower() or "⚔️" in output),
            ("Enemy extraction", "enemy" in output.lower() or "enemies" in output.lower() or "npc" in output.lower()),
            ("Initiative rolled", "initiative" in output.lower()),
            ("Combat turn", "turn" in output.lower() or "round" in output.lower())
        ]

        passed = 0
        for check_name, check_result in combat_indicators:
            if check_result:
                print(f"✅ {check_name}")
                passed += 1
            else:
                print(f"❌ {check_name}")

        print()
        print(f"Combat checks: {passed}/{len(combat_indicators)} passed")
        print("=" * 60)

        return 0 if passed >= 3 else 1

    except Exception as e:
        print(f"❌ Combat test error: {e}")
        import traceback
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    print()
    print("=" * 60)
    print("D&D GAME AUTOMATED TESTING")
    print("=" * 60)
    print()

    # Check if run_game.sh exists
    game_script = project_root / "run_game.sh"
    if not game_script.exists():
        print(f"❌ Error: {game_script} not found!")
        print(f"   Current directory: {Path.cwd()}")
        print(f"   Project root: {project_root}")
        sys.exit(1)

    print(f"✅ Found game script: {game_script}")
    print()

    # Run basic game test
    print("TEST 1: Basic Game Initialization")
    print("-" * 60)
    result1 = run_game_automated()

    print()
    print()

    # Run combat test
    print("TEST 2: Combat System")
    print("-" * 60)
    result2 = run_combat_test()

    print()
    print("=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    print(f"Basic Game Test: {'✅ PASSED' if result1 == 0 else '⚠️  PARTIAL' if result1 == 1 else '❌ FAILED'}")
    print(f"Combat Test: {'✅ PASSED' if result2 == 0 else '❌ FAILED'}")
    print("=" * 60)

    # Exit with appropriate code
    exit_code = max(result1, result2)
    sys.exit(exit_code)
