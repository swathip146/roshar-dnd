#!/usr/bin/env python3
"""
Simple automated test script to run the game for 3-4 rounds
"""

import subprocess
import time
from pathlib import Path

def run_game_test():
    """Run the game with predefined inputs"""

    print("=" * 80)
    print("AUTOMATED GAME TEST - 3-4 ROUNDS")
    print("=" * 80)
    print()

    # Predefined inputs for testing
    test_inputs = [
        "start first encounter",  # Round 1
        "1",                      # Round 2: Select first choice
        "2",                      # Round 3: Select second choice
        "3",                      # Round 4: Select third choice
        "quit"                    # Exit
    ]

    # Create input string
    input_str = "\n".join(test_inputs) + "\n"

    print("🎮 Starting game with predefined inputs:")
    for i, inp in enumerate(test_inputs, 1):
        print(f"   {i}. {inp}")
    print()

    # Run the game
    try:
        result = subprocess.run(
            ["python3", "haystack_dnd_game.py"],
            input=input_str,
            capture_output=True,
            text=True,
            timeout=120  # 2 minute timeout
        )

        print("=" * 80)
        print("GAME OUTPUT")
        print("=" * 80)
        print(result.stdout)

        if result.stderr:
            print("=" * 80)
            print("STDERR (if any)")
            print("=" * 80)
            print(result.stderr)

        print()
        print("=" * 80)
        print("TEST COMPLETE")
        print("=" * 80)

        # Find and display the latest log file
        logs_dir = Path("logs")
        if logs_dir.exists():
            log_files = sorted(logs_dir.glob("dnd_game_*.log"))
            if log_files:
                latest_log = log_files[-1]
                print(f"\n📄 Latest log file: {latest_log}")
                print(f"\n📊 Checking for errors in log...")

                with open(latest_log) as f:
                    lines = f.readlines()
                    errors = [line for line in lines if " - ERROR - " in line]
                    warnings = [line for line in lines if " - WARNING - " in line]

                    print(f"   Total lines: {len(lines)}")
                    print(f"   Errors: {len(errors)}")
                    print(f"   Warnings: {len(warnings)}")

                    if errors:
                        print("\n❌ ERRORS FOUND:")
                        for error in errors[:5]:  # Show first 5
                            print(f"   {error.strip()[:120]}")
                    else:
                        print("\n✅ No errors found")

                    # Check for successful rounds
                    turn_processing = [line for line in lines if "Processing turn" in line]
                    print(f"\n🎯 Turns processed: {len(turn_processing)}")

                    # Check for scenario generation
                    scenarios = [line for line in lines if "scenario generation" in line.lower() or "scenario pipeline" in line.lower()]
                    print(f"📖 Scenario generations: {len(scenarios)}")

                    # Check for routing
                    routes = [line for line in lines if "Got routing result:" in line]
                    print(f"🔀 Routing decisions: {len(routes)}")
                    if routes:
                        print("   Routes:")
                        for route in routes[:5]:
                            route_value = route.split("Got routing result:")[-1].strip()
                            print(f"      {route_value}")

        return result.returncode == 0

    except subprocess.TimeoutExpired:
        print("❌ Test timed out after 2 minutes")
        return False
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False

if __name__ == "__main__":
    success = run_game_test()
    exit(0 if success else 1)
