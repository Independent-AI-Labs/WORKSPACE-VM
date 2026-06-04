"""Unit tests for workspace.cli.status_systemd."""

from pathlib import Path
from unittest.mock import mock_open, patch

import yaml as real_yaml

from workspace.cli.status_systemd import (
    _collect_compose_files,
    _find_workspace_root,
    _load_services_from,
    get_declared_compose_files,
    get_managed_service_names,
)

_TWO = 2

# ── _find_workspace_root ────────────────────────────────────────────────


def test_find_workspace_root_when_projects_dir_exists(tmp_path: Path) -> None:
    (tmp_path / "projects").mkdir()
    deep = tmp_path / "workspace" / "cli"
    deep.mkdir(parents=True)
    fake_file = deep / "status_systemd.py"
    fake_file.touch()

    with patch("workspace.cli.status_systemd.__file__", str(fake_file)):
        result = _find_workspace_root()

    assert result == tmp_path


def test_find_workspace_root_returns_none_when_projects_not_found(
    tmp_path: Path,
) -> None:
    deep = tmp_path / "workspace" / "cli"
    deep.mkdir(parents=True)
    fake_file = deep / "status_systemd.py"
    fake_file.touch()

    with patch("workspace.cli.status_systemd.__file__", str(fake_file)):
        result = _find_workspace_root()

    assert result is None


def test_find_workspace_root_stops_at_loop_limit(tmp_path: Path) -> None:
    parts = [f"lvl{i}" for i in range(12)]
    deep = tmp_path.joinpath(*parts)
    deep.mkdir(parents=True)
    fake_file = deep / "status_systemd.py"
    fake_file.touch()

    with patch("workspace.cli.status_systemd.__file__", str(fake_file)):
        result = _find_workspace_root()

    assert result is None


def test_find_workspace_root_walks_up_from_deep_directory(tmp_path: Path) -> None:
    (tmp_path / "projects").mkdir()
    deep = tmp_path / "a" / "b" / "c" / "d" / "e"
    deep.mkdir(parents=True)
    fake_file = deep / "status_systemd.py"
    fake_file.touch()

    with patch("workspace.cli.status_systemd.__file__", str(fake_file)):
        result = _find_workspace_root()

    assert result == tmp_path


# ── _load_services_from ──────────────────────────────────────────────────


def test_load_services_parses_valid_yaml() -> None:
    yaml_data = {
        "compose_services": {"svc-a": {}, "svc-b": {}},
        "local_services": {"local-x": {}, "local-y": {}},
    }
    managed: set[str] = set()
    m_open = mock_open(read_data=real_yaml.dump(yaml_data))

    with (
        patch("builtins.open", m_open),
        patch("workspace.cli.status_systemd.yaml.safe_load", return_value=yaml_data),
    ):
        _load_services_from(Path("/fake/services.yml"), managed)

    assert managed == {
        "svc-a.service",
        "svc-b.service",
        "local-x.service",
        "local-y.service",
    }


def test_load_services_returns_early_when_yaml_module_is_none() -> None:
    managed: set[str] = set()

    with patch("workspace.cli.status_systemd.yaml", None):
        _load_services_from(Path("/fake/services.yml"), managed)

    assert managed == set()


def test_load_services_returns_early_on_non_dict_yaml() -> None:
    managed: set[str] = set()
    m_open = mock_open(read_data="")

    with (
        patch("builtins.open", m_open),
        patch("workspace.cli.status_systemd.yaml.safe_load", return_value=[]),
    ):
        _load_services_from(Path("/fake/services.yml"), managed)

    assert managed == set()


def test_load_services_handles_os_error() -> None:
    managed: set[str] = set()
    m_open = mock_open()
    m_open.side_effect = OSError("permission denied")

    with (
        patch("builtins.open", m_open),
        patch("workspace.cli.status_systemd.sys.stderr") as mock_stderr,
    ):
        _load_services_from(Path("/fake/services.yml"), managed)

    assert managed == set()
    mock_stderr.write.assert_called()
    written = "".join(
        call.args[0] for call in mock_stderr.write.call_args_list if call.args
    )
    assert "Warning" in written
    assert "permission denied" in written


