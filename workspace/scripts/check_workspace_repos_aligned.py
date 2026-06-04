#!/usr/bin/env python3
"""Verify .moon/workspace.yml::projects and workspace-clones.yaml agree.

Both files list the workspace's repos but for different consumers:
  - .moon/workspace.yml::projects — moon's project graph (drives `moon run
    :update`, `moon ci --affected`, every cross-project task walk).
  - workspace/config/workspace-clones.yaml::workspaceClones — the boot installer's
    repo-selection step + the chicken-egg-safe clone walker
    (bootstrap-repos).

If a repo lives in one but not the other, you get split-brain: moon updates
something the installer never clones, or the installer clones something moon
ignores. This check fires on `make check`/CI and blocks the merge.

Exit 0 if aligned, 1 if drifted, 2 on infra error.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from workspace.scripts.bootstrap_component_defs import WorkspaceClonesManifest

EXIT_OK = 0
EXIT_DRIFT = 1
EXIT_INFRA = 2


class MoonWorkspace(BaseModel):
    """Subset of the .moon/workspace.yml schema we care about. extra='ignore'
    so unrelated keys (vcs, pipeline, telemetry) pass through."""

    model_config = ConfigDict(extra="ignore")

    projects: dict[str, str] = Field(default_factory=dict)


def _find_workspace_root(start: Path) -> Path | None:
    cur = start.resolve()
    while cur != cur.parent:
        if (cur / ".moon" / "workspace.yml").exists() and (
            cur / "workspace" / "config" / "workspace-clones.yaml"
        ).exists():
            return cur
        cur = cur.parent
    return None


def _load_yaml(path: Path) -> object:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def main(argv: list[str] | None = None) -> int:
    root = _find_workspace_root(Path(__file__).resolve().parent)
    if root is None:
        print(
            "ERROR: cannot find workspace root with both .moon/workspace.yml "
            "and workspace/config/workspace-clones.yaml",
            file=sys.stderr,
        )
        return EXIT_INFRA

    moon_yaml = root / ".moon" / "workspace.yml"
    clones_yaml = root / "workspace" / "config" / "workspace-clones.yaml"

    try:
        moon = MoonWorkspace.model_validate(_load_yaml(moon_yaml))
        clones = WorkspaceClonesManifest.model_validate(_load_yaml(clones_yaml))
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        print(f"ERROR: failed to load registries: {exc}", file=sys.stderr)
        return EXIT_INFRA

    # Drop the umbrella entry — the umbrella IS the workspace root, it isn't
    # cloned by the bootstrap walker.
    moon_projects = {k: v for k, v in moon.projects.items() if v != "."}
    clone_paths = {eid: e.path for eid, e in clones.workspaceClones.items()}

    moon_ids = set(moon_projects.keys())
    clone_ids = set(clone_paths.keys())

    only_in_moon = moon_ids - clone_ids
    only_in_clones = clone_ids - moon_ids
    path_mismatches: list[tuple[str, str, str]] = [
        (shared_id, moon_projects[shared_id], clone_paths[shared_id])
        for shared_id in moon_ids & clone_ids
        if moon_projects[shared_id] != clone_paths[shared_id]
    ]

    if not (only_in_moon or only_in_clones or path_mismatches):
        print("✓ .moon/workspace.yml and workspace-clones.yaml are aligned")
        return EXIT_OK

    print(
        "✗ workspace registries drifted between "
        ".moon/workspace.yml and workspace/config/workspace-clones.yaml",
        file=sys.stderr,
    )
    if only_in_moon:
        print(
            f"  in .moon/workspace.yml but missing from workspace-clones.yaml: "
            f"{sorted(only_in_moon)}",
            file=sys.stderr,
        )
    if only_in_clones:
        print(
            f"  in workspace-clones.yaml but missing from .moon/workspace.yml: "
            f"{sorted(only_in_clones)}",
            file=sys.stderr,
        )
    for entry_id, moon_path, clone_path in path_mismatches:
        print(
            f"  path mismatch for '{entry_id}': "
            f"moon={moon_path!r} vs clones={clone_path!r}",
            file=sys.stderr,
        )
    return EXIT_DRIFT


if __name__ == "__main__":
    sys.exit(main())
