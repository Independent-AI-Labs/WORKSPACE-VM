"""Unit tests for config_utils module."""

from pathlib import Path
from unittest.mock import patch

from workspace.config_utils import (
    _ProjectRootCache,
    get_config_path,
    get_project_root,
    get_vendor_config_path,
)


class TestGetConfigPath:
    """Tests for get_config_path function."""

    @patch("workspace.config_utils.get_project_root")
    def test_get_config_path_returns_correct_path(self, mock_root) -> None:
        """Test that config path is constructed correctly."""
        mock_root.return_value = Path("/project")

        result = get_config_path("ruff.toml")

        assert result == Path("/project/res/config/ruff.toml")

    @patch("workspace.config_utils.get_project_root")
    def test_get_config_path_mypy(self, mock_root) -> None:
        """Test getting mypy config path."""
        mock_root.return_value = Path("/opt/user/project")

        result = get_config_path("mypy.toml")

        assert result == Path("/opt/user/project/res/config/mypy.toml")

    @patch("workspace.config_utils.get_project_root")
    def test_get_config_path_with_subdirectory(self, mock_root) -> None:
        """Test config path preserves filename with path separators."""
        mock_root.return_value = Path("/project")

        # Note: This passes filename as-is, doesn't handle subdirs
        result = get_config_path("patterns/banned_words.yaml")

        assert result == Path("/project/res/config/patterns/banned_words.yaml")


class TestGetVendorConfigPath:
    """Tests for get_vendor_config_path function."""

    @patch("workspace.config_utils.get_project_root")
    def test_get_vendor_config_path_cuda(self, mock_root) -> None:
        """Test getting CUDA vendor config path."""
        mock_root.return_value = Path("/project")

        result = get_vendor_config_path("sources-cuda.toml")

        assert result == Path("/project/res/config/vendor/sources-cuda.toml")

    @patch("workspace.config_utils.get_project_root")
    def test_get_vendor_config_path_rocm(self, mock_root) -> None:
        """Test getting ROCm vendor config path."""
        mock_root.return_value = Path("/opt/user/project")

        result = get_vendor_config_path("requirements-rocm.txt")

        assert result == Path(
            "/opt/user/project/res/config/vendor/requirements-rocm.txt"
        )

    @patch("workspace.config_utils.get_project_root")
    def test_get_vendor_config_path_mps(self, mock_root) -> None:
        """Test getting MPS (Apple Silicon) vendor config path."""
        mock_root.return_value = Path("/project")

        result = get_vendor_config_path("sources-mps.toml")

        assert result == Path("/project/res/config/vendor/sources-mps.toml")


class TestGetProjectRoot:
    def test_uses_cached_value(self) -> None:
        cached = Path("/cached/root")
        _ProjectRootCache.set(cached)
        try:
            result = get_project_root()
            assert result == cached
        finally:
            _ProjectRootCache._value = None

    def test_uses_env_var(self, monkeypatch) -> None:
        monkeypatch.setenv("AMI_PROJECT_ROOT", "/env/project")
        _ProjectRootCache._value = None
        try:
            result = get_project_root()
            assert result == Path("/env/project")
        finally:
            _ProjectRootCache._value = None

    def test_cached_value_persists(self) -> None:
        path = Path("/cached/value")
        _ProjectRootCache.set(path)
        try:
            result = get_project_root()
            assert result == path
        finally:
            _ProjectRootCache._value = None


class TestProjectRootCache:
    def test_get_returns_none_initially(self) -> None:
        _ProjectRootCache._value = None
        assert _ProjectRootCache.get() is None

    def test_set_and_get(self) -> None:
        path = Path("/some/path")
        _ProjectRootCache.set(path)
        try:
            assert _ProjectRootCache.get() == path
        finally:
            _ProjectRootCache._value = None
