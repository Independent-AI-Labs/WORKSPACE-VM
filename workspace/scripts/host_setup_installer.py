"""Host configuration TUI for `sudo make init` and `make install-aux`.

See docs/specifications/SPEC-INSTALLER.md.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dataops.cli_components import dialogs as _dialogs
from dataops.cli_components import menu_selector as _menu
from dataops.cli_components.selection_dialog import DialogItem

from workspace.scripts.bootstrap_aux import detect_configured, run_selected
from workspace.scripts.bootstrap_aux_defs import (
    AUX_DEFAULTS_YAML,
    AuxDefaults,
    AuxFeature,
    AuxManifest,
    features_by_group,
    load_defaults,
    load_registry,
    ordered_features,
    validate_defaults,
)
from workspace.scripts.host_setup_installer_ui import (
    CYAN,
    DIM,
    GREEN,
    RED,
    RESET,
    YELLOW,
    print_section,
    print_status,
    restore_terminal,
)


def _allowed(feature: AuxFeature, scope: str, uid: int) -> bool:
    if scope == "agent":
        return feature.scope == "agent"
    if scope == "root":
        return feature.scope == "root"
    if uid == 0:
        return True
    return feature.scope == "agent"


def _prompt_args(features: list[AuxFeature]) -> dict[str, dict[str, str]]:
    values: dict[str, dict[str, str]] = {}
    for feature in features:
        if not feature.args:
            continue
        print_section(feature.label)
        resolved: dict[str, str] = {}
        for name, spec in feature.args.items():
            label = spec.description or name
            answer = input(f"  {label} [{spec.default}]: ").strip()
            resolved[name] = answer or spec.default
        values[feature.id] = resolved
    return values


def _select_interactive(
    manifest: AuxManifest, scope: str, uid: int
) -> list[AuxFeature]:
    MenuItemClass = _menu.MenuItem
    items: list[DialogItem] = []
    preselected: set[str] = set()
    skippable: set[str] = set()

    for group, features in features_by_group(manifest):
        allowed = [f for f in features if _allowed(f, scope, uid)]
        if not allowed:
            continue
        items.append(
            MenuItemClass(
                id=f"_header_{group}",
                label=group,
                value=None,
                description=f"{len(allowed)} feature(s)",
            )
        )
        for feature in allowed:
            configured = detect_configured(feature)
            if configured:
                skippable.add(feature.id)
            if feature.enabled_by_default:
                preselected.add(feature.id)
            status = "configured" if configured else "not configured"
            items.append(
                MenuItemClass(
                    id=feature.id,
                    label=feature.label,
                    value=feature,
                    description=f"{feature.description} ({status})",
                )
            )

    raw = _dialogs.multiselect(
        items,
        title="Host configuration",
        preselected=preselected,
        skippable_ids=skippable,
        max_height=20,
    )
    return [
        item.value
        for item in raw
        if isinstance(item, _menu.MenuItem) and isinstance(item.value, AuxFeature)
    ]


def _select_defaults(
    manifest: AuxManifest, defaults: AuxDefaults, scope: str, uid: int
) -> tuple[list[AuxFeature], dict[str, dict[str, str]]]:
    validate_defaults(manifest, defaults)
    by_id = {feature.id: feature for feature in manifest.features}
    selected: list[AuxFeature] = []
    values: dict[str, dict[str, str]] = {}
    for feature_id, selection in defaults.features.items():
        feature = by_id[feature_id]
        if not selection.enabled or not _allowed(feature, scope, uid):
            continue
        selected.append(feature)
        values[feature_id] = dict(selection.args)
    return selected, values


def _run(manifest: AuxManifest, scope: str, defaults_path: Path | None) -> int:
    uid = os.geteuid()
    interactive = sys.stdin.isatty() and defaults_path is None
    if interactive:
        selected = _select_interactive(manifest, scope, uid)
        values = _prompt_args(selected)
    else:
        defaults = load_defaults(defaults_path)
        selected, values = _select_defaults(manifest, defaults, scope, uid)

    if not selected:
        print(f"{YELLOW}No host features selected.{RESET}")
        return 0

    ordered = ordered_features(manifest, {f.id for f in selected})
    print_section(f"Host configuration ({len(ordered)} feature(s))")
    for feature in ordered:
        marker = "root" if feature.scope == "root" else "agent"
        print_status("•", f"{feature.label} {DIM}[{marker}]{RESET}", CYAN)

    if interactive and not _dialogs.confirm("Apply these actions?", "Confirm"):
        print(f"{YELLOW}Host configuration cancelled.{RESET}")
        return 0

    results = run_selected(ordered, values)
    failures = [result for result in results if not result.success]
    for result in results:
        color = GREEN if result.success else RED
        icon = "✓" if result.success else "✗"
        print_status(icon, result.message, color)
    if failures:
        return 1
    print(f"\n{GREEN}Host configuration complete.{RESET}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="WORKSPACE host configuration TUI")
    parser.add_argument(
        "--defaults",
        type=Path,
        metavar="FILE",
        help=f"Run non-interactively (default: {AUX_DEFAULTS_YAML})",
    )
    parser.add_argument(
        "--scope",
        choices=("all", "agent", "root"),
        default="all",
        help="Restrict actions by privilege scope",
    )
    args = parser.parse_args()

    try:
        manifest = load_registry()
        return _run(manifest, args.scope, args.defaults)
    except (FileNotFoundError, ValueError) as exc:
        print(f"{RED}ERROR:{RESET} {exc}", file=sys.stderr)
        return 1
    finally:
        restore_terminal()


if __name__ == "__main__":
    sys.exit(main())
