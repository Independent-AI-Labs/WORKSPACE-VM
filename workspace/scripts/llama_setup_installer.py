"""Llama / hardware setup TUI (make llama-setup)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple, cast

import yaml

sys.path.insert(
    0,
    os.environ.get(
        "AMI_PROJECT_ROOT",
        str(
            next(
                p
                for p in Path(__file__).resolve().parents
                if (p / "pyproject.toml").exists()
            )
        ),
    ),
)

from dataops.cli_components import dialogs as _dialogs
from dataops.cli_components import menu_selector as _menu
from dataops.cli_components.selection_dialog import DialogItem

from workspace.config_utils import PROJECT_ROOT
from workspace.scripts.llama_setup_detect import (
    DetectSnapshot,
    collect_snapshot,
    missing_prereqs_for_stack,
)

if TYPE_CHECKING:
    from dataops.cli_components.menu_selector import MenuItem
from workspace.scripts.llama_setup_install import InstallPlan, execute_plan
from workspace.scripts.llama_setup_installer_ui import (
    BANNER,
    CYAN,
    GREEN,
    RED,
    RESET,
    YELLOW,
    print_detect_snapshot,
    print_progress,
    print_section,
    print_status,
    restore_terminal,
)
from workspace.scripts.llama_setup_registry import (
    LlamaSetupRegistry,
    PrereqSpec,
    StackProfile,
    load_registry,
    stack_by_id,
)

DEFAULTS_PATH = PROJECT_ROOT / "workspace" / "config" / "llama-setup-defaults.yaml"


class DefaultsConfig(NamedTuple):
    stack_ids: tuple[str, ...]
    prereq_ids: tuple[str, ...]
    run_diagnostics: bool
    deploy: bool
    model: str


class RunSummary(NamedTuple):
    success_count: int
    failed_labels: list[str]


class PlanBuildInput(NamedTuple):
    registry: LlamaSetupRegistry
    stacks: list[StackProfile]
    snapshot: DetectSnapshot
    extra_prereqs: list[PrereqSpec]
    run_diagnostics: bool
    deploy: bool
    model: str


def _load_defaults(path: Path) -> DefaultsConfig:
    if not path.is_file():
        print(f"{RED}Error:{RESET} defaults file not found: {path}")
        sys.exit(1)
    with open(path, encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        print(f"{RED}Error:{RESET} invalid defaults file: {path}")
        sys.exit(1)
    stacks_raw = data.get("stacks") or []
    prereqs_raw = data.get("prereqs") or []
    stack_ids = (
        tuple(str(item) for item in stacks_raw) if isinstance(stacks_raw, list) else ()
    )
    prereq_ids = (
        tuple(str(item) for item in prereqs_raw)
        if isinstance(prereqs_raw, list)
        else ()
    )
    return DefaultsConfig(
        stack_ids=stack_ids,
        prereq_ids=prereq_ids,
        run_diagnostics=bool(data.get("run_diagnostics", False)),
        deploy=bool(data.get("deploy", False)),
        model=str(data.get("model", "minicpm5-1b")),
    )


def _select_stacks(registry: LlamaSetupRegistry) -> list[StackProfile]:
    MenuItemClass = _menu.MenuItem
    items: list[DialogItem] = [
        MenuItemClass(
            id=stack.id,
            label=stack.label,
            value=stack,
            description=stack.description,
        )
        for stack in registry.stacks
    ]
    raw = _dialogs.multiselect(
        items,
        title="Select stack profile(s)",
        preselected={"llamafile_vulkan_server"},
        max_height=16,
    )
    selected = cast("list[MenuItem[StackProfile]]", raw)
    return [item.value for item in selected if not isinstance(item.value, str)]


def _select_extra_prereqs(
    registry: LlamaSetupRegistry,
    snapshot_prereq_ids: set[str],
) -> list[PrereqSpec]:
    optional = [
        prereq
        for prereq in registry.prereqs
        if prereq.id == "intel_monitoring" and prereq.id not in snapshot_prereq_ids
    ]
    if not optional:
        return []
    if not _dialogs.confirm(
        "Install Intel GPU monitoring (xpu-smi only)?",
        title="Optional prereq",
    ):
        return []
    return optional


def _confirm_deploy(stacks: list[StackProfile]) -> bool:
    deployable = [stack for stack in stacks if stack.deploy is not None]
    if not deployable:
        return False
    names = ", ".join(stack.label for stack in deployable)
    return _dialogs.confirm(
        f"Deploy systemd services for: {names}?",
        title="Service deploy",
    )


def _build_plan(plan_input: PlanBuildInput) -> InstallPlan:
    needed: list[PrereqSpec] = list(plan_input.extra_prereqs)
    seen: set[str] = {p.id for p in needed}
    for stack in plan_input.stacks:
        for missing in missing_prereqs_for_stack(
            plan_input.registry, plan_input.snapshot, stack
        ):
            if missing.id not in seen:
                needed.append(missing)
                seen.add(missing.id)
    return InstallPlan(
        prereqs=tuple(needed),
        stacks=tuple(plan_input.stacks),
        run_diagnostics=plan_input.run_diagnostics,
        deploy=plan_input.deploy,
        model=plan_input.model,
    )


def _run_plan(plan: InstallPlan, registry: LlamaSetupRegistry) -> RunSummary:
    success_count = 0
    failed: list[str] = []

    def on_progress(current: int, total: int, label: str) -> None:
        print_progress(current, total, label)

    def on_result(label: str, success: bool, detail: str) -> None:
        nonlocal success_count
        if success:
            success_count += 1
            print_status("✓", f"{label} ({detail})", GREEN)
        else:
            failed.append(label)
            print_status("✗", f"{label}: {detail}", RED)

    execute_plan(registry, plan, on_progress=on_progress, on_result=on_result)
    return RunSummary(success_count=success_count, failed_labels=failed)


def _print_summary(outcome: RunSummary) -> int:
    print_section("Setup Summary")
    if outcome.failed_labels:
        print_status("✓", f"Successful steps: {outcome.success_count}", GREEN)
        print_status("✗", f"Failed steps: {len(outcome.failed_labels)}", RED)
        for label in outcome.failed_labels:
            print_status("  •", label, RED)
        return 1
    print_status("✓", f"All {outcome.success_count} step(s) completed", GREEN)
    print(f"\n{CYAN}{'─' * 60}{RESET}")
    print(f"{GREEN}  Llama setup complete.{RESET}")
    print(f"{CYAN}{'─' * 60}{RESET}\n")
    return 0


def _run_interactive(registry: LlamaSetupRegistry) -> int:
    print(BANNER)
    snapshot = collect_snapshot(registry)
    print_detect_snapshot(snapshot)

    stacks = _select_stacks(registry)
    if not stacks:
        print(f"{YELLOW}No stacks selected. Exiting.{RESET}")
        return 0

    extra_prereqs = _select_extra_prereqs(registry, set())
    deploy = _confirm_deploy(stacks)
    run_diagnostics = _dialogs.confirm(
        "Run post-setup diagnostics (Vulkan probe, xpu-smi, tests)?",
        title="Diagnostics",
    )

    plan = _build_plan(
        PlanBuildInput(
            registry=registry,
            stacks=stacks,
            snapshot=snapshot,
            extra_prereqs=extra_prereqs,
            run_diagnostics=run_diagnostics,
            deploy=deploy,
            model="minicpm5-1b",
        )
    )

    print_section(f"Installing {len(plan.stacks)} stack(s)")
    for stack in plan.stacks:
        print_status("•", stack.label, CYAN)
    print()

    summary = _run_plan(plan, registry)
    return _print_summary(summary)


def _run_from_defaults(registry: LlamaSetupRegistry, defaults_path: Path) -> int:
    print(f"{CYAN}Running llama-setup CI mode:{RESET} {defaults_path}\n")
    config = _load_defaults(defaults_path)
    stacks: list[StackProfile] = []
    for stack_id in config.stack_ids:
        stack = stack_by_id(registry, stack_id)
        if stack is not None:
            stacks.append(stack)
        else:
            print(f"{YELLOW}Warning:{RESET} unknown stack '{stack_id}', skipping")

    if not stacks:
        print(f"{YELLOW}No valid stacks in defaults. Exiting.{RESET}")
        return 0

    snapshot = collect_snapshot(registry)
    prereq_map = {prereq.id: prereq for prereq in registry.prereqs}
    extra_prereqs = [
        prereq_map[prereq_id]
        for prereq_id in config.prereq_ids
        if prereq_id in prereq_map
    ]

    plan = _build_plan(
        PlanBuildInput(
            registry=registry,
            stacks=stacks,
            snapshot=snapshot,
            extra_prereqs=extra_prereqs,
            run_diagnostics=config.run_diagnostics,
            deploy=config.deploy,
            model=config.model,
        )
    )

    print_section(f"Installing {len(plan.stacks)} stack(s) (CI)")
    summary = _run_plan(plan, registry)
    return _print_summary(summary)


def _main_impl() -> int:
    parser = argparse.ArgumentParser(description="Llama / hardware setup TUI")
    parser.add_argument(
        "--defaults",
        type=Path,
        metavar="FILE",
        help="Non-interactive mode using YAML defaults",
    )
    args = parser.parse_args()

    registry = load_registry()

    if args.defaults is not None:
        return _run_from_defaults(registry, args.defaults)

    if not sys.stdin.isatty():
        print(
            f"{RED}Error:{RESET} interactive mode requires a TTY.\n"
            f"Use: make llama-setup-ci  or  --defaults {DEFAULTS_PATH}"
        )
        return 1

    return _run_interactive(registry)


def main() -> int:
    try:
        return _main_impl()
    except (KeyboardInterrupt, SystemExit):
        restore_terminal()
        raise
    except Exception:
        restore_terminal()
        raise
    finally:
        restore_terminal()


if __name__ == "__main__":
    raise SystemExit(main())
