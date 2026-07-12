"""Integration checks for QEMU hypervisor modules."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from workspace.cli import process as proc
from workspace.cli import vm_lifecycle, vm_manager
from workspace.cli.hypervisor import qemu_backend as qb
from workspace.cli.hypervisor import qemu_images as qi
from workspace.cli.hypervisor import qemu_provision as qp
from workspace.cli.hypervisor import qemu_resolve as qr
from workspace.cli.hypervisor.factory import get_backend
from workspace.cli.hypervisor.qemu_argv import QemuLaunchContext, build_qemu_argv
from workspace.types.vm import VMConfig

_TEST_SSH_PORT = 55111


def test_get_backend_qemu() -> None:
    cfg = VMConfig.model_validate(
        {"components": ["uv"], "isolation": {"backend": "qemu"}}
    )
    assert get_backend(cfg).backend_name() == "qemu"


def test_get_backend_podman() -> None:
    cfg = VMConfig.model_validate(
        {"components": ["uv"], "isolation": {"backend": "podman"}}
    )
    assert get_backend(cfg).backend_name() == "podman"


def test_build_qemu_argv_smoke() -> None:
    cfg = VMConfig.model_validate(
        {
            "components": ["uv"],
            "isolation": {"backend": "qemu", "qemu": {"guest_arch": "aarch64"}},
        }
    )
    launch = QemuLaunchContext(
        qemu_bin=Path("/opt/qemu-system-aarch64"),
        accel="tcg",
        ssh_port=55222,
    )
    argv = build_qemu_argv(cfg=cfg, vm_dir=Path("/tmp/vm"), launch=launch)
    assert "-accel" in argv


def test_process_run_ok_integration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        proc.subprocess,
        "run",
        MagicMock(return_value=subprocess.CompletedProcess(["true"], 0, "", "")),
    )
    assert proc.run_ok(["true"]) is True


def test_process_run_result_integration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        proc.subprocess,
        "run",
        MagicMock(side_effect=subprocess.CalledProcessError(1, "false")),
    )
    result = proc.run_result(["false"])
    assert result.returncode == 1


def test_qemu_resolve_probe_integration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(qr.proc, "run_ok", lambda *_a, **_k: True)
    assert qr.probe_accel(Path("/opt/qemu"), "tcg") is True


def test_qemu_images_allocate_port() -> None:
    assert qi.allocate_ssh_port(_TEST_SSH_PORT) == _TEST_SSH_PORT


def test_qemu_write_cloud_init_integration(tmp_path: Path) -> None:
    vm_dir = tmp_path / "vm"
    qi.write_cloud_init(vm_dir, "ssh-ed25519 AAA", mount_workspace=True)
    assert (vm_dir / "cloud-init" / "seed.img").is_file()


def test_qemu_provision_scripts_integration() -> None:
    assert "make install-ci" in qp._build_install_script("full-ci", [])
    assert "rsync" in qp._build_rsync_script("full-ci")


def test_qemu_backend_status_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(qb, "_VMS_DIR", tmp_path)
    assert qb.QemuBackend().status("nope")["state"] == "unknown"


def test_vm_lifecycle_list_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.setattr(vm_lifecycle, "_VMS_DIR", tmp_path / "missing")
    vm_lifecycle.list_vms()
    assert "No VMs found" in capsys.readouterr().out


def test_qemu_images_load_pins() -> None:
    pins = qi._load_pins()
    assert pins.images is not None


def test_qemu_resolve_workspace_boot_dir() -> None:
    boot = qr.workspace_boot_dir()
    assert boot.name in (".boot-macos", ".boot-linux")


def test_vm_manager_create_delegates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg_path = tmp_path / "vm.yaml"
    cfg_path.write_text(
        yaml.dump({"components": ["uv"], "isolation": {"backend": "qemu"}})
    )
    backend = MagicMock()
    monkeypatch.setattr(vm_manager, "get_backend", lambda _cfg: backend)
    vm_manager.create(str(cfg_path))
    backend.create.assert_called_once()


def test_vm_manager_rebuild_qemu_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vms = tmp_path / ".vms"
    vm_dir = vms / "qemu-uuid"
    vm_dir.mkdir(parents=True)
    (vm_dir / "vm.yaml").write_text(
        yaml.dump({"components": ["uv"], "isolation": {"backend": "qemu"}})
    )
    monkeypatch.setattr(vm_manager, "_VMS_DIR", vms)
    monkeypatch.setattr(
        vm_manager.sys,
        "exit",
        lambda code: (_ for _ in ()).throw(SystemExit(code)),
    )
    with pytest.raises(SystemExit):
        vm_manager.rebuild("qemu-uuid")


def test_vm_config_qemu_provision_profiles() -> None:
    for profile in ("none", "guard", "full-ci"):
        cfg = VMConfig.model_validate(
            {
                "components": ["uv"],
                "isolation": {
                    "backend": "qemu",
                    "qemu": {"guest_arch": "aarch64", "provision": profile},
                },
            }
        )
        assert cfg.isolation.qemu.provision == profile
