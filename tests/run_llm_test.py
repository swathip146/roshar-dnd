#!/usr/bin/env python3
"""
Run the real LLM test with .env loaded.
"""

import sys
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Verify API key is loaded
if not os.getenv("GEMINI_API_KEY"):
    print("❌ GEMINI_API_KEY not found in environment")
    sys.exit(1)

print("✅ GEMINI_API_KEY loaded")
print("🔄 Running real LLM test...")
print()

# Run pytest
import pytest

sys.exit(pytest.main([
    "tests/combat/test_npc_stat_generator.py::test_generate_goblin_stats_real_llm",
    "-v",
    "-s"
]))
