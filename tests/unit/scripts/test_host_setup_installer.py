"""Tests for the host configuration installer dispatch."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from workspace.scripts.bootstrap_aux import AuxResult
from workspace.scripts.bootstrap_aux_defs import (
    AuxDefaults,
    AuxFeature,
    AuxManifest,
    AuxSelection,
    Scope,
)
from workspace.scripts.host_setup_installer import (
    _allowed,
    _run,
    _select_defaults,
)


def _feature(feature_id: str, scope: Scope = "agent") -> AuxFeature:
    return AuxFeature(
        id=feature_id,
        label=feature_id,
        description=feature_id,
        group="Storage",
        scope=scope,
        action="storage-configure",
    )


class TestAllowed:
    def test_agent_scope_hides_root_features(self) -> None:
        assert _allowed(_feature("root", "root"), "agent", 1000) is False

    def test_root_scope_hides_agent_features(self) -> None:
        assert _allowed(_feature("agent", "agent"), "root", 0) is False

    def test_all_scope_allows_both_under_root(self) -> None:
        assert _allowed(_feature("root", "root"), "all", 0) is True
        assert _allowed(_feature("agent", "agent"), "all", 0) is True

    def test_all_scope_hides_root_for_agent(self) -> None:
        assert _allowed(_feature("root", "root"), "all", 1000) is False


class TestSelectDefaults:
    def test_disabled_features_are_omitted(self) -> None:
        manifest = AuxManifest(
            groups=["Storage"],
            features=[_feature("one"), _feature("two")],
        )
        defaults = AuxDefaults(
            features={
                "one": AuxSelection(enabled=True),
                "two": AuxSelection(enabled=False),
            }
        )
        selected, values = _select_defaults(manifest, defaults, "agent", 1000)
        assert [feature.id for feature in selected] == ["one"]
        assert values == {"one": {}}

    def test_unknown_feature_raises(self) -> None:
        manifest = AuxManifest(groups=["Storage"], features=[_feature("one")])
        defaults = AuxDefaults(features={"missing": AuxSelection()})
        with pytest.raises(ValueError, match="unknown auxiliary feature in defaults"):
            _select_defaults(manifest, defaults, "agent", 1000)


class TestRun:
    @patch("workspace.scripts.host_setup_installer.run_selected")
    def test_defaults_mode_runs_without_tty(
        self, run_selected, tmp_path, capsys
    ) -> None:
        defaults = tmp_path / "defaults.yaml"
        defaults.write_text("features:\n  storage-locations:\n    enabled: true\n")
        manifest = AuxManifest(
            groups=["Storage"],
            features=[_feature("storage-locations")],
        )
        run_selected.return_value = [AuxResult("storage-locations", True, "complete")]
        rc = _run(manifest, "agent", defaults)
        assert rc == 0
        run_selected.assert_called_once()
        assert "Host configuration complete" in capsys.readouterr().out

    @patch("workspace.scripts.host_setup_installer.run_selected")
    def test_failure_returns_one(self, run_selected, tmp_path) -> None:
        defaults = tmp_path / "defaults.yaml"
        defaults.write_text("features:\n  storage-locations:\n    enabled: true\n")
        manifest = AuxManifest(
            groups=["Storage"],
            features=[_feature("storage-locations")],
        )
        run_selected.return_value = [AuxResult("storage-locations", False, "failed")]
        assert _run(manifest, "agent", defaults) == 1

    def test_empty_selection_returns_zero(self, tmp_path, capsys) -> None:
        defaults = tmp_path / "defaults.yaml"
        defaults.write_text("features: {}\n")
        manifest = AuxManifest(groups=["Storage"], features=[_feature("one")])
        assert _run(manifest, "agent", defaults) == 0
        assert "No host features selected" in capsys.readouterr().out
