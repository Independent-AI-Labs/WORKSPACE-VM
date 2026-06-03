"""Unit tests for ami/scripts/check_workspace_repos_aligned.py.

Covers the alignment invariant between .moon/workspace.yml::projects and
ami/config/workspace-clones.yaml::workspaceClones.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from workspace.scripts import check_workspace_repos_aligned as mod

MOON_OK = """\
projects:
  ami-agents: '.'
  ami-ci: 'projects/AMI-CI'
  ami-dataops: 'projects/AMI-DATAOPS'
"""

CLONES_OK = """\
workspaceClones:
  ami-ci:
    remote: 'git@example.com:ami-ci.git'
    path: 'projects/AMI-CI'
    mandatory: true
  ami-dataops:
    remote: 'git@example.com:ami-dataops.git'
    path: 'projects/AMI-DATAOPS'
    mandatory: true
"""


def _make_workspace(tmp_path: Path, moon_yaml: str, clones_yaml: str) -> Path:
    (tmp_path / ".moon").mkdir()
    (tmp_path / ".moon" / "workspace.yml").write_text(moon_yaml)
    (tmp_path / "ami" / "config").mkdir(parents=True)
    (tmp_path / "ami" / "config" / "workspace-clones.yaml").write_text(clones_yaml)
    return tmp_path


class TestAlignmentCheck:
    def test_ok_when_aligned(self, tmp_path, capsys) -> None:
        root = _make_workspace(tmp_path, MOON_OK, CLONES_OK)
        with patch.object(mod, "_find_workspace_root", return_value=root):
            assert mod.main() == mod.EXIT_OK
        assert "aligned" in capsys.readouterr().out

    def test_drift_only_in_moon(self, tmp_path, capsys) -> None:
        moon = MOON_OK + "  ami-stray: 'projects/STRAY'\n"
        root = _make_workspace(tmp_path, moon, CLONES_OK)
        with patch.object(mod, "_find_workspace_root", return_value=root):
            assert mod.main() == mod.EXIT_DRIFT
        err = capsys.readouterr().err
        assert "missing from workspace-clones.yaml" in err
        assert "ami-stray" in err

    def test_drift_only_in_clones(self, tmp_path, capsys) -> None:
        clones = CLONES_OK + (
            "  ami-extra:\n"
            "    remote: 'git@example.com:extra.git'\n"
            "    path: 'projects/EXTRA'\n"
            "    mandatory: false\n"
        )
        root = _make_workspace(tmp_path, MOON_OK, clones)
        with patch.object(mod, "_find_workspace_root", return_value=root):
            assert mod.main() == mod.EXIT_DRIFT
        err = capsys.readouterr().err
        assert "missing from .moon/workspace.yml" in err
        assert "ami-extra" in err

    def test_drift_path_mismatch(self, tmp_path, capsys) -> None:
        moon = (
            "projects:\n"
            "  ami-agents: '.'\n"
            "  ami-ci: 'projects/AMI-CI'\n"
            "  ami-dataops: 'projects/WRONG'\n"
        )
        root = _make_workspace(tmp_path, moon, CLONES_OK)
        with patch.object(mod, "_find_workspace_root", return_value=root):
            assert mod.main() == mod.EXIT_DRIFT
        err = capsys.readouterr().err
        assert "path mismatch" in err
        assert "ami-dataops" in err

    def test_infra_error_when_root_unfindable(self, tmp_path, capsys) -> None:
        with patch.object(mod, "_find_workspace_root", return_value=None):
            assert mod.main() == mod.EXIT_INFRA
        assert "cannot find workspace root" in capsys.readouterr().err

    def test_infra_error_on_invalid_yaml(self, tmp_path, capsys) -> None:
        bad_clones = "workspaceClones:\n  ami-ci: : :\n"
        root = _make_workspace(tmp_path, MOON_OK, bad_clones)
        with patch.object(mod, "_find_workspace_root", return_value=root):
            assert mod.main() == mod.EXIT_INFRA
        assert "failed to load registries" in capsys.readouterr().err

    def test_finds_workspace_root_walks_upwards(self, tmp_path: Path) -> None:
        _make_workspace(tmp_path, MOON_OK, CLONES_OK)
        nested = tmp_path / "a" / "b" / "c"
        nested.mkdir(parents=True)
        assert mod._find_workspace_root(nested) == tmp_path.resolve()

    def test_finds_workspace_root_returns_none_when_absent(
        self, tmp_path: Path
    ) -> None:
        assert mod._find_workspace_root(tmp_path) is None
