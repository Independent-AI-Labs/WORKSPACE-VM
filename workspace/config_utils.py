"""Configuration utilities for ami-agents package.

Project root discovery utilities - moved here from ami/core/env.py during
the V3 migration to avoid deleting infrastructure used by staying scripts.
"""

import os
from pathlib import Path


class _ProjectRootCache:
    """Cache for project root to avoid repeated filesystem lookups."""

    _value: Path | None = None

    @classmethod
    def get(cls) -> Path | None:
        """Get cached project root."""
        return cls._value

    @classmethod
    def set(cls, path: Path) -> None:
        """Set cached project root."""
        cls._value = path


def get_project_root() -> Path:
    """Get the project root directory.

    Finds root by looking for pyproject.toml or .git marker files.
    Falls back to AMI_PROJECT_ROOT environment variable if set.
    """
    cached = _ProjectRootCache.get()
    if cached is not None:
        return cached

    env_root = os.environ.get("AMI_PROJECT_ROOT")
    if env_root:
        result = Path(env_root)
        _ProjectRootCache.set(result)
        return result

    current = Path(__file__).resolve()
    while current != current.parent:
        if (current / "pyproject.toml").exists() or (current / ".git").exists():
            _ProjectRootCache.set(current)
            return current
        current = current.parent

    msg = "project root not found"
    raise RuntimeError(msg)


PROJECT_ROOT = get_project_root()
