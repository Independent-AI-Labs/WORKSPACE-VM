"""Unit tests for scripts/bootstrap_components module."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from workspace.scripts.bootstrap_component_defs import (
    ALL_COMPONENTS,
    GROUPS,
    WORKSPACE_REPOS,
    WORKSPACE_REPOS_GROUP,
    get_component_by_name,
    get_components_by_group,
)
from workspace.scripts.bootstrap_components import (
    Component,
    ComponentStatus,
    ComponentType,
)


class TestComponentType:
    """Tests for ComponentType enum."""

    def test_script_value(self) -> None:
        """Test SCRIPT enum value."""
        assert ComponentType.SCRIPT.value == "script"

    def test_uv_value(self) -> None:
        """Test UV enum value."""
        assert ComponentType.UV.value == "uv"


class TestComponentStatus:
    """Tests for ComponentStatus model."""

    def test_creates_installed_status(self) -> None:
        """Test creates installed status."""
        status = ComponentStatus(installed=True, version="1.0.0", path="/path/to/bin")

        assert status.installed is True
        assert status.version == "1.0.0"
        assert status.path == "/path/to/bin"

    def test_creates_not_installed_status(self) -> None:
        """Test creates not-installed status."""
        status = ComponentStatus(installed=False)

        assert status.installed is False
        assert status.version is None
        assert status.path is None


class TestComponent:
    """Tests for Component model."""

    def test_creates_component(self) -> None:
        """Test creates component with required fields."""
        comp = Component(
            name="test",
            label="Test",
            description="Test component",
            type=ComponentType.SCRIPT,
            group="Test Group",
        )

        assert comp.name == "test"
        assert comp.label == "Test"
        assert comp.type == ComponentType.SCRIPT

    @patch("workspace.scripts.bootstrap_components.PROJECT_ROOT", Path("/test/root"))
    def test_get_status_with_detect_path(self) -> None:
        """Test get_status with path detection."""
        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.SCRIPT,
            group="Test",
            detect_path="existing/path",
        )

        with patch.object(Path, "exists", return_value=True):
            status = comp.get_status()

        assert status.installed is True

    @patch("workspace.scripts.bootstrap_components.PROJECT_ROOT", Path("/test/root"))
    def test_get_status_path_not_found(self) -> None:
        """Test get_status when path not found."""
        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.SCRIPT,
            group="Test",
            detect_path="nonexistent/path",
        )

        with patch.object(Path, "exists", return_value=False):
            status = comp.get_status()

        assert status.installed is False

    @patch("workspace.scripts.bootstrap_components.PROJECT_ROOT", Path("/test/root"))
    @patch("workspace.scripts.bootstrap_components.subprocess.run")
    def test_get_status_with_detect_cmd(self, mock_run) -> None:
        """Test get_status with command detection."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="version 1.0.0", stderr=""
        )

        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.SCRIPT,
            group="Test",
            detect_cmd=["test", "--version"],
        )

        status = comp.get_status()

        assert status.installed is True
        assert status.version == "1.0.0"

    @patch("workspace.scripts.bootstrap_components.PROJECT_ROOT", Path("/test/root"))
    @patch("workspace.scripts.bootstrap_components.subprocess.run")
    def test_get_status_cmd_fails(self, mock_run) -> None:
        """Test get_status when command fails."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")

        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.SCRIPT,
            group="Test",
            detect_cmd=["nonexistent"],
        )

        status = comp.get_status()

        assert status.installed is False

    @patch("workspace.scripts.bootstrap_components.PROJECT_ROOT", Path("/test/root"))
    @patch("workspace.scripts.bootstrap_components.subprocess.run")
    def test_get_status_cmd_timeout(self, mock_run) -> None:
        """Test get_status when command times out."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=5)

        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.SCRIPT,
            group="Test",
            detect_cmd=["slow_cmd"],
        )

        status = comp.get_status()

        assert status.installed is False

    @patch("workspace.scripts.bootstrap_components.PROJECT_ROOT", Path("/test/root"))
    @patch("workspace.scripts.bootstrap_components.subprocess.run")
    def test_get_status_detect_path_with_version_cmd_success(self, mock_run) -> None:
        """detect_path + runnable + version_cmd success => installed with version."""
        mock_run.return_value = MagicMock(returncode=0, stdout="tool v2.0.0", stderr="")

        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.SCRIPT,
            group="Test",
            detect_path="bin/test",
            version_cmd=["bin/test", "--version"],
            version_pattern=r"v(\d+\.\d+\.\d+)",
        )

        with (
            patch.object(Path, "exists", return_value=True),
            patch("os.access", return_value=True),
        ):
            status = comp.get_status()

        assert status.installed is True
        assert status.version == "2.0.0"
        assert status.path is not None

    @patch("workspace.scripts.bootstrap_components.PROJECT_ROOT", Path("/test/root"))
    @patch("workspace.scripts.bootstrap_components.subprocess.run")
    def test_get_status_detect_path_version_cmd_fails(self, mock_run) -> None:
        """detect_path exists but version_cmd fails => not installed."""
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="exec format error"
        )

        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.SCRIPT,
            group="Test",
            detect_path="bin/broken",
            version_cmd=["bin/broken", "--version"],
        )

        with (
            patch.object(Path, "exists", return_value=True),
            patch("os.access", return_value=True),
        ):
            status = comp.get_status()

        assert status.installed is False

    def test_get_status_no_version_cmd_uses_runnable_only(self) -> None:
        """detect_path with no version_cmd: installed if path exists + runnable."""
        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.SCRIPT,
            group="Test",
            detect_path="bin/test",
        )

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(comp, "_runnable_binary_present", return_value=True),
        ):
            status = comp.get_status()

        assert status.installed is True
        assert status.version is None

    def test_runnable_binary_present_absolute_path(self) -> None:
        """version_cmd starting with '/' skips in-tree check, returns True."""
        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.SCRIPT,
            group="Test",
            version_cmd=["/usr/bin/tool", "--version"],
        )
        assert comp._runnable_binary_present() is True


