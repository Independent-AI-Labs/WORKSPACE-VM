"""Unit tests for workspace.cli.status_containers - system docker section."""

from unittest.mock import DEFAULT, patch

from workspace.cli.status_containers import (
    _find_size_by_name,
    _find_stats_by_name,
    _print_orphans,
    _print_service_children,
    _print_system_docker_section,
    get_system_docker_containers,
    get_system_docker_stats,
)
from workspace.types.common import ContainerSizeData, ContainerStatsData
from workspace.types.results import ContainerStatusDisplay
from workspace.types.status import PodmanContainer, PortMapping

SYSTEM_DOCKER_BIN = "/usr/bin/docker"
MIN_PARTS_COUNT = 2
MIN_VOLUME_BYTES = 8192

_PORT_80 = 80
_PORT_443 = 443
_PORT_3000 = 3000
_PORT_8080 = 8080
_PORT_8443 = 8443
_PORT_9000 = 9000
_PORT_9001 = 9001
_PORT_9999 = 9999
_PORT_5555 = 5555
_COUNT_2 = 2


def _make_podman_container(**kwargs):
    defaults = {
        "id": "abc123456789",
        "name": "test-container",
        "state": "running",
        "status": "Up 5 minutes",
        "ports": [],
        "image": "nginx:1.27",
        "labels": {},
    }
    defaults.update(kwargs)
    return PodmanContainer(**defaults)


class TestGetSystemDockerContainers:
    @patch("workspace.cli.status_containers.os.path.exists")
    def test_returns_empty_when_docker_bin_missing(self, mock_exists):
        mock_exists.return_value = False

        containers = get_system_docker_containers()

        assert containers == []
        mock_exists.assert_called_once_with("/usr/bin/docker")

    @patch("workspace.cli.status_containers.run_cmd")
    @patch("workspace.cli.status_containers.os.path.exists")
    def test_returns_empty_when_output_empty_no_sudo(self, mock_exists, mock_run_cmd):
        mock_exists.return_value = True
        mock_run_cmd.return_value = ""

        containers = get_system_docker_containers()

        assert containers == []

    @patch("workspace.cli.status_containers.run_cmd")
    @patch("workspace.cli.status_containers.os.path.exists")
    def test_tries_sudo_fallback_when_docker_fails(self, mock_exists, mock_run_cmd):
        mock_exists.return_value = True
        docker_output = (
            '{"ID": "abc123", "Names": "mydocker", "State": "running", '
            '"Status": "Up", "Image": "redis", "Ports": ""}\n'
        )
        mock_run_cmd.side_effect = ["", docker_output]

        containers = get_system_docker_containers()

        assert len(containers) == 1
        assert containers[0].name == "mydocker"
        assert mock_run_cmd.call_count == _COUNT_2

    @patch("workspace.cli.status_containers.os.path.exists")
    @patch("workspace.cli.status_containers.run_cmd")
    def test_parses_docker_json_line_by_line(self, mock_run_cmd, mock_exists):
        mock_exists.return_value = True
        mock_run_cmd.return_value = (
            '{"ID": "aaa111", "Names": "nginx", "State": "running", '
            '"Status": "Up 10 min", "Image": "nginx:1.27", "Ports": ""}\n'
            '{"ID": "bbb222", "Names": "redis", "State": "exited", '
            '"Status": "Exited", "Image": "redis:7", "Ports": ""}'
        )

        containers = get_system_docker_containers()

        assert len(containers) == _COUNT_2
        assert containers[0].name == "nginx"
        assert containers[1].name == "redis"

    @patch("workspace.cli.status_containers.os.path.exists")
    @patch("workspace.cli.status_containers.run_cmd")
    def test_parses_port_string_format(self, mock_run_cmd, mock_exists):
        mock_exists.return_value = True
        mock_run_cmd.return_value = (
            '{"ID": "web123", "Names": "web", "State": "running", '
            '"Status": "Up", "Image": "nginx", '
            '"Ports": "0.0.0.0:8080->80/tcp, 0.0.0.0:8443->443/tcp"}'
        )

        containers = get_system_docker_containers()

        assert len(containers) == 1
        assert len(containers[0].ports) == _COUNT_2
        assert containers[0].ports[0].host_port == _PORT_8080
        assert containers[0].ports[0].container_port == _PORT_80
        assert containers[0].ports[0].protocol == "tcp"
        assert containers[0].ports[1].host_port == _PORT_8443
        assert containers[0].ports[1].container_port == _PORT_443
        assert containers[0].ports[1].protocol == "tcp"

    @patch("workspace.cli.status_containers.os.path.exists")
    @patch("workspace.cli.status_containers.run_cmd")
    def test_handles_json_decode_error_per_line(self, mock_run_cmd, mock_exists):
        mock_exists.return_value = True
        mock_run_cmd.return_value = "bad json { not valid"

        containers = get_system_docker_containers()

        assert containers == []

    @patch("workspace.cli.status_containers.os.path.exists")
    @patch("workspace.cli.status_containers.run_cmd")
    def test_uses_id_when_names_missing(self, mock_run_cmd, mock_exists):
        mock_exists.return_value = True
        mock_run_cmd.return_value = (
            '{"ID": "abc123def456", "State": "running", "Status": "Up", '
            '"Image": "busybox", "Ports": ""}'
        )

        containers = get_system_docker_containers()

        assert len(containers) == 1
        assert containers[0].name == "abc123def456"


