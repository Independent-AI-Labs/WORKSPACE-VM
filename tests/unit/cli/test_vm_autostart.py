"""Unit tests for QEMU systemd user autostart."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from workspace.cli import vm_autostart
from workspace.cli.hypervisor.qemu_state import ensure_state


def _prepare(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    vms = tmp_path / "vms"
    vm_dir = vms / "vm-uuid"
    vm_dir.mkdir(parents=True)
    (vm_dir / "vm.yaml").write_text(
        yaml.dump({"components": ["uv"], "isolation": {"backend": "qemu"}})
    )
    unit_dir = tmp_path / "units"
    monkeypatch.setattr(vm_autostart, "_VMS_DIR", vms)
    monkeypatch.setattr(vm_autostart, "_UNIT_DIR", unit_dir)
    monkeypatch.setattr(vm_autostart, "find_workspace_root", lambda: tmp_path / "ws")
    monkeypatch.setattr(vm_autostart, "require_systemd", lambda: None)
    monkeypatch.setattr(vm_autostart, "_systemctl", MagicMock())
    ensure_state(vm_dir, profile="none", mode="persistent")
    return vm_dir


def test_enable_writes_unit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _prepare(tmp_path, monkeypatch)
    vm_autostart.enable("vm-uuid")
    unit = tmp_path / "units" / "workspace-vm-vm-uuid.service"
    assert unit.is_file()
    assert "ExecStart=" in unit.read_text()
    assert "ExecStop=" in unit.read_text()


def test_disable_removes_unit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _prepare(tmp_path, monkeypatch)
    vm_autostart.enable("vm-uuid")
    vm_autostart.disable("vm-uuid")
    assert not (tmp_path / "units" / "workspace-vm-vm-uuid.service").exists()


def test_enable_rejects_ephemeral(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vm_dir = _prepare(tmp_path, monkeypatch)
    ensure_state(vm_dir, profile="none", mode="persistent")
    (vm_dir / "state.yaml").write_text(
        '{"mode": "ephemeral", "created_at": "2026-10-23T00:00:00Z"}\n'
    )
    with pytest.raises(ValueError, match="persistent"):
        vm_autostart.enable("vm-uuid")


def test_disable_missing_unit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _prepare(tmp_path, monkeypatch)
    with pytest.raises(FileNotFoundError):
        vm_autostart.disable("vm-uuid")
