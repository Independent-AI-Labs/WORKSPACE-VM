"""Load llama-setup.yaml into typed registry objects."""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import yaml

from workspace.config_utils import PROJECT_ROOT

LLAMA_SETUP_YAML = PROJECT_ROOT / "workspace" / "config" / "llama-setup.yaml"


class DetectCmd(NamedTuple):
    cmd: tuple[str, ...]
    expect_rc: int


class BuildStep(NamedTuple):
    id: str
    label: str
    script: str | None
    make_target: str | None
    make_vars: tuple[tuple[str, str], ...]
    detect_path: str | None
    detect_glob: str | None


class DeploySpec(NamedTuple):
    kind: str
    model: str | None
    gpu: str | None
    flavor: str | None


class StackProfile(NamedTuple):
    id: str
    label: str
    description: str
    prereq_ids: tuple[str, ...]
    build_steps: tuple[BuildStep, ...]
    deploy: DeploySpec | None


class PrereqSpec(NamedTuple):
    id: str
    label: str
    description: str
    script: str
    script_args: tuple[str, ...]
    detect_cmds: tuple[DetectCmd, ...]
    needs_sudo: bool


class DiagnosticSpec(NamedTuple):
    id: str
    label: str
    script: str | None
    cmd: tuple[str, ...] | None
    optional: bool


class LlamaSetupRegistry(NamedTuple):
    stacks: tuple[StackProfile, ...]
    prereqs: tuple[PrereqSpec, ...]
    diagnostics: tuple[DiagnosticSpec, ...]


def _tuple_cmd(raw: list[str]) -> tuple[str, ...]:
    return tuple(str(part) for part in raw)


def _parse_build_step(entry: object) -> BuildStep:
    if not isinstance(entry, dict):
        msg = "build step entry must be a mapping"
        raise TypeError(msg)
    raw = entry
    make_vars_raw = raw.get("make_vars") or {}
    make_vars: list[tuple[str, str]] = []
    if isinstance(make_vars_raw, dict):
        for key, value in make_vars_raw.items():
            make_vars.append((str(key), str(value)))
    return BuildStep(
        id=str(raw["id"]),
        label=str(raw["label"]),
        script=str(raw["script"]) if raw.get("script") else None,
        make_target=str(raw["make_target"]) if raw.get("make_target") else None,
        make_vars=tuple(make_vars),
        detect_path=str(raw["detect_path"]) if raw.get("detect_path") else None,
        detect_glob=str(raw["detect_glob"]) if raw.get("detect_glob") else None,
    )


def _parse_deploy(raw: object | None) -> DeploySpec | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        return None
    return DeploySpec(
        kind=str(raw.get("kind", "")),
        model=str(raw["model"]) if raw.get("model") else None,
        gpu=str(raw["gpu"]) if raw.get("gpu") else None,
        flavor=str(raw["flavor"]) if raw.get("flavor") else None,
    )


def _parse_stack(entry: object) -> StackProfile:
    if not isinstance(entry, dict):
        msg = "stack entry must be a mapping"
        raise TypeError(msg)
    raw = entry
    steps_raw = raw.get("build_steps") or []
    steps: list[BuildStep] = (
        [_parse_build_step(entry) for entry in steps_raw if isinstance(entry, dict)]
        if isinstance(steps_raw, list)
        else []
    )
    prereqs_raw = raw.get("prereqs") or []
    prereq_ids: list[str] = []
    if isinstance(prereqs_raw, list):
        prereq_ids = [str(item) for item in prereqs_raw]
    return StackProfile(
        id=str(raw["id"]),
        label=str(raw["label"]),
        description=str(raw["description"]),
        prereq_ids=tuple(prereq_ids),
        build_steps=tuple(steps),
        deploy=_parse_deploy(raw.get("deploy")),
    )


def _parse_prereq(entry: object) -> PrereqSpec:
    if not isinstance(entry, dict):
        msg = "prereq entry must be a mapping"
        raise TypeError(msg)
    raw = entry
    detect_cmds: list[DetectCmd] = []
    for detect_entry in raw.get("detect_cmds") or []:
        if not isinstance(detect_entry, dict):
            continue
        cmd_list = detect_entry.get("cmd") or []
        if not isinstance(cmd_list, list):
            continue
        detect_cmds.append(
            DetectCmd(
                cmd=_tuple_cmd([str(part) for part in cmd_list]),
                expect_rc=int(detect_entry.get("expect_rc", 0)),
            )
        )
    args_raw = raw.get("script_args") or []
    script_args: list[str] = []
    if isinstance(args_raw, list):
        script_args = [str(item) for item in args_raw]
    return PrereqSpec(
        id=str(raw["id"]),
        label=str(raw["label"]),
        description=str(raw["description"]),
        script=str(raw["script"]),
        script_args=tuple(script_args),
        detect_cmds=tuple(detect_cmds),
        needs_sudo=bool(raw.get("needs_sudo", False)),
    )


def _parse_diagnostic(entry: object) -> DiagnosticSpec:
    if not isinstance(entry, dict):
        msg = "diagnostic entry must be a mapping"
        raise TypeError(msg)
    raw = entry
    cmd_raw = raw.get("cmd")
    cmd: tuple[str, ...] | None = None
    if isinstance(cmd_raw, list):
        cmd = _tuple_cmd([str(part) for part in cmd_raw])
    return DiagnosticSpec(
        id=str(raw["id"]),
        label=str(raw["label"]),
        script=str(raw["script"]) if raw.get("script") else None,
        cmd=cmd,
        optional=bool(raw.get("optional", False)),
    )


def load_registry(path: Path | None = None) -> LlamaSetupRegistry:
    yaml_path = path if path is not None else LLAMA_SETUP_YAML
    with open(yaml_path, encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        msg = f"invalid llama-setup registry: {yaml_path}"
        raise TypeError(msg)

    stacks = [
        _parse_stack(entry)
        for entry in data.get("stacks") or []
        if isinstance(entry, dict)
    ]
    prereqs = [
        _parse_prereq(entry)
        for entry in data.get("prereqs") or []
        if isinstance(entry, dict)
    ]
    diagnostics = [
        _parse_diagnostic(entry)
        for entry in data.get("diagnostics") or []
        if isinstance(entry, dict)
    ]

    return LlamaSetupRegistry(
        stacks=tuple(stacks),
        prereqs=tuple(prereqs),
        diagnostics=tuple(diagnostics),
    )


def stack_by_id(registry: LlamaSetupRegistry, stack_id: str) -> StackProfile | None:
    for stack in registry.stacks:
        if stack.id == stack_id:
            return stack
    return None


def prereq_by_id(registry: LlamaSetupRegistry, prereq_id: str) -> PrereqSpec | None:
    for prereq in registry.prereqs:
        if prereq.id == prereq_id:
            return prereq
    return None
