"""E2E tests for vm create - requires full build pipeline."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml

from tests.e2e.conftest import _VMS_DIR, VMTracker, extract_uuid, vm_cmd

pytestmark = pytest.mark.e2e

_PASSWORD_LEN = 32


class TestVMCreate:
    def test_create_exits_cleanly(
        self,
        temp_config: Path,
        vm_tracker: VMTracker,
        vm_build_capable: None,
    ) -> None:
        result = vm_cmd("create", str(temp_config), timeout=600)
        assert result.returncode == 0, f"create failed: {result.stderr}"
        uuid_val = extract_uuid(result.stdout)
        vm_tracker.register(uuid_val)
        assert "VM " in result.stdout
        assert "UUID:" in result.stdout
        assert "Password:" in result.stdout
        assert "Cert:" in result.stdout

    def test_container_running_after_create(
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
            ["podman", "inspect", "-f", "{{.State.Running}}", uuid_val],
            capture_output=True,
            text=True,
            check=True,
        )
        assert inspect.stdout.strip() == "true"

    def test_labels_correct(
        self,
        temp_config: Path,
        vm_tracker: VMTracker,
        vm_build_capable: None,
    ) -> None:
        result = vm_cmd("create", str(temp_config), timeout=600)
        assert result.returncode == 0
        uuid_val = extract_uuid(result.stdout)
        vm_tracker.register(uuid_val)
        labels_raw = subprocess.run(
            ["podman", "inspect", "-f", "{{json .Config.Labels}}", uuid_val],
            capture_output=True,
            text=True,
            check=True,
        )
        labels = json.loads(labels_raw.stdout.strip())
        assert labels.get("workspace.type") == "vm"
        assert labels.get("ami.uuid") == uuid_val
        assert "ami.config" in labels

    def test_volumes_created(
        self,
        temp_config: Path,
        vm_tracker: VMTracker,
        vm_build_capable: None,
    ) -> None:
        result = vm_cmd("create", str(temp_config), timeout=600)
        assert result.returncode == 0
        uuid_val = extract_uuid(result.stdout)
        vm_tracker.register(uuid_val)
        for suffix in ("workspace", "transcripts", "cache"):
            vol_result = subprocess.run(
                ["podman", "volume", "exists", f"{uuid_val}-{suffix}"],
                capture_output=True,
                check=True,
            )
            assert vol_result.returncode == 0

    def test_pid_file_written(
        self,
        temp_config: Path,
        vm_tracker: VMTracker,
        vm_build_capable: None,
    ) -> None:
        result = vm_cmd("create", str(temp_config), timeout=600)
        assert result.returncode == 0
        uuid_val = extract_uuid(result.stdout)
        vm_tracker.register(uuid_val)
        pid_file = _VMS_DIR / uuid_val / "pid"
        assert pid_file.exists()
        pid = pid_file.read_text().strip()
        assert pid.isdigit()

    def test_password_file_written(
        self,
        temp_config: Path,
        vm_tracker: VMTracker,
        vm_build_capable: None,
    ) -> None:
        result = vm_cmd("create", str(temp_config), timeout=600)
        assert result.returncode == 0
        uuid_val = extract_uuid(result.stdout)
        vm_tracker.register(uuid_val)
        pw_file = _VMS_DIR / uuid_val / "password"
        assert pw_file.exists()
        pw = pw_file.read_text().strip()
        assert len(pw) == _PASSWORD_LEN
        assert pw.isalnum()

    def test_vm_yaml_stored(
        self,
        temp_config: Path,
        vm_tracker: VMTracker,
        vm_build_capable: None,
    ) -> None:
        result = vm_cmd("create", str(temp_config), timeout=600)
        assert result.returncode == 0
        uuid_val = extract_uuid(result.stdout)
        vm_tracker.register(uuid_val)
        vm_yaml = _VMS_DIR / uuid_val / "vm.yaml"
        assert vm_yaml.exists()
        parsed = yaml.safe_load(vm_yaml.read_text())
        assert "components" in parsed

    def test_dockerfile_generated(
        self,
        temp_config: Path,
        vm_tracker: VMTracker,
        vm_build_capable: None,
    ) -> None:
        result = vm_cmd("create", str(temp_config), timeout=600)
        assert result.returncode == 0
        uuid_val = extract_uuid(result.stdout)
        vm_tracker.register(uuid_val)
        dockerfile = _VMS_DIR / uuid_val / "Dockerfile"
        assert dockerfile.exists()
        assert "FROM ubuntu:22.04" in dockerfile.read_text()

    def test_certs_generated(
        self,
        temp_config: Path,
        vm_tracker: VMTracker,
        vm_build_capable: None,
    ) -> None:
        result = vm_cmd("create", str(temp_config), timeout=600)
        assert result.returncode == 0
        uuid_val = extract_uuid(result.stdout)
        vm_tracker.register(uuid_val)
        cert_dir = _VMS_DIR / uuid_val / "certs"
        for fname in (
            "ca.crt",
            "ca.key",
            "server.crt",
            "server.key",
            "client.crt",
            "client.key",
        ):
            assert (cert_dir / fname).exists(), f"missing cert: {fname}"

    def test_userns_keep_id(
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
            ["podman", "inspect", "-f", "{{.HostConfig.UsernsMode}}", uuid_val],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "keep-id" in inspect.stdout

    def test_default_no_network(
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
            ["podman", "inspect", "-f", "{{.HostConfig.NetworkMode}}", uuid_val],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "none" in inspect.stdout
