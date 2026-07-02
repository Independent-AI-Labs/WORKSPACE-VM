"""Bootstrap component data loader.

The component data lives in:
  - workspace/config/bootstrap-components.yaml   (tools/components per group)
  - workspace/config/workspace-clones.yaml       (workspace repos to clone)

This module loads both YAML files via Pydantic manifest models and exposes:
  - ALL_COMPONENTS         - flat list, in load order (CORE_DEPS first)
  - WORKSPACE_REPOS        - workspace-repo subset (used by the TUI's
                             dedicated repo-selection step)
  - GROUPS                 - display-order list of group names
  - get_components_by_group()
  - get_component_by_name()

Component model lives in bootstrap_components.py (Layer 1).
This file is Layer 2: schemas + loader. Dep direction: this -> bootstrap_components.
"""

import json

import yaml
from pydantic import BaseModel, ConfigDict, Field

from workspace.config_utils import PROJECT_ROOT
from workspace.scripts.bootstrap_components import (
    Component,
    ComponentType,
    GroupComponents,
)

WORKSPACE_REPOS_GROUP = "Workspace Repositories"
WORKSPACE_CLONES_YAML = PROJECT_ROOT / "workspace" / "config" / "workspace-clones.yaml"
COMPONENTS_YAML = PROJECT_ROOT / "workspace" / "config" / "bootstrap-components.yaml"
PACKAGE_JSON = PROJECT_ROOT / "workspace" / "scripts" / "package.json"


# --------------------------------------
# Manifest schemas - Pydantic models for the two YAML config files. The
# Component class (in bootstrap_components.py) is the public output type;
# these schemas describe the on-disk shape.
# --------------------------------------


class RequiresEntry(BaseModel):
    """One system dependency entry - checked by pre-req.sh."""

    model_config = ConfigDict(extra="forbid")

    check_cmd: str | None = None
    check_type: str | None = None
    apt_package: str | None = None
    bootstrap_script: str | None = None
    description: str
    optional: bool = False


class ComponentManifestEntry(BaseModel):
    """One entry in ami/config/bootstrap-components.yaml::components."""

    model_config = ConfigDict(extra="forbid")

    name: str
    label: str
    description: str
    type: ComponentType = ComponentType.SCRIPT
    group: str
    script: str | None = None
    script_path: str | None = None
    detect_cmd: list[str] | None = None
    detect_path: str | None = None
    version_pattern: str | None = None
    version_cmd: list[str] | None = None
    package: str | None = None
    package_ref: str | None = None
    requires: list[RequiresEntry] | None = None

    def to_component(self, pkg_versions: dict[str, str]) -> Component:
        package = self.package
        if self.package_ref:
            version = pkg_versions.get(self.package_ref, "latest")
            package = f"{self.package_ref}@{version}"
        return Component(
            name=self.name,
            label=self.label,
            description=self.description,
            type=self.type,
            group=self.group,
            package=package,
            script=self.script,
            script_path=self.script_path,
            detect_cmd=self.detect_cmd,
            detect_path=self.detect_path,
            version_pattern=self.version_pattern,
            version_cmd=self.version_cmd,
        )


class BootstrapManifest(BaseModel):
    """Schema for ami/config/bootstrap-components.yaml."""

    model_config = ConfigDict(extra="forbid")

    groups: list[str] = Field(default_factory=list)
    components: list[ComponentManifestEntry] = Field(default_factory=list)
    requires: list[RequiresEntry] = Field(default_factory=list)


class WorkspaceCloneEntry(BaseModel):
    """One entry under workspace-clones.yaml::workspaceClones.<id>."""

    model_config = ConfigDict(extra="forbid")

    remote: str
    path: str
    mandatory: bool = False
    # Optional minimum tag - bootstrap-repos refuses to proceed if the
    # cloned working tree is older than this. Format: 'vX.Y.Z'.
    minTag: str | None = None


class WorkspaceClonesManifest(BaseModel):
    """Schema for ami/config/workspace-clones.yaml."""

    model_config = ConfigDict(extra="forbid")

    workspaceClones: dict[str, WorkspaceCloneEntry] = Field(default_factory=dict)


# --------------------------------------
# Loaders
# --------------------------------------


def _load_package_versions() -> dict[str, str]:
    """Read scripts/package.json so YAML entries can use `package_ref:` to
    pull the pinned version without duplicating it in two places."""
    if not PACKAGE_JSON.exists():
        return {}
    try:
        with open(PACKAGE_JSON) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    deps = data.get("dependencies", {})
    return {str(k): str(v) for k, v in deps.items()}


def _load_components_yaml() -> tuple[list[Component], list[str]]:
    """Load bootstrap-components.yaml. Returns (components, group_order)."""
    if not COMPONENTS_YAML.exists():
        msg = f"bootstrap component manifest missing: {COMPONENTS_YAML}"
        raise FileNotFoundError(msg)
    with open(COMPONENTS_YAML) as f:
        raw = yaml.safe_load(f) or {}

    manifest = BootstrapManifest.model_validate(raw)
    pkg_versions = _load_package_versions()
    components = [entry.to_component(pkg_versions) for entry in manifest.components]
    return components, manifest.groups


def _load_workspace_repo_components() -> list[Component]:
    """Emit one Component per workspace-clones.yaml entry.

    Mandatory entries are still rendered (locked-on by the TUI) so the user
    sees the full workspace topology. Optional entries opt-in via checkbox.
    install_component() routes WORKSPACE_REPO to
    `bootstrap-repos -include <id>` instead of a bootstrap shell script.
    """
    if not WORKSPACE_CLONES_YAML.exists():
        return []
    try:
        with open(WORKSPACE_CLONES_YAML) as f:
            raw = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return []
    manifest = WorkspaceClonesManifest.model_validate(raw)

    components: list[Component] = []
    for entry_id, entry in manifest.workspaceClones.items():
        marker = "[mandatory]" if entry.mandatory else "[optional]"
        components.append(
            Component(
                name=entry_id,
                label=entry_id,
                description=f"{marker} {entry.remote} -> {entry.path}",
                type=ComponentType.WORKSPACE_REPO,
                group=WORKSPACE_REPOS_GROUP,
                # detect_path is the path to the cloned working tree;
                # Component.get_status() treats existence as "installed".
                detect_path=entry.path,
            )
        )
    return components


_COMPONENTS, _GROUP_ORDER = _load_components_yaml()
WORKSPACE_REPOS: list[Component] = _load_workspace_repo_components()

ALL_COMPONENTS: list[Component] = [*_COMPONENTS, *WORKSPACE_REPOS]
GROUPS: list[str] = [*_GROUP_ORDER, WORKSPACE_REPOS_GROUP]


def get_components_by_group() -> list[GroupComponents]:
    """Get components organized by group, in declared display order."""
    groups_map = {g: GroupComponents(group=g, components=[]) for g in GROUPS}
    for comp in ALL_COMPONENTS:
        if comp.group in groups_map:
            groups_map[comp.group].components.append(comp)
    return list(groups_map.values())


def get_component_by_name(name: str) -> Component | None:
    """Get a component by its name."""
    for comp in ALL_COMPONENTS:
        if comp.name == name:
            return comp
    return None
