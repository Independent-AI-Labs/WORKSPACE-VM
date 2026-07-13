"""Unit tests for llama_setup_install orchestration."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from workspace.scripts.llama_setup_install import (
    DispatchContext,
    InstallPlan,
    RegistryMaps,
    StepResult,
    _collect_work_items,
    _diagnostic_argv,
    _diagnostic_result,
    _dispatch_work_item,
    _find_build_step,
    _registry_maps,
    _run_build_item,
    _run_deploy_item,
    _run_diagnostics,
    _run_prereq_item,
    _run_shell_step,
    deploy_stack,
    execute_plan,
    run_build_step,
    run_diagnostic,
    run_prereq,
)
from workspace.scripts.llama_setup_registry import (
    BuildStep,
    DeploySpec,
    DiagnosticSpec,
    LlamaSetupRegistry,
    PrereqSpec,
    StackProfile,
    load_registry,
)


def _test_prereq(tmp_path: Path) -> PrereqSpec:
    script = tmp_path / "install.sh"
    script.write_text("#!/bin/bash\necho ok\n", encoding="utf-8")
    return PrereqSpec(
        id="test_prereq",
        label="Test prereq",
        description="",
        script=str(script.relative_to(tmp_path)),
        script_args=("--flag",),
        detect_cmds=(),
        needs_sudo=False,
    )


def _test_stack(
    *,
    deploy: DeploySpec | None = None,
    build_script: str | None = None,
    make_target: str | None = None,
) -> StackProfile:
    return StackProfile(
        id="test_stack",
        label="Test stack",
        description="",
        prereq_ids=(),
        build_steps=(
            BuildStep(
                id="build_step",
                label="Build",
                script=build_script,
                make_target=make_target,
                make_vars=(),
                detect_path=None,
                detect_glob=None,
            ),
        ),
        deploy=deploy,
    )


class TestRunShellStep:
    @patch("workspace.scripts.llama_setup_install.subprocess.run")
    def test_success(self, mock_run: MagicMock) -> None:
        result = _run_shell_step("label", ["bash", "script.sh"], needs_sudo=False)
        assert result == StepResult(label="label", success=True, detail="ok")
        mock_run.assert_called_once()

    @patch("workspace.scripts.llama_setup_install.subprocess.run")
    def test_failure(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = subprocess.CalledProcessError(1, "bash")
        result = _run_shell_step("label", ["bash", "script.sh"], needs_sudo=False)
        assert result.success is False

    @patch("workspace.scripts.llama_setup_install.subprocess.run")
    def test_sudo_prefix_for_bash(self, mock_run: MagicMock) -> None:
        _run_shell_step("label", ["bash", "script.sh"], needs_sudo=True)
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "sudo"
        assert cmd[1] == "bash"

    @patch("workspace.scripts.llama_setup_install.subprocess.run")
    def test_sudo_prefix_for_other_argv(self, mock_run: MagicMock) -> None:
        _run_shell_step("label", ["make", "target"], needs_sudo=True)
        cmd = mock_run.call_args[0][0]
        assert cmd == ["sudo", "make", "target"]


class TestRunPrereqAndBuild:
    def test_run_prereq_missing_script(self, tmp_path: Path) -> None:
        prereq = _test_prereq(tmp_path)
        prereq = prereq._replace(script="missing.sh")
        with patch("workspace.scripts.llama_setup_install.PROJECT_ROOT", tmp_path):
            result = run_prereq(prereq)
        assert result.success is False
        assert "missing script" in result.detail

    @patch("workspace.scripts.llama_setup_install._run_shell_step")
    def test_run_prereq_delegates(self, mock_shell: MagicMock, tmp_path: Path) -> None:
        mock_shell.return_value = StepResult(label="x", success=True, detail="ok")
        prereq = _test_prereq(tmp_path)
        with patch("workspace.scripts.llama_setup_install.PROJECT_ROOT", tmp_path):
            result = run_prereq(prereq)
        assert result.success is True
        mock_shell.assert_called_once()

    def test_run_build_step_missing_script(self, tmp_path: Path) -> None:
        step = BuildStep(
            id="s",
            label="S",
            script="missing.sh",
            make_target=None,
            make_vars=(),
            detect_path=None,
            detect_glob=None,
        )
        with patch("workspace.scripts.llama_setup_install.PROJECT_ROOT", tmp_path):
            result = run_build_step(step)
        assert result.success is False

    @patch("workspace.scripts.llama_setup_install.subprocess.run")
    def test_run_build_step_make_target(self, mock_run: MagicMock) -> None:
        step = BuildStep(
            id="s",
            label="Bundle",
            script=None,
            make_target="build-llamafile",
            make_vars=(("MODEL", "minicpm5-1b"),),
            detect_path=None,
            detect_glob=None,
        )
        result = run_build_step(step)
        assert result.success is True
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "make"
        assert "MODEL=minicpm5-1b" in cmd

    def test_run_build_step_no_action(self) -> None:
        step = BuildStep(
            id="s",
            label="S",
            script=None,
            make_target=None,
            make_vars=(),
            detect_path=None,
            detect_glob=None,
        )
        result = run_build_step(step)
        assert result.detail == "no build action"


class TestDeployStack:
    def test_skips_when_deploy_null(self) -> None:
        stack = _test_stack(deploy=None)
        result = deploy_stack(stack, "minicpm5-1b")
        assert result.detail == "skipped"

    @patch("workspace.scripts.llama_setup_install.subprocess.run")
    def test_llamafile_deploy(self, mock_run: MagicMock) -> None:
        stack = _test_stack(
            deploy=DeploySpec(
                kind="llamafile", model="minicpm5-1b", gpu="vulkan", flavor=None
            ),
        )
        result = deploy_stack(stack, "minicpm5-1b")
        assert result.success is True
        cmd = mock_run.call_args[0][0]
        assert "install-llamafile" in cmd

    @patch("workspace.scripts.llama_setup_install.subprocess.run")
    def test_llamaserver_deploy(self, mock_run: MagicMock) -> None:
        stack = _test_stack(
            deploy=DeploySpec(
                kind="llamaserver", model=None, gpu=None, flavor="vulkan"
            ),
        )
        result = deploy_stack(stack, "")
        assert result.success is True
        assert "FLAVOR=vulkan" in mock_run.call_args[0][0]

    def test_unknown_deploy_kind(self) -> None:
        stack = _test_stack(
            deploy=DeploySpec(kind="unknown", model=None, gpu=None, flavor=None)
        )
        result = deploy_stack(stack, "")
        assert result.success is False


class TestDiagnostics:
    def test_diagnostic_argv_python_script(self, tmp_path: Path) -> None:
        script = tmp_path / "probe.py"
        script.write_text("print('ok')", encoding="utf-8")
        spec = DiagnosticSpec(
            id="p",
            label="Probe",
            script=str(script.relative_to(tmp_path)),
            cmd=None,
            optional=False,
        )
        with patch("workspace.scripts.llama_setup_install.PROJECT_ROOT", tmp_path):
            argv = _diagnostic_argv(spec)
        assert argv is not None
        assert argv[0] == "uv"

    def test_diagnostic_argv_missing_script(self, tmp_path: Path) -> None:
        spec = DiagnosticSpec(
            id="p",
            label="Probe",
            script="missing.py",
            cmd=None,
            optional=False,
        )
        with patch("workspace.scripts.llama_setup_install.PROJECT_ROOT", tmp_path):
            assert _diagnostic_argv(spec) is None

    def test_diagnostic_result_optional_failure(self) -> None:
        spec = DiagnosticSpec(
            id="p", label="Probe", script=None, cmd=("x",), optional=True
        )
        result = _diagnostic_result(spec, rc=1, error="")
        assert result.success is True
        assert "optional" in result.detail

    def test_diagnostic_result_required_failure(self) -> None:
        spec = DiagnosticSpec(
            id="p", label="Probe", script=None, cmd=("x",), optional=False
        )
        result = _diagnostic_result(spec, rc=2, error="")
        assert result.success is False

    @patch("workspace.scripts.llama_setup_install.subprocess.run")
    def test_run_diagnostic_success(self, mock_run: MagicMock) -> None:
        spec = DiagnosticSpec(
            id="p", label="Probe", script=None, cmd=("true",), optional=False
        )
        result = run_diagnostic(spec)
        assert result.success is True
        mock_run.assert_called_once()


class TestPlanExecution:
    def test_collect_work_items_includes_deploy_and_diagnostics(self) -> None:
        stack = _test_stack(
            deploy=DeploySpec(kind="llamaserver", model=None, gpu=None, flavor="cpu")
        )
        prereq = PrereqSpec(
            id="p",
            label="P",
            description="",
            script="s.sh",
            script_args=(),
            detect_cmds=(),
            needs_sudo=False,
        )
        plan = InstallPlan(
            prereqs=(prereq,),
            stacks=(stack,),
            run_diagnostics=True,
            deploy=True,
            model="minicpm5-1b",
        )
        items = _collect_work_items(plan)
        kinds = [kind for kind, _ref in items]
        assert "prereq" in kinds
        assert "build" in kinds
        assert "deploy" in kinds
        assert "diagnostics" in kinds

    def test_registry_maps_and_find_build_step(self) -> None:
        registry = load_registry()
        maps = _registry_maps(registry)
        stack = registry.stacks[0]
        step = _find_build_step(stack, stack.build_steps[0].id)
        assert step is not None
        assert isinstance(maps, RegistryMaps)

    def test_dispatch_unknown_kind(self) -> None:
        registry = load_registry()
        ctx = DispatchContext(
            maps=_registry_maps(registry),
            registry=registry,
            model="minicpm5-1b",
            on_result=None,
        )
        results = _dispatch_work_item("unknown", "ref", ctx)
        assert results[0].success is False

    def test_run_item_helpers_unknown_refs(self) -> None:
        registry = load_registry()
        maps = _registry_maps(registry)
        assert _run_prereq_item(maps, "missing").success is False
        assert _run_build_item(maps, "missing:step").success is False
        assert _run_deploy_item(maps, "missing", "m").success is False

    @patch("workspace.scripts.llama_setup_install.run_diagnostic")
    def test_run_diagnostics_invokes_callback(self, mock_diag: MagicMock) -> None:
        registry = load_registry()
        mock_diag.return_value = StepResult(label="d", success=True, detail="ok")
        seen: list[str] = []

        def on_result(label: str, success: bool, detail: str) -> None:
            seen.append(label)

        results = _run_diagnostics(registry, on_result)
        assert results
        assert seen

    @patch("workspace.scripts.llama_setup_install.deploy_stack")
    @patch("workspace.scripts.llama_setup_install.run_build_step")
    @patch("workspace.scripts.llama_setup_install.run_prereq")
    @patch("workspace.scripts.llama_setup_install.run_diagnostic")
    def test_execute_plan_runs_callbacks(
        self,
        mock_diag: MagicMock,
        mock_prereq: MagicMock,
        mock_build: MagicMock,
        mock_deploy: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_prereq.return_value = StepResult(label="prereq", success=True, detail="ok")
        mock_build.return_value = StepResult(label="build", success=True, detail="ok")
        mock_deploy.return_value = StepResult(label="deploy", success=True, detail="ok")
        mock_diag.return_value = StepResult(label="diag", success=True, detail="ok")

        prereq = _test_prereq(tmp_path)
        stack = _test_stack(
            deploy=DeploySpec(kind="llamaserver", model=None, gpu=None, flavor="cpu"),
            build_script="scripts/setup/build.sh",
        )
        registry = LlamaSetupRegistry(
            stacks=(stack,), prereqs=(prereq,), diagnostics=()
        )
        plan = InstallPlan(
            prereqs=(prereq,),
            stacks=(stack,),
            run_diagnostics=True,
            deploy=True,
            model="minicpm5-1b",
        )
        progress: list[str] = []
        results_seen: list[str] = []

        execute_plan(
            registry,
            plan,
            on_progress=lambda cur, total, label: progress.append(label),
            on_result=lambda label, _ok, _detail: results_seen.append(label),
        )
        assert progress
        assert "prereq" in progress[0]
        assert results_seen
