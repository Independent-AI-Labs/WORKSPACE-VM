"""Unit tests for QEMU workspace sync."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from workspace.cli import qemu_sync, vm_lifecycle


def _prepare(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, strategy: str
) -> list[list[str]]:
    vms = tmp_path / "vms"
    vm_dir = vms / "vm-uuid"
    vm_dir.mkdir(parents=True)
    source = tmp_path / "source"
    source.mkdir()
    config = {
        "components": ["uv"],
        "isolation": {"backend": "qemu"},
        "sync": [{"dir": str(source), "strategy": strategy}],
    }
    (vm_dir / "vm.yaml").write_text(yaml.dump(config))
    (vm_dir / "ssh_port").write_text("55222")
    (vm_dir / "qemu_ssh_ed25519").write_text("key")
    monkeypatch.setattr(qemu_sync, "_VMS_DIR", vms)
    monkeypatch.setattr(vm_lifecycle, "_VMS_DIR", vms)
    calls: list[list[str]] = []

    def _run(cmd: list[str], **_kwargs: object) -> object:
        calls.append(cmd)
        return MagicMock(returncode=0)

    monkeypatch.setattr(qemu_sync.subprocess, "run", _run)
    return calls


def test_sync_overwrite_adds_delete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    calls = _prepare(tmp_path, monkeypatch, "overwrite")
    qemu_sync.sync("vm-uuid")
    assert "--delete" in calls[0]
    assert "synced 1 directory" in capsys.readouterr().out


def test_sync_skip_adds_ignore_existing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _prepare(tmp_path, monkeypatch, "skip")
    qemu_sync.sync("vm-uuid")
    assert "--ignore-existing" in calls[0]


def test_sync_requires_qemu(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vms = tmp_path / "vms"
    vm_dir = vms / "vm-uuid"
    vm_dir.mkdir(parents=True)
    (vm_dir / "vm.yaml").write_text(yaml.dump({"components": ["uv"]}))
    monkeypatch.setattr(qemu_sync, "_VMS_DIR", vms)
    monkeypatch.setattr(vm_lifecycle, "_VMS_DIR", vms)
    with pytest.raises(ValueError, match="qemu"):
        qemu_sync.sync("vm-uuid")
