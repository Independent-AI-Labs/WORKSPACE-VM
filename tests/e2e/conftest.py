"""E2E test fixtures for VM lifecycle tests. Uses lightweight podman containers."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

_SUBPROCESS_ERRORS = (
    FileNotFoundError,
    subprocess.TimeoutExpired,
    subprocess.CalledProcessError,
)

_VM_SCRIPT = Path("workspace/scripts/bin/vm")
_VMS_DIR = Path(".vms")


def _podman_available() -> bool:
    try:
        result = subprocess.run(
            ["podman", "version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
    except _SUBPROCESS_ERRORS:
        return False
    else:
        return "Version:" in result.stdout


def _base_image_cached() -> bool:
    try:
        subprocess.run(
            ["podman", "image", "exists", "ubuntu:22.04"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
    except _SUBPROCESS_ERRORS:
        return False
    else:
        return True


class VMTracker:
    """Track created resources for automatic cleanup.

    Return codes are checked explicitly. Failures print to stderr
    but do not crash the test suite.
    """

    def __init__(self) -> None:
        self.uuids: list[str] = []

    def register(self, uuid_val: str) -> None:
        self.uuids.append(uuid_val)

    def _cleanup_volumes(self, uuid_val: str) -> None:
        for suffix in ("workspace", "transcripts", "cache"):
            subprocess.run(
                ["podman", "volume", "rm", "-f", f"{uuid_val}-{suffix}"],
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )

    def cleanup(self) -> None:
        for uuid_val in self.uuids:
            try:
                subprocess.run(
                    ["podman", "rm", "-f", "-time", "1", uuid_val],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=True,
                )
            except subprocess.CalledProcessError as exc:
                print(
                    f"WARNING: cleanup podman rm failed for {uuid_val}: "
                    f"{exc.stderr.strip() if exc.stderr else exc}",
                    flush=True,
                )
            self._cleanup_volumes(uuid_val)
            try:
                subprocess.run(
                    ["podman", "rmi", "-f", f"ami-vm:{uuid_val}"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=True,
                )
            except subprocess.CalledProcessError as exc:
                print(
                    f"WARNING: cleanup image rm failed for {uuid_val}: "
                    f"{exc.stderr.strip() if exc.stderr else exc}",
                    flush=True,
                )
            vm_path = _VMS_DIR / uuid_val
            if vm_path.exists():
                shutil.rmtree(vm_path, ignore_errors=True)


@pytest.fixture(scope="session")
def podman_available() -> None:
    """Skip e2e suite if podman is not available."""
    if not _podman_available():
        pytest.skip("podman not available - skipping e2e tests")


@pytest.fixture(scope="session")
def vm_build_capable(podman_available) -> None:
    """Skip full-build tests if ubuntu:22.04 image is not cached."""
    if not _base_image_cached():
        pytest.skip("ubuntu:22.04 image not cached - skipping build tests")


@pytest.fixture
def vm_tracker(vm_build_capable) -> VMTracker:
    """Automatic cleanup of VMs created during a test."""
    tracker = VMTracker()
    yield tracker
    tracker.cleanup()


# Lightweight test VM (no podman build, fast)


def _fake_uuid() -> str:
    """Deterministic fake UUID for lightweight test VMs."""
    ts = int(os.times().elapsed * 1000)
    return f"test-{ts:x}"


@pytest.fixture
def test_vm(podman_available, vm_tracker: VMTracker) -> str:
    """Create a lightweight test VM using podman run (no build).

    Bootstraps a container with ubuntu:22.04 sleep infinity,
    fakes .vms/<uuid>/ directory with pid and vm.yaml,
    and registers it for automatic cleanup.
    """
    uuid_val = _fake_uuid()
    vm_tracker.register(uuid_val)

    vm_dir = _VMS_DIR / uuid_val
    vm_dir.mkdir(parents=True, exist_ok=True)

    config_data = {"components": ["opencode"]}
    (vm_dir / "vm.yaml").write_text(yaml.dump(config_data))

    subprocess.run(
        [
            "podman",
            "run",
            "-d",
            "-name",
            uuid_val,
            "-label",
            "ami.type=vm",
            "-label",
            f"ami.uuid={uuid_val}",
            "-label",
            f"ami.config={hashlib.sha256(b'fake').hexdigest()[:16]}",
            "-v",
            f"{uuid_val}-workspace:/workspace",
            "-v",
            f"{uuid_val}-transcripts:/transcripts",
            "-v",
            f"{uuid_val}-cache:/cache",
            "-userns=keep-id",
            "-memory",
            "1g",
            "-cpus",
            "1",
            "-pids-limit",
            "64",
            "ubuntu:22.04",
            "sleep",
            "infinity",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )

    pid_result = subprocess.run(
        ["podman", "inspect", "-f", "{{.State.Pid}}", uuid_val],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    (vm_dir / "pid").write_text(pid_result.stdout.strip())

    return uuid_val


@pytest.fixture
def temp_config(tmp_path: Path) -> Path:
    """Write a minimal VM config to a temporary file."""
    config_data = {"components": ["opencode"]}
    config_file = tmp_path / "vm-config.yaml"
    config_file.write_text(yaml.dump(config_data))
    return config_file


def vm_cmd(*args: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    """Run a vm subcommand and return the result.

    Uses check=False because callers must inspect returncode -
    many tests assert non-zero exit for error cases.
    """
    return subprocess.run(
        ["bash", str(_VM_SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def extract_uuid(output: str) -> str:
    for line in output.strip().splitlines():
        stripped = line.strip()
        if stripped.startswith("UUID:"):
            return stripped.split(":", 1)[1].strip()
    return ""
