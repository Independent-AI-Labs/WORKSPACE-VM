"""Tests for auxiliary action construction and scope gates."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from workspace.scripts.bootstrap_aux import (
    AuxResult,
    build_commands,
    detect_configured,
    run_feature,
    run_selected,
)
from workspace.scripts.bootstrap_aux_defs import AuxArg, AuxFeature, Scope


def _feature(action: str, scope: Scope = "agent") -> AuxFeature:
    return AuxFeature(
        id="test",
        label="Test",
        description="Test",
        group="Storage",
        scope=scope,
        action=action,
        args={
            "fast": AuxArg(default="/mnt/ws-fast"),
            "backup": AuxArg(default="/mnt/ws-backup"),
            "profiles": AuxArg(default="data,secrets"),
        },
    )


class TestDetect:
    def test_missing_detect_path_is_not_configured(self) -> None:
        feature = _feature("storage-configure")
        feature.detect_path = "/nonexistent/workspace/seam.yaml"
        assert detect_configured(feature) is False

    def test_existing_detect_path_is_configured(self, tmp_path: Path) -> None:
        target = tmp_path / "seam.yaml"
        target.write_text("fast: /mnt/ws-fast\n")
        feature = _feature("storage-configure")
        feature.detect_path = str(target)
        assert detect_configured(feature) is True

    def test_detect_command_exit_zero_is_configured(self) -> None:
        feature = _feature("storage-configure")
        feature.detect_cmd = ["test", "-d", "/"]
        assert detect_configured(feature) is True

    def test_detect_command_failure_is_not_configured(self) -> None:
        feature = _feature("storage-configure")
        feature.detect_cmd = ["test", "-d", "/nonexistent/aux"]
        assert detect_configured(feature) is False

    @patch("workspace.scripts.bootstrap_aux.os.path.ismount")
    def test_detect_mount_is_configured(self, ismount) -> None:
        ismount.return_value = True
        feature = _feature("storage-mount-backup", "root")
        feature.detect_mount = "/mnt/ws-backup"
        assert detect_configured(feature) is True


class TestBuildCommands:
    def test_storage_configure_uses_writer(self) -> None:
        commands = build_commands(_feature("storage-configure"), {})
        assert len(commands) == 1
        assert commands[0][0] == "bash"
        assert "write-storage-locations.sh" in commands[0][1]
        assert "--fast" in commands[0]
        assert "--backup" in commands[0]

    def test_storage_mount_is_root_make_target(self) -> None:
        commands = build_commands(_feature("storage-mount-backup", "root"), {})
        assert commands[0][:2] == ["make", "-C"]
        assert "storage-mount" in commands[0]
        assert "NAME=ws-backup" in commands[0]

    def test_provision_runs_dry_run_first(self) -> None:
        commands = build_commands(_feature("storage-provision-fast", "root"), {})
        assert commands[0][-1] == "DRY_RUN=1"
        assert commands[1][-1] == "storage-provision"

    def test_dataops_profiles_uses_argument(self) -> None:
        commands = build_commands(_feature("dataops-profiles"), {"profiles": "data"})
        assert "PROFILES=data" in commands[0]

    def test_unknown_action_raises(self) -> None:
        with pytest.raises(ValueError, match="unknown auxiliary action"):
            build_commands(_feature("not-an-action"), {})


class TestRunFeature:
    def test_root_feature_skipped_without_root(self) -> None:
        result = run_feature(
            _feature("storage-mount-backup", "root"),
            {},
            effective_uid=1000,
        )
        assert result.success is False
        assert "sudo make init" in result.message

    def test_agent_feature_requires_owner_under_root(self, monkeypatch) -> None:
        monkeypatch.delenv("SUDO_USER", raising=False)
        with pytest.raises(ValueError, match="SUDO_USER"):
            run_feature(_feature("storage-configure"), {}, effective_uid=0)

    @patch("workspace.scripts.bootstrap_aux.subprocess.run")
    def test_successful_command(self, run) -> None:
        run.return_value = subprocess.CompletedProcess([], 0)
        result = run_feature(_feature("storage-configure"), {}, effective_uid=1000)
        assert result.success is True

    @patch("workspace.scripts.bootstrap_aux.subprocess.run")
    def test_failed_command_stops(self, run) -> None:
        run.side_effect = subprocess.CalledProcessError(1, [])
        result = run_feature(_feature("storage-configure"), {}, effective_uid=1000)
        assert result.success is False
        assert "rc=1" in result.message


class TestRunSelected:
    @patch("workspace.scripts.bootstrap_aux.run_feature")
    def test_stops_after_first_failure(self, run_feature) -> None:
        run_feature.side_effect = [
            AuxResult("one", True, "ok"),
            AuxResult("two", False, "failed"),
            AuxResult("three", True, "ok"),
        ]
        features = [_feature("storage-configure") for _ in range(3)]
        for index, feature in enumerate(features):
            feature.id = f"f{index}"
        results = run_selected(features, {}, effective_uid=1000)
        assert [result.success for result in results] == [True, False]
        assert results[-1].feature_id == "two"
