"""Unit tests for config_utils module."""

from pathlib import Path

from workspace.config_utils import (
    _ProjectRootCache,
    get_project_root,
)


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
