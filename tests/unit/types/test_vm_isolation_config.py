"""Unit tests for VM isolation / QEMU schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from workspace.types.vm import VMConfig, VMIsolationConfig, VMQemuConfig

_DEFAULT_DISK_GB = 20
_FIXED_SSH_PORT = 55222


class TestVMIsolationConfig:
    def test_defaults_podman(self) -> None:
        iso = VMIsolationConfig()
        assert iso.backend == "podman"

    def test_qemu_backend(self) -> None:
        iso = VMIsolationConfig(backend="qemu")
        assert iso.backend == "qemu"
        assert iso.qemu.disk_gb == _DEFAULT_DISK_GB

    def test_disk_gb_bounds(self) -> None:
        with pytest.raises(ValidationError):
            VMQemuConfig(disk_gb=4)


class TestVMConfigIsolation:
    def test_minimal_includes_isolation(self) -> None:
        cfg = VMConfig.model_validate({"components": ["uv"]})
        assert cfg.isolation.backend == "podman"

    def test_qemu_block(self) -> None:
        cfg = VMConfig.model_validate(
            {
                "components": ["uv"],
                "isolation": {
                    "backend": "qemu",
                    "qemu": {
                        "guest_arch": "aarch64",
                        "accel": "tcg",
                        "disk_gb": 16,
                        "ssh_host_port": _FIXED_SSH_PORT,
                    },
                },
            }
        )
        assert cfg.isolation.backend == "qemu"
        assert cfg.isolation.qemu.accel == "tcg"
        assert cfg.isolation.qemu.ssh_host_port == _FIXED_SSH_PORT
