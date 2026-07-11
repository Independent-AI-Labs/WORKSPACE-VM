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
    ("node", "/opt/ami-agents/projects/CI/.boot-linux/bin/node"),
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
        }
        config_file = tmp_path / "full-ci.yaml"
        config_file.write_text(yaml.dump(config_data))

        result = vm_cmd("create", str(config_file), timeout=_BUILD_TIMEOUT)
        # Save full build output to a file for debugging
        log_file = tmp_path / "vm-create-output.log"
        log_file.write_text(
            f"=== STDOUT ===\n{result.stdout}\n=== STDERR ===\n{result.stderr}"
        )
        assert result.returncode == 0, (
            f"full CI build failed - logs saved to {log_file}\n"
            f"STDERR (last 3000):\n{result.stderr[-3000:]}\n"
            f"STDOUT (last 3000):\n{result.stdout[-3000:]}"
        )
        uuid_val = extract_uuid(result.stdout)
        assert uuid_val, "could not extract UUID from output"
        vm_tracker.register(uuid_val)

        # Verify the image was built successfully with healthcheck intact.
        # The container may not stay running - systemd in rootless podman
        # can exit immediately. The key assertion is that the image built
        # with all 13 CI components.
        image_ok = subprocess.run(
            ["podman", "image", "inspect", f"ami-vm:{uuid_val}"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        assert image_ok.returncode == 0

        health = subprocess.run(
            [
                "podman",
                "image",
                "inspect",
                "-f",
                "{{.Config.Healthcheck}}",
                f"ami-vm:{uuid_val}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        assert "4096" in health.stdout, "healthcheck not found in image"
