"""Unit tests for workspace.cli.status_containers."""

from unittest.mock import patch

from workspace.cli.status_containers import (
    _get_container_inspect_info,
    _parse_port_mapping,
    get_container_sizes,
    get_container_stats,
    get_container_volumes,
    get_podman_containers,
)
from workspace.types.results import ContainerInspectInfo

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


class TestParsePortMapping:
    def test_host_port_and_container_port(self):
        result = _parse_port_mapping(
            {
                "hostPort": "8080",
                "containerPort": "80",
            }
        )
        assert result.host_port == _PORT_8080
        assert result.container_port == _PORT_80
        assert result.protocol == "tcp"

    def test_host_port_key(self):
        result = _parse_port_mapping(
            {
                "HostPort": "3000",
                "ContainerPort": "3000",
            }
        )
        assert result.host_port == _PORT_3000
        assert result.container_port == _PORT_3000

    def test_host_port_key_lowercase(self):
        result = _parse_port_mapping(
            {
                "host_port": "9000",
                "container_port": "9001",
            }
        )
        assert result.host_port == _PORT_9000
        assert result.container_port == _PORT_9001

    def test_protocol_field(self):
        result = _parse_port_mapping(
            {
                "hostPort": "8080",
                "containerPort": "80",
                "protocol": "udp",
            }
        )
        assert result.protocol == "udp"

    def test_missing_host_port_returns_none(self):
        result = _parse_port_mapping(
            {
                "containerPort": "80",
            }
        )
        assert result.host_port is None
        assert result.container_port == _PORT_80

    def test_missing_container_port_returns_none(self):
        result = _parse_port_mapping(
            {
                "hostPort": "8080",
            }
        )
        assert result.host_port == _PORT_8080
        assert result.container_port is None

    def test_default_protocol_is_tcp(self):
        result = _parse_port_mapping(
            {
                "hostPort": "443",
                "containerPort": "443",
            }
        )
        assert result.protocol == "tcp"

    def test_multiple_port_variations_in_one_dict(self):
        result = _parse_port_mapping(
            {
                "hostPort": "9999",
                "HostPort": "8888",
                "host_port": "7777",
                "containerPort": "5555",
                "ContainerPort": "4444",
                "container_port": "3333",
                "protocol": "tcp",
                "Protocol": "udp",
            }
        )
        assert result.host_port == _PORT_9999
        assert result.container_port == _PORT_5555
        assert result.protocol == "tcp"


class TestGetContainerInspectInfo:
    @patch("workspace.cli.status_containers.run_cmd")
    def test_returns_ports_and_labels_from_valid_json(self, mock_run_cmd):
        inspect_json = (
            '[{"Config": {'
            '"Labels": {"app": "nginx"}, '
            '"ExposedPorts": {"80/tcp": {}, "443/udp": {}}'
            "}}]"
        )
        mock_run_cmd.return_value = inspect_json

        result = _get_container_inspect_info("myapp", "podman")

        assert len(result.ports) == _COUNT_2
        port_protos = {(p.container_port, p.protocol) for p in result.ports}
        assert port_protos == {(80, "tcp"), (443, "udp")}
        assert result.labels == {"app": "nginx"}

    @patch("workspace.cli.status_containers.run_cmd")
    def test_returns_empty_info_when_inspect_raw_empty(self, mock_run_cmd):
        mock_run_cmd.return_value = ""

        result = _get_container_inspect_info("myapp", "podman")

        assert result.ports == []
        assert result.labels == {}

    @patch("workspace.cli.status_containers.run_cmd")
    def test_returns_empty_info_on_json_parse_error(self, mock_run_cmd):
        mock_run_cmd.return_value = "not valid json{{{{"

        result = _get_container_inspect_info("myapp", "podman")

        assert result.ports == []
        assert result.labels == {}

    @patch("workspace.cli.status_containers.run_cmd")
    def test_returns_empty_info_on_missing_config_key(self, mock_run_cmd):
        mock_run_cmd.return_value = '[{"NoConfig": {}}]'

        result = _get_container_inspect_info("myapp", "podman")

        assert result.ports == []
        assert result.labels == {}

    @patch("workspace.cli.status_containers.run_cmd")
    def test_handles_containers_without_exposed_ports(self, mock_run_cmd):
        mock_run_cmd.return_value = (
            '[{"Config": {"Labels": {"env": "prod"}, "ExposedPorts": null}}]'
        )

        result = _get_container_inspect_info("myapp", "podman")

        assert result.ports == []
        assert result.labels == {"env": "prod"}

    @patch("workspace.cli.status_containers.run_cmd")
    def test_calls_run_cmd_with_correct_command(self, mock_run_cmd):
        mock_run_cmd.return_value = '[{"Config": {"Labels": {}, "ExposedPorts": {}}}]'

        _get_container_inspect_info("mycontainer", "/usr/bin/podman")

        mock_run_cmd.assert_called_once_with(
            "/usr/bin/podman inspect mycontainer -format json"
        )


