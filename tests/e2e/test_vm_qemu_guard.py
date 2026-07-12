"""E2E: WORKSPACE-GUARD authoritative gate inside QEMU guest."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.e2e.qemu_availability import qemu_e2e_available
from tests.e2e.qemu_cleanup import QemuTracker, run_vm_create
from tests.e2e.qemu_host_isolation import assert_host_git_unchanged, snapshot_host_git
from workspace.cli import process as proc

_GUARD_CONFIG = Path("workspace/config/vm-guard-qemu.yaml")
_E2E_GUEST = Path("projects/WORKSPACE-GUARD/scripts/qemu/e2e-guest.sh")
_CREATE_TIMEOUT = 3600
_GUARD_TIMEOUT = 1800


def _qemu_guard_available() -> bool:
    return _E2E_GUEST.is_file() and qemu_e2e_available(_GUARD_CONFIG)


@pytest.mark.e2e
@pytest.mark.skipif(
    not _qemu_guard_available(),
    reason="qemu, genisoimage, or guard config not available",
)
def test_vm_qemu_guard_e2e_guest(qemu_tracker: QemuTracker) -> None:
    """Provision guard VM, run e2e-guest.sh, verify host git unchanged."""
    before = snapshot_host_git()

    create = run_vm_create(_GUARD_CONFIG, timeout=_CREATE_TIMEOUT, tracker=qemu_tracker)
    assert create.returncode == 0, create.stderr + create.stdout

    uuid = qemu_tracker.uuids[-1]
    vm_dir = Path(".vms") / uuid
    port = int((vm_dir / "ssh_port").read_text().strip())
    key = vm_dir / "qemu_ssh_ed25519"

    guard = proc.run(
        [
            "ssh",
            "-i",
            str(key),
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-p",
            str(port),
            "workspace@127.0.0.1",
            "sudo",
            "bash",
            "/opt/workspace/projects/WORKSPACE-GUARD/scripts/qemu/e2e-guest.sh",
        ],
        capture_output=True,
        text=True,
        timeout=_GUARD_TIMEOUT,
    )
    assert "PASS:" in guard.stdout

    after = snapshot_host_git()
    assert_host_git_unchanged(before, after)
