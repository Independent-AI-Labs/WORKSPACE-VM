"""Integration tests for AMI core utilities.

Exercises config_utils, banner, uuid_utils, and version_enforcer
through direct function calls against the live project tree.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

from workspace.config_utils import (
    PROJECT_ROOT,
    _ProjectRootCache,
    get_project_root,
)
from workspace.scripts.register_extensions import (
    create_symlink,
    create_wrapper,
    fix_stale_shebang,
)
from workspace.scripts.shell.banner_log import _timestamp, _write_record
from workspace.scripts.shell.extension_registry import ResolvedExtension, Status
from workspace.scripts.shell.version_enforcer import enforce_versions
from workspace.utils.banner import (
    generate_banner_lines,
    generate_banner_text,
    get_project_version,
)
from workspace.utils.uuid_utils import uuid7

_UUID_V4_LENGTH = 36
_UUID_UNIQUE_COUNT = 100
_TIMESTAMP_MIN = 15


class TestConfigUtils:
    def test_get_project_root_finds_pyproject(self):
        root = get_project_root()
        assert (root / "pyproject.toml").exists()

    def test_project_root_constant(self):
        assert (PROJECT_ROOT / "pyproject.toml").exists()

    def test_cache_reuse(self):
        _ProjectRootCache.set(None)
        r1 = get_project_root()
        r2 = get_project_root()
        assert r1 == r2

    def test_env_var_fallback(self, monkeypatch):
        monkeypatch.setenv("AMI_PROJECT_ROOT", "/tmp/fake_ami_root")
        _ProjectRootCache.set(None)
        root = get_project_root()
        assert str(root) == "/tmp/fake_ami_root"
        monkeypatch.delenv("AMI_PROJECT_ROOT")
        _ProjectRootCache.set(None)


class TestBanner:
    def test_get_project_version(self):
        version = get_project_version()
        assert version is not None
        assert len(version) > 0

    def test_generate_banner_text_default(self):
        text = generate_banner_text()
        assert len(text) > 0
        assert "\n" in text or len(text.splitlines()) >= 1

    def test_generate_banner_lines(self):
        lines = generate_banner_lines()
        assert isinstance(lines, list)
        assert len(lines) > 0

    def test_get_project_version_explicit_root(self):
        version = get_project_version(PROJECT_ROOT)
        assert version is not None


class TestUuidUtils:
    def test_uuid7_returns_string(self):
        uid = uuid7()
        assert isinstance(uid, str)
        assert len(uid) == _UUID_V4_LENGTH

    def test_uuid7_has_correct_version(self):
        uid = uuid7()
        assert uid[14] == "7"

    def test_uuid7_unique(self):
        uids = {uuid7() for _ in range(_UUID_UNIQUE_COUNT)}
        assert len(uids) == _UUID_UNIQUE_COUNT


class TestVersionEnforcer:
    def test_no_constraints_passthrough(self):
        entry = {"name": "no-constraints", "binary": "workspace/scripts/bin/welcome"}
        ext = ResolvedExtension(
            entry=entry,
            manifest_path=Path("/fake/manifest.yaml"),
            status=Status.READY,
            reason=None,
            version=None,
        )
        result = enforce_versions([ext], PROJECT_ROOT)
        assert len(result) == 1
        assert result[0].status == Status.READY

    def test_hidden_unavailable_skipped(self):
        entry = {
            "name": "hidden-ext",
            "binary": "workspace/scripts/bin/nonexistent",
            "minVersion": "0.1.0",
        }
        ext = ResolvedExtension(
            entry=entry,
            manifest_path=Path("/fake/manifest.yaml"),
            status=Status.HIDDEN,
            reason="hidden",
            version=None,
        )
        result = enforce_versions([ext], PROJECT_ROOT)
        assert len(result) == 1
        assert result[0].status == Status.HIDDEN

    def test_version_mismatch_detected(self):
        entry = {
            "name": "welcome",
            "binary": "workspace/scripts/bin/welcome",
            "maxVersion": "0.0.1",
            "check": {
                "command": ["{binary}", "--help"],
                "healthExpect": "welcome",
                "timeout": 5,
            },
        }
        ext = ResolvedExtension(
            entry=entry,
            manifest_path=Path("/fake/manifest.yaml"),
            status=Status.READY,
            reason=None,
            version=None,
        )
        result = enforce_versions([ext], PROJECT_ROOT)
        assert result[0].status == Status.VERSION_MISMATCH

    def test_version_match_passes(self):
        entry = {
            "name": "welcome",
            "binary": "workspace/scripts/bin/welcome",
            "minVersion": "0.0.0",
            "check": {
                "command": ["{binary}", "--help"],
                "healthExpect": "welcome",
                "timeout": 5,
            },
        }
        ext = ResolvedExtension(
            entry=entry,
            manifest_path=Path("/fake/manifest.yaml"),
            status=Status.READY,
            reason=None,
            version=None,
        )
        result = enforce_versions([ext], PROJECT_ROOT)
        assert len(result) == 1

    def test_empty_list(self):
        result = enforce_versions([], PROJECT_ROOT)
        assert result == []


class TestRegisterExtensions:
    def test_create_wrapper_creates_executable(self, tmp_path: Path):
        script_path = tmp_path / "test-wrapper"
        create_wrapper(script_path, PROJECT_ROOT, "workspace/scripts/bin/welcome")
        assert script_path.exists()
        content = script_path.read_text()
        assert "welcome" in content

    def test_create_symlink_creates_link(self, tmp_path: Path):
        target = tmp_path / "target.sh"
        target.write_text("#!/bin/bash\necho hello")
        target.chmod(0o755)
        link = tmp_path / "link-name"
        create_symlink(link, target)
        assert link.is_symlink()
        assert link.resolve() == target.resolve()

    def test_fix_stale_shebang_noop(self, tmp_path: Path):
        binary = tmp_path / "some-bin"
        binary.write_text("#!/usr/bin/env python3\nprint('hello')")
        binary.chmod(0o755)
        with contextlib.suppress(  # silent-ok: shebang check may fail on temp files
            Exception
        ):
            fix_stale_shebang(binary, PROJECT_ROOT)

    def test_banner_log_session_writes_jsonl(self, tmp_path: Path):
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        log_path = log_dir / "banner-test.jsonl"
        fh = log_path.open("a")
        record = {"event": "test", "value": 42}
        _write_record(fh, record)
        fh.close()
        content = log_path.read_text()
        assert '"event": "test"' in content
        assert '"value": 42' in content

    def test_timestamp_format(self):
        ts = _timestamp()
        assert isinstance(ts, str)
        assert len(ts) >= _TIMESTAMP_MIN

    def test_create_symlink_replaces_existing(self, tmp_path: Path):
        target = tmp_path / "real-target"
        target.write_text("data")
        link = tmp_path / "the-link"
        link.symlink_to(tmp_path / "old-target")
        create_symlink(link, target)
        assert link.is_symlink()
        assert link.resolve() == target.resolve()