class TestGetContainerStats:
    @patch("workspace.cli.status_containers.run_cmd")
    def test_parses_stats_with_name_cpu_mem_usage(self, mock_run_cmd):
        mock_run_cmd.return_value = (
            '[{"Name": "web", "CPU": "0.50%", "MemUsage": "100MB / 1GB", '
            '"MemPerc": "10.00%"}]'
        )
        stats = get_container_stats()
        assert len(stats) == 1
        assert stats[0]["name"] == "web"
        assert stats[0]["cpu"] == "0.50%"
        assert stats[0]["mem_usage"] == "100MB / 1GB"
        assert stats[0]["mem_percent"] == "10.00%"

    @patch("workspace.cli.status_containers.run_cmd")
    def test_parses_stats_with_lowercase_keys(self, mock_run_cmd):
        mock_run_cmd.return_value = (
            '[{"name": "worker", "cpu_percent": "1.20%", "mem_usage": "50MB / 500MB", '
            '"mem_percent": "5.00%"}]'
        )
        stats = get_container_stats()
        assert len(stats) == 1
        assert stats[0]["name"] == "worker"
        assert stats[0]["cpu"] == "1.20%"
        assert stats[0]["mem_usage"] == "50MB / 500MB"
        assert stats[0]["mem_percent"] == "5.00%"

    @patch("workspace.cli.status_containers.run_cmd")
    def test_returns_empty_list_when_output_empty(self, mock_run_cmd):
        mock_run_cmd.return_value = ""
        stats = get_container_stats()
        assert stats == []

    @patch("workspace.cli.status_containers.run_cmd")
    def test_skips_entries_without_name(self, mock_run_cmd):
        mock_run_cmd.return_value = (
            '[{"CPU": "0.1%", "MemUsage": "10MB / 100MB"}, '
            '{"Name": "valid", "CPU": "0.2%", "MemUsage": "20MB / 200MB"}]'
        )
        stats = get_container_stats()
        assert len(stats) == 1
        assert stats[0]["name"] == "valid"

    @patch("workspace.cli.status_containers.run_cmd")
    def test_handles_json_decode_error_gracefully(self, mock_run_cmd):
        mock_run_cmd.return_value = "corrupted { json [ data"
        stats = get_container_stats()
        assert stats == []


class TestGetContainerSizes:
    @patch("workspace.cli.status_containers.run_cmd")
    def test_parses_size_with_writable_and_virtual(self, mock_run_cmd):
        mock_run_cmd.return_value = (
            "web\t22kB (virtual 198MB)\nworker\t15MB (virtual 250MB)"
        )
        sizes = get_container_sizes()
        assert len(sizes) == _COUNT_2
        assert sizes[0]["name"] == "web"
        assert sizes[0]["writable"] == "22kB"
        assert sizes[0]["virtual"] == "198MB"
        assert sizes[1]["name"] == "worker"
        assert sizes[1]["writable"] == "15MB"
        assert sizes[1]["virtual"] == "250MB"

    @patch("workspace.cli.status_containers.run_cmd")
    def test_parses_size_without_virtual_part(self, mock_run_cmd):
        mock_run_cmd.return_value = "db\t45MB\ncache\t2GB"
        sizes = get_container_sizes()
        assert len(sizes) == _COUNT_2
        assert sizes[0]["name"] == "db"
        assert sizes[0]["writable"] == "45MB"
        assert sizes[0]["virtual"] == "-"
        assert sizes[1]["name"] == "cache"
        assert sizes[1]["writable"] == "2GB"
        assert sizes[1]["virtual"] == "-"

    @patch("workspace.cli.status_containers.run_cmd")
    def test_returns_empty_list_when_empty_output(self, mock_run_cmd):
        mock_run_cmd.return_value = ""
        sizes = get_container_sizes()
        assert sizes == []

    @patch("workspace.cli.status_containers.run_cmd")
    def test_skips_lines_with_too_few_parts(self, mock_run_cmd):
        mock_run_cmd.return_value = "orphan_line_no_tab\nweb\t22kB (virtual 198MB)"
        sizes = get_container_sizes()
        assert len(sizes) == 1
        assert sizes[0]["name"] == "web"

    @patch("workspace.cli.status_containers.run_cmd")
    def test_formats_size_with_kB_and_MB_units(self, mock_run_cmd):
        mock_run_cmd.return_value = "app\t22kB (virtual 198MB)"
        sizes = get_container_sizes()
        assert len(sizes) == 1
        assert sizes[0]["name"] == "app"
        assert sizes[0]["writable"] == "22kB"
        assert sizes[0]["virtual"] == "198MB"


