#!/usr/bin/env python3
"""
Run the real LLM test with .env loaded.

NOTE: This is a runner script, not a test module. Everything must stay behind
the __main__ guard — pytest imports every tests/*.py during collection, and a
bare sys.exit()/pytest.main() at import scope aborts the whole run with
INTERNALERROR. (Plan item 0.8.)
"""

import sys
import os


def main() -> int:
    from dotenv import load_dotenv

    load_dotenv()

    if not os.getenv("GEMINI_API_KEY"):
        print("❌ GEMINI_API_KEY not found in environment")
        return 1

    print("✅ GEMINI_API_KEY loaded")
    print("🔄 Running real LLM test...")
    print()

    import pytest

    return pytest.main([
        "tests/combat/test_npc_stat_generator.py::test_generate_goblin_stats_real_llm",
        "-v",
        "-s",
    ])


if __name__ == "__main__":
    sys.exit(main())