class TestExtractVersion:
    """Tests for Component._extract_version method."""

    def test_extracts_with_custom_pattern(self) -> None:
        """Test extracts version with custom pattern."""
        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.SCRIPT,
            group="Test",
            version_pattern=r"Version: (\d+\.\d+)",
        )

        version = comp._extract_version("Version: 2.5 (stable)")

        assert version == "2.5"

    def test_extracts_semver(self) -> None:
        """Test extracts semver pattern."""
        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.SCRIPT,
            group="Test",
        )

        version = comp._extract_version("tool version 1.2.3")

        assert version == "1.2.3"

    def test_extracts_v_prefixed_version(self) -> None:
        """Test extracts v-prefixed version."""
        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.SCRIPT,
            group="Test",
        )

        version = comp._extract_version("v4.5.6")

        assert version == "4.5.6"

    def test_extracts_major_minor(self) -> None:
        """Test extracts major.minor pattern."""
        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.SCRIPT,
            group="Test",
        )

        version = comp._extract_version("release 7.8")

        assert version == "7.8"

    def test_returns_none_for_empty_output(self) -> None:
        """Test returns None for empty output."""
        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.SCRIPT,
            group="Test",
        )

        version = comp._extract_version("")

        assert version is None

    def test_returns_none_for_no_match(self) -> None:
        """Test returns None when no version found."""
        comp = Component(
            name="test",
            label="Test",
            description="Test",
            type=ComponentType.SCRIPT,
            group="Test",
        )

        version = comp._extract_version("no version here")

        assert version is None


class TestGetComponentsByGroup:
    """Tests for get_components_by_group function."""

    def test_returns_list_with_all_groups(self) -> None:
        """Test returns list with all groups."""
        result = get_components_by_group()
        group_names = {gc.group for gc in result}

        for group in GROUPS:
            assert group in group_names

    def test_components_in_correct_groups(self) -> None:
        """Test components are in their correct groups."""
        result = get_components_by_group()
        by_group = {gc.group: gc.components for gc in result}

        assert any(c.name == "opencode" for c in by_group["AI Coding Assistants"])
        assert any(
            c.name == "podman" for c in by_group["Infrastructure & Orchestration"]
        )