class TestGetSystemDockerStats:
    @patch("workspace.cli.status_containers.os.path.exists")
    def test_returns_empty_when_docker_binary_missing(self, mock_exists):
        mock_exists.return_value = False

        stats = get_system_docker_stats()

        assert stats == []

    @patch("workspace.cli.status_containers.run_cmd")
    @patch("workspace.cli.status_containers.os.path.exists")
    def test_parses_stats_in_name_cpu_mem_format(self, mock_exists, mock_run_cmd):
        mock_exists.return_value = True
        mock_run_cmd.return_value = (
            "mycontainer|0.50%|100MiB / 1GiB\nweb|0.20%|50MiB / 500MiB"
        )

        stats = get_system_docker_stats()

        assert len(stats) == _COUNT_2
        assert stats[0]["name"] == "mycontainer"
        assert stats[0]["cpu"] == "0.50%"
        assert stats[0]["mem_usage"] == "100MiB / 1GiB"
        assert stats[1]["name"] == "web"
        assert stats[1]["cpu"] == "0.20%"

    @patch("workspace.cli.status_containers.run_cmd")
    @patch("workspace.cli.status_containers.os.path.exists")
    def test_returns_empty_on_no_output(self, mock_exists, mock_run_cmd):
        mock_exists.return_value = True
        mock_run_cmd.return_value = ""

        stats = get_system_docker_stats()

        assert stats == []

    @patch("workspace.cli.status_containers.run_cmd")
    @patch("workspace.cli.status_containers.os.path.exists")
    def test_skips_lines_with_too_few_parts(self, mock_exists, mock_run_cmd):
        mock_exists.return_value = True
        mock_run_cmd.return_value = "short_line\nvalid|0.5%|100MiB / 1GiB"

        stats = get_system_docker_stats()

        assert len(stats) == 1
        assert stats[0]["name"] == "valid"


class TestFindStatsByName:
    def test_finds_matching_stats_entry(self):
        stats_list = [
            ContainerStatsData(
                name="web", cpu="0.5%", mem_usage="100MB", mem_percent="10%"
            ),
            ContainerStatsData(
                name="db", cpu="1.0%", mem_usage="200MB", mem_percent="20%"
            ),
        ]

        result = _find_stats_by_name(stats_list, "db")

        assert result is not None
        assert result["name"] == "db"
        assert result["cpu"] == "1.0%"

    def test_returns_none_when_not_found(self):
        stats_list = [
            ContainerStatsData(
                name="web", cpu="0.5%", mem_usage="100MB", mem_percent="10%"
            ),
        ]

        result = _find_stats_by_name(stats_list, "nonexistent")

        assert result is None


