"""E2E tests for VM resource limits (requires full build)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

from tests.e2e.conftest import VMTracker, extract_uuid, vm_cmd

pytestmark = pytest.mark.e2e


class TestVMResources:
    def test_default_resources(
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
            ["podman", "inspect", uuid_val],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "4g" in inspect.stdout or "4294967296" in inspect.stdout.lower()
        assert "CPUShares" in inspect.stdout or "NanoCpus" in inspect.stdout

    def test_custom_resources(
        self,
        tmp_path: Path,
        vm_tracker: VMTracker,
        vm_build_capable: None,
    ) -> None:
        config_data = {
            "components": ["opencode"],
            "resources": {"memory": "1g", "cpus": 1, "pids_limit": 64},
        }
        config_file = tmp_path / "custom-res.yaml"
        config_file.write_text(yaml.dump(config_data))

        result = vm_cmd("create", str(config_file), timeout=600)
        assert result.returncode == 0
        uuid_val = extract_uuid(result.stdout)
        vm_tracker.register(uuid_val)

        inspect = subprocess.run(
            ["podman", "inspect", uuid_val],
            capture_output=True,
            text=True,
            check=True,
        )
        inspect_lower = inspect.stdout.lower()
        assert "1073741824" in inspect_lower or "1g" in inspect_lower
