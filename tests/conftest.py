"""
pytest configuration file for test suite.

Adds external/dnd_engine to Python path to enable imports from dnd module.
"""

import sys
from pathlib import Path

# Add dnd_engine to path
project_root = Path(__file__).parent.parent
dnd_engine_path = project_root / "external" / "dnd_engine"
sys.path.insert(0, str(dnd_engine_path))
