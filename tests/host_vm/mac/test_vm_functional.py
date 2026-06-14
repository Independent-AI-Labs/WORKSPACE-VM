"""End-to-end test: run pytest suite inside the VM container."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


CONTAINER_NAME = "workspace-vm-ubuntu"
IMAGE_NAME = "workspace-vm-ubuntu:latest"
TEST_TIMEOUT = 1800


def _container_running() -> bool:
    try:
        result = subprocess.run(
            ["podman", "inspect", "-f", "{{.State.Running}}", CONTAINER_NAME],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        return result.stdout.strip() == "true"
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _cleanup_container() -> None:
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


def _ensure_container(launch_mac_script: Path) -> None:
    if _container_running():
        return
    result = subprocess.run(
        ["bash", str(launch_mac_script)],
        capture_output=True,
        text=True,
        timeout=1200,
    )
    if result.returncode != 0:
        _cleanup_container()
        pytest.fail(f"Failed to launch container: {result.stderr}")


def _run_pytest_in_container(test_path: str, timeout: int = TEST_TIMEOUT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "podman", "exec",
            CONTAINER_NAME,
            "bash", "-c",
            f"cd /opt/workspace && .venv/bin/pytest {test_path} -v --tb=short",
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


@pytest.fixture(scope="module")
def vm_container(launch_mac_script: Path, podman_available: bool):
    if not podman_available:
        pytest.skip("podman not available")
    
    container_was_running = _container_running()
    try:
        _ensure_container(launch_mac_script)
        yield CONTAINER_NAME
    finally:
        if not container_was_running:
            _cleanup_container()


@pytest.mark.e2e
@pytest.mark.timeout(1200)
class TestVMFunctional:
    def test_container_can_run_basic_commands(self, vm_container: str) -> None:
        result = subprocess.run(
            ["podman", "exec", CONTAINER_NAME, "bash", "-c", "echo 'hello' && pwd"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"Container cannot run basic commands: {result.stderr}"
        assert "hello" in result.stdout

    def test_opencode_service_running(self, vm_container: str) -> None:
        result = subprocess.run(
            ["podman", "exec", CONTAINER_NAME, "systemctl", "is-active", "opencode.service"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"opencode service not active: {result.stdout}"
        assert result.stdout.strip() == "active"

    def test_essential_binaries_exist_inside_container(self, vm_container: str) -> None:
        binaries = [
            "/opt/workspace/.boot-linux/bin/uv",
            "/opt/workspace/.boot-linux/bin/python",
            "/usr/bin/git",
        ]
        for binary in binaries:
            result = subprocess.run(
                ["podman", "exec", CONTAINER_NAME, "test", "-x", binary],
                capture_output=True,
                timeout=10,
            )
            assert result.returncode == 0, f"Binary not found: {binary}"

    def test_workspace_volumes_mounted(self, vm_container: str) -> None:
        for mount_point in ("/workspace", "/transcripts", "/cache"):
            result = subprocess.run(
                ["podman", "exec", CONTAINER_NAME, "test", "-d", mount_point],
                capture_output=True,
                timeout=10,
            )
            assert result.returncode == 0, f"Mount point missing: {mount_point}"
