"""Hardware and install-state detection for llama-setup TUI."""

from __future__ import annotations

import grp
import os
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

from workspace.config_utils import PROJECT_ROOT
from workspace.scripts.llama_setup_registry import (
    BuildStep,
    LlamaSetupRegistry,
    PrereqSpec,
    StackProfile,
    prereq_by_id,
)

MIN_SYSTEMCTL_COLUMNS = 4


class GroupMembership(NamedTuple):
    render: bool
    video: bool


class ToolPresence(NamedTuple):
    xpu_smi: bool
    vulkaninfo: bool
    clinfo: bool


class BuildStepStatus(NamedTuple):
    step_id: str
    label: str
    installed: bool
    detail: str


class PrereqStatus(NamedTuple):
    prereq_id: str
    label: str
    satisfied: bool
    detail: str


class StackStatus(NamedTuple):
    stack_id: str
    label: str
    build_steps: tuple[BuildStepStatus, ...]
    ready: bool


class ServiceUnit(NamedTuple):
    name: str
    active: str


class HardwareSnapshot(NamedTuple):
    groups: GroupMembership
    tools: ToolPresence
    gpu_probe_rc: int
    gpu_probe_lines: tuple[str, ...]


class DetectSnapshot(NamedTuple):
    hardware: HardwareSnapshot
    prereqs: tuple[PrereqStatus, ...]
    stacks: tuple[StackStatus, ...]
    services: tuple[ServiceUnit, ...]


def _user_in_group(group_name: str) -> bool:
    try:
        gid = grp.getgrnam(group_name).gr_gid
    except KeyError:
        return False
    return gid in os.getgroups()


def _run_detect_cmd(cmd: tuple[str, ...]) -> int:
    try:
        subprocess.run(
            list(cmd),
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        if exc.stderr:
            sys.stderr.write(exc.stderr)
        return exc.returncode
    except OSError as exc:
        sys.stderr.write(f"detect command failed: {exc}\n")
        return 127
    return 0


def _prereq_satisfied(prereq: PrereqSpec) -> tuple[bool, str]:
    if not prereq.detect_cmds:
        return False, "no detect commands configured"
    for detect in prereq.detect_cmds:
        rc = _run_detect_cmd(detect.cmd)
        if rc != detect.expect_rc:
            cmd_text = " ".join(detect.cmd)
            return False, f"{cmd_text} -> rc {rc}"
    return True, "detect checks passed"


def _step_installed(step: BuildStep) -> tuple[bool, str]:
    if step.detect_path:
        path = PROJECT_ROOT / step.detect_path
        if path.is_file() and os.access(path, os.X_OK):
            return True, str(step.detect_path)
        if path.is_file():
            return True, str(step.detect_path)
        return False, f"missing {step.detect_path}"
    if step.detect_glob:
        matches = sorted(PROJECT_ROOT.glob(step.detect_glob))
        if matches:
            return True, str(matches[0].relative_to(PROJECT_ROOT))
        return False, f"no match for {step.detect_glob}"
    return False, "no detect rule"


def _stack_status(stack: StackProfile) -> StackStatus:
    steps: list[BuildStepStatus] = []
    all_ready = True
    for step in stack.build_steps:
        installed, detail = _step_installed(step)
        if not installed:
            all_ready = False
        steps.append(
            BuildStepStatus(
                step_id=step.id,
                label=step.label,
                installed=installed,
                detail=detail,
            )
        )
    return StackStatus(
        stack_id=stack.id,
        label=stack.label,
        build_steps=tuple(steps),
        ready=all_ready,
    )


def _list_user_services() -> tuple[ServiceUnit, ...]:
    units: list[ServiceUnit] = []
    try:
        completed = subprocess.run(
            [
                "systemctl",
                "--user",
                "list-units",
                "llamafile-*.service",
                "llamaserver@*.service",
                "--no-pager",
                "--no-legend",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.SubprocessError, subprocess.CalledProcessError) as exc:
        sys.stderr.write(f"systemctl list-units failed: {exc}\n")
        return tuple(units)
    for line in completed.stdout.splitlines():
        parts = line.split()
        if len(parts) >= MIN_SYSTEMCTL_COLUMNS:
            units.append(ServiceUnit(name=parts[0], active=parts[2]))
    return tuple(units)


def _gpu_probe_lines() -> tuple[int, tuple[str, ...]]:
    probe_script = PROJECT_ROOT / "scripts/setup/lib/vulkan_gpu_probe.py"
    if not probe_script.is_file():
        return 1, ("probe script missing",)
    try:
        completed = subprocess.run(
            ["uv", "run", "python", str(probe_script)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        err_text = exc.stderr.strip() if exc.stderr else f"probe exit {exc.returncode}"
        return exc.returncode, (err_text,)
    except OSError as exc:
        return 127, (f"uv/python unavailable: {exc}",)
    lines = tuple(line for line in completed.stdout.splitlines() if line.strip())
    return 0, lines


def collect_hardware_snapshot() -> HardwareSnapshot:
    probe_rc, probe_lines = _gpu_probe_lines()
    return HardwareSnapshot(
        groups=GroupMembership(
            render=_user_in_group("render"),
            video=_user_in_group("video"),
        ),
        tools=ToolPresence(
            xpu_smi=Path("/usr/bin/xpu-smi").is_file(),
            vulkaninfo=_run_detect_cmd(("command", "-v", "vulkaninfo")) == 0,
            clinfo=_run_detect_cmd(("command", "-v", "clinfo")) == 0,
        ),
        gpu_probe_rc=probe_rc,
        gpu_probe_lines=probe_lines,
    )


def collect_prereq_statuses(registry: LlamaSetupRegistry) -> tuple[PrereqStatus, ...]:
    statuses: list[PrereqStatus] = []
    for prereq in registry.prereqs:
        satisfied, detail = _prereq_satisfied(prereq)
        statuses.append(
            PrereqStatus(
                prereq_id=prereq.id,
                label=prereq.label,
                satisfied=satisfied,
                detail=detail,
            )
        )
    return tuple(statuses)


def collect_stack_statuses(registry: LlamaSetupRegistry) -> tuple[StackStatus, ...]:
    return tuple(_stack_status(stack) for stack in registry.stacks)


def collect_snapshot(registry: LlamaSetupRegistry) -> DetectSnapshot:
    return DetectSnapshot(
        hardware=collect_hardware_snapshot(),
        prereqs=collect_prereq_statuses(registry),
        stacks=collect_stack_statuses(registry),
        services=_list_user_services(),
    )


def missing_prereqs_for_stack(
    registry: LlamaSetupRegistry,
    snapshot: DetectSnapshot,
    stack: StackProfile,
) -> tuple[PrereqSpec, ...]:
    satisfied_ids = {item.prereq_id for item in snapshot.prereqs if item.satisfied}
    missing: list[PrereqSpec] = []
    for prereq_id in stack.prereq_ids:
        if prereq_id in satisfied_ids:
            continue
        prereq = prereq_by_id(registry, prereq_id)
        if prereq is not None:
            missing.append(prereq)
    return tuple(missing)