class TestFindSizeByName:
    def test_finds_matching_size_entry(self):
        sizes_list = [
            ContainerSizeData(name="web", writable="22kB", virtual="198MB"),
            ContainerSizeData(name="db", writable="45MB", virtual="250MB"),
        ]

        result = _find_size_by_name(sizes_list, "web")

        assert result is not None
        assert result["name"] == "web"
        assert result["writable"] == "22kB"

    def test_returns_none_when_not_found(self):
        sizes_list = [
            ContainerSizeData(name="web", writable="22kB", virtual="198MB"),
        ]

        result = _find_size_by_name(sizes_list, "nonexistent")

        assert result is None


class TestPrintServiceChildren:
    @patch("workspace.cli.status_containers.get_container_volumes")
    @patch("workspace.cli.status_containers.format_ports")
    @patch("workspace.cli.status_containers.print_box_line")
    def test_does_nothing_with_empty_child_items(
        self, mock_print_box, mock_format_ports, mock_volumes
    ):
        _print_service_children([], [], [])

        mock_print_box.assert_not_called()

    @patch("workspace.cli.status_containers.get_container_volumes")
    @patch("workspace.cli.status_containers.format_ports")
    @patch("workspace.cli.status_containers.print_box_line")
    def test_prints_child_containers_with_state_image_ports(
        self, mock_print_box, mock_format_ports, mock_volumes
    ):
        mock_format_ports.return_value = "8080->80/tcp"
        mock_volumes.return_value = []
        c = _make_podman_container(
            id="child1",
            name="child-svc",
            state="running",
            image="alpine:edge",
            ports=[
                PortMapping(host_port=8080, container_port=80, protocol="tcp"),
            ],
        )

        _print_service_children([c], [], [])

        calls = mock_print_box.call_args_list
        texts = [call[0][0] for call in calls]
        assert any("child-svc" in t and "[running]" in t for t in texts)
        assert any("alpine:edge" in t for t in texts)
        assert any("8080->80/tcp" in t for t in texts)

    @patch("workspace.cli.status_containers.get_container_volumes")
    @patch("workspace.cli.status_containers.format_ports")
    @patch("workspace.cli.status_containers.print_box_line")
    def test_prints_stats_when_container_is_running(
        self, mock_print_box, mock_format_ports, mock_volumes
    ):
        mock_format_ports.return_value = ""
        mock_volumes.return_value = []
        c = _make_podman_container(name="active-svc", state="running")
        stats = [
            ContainerStatsData(
                name="active-svc", cpu="0.8%", mem_usage="80MB / 1GB", mem_percent="8%"
            ),
        ]

        _print_service_children([c], stats, [])

        calls = mock_print_box.call_args_list
        texts = [call[0][0] for call in calls]
        assert any("0.8%" in t and "80MB / 1GB" in t for t in texts)

    @patch("workspace.cli.status_containers.get_container_volumes")
    @patch("workspace.cli.status_containers.format_ports")
    @patch("workspace.cli.status_containers.print_box_line")
    def test_prints_sizes_when_available(
        self, mock_print_box, mock_format_ports, mock_volumes
    ):
        mock_format_ports.return_value = ""
        mock_volumes.return_value = []
        c = _make_podman_container(name="sized-svc", state="exited")
        sizes = [
            ContainerSizeData(name="sized-svc", writable="10MB", virtual="150MB"),
        ]

        _print_service_children([c], [], sizes)

        calls = mock_print_box.call_args_list
        texts = [call[0][0] for call in calls]
        assert any("150MB" in t and "10MB" in t for t in texts)


