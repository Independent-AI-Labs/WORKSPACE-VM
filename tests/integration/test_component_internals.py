"""Additional integration coverage for bootstrap components internals."""

from __future__ import annotations

from pathlib import Path

from workspace.scripts.bootstrap_components import (
    Component,
    ComponentStatus,
    ComponentType,
)
from workspace.scripts.find_duplicates import (
    DuplicateResult,
    find_duplicates,
    get_all_filenames,
)

_UUID_V4_LENGTH = 36


class TestComponentMethods:
    def test_extract_version_regex_match(self):
        c = Component(
            name="test-extract",
            label="Extract",
            description="Test version extraction",
            type=ComponentType.SCRIPT,
            group="Tools",
            package=None,
            script=None,
            detect_cmd=["echo", "test"],
            detect_path=None,
            version_pattern=r"v?(\d+\.\d+\.\d+)",
            version_cmd=None,
        )
        v = c._extract_version("tool version v2.3.1 installed")
        assert v == "2.3.1"

    def test_extract_version_no_match(self):
        c = Component(
            name="test-nomatch",
            label="NoMatch",
            description="desc",
            type=ComponentType.SCRIPT,
            group="Tools",
            package=None,
            script=None,
            detect_cmd=["echo", "test"],
            detect_path=None,
            version_pattern=r"v(\d+\.\d+)",
            version_cmd=None,
        )
        v = c._extract_version("no version here")
        assert v is None

    def test_runnable_binary_present_file(self, tmp_path: Path):
        fake = tmp_path / "cmd"
        fake.write_text("#!/bin/sh\necho 1.0\n")
        fake.chmod(0o755)

        c = Component(
            name="runnable",
            label="R",
            description="d",
            type=ComponentType.SCRIPT,
            group="Tools",
            package=None,
            script=None,
            detect_cmd=["echo", "test"],
            detect_path=None,
            version_pattern=r"(\d+\.\d+)",
            version_cmd=[str(fake)],
        )
        result = c._runnable_binary_present()
        assert isinstance(result, bool)

    def test_get_version_from_cmd(self, tmp_path: Path):
        fake = tmp_path / "vercmd"
        fake.write_text("#!/bin/sh\necho version 3.1.4\n")
        fake.chmod(0o755)

        c = Component(
            name="ver-cmd",
            label="V",
            description="d",
            type=ComponentType.SCRIPT,
            group="Tools",
            package=None,
            script=None,
            detect_cmd=["echo", "test"],
            detect_path=None,
            version_pattern=r"(\d+\.\d+\.\d+)",
            version_cmd=[str(fake)],
        )
        v = c._get_version_from_cmd()
        assert v == "3.1.4"

    def test_component_status_serialization(self):
        s = ComponentStatus(installed=True, version="1.0", path="/tmp/x")
        d = s.model_dump()
        assert d["installed"] is True
        assert d["version"] == "1.0"
        assert d["path"] == "/tmp/x"


class TestFindDuplicatesMore:
    def test_find_duplicates_result_structure(self, tmp_path: Path):
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        (dir_a / "x.txt").write_text("x")
        (dir_b / "y.txt").write_text("y")
        result = find_duplicates(dir_a, dir_b)
        assert isinstance(result, DuplicateResult)
        assert not result.duplicates
        assert isinstance(result.entries_a, list)
        assert isinstance(result.entries_b, list)

    def test_get_all_filenames_path_object(self, tmp_path: Path):
        (tmp_path / "f1.txt").write_text("1")
        sub = tmp_path / "s"
        sub.mkdir()
        (sub / "f2.txt").write_text("2")
        entries = get_all_filenames(str(tmp_path))
        names = {e.name for e in entries}
        assert "f1.txt" in names
        assert "f2.txt" in names
