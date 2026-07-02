"""Unit tests for scripts/bootstrap_install module."""

import subprocess
from pathlib import Path
from typing import NamedTuple
from unittest.mock import MagicMock, patch

from workspace.scripts.bootstrap_components import Component, ComponentType
from workspace.scripts.bootstrap_install import (
    _pull_workspace_repo,
    ensure_directories,
    get_bootstrap_dir,
    install_component,
    install_components,
    run_bootstrap_script,
)


class ProgressCall(NamedTuple):
    """Progress callback invocation data."""

    current: int
    total: int
    label: str


class ResultCall(NamedTuple):
    """Result callback invocation data."""

    component: Component
    success: bool


EXPECTED_DIRECTORY_COUNT = 2
EXPECTED_SCRIPT_INSTALL_CALL_COUNT = 2
EXPECTED_COMPONENT_RESULT_COUNT = 2


class TestEnsureDirectories:
    """Tests for ensure_directories function."""

    @patch("workspace.scripts.bootstrap_install._PROJECT_ROOT", Path("/test/root"))
    def test_creates_directories(self) -> None:
        """Test creates required directories."""
        with patch.object(Path, "mkdir") as mock_mkdir:
            ensure_directories()

            # Should be called twice (for .boot-linux/bin and .venv/bin)
            assert mock_mkdir.call_count == EXPECTED_DIRECTORY_COUNT


class TestGetPaths:
    """Tests for path getter functions."""

    @patch("workspace.scripts.bootstrap_install._PROJECT_ROOT", Path("/test/root"))
    def test_get_bootstrap_dir(self) -> None:
        """Test get_bootstrap_dir returns correct path."""
        result = get_bootstrap_dir()
        assert result == Path("/test/root/workspace/scripts/bootstrap")


class TestRunBootstrapScript:
    """Tests for run_bootstrap_script function."""

    @patch("workspace.scripts.bootstrap_install.get_bootstrap_dir")
    def test_returns_false_if_script_not_found(self, mock_dir) -> None:
        """Test returns False if script doesn't exist."""
        mock_dir.return_value = Path("/scripts")

        with patch.object(Path, "exists", return_value=False):
            result = run_bootstrap_script("test.sh")

        assert result is False

    @patch("workspace.scripts.bootstrap_install.subprocess.run")
    @patch("workspace.scripts.bootstrap_install.get_bootstrap_dir")
    def test_runs_script(self, mock_dir, mock_run) -> None:
        """Test runs bootstrap script."""
        mock_dir.return_value = Path("/scripts")
        mock_run.return_value = MagicMock(returncode=0)

        with patch.object(Path, "exists", return_value=True):
            result = run_bootstrap_script("test.sh")

        assert result is True
        mock_run.assert_called_once()

    @patch("workspace.scripts.bootstrap_install.subprocess.run")
    @patch("workspace.scripts.bootstrap_install.get_bootstrap_dir")
    def test_returns_false_on_script_failure(self, mock_dir, mock_run) -> None:
        """Test returns False if script fails."""
        mock_dir.return_value = Path("/scripts")
        mock_run.side_effect = subprocess.CalledProcessError(
            1, ["bash", "/scripts/test.sh"]
        )

        with patch.object(Path, "exists", return_value=True):
            result = run_bootstrap_script("test.sh")

        assert result is False


class TestInstallComponent:
    """Tests for install_component function."""

    @patch(
        "workspace.scripts.bootstrap_install.run_bootstrap_script", return_value=True
    )
    def test_installs_script_component(self, mock_run) -> None:
        """Test installs script component."""
        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.SCRIPT,
            group="Test",
            script="test.sh",
        )

        result = install_component(comp)

        assert result is True
        mock_run.assert_called_once_with("test.sh")

    def test_returns_false_for_script_without_script(self) -> None:
        """Test returns False for script component without script."""
        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.SCRIPT,
            group="Test",
        )

        result = install_component(comp)

        assert result is False

    def test_returns_true_for_uv_component(self) -> None:
        """Test returns True for UV component (no action needed)."""
        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.UV,
            group="Test",
        )

        result = install_component(comp)

        assert result is True

    @patch(
        "workspace.scripts.bootstrap_install._pull_workspace_repo",
    )
    def test_installs_workspace_repo_via_pull(self, mock_pull) -> None:
        """Test WORKSPACE_REPO pulls existing repo."""
        comp = Component(
            name="ami-portal",
            label="ami-portal",
            description="[optional] git@example.com:foo.git -> projects/AMI-PORTAL",
            type=ComponentType.WORKSPACE_REPO,
            group="Workspace Repositories",
            detect_path="projects/AMI-PORTAL",
        )

        result = install_component(comp)

        assert result is True
        mock_pull.assert_called_once()


