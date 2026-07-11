"""E2E: QEMU backend boots a Linux guest and answers SSH."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from workspace.cli.hypervisor.qemu_backend import QemuBackend
from workspace.cli.hypervisor.qemu_resolve import resolve_qemu_system
from workspace.types.vm import VMConfig

_POC_CONFIG = Path("workspace/config/vm-poc-qemu.yaml")


def _qemu_available() -> bool:
    if not _POC_CONFIG.is_file():
        return False
    cfg = VMConfig.model_validate(yaml.safe_load(_POC_CONFIG.read_text()))
    try:
        resolve_qemu_system(cfg.isolation.qemu.guest_arch, allow_path=True)
    except FileNotFoundError:
        return False
    return shutil.which("cloud-localds") is not None


@pytest.mark.e2e
@pytest.mark.skipif(not _qemu_available(), reason="qemu or cloud-localds not installed")
def test_vm_qemu_boot_uname() -> None:
    """Create POC VM, SSH uname -a, destroy. Mutates .vms/ only."""
    create = subprocess.run(
        [sys.executable, "-m", "workspace.cli.vm_main", "create", str(_POC_CONFIG)],
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    assert create.returncode == 0, create.stderr + create.stdout

    # Parse UUID from create output
    uuid_line = next(
        (
            line
            for line in create.stdout.splitlines()
            if line.startswith("VM ") and "created" in line
        ),
        "",
    )
    assert uuid_line
    uuid = uuid_line.split()[1]
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

    QemuBackend().destroy(uuid)