class TestPrintOrphans:
    @patch("workspace.cli.status_containers.format_ports")
    def test_does_nothing_when_no_orphans(self, mock_format_ports, capsys):
        c = _make_podman_container(name="managed", id="m1")
        processed = {"managed"}

        _print_orphans([c], processed)

        captured = capsys.readouterr()
        mock_format_ports.assert_not_called()
        assert "UNMANAGED" not in captured.out

    @patch("workspace.cli.status_containers.print_box_line")
    @patch("workspace.cli.status_containers.format_ports")
    def test_prints_orphan_containers_with_state_and_ports(
        self, mock_format_ports, mock_print_box, capsys
    ):
        mock_format_ports.return_value = "3000->3000/tcp"
        c1 = _make_podman_container(name="orphan1", id="o1", state="exited")
        c2 = _make_podman_container(
            name="orphan2",
            id="o2",
            state="running",
            ports=[PortMapping(host_port=3000, container_port=3000, protocol="tcp")],
        )

        _print_orphans([c1, c2], set())

        calls = mock_print_box.call_args_list
        texts = [call[0][0] for call in calls]
        assert any("UNMANAGED" in t for t in texts)
        assert any("orphan1" in t and "exited" in t for t in texts)
        assert any("orphan2" in t and "running" in t for t in texts)
        assert any("3000->3000/tcp" in t for t in texts)

    @patch("workspace.cli.status_containers.print_box_line")
    @patch("workspace.cli.status_containers.format_ports")
    def test_filters_out_run_prefix_containers(
        self, mock_format_ports, mock_print_box, capsys
    ):
        mock_format_ports.return_value = ""
        c_run = _make_podman_container(name="run-abc123", id="r1")
        c_normal = _make_podman_container(name="normal-orphan", id="n1")

        _print_orphans([c_run, c_normal], set())

        calls = mock_print_box.call_args_list
        texts = [call[0][0] for call in calls]
        assert any("normal-orphan" in t for t in texts)
        assert not any("run-abc123" in t for t in texts)


class TestPrintSystemDockerSection:
    @patch("workspace.cli.status_containers.print_box_line")
    @patch("workspace.cli.status_containers.os.path.exists")
    def test_prints_not_found_when_docker_binary_missing(
        self, mock_exists, mock_print_box, capsys
    ):
        mock_exists.return_value = False

        _print_system_docker_section()

        calls = mock_print_box.call_args_list
        texts = [call[0][0] for call in calls]
        assert any("not found" in t.lower() for t in texts)

    @patch("workspace.cli.status_containers.get_system_docker_stats")
    @patch("workspace.cli.status_containers.get_system_docker_containers")
    @patch("workspace.cli.status_containers.os.path.exists")
    def test_prints_no_containers_message_when_list_empty(
        self, mock_exists, mock_get_containers, mock_get_stats, capsys
    ):
        mock_exists.return_value = True
        mock_get_containers.return_value = []
        mock_get_stats.return_value = []

        _print_system_docker_section()

        captured = capsys.readouterr()
        assert "SYSTEM DOCKER" in captured.out

    @patch.multiple(
        "workspace.cli.status_containers",
        _format_port_string=DEFAULT,
        _get_container_status_display=DEFAULT,
        get_system_docker_stats=DEFAULT,
        get_system_docker_containers=DEFAULT,
        print_box_line=DEFAULT,
    )
    @patch("workspace.cli.status_containers.os.path.exists")
    def test_prints_system_docker_containers_with_stats_and_ports(
        self, mock_exists, capsys, **mocks
    ):
        mock_format_port = mocks["_format_port_string"]
        mock_status_display = mocks["_get_container_status_display"]
        mock_get_stats = mocks["get_system_docker_stats"]
        mock_get_containers = mocks["get_system_docker_containers"]
        mock_print_box = mocks["print_box_line"]

        mock_exists.return_value = True
        mock_status_display.return_value = ContainerStatusDisplay("icon", "COLOR")
        mock_format_port.return_value = "80->80/tcp"

        c1 = _make_podman_container(
            id="d1",
            name="docker-nginx",
            state="running",
            image="nginx:1.27",
            ports=[PortMapping(host_port=80, container_port=80, protocol="tcp")],
        )
        c2 = _make_podman_container(
            id="d2",
            name="docker-redis",
            state="running",
            image="redis:7",
            ports=[],
        )
        mock_get_containers.return_value = [c1, c2]
        mock_get_stats.return_value = [
            ContainerStatsData(
                name="docker-nginx", cpu="0.3%", mem_usage="50MiB", mem_percent="5%"
            ),
        ]

        _print_system_docker_section()

        calls = mock_print_box.call_args_list
        texts = [call[0][0] for call in calls]
        assert any("SYSTEM DOCKER" in t for t in texts)
        assert any("docker-nginx" in t for t in texts)
        assert any("docker-redis" in t for t in texts)
        assert any("nginx:1.27" in t for t in texts)
        stats_texts = [t for t in texts if "0.3%" in t and "50MiB" in t]
        assert len(stats_texts) >= 1
