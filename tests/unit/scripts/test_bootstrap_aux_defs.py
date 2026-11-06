"""Tests for the auxiliary installer registry."""

from __future__ import annotations

from pathlib import Path

import pytest

from workspace.scripts.bootstrap_aux_defs import (
    AuxDefaults,
    AuxFeature,
    AuxManifest,
    AuxSelection,
    features_by_group,
    load_defaults,
    load_registry,
    ordered_features,
    validate_defaults,
)


def _feature(
    feature_id: str, order: int, requires: list[str] | None = None
) -> AuxFeature:
    return AuxFeature(
        id=feature_id,
        label=feature_id,
        description=feature_id,
        group="Storage",
        scope="agent",
        action="storage-configure",
        order=order,
        requires=requires or [],
        args={},
    )


class TestLoadRegistry:
    def test_loads_shipped_registry(self) -> None:
        manifest = load_registry()
        ids = {feature.id for feature in manifest.features}
        assert "storage-locations" in ids
        assert "storage-migrate" in ids
        assert "diagnostics" in ids

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_registry(tmp_path / "missing.yaml")

    def test_unknown_action_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "aux.yaml"
        path.write_text(
            "groups: [Storage]\n"
            "features:\n"
            "  - id: bad\n"
            "    label: bad\n"
            "    description: bad\n"
            "    group: Storage\n"
            "    scope: agent\n"
            "    action: arbitrary-command\n"
        )
        with pytest.raises(ValueError, match="unknown auxiliary action"):
            load_registry(path)

    def test_unknown_dependency_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "aux.yaml"
        path.write_text(
            "groups: [Storage]\n"
            "features:\n"
            "  - id: bad\n"
            "    label: bad\n"
            "    description: bad\n"
            "    group: Storage\n"
            "    scope: agent\n"
            "    action: storage-configure\n"
            "    requires: [missing]\n"
        )
        with pytest.raises(ValueError, match="unknown auxiliary dependency"):
            load_registry(path)


class TestOrdering:
    def test_dependency_runs_before_dependent(self) -> None:
        manifest = AuxManifest(
            groups=["Storage"],
            features=[
                _feature("later", 10, ["earlier"]),
                _feature("earlier", 20),
            ],
        )
        ordered = ordered_features(manifest, {"later", "earlier"})
        assert [feature.id for feature in ordered] == ["earlier", "later"]

    def test_unselected_features_are_omitted(self) -> None:
        manifest = AuxManifest(
            groups=["Storage"],
            features=[_feature("one", 10), _feature("two", 20)],
        )
        ordered = ordered_features(manifest, {"two"})
        assert [feature.id for feature in ordered] == ["two"]

    def test_cycle_raises(self) -> None:
        manifest = AuxManifest(
            groups=["Storage"],
            features=[
                _feature("one", 10, ["two"]),
                _feature("two", 20, ["one"]),
            ],
        )
        with pytest.raises(ValueError, match="dependency cycle"):
            ordered_features(manifest, {"one", "two"})

    def test_groups_keep_declared_order(self) -> None:
        manifest = AuxManifest(
            groups=["Storage", "Host Services"],
            features=[
                AuxFeature(
                    id="b",
                    label="b",
                    description="b",
                    group="Host Services",
                    scope="agent",
                    action="install-diagnostics",
                ),
                AuxFeature(
                    id="a",
                    label="a",
                    description="a",
                    group="Storage",
                    scope="agent",
                    action="storage-configure",
                ),
            ],
        )
        groups = features_by_group(manifest)
        assert [group for group, _ in groups] == ["Storage", "Host Services"]


class TestDefaults:
    def test_loads_shipped_defaults(self) -> None:
        defaults = load_defaults()
        assert defaults.features["storage-locations"].enabled is True

    def test_unknown_default_feature_raises(self) -> None:
        manifest = AuxManifest(groups=["Storage"], features=[_feature("one", 10)])
        defaults = AuxDefaults(features={"missing": AuxSelection()})
        with pytest.raises(ValueError, match="unknown auxiliary feature in defaults"):
            validate_defaults(manifest, defaults)
