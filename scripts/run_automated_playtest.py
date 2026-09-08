#!/usr/bin/env python3
"""
Automated test runner that properly loads environment and runs game
"""

import os
import sys
from pathlib import Path

# Load .env file first
env_file = Path('.env')
if env_file.exists():
    print("📝 Loading .env file...")
    with open(env_file) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value
    print("✅ Environment loaded")
else:
    print("⚠️  No .env file found")

# Set tokenizers parallelism
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Now run the game with automated inputs
import subprocess

print("\n" + "=" * 80)
print("AUTOMATED GAME TEST - Running with default selections")
print("=" * 80)
print()

# Inputs:
# 1. Skip load game (Enter)
# 2. Default campaign (Enter)
# 3. Default character (Enter)
# 4. Then game commands
test_inputs = [
    "",                       # Skip load game
    "",                       # Default campaign (1)
    "",                       # Default character (1)
    "start first encounter",  # Round 1
    "1",                      # Round 2: Select first choice
    "2",                      # Round 3: Select second choice
    "3",                      # Round 4: Select third choice
    "quit"                    # Exit
]

input_str = "\n".join(test_inputs) + "\n"

print("🎮 Test inputs:")
print("   1. [Enter] - Skip load game")
print("   2. [Enter] - Default campaign")
print("   3. [Enter] - Default character")
print("   4. 'start first encounter'")
print("   5. '1' - Select choice 1")
print("   6. '2' - Select choice 2")
print("   7. '3' - Select choice 3")
print("   8. 'quit'")
print()

try:
    # Run with inherited environment
    result = subprocess.run(
        [sys.executable, "haystack_dnd_game.py"],
        input=input_str,
        capture_output=True,
        text=True,
        timeout=180,  # 3 minute timeout
        env=os.environ.copy()  # Pass environment variables
    )

    print("=" * 80)
    print("GAME OUTPUT")
    print("=" * 80)
    print(result.stdout)

    if result.returncode != 0:
        print("\n" + "=" * 80)
        print("ERRORS")
        print("=" * 80)
        print(result.stderr)

    # Analyze the log
    logs_dir = Path("logs")
    if logs_dir.exists():
        log_files = sorted(logs_dir.glob("dnd_game_*.log"))
        if log_files:
            latest_log = log_files[-1]
            print("\n" + "=" * 80)
            print(f"LOG ANALYSIS: {latest_log.name}")
            print("=" * 80)

            with open(latest_log) as f:
                lines = f.readlines()

            errors = [line for line in lines if " - ERROR - " in line]
            warnings = [line for line in lines if " - WARNING - " in line]
            turns = [line for line in lines if "Processing turn" in line]
            routes = [line for line in lines if "Got routing result:" in line]
            function_calls = [line for line in lines if "Function call detected:" in line]
            scenarios = [line for line in lines if "scenario generation" in line.lower()]

            print(f"\n📊 Statistics:")
            print(f"   Total lines: {len(lines)}")
            print(f"   Errors: {len(errors)}")
            print(f"   Warnings: {len(warnings)}")
            print(f"   Turns processed: {len(turns)}")
            print(f"   Function calls: {len(function_calls)}")
            print(f"   Routing decisions: {len(routes)}")
            print(f"   Scenarios generated: {len(scenarios)}")

            if function_calls:
                print(f"\n✅ Function calls detected:")
                for fc in function_calls[:5]:
                    func_name = fc.split("Function call detected:")[-1].strip()
                    print(f"   - {func_name}")

            if routes:
                print(f"\n🔀 Routes:")
                for route in routes[:5]:
                    route_value = route.split("Got routing result:")[-1].strip()
                    print(f"   - {route_value}")

            if errors:
                print(f"\n❌ Errors found:")
                for error in errors[:5]:
                    # Extract just the error message part
                    error_parts = error.split(" - ")
                    if len(error_parts) >= 5:
                        error_msg = " - ".join(error_parts[4:]).strip()
                        print(f"   {error_msg[:120]}")
                    else:
                        print(f"   {error.strip()[:120]}")
            else:
                print(f"\n✅ No errors found!")

            # Check for story progression
            location_moves = [line for line in lines if "Moved to location:" in line]
            narrative_updates = [line for line in lines if "Updated narrative context" in line]

            if location_moves:
                print(f"\n📍 Location changes: {len(location_moves)}")
            if narrative_updates:
                print(f"📖 Narrative updates: {len(narrative_updates)}")

            # Final status
            print("\n" + "=" * 80)
            if errors:
                print("❌ TEST FAILED - Errors found")
            elif len(turns) < 3:
                print("⚠️  TEST INCOMPLETE - Less than 3 turns")
            else:
                print("✅ TEST PASSED - Game ran successfully!")
            print("=" * 80)

except subprocess.TimeoutExpired:
    print("❌ Test timed out after 3 minutes")
except Exception as e:
    print(f"❌ Test failed with error: {e}")
    import traceback
    traceback.print_exc()
