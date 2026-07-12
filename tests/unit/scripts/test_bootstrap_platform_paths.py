"""Unit tests for platform boot-path substitution in bootstrap manifests."""

from __future__ import annotations

import platform
from pathlib import Path

from workspace.scripts.bootstrap_component_defs import (
    ComponentManifestEntry,
    _load_package_versions,
    _with_platform_boot_paths,
)


class TestLoadPackageVersions:
    def test_returns_empty_when_package_json_missing(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(
            "workspace.scripts.bootstrap_component_defs.PACKAGE_JSON",
            tmp_path / "missing-package.json",
        )
        assert _load_package_versions() == {}


class TestPlatformBootPaths:
    def test_returns_unchanged_entry_without_boot_paths(self) -> None:
        entry = ComponentManifestEntry(
            name="opencode",
            label="OpenCode",
            description="AI assistant",
            group="AI Coding Assistants",
        )
        assert _with_platform_boot_paths(entry) is entry

    def test_substitutes_boot_linux_paths(self) -> None:
        entry = ComponentManifestEntry(
            name="python",
            label="Python",
            description="Python runtime",
            group="Core Dependencies",
            detect_path=".boot-linux/bin/python",
            script_path="scripts/.boot-linux/install",
            detect_cmd=[".boot-linux/bin/uv", "python", "list"],
            version_cmd=[".boot-linux/bin/python", "--version"],
        )
        result = _with_platform_boot_paths(entry)
        boot = ".boot-macos" if platform.system() == "Darwin" else ".boot-linux"
        assert result.detect_path == f"{boot}/bin/python"
        assert result.script_path == f"scripts/{boot}/install"
        assert result.detect_cmd == [f"{boot}/bin/uv", "python", "list"]
        assert result.version_cmd == [f"{boot}/bin/python", "--version"]
