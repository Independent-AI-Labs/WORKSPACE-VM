"""Unit tests for _load_workspace_repo_components helper.

Exercises the workspaceClones YAML reader: missing file, malformed manifest,
mandatory/optional marker assignment, and detect_path mapping.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from ami.scripts import bootstrap_component_defs as defs


class TestLoadWorkspaceRepoComponents:
    """Tests for _load_workspace_repo_components helper."""

    def test_returns_empty_when_file_absent(self, tmp_path: Path) -> None:
        with patch.object(defs, "WORKSPACE_CLONES_YAML", tmp_path / "missing.yaml"):
            assert defs._load_workspace_repo_components() == []

    def test_returns_empty_on_yaml_error(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text("workspaceClones: : :\n")  # invalid YAML
        with patch.object(defs, "WORKSPACE_CLONES_YAML", bad):
            assert defs._load_workspace_repo_components() == []

    def test_invalid_entry_raises_validation_error(self, tmp_path: Path) -> None:
        """A non-dict entry under workspaceClones is a manifest bug — fail
        loudly so the user can fix their YAML rather than silently dropping
        a repo from the workspace topology."""
        f = tmp_path / "clones.yaml"
        f.write_text("workspaceClones:\n  garbage: 'not-a-dict'\n")
        with (
            patch.object(defs, "WORKSPACE_CLONES_YAML", f),
            pytest.raises(ValidationError),
        ):
            defs._load_workspace_repo_components()

    def test_marks_mandatory_vs_optional(self, tmp_path: Path) -> None:
        f = tmp_path / "clones.yaml"
        f.write_text(
            "workspaceClones:\n"
            "  hard:\n"
            "    remote: 'git@example.com:hard.git'\n"
            "    path: 'projects/HARD'\n"
            "    mandatory: true\n"
            "  soft:\n"
            "    remote: 'git@example.com:soft.git'\n"
            "    path: 'projects/SOFT'\n"
            "    mandatory: false\n"
        )
        with patch.object(defs, "WORKSPACE_CLONES_YAML", f):
            comps = defs._load_workspace_repo_components()
        by_name = {c.name: c for c in comps}
        assert by_name["hard"].description.startswith("[mandatory]")
        assert by_name["soft"].description.startswith("[optional]")
        # detect_path mirrors the YAML path (TUI uses it for installed-state).
        assert by_name["hard"].detect_path == "projects/HARD"
        assert by_name["soft"].detect_path == "projects/SOFT"
