"""Integration test fixtures for workspace package."""

import subprocess
from unittest.mock import MagicMock

import pytest

try:
    import psutil as _psutil
except ImportError:
    _psutil = None


@pytest.fixture(autouse=True)
def _patch_subprocess(monkeypatch) -> None:
    mock_result = MagicMock()
    mock_result.stdout = ""
    mock_result.stderr = ""
    mock_result.returncode = 0
    monkeypatch.setattr(subprocess, "run", MagicMock(return_value=mock_result))

    if _psutil is not None:
        mock_disk = MagicMock()
        mock_disk.percent = 50.0
        mock_disk.used = 1000000000
        mock_disk.total = 10000000000
        monkeypatch.setattr(_psutil, "disk_usage", MagicMock(return_value=mock_disk))
