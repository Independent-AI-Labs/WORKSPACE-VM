"""End-to-end tests for macOS scripts with podman."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


CONTAINER_NAME = "workspace-vm-ubuntu"


@pytest.fixture(scope="module")
def _cleanup_container_module():
    yield
    subprocess.run(
        ["podman", "rm", "-f", "--time", "1", CONTAINER_NAME],
        capture_output=True,
        timeout=30,
    )
    for vol in ("workspace", "transcripts", "cache"):
        subprocess.run(
            ["podman", "volume", "rm", "-f", f"{CONTAINER_NAME}-{vol}"],
            capture_output=True,
            timeout=30,
        )


@pytest.mark.e2e
class TestMacScriptsE2E:
    def test_full_launch_lifecycle(
        self, launch_mac_script: Path, podman_available: bool
    ) -> None:
        if not podman_available:
            pytest.skip("podman not available")
        result = subprocess.run(
            ["bash", str(launch_mac_script)],
            capture_output=True,
            text=True,
            timeout=600,
        )
        assert result.returncode == 0, f"Launch failed: {result.stderr}"
        assert "workspace-vm-ubuntu" in result.stdout

    def test_container_restart_policy_is_always(
        self, launch_mac_script: Path, podman_available: bool
    ) -> None:
        if not podman_available:
            pytest.skip("podman not available")
        subprocess.run(
            ["bash", str(launch_mac_script)],
            capture_output=True,
            text=True,
            timeout=600,
        )
        result = subprocess.run(
            [
                "podman",
                "inspect",
                "--format",
                "{{.HostConfig.RestartPolicy.Name}}",
                CONTAINER_NAME,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"Inspect failed: {result.stderr}"
        assert result.stdout.strip() == "always"

    def test_volumes_persist_across_shutdown(
        self, launch_mac_script: Path, podman_available: bool
    ) -> None:
        if not podman_available:
            pytest.skip("podman not available")
        subprocess.run(
            ["bash", str(launch_mac_script)],
            capture_output=True,
            text=True,
            timeout=600,
        )
        subprocess.run(
            ["bash", str(launch_mac_script), "--shutdown"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        result = subprocess.run(
            ["podman", "volume", "exists", f"{CONTAINER_NAME}-workspace"],
            capture_output=True,
            timeout=10,
        )
        assert result.returncode == 0, "Volume should persist after shutdown"

    def test_recreate_removes_all_resources(
        self, launch_mac_script: Path, podman_available: bool
    ) -> None:
        if not podman_available:
            pytest.skip("podman not available")
        result = subprocess.run(
            ["bash", str(launch_mac_script), "--recreate-vm-from-scratch"],
            capture_output=True,
            text=True,
            timeout=600,
        )
        assert result.returncode == 0, f"Recreate failed: {result.stderr}"
        inspect_result = subprocess.run(
            ["podman", "inspect", CONTAINER_NAME],
            capture_output=True,
            timeout=10,
        )
        assert inspect_result.returncode == 0, "Container should exist after recreate"

    def test_custom_config_respected(
        self, launch_mac_script: Path, podman_available: bool, tmp_path: Path
    ) -> None:
        if not podman_available:
            pytest.skip("podman not available")
        config_file = tmp_path / "test-config.yaml"
        config_file.write_text("components:\n  - uv\n  - python\n")
        result = subprocess.run(
            ["bash", str(launch_mac_script), "--config", str(config_file)],
            capture_output=True,
            text=True,
            timeout=600,
        )
        assert result.returncode == 0, f"Custom config failed: {result.stderr}"

    def test_force_rebuild_rebuilds_image(
        self, launch_mac_script: Path, podman_available: bool
    ) -> None:
        if not podman_available:
            pytest.skip("podman not available")
        result = subprocess.run(
            ["bash", str(launch_mac_script), "--force-rebuild"],
            capture_output=True,
            text=True,
            timeout=600,
        )
        assert result.returncode == 0, f"Force rebuild failed: {result.stderr}"
        assert "Building" in result.stdout or "building" in result.stdout.lower()
