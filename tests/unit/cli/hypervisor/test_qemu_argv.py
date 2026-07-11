"""Unit tests for qemu_argv builder."""

from __future__ import annotations

from pathlib import Path

from workspace.cli.hypervisor.qemu_argv import (
    QemuLaunchContext,
    build_qemu_argv,
    parse_memory_mb,
)
from workspace.types.vm import VMConfig

_FOUR_GB_MB = 4096
_HALF_GB_MB = 512
_SSH_PORT = 55222


def test_parse_memory_mb() -> None:
    assert parse_memory_mb("4g") == _FOUR_GB_MB
    assert parse_memory_mb("512m") == _HALF_GB_MB


def test_build_qemu_argv_aarch64() -> None:
    cfg = VMConfig.model_validate(
        {
            "components": ["uv"],
            "resources": {"memory": "2g", "cpus": 2},
            "isolation": {"backend": "qemu", "qemu": {"guest_arch": "aarch64"}},
        }
    )
    vm_dir = Path("/tmp/vm-test")
    launch = QemuLaunchContext(
        qemu_bin=Path("/opt/qemu-system-aarch64"),
        accel="tcg",
        ssh_port=_SSH_PORT,
        firmware=Path("/opt/QEMU_EFI.fd"),
    )
    argv = build_qemu_argv(cfg=cfg, vm_dir=vm_dir, launch=launch)
    assert argv[0] == "/opt/qemu-system-aarch64"
    assert "-accel" in argv
    assert "tcg" in argv
    assert "-bios" in argv
    assert f"hostfwd=tcp:127.0.0.1:{_SSH_PORT}-:22" in " ".join(argv)