class TestGetComponentByName:
    """Tests for get_component_by_name function."""

    def test_finds_existing_component(self) -> None:
        """Test finds existing component by name."""
        comp = get_component_by_name("opencode")

        assert comp is not None
        assert comp.name == "opencode"

    def test_returns_none_for_nonexistent(self) -> None:
        """Test returns None for nonexistent component."""
        comp = get_component_by_name("nonexistent_component")

        assert comp is None


class TestYamlLoadedManifest:
    """Tests that the YAML manifest loaded into ALL_COMPONENTS / GROUPS is
    well-formed. Group names are derived from the manifest, not hardcoded
    here — adding/removing groups in YAML must not require a test edit."""

    def test_groups_non_empty(self) -> None:
        assert len(GROUPS) > 0

    def test_workspace_repos_group_is_last(self) -> None:
        """The dedicated Workspace Repositories group renders as the last
        group so it can also be surfaced as a separate first-step dialog."""
        assert GROUPS[-1] == WORKSPACE_REPOS_GROUP

    def test_every_group_has_at_least_one_component(self) -> None:
        for grouping in get_components_by_group():
            assert len(grouping.components) > 0, (
                f"group '{grouping.group}' has no components"
            )

    def test_every_component_belongs_to_a_declared_group(self) -> None:
        declared = set(GROUPS)
        for comp in ALL_COMPONENTS:
            assert comp.group in declared, (
                f"component {comp.name} has undeclared group {comp.group!r}"
            )

    def test_get_components_by_group_partitions_all(self) -> None:
        partitioned = sum(len(g.components) for g in get_components_by_group())
        assert partitioned == len(ALL_COMPONENTS)

    def test_workspace_repos_subset_lands_in_workspace_group(self) -> None:
        ws_group = next(
            g for g in get_components_by_group() if g.group == WORKSPACE_REPOS_GROUP
        )
        assert {c.name for c in ws_group.components} == {
            c.name for c in WORKSPACE_REPOS
        }


class TestComponentVersionParsing:
    """Tests for version parsing edge cases."""

    def test_get_version_from_cmd_no_cmd(self):
        """Test returns None when no version_cmd set."""
        comp = Component(
            name="t",
            label="t",
            description="t",
            type=ComponentType.SCRIPT,
            group="t",
        )
        assert comp._get_version_from_cmd() is None

    @patch("workspace.scripts.bootstrap_components.subprocess.run")
    def test_get_version_from_cmd_timeout(self, mock_run):
        """Test returns None on timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 5)
        comp = Component(
            name="t",
            label="t",
            description="t",
            type=ComponentType.SCRIPT,
            group="t",
            version_cmd=["test", "--version"],
        )
        assert comp._get_version_from_cmd() is None

    @patch("workspace.scripts.bootstrap_components.subprocess.run")
    def test_get_version_from_cmd_success(self, mock_run):
        """Test extracts version from successful command."""
        mock_run.return_value = MagicMock(returncode=0, stdout="test v1.2.3", stderr="")
        comp = Component(
            name="t",
            label="t",
            description="t",
            type=ComponentType.SCRIPT,
            group="t",
            version_cmd=["test", "--version"],
            version_pattern=r"v(\d+\.\d+\.\d+)",
        )
        assert comp._get_version_from_cmd() == "1.2.3"

    @patch("workspace.scripts.bootstrap_components.subprocess.run")
    def test_get_version_from_cmd_nonzero_exit(self, mock_run):
        """Test returns None on non-zero exit."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="err")
        comp = Component(
            name="t",
            label="t",
            description="t",
            type=ComponentType.SCRIPT,
            group="t",
            version_cmd=["test", "--version"],
        )
        assert comp._get_version_from_cmd() is None
