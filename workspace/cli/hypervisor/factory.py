"""Hypervisor backend factory for make vm."""

from __future__ import annotations

from workspace.cli.hypervisor.podman_backend import PodmanBackend
from workspace.cli.hypervisor.qemu_backend import QemuBackend
from workspace.types.vm import VMConfig


def get_backend(cfg: VMConfig) -> PodmanBackend | QemuBackend:
    if cfg.isolation.backend == "qemu":
        return QemuBackend()
    return PodmanBackend()
