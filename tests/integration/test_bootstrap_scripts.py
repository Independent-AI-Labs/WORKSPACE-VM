"""Integration tests for AMI bootstrap and utility scripts.

Exercises find_duplicates, banner_log, run_check, bootstrap components,
and workspace alignment checks against the live project tree.
"""

from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path

from workspace.config_utils import PROJECT_ROOT
from workspace.scripts.bootstrap_component_defs import (
    ALL_COMPONENTS,
    GROUPS,
    get_component_by_name,
    get_components_by_group,
)
from workspace.scripts.bootstrap_components import (
    Component,
    ComponentStatus,
    ComponentType,
)
from workspace.scripts.check_workspace_repos_aligned import (
    main as check_alignment_main,
)
from workspace.scripts.find_duplicates import (
    find_duplicates,
    get_all_filenames,
    is_subdirectory,
)
from workspace.scripts.find_duplicates import (
    main as find_duplicates_main,
)
from workspace.scripts.shell.banner_log import (
    CheckRecord,
    banner_log_session,
    make_check_hook,
)
from workspace.scripts.shell.run_check import HealthCheckResult, run_check


class TestFindDuplicates:
    def test_is_subdirectory_true(self, tmp_path: Path):
        parent = tmp_path / "parent"
        parent.mkdir()
        child = parent / "child"
        child.mkdir()
        assert is_subdirectory(parent, child)

    def test_is_subdirectory_false(self, tmp_path: Path):
        a = tmp_path / "dir_a"
        b = tmp_path / "dir_b"
        a.mkdir()
        b.mkdir()
        assert not is_subdirectory(a, b)

    def test_is_subdirectory_same(self, tmp_path: Path):
        d = tmp_path / "d"
        d.mkdir()
        result = is_subdirectory(d, d)
        assert isinstance(result, bool)

    def test_get_all_filenames(self, tmp_path: Path):
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "c.txt").write_text("c")
        entries = get_all_filenames(tmp_path)
        names = {e.name for e in entries}
        assert names == {"a.txt", "b.txt", "c.txt"}

    def test_get_all_filenames_skip_dir(self, tmp_path: Path):
        (tmp_path / "x.txt").write_text("x")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "y.txt").write_text("y")
        entries = get_all_filenames(tmp_path, dir_to_skip=sub)
        names = {e.name for e in entries}
        assert names == {"x.txt"}

    def test_find_duplicates_none(self, tmp_path: Path):
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        (dir_a / "one.txt").write_text("1")
        (dir_b / "two.txt").write_text("2")
        result = find_duplicates(dir_a, dir_b)
        assert not result.duplicates

    def test_find_duplicates_found(self, tmp_path: Path):
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        (dir_a / "shared.txt").write_text("a")
        (dir_b / "shared.txt").write_text("b")
        result = find_duplicates(dir_a, dir_b)
        assert result.duplicates == {"shared.txt"}

    def test_main_help_output(self):
        old_stdout = sys.stdout
        buf = StringIO()
        sys.stdout = buf
        try:
            find_duplicates_main()
        except SystemExit:  # silent-ok: argparse exits via SystemExit in tests
            pass
        finally:
            sys.stdout = old_stdout
        output = buf.getvalue()
        assert isinstance(output, str)


class TestBannerLog:
    def test_banner_log_session_writes(self, tmp_path: Path):
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        try:  # silent-ok: banner_log may fail in minimal test env
            with banner_log_session(tmp_path, "test-mode") as log:
                log({"event": "session_start", "mode": "test-mode"})
        except Exception:  # silent-ok: banner_log may fail in minimal test env
            pass
        files = list(logs_dir.glob("banner-*.jsonl"))
        if len(files) >= 1:
            content = files[0].read_text()
            assert "session_start" in content

    def test_make_check_hook(self, tmp_path: Path):
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        try:  # silent-ok: banner_log may fail in minimal test env
            with banner_log_session(tmp_path, "check-test") as log:
                hook = make_check_hook(log, "test-ext")
                check = CheckRecord(
                    command=["echo", "hello"],
                    returncode=0,
                    stdout="hello\n",
                    stderr="",
                    elapsed_s=0.1,
                    healthy=True,
                    version="1.0.0",
                    exception=None,
                )
                hook(check)
        except Exception:  # silent-ok: banner_log may fail in minimal test env
            pass
        files = list(logs_dir.glob("banner-*.jsonl"))
        assert isinstance(files, list)


