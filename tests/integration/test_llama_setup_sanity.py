"""Integration sanity tests for make llama-setup modules."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from workspace.config_utils import PROJECT_ROOT
from workspace.scripts.llama_setup_detect import collect_snapshot
from workspace.scripts.llama_setup_install import InstallPlan, _collect_work_items
from workspace.scripts.llama_setup_installer import (
    DefaultsConfig,
    PlanBuildInput,
    _build_plan,
    _load_defaults,
    _run_from_defaults,
)
from workspace.scripts.llama_setup_installer_ui import print_detect_snapshot
from workspace.scripts.llama_setup_registry import (
    load_registry,
    stack_by_id,
)


class TestLlamaSetupRegistrySanity:
    def test_load_registry_from_project_tree(self) -> None:
        registry = load_registry()
        assert registry.stacks
        assert registry.prereqs
        assert registry.diagnostics

    def test_stack_by_id_resolves_known_profile(self) -> None:
        registry = load_registry()
        stack = stack_by_id(registry, "llama_cpp_cpu")
        assert stack is not None
        assert stack.deploy is not None


class TestLlamaSetupDetectSanity:
    def test_collect_snapshot_runs_live_probes(self) -> None:
        registry = load_registry()
        snapshot = collect_snapshot(registry)
        assert snapshot.hardware is not None
        assert len(snapshot.prereqs) == len(registry.prereqs)
        assert len(snapshot.stacks) == len(registry.stacks)

    def test_print_detect_snapshot_renders(self, capsys) -> None:
        registry = load_registry()
        snapshot = collect_snapshot(registry)
        print_detect_snapshot(snapshot)
        output = capsys.readouterr().out
        assert "Hardware Detection" in output
        assert "Stack Build Status" in output


class TestLlamaSetupInstallerSanity:
    def test_load_defaults_from_repo_file(self) -> None:
        defaults_path = PROJECT_ROOT / "workspace/config/llama-setup-defaults.yaml"
        config = _load_defaults(defaults_path)
        assert isinstance(config, DefaultsConfig)
        assert config.stack_ids

    def test_build_plan_merges_stack_prereqs(self) -> None:
        registry = load_registry()
        stack = stack_by_id(registry, "llamafile_vulkan_server")
        assert stack is not None
        snapshot = collect_snapshot(registry)
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
        assert isinstance(plan, InstallPlan)
        assert plan.stacks == (stack,)
        assert _collect_work_items(plan)


class TestLlamaSetupCiDefaultsSanity:
    def test_defaults_path_drives_non_interactive_entry(self, tmp_path: Path) -> None:
        defaults = tmp_path / "llama-defaults.yaml"
        defaults.write_text(
            "stacks: [llama_cpp_cpu]\n"
            "prereqs: []\n"
            "run_diagnostics: false\n"
            "deploy: false\n"
            "model: minicpm5-1b\n",
            encoding="utf-8",
        )
        with (
            patch(
                "workspace.scripts.llama_setup_installer.execute_plan",
                return_value=[],
            ),
            patch(
                "workspace.scripts.llama_setup_installer.collect_snapshot",
                return_value=collect_snapshot(load_registry()),
            ),
        ):
            registry = load_registry()
            result = _run_from_defaults(registry, defaults)
        assert result == 0
