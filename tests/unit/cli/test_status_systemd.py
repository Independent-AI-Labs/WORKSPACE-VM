"""Unit tests for workspace.cli.status_systemd - services/details/display."""

from unittest.mock import patch

from workspace.cli.status_systemd import (
    _extract_compose_info,
    _find_container_by_name,
    _parse_systemd_details,
    _print_orphan_services,
    _process_service,
    get_systemd_services,
)
from workspace.types.status import (
    PodmanContainer,
    SystemdService,
)

_PF = (
    "--property=Id,ActiveState,SubState,FragmentPath,"
    "MainPID,ExecStart,Restart,UnitFileState"
)


def _run_cmd_matcher(outputs: dict[str, str]):
    def inner(cmd: str) -> str:
        for key, value in outputs.items():
            if key == cmd:
                return value
        return ""

    return inner


# ── _parse_systemd_details ────────────────────────────────────────────────

_SAMPLE_SHOW_OUTPUT = (
    "Id=ami-web.service\n"
    "Description=AMI Web Service\n"
    "LoadState=loaded\n"
    "ActiveState=active\n"
    "SubState=running\n"
    "MainPID=12345\n"
    "ExecMainStartTimestamp=Tue 2025-01-01 00:00:00 UTC\n"
    "MemoryCurrent=104857600\n"
    "CPUUsageNSec=5000000000\n"
    "FragmentPath=/etc/systemd/system/ami-web.service\n"
    "ExecStart=/usr/bin/podman start ami-web\n"
    "Restart=always\n"
    "UnitFileState=enabled\n"
)


def test_parse_systemd_details_parses_full_output() -> None:
    result = _parse_systemd_details(_SAMPLE_SHOW_OUTPUT)
    assert result["Id"] == "ami-web.service"
    assert result["Description"] == "AMI Web Service"
    assert result["LoadState"] == "loaded"
    assert result["ActiveState"] == "active"
    assert result["SubState"] == "running"
    assert result["MainPID"] == "12345"
    assert result["ExecMainStartTimestamp"] == "Tue 2025-01-01 00:00:00 UTC"
    assert result["MemoryCurrent"] == "104857600"
    assert result["CPUUsageNSec"] == "5000000000"
    assert result["FragmentPath"] == "/etc/systemd/system/ami-web.service"
    assert result["ExecStart"] == "/usr/bin/podman start ami-web"
    assert result["Restart"] == "always"
    assert result["UnitFileState"] == "enabled"


def test_parse_systemd_details_handles_empty_input() -> None:
    result = _parse_systemd_details("")
    assert result["Id"] == ""
    assert result["ActiveState"] == ""
    assert result["SubState"] == ""
    assert result["MainPID"] == ""
    assert result["ExecStart"] == ""
    assert result["Restart"] == ""
    assert result["UnitFileState"] == ""


def test_parse_systemd_details_handles_missing_fields() -> None:
    result = _parse_systemd_details("Id=test.service\nActiveState=active\n")
    assert result["Id"] == "test.service"
    assert result["ActiveState"] == "active"
    assert result["SubState"] == ""
    assert result["MainPID"] == ""


def test_parse_systemd_details_correct_structure_with_all_13_fields() -> None:
    result = _parse_systemd_details(_SAMPLE_SHOW_OUTPUT)
    assert isinstance(result, dict)
    assert set(result.keys()) == {
        "Id",
        "Description",
        "LoadState",
        "ActiveState",
        "SubState",
        "MainPID",
        "ExecMainStartTimestamp",
        "MemoryCurrent",
        "CPUUsageNSec",
        "FragmentPath",
        "ExecStart",
        "Restart",
        "UnitFileState",
    }


# ── _extract_compose_info ─────────────────────────────────────────────────


def test_extract_compose_info_container_name_from_podman_start() -> None:
    result = _extract_compose_info("/usr/bin/podman start -a ami-mycontainer")
    assert result.managed_container == "ami-mycontainer"
    assert result.compose_file is None
    assert result.compose_profiles == []


def test_extract_compose_info_extracts_compose_file_from_f_flag() -> None:
    result = _extract_compose_info(
        "/usr/bin/podman-compose -f /etc/compose/web.yml up -d"
    )
    assert result.compose_file == "/etc/compose/web.yml"


def test_extract_compose_info_extracts_profiles_from_profile_flags() -> None:
    result = _extract_compose_info(
        "/usr/bin/podman-compose -f /etc/compose.yml -profile prod -profile debug up -d"
    )
    assert result.compose_profiles == ["prod", "debug"]


def test_extract_compose_info_returns_none_when_no_compose_info() -> None:
    result = _extract_compose_info("/usr/bin/myapp --flag value")
    assert result.managed_container is None
    assert result.compose_file is None
    assert result.compose_profiles == []


