"""E2E: full install-ci inside QEMU guest disk."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.e2e.qemu_availability import qemu_e2e_available
from tests.e2e.qemu_cleanup import QemuTracker, run_vm_create
from workspace.cli.hypervisor.qemu_backend import QemuBackend
from workspace.types.vm import VM_INSTALL_ROOT

_FULL_CI_CONFIG = Path("workspace/config/vm-full-ci-qemu.yaml")
_CREATE_TIMEOUT = 3600

_ESSENTIAL_BINARIES = [
    ("uv", f"{VM_INSTALL_ROOT}/.boot-linux/bin/uv"),
    ("python3", f"{VM_INSTALL_ROOT}/.boot-linux/bin/python3"),
    ("node", f"{VM_INSTALL_ROOT}/projects/CI/.boot-linux/bin/node"),
    ("opencode", f"{VM_INSTALL_ROOT}/.boot-linux/bin/opencode"),
]


@pytest.mark.e2e
@pytest.mark.skipif(
    not qemu_e2e_available(_FULL_CI_CONFIG),
    reason="qemu or genisoimage not installed",
)
def test_vm_qemu_full_ci_provision(qemu_tracker: QemuTracker) -> None:
    """Create full-ci QEMU VM, verify binaries, always destroy guest overlay."""
    create = run_vm_create(
        _FULL_CI_CONFIG, timeout=_CREATE_TIMEOUT, tracker=qemu_tracker
    )
    assert create.returncode == 0, create.stderr + create.stdout

    uuid = qemu_tracker.uuids[-1]
    backend = QemuBackend()
    for name, path in _ESSENTIAL_BINARIES:
        probe = backend.exec(uuid, ["test", "-x", path])
        assert probe.returncode == 0, f"missing {name} at {path}"

    uname = backend.exec(uuid, ["uname", "-a"])
    assert "Linux" in uname.stdout
