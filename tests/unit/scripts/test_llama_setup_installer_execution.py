"""Unit tests for llama_setup_installer main and CI defaults path."""

from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from workspace.scripts.llama_setup_install import InstallPlan
from workspace.scripts.llama_setup_installer import (
    DefaultsConfig,
    PlanBuildInput,
    RunSummary,
    _build_plan,
    _confirm_deploy,
    _load_defaults,
    _print_summary,
    _run_from_defaults,
    _run_interactive,
    _run_plan,
    _select_extra_prereqs,
    _select_stacks,
    main,
)
from workspace.scripts.llama_setup_registry import (
    DeploySpec,
    PrereqSpec,
    StackProfile,
    load_registry,
)


class TestLoadDefaults:
    def test_load_defaults_parses_stacks(self) -> None:
        path = (
            Path(__file__).resolve().parents[3]
            / "workspace/config/llama-setup-defaults.yaml"
        )
        config = _load_defaults(path)
        assert isinstance(config, DefaultsConfig)
        assert "llamafile_vulkan_server" in config.stack_ids
        assert config.deploy is True


class TestPrintSummary:
    def test_success_exit_code(self) -> None:
        assert _print_summary(RunSummary(success_count=2, failed_labels=[])) == 0

    def test_failure_exit_code(self) -> None:
        assert _print_summary(RunSummary(success_count=1, failed_labels=["step"])) == 1


class TestMain:
    @patch("workspace.scripts.llama_setup_installer._run_from_defaults")
    @patch("sys.stdin")
    def test_defaults_skips_tty_check(self, mock_stdin, mock_run_defaults) -> None:
        mock_run_defaults.return_value = 0
        path = Path("workspace/config/llama-setup-defaults.yaml")
        with patch(
            "sys.argv",
            ["llama_setup_installer.py", "--defaults", str(path)],
        ):
            result = main()
        assert result == 0
        mock_run_defaults.assert_called_once()

    @patch("sys.stdin")
    def test_non_tty_without_defaults_exits(self, mock_stdin) -> None:
        mock_stdin.isatty.return_value = False
        with patch("sys.argv", ["llama_setup_installer.py"]):
            result = main()
        assert result == 1


class TestRegistryIntegration:
    def test_registry_loads_from_disk(self) -> None:
        registry = load_registry()
        ids = {stack.id for stack in registry.stacks}
        assert "llama_cpp_cpu" in ids
        assert "llamafile_vulkan_server" in ids