def test_load_services_handles_yaml_error() -> None:
    managed: set[str] = set()
    m_open = mock_open(read_data="bad: [unclosed")

    with (
        patch("builtins.open", m_open),
        patch(
            "workspace.cli.status_systemd.yaml.safe_load",
            side_effect=real_yaml.YAMLError("parse error"),
        ),
        patch("workspace.cli.status_systemd.sys.stderr") as mock_stderr,
    ):
        _load_services_from(Path("/fake/services.yml"), managed)

    assert managed == set()
    mock_stderr.write.assert_called()
    written = "".join(
        call.args[0] for call in mock_stderr.write.call_args_list if call.args
    )
    assert "Warning" in written
    assert "parse error" in written


def test_load_services_does_not_add_duplicates() -> None:
    yaml_data = {
        "compose_services": {"svc-a": {}},
        "local_services": {"svc-a": {}},
    }
    managed: set[str] = set()
    m_open = mock_open(read_data=real_yaml.dump(yaml_data))

    with (
        patch("builtins.open", m_open),
        patch("workspace.cli.status_systemd.yaml.safe_load", return_value=yaml_data),
    ):
        _load_services_from(Path("/fake/services.yml"), managed)

    assert managed == {"svc-a.service"}


# ── get_managed_service_names ────────────────────────────────────────────


def test_get_managed_service_names_from_root_and_projects(tmp_path: Path) -> None:
    (tmp_path / "projects").mkdir()
    root = tmp_path

    ansible_dir = root / "ansible" / "inventory" / "host_vars"
    ansible_dir.mkdir(parents=True)
    (ansible_dir / "localhost.yml").touch()

    proj_dir = root / "projects" / "myproj" / "res" / "ansible"
    proj_dir.mkdir(parents=True)
    (proj_dir / "services.yml").touch()

    def load_side_effect(path: Path, managed: set[str]) -> None:
        p_str = str(path)
        if "localhost.yml" in p_str:
            managed.add("root-svc.service")
        elif "myproj" in p_str:
            managed.add("proj-svc.service")

    with (
        patch("workspace.cli.status_systemd._find_workspace_root", return_value=root),
        patch(
            "workspace.cli.status_systemd._load_services_from",
            side_effect=load_side_effect,
        ),
    ):
        result = get_managed_service_names()

    assert "root-svc.service" in result
    assert "proj-svc.service" in result


def test_get_managed_service_names_empty_when_root_not_found() -> None:
    with patch("workspace.cli.status_systemd._find_workspace_root", return_value=None):
        result = get_managed_service_names()
    assert result == set()


def test_get_managed_service_names_scans_all_project_dirs(tmp_path: Path) -> None:
    (tmp_path / "projects").mkdir()
    root = tmp_path

    ansible_dir = root / "ansible" / "inventory" / "host_vars"
    ansible_dir.mkdir(parents=True)
    (ansible_dir / "localhost.yml").touch()

    for name in ("a", "b", "c"):
        proj_dir = root / "projects" / name / "res" / "ansible"
        proj_dir.mkdir(parents=True)
        (proj_dir / "services.yml").touch()

    def load_side_effect(path: Path, managed: set[str]) -> None:
        p_str = str(path)
        if "localhost.yml" in p_str:
            managed.add("root-svc.service")
        elif f"{'a'}/res/ansible" in p_str:
            managed.add("a-local.service")
        elif f"{'b'}/res/ansible" in p_str:
            managed.add("b-svc.service")
        elif f"{'c'}/res/ansible" in p_str:
            managed.add("c-svc.service")

    with (
        patch("workspace.cli.status_systemd._find_workspace_root", return_value=root),
        patch(
            "workspace.cli.status_systemd._load_services_from",
            side_effect=load_side_effect,
        ),
    ):
        result = get_managed_service_names()

    assert "root-svc.service" in result
    assert "a-local.service" in result
    assert "b-svc.service" in result
    assert "c-svc.service" in result


# ── _collect_compose_files ────────────────────────────────────────────────


def test_collect_compose_files_from_yaml() -> None:
    yaml_data = {
        "compose_services": {
            "web": {"compose_file": "docker/web.yml"},
            "db": {"compose_file": "docker/db.yml"},
        }
    }
    paths: set[str] = set()
    base_dir = Path("/base")
    m_open = mock_open(read_data=real_yaml.dump(yaml_data))

    with (
        patch("builtins.open", m_open),
        patch("workspace.cli.status_systemd.yaml.safe_load", return_value=yaml_data),
    ):
        _collect_compose_files(Path("/base/services.yml"), base_dir, paths)

    assert len(paths) == _TWO
    assert any("web.yml" in p for p in paths)
    assert any("db.yml" in p for p in paths)


