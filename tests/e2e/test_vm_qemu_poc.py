"""E2E: QEMU backend boots a Linux guest and answers SSH."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.e2e.qemu_availability import qemu_e2e_available
from tests.e2e.qemu_cleanup import QemuTracker, run_vm_create

_POC_CONFIG = Path("workspace/config/vm-poc-qemu.yaml")
_CREATE_TIMEOUT = 900


@pytest.mark.e2e
@pytest.mark.skipif(
    not qemu_e2e_available(_POC_CONFIG),
    reason="qemu or genisoimage not installed",
)
def test_vm_qemu_boot_uname(qemu_tracker: QemuTracker) -> None:
    """Create POC VM, SSH uname -a, always destroy overlay (keeps _base/ cache)."""
    create = run_vm_create(_POC_CONFIG, timeout=_CREATE_TIMEOUT, tracker=qemu_tracker)
    assert create.returncode == 0, create.stderr + create.stdout

    uuid = qemu_tracker.uuids[-1]
    vm_dir = Path(".vms") / uuid
    port = int((vm_dir / "ssh_port").read_text().strip())
    key = vm_dir / "qemu_ssh_ed25519"

    probe = subprocess.run(
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
            "uname",
            "-a",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    assert "Linux" in probe.stdout
