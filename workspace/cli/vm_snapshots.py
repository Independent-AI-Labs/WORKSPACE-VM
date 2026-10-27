"""QEMU snapshot, export, and import operations."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

from workspace.cli.hypervisor.factory import get_backend
from workspace.cli.hypervisor.qemu_images import allocate_ssh_port
from workspace.cli.hypervisor.qemu_resolve import resolve_qemu_img
from workspace.cli.hypervisor.qemu_state import load_state, mark_stopped, save_state
from workspace.cli.vm_core import _VMS_DIR
from workspace.cli.vm_lifecycle import load_vm_config
from workspace.types.vm import VMConfig
from workspace.utils.uuid_utils import uuid7

_BUNDLE_FILES = (
    "disk.qcow2",
    "vm.yaml",
    "vm-install-defaults.yaml",
    "state.yaml",
    "password",
    "qemu_ssh_ed25519",
    "cloud-init/seed.img",
    "cloud-init/user-data",
    "cloud-init/meta-data",
)
_MANIFEST = "manifest.json"
_FORMAT = 1


def _require_qemu(uuid: str) -> Path:
    cfg = load_vm_config(uuid)
    if cfg.isolation.backend != "qemu":
        msg = f"vm: backup operations require the qemu backend: {uuid}"
        raise ValueError(msg)
    return _VMS_DIR / uuid


def _run_qemu_img(*args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            [str(resolve_qemu_img()), *args],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip()
        msg = f"vm: qemu-img failed: {detail}"
        raise RuntimeError(msg) from exc


def snapshot_create(uuid: str, name: str) -> None:
    vm_dir = _require_qemu(uuid)
    get_backend(load_vm_config(uuid)).stop(uuid)
    _run_qemu_img("snapshot", "-c", name, str(vm_dir / "disk.qcow2"))
    print(f"VM {uuid} snapshot created: {name}")


def snapshot_list(uuid: str) -> None:
    vm_dir = _require_qemu(uuid)
    result = _run_qemu_img("snapshot", "-l", str(vm_dir / "disk.qcow2"))
    sys.stdout.write(result.stdout)


def snapshot_delete(uuid: str, name: str) -> None:
    vm_dir = _require_qemu(uuid)
    get_backend(load_vm_config(uuid)).stop(uuid)
    _run_qemu_img("snapshot", "-d", name, str(vm_dir / "disk.qcow2"))
    print(f"VM {uuid} snapshot deleted: {name}")


def export_vm(uuid: str, destination: Path) -> None:
    vm_dir = _require_qemu(uuid)
    get_backend(load_vm_config(uuid)).stop(uuid)
    if destination.exists():
        msg = f"vm: export destination already exists: {destination}"
        raise FileExistsError(msg)
    destination.mkdir(parents=True)
    for name in _BUNDLE_FILES:
        source = vm_dir / name
        if source.is_file():
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    manifest = {
        "format": _FORMAT,
        "source_uuid": uuid,
        "created_at": datetime.now(UTC).isoformat(),
        "files": [name for name in _BUNDLE_FILES if (destination / name).is_file()],
    }
    (destination / _MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"VM {uuid} exported to {destination}")


def import_vm(source: Path) -> str:
    manifest_path = source / _MANIFEST
    if not manifest_path.is_file():
        msg = f"vm: import manifest missing: {manifest_path}"
        raise FileNotFoundError(msg)
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("format") != _FORMAT:
        msg = f"vm: unsupported import format: {manifest.get('format')!r}"
        raise ValueError(msg)
    disk = source / "disk.qcow2"
    config = source / "vm.yaml"
    if not disk.is_file() or not config.is_file():
        msg = f"vm: import bundle is missing disk or config: {source}"
        raise FileNotFoundError(msg)
    _run_qemu_img("info", str(disk))

    uuid = uuid7()
    vm_dir = _VMS_DIR / uuid
    vm_dir.mkdir(parents=True)
    for name in _BUNDLE_FILES:
        item = source / name
        if item.is_file():
            target = vm_dir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)
    imported_cfg = VMConfig.model_validate(
        yaml.safe_load((vm_dir / "vm.yaml").read_text())
    )
    ssh_port = allocate_ssh_port(imported_cfg.isolation.qemu.ssh_host_port)
    (vm_dir / "ssh_port").write_text(str(ssh_port))
    state = load_state(vm_dir)
    if state is None:
        mark_stopped(vm_dir)
        state = load_state(vm_dir)
    if state is not None:
        state.created_at = datetime.now(UTC).isoformat()
        state.last_started_at = None
        state.last_stopped_at = None
        state.last_error = None
        state.pid_start = None
        state.ssh_port = ssh_port
        save_state(vm_dir, state)
    print(f"VM imported as {uuid}")
    return uuid
