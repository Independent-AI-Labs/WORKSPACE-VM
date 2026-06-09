"""E2E tests for VM security hardening (requires full build)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

from tests.e2e.conftest import VMTracker, extract_uuid, vm_cmd

pytestmark = pytest.mark.e2e


class TestVMSecurityDefaults:
    def test_cap_drop_all(
        self,
        temp_config: Path,
        vm_tracker: VMTracker,
        vm_build_capable: None,
    ) -> None:
        result = vm_cmd("create", str(temp_config), timeout=600)
        assert result.returncode == 0
        uuid_val = extract_uuid(result.stdout)
        vm_tracker.register(uuid_val)

        inspect = subprocess.run(
            ["podman", "inspect", "-f", "{{.HostConfig.CapDrop}}", uuid_val],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "ALL" in inspect.stdout

    def test_no_new_privileges(
        self,
        temp_config: Path,
        vm_tracker: VMTracker,
        vm_build_capable: None,
    ) -> None:
        result = vm_cmd("create", str(temp_config), timeout=600)
        assert result.returncode == 0
        uuid_val = extract_uuid(result.stdout)
        vm_tracker.register(uuid_val)

        inspect = subprocess.run(
            ["podman", "inspect", "-f", "{{.HostConfig.SecurityOpt}}", uuid_val],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "no-new-privileges" in inspect.stdout

    def test_runs_as_non_root(
        self,
        temp_config: Path,
        vm_tracker: VMTracker,
        vm_build_capable: None,
    ) -> None:
        result = vm_cmd("create", str(temp_config), timeout=600)
        assert result.returncode == 0
        uuid_val = extract_uuid(result.stdout)
        vm_tracker.register(uuid_val)

        user_result = vm_cmd("exec", uuid_val, "--", "whoami")
        assert user_result.stdout.strip() != "root"

    def test_read_only_rootfs(
        self,
        temp_config: Path,
        vm_tracker: VMTracker,
        vm_build_capable: None,
    ) -> None:
        result = vm_cmd("create", str(temp_config), timeout=600)
        assert result.returncode == 0
        uuid_val = extract_uuid(result.stdout)
        vm_tracker.register(uuid_val)

        write_result = vm_cmd(
            "exec",
            uuid_val,
            "--",
            "touch",
            "/should-fail.txt",
        )
        assert write_result.returncode != 0


class TestVMSecurityNetAdmin:
    def test_net_admin_added_for_internet(
        self,
        tmp_path: Path,
        vm_tracker: VMTracker,
        vm_build_capable: None,
    ) -> None:
        config_data = {
            "components": ["opencode"],
            "network": {"mode": "bridge", "policy": "internet"},
        }
        config_file = tmp_path / "netadmin.yaml"
        config_file.write_text(yaml.dump(config_data))

        result = vm_cmd("create", str(config_file), timeout=600)
        assert result.returncode == 0
        uuid_val = extract_uuid(result.stdout)
        vm_tracker.register(uuid_val)

        inspect = subprocess.run(
            ["podman", "inspect", "-f", "{{.HostConfig.CapAdd}}", uuid_val],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "NET_ADMIN" in inspect.stdout

    def test_net_admin_not_added_for_unrestricted(
        self,
        tmp_path: Path,
        vm_tracker: VMTracker,
        vm_build_capable: None,
    ) -> None:
        config_data = {
            "components": ["opencode"],
            "network": {"mode": "bridge", "policy": "unrestricted"},
        }
        config_file = tmp_path / "unres.yaml"
        config_file.write_text(yaml.dump(config_data))

        result = vm_cmd("create", str(config_file), timeout=600)
        assert result.returncode == 0
        uuid_val = extract_uuid(result.stdout)
        vm_tracker.register(uuid_val)

        inspect = subprocess.run(
            ["podman", "inspect", "-f", "{{.HostConfig.CapAdd}}", uuid_val],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "NET_ADMIN" not in inspect.stdout
