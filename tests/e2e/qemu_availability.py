"""Shared QEMU E2E prerequisite checks."""

from __future__ import annotations

from pathlib import Path

import yaml

from workspace.cli.hypervisor.qemu_images import _resolve_genisoimage
from workspace.cli.hypervisor.qemu_resolve import resolve_qemu_system
from workspace.types.vm import VMConfig


def qemu_e2e_available(config_path: Path) -> bool:
    """Return True when config exists and QEMU toolchain is bootstrapped."""
    if not config_path.is_file():
        return False
    cfg = VMConfig.model_validate(yaml.safe_load(config_path.read_text()))
    if cfg.isolation.backend != "qemu":
        return False
    try:
        resolve_qemu_system(cfg.isolation.qemu.guest_arch, allow_path=True)
        _resolve_genisoimage()
    except FileNotFoundError:
        return False
    return True
