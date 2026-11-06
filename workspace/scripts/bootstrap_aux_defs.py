"""Auxiliary installer feature schemas and loaders.

The registry lives at workspace/config/install-aux.yaml. Non-interactive
selections live at workspace/config/install-aux-defaults.yaml. See
docs/specifications/SPEC-INSTALLER.md.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from workspace.config_utils import PROJECT_ROOT

AUX_YAML = PROJECT_ROOT / "workspace" / "config" / "install-aux.yaml"
AUX_DEFAULTS_YAML = PROJECT_ROOT / "workspace" / "config" / "install-aux-defaults.yaml"

Scope = Literal["agent", "root"]

KNOWN_ACTIONS = frozenset(
    {
        "storage-configure",
        "storage-mount-backup",
        "storage-persist-backup",
        "storage-provision-fast",
        "storage-migrate",
        "install-diagnostics",
        "install-agentci",
        "dataops-profiles",
    }
)


class AuxArg(BaseModel):
    """One named argument for an auxiliary feature."""

    model_config = ConfigDict(extra="forbid")

    default: str
    description: str = ""


class AuxFeature(BaseModel):
    """One auxiliary feature entry."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    description: str
    group: str
    scope: Scope
    action: str
    order: int = 100
    enabled_by_default: bool = False
    detect_path: str | None = None
    detect_mount: str | None = None
    detect_cmd: list[str] | None = None
    args: dict[str, AuxArg] = Field(default_factory=dict)
    requires: list[str] = Field(default_factory=list)


class AuxManifest(BaseModel):
    """Schema for workspace/config/install-aux.yaml."""

    model_config = ConfigDict(extra="forbid")

    groups: list[str] = Field(default_factory=list)
    features: list[AuxFeature] = Field(default_factory=list)


class AuxSelection(BaseModel):
    """One feature selection from the defaults file."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    args: dict[str, str] = Field(default_factory=dict)


class AuxDefaults(BaseModel):
    """Schema for workspace/config/install-aux-defaults.yaml."""

    model_config = ConfigDict(extra="forbid")

    features: dict[str, AuxSelection] = Field(default_factory=dict)


def load_registry(path: Path | None = None) -> AuxManifest:
    """Load and validate the auxiliary feature registry."""
    target = path or AUX_YAML
    if not target.is_file():
        msg = f"auxiliary registry missing: {target}"
        raise FileNotFoundError(msg)
    with open(target, encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    manifest = AuxManifest.model_validate(raw)
    _validate_registry(manifest)
    return manifest


def load_defaults(path: Path | None = None) -> AuxDefaults:
    """Load and validate non-interactive selections."""
    target = path or AUX_DEFAULTS_YAML
    if not target.is_file():
        msg = f"auxiliary defaults missing: {target}"
        raise FileNotFoundError(msg)
    with open(target, encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    return AuxDefaults.model_validate(raw)


def _validate_registry(manifest: AuxManifest) -> None:
    seen: set[str] = set()
    for feature in manifest.features:
        if feature.id in seen:
            msg = f"duplicate auxiliary feature id: {feature.id}"
            raise ValueError(msg)
        seen.add(feature.id)
        if feature.action not in KNOWN_ACTIONS:
            msg = f"unknown auxiliary action '{feature.action}' for {feature.id}"
            raise ValueError(msg)
    for feature in manifest.features:
        for dep in feature.requires:
            if dep not in seen:
                msg = f"unknown auxiliary dependency '{dep}' for {feature.id}"
                raise ValueError(msg)


def validate_defaults(manifest: AuxManifest, defaults: AuxDefaults) -> None:
    """Reject defaults entries that name features outside the registry."""
    known = {feature.id for feature in manifest.features}
    for feature_id in defaults.features:
        if feature_id not in known:
            msg = f"unknown auxiliary feature in defaults: {feature_id}"
            raise ValueError(msg)


def features_by_group(manifest: AuxManifest) -> list[tuple[str, list[AuxFeature]]]:
    """Return groups in declared order, then any undeclared groups."""
    order = list(manifest.groups)
    grouped: dict[str, list[AuxFeature]] = {group: [] for group in order}
    for feature in manifest.features:
        grouped.setdefault(feature.group, []).append(feature)
        if feature.group not in order:
            order.append(feature.group)
    return [(group, grouped[group]) for group in order if grouped[group]]


def ordered_features(manifest: AuxManifest, selected_ids: set[str]) -> list[AuxFeature]:
    """Return selected features in dependency-safe execution order."""
    by_id = {feature.id: feature for feature in manifest.features}
    result: list[AuxFeature] = []
    visiting: set[str] = set()

    def visit(feature: AuxFeature) -> None:
        if feature.id in visiting:
            msg = f"auxiliary dependency cycle at {feature.id}"
            raise ValueError(msg)
        if any(item.id == feature.id for item in result):
            return
        visiting.add(feature.id)
        for dep in feature.requires:
            if dep in selected_ids:
                visit(by_id[dep])
        visiting.remove(feature.id)
        result.append(feature)

    for feature in sorted(by_id.values(), key=lambda item: (item.order, item.id)):
        if feature.id in selected_ids:
            visit(feature)
    return result