def test_collect_compose_files_returns_early_when_yaml_none() -> None:
    paths: set[str] = set()

    with patch("workspace.cli.status_systemd.yaml", None):
        _collect_compose_files(Path("/base/s.yml"), Path("/base"), paths)

    assert paths == set()


def test_collect_compose_files_returns_early_on_non_dict() -> None:
    paths: set[str] = set()
    m_open = mock_open(read_data="hello")

    with (
        patch("builtins.open", m_open),
        patch("workspace.cli.status_systemd.yaml.safe_load", return_value="string"),
    ):
        _collect_compose_files(Path("/base/s.yml"), Path("/base"), paths)

    assert paths == set()


def test_collect_compose_files_handles_os_error() -> None:
    paths: set[str] = set()
    m_open = mock_open()
    m_open.side_effect = OSError("gone")

    with patch("builtins.open", m_open):
        _collect_compose_files(Path("/base/s.yml"), Path("/base"), paths)

    assert paths == set()


def test_collect_compose_files_handles_yaml_error() -> None:
    paths: set[str] = set()
    m_open = mock_open(read_data=":")

    with (
        patch("builtins.open", m_open),
        patch(
            "workspace.cli.status_systemd.yaml.safe_load",
            side_effect=real_yaml.YAMLError("bad yaml"),
        ),
    ):
        _collect_compose_files(Path("/base/s.yml"), Path("/base"), paths)

    assert paths == set()


def test_collect_compose_files_resolves_relative_paths() -> None:
    yaml_data = {
        "compose_services": {
            "web": {"compose_file": "relative/path/compose.yml"},
        }
    }
    paths: set[str] = set()
    base_dir = Path("/abs/base")
    m_open = mock_open(read_data=real_yaml.dump(yaml_data))

    with (
        patch("builtins.open", m_open),
        patch("workspace.cli.status_systemd.yaml.safe_load", return_value=yaml_data),
    ):
        _collect_compose_files(Path("/abs/base/services.yml"), base_dir, paths)

    resolved = Path("/abs/base/relative/path/compose.yml").resolve()
    assert str(resolved) in paths


# ── get_declared_compose_files ────────────────────────────────────────────


def test_get_declared_compose_files_from_root_and_projects(tmp_path: Path) -> None:
    root = tmp_path

    ansible_dir = root / "ansible" / "inventory" / "host_vars"
    ansible_dir.mkdir(parents=True)
    root_inv = ansible_dir / "localhost.yml"
    root_inv.touch()

    proj_dir = root / "projects" / "p1" / "res" / "ansible"
    proj_dir.mkdir(parents=True)
    (proj_dir / "services.yml").touch()

    def safe_load_side_effect(stream):
        path = getattr(stream, "name", "")
        if "localhost.yml" in str(path):
            return {"compose_services": {"a": {"compose_file": "root.yml"}}}
        return {"compose_services": {"b": {"compose_file": "proj.yml"}}}

    with (
        patch("workspace.cli.status_systemd._find_workspace_root", return_value=root),
        patch(
            "workspace.cli.status_systemd.yaml.safe_load",
            side_effect=safe_load_side_effect,
        ),
    ):
        result = get_declared_compose_files()

    assert len(result) >= _TWO
    assert any("root.yml" in p for p in result)
    assert any("proj.yml" in p for p in result)


def test_get_declared_compose_files_empty_when_root_not_found() -> None:
    with patch("workspace.cli.status_systemd._find_workspace_root", return_value=None):
        result = get_declared_compose_files()
    assert result == set()


def test_get_declared_compose_files_skips_nonexistent_services_yml(
    tmp_path: Path,
) -> None:
    root = tmp_path
    ansible_dir = root / "ansible" / "inventory" / "host_vars"
    ansible_dir.mkdir(parents=True)
    (ansible_dir / "localhost.yml").touch()

    proj_dir = root / "projects" / "no_yaml" / "res" / "ansible"
    proj_dir.mkdir(parents=True)

    def safe_load_side_effect(stream):
        return {"compose_services": {"x": {"compose_file": "main.yml"}}}

    with (
        patch("workspace.cli.status_systemd._find_workspace_root", return_value=root),
        patch(
            "workspace.cli.status_systemd.yaml.safe_load",
            side_effect=safe_load_side_effect,
        ),
    ):
        result = get_declared_compose_files()

    assert any("main.yml" in p for p in result)
