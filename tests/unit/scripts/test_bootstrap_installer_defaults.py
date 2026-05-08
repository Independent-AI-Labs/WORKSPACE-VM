"""Unit tests for bootstrap_installer defaults-mode (CI) entry path.

Covers `_load_defaults`, `_run_from_defaults`, and the `main()` argv
dispatch into defaults mode. These exercise the non-interactive path
that `make install-ci` takes.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from ami.scripts.bootstrap_components import Component, ComponentType
from ami.scripts.bootstrap_installer import (
    InstallationResult,
    _load_defaults,
    _run_from_defaults,
    main,
)


class TestLoadDefaults:
    """Tests for _load_defaults."""

    def test_loads_components_list(self, tmp_path: Path) -> None:
        f = tmp_path / "defaults.yaml"
        f.write_text("components:\n  - uv\n  - python\n")
        assert _load_defaults(f) == ["uv", "python"]

    def test_missing_file_exits(self, tmp_path: Path) -> None:
        f = tmp_path / "nope.yaml"
        with pytest.raises(SystemExit) as exc:
            _load_defaults(f)
        assert exc.value.code == 1

    def test_missing_components_key_exits(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.yaml"
        f.write_text("foo: bar\n")
        with pytest.raises(SystemExit) as exc:
            _load_defaults(f)
        assert exc.value.code == 1

    def test_empty_file_exits(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.yaml"
        f.write_text("")
        with pytest.raises(SystemExit) as exc:
            _load_defaults(f)
        assert exc.value.code == 1


class TestRunFromDefaults:
    """Tests for _run_from_defaults."""

    @patch("ami.scripts.bootstrap_installer._run_installation")
    def test_runs_installation_with_resolved_components(
        self, mock_run, tmp_path: Path
    ) -> None:
        f = tmp_path / "defaults.yaml"
        f.write_text("components:\n  - uv\n")
        mock_run.return_value = InstallationResult(success_count=1, failed_labels=[])

        rc = _run_from_defaults(f)

        assert rc == 0
        # uv must reach _run_installation as a Component instance.
        components = mock_run.call_args[0][0]
        assert any(c.name == "uv" for c in components)

    @patch("ami.scripts.bootstrap_installer._run_installation")
    def test_warns_on_unknown_component(self, mock_run, tmp_path: Path, capsys) -> None:
        f = tmp_path / "defaults.yaml"
        f.write_text("components:\n  - uv\n  - zzz_does_not_exist_zzz\n")
        mock_run.return_value = InstallationResult(success_count=1, failed_labels=[])

        rc = _run_from_defaults(f)

        out = capsys.readouterr().out
        assert "Unknown component 'zzz_does_not_exist_zzz'" in out
        assert rc == 0

    @patch("ami.scripts.bootstrap_installer._run_installation")
    def test_no_valid_components_short_circuits(self, mock_run, tmp_path: Path) -> None:
        # An entry that resolves to nothing; combined with no mandatory repos
        # being defined in the patched WORKSPACE_REPOS, _run_installation
        # must NOT be invoked.
        f = tmp_path / "defaults.yaml"
        f.write_text("components:\n  - zzz_does_not_exist_zzz\n")
        with patch(
            "ami.scripts.bootstrap_installer._bootstrap_defs.WORKSPACE_REPOS", []
        ):
            rc = _run_from_defaults(f)

        assert rc == 0
        mock_run.assert_not_called()

    @patch("ami.scripts.bootstrap_installer._run_installation")
    def test_appends_mandatory_workspace_repos(self, mock_run, tmp_path: Path) -> None:
        f = tmp_path / "defaults.yaml"
        f.write_text("components:\n  - uv\n")
        mock_run.return_value = InstallationResult(success_count=1, failed_labels=[])

        # Simulate one mandatory + one optional repo.
        fake_mandatory = Component(
            name="ami-fake",
            label="ami-fake",
            description="[mandatory] git@example.com:fake.git -> projects/AMI-FAKE",
            type=ComponentType.WORKSPACE_REPO,
            group="Workspace Repositories",
            detect_path="projects/AMI-FAKE",
        )
        fake_optional = Component(
            name="ami-opt",
            label="ami-opt",
            description="[optional] git@example.com:opt.git -> projects/AMI-OPT",
            type=ComponentType.WORKSPACE_REPO,
            group="Workspace Repositories",
            detect_path="projects/AMI-OPT",
        )

        uv_component = Component(
            name="uv",
            label="uv",
            description="x",
            type=ComponentType.SCRIPT,
            group="Core Dependencies",
            script="bootstrap_uv.sh",
        )
        resolver_table = {
            "uv": uv_component,
            "ami-fake": fake_mandatory,
            "ami-opt": fake_optional,
        }

        def _resolve(name: str) -> Component | None:
            return resolver_table.get(name)

        # get_component_by_name() walks ALL_COMPONENTS, so register the fakes
        # there too — patch the module-level list seen by the resolver.
        with (
            patch(
                "ami.scripts.bootstrap_installer._bootstrap_defs.WORKSPACE_REPOS",
                [fake_mandatory, fake_optional],
            ),
            patch(
                "ami.scripts.bootstrap_installer._bootstrap_defs.get_component_by_name",
                side_effect=_resolve,
            ),
        ):
            rc = _run_from_defaults(f)

        assert rc == 0
        components = mock_run.call_args[0][0]
        names = {c.name for c in components}
        # Mandatory must be auto-included; optional must NOT be.
        assert "ami-fake" in names
        assert "ami-opt" not in names
        assert "uv" in names


class TestMainEntryDispatch:
    """Tests for main() argv dispatch."""

    @patch("ami.scripts.bootstrap_installer._run_from_defaults", return_value=0)
    def test_main_routes_to_defaults_mode(
        self, mock_defaults, monkeypatch, tmp_path: Path
    ) -> None:
        f = tmp_path / "defaults.yaml"
        f.write_text("components: [uv]\n")
        monkeypatch.setattr("sys.argv", ["bootstrap_installer", "--defaults", str(f)])

        rc = main()

        assert rc == 0
        mock_defaults.assert_called_once_with(f)

    def test_main_rejects_non_tty_without_defaults(self, monkeypatch) -> None:
        monkeypatch.setattr("sys.argv", ["bootstrap_installer"])
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        rc = main()
        assert rc == 1