class TestInstallComponents:
    """Tests for install_components function."""

    @patch("workspace.scripts.bootstrap_install.ensure_directories")
    @patch("workspace.scripts.bootstrap_install.install_component", return_value=True)
    def test_installs_script_components_separately(
        self, mock_install, mock_dirs
    ) -> None:
        """Test installs script components one at a time."""
        comps = [
            Component(
                name="a",
                label="A",
                description="A",
                type=ComponentType.SCRIPT,
                group="Test",
                script="a.sh",
            ),
            Component(
                name="b",
                label="B",
                description="B",
                type=ComponentType.SCRIPT,
                group="Test",
                script="b.sh",
            ),
        ]

        results = install_components(comps)

        # Results is now a list of InstallationResult
        assert len(results) == EXPECTED_COMPONENT_RESULT_COUNT
        names = [r["component_name"] for r in results]
        assert "a" in names
        assert "b" in names
        assert all(r["success"] for r in results)
        assert mock_install.call_count == EXPECTED_SCRIPT_INSTALL_CALL_COUNT

    @patch("workspace.scripts.bootstrap_install.ensure_directories")
    @patch("workspace.scripts.bootstrap_install.install_component", return_value=True)
    def test_calls_progress_callback(self, mock_install, mock_dirs) -> None:
        """Test calls progress callback."""
        progress_calls: list[ProgressCall] = []

        def on_progress(current: int, total: int, label: str) -> None:
            progress_calls.append(ProgressCall(current, total, label))

        comps = [
            Component(
                name="a",
                label="A",
                description="A",
                type=ComponentType.SCRIPT,
                group="Test",
                script="a.sh",
            ),
        ]

        install_components(comps, on_progress=on_progress)

        assert len(progress_calls) == 1

    @patch("workspace.scripts.bootstrap_install.ensure_directories")
    @patch("workspace.scripts.bootstrap_install.install_component", return_value=True)
    def test_calls_result_callback(self, mock_install, mock_dirs) -> None:
        """Test calls result callback."""
        result_calls: list[ResultCall] = []

        def on_result(comp: Component, success: bool) -> None:
            result_calls.append(ResultCall(comp, success))

        comps = [
            Component(
                name="a",
                label="A",
                description="A",
                type=ComponentType.SCRIPT,
                group="Test",
                script="a.sh",
            ),
        ]

        install_components(comps, on_result=on_result)

        assert len(result_calls) == 1
        assert result_calls[0].success is True

    @patch("workspace.scripts.bootstrap_install.ensure_directories")
    @patch("workspace.scripts.bootstrap_install.install_component", return_value=True)
    def test_installs_core_deps_with_result_callback(
        self, mock_install, mock_dirs
    ) -> None:
        """Core Dependencies group uses _install_core_deps path with callbacks."""
        result_calls: list[ResultCall] = []
        progress_calls: list[ProgressCall] = []

        def on_result(comp: Component, success: bool) -> None:
            result_calls.append(ResultCall(comp, success))

        def on_progress(current: int, total: int, label: str) -> None:
            progress_calls.append(ProgressCall(current, total, label))

        comps = [
            Component(
                name="uv",
                label="uv",
                description="Python package manager",
                type=ComponentType.SCRIPT,
                group="Core Dependencies",
                script="bootstrap_uv.sh",
            ),
        ]

        results = install_components(
            comps, on_progress=on_progress, on_result=on_result
        )

        names = [r["component_name"] for r in results]
        assert "uv" in names
        assert len(result_calls) == 1
        assert result_calls[0].success is True
        assert len(progress_calls) == 1


class TestInstallEdgeCases:
    """Tests for install edge cases."""

    @patch("workspace.scripts.bootstrap_install.subprocess.run")
    def test_run_script_oserror(self, mock_run):
        """Test run_bootstrap_script handles OSError."""
        mock_run.side_effect = OSError("exec failed")
        result = run_bootstrap_script("fail.sh")
        assert result is False

    def test_install_uv_type_returns_true(self):
        """Test UV type components always return True."""
        comp = Component(
            name="uv_pkg",
            label="UV Pkg",
            description="test",
            type=ComponentType.UV,
            group="Test",
        )
        result = install_component(comp)
        assert result is True

    def test_install_script_no_script(self):
        """Test script type with no script returns False."""
        comp = Component(
            name="bad",
            label="Bad",
            description="test",
            type=ComponentType.SCRIPT,
            group="Test",
        )
        result = install_component(comp)
        assert result is False


class TestScriptFailureNotRescuedByDetectPath:
    """install_component returns False when script fails, regardless of detect_path."""

    @patch(
        "workspace.scripts.bootstrap_install.run_bootstrap_script", return_value=False
    )
    def test_script_failure_returns_false(self, mock_run) -> None:
        comp = Component(
            name="t",
            label="T",
            description="t",
            type=ComponentType.SCRIPT,
            group="Test",
            script="t.sh",
            detect_path="some/path",
        )
        with patch.object(Path, "exists", return_value=True):
            assert install_component(comp) is False


