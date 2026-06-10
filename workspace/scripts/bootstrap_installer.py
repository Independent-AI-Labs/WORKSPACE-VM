#!/usr/bin/env python3
"""
Bootstrap Installer TUI for AMI Orchestrator.

Provides an interactive multi-select interface for installing optional
bootstrap components with status detection.

Supports non-interactive mode via --defaults flag for CI environments.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple, cast

import yaml

# Ruff E402 exempts sys.path.insert between imports
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
sys.path.insert(0, str(Path(__file__).parent))

from dataops.cli_components import dialogs as _dialogs
from dataops.cli_components import menu_selector as _menu
from dataops.cli_components.selection_dialog import DialogItem

import workspace.scripts.bootstrap_component_defs as _bootstrap_defs
import workspace.scripts.bootstrap_install as _bootstrap_install
from workspace.scripts.bootstrap_install import get_bootstrap_env
from workspace.scripts.bootstrap_installer_ui import (
    BANNER,
    CYAN,
    DIM,
    GREEN,
    RED,
    RESET,
    YELLOW,
    print_progress,
    print_section,
    print_status,
    restore_terminal,
)
from workspace.types.results import NamedComponentStatus

if TYPE_CHECKING:
    from dataops.cli_components.menu_selector import MenuItem

    from workspace.scripts.bootstrap_components import Component


class MenuBuildResult(NamedTuple):
    """Result from building menu items."""

    menu_items: object  # list of MenuItem with Component or None values
    preselected_ids: set[str]
    skippable_ids: set[str]  # IDs of installed components (can skip reinstall)


class InstallationResult(NamedTuple):
    """Result from running installation."""

    success_count: int
    failed_labels: list[str]


def _find_status_by_name(
    statuses: list[NamedComponentStatus], name: str
) -> NamedComponentStatus | None:
    """Find a status entry by component name."""
    for s in statuses:
        if s.name == name:
            return s
    return None


def format_component_label(comp: Component, status: NamedComponentStatus | None) -> str:
    """Format component label with version if installed."""
    if status and status.installed and status.version:
        return f"{comp.label} {GREEN}v{status.version}{RESET}"
    return comp.label


def format_component_description(
    comp: Component, status: NamedComponentStatus | None
) -> str:
    """Format component description with status."""
    if status and status.installed:
        return f"{comp.description} {GREEN}✓{RESET}"
    return f"{comp.description} {DIM}(not installed){RESET}"


def scan_components() -> list[NamedComponentStatus]:
    """Scan all components and return their status as a list.

    Each status has a name field for lookups.
    """
    print(f"\n{CYAN}Scanning installed components...{RESET}")

    groups = _bootstrap_defs.get_components_by_group()
    statuses: list[NamedComponentStatus] = []
    env = get_bootstrap_env()

    total = sum(len(g.components) for g in groups)

    for group in groups:
        for comp in group.components:
            # Show scanning progress
            sys.stdout.write(f"\r  Checking {comp.label}...{' ' * 20}")
            sys.stdout.flush()

            raw_status = comp.get_status(env=env)
            statuses.append(
                NamedComponentStatus(
                    name=comp.name,
                    installed=raw_status.installed,
                    version=raw_status.version,
                    path=raw_status.path,
                )
            )

    sys.stdout.write(f"\r{' ' * 60}\r")  # Clear line
    sys.stdout.flush()

    # Print summary
    installed = sum(1 for s in statuses if s.installed)
    print(f"  {GREEN}✓{RESET} Found {installed}/{total} components installed\n")

    return statuses


def build_menu_items(
    statuses: list[NamedComponentStatus],
) -> MenuBuildResult:
    """Build menu items with status information.

    Workspace repos are NOT included here — they have a dedicated first-step
    dialog (`select_workspace_repos`). This dialog is for tools/components only.

    Returns:
        MenuBuildResult with menu_items, preselected_ids, and skippable_ids
    """
    groups = _bootstrap_defs.get_components_by_group()
    menu_items: list[DialogItem] = []
    preselected: set[str] = set()
    skippable: set[str] = set()  # IDs of installed components
    MenuItemClass = _menu.MenuItem

    for group in groups:
        if not group.components:
            continue
        if group.group == _bootstrap_defs.WORKSPACE_REPOS_GROUP:
            continue

        # Core Dependencies are mandatory (disabled = locked)
        is_core = group.group == "Core Dependencies"

        # Count installed in group
        installed_count = sum(
            1
            for c in group.components
            if (
                _find_status_by_name(statuses, c.name)
                or NamedComponentStatus(c.name, False, None, None)
            ).installed
        )

        # Add group header with (required) suffix for core deps
        header_label = f"{group.group} (required)" if is_core else group.group
        menu_items.append(
            MenuItemClass(
                id=f"_header_{group.group}",
                label=header_label,
                value=None,
                description=f"{installed_count}/{len(group.components)} installed",
            )
        )

        # Add components in this group
        for comp in group.components:
            status = _find_status_by_name(statuses, comp.name)

            # Track installed components as skippable (can toggle skip/reinstall)
            if status and status.installed:
                skippable.add(comp.name)

            menu_items.append(
                MenuItemClass(
                    id=comp.name,
                    label=format_component_label(comp, status),
                    value=comp,
                    description=format_component_description(comp, status),
                    disabled=is_core,  # Core deps are locked
                )
            )

    return MenuBuildResult(
        menu_items=menu_items, preselected_ids=preselected, skippable_ids=skippable
    )


def _extract_components(selected: list[MenuItem[Component]]) -> list[Component]:
    """Extract component values from selected menu items."""
    # MenuItem.value is T | str (uses id if value was None)
    # We know our values are Component instances, so filter non-strings
    return [item.value for item in selected if not isinstance(item.value, str)]


def _is_mandatory_repo(comp: Component) -> bool:
    """Mandatory workspace-repo entries are tagged in their description."""
    return comp.description.startswith("[mandatory]")


def select_workspace_repos(
    statuses: list[NamedComponentStatus],
) -> list[Component]:
    """Step 1 of the TUI — dedicated workspace-repo selection.

    Mandatory entries (workspace-ci, ami-dataops) render locked-on so the user sees
    the full workspace topology and can't deselect them. Optional entries
    opt-in via checkbox. Already-cloned repos are marked skippable.
    """
    repos = list(_bootstrap_defs.WORKSPACE_REPOS)
    if not repos:
        return []

    print_section("Step 1 of 2 — Select Workspace Repositories")
    print(
        f"  {DIM}Mandatory repos are pre-selected and locked. "
        f"Optional repos opt-in below.{RESET}\n"
    )

    MenuItemClass = _menu.MenuItem
    items: list[DialogItem] = []
    preselected: set[str] = set()
    skippable: set[str] = set()

    for comp in repos:
        status = _find_status_by_name(statuses, comp.name)
        is_mandatory = _is_mandatory_repo(comp)
        if is_mandatory:
            preselected.add(comp.name)
        if status and status.installed:
            skippable.add(comp.name)
        items.append(
            MenuItemClass(
                id=comp.name,
                label=format_component_label(comp, status),
                value=comp,
                description=format_component_description(comp, status),
                disabled=is_mandatory,
            )
        )

    raw = _dialogs.multiselect(
        items,
        title="Workspace Repositories",
        preselected=preselected,
        skippable_ids=skippable,
        max_height=20,
    )
    selected = cast(list["MenuItem[Component]"], raw)
    chosen = _extract_components([s for s in selected if s.value is not None])

    # Mandatory entries always come back even if disabled in the menu —
    # but defend against UI quirks: re-add any missing mandatories.
    chosen_names = {c.name for c in chosen}
    for comp in repos:
        if _is_mandatory_repo(comp) and comp.name not in chosen_names:
            chosen.append(comp)

    return chosen


def _show_selection_summary(
    components: list[Component], statuses: list[NamedComponentStatus]
) -> None:
    """Display selected components with install/reinstall status."""
    print_section(f"Selected {len(components)} Component(s)")
    for comp in components:
        status = _find_status_by_name(statuses, comp.name)
        if status and status.installed:
            print_status("•", f"{comp.label} {DIM}(reinstall){RESET}", CYAN)
        else:
            print_status("•", comp.label, CYAN)


def _run_installation(components: list[Component]) -> InstallationResult:
    """Run installation and return InstallationResult."""
    _bootstrap_install.ensure_directories()
    print_status("✓", "Ensured directories exist", GREEN)

    success_count = 0
    failed: list[str] = []

    def on_progress(current: int, total: int, label: str) -> None:
        print_progress(current, total, label)

    def on_result(comp: Component, success: bool) -> None:
        nonlocal success_count
        if success:
            success_count += 1
            print_status("✓", f"{comp.label} installed", GREEN)
        else:
            failed.append(comp.label)
            print_status("✗", f"{comp.label} failed", RED)

    _bootstrap_install.install_components(
        list(components), on_progress=on_progress, on_result=on_result
    )
    return InstallationResult(success_count=success_count, failed_labels=failed)


def _print_summary(success_count: int, failed: list[str]) -> int:
    """Print installation summary and return exit code."""
    print_section("Installation Summary")

    if failed:
        print_status("✓", f"Successful: {success_count}", GREEN)
        print_status("✗", f"Failed: {len(failed)}", RED)
        print()
        for name in failed:
            print_status("  •", name, RED)
        return 1

    print_status(
        "✓", f"All {success_count} component(s) installed successfully!", GREEN
    )
    print(f"\n{CYAN}{'─' * 60}{RESET}")
    print(f"{GREEN}  Installation complete!{RESET}")
    print(f"{CYAN}{'─' * 60}{RESET}\n")
    return 0


def _load_defaults(defaults_file: Path) -> list[str]:
    """Load component names from defaults file."""
    if not defaults_file.exists():
        print(f"{RED}Error:{RESET} Defaults file not found: {defaults_file}")
        sys.exit(1)

    with open(defaults_file) as f:
        data = yaml.safe_load(f)

    if not data or "components" not in data:
        print(f"{RED}Error:{RESET} Invalid defaults file: missing 'components' key")
        sys.exit(1)

    return list(data["components"])


def _run_from_defaults(defaults_file: Path) -> int:
    """Run installation from defaults file (non-interactive CI mode)."""
    print(f"{CYAN}Running in CI mode with defaults from:{RESET} {defaults_file}\n")

    component_names = _load_defaults(defaults_file)

    # Mandatory workspace repos (e.g. workspace-ci, ami-dataops) are always
    # installed in CI mode regardless of install-defaults.yaml content,
    # so the workspace-clones.yaml manifest stays the source of truth.
    mandatory_repo_names = [
        c.name
        for c in _bootstrap_defs.WORKSPACE_REPOS
        if c.description.startswith("[mandatory]")
    ]
    for name in mandatory_repo_names:
        if name not in component_names:
            component_names.append(name)

    print(f"  Components to install: {', '.join(component_names)}\n")

    # Resolve component names to Component objects
    components: list[Component] = []
    for name in component_names:
        comp = _bootstrap_defs.get_component_by_name(name)
        if comp:
            components.append(comp)
        else:
            print(f"{YELLOW}Warning:{RESET} Unknown component '{name}', skipping")

    if not components:
        print(f"{YELLOW}No valid components found. Exiting.{RESET}")
        return 0

    print_section(f"Installing {len(components)} Component(s)")
    for comp in components:
        print_status("•", comp.label, CYAN)

    print()
    install_result = _run_installation(components)
    return _print_summary(install_result.success_count, install_result.failed_labels)


def main() -> int:
    """Main entry point for the bootstrap installer TUI."""
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


def _main_impl() -> int:
    """Main entry point for the bootstrap installer TUI."""
    parser = argparse.ArgumentParser(
        description="Bootstrap Installer for AMI Orchestrator"
    )
    parser.add_argument(
        "--defaults",
        type=Path,
        metavar="FILE",
        help="Run non-interactively using component list from YAML file",
    )
    args = parser.parse_args()

    # Non-interactive mode
    if args.defaults:
        return _run_from_defaults(args.defaults)

    # Interactive mode requires TTY
    if not sys.stdin.isatty():
        print(f"{RED}Error:{RESET} This script requires an interactive terminal.")
        print("Run it directly, not through a pipe.")
        print(f"\n{CYAN}Tip:{RESET} Use --defaults FILE for non-interactive CI mode.")
        return 1

    print(BANNER)
    statuses = scan_components()

    # Step 1 — dedicated workspace-repo selection (mandatory locked-on,
    # optional opt-in). Repos clone first so subsequent component installs
    # have the on-disk graph available.
    repo_components = select_workspace_repos(statuses)

    # Step 2 — components multi-select (everything except workspace repos).
    print_section("Step 2 of 2 — Select Components")
    menu_build_result = build_menu_items(statuses)
    menu_items = menu_build_result.menu_items
    preselected = menu_build_result.preselected_ids
    skippable = menu_build_result.skippable_ids

    # MenuItem implements SelectableItem protocol structurally
    dialog_items = cast(list[DialogItem], menu_items)
    raw_selected = _dialogs.multiselect(
        dialog_items,
        title="Select Components",
        preselected=preselected,
        skippable_ids=skippable,
        max_height=20,
    )

    # Cast back to MenuItem since we know what we passed in
    selected = cast(list["MenuItem[Component]"], raw_selected)
    selected = [s for s in selected if s.value is not None]

    component_components = _extract_components(selected)
    components = [*repo_components, *component_components]

    if not components:
        print(f"\n{YELLOW}Nothing selected. Exiting.{RESET}")
        return 0

    _show_selection_summary(components, statuses)

    print()
    if not _dialogs.confirm(f"Install {len(components)} component(s)?", "Confirm"):
        print(f"\n{YELLOW}Installation cancelled.{RESET}")
        return 0

    print_section("Installing Components")
    install_result = _run_installation(components)
    return _print_summary(install_result.success_count, install_result.failed_labels)


if __name__ == "__main__":
    sys.exit(main())