def test_extract_compose_info_empty_profiles_when_none_found() -> None:
    result = _extract_compose_info("/usr/bin/podman-compose -f /etc/compose.yml up -d")
    assert result.compose_file == "/etc/compose.yml"
    assert result.compose_profiles == []


# ── get_systemd_services ──────────────────────────────────────────────────


def _list_units(cmd: str) -> str:
    """systemctl list-units command template (scope=user or empty)."""
    return f"systemctl {cmd}list-units --type=service --all --no-legend --no-pager"


def _show(scope: str, name: str) -> str:
    """systemctl show command template."""
    return f"systemctl {scope}show {name} {_PF}"


def _make_show_output(name: str, exec_start: str = "/usr/bin/app") -> str:
    return (
        f"Id={name}\nActiveState=active\nSubState=running\n"
        "MainPID=9999\n"
        f"ExecStart={exec_start}\nRestart=always\n"
        "UnitFileState=enabled\nFragmentPath=/etc/systemd/system/\n"
    )


def test_get_systemd_services_user_scope() -> None:
    outputs = {
        _list_units("--user "): "ami-web.service loaded active running\n",
        _show("--user ", "ami-web.service"): _make_show_output("ami-web.service"),
        _list_units(""): "",
    }
    with patch(
        "workspace.cli.status_systemd.run_cmd", side_effect=_run_cmd_matcher(outputs)
    ):
        services = get_systemd_services()
    assert len(services) == 1
    assert services[0].name == "ami-web.service"
    assert services[0].scope == "user"


def test_get_systemd_services_system_scope() -> None:
    outputs = {
        _list_units("--user "): "",
        _list_units(""): "matrix-synapse.service loaded active running\n",
        _show("", "matrix-synapse.service"): _make_show_output(
            "matrix-synapse.service"
        ),
    }
    with patch(
        "workspace.cli.status_systemd.run_cmd", side_effect=_run_cmd_matcher(outputs)
    ):
        services = get_systemd_services()
    assert len(services) == 1
    assert services[0].name == "matrix-synapse.service"
    assert services[0].scope == "system"


def test_get_systemd_services_filters_by_prefixes() -> None:
    outputs = {
        _list_units("--user "): (
            "random.service loaded active running\n"
            "ami-keep.service loaded active running\n"
            "git-daemon.service loaded active running\n"
        ),
        _show("--user ", "ami-keep.service"): _make_show_output("ami-keep.service"),
        _show("--user ", "git-daemon.service"): _make_show_output("git-daemon.service"),
        _list_units(""): "",
    }
    with patch(
        "workspace.cli.status_systemd.run_cmd", side_effect=_run_cmd_matcher(outputs)
    ):
        services = get_systemd_services()
    names = {s.name for s in services}
    assert "random.service" not in names
    assert "ami-keep.service" in names
    assert "git-daemon.service" in names


def test_get_systemd_services_deduplicates_preferring_user_scope() -> None:
    outputs = {
        _list_units("--user "): "ami-web.service loaded active running\n",
        _show("--user ", "ami-web.service"): _make_show_output(
            "ami-web.service", exec_start="/usr/bin/user-scope"
        ),
        _list_units(""): "ami-web.service loaded active running\n",
        _show("", "ami-web.service"): _make_show_output(
            "ami-web.service", exec_start="/usr/bin/system-scope"
        ),
    }
    with patch(
        "workspace.cli.status_systemd.run_cmd", side_effect=_run_cmd_matcher(outputs)
    ):
        services = get_systemd_services()
    assert len(services) == 1
    assert services[0].scope == "user"


def test_get_systemd_services_empty_when_no_services() -> None:
    with patch("workspace.cli.status_systemd.run_cmd", return_value=""):
        services = get_systemd_services()
    assert services == []


def test_get_systemd_services_handles_malformed_lines() -> None:
    outputs = {
        _list_units("--user "): ("\n   \nami-web.service loaded active running\n"),
        _show("--user ", "ami-web.service"): _make_show_output("ami-web.service"),
        _list_units(""): "",
    }
    with patch(
        "workspace.cli.status_systemd.run_cmd", side_effect=_run_cmd_matcher(outputs)
    ):
        services = get_systemd_services()
    assert len(services) == 1


# ── _find_container_by_name ───────────────────────────────────────────────


def test_find_container_by_name_finds_matching() -> None:
    containers = [
        PodmanContainer(id="1", name="web"),
        PodmanContainer(id="2", name="db"),
    ]
    result = _find_container_by_name(containers, "db")
    assert result is not None
    assert result.id == "2"


def test_find_container_by_name_returns_none_when_not_found() -> None:
    result = _find_container_by_name([PodmanContainer(id="1", name="web")], "missing")
    assert result is None


def test_find_container_by_name_handles_empty_list() -> None:
    result = _find_container_by_name([], "anything")
    assert result is None


# ── _process_service ──────────────────────────────────────────────────────