class TestRunBootstrapScriptOSError:
    """Cover run_bootstrap_script's OSError except branch."""

    @patch("workspace.scripts.bootstrap_install.subprocess.run")
    @patch("workspace.scripts.bootstrap_install.get_bootstrap_dir")
    def test_subprocess_error_propagates_false(self, mock_dir, mock_run) -> None:
        mock_dir.return_value = Path("/scripts")
        mock_run.side_effect = subprocess.SubprocessError("boom")
        with patch.object(Path, "exists", return_value=True):
            assert run_bootstrap_script("t.sh") is False


class TestPullWorkspaceRepo:
    """Tests for _pull_workspace_repo helper."""

    @patch("workspace.scripts.bootstrap_install.subprocess.run")
    def test_pulls_existing_repo(self, mock_run) -> None:
        comp = Component(
            name="test",
            label="T",
            description="T",
            type=ComponentType.WORKSPACE_REPO,
            group="Workspace Repositories",
            detect_path="projects/TEST",
        )
        with patch.object(Path, "exists", return_value=True):
            _pull_workspace_repo(comp)
        mock_run.assert_called_once()

    @patch("workspace.scripts.bootstrap_install.subprocess.run")
    def test_skips_when_no_detect_path(self, mock_run) -> None:
        comp = Component(
            name="test",
            label="T",
            description="T",
            type=ComponentType.WORKSPACE_REPO,
            group="Workspace Repositories",
        )
        _pull_workspace_repo(comp)
        mock_run.assert_not_called()

    @patch("workspace.scripts.bootstrap_install.subprocess.run")
    def test_clones_missing_repo_via_bootstrap(self, mock_run) -> None:
        """Missing repo (no .git) calls bootstrap-repos -include."""
        comp = Component(
            name="ami-portal",
            label="T",
            description="T",
            type=ComponentType.WORKSPACE_REPO,
            group="Workspace Repositories",
            detect_path="projects/PORTAL",
        )
        with patch.object(Path, "exists", return_value=False):
            _pull_workspace_repo(comp)
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "bash"
        assert "-include" in call_args
        assert call_args[-1] == "ami-portal"

    @patch("workspace.scripts.bootstrap_install.subprocess.run")
    def test_clone_failure_does_not_crash(self, mock_run) -> None:
        """bootstrap-repos failure prints error but does not raise."""
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd="bootstrap-repos"
        )
        comp = Component(
            name="ami-portal",
            label="T",
            description="T",
            type=ComponentType.WORKSPACE_REPO,
            group="Workspace Repositories",
            detect_path="projects/PORTAL",
        )
        with patch.object(Path, "exists", return_value=False):
            _pull_workspace_repo(comp)
        mock_run.assert_called_once()


class TestRunScriptPath:
    """Tests for _run_script_path (script_path install path)."""

    @patch("workspace.scripts.bootstrap_install.subprocess.run")
    @patch("workspace.scripts.bootstrap_install._PROJECT_ROOT", Path("/test/root"))
    def test_runs_script_path_success(self, mock_run) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        comp = Component(
            name="test",
            label="T",
            description="t",
            type=ComponentType.SCRIPT,
            group="Test",
            script_path="projects/CI/scripts/bootstrap-gitleaks",
        )
        with patch.object(Path, "exists", return_value=True):
            result = install_component(comp)
        assert result is True
        mock_run.assert_called_once()

    @patch("workspace.scripts.bootstrap_install.subprocess.run")
    @patch("workspace.scripts.bootstrap_install._PROJECT_ROOT", Path("/test/root"))
    def test_runs_script_path_failure(self, mock_run) -> None:
        mock_run.side_effect = subprocess.CalledProcessError(
            1, ["bash", str(Path("/test/root/projects/CI/scripts/bootstrap-gitleaks"))]
        )
        comp = Component(
            name="test",
            label="T",
            description="t",
            type=ComponentType.SCRIPT,
            group="Test",
            script_path="projects/CI/scripts/bootstrap-gitleaks",
        )
        with patch.object(Path, "exists", return_value=True):
            result = install_component(comp)
        assert result is False

    @patch("workspace.scripts.bootstrap_install._PROJECT_ROOT", Path("/test/root"))
    def test_script_path_not_found(self) -> None:
        comp = Component(
            name="test",
            label="T",
            description="t",
            type=ComponentType.SCRIPT,
            group="Test",
            script_path="nonexistent/script.sh",
        )
        with patch.object(Path, "exists", return_value=False):
            result = install_component(comp)
        assert result is False

    @patch("workspace.scripts.bootstrap_install.subprocess.run")
    @patch("workspace.scripts.bootstrap_install._PROJECT_ROOT", Path("/test/root"))
    def test_script_path_oserror(self, mock_run) -> None:
        mock_run.side_effect = OSError("exec failed")
        comp = Component(
            name="test",
            label="T",
            description="t",
            type=ComponentType.SCRIPT,
            group="Test",
            script_path="projects/CI/scripts/bootstrap-gitleaks",
        )
        with patch.object(Path, "exists", return_value=True):
            result = install_component(comp)
        assert result is False
