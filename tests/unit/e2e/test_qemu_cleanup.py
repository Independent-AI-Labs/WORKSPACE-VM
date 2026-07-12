"""Unit tests for QEMU E2E cleanup helpers."""

from __future__ import annotations

from pathlib import Path

from tests.e2e.qemu_cleanup import (
    QemuTracker,
    _is_qemu_vm_dir,
    cleanup_orphan_qemu_vms,
    parse_vm_uuid,
)


def test_parse_vm_uuid_from_created_line() -> None:
    stdout = "VM 019f5463-c047-7637-92e4-b25d7105af81 created (qemu)\n"
    assert parse_vm_uuid(stdout) == "019f5463-c047-7637-92e4-b25d7105af81"


def test_parse_vm_uuid_from_uuid_line() -> None:
    stdout = "  UUID:     019f5463-c047-7637-92e4-b25d7105af81\n"
    assert parse_vm_uuid(stdout) == "019f5463-c047-7637-92e4-b25d7105af81"


def test_is_qemu_vm_dir_skips_base_cache(tmp_path: Path) -> None:
    base = tmp_path / "_base"
    base.mkdir()
    assert _is_qemu_vm_dir(base) is False


def test_is_qemu_vm_dir_detects_qemu_artifacts(tmp_path: Path) -> None:
    vm_dir = tmp_path / "019f5463-c047-7637-92e4-b25d7105af81"
    vm_dir.mkdir()
    (vm_dir / "vm.yaml").write_text("isolation:\n  backend: qemu\n")
    assert _is_qemu_vm_dir(vm_dir) is True


def test_cleanup_orphan_skips_base_only(tmp_path: Path, monkeypatch) -> None:
    vms = tmp_path / ".vms"
    vms.mkdir()
    (vms / "_base").mkdir()
    monkeypatch.chdir(tmp_path)
    removed = cleanup_orphan_qemu_vms(max_age_seconds=0)
    assert removed == []


def test_qemu_tracker_register_dedupes() -> None:
    tracker = QemuTracker()
    tracker.register("019f5463-c047-7637-92e4-b25d7105af81")
    tracker.register("019f5463-c047-7637-92e4-b25d7105af81")
    assert tracker.uuids == ["019f5463-c047-7637-92e4-b25d7105af81"]
