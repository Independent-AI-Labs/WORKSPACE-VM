"""Pytest configuration for all tests.

Handles path setup so test files can import from project modules.
"""

import sys
from pathlib import Path

# Find WORKSPACE_ROOT (agents/ directory)
_TESTS_DIR = Path(__file__).resolve().parent
_WORKSPACE_ROOT = _TESTS_DIR.parent

# Add WORKSPACE_ROOT to path for project imports
if str(_WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE_ROOT))

# Export for use in tests
WORKSPACE_ROOT = _WORKSPACE_ROOT
