"""Non-interactive install orchestration for llama-setup TUI."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from typing import NamedTuple

from workspace.config_utils import PROJECT_ROOT
from workspace.scripts.llama_setup_registry import (
    BuildStep,
    DiagnosticSpec,
    LlamaSetupRegistry,
    PrereqSpec,
    StackProfile,
)


class StepResult(NamedTuple):
    label: str
    success: bool
    detail: str


class InstallPlan(NamedTuple):
    prereqs: tuple[PrereqSpec, ...]
    stacks: tuple[StackProfile, ...]
    run_diagnostics: bool
    deploy: bool
    model: str


class RegistryMaps(NamedTuple):
    prereqs: dict[str, PrereqSpec]
    stacks: dict[str, StackProfile]


class DispatchContext(NamedTuple):
    maps: RegistryMaps
    registry: LlamaSetupRegistry
    model: str
    on_result: ResultCallback | None


ProgressCallback = Callable[[int, int, str], None]
ResultCallback = Callable[[str, bool, str], None]


def _run_shell_step(
    label: str,
    argv: list[str],
    *,
    needs_sudo: bool,
) -> StepResult:
    cmd = ["sudo", "bash", *argv[1:]] if needs_sudo and argv[0] == "bash" else argv
    if needs_sudo and argv[0] != "bash":
        cmd = ["sudo", *argv]
    try:
        subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            env=dict(os.environ),
            stdin=subprocess.DEVNULL,
            check=True,
        )
    except (OSError, subprocess.SubprocessError, subprocess.CalledProcessError) as exc:
        return StepResult(label=label, success=False, detail=str(exc))
    return StepResult(label=label, success=True, detail="ok")


def run_prereq(prereq: PrereqSpec) -> StepResult:
    script_path = PROJECT_ROOT / prereq.script
    if not script_path.is_file():
        return StepResult(
            label=prereq.label,
            success=False,
            detail=f"missing script {prereq.script}",
        )
    argv = ["bash", str(script_path), *prereq.script_args]
    return _run_shell_step(prereq.label, argv, needs_sudo=prereq.needs_sudo)


def run_build_step(step: BuildStep) -> StepResult:
    if step.script:
        script_path = PROJECT_ROOT / step.script
        if not script_path.is_file():
            return StepResult(
                label=step.label,
                success=False,
                detail=f"missing script {step.script}",
            )
        return _run_shell_step(step.label, ["bash", str(script_path)], needs_sudo=False)

    if step.make_target:
        make_argv = ["make", "-f", "Makefile.llamafile", step.make_target]
        for key, value in step.make_vars:
            make_argv.append(f"{key}={value}")
        try:
            subprocess.run(
                make_argv,
                cwd=str(PROJECT_ROOT),
                env=dict(os.environ),
                stdin=subprocess.DEVNULL,
                check=True,
            )
        except (
            OSError,
            subprocess.SubprocessError,
            subprocess.CalledProcessError,
        ) as exc:
            return StepResult(label=step.label, success=False, detail=str(exc))
        return StepResult(label=step.label, success=True, detail="ok")

    return StepResult(label=step.label, success=False, detail="no build action")


def deploy_stack(stack: StackProfile, model: str) -> StepResult:
    deploy = stack.deploy
    if deploy is None:
        return StepResult(label="deploy", success=True, detail="skipped")

    if deploy.kind == "llamafile":
        gpu = deploy.gpu or "vulkan"
        target_model = model or deploy.model or "minicpm5-1b"
        make_argv = [
            "make",
            "-f",
            "Makefile.llamafile",
            f"MODEL={target_model}",
            f"GPU={gpu}",
            "install-llamafile",
        ]
        label = f"deploy llamafile ({model})"
    elif deploy.kind == "llamaserver":
        flavor = deploy.flavor or "vulkan"
        make_argv = [
            "make",
            "-f",
            "Makefile.llamaserver",
            "install-llamaserver",
            f"FLAVOR={flavor}",
        ]
        label = f"deploy llamaserver@{flavor}"
    else:
        return StepResult(
            label="deploy", success=False, detail=f"unknown kind {deploy.kind}"
        )

    try:
        subprocess.run(
            make_argv,
            cwd=str(PROJECT_ROOT),
            env=dict(os.environ),
            stdin=subprocess.DEVNULL,
            check=True,
        )
    except (OSError, subprocess.SubprocessError, subprocess.CalledProcessError) as exc:
        return StepResult(label=label, success=False, detail=str(exc))
    return StepResult(label=label, success=True, detail="ok")


def _diagnostic_argv(spec: DiagnosticSpec) -> list[str] | None:
    if spec.script:
        script_path = PROJECT_ROOT / spec.script
        if not script_path.is_file():
            return None
        if spec.script.endswith(".py"):
            return ["uv", "run", "python", str(script_path)]
        return ["bash", str(script_path)]
    if spec.cmd:
        return list(spec.cmd)
    return None


def _diagnostic_result(
    spec: DiagnosticSpec, *, rc: int | None, error: str
) -> StepResult:
    if error:
        if spec.optional:
            return StepResult(
                label=spec.label, success=True, detail=f"optional skip: {error}"
            )
        return StepResult(label=spec.label, success=False, detail=error)
    if rc is not None and rc != 0:
        if spec.optional:
            return StepResult(
                label=spec.label,
                success=True,
                detail=f"optional (rc {rc})",
            )
        return StepResult(label=spec.label, success=False, detail=f"exit {rc}")
    return StepResult(label=spec.label, success=True, detail="ok")


def run_diagnostic(spec: DiagnosticSpec) -> StepResult:
    argv = _diagnostic_argv(spec)
    if argv is None:
        return _diagnostic_result(
            spec, rc=None, error="no diagnostic command or missing script"
        )
    try:
        subprocess.run(
            argv,
            cwd=str(PROJECT_ROOT),
            env=dict(os.environ),
            stdin=subprocess.DEVNULL,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        return _diagnostic_result(spec, rc=exc.returncode, error="")
    except OSError as exc:
        return _diagnostic_result(spec, rc=None, error=str(exc))
    return _diagnostic_result(spec, rc=0, error="")


def _collect_work_items(plan: InstallPlan) -> list[tuple[str, str]]:
    items = [("prereq", prereq.id) for prereq in plan.prereqs]
    for stack in plan.stacks:
        items.extend(("build", f"{stack.id}:{step.id}") for step in stack.build_steps)
        if plan.deploy and stack.deploy is not None:
            items.append(("deploy", stack.id))
    if plan.run_diagnostics:
        items.append(("diagnostics", "all"))
    return items


def _registry_maps(registry: LlamaSetupRegistry) -> RegistryMaps:
    return RegistryMaps(
        prereqs={item.id: item for item in registry.prereqs},
        stacks={item.id: item for item in registry.stacks},
    )


def _find_build_step(stack: StackProfile, step_id: str) -> BuildStep | None:
    for step in stack.build_steps:
        if step.id == step_id:
            return step
    return None


def _run_prereq_item(maps: RegistryMaps, ref: str) -> StepResult:
    prereq = maps.prereqs.get(ref)
    if prereq is None:
        return StepResult(label=ref, success=False, detail="unknown prereq")
    return run_prereq(prereq)


def _run_build_item(maps: RegistryMaps, ref: str) -> StepResult:
    stack_id, step_id = ref.split(":", 1)
    stack = maps.stacks.get(stack_id)
    if stack is None:
        return StepResult(label=ref, success=False, detail="unknown stack")
    step = _find_build_step(stack, step_id)
    if step is None:
        return StepResult(label=ref, success=False, detail="unknown build step")
    return run_build_step(step)


def _run_deploy_item(maps: RegistryMaps, ref: str, model: str) -> StepResult:
    stack = maps.stacks.get(ref)
    if stack is None:
        return StepResult(label=ref, success=False, detail="unknown stack")
    return deploy_stack(stack, model)


def _run_diagnostics(
    registry: LlamaSetupRegistry,
    on_result: ResultCallback | None,
) -> list[StepResult]:
    results: list[StepResult] = []
    for diag in registry.diagnostics:
        diag_result = run_diagnostic(diag)
        results.append(diag_result)
        if on_result is not None:
            on_result(diag_result.label, diag_result.success, diag_result.detail)
    return results


def _dispatch_work_item(
    kind: str,
    ref: str,
    ctx: DispatchContext,
) -> list[StepResult]:
    if kind == "prereq":
        return [_run_prereq_item(ctx.maps, ref)]
    if kind == "build":
        return [_run_build_item(ctx.maps, ref)]
    if kind == "deploy":
        return [_run_deploy_item(ctx.maps, ref, ctx.model)]
    if kind == "diagnostics":
        return _run_diagnostics(ctx.registry, ctx.on_result)
    return [StepResult(label=ref, success=False, detail=f"unknown work kind {kind}")]


def execute_plan(
    registry: LlamaSetupRegistry,
    plan: InstallPlan,
    *,
    on_progress: ProgressCallback | None = None,
    on_result: ResultCallback | None = None,
) -> list[StepResult]:
    work = _collect_work_items(plan)
    ctx = DispatchContext(
        maps=_registry_maps(registry),
        registry=registry,
        model=plan.model,
        on_result=on_result,
    )
    results: list[StepResult] = []
    total = len(work)

    for current, (kind, ref) in enumerate(work, start=1):
        if on_progress is not None:
            on_progress(current, total, f"{kind}:{ref}")

        batch = _dispatch_work_item(kind, ref, ctx)
        if kind == "diagnostics":
            results.extend(batch)
            continue

        for result in batch:
            results.append(result)
            if on_result is not None:
                on_result(result.label, result.success, result.detail)

    return results
