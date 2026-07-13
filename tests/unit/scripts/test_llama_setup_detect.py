"""Unit tests for llama_setup_detect."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from workspace.scripts.llama_setup_detect import (
    DetectSnapshot,
    HardwareSnapshot,
    PrereqStatus,
    StackStatus,
    _gpu_probe_lines,
    _list_user_services,
    _prereq_satisfied,
    _run_detect_cmd,
    _stack_status,
    _step_installed,
    _user_in_group,
    collect_hardware_snapshot,
    collect_prereq_statuses,
    collect_snapshot,
    collect_stack_statuses,
    missing_prereqs_for_stack,
)
from workspace.scripts.llama_setup_registry import (
    BuildStep,
    DetectCmd,
    PrereqSpec,
    StackProfile,
    load_registry,
)

RC_CMD_FAILURE = 2
RC_CMD_MISSING = 127
RC_DETECT_FAILURE = 1
RC_PROBE_FAILURE = 3


def _minimal_stack(
    *,
    step_id: str = "step",
    detect_path: str | None = "bin/tool",
    detect_glob: str | None = None,
) -> StackProfile:
    return StackProfile(
        id="test_stack",
        label="Test Stack",
        description="test",
        prereq_ids=("intel_drivers",),
        build_steps=(
            BuildStep(
                id=step_id,
                label="Build step",
                script=None,
                make_target=None,
                make_vars=(),
                detect_path=detect_path,
                detect_glob=detect_glob,
            ),
        ),
        deploy=None,
    )


class TestUserInGroup:
    def test_returns_false_when_group_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "workspace.scripts.llama_setup_detect.grp.getgrnam",
            MagicMock(side_effect=KeyError),
        )
        assert _user_in_group("render") is False

    def test_returns_true_when_gid_in_groups(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "workspace.scripts.llama_setup_detect.grp.getgrnam",
            MagicMock(return_value=MagicMock(gr_gid=42)),
        )
        monkeypatch.setattr(
            "workspace.scripts.llama_setup_detect.os.getgroups", lambda: [42, 99]
        )
        assert _user_in_group("render") is True


class TestRunDetectCmd:
    @patch("workspace.scripts.llama_setup_detect.subprocess.run")
    def test_success_returns_zero(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        assert _run_detect_cmd(("true",)) == 0

    @patch("workspace.scripts.llama_setup_detect.subprocess.run")
    def test_called_process_error_returns_rc(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = subprocess.CalledProcessError(RC_CMD_FAILURE, "cmd")
        assert _run_detect_cmd(("false",)) == RC_CMD_FAILURE

    @patch("workspace.scripts.llama_setup_detect.subprocess.run")
    def test_os_error_returns_127(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = OSError("missing")
        assert _run_detect_cmd(("missing",)) == RC_CMD_MISSING


class TestPrereqSatisfied:
    def test_no_detect_cmds(self) -> None:
        prereq = PrereqSpec(
            id="x",
            label="X",
            description="",
            script="s.sh",
            script_args=(),
            detect_cmds=(),
            needs_sudo=False,
        )
        ok, detail = _prereq_satisfied(prereq)
        assert ok is False
        assert "no detect commands" in detail

    @patch("workspace.scripts.llama_setup_detect._run_detect_cmd", return_value=0)
    def test_all_detect_cmds_pass(self, mock_run: MagicMock) -> None:
        prereq = PrereqSpec(
            id="x",
            label="X",
            description="",
            script="s.sh",
            script_args=(),
            detect_cmds=(DetectCmd(cmd=("true",), expect_rc=0),),
            needs_sudo=False,
        )
        ok, detail = _prereq_satisfied(prereq)
        assert ok is True
        assert detail == "detect checks passed"
        mock_run.assert_called_once()

    @patch(
        "workspace.scripts.llama_setup_detect._run_detect_cmd",
        return_value=RC_DETECT_FAILURE,
    )
    def test_detect_failure(self, mock_run: MagicMock) -> None:
        prereq = PrereqSpec(
            id="x",
            label="X",
            description="",
            script="s.sh",
            script_args=(),
            detect_cmds=(DetectCmd(cmd=("false",), expect_rc=0),),
            needs_sudo=False,
        )
        ok, detail = _prereq_satisfied(prereq)
        assert ok is False
        assert f"rc {RC_DETECT_FAILURE}" in detail
        mock_run.assert_called_once()


class TestStepInstalled:
    def test_detect_path_executable(self, tmp_path: Path) -> None:
        tool = tmp_path / "bin" / "tool"
        tool.parent.mkdir(parents=True)
        tool.write_text("#!/bin/sh\n", encoding="utf-8")
        tool.chmod(0o755)
        step = BuildStep(
            id="s",
            label="S",
            script=None,
            make_target=None,
            make_vars=(),
            detect_path="bin/tool",
            detect_glob=None,
        )
        with patch("workspace.scripts.llama_setup_detect.PROJECT_ROOT", tmp_path):
            ok, detail = _step_installed(step)
        assert ok is True
        assert detail == "bin/tool"

    def test_detect_path_missing(self, tmp_path: Path) -> None:
        step = BuildStep(
            id="s",
            label="S",
            script=None,
            make_target=None,
            make_vars=(),
            detect_path="missing.bin",
            detect_glob=None,
        )
        with patch("workspace.scripts.llama_setup_detect.PROJECT_ROOT", tmp_path):
            ok, detail = _step_installed(step)
        assert ok is False
        assert "missing missing.bin" in detail

    def test_detect_glob_match(self, tmp_path: Path) -> None:
        bundle = tmp_path / "models" / "m" / "chat.llamafile"
        bundle.parent.mkdir(parents=True)
        bundle.write_text("bundle", encoding="utf-8")
        step = BuildStep(
            id="s",
            label="S",
            script=None,
            make_target=None,
            make_vars=(),
            detect_path=None,
            detect_glob="models/m/*.llamafile",
        )
        with patch("workspace.scripts.llama_setup_detect.PROJECT_ROOT", tmp_path):
            ok, detail = _step_installed(step)
        assert ok is True
        assert "models/m/chat.llamafile" in detail

    def test_no_detect_rule(self) -> None:
        step = BuildStep(
            id="s",
            label="S",
            script=None,
            make_target=None,
            make_vars=(),
            detect_path=None,
            detect_glob=None,
        )
        ok, detail = _step_installed(step)
        assert ok is False
        assert detail == "no detect rule"


class TestStackAndServices:
    def test_stack_status_aggregates_steps(self, tmp_path: Path) -> None:
        stack = _minimal_stack(detect_path="ready.bin")
        (tmp_path / "ready.bin").write_text("x", encoding="utf-8")
        with patch("workspace.scripts.llama_setup_detect.PROJECT_ROOT", tmp_path):
            status = _stack_status(stack)
        assert isinstance(status, StackStatus)
        assert status.ready is True
        assert status.build_steps[0].installed is True

    @patch("workspace.scripts.llama_setup_detect.subprocess.run")
    def test_list_user_services_parses_output(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout="llamafile-minicpm.service loaded active running\n",
            returncode=0,
        )
        units = _list_user_services()
        assert len(units) == 1
        assert units[0].name == "llamafile-minicpm.service"
        assert units[0].active == "active"

    @patch(
        "workspace.scripts.llama_setup_detect.subprocess.run",
        side_effect=OSError("no systemctl"),
    )
    def test_list_user_services_handles_errors(self, mock_run: MagicMock) -> None:
        assert _list_user_services() == ()
        mock_run.assert_called_once()


class TestGpuProbe:
    def test_missing_probe_script(self, tmp_path: Path) -> None:
        with patch("workspace.scripts.llama_setup_detect.PROJECT_ROOT", tmp_path):
            rc, lines = _gpu_probe_lines()
        assert rc == 1
        assert lines == ("probe script missing",)

    @patch("workspace.scripts.llama_setup_detect.subprocess.run")
    def test_probe_success(self, mock_run: MagicMock, tmp_path: Path) -> None:
        probe = tmp_path / "scripts/setup/lib/vulkan_gpu_probe.py"
        probe.parent.mkdir(parents=True)
        probe.write_text("print('ok')", encoding="utf-8")
        mock_run.return_value = MagicMock(stdout="device: Intel\n\n", returncode=0)
        with patch("workspace.scripts.llama_setup_detect.PROJECT_ROOT", tmp_path):
            rc, lines = _gpu_probe_lines()
        assert rc == 0
        assert lines == ("device: Intel",)

    @patch("workspace.scripts.llama_setup_detect.subprocess.run")
    def test_probe_called_process_error(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        probe = tmp_path / "scripts/setup/lib/vulkan_gpu_probe.py"
        probe.parent.mkdir(parents=True)
        probe.write_text("raise", encoding="utf-8")
        mock_run.side_effect = subprocess.CalledProcessError(
            RC_PROBE_FAILURE,
            "uv",
            stderr="probe failed",
        )
        with patch("workspace.scripts.llama_setup_detect.PROJECT_ROOT", tmp_path):
            rc, lines = _gpu_probe_lines()
        assert rc == RC_PROBE_FAILURE
        assert lines == ("probe failed",)


class TestCollectSnapshot:
    @patch(
        "workspace.scripts.llama_setup_detect._gpu_probe_lines",
        return_value=(0, ("ok",)),
    )
    @patch("workspace.scripts.llama_setup_detect._run_detect_cmd", return_value=0)
    @patch("workspace.scripts.llama_setup_detect._user_in_group", return_value=True)
    @patch("workspace.scripts.llama_setup_detect.Path.is_file", return_value=True)
    def test_collect_hardware_snapshot(
        self,
        mock_is_file: MagicMock,
        mock_group: MagicMock,
        mock_cmd: MagicMock,
        mock_probe: MagicMock,
    ) -> None:
        hardware = collect_hardware_snapshot()
        assert isinstance(hardware, HardwareSnapshot)
        assert hardware.gpu_probe_rc == 0
        assert hardware.tools.xpu_smi is True
        mock_is_file.assert_called()
        mock_group.assert_called()
        mock_cmd.assert_called()
        mock_probe.assert_called_once()

    def test_collect_snapshot_integration(self) -> None:
        registry = load_registry()
        with (
            patch(
                "workspace.scripts.llama_setup_detect.collect_hardware_snapshot",
                return_value=HardwareSnapshot(
                    groups=MagicMock(render=True, video=True),
                    tools=MagicMock(xpu_smi=False, vulkaninfo=True, clinfo=False),
                    gpu_probe_rc=0,
                    gpu_probe_lines=("ok",),
                ),
            ),
            patch(
                "workspace.scripts.llama_setup_detect._list_user_services",
                return_value=(),
            ),
            patch(
                "workspace.scripts.llama_setup_detect._prereq_satisfied",
                return_value=(False, "missing"),
            ),
        ):
            snapshot = collect_snapshot(registry)
        assert isinstance(snapshot, DetectSnapshot)
        assert len(snapshot.prereqs) == len(registry.prereqs)
        assert len(snapshot.stacks) == len(registry.stacks)

    def test_missing_prereqs_for_stack(self) -> None:
        registry = load_registry()
        stack = _minimal_stack()
        snapshot = DetectSnapshot(
            hardware=HardwareSnapshot(
                groups=MagicMock(render=True, video=True),
                tools=MagicMock(xpu_smi=False, vulkaninfo=True, clinfo=False),
                gpu_probe_rc=0,
                gpu_probe_lines=(),
            ),
            prereqs=(
                PrereqStatus(
                    prereq_id="vulkan_dev",
                    label="Vulkan",
                    satisfied=True,
                    detail="ok",
                ),
            ),
            stacks=(),
            services=(),
        )
        missing = missing_prereqs_for_stack(registry, snapshot, stack)
        assert all(item.id != "vulkan_dev" for item in missing)

    @patch(
        "workspace.scripts.llama_setup_detect._prereq_satisfied",
        return_value=(True, "ok"),
    )
    def test_collect_prereq_and_stack_statuses(self, mock_prereq: MagicMock) -> None:
        registry = load_registry()
        prereqs = collect_prereq_statuses(registry)
        stacks = collect_stack_statuses(registry)
        assert prereqs
        assert stacks
        assert mock_prereq.call_count == len(registry.prereqs)
