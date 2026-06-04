"""Integration smoke tests for workspace core modules."""

from pathlib import Path

from workspace.cli.legend import (
    WIDE_EMOJI,
    Legend,
    LegendGroup,
    LegendItem,
    get_visual_width,
    pad_center,
)
from workspace.cli.status_containers import (
    _find_size_by_name,
    _find_stats_by_name,
    _parse_port_mapping,
    get_container_sizes,
    get_container_stats,
    get_container_volumes,
    get_podman_containers,
    get_system_docker_containers,
    get_system_docker_stats,
)
from workspace.cli.status_systemd import (
    SYSTEMD_PREFIXES,
    _extract_compose_info,
    _find_container_by_name,
    _find_workspace_root,
    _parse_systemd_details,
    _process_service,
    get_declared_compose_files,
    get_managed_service_names,
    get_systemd_services,
)
from workspace.cli.status_utils import (
    _format_port_string,
    _get_container_status_display,
    _get_restart_icon,
    format_bytes,
    format_ports,
    parse_size_to_bytes,
    print_box_line,
    run_cmd,
)
from workspace.cli.storage import _print_container_sizes, _print_root_disk, _remove_path
from workspace.config_utils import get_config_path, get_project_root
from workspace.types.config import AgentConfig
from workspace.types.events import StreamEvent, StreamEventType
from workspace.types.results import LegendRender
from workspace.types.status import PodmanContainer, PortMapping, SystemdService
from workspace.utils.banner import (
    _find_pyproject,
    generate_banner_lines,
    get_project_version,
)
from workspace.utils.uuid_utils import uuid7

_P100 = 100
_P1024 = 1024
_P1536 = 1536
_P1048576 = 1048576
_P1572864 = 1572864
_P1073741824 = 1073741824
_P1099511627776 = 1099511627776
_P1125899906842624 = 1125899906842624
_P2199023255552 = 2199023255552
_P12345 = 12345
_W5 = 5
_W2 = 2
_DEFAULT_TIMEOUT = 180
_UUID_LEN = 36
_PORT_8080 = 8080
_PORT_80 = 80
_PORT_3000 = 3000


def test_get_project_root_returns_path() -> None:
    root = get_project_root()
    assert isinstance(root, Path)
    assert root.is_dir()


def test_get_config_path_returns_valid_path() -> None:
    result = get_config_path("ruff.toml")
    assert str(result).endswith("/res/config/ruff.toml")


def test_format_bytes_all_branches() -> None:
    assert format_bytes(0) == "0B"
    assert format_bytes(-1) == "0B"
    assert format_bytes(500) == "500B"
    assert format_bytes(_P1024) == "1KB"
    assert format_bytes(_P1536) == "1KB"
    assert format_bytes(_P1048576) == "1.0MB"
    assert format_bytes(_P1073741824) == "1.0GB"
    assert format_bytes(_P1099511627776) == "1.0TB"
    assert format_bytes(_P1125899906842624) == "1.0PB"


def test_parse_size_to_bytes_all_branches() -> None:
    assert parse_size_to_bytes("") == 0
    assert parse_size_to_bytes("-") == 0
    assert parse_size_to_bytes("100B") == _P100
    assert parse_size_to_bytes("1K") == _P1024
    assert parse_size_to_bytes("1.5M") == _P1572864
    assert parse_size_to_bytes("1G") == _P1073741824
    assert parse_size_to_bytes("2T") == _P2199023255552
    assert parse_size_to_bytes("12345") == _P12345
    assert parse_size_to_bytes("invalid") == 0


def test_format_ports_all_branches() -> None:
    assert format_ports([]) == ""
    pm_host = PortMapping(host_port=_PORT_8080, container_port=_PORT_80)
    result1 = format_ports([pm_host])
    assert "8080->80" in result1
    pm_cont = PortMapping(container_port=_PORT_3000, protocol="udp")
    result2 = format_ports([pm_cont])
    assert "3000/udp" in result2


def test_format_port_string_both() -> None:
    assert (
        _format_port_string(PortMapping(host_port=_PORT_80, container_port=_PORT_80))
        == "80->80/tcp"
    )
    assert (
        _format_port_string(PortMapping(container_port=443, protocol="udp"))
        == "443/udp"
    )


def test_run_cmd_integration() -> None:
    result = run_cmd("echo hello")
    assert isinstance(result, str)


def test_print_box_line(capsys) -> None:
    print_box_line("hello", width=80)
    captured = capsys.readouterr()
    assert "hello" in captured.out


