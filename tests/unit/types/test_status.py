"""Unit tests for workspace.types.status models."""

from workspace.types.status import (
    PodmanContainer,
    PortMapping,
    ServiceDisplayInfo,
    SystemdService,
)

_PORT_8080 = 8080
_PORT_80 = 80
_PORT_3000 = 3000
_PORT_443 = 443
_MEMORY_1MB = 1048576
_CPU_5MS = 5000000


class TestPortMapping:
    def test_default_construction(self) -> None:
        pm = PortMapping()
        assert pm.host_port is None
        assert pm.container_port is None
        assert pm.protocol == "tcp"

    def test_with_host_and_container_port(self) -> None:
        pm = PortMapping(host_port=_PORT_8080, container_port=_PORT_80)
        assert pm.host_port == _PORT_8080
        assert pm.container_port == _PORT_80

    def test_with_protocol(self) -> None:
        pm = PortMapping(host_port=_PORT_443, container_port=_PORT_443, protocol="udp")
        assert pm.protocol == "udp"

    def test_alias_population_host_port(self) -> None:
        pm = PortMapping.model_validate(
            {"hostPort": _PORT_3000, "containerPort": _PORT_3000}
        )
        assert pm.host_port == _PORT_3000
        assert pm.container_port == _PORT_3000


class TestPodmanContainer:
    def test_minimal_construction(self) -> None:
        c = PodmanContainer(id="abc123", name="myapp")
        assert c.id == "abc123"
        assert c.name == "myapp"
        assert c.state == ""
        assert c.status == ""
        assert c.ports == []
        assert c.image == ""
        assert c.labels == {}
        assert c.stats is None
        assert c.size is None

    def test_with_state_and_status(self) -> None:
        c = PodmanContainer(id="abc", name="svc", state="running", status="Up 5 min")
        assert c.state == "running"
        assert c.status == "Up 5 min"

    def test_with_ports(self) -> None:
        ports = [PortMapping(host_port=_PORT_80, container_port=_PORT_80)]
        c = PodmanContainer(id="x", name="web", ports=ports)
        assert len(c.ports) == 1
        assert c.ports[0].host_port == _PORT_80

    def test_with_labels_and_image(self) -> None:
        c = PodmanContainer(
            id="x", name="svc", image="nginx:1.27", labels={"env": "prod"}
        )
        assert c.image == "nginx:1.27"
        assert c.labels == {"env": "prod"}

    def test_stats_default_none(self) -> None:
        c = PodmanContainer(id="x", name="svc")
        assert c.stats is None


class TestSystemdService:
    def test_minimal_construction(self) -> None:
        s = SystemdService(name="ami-serve-web")
        assert s.name == "ami-serve-web"
        assert s.scope == ""
        assert s.active == ""
        assert s.sub == ""
        assert s.pid == "0"
        assert s.managed_container is None
        assert s.compose_file is None
        assert s.compose_profiles == []
        assert s.restart == ""
        assert s.enabled == ""
        assert s.memory_bytes == 0
        assert s.cpu_ns == 0
        assert s.start_time == ""
        assert s.description == ""
        assert s.exec_start == ""

    def test_active_sub_state(self) -> None:
        s = SystemdService(name="svc", active="active", sub="running")
        assert s.active == "active"
        assert s.sub == "running"

    def test_with_compose_info(self) -> None:
        s = SystemdService(
            name="svc",
            compose_file="/etc/compose.yml",
            compose_profiles=["prod"],
        )
        assert s.compose_file == "/etc/compose.yml"
        assert s.compose_profiles == ["prod"]

    def test_with_enhanced_fields(self) -> None:
        s = SystemdService(
            name="svc",
            restart="always",
            enabled="enabled",
            memory_bytes=_MEMORY_1MB,
            cpu_ns=_CPU_5MS,
            start_time="Tue 2025-01-01",
            description="A service",
            exec_start="/usr/bin/app",
        )
        assert s.restart == "always"
        assert s.enabled == "enabled"
        assert s.memory_bytes == _MEMORY_1MB
        assert s.cpu_ns == _CPU_5MS
        assert s.start_time == "Tue 2025-01-01"
        assert s.description == "A service"
        assert s.exec_start == "/usr/bin/app"

    def test_pid_as_string(self) -> None:
        s = SystemdService(name="svc", pid="12345")
        assert s.pid == "12345"

    def test_managed_container_none(self) -> None:
        s = SystemdService(name="svc", managed_container="ami-container")
        assert s.managed_container == "ami-container"


class TestServiceDisplayInfo:
    def test_default_construction(self) -> None:
        info = ServiceDisplayInfo(row_type="service")
        assert info.row_type == "service"
        assert info.row_details == []
        assert info.child_items == []
        assert info.ports_str == ""

    def test_with_row_details(self) -> None:
        info = ServiceDisplayInfo(
            row_type="container", row_details=["running", "ports: 8080"]
        )
        assert info.row_details == ["running", "ports: 8080"]

    def test_with_child_items(self) -> None:
        child = PodmanContainer(id="sub", name="worker")
        info = ServiceDisplayInfo(row_type="compose", child_items=[child])
        assert len(info.child_items) == 1
        assert info.child_items[0].name == "worker"

    def test_with_ports_str(self) -> None:
        info = ServiceDisplayInfo(row_type="service", ports_str="8080:80")
        assert info.ports_str == "8080:80"