class TestGetContainerVolumes:
    @patch("workspace.cli.status_containers.run_cmd")
    def test_returns_volumes_with_dest_source_type_size(self, mock_run_cmd):
        inspect_json = (
            '[{"Mounts": ['
            '{"Source": "/data/app", "Destination": "/var/lib/data", "Type": "bind"}'
            "]}]"
        )
        mock_run_cmd.side_effect = [inspect_json, "52428800"]

        volumes = get_container_volumes("myapp")

        assert len(volumes) == 1
        assert volumes[0]["dst"] == "/var/lib/data"
        assert volumes[0]["src"] == "/data/app"
        assert volumes[0]["type"] == "bind"
        assert volumes[0]["size"] == "50.0MB"

    @patch("workspace.cli.status_containers.run_cmd")
    def test_returns_empty_when_inspect_output_empty(self, mock_run_cmd):
        mock_run_cmd.return_value = ""

        volumes = get_container_volumes("myapp")

        assert volumes == []

    @patch("workspace.cli.status_containers.run_cmd")
    def test_filters_volumes_smaller_than_min_bytes(self, mock_run_cmd):
        inspect_json = (
            '[{"Mounts": ['
            '{"Source": "/small", "Destination": "/mnt/small", "Type": "bind"}, '
            '{"Source": "/large", "Destination": "/mnt/large", "Type": "bind"}'
            "]}]"
        )
        mock_run_cmd.side_effect = [inspect_json, "4096", "10485760"]

        volumes = get_container_volumes("myapp")

        assert len(volumes) == 1
        assert volumes[0]["dst"] == "/mnt/large"

    @patch("workspace.cli.status_containers.run_cmd")
    def test_handles_json_decode_error(self, mock_run_cmd):
        mock_run_cmd.return_value = "{broken"

        volumes = get_container_volumes("myapp")

        assert volumes == []

    @patch("workspace.cli.status_containers.run_cmd")
    def test_handles_empty_mounts_list(self, mock_run_cmd):
        mock_run_cmd.return_value = '[{"Mounts": []}]'

        volumes = get_container_volumes("myapp")

        assert volumes == []


class TestGetPodmanContainers:
    @patch("workspace.cli.status_containers._get_container_inspect_info")
    @patch("workspace.cli.status_containers.run_cmd")
    def test_parses_containers_with_names_state_status_image_id(
        self, mock_run_cmd, mock_inspect
    ):
        mock_inspect.return_value = ContainerInspectInfo([], {})
        mock_run_cmd.return_value = (
            '[{"Id": "abc123456789abcdef", "Names": ["web"], '
            '"State": "running", "Status": "Up 5 min", '
            '"Image": "nginx:1.27", "Ports": []}]'
        )

        containers = get_podman_containers()

        assert len(containers) == 1
        assert containers[0].id == "abc123456789"
        assert containers[0].name == "web"
        assert containers[0].state == "running"
        assert containers[0].status == "Up 5 min"
        assert containers[0].image == "nginx:1.27"

    @patch("workspace.cli.status_containers._get_container_inspect_info")
    @patch("workspace.cli.status_containers.run_cmd")
    def test_uses_first_name_from_names_list(self, mock_run_cmd, mock_inspect):
        mock_inspect.return_value = ContainerInspectInfo([], {})
        mock_run_cmd.return_value = (
            '[{"Id": "def4567890123456", "Names": ["primary", "alias1"], '
            '"State": "running", "Status": "Up", "Image": "alpine"}]'
        )

        containers = get_podman_containers()

        assert containers[0].name == "primary"

    @patch("workspace.cli.status_containers._get_container_inspect_info")
    @patch("workspace.cli.status_containers.run_cmd")
    def test_falls_back_to_id_when_names_empty(self, mock_run_cmd, mock_inspect):
        mock_inspect.return_value = ContainerInspectInfo([], {})
        mock_run_cmd.return_value = (
            '[{"Id": "xyz7890123456789", "Names": [], '
            '"State": "created", "Status": "Created", "Image": "busybox"}]'
        )

        containers = get_podman_containers()

        assert containers[0].name == "xyz789012345"

    @patch("workspace.cli.status_containers._get_container_inspect_info")
    @patch("workspace.cli.status_containers.run_cmd")
    def test_returns_empty_list_when_output_empty(self, mock_run_cmd, mock_inspect):
        mock_run_cmd.return_value = ""

        containers = get_podman_containers()

        assert containers == []

    @patch("workspace.cli.status_containers._get_container_inspect_info")
    @patch("workspace.cli.status_containers.run_cmd")
    def test_handles_json_decode_error(self, mock_run_cmd, mock_inspect):
        mock_run_cmd.return_value = "not json at all"

        containers = get_podman_containers()

        assert containers == []

    @patch("workspace.cli.status_containers._get_container_inspect_info")
    @patch("workspace.cli.status_containers.run_cmd")
    def test_handles_general_exception(self, mock_run_cmd, mock_inspect):
        mock_inspect.side_effect = Exception("inspect failure")
        mock_run_cmd.return_value = (
            '[{"Id": "bad123456789", "Names": ["bad"], '
            '"State": "running", "Status": "Up", "Image": "img"}]'
        )

        containers = get_podman_containers()

        assert containers == []