def test_print_box_line_truncated(capsys) -> None:
    print_box_line("x" * 200, width=80)
    captured = capsys.readouterr()
    assert "x" in captured.out


def test_print_box_line_bold(capsys) -> None:
    print_box_line("bold text", width=80, bold=True)
    captured = capsys.readouterr()
    assert "bold text" in captured.out


def test_legend_render_dim() -> None:
    legend = Legend(
        groups=[LegendGroup(items=[LegendItem(icon="X", label="test")])],
        dim=True,
    )
    result = legend.render(width=80)
    assert isinstance(result, LegendRender)
    assert "test" in result.labels_line
    assert "\033[2m" in result.icons_line


def test_legend_render_no_dim() -> None:
    legend = Legend(
        groups=[LegendGroup(items=[LegendItem(icon="X", label="test")])],
        dim=False,
    )
    result = legend.render(width=80)
    assert "\033[2m" not in result.icons_line


def test_legend_multi_group_separator() -> None:
    legend = Legend(
        groups=[
            LegendGroup(items=[LegendItem(icon="A", label="aa")]),
            LegendGroup(items=[LegendItem(icon="B", label="bb")]),
        ],
        separator="|",
        dim=False,
    )
    result = legend.render(width=80)
    assert "aa" in result.labels_line
    assert "bb" in result.labels_line


def test_legend_empty_and_narrow() -> None:
    empty_result = Legend(groups=[], dim=False).render(width=80)
    assert isinstance(empty_result, LegendRender)

    narrow_result = Legend(
        groups=[LegendGroup(items=[LegendItem(icon="X", label="t")])],
        dim=False,
    ).render(width=10)
    assert isinstance(narrow_result, LegendRender)


def test_get_visual_width_full() -> None:
    assert get_visual_width("hello") == _W5
    assert get_visual_width("") == 0
    assert get_visual_width("\033[32mok\033[0m") == _W2
    assert get_visual_width("あ") in (2, 1)


def test_pad_center_simple() -> None:
    result = pad_center("hi", 10)
    assert "hi" in result


def test_wide_emoji_set() -> None:
    assert "🟢" in WIDE_EMOJI
    assert "🔴" in WIDE_EMOJI
    assert "🐳" in WIDE_EMOJI


def test_stream_event_factories() -> None:
    chunk = StreamEvent.chunk("data")
    assert chunk.type == StreamEventType.CHUNK
    assert chunk.data == "data"

    err = StreamEvent.error("boom")
    assert err.type == StreamEventType.ERROR
    assert err.data == "boom"


def test_agent_config_defaults() -> None:
    config = AgentConfig(model="gpt-4", provider=object())
    assert config.model == "gpt-4"
    assert config.enable_hooks is True
    assert config.enable_streaming is False
    assert config.capture_content is False
    assert config.timeout == _DEFAULT_TIMEOUT
    assert config.session_id is None


def test_restart_icon_all_values() -> None:
    for val in (
        "always",
        "on-failure",
        "on-abnormal",
        "on-abort",
        "on-watchdog",
        "no",
        "never",
        "",
    ):
        icon = _get_restart_icon(val)
        assert isinstance(icon, str)
        assert len(icon) > 0


def test_container_status_all_states() -> None:
    for state in ("running", "exited", "paused", "unknown"):
        display = _get_container_status_display(state)
        assert display.icon != ""


def test_systemd_service_full() -> None:
    s = SystemdService(
        name="test-svc",
        scope="user",
        active="active",
        sub="running",
        restart="always",
        enabled="enabled",
        pid="12345",
        compose_file="/etc/compose.yml",
        compose_profiles=["prod"],
    )
    assert s.active == "active"
    assert s.restart == "always"
    assert s.pid == "12345"
    assert s.compose_profiles == ["prod"]


def test_podman_container_full() -> None:
    c = PodmanContainer(
        id="abc",
        name="web",
        state="running",
        status="Up 5 minutes",
        image="nginx:1.27",
        ports=[PortMapping(host_port=80, container_port=80)],
    )
    assert c.state == "running"
    assert c.image == "nginx:1.27"
    assert len(c.ports) == 1


def test_get_project_version() -> None:
    version = get_project_version()
    assert isinstance(version, str)
    assert len(version) > 0


def test_generate_banner_lines() -> None:
    lines = generate_banner_lines(font="small")
    assert isinstance(lines, list)


def test_find_pyproject() -> None:
    result = _find_pyproject(Path(__file__).resolve())
    assert result.name == "pyproject.toml"


def test_uuid_v7() -> None:
    uid = uuid7()
    assert isinstance(uid, str)
    assert len(uid) == _UUID_LEN


