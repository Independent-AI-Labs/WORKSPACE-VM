"""E2E test: full VM creation with CI loadout (all default components).

This test builds a VM with the complete install-defaults.yaml component list
(13 tools + 3 workspace repos) and verifies the container is functional.
Requires ubuntu:22.04 cached and 30+ minutes to complete.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

from tests.e2e.conftest import VMTracker, extract_uuid, vm_cmd

pytestmark = pytest.mark.e2e

_FULL_CI_COMPONENTS = [
    "uv",
    "python",
    "node",
    "opencode",
    "podman",
    "gh",
    "go",
    "cloudflared",
    "playwright",
    "pandoc",
    "texlive",
    "adb",
    "ansible",
]

_ESSENTIAL_BINARIES = [
    ("uv", "/opt/ami-agents/.boot-linux/bin/uv"),
    ("python3", "/opt/ami-agents/.boot-linux/bin/python3"),
    ("node", "/opt/ami-agents/.boot-linux/bin/node"),
    ("opencode", "/opt/ami-agents/.boot-linux/bin/opencode"),
    ("git", "/usr/bin/git"),
]

_BUILD_TIMEOUT = 3600


class TestVMCreateFullCI:
    """Build a VM with all install-defaults.yaml components."""

    def test_full_ci_build_and_verify(
        self,
        tmp_path: Path,
        vm_tracker: VMTracker,
        vm_build_capable: None,
    ) -> None:
        config_data = {
            "components": _FULL_CI_COMPONENTS,
            "resources": {"memory": "8g", "cpus": 4, "pids_limit": 512},
            "security": {"read_only_rootfs": False},
        }
        config_file = tmp_path / "full-ci.yaml"
        config_file.write_text(yaml.dump(config_data))

        result = vm_cmd("create", str(config_file), timeout=_BUILD_TIMEOUT)
        assert result.returncode == 0, f"full CI build failed:\n{result.stderr[-2000:]}"
        uuid_val = extract_uuid(result.stdout)
        assert uuid_val, "could not extract UUID from output"
        vm_tracker.register(uuid_val)

        # Verify container is running
        running = subprocess.run(
            ["podman", "inspect", "-f", "{{.State.Running}}", uuid_val],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        assert running.stdout.strip() == "true"

        # Verify essential installed binaries exist
        for _name, path in _ESSENTIAL_BINARIES:
            check = vm_cmd("exec", uuid_val, "--", "test", "-f", path)
            assert check.returncode == 0, (
                f"missing binary at {path}:\n{check.stderr[-500:]}"
            )

        # Verify make targets work (init was already run)
        verify = vm_cmd(
            "exec",
            uuid_val,
            "--",
            "test",
            "-d",
            "/opt/ami-agents/.boot-linux",
        )
        assert verify.returncode == 0, ".boot-linux directory not found"
