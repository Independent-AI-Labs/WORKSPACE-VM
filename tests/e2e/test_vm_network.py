"""E2E tests for VM network isolation (requires full build)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

from tests.e2e.conftest import VMTracker, extract_uuid, vm_cmd

pytestmark = pytest.mark.e2e


class TestVMNetworkNone:
    def test_no_interfaces_except_lo(
        self,
        temp_config: Path,
        vm_tracker: VMTracker,
        vm_build_capable: None,
    ) -> None:
        result = vm_cmd("create", str(temp_config), timeout=600)
        assert result.returncode == 0
        uuid_val = extract_uuid(result.stdout)
        vm_tracker.register(uuid_val)

        exec_result = vm_cmd("exec", uuid_val, "--", "ip", "link")
        raw_lines = [ln for ln in exec_result.stdout.splitlines() if ln.strip()]
        non_lo = [
            ln for ln in raw_lines if "lo:" not in ln and "LOOPBACK" not in ln.upper()
        ]
        real_ifaces = [ln for ln in non_lo if "@NONE" not in ln and "NOARP" not in ln]
        assert len(real_ifaces) == 0, f"unexpected interfaces: {real_ifaces}"

    def test_no_external_connectivity(
        self,
        temp_config: Path,
        vm_tracker: VMTracker,
        vm_build_capable: None,
    ) -> None:
        result = vm_cmd("create", str(temp_config), timeout=600)
        assert result.returncode == 0
        uuid_val = extract_uuid(result.stdout)
        vm_tracker.register(uuid_val)

        ping_result = vm_cmd(
            "exec",
            uuid_val,
            "--",
            "ping",
            "-c",
            "1",
            "-W",
            "2",
            "1.1.1.1",
        )
        assert ping_result.returncode != 0


class TestVMNetworkBridge:
    def test_bridge_gets_ip(
        self,
        tmp_path: Path,
        vm_tracker: VMTracker,
        vm_build_capable: None,
    ) -> None:
        config_data = {
            "components": ["opencode"],
            "network": {
                "mode": "bridge",
                "network_name": "ami-vm-net",
                "policy": "internet",
            },
        }
        config_file = tmp_path / "bridge.yaml"
        config_file.write_text(yaml.dump(config_data))

        result = vm_cmd("create", str(config_file), timeout=600)
        assert result.returncode == 0
        uuid_val = extract_uuid(result.stdout)
        vm_tracker.register(uuid_val)

        inspect = subprocess.run(
            [
                "podman",
                "inspect",
                "-f",
                "{{.NetworkSettings.Networks.ami-vm-net.IPAddress}}",
                uuid_val,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        ip = inspect.stdout.strip()
        assert ip != ""
        assert "." in ip


class TestVMNetworkHost:
    def test_host_mode(
        self,
        tmp_path: Path,
        vm_tracker: VMTracker,
        vm_build_capable: None,
    ) -> None:
        config_data = {
            "components": ["opencode"],
            "network": {"mode": "host"},
        }
        config_file = tmp_path / "host.yaml"
        config_file.write_text(yaml.dump(config_data))

        result = vm_cmd("create", str(config_file), timeout=600)
        assert result.returncode == 0
        uuid_val = extract_uuid(result.stdout)
        vm_tracker.register(uuid_val)

        inspect = subprocess.run(
            ["podman", "inspect", "-f", "{{.HostConfig.NetworkMode}}", uuid_val],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "host" in inspect.stdout