def test_process_service_unified_stack_type() -> None:
    svc = SystemdService(
        name="ami-web", compose_file="/etc/compose/web.yml", compose_profiles=["prod"]
    )
    result = _process_service(svc, [], set())
    assert result.row_type == "Unified Stack"
    assert "Profiles: prod" in result.row_details[0]


def test_process_service_container_wrapper_type() -> None:
    managed = PodmanContainer(id="c1", name="ami-nginx")
    svc = SystemdService(name="ami-nginx-svc", managed_container="ami-nginx")
    processed: set[str] = set()
    result = _process_service(svc, [managed], processed)
    assert result.row_type == "Container Wrapper"
    assert len(result.child_items) == 1
    assert result.child_items[0].name == "ami-nginx"
    assert "ami-nginx" in processed


def test_process_service_local_process_type() -> None:
    svc = SystemdService(name="ami-local", pid="9999")
    with patch(
        "workspace.cli.status_systemd.get_local_ports", return_value=["8080", "443"]
    ):
        result = _process_service(svc, [], set())
    assert result.row_type == "Local Process"
    assert result.ports_str == "8080, 443"


def test_process_service_matches_containers_by_compose_config_labels() -> None:
    svc = SystemdService(name="ami-stack", compose_file="/etc/compose/app.yml")
    child = PodmanContainer(
        id="c1",
        name="app-container",
        labels={
            "com.docker.compose.project.config_files": "/etc/compose/app.yml,/other.yml"
        },
    )
    other = PodmanContainer(id="c2", name="other-container", labels={})
    processed: set[str] = set()
    result = _process_service(svc, [child, other], processed)
    assert result.row_type == "Unified Stack"
    assert len(result.child_items) == 1
    assert result.child_items[0].name == "app-container"
    assert "app-container" in processed
    assert "other-container" not in processed


def test_process_service_local_process_gets_ports_from_pid() -> None:
    svc = SystemdService(name="ami-svc", pid="42")
    with patch("workspace.cli.status_systemd.get_local_ports", return_value=["3000"]):
        result = _process_service(svc, [], set())
    assert result.ports_str == "3000"


def test_process_service_inactive_returns_empty_display() -> None:
    svc = SystemdService(name="ami-inactive", pid="0")
    result = _process_service(svc, [], set())
    assert result.row_type == "Local Process"
    assert result.row_details == []
    assert result.child_items == []
    assert result.ports_str == ""


# ── _print_orphan_services ────────────────────────────────────────────────


def test_print_orphan_services_does_nothing_when_no_orphans() -> None:
    with patch("workspace.cli.status_systemd.print_box_line") as mock_print:
        _print_orphan_services([], {"ami-test.service"})
        mock_print.assert_not_called()


def test_print_orphan_services_prints_with_status_icons() -> None:
    orphan = SystemdService(
        name="ami-orphan.service",
        scope="user",
        active="active",
        sub="running",
        path="/tmp/testuser/.config/systemd/user/ami-orphan.service",
        enabled="enabled",
        restart="always",
    )
    with (
        patch("workspace.cli.status_systemd.print_box_line") as mock_print,
        patch("workspace.cli.status_systemd._get_restart_icon", return_value="R"),
        patch(
            "workspace.cli.status_systemd.os.path.expanduser",
            return_value="/tmp/testuser",
        ),
    ):
        _print_orphan_services([orphan], set())
    assert mock_print.call_count >= 1
    all_text = " ".join(
        str(call.args[0]) for call in mock_print.call_args_list if call.args
    )
    assert "ami-orphan.service" in all_text


def test_print_orphan_services_only_checks_ami_user_scope_services() -> None:
    non_orphan = SystemdService(
        name="matrix-synapse.service",
        scope="system",
        active="active",
        sub="running",
        path="/etc/systemd/system/matrix-synapse.service",
        enabled="enabled",
        restart="always",
    )
    with patch("workspace.cli.status_systemd.print_box_line") as mock_print:
        _print_orphan_services([non_orphan], set())
        mock_print.assert_not_called()


def test_print_orphan_services_shows_origin_path_shortened() -> None:
    orphan = SystemdService(
        name="ami-test.service",
        scope="user",
        active="inactive",
        sub="dead",
        path="/tmp/testuser/.config/systemd/user/ami-test.service",
        enabled="disabled",
        restart="no",
    )
    with (
        patch("workspace.cli.status_systemd.print_box_line") as mock_print,
        patch("workspace.cli.status_systemd._get_restart_icon", return_value="X"),
        patch(
            "workspace.cli.status_systemd.os.path.expanduser",
            return_value="/tmp/testuser",
        ),
    ):
        _print_orphan_services([orphan], set())
    origin_calls = [
        call.args[0]
        for call in mock_print.call_args_list
        if call.args and "Origin:" in str(call.args[0])
    ]
    assert len(origin_calls) >= 1
    assert "~" in str(origin_calls[0])
