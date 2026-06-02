"""Unit tests for scripts/bootstrap_install module."""

import subprocess
from pathlib import Path
from typing import NamedTuple
from unittest.mock import MagicMock, patch

from ami.scripts.bootstrap_components import Component, ComponentType
from ami.scripts.bootstrap_install import (
    _binary_is_runnable,
    ensure_directories,
    get_bootstrap_dir,
    install_component,
    install_components,
    run_bootstrap_script,
    run_workspace_repo_clone,
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

    @patch("ami.scripts.bootstrap_install.PROJECT_ROOT", Path("/test/root"))
    def test_creates_directories(self) -> None:
        """Test creates required directories."""
        with patch.object(Path, "mkdir") as mock_mkdir:
            ensure_directories()

            # Should be called twice (for .boot-linux/bin and .venv/bin)
            assert mock_mkdir.call_count == EXPECTED_DIRECTORY_COUNT


class TestGetPaths:
    """Tests for path getter functions."""

    @patch("ami.scripts.bootstrap_install.PROJECT_ROOT", Path("/test/root"))
    def test_get_bootstrap_dir(self) -> None:
        """Test get_bootstrap_dir returns correct path."""
        result = get_bootstrap_dir()
        assert result == Path("/test/root/ami/scripts/bootstrap")


class TestRunBootstrapScript:
    """Tests for run_bootstrap_script function."""

    @patch("ami.scripts.bootstrap_install.get_bootstrap_dir")
    def test_returns_false_if_script_not_found(self, mock_dir) -> None:
        """Test returns False if script doesn't exist."""
        mock_dir.return_value = Path("/scripts")

        with patch.object(Path, "exists", return_value=False):
            result = run_bootstrap_script("test.sh")

        assert result is False

    @patch("ami.scripts.bootstrap_install.subprocess.run")
    @patch("ami.scripts.bootstrap_install.get_bootstrap_dir")
    @patch("ami.scripts.bootstrap_install.PROJECT_ROOT", Path("/root"))
    def test_runs_script(self, mock_dir, mock_run) -> None:
        """Test runs bootstrap script."""
        mock_dir.return_value = Path("/scripts")
        mock_run.return_value = MagicMock(returncode=0)

        with patch.object(Path, "exists", return_value=True):
            result = run_bootstrap_script("test.sh")

        assert result is True
        mock_run.assert_called_once()

    @patch("ami.scripts.bootstrap_install.subprocess.run")
    @patch("ami.scripts.bootstrap_install.get_bootstrap_dir")
    @patch("ami.scripts.bootstrap_install.PROJECT_ROOT", Path("/root"))
    def test_returns_false_on_script_failure(self, mock_dir, mock_run) -> None:
        """Test returns False if script fails."""
        mock_dir.return_value = Path("/scripts")
        mock_run.return_value = MagicMock(returncode=1)

        with patch.object(Path, "exists", return_value=True):
            result = run_bootstrap_script("test.sh")

        assert result is False


class TestInstallComponent:
    """Tests for install_component function."""

    @patch("ami.scripts.bootstrap_install.run_bootstrap_script", return_value=True)
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

    @patch("ami.scripts.bootstrap_install.run_workspace_repo_clone", return_value=True)
    def test_installs_workspace_repo_via_walker(self, mock_walker) -> None:
        """Test WORKSPACE_REPO routes to bootstrap-repos walker."""
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
        mock_walker.assert_called_once_with("ami-portal")


class TestInstallComponents:
    """Tests for install_components function."""

    @patch("ami.scripts.bootstrap_install.ensure_directories")
    @patch("ami.scripts.bootstrap_install.install_component", return_value=True)
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

    @patch("ami.scripts.bootstrap_install.ensure_directories")
    @patch("ami.scripts.bootstrap_install.install_component", return_value=True)
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

    @patch("ami.scripts.bootstrap_install.ensure_directories")
    @patch("ami.scripts.bootstrap_install.install_component", return_value=True)
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


class TestInstallEdgeCases:
    """Tests for install edge cases."""

    @patch("ami.scripts.bootstrap_install.subprocess.run")
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


class TestScriptDetectPathOverride:
    """install_component returns True if script fails but detect_path exists."""

    @patch("ami.scripts.bootstrap_install._binary_is_runnable", return_value=True)
    @patch("ami.scripts.bootstrap_install.run_bootstrap_script", return_value=False)
    def test_detect_path_exists_after_script_failure(
        self, mock_run, mock_runnable
    ) -> None:
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
            assert install_component(comp) is True

    @patch("ami.scripts.bootstrap_install._binary_is_runnable", return_value=False)
    @patch("ami.scripts.bootstrap_install.run_bootstrap_script", return_value=False)
    def test_detect_path_no_runnable_returns_false(
        self, mock_run, mock_runnable
    ) -> None:
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


class TestBinaryIsRunnable:
    """Tests for _binary_is_runnable helper."""

    def test_no_version_cmd_returns_true(self) -> None:
        comp = Component(
            name="x",
            label="x",
            description="x",
            type=ComponentType.SCRIPT,
            group="Test",
        )
        assert _binary_is_runnable(comp) is True

    def test_absolute_path_returns_true(self) -> None:
        comp = Component(
            name="x",
            label="x",
            description="x",
            type=ComponentType.SCRIPT,
            group="Test",
            version_cmd=["/usr/bin/true", "--version"],
        )
        assert _binary_is_runnable(comp) is True

    def test_in_tree_missing_returns_false(self) -> None:
        comp = Component(
            name="x",
            label="x",
            description="x",
            type=ComponentType.SCRIPT,
            group="Test",
            version_cmd=["does/not/exist/binary", "--version"],
        )
        assert _binary_is_runnable(comp) is False


class TestRunBootstrapScriptOSError:
    """Cover run_bootstrap_script's OSError except branch."""

    @patch("ami.scripts.bootstrap_install.subprocess.run")
    @patch("ami.scripts.bootstrap_install.get_bootstrap_dir")
    def test_subprocess_error_propagates_false(self, mock_dir, mock_run) -> None:
        mock_dir.return_value = Path("/scripts")
        mock_run.side_effect = subprocess.SubprocessError("boom")
        with patch.object(Path, "exists", return_value=True):
            assert run_bootstrap_script("t.sh") is False


class TestRunWorkspaceRepoClone:
    """Tests for run_workspace_repo_clone helper."""

    @patch("ami.scripts.bootstrap_install.subprocess.run")
    def test_invokes_ami_bootstrap_repos_with_include(self, mock_run) -> None:
        """Test routes to bootstrap-repos --include <id>."""
        mock_run.return_value = MagicMock(returncode=0)
        with patch.object(Path, "exists", return_value=True):
            assert run_workspace_repo_clone("ami-portal") is True
        args = mock_run.call_args[0][0]
        assert args[0] == "bash"
        assert args[-2] == "--include"
        assert args[-1] == "ami-portal"

    @patch("ami.scripts.bootstrap_install.subprocess.run")
    def test_returns_false_on_walker_failure(self, mock_run) -> None:
        """Test returns False if walker exits non-zero."""
        mock_run.return_value = MagicMock(returncode=1)
        with patch.object(Path, "exists", return_value=True):
            assert run_workspace_repo_clone("ami-portal") is False

    def test_returns_false_if_walker_missing(self) -> None:
        """Test returns False if bootstrap-repos does not exist."""
        with patch.object(Path, "exists", return_value=False):
            assert run_workspace_repo_clone("ami-portal") is False

    @patch("ami.scripts.bootstrap_install.subprocess.run")
    def test_handles_oserror(self, mock_run) -> None:
        """Test catches OSError from subprocess.run."""
        mock_run.side_effect = OSError("exec failed")
        with patch.object(Path, "exists", return_value=True):
            assert run_workspace_repo_clone("ami-portal") is False
