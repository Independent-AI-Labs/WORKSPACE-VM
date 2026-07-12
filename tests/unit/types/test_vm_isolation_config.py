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

    def test_image_defaults_match_guest_arch(self) -> None:
        arm = VMQemuConfig(guest_arch="aarch64")
        assert arm.image.endswith("aarch64.qcow2")
        x86 = VMQemuConfig(guest_arch="x86_64")
        assert x86.image.endswith("x86_64.qcow2")

    def test_provision_profile(self) -> None:
        cfg = VMQemuConfig(provision="full-ci")
        assert cfg.provision == "full-ci"


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