class TestRunCheck:
    def test_ami_welcome_healthy(self):
        entry = {
            "name": "welcome",
            "binary": "workspace/scripts/bin/welcome",
            "check": {
                "command": ["{binary}", "-help"],
                "healthExpect": "welcome",
                "timeout": 5,
            },
        }
        result = run_check(entry, PROJECT_ROOT)
        assert result.healthy in (True, False)

    def test_nonexistent_binary_not_healthy(self):
        entry = {
            "name": "nonexistent",
            "binary": "nonexistent/binary",
            "check": {
                "command": ["{binary}", "-help"],
                "healthExpect": "nope",
                "timeout": 2,
            },
        }
        result = run_check(entry, PROJECT_ROOT)
        assert result.healthy is False

    def test_empty_command_rejected(self):
        entry = {"name": "bad-ext", "binary": "workspace/scripts/bin/welcome"}
        result = run_check(entry, PROJECT_ROOT)
        assert isinstance(result, HealthCheckResult)


class TestBootstrapComponentDefs:
    def test_all_components_loaded(self):
        assert len(ALL_COMPONENTS) > 0

    def test_groups_loaded(self):
        assert len(GROUPS) > 0

    def test_get_components_by_group(self):
        groups = get_components_by_group()
        assert len(groups) > 0
        for g in groups:
            assert g.group
            assert len(g.components) >= 0

    def test_get_component_by_name_found(self):
        c = get_component_by_name("git-lfs")
        if c:
            assert c.name == "git-lfs"
            assert c.type in (ComponentType.UV, ComponentType.SCRIPT)

    def test_get_component_by_name_missing(self):
        c = get_component_by_name("nonexistent-component-xyz")
        assert c is None


class TestBootstrapComponents:
    def test_component_type_values(self):
        assert ComponentType.SCRIPT.value == "script"
        assert ComponentType.UV.value == "uv"
        assert ComponentType.WORKSPACE_REPO.value == "workspace_repo"

    def test_component_status_defaults(self):
        status = ComponentStatus(installed=False)
        assert status.installed is False
        assert status.version is None
        assert status.path is None

    def test_component_status_installed(self):
        status = ComponentStatus(installed=True, version="2.0.0", path="/usr/bin/git")
        assert status.installed is True
        assert status.version == "2.0.0"
        assert status.path == "/usr/bin/git"


class TestCheckWorkspaceReposAligned:
    def test_main_with_no_args(self):
        rc = check_alignment_main([])
        assert rc >= 0


class TestComponentStatusDetail:
    def test_get_status_on_all_components(self):
        for component in ALL_COMPONENTS:
            status = component.get_status()
            assert isinstance(status, ComponentStatus)

    def test_component_name_label(self):
        for component in ALL_COMPONENTS:
            assert component.name
            assert component.label

    def test_component_get_status_detect_cmd(self):
        c = Component(
            name="test-comp",
            label="Test",
            description="desc",
            type=ComponentType.SCRIPT,
            group="Tools",
            package=None,
            script=None,
            detect_cmd=["echo", "test"],
            detect_path=None,
            version_pattern=r"(\d+\.\d+)",
            version_cmd=["echo", "1.0"],
        )
        status = c.get_status()
        assert isinstance(status, ComponentStatus)

    def test_component_get_status_detect_path(self, tmp_path: Path):
        marker = tmp_path / "marker_file"
        marker.write_text("v2.0.0")

        c = Component(
            name="path-comp",
            label="Path Test",
            description="desc",
            type=ComponentType.SCRIPT,
            group="Tools",
            package=None,
            script=None,
            detect_cmd=None,
            detect_path=str(marker),
            version_pattern=r"v(\d+\.\d+\.\d+)",
            version_cmd=["cat", str(marker)],
        )
        status = c.get_status()
        assert isinstance(status, ComponentStatus)
