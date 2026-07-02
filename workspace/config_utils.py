"""Configuration utilities for ami-agents package.

This module provides utilities for accessing shared configuration files
and project root discovery - moved here from ami/core/env.py during the
V3 migration to avoid deleting infrastructure used by staying scripts.
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


def get_config_path(config_name: str) -> Path:
    """Get the path to a shared configuration file.

    Args:
        config_name: Name of the configuration file (e.g., "ruff.toml", "mypy.toml")

    Returns:
        Path to the configuration file
    """
    return get_project_root() / "res" / "config" / config_name


def get_vendor_config_path(config_name: str) -> Path:
    """Get the path to a vendor-specific configuration file.

    Args:
        config_name: Name of the vendor configuration file (e.g., "sources-cuda.toml")

    Returns:
        Path to the vendor configuration file
    """
    return get_project_root() / "res" / "config" / "vendor" / config_name
