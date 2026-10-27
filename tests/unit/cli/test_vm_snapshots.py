"""Unit tests for QEMU snapshot, export, and import operations."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from workspace.cli import vm_lifecycle, vm_snapshots


def _prepare(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    vms = tmp_path / "vms"
    vm_dir = vms / "vm-uuid"
    vm_dir.mkdir(parents=True)
    (vm_dir / "vm.yaml").write_text(
        yaml.dump({"components": ["uv"], "isolation": {"backend": "qemu"}})
    )
    (vm_dir / "disk.qcow2").write_bytes(b"disk")
    (vm_dir / "state.yaml").write_text("{}\n")
    monkeypatch.setattr(vm_snapshots, "_VMS_DIR", vms)
    monkeypatch.setattr(vm_lifecycle, "_VMS_DIR", vms)
    monkeypatch.setattr(
        vm_snapshots,
        "get_backend",
        MagicMock(return_value=MagicMock(stop=MagicMock())),
    )
    monkeypatch.setattr(
        vm_snapshots,
        "_run_qemu_img",
        MagicMock(return_value=subprocess.CompletedProcess("qemu-img", 0, "", "")),
    )
    return vm_dir


def test_snapshot_create_calls_qemu_img(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(tmp_path, monkeypatch)
    vm_snapshots.snapshot_create("vm-uuid", "before")
    vm_snapshots._run_qemu_img.assert_called_once()
    assert vm_snapshots._run_qemu_img.call_args.args[:2] == ("snapshot", "-c")


def test_snapshot_delete_calls_qemu_img(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(tmp_path, monkeypatch)
    vm_snapshots.snapshot_delete("vm-uuid", "before")
    assert vm_snapshots._run_qemu_img.call_args.args[:2] == ("snapshot", "-d")


def test_snapshot_list_prints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    _prepare(tmp_path, monkeypatch)
    vm_snapshots._run_qemu_img.return_value = subprocess.CompletedProcess(
        "qemu-img", 0, "ID NAME\n", ""
    )
    vm_snapshots.snapshot_list("vm-uuid")
    assert "NAME" in capsys.readouterr().out


def test_export_and_import_roundtrip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(tmp_path, monkeypatch)
    backup = tmp_path / "bundle"
    vm_snapshots.export_vm("vm-uuid", backup)
    assert (backup / "manifest.json").is_file()
    manifest = json.loads((backup / "manifest.json").read_text())
    assert manifest["source_uuid"] == "vm-uuid"

    monkeypatch.setattr(vm_snapshots, "uuid7", lambda: "new-uuid")
    imported = vm_snapshots.import_vm(backup)
    assert imported == "new-uuid"
    assert (tmp_path / "vms" / "new-uuid" / "disk.qcow2").is_file()


def test_export_rejects_existing_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(tmp_path, monkeypatch)
    destination = tmp_path / "bundle"
    destination.mkdir()
    with pytest.raises(FileExistsError):
        vm_snapshots.export_vm("vm-uuid", destination)


def test_import_rejects_missing_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(tmp_path, monkeypatch)
    with pytest.raises(FileNotFoundError, match="manifest"):
        vm_snapshots.import_vm(tmp_path / "bundle")


def test_require_qemu_rejects_other_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = MagicMock()
    cfg.isolation.backend = "podman"
    monkeypatch.setattr(vm_snapshots, "load_vm_config", lambda _uuid: cfg)
    with pytest.raises(ValueError, match="require the qemu backend"):
        vm_snapshots._require_qemu("vm-uuid")


def test_run_qemu_img_reports_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(vm_snapshots, "resolve_qemu_img", lambda: tmp_path / "qemu-img")
    monkeypatch.setattr(
        vm_snapshots.subprocess,
        "run",
        MagicMock(
            side_effect=subprocess.CalledProcessError(1, "qemu-img", stderr="boom")
        ),
    )
    with pytest.raises(RuntimeError, match="qemu-img failed: boom"):
        vm_snapshots._run_qemu_img("info", "disk.qcow2")


def test_import_rejects_unknown_format(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "manifest.json").write_text(json.dumps({"format": 999}))
    with pytest.raises(ValueError, match="unsupported import format"):
        vm_snapshots.import_vm(bundle)


def test_import_rejects_missing_disk(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "manifest.json").write_text(json.dumps({"format": 1}))
    (bundle / "vm.yaml").write_text("components: [uv]\n")
    with pytest.raises(FileNotFoundError, match="missing disk or config"):
        vm_snapshots.import_vm(bundle)