class TestLoadDefaultsErrors:
    def test_missing_defaults_exits(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit) as exc:
            _load_defaults(tmp_path / "missing.yaml")
        assert exc.value.code == 1

    def test_invalid_defaults_exits(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text("not-a-mapping\n", encoding="utf-8")
        with pytest.raises(SystemExit) as exc:
            _load_defaults(bad)
        assert exc.value.code == 1


class TestInteractiveHelpers:
    def test_select_stacks_returns_profiles(self) -> None:
        registry = load_registry()
        stack = registry.stacks[0]
        menu_item = MagicMock(value=stack)
        with patch(
            "workspace.scripts.llama_setup_installer._dialogs.multiselect",
            return_value=[menu_item],
        ):
            selected = _select_stacks(registry)
        assert selected == [stack]

    def test_select_extra_prereqs_declined(self) -> None:
        registry = load_registry()
        with patch(
            "workspace.scripts.llama_setup_installer._dialogs.confirm",
            return_value=False,
        ):
            result = _select_extra_prereqs(registry, set())
        assert result == []

    def test_confirm_deploy_no_deployable_stacks(self) -> None:
        stack = StackProfile(
            id="s",
            label="S",
            description="",
            prereq_ids=(),
            build_steps=(),
            deploy=None,
        )
        assert _confirm_deploy([stack]) is False

    def test_confirm_deploy_prompts(self) -> None:
        stack = StackProfile(
            id="s",
            label="Deployable",
            description="",
            prereq_ids=(),
            build_steps=(),
            deploy=DeploySpec(kind="llamaserver", model=None, gpu=None, flavor="cpu"),
        )
        with patch(
            "workspace.scripts.llama_setup_installer._dialogs.confirm",
            return_value=True,
        ):
            assert _confirm_deploy([stack]) is True


class TestPlanAndRun:
    def test_build_plan_collects_missing_prereqs(self) -> None:
        registry = load_registry()
        stack = next(s for s in registry.stacks if s.id == "llamafile_vulkan_server")
        snapshot = MagicMock()
        snapshot.prereqs = ()
        with patch(
            "workspace.scripts.llama_setup_installer.missing_prereqs_for_stack",
            return_value=(
                PrereqSpec(
                    id="vulkan_dev",
                    label="Vulkan",
                    description="",
                    script="s.sh",
                    script_args=(),
                    detect_cmds=(),
                    needs_sudo=True,
                ),
            ),
        ):
            plan = _build_plan(
                PlanBuildInput(
                    registry=registry,
                    stacks=[stack],
                    snapshot=snapshot,
                    extra_prereqs=[],
                    run_diagnostics=False,
                    deploy=False,
                    model="minicpm5-1b",
                )
            )
        assert plan.prereqs[0].id == "vulkan_dev"

    @patch("workspace.scripts.llama_setup_installer.execute_plan")
    def test_run_plan_counts_results(self, mock_execute: MagicMock) -> None:
        registry = load_registry()
        plan = InstallPlan(
            prereqs=(), stacks=(), run_diagnostics=False, deploy=False, model="m"
        )

        def fake_execute(_registry, _plan, *, on_progress, on_result):
            on_progress(1, 2, "prereq:x")
            on_result("ok-step", True, "done")
            on_result("bad-step", False, "failed")
            return []

        mock_execute.side_effect = fake_execute
        outcome = _run_plan(plan, registry)
        assert outcome.success_count == 1
        assert outcome.failed_labels == ["bad-step"]

    @patch("workspace.scripts.llama_setup_installer._print_summary", return_value=0)
    @patch("workspace.scripts.llama_setup_installer._run_plan")
    @patch("workspace.scripts.llama_setup_installer.collect_snapshot")
    def test_run_from_defaults_skips_unknown_stack(
        self,
        mock_snapshot: MagicMock,
        mock_run_plan: MagicMock,
        mock_summary: MagicMock,
        tmp_path: Path,
    ) -> None:
        defaults = tmp_path / "defaults.yaml"
        defaults.write_text(
            "stacks: [missing_stack, llama_cpp_cpu]\n"
            "prereqs: []\n"
            "run_diagnostics: false\n"
            "deploy: false\n"
            "model: minicpm5-1b\n",
            encoding="utf-8",
        )
        mock_snapshot.return_value = MagicMock(prereqs=())
        mock_run_plan.return_value = RunSummary(success_count=1, failed_labels=[])
        registry = load_registry()
        result = _run_from_defaults(registry, defaults)
        assert result == 0
        mock_summary.assert_called_once()

    def test_run_interactive_happy_path(self) -> None:
        registry = load_registry()
        stack = registry.stacks[0]
        with ExitStack() as exit_stack:
            mock_print_snapshot = exit_stack.enter_context(
                patch("workspace.scripts.llama_setup_installer.print_detect_snapshot")
            )
            exit_stack.enter_context(
                patch(
                    "workspace.scripts.llama_setup_installer.collect_snapshot",
                    return_value=MagicMock(prereqs=()),
                )
            )
            exit_stack.enter_context(
                patch(
                    "workspace.scripts.llama_setup_installer._select_stacks",
                    return_value=[stack],
                )
            )
            mock_extra = exit_stack.enter_context(
                patch(
                    "workspace.scripts.llama_setup_installer._select_extra_prereqs",
                    return_value=[],
                )
            )
            mock_deploy = exit_stack.enter_context(
                patch(
                    "workspace.scripts.llama_setup_installer._confirm_deploy",
                    return_value=False,
                )
            )
            exit_stack.enter_context(
                patch(
                    "workspace.scripts.llama_setup_installer._run_plan",
                    return_value=RunSummary(success_count=2, failed_labels=[]),
                )
            )
            mock_summary = exit_stack.enter_context(
                patch(
                    "workspace.scripts.llama_setup_installer._print_summary",
                    return_value=0,
                )
            )
            exit_stack.enter_context(
                patch(
                    "workspace.scripts.llama_setup_installer._dialogs.confirm",
                    return_value=True,
                )
            )
            result = _run_interactive(registry)
        assert result == 0
        mock_print_snapshot.assert_called_once()
        mock_extra.assert_called_once()
        mock_deploy.assert_called_once()
        mock_summary.assert_called_once()

    @patch("workspace.scripts.llama_setup_installer._select_stacks", return_value=[])
    @patch("workspace.scripts.llama_setup_installer.collect_snapshot")
    @patch("workspace.scripts.llama_setup_installer.print_detect_snapshot")
    def test_run_interactive_no_stacks_selected(
        self,
        mock_print_snapshot: MagicMock,
        mock_collect: MagicMock,
        mock_select: MagicMock,
    ) -> None:
        registry = load_registry()
        mock_collect.return_value = MagicMock(prereqs=())
        assert _run_interactive(registry) == 0
        mock_print_snapshot.assert_called_once()
        mock_select.assert_called_once()


class TestPrintSummaryOutput:
    def test_print_summary_success_messages(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert _print_summary(RunSummary(success_count=3, failed_labels=[])) == 0
        captured = capsys.readouterr().out
        assert "All 3 step(s) completed" in captured
        assert "Llama setup complete" in captured

    def test_print_summary_failure_lists_labels(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert (
            _print_summary(RunSummary(success_count=1, failed_labels=["step-a"])) == 1
        )
        captured = capsys.readouterr().out
        assert "Failed steps" in captured
        assert "step-a" in captured