def test_parse_port_mapping() -> None:
    result = _parse_port_mapping(
        {"hostPort": _PORT_8080, "containerPort": _PORT_80, "protocol": "tcp"}
    )
    assert result.host_port == _PORT_8080
    assert result.container_port == _PORT_80
    assert result.protocol == "tcp"


def test_parse_port_mapping_defaults() -> None:
    result = _parse_port_mapping({"containerPort": _PORT_3000})
    assert result.host_port is None
    assert result.container_port == _PORT_3000
    assert result.protocol == "tcp"


def test_get_container_stats_empty() -> None:
    stats = get_container_stats()
    assert isinstance(stats, list)


def test_get_container_sizes_empty() -> None:
    sizes = get_container_sizes()
    assert isinstance(sizes, list)


def test_find_stats_by_name_found() -> None:
    data = [{"name": "test", "cpu": "1%", "mem_usage": "100MB", "mem_percent": "0.5%"}]
    found = _find_stats_by_name(data, "test")
    assert found is not None
    assert found["name"] == "test"


def test_find_stats_by_name_not_found() -> None:
    found = _find_stats_by_name([], "no")
    assert found is None


def test_find_size_by_name_found() -> None:
    data = [{"name": "web", "writable": "10MB", "virtual": "100MB"}]
    found = _find_size_by_name(data, "web")
    assert found is not None
    assert found["name"] == "web"


def test_find_size_by_name_not_found() -> None:
    found = _find_size_by_name([], "no")
    assert found is None


def test_systemd_prefixes() -> None:
    assert "ami-" in SYSTEMD_PREFIXES
    assert "postgres" in SYSTEMD_PREFIXES


def test_find_workspace_root() -> None:
    root = _find_workspace_root()
    assert root is None or isinstance(root, Path)


def test_parse_systemd_details_basic() -> None:
    details = _parse_systemd_details(
        "Id=test.service\nActiveState=active\nSubState=running\nMainPID=123\n"
    )
    assert details["Id"] == "test.service"
    assert details["ActiveState"] == "active"
    assert details["SubState"] == "running"
    assert details["MainPID"] == "123"


def test_parse_systemd_details_empty() -> None:
    details = _parse_systemd_details("")
    assert details["Id"] == ""


def test_extract_compose_info_podman_compose() -> None:
    info = _extract_compose_info("podman-compose -f /etc/web.yml --profile prod up -d")
    assert info[1] == "/etc/web.yml"
    assert "prod" in info[2]


def test_extract_compose_info_podman_start() -> None:
    info = _extract_compose_info("podman start -a ami-web-container")
    assert info[0] == "ami-web-container"


def test_find_container_by_name() -> None:
    containers = [PodmanContainer(id="x", name="found")]
    result = _find_container_by_name(containers, "found")
    assert result is not None
    assert result.name == "found"


def test_find_container_by_name_not_found() -> None:
    result = _find_container_by_name([], "nope")
    assert result is None


def test_storage_prints_root_disk(capsys) -> None:
    _print_root_disk()
    captured = capsys.readouterr()
    assert "Root Disk" in captured.out


def test_storage_prints_container_sizes(capsys) -> None:
    _print_container_sizes()
    captured = capsys.readouterr()
    assert "Container Sizes" in captured.out


def test_storage_remove_path_dir(tmp_path) -> None:
    d = tmp_path / "testdir"
    d.mkdir()
    assert _remove_path(d) is True


def test_storage_remove_path_file(tmp_path) -> None:
    f = tmp_path / "test.txt"
    f.write_text("data")
    assert _remove_path(f) is True


def test_get_container_volumes() -> None:
    vols = get_container_volumes("test-container")
    assert isinstance(vols, list)


def test_get_podman_containers() -> None:
    containers = get_podman_containers()
    assert isinstance(containers, list)


def test_get_system_docker_containers() -> None:
    containers = get_system_docker_containers()
    assert isinstance(containers, list)


def test_get_system_docker_stats() -> None:
    stats = get_system_docker_stats()
    assert isinstance(stats, list)


def test_get_systemd_services() -> None:
    services = get_systemd_services()
    assert isinstance(services, list)


def test_get_managed_service_names() -> None:
    names = get_managed_service_names()
    assert isinstance(names, set)


def test_get_declared_compose_files() -> None:
    files = get_declared_compose_files()
    assert isinstance(files, set)


def test_process_service() -> None:
    svc = SystemdService(name="test", pid="12345")
    info = _process_service(svc, [], set())
    assert info.row_type is not None
    assert isinstance(info.child_items, list)
